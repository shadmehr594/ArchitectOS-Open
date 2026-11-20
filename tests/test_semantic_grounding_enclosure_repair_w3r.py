"""W3R — SEMANTIC GROUNDING CLEANUP + ENCLOSURE COVERAGE REPAIR.

Two defects are repaired here, generally:

1. **A drawing graphic is not text.**  A wall/hatch/dimension crossing could be
   read as a Persian room label: on D a wall junction produced `ترس`, scored
   0.857 against `تراس` and was published as the plan's only named space,
   although its bbox contains no readable text.  A region whose ink carries a
   horizontal run spanning half its width AND a vertical run spanning half its
   height at the same time is such a junction, and is now rejected — rejection
   only, so the gate can never invent a label.

2. **An uninformative level is not a contradiction.**  A room that a higher
   wall level CLOSES but a lower higher level merges with the drawing's
   exterior was rejected by the cross-level consensus, so D's two large bottom
   rooms were lost.  Such a level carries no evidence about the room; it is
   skipped instead of counted against it.  A level that instead shows a
   different BOUNDED room there is a genuine subdivision and still contradicts,
   so threshold instability can never blindly admit a region.

Every non-image fixture is synthetic.  The real-image tests skip unless
``ARCHITECTOS_PLAN_A/B/C/D`` are provided.
"""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from core.vision.local_plan_reader_v1 import (
    _drawing_line_structure,
    _read_raster,
    _reject_graphic_labels,
    read_local_plan,
)
from core.vision.local_plan_sheet_v1 import (
    DIMENSION_PLAN,
    FURNISHED_ARCHITECTURAL_PLAN,
    grounded_sheet_structure,
)
from core.vision.local_plan_symbols_v1 import (
    ENCLOSURE_LEVEL_MIN_AREA_FRACTION,
    ENCLOSURE_WALL_LEVELS,
    _candidates,
    _enclosure_consensus,
    _enclosures,
    _walls,
)
from core.vision.small_architectural_text_v1 import (
    SMALL_TEXT_MIN_GLYPH_HEIGHT,
    SMALL_TEXT_MIN_RECOVERABLE_GLYPH_HEIGHT,
    SMALL_TEXT_RECOVERY_ENABLED,
    localize_small_text,
    recovery_disabled_audit,
)

CANVAS = 420
FRAME = (40, 40, 380, 380)
PLAN_BOX = [36, 36, 384, 384]
DARK = ENCLOSURE_WALL_LEVELS[0]
# Ink at the highest level only: invisible to 165 and 190, a wall at 215.
FAINT = 200

PATHS = {
    key: Path(os.environ.get("ARCHITECTOS_PLAN_" + key, "__missing_private_image__"))
    for key in "ABCD"
}


@pytest.fixture(scope="module")
def four_images():
    if not all(p.is_file() for p in PATHS.values()):
        pytest.skip("Provide private ARCHITECTOS_PLAN_A/B/C/D for the real acceptance checks")
    return {key: read_local_plan(path) for key, path in PATHS.items()}


def _consensus(gray, box):
    dark = []
    for threshold in (DARK, 180, 155):
        dark += _candidates(cv2, gray, box, threshold)[0]
    return _enclosure_consensus(cv2, gray, box, dark)[0]


def _baseline(gray, box):
    return _enclosures(
        cv2, _walls(cv2, (gray < DARK).astype(np.uint8), box, True), box
    )[0]


def _admitted(consensus):
    return [
        region
        for region in consensus["regions"]
        if any(level in region["wall_levels"] for level in ENCLOSURE_WALL_LEVELS[1:])
    ]


def _leaking_plan(bottom_value=FAINT, partition=None):
    """A plan whose bottom room leaks to the exterior until the top level.

    The perimeter's bottom edge is drawn faint, so at 165/190 the lower room's
    free space escapes the drawing and at 215 the edge closes it.  An optional
    faint internal partition can subdivide the lower room at 215 only.
    """
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    draw.line((FRAME[0], FRAME[1], FRAME[2], FRAME[1]), fill=0, width=5)
    draw.line((FRAME[0], FRAME[1], FRAME[0], FRAME[3]), fill=0, width=5)
    draw.line((FRAME[2], FRAME[1], FRAME[2], FRAME[3]), fill=0, width=5)
    draw.line((FRAME[0], FRAME[3], FRAME[2], FRAME[3]), fill=bottom_value, width=4)
    draw.line((FRAME[0], 210, FRAME[2], 210), fill=0, width=4)
    draw.line((210, FRAME[1], 210, 210), fill=0, width=4)
    if partition is not None:
        draw.line((partition, 216, partition, FRAME[3] - 6), fill=FAINT, width=3)
    return np.asarray(image)


