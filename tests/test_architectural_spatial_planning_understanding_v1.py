"""Architectural Spatial Planning Understanding (V1) — isolated self-checks.

    T1  a natural house request -> a conceptual spatial planning
    T2  the conceptual levels (ground = public/semi-public/service, upper = private)
    T3  the relationships between spaces
    T4  fixed vs flexible
    T5  the priority ladder (SAFETY -> ESSENTIAL -> QUALITY -> OPTIONAL)
    T6  the fixed stair is protected (a flexible need never shrinks it)
    T7  a small site vs the optional features (a reported conflict)
    T8  the duplex understanding (two conceptual levels + a fixed vertical core)
    T9  the privacy / daylight trade-off
    T10 the conceptual alternatives (never a final decision)
    T11 the context-dependent parameters (a number is never a constant)
    T12 no geometry / CAD / BIM / IFC / render / plan
    T13 the human experience (a natural request -> a natural answer)
"""

from __future__ import annotations


import ast
from pathlib import Path

import pytest

from core.knowledge.architectural_spatial_planning_understanding_v1 import (
    CONTRACT,
    FIXED_KINDS,
    FLEXIBLE_KINDS,
    LEVEL_GROUND,
    LEVEL_MAIN,
    LEVEL_UPPER,
    PRIORITY_ESSENTIAL,
    PRIORITY_OPTIONAL,
    PRIORITY_QUALITY,
    PRIORITY_SAFETY,
    SPATIAL_PRIORITY_ORDER,
    ArchitecturalSpatialPlanningUnderstandingError,
    ArchitecturalSpatialPlanningUnderstandingV1,
    architectural_spatial_planning_understanding,
    build_natural_planning,
    detect_floors,
    detect_household,
    extract_parameters,
    priority_of,
    understand_spatial_planning,
)

from core.knowledge.architectural_intent_understanding_v1 import understand_intent

from core.knowledge.architectural_spatial_organization_v1 import (
    understand_spatial_organization,
)

from core.knowledge.architectural_knowledge_extraction_engine_v1 import (
    extract_architectural_knowledge_candidate_v1 as extract,
)

from core.knowledge.human_knowledge_validation_loop_v1 import open_review

from core.knowledge.architectural_knowledge_memory_v1 import (
    ArchitecturalKnowledgeMemoryV1,
)


MODULE = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "knowledge"
    / "architectural_spatial_planning_understanding_v1.py"
)


# ---- the brief's own human examples ----

EX_DUPLEX = (
    "یک خانه دوبلکس برای خانواده ۴ نفره می‌خواهم، زمین کوچک است، "
    "نور مهم است، حریم هم مهم است."
)

EX_SMALL_BIG_KITCHEN = (
    "یک خانه کوچک می‌خواهم ولی آشپزخانه بزرگ دوست دارم، "
    "اتاق مستر هم کلوزت داشته باشد."
)

EX_NORTH_LIGHTWELL = "زمین شمالی است، نورگیری مرکزی لازم دارم."

EX_HUMAN = "یه خونه برای چهار نفر می‌خوام، زمین کوچیکه، نور خوب می‌خوام، حریم هم مهمه."

EX_STAIR = "خانه کوچک است، راه پله ثابت است و کلوزت بزرگ می‌خواهم."

EX_PARAM = "نورگیر با عرض ۳ متر و مساحت ۱۲ متر مربع در این آموزش."

EX_PARAM_BARE = "نورگیر ۳ متر"


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


def priorities_of(result):

    return {r["element"]: r["priority"] for r in result["priority_reasoning"]}


def conflict_kinds(result):

    return [c["kind"] for c in result["conflicts"]]


# ==========================================================
# T1 — a natural house request
# ==========================================================

def test_t1_a_request_yields_a_conceptual_planning():

    result = understand_spatial_planning(EX_DUPLEX)

    assert result["contract"] == CONTRACT

    assert result["building_intent"]["building_type"] == "duplex"

    assert result["building_intent"]["household"]["size"] == 4

    assert result["spaces"]

    assert result["spatial_planning_concept"]["levels"]

    assert result["natural_planning"]


