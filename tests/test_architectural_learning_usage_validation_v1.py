"""ARCHITECTURAL_LEARNING_USAGE_VALIDATION_PHASE_V1 — isolated self-checks.

Validates the full human cycle:

    Human Teaching -> Knowledge Extraction -> Human Confirmation
        -> Architectural Knowledge Memory -> Knowledge Retrieval
        -> Architectural Reasoning

It proves what WORKS and records what DOES NOT (as `test_known_limitation_*`),
honestly, with live evidence. NO design / plan / render / CAD / BIM / geometry.
"""

from __future__ import annotations


import ast
from pathlib import Path

import pytest

from core.knowledge.architectural_knowledge_extraction_engine_v1 import (
    extract_architectural_knowledge_candidate_v1 as extract,
)

from core.knowledge.human_knowledge_validation_loop_v1 import open_review

from core.knowledge.architectural_knowledge_memory_v1 import (
    ArchitecturalKnowledgeMemoryV1,
)

from core.knowledge.architectural_knowledge_retrieval_v1 import retrieve

from core.knowledge.architectural_reasoning_v1 import reason_design


MODULES = (
    Path(__file__).resolve().parents[1] / "core" / "knowledge" / "architectural_knowledge_extraction_engine_v1.py",
    Path(__file__).resolve().parents[1] / "core" / "knowledge" / "human_knowledge_validation_loop_v1.py",
    Path(__file__).resolve().parents[1] / "core" / "knowledge" / "architectural_knowledge_memory_v1.py",
    Path(__file__).resolve().parents[1] / "core" / "knowledge" / "architectural_knowledge_retrieval_v1.py",
    Path(__file__).resolve().parents[1] / "core" / "knowledge" / "architectural_reasoning_v1.py",
)


# ----------------------------------------------------------
# the human teaching used by the scenarios
# ----------------------------------------------------------

STAIR = (
    "راه پله عنصر ارتباط عمودی است.\n"
    "باکس راه پله در طبقات ثابت می‌ماند.\n"
    "تعداد پله‌ها با ارتفاع ساختمان تغییر می‌کند."
)

CLOSET = "نزدیکی حمام و کلوزت باعث کاهش مسیر حرکت و افزایش حفظ حریم می‌شود."

LIGHT = "فضاهای اصلی خانه نیاز به نورگیری دارند."

MASTER = "فضای مستر دارای روابط فضایی بین خواب، حمام و کلوزت است."


QUESTION_1 = "اگر در طبقه دوم بخواهیم اتاق خواب را جابه‌جا کنیم چه چیزی را باید بررسی کنیم؟"

QUESTION_2 = "آیا هر اتاق مستری حتما باید کلوزت کنار حمام داشته باشد؟"

QUESTION_3 = (
    "برای یک زمین کوچک که هم راه پله، هم اتاق مستر و هم نورگیری لازم دارد "
    "چه چیزهایی باید بررسی شود؟"
)


def teach(memory, text, turn_kind="TEACHING_STATEMENT"):

    """The full cycle: extract -> confirm -> store. Returns the memory entry."""

    candidate = extract(text, turn_kind=turn_kind)

    assert candidate is not None, "no candidate for %r" % (text,)

    review = open_review(candidate)

    review.confirm()

    return memory.add_confirmed_entry(review.to_confirmed_entry())


def memory_with(*texts):

    memory = ArchitecturalKnowledgeMemoryV1()

    for text in texts:

        teach(memory, text)

    return memory


# ==========================================================
# S1 — a previously stored teaching used in a NEW question
# ==========================================================

def test_s1_the_full_human_cycle_runs_end_to_end():

    memory = memory_with(STAIR)

    assert memory.count() == 1

    result = retrieve("راه پله چه چیزی یاد گرفتی؟", memory)

    assert result["found"] is True

    assert result["entry_count"] == 1


def test_s1_a_stored_teaching_is_retrieved_by_its_own_topic():

    memory = memory_with(STAIR)

    result = retrieve("راه پله چه چیزی یاد گرفتی؟", memory)

    answer = result["answer"]

    # the facets the brief asks for are all reachable
    assert "ارتباط عمودی" in answer          # function
    assert "ثابت" in answer                  # fixed
    assert "تغییر می" in answer              # variable


def test_s1_reasoning_can_use_the_retrieved_knowledge():

    memory = memory_with(STAIR)

    retrieval = retrieve("راه پله", memory)

    result = reason_design(
        {"topic": "راه پله", "area_limitation": True}, retrieval=retrieval
    )

    assert result["used_knowledge"]

    assert result["human_review_required"] is True

    assert result["is_final_solution"] is False


def test_known_limitation_s1_an_implicit_question_does_not_retrieve_the_element():

    """KNOWN LIMITATION (recorded honestly): the retrieval is entity-keyword based.

    A question that *implies* a stored element without NAMING it (moving a
    bedroom on the 2nd floor implies the FIXED stair) does NOT retrieve the
    stair knowledge today.
    """

    memory = memory_with(STAIR)

    stair_entry = memory.active_entries()[0]

    result = retrieve(QUESTION_1, memory)

    assert stair_entry["knowledge_id"] not in result["knowledge_ids"]


