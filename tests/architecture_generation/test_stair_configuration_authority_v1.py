from copy import deepcopy
import inspect
import json
from pathlib import Path

from core.architecture.reasoning.stair_configuration_authority_v1 import StairConfigurationAuthorityV1


def profile(evidence):
    return {"contract": "SyntheticDemand", "functions": [{
        "function_id": "stair", "function": "stair", "floor_scope": ["lower", "upper"],
        "operational_requirements": deepcopy(evidence)}]}


def constraints(**extra):
    base = {"maximum_riser": .18, "minimum_tread": .28,
            "served_level_spans": [{"name": "lower", "bottom": 0.0},
                                   {"name": "upper", "bottom": 2.4}]}
    base.update(extra)
    return base


def selected(flights):
    return {"contract": "SyntheticDesignSelection", "source_reference": "decision:stair:1",
            "evidence_status": "authoritative_selected_by_project",
            "authority_class": "PROJECT_REQUIREMENT",
            "stair": {"flight_count": flights}}


def test_missing_prerequisite_fails_closed():
    audit = StairConfigurationAuthorityV1().resolve(profile({}))[
        "stair_configuration_audits"][0]
    assert audit["status"] == "unresolved_prerequisites"
    assert set(audit["required_inputs"]) == {
        "maximum_riser", "minimum_tread", "authoritative_rise_or_level_spans"}


def test_one_feasible_is_not_silently_selected():
    audit = StairConfigurationAuthorityV1().resolve(profile(constraints()))[
        "stair_configuration_audits"][0]
    assert audit["status"] == "uniquely_feasible"
    assert [x["flight_count"] for x in audit["configuration_hypotheses"]] == [1]
    assert audit["selected_flight_count"] is None


def test_multiple_feasible_requires_project_selection():
    evidence = constraints(landing_required=True, landing_depth=1.2)
    audit = StairConfigurationAuthorityV1().resolve(profile(evidence))[
        "stair_configuration_audits"][0]
    assert audit["status"] == "human_input_required"
    assert [x["flight_count"] for x in audit["configuration_hypotheses"]] == [1, 2]


def test_explicit_authoritative_selection_publishes_flight_count():
    out = StairConfigurationAuthorityV1().resolve(
        profile(constraints(landing_required=True, landing_depth=1.2)), selected(2))
    audit = out["stair_configuration_audits"][0]
    assert audit["status"] == "authoritative_selected"
    assert out["demand_profile"]["functions"][0]["operational_requirements"]["flight_count"] == 2


def test_parcel2_human_confirmation_selects_two_flights_without_geometry_authority():
    root = Path(__file__).resolve().parents[2]
    contract = json.loads((root / "core/architecture/contracts/parcel2_human_program_evidence_v1.json")
                          .read_text(encoding="utf-8"))
    selection = next(record for record in contract["evidence_records"]
                     if record.get("id") == "stair_flight_count_selection")
    evidence = constraints(maximum_rise_per_flight=1.5, landing_required=True,
                           landing_depth=1.2)
    out = StairConfigurationAuthorityV1().resolve(profile(evidence), selection)
    audit = out["stair_configuration_audits"][0]
    assert audit["status"] == "authoritative_selected"
    assert audit["selected_flight_count"] == 2
    assert audit["selection_authority_class"] == "DESIGN_CONFIRMATION"
    assert out["geometry_generated"] is False
    assert set(selection["scope_exclusions"]) == {
        "topology", "direction", "position", "offset", "rectangle", "core_location"}


def test_zero_feasible_has_evidence_bearing_rejections():
    evidence = constraints(maximum_risers_per_flight=1,
                           landing_required=True, landing_depth=1.2)
    audit = StairConfigurationAuthorityV1().resolve(profile(evidence))[
        "stair_configuration_audits"][0]
    assert audit["status"] == "no_feasible_hypothesis"
    assert audit["configuration_hypotheses"] == []
    assert {x["flight_count"] for x in audit["rejected_hypotheses"]} == {1, 2}


def test_two_flight_missing_landing_evidence_remains_rejected():
    audit = StairConfigurationAuthorityV1().resolve(profile(constraints()))[
        "stair_configuration_audits"][0]
    rejection = next(x for x in audit["rejected_hypotheses"] if x["flight_count"] == 2)
    assert set(rejection["reasons"]) == {
        "authoritative_landing_requirement_required", "authoritative_landing_depth_required"}


