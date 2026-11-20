import json
from copy import deepcopy
from pathlib import Path

from core.architecture.reasoning.conditional_regulation_applicability_evaluation_v1 import ConditionalRegulationApplicabilityEvaluationV1
from core.architecture.reasoning.validated_design_result_authority_promotion_v1 import ValidatedDesignResultAuthorityPromotionV1
from core.architecture.reasoning.parking_size_classification_authority_v1 import ParkingSizeClassificationAuthorityV1
from core.architecture.reasoning.parcel2_parking_ramp_applicability_audit_v1 import Parcel2ParkingRampApplicabilityAuditV1

ROOT = Path(__file__).resolve().parents[2]
REG = json.loads((ROOT / "core/architecture/contracts/iran_topic4_vehicle_parking_ramp_slope_evidence_v1.json").read_text(encoding="utf-8"))
PROJECT = json.loads((ROOT / "core/architecture/contracts/parcel2_human_program_evidence_v1.json").read_text(encoding="utf-8"))


def hypothesis(hid="h3", target=3):
    return {"hypothesis_id": hid, "target_capacity": target, "minimum_required_capacity": 3,
            "parking_ownership": "private", "ramp_enclosure": "covered"}


def candidate(achieved=3, **changes):
    value = {"candidate_id": "candidate-1", "candidate_status": "design_result",
             "selected_status": "selected", "selection_evidence": [{"decision": "selected"}],
             "validation_status": "accepted", "validation_evidence": [{"check": "complete"}],
             "achieved_capacity": achieved, "achieved_capacity_evidence": [{"metric": "vehicle_count", "value": achieved}],
             "hypothesis_id": "h3", "provenance": [{"source": "synthetic_non_geometry_result"}]}
    value.update(changes); return value


def evaluate(items, achieved=None):
    return ConditionalRegulationApplicabilityEvaluationV1().evaluate(
        items, REG["parking_size_classification"], REG["clauses"], REG, achieved)


def test_target_three_is_non_authoritative_small_with_conditional_clause_and_no_leakage():
    before = Parcel2ParkingRampApplicabilityAuditV1().resolve(PROJECT, REG, None)
    result = evaluate([hypothesis()])["evaluations"][0]
    after = Parcel2ParkingRampApplicabilityAuditV1().resolve(PROJECT, REG, None)
    assert result["hypothesis_status"] == "hypothesis_valid"
    assert result["provisional_size_class"]["value"] == "small"
    assert result["conditional_clause"]["status"] == "conditional_under_hypothesis"
    assert result["conditional_clause"]["clause_id"].endswith("private_small_covered")
    assert result["authority_class"] == "DESIGN_HYPOTHESIS" and result["authoritative"] is False
    assert before == after and after["parking_size_classification"]["status"] == "unresolved"


def test_target_two_rejected():
    result = evaluate([hypothesis(target=2)])["evaluations"][0]
    assert result["hypothesis_status"] == "hypothesis_rejected"
    assert "target_capacity_below_minimum_required_capacity" in result["failure_reasons"]


def test_validated_selected_three_promotes_and_authoritative_chain_resolves_small_clause():
    promoted = ValidatedDesignResultAuthorityPromotionV1().promote(candidate(), 3, hypothesis())
    fact = promoted["authoritative_project_fact"]
    classified = ParkingSizeClassificationAuthorityV1().resolve(REG, fact)
    audit = Parcel2ParkingRampApplicabilityAuditV1().resolve(PROJECT, REG, fact)
    assert promoted["status"] == "promoted" and promoted["hypothesis_consistency"]["status"] == "match"
    assert classified["parking_size_class"] == "small"
    assert audit["slope_constraint_authority"]["status"] == "resolved"
    assert audit["slope_constraint_authority"]["selected_clause"].endswith("private_small_covered")


def test_achieved_four_invalidates_hypothesis_but_promotes_result_and_blocks_publication_downstream():
    lifecycle = evaluate([hypothesis()], [{"hypothesis_id": "h3", "achieved_capacity": 4}])["evaluations"][0]
    promoted = ValidatedDesignResultAuthorityPromotionV1().promote(candidate(4), 3, hypothesis())
    audit = Parcel2ParkingRampApplicabilityAuditV1().resolve(PROJECT, REG, promoted["authoritative_project_fact"])
    assert lifecycle["hypothesis_status"] == "invalidated_by_result"
    assert promoted["status"] == "promoted" and promoted["hypothesis_consistency"]["status"] == "mismatch"
    assert audit["parking_size_classification"]["parking_size_class"] == "medium"
    assert audit["slope_constraint_authority"]["status"] == "unresolved"
    assert audit["blocker_next"] == "explicit_regulation_clause_for_resolved_applicability"


def test_failed_unvalidated_historical_or_merely_feasible_cannot_promote():
    gate = ValidatedDesignResultAuthorityPromotionV1()
    cases = [candidate(candidate_status="failed"), candidate(validation_status="pending"),
             candidate(candidate_status="historical"), candidate(candidate_status="merely_feasible")]
    assert all(gate.promote(item, 3, hypothesis())["status"] == "promotion_forbidden" for item in cases)


def test_selected_alone_and_non_evidence_capacity_cannot_promote():
    gate = ValidatedDesignResultAuthorityPromotionV1()
    assert gate.promote(candidate(validation_status=None, validation_evidence=[]), 3, hypothesis())["status"] == "promotion_forbidden"
    assert gate.promote(candidate(achieved_capacity_evidence=[]), 3, hypothesis())["status"] == "promotion_forbidden"


def test_multiple_hypotheses_are_deterministic_bounded_and_inputs_are_not_mutated():
    items = [hypothesis("z", 4), hypothesis("a", 3)]; original = deepcopy(items)
    first = evaluate(items); second = evaluate(items)
    assert first == second and items == original and first["input_mutated"] is False
    assert [row["hypothesis_id"] for row in first["evaluations"]] == ["a", "z"]
    overflow = evaluate([hypothesis(str(i), 3) for i in range(65)])
    assert overflow["status"] == "rejected" and overflow["failure_reasons"] == ["hypothesis_limit_exceeded"]
