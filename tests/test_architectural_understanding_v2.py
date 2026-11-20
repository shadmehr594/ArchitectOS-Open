"""Acceptance tests for Architectural Understanding Contract V2."""

from core.vision.architectural_understanding_v2 import (
    CLAIM_TYPES,
    CONTRACT,
    RELATION_STATUSES,
    VERSION,
    build_architectural_understanding_v2,
)
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)
from core.vision.vision_analysis_store_v1 import CARRIED_KEYS


def _master_case():
    return {
        "image_type": "architectural_render_or_photo",
        "observed": ["bed visible", "wardrobe visible", "bathroom visible"],
        "inferred": [],
        "unresolved": [],
        "confidence": "MEDIUM",
        "architectural_elements": ["bed", "wardrobe", "bathroom"],
    }


def test_contract_identity_and_required_shape():
    result = interpret_architectural_vision(_master_case())
    v2 = result["architectural_understanding_v2"]

    assert v2["contract"] == CONTRACT == "ArchitecturalUnderstandingV2"
    assert v2["version"] == VERSION == "2.0"
    for key in (
        "semantic_space",
        "functional_understanding",
        "spatial_relationships",
        "claim_trace",
        "interpretation_states",
        "evidence_basis",
        "uncertainty",
        "non_claims",
        "geometry_authoritative",
        "read_only",
        "persistent",
    ):
        assert key in v2


def test_v2_is_additive_and_v1_remains_available():
    result = interpret_architectural_vision(_master_case())

    assert result["architectural_understanding"]["contract"] == "ArchitecturalUnderstandingV1"
    assert result["architectural_understanding"]["version"] == "1.0"
    assert result["architectural_understanding_v2"]["contract"] == CONTRACT
    assert result["space_type"] == "master bedroom"
    assert result["classification_basis"] == [
        "grounding-bounded suite upgrade",
        "sleeping element",
        "wardrobe_or_closet",
        "bathroom_or_ensuite",
    ]


def test_master_bedroom_functional_understanding_is_bounded():
    v2 = interpret_architectural_vision(_master_case())["architectural_understanding_v2"]
    functional = v2["functional_understanding"]

    roles = functional["role_candidates"]
    assert roles == [
        {
            "role": "private_sleeping_space",
            "status": "bounded_interpretation",
            "claim_id": roles[0]["claim_id"],
            "evidence_reference": ["sleeping_element"],
            "uncertainty": roles[0]["uncertainty"],
        }
    ]

    associated = functional["associated_elements"]
    assert {item["element"] for item in associated} == {
        "wardrobe_or_closet",
        "bathroom_or_ensuite",
    }
    assert all(item["grounding_status"] == ["visible"] for item in associated)
    assert all(item["evidence_reference"] == [item["element"]] for item in associated)

    relationships = functional["functional_relationships"]
    assert {item["type"] for item in relationships} == {
        "sleeping_storage_relation",
        "sleeping_sanitary_relation",
    }
    assert all(item["status"] == "BOUNDED_INFERENCE" for item in relationships)
    assert all(
        "sleeping_element" in item["evidence_reference"]
        for item in relationships
    )


def test_typed_spatial_relationships_and_allowed_statuses():
    interpretation = {
        "space_type": "bedroom",
        "confidence": "MEDIUM",
        "observed_elements": [
            "sleeping element visible",
            "daylight opening visible",
            "seating element visible",
        ],
        "architectural_interpretation": [
            "The visible sleeping element supports an enclosed sleeping-space interpretation."
        ],
        "spatial_relations": [
            "The daylight opening is associated with the enclosed sleeping space.",
            "The seating element is located within the same visible room zone.",
        ],
        "unknowns": [],
        "expected_gaps": [],
        "evidence_conflicts": [],
        "unverified_claims": [],
        "classification_basis": ["sleeping element"],
        "grounding": {
            "visible_elements": ["sleeping_element", "window", "seating"],
            "unverified_elements": [],
            "symbol_readings": [],
            "denied_elements": [],
            "not_reported_elements": [],
        },
    }
    v2 = build_architectural_understanding_v2(interpretation)

    assert len(v2["spatial_relationships"]) == 2
    for relation in v2["spatial_relationships"]:
        assert relation["relation_id"]
        assert relation["relation_type"] in {
            "opening_associated_with_space",
            "seating_within_visible_room_zone",
        }
        assert relation["relation_status"] in RELATION_STATUSES
        assert relation["evidence_reference"]
        assert isinstance(relation["uncertainty"], dict)
        assert relation["claim_id"]


