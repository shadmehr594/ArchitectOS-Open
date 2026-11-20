# -*- coding: utf-8 -*-
"""T2I_ARCHITECTURAL_FIDELITY_REPORTING_V1 — CPU-only regression.

Six cases prove the render-result contract keeps TECHNICAL completion and
ARCHITECTURAL verification as separate facts, never fabricates an observed
count, and never turns an uncertain observation into a hard failure.

No vision inference, no GPU, no render: every observation here is a stubbed
contract supplied by the test.
"""

import pytest

from core.chat.handlers.image_handler import _architectural_fidelity_report
from core.vision import design_constraint_fidelity_v1 as fidelity


# ---------------------------------------------------------------- helpers

def _total_contract(count, *, legible=True, evidenced=False, building_type="tower"):
    """A stubbed facade observation declaring an exact TOTAL."""

    observation = {
        "count_type": "TOTAL",
        "count": count,
        "storey_divisions_legible": legible,
    }

    if evidenced:
        observation["per_level_evidence"] = [
            {
                "category": "principal_storey",
                "contributes_to_floor_count": True,
                "confidence": "high",
            }
            for _ in range(count)
        ]

    return {
        "visible_floor_count": count,
        "building_type": building_type,
        "floor_observation": observation,
    }


def _evaluate(intent, prompt, contract, requested_text):
    return fidelity.evaluate(intent, prompt, contract, requested_text=requested_text)


# ---------------------------------------------------------------- A

def test_a_requested_25_no_observation_is_not_verified():
    """No verified observation must never become a fabricated count."""

    evaluation = _evaluate(
        {"floors": 25},
        "The building has exactly 25 floors.",
        None,
        "a 25 storey tower",
    )

    report = _architectural_fidelity_report(evaluation, "success", True)

    assert report["technical_status"] == "success"
    assert report["image_preserved"] is True
    assert report["architectural_status"] == "NOT_VERIFIED"
    assert report["requested_floors"] == 25
    assert report["observed_floors"] is None
    assert report["observation_available"] is False
    assert report["confidence"] == "NONE"
    assert report["advisory"] is True
    # The instruction reached the sampler — that is reported as its own fact
    # and is explicitly NOT evidence of the result.
    assert report["instruction_carried_the_request"] is True
    assert report["instruction_is_not_evidence_of_result"] is True


# ---------------------------------------------------------------- B

def test_b_requested_25_observed_15_reports_mismatch_and_keeps_image():
    """A grounded count that disagrees is a MISMATCH, not a technical failure."""

    evaluation = _evaluate(
        {"floors": 25},
        "The building has exactly 25 floors.",
        _total_contract(15, evidenced=True),
        "a 25 storey tower",
    )

    assert evaluation["floor_status"] == fidelity.FLOOR_MISMATCH

    report = _architectural_fidelity_report(evaluation, "success", True)

    assert report["technical_status"] == "success"
    assert report["image_preserved"] is True
    assert report["architectural_status"] == "MISMATCH"
    assert report["requested_floors"] == 25
    assert report["observed_floors"] == 15
    assert report["observation_available"] is True
    assert report["confidence"] == "HIGH"
    assert report["provenance"]["floor_consistency"] == "CONSISTENT"
    assert report["advisory"] is True
    # A mismatch is reported, never acted on.
    assert "retry" not in str(report).lower()


# ---------------------------------------------------------------- C

def test_c_requested_3_observed_3_reports_match():
    """A grounded count that agrees is the only path to VERIFIED."""

    evaluation = _evaluate(
        {"floors": 3},
        "The building has exactly 3 floors.",
        _total_contract(3, evidenced=True),
        "a three storey house",
    )

    report = _architectural_fidelity_report(evaluation, "success", True)

    assert report["technical_status"] == "success"
    assert report["architectural_status"] == "VERIFIED"
    assert report["requested_floors"] == 3
    assert report["observed_floors"] == 3
    assert report["confidence"] == "HIGH"


# ---------------------------------------------------------------- D

