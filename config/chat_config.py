"""Runtime-only configuration for the text CHAT model path.

CHAT_MODEL_ROUTING_V1 — one authoritative default for the local chat model.

Scope: normal text conversation and the architectural intent parser's model
role. This module is deliberately independent of the vision configuration:

* it never reads ``ARCHITECTOS_VISION_MODEL``;
* ``config/vision_config.py`` never reads ``ARCHITECTOS_CHAT_MODEL``.

Changing the chat model therefore cannot change Vision, and changing the
vision model cannot change Chat.

Model roles are kept to the minimum the code actually needs. ``intent_model``
is not a second role by default: it follows ``model`` unless the operator
explicitly sets ``ARCHITECTOS_INTENT_MODEL``. The architectural intent parser
prefers deterministic parsing and only calls a model when the deterministic
Conversation Intent Boundary has not already resolved the turn.
"""

from dataclasses import dataclass
import os


# The already-installed local chat model. This is the ONE place the default
# lives; no other module hardcodes a chat model name.
DEFAULT_CHAT_MODEL = "qwen3.8:27b"

# A local model may need a long first call (model load + long Persian answer).
# The old 120 s ceiling cut real answers short and reported them as degraded.
# 300 s matches the budget the project already uses for its other large call
# (the vision observer).
DEFAULT_CHAT_TIMEOUT = 300

# CHAT_MODEL_ROUTING_V1 — thinking models put their chain of thought in a
# separate `thinking` field and can return an EMPTY `response` while the
# thinking budget is still being spent. Measured on this machine:
#   gemma4:12b, no `think` flag -> response "" (thinking 256 tokens)
#   gemma4:12b, think=false     -> response "سلام! چطور میتوانم به شما کمک کنم؟"
# The text-chat path wants the ANSWER, never the private reasoning, so the
# chat call disables thinking by default. Operators may opt back in with
# ARCHITECTOS_CHAT_THINK=1.
DEFAULT_CHAT_THINK = False

# CHAT-02D_LIVE_FAILURE_FIX — the chat call sends an explicit sampling
# temperature. The installed chat model's Modelfile defaults to 0.7, and at
# that temperature the model's READING of the user's request is unstable:
# measured on the real assembled prompt (N=5 each),
#   temperature 0.7 -> 2/5 answers switched the user's topic to a different,
#                      similar-looking one (a request about «معمایی» answered
#                      as «معماری»)
#   temperature 0.0 -> 0/5 such switches
# This is a sampling setting for the CHAT path only. It changes no model, no
# endpoint and no routing; operators may override it with
# ARCHITECTOS_CHAT_TEMPERATURE (e.g. 0.7 to restore the previous behaviour).
DEFAULT_CHAT_TEMPERATURE = 0.0


# ==========================================================
# CODER-03 — DEDICATED CODING MODEL (DEDICATED_CODING_MODEL_V1)
#
# A confirmed code-writing chat turn is answered by a dedicated local coder
# model; every other turn keeps the general chat model. The coder model is
# INDEPENDENT of DEFAULT_CHAT_MODEL — this module never rewrites the chat
# model, and the shared gateway is never mutated (the coding call builds its
# own per-call gateway).
# ==========================================================

DEFAULT_CODER_MODEL = "qwen3-coder:30b"

# The chat path sends no output-token cap, so a long program can be cut
# mid-line. The coder call therefore gets an explicit, bounded ceiling.
# NOTE: the EFFECTIVE ceiling is still Ollama's context window — the local
# qwen3-coder:30b was observed with an effective num_ctx of 4096, so this
# value only takes full effect once num_ctx is raised as well.
DEFAULT_CODER_NUM_PREDICT = 4096
MIN_CODER_NUM_PREDICT = 256
MAX_CODER_NUM_PREDICT = 16384

# Coding answers are long; give the coder call more headroom than chat.
DEFAULT_CODER_TIMEOUT = 600


def _bounded(name, default, low, high):
    value = int(os.environ.get(name, default))
    if value < low:
        return low
    if value > high:
        return high
    return value


def _positive(name, default):
    value = int(os.environ.get(name, default))
    if value <= 0:
        raise ValueError(name + " must be positive")
    return value


def _flag(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _temperature(name, default):
    """Sampling temperature for the chat call. Must be a finite number >= 0."""
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    value = float(raw)
    if value != value or value < 0:  # NaN or negative
        raise ValueError(name + " must be a number >= 0")
    return value


@dataclass(frozen=True)
class ChatConfig:
    model: str
    intent_model: str
    endpoint: str
    timeout: int
    think: bool
    temperature: float
    # CODER-03 — independent coding role. Defaulted so direct construction
    # keeps working unchanged.
    coder_model: str = DEFAULT_CODER_MODEL
    coder_num_predict: int = DEFAULT_CODER_NUM_PREDICT
    coder_timeout: int = DEFAULT_CODER_TIMEOUT

    @classmethod
    def from_env(cls, model=None):
        model = model or os.environ.get("ARCHITECTOS_CHAT_MODEL", DEFAULT_CHAT_MODEL)
        # One authoritative default: the intent role follows the chat model
        # unless the operator gives it its own explicit setting.
        intent_model = os.environ.get("ARCHITECTOS_INTENT_MODEL") or model
        return cls(
            model=model,
            intent_model=intent_model,
            endpoint=os.environ.get(
                "ARCHITECTOS_OLLAMA_URL", "http://127.0.0.1:11434"
            ).rstrip("/"),
            timeout=_positive("ARCHITECTOS_CHAT_TIMEOUT", DEFAULT_CHAT_TIMEOUT),
            think=_flag("ARCHITECTOS_CHAT_THINK", DEFAULT_CHAT_THINK),
            temperature=_temperature("ARCHITECTOS_CHAT_TEMPERATURE", DEFAULT_CHAT_TEMPERATURE),
            coder_model=os.environ.get("ARCHITECTOS_CODER_MODEL", DEFAULT_CODER_MODEL),
            coder_num_predict=_bounded(
                "ARCHITECTOS_CODER_NUM_PREDICT",
                DEFAULT_CODER_NUM_PREDICT,
                MIN_CODER_NUM_PREDICT,
                MAX_CODER_NUM_PREDICT,
            ),
            coder_timeout=_positive("ARCHITECTOS_CODER_TIMEOUT", DEFAULT_CODER_TIMEOUT),
        )

    def generate_url(self):
        return self.endpoint + "/api/generate"

    def tags_url(self):
        return self.endpoint + "/api/tags"

    def model_for(self, role):
        """Resolve a chat-path model role without inventing new roles."""
        return self.intent_model if role in ("reasoning", "intent", "architecture") else self.model


def chat_config():
    """Read the chat configuration at call time, never frozen at import."""
    return ChatConfig.from_env()
