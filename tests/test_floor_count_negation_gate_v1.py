"""FLOOR_COUNT_NEGATION_GATE_V1 - CPU-only acceptance.

A negated floor-count candidate must never become a positive exact floor-count
hard constraint. The tests exercise the REAL deterministic chain:

    _floor_count()
      -> ArchitecturalIntent.extract()      (canonical floors + FloorCountV1)
      -> build_render_instruction()         (structured render instruction)
      -> build_constraint_block()           (RenderConstraintBlockV1)
      -> PromptBuilder
      -> resolve_render_prompt()
      -> WorkflowInjector                   (final workflow positive CLIP node)

No LLM, Ollama, ComfyUI, GPU, renderer, workflow submission or network call.
"""

from __future__ import annotations

import contextlib
import io
import re
from functools import lru_cache

import pytest

from core.cognition.architectural_render_instruction_v1 import (
    _floor_count,
    build_constraint_block,
    build_render_instruction,
)
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)
from core.render.prompt_builder import PromptBuilder
from core.render.workflow_injector import WorkflowInjector


FLOOR_PHRASE = re.compile(
    r"\b(?:exactly\s+)?\d+\s*(?:story|storey|stories|storeys|floor|floors)\b",
    re.IGNORECASE,
)


@lru_cache(maxsize=None)
def _intent(text):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        return ArchitecturalIntent().extract({"prompt": text})


@lru_cache(maxsize=None)
def _instruction(text):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        return build_render_instruction(text, mode="text2img")


def _constraints(text):
    return _instruction(text).get("constraints") or {}


def _instruction_floor(text):
    floor = _constraints(text).get("floor_count")
    return floor.get("value") if isinstance(floor, dict) else None


def _provenance(text):
    return _constraints(text).get("floor_count_provenance") or {}


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
    return built, final_prompt, workflow["1"]["inputs"]["text"]


# ---------------------------------------------------------------------------
# 1. Negated floor-count statements never become a positive exact constraint.
# ---------------------------------------------------------------------------

NEGATED = [
    "not a three-storey building",
    "I do not want a three-storey building",
    "no three-storey building",
    "the building is not a two-storey house",
    "not four storeys",
    "این ساختمان سه طبقه نیست",
]


@pytest.mark.parametrize("text", NEGATED)
def test_negated_count_is_not_a_total(text):
    assert _floor_count(text) is None
    assert _intent(text).get("floors") is None
    assert _instruction_floor(text) is None
    assert _published(text)["floor_count"] is None


@pytest.mark.parametrize("text", NEGATED)
def test_negated_count_publishes_no_hard_constraint(text):
    provenance = _provenance(text)
    assert provenance.get("source") not in ("USER_TEXT", "USER_CONFIRMATION")
    assert provenance.get("hard_constraint") is not True


@pytest.mark.parametrize("text", NEGATED)
def test_negated_count_provenance_stays_unknown(text):
    floor_count = _intent(text).get("floor_count") or {}
    assert floor_count.get("value") is None
    assert floor_count.get("source") != "user_explicit"


@pytest.mark.parametrize("text", NEGATED)
def test_negated_count_never_reaches_the_workflow_prompt(text):
    _built, final_prompt, positive = _final_positive(text)
    assert "exactly" not in final_prompt.lower()
    assert FLOOR_PHRASE.findall(final_prompt) == []
    assert FLOOR_PHRASE.findall(positive) == []


# ---------------------------------------------------------------------------
# 2. Affirmed and negated counts in the same request: keep the affirmed one,
#    never promote the negated one.
# ---------------------------------------------------------------------------

MIXED = [
    ("three-storey building, not four-storey", 3, 4),
    ("a three-storey building, not a four-storey one", 3, 4),
    ("four-storey building, not three-storey", 4, 3),
    ("not a three-storey building, but a four-storey one", 4, 3),
    ("exactly 5 floors, not 4 floors", 5, 4),
    ("ساختمان سه طبقه نیست، چهار طبقه است", 4, 3),
]


@pytest.mark.parametrize("text,kept,dropped", MIXED)
def test_mixed_request_keeps_affirmed_and_drops_negated(text, kept, dropped):
    assert (_floor_count(text) or {}).get("value") == kept
    assert _intent(text).get("floors") == kept
    assert _instruction_floor(text) == kept
    assert _published(text)["floor_count"] == kept
    assert (_intent(text).get("floor_count") or {}).get("value") == kept


@pytest.mark.parametrize("text,kept,dropped", MIXED)
def test_mixed_request_prompt_contains_only_the_affirmed_count(
    text, kept, dropped
):
    _built, final_prompt, positive = _final_positive(text)
    assert ("%d story building" % kept) in final_prompt
    assert ("%d story building" % dropped) not in final_prompt
    assert ("exactly %d floors" % dropped) not in final_prompt


# ---------------------------------------------------------------------------
# 3. The five previously accepted affirmative expressions keep working.
# ---------------------------------------------------------------------------

ACCEPTED = [
    ("ساختمان دو طبقه", 2),
    ("نمای ساختمان سه طبقه", 3),
    ("two-storey house", 2),
    ("three-story building", 3),
    ("exactly 5 floors", 5),
]


@pytest.mark.parametrize("text,expected", ACCEPTED)
def test_accepted_affirmative_expressions_are_unchanged(text, expected):
    assert (_floor_count(text) or {}).get("value") == expected
    assert _intent(text).get("floors") == expected
    assert (_intent(text).get("floor_count") or {}).get("value") == expected
    assert (_intent(text).get("floor_count") or {}).get("source") == "user_explicit"
    assert _instruction_floor(text) == expected


@pytest.mark.parametrize("text,expected", ACCEPTED)
def test_accepted_affirmative_provenance_is_user_text(text, expected):
    provenance = _provenance(text)
    assert provenance.get("value") == expected
    assert provenance.get("source") == "USER_TEXT"
    assert provenance.get("hard_constraint") is True


@pytest.mark.parametrize("text,expected", ACCEPTED)
def test_accepted_affirmative_reaches_the_workflow_prompt(text, expected):
    _built, final_prompt, positive = _final_positive(text)
    assert ("exactly %d floors" % expected) in final_prompt
    assert ("%d story building" % expected) in positive


# ---------------------------------------------------------------------------
# 4. A negated count must not discard the rest of the user's constraints.
# ---------------------------------------------------------------------------


def test_negated_floor_does_not_discard_other_constraints():
    text = "not a three-storey building with a red brick facade"
    assert _floor_count(text) is None
    _built, final_prompt, positive = _final_positive(text)
    assert "brick" in final_prompt.lower()
    assert FLOOR_PHRASE.findall(positive) == []


def test_preserve_wording_keeps_an_affirmed_count():
    text = "ساختمان ۴ طبقه است، بدون تغییر در تعداد طبقات"
    assert (_floor_count(text) or {}).get("value") == 4
    assert _intent(text).get("floors") == 4
    assert _published(text)["floor_count"] == 4


def test_negation_of_another_element_does_not_remove_the_count():
    text = "no garage, three-storey house"
    assert (_floor_count(text) or {}).get("value") == 3
    assert _instruction_floor(text) == 3