def test_t1_no_form_and_no_json_is_required():

    text = understand_spatial_planning(EX_HUMAN)["natural_planning"]

    assert isinstance(text, str)

    for marker in ("{", "}", "contract", "json", "schema", "zones"):

        assert marker not in text


def test_t1_the_understanding_is_never_a_plan():

    result = understand_spatial_planning(EX_DUPLEX)

    assert result["plan_generated"] is False

    assert result["design_generated"] is False

    assert result["geometry_generated"] is False

    assert result["non_claims"]["not_a_plan"] is True

    assert result["is_final_solution"] is False

    assert result["human_review_required"] is True


# ==========================================================
# T2 — the conceptual levels
# ==========================================================

def test_t2_ground_holds_the_public_semi_public_and_service_zones():

    concept = understand_spatial_planning(EX_DUPLEX)["spatial_planning_concept"]

    ground = next(l for l in concept["levels"] if l["level"] == LEVEL_GROUND)

    assert "PUBLIC_ZONE" in ground["zones"]

    assert "SEMI_PUBLIC_ZONE" in ground["zones"]

    assert "SERVICE_ZONE" in ground["zones"]


def test_t2_upper_holds_the_private_zone():

    concept = understand_spatial_planning(EX_DUPLEX)["spatial_planning_concept"]

    upper = next(l for l in concept["levels"] if l["level"] == LEVEL_UPPER)

    assert "PRIVATE_ZONE" in upper["zones"]


def test_t2_a_single_level_house_uses_one_main_level():

    concept = understand_spatial_planning(EX_SMALL_BIG_KITCHEN)["spatial_planning_concept"]

    assert [l["level"] for l in concept["levels"]] == [LEVEL_MAIN]


def test_t2_the_classification_comes_from_the_corpus_not_a_hardcoded_law():

    concept = understand_spatial_planning(EX_SMALL_BIG_KITCHEN)["spatial_planning_concept"]

    assert "OPEN_KITCHEN" in concept["zones"]["SEMI_PUBLIC_ZONE"]

    assert "MASTER_BEDROOM_SLEEPING" in concept["zones"]["PRIVATE_ZONE"]


# ==========================================================
# T3 — the relationships
# ==========================================================

def test_t3_an_entrance_and_a_living_are_adjacent():

    result = understand_spatial_planning(EX_DUPLEX)

    assert any(
        r["kind"] == "adjacent"
        and {r["a"], r["b"]} == {"UNIT_ENTRY", "LIVING_RECEPTION"}
        for r in result["relationships"]
    )


def test_t3_a_bedroom_and_a_bathroom_relate_privately():

    result = understand_spatial_planning(EX_DUPLEX)

    assert any(
        r["kind"] == "private_transition"
        and {r["a"], r["b"]} == {"MASTER_BEDROOM_SLEEPING", "FAMILY_BATHROOM"}
        for r in result["relationships"]
    )


def test_t3_the_stair_relates_to_the_upper_floor():

    result = understand_spatial_planning(EX_DUPLEX)

    vertical = [r for r in result["relationships"] if r["b"] == LEVEL_UPPER]

    assert vertical

    assert vertical[0]["kind"] == "connected"

    assert vertical[0]["fixed"] is True


# ==========================================================
# T4 — fixed vs flexible
# ==========================================================

def test_t4_the_stair_is_fixed_and_the_closet_is_flexible():

    result = understand_spatial_planning(EX_STAIR)

    assert "stair" in result["fixed_flexible"]["fixed"]

    assert "closet" in result["fixed_flexible"]["flexible"]


def test_t4_the_vocabulary_is_declared():

    assert "stair" in FIXED_KINDS

    assert "closet" in FLEXIBLE_KINDS

    assert "furniture" in FLEXIBLE_KINDS


def test_t4_the_rule_is_declared():

    result = understand_spatial_planning(EX_STAIR)

    assert "flexible" in result["fixed_flexible"]["rule"]

    assert result["fixed_flexible"]["rule"]


# ==========================================================
# T5 — the priority ladder
# ==========================================================

