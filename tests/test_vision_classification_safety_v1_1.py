# -*- coding: utf-8 -*-
"""VISION_CLASSIFICATION_SAFETY_V1_1 — RED then GREEN.

Two defects that V1 did not catch, both reproduced independently against the
uploaded production module before any test was written:

  S1  PLURAL MORPHOLOGY. `_marker_pattern()` appended "ies" to the WHOLE
      marker, so `balcony` became `balconyies`. "balconies", "canopies" and
      "entries" therefore matched nothing at all — and because they matched
      nothing, `_positive_labels()` returned [] for BOTH buckets. A negated
      plural was not merely mis-scoped, it was invisible:
          "No balconies are visible"  ->  present []  absent []
      That is the most dangerous shape of this bug: absence evidence silently
      disappears instead of being misfiled.

  S2  COORDINATED NEGATION WITHOUT "or". V1 required an `or`/`nor` in the
      clause before a comma could continue a negation, so an `and` list or a
      bare comma enumeration still negated only the first member:
          "No doors, windows, and stairs are visible"
              ->  present ['window', 'stair']   absent ['door']

The S2 fix must NOT be "add `and` to the disjunction regex": that would turn
"No columns are visible, and the facade is plain" into a negated facade.
Test I exists to prevent exactly that.

Phrases are REAL where the four-facade corpus supplies them, otherwise they are
explicitly synthetic counterexamples. The observer emits U+2011, not ASCII '-'.
"""

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.vision.architectural_observation_v1 import (  # noqa: E402
    ARCHITECTURAL_ELEMENT_MARKERS,
    COLOR_MARKERS,
    MATERIAL_MARKERS,
    OBJECT_MARKERS,
    TEXTURE_MARKERS,
    _labels,
    _positive_labels,
    build_architectural_observation,
)

H = "\u2011"


def _kinds(phrase):
    return _positive_labels(
        phrase, ARCHITECTURAL_ELEMENT_MARKERS,
        suppress_compound_modifiers=True)


def _present(phrase):
    return _kinds(phrase)[0]


def _absent(phrase):
    return _kinds(phrase)[1]


# ============================================================
# S1 — English plural morphology
# ============================================================


def test_A_balconies_plural_is_a_balcony():
    present = _present("several balconies with railings")
    assert "balcony" in present
    assert "railing" in present


def test_A_balcony_singular_still_works():
    present = _present("a balcony with a railing")
    assert "balcony" in present
    assert "railing" in present


def test_B_canopies_plural_is_a_canopy():
    assert "canopy" in _present("two canopies above the entrance")


def test_C_entries_plural_is_an_entrance():
    assert "entrance" in _present("several entries are visible")


@pytest.mark.parametrize("phrase,label", [
    ("two doorways", "door"),
    ("three archways", "arch"),
    ("several walls", "wall"),
    ("two windows", "window"),
    ("three arches", "arch"),
    ("four piers", "pier"),
    ("two staircases", "stair"),
])
def test_C_ordinary_plurals_unchanged(phrase, label):
    assert label in _present(phrase)


def test_C_vowel_y_plural_does_not_invent_an_ies_form():
    # "day" -> "days", never "daies". A marker-free control phrase: nothing
    # architectural should be asserted from it either way.
    assert _present("days of work") == []


def test_D_negated_plural_is_recorded_absent():
    present, absent = _kinds("No balconies are visible")
    assert "balcony" not in present
    assert "balcony" in absent, (
        "a negated plural must be recorded as ABSENT, not vanish entirely")


def test_D_negated_plural_canopy():
    present, absent = _kinds("No canopies are visible")
    assert "canopy" not in present
    assert "canopy" in absent


# ============================================================
# S2 — coordinated negation
# ============================================================


def test_E_or_list_with_plurals():
    present, absent = _kinds(
        "No stairs, balconies, or other external features are visible")
    for label in ("stair", "balcony"):
        assert label not in present
        assert label in absent


def test_F_and_list_negates_every_member():
    present, absent = _kinds("No doors, windows, and stairs are visible")
    for label in ("door", "window", "stair"):
        assert label not in present, "%r was promoted to visible" % label
        assert label in absent, "%r was not recorded absent" % label


def test_G_bare_comma_enumeration_negates_every_member():
    present, absent = _kinds("No doors, windows, stairs are visible")
    for label in ("door", "window", "stair"):
        assert label not in present
        assert label in absent


def test_H_or_pair_still_correct():
    present, absent = _kinds("No doors or windows are visible")
    assert "door" not in present and "window" not in present
    assert "door" in absent and "window" in absent


def test_I_clause_joining_comma_does_not_negate_the_next_clause():
    present, absent = _kinds("No columns are visible, and the facade is plain")
    assert "column" in absent
    assert "facade" not in absent, (
        "adding `and` blindly would negate an independent affirmative clause")
    assert "facade" in present


def test_I_single_comma_without_conjunction_is_a_clause_boundary():
    present, absent = _kinds("No columns, the facade is plain")
    assert "column" in absent
    assert "facade" not in absent


def test_J_other_than_exception_stays_positive():
    present, absent = _kinds(
        "No visible columns other than the ground-floor piers")
    assert "column" in absent
    assert "pier" in present


def test_K_except_exception_stays_positive():
    present, absent = _kinds("No openings except the two doorways")
    assert "opening" in absent
    assert "door" in present


