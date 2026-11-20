from shapely.geometry import mapping, box

from core.architecture.reasoning.contextual_program_demand_profile_v1 import ContextualProgramDemandProfileV1
from core.architecture.reasoning.spatial_demand_sizing_and_capacity_v1 import SpatialDemandSizingAndCapacityV1
from core.architecture.reasoning.resource_scarcity_and_competition_v1 import ResourceScarcityAndCompetitionV1
from core.architecture.reasoning.contextual_spatial_allocation_planner_v1 import ContextualSpatialAllocationPlannerV1
from core.architecture.reasoning.contextual_allocation_geometry_realizer_v1 import ContextualAllocationGeometryRealizerV1


def _profile(functions):
    demand=ContextualProgramDemandProfileV1().build({"functions":functions})
    return SpatialDemandSizingAndCapacityV1().resolve(demand)


def _resource():
    channels={name:{"value":1,"status":"known","provenance":["synthetic"],"confidence":1}
              for name in ("frontage_value","public_access_value","daylight_value","visibility_value",
                           "privacy_value","quietness_value","terrace_value")}
    return {"resources":[{"resource_id":"zone","floor_scope":["ground"],"geometry_type":"Polygon",
        "geometry":mapping(box(0,0,10,10)),"usable_capacity":100,"gross_capacity":100,"channels":channels}]}


def test_five_modes_are_explicit_and_count_never_becomes_area():
    profile=_profile([
        {"function_id":"route","function":"corridor","floor_scope":["ground"]},
        {"function_id":"fixed","function":"living","required_capacity":12,"floor_scope":["ground"]},
        {"function_id":"minimum","function":"stair","minimum_area":4,"floor_scope":["ground"]},
        {"function_id":"flex","function":"commercial","quantity":1,"floor_scope":["ground"]},
        {"function_id":"unit","function":"residential_unit","quantity":1,"floor_scope":["level-1"]},
        {"function_id":"derived","function":"parking","quantity":2,"dimensions":[2.5,5],"floor_scope":["ground"]},
    ])
    rows={x["function_id"]:x["spatial_sizing"] for x in profile["functions"]}
    assert {x["sizing_mode"] for x in rows.values()}=={
        "COUNT_ONLY","FIXED_AUTHORITATIVE_AREA","MINIMUM_FUNCTIONAL_AREA","FLEXIBLE_AREA_DEMAND","DERIVED_GEOMETRIC_FOOTPRINT"}
    assert rows["flex"]["count"]==1 and rows["flex"]["resolved_spatial_area"] is None
    assert rows["unit"]["count"]==1 and rows["unit"]["resolved_spatial_area"] is None
    assert rows["derived"]["derived_footprint"]==12.5
    assert rows["derived"]["resolved_spatial_area"]==25
    assert rows["derived"]["area_unit"]=="m2" and rows["derived"]["provenance"]


def test_scarcity_and_planner_preserve_unresolved_area_without_consuming_one_m2():
    profile=_profile([{"function_id":"shop","function":"commercial","quantity":1,"floor_scope":["ground"]}])
    scarcity=ResourceScarcityAndCompetitionV1().evaluate(_resource(),profile)
    assert all(row["weighted_demand"]==0 for row in scarcity["resources"])
    assert all("shop" in row["unresolved_spatial_demands"] for row in scarcity["resources"])
    plan=ContextualSpatialAllocationPlannerV1().plan(_resource(),profile,scarcity,max_hypotheses=1)
    hypothesis=plan["hypotheses"][0]
    assert hypothesis["assignments"]==[]
    assert hypothesis["unresolved_demands"]==[{"function_id":"shop","reason":"resolved_spatial_area_required"}]


def test_realizer_rejects_dimensionless_area_assignment_without_polygon():
    profile=_profile([{"function_id":"shop","function":"commercial","floor_scope":["ground"]}])
    plan={"hypotheses":[{"hypothesis_id":"bad","assignments":[{"function_id":"shop","resource_id":"zone",
        "spatial_requirement":"AREA_OCCUPANCY","consumed_capacity":1,"utility":0,"evidence":[]}],"prerequisites":{}}]}
    out=ContextualAllocationGeometryRealizerV1().realize(plan,_resource(),profile,
        {"additional_daylight_source_required":False},{"ground":[[0,0],[10,0],[10,10],[0,10]]},relationship_contracts=[])
    candidate=out["candidates"][0]
    assert candidate["geometry"]==[]
    assert "resolved_spatial_area_required" in candidate["hard_rejection_reasons"]
