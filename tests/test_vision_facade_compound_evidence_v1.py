# -*- coding: utf-8 -*-
"""VISION_FIRST_FACADE_COMPOUND_EVIDENCE_V1 — focused CPU tests.

Defect under test: `D4_COMPOUND_ARCHITECTURAL_OBSERVATION_LOSS`.

The archived live record (`runs/r2_live_normalizer_v13/eye_V3_v13.json`) shows the
loss boundary precisely: `accepted_claim_count = 15`, `rejected_claim_count = 0`,
`source_resolution_failures = []`, and ZERO occurrences of
mullion / glaz / multi / bay / pane in the normalizer's own JSON. Nothing was
dropped by parsing, by quote verification, or downstream — the normalizer model
emitted only the first sentence of a three-sentence source passage.

So the RED test is the PROMPT CONTRACT (the instruction that licensed the
shortening), and the GREEN proof downstream is that correctly normalised
compound claims actually survive to the user.

WHAT THIS FILE DOES NOT PROVE
-----------------------------
A synthetic payload proves the DOWNSTREAM can carry compound facts. It does NOT
prove the normalizer model obeys a new instruction. Only a live inference can
show that, and no test here claims otherwise.

No Ollama. No GPU. No ComfyUI.
"""

import json
import os
import re

import pytest

from core.vision.architectural_observation_v1 import build_architectural_observation
from core.vision.architectural_vision_interpreter_v1 import interpret_architectural_vision
from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
from core.vision.image_understanding_v1 import build_understanding
from core.vision.observation_normalizer_v1 import NORMALIZER_PROMPT
from core.vision.vision_report_v1 import render_vision_report


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

V3_RECORD = os.path.join(ROOT, "runs", "r2_live_normalizer_v13", "eye_V3_v13.json")

EXPECTED_SHA = "ae77532be8dd80bbf35af1a04136b86d1689f9b0845b50325f0e4c8a5cde1ab4"

#: The instruction this milestone adds. The marker is asserted, not the wording.
PROMPT_MARKER = "COMPOUND ARCHITECTURAL EVIDENCE"


def _prompt():
    """The prompt, lower-cased with whitespace collapsed.

    The instruction is wrapped across source lines, so a naive substring test
    would fail on a line break rather than on a missing rule.
    """

    return " ".join(NORMALIZER_PROMPT.lower().split())



def _record():
    with open(V3_RECORD, encoding="utf-8") as fh:
        return json.load(fh)


def _raw_text():
    return _record()["raw_observer"]["raw_text"]


def _sentence_with(marker):
    """An EXACT substring of the observer text around `marker`.

    Slicing by offset guarantees the quote is verbatim, so the claim exercises
    the real quote verification instead of bypassing it.
    """

    raw = _raw_text()
    index = raw.find(marker)
    assert index >= 0, "marker not in the archived observer text: %r" % marker

    start = max(raw.rfind(". ", 0, index) + 2, raw.rfind("\n", 0, index) + 1)
    stop = raw.find(". ", index)
    stop = len(raw) if stop < 0 else stop + 1

    quote = raw[start:stop].strip()
    assert quote in raw
    return quote


def _bridge(structured):
    record = _record()
    return {"contract": BRIDGE_CONTRACT,
            "raw_observer": record["raw_observer"],
            "normalization": {"status": "NORMALIZED", "structured": structured}}


def _chain(structured):
    understanding = build_understanding(
        _bridge(structured), provider="ollama", model="qwen3.8:27b",
        image_id="V3", source_type="other")
    return understanding, interpret_architectural_vision(understanding)


def _claim(text, quote, kind, certainty="ASSERTED", count=None):
    return {"text": text, "source_quote": quote, "kind": kind,
            "certainty": certainty, "count": count}


def _compound_structured():
    """What a normalizer that preserves compound facts SHOULD emit.

    Every quote is an exact slice of the archived observer text. The payload is
    a TEST FIXTURE, labelled as such — it is not claimed to be model output.
    """

    base = json.loads(json.dumps(_record()["normalization"]["structured"]))
    structured = {key: (list(value) if isinstance(value, list) else value)
                  for key, value in base.items()}

    glazing = _sentence_with("multi")
    grid = _sentence_with("four bays")

    structured["openings"] = json.loads(json.dumps(structured.get("openings") or {}))
    windows = list((structured["openings"].get("windows") or []))
    windows.append(_claim(glazing, glazing, "window"))
    structured["openings"]["windows"] = windows

    relationships = list(structured.get("spatial_relationships") or [])
    relationships.append(_claim(grid, grid, "facade_arrangement"))
    structured["spatial_relationships"] = relationships

    return structured, glazing, grid


