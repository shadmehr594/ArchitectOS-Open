"""Real A/B contrast plus independent symbols and evidence-boundary attacks."""

import os
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from core.vision.architectural_vision_interpreter_v1 import (
    _plan_walls,
    interpret_architectural_vision,
)
from core.vision.image_understanding_v1 import (
    EVIDENCE_PIPELINE_VERSION,
    build_understanding,
)
from core.vision.local_plan_reader_v1 import (
    _plan_bbox,
    _read_png,
    _read_raster,
    read_local_plan,
)
from core.vision.local_plan_symbols_v1 import analyze_plan_symbols, grounded_plan_items
from core.vision.vision_observation_mode_v1 import build_observation
from core.vision.vision_report_v1 import render_vision_report

FIXTURES = Path(__file__).parent / "fixtures" / "vision" / "furnished_plan_v1"
A = Path(os.environ.get("ARCHITECTOS_PLAN_A", str(FIXTURES / "unfurnished.png")))
B = Path(os.environ.get("ARCHITECTOS_PLAN_B", str(FIXTURES / "furnished.jpg")))
requires_a = pytest.mark.skipif(
    not A.is_file(), reason="Supply private Image A with ARCHITECTOS_PLAN_A"
)
requires_b = pytest.mark.skipif(
    not B.is_file(), reason="Supply private Image B with ARCHITECTOS_PLAN_B"
)


@pytest.fixture(scope="module")
def readings():
    if not A.is_file() or not B.is_file():
        pytest.skip(
            "Real A/B images are private; set ARCHITECTOS_PLAN_A and ARCHITECTOS_PLAN_B"
        )
    return read_local_plan(A), read_local_plan(B)


def interpret(local, provider_tokens=("bed", "sofa", "table", "wardrobe", "desk")):
    raw = {
        "image_type": "floor_plan_or_sketch",
        "confidence": "HIGH",
        "observed": ["floor plan", "bed sofa table wardrobe visible"],
        "architectural_elements": list(provider_tokens),
        "furniture_elements": list(provider_tokens),
        "text_labels_if_visible": ["ساونا", "آبدارخانه", "سردر"],
        "local_plan_reading": local,
    }
    understanding = build_understanding(raw, provider="adversarial-stub", model="stub")
    return understanding, interpret_architectural_vision(understanding)


@requires_a
def test_png_decoder_is_unchanged():
    assert np.array_equal(_read_raster(A), _read_png(A))


@pytest.mark.parametrize("suffix", [".jpg", ".jpeg", ".bin"])
@requires_b
def test_jpeg_signature_decode_not_extension(tmp_path, suffix):
    destination = tmp_path / ("sheet" + suffix)
    destination.write_bytes(B.read_bytes())
    raster = _read_raster(destination)
    assert raster.dtype == np.uint8 and raster.ndim == 2
    assert np.array_equal(raster, _read_raster(B))


def test_A_unfurnished_rejects_provider_furniture(readings):
    local, _ = readings
    understanding, result = interpret(local)
    plan = result["plan_reading"]
    assert local["symbol_analysis_status"] == "analyzed"
    assert local["furniture_observed"] is False
    assert local["furniture_evidence"] == []
    assert plan["furniture"] == [] and not plan["furniture_observed"]
    assert plan["inferred_functions"] == []
    assert not build_observation(understanding)["grounded_furniture_evidence"]
    assert not any(
        e["name"] in ("sleeping_element", "seating", "desk")
        for e in build_observation(understanding)["elements"]
    )


