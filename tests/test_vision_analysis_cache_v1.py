"""LOCAL_PLAN_READING_V1 — vision analysis cache reuse contract.

A stored analysis may be served to the UI ONLY while it is genuinely the
CURRENT pipeline's result for the CURRENT environment:

  * an analysis produced before the local plan reader existed (no
    `evidence_pipeline` stamp) is stale;
  * an analysis produced while the compiled OCR backend was unavailable
    (no / different `local_ocr_environment` fingerprint) is stale;
  * an analysis produced by the current pipeline under the current
    environment is still reused — without re-calling the provider.

These tests exercise the REAL local reader; only the multimodal provider is
stubbed so the suite stays offline.  No OCR or vision algorithm is changed
by this contract.
"""

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXED_PLAN = ROOT / "uploads" / "chat_media" / "4bd10b4bebe6_7.png"
SESSION = "project_cache_contract_v1"
IMAGE_ID = "img_cache_contract01"

DEGRADED_LABELS = ["اتاق خواب", "آشپزخانه", "اتاق نشیمن", "حمام", "سردر", "دینینگ"]

EXPECTED_LOCAL_LABELS = {
    "اتاق خواب": 2,
    "مطبخ": 1,
    "آشپزخانه": 1,
    "حمام": 1,
    "سرویس": 1,
    "پذیرایی": 1,
    "تراس": 1,
    "ایوان": 1,
}


class _StubProvider:
    """Offline stand-in for the Ollama vision provider."""

    name = "stub"
    model = "stub-model"
    supports_grounding = False

    def __init__(self):
        self.calls = 0

    def is_available(self):
        return True

    def analyze(self, payload):
        self.calls += 1
        return {
            "image_type": "floor_plan_or_sketch",
            "observed": ["stub provider observation"],
            "inferred": [],
            "unresolved": [],
            "confidence": "HIGH",
            "architectural_elements": [],
            # the provider's own false labels must never become the answer
            "text_labels_if_visible": list(DEGRADED_LABELS),
        }


def _record(cached_analysis):
    return {
        "contract": "ImageRegistryV1",
        "version": "1.0",
        "image_id": IMAGE_ID,
        "session_id": SESSION,
        "ordinal": 1,
        "source_type": "uploaded",
        "path": str(FIXED_PLAN),
        "label": "7.png",
        "analysis_status": "ANALYZED_WITH_UNCERTAINTY",
        "analysis": cached_analysis,
        "active": True,
    }


@pytest.fixture
def vision(monkeypatch):
    from core.vision import image_session_v1 as session
    from core.vision.image_registry_v1 import image_registry

    if not FIXED_PLAN.is_file():
        pytest.skip("fixed Vision acceptance image is not installed")

    stub = _StubProvider()
    monkeypatch.setattr(session, "provider", lambda: stub)

    yield session, image_registry, stub

    image_registry.reset(SESSION)


def test_cache_reuse_reason_contract():
    from core.vision.image_session_v1 import _cache_reuse_reason, _provider_cache_identity, provider
    from core.vision.image_understanding_v1 import EVIDENCE_PIPELINE_VERSION
    from core.vision.local_plan_reader_v1 import local_ocr_environment

    done = {"analysis_status": "ANALYZED_WITH_UNCERTAINTY"}
    current = {
        "evidence_pipeline": EVIDENCE_PIPELINE_VERSION,
        "local_ocr_environment": local_ocr_environment(),
        "vision_cache_identity": _provider_cache_identity(provider()),
    }

    # pre-local-reader cache: no pipeline stamp at all
    assert _cache_reuse_reason(done, {}) == "stale_evidence_pipeline"
    assert _cache_reuse_reason(done, {"local_plan_reading": {}}) == "stale_evidence_pipeline"

    # current pipeline but recorded before the OCR environment was known
    assert _cache_reuse_reason(
        done, {"evidence_pipeline": EVIDENCE_PIPELINE_VERSION}
    ) == "stale_local_ocr_environment"

    # current pipeline recorded under a different (degraded) environment
    assert _cache_reuse_reason(
        done,
        dict(current, local_ocr_environment="tesserocr=off;tessdata=off"),
    ) == "stale_local_ocr_environment"

    # a genuine current result is reusable
    assert _cache_reuse_reason(done, dict(current)) == "current"

    # incomplete states are never reusable
    for status in (None, "pending", "failed"):
        assert _cache_reuse_reason(
            {"analysis_status": status}, dict(current)
        ) == "no_completed_analysis"

    assert _cache_reuse_reason(done, "not-a-dict") == "not_an_understanding"


