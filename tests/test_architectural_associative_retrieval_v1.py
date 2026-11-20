"""Architectural Associative Retrieval (V1) — isolated self-checks.

Closes GAP 1 and GAP 2 of `ARCHITECTURAL_LEARNING_USAGE_VALIDATION_V1_PARTIAL`.

    T1  explicit retrieval still works
    T2  implicit relationship retrieval works
    T3  multi-space knowledge retrieval works
    T4  unconfirmed knowledge is never retrieved
    T5  no invented architectural knowledge appears
    T6  natural language output remains human-like
    +   the contract, non-claims, and no forbidden import
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

from core.knowledge.architectural_knowledge_retrieval_v1 import (
    NO_KNOWLEDGE,
    retrieve,
)

from core.knowledge.architectural_associative_retrieval_v1 import (
    CONTRACT,
    SPACE_SURFACE,
    ArchitecturalAssociativeRetrievalV1,
    ArchitecturalAssociativeRetrievalError,
    architectural_associative_retrieval,
    associative_retrieve,
    extract_topics,
)


MODULE = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "knowledge"
    / "architectural_associative_retrieval_v1.py"
)


STAIR = (
    "راه پله عنصر ارتباط عمودی است.\n"
    "باکس راه پله در طبقات ثابت می‌ماند.\n"
    "تعداد پله‌ها با ارتفاع تغییر می‌کند."
)

CLOSET = "نزدیکی حمام و کلوزت باعث کاهش مسیر حرکت و افزایش حفظ حریم می‌شود."

LIGHT = "فضاهای اصلی خانه نیاز به نورگیری دارند."

MASTER = "فضای مستر دارای روابط فضایی بین خواب، حمام و کلوزت است."


IMPLICIT_QUESTION = "اگر بخواهیم اتاق خواب طبقه دوم را جابه‌جا کنیم چه چیزی را باید بررسی کنیم؟"

MULTI_QUESTION = (
    "برای یک زمین کوچک که هم راه پله، هم اتاق مستر و هم نورگیری لازم دارد "
    "چه چیزهایی باید بررسی شود؟"
)


def store(memory, text):

    candidate = extract(text, turn_kind="TEACHING_STATEMENT")

    assert candidate is not None, text

    review = open_review(candidate)

    review.confirm()

    return memory.add_confirmed_entry(review.to_confirmed_entry())


def memory_with(*texts):

    memory = ArchitecturalKnowledgeMemoryV1()

    entries = [store(memory, text) for text in texts]

    return memory, entries


# ==========================================================
# T1 — explicit retrieval still works
# ==========================================================

def test_t1_explicit_retrieval_still_works():

    memory, entries = memory_with(STAIR)

    result = associative_retrieve("راه پله چه چیزی یاد گرفتی؟", memory)

    assert result["found"] is True

    assert entries[0]["knowledge_id"] in result["knowledge_ids"]

    # the plain retrieval boundary is untouched and still works
    assert retrieve("راه پله چه چیزی یاد گرفتی؟", memory)["found"] is True


# ==========================================================
# T2 — implicit relationship retrieval
# ==========================================================

def test_t2_an_implicit_question_reaches_the_stair():

    memory, entries = memory_with(STAIR, CLOSET, LIGHT, MASTER)

    stair_id = entries[0]["knowledge_id"]

    result = associative_retrieve(IMPLICIT_QUESTION, memory)

    # the stair is reached although the question never names it
    assert stair_id in result["knowledge_ids"]

    assert "stair" not in IMPLICIT_QUESTION


def test_t2_the_concept_bridge_is_what_reaches_it():

    memory, entries = memory_with(STAIR)

    topics = extract_topics(IMPLICIT_QUESTION, memory)

    assert "vertical_circulation" in topics["concepts"]

    result = associative_retrieve(IMPLICIT_QUESTION, memory)

    assert result["found"] is True


# ==========================================================
# T3 — multi-space knowledge retrieval
# ==========================================================

def test_t3_a_multi_entity_question_retrieves_several_entries():

    memory, entries = memory_with(STAIR, CLOSET, LIGHT, MASTER)

    result = associative_retrieve(MULTI_QUESTION, memory)

    assert result["entry_count"] >= 3

    assert len(result["topics"]["spaces"]) >= 3


def test_t3_the_topics_cover_every_named_area():

    memory, entries = memory_with(STAIR, CLOSET, LIGHT, MASTER)

    topics = extract_topics(MULTI_QUESTION, memory)

    assert "stair" in topics["spaces"]

    assert "master bedroom" in topics["spaces"]

    # the daylight teaching is reached through the lighting concept
    assert "lighting" in topics["concepts"]


# ==========================================================
# T4 — unconfirmed knowledge is never retrieved
# ==========================================================

def test_t4_an_unconfirmed_candidate_is_never_retrieved():

    memory = ArchitecturalKnowledgeMemoryV1()

    assert extract(STAIR, turn_kind="TEACHING_STATEMENT") is not None

    result = associative_retrieve("راه پله چه چیزی یاد گرفتی؟", memory)

    assert result["found"] is False

    assert result["no_knowledge"] is True

    assert result["answer"] == NO_KNOWLEDGE["fa"]


def test_t4_a_superseded_revision_is_never_current():

    memory = ArchitecturalKnowledgeMemoryV1()

    first = store(memory, "Bathroom should be next to closet.")

    candidate = extract(
        "Closet should be next to bathroom in the master bedroom.",
        turn_kind="TEACHING_STATEMENT",
    )

    review = open_review(candidate)

    review.confirm()

    memory.add_confirmed_entry(
        review.to_confirmed_entry(), previous_revision=first["knowledge_id"]
    )

    assert memory._by_id(first["knowledge_id"])["status"] == "superseded"

    result = associative_retrieve("رابطه حمام و کلوزت", memory)

    assert first["knowledge_id"] not in result["knowledge_ids"]

    for entry in result["entries"]:

        assert entry["status"] == "active"


def test_t4_retrieval_requires_a_memory():

    with pytest.raises(ArchitecturalAssociativeRetrievalError):

        associative_retrieve("راه پله", None)


# ==========================================================
# T5 — no invented architectural knowledge
# ==========================================================

def test_t5_every_returned_entry_is_a_stored_confirmed_entry():

    memory, entries = memory_with(STAIR, CLOSET, LIGHT, MASTER)

    stored_ids = {e["knowledge_id"] for e in memory.active_entries()}

    result = associative_retrieve(MULTI_QUESTION, memory)

    assert result["knowledge_ids"]

    for knowledge_id in result["knowledge_ids"]:

        assert knowledge_id in stored_ids


def test_t5_the_layer_declares_it_invents_nothing():

    assert ArchitecturalAssociativeRetrievalV1.INVENTS_KNOWLEDGE is False

    assert ArchitecturalAssociativeRetrievalV1.GENERATES_DESIGN is False

    memory = ArchitecturalKnowledgeMemoryV1()

    result = associative_retrieve("یک موضوع ناشناخته", memory)

    assert result["non_claims"]["not_invented"] is True

    assert result["non_claims"]["confirmed_memory_only"] is True

    assert result["found"] is False


# ==========================================================
# T6 — natural language output
# ==========================================================

def test_t6_the_output_is_natural_not_json():

    memory, entries = memory_with(STAIR, CLOSET, LIGHT, MASTER)

    answer = associative_retrieve(IMPLICIT_QUESTION, memory)["answer"]

    assert isinstance(answer, str)

    assert "از آموزش‌های تأییدشدهٔ شما" in answer

    for marker in ("{", "}", "contract", "knowledge_id", "facets"):

        assert marker not in answer


def test_t6_the_answer_stays_non_absolute():

    memory, entries = memory_with(CLOSET)

    answer = associative_retrieve("آیا هر اتاق مستری حتما باید کلوزت کنار حمام داشته باشد؟", memory)["answer"]

    for absolute in ("must", "always", "همیشه"):

        assert absolute not in answer


# ==========================================================
# the contract + vocabularies
# ==========================================================

def test_the_contract_is_declared():

    memory, entries = memory_with(STAIR)

    result = associative_retrieve("راه پله", memory)

    assert result["contract"] == CONTRACT

    for field in (
        "topics", "direct_ids", "associated_ids", "association_trace",
        "entries", "answer", "found", "non_claims",
    ):

        assert field in result, field

    assert result["design_generated"] is False

    assert result["memory_written"] is False


def test_the_persian_surface_vocabulary_only_recognises_words():

    # a surface form is a HANDLE — it adds no knowledge of its own
    assert SPACE_SURFACE["راه پله"] == "stair"

    assert SPACE_SURFACE["اتاق مستر"] == "master bedroom"

    memory = ArchitecturalKnowledgeMemoryV1()

    # the handle resolves to NOTHING when nothing was taught
    result = associative_retrieve("راه پله چه چیزی یاد گرفتی؟", memory)

    assert result["found"] is False


# ==========================================================
# dependency direction
# ==========================================================

def test_the_module_imports_no_forbidden_package():

    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))

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

            assert not root.startswith(forbidden), root
