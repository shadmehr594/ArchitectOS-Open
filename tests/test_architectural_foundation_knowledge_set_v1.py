"""Tests for ArchitecturalFoundationKnowledgeSetV1."""

import json

import pytest

from core.knowledge.foundation.architectural_foundation_knowledge_set_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    build_architectural_foundation_knowledge_set_v1,
)


def _curriculum():
    return {
        "contract": SOURCE_CONTRACT,
        "version": VERSION,
        "curriculum_domain": "foundation_spatial_semantics",
        "learning_cases": [
            {
                "teaching_topic": "bedroom_identity",
                "source_pattern": "bedroom",
                "semantic_area": "space_identity",
                "source_claim_ids": ["claim_space_001"],
                "evidence_reference": ["sleeping_element"],
                "grounding_status": ["visible"],
                "uncertainty": {"unknowns": []},
                "human_explanation": "This is a bounded space identity case.",
            },
            {
                "teaching_topic": "sleeping_storage",
                "source_pattern": "sleeping_storage_relation",
                "semantic_area": "functional_association",
                "source_claim_ids": ["claim_function_001"],
                "evidence_reference": ["sleeping_element", "wardrobe_or_closet"],
                "grounding_status": ["visible"],
                "uncertainty": {"unknowns": []},
                "human_explanation": "This is a bounded functional association case.",
            },
            {
                "teaching_topic": "private_zone",
                "source_pattern": "private_space",
                "semantic_area": "semantic_zone",
                "source_claim_ids": ["claim_zone_001"],
                "evidence_reference": ["sleeping_element"],
                "grounding_status": ["visible"],
                "uncertainty": {"unknowns": ["zone boundary unresolved"]},
                "human_explanation": "This is a bounded semantic zone case.",
            },
        ],
        "semantic_groups": [],
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
        "non_claims": [],
        "persistent": False,
        "read_only": True,
    }


def test_contract_version_domain_and_flags():
    result = build_architectural_foundation_knowledge_set_v1(_curriculum())

    assert result["contract"] == CONTRACT == "ArchitecturalFoundationKnowledgeSetV1"
    assert result["version"] == VERSION == "1.0"
    assert result["knowledge_domain"] == "foundation_spatial_semantics"
    assert result["persistent"] is False
    assert result["read_only"] is True
    assert result["non_claims"] == {
        "not_design_rule": True,
        "not_recommendation": True,
        "not_authoritative_standard": True,
        "not_memory": True,
        "not_learned_model": True,
        "not_design_solution": True,
    }


def test_curriculum_only_input_and_version_validation():
    with pytest.raises(TypeError):
        build_architectural_foundation_knowledge_set_v1(None)
    for invalid in (
        {"contract": "ArchitecturalTeachingRecordV1", "version": "1.0"},
        {"contract": "ArchitecturalKnowledgeCandidateV1", "version": "1.0"},
        {"contract": "ArchitecturalUnderstandingV2", "version": "2.0"},
        {"contract": "ArchitecturalSemanticLibraryCandidateV1", "version": "1.0"},
        {"contract": "ArchitecturalSemanticRetrievalResultV1", "version": "1.0"},
        {"contract": "ArchitecturalDesignReasoningInputV1", "version": "1.0"},
        {"contract": SOURCE_CONTRACT, "version": "2.0"},
    ):
        with pytest.raises(ValueError):
            build_architectural_foundation_knowledge_set_v1(invalid)
    with pytest.raises(ValueError):
        build_architectural_foundation_knowledge_set_v1(
            {"contract": SOURCE_CONTRACT, "version": VERSION, "learning_cases": []}
        )


def test_space_functional_and_zone_grouping():
    result = build_architectural_foundation_knowledge_set_v1(_curriculum())

    assert [case["source_pattern"] for case in result["space_identity_cases"]] == [
        "bedroom"
    ]
    assert [case["source_pattern"] for case in result["functional_relationship_cases"]] == [
        "sleeping_storage_relation"
    ]
    assert [case["source_pattern"] for case in result["semantic_zone_cases"]] == [
        "private_space"
    ]


def test_source_curriculum_evidence_claims_and_uncertainty_preserved():
    curriculum = _curriculum()
    result = build_architectural_foundation_knowledge_set_v1(curriculum)

    assert result["source_curriculum"] == curriculum["learning_cases"]
    assert result["source_evidence"] == curriculum["source_evidence"]
    assert result["uncertainty"] == curriculum["uncertainty"]
    assert result["functional_relationship_cases"][0]["source_claim_ids"] == [
        "claim_function_001"
    ]
    assert result["semantic_zone_cases"][0]["grounding_status"] == ["visible"]


def test_deterministic_and_non_mutating():
    curriculum = _curriculum()
    original = json.loads(json.dumps(curriculum))

    first = build_architectural_foundation_knowledge_set_v1(curriculum)
    second = build_architectural_foundation_knowledge_set_v1(curriculum)

    assert first == second
    assert curriculum == original
    first["space_identity_cases"][0]["source_pattern"] = "changed"
    assert curriculum["learning_cases"][0]["source_pattern"] == "bedroom"


def test_no_forbidden_outputs_or_automatic_learning():
    result = build_architectural_foundation_knowledge_set_v1(_curriculum())
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
        "learned_model",
        "promoted",
    ):
        assert term not in serialized
    assert result["persistent"] is False
