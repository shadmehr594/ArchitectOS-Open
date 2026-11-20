# ==========================================================
# PHASE 2D-4 — MEMORY / CONTEXT REPAIR
# Multi-turn architectural context merge + canonical context assembly.
# ==========================================================

import inspect
import json
import re

from core.prompt_intelligence.persian_architectural_understanding import (
    understand,
)
from core.chat.architectural_conversation_context_v1 import (
    CONTRACT,
    VERSION,
    ArchitecturalConversationContextMergerV1,
    ArchitecturalConversationContextV1,
    architectural_conversation_context,
    merge_context,
)

_MERGER = ArchitecturalConversationContextMergerV1()


def _turn(prev, text, context=None):
    return _MERGER.merge(
        prev, understand(text), raw_text=text, normalized_text=text, context=context
    )


# ==========================================================
# MULTI-TURN DELTA BEHAVIOR
# ==========================================================

def test_A_preserve_and_style_retained_material_updated():
    c = _turn({}, "همین حجم و پنجره‌ها بمونه فقط نما مدرن‌تر شه")
    assert c["active_preserve_constraints"].get("massing") is True
    assert c["active_preserve_constraints"].get("windows") is True
    assert c["active_style"]["target"] == "modern"
    assert c["active_scope"] == "facade"

    c = _turn(c, "خوبه فقط سنگش روشن‌تر شه")
    # carried forward
    assert c["active_preserve_constraints"].get("massing") is True
    assert c["active_preserve_constraints"].get("windows") is True
    assert c["active_style"]["target"] == "modern"
    assert c["active_scope"] == "facade"
    # updated
    assert c["active_materials"]["primary"] == "stone"
    assert c["active_materials"]["tone"] == "light"
    # new turn is a delta
    ops = c["active_architectural_understanding"]["change_operations"]
    assert [op["operation"] for op in ops] == ["increase"]


def test_B_latest_explicit_overrides_prior_preserve():
    c = _turn({}, "پنجره‌ها همین بمونه")
    assert c["active_preserve_constraints"].get("windows") is True

    c = _turn(c, "حالا پنجره‌ها رو عوض کن")
    assert c["active_preserve_constraints"].get("windows") is not True
    ops = c["active_architectural_understanding"]["change_operations"]
    assert any(op["operation"] == "replace" and op["target"] == "windows" for op in ops)
    assert any(
        r["field"] == "windows" and r["resolution"] == "latest_change_overrides_preserve"
        for r in c["provenance"]["resolutions"]
    )


def test_C_context_resolves_unique_target():
    c = _turn({}, "ورودی ضعیفه")
    assert c["active_targets"] == ["entrance"]

    c = _turn(c, "قوی‌ترش کن")
    ops = c["active_architectural_understanding"]["change_operations"]
    assert any(op["target"] == "entrance" and op["operation"] == "increase" for op in ops)
    assert c["provenance"]["resolved_from_context"], "resolution must be recorded"
    assert c["provenance"]["resolved_from_context"][0]["reason"] == "unique_active_target"


def test_D_multiple_targets_remains_ambiguous():
    c = _turn({}, "همین حجم و پنجره‌ها بمونه فقط نما مدرن‌تر شه")
    c = _turn(c, "بهترش کن")
    assert c["pending_ambiguities"], "vague modifier with multiple targets stays ambiguous"
    assert c["active_architectural_understanding"]["intent_type"] == "clarify"


def test_E_new_design_resets_old_constraints():
    c = _turn({}, "نما مدرن‌تر شه")
    assert c["active_scope"] == "facade"
    c = _turn(c, "هوا چطوره؟")
    assert c["turn_has_architectural_signal"] is False  # unrelated chat does not reset
    c = _turn(c, "یه ویلای جدید طراحی کن")
    assert c["provenance"]["reset"] is True
    assert c["active_scope"] == "unknown"
    assert c["active_style"] == {}
    assert c["active_preserve_constraints"] == {}


def test_F_reference_policy_carries_across_revision():
    c = _turn({}, "از این عکس فقط متریالش رو بگیر")
    assert c["active_reference_policy"]["role"] == "material_only"
    c = _turn(c, "یکم روشن‌ترش کن")
    assert c["active_reference_policy"]["role"] == "material_only"


def test_G_new_reference_resets_reference_policy():
    c = _turn({}, "از این عکس فقط متریالش رو بگیر")
    assert c["active_reference_policy"]["referenced"] is True
    c = _turn(c, "یکم روشن‌ترش کن", context={"new_reference": True})
    assert c["active_reference_policy"] == {}


def test_H_current_request_wins_over_persistent_preference():
    c = _turn(
        {},
        "این یکی کلاسیک باشه",
        context={"persistent_user_facts": {"preferences": {"architecture_style": "modern"}}},
    )
    assert c["active_style"]["target"] == "classic"
    assert c["persistent_user_facts"]["preferences"]["architecture_style"] == "modern"


def test_untouched_fields_carry_and_missing_field_is_not_reset():
    c = _turn({}, "قوس‌ها کمتر شه")
    assert c["active_elements"]["arches"]["direction"] == "decrease"
    c = _turn(c, "سنگش روشن‌تر شه")
    assert c["active_elements"]["arches"]["direction"] == "decrease"


# ==========================================================
# CONTRACT / DETERMINISM / SERIALIZATION
# ==========================================================

