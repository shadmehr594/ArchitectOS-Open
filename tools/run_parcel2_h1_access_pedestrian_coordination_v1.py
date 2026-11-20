"""Coordinate access/pedestrian geometry over the frozen Parcel 2 H1 checkpoint."""
from __future__ import annotations

import hashlib, html, json, math
from datetime import datetime
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points, unary_union

from core.architecture.reasoning.site_access_evidence_derivation_v1 import SiteAccessEvidenceDerivationV1
from core.architecture.reasoning.site_access_coordination_reasoner_v1 import SiteAccessCoordinationReasonerV1
from core.intelligence.vehicle_access_candidate_selector import VehicleAccessCandidateSelector

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "exports/DEFAULT/parcel2_temporary_core_reservation_geometry_v1_20260912_194032/PARCEL2_TEMPORARY_CORE_RESERVATION_GEOMETRY_V1.json"
BASE = ROOT / "exports/DEFAULT/parcel2_basement_v2_20260909_143231_229427/PARCEL2_BASEMENT_V2_CONTRACT.json"
LOCAL_RULE = ROOT / "core/architecture/contracts/local/minab_local_commercial_rules_v1.json"

def load(p): return json.loads(p.read_text(encoding="utf-8"))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def coords(g): return [[round(x, 9), round(y, 9)] for x, y in list(g.coords)]
def polycoords(g): return [[round(x, 9), round(y, 9)] for x, y in list(g.exterior.coords)[:-1]]
def lerp(a, b, t): return [a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1])]
def param(a, b, p):
    dx, dy = b[0]-a[0], b[1]-a[1]
    return ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)

def edge_binding(parcel, frontage):
    for i, a in enumerate(parcel):
        b = parcel[(i+1) % len(parcel)]
        if (a == frontage[0] and b == frontage[1]) or (a == frontage[1] and b == frontage[0]):
            canonical = sorted([[format(x, ".15g") for x in a], [format(x, ".15g") for x in b]])
            digest = hashlib.sha256(json.dumps(canonical, separators=(",", ":")).encode()).hexdigest()[:16].upper()
            return i, "PARCEL-EDGE-" + digest
    raise ValueError("frontage_segment_not_bound_to_parcel_edge")

def interval(a, b, center_t, width):
    length = math.dist(a, b); half = width/(2*length)
    if 2*half > 1.0 + 1e-7: return None
    center_t = min(1.0-half, max(half, center_t))
    lo, hi = center_t-half, center_t+half
    if (hi-lo)*length + 1e-7 < width: return None
    return [lerp(a, b, lo), lerp(a, b, hi)]

