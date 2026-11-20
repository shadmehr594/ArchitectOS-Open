# -*- coding: utf-8 -*-
"""VISION_FIRST_D7_ARCHITECTURAL_ARRANGEMENT_V1 — focused CPU tests.

Defect: the real observer states a facade arrangement relationship

    second row of windows in the same four-bay arrangement

and the normalizer does not emit it as a supported claim, so the relationship is
lost while the individual windows survive.

ANTI-OVERFITTING (brief §3)
---------------------------
The previous milestone added an example to `NORMALIZER_PROMPT` that is
NEAR-VERBATIM the acceptance sentence (38-character common substring; identical
but for U+2011 vs ASCII hyphen). Producing that phrase in one model output would
therefore prove nothing. `test_prompt_*` below enforces that the example is
generalised away before any inference is spent.

FIXTURES
--------
* `runs/vision_facade_compound_v1/live_compound_v1.json` — the immutable saved
  observer record (raw_text sha `9210ac9a…`).
* `runs/vision_facade_evidence_semantics_v1/live_semantics_v1.json` — the
  accepted saved normalizer output, used as the structured baseline.
* SYNTHETIC fixtures are labelled and are used only where the real observer
  never stated the relationship (a paraphrased arrangement with different
  numbers).

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

#: Real observer text, with the non-breaking hyphen the observer actually used.
Q_BAY = "second row of windows in the same four\u2011bay arrangement"
Q_ROWS = "They appear in three horizontal rows above the ground level"

#: SYNTHETIC observer fixture — a different building, different numbers.
SYNTHETIC_OBSERVER = (
    "The street elevation shows a six-bay rhythm. "
    "The upper row repeats the same six-bay rhythm above the entrance level. "
    "Openings are grouped in two horizontal rows."
)
Q_SYNTH_BAY = "The upper row repeats the same six-bay rhythm above the entrance level"
Q_SYNTH_ROWS = "Openings are grouped in two horizontal rows"

ARRANGEMENT_MARKER = "FACADE ARRANGEMENT"


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


# ==========================================================
# §3 — the prompt must not contain the acceptance sentence
# ==========================================================


def _normalise(text):
    return " ".join(text.split()).lower()


def _longest_common_run(a, b):
    import difflib
    match = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return max(block.size for block in match.get_matching_blocks())


def test_prompt_does_not_contain_the_acceptance_phrase():
    """A prompt example that IS the answer cannot prove extraction."""

    prompt = _normalise(NORMALIZER_PROMPT).replace("\u2011", "-")
    phrase = _normalise(Q_BAY).replace("\u2011", "-")

    assert phrase not in prompt, (
        "the prompt still contains the acceptance sentence verbatim, so a "
        "match would be tautological")


def test_prompt_overlap_with_the_observer_text_is_small():
    """Near-verbatim overlap is as bad as verbatim overlap."""

    run = _longest_common_run(_normalise(NORMALIZER_PROMPT), _normalise(_raw_text()))

    assert run < 30, (
        "the prompt shares a %d-character run with the observer text; an "
        "example that long can be copied rather than extracted" % run)


def test_prompt_states_the_arrangement_rule_generically():
    assert ARRANGEMENT_MARKER in NORMALIZER_PROMPT


def test_prompt_arrangement_example_is_not_image_specific():
    lowered = _normalise(NORMALIZER_PROMPT)

    assert "four-bay" not in lowered.replace("\u2011", "-"), (
        "an image-specific bay count is still used as the example")
    assert "four bay" not in lowered


def test_prompt_keeps_the_accepted_rules():
    """The D4 / D5 / D6 instructions must survive the generalisation."""

    assert "COMPOUND ARCHITECTURAL EVIDENCE" in NORMALIZER_PROMPT
    assert "QUANTITY, CERTAINTY AND POLARITY" in NORMALIZER_PROMPT
    assert "never achieve brevity by dropping" in _normalise(NORMALIZER_PROMPT)


# ==========================================================
# A / B / C — the downstream already carries arrangement claims
# ==========================================================


def test_a_bay_relationship_is_carried_downstream():
    """SYNTHETIC wording (not the acceptance phrase) must also survive."""

    _, report = _report(_payload([_claim(Q_SYNTH_BAY)]), {
        **_raw_observer(), "raw_text": SYNTHETIC_OBSERVER})

    assert Q_SYNTH_BAY in report


def test_b_three_horizontal_rows_are_carried_downstream():
    _, report = _report(_payload([_claim(Q_ROWS)]))

    assert Q_ROWS in report
    assert "three horizontal rows" in report


def test_c_second_row_arrangement_is_carried_downstream():
    _, report = _report(_payload([_claim(Q_BAY)]))

    assert Q_BAY in report
    assert "second row" in report
    assert "four\u2011bay" in report


def test_d_a_paraphrased_arrangement_with_other_numbers_works():
    """SYNTHETIC observer fixture: six bays, two rows — no 'four' anywhere."""

    raw_observer = {**_raw_observer(), "raw_text": SYNTHETIC_OBSERVER}
    _, report = _report(
        _payload([_claim(Q_SYNTH_BAY), _claim(Q_SYNTH_ROWS)]), raw_observer)

    assert "six\u2011bay" in report or "six-bay" in report
    assert "two horizontal rows" in report
    assert "four" not in report.lower(), "a four-bay answer leaked into a six-bay fixture"


# ==========================================================
# E / F / G — certainty and evidence integrity
# ==========================================================


def test_e_a_hedged_arrangement_stays_uncertain():
    hedged = _claim(Q_BAY, certainty="AMBIGUOUS")
    understanding, interpretation = _chain(_payload([hedged]))

    candidate = next(c for c in understanding["provider_candidates"]
                     if c["text"] == Q_BAY)
    assert candidate["state"] == "AMBIGUOUS"

    report = render_vision_report(interpretation, "fa")
    _, _, ambiguous = report.partition("خوانش‌های مبهم")
    assert Q_BAY in ambiguous


def test_f_a_claim_without_a_verbatim_quote_is_rejected():
    invented = "the facade repeats a nine-bay rhythm on every level"
    understanding, _ = _chain(_payload([_claim(invented)]))

    texts = [c["text"] for c in understanding["provider_candidates"]]
    assert invented not in texts


def test_g_a_fabricated_arrangement_is_rejected():
    fabricated = _claim("second row of windows in the same eight-bay arrangement",
                        quote="second row of windows in the same eight-bay arrangement")
    understanding, _ = _chain(_payload([fabricated]))

    texts = [c["text"] for c in understanding["provider_candidates"]]
    assert fabricated["text"] not in texts


# ==========================================================
# H / I / J / K — no invented counts, no geometry
# ==========================================================


def test_h_four_bays_do_not_imply_four_floors():
    _, interpretation = _chain(_payload([_claim(Q_BAY)]))
    reading = interpretation["architectural_observation"]["visible_floors_observation"]

    assert reading["count"] == 4, "the real storey count must be unchanged"
    # ... and it comes from the observer's storey statement, not from the bays.
    assert reading["count_scope"] == "TOTAL"
    assert reading["ground_floor_included"] is True


def test_i_three_rows_do_not_imply_three_floors():
    _, interpretation = _chain(_payload([_claim(Q_ROWS)]))
    reading = interpretation["architectural_observation"]["visible_floors_observation"]

    assert reading["count"] == 4
    assert reading["upper_floors"] == 3


def test_j_bays_times_rows_never_becomes_a_window_total():
    understanding, interpretation = _chain(
        _payload([_claim(Q_BAY), _claim(Q_ROWS)]))

    for text in (Q_BAY, Q_ROWS):
        candidate = next(c for c in understanding["provider_candidates"]
                         if c["text"] == text)
        assert candidate["count"] is None, (
            "a bay or row count became a numeric total")

    report = render_vision_report(interpretation, "fa")

    assert "12" not in report
    assert "twelve" not in report.lower()
    assert "total of" not in report.lower()


def test_k_no_geometry_is_invented():
    _, interpretation = _chain(_payload([_claim(Q_BAY)]))

    observation = interpretation["architectural_observation"]

    # No geometry-bearing KEY exists on the contract.
    for key in ("bbox", "bounding_box", "polygon", "coordinates", "vertices"):
        assert key not in observation, key

    # And the contract still declares the limitation in its own words.
    serialised = json.dumps(observation).lower()
    assert "no dimensions or measurements are inferred" in serialised
    assert "no bounding boxes" in serialised


def test_l_the_claim_keeps_subject_row_and_relation():
    _, report = _report(_payload([_claim(Q_BAY)]))

    # subject, row scope and relation all still present in one claim
    assert "windows" in Q_BAY
    assert "second row" in Q_BAY
    assert "same" in Q_BAY
    assert Q_BAY in report


# ==========================================================
# M / N / O — accepted evidence must not regress
# ==========================================================


def test_m_compound_window_evidence_is_not_lost():
    base = _base()
    _, report = _report(base)

    assert "Rectangular, dark\u2011framed (black/bronze) windows" in report
    assert "several are multi\u2011pane with thin mullions/transoms" in report


def test_n_d5_quantity_and_d6_absence_do_not_regress():
    base = _base()
    _, interpretation = _chain(base)
    report = render_vision_report(interpretation, "fa")

    # D5 — asserted quantity, positive band, no integer
    quantity = next(c for c in _chain(_base())[0]["provider_candidates"]
                    if "several" in c["text"].lower())
    assert quantity["certainty"] == "ASSERTED"
    assert quantity["count"] is None
    assert quantity["text"] in report

    # D6 — absence still scoped and still reported
    fragments = [f
                 for entry in interpretation["architectural_observation"]
                 .get("negative_observations") or []
                 for f in (entry.get("negated_texts") or [])]
    assert "no pitched roof" in fragments
    assert "no dormers" in fragments
    assert "no pitched roof" in report


def test_o_the_open_through_passage_is_preserved():
    _, report = _report(_base())

    assert "open through" in report.lower()
    assert "فضای بسته" not in report


# ==========================================================
# P / Q — knowledge layer unchanged
# ==========================================================


def test_p_material_knowledge_still_reports_generic_brick():
    _, interpretation = _chain(_base())

    knowledge = interpretation["architectural_knowledge"]
    entry = next(e for e in knowledge["materials"] if e["ontology_id"] == "brick")

    assert entry["ontology_normalized"] == "brick facade"
    assert entry["subtype_established"] is False
    assert knowledge["resolves_evidence"] is False


def test_q_style_remains_unsupported():
    _, interpretation = _chain(_base())
    style = interpretation["architectural_knowledge"]["style"]

    assert style["status"] == "INSUFFICIENT_EVIDENCE"
    assert style["assigned"] is None
