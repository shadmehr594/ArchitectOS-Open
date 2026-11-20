import hashlib, importlib.util, json, re, xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"tools"/"run_parcel2_h1_residential_corridor_entrance_geometry_v9.py"
spec=importlib.util.spec_from_file_location("v9",SCRIPT); v9=importlib.util.module_from_spec(spec); spec.loader.exec_module(v9)
def hashes(p): return {f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in p.iterdir() if f.is_file()}

def test_v9_determinism_contract_and_immutable_lineage(tmp_path):
    before={"v6":v9.inventory(v9.V6_DIR),"v7":v9.inventory(v9.V7_DIR),"v8":v9.inventory(v9.V8_DIR)}
    a,b=tmp_path/"a",tmp_path/"b"; v9.build(a); v9.build(b)
    assert hashes(a)==hashes(b)
    assert before=={"v6":v9.inventory(v9.V6_DIR),"v7":v9.inventory(v9.V7_DIR),"v8":v9.inventory(v9.V8_DIR)}
    r=json.loads((a/"PARCEL2_H1_RESIDENTIAL_CORRIDOR_ENTRANCE_GEOMETRY_V9.json").read_text(encoding="utf-8"))
    assert len(r["evaluations"])==6 and r["result"]["total_hypothesis_count"]==24
    assert r["selection"]=={"authoritative_ranking":False,"final_selection_performed":False,"winner":None}

def test_four_generic_hypotheses_thresholds_and_no_hardcoded_pentagon(tmp_path):
    out=tmp_path/"out"; v9.build(out)
    r=json.loads((out/"PARCEL2_H1_RESIDENTIAL_CORRIDOR_ENTRANCE_GEOMETRY_V9.json").read_text(encoding="utf-8"))
    expected={"straight_termination","widened_vestibule","polygonal_distribution_node","short_branch_corridor"}
    for item in r["evaluations"]:
        intel=item["intelligence"]; assert {h["hypothesis_id"] for h in intel["hypotheses"]}==expected
        assert intel["winner"] is None and not intel["authoritative_ranking"] and not item["core_geometry_mutated"]
        for h in intel["hypotheses"]:
            assert h["corridor_stops_at_unit_thresholds"] and h["public_corridor_private_penetration_m2"] <= 1e-7
            assert not h["hardcoded_pentagon"]
            assert set(("dead_space_m2","circulation_length_m","door_feasibility_0_1","privacy_0_1","geometric_coherence_0_1")) <= set(h["metrics"])
    text=(Path(v9.ROOT)/"core/architecture/reasoning/residential_corridor_entrance_geometry_intelligence_v1.py").read_text(encoding="utf-8").lower()
    assert "hardcoded_pentagon\": false" in text
    assert not re.search(r"polygon\s*\(\s*\[(?:[^\]]*\([^)]*\)){5}\s*\]\s*\)",text,re.S)

def test_regulation_provenance_svg_and_prohibited_scope(tmp_path):
    rules=json.loads(v9.RULES.read_text(encoding="utf-8")); assert len(rules["evidence_records"])>=4
    for rec in rules["evidence_records"]:
        assert all(k in rec for k in ("jurisdiction","issuing_authority","document_title","edition_date","clause_article","printed_page","pdf_page","applicability","provenance"))
    out=tmp_path/"out"; v9.build(out); r=json.loads((out/"PARCEL2_H1_RESIDENTIAL_CORRIDOR_ENTRANCE_GEOMETRY_V9.json").read_text(encoding="utf-8"))
    assert not any(r["prohibited_workflows_executed"].values())
    svgs=list(out.glob("*.svg")); assert len(svgs)==7
    for p in svgs: ET.parse(p)
    assert all("NO AUTHORITATIVE WINNER" in p.read_text(encoding="utf-8") for p in svgs if "FLOOR" in p.name)
