# -*- coding: utf-8 -*-
"""VISION_FACADE_EVIDENCE_SEMANTICS_V1 — focused CPU tests.

Defects under test, all measured against the ONE fixed real observer text saved
in `runs/vision_facade_compound_v1/live_compound_v1.json`
(raw_text sha256 `9210ac9a…`, 2963 chars):

  D5  `several are multi-pane with thin mullions/transoms` became two bare
      AMBIGUOUS fragments, losing the subject, the quantifier and the fact that
      the observer ASSERTED them.
  D6  Explicit negatives produced no negative claims at all.
  D7  `second row of windows in the same four-bay arrangement` was not retained.

`§4` of the brief requires the DOWNSTREAM representation to be proved before the
prompt is touched, so the payload tests below drive the real
`build_understanding` → interpreter → report chain with synthetic structured
claims whose quotes are exact slices of the real observer text.

WHAT THIS FILE DOES NOT PROVE: that the normalizer model obeys any instruction.
CPU prompt-text assertions are contract checks, not behavioural proof.

No Ollama. No GPU. No ComfyUI.
"""

import json
import os

import pytest

from core.vision.architectural_observation_v1 import build_architectural_observation
from core.vision.architectural_vision_interpreter_v1 import interpret_architectural_vision
from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
from core.vision.image_understanding_v1 import build_understanding
from core.vision.observation_normalizer_v1 import NORMALIZER_PROMPT
from core.vision.vision_report_v1 import render_vision_report


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RECORD = os.path.join(ROOT, "runs", "vision_facade_compound_v1", "live_compound_v1.json")

EXPECTED_RAW_SHA = "9210ac9ab659db686606a0284b1360f0b322a4bb911a1344d76c635611f6f155"

PROMPT_MARKER = "QUANTITY, CERTAINTY AND POLARITY"

#: Exact slices of the real observer text, so every quote passes verification.
Q_QUANTITY = "several are multi\u2011pane with thin mullions/transoms"
#: The same fact WITH its subject — what D5 requires the normalizer to emit,
#: because the user sees the claim text alone and "several are multi-pane"
#: never says several *what*.
Q_QUANTITY_SUBJECT = ("windows arranged in a grid; several are multi\u2011pane "
                      "with thin mullions/transoms")
Q_NEG_ROOF = "no pitched roof, no visible roof terrace, no dormers"
Q_NEG_SCOPED = ("no roof terrace, no attic band, and no windows or openings "
                "above the top window row")
Q_BAY = "second row of windows in the same four\u2011bay arrangement"
Q_ROWS = "three horizontal rows"


def _record():
    with open(RECORD, encoding="utf-8") as fh:
        return json.load(fh)


def _raw():
    return _record()["raw_text"]


def _prompt():
    return " ".join(NORMALIZER_PROMPT.lower().split())


def _claim(text, kind, certainty="ASSERTED", count=None, quote=None):
    return {"text": text, "source_quote": quote or text, "kind": kind,
            "certainty": certainty, "count": count}


def _chain(structured):
    """The real production chain, from a structured normalizer payload."""

    record = _record()
    understanding = build_understanding(
        {"contract": BRIDGE_CONTRACT, "raw_observer": record["raw_observer"],
         "normalization": {"status": "NORMALIZED", "structured": structured}},
        provider="ollama", model="qwen3.8:27b", image_id="V3", source_type="other")
    return understanding, interpret_architectural_vision(understanding)


def _payload(**slots):
    """The saved structured payload with the given categories replaced.

    The FULL payload is used because `validate_structured` requires every
    schema category; a minimal dict is rejected before any claim is examined.
    """

    base = json.loads(json.dumps(_record()["normalization"]["structured"]))
    base["observed_elements"] = []
    base["walls"] = []
    base["structural_elements"] = []
    base["spatial_relationships"] = []
    base["openings"] = {"doors": [], "windows": [], "other_openings": []}
    for key, value in slots.items():
        base[key] = value
    return base


# ==========================================================
# Fixture identity
# ==========================================================


