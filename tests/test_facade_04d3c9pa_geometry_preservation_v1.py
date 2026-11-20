# -*- coding: utf-8 -*-
"""FACADE-04D.3C-9P-A — PERSIAN GEOMETRY PRESERVATION + FAIL-CLOSED FIDELITY.

Focused regression tests. NO new Vision inference: the IMAGE A/B contracts are
loaded from the EXISTING 9M captures.

Cases A..K per the 9P-A brief.
"""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.cognition.architectural_render_instruction_v1 import (
    build_render_instruction,
)
from core.cognition.render_semantic_fidelity_v1 import (
    validate_render_fidelity,
)
from core.prompt_intelligence.persian_architectural_understanding import (
    understand,
)

CAP_A = ROOT / ".pytest_tmp/9m_capture_A_contract.json"
CAP_B = ROOT / ".pytest_tmp/9m_capture_B_contract.json"

REAL = ("نمای این ساختمان را بازطراحی کن. نما را با سبک کلاسیک/نئوکلاسیک "
        "بازطراحی کن، بدون تغییر در مکان پنجره‌ها و بازشوها و بدون تغییر در "
        "تعداد طبقات.")


def _contract(path):
    if not path.exists():
        pytest.skip("9M capture missing (completed phase): %s" % path.name)
    return json.loads(path.read_text(encoding="utf-8"))["contract"]


def _ab():
    return {
        "A": _contract(CAP_A),
        "B": _contract(CAP_B),
        "roles": {
            "A": "facade_reference",
            "B": "target_building",
            "geometry_authority": "target_building",
        },
    }


def _preserve(text):
    return understand(text).get("preserve_constraints") or {}


# ==========================================================
# A. EXACT ORIGINAL PERSIAN REQUEST
# ==========================================================

def test_A_preservation_recognized():
    p = _preserve(REAL)
    assert p.get("windows") is True
    assert p.get("openings") is True
    assert p.get("floor_count") is True


def test_A_checked_slots_non_empty():
    c = build_render_instruction(REAL, reference_analysis_ab=_ab())
    v = validate_render_fidelity(REAL, contract=c)
    assert v["status"] == "PASS"
    assert v.get("may_proceed_to_render") is True
    slots = {k.get("slot") for k in v.get("checks", [])}
    assert "window_positions" in slots
    assert "opening_positions" in slots
    assert "floor_count_preservation" in slots
    assert v.get("checks"), "checked_slots must not be empty"


def test_A_image_B_floor_count_authoritative():
    c = build_render_instruction(REAL, reference_analysis_ab=_ab())
    fcp = c["constraints"]["floor_count_provenance"]
    assert fcp.get("value") == 3                 # IMAGE B, not IMAGE A's 2
    assert fcp.get("source") == "VISION_OBSERVATION_UNVERIFIED"
    assert fcp.get("anchored_to") == "IMAGE_B_TARGET"
    # IMAGE A's count must never be used
    assert fcp.get("value") != 2


def _drop_sentences(text, markers):
    """Remove every sentence that carries one of ``markers`` (lowercased)."""

    keep = []
    for sent in re.split(r"(?<=[.!;])\s+", text):
        low = sent.lower()
        if any(m in low for m in markers):
            continue
        keep.append(sent)
    return " ".join(keep)


# ==========================================================
# B. ENGLISH WINDOW-PRESERVATION CLAUSE REMOVED -> BLOCKED
# ==========================================================

def test_B_missing_window_preservation_blocks():
    from core.cognition.render_semantic_fidelity_v1 import (
        _WINDOW_POSITION_MARKERS,
    )
    c = build_render_instruction(REAL, reference_analysis_ab=_ab())
    english = _drop_sentences(c["english_instruction"], _WINDOW_POSITION_MARKERS)
    v = validate_render_fidelity(REAL, instruction=english, contract=c)
    assert v["status"] == "BLOCKED"
    assert v["may_proceed_to_render"] is False


# ==========================================================
# C. FLOOR-COUNT PRESERVATION CLAUSE REMOVED -> BLOCKED
# ==========================================================

def test_C_missing_floor_preservation_blocks():
    from core.cognition.render_semantic_fidelity_v1 import (
        _FLOOR_PRESERVE_MARKERS,
    )
    c = build_render_instruction(REAL, reference_analysis_ab=_ab())
    english = _drop_sentences(c["english_instruction"], _FLOOR_PRESERVE_MARKERS)
    v = validate_render_fidelity(REAL, instruction=english, contract=c)
    assert v["status"] == "BLOCKED"


# ==========================================================
# D. REVERSE PRESERVATION INTO "MOVE WINDOWS" -> BLOCKED
# ==========================================================

