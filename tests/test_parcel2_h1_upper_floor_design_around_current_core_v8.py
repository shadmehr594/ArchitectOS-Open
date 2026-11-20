import hashlib,importlib.util,json,re,xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"tools"/"run_parcel2_h1_upper_floor_design_around_current_core_v8.py"
spec=importlib.util.spec_from_file_location("v8",SCRIPT);v8=importlib.util.module_from_spec(spec);spec.loader.exec_module(v8)
def hashes(p):return {f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in p.iterdir() if f.is_file()}

def test_deterministic_three_cores_two_floors_and_no_mutation(tmp_path):
    b6,b7=v8.inventory(v8.V6_DIR),v8.inventory(v8.V7_DIR);a,b=tmp_path/"a",tmp_path/"b";v8.build(a);v8.build(b)
    assert hashes(a)==hashes(b);assert v8.inventory(v8.V6_DIR)==b6;assert v8.inventory(v8.V7_DIR)==b7
    r=json.loads((a/"PARCEL2_H1_UPPER_FLOOR_DESIGN_AROUND_CURRENT_CORE_V8.json").read_text(encoding="utf-8"));assert len(r["core_hypotheses"])==3
    for t in r["core_hypotheses"]:
        assert [f["program_unit_count"] for f in t["floors"]]==[1,2];assert not t["core_geometry_mutated"]
        assert t["vertical_anchor"]["status"]=="PREFERRED_VERTICAL_ANCHOR_HYPOTHESIS_NON_FINAL";assert t["vertical_anchor"]["lobby_status"]=="LOBBY_UNRESOLVED"

def test_architecture_checks_status_and_no_winner(tmp_path):
    out=tmp_path/"out";v8.build(out);r=json.loads((out/"PARCEL2_H1_UPPER_FLOOR_DESIGN_AROUND_CURRENT_CORE_V8.json").read_text(encoding="utf-8"))
    assert r["result"]["status"] in ("H1_UPPER_FLOORS_READY_FOR_HUMAN_REVIEW","BLOCKED")
    assert r["selection"]=={"authoritative_ranking":False,"final_selection_performed":False,"winner":None}
    for t in r["core_hypotheses"]:
        assert t["core_preservation_status"] in ("CURRENT_CORE_PRESERVABLE","CURRENT_CORE_PRESERVABLE_WITH_TRADEOFFS","CURRENT_CORE_ARCHITECTURALLY_DISFAVORED_FOR_UPPER_FLOORS","CURRENT_CORE_INFEASIBLE_FOR_UPPER_FLOORS")
        for f in t["floors"]:
            assert all(f["checks"][k] for k in ("unit_count_matches_program","all_unit_entrances_connect_to_stair_elevator_lobby_circulation","no_access_through_other_unit","no_overlap","fully_inside_floor_domain","vertical_core_consistent"))
            assert f["plumbing_service_clustering"]["status"].startswith("UNRESOLVED")

def test_no_leakage_prohibited_workflows_and_svg_contract(tmp_path):
    text=SCRIPT.read_text(encoding="utf-8").lower();scoring=text[text.index("def evaluate_floor"):text.index("def svg_polygon")]
    for tid in v8.EXPECTED_IDS:assert tid.lower() not in scoring
    assert not re.search(r"\b(north|south|east|west)\b",text)
    out=tmp_path/"out";v8.build(out);r=json.loads((out/"PARCEL2_H1_UPPER_FLOOR_DESIGN_AROUND_CURRENT_CORE_V8.json").read_text(encoding="utf-8"))
    assert not any(r["prohibited_workflows_executed"].values());svgs=list(out.glob("*.svg"));assert len(svgs)==7
    for p in svgs:ET.parse(p)
    details=[p for p in svgs if "RESIDENTIAL_FLOOR" in p.name];assert len(details)==6
    required=("FLOOR / PARCEL BOUNDARY","STAIR SCHEMATIC","TEMP ELEVATOR 2.10×2.10 m","PUBLIC CORRIDOR","UNIT-1 ENTRANCE","ROOM/ZONES UNRESOLVED","DEAD / UNRESOLVED REGION","NO WINNER")
    for p in details:
        s=p.read_text(encoding="utf-8");assert all(x in s for x in required)
