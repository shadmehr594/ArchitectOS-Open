"""Actual private A/B contrast, independent symbols and provider-boundary tests."""

import os
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)
from core.vision.image_understanding_v1 import build_understanding
from core.vision.local_plan_elements_v1 import (
    _axes,
    _columns,
    _ducts,
    _numeric_ocr,
    _record,
    _stairs,
    _windows,
    analyze_plan_elements,
    grounded_plan_elements,
    interpret_plan_elements,
)
from core.vision.local_plan_reader_v1 import (
    _perimeter_windows,
    _plan_bbox,
    _read_raster,
    read_local_plan,
)
from core.vision.vision_observation_mode_v1 import build_observation
from core.vision.vision_report_v1 import render_vision_report

FIXTURES = Path(__file__).parent / "fixtures/vision/furnished_plan_v1"
A = Path(os.environ.get("ARCHITECTOS_PLAN_A", str(FIXTURES / "unfurnished.png")))
B = Path(os.environ.get("ARCHITECTOS_PLAN_B", str(FIXTURES / "furnished.jpg")))


@pytest.fixture(scope="module")
def local_pair():
    if not A.is_file() or not B.is_file():
        pytest.skip("Supply private A/B images through ARCHITECTOS_PLAN_A/B")
    return read_local_plan(A), read_local_plan(B)


def interpret(local=None, tokens=("windows", "stairs", "column", "duct", "axis")):
    raw = {
        "image_type": "floor_plan_or_sketch",
        "confidence": "HIGH",
        "observed": ["floor plan"] + [t + " visible" for t in tokens],
        "architectural_elements": list(tokens),
        "furniture_elements": ["bed", "sofa", "table"],
    }
    if local is not None:
        raw["local_plan_reading"] = local
    u = build_understanding(raw, provider="adversarial-offline", model="stub")
    return u, interpret_architectural_vision(u)


def test_real_B_window_recovery_and_trace(local_pair):
    local = local_pair[1]
    g = _read_raster(B)
    assert len(_perimeter_windows(g, _plan_bbox(g))) == 1
    items = grounded_plan_elements(local)
    windows = [e for e in items if e["type"] == "window"]
    assert (
        len(windows) == 5
    )  # Acceptance assertion only; production has no fixed count.
    _, v = interpret(local)
    assert len(v["architectural_observation"]["grounded_element_evidence"]) == len(
        items
    )
    assert len(v["plan_reading"]["architectural_elements"]) == len(items)
    assert (
        sum(
            o["instance_count"]
            for o in v["plan_reading"]["openings"]
            if o["kind"] == "window"
        )
        == 5
    )
    assert all(
        e["source"] == "local_raster_geometry" and e["confidence"] == "MEDIUM"
        for e in windows
    )
    assert "چند پنجره" in render_vision_report(v, "fa")


def test_real_B_independent_stairs_levels_and_no_riser_invention(local_pair):
    local = local_pair[1]
    items = grounded_plan_elements(local)
    stairs = [e for e in items if e["type"] == "stair"]
    assert len(stairs) == 2 and len({s["element_id"] for s in stairs}) == 2
    assert {e["geometry"]["orientation"] for e in stairs} == {"horizontal", "vertical"}
    assert all(s["attributes"]["step_count"] == 7 for s in stairs)
    assert all("riser_height_m" not in s["attributes"] for s in stairs)
    levels = [e for e in items if e["type"] == "level"]
    assert {e["attributes"]["elevation_m"] for e in levels} == {0.0, 1.26}
    _, v = interpret(local)
    meanings = v["plan_reading"]["element_interpretation"]
    access = [m for m in meanings if m["type"] == "vertical_access"]
    assert all(m["total_rise_m"] is None and m["role"] is None for m in access)
    relationship = next(
        m["plan_level_relationship"]
        for m in meanings
        if m["type"] == "floor_elevation_relationship"
    )
    assert relationship["difference_m"] == 1.26
    assert not any("plan_level_relationship" in m for m in access)
    derived = next(m for m in meanings if m["type"] == "derived_stair_riser")
    assert derived["derived_riser_m"] == 0.18
    assert derived["derived_riser_cm"] == 18
    assert derived["provenance"] == "computed_from_grounded_evidence"
    assert derived["run_id"] is None and derived["assigned_run_ids"] == []
    assert not any("derived_riser_cm" in e["attributes"] for e in items)
    report = render_vision_report(v, "fa")
    assert "۰٫۰۰ و +۱٫۲۶ خوانده می‌شوند" in report
    assert "۱۸ سانتی‌متر محاسبه می‌شود" in report
    assert "ارتفاع درج‌شده" not in report


