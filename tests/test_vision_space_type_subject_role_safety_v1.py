# -*- coding: utf-8 -*-
"""VISION_SPACE_TYPE_SUBJECT_ROLE_SAFETY_V1 — focused CPU tests.

THE DEFECT
----------
`_space_type_basis()` selects a scene type from a first-match loop over
space-type terms, and `_positive_sources()` treats ANY entry of a field that
contains the term as evidence for it — regardless of what the entry is ABOUT.

After DESCRIPTIVE_ARCHITECTURAL_CLAIM_RETENTION_V1 restored this claim on
facade C:

    "three stacked levels, each with a dark-glazed rectangular window
     behind a projecting balcony and a smaller rectangular window ..."

the WINDOW it describes made the whole elevation a BALCONY, because the phrase
also mentions a balcony. Facade C's accepted scene type is `unknown`.

Measured detail that makes the mechanism exact:

    "Three projecting balconies in the central bay ..."   plural  -> NO match
    "... window behind a projecting balcony ..."          singular -> MATCH

So the regression was a singular/plural accident, not a considered decision.
The vocabulary is NOT changed here (that is a separate decision); the ROLE of
the term inside the description is what must be fixed.

THE RULE THIS FILE PINS
-----------------------
An architectural element named inside a description of ANOTHER element is a
component of that description, not the subject of it. A scene type may only be
selected from an element whose OWN primary kind is that scene type.

Nothing is globally suppressed: a genuine balcony observation still classifies
as a balcony.

CPU only. No model call. No GPU. No render.
"""

import json
import os

import pytest

from core.vision.architectural_observation_v1 import build_architectural_observation
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)
from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
from core.vision.image_understanding_v1 import build_understanding
from core.vision.observation_normalizer_v1 import parse_normalization


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORPUS = os.path.join(ROOT, "runs", "vision_finished_facade_acceptance_v1")

FACADES = {
    "A": os.path.join(CORPUS, "A_neue_nationalgalerie_2022"),
    "B": os.path.join(CORPUS, "B_ref_10"),
    "C": os.path.join(CORPUS, "C_ref_14"),
    "D": os.path.join(CORPUS, "D_upload_042039a7_003"),
}

EXPECTED_SPACE_TYPE = {
    "A": "unknown",
    "B": "facade",
    "C": "unknown",
    "D": "entrance",
}


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _understanding(facade):
    """Current CPU chain on saved evidence, `generation_status` preserved."""
    folder = FACADES[facade]
    observer = _load(os.path.join(folder, "01_raw_observer.json"))
    normalizer = _load(os.path.join(folder, "02_normalizer.json"))

    diagnostics = {}
    structured = parse_normalization(
        normalizer["raw_text"], observer["raw_text"], diagnostics=diagnostics)

    return build_understanding(
        {"contract": BRIDGE_CONTRACT,
         "raw_observer": {
             "raw_text": observer["raw_text"],
             "generation_status": observer.get("generation_status"),
             "done_reason": observer.get("done_reason"),
             "raw_truncated": observer.get("raw_truncated"),
             "provider": observer.get("provider"),
             "model": observer.get("model"),
             "observer_version": observer.get("observer_version"),
             "diagnostics": observer.get("diagnostics"),
         },
         "normalization": {
             "status": "NORMALIZED",
             "structured": structured,
             "source_resolution_failures": diagnostics.get("source_resolution_failures") or [],
             "source_resolutions": diagnostics.get("source_resolutions") or [],
             "accepted_claim_count": diagnostics.get("accepted_claim_count"),
             "rejected_claim_count": diagnostics.get("rejected_claim_count"),
         }},
        provider="ollama",
        model=normalizer.get("model") or "unknown",
        image_id=os.path.basename(folder),
        source_type="other",
    )


def _interpret(understanding):
    observation = build_architectural_observation(
        understanding, upstream_understanding=understanding)
    return interpret_architectural_vision(
        dict(understanding, architectural_observation=observation))


def _synthetic(phrases):
    """A minimal understanding for a synthetic phrase list."""
    raw = {
        "image_type": "unknown",
        "observed": [],
        "inferred": [],
        "architectural_elements": list(phrases),
        "text_labels_if_visible": [],
        "observation_extras": {},
        "local_plan_reading": None,
        "confidence": "LOW",
        "provider_candidates": [],
    }
    return _interpret(raw)


def _observation(facade):
    understanding = _understanding(facade)
    return build_architectural_observation(
        understanding, upstream_understanding=understanding)


def _kinds(observation):
    out = []
    for entry in observation.get("architectural_elements") or []:
        value = entry.get("kind")
        for kind in (value if isinstance(value, list) else [value]):
            if kind and kind not in out:
                out.append(kind)
    return out


def _phrases(observation):
    return [entry.get("evidence_phrase") or ""
            for entry in observation.get("architectural_elements") or []]


# ======================================================================
# Case 1 — facade C: scene type restored, evidence retained
# ======================================================================

def test_c1_facade_c_scene_type_is_unknown():
    """The accepted baseline. NOT replaced by `facade` for specificity."""
    result = _interpret(_understanding("C"))

    assert result["space_type"] == "unknown", (
        "facade C must not be typed from a component mentioned inside a "
        "window description: %r" % (result.get("classification_basis"),)
    )


def test_c1_facade_c_retains_its_descriptive_windows():
    observation = _observation("C")

    kinds = _kinds(observation)
    phrases = " ".join(_phrases(observation)).casefold()

    assert "window" in kinds, kinds
    assert "arched" in phrases or "rectangular" in phrases


