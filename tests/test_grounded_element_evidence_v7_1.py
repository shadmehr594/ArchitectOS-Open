"""GROUNDED_FACADE_EVIDENCE_END_TO_END_V7_1 — source-anchored element evidence.

The chain under test:

    SAVED MODEL OBSERVATION
      -> EXISTING observation normalization (parse_normalization)
      -> GROUNDED ELEMENT EVIDENCE (element_evidence_from_claims)
      -> EXISTING ARCHITECTURAL INTERPRETATION (interpret_architectural_vision)
      -> CHAT/API RESPONSE (ChatArchitect._vision_block)

Every test here starts from the **real saved V7 observation text**
(`runs/architectural_element_vision_v7/21_raw_observation.txt`). None starts
from a hand-authored `element_evidence` dictionary.

NORMALIZER_SUBSTITUTE
=====================
The normalizer's structured output is normally produced by a text LLM. This task
is CPU-only and forbids Ollama calls, so the structured input is supplied
statically — but it is **validated by the real `parse_normalization`**, which
rejects any claim whose `source_quote` is not a verbatim substring of the saved
text. So the anchoring is enforced by existing production code, not by trust.
Negative tests below prove the enforcement actually bites.

Evidence classes are deliberately distinct:
    MODEL_REPORTED          — the observer said it (NOT pixel-verified)
    MANUALLY_PIXEL_CHECKED  — a human compared it against the pixels
    UNVERIFIED              — ambiguous or unresolvable

CPU only: no Ollama, no GPU, no ComfyUI, no rendering.
"""

import hashlib
import json
from pathlib import Path

import pytest

from core.vision.architectural_observation_v1 import (
    EVIDENCE_CLASSES,
    build_architectural_observation,
    element_evidence_from_claims,
)
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)
from core.vision.image_understanding_v1 import build_understanding
from core.vision.observation_normalizer_v1 import (
    CATEGORIES,
    iter_claims,
    parse_normalization,
)

ROOT = Path(__file__).resolve().parents[1]
V7_OBS = ROOT / "runs" / "architectural_element_vision_v7" / "21_raw_observation.txt"
V6_OBS = ROOT / "runs" / "architectural_fine_detail_vision_v6" / "31_raw_observation.txt"

SOURCE = {
    "sha256": "d981742208b65d27b6243db4780d59a0b901b5c195f4d153e916555141ed866b",
    "width": 890,
    "height": 510,
    "crop_box": {"left": 440, "top": 790, "right": 1330, "bottom": 1300},
    "parent": {
        "sha256": "1b304a9f2c34819015fbc1b9a15d930f4c2d9fd011572677d648748a15c0231c",
        "width": 2000,
        "height": 1682,
    },
}

#: Verbatim spans of the saved V7 text. The em-dash multiplication sign and the
#: non-breaking hyphens are part of the source, so they are copied exactly.
Q_COLUMNS = ("Fluted columns with carved capitals flanking the central opening "
             "\u2014 \u00d72")
Q_LANTERNS = "Wall\u2011mounted lanterns (black, lit) \u2014 \u00d74"
Q_PLANTERS = ("Half\u2011bowl (scalloped) planters with purple flowers "
              "\u2014 \u00d73")
Q_BALUSTRADE = "White balustrade with turned balusters and a newel block"
Q_MATERIAL = "Light stone wall surface with horizontal ashlar joint lines"
Q_BAND = "Carved relief band along the very top (frieze / cornice)"


def _saved_text():
    return V7_OBS.read_text(encoding="utf-8")


def _empty_structured():
    value = {"drawing_type": None}
    for category in CATEGORIES:
        value[category] = []
    value["openings"] = {"doors": [], "windows": [], "other_openings": []}
    return value


def _claim(text, quote, kind, certainty="ASSERTED", count=None):
    return {"text": text, "source_quote": quote, "kind": kind,
            "certainty": certainty, "count": count}


def _canonical_claims():
    return [
        _claim("Fluted columns with carved capitals",
               Q_COLUMNS, "column", count=2),
        _claim("Wall\u2011mounted lanterns (black, lit)",
               Q_LANTERNS, "light_fixture", count=4),
        _claim("Half\u2011bowl (scalloped) planters with purple flowers",
               Q_PLANTERS, "planter", count=3),
        _claim("White balustrade with turned balusters", Q_BALUSTRADE, "railing"),
        _claim("Light stone wall surface", Q_MATERIAL, "wall"),
        _claim("Carved relief band", Q_BAND, "cornice"),
    ]


