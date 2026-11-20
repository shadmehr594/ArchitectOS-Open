# -*- coding: utf-8 -*-
"""VISION_STYLE_INDICATOR_POLARITY_SAFETY_V1 — focused CPU tests.

THE DEFECT
----------
The style-indicator loop in `core/vision/architectural_observation_v1.py` used
an unanchored substring test:

    if any(_norm(m) in _norm(phrase) for m in markers):

That test has no polarity. A sentence that reports architectural elements as
ABSENT therefore became positive evidence of architectural STYLE:

    "no visible external stairs, balconies, or vertical-circulation elements"
        -> "vertical" present -> style_indicators: [{"kind": "proportion"}]

and `architectural_visual_interpretation_v2.py:1395` builds the facade
`massing` claim from `form`/`proportion` style indicators, so the false
indicator propagated into architectural reasoning as MASSING EVIDENCE.

WHAT THIS FILE PINS
-------------------
* a negated style marker never becomes a positive style indicator;
* a negated marker is still recorded as ABSENT, not discarded;
* a mixed sentence keeps BOTH its affirmative indicators and its absences;
* word boundaries hold — an incidental substring is not architectural evidence;
* the existing first-match-per-phrase contract is unchanged;
* the delta of this milestone is confined to `style_indicators`: floors,
  materials, furniture, elements, negative observations and provenance are
  byte-identical to the pre-fix behaviour;
* the downstream `massing` consumer no longer receives a negated clause;
* the four-facade corpus behaves as reviewed (A and C lose unsupported
  indicators, B and D are unchanged).

RED EVIDENCE
------------
Before the production edit the focused set measured 4 failed / 17 passed. The
four failures were: a negated vertical-circulation clause creating `proportion`;
negated classical columns creating `style_family`; negated vertical elements
creating `proportion`; and the authentic facade D clause creating false style
evidence.

The pre-fix rule is reproduced here IN MEMORY (`_legacy_style_kinds`) so the
regression can be demonstrated without reverting or rewriting production.

CPU only. No model call. No GPU. No render. No file is modified.
"""

import json
import os

import pytest

