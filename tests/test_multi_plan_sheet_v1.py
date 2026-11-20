"""Sheet isolation, conservative correspondence and private four-image contrast."""

import os
from copy import deepcopy
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)
from core.vision.image_understanding_v1 import build_understanding
from core.vision.local_plan_reader_v1 import read_local_plan
from core.vision.local_plan_symbols_v1 import FUNCTIONS, grounded_plan_items
from core.vision.local_plan_sheet_v1 import (
    _descriptor,
    _panel_context,
    _unit_support,
    analyze_sheet,
    correspondence,
    detect_sheet,
    grounded_sheet_structure,
)
from core.vision.vision_report_v1 import render_vision_report


def plan_raster(alternative=False):
    im = Image.new("L", (260, 360), 255)
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
    return np.asarray(im)


@pytest.mark.parametrize("vertical", [False, True])
@pytest.mark.parametrize("scale", [0.8, 1.4])
def test_two_drawing_regions_without_titles_and_at_varied_scale(vertical, scale):
    p = plan_raster()
    sheet = (
        np.full((800, 340), 255, np.uint8)
        if vertical
        else np.full((420, 660), 255, np.uint8)
    )
    if vertical:
        sheet[10:370, 40:300] = p
        sheet[420:780, 40:300] = p
    else:
        sheet[20:380, 20:280] = p
        sheet[20:380, 370:630] = p
    sheet = cv2.resize(sheet, None, fx=scale, fy=scale)
    result = detect_sheet(sheet)
    assert result["sheet_type"] == "multi_plan"
    assert len(result["panels"]) == 2
    a, b = result["panels"]
    assert (
        a["bbox_pixels"][2] <= b["bbox_pixels"][0]
        or a["bbox_pixels"][3] <= b["bbox_pixels"][1]
    )


def test_single_connected_partitioned_plan_is_not_split_into_rooms():
    assert len(detect_sheet(plan_raster())["panels"]) == 1


def test_border_and_title_or_legend_do_not_create_plan_panels():
    im = Image.fromarray(plan_raster())
    d = ImageDraw.Draw(im)
    d.rectangle((1, 1, 258, 358), outline=0, width=1)
    d.text((70, 340), "FURNITURE PLAN", fill=0)
    assert len(detect_sheet(np.asarray(im))["panels"]) == 1


def described(p, identity):
    return {
        "panel_id": identity,
        "geometry_descriptor": _descriptor(cv2, p, [26, 21, 235, 335]),
    }


def test_correspondence_uses_internal_partitions_and_is_not_pixel_equality():
    a = plan_raster()
    b = cv2.resize(a, (300, 410))
    left = described(a, "a")
    right = {
        "panel_id": "b",
        "geometry_descriptor": _descriptor(cv2, b, [30, 24, 271, 382]),
    }
    assert correspondence(left, right)["supported"]


def test_matching_rectangular_footprint_with_different_rooms_does_not_fuse():
    assert not correspondence(
        described(plan_raster(), "a"), described(plan_raster(True), "b")
    )["supported"]


def test_empty_rectangles_do_not_establish_correspondence():
    a = np.full((200, 200), 255, np.uint8)
    cv2.rectangle(a, (10, 10), (190, 190), 0, 2)
    assert not correspondence(
        {"panel_id": "a", "geometry_descriptor": _descriptor(cv2, a, [8, 8, 193, 193])},
        {"panel_id": "b", "geometry_descriptor": _descriptor(cv2, a, [8, 8, 193, 193])},
    )["supported"]


