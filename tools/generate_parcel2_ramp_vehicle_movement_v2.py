"""Honest, production-contract-only Parcel 2 movement comparison."""
import json,sys
from datetime import datetime
from pathlib import Path
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.far_end_operational_turn_v2 import FarEndOperationalTurnV2
from core.architecture.reasoning.terminal_vehicle_alignment_v2 import TerminalVehicleAlignmentV2
from core.architecture.reasoning.vehicle_movement_path_v3 import VehicleMovementPathV3
from tools.generate_parcel2_basement_v2_design import View,text,svg_to_png


def main():
    source=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1]
    base=json.loads(source.read_text());base['requirements']['ramp']['minimum_inner_turn_radius']=5.
    helper=BasementRampParkingDesignReasonerV2();frame=helper._frame(base['site']['parcel'],base['site']['frontage'])
    inner=helper._to_local_polygon(base['physical_basement_wall']['inner_face'],frame)
    local=lambda points:[helper._local(p,frame) for p in points]
    search=FarEndOperationalTurnV2().resolve(base['site']['parcel'],base['site']['frontage'],base['physical_basement_wall'],base['requirements'],{'status':'required','slope':.15})
    c15=min((c for c in search['candidates'] if c.get('ramp_operational_end_status')=='hard_valid'),key=lambda c:(c['maneuvering_field']['dimensions'][0]<5,-c['terminal_leg']['length'],c['candidate_id']))
    alignment=TerminalVehicleAlignmentV2().resolve(c15['topology']['end_point'],c15['topology']['end_heading'],list(inner.exterior.coords)[:-1],c15['surface']['complete_union_surface'],3.0)
    records=[curved_record(c15,alignment,helper,inner,base)]
    for slope in (.16,.17):
        candidates=[c for c in base['design']['candidates'] if abs(c['ramp']['slope']-slope)<1e-7]
        candidate=max(candidates,key=lambda c:(len(c['parking_stalls']),c['generated_maneuvering_placements'],-len(c['rejection_reasons'])))
        ramp_line=[helper._local(candidate['ramp']['start'],frame),helper._local(candidate['ramp']['end'],frame)]
        maneuver=local(candidate['maneuvering_envelope']);aisle=local(candidate['parking_aisle']);stalls=[local(p) for p in candidate['parking_stalls']]
        movement=VehicleMovementPathV3().resolve(ramp_line,local(candidate['ramp']['end_edge']),maneuver,aisle,stalls,3.0)
        records.append(straight_record(slope,candidate,ramp_line,maneuver,aisle,stalls,movement,local,helper,frame))
    contract={'contract':'Parcel2RampVehicleMovementComparisonV2','source_contract':str(source),'records':records,
        'renderer_authority':'production_comparison_contract_only','human_visual_acceptance':'pending','physical_ramp_published':False}
    folder=source.parent/('ramp_vehicle_movement_v2_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir()
    json_path=folder/'PARCEL2_RAMP_VEHICLE_MOVEMENT_15_16_17_V2.json';json_path.write_text(json.dumps(contract,indent=2),encoding='utf-8')
    svg_path=folder/'PARCEL2_RAMP_VEHICLE_MOVEMENT_15_16_17_V2.svg';png_path=folder/'PARCEL2_RAMP_VEHICLE_MOVEMENT_15_16_17_V2.png'
    svg_path.write_text(render(records,inner),encoding='utf-8');svg_to_png(svg_path,png_path)
    print(json.dumps({'folder':str(folder),'png':str(png_path),'json':str(json_path),'summary':[(r['slope'],r['terminal_alignment_status'],r['parking_search_status'],r['vehicle_path_status']) for r in records]}))


def curved_record(c,alignment,helper,inner,base):
    chosen=alignment['selected'];stalls=[];movement=None;field=[];end_edge=[]
    parking_status='parking_search_not_run'
    if chosen:
        field=chosen['maneuvering_polygon'];end_edge=chosen['final_end_edge']
        options=helper._stall_topologies(inner,Polygon(field),Polygon(c['surface']['complete_union_surface']),Polygon(),base['requirements']['parking'],None)
        if options:
            best=max(options,key=lambda o:(len(o['stalls']),helper._parking_rank(o)));stalls=[helper._polygon_coords(p) for p in best['stalls']]
            parking_status='parking_geometry_generated'
            movement=VehicleMovementPathV3().resolve(c['topology']['centerline']+chosen['alignment_centerline'][1:],end_edge,field,field,stalls,3.0)
            parking_status='hard_valid' if len(stalls)>=2 and movement['geometry_status']=='hard_valid' else 'parking_paths_under_validation'
        else:parking_status='aligned_maneuver_not_generated'
    return {'slope':.15,'candidate_id':c['candidate_id'],'ramp_geometry_status':'hard_valid','ramp_surface':c['surface']['complete_union_surface'],
        'ramp_centerline':c['topology']['centerline'],'start':c['topology']['start_point'],'end':chosen['final_end_point'] if chosen else None,
        'end_heading':chosen['final_end_heading'] if chosen else c['topology']['end_heading'],'end_edge':end_edge,
        'terminal_alignment_status':alignment['terminal_alignment_status'],'terminal_alignment_geometry':chosen,
        'end_interface_width':chosen['end_interface_width'] if chosen else 0.0,'maneuvering_field_status':'hard_valid' if chosen else 'not_generated',
        'maneuvering_dimensions':chosen['maneuvering_dimensions'] if chosen else None,'maneuvering_orientation':'site_local_axes' if chosen else 'not_generated',
        'maneuvering_polygon':field,'aisle_polygon':field,'parking_search_status':parking_status,'parking_stalls':stalls,
        'parking_stall_count':len(stalls),'vehicle_path_validation_level':movement['vehicle_path_validation_level'] if movement else 'not_generated',
        'vehicle_path_status':movement['geometry_status'] if movement else 'not_generated','vehicle_movement':movement,
        'alignment_failure_reasons':alignment['failure_reasons']}


def straight_record(slope,c,ramp_line,maneuver,aisle,stalls,movement,local,helper,frame):
    h=[ramp_line[-1][0]-ramp_line[-2][0],ramp_line[-1][1]-ramp_line[-2][1]];n=(h[0]**2+h[1]**2)**.5;h=[h[0]/n,h[1]/n]
    return {'slope':slope,'candidate_id':c['candidate_id'],'ramp_geometry_status':'hard_valid','ramp_surface':local(c['ramp']['polygon']),
        'ramp_centerline':ramp_line,'start':ramp_line[0],'end':ramp_line[-1],'end_heading':h,'end_edge':local(c['ramp']['end_edge']),
        'terminal_alignment_status':'already_aligned_site_longitudinal','terminal_alignment_geometry':None,
        'end_interface_width':c['ramp_end_escape']['minimum_connection_width'],'maneuvering_field_status':'hard_valid',
        'maneuvering_dimensions':[5.,5.],'maneuvering_orientation':'site_local_axes','maneuvering_polygon':maneuver,'aisle_polygon':aisle,
        'parking_search_status':'hard_valid' if len(stalls)>=2 and movement['geometry_status']=='hard_valid' else 'parking_paths_under_validation',
        'parking_stalls':stalls,'parking_stall_count':len(stalls),'vehicle_path_validation_level':movement['vehicle_path_validation_level'],
        'vehicle_path_status':movement['geometry_status'],'vehicle_movement':movement,'alignment_failure_reasons':[]}


def render(records,inner):
    view=View(list(inner.exterior.coords)[:-1]);W,H=2100,1320
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="#f7f6f1"/>',
         text(45,48,'REAL PARCEL 2 — RAMP / VEHICLE MOVEMENT 15–16–17% V2',30,'bold'),text(45,82,'CONTRACT GEOMETRY ONLY — HUMAN REVIEW',17,'bold')]
    for i,r in enumerate(records):
        x=30+i*690;y=105;out.append(f'<rect x="{x}" y="{y}" width="660" height="1145" rx="8" fill="white" stroke="#8499a6" stroke-width="2"/>')
        out.append(text(x+20,y+36,f"{int(r['slope']*100)}% — {r['candidate_id']}",21,'bold'))
        out.append(f'<svg x="{x+18}" y="{y+55}" width="625" height="750" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet">')
        # Strict architectural layer order.
        out.append(f'<polygon points="{view.points(list(inner.exterior.coords)[:-1])}" fill="#eef1ef" stroke="#263a43" stroke-width="6"/>')
        out.append(f'<polygon points="{view.points(r["ramp_surface"])}" fill="#efb3bf" stroke="#a61734" stroke-width="4"/>')
        if r['maneuvering_polygon']:
            out.append(f'<polygon points="{view.points(r["maneuvering_polygon"])}" fill="#a9dfbd" fill-opacity=".72" stroke="#19733b" stroke-width="7" stroke-dasharray="16 8"/>')
            cx,cy=view.p(Polygon(r['maneuvering_polygon']).centroid.coords[0]);dims=r['maneuvering_dimensions']
            out.append(text(cx-120,cy-8,f'MANEUVER {dims[0]:.1f}x{dims[1]:.1f}',20,'bold','#155b2c'))
            out.append(text(cx-65,cy+25,f'{dims[0]:.1f}m x {dims[1]:.1f}m',17,'bold','#155b2c'))
        for index,stall in enumerate(r['parking_stalls']):
            out.append(f'<polygon points="{view.points(stall)}" fill="#d8dee1" stroke="#354750" stroke-width="5"/>')
            poly=Polygon(stall);cx,cy=view.p(poly.centroid.coords[0]);out.append(text(cx-22,cy-32,f'P-{index+1:02d}',17,'bold'))
            minx,miny,maxx,maxy=poly.bounds;car=Polygon([(minx+(maxx-minx)*.22,miny+(maxy-miny)*.18),(maxx-(maxx-minx)*.22,miny+(maxy-miny)*.18),(maxx-(maxx-minx)*.22,maxy-(maxy-miny)*.18),(minx+(maxx-minx)*.22,maxy-(maxy-miny)*.18)])
            out.append(f'<polygon points="{view.points(list(car.exterior.coords)[:-1])}" fill="#8798a1" stroke="#23343c" stroke-width="3"/>')
        movement=r.get('vehicle_movement')
        if movement:
            for path in movement['stall_paths']:
                for key,color in (('center_trajectory','#0875c9'),('exit_trajectory','#e07816'),('return_to_ramp_trajectory','#6a31a6')):
                    if path[key]:out.append(f'<polyline points="{view.points(path[key])}" fill="none" stroke="{color}" stroke-width="5" stroke-dasharray="15 9"/>')
        if r['end_edge']:out.append(f'<polyline points="{view.points(r["end_edge"])}" fill="none" stroke="#71142a" stroke-width="9"/>')
        sx,sy=view.p(r['start']);out.append(f'<circle cx="{sx}" cy="{sy}" r="10" fill="#075fa8"/>');out.append(text(sx+12,sy-8,'START +0.00',15,'bold'))
        if r['end']:
            ex,ey=view.p(r['end']);out.append(f'<circle cx="{ex}" cy="{ey}" r="10" fill="#a81734"/>');out.append(text(ex+12,ey+22,'END -2.40',15,'bold'))
        out.append('</svg>')
        lines=[f"Terminal alignment: {r['terminal_alignment_status']}",f"END interface: {r['end_interface_width']:.2f}m",
            f"Maneuver: {r['maneuvering_field_status']} / {r['maneuvering_dimensions'] or 'NOT GENERATED'}",
            f"Parking: {r['parking_search_status']} / stalls {r['parking_stall_count']}",f"Vehicle paths: {r['vehicle_path_status']} ({r['vehicle_path_validation_level']})"]
        if r['slope']==.15:lines.append('FLOOR-LEVEL TERMINAL ALIGNMENT: '+('GENERATED' if r['terminal_alignment_geometry'] else 'NOT GENERATED'))
        if not r['maneuvering_polygon']:lines.append('ALIGNED MANEUVERING FIELD: NOT GENERATED')
        if not movement or not any(p['center_trajectory'] for p in movement.get('stall_paths',[])):lines.append('VALIDATED ENTRY / EXIT TRAJECTORIES: NOT GENERATED')
        if movement:
            for p in movement['stall_paths']:lines.append(f"{p['stall_id']}: ENTRY {p['entry_status']} | EXIT {p['exit_status']} | RETURN {p['return_to_ramp_status']}")
        for j,line in enumerate(lines):out.append(text(x+20,y+850+j*29,line,14,'bold' if 'NOT GENERATED' in line else 'normal','#b0162f' if 'NOT GENERATED' in line else '#20272c'))
    out.extend([text(45,1290,'NO FINAL RAMP PUBLISHED | HUMAN VISUAL ACCEPTANCE PENDING',16,'bold'),'</svg>'])
    return ''.join(out)


if __name__=='__main__':main()
