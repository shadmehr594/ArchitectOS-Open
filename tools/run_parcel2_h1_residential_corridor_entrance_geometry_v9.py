"""V9 architecture-only corridor, entrance and geometric-coherence review."""
from __future__ import annotations

import argparse, hashlib, html, json, sys, xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(r"<repo-root>")
sys.path.insert(0, str(ROOT))
from core.architecture.reasoning.residential_corridor_entrance_geometry_intelligence_v1 import (  # noqa:E402
    ResidentialCorridorEntranceGeometryIntelligenceV1,
)

V6_DIR = ROOT / "exports/DEFAULT/parcel2_h1_circulation_core_topology_v6_20260912_210133"
V7_DIR = ROOT / "exports/DEFAULT/parcel2_h1_human_architectural_quality_review_v7_20260912_211316"
V8_DIR = ROOT / "exports/DEFAULT/parcel2_h1_upper_floor_design_around_current_core_v8_20260912_212949"
V8_JSON = V8_DIR / "PARCEL2_H1_UPPER_FLOOR_DESIGN_AROUND_CURRENT_CORE_V8.json"
RULES = ROOT / "core/architecture/contracts/parcel2_residential_corridor_entrance_regulation_evidence_v1.json"
EXPECTED_IDS = {"H1-V6-ADJACENT-SPINE", "H1-V6-BETWEEN-DOGLEG", "H1-V6-EDGE-RETURN"}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def inventory(folder): return {p.name:{"sha256":sha(p),"size_bytes":p.stat().st_size} for p in sorted(Path(folder).iterdir()) if p.is_file()}

def polygons(value):
    if not value: return []
    if isinstance(value[0][0], (int,float)): return [value]
    return value

def shape(points, tr, fill, stroke, opacity=.5, dash=""):
    return ''.join(f'<polygon points="{" ".join(f"{tr(p)[0]:.1f},{tr(p)[1]:.1f}" for p in poly)}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" {dash}/>' for poly in polygons(points))

def render(topology_id, floor, result):
    boundary=floor["floor_boundary"]; xs=[p[0] for p in boundary]; ys=[p[1] for p in boundary]
    scale=min(650/max(max(xs)-min(xs),1e-7),760/max(max(ys)-min(ys),1e-7)); minx,maxy=min(xs),max(ys)
    tr=lambda p:(55+(p[0]-minx)*scale,145+(maxy-p[1])*scale)
    cards=[]
    for idx,h in enumerate(result["hypotheses"]):
        y=165+idx*155; m=h["metrics"]
        cards.append(f'<rect x="760" y="{y-28}" width="790" height="140" rx="7" fill="white" stroke="#94a3b8"/><text x="780" y="{y}" class="h">{html.escape(h["hypothesis_id"])}</text><text x="780" y="{y+25}" class="t">{h["status"]} | advisory score {m["advisory_score_0_1"]:.3f} | node vertices {h["geometry_derived_node_vertex_count"]}</text><text x="780" y="{y+50}" class="t">dead {m["dead_space_m2"]:.2f} m² | length {m["circulation_length_m"]:.2f} m | door {m["door_feasibility_0_1"]:.2f}</text><text x="780" y="{y+75}" class="t">privacy {m["privacy_0_1"]:.2f} | coherence {m["geometric_coherence_0_1"]:.2f} | off-axis {m["off_context_axis_length_m"]:.2f} m</text><text x="780" y="{y+100}" class="t">corridor stops at thresholds: {str(h["corridor_stops_at_unit_thresholds"]).lower()} | hardcoded pentagon: false</text>')
    layers=[shape(boundary,tr,"#fff","#111827",.9),shape(floor["core_boundary_unchanged"],tr,"#fed7aa","#9a3412",.55)]
    colors=["#60a5fa","#a78bfa","#34d399","#fb7185"]
    for idx,h in enumerate(result["hypotheses"]):
        layers.append(shape(h["public_corridor"],tr,colors[idx],colors[idx],.16,f'stroke-dasharray="{3+idx*2} 4"'))
        for p in h["entrance_thresholds"]:
            x,y=tr(p); layers.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{4+idx}" fill="none" stroke="{colors[idx]}"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900"><defs><style>.h{{font:700 15px Arial}}.t{{font:12px Arial}}</style></defs><rect width="100%" height="100%" fill="#f8fafc"/><text x="45" y="42" font-family="Arial" font-size="22" font-weight="bold">V9 — {html.escape(topology_id)} — {floor["floor_id"]}</text><text x="45" y="76" class="t">ENGINEERING REVIEW | 1.40 m COMMON CORRIDOR | PUBLIC PATH STOPS AT UNIT THRESHOLD</text><text x="45" y="105" class="t">Four overlaid hypotheses; detailed rooms and final lobby remain unresolved.</text>{''.join(layers)}{''.join(cards)}<text x="760" y="800" class="t">NO AUTHORITATIVE WINNER — advisory scores support human review only.</text><text x="760" y="830" class="t">Internal entrance zone: min depth 1.40 m and min area 2.00 m², checked separately inside each unit.</text></svg>'''

def render_index(items):
    rows=[]; y=125
    for item in items:
        review=sum(h["status"]=="reviewable" for h in item["intelligence"]["hypotheses"])
        ids=', '.join(item["intelligence"]["advisory_highest_score_ids"]) or 'none'
        rows.append(f'<rect x="40" y="{y}" width="1520" height="82" fill="white" stroke="#94a3b8"/><text x="60" y="{y+29}" class="h">{html.escape(item["topology_id"])} — {item["floor_id"]}</text><text x="60" y="{y+58}" class="t">reviewable {review}/4 | advisory highest: {html.escape(ids)} | winner: NONE</text>'); y+=94
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="760"><defs><style>.h{{font:700 15px Arial}}.t{{font:13px Arial}}</style></defs><rect width="100%" height="100%" fill="#f8fafc"/><text x="40" y="42" font-family="Arial" font-size="23" font-weight="bold">Parcel 2 H1 V9 — Corridor + Entrance + Geometric Coherence</text><text x="40" y="78" class="t">3 frozen core hypotheses × RF1/RF2 | 4 termination hypotheses each | NO AUTHORITATIVE WINNER</text>{''.join(rows)}</svg>'''