def test_panel_reader_receives_only_its_crop_and_no_whole_sheet():
    sheet = np.full((420, 660), 255, np.uint8)
    sheet[20:380, 20:280] = plan_raster()
    sheet[20:380, 370:630] = plan_raster()
    calls = []

    def reader(raster, **kwargs):
        calls.append(raster.shape)
        h, w = raster.shape
        return {
            "contract": "LocalPlanReadingV1",
            "source": "local_offline_raster",
            "provider_independent": True,
            "status": "grounded",
            "image_size": {"width": w, "height": h},
            "plan_bbox_pixels": [0, 0, w, h],
            "labels": [],
            "openings": [],
            "furniture_evidence": [],
            "element_evidence": [],
            "enclosure_geometry": {"count": None, "regions": []},
        }

    result = analyze_sheet(sheet, detect_sheet(sheet), reader, None)
    assert len(calls) == 2
    assert all(w < h for h, w in calls)
    assert result["labels"] == [] and result["furniture_evidence"] == []
    assert grounded_sheet_structure(result)


@pytest.mark.parametrize("has_doors", [False, True])
def test_parallel_grid_alone_does_not_ground_stairs_or_elevator(has_doors):
    im = np.full((300, 300), 255, np.uint8)
    for y in range(150, 190, 5):
        cv2.line(im, (125, y), (165, y), 0, 1)
    # Dense 2D grids are not paired stair flights.
    for x in range(125, 170, 5):
        cv2.line(im, (x, 150), (x, 185), 0, 1)
    doors = (
        [
            {"element_id": "d1", "bbox_pixels": [115, 130, 125, 140]},
            {"element_id": "d2", "bbox_pixels": [170, 130, 180, 140]},
        ]
        if has_doors
        else []
    )
    _, items = _panel_context(cv2, im, [20, 20, 280, 280], doors)
    assert items == []


@pytest.mark.parametrize("missing", ["functions", "entrances", "neither"])
def test_symmetry_only_is_not_two_units(missing):
    funcs = [
        (f, [x, 0.3]) for x in (0.2, 0.8) for f in ("bedroom", "living room", "kitchen")
    ]
    entries = [("left", [0.35, 0.7]), ("right", [0.65, 0.7])]
    result = _unit_support(
        [] if missing == "functions" else funcs,
        [] if missing == "entrances" else entries,
        0,
    )
    assert result["unit_count_candidate"] == (2 if missing == "neither" else None)


PATHS = {
    key: Path(os.environ.get("ARCHITECTOS_PLAN_" + key, "__missing_private_image__"))
    for key in "ABCD"
}


@pytest.fixture(scope="module")
def four_images():
    if not all(p.is_file() for p in PATHS.values()):
        pytest.skip(
            "Provide private ARCHITECTOS_PLAN_A/B/C/D; synthetic tests are not real acceptance"
        )
    return {k: read_local_plan(p) for k, p in PATHS.items()}


def interpretation(local, provider=False):
    raw = {
        "image_type": "floor_plan_or_sketch",
        "observed": ["floor plan"],
        "local_plan_reading": local,
    }
    if provider:
        raw.update(
            confidence="HIGH",
            architectural_elements=["stairs", "elevator", "windows", "column"],
            furniture_elements=["bed", "sofa", "table"],
        )
    return interpret_architectural_vision(
        build_understanding(raw, provider="adversarial-offline", model="stub"),
        user_text="خودتو جای یه معمار بزار و این پلان رو آنالیز کن",
    )


@pytest.mark.parametrize("name", list("ABC"))
def test_real_single_plans_remain_single(four_images, name):
    local = four_images[name]
    assert local["sheet_structure"]["sheet_type"] == "single_plan"
    assert len(local["sheet_structure"]["panels"]) == 1
    assert local["sheet_structure"]["panels"][0]["role"] == (
        "architectural_plan" if name == "A" else "furnished_architectural_plan"
    )


def test_real_D_split_independent_roles_and_supported_correspondence(four_images):
    local = four_images["D"]
    sheet = grounded_sheet_structure(local)
    assert sheet and len(sheet["panels"]) == 2 and sheet["sheet_type"] == "plan_pair"
    assert {p["role"] for p in sheet["panels"]} == {
        "dimension_plan",
        "furnished_architectural_plan",
    }
    assert all(
        "sheet_structure" not in p["local_plan_reading"] for p in sheet["panels"]
    )
    assert (
        local["labels"] == []
        and local["element_evidence"] == []
        and local["furniture_evidence"] == []
    )
    assert all(
        p["raster_transform"]["coordinate_frame"] == "panel_analysis_pixels"
        for p in sheet["panels"]
    )


