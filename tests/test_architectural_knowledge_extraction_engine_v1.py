"""Architectural Knowledge Extraction Engine (V1) — isolated self-checks.

Proves the engine:

    1. activates ONLY for a teaching statement / correction
    2. extracts the structured facets (element / function / relationship /
       fixed / variable / context / exceptions / reason / effect)
    3. never invents a missing facet
    4. never converts a preference into an absolute rule
    5. produces a CANDIDATE only (no memory, no design, no geometry)
    6. is deterministic and keeps the human's words verbatim
    7. imports no vision / render / cad / bim / geometry / runtime module
"""

from __future__ import annotations


import ast
from pathlib import Path

import pytest

from core.knowledge.architectural_knowledge_extraction_engine_v1 import (
    CONTRACT,
    FACET_KEYS,
    TEACHING_TURN_KINDS,
    ArchitecturalKnowledgeExtractionEngineV1,
    architectural_knowledge_extraction_engine,
    extract_architectural_knowledge_candidate_v1,
)


MODULE = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "knowledge"
    / "architectural_knowledge_extraction_engine_v1.py"
)


# ----------------------------------------------------------
# the checkpoint's inputs
# ----------------------------------------------------------

SPACES = "فضاهای اصلی خانه شامل اتاق خواب، پذیرایی و آشپزخانه هستند."

STAIR = (
    "راه پله یکی از عناصر ارتباط عمودی در ساختمان است.\n"
    "باکس راه پله در طبقات ثابت می‌ماند.\n"
    "تعداد پله‌ها با ارتفاع ساختمان تغییر می‌کند."
)

CLOSET_BATH = (
    "حمام و کلوزت نزدیک هم باشند بهتره چون مسیر حرکت کمتر میشه و حریم حفظ میشه."
)

QUESTION = "ابعاد استاندارد اتاق خواب چقدر است؟"

DESIGN_REQUEST = "یک خانه ۱۰ در ۲۰ برای من طراحی کن"

CORRECTION = "نه، برای همه پروژه‌ها نیست. در ساختمان کوچک ممکن است متفاوت باشد."

PREFERENCE = "حمام و کلوزت نزدیک هم باشند بهتره"


def _text(candidate, key):

    return " ".join(str(v) for v in candidate.get(key) or [])


# ==========================================================
# TASK 7 / T1 — the spaces example
# ==========================================================

def test_t1_spaces_extracts_elements_and_residential_context():

    candidate = extract_architectural_knowledge_candidate_v1(SPACES)

    assert candidate is not None

    elements = candidate["element"]

    assert "bedroom" in elements

    assert "living" in elements

    assert "kitchen" in elements

    assert "residential" in candidate["context"]


def test_t1_produces_no_design_output():

    candidate = extract_architectural_knowledge_candidate_v1(SPACES)

    # Scan the CONTENT the engine extracted — not the `non_claims` keys, whose
    # names literally contain the terms (e.g. `not_geometry`, `not_cad_or_bim`).
    payload = (
        " ".join(str(candidate[key]) for key in FACET_KEYS)
        + " "
        + candidate["human_basis"]
    ).lower()

    for forbidden in ("geometry", "polygon", "cad", "bim", "ifc", "render"):

        assert forbidden not in payload

    assert candidate["persistent"] is False

    assert candidate["read_only"] is True


# ==========================================================
# TASK 7 / T2 — the stair example
# ==========================================================

def test_t2_stair_extracts_the_structured_facets():

    candidate = extract_architectural_knowledge_candidate_v1(STAIR)

    assert candidate is not None

    assert "stair" in candidate["element"]

    # function — the clause that states what the stair IS FOR
    assert "ارتباط عمودی" in _text(candidate, "function")

    # fixed — the clause that states what does NOT change
    assert "ثابت" in _text(candidate, "fixed_properties")

    # variable — the clause that states what DOES change
    assert "تغییر می" in _text(candidate, "variable_properties")

    # relationship — present (from the normalised relations)
    assert candidate["relationship"]

    # every facet present is declared
    for key in candidate["facets_present"]:

        assert candidate[key]


def test_t2_does_not_add_standards_or_regulations():

    candidate = extract_architectural_knowledge_candidate_v1(STAIR)

    payload = _text(candidate, "function") + _text(candidate, "fixed_properties")

    for term in ("استاندارد", "مقررات", "ضوابط", "مبحث"):

        assert term not in payload


# ==========================================================
# TASK 7 / T3 — the closet / bathroom relationship
# ==========================================================

def test_t3_closet_bathroom_extracts_the_relationship():

    candidate = extract_architectural_knowledge_candidate_v1(CLOSET_BATH)

    assert candidate is not None

    assert candidate["relationship"]

    assert "bathroom" in candidate["element"]

    # the reason / effect of the natural "چون" clause
    assert candidate["reason"]

    assert candidate["effect"]


