from shapely.affinity import rotate, translate
from shapely.geometry import box, mapping

from core.architecture.reasoning.contextual_program_demand_profile_v1 import ContextualProgramDemandProfileV1
from core.architecture.reasoning.spatial_demand_sizing_and_capacity_v1 import SpatialDemandSizingAndCapacityV1
from core.architecture.reasoning.flexible_area_allocation_authority_v1 import FlexibleAreaAllocationAuthorityV1
from core.architecture.reasoning.resource_scarcity_and_competition_v1 import ResourceScarcityAndCompetitionV1
from core.architecture.reasoning.contextual_spatial_allocation_planner_v1 import ContextualSpatialAllocationPlannerV1


def profile(functions):
    return SpatialDemandSizingAndCapacityV1().resolve(ContextualProgramDemandProfileV1().build({"functions":functions}))


def resource(floors=("ground",),area=100,geometry=None):
    geometry=geometry or box(0,0,10,area/10)
    channels={name:{"value":1,"status":"known","provenance":["synthetic"],"confidence":1.0}
              for name in ("frontage_value","public_access_value","daylight_value","visibility_value",
                           "privacy_value","quietness_value","terrace_value")}
    return {"resources":[{"resource_id":"floor-domain","floor_scope":list(floors),"geometry_type":"Polygon",
        "geometry":mapping(geometry),"usable_capacity":area,"gross_capacity":geometry.area,
        "capacity_role":"floor_domain","capacity_unit":"m2","capacity_derivation":"synthetic_geometry",
        "capacity_provenance":["synthetic.floor_domain"],"capacity_confidence":1.0,"channels":channels}]}


def allocate(functions,resources=None):
    return FlexibleAreaAllocationAuthorityV1().allocate(resources or resource(),profile(functions))


def areas(result):
    return {f["function_id"]:f["spatial_sizing"].get("allocated_area_m2")
            for f in result["demand_profile"]["functions"]}


def test_one_claimant_gets_residual_after_nonflexible_reservations_not_count():
    result=allocate([{"function_id":"fixed","function":"living","required_capacity":20,"floor_scope":["ground"]},
        {"function_id":"shop","function":"commercial","quantity":7,"floor_scope":["ground"]}])
    assert areas(result)["shop"]==80
    assert result["floors"][0]["reserved_nonflexible_area"]==20
    assert result["count_is_area"] is False


def test_symmetric_claimants_equal_and_null_weight_remains_null():
    result=allocate([{"function_id":"a","function":"residential_unit","floor_scope":["ground"]},
                     {"function_id":"b","function":"residential_unit","floor_scope":["ground"]}])
    assert areas(result)=={"a":50,"b":50}
    assert result["floors"][0]["allocation_mode"]=="symmetry_preserving_equal"
    assert all(c["flexible_weight"] is None for c in result["floors"][0]["claimants"])
    assert result["floors"][0]["provenance"]==["symmetry_no_distinguishing_evidence"]


def test_asymmetric_claimants_without_valid_weights_fail_closed():
    result=allocate([{"function_id":"shop","function":"commercial","floor_scope":["ground"]},
                     {"function_id":"unit","function":"residential_unit","floor_scope":["ground"]}])
    assert areas(result)=={"shop":None,"unit":None}
    assert {x["reason"] for x in result["unresolved"]}=={"asymmetric_claimants_without_valid_allocation_evidence"}


def test_explicit_target_and_bounds_are_respected():
    result=allocate([{"function_id":"target","function":"commercial","floor_scope":["ground"],"sizing_mode":"FLEXIBLE_AREA_DEMAND",
        "minimum_area":20,"maximum_area":40,"target_area":30}])
    assert areas(result)["target"]==30
    assert result["floors"][0]["claimants"][0]["bounds_m2"]=={"minimum":20,"maximum":40,"target":30}


