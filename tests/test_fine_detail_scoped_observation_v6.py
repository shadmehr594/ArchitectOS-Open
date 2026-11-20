"""FINE_DETAIL_ARCHITECTURAL_VISION_V6 — scoped observation interface.

Why this file exists
====================

V6 Task A found that **no existing vision entry point accepts a caller-supplied
question**:

* `FacadeReferenceVisionProvider.analyze()` posts a fixed whole-building facade
  schema (which also asks for a total floor count — unusable on a crop);
* `OllamaVisualObserver.observe()` posts the fixed drawing-oriented
  `OBSERVER_PROMPT`;
* `OllamaVisionProvider.analyze()` runs that same fixed bridge.

A fine-detail experiment is only interpretable if the model is actually ASKED
about the local detail: a null result from an unasked question cannot be
distinguished from a capability limit. So the missing interface is supplied in
the smallest possible way — one optional keyword on the EXISTING observer — and
these tests pin both the new behaviour and the unchanged default path.

The general observation path (drawing-oriented `OBSERVER_PROMPT`, two-stage
bridge, `RawVisualObservationV1`) must be bit-for-bit unaffected. No new
provider, no new preprocessing, no new transport.

CPU only: the session is a fake transport, nothing reaches Ollama.
"""

import base64
import hashlib
import json

from PIL import Image

from config.vision_config import VisionConfig
from core.vision.general_visual_observer_v1 import OBSERVER_PROMPT
from core.vision.vision_provider_ollama_v1 import OllamaVisualObserver


#: Pinned so the general (non-scoped) observation path cannot drift silently.
OBSERVER_PROMPT_SHA256 = hashlib.sha256(OBSERVER_PROMPT.encode("utf-8")).hexdigest()
OBSERVER_PROMPT_PINNED = "2db20f4ca6865fd90bd1ce80bd284472cdcadab223aa0b48769c6cc2f4851c53"


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class _RecordingSession:
    """Minimal stand-in for the requests session used by the observer."""

    def __init__(self, reply="two separate window rows"):
        self.reply = reply
        self.calls = []

    def post(self, url, json=None, timeout=None):  # noqa: A002 - requests API
        self.calls.append((url, {"json": json, "timeout": timeout}))
        return _Response({
            "response": self.reply,
            "done": True,
            "done_reason": "stop",
            "eval_count": 12,
        })


def _image(tmp_path):
    path = tmp_path / "crop.png"
    with Image.new("RGB", (120, 90), "white") as image:
        image.save(path)
    return str(path)


def _observe(tmp_path, prompt=None):
    session = _RecordingSession()
    observer = OllamaVisualObserver(VisionConfig.from_env(), session)
    path = _image(tmp_path)
    raw = observer.observe({"path": path}, prompt) if prompt is not None \
        else observer.observe({"path": path})
    return session, raw, path


# ==========================================================
# GUARD — the general path is untouched
# ==========================================================

def test_default_observer_prompt_text_is_unchanged():
    """The drawing-oriented prompt must not be edited to serve V6."""

    assert OBSERVER_PROMPT_SHA256 == OBSERVER_PROMPT_PINNED

    # The substantive guard: the prompt still asks for the drawing vocabulary
    # and still contains NO storey-count question.
    lowered = " ".join(OBSERVER_PROMPT.lower().split())
    for required in ("openings", "spatial relations", "observations", "uncertainty"):
        assert required in lowered
    for forbidden in ("floor count", "storey count", "how many floors",
                      "how many storeys", "number of floors", "number of storeys"):
        assert forbidden not in lowered


def test_observe_without_a_prompt_still_sends_the_general_prompt(tmp_path):
    session, raw, _ = _observe(tmp_path)

    sent = session.calls[0][1]["json"]["prompt"]

    assert sent == OBSERVER_PROMPT
    assert raw["diagnostics"]["observer_prompt_source"] == "default"
    assert raw["diagnostics"]["observer_prompt_sha256"] == OBSERVER_PROMPT_SHA256


# ==========================================================
# RED — the scoped question
# ==========================================================

def test_observe_accepts_a_caller_scoped_prompt(tmp_path):
    """The missing interface: one optional question on the existing observer."""

    question = "Describe the openings in each bay and any horizontal divisions."

    session, raw, _ = _observe(tmp_path, prompt=question)

    assert session.calls[0][1]["json"]["prompt"] == question
    assert raw["diagnostics"]["observer_prompt_source"] == "caller_scoped"
    assert raw["diagnostics"]["observer_prompt_sha256"] == hashlib.sha256(
        question.encode("utf-8")).hexdigest()


def test_blank_scoped_prompt_falls_back_to_the_general_prompt(tmp_path):
    """A blank question must never become an empty prompt."""

    for blank in ("", "   ", "\n\t "):
        session, raw, _ = _observe(tmp_path, prompt=blank)
        assert session.calls[0][1]["json"]["prompt"] == OBSERVER_PROMPT
        assert raw["diagnostics"]["observer_prompt_source"] == "default"


def test_non_string_scoped_prompt_falls_back_to_the_general_prompt(tmp_path):
    session, raw, _ = _observe(tmp_path, prompt={"not": "a prompt"})

    assert session.calls[0][1]["json"]["prompt"] == OBSERVER_PROMPT
    assert raw["diagnostics"]["observer_prompt_source"] == "default"


# ==========================================================
# GUARD — the observation contract is unchanged
# ==========================================================

def test_scoped_observation_preserves_the_raw_observation_contract(tmp_path):
    """A scoped call returns exactly the same contract shape as a default call."""

    _, default_raw, _ = _observe(tmp_path)
    _, scoped_raw, _ = _observe(tmp_path, prompt="What separates the rows?")

    assert set(default_raw) == set(scoped_raw)
    assert scoped_raw["contract"] == "RawVisualObservationV1"
    assert scoped_raw["generation_status"] == "COMPLETE"
    assert scoped_raw["raw_text"] == "two separate window rows"
    assert scoped_raw["raw_text_sha256"] == hashlib.sha256(
        b"two separate window rows").hexdigest()
    assert scoped_raw["raw_truncated"] is False


def test_scoped_observation_still_sends_the_image_and_no_format(tmp_path):
    session, _, _ = _observe(tmp_path, prompt="Local detail only.")

    request = session.calls[0][1]["json"]

    assert request["images"] and len(request["images"]) == 1
    assert base64.b64decode(request["images"][0])[:8] == b"\x89PNG\r\n\x1a\n"
    assert "format" not in request
    assert request["options"]["temperature"] == 0