def test_real_B_service_context_columns_axes_and_concise_report(local_pair):
    local = local_pair[1]
    items = grounded_plan_elements(local)
    ducts = [e for e in items if e["type"] == "duct"]
    assert len(ducts) == 1 and ducts[0]["attributes"]["adjacent_service_region_ids"]
    assert not ducts[0]["attributes"]["shared_service_supported"]
    columns = [e for e in items if e["type"] == "column"]
    axes = [e for e in items if e["type"] == "axis"]
    assert (
        columns
        and axes
        and {a["geometry"]["orientation"] for a in axes} == {"horizontal", "vertical"}
    )
    assert all(
        c["status"] == "candidate" and len(c["attributes"]["matched_axis_ids"]) >= 2
        for c in columns
    )
    assert all(
        a["attributes"]["label"] is None
        or a["attributes"]["label_source"] == "local_marker_ocr"
        for a in axes
    )
    _, v = interpret(local)
    report = render_vision_report(v, "fa")
    assert "داکت" in report and "ستون احتمالی" in report and "دو مسیر پله‌ای" in report
    assert len(report) < 900 and len(report.split("\n\n")) <= 6
    assert not any(w in report for w in ("bbox", "threshold", "clearance", "collision"))


def test_A_and_furniture_regressions(local_pair):
    a, b = local_pair
    assert a["furniture_evidence"] == [] and not a["furniture_observed"]
    assert len([o for o in a["openings"] if o["kind"] == "window"]) == 4
    assert len(b["furniture_evidence"]) == 11
    _, va = interpret(a)
    _, vb = interpret(b)
    assert va["plan_reading"]["furniture"] == []
    assert {f["space"] for f in vb["plan_reading"]["inferred_functions"]} == {
        "bedroom",
        "living room",
        "kitchen",
        "bathroom",
        "dining",
    }
    assert {l["text"] for l in a["labels"]} >= {
        "اتاق خواب",
        "آشپزخانه",
        "حمام",
        "سرویس",
        "پذیرایی",
    }


@pytest.mark.parametrize("with_local", [False, True])
def test_provider_tokens_cannot_establish_any_symbol(with_local):
    local = (
        {
            "status": "grounded",
            "element_analysis_status": "analyzed",
            "element_evidence": [],
            "image_size": {"width": 200, "height": 200},
            "symbol_analysis_status": "analyzed",
            "furniture_evidence": [],
            "labels": [],
            "openings": [],
            "enclosure_geometry": {"regions": []},
        }
        if with_local
        else None
    )
    u, v = interpret(local)
    assert v["plan_reading"]["architectural_elements"] == []
    assert v["plan_reading"]["element_interpretation"] == []
    observation = build_observation(u)
    assert not observation["grounded_element_evidence"]
    assert not any(
        e["name"] in ("stair", "window", "column", "axis", "duct")
        for e in observation["elements"]
    )


@pytest.mark.parametrize("rotation", range(4))
def test_windows_support_both_orientations_and_ignore_empty_gap(rotation):
    import cv2

    im = Image.new("L", (300, 300), 255)
    d = ImageDraw.Draw(im)
    d.rectangle((40, 40, 260, 260), outline=0, width=7)
    for a, b in ((80, 120), (170, 215)):
        d.rectangle((a, 40, b, 46), fill=255)
        for y in (40, 43, 46):
            d.line((a, y, b, y), fill=0, width=1)
    d.rectangle((90, 253, 130, 260), fill=255)  # Empty wall gap is not a window.
    g = np.rot90(np.asarray(im), rotation).copy()
    found = _windows(cv2, g, (39, 39, 261, 261))
    assert len(found) == 2
    assert {e["geometry"]["orientation"] for e in found} == (
        {"horizontal"} if rotation % 2 == 0 else {"vertical"}
    )


