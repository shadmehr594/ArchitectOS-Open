"""Tests for the transient ArchitecturalIntentResolutionV1 boundary."""

import json

import pytest

from core.design.architectural_intent.architectural_intent_resolution_v1 import (
    CONTRACT,
    SOURCE_CONTRACT,
    VERSION,
    resolve_architectural_intent_v1,
)


def _candidate(intents):
    return {
        "contract": SOURCE_CONTRACT,
        "version": VERSION,
        "intent_candidates": intents,
        "source_patterns": [
            pattern
            for intent in intents
            for pattern in intent.get("source_pattern", [])
        ],
        "evidence_basis": [
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
                "uncertainty": [],
            }
        ],
        "uncertainty": {
            "library": {},
            "matched_groups": 1,
        },
        "non_claims": [],
        "persistent": False,
        "read_only": True,
    }


def _sleeping_candidate():
    return _candidate(
        [
            {
                "intent_type": "sleeping_private_space_intent",
                "status": "bounded_intent_candidate",
                "source_pattern": ["sleeping_storage_relation"],
                "evidence_reference": ["sleeping_element"],
                "uncertainty": [],
            },
            {
                "intent_type": "storage_associated_intent",
                "status": "bounded_intent_candidate",
                "source_pattern": ["sleeping_storage_relation"],
                "evidence_reference": ["wardrobe_or_closet"],
                "uncertainty": [],
            },
            {
                "intent_type": "sanitary_service_associated_intent",
                "status": "bounded_intent_candidate",
                "source_pattern": ["sleeping_sanitary_relation"],
                "evidence_reference": ["bathroom_or_ensuite"],
                "uncertainty": [],
            },
        ]
    )


def test_contract_and_version():
    result = resolve_architectural_intent_v1(_sleeping_candidate())

    assert result["contract"] == CONTRACT == "ArchitecturalIntentResolutionV1"
    assert result["version"] == VERSION == "1.0"
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_private_sleeping_group_resolution():
    result = resolve_architectural_intent_v1(_sleeping_candidate())

    assert result["intent_groups"] == [
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
        }
    ]
    assert result["semantic_components"] == ["private_sleeping_zone_intent"]


def test_circulation_and_opening_groups():
    candidate = _candidate(
        [
            {
                "intent_type": "circulation_associated_intent",
                "status": "bounded_intent_candidate",
                "source_pattern": ["entrance_threshold_in_facade_composition"],
                "evidence_reference": ["entrance"],
                "uncertainty": {},
            },
            {
                "intent_type": "opening_relationship_intent",
                "status": "bounded_intent_candidate",
                "source_pattern": ["opening_within_facade_plane"],
                "evidence_reference": ["window"],
                "uncertainty": {},
            },
        ]
    )
    result = resolve_architectural_intent_v1(candidate)

    assert [group["intent_group"] for group in result["intent_groups"]] == [
        "circulation_zone_intent",
        "opening_relationship_intent",
    ]
    assert result["source_intents"] == [
        "circulation_associated_intent",
        "opening_relationship_intent",
    ]


def test_evidence_and_uncertainty_are_preserved():
    candidate = _sleeping_candidate()
    candidate["uncertainty"] = {
        "library": {"records": ["uncertain"]},
        "matched_groups": 1,
    }
    result = resolve_architectural_intent_v1(candidate)

    assert result["evidence_basis"] == candidate["evidence_basis"]
    assert result["uncertainty"] == candidate["uncertainty"]
    group = result["intent_groups"][0]
    assert group["evidence_reference"] == [
        "sleeping_element",
        "wardrobe_or_closet",
        "bathroom_or_ensuite",
    ]


def test_deterministic_and_non_mutating():
    candidate = _sleeping_candidate()
    original = json.loads(json.dumps(candidate))

    first = resolve_architectural_intent_v1(candidate)
    second = resolve_architectural_intent_v1(candidate)

    assert first == second
    assert candidate == original


def test_input_validation_and_no_forbidden_semantics():
    with pytest.raises(TypeError):
        resolve_architectural_intent_v1(None)
    with pytest.raises(ValueError):
        resolve_architectural_intent_v1(
            {"contract": "ArchitecturalSemanticRetrievalResultV1", "version": "1.0"}
        )

    result = resolve_architectural_intent_v1(_sleeping_candidate())
    payload = {
        key: value for key, value in result.items() if key != "non_claims"
    }
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for term in (
        "should",
        "must",
        "required",
        "optimal",
        "best",
        "recommended",
        "adjacent",
        "place",
        "layout",
        "geometry",
    ):
        assert term not in serialized
    assert result["non_claims"] == [
        "not_design_reasoning",
        "not_layout",
        "not_geometry",
        "not_rule",
    ]
