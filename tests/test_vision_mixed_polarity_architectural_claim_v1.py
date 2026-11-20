# -*- coding: utf-8 -*-
"""MIXED_POLARITY_ARCHITECTURAL_CLAIM_SAFETY_V1 — focused CPU tests.

THE DEFECT
----------
Facade B's observer wrote:

    one central rectangular doorway, open (no door leaf visible),
    with a stone surround

The doorway is PRESENT. Its door LEAF is not visible. `claim_polarity()` tested
the whole string for a negation marker:

    if _NEGATIVE.search(text) or _NEGATIVE.search(context):
        return "ABSENT"

so one parenthetical about a component made the entire doorway ABSENT, and the
chat reply listed the doorway under "Model-reported absences".

WHAT THIS FILE PINS
-------------------
Polarity follows the architectural SUBJECT. A negation that qualifies a
subordinate component does not erase the parent element — and a genuine
"no doorway is visible" is still an absence. Nothing becomes corroborated:
polarity is not verification.

No model call, no GPU. Real saved facade B evidence plus constructed claims.
"""

import json
import os

import pytest

from core.chat.response_adapter import ResponseAdapter
from core.vision.architectural_vision_interpreter_v1 import (
    ArchitecturalVisionInterpreterV1,
)
from core.vision.image_understanding_v1 import _build_bridge_understanding
from core.vision.provider_candidate_verification_v1 import claim_polarity
from core.vision.vision_observation_mode_v1 import build_observation


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORPUS = os.path.join(ROOT, "runs", "vision_finished_facade_acceptance_v1")

FACADE_DIRS = {
    "A": "A_neue_nationalgalerie_2022",
    "B": "B_ref_10",
    "C": "C_ref_14",
    "D": "D_upload_042039a7_003",
}

DOORWAY_TEXT = (
    "one central rectangular doorway, open (no door leaf visible), "
    "with a stone surround"
)

EXPECTED_SPACE_TYPE = {"A": "unknown", "B": "facade", "C": "unknown", "D": "entrance"}

EXPECTED_FLOORS = {"A": 1, "B": 2, "C": None, "D": 2}


def _load(case, name="03_understanding.json"):
    with open(os.path.join(CORPUS, FACADE_DIRS[case], name), encoding="utf-8") as fh:
        return json.load(fh)


def _understanding(case):
    saved = _load(case)

    return _build_bridge_understanding(
        saved["visual_observer_bridge"],
        provider=saved["provider"], model=saved["model"],
        image_id=saved["image_id"], source_type=saved["source_type"],
        source_hash=saved["source_hash"],
        local_plan_reading=saved.get("local_plan_reading"),
    )


def _candidates(case):
    return [c for c in _understanding(case).get("provider_candidates") or []
            if isinstance(c, dict)]


def _doorway(case="B"):
    for candidate in _candidates(case):

        if "door leaf" in str(candidate.get("text") or ""):

            return candidate

    raise AssertionError("the saved facade B doorway claim was not found")


def _claim(text, kind=None, category="openings.doors", **extra):
    claim = {
        "text": text,
        "count": None,
        "certainty": "ASSERTED",
        "category": category,
        "kind": kind,
    }

    claim.update(extra)

    return claim


def _chat_text(case, language="en"):
    observation = build_observation(_understanding(case), language=language)

    return ResponseAdapter().build_message({
        "type": "image_observation",
        "engine": "vision+observation_mode",
        "result": observation,
        "observation": observation,
        "status": "success",
        "language": {
            "input_language": "english",
            "output_language": "english" if language == "en" else "persian",
            "guard_status": "not_applicable",
            "corrected": False,
        },
    })


# ==========================================================
# A — THE ACTUAL FACADE B CLAIM
# ==========================================================


def test_a1_the_doorway_is_not_absent_because_its_leaf_is():
    """The measured defect, on the real saved evidence."""

    assert claim_polarity(_doorway()) == "PRESENT", (
        "the whole doorway is still marked ABSENT because its door leaf is "
        "not visible")