def test_real_D_fusion_does_not_sum_spaces_or_openings(four_images):
    plan = interpretation(four_images["D"], True)["plan_reading"]
    assert plan["fusion"]["status"] == "corresponding_pair"
    geometry = next(
        p["plan_reading"]
        for p in plan["panel_readings"]
        if p["panel_id"] == plan["fusion"]["geometry_panel_id"]
    )
    assert len(plan["geometry_spaces"]) == len(geometry["geometry_spaces"])
    assert sum(o["instance_count"] for o in plan["openings"]) == sum(
        o["instance_count"] for o in geometry["openings"]
    )
    assert all(i["source_refs"] for o in plan["openings"] for i in o["instances"])
    assert any(
        len(i["source_refs"]) > 1 for o in plan["openings"] for i in o["instances"]
    )
    assert plan["central_core"]["status"] == "grounded_candidate"
    assert not plan["central_core"]["elevator_confirmed"]
    assert plan["spatial_organization"]["unit_count_candidate"] is None
    assert any(e["type"] == "axis" for e in plan["architectural_elements"])


def test_real_D_report_is_sheet_level_and_does_not_fill_missing_functions(four_images):
    v = interpretation(four_images["D"], True)
    report = render_vision_report(v, "fa")
    assert report.startswith("این شیت شامل دو نمایش متناظر")
    assert "پلان معماری" in report and "پلان مبلمان" in report and "بخش مرکزی" in report
    assert len(report) < 1000 and len(report.split("\n\n")) <= 6
    assert not any(
        w in report for w in ("bbox", "similarity", "threshold", "panel_id", "18 cm")
    )
    assert "تخت" not in report and "آسانسور است" not in report
    # The furniture panel now contributes genuine grounded evidence, but a
    # localized item whose enclosure region was not transported still cannot
    # promote a space function — so no missing room is filled in.
    plan = v["plan_reading"]
    furniture_panel_id = plan["fusion"]["furniture_panel_id"]
    assert furniture_panel_id is not None
    assert plan["furniture"]
    assert all(
        item["source_panel_id"] == furniture_panel_id
        and item["source"] == "local_raster_symbol_topology"
        and item["provider_independent"] is True
        for item in plan["furniture"]
    )
    assert plan["inferred_functions"] == []


def test_real_A_B_C_enclosure_baseline_is_not_disturbed(four_images):
    """W1 adds regions only where the dark mask genuinely loses partitions."""
    for name in "ABC":
        geometry = four_images[name]["enclosure_geometry"]
        assert geometry["wall_levels"] == [165, 190, 215]
        assert geometry["level_admitted_count"] == 0
        assert all(region["wall_levels"] == [165] for region in geometry["regions"])
        assert all(
            region["confidence"] in ("MEDIUM", "LOW")
            for region in geometry["regions"]
        )
    assert four_images["A"]["furniture_evidence"] == []
    assert len(four_images["B"]["furniture_evidence"]) == 11
    assert len(four_images["C"]["furniture_evidence"]) >= 3


