"""LIVE_ELEMENT_NORMALIZATION_V7_2 — live normalizer output + position schema.

RED tests written before the production change they justify.

The demonstrated gap
====================

A real live normalization of the saved V7 observation
(`runs/architectural_live_element_normalization_v7_2/20_live_normalization.json`,
one call, status NORMALIZED, 30 accepted claims) emits element claims whose
`kind` is a **normalizer meta-kind** rather than an architectural label:

    interpretation   (4 claims)  e.g. "frieze/cornice", "Ionic/Corinthian",
                                 "pilaster vs. column"
    unknown          (9 claims)  e.g. "Capital order",
                                 "free‑standing column or a flat pilaster"
    pier             (6 claims)  an architectural kind absent from the
                                 vocabulary
    fixture          (2 claims)  e.g. "chandelier"

The V7.1 adapter rejected ALL 21 of them, because a declared kind that is not a
vocabulary label failed the support test. The quotes for many of those claims DO
support architectural kinds (`['cornice','frieze']`, `['column','pilaster']`,
`['capital']`), so the rejection discarded exactly the ambiguity evidence this
project is required to keep:

    "Maintain uncertainty for: ... pilaster vs engaged column,
     exact capital order ..."

That is the gap: an unsupported *declared label* is not the same as an
unsupported *classification*. The fix must fall back to the kinds the quote
itself supports, and must still reject a claim whose quote supports no
architectural kind at all.

Also pinned here: the position schema is CLOSED (see
`test_the_normalizer_schema_requires_every_property`), which is why
POSITION_TRANSPORT is blocked rather than extended.

CPU only. These tests read saved evidence; they never call a model.
"""

import json
from pathlib import Path

import pytest

from core.vision.architectural_observation_v1 import (
    build_architectural_observation,
    element_evidence_from_claims,
)
from core.vision.observation_normalizer_v1 import (
    CLAIM_SCHEMA,
    STRUCTURED_SCHEMA,
    iter_claims,
    parse_normalization,
)

ROOT = Path(__file__).resolve().parents[1]
V7_2 = ROOT / "runs" / "architectural_live_element_normalization_v7_2"
LIVE = V7_2 / "20_live_normalization.json"
LIVE_STRUCTURED = V7_2 / "21_live_structured.json"
V7_TEXT = ROOT / "runs" / "architectural_element_vision_v7" / "21_raw_observation.txt"

SOURCE_IMAGE = {
    "sha256": "d981742208b65d27b6243db4780d59a0b901b5c195f4d153e916555141ed866b",
    "width": 890, "height": 510,
    "crop_box": {"left": 440, "top": 790, "right": 1330, "bottom": 1300},
    "parent": {"sha256": "1b304a9f2c34819015fbc1b9a15d930f4c2d9fd011572677d648748a15c0231c",
               "width": 2000, "height": 1682},
}


def _source_text():
    return V7_TEXT.read_text(encoding="utf-8")


def _live_claims():
    structured = json.loads(LIVE_STRUCTURED.read_text(encoding="utf-8"))
    return [dict(claim, claim_category=cat)
            for cat, claim in iter_claims(structured)]


def _anchor(claims, text=None):
    observation = build_architectural_observation(
        {"observed": [], "image_type": "facade"}, image_id="v7-live")
    return element_evidence_from_claims(
        observation, claims, text if text is not None else _source_text(),
        source_image=SOURCE_IMAGE)


# ==========================================================
# RED — meta-kinds must fall back to quote-supported kinds
# ==========================================================

def test_a_meta_kind_falls_back_to_the_kinds_its_quote_supports():
    """Real live claim: kind is the meta-kind `interpretation`."""

    claim = {
        "text": "frieze/cornice",
        "source_quote": 'calling it a "frieze/cornice" is interpretation from convention.',
        "kind": "interpretation",
        "certainty": "AMBIGUOUS",
        "count": None,
        "claim_category": "interpretations",
    }

    anchored, report = _anchor([claim])

    assert report["accepted_count"] == 1
    entry = anchored["element_evidence"]["elements"][0]
    assert set(entry["kind"]) == {"cornice", "frieze"}
    assert entry["evidence_class"] == "UNVERIFIED"
    assert entry["declared_kind"] == "interpretation"


def test_an_unresolved_pilaster_column_claim_keeps_both_kinds_and_stays_unverified():
    """The exact ambiguity the task requires us to maintain."""

    claim = {
        "text": "pilaster vs. column",
        "source_quote": '"pilaster vs. column" is interpretive (see ambiguity).',
        "kind": "interpretation",
        "certainty": "AMBIGUOUS",
        "count": None,
        "claim_category": "interpretations",
    }

    anchored, report = _anchor([claim])

    assert report["accepted_count"] == 1
    entry = anchored["element_evidence"]["elements"][0]
    assert set(entry["kind"]) == {"column", "pilaster"}
    assert entry["evidence_class"] == "UNVERIFIED"
    assert entry["uncertainty"]


