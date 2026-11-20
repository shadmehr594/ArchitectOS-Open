"""Run generic architectural geometry/form reasoning diagnostically on frozen Parcel 2 V8/V9."""
from __future__ import annotations

import hashlib, html, json, sys
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.architectural_geometry_form_reasoning_v1 import ArchitecturalGeometryFormReasoningV1

V6=ROOT/"exports/DEFAULT/parcel2_h1_circulation_core_topology_v6_20260912_210133"
V7=ROOT/"exports/DEFAULT/parcel2_h1_human_architectural_quality_review_v7_20260912_211316"
V8=ROOT/"exports/DEFAULT/parcel2_h1_upper_floor_design_around_current_core_v8_20260912_212949"
V9=ROOT/"exports/DEFAULT/parcel2_h1_residential_corridor_entrance_geometry_v9_20260913_000244"
V8_JSON=V8/"PARCEL2_H1_UPPER_FLOOR_DESIGN_AROUND_CURRENT_CORE_V8.json"
KNOWLEDGE=ROOT/"core/architecture/contracts/architectural_geometry_form_precedent_knowledge_v1.json"

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def inventory(folder): return {p.name:{"sha256":sha(p),"size_bytes":p.stat().st_size} for p in sorted(folder.iterdir()) if p.is_file()}
def polygons(value):
    if not value:return []
    return [value] if value and isinstance(value[0][0],(int,float)) else value
def svg_poly(points,tr,fill,stroke,opacity=.4,dash=""):
    return f'<polygon points="{" ".join(f"{tr(p)[0]:.1f},{tr(p)[1]:.1f}" for p in points)}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="2" {dash}/>'
def frame(boundary):
    xs=[p[0] for p in boundary];ys=[p[1] for p in boundary]; x0,x1=min(xs),max(xs);y0,y1=min(ys),max(ys)
    scale=min(650/max(x1-x0,.001),780/max(y1-y0,.001))
    return lambda p:(55+(p[0]-x0)*scale,900-(55+(p[1]-y0)*scale))

