"""Comparison of forward leg2=0 evidence and reverse-solved operational END."""
import json
from datetime import datetime
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.far_end_operational_turn_v2 import FarEndOperationalTurnV2
from tools.generate_parcel2_basement_v2_design import View,text,svg_to_png


def main():
    source=sorted((ROOT/"exports"/"DEFAULT").glob("parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json"))[-1]
    base=json.loads(source.read_text());base["requirements"]["ramp"]["minimum_inner_turn_radius"]=5.
    result=FarEndOperationalTurnV2().resolve(base["site"]["parcel"],base["site"]["frontage"],
        base["physical_basement_wall"],base["requirements"],{"status":"required","slope":.15})
    previous=sorted(source.parent.glob("centerline_topology_v2_*/PARCEL2_15_CENTERLINE_TOPOLOGY_V2.json"))[-1]
    old=json.loads(previous.read_text());old_far=max((c for c in old["candidates"] if c["classification"]=="far_end_perimeter_turn"),
        key=lambda c:("turn_outside_clear_envelope" not in c["failure_reasons"],c["topology"]["turn_angle_degrees"],-c["topology"]["leg_2_length"]))
    folder=source.parent/("far_end_operational_turn_v2_"+datetime.now().strftime("%Y%m%d_%H%M%S"));folder.mkdir()
    result["frozen_forward_leg2_zero_candidate"]=old_far;result["source_contract"]=str(source)
    (folder/"PARCEL2_FAR_END_OPERATIONAL_TURN_V2.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    helper=BasementRampParkingDesignReasonerV2();frame=helper._frame(base["site"]["parcel"],base["site"]["frontage"])
    parcel=helper._to_local_polygon(base["site"]["parcel"],frame);inner=helper._to_local_polygon(base["physical_basement_wall"]["inner_face"],frame)
    def best(size):
        cs=[c for c in result["candidates"] if c["maneuvering_field"]["dimensions"][0]==size]
        return min(cs,key=lambda c:(c["operational_end"]["geometry_status"]!="resolved",c["topology"]["z_profile"]["geometry_status"]!="resolved",len(c["failure_reasons"]),"R5_curve_outside_envelope" in c["failure_reasons"],-c["terminal_leg"]["length"])) if cs else None
    panels=[("CURRENT FAILED FAR-END / LEG2=0",old_far),("REVERSE-SOLVED 5×5",best(5.0)),("REVERSE-SOLVED 4.5×4.5",best(4.5))]
    W,H=1900,1120;out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="#faf9f5"/>',
        text(45,44,"REAL PARCEL 2 — FAR-END OPERATIONAL TURN V2",28,"bold"),text(45,75,"MANEUVER FIELD → END INTERFACE → TERMINAL LEG → R5 CURVE → NORTH START",17,"bold")]
    view=View(list(parcel.exterior.coords)[:-1])
    for i,(title,c) in enumerate(panels):
        x=30+i*625;y=100;out.append(f'<rect x="{x}" y="{y}" width="600" height="955" fill="#fff" stroke="#9aa8b2" stroke-width="2"/>')
        out.append(f'<svg x="{x+18}" y="{y+55}" width="565" height="650" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet">')
        out.append(f'<polygon points="{view.points(list(parcel.exterior.coords)[:-1])}" fill="#f5f6f4" stroke="#24353e" stroke-width="5"/>')
        out.append(f'<polygon points="{view.points(list(inner.exterior.coords)[:-1])}" fill="none" stroke="#71838c" stroke-width="3" stroke-dasharray="13 8"/>')
        if c:
            is_old="terminal_leg" not in c
            surface=c["surface"]["complete_union_surface"] if is_old else c["surface"]["complete_union_surface"]
            t=c["topology"];out.append(f'<polygon points="{view.points(surface)}" fill="#efb7c1" stroke="#a71732" stroke-width="4"/>')
            out.append(f'<polyline points="{view.points(t["centerline"])}" fill="none" stroke="#0564ad" stroke-width="5" stroke-dasharray="14 8"/>')
            field=None if is_old else c["maneuvering_field"]["polygon"]
            if field:out.append(f'<polygon points="{view.points(field)}" fill="#bfe0c6" fill-opacity=".7" stroke="#28763d" stroke-width="4"/>')
            movement=None if is_old else c.get("vehicle_movement")
            if movement and movement.get("semantic_centerline"):
                out.append(f'<polyline points="{view.points(movement["semantic_centerline"])}" fill="none" stroke="#066bc1" stroke-width="5" stroke-dasharray="14 8"/>')
            sx,sy=view.p(t["start_point"]);ex,ey=view.p(t["end_point"])
            out += [f'<circle cx="{sx}" cy="{sy}" r="10" fill="#075fa8"/>',text(sx+12,sy-10,"START NORTH +0.00",13,"bold"),
                f'<circle cx="{ex}" cy="{ey}" r="10" fill="#ae1732"/>',text(ex+12,ey+18,"END -2.40",13,"bold")]
        out.append('</svg>');out.append(text(x+18,y+35,title,19,"bold","#a6152f"))
        if c and "terminal_leg" in c:
            t=c["topology"];e=c["operational_end"];w=c["width_transition"];lines=[f"Status: {c['geometry_status']}",
                f"Entry/straight {w['entry_width']:.2f}m → curve {w['curve_width']:.2f}m",f"Leg1 {t['leg_1_length']:.3f} | arc {t['centerline_arc_length']:.3f} | leg2 {t['leg_2_length']:.3f}m",
                f"Total {t['effective_total_run']:.3f}m | max slope {t['z_profile']['maximum_local_slope']:.0%}",f"END interface {e['interface_length']:.3f} / required {e['required_connection_width']:.3f}m",
                f"Ramp/END: {c['ramp_operational_end_status']} | Parking capacity {c['parking_capacity']}","Failures:"]+c["failure_reasons"]
        elif c:
            t=c["topology"];lines=["Status: FAILED (FROZEN)",f"Leg1 {t['leg_1_length']:.3f} | arc {t['centerline_arc_length']:.3f} | leg2 {t['leg_2_length']:.3f}m","END placed at tangent-out","Maneuvering unresolved"]
        else:lines=["NO REVERSE-SOLVED CANDIDATE ASSEMBLED"]
        for j,line in enumerate(lines):out.append(text(x+18,y+750+j*27,line,13,"bold" if j==0 else "normal"))
    out += [text(45,1085,f"FIRST UNRESOLVED STAGE: {result['first_failure_stage']} | candidates {len(result['candidates'])} | complete hard-valid {len(result['hard_valid_candidates'])} | NO PHYSICAL RAMP | HUMAN REVIEW PENDING",15,"bold","#a6152f"),'</svg>']
    svg=folder/"PARCEL2_FAR_END_OPERATIONAL_TURN_V2_COMPARISON.svg";svg.write_text(''.join(out),encoding='utf-8')
    png=folder/"PARCEL2_FAR_END_OPERATIONAL_TURN_V2_COMPARISON.png";svg_to_png(svg,png)
    print(json.dumps({"folder":str(folder),"image":str(png),"status":result["status"],"candidates":len(result["candidates"]),"hard_valid":len(result["hard_valid_candidates"]),"first_failure":result["first_failure_stage"]}))


if __name__=="__main__":main()
