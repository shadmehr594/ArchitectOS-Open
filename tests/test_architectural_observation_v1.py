# -*- coding: utf-8 -*-
"""ARCHITECTURAL_OBSERVATION_V1 — tests.

Covers the contract, the three no-loss rules, the interpreter pass-through,
observation/interpretation separation, and the three human validation cases.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.vision.architectural_observation_v1 import (
    CONTRACT,
    IMAGE_TYPES,
    build_architectural_observation,
    visible_observations_passthrough,
    detect_visible_floors,
    architectural_observation_v1,
)
from core.vision.image_understanding_v1 import build_understanding
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)


# ======================================================================
# HUMAN VALIDATION CASE 1 — TWO-STOREY FACADE
# (the real gemma4:12b output for the facade image)
# ======================================================================

FACADE_RAW = {
    "image_type": "architectural_render_or_photo",
    "observed": [
        "two-story building", "concrete facade", "large glass windows",
        "wooden slats", "glass balcony railing", "flat roof",
        "surrounding greenery", "paved walkway",
    ],
    "inferred": ["residential building", "modern architectural style"],
    "unresolved": ["interior layout", "exact material composition", "geographic location"],
    "confidence": "HIGH",
    "architectural_elements": [
        "concrete facade", "glass windows", "wooden louvers",
        "balcony", "glass railing", "flat roof", "walkway",
    ],
    "text_labels_if_visible": [],
    "visible_floors": "two-story building",
    "material_observations": ["concrete facade", "glass windows", "wooden slats"],
    "style_indicators": ["horizontal emphasis", "minimalist detailing"],
    "spatial_clues": ["walkway leading to the entrance"],
}


class TestCase1_Facade:

    def _observation(self):
        return build_architectural_observation(
            FACADE_RAW, provider="ollama", model="gemma4:12b", image_id="facade"
        )

    def test_1a_floors_are_detected(self):
        obs = self._observation()
        assert obs["visible_floors"] is not None
        assert obs["visible_floors"]["count"] == 2

    def test_1b_windows_and_balconies_are_detected(self):
        obs = self._observation()
        kinds = set()
        for entry in obs["architectural_elements"]:
            kinds.update(entry.get("kind") or [])
        assert "window" in kinds
        assert "balcony" in kinds

    def test_1c_visible_materials_are_detected(self):
        obs = self._observation()
        materials = set()
        for entry in obs["material_observations"]:
            materials.update(entry.get("materials") or [])
        assert "concrete" in materials
        assert "glass" in materials
        assert "wood" in materials

    def test_1d_facade_composition_clues_are_detected(self):
        obs = self._observation()
        assert obs["style_indicators"], "composition/style clues must survive"

    def test_1e_image_type_is_exterior(self):
        assert self._observation()["image_type"] == "exterior"


# ======================================================================
# HUMAN VALIDATION CASE 2 — BEDROOM
# ======================================================================

BEDROOM_RAW = {
    "image_type": "architectural_render_or_photo",
    "observed": [
        "bed with white linens", "wooden slatted wall",
        "floor-to-ceiling glass windows", "adjacent room with clothing",
        "doorway on the left", "en-suite bathroom door", "minimalist floor",
        "leaning full-length mirror", "white ceiling",
    ],
    "inferred": ["bedroom interior", "walk-in closet area", "natural lighting"],
    "unresolved": ["exact material types", "room dimensions"],
    "confidence": "HIGH",
    "architectural_elements": [
        "slatted wall", "glass partition", "floor-to-ceiling windows",
        "bed frame", "ceiling", "floor", "door",
    ],
    "text_labels_if_visible": [],
    "material_observations": ["wooden slatted wall", "glass windows"],
    "spatial_clues": [
        "adjacent room with clothing", "doorway on the left",
        "en-suite bathroom door",
    ],
    "furniture_elements": ["bed", "wardrobe", "mirror", "toilet"],
}


class TestCase2_Bedroom:

    def _observation(self):
        return build_architectural_observation(
            BEDROOM_RAW, provider="ollama", model="gemma4:12b", image_id="bedroom"
        )

    def test_2a_bed_and_furniture_are_detected(self):
        obs = self._observation()
        kinds = set()
        for entry in obs["furniture_elements"]:
            kinds.update(entry.get("kind") or [])
        assert "bed" in kinds
        assert "wardrobe" in kinds
        assert "mirror" in kinds

    def test_2b_door_and_window_are_detected(self):
        obs = self._observation()
        kinds = set()
        for entry in obs["architectural_elements"]:
            kinds.update(entry.get("kind") or [])
        assert "door" in kinds
        assert "window" in kinds

    def test_2c_closet_is_detected_when_visible(self):
        obs = self._observation()
        kinds = set()
        for entry in obs["furniture_elements"]:
            kinds.update(entry.get("kind") or [])
        assert "wardrobe" in kinds

    def test_2d_bathroom_is_detected_when_visible(self):
        obs = self._observation()
        kinds = set()
        for entry in obs["furniture_elements"]:
            kinds.update(entry.get("kind") or [])
        assert "sanitary" in kinds

    def test_2e_circulation_clues_are_detected(self):
        obs = self._observation()
        kinds = {clue.get("kind") for clue in obs["spatial_clues"]}
        assert kinds, "spatial clues must survive"
        assert kinds & {"adjacency", "access", "circulation"}

    def test_2f_image_type_is_interior(self):
        assert self._observation()["image_type"] == "interior"


# ======================================================================
# HUMAN VALIDATION CASE 3 — ARCHITECTURAL PLAN
# ======================================================================

PLAN_RAW = {
    "image_type": "floor_plan_or_sketch",
    "observed": [
        "2D floor plan", "Persian text labels", "wall outlines",
        "door symbols", "window symbols", "furniture icons",
        "dimension lines", "website URL",
    ],
    "inferred": ["residential layout", "interior spaces"],
    "unresolved": ["exact scale", "building materials"],
    "confidence": "HIGH",
    "architectural_elements": ["walls", "doors", "windows", "rooms"],
    "text_labels_if_visible": [
        "اتاق خواب", "آشپزخانه", "حمام", "سرمایش", "آبشویی", "پذیرایی",
    ],
    "furniture_elements": ["bed", "wardrobe", "sofa", "table"],
    "spatial_clues": ["rooms side-by-side", "corridor leading to rooms"],
}


class TestCase3_Plan:

    def _observation(self):
        return build_architectural_observation(
            PLAN_RAW, provider="ollama", model="gemma4:12b", image_id="plan"
        )

    def test_3a_image_type_is_plan(self):
        assert self._observation()["image_type"] == "plan"

    def test_3b_walls_doors_windows_are_detected(self):
        obs = self._observation()
        kinds = set()
        for entry in obs["architectural_elements"]:
            kinds.update(entry.get("kind") or [])
        assert "wall" in kinds
        assert "door" in kinds
        assert "window" in kinds

    def test_3c_rooms_and_labels_are_preserved(self):
        obs = self._observation()
        assert len(obs["text_labels_if_visible"]) >= 4

    def test_3d_furniture_is_detected(self):
        obs = self._observation()
        assert obs["furniture_elements"]

    def test_3e_whole_plan_is_NOT_one_room(self):
        """The interpreter must not collapse a plan to a single room."""

        understanding = build_understanding(
            PLAN_RAW, provider="ollama", model="gemma4:12b",
            image_id="plan", source_type="uploaded",
        )
        result = interpret_architectural_vision(understanding)

        assert result["space_type"] == "plan"
        assert result["space_type"] not in ("bedroom", "living room", "kitchen")

    def test_3f_observation_does_not_classify_a_space(self):
        """The observation contract carries no space classification."""

        obs = self._observation()
        assert obs["space_classification"] is None
        assert obs["observation_only"] is True
        assert obs["interpretation_merged"] is False


# ======================================================================
# THE CONTRACT
# ======================================================================

class TestContract:

    def _observation(self):
        return build_architectural_observation(
            FACADE_RAW, provider="ollama", model="gemma4:12b",
            image_id="x", source_type="uploaded", elapsed_s=1.5,
        )

    def test_all_required_fields_are_present(self):
        obs = self._observation()
        for key in (
            "image_type",              # image type
            "visible_floors",          # visible floors
            "architectural_elements",  # architectural elements
            "furniture_elements",      # furniture elements
            "object_elements",         # object elements
            "spatial_clues",           # spatial clues
            "material_observations",   # material observations
            "texture_color_observations",  # texture / colour
            "style_indicators",        # style indicators
            "confidence",              # confidence
            "provenance",              # evidence provenance
        ):
            assert key in obs, "missing contract field: " + key

    def test_contract_identity(self):
        obs = self._observation()
        assert obs["contract"] == CONTRACT
        assert obs["image_type"] in IMAGE_TYPES

    def test_provenance_records_the_model(self):
        prov = self._observation()["provenance"]
        assert prov["provider"] == "ollama"
        assert prov["model"] == "gemma4:12b"
        assert prov["raw_preserved"] is True

    def test_it_is_observation_only(self):
        obs = self._observation()
        assert obs["observation_only"] is True
        assert obs["interpretation_merged"] is False
        assert obs["space_classification"] is None
        assert obs["possible_function"] == []
        assert obs["design_reasoning"] == []
        assert obs["geometry_authoritative"] is False
        assert obs["design_generated"] is False
        assert obs["render_requested"] is False
        assert obs["comfy_invoked"] is False

    def test_the_class_declares_its_boundaries(self):
        layer = architectural_observation_v1
        assert layer.INTERPRETS is False
        assert layer.GENERATES_DESIGN is False
        assert layer.GENERATES_GEOMETRY is False
        assert layer.RENDERS is False
        assert layer.DROPS_OBSERVATIONS is False
        assert layer.DEMOTES_TO_UNKNOWN is False


# ======================================================================
# RULE 1 — NEVER DROP
# ======================================================================

class TestNoLoss:

    def test_every_raw_phrase_is_preserved(self):
        obs = build_architectural_observation(FACADE_RAW, provider="t", model="t")

        collected = []
        for bucket in (
            "architectural_elements", "furniture_elements",
            "object_elements", "unclassified_observations",
        ):
            collected.extend(e["evidence_phrase"] for e in obs[bucket])

        for phrase in FACADE_RAW["observed"] + FACADE_RAW["architectural_elements"]:
            assert phrase in collected, "dropped observation: " + phrase

    def test_an_unrecognised_phrase_is_kept_unclassified(self):
        raw = dict(FACADE_RAW, observed=["a very unusual architectural thing"])
        obs = build_architectural_observation(raw, provider="t", model="t")

        unclassified = [e["evidence_phrase"] for e in obs["unclassified_observations"]]
        assert "a very unusual architectural thing" in unclassified

    def test_raw_output_is_preserved_verbatim(self):
        obs = build_architectural_observation(FACADE_RAW, provider="t", model="t")
        assert obs["raw_observations"] == FACADE_RAW
        assert obs["raw_observations"] is not FACADE_RAW  # a deep copy

    def test_every_input_key_survives_in_raw(self):
        obs = build_architectural_observation(FACADE_RAW, provider="t", model="t")
        for key in FACADE_RAW:
            assert key in obs["raw_observations"]


# ======================================================================
# RULE 2 — NEVER DEMOTE TO UNKNOWN
# ======================================================================

class TestNoDemotion:

    def test_a_visible_material_is_not_unknown(self):
        obs = build_architectural_observation(FACADE_RAW, provider="t", model="t")
        unknown_text = " ".join(str(u.get("name")) for u in obs["unknowns"])
        assert "concrete" not in unknown_text
        assert obs["material_observations"]

    def test_no_unverified_from_image_rewrite(self):
        obs = build_architectural_observation(FACADE_RAW, provider="t", model="t")
        assert "unverified from image" not in str(obs)

    def test_the_adapter_no_longer_emits_the_noise(self):
        u = build_understanding(
            FACADE_RAW, provider="ollama", model="gemma4:12b",
            image_id="f", source_type="uploaded",
        )
        assert "unverified from image" not in str(u.get("unresolved"))
        assert u.get("observed_attributed")

    def test_the_adapter_keeps_the_old_band_intact(self):
        """`inferred` and `classify_claim` are unchanged for old consumers."""

        from core.vision.image_understanding_v1 import classify_claim

        assert classify_claim("concrete facade")[0] == "demote"
        assert classify_claim("residential building")[0] == "demote"
        assert classify_claim("width 12 m")[0] == "reject"

        u = build_understanding(
            {"image_type": "facade_or_elevation", "observed": [],
             "inferred": ["concrete structure"], "unresolved": [],
             "confidence": "HIGH", "architectural_elements": [],
             "text_labels_if_visible": []},
            provider="t", model="t",
        )
        assert "concrete structure" in u["inferred"]


# ======================================================================
# RULE 3 — UNKNOWN ONLY WHEN EVIDENCE IS TRULY ABSENT
# ======================================================================

class TestUnknownOnlyWhenAbsent:

    def test_an_answered_uncertainty_is_not_an_unknown(self):
        obs = build_architectural_observation(FACADE_RAW, provider="t", model="t")
        unknown_text = " ".join(str(u.get("name")) for u in obs["unknowns"])
        assert "material" not in unknown_text

    def test_a_genuinely_absent_item_stays_unknown(self):
        obs = build_architectural_observation(FACADE_RAW, provider="t", model="t")
        unknown_text = " ".join(str(u.get("name")) for u in obs["unknowns"])
        assert "geographic location" in unknown_text

    def test_an_answered_uncertainty_is_recorded_as_resolved(self):
        obs = build_architectural_observation(FACADE_RAW, provider="t", model="t")
        assert obs["resolved_uncertainties"]

    def test_nothing_is_unknown_when_nothing_was_reported(self):
        obs = build_architectural_observation(
            {"image_type": "unknown", "observed": [], "inferred": [],
             "unresolved": [], "confidence": "LOW",
             "architectural_elements": [], "text_labels_if_visible": []},
            provider="t", model="t",
        )
        assert obs["unknowns"] == []


# ======================================================================
# RULE 4 — PASS-THROUGH BEFORE INTERPRETATION
# ======================================================================

class TestPassthrough:

    def test_the_passthrough_publishes_visible_phrases(self):
        understanding = build_understanding(
            FACADE_RAW, provider="ollama", model="gemma4:12b",
            image_id="f", source_type="uploaded",
        )
        obs = build_architectural_observation(understanding, provider="t", model="t")
        passthrough = visible_observations_passthrough(understanding, obs)

        assert passthrough["interpretation_applied"] is False
        assert "two-story building" in passthrough["phrases"]
        assert passthrough["visible_floors"] is not None

    def test_the_interpreter_publishes_the_passthrough(self):
        understanding = build_understanding(
            FACADE_RAW, provider="ollama", model="gemma4:12b",
            image_id="f", source_type="uploaded",
        )
        result = interpret_architectural_vision(understanding)

        assert "visible_observations" in result
        assert result["visible_observations"]["interpretation_applied"] is False

    def test_the_passthrough_survives_the_interpreter_vocabulary(self):
        """`two-story building` is not in the interpreter's closed map."""

        understanding = build_understanding(
            FACADE_RAW, provider="ollama", model="gemma4:12b",
            image_id="f", source_type="uploaded",
        )
        result = interpret_architectural_vision(understanding)

        assert "two-story building" in result["visible_observations"]["phrases"]

    def test_the_interpreter_publishes_the_observation_separately(self):
        understanding = build_understanding(
            BEDROOM_RAW, provider="ollama", model="gemma4:12b",
            image_id="b", source_type="uploaded",
        )
        result = interpret_architectural_vision(understanding)

        assert result["architectural_observation"]["contract"] == CONTRACT
        # the observation is separate from, and never merged with, the interpretation
        assert result["architectural_observation"]["interpretation_merged"] is False
        assert result["architectural_observation"]["space_classification"] is None

    def test_an_answered_floor_uncertainty_is_not_repeated(self):
        understanding = build_understanding(
            FACADE_RAW, provider="ollama", model="gemma4:12b",
            image_id="f", source_type="uploaded",
        )
        result = interpret_architectural_vision(understanding)
        assert not any("floor count" in str(u) for u in result["unknowns"])


