# -*- coding: utf-8 -*-
"""VISION_FIRST_D7_RESTATEMENT_EVIDENCE_V1 — focused CPU tests.

Defect: the observer's section 5 ("Visible evidence supporting the storey count")
restates section 1 and adds a few facts that exist NOWHERE else — most
importantly

    second row of windows in the same four-bay arrangement

The previous normalizer emitted ZERO claims from that section, so the unique
relationship was lost with the redundant restatement.

The hypothesis is over-aggressive anti-duplication, but the causal mechanism is
NOT independently established and is not asserted here. What is asserted is the
missing INSTRUCTION CONTRACT: nothing in the prompt protects a unique fact that
happens to sit inside a restatement.

FIXTURES
--------
* `runs/vision_facade_compound_v1/live_compound_v1.json` — immutable observer text
  (sha `9210ac9a…`).
* `runs/vision_facade_evidence_semantics_v1/live_semantics_v1.json` — accepted
  structured baseline.
* SYNTHETIC fixtures are labelled (a different building, a different bay count).

No Ollama. No GPU. No ComfyUI.
"""

import json
import os

import pytest

from core.vision.architectural_vision_interpreter_v1 import interpret_architectural_vision
from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
from core.vision.image_understanding_v1 import build_understanding
from core.vision.observation_normalizer_v1 import NORMALIZER_PROMPT
from core.vision.vision_report_v1 import render_vision_report


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COMPOUND = os.path.join(ROOT, "runs", "vision_facade_compound_v1",
                        "live_compound_v1.json")
SEMANTICS = os.path.join(ROOT, "runs", "vision_facade_evidence_semantics_v1",
                         "live_semantics_v1.json")

OBSERVER_SHA = "9210ac9ab659db686606a0284b1360f0b322a4bb911a1344d76c635611f6f155"

# ---- real observer text -------------------------------------------------
Q_BAY = "second row of windows in the same four\u2011bay arrangement"
Q_ROWS = "They appear in three horizontal rows above the ground level"
Q_SCOPED_ABSENCE = ("no windows or openings above the top window row")
Q_PASSAGE = "A large open through\u2011passage (arcade) on the ground floor"
Q_DOOR = "One dark, recessed pedestrian door on the ground floor, left of centre"
# ---- unique facts that live only inside the restatement section ----------
Q_STOREY2 = ("first row of windows above the ground level (left window, wide "
             "central window, mid window, right window)")
Q_STOREY4 = "third and topmost row of windows, sitting just below the parapet"

# ---- SYNTHETIC fixture: different building, different bay count ---------
SYNTHETIC_OBSERVER = (
    "The elevation is a rendered block. "
    "A band of windows crosses the upper floor. "
    "The upper band repeats the same six-bay rhythm described above. "
    "The band is set in two horizontal rows."
)
Q_SYNTH_BAY = "The upper band repeats the same six-bay rhythm described above"
Q_SYNTH_ROWS = "The band is set in two horizontal rows"

RESTATEMENT_MARKER = "RESTATED EVIDENCE"


def _raw():
    with open(COMPOUND, encoding="utf-8") as fh:
        return json.load(fh)


def _raw_text():
    return _raw()["raw_text"]


def _raw_observer():
    return _raw()["raw_observer"]


def _base():
    with open(SEMANTICS, encoding="utf-8") as fh:
        return json.loads(json.dumps(json.load(fh)["normalization"]["structured"]))


def _claim(text, kind="window", certainty="ASSERTED", count=None, quote=None):
    return {"text": text, "source_quote": quote or text, "kind": kind,
            "certainty": certainty, "count": count}


def _payload(claims, **slots):
    base = _base()
    base["observed_elements"] = claims
    base["walls"] = []
    base["structural_elements"] = []
    base["spatial_relationships"] = []
    base["openings"] = {"doors": [], "other_openings": [], "windows": []}
    for key, value in slots.items():
        base[key] = value
    return base


def _chain(structured, raw_observer=None):
    understanding = build_understanding(
        {"contract": BRIDGE_CONTRACT,
         "raw_observer": raw_observer or _raw_observer(),
         "normalization": {"status": "NORMALIZED", "structured": structured}},
        provider="ollama", model="qwen3.8:27b", image_id="V3", source_type="other")
    return understanding, interpret_architectural_vision(understanding)


def _report(structured, raw_observer=None):
    _, interpretation = _chain(structured, raw_observer)
    return interpretation, render_vision_report(interpretation, "fa")


def _norm(text):
    return " ".join(text.split()).lower()


# ==========================================================
# RED — the missing instruction contract
# ==========================================================


def test_prompt_protects_unique_facts_inside_a_restatement():
    """The prompt must say a restatement can still carry a NEW fact."""

    assert RESTATEMENT_MARKER in NORMALIZER_PROMPT, (
        "nothing in the prompt protects a fact that appears only inside a "
        "section which otherwise restates earlier evidence")


