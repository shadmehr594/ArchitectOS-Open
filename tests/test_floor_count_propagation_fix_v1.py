"""FLOOR_COUNT_PROPAGATION_FIX_V1 — focused CPU-only regression coverage.

No LLM, Ollama, ComfyUI, GPU model, workflow file, or render is used.  The
tests call the real production normalizer and deterministic downstream
consumers.  Raw prompts used for integration contain no floor words or digits,
so a numeric prompt phrase can only originate in structured metadata.
"""

from __future__ import annotations

import contextlib
import io
import re

import pytest

from core.chat.handlers.image_handler import ImageHandler
from core.prompt_intelligence.prompt_router import PromptRouter
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)
from core.render.prompt_builder import PromptBuilder
from core.render.workflow_injector import WorkflowInjector


NO_FLOOR_WORDS_PROMPT = (
    "Brick villa with a symmetrical facade, pitched roof and daylight"
)
_NOT_PROVIDED = object()


def _trusted_instruction(floors):
    return {
        "contract": "RenderConstraintBlockV1",
        "version": "1.0",
        "constraint_block": "The building has exactly %s floors." % floors,
        "source": "render_instruction.english_instruction",
        "floor_count": floors,
    }


def _normalize(intent, floor_constraint=_NOT_PROVIDED):
    handler = ImageHandler.__new__(ImageHandler)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        if floor_constraint is _NOT_PROVIDED:
            return handler.normalize_intent(intent)
        return handler.normalize_intent(
            intent,
            floor_constraint=floor_constraint,
        )


def _synthetic_workflow():
    return {
        "1": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "template positive"},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "template negative"},
        },
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


def _floor_phrases(text):
    return re.findall(
        r"(?:single floor building|\d+ story building|exactly \d+ floors?)",
        str(text or ""),
        flags=re.IGNORECASE,
    )


def _downstream(raw_floor, floor_constraint=None):
    raw = {
        "prompt": NO_FLOOR_WORDS_PROMPT,
        "building": {
            "type": "villa",
            "style": "traditional_residential",
        },
        "materials": ["brick"],
    }
    if raw_floor is not None:
        raw["building"]["floors"] = raw_floor

    normalized = _normalize(raw, floor_constraint=floor_constraint)
    design = {
        "prompt": NO_FLOOR_WORDS_PROMPT,
        "architectural_intent": normalized,
        "floors": (
            floor_constraint.get("floor_count")
            if isinstance(floor_constraint, dict)
            else None
        ),
    }
    built = PromptBuilder().build(design)
    routed = PromptRouter().build(design, mode="text2img")
    resolved = resolve_render_prompt(
        compiled_prompt="Architectural visualization of the requested villa.",
        builder_prompt=built.get("description") or "",
        user_text=NO_FLOOR_WORDS_PROMPT,
        architectural_instruction=floor_constraint,
    )
    final_prompt = resolved.get("prompt") or resolved.get("final_prompt") or ""
    workflow = WorkflowInjector().inject_prompt(
        _synthetic_workflow(),
        final_prompt,
        None,
    )
    return {
        "normalized": normalized,
        "design": design,
        "built": built,
        "routed": routed,
        "final_prompt": final_prompt,
        "positive_prompt": workflow["1"]["inputs"]["text"],
    }


@pytest.mark.parametrize("floors", [2, 4, 3])
def test_nested_floor_is_projected_to_canonical_metadata(floors):
    normalized = _normalize(
        {
            "prompt": NO_FLOOR_WORDS_PROMPT,
            "building": {"type": "villa", "floors": floors},
        }
    )

    assert normalized.get("floors") == floors


def test_no_floor_remains_unknown():
    normalized = _normalize(
        {"prompt": NO_FLOOR_WORDS_PROMPT, "building": {"type": "villa"}}
    )

    assert "floors" not in normalized


def test_valid_top_level_floor_is_preserved_when_nested_is_unavailable():
    normalized = _normalize(
        {
            "prompt": NO_FLOOR_WORDS_PROMPT,
            "building": {"type": "villa"},
            "floors": 5,
        }
    )

    assert normalized.get("floors") == 5


@pytest.mark.parametrize(
    "invalid",
    [None, True, False, 0, -1, 2.5, "two", "", [], {}, float("nan"), float("inf")],
)
def test_invalid_floor_values_are_not_promoted(invalid):
    normalized = _normalize(
        {
            "prompt": NO_FLOOR_WORDS_PROMPT,
            "building": {"type": "villa", "floors": invalid},
        }
    )

    assert "floors" not in normalized


