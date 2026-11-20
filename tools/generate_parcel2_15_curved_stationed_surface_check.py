"""Parcel 2 15% common-centerline-station curved surface proof."""
import json,sys
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.curved_ramp_stationed_surface_v1 import CurvedRampStationedSurfaceV1
from core.architecture.reasoning.far_end_operational_turn_v2 import FarEndOperationalTurnV2
from tools.generate_parcel2_basement_v2_design import View,text,svg_to_png


def main():
    source=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1]
    base=json.loads(source.read_text());base['requirements']['ramp']['minimum_inner_turn_radius']=5.
    search=FarEndOperationalTurnV2().resolve(base['site']['parcel'],base['site']['frontage'],base['physical_basement_wall'],base['requirements'],{'status':'required','slope':.15})
    candidate=min((c for c in search['candidates'] if c.get('ramp_operational_end_status')=='hard_valid'),key=lambda c:(c['maneuvering_field']['dimensions'][0]<5,-c['terminal_leg']['length'],c['candidate_id']))
    stationed=CurvedRampStationedSurfaceV1().resolve(candidate['topology'],candidate['width_transition'])
    contract={'contract':'Parcel2CurvedRampStationedSurfaceCheckV1','candidate_id':candidate['candidate_id'],
        'parcel_source':str(source),'slope_family':.15,'start_z':0.0,'end_z':-2.4,
        'topology':candidate['topology'],'width_transition':candidate['width_transition'],
        'stationed_surface':stationed,'downstream_generation':'stopped_before_terminal_alignment_maneuvering_parking',
        'human_visual_acceptance':'pending','physical_ramp_published':False}
    folder=source.parent/('curved_stationed_surface_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir()
    json_path=folder/'PARCEL2_15_CURVED_RAMP_STATIONED_SURFACE_CHECK.json';json_path.write_text(json.dumps(contract,indent=2),encoding='utf-8')
    svg_path=folder/'PARCEL2_15_CURVED_RAMP_STATIONED_SURFACE_CHECK.svg';png_path=folder/'PARCEL2_15_CURVED_RAMP_STATIONED_SURFACE_CHECK.png'
    svg_path.write_text(render(base,candidate,stationed),encoding='utf-8');svg_to_png(svg_path,png_path)
    print(json.dumps({'folder':str(folder),'png':str(png_path),'json':str(json_path),'status':stationed['geometry_status'],
        'end_z':[stationed['end_left_z'],stationed['end_center_z'],stationed['end_right_z']],
        'max_grades':[stationed['maximum_abs_grade_left_edge'],stationed['maximum_abs_grade_centerline'],stationed['maximum_abs_grade_right_edge']]}))


def render(base,candidate,surface):
    helper=BasementRampParkingDesignReasonerV2();frame=helper._frame(base['site']['parcel'],base['site']['frontage'])
    inner=helper._to_local_polygon(base['physical_basement_wall']['inner_face'],frame);view=View(list(inner.exterior.coords)[:-1])
    W,H=1900,1160;out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="#f7f6f1"/>',
        text(48,48,'REAL PARCEL 2 — 15% CURVED RAMP STATIONED SURFACE CHECK',29,'bold'),
        text(48,80,'COMMON CENTERLINE STATIONS — NO DOWNSTREAM MANEUVER / PARKING GENERATION',16,'bold')]
    # Top view.
    out.append('<rect x="35" y="105" width="900" height="980" rx="8" fill="white" stroke="#8297a3" stroke-width="2"/>')
    out.append(text(60,145,'TOP VIEW — LEVEL CROSS-SECTIONS',20,'bold'))
    out.append('<svg x="70" y="165" width="820" height="850" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet">')
    out.append(f'<polygon points="{view.points(list(inner.exterior.coords)[:-1])}" fill="#edf1ef" stroke="#263a43" stroke-width="6"/>')
    left=[p+[0] if len(p)==2 else p for p in surface['left_edge_xy']];right=[p+[0] if len(p)==2 else p for p in surface['right_edge_xy']]
    boundary=surface['left_edge_xy']+list(reversed(surface['right_edge_xy']))
    out.append(f'<polygon points="{view.points(boundary)}" fill="#efb5c0" stroke="#a71734" stroke-width="4"/>')
    out.append(f'<polyline points="{view.points(surface["centerline_xy"])}" fill="none" stroke="#075fa8" stroke-width="6" stroke-dasharray="15 9"/>')
    out.append(f'<polyline points="{view.points(surface["left_edge_xy"])}" fill="none" stroke="#772036" stroke-width="5"/>')
    out.append(f'<polyline points="{view.points(surface["right_edge_xy"])}" fill="none" stroke="#772036" stroke-width="5"/>')
    step=max(1,len(surface['cross_sections'])//12)
    for section in surface['cross_sections'][::step]:out.append(f'<line x1="{view.p(section["left"])[0]}" y1="{view.p(section["left"])[1]}" x2="{view.p(section["right"])[0]}" y2="{view.p(section["right"])[1]}" stroke="#58717d" stroke-width="3"/>')
    for label,key,color in [('TANGENT IN','tangent_in_cross_section','#885000'),('TANGENT OUT','tangent_out_cross_section','#885000'),('END','end_cross_section','#b01630')]:
        section=surface[key];a=view.p(section['left']);b=view.p(section['right']);out.append(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="{color}" stroke-width="9"/>');out.append(text((a[0]+b[0])/2+12,(a[1]+b[1])/2,label,16,'bold',color))
    out.append('</svg>')
    # Side profile and grade evidence.
    out.append('<rect x="965" y="105" width="900" height="980" rx="8" fill="white" stroke="#8297a3" stroke-width="2"/>')
    out.append(text(990,145,'SIDE / ELEVATION EVIDENCE',20,'bold'))
    x0,y0,x1,y1=1030,190,1805,600;stations=surface['centerline_stations'];total=stations[-1]
    px=lambda s:x0+(x1-x0)*s/total;py=lambda z:y0+(0-z)/2.4*(y1-y0)
    out.append(f'<line x1="{x0}" y1="{py(0)}" x2="{x1}" y2="{py(0)}" stroke="#777" stroke-width="2"/>')
    out.append(f'<line x1="{x0}" y1="{py(-2.4)}" x2="{x1}" y2="{py(-2.4)}" stroke="#777" stroke-width="2"/>')
    colors=[('#b01630',surface['left_edge_z'],'LEFT'),('#075fa8',surface['centerline_z'],'CENTER'),('#25833b',surface['right_edge_z'],'RIGHT')]
    for color,zs,label in colors:
        points=' '.join(f'{px(s):.2f},{py(z):.2f}' for s,z in zip(stations,zs));out.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="5"/>');out.append(text(x1-105,py(zs[-1])-12,label,14,'bold',color))
    out.append(text(x0,py(0)-14,'START +0.00',16,'bold'));out.append(text(x1-170,py(-2.4)+34,'END -2.40',16,'bold'))
    out.append(text(990,650,'LOCAL LONGITUDINAL GRADE EVIDENCE',19,'bold'))
    rows=[('LEFT edge',surface['maximum_abs_grade_left_edge']),('CENTERLINE',surface['maximum_abs_grade_centerline']),('RIGHT edge',surface['maximum_abs_grade_right_edge'])]
    for i,(label,value) in enumerate(rows):out.append(text(1010,695+i*38,f'{label}: max |grade| = {100*value:.4f}%  (limit 15.0000%)',17,'bold' if i==1 else 'normal'))
    out.append(text(1010,835,f"END LEFT   {surface['end_left_z']:.3f} m",20,'bold','#b01630'))
    out.append(text(1010,875,f"END MID    {surface['end_center_z']:.3f} m",20,'bold','#075fa8'))
    out.append(text(1010,915,f"END RIGHT  {surface['end_right_z']:.3f} m",20,'bold','#25833b'))
    out.append(text(1010,965,f"END LEVEL ERROR = {surface['end_cross_section_level_error']:.9f} m",17,'bold'))
    out.append(text(1010,1005,f"SURFACE TWIST STATUS = {surface['surface_twist_status'].upper()}",17,'bold'))
    out.append(text(1010,1045,f"REDISTRIBUTION = {surface['grade_redistribution_status'].upper()}",15,'bold','#b01630'))
    out.append(text(1010,1075,f"DROP SHORTFALL = {surface['vertical_drop_shortfall']:.4f} m",15,'bold','#b01630'))
    out.append(text(48,1125,'HUMAN VISUAL ACCEPTANCE PENDING | NO PHYSICAL RAMP PUBLISHED',16,'bold'))
    out.append('</svg>');return ''.join(out)


if __name__=='__main__':main()
