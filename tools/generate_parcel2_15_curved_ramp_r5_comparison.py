"""Human-review comparison for the approved Straight-15 topology change."""
import json
from datetime import datetime
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.curved_ramp_vehicle_movement_reasoner_v1 import CurvedRampVehicleMovementReasonerV1
from tools.generate_parcel2_basement_v2_design import View, text, svg_to_png


def main():
    proofs=sorted((ROOT/"exports"/"DEFAULT").glob("parcel2_basement_v2_*/straight_15_maneuvering_proof_*/PARCEL2_15_PERCENT_MANEUVERING_PROOF.json"))
    proof=json.loads(proofs[-1].read_text(encoding="utf-8"));base=json.loads(Path(proof["source_contract"]).read_text(encoding="utf-8"))
    requirements=base["requirements"];requirements["ramp"].update({"minimum_inner_turn_radius":5.0,
        "minimum_inner_turn_radius_source":"user_project_requirement","minimum_inner_turn_radius_evidence_status":"authoritative_for_current_test"})
    result=CurvedRampVehicleMovementReasonerV1().resolve(base["site"]["parcel"],base["site"]["frontage"],
        base["physical_basement_wall"],requirements,{"inventory_status":"complete_empty"},proof["topology_change_request"])
    result["straight_rejection_proof"]=proof
    folder=Path(proof["source_contract"]).parent/("curved_r5_comparison_"+datetime.now().strftime("%Y%m%d_%H%M%S"));folder.mkdir()
    (folder/"PARCEL2_15_CURVED_RAMP_R5_COMPARISON.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    def best(side):
        subset=[c for c in result["candidates"] if c["topology"]=="perimeter_curved_turn" and c["side"]==side]
        return min(subset,key=lambda c:(c["geometry_status"]!="hard_valid",len(c["failure_reasons"]),
            "turn_outside_clear_envelope" in c["failure_reasons"],c["central_field_intrusion_area"],-c["largest_contiguous_remaining_free_field"],c["candidate_id"]))
    left,right=best("left"),best("right")
    distinct_dog=[c for c in result["candidates"] if c["topology"]=="curved_dog_leg" and "second_tangent_arc_not_geometrically_resolved" not in c["failure_reasons"]]
    panels=[("REJECTED STRAIGHT 15%",None),("BEST LEFT PERIMETER CURVE",left),("BEST RIGHT PERIMETER CURVE",right)]
    W,H=1900,1200;inner=base["physical_basement_wall"]["inner_face"]
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="#fbfaf6"/>',
        text(55,48,"REAL PARCEL 2 — 15% CURVED RAMP R5 SEARCH",29,"bold"),
        text(55,82,"Rinner ≥ 5.00m | Rcenterline ≥ 6.75m | Router ≥ 8.50m | effective run = 16.00m",17,"bold")]
    for panel,(title,candidate) in enumerate(panels):
        x=35+panel*625;y=110;out.append(f'<rect x="{x}" y="{y}" width="600" height="1010" fill="#fff" stroke="#abb4bb" stroke-width="2"/>')
        geometry=proof["maneuvering_field"]["polygon"] if candidate is None else candidate["ramp_surface"]
        view=View(inner+geometry);out.append(f'<svg x="{x+15}" y="{y+60}" width="570" height="650" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet">')
        out.append(f'<polygon points="{view.points(inner)}" fill="#edf2f4" stroke="#263640" stroke-width="4"/>')
        if candidate is None:
            old=next(c for c in base["design"]["candidates"] if c["candidate_id"]==proof["candidate_id"])
            out.append(f'<polygon points="{view.points(old["ramp"]["polygon"])}" fill="#efb9c1" stroke="#aa1730" stroke-width="4"/>')
            out.append(f'<polygon points="{view.points(proof["maneuvering_field"]["polygon"])}" fill="#bfddc7" stroke="#26713b" stroke-width="3"/>')
            details=["REJECTED — POINT CONTACT","Interface 0.000m | bottleneck 0.000m","Parking capacity 0"]
        else:
            out.append(f'<polygon points="{view.points(candidate["ramp_surface"])}" fill="#efb9c1" stroke="#aa1730" stroke-width="4"/>')
            out.append(f'<polygon points="{view.points(candidate["transition_polygon"])}" fill="#e49a3a" stroke="#884d00" stroke-width="4"/>')
            out.append(f'<polyline points="{view.points(candidate["centerline_arc"])}" fill="none" stroke="#711526" stroke-width="3" stroke-dasharray="10 6"/>')
            for trial in candidate["maneuvering_trials"]: out.append(f'<polygon points="{view.points(trial["polygon"])}" fill="#bfddc7" stroke="#26713b" stroke-width="3"/>')
            movement=candidate.get("vehicle_movement_path") or {};spine=movement.get("vehicle_main_spine",[])
            if spine: out.append(f'<polyline points="{view.points(spine)}" fill="none" stroke="#145ea8" stroke-width="4" stroke-dasharray="12 7"/>')
            sx,sy=view.p(candidate["start"]);ex,ey=view.p(candidate["end"])
            out += [f'<circle cx="{sx}" cy="{sy}" r="10" fill="#12639e"/>',text(sx+14,sy-12,"START +0.00",15,"bold"),f'<circle cx="{ex}" cy="{ey}" r="10" fill="#aa1730"/>',text(ex+14,ey+22,"END -2.40",15,"bold")]
            details=[candidate["geometry_status"].upper(),f"Rin 5.00 | Rc 6.75 | Rout 8.50m",f"Angle {candidate['turn_angle_degrees']:.1f}° | arc {candidate['centerline_arc_length']:.3f}m",f"Legs {candidate['leg_1_length']:.3f} + {candidate['leg_2_length']:.3f}m",f"Total effective run {candidate['effective_run']:.3f}m",f"Central intrusion {candidate['central_field_intrusion_area']:.3f}m²",f"Largest free field {candidate['largest_contiguous_remaining_free_field']:.3f}m²",f"Parking capacity {candidate['parking_capacity']}","Failures:"]+candidate["failure_reasons"]
        out.append('</svg>');out.append(text(x+18,y+38,title,20,"bold"))
        for n,line in enumerate(details): out.append(text(x+18,y+750+n*29,line,13,"bold" if n==0 else "normal","#a81626" if n==0 else "#20252b"))
    out += [text(55,1160,f"{result['status']} | searched {len(result['candidates'])} | hard-valid {len(result['hard_valid_candidates'])} | distinct dog-leg {len(distinct_dog)} | NO PHYSICAL RAMP PUBLISHED | HUMAN REVIEW PENDING",15,"bold"),'</svg>']
    svg=folder/"PARCEL2_15_CURVED_RAMP_R5_COMPARISON.svg";svg.write_text("".join(out),encoding="utf-8")
    output=folder/"PARCEL2_15_CURVED_RAMP_R5_COMPARISON.png";svg_to_png(svg,output)
    print(json.dumps({"output":str(folder),"image":str(output),"status":result["status"],"searched":len(result["candidates"]),"hard_valid":len(result["hard_valid_candidates"]),"left":left["candidate_id"],"right":right["candidate_id"],"distinct_dog_leg":len(distinct_dog)},ensure_ascii=False))


if __name__=="__main__": main()
