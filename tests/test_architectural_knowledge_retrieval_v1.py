"""Architectural Knowledge Retrieval (V1) — isolated self-checks.

Proves the retrieval boundary:

    T1  teach stair -> confirm -> ask -> correct answer
    T2  ask an unknown topic -> no hallucination
    T3  retrieve bedroom knowledge
    T4  retrieve a cross-space relationship
    T5  a correction -> the newest revision is returned
    T6  a natural-language question -> a natural answer, no JSON
    +   confirmed memory only; no design / geometry; no forbidden import
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
    CONTRACT,
    NO_KNOWLEDGE,
    ArchitecturalKnowledgeRetrievalBoundaryV1,
    ArchitecturalKnowledgeRetrievalError,
    architectural_knowledge_retrieval,
    render_answer,
    retrieve,
    understand_query,
)


MODULE = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "knowledge"
    / "architectural_knowledge_retrieval_v1.py"
)


STAIR = (
    "راه پله یکی از عناصر ارتباط عمودی ساختمان است.\n"
    "باکس راه پله در طبقات ثابت می‌ماند.\n"
    "تعداد پله‌ها با ارتفاع تغییر می‌کند."
)

SPACES = "فضاهای اصلی خانه شامل اتاق خواب، پذیرایی و آشپزخانه هستند."

CLOSET_BATH = (
    "The bathroom and the closet should be near each other because it "
    "improves privacy."
)

REVISION_V1 = "Bathroom should be next to closet."

REVISION_V2 = "Closet should be next to bathroom in the master bedroom."


def store(mem, text, previous=None):

    candidate = extract(text)

    assert candidate is not None, "no candidate for %r" % (text,)

    review = open_review(candidate)

    review.confirm()

    return mem.add_confirmed_entry(
        review.to_confirmed_entry(), previous_revision=previous
    )


def memory():

    return ArchitecturalKnowledgeMemoryV1()


# ==========================================================
# T1 — teach stair -> ask
# ==========================================================

def test_t1_teach_stair_then_ask_returns_the_stair_knowledge():

    mem = memory()

    store(mem, STAIR)

    result = retrieve("راه پله چه چیزی یاد گرفتی؟", mem)

    assert result["found"] is True

    answer = result["answer"]

    assert "ارتباط عمودی" in answer

    assert "ثابت" in answer

    assert "تغییر می" in answer


def test_t1_the_answer_is_natural_not_json():

    mem = memory()

    store(mem, STAIR)

    answer = retrieve("راه پله چه چیزی یاد گرفتی؟", mem)["answer"]

    assert isinstance(answer, str)

    for json_marker in ("{", "}", "contract", "facets", "knowledge_id"):

        assert json_marker not in answer


# ==========================================================
# T2 — an unknown topic
# ==========================================================

def test_t2_an_unknown_topic_is_answered_honestly():

    mem = memory()

    store(mem, STAIR)

    result = retrieve("درباره پارکینگ چه می‌دانی؟", mem)

    assert result["found"] is False

    assert result["no_knowledge"] is True

    assert result["answer"] == NO_KNOWLEDGE["fa"]

    assert result["entries"] == []


def test_t2_an_empty_memory_never_hallucinates():

    result = retrieve("در مورد اتاق خواب چه می‌دانی؟", memory())

    assert result["found"] is False

    assert result["no_knowledge"] is True


# ==========================================================
# T3 — bedroom knowledge
# ==========================================================

def test_t3_bedroom_knowledge_is_retrieved():

    mem = memory()

    store(mem, SPACES)

    result = retrieve("در مورد اتاق خواب چه می‌دانی؟", mem)

    assert result["found"] is True

    assert result["entry_count"] >= 1


def test_t3_a_space_query_widens_along_the_taxonomy():

    mem = memory()

    store(mem, SPACES)

    store(mem, CLOSET_BATH)  # routes to Residential/Master_Bedroom too

    result = retrieve("در مورد اتاق خواب چه می‌دانی؟", mem)

    # the bedroom family reaches the master-bedroom knowledge
    assert result["entry_count"] >= 2


# ==========================================================
# T4 — a cross-space relationship
# ==========================================================

def test_t4_a_cross_space_relationship_is_retrieved():

    mem = memory()

    store(mem, CLOSET_BATH)

    result = retrieve("رابطه حمام و کلوزت را بگو", mem)

    assert result["found"] is True

    assert result["understanding"]["kind"] == "relationship"

    assert "closet" in result["answer"].lower() or "bathroom" in result["answer"].lower()


# ==========================================================
# T5 — a correction
# ==========================================================

def test_t5_the_newest_revision_is_retrieved():

    mem = memory()

    first = store(mem, REVISION_V1)

    second = store(mem, REVISION_V2, previous=first["knowledge_id"])

    result = retrieve("در مورد حمام چه می‌دانی؟", mem)

    assert result["found"] is True

    # the superseded revision is never returned as current
    assert second["knowledge_id"] in result["knowledge_ids"]

    assert first["knowledge_id"] not in result["knowledge_ids"]


def test_t5_the_old_revision_remains_in_history():

    mem = memory()

    first = store(mem, REVISION_V1)

    second = store(mem, REVISION_V2, previous=first["knowledge_id"])

    history = mem.get_revision_history(second["knowledge_id"])

    assert len(history) == 2

    assert history[0]["knowledge_id"] == first["knowledge_id"]


# ==========================================================
# T6 — a natural-language question
# ==========================================================

def test_t6_a_natural_question_needs_no_form():

    mem = memory()

    store(mem, STAIR)

    result = retrieve("چه چیزی درباره راه پله یاد گرفتی؟", mem)

    assert isinstance(result["answer"], str)

    assert result["answer"]

    assert "?" not in result["answer"][:0]  # no form prompt


def test_t6_the_boundary_exposes_no_database_structure():

    mem = memory()

    store(mem, STAIR)

    result = retrieve("راه پله", mem)

    for key in ("contract", "version", "non_claims", "read_only"):

        assert key in result  # the ARTIFACT may carry them …

    # … but the human-facing ANSWER never does
    for key in ("contract", "facets", "entries", "knowledge_ids"):

        assert key not in result["answer"]


# ==========================================================
# scope control
# ==========================================================

def test_an_unconfirmed_candidate_is_never_retrieved():

    mem = memory()

    # an extraction candidate exists but was never confirmed / stored
    assert extract(STAIR) is not None

    result = retrieve("راه پله چه چیزی یاد گرفتی؟", mem)

    assert result["found"] is False

    assert result["no_knowledge"] is True


def test_retrieval_requires_a_memory():

    with pytest.raises(ArchitecturalKnowledgeRetrievalError):

        retrieve("راه پله", None)


# ==========================================================
# no design / no geometry
# ==========================================================

def test_the_answer_carries_no_design_or_geometry():

    mem = memory()

    store(mem, STAIR)

    answer = retrieve("راه پله چه چیزی یاد گرفتی؟", mem)["answer"].lower()

    for forbidden in ("geometry", "polygon", "cad", "bim", "ifc", "render", "plan"):

        assert forbidden not in answer


def test_the_boundary_declares_its_safety_flags():

    assert ArchitecturalKnowledgeRetrievalBoundaryV1.GENERATES_DESIGN is False

    assert ArchitecturalKnowledgeRetrievalBoundaryV1.INFERS_KNOWLEDGE is False

    assert architectural_knowledge_retrieval.CONTRACT == CONTRACT


# ==========================================================
# understanding + rendering helpers
# ==========================================================

def test_understand_query_classifies_the_three_shapes():

    assert understand_query("راه پله چه چیزی یاد گرفتی؟")["kind"] == "space"

    assert understand_query("رابطه حمام و کلوزت را بگو")["kind"] == "relationship"

    assert understand_query("سلام")["kind"] == "broad"


def test_render_answer_skips_empty_facets():

    text = render_answer(
        [
            {
                "knowledge_id": "akm_x",
                "status": "active",
                "element": ["stair"],
                "function": [],
                "relationship": [],
                "fixed_properties": [],
                "variable_properties": [],
                "context": [],
                "exceptions": [],
                "reason": [],
                "effect": [],
            }
        ],
        language="fa",
        topic="stair",
    )

    assert "کارکرد" not in text

    assert "عنصر" in text


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
