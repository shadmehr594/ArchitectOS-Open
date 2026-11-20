import inspect

from shapely.geometry import LineString, Polygon, mapping

from core.architecture.reasoning.contextual_program_demand_profile_v1 import ContextualProgramDemandProfileV1
from core.architecture.reasoning.contextual_spatial_allocation_planner_v1 import ContextualSpatialAllocationPlannerV1


CHANNELS=("frontage_value","public_access_value","daylight_value","visibility_value",
          "privacy_value","quietness_value","terrace_value","commercial_value")


def _channels(frontage=0):
    return {name:{"value":frontage if name=="frontage_value" else 0,"status":"known",
                  "source":"synthetic","provenance":[name],"confidence":1.0} for name in CHANNELS}


def _resource(rid,geometry,capacity,frontage=0,floors=("level",)):
    return {"resource_id":rid,"geometry":mapping(geometry),"geometry_type":geometry.geom_type,
            "floor_scope":list(floors),"usable_capacity":capacity,"channels":_channels(frontage)}


def _demand(function="commercial"):
    return ContextualProgramDemandProfileV1().build({"functions":[{
        "function_id":"function","function":function,"floor_scope":["level"],"required_capacity":2}]})


def _plan(resources,function="commercial"):
    return ContextualSpatialAllocationPlannerV1().plan({"resources":resources},_demand(function),{"resources":[]},max_hypotheses=4)


def test_area_occupancy_cannot_use_line_as_host():
    plan=_plan([_resource("frontage",LineString([(0,0),(5,0)]),5,1)])
    assert all(not hypothesis["assignments"] for hypothesis in plan["hypotheses"])
    assert all(hypothesis["unresolved_demands"]==[{"function_id":"function","reason":"no_selected_known_capacity"}]
               for hypothesis in plan["hypotheses"])


def test_line_benefit_is_preserved_as_attachment_to_areal_host():
    resources=[_resource("host",Polygon([(0,0),(5,0),(5,4),(0,4)]),20),
               _resource("frontage",LineString([(0,0),(5,0)]),5,1)]
    assignment=next(h["assignments"][0] for h in _plan(resources)["hypotheses"] if h["assignments"])
    assert assignment["resource_id"]=="host"
    assert assignment["spatial_requirement"]=="AREA_OCCUPANCY"
    assert assignment["resource_attachments"]==[{"resource_id":"frontage","geometry_type":"LineString","role":"resource_benefit","utility":1.0}]


def test_linear_route_accepts_route_compatible_geometry():
    plan=_plan([_resource("route",LineString([(0,0),(5,0)]),5)],"vehicle_circulation")
    assignment=next(h["assignments"][0] for h in plan["hypotheses"] if h["assignments"])
    assert assignment["resource_id"]=="route" and assignment["spatial_requirement"]=="LINEAR_ROUTE"


def test_context_change_in_line_benefit_changes_area_allocation():
    left=Polygon([(0,0),(4,0),(4,4),(0,4)]); right=Polygon([(6,0),(10,0),(10,4),(6,4)])
    first=[_resource("left",left,16),_resource("right",right,16),_resource("edge",LineString([(0,0),(4,0)]),4,1)]
    second=[_resource("left",left,16),_resource("right",right,16),_resource("edge",LineString([(6,0),(10,0)]),4,1)]
    def selected(resources):
        return next(h["assignments"][0]["resource_id"] for h in _plan(resources)["hypotheses"] if h["assignments"])
    assert selected(first)=="left" and selected(second)=="right"


def test_planner_source_has_no_orientation_or_parcel_branch():
    source=inspect.getsource(ContextualSpatialAllocationPlannerV1).lower()
    assert "parcel2" not in source and "parcel 2" not in source
    assert all(('"%s"'%value) not in source and ("'%s'"%value) not in source
               for value in ("north","east","south","west","ns","ew","hybrid"))
