"""Validation set V1 for Image -> Observation -> Interpretation -> V2."""

import json
from pathlib import Path

import pytest

from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)
from core.vision.vision_analysis_store_v1 import CARRIED_KEYS


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "vision" / "architectural_understanding_v2"
FIXTURES = sorted(FIXTURE_DIR.glob("*.json"))
FORBIDDEN = (
    "knowledge_id",
    "ontology_assignment",
    "verified_space",
    "teaching_call",
    "memory_write",
    "design reasoning",
    "design_rule",
    "layout_rule",
    "geometry_mutation",
    "cad_operation",
    "bim_operation",
    "ifc_operation",
    "render_call",
    "comfyui_call",
    "required",
    "optimized",
    "should",
    "recommended",
    "best",
    "privacy improvement",
)


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=lambda path: path.stem)
def test_validation_case_preserves_evidence_and_bounded_semantics(fixture_path):
    fixture = _load(fixture_path)
    result = interpret_architectural_vision(fixture["input"])
    v2 = result["architectural_understanding_v2"]
    expected = fixture["expected"]

    assert result["contract"] == "ArchitecturalVisionInterpreterV1"
    assert v2["contract"] == "ArchitecturalUnderstandingV2"
    assert result["space_type"] == expected["space_type"]
    assert v2["semantic_space"]["label"] == expected["space_type"]
    assert v2["semantic_space"]["status"] == expected["semantic_status"]
    assert v2["semantic_space"]["basis"] == result["classification_basis"]

    visible = v2["evidence_basis"]["grounding_status"]["visible"]
    for element in expected.get("visible_elements", []):
        assert element in visible

    assert v2["evidence_basis"]["observed_elements"] == result["observed_elements"]
    assert v2["uncertainty"]["unknowns"] == result["unknowns"]
    assert v2["uncertainty"]["expected_gaps"] == result["expected_gaps"]
    assert v2["uncertainty"]["evidence_conflicts"] == result["evidence_conflicts"]

    role_candidates = v2["functional_understanding"]["role_candidates"]
    role = expected.get("role")
    if role is None:
        assert role_candidates == []
    else:
        assert [candidate["role"] for candidate in role_candidates] == [role]
        assert all(
            candidate["status"] == "bounded_interpretation"
            for candidate in role_candidates
        )

    associated = v2["functional_understanding"]["associated_elements"]
    for element, relationship in expected.get("associated", {}).items():
        matches = [item for item in associated if item["element"] == element]
        assert len(matches) == 1
        assert matches[0]["relationship"] == relationship
        assert matches[0]["evidence_reference"] == [element]

    functional_types = {
        item["type"]
        for item in v2["functional_understanding"]["functional_relationships"]
    }
    assert set(expected.get("functional_relation_types", [])).issubset(functional_types)

    spatial = v2["spatial_relationships"]
    relation_types = {item["relation_type"] for item in spatial}
    assert set(expected.get("relation_types", [])).issubset(relation_types)
    for relation in spatial:
        assert relation["relation_status"] in {
            "OBSERVED_RELATION",
            "BOUNDED_INFERENCE",
            "UNRESOLVED_RELATION",
        }
        assert relation["relation_id"]
        assert relation["claim_id"]
        assert relation["evidence_reference"] or relation["relation_status"] == "UNRESOLVED_RELATION"
        assert isinstance(relation["uncertainty"], dict)

    expected_statuses = set(expected.get("relation_statuses", []))
    if expected_statuses:
        assert expected_statuses.issubset(
            {item["relation_status"] for item in spatial}
        )

    if expected.get("requires_uncertainty"):
        assert v2["uncertainty"]["confidence"] == "LOW"
        assert v2["uncertainty"]["unknowns"]
        assert v2["interpretation_states"]["unresolved"]


def test_validation_set_claim_traces_are_complete_and_local():
    for fixture_path in FIXTURES:
        fixture = _load(fixture_path)
        v2 = interpret_architectural_vision(fixture["input"])[
            "architectural_understanding_v2"
        ]
        claims = v2["claim_trace"]
        assert claims
        assert [claim["claim_id"] for claim in claims] == [
            "au2_claim_%03d" % index
            for index in range(1, len(claims) + 1)
        ]
        for claim in claims:
            assert claim["claim_type"] in {
                "semantic_space",
                "functional_role",
                "functional_relationship",
                "spatial_relationship",
                "alternative_interpretation",
            }
            assert "source_evidence" in claim
            assert "grounding_status" in claim
            assert "interpretation_basis" in claim
            assert "uncertainty" in claim


def test_validation_set_boundary_is_transient_and_non_design():
    for fixture_path in FIXTURES:
        fixture = _load(fixture_path)
        v2 = interpret_architectural_vision(fixture["input"])[
            "architectural_understanding_v2"
        ]
        serialized = json.dumps(v2, ensure_ascii=False).lower()
        assert v2["geometry_authoritative"] is False
        assert v2["read_only"] is True
        assert v2["persistent"] is False
        assert "not_permanent_knowledge" in v2["non_claims"]
        assert "not_design_reasoning" in v2["non_claims"]
        assert all(term not in serialized for term in FORBIDDEN)

    assert "architectural_understanding_v2" not in CARRIED_KEYS