def build(output):
    before={"v6":inventory(V6_DIR),"v7":inventory(V7_DIR),"v8":inventory(V8_DIR)}
    v8=json.loads(V8_JSON.read_text(encoding="utf-8")); rules=json.loads(RULES.read_text(encoding="utf-8"))
    assert v8["result"]["status"]=="H1_UPPER_FLOORS_READY_FOR_HUMAN_REVIEW"
    assert {t["topology_id"] for t in v8["core_hypotheses"]}==EXPECTED_IDS
    width=rules["resolved_design_inputs"]["common_access_corridor_minimum_clear_width_m"]
    depth=rules["resolved_design_inputs"]["apartment_internal_entrance_space_minimum_clear_depth_m"]
    area=rules["resolved_design_inputs"]["apartment_internal_entrance_space_minimum_area_m2"]
    engine=ResidentialCorridorEntranceGeometryIntelligenceV1(); items=[]
    for t in v8["core_hypotheses"]:
        for f in t["floors"]:
            result=engine.solve(floor_boundary=f["floor_boundary"],core_boundary=f["core_boundary_unchanged"],unit_boundaries=[u["boundary"] for u in f["units"]],entrances=[u["entrance"] for u in f["units"]],corridor_width=width,entrance_zone_depth=depth,entrance_zone_min_area=area)
            items.append({"topology_id":t["topology_id"],"floor_id":f["floor_id"],"program_unit_count":f["program_unit_count"],"core_geometry_mutated":False,"source_v8_floor":f,"intelligence":result})
    report={"contract":"Parcel2H1ResidentialCorridorEntranceGeometryV9","scope":"architecture_only","lineage":{"v6_dir":str(V6_DIR),"v7_dir":str(V7_DIR),"v8_dir":str(V8_DIR),"v8_json_sha256":sha(V8_JSON),"regulation_evidence_path":str(RULES),"regulation_evidence_sha256":sha(RULES),"inventories_before":before},"regulatory_application":{"common_corridor_clear_width_m":width,"apartment_internal_entrance_zone":{"minimum_depth_m":depth,"minimum_area_m2":area,"is_public_corridor_extension":False},"local_numeric_override_applied":False,"topic3_and_accessibility_dependent_checks":"UNRESOLVED_REQUIRES_BUILDING_GROUP_OCCUPANT_LOAD_AND_FIRE_STRATEGY"},"evaluations":items,"selection":{"winner":None,"authoritative_ranking":False,"final_selection_performed":False},"result":{"status":"V9_READY_FOR_HUMAN_REVIEW","reviewable_hypothesis_count":sum(h["status"]=="reviewable" for i in items for h in i["intelligence"]["hypotheses"]),"total_hypothesis_count":len(items)*4,"unresolved_internal_entrance_zone_cases":sum(not z["feasible"] for i in items for h in i["intelligence"]["hypotheses"] for z in h["private_entrance_zones"])},"snapshot":{"overwritten_files":[],"snapshot_required_for_v9_creation":False,"prior_corrective_overwrite_snapshots_recorded":True},"prohibited_workflows_executed":{"H2":False,"elevator_traffic":False,"structure":False,"BIM":False,"IFC":False,"render":False,"image_generation":False}}
    output.mkdir(parents=True,exist_ok=False); artifacts=[]
    jp=output/"PARCEL2_H1_RESIDENTIAL_CORRIDOR_ENTRANCE_GEOMETRY_V9.json"; jp.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    for item in items:
        floor=next(f for t in v8["core_hypotheses"] if t["topology_id"]==item["topology_id"] for f in t["floors"] if f["floor_id"]==item["floor_id"])
        p=output/f'{item["topology_id"]}-{item["floor_id"]}-V9.svg'; p.write_text(render(item["topology_id"],floor,item["intelligence"]),encoding="utf-8"); ET.parse(p); artifacts.append(p)
    ip=output/"PARCEL2_H1_RESIDENTIAL_CORRIDOR_ENTRANCE_GEOMETRY_V9_INDEX.svg"; ip.write_text(render_index(items),encoding="utf-8"); ET.parse(ip); artifacts += [jp,ip]
    after={"v6":inventory(V6_DIR),"v7":inventory(V7_DIR),"v8":inventory(V8_DIR)}
    if before!=after: raise RuntimeError("immutable V6/V7/V8 mutation detected")
    manifest={"contract":"Parcel2H1ResidentialCorridorEntranceGeometryV9Manifest","artifacts":[{"file":p.name,"sha256":sha(p),"size_bytes":p.stat().st_size} for p in sorted(artifacts)],"source_inventories_before":before,"source_inventories_after":after,"source_immutable":True,"selection":{"winner":None,"final_selection_performed":False}}
    mp=output/"ARTIFACT_MANIFEST.json"; mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return {"output":str(output),"result":report["result"],"manifest_sha256":sha(mp)}

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--output",type=Path,required=True); print(json.dumps(build(ap.parse_args().output),ensure_ascii=False,indent=2))