def test_context_contract_identity_and_fields():
    c = _turn({}, "ورودیش قوی‌تر شه")
    assert isinstance(c, ArchitecturalConversationContextV1)
    assert c["contract"] == CONTRACT
    assert c["version"] == VERSION
    for key in (
        "contract", "version", "session_id", "conversation_id", "recent_turns",
        "active_topic", "active_scope", "active_architectural_intent",
        "active_architectural_understanding", "active_compiled_prompt",
        "active_preserve_constraints", "active_negative_constraints",
        "active_materials", "active_style", "active_reference_policy",
        "pending_ambiguities", "pending_clarifications",
        "active_design_id", "active_candidate_id", "active_render_id",
        "user_profile_summary", "persistent_user_facts",
        "context_sources", "provenance", "context_hash",
    ):
        assert key in c, key


def test_context_hash_is_deterministic_given_same_previous():
    base = _turn({}, "همین حجم و پنجره‌ها بمونه فقط نما مدرن‌تر شه")
    a = _turn(base, "خوبه فقط سنگش روشن‌تر شه")
    b = _turn(base, "خوبه فقط سنگش روشن‌تر شه")
    assert a["context_hash"] == b["context_hash"]
    assert len(a["context_hash"]) == 64


def test_context_json_round_trip():
    c = _turn({}, "خود ساختمون تغییر نکنه فقط نما رو عوض کن")
    restored = json.loads(json.dumps(c, ensure_ascii=False))
    assert restored == c


def test_ids_are_not_invented():
    c = _turn({}, "نما مدرن‌تر شه")
    assert c["active_design_id"] is None
    assert c["active_candidate_id"] is None
    assert c["active_render_id"] is None


def test_ids_preserved_when_provided():
    c = _turn({}, "نما مدرن‌تر شه", context={"design_id": "D1", "render_id": "R1"})
    assert c["active_design_id"] == "D1"
    assert c["active_render_id"] == "R1"


# ==========================================================
# WRITE-BACK / RAW TEXT
# ==========================================================

def test_write_back_stores_structured_state_not_only_raw_text():
    c = _turn({}, "همین حجم و پنجره‌ها بمونه فقط نما مدرن‌تر شه")
    assert isinstance(c["active_preserve_constraints"], dict)
    assert isinstance(c["active_style"], dict)
    assert isinstance(c["active_materials"], dict)
    assert c["recent_turns"] and isinstance(c["recent_turns"][-1], dict)
    assert c["recent_turns"][-1]["scope"] == "facade"


def test_raw_and_normalized_text_preserved():
    raw = "نماي مدرن‌تر شه"  # Arabic yeh
    from core.cognition.persian_normalizer import persian_normalizer
    normalized = persian_normalizer.normalize(raw)["normalized_text"]
    c = _MERGER.merge({}, understand(raw), raw_text=raw, normalized_text=normalized)
    assert c["recent_turns"][-1]["raw_text"] == raw
    assert c["recent_turns"][-1]["normalized_text"] == normalized
    assert c["active_architectural_understanding"]["raw_text"] == raw


def test_recent_turns_are_capped():
    c = {}
    for i in range(30):
        c = _turn(c, "نما مدرن‌تر شه")
    assert len(c["recent_turns"]) <= 20


# ==========================================================
# STORE
# ==========================================================

def test_store_apply_get_reset():
    architectural_conversation_context.reset()
    c = architectural_conversation_context.apply_turn(
        understand("پنجره‌ها همین بمونه"), raw_text="پنجره‌ها همین بمونه",
        normalized_text="پنجره‌ها همین بمونه",
    )
    assert architectural_conversation_context.get()["active_preserve_constraints"]["windows"] is True
    architectural_conversation_context.set_compiled_prompt({"status": "COMPILED"})
    assert architectural_conversation_context.get()["active_compiled_prompt"]["status"] == "COMPILED"
    architectural_conversation_context.reset()
    assert architectural_conversation_context.get() == {}


# ==========================================================
# RUNTIME INTEGRATION (ChatArchitect)
# ==========================================================

def _chat_architect_source():
    with open("core/chat/chat_architect.py", encoding="utf-8") as fh:
        return fh.read()


def test_I_hardcoded_user_name_removed_from_primary_path():
    src = _chat_architect_source()
    assert "مهدی" not in src


def test_J_context_builder_used_on_primary_chat_path():
    src = _chat_architect_source()
    assert "self.context_builder.build(" in src
    assert "architectural_conversation_context.apply_turn(" in src
    assert '"architectural_context"' in src


def test_context_builder_returns_real_memory_not_hardcoded():
    from core.memory.context_builder import ContextBuilder
    ctx = ContextBuilder().build("سلام", task="chat")
    assert "memory" in ctx
    assert "user_profile" in ctx["memory"]


# ==========================================================
# ISOLATION — no render / provider / voice change
# ==========================================================

def test_2d4_module_is_isolated():
    source = inspect.getsource(
        inspect.getmodule(architectural_conversation_context)
    ).lower()
    for forbidden in ("renderruntime", "comfy", "requests", "ollama", "voice", "whisper"):
        assert forbidden not in source, forbidden


def test_2d1_2d2_2d3_still_import_and_work():
    from core.prompt_intelligence.architectural_prompt_compiler_v1 import compile_prompt
    u = understand("یه نمای سنگ روشن میخوام ولی خیلی رومی نشه")
    r = compile_prompt(u)
    assert r["status"] == "COMPILED"
    assert "light natural stone" in r["positive_prompt"]
