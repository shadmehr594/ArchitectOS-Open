import json,sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.maneuver_field_first_reverse_solve_v1 import ManeuverFieldFirstReverseSolveV1
from tools.generate_parcel2_basement_v2_design import View,text,svg_to_png

def main():
    source=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1]
    data=json.loads(source.read_text());h=BasementRampParkingDesignReasonerV2();frame=h._frame(data['site']['parcel'],data['site']['frontage']);inner=h._to_local_polygon(data['physical_basement_wall']['inner_face'],frame)
    search=ManeuverFieldFirstReverseSolveV1().resolve(inner);valid=[c for c in search['candidates'] if c['geometry_status']=='ramp_operational']
    first5=next((c for c in valid if c['maneuvering_dimensions']==[5.,5.]),None);best=max(valid,key=lambda c:c['remaining_free_area']) if valid else None
    limiting=min((c for c in search['candidates'] if c.get('terminal_leg_length',-999)<=0),key=lambda c:abs(c.get('terminal_leg_length',-999)),default=None)
    prev=json.loads(sorted(source.parent.glob('terminal_end_maneuver_fix_*/PARCEL2_15_TERMINAL_END_MANEUVER_FIX.json'))[-1].read_text())['comparison_records'][1]
    records=[{'label':'A — PREVIOUS POSTPROCESSING FAILURE','status':'invalid','ramp':prev['ramp'],'field':prev['field'],'end':prev['end'],'failure':prev['failure']},rec('B — FIRST REVERSE-SOLVED VALID 5x5',first5),rec('C — BEST REVERSE-SOLVED / LIMIT',best or limiting)]
    contract={'contract':'Parcel2ManeuverFirstReverseSolveComparison','maneuver_field_first':True,'old_terminal_postprocessing_reused':False,'v3_terminal_geometry_frozen_as_input':False,'field_edge_trials':len(search['field_edge_trials']),'reverse_candidates':len(search['candidates']),'hard_valid_candidates':len(valid),'status':search['status'],'first_geometric_contradiction':search['first_geometric_contradiction'],'comparison_records':records,'parking_search_status':'not_run_terminal_arrival_validation','physical_ramp_published':False,'human_visual_acceptance':'pending'}
    folder=source.parent/('maneuver_first_reverse_solve_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir();jp=folder/'PARCEL2_15_MANEUVER_FIRST_REVERSE_SOLVE.json';sp=folder/'PARCEL2_15_MANEUVER_FIRST_REVERSE_SOLVE.svg';pp=folder/'PARCEL2_15_MANEUVER_FIRST_REVERSE_SOLVE.png'
    jp.write_text(json.dumps(contract,indent=2),encoding='utf-8');sp.write_text(render(records,inner,contract),encoding='utf-8');svg_to_png(sp,pp)
    print(json.dumps({'folder':str(folder),'png':str(pp),'json':str(jp),'field_edge_trials':len(search['field_edge_trials']),'reverse_candidates':len(search['candidates']),'hard_valid':len(valid),'status':search['status']}))

def rec(label,c):
    if c is None:return {'label':label,'status':'not_generated'}
    if c.get('geometry_status')!='ramp_operational':return {'label':label,'status':'limiting_geometry','field':c.get('maneuvering_field',[]),'end':[],'candidate_id':c['candidate_id'],'terminal_leg':c.get('terminal_leg_length'),'failure':', '.join(c['failure_reasons'])}
    t=c['topology'];return {'label':label,'status':'ramp_operational','candidate_id':c['candidate_id'],'ramp':c['ramp_surface'],'centerline':t['centerline'],'field':c['maneuvering_field'],'end':c['end_edge'],'movement':c['vehicle_movement_path'],'leg1':t['leg_1_length'],'terminal_leg':t['leg_2_length'],'rinner':t['R_inner'],'rcenter':t['R_centerline'],'router':t['R_outer'],'interface':c['end_interface_width'],'overlap':c['ramp_maneuver_overlap_area'],'end_z':[c['end_left_z'],c['end_center_z'],c['end_right_z']],'failure':'none'}

def render(records,inner,contract):
    view=View(list(inner.exterior.coords)[:-1]);out=['<svg xmlns="http://www.w3.org/2000/svg" width="2040" height="1260"><rect width="100%" height="100%" fill="#f7f6f1"/>',text(40,44,'REAL PARCEL 2 — 15% MANEUVER-FIELD-FIRST REVERSE SOLVE',27,'bold'),text(40,74,'FIELD → END → TERMINAL LEG → R5 CURVE → NORTH START',17,'bold')]
    for i,r in enumerate(records):
        x=24+i*674;y=98;out += [f'<rect x="{x}" y="{y}" width="650" height="1090" rx="8" fill="white" stroke="#8497a2" stroke-width="2"/>',text(x+18,y+34,r['label'],17,'bold')]
        if r['status']=='not_generated':out += [text(x+325,y+490,'NOT GENERATED',28,'bold','#b01630','middle'),text(x+325,y+530,'No reverse-solved operational candidate',15,'normal','#b01630','middle')];continue
        out.append(f'<svg x="{x+18}" y="{y+55}" width="614" height="690" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet"><polygon points="{view.points(list(inner.exterior.coords)[:-1])}" fill="#edf1ef" stroke="#263a43" stroke-width="6"/>')
        if r.get('ramp'):out.append(f'<polygon points="{view.points(r["ramp"])}" fill="#efb3bf" fill-opacity=".65" stroke="#a61734" stroke-width="4"/>')
        if r.get('field'):out.append(f'<polygon points="{view.points(r["field"])}" fill="#9fd9ad" fill-opacity=".65" stroke="#176f37" stroke-width="6"/>')
        if r.get('centerline'):out.append(f'<polyline points="{view.points(r["centerline"])}" fill="none" stroke="#0865af" stroke-width="7" stroke-dasharray="16 9"/>')
        if r.get('end'):out.append(f'<polyline points="{view.points(r["end"])}" fill="none" stroke="#541128" stroke-width="12"/>')
        out.append('</svg>');lines=[f"Candidate: {r.get('candidate_id','previous diagnostic')}",f"Status: {r['status']}"]
        if r['status']=='ramp_operational':lines += [f"Leg1 / terminal: {r['leg1']:.3f} / {r['terminal_leg']:.3f} m",f"R inner / center / outer: {r['rinner']:.2f} / {r['rcenter']:.2f} / {r['router']:.2f} m",f"END interface: {r['interface']:.3f} m",f"END L/C/R Z: {r['end_z'][0]:.2f} / {r['end_z'][1]:.2f} / {r['end_z'][2]:.2f}",f"Ramp/field overlap: {r['overlap']:.3f} m²"]
        elif r.get('terminal_leg') is not None:lines += [f"Solved terminal leg: {r['terminal_leg']:.3f} m"]
        lines += [f"Failure: {r.get('failure','none')}"]
        for j,line in enumerate(lines):out.append(text(x+18,y+785+j*31,line,14,'bold' if ('Status' in line or 'Failure' in line) else 'normal','#b01630' if r['status']!='ramp_operational' and ('Status' in line or 'Failure' in line) else '#20272c'))
    e=contract['first_geometric_contradiction'];out += [text(40,1225,f"FIELD EDGES/SENSES TESTED: {contract['field_edge_trials']} | REVERSE CANDIDATES: {contract['reverse_candidates']} | HARD VALID: {contract['hard_valid_candidates']}",15,'bold'),text(40,1252,f"FIRST CONTRADICTION: {', '.join(e['failure_reasons'])} | R_outer={e['required_outer_radius']:.2f}m | clear width={e['available_transverse_clear_width']:.3f}m | HUMAN ACCEPTANCE PENDING",14,'bold','#b01630'),'</svg>'];return ''.join(out)

if __name__=='__main__':main()
