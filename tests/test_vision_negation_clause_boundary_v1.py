# -*- coding: utf-8 -*-
"""VISION_NEGATION_CLAUSE_BOUNDARY_V1 — RED then GREEN.

The remaining defect: `_forward_scope_end()` treated "comma + conjunction" as
proof of ONE coordinated negative list, so a negated statement followed by a
separate affirmative clause had that clause's elements dragged into absence.

Reproduced against the uploaded production module before any test was written:

    "No columns, a balcony and windows are visible"
        -> present []                        absent [window, balcony, column]
    "No columns, the facade is plain, and two windows are visible"
        -> present [window]                  absent [facade, column]
    "No openings, a balcony is visible, and the columns are painted"
        -> present [column]                  absent [opening, balcony]

A comma must never turn a separately asserted visible balcony, window, wall or
facade into an absent architectural element.

Every REGRESSION CONTROL below is a construction that already worked and must
keep working — they are here so that a fix for the three cases above cannot be
bought by breaking the list cases.
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


# ============================================================
# 1. The three reported false negatives
# ============================================================


def test_repro_1_affirmative_clause_after_negated_noun():
    present, absent = _kinds("No columns, a balcony and windows are visible")
    assert "column" in absent
    assert "balcony" in present, "a separately asserted balcony became absent"
    assert "window" in present, "a separately asserted window became absent"
    assert "balcony" not in absent
    assert "window" not in absent


def test_repro_2_two_affirmative_clauses_after_negation():
    present, absent = _kinds(
        "No columns, the facade is plain, and two windows are visible")
    assert "column" in absent
    assert "facade" in present, "the facade clause was dragged into absence"
    assert "window" in present
    assert "facade" not in absent
    assert "window" not in absent


def test_repro_3_negation_stops_at_first_clause_boundary():
    present, absent = _kinds(
        "No openings, a balcony is visible, and the columns are painted")
    assert "opening" in absent
    assert "balcony" in present
    assert "column" in present
    assert "balcony" not in absent
    assert "column" not in absent


# ============================================================
# 2. Regression controls — every one of these already worked
# ============================================================


@pytest.mark.parametrize("phrase,negated", [
    ("No doors, windows, and stairs are visible", ("door", "window", "stair")),
    ("No doors, windows, stairs are visible", ("door", "window", "stair")),
    ("No stairs, balconies, or other external features are visible",
     ("stair", "balcony")),
    ("No doors or windows are visible", ("door", "window")),
    ("No doors and windows are visible", ("door", "window")),
])
def test_control_genuine_negated_list_stays_negated(phrase, negated):
    present, absent = _kinds(phrase)
    for label in negated:
        assert label not in present, "%r promoted to visible" % label
        assert label in absent, "%r lost its absence" % label


def test_control_clause_after_predicate_keeps_facade_positive():
    present, absent = _kinds("No columns are visible, and the facade is plain")
    assert "column" in absent
    assert "facade" in present
    assert "facade" not in absent


def test_control_other_than_exception():
    present, absent = _kinds(
        "No visible columns other than the ground-floor piers")
    assert "column" in absent
    assert "pier" in present


def test_control_except_exception():
    present, absent = _kinds("No openings except the two doorways")
    assert "opening" in absent
    assert "door" in present


def test_control_repeated_negative_cues_keep_separate_fragments():
    observation = build_architectural_observation(
        {"observed": ["no pitched roof, no visible roof terrace, no dormers"]},
        provider="ollama", model="qwen3.8:27b", image_id="x",
        source_type="other")
    fragments = [f for entry in (observation.get("negative_observations") or [])
                 for f in (entry.get("negated_texts") or [])]
    assert "no pitched roof" in fragments
    assert any("roof terrace" in f for f in fragments)
    assert any("dormers" in f for f in fragments)


def test_control_but_clause_keeps_doors_positive():
    present, absent = _kinds("No windows, but two doors are visible")
    assert "window" in absent
    assert "door" in present
    assert "door" not in absent


def test_control_scoped_negative_with_repeated_cue_and_conjunction():
    observation = build_architectural_observation(
        {"observed": ["no roof terrace, no attic band, and no windows or "
                      "openings above the top window row"]},
        provider="ollama", model="qwen3.8:27b", image_id="x",
        source_type="other")
    fragments = [f for entry in (observation.get("negative_observations") or [])
                 for f in (entry.get("negated_texts") or [])]
    assert any(f.startswith("no roof terrace") for f in fragments), fragments


# ============================================================
# 3. V1 / V1.1 behaviour must survive untouched
# ============================================================


def test_preserved_plurals():
    assert "balcony" in _kinds("several balconies with railings")[0]
    assert "canopy" in _kinds("two canopies above the entrance")[0]
    assert "entrance" in _kinds("several entries are visible")[0]


def test_preserved_negated_plural():
    present, absent = _kinds("No balconies are visible")
    assert "balcony" not in present
    assert "balcony" in absent


def test_preserved_substring_boundaries():
    assert _labels("legible through the glass", TEXTURE_MARKERS) == []
    assert _labels("clad in rendered masonry", COLOR_MARKERS) == []
    assert _labels("Foreground asphalt street with painted lines",
                   OBJECT_MARKERS) == []


def test_preserved_compound_modifiers():
    present, _ = _kinds("floor{0}to{0}ceiling glass curtain wall".format(H))
    assert "floor" not in present and "ceiling" not in present
    assert "wall" in present

    present, _ = _kinds("two wall{0}mounted sconce lights".format(H))
    assert "light_fixture" in present and "wall" not in present


# ============================================================
# 4. Provenance — nothing is promoted, nothing is suppressed
# ============================================================


def test_provenance_evidence_phrase_verbatim():
    phrase = "No columns, a balcony and windows are visible"
    observation = build_architectural_observation(
        {"observed": [phrase]}, provider="ollama", model="qwen3.8:27b",
        image_id="x", source_type="other")
    for entry in observation.get("architectural_elements") or []:
        assert entry["evidence_phrase"] == phrase
    for entry in observation.get("negative_observations") or []:
        assert entry["evidence_phrase"] == phrase


def test_provenance_negatives_not_authoritative():
    observation = build_architectural_observation(
        {"observed": ["No columns, a balcony and windows are visible"]},
        provider="ollama", model="qwen3.8:27b", image_id="x",
        source_type="other")
    for entry in observation.get("negative_observations") or []:
        assert entry["status"] == "absent"
        assert entry.get("authoritative") is not True
        assert entry.get("verification") != "VERIFIED"


def test_provenance_raw_text_preserved():
    phrase = "No columns, the facade is plain, and two windows are visible"
    observation = build_architectural_observation(
        {"observed": [phrase]}, provider="ollama", model="qwen3.8:27b",
        image_id="x", source_type="other")
    assert phrase in json.dumps(observation.get("raw_observations"),
                                ensure_ascii=False)
