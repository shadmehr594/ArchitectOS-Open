import hashlib,json,subprocess,sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.residential_floor_access_and_daylight_topology_v1 import ResidentialFloorAccessAndDaylightTopologyV1
def fp(v):return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
def pts(v,s,ox,oy):return ' '.join(f'{ox+x*s:.1f},{oy-y*s:.1f}' for x,y in v)
def poly(v,s,ox,oy,fill,stroke='#334155',opacity=.78,w=1.5):return f'<polygon points="{pts(v,s,ox,oy)}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="{w}"/>'
def line(v,s,ox,oy,stroke,w=2,dash=''):return f'<polyline points="{pts(v,s,ox,oy)}" fill="none" stroke="{stroke}" stroke-width="{w}" {dash}/>'
def text(x,y,v,size=13,color='#17212b',weight='normal'):return f'<text x="{x}" y="{y}" font-family="Arial" font-size="{size}" fill="{color}" font-weight="{weight}">{v}</text>'
def mark(x,y,label,s,ox,oy,color='#111827'):return f'<circle cx="{ox+x*s}" cy="{oy-y*s}" r="4" fill="{color}"/>'+text(ox+x*s+6,oy-y*s-5,label,11,color,'bold')
def plan(study,c,ox,oy,s):
 p=study['local_parcel_polygon'];out=[poly(p,s,ox,oy,'#fff','#111827',1,2.5),poly([[p[0][0],-2],[p[1][0],-2],[p[1][0],0],[p[0][0],0]],s,ox,oy,'#cbd5e1','#64748b')]
 out += [text(ox,oy+42,'SOUTH — 10 m ROAD',12,'#334155','bold'),text(ox,oy-20*s,'NORTH PRIVATE NEIGHBOR — NO OPENING',10,'#b91c1c','bold'),text(ox-18,oy-9*s,'WEST',10,'#b91c1c','bold')]
 colors=['#bfe3b5','#b7d7f0']
 for i,u in enumerate(c['unit_envelopes']):
  out.append(poly(u['polygon'],s,ox,oy,colors[i],['#39833d','#17658a'][i],.72,2));x,y=u['entry_point'];out.append(mark(x,y,f'U{i+1} ENTRY',s,ox,oy,'#7c3aed'))
 out += [poly(c['lightwell']['polygon'],s,ox,oy,'#d9f4ff','#0284c7',.9,2.5),poly(c['common_lobby_polygon'],s,ox,oy,'#f5dda8','#9a6b12',.9),poly(c['stair']['landing_geometry'],s,ox,oy,'#c4a7e7','#70408c',.9),poly(c['elevator']['polygon'],s,ox,oy,'#f3c2d1','#9d3155',.9),poly(c['elevator']['elevator_front_clear_zone'],s,ox,oy,'#ffe8a3','#d97706',.45)]
 for path in c['common_access_paths']:out.append(line(path,s,ox,oy,'#a97900',3,'stroke-dasharray="5 3"'))
 for i,t in enumerate(c['terraces']):out.append(poly(t['terrace_polygon'],s,ox,oy,'#80cbc4','#00796b',.9,2))
 st=c['stair'];out += [mark(*st['stair_start_point'],'STAIR START / UP',s,ox,oy,'#6b21a8'),mark(*st['stair_end_point'],'STAIR END / DOWN',s,ox,oy,'#6b21a8')]
 lx0,ly0,lx1,ly1=min(x for x,y in c['lightwell']['polygon']),min(y for x,y in c['lightwell']['polygon']),max(x for x,y in c['lightwell']['polygon']),max(y for x,y in c['lightwell']['polygon']);out += [text(ox+lx0*s,oy-(ly0+(ly1-ly0)/2)*s,f'LIGHTWELL {c["lightwell"]["area"]:.1f} m² / min {c["lightwell"]["minimum_width"]:.1f} m',10,'#0369a1','bold')]
 return out
def rows(c):
 u1,u2=c['unit_envelopes'][0]['metrics'],c['unit_envelopes'][1]['metrics'];return [c['candidate_id'],f'Unit areas {c["unit_1_area"]:.1f} / {c["unit_2_area"]:.1f} m² | balance {c["unit_area_balance_ratio"]:.2f}',f'Aspect {u1["aspect_ratio"]:.2f} / {u2["aspect_ratio"]:.2f} | corridor {u1["corridor_likeness_score"]:.2f} / {u2["corridor_likeness_score"]:.2f}',f'Common {c["common_corridor_area"]:.1f} m² / paths {c["common_access_length"]:.1f} m',f'Terraces {c["unit_1_terrace_area"]:.1f} / {c["unit_2_terrace_area"]:.1f} m²',f'Lightwell {c["lightwell"]["area"]:.1f} m² / {c["lightwell"]["minimum_width"]:.1f} m',f'Daylight {c["daylight_topology_status"]}',f'Privacy {c["privacy_status"]}',f'Penalties: {", ".join(c["architectural_quality_penalties"]) or "none"}']
