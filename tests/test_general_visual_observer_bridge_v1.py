"""Offline transport, schema, provenance, verification and live-path contracts.

Synthetic local evidence uses existing reader contracts, never an acceptance
image, its content, or tuned pixel thresholds. No model download/inference.
"""
import copy
import base64
from dataclasses import replace
import hashlib
import json
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from config.vision_config import VisionConfig
from core.vision.general_visual_observer_v1 import (
    CONTRACT, OBSERVER_VERSION, raw_observation, run_visual_bridge,
)
from core.vision.observation_normalizer_v1 import (
    CATEGORIES, CLAIM_SCHEMA, MAX_ITEMS, STRUCTURED_SCHEMA, NORMALIZER_PROMPT,
    iter_claims, parse_normalization, resolve_source_quote, validate_structured,
)
from core.vision.provider_candidate_verification_v1 import provider_candidates, verify_candidates
from core.vision.vision_provider_ollama_v1 import (
    OllamaVisionProvider, OllamaTextNormalizer, get_vision_provider,
)
from core.vision.image_understanding_v1 import build_understanding
from core.vision.vision_observation_mode_v1 import build_observation, render_observation


def structured():
    return {"drawing_type": None, **{k: [] for k in CATEGORIES},
            "openings": {"doors": [], "windows": [], "other_openings": []}}


def claim(text="bed", *, kind="bed", quote=None, certainty="ASSERTED", count=None):
    return {"text": text, "source_quote": quote or text, "kind": kind,
            "certainty": certainty, "count": count}


def bridge(data=None, text="bed", status="NORMALIZED"):
    if data is None:
        data = structured()
        data["furniture"] = [claim()]
    return {"contract": CONTRACT,
            "raw_observer": raw_observation(provider="test", model="model", backend="test",
                                             thinking_mode="low", body={"response": text, "done": True}),
            "normalization": {"status": status, "structured": data}}


def local():
    return {"contract": "LocalPlanReadingV1", "version": "1.3", "status": "grounded",
            "source": "local_offline_raster", "provider_independent": True,
            "image_size": {"width": 160, "height": 120}, "ocr_status": "analyzed",
            "symbol_analysis_status": "analyzed", "element_analysis_status": "analyzed",
            "labels": [], "openings": [], "element_evidence": [],
            "furniture_evidence": [{
                "class": "bed", "bbox_pixels": [20, 20, 70, 90], "name": "bed",
                "corroboration": ["frame", "pillow", "blanket"], "status": "visible",
                "confidence": "MEDIUM", "evidence_type": "fixture",
                "source": "local_raster_symbol_topology", "provider_independent": True,
                "item_id": "synthetic_local_bed", "raster_patch_sha256": "a" * 64,
            }]}


def label(text, *, correction=None, raw=None):
    return {"text": text, "raw_ocr": text if raw is None else raw,
            "bbox_pixels": [5, 5, 70, 15], "status": "grounded_ocr",
            "evidence_type": "local_ocr", "confidence": "MEDIUM", "correction": correction,
            "independent_passes": 2, "ocr_confidence": 75}


class Response:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status
        self.text = json.dumps(body, ensure_ascii=False)

    def json(self):
        return self.body


class Transport:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def post(self, url, **kwargs):
        self.calls.append((url, copy.deepcopy(kwargs)))
        response = self.replies.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def asset(tmp_path):
    path = tmp_path / "unseen-synthetic.png"
    with Image.new("RGB", (160, 120), "white") as image:
        image.save(path)
    return str(path)


def provider_transport(asset, *, normalized=None, raw="bed", config=None, normalizer_reply=None):
    data = normalized or structured()
    if normalized is None:
        data["furniture"] = [claim()]
    transport = Transport([
        Response({"response": raw, "done": True, "done_reason": "stop", "eval_count": 31}),
        normalizer_reply or Response({"response": json.dumps(data), "done": True}),
    ])
    provider = OllamaVisionProvider(config=config or VisionConfig.from_env(), session=transport)
    return provider, transport, provider.analyze(asset if isinstance(asset, dict) else {"path": asset})


