# ==========================================================
# ArchitectOS — POST-RENDER ROUTING V1
#
# Regression tests for the measured routing defects:
#
#   A — a previous render must not turn every later text turn into
#       an image edit.
#   B — a generic "make" must not capture a programming request.
#   D — an explicitly selected UI mode is authoritative, while
#       Chat mode must never execute a render.
#
# Every case mirrors the production intent_context built by
# ChatArchitect.handle(): the compiled edit delta is ALWAYS present,
# because core/intent_router.py reads it from the context.
#
# NO GPU. NO COMFYUI. NO NETWORK.
# ==========================================================

import pytest

from core.intent_router import IntentRouter
from core.cognition.intent_engine import _has_programming_signal
from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta


# A session in which a render has already been produced.
POST_RENDER = {
    "last_render_asset": "outputs/B1_output.png",
    "last_render_image": "outputs/B1_output.png",
    "last_image_asset": "outputs/B1_output.png",
    "last_route_intent": "image",
    "last_model_role": "architect",
    "turn_index": 12,
    "waiting_image_edit": False,
}

POST_RENDER_WAITING = dict(POST_RENDER, waiting_image_edit=True)

CLEAN = {"turn_index": 3, "last_model_role": None}

ARCH = {"is_architecture": True}
NOT_ARCH = {"is_architecture": False}


def route(text, context):
    """Call the real router exactly the way ChatArchitect does."""
    ctx = dict(context)
    ctx["image_edit_delta"] = compile_edit_delta(text)
    return IntentRouter().route(text, None, ctx)


# ==========================================================
# A — TEXT CHAT AFTER A RENDER
# ==========================================================

@pytest.mark.parametrize(
    "text",
    [
        "What is the difference between load-bearing and framed structure?",
        "تفاوت سازه باربر و اسکلت چیست؟",
        "Explain the difference between a shear wall and a moment frame.",
        "چرا از دیوار برشی استفاده می‌کنیم؟",
    ],
)
def test_a_text_chat_after_render_stays_chat(text):
    result = route(text, {"conversation_state": POST_RENDER, "conversation_intent": ARCH})
    assert result["intent"] == "chat", result
    assert result["mode"] == "conversation", result


# ==========================================================
# B — PROGRAMMING AFTER A RENDER
# ==========================================================

@pytest.mark.parametrize(
    "text",
    [
        "Now make it iterative instead of recursive and keep the same function name.",
        "Rewrite that Python function iteratively instead of recursively.",
        "Can you make that algorithm O(n log n) instead?",
    ],
)
def test_b_programming_after_render_stays_chat(text):
    result = route(text, {"conversation_state": POST_RENDER, "conversation_intent": ARCH})
    assert result["intent"] == "chat", result


def test_b_programming_is_not_captured_even_while_waiting_for_an_edit():
    """`waiting_image_edit` must not be enough on its own."""
    text = "Now make it iterative instead of recursive and keep the same function name."
    result = route(
        text,
        {"conversation_state": POST_RENDER_WAITING, "conversation_intent": ARCH},
    )
    assert result["intent"] == "chat", result


def test_b_measured_programming_turn_is_not_a_structured_edit():
    """The measured turn must not compile into a classified edit delta."""
    delta = compile_edit_delta(
        "Now make it iterative instead of recursive and keep the same function name."
    )
    assert delta["edit_class"] == "generic_edit", delta


# ==========================================================
# C — LEGITIMATE ARCHITECTURAL FOLLOW-UPS STILL EDIT
# ==========================================================

@pytest.mark.parametrize(
    "text",
    [
        "حالا رنگ آجرهای همان نما را کمی روشن‌تر کن.",
        "Make the brick on that facade a little lighter.",
    ],
)
def test_c_architectural_followup_after_render_still_edits(text):
    result = route(text, {"conversation_state": POST_RENDER, "conversation_intent": ARCH})
    assert result["intent"] == "image", result
    assert result["mode"] == "edit", result


# ==========================================================
# D — EXPLICIT MODES
# ==========================================================

def test_d_manual_text_to_image_is_authoritative():
    result = route(
        "A neoclassical villa with travertine cladding.",
        {
            "conversation_state": CLEAN,
            "conversation_intent": ARCH,
            "mode": "text_to_image",
            "routing_source": "manual",
        },
    )
    assert result["intent"] == "image", result
    assert result["mode"] == "generate", result
    assert result["source"] == "validated_manual_mode"


def test_d_manual_chat_never_renders_after_a_render():
    result = route(
        "What is the difference between load-bearing and framed structure?",
        {
            "conversation_state": POST_RENDER,
            "conversation_intent": ARCH,
            "mode": "chat",
            "routing_source": "manual",
        },
    )
    assert result["intent"] == "chat", result
    assert result["mode"] == "conversation", result


def test_d_manual_image_to_image_uses_the_existing_render():
    result = route(
        "A lighter brick facade.",
        {
            "conversation_state": POST_RENDER,
            "conversation_intent": ARCH,
            "mode": "image_to_image",
            "routing_source": "manual",
        },
    )
    assert result["intent"] == "image", result
    assert result["mode"] == "edit", result


def test_d_manual_image_to_image_without_any_source_asks_for_upload():
    result = route(
        "A lighter brick facade.",
        {
            "conversation_state": CLEAN,
            "conversation_intent": ARCH,
            "mode": "image_to_image",
            "routing_source": "manual",
        },
    )
    assert result["mode"] == "waiting_for_upload", result


def test_d_auto_mode_is_not_authoritative():
    """`mode` alone must not be trusted when the strategy says auto."""
    result = route(
        "What is the difference between load-bearing and framed structure?",
        {
            "conversation_state": POST_RENDER,
            "conversation_intent": ARCH,
            "mode": "text_to_image",
            "routing_source": "auto",
        },
    )
    assert result["intent"] == "chat", result


# ==========================================================
# E — GENERIC CREATION FALLBACK
# ==========================================================

def test_e_generic_creation_request_renders():
    result = route(
        "Generate a simple white cube.",
        {"conversation_state": CLEAN, "conversation_intent": NOT_ARCH},
    )
    assert result["intent"] == "image", result
    assert result["mode"] == "generate", result


def test_e_non_visual_artefact_is_not_a_render():
    result = route(
        "Create a report about brick facades.",
        {"conversation_state": CLEAN, "conversation_intent": NOT_ARCH},
    )
    assert result["intent"] == "chat", result
