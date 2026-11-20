import hashlib, json, subprocess, sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.residential_ns_shared_court_refinement_v1 import ResidentialNSSharedCourtRefinementV1
from tools.generate_parcel2_residential_floor_access_daylight_topology_v1 import poly,line,text,mark


def fp(value): return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
DEFS='''<defs><pattern id="residual" width="8" height="8" patternUnits="userSpaceOnUse"><path d="M0 8L8 0" stroke="#dc2626" stroke-width="1"/></pattern><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="context-stroke"/></marker></defs>'''


def plan_elements(study,c,ox=70,oy=760,s=28):
    util=c['buildable_space_utilization']; p=study['local_parcel_polygon']
    out=[poly(p,s,ox,oy,'url(#residual)','#111827',1,2.5),text(ox,oy+42,'SOUTH — 10 m PUBLIC ROAD',12,'#334155','bold')]
    colors={'PRIVATE_UNIT':('#bfe3b5','#39833d'),'COMMON':('#f5dda8','#9a6b12'),'VERTICAL_CIRCULATION':('#c4a7e7','#70408c'),
            'DAYLIGHT_COURT':('#d9f4ff','#0284c7'),'PRIVATE_TERRACE':('#80cbc4','#00796b'),'STRUCTURAL_OR_SHAFT_RESERVATION':('#9ca3af','#374151')}
    labels={'UNIT-SOUTH':'UNIT SOUTH','UNIT-NORTH':'UNIT NORTH','UNIT-1':'UNIT 1','UNIT-2':'UNIT 2','COMMON-LOBBY':'COMMON LOBBY',
            'STAIR':'STAIR','ELEVATOR':'ELEVATOR','SHARED-DAYLIGHT-COURT':'SHARED DAYLIGHT COURT','PRIVACY-WALL':'PRIVACY WALL'}
    for space in util['classified_spaces']:
        if space['classification']=='UNALLOCATED_RESIDUAL': continue
        fill,stroke=colors[space['classification']]; out.append(poly(space['polygon'],s,ox,oy,fill,stroke,1,2))
        xs=[q[0] for q in space['polygon']]; ys=[q[1] for q in space['polygon']]
        if space['space_id'] in labels and space['space_id'] in ('UNIT-SOUTH','UNIT-NORTH','UNIT-1','UNIT-2','SHARED-DAYLIGHT-COURT'):
            out.append(text(ox+s*sum(xs)/len(xs)-35,oy-s*sum(ys)/len(ys),labels[space['space_id']],10,stroke,'bold'))
    for residual in util['unallocated_residual_polygons']:
        if residual['area'] < .05: continue
        out.append(poly(residual['polygon'],s,ox,oy,'url(#residual)','#dc2626',1,2))
        xs=[q[0] for q in residual['polygon']];ys=[q[1] for q in residual['polygon']]
        out.append(text(ox+s*sum(xs)/len(xs)-45,oy-s*sum(ys)/len(ys),f'UNALLOCATED RESIDUAL {residual["area"]:.1f} m²',9,'#b91c1c','bold'))
    for i,t in enumerate(c['terraces']):
        if t['terrace_polygon']:
            xs=[q[0] for q in t['terrace_polygon']];ys=[q[1] for q in t['terrace_polygon']]
            out.append(text(ox+s*sum(xs)/len(xs)-30,oy-s*sum(ys)/len(ys),f'{"SOUTH" if i==0 else "NORTH"} TERRACE',9,'#00695c','bold'))
    graph=c['residential_common_access_graph']
    for path in graph['walk_path_proofs'].values(): out.append(line(path,s,ox,oy,'#7c3aed',2,'stroke-dasharray="6 3" marker-end="url(#arrow)"'))
    for i,d in enumerate(graph['unit_entry_doors']): out.append(mark(*d['door_center'],f'D{i+1}',s,ox,oy,'#111827'))
    md=c['maintenance_door']; out.append(mark(*md['door_center'],'DM',s,ox,oy,'#7c4a2d'))
    if c['projection_mode'].endswith('enabled'):
        x0=min(x for x,y in p);x1=max(x for x,y in p)
        out += [poly([[x0,-.8],[x1,-.8],[x1,0],[x0,0]],s,ox,oy,'#f5d0fe','#c026d3',.55,2),text(ox,oy+70,'0.80 m PROJECTION CANDIDATE — APPROVAL PENDING',10,'#c026d3','bold')]
    return out


