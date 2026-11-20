"""Tests for the transient ArchitecturalTeachingCandidateV1 layer."""

import json

import pytest

from core.knowledge.architectural_knowledge_v1 import (
    build_architectural_knowledge_candidate_v1,
)
from core.knowledge.architectural_knowledge_structurer_v1 import (
    build_architectural_knowledge_structure_v1,
)
from core.teaching.architectural_teaching_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    build_architectural_teaching_candidate_v1,
)
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)


FORBIDDEN = (
    "why this design is good",
    "recommended layout",
    "optimal arrangement",
    "architectural rule",
    "should",
    "must",
    "required",
    "optimized",
    "best",
    "recommended",
)


def _knowledge_structure():
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
    candidate = build_architectural_knowledge_candidate_v1(
        interpretation["architectural_understanding_v2"]
    )
    return build_architectural_knowledge_structure_v1(candidate)


def test_contract_and_structure_shape():
    result = build_architectural_teaching_candidate_v1(_knowledge_structure())

    assert result["contract"] == CONTRACT == "ArchitecturalTeachingCandidateV1"
    assert result["version"] == VERSION == "1.0"
    assert result["teaching_units"]
    assert result["source_patterns"]
    assert result["evidence_basis"]["source_contract"] == SOURCE_CONTRACT
    assert result["evidence_basis"]["source_version"] == "1.0"
    assert result["is_training_input"] is True
    assert result["persistent"] is False


def test_teaching_units_are_containers_needing_human_explanation():
    result = build_architectural_teaching_candidate_v1(_knowledge_structure())
    units = result["teaching_units"]

    assert {unit["topic"] for unit in units} == {
        "sleeping_space_and_storage_association",
        "sleeping_space_and_sanitary_service_association",
    }
    assert {unit["source_pattern"] for unit in units} == {
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    }
    assert all(
        unit["explanation_status"] == "needs_human_explanation"
        for unit in units
    )
    assert all(unit["confidence"] == "bounded" for unit in units)
    assert all(unit["evidence_reference"] for unit in units)
    assert all(unit["source_claim_ids"] for unit in units)


def test_evidence_and_uncertainty_are_preserved():
    structure = _knowledge_structure()
    result = build_architectural_teaching_candidate_v1(structure)

    assert result["evidence_basis"] == {
        **structure["evidence_basis"],
        "source_contract": "ArchitecturalKnowledgeStructureV1",
        "source_version": "1.0",
    }
    assert result["uncertainty"] == structure["uncertainty"]
    for pattern in result["source_patterns"]:
        assert pattern["source_claim_ids"]
        assert pattern["evidence_reference"]
        assert "grounding_status" in pattern
        assert "uncertainty" in pattern


def test_no_memory_learning_promotion_or_design_reasoning():
    result = build_architectural_teaching_candidate_v1(_knowledge_structure())
    payload = {
        key: value
        for key, value in result.items()
        if key != "non_claims"
    }
    serialized = json.dumps(payload, ensure_ascii=False).lower()

    assert result["non_claims"] == [
        "not_memory",
        "not_learned_model",
        "not_design_rule",
        "not_authoritative_knowledge",
    ]
    assert all(term not in serialized for term in FORBIDDEN)
    assert "learned" not in serialized
    assert "promoted" not in serialized
    assert result["persistent"] is False


def test_input_validation_and_determinism():
    structure = _knowledge_structure()
    first = build_architectural_teaching_candidate_v1(structure)
    second = build_architectural_teaching_candidate_v1(structure)

    assert first == second
    with pytest.raises(TypeError):
        build_architectural_teaching_candidate_v1(None)
    with pytest.raises(ValueError):
        build_architectural_teaching_candidate_v1(
            {"contract": "ArchitecturalKnowledgeCandidateV1", "version": "1.0"}
        )
