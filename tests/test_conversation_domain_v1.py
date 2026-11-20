# -*- coding: utf-8 -*-
"""CONVERSATION_DOMAIN_V1 — chat/voice domain isolation tests.

Covers the reported contamination: a voice/audio or general turn must never
receive the session's architectural context, while an architectural turn
keeps it in full. The context is SUSPENDED, never deleted.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.chat.conversation_domain_v1 import (
    CONTRACT,
    DOMAINS,
    classify_domain,
    project_context_for_domain,
    resolve_turn_domain,
    domain_guidance,
    conversation_domain,
)


# a realistic session architectural context (as the store produces).
#
# NOTE: `turn_has_architectural_signal` describes the CURRENT turn (the
# merger sets it from this turn's own understanding). It is False for a
# voice/audio or general turn, and True only for an architectural turn.
def architectural_session(*, signal=False):
    return {
        "contract": "ArchitecturalConversationContextV1",
        "version": "1.0",
        "session_id": "sess-1",
        "conversation_id": "conv-1",
        "active_topic": "architecture",
        "active_scope": "whole_building",
        "active_architectural_intent": {"style": "modern"},
        "active_architectural_understanding": {"facade": {}, "windows": {}},
        "active_compiled_prompt": {"positive_prompt": "brick facade, two floors"},
        "active_preserve_constraints": {"facade": True},
        "active_negative_constraints": ["no glass"],
        "active_materials": {"primary": "brick"},
        "active_style": {"target": "modern"},
        "active_reference_policy": {},
        "active_targets": ["facade", "floors"],
        "active_elements": {"facade": {}, "windows": {}, "balconies": {}},
        "pending_ambiguities": [],
        "pending_clarifications": [],
        "active_design_id": "design-9",
        "active_candidate_id": None,
        "active_render_id": None,
        "active_reference_id": None,
        "recent_turns": [
            {"turn": 1, "raw_text": "خانه مسکونی دو طبقه با نمای آجری",
             "scope": "whole_building"},
            {"turn": 2, "raw_text": "صدا میاد؟", "scope": None},
        ],
        "turn_has_architectural_signal": bool(signal),
        "context_hash": "abc123",
    }


# ======================================================================
# 1. DOMAIN CLASSIFICATION
# ======================================================================

class TestClassification:

    def test_voice_audio_questions(self):
        for text in ("صدا میاد؟", "صدای من را می‌شنوی؟", "مشکل میکروفن چیست؟"):
            result = classify_domain(text)
            assert result["domain"] == "voice_audio", text
            assert result["evidence"], text

    def test_a_greeting_is_general(self):
        assert classify_domain("سلام")["domain"] == "general"

    def test_an_architectural_turn_is_architecture(self):
        assert classify_domain("خانه مسکونی دو طبقه با نمای آجری")["domain"] == "architecture"

    def test_a_parsed_understanding_forces_architecture(self):
        result = classify_domain("هرچیزی", understanding={"facade": {}})
        assert result["domain"] == "architecture"
        assert result["confidence"] == "HIGH"

    def test_the_context_signal_forces_architecture(self):
        result = classify_domain("هرچیزی", architectural_signal=True)
        assert result["domain"] == "architecture"

    def test_a_voice_marker_beats_a_weak_architectural_marker(self):
        """`صدای اتاق` is about audio, not about the room."""
        assert classify_domain("صدای اتاق چطور است؟")["domain"] == "voice_audio"

    def test_domain_is_always_from_the_vocabulary(self):
        for text in ("سلام", "صدا میاد؟", "خانه", "blah"):
            assert classify_domain(text)["domain"] in DOMAINS

    def test_every_result_carries_evidence_and_source(self):
        for text in ("سلام", "صدا میاد؟", "خانه"):
            result = classify_domain(text)
            assert "evidence" in result
            assert result["reasoning_source"]
            assert result["confidence"] in ("LOW", "MEDIUM", "HIGH")

    def test_guidance_exists_for_every_domain(self):
        for domain in DOMAINS:
            assert domain_guidance(domain)


# ======================================================================
# 2. THE PROJECTION — SUSPEND, NEVER DELETE
# ======================================================================

class TestProjection:

    def test_an_architectural_turn_keeps_the_context(self):
        context = architectural_session()
        projected = project_context_for_domain(context, "architecture")
        assert projected is context          # the very same object
        assert projected["active_materials"] == {"primary": "brick"}

    def test_a_voice_turn_suspends_the_context(self):
        projected = project_context_for_domain(architectural_session(), "voice_audio")
        assert projected["suspended"] is True
        assert projected["domain"] == "voice_audio"

    def test_a_general_turn_suspends_the_context(self):
        assert project_context_for_domain(architectural_session(), "general")["suspended"] is True

    def test_no_active_architectural_understanding(self):
        projected = project_context_for_domain(architectural_session(), "voice_audio")
        assert projected["active_architectural_understanding"] == {}

    def test_no_active_materials(self):
        projected = project_context_for_domain(architectural_session(), "voice_audio")
        assert projected["active_materials"] == {}

    def test_no_active_elements(self):
        projected = project_context_for_domain(architectural_session(), "voice_audio")
        assert projected["active_elements"] == {}

    def test_no_architectural_recent_turns(self):
        projected = project_context_for_domain(architectural_session(), "voice_audio")
        texts = [t.get("raw_text") for t in projected["recent_turns"]]
        assert "خانه مسکونی دو طبقه با نمای آجری" not in texts
        assert "صدا میاد؟" in texts          # a non-architectural turn is kept

    def test_no_architectural_payload_at_all(self):
        projected = project_context_for_domain(architectural_session(), "general")
        blob = str(projected)
        for leak in ("brick", "whole_building", "facade", "windows", "balconies",
                     "modern", "no glass", "design-9"):
            assert leak not in blob, "leaked: " + leak

    def test_the_signal_is_forced_false_when_suspended(self):
        projected = project_context_for_domain(architectural_session(), "voice_audio")
        assert projected["turn_has_architectural_signal"] is False

    def test_the_original_context_is_never_mutated(self):
        context = architectural_session()
        before = repr(context)
        project_context_for_domain(context, "voice_audio")
        assert repr(context) == before

    def test_the_session_identity_is_kept(self):
        projected = project_context_for_domain(architectural_session(), "voice_audio")
        assert projected["session_id"] == "sess-1"
        assert projected["conversation_id"] == "conv-1"

    def test_the_context_returns_in_full_on_the_next_architectural_turn(self):
        context = architectural_session()
        suspended = project_context_for_domain(context, "voice_audio")
        assert suspended["active_materials"] == {}

        restored = project_context_for_domain(context, "architecture")
        assert restored["active_materials"] == {"primary": "brick"}
        assert restored["active_elements"]


# ======================================================================
# 3. END-TO-END RESOLUTION
# ======================================================================

class TestResolve:

    def test_a_voice_turn_resolves_to_voice_audio_with_no_architecture(self):
        result = resolve_turn_domain("صدا میاد؟", architectural_session())

        assert result["domain"]["domain"] == "voice_audio"
        assert result["domain_block"]["architectural_context_injected"] is False
        assert result["domain_block"]["architectural_context_suspended"] is True
        assert "architecture" in result["domain_block"]["guidance"].lower()

        blob = str(result["architectural_context"])
        for leak in ("brick", "facade", "windows", "balconies"):
            assert leak not in blob

    def test_a_general_turn_resolves_to_general_with_no_architecture(self):
        result = resolve_turn_domain("سلام", architectural_session())

        assert result["domain"]["domain"] == "general"
        assert result["domain_block"]["architectural_context_injected"] is False
        assert "brick" not in str(result["architectural_context"])

    def test_an_architectural_turn_keeps_its_context(self):
        result = resolve_turn_domain(
            "نمای آجری را مدرن کن", architectural_session()
        )

        assert result["domain"]["domain"] == "architecture"
        assert result["domain_block"]["architectural_context_injected"] is True
        assert result["architectural_context"]["active_materials"] == {"primary": "brick"}

    def test_a_voice_turn_after_an_architectural_turn_does_not_leak(self):
        """The exact reported scenario."""

        context = architectural_session()          # after an architectural turn

        voice = resolve_turn_domain("صدا میاد؟", context)
        assert voice["domain"]["domain"] == "voice_audio"
        assert voice["domain_block"]["architectural_context_injected"] is False

        # ... and the architectural context is still intact for later
        arch = resolve_turn_domain("نما را بررسی کن", context)
        assert arch["architectural_context"]["active_materials"] == {"primary": "brick"}

    def test_the_context_signal_wins_when_it_is_true(self):
        """A True signal means THIS turn is architectural — keep the context."""

        result = resolve_turn_domain("صدا میاد؟", architectural_session(signal=True))
        assert result["domain"]["domain"] == "architecture"
        assert result["domain_block"]["architectural_context_injected"] is True

    def test_the_session_store_is_not_modified_by_resolution(self):
        context = architectural_session()
        before = repr(context)

        for text in ("صدا میاد؟", "سلام", "خانه"):
            resolve_turn_domain(text, context)

        assert repr(context) == before


# ======================================================================
# THE CLASS
# ======================================================================

class TestClass:

    def test_boundaries(self):
        layer = conversation_domain
        assert layer.CONTRACT == CONTRACT
        assert layer.MUTATES_SESSION_CONTEXT is False
        assert layer.DELETES_ARCHITECTURAL_CONTEXT is False
        assert layer.GENERATES_DESIGN is False
        assert layer.RENDERS is False
        assert layer.USES_VISION is False

    def test_the_class_api(self):
        assert conversation_domain.classify("صدا میاد؟")["domain"] == "voice_audio"
        assert conversation_domain.project(architectural_session(), "general")["suspended"] is True
        assert conversation_domain.resolve("سلام", architectural_session())["domain"]["domain"] == "general"
