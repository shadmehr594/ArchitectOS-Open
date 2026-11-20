# -*- coding: utf-8 -*-
"""NORMALIZER_NEGATION_SCOPE_SAFETY_V1 — focused CPU tests.

THE QUESTION
------------
`VISION_NORMALIZER_EVIDENCE_RETENTION_V1` added a clause-level recovery for a
model claim that restates one item of the source's own coordinated negation.
Its scope test is `_governing_negation_start()`: the nearest negation opener
before the subject, with no SENTENCE TERMINATOR between.

Sentence terminators are not the only thing that ends a negation's scope. A
contrast ("but"), an exception ("other than", "except"), a new determiner or a
new predicate all reintroduce affirmative content:

    No external stairs, but balconies are visible.

A candidate `no balconies` must NOT be recovered here: the source says the
balconies ARE visible. "An architectural element mentioned inside a sentence
containing a negation is not necessarily absent. The negation must actually
govern that element."

WHAT THIS FILE PINS
-------------------
* a contrast, exception, determiner or predicate between the opener and the
  subject means the subject is NOT in the negation's scope;
* a genuine coordinated negation is still recovered (facade D, and the
  synthetic `no stairs or balconies are visible`);
* a rejected candidate leaves its failure diagnostic and changes nothing;
* quote integrity (`text in quote`, `quote in source`) is never relaxed;
* downstream, a rejected candidate never becomes an absent observation and
  never removes a positive element.

CPU only. No model call. No GPU. No render.
"""

import json
import os

import pytest

from core.vision.observation_normalizer_v1 import parse_normalization
from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
from core.vision.image_understanding_v1 import build_understanding
from core.vision.architectural_vision_interpreter_v1 import interpret_architectural_vision


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORPUS = os.path.join(ROOT, "runs", "vision_finished_facade_acceptance_v1")

FACADE_D = os.path.join(CORPUS, "D_upload_042039a7_003")

#: Facade D's two authentic coordinated negations, U+2011 hyphen included.
D_CLAUSE_ROOF = "no parapet, roof terrace, or occupiable attic storey is visible"
D_CLAUSE_CIRC = ("no visible external stairs, balconies, or "
                 "vertical\u2011circulation elements")


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _facade_d_structured():
    return _load(os.path.join(FACADE_D, "02_normalizer.json"))["structured"]


def _payload(claims):
    """A valid structured payload carrying exactly the supplied claims.

    EVERY claim category is cleared. An earlier version cleared only five and
    left the facade-D leftovers in place, so `rejected_claim_count` included 16
    unrelated claims and two already-correct cases looked broken. The schema
    requires every category to be present, so they are emptied rather than
    dropped.
    """

    from core.vision.observation_normalizer_v1 import CATEGORIES

    base = json.loads(json.dumps(_facade_d_structured()))

    for category in CATEGORIES:
        base[category] = []

    base["openings"] = {"doors": [], "windows": [], "other_openings": []}

    # The facade D drawing type and floor quote do not belong to a synthetic
    # source; leaving them in adds unrelated rejections to the count.
    base["drawing_type"] = None
    base["visible_floors"] = None

    base["observed_elements"] = list(claims)

    return base


def _claim(text, kind, quote=None):
    return {"text": text, "source_quote": quote if quote is not None else text,
            "kind": kind, "certainty": "ASSERTED", "count": None}


def _run(source_text, claims):
    """Real normalizer, then the real understanding and observation chain."""

    diagnostics = {}

    structured = parse_normalization(
        json.dumps(_payload(claims)), source_text, diagnostics=diagnostics)

    normalization = {
        "status": "NORMALIZED",
        "structured": structured,
        "source_resolution_failures": diagnostics["source_resolution_failures"],
        "source_resolutions": diagnostics.get("source_resolutions") or [],
        "accepted_claim_count": diagnostics["accepted_claim_count"],
        "rejected_claim_count": diagnostics["rejected_claim_count"],
    }

    understanding = build_understanding(
        {"contract": BRIDGE_CONTRACT,
         "raw_observer": {"raw_text": source_text},
         "normalization": normalization},
        provider="ollama", model="qwen3.8:27b", image_id="S", source_type="other",
    )

    return diagnostics, structured, understanding, interpret_architectural_vision(understanding)


def _recovered(diagnostics):
    return [entry for entry in diagnostics.get("source_resolutions") or []
            if entry.get("quote_method") == "coordinated_negation"]


def _negatives(interpretation):
    return [entry.get("evidence_phrase")
            for entry in interpretation["architectural_observation"]
            .get("negative_observations") or []]


def _visible(interpretation):
    return [entry.get("evidence_phrase")
            for entry in interpretation["architectural_observation"]
            .get("architectural_elements") or []
            if entry.get("status") == "visible"]