def test_two_requests_raw_verbatim_and_text_only_normalization(asset):
    raw = "  bed\nمتن قابل مشاهده\n"
    provider, transport, result = provider_transport(asset, raw=raw)
    observer, normalizer = [c[1]["json"] for c in transport.calls]
    assert len(transport.calls) == 2
    assert observer["images"] and "format" not in observer
    assert normalizer["prompt"] == raw
    assert normalizer["think"] is False
    assert normalizer["options"]["temperature"] == observer["options"]["temperature"] == 0
    assert normalizer["options"]["num_ctx"] == provider.config.normalizer_ctx
    assert observer["options"]["num_ctx"] == provider.config.observer_ctx
    assert normalizer["options"]["num_predict"] == provider.config.normalizer_tokens
    assert normalizer["format"] == STRUCTURED_SCHEMA
    assert not ({"images", "image", "image_path", "path", "file"} & set(normalizer))
    assert asset not in json.dumps(normalizer)
    retained = result["raw_observer"]
    assert retained["raw_text"] == raw
    assert retained["raw_text_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert retained["raw_truncated"] is False and retained["original_length"] == len(raw)
    assert retained["generation_metadata"]["eval_count"] == 31
    assert retained["provider"] == "ollama" and retained["observer_version"] == OBSERVER_VERSION
    result["raw_observer"]["raw_text"] = "mutated caller"
    assert provider.analyze(asset)["raw_observer"]["raw_text"] == raw


@pytest.mark.parametrize("reply", [Response({"response": "not json"}),
    Response({"response": "{}"}), RuntimeError("normalizer unavailable"),
    Response({"response": "partial", "done_reason": "length"}), Response({}, 503)])
def test_raw_and_local_survive_all_normalizer_failures(asset, reply):
    _, _, result = provider_transport(asset, normalizer_reply=reply)
    original = local()
    u = build_understanding(result, local_plan_reading=original)
    assert u["visual_observer_bridge"]["raw_observer"]["raw_text"] == "bed"
    assert u["visual_observer_bridge"]["normalization"]["status"] == "FAILED"
    assert u["local_plan_reading"] == original
    assert build_observation(u)["grounded_furniture_evidence"]
    assert not u["grounded_provider_evidence"]


def test_generic_boundary_accepts_only_raw_text():
    seen = []
    observer = SimpleNamespace(observe=lambda _: bridge()["raw_observer"])
    normalizer = SimpleNamespace(normalize=lambda text: seen.append(text) or {"status": "FAILED"})
    result = run_visual_bridge(observer, normalizer, {"path": "never-pass-to-normalizer"})
    assert seen == ["bed"] and result["raw_observer"]["raw_text"] == "bed"
    normalizer.normalize = lambda text: (_ for _ in ()).throw(RuntimeError("down"))
    assert run_visual_bridge(observer, normalizer, object())["raw_observer"]["raw_text"] == "bed"
    with pytest.raises(TypeError):
        OllamaTextNormalizer(VisionConfig.from_env(), Transport([])).normalize({"path": "image"})


def rich_observation():
    """Synthetic observer prose across the full taxonomy; no acceptance image."""
    groups = {
        "observed_elements": ["a paved exterior forecourt", "a planted edge beside the facade"],
        "enclosed_spaces": ["an enclosed space at the upper left", "a narrow central enclosure"],
        "walls": ["a thick outer wall", "a thin partition", "a curved wall segment"],
        "vertical_circulation": ["a stair with parallel tread lines", "a rectangular landing"],
        "furniture": ["a rectangular table", "chairs beside the table", "a sofa along the wall",
                      "a freestanding cabinet", "a small round side table"],
        "fixtures": ["a basin outline", "a long counter", "a circular fixture symbol"],
        "structural_elements": ["a square column symbol", "a circular support symbol"],
        "axes": ["a dashed axis with an unreadable label"],
        "orientation": ["an arrow whose direction is ambiguous"],
        "provider_ocr_candidate": ["RECEPTION"],
        "ocr_exact": ["COURTYARD", "حیاط"],
        "ocr_partial": ["STO?AGE"],
        "ocr_unreadable": ["small text is unreadable"],
        "scale": ["1:125"],
        "dimensions": ["6.25 m", "850 mm"],
        "level_codes": ["+0.45", "-0.30"],
        "spatial_relationships": ["the table is beside the chairs", "the landing adjoins the stair",
                                  "the counter touches the partition"],
        "interpretations": ["possibly a shared workspace", "the enclosure may be storage"],
        "unknowns": ["the wall material is unknown", "the building height is unknown",
                     "the number of floors is unknown"],
        "openings.doors": ["a swing arc at the enclosure", "a wide double opening"],
        "openings.windows": ["a narrow glazed strip", "a window in the outer wall"],
        "openings.other_openings": ["an unmarked gap in the partition"],
    }
    data = structured()
    data["drawing_type"] = claim("an architectural sheet", kind="drawing")
    paragraphs = ["The observer describes an architectural sheet."]
    for category, phrases in groups.items():
        target = (data["openings"][category.split(".")[1]]
                  if category.startswith("openings.") else data[category])
        for phrase in phrases:
            certainty = ("UNKNOWN" if "unknown" in phrase or "unreadable" in phrase
                         else "AMBIGUOUS" if category in ("orientation", "interpretations")
                         else "ASSERTED")
            target.append(claim(phrase, kind=category.split(".")[-1], certainty=certainty))
        paragraphs.append(category + ": " + "; ".join(phrases) + ".")
    return "\n".join(paragraphs), data


def test_rich_observer_text_normalizes_with_compact_exact_sources(asset):
    raw, data = rich_observation()
    # Controlled transport verifies the contract, not live model completion.
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    assert len(list(iter_claims(data))) >= 40
    assert len(encoded) > 4096  # characters, deliberately NOT a token estimate
    _, transport, result = provider_transport(asset, raw=raw, normalized=data,
        normalizer_reply=Response({"response": encoded, "done": True, "done_reason": "stop"}))
    assert result["normalization"]["status"] == "NORMALIZED"
    assert result["normalization"]["structured"] == data
    request = transport.calls[1][1]["json"]
    assert request["prompt"] == raw and "images" not in request
    assert result["raw_observer"]["raw_text"] == raw
    candidates = provider_candidates(result["normalization"], raw)
    assert all(c["text"] in c["source_quote"] in raw for c in candidates)
    assert {c["certainty"] for c in candidates} == {"ASSERTED", "UNKNOWN", "AMBIGUOUS"}
    assert {c["text"] for c in candidates if c["category"] == "axes"} == {
        item["text"] for item in data["axes"]}
    for category in ("ocr_exact", "scale", "dimensions", "level_codes"):
        assert [c["text"] for c in candidates if c["category"] == category] == [
            item["text"] for item in data[category]]


def test_length_stop_rejects_even_complete_rich_json_and_retains_raw(asset):
    raw, data = rich_observation()
    provider, _, result = provider_transport(asset, raw=raw, normalizer_reply=Response({
        "response": json.dumps(data), "done": True, "done_reason": "length"}))
    assert result["normalization"]["status"] == "FAILED"
    assert "normalizer_generation_incomplete" in result["normalization"]["error"]
    assert result["raw_observer"]["raw_text"] == raw
    assert not provider._raw_cache
    original = local()
    understanding = build_understanding(result, local_plan_reading=original)
    assert understanding["visual_observer_bridge"]["raw_observer"]["raw_text"] == raw
    assert understanding["local_plan_reading"] == original
    assert not understanding["provider_candidates"]
    assert build_observation(understanding)["grounded_furniture_evidence"]


def test_normalizer_budget_defaults_and_environment_overrides(monkeypatch):
    for key in ("CTX", "TOKENS"):
        monkeypatch.delenv("ARCHITECTOS_VISION_NORMALIZER_" + key, raising=False)
    cfg = VisionConfig.from_env()
    assert (cfg.normalizer_ctx, cfg.normalizer_tokens) == (32768, 8192)
    monkeypatch.setenv("ARCHITECTOS_VISION_NORMALIZER_CTX", "24576")
    monkeypatch.setenv("ARCHITECTOS_VISION_NORMALIZER_TOKENS", "6144")
    cfg = VisionConfig.from_env()
    transport = Transport([Response({"response": json.dumps(structured()), "done": True})])
    assert OllamaTextNormalizer(cfg, transport).normalize("")["status"] == "NORMALIZED"
    assert transport.calls[0][1]["json"]["options"] == {
        "temperature": 0, "num_ctx": 24576, "num_predict": 6144}


@pytest.mark.parametrize("setting", ["CTX", "TOKENS"])
@pytest.mark.parametrize("value", ["0", "-1", "invalid"])
def test_invalid_normalizer_budget_is_rejected(monkeypatch, setting, value):
    monkeypatch.setenv("ARCHITECTOS_VISION_NORMALIZER_" + setting, value)
    with pytest.raises(ValueError):
        VisionConfig.from_env()


@pytest.mark.parametrize("field", ["normalizer_ctx", "normalizer_tokens", "timeout", "normalizer_timeout",
                                   "observer_ctx", "observer_max_long_edge", "observer_max_pixels"])
def test_normalizer_budget_invalidates_provider_and_persisted_cache(monkeypatch, asset, field):
    from core.vision import image_session_v1 as session
    from core.vision.image_understanding_v1 import EVIDENCE_PIPELINE_VERSION
    from core.vision.local_plan_reader_v1 import local_ocr_environment
    cfg = VisionConfig.from_env()
    before = OllamaVisionProvider(config=cfg)
    after = OllamaVisionProvider(config=replace(cfg, **{field: getattr(cfg, field) + 1024}))
    assert before.cache_identity() != after.cache_identity()
    assert before._cache_key(asset) != after._cache_key(asset)
    cached = {"evidence_pipeline": EVIDENCE_PIPELINE_VERSION,
              "local_ocr_environment": local_ocr_environment(),
              "vision_cache_identity": before.cache_identity(), "visual_observer_bridge": bridge()}
    monkeypatch.setattr(session, "provider", lambda: after)
    assert session._cache_reuse_reason({"analysis_status": "ANALYZED_WITH_UNCERTAINTY"}, cached) == "stale_vision_configuration"


@pytest.mark.parametrize("field", ["text", "source_quote", "kind"])
def test_compact_claim_string_boundaries(field):
    limit = CLAIM_SCHEMA["properties"][field]["maxLength"]
    data = structured()
    data["furniture"] = [{**claim(), field: "x" * limit}]
    validate_structured(data)
    data["furniture"][0][field] += "x"
    with pytest.raises(ValueError, match="string bounds"):
        validate_structured(data)


def test_normalizer_input_reduction_is_explicit_and_raw_is_not_truncated(asset):
    cfg = replace(VisionConfig.from_env(), normalizer_input_chars=3)
    _, transport, result = provider_transport(asset, raw="bed" + " " * 80, config=cfg)
    assert result["raw_observer"]["original_length"] == 83
    assert result["raw_observer"]["raw_truncated"] is False
    assert result["normalization"]["input"]["input_reduced"] is True
    assert transport.calls[1][1]["json"]["prompt"] == "bed"


def test_thinking_only_generation_is_retained_without_normalization(asset):
    transport = Transport([Response({"response": "", "thinking": "diagnostic thoughts",
                                     "done_reason": "length", "eval_count": 1600})])
    result = OllamaVisionProvider(session=transport).analyze(asset)
    assert result["normalization"]["status"] == "NOT_RUN"
    assert result["raw_observer"]["generation_status"] == "PARTIAL"
    assert result["raw_observer"]["generation_metadata"]["thinking"] == "diagnostic thoughts"
    assert len(transport.calls) == 1


def test_partial_observer_text_can_be_normalized_without_losing_partial_status(asset):
    data = structured()
    transport = Transport([Response({"response": "bed", "done_reason": "length"}),
                           Response({"response": json.dumps(data)})])
    result = OllamaVisionProvider(session=transport).analyze(asset)
    assert result["raw_observer"]["raw_text"] == "bed"
    assert build_understanding(result)["analysis_status"] == "PARTIAL"


def test_every_schema_collection_and_string_is_bounded_and_objects_closed():
    def inspect(node):
        kind = node.get("type")
        if kind == "array":
            assert 0 < node["maxItems"] <= MAX_ITEMS
            inspect(node["items"])
        if kind == "string":
            assert "maxLength" in node or "enum" in node
        if kind == "object" or kind == ["object", "null"]:
            assert node["additionalProperties"] is False
            # ARCHITECTURAL_EYE_EVIDENCE_TIER_HANDOFF_V1 — an object may now
            # declare explicitly OPTIONAL properties (the storey-observation
            # slot). The schema stays CLOSED: every property must be either
            # required or declared optional, and no property may be both.
            required = set(node["required"])
            optional = set(node.get("optional") or ())
            assert required | optional == set(node["properties"])
            assert not (required & optional)
            for child in node["properties"].values():
                inspect(child)
    inspect(STRUCTURED_SCHEMA)
    validate_structured(structured())


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(grounded=True),
    lambda d: d["furniture"].extend([claim()] * (MAX_ITEMS + 1)),
    lambda d: d["furniture"].append(claim("x" * 241)),
    lambda d: d["furniture"].append(claim(count=True)),
    lambda d: d["furniture"].append(claim(certainty="HIGH")),
    lambda d: d["furniture"].append({**claim(), "state": "CONFIRMED"}),
])
def test_strict_schema_rejects_extra_keys_types_and_bounds(mutation):
    data = structured()
    mutation(data)
    with pytest.raises(ValueError):
        parse_normalization(json.dumps(data), "bed")


