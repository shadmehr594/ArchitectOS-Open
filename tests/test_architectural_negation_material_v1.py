# -*- coding: utf-8 -*-
"""R2_NEGATION_MATERIAL_INTEGRITY_V1 — focused CPU tests.

Two confirmed defects, one owner (`build_architectural_observation`):

  1. A negated phrase became a POSITIVE visible architectural element, because
     `status` was hard-coded to "visible" and `_labels()` matched markers
     anywhere in the phrase.
  2. Materials were extracted by matching markers anywhere in the phrase, so
     "no plaster or cladding" produced a PRESENT plaster and "no glazing"
     produced PRESENT glass.

The correction scopes every marker occurrence to its clause and ignores
occurrences inside a negation. It never invents an element or a material, and
it preserves the source claim in a negative-evidence channel.

No Ollama. No GPU. Fixtures are the authentic saved live records.
"""

import json
import os

import pytest

from core.vision.architectural_observation_v1 import (
    build_architectural_observation,
)
from core.vision.image_understanding_v1 import build_understanding
from core.vision.architectural_vision_interpreter_v1 import interpret_architectural_vision
from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIXTURES = {
    "V3": os.path.join(ROOT, "runs", "r2_live_normalizer_v13", "eye_V3_v13.json"),
    "ARM_A": os.path.join(ROOT, "runs", "r2_live_eye_v13_completion_v1", "eye_ARM_A_v13.json"),
    "ARM_B": os.path.join(ROOT, "runs", "r2_live_eye_v13_completion_v1", "eye_ARM_B_v13.json"),
    "B01": os.path.join(ROOT, "runs", "r2_live_eye_v13_completion_v1", "eye_B01_v13.json"),
}


def _observe(*phrases):
    """Drive the real builder with a minimal provider-shaped payload."""
    return build_architectural_observation(
        {"observed": list(phrases), "confidence": "LOW"},
        provider="ollama", model="qwen3.8:27b", image_id="synthetic",
        source_type="other",
    )


def _visible_kinds(observation):
    return {
        kind
        for entry in observation.get("architectural_elements") or []
        if entry.get("status") == "visible"
        for kind in (entry.get("kind") or [])
    }


def _all_element_statuses(observation):
    return {
        entry.get("evidence_phrase"): entry.get("status")
        for entry in observation.get("architectural_elements") or []
    }


def _materials(observation):
    return {
        material
        for entry in observation.get("material_observations") or []
        for material in (entry.get("materials") or [])
    }


def _negative(observation):
    return observation.get("negative_observations") or []


# ==========================================================
# RED — the two confirmed live failures
# ==========================================================

def test_RED_arm_b_absent_roof_is_not_a_visible_element():
    observation = _observe("no pitched roof")
    assert "roof" not in _visible_kinds(observation), (
        "an explicitly absent roof must not be a visible roof"
    )


def test_RED_arm_b_absent_roof_terrace_is_not_a_visible_terrace():
    observation = _observe("no visible roof terrace")
    kinds = _visible_kinds(observation)
    assert "roof" not in kinds
    assert "balcony" not in kinds


def test_RED_b01_no_plaster_does_not_create_plaster():
    observation = _observe(
        "Exposed masonry (brick / concrete block) infill walls, unfinished, "
        "no plaster or cladding")
    materials = _materials(observation)
    assert "plaster" not in materials
    assert "masonry" in materials  # the positive clause survives
    assert "brick" in materials


def test_RED_b01_no_glazing_does_not_create_glass():
    observation = _observe("Rectangular window *openings* (no glazing, no frames)")
    assert "glass" not in _materials(observation)
    assert "window" in _visible_kinds(observation)  # the opening is real


# ==========================================================
# A–D  architectural elements
# ==========================================================

def test_A_positive_pitched_roof_is_present():
    observation = _observe("Pitched roof with clay tiles")
    assert "roof" in _visible_kinds(observation)
    assert _negative(observation) == []


def test_B_explicitly_absent_pitched_roof_is_negative_only():
    observation = _observe("There is no pitched roof")
    assert "roof" not in _visible_kinds(observation)
    recorded = [e for e in _negative(observation) if "roof" in (e.get("kind") or [])]
    assert recorded, "the absent roof must be preserved as negative evidence"
    assert all(e.get("status") == "absent" for e in recorded)


def test_C_pitched_roof_not_visible_is_not_present():
    observation = _observe("Pitched roof not visible")
    assert "roof" not in _visible_kinds(observation)


def test_D_positive_roof_terrace_is_present():
    observation = _observe("Roof terrace with a brick parapet")
    kinds = _visible_kinds(observation)
    assert "roof" in kinds


def test_E_no_visible_roof_terrace_is_not_present():
    observation = _observe("No visible roof terrace")
    assert "roof" not in _visible_kinds(observation)
    assert "balcony" not in _visible_kinds(observation)


def test_positive_flat_roof_with_brick_parapet_survives():
    observation = _observe("Flat roof with a brick parapet")
    kinds = _visible_kinds(observation)
    assert "roof" in kinds
    assert "parapet" in kinds
    assert "brick" in _materials(observation)


def test_negation_with_positive_exception_keeps_the_exception():
    """'no visible columns other than the piers' — piers are real."""
    observation = _observe(
        "no visible columns other than the ground-floor piers of the arcade")
    kinds = _visible_kinds(observation)
    assert "pier" in kinds, "the exception clause names a real element"
    assert "column" not in kinds


