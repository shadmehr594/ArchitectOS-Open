"""ARCHITECTURAL_MATERIAL_INTENT_FIDELITY_V1 - CPU-only acceptance.

A material the user REJECTED must never become a positive render requirement,
and an affirmed replacement material must survive to the workflow node.

Real deterministic chain only:

    ArchitecturalIntent.extract()
      -> ArchitecturalKnowledgeResolver (material resolution)
      -> build_render_instruction()  (prohibition evidence)
      -> PromptBuilder -> resolve_render_prompt -> WorkflowInjector node

Positive material assertions and the prohibition are inspected SEPARATELY.

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
def _intent(text):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        return ArchitecturalIntent().extract({"prompt": text})


def _materials(text):
    return list(_intent(text).get("materials") or [])


def _instruction(text):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        return build_render_instruction(text, mode="text2img")


def _rejected(text):
    return (_instruction(text).get("constraints") or {}).get("negations", {}).get(
        "rejected_span"
    )


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


def _workflow_positive(text):
    intent = _intent(text)
    instruction = _instruction(text)
    provenance = (instruction.get("constraints") or {}).get(
        "floor_count_provenance"
    ) or {}
    handoff = {
        "contract": "RenderConstraintBlockV1",
        "version": "1.0",
        "constraint_block": build_constraint_block(instruction),
        "source": "render_instruction.english_instruction",
        "floor_count": (
            provenance.get("value")
            if provenance.get("source") in ("USER_TEXT", "USER_CONFIRMATION")
            else None
        ),
    }
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


def _positive_body(prompt):
    """The prompt with every prohibition sentence removed."""

    return PROHIBITION.sub("", prompt)


# ---------------------------------------------------------------------------
# 1. Case A - rejected Persian material must not become a requirement.
# ---------------------------------------------------------------------------


def test_rejected_red_brick_is_not_a_positive_material():
    text = "نه آجر قرمز بلکه سنگ"

    assert _materials(text) == ["natural stone facade"]
    assert "red brick" not in " ".join(_materials(text)).lower()

    final_prompt, positive = _workflow_positive(text)
    assert "red brick" not in _positive_body(final_prompt).lower()
    assert "red brick" not in _positive_body(positive).lower()


def test_affirmed_stone_replacement_survives_to_the_workflow_node():
    text = "نه آجر قرمز بلکه سنگ"

    final_prompt, positive = _workflow_positive(text)
    assert "natural stone facade" in final_prompt
    assert "natural stone facade" in positive


def test_rejected_material_is_still_named_by_the_prohibition():
    text = "نه آجر قرمز بلکه سنگ"

    assert _rejected(text) == "آجر قرمز"
    final_prompt, positive = _workflow_positive(text)
    assert _prohibitions(final_prompt) == ["آجر قرمز"]
    assert _prohibitions(positive) == ["آجر قرمز"]


def test_negation_only_material_leaves_no_positive_requirement():
    text = "نه آجر قرمز"

    assert _materials(text) == []
    final_prompt, positive = _workflow_positive(text)
    assert "red brick" not in _positive_body(positive).lower()
    assert _prohibitions(positive) == ["آجر قرمز"]


def test_rejected_material_is_not_invented_as_another_material():
    text = "نه آجر قرمز بلکه سنگ"
    materials = _materials(text)

    assert materials == ["natural stone facade"]
    assert "traditional brick facade" not in materials
    assert "fire resistant brick facade" not in materials


# ---------------------------------------------------------------------------
# 2. English contrastive replacement, with synonyms the ontology knows.
# ---------------------------------------------------------------------------


def test_english_contrastive_replacement_is_preserved():
    text = "not red brick, but natural stone"

    assert _materials(text) == ["natural stone facade"]

    final_prompt, positive = _workflow_positive(text)
    assert "natural stone facade" in positive
    assert "red brick" not in _positive_body(positive).lower()
    assert _prohibitions(positive) == ["red brick"]


# ---------------------------------------------------------------------------
# 3. Positive and rejected evidence stay distinguishable.
# ---------------------------------------------------------------------------


def test_positive_and_rejected_material_evidence_are_distinguishable():
    text = "نه آجر قرمز بلکه سنگ"

    rejected = _rejected(text)
    materials = _materials(text)

    assert rejected == "آجر قرمز"
    assert materials == ["natural stone facade"]
    assert rejected not in materials
    assert "آجر قرمز" not in " ".join(materials)


# ---------------------------------------------------------------------------
# 4. Existing affirmative material ontology mappings are unchanged.
# ---------------------------------------------------------------------------

AFFIRMATIVE = [
    ("آجر قرمز", "red brick facade"),
    ("نمای سنگی", "natural stone facade"),
    ("red brick", "red brick facade"),
    ("stone facade", "natural stone facade"),
    # VISION_GENERIC_BRICK_IDENTITY_V1 — this entry used to expect
    # "red brick facade", and that expectation WAS the defect: the red record
    # declared "brick facade" as a synonym, so a generic English phrase
    # produced a colour the text never named. A generic phrase stays generic.
    ("brick facade", "brick facade"),
    ("travertine", "travertine stone facade"),
    ("بتن اکسپوز", "exposed concrete"),
]


@pytest.mark.parametrize("text,expected", AFFIRMATIVE)
def test_affirmative_material_mappings_are_intact(text, expected):
    assert _materials(text) == [expected]
    _final_prompt, positive = _workflow_positive(text)
    assert expected in positive
    assert _prohibitions(positive) == []


def test_affirmative_request_gets_no_material_it_did_not_name():
    text = "یک ویلای مدرن با سقف شیبدار"
    assert _materials(text) == []
    _final_prompt, positive = _workflow_positive(text)
    assert "brick" not in positive.lower()
    assert "stone facade" not in positive.lower()


# ---------------------------------------------------------------------------
# 5. Case B - English contrastive replacement (closed by
#    MATERIAL_VOCABULARY_COMPLETENESS_V1, which added the bare `stone` synonym
#    to the existing generic stone record).
# ---------------------------------------------------------------------------


def test_english_bare_stone_replacement_now_survives():
    text = "not brick, but stone"

    assert _materials(text) == ["natural stone facade"]

    final_prompt, positive = _workflow_positive(text)
    assert "natural stone facade" in positive
    assert _prohibitions(positive) == ["brick"]
    assert "brick facade" not in _positive_body(positive).lower()
    assert "red brick" not in _positive_body(final_prompt).lower()


def test_persian_adjectival_brick_form_resolves_to_generic_brick():
    """`نمای آجری` now resolves to the GENERIC brick record — no red colour.

    The generic `brick` record was added additively; `brick_red` keeps its own
    synonyms and meaning.
    """

    assert _materials("نمای آجری") == ["brick facade"]
    _final_prompt, positive = _workflow_positive("نمای آجری")
    assert "brick facade" in positive
    assert "red brick" not in _positive_body(positive).lower()
