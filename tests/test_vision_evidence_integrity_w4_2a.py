"""Evidence/state integrity, independent of acceptance images and providers."""

import copy
from types import SimpleNamespace

import numpy as np
import pytest

from core.vision.architectural_function_evidence_v1 import (
    OPENING_ACCESS, build_architectural_function_evidence,
)
from core.vision.architectural_vision_interpreter_v1 import (
    build_plan_reading, interpret_architectural_vision,
)
from core.vision.image_session_v1 import _local_plan_raw
from core.vision.image_understanding_v1 import build_understanding
from core.vision.local_plan_elements_v1 import merge_local_openings
from core.vision.local_plan_reader_v1 import _perimeter_windows


def _local(**changes):
    result = {
        "status": "grounded", "image_size": {"width": 320, "height": 240},
        "plan_bbox_pixels": [20, 20, 300, 220],
        "labels": [], "openings": [], "furniture_evidence": [],
        "element_evidence": [], "furniture_observed": None,
        "symbol_analysis_status": "unavailable",
        "element_analysis_status": "unavailable", "ocr_status": "unavailable",
        "symbol_reason": "symbol backend unavailable",
        "ocr_reason": "OCR backend unavailable",
        "element_reason": "element backend unavailable",
        "enclosure_geometry": {"count": None, "count_status": "unknown", "regions": []},
    }
    result.update(changes)
    return result


@pytest.mark.parametrize("local_status", ["grounded", "no_grounded_evidence", "unavailable"])
@pytest.mark.parametrize("symbol_status,value", [
    ("unavailable", None), ("unknown", None), ("not_applicable", None),
    ("analyzed", False), ("analyzed", True),
])
def test_furniture_keeps_nullable_state(local_status, symbol_status, value):
    local = _local(status=local_status, symbol_analysis_status=symbol_status,
                   furniture_observed=value)
    plan = build_plan_reading({"local_plan_reading": local})
    assert plan["furniture_observed"] is value
    assert plan["symbol_analysis_status"] == symbol_status


def _opening_items(local):
    plan = build_plan_reading({"local_plan_reading": local})
    evidence = build_architectural_function_evidence(plan)
    return [item for item in evidence["evidence_items"] if item["evidence_type"] == OPENING_ACCESS]


@pytest.fixture
def perimeter():
    # Generated drawing: thick boundary with one thin window interruption.
    gray = np.full((240, 320), 255, dtype=np.uint8)
    gray[18:25, 20:300] = 0
    gray[215:222, 20:300] = 0
    gray[18:25, 110:160] = 255
    gray[21, 110:160] = 0
    windows = _perimeter_windows(gray, [20, 20, 300, 220])
    assert windows
    return gray, windows


def test_perimeter_producer_survives_unavailable_element_reader(perimeter):
    _, windows = perimeter
    local = _local(openings=windows)
    items = _opening_items(local)
    assert len(items) == len(windows)
    assert {item["producer"] for item in items} == {
        "core.vision.local_plan_reader_v1._perimeter_windows"
    }


@pytest.mark.parametrize("producer", ["custom.reader.detect", None])
def test_opening_producer_is_preserved_or_explicitly_unknown(perimeter, producer):
    _, windows = perimeter
    for window in windows:
        window["producer"] = producer
    assert {item["producer"] for item in _opening_items(_local(openings=windows))} == {
        producer or "UNKNOWN"
    }


def test_legacy_opening_wrapper_does_not_change_producer(perimeter):
    gray, windows = perimeter
    openings, _ = merge_local_openings(gray, windows, [])
    items = _opening_items(_local(openings=openings, element_analysis_status="analyzed"))
    assert items
    assert all(item["producer"] == windows[0]["producer"] for item in items)


@pytest.mark.parametrize("ground", [False, True])
@pytest.mark.parametrize("kind,text", [
    ("RUNTIME_STATUS", "floor plan raster available for local reading"),
    ("SYSTEM_STATUS", "floor plane window and wall processing unavailable"),
    ("SYNTHETIC_DESCRIPTION", "horizontal floor surface preprocessing completed"),
])
def test_runtime_text_never_becomes_visual_evidence(kind, text, ground):
    raw = _local_plan_raw(_local())
    raw["runtime_status"][0].update(evidence_type=kind, text=text)
    understanding = build_understanding(raw)
    assert understanding["observed"] == []
    assert understanding["runtime_status"] == raw["runtime_status"]
    interpretation = interpret_architectural_vision(understanding, ground=ground)
    observation = interpretation["architectural_observation"]
    assert observation["architectural_elements"] == []
    assert not any("floor" in phrase for phrase in interpretation["observed_elements"])


def test_genuine_visual_floor_is_retained():
    understanding = build_understanding({
        "image_type": "architectural_render_or_photo", "confidence": "HIGH",
        "observed": ["horizontal floor plane visible"],
    })
    result = interpret_architectural_vision(understanding)
    assert any("floor" in entry["kind"] for entry in result["architectural_observation"]["architectural_elements"])
    assert "horizontal floor plane visible" in result["observed_elements"]