def test_real_D_enclosure_and_axis_foundation_is_recovered(four_images):
    """W1/W2: D's panels now localize rooms and both axis orientations."""
    sheet = grounded_sheet_structure(four_images["D"])
    assert sheet
    architectural = next(p for p in sheet["panels"] if p["role"] == "dimension_plan")
    local = architectural["local_plan_reading"]
    geometry = local["enclosure_geometry"]
    assert geometry["wall_levels"] == [165, 190, 215]
    assert geometry["level_admitted_count"] >= 1
    admitted = [r for r in geometry["regions"] if 190 in r["wall_levels"]]
    assert admitted
    for region in admitted:
        assert region["confidence"] == "MEDIUM"
        assert region["stable_across_gap_scales"] is True
        assert "cross_level_wall_support" in region["corroboration"]
        # A level-admitted region never attracts a furniture item: the
        # connected-component label is stripped from every region before the
        # reading is published, and was never attached to an admitted one.
        assert all("label" not in region for region in geometry["regions"])
    # Both axis orientations are now grounded from the same panel.
    orientations = {
        e["geometry"]["orientation"]
        for e in local["element_evidence"]
        if e["type"] == "axis"
    }
    assert orientations == {"horizontal", "vertical"}
    # No exact room count is asserted, and the count contract is unchanged.
    assert geometry["count"] is None
    assert geometry["count_status"] == "uncertain"


def test_real_D_furnished_panel_is_read_at_native_resolution(four_images):
    """D's furniture panel contributes evidence from its ORIGINAL crop."""
    sheet = grounded_sheet_structure(four_images["D"])
    assert sheet
    furnished = next(
        p for p in sheet["panels"] if p["role"] == "furnished_architectural_plan"
    )
    record = furnished["native_furniture_transport"]
    assert record and record["appended"] >= 1
    assert record["provider_independent"] is True
    assert record["native_raster_size"] != record["analysis_raster_size"]
    assert record["analysis_raster_size"]["width"] == round(
        record["native_raster_size"]["width"] * record["scale_x"]
    )
    assert record["analysis_raster_size"]["height"] == round(
        record["native_raster_size"]["height"] * record["scale_y"]
    )
    local = furnished["local_plan_reading"]
    items = local["furniture_evidence"]
    assert items
    assert len(grounded_plan_items(local)) == len(items)
    for item in items:
        assert item["native_symbol_pass"] is True
        assert item["source_panel_id"] == furnished["panel_id"]
        assert item["native_bbox_pixels"] != item["bbox_pixels"]
        assert item["region_ids"] == []
        assert item["class"] in FUNCTIONS


def test_real_A_B_regression_and_no_provider_furniture_promotion(four_images):
    assert four_images["A"]["furniture_evidence"] == []
    assert interpretation(four_images["A"], True)["plan_reading"]["furniture"] == []
    assert len(four_images["B"]["furniture_evidence"]) == 11
    assert (
        len([e for e in four_images["B"]["element_evidence"] if e["type"] == "window"])
        == 5
    )


@pytest.mark.parametrize("bad", ["source", "bbox", "confidence", "child_source"])
def test_sheet_contract_rejects_provider_or_invalid_localization(four_images, bad):
    local = deepcopy(four_images["D"])
    if bad == "source":
        local["source"] = "provider_only"
    if bad == "bbox":
        local["sheet_structure"]["panels"][0]["bbox_pixels"][0] = -1
    if bad == "confidence":
        local["sheet_structure"]["confidence"] = "LOW"
    if bad == "child_source":
        local["sheet_structure"]["panels"][0]["local_plan_reading"]["source"] = (
            "provider_only"
        )
    assert grounded_sheet_structure(local) is None


def test_provider_only_elevator_cannot_be_grounded():
    from core.vision.architectural_vision_grounding_v1 import ground_vision_evidence

    raw = {
        "image_type": "floor_plan_or_sketch",
        "confidence": "HIGH",
        "observed": ["elevator visible"],
        "architectural_elements": ["elevator"],
    }
    grounding = ground_vision_evidence(raw)
    shaft = next(e for e in grounding["elements"] if e["element"] == "shaft")
    assert shaft["status"] == "provider_only"
    assert all(c["source"] == "provider_only" for c in shaft["evidence"])


