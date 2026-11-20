"""Tests for the bounded ArchitecturalDesignReasoningResultV1 engine."""

import json

import pytest

from core.design.design_reasoning.architectural_design_reasoning_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    reason_architectural_design_v1,
)
from core.design.design_reasoning.architectural_design_reasoning_context_v1 import (
    build_architectural_design_reasoning_context_v1,
)
from core.design.design_reasoning.design_reasoning_input_v1 import (
    build_design_reasoning_input_v1,
)


def _resolution():
    """A real ArchitecturalIntentResolutionV1 carrying two intent groups."""
    return {
        "contract": "ArchitecturalIntentResolutionV1",
        "version": "1.0",
        "intent_groups": [
            {
                "intent_group": "private_sleeping_zone_intent",
                "source_intents": [
                    "sleeping_private_space_intent",
                    "storage_associated_intent",
                    "sanitary_service_associated_intent",
                ],
                "status": "bounded_pattern_group",
                "source_patterns": [
                    "sleeping_storage_relation",
                    "sleeping_sanitary_relation",
                ],
                "evidence_reference": [
                    "sleeping_element",
                    "wardrobe_or_closet",
                    "bathroom_or_ensuite",
                ],
                "uncertainty": [],
            },
            {
                "intent_group": "opening_relationship_intent",
                "source_intents": ["opening_relationship_intent"],
                "status": "bounded_pattern_group",
                "source_patterns": ["opening_associated_with_space"],
                "evidence_reference": ["window"],
                "uncertainty": [],
            },
        ],
        "semantic_components": [
            "private_sleeping_zone_intent",
            "opening_relationship_intent",
        ],
        "source_intents": [
            "sleeping_private_space_intent",
            "storage_associated_intent",
            "sanitary_service_associated_intent",
            "opening_relationship_intent",
        ],
        "evidence_basis": [
            {
                "intent_group": "private_sleeping_zone_intent",
                "source_patterns": [
                    "sleeping_storage_relation",
                    "sleeping_sanitary_relation",
                ],
                "evidence_reference": [
                    "sleeping_element",
                    "wardrobe_or_closet",
                    "bathroom_or_ensuite",
                ],
            },
            {
                "intent_group": "opening_relationship_intent",
                "source_patterns": ["opening_associated_with_space"],
                "evidence_reference": ["window"],
            },
        ],
        "uncertainty": {"matched_groups": 2, "library": {}},
        "non_claims": [],
        "persistent": False,
        "read_only": True,
    }


def _graph():
    """A real ArchitecturalSemanticGraphV1 whose nodes carry both patterns."""
    return {
        "contract": "ArchitecturalSemanticGraphV1",
        "version": "1.0",
        "nodes": [
            {
                "node_id": "sleeping_space_with_storage_association",
                "concept_type": "architectural_concept",
                "semantic_label": "sleeping_space_with_storage_association",
                "source_patterns": ["sleeping_storage_relation"],
                "evidence_reference": ["sleeping_element", "wardrobe_or_closet"],
                "uncertainty": {},
                "status": "bounded_semantic_node",
            },
            {
                "node_id": "sleeping_space_with_sanitary_association",
                "concept_type": "architectural_concept",
                "semantic_label": "sleeping_space_with_sanitary_association",
                "source_patterns": ["sleeping_sanitary_relation"],
                "evidence_reference": ["sleeping_element", "bathroom_or_ensuite"],
                "uncertainty": {},
                "status": "bounded_semantic_node",
            },
            {
                "node_id": "opening_relationship_node",
                "concept_type": "architectural_concept",
                "semantic_label": "opening_relationship_node",
                "source_patterns": ["opening_associated_with_space"],
                "evidence_reference": ["window"],
                "uncertainty": {},
                "status": "bounded_semantic_node",
            },
        ],
        "edges": [],
        "evidence_basis": [],
        "uncertainty": {},
        "non_claims": {},
        "persistent": False,
        "read_only": True,
    }


def _reasoning_input():
    """MUST travel the real pipeline: resolution + graph -> context -> input."""
    context = build_architectural_design_reasoning_context_v1(_resolution(), _graph())
    return build_design_reasoning_input_v1(context)


def test_contract_and_output_shape():
    result = reason_architectural_design_v1(_reasoning_input())

    assert result["contract"] == CONTRACT == "ArchitecturalDesignReasoningResultV1"
    assert result["version"] == VERSION == "1.0"
    assert result["reasoning_statements"]
    assert result["intent_basis"]
    assert result["evidence_basis"]
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_bounded_reasoning_types_and_statements():
    result = reason_architectural_design_v1(_reasoning_input())

    assert [item["type"] for item in result["reasoning_statements"]] == [
        "space_identity_reasoning",
        "functional_relationship_reasoning",
    ]
    assert result["reasoning_statements"][0]["statement"] == (
        "Private sleeping-space semantic context is present."
    )
    assert result["reasoning_statements"][0]["basis"] == [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    ]
    assert result["reasoning_statements"][1]["statement"] == (
        "Opening relationship semantic context is present."
    )


def test_evidence_and_uncertainty_are_preserved():
    reasoning_input = _reasoning_input()
    result = reason_architectural_design_v1(reasoning_input)

    assert result["intent_basis"] == [
        {
            "intent_group": "private_sleeping_zone_intent",
            "source_intents": [
                "sleeping_private_space_intent",
                "storage_associated_intent",
                "sanitary_service_associated_intent",
            ],
            "status": "bounded_pattern_group",
        },
        {
            "intent_group": "opening_relationship_intent",
            "source_intents": ["opening_relationship_intent"],
            "status": "bounded_pattern_group",
        },
    ]
    # The reasoning engine reads its evidence from source_evidence and its
    # uncertainty from the input's uncertainty envelope.
    assert result["evidence_basis"] == reasoning_input["source_evidence"]
    assert result["uncertainty"] == reasoning_input["uncertainty"]
    assert result["reasoning_statements"][0]["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
        "bathroom_or_ensuite",
    ]


def test_deterministic_and_non_mutating():
    reasoning_input = _reasoning_input()
    original = json.loads(json.dumps(reasoning_input))

    first = reason_architectural_design_v1(reasoning_input)
    second = reason_architectural_design_v1(reasoning_input)

    assert first == second
    assert reasoning_input == original


def test_only_reasoning_input_is_accepted():
    with pytest.raises(TypeError):
        reason_architectural_design_v1(None)
    for invalid in (
        {"contract": "ArchitecturalIntentResolutionV1", "version": "1.0"},
        {"contract": "ArchitecturalIntentCandidateV1", "version": "1.0"},
        {"contract": "ArchitecturalSemanticRetrievalResultV1", "version": "1.0"},
    ):
        with pytest.raises(ValueError):
            reason_architectural_design_v1(invalid)


def test_no_design_solution_geometry_or_persistence():
    result = reason_architectural_design_v1(_reasoning_input())
    payload = {
        key: value
        for key, value in result.items()
        if key != "non_claims"
    }
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for term in (
        "should",
        "must",
        "required",
        "optimal",
        "best",
        "recommended",
        "place",
        "move",
        "layout",
        "geometry",
        "dimension",
        "wall",
        "door",
        "window_position",
        "cad",
        "bim",
    ):
        assert term not in serialized
    assert result["non_claims"] == [
        "not_geometry",
        "not_cad",
        "not_bim",
        "not_layout_solution",
        "not_final_design",
    ]
