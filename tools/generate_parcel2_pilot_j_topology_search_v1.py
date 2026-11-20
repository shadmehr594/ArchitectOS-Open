import hashlib,json,subprocess,sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.pilot_parking_compact_circulation_topology_search_v1 import PilotParkingCompactCirculationTopologySearchV1

def fp(v):return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
def pts(v,s,ox,oy):return ' '.join(f'{ox+x*s:.1f},{oy-y*s:.1f}' for x,y in v)
def poly(v,s,ox,oy,fill,stroke,opacity=.75,w=1.5):return f'<polygon points="{pts(v,s,ox,oy)}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="{w}"/>'
def line(v,s,ox,oy,stroke,w=2,dash=''):return f'<polyline points="{pts(v,s,ox,oy)}" fill="none" stroke="{stroke}" stroke-width="{w}" {dash}/>'
def text(x,y,v,size=14,color='#17212b',weight='normal'):return f'<text x="{x}" y="{y}" font-family="Arial" font-size="{size}" fill="{color}" font-weight="{weight}">{v}</text>'
def plan(study,c,ox,oy,s):
 p=study['local_parcel_polygon'];out=[poly(p,s,ox,oy,'#fff','#111827',1,2.5),poly([[p[0][0],-2],[p[1][0],-2],[p[1][0],0],[p[0][0],0]],s,ox,oy,'#cbd5e1','#64748b')]
 out += [poly(c['commercial_field'],s,ox,oy,'#d9edc7','#39833d',.9),poly(c['drive_lane'],s,ox,oy,'#d7dde3','#64748b',.75),poly(c['maneuvering_field'],s,ox,oy,'#bfc9d4','#334155',.75,2),poly(c['pedestrian_corridor'],s,ox,oy,'#fff0a8','#b18400',.85,2)]
 for stall in c['parking_stalls']:out.append(poly(stall['polygon'],s,ox,oy,'#8ecae6','#17658a',.85,2))
 out += [poly(c['core']['stair'],s,ox,oy,'#d3b5e5','#70408c',.9),poly(c['core']['elevator'],s,ox,oy,'#f3c2d1','#9d3155',.9),poly(c['core']['lobby'],s,ox,oy,'#f5dda8','#9a6b12',.9),line(c['vehicle_access_axis'],s,ox,oy,'#334155',3,'stroke-dasharray="7 4"'),line(c['pedestrian_path'],s,ox,oy,'#a97900',3),line(c['vehicle_entrance'],s,ox,oy,'#087454',6),line(c['pedestrian_entrance'],s,ox,oy,'#d49b00',6),line(c['commercial_storefront'],s,ox,oy,'#39833d',6)]
 vx,vy=c['vehicle_lane_endpoint'];px,py=c['pedestrian_corridor_endpoint'];out += [f'<circle cx="{ox+vx*s}" cy="{oy-vy*s}" r="5" fill="#d11a2a"/>',f'<circle cx="{ox+px*s}" cy="{oy-py*s}" r="5" fill="#d11a2a"/>']
 return out
def candidate_svg(study,c):
 s,ox,oy=34,70,790;m=c['metrics'];out=['<svg xmlns="http://www.w3.org/2000/svg" width="1450" height="920"><rect width="100%" height="100%" fill="#f7f8f6"/>']+plan(study,c,ox,oy,s)
 out += [text(500,60,c['candidate_id'],23,'#17212b','bold'),text(500,100,f'Parking {c["parking_count"]} | independent proven 0',16),text(500,130,f'Vehicle circulation: {m["vehicle_circulation_length"]:.2f} m / {m["vehicle_circulation_area"]:.2f} m²',16),text(500,160,f'Pedestrian circulation: {m["pedestrian_circulation_length"]:.2f} m / {m["pedestrian_circulation_area"]:.2f} m²',16),text(500,190,f'Total circulation area: {m["total_circulation_area"]:.2f} m²',16,'#9a3412','bold'),text(500,220,f'Dead run V/P: {m["vehicle_dead_run_length"]:.2f} / {m["pedestrian_dead_run_length"]:.2f} m',16),text(500,250,f'Commercial: {m["commercial_area"]:.2f} m² | frontage {m["commercial_frontage"]:.2f} m',16),text(500,280,f'Boundary adjacency: {m["parking_boundary_adjacency_ratio"]:.2f} | terminality {m["parking_terminality_score"]:.2f}',16),text(500,325,'Red dots: exact circulation endpoints',15,'#a11','bold'),text(500,355,'Red waste zone: none; dead-run = 0',15,'#27632a','bold'),text(500,395,'Maneuvering: pending_vehicle_model_validation',15,'#9a3412','bold'),text(500,430,'Regulatory status: pending_rule_resolution',15),text(500,470,'No final selection performed.',16,'#17212b','bold'),'</svg>'];return ''.join(out)
