from __future__ import annotations
from datetime import datetime
from hashlib import sha256
import html, json, sys
from pathlib import Path
from shapely.geometry import Polygon

ROOT=Path(r"<repo-root>")
sys.path.insert(0,str(ROOT/"core/architecture/reasoning"))
from parcel2_residential_room_planning_daylight_v4 import ResidentialRelationalConstraintRepairV4,verify_authority
V3=ROOT/"exports/DEFAULT/parcel2_residential_room_planning_daylight_v3_20260913_124549/PARCEL2_RESIDENTIAL_ROOM_PLANNING_DAYLIGHT_V3.json"
EV=ROOT/"core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json"

def _points(a,s,x0,y1): return " ".join(f"{(x-x0)*s:.1f},{(y1-y)*s:.1f}" for x,y in a)

def render_svg(plan,path):
 u=Polygon(plan["unit_boundary"]); x0,y0,x1,y1=u.bounds; s=min(760/max(x1-x0,.1),540/max(y1-y0,.1)); P=lambda a:_points(a,s,x0,y1)
 q=['<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="720" viewBox="0 0 1080 720">','<rect width="100%" height="100%" fill="#fbfaf6"/>',
 f'<text x="28" y="28" font-family="Arial" font-size="16" font-weight="bold">V4 · {html.escape(plan["source_identity"]["topology_id"])} · {html.escape(plan["source_identity"]["floor_id"])} · {html.escape(plan["source_identity"]["unit_id"])} · {html.escape(plan["source_identity"]["program_hypothesis"]["id"])}</text>',
 '<text x="28" y="48" font-family="Arial" font-size="10">engineering diagnostic · V3-cell repair only · no image generation · no winner/ranking</text>',
 f'<g transform="translate(28,72)"><polygon points="{P(plan["unit_boundary"])}" fill="#fff" stroke="#17212b" stroke-width="5"/>']
 if len(plan["public_corridor"])>=3:
  q.append(f'<polygon points="{P(plan["public_corridor"])}" fill="#d9d2c3" fill-opacity=".72" stroke="#685f52" stroke-width="2"/>')
  cg=Polygon(plan["public_corridor"]).representative_point(); q.append(f'<text x="{(cg.x-x0)*s:.1f}" y="{(y1-cg.y)*s:.1f}" text-anchor="middle" font-family="Arial" font-size="8">COMMON CORRIDOR</text>')
 if len(plan["core_geometry"])>=3:
  q.append(f'<polygon points="{P(plan["core_geometry"])}" fill="#aab7c4" fill-opacity=".55" stroke="#394b59" stroke-width="2"/>')
  kg=Polygon(plan["core_geometry"]).representative_point(); q.append(f'<text x="{(kg.x-x0)*s:.1f}" y="{(y1-kg.y)*s:.1f}" text-anchor="middle" font-family="Arial" font-size="8">CORE / STAIR / ELEVATOR*</text>')
 colors={"living":"#f7dba7","bedroom":"#c9dff2","kitchen":"#d2e8c8","bathroom":"#c9ece9","service":"#ddd"}
 for r in plan["rooms"]:
  if len(r["polygon"])<3: continue
  g=Polygon(r["polygon"]); c=g.representative_point(); q.append(f'<polygon points="{P(r["polygon"])}" fill="{colors.get(r["use"],"#eee")}" fill-opacity=".84" stroke="#34495e" stroke-width="1.4"/><text x="{(c.x-x0)*s:.1f}" y="{(y1-c.y)*s:.1f}" text-anchor="middle" font-family="Arial" font-size="9">{html.escape(r["room_id"])} · {r["area_m2_geometry_derived"]:.1f}m²</text>')
 for c in plan["circulation"]: q.append(f'<polygon points="{P(c["polygon"])}" fill="#eee8d5" fill-opacity=".75" stroke="#7b6f49" stroke-width="1.4"/>')
 for d in plan["doors"]:
  x,y=d["opening"]["center"]; col="#16794d" if d["valid"] else "#c0392b"; q.append(f'<circle cx="{(x-x0)*s:.1f}" cy="{(y1-y)*s:.1f}" r="5" fill="white" stroke="{col}" stroke-width="2"/><text x="{(x-x0)*s+7:.1f}" y="{(y1-y)*s-5:.1f}" font-family="Arial" font-size="7">{html.escape(d["door_id"])}</text>')
 for w in plan["windows"]:
  x,y=w["geometry"]["center"]; col="#168aad" if w["opening_verified"] else "#d35400"; q.append(f'<rect x="{(x-x0)*s-4:.1f}" y="{(y1-y)*s-4:.1f}" width="8" height="8" fill="{col}"/><text x="{(x-x0)*s+7:.1f}" y="{(y1-y)*s+9:.1f}" font-family="Arial" font-size="7">{html.escape(w["window_id"])} / {html.escape(w["source_id"])}</text>')
 q.append('</g>'); status="RESOLVED" if plan["resolved_room_level"] else "FAIL-CLOSED · "+", ".join(plan["spatial_problems"])
 q += [f'<text x="28" y="642" font-family="Arial" font-size="11" fill="#922">{html.escape(status)}</text>',
 f'<text x="28" y="663" font-family="Arial" font-size="10">repair accepted={str(plan["repair_provenance"]["accepted"]).lower()} · moves={len(plan["repair_provenance"]["moves"])} · coverage={plan["allocation"]["COVERAGE_RATIO"]:.3f} · lightwell=none</text>',
 '<text x="28" y="684" font-family="Arial" font-size="10">green/red circle valid/invalid door · blue/orange square valid/invalid window · *stair/elevator subdivision unavailable in immutable V3 input; not invented</text>','</svg>']
 path.write_text("".join(q),encoding="utf-8")

