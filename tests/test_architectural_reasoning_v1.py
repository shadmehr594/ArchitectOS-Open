"""Architectural Design Reasoning (V1) — isolated self-checks.

Proves the reasoning engine (`core/knowledge/architectural_reasoning_v1.py`):

    T1  a small master bedroom   -> the closet is NOT forced
    T2  a fixed stair location   -> moving the stair is REFUSED
    T3  a large master bedroom   -> the closet CAN be considered
    T4  contradictory requirements -> the conflict is REPORTED
    T5  a user preference        -> it influences, it does not become a rule
    +   the contract, the priority system, the natural reasoning,
        no geometry / no plan / no final decision / no forbidden import

NOTE: this module is DISTINCT from the legacy
`core/design/design_reasoning/architectural_design_reasoning_v1.py`
(contract `ArchitecturalDesignReasoningResultV1`), which is a different engine.
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

from core.knowledge.architectural_reasoning_v1 import (
    CONTRACT,
    FIXED_TOKENS,
    FLEXIBLE_TOKENS,
    PRIORITY_BY_TOKEN,
    PRIORITY_ESSENTIAL,
    PRIORITY_OPTIONAL,
    PRIORITY_ORDER,
    PRIORITY_QUALITY,
    PRIORITY_SAFETY,
    ArchitecturalDesignReasoningV1,
    build_natural_reasoning,
    reason_design,
)


MODULE = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "knowledge"
    / "architectural_reasoning_v1.py"
)


CLOSET_BATH = (
    "The bathroom and the closet should be near each other because it "
    "improves privacy."
)


def _memory_with_closet_knowledge():

    mem = ArchitecturalKnowledgeMemoryV1()

    candidate = extract(CLOSET_BATH)

    assert candidate is not None

    review = open_review(candidate)

    review.confirm()

    mem.add_confirmed_entry(review.to_confirmed_entry())

    return mem


def _retrieval(mem):

    return retrieve("رابطه حمام و کلوزت", mem)


# ==========================================================
# TASK 8 / TEST 1 — a small master bedroom
# ==========================================================

def test_t1_a_small_bedroom_does_not_force_a_closet():

    mem = _memory_with_closet_knowledge()

    result = reason_design(
        {"topic": "closet", "area_limitation": True, "building_type": "Residential"},
        retrieval=_retrieval(mem),
    )

    kinds = [c["kind"] for c in result["conflicts"]]

    assert "area_limitation" in kinds

    assert "priority_rule" in kinds

    assert [d["kind"] for d in result["decisions"]] == ["keep_essential"]

    # it never forces the optional feature: every "باید" is part of a GUARD
    # ("نباید" = must not), never a mandate for the feature
    text = result["natural_reasoning"]

    assert text.count("باید") == text.count("نباید")

    assert "closet must" not in text.lower()

    assert "always" not in text.lower()


def test_t1_alternatives_are_offered():

    mem = _memory_with_closet_knowledge()

    result = reason_design(
        {"topic": "closet", "area_limitation": True}, retrieval=_retrieval(mem)
    )

    labels = [a["label"] for a in result["alternatives"]]

    assert "Independent closet" in labels

    assert "Built-in wardrobe" in labels

    assert any("No closet" in label for label in labels)


# ==========================================================
# TASK 8 / TEST 2 — a fixed stair location
# ==========================================================

def test_t2_moving_a_fixed_stair_is_refused():

    mem = _memory_with_closet_knowledge()

    result = reason_design(
        {
            "topic": "stair",
            "requested_modifications": [{"target": "stair", "reason": "closet"}],
            "fixed_elements": ["stair"],
        },
        retrieval=_retrieval(mem),
    )

    kinds = [c["kind"] for c in result["conflicts"]]

    assert "fixed_vs_flexible" in kinds

    assert any(d["kind"] == "fixed_untouched" for d in result["decisions"])

    # the fixed element is declared fixed, the need is declared flexible
    assert "stair" in FIXED_TOKENS

    assert "closet" in FLEXIBLE_TOKENS


def test_t2_no_alternative_touches_the_stair():

    mem = _memory_with_closet_knowledge()

    result = reason_design(
        {"requested_modifications": [{"target": "stair", "reason": "storage"}]},
        retrieval=_retrieval(mem),
    )

    for alternative in result["alternatives"]:

        assert "stair" not in str(alternative).lower()


# ==========================================================
# TASK 8 / TEST 3 — a large master bedroom
# ==========================================================

def test_t3_a_large_bedroom_can_consider_the_closet():

    mem = _memory_with_closet_knowledge()

    result = reason_design(
        {"topic": "closet", "area_limitation": False}, retrieval=_retrieval(mem)
    )

    assert result["conflicts"] == []

    assert [d["kind"] for d in result["decisions"]] == ["considerable"]


# ==========================================================
# TASK 8 / TEST 4 — contradictory requirements
# ==========================================================

def test_t4_a_contradiction_is_reported_not_solved():

    mem = _memory_with_closet_knowledge()

    result = reason_design(
        {
            "area_limitation": True,
            "user_requirements": [
                "large independent closet",
                "maximize master bedroom area",
            ],
        },
        retrieval=_retrieval(mem),
    )

    kinds = [c["kind"] for c in result["conflicts"]]

    assert "contradictory_requirements" in kinds

    # it never invents a solution, and the human decides
    assert result["human_review_required"] is True

    assert result["is_final_solution"] is False


# ==========================================================
# TASK 8 / TEST 5 — a user preference
# ==========================================================

def test_t5_a_preference_influences_but_does_not_become_a_rule():

    mem = _memory_with_closet_knowledge()

    result = reason_design(
        {"user_requirements": ["I prefer large windows"]},
        retrieval=_retrieval(mem),
    )

    kinds = [d["kind"] for d in result["decisions"]]

    assert "preference" in kinds

    assert result["is_final_solution"] is False

    assert result["non_claims"]["not_a_rule"] is True


# ==========================================================
# TASK 3 — the priority system
# ==========================================================

def test_the_priority_order_is_declared():

    assert PRIORITY_ORDER == (
        "SAFETY",
        "ESSENTIAL_FUNCTION",
        "SPATIAL_QUALITY",
        "OPTIONAL_FEATURE",
    )

    assert PRIORITY_BY_TOKEN["stair"] == PRIORITY_SAFETY

    assert PRIORITY_BY_TOKEN["bathroom"] == PRIORITY_ESSENTIAL

    assert PRIORITY_BY_TOKEN["privacy"] == PRIORITY_QUALITY

    assert PRIORITY_BY_TOKEN["closet"] == PRIORITY_OPTIONAL


# ==========================================================
# TASK 2 — the contract
# ==========================================================

def test_the_result_carries_every_required_field():

    result = reason_design(
        {"topic": "closet"}, retrieval=_retrieval(_memory_with_closet_knowledge())
    )

    for field in (
        "decisions",
        "reasoning_basis",
        "used_knowledge",
        "conflicts",
        "trade_offs",
        "alternatives",
        "unresolved_questions",
        "human_review_required",
    ):

        assert field in result, field

    assert result["contract"] == CONTRACT


def test_the_result_carries_no_forbidden_field():

    result = reason_design(
        {"topic": "closet"}, retrieval=_retrieval(_memory_with_closet_knowledge())
    )

    for forbidden in (
        "confidence", "truth", "final_solution", "geometry", "coordinates", "dimensions",
    ):

        assert forbidden not in result

    assert result["human_review_required"] is True

    assert result["is_final_solution"] is False

    assert result["non_claims"]["not_a_final_solution"] is True

    assert result["non_claims"]["not_geometry"] is True


def test_the_reasoning_never_emits_geometry():

    result = reason_design(
        {"requested_modifications": [{"target": "structure", "reason": "furniture"}]},
        retrieval=_retrieval(_memory_with_closet_knowledge()),
    )

    payload = str(result).lower()

    for forbidden in ("geometry", "polygon", "coordinate", "dimension", "cad", "bim", "ifc"):

        assert forbidden not in payload.replace("not_geometry", "").replace("not_cad_or_bim", "")


# ==========================================================
# TASK 7 — the natural reasoning
# ==========================================================

def test_the_natural_reasoning_is_not_json():

    result = reason_design(
        {"topic": "closet", "area_limitation": True},
        retrieval=_retrieval(_memory_with_closet_knowledge()),
    )

    text = result["natural_reasoning"]

    assert "استدلال معماری من این است" in text

    assert "تصمیم نهایی با معمار است" in text

    for marker in ("{", "}", "contract", "decisions"):

        assert marker not in text


def test_the_natural_reasoning_has_english():

    result = reason_design(
        {"topic": "closet", "area_limitation": True},
        retrieval=_retrieval(_memory_with_closet_knowledge()),
    )

    assert "architectural reasoning" in build_natural_reasoning(result, language="en")


# ==========================================================
# no design / no plan
# ==========================================================

def test_the_engine_declares_its_safety_flags():

    assert ArchitecturalDesignReasoningV1.GENERATES_GEOMETRY is False

    assert ArchitecturalDesignReasoningV1.DECIDES_FINAL_DESIGN is False

    assert ArchitecturalDesignReasoningV1.OVERRIDES_ARCHITECT is False


def test_the_engine_reasons_without_knowledge():

    result = reason_design({"topic": "unknown topic"})

    assert result["human_review_required"] is True

    assert "No confirmed knowledge covers this topic yet." in result["unresolved_questions"]


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
