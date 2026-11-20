# ==========================================================
# PHASE 2D-1 — PERSIAN / LANGUAGE NORMALIZATION FOUNDATION
# Deterministic normalization + language detection + boundary contract.
#
# These tests assert ONLY deterministic, non-semantic behaviour:
# no LLM, no provider, no translation, no colloquial rewriting.
# ==========================================================

import inspect

from core.cognition.persian_normalizer import (
    NormalizedRequest,
    PersianNormalizer,
    detect_language,
    has_persian_chars,
    persian_normalizer,
)
from core.chat.chat_input_adapter import ChatInputAdapter
from core.intent_router import intent_router
from core.cognition.intent_engine import intent_engine


# ==========================================================
# REQUIRED REGRESSION CASES
# ==========================================================

def test_case_1_arabic_yeh_to_persian_yeh():
    r = persian_normalizer.normalize("نماي مدرن")
    assert r["normalized_text"] == "نمای مدرن"
    assert r["raw_text"] == "نماي مدرن"
    assert r["normalization_applied"] is True


def test_case_2_arabic_kaf_to_persian_kaf():
    r = persian_normalizer.normalize("سنگ كرم")
    assert r["normalized_text"] == "سنگ کرم"
    assert r["raw_text"] == "سنگ كرم"


def test_case_3_persian_digit_to_ascii():
    r = persian_normalizer.normalize("طبقه ۲")
    assert r["normalized_text"] == "طبقه 2"
    assert r["raw_text"] == "طبقه ۲"


def test_case_4_arabic_indic_digit_to_ascii():
    r = persian_normalizer.normalize("طبقه ٢")
    assert r["normalized_text"] == "طبقه 2"


def test_case_5_colloquial_is_not_rewritten():
    """Letter normalization only — no colloquial / spelling rewriting."""
    r = persian_normalizer.normalize("يه ويلاي مدرن ميخوام")
    assert r["normalized_text"] == "یه ویلای مدرن میخوام"
    # colloquial "يه" must NOT become "یک"
    assert "یک" not in r["normalized_text"]
    # colloquial "ميخوام" must NOT become "میخواهم"
    assert "میخواهم" not in r["normalized_text"]


def test_case_6_mixed_language_detected():
    r = persian_normalizer.normalize("Modern نما با 2 طبقه")
    assert r["detected_language"] == "mixed"


def test_case_7_english_only_unchanged():
    r = persian_normalizer.normalize("modern villa with 2 floors")
    assert r["normalized_text"] == "modern villa with 2 floors"
    assert r["detected_language"] == "en"
    assert r["normalization_applied"] is False


def test_case_8_whitespace_noise_collapses():
    r = persian_normalizer.normalize("  a\t\t b\n\n c  ")
    assert r["normalized_text"] == "a b c"


def test_case_9_raw_text_is_content_preserved():
    raw = "  نماي\tمدرن \u200c با ۱۲ طبقه  "
    r = persian_normalizer.normalize(raw)
    assert r["raw_text"] == raw


# ==========================================================
# DETERMINISM / PURITY
# ==========================================================

def test_deterministic_same_input_same_output():
    raw = "نماي مدرن ۲ طبقه"
    a = persian_normalizer.normalize(raw)
    b = persian_normalizer.normalize(raw)
    assert a == b
    assert a["normalized_text"] == b["normalized_text"]


def test_normalizer_is_pure_no_network_no_llm():
    """The canonical normalizer must not depend on any LLM / provider."""
    source = inspect.getsource(
        inspect.getmodule(persian_normalizer)
    ).lower()
    for forbidden in (
        "requests",
        "ollama",
        "http://",
        "https://",
        "openai",
        "anthropic",
        "gemini",
        "llm_gateway",
    ):
        assert forbidden not in source, forbidden


def test_normalize_never_calls_llm_on_empty_input():
    r = persian_normalizer.normalize("")
    assert r["normalized_text"] == ""
    assert r["detected_language"] == "unknown"


# ==========================================================
# ZWNJ / INVISIBLE CONTROL POLICY
# ==========================================================

def test_zwnj_run_collapses_to_single():
    r = persian_normalizer.normalize("می\u200c\u200cخواهم")
    assert r["normalized_text"] == "می\u200cخواهم"


def test_zwnj_adjacent_to_whitespace_removed():
    r = persian_normalizer.normalize("می\u200c خواستن")
    assert r["normalized_text"] == "می خواستن"


