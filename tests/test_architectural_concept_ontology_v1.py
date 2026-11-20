"""Tests for ArchitecturalConceptOntologyV1."""

import json

import pytest

from core.knowledge.foundation.architectural_concept_ontology_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    build_architectural_concept_ontology_v1,
)


def _relationships():
    return {
        "contract": SOURCE_CONTRACT,
        "version": VERSION,
        "relationships": [
            {
                "relationship_type": "private_sleeping_concept_context",
                "related_concepts": [
                    "sleeping_space_with_storage_association",
                    "sleeping_space_with_sanitary_association",
                ],
                "source_patterns": [
                    "sleeping_storage_relation",
                    "sleeping_sanitary_relation",
                ],
                "evidence_reference": [
                    "sleeping_element",
                    "wardrobe_or_closet",
                    "bathroom_or_ensuite",
                ],
                "uncertainty": [{"unknowns": ["service relation unresolved"]}],
                "status": "bounded_concept_relationship",
            }
        ],
        "source_concepts": [
            {
                "semantic_label": "sleeping_space_with_storage_association",
                "source_patterns": ["sleeping_storage_relation"],
            },
            {
                "semantic_label": "sleeping_space_with_sanitary_association",
                "source_patterns": ["sleeping_sanitary_relation"],
            },
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
        "uncertainty": {"matched_concepts": 2},
        "non_claims": {},
        "persistent": False,
        "read_only": True,
    }


def test_contract_and_valid_relationship_input():
    result = build_architectural_concept_ontology_v1(_relationships())

    assert result["contract"] == CONTRACT == "ArchitecturalConceptOntologyV1"
    assert result["version"] == VERSION == "1.0"
    assert result["concept_nodes"]
    assert result["relationship_edges"]
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_concept_nodes_are_created_from_relationships():
    result = build_architectural_concept_ontology_v1(_relationships())

    assert [node["concept_id"] for node in result["concept_nodes"]] == [
        "sleeping_space_with_storage_association",
        "sleeping_space_with_sanitary_association",
    ]
    assert all(node["status"] == "bounded_concept_node" for node in result["concept_nodes"])
    assert result["concept_nodes"][0]["source_relationships"] == [
        "private_sleeping_concept_context"
    ]


def test_relationship_edges_and_source_data_are_preserved():
    relationships = _relationships()
    result = build_architectural_concept_ontology_v1(relationships)

    assert result["relationship_edges"] == [
        {
            "relationship_type": "private_sleeping_concept_context",
            "source_concepts": [
                "sleeping_space_with_storage_association",
                "sleeping_space_with_sanitary_association",
            ],
            "status": "bounded_relationship_edge",
        }
    ]
    assert result["evidence_basis"] == relationships["evidence_basis"]
    assert result["uncertainty"] == relationships["uncertainty"]
    assert result["concept_nodes"][0]["source_patterns"] == [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    ]
    assert result["concept_nodes"][0]["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
        "bathroom_or_ensuite",
    ]


def test_deterministic_and_non_mutating():
    relationships = _relationships()
    original = json.loads(json.dumps(relationships))

    first = build_architectural_concept_ontology_v1(relationships)
    second = build_architectural_concept_ontology_v1(relationships)

    assert first == second
    assert relationships == original
    first["concept_nodes"][0]["semantic_label"] = "changed"
    assert relationships["source_concepts"][0]["semantic_label"] == (
        "sleeping_space_with_storage_association"
    )


def test_invalid_contract_and_version_rejection():
    with pytest.raises(TypeError):
        build_architectural_concept_ontology_v1(None)
    for invalid in (
        {"contract": "ArchitecturalConceptUnderstandingV1", "version": "1.0"},
        {"contract": "ArchitecturalConceptRelationshipV1", "version": "2.0"},
        {"contract": "ArchitecturalFoundationKnowledgeSetV1", "version": "1.0"},
    ):
        with pytest.raises(ValueError):
            build_architectural_concept_ontology_v1(invalid)


def test_no_forbidden_language_or_persistence():
    result = build_architectural_concept_ontology_v1(_relationships())
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
