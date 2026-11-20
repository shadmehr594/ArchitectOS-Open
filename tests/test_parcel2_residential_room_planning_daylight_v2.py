from copy import deepcopy
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(r"<repo-root>")
sys.path.insert(0,str(ROOT/"core/architecture/reasoning"))
from parcel2_residential_room_planning_daylight_v2 import ResidentialRoomPlanningDaylightV2,verify_authority
V8=ROOT/"exports/DEFAULT/parcel2_h1_upper_floor_design_around_current_core_v8_20260912_212949/PARCEL2_H1_UPPER_FLOOR_DESIGN_AROUND_CURRENT_CORE_V8.json"
EV=ROOT/"core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json"
def samples():
 d=json.loads(V8.read_text(encoding="utf-8"))
 for t in d["core_hypotheses"]:
  for f in t["floors"]:
   for u in f["units"]: yield t,f,u
def engine(): return ResidentialRoomPlanningDaylightV2(json.loads(EV.read_text(encoding="utf-8")))
def test_authority_clause_page_provenance():
 d=json.loads(EV.read_text(encoding="utf-8")); assert verify_authority(d)["status"]=="PASS"; assert d["document"]["sha256"]=="d1bf218bd5e346158a7f2a64bf929096c95b6330d1bd50d097c17bea9dff94d2"
 assert all(("pdf_page" in r or "pdf_pages" in r) and "applicability" in r for r in d["rules"])
def test_no_slice_strategy():
 src=(ROOT/"core/architecture/reasoning/parcel2_residential_room_planning_daylight_v2.py").read_text(encoding="utf-8").lower(); assert "_slice" not in src and "weights" not in src and "equal slice" not in src
@pytest.mark.parametrize("idx",range(9))
def test_determinism_no_mutation_and_provenance(idx):
 t,f,u=list(samples())[idx]; before=deepcopy(u); e=engine(); h=e.hypotheses()[0]; a=e.solve(u,f["public_corridor"],t["topology_id"],f["floor_id"],h); b=e.solve(u,f["public_corridor"],t["topology_id"],f["floor_id"],h)
 assert a==b and u==before and a["winner"] is None and not a["authoritative_ranking"]
 assert a["program_hypothesis"]["authority_class"]=="DESIGN_KNOWLEDGE_NON_AUTHORITATIVE"
def test_room_source_window_chain_not_opportunity():
 t,f,u=next(samples()); a=engine().solve(u,f["public_corridor"],t["topology_id"],f["floor_id"],engine().hypotheses()[0]); ids={s["source_id"] for s in a["daylight_sources"]}
 assert all(w["source_id"] in ids and w["room_id"] for w in a["windows"]); assert "opening_opportunity" not in json.dumps(a).lower()
def test_corridor_threshold_doors_privacy_service_furniture_and_agi_gate():
 t,f,u=next(samples()); a=engine().solve(u,f["public_corridor"],t["topology_id"],f["floor_id"],engine().hypotheses()[0]); assert a["public_corridor_stops_at_threshold"]
 assert all("space_a" in d and "space_b" in d and "host_wall" in d and "opening" in d for d in a["doors"])
 assert isinstance(a["checks"]["privacy"],bool) and isinstance(a["checks"]["service_plumbing_relation"],bool)
 assert all(r["furniture"]["authority_class"]=="DESIGN_KNOWLEDGE_NON_AUTHORITATIVE" for r in a["rooms"])
 assert a["agi_precedent"]["invoked"]==bool(a["spatial_problems"]) and not a["agi_precedent"]["precedent_geometry_copied"]
def test_glazing_and_depth_are_calculated():
 t,f,u=next(samples()); a=engine().solve(u,f["public_corridor"],t["topology_id"],f["floor_id"],engine().hypotheses()[0])
 assert all(w["ratio_basis"] in {"1/8","1/7"} and w["required_glazing_area_m2"]>0 and w["daylight_depth_m"]>0 for w in a["windows"])
def test_no_parcel2_hardcode():
 src=(ROOT/"core/architecture/reasoning/parcel2_residential_room_planning_daylight_v2.py").read_text(encoding="utf-8").lower(); assert "h1-v6" not in src and "parcel2" not in src
