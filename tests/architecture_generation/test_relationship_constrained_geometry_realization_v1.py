import inspect
from copy import deepcopy

from shapely.geometry import GeometryCollection, LineString, MultiLineString, Point, Polygon, mapping

from core.architecture.reasoning.relationship_constrained_geometry_realization_v1 import RelationshipConstrainedGeometryRealizationV1
from core.architecture.reasoning.spatial_relationship_and_operational_feasibility_v1 import SpatialRelationshipAndOperationalFeasibilityV1
from core.architecture.reasoning.operational_relationship_requirement_derivation_v1 import FUNCTION_TAXONOMY, RULES


def relation(kind,source,target,requirement,target_role="TARGET",floors=("level",),via=None):
    item={"relationship_type":kind,"source_function":source,"target_function":target,"target_role":target_role,
          "floor_scope":list(floors),"required":True,"source_requirement":requirement,"provenance":["synthetic"],"confidence":1.0}
    if via is not None:item["via_functions"]=via
    return item


def contract(relationships=(),unresolved=()):
    return {"contract":"OperationalRelationshipRequirementDerivationV1","hypotheses":[{
        "hypothesis_id":"h","relationship_requirements":list(relationships),"mandatory_unresolved":list(unresolved)}]}


def assignment(fid,attachments=()):
    return {"function_id":fid,"resource_id":"site","consumed_capacity":4,"utility":1,"evidence":[],"resource_attachments":list(attachments)}


def function(fid,kind="residential_unit",floors=("level",),operational=None):
    return {"function_id":fid,"function":kind,"floor_scope":list(floors),"operational_requirements":operational or {}}


def test_direct_access_constrains_placement_before_publication_and_gate_remains_independent():
    bridge=RelationshipConstrainedGeometryRealizationV1(); lobby=Polygon([(4,4),(6,4),(6,6),(4,6)])
    rel=relation("DIRECT_ACCESS","lobby","stair","core.lobby_stair_access","STAIR")
    plan=bridge.compile({"hypothesis_id":"h","assignments":[assignment("stair"),assignment("lobby")]},
        {"functions":[function("lobby","lobby"),function("stair","stair")]},contract([rel]),{"resources":[]})
    assert [a["function_id"] for a in plan["ordered_assignments"]][:2]==["lobby","stair"]
    available=Polygon([(0,0),(10,0),(10,10),(0,10)]).difference(lobby)
    constrained,evidence,failure=bridge.constrain_available("stair",available,{"lobby":lobby},plan["placement_constraints"],4)
    assert failure is None and evidence["constraints_applied"]==["USABLE_SHARED_BOUNDARY"]
    touching=Polygon([(4,2),(6,2),(6,4),(4,4)])
    proof,failure=bridge.verify_before_publication("stair",touching,{"lobby":lobby},plan["placement_constraints"])
    assert failure is None and proof["status"]=="pass"
    separated=Polygon([(0,0),(2,0),(2,2),(0,2)])
    _,failure=bridge.verify_before_publication("stair",separated,{"lobby":lobby},plan["placement_constraints"])
    assert failure=="relationship_prepublication_direct_access_failed"
    operational=SpatialRelationshipAndOperationalFeasibilityV1().evaluate([
        {"space_id":"lobby","polygon":list(lobby.exterior.coords)[:-1]},
        {"space_id":"stair","polygon":list(touching.exterior.coords)[:-1]}],
        [{"relationship_id":"direct","relationship":"DIRECT_ACCESS","from":"lobby","to":"stair","required":True}])
    assert operational["hard_validation_status"]=="hard_valid"


