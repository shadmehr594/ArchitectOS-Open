from copy import deepcopy

from core.architecture.reasoning.elevator_regulation_requirement_reasoning_v1 import (
    ElevatorRegulationRequirementReasoningV1,
)


LEVELS = {
    "contract": "ProjectLevelContractV1",
    "exact_levels": {
        "site_grade": 0.0,
        "ramp_start": 0.0,
        "basement": -2.4,
        "ramp_arrival": -2.4,
        "ground": 0.3,
        "residential_floor_1": 5.0,
        "residential_floor_2": 8.24,
        "roof": 11.48,
        "stairhouse_base": 11.48,
        "stairhouse_top": 14.18,
    },
}


def regulation(threshold=7.0, comparison="greater_than", datum="ground"):
    return {
        "rule_id": "synthetic_elevator_height_acceptance_rule",
        "authority_class": "HARD_REGULATION",
        "source_reference": "synthetic://acceptance-only/not-project-evidence",
        "provenance": ["synthetic_acceptance_test"],
        "evidence_path": "synthetic.regulations.elevator_height",
        "threshold_m": threshold,
        "comparison": comparison,
        "measurement_datum_level": datum,
    }


def resolve(**overrides):
    arguments = {
        "level_contract": LEVELS,
        "building_type": "mixed_use",
        "requirements": [],
        "regulation_evidence": None,
    }
    arguments.update(overrides)
    return ElevatorRegulationRequirementReasoningV1().resolve(**arguments)


def test_parcel_chain_without_internal_regulation_uses_only_semantic_trigger():
    result = resolve()
    assert result["elevator_required"] is True
    assert result["regulatory_height_trigger"]["status"] == "regulation_input_required"
    assert result["regulatory_height_trigger"]["triggered"] is False
    assert [item["trigger"] for item in result["active_triggers"]] == [
        "multilevel_commercial_semantic"
    ]


def test_height_uses_highest_occupiable_floor_and_excludes_roof_and_stairhouse():
    result = resolve(building_type="residential", regulation_evidence=regulation())
    context = result["occupiable_height_context"]
    assert context["highest_occupiable_level"] == "residential_floor_2"
    assert result["regulatory_height_trigger"]["measured_height_m"] == 7.94
    assert result["regulatory_height_trigger"]["triggered"] is True


def test_threshold_boundary_below_equal_and_above_for_strict_comparison():
    base = {"exact_levels": {"ground": 0.0, "residential_floor_1": 0.0}}
    outcomes = []
    for elevation in (6.99, 7.0, 7.01):
        levels = deepcopy(base)
        levels["exact_levels"]["residential_floor_1"] = elevation
        outcomes.append(resolve(
            level_contract=levels,
            building_type="residential",
            regulation_evidence=regulation(),
        )["regulatory_height_trigger"]["triggered"])
    assert outcomes == [False, False, True]


def test_equal_boundary_can_be_inclusive_only_when_evidence_says_so():
    levels = {"exact_levels": {"ground": 0.0, "residential_floor_1": 7.0}}
    result = resolve(
        level_contract=levels,
        building_type="residential",
        regulation_evidence=regulation(comparison="greater_than_or_equal"),
    )
    assert result["regulatory_height_trigger"]["triggered"] is True


def test_multiple_triggers_keep_separate_reason_codes_and_evidence_paths():
    result = resolve(regulation_evidence=regulation())
    assert {item["reason_code"] for item in result["active_triggers"]} == {
        "ELEVATOR_REQUIRED_MULTILEVEL_COMMERCIAL_SEMANTIC",
        "ELEVATOR_REQUIRED_REGULATORY_HEIGHT",
    }
    assert len({item["evidence_path"] for item in result["active_triggers"]}) == 2
    assert result["elevator_count"] is None
    assert result["elevator_capacity"] is None


def test_invalid_or_missing_source_cannot_create_regulatory_trigger():
    invalid = regulation()
    invalid.pop("source_reference")
    result = resolve(building_type="residential", regulation_evidence=invalid)
    assert result["elevator_required"] is False
    assert result["regulatory_height_trigger"]["status"] == "invalid_regulation_input"


def test_deterministic_and_does_not_mutate_inputs():
    levels = deepcopy(LEVELS)
    evidence = regulation()
    before = deepcopy((levels, evidence))
    engine = ElevatorRegulationRequirementReasoningV1()
    first = engine.resolve(levels, "mixed_use", [], evidence)
    second = engine.resolve(levels, "mixed_use", [], evidence)
    assert first == second
    assert (levels, evidence) == before
    assert first["input_mutated"] is False
    assert first["geometry_generated"] is False