def test_fixture_is_the_saved_real_observer_text():
    """The experiment isolates the normalizer against ONE fixed text."""

    import hashlib

    raw = _raw()

    assert hashlib.sha256(raw.encode("utf-8")).hexdigest() == EXPECTED_RAW_SHA
    for quote in (Q_QUANTITY, Q_NEG_ROOF, Q_NEG_SCOPED, Q_BAY, Q_ROWS):
        assert quote in raw, quote


# ==========================================================
# RED — prompt contract for D5 / D6 / D7
# ==========================================================


def test_prompt_states_that_quantity_is_not_a_hedge():
    """D5 — 'several' must not be read as epistemic doubt."""

    text = _prompt()

    assert PROMPT_MARKER in NORMALIZER_PROMPT
    assert "several" in text
    assert ("not a hedge" in text or "is not hedging" in text), (
        "the prompt still gives the model no way to tell a quantity word from "
        "a genuine hedge, so 'several are multi-pane' can be demoted to "
        "AMBIGUOUS")


def test_prompt_requires_quantifier_to_stay_with_its_subject():
    """D5 — the claim must keep WHAT is quantified, not just the adjective."""

    text = _prompt()

    assert ("with the element it counts" in text
            or "subject" in text), (
        "nothing requires the claim text to keep the element the quantifier "
        "counts")


def test_prompt_requires_explicit_negatives_to_be_emitted():
    """D6 — an absence the observer states is itself a fact."""

    text = _prompt()

    assert ("explicit absence" in text or "explicit negative" in text), (
        "the prompt never says a stated absence must be emitted as a claim, "
        "which is why the run produced no negative claims at all")


def test_prompt_requires_negative_scope_to_be_kept():
    """D6 — 'no windows above the top row' must not become 'no windows'."""

    text = _prompt()

    assert "qualifier" in text
    assert ("never be shortened" in text or "absolute" in text), (
        "the prompt does not warn that a restricted absence must keep its "
        "qualifier instead of collapsing into an absolute denial")
    assert "above the top row" in text, "no positional example of a scoped absence"


def test_prompt_requires_bay_and_row_relationship_retention():
    """D7 — a bay/row arrangement must survive, without inventing a total.

    D7_ARCHITECTURAL_ARRANGEMENT_V1 — this test used to require the acceptance
    image's own "four-bay" phrase to appear in the prompt. That example was
    near-verbatim the answer being tested, so it was generalised away (§3 of
    the D7 brief). The requirement was always the INSTRUCTION, not that
    specific wording, so it is now asserted generically.
    """

    text = _prompt()

    assert "FACADE ARRANGEMENT" in NORMALIZER_PROMPT
    assert "bay" in text and "row" in text
    assert "per-storey" in text or "storey evidence" in text, (
        "the prompt does not tell the model that per-storey evidence lines "
        "carry claimable facts")
    assert "multiply a bay count" in text, (
        "nothing forbids turning bays x rows into a window total")


def test_prompt_keeps_the_accepted_compound_paragraph():
    """Regression: the previous milestone's instruction must not be replaced."""

    assert "COMPOUND ARCHITECTURAL EVIDENCE" in NORMALIZER_PROMPT
    assert "never achieve brevity by dropping" in _prompt()


# ==========================================================
# GREEN — downstream representation proof (§4)
# ==========================================================


def test_downstream_can_carry_an_asserted_scoped_quantity():
    """§4(a) — asserted claim with a quantity qualifier survives to the user.

    The claim must reach the user with its SUBJECT: the report bullet has to
    say several *windows*, not just "several".
    """

    structured = _payload(**{"openings": {"doors": [], "other_openings": [],
                                          "windows": [_claim(Q_QUANTITY_SUBJECT,
                                                             "window")]}})
    understanding, interpretation = _chain(structured)

    candidate = next(c for c in understanding["provider_candidates"]
                     if c["text"] == Q_QUANTITY_SUBJECT)

    assert candidate["state"] == "UNVERIFIED"
    assert candidate["certainty"] == "ASSERTED"
    assert candidate["category"] == "openings.windows", "subject association lost"

    report = render_vision_report(interpretation, "fa")

    assert Q_QUANTITY_SUBJECT in report

    line = next(l for l in report.splitlines() if "several" in l.lower())
    assert "window" in line.lower(), (
        "the quantifier lost its subject: %r" % line)
    assert "mullion" in line.lower()


