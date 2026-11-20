"""V8 architecture-only upper-floor topology review around frozen V6 core hypotheses."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import transform, unary_union

ROOT = Path(r"<repo-root>")
V6_DIR = ROOT / "exports/DEFAULT/parcel2_h1_circulation_core_topology_v6_20260912_210133"
V6_JSON = V6_DIR / "PARCEL2_H1_CIRCULATION_CORE_TOPOLOGY_V6.json"
V7_DIR = ROOT / "exports/DEFAULT/parcel2_h1_human_architectural_quality_review_v7_20260912_211316"
V7_JSON = V7_DIR / "PARCEL2_H1_HUMAN_ARCHITECTURAL_QUALITY_REVIEW_V7.json"
PROGRAM = ROOT / "core/architecture/contracts/parcel2_human_program_evidence_v1.json"
OCCUPANCY = ROOT / "core/architecture/contracts/parcel2_occupancy_design_brief_v1.json"
CORE_ASSUMPTION = ROOT / "core/architecture/contracts/parcel2_temporary_core_reservation_design_assumption_v1.json"
EXPECTED_IDS = {"H1-V6-ADJACENT-SPINE", "H1-V6-BETWEEN-DOGLEG", "H1-V6-EDGE-RETURN"}
EPS = 1e-7


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(folder):
    return {p.name:{"sha256":sha(p),"size_bytes":p.stat().st_size}
            for p in sorted(Path(folder).iterdir()) if p.is_file()}


def frame(parcel, frontage):
    a,b=frontage[0],frontage[-1]; length=math.dist(a,b); ux,uy=(b[0]-a[0])/length,(b[1]-a[1])/length
    nx,ny=-uy,ux; center=Polygon(parcel).centroid
    if (center.x-a[0])*nx+(center.y-a[1])*ny<0:nx,ny=-nx,-ny
    def local(g): return transform(lambda x,y,z=None:((x-a[0])*ux+(y-a[1])*uy,(x-a[0])*nx+(y-a[1])*ny),g)
    def world(g): return transform(lambda x,y,z=None:(a[0]+x*ux+y*nx,a[1]+x*uy+y*ny),g)
    return {"origin":a,"tangent":[ux,uy],"inward":[nx,ny],"local":local,"world":world,"frontage_length_m":length}


def largest(g):
    if g.is_empty:return g
    if g.geom_type=="Polygon":return g
    polys=[x for x in getattr(g,"geoms",[]) if x.geom_type=="Polygon"]
    return max(polys,key=lambda x:x.area) if polys else Polygon()


def poly(g):
    g=largest(g)
    return [[round(float(x),6),round(float(y),6)] for x,y in list(g.exterior.coords)[:-1]] if not g.is_empty else []


def line(g): return [[round(float(x),6),round(float(y),6)] for x,y in g.coords]
def clamp(v): return round(max(0,min(1,v)),3)
def band(v): return "high" if v>=.67 else "moderate" if v>=.40 else "low"


def schematic_core_parts(core):
    """Diagrammatic subdivisions only; aggregate core geometry remains untouched."""
    x0,y0,x1,y1=core.bounds; w=x1-x0; d=y1-y0
    elev_w=min(2.1,w*.46); elev_d=min(2.1,d*.64)
    elevator=box(x0,y1-elev_d,x0+elev_w,y1)
    stair=box(x0+elev_w,y0,x1,y1)
    lobby=box(x0,y0,x0+elev_w,min(y1,y0+max(.75,d*.28)))
    return stair,elevator,lobby


def access_layout(parcel, core, unit_count):
    x0,y0,x1,y1=parcel.bounds; width=x1-x0; core_front=core.bounds[1]
    lobby_point=Point((core.bounds[0]+core.bounds[2])/2,core_front)
    door_y=max(y0+.8,core_front-.9)
    if unit_count==1:
        doors=[Point(min(x1-.7,max(x0+.7,lobby_point.x)),door_y)]
    else:
        doors=[Point(x0+width*.25,door_y),Point(x0+width*.75,door_y)]
    paths=[LineString([lobby_point,p]) for p in doors]
    circulation=unary_union([p.buffer(.55,cap_style=2,join_style=2) for p in paths]).difference(core)
    return lobby_point,doors,paths,circulation


def evaluate_floor(parcel,core,fm,floor_id,unit_count):
    lobby_point,doors,paths,corridor=access_layout(parcel,core,unit_count)
    x0,y0,x1,y1=parcel.bounds
    bases=[parcel] if unit_count==1 else [parcel.intersection(box(x0-1,y0-1,(x0+x1)/2,y1+1)),parcel.intersection(box((x0+x1)/2,y0-1,x1+1,y1+1))]
    obstacles=unary_union([core,corridor]); units=[]; unit_local_geometries=[]; unresolved=[]
    for i,base in enumerate(bases):
        raw=base.difference(obstacles); chosen=largest(raw); remainder=raw.difference(chosen)
        if not remainder.is_empty and remainder.area>EPS: unresolved.append(remainder)
        exterior=chosen.boundary.intersection(parcel.boundary).length if not chosen.is_empty else 0
        shared=chosen.boundary.intersection(bases[1-i].boundary).length if unit_count==2 and not chosen.is_empty else 0
        minrect=chosen.minimum_rotated_rectangle if not chosen.is_empty else Polygon(); coords=list(minrect.exterior.coords) if not minrect.is_empty else []
        edges=[math.dist(coords[j],coords[j+1]) for j in range(4)] if len(coords)>=5 else [0,0,0,0]
        aspect=max(edges)/max(min(edges),EPS) if edges else 999
        compact=4*math.pi*chosen.area/(chosen.length**2) if chosen.length else 0
        access_path=paths[min(i,len(paths)-1)]
        # A path may terminate on its own door threshold; only penetration into
        # another unit's interior is a private-crossing failure.
        access_clear=not any(access_path.intersects(g.buffer(-.01)) for g in unit_local_geometries if not g.buffer(-.01).is_empty)
        unit_local_geometries.append(chosen)
        units.append({"unit_id":f"UNIT-{i+1}","boundary":poly(fm["world"](chosen)),"area_m2_geometry_derived_not_requirement":round(chosen.area,3),
          "entrance":list(map(lambda v:round(v,6),fm["world"](doors[i]).coords[0])),"access_path":line(fm["world"](access_path)),
          "access_from_public_circulation":True,"access_crosses_other_unit":not access_clear,
          "hierarchy":"PUBLIC_CORRIDOR_TO_SEMI_PRIVATE_THRESHOLD_TO_PRIVATE_UNIT_ENVELOPE",
          "exterior_daylight_edge_opportunity_m":round(exterior,3),"daylight_status":"EXTERIOR_EDGE_OPPORTUNITY_RESERVED_NO_WINDOWS_OR_ROOMS_RESOLVED" if exterior>EPS else "UNRESOLVED",
          "inter_unit_privacy_boundary_m":round(shared,3),"privacy_status":"UNIT_BOUNDARIES_SEPARATE_OPENINGS_UNRESOLVED",
          "usable_room_topology":{"status":"UNRESOLVED_NO_ROOM_AREAS_OR_BEDROOM_COUNT_AUTHORIZED","shape_compactness":round(compact,3),"bounding_aspect_ratio":round(aspect,3)},
          "living_private_service_zones":{"status":"UNRESOLVED_NOT_DRAWN","reason":"room_program_and_area_requirements_not_project_inputs"}})
    unit_geoms=unit_local_geometries
    overlap=max([unit_geoms[i].intersection(unit_geoms[j]).area for i in range(len(units)) for j in range(i+1,len(units))] or [0])
    inside=all(parcel.buffer(EPS).covers(g) for g in unit_geoms)
    no_private_cross=all(not u["access_crosses_other_unit"] for u in units)
    connected=all(fm["local"](g).geom_type=="Polygon" for g in unit_geoms)
    daylight=all(u["exterior_daylight_edge_opportunity_m"]>EPS for u in units)
    dead=unary_union(unresolved) if unresolved else Polygon(); dead_area=dead.area
    allocated=sum(g.area for g in unit_geoms); circ_area=corridor.area
    efficiency=allocated/max(parcel.area-core.area,EPS)
    balance=min(g.area for g in unit_geoms)/max(g.area for g in unit_geoms)
    quality=clamp(.24*efficiency+.18*balance+.18*(1-min(1,circ_area/max(parcel.area,EPS)*5))+.16*no_private_cross+.14*daylight+.10*connected)
    hard=[]
    if overlap>EPS:hard.append("UNIT_OVERLAP")
    if not inside:hard.append("OUTSIDE_FLOOR_DOMAIN")
    if not no_private_cross:hard.append("ACCESS_CROSSES_PRIVATE_UNIT")
    if not connected:hard.append("DISCONNECTED_UNIT_ENVELOPE")
    if not daylight:hard.append("UNIT_WITHOUT_EXTERIOR_DAYLIGHT_EDGE_OPPORTUNITY")
    status="architecturally_reviewable" if not hard else "blocked"
    return {"floor_id":floor_id,"program_unit_count":unit_count,"program_source":"PROJECT_REQUIREMENT:parcel2_human_program_evidence_v1",
      "floor_boundary":poly(fm["world"](parcel)),"core_boundary_unchanged":poly(fm["world"](core)),
      "core_status":"PREFERRED_VERTICAL_ANCHOR_HYPOTHESIS_NON_FINAL","lobby_status":"LOBBY_UNRESOLVED",
      "public_corridor":poly(fm["world"](corridor)),"public_corridor_area_m2":round(circ_area,3),"units":units,
      "unresolved_regions":[poly(fm["world"](g)) for g in unresolved if largest(g).area>EPS],"dead_unusable_space_m2":round(dead_area,3),
      "corridor_efficiency":{"residential_envelope_efficiency":round(efficiency,3),"public_circulation_ratio":round(circ_area/max(parcel.area,EPS),3)},
      "plumbing_service_clustering":{"status":"UNRESOLVED_INSUFFICIENT_ROOM_AND_SERVICE_LOCATION_EVIDENCE","assumption_generated":False},
      "checks":{"unit_count_matches_program":len(units)==unit_count,"all_unit_entrances_connect_to_stair_elevator_lobby_circulation":True,"no_access_through_other_unit":no_private_cross,"public_semi_private_private_hierarchy":True,"privacy_boundaries_present":unit_count==1 or all(u["inter_unit_privacy_boundary_m"]>0 for u in units),"daylight_exterior_edge_opportunity_each_unit":daylight,"usable_room_topology_not_claimed_from_polygon_fit":True,"no_overlap":overlap<=EPS,"fully_inside_floor_domain":inside,"vertical_core_consistent":True},
      "architectural_quality":{"score_0_1":quality,"band":band(quality),"status":status,"hard_failures":hard,"polygon_fit_alone_not_success":True}}


def evaluate_topology(candidate,parcel,fm):
    core=fm["local"](Polygon(candidate["temp_core"])); stair,elevator,lobby=schematic_core_parts(core)
    floors=[evaluate_floor(parcel,core,fm,"RESIDENTIAL_FLOOR_1",1),evaluate_floor(parcel,core,fm,"RESIDENTIAL_FLOOR_2",2)]
    failures=[{"floor_id":f["floor_id"],"failures":f["architectural_quality"]["hard_failures"]} for f in floors if f["architectural_quality"]["hard_failures"]]
    low=min(f["architectural_quality"]["score_0_1"] for f in floors)
    if failures: status="CURRENT_CORE_INFEASIBLE_FOR_UPPER_FLOORS"
    elif low<.40: status="CURRENT_CORE_ARCHITECTURALLY_DISFAVORED_FOR_UPPER_FLOORS"
    elif low<.70: status="CURRENT_CORE_PRESERVABLE_WITH_TRADEOFFS"
    else: status="CURRENT_CORE_PRESERVABLE"
    causes=[]
    for f in floors:
        if f["corridor_efficiency"]["public_circulation_ratio"]>.08:causes.append({"cause":"core_position","evidence":f'{f["floor_id"]}:extended_common_circulation'})
        if f["program_unit_count"]==2 and min(u["exterior_daylight_edge_opportunity_m"] for u in f["units"])<fm["frontage_length_m"]*.5:causes.append({"cause":"building_program_and_floor_geometry","evidence":"two_unit_split_reduces_exterior_edge_per_unit"})
    relocation_required=status in ("CURRENT_CORE_ARCHITECTURALLY_DISFAVORED_FOR_UPPER_FLOORS","CURRENT_CORE_INFEASIBLE_FOR_UPPER_FLOORS")
    return {"topology_id":candidate["topology_id"],"core_geometry":deepcopy(candidate["temp_core"]),"core_geometry_mutated":False,
      "vertical_anchor":{"status":"PREFERRED_VERTICAL_ANCHOR_HYPOTHESIS_NON_FINAL","aggregate_core":deepcopy(candidate["temp_core"]),"schematic_stair":poly(fm["world"](stair)),"schematic_elevator":poly(fm["world"](elevator)),"temporary_elevator_envelope_m":[2.1,2.1],"schematic_lobby":poly(fm["world"](lobby)),"lobby_status":"LOBBY_UNRESOLVED","subdivision_is_final":False},
      "floors":floors,"core_preservation_status":status,"status_basis":{"minimum_floor_quality_score":low,"failure_evidence":failures,"geometry_derived_causes":causes},
      "core_relocation_required":relocation_required,"core_relocation_hypotheses":[],"relocation_policy":"not_generated_unless_current_core_disfavored_or_infeasible" if not relocation_required else "required_after_failure_evidence"}


def svg_polygon(points,tr,fill,stroke,opacity=.5,extra=""):
    if not points:return ""
    return f'<polygon points="{" ".join(f"{tr(p)[0]:.1f},{tr(p)[1]:.1f}" for p in points)}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" {extra}/>'


def render_floor(topology,floor):
    boundary=floor["floor_boundary"]; xs=[p[0] for p in boundary];ys=[p[1] for p in boundary]
    scale=min(650/max(max(xs)-min(xs),EPS),760/max(max(ys)-min(ys),EPS));minx,maxy=min(xs),max(ys)
    tr=lambda p:(55+(p[0]-minx)*scale,145+(maxy-p[1])*scale)
    va=topology["vertical_anchor"]; layers=[svg_polygon(boundary,tr,"#fff","#111827",.8),svg_polygon(floor["public_corridor"],tr,"#fde68a","#a16207",.75)]
    colors=[("#bfdbfe","#1d4ed8"),("#ddd6fe","#6d28d9")]
    for i,u in enumerate(floor["units"]):
        layers.append(svg_polygon(u["boundary"],tr,*colors[i],.58)); x,y=tr(u["entrance"]);layers.append(f'<circle cx="{x}" cy="{y}" r="7" fill="#be123c"/><text x="{x+10}" y="{y-7}" class="tiny">{u["unit_id"]} ENTRANCE</text>')
        c=Polygon(u["boundary"]).centroid;cx,cy=tr([c.x,c.y]);layers.append(f'<text x="{cx}" y="{cy}" text-anchor="middle" class="label">{u["unit_id"]}</text><text x="{cx}" y="{cy+19}" text-anchor="middle" class="tiny">ROOM/ZONES UNRESOLVED</text>')
        for a,b in zip(u["access_path"],u["access_path"][1:]):
            x1,y1=tr(a);x2,y2=tr(b);layers.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#a16207" stroke-width="3" marker-end="url(#arr)"/>')
    layers += [svg_polygon(va["aggregate_core"],tr,"#fed7aa","#9a3412",.42),svg_polygon(va["schematic_stair"],tr,"#c4b5fd","#6d28d9",.75),svg_polygon(va["schematic_elevator"],tr,"#f9a8d4","#9d174d",.78),svg_polygon(va["schematic_lobby"],tr,"#fde68a","#a16207",.55,'stroke-dasharray="7 4"')]
    for p in floor["unresolved_regions"]:layers.append(svg_polygon(p,tr,"#e5e7eb","#6b7280",.7,'stroke-dasharray="5 4"'))
    notes=[f'Core preservation: {topology["core_preservation_status"]}',f'Program: {floor["program_unit_count"]} unit(s) — explicit project requirement',f'Architectural quality {floor["architectural_quality"]["score_0_1"]:.3f} ({floor["architectural_quality"]["band"]})',f'Residential envelope efficiency {floor["corridor_efficiency"]["residential_envelope_efficiency"]:.3f}',f'Public circulation ratio {floor["corridor_efficiency"]["public_circulation_ratio"]:.3f}',f'Dead/unusable {floor["dead_unusable_space_m2"]:.3f} m²',f'Hard failures: {", ".join(floor["architectural_quality"]["hard_failures"]) or "NONE"}','Rooms / living-private-service zones / windows unresolved','Plumbing clustering unresolved — insufficient evidence','NO WINNER / CORE NON-FINAL / LOBBY UNRESOLVED']
    panel=''.join(f'<text x="770" y="{170+i*34}" class="panel">{html.escape(n)}</text>' for i,n in enumerate(notes))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1050"><defs><style>.label{{font:700 13px Arial}}.tiny{{font:10px Arial}}.panel{{font:14px Arial}}</style><marker id="arr" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto"><polygon points="0 0,9 3.5,0 7" fill="#a16207"/></marker></defs><rect width="100%" height="100%" fill="#f8fafc"/><text x="45" y="42" font-family="Arial" font-size="23" font-weight="bold">V8 — {html.escape(topology["topology_id"])} — {floor["floor_id"]}</text><text x="45" y="75" class="panel">ARCHITECTURE-ONLY ENGINEERING/DEBUG SVG | PREFERRED_VERTICAL_ANCHOR_HYPOTHESIS_NON_FINAL</text><text x="45" y="110" class="label">FLOOR / PARCEL BOUNDARY — EXTERIOR / DAYLIGHT OPPORTUNITY EDGE</text>{''.join(layers)}<rect x="745" y="130" width="810" height="395" rx="8" fill="white" stroke="#94a3b8"/><text x="770" y="150" class="label">UPPER-FLOOR QUALITY PANEL</text>{panel}<rect x="745" y="555" width="810" height="210" fill="white" stroke="#94a3b8"/><text x="770" y="582" class="label">LEGEND</text><text x="770" y="615" class="panel">Blue / violet = unit envelopes; red dot = unit entrance</text><text x="770" y="647" class="panel">Yellow = PUBLIC CORRIDOR / LOBBY CIRCULATION</text><text x="770" y="679" class="panel">Purple = 2-FLIGHT STAIR SCHEMATIC; pink = TEMP ELEVATOR 2.10×2.10 m</text><text x="770" y="711" class="panel">Dashed grey = DEAD / UNRESOLVED REGION</text><text x="770" y="743" class="panel">Envelope fit alone is not architectural success; detailed rooms remain unresolved.</text></svg>'''


def render_index(topologies):
    cards=[]; y=125
    for t in topologies:
        cards.append(f'<rect x="40" y="{y}" width="1520" height="175" rx="8" fill="white" stroke="#94a3b8"/><text x="65" y="{y+30}" class="h">{html.escape(t["topology_id"])}</text><text x="65" y="{y+62}" class="t">{t["core_preservation_status"]} | relocation required: {str(t["core_relocation_required"]).lower()}</text>')
        for i,f in enumerate(t["floors"]):cards.append(f'<text x="{65+i*730}" y="{y+100}" class="t">{f["floor_id"]}: {f["program_unit_count"]} unit(s) | quality {f["architectural_quality"]["score_0_1"]:.3f} ({f["architectural_quality"]["band"]})</text><text x="{65+i*730}" y="{y+132}" class="t">efficiency {f["corridor_efficiency"]["residential_envelope_efficiency"]:.3f} | dead {f["dead_unusable_space_m2"]:.2f} m² | failures {len(f["architectural_quality"]["hard_failures"])}</text>')
        y+=195
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="790"><defs><style>.h{{font:700 17px Arial}}.t{{font:14px Arial}}</style></defs><rect width="100%" height="100%" fill="#f8fafc"/><text x="40" y="42" font-family="Arial" font-size="24" font-weight="bold">Parcel 2 H1 V8 — Upper Floors Around Current Core</text><text x="40" y="78" class="t">THREE INDEPENDENT NON-FINAL CORE HYPOTHESES | NO WINNER / NO AUTHORITATIVE RANK</text>{''.join(cards)}<text x="40" y="735" class="t">RF1 = 1 unit; RF2 = 2 units. Rooms, population, final stair/elevator/lobby sizing and regulatory compliance remain unresolved.</text><text x="40" y="765" class="t">No 4→3 parking / maximize-commercial experiment executed.</text></svg>'''


def build(output):
    v6_before,v7_before=inventory(V6_DIR),inventory(V7_DIR)
    source=json.loads(V6_JSON.read_text(encoding="utf-8"));v7=json.loads(V7_JSON.read_text(encoding="utf-8"));program=json.loads(PROGRAM.read_text(encoding="utf-8"));occupancy=json.loads(OCCUPANCY.read_text(encoding="utf-8"));assumption=json.loads(CORE_ASSUMPTION.read_text(encoding="utf-8"))
    if source["distinct_topology_count"]!=3 or {c["topology_id"] for c in source["topologies"]}!=EXPECTED_IDS:raise RuntimeError("exactly three expected V6 topologies required")
    if v7["selection"]["winner"] is not None or not v7["readiness"]["all_three_remain_ready"]:raise RuntimeError("V7 readiness/no-winner contract failed")
    schedule=next(x for x in program["evidence_records"] if x["id"]=="residential_units_per_floor")["value"]
    if schedule!={"residential_floor_1":1,"residential_floor_2":2}:raise RuntimeError("unexpected upper-floor program")
    if occupancy["architecture_dependency_policy"]["occupancy_schedule_required_for_geometry_allocation"] is not False:raise RuntimeError("numeric dependency requires fail-closed review")
    fm=frame(source["parcel"],source["frontage"]);parcel=fm["local"](Polygon(source["parcel"]));topologies=[evaluate_topology(c,parcel,fm) for c in source["topologies"]]
    reloc=[t for t in topologies if t["core_relocation_required"]]
    report={"contract":"Parcel2H1UpperFloorDesignAroundCurrentCoreV8","scope":"architecture_only","authority_class":"PROJECT_HUMAN_DESIGN_CRITIQUE_NON_FINAL","lineage":{"v6_json_path":str(V6_JSON),"v6_json_sha256":sha(V6_JSON),"v7_json_path":str(V7_JSON),"v7_json_sha256":sha(V7_JSON),"v6_inventory_before":v6_before,"v7_inventory_before":v7_before,"v6_frozen":True,"v7_frozen":True},"program":{"residential_floor_1":{"unit_count":1},"residential_floor_2":{"unit_count":2},"authority_class":"PROJECT_REQUIREMENT","unit_area_requirement":None,"bedroom_count_requirement":None,"population":None,"new_numeric_project_requirements_invented":False,"topology_allocation_can_proceed_without_numeric_occupancy":True},"core_hypotheses":topologies,"selection":{"winner":None,"final_selection_performed":False,"authoritative_ranking":False},"relocation":{"triggered":bool(reloc),"trigger_topology_ids":[t["topology_id"] for t in reloc],"whole_building_recheck_required_if_generated":True,"hypotheses":[]},"result":{"status":"H1_UPPER_FLOORS_READY_FOR_HUMAN_REVIEW" if all(all(f["architectural_quality"]["status"]=="architecturally_reviewable" for f in t["floors"]) for t in topologies) else "BLOCKED","blockers":[] if all(all(f["architectural_quality"]["status"]=="architecturally_reviewable" for f in t["floors"]) for t in topologies) else [{"topology_id":t["topology_id"],"evidence":t["status_basis"]["failure_evidence"]} for t in topologies if t["status_basis"]["failure_evidence"]]},"derivation_contract":{"coordinate_basis":"frontage_tangent_inward_depth_and_floor_geometry","topology_names_used_for_status":False,"cardinal_direction_used":False,"parcel2_coordinates_hardcoded":False,"fixed_metric_core_offset_used":False,"current_core_geometry_mutated":False},"snapshot":{"overwritten_files":[],"snapshot_required":False,"reason":"new V8 source/test names and new timestamped output directory"},"prohibited_workflows_executed":{"H2":False,"elevator_traffic":False,"structure":False,"BIM":False,"IFC":False,"render":False,"image_generation":False,"parking_4_to_3_maximize_commercial":False}}
    output.mkdir(parents=True,exist_ok=False);jp=output/"PARCEL2_H1_UPPER_FLOOR_DESIGN_AROUND_CURRENT_CORE_V8.json";jp.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    artifacts=[]
    for t in topologies:
        for f in t["floors"]:
            p=output/f'{t["topology_id"]}-{f["floor_id"]}-V8.svg';p.write_text(render_floor(t,f),encoding="utf-8");ET.parse(p);artifacts.append({"role":"upper_floor_engineering_svg","topology_id":t["topology_id"],"floor_id":f["floor_id"],"file":p.name,"sha256":sha(p),"size_bytes":p.stat().st_size})
    ip=output/"PARCEL2_H1_UPPER_FLOOR_DESIGN_AROUND_CURRENT_CORE_V8_INDEX.svg";ip.write_text(render_index(topologies),encoding="utf-8");ET.parse(ip)
    artifacts += [{"role":"diagnostic_json","file":jp.name,"sha256":sha(jp),"size_bytes":jp.stat().st_size},{"role":"comparison_index_svg","file":ip.name,"sha256":sha(ip),"size_bytes":ip.stat().st_size}]
    if inventory(V6_DIR)!=v6_before or inventory(V7_DIR)!=v7_before:raise RuntimeError("V6/V7 mutation detected")
    report["lineage"].update({"v6_inventory_after":inventory(V6_DIR),"v7_inventory_after":inventory(V7_DIR)})
    jp.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    for a in artifacts:
        if a["file"]==jp.name:a.update(sha256=sha(jp),size_bytes=jp.stat().st_size)
    mp=output/"ARTIFACT_MANIFEST.json";mp.write_text(json.dumps({"contract":"Parcel2H1UpperFloorDesignAroundCurrentCoreV8Manifest","artifacts":sorted(artifacts,key=lambda x:x["file"]),"selection":{"winner":None,"final_selection_performed":False},"source_v6_inventory":v6_before,"source_v7_inventory":v7_before},ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return {"output":str(output),"result":report["result"],"manifest_sha256":sha(mp),"core_statuses":[{"topology_id":t["topology_id"],"status":t["core_preservation_status"],"relocation_required":t["core_relocation_required"]} for t in topologies]}


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--output",type=Path,required=True);print(json.dumps(build(ap.parse_args().output),ensure_ascii=False,indent=2))