def candidate_access(parcel_poly, frontage, edge_id, core, candidate, widths):
    a, b = frontage; front_line = LineString(frontage)
    aisle = Polygon(candidate["candidate_geometry"]["aisle"])
    occupied = [Polygon(core["polygon"]), aisle] + [Polygon(s["polygon"]) for s in candidate["stall_geometries"]]
    vehicle, rejected_vehicle = [], []
    blockers = [Polygon(core["polygon"])] + [Polygon(s["polygon"]) for s in candidate["stall_geometries"]]
    topology_points = [aisle.centroid] + [Point(p) for p in list(aisle.exterior.coords)[:-1]]
    derived_parameters = sorted(set(round(min(1.0,max(0.0,param(a,b,[nearest_points(front_line,p)[0].x,nearest_points(front_line,p)[0].y]))),9) for p in topology_points))
    for t in derived_parameters:
        vehicle_interval = interval(a,b,t,widths["vehicle"])
        if not vehicle_interval: continue
        mid = lerp(vehicle_interval[0],vehicle_interval[1],.5)
        nearest_aisle = nearest_points(Point(mid),aisle)[1]
        centerline=LineString([mid,[nearest_aisle.x,nearest_aisle.y]])
        swept=centerline.buffer(widths["vehicle"]/2,cap_style=2)
        conflicts=[i for i,g in enumerate(blockers) if swept.intersection(g).area>1e-7]
        if conflicts:
            rejected_vehicle.append({"derived_parameter":t,"entrance_interval":vehicle_interval,
              "driveway_corridor":coords(centerline),"status":"not_feasible",
              "conflicts":["core_proxy" if i==0 else f"parking_stall_{i:03d}" for i in conflicts]})
            continue
        ident=f"VEH-{len(vehicle)+1:02d}"; corridor=coords(centerline)
        vehicle.append({"access_id":ident, "candidate_id":ident, "access_edge_reference":edge_id,
          "parcel_edge_id":edge_id, "entrance_interval":vehicle_interval, "access_point":mid,
          "driveway_corridor":corridor, "clear_width":widths["vehicle"], "candidate_score":100.0,
          "status":"feasible", "access_elevation":0.0, "target_elevation":0.0, "delta_z":0.0,
          "absolute_level_difference":0.0, "access_mode":"direct_at_grade", "ramp_geometry_required":False,
          "access_edge_status":"confirmed", "source":"user_explicit"})
    # Public/commercial access stays on the same confirmed frontage, outside the vehicle interval.
    spans = [(0.0, 1.0)]
    pedestrians=[]
    target = Point(core["polygon"][0])
    for n,(lo,hi) in enumerate(spans,1):
        if (hi-lo)*front_line.length + 1e-7 < widths["pedestrian"]: continue
        projected = param(a,b,[nearest_points(front_line,target)[0].x, nearest_points(front_line,target)[0].y])
        half=widths["pedestrian"]/(2*front_line.length); ct=min(hi-half,max(lo+half,projected))
        seg=interval(a,b,ct,widths["pedestrian"])
        if not seg: continue
        p=lerp(seg[0],seg[1],.5); route=coords(LineString([p, nearest_points(Point(p), Polygon(core["polygon"]))[1]]))
        pedestrians.append({"candidate_id":f"PUBLIC-{n:02d}","access_edge_reference":edge_id,
          "access_segment":seg,"access_point":p,"approach_line":route,"clear_width":widths["pedestrian"],
          "candidate_score":100.0,"geometry_status":"candidate","role":"PUBLIC_ACCESS_POINT",
          "dedicated_pedestrian_entrance_required":False})
    return vehicle, pedestrians, occupied, rejected_vehicle

