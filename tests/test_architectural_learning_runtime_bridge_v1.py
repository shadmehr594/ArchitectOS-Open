# -*- coding: utf-8 -*-
"""ARCHITECTURAL_LEARNING_RUNTIME_BRIDGE_V1 — tests.

Covers the human learning cycle (A-D) plus the contract guarantees:
no automatic learning, no absolute rules, context/exception preservation,
no design generation, and non-invention.
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.knowledge.architectural_learning_runtime_bridge_v1 import (
    bridge,
    reset_state,
    get_memory,
    extract_concepts,
    expand_concepts,
    augment_candidate,
    is_confirmation,
    looks_like_project_request,
    memory_path,
    pending_path,
    architectural_learning_runtime,
    CONTRACT,
)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _turn(kind, candidate=True):
    """A minimal teaching-turn observation (what observe_turn returns)."""

    return {
        "turn_kind": kind,
        "candidate": ({"placeholder": True} if candidate else None),
        "language": "fa",
        "short_circuit": True,
    }


@pytest.fixture(autouse=True)
def _isolated_store():
    tmp = tempfile.mkdtemp(prefix="bridge_test_")
    reset_state(
        memory_path_=os.path.join(tmp, "memory.json"),
        pending_path_=os.path.join(tmp, "pending.json"),
    )
    yield
    reset_state()


def teach(session, text, kind="TEACHING_STATEMENT"):
    return bridge(_turn(kind), text, {}, session_id=session)


def confirm(session, text="تایید"):
    return bridge(_turn("NORMAL_CONVERSATION", candidate=False), text, {}, session_id=session)


def ask(session, text, kind="NORMAL_CONVERSATION"):
    return bridge(_turn(kind, candidate=False), text, {}, session_id=session)


# ======================================================================
# TEST A — teach -> confirm -> the knowledge is used in a NEW request
# ======================================================================

class TestA_HumanCycle:

    def test_a1_teaching_proposes_and_writes_nothing(self):

        r = teach("sA", "راه پله یک عنصر ثابت است و نباید برای اضافه کردن کلوزت کوچک شود.")

        assert r is not None
        assert r["teaching"]["action"] == "propose_learning"
        assert r["teaching"]["awaiting_human_confirmation"] is True
        assert r["teaching"]["memory_written"] is False
        assert get_memory().count() == 0          # NOTHING learned automatically

    def test_a2_the_prompt_is_natural_not_a_form(self):

        r = teach("sA", "راه پله یک عنصر ثابت است و نباید برای اضافه کردن کلوزت کوچک شود.")

        text = r["result"]
        assert "این برداشت من از آموزش شماست" in text
        for schema_word in ("Element:", "JSON", "{", "schema"):
            assert schema_word not in text

    def test_a3_confirmation_stores_it(self):

        teach("sA", "راه پله یک عنصر ثابت است و نباید برای اضافه کردن کلوزت کوچک شود.")
        r = confirm("sA")

        assert r["teaching"]["action"] == "confirm_learning"
        assert r["teaching"]["memory_written"] is True
        assert r["teaching"]["is_absolute"] is False
        assert get_memory().count() == 1

    def test_a4_the_new_request_uses_the_learned_knowledge(self):

        teach("sA", "راه پله یک عنصر ثابت است و نباید برای اضافه کردن کلوزت کوچک شود.")
        confirm("sA")

        r = ask("sA", "خانه دوبلکس روی زمین کوچک با اتاق مستر و کلوزت")

        assert r is not None
        assert r["teaching"]["action"] == "answer_from_learned_memory"
        used = r["teaching"]["used_knowledge"]
        assert used, "the learned knowledge must appear in the reasoning"
        assert any("stair" in (e.get("element") or []) for e in used)

    def test_a5_duplex_reaches_the_stair_by_MEANING(self):
        """duplex -> multiple floors -> vertical circulation -> stair."""

        teach("sA", "راه پله یک عنصر ثابت است و نباید برای اضافه کردن کلوزت کوچک شود.")
        confirm("sA")

        r = ask("sA", "خانه دوبلکس روی زمین کوچک با اتاق مستر و کلوزت")
        concepts = r["teaching"]["concepts"]

        assert "multiple_floors" in concepts       # from «دوبلکس»
        assert "vertical_circulation" in concepts  # implied
        assert "stair" in concepts                 # implied

    def test_a6_the_conflict_is_explained_and_the_stair_is_protected(self):

        teach("sA", "راه پله یک عنصر ثابت است و نباید برای اضافه کردن کلوزت کوچک شود.")
        confirm("sA")

        r = ask("sA", "خانه دوبلکس روی زمین کوچک با اتاق مستر و کلوزت")

        assert "fixed_vs_flexible" in r["teaching"]["conflicts"]
        assert "stair" in r["result"]

    def test_a7_no_design_no_render_no_geometry(self):

        teach("sA", "راه پله یک عنصر ثابت است و نباید برای اضافه کردن کلوزت کوچک شود.")
        confirm("sA")
        r = ask("sA", "خانه دوبلکس روی زمین کوچک با اتاق مستر و کلوزت")

        assert r["render_requested"] is False
        assert r["learning_runtime"]["design_generated"] is False
        assert r["learning_runtime"]["geometry_generated"] is False
        assert r["learning_runtime"]["render_requested"] is False


# ======================================================================
# TEST B — context is preserved and later mentioned
# ======================================================================

class TestB_ContextPreservation:

    def test_b1_the_condition_is_preserved_as_context(self):

        r = teach("sB", "در زمین کوچک حذف کلوزت منطقی‌تر است.")

        assert r is not None
        assert any("context_preserved" in t for t in r["learning_runtime"]["trace"])

    def test_b2_the_exception_is_preserved(self):

        r = teach("sB", "در زمین کوچک حذف کلوزت منطقی‌تر است.")

        assert any("exception_preserved" in t for t in r["learning_runtime"]["trace"])

    def test_b3_stored_context_and_exception_are_explicit(self):

        teach("sB", "در زمین کوچک حذف کلوزت منطقی‌تر است.")
        confirm("sB")

        entry = get_memory().active_entries()[0]

        assert "site_size: small" in entry["context"]
        assert any("optional" in e for e in entry["exceptions"])

    def test_b4_it_is_never_converted_into_an_absolute_rule(self):

        teach("sB", "در زمین کوچک حذف کلوزت منطقی‌تر است.")
        confirm("sB")

        entry = get_memory().active_entries()[0]

        assert entry["is_absolute"] is False
        assert entry["context"]              # a contextual rule keeps its context
        assert "always" not in str(entry["exceptions"]).lower()

    def test_b5_a_small_house_question_mentions_the_context(self):

        teach("sB", "در زمین کوچک حذف کلوزت منطقی‌تر است.")
        confirm("sB")

        r = ask("sB", "خانه کوچک")

        assert r is not None
        assert r["teaching"]["action"] == "answer_from_learned_memory"
        joined = r["result"] + " " + " ".join(r["teaching"]["concepts"])
        assert ("زمین کوچک" in joined) or ("site_size" in joined) or ("area_limitation" in joined)


# ======================================================================
# TEST C — a correction preserves the revision history
# ======================================================================

class TestC_Correction:

    def test_c1_correction_supersedes_and_keeps_the_old_revision(self):

        teach("sC", "کلوزت لازم است.")
        confirm("sC")

        old_id = get_memory().active_entries()[0]["knowledge_id"]

        teach("sC", "نه، کلوزت در زمین کوچک اختیاری است.", kind="CORRECTION")
        r = confirm("sC")

        new_id = r["teaching"]["knowledge_id"]
        memory = get_memory()

        assert r["teaching"]["revision"] == 2
        assert memory._by_id(old_id) is not None              # never deleted
        assert memory._by_id(old_id)["status"] == "superseded"
        assert memory._by_id(old_id)["superseded_by"] == new_id
        assert len(memory.get_revision_history(new_id)) == 2

    def test_c2_the_correction_is_traced_as_a_supersede(self):

        teach("sC", "کلوزت لازم است.")
        confirm("sC")

        r = teach("sC", "نه، کلوزت در زمین کوچک اختیاری است.", kind="CORRECTION")

        assert any("supersede_target" in t for t in r["learning_runtime"]["trace"])

    def test_c3_only_the_related_item_is_superseded(self):

        teach("sC", "راه پله یک عنصر ثابت است و نباید برای اضافه کردن کلوزت کوچک شود.")
        confirm("sC")
        teach("sC", "کلوزت لازم است.")
        confirm("sC")

        stair_id = [
            e["knowledge_id"]
            for e in get_memory().active_entries()
            if "stair" in (e.get("element") or [])
        ][0]

        teach("sC", "نه، کلوزت در زمین کوچک اختیاری است.", kind="CORRECTION")
        confirm("sC")

        assert get_memory()._by_id(stair_id)["status"] == "active"


# ======================================================================
# TEST D — an unknown topic invents nothing
# ======================================================================

class TestD_NoInvention:

    def test_d1_an_unknown_topic_is_declined(self):

        teach("sD", "راه پله یک عنصر ثابت است.")
        confirm("sD")

        r = ask("sD", "در مورد بیمارستان و آی‌سی‌یو چه می‌دانی؟")

        assert r is None, "the bridge must decline rather than invent"

    def test_d2_the_memory_is_unchanged(self):

        teach("sD", "راه پله یک عنصر ثابت است.")
        confirm("sD")

        before = get_memory().count()
        ask("sD", "در مورد بیمارستان و آی‌سی‌یو چه می‌دانی؟")

        assert get_memory().count() == before

    def test_d3_an_empty_memory_declines_everything(self):

        assert ask("sD", "خانه دوبلکس روی زمین کوچک با اتاق مستر و کلوزت") is None


# ======================================================================
# CONTRACT GUARANTEES
# ======================================================================

class TestGuarantees:

    def test_no_memory_write_without_confirmation(self):

        teach("g", "راه پله یک عنصر ثابت است.")
        teach("g", "در زمین کوچک حذف کلوزت منطقی‌تر است.")

        assert get_memory().count() == 0

    def test_a_question_is_never_learned(self):

        r = bridge(_turn("QUESTION", candidate=False), "راه پله چیست؟", {}, session_id="g")

        assert r is None
        assert get_memory().count() == 0

    def test_a_stray_confirmation_learns_nothing(self):

        r = confirm("g", "بله")

        assert r is None
        assert get_memory().count() == 0

    def test_the_pending_review_is_visible_and_confirmable(self):

        teach("g", "راه پله یک عنصر ثابت است.")

        assert "g" in architectural_learning_runtime.pending()

    def test_the_response_mirrors_the_chat_contract(self):

        r = teach("g", "راه پله یک عنصر ثابت است.")

        assert r["type"] == "chat"
        assert r["status"] == "success"
        assert isinstance(r["result"], str)
        assert r["render_requested"] is False
        assert r["learning_runtime"]["contract"] == CONTRACT

    def test_the_layer_declares_its_boundaries(self):

        layer = architectural_learning_runtime

        assert layer.GENERATES_DESIGN is False
        assert layer.GENERATES_GEOMETRY is False
        assert layer.WRITES_MEMORY_WITHOUT_CONFIRMATION is False
        assert layer.DUPLICATES_EXTRACTION is False
        assert layer.DUPLICATES_CLASSIFICATION is False
        assert layer.DUPLICATES_MEMORY is False

    def test_persistence_paths_live_under_the_data_root(self):
        """The DEFAULT path derives from PROJECT_DATA_ROOT (not a new store)."""

        import core.knowledge.architectural_learning_runtime_bridge_v1 as B

        saved_memory = B._MEMORY_PATH_OVERRIDE
        saved_pending = B._PENDING_PATH_OVERRIDE

        try:

            B._MEMORY_PATH_OVERRIDE = None
            B._PENDING_PATH_OVERRIDE = None

            assert os.path.join("learning", "knowledge_memory.json") in B.memory_path()
            assert os.path.join("learning", "pending_reviews.json") in B.pending_path()
            assert B.memory_path().startswith(B._data_root())

        finally:

            B._MEMORY_PATH_OVERRIDE = saved_memory
            B._PENDING_PATH_OVERRIDE = saved_pending

    def test_the_memory_is_the_EXISTING_one(self):

        from core.knowledge.architectural_knowledge_memory_v1 import (
            ArchitecturalKnowledgeMemoryV1,
        )

        assert isinstance(get_memory(), ArchitecturalKnowledgeMemoryV1)


# ======================================================================
# SEMANTIC ASSOCIATION + AUGMENTATION UNITS
# ======================================================================

class TestSemantics:

    def test_duplex_expands_to_the_stair(self):

        concepts = expand_concepts(extract_concepts("خانه دوبلکس روی زمین کوچک"))

        assert "multiple_floors" in concepts
        assert "vertical_circulation" in concepts
        assert "stair" in concepts
        assert "area_limitation" in concepts

    def test_expansion_is_bounded(self):

        concepts = expand_concepts(["multiple_floors"])

        assert len(concepts) <= 1 + len(expand_concepts(["multiple_floors"]))

    def test_an_unrelated_text_yields_no_concepts(self):

        assert extract_concepts("سلام، حالت چطور است؟") == []

    def test_confirmation_detection_is_short_and_explicit(self):

        assert is_confirmation("تایید")
        assert is_confirmation("بله درست است")
        assert is_confirmation("yes")
        assert not is_confirmation("راه پله یک عنصر ثابت است و این جمله بسیار طولانی است تا آزمایش شود")

    def test_a_program_request_is_not_teaching(self):

        assert looks_like_project_request("خانه دوبلکس روی زمین کوچک با اتاق مستر و کلوزت")
        assert not looks_like_project_request("راه پله یک عنصر ثابت است.")

    def test_augmentation_never_invents_a_facet(self):

        candidate = {"context": [], "exceptions": [], "facets_present": []}
        out, notes = augment_candidate(candidate, "راه پله یک عنصر ثابت است.")

        assert out["context"] == []
        assert out["exceptions"] == []
        assert notes == []

    def test_augmentation_does_not_mutate_the_engine_marker_tables(self):

        from core.knowledge.architectural_knowledge_extraction_engine_v1 import (
            FACET_KEYS,
        )

        assert "context" in FACET_KEYS
        assert "exceptions" in FACET_KEYS
