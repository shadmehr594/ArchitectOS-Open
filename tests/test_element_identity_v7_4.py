"""ARCHITECTURAL_ELEMENT_IDENTITY_AND_RELATION_V7_4.

Demonstrated defects this file reproduces and then pins
=====================================================

1. SUBJECT vs CONTEXT (Task A)
   `lanterns` carried `kind = ["wall", "light_fixture"]` because the quote says
   "mounted on the wall". The wall is the MOUNTING CONTEXT, not the subject.

2. SUBJECT vs COMPONENT (Task D)
   `pier` carried `kind = ["capital"]` because its description mentions "a plain
   projecting capital block". The capital is a COMPONENT of the pier; the pier is
   the subject.

3. UNREPRESENTABLE SUBJECTS (Task B)
   `planter` and `carved relief band` were lost because neither quote contains a
   vocabulary marker for its declared kind — although the appearance is described
   precisely enough for a NARROW interpretation.

4. CLAIM COUNT vs OBJECT COUNT (Task C)
   26 carried evidence records include repeated category claims and do not
   establish 26 physical objects.

CPU only. Reads saved evidence; no model call is possible from this file.
"""

import json
from pathlib import Path

import pytest

from core.vision.architectural_observation_v1 import (
    _appearance_kind,
    attach_element_evidence,
    build_architectural_observation,
    element_evidence_from_claims,
    recovered_claims_from_failures,
)

ROOT = Path(__file__).resolve().parents[1]
V7_2 = ROOT / "runs" / "architectural_live_element_normalization_v7_2"
LIVE = V7_2 / "20_live_normalization.json"
V7_TEXT = ROOT / "runs" / "architectural_element_vision_v7" / "21_raw_observation.txt"

CROP_SHA = "d981742208b65d27b6243db4780d59a0b901b5c195f4d153e916555141ed866b"
SOURCE_IMAGE = {
    "sha256": CROP_SHA, "width": 890, "height": 510,
    "crop_box": {"left": 440, "top": 790, "right": 1330, "bottom": 1300},
    "parent": {"sha256": "1b304a9f2c34819015fbc1b9a15d930f4c2d9fd011572677d648748a15c0231c",
               "width": 2000, "height": 1682},
}


def _source_text():
    return V7_TEXT.read_text(encoding="utf-8")


def _live():
    return json.loads(LIVE.read_text(encoding="utf-8"))


def _failures():
    return _live()["normalizer_result"]["source_resolution_failures"]


def _accepted():
    from core.vision.observation_normalizer_v1 import iter_claims
    return [dict(claim, claim_category=cat)
            for cat, claim in iter_claims(_live()["normalizer_result"]["structured"])]


def _anchor(claims, raw_claim_count=None, normalizer_accepted_count=None):
    observation = build_architectural_observation(
        {"observed": [], "image_type": "facade"}, image_id="v7-live")
    return element_evidence_from_claims(
        observation, claims, _source_text(), source_image=SOURCE_IMAGE,
        raw_claim_count=raw_claim_count,
        normalizer_accepted_count=normalizer_accepted_count)


def _by_element(anchored, label):
    return [e for e in anchored["element_evidence"]["elements"]
            if (e["element"] or "").lower() == label.lower()]


# ==========================================================
# TASK A — subject vs context
# ==========================================================

def test_a_wall_lantern_is_a_light_fixture_not_a_wall():
    recovered = recovered_claims_from_failures(_failures(), _source_text())
    lanterns = [c for c in recovered if (c.get("text") or "").lower() == "lanterns"]

    anchored, _ = _anchor(lanterns)
    entry = _by_element(anchored, "lanterns")[0]

    assert entry["kind"] == ["light_fixture"]
    assert "wall" not in entry["kind"]
    # The wall is preserved as CONTEXT, not promoted to identity.
    assert "wall" in entry["context_kinds"]
    assert entry["relations"] == [{
        "relation": "mounted_on",
        "target_kind": "wall",
        "source_quote": entry["source_quote"],
    }]


