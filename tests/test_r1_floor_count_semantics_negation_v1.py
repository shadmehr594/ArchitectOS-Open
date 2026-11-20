# -*- coding: utf-8 -*-
"""R1_FLOOR_COUNT_SEMANTICS_NEGATION_V1 — CPU-only acceptance.

Defect under test: a Persian prohibitive floor-count statement
("ساختمان چهار طبقه نباشد" = "the building should not be four storeys")
was published as an EXACT POSITIVE floor-count hard constraint, inverting
the user's instruction.

Every test exercises the REAL deterministic chain:

    is_affirmed() / _floor_count()            (shared negation + grammar owner)
      -> ArchitecturalIntent.extract()        (canonical floors + FloorCountV1)
      -> build_render_instruction()           (structured render instruction)
      -> build_constraint_block()             (RenderConstraintBlockV1)

No LLM, Ollama, ComfyUI, GPU, renderer, workflow submission or network call.
"""

from __future__ import annotations

import contextlib
import io
import inspect
from functools import lru_cache

import pytest

from core.cognition.architectural_render_instruction_v1 import (
    _floor_count,
    build_constraint_block,
    build_render_instruction,
)
from core.chat.negation_scope_v1 import (
    NEGATED_AFTER,
    NEGATION_TOKENS,
    _AFTER_WINDOW,
    is_affirmed,
)
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.vision.architectural_observation_v1 import _floor_count_is_valid
from core.vision.vision_report_v1 import _reported_floor_count


# ---------------------------------------------------------------------------
# Chain helpers
# ---------------------------------------------------------------------------

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
    """The floor count the constraint block may publish as authoritative."""

    block = build_constraint_block(_instruction(text))
    provenance = _provenance(text)
    return {
        "constraint_block_is_dict": isinstance(block, dict),
        "floor_count": (
            provenance.get("value")
            if provenance.get("source") in ("USER_TEXT", "USER_CONFIRMATION")
            else None
        ),
        "hard_constraint": provenance.get("hard_constraint"),
        "source": provenance.get("source"),
    }


# ---------------------------------------------------------------------------
# 1. Affirmative floor-count request — must still be published exactly.
# ---------------------------------------------------------------------------

AFFIRMATIVE = [
    ("ساختمان را چهار طبقه کن.", 4),          # Persian imperative
    ("ساختمان را ۴ طبقه کن.", 4),              # Persian digits
    ("ساختمان چهار طبقه باشد.", 4),            # positive subjunctive
    ("Make the facade four storeys.", 4),      # English
    ("Render a 30-floor tower", 30),           # English hyphenated
]

# R1_B_FLOOR_COUNT_DESCRIPTION_REQUEST_V1 — SUPERSEDED ASSERTION.
#
# `("ساختمان چهار طبقه است.", 4)` used to live in AFFIRMATIVE above. R1-B
# established that a copula statement describes the building AS IT ALREADY IS
# and is not a request ("این ساختمان سه طبقه است." -> no requested target).
# "ساختمان چهار طبقه است." is structurally identical, so it now correctly
# yields no requested target. The polarity is still affirmative (see
# test_04b); only its status as a REQUEST changed.
DESCRIBED_NOT_REQUESTED = [
    ("ساختمان چهار طبقه است.", 4),
    ("این ساختمان سه طبقه است.", 3),
    ("The building has three storeys.", 3),
]


@pytest.mark.parametrize("text,expected", AFFIRMATIVE)
def test_01_affirmative_request_is_published_exactly(text, expected):
    parsed = _floor_count(text)
    assert parsed is not None, "affirmative count was lost: %r" % text
    assert parsed["value"] == expected
    assert _intent(text).get("floors") == expected
    assert _instruction_floor(text) == expected
    published = _published(text)
    assert published["floor_count"] == expected
    assert published["hard_constraint"] is True
    assert published["source"] == "USER_TEXT"


@pytest.mark.parametrize("text,described", DESCRIBED_NOT_REQUESTED)
def test_01b_copula_description_is_not_a_requested_target(text, described):
    """R1_B — a description states the existing building, not a request."""

    from core.cognition.architectural_render_instruction_v1 import (
        _floor_count_description,
    )

    assert _floor_count(text) is None
    assert _instruction_floor(text) is None
    assert _published(text)["floor_count"] is None
    # ...and the stated value is still reported, as a DESCRIPTION.
    assert (_floor_count_description(text) or {}).get("value") == described