def test_an_unknown_capital_order_claim_is_carried_as_unverified():
    claim = {
        "text": "Capital order",
        "source_quote": "Capital order is indeterminate from this resolution",
        "kind": "unknown",
        "certainty": "UNKNOWN",
        "count": None,
        "claim_category": "unknowns",
    }

    anchored, report = _anchor([claim])

    assert report["accepted_count"] == 1
    entry = anchored["element_evidence"]["elements"][0]
    assert "capital" in entry["kind"]
    assert entry["evidence_class"] == "UNVERIFIED"


def test_a_claim_whose_quote_supports_no_architectural_kind_is_still_rejected():
    """Fallback must not become invention. Real live claim: the lantern count."""

    claim = {
        "text": "exact count of fixtures on the left",
        "source_quote": "exact count of fixtures on the left is slightly unclear.",
        "kind": "unknown",
        "certainty": "UNKNOWN",
        "count": None,
        "claim_category": "unknowns",
    }

    anchored, report = _anchor([claim])

    assert report["accepted_count"] == 0
    assert report["rejected_count"] == 1
    assert report["rejected"][0]["reason"] == \
        "no_architectural_kind_supported_by_quote"
    assert anchored["element_evidence"]["elements"] == []


# ==========================================================
# ACCEPTANCE — the REAL saved live output
# ==========================================================

def test_the_saved_live_normalization_yields_anchored_element_evidence():
    """Begins with the real saved live normalizer output, not a hand-authored list."""

    record = json.loads(LIVE.read_text(encoding="utf-8"))
    assert record["normalizer_result"]["status"] == "NORMALIZED"
    assert record["inference_budget"]["text_normalizer_calls_used"] == 1

    anchored, report = _anchor(_live_claims())

    # A meaningful share of the live claims must survive anchoring.
    assert report["accepted_count"] >= 15
    for entry in anchored["element_evidence"]["elements"]:
        assert entry["source_quote"] in _source_text()
        assert entry["kind"]
        assert entry["evidence_class"] in ("MODEL_REPORTED", "UNVERIFIED")


def test_the_live_ambiguities_survive_into_element_evidence():
    anchored, _ = _anchor(_live_claims())

    kinds = [set(entry["kind"]) for entry in
             anchored["element_evidence"]["elements"]]

    # "pilaster vs column" and "capital order" must be represented, unresolved.
    assert any({"column", "pilaster"} <= k for k in kinds)
    assert any("capital" in k for k in kinds)

    unresolved = [entry for entry in anchored["element_evidence"]["elements"]
                  if entry["evidence_class"] == "UNVERIFIED"]
    assert unresolved


def test_no_live_claim_becomes_pixel_verified():
    anchored, _ = _anchor(_live_claims())

    for entry in anchored["element_evidence"]["elements"]:
        assert entry["evidence_class"] != "OBSERVED"
        assert entry["confidence"] is None


# ==========================================================
# POSITION — the schema is closed, so positions cannot travel
# ==========================================================

def test_the_normalizer_schema_requires_every_property():
    """Every object in the schema requires exactly its declared properties.

    This is the invariant that blocks an optional coordinate field: an optional
    property would be a contract break, not a compatible extension.
    """

    def walk(node):
        kind = node.get("type")
        if kind == "array":
            walk(node["items"])
        if kind in ("object", ["object", "null"]):
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
            for child in node["properties"].values():
                walk(child)

    walk(STRUCTURED_SCHEMA)


def test_a_claim_carrying_a_coordinate_is_rejected_by_the_existing_schema():
    """Proof that positions cannot be smuggled into a claim."""

    text = "Hanging chandelier in the central arch"
    payload = {
        "drawing_type": None,
        **{category: [] for category in
           __import__("core.vision.observation_normalizer_v1", fromlist=["CATEGORIES"]).CATEGORIES},
        "openings": {"doors": [], "windows": [], "other_openings": []},
    }
    payload["observed_elements"] = [{
        "text": "chandelier",
        "source_quote": "Hanging chandelier",
        "kind": "fixture",
        "certainty": "ASSERTED",
        "count": None,
        "position": {"x": [0.3, 0.5], "y": [0.0, 0.2]},
    }]

    with pytest.raises(ValueError):
        parse_normalization(json.dumps(payload), text)


def test_element_evidence_produced_from_normalization_carries_no_position():
    anchored, _ = _anchor(_live_claims())

    for entry in anchored["element_evidence"]["elements"]:
        assert entry["position"] is None


