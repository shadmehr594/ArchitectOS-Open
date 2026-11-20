from copy import deepcopy
import inspect
import json
from pathlib import Path

from core.architecture.reasoning.authoritative_stair_requirements_resolution_v1 import (
    AuthoritativeStairRequirementsResolutionV1,
)
from core.architecture.reasoning.contextual_program_demand_profile_v1 import ContextualProgramDemandProfileV1
from core.architecture.reasoning.spatial_demand_sizing_and_capacity_v1 import SpatialDemandSizingAndCapacityV1
from core.architecture.reasoning.vertical_circulation_footprint_sizing_v1 import VerticalCirculationFootprintSizingV1
from core.architecture.reasoning.project_level_contract_v1 import ProjectLevelContractV1


def demand(scope=("basement", "ground"), operational=None, quantity=1):
    return ContextualProgramDemandProfileV1().build({"functions": [{
        "function_id": "stair", "function": "stair", "quantity": quantity,
        "floor_scope": list(scope), "operational_requirements": operational or {},
    }]})


def project(width=1.2, levels=None, source="current_project_contract"):
    return {"contract": "SyntheticProjectRequirements", "source": source,
            "evidence_status": "authoritative_for_current_project", "applicability": "synthetic_case",
            "confidence": 1.0, "core": {"stair_clear_width": width},
            "levels": levels if levels is not None else {"basement": -2.4, "ground": 0.0}}


def regulations():
    return {"contract": "SyntheticRegulation", "source": "adopted_code",
            "source_reference": "Synthetic Code, clause 1.2.3",
            "evidence_status": "resolved_authoritative", "jurisdiction": "synthetic",
            "edition": "v1", "applicability": {
                "status": "explicitly_applicable", "project_id": "synthetic_case",
                "occupancies": ["residential", "commercial"],
                "jurisdiction": "synthetic", "edition": "v1"}, "confidence": 1.0,
            "stair": {"riser": {"value": .18}, "tread": {"value": .28}}}


def project_context():
    return {"project_id": "synthetic_case", "occupancies": ["residential", "commercial"],
            "jurisdiction": "synthetic", "edition": "v1"}


def configuration(flights=1):
    return {"contract": "SyntheticConfiguration", "source": "project_program_decision",
            "evidence_status": "authoritative_for_current_project", "applicability": "synthetic_case",
            "authority_class": "PROJECT_REQUIREMENT",
            "confidence": 1.0, "stair": {"flight_count": flights}}


def test_width_and_basement_ground_span_resolve_with_preserved_provenance():
    source = demand()
    out = AuthoritativeStairRequirementsResolutionV1().resolve(source, project())
    fields = out["stair_requirement_audits"][0]["fields"]
    width = fields["clear_width"]
    assert width["status"] == "resolved" and width["value"] == 1.2 and width["unit"] == "m"
    assert width["source_path"] == "requirements.core.stair_clear_width"
    assert width["evidence_status"] == "authoritative_for_current_project"
    assert width["applicability"] == "synthetic_case"
    spans = fields["floor_to_floor_spans"]
    assert spans["status"] == "resolved"
    assert abs(spans["value"][1]["bottom"] - spans["value"][0]["bottom"]) == 2.4


def test_upper_spans_and_missing_rules_remain_unresolved_with_precise_actions():
    out = AuthoritativeStairRequirementsResolutionV1().resolve(
        demand(("basement", "ground", "first")), project())
    audit = out["stair_requirement_audits"][0]
    assert audit["fields"]["floor_to_floor_spans"]["status"] == "unresolved"
    assert audit["fields"]["maximum_riser"]["status"] == "unresolved"
    assert audit["fields"]["minimum_tread"]["status"] == "unresolved"
    assert audit["fields"]["flight_count"]["status"] == "unresolved"
    assert set(audit["required_inputs"]) == {
        "regulation_input_required", "level_contract_required", "configuration_required"}


def test_missing_project_width_is_distinguished_as_human_input_required():
    out = AuthoritativeStairRequirementsResolutionV1().resolve(demand(), {})
    audit = out["stair_requirement_audits"][0]
    assert audit["fields"]["clear_width"]["status"] == "unresolved"
    assert "human_input_required" in audit["required_inputs"]


