import hashlib
import importlib.util
import json
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"tools"/"run_parcel2_h1_human_architectural_comparison_v5.py"
spec=importlib.util.spec_from_file_location("v5",SCRIPT); v5=importlib.util.module_from_spec(spec); spec.loader.exec_module(v5)

def hashes(folder):
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}

def test_contract_and_determinism(tmp_path):
    before=hashlib.sha256(v5.V4.read_bytes()).hexdigest()
    a,b=tmp_path/"same",tmp_path/"same2"; v5.build(a); v5.build(b)
    assert hashes(a)==hashes(b)
    assert before==hashlib.sha256(v5.V4.read_bytes()).hexdigest()
    report=json.loads((a/"PARCEL2_H1_HUMAN_ARCHITECTURAL_COMPARISON_V5.json").read_text(encoding="utf-8"))
    assert report["active_candidate_ids"]==v5.ACTIVE_IDS
    assert report["historical_counterexamples"]["active"] is False
    assert report["winner"] is None and report["final_selection_performed"] is False
    assert report["ranking_imported_from_v4"] is False
    assert all("bounded_review_rank" not in c for c in report["candidates"])
    assert report["geometric_equivalence"]["all_active_equivalent"] is True
    assert all(a["pedestrian_vehicle_conflict"]["status"]=="material_unresolved_conflict" for a in report["candidate_comparison"])

def test_svg_required_debug_content(tmp_path):
    out=tmp_path/"out"; v5.build(out)
    for cid in v5.ACTIVE_IDS:
        svg=(out/f"{cid}.svg").read_text(encoding="utf-8")
        for token in ("STREET EDGE / COMMERCIAL FRONTAGE","COMMERCIAL ENTRANCE","RESIDENTIAL / BUILDING ENTRANCE","TEMP CORE — NOT COMMERCIAL","2-FLIGHT STAIR","TEMP ELEVATOR 2.10×2.10 m","LOBBY UNRESOLVED","S-001","S-004","NO RANK / NO WINNER"):
            assert token in svg
    assert len(list(out.glob("H1-AF-*.svg")))==3
