import copy
from core.architecture.reasoning.project_planning_control_inputs_v1 import ProjectPlanningControlInputsV1
from core.architecture.reasoning.minab_local_commercial_validator_v1 import MinabLocalCommercialValidatorV1


class PassNational:
    def validate(self, fields):
        return {"status": "pass", "input_overwritten": False, "findings": []}


def run(values, local=None):
    return ProjectPlanningControlInputsV1().resolve(values, local or MinabLocalCommercialValidatorV1(), PassNational())


def complete(**changes):
    values = {"allowed_FAR": 180, "max_site_coverage": 60, "commercial_area_target": 65,
              "commercial_use_type": "commercial_service_land", "local_regulation_jurisdiction": "MINAB_LOCAL_ONLY"}
    values.update(changes)
    return values


def test_missing_controls_are_unresolved_human_inputs():
    result = run({})
    assert result["status"] == "unresolved"
    assert all(x["human_input_required"] for x in result["fields"].values())


def test_user_values_are_preserved_as_project_requirements_without_mutation_and_deterministically():
    values = complete()
    before = copy.deepcopy(values)
    first, second = run(values), run(values)
    assert values == before and first == second
    assert all(item["authority_class"] == "PROJECT_REQUIREMENT" for item in first["fields"].values())
    assert [first["fields"][key]["value"] for key in values] == list(values.values())


def test_minab_floating_over_100_requires_case_specific_article_5_approval():
    result = run(complete(commercial_area_target=120, commercial_use_type="floating_commercial_eligible_axis"))
    assert result["status"] == "approval_required"
    assert "ARTICLE_5_CASE_SPECIFIC_APPROVAL_REQUIRED" in result["local_validation"]["findings"]


def test_minab_validator_reports_conflict_without_overwriting_input():
    values = complete(commercial_area_target=19, commercial_use_type="residential_land_neighborhood_exception")
    result = run(values)
    assert result["status"] == "conflict" and result["fields"]["commercial_area_target"]["value"] == 19


def test_commercial_land_over_100_is_not_automatically_invalid():
    result = run(complete(commercial_area_target=500, commercial_use_type="commercial_service_land"))
    assert result["status"] == "pass"
    assert "NO_GLOBAL_100_M2_CAP_LOCAL_ZONING_CONTROLS_APPLY" in result["local_validation"]["findings"]


def test_other_jurisdiction_does_not_apply_minab_rules():
    result = run(complete(commercial_area_target=120, commercial_use_type="floating_commercial_eligible_axis", local_regulation_jurisdiction="TEHRAN_LOCAL"))
    assert result["status"] == "pass" and result["local_validation"]["applicable"] is False


def coverage(id, floor_scope, use, value):
    return {"id": id, "floor_scope": floor_scope, "use": use, "value_percent": value,
            "authority_class": "PROJECT_DESIGN_CONFIRMATION", "source_reference": "test://user-confirmation",
            "provenance": ["explicit_test_confirmation"], "applicability": {"project_id": "parcel_2"}}


def test_mixed_use_coverage_is_floor_aware_and_never_emits_global_scalar():
    values = complete(max_site_coverage=None, coverage_controls=[
        coverage("ground", ["ground"], "commercial", 100),
        coverage("upper", ["upper_residential_floors"], "residential", 100),
    ])
    first, second = run(values), run(values)
    assert first == second
    assert first["fields"]["max_site_coverage"]["value"] is None
    assert first["fields"]["max_site_coverage"]["status"] == "not_applicable_floor_aware_controls_present"
    assert [x["value_percent"] for x in first["fields"]["coverage_controls"]["value"]] == [100, 100]


def test_legacy_scalar_remains_explicit_only_and_no_coverage_default_is_created():
    legacy = run(complete())
    assert legacy["fields"]["max_site_coverage"]["value"] == 60
    assert legacy["fields"]["coverage_controls"]["value"] == []


def test_project_specific_100_100_does_not_become_a_validator_default():
    controls = [coverage("ground", ["ground"], "commercial", 100), coverage("upper", ["upper_residential_floors"], "residential", 100)]
    result = run(complete(max_site_coverage=None, coverage_controls=controls))
    assert result["fields"]["coverage_controls"]["value"] == controls
    assert result["fields"]["max_site_coverage"]["value"] is None
    assert result["defaults_applied"] is False
    assert result["local_validation"]["input_overwritten"] is False
