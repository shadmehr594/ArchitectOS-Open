import json,sys
from datetime import datetime
from pathlib import Path
from shapely.geometry import Polygon
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.vertical_core_commercial_quality_checkpoint_v1 import VerticalCoreCommercialQualityCheckpointV1
from tools.generate_parcel2_basement_v2_design import text,svg_to_png

def point(p,b,x,y,w,h):
 x0,y0,x1,y1=b;s=min(w/(x1-x0),h/(y1-y0));return x+(w-(x1-x0)*s)/2+(p[0]-x0)*s,y+(h-(y1-y0)*s)/2+(y1-p[1])*s
def pts(p,b,x,y,w,h):return ' '.join(f'{a:.1f},{d:.1f}' for a,d in (point(q,b,x,y,w,h) for q in p))
def poly(out,p,b,x,y,w,h,fill,stroke='#344850',op=1,dash=None):
 ds=f' stroke-dasharray="{dash}"' if dash else '';out.append(f'<polygon points="{pts(p,b,x,y,w,h)}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="4"{ds}/>')
def panel(out,title,x):out += [f'<rect x="{x}" y="95" width="740" height="1280" rx="10" fill="white" stroke="#8398a3" stroke-width="2"/>',text(x+20,130,title,19,'bold')]
def candidate_panel(out,c,ctx,x,title):
 panel(out,title,x);b=Polygon(ctx['clear_face']).bounds;gx,gy,gw,gh=x+30,160,390,850;poly(out,ctx['clear_face'],b,gx,gy,gw,gh,'#eef1ef');poly(out,ctx['ramp'],b,gx,gy,gw,gh,'#eaa2b2','#a61734');
 for p in c['ground_floor']['commercial_space_polygons']:poly(out,p,b,gx,gy,gw,gh,'#f1d17f','#9b6500',.72)
 poly(out,c['ground_floor']['pedestrian_corridor'],b,gx,gy,gw,gh,'#cabce8','#6545a0');poly(out,c['core_polygon'],b,gx,gy,gw,gh,'#f5d69a','#a76300',.65)
 q=c['commercial_spatial_quality'];n=q['neck_and_tail'];
 if n['neck_polygon']:poly(out,n['neck_polygon'],b,gx,gy,gw,gh,'#ff796f','#ba1524',.55,'8 5')
 if n['tail_polygon']:poly(out,n['tail_polygon'],b,gx,gy,gw,gh,'#ffc46b','#b56800',.34,'9 6')
 if q['largest_inscribed_usable_field']:poly(out,q['largest_inscribed_usable_field'],b,gx,gy,gw,gh,'none','#176f37',1,'10 6')
 facts=[f"ID {c['candidate_id']}",f"Area {q['commercial_total_area']:.2f}m² | largest {q['largest_contiguous_commercial_area']:.2f}m²",f"Storefront {q['effective_storefront_width']:.2f}m | avg depth {q['average_commercial_depth']:.2f}m",f"Neck W/L {q['neck_width']:.2f}/{q['neck_length']:.2f}m",f"Rear tail {n['tail_area']:.2f}m² ({n['tail_area_ratio']:.1%})",f"Narrow strip {q['narrow_strip_area']:.2f}m²",f"Compactness {q['commercial_space_compactness']:.3f} | convexity {q['commercial_convexity_ratio']:.3f}",f"Largest usable rectangle {q['usable_rectangular_field_area']:.2f}m²",f"Corridor {c['ground_floor']['corridor_length']:.2f}m",f"STATUS {q['architectural_quality_status']}"]
 for i,s in enumerate(facts):out.append(text(x+440,190+i*31,s,12,'bold' if i in (0,9) else 'normal','#a61734' if i==9 else '#14242e'))
 yy=1050;out.append(text(x+25,yy,'ARCHITECTURAL QUALITY FAILURES',13,'bold','#a61734'))
 for i,s in enumerate(q['architectural_quality_failures']):out.append(text(x+35,yy+27+i*24,s,11,'normal','#a61734'))
