from copy import deepcopy

import pytest

from core.agents.design_agent import DesignAgent
from core.agents.planner_agent import PlannerAgent
from core.ai.program_intent_bridge import ProgramIntentBridge
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent


EXACT_BRIEF = (
    "برای یک واحد مسکونی یک‌طبقه حدود ۱۰۰ مترمربع، پلان دوخوابه طراحی کن. "
    "نشیمن و آشپزخانه ارتباط مناسب داشته باشند، اتاق‌خواب‌ها حریم خصوصی "
    "داشته باشند، سرویس بهداشتی از فضای عمومی قابل دسترسی باشد و مسیرهای "
    "حرکت منطقی باشند."
)


def run_real_design_path(brief):
    intent = ArchitecturalIntent().extract({"prompt": brief})
    ProgramIntentBridge().build(intent)
    plan = PlannerAgent().plan(
        brief,
        {"building_type": intent.get("building_type")},
        {"architectural_intent": intent},
    )
    design = DesignAgent().build(plan)
    return intent, plan, design


def floor_types(design, floor="F1"):
    return [item["type"] for item in design[floor]["nodes"].values()]


def test_exact_authoritative_program_reaches_design_without_defaults():
    _intent, plan, design = run_real_design_path(EXACT_BRIEF)

    assert set(design) == {"F1", "metadata"}
    types = floor_types(design)
    assert types.count("living") == 1
    assert types.count("kitchen") == 1
    assert types.count("bedroom") == 2
    assert types.count("bathroom") == 1
    assert "stairs" not in types
    assert "vertical_core" not in types

    metadata = design["metadata"]
    assert metadata["program_source"] == "plan_requirements"
    assert metadata["plan_requirements"] == plan["plan_requirements"]
    assert metadata["plan_requirements"]["area"]["value"] == 100.0
    assert metadata["plan_requirements"]["area"]["precision"] == "approximate"
    assert metadata["plan_requirements"]["area"]["basis"] == "unspecified"


@pytest.mark.parametrize(
    ("brief", "expected_count"),
    [
        (
            "برای یک واحد مسکونی یک‌طبقه با نشیمن، آشپزخانه، سرویس "
            "بهداشتی و یک اتاق خواب پلان طراحی کن.",
            1,
        ),
        (
            "برای یک واحد مسکونی یک‌طبقه با نشیمن، آشپزخانه، سرویس "
            "بهداشتی و سه اتاق خواب پلان طراحی کن.",
            3,
        ),
    ],
)
def test_authoritative_bedroom_multiplicity_reaches_design(
    brief, expected_count
):
    _intent, _plan, design = run_real_design_path(brief)

    types = floor_types(design)
    assert types.count("bedroom") == expected_count
    assert types.count("bathroom") == 1
    assert "stairs" not in types
    assert "vertical_core" not in types


def test_explicit_multistorey_internal_stair_keeps_stair_and_core():
    brief = (
        "برای یک واحد مسکونی دو طبقه با نشیمن، آشپزخانه، دو اتاق خواب، "
        "سرویس بهداشتی و راه‌پله داخلی پلان طراحی کن."
    )
    _intent, _plan, design = run_real_design_path(brief)

    assert "stairs" in floor_types(design, "F1")
    assert "vertical_core" in floor_types(design, "F1")
    assert "stair_landing" in floor_types(design, "F2")
    assert "vertical_core" in floor_types(design, "F2")


def test_explicit_vertical_transport_keeps_justified_core():
    brief = (
        "برای یک واحد مسکونی دو طبقه با نشیمن، آشپزخانه، دو اتاق خواب، "
        "سرویس بهداشتی و آسانسور پلان طراحی کن."
    )
    intent, _plan, design = run_real_design_path(brief)

    assert intent["vertical_transport"]["elevators"]
    assert "vertical_core" in floor_types(design, "F1")
    assert "vertical_core" in floor_types(design, "F2")


def test_legacy_house_without_authoritative_contract_keeps_template_behavior():
    _intent, plan, design = run_real_design_path("یک خانه طراحی کن.")

    assert plan["plan_requirements"] is None
    assert plan["program_source"] == "template_defaults"
    types = floor_types(design)
    assert "entrance" in types
    assert "living" in types
    assert "kitchen" in types
    assert "stairs" in types
    assert "vertical_core" in types


def test_design_build_does_not_mutate_planner_output():
    intent = ArchitecturalIntent().extract({"prompt": EXACT_BRIEF})
    ProgramIntentBridge().build(intent)
    plan = PlannerAgent().plan(
        EXACT_BRIEF,
        {"building_type": intent.get("building_type")},
        {"architectural_intent": intent},
    )
    before = deepcopy(plan)

    DesignAgent().build(plan)

    assert plan == before


def test_repeated_build_is_stable_and_does_not_accumulate_spaces():
    intent = ArchitecturalIntent().extract({"prompt": EXACT_BRIEF})
    ProgramIntentBridge().build(intent)
    plan = PlannerAgent().plan(
        EXACT_BRIEF,
        {"building_type": intent.get("building_type")},
        {"architectural_intent": intent},
    )
    before = deepcopy(plan)

    first = DesignAgent().build(plan)
    second = DesignAgent().build(plan)

    assert first == second
    assert plan == before
    assert floor_types(first).count("bedroom") == 2


def test_pending_relationship_constraints_survive_without_geometry_claim():
    _intent, plan, design = run_real_design_path(EXACT_BRIEF)

    metadata = design["metadata"]
    assert metadata["relationship_constraints"] == plan["relationships"]
    assert all(
        item["validation_status"] == "pending"
        for item in metadata["relationship_constraints"]
    )
    assert metadata["circulation_constraint"]["validation_status"] == "pending"
    assert metadata["geometry_validation"] == {
        "status": "pending",
        "reason": "semantic_requirements_only",
    }
    assert all(
        connection.get("geometric") is not True
        for connection in design["F1"]["connections"]
    )
