# -*- coding: utf-8 -*-
"""VISION_FIRST_D6_NEGATIVE_EVIDENCE_BRIDGE_V1 — focused CPU tests.

Defect: a model-reported architectural absence is silently lost between the
verified provider candidates and the architectural observation, whenever the
absence's SUBJECT is a recognised architectural element.

Two independent causes, both proved in the previous milestone:

  D6.1  `provider_candidate_verification_v1._decision()` returns
        `negative_claim_requires_explicit_local_absence` for a negative claim
        whose `kind` is in `_KINDS[category]` (window, opening, door, column,
        stair, furniture). `_build_bridge_understanding` admits ONLY
        `no_applicable_independent_corroboration` into the attributed band, so
        those absences vanish. An absence about `roof` survives, because
        `roof` is not an element kind.
  D6.2  `ARCHITECTURAL_ELEMENT_MARKERS` has no `dormer` label, so
        "no dormers" falls through to `unclassified_observations` and never
        becomes an absence record.

FIXTURES
--------
* `runs/vision_facade_evidence_semantics_v1/live_semantics_v1.json` — the
  accepted real saved output, used IMMUTABLE as the structured baseline.
* `runs/vision_facade_compound_v1/live_compound_v1.json` — its `raw_observer`,
  the byte-identical observer text (sha `9210ac9a…`) those claims were
  verified against.
* Synthetic candidates are used only where the model never emitted the needed
  negative claim, and every quote is a verbatim slice of that real observer
  text, so `parse_normalization` really verifies it.

No Ollama. No GPU. No ComfyUI. No prompt change.
"""

import json
import os

import pytest

from core.vision.architectural_observation_v1 import (
    ARCHITECTURAL_ELEMENT_MARKERS,
    build_architectural_observation,
)
from core.vision.architectural_vision_interpreter_v1 import interpret_architectural_vision
from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
from core.vision.image_understanding_v1 import build_understanding
from core.vision.vision_report_v1 import render_vision_report


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEMANTICS = os.path.join(ROOT, "runs", "vision_facade_evidence_semantics_v1",
                         "live_semantics_v1.json")
COMPOUND = os.path.join(ROOT, "runs", "vision_facade_compound_v1",
                        "live_compound_v1.json")

OBSERVER_SHA = "9210ac9ab659db686606a0284b1360f0b322a4bb911a1344d76c635611f6f155"

Q_NEG_ROOF = "no pitched roof"
Q_NEG_TERRACE = "no visible roof terrace"
Q_NEG_DORMERS = "no dormers"
Q_NEG_SCOPED = "no windows or openings above the top window row"
Q_POS_WINDOWS = "Rectangular, dark\u2011framed (black/bronze) windows"
Q_POS_DOOR = "One dark, recessed pedestrian door on the ground floor, left of centre"

#: From the ARCHIVED v1.3 observer text (a genuine observer phrase that the
#: current text does not contain). Used only for the pier/column polarity test.
Q_NEG_COLUMNS = ("no visible columns other than the ground\u2011floor piers of "
                 "the arcade")


def _semantics():
    with open(SEMANTICS, encoding="utf-8") as fh:
        return json.load(fh)


def _raw():
    with open(COMPOUND, encoding="utf-8") as fh:
        return json.load(fh)


def _raw_text():
    return _raw()["raw_text"]


def _raw_observer():
    return _raw()["raw_observer"]


def _claim(text, kind, certainty="ASSERTED", count=None, quote=None):
    return {"text": text, "source_quote": quote or text, "kind": kind,
            "certainty": certainty, "count": count}


def _payload(**slots):
    """The accepted saved payload with the given categories replaced.

    The full payload is used because `validate_structured` requires every
    schema category.
    """

    base = json.loads(json.dumps(_semantics()["normalization"]["structured"]))
    base["observed_elements"] = []
    base["walls"] = []
    base["structural_elements"] = []
    base["spatial_relationships"] = []
    base["openings"] = {"doors": [], "windows": [], "other_openings": []}
    for key, value in slots.items():
        base[key] = value
    return base


def _chain(structured):
    understanding = build_understanding(
        {"contract": BRIDGE_CONTRACT, "raw_observer": _raw_observer(),
         "normalization": {"status": "NORMALIZED", "structured": structured}},
        provider="ollama", model="qwen3.8:27b", image_id="V3", source_type="other")
    return understanding, interpret_architectural_vision(understanding)


def _negatives(interpretation):
    return (interpretation["architectural_observation"]
            .get("negative_observations") or [])


def _fragments(interpretation):
    return [fragment
            for entry in _negatives(interpretation)
            for fragment in (entry.get("negated_texts") or [])]


def _visible(interpretation):
    return [entry.get("evidence_phrase")
            for entry in (interpretation["architectural_observation"]
                          .get("architectural_elements") or [])
            if entry.get("status") == "visible"]


