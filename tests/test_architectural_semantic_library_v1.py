"""Tests for the transient ArchitecturalSemanticLibraryCandidateV1 layer."""

import json

import pytest

from core.knowledge.architectural_semantic_library_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    build_architectural_semantic_library_candidate_v1,
)
from core.teaching.architectural_teaching_record_v1 import (
    build_architectural_teaching_record_v1,
)
from core.teaching.architectural_teaching_session_v1 import (
    build_architectural_teaching_session_v1,
)


def _record(topic, pattern, evidence, claim_id):
    record = build_architectural_teaching_record_v1(
        {
            "contract": "ArchitecturalTeachingCandidateV1",
            "version": "1.0",
            "teaching_units": [
                {
                    "topic": topic,
                    "source_pattern": pattern,
                    "evidence_reference": evidence,
                    "source_claim_ids": [claim_id],
                    "grounding_status": ["visible"],
                    "uncertainty": {
                        "unknowns": [],
                        "evidence_conflicts": [],
                    },
                }
            ],
            "uncertainty": {
                "confidence": "bounded",
                "unknowns": [],
                "evidence_conflicts": [],
            },
        },
        "This is a bounded human explanation of an observed association.",
    )
    # The current TeachingRecordV1 contract does not emit claim IDs itself.
    # This validation input includes an explicitly supplied ID to verify that
    # the semantic-library boundary preserves, rather than invents, it.
    record["source_claim_ids"] = [claim_id]
    record["grounding_status"] = ["visible"]
    return record


def _session():
    return build_architectural_teaching_session_v1(
        [
            _record(
                "sleeping_space_and_storage_association",
                "sleeping_storage_relation",
                ["sleeping_element", "wardrobe_or_closet"],
                "au2_claim_001",
            ),
            _record(
                "sleeping_space_and_sanitary_service_association",
                "sleeping_sanitary_relation",
                ["sleeping_element", "bathroom_or_ensuite"],
                "au2_claim_002",
            ),
        ]
    )


def test_contract_and_output_shape():
    candidate = build_architectural_semantic_library_candidate_v1(_session())

    assert candidate["contract"] == CONTRACT == "ArchitecturalSemanticLibraryCandidateV1"
    assert candidate["version"] == VERSION == "1.0"
    assert candidate["semantic_groups"]
    assert candidate["pattern_index"] == [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    ]
    assert candidate["evidence_chain"]
    assert candidate["source_sessions"][0]["contract"] == SOURCE_CONTRACT
    assert candidate["persistent"] is False
    assert candidate["promoted"] is False


def test_patterns_are_grouped_as_observed_semantic_group():
    candidate = build_architectural_semantic_library_candidate_v1(_session())

    assert len(candidate["semantic_groups"]) == 1
    group = candidate["semantic_groups"][0]
    assert group["group"] == "sleeping_space_association"
    assert group["patterns"] == [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    ]
    assert group["status"] == "observed_semantic_group"
    assert group["claim_ids"] == ["au2_claim_001", "au2_claim_002"]


def test_evidence_and_uncertainty_are_preserved():
    session = _session()
    candidate = build_architectural_semantic_library_candidate_v1(session)

    chain = candidate["evidence_chain"]
    assert chain[0]["source_pattern"] == "sleeping_storage_relation"
    assert chain[0]["claim_ids"] == ["au2_claim_001"]
    assert chain[1]["claim_ids"] == ["au2_claim_002"]
    assert chain[0]["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
    ]
    assert chain[0]["grounding_status"] == ["visible"]
    assert candidate["uncertainty"]["session"] == session["uncertainty"]
    assert candidate["semantic_groups"][0]["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
        "bathroom_or_ensuite",
    ]


def test_deterministic_and_non_mutating():
    session = _session()
    original = json.loads(json.dumps(session))
    first = build_architectural_semantic_library_candidate_v1(session)
    second = build_architectural_semantic_library_candidate_v1(session)

    assert first == second
    assert session == original
    first["semantic_groups"][0]["patterns"].append("changed")
    assert "changed" not in session["source_patterns"]


def test_no_memory_learning_design_or_permanent_knowledge():
    candidate = build_architectural_semantic_library_candidate_v1(_session())
    payload = {
        key: value
        for key, value in candidate.items()
        if key != "non_claims"
    }
    serialized = json.dumps(payload, ensure_ascii=False).lower()

    assert candidate["non_claims"] == [
        "not_design_rule",
        "not_recommendation",
        "not_permanent_memory",
        "not_authoritative_knowledge",
    ]
    assert candidate["persistent"] is False
    assert candidate["promoted"] is False
    assert "design rule" not in serialized
    assert "recommendation" not in serialized
    assert "optimal_solution" not in serialized
    assert "permanent" not in serialized


def test_session_validation_rejects_other_pipeline_objects():
    with pytest.raises(TypeError):
        build_architectural_semantic_library_candidate_v1(None)
    with pytest.raises(ValueError):
        build_architectural_semantic_library_candidate_v1(
            {
                "contract": "ArchitecturalTeachingRecordV1",
                "version": "1.0",
            }
        )
    with pytest.raises(ValueError):
        build_architectural_semantic_library_candidate_v1(
            {
                "contract": "ArchitecturalTeachingSessionV1",
                "version": "2.0",
                "teaching_records": [],
            }
        )
