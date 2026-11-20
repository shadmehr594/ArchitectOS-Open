"""ARCHITECTURAL_REQUIREMENT_GROUNDING_V1 - CPU-only acceptance.

Two confirmed defects:

  A. An invented facade door (Persian «در زمین» read as the door noun, plus a
     floor numeral donated as a door count).
  B. An invented commercial function (`two-storey house` -> "retail") and
     inferred amenities (pool / terrace) promoted to hard requirements.

Real deterministic chain only:
    ArchitecturalIntent.extract() -> build_render_instruction()
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
    _feature_requirements,
    build_constraint_block,
    build_render_instruction,
)
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)
from core.render.prompt_builder import PromptBuilder
from core.render.workflow_injector import WorkflowInjector

BRICK_VILLA = (
    "یک ویلای مدرن با نمای آجری در زمین داشته باشد: همکف و دو طبقه بالای آن. "
    "ساختمان سه طبقه در کل. نمای ساختمان دارای پنجره‌های بزرگ باشد."
)


@lru_cache(maxsize=None)
def _intent(text):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        return ArchitecturalIntent().extract({"prompt": text})


def _requirements(text):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        return _feature_requirements(text)


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


# ===========================================================================
# Defect A - invented doors
# ===========================================================================


def test_brick_villa_request_invents_no_door():
    requirements = _requirements(BRICK_VILLA)
    assert [r["element"] for r in requirements] == ["window"]

    final_prompt, positive = _workflow_positive(BRICK_VILLA)
    assert "door" not in positive.lower()
    assert "door" not in final_prompt.lower()


def test_brick_villa_request_keeps_its_real_requirements():
    intent = _intent(BRICK_VILLA)
    assert intent.get("materials") == ["brick facade"]
    assert intent.get("floors") == 3

    _final_prompt, positive = _workflow_positive(BRICK_VILLA)
    assert "brick facade" in positive
    assert "exactly 3 floors" in positive
    assert "3 story building" in positive
    assert "window" in positive.lower()


def test_persian_preposition_is_not_a_door():
    for text in (
        "در زمین داشته باشد",
        "ویلایی در زمین داشته باشیم",
        "در این زمین یک ویلا",
    ):
        assert _requirements(text) == [], text


def test_floor_count_is_never_a_door_count():
    requirements = _requirements("ساختمان دو طبقه با یک در چوبی")
    doors = [r for r in requirements if r["element"] == "door"]
    assert len(doors) == 1
    assert doors[0]["count"] != 2
    assert doors[0]["count"] in (None, 1)


def test_explicit_door_requirement_still_works():
    requirements = _requirements("یک در چوبی بگذار")
    assert len(requirements) == 1
    assert requirements[0]["element"] == "door"
    assert requirements[0]["material"] == "wood"

    _final_prompt, positive = _workflow_positive("یک در چوبی بگذار")
    assert "door" in positive.lower()
    assert "wood" in positive.lower()


def test_explicit_window_request_still_works():
    requirements = _requirements("نمای ساختمان دارای پنجره‌های بزرگ باشد")
    assert [r["element"] for r in requirements] == ["window"]
    assert requirements[0]["locations"] == ["facade"]

    _final_prompt, positive = _workflow_positive(
        "نمای ساختمان دارای پنجره‌های بزرگ باشد"
    )
    assert "window" in positive.lower()
    assert "for the facade" in positive.lower()


def test_unknown_door_count_stays_unknown():
    _final_prompt, positive = _workflow_positive(BRICK_VILLA)
    assert "exactly 2 brick doors" not in positive.lower()
    assert re.search(r"exactly \d+ (?:brick )?doors", positive, re.I) is None


# ===========================================================================
# Defect B - invented commercial function and inferred amenities
# ===========================================================================


def test_residential_request_has_no_commercial_function():
    for text in ("two-storey house", "سه طبقه مسکونی", "a two-storey house"):
        assert "retail" not in (_intent(text).get("spaces") or []), text
        _final_prompt, positive = _workflow_positive(text)
        assert "retail" not in positive.lower(), text


def test_explicit_commercial_requests_keep_retail():
    for text in (
        "two-storey retail building",
        "ground-floor shop with two residential floors",
        "مغازه",
    ):
        assert "retail" in (_intent(text).get("spaces") or []), text
        _final_prompt, positive = _workflow_positive(text)
        assert "retail" in positive.lower(), text


def test_inferred_amenities_are_not_hard_requirements():
    text = "brick and stone villa"
    spaces = _intent(text).get("spaces") or []

    assert "pool" not in spaces
    assert "terrace" not in spaces

    _final_prompt, positive = _workflow_positive(text)
    assert "pool" not in positive.lower()
    assert "terrace" not in positive.lower()


def test_category_norm_spaces_are_kept_for_a_residential_request():
    spaces = _intent("brick and stone villa").get("spaces") or []
    assert spaces == ["living_room", "kitchen", "bedroom"]


def test_explicitly_requested_amenity_is_kept():
    spaces = _intent("villa with a swimming pool").get("spaces") or []
    assert "pool" in spaces


def test_optional_amenities_remain_recorded_as_knowledge():
    knowledge = _intent("brick and stone villa").get("knowledge") or {}
    assert knowledge.get("optional_spaces") == ["pool", "terrace"]