# --------------------------------------------------------------------------
# 1. a wall/hatch graphic cannot become a room label
# --------------------------------------------------------------------------


def test_a_wall_junction_region_is_not_text():
    gray = np.full((120, 120), 255, np.uint8)
    cv2.line(gray, (5, 60), (115, 60), 0, 3)
    cv2.line(gray, (60, 5), (60, 115), 0, 3)
    assert _drawing_line_structure(gray, [5, 5, 115, 115]) is True


def test_a_hatched_region_is_not_text():
    gray = np.full((120, 120), 255, np.uint8)
    for y in range(6, 118, 12):
        cv2.line(gray, (3, y), (117, y), 0, 1)
    cv2.line(gray, (60, 3), (60, 117), 0, 1)
    assert _drawing_line_structure(gray, [3, 3, 117, 117]) is True


def test_a_junction_read_as_teras_is_rejected_by_the_reader_gate():
    """The exact defect: a junction OCR'd as `تراس` must not survive."""
    gray = np.full((120, 120), 255, np.uint8)
    cv2.line(gray, (5, 60), (115, 60), 0, 3)
    cv2.line(gray, (60, 5), (60, 115), 0, 3)
    label = {
        "text": "تراس",
        "semantic_function": "balcony",
        "raw_ocr": "ترس",
        "match_score": 0.857,
        "bbox_pixels": [5.0, 5.0, 115.0, 115.0],
        "confidence": "MEDIUM",
    }
    grounded, graphic = _reject_graphic_labels(gray, [label])
    assert grounded == []
    assert [entry["text"] for entry in graphic] == ["تراس"]


def test_a_region_too_small_for_text_is_never_rejected():
    """The gate needs a region large enough to hold text; tiny boxes pass."""
    gray = np.full((40, 40), 255, np.uint8)
    cv2.line(gray, (2, 2), (38, 2), 0, 1)
    cv2.line(gray, (2, 2), (2, 38), 0, 1)
    assert _drawing_line_structure(gray, [2, 2, 10, 9]) is False


# --------------------------------------------------------------------------
# 2. legitimate architectural text still survives
# --------------------------------------------------------------------------


def test_a_row_of_short_strokes_is_still_text():
    gray = np.full((40, 160), 255, np.uint8)
    for x in range(6, 150, 12):
        cv2.line(gray, (x, 8), (x, 30), 0, 2)
        cv2.line(gray, (x, 20), (x + 6, 20), 0, 2)
    assert _drawing_line_structure(gray, [2, 4, 158, 36]) is False


def test_a_rendered_word_is_still_text():
    image = Image.new("L", (160, 40), 255)
    draw = ImageDraw.Draw(image)
    draw.text((6, 10), "LIVING AREA", font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 14), fill=0)
    gray = np.asarray(image)
    assert _drawing_line_structure(gray, [4, 6, 156, 34]) is False


def test_real_A_keeps_every_persian_label(four_images):
    labels = four_images["A"]["labels"]
    assert len(labels) == 9
    assert all(entry["semantic_function"] for entry in labels)
    assert all(
        any("\u0600" <= ch <= "\u06ff" for ch in entry["text"]) for entry in labels
    )
    assert not (four_images["A"].get("rejected_graphic_ocr_labels") or [])


def test_real_D_publishes_no_graphic_as_a_named_space(four_images):
    from core.vision.architectural_vision_interpreter_v1 import (
        interpret_architectural_vision,
    )
    from core.vision.image_understanding_v1 import build_understanding

    local = four_images["D"]
    sheet = grounded_sheet_structure(local)
    assert sheet
    grounded = [
        entry
        for panel in sheet["panels"]
        for entry in panel["local_plan_reading"]["labels"]
    ]
    assert grounded == []
    raw = {"image_type": "floor_plan_or_sketch", "local_plan_reading": local}
    plan = interpret_architectural_vision(
        build_understanding(raw, provider="stub", model="stub")
    )["plan_reading"]
    assert plan.get("named_spaces") == []
    assert plan["fusion"]["corresponding_label_transfers"] == []


