"""FLOOR_COUNT_AMBIGUITY_GUARD_V1 — CPU-only focused acceptance.

The tests exercise the production floor parser and deterministic prompt path.
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


AMBIGUOUS_CASES = [
    pytest.param("2-4 storey building", "range", id="digit-hyphen-range"),
    pytest.param("2 or 4 storey building", "alternative", id="digit-or"),
    pytest.param(
        "two- to four-storey building",
        "range",
        id="word-elided-hyphen-range",
    ),
    pytest.param("بین دو تا چهار طبقه", "range", id="persian-range"),
    pytest.param("حداکثر چهار طبقه", "maximum", id="persian-maximum"),
    pytest.param("حداقل دو طبقه", "minimum", id="persian-minimum"),
    pytest.param("at least 2 storeys", "minimum", id="english-at-least"),
    pytest.param("up to four storeys", "maximum", id="english-up-to"),
    pytest.param("2 to 4 storeys", "range", id="digit-to-range"),
    pytest.param(
        "two or four-storey house",
        "alternative",
        id="word-or",
    ),
    pytest.param(
        "a two- or three-storey building",
        "alternative",
        id="word-elided-or",
    ),
    pytest.param("2/4 storey building", "alternative", id="slash"),
    pytest.param(
        "between 2 and 4 storeys",
        "range",
        id="english-between",
    ),
    pytest.param(
        "between two and four storeys",
        "range",
        id="english-between-words",
    ),
    pytest.param("دو یا چهار طبقه", "alternative", id="persian-alternative"),
    pytest.param("بین دو و چهار طبقه", "range", id="persian-between-and"),
    pytest.param("maximum four storeys", "maximum", id="english-maximum"),
    pytest.param("minimum two storeys", "minimum", id="english-minimum"),
]


EXACT_CASES = [
    pytest.param("Two-storey villa", 2, id="english-word-hyphen"),
    pytest.param("Four-storey residence", 4, id="english-word-four"),
    pytest.param("2-storey building", 2, id="english-digit"),
    pytest.param("ساختمان سه طبقه", 3, id="persian-word"),
    pytest.param(
        "Three floors in total: ground plus two floors above it",
        3,
        id="total-with-level-component",
    ),
    pytest.param(
        "Two-storey villa with brick or stone facade",
        2,
        id="unrelated-or",
    ),
    pytest.param(
        "Four-storey residence on a 10-meter-wide site",
        4,
        id="unrelated-number-and-hyphens",
    ),
    pytest.param(
        "ساختمان سه طبقه با نمای آجری یا سنگی",
        3,
        id="unrelated-persian-or",
    ),
]


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


def _published_instruction(text):
    instruction = _instruction(text)
    provenance = (
        (instruction.get("constraints") or {}).get("floor_count_provenance")
        or {}
    )
    return {
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


def _pipeline(text):
    intent = _intent(text)
    instruction = _instruction(text)
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
    return intent, instruction, handoff, final_prompt, workflow["1"]["inputs"]["text"]


def _numeric_floor_values(text):
    return {
        int(value)
        for value in re.findall(
            r"(?:exactly\s+)?(\d+)\s+(?:story building|floors?)",
            text,
            flags=re.IGNORECASE,
        )
    }


@pytest.mark.parametrize("text,category", AMBIGUOUS_CASES)
def test_ranges_alternatives_and_limits_fail_closed_through_pipeline(
    text,
    category,
):
    intent, instruction, handoff, final_prompt, positive_prompt = _pipeline(text)
    constraints = instruction.get("constraints") or {}

    assert category in {"range", "alternative", "maximum", "minimum"}
    assert _floor_count(text) is None
    assert "floors" not in intent
    assert (intent.get("floor_count") or {}).get("value") is None
    assert (intent.get("floor_count") or {}).get("source") == "unspecified"
    assert constraints.get("floor_count") is None
    assert constraints.get("floor_count_provenance") is None
    assert handoff.get("floor_count") is None
    assert not re.search(r"exactly\s+\d+\s+floors?", handoff["constraint_block"], re.I)
    assert not re.search(r"exactly\s+\d+\s+floors?", final_prompt, re.I)
    assert not re.search(r"exactly\s+\d+\s+floors?", positive_prompt, re.I)
    assert _numeric_floor_values(positive_prompt) == set()


@pytest.mark.parametrize("text,expected", EXACT_CASES)
def test_valid_exact_totals_retain_value_provenance_and_final_prompt(
    text,
    expected,
):
    intent, instruction, handoff, final_prompt, positive_prompt = _pipeline(text)
    parsed = _floor_count(text)
    contract = intent.get("floor_count") or {}
    constraints = instruction.get("constraints") or {}
    rendered = constraints.get("floor_count") or {}
    provenance = constraints.get("floor_count_provenance") or {}

    assert parsed and parsed.get("value") == expected
    assert intent.get("floors") == expected
    assert contract.get("contract") == "FloorCountV1"
    assert contract.get("value") == expected
    assert contract.get("source") == "user_explicit"
    assert rendered.get("value") == expected
    assert provenance.get("value") == expected
    assert provenance.get("source") == "USER_TEXT"
    assert provenance.get("hard_constraint") is True
    assert handoff.get("floor_count") == expected
    assert "exactly %d floors" % expected in handoff["constraint_block"]
    assert "exactly %d floors" % expected in final_prompt
    assert "exactly %d floors" % expected in positive_prompt
    assert _numeric_floor_values(positive_prompt) == {expected}


@pytest.mark.parametrize(
    "text",
    [
        "Put arched windows on the second floor of the existing building",
        "A ground floor plus two floors above it",
    ],
    ids=["particular-floor", "level-breakdown-component-only"],
)
def test_non_total_floor_mentions_remain_unknown(text):
    intent, instruction, handoff, final_prompt, positive_prompt = _pipeline(text)

    assert _floor_count(text) is None
    assert "floors" not in intent
    assert (intent.get("floor_count") or {}).get("value") is None
    assert (instruction.get("constraints") or {}).get("floor_count") is None
    assert handoff.get("floor_count") is None
    assert _numeric_floor_values(final_prompt) == set()
    assert _numeric_floor_values(positive_prompt) == set()
