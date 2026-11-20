import hashlib,json,subprocess,sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.program_driven_pilot_space_composition_v1 import ProgramDrivenPilotSpaceCompositionV1

def fp(v):return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
def pts(v,s,ox,oy):return ' '.join(f'{ox+x*s:.1f},{oy-y*s:.1f}' for x,y in v)
def poly(v,s,ox,oy,fill,stroke='#334155',opacity=.8,w=1.4):return f'<polygon points="{pts(v,s,ox,oy)}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="{w}"/>'
def line(v,s,ox,oy,stroke,w=2,dash=''):return f'<polyline points="{pts(v,s,ox,oy)}" fill="none" stroke="{stroke}" stroke-width="{w}" {dash}/>'
def text(x,y,v,size=13,color='#17212b',weight='normal'):return f'<text x="{x}" y="{y}" font-family="Arial" font-size="{size}" fill="{color}" font-weight="{weight}">{v}</text>'
COLORS={'residential_storage':'#c4a7e7','mechanical_room':'#f4a261','electrical_room':'#e9c46a','common_wc':'#f7b267','caretaker_unit':'#ef9a9a','guard_room':'#ef9a9a','utility_room':'#b0bec5','refuse_room':'#8d6e63'}

def common(parking):return [
 {'space_type':'parking','required':True,'required_count':parking,'hard_requirement':True,'requirement_source':'user_design_requirement','priority':90},
 {'space_type':'commercial','required':True,'hard_requirement':True,'area_goal':'maximize','expandable':True,'shrinkable':True,'requirement_source':'user_design_requirement','priority':70},
 *[{'space_type':t,'required':True,'hard_requirement':True,'requirement_source':'project_requirement','priority':95} for t in ('stair','elevator','common_lobby')]]
def programs(min_parking):
 optional=lambda t:{'space_type':t,'required':False,'preferred':False,'removable':True,'requirement_source':'unresolved_source'}
 storage={'space_type':'residential_storage','required':True,'required_count':2,'count':2,'preferred_area_per_unit':5.0,'maximum_area_per_unit':6.0,'shrinkable':True,'hard_requirement':True,'requirement_source':'user_design_requirement','priority':60}
 mech={'space_type':'mechanical_room','required':True,'preferred_area':4.0,'shrinkable':True,'hard_requirement':True,'requirement_source':'engineering_assumption','regulatory_status':'pending_rule_resolution','priority':80}
 elec={'space_type':'electrical_room','required':True,'preferred_area':3.0,'shrinkable':True,'hard_requirement':True,'requirement_source':'engineering_assumption','regulatory_status':'pending_rule_resolution','priority':80}
 return {
  'PROGRAM-A':common(3)+[optional(t) for t in ('residential_storage','common_wc','mechanical_room','electrical_room')],
  'PROGRAM-B':common(3)+[storage,mech,{'space_type':'electrical_room','preferred':True,'preferred_area':3.0,'shrinkable':True,'removable':True,'requirement_source':'engineering_assumption'}, {'space_type':'common_wc','preferred':True,'preferred_area':2.7,'shrinkable':True,'removable':True,'requirement_source':'engineering_assumption'}],
  'PROGRAM-C':common(min_parking),
  'PROGRAM-D':common(min_parking)+[{'space_type':'caretaker_unit','preferred':True,'preferred_area':12.0,'shrinkable':True,'removable':True,'requirement_source':'engineering_assumption','regulatory_status':'pending_rule_resolution'}],
  'PROGRAM-E':common(min_parking)+[mech,elec,dict(storage,required=False,preferred=True,hard_requirement=False,removable=True)],
 }

def plan(study,c,ox,oy,s):
 g=c['geometry'];p=study['local_parcel_polygon'];out=[poly(p,s,ox,oy,'#fff','#111827',1,2),poly([[p[0][0],-2],[p[1][0],-2],[p[1][0],0],[p[0][0],0]],s,ox,oy,'#cbd5e1')]
 for cp in c['commercial_polygons']:out.append(poly(cp,s,ox,oy,'#bfe3b5','#39833d',.85))
 out += [poly(g['drive_lane'],s,ox,oy,'#d7dde3','#64748b',.7),poly(g['maneuvering_field'],s,ox,oy,'#b8c4d0','#334155',.7)]
 for stall in g['parking_stalls']:out.append(poly(stall['polygon'],s,ox,oy,'#8ecae6','#17658a',.85))
 out += [poly(g['core']['stair'],s,ox,oy,'#d3b5e5','#70408c'),poly(g['core']['elevator'],s,ox,oy,'#f3c2d1','#9d3155'),poly(g['core']['lobby'],s,ox,oy,'#f5dda8','#9a6b12')]
 for space in c['generated_program_spaces']:out.append(poly(space['polygon'],s,ox,oy,COLORS.get(space['space_type'],'#ddd'),'#5b3a29',.9))
 for r in c['unallocated_residual_polygons']:out.append(poly(r,s,ox,oy,'#eeeeee','#888',.45))
 out += [line(g['vehicle_entrance'],s,ox,oy,'#087454',6),line(g['pedestrian_entrance'],s,ox,oy,'#d49b00',6),line(g['commercial_storefront'],s,ox,oy,'#39833d',6)]
 return out
