# -*- coding: utf-8 -*-
"""FACADE-04D.3C-9P-B1 — REAL USER CONFIRMATION PROVENANCE.

Focused tests. NO Vision inference: the IMAGE A/B contracts are loaded from the
EXISTING 9M captures.

Cases A..J per the 9P-B1 brief.
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
    _valid_user_geometry,
)
from core.cognition.render_semantic_fidelity_v1 import (
    validate_render_fidelity,
)

CAP_A = ROOT / ".pytest_tmp/9m_capture_A_contract.json"
CAP_B = ROOT / ".pytest_tmp/9m_capture_B_contract.json"

REAL = ("نمای این ساختمان را بازطراحی کن. نما را با سبک کلاسیک/نئوکلاسیک "
        "بازطراحی کن، بدون تغییر در مکان پنجره‌ها و بازشوها و بدون تغییر در "
        "تعداد طبقات.")


def _contract(path):
    if not path.exists():
        pytest.skip("9M capture missing: %s" % path.name)
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


def _fcp(user_geometry=None, ab=None):
    c = build_render_instruction(
        REAL,
        reference_analysis_ab=(ab if ab is not None else _ab()),
        user_geometry=user_geometry,
    )
    return c, c["constraints"]["floor_count_provenance"]


CONFIRM_3 = {"origin": "user", "storey_count": 3,
             "storeys": ["ground", "first", "second"]}


# ==========================================================
# A. GENUINE USER CONFIRMATION
# ==========================================================

def test_A_genuine_confirmation():
    c, fcp = _fcp(CONFIRM_3)
    assert fcp["source"] == "USER_CONFIRMATION"
    assert fcp["hard_constraint"] is True
    assert fcp["value"] == 3
    assert fcp["confirmed_scope"] == ["ground", "first", "second"]


# ==========================================================
# B. NO CONFIRMATION AVAILABLE
# ==========================================================

def test_B_no_confirmation_no_fabrication():
    c, fcp = _fcp(None)
    assert fcp["source"] == "VISION_OBSERVATION_UNVERIFIED"
    assert fcp["hard_constraint"] is False
    assert "USER_CONFIRMATION" not in json.dumps(fcp)


# ==========================================================
# C. B VISION = 3, USER CONFIRMS = 3
# ==========================================================

def test_C_agreement():
    c, fcp = _fcp({"origin": "user", "storey_count": 3})
    assert fcp["source"] == "USER_CONFIRMATION"
    assert fcp["vision_observation"]["value"] == 3
    assert fcp["vision_observation"]["agrees"] is True
    assert fcp["conflict"] is False


# ==========================================================
# D. B VISION = 3, USER CONFIRMS = 4 -> CONFLICT SURFACED
# ==========================================================

def test_D_disagreement_preserved_and_surfaced():
    c, fcp = _fcp({"origin": "user", "storey_count": 4})
    assert fcp["value"] == 4                         # user wins numerically
    assert fcp["source"] == "USER_CONFIRMATION"
    assert fcp["vision_observation"]["value"] == 3   # raw vision preserved
    assert fcp["vision_observation"]["agrees"] is False
    assert fcp["conflict"] is True
    # surfaced to the readiness gate, not silently resolved
    assert c["reference_analysis_ab"]["floor_count_conflict"] is not None
    assert c["reference_analysis_ab"]["floor_count_conflict"][
        "target_building_observed_floor_count"] == 3


# ==========================================================
# E. IMAGE A = 2, IMAGE B = 3 -> NO A TRANSFER
# ==========================================================

def test_E_no_image_a_transfer():
    ab = _ab()
    assert ab["A"]["visible_floor_count"] == 2
    assert ab["B"]["visible_floor_count"] == 3
    c, fcp = _fcp(CONFIRM_3, ab=ab)
    assert fcp["value"] == 3
    assert fcp["value"] != ab["A"]["visible_floor_count"]
    # IMAGE A/B contracts unchanged (read-only)
    assert ab["A"]["visible_floor_count"] == 2
    assert ab["B"]["visible_floor_count"] == 3


def test_E2_no_confirmation_uses_b_not_a():
    c, fcp = _fcp(None)
    assert fcp["value"] == 3     # IMAGE B
    assert fcp["value"] != 2     # never IMAGE A


# ==========================================================
# F. MISSING / MALFORMED CONFIRMATION -> FAIL SAFE
# ==========================================================

@pytest.mark.parametrize("bad", [
    None,
    {},
    {"origin": "user"},
    {"origin": "user", "storey_count": "three"},
    {"origin": "user", "storey_count": 0},
    {"origin": "user", "storey_count": -2},
    {"origin": "user", "storey_count": 3.5},
    {"origin": "user", "storey_count": True},
    {"origin": "user", "storey_count": 3, "storeys": ["ground", "first"]},  # scope mismatch
])
def test_F_malformed_confirmation_fails_safe(bad):
    assert _valid_user_geometry(bad) is None
    c, fcp = _fcp(bad)
    assert fcp["source"] == "VISION_OBSERVATION_UNVERIFIED"
    assert fcp["hard_constraint"] is False


# ==========================================================
# G. WINDOW/OPENING PRESERVATION STILL CHECKED & FAIL-CLOSED
# ==========================================================

def test_G_preservation_checks_intact_with_confirmation():
    c, fcp = _fcp(CONFIRM_3)
    v = validate_render_fidelity(REAL, contract=c)
    assert v["status"] == "PASS"
    slots = {k.get("slot") for k in v.get("checks", [])}
    assert "window_positions" in slots
    assert "opening_positions" in slots
    assert "floor_count_preservation" in slots


def test_G2_missing_window_clause_still_blocks_with_confirmation():
    from core.cognition.render_semantic_fidelity_v1 import _WINDOW_POSITION_MARKERS
    c, _ = _fcp(CONFIRM_3)
    keep = []
    for sent in re.split(r"(?<=[.!;])\s+", c["english_instruction"]):
        if any(m in sent.lower() for m in _WINDOW_POSITION_MARKERS):
            continue
        keep.append(sent)
    v = validate_render_fidelity(REAL, instruction=" ".join(keep), contract=c)
    assert v["status"] == "BLOCKED"


# ==========================================================
# H. 9M ROOF BRIDGE INTACT
# ==========================================================

def test_H_roof_bridge_intact():
    c, _ = _fcp(CONFIRM_3)
    b_line = [l for l in c["english_instruction"].split(". ")
              if "TARGET BUILDING" in l]
    assert b_line
    b_line = b_line[0].lower()
    assert "flat" in b_line and "parapet" in b_line
    for leak in ("mansard", "dome", "finial", "oculus"):
        assert leak not in b_line


# ==========================================================
# I. NON-USER-ORIGINATED "CONFIRMATION" MUST BE REJECTED
# ==========================================================

@pytest.mark.parametrize("origin", [
    "assistant", "model", "llm", "system", "assistant_message", "other_session",
])
def test_I_non_user_origin_rejected(origin):
    bad = {"origin": origin, "storey_count": 3}
    assert _valid_user_geometry(bad) is None
    c, fcp = _fcp(bad)
    assert fcp["source"] == "VISION_OBSERVATION_UNVERIFIED"


def test_I2_no_source_kind_is_accepted_as_user():
    # an explicitly non-user source_kind must be rejected too
    assert _valid_user_geometry(
        {"source_kind": "model_output", "storey_count": 3}
    ) is None


# ==========================================================
# J. REAL CHAT CALLER PATH (or explicit BLOCKER)
# ==========================================================

def test_J_live_caller_uses_context_user_geometry():
    """A caller that supplies context['user_geometry'] must reach the contract.

    This exercises the chat_architect integration POINT (the pass-through),
    not the whole live server. The upstream carrier does not yet exist; if the
    chat module cannot be imported here, that is reported, not faked.
    """

    try:
        import core.chat.chat_architect  # noqa: F401
    except Exception as error:  # pragma: no cover - environment gap
        pytest.skip("chat_architect not importable here: %r" % error)

    src = (ROOT / "core/chat/chat_architect.py").read_text(encoding="utf-8")
    # the live path must read the per-request context field and pass it through
    assert "context.get(\"user_geometry\")" in src
    assert "user_geometry=_user_geometry" in src


def test_J2_no_session_or_assistant_confirmation_source():
    """The live path must NOT read a confirmation from session state."""

    src = (ROOT / "core/chat/chat_architect.py").read_text(encoding="utf-8")
    # no confirmation pulled from persisted/global state
    for forbidden in (
        "state.get(\"user_geometry\")",
        "self.state.get(\"user_geometry\")",
        "last_user_geometry",
    ):
        assert forbidden not in src


# ==========================================================
# STRENGTHENED ORDINARY-REQUEST ASSERTIONS
# ==========================================================

def test_ordinary_request_has_no_confirmation_and_no_preservation():
    text = "یک ویلای دو طبقه با نمای سنتی بساز"
    c = build_render_instruction(text)
    fcp = c["constraints"]["floor_count_provenance"]
    # a numeral IS present -> USER_TEXT, never USER_CONFIRMATION
    assert fcp is not None and fcp["source"] == "USER_TEXT"
    assert fcp["hard_constraint"] is True
    assert "USER_CONFIRMATION" not in json.dumps(fcp)
    # and no geometry preservation was invented
    assert c["constraints"]["openings"].get("preserve_window_positions") is not True
    assert c["constraints"]["geometry"].get("preserve_floor_count") is not True


def test_user_text_outranks_confirmation():
    text = "ساختمان ۴ طبقه است، بدون تغییر در تعداد طبقات"
    c = build_render_instruction(text, user_geometry=CONFIRM_3)
    fcp = c["constraints"]["floor_count_provenance"]
    assert fcp["source"] == "USER_TEXT"
    assert fcp["value"] == 4