def test_context_kinds_never_replace_the_subject():
    anchored, _ = _anchor(_accepted())
    for entry in anchored["element_evidence"]["elements"]:
        assert not (set(entry["kind"]) & set(entry["context_kinds"]))


def test_a_wall_word_without_a_mounting_predicate_creates_no_relation():
    anchored, _ = _anchor(_accepted())
    wall_surface = _by_element(anchored, "background wall of pale stone")[0]

    assert "pier" in wall_surface["context_kinds"]
    assert wall_surface["relations"] == []


def test_a_relation_with_different_evidence_or_target_is_refused():
    quote = "A lantern fixture mounted on a wall."
    observation = attach_element_evidence({}, [{
        "element": "lantern fixture",
        "kind": ["light_fixture"],
        "evidence": quote,
        "source_quote": quote,
        "evidence_class": "MODEL_REPORTED",
        "relations": [
            {"relation": "mounted_on", "target_kind": "roof",
             "source_quote": quote},
            {"relation": "mounted_on", "target_kind": "wall",
             "source_quote": "fabricated relation evidence"},
        ],
    }])

    assert observation["element_evidence"]["elements"][0]["relations"] == []


# ==========================================================
# TASK D — subject vs component
# ==========================================================

def test_a_pier_is_a_pier_and_is_not_replaced_by_its_capital():
    anchored, _ = _anchor(_accepted())
    piers = _by_element(anchored, "pier")

    assert piers, "the pier claim disappeared"
    for entry in piers:
        assert entry["kind"] == ["pier"]
        assert "capital" not in entry["kind"]

    # When the quote mentions a capital, it is preserved as context, not identity.
    piers_with_capital = [e for e in piers
                          if "capital" in (e["source_quote"] or "").lower()]
    assert piers_with_capital, "no pier quote mentions a capital"
    for entry in piers_with_capital:
        assert "capital" in entry["context_kinds"]


def test_an_ambiguous_pilaster_column_claim_is_preserved():
    anchored, _ = _anchor(_accepted())
    entry = _by_element(anchored, "pilaster vs. column")[0]

    assert set(entry["kind"]) == {"column", "pilaster"}
    assert entry["evidence_class"] == "UNVERIFIED"


# ==========================================================
# TASK B — narrow appearance interpretation
# ==========================================================

def test_a_wall_mounted_planter_with_plants_is_recovered():
    recovered = recovered_claims_from_failures(_failures(), _source_text())
    planter = [c for c in recovered if (c.get("text") or "").lower() == "planter"]

    assert planter, "the planter claim was not recovered"

    anchored, _ = _anchor(planter)
    entry = _by_element(anchored, "planter")[0]

    assert entry["kind"] == ["planter"]
    assert entry["kind_basis"] == "appearance_rule"
    assert entry["evidence_class"] == "MODEL_REPORTED"
    assert entry["relations"][0]["relation"] == "mounted_on"
    assert entry["relations"][0]["target_kind"] == "wall"
    # The model's own count is not supported by the quote and is not carried.
    assert entry["model_reported_count"] is None


def test_a_plain_bowl_without_plants_is_not_a_planter():
    assert _appearance_kind(
        "A shallow ribbed stone bowl mounted on the wall.") is None


def test_a_bowl_with_flowers_elsewhere_but_no_containment_is_not_a_planter():
    """Flowers in the sentence do not convert an unrelated object."""

    assert _appearance_kind(
        "A carved stone bench beside a bed of purple flowers.") is None


def test_flower_motifs_on_a_mounted_bowl_do_not_make_a_planter():
    assert _appearance_kind(
        "A shallow bowl carved with flower motifs and mounted on the wall.") is None


def test_a_planter_that_is_not_wall_mounted_is_not_interpreted():
    assert _appearance_kind(
        "A shallow ribbed bowl filled with purple flowers standing on the ground.") is None