def test_t3_no_absolute_rule_is_created():

    candidate = extract_architectural_knowledge_candidate_v1(CLOSET_BATH)

    assert candidate["is_absolute"] is False

    # the engine authored NO absolute term anywhere in its own fields
    authored = " ".join(
        str(candidate[k])
        for k in ("candidate_kind", "status", "facets_present")
    ).lower()

    for term in ("must", "always", "required"):

        assert term not in authored

    # the non-claims declare the non-absolute rule
    assert candidate["non_claims"]["not_absolute_rule"] is True

    assert candidate["non_claims"]["not_must"] is True


def test_t3_preference_is_not_converted_to_must():

    candidate = extract_architectural_knowledge_candidate_v1(PREFERENCE)

    # the human's preference stays a preference — no absolute wording at all
    assert candidate["absolute_wording"] == []

    assert candidate["is_absolute"] is False


def test_t3_a_human_absolute_is_flagged_not_converted():

    candidate = extract_architectural_knowledge_candidate_v1(
        "کلوزت باید کنار حمام باشد"
    )

    # the human's word is reported, never converted into engine-authored text
    assert "باید" in candidate["absolute_wording"]

    assert candidate["is_absolute"] is False


# ==========================================================
# TASK 7 / T4 — the correction
# ==========================================================

def test_t4_correction_produces_a_refinement_candidate():

    candidate = extract_architectural_knowledge_candidate_v1(CORRECTION)

    assert candidate is not None

    assert candidate["candidate_kind"] == "correction"

    refinement = candidate["refinement"]

    assert refinement["narrowing"] is True

    assert refinement["deletes"] == []

    assert refinement["overwrites_silently"] is False

    assert refinement["supersedes"] is None

    # the correction captured the exception the human stated
    assert candidate["exceptions"]


# ==========================================================
# TASK 7 / T5 — a question creates no candidate
# ==========================================================

def test_t5_question_creates_no_candidate():

    assert extract_architectural_knowledge_candidate_v1(QUESTION) is None


def test_t5_design_request_creates_no_candidate():

    assert extract_architectural_knowledge_candidate_v1(DESIGN_REQUEST) is None


def test_t5_empty_or_non_string_creates_no_candidate():

    assert extract_architectural_knowledge_candidate_v1("") is None

    assert extract_architectural_knowledge_candidate_v1("   ") is None

    assert extract_architectural_knowledge_candidate_v1(None) is None

    assert extract_architectural_knowledge_candidate_v1(42) is None


def test_the_gate_accepts_an_explicit_teaching_turn_kind():

    candidate = extract_architectural_knowledge_candidate_v1(
        "اتاق خواب پنجره دارد", turn_kind="TEACHING_STATEMENT"
    )

    assert candidate is not None

    assert candidate["turn_kind"] == "TEACHING_STATEMENT"

    assert TEACHING_TURN_KINDS == ("TEACHING_STATEMENT", "CORRECTION")


# ==========================================================
# TASK 2 — the model: optional facets, never invented
# ==========================================================

def test_every_facet_key_exists_on_the_candidate():

    candidate = extract_architectural_knowledge_candidate_v1(SPACES)

    for key in FACET_KEYS:

        assert key in candidate


def test_an_absent_facet_stays_empty():

    candidate = extract_architectural_knowledge_candidate_v1(SPACES)

    # the spaces statement states no fixed / variable property
    assert candidate["fixed_properties"] == []

    assert candidate["variable_properties"] == []

    assert "fixed_properties" not in candidate["facets_present"]


def test_the_human_basis_is_verbatim():

    candidate = extract_architectural_knowledge_candidate_v1(STAIR)

    assert candidate["human_basis"] == STAIR


# ==========================================================
# TASK 6 — candidate only
# ==========================================================

def test_the_candidate_is_not_permanent_knowledge():

    candidate = extract_architectural_knowledge_candidate_v1(SPACES)

    assert candidate["status"] == "proposed"

    assert candidate["persistent"] is False

    assert candidate["non_claims"]["not_permanent_knowledge"] is True


def test_the_contract_is_distinct_from_the_vision_candidate():

    # the vision-side rich candidate already owns this name
    from core.knowledge.architectural_knowledge_v1 import (
        CONTRACT as VISION_CONTRACT,
    )

    assert CONTRACT == "ArchitecturalKnowledgeExtractionCandidateV1"

    assert CONTRACT != VISION_CONTRACT


def test_the_engine_never_writes_memory():

    source = MODULE.read_text(encoding="utf-8")

    for forbidden in ("promote(", "knowledge_memory", "permanent_knowledge_store"):

        assert forbidden not in source


# ==========================================================
# determinism + the class API
# ==========================================================

def test_the_engine_is_deterministic():

    first = extract_architectural_knowledge_candidate_v1(STAIR)

    second = extract_architectural_knowledge_candidate_v1(STAIR)

    assert first == second


def test_the_class_api_matches_the_function():

    candidate = architectural_knowledge_extraction_engine.extract(STAIR)

    assert candidate == extract_architectural_knowledge_candidate_v1(STAIR)

    assert ArchitecturalKnowledgeExtractionEngineV1.LLM_USED is False

    assert ArchitecturalKnowledgeExtractionEngineV1.NETWORK_USED is False


# ==========================================================
# dependency direction
# ==========================================================

def test_the_engine_imports_no_forbidden_package():

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
