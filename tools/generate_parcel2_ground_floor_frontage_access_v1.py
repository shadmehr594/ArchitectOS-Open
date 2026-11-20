import json
import sys
from datetime import datetime
from pathlib import Path
from shapely.geometry import box

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.ground_floor_frontage_program_v1 import GroundFloorFrontageProgramV1
from tools.generate_parcel2_basement_v2_design import View,text,svg_to_png

def poly(p):return [[float(x),float(y)] for x,y in list(p.exterior.coords)[:-1]]

def main():
 source=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];data=json.loads(source.read_text());h=BasementRampParkingDesignReasonerV2();frame=h._frame(data['site']['parcel'],data['site']['frontage']);inner=h._to_local_polygon(data['physical_basement_wall']['inner_face'],frame)
 ramp_source=sorted(source.parent.glob('regulation_aware_straight_parking_*/PARCEL2_REGULATION_AWARE_STRAIGHT_RAMP_PARKING.json'))[-1];ramp=json.loads(ramp_source.read_text());reservations=[c for c in ramp['straight_candidates'] if c['slope']==.16 and c['status']=='architecture_selected_candidate']
 result=GroundFloorFrontageProgramV1().resolve(inner,reservations,data['requirements']['parking_pedestrian']['required_clear_width'])
 u0,v0,u1,v1=inner.bounds;result['site_geometry']={'ground_floor_clear_face':poly(inner),'legal_frontage':[[u0,v0],[u1,v0]],'road_polygon':poly(box(u0,v0-2,u1,v0)),'source_parcel':data['site']['parcel'],'source_frontage':data['site']['frontage']};result['vehicle_access_source_contract']=str(ramp_source)
 folder=source.parent/('ground_floor_frontage_access_v1_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir();jp=folder/'PARCEL2_GROUND_FLOOR_FRONTAGE_ACCESS_V1.json';sp=folder/'PARCEL2_GROUND_FLOOR_FRONTAGE_ACCESS_V1.svg';pp=folder/'PARCEL2_GROUND_FLOOR_FRONTAGE_ACCESS_V1.png'
 jp.write_text(json.dumps(result,indent=2),encoding='utf-8');sp.write_text(render(result,inner),encoding='utf-8');svg_to_png(sp,pp);print(json.dumps({'json':str(jp),'png':str(pp),'status':result['ground_floor_frontage_status'],'diagnostic':result['selected_diagnostic_candidate']['candidate_id'] if result['selected_diagnostic_candidate'] else None,'rule_status':result['rule_status']}))

def render(contract,inner):
 view=View(list(inner.exterior.coords)[:-1]);west=next(c for c in contract['candidates'] if c['candidate_id'].startswith('GF-FRONTAGE-WEST') and c['candidate_id'].endswith('-1'));east=next(c for c in contract['candidates'] if c['candidate_id'].startswith('GF-FRONTAGE-EAST') and c['candidate_id'].endswith('-1'));records=[west,east,contract['selected_diagnostic_candidate']];titles=['A — '+west['arrangement_family'],'B — '+east['arrangement_family'],'C — BEST GEOMETRIC CORE INTERFACE (RULE PENDING)'];out=['<svg xmlns="http://www.w3.org/2000/svg" width="2040" height="1260"><rect width="100%" height="100%" fill="#f7f6f1"/>',text(40,43,'REAL PARCEL 2 — CORRIDOR TERMINATION AT CORE INTERFACE',27,'bold'),text(40,73,'FULL-DEPTH CORRIDOR RELEASED — FIRE/EGRESS NUMERIC RULES PENDING',15,'bold')]
 for i,c in enumerate(records):
  x=24+i*674;y=98;out += [f'<rect x="{x}" y="{y}" width="650" height="1090" rx="8" fill="white" stroke="#8497a2" stroke-width="2"/>',text(x+18,y+34,titles[i],17,'bold'),f'<svg x="{x+18}" y="{y+55}" width="614" height="760" viewBox="0 0 1900 1450" preserveAspectRatio="xMidYMid meet"><defs><marker id="p{i}" markerWidth="12" markerHeight="12" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#6545a0"/></marker></defs>']
  road=contract['site_geometry']['road_polygon'];out += [f'<polygon points="{view.points(road)}" fill="#b9bec2" stroke="#59636b" stroke-width="5"/>',f'<polygon points="{view.points(contract["site_geometry"]["ground_floor_clear_face"])}" fill="#f1f2ef" stroke="#263a43" stroke-width="7"/>',f'<polygon points="{view.points(c["vehicle_ramp_reservation"])}" fill="#efb3bf" stroke="#a61734" stroke-width="4"/>']
  for cp in c['commercial_space_polygon']:out.append(f'<polygon points="{view.points(cp)}" fill="#f4d487" fill-opacity=".7" stroke="#a76b00" stroke-width="5"/>')
  out += [f'<polygon points="{view.points(c["pedestrian_clear_corridor_polygon"])}" fill="#cfc3ef" fill-opacity=".8" stroke="#6545a0" stroke-width="5"/>',f'<polygon points="{view.points(c["future_core_access_zone"])}" fill="#75c8c7" stroke="#087b7a" stroke-width="6"/>',f'<polyline points="{view.points(c["pedestrian_centerline"])}" fill="none" stroke="#6545a0" stroke-width="7" stroke-dasharray="17 10" marker-end="url(#p{i})"/>']
  px,py=view.p(c['corridor_end']);out += [text(px+20,py,'CORE INTERFACE',21,'bold','#087b7a'),text(px+20,py+27,'GEOMETRY NOT GENERATED',15,'normal','#087b7a'),text(view.p(c['corridor_start'])[0],view.p(c['corridor_start'])[1]+45,'EXTERIOR DISCHARGE',22,'bold','#6545a0','middle'),'</svg>']
  m=c['quality_metrics'];lines=[f"Candidate: {c['candidate_id']}",f"Geometry: {c['geometry_status']} | publication: {c['publication_status']}",f"Frontage: {c['frontage_width']:.3f}m",f"Vehicle / pedestrian / commercial: {c['vehicle_access_width']:.3f} / {c['pedestrian_access_width']:.3f} / {c['commercial_frontage_width']:.3f}m",f"Corridor start→core: {c['corridor_length']:.3f}m | turns: {c['turn_count']}",f"Old/new corridor area: {m['old_reserved_corridor_area']:.3f}/{m['new_required_corridor_area']:.3f}m²",f"Recovered corridor area: {c['released_old_corridor_area']:.3f}m²",f"Core interface: {c['future_core_interface_width']:.3f}m",'FIRE EGRESS LIMITS: PENDING RULE RESOLUTION']
  for j,line in enumerate(lines):out.append(text(x+18,y+850+j*27,line,13,'bold' if j in (1,8) else 'normal','#155b2c' if j==1 else '#20272c'))
 out += [text(40,1225,f"PUBLICATION STATUS: {contract['ground_floor_frontage_status'].upper()} | RULE STATUS: {contract['rule_status'].upper()}",15,'bold','#b01630'),text(40,1252,'FULL-DEPTH CORRIDOR NOT FROZEN | NO STAIR / ELEVATOR / CORE GEOMETRY GENERATED',14,'bold'),'</svg>'];return ''.join(out)

if __name__=='__main__':main()