# ---------------------------------------------------------------------------
# 2. Negated floor-count request — THE DEFECT. Never a positive target.
# ---------------------------------------------------------------------------

NEGATED = [
    # Persian prohibitive forms that were MISSING before this milestone
    ("ساختمان چهار طبقه نباشد.", "نباشد"),
    ("ساختمان‌ها چهار طبقه نباشند.", "نباشند"),
    ("ساختمان چهار طبقه نباشه.", "نباشه"),
    ("ساختمان چهار طبقه نشود.", "نشود"),
    ("ساختمان چهار طبقه نشه.", "نشه"),
    ("ساختمان چهار طبقه نمی‌شود.", "نمی‌شود"),
    ("ساختمان چهار طبقه نخواهد بود.", "نخواهد بود"),
    ("ساختمان چهار طبقه نداشته باشد.", "نداشته باشد"),
    ("ساختمان چهار طبقه نداشته باشه.", "نداشته باشه"),
    ("ساختمان چهار طبقه نداشته باشید.", "نداشته باشید"),
    ("ساختمان نباید چهار طبقه باشد.", "نباید"),
    # Persian forms that already worked — regression guard
    ("این ساختمان سه طبقه نیست", "نیست"),
    ("ساختمان چهار طبقه نبود.", "نبود"),
    ("بدون چهار طبقه", "بدون"),
    # English
    ("Do not make it four storeys.", "not"),
    ("not a three-storey building", "not"),
]


@pytest.mark.parametrize("text,marker", NEGATED)
def test_02_negated_count_is_never_a_positive_target(text, marker):
    assert _floor_count(text) is None, (
        "%r (marker %s) was published as a floor count" % (text, marker)
    )
    assert _intent(text).get("floors") is None
    assert _instruction_floor(text) is None
    published = _published(text)
    assert published["floor_count"] is None
    assert published["hard_constraint"] is not True
    assert published["source"] not in ("USER_TEXT", "USER_CONFIRMATION")


@pytest.mark.parametrize("text,marker", NEGATED)
def test_03_negated_count_creates_no_hard_constraint(text, marker):
    provenance = _provenance(text)
    assert provenance.get("value") is None
    assert provenance.get("hard_constraint") is not True


# The floor span each prohibition must de-affirm. The shared negation owner
# decides polarity for the SPAN, not for the bare marker.
NEGATED_SPANS = [
    ("ساختمان چهار طبقه نباشد.", "چهار طبقه"),
    ("ساختمان‌ها چهار طبقه نباشند.", "چهار طبقه"),
    ("ساختمان چهار طبقه نباشه.", "چهار طبقه"),
    ("ساختمان چهار طبقه نشود.", "چهار طبقه"),
    ("ساختمان چهار طبقه نشه.", "چهار طبقه"),
    ("ساختمان چهار طبقه نمی‌شود.", "چهار طبقه"),
    ("ساختمان چهار طبقه نخواهد بود.", "چهار طبقه"),
    ("ساختمان چهار طبقه نداشته باشد.", "چهار طبقه"),
    ("ساختمان چهار طبقه نداشته باشه.", "چهار طبقه"),
    ("ساختمان چهار طبقه نداشته باشید.", "چهار طبقه"),
    ("ساختمان نباید چهار طبقه باشد.", "چهار طبقه"),
    ("این ساختمان سه طبقه نیست", "سه طبقه"),
    ("ساختمان چهار طبقه نبود.", "چهار طبقه"),
    ("بدون چهار طبقه", "چهار طبقه"),
    ("Do not make it four storeys.", "four storeys"),
    ("not a three-storey building", "three-storey"),
]


@pytest.mark.parametrize("text,span", NEGATED_SPANS)
def test_04_is_affirmed_recognises_the_prohibition(text, span):
    """The shared negation owner is what must reject these floor spans."""

    assert is_affirmed(text, span) is False


@pytest.mark.parametrize("text,span", [
    ("ساختمان را چهار طبقه کن.", "چهار طبقه"),
    ("ساختمان چهار طبقه باشد.", "چهار طبقه"),
    ("ساختمان چهار طبقه است.", "چهار طبقه"),
    ("Make the facade four storeys.", "four storeys"),
])
def test_04b_affirmative_floor_spans_stay_affirmed(text, span):
    """The same owner must NOT over-negate a genuine requirement."""

    assert is_affirmed(text, span) is True


# ---------------------------------------------------------------------------
# 3. Preservation — never invent a numerical value.
# ---------------------------------------------------------------------------