def test_geometry_like_operational_values_are_removed_and_count_one_never_becomes_area():
    raw = {"maximum_riser": .17, "minimum_tread": .29, "flight_count": 2,
           "landing_required": True, "landing_depth": 1.2, "clear_width": 9.9,
           "floor_to_floor_height": 3.0}
    resolved = AuthoritativeStairRequirementsResolutionV1().resolve(demand(operational=raw), project())
    operational = resolved["demand_profile"]["functions"][0]["operational_requirements"]
    assert operational == {"clear_width": 1.2, "provenance": [
        "requirements.core.stair_clear_width", "requirements.levels.basement", "requirements.levels.ground"],
        "confidence": 1.0, "served_level_spans": [
            {"name": "basement", "bottom": -2.4}, {"name": "ground", "bottom": 0.0}]}
    sized = SpatialDemandSizingAndCapacityV1().resolve(resolved["demand_profile"])
    footprint = VerticalCirculationFootprintSizingV1().resolve(sized)
    sizing = footprint["demand_profile"]["functions"][0]["spatial_sizing"]
    assert sizing["count"] == 1 and sizing["resolved_spatial_area"] is None
    assert set(footprint["stair_audits"][0]["missing_inputs"]) >= {
        "maximum_riser", "minimum_tread", "flight_count"}


def test_complete_independent_authorities_can_feed_footprint_without_defaults():
    resolved = AuthoritativeStairRequirementsResolutionV1().resolve(
        demand(), project(), regulations(), configuration=configuration(1),
        project_context=project_context())
    sized = SpatialDemandSizingAndCapacityV1().resolve(resolved["demand_profile"])
    footprint = VerticalCirculationFootprintSizingV1().resolve(sized)
    assert footprint["stair_audits"][0]["status"] == "resolved"


def test_two_flights_do_not_resolve_without_independent_landing_evidence():
    resolved = AuthoritativeStairRequirementsResolutionV1().resolve(
        demand(), project(), regulations(), configuration=configuration(2),
        project_context=project_context())
    audit = resolved["stair_requirement_audits"][0]
    assert set(audit["required_inputs"]) >= {"configuration_required", "regulation_input_required"}
    footprint = VerticalCirculationFootprintSizingV1().resolve(
        SpatialDemandSizingAndCapacityV1().resolve(resolved["demand_profile"]))
    assert set(footprint["stair_audits"][0]["missing_inputs"]) >= {
        "landing_required_true", "landing_depth"}


def test_conflicting_authoritative_sources_fail_closed():
    out = AuthoritativeStairRequirementsResolutionV1().resolve(
        demand(), [project(1.2, source="a"), project(1.3, source="b")])
    width = out["stair_requirement_audits"][0]["fields"]["clear_width"]
    operational = out["demand_profile"]["functions"][0]["operational_requirements"]
    assert width["status"] == "conflicted" and width["value"] is None
    assert "clear_width" not in operational


def test_regulation_applicability_mismatch_and_missing_reference_fail_closed():
    mismatched = regulations()
    mismatched["applicability"]["occupancies"] = ["residential"]
    out = AuthoritativeStairRequirementsResolutionV1().resolve(
        demand(), project(), mismatched, project_context=project_context())
    field = out["stair_requirement_audits"][0]["fields"]["maximum_riser"]
    assert field["status"] == "unresolved"
    assert "occupancy_scope_mismatch" in field["rejection_reasons"][0]["reasons"]
    missing_reference = regulations()
    missing_reference.pop("source_reference")
    field = AuthoritativeStairRequirementsResolutionV1().resolve(
        demand(), project(), missing_reference, project_context=project_context()
    )["stair_requirement_audits"][0]["fields"]["maximum_riser"]
    assert "source_reference_required" in field["rejection_reasons"][0]["reasons"]


def test_conflicting_applicable_regulations_remain_conflicted():
    second = regulations()
    second["source"] = "other_adopted_code"
    second["source_reference"] = "Synthetic Code, clause 9.9"
    second["stair"]["riser"]["value"] = .17
    field = AuthoritativeStairRequirementsResolutionV1().resolve(
        demand(), project(), [regulations(), second], project_context=project_context()
    )["stair_requirement_audits"][0]["fields"]["maximum_riser"]
    assert field["status"] == "conflicted" and field["value"] is None


def test_no_mutation_and_deterministic_output():
    source = demand()
    frozen = deepcopy(source)
    resolver = AuthoritativeStairRequirementsResolutionV1()
    assert resolver.resolve(source, project()) == resolver.resolve(source, project())
    assert source == frozen