def _run_chain(claims, source_text=None, category="observed_elements"):
    """SAVED TEXT -> real normalizer -> anchored element evidence."""
    raw = source_text if source_text is not None else _saved_text()
    structured = _empty_structured()
    structured[category] = list(claims)
    diagnostics = {}
    normalized = parse_normalization(json.dumps(structured), raw,
                                     diagnostics=diagnostics)
    pairs = [(cat, dict(claim, claim_category=cat))
             for cat, claim in iter_claims(normalized)]
    observation = build_architectural_observation(
        {"observed": ["arched window"], "image_type": "facade"}, image_id="v7")
    return element_evidence_from_claims(
        observation, [claim for _, claim in pairs], raw, source_image=SOURCE)


# ==========================================================
# THE MAIN ACCEPTANCE TEST — begins with real saved data
# ==========================================================

def test_saved_observation_becomes_source_anchored_element_evidence():
    raw = _saved_text()
    anchored, report = _run_chain(_canonical_claims())

    assert report["contract"] == "SourceAnchoredElementEvidenceV1"
    assert report["source_text_sha256"] == hashlib.sha256(
        raw.encode("utf-8")).hexdigest()
    assert report["accepted_count"] == 6
    assert report["rejected_count"] == 0

    elements = anchored["element_evidence"]["elements"]
    assert len(elements) == 6

    # Every carried record points back at a verbatim span of the saved text.
    for entry in elements:
        assert entry["source_quote"]
        assert entry["source_quote"] in raw

    by_kind = {tuple(entry["kind"]): entry for entry in elements}

    columns = by_kind[("column",)]
    assert columns["element"] == "Fluted columns with carved capitals"
    assert columns["evidence_class"] == "MODEL_REPORTED"
    assert columns["model_reported_count"] == 2
    assert columns["position"] is None
    assert columns["confidence"] is None


def test_crop_and_parent_provenance_survive_the_whole_chain():
    anchored, _ = _run_chain(_canonical_claims())

    source = anchored["element_evidence"]["source_image"]

    assert source["sha256"] == SOURCE["sha256"]
    assert source["crop_box"] == SOURCE["crop_box"]
    assert source["parent"]["sha256"] == SOURCE["parent"]["sha256"]


def test_model_reported_evidence_is_never_labelled_as_pixel_verified():
    anchored, _ = _run_chain(_canonical_claims())

    for entry in anchored["element_evidence"]["elements"]:
        assert entry["evidence_class"] == "MODEL_REPORTED"
        assert entry["confidence"] is None


# ==========================================================
# NEGATIVE TESTS — the anchoring must actually bite
# ==========================================================

def test_a_fabricated_source_quote_is_rejected():
    """A quote that is not in the saved text must die, at whichever layer sees it.

    In practice the EXISTING normalizer catches it first (it resolves every
    source_quote against the source text), so it never reaches the adapter.
    The invariant under test is that it cannot survive the chain at all.
    """

    raw = _saved_text()
    structured = _empty_structured()
    structured["observed_elements"] = [
        _claim("Corinthian capital", "a Corinthian capital crowns the pier",
               "capital"),
    ]
    diagnostics = {}
    normalized = parse_normalization(json.dumps(structured), raw,
                                     diagnostics=diagnostics)

    # The existing normalizer rejected it before any V7.1 code ran.
    assert diagnostics["rejected_claim_count"] == 1
    assert diagnostics["source_resolution_failures"][0]["field"] == "source_quote"
    assert normalized["observed_elements"] == []

    claims = [dict(claim, claim_category=cat)
              for cat, claim in iter_claims(normalized)]

    observation = build_architectural_observation(
        {"observed": [], "image_type": "facade"}, image_id="v7")
    anchored, report = element_evidence_from_claims(
        observation, claims, raw, source_image=SOURCE)

    # Nothing invented reaches the observation.
    assert report["accepted_count"] == 0
    assert anchored["element_evidence"]["elements"] == []