def test_a2_the_doorway_claim_keeps_its_verbatim_wording():
    """The component absence must stay readable in the original evidence."""

    assert "no door leaf visible" in _doorway()["text"]

    assert _doorway()["text"] == DOORWAY_TEXT


def test_a3_the_doorway_is_still_unverified():
    """Polarity is not verification."""

    candidate = _doorway()

    assert candidate["state"] == "UNVERIFIED"

    assert candidate["grounded"] is False

    assert candidate["verification"]["reason"] == (
        "no_applicable_independent_corroboration")

    assert candidate["verification"]["local_evidence"] == []


# ==========================================================
# B — A MISSING COMPONENT DOES NOT ERASE ITS PRESENT PARENT
# ==========================================================


@pytest.mark.parametrize("text,kind", [
    ("A rectangular doorway is present, with no door leaf visible.", "doorway"),
    ("An open doorway without a fitted door leaf.", "doorway"),
    ("A window opening is visible, but no glazing is installed.", "window"),
    ("one central rectangular doorway, open (no door leaf visible), "
     "with a stone surround", "doorway"),
])
def test_b1_a_component_absence_does_not_negate_the_parent(text, kind):
    assert claim_polarity(_claim(text, kind=kind)) == "PRESENT", (
        "a described opening disappeared because one of its components is "
        "missing: " + text)


def test_b2_the_component_absence_is_not_discarded():
    """The sentence still says the leaf is missing — it is simply not the
    claim's subject. Nothing rewrites the text."""

    text = "An open doorway without a fitted door leaf."

    claim = _claim(text, kind="doorway")

    assert claim_polarity(claim) == "PRESENT"

    assert claim["text"] == text


# ==========================================================
# C — GENUINE PRIMARY-SUBJECT ABSENCE STAYS ABSENT
# ==========================================================


@pytest.mark.parametrize("text,kind,category", [
    ("No doorway is visible.", "doorway", "openings.doors"),
    ("The entrance opening is not visible.", "entrance", "openings.doors"),
    ("There are no windows on this wall.", "window", "openings.windows"),
    ("No doors or windows are visible.", "window", "openings.windows"),
    ("no bed", None, "furniture"),
])
def test_c1_a_genuine_absence_is_still_absent(text, kind, category):
    assert claim_polarity(_claim(text, kind=kind, category=category)) == "ABSENT", (
        "genuine absence detection was weakened: " + text)


def test_c2_a_machine_readable_zero_count_is_still_absent():
    assert claim_polarity(_claim("doorway", kind="doorway", count=0)) == "ABSENT"


def test_c3_unknown_certainty_still_wins():
    claim = _claim("maybe a doorway", kind="doorway", certainty="UNKNOWN")

    assert claim_polarity(claim) == "UNKNOWN"


# ==========================================================
# D — MIXED SUBJECTS
# ==========================================================


def test_d1_a_mixed_sentence_does_not_become_positive_for_the_absent_subject():
    """`A window is visible, but no door is visible.`

    The sentence asserts a window and denies a door. A door-kind claim must
    not be promoted to PRESENT just because the window clause is positive.
    """

    text = "A window is visible, but no door is visible."

    assert claim_polarity(_claim(text, kind="door", category="openings.doors")) == (
        "ABSENT")


def test_d2_the_present_subject_of_a_mixed_sentence_stays_present():
    """The same sentence, read as a window claim, is a positive window."""

    text = "A window is visible, but no door is visible."

    assert claim_polarity(_claim(text, kind="window", category="openings.windows")) == (
        "PRESENT")


# ==========================================================
# E — CONTEXT SAFETY
# ==========================================================


def test_e1_a_negative_context_about_another_component_does_not_flip_a_positive():
    """The observer's enclosing line qualifies the door leaf, not the doorway."""

    claim = _claim(
        "one central rectangular doorway",
        kind="doorway",
        source_context="Ground floor: one central rectangular doorway, open "
                       "(no door leaf visible), with a stone surround",
    )

    assert claim_polarity(claim) == "PRESENT"


