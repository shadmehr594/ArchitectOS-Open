"""Evaluate an approved 15% topology-change request and render its evidence."""
import json
from datetime import datetime
from pathlib import Path
import sys

from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from tools.generate_parcel2_basement_v2_design import View, text, svg_to_png


def main():
    proofs=sorted((ROOT/"exports"/"DEFAULT").glob("parcel2_basement_v2_*/straight_15_maneuvering_proof_*/PARCEL2_15_PERCENT_MANEUVERING_PROOF.json"))
    proof=json.loads(proofs[-1].read_text(encoding="utf-8"));request=proof["topology_change_request"]
    source=Path(proof["source_contract"]);base=json.loads(source.read_text(encoding="utf-8"))
    evaluator=BasementRampParkingDesignReasonerV2()
    result=evaluator.resolve_topology_change_request(base["site"]["parcel"],base["site"]["frontage"],
        base["physical_basement_wall"],base["requirements"],
        {"inventory_status":base["site"]["fixed_obstacle_inventory"]},request)
    result["straight_rejection_proof"]=proof
    folder=source.parent/("piecewise_15_comparison_"+datetime.now().strftime("%Y%m%d_%H%M%S"));folder.mkdir()
    (folder/"PARCEL2_15_PERCENT_PIECEWISE_RAMP_COMPARISON.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    candidates=result["candidates"]
    def best(family):
        subset=[c for c in candidates if c["topology"]==family]
        return min(subset,key=lambda c:(len(c["failure_reasons"]),c["central_field_intrusion_area"],-c["largest_contiguous_remaining_field"],c["candidate_id"]),default=None)
    selections=[("REJECTED STRAIGHT 15%",None),("BEST PERIMETER-TURN",best("perimeter_turn")),("BEST DOG-LEG",best("dog_leg"))]
    W,H=1900,1200;out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="#fbfaf6"/>',
        text(55,52,"PARCEL 2 — 15% PIECEWISE RAMP COMPARISON",30,"bold"),
        text(55,88,"Generated only from APPROVED RampTopologyChangeRequestV1 — no physical ramp published",17,"bold")]
    inner=base["physical_basement_wall"]["inner_face"]
    for panel,(title,candidate) in enumerate(selections):
        x=45+panel*620;y=125
        geometry=proof["maneuvering_field"]["polygon"]+proof["ramp_end"]["edge"] if candidate is None else candidate["ramp_polygon"]
        view=View(inner+geometry);out.append(f'<rect x="{x}" y="{y}" width="590" height="970" fill="#fff" stroke="#aab2b8" stroke-width="2"/>')
        out.append(f'<svg x="{x+12}" y="{y+65}" width="566" height="570" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet">')
        out.append(f'<polygon points="{view.points(inner)}" fill="#eef2f4" stroke="#263640" stroke-width="3"/>')
        if candidate is None:
            old=next(c for c in base["design"]["candidates"] if c["candidate_id"]==proof["candidate_id"])
            out.append(f'<polygon points="{view.points(old["ramp"]["polygon"])}" fill="#efc9cf" stroke="#a81626" stroke-width="3"/>')
            out.append(f'<polygon points="{view.points(proof["maneuvering_field"]["polygon"])}" fill="#c9decf" stroke="#28733d" stroke-width="3"/>')
            status="REJECTED — POINT CONTACT";details=["Run 16.000m", "Interface 0.000m", "Bottleneck 0.000m", "Stalls independently usable: 0"]
        else:
            out.append(f'<polygon points="{view.points(candidate["ramp_polygon"])}" fill="#efc9cf" stroke="#a81626" stroke-width="3"/>')
            turn=candidate["turn_geometry"].get("transition_polygon",[])
            if turn: out.append(f'<polygon points="{view.points(turn)}" fill="#d88936" stroke="#804600" stroke-width="4"/>')
            trial=candidate.get("best_maneuvering") or (candidate["maneuvering_trials"][0] if candidate["maneuvering_trials"] else None)
            if trial:
                out.append(f'<polygon points="{view.points(trial["polygon"])}" fill="#c9decf" stroke="#28733d" stroke-width="3"/>')
                for stall in trial.get("parking_stalls",[]): out.append(f'<polygon points="{view.points(stall)}" fill="#87909a" stroke="#313941" stroke-width="2"/>')
            status=candidate["geometry_status"].replace("_"," ").upper()
            details=[f"Legs {candidate['leg_1_run']:.3f} + {candidate['transition_effective_run']:.3f} + {candidate['leg_2_run']:.3f}",
                f"Total run {candidate['total_effective_run']:.3f}m",f"Central intrusion {candidate['central_field_intrusion_area']:.3f}m²",
                f"Largest free field {candidate['largest_contiguous_remaining_field']:.3f}m²",
                f"Failures: {', '.join(candidate['failure_reasons']) or 'none'}"]
        out.append('</svg>');out.append(text(x+22,y+42,title,21,"bold"));out.append(text(x+22,y+675,status,17,"bold","#a81626" if "REJECT" in status or "NOT FEASIBLE" in status else "#28733d"))
        detail_lines=[]
        for line in details:
            if line.startswith("Failures:"):
                reasons=line[len("Failures:"):].strip().split(", ")
                detail_lines.append("Failures:");detail_lines.extend(["• "+reason for reason in reasons])
            else: detail_lines.append(line)
        for n,line in enumerate(detail_lines): out.append(text(x+22,y+720+n*31,line,13,"bold" if n==0 else "normal"))
    out += [text(55,1145,f"Evaluation status: {result['status']} | hard-valid candidates: {len(result['hard_valid_candidates'])} | human visual acceptance: PENDING",17,"bold"),'</svg>']
    svg=folder/"PARCEL2_15_PERCENT_PIECEWISE_RAMP_COMPARISON.svg";svg.write_text("".join(out),encoding="utf-8")
    png=folder/"PARCEL2_15_PERCENT_PIECEWISE_RAMP_COMPARISON.png";svg_to_png(svg,png)
    print(json.dumps({"output":str(folder),"status":result["status"],"generated":len(candidates),
        "perimeter_turn":sum(c["topology"]=="perimeter_turn" for c in candidates),
        "dog_leg":sum(c["topology"]=="dog_leg" for c in candidates),
        "hard_valid":len(result["hard_valid_candidates"]),"first_boundary":result.get("first_proven_boundary")},ensure_ascii=False))


if __name__=="__main__": main()