def test_invalid_nested_value_allows_valid_top_level_fallback():
    normalized = _normalize(
        {
            "prompt": NO_FLOOR_WORDS_PROMPT,
            "building": {"type": "villa", "floors": False},
            "floors": 4,
        }
    )

    assert normalized.get("floors") == 4


def test_nested_value_outranks_weaker_top_level_semantic_fallback():
    normalized = _normalize(
        {
            "prompt": NO_FLOOR_WORDS_PROMPT,
            "building": {"type": "villa", "floors": 2},
            "floors": 4,
        }
    )

    assert normalized.get("floors") == 2


def test_user_explicit_floor_contract_outranks_conflicting_semantic_values():
    normalized = _normalize(
        {
            "prompt": NO_FLOOR_WORDS_PROMPT,
            "building": {"type": "villa", "floors": 2},
            "floors": 4,
            "floor_count": {
                "contract": "FloorCountV1",
                "value": 6,
                "source": "user_explicit",
            },
        }
    )

    assert normalized.get("floors") == 6


def test_untrusted_floor_contract_does_not_override_semantic_value():
    normalized = _normalize(
        {
            "prompt": NO_FLOOR_WORDS_PROMPT,
            "building": {"type": "villa", "floors": 2},
            "floor_count": {
                "contract": "FloorCountV1",
                "value": 6,
                "source": "inferred",
            },
        }
    )

    assert normalized.get("floors") == 2


def test_published_hard_constraint_outranks_all_semantic_values():
    normalized = _normalize(
        {
            "prompt": NO_FLOOR_WORDS_PROMPT,
            "building": {"type": "villa", "floors": 2},
            "floors": 3,
            "floor_count": {
                "contract": "FloorCountV1",
                "value": 4,
                "source": "user_explicit",
            },
        },
        floor_constraint=_trusted_instruction(5),
    )

    assert normalized.get("floors") == 5


def test_untrusted_external_constraint_does_not_override_semantic_value():
    normalized = _normalize(
        {
            "prompt": NO_FLOOR_WORDS_PROMPT,
            "building": {"type": "villa", "floors": 2},
        },
        floor_constraint={"floor_count": 9},
    )

    assert normalized.get("floors") == 2


def test_existing_building_style_and_material_mappings_are_unchanged():
    normalized = _normalize(
        {
            "prompt": NO_FLOOR_WORDS_PROMPT,
            "building": {
                "type": "villa",
                "style": "traditional_residential",
                "floors": 2,
            },
            "materials": ["brick", "wood"],
            "facade": {"details": ["symmetrical composition"]},
        }
    )

    assert normalized["building_type"] == "villa"
    assert normalized["style"] == "traditional_residential"
    assert normalized["materials"] == ["brick", "wood"]
    assert normalized["facade_details"] == ["symmetrical composition"]


@pytest.mark.parametrize("floors", [2, 4])
def test_structured_floor_reaches_router_resolver_and_positive_node(floors):
    result = _downstream(floors)
    phrase = "%d story building" % floors

    assert result["normalized"]["floors"] == floors
    assert result["built"]["floors"] == floors
    assert phrase in result["built"]["description"]
    assert phrase in result["routed"]["description"]
    assert phrase in result["final_prompt"]
    assert phrase in result["positive_prompt"]
    assert _floor_phrases(result["positive_prompt"]) == [phrase]
    assert str(floors) not in NO_FLOOR_WORDS_PROMPT


def test_unknown_reaches_positive_node_without_inventing_a_floor():
    result = _downstream(None)

    assert "floors" not in result["normalized"]
    assert result["built"]["floors"] is None
    assert _floor_phrases(result["built"]["description"]) == []
    assert _floor_phrases(result["final_prompt"]) == []
    assert _floor_phrases(result["positive_prompt"]) == []


def test_explicit_hard_constraint_is_not_weakened_by_semantic_conflict():
    instruction = _trusted_instruction(4)
    result = _downstream(2, floor_constraint=instruction)

    assert result["normalized"]["floors"] == 4
    assert result["built"]["floors"] == 4
    assert "exactly 4 floors" in result["final_prompt"]
    assert "4 story building" in result["final_prompt"]
    assert "2 story building" not in result["final_prompt"]
    assert "exactly 2 floors" not in result["final_prompt"]
    assert "2 story building" not in result["positive_prompt"]
    assert "exactly 2 floors" not in result["positive_prompt"]
