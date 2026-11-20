"""ENGLISH_FLOOR_COUNT_PARSER_PARITY_V1 — CPU-only acceptance.

The tests use the real production parsers and deterministic prompt consumers.
They contact no LLM, Ollama, ComfyUI, GPU, renderer, or workflow service.
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


def _instruction_value(text):
    floor = (_instruction(text).get("constraints") or {}).get("floor_count")
    return floor.get("value") if isinstance(floor, dict) else None


def _published_instruction(text):
    instruction = _instruction(text)
    block = build_constraint_block(instruction)
    provenance = (
        (instruction.get("constraints") or {}).get("floor_count_provenance")
        or {}
    )
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


def _final_positive(text):
    intent = _intent(text)
    handoff = _published_instruction(text)
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
    return intent, _instruction(text), final_prompt, workflow["1"]["inputs"]["text"]


ENGLISH_CASES = [
    ("Two-storey brick villa", 2),
    ("Four-storey residential building", 4),
    ("Two-story brick villa", 2),
    ("Three-storey residential building", 3),
    ("four storeys with a brick facade", 4),
    ("2-storey brick villa", 2),
    ("4-story residential building", 4),
]


@pytest.mark.parametrize("text,expected", ENGLISH_CASES)
def test_english_forms_are_recognized_by_both_consumers(text, expected):
    intent = _intent(text)
    contract = intent.get("floor_count") or {}
    instruction = _instruction(text)
    provenance = (
        (instruction.get("constraints") or {}).get("floor_count_provenance")
        or {}
    )

    assert _floor_count(text)["value"] == expected
    assert intent.get("floors") == expected
    assert contract.get("contract") == "FloorCountV1"
    assert contract.get("value") == expected
    assert contract.get("source") == "user_explicit"
    assert _instruction_value(text) == expected
    assert provenance.get("value") == expected
    assert provenance.get("source") == "USER_TEXT"
    assert provenance.get("hard_constraint") is True


@pytest.mark.parametrize(
    "text,expected",
    [
        ("ساختمان سه طبقه", 3),
        ("ویلای دو‌طبقه", 2),
        ("برج ۴-طبقه", 4),
    ],
)
def test_existing_persian_recognition_is_preserved(text, expected):
    intent = _intent(text)

    assert _floor_count(text)["value"] == expected
    assert intent.get("floors") == expected
    assert (intent.get("floor_count") or {}).get("value") == expected
    assert _instruction_value(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "A brick villa with a pitched roof",
        "Put arched windows on the second floor of the existing building",
        "Tell a story about a brick villa",
        "The design story should describe four facade materials",
        "twenty-one-storey building",
        "twenty one storey building",
    ],
)
def test_negative_controls_remain_unknown(text):
    intent = _intent(text)
    instruction = _instruction(text)

    assert _floor_count(text) is None
    assert "floors" not in intent
    assert (intent.get("floor_count") or {}).get("value") is None
    assert (intent.get("floor_count") or {}).get("source") == "unspecified"
    assert (instruction.get("constraints") or {}).get("floor_count") is None
    assert (
        (instruction.get("constraints") or {}).get("floor_count_provenance")
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        "two storeys or four storeys",
        "2-storey or 4-story building",
        "ساختمان سه طبقه یا چهار طبقه",
        "three-storey building, alternatively a 4-storey building",
    ],
)
def test_conflicting_counts_fail_closed(text):
    intent = _intent(text)
    instruction = _instruction(text)

    assert _floor_count(text) is None
    assert "floors" not in intent
    assert (intent.get("floor_count") or {}).get("value") is None
    assert (intent.get("floor_count") or {}).get("source") == "unspecified"
    assert (instruction.get("constraints") or {}).get("floor_count") is None
    assert (
        (instruction.get("constraints") or {}).get("floor_count_provenance")
        is None
    )


@pytest.mark.parametrize("text,expected", ENGLISH_CASES[:5])
def test_word_form_reaches_final_synthetic_positive_node(text, expected):
    intent, instruction, final_prompt, positive_prompt = _final_positive(text)
    numeric_story = "%d story building" % expected
    exact_floor = "exactly %d floors" % expected

    assert intent.get("floors") == expected
    assert _instruction_value(text) == expected
    assert numeric_story in final_prompt
    assert exact_floor in final_prompt
    assert numeric_story in positive_prompt
    assert exact_floor in positive_prompt

    observed = {
        int(value)
        for value in re.findall(
            r"(?:exactly\s+)?(\d+)\s+(?:story building|floors?)",
            positive_prompt,
            flags=re.IGNORECASE,
        )
    }
    assert observed == {expected}


def test_unknown_does_not_create_a_final_floor_phrase():
    intent, instruction, final_prompt, positive_prompt = _final_positive(
        "A brick villa with a pitched roof"
    )

    assert "floors" not in intent
    assert (instruction.get("constraints") or {}).get("floor_count") is None
    assert not re.search(
        r"(?:exactly\s+)?\d+\s+(?:story building|floors?)",
        final_prompt,
        flags=re.IGNORECASE,
    )
    assert not re.search(
        r"(?:exactly\s+)?\d+\s+(?:story building|floors?)",
        positive_prompt,
        flags=re.IGNORECASE,
    )