def test_the_adapter_also_rejects_an_unanchored_quote_that_bypasses_the_normalizer():
    """Defence in depth: a claim injected past the normalizer still dies here."""

    raw = _saved_text()
    observation = build_architectural_observation(
        {"observed": [], "image_type": "facade"}, image_id="v7")

    anchored, report = element_evidence_from_claims(
        observation,
        [_claim("Corinthian capital", "a Corinthian capital crowns the pier",
                "capital")],
        raw,
        source_image=SOURCE,
    )

    assert report["accepted_count"] == 0
    assert report["rejected_count"] == 1
    assert report["rejected"][0]["reason"] == "source_quote_not_found_in_saved_text"
    assert anchored["element_evidence"]["elements"] == []


def test_a_kind_not_supported_by_its_own_quote_is_rejected():
    """An invented classification cannot ride a real quote."""

    raw = _saved_text()
    structured = _empty_structured()
    structured["observed_elements"] = [
        _claim("White balustrade", Q_BALUSTRADE, "pediment"),
    ]
    normalized = parse_normalization(json.dumps(structured), raw)
    claims = [dict(claim, claim_category=cat)
              for cat, claim in iter_claims(normalized)]

    observation = build_architectural_observation(
        {"observed": [], "image_type": "facade"}, image_id="v7")
    anchored, report = element_evidence_from_claims(
        observation, claims, raw, source_image=SOURCE)

    assert report["accepted_count"] == 0
    assert report["rejected"][0]["reason"] == \
        "declared_kind_not_supported_by_its_quote"
    assert report["rejected"][0]["supported_by_quote"] == ["railing"]


def test_a_count_absent_from_the_quote_is_dropped_not_trusted():
    raw = _saved_text()
    structured = _empty_structured()
    structured["observed_elements"] = [
        _claim("Wall\u2011mounted lanterns (black, lit)", Q_LANTERNS,
               "light_fixture", count=9),
    ]
    normalized = parse_normalization(json.dumps(structured), raw)
    claims = [dict(claim, claim_category=cat)
              for cat, claim in iter_claims(normalized)]

    observation = build_architectural_observation(
        {"observed": [], "image_type": "facade"}, image_id="v7")
    anchored, _ = element_evidence_from_claims(
        observation, claims, raw, source_image=SOURCE)

    assert anchored["element_evidence"]["elements"][0]["model_reported_count"] \
        is None


def test_an_ambiguous_claim_stays_unverified_and_keeps_its_hedge():
    raw = _saved_text()
    structured = _empty_structured()
    structured["observed_elements"] = [
        _claim("White balustrade", Q_BALUSTRADE, "railing", certainty="AMBIGUOUS"),
    ]
    normalized = parse_normalization(json.dumps(structured), raw)
    claims = [dict(claim, claim_category=cat)
              for cat, claim in iter_claims(normalized)]

    observation = build_architectural_observation(
        {"observed": [], "image_type": "facade"}, image_id="v7")
    anchored, _ = element_evidence_from_claims(
        observation, claims, raw, source_image=SOURCE)

    entry = anchored["element_evidence"]["elements"][0]

    assert entry["evidence_class"] == "UNVERIFIED"
    assert entry["uncertainty"].startswith("observer hedged:")
    assert entry["confidence"] is None


def test_a_claim_text_outside_its_own_quote_is_rejected():
    raw = _saved_text()
    structured = _empty_structured()
    structured["observed_elements"] = [
        _claim("Corinthian order", Q_BALUSTRADE, "railing"),
    ]
    normalized = parse_normalization(json.dumps(structured), raw)
    claims = [dict(claim, claim_category=cat)
              for cat, claim in iter_claims(normalized)]

    observation = build_architectural_observation(
        {"observed": [], "image_type": "facade"}, image_id="v7")
    anchored, report = element_evidence_from_claims(
        observation, claims, raw, source_image=SOURCE)

    assert report["accepted_count"] == 0
    assert anchored["element_evidence"]["elements"] == []


# ==========================================================
# TASK C — the known defects are recorded, never silently fixed
# ==========================================================

def test_the_lantern_count_is_carried_as_model_reported_not_verified():
    """The model said four; five are visible. Four must not become a fact."""

    anchored, _ = _run_chain(_canonical_claims())
    lantern = next(entry for entry in anchored["element_evidence"]["elements"]
                   if entry["kind"] == ["light_fixture"])

    assert lantern["model_reported_count"] == 4
    assert lantern["evidence_class"] == "MODEL_REPORTED"
    # No verified count field exists, and none is fabricated.
    assert "count" not in lantern
    assert "verified_count" not in lantern


