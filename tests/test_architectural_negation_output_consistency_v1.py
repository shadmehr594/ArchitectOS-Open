"""ARCHITECTURAL_NEGATION_OUTPUT_CONSISTENCY_V1 - CPU-only acceptance.

A prohibition must name only the negated architectural requirement. It must
never swallow the affirmed replacement, e.g.

    "not a three-storey building, but a four-storey one"
      -> positive: exactly 4 floors
      -> prohibition: Do NOT use or repeat: a three-storey building.

Real deterministic chain only:

    build_render_instruction()
      -> constraints.negations / floor_count
      -> build_constraint_block()
      -> PromptBuilder
      -> resolve_render_prompt()
      -> WorkflowInjector  (final workflow positive CLIP node)

No LLM, Ollama, ComfyUI, GPU, renderer or network call.
"""

from __future__ import annotations

import contextlib
import io
import re
from functools import lru_cache

import pytest

from core.cognition.architectural_render_instruction_v1 import (
    build_constraint_block,
    build_render_instruction,
)
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)
from core.render.prompt_builder import PromptBuilder
from core.render.workflow_injector import WorkflowInjector

PROHIBITION = re.compile(r"Do NOT use or repeat:\s*([^.]*)\.")


@lru_cache(maxsize=None)
def _instruction(text):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        return build_render_instruction(text, mode="text2img")


@lru_cache(maxsize=None)
def _intent(text):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        return ArchitecturalIntent().extract({"prompt": text})


def _rejected(text):
    return (_instruction(text).get("constraints") or {}).get("negations", {}).get(
        "rejected_span"
    )


def _floor(text):
    floor = (_instruction(text).get("constraints") or {}).get("floor_count")
    return floor.get("value") if isinstance(floor, dict) else None


def _provenance(text):
    return (_instruction(text).get("constraints") or {}).get(
        "floor_count_provenance"
    ) or {}


def _published(text):
    instruction = _instruction(text)
    block = build_constraint_block(instruction)
    provenance = _provenance(text)
    return {
        "contract": "RenderConstraintBlockV1",
        "version": "1.0",
        "constraint_block": block,
        "source": "render_instruction.english_instruction",
        "floor_count": (
            provenance.get("value")
            if provenance.get("source") in ("USER_TEXT", "USER_CONFIRMATION")
            else None
        ),
    }


def _synthetic_workflow():
    return {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "template positive"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "template negative"}},
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "positive": ["1", 0],
                "negative": ["2", 0],
                "seed": 1,
                "steps": 1,
                "denoise": 1.0,
            },
        },
    }


def _final_positive(text):
    intent = _intent(text)
    handoff = _published(text)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        built = PromptBuilder().build(
            {
                "prompt": "Architectural visualization request",
                "architectural_intent": intent,
            }
        )
        resolved = resolve_render_prompt(
            compiled_prompt="Architectural visualization of the requested building.",
            builder_prompt=built.get("description") or "",
            architectural_instruction=handoff,
        )
        final_prompt = resolved.get("prompt") or resolved.get("final_prompt") or ""
        workflow = WorkflowInjector().inject_prompt(
            _synthetic_workflow(), final_prompt, None
        )
    return final_prompt, workflow["1"]["inputs"]["text"]


def _prohibitions(prompt):
    return [m.strip() for m in PROHIBITION.findall(prompt)]


# ---------------------------------------------------------------------------
# 1. Negated requirement + affirmed replacement.
# ---------------------------------------------------------------------------


def test_replacement_is_not_swallowed_by_the_prohibition():
    text = "not a three-storey building, but a four-storey one"

    assert _floor(text) == 4
    assert _provenance(text).get("source") == "USER_TEXT"
    assert _provenance(text).get("hard_constraint") is True
    assert _rejected(text) == "a three-storey building"

    final_prompt, positive = _final_positive(text)
    assert _prohibitions(final_prompt) == ["a three-storey building"]
    assert _prohibitions(positive) == ["a three-storey building"]
    assert "exactly 4 floors" in positive
    assert "4 story building" in positive


