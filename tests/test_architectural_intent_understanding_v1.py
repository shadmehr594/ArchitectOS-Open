"""Architectural Intent Understanding (V1) — isolated self-checks.

    T1  a natural Persian project request -> intent extraction
    T2  requirement vs preference separation
    T3  constraint detection
    T4  priority extraction
    T5  fixed vs flexible identification
    T6  knowledge retrieval connection
    T7  conflict identification without solving
    T8  no design generation
    T9  no geometry output
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

from core.knowledge.architectural_intent_understanding_v1 import (
    BUILDING_TYPE_SURFACE,
    CONTRACT,
    ArchitecturalIntentUnderstandingError,
    ArchitecturalIntentUnderstandingV1,
    architectural_intent_understanding,
    build_natural_understanding,
    understand_intent,
)


MODULE = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "knowledge"
    / "architectural_intent_understanding_v1.py"
)


FAMILY_REQUEST = (
    "یک خانه کوچک برای خانواده ۴ نفره می‌خواهم، نور خوب داشته باشد، "
    "حریم مناسب باشد و پارکینگ هم داشته باشد."
)

DUPLEX_REQUEST = (
    "یه خانه دوبلکس می‌خوام برای خانواده با دو بچه، آشپزخانه بزرگ، حریم خوب و نور زیاد."
)

REQUIREMENT = "پارکینگ لازم است"
CONSTRAINT = "زمین کوچک است"
PREFERENCE = "آشپزخانه بزرگ دوست دارم"
PRIORITY = "راه پله باید ارتباط طبقات را حفظ کند"

CONFLICT_REQUEST = (
    "یک خانه کوچک می‌خواهم، کلوزت بزرگ داشته باشد، پارکینگ لازم است و نور زیاد داشته باشد."
)


def memory_with_knowledge():

    memory = ArchitecturalKnowledgeMemoryV1()

    for text in (
        "راه پله عنصر ارتباط عمودی است.\nباکس راه پله در طبقات ثابت می‌ماند.",
        "نزدیکی حمام و کلوزت باعث کاهش مسیر حرکت و افزایش حفظ حریم می‌شود.",
        "فضاهای اصلی خانه نیاز به نورگیری دارند.",
    ):

        candidate = extract(text, turn_kind="TEACHING_STATEMENT")

        assert candidate is not None

        review = open_review(candidate)

        review.confirm()

        memory.add_confirmed_entry(review.to_confirmed_entry())

    return memory


# ==========================================================
# T1 — a natural Persian project request
# ==========================================================

def test_t1_a_natural_request_yields_an_intent():

    result = understand_intent(FAMILY_REQUEST)

    assert result["intent"]["building_type"] == "residential"

    assert result["intent"]["household"]["size"] == 4

    assert "parking" in result["intent"]["program"]


def test_t1_a_duplex_request_is_read_as_a_duplex():

    result = understand_intent(DUPLEX_REQUEST)

    assert result["intent"]["building_type"] == "duplex"

    assert result["intent"]["household"]["children"] == 2


def test_t1_no_form_and_no_json_is_required():

    result = understand_intent(FAMILY_REQUEST)

    text = result["natural_understanding"]

    assert isinstance(text, str)

    assert "برداشت من از درخواست شما" in text

    for marker in ("{", "}", "contract", "intent"):

        assert marker not in text


# ==========================================================
# T2 — requirement vs preference
# ==========================================================

def test_t2_a_requirement_and_a_preference_are_separated():

    requirement = understand_intent(REQUIREMENT)

    preference = understand_intent(PREFERENCE)

    assert requirement["requirement"]

    assert requirement["preference"] == []

    assert preference["preference"]

    assert preference["requirement"] == []


def test_t2_the_family_request_keeps_parking_as_a_requirement():

    result = understand_intent(FAMILY_REQUEST)

    assert result["requirement"]

    assert any("پارکینگ" in clause for clause in result["requirement"])


# ==========================================================
# T3 — constraint detection
# ==========================================================

def test_t3_a_small_site_is_a_constraint():

    result = understand_intent(CONSTRAINT)

    assert result["constraint"]

    assert result["requirement"] == []


def test_t3_the_small_house_is_a_constraint():

    result = understand_intent(FAMILY_REQUEST)

    assert result["constraint"]

    assert any("کوچک" in clause for clause in result["constraint"])


# ==========================================================
# T4 — priority extraction
# ==========================================================

def test_t4_privacy_and_lighting_are_priorities():

    result = understand_intent(FAMILY_REQUEST)

    text = " ".join(result["priority"])

    assert "نور" in text

    assert "حریم" in text


# ==========================================================
# T5 — fixed vs flexible
# ==========================================================

def test_t5_a_stair_is_fixed_and_a_closet_is_flexible():

    fixed = understand_intent(PRIORITY)

    assert "stair" in fixed["fixed_elements"]

    flexible = understand_intent("کلوزت بزرگ دوست دارم")

    assert "closet" in flexible["flexible_elements"]


# ==========================================================
# T6 — knowledge retrieval connection
# ==========================================================

def test_t6_the_intent_connects_to_confirmed_knowledge():

    memory = memory_with_knowledge()

    result = understand_intent("خانه کوچک با حریم بالا", memory=memory)

    assert result["retrieval_ids"]

    dimensions = {d["dimension"] for d in result["dimensions"]}

    assert "privacy" in dimensions


def test_t6_no_memory_still_understands_the_request():

    result = understand_intent(FAMILY_REQUEST)

    assert result["retrieval_ids"] == []

    assert result["intent"]["building_type"] == "residential"


# ==========================================================
# T7 — conflict identification without solving
# ==========================================================

def test_t7_a_conflict_is_identified_not_solved():

    memory = memory_with_knowledge()

    result = understand_intent(CONFLICT_REQUEST, memory=memory)

    kinds = {c["kind"] for c in result["conflicts"]}

    assert "area_limitation" in kinds

    # the conflict is REPORTED — the decision stays with the architect
    assert result["human_review_required"] is True

    assert result["is_final_solution"] is False


# ==========================================================
# T8 — no design generation
# ==========================================================

def test_t8_no_design_is_generated():

    memory = memory_with_knowledge()

    result = understand_intent(FAMILY_REQUEST, memory=memory)

    assert result["design_generated"] is False

    assert result["is_final_solution"] is False

    assert result["non_claims"]["not_a_design"] is True

    assert result["non_claims"]["not_a_plan"] is True


# ==========================================================
# T9 — no geometry output
# ==========================================================

def test_t9_no_geometry_is_emitted():

    memory = memory_with_knowledge()

    result = understand_intent(FAMILY_REQUEST, memory=memory)

    # scan the CONTENT — not the field name `dimensions` (an architectural
    # dimension grouping, not a geometric dimension) nor the non-claim keys
    payload = " ".join(
        str(result[key])
        for key in (
            "requirement", "constraint", "preference", "priority",
            "fixed_elements", "flexible_elements", "natural_understanding",
        )
    ).lower()

    for forbidden in ("geometry", "polygon", "coordinate", "cad", "bim", "ifc"):

        assert forbidden not in payload


def test_t9_the_layer_declares_its_safety_flags():

    assert ArchitecturalIntentUnderstandingV1.GENERATES_DESIGN is False

    assert ArchitecturalIntentUnderstandingV1.GENERATES_GEOMETRY is False

    assert ArchitecturalIntentUnderstandingV1.DECIDES_FINAL_DESIGN is False

    assert architectural_intent_understanding.CONTRACT == CONTRACT


# ==========================================================
# the contract + helpers
# ==========================================================

def test_the_contract_carries_every_required_field():

    result = understand_intent(FAMILY_REQUEST)

    for field in (
        "intent", "requirement", "constraint", "preference", "priority",
        "fixed_elements", "flexible_elements", "retrieved_knowledge",
        "conflicts", "human_review_required", "natural_understanding",
    ):

        assert field in result, field

    assert result["contract"] == CONTRACT


def test_an_empty_request_is_rejected():

    with pytest.raises(ArchitecturalIntentUnderstandingError):

        understand_intent("   ")


def test_the_natural_understanding_has_english():

    result = understand_intent(FAMILY_REQUEST)

    assert "my reading of your request" in build_natural_understanding(result, language="en")


def test_the_building_type_vocabulary_is_declared():

    assert BUILDING_TYPE_SURFACE["دوبلکس"] == "duplex"

    assert BUILDING_TYPE_SURFACE["ویلا"] == "villa"

    assert BUILDING_TYPE_SURFACE["خانه"] == "residential"


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