# ==========================================================
# Fixture integrity
# ==========================================================


def test_fixtures_are_the_accepted_saved_evidence():
    import hashlib

    raw = _raw_text()

    assert hashlib.sha256(raw.encode("utf-8")).hexdigest() == OBSERVER_SHA
    assert _semantics()["normalization"]["status"] == "NORMALIZED"
    for quote in (Q_NEG_ROOF, Q_NEG_TERRACE, Q_NEG_DORMERS, Q_NEG_SCOPED,
                  Q_POS_WINDOWS, Q_POS_DOOR):
        assert quote in raw, quote


# ==========================================================
# A / B — absences that already survive
# ==========================================================


def test_a_no_pitched_roof_is_an_attributed_negative():
    _, interpretation = _chain(_payload(
        observed_elements=[_claim(Q_NEG_ROOF, "roof")]))

    assert Q_NEG_ROOF in _fragments(interpretation)
    assert Q_NEG_ROOF not in _visible(interpretation)


def test_b_no_visible_roof_terrace_keeps_its_scope():
    _, interpretation = _chain(_payload(
        observed_elements=[_claim(Q_NEG_TERRACE, "roof")]))

    fragments = _fragments(interpretation)

    assert Q_NEG_TERRACE in fragments
    assert "no roof terrace" not in fragments, "the 'visible' qualifier was lost"


# ==========================================================
# C — D6.2 dormer classification
# ==========================================================


def test_c_dormer_is_a_known_architectural_element():
    vocabulary = {label for label, _ in ARCHITECTURAL_ELEMENT_MARKERS}

    assert "dormer" in vocabulary, (
        "no `dormer` label exists, so 'no dormers' can never become an "
        "absence record (D6.2)")


def test_c_no_dormers_becomes_a_negative_roof_element():
    _, interpretation = _chain(_payload(
        observed_elements=[_claim(Q_NEG_DORMERS, "dormer")]))

    assert Q_NEG_DORMERS in _fragments(interpretation)
    assert Q_NEG_DORMERS not in _visible(interpretation)

    report = render_vision_report(interpretation, "fa")
    assert Q_NEG_DORMERS in report


def test_c_no_dormers_is_never_a_positive_dormer():
    _, interpretation = _chain(_payload(
        observed_elements=[_claim(Q_NEG_DORMERS, "dormer")]))

    observation = interpretation["architectural_observation"]

    for entry in observation.get("architectural_elements") or []:
        if entry.get("status") != "visible":
            continue
        assert "dormer" not in (entry.get("kind") or [])


# ==========================================================
# D / E / F — D6.1 scoped window negative
# ==========================================================


def test_d_scoped_window_negative_survives():
    understanding, interpretation = _chain(_payload(
        observed_elements=[_claim(Q_NEG_SCOPED, "window")]))

    assert Q_NEG_SCOPED in _fragments(interpretation), (
        "the absence vanished because its subject is a recognised element")

    band = understanding.get("absence_attributed") or []
    assert any(entry.get("text") == Q_NEG_SCOPED for entry in band)


def test_e_scoped_window_negative_is_never_widened():
    _, interpretation = _chain(_payload(
        observed_elements=[_claim(Q_NEG_SCOPED, "window")]))

    fragments = _fragments(interpretation)

    # Precondition: the absence must actually be present, otherwise "not
    # widened" would pass vacuously on a total loss.
    assert Q_NEG_SCOPED in fragments

    assert "no windows" not in fragments
    assert "no openings" not in fragments
    assert not any(f.strip().lower() == "no window" for f in fragments)


def test_f_positive_windows_and_doors_survive_alongside_the_negative():
    _, interpretation = _chain(_payload(
        observed_elements=[_claim(Q_NEG_SCOPED, "window")],
        openings={"doors": [_claim(Q_POS_DOOR, "door")],
                  "other_openings": [],
                  "windows": [_claim(Q_POS_WINDOWS, "window")]}))

    report = render_vision_report(interpretation, "fa")

    # Both positives must still reach the user ...
    assert Q_POS_WINDOWS in report
    assert Q_POS_DOOR in report

    # ... in the positive block, not the absence block ...
    positive, _, absence = report.partition("مواردی که مدل صریحاً غایب")
    assert Q_POS_WINDOWS in positive
    assert Q_POS_DOOR in positive
    assert Q_NEG_SCOPED not in positive

    # ... and the absence must be reported as an absence, scoped as stated.
    assert Q_NEG_SCOPED in absence
    assert "no windows" not in absence.replace(Q_NEG_SCOPED, "")


# ==========================================================
# G — a negative must never erase positive evidence
# ==========================================================