def test_source_has_no_parcel_or_historical_geometry_heuristics():
    source = inspect.getsource(AuthoritativeStairRequirementsResolutionV1).lower()
    forbidden = ("parcel2", "north", "south", "east", "west", "hybrid",
                 "prior_geometry", "historical_geometry", "fixed_offset", "split_offset")
    assert not any(token in source for token in forbidden)
    assert AuthoritativeStairRequirementsResolutionV1.CANONICAL_MAPPING == {
        "riser": "maximum_riser", "tread": "minimum_tread"}


def minab_stair_evidence():
    path = Path(__file__).parents[2] / "core" / "architecture" / "contracts" / \
        "parcel2_minab_stair_regulation_evidence_v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def minab_context(project_id="parcel_2", jurisdiction="Minab"):
    return {"project_id": project_id, "jurisdiction": jurisdiction,
            "editions": ["1395", "1396"], "occupancies": ["residential", "commercial"]}


def test_minab_tread_is_lower_bound_with_separate_evidence_and_explicit_precedence():
    result = AuthoritativeStairRequirementsResolutionV1().resolve(
        demand(("basement", "ground", "first")), project(), minab_stair_evidence(),
        project_context=minab_context())
    audit = result["stair_requirement_audits"][0]
    tread = audit["fields"]["minimum_tread"]
    assert tread["status"] == "resolved" and tread["value"] == .30
    assert tread["constraint"] == "minimum" and tread["operator"] == ">="
    assert .31 >= tread["value"]
    assert tread["resolution_rule"] == "strictest_applicable_minimum"
    assert [item["value"] for item in tread["accepted_evidence"]] == [.28, .30]
    assert [item["source_kind"] for item in tread["accepted_evidence"]] == [
        "national_building_regulation", "human_confirmed_current_project_local_requirement"]
    assert tread["resolution_provenance"]["candidate_lower_bounds_m"] == [.28, .30]
    assert "minab_current_project" in tread["resolution_provenance"]["effective_source_path"]
    riser = audit["fields"]["maximum_riser"]
    assert riser["status"] == "resolved" and riser["value"] == .17
    assert riser["constraint"] == "maximum" and riser["operator"] == "<="
    assert riser["resolution_rule"] == "strictest_applicable_maximum"
    assert riser["accepted_evidence"][0]["clause"] == "4-5-1-7-1"
    assert riser["accepted_evidence"][0]["derivation"]["project_requirement_evidence_id"] == \
        "minab_current_project_minimum_tread"
    assert audit["fields"]["floor_to_floor_spans"]["status"] == "unresolved"


def test_minab_local_tread_does_not_leak_to_another_project_or_context():
    other = AuthoritativeStairRequirementsResolutionV1().resolve(
        demand(), project(), minab_stair_evidence(),
        project_context=minab_context("another_project", "Minab"))
    tread = other["stair_requirement_audits"][0]["fields"]["minimum_tread"]
    assert tread["status"] == "resolved" and tread["value"] == .28
    assert [item["value"] for item in tread["accepted_evidence"]] == [.28]
    assert all(item["source_kind"] != "human_confirmed_current_project_local_requirement"
               for item in tread["accepted_evidence"])


def test_minab_resolution_is_non_mutating_and_deterministic():
    evidence = minab_stair_evidence()
    frozen = deepcopy(evidence)
    resolver = AuthoritativeStairRequirementsResolutionV1()
    first = resolver.resolve(demand(), project(), evidence, project_context=minab_context())
    second = resolver.resolve(demand(), project(), evidence, project_context=minab_context())
    assert first == second and evidence == frozen


def test_landing_and_flight_limits_keep_dimension_semantics_and_applicability_separate():
    audit = AuthoritativeStairRequirementsResolutionV1().resolve(
        demand(), project(), minab_stair_evidence(), project_context=minab_context()
    )["stair_requirement_audits"][0]
    fields = audit["fields"]
    assert fields["maximum_rise_per_flight"]["status"] == "resolved"
    assert fields["maximum_rise_per_flight"]["value"] == 3.70
    assert fields["minimum_landing_dimension_relation"]["value"] == \
        "not_less_than_stair_clear_width"
    depth = fields["landing_depth"]
    assert depth["status"] == "resolved" and depth["value"] == 1.2
    assert depth["constraint"] == "minimum" and depth["operator"] == ">="
    assert depth["resolution_rule"] == "authoritative_relation_bound"
    assert depth["resolution_provenance"]["numeric_constant_introduced"] is False
    assert depth["resolution_provenance"]["expression"] == \
        "minimum_landing_dimension >= stair_clear_width"
    assert depth["resolution_provenance"]["effective_value_source_path"] == \
        "requirements.core.stair_clear_width"
    assert "minimum_landing_dimension_relation" in \
        depth["resolution_provenance"]["relation_source_path"]
    assert fields["maximum_risers_per_flight"]["status"] == "unresolved"
    rejected = fields["maximum_risers_per_flight"]["rejection_reasons"][0]["reasons"]
    assert "applicability_status_not_explicit" in rejected


