"""Human comparison of geometry regenerated from sketch relationships."""
import json,sys
from datetime import datetime
from pathlib import Path
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.curved_ramp_stationed_surface_v1 import CurvedRampStationedSurfaceV1
from core.architecture.reasoning.far_end_operational_turn_v2 import FarEndOperationalTurnV2
from tools.generate_parcel2_basement_v2_design import View,text,svg_to_png


def main():
    source=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1]
    base=json.loads(source.read_text());base['requirements']['ramp']['minimum_inner_turn_radius']=5.
    search=FarEndOperationalTurnV2().resolve(base['site']['parcel'],base['site']['frontage'],base['physical_basement_wall'],base['requirements'],{'status':'required','slope':.15})
    candidates=search['candidates'];operational=[c for c in candidates if c.get('ramp_operational_end_status')=='hard_valid']
    far=max((c for c in operational if '-west-' in c['candidate_id']),key=lambda c:(c['topology']['leg_1_length'],c['topology']['effective_total_run']))
    lateral=max(candidates,key=lambda c:(c['topology']['leg_2_length'],c['topology']['effective_total_run']))
    opposite=max((c for c in operational if '-east-' in c['candidate_id']),key=lambda c:c['topology']['effective_total_run'])
    chosen=[('A — PERIMETER + FAR-END CURVE',far),('B — CURVE + LATERAL TERMINAL',lateral),('C/D — OPPOSITE PERIMETER / PARKING SEARCH',opposite)]
    helper=BasementRampParkingDesignReasonerV2();frame=helper._frame(base['site']['parcel'],base['site']['frontage']);inner=helper._to_local_polygon(base['physical_basement_wall']['inner_face'],frame)
    records=[]
    for family,c in chosen:
        stationed=CurvedRampStationedSurfaceV1().resolve(c['topology'],c['width_transition'])
        ramp=Polygon(c['surface']['complete_union_surface']);remaining=inner.difference(ramp)
        records.append({'family':family,'candidate_id':c['candidate_id'],'topology':'perimeter_curved_variable_profile',
            'route_length':c['topology']['effective_total_run'],'maximum_local_grade':max(stationed['maximum_abs_grade_left_edge'],stationed['maximum_abs_grade_centerline'],stationed['maximum_abs_grade_right_edge']),
            'R_inner':c['topology']['R_inner'],'surface_status':stationed['geometry_status'],'surface_failures':stationed['failure_reasons'],
            'ramp_surface':c['surface']['complete_union_surface'],'ramp_centerline':c['topology']['centerline'],
            'tangent_in':c['topology']['tangent_in'],'tangent_out':c['topology']['tangent_out'],'end_edge':c['topology']['operational_end_edge'],
            'maneuvering_field':c['maneuvering_field']['polygon'] if c.get('ramp_operational_end_status')=='hard_valid' else [],
            'maneuvering_size':c['maneuvering_field']['dimensions'] if c.get('ramp_operational_end_status')=='hard_valid' else None,
            'end_interface_width':c['operational_end']['interface_length'],'parking_capacity':c['parking_capacity'],
            'independently_usable_stall_count':0,'vehicle_path_status':'not_generated','parking_stalls':[],
            'central_intrusion':ramp.intersection(inner.buffer(-3)).area if not inner.buffer(-3).is_empty else 0,
            'fragmentation':len(getattr(remaining,'geoms',[remaining])),'remaining_free_field_area':remaining.area,
            'grade_redistribution_status':stationed['grade_redistribution_status'],'vertical_drop_shortfall':stationed['vertical_drop_shortfall'],
            'final_status':'rejected_before_parking' if stationed['geometry_status']!='resolved' else c['geometry_status']})
    contract={'contract':'Parcel2FifteenPercentCounterexampleTopologyStudyV1',
        'SKETCH_RELATIONSHIP_EXTRACTED':['long ramp leg follows usable perimeter','turn belongs in far region when operational space remains','terminal field must remain connected','parking is searched at perimeter/dead edges','multiple asymmetric parking arrangements belong to the search space'],
        'PRODUCTION_REGENERATION':{'source':'REAL Parcel 2 contracts','coordinates_copied_from_sketch':False,
            'maneuver_field_center_events':'legal clear-face interval endpoints/quartiles/midpoint','candidates_generated':len(candidates),
            'operational_end_candidates':len(operational),'stationed_surface_hard_valid_candidates':sum(r['surface_status']=='resolved' for r in records)},
        'records':records,'selection_status':'unresolved_no_stationed_surface_candidate','physical_ramp_published':False,'human_visual_acceptance':'pending'}
    folder=source.parent/('counterexample_topologies_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir()
    jp=folder/'PARCEL2_15_COUNTEREXAMPLE_TOPOLOGY_ALTERNATIVES.json';jp.write_text(json.dumps(contract,indent=2),encoding='utf-8')
    sp=folder/'PARCEL2_15_COUNTEREXAMPLE_TOPOLOGY_ALTERNATIVES.svg';pp=folder/'PARCEL2_15_COUNTEREXAMPLE_TOPOLOGY_ALTERNATIVES.png';sp.write_text(render(records,inner),encoding='utf-8');svg_to_png(sp,pp)
    print(json.dumps({'folder':str(folder),'png':str(pp),'json':str(jp),'generated':len(candidates),'operational_end':len(operational),'stationed_valid':sum(r['surface_status']=='resolved' for r in records)}))


def render(records,inner):
    view=View(list(inner.exterior.coords)[:-1]);W,H=2040,1320
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="#f7f6f1"/>',text(42,46,'REAL PARCEL 2 — 15% COUNTEREXAMPLE TOPOLOGY STUDY',28,'bold'),text(42,77,'SKETCH RELATIONSHIPS REGENERATED FROM REAL GEOMETRY — NO COPIED COORDINATES',16,'bold')]
    for i,r in enumerate(records):
        x=25+i*675;y=100;out.append(f'<rect x="{x}" y="{y}" width="650" height="1160" rx="8" fill="white" stroke="#879aa5" stroke-width="2"/>');out.append(text(x+18,y+35,r['family'],18,'bold'))
        out.append(f'<svg x="{x+18}" y="{y+50}" width="614" height="720" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet">')
        out.append(f'<polygon points="{view.points(list(inner.exterior.coords)[:-1])}" fill="#edf1ef" stroke="#263a43" stroke-width="6"/>')
        out.append(f'<polygon points="{view.points(r["ramp_surface"])}" fill="#efb3bf" stroke="#a61734" stroke-width="4"/>')
        out.append(f'<polyline points="{view.points(r["ramp_centerline"])}" fill="none" stroke="#0871bd" stroke-width="6" stroke-dasharray="15 9"/>')
        if r['maneuvering_field']:out.append(f'<polygon points="{view.points(r["maneuvering_field"])}" fill="#a9dfbd" fill-opacity=".7" stroke="#19733b" stroke-width="6" stroke-dasharray="15 8"/>')
        for label,p,color in [('T-IN',r['tangent_in'],'#8a5a00'),('T-OUT',r['tangent_out'],'#8a5a00')]:
            px,py=view.p(p);out.append(f'<circle cx="{px}" cy="{py}" r="10" fill="{color}"/>');out.append(text(px+10,py-8,label,14,'bold',color))
        out.append(f'<polyline points="{view.points(r["end_edge"])}" fill="none" stroke="#72162b" stroke-width="9"/>');out.append('</svg>')
        lines=[f"Candidate: {r['candidate_id']}",f"Route: {r['route_length']:.3f}m | R-inner: {r['R_inner']:.2f}m",f"Max physical-edge grade: {100*r['maximum_local_grade']:.3f}%",f"Stationed surface: {r['surface_status']}",f"Redistribution: {r['grade_redistribution_status']}",f"Drop shortfall: {r['vertical_drop_shortfall']:.3f}m",f"END interface: {r['end_interface_width']:.3f}m",f"Maneuver: {r['maneuvering_size'] or 'NOT GENERATED'}",f"Parking / independent: {r['parking_capacity']} / {r['independently_usable_stall_count']}",f"Vehicle path: {r['vehicle_path_status']}",f"Central intrusion: {r['central_intrusion']:.2f}m2",f"Remaining field: {r['remaining_free_field_area']:.2f}m2 | fragments {r['fragmentation']}",f"STATUS: {r['final_status']}"]
        for j,line in enumerate(lines):out.append(text(x+18,y+805+j*25,line,13,'bold' if 'STATUS' in line else 'normal','#b01630' if ('not_' in line or 'rejected' in line) else '#20272c'))
    out.extend([text(42,1295,'NO FINAL PHYSICAL RAMP PUBLISHED | HUMAN VISUAL ACCEPTANCE PENDING',16,'bold'),'</svg>']);return ''.join(out)


if __name__=='__main__':main()
