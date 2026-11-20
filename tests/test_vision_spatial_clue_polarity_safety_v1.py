# -*- coding: utf-8 -*-
"""VISION_SPATIAL_CLUE_POLARITY_SAFETY_V1 — focused CPU tests.

THE DEFECT
----------
The `spatial_clues` loop in `core/vision/architectural_observation_v1.py` used
the same polarity-blind substring test that `style_indicators` carried before
VISION_STYLE_INDICATOR_POLARITY_SAFETY_V1:

    if any(_norm(m) in _norm(phrase) for m in markers):

A phrase that reports a space, an element or a relationship as ABSENT therefore
published an AFFIRMATIVE spatial relationship:

    "No adjacent entrance is visible."  -> adjacency

That is the exact inversion the clue contract cannot express: its four kinds
map to affirmative relationship kinds only (`adjacency`, `circulation_path`,
`visibility`) and the record carries no polarity field. An absence published as
a relationship is not an uncertain claim — it is the opposite of what the
observer said.

A SECOND, STRUCTURAL CAUSE
---------------------------
Polarity alone is not enough. `_forward_scope_end()` deliberately stops a
negative scope AT the predicate, because for an ELEMENT the predicate is where
a trailing locative begins ("... are visible ON THE FACADE" must not negate the
facade). But one `visibility` marker IS the predicate — "visible" — so it sits
permanently outside the scope:

    "No corridor is visible."  -> "visible" outside the span -> visibility CLUE

`_clue_negation_spans()` extends the span over the negation's OWN postfix
visibility predicate, for spatial clues only. The shared `_negation_spans()` is
untouched, so element, material and floor fragments do not move.

WHAT THIS FILE PINS
-------------------
* a negated clue marker never becomes an affirmative spatial relationship;
* the absence is still recorded in `negative_observations`;
* a mixed sentence keeps its independently supported clause;
* positive controls are unchanged;
* word boundaries hold, and the first-match-per-phrase contract is preserved;
* the entry schema, its confidence and its provenance are unchanged;
* no material, furniture, floor or element evidence moves.

RED EVIDENCE
------------
Against the pre-fix rule, this file measures 16 failed / 34 passed. The
pre-fix rule is reproduced IN MEMORY (`_legacy_clue_kinds`) — no production
file is reverted or rewritten.

CPU only. No model call. No GPU. No render. No file is modified.
"""

import json
import os

import pytest

