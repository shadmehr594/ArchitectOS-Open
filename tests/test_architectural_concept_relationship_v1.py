"""Tests for ArchitecturalConceptRelationshipV1."""

import json

import pytest

from core.knowledge.foundation.architectural_concept_relationship_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    build_architectural_concept_relationship_v1,
)


def _concept_understanding():
    return {
        "contract": SOURCE_CONTRACT,
        "version": VERSION,
        "concepts": [
            {
                "concept_type": "functional_association_concept",
                "semantic_label": "sleeping_space_with_storage_association",
                "source_patterns": ["sleeping_storage_relation"],
                "evidence_reference": ["sleeping_element", "wardrobe_or_closet"],
                "uncertainty": [],
                "status": "bounded_concept_understanding",
            },
            {
                "concept_type": "functional_association_concept",
                "semantic_label": "sleeping_space_with_sanitary_association",
                "source_patterns": ["sleeping_sanitary_relation"],
                "evidence_reference": ["sleeping_element", "bathroom_or_ensuite"],
                "uncertainty": [{"unknowns": ["service relation unresolved"]}],
                "status": "bounded_concept_understanding",
            },
        ],
        "source_patterns": [
            "sleeping_storage_relation",
            "sleeping_sanitary_relation",
        ],
        "evidence_basis": [
            {
                "source_pattern": "sleeping_storage_relation",
                "evidence_reference": ["sleeping_element", "wardrobe_or_closet"],
            },
            {
                "source_pattern": "sleeping_sanitary_relation",
                "evidence_reference": ["sleeping_element", "bathroom_or_ensuite"],
            },
        ],
        "uncertainty": {"matched_groups": 2},
        "non_claims": {},
        "persistent": False,
        "read_only": True,
    }


def test_contract_and_valid_input():
    result = build_architectural_concept_relationship_v1(_concept_understanding())

    assert result["contract"] == CONTRACT == "ArchitecturalConceptRelationshipV1"
    assert result["version"] == VERSION == "1.0"
    assert result["relationships"]
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_private_sleeping_relationship_extraction():
    result = build_architectural_concept_relationship_v1(_concept_understanding())
    relationship = result["relationships"][0]

    assert relationship["relationship_type"] == "private_sleeping_concept_context"
    assert relationship["related_concepts"] == [
        "sleeping_space_with_storage_association",
        "sleeping_space_with_sanitary_association",
    ]
    assert relationship["source_patterns"] == [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    ]
    assert relationship["status"] == "bounded_concept_relationship"


def test_source_concepts_evidence_and_uncertainty_are_preserved():
    understanding = _concept_understanding()
    result = build_architectural_concept_relationship_v1(understanding)
    relationship = result["relationships"][0]

    assert result["source_concepts"] == understanding["concepts"]
    assert result["evidence_basis"] == understanding["evidence_basis"]
    assert result["uncertainty"] == understanding["uncertainty"]
    assert relationship["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
        "bathroom_or_ensuite",
    ]
    assert relationship["uncertainty"] == [
        [{"unknowns": ["service relation unresolved"]}]
    ]


def test_movement_and_boundary_relationships():
    base = _concept_understanding()
    base["concepts"] = [
        {
            "semantic_label": "circulation_related_semantic_context",
            "source_patterns": ["circulation_connection_relation"],
            "evidence_reference": ["entrance"],
            "uncertainty": [],
        },
        {
            "semantic_label": "opening_related_semantic_context",
            "source_patterns": ["opening_space_relation"],
            "evidence_reference": ["window"],
            "uncertainty": [],
        },
    ]
    result = build_architectural_concept_relationship_v1(base)

    assert [item["relationship_type"] for item in result["relationships"]] == [
        "movement_related_concept_context",
    ]

    opening_only = dict(base)
    opening_only["concepts"] = [base["concepts"][1]]
    opening_result = build_architectural_concept_relationship_v1(opening_only)
    assert opening_result["relationships"][0]["relationship_type"] == (
        "boundary_connection_concept_context"
    )


def test_deterministic_and_non_mutating():
    understanding = _concept_understanding()
    original = json.loads(json.dumps(understanding))

    first = build_architectural_concept_relationship_v1(understanding)
    second = build_architectural_concept_relationship_v1(understanding)

    assert first == second
    assert understanding == original
    first["source_concepts"][0]["semantic_label"] = "changed"
    assert understanding["concepts"][0]["semantic_label"] == (
        "sleeping_space_with_storage_association"
    )


def test_invalid_contract_and_version_rejection():
    with pytest.raises(TypeError):
        build_architectural_concept_relationship_v1(None)
    for invalid in (
        {"contract": "ArchitecturalFoundationKnowledgeAccessV1", "version": "1.0"},
        {"contract": "ArchitecturalKnowledgeCurriculumV1", "version": "1.0"},
        {"contract": "ArchitecturalConceptUnderstandingV1", "version": "2.0"},
    ):
        with pytest.raises(ValueError):
            build_architectural_concept_relationship_v1(invalid)


def test_no_forbidden_language_or_persistence():
    result = build_architectural_concept_relationship_v1(_concept_understanding())
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
