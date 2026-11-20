import json
from copy import deepcopy
from pathlib import Path

from core.architecture.reasoning.ramp_slope_profile_validation_v1 import RampSlopeProfileValidationV1
from core.architecture.reasoning.ramp_vehicle_slope_constraint_authority_v1 import RampVehicleSlopeConstraintAuthorityV1


SOURCE = Path(__file__).parents[2] / "core" / "architecture" / "contracts" / "iran_topic4_vehicle_parking_ramp_slope_evidence_v1.json"


def evidence():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def resolve(**overrides):
    context = {"ramp_use": "vehicle_parking", "parking_ownership": "private",
               "parking_size_class": "medium", "ramp_enclosure": "open"}
    context.update(overrides)
    return RampVehicleSlopeConstraintAuthorityV1().resolve(evidence(), applicability(context))


def applicability(values):
    authorities = {"parking_size_class": "HARD_REGULATION"}
    return {"contract": "ParkingRampApplicabilityAuditV1", "facts": {
        key: {"status": "resolved", "value": value,
              "authority_class": authorities.get(key, "PROJECT_REQUIREMENT"),
              "source_kind": "regulation" if key == "parking_size_class" else "explicit_user_requirement",
              "provenance": [{"source": "synthetic_authoritative_fact", "key": key}]}
        for key, value in values.items()}}


def binding():
    return {"contract": "AuthoritativeRampEndpointBindingContractV1", "status": "resolved",
            "binding_resolved": True, "expected_start_z": 0.0, "expected_end_z": -2.4}


def profile(main_length=14.0, transition_length=1.0):
    return [{"contract": "RampPathProfileEvidenceV1", "status": "resolved", "path_id": "center",
             "provenance": [{"source": "synthetic_path"}], "segments": [
                 {"role": "transition_start", "start_z": 0.0, "end_z": -0.1,
                  "length": transition_length, "provenance": [{"source": "synthetic_segment"}]},
                 {"role": "main", "start_z": -0.1, "end_z": -2.2,
                  "length": main_length, "provenance": [{"source": "synthetic_segment"}]},
                 {"role": "transition_end", "start_z": -2.2, "end_z": -2.4,
                  "length": 2.0, "provenance": [{"source": "synthetic_segment"}]},
             ]}]


def test_exact_private_medium_open_clause_resolves_hard_15_percent_and_transitions():
    result = resolve()
    assert result["status"] == "resolved"
    assert result["maximum_slope_constraint"]["maximum_slope"] == 0.15
    assert result["maximum_slope_constraint"]["authority_class"] == "HARD_REGULATION"
    assert result["maximum_slope_constraint"]["provenance"][0]["clause"] == "4-5-10-2-7"
    assert result["transition_constraints"]["transition_start"]["maximum_slope"] == 0.10
    assert result["transition_constraints"]["transition_end"]["minimum_length"] == 1.0


def test_small_private_covered_is_17_percent_not_global_15_percent():
    result = resolve(parking_size_class="small", ramp_enclosure="covered")
    assert result["status"] == "resolved"
    assert result["maximum_slope_constraint"]["maximum_slope"] == 0.17
    assert result["maximum_slope_constraint"]["provenance"][0]["clause"] == "4-5-10-2-8"


def test_secondary_only_source_does_not_become_hard_authority():
    source = evidence()
    source["source"]["kind"] = "secondary_summary"
    result = RampVehicleSlopeConstraintAuthorityV1().resolve(source, applicability({
        "ramp_use": "vehicle_parking", "parking_ownership": "private",
        "parking_size_class": "medium", "ramp_enclosure": "open"}))
    assert result["status"] == "unresolved"
    assert result["maximum_slope_constraint"] is None


def test_pedestrian_or_incomplete_applicability_stays_unresolved():
    pedestrian = resolve(ramp_use="accessible_pedestrian")
    incomplete = RampVehicleSlopeConstraintAuthorityV1().resolve(evidence(), applicability({"ramp_use": "vehicle_parking"}))
    assert pedestrian["status"] == "unresolved"
    assert incomplete["status"] == "unresolved"
    assert incomplete["transition_constraints"]["transition_start"]["status"] == "unresolved"


def test_constraint_output_wires_directly_to_profile_validator_without_geometry_generation():
    authority = resolve()
    validated = RampSlopeProfileValidationV1().resolve(
        binding(), authority["maximum_slope_constraint"], profile(), authority["transition_constraints"])
    failed = RampSlopeProfileValidationV1().resolve(
        binding(), authority["maximum_slope_constraint"], profile(main_length=13.9), authority["transition_constraints"])
    assert validated["status"] == "validated"
    assert validated["geometry_generated"] is False
    assert failed["status"] == "invalid"
    assert "center_segment_1_slope_exceeds_maximum" in failed["failure_reasons"]


def test_missing_transition_authority_keeps_profile_unresolved():
    authority = resolve()
    validated = RampSlopeProfileValidationV1().resolve(
        binding(), authority["maximum_slope_constraint"], profile(), None)
    assert validated["status"] == "unresolved"


def test_transition_length_below_authoritative_minimum_fails():
    authority = resolve()
    validated = RampSlopeProfileValidationV1().resolve(
        binding(), authority["maximum_slope_constraint"], profile(transition_length=0.9),
        authority["transition_constraints"])
    assert validated["status"] == "invalid"
    assert "center_segment_0_length_below_minimum" in validated["failure_reasons"]


def test_deterministic_and_no_mutation():
    source = evidence()
    context = {"ramp_use": "vehicle_parking", "parking_ownership": "private",
               "parking_size_class": "medium", "ramp_enclosure": "open"}
    audit = applicability(context); before = deepcopy((source, audit))
    first = RampVehicleSlopeConstraintAuthorityV1().resolve(source, audit)
    second = RampVehicleSlopeConstraintAuthorityV1().resolve(source, audit)
    assert first == second
    assert (source, audit) == before
    assert first["input_mutated"] is False


def test_authority_resolver_source_has_no_geometry_or_pipeline_dependency():
    source_text = (Path(__file__).parents[2] / "core" / "architecture" / "reasoning" /
                   "ramp_vehicle_slope_constraint_authority_v1.py").read_text(encoding="utf-8")
    forbidden = ("geometry", "placement", "parking_design_reasoner", "bim", "ifc", "render")
    assert not any(f"import {name}" in source_text.lower() for name in forbidden)
    assert "RampSlopePolicyV1" not in source_text


def test_raw_or_geometry_derived_applicability_cannot_select_clause():
    raw = RampVehicleSlopeConstraintAuthorityV1().resolve(evidence(), {
        "ramp_use": "vehicle_parking", "parking_ownership": "private",
        "parking_size_class": "small", "ramp_enclosure": "covered"})
    audit = applicability({"ramp_use": "vehicle_parking", "parking_ownership": "private",
                           "parking_size_class": "small", "ramp_enclosure": "covered"})
    audit["facts"]["parking_size_class"]["source_kind"] = "geometry_derived"
    derived = RampVehicleSlopeConstraintAuthorityV1().resolve(evidence(), audit)
    assert raw["status"] == "unresolved" and derived["status"] == "unresolved"
