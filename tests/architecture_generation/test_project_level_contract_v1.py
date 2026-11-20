from copy import deepcopy

from core.architecture.reasoning.project_level_contract_v1 import ProjectLevelContractV1


def elevation(level, value):
    return {"kind": "level_elevation", "level": level, "value": value, "unit": "m",
            "authority_class": "PROJECT_REQUIREMENT", "provenance": ["human_confirmation"]}


def span(lower, upper, value):
    return {"kind": "floor_to_floor_span", "from_level": lower, "to_level": upper,
            "value": value, "unit": "m", "authority_class": "PROJECT_REQUIREMENT",
            "provenance": ["human_confirmation"]}


def test_human_confirmed_spans_build_an_exact_elevation_chain():
    result = ProjectLevelContractV1().resolve(confirmations=[
        elevation("ground", 0.0), span("ground", "residential_floor_1", 3.3),
        span("residential_floor_1", "residential_floor_2", 3.2)])
    assert result["status"] == "resolved"
    assert result["exact_levels"] == {"ground": 0.0, "residential_floor_1": 3.3,
                                      "residential_floor_2": 6.5}
    assert result["authoritative_stair_level_contract"] == result["exact_levels"]


def test_ranges_never_become_exact_levels_or_ramp_authority():
    hypothesis = {"range": {"min": 3.1, "max": 3.6}, "status": "hypothesis_not_exact_level"}
    result = ProjectLevelContractV1().resolve(range_hypotheses=[hypothesis])
    assert result["exact_levels"] == {}
    assert result["range_hypotheses"] == [hypothesis]
    assert result["range_hypotheses_authoritative"] is False
    assert result["ramp_level_dependency"]["status"] == "unresolved"


def test_ramp_level_readiness_is_separate_from_integration_validation():
    result = ProjectLevelContractV1().resolve(confirmations=[
        elevation("ground", 0.0), elevation("basement", -2.4)])
    ramp = result["ramp_level_dependency"]
    assert ramp["status"] == "resolved" and ramp["level_span"] == 2.4
    assert ramp["authoritative_for_geometry"] is True
    assert ramp["placement_slope_parking_integration_validated"] is False


def test_conflict_fails_closed_and_suppresses_downstream_contracts():
    result = ProjectLevelContractV1().resolve(confirmations=[
        elevation("ground", 0.0), elevation("first", 3.4), span("ground", "first", 3.2)])
    assert result["status"] == "conflicted"
    assert result["exact_levels"] == {}
    assert result["authoritative_stair_level_contract"] is None
    assert result["ramp_level_dependency"]["status"] == "unresolved"


def test_non_authoritative_or_unproven_confirmation_is_rejected_and_input_is_unchanged():
    records = [{"kind": "level_elevation", "level": "ground", "value": 0.0,
                "authority_class": "HUMAN_CONFIRMED_DESIGN_RANGE", "provenance": ["knowledge"]},
               {"kind": "level_elevation", "level": "first", "value": 3.2,
                "authority_class": "PROJECT_REQUIREMENT", "provenance": []}]
    frozen = deepcopy(records)
    result = ProjectLevelContractV1().resolve(confirmations=records)
    assert len(result["rejected_confirmations"]) == 2
    assert result["exact_levels"] == {} and records == frozen


def test_explicit_ramp_endpoints_override_ground_ffl_without_validating_integration():
    result = ProjectLevelContractV1().resolve(confirmations=[
        elevation("site_grade", 0.0), elevation("ramp_start", 0.0),
        elevation("basement", -2.4), elevation("ramp_arrival", -2.4),
        elevation("ground", 0.3), span("basement", "ground", 2.7)])
    ramp = result["ramp_level_dependency"]
    assert ramp["required_levels"] == ["ramp_start", "ramp_arrival"]
    assert ramp["level_span"] == 2.4
    assert ramp["endpoint_source"] == "explicit_project_ramp_endpoints"
    assert ramp["placement_slope_parking_integration_validated"] is False


def test_confirmed_full_chain_is_deterministic_consistent_and_semantically_distinct():
    confirmations = [
        elevation("site_grade", 0.0), elevation("ramp_start", 0.0),
        elevation("basement", -2.4), elevation("ramp_arrival", -2.4),
        elevation("ground", 0.3), span("basement", "ground", 2.7),
        span("ground", "residential_floor_1", 4.7),
        elevation("residential_floor_1", 5.0),
        span("residential_floor_1", "residential_floor_2", 3.24),
        elevation("residential_floor_2", 8.24),
        span("residential_floor_2", "roof", 3.24), elevation("roof", 11.48),
        elevation("stairhouse_base", 11.48),
        span("stairhouse_base", "stairhouse_top", 2.7),
        elevation("stairhouse_top", 14.18)]
    semantics = {
        "authority_class": "PROJECT_REQUIREMENT",
        "provenance": ["human_confirmed_project_requirement"],
        "basement_clear_height_m": 2.4,
        "grade_is_not_ground_ffl": True,
        "basement_clear_height_is_not_floor_to_floor_span": True,
        "ramp_start_is_not_ground_ffl": True,
        "roof_is_real_level": True,
        "stairhouse_is_roof_superstructure_not_residential_floor": True,
    }
    resolver = ProjectLevelContractV1()
    first = resolver.resolve(confirmations=confirmations, project_semantics=semantics)
    second = resolver.resolve(confirmations=confirmations, project_semantics=semantics)
    assert first == second and first["status"] == "resolved"
    assert first["conflicts"] == []
    assert first["exact_levels"]["ground"] == .3
    assert first["exact_levels"]["residential_floor_1"] == 5.0
    assert first["exact_levels"]["residential_floor_2"] == 8.24
    assert first["exact_levels"]["roof"] == 11.48
    assert first["project_semantics"]["status"] == "resolved"
    assert first["project_semantics"]["authority_class"] == "PROJECT_REQUIREMENT"