def test_stale_pre_local_reader_cache_is_recomputed(vision):
    session, registry, stub = vision
    registry.hydrate(SESSION, [_record({
        "contract": "ImageUnderstandingV1",
        "version": "1.0",
        "image_id": IMAGE_ID,
        "analysis_status": "ANALYZED_WITH_UNCERTAINTY",
        "text_labels_if_visible": list(DEGRADED_LABELS),
    })])

    result = session.analyze_record(SESSION, IMAGE_ID)

    assert stub.calls == 1, "a pre-local-reader cache must be recomputed"

    from core.vision.image_understanding_v1 import EVIDENCE_PIPELINE_VERSION

    assert result.get("evidence_pipeline") == EVIDENCE_PIPELINE_VERSION
    assert result.get("local_ocr_environment")

    reading = result.get("local_plan_reading") or {}
    assert reading.get("status") == "grounded"
    assert reading.get("reason") is None

    counts = {}
    for item in reading.get("labels") or []:
        counts[item["text"]] = counts.get(item["text"], 0) + 1

    assert counts == EXPECTED_LOCAL_LABELS
    assert not ({"سردر", "دینینگ", "دالان", "آبدارخانه"} & set(counts))
    # The shared `openings` collection carries window AND door instances
    # (PR #2). The regression intent is the four historical grounded
    # WINDOWS; the three independently grounded DOORS are asserted too.
    openings = reading.get("openings") or []
    windows = [item for item in openings if item.get("type") == "window"]
    assert len(windows) == 4
    doors = [item for item in openings if item.get("type") == "door"]
    assert len(doors) == 3
    assert reading.get("furniture_observed") is False


def test_degraded_ocr_environment_cache_is_recomputed(vision):
    session, registry, stub = vision
    from core.vision.image_understanding_v1 import EVIDENCE_PIPELINE_VERSION

    # exactly the shape the live manual-test project held: the CURRENT
    # pipeline stamp, but the local reader could not run.
    registry.hydrate(SESSION, [_record({
        "contract": "ImageUnderstandingV1",
        "version": "1.0",
        "image_id": IMAGE_ID,
        "analysis_status": "ANALYZED_WITH_UNCERTAINTY",
        "evidence_pipeline": EVIDENCE_PIPELINE_VERSION,
        "local_plan_reading": {
            "contract": "LocalPlanReadingV1",
            "version": "1.0",
            "status": "unavailable",
            "reason": "RuntimeError:tesserocr_unavailable",
        },
        "text_labels_if_visible": list(DEGRADED_LABELS),
    })])

    result = session.analyze_record(SESSION, IMAGE_ID)

    assert stub.calls == 1, (
        "an analysis produced while the OCR backend was unavailable must be "
        "recomputed once the environment is repaired"
    )

    reading = result.get("local_plan_reading") or {}
    assert reading.get("status") == "grounded"
    assert len(reading.get("labels") or []) == 9
    # The shared `openings` collection carries window AND door instances
    # (PR #2). The regression intent is the four historical grounded
    # WINDOWS; the three independently grounded DOORS are asserted too.
    openings = reading.get("openings") or []
    windows = [item for item in openings if item.get("type") == "window"]
    assert len(windows) == 4
    doors = [item for item in openings if item.get("type") == "door"]
    assert len(doors) == 3


def test_current_cache_is_still_reused(vision):
    session, registry, stub = vision
    from core.vision.image_understanding_v1 import EVIDENCE_PIPELINE_VERSION
    from core.vision.local_plan_reader_v1 import local_ocr_environment

    cached = {
        "contract": "ImageUnderstandingV1",
        "version": "1.0",
        "image_id": IMAGE_ID,
        "analysis_status": "ANALYZED_WITH_UNCERTAINTY",
        "evidence_pipeline": EVIDENCE_PIPELINE_VERSION,
        "local_ocr_environment": local_ocr_environment(),
        "vision_cache_identity": session._provider_cache_identity(stub),
        "local_plan_reading": {
            "contract": "LocalPlanReadingV1",
            "version": "1.0",
            "status": "grounded",
            "labels": [],
            "openings": [],
        },
        "text_labels_if_visible": ["اتاق خواب"],
    }

    registry.hydrate(SESSION, [_record(cached)])

    result = session.analyze_record(SESSION, IMAGE_ID)

    assert stub.calls == 0, (
        "a current cache must be reused without re-calling the provider"
    )
    assert result.get("local_ocr_environment") == local_ocr_environment()
    assert result.get("text_labels_if_visible") == ["اتاق خواب"]
