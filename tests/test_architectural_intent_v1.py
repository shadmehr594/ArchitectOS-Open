"""Tests for the transient ArchitecturalIntentCandidateV1 boundary."""

import json

import pytest

from core.design.architectural_intent.architectural_intent_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    build_architectural_intent_candidate_v1,
)
from core.knowledge.architectural_semantic_library_v1 import (
    build_architectural_semantic_library_candidate_v1,
)
from core.knowledge.architectural_semantic_retrieval_v1 import (
    retrieve_architectural_semantic_patterns_v1,
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
                    "uncertainty": {"unknowns": [], "evidence_conflicts": []},
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
    record["source_claim_ids"] = [claim_id]
    record["grounding_status"] = ["visible"]
    return record


def _retrieval_result():
    session = build_architectural_teaching_session_v1(
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
    library = build_architectural_semantic_library_candidate_v1(session)
    return retrieve_architectural_semantic_patterns_v1(
        library,
        "sleeping_space_association",
    )


def test_contract_and_version():
    result = build_architectural_intent_candidate_v1(_retrieval_result())

    assert result["contract"] == CONTRACT == "ArchitecturalIntentCandidateV1"
    assert result["version"] == VERSION == "1.0"
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_intents_are_derived_only_from_retrieved_patterns():
    result = build_architectural_intent_candidate_v1(_retrieval_result())

    assert [item["intent_type"] for item in result["intent_candidates"]] == [
        "sleeping_private_space_intent",
        "storage_associated_intent",
        "sanitary_service_associated_intent",
    ]
    assert all(
        item["status"] == "bounded_intent_candidate"
        for item in result["intent_candidates"]
    )
    assert result["source_patterns"] == [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    ]


def test_evidence_and_uncertainty_are_preserved():
    retrieval = _retrieval_result()
    result = build_architectural_intent_candidate_v1(retrieval)

    assert result["uncertainty"] == retrieval["uncertainty"]
    assert result["evidence_basis"] == [
        {
            "semantic_group": "sleeping_space_association",
            "matched_patterns": [
                "sleeping_storage_relation",
                "sleeping_sanitary_relation",
            ],
            "source_evidence": [
                "sleeping_element",
                "wardrobe_or_closet",
                "bathroom_or_ensuite",
            ],
            "uncertainty": retrieval["matches"][0]["uncertainty"],
        }
    ]
    assert result["intent_candidates"][0]["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
        "bathroom_or_ensuite",
    ]


def test_deterministic_and_non_mutating():
    retrieval = _retrieval_result()
    original = json.loads(json.dumps(retrieval))

    first = build_architectural_intent_candidate_v1(retrieval)
    second = build_architectural_intent_candidate_v1(retrieval)

    assert first == second
    assert retrieval == original
    first["source_patterns"].append("changed")
    assert "changed" not in retrieval["query"]


def test_retrieval_only_input_validation():
    with pytest.raises(TypeError):
        build_architectural_intent_candidate_v1(None)
    for invalid in (
        {"contract": "ArchitecturalSemanticLibraryCandidateV1", "version": "1.0"},
        {"contract": "ArchitecturalKnowledgeCandidateV1", "version": "1.0"},
        {"contract": "ArchitecturalTeachingRecordV1", "version": "1.0"},
    ):
        with pytest.raises(ValueError):
            build_architectural_intent_candidate_v1(invalid)


def test_no_design_reasoning_geometry_or_persistence():
    result = build_architectural_intent_candidate_v1(_retrieval_result())
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
        "place_bed",
        "move_wall",
        "optimize_daylight",
        "recommended_plan",
        "geometry",
        "cad",
        "bim",
        "memory",
    ):
        assert term not in serialized

    assert result["non_claims"] == [
        "not_design_reasoning",
        "not_design_solution",
        "not_geometry",
        "not_layout",
        "not_rule",
    ]
