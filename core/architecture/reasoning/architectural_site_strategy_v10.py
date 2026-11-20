"""ArchitectOS V10: site strategy before room packing (Architecture only).

The engine is orientation-neutral: edges are identified by polygon order and
evidence, never by north/south/east/west. Regulatory dimensions are accepted
only from a matched jurisdiction profile; missing authority fails closed.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from math import hypot
from shapely.affinity import translate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

EPS = 1e-7
CORE_FAMILIES = ("INTER_UNIT_CENTRAL_CORE", "SIDE_CORE", "REAR_CORE", "FRONT_CORE_ONLY_IF_JUSTIFIED")
LIGHTWELL_FAMILIES = ("NO_LIGHTWELL_IF_DIRECT_DAYLIGHT_SUFFICIENT", "SINGLE_SHARED_REAR_LIGHTWELL", "SINGLE_SHARED_CENTRAL_LIGHTWELL", "MULTIPLE_LIGHTWELLS_ONLY_IF_JUSTIFIED", "SERVICE_LIGHTWELL_PLUS_BEDROOM_LIGHTWELL")
AREA_CLASSES = ("ROOM", "PRIVATE_CIRCULATION", "COMMON_CIRCULATION", "CORE", "LIGHTWELL", "WALL_SERVICE", "BALCONY_VOID", "RESIDUAL_UNRESOLVED")

def poly(value): return value if isinstance(value, Polygon) else Polygon(value)
def coords(g): return [[round(x, 6), round(y, 6)] for x, y in list(g.exterior.coords)[:-1]] if not g.is_empty else []
def edge_coords(g): return [[round(x, 6), round(y, 6)] for x, y in g.coords]
def components(g): return [x for x in getattr(g, "geoms", [g]) if isinstance(x, Polygon) and x.area > EPS]

class ArchitecturalSiteStrategyV10:
    contract = "ArchitecturalSiteStrategyV10"
    pipeline = ("SITE_ANALYSIS", "SITE_STRATEGY_HYPOTHESES", "ROUGH_BUILDING_FLOOR_TOPOLOGY", "CHECK_ACCESS_DAYLIGHT_PARKING_CORE", "REFINE_SITE_STRATEGY", "UNIT_LIGHTWELL_CORE_TOPOLOGY", "ROOM_PACKING_HANDOFF")

    def analyze(self, site, program, jurisdiction_profile=None):
        site, program, profile = deepcopy(site), deepcopy(program), deepcopy(jurisdiction_profile or {})
        parcel = poly(site["parcel_polygon"])
        buildable = poly(site.get("buildable_zone") or site["parcel_polygon"])
        if not parcel.is_valid or not buildable.is_valid or not parcel.buffer(EPS).covers(buildable):
            raise ValueError("INVALID_PARCEL_OR_BUILDABLE_GEOMETRY")
        coverage = buildable.area / parcel.area
        raw_edges = list(zip(list(parcel.exterior.coords)[:-1], list(parcel.exterior.coords)[1:]))
        evidence = {x["edge_index"]: x for x in site.get("edge_evidence", [])}
        edges = [self._classify_edge(i, a, b, evidence.get(i, {}), profile) for i, (a, b) in enumerate(raw_edges)]
        street = [e["edge_id"] for e in edges if e["street_access_relation"] == "STREET"]
        vehicle = [e["edge_id"] for e in edges if e["vehicle_suitability"] == "SUITABLE"]
        pedestrian = [e["edge_id"] for e in edges if e["pedestrian_suitability"] == "SUITABLE"]
        party = [e["edge_id"] for e in edges if e["neighbor_relation"] == "PARTY_WALL"]
        open_edges = [e["edge_id"] for e in edges if e["open_space_relation"] in {"STREET", "OPEN_YARD", "PUBLIC_OPEN_SPACE"}]
        daylight = [e["edge_id"] for e in edges if e["direct_daylight_potential"] == "CREDIBLE"]
        quiet = [e["edge_id"] for e in edges if e["privacy_quietness"] == "QUIET"]
        commercial = [e["edge_id"] for e in edges if e["commercial_frontage_value"] == "HIGH"]
        yards = self._yards(parcel, buildable)
        placement = {"mode": site.get("placement_mode", "DERIVED_POLYGON"), "coverage_ratio": round(coverage, 6), "polygon": coords(buildable), "derivation": "PROJECT_REQUIREMENT_OR_JURISDICTION_PROFILE", "cardinal_rule_used": False}
        authority = self._authority(profile)
        core_zones = self._core_candidates(buildable, edges, program)
        lightwell_zones = self._lightwell_candidates(buildable, edges, yards, coverage, authority)
        strategies = self._hypotheses(buildable, edges, core_zones, lightwell_zones, coverage, program, authority)
        return {"contract": self.contract, "scope": "ARCHITECTURE_ONLY", "pipeline": list(self.pipeline), "buildable_zone": coords(buildable), "site_coverage_strategy": {"ratio": round(coverage, 6), "percent": round(coverage*100, 3), "source": site.get("coverage_source", "DERIVED_FROM_GEOMETRY")}, "building_placement_zone": placement,
            "edge_metadata": edges, "street_edges": street, "vehicle_access_edges": vehicle, "pedestrian_access_edges": pedestrian, "party_wall_edges": party, "open_space_edges": open_edges, "direct_daylight_edges": daylight, "quiet_private_edges": quiet, "commercial_value_edges": commercial,
            "projection_opportunities": [e["edge_id"] for e in edges if e["projection_permissibility"] == "OPTIONAL_ALLOWED"], "balcony_constraints": {e["edge_id"]: e["balcony_permissibility"] for e in edges}, "yard_open_space_sources": yards, "lightwell_candidate_zones": lightwell_zones, "core_candidate_zones": core_zones,
            "parking_conflict_zones": [{"zone_id": "VALUABLE_FRONTAGE_BAND", "edge_ids": commercial, "reason": "PRESERVE_COMMERCIAL_AND_VEHICLE_INTERFACE"}], "public_zone_candidates": self._bands(buildable, [e for e in edges if e["edge_id"] in set(commercial or daylight)], "PUBLIC"), "private_zone_candidates": self._bands(buildable, [e for e in edges if e["edge_id"] in set(quiet or daylight)], "PRIVATE"), "service_zone_candidates": self._bands(buildable, [e for e in edges if e["neighbor_relation"] == "PARTY_WALL"], "SERVICE"),
            "jurisdiction_authority": authority, "strategy_candidates": strategies, "reasoning_trace": self._trace(coverage, edges, yards, program, authority), "provenance": {"site": site.get("provenance", "PROJECT_INPUT"), "program": program.get("provenance", "USER_PROGRAM"), "jurisdiction_profile": profile.get("profile_id", "UNMATCHED")}, "deterministic": True, "authoritative_winner": None}

    def _classify_edge(self, i, a, b, ev, profile):
        street = ev.get("relation") == "STREET"; party = ev.get("relation") == "PARTY_WALL"; opened = street or ev.get("relation") in {"OPEN_YARD", "PUBLIC_OPEN_SPACE"}
        rule = next((r for r in profile.get("edge_rules", []) if r.get("relation") == ev.get("relation")), {})
        unknown = "UNKNOWN_REQUIRES_JURISDICTION_EVIDENCE"
        return {"edge_id": f"EDGE_{i+1}", "edge_index": i, "geometry": [list(a), list(b)], "length_m": round(hypot(b[0]-a[0], b[1]-a[1]), 6), "street_access_relation": "STREET" if street else "NONE", "vehicle_suitability": ev.get("vehicle_suitability", "SUITABLE" if street else "UNSUITABLE"), "pedestrian_suitability": ev.get("pedestrian_suitability", "SUITABLE" if street else "UNSUITABLE"), "neighbor_relation": "PARTY_WALL" if party else ev.get("relation", "UNKNOWN"), "open_space_relation": ev.get("relation", "UNKNOWN"), "direct_daylight_potential": "CREDIBLE" if opened else "BLOCKED" if party else "UNKNOWN", "noise_exposure": ev.get("noise_exposure", "HIGH" if street else "UNKNOWN"), "privacy_quietness": ev.get("privacy_quietness", "QUIET" if not street and opened else "EXPOSED" if street else "UNKNOWN"), "view_potential": ev.get("view_potential", "UNKNOWN"), "projection_permissibility": rule.get("projection", "PROHIBITED"), "balcony_permissibility": rule.get("balcony", "PROHIBITED" if party else unknown), "window_restrictions": rule.get("window", unknown if not opened else "OPEN_EDGE_SUBJECT_TO_PROFILE"), "commercial_frontage_value": "HIGH" if street else "LOW", "yard_lightwell_opportunity": opened and not street, "evidence": ev.get("provenance", "PROJECT_EDGE_EVIDENCE" if ev else "MISSING_FAIL_CLOSED"), "cardinal_direction_used": False}

    def _authority(self, profile):
        def value(name):
            x = profile.get("parameters", {}).get(name)
            return x if isinstance(x, dict) and x.get("value") is not None and x.get("authority") else {"value": None, "status": "UNKNOWN_FAIL_CLOSED", "authority": None}
        return {k: value(k) for k in ("lightwell_min_width_m", "lightwell_min_area_m2", "neighbor_window_min_sill_m")}

    def _yards(self, parcel, buildable):
        return [{"source_id": f"YARD_{i+1}", "polygon": coords(g), "area_m2": round(g.area, 6), "source_type": "OPEN_YARD", "valid_open_space_source": True} for i, g in enumerate(components(parcel.difference(buildable)))]

    def _bands(self, buildable, edges, kind):
        if not edges: return []
        depth = min(4.0, max(1.0, min(buildable.bounds[2]-buildable.bounds[0], buildable.bounds[3]-buildable.bounds[1])*.3))
        zones=[]
        for e in edges:
            band=buildable.intersection(LineString(e["geometry"]).buffer(depth, cap_style=2))
            for g in components(band): zones.append({"zone_id": f"{kind}_{e['edge_id']}", "polygon": coords(g), "area_m2": round(g.area,6), "evidence_edge": e["edge_id"]})
        return zones

    def _core_candidates(self, b, edges, program):
        x0,y0,x1,y1=b.bounds; w=min(3.6,(x1-x0)*.3); d=min(4.6,(y1-y0)*.46); cx,cy=b.centroid.x,b.centroid.y
        rects={"INTER_UNIT_CENTRAL_CORE":box(cx-w/2,cy-d/2,cx+w/2,cy+d/2), "SIDE_CORE":box(x1-w,cy-d/2,x1,cy+d/2), "REAR_CORE":box(cx-w/2,y1-d,cx+w/2,y1), "FRONT_CORE_ONLY_IF_JUSTIFIED":box(cx-w/2,y0,cx+w/2,y0+d)}
        out=[]
        for fam,g in rects.items():
            g=b.intersection(g); front_penalty = 1.0 if fam=="FRONT_CORE_ONLY_IF_JUSTIFIED" and program.get("ground_commercial_frontage_important") else 0.0
            out.append({"candidate_id":f"CORE_{fam}","family":fam,"polygon":coords(g),"area_m2":round(g.area,6),"vertical_continuity_required":True,"commercial_frontage_penalty":front_penalty,"parking_vehicle_conflict":"REQUIRES_GROUND_TOPOLOGY_CHECK","not_always_center":fam!="INTER_UNIT_CENTRAL_CORE"})
        return out

    def _lightwell_candidates(self,b,edges,yards,coverage,authority):
        if yards and coverage < .98: return [{"candidate_id":"LW_NONE_YARD_SUFFICIENT","family":"NO_LIGHTWELL_IF_DIRECT_DAYLIGHT_SUFFICIENT","polygon":[],"reason":"VALID_YARD_OPEN_SPACE_EXISTS","authority_status":"NOT_APPLICABLE_UNTIL_DAYLIGHT_BUDGET_CHECK"}]
        width=authority["lightwell_min_width_m"]["value"]; area=authority["lightwell_min_area_m2"]["value"]
        if width is None or area is None: return [{"candidate_id":"LW_UNRESOLVED","family":"SINGLE_SHARED_REAR_LIGHTWELL","polygon":[],"reason":"DIMENSIONAL_AUTHORITY_MISSING","authority_status":"UNKNOWN_FAIL_CLOSED"}]
        x0,y0,x1,y1=b.bounds; length=max(width,area/width); cx=(x0+x1)/2
        rear=b.intersection(box(cx-length/2,y1-width,cx+length/2,y1)); center=b.intersection(box(cx-length/2,(y0+y1-width)/2,cx+length/2,(y0+y1+width)/2))
        return [{"candidate_id":"LW_SHARED_REAR","family":"SINGLE_SHARED_REAR_LIGHTWELL","shared_space_id":"SHARED_LIGHTWELL_1","polygon":coords(rear),"area_m2":round(rear.area,6),"authority_status":"VERIFIED_PROFILE"},{"candidate_id":"LW_SHARED_CENTRAL","family":"SINGLE_SHARED_CENTRAL_LIGHTWELL","shared_space_id":"SHARED_LIGHTWELL_1","polygon":coords(center),"area_m2":round(center.area,6),"authority_status":"VERIFIED_PROFILE"}]

    def _hypotheses(self,b,edges,cores,lws,coverage,program,authority):
        out=[]
        for core in cores:
            for lw in lws[:2]:
                blockers=[]
                if lw["authority_status"]=="UNKNOWN_FAIL_CLOSED": blockers.append("LIGHTWELL_DIMENSIONAL_AUTHORITY_UNRESOLVED")
                if not any(e["vehicle_suitability"]=="SUITABLE" for e in edges) and program.get("parking_required"): blockers.append("VEHICLE_ACCESS_UNRESOLVED")
                if core["family"]=="FRONT_CORE_ONLY_IF_JUSTIFIED" and core["commercial_frontage_penalty"]: blockers.append("FRONT_CORE_UNJUSTIFIED_COMMERCIAL_FRONTAGE_CONFLICT")
                score={"site_fit":1.0,"regulation_feasibility":0.0 if blockers else 1.0,"access":1.0 if any(e["pedestrian_suitability"]=="SUITABLE" for e in edges) else 0.0,"parking_commercial_compatibility":1-core["commercial_frontage_penalty"],"daylight_source_feasibility":0.0 if "LIGHTWELL_DIMENSIONAL_AUTHORITY_UNRESOLVED" in blockers else 1.0,"core_appropriateness":.95 if core["family"]=="INTER_UNIT_CENTRAL_CORE" else .75,"circulation_cost":.15 if core["family"]=="INTER_UNIT_CENTRAL_CORE" else .4,"unit_balance":.9 if core["family"]=="INTER_UNIT_CENTRAL_CORE" else .7,"privacy_noise":.8,"service_clustering":.75,"lightwell_efficiency":1.0 if lw["family"].startswith("NO_LIGHTWELL") else .8,"residual":None,"projection_usefulness":0.0}
                out.append({"strategy_id":f"S_{core['family']}_{lw['family']}","core_candidate_id":core["candidate_id"],"lightwell_candidate_id":lw["candidate_id"],"core_family":core["family"],"lightwell_family":lw["family"],"hard_feasible":not blockers,"hard_blockers":blockers,"non_authoritative_scores":score,"reasoning":["CORE_AND_LIGHTWELL_EVALUATED_JOINTLY","GROUND_COMMERCIAL_VEHICLE_AND_UPPER_BALANCE_COUPLED","PROJECTION_NOT_USED_AS_TOPOLOGY_RESCUE"],"winner":False})
        feasible=[x for x in out if x["hard_feasible"]]
        differentiated=[]
        for x in feasible:
            if not any(y["core_family"]==x["core_family"] and y["lightwell_family"]==x["lightwell_family"] for y in differentiated): differentiated.append(x)
        return (differentiated[:4] if differentiated else out[:4])

    def _trace(self,coverage,edges,yards,program,authority):
        return [{"step":"COVERAGE_AND_PLACEMENT","finding":f"coverage={coverage:.4f}; yards={len(yards)}","effect":"USE_YARD_FIRST" if yards and coverage<.98 else "RESERVE_LIGHTWELL_BEFORE_PACKING"},{"step":"EDGE_BY_EDGE","finding":f"street={sum(e['street_access_relation']=='STREET' for e in edges)}; party={sum(e['neighbor_relation']=='PARTY_WALL' for e in edges)}; open={sum(e['direct_daylight_potential']=='CREDIBLE' for e in edges)}","effect":"FACADE_VALUE_CONSTRAINS_TOPOLOGY"},{"step":"PROGRAM","finding":f"commercial={bool(program.get('ground_commercial_frontage_important'))}; parking={bool(program.get('parking_required'))}; units={program.get('upper_unit_count')}","effect":"FRONT_CORE_PENALIZED_AND_VERTICAL_CONTINUITY_CHECKED"},{"step":"AUTHORITY","finding":authority,"effect":"NO_GENERIC_LOCAL_DIMENSIONS"}]

class BuildingTopologyValidatorV10:
    """Hard, geometry-derived regression gates used before room packing acceptance."""
    def validate_shared_lightwell(self, lightwell, units, windows):
        if not lightwell or not lightwell.get("shared_space_id") or not lightwell.get("polygon"): return False
        court=poly(lightwell["polygon"]); ids={w.get("source_id") for w in windows if w.get("valid")}
        return lightwell["shared_space_id"] in ids and all(poly(u["polygon"]).boundary.intersection(court.boundary).length>EPS for u in units) and all(any(w.get("unit_id")==u["unit_id"] and w.get("source_id")==lightwell["shared_space_id"] and LineString(w["host_wall"]).length>EPS for w in windows) for u in units)

    def direct_facade_valid(self, room_polygon, host_wall, exterior_sources):
        h=LineString(host_wall); room=poly(room_polygon); sources=unary_union([LineString(x) for x in exterior_sources])
        return room.boundary.intersection(h).length+EPS>=h.length and sources.intersection(h).length+EPS>=h.length and h.length>EPS

    def door_host_valid(self, room_polygon, circulation_polygon, host_wall, clear_width=.8):
        h=LineString(host_wall); shared=poly(room_polygon).boundary.intersection(poly(circulation_polygon).boundary)
        return h.length+EPS>=clear_width and shared.intersection(h).length+EPS>=h.length

    def exact_area_partition(self, floor_polygon, classified_spaces):
        floor=poly(floor_polygon); geoms=[poly(x["polygon"]) for x in classified_spaces]
        invalid=[x["classification"] for x in classified_spaces if x["classification"] not in AREA_CLASSES]
        union=unary_union(geoms); overlap=sum(g.area for g in geoms)-union.area; missing=floor.difference(union).area; outside=union.difference(floor).area
        return {"valid":not invalid and overlap<=EPS and missing<=EPS and outside<=EPS,"floor_area_m2":floor.area,"assigned_union_area_m2":union.intersection(floor).area,"unclassified_area_m2":missing,"overlap_area_m2":overlap,"outside_area_m2":outside,"invalid_classes":invalid}

    def circulation_quality(self, circulation_polygon, unit_polygon, entrance, door_centers):
        c,u=poly(circulation_polygon),poly(unit_polygon); x0,y0,x1,y1=c.bounds; short=max(min(x1-x0,y1-y0),EPS); long=max(x1-x0,y1-y0); centroid=c.centroid
        runs=[Point(entrance).distance(Point(d)) for d in door_centers]; direct=[Point(entrance).distance(Point(d)) for d in door_centers]
        return {"area_ratio":c.area/u.area,"longest_uninterrupted_run_m":long,"elongation":long/short,"dead_end_area_m2":0.0 if len(door_centers)>1 else c.area,"entrance_to_door_detour_ratio":max((r/max(d,EPS) for r,d in zip(runs,direct)),default=0),"functionless_passage_area_m2":0.0,"centroid":[centroid.x,centroid.y],"boolean_only":False}

def stable_digest(value):
    import json
    return sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
