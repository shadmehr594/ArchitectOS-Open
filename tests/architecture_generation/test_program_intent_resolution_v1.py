from copy import deepcopy

import pytest

from core.architecture.reasoning.program_intent_resolution_v1 import ProgramIntentResolutionV1


def base(status="unresolved_authoritative_program_input"):
    item = {"id": "commercial", "function": "commercial", "requirement_type": "unresolved",
            "source_contract": None, "source_path": None, "provenance": [], "evidence_status": status}
    if status == "authoritative_resolved":
        item.update({"requirement_type": "hard", "source_contract": "BASE", "source_path": "base.json#commercial",
                     "provenance": [{"contract": "BASE", "key": "commercial"}]})
    return {"contract": "AuthoritativeMixedUseProgramContractV1", "project_id": "test", "program_items": [item]}


def evidence(value=True, **changes):
    record = {"id": "commercial", "requirement_type": "hard", "source_kind": "project_requirement",
              "confirmation_status": "confirmed", "source": "user_project_requirement",
              "source_contract": "TEST", "source_path": "test.json#commercial", "key": "commercial",
              "provenance": [{"contract": "TEST", "key": "commercial"}], "confidence": 1.0,
              "applicability": {"project_id": "test"}, "value": value}
    record.update(changes)
    return record


def resolve(records, contract=None):
    return ProgramIntentResolutionV1().build(authoritative_contract=contract or base(), evidence_records=records)


def test_resolved_item_without_provenance_fails():
    bad = evidence(provenance=[])
    with pytest.raises(ValueError, match="provenance"):
        resolve([bad])


def test_human_preference_cannot_be_hard_requirement():
    bad = evidence(source_kind="human_preference")
    with pytest.raises(ValueError, match="cannot become a hard"):
        resolve([bad])


def test_explicit_user_requirement_is_correctly_resolved():
    item = resolve([evidence(source_kind="explicit_user_requirement")])["program_items"][0]
    assert item["status"] == "human_design_intent_resolved"
    assert item["requirement_type"] == "hard" and item["downstream_demand_state"] == "known"
    assert item["source_contract"] == "TEST" and item["source_path"] and item["key"] == "commercial"


def test_historical_search_target_is_ignored_as_authority():
    record = evidence(source_kind="historical_search_target", provenance=[])
    result = resolve([record])
    assert result["program_items"][0]["status"] == "unresolved_authoritative_input"
    assert result["ignored_evidence"][0]["source_kind"] == "historical_search_target"


def test_conflicting_sources_are_explicit():
    result = resolve([evidence(value=2), evidence(value=3, source_contract="OTHER")])
    item = result["program_items"][0]
    assert item["status"] == "conflicted_sources" and item["downstream_demand_state"] == "unknown"


def test_unresolved_remains_unknown_without_default():
    item = resolve([])["program_items"][0]
    assert item["status"] == "unresolved_authoritative_input"
    assert item["downstream_demand_state"] == "unknown" and "value" not in item


def test_optional_support_absence_is_not_failure():
    contract = base()
    contract["program_items"][0].update({"id": "storage", "function": "storage"})
    item = resolve([], contract)["program_items"][0]
    assert item["status"] == "unresolved_authoritative_input" and item["program_failure"] is False


def test_unconfirmed_preferred_and_optional_are_not_resolved():
    preferred = evidence(requirement_type="preferred", source_kind="human_preference", confirmation_status="unconfirmed")
    assert resolve([preferred])["program_items"][0]["status"] == "preferred_unconfirmed"
    optional = evidence(requirement_type="optional", confirmation_status="unconfirmed")
    assert resolve([optional])["program_items"][0]["status"] == "optional_unconfirmed"


def test_geometry_and_historical_candidate_data_cannot_leak():
    bad = evidence()
    bad["candidate_id"] = "OLD-7"
    with pytest.raises(ValueError, match="forbidden"):
        resolve([bad])
    bad = evidence()
    bad["geometry"] = {"coordinates": [[0, 0], [1, 1]]}
    with pytest.raises(ValueError, match="forbidden"):
        resolve([bad])


def test_existing_authoritative_item_preserves_traceability():
    item = resolve([], base("authoritative_resolved"))["program_items"][0]
    assert item["status"] == "authoritative_resolved" and item["key"] == "commercial"
