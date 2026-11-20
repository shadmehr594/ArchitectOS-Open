from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import html, json, sys
from pathlib import Path
from shapely.geometry import Polygon

ROOT = Path(r"<repo-root>")
sys.path.insert(0, str(ROOT/"core/architecture/reasoning"))
from parcel2_architectural_graph_floor_plan_synthesizer_v8 import (
    ArchitecturalGraphFloorPlanSynthesizerV8, verify_projection_policy, verify_topic4,
)

SOURCE = ROOT/"exports/DEFAULT/parcel2_residential_room_planning_daylight_v4_20260913_131505/PARCEL2_RESIDENTIAL_ROOM_PLANNING_DAYLIGHT_V4.json"
NATIONAL = ROOT/"core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json"
POLICY = ROOT/"core/architecture/contracts/jurisdictional_projection_policy_v1.json"
PATTERNS = ROOT/"core/architecture/knowledge/residential_floor_precedent_patterns_v2.json"
PROFILE = "PARCEL2_MINAB_WORKING_20260913"
HISTORICAL = [
    "core/architecture/reasoning/parcel2_residential_room_planning_daylight_v3.py",
    "core/architecture/reasoning/parcel2_residential_room_planning_daylight_v4.py",
    "core/architecture/reasoning/parcel2_controlled_geometric_repair_search_v5.py",
    "core/architecture/reasoning/parcel2_floor_level_residential_synthesis_v6.py",
    "core/architecture/reasoning/parcel2_architectural_graph_floor_plan_synthesizer_v7.py",
    "tools/run_parcel2_architectural_graph_floor_plan_synthesizer_v7.py",
    "tests/test_parcel2_architectural_graph_floor_plan_synthesizer_v7.py",
    "core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json",
    "core/architecture/knowledge/residential_floor_precedent_patterns_v1.json",
]

def fingerprint():
    return {name: {"sha256": sha256((ROOT/name).read_bytes()).hexdigest(), "size": (ROOT/name).stat().st_size} for name in HISTORICAL}

def _points(values, scale, x0, y1):
    return " ".join(f"{(x-x0)*scale:.1f},{(y1-y)*scale:.1f}" for x,y in values)

def render(plan, path):
    floor = Polygon(plan["floor_boundary"]); x0,y0,x1,y1 = floor.bounds
    proj = plan["projection_balcony_opportunity"].get("polygon")
    all_poly = [floor] + ([Polygon(proj)] if proj else [])
    bounds = Polygon(all_poly[0]).union(all_poly[1] if len(all_poly)>1 else all_poly[0]).bounds
    bx0,by0,bx1,by1=bounds; scale=min(790/max(bx1-bx0,.1),560/max(by1-by0,.1)); p=lambda v:_points(v,scale,bx0,by1)
    title = " · ".join(str(plan["identity"][k]) if k!="program_hypothesis" else plan["identity"][k]["id"] for k in ("topology_id","floor_id","program_hypothesis","candidate_id"))
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="820" viewBox="0 0 1280 820">','<rect width="100%" height="100%" fill="#fbfaf6"/>',f'<text x="24" y="28" font-family="Arial" font-size="15" font-weight="bold">V8 · {html.escape(title)}</text>', '<text x="24" y="50" font-family="Arial" font-size="10">ARCHITECTURE ONLY · whole-floor sheet · no winner/ranking · project-local projection permission is not regulatory acceptance</text>', '<g transform="translate(24,74)">',f'<polygon points="{p(plan["floor_boundary"])}" fill="white" stroke="#152238" stroke-width="4"/>']
    if proj: out.append(f'<polygon points="{p(proj)}" fill="#f7c873" fill-opacity=".65" stroke="#b45309" stroke-width="3"/>')
    access=plan["core_common_access"]
    for key,color in (("core_polygon","#8795a1"),("common_landing_polygon","#d8cdb7")):
        if len(access[key])>=3: out.append(f'<polygon points="{p(access[key])}" fill="{color}" stroke="#333" stroke-width="2"/>')
    colors={"living":"#f4d6a0","bedroom":"#bcd7ed","kitchen":"#bcdcab","bathroom":"#aee3df","service":"#ddd"}
    for unit in plan["units"]:
        out.append(f'<polygon points="{p(unit["unit_boundary"])}" fill="none" stroke="#7b2cbf" stroke-width="2"/>')
        for room in unit["rooms"]:
            if len(room["polygon"])<3: continue
            g=Polygon(room["polygon"]); c=g.representative_point(); out.append(f'<polygon points="{p(room["polygon"])}" fill="{colors[room["use"]]}" fill-opacity=".8" stroke="#334155"/><text x="{(c.x-bx0)*scale:.1f}" y="{(by1-c.y)*scale:.1f}" text-anchor="middle" font-family="Arial" font-size="8">{html.escape(room["room_id"])}</text>')
    out.append('</g>')
    opp=plan["projection_balcony_opportunity"]; out.extend([f'<text x="24" y="670" font-family="Arial" font-size="10">Projection: {opp["candidate_type"]} · depth={opp["selected_depth_m"]}m · rule={opp["rule_id"]} · evidence_pending=true</text>',f'<text x="24" y="694" font-family="Arial" font-size="10">Facade map: street/public={plan["facade_value_map"]["street_public_edge"]} · private/quiet={plan["facade_value_map"]["private_quiet_edge"]} · derived from access/core evidence</text>',f'<text x="24" y="718" font-family="Arial" font-size="10" fill="#991b1b">FAIL-CLOSED: {html.escape(", ".join(plan["blockers"])[:175])}</text>','<text x="24" y="742" font-family="Arial" font-size="10">REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN=false · human architectural acceptance separate from software acceptance</text>','</svg>'])
    path.write_text("".join(out), encoding="utf-8")