def test_a_negated_planter_is_rejected():
    text = _source_text()
    claim = {
        "text": "No planter is visible",
        "source_quote": "A shallow, ribbed/scalloped stone bowl mounted on the wall, filled with a mass of small purple flowers.",
        "kind": "planter",
        "certainty": "ASSERTED",
        "count": None,
        "text_is_model_label": True,
    }
    anchored, report = _anchor([claim])

    assert report["accepted_count"] == 0
    assert report["rejected"][0]["reason"] == "claim_states_absence"


def test_a_negated_source_quote_never_becomes_a_positive_planter():
    quote = "There is no planter visible on the wall."
    claim = {
        "text": "planter",
        "source_quote": quote,
        "kind": "planter",
        "certainty": "ASSERTED",
        "count": None,
        "text_is_model_label": True,
    }
    observation = build_architectural_observation(
        {"observed": [], "image_type": "facade"}, image_id="negative")
    anchored, report = element_evidence_from_claims(
        observation, [claim], quote, source_image=SOURCE_IMAGE)

    assert anchored["element_evidence"]["elements"] == []
    assert report["rejected"][0]["reason"] == "claim_states_absence"


# ==========================================================
# TASK B/D — the carved horizontal band
# ==========================================================

def test_a_carved_horizontal_band_is_recovered_as_a_generic_band():
    recovered = recovered_claims_from_failures(_failures(), _source_text())
    band = [c for c in recovered if "carved relief" in (c.get("text") or "").lower()]

    assert band, "the carved relief band was not recovered"

    anchored, _ = _anchor(band)
    entry = anchored["element_evidence"]["elements"][0]

    assert entry["kind"] == ["decorative_band"]
    assert entry["kind_basis"] == "appearance_rule"
    # The model's precise naming is preserved but NOT asserted.
    assert entry["declared_kind"] == "frieze"
    assert entry["evidence_class"] == "MODEL_REPORTED"


def test_a_carved_band_is_never_asserted_to_be_a_cornice_frieze_or_floor():
    recovered = recovered_claims_from_failures(_failures(), _source_text())
    band = [c for c in recovered if "carved relief" in (c.get("text") or "").lower()]

    anchored, _ = _anchor(band)
    entry = anchored["element_evidence"]["elements"][0]

    for forbidden in ("cornice", "frieze", "floor", "storey", "entablature"):
        assert forbidden not in entry["kind"]
    assert entry["uncertainty"], "the precise classical type must stay uncertain"


def test_the_appearance_rule_does_not_fire_on_unrelated_descriptions():
    assert _appearance_kind("A low railing of turned balusters.") is None
    assert _appearance_kind("Two vertical columns with fluted shafts.") is None
    assert _appearance_kind("Small black metal lantern fixtures.") is None
    assert _appearance_kind(
        "A horizontal painted band with floral ornament motifs.") is None


# ==========================================================
# SOURCE AND UNCERTAINTY SAFETY
# ==========================================================

def test_recovered_records_still_require_a_verbatim_quote():
    failures = [{
        "claim_index": 0, "category": "observed_elements",
        "field": "text", "reason": "no_match",
        "claim": {"text": "planter",
                  "source_quote": "a quote never present in the observation",
                  "kind": "planter", "certainty": "ASSERTED", "count": 3},
    }]
    assert recovered_claims_from_failures(failures, _source_text()) == []


def test_structural_function_is_still_refused():
    text = _source_text()
    claim = {
        "text": "pier",
        "source_quote": ("A broad vertical pier with a smooth, horizontally‑coursed "
                         "shaft and a plain projecting capital block."),
        "kind": "pier",
        "certainty": "ASSERTED",
        "count": None,
        "load_bearing": True,
        "structural_function": "load_bearing",
    }
    anchored, _ = _anchor([claim])
    entry = anchored["element_evidence"]["elements"][0]

    assert "load_bearing" not in entry
    assert "structural_function" not in entry


