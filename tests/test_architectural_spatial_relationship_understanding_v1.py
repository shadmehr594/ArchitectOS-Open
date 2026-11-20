# -*- coding: utf-8 -*-
"""ARCHITECTURAL_SPATIAL_RELATIONSHIP_UNDERSTANDING_V1 — tests.

Visible spatial organization. Four scenarios (master bedroom · facade ·
floor plan · Case C) plus the cross-cutting invariants:

  * observation_basis[] is the ONLY source of visible facts (E1/E2)
  * confidence is LOW/MEDIUM only — never HIGH (C10)
  * the authored vocabulary carries no judgement (E3)
  * no graph duplicates another (C6/C9b)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.vision.architectural_observation_v1 import (
    build_architectural_observation,
)
from core.vision.architectural_visual_interpretation_v2 import (
    build_architectural_visual_interpretation_v2,
)
from core.vision.architectural_spatial_relationship_understanding_v1 import (
    CONTRACT,
    RELATIONSHIP_KINDS,
    ZONE_RELATION_KINDS,
    EXPOSURE_MODES,
    FACADE_COMPOSITION_KINDS,
    UNKNOWN_KINDS,
    FORBIDDEN_WORDS,
    forbidden_vocabulary_hits,
    build_architectural_spatial_relationship_understanding_v1,
    architectural_spatial_relationship_understanding_v1,
)


def understand(raw, provider="ollama", model="gemma4:12b"):
    observation = build_architectural_observation(raw, provider=provider, model=model)
    interpretation = build_architectural_visual_interpretation_v2(observation)
    return build_architectural_spatial_relationship_understanding_v1(
        observation, interpretation
    )


def units_of(result):
    return [u["unit"] for u in result["spatial_units"]]


def zones_of(result):
    return {u["unit"]: u["zone"] for u in result["spatial_units"]}


# ======================================================================
# MASTER BEDROOM
# ======================================================================

MASTER_BEDROOM = {
    "image_type": "architectural_render_or_photo",
    "observed": [
        "bed with white linens", "walk-in closet", "en-suite bathroom door",
        "toilet", "louver screen at the entrance", "large window",
        "doorway on the left",
    ],
    "inferred": [], "unresolved": [], "confidence": "HIGH",
    "architectural_elements": ["wall", "floor", "ceiling", "door", "large window", "louver"],
    "text_labels_if_visible": [],
    "furniture_elements": ["bed", "wardrobe", "toilet"],
    "spatial_clues": [
        {"kind": "adjacency", "evidence_phrase": "bedroom adjacent to walk-in closet"},
        {"kind": "visibility", "evidence_phrase": "louver screen at the entrance"},
    ],
    "material_observations": ["timber slats"],
    "provenance": {"provider": "ollama", "model": "gemma4:12b",
                   "prompt_version": "v3", "image_id": "master"},
}


class TestMasterBedroom:

    def _result(self):
        return understand(MASTER_BEDROOM)

    def test_observation_basis_exists(self):
        result = self._result()
        assert result["observation_basis"]
        facts = {entry["fact"] for entry in result["observation_basis"]}
        assert "element_visible" in facts

    def test_the_units_trace_to_visible_elements(self):
        result = self._result()
        units = units_of(result)
        assert "sleeping_area" in units       # bed
        assert "dressing" in units            # wardrobe
        assert "sanitary" in units            # toilet
        assert "access" in units              # door
        assert "screening_element" in units   # louver

    def test_the_zones_are_correct(self):
        zones = zones_of(self._result())
        assert zones["sleeping_area"] == "PRIVATE_ZONE"
        assert zones["dressing"] == "PRIVATE_ZONE"
        assert zones["sanitary"] == "SERVICE_ZONE"
        assert zones["access"] == "CIRCULATION_ZONE"

    def test_filtered_exposure_only_with_visible_filter_evidence(self):
        result = self._result()
        assert result["visibility_graph"]
        for entry in result["visibility_graph"]:
            assert entry["mode"] == "filtered"
            assert entry["mode_evidence"]
            assert any(
                "louver" in phrase.lower() for phrase in entry["mode_evidence"]
            )

    def test_no_filter_means_direct(self):
        # `entrance` is an ACCESS element but NOT a filter kind
        raw = dict(MASTER_BEDROOM)
        raw["architectural_elements"] = ["entrance", "floor", "ceiling"]
        raw["observed"] = ["bed with white linens", "an entrance"]
        raw["furniture_elements"] = ["bed"]
        raw["spatial_clues"] = []
        # NOTE: "timber slats" is labelled as a louver (a screening element),
        # so it must be cleared for a genuine no-filter case.
        raw["material_observations"] = []
        result = understand(raw)
        assert result["visibility_graph"]
        for entry in result["visibility_graph"]:
            assert entry["mode"] == "direct"
            assert entry["mode_evidence"] == []

    def test_a_door_never_creates_blocked(self):
        raw = dict(MASTER_BEDROOM)
        raw["architectural_elements"] = ["door"]
        raw["observed"] = ["bed with white linens", "a closed door"]
        raw["furniture_elements"] = ["bed"]
        raw["spatial_clues"] = []
        result = understand(raw)
        for entry in result["visibility_graph"]:
            assert entry["mode"] != "blocked"

    def test_a_full_wall_creates_blocked(self):
        # a full wall with NO filter kind present
        raw = dict(MASTER_BEDROOM)
        raw["architectural_elements"] = ["wall", "entrance"]
        raw["observed"] = ["bed with white linens", "a solid wall", "an entrance"]
        raw["furniture_elements"] = ["bed"]
        raw["spatial_clues"] = []
        raw["material_observations"] = []
        result = understand(raw)
        modes = {entry["mode"] for entry in result["visibility_graph"]}
        assert modes == {"blocked"}
        for entry in result["visibility_graph"]:
            assert entry["mode_evidence"]

    def test_a_partition_wall_is_a_filter_not_a_blocker(self):
        raw = dict(MASTER_BEDROOM)
        raw["architectural_elements"] = ["partition wall", "entrance"]
        raw["observed"] = ["bed with white linens", "a partition wall", "an entrance"]
        raw["furniture_elements"] = ["bed"]
        raw["spatial_clues"] = []
        raw["material_observations"] = []
        result = understand(raw)
        modes = {entry["mode"] for entry in result["visibility_graph"]}
        assert modes == {"filtered"}

    def test_no_privacy_principle_appears(self):
        result = self._result()
        assert result["non_claims"]["principle_asserted"] is False
        assert result["non_claims"]["observation_only"] is True

    def test_a_sequence_exists_with_the_visible_access_element(self):
        result = self._result()
        assert result["sequences"]
        sequence = result["sequences"][0]["sequence"]
        assert sequence[0] == "access"
        assert "screening_element" in sequence
        # private before service
        assert sequence.index("sleeping_area") < sequence.index("sanitary")

    def test_adjacency_is_unit_to_unit_only(self):
        result = self._result()
        kinds = {r["kind"] for r in result["relationships"]}
        assert kinds <= set(RELATIONSHIP_KINDS)
        assert "adjacency" in kinds


# ======================================================================
# FACADE
# ======================================================================

FACADE = {
    "image_type": "architectural_render_or_photo",
    "observed": [
        "two-storey building", "concrete facade", "large glass windows",
        "vertical slats", "glass balcony railing", "flat roof",
    ],
    "inferred": [], "unresolved": [], "confidence": "HIGH",
    "architectural_elements": [
        "concrete facade", "glass windows", "balcony", "vertical slats",
        "walkway", "flat roof",
    ],
    "text_labels_if_visible": [],
    "visible_floors": "two-storey building",
    "material_observations": ["concrete facade", "glass windows", "vertical slats"],
    "style_indicators": ["rectilinear massing", "minimalist design"],
    "spatial_clues": ["walkway leading to entrance"],
    "provenance": {"provider": "ollama", "model": "gemma4:12b",
                   "prompt_version": "v3", "image_id": "facade"},
}


class TestFacade:

    def _result(self):
        return understand(FACADE)

    def test_only_exterior_zones_are_inferred(self):
        """A facade may show an entrance (circulation) — but never an interior."""

        zones = {z for z in zones_of(self._result()).values() if z}
        assert zones
        assert zones <= {"EXTERNAL_ZONE", "CIRCULATION_ZONE"}

    def test_no_interior_zone_is_inferred(self):
        result = self._result()
        for zone in ("PRIVATE_ZONE", "SERVICE_ZONE", "PUBLIC_ZONE"):
            assert zone not in {z["zone"] for z in result["hierarchy"]}
            assert zone not in {z["from_zone"] for z in result["zone_graph"]}
            assert zone not in {z["to_zone"] for z in result["zone_graph"]}

    def test_floor_stacking(self):
        kinds = {e["kind"] for e in self._result()["facade_composition_graph"]}
        assert "floor_stacking" in kinds

    def test_opening_rhythm(self):
        kinds = {e["kind"] for e in self._result()["facade_composition_graph"]}
        assert "opening_rhythm" in kinds

    def test_balcony_connection(self):
        kinds = {e["kind"] for e in self._result()["facade_composition_graph"]}
        assert "balcony_connection" in kinds

    def test_solid_void_needs_both_a_solid_and_an_opening(self):
        result = self._result()
        kinds = {e["kind"] for e in result["facade_composition_graph"]}
        assert "solid_void" in kinds

        raw = dict(FACADE)
        raw["architectural_elements"] = ["concrete facade", "flat roof"]
        raw["observed"] = ["concrete facade", "flat roof"]
        raw["material_observations"] = ["concrete facade"]
        no_openings = understand(raw)
        assert "solid_void" not in {
            e["kind"] for e in no_openings["facade_composition_graph"]
        }

    def test_material_distribution_only(self):
        kinds = {e["kind"] for e in self._result()["facade_composition_graph"]}
        assert "material_distribution" in kinds
        assert "material_hierarchy" not in kinds

    def test_an_interior_has_no_facade_composition(self):
        """Found in live validation: an interior must not get one."""

        assert understand(MASTER_BEDROOM)["facade_composition_graph"] == []

    def test_a_plan_has_no_facade_composition(self):
        """Found in live validation: a drawing must not get one."""

        assert understand(PLAN)["facade_composition_graph"] == []

    def test_no_style_words_in_the_authored_payload(self):
        result = self._result()
        assert result["forbidden_vocabulary_hits"] == []


# ======================================================================
# FLOOR PLAN
# ======================================================================

PLAN = {
    "image_type": "floor_plan_or_sketch",
    "observed": ["2D floor plan", "labeled rooms", "wall outlines",
                 "door swings", "window symbols", "corridor"],
    "inferred": [], "unresolved": [], "confidence": "HIGH",
    "architectural_elements": ["walls", "doors", "windows", "rooms", "corridors"],
    "text_labels_if_visible": ["اتاق خواب", "آشپزخانه", "حمام", "نشیمن", "دالان"],
    "furniture_elements": ["bed", "sofa", "table"],
    "spatial_clues": ["rooms side-by-side"],
    "provenance": {"provider": "ollama", "model": "gemma4:12b",
                   "prompt_version": "v3", "image_id": "plan"},
}


class TestFloorPlan:

    def _result(self):
        return understand(PLAN)

    def test_readable_labels_become_units(self):
        units = units_of(self._result())
        assert "bedroom" in units
        assert "kitchen" in units
        assert "bathroom" in units
        assert "living room" in units
        assert "corridor" in units

    def test_the_zones_are_correct(self):
        zones = zones_of(self._result())
        assert zones["bedroom"] == "PRIVATE_ZONE"
        assert zones["living room"] == "PUBLIC_ZONE"
        assert zones["kitchen"] == "SERVICE_ZONE"
        assert zones["bathroom"] == "SERVICE_ZONE"
        assert zones["corridor"] == "CIRCULATION_ZONE"

    def test_hierarchy_is_emitted(self):
        hierarchy = self._result()["hierarchy"]
        assert hierarchy
        zones = [entry["zone"] for entry in hierarchy]
        assert "PUBLIC_ZONE" in zones
        assert "PRIVATE_ZONE" in zones
        # public comes before private
        assert zones.index("PUBLIC_ZONE") < zones.index("PRIVATE_ZONE")

    def test_hierarchy_units_are_unordered_sets(self):
        for entry in self._result()["hierarchy"]:
            assert entry["units"] == sorted(entry["units"])

    def test_sequence_is_emitted_with_a_visible_circulation_element(self):
        result = self._result()
        assert result["sequences"]
        sequence = result["sequences"][0]["sequence"]
        assert "corridor" in sequence or "access" in sequence

    def test_never_a_single_room(self):
        result = self._result()
        assert len([u for u in result["spatial_units"] if u["zone"]]) >= 4


# ======================================================================
# CASE C — labels only, no circulation
# ======================================================================

CASE_C = {
    "image_type": "floor_plan_or_sketch",
    "observed": ["2D floor plan", "labeled rooms"],
    "inferred": [], "unresolved": [], "confidence": "MEDIUM",
    "architectural_elements": ["rooms"],
    "text_labels_if_visible": ["اتاق خواب", "آشپزخانه", "نشیمن"],
    "spatial_clues": [],
    "provenance": {"provider": "ollama", "model": "gemma4:12b",
                   "prompt_version": "v3", "image_id": "case_c"},
}


class TestCaseC:

    def _result(self):
        return understand(CASE_C)

    def test_sequences_are_empty(self):
        assert self._result()["sequences"] == []

    def test_an_unreadable_path_unknown_is_added(self):
        unknowns = self._result()["unknowns"]
        assert any(u["kind"] == "unreadable_path" for u in unknowns)

    def test_hierarchy_still_exists(self):
        hierarchy = self._result()["hierarchy"]
        assert hierarchy
        assert any(entry["zone"] == "PRIVATE_ZONE" for entry in hierarchy)

    def test_the_units_still_resolve_from_the_labels(self):
        units = units_of(self._result())
        assert "bedroom" in units
        assert "kitchen" in units


# ======================================================================
# CROSS-CHECKS
# ======================================================================

class TestCrossChecks:

    def _all_results(self):
        return [understand(MASTER_BEDROOM), understand(FACADE),
                understand(PLAN), understand(CASE_C)]

    def test_every_evidence_phrase_exists_in_observation_basis(self):
        for result in self._all_results():
            assert result["traceability_violations"] == []

    def test_no_high_confidence_anywhere(self):
        for result in self._all_results():
            for section in ("spatial_units", "relationships", "zone_graph",
                            "visibility_graph", "hierarchy", "sequences",
                            "facade_composition_graph"):
                for entry in result[section]:
                    assert entry.get("confidence") in ("LOW", "MEDIUM"), section

    def test_the_forbidden_vocabulary_scan_passes(self):
        for result in self._all_results():
            assert result["forbidden_vocabulary_hits"] == []

    def test_the_scan_detects_a_planted_violation(self):
        payload = {
            "spatial_units": [{"unit": "sleeping_area",
                               "reasoning_source": "the privacy is protected here"}],
        }
        hits = forbidden_vocabulary_hits(payload)
        assert hits

    def test_no_duplicate_ownership_between_graphs(self):
        for result in self._all_results():
            # relationships owns unit-to-unit only (C6)
            assert {r["kind"] for r in result["relationships"]} <= set(RELATIONSHIP_KINDS)
            assert "service_relationship" not in {
                r["kind"] for r in result["relationships"]
            }
            # zone_graph owns the zone relations
            assert {z["relation"] for z in result["zone_graph"]} <= set(ZONE_RELATION_KINDS)
            # visibility_graph owns exposure (C9b)
            assert {v["mode"] for v in result["visibility_graph"]} <= set(EXPOSURE_MODES)
            # facade graph owns the composition kinds
            assert {f["kind"] for f in result["facade_composition_graph"]} <= set(
                FACADE_COMPOSITION_KINDS
            )

    def test_the_removed_sections_do_not_exist(self):
        for result in self._all_results():
            assert "privacy_observations" not in result
            assert "circulation_paths" not in result

    def test_the_contract_identity_and_sources(self):
        result = understand(MASTER_BEDROOM)
        assert result["contract"] == CONTRACT
        assert result["source_observation_contract"] == "ArchitecturalObservationV1"
        assert result["source_interpretation_contract"] == "ArchitecturalVisualInterpretationV2"

    def test_provenance_is_recorded(self):
        prov = understand(MASTER_BEDROOM)["provenance"]
        for key in ("provider", "model", "prompt_version", "image_id"):
            assert key in prov

    def test_unknown_kinds_are_from_the_vocabulary(self):
        for result in self._all_results():
            for entry in result["unknowns"]:
                assert entry["kind"] in UNKNOWN_KINDS

    def test_non_claims_always_present(self):
        for result in self._all_results():
            claims = result["non_claims"]
            assert claims["principle_asserted"] is False
            assert claims["design_generated"] is False
            assert claims["plan_generated"] is False
            assert claims["geometry_authoritative"] is False
            assert claims["render_requested"] is False
            assert claims["observation_only"] is True

    def test_the_class_declares_its_boundaries(self):
        layer = architectural_spatial_relationship_understanding_v1
        assert layer.GENERATES_DESIGN is False
        assert layer.GENERATES_PLAN is False
        assert layer.GENERATES_GEOMETRY is False
        assert layer.RENDERS is False
        assert layer.ASSERTS_PRINCIPLES is False
        assert layer.MAX_CONFIDENCE == "MEDIUM"

    def test_no_geometry_terms_in_the_payload(self):
        """Word-boundary matched: `facade` legitimately contains `cad`."""

        import re

        result = understand(MASTER_BEDROOM)
        # `non_claims` legitimately names `geometry_authoritative` (a refusal),
        # so the scan covers the authored CONTENT, not the refusal keys.
        content = {k: v for k, v in result.items() if k != "non_claims"}
        blob = str(content).lower()
        for term in ("svg", "png", "cad", "bim", "ifc", "coordinate",
                     "geometry", "render"):
            assert not re.search(r"(?<![a-z])" + term + r"(?![a-z])", blob), term

    def test_the_publisher_exposes_the_contract(self):
        from core.vision.architectural_vision_interpreter_v1 import (
            interpret_architectural_vision,
        )
        from core.vision.image_understanding_v1 import build_understanding

        understanding = build_understanding(
            MASTER_BEDROOM, provider="ollama", model="gemma4:12b", image_id="master"
        )
        result = interpret_architectural_vision(understanding)

        assert "architectural_spatial_relationship_understanding_v1" in result
        published = result["architectural_spatial_relationship_understanding_v1"]
        assert published["contract"] == CONTRACT
        # the V2 output is untouched
        assert result["architectural_visual_interpretation_v2"]["contract"] == (
            "ArchitecturalVisualInterpretationV2"
        )
