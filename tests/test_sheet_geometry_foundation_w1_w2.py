"""ARCHITECTURAL SHEET GEOMETRY FOUNDATION — W1 (enclosure recovery) + W2 (axis/grid recovery).

Every fixture here is drawn synthetically. Nothing depends on the private
acceptance images, their filenames, or any fixed count from them.

W1: the room/void mask is evaluated at more than one binarization level, but a
higher level can only ever ADD a region that is cross-level stable, gap-scale
stable, substantial, and not a furniture symbol. The dark mask remains the
baseline and is unchanged.

W2: an axis leader interrupted by the dimension chain is still a leader; the
required covered length is unchanged and only bounded interruptions are
repaired. A marker with no leader, or one crossed by a perpendicular dimension
line, is still rejected.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from core.vision.local_plan_elements_v1 import (
    AXIS_LEADER_MAX_GAP_FRACTION,
    _axes,
    _columns,
    _leader_support,
    _runs,
)
from core.vision.local_plan_symbols_v1 import (
    ENCLOSURE_LEVEL_MIN_AREA_FRACTION,
    ENCLOSURE_WALL_LEVELS,
    _candidates,
    _enclosure_consensus,
    _enclosures,
    _walls,
)

CANVAS = 420
FRAME = (40, 40, 380, 380)
PLAN_BOX = [36, 36, 384, 384]
DARK = ENCLOSURE_WALL_LEVELS[0]


def _signature(geometry):
    return [
        (
            region["region_id"],
            tuple(region["bbox_pixels"]),
            region["confidence"],
            region["stable_across_gap_scales"],
        )
        for region in geometry["regions"]
    ]


def _baseline(gray, box):
    return _enclosures(
        cv2, _walls(cv2, (gray < DARK).astype(np.uint8), box, True), box
    )[0]


def _consensus(gray, box):
    dark = []
    for threshold in (DARK, 180, 155):
        dark += _candidates(cv2, gray, box, threshold)[0]
    return _enclosure_consensus(cv2, gray, box, dark)[0]


def _plan_frame(draw, width=5, value=0):
    draw.rectangle(FRAME, outline=value, width=width)


# --------------------------------------------------------------------------
# W1 — enclosure recovery
# --------------------------------------------------------------------------


def test_dark_wall_plan_enclosures_are_unchanged():
    """A plan whose partitions are already dark keeps its exact baseline set."""
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    draw.line((FRAME[0], 210, FRAME[2], 210), fill=0, width=4)
    draw.line((210, FRAME[1], 210, 210), fill=0, width=4)
    gray = np.asarray(image)
    baseline = _baseline(gray, PLAN_BOX)
    consensus = _consensus(gray, PLAN_BOX)
    assert _signature(consensus) == _signature(baseline)
    assert consensus["level_admitted_count"] == 0
    assert consensus["stable_region_count"] == baseline["stable_region_count"]
    assert consensus["multiple_spaces"] == baseline["multiple_spaces"]


def test_light_partition_enclosure_is_recovered_across_levels():
    """Partitions lighter than the dark mask are recovered, not replaced."""
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    draw.line((FRAME[0], 210, FRAME[2], 210), fill=180, width=3)
    draw.line((210, FRAME[1], 210, 210), fill=180, width=3)
    gray = np.asarray(image)
    baseline = _baseline(gray, PLAN_BOX)
    consensus = _consensus(gray, PLAN_BOX)
    assert len(consensus["regions"]) > len(baseline["regions"])
    admitted = [r for r in consensus["regions"] if 190 in r["wall_levels"]]
    assert admitted
    for region in admitted:
        assert region["confidence"] == "MEDIUM"
        assert region["stable_across_gap_scales"] is True
        assert "cross_level_wall_support" in region["corroboration"]
        assert "substantial_space" in region["corroboration"]
    # The baseline regions themselves are untouched, only annotated.
    assert _signature(consensus)[: len(baseline["regions"])] == _signature(baseline)


def test_a_higher_level_can_never_add_a_region_on_its_own():
    """Only the first level defines the baseline; higher levels only support."""
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    gray = np.asarray(image)
    baseline = _baseline(gray, PLAN_BOX)
    consensus = _consensus(gray, PLAN_BOX)
    assert consensus["wall_levels"] == list(ENCLOSURE_WALL_LEVELS)
    assert consensus["level_admitted_count"] == 0
    assert len(consensus["regions"]) == len(baseline["regions"])


def test_hatched_band_does_not_become_a_room():
    """A hatched sliver inside a wall band is not a space."""
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    # Two dark rails 32 px apart, split by a dark divider, filled with a light
    # hatch: at a higher level the hatch joins the wall mask.
    draw.line((120, FRAME[1], 120, FRAME[3]), fill=0, width=4)
    draw.line((152, FRAME[1], 152, FRAME[3]), fill=0, width=4)
    draw.line((120, 210, 152, 210), fill=0, width=3)
    for y in range(FRAME[1] + 6, FRAME[3] - 4, 7):
        draw.line((124, y, 148, y), fill=180, width=1)
    gray = np.asarray(image)
    baseline = _baseline(gray, PLAN_BOX)
    consensus = _consensus(gray, PLAN_BOX)
    baseline_boxes = {tuple(r["bbox_pixels"]) for r in baseline["regions"]}
    for region in consensus["regions"]:
        if tuple(region["bbox_pixels"]) in baseline_boxes:
            continue
        # Any admitted region must be a substantial space, never the 32 px band.
        width = region["bbox_pixels"][2] - region["bbox_pixels"][0]
        assert width > 32 or region["pixel_area"] >= (
            (PLAN_BOX[2] - PLAN_BOX[0]) * (PLAN_BOX[3] - PLAN_BOX[1])
            * ENCLOSURE_LEVEL_MIN_AREA_FRACTION
        )


def test_a_small_light_compartment_is_below_the_substantial_space_gate():
    """A tiny light-line compartment cannot be admitted as a room."""
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    draw.line((120, FRAME[1], 120, FRAME[3]), fill=0, width=4)
    draw.line((152, FRAME[1], 152, FRAME[3]), fill=0, width=4)
    draw.line((120, 210, 152, 210), fill=180, width=3)
    gray = np.asarray(image)
    consensus = _consensus(gray, PLAN_BOX)
    plan_area = (PLAN_BOX[2] - PLAN_BOX[0]) * (PLAN_BOX[3] - PLAN_BOX[1])
    for region in consensus["regions"]:
        if 190 in region.get("wall_levels", []):
            assert region["pixel_area"] >= plan_area * ENCLOSURE_LEVEL_MIN_AREA_FRACTION


def test_furniture_symbol_is_not_admitted_as_a_room():
    """A light-line furniture symbol never becomes an enclosure."""
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    # A large sleeping symbol in the light band, clear of the area gate.
    x, y, w, h = 150, 110, 90, 160
    draw.rectangle((x, y, x + w, y + h), outline=170, width=1)
    pw, ph = int(w * 0.38), int(h * 0.13)
    draw.rectangle((x + 3, y + 5, x + 3 + pw, y + 5 + ph), outline=170, width=1)
    draw.rectangle((x + w - 3 - pw, y + 5, x + w - 3, y + 5 + ph), outline=170, width=1)
    gray = np.asarray(image)
    consensus = _consensus(gray, PLAN_BOX)
    for region in consensus["regions"]:
        if 190 not in region.get("wall_levels", []):
            continue
        bx0, by0, bx1, by1 = region["bbox_pixels"]
        assert not (
            bx0 >= x - 4 and bx1 <= x + w + 4 and by0 >= y - 4 and by1 <= y + h + 4
        )


def test_a_region_that_is_a_furniture_symbol_is_not_admitted():
    """The furniture exclusion is a real gate, not an accident of thresholds."""
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    draw.line((FRAME[0], 210, FRAME[2], 210), fill=180, width=3)
    draw.line((210, FRAME[1], 210, 210), fill=180, width=3)
    gray = np.asarray(image)
    without = _enclosure_consensus(cv2, gray, PLAN_BOX, [])[0]
    admitted = [r for r in without["regions"] if 190 in r["wall_levels"]]
    assert admitted
    covering = {"class": "bed", "bbox_pixels": list(admitted[0]["bbox_pixels"])}
    with_candidate = _enclosure_consensus(cv2, gray, PLAN_BOX, [covering])[0]
    assert with_candidate["level_admitted_count"] == len(admitted) - 1
    assert all(
        tuple(r["bbox_pixels"]) != tuple(covering["bbox_pixels"])
        for r in with_candidate["regions"]
        if 190 in r.get("wall_levels", [])
    )


def test_furniture_inside_a_room_does_not_suppress_the_room():
    """Only a region that IS the symbol is suppressed, never its room."""
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    draw.line((FRAME[0], 210, FRAME[2], 210), fill=180, width=3)
    draw.line((210, FRAME[1], 210, 210), fill=180, width=3)
    gray = np.asarray(image)
    without = _enclosure_consensus(cv2, gray, PLAN_BOX, [])[0]
    admitted = [r for r in without["regions"] if 190 in r["wall_levels"]]
    assert admitted
    x0, y0, x1, y1 = admitted[0]["bbox_pixels"]
    inside = {
        "class": "bed",
        "bbox_pixels": [
            x0 + (x1 - x0) // 4,
            y0 + (y1 - y0) // 4,
            x0 + (x1 - x0) // 2,
            y0 + (y1 - y0) // 2,
        ],
    }
    with_candidate = _enclosure_consensus(cv2, gray, PLAN_BOX, [inside])[0]
    assert with_candidate["level_admitted_count"] == len(admitted)


def test_level_admitted_regions_deduplicate_deterministically():
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    draw.line((FRAME[0], 210, FRAME[2], 210), fill=180, width=3)
    draw.line((210, FRAME[1], 210, 210), fill=180, width=3)
    gray = np.asarray(image)
    first = _consensus(gray, PLAN_BOX)
    second = _consensus(gray, PLAN_BOX)
    assert _signature(first) == _signature(second)
    boxes = [r["bbox_pixels"] for r in first["regions"]]
    for index, left in enumerate(boxes):
        for right in boxes[index + 1:]:
            intersection = max(0, min(left[2], right[2]) - max(left[0], right[0])) * max(
                0, min(left[3], right[3]) - max(left[1], right[1])
            )
            union = (
                (left[2] - left[0]) * (left[3] - left[1])
                + (right[2] - right[0]) * (right[3] - right[1])
                - intersection
            )
            assert intersection / max(1, union) <= 0.65


def test_region_ids_are_deterministic_and_sequential():
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    draw.line((FRAME[0], 210, FRAME[2], 210), fill=180, width=3)
    draw.line((210, FRAME[1], 210, 210), fill=180, width=3)
    gray = np.asarray(image)
    regions = _consensus(gray, PLAN_BOX)["regions"]
    assert [r["region_id"] for r in regions] == [
        f"r{index + 1}" for index in range(len(regions))
    ]
    assert regions == sorted(
        regions, key=lambda r: (r["bbox_pixels"][1], r["bbox_pixels"][0])
    )


def test_level_admitted_regions_carry_no_component_label():
    """Level-admitted regions must not be able to attract a furniture item."""
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    draw.line((FRAME[0], 210, FRAME[2], 210), fill=180, width=3)
    draw.line((210, FRAME[1], 210, 210), fill=180, width=3)
    gray = np.asarray(image)
    regions = _consensus(gray, PLAN_BOX)["regions"]
    for region in regions:
        if 190 in region["wall_levels"]:
            assert "label" not in region
        else:
            assert "label" in region


# --------------------------------------------------------------------------
# W2 — axis / grid recovery
# --------------------------------------------------------------------------

AXIS_BOX = [50, 120, 390, 400]


def _axis_sheet(markers):
    """`markers` = list of (cx, cy, radius, leader_segments)."""
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 130, 380, 390), outline=0, width=4)
    for cx, cy, radius, segments in markers:
        draw.ellipse(
            (cx - radius, cy - radius, cx + radius, cy + radius), outline=0, width=2
        )
        for y0, y1 in segments:
            draw.line((cx, y0, cx, y1), fill=0, width=1)
    return np.asarray(image)


def _fragmented(cx, cy, radius, gap):
    """A leader broken by one annotation-sized gap."""
    bottom = cy + radius
    end = AXIS_BOX[1]
    middle = (bottom + end) // 2
    return [(bottom, middle - gap // 2), (middle + gap // 2, end)]


def test_fragmented_leaders_still_ground_axes():
    markers = [
        (110, 100, 9, _fragmented(110, 100, 9, 8)),
        (200, 100, 9, _fragmented(200, 100, 9, 8)),
    ]
    found = _axes(cv2, _axis_sheet(markers), AXIS_BOX)
    assert len(found) == 2
    assert {item["geometry"]["orientation"] for item in found} == {"vertical"}


def test_unbroken_leaders_are_unchanged():
    markers = [
        (110, 100, 9, [(109, AXIS_BOX[1])]),
        (200, 100, 9, [(109, AXIS_BOX[1])]),
    ]
    found = _axes(cv2, _axis_sheet(markers), AXIS_BOX)
    assert len(found) == 2
    assert all(item["geometry"]["orientation"] == "vertical" for item in found)


def test_marker_without_a_leader_is_still_rejected():
    markers = [(110, 100, 9, []), (200, 100, 9, [])]
    assert _axes(cv2, _axis_sheet(markers), AXIS_BOX) == []


def test_a_perpendicular_dimension_line_is_not_a_leader():
    """A horizontal dimension line crossing the strip contributes no support."""
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 130, 380, 390), outline=0, width=4)
    for cx in (110, 200):
        draw.ellipse((cx - 9, 91, cx + 9, 109), outline=0, width=2)
        draw.line((cx - 30, 118, cx + 30, 118), fill=0, width=1)
    assert _axes(cv2, np.asarray(image), AXIS_BOX) == []


def test_leader_gap_repair_is_bounded():
    """A gap larger than the bound is not repaired into a false leader."""
    short = np.zeros(40, np.uint8)
    short[0:6] = 1
    short[30:36] = 1
    assert _leader_support(short, 4) == (6, 6)
    assert _leader_support(short, 30)[0] == 36


def test_leader_support_counts_only_real_ink():
    sparse = np.zeros(40, np.uint8)
    sparse[::12] = 1
    covered, support = _leader_support(sparse, 12)
    assert covered == 37
    assert support == 4
    assert support < covered


def test_leader_gap_fraction_is_explicit_and_bounded():
    assert 0 < AXIS_LEADER_MAX_GAP_FRACTION <= 1


def test_a_single_axis_orientation_is_still_not_a_grid():
    """A grid needs at least two axes of the same orientation."""
    markers = [(110, 100, 9, _fragmented(110, 100, 9, 8))]
    assert _axes(cv2, _axis_sheet(markers), AXIS_BOX) == []


def test_columns_still_require_both_axis_orientations():
    """No single-axis column fallback was introduced in this phase."""
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 130, 380, 390), outline=0, width=4)
    # A grid of solid blocks with only vertical axis markers available.
    for x in range(100, 360, 60):
        for y in range(170, 370, 60):
            draw.rectangle((x - 6, y - 6, x + 6, y + 6), fill=0)
    gray = np.asarray(image)
    axes = _axes(cv2, gray, AXIS_BOX)
    assert all(item["geometry"]["orientation"] == "vertical" for item in axes)
    for index, item in enumerate(axes):
        item["element_id"] = f"axis{index + 1}"
    assert _columns(cv2, gray, AXIS_BOX, axes) == []


@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_axis_evidence_records_orientation_and_a_line(orientation):
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 130, 380, 390), outline=0, width=4)
    if orientation == "vertical":
        box = AXIS_BOX
        for cx in (110, 200):
            draw.ellipse((cx - 9, 91, cx + 9, 109), outline=0, width=2)
            for y0, y1 in _fragmented(cx, 100, 9, 8):
                draw.line((cx, y0, cx, y1), fill=0, width=1)
    else:
        # The markers sit well left of the plan box so the leader strip has room.
        box = [110, 120, 390, 400]
        for cy in (200, 300):
            draw.ellipse((31, cy - 9, 49, cy + 9), outline=0, width=2)
            draw.line((49, cy, 70, cy), fill=0, width=1)
            draw.line((76, cy, 105, cy), fill=0, width=1)
    found = _axes(cv2, np.asarray(image), box)
    assert found
    assert all(item["geometry"]["orientation"] == orientation for item in found)
    assert all(len(item["geometry"]["line_pixels"]) == 2 for item in found)
    assert all(len(item["corroboration"]) >= 3 for item in found)