# ==========================================================
# S2 — knowledge does not become absolute
# ==========================================================

def test_s2_the_relationship_is_retrieved():

    memory = memory_with(CLOSET)

    result = retrieve(QUESTION_2, memory)

    assert result["found"] is True

    assert "closet" in result["answer"].lower() or "bathroom" in result["answer"].lower()


def test_s2_no_absolute_rule_is_produced():

    memory = memory_with(CLOSET)

    answer = retrieve(QUESTION_2, memory)["answer"]

    for absolute in ("must", "always", "باید", "همیشه"):

        assert absolute not in answer


def test_s2_the_memory_entry_declares_non_absolute():

    memory = memory_with(CLOSET)

    entry = memory.active_entries()[0]

    assert entry["is_absolute"] is False

    assert entry["non_claims"]["not_absolute_rule"] is True


# ==========================================================
# S3 — several teachings used together
# ==========================================================

def test_s3_several_teachings_are_stored():

    memory = memory_with(STAIR, CLOSET, LIGHT, MASTER)

    assert memory.count() == 4

    for entry in memory.active_entries():

        assert entry["status"] == "active"


def test_known_limitation_s3_a_multi_entity_question_retrieves_only_one_entity():

    """KNOWN LIMITATION (recorded honestly): the query understanding extracts a
    single entity from the multi-entity question, so only ONE of the three
    requested knowledge areas is retrieved today.
    """

    memory = memory_with(STAIR, CLOSET, LIGHT, MASTER)

    result = retrieve(QUESTION_3, memory)

    assert result["understanding"]["spaces"] == ["stair"]

    assert result["entry_count"] == 1


def test_s3_reasoning_never_produces_a_plan():

    memory = memory_with(STAIR, CLOSET, LIGHT, MASTER)

    result = reason_design(
        {
            "topic": "small site",
            "area_limitation": True,
            "user_requirements": ["راه پله", "اتاق مستر", "نورگیری"],
        },
        retrieval=retrieve(QUESTION_3, memory),
    )

    assert result["is_final_solution"] is False

    assert result["non_claims"]["not_a_plan"] is True

    payload = str(result).lower()

    for forbidden in ("geometry", "polygon", "cad", "bim", "ifc"):

        assert forbidden not in payload.replace("not_geometry", "").replace("not_cad_or_bim", "")


# ==========================================================
# S4 — the human experience
# ==========================================================

def test_s4_a_natural_persian_question_is_understood():

    memory = memory_with(STAIR)

    result = retrieve("راه پله چه چیزی یاد گرفتی؟", memory)

    assert result["understanding"]["spaces"] == ["stair"]


def test_s4_no_json_and_no_form_is_required():

    memory = memory_with(STAIR)

    answer = retrieve("راه پله چه چیزی یاد گرفتی؟", memory)["answer"]

    assert isinstance(answer, str)

    for marker in ("{", "}", "contract", "facets", "knowledge_id"):

        assert marker not in answer


def test_s4_a_question_is_never_mistaken_for_teaching():

    for question in (QUESTION_1, QUESTION_2, QUESTION_3):

        assert extract(question) is None


def test_s4_a_correction_is_a_learning_act():

    memory = ArchitecturalKnowledgeMemoryV1()

    candidate = extract("حمام باید همیشه کنار کلوزت باشد", turn_kind="TEACHING_STATEMENT")

    review = open_review(candidate)

    # the human corrects BEFORE confirming
    refinement = review.request_refinement("نه، فقط در اتاق خواب مستر و در صورت وجود فضای کافی.")

    assert review.superseded_by == refinement.review_id

    assert review.candidate["human_basis"]  # the old candidate is kept

    assert refinement.state == "pending_review"

    assert refinement.candidate["candidate_kind"] == "correction"


def test_s4_only_confirmed_knowledge_is_ever_used():

    memory = ArchitecturalKnowledgeMemoryV1()

    # a candidate exists but is NEVER confirmed / stored
    assert extract(STAIR, turn_kind="TEACHING_STATEMENT") is not None

    result = retrieve("راه پله چه چیزی یاد گرفتی؟", memory)

    assert result["found"] is False

    assert result["no_knowledge"] is True


# ==========================================================
# no design / no generation / frozen surfaces
# ==========================================================

def test_no_generation_module_is_imported_by_the_knowledge_layer():

    for module in MODULES:

        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))

        roots = []

        for node in ast.walk(tree):

            if isinstance(node, ast.Import):

                roots.extend(alias.name for alias in node.names)

            elif isinstance(node, ast.ImportFrom):

                if node.module:

                    roots.append(node.module)

        for root in roots:

            for forbidden in (
                "core.vision",
                "core.render",
                "core.rendering",
                "core.cad",
                "core.bim",
                "core.ifc",
                "core.geometry",
                "core.spatial",
                "core.ai",
                "core.runtime",
            ):

                assert not root.startswith(forbidden), (str(module), root)
