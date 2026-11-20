import json
from copy import deepcopy
from pathlib import Path

from core.architecture.reasoning.synthetic_parking_ramp_lifecycle_orchestration_v1 import (
    SyntheticParkingRampLifecycleOrchestrationV1,
)

ROOT = Path(__file__).resolve().parents[2]
REG = json.loads((ROOT / "core/architecture/contracts/iran_topic4_vehicle_parking_ramp_slope_evidence_v1.json").read_text(encoding="utf-8"))
PROJECT = json.loads((ROOT / "core/architecture/contracts/parcel2_human_program_evidence_v1.json").read_text(encoding="utf-8"))


def hypothesis(hid="h3", target=3):
    return {"hypothesis_id": hid, "target_capacity": target, "minimum_required_capacity": 3,
            "parking_ownership": "private", "ramp_enclosure": "covered"}


def candidate(cid="candidate-1", hid="h3", achieved=3, **changes):
    row = {"candidate_id": cid, "candidate_status": "design_result",
           "selected_status": "selected", "selection_evidence": [{"decision": "selected"}],
           "validation_status": "accepted", "validation_evidence": [{"check": "complete"}],
           "achieved_capacity": achieved,
           "achieved_capacity_evidence": [{"metric": "vehicle_count", "value": achieved}],
           "hypothesis_id": hid, "provenance": [{"source": "synthetic_non_geometry_result"}]}
    row.update(changes)
    return row


def run(hypotheses=None, candidates=None):
    return SyntheticParkingRampLifecycleOrchestrationV1().run(
        PROJECT, REG, hypotheses if hypotheses is not None else [hypothesis()],
        candidates if candidates is not None else [candidate()])


def test_target_three_stays_conditional_until_promotion_then_resolves_real_clause_and_transitions():
    result = run()
    before = result["authoritative_audit_before_promotion"]
    row = result["lifecycles"][0]
    provisional = row["hypothesis_evaluation"]
    slope = row["authoritative_audit"]["slope_constraint_authority"]
    assert before["parking_size_classification"]["status"] == "unresolved"
    assert before["slope_constraint_authority"]["status"] == "unresolved"
    assert provisional["provisional_size_class"]["value"] == "small"
    assert provisional["provisional_size_class"]["authority_class"] == "DESIGN_HYPOTHESIS"
    assert provisional["conditional_clause"]["authority_class"] == "DESIGN_HYPOTHESIS"
    assert row["promotion"]["authoritative_project_fact"]["value"] == 3
    assert row["authoritative_audit"]["parking_size_classification"]["parking_size_class"] == "small"
    assert slope["selected_clause"].endswith("private_small_covered")
    assert slope["maximum_slope_constraint"]["maximum_slope"] == 0.17
    assert slope["transition_constraints"]["transition_start"]["maximum_slope"] == 0.10
    assert slope["transition_constraints"]["transition_end"]["minimum_length"] == 1.0
    assert row["publication"]["status"] == "ready" and row["publication"]["published"] is False


def test_achieved_four_invalidates_target_but_promotes_reclassifies_and_blocks_publication():
    row = run(candidates=[candidate(achieved=4)])["lifecycles"][0]
    assert row["hypothesis_evaluation"]["hypothesis_status"] == "invalidated_by_result"
    assert row["promotion"]["hypothesis_consistency"]["status"] == "mismatch"
    assert row["promotion"]["authoritative_project_fact"]["value"] == 4
    assert row["authoritative_audit"]["parking_size_classification"]["parking_size_class"] == "medium"
    assert row["authoritative_audit"]["slope_constraint_authority"]["status"] == "unresolved"
    assert row["publication"]["status"] == "blocked"


def test_target_below_minimum_is_rejected_before_validation_and_cannot_publish():
    row = run([hypothesis(target=2)], [candidate(achieved=3)])["lifecycles"][0]
    assert row["hypothesis_evaluation"]["hypothesis_status"] == "hypothesis_rejected"
    assert "target_capacity_below_minimum_required_capacity" in row["hypothesis_evaluation"]["failure_reasons"]
    assert row["selection"]["status"] == "ineligible_hypothesis"
    assert row["validation"]["status"] == "not_evaluated"
    assert row["promotion"]["status"] == "promotion_forbidden"
    assert row["publication"]["status"] == "blocked"


def test_failed_unvalidated_historical_and_merely_feasible_are_forbidden():
    changes = ({"candidate_status": "failed"}, {"validation_status": "pending"},
               {"candidate_status": "historical"}, {"candidate_status": "merely_feasible"})
    for change in changes:
        row = run(candidates=[candidate(**change)])["lifecycles"][0]
        assert row["promotion"]["status"] == "promotion_forbidden"
        assert row["promotion"]["authoritative_project_fact"] is None


def test_multiple_hypotheses_are_bounded_sorted_and_duplicate_or_conflicting_ids_fail_closed():
    ordered = run([hypothesis("z", 4), hypothesis("a", 3)],
                  [candidate("cz", "z", 4), candidate("ca", "a", 3)])
    assert [row["hypothesis_id"] for row in ordered["lifecycles"]] == ["a", "z"]
    duplicate = run([hypothesis("same", 3), hypothesis("same", 4)], [])
    conflict = run([hypothesis()], [candidate("one"), candidate("two")])
    assert duplicate["status"] == "rejected"
    assert "duplicate_or_conflicting_hypothesis_ids" in duplicate["failure_reasons"]
    assert conflict["status"] == "rejected"
    assert "multiple_candidates_for_hypothesis_forbidden" in conflict["failure_reasons"]
    overflow = run([hypothesis(str(i), 3) for i in range(65)], [])
    assert overflow["status"] == "rejected" and "hypothesis_limit_exceeded" in overflow["failure_reasons"]


def test_lifecycle_states_are_separate_machine_readable_and_never_upgrade_provisional_evidence():
    result = run()
    row = result["lifecycles"][0]
    assert result["selection_is_validation"] is False
    assert result["validation_is_promotion"] is False
    assert result["promotion_is_publication"] is False
    assert row["selection"]["status"] == "selected"
    assert row["validation"]["status"] == "accepted"
    assert row["promotion"]["status"] == "promoted"
    assert row["publication"]["published"] is False
    encoded = json.dumps(row["hypothesis_evaluation"], sort_keys=True)
    assert "AUTHORITATIVE_PROJECT_FACT" not in encoded and "HARD_REGULATION" not in encoded


def test_repeated_execution_is_deterministic_non_mutating_and_executes_no_forbidden_pipeline():
    inputs = ([hypothesis()], [candidate()])
    before = deepcopy((PROJECT, REG, inputs))
    first = run(*inputs)
    second = run(*inputs)
    assert first == second and (PROJECT, REG, inputs) == before and first["input_mutated"] is False
    assert all(first[key] is False for key in (
        "geometry_generated", "ramp_profile_generated", "structure_executed", "bim_executed",
        "ifc_executed", "render_executed", "image_generation_executed"))
