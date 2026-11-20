import json
from pathlib import Path

import pytest

from core.architecture.reasoning.authoritative_mixed_use_program_contract_v1 import AuthoritativeMixedUseProgramContractV1
from tools.audit_parcel2_authoritative_program_v1 import BASEMENT, REQUESTED_ITEMS, collect_evidence


def evidence(item_id="commercial", requirement_type="hard", value=True, source="user_project_requirement"):
    return {"id": item_id, "function": item_id, "requirement_type": requirement_type, "quantity": value,
            "source": source, "source_contract": "TEST", "source_path": "test.json#item",
            "provenance": [{"contract": "TEST", "path": "item"}], "confidence": 1.0,
            "applicability": {"project_id": "test"}, "authoritative": True,
            "human_decision_required": False}


def build(records, specs=None):
    return AuthoritativeMixedUseProgramContractV1().build(
        project_id="test", requested_items=specs or [{"id": "commercial"}], evidence_records=records)


def test_resolved_item_has_complete_provenance():
    item = build([evidence()])["resolved_items"][0]
    assert item["source"] and item["source_contract"] and item["source_path"]
    assert item["provenance"] and item["confidence"] == 1.0 and item["applicability"]


def test_missing_authoritative_item_remains_unresolved():
    item = build([])["program_items"][0]
    assert item["requirement_type"] == "unresolved"
    assert item["evidence_status"] == "unresolved_authoritative_program_input"
    assert item["human_decision_required"] is True


def test_preferred_human_intent_is_not_hard():
    item = build([evidence(requirement_type="preferred", source="human_review_decision")])["resolved_items"][0]
    assert item["requirement_type"] == "preferred"


def test_conflicting_sources_are_not_silently_reconciled():
    result = build([evidence(value=2), evidence(value=3, source="other_authoritative_source")])
    assert result["conflicted_items"][0]["evidence_status"] == "conflict"
    assert result["conflicted_items"][0]["human_decision_required"] is True


def test_parcel2_parking_two_is_traceable_to_current_source():
    source = json.loads(Path(BASEMENT).read_text(encoding="utf-8"))
    result = AuthoritativeMixedUseProgramContractV1().build(
        project_id="parcel_2", requested_items=REQUESTED_ITEMS, evidence_records=collect_evidence())
    parking = next(item for item in result["resolved_items"] if item["id"] == "parking")
    assert parking["count"] == source["requirements"]["parking"]["minimum_count"] == 2
    assert parking["source"] == "user_project_requirement"
    assert parking["source_path"].endswith("#requirements.parking")


def test_missing_optional_support_space_is_not_a_program_failure():
    result = build([], [{"id": "storage", "function": "storage"}])
    item = result["unresolved_items"][0]
    assert item["evidence_status"] == "unresolved_authoritative_program_input"
    assert item["program_failure"] is False
    assert not result["conflicted_items"]


def test_general_contract_rejects_parcel_specific_geometry():
    bad = evidence()
    bad["coordinates"] = [[0, 0], [1, 1]]
    with pytest.raises(ValueError, match="geometry is forbidden"):
        build([bad])


def test_non_authoritative_search_or_recommendation_does_not_resolve_item():
    record = evidence(requirement_type="preferred", source="search_target")
    record["authoritative"] = False
    item = build([record])["unresolved_items"][0]
    assert item["requirement_type"] == "unresolved"
    assert item["non_authoritative_evidence"][0]["source"] == "search_target"
