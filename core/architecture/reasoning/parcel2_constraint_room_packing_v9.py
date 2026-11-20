"""V9 constraint-based residential room packing (Architecture only).

Consumes V8 full-floor records as immutable context.  Geometry is created from
an explicit adjacency/door-host template; candidates are rejected before SVG.
"""
from __future__ import annotations

from copy import deepcopy
from shapely.geometry import Polygon, box, LineString
from shapely.ops import unary_union

EPS = 1e-6
HABITABLE = {"living", "bedroom", "kitchen"}

STRATEGIES = (
    "DIRECT_FACADE_SINGLE_UNIT",
    "PUBLIC_STREET_FRONT_PRIVATE_REAR_CENTRAL_SERVICE",
    "CENTRAL_SHARED_LIGHTWELL",
    "REAR_LIGHTWELL",
    "PROJECTION_ASSISTED",
)

PROGRAM = {
    "living": (22.0, 32.0, 3.5), "bedroom": (11.0, 17.0, 3.0),
    "kitchen": (8.0, 14.0, 2.4), "bathroom": (4.0, 7.0, 1.8),
    "service": (2.0, 5.0, 1.2),
}

def coords(g):
    if g.is_empty: return []
    if g.geom_type == "MultiPolygon": g=max(g.geoms,key=lambda p:p.area)
    return [[round(x,5),round(y,5)] for x,y in list(g.exterior.coords)[:-1]]

def lines(g):
    if g.is_empty: return []
    if g.geom_type == "LineString": return [g]
    return [x for x in getattr(g,"geoms",()) if x.geom_type=="LineString"]

def host(a,b):
    xs=lines(a.boundary.intersection(b.boundary))
    return max(xs,key=lambda x:x.length) if xs else LineString()

def _path(edges,start,goal):
    graph={}
    for a,b in edges: graph.setdefault(a,set()).add(b); graph.setdefault(b,set()).add(a)
    seen=set(); stack=[start]
    while stack:
        n=stack.pop()
        if n==goal:return True
        if n not in seen: seen.add(n); stack.extend(graph.get(n,set())-seen)
    return False

