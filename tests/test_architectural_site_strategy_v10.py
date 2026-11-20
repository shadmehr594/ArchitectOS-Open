from copy import deepcopy
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"core"/"architecture"/"reasoning"))
from shapely.geometry import box
from architectural_site_strategy_v10 import ArchitecturalSiteStrategyV10, BuildingTopologyValidatorV10, stable_digest

def profile(verified=True):
 p={"profile_id":"TEST","edge_rules":[{"relation":"PARTY_WALL","projection":"PROHIBITED","balcony":"PROHIBITED","window":"PROHIBITED"}],"parameters":{}}
 if verified:p["parameters"]={"lightwell_min_width_m":{"value":2.0,"authority":"TEST_CLAUSE"},"lightwell_min_area_m2":{"value":12.0,"authority":"TEST_CLAUSE"},"neighbor_window_min_sill_m":{"value":1.7,"authority":"TEST_CLAUSE"}}
 return p
def site(coverage=1.0,rotate=False):
 parcel=[[0,0],[20,0],[20,10],[0,10]] if not rotate else [[0,0],[14,14],[7,21],[-7,7]]
 build=parcel if coverage==1 else [[0,0],[12,0],[12,10],[0,10]]
 return {"parcel_polygon":parcel,"buildable_zone":build,"edge_evidence":[{"edge_index":0,"relation":"STREET","vehicle_suitability":"SUITABLE","pedestrian_suitability":"SUITABLE"},{"edge_index":1,"relation":"PARTY_WALL"},{"edge_index":2,"relation":"OPEN_YARD","privacy_quietness":"QUIET"},{"edge_index":3,"relation":"PARTY_WALL"}]}
PROGRAM={"ground_commercial_frontage_important":True,"parking_required":True,"upper_unit_count":2}
def test_arbitrary_orientation_edge_classification_no_cardinal_hardcode():
 r=ArchitecturalSiteStrategyV10().analyze(site(1,True),PROGRAM,profile());assert all(not e["cardinal_direction_used"] for e in r["edge_metadata"]);assert r["street_edges"]==["EDGE_1"]
def test_coverage_and_yard_precede_lightwell():
 r=ArchitecturalSiteStrategyV10().analyze(site(.6),PROGRAM,profile());assert r["site_coverage_strategy"]["percent"]==60;assert r["yard_open_space_sources"];assert r["lightwell_candidate_zones"][0]["family"]=="NO_LIGHTWELL_IF_DIRECT_DAYLIGHT_SUFFICIENT"
def test_missing_local_dimensions_fail_closed_and_no_user_example_default():
 r=ArchitecturalSiteStrategyV10().analyze(site(),PROGRAM,profile(False));assert all(not x["hard_feasible"] for x in r["strategy_candidates"]);assert r["jurisdiction_authority"]["lightwell_min_width_m"]["value"] is None
def test_program_sensitive_core_and_not_always_center():
 r=ArchitecturalSiteStrategyV10().analyze(site(),PROGRAM,profile());f={x["family"] for x in r["core_candidate_zones"]};assert {"INTER_UNIT_CENTRAL_CORE","SIDE_CORE","REAR_CORE","FRONT_CORE_ONLY_IF_JUSTIFIED"}<=f;assert next(x for x in r["core_candidate_zones"] if x["family"]=="FRONT_CORE_ONLY_IF_JUSTIFIED")["commercial_frontage_penalty"]==1
def test_deterministic_generation_and_facade_map_is_input_to_zones():
 e=ArchitecturalSiteStrategyV10();s=site();before=deepcopy(s);a=e.analyze(s,PROGRAM,profile());b=e.analyze(s,PROGRAM,profile());assert stable_digest(a)==stable_digest(b) and s==before;assert a["public_zone_candidates"]
def test_shared_semantics_direct_facade_and_door_host_geometry():
 v=BuildingTopologyValidatorV10();units=[{"unit_id":"U1","polygon":[[0,0],[4,0],[4,5],[0,5]]},{"unit_id":"U2","polygon":[[6,0],[10,0],[10,5],[6,5]]}];lw={"shared_space_id":"LW1","polygon":[[4,1],[6,1],[6,3],[4,3]]};wins=[{"unit_id":"U1","source_id":"LW1","host_wall":[[4,1],[4,3]],"valid":True},{"unit_id":"U2","source_id":"LW1","host_wall":[[6,1],[6,3]],"valid":True}];assert v.validate_shared_lightwell(lw,units,wins);assert not v.direct_facade_valid([[0,0],[5,0],[5,5],[0,5]],[[5,1],[5,2]],[[[0,0],[0,5]]]);assert v.door_host_valid([[0,0],[4,0],[4,4],[0,4]],[[4,0],[5,0],[5,4],[4,4]],[[4,1],[4,2]])
def test_exact_area_partition_and_circulation_metrics():
 v=BuildingTopologyValidatorV10();spaces=[{"classification":"ROOM","polygon":[[0,0],[5,0],[5,10],[0,10]]},{"classification":"PRIVATE_CIRCULATION","polygon":[[5,0],[10,0],[10,10],[5,10]]}];assert v.exact_area_partition([[0,0],[10,0],[10,10],[0,10]],spaces)["valid"];m=v.circulation_quality(spaces[1]["polygon"],[[0,0],[10,0],[10,10],[0,10]],[5,0],[[5,5],[8,5]]);assert not m["boolean_only"] and "elongation" in m
def test_balcony_projection_neighbor_prohibited():
 r=ArchitecturalSiteStrategyV10().analyze(site(),PROGRAM,profile());e=r["edge_metadata"][1];assert e["projection_permissibility"]=="PROHIBITED" and e["balcony_permissibility"]=="PROHIBITED" and e["window_restrictions"]=="PROHIBITED"
