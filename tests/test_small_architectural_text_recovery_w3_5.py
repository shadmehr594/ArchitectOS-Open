"""W3.5 — SMALL ARCHITECTURAL TEXT RECOVERY.

Every fixture here is synthetic (a rendered plan raster); nothing depends on the
private acceptance images, their filenames, or any fixed count from them. The
two real-image tests skip unless ``ARCHITECTOS_PLAN_A/B/C/D`` are provided.

The suite pins the SEMANTICS the brief specifies, not the implementation: the
recovery layer must recover genuinely visible small architectural text, must
preserve provenance, must never invent a reading from a lexical prior, must not
promote axis identifiers or dimension numbers, must leave the Persian path
alone, and must not regress A/B/C.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from core.vision.local_plan_reader_v1 import (
    _architectural_label_matches,
    _label_matches,
    _plan_bbox,
    _read_raster,
    read_local_plan,
)
from core.vision.local_plan_sheet_v1 import (
    DIMENSION_PLAN,
    FURNISHED_ARCHITECTURAL_PLAN,
    analyze_sheet,
    detect_sheet,
    grounded_sheet_structure,
)
from core.vision.small_architectural_text_v1 import (
    CONTRACT,
    RECOVERY_ID,
    SMALL_TEXT_LANGUAGES,
    SMALL_TEXT_MAX_CANDIDATES,
    SMALL_TEXT_PSM_MODES,
    SMALL_TEXT_UPSCALES,
    SMALL_TEXT_VARIANTS,
    VERSION,
    _consolidate,
    _lexical_plausibility,
    _text_plausible,
    localize_small_text,
    recover_small_architectural_readings,
)

FONT_PATH = "C:/Windows/Fonts/arial.ttf"

PLAN_BOX = [40.0, 40.0, 480.0, 480.0]

PATHS = {
    key: Path(os.environ.get("ARCHITECTOS_PLAN_" + key, "__missing_private_image__"))
    for key in "ABCD"
}


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


def _plan_image(labels, *, font_size=11, canvas=520, divider=True):
    """A white plan with a wall outline and small rendered labels."""
    image = Image.new("L", (canvas, canvas), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle([40, 40, 480, 480], outline=0, width=2)
    if divider:
        draw.line([(40, 260), (480, 260)], fill=0, width=2)
        draw.line([(260, 40), (260, 480)], fill=0, width=2)
    font = ImageFont.truetype(FONT_PATH, font_size)
    for text, (x, y) in labels:
        draw.text((x, y), text, font=font, fill=0)
    return np.asarray(image, dtype=np.uint8)


def _single_label(text, **kwargs):
    return _plan_image([(text, (70, 180))], **kwargs)


def _plan_drawing(width):
    """A partitioned plan drawing so sheet detection finds a real panel."""
    image = Image.new("L", (width, 360), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, width - 10, 350), outline=0, width=4)
    draw.line((10, 120, width - 10, 120), fill=0, width=4)
    draw.line((10, 240, width - 10, 240), fill=0, width=4)
    draw.line((width // 2, 10, width // 2, 240), fill=0, width=4)
    return np.asarray(image)


def _two_panel_sheet():
    """A wide (260 px) and a narrow (200 px) drawing side by side."""
    sheet = np.full((420, 660), 255, np.uint8)
    sheet[20:380, 20:280] = _plan_drawing(260)
    sheet[20:380, 380:580] = _plan_drawing(200)
    return sheet


def _recover(gray):
    return recover_small_architectural_readings(gray, None, None)


def _texts(readings):
    return {r["raw_text"].upper() for r in readings}


def _labels_from(readings, gray):
    try:
        box = _plan_bbox(gray)
    except Exception:
        box = [0.0, 0.0, float(gray.shape[1]), float(gray.shape[0])]
    return _architectural_label_matches(readings, box, gray.shape)


# --------------------------------------------------------------------------
# 1-4. tiny architectural labels are genuinely recovered
# --------------------------------------------------------------------------


@pytest.mark.parametrize("size", [9, 10, 11, 12])
def test_tiny_single_word_architectural_label_is_recovered(size):
    gray = _single_label("PATIO", font_size=size)
    readings, audit = _recover(gray)
    assert audit["status"] == "analyzed"
    assert audit["candidates"] >= 1
    assert "PATIO" in _texts(readings)
    assert [entry["semantic_function"] for entry in _labels_from(readings, gray)] == ["patio"]


@pytest.mark.parametrize("size", [9, 11])
def test_tiny_two_word_label_living_area_is_recovered(size):
    gray = _single_label("LIVING AREA", font_size=size)
    readings, _ = _recover(gray)
    assert "LIVING AREA" in _texts(readings)
    assert [entry["semantic_function"] for entry in _labels_from(readings, gray)] == ["living room"]


def test_bedroom_label_is_recovered():
    gray = _single_label("BEDROOM")
    readings, _ = _recover(gray)
    assert "BEDROOM" in _texts(readings)
    assert [entry["semantic_function"] for entry in _labels_from(readings, gray)] == ["bedroom"]


def test_kitchen_label_is_recovered():
    gray = _single_label("KITCHEN")
    readings, _ = _recover(gray)
    assert "KITCHEN" in _texts(readings)
    assert [entry["semantic_function"] for entry in _labels_from(readings, gray)] == ["kitchen"]


def test_all_four_labels_on_one_plan_are_recovered():
    gray = _plan_image([
        ("LIVING AREA", (70, 180)),
        ("BEDROOM", (70, 300)),
        ("KITCHEN", (300, 300)),
        ("PATIO", (300, 180)),
    ])
    readings, _ = _recover(gray)
    assert {"LIVING AREA", "BEDROOM", "KITCHEN", "PATIO"} <= _texts(readings)


# --------------------------------------------------------------------------
# 5. PATIO is recovered as TEXT and never forces enclosure grounding
# --------------------------------------------------------------------------


def test_patio_text_is_recovered_but_never_forces_enclosure_grounding():
    # (a) the text is genuinely recovered and lexically mapped ...
    gray = _single_label("PATIO")
    readings, _ = _recover(gray)
    accepted = _labels_from(readings, gray)
    assert [entry["semantic_function"] for entry in accepted] == ["patio"]

    # (b) ... but with no MEDIUM enclosure region containing it, the sheet
    # association must quarantine it rather than invent a room.
    label = {
        "text": "PATIO",
        "semantic_function": "patio",
        "bbox_pixels": [200.0, 200.0, 260.0, 214.0],
        "confidence": "MEDIUM",
    }
    result = analyze_sheet(
        _two_panel_sheet(), detect_sheet(_two_panel_sheet()),
        _stub_reader([label], regions=[]), None,
    )
    for panel in result["sheet_structure"]["panels"]:
        assert panel["local_plan_reading"]["labels"] == []
        reasons = {entry["reason"] for entry in panel["quarantined_annotations"]}
        assert "no_enclosure_region_contains_label_centroid" in reasons


# --------------------------------------------------------------------------
# 6-8. noise / axis / dimension rejection
# --------------------------------------------------------------------------


def test_low_resolution_random_glyph_noise_is_rejected():
    rng = np.random.default_rng(20261007)
    gray = np.full((420, 420), 255, np.uint8)
    gray[40:380, 40:380] = rng.integers(120, 256, size=(340, 340), dtype=np.uint8)
    readings, _ = _recover(gray)
    assert _labels_from(readings, gray) == []


def test_dimension_numbers_are_not_promoted_to_room_labels():
    gray = _plan_image([("350", (70, 180)), ("1/100", (70, 300)), ("2650", (300, 300))])
    readings, _ = _recover(gray)
    assert _labels_from(readings, gray) == []


@pytest.mark.parametrize("axis_text", ["A", "B", "G", "1", "6", "2.5"])
def test_axis_letters_and_numbers_are_still_rejected(axis_text):
    gray = _single_label(axis_text, font_size=14)
    readings, _ = _recover(gray)
    assert _labels_from(readings, gray) == []


def test_a_stray_fragment_inside_a_longer_word_does_not_name_a_space():
    # `ALL` inside `WALLY` must not score against `HALL`.
    readings = [{
        "raw_text": "WALLY",
        "ocr_confidence": 90.0,
        "bbox_pixels": [100.0, 100.0, 160.0, 120.0],
        "pass": "synthetic",
    }]
    assert _architectural_label_matches(readings, PLAN_BOX, (420, 420)) == []


# --------------------------------------------------------------------------
# 9. the Persian path is unchanged
# --------------------------------------------------------------------------


def test_persian_labels_remain_unchanged():
    readings = [
        {"raw_text": "اتاق خواب", "ocr_confidence": 80.0,
         "bbox_pixels": [100.0, 100.0, 160.0, 120.0], "pass": "p"},
        {"raw_text": "آشپزخانه", "ocr_confidence": 80.0,
         "bbox_pixels": [100.0, 200.0, 170.0, 220.0], "pass": "p"},
    ]
    persian = _label_matches(readings, PLAN_BOX, (420, 420))
    assert {entry["semantic_function"] for entry in persian} == {"bedroom", "kitchen"}
    # The Latin recovery path must not claim readings the Persian path owns.
    assert _architectural_label_matches(readings, PLAN_BOX, (420, 420)) == []


def test_recovery_never_emits_a_lone_persian_fragment():
    # A Persian reading needs independent-variant agreement; a single pass is
    # dropped, so the recovery cannot inject a Persian false positive.
    entries = [{
        "text_key": "ترس", "raw_text": "ترس", "ocr_confidence": 60.0,
        "variant": SMALL_TEXT_VARIANTS[0], "language": "fas+eng",
        "psm_mode": SMALL_TEXT_PSM_MODES[0], "upscale": SMALL_TEXT_UPSCALES[0],
        "bbox_pixels": [0.0, 0.0, 10.0, 10.0],
    }]
    assert _consolidate(entries) == []
    agreed = entries + [dict(entries[0], variant=SMALL_TEXT_VARIANTS[1])]
    assert len(_consolidate(agreed)) == 1


# --------------------------------------------------------------------------
# 10-13. provenance is preserved
# --------------------------------------------------------------------------


def test_source_and_native_bbox_provenance_is_preserved():
    gray = _single_label("PATIO")
    readings, _ = _recover(gray)
    assert readings
    for reading in readings:
        assert reading["recovery"] == RECOVERY_ID
        assert reading["source_bbox_frame"] == "native_panel_pixels"
        source = reading["source_crop_bbox"]
        assert source[0] < source[2] and source[1] < source[3]
        assert reading["native_glyph_height_px"] > 0
        assert reading["bbox_pixels"] == [
            round(source[0], 1), round(source[1], 1), round(source[2], 1), round(source[3], 1),
        ]


def test_bbox_scale_maps_the_recovered_box_into_the_caller_frame():
    gray = _single_label("PATIO")
    box = _plan_bbox(gray)
    readings, _ = recover_small_architectural_readings(gray, box, None, bbox_scale=(2.0, 3.0))
    assert readings
    for reading in readings:
        source = reading["source_crop_bbox"]
        assert reading["bbox_pixels"] == [
            round(source[0] * 2.0, 1), round(source[1] * 3.0, 1),
            round(source[2] * 2.0, 1), round(source[3] * 3.0, 1),
        ]


def test_preprocessing_provenance_is_preserved():
    gray = _single_label("KITCHEN")
    readings, _ = _recover(gray)
    assert readings
    for reading in readings:
        assert reading["preprocessing_variant"] in SMALL_TEXT_VARIANTS
        assert reading["upscale"] in SMALL_TEXT_UPSCALES


def test_psm_provenance_is_preserved():
    gray = _single_label("BEDROOM")
    readings, _ = _recover(gray)
    assert readings
    for reading in readings:
        assert reading["psm_mode"] in SMALL_TEXT_PSM_MODES


def test_language_provenance_is_preserved():
    gray = _single_label("LIVING AREA")
    readings, _ = _recover(gray)
    assert readings
    for reading in readings:
        assert reading["ocr_language"] in SMALL_TEXT_LANGUAGES


def test_audit_records_the_bounded_strategy_and_cost():
    gray = _single_label("PATIO")
    _, audit = _recover(gray)
    assert audit["contract"] == CONTRACT
    assert audit["version"] == VERSION
    assert audit["variants"] == list(SMALL_TEXT_VARIANTS)
    assert audit["upscales"] == list(SMALL_TEXT_UPSCALES)
    assert audit["psm_modes"] == list(SMALL_TEXT_PSM_MODES)
    assert audit["languages"] == list(SMALL_TEXT_LANGUAGES)
    assert audit["candidates"] <= SMALL_TEXT_MAX_CANDIDATES
    assert audit["ocr_calls"] > 0


# --------------------------------------------------------------------------
# 14. consolidation is deterministic
# --------------------------------------------------------------------------


def test_duplicate_candidates_consolidate_deterministically():
    base = {
        "text_key": "PATIO", "raw_text": "PATIO", "ocr_confidence": 40.0,
        "language": "eng", "psm_mode": SMALL_TEXT_PSM_MODES[0],
        "upscale": SMALL_TEXT_UPSCALES[0], "bbox_pixels": [0.0, 0.0, 10.0, 10.0],
    }
    entries = [
        dict(base, variant=SMALL_TEXT_VARIANTS[0]),
        dict(base, variant=SMALL_TEXT_VARIANTS[1], ocr_confidence=55.0),
        dict(base, variant=SMALL_TEXT_VARIANTS[2]),
    ]
    first = _consolidate(entries)
    second = _consolidate(list(reversed(entries)))
    assert len(first) == 1
    assert first[0]["agreement"] == 3
    assert first[0]["representative"]["ocr_confidence"] == 55.0
    assert [g["text_key"] for g in first] == [g["text_key"] for g in second]
    assert first[0]["agreement"] == second[0]["agreement"]


def test_conflicting_readings_rank_the_architectural_one_first():
    base = {
        "raw_text": "", "ocr_confidence": 99.0, "language": "eng",
        "psm_mode": SMALL_TEXT_PSM_MODES[0], "upscale": SMALL_TEXT_UPSCALES[0],
        "bbox_pixels": [0.0, 0.0, 10.0, 10.0],
    }
    entries = [
        dict(base, text_key="XQZW", raw_text="XQZW", variant=SMALL_TEXT_VARIANTS[0]),
        dict(base, text_key="PATIO", raw_text="PATIO", variant=SMALL_TEXT_VARIANTS[1]),
    ]
    ranked = _consolidate(entries)
    assert ranked[0]["text_key"] == "PATIO"


# --------------------------------------------------------------------------
# 15. the lexical prior cannot create text
# --------------------------------------------------------------------------


def test_lexical_prior_cannot_create_text_without_ocr_support():
    blank = np.full((420, 420), 255, np.uint8)
    readings, audit = _recover(blank)
    assert readings == []
    assert audit["candidates"] == 0
    # `_lexical_plausibility` is a ranking hint only: it scores a string, it
    # never produces one.
    assert _lexical_plausibility("PATIO") > 0.9
    assert _lexical_plausibility("") == 0.0
    assert not _text_plausible("")
    assert not _text_plausible(".")


def test_localizer_is_deterministic_and_bounded():
    gray = _plan_image([
        ("LIVING AREA", (70, 180)),
        ("BEDROOM", (70, 300)),
        ("KITCHEN", (300, 300)),
        ("PATIO", (300, 180)),
    ])
    box = _plan_bbox(gray)
    first = localize_small_text(gray, box)
    second = localize_small_text(gray, box)
    assert first == second
    assert 0 < len(first) <= SMALL_TEXT_MAX_CANDIDATES


# --------------------------------------------------------------------------
# 16-17. real acceptance images
# --------------------------------------------------------------------------


def _stub_reader(labels, regions=(), axis_count=0, furniture=0):
    def read(raster, **kwargs):
        height, width = raster.shape
        return {
            "contract": "LocalPlanReadingV1",
            "source": "local_offline_raster",
            "provider_independent": True,
            "status": "grounded",
            "image_size": {"width": width, "height": height},
            "plan_bbox_pixels": [0, 0, width, height],
            "labels": [dict(entry) for entry in labels],
            "openings": [],
            "furniture_evidence": [{"class": "bed"}] * furniture,
            "furniture_observed": bool(furniture),
            "symbol_analysis_status": "analyzed",
            "element_evidence": [
                {"type": "axis", "geometry": {"orientation": "vertical"}}
            ] * axis_count,
            "element_analysis_status": "analyzed",
            "enclosure_geometry": {"count": len(regions), "regions": [dict(r) for r in regions]},
        }

    return read


@pytest.fixture(scope="module")
def four_images():
    if not all(p.is_file() for p in PATHS.values()):
        pytest.skip("Provide private ARCHITECTOS_PLAN_A/B/C/D for the real acceptance checks")
    return {key: read_local_plan(path) for key, path in PATHS.items()}


def test_real_a_b_c_do_not_regress(four_images):
    a, b, c = four_images["A"], four_images["B"], four_images["C"]

    # A — unfurnished Persian plan: no furniture, its own labels untouched.
    assert a["sheet_structure"]["sheet_type"] == "single_plan"
    assert len(a["furniture_evidence"]) == 0
    assert len(a["labels"]) >= 1
    assert all(entry["semantic_function"] for entry in a["labels"])

    # B — furnished plan: the W3 pinned furniture count and elements survive.
    assert b["sheet_structure"]["sheet_type"] == "single_plan"
    assert len(b["furniture_evidence"]) == 11
    b_types = {e["type"] for e in b["element_evidence"]}
    assert {"window", "axis", "column", "stair"} <= b_types

    # C — out-of-sample furnished plan: furniture survives.
    assert c["sheet_structure"]["sheet_type"] == "single_plan"
    assert len(c["furniture_evidence"]) == 4

    # The recovery layer must be present and bounded on every panel.
    for image in (a, b, c):
        audit = image.get("small_architectural_text")
        assert audit is not None
        assert audit["candidates"] <= SMALL_TEXT_MAX_CANDIDATES


def test_real_d_roles_and_geometry_do_not_regress(four_images):
    d = four_images["D"]
    assert d["sheet_structure"]["sheet_type"] == "plan_pair"
    panels = d["sheet_structure"]["panels"]
    assert len(panels) == 2
    roles = {p["panel_id"]: p["role"] for p in panels}
    assert roles == {"p1": DIMENSION_PLAN, "p2": FURNISHED_ARCHITECTURAL_PLAN}
    # geometry / axes / furniture are untouched by the recovery layer.
    # W3R raised p1 from 21 to 23 regions: the two large bottom rooms that the
    # 215 level closes but the 190 level merges with the exterior are now
    # admitted (see tests/test_semantic_grounding_enclosure_repair_w3r.py).
    assert len((panels[0]["local_plan_reading"]["enclosure_geometry"] or {}).get("regions") or []) == 23
    assert len((panels[1]["local_plan_reading"]["enclosure_geometry"] or {}).get("regions") or []) == 6
    assert sum(1 for e in panels[0]["local_plan_reading"]["element_evidence"] if e["type"] == "axis") == 11
    assert sum(
        len(p["local_plan_reading"]["furniture_evidence"]) for p in panels
    ) == 2


def test_real_d_has_no_grounded_room_label_phase_blocker_withdrawn(four_images):
    """The old W3.5 D acceptance target (`named_spaces > 1`) is WITHDRAWN.

    D's architectural room text is ~2.9 px per character in a 554x554 sheet, so
    no bounded OCR strategy recovers it (measured).  The single grounded label
    that used to satisfy `named_spaces > 1` was a wall junction read as `تراس`;
    W3R traced and rejected it as a drawing graphic.  The correct expectation is
    therefore the opposite: D publishes NO named space, and none is fabricated.
    """
    d = four_images["D"]
    from core.vision.architectural_vision_interpreter_v1 import (
        interpret_architectural_vision,
    )
    from core.vision.image_understanding_v1 import build_understanding

    sheet = grounded_sheet_structure(d)
    assert sheet
    for panel in sheet["panels"]:
        local = panel["local_plan_reading"]
        assert local["labels"] == []
        # The rejection is recorded, so the gate really did fire on D.
        assert local.get("rejected_graphic_ocr_labels")

    raw = {
        "image_type": "floor_plan_or_sketch",
        "confidence": "HIGH",
        "observed": ["floor plan"],
        "furniture_elements": [],
        "architectural_elements": [],
        "local_plan_reading": d,
    }
    understanding = build_understanding(raw, provider="stub", model="stub")
    plan = interpret_architectural_vision(understanding, user_text="analyze")["plan_reading"]
    named = plan.get("named_spaces") or []
    assert named == []
    assert plan["fusion"]["corresponding_label_transfers"] == []
    assert not [entry for entry in named if entry.get("space") == "balcony"]
