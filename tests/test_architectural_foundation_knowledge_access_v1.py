"""Tests for ArchitecturalFoundationKnowledgeAccessV1."""

import json

import pytest

from core.knowledge.foundation.architectural_foundation_knowledge_access_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    access_architectural_foundation_knowledge_v1,
)


def _foundation():
    return {
        "contract": SOURCE_CONTRACT,
        "version": VERSION,
        "knowledge_domain": "foundation_spatial_semantics",
        "space_identity_cases": [
            {
                "teaching_topic": "bedroom_identity",
                "source_pattern": "bedroom",
                "semantic_area": "space_identity",
                "source_claim_ids": ["claim_space_001"],
                "evidence_reference": ["sleeping_element"],
                "grounding_status": ["visible"],
                "uncertainty": {"unknowns": []},
            }
        ],
        "functional_relationship_cases": [
            {
                "teaching_topic": "sleeping_storage",
                "source_pattern": "sleeping_storage_relation",
                "semantic_area": "functional_association",
                "source_claim_ids": ["claim_function_001"],
                "evidence_reference": ["sleeping_element", "wardrobe_or_closet"],
                "grounding_status": ["visible"],
                "uncertainty": {"unknowns": []},
            }
        ],
        "semantic_zone_cases": [
            {
                "teaching_topic": "private_zone",
                "source_pattern": "private_space",
                "semantic_area": "semantic_zone",
                "source_claim_ids": ["claim_zone_001"],
                "evidence_reference": ["sleeping_element"],
                "grounding_status": ["visible"],
                "uncertainty": {"unknowns": ["zone boundary unresolved"]},
            }
        ],
        "source_curriculum": [],
        "source_evidence": [
            {
                "source_pattern": "bedroom",
                "source_claim_ids": ["claim_space_001"],
                "evidence_reference": ["sleeping_element"],
                "grounding_status": ["visible"],
            },
            {
                "source_pattern": "sleeping_storage_relation",
                "source_claim_ids": ["claim_function_001"],
                "evidence_reference": ["sleeping_element", "wardrobe_or_closet"],
                "grounding_status": ["visible"],
            },
            {
                "source_pattern": "private_space",
                "source_claim_ids": ["claim_zone_001"],
                "evidence_reference": ["sleeping_element"],
                "grounding_status": ["visible"],
            },
        ],
        "uncertainty": {
            "session": {"record_count": 3},
            "records": [{"unknowns": []}, {"unknowns": []}, {"unknowns": ["zone boundary unresolved"]}],
        },
        "non_claims": {},
        "persistent": False,
        "read_only": True,
    }


def test_contract_and_valid_foundation_input():
    result = access_architectural_foundation_knowledge_v1(
        _foundation(), {"area": "functional_relationship"}
    )

    assert result["contract"] == CONTRACT == "ArchitecturalFoundationKnowledgeAccessV1"
    assert result["version"] == VERSION == "1.0"
    assert result["matches"]
    assert result["matches"][0]["knowledge_area"] == "functional_relationship"
    assert result["matches"][0]["status"] == "bounded_access_match"
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_lookup_by_area_and_pattern():
    foundation = _foundation()
    by_pattern = access_architectural_foundation_knowledge_v1(
        foundation, {"pattern": "sleeping_storage_relation"}
    )
    assert len(by_pattern["matches"]) == 1
    assert by_pattern["matches"][0]["source_patterns"] == [
        "sleeping_storage_relation"
    ]

    by_area = access_architectural_foundation_knowledge_v1(
        foundation, {"knowledge_area": "space_identity"}
    )
    assert by_area["matches"][0]["source_patterns"] == ["bedroom"]


def test_evidence_claims_grounding_and_uncertainty_are_preserved():
    foundation = _foundation()
    result = access_architectural_foundation_knowledge_v1(foundation, {})

    assert result["source_evidence"] == foundation["source_evidence"]
    assert result["uncertainty"] == foundation["uncertainty"]
    function_match = result["matches"][1]
    assert function_match["source_cases"][0]["source_claim_ids"] == [
        "claim_function_001"
    ]
    assert function_match["source_cases"][0]["grounding_status"] == ["visible"]
    assert function_match["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
    ]


def test_deterministic_and_non_mutating():
    foundation = _foundation()
    original = json.loads(json.dumps(foundation))

    first = access_architectural_foundation_knowledge_v1(foundation, {})
    second = access_architectural_foundation_knowledge_v1(foundation, {})

    assert first == second
    assert foundation == original
    first["matches"][0]["source_cases"][0]["source_pattern"] = "changed"
    assert foundation["space_identity_cases"][0]["source_pattern"] == "bedroom"


def test_invalid_contract_and_version_rejection():
    with pytest.raises(TypeError):
        access_architectural_foundation_knowledge_v1(None, {})
    for invalid in (
        {"contract": "ArchitecturalKnowledgeCurriculumV1", "version": "1.0"},
        {"contract": "ArchitecturalTeachingRecordV1", "version": "1.0"},
        {"contract": "ArchitecturalSemanticLibraryCandidateV1", "version": "1.0"},
        {"contract": SOURCE_CONTRACT, "version": "2.0"},
    ):
        with pytest.raises(ValueError):
            access_architectural_foundation_knowledge_v1(invalid, {})


def test_no_forbidden_language_or_design_leakage():
    result = access_architectural_foundation_knowledge_v1(_foundation(), {})
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
        "design_rule",
        "layout_rule",
        "placement",
        "geometry",
        "dimension",
        "cad",
        "bim",
        "ifc",
    ):
        assert term not in serialized
    assert result["non_claims"] == {
        "not_design_rule": True,
        "not_recommendation": True,
        "not_authoritative_knowledge": True,
        "not_memory": True,
        "not_learned_model": True,
        "not_design_solution": True,
    }
