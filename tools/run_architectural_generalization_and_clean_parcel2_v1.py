"""Run the gated architecture-only study and emit a small decision-support package."""
from __future__ import annotations

from datetime import datetime
from html import escape
import json
from pathlib import Path

from core.architecture.reasoning.architectural_generalization_study_v1 import CleanParcel2ResolveV1, IndependentGeneralizationStudyV1
from core.architecture.reasoning.minab_residential_architectural_rules_v1 import MinabResidentialArchitecturalRulesV1

ROOT=Path(__file__).resolve().parents[1]


def _local_site(site):
    a,b=site["frontage"]; tx,ty=b[0]-a[0],b[1]-a[1]; length=(tx*tx+ty*ty)**.5; tx,ty=tx/length,ty/length
    nx,ny=-ty,tx; centroid=[sum(p[0] for p in site["parcel"])/len(site["parcel"]),sum(p[1] for p in site["parcel"])/len(site["parcel"])]
    if (centroid[0]-a[0])*nx+(centroid[1]-a[1])*ny<0: nx,ny=-nx,-ny
    points=[[(p[0]-a[0])*tx+(p[1]-a[1])*ty,(p[0]-a[0])*nx+(p[1]-a[1])*ny] for p in site["parcel"]]
    return {"local_parcel_polygon":points,"frontages":[{"edge":"south","role":"valuable_public_road","value":1.0}],
            "neighbors":{"north":"adjacent_private","east":"adjacent_private","west":"adjacent_private","south":"public_road"},
            "road_width":site.get("road_width"),"source":site.get("source"),"source_parcel":site["parcel"],"source_frontage":site["frontage"]}


def _requirements(contract):
    r=contract["requirements"]; parking=r["parking"]; core=r["core"]
    return {"program":"mixed_use_residential","parking_required_count":parking["minimum_count"],
            "parking_stall_size":[parking["stall_width"],parking["stall_depth"]],"vehicle_access_width":r["ramp"]["clear_width"],
            "core_size":[min(core["maximum_width"],3.8),min(core["maximum_depth"],5.2)],"vertical_core":True,
            "elevator_required":core["elevator_required"],"residential_units_per_floor":2,"terrace_required":True,"terrace_depth":1.5,
            "daylight_court_size":[3.0,4.0],"dedicated_pedestrian_entrance_mandatory":False,
            "pedestrian_modes_to_consider":["NO_DEDICATED_PEDESTRIAN_ENTRANCE","DEDICATED_PEDESTRIAN_ENTRANCE"],
            "source":"clean_user_program_and_approved_contracts"}


def _polygon(points,scale,ox,oy,color,opacity=.35,stroke="#243247"):
    if not points:return ""
    pts=" ".join(f"{ox+x*scale:.1f},{oy-y*scale:.1f}" for x,y in points)
    return f'<polygon points="{pts}" fill="{color}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="1.2"/>'


