import json,sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.integrated_ramp_arrival_v1 import IntegratedRampArrivalV1
from tools.generate_parcel2_basement_v2_design import View,text,svg_to_png

def main():
 p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];d=json.loads(p.read_text());h=BasementRampParkingDesignReasonerV2();f=h._frame(d['site']['parcel'],d['site']['frontage']);inner=h._to_local_polygon(d['physical_basement_wall']['inner_face'],f);r=IntegratedRampArrivalV1().resolve(inner);valid=[c for c in r['candidates'] if c['geometry_status']=='ramp_operational'];left=next((c for c in valid if c['side']=='west'),None);right=next((c for c in valid if c['side']=='east'),None);lim=min((c for c in r['candidates'] if 'arrival_transverse_mismatch' in c),key=lambda c:c['arrival_transverse_mismatch'])
 prev=json.loads(sorted(p.parent.glob('maneuver_first_reverse_solve_*/PARCEL2_15_MANEUVER_FIRST_REVERSE_SOLVE.json'))[-1].read_text())['comparison_records'][2];records=[{'label':'A — FROZEN SEPARATE-TERMINAL FAILURE','status':'frozen','field':prev.get('field',[]),'failure':prev.get('failure')},rec('B — BEST WEST INTEGRATED ARRIVAL',left),rec('C — BEST EAST / LIMITING ARRIVAL',right or lim)]
 contract={'contract':'Parcel2IntegratedRampArrivalComparison','integrated_arrival_topology':True,'separate_terminal_leg_required':False,'old_reverse_solve_reused':False,'arrival_edge_trials':len(r['arrival_edge_trials']),'new_candidates':len(r['candidates']),'hard_valid_candidates':len(valid),'status':r['status'],'first_geometric_contradiction':r['first_geometric_contradiction'],'comparison_records':records,'physical_ramp_published':False,'human_visual_acceptance':'pending'}
 folder=p.parent/('integrated_ramp_arrival_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir();jp=folder/'PARCEL2_15_INTEGRATED_RAMP_ARRIVAL.json';sp=folder/'PARCEL2_15_INTEGRATED_RAMP_ARRIVAL.svg';pp=folder/'PARCEL2_15_INTEGRATED_RAMP_ARRIVAL.png';jp.write_text(json.dumps(contract,indent=2),encoding='utf-8');sp.write_text(render(records,inner,contract),encoding='utf-8');svg_to_png(sp,pp);print(json.dumps({'folder':str(folder),'png':str(pp),'json':str(jp),'trials':len(r['arrival_edge_trials']),'candidates':len(r['candidates']),'hard_valid':len(valid),'status':r['status']}))

def rec(label,c):
 if c is None:return {'label':label,'status':'not_generated'}
 if c.get('geometry_status')!='ramp_operational':return {'label':label,'status':'limiting_geometry','field':c['maneuvering_field'],'candidate_id':c['candidate_id'],'mismatch':c['arrival_transverse_mismatch'],'rinner':c['R_inner'],'rcenter':c['R_centerline'],'router':c['R_outer'],'failure':', '.join(c['failure_reasons'])}
 t=c['topology'];return {'label':label,'status':'ramp_operational','candidate_id':c['candidate_id'],'ramp':c['ramp_surface'],'centerline':t['centerline'],'field':c['maneuvering_field'],'end':c['arrival_edge'],'movement':c['vehicle_movement_path'],'leg1':t['leg_1_length'],'rinner':t['R_inner'],'rcenter':t['R_centerline'],'router':t['R_outer'],'interface':c['arrival_interface_width'],'overlap':c['ramp_maneuver_overlap_area'],'end_z':[c['end_left_z'],c['end_center_z'],c['end_right_z']],'failure':'none'}

def render(rs,inner,c):
 v=View(list(inner.exterior.coords)[:-1]);o=['<svg xmlns="http://www.w3.org/2000/svg" width="2040" height="1260"><rect width="100%" height="100%" fill="#f7f6f1"/>',text(40,44,'REAL PARCEL 2 — 15% INTEGRATED RAMP ARRIVAL',27,'bold'),text(40,74,'MAIN LEG → R5 CURVE → LEVEL ARRIVAL EDGE → MANEUVER FIELD',17,'bold')]
 for i,r in enumerate(rs):
  x=24+i*674;y=98;o += [f'<rect x="{x}" y="{y}" width="650" height="1090" rx="8" fill="white" stroke="#8497a2" stroke-width="2"/>',text(x+18,y+34,r['label'],17,'bold'),f'<svg x="{x+18}" y="{y+55}" width="614" height="690" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet"><polygon points="{v.points(list(inner.exterior.coords)[:-1])}" fill="#edf1ef" stroke="#263a43" stroke-width="6"/>']
  if r.get('ramp'):o.append(f'<polygon points="{v.points(r["ramp"])}" fill="#efb3bf" fill-opacity=".65" stroke="#a61734" stroke-width="4"/>')
  if r.get('field'):o.append(f'<polygon points="{v.points(r["field"])}" fill="#9fd9ad" fill-opacity=".65" stroke="#176f37" stroke-width="6"/>')
  if r.get('centerline'):o.append(f'<polyline points="{v.points(r["centerline"])}" fill="none" stroke="#0865af" stroke-width="7" stroke-dasharray="16 9"/>')
  if r.get('end'):o.append(f'<polyline points="{v.points(r["end"])}" fill="none" stroke="#541128" stroke-width="12"/>')
  o.append('</svg>');lines=[f"Candidate: {r.get('candidate_id','frozen diagnostic')}",f"Status: {r['status']}"]
  if r['status']=='ramp_operational':lines += [f"Leg1: {r['leg1']:.3f} m | terminal leg: NONE",f"R inner/center/outer: {r['rinner']:.2f}/{r['rcenter']:.2f}/{r['router']:.2f} m",f"Interface: {r['interface']:.3f} m | overlap: {r['overlap']:.3f} m²",f"END L/C/R Z: {r['end_z'][0]:.2f}/{r['end_z'][1]:.2f}/{r['end_z'][2]:.2f}"]
  elif 'mismatch' in r:lines += [f"R inner/center/outer: {r['rinner']:.2f}/{r['rcenter']:.2f}/{r['router']:.2f} m",f"Arrival transverse mismatch: {r['mismatch']:.3f} m"]
  lines += [f"Failure: {r.get('failure','none')}"]
  for j,s in enumerate(lines):o.append(text(x+18,y+785+j*31,s,14,'bold' if ('Status' in s or 'Failure' in s) else 'normal','#b01630' if r['status']!='ramp_operational' and ('Status' in s or 'Failure' in s) else '#20272c'))
 e=c['first_geometric_contradiction'];o += [text(40,1225,f"ARRIVAL EDGE TRIALS: {c['arrival_edge_trials']} | NEW CANDIDATES: {c['new_candidates']} | HARD VALID: {c['hard_valid_candidates']}",15,'bold'),text(40,1252,f"FIRST CONTRADICTION: {', '.join(e['failure_reasons'])} | | HUMAN ACCEPTANCE PENDING",14,'bold','#b01630'),'</svg>'];return ''.join(o)
if __name__=='__main__':main()
