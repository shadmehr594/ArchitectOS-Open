from core.architecture.reasoning.contextual_program_demand_profile_v1 import ContextualProgramDemandProfileV1
from core.architecture.reasoning.spatial_demand_sizing_and_capacity_v1 import SpatialDemandSizingAndCapacityV1
from core.architecture.reasoning.vertical_circulation_footprint_sizing_v1 import VerticalCirculationFootprintSizingV1


def _resolve(operational=None, quantity=1, selected=True):
    operational = dict(operational or {})
    if selected and operational.get("flight_count"):
        operational["flight_count_selection"] = {
            "status": "authoritative_selected", "authority_class": "PROJECT_REQUIREMENT",
            "provenance": ["synthetic.design_selection"]}
    demand = ContextualProgramDemandProfileV1().build({"functions": [{
        "function_id": "stair", "function": "stair", "quantity": quantity,
        "floor_scope": ["ground", "level-1"], "operational_requirements": operational,
    }]})
    sized = SpatialDemandSizingAndCapacityV1().resolve(demand)
    return VerticalCirculationFootprintSizingV1().resolve(sized)


def test_two_flight_footprint_is_derived_only_from_explicit_evidence():
    out = _resolve({"clear_width": 1.2, "floor_to_floor_height": 3.24,
        "maximum_riser": .18, "minimum_tread": .28, "flight_count": 2,
        "landing_required": True, "landing_depth": 1.2,
        "stair_type": "u_return_two_flight", "provenance": ["synthetic.requirement"], "confidence": 1})
    row = out["demand_profile"]["functions"][0]["spatial_sizing"]
    assert row["sizing_mode"] == "DERIVED_GEOMETRIC_FOOTPRINT"
    assert row["resolved_spatial_area"] == row["derived_footprint"]
    assert row["vertical_circulation_footprint"]["stair_type"] == "u_return_two_flight"
    assert row["vertical_circulation_footprint"]["geometry_generated"] is False
    assert "direction" not in row["vertical_circulation_footprint"]


def test_one_flight_uses_authoritative_level_spans_without_inventing_landing_or_type():
    out = _resolve({"clear_width": 1.1, "served_level_spans": [
        {"name": "ground", "bottom": 0.0}, {"name": "level-1", "bottom": 2.7}],
        "maximum_riser": .18, "minimum_tread": .28, "flight_count": 1})
    audit = out["stair_audits"][0]
    assert audit["status"] == "resolved" and audit["stair_type"] is None
    assert audit["floor_to_floor_height_m"] == 2.7


def test_count_one_and_partial_stair_evidence_never_become_area():
    out = _resolve({"clear_width": 1.2})
    row = out["demand_profile"]["functions"][0]["spatial_sizing"]
    assert row["count"] == 1 and row["resolved_spatial_area"] is None
    assert out["complete"] is False
    assert set(out["stair_audits"][0]["missing_inputs"]) >= {
        "maximum_riser", "minimum_tread", "flight_count",
        "floor_to_floor_height_or_authoritative_level_spans"}


def test_two_flight_requires_explicit_landing_evidence():
    out = _resolve({"clear_width": 1.2, "floor_to_floor_height": 3.0,
        "maximum_riser": .18, "minimum_tread": .28, "flight_count": 2})
    assert set(out["stair_audits"][0]["missing_inputs"]) >= {"landing_required_true", "landing_depth"}


def test_feasible_flight_count_without_authoritative_selection_never_sizes_footprint():
    out = _resolve({"clear_width": 1.2, "floor_to_floor_height": 3.0,
        "maximum_riser": .17, "minimum_tread": .30, "flight_count": 1}, selected=False)
    audit = out["stair_audits"][0]
    assert audit["status"] == "unresolved"
    assert "authoritative_stair_configuration_selection" in audit["missing_inputs"]
    assert "footprint_area_m2" not in audit