def _assert_rejected(source_text, claims, label):
    diagnostics, structured, _, interpretation = _run(source_text, claims)

    assert _recovered(diagnostics) == [], (
        label + ": the candidate was recovered as a coordinated negation")

    assert diagnostics["rejected_claim_count"] == 1, (
        label + ": the candidate was not rejected")

    assert structured["observed_elements"] == [], (
        label + ": the candidate was admitted into observed_elements")

    failures = diagnostics["source_resolution_failures"]

    assert len(failures) == 1 and failures[0]["claim"]["text"] == claims[0]["text"]

    assert not any("balcon" in str(p).lower() for p in _negatives(interpretation)), (
        label + ": a balcony was reported as absent")

    return diagnostics, interpretation


# ==========================================================
# CRITICAL — contrast: "but"
# ==========================================================


def test_critical_contrast_but_does_not_govern_the_balcony():
    """Source: `No external stairs, but balconies are visible.`"""

    source = "No external stairs, but balconies are visible."

    _assert_rejected(source, [_claim("no balconies", "balcony")], "contrast 'but'")


def test_critical_the_source_text_is_preserved_verbatim():
    source = "No external stairs, but balconies are visible."

    diagnostics, _, _, _ = _run(source, [_claim("no balconies", "balcony")])

    failure = diagnostics["source_resolution_failures"][0]

    assert failure["claim"]["source_quote"] == "no balconies"

    assert source == "No external stairs, but balconies are visible."


# ==========================================================
# A — semicolon boundary
# ==========================================================


def test_a_a_semicolon_ends_the_negation_scope():
    source = "No windows are visible; balconies are visible."

    _assert_rejected(source, [_claim("no balconies", "balcony")], "semicolon")


# ==========================================================
# B — full stop boundary
# ==========================================================


def test_b_a_full_stop_ends_the_negation_scope():
    source = "No columns are visible. A balcony is present."

    _assert_rejected(source, [_claim("no balcony", "balcony")], "full stop")


# ==========================================================
# C — exception clause
# ==========================================================


def test_c_an_exception_preserves_the_excepted_element():
    """`No columns other than the piers are visible.` — the piers are present."""

    source = "No columns other than the piers are visible."

    _assert_rejected(source, [_claim("no piers", "pier")], "exception 'other than'")


# ==========================================================
# D — negation, predicate, then a contrast
# ==========================================================


def test_d_a_completed_predicate_ends_the_scope():
    source = "No roof terrace is visible, but a balcony is visible."

    _assert_rejected(source, [_claim("no balcony", "balcony")], "predicate + but")


# ==========================================================
# E — an affirmative clause after a comma
# ==========================================================


def test_e_an_affirmative_clause_after_a_comma_is_not_negated():
    source = "No stairs, a balcony and windows are visible."

    _assert_rejected(source, [_claim("no balcony", "balcony")], "affirmative clause")


# ==========================================================
# F — a genuine coordinated negation is still recovered
# ==========================================================


def test_f_a_genuine_coordinated_negation_is_recovered():
    source = "No stairs or balconies are visible."

    diagnostics, structured, _, interpretation = _run(
        source, [_claim("no balconies", "balcony")])

    recovered = _recovered(diagnostics)

    assert len(recovered) == 1, "a genuine coordinated negation was not recovered"

    assert recovered[0]["source_quote"] == "No stairs or balconies are visible"

    assert any("balcon" in str(p).lower() for p in _negatives(interpretation))


def test_f2_the_recovered_clause_is_a_verbatim_source_slice():
    source = "No stairs or balconies are visible."

    diagnostics, _, _, _ = _run(source, [_claim("no balconies", "balcony")])

    quote = _recovered(diagnostics)[0]["source_quote"]

    assert quote in source


# ==========================================================
# G / H — facade D's authentic recoveries are preserved
# ==========================================================


def test_g_facade_d_roof_clause_is_still_recovered():
    observer = _load(os.path.join(FACADE_D, "01_raw_observer.json"))
    saved = _load(os.path.join(FACADE_D, "02_normalizer.json"))

    diagnostics = {}

    parse_normalization(saved["raw_text"], observer["raw_text"],
                        diagnostics=diagnostics)

    quotes = [entry["source_quote"] for entry in _recovered(diagnostics)]

    assert D_CLAUSE_ROOF in quotes


def test_h_facade_d_circulation_clause_is_still_recovered():
    observer = _load(os.path.join(FACADE_D, "01_raw_observer.json"))
    saved = _load(os.path.join(FACADE_D, "02_normalizer.json"))

    diagnostics = {}

    parse_normalization(saved["raw_text"], observer["raw_text"],
                        diagnostics=diagnostics)

    quotes = [entry["source_quote"] for entry in _recovered(diagnostics)]

    assert D_CLAUSE_CIRC in quotes


