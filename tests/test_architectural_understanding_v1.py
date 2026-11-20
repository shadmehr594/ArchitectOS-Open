"""Acceptance tests for the transient Architectural Understanding Contract V1."""

from core.vision.architectural_understanding_v1 import (
    CONTRACT,
    VERSION,
    build_architectural_understanding,
)
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)
from core.vision.vision_analysis_store_v1 import CARRIED_KEYS


def test_contract_is_attached_additively_to_interpreter_output():
    result = interpret_architectural_vision(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["bed visible", "wardrobe visible"],
            "inferred": [],
            "unresolved": [],
            "confidence": "MEDIUM",
            "architectural_elements": ["bed", "wardrobe"],
        }
    )

    assert result["space_type"] == "bedroom"
    assert result["observed_elements"]
    assert result["architectural_understanding"]["contract"] == CONTRACT
    assert result["architectural_understanding"]["version"] == VERSION
    assert result["architectural_understanding"]["semantic_space"]["label"] == "bedroom"


def test_bedroom_understanding_is_bounded_and_functional_not_certain():
    result = interpret_architectural_vision(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["bed visible", "closet visible"],
            "inferred": [],
            "unresolved": [],
            "confidence": "MEDIUM",
            "architectural_elements": ["bed", "closet"],
        }
    )
    understanding = result["architectural_understanding"]

    assert understanding["semantic_space"]["status"] == "bounded_interpretation"
    assert understanding["functional_role"]["candidates"] == ["likely bedroom"]
    assert understanding["evidence_basis"]["observed_elements"] == result["observed_elements"]
    assert "verified" not in understanding["semantic_space"]
    assert "MASTER_BEDROOM_SLEEPING" not in str(understanding)


def test_grounded_master_bedroom_keeps_evidence_and_non_claims():
    result = interpret_architectural_vision(
        {
            "image_type": "architectural_render_or_photo",
            "observed": [
                "bed visible",
                "wardrobe visible",
                "bathroom visible",
            ],
            "inferred": [],
            "unresolved": [],
            "confidence": "MEDIUM",
            "architectural_elements": ["bed", "wardrobe", "bathroom"],
        }
    )
    understanding = result["architectural_understanding"]
    statuses = understanding["evidence_basis"]["grounding_status"]

    assert result["space_type"] == "master bedroom"
    assert understanding["semantic_space"]["label"] == "master bedroom"
    assert "grounding-bounded suite upgrade" in understanding["semantic_space"]["basis"]
    assert "sleeping_element" in statuses["visible"]
    assert "wardrobe_or_closet" in statuses["visible"]
    assert "bathroom_or_ensuite" in statuses["visible"]
    assert understanding["non_claims"]
    assert "not_permanent_knowledge" in understanding["non_claims"]
    assert "not_design_reasoning" in understanding["non_claims"]
    assert understanding["persistent"] is False
    assert understanding["read_only"] is True


def test_grounding_uncertainty_is_preserved_without_reclassification():
    result = interpret_architectural_vision(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["bed visible"],
            "inferred": ["bathroom visible"],
            "unresolved": ["closet unclear"],
            "confidence": "LOW",
            "architectural_elements": ["bed", "bathroom"],
        }
    )
    understanding = result["architectural_understanding"]
    statuses = understanding["evidence_basis"]["grounding_status"]

    assert result["space_type"] == "bedroom"
    assert "bathroom_or_ensuite" in statuses["unverified"]
    assert understanding["uncertainty"]["unknowns"] == result["unknowns"]
    assert understanding["uncertainty"]["expected_gaps"] == result["expected_gaps"]
    assert understanding["uncertainty"]["evidence_conflicts"] == result["evidence_conflicts"]


def test_transient_understanding_is_not_an_allowed_store_field():
    assert "architectural_understanding" not in CARRIED_KEYS

    interpretation = interpret_architectural_vision({"observed": ["bed visible"]})
    assert "architectural_understanding" in interpretation
