import pytest

from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.intelligence.vertical_circulation_reasoning import (
    VerticalCirculationReasoning,
)
from core.intelligence.vehicle_access_feasibility_reasoner import (
    VehicleAccessFeasibilityReasoner,
)
from core.intelligence.vehicle_access_decision_resolver import (
    VehicleAccessDecisionResolver,
)
from core.intelligence.architectural_intelligence_orchestrator import (
    ArchitecturalIntelligenceOrchestrator,
)


def _technical_context(intent):
    intent.update(
        {
            "requirements": ["parking"],
            "floors": ["basement", "ground"],
            "site": {"area": 600.0, "bbox": {"width": 20.0, "height": 30.0}},
            "allowable_vehicle_ramp_slope_percent": 15.0,
            "minimum_vehicle_ramp_width": 3.5,
            "vehicle_turning_radius": 5.5,
        }
    )
    return intent


def test_parser_and_real_vehicle_access_flow_preserve_candidate_elevations():
    brief = (
        "تراز معبر جنوبی صفر است. تراز کوچه شمالی منفی 2.5 است. "
        "کوچه شمالی کوچه پشتی است. تراز پارکینگ زیرزمین -2.5 است. "
        "دسترسی خودرو و پارکینگ لازم است. شیب مجاز رمپ 15 درصد، "
        "حداقل عرض رمپ 3.5 متر و شعاع گردش خودرو 5.5 متر است."
    )
    intent = ArchitecturalIntent().extract({"prompt": brief})
    intent.update(
        {
            "requirements": ["parking"],
            "floors": ["basement", "ground"],
            "site": {"area": 600.0, "bbox": {"width": 20.0, "height": 30.0}},
        }
    )

    accesses = intent["site_constraints"]["access_elevations"]
    assert len(accesses) == 2
    assert accesses[0]["id"] == "south_main_road"
    assert accesses[0]["elevation"] == pytest.approx(0.0)
    assert accesses[1]["id"] == "north_rear_lane"
    assert accesses[1]["elevation"] == pytest.approx(-2.5)
    assert all(item["source"] == "user_explicit" for item in accesses)
    assert intent["parking"]["level"] == "basement"
    assert intent["parking"]["elevation"] == pytest.approx(-2.5)
    assert intent["allowable_vehicle_ramp_slope_percent"] == pytest.approx(15.0)
    assert intent["minimum_vehicle_ramp_width"] == pytest.approx(3.5)
    assert intent["vehicle_turning_radius"] == pytest.approx(5.5)

    vertical = VerticalCirculationReasoning().analyze(intent)
    pending = next(
        item for item in vertical["vertical_systems"]
        if item["type"] == "vehicle_access_pending"
    )
    assert pending["parameters"]["geometry_generation_allowed"] is False

    result = VehicleAccessFeasibilityReasoner().evaluate(pending, intent)
    candidates = {item["access_id"]: item for item in result["ramp"]["access_candidates"]}

    south = candidates["south_main_road"]
    north = candidates["north_rear_lane"]
    assert south["access_elevation"] == pytest.approx(0.0)
    assert south["target_elevation"] == pytest.approx(-2.5)
    assert south["delta_z"] == pytest.approx(-2.5)
    assert south["absolute_level_difference"] == pytest.approx(2.5)
    assert south["required_run"] == pytest.approx(16.6666667)
    assert north["delta_z"] == pytest.approx(0.0)
    assert north["absolute_level_difference"] == pytest.approx(0.0)
    assert north["access_mode"] == "direct_at_grade"
    assert north["ramp_geometry_required"] is False
    assert result["ramp"]["normalized_slope_ratio"] == pytest.approx(0.15)
    assert result["ramp"]["allowable_slope_percent"] == pytest.approx(15.0)
    assert result["ramp"]["slope_source"] == "allowable_vehicle_ramp_slope_percent"
    assert "vehicle_level_difference" not in result["ramp"]

    decision = VehicleAccessDecisionResolver().resolve(result, intent)
    assert decision["status"] == "access_candidate_selection_pending"
    assert decision["selected_access_candidate"] is None
    assert len(decision["feasible_access_candidates"]) == 2
    assert decision["geometry_generation_allowed"] is False


