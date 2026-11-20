import hashlib, json, subprocess, sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.architecture.reasoning.pilot_parking_program_tradeoff_topology_search_v1 import PilotParkingProgramTradeoffTopologySearchV1


def fp(v): return hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()
def pts(v,s,ox,oy): return ' '.join(f'{ox+x*s:.1f},{oy-y*s:.1f}' for x,y in v)
def poly(v,s,ox,oy,fill,stroke='#334155',opacity=.75,w=1.5,pattern=None):
    fill_value=f'url(#{pattern})' if pattern else fill
    return f'<polygon points="{pts(v,s,ox,oy)}" fill="{fill_value}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="{w}"/>'
def line(v,s,ox,oy,stroke,w=2,dash=''): return f'<polyline points="{pts(v,s,ox,oy)}" fill="none" stroke="{stroke}" stroke-width="{w}" {dash}/>'
def text(x,y,v,size=14,color='#17212b',weight='normal'): return f'<text x="{x}" y="{y}" font-family="Arial" font-size="{size}" fill="{color}" font-weight="{weight}">{v}</text>'
def defs():
    return '<defs><pattern id="storage" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="#d8c5f2"/><path d="M0 8L8 0" stroke="#70408c"/></pattern><pattern id="residual" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="#eee"/><path d="M0 0L8 8" stroke="#999"/></pattern></defs>'


def plan(study,c,ox,oy,s):
    p=study['local_parcel_polygon']; out=[poly(p,s,ox,oy,'#fff','#111827',1,2.5),poly([[p[0][0],-2],[p[1][0],-2],[p[1][0],0],[p[0][0],0]],s,ox,oy,'#cbd5e1','#64748b')]
    out += [poly(c['commercial_field'],s,ox,oy,'#bfe3b5','#39833d',.9),poly(c['drive_lane'],s,ox,oy,'#d7dde3','#64748b',.7),poly(c['maneuvering_field'],s,ox,oy,'#b8c4d0','#334155',.7,2),poly(c['street_to_core_corridor'],s,ox,oy,'#fff0a8','#b18400',.8)]
    for stall in c['parking_stalls']: out.append(poly(stall['polygon'],s,ox,oy,'#8ecae6','#17658a',.85,2))
    for a in c['post_parking_pedestrian_access']['stall_results']:
        if a['parking_to_lobby_path']: out.append(line(a['parking_to_lobby_path'],s,ox,oy,'#e07a00',3,'stroke-dasharray="6 3"'))
        for x,y in a['crossing_points']: out.append(f'<circle cx="{ox+x*s}" cy="{oy-y*s}" r="5" fill="#dc2626"/>')
    for a in c['residual_space_program']['allocations']:
        if a['program']=='residential_storage': out.append(poly(a['polygon'],s,ox,oy,'#d8c5f2','#70408c',.9,1.5,'storage'))
        elif a['program']=='common_wc': out.append(poly(a['polygon'],s,ox,oy,'#f7b267','#b45309',.9))
        elif a['program']=='commercial': out.append(poly(a['polygon'],s,ox,oy,'#bfe3b5','#39833d',.65))
    for r in c['residual_space_program']['unallocated_residual_polygons']: out.append(poly(r,s,ox,oy,'#eee','#777',.75,1,'residual'))
    out += [poly(c['core']['stair'],s,ox,oy,'#d3b5e5','#70408c',.9),poly(c['core']['elevator'],s,ox,oy,'#f3c2d1','#9d3155',.9),poly(c['core']['lobby'],s,ox,oy,'#f5dda8','#9a6b12',.9),line(c['vehicle_access_axis'],s,ox,oy,'#334155',3,'stroke-dasharray="7 4"'),line(c['street_to_core_path'],s,ox,oy,'#a97900',3),line(c['vehicle_entrance'],s,ox,oy,'#087454',6),line(c['pedestrian_entrance'],s,ox,oy,'#d49b00',6),line(c['commercial_storefront'],s,ox,oy,'#39833d',6)]
    vx,vy=c['vehicle_lane_endpoint']; out.append(f'<circle cx="{ox+vx*s}" cy="{oy-vy*s}" r="5" fill="#dc2626"/>')
    return out


