"""Human Architectural Knowledge Validation Loop (V1) — isolated self-checks.

Proves the validation layer:

    1. a review starts `pending_review` and requires a HUMAN confirmation
    2. the confirmation prompt is NATURAL (not a schema)
    3. only a confirmed review yields a confirmed entry
    4. a rejection yields NO entry
    5. a correction creates a refinement and NEVER deletes the old candidate
    6. no auto-learning / AI approval / truth / confidence / authority
    7. the handoff is storage-agnostic (no memory write)
    8. imports no vision / render / cad / bim / geometry / runtime module
"""

from __future__ import annotations


import ast
from pathlib import Path

import pytest

from core.knowledge.architectural_knowledge_extraction_engine_v1 import (
    extract_architectural_knowledge_candidate_v1 as extract,
)

from core.knowledge.human_knowledge_validation_loop_v1 import (
    ENTRY_CONTRACT,
    FACET_KEYS,
    FORBIDDEN_STATES,
    REVIEW_CONTRACT,
    REVIEW_STATES,
    STATE_CONFIRMED,
    STATE_PENDING_REVIEW,
    STATE_REJECTED,
    STATE_REFINEMENT_REQUESTED,
    ArchitecturalKnowledgeReview,
    ArchitecturalKnowledgeValidationError,
    build_confirmation_prompt,
    handoff_confirmed_entry,
    human_knowledge_validation_loop,
    open_review,
)


MODULE = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "knowledge"
    / "human_knowledge_validation_loop_v1.py"
)


SPACES = "فضاهای اصلی خانه شامل اتاق خواب، پذیرایی و آشپزخانه هستند."

STAIR = (
    "راه پله عنصر ارتباط عمودی است.\n"
    "باکس راه پله ثابت است.\n"
    "تعداد پله با ارتفاع تغییر می‌کند."
)

ABSOLUTE = "حمام باید همیشه کنار کلوزت باشد."

CORRECTION = "نه، در اتاق خواب مستر و با شرایط خاص."

QUESTION = "ابعاد استاندارد اتاق خواب چقدر است؟"


def _text(values):

    return " ".join(str(v) for v in values or [])


# ==========================================================
# TASK 5 / TEST 1 — basic teaching confirmation
# ==========================================================

def test_test1_candidate_created_and_review_requires_confirmation():

    candidate = extract(SPACES)

    assert candidate is not None

    review = open_review(candidate)

    assert review.state == STATE_PENDING_REVIEW

    assert review.human_confirmed is False

    # no automatic memory: an unconfirmed review yields NO entry
    assert review.to_confirmed_entry() is None


def test_test1_confirmation_is_what_produces_the_entry():

    review = open_review(extract(SPACES))

    review.confirm()

    entry = review.to_confirmed_entry()

    assert entry is not None

    assert entry["status"] == "confirmed"

    assert entry["confirmed_by"] == "HUMAN_TEACHER"


# ==========================================================
# TASK 5 / TEST 2 — the stair review
# ==========================================================

def test_test2_the_review_shows_the_extracted_facets():

    review = open_review(extract(STAIR))

    candidate = review.candidate

    assert "stair" in candidate["element"]

    assert "ارتباط عمودی" in _text(candidate["function"])

    assert "ثابت" in _text(candidate["fixed_properties"])

    assert "تغییر می" in _text(candidate["variable_properties"])


def test_test2_the_prompt_reads_naturally_not_as_a_schema():

    prompt = build_confirmation_prompt(open_review(extract(STAIR)))

    assert "این برداشت من از آموزش شماست" in prompt

    assert "آیا درست استخراج شده" in prompt

    # it never asks the human to fill a field
    for schema_word in ("Element:", "Function:", "JSON", "schema", "فیلد"):

        assert schema_word not in prompt


# ==========================================================
# TASK 5 / TEST 3 — the correction
# ==========================================================

def test_test3_correction_creates_a_refinement_and_keeps_the_old_candidate():

    original = open_review(extract(ABSOLUTE))

    old_basis = original.candidate["human_basis"]

    old_id = original.review_id

    refinement = original.request_refinement(CORRECTION)

    # the OLD review keeps its candidate (never deleted)
    assert original.candidate["human_basis"] == old_basis

    assert original.state == STATE_REFINEMENT_REQUESTED

    assert original.superseded_by == refinement.review_id

    # the refinement is a NEW, still-unconfirmed review
    assert refinement.review_id != old_id

    assert refinement.state == STATE_PENDING_REVIEW

    assert refinement.candidate["candidate_kind"] == "correction"


