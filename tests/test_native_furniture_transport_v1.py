"""NATIVE-RESOLUTION FURNITURE TRANSPORT V1 — focused, image-independent tests.

`analyze_sheet` upscales every panel crop before the legacy reading so OCR and
wall geometry have a usable resolution. That resampling can change light symbol
strokes enough to lose furniture. These tests pin the narrow transport that
re-reads the furniture/fixture symbol families on the ORIGINAL panel crop and
remaps them into the panel-analysis frame.

Every fixture here is drawn synthetically. Nothing depends on the private
acceptance images, their filenames, or any fixed count from them.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from core.vision.local_plan_sheet_v1 import (
    _native_furniture_transport,
    analyze_sheet,
    build_sheet_plan_reading,
    detect_sheet,
    grounded_sheet_structure,
    native_box_to_panel,
    panel_box_to_native,
    panel_box_to_normalized,
    panel_box_to_sheet,
)
from core.vision.local_plan_symbols_v1 import (
    FUNCTIONS,
    analyze_furniture_symbols,
    grounded_plan_items,
)

PANEL_WIDTH, PANEL_HEIGHT = 260, 360


def _sleeping_symbol(draw, x, y, w=44, h=78, value=0):
    """Closed outline with a terminal pillow row — a common bed convention."""
    draw.rectangle((x, y, x + w, y + h), outline=value, width=1)
    pw, ph = int(w * 0.38), int(h * 0.13)
    draw.rectangle((x + 3, y + 5, x + 3 + pw, y + 5 + ph), outline=value, width=1)
    draw.rectangle((x + w - 3 - pw, y + 5, x + w - 3, y + 5 + ph), outline=value, width=1)


def _panel_image(furnished=False, alternative=False):
    """A small plan drawing; the optional sleeping symbol is drawn LIGHT."""
    im = Image.new("L", (PANEL_WIDTH, PANEL_HEIGHT), 255)
    d = ImageDraw.Draw(im)
    d.rectangle((30, 25, 230, 330), outline=0, width=4)
    if alternative:
        d.line((30, 210, 230, 210), fill=0, width=4)
        d.line((70, 25, 70, 330), fill=0, width=4)
        d.line((180, 25, 180, 330), fill=0, width=4)
    else:
        d.line((30, 115, 230, 115), fill=0, width=4)
        d.line((30, 185, 230, 185), fill=0, width=4)
        d.line((130, 25, 130, 185), fill=0, width=4)
    if furnished:
        # Grey 200: invisible to the 165/180 dark passes and to the 200-threshold
        # geometry descriptor, visible to the 210/220 light-line passes.
        # Placed in an unpartitioned area of each layout so no wall crosses it.
        _sleeping_symbol(d, *(95, 60) if alternative else (150, 210), value=200)
    return np.asarray(im)


def _two_panel_sheet(furnished=(True, True), alternative=(False, False)):
    sheet = np.full((420, 660), 255, np.uint8)
    for index, x in enumerate((20, 370)):
        sheet[20:380, x : x + PANEL_WIDTH] = _panel_image(
            furnished=furnished[index], alternative=alternative[index]
        )
    return sheet


_STUB_REGION = {
    "region_id": "r1",
    "bbox_pixels": [40, 30, 220, 320],
    "pixel_area": 36000,
    "centroid_pixels": [130.0, 175.0],
    "source": "local_raster_wall_boundaries",
    "status": "enclosed_region_candidate",
    "confidence": "MEDIUM",
    "corroboration": [
        "thick_wall_boundaries",
        "bounded_free_raster_region",
        "opening_gap_repair",
    ],
    "stable_across_gap_scales": True,
}


def _stub_reading(width, height):
    return {
        "contract": "LocalPlanReadingV1",
        "version": "1.3",
        "source": "local_offline_raster",
        "provider_independent": True,
        "status": "grounded",
        "image_size": {"width": width, "height": height},
        "plan_bbox_pixels": [0, 0, width, height],
        "labels": [],
        "openings": [],
        "furniture_observed": False,
        "furniture_evidence": [],
        "symbol_analysis_status": "analyzed",
        "element_evidence": [],
        "element_analysis_status": "analyzed",
        "enclosure_geometry": {
            "count": None,
            "count_status": "uncertain",
            "regions": [dict(_STUB_REGION)],
        },
    }


def _recording_reader(calls):
    def reader(raster, **kwargs):
        calls.append(tuple(raster.shape))
        height, width = raster.shape
        return _stub_reading(width, height)

    return reader


def _analyze(sheet_raster):
    calls = []
    sheet = detect_sheet(sheet_raster)
    result = analyze_sheet(sheet_raster, sheet, _recording_reader(calls), None)
    return result, calls


def _stub_build_plan(observation):
    return {
        "spaces": [],
        "named_spaces": [],
        "read_labels": [],
        "geometry_spaces": [{"space": "enclosed space", "bbox_pixels": [0, 0, 10, 10]}],
        "furniture": [
            dict(item) for item in observation.get("grounded_furniture_evidence", [])
        ],
        "inferred_functions": [],
        "openings": [],
        "architectural_elements": [],
        "space_count": 1,
    }


# --------------------------------------------------------------------------
# Phase 1 — the native pass runs, the OCR path is untouched
# --------------------------------------------------------------------------


def test_native_detector_runs_on_the_original_crop_not_the_upscaled_copy():
    result, calls = _analyze(_two_panel_sheet())
    panels = result["sheet_structure"]["panels"]
    assert len(panels) == 2
    for panel, shape in zip(panels, calls, strict=True):
        x0, y0, x1, y1 = panel["bbox_pixels"]
        native = (y1 - y0, x1 - x0)
        scale = max(1.0, 900 / max(native))
        # The reader still receives the UPSCALED copy, not the native crop.
        assert shape == (round(native[0] * scale), round(native[1] * scale))
        assert shape != native
        record = panel["native_furniture_transport"]
        assert record["native_raster_size"] == {"width": native[1], "height": native[0]}
        assert record["analysis_raster_size"] == {"width": shape[1], "height": shape[0]}
        assert record["detected"] >= 1 and record["appended"] >= 1
        items = panel["local_plan_reading"]["furniture_evidence"]
        assert items and all(item["class"] == "bed" for item in items)
        for item in items:
            assert item["native_symbol_pass"] is True
            assert item["source_panel_id"] == panel["panel_id"]


def test_resized_reader_path_matches_the_legacy_upscale_formula():
    """OCR / walls / geometry keep seeing exactly the old panel-analysis frame."""
    result, calls = _analyze(_two_panel_sheet())
    panels = result["sheet_structure"]["panels"]
    assert len(calls) == len(panels) == 2
    for panel, shape in zip(panels, calls, strict=True):
        x0, y0, x1, y1 = panel["bbox_pixels"]
        crop_width, crop_height = x1 - x0, y1 - y0
        scale = max(1.0, 900 / max(crop_height, crop_width))
        assert shape[1] == round(crop_width * scale)
        assert shape[0] == round(crop_height * scale)
        transform = panel["raster_transform"]
        assert transform["sheet_origin"] == [x0, y0]
        assert transform["scale_x"] == pytest.approx(shape[1] / crop_width)
        assert transform["scale_y"] == pytest.approx(shape[0] / crop_height)
        assert transform["coordinate_frame"] == "panel_analysis_pixels"


# --------------------------------------------------------------------------
# Phase 3 — coordinate remap safety
# --------------------------------------------------------------------------


@pytest.mark.parametrize("scale", [0.5, 1.0, 1.37, 2.394308943089431, 3.9])
@pytest.mark.parametrize("box", [[0, 0, 40, 60], [10, 20, 60, 90], [100, 200, 140, 260]])
def test_native_box_to_panel_is_an_exact_scaled_map(box, scale):
    panel_size = (round(400 * scale), round(600 * scale))
    mapped = native_box_to_panel(box, scale, scale, panel_size)
    assert mapped == [int(round(v * scale)) for v in box]
    assert 0 <= mapped[0] < mapped[2] <= panel_size[0]
    assert 0 <= mapped[1] < mapped[3] <= panel_size[1]


@pytest.mark.parametrize(
    "scale_x,scale_y", [(1.0, 1.0), (2.35, 2.35), (2.394, 2.393), (0.7, 1.3), (3.0, 1.5)]
)
def test_remap_round_trip_is_within_one_pixel(scale_x, scale_y):
    panel_size = (round(300 * scale_x), round(500 * scale_y))
    box = [40, 60, 180, 320]
    mapped = native_box_to_panel(box, scale_x, scale_y, panel_size)
    back = panel_box_to_native(mapped, scale_x, scale_y)
    assert all(abs(a - b) <= 1 for a, b in zip(back, box, strict=True))


def test_edge_and_border_symbols_are_clamped_into_the_frame():
    panel_size = (200, 300)
    assert native_box_to_panel([0, 0, 20, 30], 2.0, 2.0, panel_size) == [0, 0, 40, 60]
    assert native_box_to_panel([90, 140, 130, 200], 2.0, 2.0, panel_size) == [
        180,
        280,
        200,
        300,
    ]
    clamped = native_box_to_panel([-5, -5, 4, 6], 2.0, 2.0, panel_size)
    assert clamped[0] >= 0 and clamped[1] >= 0
    assert clamped[2] > clamped[0] and clamped[3] > clamped[1]
    assert clamped[2] <= panel_size[0] and clamped[3] <= panel_size[1]


def test_non_square_panel_keeps_independent_axis_scales():
    panel_size = (300, 900)
    box = [20, 40, 60, 140]
    mapped = native_box_to_panel(box, 3.0, 1.5, panel_size)
    assert mapped == [60, 60, 180, 210]
    assert panel_box_to_native(mapped, 3.0, 1.5) == box
    # A box whose long axis would leave the frame is clamped, not wrapped.
    assert native_box_to_panel([50, 50, 150, 250], 3.0, 1.5, panel_size) == [
        150,
        75,
        300,
        375,
    ]


def test_normalized_and_sheet_frames_follow_the_panel_transform():
    panel_size = (400, 800)
    box = [100, 200, 300, 600]
    assert panel_box_to_normalized(box, panel_size) == [0.25, 0.25, 0.75, 0.75]
    transform = {
        "sheet_origin": [53, 69],
        "scale_x": 2.0,
        "scale_y": 2.0,
        "coordinate_frame": "panel_analysis_pixels",
    }
    assert panel_box_to_sheet(box, transform) == [103, 169, 203, 369]
    normalized = panel_box_to_normalized([0, 0, 400, 800], panel_size)
    assert normalized == [0.0, 0.0, 1.0, 1.0]


def test_transported_items_carry_both_frames_and_stay_consistent():
    result, _ = _analyze(_two_panel_sheet())
    for panel in result["sheet_structure"]["panels"]:
        transform = panel["raster_transform"]
        for item in panel["local_plan_reading"]["furniture_evidence"]:
            native = item["native_bbox_pixels"]
            mapped = item["bbox_pixels"]
            scale_x, scale_y = item["native_scale"]["scale_x"], item["native_scale"]["scale_y"]
            assert mapped == native_box_to_panel(
                native,
                scale_x,
                scale_y,
                (
                    transform["scale_x"] * item["native_raster_size"]["width"],
                    transform["scale_y"] * item["native_raster_size"]["height"],
                ),
            )
            assert item["sheet_bbox_pixels"] == panel_box_to_sheet(mapped, transform)
            assert item["coordinate_frame"] == "panel_analysis_pixels"
            assert item["native_coordinate_frame"] == "panel_native_pixels"


# --------------------------------------------------------------------------
# Phase 2/4 — deduplication and provenance
# --------------------------------------------------------------------------


def test_legacy_item_is_never_overwritten_and_native_duplicate_is_suppressed():
    crop = _panel_image(furnished=True)
    native_box = [25, 20, 235, 335]
    native_items = analyze_furniture_symbols(crop, native_box)
    assert native_items
    native_bed = next(item for item in native_items if item["class"] == "bed")

    native_height, native_width = crop.shape
    analysis_width, analysis_height = round(native_width * 2.35), round(
        native_height * 2.35
    )
    scale_x = analysis_width / native_width
    scale_y = analysis_height / native_height
    mapped = native_box_to_panel(
        native_bed["bbox_pixels"], scale_x, scale_y, (analysis_width, analysis_height)
    )

    legacy = dict(
        native_bed,
        bbox_pixels=list(mapped),
        item_id="f1",
        corroboration=["a", "b", "c"],
        raster_patch_sha256="0" * 64,
    )
    local = {
        "symbol_analysis_status": "analyzed",
        "image_size": {"width": analysis_width, "height": analysis_height},
        "furniture_evidence": [legacy],
    }
    panel = {
        "panel_id": "pX",
        "raster_transform": {
            "sheet_origin": [10, 20],
            "scale_x": scale_x,
            "scale_y": scale_y,
            "coordinate_frame": "panel_analysis_pixels",
        },
    }

    _native_furniture_transport(
        cv2, local, panel, crop, native_box, (analysis_height, analysis_width)
    )

    assert local["furniture_evidence"][0] is legacy  # not overwritten
    assert len(local["furniture_evidence"]) == 1
    record = panel["native_furniture_transport"]
    assert record["detected"] >= 1
    assert record["appended"] == 0
    assert record["suppressed_as_duplicate"] >= 1


def test_panel_provenance_is_preserved_and_evidence_validates():
    result, _ = _analyze(_two_panel_sheet())
    total = 0
    for panel in result["sheet_structure"]["panels"]:
        items = panel["local_plan_reading"]["furniture_evidence"]
        for item in items:
            total += 1
            assert item["source"] == "local_raster_symbol_topology"
            assert item["provider_independent"] is True
            assert item["status"] == "visible"
            assert item["confidence"] == "MEDIUM"
            assert len(item["raster_patch_sha256"]) == 64
            assert "native_resolution_symbol_pass" in item["corroboration"]
            assert item["source_panel_id"] == panel["panel_id"]
            assert item["native_raster_size"]["width"] > 0
            assert len(item["bbox_normalized"]) == 4
        # The full evidence contract still accepts every transported item.
        assert len(grounded_plan_items(panel["local_plan_reading"])) == len(items)
        # And every transported class is in the general taxonomy.
        assert {item["class"] for item in items} <= set(FUNCTIONS)
    assert total >= 1


def test_native_items_do_not_promote_a_space_function_without_region_support():
    result, _ = _analyze(_two_panel_sheet())
    for panel in result["sheet_structure"]["panels"]:
        for item in panel["local_plan_reading"]["furniture_evidence"]:
            # The native enclosure regions are not transported, so no region is
            # claimed and the item cannot create an inferred function.
            assert item["region_ids"] == []


# --------------------------------------------------------------------------
# Phase 4 — corresponding-pair transport and isolation
# --------------------------------------------------------------------------


def test_corresponding_pair_transport_keeps_furniture_with_its_source_panel():
    result, _ = _analyze(_two_panel_sheet(furnished=(False, True)))
    sheet = grounded_sheet_structure(result)
    assert sheet and sheet["sheet_type"] == "plan_pair"
    assert {panel["role"] for panel in sheet["panels"]} == {
        "architectural_plan",
        "furnished_architectural_plan",
    }
    plan = build_sheet_plan_reading(result, _stub_build_plan)
    assert plan["fusion"]["status"] == "corresponding_pair"
    assert plan["fusion"]["furniture_panel_id"] == "p2"
    assert plan["fusion"]["geometry_panel_id"] == "p1"
    assert plan["furniture_observed"] is True
    assert plan["furniture"]
    assert all(item["source_panel_id"] == "p2" for item in plan["furniture"])
    assert all(item["coordinate_frame"] == "panel_analysis_pixels" for item in plan["furniture"])
    # No physical furniture is duplicated by the fusion step.
    keys = {(item["class"], tuple(item["bbox_pixels"])) for item in plan["furniture"]}
    assert len(keys) == len(plan["furniture"])
    assert all(item["item_id"] for item in plan["furniture"])


def test_unrelated_panels_keep_their_furniture_isolated():
    result, _ = _analyze(
        _two_panel_sheet(furnished=(False, True), alternative=(False, True))
    )
    panels = result["sheet_structure"]["panels"]
    assert len(panels) == 2
    # The native pass is panel-local: the unfurnished panel contributes nothing.
    assert panels[0]["local_plan_reading"]["furniture_evidence"] == []
    assert panels[0].get("native_furniture_transport") is None
    assert panels[1]["local_plan_reading"]["furniture_evidence"]
    collection = build_sheet_plan_reading(result, _stub_build_plan)
    assert collection["representation"] == "independent_plan_collection"
    assert collection["physical_plan_aggregation"] is False
    assert collection["fusion"]["status"] == "separate_panels"
    by_panel = {entry["panel_id"]: entry for entry in collection["plans"]}
    assert by_panel["p1"]["furniture"] == []
    assert by_panel["p2"]["furniture"]
    for entry in collection["plans"]:
        assert all(
            item["source_panel_id"] == entry["panel_id"] for item in entry["furniture"]
        )
        assert entry["provenance"]["source_panel_id"] == entry["panel_id"]
