"""Architecture-only Parcel 2 room-level runner and engineering SVG exporter."""
from __future__ import annotations
import argparse, hashlib, html, json, sys, xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(r"<repo-root>")
sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.parcel2_room_level_design_v1 import Parcel2RoomLevelDesignV1

V6=ROOT/"exports/DEFAULT/parcel2_h1_circulation_core_topology_v6_20260912_210133"
V7=ROOT/"exports/DEFAULT/parcel2_h1_human_architectural_quality_review_v7_20260912_211316"
V8=ROOT/"exports/DEFAULT/parcel2_h1_upper_floor_design_around_current_core_v8_20260912_212949"
V9=ROOT/"exports/DEFAULT/parcel2_h1_residential_corridor_entrance_geometry_v9_20260913_000244"
V8J=V8/"PARCEL2_H1_UPPER_FLOOR_DESIGN_AROUND_CURRENT_CORE_V8.json"
IMMUTABLE={
 "agi_v2":ROOT/"core/architecture/reasoning/architectural_geometric_intervention_reasoning_v2.py",
 "v6":ROOT/"tools/run_parcel2_h1_circulation_core_topology_v6.py","v7":ROOT/"tools/run_parcel2_h1_human_architectural_quality_review_v7.py",
 "v8":ROOT/"tools/run_parcel2_h1_upper_floor_design_around_current_core_v8.py","v9":ROOT/"tools/run_parcel2_h1_residential_corridor_entrance_geometry_v9.py",
 "replay":ROOT/"core/architecture/reasoning/architectural_precedent_importer_mapping_replay_v2.py"}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def inv(): return {k:{"path":str(p),"sha256":sha(p),"size_bytes":p.stat().st_size} for k,p in IMMUTABLE.items()}
def poly(points,tr,fill,stroke,w=1.4): return f'<polygon points="{" ".join(f"{tr(p)[0]:.1f},{tr(p)[1]:.1f}" for p in points)}" fill="{fill}" stroke="{stroke}" stroke-width="{w}"/>'

