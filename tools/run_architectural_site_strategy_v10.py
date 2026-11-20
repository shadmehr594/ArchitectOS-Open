from __future__ import annotations
import json, sys
from datetime import datetime
from hashlib import sha256
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"core"/"architecture"/"reasoning"))
from architectural_site_strategy_v10 import ArchitecturalSiteStrategyV10

EXCLUDED=["H2","ELEVATOR_TRAFFIC","STRUCTURE","BIM","IFC","RENDER","IMAGE_GENERATION"]
def parcel2():
 return ({"parcel_polygon":[[0,0],[20,0],[20,10],[0,10]],"buildable_zone":[[0,0],[20,0],[20,10],[0,10]],"placement_mode":"FULL_DERIVED_100_PERCENT","coverage_source":"CURRENT_PROJECT_REQUIREMENT","edge_evidence":[{"edge_index":1,"relation":"STREET","vehicle_suitability":"SUITABLE","pedestrian_suitability":"SUITABLE","noise_exposure":"HIGH","provenance":"PARCEL2_PROJECT_CONTEXT"},{"edge_index":0,"relation":"PARTY_WALL","provenance":"PARCEL2_PROJECT_CONTEXT"},{"edge_index":2,"relation":"PARTY_WALL","privacy_quietness":"QUIET","provenance":"PARCEL2_PROJECT_CONTEXT"},{"edge_index":3,"relation":"PARTY_WALL","provenance":"PARCEL2_PROJECT_CONTEXT"}],"provenance":"PARCEL2_CURRENT_CONTEXT"},
 {"ground_commercial_frontage_important":True,"vehicle_access_from_street":True,"parking_required":True,"upper_unit_count":2,"upper_program_options":["RF2","RF1"],"stair_required":True,"elevator_required":True,"provenance":"USER_CONFIRMED_PROGRAM"},
 {"profile_id":"PARCEL2_MINAB_V10_WORKING","edge_rules":[{"relation":"STREET","projection":"OPTIONAL_ALLOWED","balcony":"OPTIONAL_ALLOWED","window":"PROFILE_CONDITIONAL"},{"relation":"PARTY_WALL","projection":"PROHIBITED","balcony":"PROHIBITED","window":"PRIVACY_RULE_UNVERIFIED_FAIL_CLOSED"}],"parameters":{},"provenance":"LOCAL_VALUES_NOT_VERIFIED_FOR_V10_LIGHTWELL_DIMENSIONS"})

def main(out_root):
 site,program,profile=parcel2(); result=ArchitecturalSiteStrategyV10().analyze(site,program,profile)
 now=datetime.now().strftime("%Y%m%d_%H%M%S"); out=Path(out_root)/f"parcel2_site_strategy_joint_topology_v10_{now}"; out.mkdir(parents=True)
 topology={"contract":"JointBuildingTopologyV10","scope":"ARCHITECTURE_ONLY","source_site_strategy_contract":result["contract"],"candidates":result["strategy_candidates"],"hard_feasible_candidates":[x for x in result["strategy_candidates"] if x["hard_feasible"]],"room_packing_handoff":{"status":"ROOM_PACKING_BLOCKED" if not any(x["hard_feasible"] for x in result["strategy_candidates"]) else "READY_FOR_ROOM_PACKING","blocker_layer":"SITE_STRATEGY" if not any(x["hard_feasible"] for x in result["strategy_candidates"]) else None,"validators_not_relaxed":True},"software_acceptance":{"status":"PASS","meaning":"V10_CONTRACT_AND_FAIL_CLOSED_REASONING_EXECUTED"},"human_architectural_acceptance":{"status":"PENDING_HUMAN_REVIEW","independent":True},"authoritative_winner":None}
 lineage={"V9":{"software_acceptance":"PASS","human_architectural_acceptance":"REJECTED","historical_REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN":True,"status":"HUMAN_REVIEW_INVALIDATED_FALSE_POSITIVE","immutable":True}}
 payload={"contract":"ArchitecturalSiteStrategyV10Run","scope":"ARCHITECTURE_ONLY","excluded":EXCLUDED,"site_strategy":result,"lineage":lineage,"render_executed":False,"image_generation_executed":False}
 files={"ARCHITECTURAL_SITE_STRATEGY_V10.json":payload,"JOINT_BUILDING_TOPOLOGY_V10.json":topology}
 for name,data in files.items():(out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
 entries=[]
 for p in sorted(out.iterdir()): entries.append({"file":p.name,"size":p.stat().st_size,"sha256":sha256(p.read_bytes()).hexdigest()})
 (out/"ARTIFACT_MANIFEST.json").write_text(json.dumps({"contract":"ArtifactManifestV10","entries":entries},indent=2),encoding="utf-8")
 print(out)
if __name__=="__main__":main(Path(sys.argv[1]))