def test_no_count_is_fabricated_anywhere():
    recovered = recovered_claims_from_failures(_failures(), _source_text())
    anchored, _ = _anchor(_accepted() + recovered)

    for entry in anchored["element_evidence"]["elements"]:
        if entry["model_reported_count"] is not None:
            assert str(entry["model_reported_count"]) in (entry["source_quote"] or "")


# ==========================================================
# TASK C — claim count vs object count
# ==========================================================

def test_records_are_not_treated_as_distinct_physical_objects():
    recovered = recovered_claims_from_failures(_failures(), _source_text())
    anchored, report = _anchor(
        _accepted() + recovered,
        raw_claim_count=38, normalizer_accepted_count=30)

    elements = anchored["element_evidence"]["elements"]
    unique_evidence = {
        (e["source_quote"], tuple(sorted(e["kind"])), e["element"])
        for e in elements
    }
    unique_quotes = {e["source_quote"] for e in elements}

    # The list carries category-level evidence records. It is not an object list.
    assert len(elements) == 26
    assert len(unique_evidence) == 19
    assert len(unique_quotes) == 18

    # Bookkeeping is exposed and keeps claim count separate from object count.
    assert report["raw_claim_count"] == 38
    assert report["accepted_claim_count"] == 30
    assert report["carried_evidence_record_count"] == 26
    assert report["unique_evidence_claim_count"] == len(unique_evidence)
    assert report["unique_source_quote_count"] == len(unique_quotes)
    assert report["supported_count_claim_count"] == 0
    assert report["model_reported_object_count"] is None
    assert report["physical_object_count"] is None
    assert report["verified_object_count"] is None


def test_the_20_to_26_delta_is_two_appearance_records_plus_four_pier_records():
    recovered = recovered_claims_from_failures(_failures(), _source_text())
    accepted_only, _ = _anchor(_accepted())
    recovered_only, _ = _anchor(recovered)

    base_records = accepted_only["element_evidence"]["elements"]
    recovered_records = recovered_only["element_evidence"]["elements"]
    pier_records = [e for e in base_records if e["kind"] == ["pier"]]
    pier_quotes = {e["source_quote"] for e in pier_records}
    appearance_records = [
        e for e in recovered_records if e["kind_basis"] == "appearance_rule"
    ]

    assert len(base_records) == 20
    assert len(recovered_records) == 6
    assert len(pier_records) == 6
    assert len(pier_quotes) == 3
    assert {e["kind"][0] for e in appearance_records} == {
        "planter", "decorative_band"
    }
    assert len(appearance_records) == 2

    # V7.3 carried 20 records: 16 accepted + 4 recovered. V7.4 adds four
    # duplicate-category pier records and two appearance records, not six
    # newly verified physical objects.
    historical_v7_3_records = 20
    newly_transportable_pier_records = 4
    new_appearance_records = 2
    assert historical_v7_3_records + newly_transportable_pier_records + \
        new_appearance_records == 26


def test_the_lantern_counts_stay_three_separate_facts():
    recovered = recovered_claims_from_failures(_failures(), _source_text())
    lanterns = [c for c in recovered if (c.get("text") or "").lower() == "lanterns"]
    anchored, _ = _anchor(lanterns)

    entry = _by_element(anchored, "lanterns")[0]

    assert entry["model_reported_count"] is None       # quote has no digit
    assert "verified_count" not in entry
    assert "count" not in entry


# ==========================================================
# LEGACY / SCHEMA
# ==========================================================

def test_legacy_architectural_elements_entries_are_unchanged():
    anchored, _ = _anchor(_accepted())

    for entry in anchored["architectural_elements"]:
        assert set(entry) == {"evidence_phrase", "status", "confidence", "kind"}


def test_the_strict_normalizer_schema_is_untouched():
    from core.vision.observation_normalizer_v1 import STRUCTURED_SCHEMA

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


