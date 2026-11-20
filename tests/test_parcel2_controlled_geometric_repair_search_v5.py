from copy import deepcopy
from hashlib import sha256
import json,sys
from pathlib import Path
import pytest

ROOT=Path(r"<repo-root>")
sys.path.insert(0,str(ROOT/"core/architecture/reasoning"))
from parcel2_controlled_geometric_repair_search_v5 import ControlledGeometricRepairSearchV5,verify_authority
V4=ROOT/"exports/DEFAULT/parcel2_residential_room_planning_daylight_v4_20260913_131505/PARCEL2_RESIDENTIAL_ROOM_PLANNING_DAYLIGHT_V4.json"
EV=ROOT/"core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json"
def source(): return json.loads(V4.read_text(encoding="utf-8"))
def engine(): return ControlledGeometricRepairSearchV5(json.loads(EV.read_text(encoding="utf-8")))

def test_authority_pipeline_scope_and_no_relaxation():
 assert verify_authority(json.loads(EV.read_text(encoding="utf-8")))["status"]=="PASS"
 p=engine().pipeline
 assert p.index("detect_blockers_and_build_adjacency_graph") < p.index("apply_one_move") < p.index("full_constraint_re_evaluation")

@pytest.mark.parametrize("idx",range(18))
def test_determinism_no_mutation_repair_only_unresolved_and_only_improving(idx):
 original=source()["plans"][idx]; frozen=deepcopy(original); a=engine().repair(original); b=engine().repair(original)
 assert a==b and original==frozen
 assert a["winner"] is None and not a["authoritative_ranking"]
 rp=a["repair_provenance"]; assert rp["repair_only_unresolved"]=="UNRESOLVED_ONLY"
 assert set(rp["after_metrics"]["issues"]) <= set(rp["before_metrics"]["issues"])
 assert rp["after_metrics"]["score"] <= rp["before_metrics"]["score"]
 assert not rp["validator_relaxed"] and not rp["harder_new_blocker_created"]

def test_boundary_accounting_circulation_doors_daylight_privacy_furniture_service():
 for p in source()["plans"]:
  a=engine().repair(p); c=a["checks"]
  assert c["boundary_containment"] and c["non_overlap"] and c["area_accounting"]
  assert c["orthogonal_internal_repairs"] and not c["arbitrary_angle_created"]
  assert c["reachability_from_unit_threshold"] == c["all_doors_valid"]
  assert all("host_wall" in d and "opening" in d and "swing_clearance" in d for d in a["doors"])
  ids={s["source_id"] for s in a["daylight_sources"]}
  for w in a["windows"]:
   assert w["source_id"] in ids and w["host_wall"]["verified_room_source_boundary"]
   assert w["ratio_basis"] in {"1/8","1/7_DEPTH_GT_4_5M"}
  assert a["resolved_room_level"] == (not a["spatial_problems"])

def test_lightwell_agi_precedent_and_local_exception_fail_closed():
 for p in source()["plans"]:
  a=engine().repair(p)
  assert not a["lightwell"]["created"] and not a["lightwell"]["fake_void"]
  assert not a["local_geometric_exception"]["used"]
  assert not a["agi_precedent"]["invoked"] and not a["agi_precedent"]["precedent_geometry_copied"]

def test_v2_v3_v4_and_evidence_hashes_stable():
 paths=[ROOT/"core/architecture/reasoning"/f"parcel2_residential_room_planning_daylight_v{x}.py" for x in (2,3,4)]+[EV,V4]
 before={str(p):sha256(p.read_bytes()).hexdigest() for p in paths}
 for p in source()["plans"]: engine().repair(p)
 assert before=={str(p):sha256(p.read_bytes()).hexdigest() for p in paths}
