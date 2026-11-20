"""Architectural Knowledge Classification (V1) — isolated self-checks.

Proves the classification layer:

    T1  a general statement       -> PRINCIPLE (scope Residential)
    T2  a spatial relation        -> RELATIONSHIP
    T3  a conditional change      -> EXCEPTION
    T4  a personal wish           -> PREFERENCE (never universal)
    T5  a conditional rule        -> CONTEXT_RULE
    +   a project limitation      -> CONSTRAINT
    +   the result contract, non-absolute, natural response, routing PROPOSAL
    +   no design / no memory write / no forbidden import
"""

from __future__ import annotations


import ast
from pathlib import Path

import pytest

from core.knowledge.architectural_knowledge_classification_v1 import (
    CONTRACT,
    KNOWLEDGE_TYPES,
    ArchitecturalKnowledgeClassificationError,
    ArchitecturalKnowledgeClassificationV1,
    architectural_knowledge_classification,
    build_natural_response,
    classify_knowledge,
)


MODULE = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "knowledge"
    / "architectural_knowledge_classification_v1.py"
)


SPACES = "فضاهای اصلی خانه شامل اتاق خواب، پذیرایی و آشپزخانه هستند"

RELATIONSHIP = (
    "در اتاق مستر نزدیکی حمام و کلوزت باعث کاهش مسیر حرکت و افزایش حریم می‌شود"
)

EXCEPTION = "اگر ساختمان کوچک باشد شاید حمام داخل اتاق حذف شود"

PREFERENCE = "من دوست دارم پنجره‌های بزرگ داشته باشم"

CONTEXT_RULE = (
    "راه پله در ساختمان چندطبقه باید در تمام طبقات در یک موقعیت باقی بماند"
)

CONSTRAINT = "در این زمین امکان پنجره ضلع غربی وجود ندارد"

ABSOLUTE = "حمام باید کنار کلوزت باشد"

STAIR = "راه پله عنصر ارتباط عمودی است و باکس آن در طبقات ثابت می‌ماند"


# ==========================================================
# TASK 6 — the five required sentences
# ==========================================================

def test_t1_a_general_statement_is_a_principle():

    result = classify_knowledge(SPACES)

    assert result["knowledge_type"] == "PRINCIPLE"

    assert result["applicable_scope"] == "Residential"


def test_t2_a_spatial_relation_is_a_relationship():

    assert classify_knowledge(RELATIONSHIP)["knowledge_type"] == "RELATIONSHIP"


def test_t3_a_conditional_change_is_an_exception():

    assert classify_knowledge(EXCEPTION)["knowledge_type"] == "EXCEPTION"


def test_t4_a_personal_wish_is_a_preference():

    result = classify_knowledge(PREFERENCE)

    assert result["knowledge_type"] == "PREFERENCE"

    assert result["reusability"] == "personal"

    assert result["applicable_scope"] == "CURRENT_PROJECT"


def test_t5_a_conditional_rule_is_a_context_rule():

    assert classify_knowledge(CONTEXT_RULE)["knowledge_type"] == "CONTEXT_RULE"


def test_a_project_limitation_is_a_constraint():

    result = classify_knowledge(CONSTRAINT)

    assert result["knowledge_type"] == "CONSTRAINT"

    assert result["reusability"] == "project_specific"


def test_the_seven_types_are_declared():

    assert KNOWLEDGE_TYPES == (
        "PRINCIPLE",
        "RELATIONSHIP",
        "CONSTRAINT",
        "PREFERENCE",
        "EXAMPLE",
        "EXCEPTION",
        "CONTEXT_RULE",
    )


# ==========================================================
# TASK 3 — the result contract
# ==========================================================

def test_the_result_carries_every_required_field():

    result = classify_knowledge(SPACES)

    for field in (
        "knowledge_type",
        "reasoning_basis",
        "applicable_scope",
        "context",
        "exceptions",
        "reusability",
        "memory_destination_candidate",
        "human_explanation_basis",
    ):

        assert field in result, field

    assert result["contract"] == CONTRACT

    assert result["human_explanation_basis"] == SPACES