def test_equal_road_elevations_produce_equal_geometry_driven_differences():
    intent = _technical_context(
        ArchitecturalIntent().extract(
            {
                "prompt": (
                    "تراز خیابان جنوبی 0 است و تراز خیابان شمالی 0 است. "
                    "تراز پارکینگ زیرزمین -2.5 است. دسترسی خودرو و پارکینگ لازم است."
                )
            }
        )
    )
    pending = next(
        item for item in VerticalCirculationReasoning().analyze(intent)["vertical_systems"]
        if item["type"] == "vehicle_access_pending"
    )
    result = VehicleAccessFeasibilityReasoner().evaluate(pending, intent)
    differences = {
        item["side"]: item["absolute_level_difference"]
        for item in result["ramp"]["access_candidates"]
    }
    assert differences == {"south": pytest.approx(2.5), "north": pytest.approx(2.5)}


def test_missing_technical_evidence_fails_closed_and_pending_is_preserved():
    context = {
        "requirements": ["parking"],
        "floors": ["basement", "ground"],
        "site_constraints": {
            "access_elevations": [
                {
                    "id": "south_main_road",
                    "side": "south",
                    "type": "main_road",
                    "elevation": 0.0,
                    "vehicle_access": True,
                    "source": "user_explicit",
                }
            ]
        },
        "parking": {"level": "basement", "elevation": -2.5},
    }
    vertical = VerticalCirculationReasoning().analyze(context)
    pending = next(
        item for item in vertical["vertical_systems"]
        if item["type"] == "vehicle_access_pending"
    )
    result = VehicleAccessFeasibilityReasoner().evaluate(pending, context)
    assert result["ramp"]["status"] == "insufficient_evidence"
    assert set(result["ramp"]["missing_evidence"]) >= {
        "allowable_vehicle_ramp_slope",
        "minimum_vehicle_ramp_width",
        "vehicle_turning_radius",
    }
    assert result["geometry_generation_allowed"] is False
    assert VehicleAccessDecisionResolver().resolve(result, context)["status"] == "unresolved"


def test_legacy_slope_ratio_is_unambiguous_and_compatible():
    context = {
        "requirements": ["parking"],
        "site": {"bbox": {"width": 20.0, "height": 30.0}},
        "site_constraints": {
            "access_elevations": [
                {"id": "access", "side": "south", "elevation": 0.0,
                 "vehicle_access": True, "source": "user_explicit"}
            ]
        },
        "parking": {"level": "basement", "elevation": -2.5},
        "allowable_vehicle_ramp_slope": 0.18,
        "minimum_vehicle_ramp_width": 3.5,
        "vehicle_turning_radius": 5.5,
    }
    pending = {"parameters": {"site_evidence": {"site_depth": 30.0}}}
    result = VehicleAccessFeasibilityReasoner().evaluate(pending, context)
    assert result["ramp"]["normalized_slope_ratio"] == pytest.approx(0.18)
    assert result["ramp"]["allowable_slope_percent"] == pytest.approx(18.0)
    assert result["ramp"]["slope_status"] == "legacy_ratio_normalized"
    assert result["ramp"]["access_candidates"][0]["required_run"] == pytest.approx(13.8888889)


def test_real_intelligence_orchestrator_preserves_access_candidate_contract():
    intent = _technical_context(
        ArchitecturalIntent().extract(
            {
                "prompt": (
                    "تراز معبر جنوبی صفر است. تراز کوچه شمالی منفی 2.5 است. "
                    "کوچه شمالی کوچه پشتی است. تراز پارکینگ زیرزمین -2.5 است. "
                    "دسترسی خودرو و پارکینگ لازم است."
                )
            }
        )
    )
    # Floor program generation is outside this semantic checkpoint; the real
    # orchestrator still invokes vertical reasoning, feasibility and decision.
    intent["floors"] = []
    result = ArchitecturalIntelligenceOrchestrator().analyze(intent)
    ramp = result["vehicle_access_feasibility"]["ramp"]
    assert [
        item["absolute_level_difference"]
        for item in ramp["access_candidates"]
    ] == [pytest.approx(2.5), pytest.approx(0.0)]
    assert result["vehicle_access_decision"]["status"] == "resolved"
    assert result["vehicle_access_decision"]["selected_access_id"] == (
        "north_rear_lane"
    )
    assert result["vehicle_access_decision"]["geometry_generation_allowed"] is True
    assert result["vehicle_access_decision"]["ramp_geometry_allowed"] is False
