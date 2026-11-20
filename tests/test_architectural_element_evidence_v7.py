"""ARCHITECTURAL_FACADE_ELEMENT_EVIDENCE_V7 — grounded element evidence.

Demonstrated gaps these tests pin (Phase A/D)
=============================================

1. `ArchitecturalObservationV1` has **no field anywhere** that can carry a
   spatial position for an element (verified: no position/bbox/region key).
2. `ARCHITECTURAL_ELEMENT_MARKERS` has `column` but **no `pilaster`**, no
   `capital`, no `cornice`, no `entablature`, no `planter`, no `sconce`, no
   `grille`. A pilaster therefore fell to `unclassified`, and the V7 observation
   could not be represented without losing the element's identity.
3. `architectural_elements[].confidence` is `_phrase_confidence()` — **lexical**,
   derived from whether the phrase appeared in a list. Nothing distinguishes
   visually-grounded confidence from lexical echo.
4. Element entries carry no OBSERVED / INTERPRETED / UNVERIFIED class and no
   uncertainty, so an honest model ambiguity could only be flattened away.
5. No crop/parent-image provenance exists on the observation (only `image_id`).

CPU only: no Ollama call, no ComfyUI, no GPU, no image generation.
"""

import copy
import json

import pytest

from core.vision.architectural_observation_v1 import (
    ARCHITECTURAL_ELEMENT_MARKERS,
    attach_element_evidence,
    build_architectural_observation,
)
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)


# ==========================================================
# fixtures
# ==========================================================

SOURCE = {
    "sha256": "d981742208b65d27b6243db4780d59a0b901b5c195f4d153e916555141ed866b",
    "width": 890,
    "height": 510,
    "crop_box": {"left": 440, "top": 790, "right": 1330, "bottom": 1300},
    "parent": {
        "sha256": "1b304a9f2c34819015fbc1b9a15d930f4c2d9fd011572677d648748a15c0231c",
        "width": 2000,
        "height": 1682,
    },
}


def _observation(**raw):
    payload = {"observed": ["arched window"], "image_type": "facade"}
    payload.update(raw)
    return build_architectural_observation(payload, image_id="v7-crop")


def _column():
    return {
        "element": "fluted column with carved capital",
        "kind": ["column"],
        "evidence": "light stone shaft with vertical groove lines; wider carved "
                    "capital block with volute and leaf detail; projecting abacus",
        "evidence_class": "OBSERVED",
        "position": {"x": [0.25, 0.31], "y": [0.18, 0.85]},
        "uncertainty": "capital order indeterminate at this resolution",
        "confidence": 0.8,
    }


# ==========================================================
# RED — vocabulary must distinguish pilaster from column
# ==========================================================

def test_pilaster_vocabulary_exists_and_is_distinct_from_column():
    labels = dict(ARCHITECTURAL_ELEMENT_MARKERS)

    assert "pilaster" in labels
    assert "pilaster" not in labels["column"]
    assert "column" not in labels["pilaster"]


def test_a_pilaster_phrase_is_not_labelled_as_a_column():
    observation = _observation(observed=["flat pilaster with vertical panel lines"])

    kinds = [entry["kind"] for entry in observation["architectural_elements"]]

    assert ["pilaster"] in kinds
    assert not any("column" in kind for kind in kinds)


def test_the_element_vocabulary_covers_the_v7_observed_families():
    labels = dict(ARCHITECTURAL_ELEMENT_MARKERS)

    for kind in ("capital", "cornice", "entablature", "frieze", "moulding",
                 "planter", "light_fixture", "grille", "pediment", "keystone",
                 "pilaster"):
        assert kind in labels, kind

    # Balustrades reuse the existing "railing" kind rather than getting a
    # second label: they are one family, and a separate kind perturbed a legacy
    # space_type classification.
    assert "balustrade" in labels["railing"]


# ==========================================================
# RED — grounded evidence must survive mapping
# ==========================================================

def test_grounded_element_evidence_survives_mapping():
    observation = attach_element_evidence(
        _observation(), [_column()], source_image=SOURCE)

    block = observation["element_evidence"]
    entry = block["elements"][0]

    assert block["contract"] == "FacadeElementEvidenceV1"
    assert entry["element"] == "fluted column with carved capital"
    assert entry["kind"] == ["column"]
    assert entry["evidence_class"] == "OBSERVED"
    assert entry["position"] == {"x": [0.25, 0.31], "y": [0.18, 0.85]}
    assert entry["uncertainty"] == "capital order indeterminate at this resolution"
    assert entry["confidence"] == 0.8


def test_crop_and_parent_provenance_are_preserved():
    observation = attach_element_evidence(
        _observation(), [_column()], source_image=SOURCE)

    source = observation["element_evidence"]["source_image"]

    assert source["sha256"] == SOURCE["sha256"]
    assert source["crop_box"] == SOURCE["crop_box"]
    assert source["parent"]["sha256"] == SOURCE["parent"]["sha256"]
    assert (source["width"], source["height"]) == (890, 510)


