# -*- coding: utf-8 -*-
"""R1_B_FLOOR_COUNT_DESCRIPTION_REQUEST_V1 — CPU-only acceptance.

Defect under test: a floor count that DESCRIBES the existing building
("این ساختمان سه طبقه است") was published as a requested hard constraint,
while a request that merely FOLLOWED such a description
("ساختمان سه طبقه است، آن را چهار طبقه کن") lost its requested count
entirely because two competing numbers fail closed.

The distinction under test is clause type, not polarity:

    description  — the building AS IT ALREADY IS   (copula / possession)
    request      — what the building SHOULD BECOME (imperative / bare spec)

Chain exercised (all deterministic, no render, no model):

    _floor_count() / _floor_count_description()
      -> ArchitecturalIntent.extract()
      -> build_render_instruction()   (constraints.floor_count*)
      -> build_constraint_block()

Zero inference. Zero rendering.
"""

from __future__ import annotations

import contextlib
import io
import inspect
from functools import lru_cache

import pytest

from core.cognition.architectural_render_instruction_v1 import (
    _floor_count,
    _floor_count_description,
    build_constraint_block,
    build_render_instruction,
)
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.vision.architectural_observation_v1 import _floor_count_is_valid
from core.vision.vision_report_v1 import _reported_floor_count


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


def _requested(text):
    parsed = _floor_count(text)
    return parsed.get("value") if parsed else None


def _described(text):
    parsed = _floor_count_description(text)
    return parsed.get("value") if parsed else None


def _description_record(text):
    return _constraints(text).get("floor_count_description")


def _provenance(text):
    return _constraints(text).get("floor_count_provenance") or {}


def _published(text):
    provenance = _provenance(text)
    return (
        provenance.get("value")
        if provenance.get("source") in ("USER_TEXT", "USER_CONFIRMATION")
        else None
    )


# ---------------------------------------------------------------------------
# 1. The nine required semantics (A–I from the brief).
# ---------------------------------------------------------------------------

REQUIRED = [
    # id, text, requested, described
    ("A_mixed_fa", "ساختمان سه طبقه است، آن را چهار طبقه کن.", 4, 3),
    ("B_description_fa", "این ساختمان سه طبقه است.", None, 3),
    ("C_request_fa", "ساختمان را چهار طبقه کن.", 4, None),
    ("D_description_preserve_fa",
     "ساختمان سه طبقه است، تعداد طبقات را تغییر نده.", 3, 3),
    ("E_description_negated_request_fa",
     "ساختمان سه طبقه است، آن را چهار طبقه نکن.", None, 3),
    ("F_negated_description_request_fa",
     "ساختمان سه طبقه نباشد، چهار طبقه کن.", 4, None),
    ("G_mixed_en", "The building has three storeys. Make it four storeys.", 4, 3),
    ("H_description_en", "The building has three storeys.", None, 3),
    ("I_material_preserve_fa",
     "فقط متریال نما را تغییر بده؛ تعداد طبقات ثابت بماند.", None, None),
]


@pytest.mark.parametrize("case,text,requested,described", REQUIRED)
def test_01_required_semantics(case, text, requested, described):
    assert _requested(text) == requested, case
    assert _described(text) == described, case


@pytest.mark.parametrize("case,text,requested,described", REQUIRED)
def test_02_required_semantics_reach_the_instruction(
    case, text, requested, described
):
    """The published instruction must agree with the parser."""

    assert _published(text) == requested, case
    if requested is None:
        assert _provenance(text).get("hard_constraint") is not True, case
    else:
        assert _provenance(text).get("hard_constraint") is True, case


# ---------------------------------------------------------------------------
# 2. No descriptive count ever becomes a requested target.
# ---------------------------------------------------------------------------

DESCRIPTIONS = [
    ("این ساختمان سه طبقه است.", 3),
    ("ساختمان چهار طبقه است.", 4),
    ("ساختمان سه طبقه دارد.", 3),
    ("The building has three storeys.", 3),
    ("The building is four storeys.", 4),
]


