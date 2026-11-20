from __future__ import annotations
from datetime import datetime
from hashlib import sha256
import html,json,sys
from pathlib import Path
from shapely.geometry import Polygon

ROOT=Path(r"<repo-root>")
HERE=Path(__file__).parent
sys.path.insert(0,str(ROOT/"core/architecture/reasoning"))
from parcel2_residential_room_planning_daylight_v2 import ResidentialRoomPlanningDaylightV2,verify_authority
V8=ROOT/"exports/DEFAULT/parcel2_h1_upper_floor_design_around_current_core_v8_20260912_212949/PARCEL2_H1_UPPER_FLOOR_DESIGN_AROUND_CURRENT_CORE_V8.json"
EV=ROOT/"core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json"

def pts(a,s,x0,y1): return " ".join(f"{(x-x0)*s:.1f},{(y1-y)*s:.1f}" for x,y in a)
def svg(plan,path,core):
 u=Polygon(plan["unit_boundary"]); x0,y0,x1,y1=u.bounds; s=min(760/max(x1-x0,.1),560/max(y1-y0,.1)); W,H=980,700
 def P(a): return pts(a,s,x0,y1)
 q=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', '<rect width="100%" height="100%" fill="#fbfaf6"/>',f'<text x="28" y="30" font-family="Arial" font-size="18" font-weight="bold">{html.escape(plan["topology_id"])} · {html.escape(plan["floor_id"])} · {html.escape(plan["unit_id"])} · {html.escape(plan["program_hypothesis"]["id"])}</text>',f'<g transform="translate(28,65)"><polygon points="{P(plan["unit_boundary"])}" fill="#fff" stroke="#17212b" stroke-width="5"/>']
 colors={"living":"#f7dba7","bedroom":"#c9dff2","kitchen":"#d2e8c8","bathroom":"#c9ece9","service":"#ddd","vestibule":"#f3c7c3","private_hall":"#eee8d5"}
 for r in plan["rooms"]:
  if len(r["polygon"])<3: continue
  g=Polygon(r["polygon"]); c=g.representative_point(); q.append(f'<polygon points="{P(r["polygon"])}" fill="{colors.get(r["use"],"#eee")}" fill-opacity=".82" stroke="#34495e" stroke-width="1.5"/><text x="{(c.x-x0)*s:.1f}" y="{(y1-c.y)*s:.1f}" text-anchor="middle" font-family="Arial" font-size="11">{html.escape(r["room_id"])} · {r["area_m2_geometry_derived"]:.1f} m²</text>')
 for d in plan["doors"]:
  x,y=d["opening"]["center"]; col="#16794d" if d["valid"] else "#c0392b"; q.append(f'<circle cx="{(x-x0)*s:.1f}" cy="{(y1-y)*s:.1f}" r="5" fill="white" stroke="{col}" stroke-width="2"/><text x="{(x-x0)*s+7:.1f}" y="{(y1-y)*s-5:.1f}" font-family="Arial" font-size="8">D({html.escape(d["space_a"])}→{html.escape(d["space_b"])})</text>')
 for w in plan["windows"]:
  x,y=w["geometry"]["center"]; q.append(f'<line x1="{(x-x0)*s-10:.1f}" y1="{(y1-y)*s:.1f}" x2="{(x-x0)*s+10:.1f}" y2="{(y1-y)*s:.1f}" stroke="#168aad" stroke-width="5"/><text x="{(x-x0)*s+12:.1f}" y="{(y1-y)*s+3:.1f}" font-family="Arial" font-size="8">{html.escape(w["window_id"])}→EXTERIOR {w["glazing_area_m2"]}m²</text>')
 tx,ty=plan["unit_threshold"]; q.append(f'<path d="M {(tx-x0)*s-9:.1f} {(y1-ty)*s-9:.1f} L {(tx-x0)*s+9:.1f} {(y1-ty)*s+9:.1f} M {(tx-x0)*s+9:.1f} {(y1-ty)*s-9:.1f} L {(tx-x0)*s-9:.1f} {(y1-ty)*s+9:.1f}" stroke="#7b2cbf" stroke-width="3"/><text x="{(tx-x0)*s+12:.1f}" y="{(y1-ty)*s+18:.1f}" font-family="Arial" font-size="10">UNIT THRESHOLD / common corridor stops</text></g>')
 status="RESOLVED" if plan["resolved_room_level"] else "FAIL-CLOSED · "+", ".join(plan["spatial_problems"])
 q += [f'<text x="28" y="650" font-family="Arial" font-size="12" fill="#922">{html.escape(status)}</text>','<text x="28" y="675" font-family="Arial" font-size="10">Legend: wall/room boundary · D actual relation (green valid/red invalid) · blue verified window · purple unit threshold · core/common corridor inherited from V8 context</text>','</svg>']; path.write_text("".join(q),encoding="utf-8")

def main(out_root):
 ev=json.loads(EV.read_text(encoding="utf-8")); source=json.loads(V8.read_text(encoding="utf-8")); eng=ResidentialRoomPlanningDaylightV2(ev)
 stamp=datetime.now().strftime("%Y%m%d_%H%M%S"); out=Path(out_root)/f"parcel2_residential_room_planning_daylight_v2_{stamp}"; out.mkdir(parents=True)
 plans=[]
 for t in source["core_hypotheses"]:
  for f in t["floors"]:
   for u in f["units"]:
    for h in eng.hypotheses():
     p=eng.solve(u,f["public_corridor"],t["topology_id"],f["floor_id"],h); plans.append(p); svg(p,out/f'{t["topology_id"]}-{f["floor_id"]}-{u["unit_id"]}-{h["id"]}.svg',t["core_geometry"])
 software={"authority":verify_authority(ev),"plan_count":len(plans),"three_core_topologies":len({p["topology_id"] for p in plans})==3,"rf1_rf2_present":sorted({p["floor_id"] for p in plans}),"resolved_plan_count":sum(p["resolved_room_level"] for p in plans)}
 human={"status":"ACCEPTED" if all(p["resolved_room_level"] for p in plans) else "REJECTED_FAIL_CLOSED","unresolved_plan_count":sum(not p["resolved_room_level"] for p in plans),"note":"No automatic winner or authoritative ranking."}
 result={"contract":"ResidentialRoomPlanningDaylightLightwellIntelligenceV2","scope":"ARCHITECTURE_ONLY","source_v8":str(V8),"authority":software["authority"],"selection":{"winner":None,"authoritative_ranking":False},"software_acceptance":software,"human_architectural_acceptance":human,"REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN":all(p["resolved_room_level"] for p in plans),"plans":plans}
 jp=out/"PARCEL2_RESIDENTIAL_ROOM_PLANNING_DAYLIGHT_V2.json"; jp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
 manifest=[]
 for p in sorted(out.iterdir()): manifest.append({"file":p.name,"size":p.stat().st_size,"sha256":sha256(p.read_bytes()).hexdigest()})
 (out/"ARTIFACT_MANIFEST.json").write_text(json.dumps({"entries":manifest},indent=2),encoding="utf-8")
 print(out); print(json.dumps({"software":software,"human":human,"real":result["REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN"]},indent=2))
if __name__=="__main__": main(sys.argv[1] if len(sys.argv)>1 else HERE.parent/"outputs")
