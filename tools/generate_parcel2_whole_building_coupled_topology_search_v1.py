import hashlib,json,subprocess,sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.whole_building_coupled_topology_search_v1 import WholeBuildingCoupledTopologySearchV1
from tools.generate_parcel2_residential_floor_access_daylight_topology_v1 import poly,line,text
DEFS='<defs><pattern id="residual" width="8" height="8" patternUnits="userSpaceOnUse"><path d="M0 8L8 0" stroke="#dc2626" stroke-width="1"/></pattern></defs>'
def fp(v):return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
def label_polygon(p,label,s,ox,oy,color='#17212b'):
 xs=[q[0] for q in p];ys=[q[1] for q in p];return text(ox+s*sum(xs)/len(xs)-28,oy-s*sum(ys)/len(ys),label,9,color,'bold')
def ground(c,ox,oy,s):
 g=c['ground_floor'];out=[]
 for forbidden in c.get('vehicle_forbidden_envelope',[]):out += [poly(forbidden,s,ox,oy,'#fecaca','#dc2626',.28,2),label_polygon(forbidden,'VEHICLE FORBIDDEN',s,ox,oy,'#991b1b')]
 for commercial in g.get('commercial_polygons') or ([g['commercial_polygon']] if g['commercial_polygon'] else []):out += [poly(commercial,s,ox,oy,'#bfe3b5','#39833d',1,2),label_polygon(commercial,'COMMERCIAL',s,ox,oy,'#27632a')]
 out += [poly(g['drive_lane'],s,ox,oy,'#d6d3d1','#57534e',1,1.5),poly(g['maneuvering_field'],s,ox,oy,'#fde68a','#b45309',.8,2)]
 if g.get('vehicle_circulation_field'):out += [poly(g['vehicle_circulation_field'],s,ox,oy,'#fed7aa','#c2410c',.35,3),label_polygon(g['vehicle_circulation_field'],'FULL VEHICLE CIRCULATION FIELD',s,ox,oy,'#9a3412')]
 for i,p in enumerate(g['parking_stalls']):out += [poly(p,s,ox,oy,'#bfdbfe','#1d4ed8',1,2),label_polygon(p,f'P-{i+1}',s,ox,oy,'#1d4ed8')]
 for p in g.get('swept_path',[]):out += [poly(p,s,ox,oy,'#fb923c','#c2410c',.16,1)]
 for p in g.get('vehicle_movement',{}).get('stall_paths',[]):
  if p.get('center_trajectory'):out += [line(p['center_trajectory'],s,ox,oy,'#9a3412',2)]
 if g.get('vehicle_access_path'):out += [line(g['vehicle_access_path'],s,ox,oy,'#57534e',3,'stroke-dasharray="4 3"')]
 out += [poly(g['core']['stair'],s,ox,oy,'#c4a7e7','#70408c',1,2),poly(g['core']['elevator'],s,ox,oy,'#f3c2d1','#9d3155',1,2),poly(g['core']['lobby'],s,ox,oy,'#f5dda8','#9a6b12',1,2)]
 if g.get('pedestrian_path'):out += [line(g['pedestrian_path'],s,ox,oy,'#7c3aed',3,'stroke-dasharray="7 4"')]
 if g.get('pedestrian_entrance'):out += [line(g['pedestrian_entrance'],s,ox,oy,'#4c1d95',6)]
 if g.get('maneuvering_clear_square'):
  out += [poly(g['maneuvering_clear_square'],s,ox,oy,'none','#b45309',1.5,3),label_polygon(g['maneuvering_clear_square'],'CLEAR 4.5 x 4.5 m',s,ox,oy,'#92400e')]
 for p in g['unallocated_polygons']:out += [poly(p,s,ox,oy,'url(#residual)','#dc2626',1,1),label_polygon(p,'RESIDUAL',s,ox,oy,'#b91c1c')]
 role_fill={'common_service':'#ddd6fe','commercially_nonviable_residual':'url(#residual)','vehicle_circulation':'#fed7aa','commercial_viable':'#bfe3b5'}
 for item in g.get('architectural_space_roles',{}).get('spaces',[]):out += [poly(item['polygon'],s,ox,oy,role_fill.get(item['role'],'#e5e7eb'),'#7f1d1d',.35,1),label_polygon(item['polygon'],item['role'].upper(),s,ox,oy,'#7f1d1d')]
 return out