def test_the_result_carries_no_forbidden_field():

    result = classify_knowledge(SPACES)

    for forbidden in ("confidence", "truth", "truth_status", "approval", "authority"):

        assert forbidden not in result

    assert result["non_claims"]["not_confidence"] is True

    assert result["non_claims"]["not_truth"] is True

    assert result["non_claims"]["not_authority"] is True

    assert result["non_claims"]["not_ai_approved"] is True

    assert result["non_claims"]["not_automatic_learning"] is True


# ==========================================================
# TASK 4 — non-absolute understanding
# ==========================================================

def test_a_human_absolute_is_reported_never_authored():

    result = classify_knowledge(ABSOLUTE)

    assert result["is_absolute"] is False

    assert "باید" in result["absolute_wording"]

    assert result["non_claims"]["not_an_absolute_rule"] is True


def test_a_preference_is_never_universal_knowledge():

    result = classify_knowledge(PREFERENCE)

    assert result["reusability"] == "personal"

    assert result["non_claims"]["not_an_absolute_rule"] is True


# ==========================================================
# TASK 5 — the routing PROPOSAL
# ==========================================================

def test_the_stair_teaching_is_a_principle_plus_a_context_rule():

    result = classify_knowledge(STAIR)

    assert result["knowledge_type"] == "PRINCIPLE"

    assert "CONTEXT_RULE" in result["secondary_types"]


def test_the_classifier_proposes_paths_but_writes_nothing():

    result = classify_knowledge(STAIR)

    paths = result["memory_destination_candidate"]

    assert "Global/Circulation/Vertical_Circulation" in paths

    assert "Building_Types/Residential/Multi_Floor" in paths

    # a PROPOSAL only — no memory was written
    assert result["memory_written"] is False

    assert result["non_claims"]["does_not_write_memory"] is True


def test_an_unknown_space_is_only_proposed():

    result = classify_knowledge("تخت یکی از عناصر اصلی اتاق خواب است")

    assert "bed" in result["pending_category_proposals"]


# ==========================================================
# TASK 7 — the natural response
# ==========================================================

def test_the_natural_response_is_not_a_schema():

    response = classify_knowledge(RELATIONSHIP)["natural_response"]

    assert "برداشت من از آموزش شما" in response

    for schema_word in ("Knowledge Type", "Element:", "knowledge_type", "JSON", "فیلد"):

        assert schema_word not in response


def test_the_natural_response_names_the_type_and_the_context():

    response = classify_knowledge(RELATIONSHIP)["natural_response"]

    assert "رابطه" in response


def test_build_natural_response_has_english():

    result = classify_knowledge(RELATIONSHIP)

    assert "spatial relationship" in build_natural_response(result, language="en")


# ==========================================================
# input flexibility
# ==========================================================

def test_the_classifier_accepts_an_extraction_candidate():

    from core.knowledge.architectural_knowledge_extraction_engine_v1 import (
        extract_architectural_knowledge_candidate_v1 as extract,
    )

    candidate = extract(SPACES)

    assert candidate is not None

    result = classify_knowledge(candidate)

    assert result["knowledge_type"] == "PRINCIPLE"


def test_the_classifier_rejects_a_foreign_contract():

    with pytest.raises(ArchitecturalKnowledgeClassificationError):

        classify_knowledge({"contract": "SomethingElseV1"})


def test_the_classifier_rejects_an_empty_statement():

    with pytest.raises(ArchitecturalKnowledgeClassificationError):

        classify_knowledge("   ")


# ==========================================================
# no design / no memory write
# ==========================================================

def test_the_layer_never_creates_a_design_or_writes_memory():

    assert ArchitecturalKnowledgeClassificationV1.CREATES_DESIGN is False

    assert ArchitecturalKnowledgeClassificationV1.WRITES_MEMORY is False

    assert architectural_knowledge_classification.CONTRACT == CONTRACT

    result = classify_knowledge(SPACES)

    assert result["design_generated"] is False

    assert result["memory_written"] is False


def test_the_result_carries_no_geometry_or_design():

    result = classify_knowledge(SPACES)

    payload = str(result).lower()

    for forbidden in ("geometry", "polygon", "cad", "bim", "ifc", "render"):

        assert forbidden not in payload.replace("not_geometry", "").replace("not_cad_or_bim", "")


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