def stair_raster(n=6, arrow=True):
    im = Image.new("L", (300, 300), 255)
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = 95, 100, 145, 100 + (n - 1) * 12
    d.line((x0, y0, x0, y1), fill=0)
    d.line((x1, y0, x1, y1), fill=0)
    for y in range(y0, y1 + 1, 12):
        d.line((x0, y, x1, y), fill=0)
    if arrow:
        d.line((120, y0 + 3, 120, y1 - 3), fill=0)
        d.polygon(((120, y0 + 3), (114, y0 + 13), (126, y0 + 13)), fill=0)
    return np.asarray(im)


@pytest.mark.parametrize("n", [4, 6, 9])
@pytest.mark.parametrize("rotation", range(4))
def test_independent_stair_counts_are_not_acceptance_constants(n, rotation):
    import cv2

    g = np.rot90(stair_raster(n), rotation).copy()
    items = _stairs(cv2, g, (30, 30, 270, 270))
    assert len(items) == 1 and items[0]["attributes"]["step_count"] == n


def test_parallel_lines_without_arrow_are_not_stairs():
    import cv2

    assert _stairs(cv2, stair_raster(7, False), (30, 30, 270, 270)) == []


def test_two_dimensional_grid_with_arrow_is_not_stair():
    import cv2

    im = Image.fromarray(stair_raster(7))
    d = ImageDraw.Draw(im)
    for x in (103, 111, 129, 137):
        d.line((x, 100, x, 172), fill=0)
    assert _stairs(cv2, np.asarray(im), (30, 30, 270, 270)) == []


def grid_raster(with_walls=False):
    im = Image.new("L", (500, 500), 255)
    d = ImageDraw.Draw(im)
    for x in (120, 310):
        d.ellipse((x - 15, 10, x + 15, 40), outline=0)
        d.line((x, 40, x, 70), fill=0)
    for y in (120, 300):
        d.ellipse((25, y - 15, 55, y + 15), outline=0)
        d.line((55, y, 80, y), fill=0)
    for x in (120, 310):
        for y in (120, 300):
            d.rectangle((x - 6, y - 6, x + 6, y + 6), fill=0)
    if with_walls:
        for x in (120, 310):
            d.line((x, 80, x, 420), fill=0, width=3)
        for y in (120, 300):
            d.line((80, y, 420, y), fill=0, width=3)
    return np.asarray(im)


def test_independent_axis_geometry_with_attached_leaders():
    import cv2

    axes = _axes(cv2, grid_raster(), (80, 80, 420, 420))
    assert len(axes) == 4
    assert {a["geometry"]["orientation"] for a in axes} == {"horizontal", "vertical"}
    assert all(a["attributes"]["label"] is None for a in axes)


@pytest.mark.parametrize("with_walls", [False, True])
def test_grid_aligned_blocks_need_wall_context(with_walls):
    import cv2

    g = grid_raster(with_walls)
    box = (80, 80, 420, 420)
    axes = _axes(cv2, g, box)
    for i, a in enumerate(axes):
        a["element_id"] = f"axis{i}"
    columns = _columns(cv2, g, box, axes)
    assert len(columns) == (4 if with_walls else 0)