def residential(c,ox,oy,s):
 r=c['residential_floor'];out=[]
 if not r.get('candidate'):
  out += [poly(c['core']['polygon'],s,ox,oy,'#c4a7e7','#70408c',1,2),text(ox,oy-180,'RESIDENTIAL SPLIT NOT HARD-VALID',13,'#b91c1c','bold')];return out
 q=r['candidate'];colors=['#bfe3b5','#b7d7f0']
 for i,u in enumerate(q['unit_envelopes']):out += [poly(u['polygon'],s,ox,oy,colors[i],['#39833d','#17658a'][i],1,2),label_polygon(u['polygon'],f'UNIT {i+1}',s,ox,oy)]
 out += [poly(q['shared_daylight_court']['court_polygon'],s,ox,oy,'#d9f4ff','#0284c7',1,2),label_polygon(q['shared_daylight_court']['court_polygon'],'COURT',s,ox,oy,'#0284c7'),poly(c['core']['stair'],s,ox,oy,'#c4a7e7','#70408c',1,2),poly(c['core']['elevator'],s,ox,oy,'#f3c2d1','#9d3155',1,2),poly(c['core']['lobby'],s,ox,oy,'#f5dda8','#9a6b12',1,2)]
 for t in q['terraces']:
  if t['terrace_polygon']:out += [poly(t['terrace_polygon'],s,ox,oy,'#80cbc4','#00796b',1,2),label_polygon(t['terrace_polygon'],'TERRACE',s,ox,oy,'#00796b')]
 for item in r['residential_unallocated_polygons']:
  if item['area']>.05:out += [poly(item['polygon'],s,ox,oy,'url(#residual)','#dc2626',1,1),label_polygon(item['polygon'],f'RESIDUAL {item["area"]:.1f}',s,ox,oy,'#b91c1c')]
 return out
def paired(study,c):
 out=['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="920"><rect width="100%" height="100%" fill="#f7f8f6"/>',DEFS,text(35,38,c['candidate_id'],23,'#17212b','bold'),text(70,82,'GROUND FLOOR',17,'#17212b','bold'),text(600,82,'FIRST RESIDENTIAL FLOOR',17,'#17212b','bold')]
 out+=ground(c,70,780,28)+residential(c,600,780,28);m=c['metrics'];rows=[f'PEDESTRIAN MODE: {c["pedestrian_mode"]}',f'CORE {c["core_strategy"]} | SPLIT {c["residential_split"]}',f'Parking {m["parking_count_generated"]}/{c["ground_floor"]["parking_required_count"]}',f'Commercial {m["commercial_area"]:.1f} m² | frontage {m["commercial_frontage"]:.1f} m | coherence {m["commercial_coherence"]:.2f}',f'Pedestrian loss area/frontage {m["pedestrian_induced_area_loss"]:.1f}/{m["pedestrian_induced_frontage_loss"]:.1f}',f'Entrance impact {m["entrance_impact_score"]:.3f}',f'Unit balance {m["unit_area_balance"]:.2f} | residential quality {m["residential_quality_score"]:.2f}',f'Frontage value loss {m["frontage_value_loss"]:.1f}',f'Ground residual {m["ground_floor_unallocated_area"]:.1f} | Residential residual {m["residential_unallocated_area"]:.1f}',f'Hard status {c["hard_validation_status"]}',f'Failures: {", ".join(c["hard_rejection_reasons"]) or "none"}',f'Ground changed: {c["ground_floor_changed"]} | {c["change_reason"]}','NO ROOMS / NO FINAL WINDOWS / NO WINNER']
 if c.get('north_wall_offset_search'):
  rows.insert(2,f'North-wall offset requested 8.0 m | selected {c["north_wall_offset_search"]["actual_offset"]:.1f} m')
  rows.insert(3,f'Stalls EAST-WEST, nose EAST | full array-derived maneuvering field')
 if c.get('transform'):
  rows.insert(1,f'ROTATION {c["transform"]["rotation_degrees"]} deg | TRANSLATION {c["transform"]["translation_vector"]}')
  rows.insert(2,f'V2 objective {c["objective"]["total_score"]:.3f} | dependencies regenerated')
 if c.get('counterexample_status'):
  rows.insert(1,c['counterexample_status'])
 for i,row in enumerate(rows):out.append(text(980,100+i*34,row,14,'#b91c1c' if i in (6,7) else '#17212b','bold' if i in (0,6,9) else 'normal'))
 out.append('</svg>');return ''.join(out)
