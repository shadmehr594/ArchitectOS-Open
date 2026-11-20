import json, sys
from datetime import datetime
from pathlib import Path
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.vertical_core_architectural_usability_v3 import VerticalCoreArchitecturalUsabilityV3
from tools.generate_parcel2_basement_v2_design import text,svg_to_png

COL={'ramp':'#eaa2b2','maneuver':'#a9dcb6','stall':'#d8e3ee','core':'#f5d69a','stair':'#eabf75','elevator':'#8bc3cf','lobby':'#b6dfbe','corridor':'#cabce8','commercial':'#f1d17f','unitA':'#d5e6b7','unitB':'#bad8ef'}

def pt(p,b,x,y,w,h):
 x0,y0,x1,y1=b;s=min(w/(x1-x0),h/(y1-y0));ox=x+(w-(x1-x0)*s)/2;oy=y+(h-(y1-y0)*s)/2;return ox+(p[0]-x0)*s,oy+(y1-p[1])*s
def points(poly,b,x,y,w,h):return ' '.join(f'{a:.1f},{d:.1f}' for a,d in (pt(p,b,x,y,w,h) for p in poly))
def polygon(out,p,b,x,y,w,h,fill,stroke='#344850',dash=None,opacity=1):
 ds=f' stroke-dasharray="{dash}"' if dash else '';out.append(f'<polygon points="{points(p,b,x,y,w,h)}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="3"{ds}/>')
def line(out,p,b,x,y,w,h,color='#6545a0',dash=None,width=4,arrow=False):
 ds=f' stroke-dasharray="{dash}"' if dash else '';mark=' marker-end="url(#arr)"' if arrow else '';out.append(f'<polyline points="{points(p,b,x,y,w,h)}" fill="none" stroke="{color}" stroke-width="{width}"{ds}{mark}/>')

def stair_cut(out,c,level,b,x,y,w,h):
 plan=c['floor_stair_plan_by_level'][level]
 for p in plan['visible_below_cut_geometry']:polygon(out,p,b,x,y,w,h,COL['stair'],'#8c5300')
 for p in plan['visible_above_cut_geometry']:polygon(out,p,b,x,y,w,h,'none','#8c5300','9 6')
 span={'B1':'B1_GF','GF':'GF_F1','F1':'F1_F2','F2':'F1_F2'}[level];s=c['stairs_by_span'][span]
 for f in s['flights']:
  for tread in f['tread_lines']:line(out,tread,b,x,y,w,h,'#8c5300',None,1)
 if plan['floor_start']:
  q=pt(plan['floor_start'],b,x,y,w,h);out.append(text(q[0],q[1]+17,'START / UP',12,'bold','#1263aa','middle'))
 if plan['floor_arrival']:
  q=pt(plan['floor_arrival'],b,x,y,w,h);out.append(text(q[0],q[1]-10,'ARRIVAL / DOWN',12,'bold','#1263aa','middle'))