def test_prompt_does_not_demand_a_claim_per_heading():
    text = _norm(NORMALIZER_PROMPT)

    assert ("not emit a claim for every heading" in text
            or "no claim for every heading" in text
            or "every heading or numbered section" in text), (
        "the prompt must not be read as requiring one claim per heading")


def test_prompt_keeps_the_accepted_anti_duplication_rules():
    """The new clarification must not remove the existing protection."""

    text = _norm(NORMALIZER_PROMPT)

    assert "do not repeat a whole paragraph" in text
    assert "avoid" in text and "duplicating a claim" in text
    assert "shortest-quote rule bounds the quote" in text


def test_prompt_contains_no_image_specific_reference():
    text = _norm(NORMALIZER_PROMPT).replace("\u2011", "-")

    for forbidden in ("four-bay", "four bay", "storey 3", "section 5",
                      "second row of windows in the same"):
        assert forbidden not in text, forbidden


def test_prompt_overlap_with_the_observer_text_stays_small():
    import difflib

    match = difflib.SequenceMatcher(
        None, _norm(NORMALIZER_PROMPT), _norm(_raw_text()), autojunk=False)
    run = max(block.size for block in match.get_matching_blocks())

    assert run < 30, "prompt shares a %d-character run with the observer text" % run


# ==========================================================
# §4 — unique versus redundant source evidence (read from the real text)
# ==========================================================


def test_the_unique_facts_exist_only_in_the_restatement_section():
    """B — proves the four-bay fact really is unique, not repeated elsewhere."""

    raw = _raw_text()

    assert raw.count(Q_BAY) == 1, "the bay relationship must occur exactly once"
    assert raw.count(Q_STOREY2) == 1
    assert raw.count(Q_STOREY4) == 1

    # ... and the storey-1 line adds nothing new: every one of its facts is
    # stated earlier in section 1.
    storey1 = "street\u2011level door, small square window, open arcade passage"
    assert storey1 in raw
    for fragment in ("door", "small square window", "arcade", "garage"):
        assert fragment in raw[: raw.index(storey1)], fragment


def test_the_scoped_absence_is_present_and_unique():
    """C — a scoped absence that must survive as its own fact."""

    raw = _raw_text()

    assert Q_SCOPED_ABSENCE in raw
    assert raw.count(Q_SCOPED_ABSENCE) == 1


def test_bay_and_row_counts_are_not_storey_counts():
    """D — the arrangement counts must not be read as floors."""

    raw = _raw_text()

    assert "four\u2011bay" in raw
    assert "three horizontal rows" in raw
    assert "Total storeys visible (including ground floor): 4" in raw


# ==========================================================
# 1 / 2 — quote integrity and deduplication
# ==========================================================


def test_quote_verification_is_unchanged():
    invented = _claim("the elevation repeats a nine-bay rhythm")
    understanding, _ = _chain(_payload([invented]))

    texts = [c["text"] for c in understanding["provider_candidates"]]
    assert invented["text"] not in texts


def test_a_genuinely_duplicate_claim_is_not_repeated():
    duplicate = _claim(Q_DOOR)
    _, report = _report(_payload([duplicate]),
                        None)

    # Same claim placed twice in two categories must render once.
    structured = _payload([duplicate])
    structured["openings"] = {"doors": [duplicate], "other_openings": [],
                              "windows": []}
    _, report = _report(structured)

    assert report.count(Q_DOOR) == 1


# ==========================================================
# 3 / 4 / 5 — arrangement retention, including a synthetic building
# ==========================================================


def test_a_unique_relationship_inside_a_restatement_is_reportable():
    _, report = _report(_payload([_claim(Q_BAY)]))

    assert Q_BAY in report
    assert "second row" in report
    assert "four\u2011bay" in report


def test_a_synthetic_six_bay_arrangement_flows_downstream():
    raw_observer = {**_raw_observer(), "raw_text": SYNTHETIC_OBSERVER}
    _, report = _report(
        _payload([_claim(Q_SYNTH_BAY), _claim(Q_SYNTH_ROWS)]), raw_observer)

    assert "six\u2011bay" in report or "six-bay" in report
    assert "two horizontal rows" in report
    assert "four" not in report.lower()


def test_no_bay_claim_without_bay_evidence():
    _, report = _report(_payload([_claim(Q_DOOR)]))

    assert "bay" not in report.lower()


# ==========================================================
# 6 / 7 / 8 — counts and scope
# ==========================================================


def test_a_bay_count_does_not_become_a_floor_count():
    _, interpretation = _chain(_payload([_claim(Q_BAY)]))
    reading = interpretation["architectural_observation"]["visible_floors_observation"]

    assert reading["count"] == 4
    assert reading["count_scope"] == "TOTAL"
    assert reading["ground_floor_included"] is True