def test_h2_the_authentic_clauses_carry_the_u2011_hyphen():
    observer = _load(os.path.join(FACADE_D, "01_raw_observer.json"))

    assert "vertical\u2011circulation" in observer["raw_text"]

    assert "vertical-circulation" not in observer["raw_text"]


# ==========================================================
# Duplicate handling
# ==========================================================


def test_duplicates_of_a_rejected_candidate_are_not_invented():
    """Two candidates for a non-governed subject: neither may be recovered."""

    source = "No external stairs, but balconies are visible."

    claims = [_claim("no balconies", "balcony"),
              _claim("no balcony", "balcony")]

    diagnostics, _, _, _ = _run(source, claims)

    assert _recovered(diagnostics) == []

    assert diagnostics["rejected_claim_count"] == 2


def test_a_second_item_of_a_genuine_clause_is_marked_covered():
    source = "No stairs, ramps, or balconies are visible."

    claims = [_claim("no balconies", "balcony"),
              _claim("no ramps", "ramp")]

    diagnostics, _, _, _ = _run(source, claims)

    assert len(_recovered(diagnostics)) == 1

    reasons = [entry["reason"] for entry in diagnostics["source_resolution_failures"]]

    assert "duplicate_of_recovered_clause" in reasons


# ==========================================================
# Quote integrity and certainty
# ==========================================================


@pytest.mark.parametrize("source,claim", [
    ("No stairs or balconies are visible.", _claim("no balconies", "balcony")),
    ("No parapet, roof terrace, or occupiable attic storey is visible.",
     _claim("no roof terrace", "roof_detail")),
])
def test_quote_integrity_is_never_relaxed(source, claim):
    diagnostics, structured, _, _ = _run(source, [claim])

    for entry in structured["observed_elements"]:

        assert entry["source_quote"] in source

        assert entry["text"] in entry["source_quote"]


def test_a_recovered_claim_keeps_asserted_certainty():
    source = "No stairs or balconies are visible."

    _, structured, _, _ = _run(source, [_claim("no balconies", "balcony")])

    assert structured["observed_elements"][0]["certainty"] == "ASSERTED"


def test_a_recovered_claim_never_claims_verification():
    source = "No stairs or balconies are visible."

    _, structured, _, interpretation = _run(
        source, [_claim("no balconies", "balcony")])

    for record in interpretation["architectural_observation"]["negative_observations"]:

        assert record.get("status") == "absent"

        assert record.get("confidence") in ("LOW", "MEDIUM")


# ==========================================================
# Downstream: a rejected candidate changes nothing
# ==========================================================


def test_a_rejected_candidate_does_not_create_a_positive_element():
    source = "No external stairs, but balconies are visible."

    _, _, _, interpretation = _run(source, [_claim("no balconies", "balcony")])

    assert "balcon" not in " ".join(_visible(interpretation)).lower()


def test_a_rejected_candidate_leaves_its_diagnostic():
    source = "No external stairs, but balconies are visible."

    diagnostics, _, _, _ = _run(source, [_claim("no balconies", "balcony")])

    failure = diagnostics["source_resolution_failures"][0]

    assert failure["field"] in ("source_quote", "text")

    assert failure["claim"]["text"] == "no balconies"


# ==========================================================
# The scope helper, directly
# ==========================================================


@pytest.mark.parametrize("source,subject", [
    ("No external stairs, but balconies are visible.", "balconies"),
    ("No roof terrace is visible, but a balcony is visible.", "balcony"),
    ("No stairs, a balcony and windows are visible.", "balcony"),
    ("No columns other than the piers are visible.", "piers"),
    ("No windows are visible; balconies are visible.", "balconies"),
    ("No columns are visible. A balcony is present.", "balcony"),
])
def test_the_scope_helper_finds_no_governing_negation(source, subject):
    """A subject merely appearing after a `no` is not inside its scope."""

    from core.vision.observation_normalizer_v1 import _negated_clause

    assert _negated_clause(subject, source) is None


@pytest.mark.parametrize("source,subject,expected", [
    ("No stairs or balconies are visible.", "balconies",
     "No stairs or balconies are visible"),
    ("No stairs, ramps, or balconies are visible.", "balconies",
     "No stairs, ramps, or balconies are visible"),
    ("No windows and doors are visible.", "doors",
     "No windows and doors are visible"),
])
def test_the_scope_helper_finds_a_genuine_coordinated_negation(source, subject, expected):
    from core.vision.observation_normalizer_v1 import _negated_clause

    assert _negated_clause(subject, source) == expected