PRESERVATION = [
    "تعداد طبقات را تغییر نده.",
    "فقط متریال نما را عوض کن؛ تعداد طبقات ثابت بماند.",
    "Preserve the existing floor count.",
    "Keep the same number of floors.",
]


@pytest.mark.parametrize("text", PRESERVATION)
def test_05_preservation_invents_no_floor_count(text):
    assert _floor_count(text) is None
    assert _intent(text).get("floors") is None
    assert _instruction_floor(text) is None
    assert _published(text)["floor_count"] is None


def test_06_material_preservation_request_keeps_its_material_intent():
    """Preserving floors must not swallow the facade-material instruction."""

    text = "فقط متریال نما را عوض کن؛ تعداد طبقات ثابت بماند."
    assert _floor_count(text) is None

    from core.vision.architectural_material_knowledge_connection_v1 import (
        build_architectural_material_knowledge_connection,
    )

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
            "image_id": "R1-IMAGE-1",
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
    assert connection.get("material_correction", {}).get("status") == (
        "PENDING_CONFIRMATION"
    )


# ---------------------------------------------------------------------------
# 4. Existing observed count versus requested count stay separate.
# ---------------------------------------------------------------------------

def test_07_observed_and_requested_counts_are_different_fields():
    """Vision observation and the user's request are never the same value."""

    interpretation = {
        "architectural_observation": {
            "visible_floors_observation": {"count": 3},
        }
    }
    observed = _reported_floor_count(interpretation)
    requested = (_floor_count("ساختمان را چهار طبقه کن.") or {}).get("value")

    assert observed == 3
    assert requested == 4
    # The two live in different contracts and must not be conflated.
    assert _reported_floor_count(interpretation) == 3


def test_08_stated_current_count_is_not_published_as_the_request():
    """'it is 3 storeys, make it 4' must never publish 3 as the request.

    The parser fails closed on two distinct values in one sentence. The
    SAFETY invariant asserted here is that the observed statement (3) is
    never promoted into the user's requested design.
    """

    text = "ساختمان سه طبقه است، آن را چهار طبقه کن."
    published = _published(text)
    assert published["floor_count"] in (None, 4)
    assert published["floor_count"] != 3


# ---------------------------------------------------------------------------
# 5. Unsupported / ambiguous instructions fail closed.
# ---------------------------------------------------------------------------

AMBIGUOUS = [
    "ساختمان دو یا سه طبقه",
    "ساختمان چند طبقه",
    "چند طبقه است؟",
    "a 30-metre facade",
    "the third-floor balcony",
]


@pytest.mark.parametrize("text", AMBIGUOUS)
def test_09_ambiguous_or_unsupported_is_not_a_floor_count(text):
    assert _floor_count(text) is None
    assert _instruction_floor(text) is None
    assert _published(text)["floor_count"] is None


# ---------------------------------------------------------------------------
# 6. No accidental material-change intent from a floor-only request.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "ساختمان را چهار طبقه کن.",
    "ساختمان چهار طبقه نباشد.",
    "Make the facade four storeys.",
])
def test_10_floor_request_creates_no_material_correction(text):
    from core.vision.architectural_material_knowledge_connection_v1 import (
        build_architectural_material_knowledge_connection,
    )

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
            "image_id": "R1-IMAGE-2",
            "source_type": "test_fixture",
        },
    }
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        connection = build_architectural_material_knowledge_connection(
            observation, text
        )
    assert connection.get("status") != "MATERIAL_CORRECTION_PENDING_CONFIRMATION"
    assert "material_correction" not in connection or (
        connection["material_correction"].get("status")
        != "PENDING_CONFIRMATION"
    )


# ---------------------------------------------------------------------------
# 7. No rendering / inference path is reachable from this change.
# ---------------------------------------------------------------------------

def test_11_negation_owner_has_no_render_or_model_path():
    import core.chat.negation_scope_v1 as owner

    source = inspect.getsource(owner).lower()
    for forbidden in (
        "comfyui", "render_runtime", "workflow_injector",
        "model.generate", "ollama", "torch", "sam3", "controlnet",
    ):
        assert forbidden not in source, (
            "forbidden dependency %r in negation owner" % forbidden
        )


def test_12_floor_count_is_a_pure_parser():
    import core.cognition.architectural_render_instruction_v1 as owner

    source = inspect.getsource(owner._floor_count).lower()
    for forbidden in (
        "comfyui", "render_runtime", "workflow_injector",
        "model.generate", "ollama", "torch", "sam3", "controlnet",
        "requests.", "http",
    ):
        assert forbidden not in source


