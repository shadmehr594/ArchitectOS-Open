# -*- coding: utf-8 -*-
"""FACADE_NEGATION_TARGET_GROUNDING_V1 — focused CPU tests.

THE DEFECT
----------
Facade C's observer wrote:

    No stairs, lifts, or other vertical circulation elements are visible
    on the facade

`_claims()` matched EVERY element named anywhere in the phrase
(`_element_ids()` -> ["stair", "facade"]) and, because the phrase contains a
negation marker, gave all of them CLASS_NEGATED. `_status(["facade"])` then had
nothing but a negated claim, returned `denied`, and the chat reply printed:

    • facade — stated as not visible — confidence: not confirmed

The observer never said the facade was invisible. "On the facade" is the
LOCATION where circulation was not seen, not the thing that was not seen.

WHAT THIS FILE PINS
-------------------
A negation attaches to the element it negates, not to every element the
sentence mentions. A location named in a prepositional phrase does not inherit
the negation — and a genuine "the facade is not visible" still does.

No model call, no GPU. Real saved facade C evidence plus constructed claims.
"""

import json
import os

import pytest

from core.chat.response_adapter import ResponseAdapter
from core.vision.architectural_vision_grounding_v1 import ground_vision_evidence
from core.vision.architectural_vision_interpreter_v1 import (
    ArchitecturalVisionInterpreterV1,
)
from core.vision.image_understanding_v1 import _build_bridge_understanding
from core.vision.vision_observation_mode_v1 import build_observation


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORPUS = os.path.join(ROOT, "runs", "vision_finished_facade_acceptance_v1")

FACADE_DIRS = {
    "A": "A_neue_nationalgalerie_2022",
    "B": "B_ref_10",
    "C": "C_ref_14",
    "D": "D_upload_042039a7_003",
}

#: The real facade C statement that caused the false denial.
CIRCULATION_STATEMENT = (
    "No stairs, lifts, or other vertical circulation elements are visible "
    "on the facade"
)

EXPECTED_SPACE_TYPE = {"A": "unknown", "B": "facade", "C": "unknown", "D": "entrance"}

EXPECTED_FLOORS = {"A": 1, "B": 2, "C": None, "D": 2}

EXPECTED_ELEMENTS = {"A": 5, "B": 15, "C": 15, "D": 19}


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


def _ground(phrases, field="architectural_elements"):
    """Ground a minimal payload through the REAL grounding entry point."""

    raw = {
        "observed": [],
        "architectural_elements": [],
        "inferred": [],
        "text_labels_if_visible": [],
        "unresolved": [],
        "observation_extras": {},
    }

    raw[field] = list(phrases)

    return ground_vision_evidence(raw)


def _status_of(grounding, element_id):
    for entry in grounding["elements"]:

        if entry.get("element") == element_id:

            return entry.get("status")

    return None


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
# C1 — THE REAL FACADE C REGRESSION
# ==========================================================


def test_c1a_the_facade_is_not_denied_by_a_circulation_absence():
    """The defect, on the real saved evidence."""

    grounding = ground_vision_evidence(_understanding("C"))

    assert _status_of(grounding, "facade") != "denied", (
        "the facade is still denied because the observer said no stairs were "
        "visible on it")

    assert "facade" not in (grounding.get("denied_elements") or [])


def test_c1b_the_circulation_absence_survives():
    """The fix must not make the stairs appear."""

    grounding = ground_vision_evidence(_understanding("C"))

    assert _status_of(grounding, "stair") == "denied"


def test_c1c_the_chat_text_does_not_claim_the_facade_is_invisible():
    text = _chat_text("C")

    assert "• facade — stated as not visible" not in text, (
        "the reply still tells the user the facade was stated as not visible")

    assert "• stair run — stated as not visible" in text, (
        "the circulation absence disappeared from the reply")


def test_c1d_the_facade_is_not_reported_as_an_absence_claim():
    """The circulation statement is about circulation, not about the facade."""

    observation = build_observation(_understanding("C"), language="en")

    absence_names = {entry.get("name") for entry in observation["reported_absences"]}

    assert CIRCULATION_STATEMENT in absence_names

    unknown_names = {entry.get("name") for entry in observation["unknowns"]}

    assert "facade" not in unknown_names, (
        "the facade is still published as a stated-as-not-visible element")

    assert "stair" in unknown_names


# ==========================================================
# C2 — NEGATIVE CIRCULATION REMAINS NEGATIVE
# ==========================================================


def test_c2a_the_absence_is_still_published_as_an_absence():
    observation = build_observation(_understanding("C"), language="en")

    names = [entry.get("name") for entry in observation["reported_absences"]]

    assert CIRCULATION_STATEMENT in names

    for entry in observation["reported_absences"]:

        assert entry.get("confidence") == "not confirmed"

        assert entry.get("status") == "reported, not independently confirmed"


def test_c2b_absence_never_becomes_visible_evidence():
    observation = build_observation(_understanding("C"), language="en")

    visible = {entry.get("evidence_phrase") for entry in observation["elements"]}

    assert CIRCULATION_STATEMENT not in visible

    attributed = {entry.get("name") for entry in observation["attributed_elements"]}

    assert CIRCULATION_STATEMENT not in attributed