def render(r):
 ctx=r['context_geometry'];cur=r['current_diagnostic_counterexample'];best=r['best_local_commercial_quality_candidate'];a=r['whole_building_tradeoff_advisor'];out=['<svg xmlns="http://www.w3.org/2000/svg" width="2300" height="1450"><rect width="100%" height="100%" fill="#f7f6f1"/>',text(35,42,'REAL PARCEL 2 — COMMERCIAL SPATIAL QUALITY + WHOLE-BUILDING TRADEOFF',27,'bold'),text(35,72,'AREA IS NOT ARCHITECTURAL USABILITY | BASEMENT DECISION NOT CHANGED | HUMAN DECISION REQUIRED',14,'bold','#a61734')];candidate_panel(out,cur,ctx,25,'A — HUMAN-REJECTED DIAGNOSTIC COUNTEREXAMPLE');candidate_panel(out,best,ctx,780,'B — BEST LOCAL COMMERCIAL-SHAPE CANDIDATE');panel(out,'C — PROGRAM TRADEOFF ADVISOR',1535);x=1560;lines=['SCENARIO A — BASEMENT PARKING + RAMP + CORE',f"Parking: {a['scenario_a']['parking_capacity']}",f"Commercial: {a['scenario_a']['ground_floor_commercial_area']:.2f}m²",f"Commercial quality: {a['scenario_a']['ground_floor_commercial_quality']}",f"Ramp footprint: {a['scenario_a']['ramp_area_consumption']:.2f}m²",f"Excavation: {a['scenario_a']['basement_excavation_requirement']}",'','SCENARIO B — GROUND-FLOOR PARKING / NO RAMP','NOT DESIGNED — FIRST-ORDER ADVISORY ONLY',f"Parking: {a['scenario_b']['parking_capacity']}",f"Ramp area potentially released: {a['scenario_b']['ramp_area_potentially_released']:.2f}m²",f"Excavation: {a['scenario_b']['basement_excavation_requirement']}",'','MEASURED-EVIDENCE ADVISORY',a['advisory'],'','PROGRAM CHANGED: FALSE','BASEMENT DELETED: FALSE','HUMAN DECISION REQUIRED: TRUE']
 for i,s in enumerate(lines):
  if len(s)<88:out.append(text(x,180+i+i*38,s,13,'bold' if s.isupper() or s.startswith('SCENARIO') else 'normal','#a61734' if 'FALSE' in s or 'REQUIRED' in s else '#14242e'))
  else:
   words=s.split();row='';k=0
   for word in words:
    if len(row)+len(word)>72:out.append(text(x,180+(i+k)*38,row,12));row=word+' ';k+=1
    else:row+=word+' '
   out.append(text(x,180+(i+k)*38,row,12))
 out += [text(35,1425,'RENDERER: PRODUCTION CONTRACT ONLY | NO PARKING REDESIGN | NO PROGRAM CHANGE | NO STRUCTURE/BIM/IFC',14,'bold'),'</svg>'];return ''.join(out)
def main():
 p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/vertical_core_architectural_usability_v3_*/PARCEL2_VERTICAL_CORE_ARCHITECTURAL_USABILITY_V3.json'))[-1];v=json.loads(p.read_text());ctx=v['context_geometry'];r=VerticalCoreCommercialQualityCheckpointV1().resolve(v,Polygon(ctx['clear_face']),Polygon(ctx['ramp']));r['context_geometry']=ctx;r['source_path']=str(p);folder=p.parents[1]/('commercial_spatial_quality_tradeoff_v1_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir();jp=folder/'PARCEL2_COMMERCIAL_SPATIAL_QUALITY_TRADEOFF_V1.json';sp=folder/'PARCEL2_COMMERCIAL_SPATIAL_QUALITY_TRADEOFF_V1.svg';pp=folder/'PARCEL2_COMMERCIAL_SPATIAL_QUALITY_TRADEOFF_V1.png';jp.write_text(json.dumps(r,indent=2),encoding='utf-8');sp.write_text(render(r),encoding='utf-8');svg_to_png(sp,pp);print(json.dumps({'json':str(jp),'svg':str(sp),'png':str(pp),'current':r['current_rejected_candidate_id'],'best_local':r['best_local_commercial_quality_candidate']['candidate_id'],'quality_valid':r['quality_valid_count']}))
if __name__=='__main__':main()