def test_manual_pixel_check_is_a_separate_class_from_the_model_report():
    """Five visible fixtures is a HUMAN pixel check, not an automatic verifier."""

    assert "MANUALLY_PIXEL_CHECKED" in EVIDENCE_CLASSES
    assert "MODEL_REPORTED" in EVIDENCE_CLASSES
    assert "UNVERIFIED" in EVIDENCE_CLASSES


def test_both_saved_observations_are_kept_as_distinct_records():
    """V6 described the mid-height band; V7 did not. Neither is merged away."""

    v7 = _saved_text()
    v6 = V6_OBS.read_text(encoding="utf-8")

    assert "horizontal stone shelf" in v6.lower()
    # V7 mentions the planters at that height but never the band itself.
    assert "horizontal stone shelf" not in v7.lower()

    # The two texts are different records and stay that way.
    assert hashlib.sha256(v7.encode()).hexdigest() != hashlib.sha256(
        v6.encode()).hexdigest()


# ==========================================================
# TASK D — the chat/API handoff
# ==========================================================

def test_understanding_preserves_element_evidence():
    anchored, _ = _run_chain(_canonical_claims())

    understanding = build_understanding(anchored, provider="ollama",
                                        model="qwen3.8:27b", image_id="v7")

    assert understanding["element_evidence"]["elements"]
    assert len(understanding["element_evidence"]["elements"]) == 6


def test_understanding_does_not_fabricate_an_empty_collection():
    observation = build_architectural_observation(
        {"observed": ["arched window"], "image_type": "facade"}, image_id="v7")

    understanding = build_understanding(observation, provider="ollama",
                                        model="qwen3.8:27b", image_id="v7")

    assert understanding["element_evidence"] is None


def test_interpretation_output_carries_the_anchored_evidence():
    anchored, _ = _run_chain(_canonical_claims())
    understanding = build_understanding(anchored, provider="ollama",
                                        model="qwen3.8:27b", image_id="v7")

    result = interpret_architectural_vision(understanding, user_text="")
    blob = json.dumps(result)

    assert "element_evidence" in blob
    assert SOURCE["sha256"] in blob
    assert "Fluted columns with carved capitals" in blob


def test_chat_vision_block_carries_the_evidence():
    from core.chat.chat_architect import ChatArchitect

    anchored, _ = _run_chain(_canonical_claims())
    understanding = build_understanding(anchored, provider="ollama",
                                        model="qwen3.8:27b", image_id="v7")

    block = ChatArchitect._vision_block(
        None, {"image_id": "v7"}, understanding, None, None, None)

    assert block["element_evidence"]["elements"]
    assert block["element_evidence"]["source_image"]["sha256"] == SOURCE["sha256"]
    # Existing keys are untouched.
    assert block["contract"] == "ImageTurnV1"
    assert block["image_id"] == "v7"


def test_chat_vision_block_is_unchanged_without_element_evidence():
    from core.chat.chat_architect import ChatArchitect

    observation = build_architectural_observation(
        {"observed": ["arched window"], "image_type": "facade"}, image_id="plain")
    understanding = build_understanding(observation, provider="ollama",
                                        model="qwen3.8:27b", image_id="plain")

    block = ChatArchitect._vision_block(
        None, {"image_id": "plain"}, understanding, None, None, None)

    assert "element_evidence" not in block
    assert block["contract"] == "ImageTurnV1"


# ==========================================================
# GUARD — no promotion, no legacy change
# ==========================================================

def test_no_floor_count_or_species_is_promoted_from_element_evidence():
    anchored, _ = _run_chain(_canonical_claims())
    understanding = build_understanding(anchored, provider="ollama",
                                        model="qwen3.8:27b", image_id="v7")

    blob = json.dumps(understanding["element_evidence"])

    for forbidden in ('"species"', '"load_bearing"', '"structural_function"',
                      '"visible_floor_count"', '"floor_count"'):
        assert forbidden not in blob


def test_legacy_architectural_elements_entries_are_unchanged():
    anchored, _ = _run_chain(_canonical_claims())

    for entry in anchored["architectural_elements"]:
        assert set(entry) == {"evidence_phrase", "status", "confidence", "kind"}
