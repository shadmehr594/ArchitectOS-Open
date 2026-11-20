# -*- coding: utf-8 -*-
"""CHAT_CODE_REQUEST_ROUTING_FIX_V1 — focused tests.

Verifies that a programming / code-file request can never enter the
architectural design pipeline, that genuine architectural commands are
preserved, that the calculator word is not read as a car, and that an empty
design result can no longer be announced as created-and-saved.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cognition.intent_engine import intent_engine  # noqa: E402
from core.intent_router import intent_router  # noqa: E402
from core.chat.response_adapter import ResponseAdapter  # noqa: E402
from core.prompt_intelligence.architectural_intent import (  # noqa: E402
    ArchitecturalIntent,
)


TURN_1 = (
    "برای من یک ماشین‌حساب ساده با زبان Python برنامه‌نویسی کن که چهار عمل "
    "اصلی جمع، تفریق، ضرب و تقسیم را انجام بدهد. کد کامل و قابل اجرا را بنویس"
)

TURN_2 = (
    "حالا همین ماشین‌حساب را به‌صورت یک فایل واقعی به نام calculator.py بساز، "
    "کد را از نظر خطاهای نحوی بررسی کن، آن را اجرا کن و نتیجه آزمایش جمع ۵ و ۳ "
    "را گزارش بده. اگر امکان ساخت فایل یا اجرای کد نداری، صریحاً اعلام کن."
)


# ----------------------------------------------------------------------
# 1. The reported misroute
# ----------------------------------------------------------------------

def test_turn_2_is_code_request_never_design():
    result = intent_engine.analyze(TURN_2)
    assert result.intent == "code_request", result.intent

    route = intent_router.route(TURN_2, None, {})
    assert route.get("intent") == "code", route
    assert route.get("mode") == "capability", route
    assert route.get("intent") != "design", route


def test_turn_1_stays_chat():
    # CODER-03 — the code-writing signal is now preserved as "code_chat"
    # (it still routes to the CHAT path, but with the coder model role).
    result = intent_engine.analyze(TURN_1)
    assert result.intent == "code_chat", result.intent

    route = intent_router.route(TURN_1, None, {})
    assert route.get("intent") == "chat", route
    assert route.get("model_role") == "coder", route


# ----------------------------------------------------------------------
# 2. Genuine architectural commands preserved
# ----------------------------------------------------------------------

def test_genuine_architectural_commands_still_design():
    cases = [
        ("یک ساختمان بساز", "design_request"),
        ("پلان ساختمان ایجاد کن", "design_request"),
        ("یک ویلا طراحی کن", "villa_design"),
        ("طراحی کن یک خانه", "design_request"),
    ]
    for text, expected in cases:
        result = intent_engine.analyze(text)
        assert result.intent == expected, (text, result.intent)
        route = intent_router.route(text, None, {})
        assert route.get("intent") == "design", (text, route)


def test_generic_verb_without_architecture_is_not_design():
    # "بساز" with no architectural object and no programming signal
    result = intent_engine.analyze("یک فایل بساز")
    assert result.intent != "design_request", result.intent
    assert intent_router.route("یک فایل بساز", None, {}).get("intent") != "design"


# ----------------------------------------------------------------------
# 3. Persian word-boundary: ماشین‌حساب is not a car
# ----------------------------------------------------------------------

def test_calculator_is_not_a_car():
    intent = ArchitecturalIntent().extract("یک ماشین‌حساب ساده بساز")
    objects = intent.get("objects") or []
    assert "modern car" not in objects, objects


def test_legitimate_vehicle_recognition_preserved():
    intent = ArchitecturalIntent().extract("یک ویلا با ماشین مدرن در محوطه")
    objects = intent.get("objects") or []
    assert "modern car" in objects, objects


# ----------------------------------------------------------------------
# 4. False-success prevention on empty design results
# ----------------------------------------------------------------------

def _degenerate_design():
    """The exact shape the misrouted turn produced: pipeline ran, all empty."""
    return {
        "type": "design",
        "engine": "GOD_CORE",
        "result": {
            "geometry": {
                "rooms": [], "floors": [], "levels": [], "walls": [],
                "doors": [], "windows": [],
            },
            "architectural_geometry": {"rooms": [], "walls": [], "spaces": []},
            "bim_elements": [],
            "assets": [],
        },
        "bim_result": {
            "status": "completed",
            "bim_elements": [],
            "assets": [],
        },
        "summary": {"building_type": "building", "style": "modern"},
    }


def test_generic_placeholders_do_not_prove_a_design():
    adapter = ResponseAdapter()
    assert adapter._design_was_created(
        _degenerate_design(), "building", "modern"
    ) is False


def test_real_design_is_still_recognised():
    adapter = ResponseAdapter()

    real_geometry = {
        "type": "design",
        "result": {"geometry": {"rooms": [{"x": 0, "y": 0, "w": 5, "h": 5}]}},
        "summary": {"building_type": "building", "style": "modern"},
    }
    assert adapter._design_was_created(real_geometry, "building", "modern") is True

    # a genuinely specific building type is evidence even without geometry
    specific = {"type": "design", "result": {}, "summary": {"building_type": "villa"}}
    assert adapter._design_was_created(specific, "villa", "modern") is True


def test_design_id_is_evidence():
    adapter = ResponseAdapter()
    assert adapter._design_was_created({"design_id": "d-1"}, "building", "modern") is True
