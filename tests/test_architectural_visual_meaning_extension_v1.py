# -*- coding: utf-8 -*-
"""ARCHITECTURAL VISUAL MEANING EXTENSION V1 — tests.

The deeper element_meaning (function · architectural_role ·
possible_relationships · context · exceptions) added to
ArchitecturalVisualInterpretationV2, plus the evidence-gating rules:

  * a relationship is emitted ONLY when its co-evidence is visible
  * with no evidence the relationship is EMPTY, never inferred
  * nothing is probabilistic-turned-absolute
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.vision.architectural_observation_v1 import (
    build_architectural_observation,
)
from core.vision.architectural_visual_interpretation_v2 import (
    ELEMENT_MEANINGS,
    ELEMENT_ARCHITECTURAL_PROFILES,
    build_architectural_visual_interpretation_v2,
)


def observe(raw):
    return build_architectural_observation(raw, provider="ollama", model="gemma4:12b")


def interp(raw):
    return build_architectural_visual_interpretation_v2(observe(raw))


def element(interp_result, kind):
    for entry in interp_result["element_meaning"]:
        if entry["element_kind"] == kind:
            return entry
    return None


def relationship_names(entry):
    return [r["relationship"] for r in (entry.get("possible_relationships") or [])]


# ======================================================================
# REQUIRED TEST 1 — visible bed WITHOUT a visible entrance
#                  -> no forced privacy relation
# ======================================================================

class Test1_BedWithoutEntrance:

    def _bed_only(self):
        return interp({
            "image_type": "architectural_render_or_photo",
            "observed": ["bed with white linens", "white ceiling"],
            "inferred": [], "unresolved": [], "confidence": "HIGH",
            "architectural_elements": ["ceiling", "floor", "wall"],
            "text_labels_if_visible": [],
            "furniture_elements": ["bed"],
        })

    def test_1a_no_privacy_relationship_is_forced(self):
        bed = element(self._bed_only(), "bed")
        assert bed is not None
        assert "privacy" not in relationship_names(bed)

    def test_1b_no_entrance_visibility_relationship(self):
        bed = element(self._bed_only(), "bed")
        assert "entrance_visibility" not in relationship_names(bed)

    def test_1c_no_circulation_relationship(self):
        bed = element(self._bed_only(), "bed")
        assert "circulation" not in relationship_names(bed)

    def test_1d_the_element_itself_is_still_reported(self):
        bed = element(self._bed_only(), "bed")
        assert bed["function"] == "sleeping"
        assert bed["architectural_role"] == "private_space_indicator"
        assert bed["evidence"]

    def test_1e_the_relationships_list_is_empty_not_inferred(self):
        bed = element(self._bed_only(), "bed")
        assert bed["possible_relationships"] == []

    def test_1f_with_a_visible_door_privacy_becomes_possible(self):
        """The gate is the EVIDENCE, not the element."""

        with_door = interp({
            "image_type": "architectural_render_or_photo",
            "observed": ["bed with white linens", "doorway on the left"],
            "inferred": [], "unresolved": [], "confidence": "HIGH",
            "architectural_elements": ["ceiling", "floor", "wall", "door"],
            "text_labels_if_visible": [],
            "furniture_elements": ["bed"],
        })

        bed = element(with_door, "bed")
        assert "privacy" in relationship_names(bed)
        assert "entrance_visibility" in relationship_names(bed)


# ======================================================================
# REQUIRED TEST 2 — a visible window -> the daylight relation is allowed
# ======================================================================

class Test2_WindowDaylight:

    def _with_window(self):
        return interp({
            "image_type": "architectural_render_or_photo",
            "observed": ["large window", "bed with white linens"],
            "inferred": [], "unresolved": [], "confidence": "HIGH",
            "architectural_elements": ["large window", "wall", "floor"],
            "text_labels_if_visible": [],
            "furniture_elements": ["bed"],
        })

    def test_2a_the_window_carries_a_daylight_relation(self):
        window = element(self._with_window(), "window")
        assert window is not None
        assert "natural_light" in relationship_names(window)

    def test_2b_the_window_function_and_role(self):
        window = element(self._with_window(), "window")
        assert window["function"] == "daylight / ventilation"
        assert window["architectural_role"] == "environmental_element"

    def test_2c_the_bed_gains_the_daylight_relation_from_the_window(self):
        bed = element(self._with_window(), "bed")
        assert "daylight" in relationship_names(bed)

    def test_2d_a_window_without_an_occupant_space_has_no_room_quality(self):
        """room_quality needs an occupant element as evidence."""

        bare = interp({
            "image_type": "architectural_render_or_photo",
            "observed": ["window on a blank wall"],
            "inferred": [], "unresolved": [], "confidence": "MEDIUM",
            "architectural_elements": ["window", "wall"],
            "text_labels_if_visible": [],
        })

        window = element(bare, "window")
        assert "room_quality" not in relationship_names(window)
        assert "natural_light" in relationship_names(window)


# ======================================================================
# REQUIRED TEST 3 — a hidden bathroom -> no bathroom relationship
# ======================================================================

class Test3_HiddenBathroom:

    def _no_bathroom(self):
        return interp({
            "image_type": "architectural_render_or_photo",
            "observed": ["bed with white linens", "walk-in closet", "large window"],
            "inferred": [], "unresolved": [], "confidence": "HIGH",
            "architectural_elements": ["large window", "wall", "floor", "ceiling"],
            "text_labels_if_visible": [],
            "furniture_elements": ["bed", "wardrobe"],
        })

    def test_3a_no_bathroom_relationship_anywhere(self):
        result = self._no_bathroom()
        for entry in result["element_meaning"]:
            for name in relationship_names(entry):
                assert "bathroom" not in name, (entry["element_kind"], name)

    def test_3b_the_wardrobe_has_no_connection_with_bathroom(self):
        wardrobe = element(self._no_bathroom(), "wardrobe")
        assert "connection_with_bathroom" not in relationship_names(wardrobe)

    def test_3c_the_wardrobe_still_has_its_dressing_sequence(self):
        wardrobe = element(self._no_bathroom(), "wardrobe")
        assert "dressing_sequence" in relationship_names(wardrobe)

    def test_3d_the_interpretation_is_not_a_master_bedroom(self):
        result = self._no_bathroom()
        assert result["architectural_meaning"]["space_understanding"]["value"] == "bedroom"

    def test_3e_with_a_visible_bathroom_the_relationship_appears(self):
        with_bath = interp({
            "image_type": "architectural_render_or_photo",
            "observed": ["bed with white linens", "walk-in closet", "toilet"],
            "inferred": [], "unresolved": [], "confidence": "HIGH",
            "architectural_elements": ["wall", "floor", "ceiling"],
            "text_labels_if_visible": [],
            "furniture_elements": ["bed", "wardrobe", "toilet"],
        })

        wardrobe = element(with_bath, "wardrobe")
        assert "connection_with_bathroom" in relationship_names(wardrobe)


# ======================================================================
# REQUIRED TEST 4 — master bedroom from VISIBLE evidence only
# ======================================================================

class Test4_MasterBedroom:

    def _master(self):
        return interp({
            "image_type": "architectural_render_or_photo",
            "observed": [
                "bed with white linens", "walk-in closet", "en-suite bathroom door",
                "toilet", "large window", "doorway on the left",
            ],
            "inferred": [], "unresolved": [], "confidence": "HIGH",
            "architectural_elements": ["wall", "floor", "ceiling", "door", "large window"],
            "text_labels_if_visible": [],
            "furniture_elements": ["bed", "wardrobe", "toilet"],
        })

    def test_4a_the_space_is_a_master_bedroom_possibility(self):
        space = self._master()["architectural_meaning"]["space_understanding"]
        assert space["value"] == "master bedroom"

    def test_4b_every_evidence_phrase_is_a_visible_element(self):
        result = self._master()
        space = result["architectural_meaning"]["space_understanding"]

        visible = set()
        for entry in result["element_meaning"]:
            visible.update(entry["evidence"])

        assert space["evidence"]
        for phrase in space["evidence"]:
            assert phrase in visible, "evidence not traceable to an observation: " + phrase

    def test_4c_the_confidence_is_not_absolute(self):
        space = self._master()["architectural_meaning"]["space_understanding"]
        assert space["confidence"] in ("LOW", "MEDIUM")

    def test_4d_the_required_relationship_set_is_present(self):
        result = self._master()

        bed = element(result, "bed")
        assert set(["privacy", "entrance_visibility", "daylight", "circulation"]) <= set(
            relationship_names(bed)
        )

        wardrobe = element(result, "wardrobe")
        assert "connection_with_bathroom" in relationship_names(wardrobe)

        window = element(result, "window")
        assert "natural_light" in relationship_names(window)


# ======================================================================
# THE BRIEF'S FIELD SPEC
# ======================================================================

class TestContractFields:

    REQUIRED = (
        "element", "function", "architectural_role", "possible_relationships",
        "context", "exceptions", "evidence", "confidence", "reasoning_source",
    )

    PRESERVED = (
        "observed", "element_kind", "meaning", "evidence", "confidence",
        "reasoning_source",
    )

    def _result(self):
        return interp({
            "image_type": "architectural_render_or_photo",
            "observed": ["bed with white linens", "walk-in closet", "large window"],
            "inferred": [], "unresolved": [], "confidence": "HIGH",
            "architectural_elements": ["large window", "wall", "floor"],
            "text_labels_if_visible": [],
            "furniture_elements": ["bed", "wardrobe"],
        })

    def test_all_required_fields_are_present(self):
        for entry in self._result()["element_meaning"]:
            for key in self.REQUIRED:
                assert key in entry, (entry["element_kind"], key)

    def test_all_preserved_fields_are_still_present(self):
        """Backward compatibility: no existing field was removed."""

        for entry in self._result()["element_meaning"]:
            for key in self.PRESERVED:
                assert key in entry, (entry["element_kind"], key)

    def test_every_relationship_carries_evidence_confidence_and_source(self):
        for entry in self._result()["element_meaning"]:
            for rel in entry["possible_relationships"]:
                assert rel["evidence"], (entry["element_kind"], rel)
                assert rel["confidence"] in ("LOW", "MEDIUM", "HIGH")
                assert rel["reasoning_source"]

    def test_the_exceptions_are_reported(self):
        bed = element(self._result(), "bed")
        assert bed["exceptions"]
        assert any("hotel" in e or "exclusive" in e for e in bed["exceptions"])

    def test_the_context_names_the_typical_spaces(self):
        bed = element(self._result(), "bed")
        assert "bedroom" in bed["context"]
        assert "master_bedroom" in bed["context"]

    def test_the_image_context_is_the_real_category(self):
        result = self._result()
        for entry in result["element_meaning"]:
            assert entry["image_context"] == result["image_category"]["value"]

    def test_nothing_is_an_absolute(self):
        for entry in self._result()["element_meaning"]:
            assert entry["probabilistic"] is True
            assert entry["certainty"] == "POSSIBLE"

    def test_every_profile_is_probabilistic(self):
        """No profile may assert a certainty."""

        for kind, profile in ELEMENT_ARCHITECTURAL_PROFILES.items():
            assert "function" in profile, kind
            assert "architectural_role" in profile, kind
            blob = str(profile).lower()
            for absolute in ("always", "must", "definitely", "certainly"):
                assert absolute not in blob, (kind, absolute)

    def test_every_profiled_kind_exists_in_the_meaning_table(self):
        for kind in ELEMENT_ARCHITECTURAL_PROFILES:
            assert kind in ELEMENT_MEANINGS, kind


# ======================================================================
# NO INVENTION
# ======================================================================

class TestNoInvention:

    def test_a_kind_without_a_profile_is_not_fabricated(self):
        """`vehicle` has a profile; an unknown kind must yield empty values."""

        import core.vision.architectural_visual_interpretation_v2 as V2

        original = V2.ELEMENT_ARCHITECTURAL_PROFILES.pop("rug")
        try:
            result = interp({
                "image_type": "architectural_render_or_photo",
                "observed": ["a rug on the floor"],
                "inferred": [], "unresolved": [], "confidence": "MEDIUM",
                "architectural_elements": ["floor"],
                "text_labels_if_visible": [],
                "furniture_elements": ["rug"],
            })
            rug = element(result, "rug")
            assert rug is not None                  # it was SEEN
            assert rug["meaning"]                   # the base meaning survives
            assert rug["function"] is None          # nothing invented
            assert rug["architectural_role"] is None
            assert rug["possible_relationships"] == []
            assert rug["context"] == []
            assert rug["exceptions"] == []
        finally:
            V2.ELEMENT_ARCHITECTURAL_PROFILES["rug"] = original

    def test_no_elements_yields_no_meanings(self):
        result = build_architectural_visual_interpretation_v2(
            build_architectural_observation(
                {"image_type": "unknown", "observed": [], "inferred": [],
                 "unresolved": [], "confidence": "LOW",
                 "architectural_elements": [], "text_labels_if_visible": []},
                provider="t", model="t",
            )
        )
        assert result["element_meaning"] == []

    def test_a_bed_only_observation_gains_no_bathroom_relationship(self):
        result = interp({
            "image_type": "architectural_render_or_photo",
            "observed": ["bed with white linens"],
            "inferred": [], "unresolved": [], "confidence": "HIGH",
            "architectural_elements": ["wall"],
            "text_labels_if_visible": [],
            "furniture_elements": ["bed"],
        })
        for entry in result["element_meaning"]:
            for name in relationship_names(entry):
                assert "bathroom" not in name


# ======================================================================
# BOUNDARIES
# ======================================================================

class TestBoundaries:

    def test_no_design_or_geometry_is_produced(self):
        result = interp({
            "image_type": "architectural_render_or_photo",
            "observed": ["bed with white linens"],
            "inferred": [], "unresolved": [], "confidence": "HIGH",
            "architectural_elements": ["wall"],
            "text_labels_if_visible": [],
            "furniture_elements": ["bed"],
        })
        assert result["design_generated"] is False
        assert result["geometry_authoritative"] is False
        assert result["render_requested"] is False
        assert result["plan_generated"] is False

    def test_the_authored_payload_contains_no_geometry_terms(self):
        result = interp({
            "image_type": "architectural_render_or_photo",
            "observed": ["bed with white linens", "large window"],
            "inferred": [], "unresolved": [], "confidence": "HIGH",
            "architectural_elements": ["large window", "wall"],
            "text_labels_if_visible": [],
            "furniture_elements": ["bed"],
        })
        blob = str(result["element_meaning"]).lower()
        for term in ("svg", "png", "cad", "bim", "ifc", "coordinate",
                     "geometry", "render"):
            assert term not in blob, term