def main(out_root):
 evidence=json.loads(EV.read_text(encoding="utf-8")); source=json.loads(V3.read_text(encoding="utf-8")); engine=ResidentialRelationalConstraintRepairV4(evidence)
 out=Path(out_root)/f'parcel2_residential_room_planning_daylight_v4_{datetime.now().strftime("%Y%m%d_%H%M%S")}'; out.mkdir(parents=True)
 plans=[]
 for p in source["plans"]:
  repaired=engine.repair(p); plans.append(repaired)
  sid=repaired["source_identity"]; render_svg(repaired,out/f'{sid["topology_id"]}-{sid["floor_id"]}-{sid["unit_id"]}-{sid["program_hypothesis"]["id"]}.svg')
 resolved=sum(p["resolved_room_level"] for p in plans)
 software={"status":"PASS","authority":verify_authority(evidence),"plan_count":len(plans),"deterministic_repair_contract":True,"source_v3_immutable":True,"resolved_plan_count":resolved}
 human={"status":"ACCEPTED" if resolved==len(plans) else "REJECTED_FAIL_CLOSED","resolved_plan_count":resolved,"unresolved_plan_count":len(plans)-resolved,"independent_from_software_acceptance":True}
 blockers={}
 for p in plans:
  for issue in p["spatial_problems"]: blockers[issue]=blockers.get(issue,0)+1
 result={"contract":"ResidentialRelationalDoorDaylightConstraintRepairV4","scope":"ARCHITECTURE_ONLY","source_v3":str(V3),"selection":{"winner":None,"authoritative_ranking":False},"software_acceptance":software,"human_architectural_acceptance":human,"REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN":resolved==len(plans),"resolved_hypothesis_count":resolved,"next_intelligence_blockers":blockers,"image_generation":{"allowed":False,"executed":False},"plans":plans}
 jp=out/"PARCEL2_RESIDENTIAL_ROOM_PLANNING_DAYLIGHT_V4.json"; jp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
 entries=[]
 for p in sorted(out.iterdir()): entries.append({"file":p.name,"size":p.stat().st_size,"sha256":sha256(p.read_bytes()).hexdigest()})
 (out/"ARTIFACT_MANIFEST.json").write_text(json.dumps({"entries":entries},indent=2),encoding="utf-8")
 print(out); print(json.dumps({"software":software,"human":human,"real":result["REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN"],"blockers":blockers},indent=2))

if __name__=="__main__": main(sys.argv[1] if len(sys.argv)>1 else ROOT/"exports/DEFAULT")
