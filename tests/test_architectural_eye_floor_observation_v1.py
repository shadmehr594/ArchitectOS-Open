# -*- coding: utf-8 -*-
"""ARCHITECTURAL_EYE_FLOOR_OBSERVATION_V1 — focused CPU regressions.

Scope
=====
These tests exercise the EXISTING architectural-eye contract only:

    architectural_observation_v1.detect_visible_floors   (the owner)
    architectural_observation_v1.build_architectural_observation

They do NOT call Ollama, ComfyUI, or any image-generation path, and they do
NOT attempt to count storeys from pixels. No edge detection, no CV, no new
observer: this file pins the DATA HANDLING of a storey reading.

What these tests can and cannot prove
=====================================
CAN prove: the contract represents ground floors, upper floors, roof bands,
hedged readings and whole-building visibility correctly; the two historical
miscount defects stay fixed; existing keys keep their meaning.

CANNOT prove: that the vision model counts storeys correctly on a real
image. That requires live inference and is reported as a separate blocker.
"""

import hashlib
import os

import pytest

from core.vision.architectural_observation_v1 import (
    build_architectural_observation,
    detect_visible_floors,
)


def _count(phrase):
    reading = detect_visible_floors([phrase])
    return None if reading is None else reading.get("count")


# ======================================================================
# 1. THE TWO MISCOUNT DEFECTS — these returned confidently wrong counts
# ======================================================================

class TestDefectRegressions:

    def test_substring_defect_stone_is_not_one(self):
        """'one' matched inside 'stone' -> count 1 for a three-storey facade."""
        assert _count("a stone facade with three storeys visible") == 3

    def test_substring_defect_other_hidden_words(self):
        # every one of these contains a number word as a substring
        assert _count("a building made of limestone with two storeys") == 2
        assert _count("no one is visible, four storeys total") == 4

    def test_first_digit_defect_street_number(self):
        """The old code returned the first digit anywhere in the phrase."""
        assert _count("the building at 42 Oak Street has 3 storeys") == 3

    def test_first_digit_defect_other_leading_digits(self):
        assert _count("project 7, a five storey block") == 5

    def test_bare_digit_still_works(self):
        assert _count("3 floors") == 3
        assert _count("2-story") == 2


# ======================================================================
# 2. GROUND FLOOR MUST COUNT
# ======================================================================

class TestGroundFloorRepresentation:

    def test_ground_plus_upper_floors_totals(self):
        """'ground floor plus two upper floors' is THREE storeys, not two."""
        reading = detect_visible_floors(["ground floor plus two upper floors are visible"])
        assert reading["count"] == 3
        assert reading["count_scope"] == "TOTAL"
        assert reading["count_is_total"] is True
        assert reading["ground_floor_included"] is True
        assert reading["upper_floors"] == 2

    def test_ground_floor_named_separately(self):
        reading = detect_visible_floors(
            ["the complete building with three storeys, ground floor and two upper floors"]
        )
        assert reading["count"] == 3
        assert reading["ground_floor_included"] is True

    def test_upper_only_is_not_a_total(self):
        """'two upper floors' is two ABOVE ground, never a total of two."""
        reading = detect_visible_floors(["two upper floors are visible"])
        assert reading["count"] == 2
        assert reading["count_scope"] == "UPPER_ONLY"
        assert reading["count_is_total"] is False
        assert reading["ground_floor_included"] is False

    def test_unqualified_count_does_not_claim_ground(self):
        """'three storeys' says nothing about the ground floor — so None."""
        reading = detect_visible_floors(["three storeys"])
        assert reading["count"] == 3
        assert reading["ground_floor_included"] is None


# ======================================================================
# 3. A ROOF BAND IS NOT A STOREY
# ======================================================================

class TestRoofBandExclusion:

    def test_parapet_alone_yields_no_count(self):
        assert detect_visible_floors(["the roof parapet is visible"]) is None

    def test_roof_terrace_alone_yields_no_count(self):
        assert detect_visible_floors(["a roof terrace on top"]) is None

    def test_roof_band_is_recorded_but_does_not_add(self):
        reading = detect_visible_floors(["three storeys with a roof parapet above"])
        assert reading["count"] == 3
        assert "parapet" in reading["roof_band_excluded"]


# ======================================================================
# 4. HEDGED READING IS LOW CONFIDENCE AND EXPLICIT
# ======================================================================

class TestUncertainBands:

    def test_hedged_count_is_low_confidence(self):
        reading = detect_visible_floors(["four apparent storeys"])
        assert reading["count"] == 4
        assert reading["confidence"] == "LOW"

    def test_hedged_count_records_uncertainty(self):
        reading = detect_visible_floors(["four apparent storeys"])
        assert reading["uncertain_bands"], "a hedged reading must be recorded"
        assert reading["uncertain_bands"][0]["kind"] == "hedged_count"
        assert reading["uncertain_bands"][0]["count_as_stated"] == 4

    def test_confidence_is_never_high(self):
        """Consumers coerce HIGH to LOW, so this contract must never emit HIGH."""
        for phrase in ("three storeys", "four apparent storeys", "two upper floors",
                       "ground floor plus two upper floors"):
            assert detect_visible_floors([phrase])["confidence"] in ("MEDIUM", "LOW")


# ======================================================================
# 5. WHOLE-BUILDING VISIBILITY GATES "COUNTABLE"
# ======================================================================