# --------------------------------------------------------------------------
# 3. the real lower enclosure survives the corrected consensus
# --------------------------------------------------------------------------


def test_a_room_closed_only_by_the_higher_level_is_admitted():
    gray = _leaking_plan()
    consensus = _consensus(gray, PLAN_BOX)
    admitted = _admitted(consensus)
    assert admitted
    for region in admitted:
        assert 215 in region["wall_levels"]
        assert region["confidence"] == "MEDIUM"
        assert region["stable_across_gap_scales"] is True
        assert "cross_level_wall_support" in region["corroboration"]


def test_a_closed_bottom_edge_needs_no_extra_admission():
    """Control: with a dark bottom edge the room is baseline, nothing is added."""
    gray = _leaking_plan(bottom_value=0)
    baseline = _baseline(gray, PLAN_BOX)
    consensus = _consensus(gray, PLAN_BOX)
    assert consensus["level_admitted_count"] == 0
    assert len(consensus["regions"]) == len(baseline["regions"])


def test_real_D_lower_rooms_are_recovered(four_images):
    sheet = grounded_sheet_structure(four_images["D"])
    assert sheet
    p1 = next(panel for panel in sheet["panels"] if panel["panel_id"] == "p1")
    assert p1["role"] == DIMENSION_PLAN
    local = p1["local_plan_reading"]
    regions = local["enclosure_geometry"]["regions"]
    assert len(regions) == 23
    plan = local["plan_bbox_pixels"]
    middle = (plan[1] + plan[3]) / 2.0
    # The two large bottom rooms are admitted by the level that CLOSES them.
    admitted = [region for region in regions if 215 in region["wall_levels"]]
    assert len(admitted) == 2
    for region in admitted:
        x0, y0, x1, y1 = region["bbox_pixels"]
        assert y0 > middle
        assert x1 - x0 >= 100 and y1 - y0 >= 100
    # The lower half is covered, not just the top: three regions start below
    # the vertical middle of the plan.
    assert len([r for r in regions if r["bbox_pixels"][1] > middle]) >= 3


# --------------------------------------------------------------------------
# 4. higher-threshold noise/hatching still does not become rooms
# --------------------------------------------------------------------------


def test_hatching_that_only_appears_at_a_higher_level_creates_no_room():
    image = Image.new("L", (CANVAS, CANVAS), 255)
    draw = ImageDraw.Draw(image)
    draw.line((FRAME[0], FRAME[1], FRAME[2], FRAME[1]), fill=0, width=5)
    draw.line((FRAME[0], FRAME[1], FRAME[0], FRAME[3]), fill=0, width=5)
    draw.line((FRAME[2], FRAME[1], FRAME[2], FRAME[3]), fill=0, width=5)
    draw.line((FRAME[0], FRAME[3], FRAME[2], FRAME[3]), fill=0, width=5)
    # A faint hatched band across the middle of the single room.
    for y in range(180, 240, 12):
        draw.line((FRAME[0] + 10, y, FRAME[2] - 10, y), fill=FAINT, width=3)
    gray = np.asarray(image)
    plan_area = (PLAN_BOX[2] - PLAN_BOX[0]) * (PLAN_BOX[3] - PLAN_BOX[1])
    consensus = _consensus(gray, PLAN_BOX)
    for region in _admitted(consensus):
        # An admitted region must be a substantial space, never a hatched sliver.
        assert region["pixel_area"] >= plan_area * ENCLOSURE_LEVEL_MIN_AREA_FRACTION
        x0, y0, x1, y1 = region["bbox_pixels"]
        assert not (y0 >= 176 and y1 <= 244), region["bbox_pixels"]


# --------------------------------------------------------------------------
# 5. threshold instability does not blindly admit regions
# --------------------------------------------------------------------------


def test_a_faint_partition_that_only_one_level_sees_admits_nothing():
    """The 215 level splits a room the 190 level still holds whole.

    The halves are CONTRADICTED (their centres lie in a different bounded
    region at 190), so neither is admitted; the room survives once, from the
    baseline.  This is the guard against 'admit everything from 215'.
    """
    gray = _leaking_plan(bottom_value=0, partition=210)
    consensus = _consensus(gray, PLAN_BOX)
    assert consensus["level_admitted_count"] == 0
    assert all(215 not in region["wall_levels"] for region in consensus["regions"])
    lower = [r for r in consensus["regions"] if r["bbox_pixels"][1] > 210]
    assert len(lower) == 1