def _candidate_svg(candidate,title):
    parcel=candidate.get("site_polygon") or []; all_points=parcel or candidate["residential_unit_envelopes"][0]
    xs=[p[0] for p in all_points]; ys=[p[1] for p in all_points]; scale=min(320/max(max(xs)-min(xs),1),390/max(max(ys)-min(ys),1)); oy=485+min(ys)*scale
    gx,ux=45-min(xs)*scale,455-min(xs)*scale
    body=[f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="650"><defs><pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse"><path d="M0,8 L8,0" stroke="#64748b" stroke-width="1"/></pattern></defs><rect width="900" height="650" fill="#fbfcfe"/><text x="28" y="32" font-size="20" font-family="Arial">{escape(title)}</text><text x="45" y="60" font-family="Arial" font-weight="bold">GROUND</text><text x="455" y="60" font-family="Arial" font-weight="bold">RESIDENTIAL LEVEL (typical)</text>']
    for ox in (gx,ux): body.append(_polygon(parcel,scale,ox,oy,"#f8fafc",1))
    for key,color,opacity in (("vehicle_reserved_zone","#94a3b8",.24),("vehicle_circulation_field","#64748b",.42),("commercial_viable","#f59e0b",.58),("commercial_nonviable_fragments","#ef4444",.25),("ground_common","#22c55e",.45),("ground_service","#0f766e",.5),("core","#4c1d95",.62),("stair","#7c3aed",.8),("elevator","#4338ca",.8),("lobby","#a78bfa",.8)):
        value=candidate.get(key,[]); shapes=value if value and isinstance(value[0],list) and value[0] and isinstance(value[0][0],list) else [value]
        for shape in shapes: body.append(_polygon(shape,scale,gx,oy,color,opacity))
    for stall in candidate["parking_stalls"]: body.append(_polygon(stall,scale,gx,oy,"#65a30d",.55))
    entrance=candidate.get("vehicle_entrance",[])
    if len(entrance)==2:
        body.append(f'<line x1="{gx+entrance[0][0]*scale:.1f}" y1="{oy-entrance[0][1]*scale:.1f}" x2="{gx+entrance[1][0]*scale:.1f}" y2="{oy-entrance[1][1]*scale:.1f}" stroke="#dc2626" stroke-width="5"/><text x="{gx+entrance[0][0]*scale:.1f}" y="{oy-entrance[0][1]*scale-7:.1f}" font-size="10" font-family="Arial">vehicle entrance</text>')
    for i,u in enumerate(candidate["residential_unit_envelopes"]): body.append(_polygon(u,scale,ux,oy,"#fb7185" if i else "#fdba74",.42))
    for zone,color in (("PUBLIC","#fde68a"),("TRANSITION","#c4b5fd"),("PRIVATE","#fbcfe8"),("SERVICE","#99f6e4")):
        for shape in candidate.get("zoning_geometry",{}).get(zone,[]): body.append(_polygon(shape,scale,ux,oy,color,.16,color))
    for t in candidate["terraces"]: body.append(_polygon(t,scale,ux,oy,"#16a34a",.72))
    for key,color in (("core","#4c1d95"),("stair","#7c3aed"),("elevator","#4338ca"),("lobby","#a78bfa"),("daylight_court","#38bdf8")):
        body.append(_polygon(candidate.get(key,[]),scale,ux,oy,color,.68))
    records=candidate["floor_program_ownership"]["spaces"]
    for floor,ox in (("ground",gx),("first",ux)):
        for item in records:
            if floor in item["floor_scope"] and item["occupancy_role"] in ("VOID","UNALLOCATED"):
                body.append(_polygon(item["polygon"],scale,ox,oy,"url(#hatch)",.55,"#64748b"))
    scope=next(x for x in records if x["space_id"]=="DAYLIGHT-COURT")
    labels=["parking | full vehicle circulation | vehicle entrance", "core / stair / elevator / lobby | common / service", "commercial viable (amber) / nonviable (red)", "units | terraces | VOID/UNALLOCATED hatch | zoning in ownership JSON", f"court: {scope['vertical_extent']} — floors: {', '.join(scope['floor_scope'])}", "swept path omitted from design view; validator-only diagnostic"]
    for i,label in enumerate(labels): body.append(f'<text x="35" y="{545+i*16}" font-size="11" font-family="Arial" fill="#334155">{escape(label)}</text>')
    return ''.join(body)+'</svg>'


def _comparison_svg(shortlist):
    rows=['<svg xmlns="http://www.w3.org/2000/svg" width="980" height="360"><rect width="980" height="360" fill="#fbfcfe"/><text x="24" y="32" font-size="21" font-family="Arial">CLEAN Parcel 2 — decision support comparison (no winner)</text>']
    headers=["Topology","Parking","Commercial rectangle","Residential area","Court placement","Terrace","Hard status"]
    for i,h in enumerate(headers):rows.append(f'<text x="{24+i*135}" y="72" font-size="13" font-family="Arial" font-weight="bold">{escape(h)}</text>')
    for r,c in enumerate(shortlist):
        m=c.get("decision_metrics",{}); values=[c["topology_family"],str(m.get("parking_count",len(c["parking_stalls"]))),f'{m.get("commercial_viability",{}).get("largest_usable_rectangle",0):.1f}',f'{m.get("residential_area",0):.1f}',c.get("daylight_court_placement",{}).get("status","failed"),str(m.get("terrace_satisfaction",all(c["terraces"]))),c["hard_validation_status"]]
        y=110+r*62;rows.append(f'<rect x="18" y="{y-22}" width="940" height="44" fill="{"#eef6f1" if r%2==0 else "#f3f5f8"}"/>')
        for i,v in enumerate(values):rows.append(f'<text x="{24+i*135}" y="{y}" font-size="12" font-family="Arial">{escape(v[:20])}</text>')
    rows.append('</svg>');return ''.join(rows)


def main():
    phase1=IndependentGeneralizationStudyV1().run()
    if not phase1["phase_1_passed"]: raise RuntimeError("Phase 1 failed; Parcel 2 was not started")
    source=sorted((ROOT/"exports"/"DEFAULT").glob("parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json"),key=lambda p:p.stat().st_mtime)[-1]
    contract=json.loads(source.read_text(encoding="utf-8")); site=_local_site(contract["site"]); requirements=_requirements(contract)
    phase2=CleanParcel2ResolveV1().run(site,requirements,True)
    for c in phase2["candidates"]:c["site_polygon"]=site["local_parcel_polygon"]
    review=phase2["shortlist"][:3]
    phase2["diagnostic_shortlist_ids"]=[]
    rules=MinabResidentialArchitecturalRulesV1().resolve()
    report={"contract":"ArchitecturalGeneralizationAndCleanParcel2CheckpointV1","generated_at":datetime.now().isoformat(),
            "architecture_only":True,"phase_1":phase1,"phase_2":phase2,"minab_rule_contract":rules,
            "source_contract":str(source),"old_candidate_geometry_read_as_seed":False,"human_review_gate":True,
            "final_selection_performed":False,"room_layout_generated":False,"final_windows_generated":False,
            "structure_executed":False,"bim_executed":False,"ifc_executed":False,"render_executed":False}
    out=ROOT/"exports"/"DEFAULT"/("architectural_generalization_clean_parcel2_v1_"+datetime.now().strftime("%Y%m%d_%H%M%S"));out.mkdir(parents=True)
    (out/"ARCHITECTURAL_GENERALIZATION_AND_CLEAN_PARCEL2_V1.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    for c in review:(out/f'PARCEL2_{c["topology_family"]}_PAIRED.svg').write_text(_candidate_svg(c,f'Parcel 2 {c["topology_family"]} — decision support only'),encoding="utf-8")
    if review:(out/"PARCEL2_COMPARISON.svg").write_text(_comparison_svg(review),encoding="utf-8")
    print(json.dumps({"output":str(out),"phase_1_passed":True,"shortlist_ids":phase2["shortlist_ids"],"diagnostic_shortlist_ids":phase2["diagnostic_shortlist_ids"],"all_rejected":phase2["all_rejected"]},ensure_ascii=False))


if __name__=="__main__":main()
