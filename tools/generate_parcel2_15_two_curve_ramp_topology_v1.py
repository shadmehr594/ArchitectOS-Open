import json
import sys
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.two_curve_ramp_topology_v1 import TwoCurveRampTopologyV1
from tools.generate_parcel2_basement_v2_design import View,text,svg_to_png

def main():
    source=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1]
    data=json.loads(source.read_text());helper=BasementRampParkingDesignReasonerV2()
    frame=helper._frame(data['site']['parcel'],data['site']['frontage'])
    inner=helper._to_local_polygon(data['physical_basement_wall']['inner_face'],frame)
    search=TwoCurveRampTopologyV1().resolve(inner)
    valid=[c for c in search['candidates'] if c['geometry_status']=='ramp_operational']
    first=valid[0] if valid else None
    best=max(valid,key=lambda c:(c['remaining_contiguous_floor_area'],c['maneuvering_size'][0],c['path_length_margin'])) if valid else None
    frozen_path=sorted(source.parent.glob('integrated_ramp_arrival_*/PARCEL2_15_INTEGRATED_RAMP_ARRIVAL.json'))[-1]
    frozen=json.loads(frozen_path.read_text())['comparison_records'][2]
    records=[{'label':'A — FROZEN SINGLE-CURVE FAILURE','status':'frozen','field':frozen.get('field',[]),'failure':frozen.get('failure','frozen')},record('B — FIRST HARD-VALID TWO-CURVE',first),record('C — BEST CENTRAL-FIELD PRESERVATION',best)]
    contract={'contract':'Parcel2TwoCurveRampTopologyV1Diagnostic','new_search_source':'two_curve_joint_reverse_geometry','single_curve_candidates_reused':False,'candidate_count':len(search['candidates']),'hard_valid_candidate_count':len(valid),'hard_valid_candidate_ids':search['hard_valid_candidates'],
        'first_hard_valid_evidence':first,'best_central_field_evidence':best,
        'two_curve_ramp_geometry_status':'hard_valid' if valid else 'not_feasible','ramp_operational_end_status':'hard_valid' if valid else 'not_feasible',
        'physical_ramp_publication_status':'pending_human_acceptance','comparison_records':records,'parking_search_status':'not_run','physical_ramp_published':False,'human_visual_acceptance':'pending'}
    folder=source.parent/('two_curve_ramp_v1_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir()
    jp=folder/'PARCEL2_15_TWO_CURVE_RAMP_TOPOLOGY_V1.json';sp=folder/'PARCEL2_15_TWO_CURVE_RAMP_TOPOLOGY_V1.svg';pp=folder/'PARCEL2_15_TWO_CURVE_RAMP_TOPOLOGY_V1.png'
    jp.write_text(json.dumps(contract,indent=2),encoding='utf-8');sp.write_text(render(records,inner,len(search['candidates']),len(valid)),encoding='utf-8');svg_to_png(sp,pp)
    print(json.dumps({'folder':str(folder),'png':str(pp),'json':str(jp),'candidates':len(search['candidates']),'hard_valid':len(valid)}))

def record(label,c):
    if c is None:return {'label':label,'status':'not_generated'}
    t=c['topology'];return {'label':label,'status':'ramp_operational','candidate_id':c['candidate_id'],'surface':t['surface'],'left':t['left_path'],'center':t['centerline'],'right':t['right_path'],'field':c['maneuvering_field'],'arrival':t['arrival_edge'],'movement':c['vehicle_path'],'leg1':t['leg1_length'],'transition':t['transition_length'],'terminal':t['terminal_tangent_length'],'curve_a':t['curve_A'],'curve_b':t['curve_B'],'L':[c['L_left'],c['L_center'],c['L_right']],'grades':c['max_local_grades'],'interface':c['arrival_interface_width'],'overlap':c['ramp_maneuver_overlap_area'],'remaining':c['remaining_contiguous_floor_area'],'failure':'none'}

def render(records,inner,total,valid_count):
    view=View(list(inner.exterior.coords)[:-1]);out=['<svg xmlns="http://www.w3.org/2000/svg" width="2040" height="1260"><rect width="100%" height="100%" fill="#f7f6f1"/>',text(40,44,'REAL PARCEL 2 — 15% TWO-CURVE / S-RAMP TOPOLOGY V1',27,'bold'),text(40,74,'MANEUVER FIELD → ARRIVAL → CURVE B → TRANSITION → CURVE A → NORTH START',16,'bold')]
    for i,r in enumerate(records):
        x=24+i*674;y=98;out += [f'<rect x="{x}" y="{y}" width="650" height="1090" rx="8" fill="white" stroke="#8497a2" stroke-width="2"/>',text(x+18,y+34,r['label'],17,'bold')]
        if r['status']=='not_generated':out.append(text(x+325,y+500,'NOT GENERATED',28,'bold','#b01630','middle'));continue
        out.append(f'<svg x="{x+18}" y="{y+55}" width="614" height="690" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet"><defs><marker id="arrow{i}" markerWidth="12" markerHeight="12" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#0865af"/></marker></defs><polygon points="{view.points(list(inner.exterior.coords)[:-1])}" fill="#edf1ef" stroke="#263a43" stroke-width="6"/>')
        if r.get('surface'):out.append(f'<polygon points="{view.points(r["surface"])}" fill="#efb3bf" fill-opacity=".65" stroke="#a61734" stroke-width="4"/>')
        if r.get('field'):out.append(f'<polygon points="{view.points(r["field"])}" fill="#9fd9ad" fill-opacity=".62" stroke="#176f37" stroke-width="6"/>')
        for key,color in [('left','#a61734'),('center','#0865af'),('right','#25833b')]:
            if r.get(key):
                marker=f' marker-end="url(#arrow{i})"' if key=='center' else ''
                out.append(f'<polyline points="{view.points(r[key])}" fill="none" stroke="{color}" stroke-width="5" stroke-dasharray="14 9"{marker}/>')
        if r.get('arrival'):out.append(f'<polyline points="{view.points(r["arrival"])}" fill="none" stroke="#541128" stroke-width="12"/>')
        if r.get('center'):
            sx,sy=view.p(r['center'][0]);ex,ey=view.p(r['center'][-1])
            out.append(text(sx+18,sy-18,'START +0.00 / NORTH FRONTAGE',28,'bold','#123b6e'))
            out.append(text(ex+18,ey+35,'ARRIVAL -2.40 / RETURN TO START',28,'bold','#541128'))
        out.append('</svg>');lines=[f"Candidate: {r.get('candidate_id','frozen diagnostic')}",f"Status: {r['status']}"]
        if r['status']=='ramp_operational':lines += [f"Leg1 / transition / terminal: {r['leg1']:.3f} / {r['transition']:.3f} / {r['terminal']:.3f}m",f"Curve A/B: {r['curve_a']['angle_degrees']:.1f}° / {r['curve_b']['angle_degrees']:.1f}°",f"Rinner A/B: {r['curve_a']['R_inner']:.2f} / {r['curve_b']['R_inner']:.2f}m",f"L left/center/right: {r['L'][0]:.3f}/{r['L'][1]:.3f}/{r['L'][2]:.3f}m",f"Max grades L/C/R: {r['grades']['left']*100:.2f}/{r['grades']['center']*100:.2f}/{r['grades']['right']*100:.2f}%",f"Interface {r['interface']:.3f}m | overlap {r['overlap']:.3f}m²",f"Remaining contiguous field: {r['remaining']:.3f}m²"]
        lines += [f"Failure: {r.get('failure','none')}"]
        for j,line in enumerate(lines):
            color='#b01630' if r['status']!='ramp_operational' and ('Status' in line or 'Failure' in line) else '#20272c'
            out.append(text(x+18,y+785+j*28,line,13,'bold' if ('Status' in line or 'Failure' in line) else 'normal',color))
    out += [text(40,1225,f"NEW TWO-CURVE CANDIDATES: {total} | HARD VALID: {valid_count} | PARKING NOT RUN",15,'bold','#155b2c'),text(40,1252,'SINGLE-CURVE SEARCHES NOT REUSED | PHYSICAL RAMP NOT PUBLISHED | HUMAN ACCEPTANCE PENDING',14,'bold'),'</svg>'];return ''.join(out)

if __name__=='__main__':main()
