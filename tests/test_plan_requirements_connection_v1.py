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


def run_real_intent_to_planner(brief):
    intent = ArchitecturalIntent().extract({"prompt": brief})
    extracted_requirements = deepcopy(intent.get("plan_requirements"))
    ProgramIntentBridge().build(intent)
    plan = PlannerAgent().plan(
        brief,
        {"building_type": intent.get("building_type")},
        {"architectural_intent": intent},
    )
    return intent, extracted_requirements, plan


def space_requirement(contract, space_type):
    return next(
        item
        for item in contract["spaces"]
        if item["space_type"] == space_type
    )


def relationship(contract, requirement):
    return next(
        item
        for item in contract["relationships"]
        if item["requirement"] == requirement
    )


def test_exact_persian_brief_reaches_real_planner_as_authoritative_program():
    intent, extracted, plan = run_real_intent_to_planner(EXACT_BRIEF)

    contract = intent["plan_requirements"]
    assert extracted == contract == plan["plan_requirements"]
    assert contract["contract"] == "ArchitecturalPlanRequirementsV1"
    assert contract["occupancy"]["value"] == "residential_unit"
    assert contract["occupancy"]["source"] == "user_explicit"
    assert contract["floor_count"]["value"] == 1
    assert contract["floor_count"]["source"] == "user_explicit"

    area = contract["area"]
    assert area == {
        "value": 100.0,
        "unit": "m2",
        "precision": "approximate",
        "basis": "unspecified",
        "role": "design_target",
        "source": "user_explicit",
        "source_evidence": "حدود ۱۰۰ مترمربع",
    }

    bedroom = space_requirement(contract, "bedroom")
    assert bedroom["count"] == 2
    assert bedroom["count_status"] == "explicit"
    assert bedroom["source"] == "user_explicit"

    bathroom = space_requirement(contract, "bathroom")
    assert bathroom["required"] is True
    assert bathroom["count"] is None
    assert bathroom["count_status"] == "unspecified"

    assert plan["program_source"] == "plan_requirements"
    ground = plan["spaces"]["ground_floor"]
    assert ground.count("bedroom") == 2
    assert ground.count("bathroom") == 1
    assert "living" in ground
    assert "kitchen" in ground
    assert not ({"stairs", "parking", "guest", "storage", "laundry_room"} & set(ground))
    assert plan["spaces"].get("typical_floor", []) == []

    assert plan["geometry_validation"] == {
        "status": "pending",
        "reason": "semantic_requirements_only",
    }
    assert all(item["validation_status"] == "pending" for item in plan["relationships"])
    assert plan["design_option_provenance"]["style"]["source"] == "planner_default"
    assert plan["design_option_provenance"]["materials"]["source"] == "planner_default"


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
def test_explicit_bedroom_multiplicity_controls_single_floor_program(
    brief, expected_count
):
    _intent, _extracted, plan = run_real_intent_to_planner(brief)

    requirement = space_requirement(plan["plan_requirements"], "bedroom")
    assert requirement["count"] == expected_count
    assert requirement["count_status"] == "explicit"
    assert plan["spaces"]["ground_floor"].count("bedroom") == expected_count


def test_two_storey_explicit_internal_stair_is_preserved():
    brief = (
        "برای یک واحد مسکونی دو طبقه با نشیمن، آشپزخانه، دو اتاق خواب، "
        "سرویس بهداشتی و راه‌پله داخلی پلان طراحی کن."
    )
    _intent, _extracted, plan = run_real_intent_to_planner(brief)

    assert plan["floors"] == 2
    stair = space_requirement(plan["plan_requirements"], "stairs")
    assert stair["required"] is True
    assert stair["source"] == "user_explicit"
    assert "stairs" in plan["spaces"]["ground_floor"]


