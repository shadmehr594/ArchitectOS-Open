"""Tests for ArchitecturalSemanticGraphV1."""

import json

import pytest

from core.knowledge.foundation.architectural_semantic_graph_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    build_architectural_semantic_graph_v1,
)


def _ontology():
    return {
        "contract": SOURCE_CONTRACT,
        "version": VERSION,
        "concept_nodes": [
            {
                "concept_id": "sleeping_space_with_storage_association",
                "semantic_label": "sleeping_space_with_storage_association",
                "source_relationships": ["private_sleeping_concept_context"],
                "source_patterns": ["sleeping_storage_relation"],
                "evidence_reference": ["sleeping_element", "wardrobe_or_closet"],
                "uncertainty": [],
                "status": "bounded_concept_node",
            },
            {
                "concept_id": "sleeping_space_with_sanitary_association",
                "semantic_label": "sleeping_space_with_sanitary_association",
                "source_relationships": ["private_sleeping_concept_context"],
                "source_patterns": ["sleeping_sanitary_relation"],
                "evidence_reference": ["sleeping_element", "bathroom_or_ensuite"],
                "uncertainty": [{"unknowns": ["service unresolved"]}],
                "status": "bounded_concept_node",
            },
        ],
        "relationship_edges": [
            {
                "relationship_type": "private_sleeping_concept_context",
                "source_concepts": [
                    "sleeping_space_with_storage_association",
                    "sleeping_space_with_sanitary_association",
                ],
                "status": "bounded_relationship_edge",
            }
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


def test_contract_and_valid_ontology_input():
    result = build_architectural_semantic_graph_v1(_ontology())

    assert result["contract"] == CONTRACT == "ArchitecturalSemanticGraphV1"
    assert result["version"] == VERSION == "1.0"
    assert result["nodes"]
    assert result["edges"]
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_node_generation_preserves_ontology_nodes():
    result = build_architectural_semantic_graph_v1(_ontology())

    assert [node["node_id"] for node in result["nodes"]] == [
        "sleeping_space_with_storage_association",
        "sleeping_space_with_sanitary_association",
    ]
    assert all(node["concept_type"] == "architectural_concept" for node in result["nodes"])
    assert all(node["status"] == "bounded_semantic_node" for node in result["nodes"])
    assert result["nodes"][0]["source_patterns"] == ["sleeping_storage_relation"]
    assert result["nodes"][0]["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
    ]


def test_edge_generation_and_source_preservation():
    ontology = _ontology()
    result = build_architectural_semantic_graph_v1(ontology)

    assert result["edges"] == [
        {
            "edge_type": "private_sleeping_concept_context",
            "source_node": "sleeping_space_with_storage_association",
            "target_node": "sleeping_space_with_sanitary_association",
            "status": "bounded_semantic_edge",
        }
    ]
    assert result["evidence_basis"] == ontology["evidence_basis"]
    assert result["uncertainty"] == ontology["uncertainty"]
    assert result["nodes"][1]["uncertainty"] == [
        {"unknowns": ["service unresolved"]}
    ]


def test_deterministic_and_non_mutating():
    ontology = _ontology()
    original = json.loads(json.dumps(ontology))

    first = build_architectural_semantic_graph_v1(ontology)
    second = build_architectural_semantic_graph_v1(ontology)

    assert first == second
    assert ontology == original
    first["nodes"][0]["semantic_label"] = "changed"
    assert ontology["concept_nodes"][0]["semantic_label"] == (
        "sleeping_space_with_storage_association"
    )


def test_invalid_contract_and_version_rejection():
    with pytest.raises(TypeError):
        build_architectural_semantic_graph_v1(None)
    for invalid in (
        {"contract": "ArchitecturalConceptOntologyV1", "version": "2.0"},
        {"contract": "ArchitecturalConceptRelationshipV1", "version": "1.0"},
        {"contract": "ArchitecturalConceptUnderstandingV1", "version": "1.0"},
    ):
        with pytest.raises(ValueError):
            build_architectural_semantic_graph_v1(invalid)


def test_no_forbidden_language_or_persistence():
    result = build_architectural_semantic_graph_v1(_ontology())
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