def test_t5_the_ladder_is_the_briefs_order():

    assert SPATIAL_PRIORITY_ORDER == (
        PRIORITY_SAFETY,
        PRIORITY_ESSENTIAL,
        PRIORITY_QUALITY,
        PRIORITY_OPTIONAL,
    )

    assert list(understand_spatial_planning(EX_DUPLEX)["priorities"]) == list(
        SPATIAL_PRIORITY_ORDER
    )


def test_t5_the_ladder_is_applied_to_the_elements():

    assert priority_of("stair") == PRIORITY_SAFETY

    assert priority_of("closet") == PRIORITY_OPTIONAL

    assert priority_of("MASTER_BEDROOM_SLEEPING") == PRIORITY_ESSENTIAL

    assert priority_of("OPEN_KITCHEN") == PRIORITY_ESSENTIAL


def test_t5_the_priority_reasoning_is_ordered():

    result = understand_spatial_planning(EX_STAIR)

    priorities = [r["priority"] for r in result["priority_reasoning"]]

    order = [SPATIAL_PRIORITY_ORDER.index(p) for p in priorities]

    assert order == sorted(order)

    assert priorities[0] == PRIORITY_SAFETY


# ==========================================================
# T6 — the fixed stair is protected
# ==========================================================

def test_t6_a_flexible_need_never_shrinks_the_fixed_stair():

    result = understand_spatial_planning(EX_STAIR)

    assert "fixed_vs_flexible" in conflict_kinds(result)

    assert "stair" in result["fixed_flexible"]["fixed"]

    text = result["natural_planning"]

    assert "دست‌نخورده" in text

    for shrinking in ("راه‌پله را کوچک", "راه پله را کوچک", "کوچک می‌کنیم"):

        assert shrinking not in text


def test_t6_the_fixed_conflict_outranks_the_optional_one():

    result = understand_spatial_planning(EX_STAIR)

    kinds = {c["kind"]: c for c in result["conflicts"]}

    assert kinds["fixed_vs_flexible"]["priority"] == PRIORITY_SAFETY

    assert kinds["area_vs_optional"]["priority"] == PRIORITY_OPTIONAL


def test_t6_each_conflict_kind_is_reported_once():

    kinds = conflict_kinds(understand_spatial_planning(EX_STAIR))

    assert len(kinds) == len(set(kinds))


# ==========================================================
# T7 — a small site vs the optional features
# ==========================================================

def test_t7_a_small_site_with_a_large_optional_feature_is_a_conflict():

    kinds = conflict_kinds(understand_spatial_planning(EX_SMALL_BIG_KITCHEN))

    assert "area_limitation" in kinds

    assert "area_vs_optional" in kinds


def test_t7_the_conflict_is_reported_not_solved():

    result = understand_spatial_planning(EX_SMALL_BIG_KITCHEN)

    assert result["conflicts"]

    assert result["is_final_solution"] is False

    assert result["human_review_required"] is True

    assert result["non_claims"]["human_decides"] is True


# ==========================================================
# T8 — the duplex understanding
# ==========================================================

def test_t8_a_duplex_is_understood_as_two_levels():

    result = understand_spatial_planning(EX_DUPLEX)

    assert detect_floors(EX_DUPLEX, "duplex") == 2

    assert result["building_intent"]["floors"] == 2

    assert [l["level"] for l in result["spatial_planning_concept"]["levels"]] == [
        LEVEL_GROUND,
        LEVEL_UPPER,
    ]


def test_t8_the_vertical_core_is_fixed_and_links_the_levels():

    circulation = understand_spatial_planning(EX_DUPLEX)["spatial_planning_concept"][
        "circulation"
    ]

    assert circulation["vertical_core"] == "stair"

    assert circulation["is_fixed"] is True

    assert circulation["connects_levels"] == [LEVEL_GROUND, LEVEL_UPPER]


def test_t8_the_household_is_read_from_a_spoken_number():

    assert detect_household(EX_HUMAN)["size"] == 4

    assert understand_spatial_planning(EX_HUMAN)["building_intent"]["household"]["size"] == 4