# ==========================================================
# TASK D — the real application response
# ==========================================================

def _recorded_bridge():
    """A recorded-provider payload built from the SAVED live normalizer output."""

    from core.vision.general_visual_observer_v1 import (
        CONTRACT as BRIDGE_CONTRACT,
        raw_observation,
    )

    text = _source_text()
    structured = json.loads(LIVE_STRUCTURED.read_text(encoding="utf-8"))
    raw = raw_observation(
        provider="ollama", model="qwen3.8:27b",
        backend="http://127.0.0.1:11434", thinking_mode=False,
        body={"response": text, "done": True, "done_reason": "stop"},
    )
    raw["diagnostics"] = {
        "original_source_sha256": SOURCE_IMAGE["sha256"],
        "observer_input_width": 890,
        "observer_input_height": 510,
    }
    return {"contract": BRIDGE_CONTRACT, "raw_observer": raw,
            "normalization": {"status": "NORMALIZED", "structured": structured}}


class _RecordedProvider:
    """Stands in for the vision provider; never contacts a model."""

    name = "ollama"
    model = "qwen3.8:27b"
    endpoint = "recorded"

    def is_available(self):
        return True

    def analyze(self, asset):
        return _recorded_bridge()

    def cache_identity(self):
        return {"provider": "ollama", "model": "qwen3.8:27b", "recorded": True}


def _forbid_live_model_calls(monkeypatch):
    """Any attempt to reach a real model fails the test loudly."""

    import core.vision.vision_provider_ollama_v1 as provider_module

    def _forbidden(*args, **kwargs):
        raise AssertionError("a live model call was attempted")

    monkeypatch.setattr(provider_module.OllamaVisionProvider, "analyze", _forbidden)
    monkeypatch.setattr(provider_module.OllamaVisualObserver, "observe", _forbidden)
    monkeypatch.setattr(provider_module.OllamaTextNormalizer, "normalize", _forbidden)


def test_production_builder_produces_element_evidence_from_a_recorded_bridge():
    """The bridge path is the PRODUCTION image-analysis path, not a passthrough."""

    from core.vision.image_understanding_v1 import build_understanding

    understanding = build_understanding(
        _recorded_bridge(), provider="ollama", model="qwen3.8:27b",
        image_id="v7-live")

    block = understanding["element_evidence"]

    assert block is not None
    assert len(block["elements"]) >= 15
    assert block["source_image"]["sha256"] == SOURCE_IMAGE["sha256"]
    assert understanding["element_evidence_report"]["accepted_count"] >= 15


def test_api_chat_response_carries_element_evidence(monkeypatch):
    """Genuine Flask route; every model seam is recorded or forbidden."""

    import core.vision.image_session_v1 as session_module
    from core.llm.llm_gateway import LLMGateway
    import app as application

    _forbid_live_model_calls(monkeypatch)
    monkeypatch.setattr(session_module, "provider", lambda: _RecordedProvider())
    monkeypatch.setattr(LLMGateway, "generate",
                        lambda self, *a, **k: "recorded reply")

    import io
    from PIL import Image as _Image

    buffer = io.BytesIO()
    _Image.new("RGB", (64, 64), "white").save(buffer, format="PNG")
    buffer.seek(0)

    with _captured_stdout():
        response = application.app.test_client().post(
            "/api/chat",
            data={"text": "what do you see", "image": (buffer, "crop.png")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200

    payload = response.get_json() or {}
    vision = (payload.get("response") or {}).get("vision") or {}
    block = vision.get("element_evidence")

    assert block is not None, "the API response dropped the element evidence"
    assert block["source_image"]["sha256"] == SOURCE_IMAGE["sha256"]
    assert len(block["elements"]) >= 15
    # No floor count, species or structural function was promoted.
    import json as _json
    serialised = _json.dumps(block)
    for forbidden in ('"species"', '"load_bearing"', '"visible_floor_count"'):
        assert forbidden not in serialised


def test_a_negated_claim_never_becomes_an_element():
    """A live API probe produced element="none visible" with real kinds attached."""

    text = _source_text()
    claim = {
        "text": "No floor count has been estimated",
        "source_quote": "No floor count has been estimated",
        "kind": "wall",
        "certainty": "ASSERTED",
        "count": None,
        "claim_category": "observed_elements",
    }

    anchored, report = _anchor([claim], text)

    assert report["accepted_count"] == 0
    assert report["rejected"][0]["reason"] == "claim_states_absence"
    assert anchored["element_evidence"]["elements"] == []


def _captured_stdout():
    import contextlib
    import io as _io
    return contextlib.redirect_stdout(_io.StringIO())