def test_claim_trace_covers_v2_semantic_claims():
    v2 = interpret_architectural_vision(_master_case())["architectural_understanding_v2"]

    assert v2["claim_trace"]
    assert {claim["claim_type"] for claim in v2["claim_trace"]} >= {
        "semantic_space",
        "functional_role",
        "functional_relationship",
        "alternative_interpretation",
    }
    assert set(claim["claim_type"] for claim in v2["claim_trace"]).issubset(
        set(CLAIM_TYPES)
    )
    for index, claim in enumerate(v2["claim_trace"], start=1):
        assert claim["claim_id"] == "au2_claim_%03d" % index
        assert claim["source_evidence"]
        assert "grounding_status" in claim
        assert "interpretation_basis" in claim
        assert "uncertainty" in claim
        assert "knowledge" not in claim["claim_id"].lower()


def test_interpretation_states_include_primary_alternative_and_uncertainty():
    v2 = interpret_architectural_vision(_master_case())["architectural_understanding_v2"]
    states = v2["interpretation_states"]

    assert states["primary"]["label"] == "master bedroom"
    assert states["primary"]["status"] == "bounded_interpretation"
    assert states["alternatives"]
    assert states["alternatives"][0]["label"] == "sleeping_area_inside_larger_space"
    assert states["alternatives"][0]["status"] == "alternative_interpretation"
    assert states["unresolved"] == []
    assert states["conflicts"] == []


def test_evidence_statuses_are_preserved():
    interpretation = {
        "space_type": "bedroom",
        "confidence": "LOW",
        "observed_elements": ["sleeping element visible"],
        "architectural_interpretation": [],
        "spatial_relations": [],
        "unknowns": ["closet is unknown"],
        "expected_gaps": ["wardrobe_or_closet"],
        "evidence_conflicts": [],
        "unverified_claims": ["sanitary zone visible"],
        "classification_basis": ["sleeping element"],
        "grounding": {
            "visible_elements": ["sleeping_element"],
            "unverified_elements": ["bathroom_or_ensuite"],
            "symbol_readings": ["window"],
            "denied_elements": ["wardrobe_or_closet"],
            "not_reported_elements": ["wc"],
        },
    }
    v2 = build_architectural_understanding_v2(interpretation)
    statuses = v2["evidence_basis"]["grounding_status"]

    assert statuses == {
        "visible": ["sleeping_element"],
        "unverified": ["bathroom_or_ensuite"],
        "symbol_reading": ["window"],
        "denied": ["wardrobe_or_closet"],
        "not_reported": ["wc"],
    }
    assert v2["uncertainty"]["unknowns"] == ["closet is unknown"]
    assert v2["uncertainty"]["expected_gaps"] == ["wardrobe_or_closet"]
    assert v2["uncertainty"]["unverified_claims"] == ["sanitary zone visible"]


def test_boundary_forbidden_terms_and_non_persistence():
    v2 = interpret_architectural_vision(_master_case())["architectural_understanding_v2"]
    serialized = str(v2).lower()

    assert "MASTER_BEDROOM_SLEEPING" not in str(v2)
    for forbidden in (
        "verified_space",
        "knowledge_id",
        "ontology_assignment",
        "required",
        "optimized",
        "should",
        "recommended",
        "best",
        "privacy improvement",
    ):
        assert forbidden not in serialized

    assert "architectural_understanding_v2" not in CARRIED_KEYS
    assert v2["geometry_authoritative"] is False
    assert v2["read_only"] is True
    assert v2["persistent"] is False
    assert "not_permanent_knowledge" in v2["non_claims"]
    assert "not_design_reasoning" in v2["non_claims"]
