import pytest

from core.intelligence.architectural_intelligence_orchestrator import (
    ArchitecturalIntelligenceOrchestrator,
)
from core.intelligence.vehicle_access_candidate_selector import (
    VehicleAccessCandidateSelector,
)
from core.intelligence.vehicle_access_decision_resolver import (
    VehicleAccessDecisionResolver,
)
from core.intelligence.vehicle_access_feasibility_reasoner import (
    VehicleAccessFeasibilityReasoner,
)


def _context(south, north=None, parking=-2.5):
    accesses = [
        {"id": "south_road", "side": "south", "type": "main_road",
         "elevation": south, "vehicle_access": True,
         "source": "user_explicit", "access_edge_status": "confirmed"}
    ]
    if north is not None:
        accesses.append(
            {"id": "north_road", "side": "north", "type": "road",
             "elevation": north, "vehicle_access": True,
             "source": "user_explicit", "access_edge_status": "confirmed"}
        )
    return {
        "requirements": ["parking"],
        "floors": [],
        "site": {"area": 600.0, "bbox": {"width": 20.0, "height": 30.0}},
        "site_constraints": {"access_elevations": accesses},
        "parking": {"level": "basement", "elevation": parking,
                    "elevation_source": "user_explicit"},
        "allowable_vehicle_ramp_slope_percent": 15.0,
        "minimum_vehicle_ramp_width": 3.5,
        "vehicle_turning_radius": 5.5,
    }


def _select(context):
    pending = {
        "type": "vehicle_access_pending",
        "parameters": {"site_evidence": {
            "site_area": 600.0, "site_width": 20.0, "site_depth": 30.0,
        }},
    }
    feasibility = VehicleAccessFeasibilityReasoner().evaluate(pending, context)
    system_decision = VehicleAccessDecisionResolver().resolve(feasibility, context)
    selection = VehicleAccessCandidateSelector().select(
        feasibility, system_decision, context
    )
    return feasibility, system_decision, selection


def test_scenario_a_direct_at_grade_north_access_is_evidence_selected():
    context = _context(0.0, -2.5)
    context["site_constraints"]["access_elevations"][1].update(
        {"id": "north_rear_lane", "type": "rear_lane"}
    )
    feasibility, _, result = _select(context)
    assert feasibility["ramp"]["access_candidates"][0]["required_run"] == pytest.approx(16.6666667)
    assert result["status"] == "resolved"
    assert result["selected_access_candidate"]["access_id"] == "north_rear_lane"
    assert result["selection_reason"] == "direct_at_grade_parking_access_preferred_over_ramp"
    assert "north" not in result["selection_reason"]
    assert result["geometry_generation_allowed"] is True
    assert result["ramp_geometry_allowed"] is False
    assert result["driveway_geometry_allowed"] is True


def test_scenario_b_equal_ramp_candidates_remain_pending():
    _, _, result = _select(_context(0.0, 0.0))
    assert result["status"] == "access_candidate_selection_pending"
    assert result["selected_access_candidate"] is None
    assert result["geometry_generation_allowed"] is False
    assert result["ramp_geometry_allowed"] is False
    assert result["driveway_geometry_allowed"] is False


def test_scenario_c_reverses_selection_from_elevation_not_side():
    _, _, result = _select(_context(-2.5, 0.0))
    assert result["status"] == "resolved"
    assert result["selected_access_candidate"]["access_id"] == "south_road"
    assert result["selected_access_candidate"]["access_mode"] == "direct_at_grade"


def test_single_fully_verified_ramp_candidate_opens_ramp_gate():
    _, _, result = _select(_context(0.0))
    assert result["status"] == "resolved"
    assert result["selected_access_candidate"]["access_id"] == "south_road"
    assert result["geometry_generation_allowed"] is True
    assert result["ramp_geometry_allowed"] is True
    assert result["driveway_geometry_allowed"] is True


def test_incomplete_or_unconfirmed_access_fails_closed():
    context = _context(-2.5)
    context["site_constraints"]["access_elevations"][0]["access_edge_status"] = "pending"
    _, _, result = _select(context)
    assert result["status"] == "access_candidate_selection_pending"
    assert result["selected_access_candidate"] is None
    assert result["geometry_generation_allowed"] is False

    missing = _context(-2.5)
    del missing["minimum_vehicle_ramp_width"]
    _, _, missing_result = _select(missing)
    assert missing_result["status"] == "access_candidate_selection_pending"


def test_candidate_evidence_survives_real_orchestration():
    result = ArchitecturalIntelligenceOrchestrator().analyze(_context(0.0, -2.5))
    decision = result["vehicle_access_decision"]
    assert decision["status"] == "resolved"
    assert decision["selected_access_candidate"]["access_id"] == "north_road"
    resolved = next(
        item for item in result["vertical_systems"]
        if item["type"] == "vehicle_ramp"
    )
    parameters = resolved["parameters"]
    assert parameters["selected_access_id"] == "north_road"
    assert parameters["access_mode"] == "direct_at_grade"
    assert parameters["delta_z"] == pytest.approx(0.0)
    assert parameters["driveway_geometry_allowed"] is True
    assert parameters["ramp_geometry_allowed"] is False


def test_car_lift_comparison_and_missing_evidence_pending_are_preserved():
    context = _context(-2.5)
    context.update(
        {
            "car_lift_required_width": 2.8,
            "car_lift_required_depth": 5.5,
            "car_lift_queue_length": 6.0,
            "vehicle_access_preferences": {"prioritize_compact_footprint": True},
        }
    )
    feasibility, system_decision, selection = _select(context)
    assert feasibility["car_lift"]["status"] == "feasible"
    assert system_decision["selected_system"] == "car_lift"
    assert selection["selected_system"] == "car_lift"

    incomplete = {"requirements": ["parking"], "floors": []}
    result = ArchitecturalIntelligenceOrchestrator().analyze(incomplete)
    assert any(item["type"] == "vehicle_access_pending" for item in result["vertical_systems"])
    assert result["vehicle_access_system_decision"]["status"] == "unresolved"
    assert result["vehicle_access_decision"]["status"] == (
        "access_candidate_selection_pending"
    )
    assert result["vehicle_access_decision"]["geometry_generation_allowed"] is False
