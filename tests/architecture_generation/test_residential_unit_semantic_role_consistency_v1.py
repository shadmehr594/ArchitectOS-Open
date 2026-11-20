import inspect

from shapely.geometry import Polygon, mapping

from core.architecture.reasoning.contextual_program_demand_profile_v1 import ContextualProgramDemandProfileV1
from core.architecture.reasoning.operational_relationship_requirement_derivation_v1 import FUNCTION_TAXONOMY
from core.architecture.reasoning.contextual_allocation_geometry_realizer_v1 import ContextualAllocationGeometryRealizerV1, ROLE


def _function(fid, floor):
    return {"function_id":fid,"function":"residential_unit","floor_scope":[floor],"required_capacity":4}


def test_residential_unit_is_known_consistently_across_three_layers():
    profile=ContextualProgramDemandProfileV1().build({"functions":[_function("unit","level")]})
    function=profile["functions"][0]
    assert function["status"]=="known"
    assert all(value["status"]=="fallback" for value in function["demands"].values())
    assert FUNCTION_TAXONOMY["residential_unit"]=={"roles":["RESIDENTIAL_UNIT"],"zone":"private"}
    assert ROLE["residential_unit"]=="RESIDENTIAL_UNIT"


def test_exact_one_then_two_residential_unit_envelopes_realize_without_unsupported_role():
    floors={"floor-1":[(0,0),(12,0),(12,8),(0,8)],"floor-2":[(0,0),(12,0),(12,8),(0,8)]}
    functions=[_function("floor-1-unit-1","floor-1"),_function("floor-2-unit-1","floor-2"),_function("floor-2-unit-2","floor-2")]
    profile=ContextualProgramDemandProfileV1().build({"functions":functions})
    resources=[]; assignments=[]
    for index,function in enumerate(functions):
        floor=function["floor_scope"][0]; rid="resource-%d"%index
        resources.append({"resource_id":rid,"geometry":mapping(Polygon(floors[floor])),"floor_scope":[floor]})
        assignments.append({"function_id":function["function_id"],"resource_id":rid,"consumed_capacity":4,"evidence":[]})
    plan={"hypotheses":[{"hypothesis_id":"schedule","assignments":assignments,"prerequisites":{}}]}
    result=ContextualAllocationGeometryRealizerV1().realize(plan,{"resources":resources},profile,
        {"additional_daylight_source_required":False},floors,relationship_contracts={"schedule":[]})
    candidate=result["candidates"][0]
    units=[space for space in candidate["geometry"] if space["occupancy_role"]=="RESIDENTIAL_UNIT"]
    assert sum("floor-1" in unit["floor_scope"] for unit in units)==1
    assert sum("floor-2" in unit["floor_scope"] for unit in units)==2
    assert "unsupported_function_role" not in candidate["hard_rejection_reasons"]


def test_residential_unit_support_adds_no_orientation_or_parcel_specific_branch():
    source=(inspect.getsource(ContextualProgramDemandProfileV1)+inspect.getsource(ContextualAllocationGeometryRealizerV1)).lower()
    assert "parcel2" not in source and "parcel 2" not in source
    assert all(('"%s"'%direction) not in source and ("'%s'"%direction) not in source
               for direction in ("north","east","south","west","ns","ew","hybrid"))