def test_no_position_is_invented():
    recovered = recovered_claims_from_failures(_failures(), _source_text())
    anchored, _ = _anchor(_accepted() + recovered)

    for entry in anchored["element_evidence"]["elements"]:
        assert entry["position"] is None


# ==========================================================
# TASK F — production builder and offline API acceptance
# ==========================================================

def _recorded_bridge():
    from core.vision.general_visual_observer_v1 import (
        CONTRACT as BRIDGE_CONTRACT,
        raw_observation,
    )

    record = _live()
    result = record["normalizer_result"]
    text = _source_text()
    raw = raw_observation(
        provider="ollama", model="qwen3.8:27b",
        backend="http://127.0.0.1:11434", thinking_mode=False,
        body={"response": text, "done": True, "done_reason": "stop"},
    )
    raw["diagnostics"] = {
        "original_source_sha256": CROP_SHA,
        "observer_input_width": 890,
        "observer_input_height": 510,
    }
    return {
        "contract": BRIDGE_CONTRACT,
        "raw_observer": raw,
        "normalization": {
            "status": "NORMALIZED",
            "structured": result["structured"],
            "source_resolution_failures": result["source_resolution_failures"],
        },
    }


def test_production_builder_carries_correct_identity_and_context():
    from core.vision.image_understanding_v1 import build_understanding

    understanding = build_understanding(
        _recorded_bridge(), provider="ollama", model="qwen3.8:27b",
        image_id="v7-live")

    block = understanding["element_evidence"]
    report = understanding["element_evidence_report"]
    kinds = set()
    context_kinds = set()
    for entry in block["elements"]:
        kinds.update(entry["kind"])
        context_kinds.update(entry.get("context_kinds") or [])

    # Identity: lanterns are light fixtures, not walls.
    lantern_entry = [e for e in block["elements"]
                     if "lantern" in (e["element"] or "").lower()]
    assert lantern_entry
    assert "light_fixture" in lantern_entry[0]["kind"]
    assert "wall" not in lantern_entry[0]["kind"]
    assert "wall" in lantern_entry[0].get("context_kinds", [])

    assert "planter" in kinds            # recovered via appearance rule
    assert "decorative_band" in kinds    # recovered via appearance rule
    assert "pier" in kinds               # pier identity preserved

    # Capital is context on pier entries, not a primary identity.
    pier_entries = [e for e in block["elements"]
                    if "pier" in (e["element"] or "").lower()]
    assert pier_entries
    for entry in pier_entries:
        assert "capital" not in entry["kind"]
    assert "capital" in context_kinds    # capital preserved as context somewhere

    assert report["raw_claim_count"] == 38
    assert report["accepted_claim_count"] == 30
    assert report["carried_evidence_record_count"] == 26
    assert report["unique_evidence_claim_count"] == 19
    assert report["stage_c_recovered_claims"] == 8
    assert report["stage_c_recovered_evidence_records"] == 6
    assert report["physical_object_count"] is None


