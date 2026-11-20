"""Tests for ArchitecturalSemanticRetrievalResultV1."""

import json

import pytest

from core.knowledge.architectural_semantic_library_v1 import (
    build_architectural_semantic_library_candidate_v1,
)
from core.knowledge.architectural_semantic_retrieval_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    retrieve_architectural_semantic_patterns_v1,
)
from core.teaching.architectural_teaching_record_v1 import (
    build_architectural_teaching_record_v1,
)
from core.teaching.architectural_teaching_session_v1 import (
    build_architectural_teaching_session_v1,
)


def _record(topic, pattern, evidence, claim_id):
    record = build_architectural_teaching_record_v1(
        {
            "contract": "ArchitecturalTeachingCandidateV1",
            "version": "1.0",
            "teaching_units": [
                {
                    "topic": topic,
                    "source_pattern": pattern,
                    "evidence_reference": evidence,
                    "source_claim_ids": [claim_id],
                    "grounding_status": ["visible"],
                    "uncertainty": {"unknowns": [], "evidence_conflicts": []},
                }
            ],
            "uncertainty": {
                "confidence": "bounded",
                "unknowns": [],
                "evidence_conflicts": [],
            },
        },
        "This is a bounded human explanation of an observed association.",
    )
    record["source_claim_ids"] = [claim_id]
    record["grounding_status"] = ["visible"]
    return record


def _library():
    session = build_architectural_teaching_session_v1(
        [
            _record(
                "sleeping_space_and_storage_association",
                "sleeping_storage_relation",
                ["sleeping_element", "wardrobe_or_closet"],
                "au2_claim_001",
            ),
            _record(
                "sleeping_space_and_sanitary_service_association",
                "sleeping_sanitary_relation",
                ["sleeping_element", "bathroom_or_ensuite"],
                "au2_claim_002",
            ),
        ]
    )
    return build_architectural_semantic_library_candidate_v1(session)


def test_contract_and_version():
    result = retrieve_architectural_semantic_patterns_v1(
        _library(), "sleeping_space_association"
    )
    assert result["contract"] == CONTRACT == "ArchitecturalSemanticRetrievalResultV1"
    assert result["version"] == VERSION == "1.0"
    assert result["persistent"] is False


def test_matching_by_semantic_group():
    result = retrieve_architectural_semantic_patterns_v1(
        _library(), {"semantic_group": "sleeping_space_association"}
    )
    assert len(result["matches"]) == 1
    match = result["matches"][0]
    assert match["semantic_group"] == "sleeping_space_association"
    assert match["matched_patterns"] == [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    ]
    assert match["status"] == "semantic_match"


def test_matching_by_pattern():
    result = retrieve_architectural_semantic_patterns_v1(
        _library(), {"pattern": "sleeping_storage_relation"}
    )
    assert len(result["matches"]) == 1
    match = result["matches"][0]
    assert match["matched_patterns"] == ["sleeping_storage_relation"]
    assert match["status"] == "bounded_match"


def test_unresolved_query_returns_no_matches_without_inference():
    result = retrieve_architectural_semantic_patterns_v1(
        _library(), {"pattern": "place_bed"}
    )
    assert result["matches"] == []
    assert result["evidence_basis"] == []
    assert result["uncertainty"]["matched_groups"] == 0


def test_evidence_and_uncertainty_are_preserved():
    library = _library()
    result = retrieve_architectural_semantic_patterns_v1(
        library, "sleeping_storage_relation"
    )
    match = result["matches"][0]
    assert match["source_evidence"] == [
        "sleeping_element",
        "wardrobe_or_closet",
        "bathroom_or_ensuite",
    ]
    assert match["uncertainty"] == library["semantic_groups"][0]["uncertainty"]
    assert result["evidence_basis"][0]["source_evidence"] == match["source_evidence"]
    assert result["uncertainty"]["library"] == library["uncertainty"]


def test_deterministic_and_non_mutating():
    library = _library()
    original = json.loads(json.dumps(library))
    first = retrieve_architectural_semantic_patterns_v1(library, "sleeping_space_association")
    second = retrieve_architectural_semantic_patterns_v1(library, "sleeping_space_association")
    assert first == second
    assert library == original


def test_retrieval_input_validation():
    with pytest.raises(TypeError):
        retrieve_architectural_semantic_patterns_v1(None, "sleeping_storage_relation")
    for invalid in (
        {"contract": "ArchitecturalTeachingRecordV1", "version": "1.0"},
        {"contract": "ArchitecturalKnowledgeCandidateV1", "version": "1.0"},
        {"contract": "ArchitecturalVisionInterpreterV1", "version": "1.0"},
    ):
        with pytest.raises(ValueError):
            retrieve_architectural_semantic_patterns_v1(invalid, "sleeping_storage_relation")


def test_no_forbidden_design_language_or_memory():
    result = retrieve_architectural_semantic_patterns_v1(
        _library(), "sleeping_storage_relation"
    )
    payload = {key: value for key, value in result.items() if key != "non_claims"}
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for term in (
        "should",
        "must",
        "required",
        "optimal",
        "best",
        "recommended",
        "design_solution",
        "memory",
    ):
        assert term not in serialized
    assert result["non_claims"] == [
        "not_design_reasoning",
        "not_recommendation",
        "not_rule",
        "not_geometry",
    ]
