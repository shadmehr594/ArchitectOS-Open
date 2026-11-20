"""Render the independent edge-controlled V3 search."""
import json,sys
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.edge_controlled_curved_ramp_topology_v3 import EdgeControlledCurvedRampTopologyV3
from tools.generate_parcel2_basement_v2_design import View,text,svg_to_png


def main():
    source=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1]
    base=json.loads(source.read_text());base['requirements']['ramp']['minimum_inner_turn_radius']=5.
    result=EdgeControlledCurvedRampTopologyV3().resolve(base['site']['parcel'],base['site']['frontage'],base['physical_basement_wall'],base['requirements'],{'status':'required','slope':.15})
    old_source=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/physical_edge_length_search_*/PARCEL2_15_PHYSICAL_EDGE_LENGTH_SEARCH.json'))[-1]
    old=json.loads(old_source.read_text())['records'][0]
    valid=[c for c in result['candidates'] if c['candidate_id'] in result['length_valid_candidates']]
    first=min(valid,key=lambda c:c['physical_path_length']['path_length_margin']) if valid else None
    operational=[c for c in result['candidates'] if c['candidate_id'] in result['operational_candidates']]
    meaningful_terminal=[c for c in operational if c['topology']['leg_2_length']>=.5-1e-7]
    best=max(meaningful_terminal,key=lambda c:(c['topology']['leg_1_length'],c['topology']['leg_2_length'])) if meaningful_terminal else (max(operational,key=lambda c:c['topology']['leg_2_length']) if operational else max(valid,key=lambda c:c['topology']['leg_1_length']) if valid else None)
    best_label='C — BEST FAR-END OPERATIONAL' if operational else 'C — MAXIMUM FAR-END GEOMETRY (NOT OPERATIONAL)'
    records=[old_record(old),new_record('B — FIRST EDGE-CONTROLLED LENGTH-VALID',first),new_record(best_label,best)]
    contract={'contract':'Parcel2EdgeControlledTopologyV3Comparison','new_search':result,'comparison_records':records,
        'old_candidates_reused':False,'parking_search_status':'not_run_upstream_ramp_invalid','physical_ramp_published':False,'human_visual_acceptance':'pending'}
    folder=source.parent/('edge_controlled_v3_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir()
    jp=folder/'PARCEL2_15_EDGE_CONTROLLED_TOPOLOGY_V3.json';jp.write_text(json.dumps(contract,indent=2),encoding='utf-8')
    helper=BasementRampParkingDesignReasonerV2();frame=helper._frame(base['site']['parcel'],base['site']['frontage']);inner=helper._to_local_polygon(base['physical_basement_wall']['inner_face'],frame)
    sp=folder/'PARCEL2_15_EDGE_CONTROLLED_TOPOLOGY_V3.svg';pp=folder/'PARCEL2_15_EDGE_CONTROLLED_TOPOLOGY_V3.png';sp.write_text(render(records,inner,result['geometric_maximum'],len(operational)),encoding='utf-8');svg_to_png(sp,pp)
    print(json.dumps({'folder':str(folder),'png':str(pp),'json':str(jp),'new_candidates':len(result['candidates']),'length_valid':len(valid),'operational':len(operational),'old_candidates_reused':False}))


def old_record(r):
    return {'label':'A — OLD GENERATOR / CENTERLINE TARGET ERROR','status':'diagnostic_rejected','candidate_id':r['candidate_id'],
        'ramp_surface':r['ramp_surface'],'left_path':r['left_path'],'centerline_path':r['centerline_path'],'right_path':r['right_path'],
        'leg1':r['leg_1_length'],'leg2':r['terminal_leg_length'],
        'left':r['left_length'],'center':r['centerline_length'],'right':r['right_length'],'shortest':r['shortest_path'],
        'margin':r['path_length_margin'],'maneuver':r['maneuvering_field'],'end_edge':r['end_edge'],'failure':'shortest_physical_path_below_required_run'}


def new_record(label,c):
    if c is None:return {'label':label,'status':'not_generated'}
    q=c['physical_path_length'];t=c['topology'];s=q['stationed_xy_evidence']
    return {'label':label,'status':c['geometry_status'],'candidate_id':c['candidate_id'],'ramp_surface':c['surface'],
        'left_path':s['left_edge_xy'],'centerline_path':s['centerline_xy'],'right_path':s['right_edge_xy'],
        'leg1':t['leg_1_length'],'leg2':t['leg_2_length'],'inner_arc':t['R_inner']*abs(t['turn_angle']),
        'center_arc':t['centerline_arc_length'],'outer_arc':t['R_outer']*abs(t['turn_angle']),
        'left':q['left_edge_length'],'center':q['centerline_length'],'right':q['right_edge_length'],'shortest':q['shortest_physical_path'],
        'margin':q['path_length_margin'],'maneuver':c['maneuvering_field'],'end_edge':t['end_edge'],
        'end_interface':0 if c['operational_end'] is None else c['operational_end']['interface_length'],
        'failure':', '.join(c['failure_reasons']) if c['failure_reasons'] else 'none'}


def render(records,inner,maximum,operational_count):
    view=View(list(inner.exterior.coords)[:-1]);W,H=2040,1270
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="#f7f6f1"/>',text(42,46,'REAL PARCEL 2 — 15% EDGE-CONTROLLED TOPOLOGY V3',28,'bold'),text(42,76,'NEW XY GENERATOR — OLD 198 CANDIDATES REUSED: FALSE',17,'bold')]
    for i,r in enumerate(records):
        x=25+i*675;y=100;out.append(f'<rect x="{x}" y="{y}" width="650" height="1100" rx="8" fill="white" stroke="#879aa5" stroke-width="2"/>');out.append(text(x+18,y+35,r['label'],18,'bold'))
        if r['status']=='not_generated':out.append(text(x+325,y+500,'NOT GENERATED',27,'bold','#b01630','middle'));continue
        out.append(f'<svg x="{x+18}" y="{y+50}" width="614" height="700" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet">')
        out.append(f'<polygon points="{view.points(list(inner.exterior.coords)[:-1])}" fill="#edf1ef" stroke="#263a43" stroke-width="6"/>')
        out.append(f'<polygon points="{view.points(r["ramp_surface"])}" fill="#efb3bf" fill-opacity=".55" stroke="#a61734" stroke-width="3"/>')
        for key,color in [('left_path','#b01630'),('centerline_path','#075fa8'),('right_path','#25833b')]:out.append(f'<polyline points="{view.points(r[key])}" fill="none" stroke="{color}" stroke-width="6" stroke-dasharray="15 8"/>')
        if r['maneuver']:out.append(f'<polygon points="{view.points(r["maneuver"])}" fill="#a9dfbd" fill-opacity=".7" stroke="#19733b" stroke-width="6"/>')
        out.append(f'<polyline points="{view.points(r["end_edge"])}" fill="none" stroke="#71142a" stroke-width="10"/>');out.append('</svg>')
        lines=[f"Candidate: {r['candidate_id']}",f"Leg1: {r['leg1']:.3f}m | Leg2: {r['leg2']:.3f}m",f"L-left / center / right: {r['left']:.3f} / {r['center']:.3f} / {r['right']:.3f}m",f"Shortest: {r['shortest']:.3f}m | margin {r['margin']:.3f}m"]
        if 'inner_arc' in r:lines += [f"Arc inner / center / outer: {r['inner_arc']:.3f} / {r['center_arc']:.3f} / {r['outer_arc']:.3f}m",f"END interface: {r['end_interface']:.3f}m"]
        lines += [f"Maneuver: {'generated' if r['maneuver'] else 'NOT GENERATED'}",f"Failure: {r['failure']}",f"STATUS: {r['status']}"]
        for j,line in enumerate(lines):out.append(text(x+18,y+785+j*29,line,14,'bold' if ('Shortest' in line or 'STATUS' in line) else 'normal','#b01630' if ('NOT GENERATED' in line or 'Failure' in line or 'diagnostic' in line) else '#20272c'))
    out.append(text(42,1230,f"GEOMETRIC MAXIMUM: leg1 {maximum['maximum_leg1']:.3f}m + inner arc {maximum['inner_arc_length']:.3f}m + leg2 {maximum['maximum_terminal_leg']:.3f}m; shortest path {maximum['maximum_shortest_physical_path']:.3f}m",15,'bold'))
    footer=(f'{operational_count} OPERATIONAL RAMP + END + MANEUVER CANDIDATES | PARKING NOT RUN BY SCOPE | HUMAN ACCEPTANCE PENDING'
        if operational_count else 'NO OPERATIONAL END FIELD: TRANSVERSE CLEAR BOUNDARY IS LIMITING | HUMAN ACCEPTANCE PENDING')
    out.append(text(42,1257,footer,14,'bold','#155b2c' if operational_count else '#b01630'));out.append('</svg>');return ''.join(out)


if __name__=='__main__':main()