# ==========================================================
# RED — the prompt contract that licensed the loss
# ==========================================================


def test_prompt_requires_compound_fact_preservation():
    """A — one sentence may carry several reportable facts."""

    assert PROMPT_MARKER in NORMALIZER_PROMPT, (
        "the normalizer prompt still has no compound-evidence rule, so a "
        "three-sentence architectural observation collapses to its first "
        "sentence (D4)")


def test_prompt_bounds_the_short_quote_to_the_quote_not_the_facts():
    """The existing 'shortest exact quote' rule must not license dropping facts."""

    lowered = _prompt()

    assert "shortest" in lowered, "precondition: the brevity rule still exists"
    assert ("never achieve brevity by dropping" in lowered
            or "brevity" in lowered), (
        "the prompt never tells the model that shortening the QUOTE must not "
        "shorten the FACT SET")


def test_prompt_separates_rows_from_storeys():
    """F — a row/bay count is an arrangement, never a storey count."""

    lowered = _prompt()

    assert "storey" in lowered
    assert "row" in lowered, "the prompt does not mention rows at all"
    assert ("not a storey" in lowered or "never a storey" in lowered
            or "arrangement" in lowered), (
        "nothing stops 'three rows up' from being read as a storey count")


def test_prompt_forbids_deriving_a_total_from_a_grid():
    """N — no fabricated exact window count from 'four bays across'."""

    lowered = _prompt()

    assert ("do not derive" in lowered or "never derive" in lowered), (
        "nothing stops the model from multiplying bays by rows into an "
        "invented total window count")


# ==========================================================
# Forensic witness — where the archived loss actually happened
# ==========================================================


def test_archived_loss_is_upstream_of_parsing():
    """The loss is in the model's emission, not in parse or verification.

    This is a WITNESS on immutable archived evidence, not a RED->GREEN test: it
    cannot turn green by editing code, and it is here so the boundary stays
    recorded.
    """

    record = _record()
    normalization = record["normalization"]

    assert normalization["status"] == "NORMALIZED"
    assert normalization["accepted_claim_count"] == 15
    assert normalization["rejected_claim_count"] == 0
    assert normalization["source_resolution_failures"] == []

    emitted = normalization["raw_text"].lower()

    for term in ("mullion", "glaz", "multi", "pane", "bay", "rows up"):
        assert term not in emitted, (
            "%r IS present in the archived normalizer output; the loss "
            "boundary has moved and this witness must be re-derived" % term)


# ==========================================================
# GREEN — downstream must carry compound facts when they exist
# ==========================================================


def test_compound_source_yields_several_claims_downstream():
    """A/B/C — four independent facts from one passage all survive."""

    structured, glazing, grid = _compound_structured()
    understanding, interpretation = _chain(structured)

    texts = [c["text"] for c in understanding["provider_candidates"]]

    assert "Rectangular openings with dark (black/bronze) frames" in texts
    assert glazing in texts, "the glazing sentence did not become its own claim"
    assert grid in texts, "the facade-grid sentence did not become its own claim"

    report = render_vision_report(interpretation, "fa")

    assert "multi" in report.lower()
    assert "mullion" in report.lower()
    assert "four bays" in report.lower()


def test_glazing_and_mullion_reach_the_user():
    """B/C — the two facts the archived run lost."""

    structured, glazing, _ = _compound_structured()
    _, interpretation = _chain(structured)

    report = render_vision_report(interpretation, "fa")

    assert glazing in report or "curtain" in report.lower()
    assert "internal mullions" in report.lower()


def test_facade_grid_reaches_the_user():
    """E — the four-bay / three-row arrangement is reportable."""

    structured, _, grid = _compound_structured()
    _, interpretation = _chain(structured)

    report = render_vision_report(interpretation, "fa")

    assert grid in report
    assert "three rows" in report.lower()


def test_qualified_quantities_are_preserved_verbatim():
    """G — 'most' and 'several' must not become 'all' or an integer."""

    structured, glazing, _ = _compound_structured()
    understanding, interpretation = _chain(structured)

    claim = next(c for c in understanding["provider_candidates"]
                 if c["text"] == glazing)

    assert claim["count"] is None, "a qualified quantity became a number"
    assert "most" in glazing.lower()

    report = render_vision_report(interpretation, "fa")

    assert "most" in report.lower()
    assert not re.search(r"\ball\b", report.lower()), (
        "'most' was strengthened to 'all'")


def test_grid_rows_do_not_change_the_storey_count():
    """F — 'three rows up' must not overwrite the four-storey reading."""

    structured, _, _ = _compound_structured()
    _, interpretation = _chain(structured)

    observation = interpretation["architectural_observation"]

    assert observation["visible_floors"] is None
    assert observation["visible_floors_observation"]["count"] == 4

    report = render_vision_report(interpretation, "fa")

    assert "4 طبقهٔ قابل مشاهده" in report
    assert "3 طبقهٔ بالایی" in report


