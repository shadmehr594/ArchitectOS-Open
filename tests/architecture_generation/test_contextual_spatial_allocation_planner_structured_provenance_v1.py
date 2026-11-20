from copy import deepcopy

from core.architecture.reasoning.contextual_spatial_allocation_planner_v1 import _stable_unique_provenance


def test_scalar_provenance_is_supported_and_deduplicated_stably():
    assert _stable_unique_provenance(["b", "a", "b", 3, 3]) == ["b", "a", 3]


def test_dict_provenance_preserves_complete_record_structure():
    record = {"contract": "EvidenceV1", "path": "requirements.parking"}
    assert _stable_unique_provenance([record]) == [record]
    assert isinstance(_stable_unique_provenance([record])[0], dict)


def test_nested_dict_and_list_provenance_is_supported():
    record = {"contract": "EvidenceV1", "sources": [{"path": ["a", 1]}, {"flags": [True, None]}]}
    assert _stable_unique_provenance([record]) == [record]


def test_duplicate_structured_records_are_removed_by_complete_semantics():
    first = {"contract": "EvidenceV1", "meta": {"confidence": 1, "paths": ["a", "b"]}}
    same_with_different_key_order = {"meta": {"paths": ["a", "b"], "confidence": 1}, "contract": "EvidenceV1"}
    assert _stable_unique_provenance([first, same_with_different_key_order]) == [first]


def test_first_seen_order_is_deterministic():
    records = [{"id": 2}, "alpha", {"id": 1}, {"id": 2}, "alpha"]
    expected = [{"id": 2}, "alpha", {"id": 1}]
    assert _stable_unique_provenance(records) == expected
    assert _stable_unique_provenance(records) == expected


def test_semantically_distinct_records_are_preserved():
    records = [
        {"contract": "EvidenceV1", "path": "a", "confidence": 0.8},
        {"contract": "EvidenceV1", "path": "a", "confidence": 0.9},
        {"contract": "EvidenceV1", "path": "b", "confidence": 0.8},
    ]
    assert _stable_unique_provenance(records) == records


def test_input_provenance_is_not_mutated_or_aliased():
    records = [{"contract": "EvidenceV1", "nested": {"paths": ["a", "b"]}}]
    before = deepcopy(records)
    result = _stable_unique_provenance(records)
    assert records == before
    result[0]["nested"]["paths"].append("changed")
    assert records == before