def test_D_reversed_preservation_blocks():
    c = build_render_instruction(REAL, reference_analysis_ab=_ab())
    english = c["english_instruction"].replace(
        "Keep the existing window positions unchanged; do NOT move or "
        "relocate the windows.",
        "Move the windows to new positions.",
    )
    v = validate_render_fidelity(REAL, instruction=english, contract=c)
    assert v["status"] == "BLOCKED"
    assert v["reason_code"] == "REVERSED_PRESERVATION"


# ==========================================================
# E. "پنجره جدید اضافه کن" -> NO FALSE PRESERVE
# ==========================================================

def test_E_add_window_no_false_preserve():
    p = _preserve("پنجره جدید اضافه کن")
    assert p.get("windows") is not True
    assert p.get("openings") is not True


# ==========================================================
# F. "بدون تغییر در رنگ نما" -> NO WINDOW PRESERVATION
# ==========================================================

def test_F_colour_only_no_window_preserve():
    p = _preserve("بدون تغییر در رنگ نما")
    assert p.get("windows") is not True
    assert p.get("openings") is not True
    assert p.get("floor_count") is not True


# ==========================================================
# G. POSITION PRESERVED, SHAPE MAY CHANGE
# ==========================================================

def test_G_position_preserved_shape_changeable():
    p = _preserve("بدون تغییر در مکان پنجره‌ها، شکل پنجره‌ها را عوض کن")
    assert p.get("windows") is True       # POSITION preserved
    # the shape/style change must not be turned into a geometry prohibition
    c = build_render_instruction("بدون تغییر در مکان پنجره‌ها، شکل پنجره‌ها را عوض کن")
    assert c["constraints"]["openings"]["preserve_window_positions"] is True


# ==========================================================
# H. PRESERVATION WITHOUT A TRUSTWORTHY BASELINE
# ==========================================================

def test_H_floor_preservation_without_baseline_fails_closed():
    # no IMAGE B, no numeral -> the floor-count preservation cannot be
    # verified; the gate must NOT return a misleading geometry PASS.
    text = "بدون تغییر در تعداد طبقات"
    c = build_render_instruction(text)          # no A/B evidence
    v = validate_render_fidelity(text, contract=c)
    assert v["status"] == "BLOCKED"
    assert v["reason_code"] in (
        "UNRESOLVABLE_FLOOR_BASELINE", "MISSING_PRESERVATION",
    )
    assert v["may_proceed_to_render"] is False


# ==========================================================
# I. IMAGE A=2, IMAGE B=3 -> B REMAINS AUTHORITY
# ==========================================================

def test_I_image_b_is_geometry_authority():
    ab = _ab()
    assert ab["A"]["visible_floor_count"] == 2
    assert ab["B"]["visible_floor_count"] == 3
    c = build_render_instruction(REAL, reference_analysis_ab=ab)
    assert c["reference_analysis_ab"]["roles"]["geometry_authority"] == "target_building"
    fcp = c["constraints"]["floor_count_provenance"]
    assert fcp.get("value") == 3


# ==========================================================
# J. ROOF BRIDGE (9M/9N) STILL INTACT
# ==========================================================

def test_J_roof_bridge_intact():
    c = build_render_instruction(REAL, reference_analysis_ab=_ab())
    b_line = [l for l in c["english_instruction"].split(". ")
              if "TARGET BUILDING" in l]
    assert b_line, "B preservation clause missing"
    b_line = b_line[0].lower()
    # B's roof observation survives
    assert "flat" in b_line
    assert "parapet" in b_line
    # A's mansard/dome/finial must NOT leak into B's geometry
    for leak in ("mansard", "dome", "finial", "oculus"):
        assert leak not in b_line


# ==========================================================
# K. ORDINARY REQUESTS ARE NOT GLOBALLY BLOCKED
# ==========================================================

def test_K_ordinary_request_not_blocked():
    text = "یک ویلای دو طبقه با نمای سنتی بساز"
    c = build_render_instruction(text)
    v = validate_render_fidelity(text, contract=c)
    assert v["status"] in ("PASS", "BLOCKED")
    # a plain creation request carries no preservation demand, so it must not
    # be blocked *because of* a fabricated preservation constraint
    assert v["reason_code"] not in (
        "MISSING_PRESERVATION", "REVERSED_PRESERVATION",
        "UNRESOLVABLE_FLOOR_BASELINE",
    )


def test_K2_no_preservation_gate_invention():
    for text in ("یک ویلای دو طبقه با نمای سنتی بساز", "نما را مدرن کن"):
        p = _preserve(text)
        assert p.get("windows") is not True
        assert p.get("openings") is not True