def test_L_positive_and_negative_coexist_across_phrases():
    positive = _present("Two projecting balconies with stone balustrades")
    negative_present, negative_absent = _kinds("No balconies are visible")
    assert "balcony" in positive
    assert "balcony" in negative_absent
    assert "balcony" not in negative_present


def test_L_positive_and_negative_coexist_in_one_sentence():
    present, absent = _kinds(
        "The upper balconies are visible; no railings are visible")
    assert "balcony" in present
    assert "railing" in absent


# ============================================================
# S2b — repeated negation cues are SEPARATE statements, not one list
# ============================================================


def test_S2b_repeated_cues_stay_separate():
    """REAL (facade evidence-semantics fixture).

    "no pitched roof, no visible roof terrace, no dormers" is three separate
    absence statements. Merging them into one span loses each one's verbatim
    fragment, which is what the downstream scoped-negative contract depends
    on. A comma followed by a fresh cue must end the current span.
    """
    observation = _observation("no pitched roof, no visible roof terrace, no dormers")
    fragments = [f for entry in (observation.get("negative_observations") or [])
                 for f in (entry.get("negated_texts") or [])]
    assert "no pitched roof" in fragments
    assert any("roof terrace" in f for f in fragments)
    assert any("dormers" in f for f in fragments)


def test_S2b_repeated_cues_with_conjunction():
    observation = _observation(
        "no roof terrace, no attic band, and no windows or openings above the "
        "top window row")
    fragments = [f for entry in (observation.get("negative_observations") or [])
                 for f in (entry.get("negated_texts") or [])]
    assert any(f.startswith("no roof terrace") for f in fragments), fragments


# ============================================================
# M–N — provenance and negativity channel
# ============================================================


def _observation(*phrases):
    return build_architectural_observation(
        {"observed": list(phrases), "confidence": "LOW"},
        provider="ollama", model="qwen3.8:27b", image_id="synthetic",
        source_type="other")


def test_M_evidence_phrase_is_verbatim():
    phrase = "No stairs, balconies, or other external features are visible"
    observation = _observation(phrase)
    for entry in observation.get("architectural_elements") or []:
        assert entry["evidence_phrase"] == phrase
    for entry in observation.get("negative_observations") or []:
        assert entry["evidence_phrase"] == phrase


def test_M_raw_observation_preserved():
    phrase = "several balconies with railings"
    observation = _observation(phrase)
    assert phrase in json.dumps(observation.get("raw_observations"),
                                ensure_ascii=False)


def test_N_negatives_absent_and_non_authoritative():
    observation = _observation("No balconies are visible")
    records = observation.get("negative_observations") or []
    assert records, "the negated plural produced no absence record"
    for record in records:
        assert record["status"] == "absent"
        assert record.get("authoritative") is not True
        assert record.get("verification") != "VERIFIED"
    kinds = {k for e in (observation.get("architectural_elements") or [])
             for k in (e.get("kind") or [])}
    assert "balcony" not in kinds


# ============================================================
# O–P — V1 corrections and material behaviour must survive
# ============================================================


def test_O_substring_fixes_intact():
    assert _labels("legible through the glass", TEXTURE_MARKERS) == []
    assert _labels("clad in rendered masonry", COLOR_MARKERS) == []
    assert _labels("Foreground asphalt street with painted lines",
                   OBJECT_MARKERS) == []


def test_O_compound_modifiers_intact():
    present, _ = _kinds("floor{0}to{0}ceiling glass curtain wall".format(H))
    assert "floor" not in present and "ceiling" not in present
    assert "wall" in present

    present, _ = _kinds("two wall{0}mounted sconce lights".format(H))
    assert "light_fixture" in present
    assert "wall" not in present


def test_O_closed_compounds_intact():
    assert "roof" in _present("Flat roofline with a thin parapet")
    assert "railing" in _present("a fourth smaller balustraded ledge")
    assert "pediment" in _present("a segmental pedimented bay")


def test_P_material_lexical_labels_after_material_semantics_v1():
    """CHANGED by VISION_MATERIAL_SEMANTICS_V1.

    Two expectations moved, both deliberately:

      * "metal/wood trim" -> `metal`, not `steel` (generic family != alloy);
      * "stone or marble panels" -> `stone` only, because "panel" is a
        product form and no longer implies `composite`.

    The other two are unchanged, which is the point: the vocabulary that must
    survive still survives.
    """
    assert _labels("Dark (black) painted metal/wood trim", MATERIAL_MARKERS) == [
        "wood", "metal"]
    assert _labels("beige/tan veined stone or marble panels",
                   MATERIAL_MARKERS) == ["stone"]
    assert _labels("clad in light beige stone or rendered masonry",
                   MATERIAL_MARKERS) == ["stone", "plaster", "masonry"]
    assert _labels("filled with a tiled/mosaic dome pattern",
                   MATERIAL_MARKERS) == ["tile"]


def test_P_material_label_set_gained_family_and_alloy_identities():
    """CHANGED by VISION_MATERIAL_SEMANTICS_V1 — `metal` and `aluminium` added."""
    assert [label for label, _ in MATERIAL_MARKERS] == [
        "concrete", "glass", "wood", "stone", "brick", "steel", "metal",
        "aluminium", "tile", "plaster", "composite", "masonry"]