def test_deterministic_no_mutation_and_source_is_non_geometric():
    source = profile(constraints(landing_required=True, landing_depth=1.2))
    frozen = deepcopy(source)
    authority = StairConfigurationAuthorityV1()
    assert authority.resolve(source) == authority.resolve(source)
    assert source == frozen
    production = inspect.getsource(StairConfigurationAuthorityV1).lower()
    forbidden = ("parcel", "north", "south", "east", "west", "cardinal", "offset",
                 "historical", "polygon", "coordinate", "orientation", "placement")
    assert not any(token in production for token in forbidden)


def test_boundary_riser_counts_are_reported_for_every_exact_span():
    evidence = {"maximum_riser": .17, "minimum_tread": .30,
                "served_level_spans": [
                    {"name": "a", "bottom": 0.0},
                    {"name": "b", "bottom": .34},
                    {"name": "c", "bottom": .510000001}]}
    audit = StairConfigurationAuthorityV1().resolve(profile(evidence))["stair_configuration_audits"][0]
    calculations = audit["configuration_hypotheses"][0]["span_calculations"]
    assert [item["riser_count"] for item in calculations] == [2, 2]
    assert calculations[0]["actual_riser_height_m"] == .17
    assert calculations[1]["actual_riser_height_m"] < .17


def test_470_span_rejects_one_flight_and_two_flight_waits_for_landing_depth():
    evidence = {"maximum_riser": .17, "minimum_tread": .30,
                "maximum_rise_per_flight": 3.70,
                "minimum_landing_width_relation": "not_less_than_stair_clear_width",
                "served_level_spans": [
                    {"name": "basement", "bottom": -2.40},
                    {"name": "ground", "bottom": .30},
                    {"name": "residential_floor_1", "bottom": 5.00},
                    {"name": "residential_floor_2", "bottom": 8.24},
                    {"name": "roof", "bottom": 11.48},
                    {"name": "stairhouse_top", "bottom": 14.18}]}
    audit = StairConfigurationAuthorityV1().resolve(profile(evidence))["stair_configuration_audits"][0]
    rows = audit["span_evaluations"]
    assert [row["riser_count"] for row in rows] == [16, 28, 20, 20, 16]
    assert [row["one_flight_status"] for row in rows] == ["feasible", "invalid", "feasible", "feasible", "feasible"]
    assert rows[1]["one_flight_reasons"] == ["maximum_rise_per_flight_exceeded"]
    assert all(row["two_flight_status"] == "unresolved" for row in rows)
    assert audit["status"] == "no_feasible_hypothesis"
    assert audit["selected_flight_count"] is None
    assert audit["landing_requirements"]["resolved"] is False
    assert audit["required_inputs"] == ["authoritative_landing_depth_required"]


def test_470_span_relation_derived_depth_makes_two_flight_feasible_not_selected():
    evidence = {"maximum_riser": .17, "minimum_tread": .30,
                "maximum_rise_per_flight": 3.70,
                "minimum_landing_dimension_relation": "not_less_than_stair_clear_width",
                "landing_depth": 1.20,
                "constraint_evidence": {"landing_depth": {
                    "status": "resolved", "resolution_rule": "authoritative_relation_bound",
                    "resolution_provenance": {
                        "expression": "minimum_landing_dimension >= stair_clear_width",
                        "numeric_constant_introduced": False}}},
                "served_level_spans": [
                    {"name": "ground", "bottom": .30},
                    {"name": "residential_floor_1", "bottom": 5.00}]}
    audit = StairConfigurationAuthorityV1().resolve(profile(evidence))[
        "stair_configuration_audits"][0]
    assert audit["status"] == "uniquely_feasible"
    assert [item["flight_count"] for item in audit["configuration_hypotheses"]] == [2]
    assert audit["selected_flight_count"] is None
    assert audit["required_inputs"] == ["project_design_selection_required"]
    assert audit["landing_requirements"]["resolved"] is True
    assert audit["landing_requirements"]["landing_depth_evidence"]["resolution_rule"] == \
        "authoritative_relation_bound"


def test_maximum_rise_boundary_is_inclusive_and_selection_authority_is_whitelisted():
    evidence = constraints(maximum_rise_per_flight=3.70)
    evidence["served_level_spans"][1]["bottom"] = 3.70
    audit = StairConfigurationAuthorityV1().resolve(profile(evidence))["stair_configuration_audits"][0]
    assert audit["span_evaluations"][0]["one_flight_status"] == "feasible"
    rejected = {"source_reference": "decision:x", "evidence_status": "authoritative_selected",
                "authority_class": "FIXTURE", "stair": {"flight_count": 1}}
    audit = StairConfigurationAuthorityV1().resolve(profile(evidence), rejected)["stair_configuration_audits"][0]
    assert audit["status"] == "uniquely_feasible" and audit["selected_flight_count"] is None