def label_rows(c):
 return [f'PARKING {c["parking_generated_count"]} / {c["parking_required_count"]}',f'COMMERCIAL {c["commercial_area"]:.1f} m² | frontage {c["commercial_frontage"]:.2f} m',f'STORAGE {c["storage_generated_count"]} / {c["storage_required_count"]} — {c["storage_total_area"]:.1f} m²',f'MECHANICAL {c["mechanical_room_generated"]} | ELECTRICAL {c["electrical_room_generated"]}',f'WC {c["common_wc_generated"]} | CARETAKER {c["caretaker_unit_generated"]}',f'CIRCULATION {c["circulation_area"]:.1f} m² | RESIDUAL {c["residual_unallocated_area"]:.1f} m²',f'COMPLIANCE: {c["program_compliance_status"]}']
def candidate_svg(study,c):
 out=['<svg xmlns="http://www.w3.org/2000/svg" width="1450" height="920"><rect width="100%" height="100%" fill="#f7f8f6"/>']+plan(study,c,70,790,34);out += [text(500,55,c['candidate_id'],21,'#17212b','bold')]
 for i,row in enumerate(label_rows(c)):out.append(text(500,100+i*32,row,16,'#b91c1c' if ('SHORTFALL' in row or (i==6 and c['hard_requirement_failures'])) else '#17212b','bold' if i in (0,6) else 'normal'))
 y=350
 for reason in c['hard_requirement_failures']:out.append(text(500,y,f'WARNING — {reason}',15,'#b91c1c','bold'));y+=25
 out += [text(500,500,'GREEN commercial | BLUE parking | PURPLE stair | PINK elevator',14),text(500,528,'ORANGE mechanical/WC | GOLD electrical | RED caretaker | GREY unallocated',14),text(500,575,'Vehicle maneuvering remains pending_vehicle_model_validation.',14,'#9a3412','bold'),text(500,605,'NO FINAL SCENARIO B WINNER',16,'#17212b','bold'),'</svg>'];return ''.join(out)
def comparison(studies):
 out=['<svg xmlns="http://www.w3.org/2000/svg" width="1900" height="940"><rect width="100%" height="100%" fill="#f7f8f6"/>',text(35,38,'REAL PARCEL 2 — PROGRAM-DRIVEN PILOT COMPARISON — HUMAN REVIEW',23,'#17212b','bold')]
 for i,(pid,study) in enumerate(studies.items()):
  c=study['human_review_candidates'][0];ox=35+i*370;out+=plan(study,c,ox,485,18);out.append(text(ox,535,pid,17,'#17212b','bold'))
  for j,row in enumerate(label_rows(c)):out.append(text(ox,565+j*24,row,12,'#b91c1c' if j==6 and c['hard_requirement_failures'] else '#17212b','bold' if j in (0,6) else 'normal'))
 out += [text(35,780,'Engineering assumptions remain pending_rule_resolution. Parking independently usable status is not proven.',14,'#9a3412','bold'),text(35,810,'No final Scenario B winner selected.',16,'#17212b','bold'),'</svg>'];return ''.join(out)
def png(svg,pngfile,profile,width=1450):
 chrome=Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
 if chrome.exists():subprocess.run([str(chrome),'--headless','--no-sandbox','--disable-gpu',f'--user-data-dir={profile}','--hide-scrollbars',f'--window-size={width},940',f'--screenshot={pngfile}',svg.as_uri()],check=True)
def main():
 bp=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];rp=sorted(bp.parent.glob('program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json'))[-1];b=json.loads(bp.read_text());a=json.loads(rp.read_text())['baseline_scenario_a'];before=fp(deepcopy(b));engine=ProgramDrivenPilotSpaceCompositionV1();studies={pid:engine.resolve(b['site'],b['requirements'],a,reqs,pid) for pid,reqs in programs(int(b['requirements']['parking']['minimum_count'])).items()};assert fp(b)==before
 folder=bp.parent/('program_driven_pilot_space_composition_v1_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir();outputs=[]
 for pid,study in studies.items():
  (folder/f'{pid}_CONTRACT.json').write_text(json.dumps(study,indent=2),encoding='utf-8')
  for c in study['human_review_candidates']:
   svg=folder/f'{c["candidate_id"]}.svg';preview=svg.with_suffix('.png');svg.write_text(candidate_svg(study,c),encoding='utf-8');png(svg,preview,folder/f'.chrome_{c["candidate_id"]}');outputs.append(str(svg))
 comp=folder/'PARCEL2_PROGRAM_A_TO_E_COMPARISON.svg';comp.write_text(comparison(studies),encoding='utf-8');cp=comp.with_suffix('.png');png(comp,cp,folder/'.chrome_comparison',1900)
 summary={'contract':'ProgramDrivenPilotSpaceCompositionV1','folder':str(folder),'programs':{k:{'candidate_count':v['candidate_count'],'compliant_count':v['program_compliant_candidate_count'],'review_ids':v['human_review_candidate_ids']} for k,v in studies.items()},'svg_outputs':outputs,'comparison_svg':str(comp),'comparison_png':str(cp) if cp.exists() else None,'final_selection_performed':False,'program_changed':False,'basement_deleted':False,'basement_removal_approved':False};(folder/'PARCEL2_PROGRAM_DRIVEN_COMPOSITION_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
if __name__=='__main__':main()