@pytest.mark.parametrize("label,expected", [("R=17 cm", 0.17), ("17 cm", None)])
def test_real_annotation_ocr_and_computation_are_general(label, expected):
    import cv2

    pytest.importorskip("tesserocr")
    tessdata = Path(__file__).resolve().parents[1] / "models/ocr/tessdata_fast"
    if not (tessdata / "eng.traineddata").is_file():
        pytest.skip("Local English tessdata required for annotation OCR")
    im = Image.fromarray(stair_raster(8))
    ImageDraw.Draw(im).text((78, 78), label, fill=0, font=ImageFont.load_default())
    g = np.asarray(im)
    stairs = _stairs(cv2, g, (30, 30, 270, 270))
    _numeric_ocr(g, [], stairs, [], tessdata)
    assert stairs[0]["attributes"].get("riser_height_m") == expected
    stairs[0]["element_id"] = "s1"
    meaning = interpret_plan_elements(stairs, [])[0]
    assert meaning["total_rise_m"] == (1.36 if expected else None)


def test_missing_numeric_backend_keeps_geometry(local_pair, tmp_path):
    local = local_pair[1]
    g = _read_raster(B)
    r = analyze_plan_elements(
        g,
        _plan_bbox(g),
        local["furniture_evidence"],
        local["enclosure_geometry"],
        tmp_path,
    )
    assert len([e for e in r["element_evidence"] if e["type"] == "window"]) == 5
    assert len([e for e in r["element_evidence"] if e["type"] == "stair"]) == 2
    assert all(
        e["attributes"]["elevation_m"] is None
        for e in r["element_evidence"]
        if e["type"] == "level"
    )


def test_compact_blocks_without_grid_are_not_columns():
    import cv2

    im = Image.new("L", (300, 300), 255)
    d = ImageDraw.Draw(im)
    for x in (70, 140, 210):
        d.rectangle((x, 100, x + 12, 112), fill=0)
    assert _columns(cv2, np.asarray(im), (30, 30, 270, 270), []) == []


def test_circle_without_axis_leader_is_not_grid():
    import cv2

    im = Image.new("L", (300, 300), 255)
    d = ImageDraw.Draw(im)
    for x in (70, 140, 210):
        d.ellipse((x, 5, x + 25, 30), outline=0, width=1)
    assert _axes(cv2, np.asarray(im), (40, 45, 260, 270)) == []


def test_small_rectangle_without_service_context_is_not_duct():
    import cv2

    im = Image.new("L", (300, 300), 255)
    d = ImageDraw.Draw(im)
    d.rectangle((200, 110, 220, 155), outline=0, width=5)
    assert _ducts(cv2, np.asarray(im), (30, 30, 270, 270), [], []) == []


def derived_riser_inputs():
    common = {
        "source": "local_raster_geometry",
        "provider_independent": True,
        "confidence": "MEDIUM",
        "status": "visible",
    }
    return [
        {
            **common,
            "type": "stair",
            "element_id": "s1",
            "attributes": {"step_count": 7},
        },
        *[
            {
                **common,
                "type": "level",
                "element_id": name,
                "attributes": {
                    "elevation_m": value,
                    "annotation_status": "grounded_ocr",
                    "annotation": {
                        "source": "local_numeric_ocr",
                        "confidence": "MEDIUM",
                        "ocr_confidence": 60,
                        "independent_thresholds": [180, 220],
                    },
                },
            }
            for name, value in (("lower", 0.0), ("upper", 1.26))
        ],
    ]


def derived_results(items):
    return [
        m
        for m in interpret_plan_elements(items, [])
        if m["type"] == "derived_stair_riser"
    ]


def test_derived_riser_A_grounded_count_and_levels():
    items = derived_riser_inputs()
    original = deepcopy(items)
    result = derived_results(items)[0]
    assert result["total_rise_m"] == 1.26
    assert result["derived_riser_m"] == 0.18
    assert result["derived_riser_cm"] == 18
    assert result["derivation"] == "level_difference / grounded_step_count"
    assert result["provenance"] == "computed_from_grounded_evidence"
    assert result["status"] == "computed"
    assert items == original  # Computation never becomes an observed annotation.


def test_derived_riser_B_missing_upper_level():
    assert derived_results(derived_riser_inputs()[:-1]) == []


def test_derived_riser_C_missing_step_count():
    items = derived_riser_inputs()
    items[0]["attributes"].pop("step_count")
    assert derived_results(items) == []


