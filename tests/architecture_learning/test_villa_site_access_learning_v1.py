from core.architecture.learning.villa_site_access_learning_v1 import *

def test_required_regressions():
    c=fresh_candidate(); r=VillaGeometryValidator().validate(c)
    assert r["total"] >= 21 and r["passed"] == r["total"]
    assert c["levels"]["provenance"] == "USER_REQUESTED_PROJECT_RULE"
    assert c["site_enclosure"]["property_boundary_is_wall"] is False
    assert c["courtyard"]["requires_access"] is True
    assert CourtyardAccessSemantics.resolve("LIGHTWELL",False)["requires_access"] is False

def test_missing_gate_and_blocked_metadata_cannot_pass():
    c=fresh_candidate(); c["site_enclosure"]["gate_intents"]=[]
    r=VillaGeometryValidator().validate(c)
    assert r["status"] == "FAIL"
    assert "south_vehicle_gate_cuts_site_wall" in r["failures"]

def test_wall_openings_are_real_cut_intervals():
    c=fresh_candidate(); wg=c["wall_graph"]
    assert any(x["host"]=="H_N" for x in wg["wall_solids"])
    assert any(x["id"]=="bed2_door" for x in wg["openings"])

def test_wall_polygon_collision_is_a_hard_failure():
    c=fresh_candidate()
    c["wall_graph"]["wall_solids"].append({"id":"BLOCK","host":"TEST","bbox":[1.2,12.8,1.3,14.5]})
    r=VillaGeometryValidator().validate(c)
    assert r["status"] == "FAIL"
    assert "ACCESS_PATH_BLOCKED_BY_WALL" in r["failure_codes"]
