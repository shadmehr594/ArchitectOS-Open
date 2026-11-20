"""Parcel 2 H1 access-first/frontage-first architecture-only diagnostic."""
from __future__ import annotations

import hashlib, html, json
from datetime import datetime
from pathlib import Path

from shapely.geometry import Polygon

from core.architecture.reasoning.generic_access_first_pilotis_search_v1 import GenericAccessFirstPilotisSearchV1

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "exports/DEFAULT/parcel2_temporary_core_reservation_geometry_v1_20260912_194032/PARCEL2_TEMPORARY_CORE_RESERVATION_GEOMETRY_V1.json"
BASE = ROOT / "exports/DEFAULT/parcel2_basement_v2_20260909_143231_229427/PARCEL2_BASEMENT_V2_CONTRACT.json"
ASSUMPTION = ROOT / "core/architecture/contracts/parcel2_temporary_core_reservation_design_assumption_v1.json"

def load(p): return json.loads(p.read_text(encoding="utf-8"))
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def points(poly, ox, oy, scale, minx, maxy): return " ".join(f"{ox+(x-minx)*scale:.1f},{oy+(maxy-y)*scale:.1f}" for x,y in poly)

def render(report):
    selected = report["candidates"][:6]; width, height = 1800, 1260; body=[]
    colors={"core":"#f0cf88","stair":"#7e57c2","elevator":"#c2185b","lobby":"#9a6b12","stall":"#70a7d8","aisle":"#c9ced3","vehicle":"#7b1fa2","ped":"#16803a","commercial":"#ef8f43"}
    for i,c in enumerate(selected):
        ox=45+(i%3)*585; oy=130+(i//3)*535; parcel=report["parcel"]
        xs=[p[0] for p in parcel]; ys=[p[1] for p in parcel]; s=min(490/(max(xs)-min(xs)),390/(max(ys)-min(ys)))
        pp=lambda p:points(p,ox+20,oy+410,s,min(xs),max(ys))
        body += [f'<rect x="{ox}" y="{oy}" width="550" height="505" fill="white" stroke="#777"/>',
                 f'<text x="{ox+12}" y="{oy+22}" font-family="Arial" font-size="13" font-weight="bold">{html.escape(c["candidate_id"])}</text>',
                 f'<polygon points="{pp(parcel)}" fill="none" stroke="#111" stroke-width="2"/>',
                 f'<polygon points="{pp(c["direct_commercial_street_frontage_region"])}" fill="{colors["commercial"]}" fill-opacity=".30" stroke="{colors["commercial"]}"/>',
                 f'<polygon points="{pp(c["public_pedestrian_path"])}" fill="{colors["ped"]}" fill-opacity=".22" stroke="{colors["ped"]}"/>',
                 f'<polygon points="{pp(c["vehicle_corridor"])}" fill="{colors["vehicle"]}" fill-opacity=".17" stroke="{colors["vehicle"]}" stroke-width="2"/>',
                 f'<polygon points="{pp(c["aisle_manoeuvre"])}" fill="{colors["aisle"]}" fill-opacity=".55" stroke="#555"/>',
                 f'<polygon points="{pp(c["temp_core"])}" fill="{colors["core"]}" fill-opacity=".55" stroke="#9a6500" stroke-width="2"/>']
        for stall in c["stalls"]: body.append(f'<polygon points="{pp(stall["polygon"])}" fill="{colors["stall"]}" fill-opacity=".60" stroke="#245b88"/>')
        core=Polygon(c["temp_core"]); mincx,mincy,maxcx,maxcy=core.bounds
        shaft=[[mincx,mincy],[mincx+2.1,mincy],[mincx+2.1,mincy+2.1],[mincx,mincy+2.1]]
        body += [f'<polygon points="{pp(shaft)}" fill="none" stroke="{colors["elevator"]}" stroke-width="2" stroke-dasharray="4 2"><title>TEMP ELEVATOR SHAFT 2.10x2.10m — non-final</title></polygon>',
                 f'<path d="M {pp([[maxcx,mincy],[mincx,maxcy]])}" stroke="{colors["stair"]}" stroke-width="3" stroke-dasharray="5 3"/><path d="M {pp([[mincx,mincy],[maxcx,maxcy]])}" stroke="{colors["stair"]}" stroke-width="3" stroke-dasharray="5 3"/>',
                 f'<polyline points="{pp(c["vehicle_entrance"]+[[(c["vehicle_corridor"][2][0]+c["vehicle_corridor"][3][0])/2,(c["vehicle_corridor"][2][1]+c["vehicle_corridor"][3][1])/2]])}" fill="none" stroke="{colors["vehicle"]}" stroke-width="3" marker-end="url(#arrow)"/>',
                 f'<text x="{ox+12}" y="{oy+450}" font-family="Arial" font-size="10">TEMP CORE (cream) — NOT COMMERCIAL | STAIR 2-FLIGHT schematic/non-final</text>',
                 f'<text x="{ox+12}" y="{oy+466}" font-family="Arial" font-size="10">TEMP ELEVATOR SHAFT 2.10×2.10m | LOBBY / SPATIAL SIZING UNRESOLVED</text>',
                 f'<text x="{ox+12}" y="{oy+482}" font-family="Arial" font-size="10">P {c["parking_count"]} | legitimate commercial frontage {c["commercial_candidate_area_m2"]:.2f} m² | NO WINNER</text>']
    legend='<text x="45" y="68" font-family="Arial" font-size="14">CREAM = TEMP CORE (NOT COMMERCIAL) | ORANGE = direct-frontage commercial candidate | BLUE = stalls | GREY = aisle/manoeuvre | PURPLE = vehicle ingress/egress | GREEN = public path</text><text x="45" y="91" font-family="Arial" font-size="13">All core/stair/elevator/lobby elements are schematic/non-final. Stair flight_count=2 selected; topology/placement unresolved. No final winner selected.</text>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><defs><marker id="arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="#7b1fa2"/></marker></defs><rect width="100%" height="100%" fill="#fafafa"/><text x="45" y="36" font-family="Arial" font-size="22" font-weight="bold">Parcel 2 H1 — ACCESS-FIRST / FRONTAGE-FIRST — human review</text>{legend}{"".join(body)}</svg>'

def main(output_root=None):
    base, checkpoint, assumption = load(BASE), load(CHECKPOINT), load(ASSUMPTION)
    parcel, frontage = base["site"]["parcel"], base["site"]["frontage"]
    domain={"polygon":parcel,"floor_scope":"ground_pilotis","evidence_status":"resolved","provenance":[{"source":str(BASE),"role":"authoritative_parcel_ground_domain"}]}
    fronts={"segment":frontage,"status":"confirmed","provenance":[{"source":str(BASE),"role":"confirmed_project_frontage"}]}
    access={"vehicle_clear_width":float(base["requirements"]["ramp"]["clear_width"]),"pedestrian_clear_width":float(base["requirements"]["parking_pedestrian"]["required_clear_width"]),"commercial_candidate_depth":4.0}
    parking={"minimum_required_capacity":3,"stall_width":2.5,"stall_depth":5.0,"aisle_width":5.0,"vehicle_clear_width":access["vehicle_clear_width"],"provenance":[{"source":"parcel2_current_project_parking_requirement"}]}
    search=GenericAccessFirstPilotisSearchV1().produce(domain,fronts,access,checkpoint["core_placement_hypotheses"]["candidates"],parking,{"hypothesis_id":"H1","provenance":[{"source":"H1_access_first_iteration"}]})
    candidates=search["candidates"]
    report={"contract":"Parcel2H1AccessFirstFrontageFirstDiagnosticV2","generated_at":datetime.now().astimezone().isoformat(),"scope":"architecture_only","parcel":parcel,"frontage":frontage,
      "input_checkpoint":{"path":str(CHECKPOINT),"sha256":digest(CHECKPOINT),"historical_h1_candidate_count":19,"reused_as_root_cause_evidence":True,"mutated":False},
      "search_policy":{"order":list("ABCDEFGHI"),"cardinal_assumption_used":False,"fixed_offset_used":False,"fixed_family_used":False,"historical_seed_used":False},
      "numeric_policy":{"vehicle_width_m":access["vehicle_clear_width"],"vehicle_width_provenance":"current_project_requirement_only","pedestrian_width_m":access["pedestrian_clear_width"],"pedestrian_width_provenance":"current_project_requirement_only","old_3m_separation_fixture_used":False},
      "vertical_core_visualization":{"temp_core_not_commercial":True,"elevator_shaft_proxy_m":[2.1,2.1],"elevator_status":"TEMP_DESIGN_ASSUMPTION_NON_FINAL","stair_flight_count":2,"stair_status":"AUTHORITATIVE_SELECTED_COUNT_TOPOLOGY_AND_PLACEMENT_NON_FINAL","lobby_status":"LOBBY / SPATIAL SIZING UNRESOLVED"},
      "candidate_count":len(candidates),"passing_candidate_ids":[c["candidate_id"] for c in candidates],"candidates":candidates,"rejection_diagnostics":search["rejection_diagnostics"],"blockers":[] if candidates else ["no_geometry_passed_all_access_parking_commercial_frontage_gates"],
      "final_selection_performed":False,"winner":None,"h1_ready_for_human_architectural_selection":bool(candidates),"h2_status":"parked_not_evaluated","prohibited_workflows_executed":{"elevator_traffic":False,"structure":False,"BIM":False,"IFC":False,"render":False,"image_generation":False}}
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S"); out=(Path(output_root) if output_root else ROOT/"exports/DEFAULT")/f"parcel2_h1_access_first_v2_{stamp}"; out.mkdir(parents=True,exist_ok=False)
    jp=out/"PARCEL2_H1_ACCESS_FIRST_V2.json"; sp=out/"PARCEL2_H1_ACCESS_FIRST_V2.svg"
    jp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"); sp.write_text(render(report),encoding="utf-8")
    answer={"json":str(jp),"json_sha256":digest(jp),"svg":str(sp),"svg_sha256":digest(sp),"candidate_count":len(candidates),"ready":bool(candidates)}
    print(json.dumps(answer,indent=2)); return answer

if __name__ == "__main__": main()
