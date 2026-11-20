# -*- coding: utf-8 -*-
"""R2_UI_ANALYZE_MISROUTING_FIX_V1 — focused CPU regression.

The incident: the user selected "Analyze Image" and asked a descriptive
question. The backend received `mode=analyze_image` with
`routing_source=manual`, but `chat_architect` only honoured `image_to_image`
and let `analyze_image` fall through to the text classifier. That classifier
treats the deictic «این ساختمان» as an edit verb, so the turn was routed to
`_route_image_edit` and a real img2img render produced `edit_001_478ec6.png`.

These tests pin the decision, not the model: no Ollama, no GPU, no ComfyUI.
"""

import inspect

import pytest

from core.chat.chat_architect import _manual_image_intent
from core.intent_router import intent_router
from core.vision.image_intent_v1 import (
    classify_image_intent, INTENT_ANALYZE, INTENT_EDIT, INTENT_OBSERVE,
)
from core.vision.general_visual_observer_v1 import OBSERVER_VERSION

QUESTION = "این ساختمان چند طبقه دارد و چه مصالح و عناصری در نما دیده می‌شود؟"


# ==========================================================
# The incident, as history rather than as expected behaviour
#
# These two assertions used to REQUIRE the defect: the text classifier read the
# deictic «این ساختمان» as an edit verb. R2_AUTO_IMAGE_INTENT_SAFETY_V1 fixed
# that, so they now pin the CORRECTED behaviour. The manual-mode override is
# still proven in `test_auto_image_intent_safety_v1.py::
# test_manual_mode_still_takes_precedence_over_the_classifier`.
# ==========================================================

def test_incident_question_is_no_longer_an_edit():
    assert intent_router.is_image_edit_request(QUESTION) is False
    assert classify_image_intent(QUESTION, intent_router)["intent"] != INTENT_EDIT


def test_deictic_phrase_alone_is_not_an_edit_command():
    assert "این ساختمان" in QUESTION
    assert intent_router.is_image_edit_request("این ساختمان چند طبقه دارد؟") is False
    # a real imperative still routes to edit through the classifier vocabulary
    assert classify_image_intent("این ساختمان را حذف کن", intent_router)["intent"] == INTENT_EDIT


# ==========================================================
# GREEN — the explicit mode now decides
# ==========================================================

def test_analyze_mode_forces_analysis_not_edit():
    intent = _manual_image_intent("analyze_image", QUESTION, intent_router)
    assert intent["intent"] == INTENT_ANALYZE
    assert intent["reason"] == "validated_manual_mode"
    assert intent["matched"] == ["mode:analyze_image"]


@pytest.mark.parametrize("text", [
    QUESTION,
    "این ساختمان چند طبقه دارد؟",
    "چه مصالحی در نما دیده می‌شود؟",
    "Describe this facade.",
    "این ساختمان را شب کن",          # an explicit edit, in analyze mode
    "این ساختمان را بدون تغییر فرم شب کن",
])
def test_analyze_mode_never_returns_edit(text):
    """Requirement: Analyze Image can never silently become a render."""
    intent = _manual_image_intent("analyze_image", text, intent_router)
    assert intent["intent"] != INTENT_EDIT


def test_analyze_mode_keeps_observation_only_phrasing():
    intent = _manual_image_intent(
        "analyze_image", "فقط عناصر قابل مشاهده تصویر را لیست کن", intent_router)
    assert intent["intent"] in (INTENT_OBSERVE, INTENT_ANALYZE)
    assert intent["intent"] != INTENT_EDIT


def test_image_to_image_mode_is_unchanged():
    intent = _manual_image_intent("image_to_image", QUESTION, intent_router)
    assert intent["intent"] == INTENT_EDIT
    assert intent["reason"] == "validated_manual_mode"
    assert intent["matched"] == ["mode:image_to_image"]


def test_auto_mode_keeps_the_existing_classifier():
    """No manual mode → behaviour is byte-identical to before."""
    assert _manual_image_intent("", QUESTION, intent_router) == \
        classify_image_intent(QUESTION, intent_router)


# ==========================================================
# Acceptance matrix at the decision boundary
# ==========================================================

def test_matrix_1_analyze_with_facade_and_persian_question_is_analysis():
    intent = _manual_image_intent("analyze_image", QUESTION, intent_router)
    assert intent["intent"] == INTENT_ANALYZE


def test_matrix_2_analyze_on_a_previously_edited_asset_is_analysis():
    """The decision does not read the asset type, so an Edit #2 active asset
    cannot turn an analysis turn into another edit."""
    source = inspect.getsource(_manual_image_intent)
    for forbidden in ("image_to_image", "asset_type", "active"):
        if forbidden == "image_to_image":
            continue  # the explicit manual mode is the only legitimate use
        assert forbidden not in source
    assert _manual_image_intent(
        "analyze_image", QUESTION, intent_router)["intent"] == INTENT_ANALYZE


def test_matrix_3_analyze_on_the_original_upload_is_analysis():
    assert _manual_image_intent(
        "analyze_image", "این ساختمان چند طبقه دارد؟", intent_router
    )["intent"] == INTENT_ANALYZE


def test_matrix_5_explicit_image_to_image_still_works():
    intent = _manual_image_intent(
        "image_to_image", "این ساختمان را شب کن", intent_router)
    assert intent["intent"] == INTENT_EDIT


def test_matrix_7_analysis_cannot_create_an_image_to_image_asset():
    """Analysis never yields INTENT_EDIT, so `_route_image_edit` — the only
    producer of img2img assets — is unreachable from an analysis turn."""
    for text in (QUESTION, "این ساختمان چند طبقه دارد؟", "Analyze the facade"):
        assert _manual_image_intent(
            "analyze_image", text, intent_router)["intent"] != INTENT_EDIT


def test_matrix_12_observer_prompt_is_v2():
    assert OBSERVER_VERSION == "general-visual-observer-v2"


def test_waiting_edit_state_cannot_capture_an_analyze_turn():
    """Two inline gates can still route to edit on a lingering
    `waiting_image_edit` flag: the edit-session continuation and the
    edit-state override. Both must exempt an explicit Analyze turn.

    These gates live inside `_handle_internal` and cannot be reached without a
    provider, so the guard is pinned at source level.
    """
    from core.chat.chat_architect import ChatArchitect

    source = inspect.getsource(ChatArchitect._handle_internal)
    assert source.count('_manual_image_mode != "analyze_image"') >= 2
