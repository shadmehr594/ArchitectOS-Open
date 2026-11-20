import json,sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.vertical_circulation_core_placement_v1 import VerticalCirculationCorePlacementV1
from tools.generate_parcel2_basement_v2_design import View,text,svg_to_png

def main():
 p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];d=json.loads(p.read_text());h=BasementRampParkingDesignReasonerV2();f=h._frame(d['site']['parcel'],d['site']['frontage']);inner=h._to_local_polygon(d['physical_basement_wall']['inner_face'],f);gf_path=sorted(p.parent.glob('ground_floor_frontage_access_v1_*/PARCEL2_GROUND_FLOOR_FRONTAGE_ACCESS_V1.json'))[-1];gf=json.loads(gf_path.read_text());rp_path=sorted(p.parent.glob('regulation_aware_straight_parking_*/PARCEL2_REGULATION_AWARE_STRAIGHT_RAMP_PARKING.json'))[-1];rp=json.loads(rp_path.read_text());result=VerticalCirculationCorePlacementV1().resolve(inner,gf['selected_diagnostic_candidate'],rp['selected_candidate'],d['requirements']['core']);result['sources']={'site':str(p),'frontage':str(gf_path),'parking':str(rp_path)};result['clear_face']=[[float(x),float(y)] for x,y in list(inner.exterior.coords)[:-1]];result['approved_ramp']=rp['selected_candidate']['ramp_surface'];result['approved_stalls']=rp['selected_candidate']['parking_stalls'];result['approved_maneuver']=rp['selected_candidate']['maneuvering_field']
 folder=p.parent/('vertical_core_placement_v1_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir();jp=folder/'PARCEL2_VERTICAL_CIRCULATION_CORE_PLACEMENT_V1.json';sp=folder/'PARCEL2_VERTICAL_CIRCULATION_CORE_PLACEMENT_V1.svg';pp=folder/'PARCEL2_VERTICAL_CIRCULATION_CORE_PLACEMENT_V1.png';jp.write_text(json.dumps(result,indent=2),encoding='utf-8');sp.write_text(render(result,inner),encoding='utf-8');svg_to_png(sp,pp);print(json.dumps({'json':str(jp),'svg':str(sp),'png':str(pp),'candidates':result['candidate_count'],'hard_valid':result['hard_valid_count'],'best':result['best_whole_building_candidate']['candidate_id']}))

def render(r,inner):
 view=View(list(inner.exterior.coords)[:-1]);records=[('A — EARLIEST FEASIBLE',r['earliest_feasible_candidate']),('B — BEST WHOLE-BUILDING',r['best_whole_building_candidate']),('C — BEST TWO-UNIT PRESERVATION',r['best_upper_floor_candidate'])];out=['<svg xmlns="http://www.w3.org/2000/svg" width="2040" height="1500"><rect width="100%" height="100%" fill="#f7f6f1"/>',text(40,42,'REAL PARCEL 2 — VERTICAL CIRCULATION CORE PLACEMENT V1',27,'bold'),text(40,72,'BASEMENT + GROUND FLOOR + UPPER-FLOOR TWO-UNIT TOPOLOGY',15,'bold')]
 for i,(title,c) in enumerate(records):
  x=24+i*674;y=95;out += [f'<rect x="{x}" y="{y}" width="650" height="1340" rx="8" fill="white" stroke="#8497a2" stroke-width="2"/>',text(x+18,y+32,title,17,'bold')]
  for row,(floor_label,extra) in enumerate([('GROUND FLOOR','ground'),('BASEMENT','basement'),('UPPER FLOOR PROJECTION','upper')]):
   yy=y+48+row*355;out += [text(x+18,yy+20,floor_label,14,'bold'),f'<svg x="{x+18}" y="{yy+28}" width="614" height="315" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet"><polygon points="{view.points(r["clear_face"])}" fill="#eef1ef" stroke="#263a43" stroke-width="7"/>']
   if extra=='ground':
    out += [f'<polygon points="{view.points(c["ground_floor"]["pedestrian_corridor"])}" fill="#cfc3ef" stroke="#6545a0" stroke-width="5"/>',f'<polyline points="{view.points(c["ground_floor"]["corridor_centerline"])}" fill="none" stroke="#6545a0" stroke-width="7" stroke-dasharray="15 9"/>']
   elif extra=='basement':
    out += [f'<polygon points="{view.points(r["approved_ramp"])}" fill="#efb3bf" stroke="#a61734" stroke-width="4"/>',f'<polygon points="{view.points(r["approved_maneuver"])}" fill="#a8ddb5" stroke="#176f37" stroke-width="5"/>']
    for p in r['approved_stalls']:out.append(f'<polygon points="{view.points(p)}" fill="#d8e3ee" stroke="#304c67" stroke-width="5"/>')
    for key in ('stall_1_to_core_path','stall_2_to_core_path'):out.append(f'<polyline points="{view.points(c["basement"][key]["actual_path_polyline"])}" fill="none" stroke="#684ca0" stroke-width="6" stroke-dasharray="14 8"/>')
   else:
    out.append(f'<polygon points="{view.points(c["upper_floor"]["common_distribution"])}" fill="#87c8dc" stroke="#16708b" stroke-width="5"/>')
   out += [f'<polygon points="{view.points(c["core_polygon"])}" fill="#f3bd65" fill-opacity=".55" stroke="#a76300" stroke-width="7"/>',f'<polygon points="{view.points(c["stair"]["polygon"])}" fill="#f3d5a3" stroke="#8f5200" stroke-width="5"/>',f'<polygon points="{view.points(c["elevator"]["shaft_polygon"])}" fill="#9ec9d0" stroke="#176b78" stroke-width="5"/>',f'<polygon points="{view.points(c["common_lobby"]["polygon"])}" fill="#c2e5c8" stroke="#27793c" stroke-width="5"/>','</svg>']
  q=c['quality_metrics'];u=c['upper_floor']['private_field_metrics'];lines=[f"Candidate: {c['candidate_id']}",f"Station / corridor: {c['core_station']:.3f} / {c['ground_floor']['corridor_length']:.3f}m",f"Core: {c['core_dimensions'][0]:.2f}×{c['core_dimensions'][1]:.2f}m | lobby {c['common_lobby']['area']:.2f}m²",f"Stair width {c['stair']['clear_width']:.2f}m | 2 flights + landing",f"Elevator shaft: {c['elevator']['shaft_dimensions'][0]:.2f}×{c['elevator']['shaft_dimensions'][1]:.2f}m",f"Parking preserved: {c['basement']['parking_capacity_preserved']}/2",f"Stall paths: {c['basement']['stall_1_to_core_path']['route_length']:.2f} / {c['basement']['stall_2_to_core_path']['route_length']:.2f}m",f"Unit fields A/B: {u['unit_a_allocatable_area']:.2f}/{u['unit_b_allocatable_area']:.2f}m²",f"Two-unit balance: {u['balance_ratio']:.3f}",f"Fire rules: {c['fire_egress']['rule_status']} | geometry {c['geometry_status']}"]
  for j,line in enumerate(lines):out.append(text(x+18,y+1140+j*25,line,13,'bold' if j in (0,9) else 'normal','#155b2c' if j==9 else '#20272c'))
 out += [text(40,1460,f"CANDIDATES {r['candidate_count']} | HARD VALID {r['hard_valid_count']} | CORE PUBLICATION PENDING HUMAN ACCEPTANCE",15,'bold','#155b2c'),text(40,1487,'FIRE EGRESS RULE STATUS: PENDING_RULE_RESOLUTION | NO APARTMENT ROOMS / STRUCTURE / BIM / IFC',14,'bold','#b01630'),'</svg>'];return ''.join(out)

if __name__=='__main__':main()