def test_space_is_never_converted_to_zwnj():
    r = persian_normalizer.normalize("می خواهم")
    assert r["normalized_text"] == "می خواهم"
    assert "\u200c" not in r["normalized_text"]


def test_zwsp_maps_to_canonical_zwnj():
    r = persian_normalizer.normalize("می\u200bخواهم")
    assert r["normalized_text"] == "می\u200cخواهم"


def test_bom_removed():
    r = persian_normalizer.normalize("\ufeffسلام")
    assert r["normalized_text"] == "سلام"


def test_invisible_bidi_controls_removed():
    r = persian_normalizer.normalize("\u200fسلام\u200e")
    assert r["normalized_text"] == "سلام"


# ==========================================================
# LANGUAGE DETECTION CONTRACT
# ==========================================================

def test_language_detector_values():
    assert detect_language("سلام") == "fa"
    assert detect_language("hello world") == "en"
    assert detect_language("سلام world") == "mixed"
    assert detect_language("12345") == "unknown"
    assert detect_language("") == "unknown"
    assert detect_language(None) == "unknown"


def test_had_persian_chars_flag():
    assert has_persian_chars("سلام") is True
    assert has_persian_chars("hello") is False
    assert persian_normalizer.normalize("hello")["had_persian_chars"] is False
    assert persian_normalizer.normalize("سلام")["had_persian_chars"] is True


# ==========================================================
# REQUEST CONTRACT
# ==========================================================

def test_normalized_request_contract_fields():
    r = persian_normalizer.normalize("نماي مدرن")
    assert isinstance(r, dict)
    assert isinstance(r, NormalizedRequest)
    assert r["contract"] == NormalizedRequest.CONTRACT
    assert r["version"] == NormalizedRequest.VERSION
    for key in (
        "raw_text",
        "normalized_text",
        "detected_language",
        "had_persian_chars",
        "normalization_applied",
        "normalization_steps",
        "normalization_metadata",
    ):
        assert key in r, key
    assert r["text"] == r["normalized_text"]


def test_chat_input_adapter_backward_compatible_shape():
    adapter = ChatInputAdapter()
    payload = adapter.normalize("نماي مدرن", None)
    # legacy keys still present and typed correctly
    assert isinstance(payload["text"], str)
    assert "image" in payload
    assert payload["image"] is None
    # new keys additive
    assert payload["raw_text"] == "نماي مدرن"
    assert payload["normalized_text"] == "نمای مدرن"


def test_chat_input_adapter_dict_input_and_image():
    adapter = ChatInputAdapter()
    payload = adapter.normalize(
        {"text": "سنگ كرم", "image": {"path": "x.png"}}
    )
    assert payload["normalized_text"] == "سنگ کرم"
    assert payload["image"] == {"path": "x.png"}


def test_chat_input_adapter_context_image_fallback():
    adapter = ChatInputAdapter()
    payload = adapter.normalize("hello", {"path": "ctx.png"})
    assert payload["image"] == {"path": "ctx.png"}


# ==========================================================
# INTENT REGRESSION (normalized form must preserve or improve)
# ==========================================================

def test_intent_improves_with_letter_normalization():
    raw = "ويه ويلاي مدرن ميخوام"
    normalized = persian_normalizer.normalize(raw)["normalized_text"]
    # raw (Arabic yeh) does NOT match the Persian villa rule
    assert intent_router.route(raw)["intent"] == "chat"
    # normalized form now matches -> design
    assert intent_router.route(normalized)["intent"] == "design"


def test_intent_engine_villa_rule_on_normalized_text():
    normalized = persian_normalizer.normalize(
        "یه ویلای مدرن میخوام"
    )["normalized_text"]
    assert intent_engine.analyze(normalized).intent == "villa_design"


def test_intent_preserved_for_existing_persian_examples():
    for text in (
        "یه ویلای مدرن میخوام",
        "نمای سنگی",
        "آشپزخانه رو بزرگ کن",
        "یه ساختمان دو طبقه",
    ):
        normalized = persian_normalizer.normalize(text)["normalized_text"]
        assert intent_router.route(normalized) == intent_router.route(text)


def test_english_request_still_routes_to_chat():
    normalized = persian_normalizer.normalize(
        "hello how are you"
    )["normalized_text"]
    assert intent_router.route(normalized)["intent"] == "chat"


def test_normalizer_class_is_constructible_and_stable():
    a = PersianNormalizer()
    b = PersianNormalizer()
    assert a.normalize("نماي ۲") == b.normalize("نماي ۲")