def test_normalizer_cannot_invent_new_fact_or_axis_sequence():
    data = structured()
    data["axes"] = [claim("A-Z", kind="axis", quote="A B C")]
    diagnostics = {}
    result = parse_normalization(json.dumps(data), "A B C", diagnostics=diagnostics)
    assert result["axes"] == []
    assert diagnostics["rejected_claim_count"] == 1
    assert diagnostics["source_resolution_failures"][0]["field"] == "text"


def test_candidate_lifecycle_and_confidence_never_grounds():
    value = bridge()
    candidates = provider_candidates(value["normalization"], "bed")
    assert candidates[0]["state"] == "PROVIDER_CANDIDATE" and not candidates[0]["grounded"]
    candidates[0]["confidence"] = "HIGH"
    verified = verify_candidates(candidates, None)
    assert verified[0]["state"] == "UNVERIFIED" and not verified[0]["grounded"]
    confirmed = verify_candidates(candidates, local())
    assert confirmed[0]["state"] == "CONFIRMED" and confirmed[0]["grounded"]
    assert confirmed[0]["verification"]["local_evidence"][0]["item_id"] == "synthetic_local_bed"
    assert candidates[0]["state"] == "PROVIDER_CANDIDATE"  # no mutation


def test_confirmed_evidence_enters_grounded_observation():
    u = build_understanding(bridge(), local_plan_reading=local())
    assert u["observed"] == ["bed"]
    observation = build_observation(u)
    assert observation["grounded_provider_evidence"][0]["state"] == "CONFIRMED"
    assert observation["grounded_furniture_evidence"]


def test_contradiction_never_removes_independent_local_evidence():
    data = structured()
    data["furniture"] = [claim("no bed", quote="no bed", count=0)]
    u = build_understanding(bridge(data, "no bed"), local_plan_reading=local())
    assert u["provider_candidates"][0]["state"] == "CONTRADICTED"
    assert u["grounded_provider_evidence"] == [] and u["observed"] == []
    assert build_observation(u)["grounded_furniture_evidence"]


@pytest.mark.parametrize("quote,certainty,expected", [("unknown bed", "UNKNOWN", "UNVERIFIED"),
    ("maybe bed", "AMBIGUOUS", "AMBIGUOUS"), ("no bed", "ASSERTED", "UNVERIFIED"),
    ("maybe bed", "ASSERTED", "AMBIGUOUS")])
def test_unknown_ambiguous_and_negation_not_stripped(quote, certainty, expected):
    data = structured()
    data["furniture"] = [claim(quote="bed", certainty=certainty)]
    u = build_understanding(bridge(data, quote), local_plan_reading=local())
    assert u["provider_candidates"][0]["state"] == expected
    assert not u["grounded_provider_evidence"]
    assert u["provider_candidates"][0]["certainty"] == certainty


def test_count_and_modifiers_cannot_piggyback_on_local_type_presence():
    data = structured()
    data["furniture"] = [claim("large bed"), claim(count=3)]
    u = build_understanding(bridge(data, "large bed"), local_plan_reading=local())
    assert all(c["state"] == "UNVERIFIED" for c in u["provider_candidates"])