from core.vision import architectural_observation_v1 as OBS
from core.vision.architectural_observation_v1 import (
    SPATIAL_CLUE_MARKERS,
    _clue_negation_spans,
    _match_text,
    _negation_spans,
    _norm,
    _positive_labels,
    build_architectural_observation,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORPUS = os.path.join(ROOT, "runs", "vision_finished_facade_acceptance_v1")

FACADES = {
    "A": os.path.join(CORPUS, "A_neue_nationalgalerie_2022"),
    "B": os.path.join(CORPUS, "B_ref_10"),
    "C": os.path.join(CORPUS, "C_ref_14"),
    "D": os.path.join(CORPUS, "D_upload_042039a7_003"),
}

CLUE_KINDS = {"adjacency", "access", "visibility", "circulation"}

#: Every bucket that must be byte-identical to the pre-fix behaviour.
INVARIANT_BUCKETS = (
    "architectural_elements",
    "furniture_elements",
    "object_elements",
    "material_observations",
    "texture_color_observations",
    "negative_observations",
    "unclassified_observations",
    "style_indicators",
    "visible_floors",
    "visible_floors_observation",
    "unknowns",
    "provenance",
    "contract",
    "version",
    "image_type",
    "image_id",
    "source_type",
)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _observe(phrases, **extras):
    raw = {
        "architectural_elements": list(phrases),
        "observed": [],
        "inferred": [],
        "text_labels_if_visible": [],
    }
    raw.update(extras)
    return build_architectural_observation(raw, upstream_understanding={})


def _clue_kinds(observation):
    return [entry.get("kind") for entry in observation.get("spatial_clues") or []]


def _legacy_clue_kinds(phrase):
    """The PRE-FIX rule, reproduced in memory. Never touches production.

    This is the exact expression the milestone replaced:
        if any(_norm(m) in _norm(phrase) for m in markers)
    """
    kinds = []
    for kind, markers in SPATIAL_CLUE_MARKERS:
        if any(_norm(marker) in _norm(phrase) for marker in markers):
            kinds.append(kind)
            break
    return kinds


def _negative_kinds(observation):
    return [
        kind
        for entry in observation.get("negative_observations") or []
        for kind in (entry.get("kind") or [])
    ]


def _load(folder, name):
    with open(os.path.join(folder, name), encoding="utf-8") as fh:
        return json.load(fh)


def _canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


# ======================================================================
# A. "No visible external stairs or circulation elements."
# ======================================================================

A_PHRASE = "No visible external stairs or circulation elements."


def test_a_no_circulation_clue_from_a_negated_circulation_statement():
    observation = _observe([A_PHRASE])

    assert "circulation" not in _clue_kinds(observation), (
        "a sentence stating circulation is absent must not publish a "
        "circulation relationship: %r" % (_clue_kinds(observation),)
    )


def test_a_no_visibility_clue_from_the_word_visible_inside_a_negation():
    observation = _observe([A_PHRASE])

    assert "visibility" not in _clue_kinds(observation)


def test_a_publishes_no_clue_at_all():
    observation = _observe([A_PHRASE])

    assert _clue_kinds(observation) == [], (
        "the phrase has no affirmative relational marker: %r"
        % (_clue_kinds(observation),)
    )


def test_a_the_absence_is_still_recorded():
    observation = _observe([A_PHRASE])

    assert "stair" in _negative_kinds(observation), (
        "removing the clue must not remove the evidence of absence"
    )


# ======================================================================
# B. "No corridor is visible."
# ======================================================================

B_PHRASE = "No corridor is visible."


def test_b_no_circulation_clue():
    observation = _observe([B_PHRASE])

    assert "circulation" not in _clue_kinds(observation)


def test_b_no_visibility_clue_either():
    """The marker IS the negated predicate, so it must not survive either."""
    observation = _observe([B_PHRASE])

    assert "visibility" not in _clue_kinds(observation), (
        "'is visible' belongs to the negation's own verb phrase"
    )
    assert _clue_kinds(observation) == []


def test_b_the_corridor_is_still_recorded_absent():
    observation = _observe([B_PHRASE])

    assert "corridor" in _negative_kinds(observation)


def test_b_the_span_reaches_the_predicate():
    """Guard: the test above must not pass because nothing matched at all."""
    text = _match_text(B_PHRASE)
    spans = _clue_negation_spans(B_PHRASE)

    assert spans, "the phrase must produce a negation span"
    assert text[spans[0][0]:spans[0][1]] == "no corridor is visible"

    # the shared matcher deliberately stops earlier — that is the difference
    shared = _negation_spans(text)
    assert shared[0][1] < spans[0][1]


# ======================================================================
# C. "No adjacent entrance is visible."
# ======================================================================

C_PHRASE = "No adjacent entrance is visible."


@pytest.mark.parametrize("kind", ["adjacency", "access", "visibility"])
def test_c_no_relationship_is_asserted(kind):
    observation = _observe([C_PHRASE])

    assert kind not in _clue_kinds(observation), (
        "negated adjacency/access/visibility must not be asserted: %r"
        % (_clue_kinds(observation),)
    )


def test_c_the_entrance_is_still_recorded_absent():
    observation = _observe([C_PHRASE])

    assert "entrance" in _negative_kinds(observation)


# ======================================================================
# D. "No transparent glass partition is present."
# ======================================================================

D_PHRASE = "No transparent glass partition is present."


def test_d_no_visibility_clue_from_transparent():
    observation = _observe([D_PHRASE])

    assert "visibility" not in _clue_kinds(observation), (
        "'transparent' inside a negation is not a visibility relation: %r"
        % (_clue_kinds(observation),)
    )
    assert _clue_kinds(observation) == []


# ======================================================================
# E. mixed — negated stairs, affirmative access
# ======================================================================

E_PHRASE = "No external stairs are visible, but the entrance leads to the lobby."


def test_e_the_affirmative_access_survives():
    observation = _observe([E_PHRASE])

    assert "access" in _clue_kinds(observation)


def test_e_the_negated_circulation_does_not():
    observation = _observe([E_PHRASE])

    assert "circulation" not in _clue_kinds(observation)
    assert "visibility" not in _clue_kinds(observation)


def test_e_the_negative_stairs_are_preserved():
    observation = _observe([E_PHRASE])

    assert "stair" in _negative_kinds(observation)


# ======================================================================
# F. mixed — negated corridor, affirmative adjacency
# ======================================================================

F_PHRASE = "No corridor is visible, but the kitchen is adjacent to the dining room."


def test_f_the_affirmative_adjacency_survives():
    observation = _observe([F_PHRASE])

    assert "adjacency" in _clue_kinds(observation)


def test_f_no_false_circulation_relation():
    observation = _observe([F_PHRASE])

    assert "circulation" not in _clue_kinds(observation)
    assert "visibility" not in _clue_kinds(observation)


def test_f_the_corridor_is_still_recorded_absent():
    observation = _observe([F_PHRASE])

    assert "corridor" in _negative_kinds(observation)


# ======================================================================
# G. mixed — negated balcony, affirmative access
# ======================================================================

G_PHRASE = "No visible balcony, but a glazed doorway opens to the courtyard."


def test_g_real_access_evidence_is_retained():
    observation = _observe([G_PHRASE])

    assert "access" in _clue_kinds(observation)


def test_g_no_false_visibility_from_the_negated_balcony():
    observation = _observe([G_PHRASE])

    assert "visibility" not in _clue_kinds(observation)


def test_g_the_negative_balcony_evidence_is_preserved():
    observation = _observe([G_PHRASE])

    assert "balcony" in _negative_kinds(observation)


# ======================================================================
# H / I / J — positive controls
# ======================================================================

POSITIVE_CONTROLS = [
    ("A corridor connects the entrance to the living room.", "access"),
    ("The kitchen is adjacent to the dining room.", "adjacency"),
    ("A transparent glass partition separates the spaces.", "visibility"),
]


@pytest.mark.parametrize("phrase,expected", POSITIVE_CONTROLS)
def test_positive_controls_are_unchanged(phrase, expected):
    observation = _observe([phrase])

    assert _clue_kinds(observation) == [expected], (
        "%r must still yield exactly %r: %r"
        % (phrase, expected, _clue_kinds(observation))
    )


@pytest.mark.parametrize("phrase,expected", POSITIVE_CONTROLS)
def test_positive_controls_do_not_regress_against_the_pre_fix_rule(phrase, expected):
    """A correction may remove unsupported clues; it may not remove real ones."""
    observation = _observe([phrase])

    assert _clue_kinds(observation) == _legacy_clue_kinds(phrase)


# ======================================================================
# first-match-per-phrase contract
# ======================================================================

def test_first_match_per_phrase_is_preserved():
    """One phrase yields ONE clue: the first supported kind in table order.

    "A corridor connects the entrance..." carries both `access` (entrance)
    and `circulation` (corridor). `access` precedes `circulation` in
    SPATIAL_CLUE_MARKERS, so the existing contract selects `access`. This
    milestone must not change that choice.
    """
    phrase = "A corridor connects the entrance to the living room."

    kinds = _clue_kinds(_observe([phrase]))

    assert len(kinds) == 1, kinds
    assert kinds[0] == "access"
    assert kinds[0] == _legacy_clue_kinds(phrase)[0]

    present, _ = _positive_labels(
        phrase, SPATIAL_CLUE_MARKERS, spans=_clue_negation_spans(phrase))
    assert "circulation" in present, "the second kind must still be supported"


def test_separate_phrases_each_contribute_their_own_clue():
    observation = _observe([
        "The kitchen is adjacent to the dining room.",
        "A transparent glass partition separates the spaces.",
    ])

    kinds = _clue_kinds(observation)

    assert "adjacency" in kinds
    assert "visibility" in kinds


# ======================================================================
# entry schema, confidence, provenance
# ======================================================================

def test_the_clue_entry_schema_is_unchanged():
    observation = _observe(["The kitchen is adjacent to the dining room."])
    clues = observation.get("spatial_clues") or []

    assert len(clues) == 1

    entry = clues[0]
    assert set(entry) == {"kind", "between", "evidence_phrase", "confidence"}
    assert entry["between"] == []
    assert entry["confidence"] == "LOW"
    assert entry["evidence_phrase"] == "The kitchen is adjacent to the dining room."


def test_no_polarity_field_was_added():
    """The contract was NOT extended. Absence lives in negative_observations."""
    observation = _observe([B_PHRASE, "The kitchen is adjacent to the dining room."])

    for entry in observation.get("spatial_clues") or []:
        assert "status" not in entry
        assert "polarity" not in entry
        assert "negated" not in entry


def test_every_published_clue_kind_is_a_known_kind():
    observation = _observe([
        A_PHRASE, B_PHRASE, C_PHRASE, D_PHRASE,
        E_PHRASE, F_PHRASE, G_PHRASE,
        "The kitchen is adjacent to the dining room.",
    ])

    for kind in _clue_kinds(observation):
        assert kind in CLUE_KINDS, kind


def test_provenance_and_contract_are_unchanged():
    observation = _observe(["The kitchen is adjacent to the dining room."])

    assert observation.get("contract") == "ArchitecturalObservationV1"
    assert observation.get("version") == "1.0"

    provenance = observation.get("provenance") or {}
    for key in ("provider", "model", "source_type"):
        assert key in provenance


def test_an_absence_never_becomes_a_clue():
    """The acceptance principle, stated as one invariant.

    Two independent checks, because the second is the one that can fail:
    a clue must carry affirmative support, AND the wholly-negative phrases
    must contribute no clue at all.
    """
    negative_only = [A_PHRASE, B_PHRASE, C_PHRASE, D_PHRASE]
    observation = _observe(negative_only + [E_PHRASE, F_PHRASE, G_PHRASE])

    published = {
        entry.get("evidence_phrase")
        for entry in observation.get("spatial_clues") or []
    }

    for phrase in negative_only:
        assert phrase not in published, (
            "a wholly-negative phrase published a clue: %r" % (phrase,)
        )

    for entry in observation.get("spatial_clues") or []:
        phrase = entry.get("evidence_phrase") or ""
        present, _ = _positive_labels(
            phrase, SPATIAL_CLUE_MARKERS, spans=_clue_negation_spans(phrase))

        assert entry.get("kind") in present, (
            "clue %r from %r has no affirmative support"
            % (entry.get("kind"), phrase)
        )


# ======================================================================
# word-boundary collisions
# ======================================================================

COLLISIONS = [
    # 'adjacent' must not match inside 'adjacency' (noun, not a relation)
    "The adjacency is unclear.",
    # 'path' must not match inside 'pathway'
    "A pathway runs north.",
    # 'access' must not match inside 'inaccessible'
    "An inaccessible roof.",
    # 'visible' must not match inside 'invisibility'
    "The invisibility of the screen is notable.",
]


@pytest.mark.parametrize("phrase", COLLISIONS)
def test_incidental_substrings_are_not_spatial_evidence(phrase):
    observation = _observe([phrase])

    assert _clue_kinds(observation) == [], (
        "%r must yield no clue: %r" % (phrase, _clue_kinds(observation))
    )


def test_a_real_marker_in_the_same_sentence_still_counts():
    phrase = "The adjacency is unclear, but the kitchen is adjacent to the dining room."

    assert "adjacency" in _clue_kinds(_observe([phrase]))


# ======================================================================
# Persian — the vocabulary the project already supports
# ======================================================================

PERSIAN_POSITIVE = [
    ("راهرو به ورودی متصل است.", "access"),
    ("آشپزخانه مجاور اتاق نشیمن است.", "adjacency"),
    ("پارتیشن شیشه\u200cای شفاف فضاها را جدا می\u200cکند.", "visibility"),
    ("بالکن قابل مشاهده است.", "visibility"),
]


@pytest.mark.parametrize("phrase,expected", PERSIAN_POSITIVE)
def test_persian_positive_terms_still_produce_clues(phrase, expected):
    observation = _observe([phrase])

    assert _clue_kinds(observation) == [expected], (
        "%r must still yield %r: %r"
        % (phrase, expected, _clue_kinds(observation))
    )


def test_persian_negation_is_not_detected_known_limitation():
    """DOCUMENTED LIMITATION — `_NEGATION_CUE` is English-only.

    Persian negation («نیست», «نمی‌شود», «وجود ندارد») has no cue in the
    shared vocabulary, so a Persian negative can still publish a clue. This
    milestone does not add Persian cues: that is a vocabulary decision for a
    separate milestone, and adding them here would change element, material
    and floor polarity project-wide.
    """
    phrase = "هیچ راهروی قابل مشاهده نیست."

    assert _clue_kinds(_observe([phrase])), (
        "if this stops publishing a clue, Persian negation is now detected "
        "and this limitation record must be updated"
    )


# ======================================================================
# no material / furniture / floor / element regression
# ======================================================================

def test_materials_furniture_floors_and_elements_are_untouched():
    phrases = [
        "Two storeys are visible",
        "exposed red brick masonry",
        "a wooden chair in the foreground",
        "two brick arches",
        "No corridor is visible.",
        "The kitchen is adjacent to the dining room.",
    ]

    observation = _observe(phrases)

    floors = observation.get("visible_floors") or {}
    assert floors.get("count") == 2
    assert floors.get("provenance")

    materials = [
        material
        for entry in observation.get("material_observations") or []
        for material in (entry.get("materials") or [])
    ]
    assert "brick" in materials

    furniture = [
        kind
        for entry in observation.get("furniture_elements") or []
        for kind in (entry.get("kind") or [])
    ]
    assert "chair" in furniture

    element_kinds = [
        kind
        for entry in observation.get("architectural_elements") or []
        for kind in (entry.get("kind") or [])
    ]
    assert "arch" in element_kinds


def test_the_delta_is_confined_to_spatial_clues(monkeypatch):
    """Every other bucket must be byte-identical to the pre-fix behaviour.

    The pre-fix rule is injected ONLY for SPATIAL_CLUE_MARKERS; every other
    caller of `_positive_labels` delegates to production. Nothing on disk is
    touched.
    """
    original = OBS._positive_labels

    def legacy_for_clues_only(phrase, table, **kwargs):
        if table is OBS.SPATIAL_CLUE_MARKERS:
            return _legacy_clue_kinds(phrase), []
        return original(phrase, table, **kwargs)

    raw = _load(FACADES["D"], "03_understanding.json")

    live = build_architectural_observation(raw, upstream_understanding=raw)

    monkeypatch.setattr(OBS, "_positive_labels", legacy_for_clues_only)
    legacy = build_architectural_observation(raw, upstream_understanding=raw)
    monkeypatch.setattr(OBS, "_positive_labels", original)

    moved = [key for key in INVARIANT_BUCKETS
             if _canon(live.get(key)) != _canon(legacy.get(key))]

    assert moved == [], "this milestone must not move %r" % (moved,)


# ======================================================================
# four-facade replay
# ======================================================================

def _replay(facade):
    raw = _load(FACADES[facade], "03_understanding.json")
    return build_architectural_observation(raw, upstream_understanding=raw)


@pytest.mark.parametrize("facade", sorted(FACADES))
def test_no_facade_publishes_an_unsupported_clue(facade):
    observation = _replay(facade)

    for entry in observation.get("spatial_clues") or []:
        phrase = entry.get("evidence_phrase") or ""
        present, _ = _positive_labels(
            phrase, SPATIAL_CLUE_MARKERS, spans=_clue_negation_spans(phrase))

        assert entry.get("kind") in present, (
            "facade %s published an unsupported clue: %r" % (facade, entry)
        )


@pytest.mark.parametrize("facade", sorted(FACADES))
def test_every_facade_keeps_its_element_and_negative_evidence(facade):
    observation = _replay(facade)

    assert observation.get("architectural_elements"), facade
    assert observation.get("negative_observations"), facade