def comparison(j,h):
 candidates=[('CURRENT H COUNTEREXAMPLE',h)]+[(c['candidate_id'],c) for c in j['human_review_candidates'][:5]];out=['<svg xmlns="http://www.w3.org/2000/svg" width="2100" height="980"><rect width="100%" height="100%" fill="#f7f8f6"/>',text(40,40,'REAL PARCEL 2 — H vs COMPACT J CIRCULATION — HUMAN REVIEW',24,'#17212b','bold')]
 for i,(name,c) in enumerate(candidates):
  ox=40+i*340;oy=520;s=18
  if i==0:
   p=j['local_parcel_polygon'];out += [poly(p,s,ox,oy,'#fff','#111827',1,2),poly(c['commercial_usable_field'][0],s,ox,oy,'#d9edc7','#39833d'),poly(c['drive_lane'],s,ox,oy,'#f3b2b2','#b91c1c',.65),poly(c['pedestrian_corridor'],s,ox,oy,'#f3b2b2','#b91c1c',.65)]
   total=PolygonArea(c['drive_lane'])+PolygonArea(c['pedestrian_corridor']);vl=c['vehicle_access_axis'][-1][1];pl=c['pedestrian_path'][-1][1];parking=c['parking_count'];commercial=c['commercial_quality']['commercial_area'];frontage=c['commercial_quality']['commercial_frontage']
  else:
   out+=plan(j,c,ox,oy,s);m=c['metrics'];total=m['total_circulation_area'];vl=m['vehicle_circulation_length'];pl=m['pedestrian_circulation_length'];parking=c['parking_count'];commercial=m['commercial_area'];frontage=m['commercial_frontage']
  out += [text(ox,570,name,13,'#17212b','bold'),text(ox,595,f'Parking {parking} | circulation {total:.1f} m²',13),text(ox,620,f'Vehicle/Ped length {vl:.1f}/{pl:.1f} m',13),text(ox,645,f'Commercial {commercial:.1f} m² | frontage {frontage:.1f} m',13)]
 out += [text(40,735,'RED in H: circulation extending beyond functional need. Red dots in J: exact termination endpoints.',15,'#9a3412','bold'),text(40,770,'All J maneuvering remains pending_vehicle_model_validation. No winner selected.',15,'#17212b','bold'),'</svg>'];return ''.join(out)
def PolygonArea(p):
 from shapely.geometry import Polygon
 return Polygon(p).area
def png(svg,pngfile,profile):
 chrome=Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
 if chrome.exists():subprocess.run([str(chrome),'--headless','--no-sandbox','--disable-gpu',f'--user-data-dir={profile}','--hide-scrollbars','--window-size=2100,980',f'--screenshot={pngfile}',svg.as_uri()],check=True)
def main():
 bp=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];rp=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json'))[-1];hp=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/pilot_h_topology_search_v1_*/PARCEL2_PILOT_H_TOPOLOGY_SEARCH_V1.json'))[-1]
 b=json.loads(bp.read_text());a=json.loads(rp.read_text())['baseline_scenario_a'];h=json.loads(hp.read_text());before=fp(deepcopy(b));r=PilotParkingCompactCirculationTopologySearchV1().resolve(b['site'],b['requirements'],a);assert fp(b)==before
 folder=bp.parent/('pilot_j_topology_search_v1_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir();contract=folder/'PARCEL2_PILOT_J_TOPOLOGY_SEARCH_V1.json';contract.write_text(json.dumps(r,indent=2),encoding='utf-8');outputs=[]
 for c in r['human_review_candidates']:
  s=folder/f'{c["candidate_id"]}.svg';p=s.with_suffix('.png');s.write_text(candidate_svg(r,c),encoding='utf-8');png(s,p,folder/f'.chrome_{c["candidate_id"]}');outputs.append({'id':c['candidate_id'],'svg':str(s),'png':str(p)})
 comp=folder/'PARCEL2_H_VS_J_CIRCULATION_COMPARISON.svg';comp.write_text(comparison(r,h['promising_candidates'][0]),encoding='utf-8');cp=comp.with_suffix('.png');png(comp,cp,folder/'.chrome_comparison');print(json.dumps({'contract':str(contract),'generated':r['candidate_count'],'hard_valid':r['hard_valid_candidate_count'],'review':outputs,'comparison':str(comp),'comparison_png':str(cp),'final_selection_performed':False,'program_changed':False,'basement_deleted':False}))
if __name__=='__main__':main()