def test_observation_interpretation_and_knowledge_input_stay_separate():
    from core.vision.architectural_vision_interpreter_v1 import interpret_architectural_vision
    data = structured()
    data["furniture"] = [claim()]
    data["interpretations"] = [claim("probable bedroom", kind="bedroom")]
    u = build_understanding(bridge(data, "bed\nprobable bedroom"))
    observation = build_observation(u)
    assert observation["interpretation_section"] is None
    assert not any(c["category"] == "interpretations" for c in observation["provider_candidates"])
    assert u["observed"] == u["inferred"] == []
    assert "probable bedroom" not in render_observation(observation, "en")
    interpreted = interpret_architectural_vision(u)
    assert interpreted["space_type"] not in ("bedroom", "master bedroom")


def test_ocr_taxonomy_and_verified_ocr_are_distinct():
    data = structured()
    data["provider_ocr_candidate"] = [claim("789012", kind="text")]
    data["ocr_exact"] = [claim("LAB", kind="text")]
    data["ocr_partial"] = [claim("LA?", kind="text")]
    data["ocr_unreadable"] = [claim("Persian text visible", kind="text")]
    raw = "789012\nLAB\nLA?\nPersian text visible"
    loc = local()
    loc["labels"] = [label("LAB")]
    u = build_understanding(bridge(data, raw), local_plan_reading=loc)
    by_category = {c["category"]: c for c in u["provider_candidates"]}
    assert set(by_category) == {"provider_ocr_candidate", "ocr_exact", "ocr_partial", "ocr_unreadable"}
    assert by_category["provider_ocr_candidate"]["state"] == "UNVERIFIED"
    assert by_category["ocr_exact"]["state"] == "CONFIRMED"
    assert len(u["verified_ocr"]) == 1 and len(u["local_ocr"]) == 1


def test_corrected_local_label_does_not_verify_exact_ocr():
    data = structured()
    data["ocr_exact"] = [claim("LAB", kind="text")]
    loc = local()
    loc["labels"] = [label("LAB", correction="architectural_lexicon_match", raw="L4B")]
    u = build_understanding(bridge(data, "LAB"), local_plan_reading=loc)
    assert u["verified_ocr"] == [] and u["local_ocr"][0]["text"] == "LAB"


def test_scale_dimension_level_and_floor_title_do_not_cross_promote():
    data = structured()
    values = {"scale": "1:75", "dimensions": "4.20 m", "level_codes": "+0.85"}
    for category, value in values.items():
        data[category] = [claim(value, kind=category)]
    data["level_codes"].append(claim("Ground Floor", kind="level"))
    raw = "\n".join([*values.values(), "Ground Floor"])
    loc = local()
    loc["labels"] = [label(v) for v in [*values.values(), "Ground Floor"]]
    u = build_understanding(bridge(data, raw), local_plan_reading=loc)
    assert {(c["category"], c["text"]) for c in u["grounded_provider_evidence"]} == set(values.items())
    assert next(c for c in u["provider_candidates"] if c["text"] == "Ground Floor")["state"] == "UNVERIFIED"
    assert u["observed"] == []  # numbers never become geometry or old prose


def test_axes_orientation_remain_first_class_unverified_claims():
    data = structured()
    data["axes"] = [claim(v, kind="axis") for v in ["D", "E", "3", "4"]]
    data["orientation"] = [claim("north arrow", kind="north_indicator")]
    u = build_understanding(bridge(data, "D E 3 4\nnorth arrow"), local_plan_reading=local())
    assert [c["text"] for c in u["provider_candidates"] if c["category"] == "axes"] == ["D", "E", "3", "4"]
    assert u["provider_candidates"][-1]["category"] != "interpretations"
    assert any(c["category"] == "orientation" for c in u["provider_candidates"])
    assert not u["grounded_provider_evidence"]


def test_models_swap_via_configuration_and_thinking_defaults(monkeypatch):
    monkeypatch.delenv("ARCHITECTOS_VISION_THINK", raising=False)
    monkeypatch.delenv("ARCHITECTOS_VISION_NORMALIZER_MODEL", raising=False)
    monkeypatch.setenv("ARCHITECTOS_VISION_MODEL", "qwen3.8:27b")
    qwen = get_vision_provider()
    assert qwen.model == qwen.config.normalizer_model == "qwen3.8:27b"
    assert qwen.config.thinking == "low"
    monkeypatch.setenv("ARCHITECTOS_VISION_MODEL", "gemma4:12b")
    gemma = get_vision_provider()
    assert gemma.model == gemma.config.normalizer_model == "gemma4:12b"
    assert gemma.config.thinking is False and qwen is not gemma
    monkeypatch.setenv("ARCHITECTOS_VISION_THINK", "true")
    assert get_vision_provider().config.thinking is True


@pytest.mark.parametrize("field", ["model", "normalizer_model", "thinking"])
def test_provider_cache_identity_includes_configuration(field):
    cfg = VisionConfig.from_env()
    a = OllamaVisionProvider(config=cfg).cache_identity()
    b = OllamaVisionProvider(config=replace(cfg, **{field: "different"})).cache_identity()
    assert a != b


@pytest.mark.parametrize("version", ["OBSERVER_VERSION", "NORMALIZER_VERSION", "SCHEMA_VERSION",
                                     "OBSERVER_IMAGE_POLICY_VERSION"])
def test_cache_identity_includes_each_stage_version(monkeypatch, version):
    from core.vision import vision_provider_ollama_v1 as module
    provider = OllamaVisionProvider()
    before = provider.cache_identity()
    monkeypatch.setattr(module, version, "new-version")
    assert provider.cache_identity() != before


