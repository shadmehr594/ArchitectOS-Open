"""Tests for ArchitecturalConceptUnderstandingV1."""

import json

import pytest

from core.knowledge.foundation.architectural_concept_understanding_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    build_architectural_concept_understanding_v1,
)


def _access_result():
    return {
        "contract": SOURCE_CONTRACT,
        "version": VERSION,
        "matches": [
            {
                "knowledge_area": "functional_relationship",
                "source_cases": [
                    {
                        "source_pattern": "sleeping_storage_relation",
                        "source_claim_ids": ["claim_function_001"],
                        "evidence_reference": [
                            "sleeping_element",
                            "wardrobe_or_closet",
                        ],
                        "grounding_status": ["visible"],
                    }
                ],
                "source_patterns": ["sleeping_storage_relation"],
                "evidence_reference": [
                    "sleeping_element",
                    "wardrobe_or_closet",
                ],
                "uncertainty": [],
                "status": "bounded_access_match",
            },
            {
                "knowledge_area": "functional_relationship",
                "source_cases": [
                    {
                        "source_pattern": "sleeping_sanitary_relation",
                        "source_claim_ids": ["claim_function_002"],
                        "evidence_reference": [
                            "sleeping_element",
                            "bathroom_or_ensuite",
                        ],
                        "grounding_status": ["visible"],
                    }
                ],
                "source_patterns": ["sleeping_sanitary_relation"],
                "evidence_reference": [
                    "sleeping_element",
                    "bathroom_or_ensuite",
                ],
                "uncertainty": [{"unknowns": ["service relation unresolved"]}],
                "status": "bounded_access_match",
            },
        ],
        "source_evidence": [
            {
                "source_pattern": "sleeping_storage_relation",
                "source_claim_ids": ["claim_function_001"],
                "evidence_reference": [
                    "sleeping_element",
                    "wardrobe_or_closet",
                ],
                "grounding_status": ["visible"],
            },
            {
                "source_pattern": "sleeping_sanitary_relation",
                "source_claim_ids": ["claim_function_002"],
                "evidence_reference": [
                    "sleeping_element",
                    "bathroom_or_ensuite",
                ],
                "grounding_status": ["visible"],
            },
        ],
        "uncertainty": {
            "matched_groups": 2,
            "library": {},
        },
        "non_claims": {},
        "persistent": False,
        "read_only": True,
    }


def test_valid_access_contract_and_output():
    result = build_architectural_concept_understanding_v1(_access_result())

    assert result["contract"] == CONTRACT == "ArchitecturalConceptUnderstandingV1"
    assert result["version"] == VERSION == "1.0"
    assert result["concepts"]
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_concept_extraction_and_labels():
    result = build_architectural_concept_understanding_v1(_access_result())

    assert [concept["concept_type"] for concept in result["concepts"]] == [
        "functional_association_concept",
        "functional_association_concept",
    ]
    assert [concept["semantic_label"] for concept in result["concepts"]] == [
        "sleeping_space_with_storage_association",
        "sleeping_space_with_sanitary_association",
    ]
    assert all(
        concept["status"] == "bounded_concept_understanding"
        for concept in result["concepts"]
    )


def test_source_patterns_evidence_and_uncertainty_are_preserved():
    access = _access_result()
    result = build_architectural_concept_understanding_v1(access)

    assert result["source_patterns"] == [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    ]
    assert result["evidence_basis"] == access["source_evidence"]
    assert result["uncertainty"] == access["uncertainty"]
    assert result["concepts"][0]["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
    ]
    assert result["concepts"][1]["uncertainty"] == [
        {"unknowns": ["service relation unresolved"]}
    ]


def test_deterministic_and_non_mutating():
    access = _access_result()
    original = json.loads(json.dumps(access))

    first = build_architectural_concept_understanding_v1(access)
    second = build_architectural_concept_understanding_v1(access)

    assert first == second
    assert access == original
    first["concepts"][0]["semantic_label"] = "changed"
    assert access["matches"][0]["source_patterns"] == [
        "sleeping_storage_relation"
    ]


def test_invalid_contract_and_version_rejection():
    with pytest.raises(TypeError):
        build_architectural_concept_understanding_v1(None)
    for invalid in (
        {"contract": "ArchitecturalFoundationKnowledgeSetV1", "version": "1.0"},
        {"contract": "ArchitecturalKnowledgeCurriculumV1", "version": "1.0"},
        {"contract": "ArchitecturalSemanticRetrievalResultV1", "version": "1.0"},
        {"contract": SOURCE_CONTRACT, "version": "2.0"},
    ):
        with pytest.raises(ValueError):
            build_architectural_concept_understanding_v1(invalid)


def test_boundary_flags_and_forbidden_language():
    result = build_architectural_concept_understanding_v1(_access_result())
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