def test_B_furniture_fixtures_functions_and_concise_report(readings):
    _, local = readings
    understanding, result = interpret(local)
    plan = result["plan_reading"]
    items = plan["furniture"]
    classes = {item["class"] for item in items}
    assert {
        "bed",
        "sofa",
        "dining_surface",
        "chair",
        "kitchen_counter",
        "kitchen_sink_arrangement",
        "sanitary_fixture",
    } <= classes
    assert "storage_cabinet" not in classes  # provider wardrobe cannot upgrade itself
    assert sum(item["class"] == "bed" for item in items) >= 2
    assert {f["space"] for f in plan["inferred_functions"]} >= {
        "bedroom",
        "living room",
        "dining",
        "kitchen",
        "bathroom",
    }
    for item in items:
        assert len(item["bbox_pixels"]) == 4
        assert item["confidence"] == "MEDIUM"
        assert item["source"] == "local_raster_symbol_topology"
        assert item["provider_independent"] is True
        assert len(item["corroboration"]) >= 3
        assert len(item["raster_patch_sha256"]) == 64
    assert plan["wall_reading"]["partition"]["room_count"] is None
    assert plan["enclosure_geometry"]["multiple_spaces"] is True
    assert local["labels"] == []  # sofa texture is not a terrace label
    assert (
        plan["named_spaces"] == []
    )  # local empty transcription cannot resurrect provider labels
    assert all(e["status"] == "provider_only" for e in plan["provider_label_claims"])

    report = render_vision_report(result, "fa")
    assert len(report) < 900 and len(report.split("\n\n")) <= 6
    for word in ("مسکونی مبله", "خواب", "نشیمن", "آشپزخانه", "سرویس", "غذاخوری", "تخت"):
        assert word in report
    assert "دو فضای بسته" not in report and "تعداد دقیق" in report
    assert all(
        word not in report for word in ("OCR", "provider", "bbox", "confidence", "تراس")
    )
    observation = build_observation(understanding)
    assert all(
        e["confidence"] == "medium"
        for e in observation["elements"]
        if e["source_field"] == "local_plan_reading.furniture_evidence"
    )
    assert observation["space_type"] is None and observation["possible_function"] == []
    assert len(observation["grounded_furniture_evidence"]) == len(items)


def test_no_region_no_function_even_with_real_furniture(readings):
    local = deepcopy(readings[1])
    local["enclosure_geometry"]["regions"] = []
    _, result = interpret(local)
    assert result["plan_reading"]["furniture"]
    assert result["plan_reading"]["geometry_spaces"] == []
    assert result["plan_reading"]["inferred_functions"] == []


@pytest.mark.parametrize(
    "mutation", ["bbox", "source", "confidence", "corroboration", "hash", "function"]
)
def test_evidence_contract_cannot_promote_bad_items(readings, mutation):
    local = deepcopy(readings[1])
    item = deepcopy(next(i for i in local["furniture_evidence"] if i["class"] == "bed"))
    local["furniture_evidence"] = [item]
    if mutation == "bbox":
        item["bbox_pixels"] = [-1, 0, 5, 5]
    elif mutation == "source":
        item["source"] = "provider_only"
    elif mutation == "confidence":
        item["confidence"] = "LOW"
    elif mutation == "corroboration":
        item["corroboration"] = ["bed token"]
    elif mutation == "hash":
        item.pop("raster_patch_sha256")
    else:
        item["supported_function"] = "bathroom"
    validated = grounded_plan_items(local)
    if mutation == "function":
        assert validated[0]["supported_function"] == "bedroom"
    else:
        assert validated == []


def test_enclosure_count_cannot_be_defined_by_labels():
    elements = [{"kind": ["wall"], "evidence_phrase": "wall outlines"}]
    for count in (0, 2, 50):
        wall = _plan_walls(elements, [{"space": "bedroom"}] * count)
        assert wall["partition"]["room_count"] is None
        assert wall["partition"]["multiple_spaces"] is False
    geometry = {
        "count": None,
        "count_status": "uncertain",
        "multiple_spaces": True,
        "candidate_count_range": [4, 6],
        "regions": [{"bbox_pixels": [0, 0, 10, 10]}],
    }
    for count in (0, 2, 50):
        assert _plan_walls(elements, [{}] * count, geometry)["partition"][
            "candidate_count_range"
        ] == [4, 6]


