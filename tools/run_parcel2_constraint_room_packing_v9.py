from __future__ import annotations
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import html,json,sys
from shapely.geometry import Polygon

ROOT=Path(r"<repo-root>")
sys.path.insert(0,str(ROOT/"core/architecture/reasoning"))
from parcel2_constraint_room_packing_v9 import ConstraintRoomPackingV9
V8=ROOT/"exports/DEFAULT/parcel2_architectural_graph_floor_plan_synthesizer_v8_20260913_171805/PARCEL2_ARCHITECTURAL_GRAPH_FLOOR_PLAN_SYNTHESIZER_V8.json"
TOPIC4=ROOT/"core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json"
POLICY=ROOT/"core/architecture/contracts/jurisdictional_projection_policy_v1.json"
HIST=[f"core/architecture/reasoning/parcel2_{x}" for x in ("residential_room_planning_daylight_v3.py","residential_room_planning_daylight_v4.py","controlled_geometric_repair_search_v5.py","floor_level_residential_synthesis_v6.py","architectural_graph_floor_plan_synthesizer_v7.py","architectural_graph_floor_plan_synthesizer_v8.py")]
HIST += ["tools/run_parcel2_architectural_graph_floor_plan_synthesizer_v8.py","tests/test_parcel2_architectural_graph_floor_plan_synthesizer_v8.py"]
def fp(): return {x:{"sha256":sha256((ROOT/x).read_bytes()).hexdigest(),"size":(ROOT/x).stat().st_size} for x in HIST}
def points(a,s,x0,y1):return " ".join(f"{(x-x0)*s:.1f},{(y1-y)*s:.1f}" for x,y in a)
def svg(plan,path):
 f=Polygon(plan["floor_boundary"]); x0,y0,x1,y1=f.bounds;s=min(820/(x1-x0),560/(y1-y0));p=lambda a:points(a,s,x0,y1)
 out=['<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="820">','<rect width="100%" height="100%" fill="#faf9f5"/>',f'<text x="24" y="28" font-family="Arial" font-size="15" font-weight="bold">V9 · {html.escape(plan["identity"]["topology_id"])} · RF2 · CENTRAL_SHARED_LIGHTWELL</text>','<g transform="translate(24,62)">',f'<polygon points="{p(plan["floor_boundary"])}" fill="white" stroke="#111827" stroke-width="4"/>']
 for key,c in (("core_polygon","#8996a3"),("stair_polygon","#64748b"),("elevator_polygon","#475569"),("common_landing_polygon","#d6c7ad")):
  g=plan["core_common_access"].get(key,[])
  if len(g)>2:out.append(f'<polygon points="{p(g)}" fill="{c}" stroke="#222"/>')
 colors={"living":"#f2cf8d","bedroom":"#afd0e7","kitchen":"#acd7a8","bathroom":"#a8ded8","service":"#d4d4d4"}
 for u in plan["units"]:
  out.append(f'<polygon points="{p(u["unit_boundary"])}" fill="none" stroke="#7c3aed" stroke-width="2"/>')
  lw=u["lightwell"];out.append(f'<polygon points="{p(lw["polygon"])}" fill="#dbeafe" stroke="#2563eb" stroke-width="2"/>')
  for c in u["private_circulation"]:out.append(f'<polygon points="{p(c["polygon"])}" fill="#eee8dc" stroke="#8b7355"/>')
  for r in u["rooms"]:
   g=Polygon(r["polygon"]);q=g.representative_point();out.append(f'<polygon points="{p(r["polygon"])}" fill="{colors[r["use"]]}" stroke="#334155"/><text x="{(q.x-x0)*s:.1f}" y="{(y1-q.y)*s:.1f}" text-anchor="middle" font-family="Arial" font-size="8">{r["room_id"]}</text>')
 out += ['</g>','<text x="24" y="680" font-family="Arial" font-size="11">Doors are host-wall-derived during packing · room→source→window verified · lightwell reserved before rooms</text>','<text x="24" y="704" font-family="Arial" font-size="11">NO_PROJECTION baseline · no winner/ranking · REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN=true pending human review</text>','</svg>'];path.write_text(''.join(out),encoding='utf-8')
def main(out_root=None):
 before=fp();v8=json.loads(V8.read_text(encoding='utf-8'));e=ConstraintRoomPackingV9(json.loads(TOPIC4.read_text()),json.loads(POLICY.read_text()));search=e.search(v8["plans"])
 out=(Path(out_root) if out_root else ROOT/"exports/DEFAULT")/f'parcel2_constraint_room_packing_v9_{datetime.now().strftime("%Y%m%d_%H%M%S")}';out.mkdir(parents=True)
 for n,p in enumerate(search["survivors"],1):svg(p,out/f'V9_RF2_SURVIVOR_{n:02d}_{p["identity"]["topology_id"]}.svg')
 after=fp();immut={x:{"before":before[x],"after":after[x],"byte_equal":before[x]==after[x]} for x in before}
 result={"contract":"ConstraintRoomPackingV9Run","scope":"ARCHITECTURE_ONLY","excluded":["H2","ELEVATOR_TRAFFIC","STRUCTURE","BIM","IFC","RENDER","IMAGE_GENERATION"],"hard_feasibility_pruning_before_svg":True,"attempt_count":search["attempt_count"],"pruned_count":sum(x["pruned"] for x in search["diagnostics"]),"svg_count":len(search["survivors"]),"diagnostics":search["diagnostics"],"plans":search["survivors"],"software_acceptance":{"status":"PASS" if all(x["byte_equal"] for x in immut.values()) else "FAIL_CLOSED"},"human_architectural_acceptance":{"status":"PENDING_HUMAN_REVIEW" if search["survivors"] else "REJECTED_FAIL_CLOSED","independent":True},"REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN":bool(search["survivors"]),"immutability":immut,"overwrite_log":[],"precedent_geometry_copied":False,"render_executed":False,"image_generation_executed":False}
 report=out/"PARCEL2_CONSTRAINT_ROOM_PACKING_V9.json";report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 entries=[{"file":x.name,"size":x.stat().st_size,"sha256":sha256(x.read_bytes()).hexdigest()} for x in sorted(out.iterdir())];(out/"ARTIFACT_MANIFEST.json").write_text(json.dumps({"entries":entries},indent=2),encoding='utf-8')
 print(out);print(json.dumps({"software":result["software_acceptance"],"human":result["human_architectural_acceptance"],"attempted":result["attempt_count"],"pruned":result["pruned_count"],"svg":result["svg_count"]},indent=2))
if __name__=="__main__":main(Path(sys.argv[1]) if len(sys.argv)>1 else None)