# ==========================================================
# T9 — the privacy / daylight trade-off
# ==========================================================

def test_t9_privacy_and_daylight_are_a_reported_trade_off():

    kinds = conflict_kinds(understand_spatial_planning(EX_DUPLEX))

    assert "privacy_daylight_tradeoff" in kinds


def test_t9_a_site_condition_yields_a_daylight_strategy_not_a_size():

    result = understand_spatial_planning(EX_NORTH_LIGHTWELL)

    concept = result["spatial_planning_concept"]

    assert concept["daylight_strategy"] == "central_lightwell"

    assert result["building_intent"]["site_condition"]

    assert result["building_intent"]["site_condition"]["open_edge"] == "north"


def test_t9_a_site_condition_is_absent_when_none_is_stated():

    assert understand_spatial_planning(EX_SMALL_BIG_KITCHEN)["building_intent"][
        "site_condition"
    ] == {}


# ==========================================================
# T10 — the conceptual alternatives
# ==========================================================

def test_t10_several_conceptual_alternatives_are_offered():

    alternatives = understand_spatial_planning(EX_DUPLEX)["conceptual_alternatives"]

    assert len(alternatives) >= 2

    assert {a["id"] for a in alternatives[:2]} == {"A", "B"}

    for alternative in alternatives:

        assert alternative["label"]

        assert alternative["gains"]

        assert alternative["costs"]

        assert alternative["is_final"] is False


def test_t10_the_alternatives_trade_connection_against_privacy():

    alternatives = understand_spatial_planning(EX_DUPLEX)["conceptual_alternatives"]

    by_id = {a["id"]: a for a in alternatives}

    assert "privacy" in " ".join(by_id["A"]["costs"]).lower() or "حریم" in " ".join(
        by_id["A"]["costs"]
    )

    assert "مساحت" in " ".join(by_id["B"]["costs"]) or "area" in " ".join(
        by_id["B"]["costs"]
    ).lower()


def test_t10_no_alternative_is_final():

    result = understand_spatial_planning(EX_DUPLEX)

    assert all(a["is_final"] is False for a in result["conceptual_alternatives"])

    assert result["non_claims"]["human_decides"] is True


# ==========================================================
# T11 — the context-dependent parameters
# ==========================================================

def test_t11_a_number_is_a_parameter_not_a_constant():

    parameters = understand_spatial_planning(EX_PARAM)["context_dependent_parameters"]

    by_unit = {p["unit"]: p for p in parameters}

    assert by_unit["m"]["value"] == "3"

    assert by_unit["m2"]["value"] == "12"

    for parameter in parameters:

        assert parameter["is_constant"] is False

        assert parameter["note"]


def test_t11_a_contextualized_number_says_so():

    parameters = understand_spatial_planning(EX_PARAM)["context_dependent_parameters"]

    assert all(p["contextualized"] is True for p in parameters)


def test_t11_a_number_without_a_context_is_flagged():

    parameters = extract_parameters(EX_PARAM_BARE)

    assert parameters

    assert all(p["contextualized"] is False for p in parameters)


def test_t11_the_area_and_the_length_are_not_double_counted():

    parameters = extract_parameters("مساحت ۱۲ متر مربع و عرض ۳ متر")

    units = sorted(p["unit"] for p in parameters)

    assert units == ["m", "m2"]


# ==========================================================
# T12 — no geometry / CAD / BIM / IFC / render / plan
# ==========================================================

def test_t12_no_geometry_is_emitted():

    result = understand_spatial_planning(EX_DUPLEX, memory=memory_with_knowledge())

    payload = (
        result["natural_planning"]
        + " "
        + " ".join(
            "%s %s %s" % (a["label"], a["gains"], a["costs"])
            for a in result["conceptual_alternatives"]
        )
        + " "
        + " ".join(str(c.get("statement")) for c in result["conflicts"])
    ).lower()

    for forbidden in (
        "geometry", "polygon", "coordinate", "cad", "bim", "ifc", "revit", "render", "wall",
    ):

        assert forbidden not in payload


