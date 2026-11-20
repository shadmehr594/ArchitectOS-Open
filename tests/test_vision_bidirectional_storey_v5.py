"""BIDIRECTIONAL_STOREY_ROOF_VISION_V5 focused CPU regressions.

Root cause under test
=====================

V4.1 established that the same provider made two OPPOSITE storey errors:

* Kontext D  — OVER-counted (reported 3, true 2): a single lit window inside a
  roof gable was promoted to a principal storey.
* A_STYLE    — UNDER-counted (reported 2, true 3): two genuine window rows at
  different heights, divided by a FLUSH stone sill, were merged into one storey.

The instruction block in `_SCHEMA_SPEC` was one-directionally conservative:

    "Count PRINCIPAL STOREYS, not rows of openings."

That clause suppresses the over-count and *causes* the under-count, because a
principal storey is in fact evidenced by a row of openings. The block also
never defined what makes a storey division legible, so the model required a
projecting balcony/cornice and merged rows separated by a flush sill.

These tests pin the BIDIRECTIONAL contract that replaces it. They are CPU-only:
no Ollama call, no ComfyUI, no image generation, no GPU.
"""

import re

import pytest

from core.vision import design_constraint_fidelity_v1 as fidelity
from core.vision.facade_reference_vision_provider_v1 import (
    ROLE_STYLE_REFERENCE,
    ROLE_TARGET_BUILDING,
    _ROLE_PROMPTS,
    map_to_contract,
)


def _prompt(role=ROLE_TARGET_BUILDING):
    """The composed prompt the model actually receives, whitespace-normalised."""
    return " ".join(_ROLE_PROMPTS[role].lower().split())


# ==========================================================
# RED — the one-directional clause must be gone
# ==========================================================

def test_prompt_no_longer_forbids_counting_rows_of_openings():
    """The clause that caused the A_STYLE under-count must not survive.

    'not rows of openings' contradicts the evidence model of a storey and was
    read as 'merge adjacent window rows'. Counting rows IS how storeys are
    counted; the guidance must be about WHICH rows, not about rows in general.
    """

    prompt = _prompt()

    assert "not rows of openings" not in prompt


def test_prompt_defines_a_storey_by_a_repeating_row_with_head_and_sill():
    """A storey needs a positive, pixel-grounded definition."""

    prompt = _prompt()

    assert "repeats across more than one bay" in prompt
    assert "head" in prompt and "sill" in prompt


# ==========================================================
# RED — the INCLUSION direction (fixes A_STYLE under-count)
# ==========================================================

def test_prompt_states_a_flush_sill_is_a_legible_storey_division():
    """A division does not require a projecting band.

    A_STYLE's two upper rows are divided by a flush stone ledge carrying the
    flower boxes. The previous prompt never defined 'legible division', so the
    model demanded a projecting band and merged the rows.
    """

    prompt = _prompt()

    assert "does not have to be a projecting" in prompt
    assert "flush sill" in prompt or "flush ledge" in prompt


def test_prompt_counts_separate_rows_at_different_heights_as_separate_storeys():
    """The positive instruction the previous prompt was missing entirely."""

    prompt = _prompt()

    assert "different heights" in prompt
    assert "its own storey" in prompt or "separate storey" in prompt


def test_prompt_resolves_the_continuous_double_height_central_bay():
    """A_STYLE's central bay runs one glazed opening across both rows.

    That continuity is what makes the two rows look like one tall storey. The
    instruction must say the side bays still establish two storeys.
    """

    prompt = _prompt()

    assert "double-height" in prompt
    assert "side bays" in prompt


# ==========================================================
# RED — the EXCLUSION direction must become structural (fixes D over-count)
# ==========================================================

def test_prompt_excludes_only_openings_that_do_not_repeat_inside_the_roof_volume():
    """D's gable window is excluded because of two structural properties,
    not because it is called 'attic'. The rule must stay conditional."""

    prompt = _prompt()

    assert "does not repeat across the facade" in prompt
    assert "roof volume" in prompt


def test_prompt_keeps_a_single_roof_window_out_of_the_storey_count():
    prompt = _prompt()

    assert "single lit attic window is not a storey" in prompt