def render(item):
    floor=item["source_floor"]; result=item["diagnostic"]; boundary=floor["floor_boundary"];tr=frame(boundary)
    layers=[svg_poly(boundary,tr,"#ffffff","#111827",.9)]
    palette=["#bfdbfe","#ddd6fe","#fecdd3","#bbf7d0"]
    for idx,u in enumerate(floor["units"]): layers.append(svg_poly(u["boundary"],tr,palette[idx%len(palette)],"#334155",.45))
    layers.append(svg_poly(floor["core_boundary_unchanged"],tr,"#d8b4fe","#6b21a8",.7))
    for p in polygons(floor.get("public_corridor",[])): layers.append(svg_poly(p,tr,"#fde68a","#a16207",.65))
    colors=["#2563eb","#dc2626","#059669","#7c3aed","#ea580c"]
    for idx,p in enumerate(result["proposals"]):
        for poly in polygons(p["target_geometry"]): layers.append(svg_poly(poly,tr,colors[idx%len(colors)],colors[idx%len(colors)],.18,'stroke-dasharray="8 5"'))
    for u in floor["units"]:
        c=[sum(x for x,y in u["boundary"])/len(u["boundary"]),sum(y for x,y in u["boundary"])/len(u["boundary"])]
        x,y=tr(c);layers.append(f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial" font-size="13" text-anchor="middle">{html.escape(u["unit_id"])}</text>')
    cards=[]
    for idx,p in enumerate(result["proposals"]):
        y=145+idx*112; benefits=", ".join(k for k,v in p["metric_evidence_0_1"].items() if v>0)[:95]
        cards.append(f'<rect x="760" y="{y-28}" width="800" height="98" fill="white" stroke="{colors[idx%len(colors)]}"/><text x="780" y="{y}" class="h">{html.escape(p["proposal_id"])} — {html.escape(p["geometry_family_descriptor"])}</text><text x="780" y="{y+25}" class="t">operation: {html.escape(p["operation"])}</text><text x="780" y="{y+48}" class="t">benefits: {html.escape(benefits)} | gate: {str(p["justification_gate_passed"]).lower()}</text>')
    issues=", ".join(i["issue_id"] for i in result["detected_issues"]) or "none detected at envelope resolution"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="980"><defs><style>.h{{font:700 14px Arial}}.t{{font:12px Arial}}</style></defs><rect width="100%" height="100%" fill="#f8fafc"/><text x="40" y="38" font-family="Arial" font-size="22" font-weight="bold">Architectural Geometry/Form Diagnostic — {html.escape(item["topology_id"])} — {html.escape(item["floor_id"])}</text><text x="40" y="68" class="t">PLAN + CONTEXT-DERIVED PROPOSAL GEOMETRIES | NO WINNER | V8/V9 FROZEN</text><text x="40" y="94" class="t">Issues: {html.escape(issues[:180])}</text>{''.join(layers)}<rect x="745" y="105" width="830" height="820" fill="none" stroke="#94a3b8"/>{''.join(cards)}<text x="770" y="900" class="t">Dashed overlays are diagnostic transformations, not selected shapes or construction geometry.</text></svg>'''

def render_index(items):
    rows=[]
    for i,item in enumerate(items):
        y=120+i*105; lang=item["diagnostic"]["detected_geometry_language"]; issues=item["diagnostic"]["detected_issues"]
        rows.append(f'<rect x="45" y="{y}" width="1510" height="82" fill="white" stroke="#94a3b8"/><text x="65" y="{y+28}" class="h">{html.escape(item["topology_id"])} — {html.escape(item["floor_id"])}</text><text x="65" y="{y+55}" class="t">language {lang["primary"]} | issues {len(issues)} | proposals {len(item["diagnostic"]["proposals"])} | winner NONE</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="800"><defs><style>.h{{font:700 15px Arial}}.t{{font:13px Arial}}</style></defs><rect width="100%" height="100%" fill="#f8fafc"/><text x="40" y="42" font-family="Arial" font-size="24" font-weight="bold">Parcel 2 — Generic Architectural Geometry/Form Diagnostic</text><text x="40" y="78" class="t">Envelope-level application after V9 | simple aligned response first | no authoritative rank / no winner</text>{''.join(rows)}</svg>'''

def build(output):
    before={k:inventory(v) for k,v in {"v6":V6,"v7":V7,"v8":V8,"v9":V9}.items()}
    source=json.loads(V8_JSON.read_text(encoding="utf-8")); knowledge=json.loads(KNOWLEDGE.read_text(encoding="utf-8"))
    engine=ArchitecturalGeometryFormReasoningV1(); items=[]
    for topology in source["core_hypotheses"]:
        for floor in topology["floors"]:
            spaces=[{"id":u["unit_id"],"use":"unit_shape","boundary":u["boundary"],"doors":[u["entrance"]],"privacy":"private"} for u in floor["units"]]
            spaces.append({"id":"CORE","use":"core","boundary":floor["core_boundary_unchanged"],"privacy":"neutral"})
            connections=[["CORE",u["unit_id"]] for u in floor["units"]]
            diag=engine.analyze(plan_boundary=floor["floor_boundary"],spaces=spaces,connections=connections,
                exterior_edges=[floor["floor_boundary"][i:i+2] for i in range(len(floor["floor_boundary"])-1)],
                entrances=[u["entrance"] for u in floor["units"]])
            items.append({"topology_id":topology["topology_id"],"floor_id":floor["floor_id"],"source_floor":floor,"diagnostic":diag})
    report={"contract":"Parcel2ArchitecturalGeometryFormDiagnosticV1","scope":"architecture_only",
      "generic_intelligence":"ArchitecturalGeometryFormReasoningV1","lineage":{"checkpoint":"after_V9","inventories_before":before,"v8_json_sha256":sha(V8_JSON),"v9_frozen":True},
      "knowledge":{"path":str(KNOWLEDGE),"sha256":sha(KNOWLEDGE),"authority_class":knowledge["authority_class"],"used_as_regulation":False},
      "evaluations":items,"selection":{"winner":None,"authoritative_ranking":False,"final_selection_performed":False},
      "prohibited_workflows_executed":{"H2":False,"elevator_traffic":False,"structure":False,"BIM":False,"IFC":False,"render":False,"image_generation":False}}
    output.mkdir(parents=True,exist_ok=False); arts=[]
    jp=output/"PARCEL2_ARCHITECTURAL_GEOMETRY_FORM_DIAGNOSTIC_V1.json";jp.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8");arts.append(jp)
    for item in items:
        p=output/f'{item["topology_id"]}-{item["floor_id"]}-GEOMETRY-FORM-DIAGNOSTIC.svg';p.write_text(render(item),encoding="utf-8");ET.parse(p);arts.append(p)
    ip=output/"PARCEL2_ARCHITECTURAL_GEOMETRY_FORM_DIAGNOSTIC_V1_INDEX.svg";ip.write_text(render_index(items),encoding="utf-8");ET.parse(ip);arts.append(ip)
    after={k:inventory(v) for k,v in {"v6":V6,"v7":V7,"v8":V8,"v9":V9}.items()}; assert before==after
    mp=output/"ARTIFACT_MANIFEST.json";mp.write_text(json.dumps({"contract":"Parcel2ArchitecturalGeometryFormDiagnosticV1Manifest","artifacts":[{"file":p.name,"sha256":sha(p),"size_bytes":p.stat().st_size} for p in sorted(arts)],"source_inventories_before":before,"source_inventories_after":after,"source_immutable":True,"selection":{"winner":None,"final_selection_performed":False}},indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return report

if __name__=="__main__":
    out=ROOT/"exports/DEFAULT"/f"parcel2_architectural_geometry_form_diagnostic_v1_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    build(out);print(out)