def test_a_quantifier_never_becomes_an_integer():
    """D5 — 'several' must not be turned into a number."""

    structured = _payload(**{"openings": {"doors": [], "other_openings": [],
                                          "windows": [_claim(Q_QUANTITY_SUBJECT,
                                                             "window")]}})
    understanding, _ = _chain(structured)

    candidate = next(c for c in understanding["provider_candidates"]
                     if c["text"] == Q_QUANTITY_SUBJECT)

    assert candidate["count"] is None


def test_asserted_quantity_lands_in_the_positive_band():
    """D5 — an asserted feature is not reported as an ambiguous reading."""

    structured = _payload(**{"openings": {"doors": [], "other_openings": [],
                                          "windows": [_claim(Q_QUANTITY_SUBJECT,
                                                             "window")]}})
    _, interpretation = _chain(structured)

    report = render_vision_report(interpretation, "fa")

    positive, _, ambiguous = report.partition("خوانش‌های مبهم")
    assert Q_QUANTITY_SUBJECT in positive
    assert Q_QUANTITY_SUBJECT not in ambiguous


def test_genuine_hedging_stays_ambiguous():
    """D5 — a genuinely hedged claim must remain in the ambiguous band.

    The fixture reuses the real quote with certainty AMBIGUOUS because the
    archived observer expressed no hedge about this feature; the property under
    test is the CERTAINTY routing, not the wording.
    """

    structured = _payload(**{"openings": {"doors": [], "other_openings": [],
                                          "windows": [_claim(Q_QUANTITY_SUBJECT,
                                                             "window",
                                                             certainty="AMBIGUOUS")]}})
    understanding, interpretation = _chain(structured)

    candidate = next(c for c in understanding["provider_candidates"]
                     if c["text"] == Q_QUANTITY_SUBJECT)
    assert candidate["state"] == "AMBIGUOUS"

    report = render_vision_report(interpretation, "fa")
    _, _, ambiguous = report.partition("خوانش‌های مبهم")
    assert Q_QUANTITY_SUBJECT in ambiguous


def test_downstream_can_carry_scoped_negative_observations():
    """§4(b) — an explicit absence with a non-element kind is representable."""

    structured = _payload(**{"observed_elements": [_claim(Q_NEG_ROOF, "roof")]})
    _, interpretation = _chain(structured)

    negatives = interpretation["architectural_observation"]["negative_observations"]
    fragments = [f for entry in negatives for f in (entry.get("negated_texts") or [])]

    assert "no pitched roof" in fragments
    assert "no visible roof terrace" in fragments
    assert "no dormers" in fragments

    report = render_vision_report(interpretation, "fa")
    assert "no visible roof terrace" in report


def test_negative_scope_is_not_widened():
    """D6 — 'above the top window row' must survive in the absence record."""

    observation = build_architectural_observation(
        {"observed": [Q_NEG_SCOPED], "confidence": "LOW"},
        provider="ollama", model="qwen3.8:27b", image_id="synthetic",
        source_type="other")

    fragments = [f for entry in observation["negative_observations"]
                 for f in (entry.get("negated_texts") or [])]

    assert "no windows or openings above the top window row" in fragments
    assert "no openings" not in fragments
    assert "no windows" not in fragments


def test_negative_claims_never_become_positive_elements():
    """D6 — absence must not be restated as presence."""

    observation = build_architectural_observation(
        {"observed": [Q_NEG_ROOF], "confidence": "LOW"},
        provider="ollama", model="qwen3.8:27b", image_id="synthetic",
        source_type="other")

    positive = {entry.get("evidence_phrase")
                for entry in observation.get("architectural_elements") or []
                if entry.get("status") == "visible"}

    assert Q_NEG_ROOF not in positive


