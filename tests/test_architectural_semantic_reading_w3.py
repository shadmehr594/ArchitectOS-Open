"""ARCHITECTURAL SEMANTIC READING W3 — plan roles, multilingual labels, label→space.

Every non-image fixture here is synthetic. Nothing depends on the private
acceptance images, their filenames, or any fixed count from them.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from core.vision.local_plan_reader_v1 import (
    _architectural_label_matches,
    _label_matches,
    _read_raster,
    read_local_plan,
)
from core.vision.local_plan_sheet_v1 import (
    ARCHITECTURAL_PLAN,
    DIMENSION_PLAN,
    FURNISHED_ARCHITECTURAL_PLAN,
    STRUCTURAL_PLAN,
    UNKNOWN_PLAN,
    _region_correspondences,
    analyze_sheet,
    classify_plan_role,
    detect_sheet,
    grounded_sheet_structure,
)

PLAN_BOX = [40.0, 40.0, 380.0, 380.0]

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
    return {key: read_local_plan(path) for key, path in PATHS.items()}


def _reading(text, box=(120.0, 120.0, 190.0, 134.0), confidence=70.0, name="p1"):
    return {
        "raw_text": text,
        "ocr_confidence": confidence,
        "bbox_pixels": list(box),
        "pass": name,
    }


def _labels(readings):
    return _architectural_label_matches(readings, PLAN_BOX, (420, 420))


# --------------------------------------------------------------------------
# W3.2 — language-neutral architectural label reading
# --------------------------------------------------------------------------


def test_persian_labels_remain_unchanged():
    readings = [_reading("اتاق خواب"), _reading("آشپزخانه")]
    persian = _label_matches(readings, PLAN_BOX, (420, 420))
    assert {entry["semantic_function"] for entry in persian} == {"bedroom", "kitchen"}
    # The Persian path owns those readings; the Latin path must not touch them.
    assert _labels(readings) == []


@pytest.mark.parametrize(
    "text,semantic",
    [
        ("LIVING AREA", "living room"),
        ("BEDROOM", "bedroom"),
        ("KITCHEN", "kitchen"),
        ("BATHROOM", "bathroom"),
        ("DINING", "dining"),
        ("BALCONY", "balcony"),
        ("STORAGE", "storage"),
    ],
)
def test_latin_architectural_labels_ground(text, semantic):
    found = _labels([_reading(text, confidence=60.0)])
    assert found, text
    assert found[0]["semantic_function"] == semantic
    assert found[0]["script"] == "latin"
    assert found[0]["matched_term"]


def test_patio_is_an_architectural_label_candidate():
    found = _labels([_reading("PATIO", confidence=42.0)])
    assert found and found[0]["semantic_function"] == "patio"
    # A text label is label-level semantics, never a verified lightwell.
    assert "lightwell" not in str(found[0])


def test_void_and_lightwell_are_labelled_not_geometrically_claimed():
    for text in ("VOID", "LIGHTWELL", "COURTYARD"):
        found = _labels([_reading(text, confidence=55.0)])
        assert found, text
        assert found[0]["evidence_type"] == "local_ocr"
        assert found[0]["status"] == "grounded_ocr"


@pytest.mark.parametrize("text", ["A", "B", "G", "1", "2", "6", "E", "5"])
def test_axis_identifiers_never_become_labels(text):
    assert _labels([_reading(text, confidence=90.0)]) == []


@pytest.mark.parametrize(
    "text", ["WALL", "WALLY", "MALL", "ATHE", "ALL", "XYZQW", "###", "1/100", "AA"]
)
def test_random_latin_text_does_not_become_a_space(text):
    assert _labels([_reading(text, confidence=80.0)]) == []


def test_a_short_fragment_inside_a_longer_word_does_not_match():
    """The window is never shorter than the term, so "all" cannot be "HALL"."""
    assert _labels([_reading("all", confidence=90.0)]) == []
    assert _labels([_reading("wall", confidence=90.0)]) == []


def test_a_weak_read_alone_does_not_ground_a_label():
    assert _labels([_reading("PATIO", confidence=8.0, name="only")]) == []


# --------------------------------------------------------------------------
# W3.1 — grounded role classification
# --------------------------------------------------------------------------


def test_dimension_plan_requires_axes_and_no_furniture():
    evidence = {
        "furniture_symbols": 0,
        "furnishing_patterns": 0,
        "axis_count": 11,
        "enclosure_regions": 21,
    }
    assert classify_plan_role(evidence) == DIMENSION_PLAN
    # Removing the axis grid removes the measured-plan claim.
    assert classify_plan_role({**evidence, "axis_count": 0}) == ARCHITECTURAL_PLAN
    # A furniture symbol means it is not the measured plan.
    assert (
        classify_plan_role({**evidence, "furniture_symbols": 1})
        == FURNISHED_ARCHITECTURAL_PLAN
    )


def test_furniture_alone_is_not_the_only_criterion():
    """Furnishing texture corroborates even with no furniture symbol."""
    assert (
        classify_plan_role(
            {
                "furniture_symbols": 0,
                "furnishing_patterns": 3,
                "axis_count": 6,
                "enclosure_regions": 6,
            }
        )
        == FURNISHED_ARCHITECTURAL_PLAN
    )


def test_a_title_vote_can_force_the_structural_role():
    assert (
        classify_plan_role({"title_role": STRUCTURAL_PLAN, "axis_count": 0})
        == STRUCTURAL_PLAN
    )


def test_a_generic_floor_plan_title_does_not_override_content():
    """Both panels of a dimensioned pair are titled as floor plans."""
    assert (
        classify_plan_role(
            {
                "title_role": ARCHITECTURAL_PLAN,
                "furniture_symbols": 0,
                "furnishing_patterns": 0,
                "axis_count": 11,
                "enclosure_regions": 21,
            }
        )
        == DIMENSION_PLAN
    )


def test_an_empty_panel_is_never_promoted():
    assert classify_plan_role({}) == UNKNOWN_PLAN


def test_role_classification_is_a_pure_function_of_evidence():
    """Reordering the panels cannot change a role: order is not an input."""
    dimension = {
        "furniture_symbols": 0, "furnishing_patterns": 0,
        "axis_count": 11, "enclosure_regions": 21,
    }
    furnished = {
        "furniture_symbols": 2, "furnishing_patterns": 3,
        "axis_count": 7, "enclosure_regions": 6,
    }
    forward = [classify_plan_role(dimension), classify_plan_role(furnished)]
    reverse = [classify_plan_role(furnished), classify_plan_role(dimension)]
    assert forward == [DIMENSION_PLAN, FURNISHED_ARCHITECTURAL_PLAN]
    assert reverse == list(reversed(forward))


# --------------------------------------------------------------------------
# W3.3 — label → space association
# --------------------------------------------------------------------------


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


def _reader(labels, axis_count=0, furniture=0, regions=None):
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
            "enclosure_geometry": {
                "count": None,
                "count_status": "uncertain",
                "regions": regions if regions is not None else [],
            },
        }

    return read


def _region(region_id, box, confidence="MEDIUM"):
    return {
        "region_id": region_id,
        "bbox_pixels": list(box),
        "pixel_area": (box[2] - box[0]) * (box[3] - box[1]),
        "centroid_pixels": [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2],
        "source": "local_raster_wall_boundaries",
        "status": "enclosed_region_candidate",
        "confidence": confidence,
        "corroboration": ["a", "b", "c"],
        "stable_across_gap_scales": True,
    }


def test_a_label_outside_a_region_does_not_create_a_space():
    sheet = _two_panel_sheet()
    regions = [_region("r1", [20, 20, 120, 120])]
    label = {
        "text": "PATIO",
        "semantic_function": "patio",
        "bbox_pixels": [400.0, 300.0, 460.0, 314.0],
        "confidence": "MEDIUM",
    }
    result = analyze_sheet(
        sheet, detect_sheet(sheet), _reader([label], regions=regions), None
    )
    for panel in result["sheet_structure"]["panels"]:
        assert panel["local_plan_reading"]["labels"] == []
        reasons = {entry["reason"] for entry in panel["quarantined_annotations"]}
        assert reasons & {
            "label_outside_plan_enclosure",
            "no_enclosure_region_contains_label_centroid",
        }


def test_a_label_inside_a_medium_region_is_associated():
    sheet = _two_panel_sheet()
    regions = [_region("r1", [10, 10, 300, 200])]
    label = {
        "text": "PATIO",
        "semantic_function": "patio",
        "bbox_pixels": [120.0, 90.0, 180.0, 104.0],
        "confidence": "MEDIUM",
    }
    result = analyze_sheet(
        sheet, detect_sheet(sheet), _reader([label], regions=regions), None
    )
    associated = []
    for panel in result["sheet_structure"]["panels"]:
        for entry in panel["local_plan_reading"]["labels"]:
            associated.append(entry)
            assert entry["associated_region_id"] == "r1"
            assert entry["association"] == "label_centroid_inside_enclosure_region"
            assert entry["source_panel_id"] == panel["panel_id"]
    assert associated


def test_a_low_confidence_region_does_not_ground_a_label():
    sheet = _two_panel_sheet()
    regions = [_region("r1", [10, 10, 300, 200], confidence="LOW")]
    label = {
        "text": "PATIO",
        "semantic_function": "patio",
        "bbox_pixels": [120.0, 90.0, 180.0, 104.0],
        "confidence": "MEDIUM",
    }
    result = analyze_sheet(
        sheet, detect_sheet(sheet), _reader([label], regions=regions), None
    )
    for panel in result["sheet_structure"]["panels"]:
        assert panel["local_plan_reading"]["labels"] == []


# --------------------------------------------------------------------------
# W3.4 — corresponding-panel transfer needs geometric correspondence
# --------------------------------------------------------------------------


def _local(plan_box, regions):
    return {
        "plan_bbox_pixels": list(plan_box),
        "enclosure_geometry": {"regions": regions},
    }


def test_region_correspondence_is_geometric_and_one_to_one():
    left = _local([0, 0, 400, 400], [
        _region("r1", [40, 40, 160, 160]),
        _region("r2", [240, 240, 360, 360]),
    ])
    right = _local([0, 0, 800, 800], [
        _region("r1", [80, 80, 320, 320]),
        _region("r2", [480, 480, 720, 720]),
    ])
    pairs = _region_correspondences(left, right)
    assert {p["left_region_id"] for p in pairs} == {"r1", "r2"}
    assert len({p["right_region_id"] for p in pairs}) == len(pairs)
    assert all(p["mutual_centroid_containment"] for p in pairs)


def test_region_correspondence_rejects_a_mismatched_layout():
    left = _local([0, 0, 400, 400], [_region("r1", [40, 40, 120, 120])])
    right = _local([0, 0, 400, 400], [_region("r1", [280, 280, 360, 360])])
    assert _region_correspondences(left, right) == []


def test_corresponding_transfer_carries_provenance(four_images):
    """The transfer machinery is unchanged; W3R removed D's only label.

    D's single grounded label was a wall junction read as `تراس`, now rejected
    as a drawing graphic, so the grounded set is empty and the transfer is
    correctly vacuous.  The invariants are asserted either way: the geometric
    correspondence is still one-to-one, no space is published twice, and every
    published named space is backed by a provenance-carrying transfer.
    """
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
    pairs = [
        pair
        for record in sheet.get("corresponding_regions") or []
        for pair in record["pairs"]
    ]
    assert pairs
    assert len({pair["right_region_id"] for pair in pairs}) == len(pairs)
    raw = {
        "image_type": "floor_plan_or_sketch",
        "local_plan_reading": local,
    }
    plan = interpret_architectural_vision(
        build_understanding(raw, provider="stub", model="stub")
    )["plan_reading"]
    transfers = plan["fusion"]["corresponding_label_transfers"]
    published = [entry["space"] for entry in plan["named_spaces"]]
    assert len(published) == len(set(published))
    if grounded:
        assert transfers
    else:
        assert transfers == []
        assert published == []
    for entry in transfers:
        assert entry["source_panel_id"] != plan["fusion"]["geometry_panel_id"]
        assert entry["associated_region_id"]
        assert entry["corresponding_region_id"]
        assert entry["transfer"] == "corresponding_panel_geometric_region_match"
        assert entry["space"] in published


# --------------------------------------------------------------------------
# Real-image regressions and the D acceptance
# --------------------------------------------------------------------------


def test_real_A_B_C_labels_and_roles_do_not_regress(four_images):
    assert four_images["A"]["sheet_structure"]["panels"][0]["role"] == (
        ARCHITECTURAL_PLAN
    )
    for name in "BC":
        assert four_images[name]["sheet_structure"]["panels"][0]["role"] == (
            FURNISHED_ARCHITECTURAL_PLAN
        )
    # A's Persian labels survive untouched and gain no Latin label.
    texts = [entry["text"] for entry in four_images["A"]["labels"]]
    assert texts
    assert all(
        any("\u0600" <= ch <= "\u06ff" for ch in text) for text in texts
    )
    assert four_images["A"]["furniture_evidence"] == []
    assert len(four_images["B"]["furniture_evidence"]) == 11
    assert len(four_images["C"]["furniture_evidence"]) >= 3


def test_real_D_gains_grounded_roles_and_labels(four_images):
    sheet = grounded_sheet_structure(four_images["D"])
    assert sheet
    roles = {panel["panel_id"]: panel["role"] for panel in sheet["panels"]}
    assert roles["p1"] == DIMENSION_PLAN
    assert roles["p2"] == FURNISHED_ARCHITECTURAL_PLAN
    # The title is now read on both panels and recorded as grounded evidence.
    for panel in sheet["panels"]:
        title = panel.get("title_evidence")
        assert title and title["role"] in (
            ARCHITECTURAL_PLAN,
            FURNISHED_ARCHITECTURAL_PLAN,
        )
        assert title["corroborated"] is True
        assert panel["role_evidence"]["title_role"] == title["role"]
    # The dimensioned panel grounds no furniture; the furnished panel keeps it.
    assert sheet["panels"][0]["role_evidence"]["furniture_symbols"] == 0
    assert sheet["panels"][1]["role_evidence"]["furniture_symbols"] == 2
