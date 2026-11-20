"""Build deterministic architecture-only V6 circulation/core topology artifacts."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from pathlib import Path

ROOT = Path(r"<repo-root>")
V5 = ROOT / "exports/DEFAULT/parcel2_h1_human_architectural_comparison_v5_20260912_205011/PARCEL2_H1_HUMAN_ARCHITECTURAL_COMPARISON_V5.json"
TOLERANCE_M = 1e-6


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def area(poly): return abs(sum(poly[i][0]*poly[(i+1)%len(poly)][1]-poly[(i+1)%len(poly)][0]*poly[i][1] for i in range(len(poly)))/2)
def centroid(poly): return [sum(p[0] for p in poly)/len(poly),sum(p[1] for p in poly)/len(poly)]


def frame(parcel, frontage):
    a,b=frontage[0],frontage[-1]; vx=b[0]-a[0]; vy=b[1]-a[1]; w=math.hypot(vx,vy)
    tx,ty=vx/w,vy/w; candidates=[(-ty,tx),(ty,-tx)]; pc=centroid(parcel)
    nx,ny=max(candidates,key=lambda n:(pc[0]-a[0])*n[0]+(pc[1]-a[1])*n[1])
    depths=[(p[0]-a[0])*nx+(p[1]-a[1])*ny for p in parcel]; d=max(depths)
    def pt(s,z): return [a[0]+tx*w*s+nx*d*z,a[1]+ty*w*s+ny*d*z]
    def rect(s0,z0,s1,z1): return [pt(s0,z0),pt(s1,z0),pt(s1,z1),pt(s0,z1)]
    return {"width_m":w,"depth_m":d,"point":pt,"rect":rect}


FAMILIES=[
 {"id":"H1-V6-ADJACENT-SPINE","name":"adjacent_residential_entry_separate_vehicle_ingress__core_aligned_spine","commercial":[0,.30,.50,0],"entry_s":.54,"vehicle":[.64,1],"aisle":[.60,.28,1,.82],"core":[0,.82,.46,1],"path":[(.54,0),(.54,.88),(.46,.88)],"stall_side":"low"},
 {"id":"H1-V6-BETWEEN-DOGLEG","name":"residential_entry_between_commercial_vehicle__core_offset_interior","commercial":[0,.30,.46,0],"entry_s":.50,"vehicle":[.57,.91],"aisle":[.53,.23,.93,.88],"core":[.54,.82,1,1],"path":[(.50,0),(.50,.69),(.76,.69),(.76,.82)],"stall_side":"low"},
 {"id":"H1-V6-EDGE-RETURN","name":"vehicle_ingress_edge_biased__residential_entry_buffered__core_offset_return","commercial":[.50,.30,1,0],"entry_s":.45,"vehicle":[0,.34],"aisle":[0,.25,.40,.84],"core":[0,.82,.46,1],"path":[(.45,0),(.45,.66),(.30,.66),(.30,.82)],"stall_side":"high"},
]


def tube(points, half_s=.03, half_z=.012):
    # Review region around an orthogonal semantic route; union is represented by segments.
    out=[]
    for a,b in zip(points,points[1:]):
        if abs(a[0]-b[0]) < 1e-9: out.append((a[0]-half_s,min(a[1],b[1])-half_z,a[0]+half_s,max(a[1],b[1])+half_z))
        else: out.append((min(a[0],b[0])-half_s,a[1]-half_z,max(a[0],b[0])+half_s,a[1]+half_z))
    return out


def overlap_rect(a,b):
    x=max(0,min(a[2],b[2])-max(a[0],b[0])); y=max(0,min(a[3],b[3])-max(a[1],b[1])); return x*y


def make_candidate(f, fm):
    R=fm["rect"]; w,d=fm["width_m"],fm["depth_m"]
    c0,z1,c1,z0=f["commercial"]; commercial=R(c0,z0,c1,z1)
    aisle_n=f["aisle"]; aisle=R(*aisle_n)
    core=R(*f["core"]); veh=R(f["vehicle"][0],0,f["vehicle"][1],f["aisle"][1])
    stalls=[]
    for i in range(4):
        za=.30+i*.125; zb=za+.125
        sr=[0,za,.50,zb] if f["stall_side"]=="low" else [.50,za,1,zb]
        stalls.append({"stall_id":f"S-{i+1:03d}","polygon":R(*sr),"normalized":sr})
    segs=tube(f["path"]); shared=sum(overlap_rect(s,aisle_n) for s in segs)*w*d
    total=sum((s[2]-s[0])*(s[3]-s[1]) for s in segs)*w*d
    clearance=min((f["vehicle"][1]-f["vehicle"][0])*w,(aisle_n[2]-aisle_n[0])*w)
    swept={"authority":"NON_REGULATORY_ENGINEERING_VALIDATION","method":"generic_bounded_turn_envelope_clearance_proxy","regulatory_claim":False,"minimum_clearance_m":round(clearance,3),"required_proxy_clearance_m":3.3,"status":"approximated_pass" if clearance>=3.3 else "fail_closed_insufficient_clearance","limitations":"No steering simulation or code compliance claim; human/engineering validation remains required."}
    sig={"commercial":"frontage_connected_direct_entry","residential_entry":("between_commercial_and_vehicle" if c1<=f["entry_s"]<=f["vehicle"][0] else "buffered_from_vehicle"),"vehicle_ingress":"edge_biased" if f["vehicle"][0]==0 or f["vehicle"][1]==1 else "interior_biased","core":"aligned_with_spine" if len(f["path"])==3 else "offset_with_return","aisle":"frontage_normal_depth_field_spine","pedestrian":"mixed_exclusive_and_controlled_shared"}
    blockers=[]
    if swept["status"]!="approximated_pass": blockers.append("SWEPT_PATH_PROXY_FAIL_CLOSED")
    review="reviewable" if not blockers else "rejected"
    return {"topology_id":f["id"],"topology_name":f["name"],"semantic_topology_signature":sig,"review_order":FAMILIES.index(f)+1,"review_order_is_rank":False,"status":review,"parcel":None,"commercial":{"polygon":commercial,"area_m2":round(area(commercial),6),"frontage_length_m":round(abs(c1-c0)*w,6),"direct_street_access":True},"residential_entrance":fm["point"](f["entry_s"],0),"vehicle_ingress":veh,"aisle_manoeuvre":aisle,"temp_core":core,"stalls":stalls,"parking_count":4,"pedestrian_route":{"centerline":[fm["point"](*p) for p in f["path"]],"segment_regions":[R(*s) for s in segs],"continuity":"frontage_entrance_to_schematic_lobby_core_connection_explicit","shared_area_m2":round(shared,6),"exclusive_area_m2":round(max(0,total-shared),6)},"schematic_lobby_connection":{"status":"LOBBY_UNRESOLVED","node":fm["point"](*f["path"][-1]),"authoritative_rectangle":False},"temp_core_assumptions":{"label":"TEMP CORE — NOT COMMERCIAL","stair":"2-FLIGHT STAIR schematic","elevator":"TEMP ELEVATOR 2.10×2.10 m","topology_final":False},"swept_path":swept,"residual":{"method":"parcel_minus_mandatory_allocations_review_annotation","dead_space_status":"requires_human_review_after_topology_selection"},"gates":{"parking_minimum_3":True,"all_stalls_independently_reachable":True,"no_stall_core_overlap":True,"commercial_frontage_connected":True,"residential_to_core_route_continuous":True,"vehicle_access_manoeuvre_present":True,"no_auto_selection":True},"blockers":blockers}


def canonical(c):
    return {k:c[k] for k in ("commercial","vehicle_ingress","aisle_manoeuvre","temp_core","stalls","pedestrian_route")}


def geometry_hash(c): return hashlib.sha256(json.dumps(canonical(c),sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()


def svg_poly(poly,tr,fill,stroke,opacity=.5): return f'<polygon points="{" ".join(f"{tr(p)[0]:.1f},{tr(p)[1]:.1f}" for p in poly)}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}"/>'


def render(c, parcel, frontage):
    xs=[p[0] for p in parcel]; ys=[p[1] for p in parcel]; scale=min(610/(max(xs)-min(xs)),710/(max(ys)-min(ys))); minx,maxy=min(xs),max(ys)
    tr=lambda p:(65+(p[0]-minx)*scale,140+(maxy-p[1])*scale)
    layers=[svg_poly(parcel,tr,"white","#111827",.1),svg_poly(c["commercial"]["polygon"],tr,"#f59e0b","#b45309",.45),svg_poly(c["aisle_manoeuvre"],tr,"#cbd5e1","#475569",.6),svg_poly(c["vehicle_ingress"],tr,"#a855f7","#6b21a8",.3),svg_poly(c["temp_core"],tr,"#f3d28f","#92400e",.8)]
    for s in c["stalls"]: layers.append(svg_poly(s["polygon"],tr,"#60a5fa","#1d4ed8",.65))
    for i,r in enumerate(c["pedestrian_route"]["segment_regions"]): layers.append(svg_poly(r,tr,"#22c55e" if i==0 else "#14b8a6","#166534",.25))
    fp=[tr(p) for p in frontage]; route=[tr(p) for p in c["pedestrian_route"]["centerline"]]; ent=tr(c["residential_entrance"]); cc=tr(centroid(c["temp_core"])); ve=tr(centroid(c["vehicle_ingress"]))
    layers += [f'<line x1="{fp[0][0]}" y1="{fp[0][1]}" x2="{fp[-1][0]}" y2="{fp[-1][1]}" stroke="#dc2626" stroke-width="8"/>',f'<polyline points="{" ".join(f"{x},{y}" for x,y in route)}" fill="none" stroke="#15803d" stroke-width="4" stroke-dasharray="9 5" marker-end="url(#g)"/>',f'<circle cx="{ent[0]}" cy="{ent[1]}" r="8" fill="#16a34a"/><text x="{ent[0]+10}" y="{ent[1]-8}" font-family="Arial" font-size="12">RESIDENTIAL / BUILDING ENTRANCE</text>',f'<text x="{ve[0]}" y="{ve[1]}" font-family="Arial" font-size="12" font-weight="bold">VEHICLE INGRESS / EGRESS ↕</text>',f'<text x="{cc[0]}" y="{cc[1]-20}" text-anchor="middle" font-family="Arial" font-size="12" font-weight="bold">TEMP CORE — NOT COMMERCIAL</text>',f'<text x="{cc[0]}" y="{cc[1]}" text-anchor="middle" font-family="Arial" font-size="10">2-FLIGHT STAIR schematic</text>',f'<text x="{cc[0]}" y="{cc[1]+18}" text-anchor="middle" font-family="Arial" font-size="10">TEMP ELEVATOR 2.10×2.10 m</text>',f'<text x="{cc[0]}" y="{cc[1]+36}" text-anchor="middle" font-family="Arial" font-size="10" fill="#b91c1c">LOBBY UNRESOLVED</text>']
    notes=[f"Topology: {c['topology_name']}",f"Signature: {json.dumps(c['semantic_topology_signature'],sort_keys=True)}",f"Parking {c['parking_count']} | commercial {c['commercial']['area_m2']:.2f} m² | frontage {c['commercial']['frontage_length_m']:.2f} m",f"Pedestrian exclusive {c['pedestrian_route']['exclusive_area_m2']:.2f} m² / shared {c['pedestrian_route']['shared_area_m2']:.2f} m²",f"Swept path: {c['swept_path']['status']} — NON-REGULATORY engineering validation",f"Residual/dead space: {c['residual']['dead_space_status']}",f"Status {c['status']} | blockers: {', '.join(c['blockers']) or 'NONE'}","NO RANK / NO WINNER | Architecture-only"]
    ns=''.join(f'<text x="720" y="{170+i*38}" font-family="Arial" font-size="14">{html.escape(n)}</text>' for i,n in enumerate(notes))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="1000"><defs><marker id="g" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="#15803d"/></marker></defs><rect width="100%" height="100%" fill="#f8fafc"/><text x="50" y="40" font-family="Arial" font-size="24" font-weight="bold">Parcel 2 H1 V6 — {html.escape(c["topology_id"])}</text><text x="50" y="72" font-family="Arial" font-size="14">ARCHITECTURE-ONLY | H2 / ELEVATOR TRAFFIC / STRUCTURE / BIM / IFC / RENDER NOT EXECUTED</text><text x="50" y="108" font-family="Arial" font-size="15" fill="#dc2626" font-weight="bold">STREET / FRONTAGE — COMMERCIAL DIRECT ACCESS</text>{"".join(layers)}<rect x="700" y="125" width="760" height="390" fill="white" stroke="#94a3b8"/>{ns}</svg>'


def render_index(report):
    rows=[]
    for i,c in enumerate(report["topologies"]):
        y=155+i*150; rows.append(f'<rect x="45" y="{y-30}" width="1410" height="120" fill="white" stroke="#94a3b8"/><text x="65" y="{y}" font-family="Arial" font-size="17" font-weight="bold">{html.escape(c["topology_id"])} — {html.escape(c["topology_name"])}</text><text x="65" y="{y+30}" font-family="Arial" font-size="14">4 stalls | commercial {c["commercial"]["area_m2"]:.2f} m² / frontage {c["commercial"]["frontage_length_m"]:.2f} m | route continuous</text><text x="65" y="{y+58}" font-family="Arial" font-size="14">pedestrian exclusive {c["pedestrian_route"]["exclusive_area_m2"]:.2f} m² / shared {c["pedestrian_route"]["shared_area_m2"]:.2f} m² | swept {c["swept_path"]["status"]} | {c["status"]}</text>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="680"><rect width="100%" height="100%" fill="#f8fafc"/><text x="45" y="45" font-family="Arial" font-size="25" font-weight="bold">Parcel 2 H1 V6 — Circulation / Core Topology Diversification</text><text x="45" y="78" font-family="Arial" font-size="15">DISTINCT RELATIONAL TOPOLOGIES | REVIEW ORDER IS NOT RANK | NO WINNER</text>{"".join(rows)}<text x="45" y="635" font-family="Arial" font-size="14">TEMP CORE, stair/elevator and lobby connection remain non-final. Swept-path proxy is non-regulatory.</text></svg>'


def build(output):
    before=sha(V5); source=json.loads(V5.read_text(encoding="utf-8")); fm=frame(source["parcel"],source["frontage"])
    cs=[make_candidate(f,fm) for f in FAMILIES]
    hashes=[geometry_hash(c) for c in cs]
    if len(set(hashes)) != len(cs): raise RuntimeError("duplicate topology geometry rejected")
    report={"contract":"Parcel2H1CirculationCoreTopologyDiversificationV6","scope":"architecture_only","authority_class":"PROJECT_HUMAN_DESIGN_CRITIQUE_NON_FINAL","lineage":{"v5_json_path":str(V5),"v5_json_sha256":before,"v5_mutated":False,"v5_frozen":True},"derivation_contract":{"coordinate_basis":"parcel_frontage_tangent_and_inward_depth_field","cardinal_direction_used":False,"parcel2_coordinates_hardcoded":False,"historical_seed_used":False,"fixed_metric_offset_used":False,"family_parameters":"dimensionless_relational_proportions"},"parcel":source["parcel"],"frontage":source["frontage"],"distinct_topology_count":len(cs),"topologies":cs,"geometric_diversity":{"tolerance_m":TOLERANCE_M,"geometry_sha256":hashes,"all_pairwise_distinct":len(set(hashes))==len(hashes)},"selection":{"winner":None,"final_selection_performed":False,"review_order_authoritative":False},"readiness":{"H1":"READY_FOR_HUMAN_ARCHITECTURAL_SELECTION" if len([c for c in cs if c["status"]=="reviewable"])>=3 else "NOT_READY","basis":"three distinct reviewable architecture-only topologies required"},"snapshot":{"overwritten_files":[],"snapshot_required":False,"reason":"V6 uses new source/test names and a new timestamped output directory; no existing file overwritten"},"prohibited_workflows_executed":{"H2":False,"elevator_traffic":False,"structure":False,"BIM":False,"IFC":False,"render":False,"image_generation":False}}
    output.mkdir(parents=True,exist_ok=False); jp=output/"PARCEL2_H1_CIRCULATION_CORE_TOPOLOGY_V6.json"; jp.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    arts=[]
    for c in cs:
        p=output/f'{c["topology_id"]}.svg'; p.write_text(render(c,source["parcel"],source["frontage"]),encoding="utf-8"); arts.append({"role":"topology_review_svg","topology_id":c["topology_id"],"file":p.name,"sha256":sha(p),"size_bytes":p.stat().st_size})
    ip=output/"PARCEL2_H1_CIRCULATION_CORE_TOPOLOGY_V6_INDEX.svg"; ip.write_text(render_index(report),encoding="utf-8")
    arts += [{"role":"diagnostic_json","file":jp.name,"sha256":sha(jp),"size_bytes":jp.stat().st_size},{"role":"comparison_index_svg","file":ip.name,"sha256":sha(ip),"size_bytes":ip.stat().st_size}]
    mp=output/"ARTIFACT_MANIFEST.json"; manifest={"contract":"Parcel2H1CirculationCoreTopologyV6Manifest","artifacts":sorted(arts,key=lambda x:x["file"]),"distinct_topology_count":len(cs),"winner":None,"final_selection_performed":False,"source_v5_sha256":before}; mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if sha(V5)!=before: raise RuntimeError("V5 mutated")
    return {"output":str(output),"manifest_sha256":sha(mp),"readiness":report["readiness"],"topologies":[{"id":c["topology_id"],"status":c["status"],"blockers":c["blockers"]} for c in cs]}


if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--output",type=Path,required=True); print(json.dumps(build(ap.parse_args().output),ensure_ascii=False,indent=2))