def test_explicit_parking_is_preserved_without_inventing_its_location():
    brief = (
        "برای یک واحد مسکونی یک‌طبقه با نشیمن، آشپزخانه، یک اتاق خواب، "
        "سرویس بهداشتی و پارکینگ پلان طراحی کن."
    )
    _intent, _extracted, plan = run_real_intent_to_planner(brief)

    parking = space_requirement(plan["plan_requirements"], "parking")
    assert parking["required"] is True
    assert parking["source"] == "user_explicit"
    assert parking["floor_assignment"] == "unspecified"
    assert "parking" in plan["unassigned_required_spaces"]


def test_privacy_public_bathroom_access_and_circulation_remain_pending():
    brief = (
        "پلان یک واحد مسکونی با نشیمن و آشپزخانه طراحی کن؛ اتاق خواب حریم "
        "خصوصی داشته باشد، سرویس بهداشتی از فضای عمومی قابل دسترسی باشد و "
        "گردش داخلی منطقی باشد."
    )
    _intent, _extracted, plan = run_real_intent_to_planner(brief)
    contract = plan["plan_requirements"]

    privacy = relationship(contract, "private_zone_separation")
    assert privacy["source"] == "user_explicit"
    assert privacy["validation_status"] == "pending"
    assert privacy["separates_from_zone"] == "public"

    access = relationship(contract, "accessible_from_public_zone")
    assert access["source"] == "user_explicit"
    assert access["validation_status"] == "pending"

    assert contract["circulation"]["requirement"] == "logical"
    assert contract["circulation"]["validation_status"] == "pending"


def test_missing_area_does_not_invent_an_area_or_basis():
    brief = (
        "برای یک واحد مسکونی یک‌طبقه با نشیمن، آشپزخانه، دو اتاق خواب و "
        "سرویس بهداشتی پلان طراحی کن."
    )
    _intent, _extracted, plan = run_real_intent_to_planner(brief)

    assert plan["plan_requirements"]["area"] is None
    assert "gross_area" not in plan["architectural_intent"]
    assert "net_area" not in plan["architectural_intent"]


@pytest.mark.parametrize(
    ("brief", "basis", "value", "intent_field"),
    [
        (
            "برای یک واحد مسکونی با مساحت ناخالص ۱۲۰ مترمربع پلان طراحی کن.",
            "gross",
            120.0,
            "gross_area",
        ),
        (
            "برای یک واحد مسکونی با مساحت خالص ۸۵ مترمربع پلان طراحی کن.",
            "net",
            85.0,
            "net_area",
        ),
    ],
)
def test_explicit_gross_and_net_area_keep_their_distinction(
    brief, basis, value, intent_field
):
    intent, _extracted, plan = run_real_intent_to_planner(brief)

    area = plan["plan_requirements"]["area"]
    assert area["basis"] == basis
    assert area["value"] == value
    assert area["precision"] == "exact"
    assert intent[intent_field] == value
    other = "net_area" if intent_field == "gross_area" else "gross_area"
    assert other not in intent


def test_optional_space_is_not_promoted_to_hard_program():
    brief = (
        "برای یک واحد مسکونی یک‌طبقه با نشیمن، آشپزخانه، یک اتاق خواب و "
        "سرویس بهداشتی پلان طراحی کن؛ در صورت امکان اتاق کار را فقط به‌عنوان "
        "فضای اختیاری پیشنهاد بده."
    )
    _intent, _extracted, plan = run_real_intent_to_planner(brief)

    workspace = space_requirement(plan["plan_requirements"], "workspace")
    assert workspace["required"] is False
    assert workspace["classification"] == "inferred_architectural_option"
    assert "workspace" not in plan["spaces"]["ground_floor"]


def test_design_agent_preserves_authoritative_program_and_planner_lists():
    _intent, _extracted, plan = run_real_intent_to_planner(EXACT_BRIEF)
    assert "stairs" not in plan["spaces"]["ground_floor"]
    planner_spaces_before_design = deepcopy(plan["spaces"])

    design = DesignAgent().build(plan)
    f1_types = {item["type"] for item in design["F1"]["nodes"].values()}

    assert "stairs" not in f1_types
    assert "vertical_core" not in f1_types
    assert "stairs" not in planner_spaces_before_design["ground_floor"]
    assert plan["spaces"] == planner_spaces_before_design