def comparison(study,picks):
 out=['<svg xmlns="http://www.w3.org/2000/svg" width="1900" height="1200"><rect width="100%" height="100%" fill="#f7f8f6"/>',DEFS,text(35,38,'WHOLE-BUILDING COUPLED TOPOLOGY — DIRECT COMPARISON',23,'#17212b','bold')]
 for i,c in enumerate(picks):
  ox=35+i*465;out += [text(ox,78,c['candidate_id'],13,'#17212b','bold'),text(ox,101,f'PEDESTRIAN MODE: {c["pedestrian_mode"]}',10,'#4c1d95','bold'),text(ox,123,'GROUND',12,'#17212b','bold')]+ground(c,ox,555,18)+[text(ox,600,'RESIDENTIAL',12,'#17212b','bold')]+residential(c,ox,1050,18)
  m=c['metrics'];out += [text(ox,1082,f'P {m["parking_count_generated"]}/{c["ground_floor"]["parking_required_count"]} | C {m["commercial_area"]:.1f}m² | F {m["commercial_frontage"]:.1f}m | coh {m["commercial_coherence"]:.2f}',10),text(ox,1104,f'Ped loss area/front {m["pedestrian_induced_area_loss"]:.1f}/{m["pedestrian_induced_frontage_loss"]:.1f}',10,'#7c2d12','bold'),text(ox,1126,f'Front value loss {m["frontage_value_loss"]:.1f} | {c["hard_validation_status"]}',10,'#b91c1c' if c['hard_validation_status']!='hard_valid' else '#166534','bold')]
 out += [text(35,1175,'Pareto valid alternatives are separated from rejected diagnostics. NO FINAL SELECTION.',15,'#b91c1c','bold'),'</svg>'];return ''.join(out)
def alignment(study,candidates):
 out=['<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="850"><rect width="100%" height="100%" fill="#fafafa"/>',text(35,38,'VERTICAL CORE ALIGNMENT PROOF',23,'#17212b','bold')]
 for i,c in enumerate(candidates[:6]):
  x=80+i*235;out += [text(x,85,c['candidate_id'].replace('WB-',''),10,'#17212b','bold'),f'<rect x="{x}" y="570" width="150" height="130" fill="#d9edc7" stroke="#39833d"/>',f'<rect x="{x}" y="360" width="150" height="130" fill="#dbeafe" stroke="#17658a"/>',f'<rect x="{x}" y="150" width="150" height="130" fill="#dbeafe" stroke="#17658a"/>',f'<line x1="{x+75}" y1="150" x2="{x+75}" y2="700" stroke="#7e22ce" stroke-width="10"/>',text(x+15,635,'GROUND CORE',12,'#27632a','bold'),text(x+5,425,'FIRST RESIDENTIAL',11,'#17658a','bold'),text(x+12,215,'UPPER CORE',12,'#17658a','bold'),text(x,750,c['metrics']['vertical_alignment_status'],11,'#166534' if c['metrics']['vertical_alignment_status'].startswith('exact') else '#b91c1c','bold')]
 out.append('</svg>');return ''.join(out)
def frontage(candidates):
 out=['<svg xmlns="http://www.w3.org/2000/svg" width="1300" height="760"><rect width="100%" height="100%" fill="#fafafa"/>',text(35,38,'PUBLIC FRONTAGE VALUE IMPACT',23,'#17212b','bold'),text(35,75,'Public road edge value > private-neighbor edge; direction read from site context.',14)]
 for i,c in enumerate(candidates):
  y=130+i*70;loss=c['metrics']['frontage_value_loss'];out += [text(35,y,c['candidate_id'],13,'#17212b','bold'),f'<rect x="390" y="{y-20}" width="{loss*120:.1f}" height="30" fill="#dc2626" opacity=".75"/>',text(900,y,f'loss {loss:.2f}',13,'#b91c1c','bold')]
 out.append('</svg>');return ''.join(out)
