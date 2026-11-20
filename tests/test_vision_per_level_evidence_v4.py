"""VISION_PER_LEVEL_ARCHITECTURAL_EVIDENCE_V4 focused CPU regressions.

These tests exercise only the existing facade provider mapper and the existing
DesignConstraintFidelity owner.  They do not call Ollama, ComfyUI, or any image
generation path.
"""

from core.vision import design_constraint_fidelity_v1 as fidelity
from core.vision.facade_reference_vision_provider_v1 import (
    ROLE_TARGET_BUILDING,
    _ROLE_PROMPTS,
    map_to_contract,
)


def _intent(floors=2):
    return {"building_type": "villa", "floors": floors}


def _level(position, category, contributes, evidence, confidence=0.95):
    return {
        "level_position": position,
        "category": category,
        "evidence": evidence,
        "confidence": confidence,
        "contributes_to_floor_count": contributes,
    }


def _contract(count, levels, *, count_type="TOTAL", legible=True, **extra):
    payload = {
        "building_type": "villa",
        "visible_floor_count": count,
        "floor_observation": {
            "count": count,
            "count_type": count_type,
            "storey_divisions_legible": legible,
            "evidence": "level-by-level facade reading",
            "per_level_evidence": levels,
        },
    }
    payload.update(extra)
    return map_to_contract(payload)


def test_prompt_declares_optional_per_level_contract_and_categories():
    prompt = " ".join(_ROLE_PROMPTS[ROLE_TARGET_BUILDING].lower().split())
    for required in (
        "per_level_evidence",
        "level_position",
        "principal_storey",
        "roof_opening",
        "attic_or_roof_storey",
        "mezzanine",
        "ambiguous",
        "contributes_to_floor_count",
    ):
        assert required in prompt


def test_mapper_retains_optional_per_level_evidence_without_inventing_fields():
    mapped = _contract(
        2,
        [
            _level("ground", "principal_storey", True, "full facade band"),
            _level("upper", "principal_storey", True, "second full facade band"),
            _level("gable", "roof_opening", False, "window lies inside roof slope", 0.9),
        ],
    )

    levels = mapped["floor_observation"]["per_level_evidence"]
    assert [item["category"] for item in levels] == [
        "principal_storey", "principal_storey", "roof_opening"
    ]
    assert levels[-1]["contributes_to_floor_count"] is False
    assert levels[-1]["confidence"] == 0.9


def test_roof_opening_is_not_automatically_a_storey():
    mapped = _contract(
        2,
        [
            _level("ground", "principal_storey", True, "ground facade band"),
            _level("upper", "principal_storey", True, "upper facade band"),
            _level("gable", "roof_opening", False, "isolated opening within gable"),
        ],
    )

    result = fidelity.evaluate(_intent(2), "two-storey villa", mapped)
    assert result["floor_status"] == fidelity.FLOOR_VERIFIED
    assert result["observed"]["floor_consistency"]["status"] == "CONSISTENT"


def test_genuine_roof_storey_is_not_automatically_removed():
    mapped = _contract(
        3,
        [
            _level("ground", "principal_storey", True, "full ground facade band"),
            _level("middle", "principal_storey", True, "full middle facade band"),
            _level(
                "upper roof volume",
                "attic_or_roof_storey",
                True,
                "sustained roof-storey volume with a legible floor division",
            ),
        ],
    )

    result = fidelity.evaluate(_intent(3), "three-storey villa", mapped)
    assert result["floor_status"] == fidelity.FLOOR_VERIFIED
    assert result["observed"]["floors"] == 3


def test_mezzanine_is_not_always_a_full_storey():
    mapped = _contract(
        2,
        [
            _level("ground", "principal_storey", True, "full ground facade band"),
            _level("intermediate", "mezzanine", False, "partial-height intermediate band"),
            _level("upper", "principal_storey", True, "full upper facade band"),
        ],
    )

    result = fidelity.evaluate(_intent(2), "two-storey villa", mapped)
    assert result["floor_status"] == fidelity.FLOOR_VERIFIED


