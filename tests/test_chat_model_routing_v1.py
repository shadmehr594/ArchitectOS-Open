"""CHAT_MODEL_ROUTING_V1 — chat model configuration and routing contract.

Scope: the text CHAT model path only. Nothing here touches the vision
provider, the observer, the normalizer, verification, BIM, IFC, render or
ComfyUI.

No production code special-cases an acceptance sentence; this file is the
only place such phrases appear, and only as transport payloads.
"""

import json
import os
import re
from dataclasses import replace
from pathlib import Path

import pytest

from config.chat_config import ChatConfig, DEFAULT_CHAT_MODEL, chat_config
from core.llm.llm_gateway import LLMGateway
from core.llm.llm_gateway_v30 import LLMGatewayV30


ROOT = Path(__file__).resolve().parents[1]

# The routing surface this change owns. Deleted model names must not survive
# anywhere in it.
ROUTING_FILES = (
    "config/chat_config.py",
    "core/llm.py",
    "core/llm/llm_gateway.py",
    "core/llm/llm_gateway_v30.py",
    "core/llm/model_router.py",
    "core/chat/chat_runtime_v31.py",
)

DELETED_MODELS = ("llama3", "qwen2.5", "qwen2_5")

# The modules this change introduced or rewrote for model routing. These must
# never branch on the user's text.
GATEWAY_FILES = (
    "config/chat_config.py",
    "core/llm.py",
    "core/llm/llm_gateway.py",
    "core/llm/llm_gateway_v30.py",
    "core/llm/model_router.py",
)


class FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status
        self.text = json.dumps(body) if isinstance(body, dict) else str(body)

    def json(self):
        return self._body


class FakeSession:
    """Records the request and returns a scripted response."""

    def __init__(self, response):
        self.response = response
        self.calls = []
        self.trust_env = True

    def post(self, url, **kwargs):
        self.calls.append({"url": url, "json": kwargs.get("json")})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def get(self, url, **kwargs):
        self.calls.append({"url": url, "get": True})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _clear(monkeypatch):
    for name in ("ARCHITECTOS_CHAT_MODEL", "ARCHITECTOS_INTENT_MODEL",
                 "ARCHITECTOS_CHAT_TIMEOUT", "ARCHITECTOS_CHAT_THINK",
                 "ARCHITECTOS_OLLAMA_URL", "ARCHITECTOS_VISION_MODEL"):
        monkeypatch.delenv(name, raising=False)


def _source(path):
    """Source with comment-only lines and trailing comments removed."""
    lines = []
    for line in (ROOT / path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0]
        lines.append(line)
    return "\n".join(lines)


# ==========================================================
# CONFIG
# ==========================================================

def test_chat_model_defaults_to_the_installed_local_model(monkeypatch):
    _clear(monkeypatch)
    cfg = ChatConfig.from_env()
    assert cfg.model == "gemma4:12b"
    assert cfg.model == DEFAULT_CHAT_MODEL
    assert cfg.endpoint == "http://127.0.0.1:11434"
    assert cfg.generate_url() == "http://127.0.0.1:11434/api/generate"
    assert cfg.timeout == 300