def png(svg,pngfile,profile,width,height):
 chrome=Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
 if chrome.exists():subprocess.run([str(chrome),'--headless','--no-sandbox','--disable-gpu',f'--user-data-dir={profile}','--hide-scrollbars',f'--window-size={width},{height}',f'--screenshot={pngfile}',svg.as_uri()],check=True)
def main(output_root=None):
 bp=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];root=bp.parent;b=json.loads(bp.read_text(encoding='utf-8'));a=json.loads(sorted(root.glob('program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json'))[-1].read_text(encoding='utf-8'))['baseline_scenario_a'];pilot=json.loads(sorted(root.glob('program_driven_pilot_space_composition_v1_*/PROGRAM-A_CONTRACT.json'))[-1].read_text(encoding='utf-8'))['human_review_candidates'][0];before=fp((b,a,pilot));r=WholeBuildingCoupledTopologySearchV1().resolve(b['site'],a,pilot,{'parking_required_count':3,'pedestrian_clear_width':1.2,'commercial_required':True});assert before==fp((b,a,pilot))
 folder=(Path(output_root) if output_root else root/('architectural_reasoning_upgrade_v1_'+datetime.now().strftime('%Y%m%d_%H%M%S')));folder.mkdir(parents=True,exist_ok=False);contract=folder/'PARCEL2_ARCHITECTURAL_REASONING_UPGRADE_V1.json';contract.write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf-8');plans=[]
 no_modes=sorted([c for c in r['candidates'] if c['pedestrian_mode']=='NO_DEDICATED_PEDESTRIAN_ENTRANCE'],key=lambda c:(c['hard_validation_status']!='hard_valid',-c['metrics']['commercial_area']))
 dedicated=sorted([c for c in r['candidates'] if c['pedestrian_mode']=='DEDICATED_PEDESTRIAN_ENTRANCE'],key=lambda c:(c['hard_validation_status']!='hard_valid',c['metrics']['entrance_impact_score']))
 picks=[]
 if no_modes:picks.append(no_modes[0])
 if dedicated:picks.append(dedicated[0])
 pool=sorted([c for c in r['candidates'] if c not in picks],key=lambda c:(c['hard_validation_status']!='hard_valid',-c['metrics']['commercial_area'],c['metrics']['entrance_impact_score']))
 picks=(picks+pool)[:4]
 for i,c in enumerate(picks):
  svg=folder/f'{c["candidate_id"]}_DECISION.svg';svg.write_text(paired(r,c),encoding='utf-8');png(svg,svg.with_suffix('.png'),folder/f'.chrome_pair_{i}',1600,920);plans.append(str(svg))
 comp=folder/'PARCEL2_WHOLE_BUILDING_COMPARISON.svg';comp.write_text(comparison(r,picks),encoding='utf-8');png(comp,comp.with_suffix('.png'),folder/'.chrome_comparison',1900,1200)
 report=folder/'DECISION_REPORT.json';report.write_text(json.dumps({'references':['WB-NS-CURRENT-CORE','WB-EW-TRANSVERSE-PARKING-CORE-8M'],'decision_support_topologies':[c['candidate_id'] for c in picks],'pedestrian_modes_shown':[c['pedestrian_mode'] for c in picks],'dedicated_rejected':bool(dedicated) and all(c['hard_validation_status']!='hard_valid' for c in dedicated),'winner':None,'final_selection_performed':False},indent=2),encoding='utf-8')
 print(json.dumps({'folder':str(folder),'contract':str(contract),'candidate_count':r['candidate_count'],'hard_valid':r['hard_valid_candidate_count'],'pareto':r['pareto_shortlist_ids'],'decision_plans':plans,'comparison':str(comp),'report':str(report),'final_selection_performed':False,'program_changed':False,'basement_deleted':False}))
if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else None)
