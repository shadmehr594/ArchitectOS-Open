# ==========================================================
# PHASE 2D-2 — PERSIAN ARCHITECTURAL LANGUAGE UNDERSTANDING
# Deterministic semantic interpretation tests.
#
# No prompt generation. No translation. No image understanding.
# ==========================================================

import inspect
import json

from core.cognition.persian_normalizer import persian_normalizer
from core.prompt_intelligence.persian_architectural_understanding import (
    CONTRACT,
    VERSION,
    PersianArchitecturalUnderstandingEngine,
    PersianArchitecturalUnderstandingV1,
    persian_architectural_understanding,
    understand,
)
from core.chat.chat_input_adapter import ChatInputAdapter


def _ops(result):
    return [(op["operation"], op["target"]) for op in result["change_operations"]]


# ==========================================================
# REQUIRED EXAMPLES A–L
# ==========================================================

def test_A_low_modern_increase():
    r = understand("یه کم مدرن‌ترش کن")
    assert r["intent_type"] == "change"
    assert r["style"]["target"] == "modern"
    assert r["style"]["direction"] == "increase"
    assert r["intensity"]["level"] == "LOW"
    assert ("increase", "style") in _ops(r)


def test_B_preserve_windows():
    r = understand("پنجره‌ها همون بمونه")
    assert r["preserve_constraints"]["windows"] is True
    assert r["intent_type"] == "preserve"


def test_C_scope_facade_and_preserve_building():
    r = understand("خود ساختمون تغییر نکنه فقط نما رو عوض کن")
    assert r["scope"] == "facade"
    assert r["preserve_constraints"]["massing"] is True
    assert r["preserve_constraints"]["geometry"] is True
    assert ("replace", "facade") in _ops(r)
    # facade is being replaced -> it must NOT be marked preserved
    assert r["preserve_constraints"].get("facade") is not True


def test_D_entrance_emphasis_increase():
    r = understand("ورودیش قوی‌تر شه")
    assert r["entrance"]["emphasis"] == "increase"
    assert ("increase", "entrance") in _ops(r)


def test_E_negative_ornament_constraint():
    r = understand("خیلی شلوغ نشه")
    constraints = [c["constraint"] for c in r["negative_constraints"]]
    assert "avoid_heavy_ornament" in constraints
    assert r["intent_type"] == "constraint"


def test_F_stone_lighter():
    r = understand("سنگش روشن‌تر شه")
    assert r["materials"]["primary"] == "stone"
    assert r["materials"]["tone"] == "light"
    assert r["materials"]["tone_direction"] == "increase"


def test_G_arches_decrease():
    r = understand("قوس‌ها کمتر شه")
    assert r["arches"]["direction"] == "decrease"
    assert ("decrease", "arches") in _ops(r)


def test_H_reference_style_only_no_geometry_copy():
    r = understand("مثل این عکس ولی ساده‌تر")
    assert r["reference_image_policy"]["referenced"] is True
    assert r["reference_image_policy"]["role"] in ("style_only", "inspiration_only")
    assert r["reference_image_policy"]["copy_reference_geometry"] is False
    assert ("decrease", "complexity") in _ops(r)


def test_I_reference_material_only():
    r = understand("از این عکس فقط متریالش رو بگیر")
    assert r["reference_image_policy"]["role"] == "material_only"


def test_J_preserve_massing_and_windows_with_modern_facade():
    r = understand("همین حجم و پنجره‌ها بمونه فقط نما مدرن‌تر شه")
    assert r["preserve_constraints"]["massing"] is True
    assert r["preserve_constraints"]["windows"] is True
    assert r["style"]["target"] == "modern"
    assert r["style"]["direction"] == "increase"
    assert r["scope"] == "facade"


def test_K_light_stone_with_negative_roman():
    r = understand("یه نمای سنگ روشن میخوام ولی خیلی رومی نشه")
    assert r["materials"]["primary"] == "stone"
    assert r["materials"]["tone"] == "light"
    constraints = [c["constraint"] for c in r["negative_constraints"]]
    assert "avoid_excessive_roman_style" in constraints
    # must NOT be forced into a full neoclassical conversion
    assert r["style"]["target"] != "neoclassical"


def test_L_vague_request_is_not_guessed():
    r = understand("بهترش کن")
    assert r["ambiguities"], "expected structured ambiguity"
    assert r["ambiguities"][0]["type"] == "ambiguous_target"
    assert r["intent_type"] == "clarify"
    # no architectural guess produced
    assert r["style"]["target"] is None
    assert r["change_operations"] == []


# ==========================================================
# MIXED PERSIAN / ENGLISH
# ==========================================================

def test_mixed_facade_modern_increase():
    r = understand("نما modern تر باشه")
    assert r["scope"] == "facade"
    assert r["style"]["target"] == "modern"
    assert r["style"]["direction"] == "increase"


def test_mixed_light_stone_dark_frame():
    r = understand("light stone با فریم dark")
    assert r["materials"]["primary"] == "stone"
    assert r["materials"]["tone"] == "light"
    assert r["windows"]["frame_tone"] == "dark"


def test_mixed_facade_simpler():
    r = understand("facade رو ساده‌تر کن")
    assert r["scope"] == "facade"
    assert ("decrease", "complexity") in _ops(r)