def plan_svg(study,c):
    q=c['quality_metrics'];u=c['buildable_space_utilization'];pr=c['shared_court_terrace_privacy_separation']
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1450" height="900"><rect width="100%" height="100%" fill="#f7f8f6"/>',DEFS]+plan_elements(study,c)
    rows=[c['candidate_id'],f'Role: {c["candidate_role"]}',f'Unit balance {q["unit_area_balance"]:.2f} | court balance {q["shared_court_daylight_balance"]:.2f}',
          f'Unallocated {u["unallocated_buildable_area"]:.2f} m² / {u["unallocated_buildable_area_ratio"]:.1%}',f'Residual fragments {u["residual_fragmentation_count"]}',
          f'Privacy {pr["divider_topology_status"]} | conflicts {q["privacy_conflicts"]}',f'Maintenance {c["maintenance_access_source"]}',
          f'Projection gain {q["projection_net_architectural_gain"]:.2f} m² | FAR pending',f'Hard status {c["hard_validation_status"]}',
          'NO ROOMS / NO FINAL WINDOWS / NO FINAL SELECTION']
    for i,row in enumerate(rows): out.append(text(650,55+i*32,row,20 if i==0 else 14,'#b91c1c' if i in (5,8) else '#17212b','bold' if i in (0,9) else 'normal'))
    out += [text(650,410,'HATCH = UNALLOCATED RESIDUAL',13,'#b91c1c','bold'),text(650,440,'D1/D2 = UNIT DOORS | DM = COMMON MAINTENANCE DOOR',13),text(650,470,'PURPLE = STAIR | PINK = ELEVATOR | GOLD = COMMON LOBBY',13),'</svg>'];return ''.join(out)


def utilization_svg(c):
    u=c['buildable_space_utilization']; rows=[('Gross',u['gross_buildable_floor_area']),('Allocated',u['allocated_buildable_area']),('Unallocated',u['unallocated_buildable_area']),('Usable residual',u['usable_residual_area']),('Unusable residual',u['unusable_residual_area'])]
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="700"><rect width="100%" height="100%" fill="#fafafa"/>',DEFS,text(35,40,f'{c["candidate_id"]} — SPACE UTILIZATION DIAGNOSTIC',22,'#17212b','bold')]
    total=max(v for _,v in rows)
    for i,(label,value) in enumerate(rows):
        y=110+i*78;out += [text(35,y,label,15,'#17212b','bold'),f'<rect x="230" y="{y-22}" width="{700*value/total:.1f}" height="34" fill="{"#dc2626" if label=="Unallocated" else "#3b82f6"}" opacity=".75"/>',text(940,y,f'{value:.2f} m²',14)]
    out += [text(35,550,f'Unallocated ratio: {u["unallocated_buildable_area_ratio"]:.1%}',17,'#b91c1c','bold'),text(35,585,f'Classification status: {u["utilization_status"]}',15),'</svg>'];return ''.join(out)


def privacy_svg(c):
    pr=c['shared_court_terrace_privacy_separation'];out=['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="760"><rect width="100%" height="100%" fill="#fafafa"/>',DEFS,text(35,38,f'{c["candidate_id"]} — PRIVACY / LIGHTWELL DIAGNOSTIC',22,'#17212b','bold')]+plan_elements({'local_parcel_polygon':c['_local_parcel_polygon']},c,55,690,24)
    rows=[f'Case: {pr["privacy_case"]}',f'Divider required: {pr["privacy_divider_required"]}',f'Divider status: {pr["divider_topology_status"]}',f'Wall thickness: {pr["privacy_wall_thickness"]} m — engineering assumption',f'Clear court area: {pr["clear_daylight_court_area"]:.2f} m²',f'Clear min width: {pr["clear_daylight_court_min_width"]:.2f} m',f'Airflow: {pr["natural_airflow_status"]}',f'Maintenance remains COMMON: {pr["maintenance_access_remains_common"]}',f'Failures: {", ".join(pr["failure_reasons"]) or "none"}']
    for i,row in enumerate(rows):out.append(text(620,90+i*33,row,14,'#b91c1c' if i in (2,8) else '#17212b','bold' if i in (0,2) else 'normal'))
    out.append('</svg>');return ''.join(out)


def projection_section(c):
    s=c['projection_vertical_stack'];out=['<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="760"><rect width="100%" height="100%" fill="#f7f8f6"/>',text(35,38,'PROJECTION VERTICAL STACK — CORRECTED CONCEPT',22,'#17212b','bold'),'<rect x="60" y="600" width="360" height="70" fill="#cbd5e1" stroke="#64748b"/>',text(185,642,'10 m ROAD',16,'#334155','bold'),'<rect x="420" y="400" width="600" height="270" fill="#d9edc7" stroke="#39833d"/>',text(460,560,'GROUND FLOOR',18,'#27632a','bold'),'<rect x="420" y="170" width="600" height="230" fill="#dbeafe" stroke="#17658a"/>',text(470,270,'FIRST RESIDENTIAL OCCUPIED / TERRACE ZONE',16,'#17658a','bold'),'<rect x="340" y="390" width="680" height="18" fill="#7c3aed"/>',text(520,385,'GROUND FLOOR ROOF / FIRST RESIDENTIAL FLOOR SLAB',14,'#6d28d9','bold'),'<rect x="340" y="152" width="680" height="18" fill="#475569"/>',text(520,145,'FIRST RESIDENTIAL ROOF / NEXT SLAB',14,'#334155','bold'),'<rect x="340" y="390" width="80" height="18" fill="#d946ef"/>',text(75,380,'0.80 m CANDIDATE PROJECTION',14,'#c026d3','bold'),'<line x1="300" y1="600" x2="300" y2="408" stroke="#b91c1c" stroke-width="3"/>',text(80,500,'3.50 m CLEAR HEIGHT CHECK',14,'#b91c1c','bold')]
    out += [text(70,705,f'Clearance source: {s["clearance_check_geometry"]} | status: {s["public_road_clearance_status"]} | exact elevation pending project input',13,'#9a3412','bold'),'</svg>'];return ''.join(out)


