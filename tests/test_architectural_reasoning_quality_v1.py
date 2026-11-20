"""Architectural Reasoning Quality (V1) — isolated self-checks.

Validates the reasoning layer end to end through the ADDITIVE quality boundary:

    T1  single-knowledge reasoning
    T2  multi-knowledge reasoning (dimension assembly)
    T3  fixed-element protection
    T4  flexible-element trade-off
    T5  non-absolute reasoning
    T6  context-dependent parameters (STORED data only)
    T7  correction refinement
    T8  no design generation
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

from core.knowledge.architectural_associative_retrieval_v1 import (
    associative_retrieve,
)

from core.knowledge.architectural_reasoning_v1 import reason_design

from core.knowledge.architectural_reasoning_quality_v1 import (
    CONTRACT,
    DIMENSIONS,
    ArchitecturalReasoningQualityError,
    ArchitecturalReasoningQualityV1,
    architectural_reasoning_quality,
    assemble_dimensions,
    dedupe_conflicts,
    evaluate_context,
    improve_reasoning,
)


MODULE = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "knowledge"
    / "architectural_reasoning_quality_v1.py"
)


STAIR = "راه پله عنصر ارتباط عمودی است.\nباکس راه پله در طبقات ثابت می‌ماند."
MASTER = "اتاق مستر می‌تواند رابطه بین خواب، حمام و کلوزت داشته باشد."
CLOSET = "نزدیکی حمام و کلوزت باعث کاهش مسیر حرکت و افزایش حفظ حریم می‌شود."
LIGHT = "فضاهای اصلی خانه نیاز به نورگیری دارند."


def store(memory, text):

    candidate = extract(text, turn_kind="TEACHING_STATEMENT")

    assert candidate is not None, text

    review = open_review(candidate)

    review.confirm()

    return memory.add_confirmed_entry(review.to_confirmed_entry())


def memory_full():

    memory = ArchitecturalKnowledgeMemoryV1()

    for text in (STAIR, MASTER, CLOSET, LIGHT):

        store(memory, text)

    return memory


def run(memory, question, context):

    retrieval = associative_retrieve(question, memory)

    merged = dict(context)

    merged.setdefault(
        "topic",
        " ".join(retrieval["topics"]["spaces"] + retrieval["topics"]["concepts"]),
    )

    reasoning = reason_design(merged, retrieval=retrieval)

    quality = improve_reasoning(reasoning, retrieval=retrieval, memory=memory)

    return retrieval, reasoning, quality


# ==========================================================
# T1 — single-knowledge reasoning
# ==========================================================

def test_t1_a_single_knowledge_item_is_used():

    memory = ArchitecturalKnowledgeMemoryV1()

    store(memory, STAIR)

    retrieval, reasoning, quality = run(
        memory, "راه پله چه چیزی یاد گرفتی؟", {"area_limitation": True}
    )

    assert quality["used_knowledge"]

    assert quality["entry_count"] >= 1

    assert quality["human_review_required"] is True


# ==========================================================
# T2 — multi-knowledge reasoning
# ==========================================================

def test_t2_several_knowledge_items_are_assembled_into_dimensions():

    memory = memory_full()

    _, _, quality = run(
        memory,
        "برای یک خانه کوچک چندطبقه چه موارد معماری باید همزمان بررسی شوند؟",
        {"area_limitation": True},
    )

    dimensions = {d["dimension"] for d in quality["dimensions"]}

    # the brief's expected combination
    for expected in ("circulation", "privacy", "lighting", "fixed_elements", "flexible_elements"):

        assert expected in dimensions, expected


def test_t2_an_empty_dimension_is_omitted_never_invented():

    memory = ArchitecturalKnowledgeMemoryV1()

    store(memory, STAIR)

    _, _, quality = run(memory, "راه پله", {"topic": "stair"})

    for dimension in quality["dimensions"]:

        assert dimension["knowledge_ids"]


# ==========================================================
# T3 — fixed-element protection
# ==========================================================

def test_t3_a_fixed_element_is_not_modified():

    memory = memory_full()

    _, reasoning, quality = run(
        memory,
        "در یک زمین کوچک اگر برای اضافه کردن کلوزت مجبور شویم عرض راه پله را کم کنیم، چه چیزی باید بررسی شود؟",
        {
            "area_limitation": True,
            "requested_modifications": [{"target": "stair", "reason": "closet"}],
        },
    )

    kinds = {c["kind"] for c in quality["conflicts"]}

    assert "fixed_vs_flexible" in kinds

    assert any(d["kind"] == "fixed_untouched" for d in quality["decisions"])

    assert "stair" in quality["natural_explanation"]


# ==========================================================
# T4 — flexible-element trade-off
# ==========================================================

def test_t4_a_flexible_trade_off_is_explained():

    memory = memory_full()

    _, reasoning, quality = run(
        memory,
        "برای اضافه کردن کلوزت چه گزینه‌هایی وجود دارد؟",
        {"area_limitation": True},
    )

    assert reasoning["alternatives"]

    assert reasoning["trade_offs"]

    for trade_off in reasoning["trade_offs"]:

        assert trade_off["gains"]

        assert trade_off["costs"]


# ==========================================================
# T5 — non-absolute reasoning
# ==========================================================

def test_t5_the_explanation_is_never_absolute():

    memory = memory_full()

    _, _, quality = run(
        memory,
        "آیا هر اتاق مستری حتما باید کلوزت کنار حمام داشته باشد؟",
        {"area_limitation": True},
    )

    text = quality["natural_explanation"]

    assert text.count("باید") == text.count("نباید")

    assert "always" not in text.lower()


def test_t5_duplicate_conflicts_are_collapsed():

    conflicts = [
        {"kind": "area_limitation", "between": ["a"]},
        {"kind": "area_limitation", "between": ["b"]},
        {"kind": "priority_rule", "between": ["c"]},
    ]

    deduped = dedupe_conflicts(conflicts)

    assert [c["kind"] for c in deduped] == ["area_limitation", "priority_rule"]

    assert deduped[0]["between"] == ["a", "b"]


# ==========================================================
# T6 — context-dependent parameters
# ==========================================================

def test_t6_the_context_evaluation_uses_only_stored_data():

    memory = memory_full()

    retrieval, _, quality = run(memory, "راه پله", {"topic": "stair"})

    for item in quality["context_evaluation"]:

        assert item["note"] in ("context_dependent", "no_context_stored")

        # a dependency is only claimed when the STORED entry carries one
        expected = bool(
            item["context"] or item["exceptions"] or item["variable_properties"]
        )

        assert item["context_dependent"] is expected


def test_t6_no_dependency_is_invented_for_an_item_without_context():

    entry = {
        "knowledge_id": "akm_x",
        "element": ["stair"],
        "context": [],
        "exceptions": [],
        "variable_properties": [],
    }

    evaluation = evaluate_context([entry])

    assert evaluation[0]["context_dependent"] is False

    assert evaluation[0]["note"] == "no_context_stored"


# ==========================================================
# T7 — correction refinement
# ==========================================================

def test_t7_a_correction_is_a_refinement_and_history_is_kept():

    memory = ArchitecturalKnowledgeMemoryV1()

    candidate = extract("اتاق مستر باید همیشه کلوزت داشته باشد.", turn_kind="TEACHING_STATEMENT")

    review = open_review(candidate)

    refinement = review.request_refinement("نه، در ساختمان کوچک ممکن است حذف شود.")

    assert review.superseded_by == refinement.review_id

    assert review.candidate["human_basis"]  # the previous context is preserved

    assert refinement.candidate["candidate_kind"] == "correction"

    assert refinement.state == "pending_review"


# ==========================================================
# T8 — no design generation
# ==========================================================

def test_t8_no_design_is_generated():

    memory = memory_full()

    _, reasoning, quality = run(
        memory,
        "برای یک خانه کوچک چندطبقه چه موارد معماری باید همزمان بررسی شوند؟",
        {"area_limitation": True},
    )

    assert quality["is_final_solution"] is False

    assert quality["design_generated"] is False

    assert quality["non_claims"]["not_a_design"] is True

    assert quality["non_claims"]["not_a_plan"] is True

    payload = str(quality).lower()

    for forbidden in ("geometry", "polygon", "cad", "bim", "ifc"):

        assert forbidden not in payload.replace("not_geometry", "").replace("not_cad_or_bim", "")


# ==========================================================
# the contract + helpers
# ==========================================================

def test_the_contract_carries_every_required_field():

    memory = memory_full()

    _, _, quality = run(memory, "راه پله", {"topic": "stair"})

    assert quality["contract"] == CONTRACT

    for field in (
        "conflicts", "decisions", "dimensions", "context_evaluation",
        "used_knowledge", "natural_explanation", "human_review_required",
    ):

        assert field in quality, field


def test_the_dimension_table_is_declared():

    names = [name for name, _ in DIMENSIONS]

    assert "circulation" in names

    assert "fixed_elements" in names

    assert "flexible_elements" in names


def test_assemble_dimensions_omits_unknown_entries():

    assert assemble_dimensions([]) == []

    assert assemble_dimensions([{"knowledge_id": "x", "element": []}]) == []


def test_the_layer_declares_its_safety_flags():

    assert ArchitecturalReasoningQualityV1.INVENTS_KNOWLEDGE is False

    assert ArchitecturalReasoningQualityV1.GENERATES_DESIGN is False

    assert ArchitecturalReasoningQualityV1.DECIDES_FINAL_DESIGN is False

    assert architectural_reasoning_quality.CONTRACT == CONTRACT


def test_improve_reasoning_requires_a_result():

    with pytest.raises(ArchitecturalReasoningQualityError):

        improve_reasoning(None)


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
