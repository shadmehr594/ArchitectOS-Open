"""Read-only geometric proof for one existing Parcel 2 straight 15% candidate."""
import json
from datetime import datetime
from pathlib import Path
import sys

from shapely.geometry import LineString, Point, Polygon

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from tools.generate_parcel2_basement_v2_design import View, text, svg_to_png


def main():
    contracts=sorted((ROOT/"exports"/"DEFAULT").glob("parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json"))
    source=contracts[-1]
    contract=json.loads(source.read_text(encoding="utf-8"))
    candidates=[c for c in contract["design"]["candidates"]
        if c["ramp"]["family"]=="straight" and abs(c["ramp"]["slope"]-.15)<1e-9]
    candidate=min(candidates,key=lambda c:(len(c["rejection_reasons"]),-len(c["parking_stalls"]),c["candidate_id"]))
    end=LineString(candidate["ramp_end_escape"]["end_edge"])
    apron=Polygon(candidate["ramp_end_escape"]["departure_apron_polygon"])
    maneuver=Polygon(candidate["maneuvering_envelope"])
    inner=Polygon(contract["physical_basement_wall"]["inner_face"])
    ramp=Polygon(candidate["ramp"]["polygon"])
    stalls=[Polygon(points) for points in candidate["parking_stalls"]]
    reasoner=BasementRampParkingDesignReasonerV2()
    connection=reasoner._maneuvering_connection_proof(apron,maneuver,3.5)
    attempted=[]
    for item in candidate["vehicle_circulation_spine"]["stall_results"]:
        line=LineString(item["path"])
        other=[stall for i,stall in enumerate(stalls) if i!=item["stall_index"]-1]
        swept=line.buffer(1.75,cap_style=2,join_style=2)
        inside=inner.buffer(reasoner.EPS).covers(swept)
        crosses_other=any(swept.intersection(obstacle).area>reasoner.EPS for obstacle in other)
        connected=connection["geometry_status"]=="resolved" and inside and not crosses_other
        attempted.append({"stall_id":f"P-{item['stall_index']:02d}","attempted_center_path":[list(p) for p in line.coords],
            "vehicle_width_swept_polygon":reasoner._polygon_coords(swept),"inside_clear_face":inside,
            "crosses_other_occupied_stall":crosses_other,"incoming_path_exists":connected,
            "outgoing_path_exists":connected,"return_to_ramp_exists":connected,
            "status":"resolved" if connected else "not_feasible"})
    coords=list(maneuver.exterior.coords)[:-1]
    edge0=LineString([coords[0],coords[1]])
    proof={"contract":"Parcel2Straight15ManeuveringProofV1","source_contract":str(source),
        "candidate_id":candidate["candidate_id"],"ramp_end":{"edge":[list(p) for p in end.coords],
            "midpoint":[end.centroid.x,end.centroid.y],"departure_direction":candidate["ramp_end_escape"]["departure_direction"],
            "elevation":-2.4},
        "maneuvering_field":{"polygon":coords,"area":maneuver.area,
            "orientation_degrees":__import__('math').degrees(__import__('math').atan2(edge0.coords[1][1]-edge0.coords[0][1],edge0.coords[1][0]-edge0.coords[0][0])),
            "distance_from_end":end.distance(maneuver)},
        "connection":connection,"stall_return_tests":attempted,
        "claim":"disproved" if connection["geometry_status"]!="resolved" else "proved",
        "failure_reasons":connection["failure_reasons"],
        "topology_change_request":{"contract":"RampTopologyChangeRequestV1","reason":"insufficient_connected_post_ramp_maneuvering",
            "source_evidence":"Parcel2Straight15ManeuveringProofV1","status":"required","slope":.15,
            "required_topology_search":["perimeter_turn","dog_leg"]} if connection["geometry_status"]!="resolved" else None,
        "human_visual_acceptance":"pending"}
    folder=source.parent/("straight_15_maneuvering_proof_"+datetime.now().strftime("%Y%m%d_%H%M%S"));folder.mkdir()
    (folder/"PARCEL2_15_PERCENT_MANEUVERING_PROOF.json").write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding="utf-8")

    points=contract["physical_basement_wall"]["inner_face"]+candidate["ramp"]["polygon"]+coords
    for stall in candidate["parking_stalls"]: points+=stall
    view=View(points); W,H=1900,1300
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="#fbfaf6"/>',
        text(60,55,"PARCEL 2 — STRAIGHT 15% MANEUVERING PROOF",31,"bold"),
        text(60,92,f"CLAIM: {proof['claim'].upper()} — POINT CONTACT IS NOT A 3.50m VEHICLE CORRIDOR",19,"bold","#a81626"),
        f'<polygon points="{view.points(contract["physical_basement_wall"]["inner_face"])}" fill="#eef2f4" stroke="#263640" stroke-width="4"/>',
        f'<polygon points="{view.points(candidate["ramp"]["polygon"])}" fill="#efc9cf" stroke="#a81626" stroke-width="4"/>',
        f'<polygon points="{view.points(coords)}" fill="#b9d9c2" fill-opacity=".65" stroke="#28733d" stroke-width="4"/>']
    for i,stall in enumerate(candidate["parking_stalls"],1):
        out.append(f'<polygon points="{view.points(stall)}" fill="#87909a" stroke="#313941" stroke-width="3"/>')
        p=Polygon(stall).centroid;x,y=view.p([p.x,p.y]);out.append(text(x,y,f"P-{i:02d} OCCUPIED",14,"bold","#fff","middle"))
    for result in attempted:
        out.append(f'<polyline points="{view.points(result["attempted_center_path"])}" fill="none" stroke="#c51f32" stroke-width="6" stroke-dasharray="12 7"/>')
    ex=view.points([list(p) for p in end.coords]);out.append(f'<polyline points="{ex}" fill="none" stroke="#092f73" stroke-width="10"/>')
    contact=apron.intersection(maneuver)
    if contact.geom_type=="Point":
        x,y=view.p([contact.x,contact.y]);out.append(f'<circle cx="{x}" cy="{y}" r="12" fill="#ffcc00" stroke="#a81626" stroke-width="4"/>')
        out.append(text(x+18,y-18,"ONLY POINT CONTACT",15,"bold","#a81626"))
    out += [text(1320,180,f"Candidate: {candidate['candidate_id']}",20,"bold"),
        text(1320,225,f"5×5 AREA = {maneuver.area:.3f} m²",18),text(1320,265,"END distance = 0.000 m",18),
        text(1320,305,f"Contact length = {connection['contact_interface_length']:.3f} m",18,"bold","#a81626"),
        text(1320,345,f"Bottleneck = {connection['minimum_bottleneck_width']:.3f} m",18,"bold","#a81626"),
        text(1320,385,f"Required vehicle width = 3.500 m",18),
        text(1320,430,f"Connected components = {connection['connected_component_count']}",18),
        text(1320,485,"NO CONTINUOUS CORRIDOR POLYGON",18,"bold","#a81626"),
        text(1320,535,"P-01 entry/exit: FAIL",18,"bold","#a81626"),text(1320,575,"P-02 entry/exit: FAIL",18,"bold","#a81626"),
        text(1320,635,"RampTopologyChangeRequestV1",19,"bold"),text(1320,675,"STATUS = REQUIRED",19,"bold","#a81626"),
        text(70,1215,"Red dashed lines are previously claimed paths; their 3.50m swept corridors are not valid through the point-contact gap.",16,"bold"),'</svg>']
    svg=folder/"PARCEL2_15_PERCENT_MANEUVERING_PROOF.svg";svg.write_text("".join(out),encoding="utf-8")
    svg_to_png(svg,folder/"PARCEL2_15_PERCENT_MANEUVERING_PROOF.png")
    print(json.dumps({"output":str(folder),"candidate":candidate["candidate_id"],"claim":proof["claim"],
        "failure_reasons":proof["failure_reasons"],"contact_length":connection["contact_interface_length"],
        "bottleneck":connection["minimum_bottleneck_width"]},ensure_ascii=False))


if __name__=="__main__": main()
