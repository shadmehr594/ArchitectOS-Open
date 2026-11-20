from copy import deepcopy

from core.architecture.reasoning.architectural_spatial_quality_gate_v2 import ArchitecturalSpatialQualityGateV2


def space(sid, x0, y0, x1, y1, **extra):
    return {"id": sid, "name": sid, "floor": "F1", "required": True,
            "footprint": {"points": [[x0,y0],[x1,y0],[x1,y1],[x0,y1]], "width": x1-x0, "depth": y1-y0}, **extra}


def door(cid, a, b, wall="W1"):
    oid = "D-" + cid
    return {"id": oid, "opening_id": oid, "connection_id": cid, "type": "door", "geometry_status": "resolved",
            "host_wall_id": wall, "opening_center": [2,1], "opening_start": [2,.6], "opening_end": [2,1.4],
            "connects_from": a, "connects_to": b}


def connection(cid, a, b, door_required=True, **extra):
    return {"connection_id": cid, "from": a, "to": b, "from_space_id": a, "to_space_id": b,
            "required": True, "door_required": door_required, "geometry_status": "resolved_shared_boundary",
            "physical_connection_status": "resolved" if door_required else None, **extra}


def valid_geometry():
    d = door("C1", "entrance", "living")
    return {
        "spaces": [space("entrance",0,0,2,2), space("living",2,0,5,2)],
        "physical_walls": [{"wall_id":"W1", "is_exterior":False,
                            "physical_openings":[{"opening_id":d["opening_id"],"geometry_status":"resolved"}]}],
        "openings": [d],
        "spatial_connection_contract": {"connections":[connection("C1","entrance","living")]},
        "connections": [connection("C1","entrance","living")],
        "project_requirements": {}, "site_geometry": {}, "architectural_protected_zones": []}


def req(**extra):
    return {"enforce":True, "entrance_space":"entrance", "required_reachable_spaces":["living"],
            "isolation_exempt_spaces":[], **extra}


def evaluate(g=None, r=None): return ArchitecturalSpatialQualityGateV2().evaluate(g or valid_geometry(), r or req())
def kinds(result): return {x["type"] for x in result["critical_failures"]}


def test_fully_connected_valid_layout_passes(): assert evaluate()["status"] == "passed"


def test_required_connection_without_physical_door_fails():
    g=valid_geometry();g["openings"]=[]
    assert "required_connection_without_physical_opening" in kinds(evaluate(g))


def test_isolated_room_fails():
    g=valid_geometry();g["spaces"].append(space("bedroom",5,0,7,2))
    assert "isolated_space" in kinds(evaluate(g))


def test_entrance_disconnected_from_circulation_fails():
    g=valid_geometry();g["spatial_connection_contract"]={"connections":[]};g["connections"]=[];g["openings"]=[]
    assert "entrance_disconnected_from_circulation" in kinds(evaluate(g))


def test_door_to_nowhere_fails():
    g=valid_geometry();d=door("X","living","ghost");g["openings"].append(d);g["physical_walls"][0]["physical_openings"].append({"opening_id":"D-X","geometry_status":"resolved"})
    assert "door_to_nowhere" in kinds(evaluate(g))


def test_window_on_interior_wall_fails():
    g=valid_geometry();w={**door("WIN","living",None),"type":"window","served_space_id":"living","exterior_host_status":"resolved"};g["openings"].append(w);g["physical_walls"][0]["physical_openings"].append({"opening_id":"D-WIN","geometry_status":"resolved"})
    assert "invalid_physical_exterior_window" in kinds(evaluate(g))


def test_authoritative_required_window_missing_fails():
    g=valid_geometry();g["project_requirements"]={"window_requirements":[{"space_id":"living","required":True,"evidence_status":"authoritative"}]}
    assert "required_exterior_window_unresolved" in kinds(evaluate(g))


def test_incomplete_required_window_evidence_is_unresolved():
    g=valid_geometry();g["project_requirements"]={"window_requirements":[{"space_id":"living","required":True}]}
    assert evaluate(g)["status"] == "unresolved"


