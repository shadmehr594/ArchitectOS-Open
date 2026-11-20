"""Generate fail-closed Parcel-2 Basement V2 review artifacts.

Rejected candidates are visual evidence only and are never published as
physical architecture, CAD, BIM, or IFC.
"""

from __future__ import annotations

from datetime import datetime
import json
from math import atan2, hypot, pi
from pathlib import Path
import subprocess

from shapely.geometry import LineString, Point, Polygon

from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import (
    BasementRampParkingDesignReasonerV2,
)
from core.architecture.reasoning.vehicle_access_edge_selection_reasoner_v1 import VehicleAccessEdgeSelectionReasonerV1
from core.cad.cad_import_engine import CADImportEngine
from core.site.separation_joint_engine import SeparationJointEngine


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "data" / "real_site" / "parcel_2_source.dxf"
W, H = 1900, 1300


def esc(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class View:
    def __init__(self, points, left=80, top=145, right=550, bottom=105):
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        self.minx, self.maxx, self.miny, self.maxy = min(xs), max(xs), min(ys), max(ys)
        self.scale = min((W-left-right)/(self.maxx-self.minx), (H-top-bottom)/(self.maxy-self.miny))
        self.left, self.bottom = left, bottom

    def p(self, point):
        return self.left+(point[0]-self.minx)*self.scale, H-self.bottom-(point[1]-self.miny)*self.scale

    def points(self, points):
        return " ".join(f"{x:.2f},{y:.2f}" for x, y in map(self.p, points))


def text(x, y, value, size=18, weight="normal", fill="#20252b", anchor="start"):
    return f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{esc(value)}</text>'


def dimension(view, a, b, offset, label):
    ax, ay = view.p(a); bx, by = view.p(b)
    dx, dy = bx-ax, by-ay; length = hypot(dx, dy) or 1.0
    nx, ny = -dy/length, dx/length
    a2=(ax+nx*offset, ay+ny*offset); b2=(bx+nx*offset, by+ny*offset)
    mx,my=(a2[0]+b2[0])/2,(a2[1]+b2[1])/2
    angle=atan2(b2[1]-a2[1],b2[0]-a2[0])*180/pi
    return (f'<g stroke="#46515c" stroke-width="1.2" fill="none"><line x1="{ax}" y1="{ay}" x2="{a2[0]}" y2="{a2[1]}"/>'
            f'<line x1="{bx}" y1="{by}" x2="{b2[0]}" y2="{b2[1]}"/><line x1="{a2[0]}" y1="{a2[1]}" x2="{b2[0]}" y2="{b2[1]}" marker-start="url(#tick)" marker-end="url(#tick)"/></g>'
            f'<text x="{mx}" y="{my-6}" transform="rotate({angle} {mx} {my-6})" font-family="Arial" font-size="15" fill="#303841" text-anchor="middle">{esc(label)}</text>')


def road_polygon(parcel, edge, width):
    a,b=edge; dx,dy=b[0]-a[0],b[1]-a[1]; length=hypot(dx,dy)
    normals=[[-dy/length,dx/length],[dy/length,-dx/length]]
    center=Polygon(parcel).centroid
    n=max(normals,key=lambda q:hypot((a[0]+b[0])/2+q[0]-center.x,(a[1]+b[1])/2+q[1]-center.y))
    return [a,b,[b[0]+n[0]*width,b[1]+n[1]*width],[a[0]+n[0]*width,a[1]+n[1]*width]]


def representatives(contract):
    groups={}
    for candidate in contract["design"]["candidates"]:
        ramp=candidate["ramp"]; groups.setdefault((ramp["family"],round(ramp["slope"],4)),[]).append(candidate)
    result=[]
    for _,items in sorted(groups.items(),key=lambda item:(item[0][0],item[0][1])):
        rank=min((len(item["rejection_reasons"]),-len(item["parking_stalls"])) for item in items)
        tied=[item for item in items if (len(item["rejection_reasons"]),-len(item["parking_stalls"]))==rank]
        representative=tied[0].copy()
        representative["diagnostic_equivalent_count"]=len(tied)
        result.append(representative)
    return result


def best_straight_diagnostic(contract):
    candidates=[c for c in contract["design"]["candidates"] if c["ramp"]["family"]=="straight"]
    return min(candidates,key=lambda c:(len(c["rejection_reasons"]),-len(c["parking_stalls"]),
        c["ramp_central_field_preservation"]["central_field_intersection_area"],c["ramp"]["run"],c["candidate_id"]))


def render_plan(contract, path):
    parcel=contract["site"]["parcel"]; wall=contract["physical_basement_wall"]
    frontage=contract["site"]["frontage"]; road=road_polygon(parcel,frontage,10.0)
    available=representatives(contract)
    straight=sorted((x for x in available if x["ramp"]["family"]=="straight"),key=lambda x:x["ramp"]["run"])
    l_shaped=[x for x in available if x["ramp"]["family"]=="l_shaped"]
    ramps=straight[:1]+l_shaped[:1]
    all_points=parcel+road+wall["outer_face"]+wall["inner_face"]
    for c in ramps: all_points += c["ramp"]["polygon"]+c["maneuvering_envelope"]
    view=View(all_points); out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="#fbfaf6"/>']
    out.append('<defs><pattern id="ramp" width="12" height="12" patternUnits="userSpaceOnUse"><path d="M0 12L12 0" stroke="#b42335" stroke-width="2"/></pattern><pattern id="fail" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M0 0L10 10M10 0L0 10" stroke="#bd1e2c" stroke-width="1.6"/></pattern><marker id="arrow" markerWidth="12" markerHeight="12" refX="9" refY="4" orient="auto"><path d="M0 0L9 4L0 8Z" fill="#a81626"/></marker><marker id="tick" markerWidth="8" markerHeight="8" refX="4" refY="4"><path d="M1 7L7 1" stroke="#46515c"/></marker></defs>')
    out += [text(70,55,"REAL PARCEL 2 — BASEMENT / RAMP / PARKING V2",32,"bold"),text(70,90,"ARCHITECTURAL REJECTION PLAN — NO CANDIDATE PUBLISHED",19,"bold","#a81626")]
    out.append(f'<polygon points="{view.points(road)}" fill="#d7e6ee" stroke="#28749b" stroke-width="2"/>')
    rc=Polygon(road).centroid; rx,ry=view.p([rc.x,rc.y]); out.append(text(rx,ry,"10m ROAD",25,"bold","#215b78","middle"))
    out.append(f'<polygon points="{view.points(parcel)}" fill="none" stroke="#121820" stroke-width="4"/>')
    out.append(f'<polygon points="{view.points(wall["outer_face"])}" fill="#d9e7f2" fill-opacity=".42" stroke="#1e6197" stroke-width="3"/>')
    out.append(f'<polygon points="{view.points(wall["centerline"])}" fill="none" stroke="#29343d" stroke-width="2"/>')
    out.append(f'<polygon points="{view.points(wall["inner_face"])}" fill="none" stroke="#29343d" stroke-width="2"/>')
    colors=["#c12d40","#7541aa","#d17714","#27806f","#3366a8","#8b4d3d"]
    for index,c in enumerate(ramps):
        ramp=c["ramp"]; color=colors[index%2]
        out.append(f'<polygon points="{view.points(ramp["polygon"])}" fill="url(#ramp)" fill-opacity=".34" stroke="{color}" stroke-width="3"/>')
        sx,sy=view.p(ramp["start"]); ex,ey=view.p(ramp["end"])
        out.append(f'<line x1="{sx}" y1="{sy}" x2="{ex}" y2="{ey}" stroke="{color}" stroke-width="3" marker-end="url(#arrow)"/>')
        out.append(f'<polygon points="{view.points(c["maneuvering_envelope"])}" fill="url(#fail)" fill-opacity=".25" stroke="#bd1e2c" stroke-width="2" stroke-dasharray="8 6"/>')
        escape=c.get("ramp_end_escape",{})
        if escape.get("searchable_escape_field_polygon"):
            out.append(f'<polygon points="{view.points(escape["searchable_escape_field_polygon"])}" fill="#5aa85a" fill-opacity=".12" stroke="#397d31" stroke-width="2" stroke-dasharray="5 4"/>')
        for stall_index,stall in enumerate(c.get("parking_stalls",[]),1):
            out.append(f'<polygon points="{view.points(stall)}" fill="#d8dfc5" stroke="#61753d" stroke-width="2"/>')
            center=Polygon(stall).centroid;x,y=view.p([center.x,center.y]);out.append(text(x,y,f"P-{stall_index:02d}",15,"bold","#425329","middle"))
        out += [text(sx+8,sy-18,f"RAMP {index+1} START  EL +0.00",15,"bold",color),text(ex+8,ey+22,"END  EL -2.40",15,"bold",color)]
        out.append(dimension(view,ramp["polygon"][0],ramp["polygon"][3],-22,"WIDTH 3.50 m"))
        out.append(dimension(view,ramp["start"],ramp["end"],22,f"RUN {ramp['run']:.3f} m | SLOPE {ramp['slope']*100:.0f}%"))
    for i,(a,b) in enumerate(zip(parcel,parcel[1:]+parcel[:1])):
        out.append(dimension(view,a,b,38 if i in (0,3) else -38,f"{hypot(b[0]-a[0],b[1]-a[1]):.3f} m"))
    a,b=frontage; ax,ay=view.p(a); bx,by=view.p(b); out.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="#007aa5" stroke-width="8"/>')
    fx,fy=(ax+bx)/2,(ay+by)/2; out.append(text(fx,fy-18,"VEHICLE ACCESS FRONTAGE — 10.000 m","16","bold","#006b91","middle"))
    px,py=view.p([Polygon(parcel).centroid.x,Polygon(parcel).centroid.y]); out += [text(px,py+125,"PARCEL 2",23,"bold",anchor="middle"),text(px,py+150,"AREA 200.000 m²",16,anchor="middle")]
    out += [text(1390,165,"FIRST PROVEN FAILURE",21,"bold","#a81626"),text(1390,200,"Vehicle escape + two stalls resolve",17),text(1390,225,"but protected pedestrian/core chain",17),text(1390,250,"is not yet geometrically resolved.",17),text(1390,280,"Turning circle is NOT required",17,"bold")]
    stall_candidates=sum(len(x.get("parking_stalls",[]))>=2 for x in contract["design"]["candidates"]);max_stalls=max((len(x.get("parking_stalls",[])) for x in contract["design"]["candidates"]),default=0)
    escape_candidates=sum(x.get("ramp_end_escape",{}).get("geometry_status")=="resolved" for x in contract["design"]["candidates"])
    out += [text(1390,345,"PARKING RESULT",20,"bold"),text(1390,380,f"Connected END escape candidates: {escape_candidates}",17,"bold","#425329"),text(1390,405,f"Candidates with ≥2 stalls: {stall_candidates}",17,"bold","#425329"),text(1390,430,f"Maximum valid topology capacity: {max_stalls}",17),text(1390,455,"Pedestrian route: NOT RESOLVED",17),text(1390,480,"Core placement: NOT SELECTED",17)]
    out += [text(1390,545,"CORE EVIDENCE",20,"bold"),text(1390,580,"2 feasible sizing configurations",17),text(1390,605,"4.40 × 4.20 m / rotated",17),text(1390,630,"Stair reserve 2.40 × 4.20 m",17),text(1390,655,"Elevator clear 1.80 × 1.80 m",17),text(1390,680,"Lobby clear 1.50 × 1.50 m",17)]
    out += [text(1390,745,"LEGEND",20,"bold"),text(1390,780,"Blue: physical basement wall band",16),text(1390,805,"Red/Purple: rejected ramp surfaces",16),text(1390,830,"Cross hatch: maneuver/aisle field",16),text(1390,855,"Green dashed: connected END escape field",16),text(1390,910,"NORTH: UNRESOLVED IN SOURCE",16,"bold")]
    out.append('</svg>'); path.write_text("".join(out),encoding="utf-8")


def iso(point,z): return [point[0]-.58*point[1],.38*(point[0]+point[1])-2.8*z]


def project_ramp_surface_from_contract(ramp):
    surface=ramp["surface_3d"]
    return {"vertices_3d":surface["vertices"],"faces":surface["faces"],
            "projected":[iso(vertex[:2],vertex[2]) for vertex in surface["vertices"]]}


def render_3d(contract,path):
    wall=contract["physical_basement_wall"]; candidate=best_straight_diagnostic(contract);ramp=candidate["ramp"]
    road=road_polygon(contract["site"]["parcel"],contract["site"]["frontage"],3.0)
    mesh=project_ramp_surface_from_contract(ramp)
    allp=[iso(p,-2.4) for p in wall["inner_face"]]+[iso(p,0) for p in road]+mesh["projected"]
    view=View(allp,left=100,top=150,right=530,bottom=110); out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="#f8f8f5"/>']
    out.append('<defs><marker id="arrow" markerWidth="12" markerHeight="12" refX="9" refY="4" orient="auto"><path d="M0 0L9 4L0 8Z" fill="#ffffff" stroke="#8f1020"/></marker></defs>')
    out += [text(70,58,"REAL PARCEL 2 — BASEMENT V2 3D REJECTION VIEW",31,"bold"),text(70,94,"FULL-WIDTH INCLINED SURFACES — DIAGNOSTIC ONLY, NOT PHYSICAL ARCHITECTURE",18,"bold","#a81626")]
    floor=[iso(p,-2.4) for p in wall["inner_face"]]; out.append(f'<polygon points="{view.points(floor)}" fill="#bcd4e6" fill-opacity=".72" stroke="#28658f" stroke-width="3"/>')
    road3d=[iso(p,0) for p in road];out.append(f'<polygon points="{view.points(road3d)}" fill="#d7e3e9" stroke="#28749b" stroke-width="3"/>')
    outer0=[iso(p,-2.4) for p in wall["outer_face"]]; outer1=[iso(p,0) for p in wall["outer_face"]]
    for a,b,c,d in zip(outer0,outer0[1:]+outer0[:1],outer1[1:]+outer1[:1],outer1): out.append(f'<polygon points="{view.points([a,b,c,d])}" fill="#9da8b1" fill-opacity=".38" stroke="#52606b" stroke-width="1.5"/>')
    surf=mesh["projected"]
    for face in mesh["faces"]:
        out.append(f'<polygon points="{view.points([surf[index] for index in face])}" fill="#c12d40" fill-opacity=".58" stroke="#9e1727" stroke-width="3"/>')
    sem=ramp["semantic_edges"];start_mid=[sum(v[i] for v in sem["start_vertices"])/2 for i in range(3)];end_mid=[sum(v[i] for v in sem["end_vertices"])/2 for i in range(3)]
    ps=view.p(iso(start_mid[:2],start_mid[2]));pe=view.p(iso(end_mid[:2],end_mid[2]))
    out.append(f'<line x1="{ps[0]}" y1="{ps[1]}" x2="{pe[0]}" y2="{pe[1]}" stroke="#fff" stroke-width="5" marker-end="url(#arrow)"/>')
    out += [text(ps[0],ps[1]-18,"START +0.00",18,"bold","#8f1020","middle"),text(pe[0],pe[1]+28,"END -2.40",18,"bold","#8f1020","middle"),text((ps[0]+pe[0])/2,(ps[1]+pe[1])/2-15,"DOWN TO BASEMENT",17,"bold","#fff","middle")]
    rc=Polygon(road3d).centroid;rx,ry=view.p([rc.x,rc.y]);out.append(text(rx,ry,"ROAD +0.00",21,"bold","#205a78","middle"))
    fc=Polygon(floor).centroid;fx,fy=view.p([fc.x,fc.y]);out.append(text(fx,fy+65,"BASEMENT -2.40",21,"bold","#205a78","middle"))
    datum_xy=ramp["start"]
    datum0=view.p(iso(datum_xy,0.0));datumb=view.p(iso(datum_xy,-2.4))
    out.append(f'<line x1="{datum0[0]}" y1="{datum0[1]}" x2="{datumb[0]}" y2="{datumb[1]}" stroke="#1f2933" stroke-width="3" stroke-dasharray="7 5"/>')
    out.append(text(datum0[0]+18,(datum0[1]+datumb[1])/2,"ΔZ = 2.40 m",17,"bold","#1f2933"))
    out += [text(1390,205,"VERTICAL SEPARATION = 2.40 m",18,"bold"),text(1390,245,f"DIAGNOSTIC {ramp['slope']*100:.0f}% | RUN {ramp['run']:.3f}m",17),text(1390,275,"WIDTH 3.50 m",17),text(1390,325,"Preview vertices = contract vertices",17,"bold","#267339"),text(1390,365,"NO PHYSICAL RAMP PUBLISHED",17,"bold","#a81626")]
    out.append('</svg>'); path.write_text("".join(out),encoding="utf-8")


def render_alternatives(contract,path):
    reps=representatives(contract); desired=[]
    for slope in (.15,.16,.17):
        desired += [x for x in reps if x["ramp"]["family"]=="straight" and abs(x["ramp"]["slope"]-slope)<1e-6][:1]
    l_items=[x for x in contract["design"]["candidates"] if x["ramp"]["family"]=="l_shaped"]
    if l_items:
        desired += [min(l_items,key=lambda x:x["ramp_central_field_preservation"]["central_field_intersection_area"])]
        desired += [max(l_items,key=lambda x:x["ramp_central_field_preservation"]["central_field_intersection_area"])]
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="1100"><rect width="100%" height="100%" fill="#fbfaf6"/>',text(65,58,"PARCEL 2 — BASEMENT V2 ALTERNATIVE COMPARISON",31,"bold"),text(65,92,"ALL ALTERNATIVES REJECTED — DIAGNOSTIC ONLY",18,"bold","#a81626")]
    for i,c in enumerate(desired):
        x=50+(i%3)*610; y=135+(i//3)*450; ramp=c["ramp"];quality=c["ramp_central_field_preservation"]
        out.append(f'<rect x="{x}" y="{y}" width="575" height="410" rx="8" fill="#fff" stroke="#b8bec4" stroke-width="2"/>')
        role=("L-PERIMETER" if i==3 else "L-CENTRAL-CUT" if i==4 else "STRAIGHT")
        label=role+f" — {ramp['slope']*100:.0f}%"
        out += [text(x+20,y+38,label,21,"bold"),text(x+20,y+70,"STATUS: REJECTED",17,"bold","#a81626"),text(x+20,y+102,f"Run: {ramp['run']:.3f}m | stalls: {len(c['parking_stalls'])}",15),text(x+20,y+130,f"Ramp intrusion: {quality['ramp_intrusion_area']:.2f} m²",15),text(x+20,y+158,f"Central intrusion: {quality['central_field_intersection_area']:.2f} m²",15),text(x+20,y+186,f"Perimeter adjacency: {quality['perimeter_adjacency_ratio']:.2f}",15),text(x+20,y+214,f"Contiguous field: {quality['largest_remaining_contiguous_field']:.2f} m²",15),text(x+20,y+242,"Core: candidate / not selected",15),text(x+20,y+268,"Pedestrian: pending",15)]
        for j,reason in enumerate(c["rejection_reasons"][:4]): out.append(text(x+20,y+302+j*23,"• "+reason,13,fill="#7c1721"))
    out += [text(65,1060,"No first/nearest/midpoint/random selection. Human visual acceptance remains pending.",17,"bold"),'</svg>']
    path.write_text("".join(out),encoding="utf-8")


def render_maneuvering_fix(contract,path):
    reps=representatives(contract); desired=[]
    for slope in (.15,.17): desired += [x for x in reps if x["ramp"]["family"]=="straight" and abs(x["ramp"]["slope"]-slope)<1e-6][:1]
    desired += [x for x in reps if x["ramp"]["family"]=="l_shaped"][:1]
    inner=contract["physical_basement_wall"]["inner_face"]; bounds=Polygon(inner).bounds
    def mini(points,x,y,w=500,h=700):
        minx,miny,maxx,maxy=bounds; scale=min(w/(maxx-minx),h/(maxy-miny))
        return " ".join(f"{x+(p[0]-minx)*scale:.1f},{y+h-(p[1]-miny)*scale:.1f}" for p in points)
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="1200"><rect width="100%" height="100%" fill="#fbfaf6"/>',text(60,55,"PARCEL 2 — MANEUVERING PLACEMENT FIX",31,"bold"),text(60,90,"OLD SERIAL PLACEMENT vs SEARCHED LATERAL / AISLE-SHARED PLACEMENT",18,"bold")]
    for i,c in enumerate(desired):
        x=60+i*605;y=165;r=c["ramp"]
        out.append(f'<rect x="{x}" y="{y}" width="560" height="850" fill="#fff" stroke="#bac1c7" stroke-width="2"/>')
        out.append(f'<polygon points="{mini(inner,x+25,y+90)}" fill="#edf3f7" stroke="#275e84" stroke-width="2"/>')
        out.append(f'<polygon points="{mini(r["polygon"],x+25,y+90)}" fill="#c12d40" fill-opacity=".24" stroke="#a81626" stroke-width="3"/>')
        out.append(f'<polygon points="{mini(c["old_invalid_serial_maneuvering_polygon"],x+25,y+90)}" fill="none" stroke="#a81626" stroke-width="2" stroke-dasharray="7 5"/>')
        out.append(f'<polygon points="{mini(c["maneuvering_envelope"],x+25,y+90)}" fill="#68a65c" fill-opacity=".34" stroke="#397d31" stroke-width="3"/>')
        for n,stall in enumerate(c.get("parking_stalls",[]),1): out.append(f'<polygon points="{mini(stall,x+25,y+90)}" fill="#d7dfbd" stroke="#52692f" stroke-width="2"/>')
        label=("STRAIGHT" if r["family"]=="straight" else "L-SHAPED")+f" {r['slope']*100:.0f}%"
        out += [text(x+25,y+40,label,21,"bold"),text(x+25,y+70,f"RUN {r['run']:.3f}m",16),text(x+25,y+815,"Green = searched maneuver/aisle field",15,"bold","#397d31"),text(x+25,y+840,"Red dashed = old invalid serial placement",15,"bold","#a81626")]
    out += [text(60,1080,"Maneuvering and aisle are one shared functional field. No mandatory 10m circle is used.",18,"bold"),text(60,1115,"All displayed alternatives remain unselected until pedestrian/core coordination is resolved.",17),'</svg>']
    path.write_text("".join(out),encoding="utf-8")


def render_side_check(contract,path):
    candidate=best_straight_diagnostic(contract);ramp=candidate["ramp"];run=ramp["run"]
    x0,x1=220,1500;y0,y1=260,830
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="1050"><rect width="100%" height="100%" fill="#fbfaf6"/>',text(65,58,"PARCEL 2 — RAMP SIDE SEMANTIC CHECK",31,"bold"),text(65,94,"Exact production surface evidence; no renderer-side Z reconstruction",18,"bold")]
    out += [f'<line x1="80" y1="{y0}" x2="{x0}" y2="{y0}" stroke="#275f82" stroke-width="5"/>',f'<line x1="{x1}" y1="{y1}" x2="1780" y2="{y1}" stroke="#275f82" stroke-width="5"/>',f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="#a81626" stroke-width="12"/>']
    out += [text(80,y0-24,"ROAD +0.00",22,"bold","#275f82"),text(x0,y0-25,"START +0.00",21,"bold","#a81626","middle"),text(x1,y1+42,"END -2.40",21,"bold","#a81626","middle"),text(1780,y1+42,"BASEMENT -2.40",22,"bold","#275f82","end"),text((x0+x1)/2,(y0+y1)/2-25,"DOWN TO BASEMENT →",23,"bold","#a81626","middle"),text((x0+x1)/2,930,f"RUN = {run:.3f} m | ΔZ = -2.40 m | SLOPE = {ramp['slope']*100:.0f}%",21,"bold","#28313a","middle")]
    out.append(f'<line x1="{x0}" y1="900" x2="{x1}" y2="900" stroke="#46515c" stroke-width="2"/><line x1="{x0}" y1="880" x2="{x0}" y2="920" stroke="#46515c" stroke-width="2"/><line x1="{x1}" y1="880" x2="{x1}" y2="920" stroke="#46515c" stroke-width="2"/>')
    out.append('</svg>');path.write_text("".join(out),encoding="utf-8")


def render_vehicle_circulation_check(contract,path):
    candidates=[c for c in contract["design"]["candidates"] if c["ramp"]["family"]=="straight"
                and c.get("vehicle_circulation_spine",{}).get("geometry_status")=="resolved"]
    selected=[]
    for slope in (.15,.16,.17):
        group=[c for c in candidates if abs(c["ramp"]["slope"]-slope)<1e-7]
        if group: selected.append(min(group,key=lambda c:(-len(c["parking_stalls"]),len(c["rejection_reasons"]),c["candidate_id"])))
    inner=contract["physical_basement_wall"]["inner_face"]
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="1200"><rect width="100%" height="100%" fill="#fbfaf6"/>',
         text(60,55,"PARCEL 2 — VEHICLE CIRCULATION CHECK",31,"bold"),
         text(60,90,"Occupied-stall entry/exit validation at topology-clearance level",18,"bold")]
    for i,c in enumerate(selected):
        x=45+i*615;y=135; panel=[inner,c["ramp"]["polygon"],c["maneuvering_envelope"]]+c["parking_stalls"]
        view=View([p for poly in panel for p in poly],left=x+30,top=y+100,right=W-(x+560),bottom=250)
        out.append(f'<rect x="{x}" y="{y}" width="580" height="920" fill="#fff" stroke="#b7bec5" stroke-width="2"/>')
        out.append(f'<polygon points="{view.points(inner)}" fill="#edf3f7" stroke="#265e84" stroke-width="3"/>')
        spine=c["vehicle_circulation_spine"]
        if spine.get("vehicle_spine_polygon"): out.append(f'<polygon points="{view.points(spine["vehicle_spine_polygon"])}" fill="#6eaf67" fill-opacity=".28" stroke="#397d31" stroke-width="3"/>')
        out.append(f'<polygon points="{view.points(c["ramp"]["polygon"])}" fill="#c12d40" fill-opacity=".30" stroke="#a81626" stroke-width="3"/>')
        out.append(f'<polygon points="{view.points(c["maneuvering_envelope"])}" fill="#69a6d1" fill-opacity=".20" stroke="#27698f" stroke-width="2" stroke-dasharray="7 5"/>')
        for n,stall in enumerate(c["parking_stalls"],1):
            out.append(f'<polygon points="{view.points(stall)}" fill="#87909a" fill-opacity=".68" stroke="#313941" stroke-width="2"/>')
            pc=Polygon(stall).centroid;px,py=view.p([pc.x,pc.y]);out.append(text(px,py,f"P-{n:02d} OCCUPIED",13,"bold","#fff","middle"))
        for n,path_points in enumerate(spine.get("vehicle_spine_center_paths",[]),1):
            pts=view.points(path_points);out.append(f'<polyline points="{pts}" fill="none" stroke="#dd7b12" stroke-width="5" stroke-dasharray="10 5"/>')
        sx,sy=view.p(c["ramp"]["start"]);ex,ey=view.p(c["ramp"]["end"])
        out += [text(x+22,y+35,f"STRAIGHT {c['ramp']['slope']*100:.0f}%",21,"bold"),
                text(x+22,y+65,f"Run {c['ramp']['run']:.3f}m | stalls {len(c['parking_stalls'])}",16),
                text(x+22,y+90,f"Spine: CONNECTED | bottleneck {spine['minimum_bottleneck_width']:.2f}m",15,"bold","#397d31"),
                text(sx,sy-16,"ROAD / START",14,"bold","#a81626","middle"),text(ex,ey+20,"END / RETURN",14,"bold","#a81626","middle")]
        for n,result in enumerate(spine.get("stall_results",[]),1):
            out.append(text(x+22,y+850+n*22,f"P-{n:02d}: IN={result['incoming_path_exists']} OUT={result['outgoing_path_exists']} other stall occupied",13))
    out += [text(60,1110,"Green = connected vehicle spine | Blue = shared arrival/exit maneuvering field | Orange = stall return paths",17,"bold"),
            text(60,1140,"Core remains candidate-only until protected pedestrian connection resolves. No columns or beams generated.",16),'</svg>']
    path.write_text("".join(out),encoding="utf-8")


def render_ramp_topology_decision(contract,path):
    decisions=contract["design"]["ramp_topology_decisions"]
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="900"><rect width="100%" height="100%" fill="#fbfaf6"/>',
         text(60,55,"PARCEL 2 — RAMP TOPOLOGY DECISION",31,"bold"),
         text(60,92,"Direct post-END depth and connected lateral maneuvering are evaluated separately",18,"bold")]
    for i,d in enumerate(decisions):
        x=55+i*610;y=145
        out.append(f'<rect x="{x}" y="{y}" width="565" height="560" rx="8" fill="#fff" stroke="#b8bec4" stroke-width="2"/>')
        out += [text(x+22,y+42,f"STRAIGHT {d['slope']*100:.0f}%",23,"bold"),
                text(x+22,y+85,f"RUN = {d['straight_run']:.3f} m",18),
                text(x+22,y+120,f"DIRECT DEPTH AFTER END = {d['direct_remaining_depth']:.3f} m",18,"bold"),
                text(x+22,y+165,"CONNECTED LATERAL SEARCH = YES",17,"bold","#246c3a"),
                text(x+22,y+205,d["maneuvering_status"].replace("_"," ").upper(),17,"bold","#246c3a"),
                text(x+22,y+250,f"CONNECTED STRAIGHT CANDIDATES = {d['connected_straight_candidate_count']}",16),
                text(x+22,y+295,f"TURNED ALTERNATIVES EVALUATED = {len(d['turned_alternatives'])}",16)]
        if d["topology_change_request"]:
            out.append(text(x+22,y+345,"TOPOLOGY CHANGE REQUESTED",17,"bold","#a81626"))
        else:
            out.append(text(x+22,y+345,"NO FORCED TOPOLOGY CHANGE",17,"bold","#246c3a"))
        out += [text(x+22,y+410,"Straight remains subject to parking,",15),text(x+22,y+435,"pedestrian and core coordination.",15)]
    out += [text(60,790,"15% is not rejected only because direct depth is below 4.5m; lateral connected maneuvering was searched first.",17,"bold"),
            text(60,825,"No slope or topology is automatically selected. Human visual acceptance remains pending.",17),'</svg>']
    path.write_text("".join(out),encoding="utf-8")


def render_15_percent_topology_comparison(contract,path):
    decision=next(d for d in contract["design"]["ramp_topology_decisions"] if abs(d["slope"]-.15)<1e-9)
    transition=contract["design"]["optional_entrance_transition"]
    cards=[
        ("STRAIGHT 15%",f"RUN = {decision['straight_run']:.3f} m",decision["maneuvering_status"].replace("_"," ").upper(),
         f"CONNECTED OPTIONS = {decision['connected_straight_candidate_count']}","#eaf6ec","#246c3a"),
        ("PERIMETER-TURN 15%","NOT TRIGGERED", "STRAIGHT END HAS CONNECTED MANEUVERING",
         "NO FORCED ALTERNATIVE GENERATED","#f3f1eb","#655f51"),
        ("DOG-LEG 15%","NOT TRIGGERED", "STRAIGHT END HAS CONNECTED MANEUVERING",
         "FAMILY REMAINS AVAILABLE AFTER A PROVEN FAILURE","#f3f1eb","#655f51"),
        ("ENTRANCE TRANSITION","PENDING REQUIREMENT",f"SLOPE RANGE {transition['allowable_slope_range'][0]*100:.1f}%–{transition['allowable_slope_range'][1]*100:.1f}%",
         "TRANSITION LENGTH = UNRESOLVED","#fff2df","#a45e00"),
    ]
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="1000"><rect width="100%" height="100%" fill="#fbfaf6"/>',
         text(60,55,"PARCEL 2 — 15% RAMP TOPOLOGY COMPARISON",31,"bold"),
         text(60,92,"Required 16.000 m is total topology run; piecewise families activate only after straight connected-maneuvering failure.",17,"bold")]
    for i,(title,line1,line2,line3,fill,color) in enumerate(cards):
        x=55+(i%2)*920;y=145+(i//2)*360
        out.append(f'<rect x="{x}" y="{y}" width="850" height="300" rx="9" fill="{fill}" stroke="{color}" stroke-width="3"/>')
        out += [text(x+28,y+52,title,24,"bold",color),text(x+28,y+110,line1,19,"bold"),
                text(x+28,y+158,line2,17,"bold",color),text(x+28,y+207,line3,16),
                text(x+28,y+258,"HUMAN VISUAL ACCEPTANCE = PENDING",15,"bold","#6b4f00")]
    out += [text(60,900,"No Parcel-2 coordinate or slope-specific topology rule is used. Perimeter-turn and dog-leg are searched only after a geometry-proven request.",16,"bold"),'</svg>']
    path.write_text("".join(out),encoding="utf-8")


def render_multi_road_selection(selection,path):
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="800"><rect width="100%" height="100%" fill="#fbfaf6"/>',
         text(60,55,"MULTI-ROAD VEHICLE ACCESS SELECTION",31,"bold"),
         text(60,92,"Synthetic authoritative test fixture — REAL Parcel 2 is unchanged",18,"bold")]
    for i,e in enumerate(selection["evaluated_edges"]):
        x=90+i*850;y=155;selected=selection.get("selected_edge",{}).get("access_edge_id")==e["access_edge_id"]
        out.append(f'<rect x="{x}" y="{y}" width="720" height="440" rx="10" fill="{("#edf8ef" if selected else "#fff")}" stroke="{("#25823b" if selected else "#adb5bd")}" stroke-width="3"/>')
        shortest=min(e["required_ramp_runs"].values()) if e["ramp_required"] else 0.0
        out += [text(x+30,y+50,e["access_edge_id"],25,"bold"),text(x+30,y+100,f"ROAD ELEVATION = {e['road_elevation']:+.2f} m",19),
                text(x+30,y+145,f"PARKING LEVEL = {e['parking_level_z']:+.2f} m",19),text(x+30,y+190,f"ΔZ = {e['delta_z']:+.2f} m",19,"bold"),
                text(x+30,y+235,f"RAMP REQUIRED = {str(e['ramp_required']).upper()}",19,"bold"),text(x+30,y+280,f"SHORTEST DERIVED RUN = {shortest:.3f} m",18),
                text(x+30,y+340,"DIRECT VEHICLE ACCESS — NO RAMP REQUIRED" if not e["ramp_required"] else "ROAD → RAMP → BASEMENT",18,"bold",("#25823b" if selected else "#333")),
                text(x+30,y+395,"SELECTED" if selected else "EVALUATED ALTERNATIVE",20,"bold",("#25823b" if selected else "#755"))]
    out.append(text(60,700,"Selection uses hard validity before elevation/run ranking; a lower road with impossible geometry cannot win.",17,"bold"));out.append('</svg>')
    path.write_text("".join(out),encoding="utf-8")