# ==========================================================
# TASK 5 / TEST 4 — the reject
# ==========================================================

def test_test4_reject_yields_no_entry():

    review = open_review(extract(SPACES))

    review.reject("not what I meant")

    assert review.state == STATE_REJECTED

    assert review.to_confirmed_entry() is None


# ==========================================================
# TASK 5 / TEST 5 — question protection
# ==========================================================

def test_test5_question_produces_no_candidate_and_no_review():

    assert extract(QUESTION) is None

    with pytest.raises(ArchitecturalKnowledgeValidationError):

        open_review(None)


# ==========================================================
# TASK 1 — the review contract
# ==========================================================

def test_the_allowed_states_are_exactly_four():

    assert REVIEW_STATES == (
        "pending_review",
        "confirmed",
        "rejected",
        "refinement_requested",
    )

    assert ArchitecturalKnowledgeReview.STATES == REVIEW_STATES

    assert REVIEW_CONTRACT == "ArchitecturalKnowledgeReviewV1"


def test_the_forbidden_states_are_declared():

    for forbidden in (
        "learned",
        "learned_automatically",
        "approved_by_ai",
        "truth",
        "auto_promoted",
        "permanent",
    ):

        assert forbidden in FORBIDDEN_STATES


def test_the_review_carries_no_confidence_truth_or_authority():

    payload = open_review(extract(SPACES)).to_dict()

    for forbidden in ("confidence", "truth", "truth_status", "approval", "score"):

        assert forbidden not in payload

    assert payload["ai_approved"] is False

    assert payload["auto_promoted"] is False

    assert payload["grants_authority"] is False

    assert payload["carries_confidence"] is False

    assert payload["non_claims"]["not_learned_automatically"] is True

    assert payload["non_claims"]["not_approved_by_ai"] is True


def test_a_review_cannot_transition_twice():

    review = open_review(extract(SPACES))

    review.confirm()

    with pytest.raises(ArchitecturalKnowledgeValidationError):

        review.reject()

    with pytest.raises(ArchitecturalKnowledgeValidationError):

        review.confirm()


def test_a_review_accepts_only_an_extraction_candidate():

    with pytest.raises(ArchitecturalKnowledgeValidationError):

        open_review({"contract": "SomethingElseV1"})

    with pytest.raises(ArchitecturalKnowledgeValidationError):

        open_review("not a dict")


# ==========================================================
# TASK 2 — the confirmation prompt
# ==========================================================

def test_the_prompt_has_english_and_persian():

    review = open_review(extract(STAIR))

    assert "This is my reading" in build_confirmation_prompt(review, language="en")

    assert "این برداشت" in build_confirmation_prompt(review, language="fa")


# ==========================================================
# TASK 4 — the memory handoff (boundary only)
# ==========================================================

def test_the_handoff_is_storage_agnostic_and_writes_nothing():

    review = open_review(extract(SPACES))

    review.confirm()

    entry = review.to_confirmed_entry()

    handoff = handoff_confirmed_entry(entry)

    assert handoff["target"] == "ArchitecturalKnowledgeMemory"

    assert handoff["memory_implemented"] is False

    assert handoff["written"] is False

    assert handoff["storage_agnostic"] is True

    assert handoff["storage_reference"] is None


def test_the_handoff_rejects_an_unconfirmed_entry():

    with pytest.raises(ArchitecturalKnowledgeValidationError):

        handoff_confirmed_entry({"contract": "SomethingElseV1"})


def test_the_entry_carries_the_nine_facets_and_the_human_basis():

    review = open_review(extract(STAIR))

    review.confirm()

    entry = review.to_confirmed_entry()

    assert set(entry["facets"]) == set(FACET_KEYS)

    assert entry["human_basis"] == STAIR

    assert entry["is_absolute"] is False

    assert entry["persistent"] is False

    assert entry["contract"] == ENTRY_CONTRACT


# ==========================================================
# no auto-learning / no memory write
# ==========================================================

def test_the_module_never_promotes_or_writes_memory():

    source = MODULE.read_text(encoding="utf-8")

    for forbidden in (
        "def promote",
        "knowledge_memory_store",
        "permanent_memory_store",
        "auto_confirm",
    ):

        assert forbidden not in source


def test_the_loop_singleton_is_declared_safe():

    assert human_knowledge_validation_loop.AI_APPROVED is False

    assert human_knowledge_validation_loop.AUTO_PROMOTED is False


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
            "core.runtime",
        ):

            assert not root.startswith(forbidden), root