def test_g_negative_columns_do_not_erase_positive_piers():
    observation = build_architectural_observation(
        {"observed": [Q_NEG_COLUMNS], "confidence": "LOW"},
        provider="ollama", model="qwen3.8:27b", image_id="synthetic",
        source_type="other")

    kinds = {kind
             for entry in observation.get("architectural_elements") or []
             for kind in (entry.get("kind") or [])}
    fragments = [fragment
                 for entry in observation.get("negative_observations") or []
                 for fragment in (entry.get("negated_texts") or [])]

    assert "pier" in kinds, "the exception clause names a real element"
    assert "column" not in kinds
    assert any("other than the ground\u2011floor piers" in f for f in fragments)


# ==========================================================
# H / I / J — trust boundary
# ==========================================================


def test_h_a_fabricated_negative_is_rejected():
    invented = "no basement windows exist anywhere on the site"
    understanding, interpretation = _chain(_payload(
        observed_elements=[_claim(invented, "window")]))

    texts = [c["text"] for c in understanding["provider_candidates"]]

    assert invented not in texts
    assert invented not in _fragments(interpretation)


def test_i_a_hedged_absence_is_not_strengthened():
    hedged = _claim(Q_NEG_SCOPED, "window", certainty="AMBIGUOUS")
    understanding, interpretation = _chain(_payload(observed_elements=[hedged]))

    candidate = next(c for c in understanding["provider_candidates"]
                     if c["text"] == Q_NEG_SCOPED)
    assert candidate["state"] == "AMBIGUOUS"

    band = understanding.get("absence_attributed") or []
    assert not any(entry.get("text") == Q_NEG_SCOPED for entry in band), (
        "an ambiguous claim was admitted as an ASSERTED absence")
    assert Q_NEG_SCOPED not in _fragments(interpretation)


def test_j_no_independent_corroboration_is_invented():
    understanding, _ = _chain(_payload(
        observed_elements=[_claim(Q_NEG_SCOPED, "window")]))

    assert (understanding.get("grounded_provider_evidence") or []) == []

    for entry in understanding.get("absence_attributed") or []:
        assert entry.get("state") == "UNVERIFIED"
        assert entry.get("grounded") is False


# ==========================================================
# K / L / M — accepted observations unchanged
# ==========================================================


def test_k_four_storey_reading_and_parapet_are_unchanged():
    base = json.loads(json.dumps(_semantics()["normalization"]["structured"]))
    _, interpretation = _chain(base)

    observation = interpretation["architectural_observation"]
    reading = observation["visible_floors_observation"]

    assert observation["visible_floors"] is None
    assert reading["count"] == 4
    assert reading["roof_band_excluded"] is True
    assert reading["trust_tier"] == "PROVIDER_OBSERVATION"
    assert reading["verification"] == "UNVERIFIED"


def test_l_through_passage_remains_open():
    base = json.loads(json.dumps(_semantics()["normalization"]["structured"]))
    _, interpretation = _chain(base)

    report = render_vision_report(interpretation, "fa")

    assert "open through" in report.lower()
    assert "فضای بسته" not in report


def test_m_no_geometry_is_invented():
    _, interpretation = _chain(_payload(
        observed_elements=[_claim(Q_NEG_SCOPED, "window")]))

    serialised = json.dumps(interpretation["architectural_observation"]).lower()

    for key in ("bbox", "bounding_box", "polygon", "coordinates", "vertices"):
        assert key not in serialised, key


# ==========================================================
# N / O — provenance and presentation
# ==========================================================


def test_n_admitted_absence_keeps_quote_attribution_and_status():
    raw = _raw_text()
    understanding, _ = _chain(_payload(
        observed_elements=[_claim(Q_NEG_SCOPED, "window")]))

    entry = next(e for e in understanding["absence_attributed"]
                 if e.get("text") == Q_NEG_SCOPED)

    assert entry["source_quote"] in raw, "the quote is not verbatim"
    assert entry["reason"] == "negative_claim_requires_explicit_local_absence", (
        "the original verifier reason was not preserved")
    assert entry["state"] == "UNVERIFIED"
    assert entry["category"] == "observed_elements"


def test_o_report_separates_absence_from_established_facts():
    _, interpretation = _chain(_payload(
        observed_elements=[_claim(Q_NEG_SCOPED, "window")],
        openings={"doors": [], "other_openings": [],
                  "windows": [_claim(Q_POS_WINDOWS, "window")]}))

    report = render_vision_report(interpretation, "fa")

    header = "مواردی که مدل صریحاً غایب"
    assert header in report, "the absence section is missing"

    positive, _, absence = report.partition(header)

    assert Q_POS_WINDOWS in positive
    assert Q_NEG_SCOPED not in positive
    assert Q_NEG_SCOPED in absence

    # The absence note must still say it is evidence about this image only.
    assert "نه اثبات نبودِ آن در ساختمان" in report
