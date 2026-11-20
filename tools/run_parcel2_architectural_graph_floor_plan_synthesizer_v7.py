from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import html, json, sys
from pathlib import Path
from shapely.geometry import Polygon

ROOT = Path(r"<repo-root>")
LOCAL = Path(__file__).resolve().parent
ENGINE_DIR = (ROOT/"core/architecture/reasoning") if ROOT.exists() else LOCAL
sys.path.insert(0, str(ENGINE_DIR))
from parcel2_architectural_graph_floor_plan_synthesizer_v7 import ArchitecturalGraphFloorPlanSynthesizerV7, verify_topic4

SOURCE = ROOT/"exports/DEFAULT/parcel2_residential_room_planning_daylight_v4_20260913_131505/PARCEL2_RESIDENTIAL_ROOM_PLANNING_DAYLIGHT_V4.json"
EVIDENCE = ROOT/"core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json"
PATTERNS = ROOT/"core/architecture/knowledge/residential_floor_precedent_patterns_v1.json"
HISTORICAL = [
 "core/architecture/reasoning/parcel2_residential_room_planning_daylight_v3.py",
 "core/architecture/reasoning/parcel2_residential_room_planning_daylight_v4.py",
 "core/architecture/reasoning/parcel2_controlled_geometric_repair_search_v5.py",
 "core/architecture/reasoning/parcel2_floor_level_residential_synthesis_v6.py",
 "tools/run_parcel2_residential_room_planning_daylight_v3.py",
 "tools/run_parcel2_residential_room_planning_daylight_v4.py",
 "tools/run_parcel2_controlled_geometric_repair_search_v5.py",
 "tools/run_parcel2_floor_level_residential_synthesis_v6.py",
 "tests/test_parcel2_residential_room_planning_daylight_v3.py",
 "tests/test_parcel2_residential_room_planning_daylight_v4.py",
 "tests/test_parcel2_controlled_geometric_repair_search_v5.py",
 "tests/test_parcel2_floor_level_residential_synthesis_v6.py",
 "core/architecture/knowledge/residential_floor_precedent_patterns_v1.json",
 "core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json",
]

def fingerprint():
    return {name:{"sha256":sha256((ROOT/name).read_bytes()).hexdigest(),"size":(ROOT/name).stat().st_size} for name in HISTORICAL}

def pts(values, scale, x0, y1):
    return " ".join(f"{(x-x0)*scale:.1f},{(y1-y)*scale:.1f}" for x,y in values)

def render(plan, path):
    floor=Polygon(plan["floor_boundary"]); x0,y0,x1,y1=floor.bounds; scale=min(760/max(x1-x0,.1),540/max(y1-y0,.1))
    p=lambda v:pts(v,scale,x0,y1); ident=plan["identity"]; a=plan["core_common_access"]
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="820" viewBox="0 0 1280 820">','<rect width="100%" height="100%" fill="#fbfaf6"/>',
      f'<text x="25" y="28" font-family="Arial" font-size="16" font-weight="bold">V7 Architectural Graph → Floor Plan · {html.escape(ident["topology_id"])} · {html.escape(ident["floor_id"])} · {html.escape(ident["program_hypothesis"]["id"])} · {ident["candidate_id"]}</text>',
      '<text x="25" y="49" font-family="Arial" font-size="10">WHOLE-FLOOR HUMAN REVIEW · local orthogonal frame from buildable/floor envelope · no winner/ranking</text>',
      f'<g transform="translate(25,75)"><polygon points="{p(plan["floor_boundary"])}" fill="white" stroke="#14213d" stroke-width="5"/>']
    for key,color,label in (("core_polygon","#9aa6b2","CORE"),("stair_polygon","#708090","STAIR"),("elevator_polygon","#52616b","ELEVATOR"),("common_landing_polygon","#d8cdb7","COMMON LANDING")):
      if len(a[key])>=3:
        g=Polygon(a[key]); c=g.representative_point(); out += [f'<polygon points="{p(a[key])}" fill="{color}" fill-opacity=".72" stroke="#333" stroke-width="2"/>',f'<text x="{(c.x-x0)*scale:.1f}" y="{(y1-c.y)*scale:.1f}" text-anchor="middle" font-family="Arial" font-size="8">{label}</text>']
    colors={"living":"#f4d6a0","bedroom":"#bcd7ed","kitchen":"#bcdcab","bathroom":"#aee3df","service":"#ddd"}
    for ui,u in enumerate(plan["units"]):
      out.append(f'<polygon points="{p(u["unit_boundary"])}" fill="none" stroke="{("#7b2cbf" if ui==0 else "#d97706")}" stroke-width="3"/>')
      for z in u["private_circulation"]:
        if len(z["polygon"])>=3: out.append(f'<polygon points="{p(z["polygon"])}" fill="#f2ead3" stroke="#7c6f46" stroke-width="1.5"/>')
      for r in u["rooms"]:
        if len(r["polygon"])<3: continue
        g=Polygon(r["polygon"]); c=g.representative_point(); out += [f'<polygon points="{p(r["polygon"])}" fill="{colors[r["use"]]}" fill-opacity=".8" stroke="#34495e" stroke-width="1.2"/>',f'<text x="{(c.x-x0)*scale:.1f}" y="{(y1-c.y)*scale:.1f}" text-anchor="middle" font-family="Arial" font-size="8">{r["room_id"]} · {r["area_m2"]:.1f}m² · {r["zone"]}</text>']
      for d in u["doors"]:
        x,y=d["center"]; out.append(f'<circle cx="{(x-x0)*scale:.1f}" cy="{(y1-y)*scale:.1f}" r="5" fill="white" stroke="{("#15803d" if d["valid"] else "#c62828")}" stroke-width="2"/>')
      for w in u["windows"]:
        x,y=w["center"]; out.append(f'<rect x="{(x-x0)*scale-4:.1f}" y="{(y1-y)*scale-4:.1f}" width="8" height="8" fill="{("#0e7490" if w["valid"] else "#dc2626")}"/>')
      if u["lightwell"]["created"]: out.append(f'<polygon points="{p(u["lightwell"]["polygon"])}" fill="#b8eef5" stroke="#087f8c" stroke-width="3"/>')
    out.append('</g>')
    status='RESOLVED · HUMAN REVIEW PENDING' if plan['resolved_floor_hypothesis'] else 'FAIL-CLOSED · '+', '.join(plan['blockers'])
    out += [f'<text x="25" y="650" font-family="Arial" font-size="10" fill="#991b1b">{html.escape(status[:190])}</text>',
      f'<text x="25" y="676" font-family="Arial" font-size="10">ACCESS: '+html.escape('; '.join(f'{k}: threshold→landing→stair={v["stair_pass"]}, threshold→landing→elevator={v["elevator_pass"]}' for k,v in a['unit_reachability'].items()))+'</text>',
      f'<text x="25" y="700" font-family="Arial" font-size="10">LEDGER: rooms={plan["allocation"]["ROOM"]:.1f} · private circulation={plan["allocation"]["PRIVATE_CIRCULATION"]:.1f} · residual={plan["allocation"]["RESIDUAL_UNRESOLVED"]:.1f}m² ({100*plan["allocation"]["residual_ratio"]:.1f}%) · lightwell={plan["allocation"]["LIGHTWELL"]:.1f}</text>',
      '<text x="25" y="724" font-family="Arial" font-size="10">Legend: room color=zone/use · beige=derived circulation · circles=doors (green valid/red invalid) · squares=ROOM→SOURCE→WINDOW · cyan=physical lightwell</text>',
      '<text x="25" y="748" font-family="Arial" font-size="10">Service/wet cluster is shown by kitchen+bathroom+service adjacency. Residual remains explicit; room areas are never inflated to absorb it.</text>','</svg>']
    path.write_text(''.join(out),encoding='utf-8')