def test_residential_common_route_avoids_other_private_unit():
    bridge=RelationshipConstrainedGeometryRealizationV1()
    rel=relation("CONNECTED_BY_CIRCULATION","residential-a","lobby","residential.common_access","COMMON_CIRCULATION")
    plan=bridge.compile({"hypothesis_id":"h","assignments":[assignment("residential-a"),assignment("lobby")]},
        {"functions":[function("residential-a"),function("lobby","lobby")]},contract([rel]),{"resources":[]})
    placed={"residential-a":Polygon([(0,0),(2,0),(2,2),(0,2)]),"lobby":Polygon([(6,0),(8,0),(8,2),(6,2)])}
    generated,failures=bridge.realize_infrastructure(plan,placed,{}, {},{"level":[(0,0),(8,0),(8,4),(0,4)]})
    assert not failures and any(x["occupancy_role"]=="COMMON" and not x["program_room"] for x in generated)
    placed["residential-blocker"]=Polygon([(3,-1),(5,-1),(5,3),(3,3)])
    _,failures=bridge.realize_infrastructure(plan,placed,{}, {},{"level":[(0,0),(8,0),(8,4),(0,4)]})
    assert "route_crosses_forbidden_private_domain" in failures


def test_parking_derives_vehicle_infrastructure_not_program_room():
    bridge=RelationshipConstrainedGeometryRealizationV1()
    unresolved=relation("VEHICLE_ACCESSIBLE_FROM","parking",None,"parking.vehicle_access","VEHICLE_CIRCULATION")
    plan=bridge.compile({"hypothesis_id":"h","assignments":[assignment("parking")]},
        {"functions":[function("parking","parking",operational={"aisle_width":2})]},contract([], [unresolved]),{"resources":[]})
    spec=next(x for x in plan["derived_infrastructure"] if x["kind"]=="VEHICLE_CIRCULATION_FIELD")
    assert spec["program_room"] is False
    placed={"parking":Polygon([(3,3),(5,3),(5,5),(3,5)])}
    generated,failures=bridge.realize_infrastructure(plan,placed,{},
        {"parking":function("parking","parking",operational={"aisle_width":2})},{"level":[(0,0),(8,0),(8,8),(0,8)]})
    assert not failures and generated[0]["occupancy_role"]=="VEHICLE_CIRCULATION"
    assert generated[0]["program_room"] is False


def test_commercial_public_access_does_not_require_dedicated_entrance():
    bridge=RelationshipConstrainedGeometryRealizationV1()
    unresolved=relation("CONNECTED_BY_CIRCULATION","commercial",None,"commercial.public_access","PUBLIC_ACCESS_POINT")
    resources={"resources":[{"resource_id":"edge","geometry":mapping(LineString([(0,0),(8,0)])),
        "channels":{"public_access_value":{"status":"known","value":1}}}]}
    hypothesis={"hypothesis_id":"h","assignments":[assignment("commercial",[{"resource_id":"edge"}])]}
    plan=bridge.compile(hypothesis,{"functions":[function("commercial","commercial")]},contract([], [unresolved]),resources)
    access=next(x for x in plan["derived_infrastructure"] if x["kind"]=="PUBLIC_ACCESS_POINT")
    assert access["dedicated_entrance"] is False and access["program_room"] is False
    assert FUNCTION_TAXONOMY["public_pedestrian_entrance"]["roles"]==["PUBLIC_ACCESS_POINT","PUBLIC_PEDESTRIAN_ENTRANCE"]
    rule=next(x for x in RULES if x["source_requirement"]=="commercial.public_access")
    assert rule["target_role"]=="PUBLIC_ACCESS_POINT"


def test_vertical_alignment_and_impossible_relationship_are_prepublication_constraints():
    bridge=RelationshipConstrainedGeometryRealizationV1()
    vertical=relation("VERTICALLY_ALIGNED_WITH","stair","stair","vertical.required_scope","SELF_VERTICAL",("ground","upper"))
    missing=relation("DIRECT_ACCESS","lobby",None,"core.lobby_stair_access","STAIR")
    plan=bridge.compile({"hypothesis_id":"h","assignments":[assignment("stair")]},
        {"functions":[function("stair","stair",("ground","upper"))]},contract([vertical],[missing]),{"resources":[]})
    assert any(x["constraint_type"]=="VERTICAL_ALIGNMENT" and x["consumed_before_publication"] for x in plan["placement_constraints"])
    assert "relationship_constraint_unresolved" in plan["prepublication_failures"]
    assert plan["post_failure_relocation_allowed"] is False and plan["final_geometry_published"] is False