def svg(plan,h):
    ub=plan["unit_boundary"]; xs=[p[0] for p in ub];ys=[p[1] for p in ub]; s=min(690/max(max(xs)-min(xs),.1),690/max(max(ys)-min(ys),.1)); tr=lambda p:(55+(p[0]-min(xs))*s,100+(max(ys)-p[1])*s)
    colors={"living":"#dbeafe","kitchen":"#fef3c7","bedroom":"#ede9fe","bathroom":"#cffafe","service":"#e5e7eb","internal_circulation":"#dcfce7","entrance_vestibule":"#fed7aa"}; layers=[poly(ub,tr,"#fff","#111827",3)]
    if len(plan.get("common_corridor",[]))>=3: layers.append(poly(plan["common_corridor"],tr,"#fef08a","#a16207",2))
    if len(plan.get("core_boundary",[]))>=3: layers.append(poly(plan["core_boundary"],tr,"#fecaca","#991b1b",2))
    for key,label,color in (("schematic_stair","STAIR","#7c3aed"),("schematic_elevator","ELEVATOR","#be185d")):
        if len(plan.get(key,[]))>=3:
            layers.append(poly(plan[key],tr,"none",color,3));cx=sum(p[0] for p in plan[key])/len(plan[key]);cy=sum(p[1] for p in plan[key])/len(plan[key]);lx,ly=tr([cx,cy]);layers.append(f'<text x="{lx:.1f}" y="{ly:.1f}" class="room" text-anchor="middle">{label}</text>')
    for r in h["rooms"]:
        if len(r["boundary"])<3: continue
        layers.append(poly(r["boundary"],tr,colors[r["use"]],"#334155")); cx=sum(p[0] for p in r["boundary"])/len(r["boundary"]);cy=sum(p[1] for p in r["boundary"])/len(r["boundary"]);x,y=tr([cx,cy]);layers.append(f'<text x="{x:.1f}" y="{y:.1f}" class="room" text-anchor="middle">{html.escape(r["room_id"])} {r["area_m2_geometry_derived"]:.2f} m²</text>')
        dx,dy=tr(r["door"]["point"]);layers.append(f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="4" fill="#111827"/><text x="{dx+5:.1f}" y="{dy-5:.1f}" class="room">D</text>')
        if r["opening_opportunity"]["point"]:
            wx,wy=tr(r["opening_opportunity"]["point"]);layers.append(f'<line x1="{wx-8:.1f}" y1="{wy:.1f}" x2="{wx+8:.1f}" y2="{wy:.1f}" stroke="#0284c7" stroke-width="5"/><text x="{wx+10:.1f}" y="{wy-5:.1f}" class="room">W?</text>')
    x,y=tr(plan["hypotheses"][0]["threshold"]);layers.append(f'<circle cx="{x}" cy="{y}" r="7" fill="#dc2626"/><text x="{x+10}" y="{y-8}" class="t">UNIT THRESHOLD / ENTRY DOOR</text>')
    issues=", ".join(h["spatial_problem_detection"]) or "none"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="900"><style>.room{{font:700 10px Arial}}.t{{font:13px Arial}}.h{{font:700 18px Arial}}</style><rect width="100%" height="100%" fill="#f8fafc"/><text x="45" y="38" class="h">{html.escape(plan["topology_id"])} — {plan["floor_id"]} — {plan["unit_id"]} — {h["program_hypothesis"]["id"]}</text>{''.join(layers)}<rect x="800" y="95" width="650" height="460" fill="white" stroke="#94a3b8"/><text x="825" y="128" class="h">HUMAN ARCHITECTURAL REVIEW</text><text x="825" y="165" class="t">Program: NON-AUTHORITATIVE hypothesis; bedroom count {h["program_hypothesis"]["bedroom_count"]}</text><text x="825" y="198" class="t">Unit area: {plan["unit_area_m2_geometry_derived"]:.2f} m² (geometry-derived)</text><text x="825" y="231" class="t">Public corridor stops at threshold: {str(h["public_corridor_stops_at_threshold"]).lower()}</text><text x="825" y="264" class="t">Detected issues: {html.escape(issues)}</text><text x="825" y="297" class="t">AGI invoked: {str(bool(h["intervention"])).lower()} — only after detector issue</text><text x="825" y="330" class="t">Precedent geometry copied: false</text><text x="825" y="363" class="t">Winner: NONE | authoritative ranking: false</text><text x="825" y="405" class="t">Red = preserved stair/elevator/core aggregate; yellow = common corridor.</text><text x="825" y="438" class="t">D = schematic door; W? = exterior opening opportunity, not final window.</text><text x="825" y="471" class="t">Orange = private entrance/vestibule, not public corridor.</text></svg>'''

def build(output):
    before=inv(); data=json.loads(V8J.read_text(encoding="utf-8")); engine=Parcel2RoomLevelDesignV1(); plans=[]
    for t in data["core_hypotheses"]:
        for f in t["floors"]:
            for u in f["units"]:
                plan=engine.solve_unit(unit_record=u,public_corridor=f["public_corridor"],topology_id=t["topology_id"],floor_id=f["floor_id"])
                plan["core_boundary"]=f["core_boundary_unchanged"]
                plan["common_corridor"]=plan["hypotheses"][0]["public_corridor_geometry"]
                plan["schematic_stair"]=t["vertical_anchor"]["schematic_stair"]
                plan["schematic_elevator"]=t["vertical_anchor"]["schematic_elevator"]
                plans.append(plan)
    report={"contract":"Parcel2RoomLevelDesignV1","scope":"architecture_only","checkpoint":"PRECEDENT_REPLAY_GATE=PASS","program_authority":{"unit_counts":"PROJECT_REQUIREMENT","bedroom_counts":"DESIGN_ASSUMPTION_NON_AUTHORITATIVE","areas":"GEOMETRY_DERIVED_ONLY","population":None},"plans":plans,"human_comparison":{"three_topologies_retained":True,"winner":None,"authoritative_ranking":False},"readiness":{"human_review":True,"actual_room_level_plan_generated":True,"envelope_level_only":False},"immutability":{"before":before},"prohibited_workflows_executed":{"H2":False,"elevator_traffic":False,"structure":False,"BIM":False,"IFC":False,"render":False,"image_generation":False}}
    output.mkdir(parents=True,exist_ok=False); jp=output/"PARCEL2_ROOM_LEVEL_DESIGN_V1.json";jp.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8"); arts=[jp]
    for p in plans:
        for h in p["hypotheses"]:
            fn=f'{p["topology_id"]}-{p["floor_id"]}-{p["unit_id"]}-{h["program_hypothesis"]["id"]}.svg';q=output/fn;q.write_text(svg(p,h),encoding="utf-8");ET.parse(q);arts.append(q)
    after=inv()
    if before!=after: raise RuntimeError("immutable checkpoint mutation")
    report["immutability"]["after"]=after;report["immutability"]["byte_equal"]=True;jp.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    manifest={"contract":"Parcel2RoomLevelDesignV1Manifest","artifacts":[{"file":p.name,"sha256":sha(p),"size_bytes":p.stat().st_size} for p in sorted(arts)],"source_immutability":report["immutability"],"selection":{"winner":None,"authoritative_ranking":False}}
    mp=output/"ARTIFACT_MANIFEST.json";mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return {"output":str(output),"plan_count":len(plans),"artifact_count":len(arts)+1,"room_level":True,"winner":None}

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--output",type=Path,required=True);print(json.dumps(build(ap.parse_args().output),ensure_ascii=False,indent=2))
