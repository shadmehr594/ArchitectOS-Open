# -*- coding: utf-8 -*-
"""CHAT_CODING_CONDITIONAL_FALLBACK_FIX_V1 — focused tests.

The five live calculator scenarios, plus architecture preservation. A file
request with an explicit "write the code in the chat" fallback must reach the
code-writing chat route; a request that only requires a real file/execution
must still receive the honest capability response.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cognition.intent_engine import (  # noqa: E402
    _programming_request_kind,
    _explicit_chat_fallback,
)
from core.intent_router import intent_router  # noqa: E402


# The exact five live turns (project_2762d82a).
T1 = (
    "یک ماشین‌حساب با زبان Python بنویس که جمع، تفریق، ضرب و تقسیم را انجام "
    "دهد. امکان خروج از برنامه و جلوگیری از تقسیم بر صفر هم داشته باشد. "
    "کد کامل را بنویس."
)
T2 = (
    "حالا همین ماشین‌حساب را به‌صورت یک فایل واقعی به نام calculator.py در پروژه "
    "بساز. فقط کد را در چت نمایش نده. اگر ابزار ساخت فایل نداری، صریحاً اعلام کن"
)
T3 = (
    "فایل calculator.py را اجرا کن. عملیات جمع را انتخاب کن و اعداد ۵ و ۳ را "
    "وارد کن. نتیجه واقعی اجرای برنامه را گزارش بده. اگر امکان اجرای کد نداری، "
    "نتیجه فرضی را به‌جای نتیجه واقعی اعلام نکن."
)
T4 = (
    "به ماشین‌حساب قبلی قابلیت محاسبه توان و جذر اضافه کن. کد کامل نسخه جدید را "
    "بنویس و توضیح بده چه تغییراتی انجام دادی. فعلاً فایل نساز و کد را اجرا نکن."
)
T5 = (
    "برای من یک ماشین‌حساب پیشرفته و مدرن با رابط گرافیکی Python بساز. منظورم "
    "نرم‌افزار ماشین‌حساب است، نه خودرو یا ساختمان. اگر نمی‌توانی فایل واقعی "
    "بسازی، کد رابط گرافیکی را در همین چت بنویس."
)


def _route(text):
    return intent_router.route(text, None, {})


# ----------------------------------------------------------------------
# The five live scenarios
# ----------------------------------------------------------------------

def test_t1_write_code_in_chat():
    assert _programming_request_kind(T1) == "code_chat"
    assert _route(T1).get("intent") == "chat"
    assert _route(T1).get("model_role") == "coder"


def test_t2_real_file_declare_limitation():
    # fallback = "declare it" → still a hard capability request
    assert _programming_request_kind(T2) == "code_file"
    assert _route(T2) == {"intent": "code", "mode": "capability"}


def test_t3_execution_required():
    # fallback = "don't fake the result" → still a hard capability request
    assert _programming_request_kind(T3) == "code_file"
    assert _route(T3) == {"intent": "code", "mode": "capability"}


def test_t4_followup_stays_code_chat():
    assert _programming_request_kind(T4) == "code_chat"
    assert _route(T4).get("intent") == "chat"
    assert _route(T4).get("model_role") == "coder"


def test_t5_conditional_fallback_to_chat():
    # THE FIX — explicit "if you can't make a file, write the code in the chat"
    assert _explicit_chat_fallback(T5) is True
    assert _programming_request_kind(T5) == "code_chat"
    assert _route(T5).get("intent") == "chat"
    assert _route(T5).get("model_role") == "coder"


# ----------------------------------------------------------------------
# No programming turn may ever reach the design / BIM pipeline
# ----------------------------------------------------------------------

def test_no_programming_turn_reaches_design():
    for text in (T1, T2, T3, T4, T5):
        assert _route(text).get("intent") != "design", text


# ----------------------------------------------------------------------
# Fallback discrimination
# ----------------------------------------------------------------------

def test_negated_chat_reference_is_not_a_fallback():
    # "don't just show the code in the chat" must NOT read as a chat fallback
    text = (
        "یک فایل واقعی calculator.py بساز. فقط کد را در چت نمایش نده. "
        "اگر ابزار ساخت فایل نداری، اعلام کن"
    )
    assert _explicit_chat_fallback(text) is False
    assert _programming_request_kind(text) == "code_file"


def test_english_conditional_fallback():
    text = (
        "Build a modern GUI calculator in Python. If you can't create a real "
        "file, write the code in the chat."
    )
    assert _programming_request_kind(text) == "code_chat"
    assert _route(text).get("intent") == "chat"


def test_hard_file_request_without_fallback_stays_capability():
    text = "یک فایل calculator.py بساز و آن را اجرا کن."
    assert _programming_request_kind(text) == "code_file"
    assert _route(text) == {"intent": "code", "mode": "capability"}


# ----------------------------------------------------------------------
# Architectural design must still reach design
# ----------------------------------------------------------------------

def test_architecture_still_designs():
    cases = [
        ("یک ساختمان بساز", "design_request"),
        ("پلان ساختمان ایجاد کن", "design_request"),
        ("یک ویلا طراحی کن", "villa_design"),
    ]
    for text, expected in cases:
        route = _route(text)
        assert route.get("intent") == "design", (text, route)
        assert route.get("mode") == "create", (text, route)
        assert route.get("design_type") == expected, (text, route)