def test_bridge_source_has_no_orientation_parcel_coordinate_or_fixed_topology_titles():
    source=inspect.getsource(RelationshipConstrainedGeometryRealizationV1).lower()
    assert "parcel2" not in source and "parcel 2" not in source
    assert all(('"%s"'%token) not in source and ("'%s'"%token) not in source
               for token in ("north","east","south","west","ns","ew","hybrid"))
    assert all(token not in source for token in ("parcel2","parcel 2","fixed_offset","topology_family","buffer(0)"))


def infrastructure_plan(kind="PUBLIC_ACCESS_POINT"):
    return {"derived_infrastructure":[{"function_id":"derived","kind":kind,"resource_id":"resource",
        "floor_scope":["level"],"source_requirement":"synthetic"}]}


def realize_resource(geometry):
    bridge=RelationshipConstrainedGeometryRealizationV1(); plan=infrastructure_plan()
    generated,failures=bridge.realize_infrastructure(plan,{}, {"resource":geometry},{},{})
    return bridge,generated,failures


def test_polygon_publication_boundary_publishes():
    bridge,generated,failures=realize_resource(Polygon([(0,0),(2,0),(2,2),(0,2)]))
    assert not failures and generated[0]["geometry_mapping"]["type"]=="Polygon"
    assert bridge.infrastructure_publication_evidence[0]["status"]=="published"


def test_supported_linear_role_publishes_line_and_multiline():
    for geometry_type in (LineString([(0,0),(1,1)]),MultiLineString([[(0,0),(1,1)],[(2,2),(3,3)]])):
        _,generated,failures=realize_resource(geometry_type)
        assert not failures and generated[0]["geometry_mapping"]["type"]==geometry_type.geom_type


def test_valid_geometry_collection_fails_closed_with_deterministic_evidence():
    geometry=GeometryCollection([Polygon([(0,0),(2,0),(2,2),(0,2)]),LineString([(3,0),(3,2)])])
    first,generated,failures=realize_resource(geometry)
    second,generated_again,failures_again=realize_resource(geometry)
    assert generated==generated_again==[]
    assert failures==failures_again==["derived_infrastructure_unsupported_geometry_type"]
    assert first.infrastructure_publication_evidence==second.infrastructure_publication_evidence
    evidence=first.infrastructure_publication_evidence[0]
    assert evidence["geometry_type"]=="GeometryCollection"
    assert evidence["component_types"]==["Polygon","LineString"] and evidence["component_count"]==2
    assert evidence["is_valid"] is True and evidence["is_empty"] is False


def test_empty_geometry_collection_is_deterministic_and_fails_closed():
    bridge,generated,failures=realize_resource(GeometryCollection())
    assert generated==[] and failures==["derived_infrastructure_unsupported_geometry_type"]
    assert bridge.infrastructure_publication_evidence[0]["is_empty"] is True
    assert bridge.infrastructure_publication_evidence[0]["component_count"]==0


def test_unsupported_point_fails_closed_without_crash():
    bridge,generated,failures=realize_resource(Point(1,2))
    assert generated==[] and failures==["derived_infrastructure_unsupported_geometry_type"]
    assert bridge.infrastructure_publication_evidence[0]["geometry_type"]=="Point"


def test_publication_boundary_does_not_mutate_inputs():
    plan=infrastructure_plan(); placed={}; resources={"resource":GeometryCollection([Point(1,2)])}; functions={}; floors={}
    before=(deepcopy(plan),deepcopy(placed),deepcopy(resources),deepcopy(functions),deepcopy(floors))
    RelationshipConstrainedGeometryRealizationV1().realize_infrastructure(plan,placed,resources,functions,floors)
    assert plan==before[0] and placed==before[1] and resources==before[2] and functions==before[3] and floors==before[4]
