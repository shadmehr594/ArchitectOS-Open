import json
from copy import deepcopy
from pathlib import Path

from core.architecture.reasoning.parking_size_classification_authority_v1 import ParkingSizeClassificationAuthorityV1
from core.architecture.reasoning.parcel2_parking_ramp_applicability_audit_v1 import Parcel2ParkingRampApplicabilityAuditV1

ROOT = Path(__file__).resolve().parents[2]
REGULATION = json.loads((ROOT / "core/architecture/contracts/iran_topic4_vehicle_parking_ramp_slope_evidence_v1.json").read_text(encoding="utf-8"))
PROJECT = json.loads((ROOT / "core/architecture/contracts/parcel2_human_program_evidence_v1.json").read_text(encoding="utf-8"))


def capacity(value, semantic="authoritative_final_capacity", source_kind="accepted_final_parking_contract"):
    return {"status": "resolved", "value": value, "semantic": semantic,
            "authority_class": "AUTHORITATIVE_PROJECT_FACT", "source_kind": source_kind,
            "provenance": [{"contract": "AcceptedFinalParkingCapacityV1", "key": "vehicle_count"}]}


def classify(value):
    return ParkingSizeClassificationAuthorityV1().resolve(REGULATION, capacity(value))


def test_minimum_three_does_not_imply_small():
    result = ParkingSizeClassificationAuthorityV1().resolve(
        REGULATION, capacity(3, semantic="minimum_required_capacity"))
    assert result["status"] == "unresolved" and result["parking_size_class"] is None


def test_authoritative_boundaries_3_4_25_26():
    assert classify(3)["parking_size_class"] == "small"
    assert classify(4)["parking_size_class"] == "medium"
    assert classify(25)["parking_size_class"] == "medium"
    assert classify(26)["parking_size_class"] == "large"


def test_classification_requires_source_supported_definition():
    source = deepcopy(REGULATION); source.pop("parking_size_classification")
    result = ParkingSizeClassificationAuthorityV1().resolve(source, capacity(3))
    assert result["status"] == "unresolved" and result["parking_size_class"] is None


def test_candidate_or_geometry_achieved_cannot_be_authority():
    for source_kind in ("geometry_candidate", "candidate_geometry", "geometry_derived"):
        result = ParkingSizeClassificationAuthorityV1().resolve(REGULATION, capacity(3, source_kind=source_kind))
        assert result["status"] == "unresolved"


def test_private_covered_unknown_class_stays_unresolved_at_current_checkpoint():
    result = Parcel2ParkingRampApplicabilityAuditV1().resolve(PROJECT, REGULATION, None)
    assert result["facts"]["parking_ownership"]["value"] == "private"
    assert result["facts"]["minimum_required_parking_capacity"]["value"] == 3
    assert result["facts"]["minimum_required_parking_capacity"]["semantic"] == "minimum_lower_bound_not_achieved_or_final_capacity"
    assert result["facts"]["ramp_enclosure"]["value"] == "covered"
    assert result["parking_size_classification"]["status"] == "unresolved"
    assert result["slope_constraint_authority"]["status"] == "unresolved"
    assert result["slope_constraint_authority"]["maximum_slope_constraint"] is None


def test_private_covered_small_selects_clause_only_with_all_valid_evidence():
    result = Parcel2ParkingRampApplicabilityAuditV1().resolve(PROJECT, REGULATION, capacity(3))
    slope = result["slope_constraint_authority"]
    assert slope["status"] == "resolved" and slope["selected_clause"].endswith("private_small_covered")
    assert slope["maximum_slope_constraint"]["maximum_slope"] == 0.17


def test_private_covered_medium_and_large_have_no_invented_clause():
    for value in (4, 26):
        result = Parcel2ParkingRampApplicabilityAuditV1().resolve(PROJECT, REGULATION, capacity(value))
        assert result["parking_size_classification"]["status"] == "resolved"
        assert result["slope_constraint_authority"]["status"] == "unresolved"
        assert result["slope_constraint_authority"]["maximum_slope_constraint"] is None


def test_deterministic_no_mutation_and_no_forbidden_execution():
    inputs = deepcopy((PROJECT, REGULATION)); resolver = Parcel2ParkingRampApplicabilityAuditV1()
    first = resolver.resolve(PROJECT, REGULATION, None); second = resolver.resolve(PROJECT, REGULATION, None)
    assert first == second and (PROJECT, REGULATION) == inputs and first["input_mutated"] is False
    assert all(first[key] is False for key in (
        "geometry_generated", "ramp_profile_generated", "ramp_placement_generated",
        "parking_integration_geometry_generated", "rooms_generated", "windows_generated",
        "structure_executed", "bim_executed", "ifc_executed", "render_executed", "image_generation_executed"))


def test_generic_authority_has_no_parcel_or_cardinal_leakage():
    text = (ROOT / "core/architecture/reasoning/parking_size_classification_authority_v1.py").read_text(encoding="utf-8").lower()
    assert "parcel2" not in text and "parcel 2" not in text
    assert not any(token in text for token in ("north", "south", "east", "west"))