class TestWholeBuildingVisibility:

    def test_cropped_image_is_not_countable(self):
        reading = detect_visible_floors(["cropped image showing three storeys"])
        assert reading["count"] == 3
        assert reading["whole_building_visible"] is False
        assert reading["countable"] is False

    def test_complete_building_is_countable(self):
        reading = detect_visible_floors(["the complete building with three storeys"])
        assert reading["whole_building_visible"] is True
        assert reading["countable"] is True

    def test_unknown_framing_is_not_assumed_countable(self):
        reading = detect_visible_floors(["three storeys"])
        assert reading["whole_building_visible"] is None
        assert reading["countable"] is None, "framing must not be invented"

    def test_multi_storey_is_never_countable(self):
        reading = detect_visible_floors(["multi-storey building"])
        assert reading["count"] is None
        assert reading["descriptor"] == "multi-storey"
        assert reading["countable"] is False


# ======================================================================
# 6. BACKWARD COMPATIBILITY — existing keys keep their meaning
# ======================================================================

class TestBackwardCompatibility:

    @pytest.mark.parametrize("phrase,expected", [
        ("two-story building", 2),
        ("three floors", 3),
        ("a single storey building", 1),
        ("four storeys", 4),
    ])
    def test_legacy_count(self, phrase, expected):
        assert _count(phrase) == expected

    def test_legacy_none_for_no_claim(self):
        assert detect_visible_floors(["a tall building"]) is None

    def test_legacy_keys_present(self):
        reading = detect_visible_floors(["three storeys"])
        for key in ("count", "evidence_phrase", "confidence"):
            assert key in reading
        assert reading["evidence_phrase"] == "three storeys"

    def test_provenance_records_the_rule(self):
        reading = detect_visible_floors(["three storeys"])
        assert reading["provenance"]["source"] == "provider_phrase"
        assert reading["provenance"]["phrase"] == "three storeys"
        assert reading["provenance"]["rule"] == "number_adjacent_to_floor_noun"


# ======================================================================
# 7. CONTRACT INTEGRATION — the observation carries the extended reading
# ======================================================================

RAW = {
    "image_type": "architectural_render_or_photo",
    "observed": [
        "ground floor plus two upper floors are visible",
        "brick facade",
        "large windows",
        "complete building",
    ],
    "inferred": ["residential building"],
    "unresolved": ["interior layout"],
    "confidence": "MEDIUM",
    "architectural_elements": ["brick facade", "windows"],
    "text_labels_if_visible": [],
    "material_observations": ["brick facade"],
}


class TestContractIntegration:

    def _obs(self):
        return build_architectural_observation(
            RAW, provider="cpu-fixture", model="none", image_id="fixture"
        )

    def test_observation_exposes_ground_floor_fields(self):
        floors = self._obs()["visible_floors"]
        assert floors["count"] == 3
        assert floors["ground_floor_included"] is True
        assert floors["upper_floors"] == 2

    def test_observation_exposes_countability(self):
        floors = self._obs()["visible_floors"]
        assert floors["whole_building_visible"] is True
        assert floors["countable"] is True

    def test_observation_keeps_contract_identity(self):
        obs = self._obs()
        assert obs["contract"] == "ArchitecturalObservationV1"

    def test_provider_supplied_dict_is_backfilled_not_overwritten(self):
        raw = dict(RAW)
        raw["visible_floors"] = {
            "count": 3,
            "count_scope": "TOTAL",
            "storey_divisions_legible": True,
            "evidence": "provider per-level reading",
        }
        floors = build_architectural_observation(raw)["visible_floors"]
        assert floors["count"] == 3
        assert floors["storey_divisions_legible"] is True          # preserved
        assert floors["evidence"] == "provider per-level reading"  # preserved
        assert "ground_floor_included" in floors                   # backfilled
        assert "countable" in floors                               # backfilled

    def test_hedged_reading_survives_into_the_contract(self):
        raw = dict(RAW)
        raw["observed"] = ["four apparent storeys"]
        raw["visible_floors"] = None
        floors = build_architectural_observation(raw)["visible_floors"]
        assert floors["count"] == 4
        assert floors["confidence"] == "LOW"
        assert floors["uncertain_bands"]


# ======================================================================
# 8. ACCEPTANCE FIXTURES — recorded provenance only
#
# These are the immutable images the task designates. This test proves the
# files are the ones referenced and have not been substituted. It does NOT
# claim any storey count for them: that needs live inference.
# ======================================================================

FIXTURES = {
    "V3_00263": (
        r"C:\ComfyUI-Zluda\output\architectos_v11_00263_.png",
        "ae77532be8dd80bbf35af1a04136b86d1689f9b0845b50325f0e4c8a5cde1ab4",
    ),
    "R1_armA": (
        os.path.join("runs", "r1_controlnet_effect_isolation_v1",
                     "armA_r1_cn_effect_00001_.png"),
        "538126b466d57d1154fc4bfae6f352a2c88122d701cbbe1c8e48708bd195e0ba",
    ),
    "R1_armB": (
        os.path.join("runs", "r1_controlnet_effect_isolation_v1",
                     "armB_r1_cn_effect_00002_.png"),
        "cafea50183ea3cc627c1a9a423cff49a271caacfa69f780ffa867a762cd59fd7",
    ),
    "B01_RAW": (
        r"D:\ArchitectOS_FACADE_TEST_IMAGES\B01_RAW.jpg",
        "66f200e3dc33e91f960d40da8239d5cf5654871530cea73a89b0ef7592239c89",
    ),
}


class TestFixtures:

    @pytest.mark.parametrize("name", sorted(FIXTURES))
    def test_fixture_exists_with_expected_digest(self, name):
        path, expected = FIXTURES[name]
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), path)
        if not os.path.isfile(path):
            pytest.skip("fixture not present on this machine: " + path)
        digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
        assert digest == expected, "fixture substituted or modified: " + name