def test_d_ambiguous_observation_never_passes():
    """An ambiguous count yields uncertainty, never an invented number."""

    contract = {
        "visible_floor_count": 15,
        "building_type": "tower",
        "floor_observation": {"count_type": "AMBIGUOUS", "count": 15},
    }

    evaluation = _evaluate(
        {"floors": 25}, "The building has exactly 25 floors.", contract,
        "a 25 storey tower",
    )

    report = _architectural_fidelity_report(evaluation, "success", True)

    assert report["architectural_status"] == "NOT_VERIFIED"
    assert report["observed_floors"] is None
    assert report["provenance"]["floor_count_type"] == "AMBIGUOUS"
    assert report["provenance"]["visible_floor_count_lower_bound"] == 15
    assert "ambiguous" in (report["floor_reason"] or "").lower()


def test_d2_contradictory_evidence_never_passes():
    """Self-contradicting level evidence is UNVERIFIED, not a count."""

    contract = {
        "visible_floor_count": 15,
        "building_type": "tower",
        "floor_observation": {
            "count_type": "TOTAL",
            "count": 15,
            "storey_divisions_legible": True,
            "per_level_evidence": [
                {
                    "category": "roof_opening",
                    "contributes_to_floor_count": True,
                    "confidence": "high",
                }
                for _ in range(15)
            ],
        },
    }

    evaluation = _evaluate(
        {"floors": 25}, "The building has exactly 25 floors.", contract,
        "a 25 storey tower",
    )

    report = _architectural_fidelity_report(evaluation, "success", True)

    assert report["architectural_status"] == "NOT_VERIFIED"
    assert report["observed_floors"] is None
    assert report["provenance"]["floor_consistency"] == "CONTRADICTORY"


def test_d3_partial_view_is_not_a_total():
    """A cropped building makes any count a lower bound, not a verdict."""

    contract = {
        "visible_floor_count": 15,
        "building_type": "tower",
        "floor_observation": {"count_type": "TOTAL", "count": 15},
        "occlusions": ["the roof is cropped by the frame"],
    }

    evaluation = _evaluate(
        {"floors": 25}, "The building has exactly 25 floors.", contract,
        "a 25 storey tower",
    )

    report = _architectural_fidelity_report(evaluation, "success", True)

    assert report["architectural_status"] == "NOT_VERIFIED"
    assert report["observed_floors"] is None
    assert report["provenance"]["view_partial"] is True


# ---------------------------------------------------------------- E

def test_e_no_requested_count_creates_no_requirement():
    """A request with no storey count must not acquire a floor verdict."""

    evaluation = _evaluate(
        {}, "Generate an architectural visualization.", None,
        "یک خانه مدرن طراحی کن",
    )

    report = _architectural_fidelity_report(evaluation, "success", True)

    assert report["architectural_status"] == "NOT_REQUESTED"
    assert report["requested_floors"] is None
    assert report["observed_floors"] is None
    assert report["technical_status"] == "success"


# ---------------------------------------------------------------- F

def test_f_technical_failure_stays_a_failure():
    """Fidelity metadata must never launder a failed render into a success."""

    report = _architectural_fidelity_report(None, "failed", False)

    assert report["technical_status"] == "failed"
    assert report["image_preserved"] is False
    assert report["architectural_status"] == "NOT_VERIFIED"
    assert report["observed_floors"] is None


def test_f2_missing_evaluation_is_not_a_pass():
    """No evaluation at all reports NOT_VERIFIED, never VERIFIED."""

    report = _architectural_fidelity_report(None, "success", True)

    assert report["architectural_status"] == "NOT_VERIFIED"
    assert report["floor_status"] == "NOT_VERIFIED"
    assert report["confidence"] == "NONE"
    assert report["advisory"] is True


# ---------------------------------------------------------------- invariants

@pytest.mark.parametrize(
    "evaluation,status,image",
    [
        (None, "success", True),
        (_evaluate({"floors": 25}, "", None, "25 storey tower"), "success", True),
        (
            _evaluate(
                {"floors": 25}, "", _total_contract(15, evidenced=True),
                "25 storey tower",
            ),
            "success",
            True,
        ),
    ],
)
def test_report_is_always_advisory_and_never_discards_the_image(
    evaluation, status, image
):
    report = _architectural_fidelity_report(evaluation, status, image)

    assert report["advisory"] is True
    assert report["image_preserved"] is True
    assert report["technical_status"] == "success"
    # The requested count is never echoed as an observed one.
    if report["observed_floors"] is not None:
        assert report["observation_available"] is True
