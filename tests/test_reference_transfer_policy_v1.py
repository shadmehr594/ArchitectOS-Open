"""REFERENCE_TRANSFER_POLICY_V1 — which dual-image graph does a turn need?

Guards the defect measured in ARCHITECTOS_LIVE_PRODUCT_SMOKE_ACCEPTANCE_V2 §7:
the conditioned graph was reachable only through an explicit UI flag, so a
plain request to apply IMAGE A's style/materials to IMAGE B silently ran
`flux_img2img_dual.json`, whose reference branch is inert.

Also guards ROUTING_TRUTHFULNESS_V1: the envelope reported
`mode: CHAT_WITH_IMAGE, render: false` for a turn that had rendered.

Run:
  ./.venv/Scripts/python.exe -m pytest tests/test_reference_transfer_policy_v1.py -q \
      --basetemp=runs/_pytest_tmp_rtp
"""

import pytest

from core.render.dual_image_conditioning_v1 import (
    parse_conditioned_flag,
    resolve_conditioning,
)
from core.vision.image_intent_v1 import build_mode_contract


PAIR = {"A": {"filename": "ref.png"}, "B": {"filename": "target.png"}}

TRANSFER_EN = (
    "Transfer the neoclassical style and the light travertine facade material "
    "from the reference facade onto this target building."
)
TRANSFER_FA = "سبک و متریال این عکس را روی ساختمان هدف اعمال کن."
COMPARE_EN = "Compare these two building photographs and tell me the differences."

READY = {"status": "ready", "missing": [], "invalid": []}
BLOCKED = {
    "status": "blocked",
    "missing": [{"role": "uso_projector"}],
    "invalid": [],
}


def _resolve(**kwargs):
    kwargs.setdefault("capability", READY)
    return resolve_conditioning(**kwargs)


# ----------------------------------------------------------
# 1. TRI-STATE FLAG PARSING
# ----------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (None, None),
    ("", False),
    ("0", False),
    ("false", False),
    ("off", False),
    ("1", True),
    ("true", True),
    ("on", True),
    (True, True),
    (False, False),
])
def test_conditioned_flag_is_tri_state(value, expected):
    """`bool("0")` is True - the multipart OFF must not switch it on."""
    assert parse_conditioned_flag(value) is expected


# ----------------------------------------------------------
# 2. TRANSFER IS DERIVED FROM THE CONTRACTS
# ----------------------------------------------------------

def test_explicit_english_transfer_selects_the_conditioned_graph():
    decision = _resolve(
        role_bindings=PAIR,
        reference_policy={"referenced": True, "role": "style_only"},
        mode="image_to_image",
        text=TRANSFER_EN,
    )
    assert decision["conditioned"] is True
    assert decision["source"] == "reference_transfer_intent"
    assert decision["capability_status"] == "ready"


def test_persian_transfer_selects_the_conditioned_graph():
    decision = _resolve(
        role_bindings=PAIR,
        reference_policy={"referenced": True, "role": "style_only"},
        mode="image_to_image",
        text=TRANSFER_FA,
    )
    assert decision["conditioned"] is True


def test_material_only_role_also_transfers():
    decision = _resolve(
        role_bindings=PAIR,
        reference_policy={"referenced": True, "role": "material_only"},
        mode="image_to_image",
        text="use the material from this reference only",
    )
    assert decision["conditioned"] is True


# ----------------------------------------------------------
# 3. ORDINARY COMPARISON / ANALYSIS IS NOT A TRANSFER
# ----------------------------------------------------------

def test_comparison_request_is_not_upgraded_to_a_render():
    decision = _resolve(
        role_bindings=PAIR,
        reference_policy={"referenced": True, "role": "style_only"},
        mode="image_to_image",
        text=COMPARE_EN,
    )
    assert decision["conditioned"] is False
    assert decision["blocked_reason"] == "comparison_request"


def test_analysis_mode_never_selects_a_render_graph():
    decision = _resolve(
        role_bindings=PAIR,
        reference_policy={"referenced": True, "role": "style_only"},
        mode="analyze_image",
        text=TRANSFER_EN,
    )
    assert decision["conditioned"] is False
    assert decision["blocked_reason"] == "mode_is_not_a_render_mode"


def test_plain_two_image_message_without_a_transfer_role_does_not_condition():
    decision = _resolve(
        role_bindings=PAIR,
        reference_policy={"referenced": True, "role": "inspiration_only"},
        mode="image_to_image",
        text="make the facade darker",
    )
    assert decision["conditioned"] is False
    assert decision["blocked_reason"] == "no_transfer_role_requested"


def test_single_image_never_conditions():
    decision = _resolve(
        role_bindings={"B": {"filename": "target.png"}},
        reference_policy={"referenced": True, "role": "style_only"},
        mode="image_to_image",
        text=TRANSFER_EN,
    )
    assert decision["conditioned"] is False
    assert decision["blocked_reason"] == "role_pair_absent"


# ----------------------------------------------------------
# 4. EXPLICIT UI OVERRIDE WINS
# ----------------------------------------------------------

def test_explicit_ui_opt_in_beats_the_derivation():
    decision = _resolve(
        role_bindings=PAIR,
        reference_policy={"referenced": False, "role": "none"},
        mode="image_to_image",
        text="do something",
        explicit=True,
    )
    assert decision["conditioned"] is True
    assert decision["source"] == "explicit_ui"


def test_explicit_ui_opt_out_beats_a_transfer_request():
    decision = _resolve(
        role_bindings=PAIR,
        reference_policy={"referenced": True, "role": "style_only"},
        mode="image_to_image",
        text=TRANSFER_EN,
        explicit=False,
    )
    assert decision["conditioned"] is False
    assert decision["reason"] == "explicit_ui_opt_out"


# ----------------------------------------------------------
# 5. CAPABILITY GATE
# ----------------------------------------------------------

def test_missing_conditioning_models_downgrade_with_a_truthful_reason():
    decision = resolve_conditioning(
        role_bindings=PAIR,
        reference_policy={"referenced": True, "role": "style_only"},
        mode="image_to_image",
        text=TRANSFER_EN,
        capability=BLOCKED,
    )
    assert decision["conditioned"] is False
    assert decision["blocked_reason"] == "conditioning_models_unavailable"
    assert decision["capability_status"] == "blocked"


# ----------------------------------------------------------
# 6. ROUTING ENVELOPE TELLS THE TRUTH
# ----------------------------------------------------------

def test_executed_render_is_reported_even_when_intent_was_chat():
    """The measured Test E false negative."""
    contract = build_mode_contract(
        {"type": "image_render", "vision": {"intent": "analyze"}},
        has_image=True,
    )
    assert contract["render"] is True
    assert contract["mode"] == "IMAGE_EDIT"


def test_text_to_image_render_is_reported():
    contract = build_mode_contract({"type": "image_render"}, has_image=False)
    assert contract["render"] is True
    assert contract["mode"] == "TEXT_TO_IMAGE"


def test_analysis_still_reports_no_render():
    contract = build_mode_contract(
        {"type": "image_analysis", "vision": {"intent": "analyze"}},
        has_image=True,
    )
    assert contract["render"] is False
    assert contract["mode"] == "IMAGE_ANALYSIS"


def test_plain_chat_still_reports_no_render():
    contract = build_mode_contract({"type": "chat"}, has_image=False)
    assert contract["render"] is False
    assert contract["mode"] == "CHAT"