# ---------------------------------------------------------------------------
# 8. Existing Vision floor-count observation behaviour is unchanged.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (3, True), (30, True), (1, True),
    (True, False), ("3", False), (0, False), (-1, False), (2.7, False),
    (None, False),
])
def test_13_vision_floor_count_validity_is_unchanged(value, expected):
    assert _floor_count_is_valid(value) is expected


@pytest.mark.parametrize("count,expected", [
    (3, 3), (5, 5), (None, None),
])
def test_14_vision_reported_floor_count_is_unchanged(count, expected):
    interpretation = {
        "architectural_observation": {
            "visible_floors_observation": {"count": count},
        }
    }
    assert _reported_floor_count(interpretation) == expected


def test_15_vision_report_without_observation_returns_none():
    assert _reported_floor_count({}) is None
    assert _reported_floor_count({"architectural_observation": {}}) is None


# ---------------------------------------------------------------------------
# 9. Existing chat / architectural-report contract stays intact.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "ساختمان را چهار طبقه کن.",
    "ساختمان چهار طبقه نباشد.",
    "Preserve the existing floor count.",
])
def test_16_render_instruction_contract_still_builds(text):
    instruction = _instruction(text)
    assert isinstance(instruction, dict)
    assert isinstance(instruction.get("constraints"), dict)
    # `build_constraint_block` returns the rendered constraint TEXT.
    block = build_constraint_block(instruction)
    assert isinstance(block, str)


def test_17_negated_request_still_yields_a_usable_instruction():
    """A prohibition must degrade to 'no floor constraint', not to a crash."""

    negated = _instruction("ساختمان چهار طبقه نباشد.")
    affirmative = _instruction("ساختمان را چهار طبقه کن.")

    assert isinstance(negated, dict) and isinstance(affirmative, dict)
    assert _instruction_floor("ساختمان چهار طبقه نباشد.") is None
    assert _instruction_floor("ساختمان را چهار طبقه کن.") == 4


# ---------------------------------------------------------------------------
# 10. Structural invariant guarding the ROOT CAUSE.
# ---------------------------------------------------------------------------

def test_18_after_window_covers_the_longest_negated_copula():
    """A window shorter than the longest entry silently disables it.

    This is the exact mechanism that let 'نخواهد بود' escape the gate.
    """

    longest = max(len(entry) for entry in NEGATED_AFTER)
    assert _AFTER_WINDOW >= longest + 1, (
        "after-window %d cannot contain the longest negated copula (%d)"
        % (_AFTER_WINDOW, longest)
    )


def test_19_prohibitive_forms_are_registered_in_the_shared_lexicon():
    for entry in (
        "\u0646\u0628\u0627\u0634\u062f",          # نباشد
        "\u0646\u0628\u0627\u0634\u0647",          # نباشه
        "\u0646\u0628\u0627\u0634\u0646\u062f",    # نباشند
        "\u0646\u0634\u0648\u062f",                # نشود
        "\u0646\u0634\u0647",                      # نشه
        "\u0646\u0645\u06cc\u200c\u0634\u0648\u062f",  # نمی‌شود
    ):
        assert entry in NEGATED_AFTER
    assert "\u0646\u0628\u0627\u06cc\u062f" in NEGATION_TOKENS  # نباید


def test_19b_the_two_negation_surfaces_agree():
    """ROOT CAUSE invariant: span detection and polarity must not diverge.

    `_COPULA_PROHIBITION_MARKERS` (the trailing-prohibition SPAN surface)
    already listed every Persian copula prohibition. `NEGATED_AFTER` (the
    polarity surface `is_affirmed()` uses) did not. A prohibition the span
    detector could see was invisible to the floor-count gate. Every copula
    marker must now be recognised by BOTH surfaces.
    """

    from core.chat.negation_scope_v1 import _COPULA_PROHIBITION_MARKERS

    missing = [
        marker for marker in _COPULA_PROHIBITION_MARKERS
        if marker not in NEGATED_AFTER
    ]
    assert missing == [], (
        "copula prohibition markers unknown to the polarity surface: %r"
        % missing
    )


def test_20_positive_subjunctive_is_not_confused_with_the_prohibition():
    """'باشد' (should be) must stay affirmative while 'نباشد' is negated."""

    assert _floor_count("ساختمان چهار طبقه باشد.")["value"] == 4
    assert _floor_count("ساختمان چهار طبقه نباشد.") is None
