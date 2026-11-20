import pytest

from core.architecture.reasoning.exterior_entrance_transition_reasoner_v1 import (
    ExteriorEntranceTransitionReasonerV1,
)
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.app_boot import AppBoot


def test_explicit_040_transition_resolves_two_020_risers():
    contract = ExteriorEntranceTransitionReasonerV1().resolve({
        "site_datum": {"elevation": 0.0, "source": "user_explicit"},
        "finished_floor": {"level": "F1", "elevation": 0.4, "source": "user_explicit"},
        "entrance_transition": {"riser_height": 0.2},
    })
    steps = contract["exterior_steps"]
    assert steps["total_rise"] == pytest.approx(0.4)
    assert steps["riser_count"] == 2
    assert steps["riser_height"] == pytest.approx(0.2)
    assert steps["geometry_status"] == "pending"


def test_equal_site_and_finished_floor_requires_no_steps():
    contract = ExteriorEntranceTransitionReasonerV1().resolve({
        "site_datum": {"elevation": 0.0},
        "finished_floor": {"level": "F1", "elevation": 0.0},
    })
    assert contract["exterior_steps"]["required"] is False
    assert contract["exterior_steps"]["riser_count"] == 0


def test_non_benchmark_rise_uses_applicable_rule_instead_of_040_hardcode():
    contract = ExteriorEntranceTransitionReasonerV1().resolve({
        "site_datum": {"elevation": 0.0},
        "finished_floor": {"level": "F1", "elevation": 0.6},
        "exterior_step_rules": {"maximum_riser_height": 0.18},
    })
    steps = contract["exterior_steps"]
    assert steps["riser_count"] == 4
    assert steps["riser_height"] == pytest.approx(0.15)
    assert steps["riser_resolution_source"] == "applicable_exterior_step_rule"


def test_unresolved_entrance_geometry_never_uses_origin_fallback():
    contract = ExteriorEntranceTransitionReasonerV1().resolve({
        "site_datum": {"elevation": 0.0},
        "finished_floor": {"level": "F1", "elevation": 0.4},
        "entrance_transition": {"riser_count": 2},
    })
    steps = contract["exterior_steps"]
    assert steps["start_point"] is None
    assert steps["end_point"] is None
    assert steps["geometry_generation_allowed"] is False
    assert steps["geometry_status"] == "pending"


def test_persian_explicit_level_evidence_is_preserved_by_parser():
    brief = (
        "یک ویلای مسکونی یک طبقه طراحی کن. "
        "تراز حیاط مرجع = 0.00 است. کف ساختمان = +0.40 است. "
        "سکوی ورودی در تراز +0.40 است. دو پله داریم و ارتفاع هر رایزر = 0.20 است."
    )
    intent = ArchitecturalIntent().extract(brief)
    assert intent["site_datum"]["elevation"] == pytest.approx(0.0)
    assert intent["finished_floor"]["elevation"] == pytest.approx(0.4)
    assert intent["entrance_transition"]["platform"]["elevation"] == pytest.approx(0.4)
    assert intent["entrance_transition"]["riser_count"] == 2
    assert intent["entrance_transition"]["riser_height"] == pytest.approx(0.2)


def test_explicit_transition_survives_real_architecture_and_bim_path():
    brief = (
        "یک ویلای مسکونی یک طبقه طراحی کن. "
        "تراز حیاط مرجع = 0.00 است. کف ساختمان = +0.40 است. "
        "سکوی ورودی در تراز +0.40 است. دو پله داریم و ارتفاع هر رایزر = 0.20 است."
    )
    runtime = AppBoot().get_brain().run(brief)
    execution = runtime["execution_bridge"]
    design = execution["design"]
    transition = design["architectural_geometry"]["site_geometry"]["entrance_transition"]
    exterior_geometry = design["architectural_geometry"]["site_geometry"]["exterior_entrance"]
    steps = transition["exterior_steps"]

    assert design["architecture_first"] is True
    assert [level["name"] for level in design["vertical_section"]["levels"]] == ["F1"]
    assert design["vertical_section"]["site_datum"]["elevation"] == pytest.approx(0.0)
    assert design["vertical_section"]["levels"][0]["finished_floor_elevation"] == pytest.approx(0.4)
    assert steps["riser_count"] == 2
    assert steps["riser_height"] == pytest.approx(0.2)
    assert steps["start_point"] is None and steps["end_point"] is None
    assert steps["geometry_generation_allowed"] is False
    assert exterior_geometry["main_entrance"]["resolution_status"] == "pending"
    assert exterior_geometry["main_entrance"]["resolution_reason"] == "resolved_opening_host_geometry_required"
    assert exterior_geometry["entrance_threshold"]["resolution_status"] == "pending"
    assert exterior_geometry["entrance_threshold"]["center"] is None
    assert exterior_geometry["entrance_threshold"]["elevation"] == pytest.approx(0.4)
    assert exterior_geometry["exterior_platform_geometry"]["geometry_generation_allowed"] is False

    bim_geometry = execution["bim_result"]["bim_result"]["geometry"]
    assert bim_geometry["site_geometry"]["entrance_transition"] == transition