def test_e2_a_negative_context_that_negates_the_candidate_still_negates():
    """The enclosing line is still authoritative when it denies THIS claim."""

    claim = _claim("bed", kind="bed", category="furniture",
                   source_context="no bed is present in this room")

    assert claim_polarity(claim) == "ABSENT"


def test_e3_a_positive_context_does_not_create_presence_for_an_absent_claim():
    claim = _claim("no window", kind="window", category="openings.windows",
                   source_context="the wall is plastered and no window is present")

    assert claim_polarity(claim) == "ABSENT"


# ==========================================================
# F — NO FALSE PROMOTION
# ==========================================================


def test_f1_polarity_is_not_verification():
    candidate = _doorway()

    assert candidate["state"] != "CONFIRMED"

    assert candidate["grounded"] is False


def test_f2_no_candidate_becomes_confirmed():
    for case in sorted(FACADE_DIRS):

        for candidate in _candidates(case):

            if candidate.get("state") == "CONFIRMED":

                assert candidate.get("verification", {}).get("local_evidence")


# ==========================================================
# G — ACTUAL CHAT PRESENTATION
# ==========================================================


def test_g1_the_doorway_is_no_longer_published_as_an_absence():
    observation = build_observation(_understanding("B"), language="en")

    absences = [entry.get("name") for entry in observation["reported_absences"]]

    assert DOORWAY_TEXT not in absences, (
        "the doorway is still listed as a model-reported absence")


def test_g2_the_doorway_is_published_as_a_model_reported_description():
    observation = build_observation(_understanding("B"), language="en")

    attributed = [entry.get("name") for entry in observation["attributed_elements"]]

    assert DOORWAY_TEXT in attributed

    entry = next(e for e in observation["attributed_elements"]
                 if e.get("name") == DOORWAY_TEXT)

    assert entry["confidence"] == "not confirmed"

    assert entry["status"] == "reported, not independently confirmed"


def test_g3_the_missing_leaf_stays_readable():
    text = _chat_text("B")

    assert DOORWAY_TEXT in text

    assert "no door leaf visible" in text


def test_g4_the_persian_reply_carries_the_same_correction():
    observation = build_observation(_understanding("B"), language="fa")

    absences = [entry.get("name") for entry in observation["reported_absences"]]

    attributed = [entry.get("name") for entry in observation["attributed_elements"]]

    assert DOORWAY_TEXT not in absences

    assert DOORWAY_TEXT in attributed


# ==========================================================
# H — EXISTING A/C/D CONTROLS
# ==========================================================


def test_h1_facade_c_absences_are_unchanged():
    observation = build_observation(_understanding("C"), language="en")

    names = [entry.get("name") for entry in observation["reported_absences"]]

    assert len(names) == 1

    assert "No stairs, lifts" in names[0]


def test_h2_facade_c_facade_is_still_not_denied():
    from core.vision.architectural_vision_grounding_v1 import (
        ground_vision_evidence,
    )

    grounding = ground_vision_evidence(_understanding("C"))

    assert "facade" not in (grounding.get("denied_elements") or [])

    assert "stair" in (grounding.get("denied_elements") or [])


def test_h3_facade_a_and_d_absences_are_unchanged():
    for case, expected in (("A", 4), ("D", 2)):

        observation = build_observation(_understanding(case), language="en")

        assert len(observation["reported_absences"]) == expected, (
            case + ": the absence inventory changed")


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_h4_scene_type_and_floors_are_unchanged(case):
    interpretation = ArchitecturalVisionInterpreterV1().interpret(
        _understanding(case))

    assert interpretation["space_type"] == EXPECTED_SPACE_TYPE[case]

    assert interpretation["architectural_observation"]["visible_floors"].get(
        "count") == EXPECTED_FLOORS[case]