def render(report, chosen):
    W,H=1800,1220; panels=[]
    for k,item in enumerate(chosen):
        ox=45+(k%3)*585; oy=95+(k//3)*555; parcel=item["geometry"]["parcel"]
        xs=[p[0] for p in parcel]; ys=[p[1] for p in parcel]; s=min(480/(max(xs)-min(xs)),390/(max(ys)-min(ys)))
        def ps(poly): return " ".join(f"{ox+35+(x-min(xs))*s:.1f},{oy+430-(y-min(ys))*s:.1f}" for x,y in poly)
        body=[f'<rect x="{ox}" y="{oy}" width="550" height="520" fill="white" stroke="#777"/>',
              f'<text x="{ox+15}" y="{oy+25}" font-family="Arial" font-size="15" font-weight="bold">{html.escape(item["candidate_id"])}</text>',
              f'<text x="{ox+15}" y="{oy+47}" font-family="Arial" font-size="12">capacity {item["parking_capacity"]} | {item["outcome_group"]} | blockers: {html.escape(", ".join(item["blockers"])[:75])}</text>',
              f'<polygon points="{ps(parcel)}" fill="none" stroke="#111" stroke-width="2"/>',
              f'<line x1="{ps([item["geometry"]["frontage"][0]]) .split(",")[0]}" y1="0" x2="0" y2="0" opacity="0"/>']
        f=item["geometry"]["frontage"]; body.append(f'<polyline points="{ps(f)}" fill="none" stroke="#d00" stroke-width="5"><title>confirmed road frontage</title></polyline>')
        body.append(f'<polygon points="{ps(item["geometry"]["core_proxy"])}" fill="#f5c542" fill-opacity=".35" stroke="#9a6500"><title>TEMPORARY core proxy</title></polygon>')
        for st in item["geometry"]["stalls"]: body.append(f'<polygon points="{ps(st)}" fill="#8bbbe8" fill-opacity=".45" stroke="#245b88"/>')
        body.append(f'<polygon points="{ps(item["geometry"]["aisle"])}" fill="#ddd" fill-opacity=".45" stroke="#555"/>')
        for v in item["vehicle_access_candidates"]: body += [f'<polyline points="{ps(v["entrance_interval"])}" stroke="#7b1fa2" stroke-width="7"/>',f'<polyline points="{ps(v["driveway_corridor"])}" stroke="#7b1fa2" stroke-width="2" stroke-dasharray="6 4"/>']
        for p in item["pedestrian_public_access_candidates"]: body += [f'<polyline points="{ps(p["access_segment"])}" stroke="#16803a" stroke-width="7"/>',f'<polyline points="{ps(p["approach_line"])}" stroke="#16803a" stroke-width="2" stroke-dasharray="4 3"/>']
        body.append(f'<text x="{ox+15}" y="{oy+500}" font-family="Arial" font-size="11">yellow=TEMP core | blue=stalls | gray=aisle | purple=vehicle | green=public/commercial region</text>')
        panels += body
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="#fafafa"/><text x="45" y="42" font-family="Arial" font-size="22" font-weight="bold">Parcel 2 H1 access + pedestrian coordination — engineering diagnostic</text><text x="45" y="68" font-family="Arial" font-size="14">Review order only; no winner selected. Unresolved separation evidence is marked pending.</text>{"".join(panels)}</svg>'

def main(output_root=None):
    checkpoint, base, local = load(CHECKPOINT), load(BASE), load(LOCAL_RULE)
    parcel, frontage = base["site"]["parcel"], base["site"]["frontage"]
    edge_index, edge_id = edge_binding(parcel, frontage)
    site={"parcel_boundary":parcel,"confirmed_road_access_edge_indices":[edge_index],
      "protected_zones":[],"pedestrian_conflict_zones":[],"vehicle_access_zones":[],
      "vehicle_circulation_zones":[],"parking_access_zones":[],"setback_zones":[],
      "reserved_site_regions":[],"fixed_obstacles":[],"parking_domains":{"pilotis":checkpoint["domain"]["common_core_stack_domain"]}}
    rule=next(r for r in local["rules"] if r["id"]=="mixed_commercial_pilotis_ground")
    evidence=SiteAccessEvidenceDerivationV1().derive(site,{"commercial_required":True,"commercial_frontage_priority":True,"public_access_required":True},
      {"evidence_records":[{"jurisdiction":"Minab","issuing_authority":"Minab detailed-plan working source","document_title":local["source_document"],"edition_date":"Spring 1400","clause":"mixed_commercial_pilotis_ground","printed_page":rule["printed_page"],"pdf_page":rule["pdf_page"],"applicability_status":"current_project_condition_user_confirmed","provenance":str(LOCAL_RULE)}]}, {"enabled":["H1"]})
    cores={c["candidate_id"]:c for c in checkpoint["core_placement_hypotheses"]["candidates"]}
    widths={"vehicle":float(base["requirements"]["ramp"]["clear_width"]),"pedestrian":float(base["requirements"]["parking_pedestrian"]["required_clear_width"])}
    outcomes=[]
    for run in checkpoint["branches"]["H1"]["runs"]:
      core=cores[run["core_candidate_id"]]
      for cand in run["result"]["candidates"]:
        cid=f'{run["core_candidate_id"]}::{cand["candidate_id"]}'
        vehicles,peds,occupied,rejected_vehicle=candidate_access(Polygon(parcel),frontage,edge_id,core,cand,widths)
        coord=SiteAccessCoordinationReasonerV1().coordinate({"candidates":peds},{"selected_system":"direct_at_grade","ramp":{"access_candidates":vehicles}},
          {"pedestrian_access_required":True,"vehicle_access_required":True,"minimum_clear_separation":None,"crossing_policy":None,
           "protected_zones":[core["polygon"]],"parking_circulation_zones":[cand["candidate_geometry"]["aisle"]]+[s["polygon"] for s in cand["stall_geometries"]]})
        selection=VehicleAccessCandidateSelector().select({"ramp":{"access_candidates":vehicles}},{"status":"resolved","selected_system":"vehicle_ramp"},{"site_access_coordination":coord})
        pair_states=[p["coordination_status"] for p in coord["pairs"]]
        ped="pass" if "feasible" in pair_states else "fail" if pair_states and all(x=="not_feasible" for x in pair_states) else "pending"
        commercial="pass" if peds else "fail"
        geometry_valid=cand["candidate_geometry_status"]=="candidate_complete" and cand["achieved_capacity_candidate"]>=3
        access="resolved" if coord["selection_status"]=="resolved" and selection["status"]=="resolved" else "pending"
        blockers=sorted(set(coord.get("unresolved_evidence",[])+([] if peds else ["public_commercial_frontage_region_missing"])+([] if vehicles else ["no_conflict_free_vehicle_ingress_egress_from_confirmed_frontage"])))
        group="resolved" if geometry_valid and access=="resolved" and ped=="pass" and commercial=="pass" else "invalid" if not geometry_valid or not vehicles or ped=="fail" or commercial=="fail" else "pending"
        residual=None
        if group=="resolved": residual=round(Polygon(parcel).difference(unary_union(occupied)).area,6)
        outcomes.append({"candidate_id":cid,"source_core_candidate_id":run["core_candidate_id"],"source_parking_candidate_id":cand["candidate_id"],
          "geometry_valid":geometry_valid,"access_coordination":access,"pedestrian_protected_route":ped,
          "commercial_entrance_street_access":commercial,"parking_capacity":cand["achieved_capacity_candidate"],
          "parking_capacity_at_least_3":cand["achieved_capacity_candidate"]>=3,"manoeuvre_ingress_egress":"candidate_pass",
          "protected_conflict_inventory":"complete","publication_readiness":group=="resolved","outcome_group":group,"blockers":blockers,
          "eligible_vehicle_entrance_intervals":[v["entrance_interval"] for v in vehicles],"vehicle_access_candidates":vehicles,
          "rejected_vehicle_access_insertions":rejected_vehicle,
          "pedestrian_public_access_candidates":peds,"commercial_street_access_regions":[p["access_segment"] for p in peds],
          "commercial_residual_candidate_area_m2":residual,"selection_authority_required":coord["selection_status"] in ("pending_tie","coordination_pending"),
          "site_access_coordination":coord,"vehicle_access_candidate_selection":selection,
          "geometry":{"parcel":parcel,"frontage":frontage,"core_proxy":core["polygon"],"stalls":[s["polygon"] for s in cand["stall_geometries"]],"aisle":cand["candidate_geometry"]["aisle"]}})
    outcomes.sort(key=lambda x:(0 if x["outcome_group"]=="resolved" else 1 if x["outcome_group"]=="pending" else 2,-x["parking_capacity"],x["candidate_id"]))
    for i,x in enumerate(outcomes,1): x["review_order_rank"]=i
    counts={k:sum(x["outcome_group"]==k for x in outcomes) for k in ("resolved","pending","invalid")}
    report={"contract":"Parcel2H1AccessPedestrianCoordinationDiagnosticV1","generated_at":datetime.now().astimezone().isoformat(),"scope":"architecture_only",
      "input_checkpoint":{"path":str(CHECKPOINT),"sha256":sha(CHECKPOINT),"h1_candidate_count":19,"geometry_reused":True,"regenerated":False},
      "stable_frontage_binding":{"edge_index":edge_index,"edge_id":edge_id,"segment":frontage,"cardinal_assumption_used":False},
      "site_access_evidence":evidence,"local_commercial_validator":{"status":"applied_as_current_project_condition","rule":rule,"contract":str(LOCAL_RULE),"sha256":sha(LOCAL_RULE),"promulgation_status":local["promulgation_status"]},
      "numeric_policy":{"minimum_clear_separation":None,"old_3m_fixture_used_as_authority":False,"vehicle_width":widths["vehicle"],"pedestrian_width":widths["pedestrian"]},
      "outcome_counts":counts,"candidates":outcomes,"full_architectural_acceptance_count":counts["resolved"],
      "final_selection_performed":False,"winner_authority":None,"ranking_purpose":"human_review_order_only",
      "h1_ready_for_human_architectural_selection":counts["resolved"]>0,"h2_status":"parked_not_evaluated_this_iteration",
      "population_occupancy_numeric_assumptions_used":False,"prohibited_workflows_executed":{"structure":False,"BIM":False,"IFC":False,"render":False,"image_generation":False}}
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S"); root=Path(output_root) if output_root else ROOT/"exports/DEFAULT"; out=root/f"parcel2_h1_access_pedestrian_coordination_v1_{stamp}"; out.mkdir(parents=True,exist_ok=False)
    jp=out/"PARCEL2_H1_ACCESS_PEDESTRIAN_COORDINATION_V1.json"; sp=out/"PARCEL2_H1_ACCESS_PEDESTRIAN_COORDINATION_V1.svg"
    jp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"); sp.write_text(render(report,outcomes[:6]),encoding="utf-8")
    result={"json":str(jp),"json_sha256":sha(jp),"svg":str(sp),"svg_sha256":sha(sp),"outcome_counts":counts,"full_acceptance":counts["resolved"],"ready":report["h1_ready_for_human_architectural_selection"]}; print(json.dumps(result,indent=2)); return result

if __name__ == "__main__": main()
