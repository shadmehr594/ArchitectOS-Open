"""MATERIAL_VOCABULARY_COMPLETENESS_V1 - CPU-only acceptance.

Generic material vocabulary is now resolvable WITHOUT inventing a colour,
finish or subtype, and a generic material is never asserted alongside the more
specific material that names it.

Real deterministic chain only:

    ArchitecturalIntent.extract() -> material ontology resolution
      -> PromptBuilder -> resolve_render_prompt -> WorkflowInjector node

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
SUBTYPES = ("travertine", "marble", "granite")


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
    return PROHIBITION.sub("", prompt)


# ---------------------------------------------------------------------------
# 1-9. The required acceptance matrix.
# ---------------------------------------------------------------------------

ACCEPTANCE = [
    ("stone", ["natural stone facade"], None),
    ("not brick, but stone", ["natural stone facade"], "brick"),
    ("brick", ["brick facade"], None),
    ("نمای آجری", ["brick facade"], None),
    ("آجر قرمز", ["red brick facade"], None),
    ("نه آجر قرمز بلکه سنگ", ["natural stone facade"], "آجر قرمز"),
    ("not red brick, but brick", ["brick facade"], "red brick"),
    ("نمای سنگی", ["natural stone facade"], None),
    ("travertine", ["travertine stone facade"], None),
]


@pytest.mark.parametrize("text,expected,rejected", ACCEPTANCE)
def test_material_resolution_matrix(text, expected, rejected):
    assert _materials(text) == expected

    final_prompt, positive = _workflow_positive(text)
    for material in expected:
        assert material in positive

    if rejected is None:
        assert _prohibitions(positive) == []
    else:
        assert _prohibitions(positive) == [rejected]


# ---------------------------------------------------------------------------
# Critical architectural rule: generic must not invent colour or subtype.
# ---------------------------------------------------------------------------

GENERIC_BRICK = ["brick", "نمای آجری", "brick villa", "brick house"]
GENERIC_STONE = ["stone", "stone villa", "stone house"]


@pytest.mark.parametrize("text", GENERIC_BRICK)
def test_generic_brick_never_invents_red(text):
    materials = _materials(text)
    assert materials == ["brick facade"]
    joined = " ".join(materials).lower()
    assert "red" not in joined
    assert "fire" not in joined

    _final_prompt, positive = _workflow_positive(text)
    assert "red brick" not in _positive_body(positive).lower()


@pytest.mark.parametrize("text", GENERIC_STONE)
def test_generic_stone_never_invents_a_subtype(text):
    materials = _materials(text)
    assert materials == ["natural stone facade"]
    joined = " ".join(materials).lower()
    for subtype in SUBTYPES:
        assert subtype not in joined


# ---------------------------------------------------------------------------
# Specificity: no duplicate generic assertion next to a specific material.
# ---------------------------------------------------------------------------

SPECIFIC_ONLY = [
    ("آجر قرمز", "red brick facade"),
    ("red brick", "red brick facade"),
    # VISION_GENERIC_BRICK_IDENTITY_V1 — `("brick facade", "red brick facade")`
    # was removed from this list. It is not a specific material: the phrase
    # names no colour, and the old expectation was produced by a synonym
    # ("brick facade" on the red record), not by anything the text said. Its
    # corrected behaviour is pinned in
    # tests/test_vision_generic_brick_identity_v1.py.
    ("آجر نسوز", "fire resistant brick facade"),
    ("travertine", "travertine stone facade"),
    ("تراورتن", "travertine stone facade"),
    ("سنگ مرمر", "natural marble finish"),
    ("نمای سنگی", "natural stone facade"),
]


@pytest.mark.parametrize("text,expected", SPECIFIC_ONLY)
def test_specific_material_is_not_duplicated_by_a_generic_one(text, expected):
    assert _materials(text) == [expected]


def test_generic_brick_facade_no_longer_invents_a_colour():
    """`brick facade` is GENERIC brick — the legacy RED meaning is reversed.

    VISION_GENERIC_BRICK_IDENTITY_V1 reverses MATERIAL_VOCABULARY_COMPLETENESS_V1
    here. That milestone preserved the red meaning on the grounds that
    "brick facade" was an existing `brick_red` synonym and the generic record
    was suppressed by containment. Both observations were true, and neither is
    evidence: an ontology synonym is a mapping someone once wrote, not a
    statement the text makes. A generic phrase must not publish a colour.
    """

    assert _materials("brick facade") == ["brick facade"]

    assert "red" not in " ".join(_materials("brick facade")).lower()


def test_generic_and_specific_can_coexist_when_both_are_named():
    materials = _materials("brick and stone villa")
    assert materials == ["brick facade", "natural stone facade"]


# ---------------------------------------------------------------------------
# Rejected occurrences never become positive requirements, with the new
# vocabulary in place.
# ---------------------------------------------------------------------------


def test_rejected_generic_brick_is_not_positive():
    text = "not brick"
    assert _materials(text) == []
    _final_prompt, positive = _workflow_positive(text)
    assert "brick" not in _positive_body(positive).lower()
    assert _prohibitions(positive) == ["brick"]


def test_rejected_generic_stone_is_not_positive():
    text = "نه سنگ"
    assert _materials(text) == []
    _final_prompt, positive = _workflow_positive(text)
    assert "stone" not in _positive_body(positive).lower()


def test_rejected_specific_keeps_affirmed_generic():
    text = "not red brick, but brick"
    assert _materials(text) == ["brick facade"]
    final_prompt, positive = _workflow_positive(text)
    assert "red brick" not in _positive_body(final_prompt).lower()
    assert "brick facade" in positive
