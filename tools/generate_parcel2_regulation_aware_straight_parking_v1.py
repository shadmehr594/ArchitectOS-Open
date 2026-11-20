import json
import sys
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.ramp_architecture_selection_v1 import RampArchitectureSelectionV1
from core.architecture.reasoning.straight_ramp_parking_branch_v1 import StraightRampParkingBranchV1
from tools.generate_parcel2_basement_v2_design import View,text,svg_to_png

BASELINE_AREA=61.722
BASELINE_ID='TC-M4.5-X0-Y1-east-left_right-A30-B30-T6.647'

def main():
    source=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1]
    data=json.loads(source.read_text());helper=BasementRampParkingDesignReasonerV2();frame=helper._frame(data['site']['parcel'],data['site']['frontage']);inner=helper._to_local_polygon(data['physical_basement_wall']['inner_face'],frame)
    branch=StraightRampParkingBranchV1().resolve(inner,2,{'parking_use':'small_private_covered_parking','project_allows_17_percent':True,'authority':'active_project_regulation_contract'})
    ranker=RampArchitectureSelectionV1();selected=ranker.select(branch['candidates']);baseline=ranker.freeze_two_curve_baseline(BASELINE_ID,BASELINE_AREA)
    baseline_source=sorted(source.parent.glob('two_curve_ramp_v1_*/PARCEL2_15_TWO_CURVE_RAMP_TOPOLOGY_V1.json'))[-1]
    old=json.loads(baseline_source.read_text());old_geom=old['best_central_field_evidence']
    baseline['production_geometry']=old_geom
    complete=selected is not None
    contract={'contract':'Parcel2RegulationAwareStraightRampParkingComparisonV1','source_contract':str(source),'parking_class':'small','regulation_context':branch['slope_policy']['regulation_context'],'slope_policy':branch['slope_policy'],'two_curve_baseline':baseline,'straight_candidates':branch['candidates'],'selected_candidate':selected,
      'selected_candidate_id':selected['candidate_id'] if selected else None,'selected_slope':selected['slope'] if selected else None,'architecture_selection_reason':'complete_layout_preserves_more_contiguous_basement_with_required_parking' if complete else 'first_real_contradiction_reported','comparison_to_two_curve_baseline_m2':selected['largest_contiguous_usable_field']-BASELINE_AREA if complete else None,'physical_ramp_publication_status':'pending_human_acceptance','human_visual_acceptance':'pending'}
    records=[baseline_record(baseline),candidate_record('B — BEST REGULATION-VALID STRAIGHT + PARKING',selected),candidate_record('C — COMPLETE SELECTED BASEMENT PLAN',selected)]
    folder=source.parent/('regulation_aware_straight_parking_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir()
    jp=folder/'PARCEL2_REGULATION_AWARE_STRAIGHT_RAMP_PARKING.json';sp=folder/'PARCEL2_REGULATION_AWARE_STRAIGHT_RAMP_PARKING.svg';pp=folder/'PARCEL2_REGULATION_AWARE_STRAIGHT_RAMP_PARKING.png'
    jp.write_text(json.dumps(contract,indent=2),encoding='utf-8');sp.write_text(render(records,inner,contract),encoding='utf-8');svg_to_png(sp,pp)
    print(json.dumps({'json':str(jp),'png':str(pp),'selected':contract['selected_candidate_id'],'slope':contract['selected_slope']}))

def baseline_record(b):
    g=b['production_geometry'];t=g['topology']
    return {'label':'A — APPROVED 15% TWO-CURVE BASELINE','status':b['architecture_selection_status'],'surface':t['surface'],'maneuver':g['maneuvering_field'],'center':t['centerline'],'arrival':t['arrival_edge'],'parking':[],'paths':[],'area':b['remaining_contiguous_usable_field'],'detail':'GEOMETRY HARD VALID / NOT PREFERRED: CENTRAL FRAGMENTATION'}

def candidate_record(label,c):
    if c is None:return {'label':label,'status':'NOT GENERATED'}
    return {'label':label,'status':'architecture_selected','surface':c['ramp_surface'],'maneuver':c['maneuvering_field'],'center':[[p[0],p[1]] for p in c['center_path']],'arrival':c['arrival_edge'],'parking':c['parking_stalls'],'paths':c['vehicle_paths'],'area':c['largest_contiguous_usable_field'],'candidate':c,'detail':'COMPLETE RAMP + MANEUVER + 2 INDEPENDENT STALLS + RETURN'}

def render(records,inner,contract):
    view=View(list(inner.exterior.coords)[:-1]);out=['<svg xmlns="http://www.w3.org/2000/svg" width="2040" height="1260"><rect width="100%" height="100%" fill="#f7f6f1"/>',text(40,43,'REAL PARCEL 2 — REGULATION-AWARE RAMP + PARKING',27,'bold'),text(40,73,'COMPLETE ARCHITECTURAL SOLUTION RANKING — TWO-CURVE BASELINE VS STRAIGHT BRANCH',15,'bold')]
    for i,r in enumerate(records):
        x=24+i*674;y=98;out += [f'<rect x="{x}" y="{y}" width="650" height="1090" rx="8" fill="white" stroke="#8497a2" stroke-width="2"/>',text(x+18,y+34,r['label'],17,'bold')]
        if r['status']=='NOT GENERATED':out.append(text(x+325,y+520,'NOT GENERATED',27,'bold','#b01630','middle'));continue
        out.append(f'<svg x="{x+18}" y="{y+55}" width="614" height="720" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet"><defs><marker id="a{i}" markerWidth="12" markerHeight="12" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#0865af"/></marker></defs><polygon points="{view.points(list(inner.exterior.coords)[:-1])}" fill="#edf1ef" stroke="#263a43" stroke-width="6"/>')
        out.append(f'<polygon points="{view.points(r["surface"])}" fill="#efb3bf" fill-opacity=".72" stroke="#a61734" stroke-width="4"/>')
        out.append(f'<polygon points="{view.points(r["maneuver"])}" fill="#9fd9ad" fill-opacity=".58" stroke="#176f37" stroke-width="6"/>')
        for n,p in enumerate(r['parking']):out.append(f'<polygon points="{view.points(p)}" fill="#d8e3ee" stroke="#304c67" stroke-width="5"/><text x="{view.p(p[0])[0]}" y="{view.p(p[0])[1]}" font-size="25">P-{n+1:02d}</text>')
        out.append(f'<polyline points="{view.points(r["center"])}" fill="none" stroke="#0865af" stroke-width="6" stroke-dasharray="15 10" marker-end="url(#a{i})"/>')
        for path in r['paths']:
            out.append(f'<polyline points="{view.points(path["entry_path"])}" fill="none" stroke="#0865af" stroke-width="4" stroke-dasharray="12 9" marker-end="url(#a{i})"/>')
        out.append(f'<polyline points="{view.points(r["arrival"])}" fill="none" stroke="#541128" stroke-width="12"/></svg>')
        lines=[r['detail'],f"Remaining contiguous field: {r['area']:.3f} m²"]
        c=r.get('candidate')
        if c:lines += [f"Candidate: {c['candidate_id']}",f"Slope: {c['slope']*100:.0f}% | run L/C/R: {c['L_left']:.3f} m",f"Transitions: {c['segments'][0]['length']:.1f}m @{c['segments'][0]['grade']*100:.1f}% / main / {c['segments'][2]['length']:.1f}m @{c['segments'][2]['grade']*100:.1f}%",f"Drop: {c['achieved_vertical_drop']:.3f}m | footprint: {c['ramp_footprint_area']:.3f}m²",f"Maneuver: 4.5×4.5m | overlap {c['ramp_maneuver_overlap_area']:.3f}m²",f"Parking: {c['parking_stall_count']}/{c['required_stall_count']} | return: {c['vehicle_return_status']}"]
        for j,line in enumerate(lines):out.append(text(x+18,y+815+j*28,line,13,'bold' if j==0 else 'normal','#155b2c' if j==0 else '#20272c'))
    sel=contract['selected_candidate'];delta=contract['comparison_to_two_curve_baseline_m2']
    out += [text(40,1225,f"SELECTED: {contract['selected_candidate_id']} | SLOPE {sel['slope']*100:.0f}% | CONTIGUOUS FIELD IMPROVEMENT {delta:+.3f} m²",15,'bold','#155b2c'),text(40,1252,'PHYSICAL RAMP PUBLICATION: PENDING HUMAN ACCEPTANCE | HUMAN VISUAL ACCEPTANCE: PENDING',14,'bold'),'</svg>'];return ''.join(out)

if __name__=='__main__':main()
