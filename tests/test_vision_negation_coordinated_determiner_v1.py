# -*- coding: utf-8 -*-
"""VISION_NEGATION_COORDINATED_DETERMINER_V1 — RED then GREEN.

`VISION_NEGATION_CLAUSE_BOUNDARY_V1` added `_NEW_CLAUSE_DETERMINER` on the
assumption that a determiner after a comma always opens an INDEPENDENT
AFFIRMATIVE clause. That assumption is false. A determiner also appears
inside a coordinated NEGATIVE noun list, where English *requires* it:

    No doors, windows, or a balcony are visible
                      ^^^^^^^^^
    "balcony" is singular countable, so the article is grammatically
    obligatory inside the negated coordination. It is not a new clause.

Reproduced against the unmodified production module before any test was
written (all four confirmed, see the milestone report):

    "No doors, windows, or a balcony are visible"
        -> present [balcony]        absent [door, window]      REGRESSION
    "No windows, a door, or balconies are visible"
        -> present [door, balcony]  absent [window]            REGRESSION
    "The photograph shows no doors, windows, or a balcony"
        -> present [balcony]        absent [door, window]      REGRESSION
    "No doors, windows, and a balcony are visible"
        -> present [balcony]        absent [door, window]      REGRESSION

The previous milestone's three target cases must stay fixed, and every
V1 / V1.1 control must keep working. Those are asserted here FIRST so that a
fix for the four regressions cannot be bought by re-breaking them.

Guiding principle: a determiner alone is not proof of an independent
affirmative clause, and a coordinated negative list must never manufacture
visible architecture.
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


def _fragments(phrase):
    observation = build_architectural_observation(
        {"observed": [phrase]}, provider="ollama", model="qwen3.8:27b",
        image_id="x", source_type="other")
    return [f for entry in (observation.get("negative_observations") or [])
            for f in (entry.get("negated_texts") or [])]


def _assert_all_absent(phrase, labels):
    present, absent = _kinds(phrase)
    for label in labels:
        assert label not in present, (
            "%r manufactured visible %r from a negated list" % (phrase, label))
        assert label in absent, (
            "%r lost the absence of %r" % (phrase, label))


# ============================================================
# 1. The four reported regressions
# ============================================================


def test_A_or_list_with_obligatory_article_is_fully_negated():
    """`or a balcony` is the third member of a negated coordination."""
    _assert_all_absent("No doors, windows, or a balcony are visible",
                       ("door", "window", "balcony"))


def test_B_determiner_member_followed_by_more_bare_members():
    """`a door, or balconies` — the list continues past the determiner."""
    _assert_all_absent("No windows, a door, or balconies are visible",
                       ("window", "door", "balcony"))


def test_C_embedded_negation_article_at_end_of_sentence():
    """No predicate at all — a determiner cannot be a clause on its own."""
    _assert_all_absent("The photograph shows no doors, windows, or a balcony",
                       ("door", "window", "balcony"))


def test_D_and_list_with_article_fails_closed():
    """`No A, B, and a C` — distributed negation is the deterministic reading.

    This is the same shape documented as a known limit in
    VISION_NEGATION_CLAUSE_BOUNDARY_V1 §8.2 ("No columns, balconies and
    windows are visible"). The determiner changes nothing about the reading;
    manufacturing a visible balcony here would be a false positive.
    """
    _assert_all_absent("No doors, windows, and a balcony are visible",
                       ("door", "window", "balcony"))


# ============================================================
# 2. The previous milestone's three target cases — must stay fixed
# ============================================================


def test_V1_1_affirmative_clause_after_negated_noun():
    present, absent = _kinds("No columns, a balcony and windows are visible")
    assert "column" in absent
    assert "balcony" in present, "a separately asserted balcony became absent"
    assert "window" in present
    assert "balcony" not in absent
    assert "window" not in absent


def test_V1_2_two_affirmative_clauses_after_negation():
    present, absent = _kinds(
        "No columns, the facade is plain, and two windows are visible")
    assert "column" in absent
    assert "facade" in present, "the facade clause was dragged into absence"
    assert "window" in present
    assert "facade" not in absent


def test_V1_3_negation_stops_at_first_clause_boundary():
    present, absent = _kinds(
        "No openings, a balcony is visible, and the columns are painted")
    assert "opening" in absent
    assert "balcony" in present
    assert "column" in present
    assert "balcony" not in absent
    assert "column" not in absent


# ============================================================
# 3. V1 / V1.1 regression controls
# ============================================================


@pytest.mark.parametrize("phrase,negated", [
    ("No doors, windows, and stairs are visible", ("door", "window", "stair")),
    ("No doors, windows, stairs are visible", ("door", "window", "stair")),
    ("No stairs, balconies, or other external features are visible",
     ("stair", "balcony")),
    ("No doors or windows are visible", ("door", "window")),
    ("No doors and windows are visible", ("door", "window")),
    ("No balconies are visible", ("balcony",)),
])
def test_control_genuine_negated_list_stays_negated(phrase, negated):
    _assert_all_absent(phrase, negated)


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
    fragments = _fragments(
        "no pitched roof, no visible roof terrace, no dormers")
    assert "no pitched roof" in fragments, fragments
    assert any("roof terrace" in f for f in fragments), fragments
    assert any("dormers" in f for f in fragments), fragments


def test_control_but_clause_keeps_doors_positive():
    present, absent = _kinds("No windows, but two doors are visible")
    assert "window" in absent
    assert "door" in present
    assert "door" not in absent


def test_control_scoped_negative_with_repeated_cue_and_conjunction():
    fragments = _fragments(
        "no roof terrace, no attic band, and no windows or openings above "
        "the top window row")
    assert any(f.startswith("no roof terrace") for f in fragments), fragments


def test_preserved_plurals():
    assert "balcony" in _kinds("several balconies with railings")[0]
    assert "canopy" in _kinds("two canopies above the entrance")[0]
    assert "entrance" in _kinds("several entries are visible")[0]


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
# 4. Adversarial coordinated determiners
# ============================================================


@pytest.mark.parametrize("phrase", [
    "No doors, a window, or a balcony are visible",
    "No columns, a balcony, or a window are visible",
    "No doors, windows, or the balcony are visible",
    "No doors, windows, nor a balcony are visible",
    "No doors, windows, or a balcony is visible",
    "No doors, windows, and the balcony are visible",
])
def test_adversarial_three_member_list_with_determiner(phrase):
    """A determiner that is the third-or-later member is inside the list."""
    labels = [label for label in ("door", "window", "column", "balcony")
              if label in _kinds(phrase)[0] + _kinds(phrase)[1]]
    assert labels, "no architectural label recognised at all in %r" % phrase
    _assert_all_absent(phrase, labels)


def test_adversarial_two_member_list_plural_predicate_fails_closed():
    """`a balcony` cannot be the subject of `are` — no agreement, no clause."""
    _assert_all_absent("No doors, and a balcony are visible",
                       ("door", "balcony"))


def test_adversarial_two_member_affirmative_clause_is_kept():
    """A singular determiner phrase with a singular predicate IS a clause."""
    present, absent = _kinds("No doors, and a balcony is visible")
    assert "door" in absent
    assert "balcony" in present, "an agreeing affirmative clause was negated"
    assert "balcony" not in absent


def test_adversarial_affirmative_clause_after_a_complete_negated_list():
    present, absent = _kinds(
        "No doors, windows, or stairs are visible, and a balcony is visible")
    assert "door" in absent and "window" in absent and "stair" in absent
    assert "balcony" in present
    assert "balcony" not in absent


# ============================================================
# 5. Provenance, fragments, and the negative bucket
# ============================================================


def test_A_negative_fragment_is_verbatim_and_complete():
    phrase = "No doors, windows, or a balcony are visible"
    fragments = _fragments(phrase)
    # Verbatim contiguous slice of the ORIGINAL wording, including the
    # observer's capital "N" — never a lower-cased reconstruction.
    assert "No doors, windows, or a balcony" in fragments, fragments
    for fragment in fragments:
        assert fragment in phrase, (fragment, phrase)


def test_A_negatives_are_not_authoritative():
    observation = build_architectural_observation(
        {"observed": ["No doors, windows, or a balcony are visible"]},
        provider="ollama", model="qwen3.8:27b", image_id="x",
        source_type="other")
    records = observation.get("negative_observations") or []
    assert records, "no negative record produced"
    for entry in records:
        assert entry["status"] == "absent"
        assert entry.get("authoritative") is not True
        assert entry.get("verification") != "VERIFIED"


def test_A_positive_bucket_empty_and_absent_bucket_complete():
    observation = build_architectural_observation(
        {"observed": ["No doors, windows, or a balcony are visible"]},
        provider="ollama", model="qwen3.8:27b", image_id="x",
        source_type="other")
    positive = sorted({kind for entry in
                       (observation.get("architectural_elements") or [])
                       for kind in (entry.get("kind") or [])})
    absent = sorted({kind for entry in
                     (observation.get("negative_observations") or [])
                     for kind in (entry.get("kind") or [])})
    assert positive == [], positive
    assert set(absent) == {"balcony", "door", "window"}, absent


def test_provenance_evidence_phrase_verbatim():
    phrase = "No columns, a balcony and windows are visible"
    observation = build_architectural_observation(
        {"observed": [phrase]}, provider="ollama", model="qwen3.8:27b",
        image_id="x", source_type="other")
    for entry in observation.get("architectural_elements") or []:
        assert entry["evidence_phrase"] == phrase
    for entry in observation.get("negative_observations") or []:
        assert entry["evidence_phrase"] == phrase


def test_provenance_raw_text_preserved():
    phrase = "No columns, the facade is plain, and two windows are visible"
    observation = build_architectural_observation(
        {"observed": [phrase]}, provider="ollama", model="qwen3.8:27b",
        image_id="x", source_type="other")
    assert phrase in json.dumps(observation.get("raw_observations"),
                                ensure_ascii=False)