def test_downstream_can_carry_the_four_bay_arrangement():
    """§4(c) — a facade arrangement observation is representable."""

    structured = _payload(**{"observed_elements": [_claim(Q_BAY, "window")]})
    _, interpretation = _chain(structured)

    report = render_vision_report(interpretation, "fa")
    assert Q_BAY in report
    assert "four\u2011bay" in report or "four-bay" in report


def test_a_bay_count_never_invents_a_window_total():
    """D7 — four bays must not become twelve windows."""

    structured = _payload(**{"observed_elements": [_claim(Q_BAY, "window")]})
    understanding, interpretation = _chain(structured)

    candidate = next(c for c in understanding["provider_candidates"]
                     if c["text"] == Q_BAY)
    assert candidate["count"] is None

    report = render_vision_report(interpretation, "fa")
    assert "12" not in report
    assert "twelve" not in report.lower()


def test_row_count_never_overwrites_the_floor_count():
    """D7/F — a row count is an arrangement, not a storey count."""

    structured = _payload(**{"observed_elements": [_claim(Q_ROWS, "window",
                                                          count=3)]})
    _, interpretation = _chain(structured)

    observation = interpretation["architectural_observation"]

    assert observation["visible_floors"] is None
    assert observation["visible_floors_observation"]["count"] == 4


# ==========================================================
# Evidence integrity
# ==========================================================


def test_every_accepted_claim_quotes_the_source_verbatim():
    raw = _raw()
    structured = _payload(**{
        "observed_elements": [_claim(Q_BAY, "window"), _claim(Q_NEG_ROOF, "roof")],
        "openings": {"doors": [], "other_openings": [],
                     "windows": [_claim(Q_QUANTITY, "window")]},
    })
    understanding, _ = _chain(structured)

    assert understanding["provider_candidates"]
    for candidate in understanding["provider_candidates"]:
        assert candidate["source_quote"] in raw


def test_a_fabricated_quote_is_still_rejected():
    invented = "The facade is clad in polished granite with aluminium mullions"
    structured = _payload(**{"walls": [_claim(invented, "wall")]})
    understanding, _ = _chain(structured)

    texts = [c["text"] for c in understanding["provider_candidates"]]
    assert invented not in texts


# ==========================================================
# Accepted behaviour that must not regress
# ==========================================================


def test_open_through_passage_stays_open():
    """F — from the real saved payload."""

    base = json.loads(json.dumps(_record()["normalization"]["structured"]))
    _, interpretation = _chain(base)

    report = render_vision_report(interpretation, "fa")

    assert "open through" in report.lower()
    assert "فضای بسته" not in report


def test_four_storey_reading_stays_a_provider_observation():
    """G — more facts must never mean more authority."""

    base = json.loads(json.dumps(_record()["normalization"]["structured"]))
    _, interpretation = _chain(base)

    observation = interpretation["architectural_observation"]
    reading = observation["visible_floors_observation"]

    assert observation["visible_floors"] is None
    assert reading["count"] == 4
    assert reading["trust_tier"] == "PROVIDER_OBSERVATION"
    assert reading["verification"] == "UNVERIFIED"
    assert reading["authoritative"] is False


def test_no_fabricated_material_is_introduced():
    """H — brick only; glass is never inferred from 'window'."""

    base = json.loads(json.dumps(_record()["normalization"]["structured"]))
    _, interpretation = _chain(base)

    materials = {material
                 for entry in interpretation["architectural_observation"]
                 .get("material_observations") or []
                 for material in (entry.get("materials") or [])}

    assert "glass" not in materials


# ==========================================================
# Route isolation (item 15)
# ==========================================================


def test_normalizer_module_does_not_reach_render_or_photometric_routes():
    """The normalizer must stay a text-to-JSON component."""

    path = os.path.join(ROOT, "core", "vision", "observation_normalizer_v1.py")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()

    for forbidden in ("photometric", "comfy", "render_runtime", "WorkflowSelector",
                      "requests", "urllib"):
        assert forbidden not in source, forbidden
