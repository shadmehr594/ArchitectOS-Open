"""Render human-readable diagnostics from an existing Parcel-2 evidence run.

This script never invokes a design reasoner and never publishes rejected
candidates as architecture. It reads immutable JSON evidence and writes only
diagnostic SVG/PNG/report artifacts.
"""

import json
from math import atan2, cos, hypot, pi, sin
from pathlib import Path
import subprocess
import sys

from shapely.geometry import Polygon

from core.cad.cad_import_engine import CADImportEngine


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = ROOT / "exports" / "DEFAULT" / "basement_ramp_parking_v2_south_20260908_230910_327693"
W, H = 1800, 1300


def esc(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class View:
    def __init__(self, points, left=90, top=150, right=520, bottom=100):
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        self.minx, self.miny, self.maxx, self.maxy = min(xs), min(ys), max(xs), max(ys)
        self.scale = min((W-left-right)/(self.maxx-self.minx), (H-top-bottom)/(self.maxy-self.miny))
        self.left, self.bottom = left, bottom

    def p(self, point):
        return (self.left+(point[0]-self.minx)*self.scale,
                H-self.bottom-(point[1]-self.miny)*self.scale)

    def points(self, values):
        return " ".join(f"{x:.2f},{y:.2f}" for x, y in map(self.p, values))


def text(x, y, value, size=22, weight="normal", fill="#20242a", anchor="start"):
    return f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{esc(value)}</text>'


def dimension(view, a, b, offset, label):
    ax, ay = view.p(a); bx, by = view.p(b)
    dx, dy = bx-ax, by-ay; length = hypot(dx, dy) or 1
    nx, ny = -dy/length, dx/length
    a2, b2 = (ax+nx*offset, ay+ny*offset), (bx+nx*offset, by+ny*offset)
    angle = atan2(b2[1]-a2[1], b2[0]-a2[0])*180/pi
    mx, my = (a2[0]+b2[0])/2, (a2[1]+b2[1])/2
    return (f'<g stroke="#48515c" stroke-width="1.2" fill="none">'
            f'<line x1="{ax}" y1="{ay}" x2="{a2[0]}" y2="{a2[1]}"/>'
            f'<line x1="{bx}" y1="{by}" x2="{b2[0]}" y2="{b2[1]}"/>'
            f'<line x1="{a2[0]}" y1="{a2[1]}" x2="{b2[0]}" y2="{b2[1]}" marker-start="url(#tick)" marker-end="url(#tick)"/>'
            f'</g><text x="{mx}" y="{my-6}" transform="rotate({angle} {mx} {my-6})" font-family="Arial" font-size="17" fill="#303841" text-anchor="middle">{esc(label)}</text>')


def road_polygon(parcel, frontage, width):
    a, b = frontage; dx, dy = b[0]-a[0], b[1]-a[1]; length = hypot(dx, dy)
    normals = [[-dy/length, dx/length], [dy/length, -dx/length]]
    centroid = [sum(p[0] for p in parcel)/len(parcel), sum(p[1] for p in parcel)/len(parcel)]
    def dist(n):
        q=[(a[0]+b[0])/2+n[0],(a[1]+b[1])/2+n[1]]
        return hypot(q[0]-centroid[0],q[1]-centroid[1])
    n=max(normals,key=dist)
    return [a,b,[b[0]+n[0]*width,b[1]+n[1]*width],[a[0]+n[0]*width,a[1]+n[1]*width]]


def render_plan(report, output):
    parcel=report["parcel"]["polygon"]; basement=report["basement_footprint"]; f1=report["f1_footprint"]
    frontage=[report["road_access"]["start"],report["road_access"]["end"]]
    road=road_polygon(parcel,frontage,report["road_access"]["road_width"])
    all_points=parcel+basement+f1+road+report["stair_core_protected_zone"]
    for c in report["ramp_candidates"]: all_points += c["polygon"]+c["intersection_polygon"]
    v=View(all_points); s=[]
    s.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="#faf9f5"/>')
    s.append('<defs><pattern id="basement" width="12" height="12" patternUnits="userSpaceOnUse"><path d="M0,12 L12,0" stroke="#9db7d3" stroke-width="2"/></pattern><pattern id="core" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M0,0 L10,10 M10,0 L0,10" stroke="#d17b20" stroke-width="1.5"/></pattern><pattern id="conflict" width="8" height="8" patternUnits="userSpaceOnUse"><path d="M0,8 L8,0" stroke="#9d0016" stroke-width="3"/></pattern><marker id="arrow" markerWidth="12" markerHeight="12" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#9d0016"/></marker><marker id="tick" markerWidth="8" markerHeight="8" refX="4" refY="4"><path d="M1,7 L7,1" stroke="#48515c"/></marker></defs>')
    s.append(text(80,62,"REAL PARCEL 2 — SOUTH BASEMENT / RAMP DIAGNOSTIC",34,"bold")); s.append(text(80,98,"REJECTED CANDIDATES — DIAGNOSTIC ONLY | NO PHYSICAL RAMP PUBLISHED",20,"bold","#9d0016"))
    s.append(f'<polygon points="{v.points(road)}" fill="#dbe5ed" stroke="#33759d" stroke-width="2"/>')
    rx,ry=v.p([(sum(p[0] for p in road)/4),(sum(p[1] for p in road)/4)])
    s.append(text(rx,ry,"10m ROAD",28,"bold","#245b7a","middle"))
    s.append(f'<polygon points="{v.points(parcel)}" fill="none" stroke="#111820" stroke-width="4"/>')
    s.append(f'<polygon points="{v.points(basement)}" fill="url(#basement)" fill-opacity=".6" stroke="#1e5f9b" stroke-width="3"/>')
    s.append(f'<polygon points="{v.points(f1)}" fill="none" stroke="#6c7178" stroke-width="2.5" stroke-dasharray="14 9"/>')
    core=report["stair_core_protected_zone"]
    s.append(f'<polygon points="{v.points(core)}" fill="url(#core)" stroke="#b65d00" stroke-width="3"/>')
    cx,cy=v.p(Polygon(core).centroid.coords[0]); s.append(text(cx,cy-8,"STAIR / CORE",20,"bold","#8c4700","middle"));s.append(text(cx,cy+17,"PROTECTED ZONE",16,"bold","#8c4700","middle"))
    colors=["#c12d40","#7c3fb0"]
    for i,c in enumerate(report["ramp_candidates"]):
        color=colors[i]; poly=c["polygon"]; start,end=c["start"],c["end"]
        s.append(f'<polygon points="{v.points(poly)}" fill="{color}" fill-opacity=".16" stroke="{color}" stroke-width="3" stroke-dasharray="10 6"/>')
        sx,sy=v.p(start); ex,ey=v.p(end)
        s.append(f'<line x1="{sx}" y1="{sy}" x2="{ex}" y2="{ey}" stroke="{color}" stroke-width="2" stroke-dasharray="5 5" marker-end="url(#arrow)"/>')
        callout_x, callout_y = 770, 650+i*145
        mx,my=(sx+ex)/2,(sy+ey)/2
        s.append(f'<polyline points="{mx},{my} {callout_x-25},{callout_y-18} {callout_x},{callout_y-18}" fill="none" stroke="{color}" stroke-width="1.5"/>')
        s.append(text(callout_x,callout_y,f"RAMP CANDIDATE {i+1}",20,"bold",color)); s.append(text(callout_x,callout_y+25,"REJECTED — DIAGNOSTIC ONLY",17,"bold",color))
        s.append(text(callout_x,callout_y+52,f"WIDTH = {c['width']:.2f}m | RUN = {c['run']:.2f}m",16,"normal",color)); s.append(text(callout_x,callout_y+75,"SLOPE / ΔZ = UNRESOLVED",16,"normal",color))
        s.append(text(sx+12,sy-(45 if i==0 else 8),"RAMP START",16,"bold",color)); s.append(text(sx+12,sy-(25 if i==0 else -12),"EL = UNRESOLVED",15,"normal",color))
        s.append(text(ex+12,ey+20,"RAMP END",16,"bold",color)); s.append(text(ex+12,ey+40,"EL = UNRESOLVED",15,"normal",color))
        inter=c["intersection_polygon"]
        if inter:
            s.append(f'<polygon points="{v.points(inter)}" fill="url(#conflict)" stroke="#9d0016" stroke-width="3"/>')
            ix,iy=v.p(Polygon(inter).representative_point().coords[0]); cy=430+i*72
            s.append(f'<polyline points="{ix},{iy} 745,{cy-8} 770,{cy-8}" fill="none" stroke="#760010" stroke-width="1.5"/>')
            s.append(text(770,cy,f"CONFLICT AREA — CANDIDATE {i+1}",15,"bold","#760010")); s.append(text(770,cy+21,f"AREA = {c['intersection_area']:.3f} m²",14,"bold","#760010"))
        s.append(dimension(v,poly[0],poly[-1],-28,f"{c['width']:.2f} m")); s.append(dimension(v,start,end,25,f"RUN {c['run']:.2f} m"))
    for i,(a,b) in enumerate(zip(parcel,parcel[1:]+parcel[:1])):
        s.append(dimension(v,a,b,35 if i in (0,3) else -35,f"{hypot(b[0]-a[0],b[1]-a[1]):.3f} m"))
    a,b=frontage; s.append(f'<line x1="{v.p(a)[0]}" y1="{v.p(a)[1]}" x2="{v.p(b)[0]}" y2="{v.p(b)[1]}" stroke="#0076a8" stroke-width="8"/>')
    fx,fy=v.p([(a[0]+b[0])/2,(a[1]+b[1])/2]); s.append(text(fx,fy-22,"VEHICLE ACCESS EDGE",18,"bold","#00648f","middle"))
    pc=Polygon(parcel).centroid.coords[0]; px,py=v.p(pc); s.append(text(px,py+110,"PARCEL 2",25,"bold","#111820","middle"));s.append(text(px,py+137,f"AREA = {report['parcel']['area']:.3f} m²",18,"normal","#111820","middle"))
    bc=Polygon(basement).centroid.coords[0]; bx,by=v.p(bc); s.append(text(bx,by+150,"BASEMENT FOOTPRINT",19,"bold","#1e5f9b","middle"))
    fc=Polygon(f1).centroid.coords[0]; fpx,fpy=v.p(fc); s.append(text(fpx,fpy-25,"F1 FOOTPRINT (DASHED)",18,"bold","#626870","middle"))
    s.append(text(1325,180,"NORTH",20,"bold")); s.append(text(1325,208,"UNRESOLVED — marker has no vector",16,"normal","#9d0016"))
    s.append(text(1325,260,"CURRENT ARCHITECTURAL EVIDENCE",20,"bold"));
    for j,line in enumerate(["Vehicle opening: UNRESOLVED","Parking aisle/stalls: UNRESOLVED","Ramp slab void: UNRESOLVED","Separation joint: UNRESOLVED for non-rectangular parcel","No rejected candidate is physical architecture"]): s.append(text(1325,292+j*25,line,16))
    s.append(text(1325,455,"LEGEND",22,"bold"));
    legend=[("#111820","Parcel boundary"),("#0076a8","Road / access edge"),("#1e5f9b","Basement footprint / hatch"),("#6c7178","F1 footprint / dashed"),(colors[0],"Ramp candidate 1 — rejected"),(colors[1],"Ramp candidate 2 — rejected"),("#b65d00","Stair/core protected zone"),("#9d0016","Exact conflict polygon")]
    for j,(color,label) in enumerate(legend):
        y=490+j*34;s.append(f'<line x1="1325" y1="{y}" x2="1380" y2="{y}" stroke="{color}" stroke-width="6"/>');s.append(text(1395,y+6,label,16))
    s.append('</svg>'); output.write_text("".join(s),encoding="utf-8")


def render_3d(report, output):
    parcel=report["parcel"]["polygon"]; basement=report["basement_footprint"]; core=report["stair_core_protected_zone"]
    def iso(p,z=0): return [p[0]-0.58*p[1],0.38*(p[0]+p[1])-2.8*z]
    shapes=[iso(p,-2.4) for p in parcel]+[iso(p,-2.4) for p in basement]+[iso(p,0) for p in core]
    for c in report["ramp_candidates"]: shapes += [iso(p,0) for p in c["polygon"]]
    v=View(shapes,left=100,top=160,right=480,bottom=120); s=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="#f8f8f6"/>']
    s.append(text(80,62,"REAL PARCEL 2 — 3D DIAGNOSTIC EVIDENCE",34,"bold"));s.append(text(80,98,"RAMP ELEVATIONS UNRESOLVED IN CURRENT CONTRACT — SURFACES SHOWN AT DIAGNOSTIC REFERENCE PLANE",18,"bold","#9d0016"))
    s.append(f'<polygon points="{v.points([iso(p,-2.4) for p in parcel])}" fill="#e8edf1" stroke="#555" stroke-width="2"/>')
    s.append(f'<polygon points="{v.points([iso(p,-2.4) for p in basement])}" fill="#b9d2e8" fill-opacity=".55" stroke="#1e5f9b" stroke-width="3"/>')
    core_bottom=[iso(p,-2.4) for p in core]; core_top=[iso(p,0) for p in core]
    s.append(f'<polygon points="{v.points(core_bottom)}" fill="#dc8b32" fill-opacity=".45" stroke="#a75400" stroke-width="2"/>');s.append(f'<polygon points="{v.points(core_top)}" fill="#f0a04a" fill-opacity=".45" stroke="#a75400" stroke-width="2"/>')
    for a,b in zip(core_bottom,core_top): x1,y1=v.p(a);x2,y2=v.p(b);s.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#a75400" stroke-width="2"/>')
    colors=["#c12d40","#7c3fb0"]
    for i,c in enumerate(report["ramp_candidates"]):
        surface=[iso(p,0) for p in c["polygon"]];s.append(f'<polygon points="{v.points(surface)}" fill="{colors[i]}" fill-opacity=".28" stroke="{colors[i]}" stroke-width="4" stroke-dasharray="12 7"/>')
        q=Polygon(surface).centroid.coords[0];x,y=v.p(q);s.append(text(x,y-10,f"CANDIDATE {i+1}",20,"bold",colors[i],"middle"));s.append(text(x,y+16,"REJECTED — DIAGNOSTIC ONLY",15,"bold",colors[i],"middle"))
    s.append(text(1340,220,"No physical ramp surface is published.",19,"bold","#9d0016"));s.append(text(1340,255,"Start/end Z and slope are not present",17));s.append(text(1340,280,"in the current runtime artifact.",17));s.append(text(1340,330,"STAIR / CORE PROTECTED VOLUME",18,"bold","#a75400"));s.append(text(1340,365,"Basement reference level = -2.40 m",17));s.append(text(1340,390,"F1 reference level = 0.00 m",17));s.append('</svg>');output.write_text("".join(s),encoding="utf-8")


def svg_to_png(svg, png):
    chrome = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    if not chrome.exists():
        raise RuntimeError("Chrome SVG rasterizer is unavailable")
    subprocess.run(
        [str(chrome), "--headless", "--no-sandbox", "--disable-gpu",
         "--disable-dev-shm-usage", f"--user-data-dir={png.parent / '.chrome_render'}",
         "--hide-scrollbars",
         "--window-size=1920,1280", f"--screenshot={png}", svg.as_uri()],
        check=False,
    )
    if not png.exists() or png.stat().st_size == 0:
        raise RuntimeError(f"SVG rasterization failed: {svg}")


def main():
    folder=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else DEFAULT_RUN
    summary=json.loads((folder/"acceptance_summary.json").read_text(encoding="utf-8")); model=json.loads((folder/"MODEL_GEOMETRY.json").read_text(encoding="utf-8"))
    cad=CADImportEngine().load({"file_object":str(ROOT/"tests/data/real_site/parcel_2_source.dxf")},target_parcel=2)
    parcel=cad["site"]["points"]; access=cad["site"]["site_constraints"]["access"]
    basement=next(x for x in model["slabs"] if x.get("floor")=="basement")["footprint"]["points"]
    f1=next(x for x in model["slabs"] if x.get("floor")=="F1")["footprint"]["points"]
    stair=next(x for x in model["vertical_geometry"] if x.get("type")=="stair_geometry")["protected_zone"]["points"]
    candidates=[]
    core=Polygon(stair)
    for index,item in enumerate(summary["vehicle_access_design"]["access_candidates"],1):
        poly=Polygon(item["driveway_corridor"]); intersection=poly.intersection(core)
        inter=list(intersection.exterior.coords)[:-1] if intersection.geom_type=="Polygon" and not intersection.is_empty else []
        candidates.append({"id":item["candidate_id"],"start":item["access_point"],"end":item["parking_target_point"],"polygon":item["driveway_corridor"],"width":item["driveway_width"],"run":item["required_run"],"start_elevation":None,"end_elevation":None,"delta_z":None,"slope":None,"geometry_status":item["geometry_status"],"status":"REJECTED","reason":item["selection_reason"],"intersection_polygon":inter,"intersection_area":intersection.area})
    edge=[parcel[access["edge_index"]],parcel[(access["edge_index"]+1)%len(parcel)]]
    report={"source_run":str(folder),"parcel":{"polygon":parcel,"area":cad["site"]["area"]},"road_access":{"start":edge[0],"end":edge[1],"length":hypot(edge[1][0]-edge[0][0],edge[1][1]-edge[0][1]),"road_width":access["road_width"],"source":access},"basement_footprint":basement,"f1_footprint":f1,"stair_core_protected_zone":stair,"ramp_candidates":candidates,"automated_geometry_pass":summary["acceptance"]["automated_geometry_pass"],"human_visual_acceptance":"pending","north":{"status":"unresolved","evidence":cad["site"]["site_constraints"]["north"]},"section":{"status":"not_generated_insufficient_elevation_evidence"}}
    plan_svg=folder/"PARCEL2_RAMP_DIAGNOSTIC_PLAN.svg";model_svg=folder/"PARCEL2_RAMP_DIAGNOSTIC_3D.svg"
    render_plan(report,plan_svg);render_3d(report,model_svg);svg_to_png(plan_svg,folder/"PARCEL2_RAMP_DIAGNOSTIC_PLAN.png");svg_to_png(model_svg,folder/"PARCEL2_RAMP_DIAGNOSTIC_3D.png")
    (folder/"PARCEL2_RAMP_DIAGNOSTIC_EVIDENCE.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"folder":str(folder),"plan":str(folder/"PARCEL2_RAMP_DIAGNOSTIC_PLAN.png"),"model":str(folder/"PARCEL2_RAMP_DIAGNOSTIC_3D.png"),"section":report["section"],"intersection_areas":[c["intersection_area"] for c in candidates]},ensure_ascii=False))


if __name__=="__main__": main()
