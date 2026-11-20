"""Tests for ArchitecturalSpatialReasoningCandidateV1."""

import json

import pytest

from core.design.design_reasoning.architectural_design_reasoning_v1 import (
    reason_architectural_design_v1,
)
from core.design.spatial_reasoning.architectural_spatial_reasoning_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    build_spatial_reasoning_candidate_v1,
)


def _reasoning_result():
    return reason_architectural_design_v1(
        {
            "contract": "ArchitecturalDesignReasoningInputV1",
            "version": "1.0",
            "intent_context": [
                {
                    "intent_group": "private_sleeping_zone_intent",
                    "source_intents": ["sleeping_private_space_intent"],
                    "status": "bounded_pattern_group",
                },
                {
                    "intent_group": "opening_relationship_intent",
                    "source_intents": ["opening_relationship_intent"],
                    "status": "bounded_pattern_group",
                },
            ],
            "semantic_context": [],
            "source_evidence": [
                {
                    "intent_group": "private_sleeping_zone_intent",
                    "source_patterns": ["sleeping_storage_relation"],
                    "evidence_reference": [
                        "sleeping_element",
                        "wardrobe_or_closet",
                    ],
                },
                {
                    "intent_group": "opening_relationship_intent",
                    "source_patterns": ["opening_associated_with_space"],
                    "evidence_reference": ["window"],
                },
            ],
            "uncertainty": {
                "matched_groups": 2,
                "library": {},
            },
            "open_questions": [],
            "non_claims": [],
            "persistent": False,
            "read_only": True,
        }
    )


def test_contract_and_output_shape():
    result = build_spatial_reasoning_candidate_v1(_reasoning_result())

    assert result["contract"] == CONTRACT == "ArchitecturalSpatialReasoningCandidateV1"
    assert result["version"] == VERSION == "1.0"
    assert result["spatial_candidates"]
    assert result["reasoning_basis"]
    assert result["evidence_basis"]
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_supported_spatial_candidate_mapping():
    result = build_spatial_reasoning_candidate_v1(_reasoning_result())

    assert [item["spatial_domain"] for item in result["spatial_candidates"]] == [
        "private_sleeping_zone",
        "opening_related_zone",
    ]
    assert all(
        item["status"] == "bounded_spatial_candidate"
        for item in result["spatial_candidates"]
    )
    assert result["spatial_candidates"][0]["source_reasoning"] == [
        "space_identity_reasoning"
    ]
    assert result["spatial_candidates"][1]["source_reasoning"] == [
        "functional_relationship_reasoning"
    ]


def test_evidence_and_uncertainty_are_preserved():
    reasoning_result = _reasoning_result()
    result = build_spatial_reasoning_candidate_v1(reasoning_result)

    assert result["reasoning_basis"] == reasoning_result["intent_basis"]
    assert result["evidence_basis"] == reasoning_result["evidence_basis"]
    assert result["uncertainty"] == reasoning_result["uncertainty"]
    assert result["spatial_candidates"][0]["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
    ]
    assert result["spatial_candidates"][1]["evidence_reference"] == ["window"]


def test_deterministic_and_non_mutating():
    reasoning_result = _reasoning_result()
    original = json.loads(json.dumps(reasoning_result))

    first = build_spatial_reasoning_candidate_v1(reasoning_result)
    second = build_spatial_reasoning_candidate_v1(reasoning_result)

    assert first == second
    assert reasoning_result == original


def test_reasoning_only_input_validation():
    with pytest.raises(TypeError):
        build_spatial_reasoning_candidate_v1(None)
    for invalid in (
        {"contract": "ArchitecturalDesignReasoningInputV1", "version": "1.0"},
        {"contract": "ArchitecturalIntentResolutionV1", "version": "1.0"},
        {"contract": "ArchitecturalIntentCandidateV1", "version": "1.0"},
    ):
        with pytest.raises(ValueError):
            build_spatial_reasoning_candidate_v1(invalid)


def test_no_layout_geometry_or_cad_bim_leakage():
    result = build_spatial_reasoning_candidate_v1(_reasoning_result())
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
        "adjacent",
        "layout",
        "dimension",
        "geometry",
        "cad",
        "bim",
        "ifc",
    ):
        assert term not in serialized
    assert result["non_claims"] == [
        "not_layout",
        "not_placement",
        "not_geometry",
        "not_cad",
        "not_bim",
    ]
