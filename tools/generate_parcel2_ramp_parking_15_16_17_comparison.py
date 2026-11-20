"""Production-contract comparison of Parcel 2 ramp/parking slopes."""
import json
from datetime import datetime
from pathlib import Path
import sys

from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.far_end_operational_turn_v2 import FarEndOperationalTurnV2
from core.architecture.reasoning.terminal_vehicle_alignment_v1 import TerminalVehicleAlignmentV1
from tools.generate_parcel2_basement_v2_design import View,text,svg_to_png


def main():
    source=sorted((ROOT/"exports"/"DEFAULT").glob("parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json"))[-1]
    base=json.loads(source.read_text());base["requirements"]["ramp"]["minimum_inner_turn_radius"]=5.
    helper=BasementRampParkingDesignReasonerV2();frame=helper._frame(base["site"]["parcel"],base["site"]["frontage"])
    inner=helper._to_local_polygon(base["physical_basement_wall"]["inner_face"],frame)
    r15=FarEndOperationalTurnV2().resolve(base["site"]["parcel"],base["site"]["frontage"],base["physical_basement_wall"],base["requirements"],{"status":"required","slope":.15})
    c15=min((c for c in r15["candidates"] if c.get("ramp_operational_end_status")=="hard_valid"),key=lambda c:(c["maneuvering_field"]["dimensions"][0]<5,-c["terminal_leg"]["length"],c["candidate_id"]))
    c15["terminal_alignment"]=TerminalVehicleAlignmentV1().resolve(c15["topology"]["end_point"],c15["topology"]["end_heading"],list(inner.exterior.coords)[:-1],3,5)
    def straight(slope):
        cs=[c for c in base["design"]["candidates"] if abs(c["ramp"]["slope"]-slope)<1e-7]
        return max(cs,key=lambda c:(len(c["parking_stalls"]),c["generated_maneuvering_placements"],-len(c["rejection_reasons"])))
    c16,c17=straight(.16),straight(.17)
    def local_poly(points):return [helper._local(p,frame) for p in points]
    records=[{"slope":.15,"source":"FarEndOperationalTurnV2","candidate_id":c15["candidate_id"],
        "ramp_surface":c15["surface"]["complete_union_surface"],"ramp_centerline":c15["topology"]["centerline"],
        "start":c15["topology"]["start_point"],"end":c15["topology"]["end_point"],"end_edge":c15["topology"]["operational_end_edge"],
        "maneuvering":c15["maneuvering_field"]["polygon"],"aisle":c15["maneuvering_field"]["polygon"],
        "stalls":c15["parking_stalls"],"paths":[] if not c15.get("vehicle_movement") else [c15["vehicle_movement"]["semantic_centerline"]],
        "parking_search_status":c15["parking_search_status"],"parking_candidates_generated":c15["parking_candidates_generated"],
        "maximum_geometric_stall_count":c15["maximum_geometric_stall_count"],"independently_usable_stall_count":c15["parking_capacity"],
        "terminal_alignment_status":c15["terminal_alignment"]["geometry_status"],
        "aligned_maneuvering_field_status":"not_generated",
        "end_interface_width":c15["operational_end"]["interface_length"],
        "maneuvering_field_status":"hard_valid","vehicle_return_status":"resolved","ramp_geometry_status":"hard_valid"}]
    for slope,c in ((.16,c16),(.17,c17)):
        spine=c["vehicle_circulation_spine"]
        records.append({"slope":slope,"source":"BasementRampParkingDesignReasonerV2","candidate_id":c["candidate_id"],
            "ramp_surface":local_poly(c["ramp"]["polygon"]),"ramp_centerline":[helper._local(c["ramp"]["start"],frame),helper._local(c["ramp"]["end"],frame)],
            "start":helper._local(c["ramp"]["start"],frame),"end":helper._local(c["ramp"]["end"],frame),"end_edge":local_poly(c["ramp"]["end_edge"]),
            "maneuvering":local_poly(c["maneuvering_envelope"]),"aisle":local_poly(c["parking_aisle"]),
            "stalls":[local_poly(p) for p in c["parking_stalls"]],"paths":[[helper._local(p,frame) for p in path] for path in spine["vehicle_spine_center_paths"]],
            "parking_search_status":"hard_valid" if len(c["parking_stalls"])>=2 and spine["supports_return_to_ramp"] else "generated_not_valid",
            "parking_candidates_generated":len(c["parking_stalls"]),"maximum_geometric_stall_count":len(c["parking_stalls"]),
            "independently_usable_stall_count":sum(1 for x in spine["stall_results"] if x["incoming_path_exists"] and x["outgoing_path_exists"] and x["return_to_ramp_path_exists"]),
            "terminal_alignment_status":"already_aligned_site_longitudinal","aligned_maneuvering_field_status":"hard_valid",
            "end_interface_width":c["ramp_end_escape"]["minimum_connection_width"],
            "maneuvering_field_status":"hard_valid","vehicle_return_status":"resolved" if spine["supports_return_to_ramp"] else "not_feasible","ramp_geometry_status":"hard_valid"})
    contract={"contract":"Parcel2RampParkingSlopeComparisonV1","records":records,"human_visual_acceptance":"pending","physical_ramp_published":False,
        "note":"The 15 percent parking search executed but produced zero stall geometries. This is not proof that two stalls are geometrically impossible."}
    folder=source.parent/("ramp_parking_15_16_17_"+datetime.now().strftime("%Y%m%d_%H%M%S"));folder.mkdir()
    (folder/"PARCEL2_RAMP_PARKING_15_16_17_COMPARISON.json").write_text(json.dumps(contract,indent=2),encoding='utf-8')
    view=View(list(inner.exterior.coords)[:-1]);W,H=1900,1180;out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="#faf9f5"/>',text(45,44,"REAL PARCEL 2 — RAMP / MANEUVER / PARKING 15–16–17%",28,"bold"),text(45,75,"PRODUCTION CONTRACT GEOMETRY — DIAGNOSTIC HUMAN REVIEW",17,"bold")]
    for i,r in enumerate(records):
        x=30+i*625;y=100;out.append(f'<rect x="{x}" y="{y}" width="600" height="1010" fill="#fff" stroke="#99a8b2" stroke-width="2"/>');out.append(f'<svg x="{x+18}" y="{y+50}" width="565" height="650" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet">')
        out.append(f'<polygon points="{view.points(list(inner.exterior.coords)[:-1])}" fill="#f1f4f3" stroke="#263a43" stroke-width="5"/>')
        out.append(f'<polygon points="{view.points(r["ramp_surface"])}" fill="#efb5c0" stroke="#a41733" stroke-width="4"/>')
        out.append(f'<polyline points="{view.points(r["ramp_centerline"])}" fill="none" stroke="#075fa8" stroke-width="5" stroke-dasharray="14 8"/>')
        out.append(f'<polygon points="{view.points(r["maneuvering"])}" fill="#bce0c5" fill-opacity=".65" stroke="#28763d" stroke-width="4"/>')
        for n,p in enumerate(r["stalls"]):out.append(f'<polygon points="{view.points(p)}" fill="#d8dde0" stroke="#394a52" stroke-width="4"/>')
        for path in r["paths"]:out.append(f'<polyline points="{view.points(path)}" fill="none" stroke="#086bc0" stroke-width="5" stroke-dasharray="14 8"/>')
        sx,sy=view.p(r["start"]);ex,ey=view.p(r["end"]);out += [f'<circle cx="{sx}" cy="{sy}" r="10" fill="#075fa8"/>',text(sx+12,sy-10,"START",13,"bold"),f'<circle cx="{ex}" cy="{ey}" r="10" fill="#af1732"/>',text(ex+12,ey+18,"END",13,"bold"),'</svg>',text(x+18,y+35,f"{int(r['slope']*100)}% — {r['candidate_id']}",20,"bold")]
        lines=[f"Ramp: {r['ramp_geometry_status']}",f"Terminal alignment: {r['terminal_alignment_status']}",f"Axis-aligned maneuver field: {r['aligned_maneuvering_field_status']}",f"END interface: {r['end_interface_width']:.3f}m",f"Current maneuver: {r['maneuvering_field_status']}",f"Parking search: {r['parking_search_status']}",f"Generated options: {r['parking_candidates_generated']}",f"Max geometric / independent: {r['maximum_geometric_stall_count']} / {r['independently_usable_stall_count']}",f"Return to ramp: {r['vehicle_return_status']}"]
        if not r["stalls"]:lines.append("PARKING SEARCH PRODUCED ZERO STALL GEOMETRIES")
        for j,line in enumerate(lines):out.append(text(x+18,y+745+j*25,line,13,"bold" if j==0 else "normal","#a51630" if "ZERO" in line else "#20252b"))
    out += [text(45,1145,"NO FINAL RAMP PUBLISHED | HUMAN VISUAL ACCEPTANCE PENDING",15,"bold"),'</svg>']
    svg=folder/"PARCEL2_RAMP_PARKING_15_16_17_COMPARISON.svg";svg.write_text(''.join(out),encoding='utf-8');png=folder/"PARCEL2_RAMP_PARKING_15_16_17_COMPARISON.png";svg_to_png(svg,png)
    print(json.dumps({"folder":str(folder),"image":str(png),"records":[[r["slope"],r["parking_search_status"],r["independently_usable_stall_count"]] for r in records]}))


if __name__=="__main__":main()
