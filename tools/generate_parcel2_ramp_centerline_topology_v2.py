"""Human evidence for centerline-first Ramp V2; never invokes V1."""
import json
from datetime import datetime
from math import pi
from pathlib import Path
import sys

from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.ramp_centerline_topology_v2 import Parcel2RampCenterlineSearchV2
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from tools.generate_parcel2_basement_v2_design import View,text,svg_to_png


def main():
    source=sorted((ROOT/"exports"/"DEFAULT").glob("parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json"))[-1]
    base=json.loads(source.read_text(encoding="utf-8"));base["requirements"]["ramp"]["minimum_inner_turn_radius"]=5.0
    request={"contract":"RampTopologyChangeRequestV1","status":"required","slope":.15,
             "frozen_straight_15_rejection":True}
    result=Parcel2RampCenterlineSearchV2().resolve(base["site"]["parcel"],base["site"]["frontage"],
        base["physical_basement_wall"],base["requirements"],request)
    result["source_contract"]=str(source);result["v1_search_status"]="frozen_diagnostic_inadequate_search_space"
    folder=source.parent/("centerline_topology_v2_"+datetime.now().strftime("%Y%m%d_%H%M%S"));folder.mkdir()
    (folder/"PARCEL2_15_CENTERLINE_TOPOLOGY_V2.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    helper=BasementRampParkingDesignReasonerV2();frame=helper._frame(base["site"]["parcel"],base["site"]["frontage"])
    parcel=helper._to_local_polygon(base["site"]["parcel"],frame);inner=helper._to_local_polygon(base["physical_basement_wall"]["inner_face"],frame)
    def score(c):return ("turn_outside_clear_envelope" in c["failure_reasons"],c["topology"]["z_profile"]["geometry_status"]!="resolved",len(c["failure_reasons"]),-c["topology"]["turn_angle_degrees"],c["central_field_intrusion_area"])
    def representative(kind):return min((c for c in result["candidates"] if c["classification"]==kind),key=score)
    early,mid,far=(representative(k) for k in ("early_turn","midfield_turn","far_end_perimeter_turn"))
    panels=[("FROZEN STRAIGHT 15%",None),("EARLY TURN — FAILED",early),("MIDFIELD TURN — FAILED",mid),("FAR-END TURN — FAILED",far)]
    W,H=2000,1180;out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="#faf9f5"/>',
        text(45,45,"REAL PARCEL 2 — CENTERLINE-FIRST RAMP TOPOLOGY V2",28,"bold"),
        text(45,76,"NORTH ACCESS → PERIMETER CENTERLINE → TANGENT R5 CURVE → OPERATIONAL END",17,"bold")]
    for i,(title,c) in enumerate(panels):
        x=25+i*493;y=105;out.append(f'<rect x="{x}" y="{y}" width="475" height="990" fill="#fff" stroke="#9aa8b2" stroke-width="2"/>')
        view=View(list(parcel.exterior.coords)[:-1]);out.append(f'<svg x="{x+15}" y="{y+55}" width="445" height="680" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet">')
        out.append(f'<polygon points="{view.points(list(parcel.exterior.coords)[:-1])}" fill="#f4f6f6" stroke="#1f303a" stroke-width="5"/>')
        out.append(f'<polygon points="{view.points(list(inner.exterior.coords)[:-1])}" fill="none" stroke="#667b86" stroke-width="3" stroke-dasharray="14 8"/>')
        if c:
            t,s=c["topology"],c["surface"]
            out.append(f'<polygon points="{view.points(s["complete_union_surface"])}" fill="#efb8c2" stroke="#a21835" stroke-width="4"/>')
            out.append(f'<polyline points="{view.points(t["centerline"])}" fill="none" stroke="#075fa8" stroke-width="5" stroke-dasharray="14 8"/>')
            out.append(f'<polyline points="{view.points(s["inner_arc"])}" fill="none" stroke="#721526" stroke-width="3"/>')
            out.append(f'<polyline points="{view.points(s["outer_arc"])}" fill="none" stroke="#721526" stroke-width="3"/>')
            sx,sy=view.p(t["start_point"]);ex,ey=view.p(t["end_point"]);ti=view.p(t["tangent_in"]);to=view.p(t["tangent_out"])
            out += [f'<circle cx="{sx}" cy="{sy}" r="10" fill="#075fa8"/>',text(sx+12,sy-12,"START +0.00",14,"bold"),
                f'<circle cx="{ti[0]}" cy="{ti[1]}" r="7" fill="#e18719"/>',text(ti[0]+8,ti[1],"T-IN",12,"bold"),
                f'<circle cx="{to[0]}" cy="{to[1]}" r="7" fill="#e18719"/>',text(to[0]+8,to[1],"T-OUT",12,"bold"),
                f'<circle cx="{ex}" cy="{ey}" r="10" fill="#b3142f"/>',text(ex+12,ey+18,"END -2.40",14,"bold")]
            for m in c["maneuvering_trials"]:
                out.append(f'<polygon points="{view.points(m["polygon"])}" fill="none" stroke="#ba2636" stroke-width="2" stroke-dasharray="8 6"/>')
        out.append('</svg>');out.append(text(x+18,y+36,title,20,"bold","#9d1429" if c else "#333"))
        if c:
            t=c["topology"];z=t["z_profile"];lines=[f"Classification: {c['classification']}",f"Progress {c['far_end_progress_ratio']:.0%} | Turn {t['turn_angle_degrees']:.0f}°",
                f"Rin 5.00 | Rc 6.75 | Rout 8.50m",
                f"Leg1 {t['leg_1_length']:.3f} + arc {t['centerline_arc_length']:.3f} + leg2 {t['leg_2_length']:.3f}",
                f"Total {t['stationing']['S3']:.3f}m ({'valid ≥16' if t['stationing']['S3']>=16-1e-7 else 'INVALID <16'})",f"Slopes {z['segment_slopes']['leg_1']:.3f} / {z['segment_slopes']['curve']:.3f} / {z['segment_slopes']['leg_2']:.3f}",
                f"Z T-IN {z['z_at_tangent_in']:.2f} | T-OUT {z['z_at_tangent_out']:.2f} | END {z['end_z']:.2f}",
                "END interface: NOT RESOLVED","Parking: NOT GENERATED", "Failures:"]+c["failure_reasons"]
        else: lines=["Approved proof remains frozen","Failure: point-contact / disconnected 5×5","RampTopologyChangeRequestV1 = required","V1 curved search = diagnostic-only"]
        for j,line in enumerate(lines):out.append(text(x+18,y+770+j*27,line,13,"bold" if j==0 else "normal"))
    q=result["first_geometric_contradiction"]
    out += [text(45,1125,f"FIRST CURRENT BOUNDARY: {q['statement']}",14,"bold","#a3162d"),
        text(45,1153,f"{result['status']} | V2 candidates {len(result['candidates'])} | hard-valid {len(result['hard_valid_candidates'])} | NO PHYSICAL RAMP | HUMAN REVIEW PENDING",14,"bold"),'</svg>']
    svg=folder/"PARCEL2_15_CENTERLINE_TOPOLOGY_V2_DIAGNOSTIC.svg";svg.write_text(''.join(out),encoding='utf-8')
    png=folder/"PARCEL2_15_CENTERLINE_TOPOLOGY_V2_DIAGNOSTIC.png";svg_to_png(svg,png)
    print(json.dumps({"folder":str(folder),"image":str(png),"status":result["status"],"candidates":len(result["candidates"]),"hard_valid":len(result["hard_valid_candidates"])}))


if __name__=="__main__":main()