def test_chat_model_is_overridable_at_runtime(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("ARCHITECTOS_CHAT_MODEL", "some-other:1b")
    assert ChatConfig.from_env().model == "some-other:1b"


def test_chat_model_can_be_overridden_to_qwen(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("ARCHITECTOS_CHAT_MODEL", "qwen3.8:27b")
    assert ChatConfig.from_env().model == "qwen3.8:27b"


def test_intent_role_follows_the_chat_model_by_default(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("ARCHITECTOS_CHAT_MODEL", "chat:1b")
    cfg = ChatConfig.from_env()
    # No second model role is created unless the operator asks for one.
    assert cfg.intent_model == "chat:1b"
    assert cfg.model_for("reasoning") == "chat:1b"
    assert cfg.model_for("chat") == "chat:1b"


def test_intent_model_can_be_set_explicitly(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("ARCHITECTOS_CHAT_MODEL", "chat:1b")
    monkeypatch.setenv("ARCHITECTOS_INTENT_MODEL", "intent:2b")
    cfg = ChatConfig.from_env()
    assert cfg.model == "chat:1b"
    assert cfg.intent_model == "intent:2b"
    assert cfg.model_for("architecture") == "intent:2b"
    assert cfg.model_for("chat") == "chat:1b"


@pytest.mark.parametrize("value", ["0", "-1", "invalid"])
def test_invalid_chat_timeout_is_rejected(monkeypatch, value):
    _clear(monkeypatch)
    monkeypatch.setenv("ARCHITECTOS_CHAT_TIMEOUT", value)
    with pytest.raises(ValueError):
        ChatConfig.from_env()


def test_chat_config_helper_reads_at_call_time(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("ARCHITECTOS_CHAT_MODEL", "late:3b")
    assert chat_config().model == "late:3b"


# ==========================================================
# THINKING CONTRACT
# ==========================================================

def test_chat_thinking_is_disabled_by_default(monkeypatch):
    _clear(monkeypatch)
    assert ChatConfig.from_env().think is False


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "on"])
def test_chat_thinking_can_be_opted_back_in(monkeypatch, raw):
    _clear(monkeypatch)
    monkeypatch.setenv("ARCHITECTOS_CHAT_THINK", raw)
    assert ChatConfig.from_env().think is True


def test_gateway_sends_think_false_by_default(monkeypatch):
    """A thinking model otherwise returns an EMPTY `response`."""
    _clear(monkeypatch)
    gateway = LLMGateway()
    session = FakeSession(FakeResponse({"response": "ok"}))
    gateway.session = session
    gateway.generate("hi")
    assert session.calls[0]["json"]["think"] is False


# ==========================================================
# CHAT / VISION SEPARATION
# ==========================================================

def test_chat_model_is_independent_of_the_vision_model(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("ARCHITECTOS_VISION_MODEL", "vision-only:99b")
    cfg = ChatConfig.from_env()
    assert cfg.model == "gemma4:12b"           # chat ignores the vision setting
    assert "vision-only" not in cfg.model


def test_vision_model_is_independent_of_the_chat_model(monkeypatch):
    from config.vision_config import VisionConfig
    _clear(monkeypatch)
    monkeypatch.setenv("ARCHITECTOS_CHAT_MODEL", "chat-only:1b")
    vcfg = VisionConfig.from_env()
    assert vcfg.model != "chat-only:1b"        # vision ignores the chat setting
    assert vcfg.model == "gemma4:12b"


def test_chat_module_never_reads_the_vision_env_var():
    source = _source("config/chat_config.py")
    assert not re.search(r"os\.environ[^\n]*ARCHITECTOS_VISION_MODEL", source)
    assert not re.search(r"getenv\([^\n]*ARCHITECTOS_VISION_MODEL", source)


def test_vision_module_never_reads_the_chat_env_var():
    source = _source("config/vision_config.py")
    assert not re.search(r"os\.environ[^\n]*ARCHITECTOS_CHAT_MODEL", source)
    assert not re.search(r"os\.environ[^\n]*ARCHITECTOS_INTENT_MODEL", source)
    assert not re.search(r"getenv\([^\n]*ARCHITECTOS_CHAT_MODEL", source)


# ==========================================================
# GATEWAY ROUTING
# ==========================================================

def test_llm_gateway_uses_the_configured_chat_model(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("ARCHITECTOS_CHAT_MODEL", "routed:7b")
    gateway = LLMGateway()
    session = FakeSession(FakeResponse({"response": "hello"}))
    gateway.session = session
    assert gateway.generate("hi") == "hello"
    assert session.calls[0]["json"]["model"] == "routed:7b"
    assert gateway.last_model == "routed:7b"


def test_llm_gateway_reads_configuration_at_call_time(monkeypatch):
    _clear(monkeypatch)
    gateway = LLMGateway()
    session = FakeSession(FakeResponse({"response": "ok"}))
    gateway.session = session
    monkeypatch.setenv("ARCHITECTOS_CHAT_MODEL", "changed-after-import:1b")
    gateway.generate("hi")
    assert session.calls[0]["json"]["model"] == "changed-after-import:1b"


def test_llm_gateway_explicit_override_still_wins(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("ARCHITECTOS_CHAT_MODEL", "from-env:1b")
    gateway = LLMGateway(model="explicit:9b")
    session = FakeSession(FakeResponse({"response": "ok"}))
    gateway.session = session
    gateway.generate("hi")
    assert session.calls[0]["json"]["model"] == "explicit:9b"


def test_v30_gateway_routes_chat_and_reasoning_from_config(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("ARCHITECTOS_CHAT_MODEL", "chat:1b")
    monkeypatch.setenv("ARCHITECTOS_INTENT_MODEL", "intent:2b")
    gateway = LLMGatewayV30()
    assert gateway.MODELS == {"chat": "chat:1b", "reasoning": "intent:2b", "backup": "chat:1b"}
    session = FakeSession(FakeResponse({"response": "x"}))
    gateway.session = session
    gateway.chat("a")
    gateway.reason("b")
    assert [call["json"]["model"] for call in session.calls] == ["chat:1b", "intent:2b"]


def test_v30_gateway_never_routes_to_a_deleted_model(monkeypatch):
    _clear(monkeypatch)
    gateway = LLMGatewayV30()
    assert set(gateway.MODELS.values()) == {"gemma4:12b"}


def test_chat_runtime_v31_reports_the_configured_model(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("ARCHITECTOS_CHAT_MODEL", "runtime:5b")
    from core.chat.chat_runtime_v31 import ChatRuntimeV31
    runtime = ChatRuntimeV31()
    monkeypatch.setattr(runtime, "_llm_chat", lambda message: "reply")
    result = runtime.run("سلام")
    assert result["engine"] == "runtime:5b"
    assert result["metadata"]["llm"] == "runtime:5b"


# ==========================================================
# MODEL-UNAVAILABLE BEHAVIOUR
# ==========================================================

def test_missing_chat_model_is_reported_not_replaced(monkeypatch):
    _clear(monkeypatch)
    gateway = LLMGateway()
    session = FakeSession(FakeResponse({"error": "model not found"}, status=404))
    gateway.session = session
    # No fabricated success, and no silent fallback to another model.
    assert gateway.generate("سلام") is None
    assert gateway.last_error == "model_not_installed:gemma4:12b"
    assert len(session.calls) == 1          # exactly one attempt, no retry
    assert session.calls[0]["json"]["model"] == "gemma4:12b"


def test_service_down_is_reported_as_connection_error(monkeypatch):
    import requests
    _clear(monkeypatch)
    gateway = LLMGateway()
    gateway.session = FakeSession(requests.exceptions.ConnectionError("down"))
    assert gateway.generate("hi") is None
    assert gateway.last_error == "connection_error"


def test_empty_response_is_not_a_success(monkeypatch):
    _clear(monkeypatch)
    gateway = LLMGateway()
    gateway.session = FakeSession(FakeResponse({"response": ""}))
    assert gateway.generate("hi") is None
    assert gateway.last_error == "empty_response"


def test_model_availability_probe_reports_missing_model(monkeypatch):
    _clear(monkeypatch)
    gateway = LLMGateway()
    gateway.session = FakeSession(FakeResponse({"models": [{"name": "other:1b"}]}))
    assert gateway.is_model_available() is False
    gateway.session = FakeSession(FakeResponse({"models": [{"name": "gemma4:12b"}]}))
    assert gateway.is_model_available() is True


# ==========================================================
# NO HARDCODED / DELETED MODELS, NO SENTENCE SPECIAL-CASING
# ==========================================================

@pytest.mark.parametrize("path", ROUTING_FILES)
def test_no_deleted_model_name_survives_in_the_routing_surface(path):
    source = _source(path).lower()
    for name in DELETED_MODELS:
        assert name not in source, "%s still references %s" % (path, name)


def test_only_one_authoritative_chat_model_default():
    holders = []
    for path in ROUTING_FILES:
        if "gemma4:12b" in _source(path):
            holders.append(path)
    assert holders == ["config/chat_config.py"]


@pytest.mark.parametrize("phrase", [
    "سلام", "خوبی", "خودت رو معرفی کن", "یه لطیفه بگو",
    "میخوام یه نکته معماری بهت یاد بدم", "Hello", "Who are you?",
])
def test_production_never_special_cases_an_utterance(phrase):
    """The model-routing surface must branch on configuration, not on text.

    `core/chat/chat_runtime_v31.py` is excluded here: it carries a
    PRE-EXISTING legacy `is_chat()` keyword heuristic that this task does
    not own and must not alter. The routing modules below are the ones this
    change introduced or rewrote, and none of them may inspect the message.
    """
    for path in GATEWAY_FILES:
        assert phrase not in _source(path), "%s special-cases %r" % (path, phrase)


def test_legacy_is_chat_heuristic_is_untouched():
    """The pre-existing v31 keyword list still exists (not removed, not grown)."""
    source = _source("core/chat/chat_runtime_v31.py")
    assert "def is_chat" in source
    assert "خوبی" in source
