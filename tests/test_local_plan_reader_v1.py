from collections import Counter
from pathlib import Path

import pytest

from core.vision.local_plan_reader_v1 import read_local_plan
from core.vision.image_understanding_v1 import build_understanding
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)
from core.vision.vision_report_v1 import (
    render_vision_evidence_report,
    render_vision_report,
)


ROOT = Path(__file__).resolve().parents[1]
FIXED_PLAN = ROOT / "uploads" / "chat_media" / "4bd10b4bebe6_7.png"


@pytest.fixture(scope="module")
def local_reading():
    if not FIXED_PLAN.is_file():
        pytest.skip("fixed Vision acceptance image is not installed")
    result = read_local_plan(FIXED_PLAN)
    assert result["status"] == "grounded", result.get("reason")
    return result


def test_fixed_persian_plan_labels_and_windows(local_reading):
    counts = Counter(item["text"] for item in local_reading["labels"])

    assert counts == Counter({
        "اتاق خواب": 2,
        "مطبخ": 1,
        "آشپزخانه": 1,
        "حمام": 1,
        "سرویس": 1,
        "پذیرایی": 1,
        "تراس": 1,
        "ایوان": 1,
    })
    assert not ({"سردر", "دینینگ", "دالان", "آبدارخانه"} & set(counts))
    assert all(len(item.get("bbox_pixels") or []) == 4 for item in local_reading["labels"])
    assert all(item.get("confidence") in {"LOW", "MEDIUM", "HIGH"} for item in local_reading["labels"])
    assert local_reading["furniture_observed"] is False

    windows = [
        item for item in local_reading["openings"]
        if item.get("kind") == "window" and item.get("status") == "visible"
    ]
    assert len(windows) == 4
    assert all(len(item.get("bbox_pixels") or []) == 4 for item in windows)


def test_grounded_local_evidence_overrides_adversarial_provider(local_reading):
    provider_raw = {
        "image_type": "floor_plan_or_sketch",
        "confidence": "HIGH",
        "observed": ["floor plan", "bed and sofa visible"],
        "architectural_elements": [
            "walls", "doors", "windows", "bed", "sofa", "table", "entrance",
        ],
        "text_labels_if_visible": [
            "اتاق خواب", "آشپزخانه", "اتاق نشیمن", "حمام", "سردر", "دینینگ",
        ],
        "furniture_elements": ["bed", "sofa", "table"],
        "spatial_clues": ["دالان circulation", "آبدارخانه adjacent to dining"],
        "local_plan_reading": local_reading,
    }
    understanding = build_understanding(
        provider_raw,
        provider="adversarial-provider",
        model="unstable-provider",
        image_id="fixed-plan",
    )
    interpretation = interpret_architectural_vision(understanding)
    plan = interpretation["plan_reading"]
    counts = Counter(item["text"] for item in plan["read_labels"])
    report = render_vision_report(interpretation, "fa")
    evidence = render_vision_evidence_report(interpretation, "fa")

    assert counts["اتاق خواب"] == 2
    assert not ({"سردر", "دینینگ", "دالان", "آبدارخانه"} & set(counts))
    assert plan["provider_labels_overridden"] is True
    assert plan["furniture"] == []
    assert plan["furniture_observed"] is False
    assert plan["unsupported_claims"] == []
    assert plan["unsupported_relations"] == []
    assert any(
        item.get("kind") == "window"
        and item.get("status") == "visible"
        and item.get("instance_count") == 4
        for item in plan["openings"]
    )
    assert "عنصر خواب (تخت) دیده می‌شود" not in evidence
    assert "عنصر نشستن دیده می‌شود" not in evidence
    assert "circulation passage visible" not in interpretation["observed_elements"]
    assert all(word not in report for word in ("سردر", "دینینگ", "دالان", "آبدارخانه"))
    assert "هیچ مبلمانی با شاهد قطعی مشاهده نشد" in evidence
    assert "OCR محلی" in evidence
    assert "تعداد: 4" in evidence

    # ==================================================
    # ARCHITECTURAL_VISION_REPORT_UX_V1 — the user-facing answer is the
    # short architectural explanation, and it still carries every fact.
    # ==================================================
    assert len(report) < len(evidence) / 3
    # VISION_RETENTION_FIX_V2 — NO local OCR token may name a grounded space
    # unless it is INDEPENDENTLY verified, and this fixture has no independent
    # corroborator. The user-facing plan answer therefore carries the grounded
    # PLAN STRUCTURE (it is a plan; its perimeter windows and door openings) and
    # none of the OCR space names — neither the lexicon SUBSTITUTIONS
    # (`اتاق خواب` ← `اتاق خوایل`, `مطبخ` ← `خیطم#`, `حمام` ← `ما`,
    # `سرویس` ← `۱ سرویس |`, `ایوان` ← `ناوپآ`) nor the merely STABLE readings
    # (`آشپزخانه`, `پذیرایی`, `تراس`), whose multi-pass agreement is a stability
    # signal and not an independent source.
    assert "پلان" in report
    assert all(
        word not in report
        for word in ("آشپزخانه", "پذیرایی", "تراس",
                     "مطبخ", "حمام", "سرویس", "ایوان", "اتاق خواب")
    )
    assert "چند پنجره" in report
    assert "#1" not in report and "#2" not in report
    assert all(
        word not in report
        for word in ("OCR", "اطمینان", "شاهد", "احتمالی", "تأییدنشده")
    )
