import hashlib, importlib.util, json, re, xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"tools"/"run_parcel2_h1_human_architectural_quality_review_v7.py"
spec=importlib.util.spec_from_file_location("v7",SCRIPT); v7=importlib.util.module_from_spec(spec); spec.loader.exec_module(v7)
def hashes(p): return {f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in p.iterdir() if f.is_file()}

def test_deterministic_exactly_three_no_v6_mutation_no_selection(tmp_path):
    before=v7.v6_inventory(); a,b=tmp_path/"a",tmp_path/"b"; v7.build(a); v7.build(b)
    assert hashes(a)==hashes(b); assert v7.v6_inventory()==before
    r=json.loads((a/"PARCEL2_H1_HUMAN_ARCHITECTURAL_QUALITY_REVIEW_V7.json").read_text(encoding="utf-8"))
    assert r["input_contract"]["exactly_three_v6_topologies_consumed"] and len(r["quality_reviews"])==3
    assert r["selection"]=={"authoritative_ranking":False,"final_selection_performed":False,"labels":"neutral_A_B_C","winner":None}
    assert r["lineage"]["v6_directory_inventory_before"]==r["lineage"]["v6_directory_inventory_after"]
    assert r["prohibited_workflows_executed"]=={"BIM":False,"H2":False,"IFC":False,"elevator_traffic":False,"image_generation":False,"new_topology_generation":False,"render":False,"structure":False}

def test_metrics_are_geometry_derived_and_complete(tmp_path):
    text=SCRIPT.read_text(encoding="utf-8").lower()
    scoring=text[text.index("def review_candidate"):text.index("def svg_poly")]
    for topology_id in v7.EXPECTED_IDS: assert topology_id.lower() not in scoring
    assert not re.search(r"\b(north|south|east|west)\b",text)
    out=tmp_path/"out"; v7.build(out)
    r=json.loads((out/"PARCEL2_H1_HUMAN_ARCHITECTURAL_QUALITY_REVIEW_V7.json").read_text(encoding="utf-8"))
    fields=("commercial_frontage_quality","commercial_shape_efficiency","residential_access_legibility","pedestrian_vehicle_conflict_intensity","vehicle_manoeuvre_quality","stall_usability_notes","core_access_quality","dead_space_area_m2","reclaimable_area_m2","swept_path_status","engineering_review_required","human_review_status")
    for q in r["quality_reviews"]:
        assert all(k in q for k in fields); assert q["engineering_review_required"] is True
        assert q["human_review_status"] in ("reviewable","disfavored","blocked")

def test_svg_labels_and_xml_valid(tmp_path):
    out=tmp_path/"out"; v7.build(out); svgs=list(out.glob("*.svg")); assert len(svgs)==4
    required=("STREET / FRONTAGE","COMMERCIAL","RESIDENTIAL ENTRANCE","VEHICLE INGRESS / EGRESS","TEMP CORE — NOT COMMERCIAL","2-FLIGHT STAIR","TEMP ELEVATOR 2.10×2.10 m","LOBBY UNRESOLVED","ENGINEERING REVIEW REQUIRED","NO WINNER")
    details=list(out.glob("H1-V6-*-V7-QUALITY-REVIEW.svg")); assert len(details)==3
    for p in svgs: ET.parse(p)
    for p in details:
        s=p.read_text(encoding="utf-8"); assert all(token in s for token in required)
        assert "pedestrian exclusive" in s and "pedestrian/vehicle shared" in s and "DEAD / RECLAIMABLE" in s