# ==========================================================
# CONTRACT / SERIALIZATION / DETERMINISM
# ==========================================================

def test_contract_identity():
    r = understand("یه کم مدرن‌ترش کن")
    assert isinstance(r, PersianArchitecturalUnderstandingV1)
    assert r["contract"] == CONTRACT
    assert r["version"] == VERSION


def test_contract_required_fields():
    r = understand("سنگش روشن‌تر شه")
    for key in (
        "contract", "version", "raw_text", "normalized_text", "language",
        "scope", "intent_type", "targets",
        "style", "materials", "facade", "entrance", "windows", "balconies", "arches",
        "preserve_constraints", "negative_constraints", "change_operations",
        "intensity", "reference_image_policy", "ambiguities",
        "confidence", "deterministic_evidence", "llm_enrichment", "conflicts",
        "provenance",
    ):
        assert key in r, key


def test_json_round_trip():
    r = understand("یه نمای سنگ روشن میخوام ولی خیلی رومی نشه")
    serialized = json.dumps(r, ensure_ascii=False)
    restored = json.loads(serialized)
    assert restored == r


def test_determinism():
    text = "همین حجم بمونه فقط نما مدرن‌تر شه"
    assert understand(text) == understand(text)


def test_uses_normalized_text_from_2d1():
    adapter = ChatInputAdapter()
    payload = adapter.normalize("نماي modern تر باشه")  # Arabic yeh
    r = understand(payload)
    assert r["raw_text"] == "نماي modern تر باشه"
    assert r["normalized_text"] == "نمای modern تر باشه"
    assert r["raw_text"] != r["normalized_text"]
    assert r["style"]["target"] == "modern"


def test_raw_text_preserved_on_raw_string_input():
    raw = "  سنگش  روشن‌تر شه "
    r = understand(raw)
    assert r["raw_text"] == raw


# ==========================================================
# NO PROMPT GENERATION / NO IMAGE UNDERSTANDING
# ==========================================================

def test_no_prompt_generation():
    r = understand("یه نمای سنگ روشن میخوام ولی خیلی رومی نشه")
    assert "prompt" not in r
    assert "english_prompt" not in r
    blob = json.dumps(r, ensure_ascii=False).lower()
    assert "create a " not in blob
    assert "render prompt" not in blob


def test_no_image_understanding_imports():
    source = inspect.getsource(
        inspect.getmodule(persian_architectural_understanding)
    ).lower()
    for forbidden in ("import pil", "from pil", "import cv2", "import numpy", "import torch", "vision"):
        assert forbidden not in source, forbidden


# ==========================================================
# OPTIONAL LLM ENRICHMENT
# ==========================================================

def test_llm_disabled_is_deterministic_only():
    r = understand("سنگش روشن‌تر شه")
    before = json.dumps(r, ensure_ascii=False, sort_keys=True)
    out = persian_architectural_understanding.enrich_with_llm(r, llm_callable=None)
    assert json.dumps(out, ensure_ascii=False, sort_keys=True) == before
    assert out["llm_enrichment"] == {}


def test_llm_fills_empty_field_only():
    r = understand("سنگش روشن‌تر شه")
    assert r["arches"]["intensity"] is None

    def fake(_text):
        return {"arches": {"intensity": "low"}}

    out = persian_architectural_understanding.enrich_with_llm(r, llm_callable=fake)
    assert out["arches"]["intensity"] == "low"
    assert out["llm_enrichment"]["status"] == "applied"


def test_llm_cannot_overwrite_deterministic_field():
    r = understand("یه کم مدرن‌ترش کن")
    assert r["style"]["target"] == "modern"

    def fake(_text):
        return {"style": {"target": "classical"}}

    out = persian_architectural_understanding.enrich_with_llm(r, llm_callable=fake)
    # deterministic authority preserved
    assert out["style"]["target"] == "modern"
    assert out["conflicts"], "conflict must be recorded"
    assert out["conflicts"][0]["resolution"] == "deterministic_authoritative"


def test_llm_provider_failure_does_not_break_parsing():
    r = understand("قوس‌ها کمتر شه")

    def boom(_text):
        raise RuntimeError("provider down")

    out = persian_architectural_understanding.enrich_with_llm(r, llm_callable=boom)
    assert out["arches"]["direction"] == "decrease"  # deterministic intact
    assert out["llm_enrichment"]["status"] == "failed"


def test_llm_schema_validator_rejects_bad_output():
    r = understand("قوس‌ها کمتر شه")

    def fake(_text):
        return {"arches": {"intensity": "low"}}

    out = persian_architectural_understanding.enrich_with_llm(
        r, llm_callable=fake, schema_validator=lambda data: False
    )
    assert out["llm_enrichment"]["status"] == "rejected_schema"


# ==========================================================
# ENGINE IDENTITY / STABILITY
# ==========================================================

def test_engine_is_constructible_and_stable():
    a = PersianArchitecturalUnderstandingEngine()
    b = PersianArchitecturalUnderstandingEngine()
    assert a.interpret("قوس‌ها کمتر شه") == b.interpret("قوس‌ها کمتر شه")