def candidate_svg(study,c):
    s,ox,oy=34,70,790; m=c['metrics']; r=c['residual_space_program']; a=c['post_parking_pedestrian_access']; out=['<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="920"><rect width="100%" height="100%" fill="#f7f8f6"/>',defs()]+plan(study,c,ox,oy,s)
    rows=[c['candidate_id'],f'Intent: {c["tradeoff_intent"]}',f'Entrance: {c["entrance_mode"]}',f'Parking {c["parking_count"]} (independent proven 0)',f'Maneuver: {m["maneuvering_field_dimensions"][0]:.2f} × {m["maneuvering_field_dimensions"][1]:.2f} m',f'Commercial: {m["commercial_area"]:.1f} m² | frontage {m["commercial_frontage"]:.2f} m',f'Street→Core {m["street_to_core_path_length"]:.1f} m | Parking→Core {m["parking_to_core_path_length"]:.1f} m',f'Parking→Core crossings: {m["parking_to_core_crossing_count"]} ({a["parking_to_core_vehicle_conflict_status"]})',f'Storage: {m["residential_storage_count"]} / {m["residential_storage_total_area"]:.1f} m² | WC: {m["common_wc_generated"]}',f'Unallocated residual: {m["unallocated_residual_area"]:.1f} m²',f'Total circulation: {m["total_circulation_area"]:.1f} m²',f'Vehicle: {c["vehicle_maneuvering_status"]}',f'Regulatory: {c["regulatory_status"]}','HUMAN REVIEW — NO FINAL WINNER']
    for i,row in enumerate(rows): out.append(text(500,55+i*31,row,21 if i==0 else 15,'#17212b','bold' if i in (0,13) else 'normal'))
    out += [text(500,535,'Legend',17,'#17212b','bold'),text(500,565,'GREEN commercial | BLUE parking | GREY vehicle | YELLOW pedestrian',14),text(500,592,'PURPLE storage | ORANGE WC | HATCH grey unallocated | RED crossing/endpoint',14),'</svg>']; return ''.join(out)


def comparison(study):
    cs=study['human_review_candidates']; width=max(1600,len(cs)*335); out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="970"><rect width="100%" height="100%" fill="#f7f8f6"/>',defs(),text(35,38,'REAL PARCEL 2 — K-FAMILY PROGRAM TRADEOFFS — HUMAN REVIEW',23,'#17212b','bold')]
    for i,c in enumerate(cs):
        ox=35+i*330; oy=485; s=17; out += plan(study,c,ox,oy,s); m=c['metrics']; r=c['residual_space_program']
        mode={'independent_vehicle_gate_and_independent_pedestrian_gate':'A — independent','adjacent_vehicle_and_pedestrian_gate':'B — adjacent','combined_vehicle_pedestrian_gate_with_wicket':'C — wicket','shared_vehicle_pedestrian_access':'D — shared'}[c['entrance_mode']]
        rows=[c['candidate_id'],c['tradeoff_intent'],f'Parking {c["parking_count"]} | Commercial {m["commercial_area"]:.1f} m²',f'Frontage {m["commercial_frontage"]:.2f} m | Maneuver {m["maneuvering_field_dimensions"][0]:.2f} m',f'Parking→Core {m["parking_to_core_path_length"]:.1f} m / X {m["parking_to_core_crossing_count"]}',f'Storage {m["residential_storage_count"]} | WC {m["common_wc_generated"]}',f'Residual {m["unallocated_residual_area"]:.1f} m² | Circ {m["total_circulation_area"]:.1f} m²',f'Mode {mode}']
        for j,row in enumerate(rows): out.append(text(ox,535+j*25,row,12,'#17212b','bold' if j==0 else 'normal'))
    out += [text(35,780,'All parking maneuvering remains pending_vehicle_model_validation; independently usable count remains 0.',15,'#9a3412','bold'),text(35,810,'No final Scenario B winner selected.',16,'#17212b','bold'),'</svg>']; return ''.join(out)


def png(svg,pngfile,profile,width=1500):
    chrome=Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    if chrome.exists(): subprocess.run([str(chrome),'--headless','--no-sandbox','--disable-gpu',f'--user-data-dir={profile}','--hide-scrollbars',f'--window-size={width},970',f'--screenshot={pngfile}',svg.as_uri()],check=True)


def main():
    bp=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1]
    rp=sorted(bp.parent.glob('program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json'))[-1]
    b=json.loads(bp.read_text()); a=json.loads(rp.read_text())['baseline_scenario_a']; before=fp(deepcopy(b))
    r=PilotParkingProgramTradeoffTopologySearchV1().resolve(b['site'],b['requirements'],a); assert fp(b)==before
    folder=bp.parent/('pilot_k_topology_search_v1_'+datetime.now().strftime('%Y%m%d_%H%M%S')); folder.mkdir()
    contract=folder/'PARCEL2_PILOT_K_TOPOLOGY_SEARCH_V1.json'; contract.write_text(json.dumps(r,indent=2),encoding='utf-8'); outputs=[]
    for c in r['human_review_candidates']:
        svg=folder/f'{c["candidate_id"]}.svg'; preview=svg.with_suffix('.png'); svg.write_text(candidate_svg(r,c),encoding='utf-8'); png(svg,preview,folder/f'.chrome_{c["candidate_id"]}'); outputs.append({'candidate_id':c['candidate_id'],'svg':str(svg),'png':str(preview) if preview.exists() else None})
    comp=folder/'PARCEL2_K_PROGRAM_TRADEOFF_COMPARISON.svg'; comp.write_text(comparison(r),encoding='utf-8'); cp=comp.with_suffix('.png'); png(comp,cp,folder/'.chrome_comparison',max(1600,len(r['human_review_candidates'])*335))
    print(json.dumps({'contract':str(contract),'candidate_count':r['candidate_count'],'hard_valid':r['hard_valid_candidate_count'],'review':outputs,'comparison':str(comp),'comparison_png':str(cp) if cp.exists() else None,'final_selection_performed':False,'program_changed':False,'basement_deleted':False}))


if __name__=='__main__': main()
