"""Architectural Knowledge Memory (V1) — isolated self-checks.

Proves the memory layer:

    1. a CONFIRMED entry enters memory
    2. an UNCONFIRMED candidate cannot
    3. routing places an item on one or more taxonomy paths
    4. a correction keeps BOTH revisions
    5. no absolute rule is stored
    6. an unknown category becomes a PENDING proposal only
    7. the read API works and nothing else is stored
    8. imports no vision / render / cad / bim / geometry / runtime module
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
    CONTRACT,
    REQUIRED_FIELDS,
    TAXONOMY,
    ArchitecturalKnowledgeMemoryError,
    ArchitecturalKnowledgeMemoryV1,
    build_memory_entry,
    route_confirmed_entry,
    taxonomy_paths,
)


MODULE = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "knowledge"
    / "architectural_knowledge_memory_v1.py"
)


# ----------------------------------------------------------
# the checkpoint's inputs
# ----------------------------------------------------------

STAIR = (
    "راه پله یکی از عناصر ارتباط عمودی ساختمان است.\n"
    "باکس راه پله در طبقات ثابت می‌ماند."
)

MASTER_BEDROOM = (
    "The bathroom and the closet should be near each other because it "
    "improves privacy."
)

ABSOLUTE = "Closet must always be next to bathroom."

REVISION_V1 = "Bathroom should be next to closet."

REVISION_V2 = "Closet should be next to bathroom in the master bedroom."

UNKNOWN_SPACE = "تخت یکی از عناصر اصلی اتاق خواب است."


def confirmed_entry(text):

    """Run the real pipeline: extract -> review -> confirm."""

    candidate = extract(text)

    assert candidate is not None, "the engine produced no candidate for %r" % (text,)

    review = open_review(candidate)

    review.confirm()

    return review.to_confirmed_entry()


def memory():

    return ArchitecturalKnowledgeMemoryV1()  # in-memory (isolated)


def memory_entry(text, *, mem=None):

    """The MEMORY entry produced by storing a confirmed entry."""

    mem = mem or memory()

    return mem.add_confirmed_entry(confirmed_entry(text))


# ==========================================================
# TASK 8 / TEST 1 — confirmed teaching enters memory
# ==========================================================

def test_test1_confirmed_teaching_is_stored():

    mem = memory()

    entry = mem.add_confirmed_entry(confirmed_entry(STAIR))

    assert mem.count() == 1

    assert entry["knowledge_id"].startswith("akm_")

    assert entry["status"] == "active"

    assert entry["revision"] == 1


# ==========================================================
# TASK 8 / TEST 2 — unconfirmed cannot enter
# ==========================================================

def test_test2_an_unconfirmed_candidate_is_rejected():

    mem = memory()

    candidate = extract(STAIR)  # status = proposed

    with pytest.raises(ArchitecturalKnowledgeMemoryError):

        mem.add_confirmed_entry(candidate)

    assert mem.count() == 0


def test_test2_a_none_entry_is_rejected():

    mem = memory()

    with pytest.raises(ArchitecturalKnowledgeMemoryError):

        mem.add_confirmed_entry(None)


def test_test2_a_foreign_contract_is_rejected():

    mem = memory()

    with pytest.raises(ArchitecturalKnowledgeMemoryError):

        mem.add_confirmed_entry({"contract": "SomethingElseV1", "status": "confirmed"})


# ==========================================================
# TASK 8 / TEST 3 — master bedroom routing
# ==========================================================

def test_test3_master_bedroom_knowledge_routes_to_all_paths():

    entry = confirmed_entry(MASTER_BEDROOM)

    routing = route_confirmed_entry(entry)

    paths = set(routing["paths"])

    assert "Residential/Master_Bedroom" in paths

    assert "Residential/Bathroom" in paths

    assert "Cross_Space_Relationships" in paths

    assert "Global/Privacy" in paths


def test_test3_an_item_may_belong_to_multiple_paths():

    entry = confirmed_entry(MASTER_BEDROOM)

    assert len(entry["facets_present"]) >= 2

    assert len(route_confirmed_entry(entry)["paths"]) >= 2


# ==========================================================
# TASK 8 / TEST 4 — a correction keeps history
# ==========================================================

def test_test4_a_correction_keeps_both_revisions():

    mem = memory()

    first = mem.add_confirmed_entry(confirmed_entry(REVISION_V1))

    second = mem.add_confirmed_entry(
        confirmed_entry(REVISION_V2),
        previous_revision=first["knowledge_id"],
    )

    # both revisions exist
    assert mem.count() == 2

    assert first["status"] == "superseded"

    assert first["superseded_by"] == second["knowledge_id"]

    assert second["previous_revision"] == first["knowledge_id"]

    assert second["revision"] == 2

    # the whole history is retrievable
    history = mem.get_revision_history(second["knowledge_id"])

    assert len(history) == 2

    assert history[0]["knowledge_id"] == first["knowledge_id"]

    assert history[1]["knowledge_id"] == second["knowledge_id"]


def test_test4_an_unknown_previous_revision_is_rejected():

    mem = memory()

    with pytest.raises(ArchitecturalKnowledgeMemoryError):

        mem.add_confirmed_entry(
            confirmed_entry(REVISION_V1), previous_revision="akm_missing"
        )


# ==========================================================
# TASK 8 / TEST 5 — no absolute rule
# ==========================================================

def test_test5_an_absolute_statement_is_stored_as_contextual():

    entry = memory_entry(ABSOLUTE)

    # the human's own words are kept, but the memory never makes a law
    assert entry["is_absolute"] is False

    assert "must" in entry["absolute_wording"] or "always" in entry["absolute_wording"]

    assert entry["non_claims"]["not_absolute_rule"] is True


def test_test5_context_is_stored_on_the_memory_entry():

    entry = memory_entry(STAIR)

    # the active space is stored as context, never as a universal rule
    assert entry["context"]

    assert entry["is_absolute"] is False


# ==========================================================
# TASK 8 / TEST 6 — a new unknown category
# ==========================================================

def test_test6_an_unknown_space_becomes_a_pending_proposal():

    entry = memory_entry(UNKNOWN_SPACE)

    # the known space routes; the unknown one is PROPOSED, never added
    assert "Residential/Bedroom" in entry["category_path"]

    assert "bed" in entry["pending_category_proposals"]

    assert "bed" not in taxonomy_paths()


def test_test6_a_pending_proposal_is_not_in_the_taxonomy():

    mem = memory()

    mem.add_confirmed_entry(confirmed_entry(UNKNOWN_SPACE))

    proposals = mem.pending_category_proposals()

    assert "bed" in proposals

    for proposal in proposals:

        assert proposal not in taxonomy_paths()


# ==========================================================
# TASK 1 — the memory-entry contract
# ==========================================================

def test_the_entry_carries_every_required_field():

    entry = memory_entry(STAIR)

    for field in REQUIRED_FIELDS:

        assert field in entry, field

    assert entry["contract"] == CONTRACT

    assert entry["human_explanation_basis"] == STAIR


def test_the_entry_carries_no_confidence_truth_or_authority():

    entry = memory_entry(STAIR)

    for forbidden in ("confidence", "truth", "truth_status", "approval", "authority"):

        assert forbidden not in entry

    assert entry["non_claims"]["not_confidence"] is True

    assert entry["non_claims"]["not_truth"] is True

    assert entry["non_claims"]["not_authority"] is True

    assert entry["non_claims"]["not_automatic_learning"] is True


# ==========================================================
# TASK 2 — the taxonomy
# ==========================================================

def test_the_taxonomy_is_expandable_and_has_the_declared_top_levels():

    for top in (
        "Global",
        "Residential",
        "Commercial",
        "Mixed_Use",
        "Building_Types",
        "Cross_Space_Relationships",
    ):

        assert top in TAXONOMY

    paths = taxonomy_paths()

    assert "Global/Privacy" in paths

    assert "Residential/Master_Bedroom" in paths

    assert "Cross_Space_Relationships" in paths


# ==========================================================
# TASK 5 / 6 — context awareness + cross-space
# ==========================================================

def test_a_memory_entry_is_never_a_universal_rule():

    entry = memory_entry(STAIR)

    assert entry["is_absolute"] is False

    assert entry["non_claims"]["not_absolute_rule"] is True


def test_the_memory_refuses_geometry():

    entry = confirmed_entry(STAIR)

    entry["content"] = "the wall geometry has coordinates"

    with pytest.raises(ArchitecturalKnowledgeMemoryError):

        build_memory_entry(
            {
                "contract": entry["contract"],
                "status": "confirmed",
                "facets": {"element": ["bedroom"]},
                "human_basis": "the wall geometry has coordinates",
            }
        )


# ==========================================================
# TASK 7 — the read API
# ==========================================================

def test_the_read_api_finds_by_space_relationship_and_category():

    mem = memory()

    mem.add_confirmed_entry(confirmed_entry(MASTER_BEDROOM))

    assert mem.find_by_space("bathroom")

    assert mem.find_by_space("Residential/Bathroom")

    assert mem.find_by_relationship("near")

    assert mem.find_by_category("Global/Privacy")

    assert mem.find_by_category("No/Such/Path") == []


def test_the_memory_never_learns_from_conversation():

    assert ArchitecturalKnowledgeMemoryV1.LEARNS_FROM_CONVERSATION is False

    assert ArchitecturalKnowledgeMemoryV1.AUTO_LEARNING is False

    source = MODULE.read_text(encoding="utf-8")

    for forbidden in ("def learn", "def auto_promote", "from_conversation"):

        assert forbidden not in source


# ==========================================================
# persistence (isolated)
# ==========================================================

def test_an_isolated_memory_is_not_persistent():

    mem = memory()

    assert mem.path is None

    assert mem.to_dict()["persistent"] is False


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
            "core.runtime",
        ):

            assert not root.startswith(forbidden), root
