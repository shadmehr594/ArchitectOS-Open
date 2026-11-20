from copy import deepcopy

from core.architecture.reasoning.programmatic_level_necessity_and_alternative_reasoning_v1 import (
    ProgrammaticLevelNecessityAndAlternativeReasoningV1,
)


MINIMUM = {"value": 3, "authority_class": "PROJECT_REQUIREMENT", "provenance": ["synthetic"]}


def capacity(value=3, authority="AUTHORITATIVE_PROJECT_FACT"):
    return {"value": value, "semantic": "authoritative_achieved_capacity",
            "authority_class": authority, "provenance": ["validated_result"]}


def function(fid="parking", requirement="mandatory", satisfaction="satisfied"):
    return {"function_id": fid, "requirement_status": requirement,
            "satisfaction_status": satisfaction, "evidence": ["program"]}


def hypothesis(hid="H1", basement="eliminated", achieved=None, basement_functions=None,
               displacement=None, ramp_required=False):
    return {"hypothesis_id": hid, "basement_status": basement,
            "achieved_parking_capacity": achieved,
            "functions_assigned": {"basement": basement_functions or [function()], "pilotis": []},
            "pilotis_displacement": displacement or [],
            "ramp_dependency": {"status": "resolved", "required": ramp_required,
                                "evidence": ["hypothesis_level_assignment"]},
            "qualitative_impacts": [
                {"impact_id": "ramp_removed", "direction": "benefit", "evidence": ["ramp_not_required"]},
                {"impact_id": "excavation_removed", "direction": "benefit", "evidence": []},
            ]}


def evaluate(items, selection=None):
    return ProgrammaticLevelNecessityAndAlternativeReasoningV1().evaluate(
        [function()], MINIMUM, items, selection)


def test_h1_pilotis_three_only_parking_supports_low_necessity_but_does_not_select():
    row = evaluate([hypothesis(achieved=capacity())])["comparison_matrix"][0]
    assert row["hypothesis_support"] == "programmatically_supported"
    assert row["basement_necessity_status"] == "not_required_candidate"
    assert row["selection"] == {"status": "not_selected", "selected": False,
                                "authority_class": None, "project_decision": False}


def test_mandatory_mechanical_blocks_elimination_without_valid_relocation():
    funcs = [function(), function("mechanical", "mandatory", "unsatisfied")]
    row = evaluate([hypothesis(achieved=capacity(), basement_functions=funcs)])["comparison_matrix"][0]
    assert row["hypothesis_support"] == "programmatically_disfavored"
    assert row["basement_necessity_status"] == "required"
    assert row["basement_functions"]["unsatisfied"] == ["mechanical"]


def test_unknown_basement_function_makes_elimination_unresolved():
    funcs = [function(), function("unknown_service", "unknown", "unknown")]
    row = evaluate([hypothesis(achieved=capacity(), basement_functions=funcs)])["comparison_matrix"][0]
    assert row["hypothesis_support"] == "unresolved"
    assert row["basement_necessity_status"] == "unresolved"


def test_pilotis_two_below_minimum_rejects_h1():
    row = evaluate([hypothesis(achieved=capacity(2))])["comparison_matrix"][0]
    assert row["parking_satisfaction"]["status"] == "unsatisfied"
    assert row["hypothesis_support"] == "programmatically_disfavored"


def test_mandatory_pilotis_displacement_rejects_h1():
    displaced = [function("entrance_lobby", "mandatory", "unsatisfied")]
    row = evaluate([hypothesis(achieved=capacity(), displacement=displaced)])["comparison_matrix"][0]
    assert row["pilotis_displacement"][0]["status"] == "unsatisfied"
    assert row["hypothesis_support"] == "programmatically_disfavored"


def test_h2_basement_parking_is_feasible_and_pilotis_release_requires_evidence():
    h2 = hypothesis("H2", "retained", capacity(), ramp_required=True)
    h2["qualitative_impacts"] = [{"impact_id": "pilotis_released", "direction": "benefit", "evidence": []}]
    row = evaluate([h2])["comparison_matrix"][0]
    assert row["hypothesis_support"] == "programmatically_supported"
    assert row["ramp_dependency"]["required"] is True
    assert row["qualitative_opportunity_costs_and_benefits"][0]["evidence_status"] == "assumption_or_unresolved"


def test_both_feasible_produce_deterministic_matrix_without_auto_selection():
    items = [hypothesis("H2", "retained", capacity(), ramp_required=True),
             hypothesis("H1", "eliminated", capacity())]
    first, second = evaluate(items), evaluate(items)
    assert first == second
    assert [x["hypothesis_id"] for x in first["comparison_matrix"]] == ["H1", "H2"]
    assert all(not x["selection"]["selected"] for x in first["comparison_matrix"])
    assert first["auto_selection_performed"] is False


def test_candidate_or_feasible_capacity_never_leaks_into_authoritative_capacity():
    for authority in ("DESIGN_CANDIDATE", "FEASIBLE_RESULT", None):
        row = evaluate([hypothesis(achieved=capacity(3, authority))])["comparison_matrix"][0]
        assert row["parking_satisfaction"]["authoritative_achieved"] is None
        assert row["parking_satisfaction"]["status"] == "unresolved"
        assert row["hypothesis_support"] == "unresolved"


def test_h3_missing_mixed_capacity_is_unresolved_and_runs_are_pure():
    h3 = hypothesis("H3", "retained", None)
    h3["functions_assigned"]["basement"].append(function("mechanical", "optional", "satisfied"))
    items = [h3]; before = deepcopy(items)
    first, second = evaluate(items), evaluate(items)
    row = first["comparison_matrix"][0]
    assert row["hypothesis_support"] == "unresolved"
    assert first == second and items == before and first["input_mutated"] is False
    assert all(first[key] is False for key in ("geometry_generated", "structure_executed", "bim_executed",
                                                "ifc_executed", "render_executed", "image_generation_executed"))
