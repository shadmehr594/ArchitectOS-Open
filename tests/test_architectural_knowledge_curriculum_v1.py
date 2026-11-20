"""Tests for the transient ArchitecturalKnowledgeCurriculumV1 boundary."""

import json

import pytest

from core.knowledge.curriculum.architectural_knowledge_curriculum_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    build_architectural_knowledge_curriculum_v1,
)


def _session():
    return {
        "contract": SOURCE_CONTRACT,
        "version": VERSION,
        "session_topic": "architectural_teaching_session",
        "teaching_records": [
            {
                "contract": "ArchitecturalTeachingRecordV1",
                "version": "1.0",
                "teaching_topic": "sleeping_space_and_storage_association",
                "source_pattern": "sleeping_storage_relation",
                "human_explanation": "Storage is associated with a sleeping-space pattern.",
                "evidence_reference": [
                    "sleeping_element",
                    "wardrobe_or_closet",
                ],
                "grounding_status": ["visible"],
                "source_claim_ids": ["au2_claim_001"],
                "uncertainty": {
                    "unknowns": [],
                    "evidence_conflicts": [],
                },
            },
            {
                "contract": "ArchitecturalTeachingRecordV1",
                "version": "1.0",
                "teaching_topic": "sleeping_space_and_sanitary_service_association",
                "source_pattern": "sleeping_sanitary_relation",
                "human_explanation": "Sanitary service is associated with a sleeping-space pattern.",
                "evidence_reference": [
                    "sleeping_element",
                    "bathroom_or_ensuite",
                ],
                "grounding_status": ["visible"],
                "source_claim_ids": ["au2_claim_002"],
                "uncertainty": {
                    "unknowns": ["exact service separation is unresolved"],
                    "evidence_conflicts": [],
                },
            },
        ],
        "source_patterns": [
            "sleeping_storage_relation",
            "sleeping_sanitary_relation",
        ],
        "evidence_basis": {
            "source_contract": "ArchitecturalTeachingRecordV1",
            "source_version": "1.0",
            "evidence_reference": [
                "sleeping_element",
                "wardrobe_or_closet",
                "bathroom_or_ensuite",
            ],
        },
        "uncertainty": {
            "record_count": 2,
            "records": [
                {"unknowns": []},
                {"unknowns": ["exact service separation is unresolved"]},
            ],
        },
        "non_claims": [],
        "persistent": False,
    }


def test_contract_version_domain_and_shape():
    result = build_architectural_knowledge_curriculum_v1(_session())

    assert result["contract"] == CONTRACT == "ArchitecturalKnowledgeCurriculumV1"
    assert result["version"] == VERSION == "1.0"
    assert result["curriculum_domain"] == "foundation_spatial_semantics"
    assert result["learning_cases"]
    assert result["semantic_groups"]
    assert result["source_evidence"]
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_semantic_grouping_is_deterministic_and_bounded():
    result = build_architectural_knowledge_curriculum_v1(_session())

    assert [group["semantic_area"] for group in result["semantic_groups"]] == [
        "functional_association",
    ]
    assert result["semantic_groups"][0]["source_patterns"] == [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    ]
    assert all(
        group["status"] == "bounded_curriculum_group"
        for group in result["semantic_groups"]
    )
    assert all(
        case["semantic_area"] == "functional_association"
        for case in result["learning_cases"]
    )


def test_evidence_claim_ids_and_uncertainty_are_preserved():
    session = _session()
    result = build_architectural_knowledge_curriculum_v1(session)

    assert result["source_evidence"] == [
        {
            "source_pattern": "sleeping_storage_relation",
            "source_claim_ids": ["au2_claim_001"],
            "evidence_reference": [
                "sleeping_element",
                "wardrobe_or_closet",
            ],
            "grounding_status": ["visible"],
        },
        {
            "source_pattern": "sleeping_sanitary_relation",
            "source_claim_ids": ["au2_claim_002"],
            "evidence_reference": [
                "sleeping_element",
                "bathroom_or_ensuite",
            ],
            "grounding_status": ["visible"],
        },
    ]
    assert result["uncertainty"]["session"] == session["uncertainty"]
    assert result["learning_cases"][1]["uncertainty"] == {
        "unknowns": ["exact service separation is unresolved"],
        "evidence_conflicts": [],
    }


def test_deterministic_and_non_mutating():
    session = _session()
    original = json.loads(json.dumps(session))

    first = build_architectural_knowledge_curriculum_v1(session)
    second = build_architectural_knowledge_curriculum_v1(session)

    assert first == second
    assert session == original
    first["learning_cases"][0]["source_pattern"] = "changed"
    assert session["source_patterns"][0] != "changed"


def test_session_only_input_validation():
    with pytest.raises(TypeError):
        build_architectural_knowledge_curriculum_v1(None)
    for invalid in (
        {"contract": "ArchitecturalTeachingRecordV1", "version": "1.0"},
        {"contract": "ArchitecturalKnowledgeCandidateV1", "version": "1.0"},
        {"contract": "ArchitecturalUnderstandingV2", "version": "2.0"},
        {"contract": "ArchitecturalSemanticLibraryCandidateV1", "version": "1.0"},
        {"contract": "ArchitecturalSemanticRetrievalResultV1", "version": "1.0"},
        {"contract": "ArchitecturalDesignReasoningInputV1", "version": "1.0"},
    ):
        with pytest.raises(ValueError):
            build_architectural_knowledge_curriculum_v1(invalid)
    with pytest.raises(ValueError):
        build_architectural_knowledge_curriculum_v1(
            {"contract": SOURCE_CONTRACT, "version": "1.0", "teaching_records": []}
        )


def test_boundary_flags_and_no_forbidden_outputs():
    result = build_architectural_knowledge_curriculum_v1(_session())
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
        "design_solution",
        "layout_rule",
        "placement",
        "geometry",
        "dimension",
        "cad",
        "bim",
        "ifc",
    ):
        assert term not in serialized

    assert result["non_claims"] == [
        "not_design_rule",
        "not_recommendation",
        "not_authoritative_knowledge",
        "not_memory",
        "not_learned_model",
    ]
    assert result["persistent"] is False