def test_t12_the_layer_declares_its_safety_flags():

    assert ArchitecturalSpatialPlanningUnderstandingV1.IS_UNDERSTANDING is True

    assert ArchitecturalSpatialPlanningUnderstandingV1.GENERATES_GEOMETRY is False

    assert ArchitecturalSpatialPlanningUnderstandingV1.GENERATES_PLAN is False

    assert ArchitecturalSpatialPlanningUnderstandingV1.DECIDES_FINAL_DESIGN is False

    assert architectural_spatial_planning_understanding.CONTRACT == CONTRACT


def test_t12_nothing_is_written_into_the_memory():

    result = understand_spatial_planning(EX_DUPLEX, memory=memory_with_knowledge())

    assert result["persistent"] is False

    assert result["read_only"] is True

    assert result["non_claims"]["not_invented"] is True


def test_t12_the_module_imports_no_forbidden_package():

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


# ==========================================================
# T13 — the human experience (the main acceptance criterion)
# ==========================================================

def test_t13_a_natural_request_yields_a_natural_answer():

    text = understand_spatial_planning(EX_HUMAN)["natural_planning"]

    assert "تعادل" in text

    assert "نور" in text

    assert "حریم" in text

    assert "محدودیت" in text

    assert "عمومی و خصوصی" in text


def test_t13_the_answer_is_not_a_form():

    text = understand_spatial_planning(EX_HUMAN)["natural_planning"]

    for marker in ("{", "}", "contract", "json", "schema", "zones"):

        assert marker not in text

    assert "\n•" in text


def test_t13_the_answer_stays_non_absolute():

    text = understand_spatial_planning(EX_HUMAN)["natural_planning"]

    for absolute in ("همیشه", "always", "must", "قطعی"):

        assert absolute not in text

    assert understand_spatial_planning(EX_HUMAN)["non_claims"]["not_invented"] is True


def test_t13_the_architect_keeps_the_final_decision():

    result = understand_spatial_planning(EX_HUMAN)

    assert "معمار" in result["natural_planning"]

    assert result["human_review_required"] is True

    assert result["is_final_solution"] is False


# ==========================================================
# the contract + helpers
# ==========================================================

def test_the_contract_carries_every_required_field():

    result = understand_spatial_planning(EX_DUPLEX)

    for field in (
        "building_intent",
        "spatial_planning_concept",
        "spaces",
        "relationships",
        "fixed_flexible",
        "priority_reasoning",
        "priorities",
        "conceptual_alternatives",
        "context_dependent_parameters",
        "conflicts",
        "natural_planning",
        "human_review_required",
        "non_claims",
    ):

        assert field in result, field

    assert result["contract"] == CONTRACT


def test_an_empty_source_is_rejected():

    with pytest.raises(ArchitecturalSpatialPlanningUnderstandingError):

        understand_spatial_planning("   ")


def test_an_intent_result_may_be_the_source():

    intent = understand_intent(EX_DUPLEX)

    result = understand_spatial_planning(intent)

    assert result["building_intent"]["building_type"] == "duplex"

    assert result["spaces"]


def test_a_spatial_organization_result_may_be_the_source():

    organization = understand_spatial_organization(EX_DUPLEX)

    result = understand_spatial_planning(organization)

    assert result["contract"] == CONTRACT

    assert result["building_intent"]["floors"] == 2


def test_the_natural_planning_has_english():

    text = build_natural_planning(
        understand_spatial_planning(EX_DUPLEX), language="en"
    )

    assert "spatial planning" in text

    assert "architect" in text


def test_an_english_request_is_understood():

    result = understand_spatial_planning(
        "I want a small house for a family of four, daylight and privacy matter.",
        language="en",
    )

    assert result["language"] == "en"

    assert result["spaces"]

    assert "spatial planning" in result["natural_planning"]


def test_the_memory_path_is_safe_and_adds_no_decision():

    result = understand_spatial_planning(EX_DUPLEX, memory=memory_with_knowledge())

    assert result["is_final_solution"] is False

    assert result["reasoning_error"] is None or isinstance(result["reasoning_error"], str)

    assert result["human_review_required"] is True