def panel(out,title,x,y,w,h):out += [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="white" stroke="#8297a2" stroke-width="2"/>',text(x+18,y+30,title,18,'bold')]

def render(r):
 c=r['selected_candidate'];ctx=r['context_geometry'];b=Polygon(ctx['clear_face']).bounds;W,H=2400,1800
 out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="#f7f6f1"/><defs><marker id="arr" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#1263aa"/></marker></defs>',text(35,42,'REAL PARCEL 2 — VERTICAL CORE ARCHITECTURAL USABILITY V3',27,'bold'),text(35,70,f"SELECTED {c['candidate_id']} | SAME-CANDIDATE METRICS ONLY | HUMAN ACCEPTANCE PENDING",14,'bold')]
 panels=[('BASEMENT / B1',25,90,760,780,'B1'),('GROUND FLOOR / GF',820,90,760,780,'GF'),('FIRST FLOOR / F1',1615,90,760,780,'F1'),('SECOND FLOOR / F2',25,900,760,780,'F2')]
 for title,x,y,w,h,level in panels:
  panel(out,title,x,y,w,h);gx,gy,gw,gh=x+25,y+45,430,h-75;polygon(out,ctx['clear_face'],b,gx,gy,gw,gh,'#eef1ef')
  if level=='B1':
   polygon(out,ctx['ramp'],b,gx,gy,gw,gh,COL['ramp'],'#a61734');polygon(out,ctx['maneuver'],b,gx,gy,gw,gh,COL['maneuver'],'#176f37')
   for i,p in enumerate(ctx['stalls']):polygon(out,p,b,gx,gy,gw,gh,COL['stall'],'#304c67');q=pt(Polygon(p).centroid.coords[0],b,gx,gy,gw,gh);out.append(text(q[0],q[1],f'P-{i+1:02d}',12,'bold','#304c67','middle'))
   for k in ('stall_1_to_core_path','stall_2_to_core_path'):line(out,c['basement'][k]['actual_path_polyline'],b,gx,gy,gw,gh,'#6545a0','8 5',3,True)
  elif level=='GF':
   polygon(out,ctx['ramp'],b,gx,gy,gw,gh,COL['ramp'],'#a61734')
   for p in c['ground_floor']['commercial_space_polygons']:polygon(out,p,b,gx,gy,gw,gh,COL['commercial'],'#9b6500',None,.7)
   polygon(out,c['ground_floor']['pedestrian_corridor'],b,gx,gy,gw,gh,COL['corridor'],'#6545a0');line(out,c['ground_floor']['corridor_centerline'],b,gx,gy,gw,gh,'#6545a0','8 5',3,True)
   for label,key,color in [('VEHICLE 3.00m','vehicle_access_interval','#a61734'),('PEDESTRIAN 1.20m','pedestrian_access_interval','#6545a0'),('COMMERCIAL 5.20m','commercial_access_interval','#805400')]:
    iv=ctx['frontage'][key];q=pt([(iv[0]+iv[1])/2,b[1]],b,gx,gy,gw,gh);out.append(text(q[0],q[1]+17,label,10,'bold',color,'middle'))
  else:
   polygon(out,c['upper_floor']['unit_a_private_field'],b,gx,gy,gw,gh,COL['unitA'],'#53742c',None,.65);polygon(out,c['upper_floor']['unit_b_private_field'],b,gx,gy,gw,gh,COL['unitB'],'#356883',None,.65)
   line(out,c['upper_floor']['unit_a_entry_interface'],b,gx,gy,gw,gh,'#53742c',None,7);line(out,c['upper_floor']['unit_b_entry_interface'],b,gx,gy,gw,gh,'#356883',None,7)
  polygon(out,c['core_polygon'],b,gx,gy,gw,gh,'none','#a76300');polygon(out,c['elevator']['shaft_polygon'],b,gx,gy,gw,gh,COL['elevator'],'#176b78');polygon(out,c['common_lobby']['polygon'],b,gx,gy,gw,gh,COL['lobby'],'#27793c');stair_cut(out,c,level,b,gx,gy,gw,gh)
  tx=x+475;facts=[f"Core {c['core_dimensions'][0]:.2f}×{c['core_dimensions'][1]:.2f}m",f"Lobby gross/net {c['common_lobby']['gross_lobby_area']:.2f}/{c['common_lobby']['net_walkable_lobby_area']:.2f}m²",f"Elevator front {c['elevator_front_clearance_by_level'][level]['front_clear_width']:.2f}×{c['elevator_front_clearance_by_level'][level]['front_clear_depth']:.2f}m"]
  if level=='B1':facts += [f"P-01 path {c['basement']['stall_1_to_core_path']['route_length']:.2f}m",f"P-02 path {c['basement']['stall_2_to_core_path']['route_length']:.2f}m",'PARKING 2/2 PRESERVED']
  if level=='GF':facts += [f"Vehicle / pedestrian {c['ground_floor']['vehicle_entrance_width']:.2f}/{c['ground_floor']['pedestrian_entrance_width']:.2f}m",f"Commercial frontage {c['ground_floor']['commercial_frontage_width']:.2f}m",f"Commercial retained {c['ground_floor']['commercial_retained_area']:.2f}m²",f"Corridor W/L {c['ground_floor']['corridor_width']:.2f}/{c['ground_floor']['corridor_length']:.2f}m",'DIRECT EXTERIOR DISCHARGE']
  if level in ('F1','F2'):facts += [f"Unit A field {c['upper_floor']['unit_a_area']:.2f}m²",f"Unit B field {c['upper_floor']['unit_b_area']:.2f}m²",f"Balance {c['upper_floor']['balance_ratio']:.3f}",'INDEPENDENT UNIT ENTRIES']
  for j,s in enumerate(facts):out.append(text(tx,y+100+j*28,s,12,'bold' if j==0 else 'normal'))

 # Enlarged core detail from the same selected production candidate.
 x,y,w,h=820,900,1555,780;panel(out,'CORE DETAIL — REAL INTERFACES / CUT-PLANE STAIR',x,y,w,h);cb=Polygon(c['core_polygon']).bounds;gx,gy,gw,gh=x+30,y+55,760,670
 polygon(out,c['core_polygon'],cb,gx,gy,gw,gh,'#fff8e9','#a76300');polygon(out,c['common_lobby']['polygon'],cb,gx,gy,gw,gh,COL['lobby'],'#27793c');polygon(out,c['elevator']['shaft_polygon'],cb,gx,gy,gw,gh,COL['elevator'],'#176b78');polygon(out,c['elevator_front_clearance_by_level']['GF']['front_clear_polygon'],cb,gx,gy,gw,gh,'#d9f1f3','#176b78','8 5',.6)
 stair_cut(out,c,'GF',cb,gx,gy,gw,gh);line(out,c['common_lobby']['corridor_interface'],cb,gx,gy,gw,gh,'#6545a0',None,9);line(out,c['common_lobby']['elevator_door_interface'],cb,gx,gy,gw,gh,'#0b5260',None,10);line(out,c['common_lobby']['stair_entry_interface'],cb,gx,gy,gw,gh,'#8c5300',None,10)
 labels=['COMMON LOBBY','ELEVATOR SHAFT','ELEVATOR DOOR','FRONT CLEARANCE','STAIR ENTRY','CORRIDOR INTERFACE','VISIBLE BELOW CUT = SOLID','VISIBLE ABOVE CUT = DASHED','START / ARRIVAL / UP / DOWN'];
 for j,s in enumerate(labels):out.append(text(x+840,y+100+j*34,s,14,'bold' if j<6 else 'normal'))
 out += [text(35,1768,'RENDERER AUTHORITY: PRODUCTION CONTRACT ONLY | FIRE LIMITS: PENDING RULE RESOLUTION | NO STRUCTURE/BIM/IFC',14,'bold'),'</svg>'];return ''.join(out)

def main():
 p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/vertical_core_level_aware_v2_*/PARCEL2_VERTICAL_CORE_LEVEL_AWARE_V2.json'))[-1];v2=json.loads(p.read_text());ctx=v2['context_geometry'];r=VerticalCoreArchitecturalUsabilityV3().resolve(v2,Polygon(ctx['clear_face']),Polygon(ctx['ramp']));r['context_geometry']=ctx;r['source_path']=str(p)
 folder=p.parents[1]/('vertical_core_architectural_usability_v3_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir();jp=folder/'PARCEL2_VERTICAL_CORE_ARCHITECTURAL_USABILITY_V3.json';sp=folder/'PARCEL2_VERTICAL_CORE_ARCHITECTURAL_USABILITY_V3.svg';pp=folder/'PARCEL2_VERTICAL_CORE_ARCHITECTURAL_USABILITY_V3.png';jp.write_text(json.dumps(r,indent=2),encoding='utf-8');sp.write_text(render(r),encoding='utf-8');svg_to_png(sp,pp);print(json.dumps({'json':str(jp),'svg':str(sp),'png':str(pp),'selected':r['report_candidate_id'],'candidates':r['candidate_count'],'hard_valid':r['hard_valid_count']}))
if __name__=='__main__':main()
