from copy import deepcopy
import inspect

from core.architecture.reasoning.contextual_level_height_and_floor_assembly_v1 import (
    ContextualLevelHeightAndFloorAssemblyV1,
)


def assembly():
    return {"evidence_id": "assembly", "component": "floor_assembly_thickness",
            "range": {"min": .20, "max": .30}, "unit": "m",
            "authority_class": "PROJECT_REQUIREMENT", "provenance": ["synthetic_project"]}


def test_taxonomy_ranges_and_no_implicit_floor_to_floor_default():
    out = ContextualLevelHeightAndFloorAssemblyV1().resolve({"occupancies": ["commercial", "residential"]})
    assert set(out["fields"]) == set(ContextualLevelHeightAndFloorAssemblyV1.COMPONENTS)
    assert out["floor_to_floor"]["status"] == "partial_unresolved"
    assert out["floor_to_floor"]["hypotheses"] == []
    assert "compatible_usable_height_and_floor_assembly_thickness" in out["unresolved_inputs"]


def test_floor_to_floor_uses_only_compatible_height_and_assembly_components():
    out = ContextualLevelHeightAndFloorAssemblyV1().resolve(
        {"occupancies": ["commercial"], "evidence": [assembly()]})
    hypothesis = out["floor_to_floor"]["hypotheses"][0]
    assert hypothesis["range"] == {"min": 3.8, "max": 5.0}
    assert "finished_floor_raise_above_road" in out["floor_to_floor"]["excluded_components"]
    assert out["project_level_contract"]["authoritative_stair_level_contract"] is None


def test_drainage_raise_requires_future_contextual_site_evidence_and_is_not_assembly():
    resolver = ContextualLevelHeightAndFloorAssemblyV1()
    blocked = resolver.resolve({"occupancies": ["commercial"]})
    raise_field = blocked["fields"]["finished_floor_raise_above_road"]
    assert raise_field["status"] == "unresolved" and raise_field["rejected_candidates"]
    applicable = resolver.resolve({"occupancies": ["commercial"], "drainage_context": {
        "status": "applicable", "site_runoff_risk": True, "provenance": ["future_site_survey"]}})
    assert applicable["fields"]["finished_floor_raise_above_road"]["candidates"][0]["range"] == {"min": .1, "max": .2}


def test_basement_relation_and_residential_plinth_remain_independent():
    out = ContextualLevelHeightAndFloorAssemblyV1().resolve({"occupancies": ["residential", "basement"]})
    assert out["fields"]["finished_floor_raise_above_grade"]["candidates"][0]["range"] == {"min": .36, "max": .4}
    assert out["fields"]["basement_ceiling_above_grade"]["candidates"][0]["range"] == {"min": .2, "max": 1.4}


def test_exact_project_levels_can_feed_stairs_but_ranges_cannot():
    levels = {"authority_class": "PROJECT_REQUIREMENT", "provenance": ["signed_project_brief"],
              "levels": {"basement": -2.4, "ground": 0.0, "first": 4.2}}
    out = ContextualLevelHeightAndFloorAssemblyV1().resolve({"level_contract": levels})
    assert out["project_level_contract"]["authoritative_stair_level_contract"] == {
        "basement": -2.4, "ground": 0.0, "first": 4.2}
    assert out["project_level_contract"]["contract"] == "ProjectLevelContractV1"
    assert out["project_level_contract"]["ramp_level_dependency"]["status"] == "resolved"


def test_deterministic_non_mutating_and_source_has_no_direction_or_geometry_runtime():
    source = {"occupancies": ["commercial"], "evidence": [assembly()]}
    frozen = deepcopy(source); resolver = ContextualLevelHeightAndFloorAssemblyV1()
    assert resolver.resolve(source) == resolver.resolve(source) and source == frozen
    code = inspect.getsource(ContextualLevelHeightAndFloorAssemblyV1).lower()
    assert "3.2" not in code
    assert not any(token in code for token in ("north", "south", "parcel2", "svg", "ifc", "render_runtime", "geometry_runtime"))
