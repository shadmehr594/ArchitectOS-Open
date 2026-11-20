"""FURNITURE / FUNCTION GENERALIZATION V1 — focused, image-independent tests.

Every fixture here is drawn synthetically. Nothing depends on the private
acceptance images, their filenames, or any fixed count from them.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw

from core.vision.local_plan_reader_v1 import _plan_bbox
from core.vision.local_plan_symbols_v1 import (
    FUNCTIONS,
    LIGHT_LINE_CLASSES,
    analyze_plan_symbols,
    grounded_plan_items,
)


def _canvas(size=420):
    return Image.new("L", (size, size), 255)


def _plan_frame(draw, box=(40, 40, 380, 380), width=5):
    draw.rectangle(box, outline=0, width=width)


def _sleeping_symbol(draw, x, y, w=44, h=78, value=0, pillows=True):
    """Closed outline with a terminal pillow row — a common bed convention."""
    draw.rectangle((x, y, x + w, y + h), outline=value, width=1)
    if pillows:
        pw = int(w * 0.38)
        ph = int(h * 0.13)
        draw.rectangle((x + 3, y + 5, x + 3 + pw, y + 5 + ph), outline=value, width=1)
        draw.rectangle(
            (x + w - 3 - pw, y + 5, x + w - 3, y + 5 + ph), outline=value, width=1
        )


def _classes(gray):
    out = analyze_plan_symbols(np.asarray(gray), _plan_bbox(np.asarray(gray)))
    return [item["class"] for item in out["furniture_evidence"]]


def test_light_line_sleeping_symbol_is_grounded():
    """Furniture drawn lighter than the walls is still a supported symbol."""
    image = _canvas()
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    _sleeping_symbol(draw, 160, 150, value=200)
    assert "bed" in _classes(image)


def test_dark_line_sleeping_symbol_is_grounded():
    image = _canvas()
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    _sleeping_symbol(draw, 160, 150, value=0)
    assert "bed" in _classes(image)


def test_empty_framed_room_has_no_furniture():
    image = _canvas()
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    assert _classes(image) == []


def test_hatched_room_is_not_furniture():
    """Repetitive floor/stair hatching must not be promoted to an object."""
    image = _canvas()
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    for x in range(120, 300, 9):
        draw.line((x, 150, x, 300), fill=0)
    assert _classes(image) == []


def test_bare_rectangle_without_pillows_is_not_a_bed():
    """Ambiguous geometry stays unclassified rather than being forced."""
    image = _canvas()
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    draw.rectangle((160, 150, 204, 228), outline=0, width=1)
    assert "bed" not in _classes(image)


@pytest.mark.parametrize("scale", [0.7, 1.0, 1.5])
def test_scale_variation_keeps_the_sleeping_symbol(scale):
    base = _canvas(420)
    draw = ImageDraw.Draw(base)
    _plan_frame(draw)
    _sleeping_symbol(draw, 160, 150)
    resized = base.resize((int(420 * scale), int(420 * scale)), Image.LANCZOS)
    assert "bed" in _classes(resized)


def test_light_line_pass_is_restricted_to_structural_classes():
    """The loose upholstery classes must never come from the light-line pass."""
    assert {"sofa", "seating", "chair"}.isdisjoint(LIGHT_LINE_CLASSES)
    assert {"bed", "dining_surface", "kitchen_counter"} <= LIGHT_LINE_CLASSES


def test_provider_only_furniture_cannot_be_promoted():
    """A provider claim with no local evidence yields no grounded furniture."""
    local = {
        "symbol_analysis_status": "analyzed",
        "image_size": {"width": 300, "height": 300},
        "furniture_evidence": [],
    }
    assert grounded_plan_items(local) == []


@pytest.mark.parametrize(
    "mutation",
    ["source", "confidence", "corroboration", "hash", "status", "provider_flag"],
)
def test_item_contract_rejects_bad_evidence(mutation):
    item = {
        "class": "bed",
        "bbox_pixels": [10, 10, 60, 90],
        "status": "visible",
        "confidence": "MEDIUM",
        "source": "local_raster_symbol_topology",
        "provider_independent": True,
        "corroboration": ["a", "b", "c"],
        "raster_patch_sha256": "0" * 64,
    }
    if mutation == "source":
        item["source"] = "provider_only"
    elif mutation == "confidence":
        item["confidence"] = "LOW"
    elif mutation == "corroboration":
        item["corroboration"] = ["a"]
    elif mutation == "hash":
        item["raster_patch_sha256"] = ""
    elif mutation == "status":
        item["status"] = "candidate"
    else:
        item["provider_independent"] = False
    local = {
        "symbol_analysis_status": "analyzed",
        "image_size": {"width": 300, "height": 300},
        "furniture_evidence": [item],
    }
    assert grounded_plan_items(local) == []


def test_every_grounded_class_maps_into_the_function_taxonomy():
    for name, function in FUNCTIONS.items():
        assert function is None or isinstance(function, str)
    assert set(FUNCTIONS) >= {"bed", "sofa", "seating", "chair", "dining_surface"}


def test_detector_records_the_thresholds_that_supported_each_item():
    image = _canvas()
    draw = ImageDraw.Draw(image)
    _plan_frame(draw)
    _sleeping_symbol(draw, 160, 150, value=200)
    out = analyze_plan_symbols(np.asarray(image), _plan_bbox(np.asarray(image)))
    for item in out["furniture_evidence"]:
        assert len(item["thresholds"]) >= 2
        assert "stable_at_two_thresholds" in item["corroboration"]
