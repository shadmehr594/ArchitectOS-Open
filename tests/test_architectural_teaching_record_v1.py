"""Tests for the transient ArchitecturalTeachingRecordV1 layer."""

import json

import pytest

from core.knowledge.architectural_knowledge_v1 import (
    build_architectural_knowledge_candidate_v1,
)
from core.knowledge.architectural_knowledge_structurer_v1 import (
    build_architectural_knowledge_structure_v1,
)
from core.teaching.architectural_teaching_record_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    build_architectural_teaching_record_v1,
)
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)


def _teaching_candidate():
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
    knowledge_candidate = build_architectural_knowledge_candidate_v1(
        interpretation["architectural_understanding_v2"]
    )
    knowledge_structure = build_architectural_knowledge_structure_v1(
        knowledge_candidate
    )
    teaching_candidate = {
        "contract": SOURCE_CONTRACT,
        "version": VERSION,
        "teaching_units": [
            {
                "topic": "sleeping_space_and_storage_association",
                "source_pattern": "sleeping_storage_relation",
                "explanation_status": "needs_human_explanation",
                "evidence_reference": [
                    "sleeping_element",
                    "wardrobe_or_closet",
                ],
                "grounding_status": ["visible"],
                "source_claim_ids": ["au2_claim_001"],
                "confidence": "bounded",
                "uncertainty": {
                    "unknowns": [],
                    "evidence_conflicts": [],
                },
            }
        ],
        "source_patterns": knowledge_structure["patterns"],
        "evidence_basis": knowledge_structure["evidence_basis"],
        "uncertainty": knowledge_structure["uncertainty"],
        "non_claims": [
            "not_memory",
            "not_learned_model",
            "not_design_rule",
            "not_authoritative_knowledge",
        ],
        "is_training_input": True,
        "persistent": False,
    }
    return teaching_candidate


def test_contract_and_explanation_attachment():
    record = build_architectural_teaching_record_v1(
        _teaching_candidate(),
        "Storage is commonly associated with a sleeping space in this observed pattern.",
    )

    assert record["contract"] == CONTRACT == "ArchitecturalTeachingRecordV1"
    assert record["version"] == VERSION == "1.0"
    assert record["teaching_topic"] == "sleeping_space_and_storage_association"
    assert record["source_pattern"] == "sleeping_storage_relation"
    assert record["human_explanation"] == (
        "Storage is commonly associated with a sleeping space in this observed pattern."
    )
    assert record["claim_boundary"] == {
        "is_rule": False,
        "is_design_decision": False,
    }


def test_evidence_and_uncertainty_are_preserved():
    candidate = _teaching_candidate()
    record = build_architectural_teaching_record_v1(
        candidate,
        "The observed pattern links sleeping and storage elements without asserting a rule.",
    )

    assert record["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
    ]
    assert record["uncertainty"]["unknowns"] == candidate["uncertainty"]["unknowns"]
    assert record["uncertainty"]["evidence_conflicts"] == candidate["uncertainty"]["evidence_conflicts"]


def test_unmarked_rule_like_explanations_are_rejected():
    candidate = _teaching_candidate()
    for explanation in (
        "A bedroom should contain a wardrobe.",
        "The bed must always be separated from the entry.",
        "This is the optimal arrangement.",
        "A required layout uses storage here.",
        "This is the best solution.",
    ):
        with pytest.raises(ValueError):
            build_architectural_teaching_record_v1(candidate, explanation)


def test_marked_opinion_or_example_may_contain_rule_like_language():
    candidate = _teaching_candidate()

    opinion = build_architectural_teaching_record_v1(
        candidate,
        "Architectural opinion: a bedroom should contain storage in some projects.",
    )
    example = build_architectural_teaching_record_v1(
        candidate,
        "Architectural example: the bed must always be separated from the entry.",
    )

    assert opinion["claim_boundary"]["is_rule"] is False
    assert example["claim_boundary"]["is_design_decision"] is False
    assert "Architectural opinion" in opinion["human_explanation"]
    assert "Architectural example" in example["human_explanation"]


def test_no_memory_or_persistence_and_deterministic_output():
    candidate = _teaching_candidate()
    explanation = "Storage is associated with the sleeping-space pattern."
    first = build_architectural_teaching_record_v1(candidate, explanation)
    second = build_architectural_teaching_record_v1(candidate, explanation)

    assert first == second
    assert first["persistent"] is False
    assert first["non_claims"] == [
        "not_memory",
        "not_permanent_knowledge",
        "not_design_rule",
    ]
    payload = {
        key: value for key, value in first.items() if key != "non_claims"
    }
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    assert "memory" not in serialized
    assert "promoted" not in serialized
    assert "design decision" not in serialized


def test_input_validation_and_empty_candidate_rejection():
    with pytest.raises(TypeError):
        build_architectural_teaching_record_v1(None, "A bounded explanation.")
    with pytest.raises(ValueError):
        build_architectural_teaching_record_v1(
            {"contract": "ArchitecturalKnowledgeStructureV1", "version": "1.0"},
            "A bounded explanation.",
        )
    with pytest.raises(TypeError):
        build_architectural_teaching_record_v1(_teaching_candidate(), None)
    with pytest.raises(ValueError):
        build_architectural_teaching_record_v1(_teaching_candidate(), "")
    empty = dict(_teaching_candidate())
    empty["teaching_units"] = []
    with pytest.raises(ValueError):
        build_architectural_teaching_record_v1(empty, "A bounded explanation.")