def test_shaft_contract_rejects_unconfirmed_rectangle_without_context():
    from core.vision.local_plan_elements_v1 import _record, grounded_plan_elements

    gray = np.full((200, 200), 255, np.uint8)
    item = _record(
        gray,
        "shaft",
        [60, 60, 90, 90],
        ["rectangle", "compact", "central"],
        candidate=True,
        attributes={"likely_type": "core_shaft_or_void", "elevator_confirmed": False},
    )
    local = {
        "element_analysis_status": "analyzed",
        "image_size": {"width": 200, "height": 200},
        "element_evidence": [item],
    }
    assert grounded_plan_elements(local) == []


@pytest.mark.parametrize("count", [2, 3, 4, 9])
def test_unrelated_panel_collection_preserves_every_local_interpretation(count):
    """Contract composition test; synthetic child readings are not image acceptance."""
    from core.vision.local_plan_sheet_v1 import (
        build_sheet_plan_reading,
        render_sheet_report,
    )

    panels, originals = [], {}
    for index in range(count):
        identity = f"private-panel-{index}"
        child = {
            "contract": "LocalPlanReadingV1",
            "status": "grounded",
            "source": "local_offline_raster",
            "provider_independent": True,
            "image_size": {"width": 260, "height": 360},
            "labels": [],
            "openings": [],
            "furniture_evidence": [],
            "test_identity": identity,
        }
        panel = {
            **described(plan_raster(index % 2 == 1), identity),
            "bbox_pixels": [index * 300, 0, index * 300 + 260, 360],
            "role": "architectural_plan" if index % 2 == 0 else "furnished_plan",
            "source": "local_raster_geometry",
            "confidence": "MEDIUM",
            "corroboration": ["independent_cluster", "partition_activity", "gutter"],
            "raster_transform": {
                "sheet_origin": [index * 300, 0],
                "scale_x": 1,
                "scale_y": 1,
                "coordinate_frame": "panel_analysis_pixels",
            },
            "local_plan_reading": child,
        }
        panels.append(panel)
        originals[identity] = {
            "contract": "ArchitecturalPlanReadingV1",
            "version": "1.0",
            "spaces": [{"space": "bedroom", "marker": identity}],
            "geometry_spaces": [{"space": "enclosed space", "marker": identity}],
            "named_spaces": [{"space": "bedroom", "marker": identity}],
            "furniture": [{"name": "bed", "marker": identity}],
            "inferred_functions": [{"space": "bedroom", "marker": identity}],
            "openings": [
                {"kind": "window", "instance_count": index + 1, "marker": identity}
            ],
            "architectural_elements": [{"type": "axis", "marker": identity}],
            "element_interpretation": [{"type": "grid", "marker": identity}],
            "space_count": index + 2,
            "read_labels": [{"text": "اتاق خواب"}],
            "local_plan_reading": child,
        }
    local = {
        "source": "local_offline_raster",
        "provider_independent": True,
        "image_size": {"width": count * 300, "height": 360},
        "sheet_structure": {
            "sheet_type": "multi_plan",
            "source": "local_raster_geometry",
            "confidence": "MEDIUM",
            "panels": panels,
        },
    }
    assert grounded_sheet_structure(local)
    before = deepcopy(local)
    result = build_sheet_plan_reading(
        local,
        lambda obs: deepcopy(originals[obs["local_plan_reading"]["test_identity"]]),
    )
    assert local == before
    assert result["contract"] == "MultiPlanSheetReadingV1"
    assert result["representation"] == "independent_plan_collection"
    assert result["physical_plan_aggregation"] is False
    assert result["count_scope"] == "per_panel"
    assert result["fusion"]["status"] == "separate_panels"
    assert result["fusion"]["geometry_panel_id"] is None
    assert len(result["plans"]) == len(result["panel_readings"]) == count
    for entry, panel in zip(result["plans"], panels, strict=True):
        for key, value in originals[entry["panel_id"]].items():
            assert (
                entry[key] == value
            )  # Includes counts and complete local interpretation.
        assert entry["role"] == panel["role"]
        assert entry["provenance"]["source_panel_id"] == entry["panel_id"]
        assert entry["provenance"]["sheet_bbox_pixels"] == panel["bbox_pixels"]
        assert entry["provenance"]["raster_transform"] == panel["raster_transform"]
        assert entry["provenance"]["provider_independent"] is True
    # These are per-plan properties; there is no fictitious floor aggregate.
    assert not (
        set(originals[panels[0]["panel_id"]])
        - {"contract", "version", "local_plan_reading"}
    ) & set(result)
    rendered = render_sheet_report(result)
    assert rendered.startswith(
        "این شیت شامل چند پلان مستقل است که به‌صورت جداگانه تحلیل شده‌اند."
    )
    assert len(rendered.split("\n\n")) == count + 1
    assert rendered.count("فضاهای خواب و خصوصی") == count
    assert rendered.count("پنجره با شواهد محلی") == count
    assert not any(p["panel_id"] in rendered for p in panels)
    assert not any(
        token in rendered for token in ("bbox", "threshold", "source_panel_id")
    )
    assert "یک پلان طبقه" not in rendered
    result["plans"][0]["spaces"].clear()
    assert originals[panels[0]["panel_id"]]["spaces"]
    assert result["panel_readings"][0]["plan_reading"]["spaces"]