def test_c1_the_offending_claim_is_still_present():
    """The fix must not remove the evidence — only its scene-typing role."""
    understanding = _understanding("C")

    texts = " ".join(understanding.get("architectural_elements") or []).casefold()

    assert "behind a projecting balcony" in texts


def test_c1_the_claim_remains_unverified():
    understanding = _understanding("C")

    for candidate in understanding.get("provider_candidates") or []:
        if "behind a projecting balcony" not in str(candidate.get("text") or "").casefold():
            continue

        assert candidate.get("state") == "UNVERIFIED"
        assert candidate.get("grounded") is False
        assert (candidate.get("verification") or {}).get("reason") == (
            "claim_properties_not_verified")
        assert (candidate.get("verification") or {}).get("local_evidence") == []


# ======================================================================
# Case 2 — a balcony mentioned inside a window description
# ======================================================================

def test_c2_incidental_balcony_mention_does_not_define_the_scene():
    result = _synthetic([
        "A rectangular window sits behind a projecting balcony.",
    ])

    assert result["space_type"] != "balcony", (
        "the balcony is a component of the window's description, not the "
        "primary space: %r" % (result.get("classification_basis"),)
    )


def test_c2_the_same_phrase_with_a_negative_stays_out():
    result = _synthetic([
        "A rectangular window sits behind a projecting balcony.",
        "No balcony is accessible.",
    ])

    assert result["space_type"] != "balcony"


# ======================================================================
# Case 3 — a genuine balcony scene must remain classifiable
# ======================================================================

def test_c3_genuine_balcony_observation_is_still_classified():
    result = _synthetic([
        "A balcony with a stone balustrade overlooking the street.",
    ])

    assert result["space_type"] == "balcony", (
        "balcony recognition must not be globally disabled: %r"
        % (result.get("classification_basis"),)
    )


def test_c3_balcony_as_the_leading_subject_is_eligible():
    result = _synthetic([
        "balcony",
    ])

    assert result["space_type"] == "balcony"


# ======================================================================
# Case 4 — several true window descriptions
# ======================================================================

def test_c4_multiple_descriptive_windows_do_not_change_the_scene():
    result = _synthetic([
        "A rectangular window sits behind a projecting balcony.",
        "A second window overlooks the street below.",
        "A third window is set behind a balustrade.",
    ])

    assert result["space_type"] != "balcony"


def test_c4_a_window_row_does_not_become_a_space():
    result = _synthetic([
        "Four stacked rows of rectangular windows.",
    ])

    assert result["space_type"] not in ("balcony", "living room")


# ======================================================================
# Case 5 — duplicated provider paths
# ======================================================================

def test_c5_duplicate_descriptions_do_not_multiply_into_a_scene():
    phrase = "A rectangular window sits behind a projecting balcony."

    result = _synthetic([phrase, phrase, phrase])

    assert result["space_type"] != "balcony"


def test_c5_duplicates_do_not_change_a_genuine_balcony():
    phrase = "A balcony with a stone balustrade overlooking the street."

    once = _synthetic([phrase])
    thrice = _synthetic([phrase, phrase, phrase])

    assert once["space_type"] == thrice["space_type"] == "balcony"


# ======================================================================
# Case 6 — negative balcony evidence
# ======================================================================

def test_c6_negative_balcony_statements_are_not_evidence():
    result = _synthetic([
        "No balcony is visible.",
        "There is no projecting balcony on this elevation.",
    ])

    assert result["space_type"] != "balcony"


# ======================================================================
# Case 7 — A/B/C/D controls
# ======================================================================

@pytest.mark.parametrize("facade", sorted(FACADES))
def test_c7_accepted_space_types_hold(facade):
    result = _interpret(_understanding(facade))

    assert result["space_type"] == EXPECTED_SPACE_TYPE[facade], (
        "facade %s: expected %r, got %r (%r)"
        % (facade, EXPECTED_SPACE_TYPE[facade], result.get("space_type"),
           result.get("classification_basis"))
    )


@pytest.mark.parametrize("facade", sorted(FACADES))
def test_c7_confidence_is_not_upgraded(facade):
    result = _interpret(_understanding(facade))

    assert result.get("confidence") in ("LOW", "MEDIUM", "HIGH")

    if result["space_type"] == "unknown":
        assert result.get("confidence") == "LOW"


# ======================================================================
# Case 8 — retention preservation
# ======================================================================

def test_c8_d_still_retains_doors_and_windows():
    kinds = _kinds(_observation("D"))

    assert "door" in kinds, kinds
    assert "window" in kinds, kinds


def test_c8_b_still_retains_descriptive_columns():
    kinds = _kinds(_observation("B"))

    assert "column" in kinds, kinds


def test_c8_a_still_retains_descriptive_columns():
    observation = _observation("A")
    phrases = " ".join(_phrases(observation)).casefold()

    assert "column" in _kinds(observation)
    assert "slender" in phrases


@pytest.mark.parametrize("facade", sorted(FACADES))
def test_c8_no_claim_is_promoted(facade):
    understanding = _understanding(facade)

    confirmed = [c for c in understanding.get("provider_candidates") or []
                 if c.get("state") == "CONFIRMED"]

    assert confirmed == [], (
        "no provider claim may become CONFIRMED in this milestone: %r"
        % ([c.get("text") for c in confirmed],)
    )


@pytest.mark.parametrize("facade", sorted(FACADES))
def test_c8_provider_floor_reading_is_unchanged(facade):
    understanding = _understanding(facade)
    extras = understanding.get("observation_extras") or {}
    reading = extras.get("visible_floors_observation") or {}

    assert reading.get("authoritative") is False

    if facade == "C":
        assert reading.get("count") == 4