def svg_to_png(svg,png):
    chrome=Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    subprocess.run([str(chrome),"--headless","--no-sandbox","--disable-gpu",f"--user-data-dir={png.parent/'.chrome'}","--hide-scrollbars","--window-size=1900,1300",f"--screenshot={png}",svg.as_uri()],check=True)


def main():
    cad=CADImportEngine().load({"file_object":str(SOURCE)},target_parcel=2); site=cad["site"]
    parcel=site["points"]; access=site["site_constraints"]["access"]; frontage=[parcel[access["edge_index"]],parcel[(access["edge_index"]+1)%4]]
    engine=SeparationJointEngine()
    outer=engine.resolve_buildable_envelope(parcel,{"edge_offsets":[0,.1,.1,.1]})["buildable_boundary"]
    center=engine.resolve_buildable_envelope(parcel,{"edge_offsets":[.1,.2,.2,.2]})["buildable_boundary"]
    inner=engine.resolve_buildable_envelope(parcel,{"edge_offsets":[.2,.3,.3,.3]})["buildable_boundary"]
    wall={"outer_face":outer,"centerline":center,"inner_face":inner,"thickness":.2,"height":2.4}
    req={"source":"user_project_requirement","evidence_status":"authoritative_for_current_test","levels":{"ground":0.,"basement":-2.4},"ramp":{"clear_width":3.5,"maximum_longitudinal_slope":.17,"allowable_slope_candidates":[.15,.16,.17],"required_headroom":2.2},"parking":{"minimum_count":2,"stall_width":2.5,"stall_depth":5.,"aisle_width":5.,"minimum_turning_radius":5.,"maneuvering_clear_zone":{"preferred":[5.,5.],"minimum":[4.5,4.5],"source":"user_project_requirement","evidence_status":"authoritative_for_current_test"}},"parking_pedestrian":{"required_clear_width":1.2},"core":{"stair_clear_width":1.2,"stair_reserved_zone":[2.4,4.2],"elevator_shaft_clear":[1.8,1.8],"enclosure_wall_thickness":.2,"lobby_clear":[1.5,1.5],"maximum_width":4.5,"maximum_depth":5.5,"elevator_required":True,"evidence_used":["user_project_requirement"]}}
    design=BasementRampParkingDesignReasonerV2().design(parcel,frontage,wall,req,{"inventory_status":"complete_empty","confirmed_fixed_obstacles":[]})
    edge_fixture=lambda edge_id,z:{"access_edge_id":edge_id,"geometry":[[0,0],[10,0]],"road_width":10.0,"road_elevation":z,"source":"synthetic_authoritative_test_edge","evidence_status":"authoritative_for_current_test","available_geometric_run":20.0,"parking_capacity":2,"central_field_fragmentation":0.0}
    multi_road=VehicleAccessEdgeSelectionReasonerV1().resolve([edge_fixture("ROAD A",0.0),edge_fixture("ROAD B",-2.4)],-2.4,[.15,.16,.17])
    candidate=best_straight_diagnostic({"design":design});semantic=candidate["ramp"]["semantic_edges"];frontage_line=LineString(frontage)
    start_distances=[frontage_line.distance(Point(vertex[:2])) for vertex in semantic["start_vertices"]]
    end_mid=[sum(vertex[i] for vertex in semantic["end_vertices"])/2 for i in range(2)];start_mid=[sum(vertex[i] for vertex in semantic["start_vertices"])/2 for i in range(2)]
    parcel_centroid=Polygon(parcel).centroid;direction=[end_mid[0]-start_mid[0],end_mid[1]-start_mid[1]]
    inward_dot=direction[0]*(parcel_centroid.x-start_mid[0])+direction[1]*(parcel_centroid.y-start_mid[1])
    preview_validation={"candidate_id":candidate["candidate_id"],"ramp_id":candidate["ramp_id"],"start_vertex_frontage_distances":start_distances,"end_midpoint":end_mid,"end_midpoint_inside_inner_clear_face":Polygon(inner).covers(Point(end_mid)),"direction_points_into_parcel":inward_dot>0,"inward_direction_dot_product":inward_dot,"start_z_values":[v[2] for v in semantic["start_vertices"]],"end_z_values":[v[2] for v in semantic["end_vertices"]],"renderer_uses_contract_vertices":True}
    preview_validation["status"]="passed" if max(start_distances)<=1e-6 and preview_validation["end_midpoint_inside_inner_clear_face"] and preview_validation["direction_points_into_parcel"] else "failed"
    contract={"contract":"Parcel2BasementV2HumanReviewContract","site":{"source":str(SOURCE),"parcel":parcel,"parcel_area":site["area"],"frontage":frontage,"road_width":access["road_width"],"fixed_obstacle_inventory":"complete_empty"},"requirements":req,"physical_basement_wall":wall,"basement_outer_area":Polygon(outer).area,"basement_inner_clear_area":Polygon(inner).area,"coverage_percent":Polygon(outer).area/site["area"]*100,"design":design,"multi_road_synthetic_acceptance":multi_road,"preview_validation":preview_validation,"publication":{"physical_ramp":False,"vehicle_opening":False,"ramp_slab_void":False},"human_visual_acceptance":"pending"}
    folder=ROOT/"exports"/"DEFAULT"/("parcel2_basement_v2_"+datetime.now().strftime("%Y%m%d_%H%M%S_%f"));folder.mkdir(parents=True)
    plan_svg=folder/"PARCEL2_BASEMENT_V2_PLAN.svg";model_svg=folder/"PARCEL2_BASEMENT_V2_3D.svg";alts_svg=folder/"PARCEL2_BASEMENT_V2_ALTERNATIVES.svg";fix_svg=folder/"PARCEL2_BASEMENT_V2_MANEUVERING_FIX.svg";side_svg=folder/"PARCEL2_RAMP_SIDE_CHECK.svg";circulation_svg=folder/"PARCEL2_VEHICLE_CIRCULATION_CHECK.svg";topology_svg=folder/"PARCEL2_RAMP_TOPOLOGY_DECISION.svg";comparison15_svg=folder/"PARCEL2_15_PERCENT_RAMP_TOPOLOGY_COMPARISON.svg";multi_svg=folder/"MULTI_ROAD_VEHICLE_ACCESS_SELECTION.svg"
    render_plan(contract,plan_svg);render_3d(contract,model_svg);render_alternatives(contract,alts_svg);render_maneuvering_fix(contract,fix_svg);render_side_check(contract,side_svg);render_vehicle_circulation_check(contract,circulation_svg);render_ramp_topology_decision(contract,topology_svg);render_15_percent_topology_comparison(contract,comparison15_svg);render_multi_road_selection(multi_road,multi_svg)
    svg_to_png(plan_svg,folder/"PARCEL2_BASEMENT_V2_PLAN.png");svg_to_png(model_svg,folder/"PARCEL2_BASEMENT_V2_3D.png");svg_to_png(alts_svg,folder/"PARCEL2_BASEMENT_V2_ALTERNATIVES.png");svg_to_png(fix_svg,folder/"PARCEL2_BASEMENT_V2_MANEUVERING_FIX.png");svg_to_png(side_svg,folder/"PARCEL2_RAMP_SIDE_CHECK.png");svg_to_png(circulation_svg,folder/"PARCEL2_VEHICLE_CIRCULATION_CHECK.png")
    svg_to_png(topology_svg,folder/"PARCEL2_RAMP_TOPOLOGY_DECISION.png");svg_to_png(comparison15_svg,folder/"PARCEL2_15_PERCENT_RAMP_TOPOLOGY_COMPARISON.png");svg_to_png(multi_svg,folder/"MULTI_ROAD_VEHICLE_ACCESS_SELECTION.png")
    (folder/"PARCEL2_BASEMENT_V2_CONTRACT.json").write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"output":str(folder),"status":design["status"],"candidates":len(design["candidates"]),"feasible":sum(c["geometry_status"]=="candidate" for c in design["candidates"]),"diagnostic":design.get("diagnostic"),"outer_area":contract["basement_outer_area"],"inner_area":contract["basement_inner_clear_area"]},ensure_ascii=False))


if __name__ == "__main__": main()
