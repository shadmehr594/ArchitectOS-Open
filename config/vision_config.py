"""Runtime-only configuration for the visual observer and text normalizer."""

from dataclasses import dataclass
import os


def _thinking(value):
    value = value.lower()
    if value in ("true", "false"):
        return value == "true"
    if value in ("low", "medium", "high"):
        return value
    raise ValueError("ARCHITECTOS_VISION_THINK must be true/false/low/medium/high")


def _positive(name, default):
    value = int(os.environ.get(name, default))
    if value <= 0:
        raise ValueError(name + " must be positive")
    return value


@dataclass(frozen=True)
class VisionConfig:
    model: str
    normalizer_model: str
    endpoint: str
    thinking: object
    observer_tokens: int
    normalizer_tokens: int
    normalizer_ctx: int
    normalizer_input_chars: int
    timeout: int
    normalizer_timeout: int = 420
    observer_ctx: int = 32768
    observer_max_long_edge: int = 4096
    observer_max_pixels: int = 12000000
    # VISION_END_TO_END_RETENTION_FIX_V1 — the observer's own wait budget.
    # Measured maximum observer completion on the largest live sheet (17.4 MP,
    # 4096-pixel bounded input, 32768 ctx) is 395.203 s, so the default carries
    # ~1.5x headroom over the measured maximum. The legacy
    # ARCHITECTOS_VISION_TIMEOUT still drives it when set, so an existing
    # deployment override keeps its exact meaning.
    observer_timeout: int = 600

    @classmethod
    def from_env(cls, model=None):
        model = model or os.environ.get("ARCHITECTOS_VISION_MODEL", "qwen3.8:27b")
        # Backend defaults, not an architectural interface tied to one model.
        default_thinking = "low" if model.startswith("qwen") else "false"
        return cls(
            model=model,
            normalizer_model=os.environ.get("ARCHITECTOS_VISION_NORMALIZER_MODEL", model),
            endpoint=os.environ.get("ARCHITECTOS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
            thinking=_thinking(os.environ.get("ARCHITECTOS_VISION_THINK", default_thinking)),
            # VISION_END_TO_END_RETENTION_FIX_V1 — 2048 truncated the largest
            # live sheet (done_reason=length, eval_count=2048). Measured live,
            # 4096 lets the same image finish naturally (done_reason=stop,
            # eval_count=2656).
            observer_tokens=_positive("ARCHITECTOS_VISION_OBSERVER_TOKENS", 4096),
            observer_ctx=_positive("ARCHITECTOS_VISION_OBSERVER_CTX", 32768),
            observer_max_long_edge=_positive("ARCHITECTOS_VISION_OBSERVER_MAX_LONG_EDGE", 4096),
            observer_max_pixels=_positive("ARCHITECTOS_VISION_OBSERVER_MAX_PIXELS", 12000000),
            normalizer_tokens=_positive("ARCHITECTOS_VISION_NORMALIZER_TOKENS", 8192),
            normalizer_ctx=_positive("ARCHITECTOS_VISION_NORMALIZER_CTX", 32768),
            normalizer_input_chars=_positive("ARCHITECTOS_VISION_NORMALIZER_INPUT_CHARS", 24000),
            timeout=_positive("ARCHITECTOS_VISION_TIMEOUT", 300),
            normalizer_timeout=_positive("ARCHITECTOS_VISION_NORMALIZER_TIMEOUT", 420),
            observer_timeout=_positive(
                "ARCHITECTOS_VISION_OBSERVER_TIMEOUT",
                _positive("ARCHITECTOS_VISION_TIMEOUT", 600),
            ),
        )