def test_ambiguous_level_keeps_total_unverified():
    mapped = _contract(
        2,
        [
            _level("ground", "principal_storey", True, "full ground facade band"),
            _level("upper", "principal_storey", True, "full upper facade band"),
            _level("roof band", "ambiguous", False, "division is obscured", 0.4),
        ],
    )

    result = fidelity.evaluate(_intent(2), "two-storey villa", mapped)
    assert result["floor_status"] == fidelity.FLOOR_UNVERIFIED
    assert result["observed"]["floor_consistency"]["status"] == "UNVERIFIED"
    assert "ambiguous" in result["floor_reason"].lower()


def test_explicit_level_classification_uncertainty_keeps_total_unverified():
    mapped = _contract(
        3,
        [
            _level("ground", "principal_storey", True, "full ground facade band"),
            _level("middle", "principal_storey", True, "full middle facade band"),
            {
                **_level(
                    "upper gable",
                    "principal_storey",
                    True,
                    "single opening within the gable",
                    0.8,
                ),
                "uncertainty": "could be an attic window rather than a full storey",
            },
        ],
    )

    result = fidelity.evaluate(_intent(3), "three-storey villa", mapped)
    assert result["floor_status"] == fidelity.FLOOR_UNVERIFIED
    assert result["observed"]["floor_consistency"]["status"] == "UNVERIFIED"
    assert "uncertainty" in result["floor_reason"].lower()


def test_cropped_building_cannot_establish_complete_total_with_levels():
    mapped = _contract(
        2,
        [
            _level("middle", "principal_storey", True, "one complete visible band"),
            _level("upper", "principal_storey", True, "one complete visible band"),
        ],
        perspective_limitations=["lower building is cropped out of frame"],
    )

    result = fidelity.evaluate(_intent(2), "two-storey villa", mapped)
    assert result["floor_status"] == fidelity.FLOOR_UNVERIFIED
    assert result["observed"]["view_partial"] is True


def test_count_and_per_level_evidence_cannot_contradict_and_verify():
    mapped = _contract(
        3,
        [
            _level("ground", "principal_storey", True, "full ground facade band"),
            _level("upper", "principal_storey", True, "full upper facade band"),
            _level("gable", "roof_opening", False, "opening within the roof volume"),
        ],
    )

    result = fidelity.evaluate(_intent(3), "three-storey villa", mapped)
    assert result["floor_status"] == fidelity.FLOOR_UNVERIFIED
    assert result["observed"]["floor_consistency"]["status"] == "CONTRADICTORY"
    assert result["design_accepted"] is False


def test_total_requires_legible_divisions_when_per_level_evidence_is_present():
    mapped = _contract(
        2,
        [
            _level("ground", "principal_storey", True, "first apparent band"),
            _level("upper", "principal_storey", True, "second apparent band"),
        ],
        legible=False,
    )

    result = fidelity.evaluate(_intent(2), "two-storey villa", mapped)
    assert result["floor_status"] == fidelity.FLOOR_UNVERIFIED
    assert result["observed"]["floor_consistency"]["status"] == "CONTRADICTORY"


def test_legacy_v2_v3_contract_without_per_level_evidence_is_compatible():
    legacy = map_to_contract({
        "building_type": "villa",
        "visible_floor_count": 2,
        "floor_observation": {
            "count": 2,
            "count_type": "TOTAL",
            "storey_divisions_legible": True,
            "evidence": "two complete storeys",
        },
    })

    result = fidelity.evaluate(_intent(2), "two-storey villa", legacy)
    assert "per_level_evidence" not in legacy["floor_observation"]
    assert result["floor_status"] == fidelity.FLOOR_VERIFIED
    assert result["observed"]["floor_consistency"]["status"] == "LEGACY"


def test_existing_lighting_observation_mapping_is_unchanged():
    lighting = {
        "time_of_day": "night",
        "facade_readability": "partial",
        "artificial_lighting_visible": True,
        "evidence": "dark sky and warm window light",
        "confidence": 0.91,
    }
    mapped = map_to_contract({"lighting": lighting})
    assert mapped["lighting"] == lighting