def comparison_svg(study,candidates):
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1900" height="1250"><rect width="100%" height="100%" fill="#f7f8f6"/>',DEFS,text(35,38,'REAL PARCEL 2 — NS REFINEMENT + COUNTEREXAMPLES',23,'#17212b','bold')]
    for i,c in enumerate(candidates[:7]):
        col=i%4;row=i//4;ox=35+col*465;oy=505+row*520;out+=plan_elements(study,c,ox,oy,18);u=c['buildable_space_utilization'];out += [text(ox,oy+85,c['candidate_id'],12,'#17212b','bold'),text(ox,oy+105,f'Unallocated {u["unallocated_buildable_area"]:.1f} m² | {c["hard_validation_status"]}',10)]
    out += [text(35,1220,'NO FINAL RESIDENTIAL TOPOLOGY SELECTED',16,'#b91c1c','bold'),'</svg>'];return ''.join(out)


def png(svg,pngfile,profile,width,height=900):
    chrome=Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    if chrome.exists(): subprocess.run([str(chrome),'--headless','--no-sandbox','--disable-gpu',f'--user-data-dir={profile}','--hide-scrollbars',f'--window-size={width},{height}',f'--screenshot={pngfile}',svg.as_uri()],check=True)


def main():
    bp=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];root=bp.parent;b=json.loads(bp.read_text(encoding='utf-8'));a=json.loads(sorted(root.glob('program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json'))[-1].read_text(encoding='utf-8'))['baseline_scenario_a'];pilot=json.loads(sorted(root.glob('program_driven_pilot_space_composition_v1_*/PROGRAM-A_CONTRACT.json'))[-1].read_text(encoding='utf-8'))['human_review_candidates'][0];before=fp((b,a,pilot))
    r=ResidentialNSSharedCourtRefinementV1().resolve(b['site'],a,pilot,{'jurisdiction':'Minab'});assert before==fp((b,a,pilot))
    folder=root/('residential_ns_shared_court_refinement_v1_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir();contract=folder/'PARCEL2_RESIDENTIAL_NS_SHARED_COURT_REFINEMENT_V1.json';contract.write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf-8')
    plans=[]
    for c in r['human_review_candidates']:
        c['_local_parcel_polygon']=r['local_parcel_polygon'];svg=folder/f'{c["candidate_id"]}.svg';svg.write_text(plan_svg(r,c),encoding='utf-8');png(svg,svg.with_suffix('.png'),folder/f'.chrome_{len(plans)}',1450);del c['_local_parcel_polygon'];plans.append(str(svg))
    projection_candidate=next(c for c in r['candidates'] if c['refinement_family']=='NS-E')
    projection_plan=folder/'PARCEL2_NS_E_PROJECTION_PLAN.svg';projection_plan.write_text(plan_svg(r,projection_candidate),encoding='utf-8');png(projection_plan,projection_plan.with_suffix('.png'),folder/'.chrome_projection_plan',1450)
    primary=r['human_review_candidates'][0];util=folder/'PARCEL2_SPACE_UTILIZATION_DIAGNOSTIC.svg';util.write_text(utilization_svg(primary),encoding='utf-8');png(util,util.with_suffix('.png'),folder/'.chrome_util',1100,700)
    diagnostic=next((c for c in r['candidates'] if c['refinement_family']=='NS-D'),primary);diagnostic['_local_parcel_polygon']=r['local_parcel_polygon'];privacy=folder/'PARCEL2_PRIVACY_LIGHTWELL_DIAGNOSTIC.svg';privacy.write_text(privacy_svg(diagnostic),encoding='utf-8');png(privacy,privacy.with_suffix('.png'),folder/'.chrome_privacy',1200,760);del diagnostic['_local_parcel_polygon']
    projection=folder/'PARCEL2_PROJECTION_VERTICAL_STACK_SECTION.svg';projection.write_text(projection_section(next((c for c in r['candidates'] if c['refinement_family']=='NS-E'),primary)),encoding='utf-8');png(projection,projection.with_suffix('.png'),folder/'.chrome_projection',1400,760)
    comp=folder/'PARCEL2_NS_REFINEMENT_COMPARISON.svg';comp.write_text(comparison_svg(r,r['human_review_candidates']),encoding='utf-8');png(comp,comp.with_suffix('.png'),folder/'.chrome_comparison',1900,1250)
    contract.write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'folder':str(folder),'contract':str(contract),'candidate_count':r['candidate_count'],'hard_valid':r['hard_valid_candidate_count'],'review_candidates':r['human_review_candidate_ids'],'plans':plans,'projection_plan':str(projection_plan),'utilization':str(util),'privacy':str(privacy),'projection_section':str(projection),'comparison':str(comp),'final_selection_performed':False,'program_changed':False,'basement_deleted':False}))
if __name__=='__main__':main()
