# -*- coding: utf-8 -*-
"""CHAT_APP_CREATION_ROUTING_V1 — natural-language app requests.

These are OFFLINE tests. They never call the coding model, never create a file
and never package anything. They pin the routing decision that was wrong: an
ordinary Persian request to build an application must reach ArchitectOS's own
code workflow instead of being answered by the chat model as "impossible".
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.cognition.intent_engine import (  # noqa: E402
    app_creation_request,
    intent_engine,
)

# The two requests that failed in the live UI acceptance, verbatim.
REQUEST_A = (
    "یک برنامه ماشین‌حساب گرافیکی برای ویندوز بساز.\n\n"
    "برنامه باید با Python و Tkinter نوشته شود و پنجره گرافیکی با دکمه‌های "
    "اعداد ۰ تا ۹، جمع، تفریق، ضرب، تقسیم، اعشار، مساوی و پاک‌کردن داشته باشد.\n\n"
    "تقسیم بر صفر را مدیریت کند و با موس و صفحه‌کلید کار کند.\n\n"
    "کد کامل Python را خودت تولید کن و برای ذخیره آن از من تأیید بگیر.\n\n"
    "بعد از ذخیره و بررسی صحت کد، با تأیید جداگانه من آن را به EXE ویندوز "
    "تبدیل کن و فایل نهایی را برای دانلود در پروژه قرار بده."
)

REQUEST_B = (
    "یک ماشین‌حساب گرافیکی با دکمه‌های اعداد بساز و فایل EXE آن را تحویل بده."
)


def _intent(text):
    result = intent_engine.analyze(text)
    return getattr(result, "intent", None)


# -- the two live failures ---------------------------------------------
def test_request_b_enters_the_code_capability_boundary():
    """Regression: B used to fall through to ordinary chat."""
    assert _intent(REQUEST_B) == "code_request"


def test_request_a_enters_the_code_capability_boundary():
    assert _intent(REQUEST_A) == "code_request"


def test_request_b_is_recognised_as_app_creation():
    assert app_creation_request(REQUEST_B) is True


def test_request_a_is_recognised_as_app_creation():
    assert app_creation_request(REQUEST_A) is True


# -- controls: nothing else may be captured ----------------------------
@pytest.mark.parametrize("text", [
    "یک ساختمان مسکونی ۳ طبقه طراحی کن",
    "برای این ساختمان یک برنامه فضایی بنویس",
    "نقشه پلان طبقه اول را بساز",
    "نمای جنوبی را با آجر قرمز بازطراحی کن",
])
def test_architectural_requests_are_never_captured(text):
    assert app_creation_request(text) is False
    assert _intent(text) != "code_request"


@pytest.mark.parametrize("text", [
    "سلام، حالت چطوره؟",
    "امروز هوا چطور است؟",
    "این عکس را برایم توضیح بده",
])
def test_general_conversation_stays_chat(text):
    assert app_creation_request(text) is False
    assert _intent(text) == "chat"


def test_app_object_without_create_verb_is_not_app_creation():
    assert app_creation_request("ماشین‌حساب گرافیکی") is False


def test_create_verb_without_app_object_is_not_app_creation():
    assert app_creation_request("یک فایل بساز") is False


# -- the detector is product-agnostic ----------------------------------
@pytest.mark.parametrize("text", [
    "یک ماشین‌حساب گرافیکی بساز",
    "یک برنامه یادداشت‌برداری با Tkinter بساز",
    "یک بازی ساده برای ویندوز درست کن",
    "یک ابزار گرافیکی کوچک ایجاد کن",
    "build me a desktop app in Python",
])
def test_app_creation_is_not_calculator_specific(text):
    assert app_creation_request(text) is True


# -- authorization is still required, and the refusal is actionable ----
def test_untrusted_request_is_refused_with_recovery_guidance():
    """No model call, no file, and the message must say how to recover."""
    from core.chat.chat_architect import ChatArchitect

    class _Stub(object):
        context = {
            "trusted_local_authorization": {
                "trusted": False,
                "reason": "proxy_timestamp_invalid",
                "project_id": "project_x",
            }
        }
        _CODE_CREATE_ACTIONS = ChatArchitect._CODE_CREATE_ACTIONS
        _CODE_FILENAME_RE = ChatArchitect._CODE_FILENAME_RE
        DEFAULT_APP_FILENAME = ChatArchitect.DEFAULT_APP_FILENAME

    message = ChatArchitect._authorized_code_file_creation(
        _Stub(), REQUEST_B, "project_x")

    assert isinstance(message, str)
    # refused, and says nothing was generated
    assert "هیچ مدلی فراخوانی نشد" in message
    # actionable: names the recovery mechanism instead of dead-ending
    assert "local-bootstrap" in message
    assert "دوباره" in message


def test_default_filename_exists_and_is_generic():
    from core.chat.chat_architect import ChatArchitect

    assert ChatArchitect.DEFAULT_APP_FILENAME == "app.py"


def test_default_filename_is_guarded_by_app_creation_only():
    """A non-app request must still fail the filename gate (return None)."""
    from core.chat.chat_architect import ChatArchitect

    class _Stub(object):
        context = {
            "trusted_local_authorization": {
                "trusted": True, "project_id": "project_x"}
        }
        _CODE_CREATE_ACTIONS = ChatArchitect._CODE_CREATE_ACTIONS
        _CODE_FILENAME_RE = ChatArchitect._CODE_FILENAME_RE
        DEFAULT_APP_FILENAME = ChatArchitect.DEFAULT_APP_FILENAME

    # "بساز" is a create action but there is no app object, so the guard holds.
    result = ChatArchitect._authorized_code_file_creation(
        _Stub(), "یک فایل بساز", "project_x")
    assert result is None
