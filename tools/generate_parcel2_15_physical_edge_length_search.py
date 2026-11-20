"""Compare old short curved ramp with edge-length-driven search results."""
import json,sys
from datetime import datetime
from pathlib import Path
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.far_end_operational_turn_v2 import FarEndOperationalTurnV2
from tools.generate_parcel2_basement_v2_design import View,text,svg_to_png


def main():
    source=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1]
    base=json.loads(source.read_text());base['requirements']['ramp']['minimum_inner_turn_radius']=5.
    search=FarEndOperationalTurnV2().resolve(base['site']['parcel'],base['site']['frontage'],base['physical_basement_wall'],base['requirements'],{'status':'required','slope':.15})
    candidates=search['candidates'];old=max((c for c in candidates if c['candidate_id'].startswith('OP-4.5-west-54.4')),key=lambda c:c['physical_path_length_contract']['centerline_length'])
    length_valid=[c for c in candidates if c['physical_path_length_contract']['geometry_status']=='resolved']
    first=min(length_valid,key=lambda c:c['physical_path_length_contract']['path_length_margin']) if length_valid else None
    downstream=[c for c in length_valid if c['ramp_operational_end_status']=='hard_valid']
    best=max(downstream,key=lambda c:(c['topology']['leg_1_length'],c['physical_path_length_contract']['path_length_margin'])) if downstream else None
    closest=max(candidates,key=lambda c:c['physical_path_length_contract']['shortest_physical_path'])
    records=[record('1 — OLD SHORT 15% CURVED CANDIDATE',old,True),record('2 — FIRST NEW SHORTEST EDGE >= 16m',first,False),record('3 — BEST FAR-END + MANEUVER',best,False)]
    q=closest['physical_path_length_contract']
    contract={'contract':'Parcel2FifteenPercentPhysicalEdgeLengthSearchV1','source_contract':str(source),
        'authoritative_rule':'min(L_left,L_center,L_right) >= abs(delta_z)/maximum_grade',
        'required_minimum_path':16.0,'candidates_generated':len(candidates),'physical_path_length_valid_candidates':len(length_valid),
        'downstream_valid_candidates':len(downstream),'records':records,
        'first_geometric_contradiction':{'status':'shortest_physical_path_below_required_run','best_candidate_id':closest['candidate_id'],
            'maximum_achieved_shortest_path':q['shortest_physical_path'],'required':q['required_minimum_path'],'shortfall':-q['path_length_margin'],
            'centerline_length':q['centerline_length'],'left_edge_length':q['left_edge_length'],'right_edge_length':q['right_edge_length']},
        'parking_search_status':'not_run_upstream_ramp_invalid','physical_ramp_published':False,'human_visual_acceptance':'pending'}
    folder=source.parent/('physical_edge_length_search_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir()
    jp=folder/'PARCEL2_15_PHYSICAL_EDGE_LENGTH_SEARCH.json';jp.write_text(json.dumps(contract,indent=2),encoding='utf-8')
    helper=BasementRampParkingDesignReasonerV2();frame=helper._frame(base['site']['parcel'],base['site']['frontage']);inner=helper._to_local_polygon(base['physical_basement_wall']['inner_face'],frame)
    sp=folder/'PARCEL2_15_PHYSICAL_EDGE_LENGTH_SEARCH.svg';pp=folder/'PARCEL2_15_PHYSICAL_EDGE_LENGTH_SEARCH.png';sp.write_text(render(records,inner,contract['first_geometric_contradiction']),encoding='utf-8');svg_to_png(sp,pp)
    print(json.dumps({'folder':str(folder),'png':str(pp),'json':str(jp),'generated':len(candidates),'length_valid':len(length_valid),'closest_shortest_path':q['shortest_physical_path']}))


def record(label,candidate,diagnostic):
    if candidate is None:return {'label':label,'status':'not_generated'}
    q=candidate['physical_path_length_contract'];s=q['stationed_xy_evidence'];t=candidate['topology']
    return {'label':label,'status':'diagnostic_rejected' if diagnostic else ('hard_valid' if candidate['geometry_status']=='hard_valid' else 'rejected'),
        'candidate_id':candidate['candidate_id'],'start':t['start_point'],'tangent_in':t['tangent_in'],'tangent_out':t['tangent_out'],
        'end':t['end_point'],'end_edge':t['operational_end_edge'],'leg_1_length':t['leg_1_length'],'terminal_leg_length':t['leg_2_length'],
        'R_inner':t['R_inner'],'ramp_surface':candidate['surface']['complete_union_surface'],'left_path':s['left_edge_xy'],
        'centerline_path':s['centerline_xy'],'right_path':s['right_edge_xy'],'left_length':q['left_edge_length'],
        'centerline_length':q['centerline_length'],'right_length':q['right_edge_length'],'shortest_path':q['shortest_physical_path'],
        'path_length_margin':q['path_length_margin'],'left_average_grade':q['left_average_grade'],'centerline_average_grade':q['centerline_average_grade'],
        'right_average_grade':q['right_average_grade'],'end_z':[-2.4,-2.4,-2.4],
        'maneuvering_field':candidate['maneuvering_field']['polygon'] if q['geometry_status']=='resolved' and candidate['ramp_operational_end_status']=='hard_valid' else [],
        'parking_search_status':candidate['parking_search_status'],'failure_reasons':candidate['failure_reasons']}


def render(records,inner,contradiction):
    view=View(list(inner.exterior.coords)[:-1]);W,H=2040,1260
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="#f7f6f1"/>',text(42,46,'REAL PARCEL 2 — 15% PHYSICAL EDGE LENGTH SEARCH',28,'bold'),text(42,76,'HARD GATE: min(L-left, L-center, L-right) >= 16.00m',17,'bold')]
    for i,r in enumerate(records):
        x=25+i*675;y=100;out.append(f'<rect x="{x}" y="{y}" width="650" height="1085" rx="8" fill="white" stroke="#879aa5" stroke-width="2"/>');out.append(text(x+18,y+35,r['label'],18,'bold'))
        if r['status']=='not_generated':
            out.append(text(x+325,y+480,'NOT GENERATED',28,'bold','#b01630','middle'));out.append(text(x+325,y+525,'No candidate satisfied shortest physical path >= 16.00m',15,'bold','#b01630','middle'));continue
        out.append(f'<svg x="{x+18}" y="{y+50}" width="614" height="690" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet">')
        out.append(f'<polygon points="{view.points(list(inner.exterior.coords)[:-1])}" fill="#edf1ef" stroke="#263a43" stroke-width="6"/>')
        out.append(f'<polygon points="{view.points(r["ramp_surface"])}" fill="#efb3bf" fill-opacity=".65" stroke="#a61734" stroke-width="3"/>')
        for key,color in [('left_path','#b01630'),('centerline_path','#075fa8'),('right_path','#25833b')]:out.append(f'<polyline points="{view.points(r[key])}" fill="none" stroke="{color}" stroke-width="6" stroke-dasharray="15 8"/>')
        out.append(f'<polyline points="{view.points(r["end_edge"])}" fill="none" stroke="#71142a" stroke-width="10"/>')
        for label,key in [('T-IN','tangent_in'),('T-OUT','tangent_out')]:
            px,py=view.p(r[key]);out.append(f'<circle cx="{px}" cy="{py}" r="9" fill="#8b5c00"/>');out.append(text(px+10,py-7,label,13,'bold','#8b5c00'))
        out.append('</svg>')
        lines=[f"Candidate: {r['candidate_id']}",f"Leg1 / terminal: {r['leg_1_length']:.3f} / {r['terminal_leg_length']:.3f}m",f"L-left: {r['left_length']:.3f}m | grade {100*r['left_average_grade']:.2f}%",f"L-center: {r['centerline_length']:.3f}m | grade {100*r['centerline_average_grade']:.2f}%",f"L-right: {r['right_length']:.3f}m | grade {100*r['right_average_grade']:.2f}%",f"Shortest: {r['shortest_path']:.3f}m | margin {r['path_length_margin']:.3f}m",f"END Z: {r['end_z'][0]:.2f} / {r['end_z'][1]:.2f} / {r['end_z'][2]:.2f}",f"Maneuver: {'generated' if r['maneuvering_field'] else 'NOT GENERATED'}",f"Parking: {r['parking_search_status']}",f"STATUS: {r['status']}"]
        for j,line in enumerate(lines):out.append(text(x+18,y+775+j*27,line,14,'bold' if ('STATUS' in line or 'Shortest' in line) else 'normal','#b01630' if ('NOT GENERATED' in line or 'rejected' in line or 'Shortest' in line) else '#20272c'))
    out.append(text(42,1215,f"FIRST CONTRADICTION: best shortest path {contradiction['maximum_achieved_shortest_path']:.3f}m < 16.000m (shortfall {contradiction['shortfall']:.3f}m)",16,'bold','#b01630'))
    out.append(text(42,1243,'NO FINAL PHYSICAL RAMP PUBLISHED | HUMAN VISUAL ACCEPTANCE PENDING',15,'bold'));out.append('</svg>');return ''.join(out)


if __name__=='__main__':main()