def test_landing_relation_derivation_fails_closed_for_unknown_relation_or_missing_width():
    evidence = minab_stair_evidence()
    relation = next(item for item in evidence["evidence_records"]
                    if item["key"] == "minimum_landing_dimension_relation")
    relation["value"] = "unknown_relation"
    fields = AuthoritativeStairRequirementsResolutionV1().resolve(
        demand(), project(), evidence, project_context=minab_context()
    )["stair_requirement_audits"][0]["fields"]
    assert fields["landing_depth"]["status"] == "unresolved"
    assert fields["landing_depth"]["rejection_reasons"][0]["reasons"] == \
        ["unsupported_landing_dimension_relation"]

    fields = AuthoritativeStairRequirementsResolutionV1().resolve(
        demand(), {}, minab_stair_evidence(), project_context=minab_context()
    )["stair_requirement_audits"][0]["fields"]
    assert fields["clear_width"]["status"] == "unresolved"
    assert fields["landing_depth"]["status"] == "unresolved"


def test_landing_relation_boundary_is_exact_and_inputs_are_not_mutated():
    evidence = minab_stair_evidence()
    requirements = project(width=1.234567)
    frozen_evidence, frozen_requirements = deepcopy(evidence), deepcopy(requirements)
    resolver = AuthoritativeStairRequirementsResolutionV1()
    first = resolver.resolve(demand(), requirements, evidence, project_context=minab_context())
    second = resolver.resolve(demand(), requirements, evidence, project_context=minab_context())
    depth = first["stair_requirement_audits"][0]["fields"]["landing_depth"]
    assert depth["value"] == 1.234567
    assert first == second
    assert evidence == frozen_evidence and requirements == frozen_requirements


def test_strictest_applicable_maximum_and_mismatch_are_evidence_bearing():
    first = regulations()
    first["stair"] = {"riser": {"value": .18, "constraint": "maximum"}}
    second = deepcopy(first)
    second["source_reference"] = "Synthetic Code, clause 2.3.4"
    second["stair"]["riser"]["value"] = .17
    field = AuthoritativeStairRequirementsResolutionV1().resolve(
        demand(), project(), [first, second], project_context=project_context()
    )["stair_requirement_audits"][0]["fields"]["maximum_riser"]
    assert field["status"] == "resolved" and field["value"] == .17
    assert field["resolution_provenance"]["candidate_upper_bounds_m"] == [.18, .17]
    mismatched = deepcopy(second)
    mismatched["applicability"]["jurisdiction"] = "elsewhere"
    field = AuthoritativeStairRequirementsResolutionV1().resolve(
        demand(), project(), mismatched, project_context=project_context()
    )["stair_requirement_audits"][0]["fields"]["maximum_riser"]
    assert field["status"] == "unresolved"
    assert "jurisdiction_mismatch" in field["rejection_reasons"][0]["reasons"]


def test_project_level_contract_exact_chain_feeds_spans_without_fixture_leakage():
    level_names = ["site_grade", "basement", "ground", "residential_floor_1",
                   "residential_floor_2", "roof", "stairhouse_top"]
    values = [0.0, -2.4, .3, 5.0, 8.24, 11.48, 14.18]
    confirmations = [{"kind": "level_elevation", "level": name, "value": value,
                      "unit": "m", "authority_class": "PROJECT_REQUIREMENT",
                      "provenance": ["synthetic_human_confirmation"]}
                     for name, value in zip(level_names, values)]
    levels = ProjectLevelContractV1().resolve(confirmations=confirmations)
    scope = ("basement", "ground", "residential_floor_1", "residential_floor_2",
             "roof", "stairhouse_top")
    result = AuthoritativeStairRequirementsResolutionV1().resolve(
        demand(scope), project(), minab_stair_evidence(), level_contract=levels,
        project_context=minab_context())
    spans = result["stair_requirement_audits"][0]["fields"]["floor_to_floor_spans"]
    assert spans["status"] == "resolved"
    assert [item["bottom"] for item in spans["value"]] == [-2.4, .3, 5.0, 8.24, 11.48, 14.18]
    assert all("level_contract.level_evidence" in item for item in spans["provenance"])
    assert "site_grade" not in [item["name"] for item in spans["value"]]