@pytest.mark.parametrize("failure,expected", [
    ("unavailable", "PROVIDER_UNAVAILABLE"),
    ("exception", "FAILED"), ("malformed", "FAILED"),
])
def test_failed_provider_preserves_local_diagnostics(monkeypatch, tmp_path, failure, expected):
    from core.vision import image_session_v1 as session

    path = tmp_path / "raster.png"
    path.write_bytes(b"local-reader-is-stubbed")
    local = _local(status="no_grounded_evidence")
    original = copy.deepcopy(local)
    stored = []

    def analyze(payload):
        if failure == "exception":
            raise RuntimeError("test provider unavailable")
        return "non-structured result"

    provider = SimpleNamespace(name="offline-test", model="none", supports_grounding=False,
                               is_available=lambda: failure != "unavailable", analyze=analyze)
    monkeypatch.setattr(session, "provider", lambda: provider)
    monkeypatch.setattr(session, "read_local_plan", lambda _: local)
    monkeypatch.setattr(session.image_registry, "get", lambda *_: {
        "path": str(path), "source_type": "uploaded", "analysis_status": "pending",
    })
    monkeypatch.setattr(session.image_registry, "set_analysis", lambda *args: stored.append(args))
    result = session.analyze_record("session", "image")
    assert result["analysis_status"] == expected
    assert stored[-1][2] == result
    diagnostics = result["local_diagnostics"]
    for key in ("image_size", "plan_bbox_pixels", "symbol_reason", "ocr_reason", "element_reason"):
        assert diagnostics[key] == local[key]
    assert diagnostics["status"] == "no_grounded_evidence"
    assert diagnostics["evidence_state"] == "CAPABILITY_UNAVAILABLE"
    assert diagnostics["evidence_type"] == "RUNTIME_STATUS"
    assert "furniture_evidence" not in diagnostics
    assert "labels" not in diagnostics
    assert result["observed"] == result["inferred"] == result["architectural_elements"] == []
    interpretation = interpret_architectural_vision(result)
    assert any("capability unavailable" in text for text in interpretation["unknowns"])
    assert not any("sufficiently visible" in text for text in interpretation["unknowns"])
    assert local == original
    diagnostics["image_size"]["width"] = 1
    assert local == original


@pytest.mark.parametrize("status,capability,expected", [
    ("no_grounded_evidence", "analyzed", "IMAGE_EVIDENCE_INSUFFICIENT"),
    ("no_grounded_evidence", "unavailable", "CAPABILITY_UNAVAILABLE"),
    ("grounded", "unavailable", "LOCAL_EVIDENCE_PARTIAL"),
    ("no_grounded_evidence", "unknown", "UNKNOWN"),
])
def test_local_state_is_distinct_from_provider_state(status, capability, expected):
    local = _local(status=status, ocr_status=capability,
                   symbol_analysis_status=capability, element_analysis_status=capability)
    result = build_understanding(None, provider_error="offline", local_plan_reading=local)
    assert result["analysis_status"] == "PROVIDER_UNAVAILABLE"
    assert result["local_diagnostics"]["evidence_state"] == expected


def test_provider_failure_alone_makes_no_visibility_claim():
    result = interpret_architectural_vision(build_understanding(None, provider_error="offline"))
    assert any("provider unavailable" in text for text in result["unknowns"])
    assert not any("sufficiently visible" in text for text in result["unknowns"])


def test_real_raster_path_retains_unknown_when_backends_fail(monkeypatch):
    from core.vision import local_plan_reader_v1 as reader

    def unavailable(*args, **kwargs):
        raise RuntimeError("test backend unavailable")

    monkeypatch.setattr(reader, "_ocr_readings", unavailable)
    monkeypatch.setattr(reader, "analyze_plan_symbols", unavailable)
    gray = np.full((240, 320), 255, dtype=np.uint8)
    gray[20:25, 20:300] = gray[215:220, 20:300] = 0
    gray[20:220, 20:25] = gray[20:220, 295:300] = 0
    local = reader._read_plan_raster(gray)
    assert local["status"] == "no_grounded_evidence"
    assert local["furniture_observed"] is None
    assert local["symbol_analysis_status"] == "unavailable"
    plan = build_plan_reading({"local_plan_reading": local})
    assert plan["furniture_observed"] is None
    failed = build_understanding(None, provider_error="offline", local_plan_reading=local)
    assert failed["local_diagnostics"]["image_size"] == {"width": 320, "height": 240}
    assert failed["local_diagnostics"]["plan_bbox_pixels"] == local["plan_bbox_pixels"]
    assert failed["local_diagnostics"]["evidence_state"] == "CAPABILITY_UNAVAILABLE"


def test_pre_integrity_cache_is_not_reused():
    from core.vision.image_session_v1 import _cache_reuse_reason
    from core.vision.local_plan_reader_v1 import local_ocr_environment

    cached = {"evidence_pipeline": "multi-plan-sheet-v1-unfused-collection",
              "local_ocr_environment": local_ocr_environment()}
    assert _cache_reuse_reason({"analysis_status": "ANALYZED"}, cached) == "stale_evidence_pipeline"


def test_element_reader_records_its_own_producer(perimeter):
    from core.vision.local_plan_elements_v1 import _record

    gray, windows = perimeter
    element = _record(gray, "window", windows[0]["bbox_pixels"], ["test raster cue"])
    openings, _ = merge_local_openings(gray, [], [element])
    items = _opening_items(_local(openings=openings, element_analysis_status="analyzed"))
    assert items[0]["producer"] == "core.vision.local_plan_elements_v1._record"
