"""Architectural Spatial Organization Understanding (V1) — isolated self-checks.

    T1  a natural building request -> spatial organization
    T2  public / private / service classification
    T3  space relationship extraction
    T4  the master-bedroom teaching (element/relationship/reason/effect/context)
    T5  non-absolute rule protection
    T6  fixed vs flexible relationship
    T7  multi-space reasoning
    T8  conflict detection without a design decision
    T9  no geometry output
    T10 no plan generation
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

from core.knowledge.architectural_spatial_organization_v1 import (
    CONTRACT,
    FIXED_RELATIONSHIP_KINDS,
    REL_ADJACENT,
    REL_CONNECTED,
    REL_PRIVATE_TRANSITION,
    RELATIONSHIP_KINDS,
    SPATIAL_PRIORITIES,
    ZONE_RELATIONSHIP,
    ArchitecturalSpatialOrganizationError,
    ArchitecturalSpatialOrganizationV1,
    architectural_spatial_organization,
    build_natural_organization,
    classify_program,
    classify_space,
    derive_relationships,
    understand_spatial_organization,
)


MODULE = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "knowledge"
    / "architectural_spatial_organization_v1.py"
)


REQUEST = (
    "خانه کوچک برای خانواده ۴ نفره، حریم مناسب، نور خوب، پارکینگ، "
    "آشپزخانه نزدیک پذیرایی"
)

TEACHING = (
    "اتاق خواب مستر بهتر است حمام و کلوزت نزدیک هم باشند چون مسیر حرکت "
    "کمتر می‌شود و حریم حفظ می‌شود."
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
# T1 — a natural building request
# ==========================================================

def test_t1_a_request_yields_a_spatial_organization():

    result = understand_spatial_organization(REQUEST)

    assert result["zones"]

    assert result["relationships"]

    assert result["natural_organization"]


def test_t1_no_form_and_no_json_is_required():

    result = understand_spatial_organization(REQUEST)

    text = result["natural_organization"]

    assert isinstance(text, str)

    assert "سازمان فضایی" in text

    for marker in ("{", "}", "contract", "zones"):

        assert marker not in text


# ==========================================================
# T2 — public / private / service classification
# ==========================================================

def test_t2_spaces_are_classified_into_zones():

    classified = classify_program(["آشپزخانه", "پذیرایی", "پارکینگ", "اتاق خواب", "حمام"])

    zones = classified["zones"]

    assert "PUBLIC_ZONE" in zones

    assert "SEMI_PUBLIC_ZONE" in zones

    assert "PRIVATE_ZONE" in zones

    assert "SERVICE_ZONE" in zones


def test_t2_the_classification_comes_from_the_corpus_not_a_hardcoded_law():

    # the same surface resolves through the residential corpus
    assert classify_space("آشپزخانه")["space_id"] == "OPEN_KITCHEN"

    assert classify_space("آشپزخانه")["zone"] == "SEMI_PUBLIC_ZONE"

    assert classify_space("اتاق خواب")["zone"] == "PRIVATE_ZONE"


def test_t2_a_space_outside_the_corpus_is_reported_not_guessed():

    classified = classify_program(["اتاق خواب", "اسکالاتور"])

    assert classified["unclassified"]


# ==========================================================
# T3 — space relationship extraction
# ==========================================================

def test_t3_relationships_are_derived_from_the_zones():

    relationships = derive_relationships(["پذیرایی", "اتاق خواب", "آشپزخانه"])

    kinds = {r["kind"] for r in relationships}

    assert REL_ADJACENT in kinds            # living <-> kitchen (public <-> semi)

    assert "separated" in kinds             # living <-> bedroom (public <-> private)


def test_t3_a_private_service_pair_is_a_privacy_relationship():

    relationships = derive_relationships(["اتاق خواب", "حمام"])

    assert relationships

    assert relationships[0]["kind"] == REL_PRIVATE_TRANSITION


def test_t3_the_relationship_vocabulary_is_declared():

    assert RELATIONSHIP_KINDS == (
        "adjacent",
        "separated",
        "connected",
        "private_transition",
        "service_relationship",
    )


# ==========================================================
# T4 — the master-bedroom teaching
# ==========================================================

def test_t4_the_teaching_is_read_as_a_spatial_relationship():

    result = understand_spatial_organization(TEACHING)

    assert result["teaching"] is not None

    element = result["teaching"]["element"]

    assert "bedroom" in element

    assert "bathroom" in element

    assert result["teaching"]["reason"]

    assert result["teaching"]["effect"]

    assert result["relationships"]


def test_t4_a_closet_is_resolved_through_the_corpus():

    assert classify_space("کلوزت")["space_id"] == "DRESSING"

    assert classify_space("کلوزت")["zone"] == "PRIVATE_ZONE"


# ==========================================================
# T5 — non-absolute rule protection
# ==========================================================

def test_t5_the_organization_is_never_absolute():

    result = understand_spatial_organization(TEACHING)

    text = result["natural_organization"]

    for absolute in ("must", "always", "همیشه"):

        assert absolute not in text

    assert result["non_claims"]["not_invented"] is True


# ==========================================================
# T6 — fixed vs flexible relationship
# ==========================================================

def test_t6_a_circulation_relationship_is_fixed():

    relationships = derive_relationships(["راه پله", "اتاق خواب"])

    kinds = {r["kind"]: r for r in relationships}

    assert REL_CONNECTED in kinds

    assert kinds[REL_CONNECTED]["fixed"] is True

    assert REL_CONNECTED in FIXED_RELATIONSHIP_KINDS


def test_t6_an_adjacent_relationship_is_flexible():

    relationships = derive_relationships(["پذیرایی", "آشپزخانه"])

    assert relationships

    assert relationships[0]["kind"] == REL_ADJACENT

    assert relationships[0]["fixed"] is False


def test_t6_a_flexible_element_must_not_damage_a_fixed_one():

    result = understand_spatial_organization("راه پله ثابت است و کلوزت بزرگ می‌خواهم")

    kinds = {c["kind"] for c in result["conflicts"]}

    assert "fixed_vs_flexible" in kinds


# ==========================================================
# T7 — multi-space reasoning
# ==========================================================

def test_t7_several_spaces_are_combined():

    result = understand_spatial_organization(
        "خانه کوچک با آشپزخانه، پذیرایی، اتاق خواب، حمام و راه پله",
        memory=memory_with_knowledge(),
    )

    assert len(result["program"]) >= 4

    assert len(result["relationships"]) >= 3

    assert result["dimensions"]


def test_t7_the_priority_order_is_declared():

    assert SPATIAL_PRIORITIES == (
        "essential_circulation",
        "privacy",
        "natural_light",
        "optional_storage",
    )

    result = understand_spatial_organization(REQUEST)

    assert list(result["priorities"]) == list(SPATIAL_PRIORITIES)


# ==========================================================
# T8 — conflict detection without a design decision
# ==========================================================

def test_t8_a_conflict_is_reported_not_decided():

    result = understand_spatial_organization(
        "خانه کوچک با حریم بالا و کلوزت بزرگ", memory=memory_with_knowledge()
    )

    assert result["conflicts"]

    assert result["human_review_required"] is True

    assert result["is_final_solution"] is False


# ==========================================================
# T9 — no geometry output
# ==========================================================

def test_t9_no_geometry_is_emitted():

    result = understand_spatial_organization(REQUEST, memory=memory_with_knowledge())

    payload = " ".join(
        str(result[key])
        for key in ("zones", "relationships", "priorities", "natural_organization")
    ).lower()

    for forbidden in ("geometry", "polygon", "coordinate", "cad", "bim", "ifc"):

        assert forbidden not in payload


def test_t9_the_layer_declares_its_safety_flags():

    assert ArchitecturalSpatialOrganizationV1.GENERATES_GEOMETRY is False

    assert ArchitecturalSpatialOrganizationV1.DECIDES_FINAL_DESIGN is False

    assert architectural_spatial_organization.CONTRACT == CONTRACT


# ==========================================================
# T10 — no plan generation
# ==========================================================

def test_t10_no_plan_is_generated():

    result = understand_spatial_organization(REQUEST, memory=memory_with_knowledge())

    assert result["plan_generated"] is False

    assert result["design_generated"] is False

    assert result["non_claims"]["not_a_plan"] is True


# ==========================================================
# the contract + helpers
# ==========================================================

def test_the_contract_carries_every_required_field():

    result = understand_spatial_organization(REQUEST)

    for field in (
        "program", "zones", "space_zone", "relationships",
        "fixed_relationships", "flexible_relationships", "priorities",
        "conflicts", "human_review_required", "natural_organization",
    ):

        assert field in result, field

    assert result["contract"] == CONTRACT


def test_an_empty_source_is_rejected():

    with pytest.raises(ArchitecturalSpatialOrganizationError):

        understand_spatial_organization("   ")


def test_the_natural_organization_has_english():

    result = understand_spatial_organization(REQUEST)

    assert "spatial organization" in build_natural_organization(result, language="en")


def test_the_zone_relationship_table_is_symmetric():

    assert ZONE_RELATIONSHIP[("PUBLIC_ZONE", "PRIVATE_ZONE")] == "separated"

    assert ZONE_RELATIONSHIP[("PRIVATE_ZONE", "SERVICE_ZONE")] == "private_transition"


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