# ==========================================================
# RED — nothing may be invented
# ==========================================================

def test_an_element_without_a_kind_is_not_given_one():
    observation = attach_element_evidence(
        _observation(),
        [{"element": "an unidentified pale block", "evidence": "pale rectangle",
          "evidence_class": "UNVERIFIED"}],
        source_image=SOURCE,
    )

    entry = observation["element_evidence"]["elements"][0]

    assert entry["kind"] == []
    assert entry["evidence_class"] == "UNVERIFIED"


def test_an_element_without_a_description_is_refused():
    observation = attach_element_evidence(
        _observation(),
        [{"kind": ["column"], "evidence": "shaft"}],
        source_image=SOURCE,
    )

    assert observation["element_evidence"]["elements"] == []


def test_classical_style_alone_never_creates_capital_or_cornice_elements():
    """Vocabulary recognition is not perception."""

    observation = build_architectural_observation(
        {"observed": [], "image_type": "facade", "facade_style": "neoclassical"},
        image_id="style-only",
    )

    kinds = [kind for entry in observation.get("architectural_elements") or []
             for kind in entry.get("kind") or []]

    assert "capital" not in kinds
    assert "cornice" not in kinds


def test_material_appearance_does_not_become_a_verified_species():
    observation = attach_element_evidence(
        _observation(),
        [dict(_column(), species="Carrara marble", load_bearing=True,
              evidence="light stone with horizontal ashlar joint lines")],
        source_image=SOURCE,
    )

    entry = observation["element_evidence"]["elements"][0]

    assert "species" not in entry
    assert "load_bearing" not in entry
    assert entry["evidence"] == "light stone with horizontal ashlar joint lines"


# ==========================================================
# RED — ambiguity and confidence must stay honest
# ==========================================================

def test_an_ambiguous_boundary_stays_unverified_and_keeps_its_reason():
    observation = attach_element_evidence(
        _observation(),
        [{
            "element": "horizontal division between two opening rows",
            "kind": ["cornice"],
            "evidence": "flush stone band below the planter, new window heads below",
            "evidence_class": "UNVERIFIED",
            "uncertainty": "could be a floor division or a transom within one tall window",
            "confidence": 0.9,
        }],
        source_image=SOURCE,
    )

    entry = observation["element_evidence"]["elements"][0]

    assert entry["evidence_class"] == "UNVERIFIED"
    assert "transom" in entry["uncertainty"]
    # confidence is not allowed to outrank an unresolved classification
    assert entry["confidence"] is None


def test_an_unknown_evidence_class_falls_back_to_unverified():
    observation = attach_element_evidence(
        _observation(),
        [dict(_column(), evidence_class="PROBABLY")],
        source_image=SOURCE,
    )

    assert observation["element_evidence"]["elements"][0]["evidence_class"] == \
        "UNVERIFIED"


def test_a_non_numeric_position_is_dropped_rather_than_invented():
    observation = attach_element_evidence(
        _observation(),
        [dict(_column(), position="upper left, beside the arch")],
        source_image=SOURCE,
    )

    assert observation["element_evidence"]["elements"][0]["position"] is None


def test_a_position_outside_the_image_is_rejected():
    observation = attach_element_evidence(
        _observation(),
        [dict(_column(), position={"x": [0.2, 1.4], "y": [0.1, 0.5]})],
        source_image=SOURCE,
    )

    assert observation["element_evidence"]["elements"][0]["position"] is None


def test_confidence_is_dropped_when_there_is_no_visible_evidence():
    observation = attach_element_evidence(
        _observation(),
        [dict(_column(), evidence="", confidence=0.95)],
        source_image=SOURCE,
    )

    assert observation["element_evidence"]["elements"][0]["confidence"] is None


def test_interpreted_elements_keep_no_visual_confidence():
    observation = attach_element_evidence(
        _observation(),
        [dict(_column(), evidence_class="INTERPRETED")],
        source_image=SOURCE,
    )

    entry = observation["element_evidence"]["elements"][0]

    assert entry["evidence_class"] == "INTERPRETED"
    assert entry["confidence"] is None


# ==========================================================
# GUARD — legacy behaviour untouched
# ==========================================================

def test_an_observation_without_element_evidence_is_unchanged():
    legacy = _observation()

    assert "element_evidence" not in legacy
    assert legacy["architectural_elements"]


def test_attach_does_not_mutate_the_caller_payload():
    elements = [_column()]
    before = copy.deepcopy(elements)

    attach_element_evidence(_observation(), elements, source_image=SOURCE)

    assert elements == before


def test_grounded_element_evidence_reaches_the_interpretation_output():
    """Phase E: the evidence must be reachable by the existing interpreter."""

    observation = attach_element_evidence(
        _observation(), [_column()], source_image=SOURCE)

    result = interpret_architectural_vision(observation, user_text="")
    blob = json.dumps(result)

    assert "element_evidence" in blob
    assert "fluted column with carved capital" in blob
    assert SOURCE["sha256"] in blob