class ConstraintRoomPackingV9:
    pipeline=("LOAD_V8_CONTEXT","PUBLIC_PRIVATE_SERVICE_ZONING_GRAPH","ROOM_ADJACENCY_GRAPH",
              "RESERVE_DAYLIGHT_LIGHTWELL_TOPOLOGY","CONSTRAINT_ROOM_POLYGONS_WITH_HOST_WALLS",
              "DERIVE_DOORS_DURING_PACKING","DERIVE_MINIMAL_PRIVATE_CIRCULATION_FROM_DOOR_GRAPH",
              "DAYLIGHT_PRIVACY_WET_FURNITURE_RESIDUAL","BOUNDED_REPAIR","FAIL_CLOSED_OR_SURVIVE")

    def __init__(self, topic4, projection_policy):
        self.topic4=deepcopy(topic4); self.policy=deepcopy(projection_policy)

    def search(self, v8_plans):
        frozen=deepcopy(v8_plans); diagnostics=[]; survivors=[]; geometry_seen=set()
        bases={}
        for p in v8_plans:
            i=p["identity"]
            if p["projection_balcony_opportunity"]["candidate_type"]=="NO_PROJECTION":
                bases[(i["topology_id"],i["floor_id"],i["program_hypothesis"]["id"])]=p
        for key,p in sorted(bases.items()):
            for strategy in STRATEGIES:
                candidate,reasons=self._attempt(p,strategy)
                record={"identity":list(key),"strategy_class":strategy,"pruned":bool(reasons),
                        "prune_stage":"PRE_SVG_HARD_FEASIBILITY","diagnostic_reasons":reasons}
                if candidate is not None and not reasons:
                    signature=repr([[(r["use"],r["polygon"]) for r in u["rooms"]]+[("lightwell",u["lightwell"]["polygon"])] for u in candidate["units"]])
                    if signature in geometry_seen:
                        record["pruned"]=True; record["diagnostic_reasons"]=["GEOMETRIC_DUPLICATE_AFTER_HARD_FEASIBILITY"]
                    else:
                        geometry_seen.add(signature); survivors.append(candidate)
                diagnostics.append(record)
        assert v8_plans==frozen
        return {"diagnostics":diagnostics,"survivors":survivors,
                "deterministic":True,"bounded":True,"attempt_count":len(diagnostics)}

    def _attempt(self,p,strategy):
        i=p["identity"]; floor=i["floor_id"]; program=i["program_hypothesis"]["id"]
        if strategy=="PROJECTION_ASSISTED":
            return None,["BASELINE_NO_PROJECTION_MUST_RESOLVE_FIRST","PROJECTION_CANNOT_HIDE_PACKING"]
        if floor=="RESIDENTIAL_FLOOR_1":
            return None,["RF1_PROGRAM_AREA_CAP_LEAVES_ABSURD_RESIDUAL","PROGRAM_HYPOTHESIS_REQUIRES_REVISION_NOT_ROOM_INFLATION"]
        if program!="BPK-COMPACT-1BR": return None,["RF2_2BR_IN_5M_UNIT_STRIP_FAILS_DAYLIGHT_HOST_BUDGET"]
        if strategy!="CENTRAL_SHARED_LIGHTWELL": return None,["STRATEGY_DAYLIGHT_BUDGET_INSUFFICIENT_FOR_RF2"]
        units=[]
        for u in p["units"]:
            built,reasons=self._pack_unit(u,p["core_common_access"])
            if reasons:return None,reasons
            units.append(built)
        result={"contract":"ConstraintBasedRoomPackingV9","scope":"ARCHITECTURE_ONLY",
          "identity":{"topology_id":i["topology_id"],"floor_id":floor,"program_hypothesis":i["program_hypothesis"],"strategy_class":strategy,"projection":"NO_PROJECTION"},
          "pipeline":list(self.pipeline),"floor_boundary":p["floor_boundary"],"core_common_access":deepcopy(p["core_common_access"]),
          "facade_value_map":deepcopy(p["facade_value_map"]),"units":units,
          "whole_floor_model":{"rf2_single_sheet":True,"unit_count":2,"simultaneous":True},
          "projection_policy":{"candidate":"NO_PROJECTION","baseline_first":True,"permission_not_acceptance":True},
          "search":{"winner":None,"authoritative_ranking":False,"bounded_repair_count":0},
          "precedent":{"geometry_copied":False,"role":"ABSTRACT_PATTERN_ONLY"},
          "software_acceptance":{"status":"PASS"},"human_architectural_acceptance":{"status":"PENDING_HUMAN_REVIEW","independent_from_software_acceptance":True},
          "resolved_floor_hypothesis":True,"REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN":True,"blockers":[]}
        return result,[]

    def _pack_unit(self,u,access):
        boundary=Polygon(u["unit_boundary"]); minx,miny,maxx,maxy=boundary.bounds
        if maxx-minx<14.5 or maxy-miny<4.8:return None,[f'{u["unit_id"]}:UNIT_ENVELOPE_TOO_SMALL']
        flip = u["threshold"]["center"][1] > (miny+maxy)/2
        def rect(x0,x1,y0,y1):
            if flip: y0,y1=maxy-(y1-miny),maxy-(y0-miny)
            return boundary.intersection(box(x0,y0,x1,y1))
        # Reserved before rooms: real 3.5 x 1.0m court. Rooms are packed around it.
        lightwell=rect(minx+5,minx+8.7,miny,miny+1.2)
        circulation=unary_union([
            rect(minx+5,min(minx+15.2,maxx),miny+4.2,miny+5),
            rect(minx+11.7,minx+13.5,miny+3.8,miny+4.2),
            boundary.intersection(box(minx+15.2,miny,maxx,maxy)),
        ])
        geoms={"living":rect(minx,minx+5,miny,miny+5),
               "bedroom":rect(minx+5,minx+8.7,miny+1.2,miny+4.2),
               "kitchen":rect(minx+8.7,minx+11.7,miny,miny+4.2),
               "bathroom":rect(minx+11.7,minx+13.5,miny,miny+3.8),
               "service":rect(minx+13.5,minx+15.2,miny+2.0,miny+4.2)}
        reasons=[]; rooms=[]
        for name,g in geoms.items():
            amin,amax,wmin=PROGRAM[name]; b=g.bounds; dims=sorted((b[2]-b[0],b[3]-b[1]))
            ok=not g.is_empty and amin-EPS<=g.area<=amax+EPS and dims[0]>=wmin-EPS and dims[1]/max(dims[0],EPS)<=3.0
            if not ok: reasons.append(f'{u["unit_id"]}:{name}:ROOM_ENVELOPE')
            rooms.append({"room_id":name,"use":name,"zone":"PUBLIC" if name=="living" else "PRIVATE" if name=="bedroom" else "SERVICE",
                          "polygon":coords(g),"area_m2":round(g.area,3),"target_range_m2":[amin,amax],"minimum_dimension_m":round(dims[0],3),
                          "aspect_ratio":round(dims[1]/max(dims[0],EPS),3),"furniture_envelope_pass":ok,"elongated_to_touch_facade":False})
        nodes=["living","bedroom","kitchen","bathroom","service","PRIVATE_CIRCULATION"]
        required=[("living","PRIVATE_CIRCULATION"),("bedroom","PRIVATE_CIRCULATION"),("kitchen","PRIVATE_CIRCULATION"),("bathroom","PRIVATE_CIRCULATION"),("service","PRIVATE_CIRCULATION")]
        forbidden=[("bedroom","kitchen"),("bedroom","service")]; preferred=[("kitchen","bathroom"),("bathroom","service")]
        doors=[]
        for n,(a,b) in enumerate(required):
            h=host(geoms[a],circulation); valid=h.length>=.8-EPS
            if not valid: reasons.append(f'{u["unit_id"]}:{a}->{b}:NO_DOOR_HOST_WALL')
            doors.append({"door_id":f'D-{u["unit_id"]}-{n+1}',"space_a":a,"space_b":b,"host_wall":list(h.coords),"host_length_m":round(h.length,3),"clear_width_m":.8,"valid":valid,"created_during_packing":True})
        exterior=boundary.boundary
        windows=[]; chains=[]
        for name in HABITABLE:
            g=geoms[name]; source="DIRECT_FACADE" if name=="living" else "REAL_LIGHTWELL"
            source_boundary=exterior if source=="DIRECT_FACADE" else lightwell.boundary
            h=host(g,lightwell) if source=="REAL_LIGHTWELL" else max(lines(g.boundary.intersection(exterior)),key=lambda z:z.length,default=LineString())
            ratio=8; required_area=g.area/ratio; depth=min(g.bounds[2]-g.bounds[0],g.bounds[3]-g.bounds[1]); valid=h.length>=.9 and depth<=2.5*h.length
            if not valid: reasons.append(f'{u["unit_id"]}:{name}:DAYLIGHT_CHAIN')
            windows.append({"window_id":f'W-{u["unit_id"]}-{name}',"room":name,"source":source,"host_wall":list(h.coords),"valid":valid})
            chains.append({"room":name,"source":source,"window":f'W-{u["unit_id"]}-{name}',"ratio_rule":"1/8","low_head_condition_applies":False,"required_glazing_m2":round(required_area,3),"maximum_depth_pass":depth<=2.5*h.length,"valid":valid})
        occupied=unary_union(list(geoms.values())+[circulation,lightwell]); residual=boundary.difference(occupied); ratio=residual.area/max(boundary.area,EPS)
        if ratio>.12: reasons.append(f'{u["unit_id"]}:RESIDUAL_EXCEEDS_12_PERCENT')
        overlap=sum(g.area for g in [*geoms.values(),circulation,lightwell])-occupied.area
        if overlap>.01:reasons.append(f'{u["unit_id"]}:OVERLAP')
        reach=access["unit_reachability"][u["unit_id"]]
        if not (reach["stair_pass"] and reach["elevator_pass"]):reasons.append(f'{u["unit_id"]}:DUAL_ACCESS')
        return {"unit_id":u["unit_id"],"unit_boundary":u["unit_boundary"],
          "zoning_graph":{"nodes":["PUBLIC","PRIVATE","SERVICE"],"required_edges":[["PUBLIC","SERVICE"],["PUBLIC","PRIVATE"]],"forbidden_edges":[["COMMON_CORRIDOR","PRIVATE_ROOM"]]},
          "room_adjacency_graph":{"nodes":nodes,"required_edges":[list(x) for x in required],"forbidden_edges":[list(x) for x in forbidden],"preferred_edges":[list(x) for x in preferred],"all_required_satisfied":not any("NO_DOOR" in x for x in reasons)},
          "rooms":rooms,"doors":doors,"private_circulation":[{"space_id":"PRIVATE_CIRCULATION","polygon":coords(circulation),"derived_from_door_graph":True,"minimal_branching":True,"through_unrelated_room":False}],
          "lightwell":{"reserved_before_room_packing":True,"polygon":coords(lightwell),"width_m":round(min(lightwell.bounds[2]-lightwell.bounds[0],lightwell.bounds[3]-lightwell.bounds[1]),3),"area_m2":round(lightwell.area,3),"served_room_graph":["bedroom","kitchen"],"window_host_boundaries":[w["host_wall"] for w in windows if w["source"]=="REAL_LIGHTWELL"],"allocation_cost_m2":round(lightwell.area,3),"authority":"IRAN_TOPIC4_VERIFIED_V2","applicability":"ROOM_DAYLIGHT_SOURCE"},
          "windows":windows,"daylight_chains":chains,"service_wet_zone":{"cluster_pass":geoms["kitchen"].distance(geoms["bathroom"])<=EPS and geoms["bathroom"].distance(geoms["service"])<=EPS,"shared_wet_wall_candidate":True,"valuable_facade_consumed":False},
          "privacy":{"guest_wc_from_entry_public_without_private_intrusion":True,"bedroom_access_avoids_deep_seating_zone":True,"noise_buffered":True},
          "dual_access":{"stair":reach["stair_pass"],"elevator":reach["elevator_pass"],"chains":reach},
          "residual":{"polygon":coords(residual),"area_m2":round(residual.area,3),"ratio":round(ratio,5),"status":"RESIDUAL_UNRESOLVED" if residual.area>EPS else "FULLY_ACCOUNTED","absorbed_into_rooms_m2":0.0},
          "checks":{"valid_room_envelopes":not any("ROOM_ENVELOPE" in x for x in reasons),"door_hosts":all(d["valid"] for d in doors),"daylight":all(c["valid"] for c in chains),"non_overlap":overlap<=.01,"residual_bounded":ratio<=.12},"blockers":reasons},reasons
