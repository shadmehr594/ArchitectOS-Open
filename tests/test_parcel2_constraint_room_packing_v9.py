import json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(r"<repo-root>");sys.path.insert(0,str(ROOT/"core/architecture/reasoning"))
from parcel2_constraint_room_packing_v9 import ConstraintRoomPackingV9,STRATEGIES
V8=ROOT/"exports/DEFAULT/parcel2_architectural_graph_floor_plan_synthesizer_v8_20260913_171805/PARCEL2_ARCHITECTURAL_GRAPH_FLOOR_PLAN_SYNTHESIZER_V8.json"
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def result():return ConstraintRoomPackingV9(load(ROOT/"core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json"),load(ROOT/"core/architecture/contracts/jurisdictional_projection_policy_v1.json")).search(load(V8)["plans"])
def test_deterministic_bounded_pruning_and_no_source_mutation():
 s=load(V8)["plans"];f=deepcopy(s);e=ConstraintRoomPackingV9({},{});assert e.search(s)==e.search(s) and s==f;assert e.search(s)["attempt_count"]==12*len(STRATEGIES)
def test_real_lightwell_precedes_rooms_and_daylight_chain():
 for p in result()["survivors"]:
  assert p["pipeline"].index("RESERVE_DAYLIGHT_LIGHTWELL_TOPOLOGY")<p["pipeline"].index("CONSTRAINT_ROOM_POLYGONS_WITH_HOST_WALLS")
  for u in p["units"]:assert u["lightwell"]["polygon"] and u["lightwell"]["reserved_before_room_packing"] and all(x["valid"] for x in u["daylight_chains"])
def test_room_constraints_adjacency_doors_and_circulation():
 for p in result()["survivors"]:
  for u in p["units"]:
   assert all(r["furniture_envelope_pass"] and not r["elongated_to_touch_facade"] for r in u["rooms"]);assert u["room_adjacency_graph"]["all_required_satisfied"]
   assert all(d["valid"] and d["created_during_packing"] for d in u["doors"]);assert all(c["derived_from_door_graph"] and not c["through_unrelated_room"] for c in u["private_circulation"])
def test_wet_privacy_dual_access_residual_and_precedent():
 for p in result()["survivors"]:
  assert p["precedent"]["geometry_copied"] is False and len(p["units"])==2
  for u in p["units"]:assert u["service_wet_zone"]["cluster_pass"] and u["privacy"]["guest_wc_from_entry_public_without_private_intrusion"] and u["dual_access"]["stair"] and u["dual_access"]["elevator"] and u["checks"]["residual_bounded"]
def test_projection_assisted_pruned_and_resolved_truthful():
 r=result();assert r["survivors"] and all(p["REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN"] for p in r["survivors"]);assert all(x["pruned"] for x in r["diagnostics"] if x["strategy_class"]=="PROJECTION_ASSISTED")