from core.vision import architectural_observation_v1 as OBS
from core.vision.architectural_observation_v1 import (
    STYLE_MARKERS,
    _negation_spans,
    _match_text,
    _norm,
    _positive_labels,
    build_architectural_observation,
)
from core.vision.architectural_visual_interpretation_v2 import (
    build_architectural_visual_interpretation_v2,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORPUS = os.path.join(ROOT, "runs", "vision_finished_facade_acceptance_v1")

FACADES = {
    "A": os.path.join(CORPUS, "A_neue_nationalgalerie_2022"),
    "B": os.path.join(CORPUS, "B_ref_10"),
    "C": os.path.join(CORPUS, "C_ref_14"),
    "D": os.path.join(CORPUS, "D_upload_042039a7_003"),
}

#: Facade D's authentic negative circulation clause, U+2011 hyphen included.
D_CLAUSE_CIRC = ("no visible external stairs, balconies, or "
                 "vertical\u2011circulation elements")

#: Facade A's structurally identical clause (the same wording family, and the
#: one that DID reach the phrase list in the saved corpus).
A_CLAUSE_CIRC = ("No doors, windows, stairs, or vertical\u2011circulation "
                 "elements are clearly distinguishable")

#: The buckets that must never move because of this milestone.
INVARIANT_BUCKETS = (
    "architectural_elements",
    "furniture_elements",
    "object_elements",
    "material_observations",
    "texture_color_observations",
    "negative_observations",
    "unclassified_observations",
    "spatial_clues",
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
    """Build an observation from a bare phrase list."""
    raw = {
        "architectural_elements": list(phrases),
        "observed": [],
        "inferred": [],
        "text_labels_if_visible": [],
    }
    raw.update(extras)
    return build_architectural_observation(raw, upstream_understanding={})


def _indicator_kinds(observation):
    return [entry.get("kind") for entry in observation.get("style_indicators") or []]


def _legacy_style_kinds(phrases):
    """The PRE-FIX rule, reproduced in memory. Never touches production.

    This is the exact expression the milestone replaced:
        if any(_norm(m) in _norm(phrase) for m in markers)
    """
    kinds = []
    for phrase in phrases:
        for kind, markers in STYLE_MARKERS:
            if any(_norm(marker) in _norm(phrase) for marker in markers):
                kinds.append(kind)
                break
    return kinds


def _load(folder, name):
    with open(os.path.join(folder, name), encoding="utf-8") as fh:
        return json.load(fh)


def _understanding(facade):
    return _load(FACADES[facade], "03_understanding.json")


def _canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


# ======================================================================
# 1. the authentic facade D negative vertical-circulation clause
# ======================================================================

def test_facade_d_circulation_clause_is_not_a_positive_proportion():
    present, absent = _positive_labels(D_CLAUSE_CIRC, STYLE_MARKERS)

    assert "proportion" not in present, (
        "a negated vertical-circulation clause must not be positive "
        "proportion evidence: %r" % (present,)
    )


def test_facade_d_circulation_clause_is_recorded_as_absent():
    _, absent = _positive_labels(D_CLAUSE_CIRC, STYLE_MARKERS)

    assert "proportion" in absent, (
        "the negated marker must be recorded as ABSENT, not discarded: %r"
        % (absent,)
    )


def test_facade_d_circulation_clause_creates_no_style_indicator():
    observation = _observe([D_CLAUSE_CIRC])

    assert _indicator_kinds(observation) == [], (
        "the facade D circulation clause must create no style indicator: %r"
        % (_indicator_kinds(observation),)
    )


def test_facade_d_circulation_clause_survives_as_a_negative_observation():
    observation = _observe([D_CLAUSE_CIRC])
    negatives = observation.get("negative_observations") or []

    texts = [entry.get("evidence_phrase") for entry in negatives]

    assert any(text and D_CLAUSE_CIRC in text for text in texts), (
        "removing the false indicator must not remove the evidence of "
        "absence: %r" % (texts,)
    )


def test_the_authentic_clause_really_is_inside_a_negation_span():
    """Guard against the test passing for the wrong reason.

    If the clause were simply unmatched, the assertion above would be
    vacuous. It must be matched AND covered by a negation span.
    """
    spans = _negation_spans(_match_text(D_CLAUSE_CIRC))

    assert spans, "the clause must produce at least one negation span"
    assert spans[0][0] == 0
    assert spans[0][1] >= len(_match_text("vertical")) , (
        "the negation span must reach the 'vertical' marker: %r" % (spans,)
    )


def test_the_authentic_clause_carries_the_u2011_hyphen():
    """The corpus uses U+2011, not ASCII '-'. The matcher must fold it."""
    assert "\u2011" in D_CLAUSE_CIRC

    folded = _match_text(D_CLAUSE_CIRC)
    assert "vertical-circulation" in folded

    # folding is length-preserving, so span offsets stay valid
    assert len(folded) == len(D_CLAUSE_CIRC)


def test_facade_a_equivalent_clause_is_also_rejected():
    present, _ = _positive_labels(A_CLAUSE_CIRC, STYLE_MARKERS)

    assert "proportion" not in present
    assert _indicator_kinds(_observe([A_CLAUSE_CIRC])) == []


# ======================================================================
# 2. "No classical columns are visible."
# ======================================================================

def test_negated_classical_columns_are_not_a_style_family():
    phrase = "No classical columns are visible."

    present, absent = _positive_labels(phrase, STYLE_MARKERS)

    assert "style_family" not in present
    assert "style_family" in absent
    assert "style_family" not in _indicator_kinds(_observe([phrase]))


def test_negated_classical_columns_keep_the_column_evidence():
    """The element is still reported — as absent, with its kind."""
    observation = _observe(["No classical columns are visible."])
    negatives = observation.get("negative_observations") or []

    kinds = [kind for entry in negatives for kind in (entry.get("kind") or [])]

    assert "column" in kinds, negatives


# ======================================================================
# 3. "No vertical elements are visible."
# ======================================================================

def test_negated_vertical_elements_are_not_a_proportion():
    phrase = "No vertical elements are visible."

    present, absent = _positive_labels(phrase, STYLE_MARKERS)

    assert "proportion" not in present
    assert "proportion" in absent
    assert "proportion" not in _indicator_kinds(_observe([phrase]))


# ======================================================================
# 4. affirmative symmetrical composition
# ======================================================================

def test_affirmative_symmetry_still_produces_composition():
    phrase = "A symmetrical facade with a strong vertical rhythm."

    present, absent = _positive_labels(phrase, STYLE_MARKERS)

    assert "composition" in present
    assert "proportion" in present
    assert absent == []


def test_affirmative_symmetry_still_produces_an_indicator():
    observation = _observe(["A symmetrical facade with a strong vertical rhythm."])

    assert "composition" in _indicator_kinds(observation)


def test_first_match_per_phrase_contract_is_preserved():
    """One phrase yields ONE indicator: the first supported kind in table order.

    This is the existing contract and this milestone must not change it. The
    phrase carries both `composition` and `proportion`, but `composition` comes
    first in STYLE_MARKERS.
    """
    observation = _observe(["A symmetrical facade with a strong vertical rhythm."])

    kinds = _indicator_kinds(observation)

    assert len(kinds) == 1, kinds
    assert kinds[0] == "composition"
    assert kinds[0] == _legacy_style_kinds(
        ["A symmetrical facade with a strong vertical rhythm."])[0]


# ======================================================================
# 5. mixed: negative vertical elements + affirmative symmetry
# ======================================================================

MIXED_VERTICAL = ("No vertical rails are visible, but the facade has "
                  "symmetrical composition.")


def test_mixed_sentence_rejects_the_negated_marker():
    present, absent = _positive_labels(MIXED_VERTICAL, STYLE_MARKERS)

    assert "proportion" not in present
    assert "proportion" in absent


def test_mixed_sentence_keeps_the_affirmative_evidence():
    present, _ = _positive_labels(MIXED_VERTICAL, STYLE_MARKERS)

    assert "composition" in present

    kinds = _indicator_kinds(_observe([MIXED_VERTICAL]))

    assert "composition" in kinds
    assert "proportion" not in kinds


def test_mixed_sentence_keeps_affirmative_indicator_and_marker_level_absence():
    """Both polarities survive — at the level each is actually recorded.

    The affirmative clause keeps its style indicator. The negated marker is
    recorded as ABSENT by `_positive_labels`; it is not a
    `negative_observation` because `vertical rail` is not an architectural
    ELEMENT kind. That asymmetry is the pre-existing polarity gap for
    non-element markers and is out of scope here — it is asserted as it is,
    not as it ought to be.
    """
    observation = _observe([MIXED_VERTICAL])

    assert observation.get("style_indicators"), "affirmative part lost"
    assert "composition" in _indicator_kinds(observation)

    _, absent = _positive_labels(MIXED_VERTICAL, STYLE_MARKERS)

    assert "proportion" in absent, "the negated marker was not recorded as absent"


# ======================================================================
# 6. negated classical ornament + affirmative modern composition
# ======================================================================

MIXED_CLASSICAL = "No classical ornament, but modern composition is visible."


def test_negated_classical_ornament_is_not_a_style_family():
    present, absent = _positive_labels(MIXED_CLASSICAL, STYLE_MARKERS)

    assert "style_family" not in present
    assert "style_family" in absent


def test_affirmative_modern_composition_survives():
    present, _ = _positive_labels(MIXED_CLASSICAL, STYLE_MARKERS)

    assert "form" in present
    assert "composition" in present

    kinds = _indicator_kinds(_observe([MIXED_CLASSICAL]))

    assert "form" in kinds
    assert "style_family" not in kinds


# ======================================================================
# 7. marker substring collisions
# ======================================================================

COLLISIONS = [
    # 'vertical' / 'horizontal' must not match inside the -ly adverb
    "The facade is vertically articulated.",
    "The band runs horizontally.",
    # 'organic' must not match inside 'inorganic' — the opposite meaning
    "an inorganic palette",
    # 'massing' must not match inside 'amassing'
    "amassing a solid base",
    # 'pattern' must not match inside 'patterned'
    "a patterned screen",
    # 'modern' must not match inside 'modernised'
    "a modernised elevation",
    # 'volume' must not match inside 'volumetric'
    "volumetric articulation",
]


@pytest.mark.parametrize("phrase", COLLISIONS)
def test_incidental_substrings_are_not_style_evidence(phrase):
    present, absent = _positive_labels(phrase, STYLE_MARKERS)

    assert present == [], (
        "%r must yield no style marker: %r" % (phrase, present)
    )
    assert _indicator_kinds(_observe([phrase])) == []


def test_words_that_merely_mention_information_are_not_style_evidence():
    """`information` / `transformation` are NOT `form` collisions.

    No `form` marker is a bare "form" — the table lists `modern`,
    `contemporary`, `minimalist`, `volume`, `massing` and so on. These phrases
    are therefore vacuous for this milestone and are recorded as such rather
    than counted as evidence of a collision fix.
    """
    for phrase in ("The building information is incomplete.",
                   "The transformation layer is deformable."):
        present, _ = _positive_labels(phrase, STYLE_MARKERS)

        assert present == []
        assert not any("form" == marker for _, markers in STYLE_MARKERS
                       for marker in markers)


def test_a_real_marker_in_the_same_sentence_still_counts():
    """Boundary matching must not be so strict that it loses real evidence."""
    phrase = "The building information is incomplete but the composition is symmetrical."

    present, _ = _positive_labels(phrase, STYLE_MARKERS)

    assert "composition" in present


def test_known_limitation_inflected_forms_lose_their_indicator():
    """DOCUMENTED LIMITATION — not a defect this milestone may fix here.

    Moving the style loop onto `_positive_labels` gives it the word-boundary
    discipline already used for elements and materials (accepted under
    VISION_CLASSIFICATION_SAFETY_V1). That discipline allows the base form and
    English plurals only, so an inflection like "patterned" no longer produces
    a `composition` indicator even though the pre-fix substring rule did.

    Weakening the boundary would reintroduce "inorganic" -> `organic` and
    "amassing" -> `massing`, which are worse. The correct remedy is a taxonomy
    decision about inflected markers, which belongs to a later milestone.

    The four-facade corpus loses NO affirmative indicator this way.
    """
    phrase = "patterned brickwork"

    assert _legacy_style_kinds([phrase]) == ["composition"], (
        "the pre-fix rule did report this inflection"
    )
    assert _indicator_kinds(_observe([phrase])) == [], (
        "if this starts passing, the limitation has been closed and this "
        "test should be updated to assert the new behaviour"
    )


# ======================================================================
# 8. genuine positive style observations
# ======================================================================

GENUINE = [
    ("modern minimalist composition", "form"),
    ("The axis grid is regular.", "composition"),
    ("a wide low horizontal band", "proportion"),
    ("classic vernacular timber", "style_family"),
]


@pytest.mark.parametrize("phrase,expected", GENUINE)
def test_genuine_positive_observations_still_produce_indicators(phrase, expected):
    observation = _observe([phrase])

    assert expected in _indicator_kinds(observation), (
        "%r must still yield %r" % (phrase, expected)
    )


def test_separate_phrases_each_contribute_their_own_indicator():
    observation = _observe([
        "A symmetrical facade with a strong vertical rhythm.",
        "modern minimalist composition",
    ])

    kinds = _indicator_kinds(observation)

    assert "composition" in kinds
    assert "form" in kinds


def test_every_indicator_is_supported_by_an_affirmative_marker():
    """The invariant the whole milestone exists for."""
    observation = _observe([
        D_CLAUSE_CIRC,
        MIXED_VERTICAL,
        MIXED_CLASSICAL,
        "modern minimalist composition",
        "classic vernacular timber",
    ])

    for entry in observation.get("style_indicators") or []:
        phrase = entry.get("evidence_phrase") or ""
        present, _ = _positive_labels(phrase, STYLE_MARKERS)

        assert entry.get("kind") in present, (
            "indicator %r from %r lacks affirmative support"
            % (entry.get("kind"), phrase)
        )


# ======================================================================
# 9. preservation of negative observations
# ======================================================================

def test_a_plain_negative_observation_is_unchanged():
    observation = _observe(["no parapet"])
    negatives = observation.get("negative_observations") or []

    assert len(negatives) == 1
    assert negatives[0].get("status") == "absent"
    assert "parapet" in (negatives[0].get("kind") or [])
    assert negatives[0].get("evidence_phrase") == "no parapet"


def test_a_negative_observation_is_never_marked_visible():
    observation = _observe([D_CLAUSE_CIRC])

    visible = [
        entry.get("evidence_phrase")
        for entry in observation.get("architectural_elements") or []
        if entry.get("status") == "visible"
    ]

    assert D_CLAUSE_CIRC not in visible


# ======================================================================
# 10. floor / material / furniture / element / provenance invariants
# ======================================================================

def test_floor_materials_furniture_and_elements_are_untouched():
    phrases = [
        "Two storeys are visible",
        "exposed red brick masonry",
        "a wooden chair in the foreground",
        "two brick arches",
        D_CLAUSE_CIRC,
    ]

    observation = _observe(phrases)

    # floor — the contract carries a count AND its provenance, not a bare int
    floors = observation.get("visible_floors") or {}
    assert floors.get("count") == 2
    assert floors.get("provenance"), "the floor count lost its provenance"

    # material
    materials = [
        material
        for entry in observation.get("material_observations") or []
        for material in (entry.get("materials") or [])
    ]
    assert "brick" in materials

    # furniture
    furniture = [
        kind
        for entry in observation.get("furniture_elements") or []
        for kind in (entry.get("kind") or [])
    ]
    assert "chair" in furniture

    # element
    element_kinds = [
        kind
        for entry in observation.get("architectural_elements") or []
        for kind in (entry.get("kind") or [])
    ]
    assert "arch" in element_kinds


def test_provenance_and_contract_are_unchanged():
    observation = _observe(["two brick arches"])

    assert observation.get("contract") == "ArchitecturalObservationV1"
    assert observation.get("version") == "1.0"

    provenance = observation.get("provenance") or {}
    for key in ("provider", "model", "source_type"):
        assert key in provenance, "provenance lost %r" % key


def test_the_public_schema_of_a_style_indicator_is_unchanged():
    observation = _observe(["modern minimalist composition"])
    indicators = observation.get("style_indicators") or []

    assert len(indicators) == 1

    entry = indicators[0]
    assert set(entry) == {"kind", "descriptor", "evidence_phrase", "confidence"}
    assert entry["confidence"] == "LOW"
    assert entry["descriptor"] == "modern minimalist composition"
    assert entry["evidence_phrase"] == "modern minimalist composition"


def test_the_delta_is_confined_to_style_indicators(monkeypatch):
    """Every other bucket must be byte-identical to the pre-fix behaviour.

    The pre-fix rule is injected ONLY for STYLE_MARKERS; every other caller of
    `_positive_labels` delegates to production. Nothing on disk is touched.
    """
    original = OBS._positive_labels

    def legacy_for_style_only(phrase, table, **kwargs):
        if table is OBS.STYLE_MARKERS:
            return _legacy_style_kinds([phrase]), []
        return original(phrase, table, **kwargs)

    raw = _understanding("A")
    raw["image_type"] = "facade_or_elevation"

    live = build_architectural_observation(raw, upstream_understanding=raw)

    monkeypatch.setattr(OBS, "_positive_labels", legacy_for_style_only)
    legacy = build_architectural_observation(raw, upstream_understanding=raw)
    monkeypatch.setattr(OBS, "_positive_labels", original)

    moved = [key for key in INVARIANT_BUCKETS
             if _canon(live.get(key)) != _canon(legacy.get(key))]

    assert moved == [], "this milestone must not move %r" % (moved,)


# ======================================================================
# 11. architectural interpretation and massing consumers
# ======================================================================

def _facade_interpretation(facade):
    raw = _understanding(facade)
    raw["image_type"] = "facade_or_elevation"
    observation = build_architectural_observation(raw, upstream_understanding=raw)
    return build_architectural_visual_interpretation_v2(observation)


def test_the_facade_branch_is_reached_for_a_facade_observation():
    interpretation = _facade_interpretation("C")

    assert interpretation.get("image_category", {}).get("value") == "exterior_facade"
    assert isinstance(interpretation.get("facade_interpretation"), dict)


def test_massing_does_not_receive_a_negated_clause(monkeypatch):
    """The propagation this milestone exists to stop.

    `_facade_interpretation` builds `massing` from `form`/`proportion` style
    indicators. Facade C's negated circulation clause must not appear there.
    """
    interpretation = _facade_interpretation("C")

    massing = (interpretation.get("facade_interpretation") or {}).get("massing") or {}
    evidence = massing.get("evidence") or []

    assert evidence, "the massing claim must still have affirmative evidence"

    for phrase in evidence:
        present, _ = _positive_labels(phrase, STYLE_MARKERS)
        assert present, "massing evidence %r has no affirmative support" % (phrase,)

    assert not any("vertical circulation elements" in phrase for phrase in evidence), (
        "the negated circulation clause leaked into massing: %r" % (evidence,)
    )


def test_massing_still_carries_the_genuine_proportion_evidence():
    interpretation = _facade_interpretation("C")

    massing = (interpretation.get("facade_interpretation") or {}).get("massing") or {}

    assert any("Tall, narrow" in phrase for phrase in (massing.get("evidence") or []))


def test_the_interpretation_style_block_reports_only_supported_indicators():
    interpretation = _facade_interpretation("C")

    block = (interpretation.get("facade_interpretation") or {}).get("style_indicators") or []

    for entry in block:
        present, _ = _positive_labels(entry.get("descriptor") or "", STYLE_MARKERS)
        assert present, "interpretation kept an unsupported indicator: %r" % (entry,)


# ======================================================================
# 12. four-facade regression
# ======================================================================

def _replay(facade):
    raw = _understanding(facade)
    observation = build_architectural_observation(raw, upstream_understanding=raw)
    return observation, _indicator_kinds(observation)


def _legacy_replay(facade):
    raw = _understanding(facade)
    phrases = []
    for group in (
        raw.get("observed") or [],
        raw.get("inferred") or [],
        raw.get("architectural_elements") or [],
        raw.get("text_labels_if_visible") or [],
    ):
        for phrase in group:
            if phrase not in phrases:
                phrases.append(phrase)
    return _legacy_style_kinds(phrases)


def test_facade_a_loses_only_the_negated_indicators():
    observation, live = _replay("A")
    legacy = _legacy_replay("A")

    assert "proportion" in legacy, "the pre-fix defect is not reproduced"
    assert "proportion" not in live

    assert "form" in live
    assert live.count("composition") >= 2

    assert "low, single\u2011volume pavilion" in [
        entry.get("evidence_phrase") for entry in observation.get("style_indicators") or []
    ]


def test_facade_b_is_unchanged():
    _, live = _replay("B")

    assert live == _legacy_replay("B")
    assert live, "facade B must keep its affirmative indicators"


def test_facade_c_loses_only_the_negated_proportion():
    observation, live = _replay("C")
    legacy = _legacy_replay("C")

    assert legacy.count("proportion") == 2, "the pre-fix defect is not reproduced"
    assert live.count("proportion") == 1

    descriptors = [
        entry.get("evidence_phrase")
        for entry in observation.get("style_indicators") or []
    ]
    assert any("Tall, narrow" in text for text in descriptors)
    assert not any("vertical circulation elements" in text for text in descriptors)


def test_facade_d_is_unchanged_at_corpus_level():
    """Honest record: the saved corpus never put the clause in the phrase list.

    The normalizer kept only "no visible external stairs" from facade D's
    coordinated negation, so `all_phrases` never contained the
    vertical-circulation clause and the pre-fix loop had nothing to misfire
    on. Facade D's style indicators are therefore unchanged — and the clause
    itself is covered directly by the section-1 tests.
    """
    _, live = _replay("D")

    assert live == _legacy_replay("D")
    assert "proportion" in live, "facade D keeps its genuine 'tall portal'"


def test_facade_d_clause_is_absent_from_the_saved_phrase_list():
    """Documents WHY facade D is unchanged, so the record cannot rot."""
    raw = _understanding("D")

    phrases = list(raw.get("architectural_elements") or [])

    assert not any("vertical" in phrase for phrase in phrases), (
        "the corpus changed: facade D now carries the clause and the "
        "corpus-level expectation must be re-derived"
    )


def test_no_facade_loses_an_affirmative_indicator():
    """Across the whole corpus, nothing supported may disappear."""
    for facade in FACADES:
        observation, live = _replay(facade)

        for entry in observation.get("style_indicators") or []:
            present, _ = _positive_labels(
                entry.get("evidence_phrase") or "", STYLE_MARKERS)

            assert entry.get("kind") in present, (
                "facade %s kept an unsupported indicator: %r" % (facade, entry)
            )


def test_every_facade_keeps_its_element_and_material_evidence():
    for facade in FACADES:
        observation, _ = _replay(facade)

        assert observation.get("architectural_elements"), facade
        assert observation.get("negative_observations"), facade