# ======================================================================
# OBSERVATION / INTERPRETATION SEPARATION (rule 5)
# ======================================================================

class TestSeparation:

    def test_the_observation_has_no_interpretation_fields(self):
        obs = build_architectural_observation(FACADE_RAW, provider="t", model="t")
        assert obs["space_classification"] is None
        assert obs["possible_function"] == []
        assert obs["design_reasoning"] == []

    def test_the_interpretation_still_classifies(self):
        """Interpretation is allowed to classify; the observation is not."""

        understanding = build_understanding(
            BEDROOM_RAW, provider="ollama", model="gemma4:12b",
            image_id="b", source_type="uploaded",
        )
        result = interpret_architectural_vision(understanding)

        assert result["space_type"] in ("bedroom", "master bedroom")
        assert result["architectural_observation"]["space_classification"] is None

    def test_an_inferred_floor_is_not_visible_evidence(self):
        """A floor count stated only as `inferred` is never a visible floor."""

        obs = build_architectural_observation(
            {"image_type": "facade_or_elevation", "observed": ["facade visible"],
             "inferred": ["two floors"], "unresolved": [], "confidence": "HIGH",
             "architectural_elements": ["facade"], "text_labels_if_visible": []},
            provider="t", model="t",
        )
        assert obs["visible_floors"] is None

    def test_floor_detection_reads_observed_phrases(self):
        assert detect_visible_floors(["two-story building"])["count"] == 2
        assert detect_visible_floors(["three floors"])["count"] == 3
        assert detect_visible_floors(["a tall building"]) is None
