# -*- coding: utf-8 -*-
"""ARCHITECTURAL_VISUAL_INTERPRETATION_V2 — tests.

Observation -> Meaning. The three human validation scenarios plus the
contract, the no-invention rule, per-claim uncertainty and the boundaries.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.vision.architectural_observation_v1 import (
    build_architectural_observation,
    CONTRACT as OBSERVATION_CONTRACT,
)
from core.vision.architectural_visual_interpretation_v2 import (
    CONTRACT,
    IMAGE_CATEGORIES,
    BUILDING_TYPES,
    RELATIONSHIP_KINDS,
    ELEMENT_MEANINGS,
    build_architectural_visual_interpretation_v2,
    architectural_visual_interpretation_v2,
)
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)
from core.vision.image_understanding_v1 import build_understanding


def observe(raw):
    return build_architectural_observation(raw, provider="ollama", model="gemma4:12b")


# ======================================================================
# FIXTURES (the real gemma4:12b v3 outputs)
# ======================================================================

FACADE_RAW = {
    "image_type": "architectural_render_or_photo",
    "observed": [
        "two-storey building", "concrete facade", "large glass windows",
        "vertical slats", "glass balcony railing", "landscaped garden",
        "paved walkway",
    ],
    "inferred": ["residential building", "modern architectural style"],
    "unresolved": ["interior layout"],
    "confidence": "HIGH",
    "architectural_elements": [
        "concrete facade", "glass windows", "balcony", "glass balustrade",
        "vertical slats", "walkway", "boundary wall", "flat roof",
    ],
    "text_labels_if_visible": [],
    "visible_floors": "two-storey building",
    "material_observations": ["concrete facade", "glass windows", "vertical slats"],
    "style_indicators": ["rectilinear massing", "minimalist design", "large glazing"],
    "spatial_clues": [
        "ground floor open to garden", "upper floor set back",
        "walkway leading to entrance",
    ],
    "texture_color_observations": ["grey concrete texture", "dark-toned slats"],
}

MASTER_BEDROOM_RAW = {
    "image_type": "architectural_render_or_photo",
    "observed": [
        "bed with white linens", "timber slat wall", "glass partition",
        "walk-in closet", "large window", "en-suite bathroom door",
        "leaning mirror", "white ceiling",
    ],
    "inferred": ["bedroom interior"],
    "unresolved": ["exact material types"],
    "confidence": "HIGH",
    "architectural_elements": [
        "timber slat wall", "large window", "walk-in closet", "ceiling",
        "floor", "door",
    ],
    "text_labels_if_visible": [],
    "furniture_elements": ["bed", "wardrobe", "mirror", "toilet", "side table"],
    "material_observations": ["timber slats", "white ceiling"],
    "spatial_clues": [
        "bedroom adjacent to walk-in closet", "en-suite bathroom door",
    ],
}

PLAN_RAW = {
    "image_type": "floor_plan_or_sketch",
    "observed": [
        "2D floor plan", "labeled rooms", "furniture symbols", "wall outlines",
        "door swings", "dimension lines", "title block",
    ],
    "inferred": ["residential layout"],
    "unresolved": ["actual scale"],
    "confidence": "HIGH",
    "architectural_elements": ["walls", "doors", "windows", "rooms", "corridors"],
    "text_labels_if_visible": [
        "اتاق خواب", "آشپزخانه", "حمام", "سرویس", "نشیمن", "دالان",
    ],
    "furniture_elements": ["bed", "sofa", "table"],
    "spatial_clues": ["rooms side-by-side"],
}


# ======================================================================
# VALIDATION 1 — TWO-STOREY FACADE
# ======================================================================

class TestValidation1_Facade:

    def _interp(self):
        return build_architectural_visual_interpretation_v2(observe(FACADE_RAW))

    def test_1a_category_is_exterior_facade(self):
        assert self._interp()["image_category"]["value"] == "exterior_facade"

    def test_1b_floors_are_two(self):
        facade = self._interp()["facade_interpretation"]
        assert facade["floor_organization"]["value"]["count"] == 2

    def test_1c_materials_are_preserved(self):
        facade = self._interp()["facade_interpretation"]
        assert "concrete" in facade["material_composition"]["value"]
        assert "glass" in facade["material_composition"]["value"]

    def test_1d_residential_possibility(self):
        building = self._interp()["architectural_meaning"]["building_type"]
        assert building["value"] == "residential"
        assert building["confidence"] in ("LOW", "MEDIUM")   # a possibility
        assert building["evidence"]

    def test_1e_facade_composition_present(self):
        facade = self._interp()["facade_interpretation"]
        assert facade["openings"]["value"]
        assert facade["massing"]["value"]
        assert facade["style_indicators"]

    def test_1f_no_absolute_style_claim(self):
        facade = self._interp()["facade_interpretation"]
        assert facade["absolute_style_claim"] is False
        for entry in facade["style_indicators"]:
            assert "indicator" in entry["reasoning_source"]

    def test_1g_the_observation_wins_over_the_legacy_space_type(self):
        """The legacy interpreter says `balcony`; V2 says exterior_facade."""

        understanding = build_understanding(
            FACADE_RAW, provider="ollama", model="gemma4:12b", image_id="f"
        )
        result = interpret_architectural_vision(understanding)

        assert result["space_type"] == "balcony"          # legacy, unchanged
        assert result["architectural_visual_interpretation_v2"]["image_category"]["value"] == "exterior_facade"


# ======================================================================
# VALIDATION 2 — MASTER BEDROOM
# ======================================================================

class TestValidation2_MasterBedroom:

    def _interp(self):
        return build_architectural_visual_interpretation_v2(
            observe(MASTER_BEDROOM_RAW)
        )

    def test_2a_category_is_interior_space(self):
        assert self._interp()["image_category"]["value"] == "interior_space"

    def test_2b_bedroom_or_master_bedroom_possibility(self):
        space = self._interp()["architectural_meaning"]["space_understanding"]
        assert space["value"] in ("bedroom", "master bedroom")
        assert space["evidence"]

    def test_2c_bed_is_detected(self):
        meanings = {e["element_kind"]: e["meaning"] for e in self._interp()["element_meaning"]}
        assert "bed" in meanings
        assert meanings["bed"] == "sleeping area indicator"

    def test_2d_wardrobe_is_detected(self):
        meanings = {e["element_kind"]: e["meaning"] for e in self._interp()["element_meaning"]}
        assert meanings.get("wardrobe") == "storage / dressing indicator"

    def test_2e_bathroom_relation_is_formed(self):
        kinds = {r["kind"] for r in self._interp()["space_relationships"]}
        assert "privacy_clue" in kinds

    def test_2f_privacy_clues_are_present(self):
        privacy = [
            r for r in self._interp()["space_relationships"]
            if r["kind"] == "privacy_clue"
        ]
        assert privacy
        assert privacy[0]["evidence"]

    def test_2g_master_bedroom_possibility_when_suite_elements_visible(self):
        space = self._interp()["architectural_meaning"]["space_understanding"]
        assert space["value"] == "master bedroom"

    def test_2h_a_bed_alone_is_only_a_bedroom(self):
        raw = dict(MASTER_BEDROOM_RAW)
        raw = {k: v for k, v in raw.items() if k != "furniture_elements"}
        raw["furniture_elements"] = ["bed"]
        raw["architectural_elements"] = ["large window", "ceiling", "floor"]
        raw["spatial_clues"] = []

        space = build_architectural_visual_interpretation_v2(observe(raw))[
            "architectural_meaning"
        ]["space_understanding"]

        assert space["value"] == "bedroom"


# ======================================================================
# VALIDATION 3 — ARCHITECTURAL PLAN
# ======================================================================

class TestValidation3_Plan:

    def _interp(self):
        return build_architectural_visual_interpretation_v2(observe(PLAN_RAW))

    def test_3a_category_is_architectural_plan(self):
        assert self._interp()["image_category"]["value"] == "architectural_plan"

    def test_3b_multiple_spaces_are_recognised(self):
        plan = self._interp()["plan_interpretation"]
        assert plan["space_count"] >= 4
        spaces = {s["space"] for s in plan["spaces"]}
        assert {"bedroom", "kitchen", "bathroom", "living room"} <= spaces

    def test_3c_circulation_is_recognised(self):
        plan = self._interp()["plan_interpretation"]
        assert "corridor" in plan["circulation"]["value"]

    def test_3d_public_private_service_organisation(self):
        org = self._interp()["plan_interpretation"]["public_private_service"]
        assert "bedroom" in org.get("private", [])
        assert "living room" in org.get("public", [])
        assert "kitchen" in org.get("service", [])

    def test_3e_never_a_single_room(self):
        interp = self._interp()
        assert interp["plan_interpretation"]["single_room_classification"] is False
        assert interp["architectural_meaning"]["space_understanding"]["value"] != "bedroom"

    def test_3f_no_plan_is_generated(self):
        interp = self._interp()
        assert interp["plan_generated"] is False
        assert interp["design_generated"] is False
        assert interp["render_requested"] is False


# ======================================================================
# CONTRACT
# ======================================================================

class TestContract:

    def _interp(self):
        return build_architectural_visual_interpretation_v2(observe(FACADE_RAW))

    def test_identity(self):
        assert self._interp()["contract"] == CONTRACT

    def test_it_declares_the_observation_as_primary(self):
        interp = self._interp()
        assert interp["source_observation_is_primary"] is True
        assert interp["source_observation_contract"] == OBSERVATION_CONTRACT

    def test_all_required_sections_are_present(self):
        interp = self._interp()
        for key in (
            "image_category", "architectural_meaning", "element_meaning",
            "space_relationships", "facade_interpretation",
            "plan_interpretation", "claims", "unknowns",
        ):
            assert key in interp, "missing section: " + key

    def test_meaning_sections(self):
        meaning = self._interp()["architectural_meaning"]
        assert meaning["building_type"]["value"] in BUILDING_TYPES
        assert "space_understanding" in meaning

    def test_image_category_is_from_the_vocabulary(self):
        assert self._interp()["image_category"]["value"] in IMAGE_CATEGORIES

    def test_relationship_kinds_are_from_the_vocabulary(self):
        for rel in self._interp()["space_relationships"]:
            assert rel["kind"] in RELATIONSHIP_KINDS

    def test_it_never_mutates_the_observation(self):
        observation = observe(FACADE_RAW)
        before = repr(observation)
        build_architectural_visual_interpretation_v2(observation)
        assert repr(observation) == before

    def test_it_does_not_merge_with_the_observation(self):
        assert self._interp()["interpretation_merged_with_observation"] is False

    def test_boundaries(self):
        interp = self._interp()
        assert interp["geometry_authoritative"] is False
        assert interp["plan_generated"] is False
        assert interp["design_generated"] is False
        assert interp["render_requested"] is False
        assert interp["comfy_invoked"] is False
        assert interp["llm_used"] is False
        assert interp["read_only"] is True

    def test_the_class_declares_its_boundaries(self):
        layer = architectural_visual_interpretation_v2
        assert layer.REQUIRES_OBSERVATION is True
        assert layer.USES_LEGACY_FIELDS is False
        assert layer.GENERATES_DESIGN is False
        assert layer.GENERATES_GEOMETRY is False
        assert layer.GENERATES_PLAN is False
        assert layer.RENDERS is False
        assert layer.DROPS_CLAIMS is False


# ======================================================================
# UNCERTAINTY — every claim carries evidence + confidence + source
# ======================================================================

class TestUncertainty:

    def _interp(self):
        return build_architectural_visual_interpretation_v2(observe(FACADE_RAW))

    def test_every_claim_carries_the_three_fields(self):
        for claim in self._interp()["claims"]:
            assert "value" in claim
            assert "evidence" in claim
            assert "confidence" in claim
            assert "reasoning_source" in claim
            assert claim["reasoning_source"]

    def test_every_element_meaning_carries_the_three_fields(self):
        for entry in self._interp()["element_meaning"]:
            assert entry["evidence"]
            assert entry["confidence"]
            assert entry["reasoning_source"]

    def test_every_relationship_carries_evidence(self):
        for rel in self._interp()["space_relationships"]:
            assert rel["evidence"]
            assert rel["confidence"]
            assert rel["reasoning_source"]

    def test_confidence_is_a_known_level(self):
        for claim in self._interp()["claims"]:
            assert claim["confidence"] in ("LOW", "MEDIUM", "HIGH", "UNKNOWN")

    def test_an_empty_observation_yields_unknown_not_invention(self):
        interp = build_architectural_visual_interpretation_v2(
            build_architectural_observation(
                {"image_type": "unknown", "observed": [], "inferred": [],
                 "unresolved": [], "confidence": "LOW",
                 "architectural_elements": [], "text_labels_if_visible": []},
                provider="t", model="t",
            )
        )
        assert interp["architectural_meaning"]["building_type"]["value"] == "unknown"
        assert interp["architectural_meaning"]["space_understanding"]["value"] == "unknown"
        assert interp["element_meaning"] == []
        assert interp["space_relationships"] == []
        assert interp["facade_interpretation"] is None
        assert interp["unknowns"]

    def test_a_non_observation_input_is_handled_without_crashing(self):
        interp = build_architectural_visual_interpretation_v2({})
        assert interp["source_observation_is_primary"] is False
        assert interp["architectural_meaning"]["building_type"]["value"] == "unknown"

    def test_nothing_is_silently_dropped(self):
        """Every observation element either gets a meaning or is unclassified."""

        observation = observe(FACADE_RAW)
        interp = build_architectural_visual_interpretation_v2(observation)

        observed_kinds = set()
        for bucket in ("architectural_elements", "furniture_elements", "object_elements"):
            for entry in observation.get(bucket) or []:
                observed_kinds.update(entry.get("kind") or [])

        meaning_kinds = {e["element_kind"] for e in interp["element_meaning"]}

        for kind in observed_kinds:
            assert kind in meaning_kinds or kind not in ELEMENT_MEANINGS


# ======================================================================
# ELEMENT MEANING TABLE
# ======================================================================

class TestElementMeaning:

    def test_the_table_covers_the_required_examples(self):
        assert ELEMENT_MEANINGS["bed"] == "sleeping area indicator"
        assert ELEMENT_MEANINGS["wardrobe"] == "storage / dressing indicator"
        assert ELEMENT_MEANINGS["sanitary"] == "sanitary zone indicator"
        assert ELEMENT_MEANINGS["corridor"] == "circulation indicator"

    def test_wardrobe_bathroom_bedroom_yields_a_master_bedroom_possibility(self):
        interp = build_architectural_visual_interpretation_v2(
            observe(MASTER_BEDROOM_RAW)
        )
        space = interp["architectural_meaning"]["space_understanding"]
        assert space["value"] == "master bedroom"
        assert len(space["evidence"]) >= 2

    def test_meanings_cite_the_observation_phrase(self):
        interp = build_architectural_visual_interpretation_v2(observe(FACADE_RAW))
        for entry in interp["element_meaning"]:
            assert entry["observed"]
            assert entry["evidence"]


# ======================================================================
# REGRESSIONS FOUND IN LIVE VALIDATION
# ======================================================================

class TestLiveRegressions:

    def test_furniture_through_glazing_does_not_make_a_facade_a_living_room(self):
        """A sofa seen THROUGH the glazing must not win over the envelope."""

        raw = dict(FACADE_RAW)
        raw["furniture_elements"] = ["sofa", "armchairs"]
        raw["observed"] = list(FACADE_RAW["observed"]) + ["interior furniture visible"]

        interp = build_architectural_visual_interpretation_v2(observe(raw))

        assert interp["image_category"]["value"] == "exterior_facade"
        assert interp["architectural_meaning"]["space_understanding"]["value"] == "facade"

    def test_texture_is_not_an_annotation(self):
        """`light wood texture` must not match a bare `text` marker."""

        raw = dict(MASTER_BEDROOM_RAW)
        raw["texture_color_observations"] = ["light wood texture", "white bedding"]

        observation = observe(raw)

        for bucket in ("object_elements", "architectural_elements", "furniture_elements"):
            for entry in observation.get(bucket) or []:
                assert "text_label" not in (entry.get("kind") or []), entry

    def test_an_interior_room_still_resolves_from_its_elements(self):
        """The envelope rule must not swallow a genuine interior."""

        raw = dict(MASTER_BEDROOM_RAW)
        raw["image_type"] = "architectural_render_or_photo"
        raw["observed"] = ["bed with white linens", "ceiling", "floor"]

        interp = build_architectural_visual_interpretation_v2(observe(raw))

        assert interp["image_category"]["value"] == "interior_space"
        assert interp["architectural_meaning"]["space_understanding"]["value"] in (
            "bedroom", "master bedroom",
        )
