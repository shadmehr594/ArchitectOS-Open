"""HOUSE-DIFFUSION-CONDITIONING-QUALITY-AUDIT-02A1 — quality evaluator tests.

Proves the evaluator MEASURES and CLASSIFIES only: it never alters geometry, it
can both REJECT a defective candidate and PASS a sound one, and it makes no
compass/site assumption.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from core.architecture.reasoning.housediffusion_architectural_quality_evaluation_v1 import (
    CONTRACT,
    HARD_CODES,
    PRIVATE_ZONE,
    PUBLIC_ZONE,
    HouseDiffusionArchitecturalQualityEvaluationV1,
    evaluate_candidate,
)


ROOT = Path(__file__).resolve().parents[2]
REAL_CANDIDATE = Path(r"D:\AI_Architecture_Lab\full_program_02\semantic_plan_candidate_v2.json")


def _box(x, y, w, h):
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]]


def _space(identity, polygon):
    return {"architectos_identity": identity, "space_id": identity,
            "polygon": polygon, "floor": "ground_floor"}


def _door(door_id, a, b, front=False):
    return {"door_id": door_id, "door_type": "FRONT" if front else "INTERIOR",
            "between_identities": [a] if front else [a, b],
            "native_type": "T15" if front else "T17"}


def _sound_candidate():
    """A synthetic candidate that satisfies every hard gate.

    Sizes approximate the program's target shares so the proportional band holds.
    """
    spaces = [
        _space("UNIT_ENTRY", _box(0.00, 0.00, 0.22, 0.25)),
        _space("GUEST_WC", _box(0.00, 0.26, 0.22, 0.20)),
        _space("LIVING_RECEPTION", _box(0.23, 0.00, 0.39, 0.68)),
        _space("CLOSED_KITCHEN", _box(0.00, 0.47, 0.22, 0.50)),
        _space("MASTER_BEDROOM_SLEEPING", _box(0.63, 0.00, 0.29, 0.76)),
        _space("BEDROOM_DOUBLE", _box(0.63, 0.77, 0.28, 0.55)),
        _space("FAMILY_BATHROOM", _box(0.92, 0.77, 0.22, 0.30)),
        _space("TERRACE_BALCONY", _box(0.23, 0.69, 0.39, 0.226)),
    ]
    doors = [
        _door("D1", "UNIT_ENTRY", None, front=True),
        _door("D2", "UNIT_ENTRY", "LIVING_RECEPTION"),
        _door("D3", "LIVING_RECEPTION", "CLOSED_KITCHEN"),
        _door("D4", "UNIT_ENTRY", "GUEST_WC"),
        _door("D5", "LIVING_RECEPTION", "MASTER_BEDROOM_SLEEPING"),
        _door("D6", "MASTER_BEDROOM_SLEEPING", "BEDROOM_DOUBLE"),
        _door("D7", "BEDROOM_DOUBLE", "FAMILY_BATHROOM"),
        _door("D8", "LIVING_RECEPTION", "TERRACE_BALCONY"),
    ]
    return {"schema": "SemanticPlanCandidateV2", "candidate_id": "synthetic-sound",
            "source_engine": "HOUSE_DIFFUSION", "source_seed": 0,
            "spaces": spaces, "doors": doors}


@pytest.fixture(scope="module")
def evaluator():
    return HouseDiffusionArchitecturalQualityEvaluationV1()


# ==========================================================
# contract + read-only guarantee
# ==========================================================

def test_contract_and_verdict_domain(evaluator):
    result = evaluator.evaluate(_sound_candidate())
    assert result["contract"] == CONTRACT
    assert result["verdict"] in ("PASS", "REJECT", "INDETERMINATE")
    assert result["read_only"] is True
    assert result["geometry_altered"] is False


def test_evaluator_never_mutates_the_candidate(evaluator):
    candidate = _sound_candidate()
    snapshot = deepcopy(candidate)
    evaluator.evaluate(candidate)
    assert candidate == snapshot


def test_evaluator_can_pass_a_sound_candidate(evaluator):
    """The gate must be able to PASS — it is not a gate that always rejects."""
    result = evaluator.evaluate(_sound_candidate())
    assert result["verdict"] == "PASS", (result["hard_failures"], result["reasons"])
    assert result["hard_failures"] == []


# ==========================================================
# geometry gates
# ==========================================================

def test_overlap_is_rejected(evaluator):
    candidate = _sound_candidate()
    candidate["spaces"][2]["polygon"] = _box(0.23, 0.00, 0.45, 0.68)  # overlaps kitchen
    result = evaluator.evaluate(candidate)
    assert "GEOMETRY_OVERLAP" in result["hard_failures"]


def test_detached_space_is_rejected(evaluator):
    candidate = _sound_candidate()
    candidate["spaces"][7]["polygon"] = _box(5.00, 5.00, 0.39, 0.226)  # balcony flown away
    result = evaluator.evaluate(candidate)
    assert "GEOMETRY_DETACHED_SPACE" in result["hard_failures"]
    assert "TERRACE_BALCONY" in result["measurements"]["detached_spaces"]


def test_invalid_polygon_is_rejected(evaluator):
    candidate = _sound_candidate()
    candidate["spaces"][0]["polygon"] = [[0, 0], [1, 1]]
    result = evaluator.evaluate(candidate)
    assert "GEOMETRY_INVALID_POLYGON" in result["hard_failures"]


# ==========================================================
# program gates
# ==========================================================

def test_missing_required_identity_is_rejected(evaluator):
    candidate = _sound_candidate()
    candidate["spaces"] = [s for s in candidate["spaces"]
                           if s["architectos_identity"] != "FAMILY_BATHROOM"]
    result = evaluator.evaluate(candidate)
    assert "PROGRAM_MISSING_REQUIRED_IDENTITY" in result["hard_failures"]


def test_metric_area_is_declared_unsupported(evaluator):
    result = evaluator.evaluate(_sound_candidate())
    rows = result["measurements"]["area_rows"]
    assert rows
    assert all(row["metric_area_supported"] is False for row in rows)
    assert "UNSUPPORTED" in result["measurements"]["area_proportional_basis"]


def test_undersized_room_is_measured(evaluator):
    candidate = _sound_candidate()
    # shrink the kitchen drastically
    candidate["spaces"][3]["polygon"] = _box(0.00, 0.47, 0.22, 0.10)
    result = evaluator.evaluate(candidate)
    kitchen = next(r for r in result["measurements"]["area_rows"]
                   if r["identity"] == "CLOSED_KITCHEN")
    assert kitchen["share_ratio"] < 0.5
    assert "PROGRAM_AREA_UNDERSIZED" in result["soft_findings"]


# ==========================================================
# relationship gates
# ==========================================================

def test_kitchen_living_relation_required(evaluator):
    candidate = _sound_candidate()
    candidate["doors"] = [d for d in candidate["doors"] if d["door_id"] != "D3"]
    candidate["spaces"][3]["polygon"] = _box(3.0, 3.0, 0.22, 0.50)  # detached + not adjacent
    result = evaluator.evaluate(candidate)
    assert "RELATION_KITCHEN_NOT_ADJACENT_TO_LIVING" in result["hard_failures"]


def test_entry_living_relation_required(evaluator):
    candidate = _sound_candidate()
    candidate["doors"] = [d for d in candidate["doors"] if d["door_id"] != "D2"]
    candidate["spaces"][0]["polygon"] = _box(3.0, 3.0, 0.22, 0.25)
    result = evaluator.evaluate(candidate)
    assert "RELATION_ENTRY_NOT_ADJACENT_TO_LIVING" in result["hard_failures"]


def test_relation_satisfied_by_door_without_geometric_adjacency(evaluator):
    """A door counts even when the polygons are not within the adjacency band."""
    candidate = _sound_candidate()
    candidate["spaces"][3]["polygon"] = _box(0.00, 1.20, 0.22, 0.50)  # far from living
    candidate["spaces"][7]["polygon"] = _box(0.23, 1.20, 0.39, 0.226)
    result = evaluator.evaluate(candidate)
    assert result["measurements"]["relations"]["kitchen_living_adjacent"] is True
    assert "RELATION_KITCHEN_NOT_ADJACENT_TO_LIVING" not in result["hard_failures"]


# ==========================================================
# access gates
# ==========================================================

def test_unreachable_enclosed_room_is_rejected(evaluator):
    candidate = _sound_candidate()
    candidate["doors"] = [d for d in candidate["doors"]
                          if d["door_id"] not in ("D5", "D6", "D7")]
    result = evaluator.evaluate(candidate)
    assert "ACCESS_ROOM_UNREACHABLE_FROM_EXPLICIT_DOORS" in result["hard_failures"]
    unreachable = result["measurements"]["access"]["unreachable"]
    assert "MASTER_BEDROOM_SLEEPING" in unreachable


def test_no_door_at_all_is_rejected(evaluator):
    candidate = _sound_candidate()
    candidate["doors"] = []
    result = evaluator.evaluate(candidate)
    assert "ACCESS_NO_EXPLICIT_DOOR" in result["hard_failures"]


def test_access_never_uses_proximity_inference(evaluator):
    result = evaluator.evaluate(_sound_candidate())
    assert result["measurements"]["access"]["proximity_inference_used"] is False


# ==========================================================
# zoning gates (topological, no compass)
# ==========================================================

def test_master_outside_private_cluster_is_rejected(evaluator):
    candidate = _sound_candidate()
    # master is moved away AND disconnected from every private room, then wired to
    # the entry only -> it sits in the public side of the plan
    candidate["spaces"][4]["polygon"] = _box(0.00, 1.20, 0.29, 0.76)
    candidate["doors"] = [d for d in candidate["doors"]
                          if d["door_id"] not in ("D5", "D6")]
    candidate["doors"].append(_door("D9", "UNIT_ENTRY", "MASTER_BEDROOM_SLEEPING"))
    result = evaluator.evaluate(candidate)
    assert "ZONING_MASTER_NOT_IN_PRIVATE_CLUSTER" in result["hard_failures"]
    assert result["measurements"]["zoning"]["master_neighbours"] == ["UNIT_ENTRY"]


def test_private_cluster_disconnection_is_rejected(evaluator):
    candidate = _sound_candidate()
    candidate["doors"] = [d for d in candidate["doors"] if d["door_id"] != "D6"]
    candidate["spaces"][5]["polygon"] = _box(3.0, 0.0, 0.28, 0.55)
    candidate["spaces"][6]["polygon"] = _box(3.0, 0.60, 0.22, 0.30)
    candidate["doors"].append(_door("D9", "BEDROOM_DOUBLE", "FAMILY_BATHROOM"))
    candidate["doors"].append(_door("D10", "LIVING_RECEPTION", "BEDROOM_DOUBLE"))
    result = evaluator.evaluate(candidate)
    assert "ZONING_PRIVATE_CLUSTER_DISCONNECTED" in result["hard_failures"]


def test_excessive_public_private_mixing_is_rejected(evaluator):
    candidate = _sound_candidate()
    candidate["doors"].append(_door("D9", "MASTER_BEDROOM_SLEEPING", "GUEST_WC"))
    result = evaluator.evaluate(candidate)
    assert "ZONING_EXCESSIVE_PUBLIC_PRIVATE_MIXING" in result["hard_failures"]


def test_zoning_basis_is_topological_not_compass(evaluator):
    result = evaluator.evaluate(_sound_candidate())
    zoning = result["measurements"]["zoning"]
    assert "TOPOLOGICAL" in zoning["basis"]
    assert "compass" in zoning["basis"]
    # no compass field is ever emitted
    assert not any("north" in key.lower() or "south" in key.lower()
                   for key in zoning)
    assert zoning["public_zone"] == list(PUBLIC_ZONE)
    assert zoning["private_zone"] == list(PRIVATE_ZONE)


def test_hard_codes_are_declared():
    assert "GEOMETRY_OVERLAP" in HARD_CODES
    assert "ACCESS_ROOM_UNREACHABLE_FROM_EXPLICIT_DOORS" in HARD_CODES
    assert "ZONING_MASTER_NOT_IN_PRIVATE_CLUSTER" in HARD_CODES


# ==========================================================
# real candidate regression
# ==========================================================

@pytest.mark.skipif(not REAL_CANDIDATE.is_file(), reason="real candidate unavailable")
def test_real_seed23_is_rejected_with_expected_findings(evaluator):
    candidate = json.loads(REAL_CANDIDATE.read_text(encoding="utf-8"))
    result = evaluator.evaluate(candidate)
    assert result["verdict"] == "REJECT"
    # the exact observed defect: undersized kitchen (0.043518 normalized)
    kitchen = next(r for r in result["measurements"]["area_rows"]
                   if r["identity"] == "CLOSED_KITCHEN")
    assert kitchen["area_normalized"] == pytest.approx(0.043518, abs=1e-6)
    assert kitchen["share_ratio"] < 0.5
    master = next(r for r in result["measurements"]["area_rows"]
                  if r["identity"] == "MASTER_BEDROOM_SLEEPING")
    assert master["area_normalized"] == pytest.approx(0.159485, abs=1e-6)


@pytest.mark.skipif(not REAL_CANDIDATE.is_file(), reason="real candidate unavailable")
def test_real_candidate_evaluation_is_deterministic(evaluator):
    candidate = json.loads(REAL_CANDIDATE.read_text(encoding="utf-8"))
    first = evaluator.evaluate(candidate)
    second = evaluator.evaluate(candidate)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


@pytest.mark.skipif(not REAL_CANDIDATE.is_file(), reason="real candidate unavailable")
def test_real_candidate_has_no_metric_area_claim(evaluator):
    candidate = json.loads(REAL_CANDIDATE.read_text(encoding="utf-8"))
    result = evaluator.evaluate(candidate)
    for row in result["measurements"]["area_rows"]:
        assert row["metric_area_supported"] is False
