from copy import deepcopy
import json, sys
from pathlib import Path
import pytest

ROOT=Path(r"<repo-root>")
sys.path.insert(0,str(ROOT/"core/architecture/reasoning"))
from parcel2_residential_room_planning_daylight_v3 import ResidentialRoomPlanningDaylightV3, verify_authority
V8=ROOT/"exports/DEFAULT/parcel2_h1_upper_floor_design_around_current_core_v8_20260912_212949/PARCEL2_H1_UPPER_FLOOR_DESIGN_AROUND_CURRENT_CORE_V8.json"
EV=ROOT/"core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json"

def samples():
 d=json.loads(V8.read_text(encoding="utf-8"))
 for t in d["core_hypotheses"]:
  for f in t["floors"]:
   for u in f["units"]: yield t,f,u
def engine(): return ResidentialRoomPlanningDaylightV3(json.loads(EV.read_text(encoding="utf-8")))

def test_authority_and_pipeline_order():
 assert verify_authority(json.loads(EV.read_text(encoding="utf-8")))["status"]=="PASS"
 p=engine().pipeline
 assert p.index("dominant_orthogonal_frame") < p.index("exterior_daylight_edges") < p.index("daylight_constrained_room_allocation") < p.index("shared_wall_door_openings") < p.index("spatial_problem_detection")

@pytest.mark.parametrize("idx",range(9))
def test_determinism_no_mutation_complete_ledger_and_no_selection(idx):
 t,f,u=list(samples())[idx]; before=deepcopy(u); h=engine().hypotheses()[0]
 a=engine().solve(u,f["public_corridor"],t["core_geometry"],t["topology_id"],f["floor_id"],h)
 b=engine().solve(u,f["public_corridor"],t["core_geometry"],t["topology_id"],f["floor_id"],h)
 assert a==b and u==before and a["winner"] is None and not a["authoritative_ranking"]
 assert abs(a["allocation"]["UNIT_ENVELOPE"]-a["allocation"]["ACCOUNTED_TOTAL"]) <= .01
 assert all(x["type"]=="VERIFIED_ENVELOPE_CLIPPING" and not x["invented"] for x in a["dominant_frame"]["exceptions"])

def test_every_opening_is_physical_and_daylight_is_not_opportunity_language():
 t,f,u=next(samples()); a=engine().solve(u,f["public_corridor"],t["core_geometry"],t["topology_id"],f["floor_id"],engine().hypotheses()[0])
 assert all("host_wall" in d and "opening" in d and isinstance(d["valid"],bool) for d in a["doors"])
 ids={s["source_id"] for s in a["daylight_sources"]}
 assert all(w["source_id"] in ids and w["opening_verified"] for w in a["windows"])
 assert "opening_opportunity" not in json.dumps(a).lower()

def test_fail_closed_and_agi_gate_are_honest():
 t,f,u=next(samples()); a=engine().solve(u,f["public_corridor"],t["core_geometry"],t["topology_id"],f["floor_id"],engine().hypotheses()[1])
 assert a["resolved_room_level"] == (not a["spatial_problems"])
 assert a["agi_precedent"]["invoked"] == bool(a["spatial_problems"])