def test_the_relaxation_never_applies_to_a_subdivision():
    """Only the exterior case is skipped; a bounded room still contradicts."""
    gray = _leaking_plan(bottom_value=0, partition=210)
    consensus = _consensus(gray, PLAN_BOX)
    # The whole lower room is present exactly once and carries no level support.
    lower = [r for r in consensus["regions"] if r["bbox_pixels"][1] > 210]
    assert lower and lower[0]["wall_levels"] == [DARK]


# --------------------------------------------------------------------------
# 6. the W3.5 recovery is gated by measured recoverability
# --------------------------------------------------------------------------


def _labelled_plan(font_size):
    image = Image.new("L", (520, 520), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle([40, 40, 480, 480], outline=0, width=2)
    draw.line([(40, 260), (480, 260)], fill=0, width=2)
    draw.line([(260, 40), (260, 480)], fill=0, width=2)
    draw.text(
        (70, 180), "PATIO",
        font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size), fill=0,
    )
    return np.asarray(image, dtype=np.uint8)


def test_w35_recovery_is_disabled_by_default_and_costs_nothing():
    assert SMALL_TEXT_RECOVERY_ENABLED is False
    audit = recovery_disabled_audit()
    assert audit["status"] == "disabled"
    assert audit["candidates"] == 0
    assert audit["ocr_calls"] == 0
    assert audit["readings"] == 0


def test_w35_localizer_never_proposes_a_candidate_below_recoverability():
    """The measured floor: the synthetic fixtures recover from 6 px upward."""
    from core.vision.local_plan_reader_v1 import _plan_bbox

    assert SMALL_TEXT_MIN_GLYPH_HEIGHT == SMALL_TEXT_MIN_RECOVERABLE_GLYPH_HEIGHT
    assert SMALL_TEXT_MIN_RECOVERABLE_GLYPH_HEIGHT == 6
    readable = _labelled_plan(9)
    assert localize_small_text(readable, _plan_bbox(readable))
    for font_size in (4, 5, 9):
        gray = _labelled_plan(font_size)
        for candidate in localize_small_text(gray, _plan_bbox(gray)):
            assert candidate["glyph_height_px"] >= SMALL_TEXT_MIN_RECOVERABLE_GLYPH_HEIGHT


def _small_text_audits(local):
    """The recovery audit(s) of a reading, at top level or per panel."""
    audits = []
    if local.get("small_architectural_text") is not None:
        audits.append(local["small_architectural_text"])
    for panel in (local.get("sheet_structure") or {}).get("panels") or []:
        audit = (panel.get("local_plan_reading") or {}).get("small_architectural_text")
        if audit is not None:
            audits.append(audit)
    return audits


def test_real_panels_spend_no_small_text_ocr_by_default(four_images):
    for key in "ABCD":
        audits = _small_text_audits(four_images[key])
        assert audits
        for audit in audits:
            assert audit["status"] == "disabled"
            assert audit["ocr_calls"] == 0


# --------------------------------------------------------------------------
# A/B/C/D acceptance is non-regressed
# --------------------------------------------------------------------------


def test_real_A_B_C_roles_and_counts_do_not_regress(four_images):
    for key in "ABC":
        assert four_images[key]["sheet_structure"]["sheet_type"] == "single_plan"
    assert len(four_images["A"]["labels"]) == 9
    assert four_images["A"]["furniture_evidence"] == []
    assert len(four_images["B"]["furniture_evidence"]) == 11
    assert len(four_images["C"]["furniture_evidence"]) == 4


def test_real_D_roles_and_native_furniture_are_unchanged(four_images):
    sheet = grounded_sheet_structure(four_images["D"])
    assert sheet
    roles = {panel["panel_id"]: panel["role"] for panel in sheet["panels"]}
    assert roles == {
        "p1": DIMENSION_PLAN,
        "p2": FURNISHED_ARCHITECTURAL_PLAN,
    }
    assert sum(
        len(panel["local_plan_reading"]["furniture_evidence"])
        for panel in sheet["panels"]
    ) == 2
    for panel in sheet["panels"]:
        for item in panel["local_plan_reading"]["furniture_evidence"]:
            assert item["region_ids"] == []