def test_separate_floors_allocate_independently():
    resources={"resources":[resource(("a",),60)["resources"][0],
        {**resource(("b",),40)["resources"][0],"resource_id":"floor-b","usable_capacity":40,
         "geometry":mapping(box(0,0,8,5)),"gross_capacity":40}]}
    result=allocate([{"function_id":"fa","function":"commercial","floor_scope":["a"]},
                     {"function_id":"fb","function":"commercial","floor_scope":["b"]}],resources)
    assert areas(result)=={"fa":60,"fb":40}


def test_over_constrained_floor_fails_closed():
    result=allocate([{"function_id":"fixed","function":"living","required_capacity":110,"floor_scope":["ground"]},
                     {"function_id":"shop","function":"commercial","floor_scope":["ground"]}])
    assert areas(result)["shop"] is None
    assert result["unresolved"][0]["reason"]=="over_constrained_floor"


def test_multifloor_flexible_demand_is_deferred_without_blocking_floor_claimants():
    resources=resource(("ground","upper"),100)
    result=allocate([{"function_id":"stair","function":"stair","floor_scope":["ground","upper"]},
                     {"function_id":"elevator","function":"elevator","floor_scope":["ground","upper"],"dimensions":[2,5]},
                     {"function_id":"shop","function":"commercial","floor_scope":["ground"]},
                     {"function_id":"unit","function":"residential_unit","floor_scope":["upper"]}],resources)
    assert areas(result)=={"stair":None,"elevator":None,"shop":90,"unit":90}
    assert all(row["reserved_nonflexible_area"]==10 for row in result["floors"])
    assert result["unresolved"]==[{"function_id":"stair","floor_id":None,
        "reason":"multi_floor_flexible_demand_requires_distinct_sizing_authority"}]


def test_numeric_weight_is_not_silently_accepted_but_evidence_weight_is():
    bad=allocate([{"function_id":"a","function":"commercial","floor_scope":["ground"],"flexible_weight":2},
                  {"function_id":"b","function":"residential_unit","floor_scope":["ground"],"flexible_weight":1}])
    assert areas(bad)=={"a":None,"b":None}
    weight=lambda value:{"value":value,"unit":"ratio","provenance":["explicit.synthetic.weight"],"confidence":1}
    good=allocate([{"function_id":"a","function":"commercial","floor_scope":["ground"],"flexible_weight":weight(3)},
                   {"function_id":"b","function":"residential_unit","floor_scope":["ground"],"flexible_weight":weight(1)}])
    assert areas(good)=={"a":75,"b":25}
    assert good["floors"][0]["allocation_mode"]=="evidence_weighted"


def test_deterministic_rotation_translation_invariant_areas_and_provenance_units_preserved():
    functions=[{"function_id":"a","function":"residential_unit","floor_scope":["ground"]},
               {"function_id":"b","function":"residential_unit","floor_scope":["ground"]}]
    base=box(0,0,10,10); transformed=translate(rotate(base,37,origin="centroid"),123,-91)
    first=allocate(functions,resource(geometry=base)); second=allocate(functions,resource(geometry=transformed))
    assert areas(first)==areas(second)=={"a":50,"b":50}
    assert first["floors"][0]["provenance"]==second["floors"][0]["provenance"]
    assert first["area_unit"]==second["area_unit"]=="m2"


def test_planner_consumes_shared_domain_capacity_independently_by_floor():
    resources=resource(("ground","upper"),100)
    allocation=allocate([{"function_id":"shop","function":"commercial","floor_scope":["ground"]},
                         {"function_id":"unit","function":"residential_unit","floor_scope":["upper"]}],resources)
    demand=allocation["demand_profile"]
    scarcity=ResourceScarcityAndCompetitionV1().evaluate(resources,demand)
    plan=ContextualSpatialAllocationPlannerV1().plan(resources,demand,scarcity,max_hypotheses=1)
    assert {x["function_id"] for x in plan["hypotheses"][0]["assignments"]}=={"shop","unit"}
    assert plan["hypotheses"][0]["resource_consumption_by_floor"]==[
        {"resource_id":"floor-domain","floor_id":"ground","consumed_capacity":100},
        {"resource_id":"floor-domain","floor_id":"upper","consumed_capacity":100}]