def test_affirmed_replacement_never_appears_inside_the_prohibition():
    text = "not a three-storey building, but a four-storey one"
    final_prompt, positive = _final_positive(text)

    for prompt in (final_prompt, positive):
        for prohibition in _prohibitions(prompt):
            assert "four" not in prohibition.lower()
            assert "4-storey" not in prohibition.lower()


def test_replacement_without_a_comma_fails_closed_and_is_still_trimmed():
    """Documented limitation, not a silent guess.

    The shared negation layer treats only punctuation as a clause boundary, so
    without the comma BOTH counts are inside one negation scope and the total
    stays unknown (fail closed). The prohibition itself is still trimmed, so no
    replacement leaks into it. Changing that boundary belongs to the shared
    negation owner, not to this task.
    """

    text = "not a three-storey building but a four-storey one"

    assert _floor(text) is None
    assert _rejected(text) == "a three-storey building"

    final_prompt, positive = _final_positive(text)
    assert _prohibitions(final_prompt) == ["a three-storey building"]
    assert "exactly" not in positive.lower()


# ---------------------------------------------------------------------------
# 2. Affirmed requirement + negated alternative (already correct - keep it).
# ---------------------------------------------------------------------------


def test_negated_alternative_only_is_prohibited():
    text = "three-storey building, not four-storey"

    assert _floor(text) == 3
    assert _rejected(text) == "four-storey"

    final_prompt, positive = _final_positive(text)
    assert _prohibitions(final_prompt) == ["four-storey"]
    assert "exactly 3 floors" in positive
    assert "3 story building" in positive


# ---------------------------------------------------------------------------
# 3. Negation only: no positive count, the requirement stays represented.
# ---------------------------------------------------------------------------


def test_negation_only_keeps_the_requirement_and_no_count():
    text = "not a three-storey building"

    assert _floor(text) is None
    assert _provenance(text).get("hard_constraint") is not True

    final_prompt, positive = _final_positive(text)
    assert _prohibitions(final_prompt) == ["a three-storey building"]
    assert "exactly" not in positive.lower()
    assert re.findall(r"\d+\s*(?:story|storey|stories|storeys|floor|floors)", positive) == []


# ---------------------------------------------------------------------------
# 4. Ordinary affirmative requests stay untouched (no prohibition at all).
# ---------------------------------------------------------------------------

AFFIRMATIVE = [
    ("three-story building", 3),
    ("ساختمان سه طبقه", 3),
    ("two-storey house", 2),
    ("exactly 5 floors", 5),
]


@pytest.mark.parametrize("text,expected", AFFIRMATIVE)
def test_affirmative_requests_emit_no_prohibition(text, expected):
    assert _floor(text) == expected
    assert _rejected(text) == ""
    final_prompt, positive = _final_positive(text)
    assert _prohibitions(final_prompt) == []
    assert "Do NOT use or repeat" not in positive
    assert ("exactly %d floors" % expected) in positive


def test_affirmative_with_another_element_negated_keeps_its_prohibition():
    text = "three-storey building with no garage"
    assert _floor(text) == 3
    final_prompt, positive = _final_positive(text)
    assert "exactly 3 floors" in positive
    for prohibition in _prohibitions(positive):
        assert "three" not in prohibition.lower()


# ---------------------------------------------------------------------------
# 5. The prohibition is never emitted empty.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "not a three-storey building, but a four-storey one",
        "three-storey building, not four-storey",
        "not a three-storey building",
        "not brick, but stone",
    ],
)
def test_prohibition_is_never_empty(text):
    final_prompt, positive = _final_positive(text)
    for prompt in (final_prompt, positive):
        assert "Do NOT use or repeat: ." not in prompt
        for prohibition in _prohibitions(prompt):
            assert prohibition.strip()