def main(out_root):
    before=fingerprint(); source=json.loads(SOURCE.read_text(encoding='utf-8')); evidence=json.loads(EVIDENCE.read_text(encoding='utf-8')); patterns=json.loads(PATTERNS.read_text(encoding='utf-8'))
    engine=ArchitecturalGraphFloorPlanSynthesizerV7(evidence,patterns)
    out=Path(out_root)/f'parcel2_architectural_graph_floor_plan_synthesizer_v7_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    out.mkdir(parents=True,exist_ok=False); plans=[]
    for _,group in engine.group(source):
      for plan in engine.synthesize_group(group):
        plans.append(plan); i=plan['identity']; render(plan,out/f'{i["topology_id"]}-{i["floor_id"]}-{i["program_hypothesis"]["id"]}-{i["candidate_id"]}.svg')
    after=fingerprint(); immutable={k:{"before":before[k],"after":after[k],"byte_equal":before[k]==after[k]} for k in before}
    resolved=sum(p['resolved_floor_hypothesis'] for p in plans); blockers={}
    for p in plans:
      for b in p['blockers']: blockers[b]=blockers.get(b,0)+1
    software_ok=verify_topic4(evidence)['status']=='PASS' and all(x['byte_equal'] for x in immutable.values())
    result={"contract":"ArchitecturalGraphFloorPlanSynthesizerV7Run","scope":"ARCHITECTURE_ONLY","pipeline_scope_exclusions":["H2","ELEVATOR_TRAFFIC","STRUCTURE","BIM","IFC","RENDER","IMAGE_GENERATION"],
      "source_checkpoint":str(SOURCE),"candidate_count":len(plans),"selection":{"winner":None,"authoritative_ranking":False},
      "software_acceptance":{"status":"PASS" if software_ok else "FAIL_CLOSED","topic4_authority":verify_topic4(evidence),"historical_inputs_immutable":all(x['byte_equal'] for x in immutable.values())},
      "human_architectural_acceptance":{"status":"PENDING_HUMAN_REVIEW" if resolved else "REJECTED_FAIL_CLOSED","independent_from_tests":True,"resolved_count":resolved,"unresolved_count":len(plans)-resolved},
      "REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN":resolved>0,"fully_resolved_floor_hypothesis_count":resolved,"exact_next_blockers":blockers,"immutability":immutable,
      "overwrite_log":[],"additive_files_only":True,"render":{"executed":False},"image_generation":{"executed":False},"plans":plans}
    (out/'PARCEL2_ARCHITECTURAL_GRAPH_FLOOR_PLAN_SYNTHESIZER_V7.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    entries=[{"file":p.name,"size":p.stat().st_size,"sha256":sha256(p.read_bytes()).hexdigest()} for p in sorted(out.iterdir())]
    (out/'ARTIFACT_MANIFEST.json').write_text(json.dumps({"entries":entries},indent=2),encoding='utf-8')
    print(out); print(json.dumps({"software":result['software_acceptance'],"human":result['human_architectural_acceptance'],"blocker_kinds":len(blockers)},indent=2))

if __name__=='__main__': main(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'exports/DEFAULT')