def test_a_row_count_does_not_become_a_window_total():
    understanding, interpretation = _chain(_payload([_claim(Q_ROWS)]))

    candidate = next(c for c in understanding["provider_candidates"]
                     if c["text"] == Q_ROWS)
    assert candidate["count"] is None

    report = render_vision_report(interpretation, "fa")
    assert "12" not in report and "twelve" not in report.lower()


def test_subject_and_row_scope_survive():
    _, report = _report(_payload([_claim(Q_BAY)]))

    assert "windows" in Q_BAY and "windows" in report
    assert "second row" in Q_BAY and "second row" in report


# ==========================================================
# 9 / 10 / 11 / 12 / 13 / 14 — accepted contracts
# ==========================================================


def test_d5_quantity_certainty_is_unchanged():
    understanding, _ = _chain(_base())
    quantity = next(c for c in understanding["provider_candidates"]
                    if "several" in c["text"].lower())

    assert quantity["certainty"] == "ASSERTED"
    assert quantity["count"] is None


def test_d6_negative_evidence_stays_scoped():
    _, interpretation = _chain(_base())
    fragments = [f
                 for entry in interpretation["architectural_observation"]
                 .get("negative_observations") or []
                 for f in (entry.get("negated_texts") or [])]

    assert "no pitched roof" in fragments
    assert "no visible roof terrace" in fragments
    assert "no dormers" in fragments


def test_four_storeys_remain_provider_observation():
    _, interpretation = _chain(_base())
    observation = interpretation["architectural_observation"]
    reading = observation["visible_floors_observation"]

    assert observation["visible_floors"] is None
    assert reading["count"] == 4
    assert reading["trust_tier"] == "PROVIDER_OBSERVATION"
    assert reading["verification"] == "UNVERIFIED"
    assert reading["authoritative"] is False


def test_open_through_passage_is_preserved():
    _, report = _report(_base())

    assert "open through" in report.lower()
    assert "فضای بسته" not in report


def test_brick_ontology_resolution_is_preserved():
    _, interpretation = _chain(_base())
    knowledge = interpretation["architectural_knowledge"]
    entry = next(e for e in knowledge["materials"] if e["ontology_id"] == "brick")

    assert entry["ontology_normalized"] == "brick facade"
    assert entry["subtype_established"] is False
    assert knowledge["resolves_evidence"] is False


def test_style_remains_insufficient_evidence():
    _, interpretation = _chain(_base())
    style = interpretation["architectural_knowledge"]["style"]

    assert style["status"] == "INSUFFICIENT_EVIDENCE"
    assert style["assigned"] is None


# ==========================================================
# §9 — KNOWN DEFECTS, recorded not fixed
# ==========================================================


def test_witness_unbounded_substring_matching_is_fixed():
    """FORMERLY A WITNESS, NOW A CORRECTNESS TEST.

    This test used to assert that two defects REPRODUCED:

      1. "street" contains "tree"  -> an asphalt street was labelled `plant`.
      2. "through" contains "rough" -> a visibility phrase got texture `rough`.

    VISION_CLASSIFICATION_SAFETY_V1 fixed the root cause (unanchored
    `marker in phrase`) in `core/vision/architectural_observation_v1.py`, so
    the assertions are inverted rather than deleted: the same two phrases must
    now classify as nothing, and the genuine words must still classify.
    """

    from core.vision.architectural_observation_v1 import (
        OBJECT_MARKERS, TEXTURE_MARKERS, _labels,
    )

    street = "Foreground asphalt street with painted lines and a paved footway"
    through = "leading to a view through to the other side"

    # The substrings are still physically present — that was never the point.
    assert "tree" in "street"
    assert "rough" in "through"

    # ...but they no longer carry the label.
    assert _labels(street, OBJECT_MARKERS) == []
    assert _labels(through, TEXTURE_MARKERS) == []

    # The genuine vocabulary still classifies.
    assert "plant" in _labels("a mature tree", OBJECT_MARKERS)
    assert "rough" in _labels("rough stone", TEXTURE_MARKERS)

    # The saved 2026-10 artifact was produced BEFORE the fix. It is kept as a
    # frozen record of the defect, not as evidence of correct behaviour.
    with open(os.path.join(ROOT, "runs", "vision_d7_arrangement_v1",
                           "live_d7_v1.json"), encoding="utf-8") as fh:
        saved = json.load(fh)
    observation = saved["architectural_observation"]

    assert any(e.get("kind") == ["plant"]
               for e in observation.get("object_elements") or []), (
        "the pre-fix artifact should still show the historical false positive")
    assert any("rough" in (e.get("textures") or [])
               for e in observation.get("texture_color_observations") or [])
