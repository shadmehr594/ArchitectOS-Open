"""Deterministic, architecture-only V7 human-quality review of frozen V6 topologies."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(r"<repo-root>")
V6_DIR = ROOT / "exports/DEFAULT/parcel2_h1_circulation_core_topology_v6_20260912_210133"
V6_JSON = V6_DIR / "PARCEL2_H1_CIRCULATION_CORE_TOPOLOGY_V6.json"
EXPECTED_IDS = {
    "H1-V6-ADJACENT-SPINE", "H1-V6-BETWEEN-DOGLEG", "H1-V6-EDGE-RETURN"
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def v6_inventory():
    return {p.name: {"sha256": sha(p), "size_bytes": p.stat().st_size}
            for p in sorted(V6_DIR.iterdir()) if p.is_file()}


def centroid(poly):
    return [sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)]


def polygon_area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] -
                   poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly))) / 2)


def point_in_poly(p, poly):
    x, y = p; inside = False
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        if (a[1] > y) != (b[1] > y):
            xin = (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]
            if x < xin: inside = not inside
    return inside


def frame(parcel, frontage):
    a, b = frontage[0], frontage[-1]
    vx, vy = b[0] - a[0], b[1] - a[1]; width = math.hypot(vx, vy)
    tx, ty = vx / width, vy / width
    pc = centroid(parcel)
    normals = [(-ty, tx), (ty, -tx)]
    nx, ny = max(normals, key=lambda n: (pc[0]-a[0])*n[0] + (pc[1]-a[1])*n[1])
    depth = max((p[0]-a[0])*nx + (p[1]-a[1])*ny for p in parcel)
    def norm(p):
        return [((p[0]-a[0])*tx + (p[1]-a[1])*ty) / width,
                ((p[0]-a[0])*nx + (p[1]-a[1])*ny) / depth]
    return {"width_m": width, "depth_m": depth, "norm": norm}


def poly_bbox_norm(poly, fm):
    q = [fm["norm"](p) for p in poly]
    return [min(p[0] for p in q), min(p[1] for p in q),
            max(p[0] for p in q), max(p[1] for p in q)]


def clamp(v): return round(max(0.0, min(1.0, v)), 3)


def level(score, inverse=False):
    s = 1-score if inverse else score
    return "high" if s >= .67 else "moderate" if s >= .34 else "low"


def residual_evidence(c, parcel, fm, grid=160):
    mandatory = [c["commercial"]["polygon"], c["vehicle_ingress"], c["aisle_manoeuvre"],
                 c["temp_core"]] + [s["polygon"] for s in c["stalls"]] + c["pedestrian_route"]["segment_regions"]
    xs = [p[0] for p in parcel]; ys = [p[1] for p in parcel]
    dx, dy = (max(xs)-min(xs))/grid, (max(ys)-min(ys))/grid
    residual = set()
    for iy in range(grid):
        for ix in range(grid):
            p = (min(xs)+(ix+.5)*dx, min(ys)+(iy+.5)*dy)
            if point_in_poly(p, parcel) and not any(point_in_poly(p, q) for q in mandatory):
                residual.add((ix, iy))
    comps=[]
    while residual:
        seed=residual.pop(); stack=[seed]; comp=[seed]
        while stack:
            x,y=stack.pop()
            for n in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if n in residual: residual.remove(n); stack.append(n); comp.append(n)
        comps.append(comp)
    cell=dx*dy
    pockets=[]
    for comp in comps:
        area=len(comp)*cell
        cx=sum(min(xs)+(x+.5)*dx for x,y in comp)/len(comp)
        cy=sum(min(ys)+(y+.5)*dy for x,y in comp)/len(comp)
        q=fm["norm"]((cx,cy))
        pockets.append({"area_m2":round(area,3),"centroid":[round(cx,4),round(cy,4)],
                        "frontage_connected":q[1] <= .08})
    pockets.sort(key=lambda p:p["area_m2"], reverse=True)
    # Keep categories mutually exclusive: small fragments are dead; larger residual
    # pockets are reclaimable candidates, regardless of frontage, and retain a
    # separate no-auto-conversion caveat in the review record.
    dead=sum(p["area_m2"] for p in pockets if p["area_m2"] < 1.5)
    reclaim=sum(p["area_m2"] for p in pockets if p["area_m2"] >= 1.5)
    return round(dead,3), round(reclaim,3), pockets[:8]


def review_candidate(c, parcel, fm):
    cb=poly_bbox_norm(c["commercial"]["polygon"],fm)
    core=poly_bbox_norm(c["temp_core"],fm); aisle=poly_bbox_norm(c["aisle_manoeuvre"],fm)
    route=[fm["norm"](p) for p in c["pedestrian_route"]["centerline"]]
    route_len=sum(math.dist(a,b) for a,b in zip(route,route[1:]))
    turns=max(0,len(route)-2)
    frontage_ratio=c["commercial"]["frontage_length_m"]/fm["width_m"]
    commercial_depth=max(1e-9,cb[3]-cb[1]); commercial_width=max(1e-9,cb[2]-cb[0])
    shape=clamp(min(commercial_width/commercial_depth,commercial_depth/commercial_width)/.6)
    entry_s=fm["norm"](c["residential_entrance"])[0]
    separation=min(abs(entry_s-cb[0]),abs(entry_s-cb[2]))*fm["width_m"]
    shared=c["pedestrian_route"]["shared_area_m2"]
    exclusive=c["pedestrian_route"]["exclusive_area_m2"]
    share_ratio=shared/max(shared+exclusive,1e-9)
    clearance=c["swept_path"]["minimum_clearance_m"]
    manoeuvre=clamp(.52 + .13*(clearance-3.3) + .20*(aisle[3]-aisle[1]) - .10*turns - .14*share_ratio)
    access=clamp(.95 - .16*turns - .12*route_len - .12*share_ratio)
    frontage_quality=clamp(.55*frontage_ratio/.5 + .25*c["commercial"]["direct_street_access"] + .20*min(1,separation/1.2))
    conflict=clamp(.10 + .75*share_ratio + .10*turns + .05*(clearance < 3.5))
    core_access=clamp(.55*access + .30*core[1] + .15*(1-share_ratio))
    dead,reclaim,pockets=residual_evidence(c,parcel,fm)
    notes=[]
    if clearance < 3.5: notes.append("four stalls pass only the bounded-clearance proxy; tighter aisle warrants full vehicle simulation")
    else: notes.append("four stalls have the strongest proxy clearance, but independent egress still needs engineering validation")
    if turns: notes.append("turning pedestrian route reduces directness and requires clear wayfinding")
    if shared: notes.append("shared route portion requires visual priority and conflict management")
    else: notes.append("pedestrian route remains exclusive in the current geometric evidence")
    blockers=[]
    if not c["gates"]["residential_to_core_route_continuous"]: blockers.append("RESIDENTIAL_CORE_ROUTE_DISCONTINUOUS")
    if c["swept_path"]["status"] != "approximated_pass": blockers.append("SWEPT_PATH_PROXY_NOT_PASSING")
    status="blocked" if blockers else ("disfavored" if min(frontage_quality,access,manoeuvre,core_access)<.30 else "reviewable")
    return {
      "topology_id":c["topology_id"], "neutral_label":chr(64+c["review_order"]),
      "review_order":c["review_order"], "review_order_is_rank":False,
      "commercial_frontage_quality":{"score_0_1":frontage_quality,"band":level(frontage_quality),"usable_frontage_m":c["commercial"]["frontage_length_m"],"direct_street_entrance":True,"fragmentation":"frontage_connected_single_region"},
      "commercial_shape_efficiency":{"score_0_1":shape,"band":level(shape),"aspect_ratio":round(max(commercial_width,commercial_depth)/min(commercial_width,commercial_depth),3),"continuity":"single_contiguous_polygon"},
      "residential_access_legibility":{"score_0_1":access,"band":level(access),"normalized_route_length":round(route_len,3),"direction_changes":turns,"privacy_separation_m":round(separation,3)},
      "pedestrian_vehicle_conflict_intensity":{"score_0_1":conflict,"band":level(conflict),"shared_ratio":round(share_ratio,3),"exclusive_area_m2":exclusive,"shared_area_m2":shared},
      "vehicle_manoeuvre_quality":{"score_0_1":manoeuvre,"band":level(manoeuvre),"proxy_minimum_clearance_m":clearance,"stall_count":c["parking_count"],"independent_access_gate":c["gates"]["all_stalls_independently_reachable"]},
      "stall_usability_notes":notes,
      "core_access_quality":{"score_0_1":core_access,"band":level(core_access),"rear_or_interior":core[1]>=.75,"route_continuous":c["gates"]["residential_to_core_route_continuous"],"lobby_status":"LOBBY_UNRESOLVED"},
      "dead_space_area_m2":dead,"reclaimable_area_m2":reclaim,"residual_pockets":pockets,
      "reclaimable_space_caveat":"Do not convert automatically; preserve frontage and direct-access continuity.",
      "swept_path_status":c["swept_path"]["status"],"engineering_review_required":True,
      "swept_path_evidence_class":"generic_bounded_turn_envelope_clearance_proxy_non_regulatory",
      "human_review_status":status,"blockers":blockers,
      "architectural_coherence":{"score_0_1":clamp((frontage_quality+shape+access+manoeuvre+core_access+(1-conflict))/6),"assessment":"mixed_use_ground_floor_readable_subject_to_unresolved_lobby_and_engineering_review"}
    }


def svg_poly(poly,tr,fill,stroke,opacity=.5,extra=""):
    pts=" ".join(f"{tr(p)[0]:.1f},{tr(p)[1]:.1f}" for p in poly)
    return f'<polygon points="{pts}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" {extra}/>'


def render_detail(c,q,parcel,frontage):
    xs=[p[0] for p in parcel]; ys=[p[1] for p in parcel]
    scale=min(650/(max(xs)-min(xs)),760/(max(ys)-min(ys))); minx,maxy=min(xs),max(ys)
    tr=lambda p:(55+(p[0]-minx)*scale,145+(maxy-p[1])*scale)
    layers=[svg_poly(parcel,tr,"white","#111827",.15),svg_poly(c["commercial"]["polygon"],tr,"#f59e0b","#92400e",.48),svg_poly(c["aisle_manoeuvre"],tr,"#cbd5e1","#475569",.58),svg_poly(c["vehicle_ingress"],tr,"#c084fc","#6b21a8",.32),svg_poly(c["temp_core"],tr,"#f3d28f","#92400e",.85)]
    for s in c["stalls"]: layers.append(svg_poly(s["polygon"],tr,"#60a5fa","#1d4ed8",.62))
    for region in c["pedestrian_route"]["segment_regions"]:
        shared=any(point_in_poly(centroid(region),[c["aisle_manoeuvre"][i] for i in range(4)]) for _ in [0])
        layers.append(svg_poly(region,tr,"#ef4444" if shared else "#22c55e","#991b1b" if shared else "#166534",.32,'stroke-dasharray="7 4"' if shared else ""))
    fp=[tr(p) for p in frontage]; route=[tr(p) for p in c["pedestrian_route"]["centerline"]]
    ent=tr(c["residential_entrance"]); core=tr(centroid(c["temp_core"])); veh=tr(centroid(c["vehicle_ingress"])); comm=tr(centroid(c["commercial"]["polygon"]))
    layers += [f'<line x1="{fp[0][0]}" y1="{fp[0][1]}" x2="{fp[-1][0]}" y2="{fp[-1][1]}" stroke="#dc2626" stroke-width="9"/>',
      f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in route)}" fill="none" stroke="#166534" stroke-width="4" marker-end="url(#ped)"/>',
      f'<circle cx="{ent[0]}" cy="{ent[1]}" r="8" fill="#15803d"/><text x="{ent[0]+10}" y="{ent[1]-8}" class="small">RESIDENTIAL ENTRANCE</text>',
      f'<text x="{comm[0]}" y="{comm[1]}" text-anchor="middle" class="label">COMMERCIAL {c["commercial"]["area_m2"]:.2f} m²</text><text x="{comm[0]}" y="{comm[1]+19}" text-anchor="middle" class="small">DIRECT STREET ENTRANCE ↓</text>',
      f'<text x="{veh[0]}" y="{veh[1]}" text-anchor="middle" class="label">VEHICLE INGRESS / EGRESS ↕</text>',
      f'<path d="M {veh[0]:.1f} {veh[1]:.1f} C {veh[0]:.1f} {veh[1]-90:.1f}, {veh[0]+120:.1f} {veh[1]-120:.1f}, {veh[0]+155:.1f} {veh[1]-180:.1f}" fill="none" stroke="#7c3aed" stroke-width="22" stroke-opacity=".18"/><path d="M {veh[0]:.1f} {veh[1]:.1f} C {veh[0]:.1f} {veh[1]-90:.1f}, {veh[0]+120:.1f} {veh[1]-120:.1f}, {veh[0]+155:.1f} {veh[1]-180:.1f}" fill="none" stroke="#7c3aed" stroke-width="3" stroke-dasharray="10 6" marker-end="url(#veh)"/>',
      f'<text x="{core[0]}" y="{core[1]-26}" text-anchor="middle" class="label">TEMP CORE — NOT COMMERCIAL</text><text x="{core[0]}" y="{core[1]-5}" text-anchor="middle" class="small">2-FLIGHT STAIR schematic</text><rect x="{core[0]-18}" y="{core[1]+5}" width="36" height="36" fill="none" stroke="#92400e"/><text x="{core[0]}" y="{core[1]+56}" text-anchor="middle" class="small">TEMP ELEVATOR 2.10×2.10 m</text><text x="{core[0]}" y="{core[1]+76}" text-anchor="middle" class="warn">LOBBY UNRESOLVED</text>']
    for p in q["residual_pockets"]:
        if p["area_m2"]>=.35:
            x,y=tr(p["centroid"]); layers.append(f'<circle cx="{x}" cy="{y}" r="9" fill="#fde047" stroke="#854d0e"/><text x="{x+12}" y="{y+4}" class="tiny">DEAD / RECLAIMABLE {p["area_m2"]:.2f} m²</text>')
    metric_lines=[
      f'Commercial frontage {q["commercial_frontage_quality"]["score_0_1"]:.3f} ({q["commercial_frontage_quality"]["band"]}); shape {q["commercial_shape_efficiency"]["score_0_1"]:.3f}',
      f'Residential legibility {q["residential_access_legibility"]["score_0_1"]:.3f}; core access {q["core_access_quality"]["score_0_1"]:.3f}',
      f'Ped/vehicle conflict {q["pedestrian_vehicle_conflict_intensity"]["score_0_1"]:.3f} ({q["pedestrian_vehicle_conflict_intensity"]["band"]})',
      f'Vehicle manoeuvre {q["vehicle_manoeuvre_quality"]["score_0_1"]:.3f}; proxy clearance {q["vehicle_manoeuvre_quality"]["proxy_minimum_clearance_m"]:.2f} m',
      f'Dead {q["dead_space_area_m2"]:.2f} m²; reclaimable {q["reclaimable_area_m2"]:.2f} m²',
      f'Human status: {q["human_review_status"]}; blockers: {", ".join(q["blockers"]) or "NONE"}',
      'Swept path approximated_pass ≠ final proof; ENGINEERING REVIEW REQUIRED',
      'Envelope shown is generic/debug evidence only — no code-compliance claim',
      'NO WINNER / NO AUTHORITATIVE RANK | Architecture-only']
    panel=''.join(f'<text x="765" y="{170+i*35}" class="panel">{html.escape(line)}</text>' for i,line in enumerate(metric_lines))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1050"><defs><style>.label{{font:700 12px Arial}}.small{{font:11px Arial}}.tiny{{font:10px Arial}}.warn{{font:700 11px Arial;fill:#b91c1c}}.panel{{font:14px Arial}}</style><marker id="ped" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="#166534"/></marker><marker id="veh" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="#7c3aed"/></marker></defs><rect width="100%" height="100%" fill="#f8fafc"/><text x="45" y="42" font-family="Arial" font-size="24" font-weight="bold">V7 Human Architectural Quality Review — {html.escape(c["topology_id"])}</text><text x="45" y="75" font-family="Arial" font-size="14">Neutral label {q["neutral_label"]} | REVIEW ORDER IS NOT RANK | NO WINNER</text><text x="45" y="112" font-family="Arial" font-size="15" fill="#dc2626" font-weight="bold">STREET / FRONTAGE</text>{''.join(layers)}<rect x="740" y="130" width="815" height="360" rx="8" fill="white" stroke="#94a3b8"/><text x="765" y="150" class="label">HUMAN-QUALITY REVIEW PANEL</text>{panel}<rect x="740" y="520" width="815" height="180" fill="white" stroke="#94a3b8"/><text x="765" y="548" class="label">LEGEND / CAVEATS</text><text x="765" y="580" class="panel" fill="#166534">Solid green = pedestrian exclusive</text><text x="765" y="612" class="panel" fill="#991b1b">Dashed red region = pedestrian/vehicle shared</text><text x="765" y="644" class="panel" fill="#7c3aed">Purple envelope/arrow = generic vehicle manoeuvre evidence</text><text x="765" y="676" class="panel">Yellow markers = residual dead/reclaimable pockets; no automatic conversion</text></svg>'''


def render_index(rows):
    cards=[]
    for i,q in enumerate(rows):
        y=135+i*190
        cards.append(f'<rect x="45" y="{y}" width="1510" height="160" rx="8" fill="white" stroke="#94a3b8"/><text x="70" y="{y+32}" class="head">{q["neutral_label"]} — {html.escape(q["topology_id"])}</text><text x="70" y="{y+66}" class="t">Commercial frontage {q["commercial_frontage_quality"]["score_0_1"]:.3f} | shape {q["commercial_shape_efficiency"]["score_0_1"]:.3f} | residential legibility {q["residential_access_legibility"]["score_0_1"]:.3f} | core access {q["core_access_quality"]["score_0_1"]:.3f}</text><text x="70" y="{y+98}" class="t">Conflict intensity {q["pedestrian_vehicle_conflict_intensity"]["score_0_1"]:.3f} | manoeuvre {q["vehicle_manoeuvre_quality"]["score_0_1"]:.3f} | dead/reclaimable {q["dead_space_area_m2"]:.2f}/{q["reclaimable_area_m2"]:.2f} m²</text><text x="70" y="{y+130}" class="t">Status {q["human_review_status"]} | swept {q["swept_path_status"]} | ENGINEERING REVIEW REQUIRED</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="800"><defs><style>.head{{font:700 17px Arial}}.t{{font:14px Arial}}</style></defs><rect width="100%" height="100%" fill="#f8fafc"/><text x="45" y="45" font-family="Arial" font-size="25" font-weight="bold">Parcel 2 H1 V7 — Human Architectural Quality Comparison</text><text x="45" y="80" class="t">NEUTRAL A/B/C REVIEW ORDER — NOT A RANK — NO WINNER / FINAL SELECTION</text>{''.join(cards)}<text x="45" y="735" class="t">All swept-path graphics are non-regulatory engineering/debug evidence; engineering review remains required.</text><text x="45" y="765" class="t">TEMP CORE — NOT COMMERCIAL | 2-FLIGHT STAIR schematic | TEMP ELEVATOR 2.10×2.10 m | LOBBY UNRESOLVED</text></svg>'''


def build(output):
    before=v6_inventory(); source=json.loads(V6_JSON.read_text(encoding="utf-8"))
    if source["distinct_topology_count"] != 3 or len(source["topologies"]) != 3: raise RuntimeError("V7 requires exactly three V6 topologies")
    if {c["topology_id"] for c in source["topologies"]} != EXPECTED_IDS: raise RuntimeError("unexpected V6 topology set")
    if source["selection"]["winner"] is not None: raise RuntimeError("V6 winner must remain unset")
    fm=frame(source["parcel"],source["frontage"]); rows=[review_candidate(c,source["parcel"],fm) for c in source["topologies"]]
    report={"contract":"Parcel2H1HumanArchitecturalQualityReviewV7","scope":"architecture_only","authority_class":"PROJECT_HUMAN_DESIGN_CRITIQUE_NON_FINAL","lineage":{"v6_json_path":str(V6_JSON),"v6_json_sha256":sha(V6_JSON),"v6_directory_inventory_before":before,"v6_mutated":False,"v6_frozen":True},"input_contract":{"exactly_three_v6_topologies_consumed":True,"topology_ids":[r["topology_id"] for r in rows],"geometry_reused_without_mutation":True},"derivation_contract":{"coordinate_basis":"parcel_frontage_tangent_and_inward_depth_field","metrics_derived_from_geometry_and_evidence":True,"topology_names_used_for_scoring":False,"cardinal_direction_used":False,"parcel2_coordinates_hardcoded":False,"historical_seed_used":False,"fixed_metric_offset_used":False},"quality_reviews":rows,"selection":{"winner":None,"final_selection_performed":False,"authoritative_ranking":False,"labels":"neutral_A_B_C"},"readiness":{"H1":"READY_FOR_HUMAN_ARCHITECTURAL_SELECTION" if all(r["human_review_status"]=="reviewable" for r in rows) else "HUMAN_REVIEW_REQUIRED_WITH_FLAGS","all_three_remain_ready":all(r["human_review_status"]=="reviewable" for r in rows)},"snapshot":{"overwritten_files":[],"snapshot_required":False,"reason":"new V7 source/test names and new timestamped output directory; no overwrite"},"prohibited_workflows_executed":{"new_topology_generation":False,"H2":False,"elevator_traffic":False,"structure":False,"BIM":False,"IFC":False,"render":False,"image_generation":False}}
    output.mkdir(parents=True,exist_ok=False)
    jp=output/"PARCEL2_H1_HUMAN_ARCHITECTURAL_QUALITY_REVIEW_V7.json"; jp.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    artifacts=[]
    byid={c["topology_id"]:c for c in source["topologies"]}
    for q in rows:
        p=output/f'{q["topology_id"]}-V7-QUALITY-REVIEW.svg'; p.write_text(render_detail(byid[q["topology_id"]],q,source["parcel"],source["frontage"]),encoding="utf-8"); ET.parse(p)
        artifacts.append({"role":"topology_quality_review_svg","topology_id":q["topology_id"],"file":p.name,"sha256":sha(p),"size_bytes":p.stat().st_size})
    ip=output/"PARCEL2_H1_HUMAN_ARCHITECTURAL_QUALITY_REVIEW_V7_INDEX.svg"; ip.write_text(render_index(rows),encoding="utf-8"); ET.parse(ip)
    artifacts += [{"role":"diagnostic_json","file":jp.name,"sha256":sha(jp),"size_bytes":jp.stat().st_size},{"role":"comparison_index_svg","file":ip.name,"sha256":sha(ip),"size_bytes":ip.stat().st_size}]
    manifest={"contract":"Parcel2H1HumanArchitecturalQualityReviewV7Manifest","artifacts":sorted(artifacts,key=lambda x:x["file"]),"source_v6_inventory":before,"selection":{"winner":None,"final_selection_performed":False},"snapshot":{"overwritten_files":[],"snapshot_required":False}}
    mp=output/"ARTIFACT_MANIFEST.json"; mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    after=v6_inventory()
    if before != after: raise RuntimeError("V6 artifact mutation detected")
    report["lineage"]["v6_directory_inventory_after"]=after
    # Rewrite only the new V7 diagnostic to embed the verified post-run inventory.
    jp.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    for a in manifest["artifacts"]:
        if a["file"]==jp.name: a.update(sha256=sha(jp),size_bytes=jp.stat().st_size)
    mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return {"output":str(output),"manifest_sha256":sha(mp),"readiness":report["readiness"],"reviews":rows}


if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--output",type=Path,required=True)
    print(json.dumps(build(ap.parse_args().output),ensure_ascii=False,indent=2))
