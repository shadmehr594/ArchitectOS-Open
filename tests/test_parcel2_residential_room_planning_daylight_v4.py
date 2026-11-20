from copy import deepcopy
from hashlib import sha256
import json, sys
from pathlib import Path
import pytest

ROOT=Path(r"<repo-root>")
sys.path.insert(0,str(ROOT/"core/architecture/reasoning"))
from parcel2_residential_room_planning_daylight_v4 import ResidentialRelationalConstraintRepairV4,verify_authority
V3=ROOT/"exports/DEFAULT/parcel2_residential_room_planning_daylight_v3_20260913_124549/PARCEL2_RESIDENTIAL_ROOM_PLANNING_DAYLIGHT_V3.json"
EV=ROOT/"core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json"

def source(): return json.loads(V3.read_text(encoding="utf-8"))
def engine(): return ResidentialRelationalConstraintRepairV4(json.loads(EV.read_text(encoding="utf-8")))

def test_authority_pipeline_and_scope():
 assert verify_authority(json.loads(EV.read_text(encoding="utf-8")))["status"]=="PASS"
 p=engine().pipeline
 assert p.index("load_immutable_v3_hypothesis") < p.index("detect_relational_failures") < p.index("re_evaluate_all_constraints")

@pytest.mark.parametrize("idx",range(18))
def test_determinism_no_mutation_only_improvement_and_no_selection(idx):
 original=source()["plans"][idx]; before=deepcopy(original); e=engine(); a=e.repair(original); b=e.repair(original)
 assert a==b and original==before
 assert a["winner"] is None and not a["authoritative_ranking"]
 rp=a["repair_provenance"]
 assert rp["after_metrics"]["score"] <= rp["before_metrics"]["score"]
 assert not rp["worse_trade_off_accepted"]
 assert all(m["geometry_source"]=="V3_EXISTING_CELL" and not m["boundary_repartitioned"] for m in rp["moves"])

def test_real_doors_reachability_and_fail_closed():
 for p in source()["plans"]:
  a=engine().repair(p)
  assert all("host_wall" in d and "opening" in d and "swing_clearance" in d for d in a["doors"])
  assert a["checks"]["reachability_from_unit_threshold"] == all(d["valid"] for d in a["doors"])
  assert a["resolved_room_level"] == (not a["spatial_problems"])

def test_daylight_chain_glazing_depth_and_source_host_wall():
 for p in source()["plans"]:
  a=engine().repair(p); ids={s["source_id"] for s in a["daylight_sources"]}
  for w in a["windows"]:
   assert w["source_id"] in ids and w["host_wall"]["geometry"]
   assert w["ratio_basis"] in {"1/8","1/7_DEPTH_GT_4_5M"}
   if w["opening_verified"]: assert w["daylight_depth_m"] <= w["depth_limit_m"]+.0001 and w["glazing_area_m2"]+.002 >= w["required_glazing_area_m2"]

def test_accounting_orthogonal_service_privacy_furniture_and_agi_gate():
 for p in source()["plans"]:
  a=engine().repair(p); al=a["allocation"]
  assert abs(al["USABLE_ENVELOPE"]-al["ACCOUNTED_TOTAL"]) <= .02
  assert a["checks"]["orthogonal_internal_repairs"] and not a["checks"]["arbitrary_angle_created"]
  assert all(r["privacy"]["status"]=="PASS" for r in a["rooms"])
  assert not a["agi_precedent"]["invoked"] and not a["agi_precedent"]["precedent_geometry_copied"]
  assert not a["lightwell"]["created"]

def test_history_hashes_stable_during_repair():
 paths=[ROOT/"core/architecture/reasoning/parcel2_residential_room_planning_daylight_v3.py",ROOT/"tools/run_parcel2_residential_room_planning_daylight_v3.py",ROOT/"tests/test_parcel2_residential_room_planning_daylight_v3.py",EV,V3]
 before={str(p):sha256(p.read_bytes()).hexdigest() for p in paths}
 for p in source()["plans"]: engine().repair(p)
 assert before=={str(p):sha256(p.read_bytes()).hexdigest() for p in paths}