def test_api_response_carries_identity_provenance(monkeypatch):
    """Genuine Flask route; every model entry point is forbidden."""

    import io

    import core.vision.image_session_v1 as session_module
    import core.vision.vision_provider_ollama_v1 as provider_module
    from core.llm.llm_gateway import LLMGateway
    import app as application
    from PIL import Image as _Image

    def _forbidden(*args, **kwargs):
        raise AssertionError("a live model call was attempted")

    monkeypatch.setattr(provider_module.OllamaVisionProvider, "analyze", _forbidden)
    monkeypatch.setattr(provider_module.OllamaVisualObserver, "observe", _forbidden)
    monkeypatch.setattr(provider_module.OllamaTextNormalizer, "normalize", _forbidden)
    monkeypatch.setattr(LLMGateway, "generate", lambda self, *a, **k: "recorded reply")

    class _Recorded:
        name = "ollama"
        model = "qwen3.8:27b"
        endpoint = "recorded"

        def is_available(self):
            return True

        def analyze(self, asset):
            return _recorded_bridge()

        def cache_identity(self):
            return {"provider": "ollama", "model": "qwen3.8:27b", "recorded": True}

    monkeypatch.setattr(session_module, "provider", lambda: _Recorded())

    buffer = io.BytesIO()
    _Image.new("RGB", (64, 64), "white").save(buffer, format="PNG")
    buffer.seek(0)

    import contextlib

    with contextlib.redirect_stdout(io.StringIO()):
        response = application.app.test_client().post(
            "/api/chat",
            data={"text": "what do you see", "image": (buffer, "crop.png")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200

    payload = response.get_json() or {}
    block = ((payload.get("response") or {}).get("vision") or {}).get("element_evidence")

    assert block is not None
    assert block["source_image"]["sha256"] == CROP_SHA

    # Verify identity/context separation reached the wire.
    elements = block["elements"]
    kinds = set()
    context_kinds = set()
    for entry in elements:
        kinds.update(entry["kind"])
        context_kinds.update(entry.get("context_kinds") or [])

    # Lantern identity is light_fixture, wall is context.
    lantern_entry = [e for e in elements
                     if "lantern" in (e["element"] or "").lower()]
    assert lantern_entry
    assert "light_fixture" in lantern_entry[0]["kind"]
    assert "wall" not in lantern_entry[0]["kind"]
    assert "wall" in lantern_entry[0].get("context_kinds", [])
    assert lantern_entry[0]["relations"][0]["relation"] == "mounted_on"
    assert lantern_entry[0]["relations"][0]["target_kind"] == "wall"

    assert "planter" in kinds
    assert "decorative_band" in kinds

    # The API carries evidence records, not a silently invented object total.
    unique_evidence = {
        (e["source_quote"], tuple(sorted(e["kind"])), e["element"])
        for e in elements
    }
    assert len(elements) == 26
    assert len(unique_evidence) == 19

    # No unsupported counts or fabricated coordinates.
    serialised = json.dumps(block)
    for forbidden in ('"species"', '"load_bearing"', '"visible_floor_count"',
                      '"verified_count"', '"physical_object_count"'):
        assert forbidden not in serialised


def test_text_only_flask_response_remains_backward_compatible(monkeypatch):
    """A normal text turn stays model-isolated and gains no vision evidence."""

    import core.vision.vision_provider_ollama_v1 as provider_module
    from core.llm.llm_gateway import LLMGateway
    import app as application

    def _forbidden(*args, **kwargs):
        raise AssertionError("a live model call was attempted")

    monkeypatch.setattr(provider_module.OllamaVisionProvider, "analyze", _forbidden)
    monkeypatch.setattr(provider_module.OllamaVisualObserver, "observe", _forbidden)
    monkeypatch.setattr(provider_module.OllamaTextNormalizer, "normalize", _forbidden)
    monkeypatch.setattr(
        LLMGateway, "generate",
        lambda self, *args, **kwargs: "recorded ordinary reply")

    response = application.app.test_client().post(
        "/api/chat", json={"text": "hello"})

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("response") is not None
    assert "element_evidence" not in json.dumps(payload)


def test_ordinary_turns_without_evidence_do_not_gain_the_key(monkeypatch):
    """A bridge with no normalization must not fabricate an element collection."""

    from core.vision.general_visual_observer_v1 import (
        CONTRACT as BRIDGE_CONTRACT,
        raw_observation,
    )
    from core.vision.image_understanding_v1 import build_understanding

    raw = raw_observation(provider="ollama", model="m", backend="b",
                          thinking_mode=False, error="no_vision_provider_configured")
    bridge = {"contract": BRIDGE_CONTRACT, "raw_observer": raw,
              "normalization": {"status": "NOT_RUN", "reason": "unavailable"}}

    understanding = build_understanding(bridge, provider="ollama", model="m",
                                        image_id="plain")

    assert understanding["element_evidence"] is None
