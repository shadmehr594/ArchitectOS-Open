import json,sys
from datetime import datetime
from pathlib import Path
from shapely.geometry import box
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.vertical_circulation_core_level_aware_v2 import VerticalCirculationCoreLevelAwareV2
from tools.generate_parcel2_basement_v2_design import View,text,svg_to_png

def poly(p):return [[float(x),float(y)] for x,y in list(p.exterior.coords)[:-1]]
def main():
 p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];d=json.loads(p.read_text());h=BasementRampParkingDesignReasonerV2();f=h._frame(d['site']['parcel'],d['site']['frontage']);inner=h._to_local_polygon(d['physical_basement_wall']['inner_face'],f);gf_path=sorted(p.parent.glob('ground_floor_frontage_access_v1_*/PARCEL2_GROUND_FLOOR_FRONTAGE_ACCESS_V1.json'))[-1];rp_path=sorted(p.parent.glob('regulation_aware_straight_parking_*/PARCEL2_REGULATION_AWARE_STRAIGHT_RAMP_PARKING.json'))[-1];vc_path=sorted(p.parent.glob('vertical_core_placement_v1_*/PARCEL2_VERTICAL_CIRCULATION_CORE_PLACEMENT_V1.json'))[-1];gf=json.loads(gf_path.read_text());rp=json.loads(rp_path.read_text());vc=json.loads(vc_path.read_text());r=VerticalCirculationCoreLevelAwareV2().resolve(inner,gf['selected_diagnostic_candidate'],rp['selected_candidate'],vc['best_whole_building_candidate']);r['sources']={'site':str(p),'frontage':str(gf_path),'parking':str(rp_path),'previous_core':str(vc_path)};r['context_geometry']={'clear_face':poly(inner),'road':poly(box(inner.bounds[0],inner.bounds[1]-2,inner.bounds[2],inner.bounds[1])),'ramp':rp['selected_candidate']['ramp_surface'],'maneuver':rp['selected_candidate']['maneuvering_field'],'stalls':rp['selected_candidate']['parking_stalls'],'frontage':gf['selected_diagnostic_candidate']}
 folder=p.parent/('vertical_core_level_aware_v2_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir();jp=folder/'PARCEL2_VERTICAL_CORE_LEVEL_AWARE_V2.json';plan=folder/'PARCEL2_VERTICAL_CORE_LEVEL_AWARE_PLAN_V2.svg';plan_png=folder/'PARCEL2_VERTICAL_CORE_LEVEL_AWARE_PLAN_V2.png';sec=folder/'PARCEL2_VERTICAL_CORE_STAIR_SECTION_V2.svg';sec_png=folder/'PARCEL2_VERTICAL_CORE_STAIR_SECTION_V2.png';jp.write_text(json.dumps(r,indent=2),encoding='utf-8');plan.write_text(render_plan(r,inner),encoding='utf-8');sec.write_text(render_section(r),encoding='utf-8');svg_to_png(plan,plan_png);svg_to_png(sec,sec_png);print(json.dumps({'json':str(jp),'plan_png':str(plan_png),'section_png':str(sec_png),'candidates':r['candidate_count'],'hard_valid':r['hard_valid_count'],'selected':r['selected_candidate']['candidate_id']}))

def stair_plan(out,view,s,color='#8f5200'):
 for f in s['flights']:
  out.append(f'<polygon points="{view.points(f["polygon"])}" fill="#f3d5a3" stroke="{color}" stroke-width="5"/>')
  for line in f['tread_lines']:out.append(f'<line x1="{view.p(line[0])[0]}" y1="{view.p(line[0])[1]}" x2="{view.p(line[1])[0]}" y2="{view.p(line[1])[1]}" stroke="{color}" stroke-width="2"/>')
  a=view.p(f['start_point']);b=view.p(f['end_point']);out += [f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="#1263aa" stroke-width="6" marker-end="url(#arr)"/>',text(a[0],a[1]+20,'START',19,'bold','#1263aa','middle'),text(b[0],b[1]-12,'END',19,'bold','#1263aa','middle')]
 for l in s['landings']:out.append(f'<polygon points="{view.points(l["polygon"])}" fill="#e9c27f" stroke="{color}" stroke-width="4"/>')

def render_plan(r,inner):
 c=r['selected_candidate'];view=View(list(inner.exterior.coords)[:-1]);floors=[('BASEMENT / B1','B1_GF'),('GROUND FLOOR / GF','GF_F1'),('FIRST FLOOR / F1','F1_F2'),('SECOND FLOOR / F2','F1_F2')];out=['<svg xmlns="http://www.w3.org/2000/svg" width="2200" height="1500"><rect width="100%" height="100%" fill="#f7f6f1"/><defs><marker id="arr" markerWidth="12" markerHeight="12" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#1263aa"/></marker></defs>',text(40,43,'REAL PARCEL 2 — LEVEL-AWARE VERTICAL CORE PLAN V2',28,'bold'),text(40,73,f"SELECTED {c['candidate_id']} | PREVIOUS 4.20×4.38 CORE RESIZED TO {c['core_dimensions'][0]:.2f}×{c['core_dimensions'][1]:.2f}m",15,'bold')]
 for i,(title,key) in enumerate(floors):
  x=25+(i%2)*1080;y=95+(i//2)*690;out += [f'<rect x="{x}" y="{y}" width="1050" height="660" rx="8" fill="white" stroke="#8497a2" stroke-width="2"/>',text(x+18,y+32,title,18,'bold'),f'<svg x="{x+18}" y="{y+45}" width="620" height="590" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet"><polygon points="{view.points(r["context_geometry"]["clear_face"])}" fill="#eef1ef" stroke="#263a43" stroke-width="7"/>']
  if i==0:
   out += [f'<polygon points="{view.points(r["context_geometry"]["ramp"])}" fill="#efb3bf" stroke="#a61734" stroke-width="4"/>',f'<polygon points="{view.points(r["context_geometry"]["maneuver"])}" fill="#a8ddb5" stroke="#176f37" stroke-width="5"/>']
   for n,p in enumerate(r['context_geometry']['stalls']):out.append(f'<polygon points="{view.points(p)}" fill="#d8e3ee" stroke="#304c67" stroke-width="5"/>')
   for k in ('stall_1_to_core_path','stall_2_to_core_path'):out.append(f'<polyline points="{view.points(c["basement"][k]["actual_path_polyline"])}" fill="none" stroke="#6545a0" stroke-width="6" stroke-dasharray="14 8"/>')
  elif i==1:
   out.append(f'<polygon points="{view.points(r["context_geometry"]["ramp"])}" fill="#efb3bf" stroke="#a61734" stroke-width="4"/>')
   for p in c['ground_floor']['commercial_space_polygons']:out.append(f'<polygon points="{view.points(p)}" fill="#f4d487" fill-opacity=".68" stroke="#a76b00" stroke-width="5"/>')
   out += [f'<polygon points="{view.points(c["ground_floor"]["pedestrian_corridor"])}" fill="#cfc3ef" stroke="#6545a0" stroke-width="5"/>',f'<polyline points="{view.points(c["ground_floor"]["corridor_centerline"])}" fill="none" stroke="#6545a0" stroke-width="7" stroke-dasharray="14 8"/>']
  else:out.append(f'<polygon points="{view.points(c["upper_floor"]["common_distribution"])}" fill="#92d1df" stroke="#16708b" stroke-width="5"/>')
  out += [f'<polygon points="{view.points(c["core_polygon"])}" fill="#f7e1b8" fill-opacity=".5" stroke="#a76300" stroke-width="7"/>',f'<polygon points="{view.points(c["elevator"]["shaft_polygon"])}" fill="#9ec9d0" stroke="#176b78" stroke-width="6"/>',f'<polygon points="{view.points(c["common_lobby"]["polygon"])}" fill="#c2e5c8" stroke="#27793c" stroke-width="6"/>']
  stair_plan(out,view,c['stairs_by_span'][key]);out.append('</svg>');s=c['stairs_by_span'][key];lines=[f"{s['start_floor']}→{s['end_floor']} | rise {s['total_rise']:.2f}m",f"N={s['riser_count']} | R={s['actual_riser_height']*1000:.1f}mm",f"T={s['tread_count']} @ {s['tread_depth']:.2f}m | split {s['flight_distribution']}",f"W={s['clear_width']:.2f}m | well L={s['required_stairwell_length']:.2f}m",f"Elevator door Z={r['level_contract'][['basement_elevation','ground_elevation','first_floor_elevation','second_floor_elevation'][i]]:+.2f}m"]
  for j,line in enumerate(lines):out.append(text(x+660,y+100+j*30,line,12,'bold' if j==0 else 'normal'))
 out += [text(40,1470,'RENDERER: PRODUCTION CONTRACT ONLY | PHYSICAL CORE PUBLICATION: PENDING HUMAN ACCEPTANCE',14,'bold'),'</svg>'];return ''.join(out)

def render_section(r):
 c=r['selected_candidate'];W,H=2100,1250;zmin,zmax=-2.4,7.94;zy=lambda z:1080-(z-zmin)/(zmax-zmin)*900;out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="#f7f6f1"/>',text(40,43,'PARCEL 2 — LEVEL-AWARE STAIR UNFOLDED SECTION V2',27,'bold'),text(40,72,'PROFILES, COUNTS AND LANDING LEVELS READ FROM PRODUCTION STAIR CONTRACT',15,'bold')]
 for name,z in [('B1',-2.4),('GF',0),('F1',4.7),('F2',7.94)]:out += [f'<line x1="80" y1="{zy(z)}" x2="2020" y2="{zy(z)}" stroke="#73818a" stroke-width="2" stroke-dasharray="10 8"/>',text(85,zy(z)-8,f'{name} = {z:+.2f} m',16,'bold')]
 xbases=(180,820,1460);available=500
 for i,key in enumerate(('B1_GF','GF_F1','F1_F2')):
  s=c['stairs_by_span'][key];xbase=xbases[i];extent=max(x for x,z in s['unfolded_profile']);scale=available/extent;pts=' '.join(f'{xbase+x*scale},{zy(z)}' for x,z in s['unfolded_profile']);out.append(f'<polyline points="{pts}" fill="none" stroke="#9c4f00" stroke-width="4"/>')
  ls=s['unfolded_landing_segment'];x1=xbase+ls[0][0]*scale;x2=xbase+ls[1][0]*scale;lz=ls[0][1];out += [f'<line x1="{x1}" y1="{zy(lz)}" x2="{x2}" y2="{zy(lz)}" stroke="#14805c" stroke-width="7"/>',text((x1+x2)/2,zy(lz)-10,f"LANDING {lz:+.3f}m",12,'bold','#14805c','middle')]
  info=f"{s['start_floor']}→{s['end_floor']} | rise {s['total_rise']:.2f}m | N={s['riser_count']} | R={s['actual_riser_height']*1000:.1f}mm | treads={s['tread_count']} @ {s['tread_depth']:.2f}m | split {s['flight_distribution']}";out.append(text(180,1140+i*27,info,14,'bold'))
 out += [text(260,1225,f"HEADROOM {r['active_stair_policy']['minimum_headroom']:.2f}m | CLEAR WIDTH {r['active_stair_policy']['clear_width']:.2f}m | ELEVATOR VERTICAL EXTENT -2.40→+7.94m",14,'bold'),'</svg>'];return ''.join(out)
if __name__=='__main__':main()
