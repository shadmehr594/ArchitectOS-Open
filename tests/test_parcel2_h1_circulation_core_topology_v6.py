import hashlib, importlib.util, json, re
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"tools"/"run_parcel2_h1_circulation_core_topology_v6.py"
spec=importlib.util.spec_from_file_location("v6",SCRIPT); v6=importlib.util.module_from_spec(spec); spec.loader.exec_module(v6)
def hashes(p): return {f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in p.iterdir() if f.is_file()}

def test_determinism_no_mutation_and_contract(tmp_path):
    before=v6.sha(v6.V5); a,b=tmp_path/"a",tmp_path/"b"; v6.build(a); v6.build(b)
    assert hashes(a)==hashes(b); assert v6.sha(v6.V5)==before
    r=json.loads((a/"PARCEL2_H1_CIRCULATION_CORE_TOPOLOGY_V6.json").read_text(encoding="utf-8"))
    assert r["distinct_topology_count"]>=3 and r["geometric_diversity"]["all_pairwise_distinct"]
    assert r["selection"]["winner"] is None and not r["selection"]["final_selection_performed"]
    assert r["readiness"]["H1"]=="READY_FOR_HUMAN_ARCHITECTURAL_SELECTION"
    for c in r["topologies"]:
        assert c["parking_count"]>=3
        assert c["commercial"]["direct_street_access"] and c["commercial"]["frontage_length_m"]>0
        assert c["gates"]["residential_to_core_route_continuous"]
        assert c["pedestrian_route"]["exclusive_area_m2"]>0
        assert c["swept_path"]["status"] in ("approximated_pass","fail_closed_insufficient_clearance")
        assert c["swept_path"]["regulatory_claim"] is False

def test_no_leakage_and_svg_content(tmp_path):
    text=SCRIPT.read_text(encoding="utf-8").lower()
    assert not re.search(r"\b(north|south|east|west)\b",text)
    out=tmp_path/"out"; v6.build(out)
    r=json.loads((out/"PARCEL2_H1_CIRCULATION_CORE_TOPOLOGY_V6.json").read_text(encoding="utf-8"))
    assert r["derivation_contract"]=={
        "cardinal_direction_used":False,
        "coordinate_basis":"parcel_frontage_tangent_and_inward_depth_field",
        "family_parameters":"dimensionless_relational_proportions",
        "fixed_metric_offset_used":False,
        "historical_seed_used":False,
        "parcel2_coordinates_hardcoded":False,
    }
    for p in out.glob("H1-V6-*.svg"):
        s=p.read_text(encoding="utf-8")
        for token in ("STREET / FRONTAGE","COMMERCIAL DIRECT ACCESS","RESIDENTIAL / BUILDING ENTRANCE","VEHICLE INGRESS / EGRESS","TEMP CORE — NOT COMMERCIAL","2-FLIGHT STAIR","TEMP ELEVATOR 2.10×2.10 m","LOBBY UNRESOLVED","Residual/dead space","NO RANK / NO WINNER"):
            assert token in s
    assert len(list(out.glob("H1-V6-*.svg")))>=3
