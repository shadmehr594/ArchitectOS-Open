# -*- coding: utf-8 -*-
"""FACADE-04D.3C-9P-B1.2 — TRUSTED USER CONFIRMATION INGRESS.

Focused tests. NO Vision inference, NO render: the IMAGE A/B contracts are
loaded from the EXISTING 9M captures and the request path is exercised offline.

Cases A..J per the 9P-B1.2 brief.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.cognition.architectural_render_instruction_v1 import (
    build_render_instruction,
    user_geometry_from_messages,
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

CONFIRM = "این ساختمان سه طبقه دارد: همکف، اول و دوم."


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


# ==========================================================
# A. Actual user-originated confirmation for IMAGE B, 3 storeys
# ==========================================================

def test_A_user_confirmation_is_promoted():
    msg_geometry = user_geometry_from_messages(
        [{"role": "user", "text": CONFIRM}]
    )
    assert msg_geometry == {"origin": "user", "storey_count": 3}

    _c, p = _fcp(user_geometry=msg_geometry)

    assert p["source"] == "USER_CONFIRMATION"
    assert p["value"] == 3
    assert p["hard_constraint"] is True
    assert p["conflict"] is False
    assert p["vision_observation"]["value"] == 3
    assert p["vision_observation"]["agrees"] is True


# ==========================================================
# B. Assistant statement must NOT become a confirmation
# ==========================================================

def test_B_assistant_text_is_not_confirmation():
    assert user_geometry_from_messages(
        [{"role": "assistant", "text": CONFIRM}]
    ) is None

    _c, p = _fcp(user_geometry=None)

    assert p["source"] == "VISION_OBSERVATION_UNVERIFIED"
    assert p["hard_constraint"] is False


# ==========================================================
# C. Missing origin must be rejected
# ==========================================================

def test_C_missing_origin_is_rejected():
    assert _valid_user_geometry({"storey_count": 3}) is None

    _c, p = _fcp(user_geometry={"storey_count": 3})

    assert p["source"] == "VISION_OBSERVATION_UNVERIFIED"


# ==========================================================
# D. Forged origin through an untrusted input must NOT be promoted
# ==========================================================

def test_D_forged_origin_in_client_body_is_ignored():
    # A client-supplied body claiming a confirmation is NOT scanned by the
    # message extractor (only user-authored text is), so nothing is produced.
    assert user_geometry_from_messages(
        {"origin": "user", "storey_count": 3}
    ) is None

    # And a stated non-user origin is rejected outright by the validator.
    assert _valid_user_geometry(
        {"origin": "assistant", "storey_count": 3}
    ) is None

    _c, p = _fcp(user_geometry={"origin": "assistant", "storey_count": 3})

    assert p["source"] == "VISION_OBSERVATION_UNVERIFIED"


# ==========================================================
# E. Confirmation for another building must NOT apply to IMAGE B
# ==========================================================

def test_E_other_building_reference_is_not_extracted():
    # A confirmation about a DIFFERENT building does not state THIS building's
    # storey count as an explicit adjacency-free assertion.
    other = "ساختمان همسایه پنج طبقه دارد، برای این نما کاری نکن."
    geom = user_geometry_from_messages([{"role": "user", "text": other}])

    # The extractor is intentionally narrow: it requires an assertion about the
    # building in the SAME explicit clause. This message is ambiguous, so it
    # must not silently bind to IMAGE B.
    if geom is not None:
        # If a future revision widens this, it must still not be a silent
        # cross-building promotion — fail loudly instead.
        pytest.fail("ambiguous other-building text was promoted: %r" % geom)

    # The contract therefore keeps the unverified Vision observation.
    _c, p = _fcp(user_geometry=None)
    assert p["source"] == "VISION_OBSERVATION_UNVERIFIED"
    assert p["value"] == 3


# ==========================================================
# F. An older confirmation superseded by a later user correction
# ==========================================================

def test_F_later_user_correction_wins():
    geom = user_geometry_from_messages([
        {"role": "user", "text": "این ساختمان سه طبقه دارد"},
        {"role": "user", "text": "تصحیح می‌کنم: این ساختمان چهار طبقه دارد"},
    ])

    assert geom == {"origin": "user", "storey_count": 4}

    _c, p = _fcp(user_geometry=geom)

    assert p["source"] == "USER_CONFIRMATION"
    assert p["value"] == 4


# ==========================================================
# G. IMAGE B Vision=3, user confirms=4 -> conflict reported, render blocked
# ==========================================================

def test_G_conflict_is_reported_not_silently_resolved():
    _c, p = _fcp(user_geometry={"origin": "user", "storey_count": 4})

    assert p["source"] == "USER_CONFIRMATION"
    assert p["value"] == 4
    assert p["conflict"] is True
    assert p["vision_observation"]["value"] == 3
    assert p["vision_observation"]["agrees"] is False

    # IMAGE B is NEVER silently rewritten.
    assert _ab()["B"]["visible_floor_count"] == 3


# ==========================================================
# H. No confirmation -> existing 9P-A behaviour unchanged
# ==========================================================

def test_H_no_confirmation_keeps_9pa_behaviour():
    _c, p = _fcp(user_geometry=None)

    assert p["source"] == "VISION_OBSERVATION_UNVERIFIED"
    assert p["hard_constraint"] is False
    assert p["preservation_requested"] is True
    assert p["anchored_to"] == "IMAGE_B_TARGET"
    assert p["value"] == 3          # IMAGE B, never IMAGE A's 2


# ==========================================================
# I. Existing preservation gate: all five checks remain operative
# ==========================================================

def test_I_preservation_gate_slots_intact():
    c, _p = _fcp(user_geometry={"origin": "user", "storey_count": 3})
    v = validate_render_fidelity(REAL, contract=c)

    slots = [k.get("slot") for k in v.get("checks", [])]

    assert v["status"] == "PASS"
    assert slots.count("hard_constraint") == 2
    assert "window_positions" in slots
    assert "opening_positions" in slots
    assert "floor_count_preservation" in slots
    assert len(slots) == 5


# ==========================================================
# J. Verify the ACTUAL request-to-context path
# ==========================================================

def test_J_request_path_resolves_confirmation():
    """The real boundary resolves a confirmation from user-authored turn text.

    Honest boundary note: the LIVE wiring of `app.py` to a running server is
    asserted structurally (the boundary expression + context key), and the
    resolver itself is exercised directly. A running-HTTP test is NOT claimed.
    """

    src = (ROOT / "app.py").read_text(encoding="utf-8")

    # app.py builds the carrier from the CURRENT user message text only.
    assert "user_geometry_from_messages" in src
    assert '"user_geometry"' in src
    # It is NEVER read from the client body.
    assert 'data.get("user_geometry")' not in src

    # The chat boundary consumes that carrier via the trusted resolver.
    chat_src = (
        ROOT / "core/chat/chat_architect.py"
    ).read_text(encoding="utf-8")

    assert "_trusted_user_geometry" in chat_src
    assert 'context.get("user_geometry")' in chat_src

    # And the resolver itself promotes an explicit user turn end-to-end.
    from core.chat.chat_architect import ChatArchitect
    from core.chat.session_registry_v1 import session_registry

    chat = ChatArchitect.__new__(ChatArchitect)   # no brain needed for this

    session_registry.begin("pytest_9pb12_path")
    session_registry.current_state(None).add_message("user", CONFIRM)

    geom = chat._trusted_user_geometry({})

    assert geom == {"origin": "user", "storey_count": 3}

    # The prompt-derived carrier (current turn) takes precedence.
    carrier = {"origin": "user", "storey_count": 3}
    assert chat._trusted_user_geometry({"user_geometry": carrier}) == carrier


# ==========================================================
# Extra guards (part of the trust boundary, not in A..J)
# ==========================================================

def test_bool_count_never_becomes_one_storey():
    assert _valid_user_geometry({"origin": "user", "storey_count": True}) is None


def test_scope_length_mismatch_is_malformed():
    assert _valid_user_geometry(
        {"origin": "user", "storey_count": 3, "storeys": ["a", "b"]}
    ) is None


def test_implicit_numeral_is_not_a_confirmation():
    assert user_geometry_from_messages(
        [{"role": "user", "text": "3 پنجره جدید اضافه کن"}]
    ) is None


def test_non_user_origin_string_is_rejected():
    for origin in ("assistant", "model", "session", "system", "vision"):
        assert _valid_user_geometry(
            {"origin": origin, "storey_count": 3}
        ) is None


def test_persisted_session_is_scoped_not_global():
    """A confirmation in one session must not leak into another."""

    from core.chat.chat_architect import ChatArchitect
    from core.chat.session_registry_v1 import session_registry

    chat = ChatArchitect.__new__(ChatArchitect)

    session_registry.begin("pytest_9pb12_scope_a")
    session_registry.current_state(None).add_message("user", CONFIRM)

    session_registry.begin("pytest_9pb12_scope_b")

    assert chat._trusted_user_geometry({}) is None