def test_mixed_element_sentence_keeps_independent_clauses():
    observation = _observe(
        "Flat roofline with a thin parapet, no attic band, no roof terrace")
    kinds = _visible_kinds(observation)
    assert "parapet" in kinds
    assert "balcony" not in kinds


# ==========================================================
# E–I  materials
# ==========================================================

def test_real_glazed_window_keeps_glass():
    observation = _observe("Large glass window with dark metal frames")
    assert "glass" in _materials(observation)
    assert "window" in _visible_kinds(observation)


def test_window_opening_without_glazing_keeps_the_opening_not_the_glass():
    observation = _observe("Window opening without glazing")
    assert "window" in _visible_kinds(observation)
    assert "glass" not in _materials(observation)


def test_real_glass_balustrade_is_still_recognised():
    observation = _observe("Balcony with glass balustrades and dark metal canopies")
    assert "glass" in _materials(observation)


def test_explicitly_unglazed_opening_invents_no_glass():
    observation = _observe("Unglazed arched opening in the brick wall")
    assert "glass" not in _materials(observation)
    assert "brick" in _materials(observation)


def test_positive_plaster_finish_is_present():
    observation = _observe("Smooth plaster finish on the upper facade")
    assert "plaster" in _materials(observation)


def test_unfinished_facade_without_plaster_has_no_plaster():
    observation = _observe("Unfinished concrete facade with no plaster")
    assert "plaster" not in _materials(observation)
    assert "concrete" in _materials(observation)


def test_brick_wall_without_cladding_keeps_brick_only():
    observation = _observe("Brick wall without cladding")
    materials = _materials(observation)
    assert "brick" in materials
    assert "composite" not in materials
    assert "plaster" not in materials


def test_mixed_material_descriptor_preserves_both_clauses():
    observation = _observe(
        "Exposed masonry infill walls, unfinished, no plaster or cladding")
    materials = _materials(observation)
    assert "masonry" in materials
    assert "plaster" not in materials


def test_uncertain_material_claim_is_preserved():
    """CHANGED by VISION_MATERIAL_SEMANTICS_V1.

    Formerly asserted that BOTH sides of an "or" were present. That is the M3
    defect: "Possibly stone cladding, or painted concrete" offers two
    possibilities and commits to neither. Both are still preserved — verbatim,
    as alternatives — but neither is asserted, and the hedge is recorded.
    """
    observation = _observe("Possibly stone cladding, or painted concrete")

    materials = _materials(observation)

    assert "stone" not in materials
    assert "concrete" not in materials

    entries = observation.get("material_observations") or []

    alternatives = [group for entry in entries
                    for group in (entry.get("material_alternatives") or [])]

    assert alternatives == [["stone", "concrete"]], alternatives
    assert any(entry.get("hedged") is True for entry in entries)


def test_no_frames_does_not_invent_frames():
    """A mixed phrase must not smuggle "no frames" in as a present element.

    The opening itself is real, so the phrase stays a positive window element —
    but the negated part must be recorded as absence, and no glass may be
    extracted from "no glazing".
    """
    phrase = "Rectangular window openings (no glazing, no frames)"
    observation = _observe(phrase)

    assert "window" in _visible_kinds(observation)
    assert "glass" not in _materials(observation)

    absent = [e for e in _negative(observation) if e.get("evidence_phrase") == phrase]
    assert absent, "the negated part of a mixed phrase must be recorded"
    assert "glass" in (absent[0].get("materials") or [])

    # no element may be reported as a present frame
    for entry in observation.get("architectural_elements") or []:
        if entry.get("status") == "visible":
            assert "frame" not in (entry.get("kind") or [])


# ==========================================================
# The four authentic saved fixtures
# ==========================================================

def _fixture_observation(key):
    with open(FIXTURES[key], encoding="utf-8") as fh:
        record = json.load(fh)
    understanding = build_understanding(
        {"contract": BRIDGE_CONTRACT,
         "raw_observer": record["raw_observer"],
         "normalization": record["normalization"]},
        provider="ollama", model="qwen3.8:27b", image_id=key, source_type="other")
    return interpret_architectural_vision(understanding)["architectural_observation"]


def test_fixture_arm_b_has_no_visible_absent_roof():
    observation = _fixture_observation("ARM_B")
    for entry in observation["architectural_elements"]:
        phrase = (entry.get("evidence_phrase") or "").lower()
        if phrase.startswith("no ") or "no visible" in phrase:
            assert entry.get("status") != "visible", phrase


def test_fixture_b01_has_no_negated_materials():
    observation = _fixture_observation("B01")
    materials = _materials(observation)
    assert "plaster" not in materials
    assert "glass" not in materials


def test_fixture_b01_keeps_real_materials():
    observation = _fixture_observation("B01")
    materials = _materials(observation)
    assert "brick" in materials
    assert "masonry" in materials


def test_fixture_v3_keeps_its_positive_elements():
    observation = _fixture_observation("V3")
    kinds = _visible_kinds(observation)
    assert "wall" in kinds
    assert "roof" in kinds
    assert "door" in kinds


def test_fixture_arm_a_keeps_real_glass_and_stone():
    """ARM_A names both a stone building and real glass. BOTH must survive."""
    observation = _fixture_observation("ARM_A")
    materials = _materials(observation)
    assert "glass" in materials, "the glazed opening / reflections are real"
    assert "stone" in materials, "the pale ashlar building is real"


def test_all_fixtures_never_lose_every_element():
    for key in FIXTURES:
        observation = _fixture_observation(key)
        assert observation["architectural_elements"], key
        assert _visible_kinds(observation), key