def test_raw_cache_uses_image_content_not_mtime(asset):
    from pathlib import Path
    import os
    provider = OllamaVisionProvider()
    first = provider._cache_key(asset)
    stat = os.stat(asset)
    Path(asset).write_bytes(b"z" * stat.st_size)
    os.utime(asset, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert provider._cache_key(asset) != first


@pytest.mark.parametrize("mode", ["offline", "exception", "normalizer_failure", "schema_failure"])
def test_session_fallback_retains_local_and_raw_and_persists(monkeypatch, asset, mode):
    from core.vision import image_session_v1 as session
    from core.vision.image_registry_v1 import ImageRegistryV1
    registry = ImageRegistryV1()
    stored = []
    registry.attach_persistence(lambda key: stored.append(registry.snapshot(key)))
    record = registry.register("bridge-test", path=asset, source_type="uploaded")
    result = bridge(status="FAILED") if mode == "normalizer_failure" else bridge()
    if mode == "schema_failure":
        result["normalization"]["structured"] = {"made_up": True}
    def analyze(_):
        if mode == "exception":
            raise RuntimeError("offline")
        return result
    stub = SimpleNamespace(name="test", model="test", is_available=lambda: mode != "offline", analyze=analyze)
    original = local()
    monkeypatch.setattr(session, "image_registry", registry)
    monkeypatch.setattr(session, "provider", lambda: stub)
    monkeypatch.setattr(session, "read_local_plan", lambda _: original)
    u = session.analyze_record("bridge-test", record["image_id"])
    assert u["local_plan_reading"] == original
    assert build_observation(u)["grounded_furniture_evidence"]
    assert stored[-1][1][0]["analysis"] == u
    if mode in ("normalizer_failure", "schema_failure"):
        assert u["visual_observer_bridge"]["raw_observer"]["raw_text"] == "bed"
    assert not u["grounded_provider_evidence"]
    # An explicit retry archives prior raw output; it is not silently overwritten.
    result["raw_observer"]["raw_text"] = "new observation"
    stub.is_available = lambda: True
    stub.analyze = lambda _: result
    retried = session.analyze_record("bridge-test", record["image_id"], force=True)
    assert retried["visual_observer_history"]


def test_stale_or_failed_bridge_cache_cannot_be_reused(monkeypatch):
    from core.vision import image_session_v1 as session
    from core.vision.image_understanding_v1 import EVIDENCE_PIPELINE_VERSION
    from core.vision.local_plan_reader_v1 import local_ocr_environment
    provider = OllamaVisionProvider()
    monkeypatch.setattr(session, "provider", lambda: provider)
    cached = {"evidence_pipeline": EVIDENCE_PIPELINE_VERSION,
              "local_ocr_environment": local_ocr_environment(),
              "vision_cache_identity": provider.cache_identity(),
              "visual_observer_bridge": bridge()}
    done = {"analysis_status": "ANALYZED_WITH_UNCERTAINTY"}
    assert session._cache_reuse_reason(done, cached) == "current"
    cached["vision_cache_identity"]["schema_version"] = "old"
    assert session._cache_reuse_reason(done, cached) == "stale_vision_configuration"
    cached["vision_cache_identity"] = provider.cache_identity()
    cached["visual_observer_bridge"]["normalization"]["status"] = "FAILED"
    assert session._cache_reuse_reason(done, cached) == "incomplete_visual_bridge"


def test_no_acceptance_constants_or_detector_imports():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    sources = [root / "core/vision" / name for name in (
        "general_visual_observer_v1.py", "observation_normalizer_v1.py",
        "provider_candidate_verification_v1.py", "vision_provider_ollama_v1.py")]
    forbidden = ("212.jpg", "morteza", "namplan", "title_block", "c9821bc88bcc", "87adb7eace81")
    for path in sources:
        source = path.read_text().lower()
        assert not any(token in source for token in forbidden)
        assert "import cv2" not in source


def test_available_observer_is_not_blocked_by_missing_normalizer(asset):
    cfg = replace(VisionConfig.from_env(), normalizer_model="missing-text-model")
    transport = Transport([
        Response({"capabilities": ["vision"]}),
        Response({"response": "bed", "done": True}),
        Response({"error": "model not found"}, 404),
    ])
    transport.get = lambda *args, **kwargs: Response({"models": [{"name": cfg.model}]})
    provider = OllamaVisionProvider(config=cfg, session=transport)
    assert provider.is_available()
    result = provider.analyze(asset)
    assert result["raw_observer"]["raw_text"] == "bed"
    assert result["normalization"]["status"] == "FAILED"


def test_non_json_transport_body_is_retained_for_diagnostics(asset):
    response = Response({})
    response.text = "unexpected backend prose\n"
    response.json = lambda: (_ for _ in ()).throw(ValueError("invalid JSON envelope"))
    result = OllamaVisionProvider(session=Transport([response])).analyze(asset)
    assert result["raw_observer"]["transport_text"] == response.text
    assert result["raw_observer"]["generation_status"] == "FAILED"


def test_verifier_exception_retains_raw_and_independent_local_evidence(monkeypatch):
    from core.vision import provider_candidate_verification_v1 as verifier
    monkeypatch.setattr(verifier, "verify_candidates", lambda *_: (_ for _ in ()).throw(RuntimeError("verification failed")))
    u = build_understanding(bridge(), local_plan_reading=local())
    assert u["provider_verification_error"]
    assert u["provider_candidates"][0]["state"] == "UNVERIFIED"
    assert not u["grounded_provider_evidence"]
    assert u["visual_observer_bridge"]["raw_observer"]["raw_text"] == "bed"
    assert build_observation(u)["grounded_furniture_evidence"]


def test_confident_drawing_type_does_not_establish_geometry_or_orientation():
    data = structured()
    data["drawing_type"] = claim("floor plan", kind="floor_plan")
    data["orientation"] = [claim("north", kind="north")]
    value = bridge(data, "floor plan\nnorth")
    value["confidence"] = "HIGH"
    value["observed"] = ["north facing bedroom"]
    u = build_understanding(value)
    assert u["image_type"] == "unknown"
    assert u["observed"] == [] and not u["grounded_provider_evidence"]
    assert u["safety"]["geometry_authoritative"] is False


def test_unknown_and_fabricated_zero_count_cannot_be_promoted():
    for text, c in [("unknown bed", claim()), ("bed", claim(count=0))]:
        data = structured()
        data["furniture"] = [c]
        u = build_understanding(bridge(data, text), local_plan_reading=local())
        assert u["provider_candidates"][0]["state"] == "UNVERIFIED"


def test_failed_or_partial_analysis_is_not_a_completed_cache():
    from core.vision.image_session_v1 import _cache_reuse_reason
    for status in ("FAILED", "PARTIAL", "PROVIDER_UNAVAILABLE", "UNSUPPORTED_IMAGE"):
        assert _cache_reuse_reason({"analysis_status": status}, {}) == "no_completed_analysis"


def test_live_legacy_provider_cannot_bypass_candidate_verification(monkeypatch, asset):
    from core.vision import image_session_v1 as session
    from core.vision.image_registry_v1 import ImageRegistryV1
    registry = ImageRegistryV1()
    record = registry.register("legacy-bridge-test", path=asset, source_type="uploaded")
    legacy = {"observed": ["bed visible", "north facing"], "confidence": "HIGH",
              "image_type": "architectural_render_or_photo"}
    stub = SimpleNamespace(name="legacy", model="legacy", is_available=lambda: True,
                           analyze=lambda _: legacy)
    monkeypatch.setattr(session, "provider", lambda: stub)
    monkeypatch.setattr(session, "image_registry", registry)
    monkeypatch.setattr(session, "read_local_plan", lambda _: None)
    result = session.analyze_record("legacy-bridge-test", record["image_id"])
    assert not result["observed"] and not result["grounded_provider_evidence"]
    assert result["visual_observer_bridge"]["raw_observer"]["generation_metadata"]["legacy_payload"] == legacy


def test_observer_and_normalizer_timeouts_are_independent(asset, monkeypatch):
    monkeypatch.delenv("ARCHITECTOS_VISION_TIMEOUT", raising=False)
    monkeypatch.delenv("ARCHITECTOS_VISION_NORMALIZER_TIMEOUT", raising=False)
    cfg = VisionConfig.from_env()
    assert (cfg.timeout, cfg.normalizer_timeout) == (300, 420)
    monkeypatch.setenv("ARCHITECTOS_VISION_TIMEOUT", "90")
    assert VisionConfig.from_env().normalizer_timeout == 420
    monkeypatch.setenv("ARCHITECTOS_VISION_NORMALIZER_TIMEOUT", "510")
    cfg = VisionConfig.from_env()
    _, transport, _ = provider_transport(asset, config=cfg)
    assert [call[1]["timeout"] for call in transport.calls] == [90, 510]
    provider = OllamaVisionProvider(config=cfg, timeout=75)
    assert (provider.config.timeout, provider.config.normalizer_timeout) == (75, 510)


@pytest.mark.parametrize("value", ["0", "-1", "invalid", "inf", "nan"])
def test_invalid_normalizer_timeout_is_rejected(monkeypatch, value):
    monkeypatch.setenv("ARCHITECTOS_VISION_NORMALIZER_TIMEOUT", value)
    with pytest.raises(ValueError):
        VisionConfig.from_env()


@pytest.mark.parametrize("field", ["timeout", "normalizer_timeout"])
def test_timeout_configuration_changes_both_cache_keys(asset, field):
    cfg = VisionConfig.from_env()
    first = OllamaVisionProvider(config=cfg)
    changed = OllamaVisionProvider(config=replace(cfg, **{field: getattr(cfg, field) + 1}))
    assert first.cache_identity() != changed.cache_identity()
    assert first._cache_key(asset) != changed._cache_key(asset)


def test_normalizer_timeout_failure_does_not_retry_or_lose_raw(asset):
    import requests
    provider, transport, result = provider_transport(
        asset, normalizer_reply=requests.exceptions.ReadTimeout("synthetic timeout"))
    assert len(transport.calls) == 2
    assert result["raw_observer"]["raw_text"] == "bed"
    assert result["normalization"]["status"] == "FAILED"
    assert "ReadTimeout" in result["normalization"]["error"]
    assert not provider._raw_cache


@pytest.mark.parametrize("raw,quote,expected,reason", [
    ("Window openings are visible", "Window openings", "Window openings", "exact"),
    ("Window openings are visible", "window openings", "Window openings", "canonical"),
    ("A non\u2011bearing partition", "non-bearing", "non\u2011bearing", "canonical"),
    ("A non\u2010bearing partition", "NON-BEARING", "non\u2010bearing", "canonical"),
    ("Straße visible", "STRASSE", "Straße", "canonical"),
    ("ß", "s", None, "no_match"),
    ("Window openings\nWINDOW OPENINGS", "window openings", None, "ambiguous_canonical_match"),
    ("AAA", "aa", None, "ambiguous_canonical_match"),
    ("window openings\nWindow openings", "window openings", "window openings", "exact"),
    ("wall visible", "door visible", None, "no_match"),
    ("axis 4", "axis 5", None, "no_match"),
    ("dimension 6.25 m", "dimension 6.35 m", None, "no_match"),
    ("level \u22120.40", "level -0.40", None, "no_match"),
    ("wall  visible", "wall visible", None, "no_match"),
])
def test_source_resolution_exact_raw_spans(raw, quote, expected, reason):
    resolved, method = resolve_source_quote(quote, raw)
    assert (resolved, method) == (expected, reason)
    if resolved is not None:
        assert resolved in raw


def test_per_claim_rejections_preserve_other_categories_and_diagnostics(asset):
    raw, data = rich_observation()
    expected_count = len(list(iter_claims(data)))
    data["drawing_type"] = claim("unreported drawing", kind="drawing")
    data["axes"].append(claim("axis 5", kind="axis"))
    data["furniture"].append(claim("invented word", quote="a rectangular table"))
    data["openings"]["windows"].append(claim("window openings", kind="window"))
    raw += "\nWindow openings\nWINDOW OPENINGS"
    _, _, result = provider_transport(asset, raw=raw, normalized=data)
    norm = result["normalization"]
    assert norm["status"] == "NORMALIZED"
    assert norm["accepted_claim_count"] == expected_count - 1
    assert norm["rejected_claim_count"] == 4
    failures = norm["source_resolution_failures"]
    assert {f["category"] for f in failures} == {"drawing_type", "axes", "furniture", "openings.windows"}
    assert {f["reason"] for f in failures} == {"no_match", "ambiguous_canonical_match"}
    assert any(f["field"] == "text" for f in failures)
    assert all(f["claim"]["source_quote"] for f in failures)
    assert result["raw_observer"]["raw_text"] == raw
    understanding = build_understanding(result)
    assert len(understanding["provider_candidates"]) == expected_count - 1
    assert understanding["observed"] == []
    assert not understanding["grounded_provider_evidence"]
    assert understanding["visual_observer_bridge"]["normalization"]["source_resolution_failures"] == failures


def test_one_unsupported_quote_does_not_discard_many_valid_claims(asset):
    data = structured()
    phrases = []
    for category in ("observed_elements", "walls", "furniture", "fixtures"):
        for index in range(MAX_ITEMS):
            phrase = category + " observation " + str(index)
            phrases.append(phrase)
            data[category].append(claim(phrase, kind="generic"))
    data["axes"] = [claim("unreported axis", kind="axis")]
    raw = "\n".join(phrases)
    _, _, result = provider_transport(asset, raw=raw, normalized=data)
    norm = result["normalization"]
    assert norm["accepted_claim_count"] == 4 * MAX_ITEMS
    assert norm["rejected_claim_count"] == 1
    assert len(provider_candidates(norm, raw)) == 4 * MAX_ITEMS


def test_canonical_quote_and_claim_text_both_use_raw_characters(asset):
    data = structured()
    data["openings"]["windows"] = [claim("window openings", kind="window")]
    raw = "Window openings are visible"
    _, _, result = provider_transport(asset, raw=raw, normalized=data)
    norm = result["normalization"]
    accepted = norm["structured"]["openings"]["windows"][0]
    assert accepted["text"] == accepted["source_quote"] == "Window openings"
    assert norm["source_resolutions"][0]["claim"]["source_quote"] == "window openings"
    assert norm["accepted_claim_count"] == 1 and norm["rejected_claim_count"] == 0
    candidates = provider_candidates(norm, raw)
    assert candidates[0]["source_quote"] == "Window openings"
    assert candidates[0]["state"] == "PROVIDER_CANDIDATE" and not candidates[0]["grounded"]


def test_candidate_boundary_records_rejected_claims_without_discarding_valid_claims():
    data = structured()
    data["furniture"] = [claim(), claim("invented sofa", kind="sofa")]
    norm = bridge(data)["normalization"]
    candidates = provider_candidates(norm, "bed")
    assert [c["text"] for c in candidates] == ["bed"]
    assert norm["candidate_source_validation"]["rejected_claim_count"] == 1
    assert norm["candidate_source_validation"]["source_resolution_failures"][0]["reason"] == "no_match"


@pytest.mark.parametrize("field,length", [("text", 90), ("source_quote", 130)])
def test_expanded_exact_raw_bounds_reject_only_the_affected_claim(asset, field, length):
    data = structured()
    expanded = claim("ß" * length, kind="text")
    if field == "source_quote":
        expanded["text"] = "ss"
    data["furniture"] = [claim(), expanded]
    raw = "bed\n" + "ss" * length
    _, _, result = provider_transport(asset, raw=raw, normalized=data)
    norm = result["normalization"]
    assert norm["accepted_claim_count"] == norm["rejected_claim_count"] == 1
    assert norm["source_resolution_failures"][0]["reason"] == "resolved_claim_bounds"
    assert [c["text"] for c in provider_candidates(norm, raw)] == ["bed"]


@pytest.mark.parametrize("phrase,certainty,category,kind", [
    ("bed visible", "ASSERTED", "furniture", "bed"),
    ("window openings are visible", "ASSERTED", "observed_elements", "window"),
    ("possibly a stair", "AMBIGUOUS", "vertical_circulation", "stair"),
    ("could be a stair or ramp", "AMBIGUOUS", "vertical_circulation", "stair"),
    ("text unreadable", "UNKNOWN", "ocr_unreadable", "text"),
    ("orientation cannot be determined", "UNKNOWN", "orientation", "orientation"),
])
def test_certainty_prompt_contract_and_controlled_transport(asset, phrase, certainty, category, kind):
    # Deterministic prompt/schema + mocked response contract, NOT live inference.
    assert json.dumps(phrase) + " => " + certainty in NORMALIZER_PROMPT
    guidance = CLAIM_SCHEMA["properties"]["certainty"]["description"]
    assert "UNKNOWN must NOT mean merely" in guidance
    assert "Do not strengthen hedges" in guidance
    data = structured()
    data[category] = [claim(phrase, kind=kind, certainty=certainty)]
    _, transport, result = provider_transport(asset, raw=phrase, normalized=data)
    assert transport.calls[1][1]["json"]["system"] == NORMALIZER_PROMPT
    candidates = provider_candidates(result["normalization"], phrase)
    assert candidates[0]["certainty"] == certainty
    assert candidates[0]["state"] == "PROVIDER_CANDIDATE" and candidates[0]["grounded"] is False
    verified = verify_candidates(candidates, None)
    assert verified[0]["state"] == ("AMBIGUOUS" if certainty == "AMBIGUOUS" else "UNVERIFIED")
    assert verified[0]["grounded"] is False


def test_asserted_atomic_presence_still_requires_independent_local_evidence(asset):
    data = structured()
    data["furniture"] = [claim("bed", quote="bed visible", certainty="ASSERTED")]
    _, _, result = provider_transport(asset, raw="bed visible", normalized=data)
    candidates = provider_candidates(result["normalization"], "bed visible")
    assert candidates[0]["state"] == "PROVIDER_CANDIDATE" and not candidates[0]["grounded"]
    assert verify_candidates(candidates, None)[0]["state"] == "UNVERIFIED"
    assert verify_candidates(candidates, local())[0]["state"] == "CONFIRMED"
    assert build_understanding(result)["observed"] == []


@pytest.mark.parametrize("size,resized", [
    ((320, 240), False),
    ((2400, 3600), False),  # a detailed sheet below both default bounds
    ((1800, 5400), True),
    ((5400, 1800), True),
    ((3900, 3900), True),  # pixel bound applies even below the long-edge bound
])
def test_observer_bounding_preserves_whole_image_and_original(tmp_path, size, resized):
    path = tmp_path / "synthetic-sheet.png"
    colors = ("red", "lime", "blue", "black")
    with Image.new("RGB", size, "white") as image:
        draw = ImageDraw.Draw(image)
        w, h = size
        mw, mh = w // 20, h // 20
        for box, color in zip(((0, 0, mw, mh), (w - mw, 0, w, mh),
                               (0, h - mh, mw, h), (w - mw, h - mh, w, h)), colors):
            draw.rectangle(box, fill=color)
        image.save(path)
    original, stat = path.read_bytes(), path.stat()
    asset_record = {"path": str(path), "image_id": "synthetic-sheet"}
    record_before = copy.deepcopy(asset_record)
    provider, transport, result = provider_transport(asset_record)
    sent = base64.b64decode(transport.calls[0][1]["json"]["images"][0])
    cfg = provider.config
    with Image.open(BytesIO(sent)) as bounded:
        bw, bh = bounded.size
        assert bw <= size[0] and bh <= size[1]
        assert max(bw, bh) <= cfg.observer_max_long_edge
        assert bw * bh <= cfg.observer_max_pixels
        # Uniform scaling, allowing at most one pixel of integer rounding.
        assert abs(bw - size[0] * bh / size[1]) <= max(1, size[0] / size[1])
        assert [bounded.getpixel(point) for point in
                ((0, 0), (bw - 1, 0), (0, bh - 1), (bw - 1, bh - 1))] == [
                    (255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 0, 0)]
    diagnostics = result["raw_observer"]["diagnostics"]
    assert (diagnostics["original_width"], diagnostics["original_height"]) == size
    assert (diagnostics["observer_input_width"], diagnostics["observer_input_height"]) == (bw, bh)
    assert diagnostics["observer_image_resized"] is resized
    assert diagnostics["image_preparation_status"] == "READY"
    assert diagnostics["observer_context"] == cfg.observer_ctx
    assert diagnostics["original_source_sha256"] == hashlib.sha256(original).hexdigest()
    assert provider._cache_key(str(path))[0] == diagnostics["original_source_sha256"]
    assert path.read_bytes() == original and path.stat().st_mtime_ns == stat.st_mtime_ns
    assert asset_record == record_before
    assert set(tmp_path.iterdir()) == {path}
    if not resized:
        assert sent == original


def test_observer_context_and_bounds_environment_configuration(monkeypatch, asset):
    for name in ("CTX", "MAX_LONG_EDGE", "MAX_PIXELS"):
        monkeypatch.delenv("ARCHITECTOS_VISION_OBSERVER_" + name, raising=False)
    before = get_vision_provider()
    assert (before.config.observer_ctx, before.config.observer_max_long_edge,
            before.config.observer_max_pixels) == (32768, 4096, 12000000)
    monkeypatch.setenv("ARCHITECTOS_VISION_OBSERVER_CTX", "16384")
    monkeypatch.setenv("ARCHITECTOS_VISION_NORMALIZER_CTX", "24576")
    monkeypatch.setenv("ARCHITECTOS_VISION_OBSERVER_MAX_LONG_EDGE", "100")
    monkeypatch.setenv("ARCHITECTOS_VISION_OBSERVER_MAX_PIXELS", "5000")
    after = get_vision_provider()
    assert before is not after
    _, transport, result = provider_transport(asset, config=after.config)
    observer, normalizer = [call[1]["json"] for call in transport.calls]
    assert observer["options"]["num_ctx"] == 16384
    assert normalizer["options"]["num_ctx"] == 24576
    assert "images" not in normalizer
    d = result["raw_observer"]["diagnostics"]
    assert max(d["observer_input_width"], d["observer_input_height"]) <= 100
    assert d["observer_input_width"] * d["observer_input_height"] <= 5000
    monkeypatch.setenv("ARCHITECTOS_VISION_NORMALIZER_CTX", "8192")
    assert VisionConfig.from_env().observer_ctx == 16384
    monkeypatch.setenv("ARCHITECTOS_VISION_OBSERVER_CTX", "32768")
    assert VisionConfig.from_env().normalizer_ctx == 8192


@pytest.mark.parametrize("setting", ["CTX", "MAX_LONG_EDGE", "MAX_PIXELS"])
@pytest.mark.parametrize("value", ["0", "-1", "invalid", "inf", "nan"])
def test_invalid_observer_context_or_bounds_rejected(monkeypatch, setting, value):
    monkeypatch.setenv("ARCHITECTOS_VISION_OBSERVER_" + setting, value)
    with pytest.raises(ValueError):
        VisionConfig.from_env()


@pytest.mark.parametrize("size", [(1, 300), (300, 1)])
def test_observer_extremely_thin_image_respects_pixel_budget(tmp_path, size):
    path = tmp_path / "strip.png"
    with Image.new("RGB", size) as image:
        image.save(path)
    cfg = replace(VisionConfig.from_env(), observer_max_pixels=10)
    _, transport, _ = provider_transport(str(path), config=cfg)
    with Image.open(BytesIO(base64.b64decode(transport.calls[0][1]["json"]["images"][0]))) as bounded:
        assert bounded.width * bounded.height <= 10
        assert min(bounded.size) == 1


def test_session_local_reader_keeps_original_full_resolution(monkeypatch, tmp_path):
    from core.vision import image_session_v1 as session
    from core.vision.image_registry_v1 import ImageRegistryV1
    path = tmp_path / "local-full-resolution.png"
    size = (1500, 2100)
    with Image.new("RGB", size, "white") as image:
        image.save(path)
    original = path.read_bytes()
    registry = ImageRegistryV1()
    stored = []
    registry.attach_persistence(lambda key: stored.append(registry.snapshot(key)))
    record = registry.register("bounded-session", path=str(path), source_type="uploaded")
    cfg = replace(VisionConfig.from_env(), observer_max_long_edge=1024)
    transport = Transport([Response({"response": "bed", "done": True, "eval_count": 7}),
                           Response({"response": json.dumps(structured()), "done": True})])
    provider = OllamaVisionProvider(config=cfg, session=transport)
    monkeypatch.setattr(provider, "is_available", lambda: True)
    seen = []
    local_result = local()
    def read_original(received_path):
        seen.append(received_path)
        assert received_path == str(path)
        with Image.open(received_path) as image:
            assert image.size == size
        return local_result
    monkeypatch.setattr(session, "image_registry", registry)
    monkeypatch.setattr(session, "provider", lambda: provider)
    monkeypatch.setattr(session, "read_local_plan", read_original)
    understanding = session.analyze_record("bounded-session", record["image_id"])
    assert seen == [str(path)]
    assert understanding["local_plan_reading"] == local_result
    with Image.open(BytesIO(base64.b64decode(transport.calls[0][1]["json"]["images"][0]))) as bounded:
        assert max(bounded.size) == 1024
    raw = understanding["visual_observer_bridge"]["raw_observer"]
    assert raw["diagnostics"]["original_width"] == size[0]
    assert raw["diagnostics"]["observer_image_resized"] is True
    assert raw["generation_metadata"]["eval_count"] == 7
    assert raw["raw_text"] == "bed" and raw["raw_truncated"] is False
    assert understanding["observed"] == [] and understanding["provider_candidates"] == []
    assert stored[-1][1][0]["analysis"] == understanding
    registered = registry.get("bounded-session", record["image_id"])
    for key in record:
        if key not in ("analysis", "analysis_status"):
            assert registered[key] == record[key]
    assert path.read_bytes() == original
    assert set(tmp_path.iterdir()) == {path}


def test_corrupt_image_fails_truthfully_without_observer_or_normalizer(tmp_path):
    path = tmp_path / "corrupt.png"
    path.write_bytes(b"not an image")
    transport = Transport([])
    provider = OllamaVisionProvider(session=transport)
    result = provider.analyze(str(path))
    raw = result["raw_observer"]
    assert raw["generation_status"] == "FAILED" and raw["raw_text"] == ""
    assert "UnidentifiedImageError" in raw["error"]
    assert raw["diagnostics"]["image_preparation_status"] == "FAILED"
    assert raw["diagnostics"]["original_width"] is None
    assert raw["diagnostics"]["observer_image_resized"] is None
    assert raw["diagnostics"]["original_source_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["normalization"]["status"] == "NOT_RUN"
    assert not transport.calls and not provider._raw_cache


@pytest.mark.parametrize("failure", [None, "encode", "transport"])
def test_observer_memory_resources_closed_on_success_and_failure(monkeypatch, asset, failure):
    from core.vision import vision_provider_ollama_v1 as module
    from pathlib import Path
    buffers = []
    def tracked_buffer(*args):
        buffer = BytesIO(*args)
        buffers.append(buffer)
        return buffer
    monkeypatch.setattr(module, "BytesIO", tracked_buffer)
    if failure == "encode":
        def fail_save(*args, **kwargs):
            raise OSError("synthetic encoder failure")
        monkeypatch.setattr(Image.Image, "save", fail_save)
    cfg = replace(VisionConfig.from_env(), observer_max_long_edge=80)
    replies = [RuntimeError("synthetic transport failure")] if failure == "transport" else [
        Response({"response": "bed", "done": True}),
        Response({"response": json.dumps(structured()), "done": True})]
    transport = Transport(replies)
    provider = OllamaVisionProvider(config=cfg, session=transport)
    before = Path(asset).read_bytes()
    result = provider.analyze(asset)
    assert buffers and all(buffer.closed for buffer in buffers)
    assert set(Path(asset).parent.iterdir()) == {Path(asset)}
    assert Path(asset).read_bytes() == before
    raw = result["raw_observer"]
    assert raw["generation_status"] == ("FAILED" if failure else "COMPLETE")
    assert raw["diagnostics"]["original_width"] == 160
    assert raw["diagnostics"]["image_preparation_status"] == ("FAILED" if failure == "encode" else "READY")
    if failure:
        assert result["normalization"]["status"] == "NOT_RUN"
        assert not provider._raw_cache
        assert len(transport.calls) == (1 if failure == "transport" else 0)