def test_real_unrelated_A_C_keep_independent_high_level_readings(four_images):
    """Use existing real readings to verify the complete observation/interpreter path."""
    from core.vision.local_plan_reader_v1 import _read_raster

    panels = []
    for index, name in enumerate("AC"):
        child = deepcopy(four_images[name])
        child.pop("sheet_structure")
        width, height = child["image_size"]["width"], child["image_size"]["height"]
        panels.append(
            {
                "panel_id": name,
                "role": "architectural_plan" if name == "A" else "furnished_plan",
                "bbox_pixels": [index * 1000, 0, index * 1000 + width, height],
                "source": "local_raster_geometry",
                "confidence": "MEDIUM",
                "corroboration": [
                    "independent_cluster",
                    "partition_activity",
                    "gutter",
                ],
                "local_plan_reading": child,
                "geometry_descriptor": _descriptor(
                    cv2, _read_raster(PATHS[name]), child["plan_bbox_pixels"]
                ),
            }
        )
    assert not correspondence(*panels)["supported"]
    local = {
        "status": "grounded",
        "source": "local_offline_raster",
        "provider_independent": True,
        "image_size": {"width": 2000, "height": 1000},
        "sheet_structure": {
            "sheet_type": "multi_plan",
            "source": "local_raster_geometry",
            "confidence": "MEDIUM",
            "panels": panels,
        },
    }
    result = interpretation(local, True)
    collection = result["plan_reading"]
    assert collection["representation"] == "independent_plan_collection"
    assert [p["panel_id"] for p in collection["plans"]] == list("AC")
    assert collection["plans"][0]["furniture"] == []
    # IMAGE C is the out-of-sample generalization target: its grounded set is
    # expected to GROW as the detector generalizes, so assert the qualitative
    # contract (non-empty, taxonomy-valid, item-local provenance) instead of a
    # frozen count. IMAGE A above stays strictly empty.
    c_furniture = collection["plans"][1]["furniture"]
    assert len(c_furniture) >= 3
    assert {f["class"] for f in c_furniture} <= set(FUNCTIONS)
    assert all(
        f["source"] == "local_raster_symbol_topology"
        and f["provider_independent"] is True
        for f in c_furniture
    )
    for entry, reading in zip(
        collection["plans"], collection["panel_readings"], strict=True
    ):
        assert entry["geometry_spaces"] == reading["plan_reading"]["geometry_spaces"]
        assert entry["openings"] == reading["plan_reading"]["openings"]
        assert (
            entry["architectural_elements"]
            == reading["plan_reading"]["architectural_elements"]
        )
    report = render_vision_report(result, "fa")
    assert report.startswith("این شیت شامل چند پلان مستقل")
    assert "پلان ۱" in report and "پلان ۲" in report
