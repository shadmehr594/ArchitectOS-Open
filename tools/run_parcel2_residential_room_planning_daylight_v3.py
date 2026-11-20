from __future__ import annotations
from datetime import datetime
from hashlib import sha256
import html,json,sys
from pathlib import Path
from shapely.geometry import Polygon

ROOT=Path(r"<repo-root>")
sys.path.insert(0,str(ROOT/"core/architecture/reasoning"))
from parcel2_residential_room_planning_daylight_v3 import ResidentialRoomPlanningDaylightV3,verify_authority
V8=ROOT/"exports/DEFAULT/parcel2_h1_upper_floor_design_around_current_core_v8_20260912_212949/PARCEL2_H1_UPPER_FLOOR_DESIGN_AROUND_CURRENT_CORE_V8.json"
EV=ROOT/"core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json"

def _points(a,s,x0,y1): return " ".join(f"{(x-x0)*s:.1f},{(y1-y)*s:.1f}" for x,y in a)
def render_svg(plan,path):
 u=Polygon(plan["unit_boundary"]); x0,y0,x1,y1=u.bounds; s=min(760/max(x1-x0,.1),560/max(y1-y0,.1)); P=lambda a:_points(a,s,x0,y1)
 q=['<svg xmlns="http://www.w3.org/2000/svg" width="980" height="700" viewBox="0 0 980 700">','<rect width="100%" height="100%" fill="#fbfaf6"/>',
    f'<text x="28" y="30" font-family="Arial" font-size="16" font-weight="bold">{html.escape(plan["topology_id"])} · {html.escape(plan["floor_id"])} · {html.escape(plan["unit_id"])} · {html.escape(plan["program_hypothesis"]["id"])}</text>',
    f'<text x="28" y="50" font-family="Arial" font-size="10">derived frame {plan["dominant_frame"]["angle_degrees"]}° · diagnostic only · no winner/ranking</text>',
    f'<g transform="translate(28,70)"><polygon points="{P(plan["unit_boundary"])}" fill="#fff" stroke="#17212b" stroke-width="5"/>']
 colors={"living":"#f7dba7","bedroom":"#c9dff2","kitchen":"#d2e8c8","bathroom":"#c9ece9","service":"#ddd"}
 for r in plan["rooms"]:
  if len(r["polygon"])<3: continue
  g=Polygon(r["polygon"]); c=g.representative_point(); q.append(f'<polygon points="{P(r["polygon"])}" fill="{colors.get(r["use"],"#eee")}" fill-opacity=".84" stroke="#34495e" stroke-width="1.4"/><text x="{(c.x-x0)*s:.1f}" y="{(y1-c.y)*s:.1f}" text-anchor="middle" font-family="Arial" font-size="10">{html.escape(r["room_id"])} · {r["area_m2_geometry_derived"]:.1f}m²</text>')
 for cspace in plan["circulation"]:
  if len(cspace["polygon"])>=3: q.append(f'<polygon points="{P(cspace["polygon"])}" fill="#eee8d5" fill-opacity=".75" stroke="#7b6f49" stroke-width="1"/>')
 for d in plan["doors"]:
  x,y=d["opening"]["center"]; col="#16794d" if d["valid"] else "#c0392b"; q.append(f'<circle cx="{(x-x0)*s:.1f}" cy="{(y1-y)*s:.1f}" r="4" fill="white" stroke="{col}" stroke-width="2"/>')
 for w in plan["windows"]:
  x,y=w["geometry"]["center"]; q.append(f'<circle cx="{(x-x0)*s:.1f}" cy="{(y1-y)*s:.1f}" r="4" fill="#168aad"/>')
 q.append('</g>'); status="RESOLVED" if plan["resolved_room_level"] else "FAIL-CLOSED · "+", ".join(plan["spatial_problems"])
 q += [f'<text x="28" y="652" font-family="Arial" font-size="11" fill="#922">{html.escape(status)}</text>',f'<text x="28" y="675" font-family="Arial" font-size="10">coverage {plan["allocation"]["COVERAGE_RATIO"]:.3f} · green/red door = valid/invalid shared wall · blue = verified window</text>','</svg>']
 path.write_text("".join(q),encoding="utf-8")

def main(out_root):
 ev=json.loads(EV.read_text(encoding="utf-8")); source=json.loads(V8.read_text(encoding="utf-8")); engine=ResidentialRoomPlanningDaylightV3(ev)
 out=Path(out_root)/f'parcel2_residential_room_planning_daylight_v3_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
 out.mkdir(parents=True); plans=[]
 for t in source["core_hypotheses"]:
  for f in t["floors"]:
   for u in f["units"]:
    for h in engine.hypotheses():
     p=engine.solve(u,f["public_corridor"],t["core_geometry"],t["topology_id"],f["floor_id"],h); plans.append(p)
     render_svg(p,out/f'{t["topology_id"]}-{f["floor_id"]}-{u["unit_id"]}-{h["id"]}.svg')
 resolved=sum(p["resolved_room_level"] for p in plans)
 software={"status":"PASS","authority":verify_authority(ev),"plan_count":len(plans),"three_core_topologies":len({p["topology_id"] for p in plans})==3,"rf1_rf2_present":sorted({p["floor_id"] for p in plans}),"resolved_plan_count":resolved}
 human={"status":"ACCEPTED" if resolved==len(plans) else "REJECTED_FAIL_CLOSED","resolved_plan_count":resolved,"unresolved_plan_count":len(plans)-resolved,"independent_from_software_acceptance":True}
 result={"contract":"ResidentialRoomPlanningDaylightLightwellIntelligenceV3","scope":"ARCHITECTURE_ONLY","source_v8":str(V8),"v2_failure_evidence":{"checkpoint_claims":{"resolved_plan_count":0,"residual_white_space":"HIGH","door_graph":"INCOMPLETE","daylight":"INCOMPLETE","service":"UNRESOLVED","circulation":"OVERSIZED_AND_OBLIQUE"},"artifact_path":None,"artifact_availability":"NOT_FOUND_DURING_V3_READ_ONLY_AUDIT"},"selection":{"winner":None,"authoritative_ranking":False},"software_acceptance":software,"human_architectural_acceptance":human,"REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN":resolved==len(plans),"plans":plans}
 jp=out/"PARCEL2_RESIDENTIAL_ROOM_PLANNING_DAYLIGHT_V3.json"; jp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
 entries=[]
 for p in sorted(out.iterdir()): entries.append({"file":p.name,"size":p.stat().st_size,"sha256":sha256(p.read_bytes()).hexdigest()})
 (out/"ARTIFACT_MANIFEST.json").write_text(json.dumps({"entries":entries},indent=2),encoding="utf-8")
 print(out); print(json.dumps({"software":software,"human":human,"real":result["REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN"]},indent=2))

if __name__=="__main__": main(sys.argv[1] if len(sys.argv)>1 else ROOT/"exports/DEFAULT")
