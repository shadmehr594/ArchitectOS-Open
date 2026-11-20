# -*- coding: utf-8 -*-
"""R2_AUTO_IMAGE_INTENT_SAFETY_V1 — Auto mode must not render on a question.

`intent_router.is_image_edit_request()` listed the deictic «این ساختمان»
among its STRONG edit keywords, so a sentence that merely NAMES the subject was
treated as a modification command. In Auto mode that dispatched a real img2img
render for a descriptive question.

The deictic is a reference, not a verb. The classifier already has a
deictic-aware path (`_OBJECT_ANCHORS` + `_BARE_APPEARANCE_NOUNS`) and a full
imperative vocabulary, so the keyword only needs to stop standing alone.

No Ollama. No GPU. No ComfyUI.
"""

import inspect

import pytest

from core.intent_router import intent_router
from core.vision.image_intent_v1 import (
    classify_image_intent, has_edit_signal,
    INTENT_ANALYZE, INTENT_EDIT, INTENT_OBSERVE,
)
from core.chat.chat_architect import _manual_image_intent


DESCRIPTIVE_QUESTIONS = [
    "این ساختمان چند طبقه دارد و چه مصالح و عناصری در نما دیده می‌شود؟",
    "این ساختمان چند طبقه دارد؟",
    "چه متریالی در این نما استفاده شده؟",
    "آیا این ساختمان بالکن دارد؟",
    "What materials are visible on this building?",
    "این ساختمان چه رنگی است؟",
]

EDIT_COMMANDS = [
    "این ساختمان را شب کن",
    "مصالح نمای این ساختمان را تغییر بده",
    "دو پنجره به ساختمان اضافه کن",
    "Remove the balcony from this building",
    "Make this facade modern",
    "این ساختمان را بازطراحی کن",
]


def _auto(text):
    """Auto mode is exactly what `_manual_image_intent` does with no mode."""
    return _manual_image_intent("", text, intent_router)


# ==========================================================
# RED — the defect
# ==========================================================

def test_RED_deictic_alone_was_a_strong_edit_signal():
    """Before the fix this returned True and caused the render."""
    assert intent_router.is_image_edit_request("این ساختمان") is False


def test_RED_auto_question_was_classified_as_edit():
    """The exact incident sentence must not be an edit in Auto mode."""
    assert _auto(DESCRIPTIVE_QUESTIONS[0])["intent"] != INTENT_EDIT


# ==========================================================
# GREEN — descriptive questions never render
# ==========================================================

@pytest.mark.parametrize("text", DESCRIPTIVE_QUESTIONS)
def test_auto_descriptive_question_is_never_an_edit(text):
    intent = _auto(text)
    assert intent["intent"] in (INTENT_ANALYZE, INTENT_OBSERVE)
    assert intent["intent"] != INTENT_EDIT


@pytest.mark.parametrize("text", DESCRIPTIVE_QUESTIONS)
def test_auto_descriptive_question_has_no_edit_signal(text):
    ok, hits = has_edit_signal(text, intent_router)
    assert ok is False
    assert hits == []


# ==========================================================
# GREEN — explicit edits still route to edit
# ==========================================================

@pytest.mark.parametrize("text", EDIT_COMMANDS)
def test_auto_explicit_edit_is_still_an_edit(text):
    assert _auto(text)["intent"] == INTENT_EDIT


@pytest.mark.parametrize("text", [t for t in EDIT_COMMANDS
                                  if t != "Make this facade modern"])
def test_explicit_edit_signal_survives_without_the_deictic_keyword(text):
    """These carry a real imperative. ("Make this facade modern" is routed by
    the later same-subject-appearance branch, not by this predicate.)"""
    ok, hits = has_edit_signal(text, intent_router)
    assert ok is True and hits


def test_deictic_plus_appearance_is_still_an_edit():
    """The existing deictic path (anchor + appearance noun) must keep working."""
    assert _auto("این ساختمان را مدرن کن")["intent"] == INTENT_EDIT


def test_deictic_plus_imperative_verb_is_still_an_edit():
    assert _auto("این ساختمان را حذف کن")["intent"] == INTENT_EDIT


# ==========================================================
# Manual-mode precedence is untouched
# ==========================================================

@pytest.mark.parametrize("text", DESCRIPTIVE_QUESTIONS + EDIT_COMMANDS)
def test_manual_analyze_still_never_edits(text):
    assert _manual_image_intent(
        "analyze_image", text, intent_router)["intent"] != INTENT_EDIT


@pytest.mark.parametrize("text", EDIT_COMMANDS + DESCRIPTIVE_QUESTIONS)
def test_manual_image_to_image_still_edits(text):
    assert _manual_image_intent(
        "image_to_image", text, intent_router)["intent"] == INTENT_EDIT


# ==========================================================
# Dispatch safety
# ==========================================================

@pytest.mark.parametrize("text", DESCRIPTIVE_QUESTIONS)
def test_question_cannot_reach_the_edit_dispatcher(text):
    """The edit route in `_handle_internal` is gated on
    `image_intent["intent"] == INTENT_EDIT`. A question never satisfies it, so
    `_route_image_edit` — the only producer of img2img assets — is unreachable.
    """
    from core.chat.chat_architect import ChatArchitect

    source = inspect.getsource(ChatArchitect._handle_internal)
    assert 'if image_intent.get("intent") == INTENT_EDIT:' in source

    assert _auto(text)["intent"] != INTENT_EDIT


def test_manual_mode_still_takes_precedence_over_the_classifier():
    """An explicit Analyze turn wins even for a text the classifier calls edit."""
    text = "این ساختمان را شب کن"
    assert classify_image_intent(text, intent_router)["intent"] == INTENT_EDIT
    assert _manual_image_intent(
        "analyze_image", text, intent_router)["intent"] == INTENT_ANALYZE