def test_c2c_absence_is_not_independent_corroboration():
    grounding = ground_vision_evidence(_understanding("C"))

    assert grounding.get("grounded_provider_evidence") == []

    for entry in grounding.get("elements") or []:

        if entry.get("element") in ("stair", "facade"):

            assert entry.get("status") != "visible"


# ==========================================================
# C3 — LOCATION IS NOT THE NEGATED SUBJECT
# ==========================================================


def test_c3_location_does_not_inherit_the_negation():
    grounding = _ground(["No stairs are visible on the facade."])

    assert _status_of(grounding, "stair") == "denied"

    assert _status_of(grounding, "facade") != "denied"


def test_c3b_the_location_is_not_turned_into_a_positive_claim_either():
    """Not negated is not the same as confirmed."""

    grounding = _ground(["No stairs are visible on the facade."])

    assert _status_of(grounding, "facade") in (None, "not_reported")

    visible = {entry.get("element") for entry in grounding.get("visible_elements") or []}

    assert "facade" not in visible


# ==========================================================
# C4 — A GENUINE FACADE ABSENCE IS STILL AN ABSENCE
# ==========================================================


@pytest.mark.parametrize("phrase", [
    "The facade is not visible in the image.",
    "The facade is not visible.",
    "No facade is visible.",
])
def test_c4_a_genuine_facade_absence_is_still_denied(phrase):
    """The fix must not disable facade negation."""

    grounding = _ground([phrase])

    assert _status_of(grounding, "facade") == "denied", (
        "a genuine facade absence was lost: " + phrase)


# ==========================================================
# C5 — ARCHITECTURAL LOCATION CONTROLS
# ==========================================================


@pytest.mark.parametrize("phrase,negated,location", [
    ("No windows are visible on the wall.", "window", "wall"),
    ("No doors are visible in the facade.", "entrance", "facade"),
    ("No balcony is visible on the elevation.", "balcony", "facade"),
    ("No windows are visible on the rear elevation.", "window", "facade"),
])
def test_c5_the_location_does_not_inherit_the_negation(phrase, negated, location):
    grounding = _ground([phrase])

    assert _status_of(grounding, negated) == "denied", (
        "the negated element was lost: " + phrase)

    assert _status_of(grounding, location) != "denied", (
        "the architectural location inherited the negation: " + phrase)


def test_c5b_a_location_mention_is_not_independent_confirmation():
    """A location named inside a negation is not evidence that it exists."""

    grounding = _ground(["No doors are visible in the facade."])

    assert "facade" not in (grounding.get("visible_elements") or [])


# ==========================================================
# C6 — POSITIVE EVIDENCE PRESERVED
# ==========================================================


def test_c6_a_positive_facade_observation_stays_positive():
    grounding = _ground(["The facade is clad in beige stone panels"], field="observed")

    assert _status_of(grounding, "facade") == "visible"

    assert "facade" in (grounding.get("visible_elements") or []), (
        "a positive facade observation was lost")

    entry = next(e for e in grounding["elements"] if e.get("element") == "facade")

    assert entry.get("evidence"), "its evidence provenance was dropped"


def test_c6b_a_positive_location_mention_is_unchanged():
    """Matching a positive phrase is untouched by the negation-scope rule."""

    grounding = _ground(["Windows set in the facade"])

    assert _status_of(grounding, "window") in ("unverified", "likely", "visible")

    assert _status_of(grounding, "facade") is not None


# ==========================================================
# C7 — PROVIDER TRUST
# ==========================================================


def test_c7_nothing_is_promoted_to_confirmed():
    grounding = ground_vision_evidence(_understanding("C"))

    for entry in grounding.get("elements") or []:

        if entry.get("element") in ("facade", "stair"):

            assert entry.get("status") != "visible"

    assert grounding.get("grounded_provider_evidence") == []


def test_c7b_no_local_evidence_is_created():
    grounding = ground_vision_evidence(_understanding("C"))

    assert grounding.get("grounded_provider_evidence") == []

    assert grounding.get("visible_elements") == []


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_c7c_architectural_results_are_unchanged(case):
    interpretation = ArchitecturalVisionInterpreterV1().interpret(
        _understanding(case))

    observation = interpretation["architectural_observation"]

    assert interpretation["space_type"] == EXPECTED_SPACE_TYPE[case]

    assert observation["visible_floors"].get("count") == EXPECTED_FLOORS[case]

    assert len(observation["architectural_elements"]) == EXPECTED_ELEMENTS[case]


#: Denied elements per facade AFTER the scope rule. Facade C loses only
#: `facade`; its circulation absence survives. A's negated phrase has no
#: locative ("No doors, windows, stairs, or vertical-circulation elements are
#: clearly distinguishable"), so nothing there changes. B and D deny nothing.
EXPECTED_DENIED = {
    "A": ["entrance", "kitchen", "stair"],
    "B": [],
    "C": ["stair"],
    "D": [],
}


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_c7d_denied_elements_are_exactly_the_negated_targets(case):
    """The scope rule may only remove a LOCATION from the denied list."""

    grounding = ground_vision_evidence(_understanding(case))

    assert sorted(grounding.get("denied_elements") or []) == EXPECTED_DENIED[case]