def test_bathroom_privacy_violation_fails_and_recommends_regeneration():
    g=valid_geometry();g["spatial_connection_contract"]["connections"][0]["privacy_violation"]=True
    r=evaluate(g);assert "privacy_violation" in kinds(r) and r["regeneration_recommended"]


def test_stair_geometry_without_interface_connection_fails():
    g=valid_geometry();g["spaces"].append(space("basement_lobby",5,0,7,2)|{"floor":"basement"});g["vertical_geometry"]=[{"id":"S1","type":"stair_geometry","geometry_status":"resolved"}]
    c=connection("CV","living","basement_lobby",False,geometry_status="resolved_vertical",vertical_system_id="S1")
    g["spatial_connection_contract"]["connections"].append(c)
    assert "vertical_system_interface_disconnected" in kinds(evaluate(g))


def test_parking_arrival_without_pedestrian_chain_is_unresolved():
    g=valid_geometry();g["project_requirements"]={"parking_pedestrian_requirements":[{"required":True}]};g["site_geometry"]={"parking_arrival":{"geometry_status":"resolved"}}
    assert evaluate(g)["status"] == "unresolved"


def test_full_parking_pedestrian_chain_passes_constraint():
    g=valid_geometry();g["project_requirements"]={"parking_pedestrian_requirements":[{"required":True}]};g["site_geometry"]={"parking_pedestrian_connection":{"connection_id":"PP1","geometry_status":"resolved","parking_to_building_status":"resolved","wall_conflict_status":"clear","stall_conflict_status":"clear","ramp_conflict_status":"clear","protected_zone_status":"clear","target_stair_core_id":"S1","vertical_connection_status":"resolved"}}
    assert evaluate(g)["status"] == "passed"


def test_circulation_through_ramp_protected_zone_fails():
    g=valid_geometry();g["circulation_paths"]=[{"polygon":[[1,0],[3,0],[3,1],[1,1]]}];g["architectural_protected_zones"]=[{"id":"R","type":"ramp_clearance","polygon":[[2,.2],[4,.2],[4,.8],[2,.8]]}]
    assert "circulation_intersects_protected_zone" in kinds(evaluate(g))


def test_resolved_opening_without_wall_interruption_fails():
    g=valid_geometry();g["physical_walls"][0]["physical_openings"]=[]
    assert "required_connection_without_physical_opening" in kinds(evaluate(g))


def test_circulation_path_through_solid_wall_fails():
    g=valid_geometry();g["physical_walls"].append({"wall_id":"W2","start":[3,-1],"end":[3,3],"physical_openings":[]})
    g["circulation_paths"]=[{"id":"PATH","path_centerline":[[1,1],[4,1]]}]
    assert "circulation_path_through_solid_wall" in kinds(evaluate(g))


def test_room_outside_buildable_boundary_fails():
    g=valid_geometry();g["buildable_boundary"]=[[0,0],[4,0],[4,3],[0,3]]
    assert "room_outside_buildable_boundary" in kinds(evaluate(g))


def test_missing_enforcement_is_unresolved(): assert ArchitecturalSpatialQualityGateV2().evaluate(valid_geometry(),{})["status"] == "unresolved"


def test_regenerable_failure_emits_request():
    g=valid_geometry();g["spaces"].append(space("isolated",6,0,8,2));r=evaluate(g)
    assert any(x["failed_constraint"]=="isolated_space" for x in r["regeneration_requests"])


def test_missing_evidence_does_not_emit_fake_regeneration_request():
    g=valid_geometry();g["project_requirements"]={"parking_pedestrian_requirements":[{"required":True}]}
    assert evaluate(g)["regeneration_requests"] == []


def test_high_score_never_overrides_critical_failure():
    g=valid_geometry();g["spaces"].append(space("isolated",6,0,8,2));r=evaluate(g)
    assert r["quality_score"] > 0 and r["status"] == "failed"


def test_deterministic_repeat():
    g=valid_geometry();assert evaluate(deepcopy(g)) == evaluate(deepcopy(g))
