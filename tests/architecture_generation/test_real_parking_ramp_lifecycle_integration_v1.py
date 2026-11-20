import json
from copy import deepcopy
from pathlib import Path

from core.architecture.reasoning.real_parking_ramp_lifecycle_integration_v1 import RealParkingRampLifecycleIntegrationV1

ROOT = Path(__file__).resolve().parents[2]
REG = json.loads((ROOT / "core/architecture/contracts/iran_topic4_vehicle_parking_ramp_slope_evidence_v1.json").read_text(encoding="utf-8"))
PROJECT = json.loads((ROOT / "core/architecture/contracts/parcel2_human_program_evidence_v1.json").read_text(encoding="utf-8"))


def inputs(achieved=3, accepted=True):
    cid = "BASEMENT-V2-01"
    producer = {"source": "BasementRampParkingDesignReasonerV2", "selection_status": "resolved",
                "selected_candidate": {"candidate_id": cid, "parking_stalls": ["stall"] * achieved,
                                       "ramp": {"geometry": "must-not-leak"}},
                "provenance": [{"source": "real_producer", "candidate_id": cid}]}
    acceptance = {"source": "BasementVehicleArchitecturalAcceptanceV2", "candidate_id": cid,
                  "validation_status": "accepted" if accepted else "failed",
                  "automated_geometry_pass": accepted, "human_visual_acceptance": "not_required",
                  "achieved_parking_capacity": achieved if accepted else None,
                  "accepted_result_evidence": ([{"source": "acceptance", "candidate_id": cid,
                                                 "parking_stall_count": achieved}] if accepted else [])}
    binding = {"contract": "AuthoritativeRampEndpointBindingContractV1", "status": "resolved",
               "binding_resolved": True, "expected_start_z": 0.0, "expected_end_z": -2.4}
    slope = {"contract": "RampSlopeProfileValidationV1", "status": "validated",
             "slope_validated": True, "provenance": [{"source": "profile"}]}
    hypothesis = {"hypothesis_id": "H2", "target_capacity": 3}
    return producer, acceptance, slope, binding, hypothesis


def run(achieved=3, accepted=True):
    producer, acceptance, slope, binding, hypothesis = inputs(achieved, accepted)
    return RealParkingRampLifecycleIntegrationV1().run(
        PROJECT, REG, hypothesis, producer, acceptance, slope, binding)


def test_real_producer_cannot_promote_before_acceptance_and_partial_or_failed_cannot_promote():
    for acceptance_change in ({"validation_status": "pending"},
                              {"validation_status": "failed", "automated_geometry_pass": False},
                              {"human_visual_acceptance": "pending"}):
        producer, acceptance, slope, binding, hypothesis = inputs()
        acceptance.update(acceptance_change)
        result = RealParkingRampLifecycleIntegrationV1().run(
            PROJECT, REG, hypothesis, producer, acceptance, slope, binding)
        assert result["promotion"]["promotion_status"] == "forbidden"
        assert result["promotion"]["authoritative_project_fact"] is None


def test_accepted_three_promotes_and_chain_is_traceable_without_geometry_leakage():
    result = run(3)
    assert result["promotion"]["authoritative_project_fact"]["value"] == 3
    assert result["authoritative_audit"]["parking_size_classification"]["parking_size_class"] == "small"
    assert result["authoritative_audit"]["slope_constraint_authority"]["status"] == "resolved"
    provenance = result["promotion"]["authoritative_project_fact"]["provenance"][0]
    assert provenance["candidate_id"] == "BASEMENT-V2-01"
    assert provenance["validation_evidence"][1]["endpoint_binding"]["binding_resolved"] is True
    assert "must-not-leak" not in json.dumps(result["authoritative_audit"])
    assert result["candidate_geometry_exposed_to_authoritative_audit"] is False
    assert result["publication"]["published"] is False


def test_accepted_four_reclassifies_medium_and_covered_medium_blocks_publication():
    result = run(4)
    assert result["promotion"]["authoritative_project_fact"]["value"] == 4
    assert result["authoritative_audit"]["parking_size_classification"]["parking_size_class"] == "medium"
    assert result["authoritative_audit"]["slope_constraint_authority"]["status"] == "unresolved"
    assert result["publication"]["status"] == "blocked"


def test_binding_and_profile_are_both_mandatory_and_identity_mismatch_fails_closed():
    producer, acceptance, slope, binding, hypothesis = inputs()
    cases = [(producer, acceptance, None, binding),
             (producer, acceptance, slope, None)]
    mismatch = deepcopy(acceptance); mismatch["candidate_id"] = "OTHER"
    cases.append((producer, mismatch, slope, binding))
    for p, a, s, b in cases:
        result = RealParkingRampLifecycleIntegrationV1().run(PROJECT, REG, hypothesis, p, a, s, b)
        assert result["promotion"]["promotion_status"] == "forbidden"


def test_deterministic_no_mutation_and_lifecycle_states_remain_distinct():
    producer, acceptance, slope, binding, hypothesis = inputs()
    call = (PROJECT, REG, hypothesis, producer, acceptance, slope, binding)
    before = deepcopy(call)
    first = RealParkingRampLifecycleIntegrationV1().run(*call)
    second = RealParkingRampLifecycleIntegrationV1().run(*call)
    assert first == second and call == before and first["input_mutated"] is False
    assert first["auto_selection_performed"] is False
    assert first["selection_is_validation"] is False
    assert first["validation_is_promotion"] is False
    assert first["promotion_is_publication"] is False
