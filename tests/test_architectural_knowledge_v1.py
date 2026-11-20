"""Tests for the transient ArchitecturalKnowledgeCandidateV1 layer."""

import json

import pytest

from core.knowledge.architectural_knowledge_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    build_architectural_knowledge_candidate_v1,
)
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)


FORBIDDEN = (
    "should",
    "must",
    "required",
    "optimized",
    "best",
    "recommended",
    "design solution",
    "geometry_generation",
    "cad_operation",
    "bim_operation",
    "ifc_operation",
    "render_call",
    "comfyui_call",
)


def _master_v2():
    interpretation = interpret_architectural_vision(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["bed visible", "wardrobe visible", "bathroom visible"],
            "inferred": [],
            "unresolved": [],
            "confidence": "MEDIUM",
            "architectural_elements": ["bed", "wardrobe", "bathroom"],
        }
    )
    return interpretation["architectural_understanding_v2"]


def test_candidate_identity_and_v2_only_input():
    candidate = build_architectural_knowledge_candidate_v1(_master_v2())

    assert candidate["contract"] == CONTRACT == "ArchitecturalKnowledgeCandidateV1"
    assert candidate["version"] == VERSION == "1.0"
    assert candidate["source"]["contract"] == SOURCE_CONTRACT
    assert candidate["source"]["version"] == "2.0"
    assert candidate["status"] == "candidate"
    assert candidate["candidate_type"] == "derived_pattern"

    with pytest.raises(TypeError):
        build_architectural_knowledge_candidate_v1(None)
    with pytest.raises(ValueError):
        build_architectural_knowledge_candidate_v1({"contract": "ArchitecturalVisionInterpreterV1"})


def test_master_bedroom_extracts_bounded_patterns_and_associations():
    candidate = build_architectural_knowledge_candidate_v1(_master_v2())

    assert {item["pattern"] for item in candidate["patterns"]} == {
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    }
    assert {item["element"] for item in candidate["element_associations"]} == {
        "wardrobe_or_closet",
        "bathroom_or_ensuite",
    }
    assert {item["association"] for item in candidate["element_associations"]} == {
        "storage_associated",
        "sanitary_service_associated",
    }
    assert candidate["space_associations"][0]["space"] == "master bedroom"
    assert candidate["space_associations"][0]["status"] == "bounded_association"


def test_evidence_chain_is_preserved_from_v2_claims():
    v2 = _master_v2()
    candidate = build_architectural_knowledge_candidate_v1(v2)
    chain = candidate["evidence_chain"]

    assert chain["source_contract"] == "ArchitecturalUnderstandingV2"
    assert chain["source_version"] == "2.0"
    assert chain["claim_ids"] == [
        claim["claim_id"] for claim in v2["claim_trace"]
    ]
    assert chain["source_evidence"]
    assert chain["grounding_status"]
    assert chain["interpretation_basis"]
    assert chain["uncertainty"] == v2["uncertainty"]

    for item in candidate["semantic_relationships"]:
        assert item["source_claim_ids"]
        assert item["evidence_reference"]
        assert "uncertainty" in item


def test_no_knowledge_inflation_or_persistence():
    candidate = build_architectural_knowledge_candidate_v1(_master_v2())

    assert candidate["is_knowledge"] is False
    assert candidate["promoted"] is False
    assert candidate["persistent"] is False
    assert candidate["read_only"] is True
    assert "not_promoted" in candidate["non_claims"]
    assert "not_permanent_knowledge" in candidate["non_claims"]


def test_no_design_reasoning_or_geometry_leakage():
    candidate = build_architectural_knowledge_candidate_v1(_master_v2())
    serialized = json.dumps(candidate, ensure_ascii=False).lower()

    for term in FORBIDDEN:
        assert term not in serialized

    assert "sleeping_storage_relation" in serialized
    assert "sleeping_sanitary_relation" in serialized
    assert "storage_associated" in serialized
    assert "sanitary_service_associated" in serialized


def test_unverified_and_not_reported_evidence_are_not_promoted_to_facts():
    v2 = {
        "contract": "ArchitecturalUnderstandingV2",
        "version": "2.0",
        "semantic_space": {
            "label": "bedroom",
            "status": "bounded_interpretation",
            "basis": ["sleeping element"],
            "claim_id": "au2_claim_001",
        },
        "functional_understanding": {
            "role_candidates": [],
            "associated_elements": [
                {
                    "element": "wardrobe_or_closet",
                    "relationship": "storage_associated",
                    "claim_id": "au2_claim_002",
                    "evidence_reference": ["wardrobe_or_closet"],
                    "grounding_status": ["unverified"],
                    "uncertainty": {"unknowns": ["unverified"]},
                }
            ],
            "functional_relationships": [],
        },
        "spatial_relationships": [],
        "claim_trace": [
            {
                "claim_id": "au2_claim_001",
                "claim_type": "semantic_space",
                "source_evidence": ["sleeping_element"],
                "grounding_status": ["visible"],
                "interpretation_basis": ["sleeping element"],
                "uncertainty": {},
            },
            {
                "claim_id": "au2_claim_002",
                "claim_type": "functional_relationship",
                "source_evidence": ["wardrobe_or_closet"],
                "grounding_status": ["unverified"],
                "interpretation_basis": ["mention only"],
                "uncertainty": {"unknowns": ["unverified"]},
            },
        ],
        "interpretation_states": {
            "primary": {},
            "alternatives": [],
            "unresolved": ["closet is not confirmed"],
            "conflicts": [],
        },
        "evidence_basis": {
            "observed_elements": ["sleeping element visible"],
            "grounding_status": {
                "visible": ["sleeping_element"],
                "unverified": ["wardrobe_or_closet"],
                "symbol_reading": [],
                "denied": [],
                "not_reported": ["bathroom_or_ensuite"],
            },
            "classification_basis": ["sleeping element"],
        },
        "uncertainty": {
            "confidence": "LOW",
            "unknowns": ["closet is not confirmed"],
            "expected_gaps": ["bathroom_or_ensuite"],
            "evidence_conflicts": [],
            "unverified_claims": [],
        },
        "non_claims": [],
        "geometry_authoritative": False,
        "read_only": True,
        "persistent": False,
    }
    candidate = build_architectural_knowledge_candidate_v1(v2)

    association = candidate["element_associations"][0]
    assert association["status"] == "bounded_association"
    assert association["grounding_status"] == ["unverified"]
    assert candidate["uncertainty"]["expected_gaps"] == ["bathroom_or_ensuite"]