def test_derived_riser_D_ambiguous_association_stays_general():
    items = derived_riser_inputs()
    other = deepcopy(items[0])
    other["element_id"] = "s2"
    items.append(other)
    result = derived_results(items)[0]
    assert result["association"] == "general_unassigned"
    assert result["run_id"] is None and result["assigned_run_ids"] == []
    assert result["candidate_step_evidence_ids"] == ["s1", "s2"]
    access = [
        m for m in interpret_plan_elements(items, []) if m["type"] == "vertical_access"
    ]
    assert all(
        m["total_rise_m"] is None and "derived_riser_cm" not in m for m in access
    )
    other["attributes"]["step_count"] = 6
    assert derived_results(items) == []  # No arbitrary count chosen between runs.


@pytest.mark.parametrize(
    "bad", ["provider", "low_count_confidence", "unread_level", "no_ocr_agreement"]
)
def test_derived_riser_rejects_ungrounded_inputs(bad):
    items = derived_riser_inputs()
    if bad == "provider":
        items[0]["source"] = "provider_only"
    elif bad == "low_count_confidence":
        items[0]["confidence"] = "LOW"
    elif bad == "unread_level":
        items[2]["attributes"]["elevation_m"] = None
    else:
        items[2]["attributes"]["annotation"]["independent_thresholds"] = [180]
    assert derived_results(items) == []


@pytest.mark.parametrize("missing", ["count", "riser", "provenance", "none"])
def test_rise_multiplication_requires_both_grounded_inputs(missing):
    stair = {
        "type": "stair",
        "element_id": "s1",
        "confidence": "MEDIUM",
        "bbox_pixels": [10, 10, 50, 80],
        "attributes": {
            "step_count": 8,
            "riser_height_m": 0.17,
            "riser_annotation": {
                "source": "local_numeric_ocr",
                "independent_thresholds": [180, 220],
                "ocr_confidence": 65,
                "confidence": "MEDIUM",
            },
        },
    }
    if missing == "count":
        stair["attributes"].pop("step_count")
    if missing == "riser":
        stair["attributes"].pop("riser_height_m")
    if missing == "provenance":
        stair["attributes"]["riser_annotation"]["source"] = "provider_only"
    result = interpret_plan_elements([stair], [])[0]
    assert result["total_rise_m"] == (1.36 if missing == "none" else None)


@pytest.mark.parametrize(
    "bad",
    ["bbox", "confidence", "source", "corroboration", "hash", "orientation", "count"],
)
def test_element_contract_rejects_invalid_evidence(bad):
    g = stair_raster()
    item = _record(
        g,
        "stair",
        [95, 100, 145, 161],
        ["a", "b", "c"],
        geometry={"orientation": "vertical", "direction": "up"},
        attributes={"step_count": 6},
    )
    local = {
        "element_analysis_status": "analyzed",
        "image_size": {"width": 300, "height": 300},
        "element_evidence": [deepcopy(item)],
    }
    if bad == "bbox":
        local["element_evidence"][0]["bbox_pixels"] = [-1, 0, 1, 3]
    elif bad == "confidence":
        local["element_evidence"][0]["confidence"] = "LOW"
    elif bad == "source":
        local["element_evidence"][0]["source"] = "provider_only"
    elif bad == "corroboration":
        local["element_evidence"][0]["corroboration"] = []
    elif bad == "hash":
        local["element_evidence"][0]["raster_patch_sha256"] = "x" * 64
    elif bad == "orientation":
        local["element_evidence"][0]["geometry"]["orientation"] = "unknown"
    else:
        local["element_evidence"][0]["attributes"]["step_count"] = 7.5
    assert grounded_plan_elements(local) == []


def test_recognizer_does_not_touch_frozen_pipelines(local_pair):
    _, v = interpret(local_pair[1])
    p = v["plan_reading"]
    assert (
        p["read_only"]
        and not p["render_requested"]
        and not p["comfy_invoked"]
        and not p["llm_used"]
    )