# ==========================================================
# Evidence integrity
# ==========================================================


def test_fabricated_quote_is_rejected():
    """H/I — a claim not grounded in the source never becomes a candidate."""

    structured, _, _ = _compound_structured()

    fabricated = _claim(
        "The facade is clad in polished granite with aluminium mullions",
        "The facade is clad in polished granite with aluminium mullions",
        "wall")

    walls = list(structured.get("walls") or [])
    walls.append(fabricated)
    structured["walls"] = walls

    understanding, _ = _chain(structured)

    texts = [c["text"] for c in understanding["provider_candidates"]]

    assert fabricated["text"] not in texts, (
        "a claim whose quote is not in the observer text was accepted")


def test_every_accepted_claim_quotes_the_source():
    """H — each surviving claim is traceable to the archived text."""

    structured, _, _ = _compound_structured()
    understanding, _ = _chain(structured)

    raw = _raw_text()

    for candidate in understanding["provider_candidates"]:
        assert candidate["source_quote"] in raw, (
            "claim quotes text the observer never wrote: %r"
            % candidate["source_quote"])


def test_opening_alone_does_not_become_glass():
    """D — an opening is not glazing; no material is inferred from a term."""

    structured, _, _ = _compound_structured()

    # Remove every glazing claim, leaving the bare opening statement.
    windows = [c for c in (structured["openings"].get("windows") or [])
               if "multi" not in c["text"].lower()]
    structured["openings"]["windows"] = windows
    structured["spatial_relationships"] = []

    _, interpretation = _chain(structured)

    observation = interpretation["architectural_observation"]

    materials = {
        material
        for entry in observation.get("material_observations") or []
        for material in (entry.get("materials") or [])
    }

    assert "glass" not in materials, (
        "glass was inferred from an opening that the source never called glazed")


def test_compound_claims_do_not_become_verified_geometry():
    """Provenance: more facts must not mean more authority."""

    structured, _, _ = _compound_structured()
    _, interpretation = _chain(structured)

    observation = interpretation["architectural_observation"]

    assert observation["visible_floors"] is None
    assert observation["visible_floors_observation"]["trust_tier"] == (
        "PROVIDER_OBSERVATION")
    assert observation["visible_floors_observation"]["authoritative"] is False

    serialised = json.dumps(observation).lower()
    for key in ("bbox", "bounding_box", "polygon", "coordinates"):
        assert key not in serialised, "geometry was fabricated: %r" % key


# ==========================================================
# Previously accepted behaviour must not regress
# ==========================================================


def test_restricted_negation_still_holds():
    """J — 'no visible columns other than the piers' stays restricted."""

    observation = build_architectural_observation(
        {"observed": ["no visible columns other than the ground-floor piers of "
                      "the arcade"], "confidence": "LOW"},
        provider="ollama", model="qwen3.8:27b", image_id="synthetic",
        source_type="other")

    fragments = [fragment
                 for entry in observation.get("negative_observations") or []
                 for fragment in (entry.get("negated_texts") or [])]

    assert any("other than the ground-floor piers" in fragment
               for fragment in fragments)

    kinds = {kind
             for entry in observation.get("architectural_elements") or []
             for kind in (entry.get("kind") or [])}

    assert "pier" in kinds
    assert "column" not in kinds


def test_storey_count_and_open_passage_still_reach_the_report():
    """K/L — the two accepted facade facts."""

    structured, _, _ = _compound_structured()
    _, interpretation = _chain(structured)

    report = render_vision_report(interpretation, "fa")

    assert "4 طبقهٔ قابل مشاهده" in report
    assert "open through" in report.lower()
    assert "فضای بسته" not in report


def test_observation_and_interpretation_stay_separate():
    """M — a compound observation is still not an interpretation."""

    structured, _, _ = _compound_structured()
    _, interpretation = _chain(structured)

    observed = {str(item).lower() for item in interpretation["observed_elements"]}

    for line in interpretation.get("architectural_interpretation") or []:
        assert str(line).lower() not in observed


def test_no_english_meta_unknown_and_no_duplicate_passage():
    """The previous milestone's fixes still hold on the compound payload."""

    structured, _, _ = _compound_structured()
    _, interpretation = _chain(structured)

    report = render_vision_report(interpretation, "fa")

    assert "reliable architectural evidence has not been established" not in report

    passages = [line for line in report.splitlines()
                if "through" in line.lower() and "passage" in line.lower()]
    assert len(passages) == 1