def candidate_svg(study,c):
 out=['<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="940"><rect width="100%" height="100%" fill="#f7f8f6"/>']+plan(study,c,80,790,32)
 for i,r in enumerate(rows(c)):out.append(text(520,55+i*31,r,20 if i==0 else 14,'#b91c1c' if i==8 and c['architectural_quality_penalties'] else '#17212b','bold' if i in (0,8) else 'normal'))
 out += [text(520,380,'GREEN UNIT 1 | BLUE UNIT 2 | CYAN LIGHTWELL | TEAL TERRACE',14),text(520,410,'PURPLE STAIR/LANDING | PINK ELEVATOR | GOLD COMMON',14),text(520,455,'NO OPENING NORTH / WEST',15,'#b91c1c','bold'),text(520,490,'No rooms or final windows generated.',14,'#17212b','bold'),text(520,525,'HUMAN REVIEW — NO FINAL TOPOLOGY',16,'#17212b','bold'),'</svg>'];return ''.join(out)
def comparison(study):
 best=[next(c for c in study['human_review_candidates'] if c['split_family']==f) for f in ('R-EW','R-NS','R-HYBRID')];out=['<svg xmlns="http://www.w3.org/2000/svg" width="1700" height="960"><rect width="100%" height="100%" fill="#f7f8f6"/>',text(35,38,'REAL PARCEL 2 — RESIDENTIAL ACCESS / DAYLIGHT TOPOLOGIES — HUMAN REVIEW',23,'#17212b','bold')]
 for i,c in enumerate(best):
  ox=45+i*550;out+=plan(study,c,ox,500,20)
  for j,r in enumerate(rows(c)[:6]+[f'South frontage U1/U2 {c["south_frontage_distribution"]["south_frontage_unit_1"]:.1f}/{c["south_frontage_distribution"]["south_frontage_unit_2"]:.1f} m',f'Future rooms: {c["future_room_planning_potential"]}']):out.append(text(ox,555+j*24,r,12,'#17212b','bold' if j==0 else 'normal'))
 out += [text(35,800,'EW exposes corridor-like depth; NS depends on internal daylight/terrace; Hybrid tests stepped balance.',14,'#9a3412','bold'),text(35,830,'No final topology selected. Exact Minab page references remain pending source-document attachment.',14,'#b91c1c','bold'),'</svg>'];return ''.join(out)
def png(svg,pngfile,profile,width=1500):
 chrome=Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
 if chrome.exists():subprocess.run([str(chrome),'--headless','--no-sandbox','--disable-gpu',f'--user-data-dir={profile}','--hide-scrollbars',f'--window-size={width},960',f'--screenshot={pngfile}',svg.as_uri()],check=True)
def main():
 bp=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];root=bp.parent;rp=sorted(root.glob('program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json'))[-1];pp=sorted(root.glob('program_driven_pilot_space_composition_v1_*/PROGRAM-A_CONTRACT.json'))[-1];b=json.loads(bp.read_text());a=json.loads(rp.read_text())['baseline_scenario_a'];pilot=json.loads(pp.read_text())['human_review_candidates'][0];before=fp((b,a,pilot));r=ResidentialFloorAccessAndDaylightTopologyV1().resolve(b['site'],a,pilot,{'allowed_floor_count':5});assert before==fp((b,a,pilot))
 folder=root/('residential_floor_access_daylight_topology_v1_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir();contract=folder/'PARCEL2_RESIDENTIAL_FLOOR_ACCESS_DAYLIGHT_TOPOLOGY_V1.json';contract.write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf-8');outputs=[]
 for c in r['human_review_candidates']:
  svg=folder/f'{c["candidate_id"]}.svg';preview=svg.with_suffix('.png');svg.write_text(candidate_svg(r,c),encoding='utf-8');png(svg,preview,folder/f'.chrome_{c["candidate_id"]}');outputs.append({'candidate_id':c['candidate_id'],'svg':str(svg),'png':str(preview) if preview.exists() else None})
 comp=folder/'PARCEL2_RESIDENTIAL_EW_NS_HYBRID_COMPARISON.svg';comp.write_text(comparison(r),encoding='utf-8');cp=comp.with_suffix('.png');png(comp,cp,folder/'.chrome_comparison',1700);print(json.dumps({'contract':str(contract),'candidates':r['candidate_count'],'hard_valid':r['hard_valid_candidate_count'],'review':outputs,'comparison_svg':str(comp),'comparison_png':str(cp) if cp.exists() else None,'final_selection_performed':False,'program_changed':False,'basement_deleted':False}))
if __name__=='__main__':main()