def main(out_root=None):
    before=fingerprint(); source=json.loads(SOURCE.read_text(encoding="utf-8")); national=json.loads(NATIONAL.read_text(encoding="utf-8")); policy=json.loads(POLICY.read_text(encoding="utf-8")); patterns=json.loads(PATTERNS.read_text(encoding="utf-8"))
    engine=ArchitecturalGraphFloorPlanSynthesizerV8(national,patterns,policy,PROFILE)
    out=(Path(out_root) if out_root else ROOT/"exports/DEFAULT")/f'parcel2_architectural_graph_floor_plan_synthesizer_v8_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    out.mkdir(parents=True,exist_ok=False); plans=[]
    for _,group in engine.group(source):
        for plan in engine.synthesize_group(group):
            plans.append(plan); i=plan["identity"]; render(plan,out/f'{i["topology_id"]}-{i["floor_id"]}-{i["program_hypothesis"]["id"]}-{i["candidate_id"]}.svg')
    after=fingerprint(); immutable={k:{"before":before[k],"after":after[k],"byte_equal":before[k]==after[k]} for k in before}
    blockers={}
    for plan in plans:
        for blocker in plan["blockers"]: blockers[blocker]=blockers.get(blocker,0)+1
    policy_check=verify_projection_policy(policy,PROFILE); topic4=verify_topic4(national)
    software_ok=policy_check["status"]=="PASS" and topic4["status"]=="PASS" and all(x["byte_equal"] for x in immutable.values())
    resolved=sum(p["resolved_floor_hypothesis"] for p in plans)
    result={"contract":"ArchitecturalGraphFloorPlanSynthesizerV8Run","scope":"ARCHITECTURE_ONLY","pipeline_scope_exclusions":["H2","ELEVATOR_TRAFFIC","STRUCTURE","BIM","IFC","RENDER","IMAGE_GENERATION"],"candidate_count":len(plans),"selection":{"winner":None,"authoritative_ranking":False},"software_acceptance":{"status":"PASS" if software_ok else "FAIL_CLOSED","topic4_authority":topic4,"projection_policy":policy_check,"historical_inputs_immutable":all(x["byte_equal"] for x in immutable.values())},"human_architectural_acceptance":{"status":"PENDING_HUMAN_REVIEW" if resolved else "REJECTED_FAIL_CLOSED","resolved_count":resolved,"unresolved_count":len(plans),"independent_from_software_acceptance":True},"REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN":resolved>0,"fully_resolved_floor_hypothesis_count":resolved,"exact_next_blockers":blockers,"immutability":immutable,"overwrite_log":[],"additive_files_only":True,"render":{"executed":False},"image_generation":{"executed":False},"plans":plans}
    report=out/"PARCEL2_ARCHITECTURAL_GRAPH_FLOOR_PLAN_SYNTHESIZER_V8.json"; report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    entries=[{"file":p.name,"size":p.stat().st_size,"sha256":sha256(p.read_bytes()).hexdigest()} for p in sorted(out.iterdir())]
    (out/"ARTIFACT_MANIFEST.json").write_text(json.dumps({"entries":entries},indent=2),encoding="utf-8")
    print(out); print(json.dumps({"software":result["software_acceptance"]["status"],"human":result["human_architectural_acceptance"],"candidate_count":len(plans),"blocker_kinds":len(blockers)},indent=2))

if __name__ == "__main__": main(Path(sys.argv[1]) if len(sys.argv)>1 else None)