def schematic(furnished):
    image = Image.new("L", (500, 500), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((50, 50, 450, 450), outline=0, width=5)
    if furnished:
        draw.rectangle((95, 90, 155, 200), outline=0, width=1)
        draw.rectangle((98, 123, 152, 197), outline=0, width=1)
        draw.rectangle((101, 95, 121, 116), outline=0, width=1)
        draw.rectangle((128, 95, 148, 116), outline=0, width=1)
        draw.rectangle((240, 240, 332, 272), outline=0, width=1)
        for x in (250, 274, 298):
            draw.rectangle((x, 245, x + 20, 265), outline=0, width=1)
    else:
        # Empty dashed annotation + stair rows + text are not furniture.
        for x in range(100, 160, 10):
            draw.line((x, 100, x + 5, 100), fill=0)
        for y in range(250, 340, 10):
            draw.line((250, y, 300, y), fill=0)
        draw.text((100, 140), "BED SOFA TABLE", fill=0)
    return np.asarray(image)


@pytest.mark.parametrize("turns", [0, 1, 2, 3])
def test_independent_outline_symbols_not_acceptance_hardcoding(turns):
    gray = np.ascontiguousarray(np.rot90(schematic(True), turns))
    items = analyze_plan_symbols(gray, _plan_bbox(gray))["furniture_evidence"]
    assert {"bed", "sofa"} <= {item["class"] for item in items}


def test_empty_annotations_and_stair_marks_are_not_furniture():
    gray = schematic(False)
    assert analyze_plan_symbols(gray, _plan_bbox(gray))["furniture_evidence"] == []


@requires_b
def test_translation_of_acceptance_image_retains_local_evidence():
    gray = _read_raster(B)
    shifted = np.pad(gray, ((25, 40), (30, 50)), constant_values=255)
    items = analyze_plan_symbols(shifted, _plan_bbox(shifted))["furniture_evidence"]
    assert {"bed", "sofa", "sanitary_fixture", "kitchen_counter", "dining_surface"} <= {
        i["class"] for i in items
    }
    assert all(i["bbox_pixels"][0] >= 30 and i["bbox_pixels"][1] >= 25 for i in items)


@requires_b
def test_ocr_unavailable_does_not_suppress_symbol_evidence(tmp_path):
    local = read_local_plan(B, tessdata_path=tmp_path)
    assert local["ocr_status"] == "unavailable"
    assert local["furniture_observed"] is True
    assert local["status"] == "grounded"
    assert {i["class"] for i in local["furniture_evidence"]} >= {
        "bed",
        "sanitary_fixture",
    }


def test_raw_provider_only_drawing_does_not_create_function():
    understanding = build_understanding(
        {
            "image_type": "floor_plan_or_sketch",
            "observed": ["bed sofa table visible"],
            "furniture_elements": ["bed", "sofa", "table"],
        },
        provider="stub",
        model="stub",
    )
    result = interpret_architectural_vision(understanding)
    assert not result["plan_reading"]["inferred_functions"]
    assert not result["plan_reading"]["furniture_observed"]


def test_provider_words_cannot_change_B_local_items(readings):
    _, first = interpret(readings[1], ("bed", "sofa", "table", "wardrobe", "sauna"))
    _, second = interpret(readings[1], ())
    assert first["plan_reading"]["furniture"] == second["plan_reading"]["furniture"]
    assert (
        first["plan_reading"]["inferred_functions"]
        == second["plan_reading"]["inferred_functions"]
    )


def test_old_hardcoded_false_cache_is_stale():
    from core.vision.image_session_v1 import _cache_reuse_reason
    from core.vision.local_plan_reader_v1 import local_ocr_environment

    record = {"analysis_status": "ANALYZED_WITH_UNCERTAINTY"}
    old = {
        "evidence_pipeline": "local-plan-reading-v1",
        "local_ocr_environment": local_ocr_environment(),
    }
    assert _cache_reuse_reason(record, old) == "stale_evidence_pipeline"
    current = {
        "evidence_pipeline": EVIDENCE_PIPELINE_VERSION,
        "local_ocr_environment": local_ocr_environment(),
    }
    assert _cache_reuse_reason(record, current) == "current"


def test_no_frozen_subsystem_is_invoked(readings):
    # All exercised entry points are offline; only the existing interpreter's
    # pure projections run. Provider stub words never trigger a render/design.
    _understanding, result = interpret(readings[1])
    observation = result["architectural_observation"]
    assert observation["design_generated"] is False
    assert observation["render_requested"] is False
    assert observation["comfy_invoked"] is False