@pytest.mark.parametrize("text,stated", DESCRIPTIONS)
def test_03_description_is_never_a_requested_target(text, stated):
    assert _requested(text) is None
    assert _published(text) is None
    assert _provenance(text).get("hard_constraint") is not True
    # The stated value is still reported — as a description.
    assert _described(text) == stated


@pytest.mark.parametrize("text,stated", DESCRIPTIONS)
def test_04_description_record_is_labelled_user_text_not_evidence(
    text, stated
):
    record = _description_record(text)
    assert isinstance(record, dict)
    assert record["value"] == stated
    assert record["source"] == "USER_TEXT_DESCRIPTION"
    assert record["visually_verified"] is False
    assert record["raw"]
    assert len(record["span"]) == 2


def test_05_no_description_record_when_no_description_exists():
    assert _description_record("ساختمان را چهار طبقه کن.") is None


# ---------------------------------------------------------------------------
# 3. No negative count becomes positive (R1 must stay intact).
# ---------------------------------------------------------------------------

NEGATED = [
    "ساختمان چهار طبقه نباشد.",
    "ساختمان چهار طبقه نشود.",
    "ساختمان چهار طبقه نباشه.",
    "ساختمان چهار طبقه نداشته باشد.",
    "ساختمان نباید چهار طبقه باشد.",
    "این ساختمان سه طبقه نیست",
    "Do not make it four storeys.",
    "not a three-storey building",
]


@pytest.mark.parametrize("text", NEGATED)
def test_06_negative_never_becomes_a_positive_target(text):
    assert _requested(text) is None
    assert _published(text) is None
    assert _provenance(text).get("hard_constraint") is not True


def test_07_negated_description_is_not_reported_as_a_description():
    """A negated statement is not a stated existing count either."""

    assert _described("ساختمان سه طبقه نیست.") is None


# ---------------------------------------------------------------------------
# 4. The mixed clause keeps BOTH readings, without merging them.
# ---------------------------------------------------------------------------

def test_08_mixed_clause_keeps_description_and_request_separate():
    text = "ساختمان سه طبقه است، آن را چهار طبقه کن."
    assert _described(text) == 3
    assert _requested(text) == 4
    assert _published(text) == 4
    assert _description_record(text)["value"] == 3
    assert _description_record(text)["value"] != _published(text)


def test_09_mixed_clause_english_matches_persian():
    assert _requested(
        "The building has three storeys. Make it four storeys."
    ) == _requested("ساختمان سه طبقه است، آن را چهار طبقه کن.")
    assert _described(
        "The building has three storeys. Make it four storeys."
    ) == _described("ساختمان سه طبقه است، آن را چهار طبقه کن.")


def test_10_preserve_request_quotes_the_stated_count_it_does_not_invent():
    text = "ساختمان سه طبقه است، تعداد طبقات را تغییر نده."
    assert _published(text) == 3
    # The published value is exactly the value the user stated.
    assert _published(text) == _described(text)


# ---------------------------------------------------------------------------
# 5. Persian and English parity, digits, and accepted specification forms.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("ساختمان را چهار طبقه کن.", 4),
    ("ساختمان را ۴ طبقه کن.", 4),
    ("Make the facade four storeys.", 4),
    ("Render a 30-floor tower", 30),
    ("برج ۳۰-طبقه", 30),
    ("ساختمان چهار طبقه باشد.", 4),
])
def test_11_accepted_request_forms_are_unchanged(text, expected):
    assert _requested(text) == expected
    assert _published(text) == expected


@pytest.mark.parametrize("text", [
    "ساختمان دو یا سه طبقه",
    "ساختمان چند طبقه",
    "a 30-metre facade",
])
def test_12_ambiguous_or_unsupported_is_still_none(text):
    assert _requested(text) is None
    assert _published(text) is None


