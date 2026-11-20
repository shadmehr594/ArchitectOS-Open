# -*- coding: utf-8 -*-
"""CODER-03 — DEDICATED CODING MODEL V1 (focused tests, mocked Ollama).

Verifies the exact model selected and the exact request payload for a coding
turn vs an ordinary turn, the config defaults/bounds, that the shared chat
gateway is never mutated, and that the routing boundary is unchanged for
architecture and for hard file requests.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.chat_config import (  # noqa: E402
    ChatConfig,
    DEFAULT_CHAT_MODEL,
    DEFAULT_CODER_MODEL,
    DEFAULT_CODER_NUM_PREDICT,
    MIN_CODER_NUM_PREDICT,
    MAX_CODER_NUM_PREDICT,
)
from core.llm.llm_gateway import LLMGateway, coder_gateway, llm_gateway  # noqa: E402
from core.intent_router import intent_router  # noqa: E402


class _FakeResp:
    status_code = 200
    text = '{"response":"ok"}'

    def json(self):
        return {"response": "print('hello')"}


def _capture(monkeypatch, gateway):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["payload"] = json
        captured["timeout"] = timeout
        return _FakeResp()

    monkeypatch.setattr(gateway.session, "post", fake_post)
    return captured


# ----------------------------------------------------------------------
# 1. Configuration
# ----------------------------------------------------------------------

def test_coder_config_defaults(monkeypatch):
    monkeypatch.delenv("ARCHITECTOS_CODER_MODEL", raising=False)
    monkeypatch.delenv("ARCHITECTOS_CODER_NUM_PREDICT", raising=False)
    cfg = ChatConfig.from_env()
    assert cfg.coder_model == DEFAULT_CODER_MODEL == "qwen3-coder:30b"
    assert cfg.coder_num_predict == DEFAULT_CODER_NUM_PREDICT
    # The general chat model is untouched.
    assert cfg.model == DEFAULT_CHAT_MODEL == "qwen3.8:27b"


def test_coder_env_override_and_bounds(monkeypatch):
    monkeypatch.setenv("ARCHITECTOS_CODER_MODEL", "my-coder:1b")
    monkeypatch.setenv("ARCHITECTOS_CODER_NUM_PREDICT", "999999")
    cfg = ChatConfig.from_env()
    assert cfg.coder_model == "my-coder:1b"
    assert cfg.coder_num_predict == MAX_CODER_NUM_PREDICT

    monkeypatch.setenv("ARCHITECTOS_CODER_NUM_PREDICT", "1")
    assert ChatConfig.from_env().coder_num_predict == MIN_CODER_NUM_PREDICT


# ----------------------------------------------------------------------
# 2. Exact model + payload (mocked Ollama)
# ----------------------------------------------------------------------

def test_coder_request_payload(monkeypatch):
    gw = coder_gateway()
    cap = _capture(monkeypatch, gw)
    gw.generate("یک ماشین‌حساب پایتون بنویس")
    assert cap["payload"]["model"] == "qwen3-coder:30b"
    assert cap["payload"]["think"] is False
    assert cap["payload"]["options"]["num_predict"] == DEFAULT_CODER_NUM_PREDICT
    assert cap["payload"]["options"]["temperature"] == 0.0


def test_general_chat_payload_unchanged(monkeypatch):
    gw = LLMGateway()
    cap = _capture(monkeypatch, gw)
    gw.generate("سلام، خوبی؟")
    assert cap["payload"]["model"] == "qwen3.8:27b"
    # The general chat path never gains an output-token cap.
    assert "num_predict" not in cap["payload"]["options"]


def test_shared_gateway_is_not_mutated():
    before_model = llm_gateway.model
    before_num = llm_gateway._num_predict_override
    gw = coder_gateway()
    assert gw is not llm_gateway
    assert llm_gateway.model == before_model == "qwen3.8:27b"
    assert llm_gateway._num_predict_override == before_num is None


# ----------------------------------------------------------------------
# 3. Routing boundary
# ----------------------------------------------------------------------

T1 = (
    "یک ماشین‌حساب با زبان Python بنویس که جمع، تفریق، ضرب و تقسیم را انجام "
    "دهد. کد کامل را بنویس."
)
T_TK = (
    "یک ماشین‌حساب گرافیکی زیبا با Python و Tkinter بساز. اگر نمی‌توانی فایل "
    "واقعی بسازی، کد کامل آن را همین‌جا در چت بنویس."
)
T_FILE_HARD = "یک فایل calculator.py بساز و آن را اجرا کن."


def _route(text):
    return intent_router.route(text, None, {})


def test_code_writing_uses_coder_role():
    assert _route(T1).get("model_role") == "coder"
    assert _route(T1).get("intent") == "chat"


def test_tkinter_conditional_fallback_uses_coder_role():
    assert _route(T_TK).get("intent") == "chat"
    assert _route(T_TK).get("model_role") == "coder"


def test_hard_file_request_has_no_coder_role():
    route = _route(T_FILE_HARD)
    assert route.get("intent") == "code"
    assert route.get("mode") == "capability"
    assert route.get("model_role") is None


def test_architecture_still_designs():
    for text, expected in [
        ("یک ساختمان بساز", "design_request"),
        ("پلان ساختمان ایجاد کن", "design_request"),
        ("یک ویلا طراحی کن", "villa_design"),
    ]:
        route = _route(text)
        assert route.get("intent") == "design", (text, route)
        assert route.get("model_role") is None, (text, route)
        assert route.get("design_type") == expected, (text, route)


def test_ordinary_conversation_has_no_coder_role():
    for text in ("سلام، خوبی؟", "خودت رو معرفی کن", "بیا درباره معماری حرف بزنیم"):
        route = _route(text)
        assert route.get("model_role") is None, (text, route)
        assert route.get("intent") == "chat", (text, route)