# ==========================================================
# GUARD — no hardcoded answers, no control identities
# ==========================================================

def test_prompt_hardcodes_no_count_and_no_control_identity():
    """The correction must generalise: no expected number, no image identity."""

    for role in (ROLE_TARGET_BUILDING, ROLE_STYLE_REFERENCE):

        prompt = _prompt(role)

        for forbidden in (
            "a_style",
            "kontext",
            "architectos_kontext",
            "three storey",
            "three-storey",
            "3 storey",
            "3-storey",
            "two storey",
            "two-storey",
            "2 storey",
            "2-storey",
        ):
            assert forbidden not in prompt, (role, forbidden)

        # No bare expected counts smuggled into the storey guidance.
        assert not re.search(r"expected\s+(count|floors?)\s*[:=]", prompt)


def test_prompt_still_declares_the_v4_per_level_vocabulary():
    """The V5 change must not remove the V4 contract vocabulary."""

    prompt = _prompt()

    for required in (
        "per_level_evidence",
        "principal_storey",
        "roof_opening",
        "attic_or_roof_storey",
        "mezzanine",
        "ambiguous",
        "contributes_to_floor_count",
    ):
        assert required in prompt


# ==========================================================
# GUARD — V4 safety behaviour must be preserved
# ==========================================================

def _level(position, category, contributes, evidence, confidence=0.95):
    return {
        "level_position": position,
        "category": category,
        "evidence": evidence,
        "confidence": confidence,
        "contributes_to_floor_count": contributes,
    }


def _contract(count, levels, *, count_type="TOTAL", legible=True):
    return map_to_contract(
        {
            "building_type": "villa",
            "visible_floor_count": count,
            "floor_observation": {
                "count": count,
                "count_type": count_type,
                "storey_divisions_legible": legible,
                "evidence": "level-by-level facade reading",
                "per_level_evidence": levels,
            },
        }
    )


def test_mapper_still_accepts_two_principal_storeys_plus_roof_opening():
    """The D shape: two principal storeys and a gable opening."""

    mapped = _contract(
        2,
        [
            _level("ground", "principal_storey", True, "row across the facade"),
            _level("upper", "principal_storey", True, "second row across the facade"),
            _level("gable", "roof_opening", False, "single window inside gable", 0.9),
        ],
    )

    assert mapped["visible_floor_count"] == 2
    assert mapped["floor_observation"]["count"] == 2


def test_mapper_still_accepts_three_principal_storeys_with_flush_divisions():
    """The A_STYLE shape: three principal storeys, no projecting band."""

    mapped = _contract(
        3,
        [
            _level("ground", "principal_storey", True, "entrance row, flush division"),
            _level("middle", "principal_storey", True, "rectangular row, flush sill"),
            _level("upper", "principal_storey", True, "arched row, flush sill"),
        ],
    )

    assert mapped["visible_floor_count"] == 3
    assert mapped["floor_observation"]["count"] == 3


def test_fidelity_still_refuses_a_total_that_contradicts_its_own_levels():
    """V4's containment must not regress: a confident wrong TOTAL stays UNVERIFIED."""

    mapped = _contract(
        3,
        [
            _level("ground", "principal_storey", True, "row"),
            _level("upper", "principal_storey", True, "row"),
        ],
    )

    evaluation = fidelity.evaluate({"building_type": "villa", "floors": 2}, "", mapped)

    assert evaluation["floor_status"] != "FLOOR_COUNT_VERIFIED"
    assert evaluation["design_accepted"] is False


def test_fidelity_still_never_accepts_an_ambiguous_level_as_total():
    mapped = _contract(
        3,
        [
            _level("ground", "principal_storey", True, "row"),
            _level("upper", "principal_storey", True, "row"),
            _level("top", "ambiguous", False, "cannot resolve band", 0.5),
        ],
    )

    evaluation = fidelity.evaluate({"building_type": "villa", "floors": 2}, "", mapped)

    assert evaluation["floor_status"] != "FLOOR_COUNT_VERIFIED"
    assert evaluation["design_accepted"] is False