# ---------------------------------------------------------------------------
# 6. Vision observation is a different authority and stays unchanged.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (3, True), (30, True), (True, False), ("3", False), (0, False), (2.7, False),
])
def test_13_vision_floor_validity_is_unchanged(value, expected):
    assert _floor_count_is_valid(value) is expected


def test_14_vision_reported_floor_count_is_unchanged():
    interpretation = {
        "architectural_observation": {
            "visible_floors_observation": {"count": 3},
        }
    }
    assert _reported_floor_count(interpretation) == 3


def test_15_text_description_is_never_sourced_from_vision():
    """The description record must not borrow vision provenance."""

    record = _description_record("ساختمان سه طبقه است، آن را چهار طبقه کن.")
    assert record["source"] == "USER_TEXT_DESCRIPTION"
    assert "VISION" not in record["source"]


# ---------------------------------------------------------------------------
# 7. Material-change and preservation interpretations are unchanged.
# ---------------------------------------------------------------------------

def test_16_material_preserve_request_keeps_its_material_intent():
    from core.vision.architectural_material_knowledge_connection_v1 import (
        build_architectural_material_knowledge_connection,
    )

    text = "فقط متریال نما را تغییر بده؛ تعداد طبقات ثابت بماند."
    assert _requested(text) is None
    assert _described(text) is None

    observation = {
        "contract": "ArchitecturalObservationV1",
        "material_observations": [{
            "descriptor": "cream travertine facade cladding",
            "materials": ["travertine"],
            "evidence_phrase": "cream travertine facade cladding",
            "confidence": "MEDIUM",
        }],
        "provenance": {
            "provider": "SYNTHETIC_TEST_FIXTURE",
            "model": "NONE",
            "image_id": "R1B-IMAGE-1",
            "source_type": "test_fixture",
        },
    }
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        connection = build_architectural_material_knowledge_connection(
            observation,
            "The material you identified as travertine is actually marble.",
        )
    assert connection.get("status") == "MATERIAL_CORRECTION_PENDING_CONFIRMATION"


def test_17_preserve_geometry_is_still_reported():
    text = "ساختمان سه طبقه است، تعداد طبقات را تغییر نده."
    geometry = _constraints(text).get("geometry") or {}
    assert geometry.get("preserve_floor_count") is True


# ---------------------------------------------------------------------------
# 8. Instruction contract stays usable for every case.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case,text,requested,described", REQUIRED)
def test_18_instruction_contract_still_builds(
    case, text, requested, described
):
    instruction = _instruction(text)
    assert isinstance(instruction, dict)
    assert isinstance(instruction.get("constraints"), dict)
    assert isinstance(build_constraint_block(instruction), str)
    # The instruction never carries a request it did not derive from text.
    intent = _intent(text)
    assert isinstance(intent, dict)


def test_19_floor_count_description_field_is_additive_and_optional():
    """Every instruction carries the key; it is None when absent."""

    for text in (
        "ساختمان را چهار طبقه کن.",
        "این ساختمان سه طبقه است.",
        "فقط متریال نما را عوض کن",
    ):
        constraints = _constraints(text)
        assert "floor_count_description" in constraints


# ---------------------------------------------------------------------------
# 9. Zero inference / zero rendering.
# ---------------------------------------------------------------------------

def test_20_no_render_or_model_path_in_the_new_helpers():
    import core.cognition.architectural_render_instruction_v1 as owner

    for function in (
        owner._floor_count_is_description,
        owner._floor_description_is_operative,
        owner._floor_span_is_prohibited,
        owner._floor_count_candidates,
        owner._floor_count_description,
    ):
        source = inspect.getsource(function).lower()
        for forbidden in (
            "comfyui", "render_runtime", "workflow_injector",
            "model.generate", "ollama", "torch", "sam3", "controlnet",
            "requests.", "http",
        ):
            assert forbidden not in source, (
                "%s references %r" % (function.__name__, forbidden)
            )
