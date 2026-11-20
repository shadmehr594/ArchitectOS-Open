"""Tests for the transient ArchitecturalTeachingSessionV1 layer."""

import json

import pytest

from core.teaching.architectural_teaching_record_v1 import (
    build_architectural_teaching_record_v1,
)
from core.teaching.architectural_teaching_session_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    build_architectural_teaching_session_v1,
)


def _record(topic, pattern, evidence, explanation):
    return build_architectural_teaching_record_v1(
        {
            "contract": "ArchitecturalTeachingCandidateV1",
            "version": "1.0",
            "teaching_units": [
                {
                    "topic": topic,
                    "source_pattern": pattern,
                    "evidence_reference": evidence,
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
        explanation,
    )


def _records():
    return [
        _record(
            "sleeping_space_and_storage_association",
            "sleeping_storage_relation",
            ["sleeping_element", "wardrobe_or_closet"],
            "Storage is associated with a sleeping-space pattern.",
        ),
        _record(
            "sleeping_space_and_sanitary_service_association",
            "sleeping_sanitary_relation",
            ["sleeping_element", "bathroom_or_ensuite"],
            "A sanitary service is associated with a sleeping-space pattern.",
        ),
    ]


def test_contract_and_grouped_session_shape():
    records = _records()
    session = build_architectural_teaching_session_v1(records)

    assert session["contract"] == CONTRACT == "ArchitecturalTeachingSessionV1"
    assert session["version"] == VERSION == "1.0"
    assert session["session_topic"] == "architectural_teaching_session"
    assert session["teaching_records"] == records
    assert session["source_patterns"] == [
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    ]
    assert session["persistent"] is False


def test_evidence_and_uncertainty_are_preserved():
    records = _records()
    session = build_architectural_teaching_session_v1(records)

    evidence = session["evidence_basis"]
    assert evidence["source_contract"] == SOURCE_CONTRACT
    assert evidence["source_version"] == "1.0"
    assert evidence["teaching_topics"] == [
        "sleeping_space_and_storage_association",
        "sleeping_space_and_sanitary_service_association",
    ]
    assert evidence["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
        "bathroom_or_ensuite",
    ]
    assert session["uncertainty"]["record_count"] == 2
    assert len(session["uncertainty"]["records"]) == 2


def test_grouping_is_deterministic_and_does_not_mutate_records():
    records = _records()
    original = json.loads(json.dumps(records))
    first = build_architectural_teaching_session_v1(records)
    second = build_architectural_teaching_session_v1(records)

    assert first == second
    assert records == original
    first["teaching_records"][0]["human_explanation"] = "changed"
    assert records[0]["human_explanation"] != "changed"


def test_no_memory_learning_or_persistence():
    session = build_architectural_teaching_session_v1(_records())

    assert session["non_claims"] == [
        "not_memory",
        "not_learned_model",
        "not_design_rule",
    ]
    assert session["persistent"] is False
    payload = {
        key: value
        for key, value in session.items()
        if key != "non_claims"
    }
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    assert "promoted" not in serialized
    assert "learned_model" not in serialized
    assert "design rule" not in serialized


def test_record_validation_and_empty_session_rejection():
    with pytest.raises(TypeError):
        build_architectural_teaching_session_v1(None)
    with pytest.raises(TypeError):
        build_architectural_teaching_session_v1(_records()[0])
    with pytest.raises(ValueError):
        build_architectural_teaching_session_v1([])
    with pytest.raises(ValueError):
        build_architectural_teaching_session_v1(
            [{"contract": "ArchitecturalTeachingCandidateV1", "version": "1.0"}]
        )
