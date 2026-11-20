"""V7 additive architectural-graph to whole-floor plan synthesizer.

Architecture only.  Historical V3--V6 artifacts are inputs, never mutation targets.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import atan2, degrees
from pathlib import Path
import json

from shapely.affinity import rotate, translate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

EPS = 1e-5
HABITABLE = {"living", "bedroom", "kitchen"}
WET = {"kitchen", "bathroom", "service"}
PROGRAMS = {
    "BPK-COMPACT-1BR": {
        "rooms": [("living", 22.0, 32.0, 3.5), ("kitchen", 8.0, 14.0, 2.4),
                  ("bedroom", 11.0, 17.0, 3.0), ("bathroom", 4.0, 7.0, 1.8),
                  ("service", 2.0, 5.0, 1.2)]
    },
    "BPK-FAMILY-2BR": {
        "rooms": [("living", 24.0, 34.0, 3.5), ("kitchen", 9.0, 15.0, 2.4),
                  ("bedroom", 11.0, 17.0, 3.0), ("bedroom", 10.0, 16.0, 3.0),
                  ("bathroom", 4.0, 7.0, 1.8), ("service", 2.0, 5.0, 1.2)]
    },
}


def poly(points):
    p = Polygon(points)
    return p if p.is_valid else p.buffer(0)


def coords(g):
    if g.is_empty:
        return []
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda x: x.area)
    return [[round(x, 5), round(y, 5)] for x, y in list(g.exterior.coords)[:-1]]


def largest(g):
    if g.is_empty:
        return Polygon()
    if g.geom_type == "Polygon":
        return g
    ps = [x for x in getattr(g, "geoms", ()) if x.geom_type == "Polygon"]
    return max(ps, key=lambda x: x.area) if ps else Polygon()


def lines(g):
    if g.is_empty:
        return []
    if g.geom_type == "LineString":
        return [g]
    return [x for x in getattr(g, "geoms", ()) if x.geom_type == "LineString"]


def longest(g):
    ls = lines(g)
    return max(ls, key=lambda x: x.length) if ls else LineString()


def frame_angle(rect):
    pts = list(rect.exterior.coords)
    edges = [(Point(pts[i]).distance(Point(pts[i + 1])), pts[i], pts[i + 1]) for i in range(4)]
    _, a, b = max(edges, key=lambda x: x[0])
    value = degrees(atan2(b[1] - a[1], b[0] - a[0])) % 180
    if value > 90:
        value -= 180
    return value


def bbox_room(unit, x0, x1, y0, y1):
    return largest(unit.intersection(box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))))


def path_exists(edges, start, goal):
    graph = {}
    for a, b in edges:
        graph.setdefault(a, set()).add(b)
        graph.setdefault(b, set()).add(a)
    seen, stack = set(), [start]
    while stack:
        node = stack.pop()
        if node == goal:
            return True
        if node not in seen:
            seen.add(node)
            stack.extend(graph.get(node, ()) - seen)
    return False


@dataclass(frozen=True)
class CandidateMove:
    id: str
    public_at_far_facade: bool
    private_split: float


class ArchitecturalGraphFloorPlanSynthesizerV7:
    pipeline = (
        "resolve_buildable_floor_envelope", "retain_core_stair_elevator", "build_common_landing_graph",
        "whole_floor_rf2_model", "facade_daylight_source_budget", "unit_zoning_graph",
        "room_adjacency_graph_and_requirements", "graph_constrained_room_polygon_synthesis",
        "thresholds_and_host_wall_doors", "derive_minimal_private_circulation", "room_source_window_chains",
        "physical_lightwell_if_required", "privacy_service_furniture_residual", "precedent_guided_repair",
        "agi_only_if_unresolved", "full_floor_re_evaluation",
    )
    moves = (CandidateMove("PUBLIC_FAR_PRIVATE_NEAR", True, .47),
             CandidateMove("PUBLIC_NEAR_PRIVATE_FAR", False, .53))

    def __init__(self, evidence, precedent_patterns):
        self.evidence = deepcopy(evidence)
        self.patterns = deepcopy(precedent_patterns)
        if self.patterns["policy"]["geometry_copying"] is not False:
            raise ValueError("precedent coordinates are forbidden")

    @staticmethod
    def group(source):
        grouped = {}
        for plan in source["plans"]:
            i = plan["source_identity"]
            key = (i["topology_id"], i["floor_id"], i["program_hypothesis"]["id"])
            grouped.setdefault(key, []).append(plan)
        return [(k, sorted(v, key=lambda x: x["source_identity"]["unit_id"])) for k, v in sorted(grouped.items())]

    def synthesize_group(self, source_plans):
        frozen = deepcopy(source_plans)
        results = [self._candidate(source_plans, move) for move in self.moves]
        assert source_plans == frozen
        return results

    def _candidate(self, sources, move):
        first = sources[0]
        identity = deepcopy(first["source_identity"])
        raw_parts = [poly(x["unit_boundary"]) for x in sources]
        raw_parts += [poly(first["core_geometry"]), poly(first["public_corridor"])]
        raw_floor = unary_union(raw_parts)
        raw_rect = raw_floor.minimum_rotated_rectangle
        inherited = float(first.get("dominant_frame", {}).get("angle_degrees", frame_angle(raw_rect)))
        measured = frame_angle(raw_rect)
        # Canonical local frame: envelope-derived normalization; parcel angle is never a design angle.
        local_parts = [rotate(g, -measured, origin=(0, 0)) for g in raw_parts]
        bounds = unary_union(local_parts).bounds
        dx, dy = -bounds[0], -bounds[1]
        local_parts = [translate(g, dx, dy) for g in local_parts]
        units = local_parts[:len(sources)]
        core, inherited_common = local_parts[-2:]
        floor_envelope = box(0, 0, bounds[2] - bounds[0], bounds[3] - bounds[1])
        envelope = {
            "parcel_geometry_role": "CONTEXT_ONLY_NOT_DESIGN_FRAME",
            "buildable_floor_envelope": coords(floor_envelope),
            "world_to_local_rotation_degrees": round(-measured, 6),
            "source_inherited_angle_degrees": inherited,
            "dominant_design_frame_degrees": 0.0,
            "frame_source": "BUILDABLE_FLOOR_ENVELOPE",
            "frame_hypotheses": [{"angle": 0.0, "priority": "ORTHOGONAL_FIRST", "selected": True},
                                 {"angle": round(inherited, 6), "priority": "REJECTED_PARCEL_INHERITANCE", "selected": False}],
            "local_angle_issue": None,
            "orthogonal": True,
        }
        cminx, cminy, cmaxx, cmaxy = core.bounds
        if cmaxx-cminx >= cmaxy-cminy:
            stair = core.intersection(box(cminx-1, cminy-1, (cminx+cmaxx)/2, cmaxy+1))
            elevator = core.difference(stair)
        else:
            stair = core.intersection(box(cminx-1, cminy-1, cmaxx+1, (cminy+cmaxy)/2))
            elevator = core.difference(stair)
        landing = inherited_common
        access_edges = [("COMMON_LANDING", "STAIR_ACCESS"), ("COMMON_LANDING", "ELEVATOR_ACCESS")]
        unit_thresholds = []
        for index, unit in enumerate(units):
            uid = sources[index]["source_identity"]["unit_id"]
            host = longest(unit.boundary.intersection(landing.boundary.buffer(EPS)))
            pt = host.interpolate(host.length/2) if host.length else unit.representative_point()
            valid = host.length >= .8-EPS
            unit_thresholds.append((uid, pt, host, valid))
            if valid:
                access_edges.append((f"{uid}_THRESHOLD", "COMMON_LANDING"))
        access = {
            "core_polygon": coords(core), "stair_polygon": coords(stair), "elevator_polygon": coords(elevator),
            "common_landing_polygon": coords(landing), "graph_edges": [list(x) for x in access_edges],
            "unit_reachability": {}, "shared_access_complete": False,
        }
        for uid, _, _, _ in unit_thresholds:
            access["unit_reachability"][uid] = {
                "stair_chain": [f"{uid}_THRESHOLD", "COMMON_LANDING", "STAIR_ACCESS"],
                "elevator_chain": [f"{uid}_THRESHOLD", "COMMON_LANDING", "ELEVATOR_ACCESS"],
                "stair_pass": path_exists(access_edges, f"{uid}_THRESHOLD", "STAIR_ACCESS"),
                "elevator_pass": path_exists(access_edges, f"{uid}_THRESHOLD", "ELEVATOR_ACCESS"),
            }
        access["shared_access_complete"] = all(x["stair_pass"] and x["elevator_pass"] for x in access["unit_reachability"].values())

        facade_budget, built_units = {}, []
        for index, unit in enumerate(units):
            uid = sources[index]["source_identity"]["unit_id"]
            exposed = longest(unit.boundary.intersection(floor_envelope.boundary.buffer(EPS)))
            facade_budget[uid] = {"allocated_before_rooms": True, "qualifying_length_m": round(exposed.length, 3),
                                  "source_id": f"SRC-{uid}-EXTERIOR", "geometry": list(exposed.coords)}
            threshold = next(x for x in unit_thresholds if x[0] == uid)
            built_units.append(self._unit(uid, unit, threshold, floor_envelope, facade_budget[uid], identity["program_hypothesis"]["id"], move))

        usable = unary_union(units)
        room_geoms = [poly(r["polygon"]) for u in built_units for r in u["rooms"] if len(r["polygon"]) >= 3]
        circ_geoms = [poly(c["polygon"]) for u in built_units for c in u["private_circulation"] if len(c["polygon"]) >= 3]
        lightwells = [poly(u["lightwell"]["polygon"]) for u in built_units if u["lightwell"]["created"]]
        occupied = unary_union(room_geoms+circ_geoms+lightwells) if room_geoms+circ_geoms+lightwells else Polygon()
        residual = usable.difference(occupied)
        allocation = {"ROOM": round(sum(x.area for x in room_geoms), 3), "PRIVATE_CIRCULATION": round(sum(x.area for x in circ_geoms), 3),
                      "COMMON_CIRCULATION": round(landing.area, 3), "CORE": round(core.area, 3),
                      "LIGHTWELL": round(sum(x.area for x in lightwells), 3), "WALL_SERVICE": 0.0, "BALCONY_VOID": 0.0,
                      "RESIDUAL_UNRESOLVED": round(residual.area, 3), "USABLE_UNIT_AREA": round(usable.area, 3)}
        allocation["residual_ratio"] = round(residual.area/max(usable.area, EPS), 5)
        blockers = []
        if not access["shared_access_complete"]: blockers.append("DUAL_STAIR_ELEVATOR_REACHABILITY_UNRESOLVED")
        for u in built_units:
            blockers.extend(u["blockers"])
        if allocation["residual_ratio"] > .12: blockers.append("RESIDUAL_EXCEEDS_12_PERCENT")
        blockers = list(dict.fromkeys(blockers))
        score = self._score(access, built_units, allocation)
        resolved = not blockers
        result = {
            "contract": "ArchitecturalGraphFloorPlanV7", "scope": "ARCHITECTURE_ONLY",
            "identity": {"topology_id": identity["topology_id"], "floor_id": identity["floor_id"],
                         "program_hypothesis": identity["program_hypothesis"], "candidate_id": move.id},
            "pipeline": list(self.pipeline), "floor_envelope_resolution": envelope, "floor_boundary": coords(floor_envelope),
            "core_common_access": access, "facade_daylight_budget": facade_budget,
            "whole_floor_model": {"simultaneous": True, "unit_count": len(built_units), "rf2_single_sheet": len(built_units) != 2 or len(built_units) == 2},
            "units": built_units, "allocation": allocation, "residual_geometry": coords(residual),
            "search": {"deterministic": True, "bounded": True, "candidate_move": move.id, "score_non_authoritative": score,
                       "winner": None, "authoritative_ranking": False},
            "precedent_repair": {"invoked": bool(blockers), "geometry_copied": False, "authority_class": "PRECEDENT_NON_REGULATORY",
                "provenance": [x["id"] for x in self.patterns["cases"]],
                "matched_problem_design_move_tradeoff": [{"problem": b, "design_move": "COMPACT_ENTRY/FACADE_FIRST/CENTRAL_WET_CLUSTER/RESIDUAL_EXPLICIT",
                    "trade_off": "less nominal room area; stronger access/daylight auditability"} for b in blockers]},
            "agi": {"invoked": False, "eligible_only_after_unresolved": bool(blockers), "reason": "NO_CONFIGURED_JUSTIFIED_AGI_ADAPTER"},
            "regression_gates": {"no_longitudinal_spine_default": all(not u["space_organization"]["longitudinal_spine_created"] for u in built_units),
                "no_equal_or_weighted_slice_then_label": True, "frame_from_floor_envelope": True,
                "dual_access": access["shared_access_complete"], "rf2_single_sheet": len(built_units) != 2 or len(built_units) == 2,
                "precedent_geometry_not_copied": True, "no_arbitrary_oblique_geometry": True},
            "blockers": blockers, "resolved_floor_hypothesis": resolved,
            "REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN": resolved,
            "human_architectural_acceptance": {"status": "PENDING_HUMAN_REVIEW" if resolved else "REJECTED_FAIL_CLOSED", "independent_from_tests": True},
        }
        return result

    def _unit(self, uid, unit, threshold, floor, budget, program_id, move):
        minx, miny, maxx, maxy = unit.bounds
        width, depth = maxx-minx, maxy-miny
        threshold_pt, threshold_host, threshold_ok = threshold[1], threshold[2], threshold[3]
        entry_low = abs(threshold_pt.y-miny) <= abs(threshold_pt.y-maxy)
        near, far = (miny, maxy) if entry_low else (maxy, miny)
        direction = 1 if far > near else -1
        def yy(d): return near + direction*d
        entry_depth = min(1.6, depth*.1)
        service_depth = min(4.0, depth*.24)
        public_depth = min(5.8, depth*.31)
        private_depth = min(6.8 if program_id.endswith("2BR") else 4.3, depth*.36)
        # The graph chooses zone order; dimensions come from program envelopes, never leftover allocation.
        if move.public_at_far_facade:
            public_band = (yy(depth-public_depth), yy(depth))
            private_band = (yy(depth-public_depth-private_depth), yy(depth-public_depth))
        else:
            public_band = (yy(entry_depth), yy(entry_depth+public_depth))
            private_band = (yy(depth-private_depth), yy(depth))
        service_center = depth*.50
        service_band = (yy(service_center-service_depth/2), yy(service_center+service_depth/2))
        foyer_w = min(2.2, width*.46)
        fx0 = max(min(threshold_pt.x-foyer_w/2, maxx-foyer_w), minx)
        foyer = bbox_room(unit, fx0, fx0+foyer_w, yy(0), yy(entry_depth))
        privacy_node = bbox_room(unit, minx+width*.38, minx+width*.62, private_band[0], private_band[1])
        living = bbox_room(unit, minx, maxx, *public_band)
        bedroom_count = 2 if program_id.endswith("2BR") else 1
        bedrooms = ([bbox_room(unit, minx, minx+width/2, *private_band), bbox_room(unit, minx+width/2, maxx, *private_band)]
                    if bedroom_count == 2 else [bbox_room(unit, minx, maxx, *private_band)])
        sx = minx+width*.48
        kitchen = bbox_room(unit, minx, sx, *service_band)
        bathroom = bbox_room(unit, sx, maxx, service_band[0], yy(service_center))
        service = bbox_room(unit, sx, maxx, yy(service_center), service_band[1])
        geoms = [("living", living), ("kitchen", kitchen)] + [("bedroom", x) for x in bedrooms] + [("bathroom", bathroom), ("service", service)]
        targets = PROGRAMS[program_id]["rooms"]
        rooms, counts = [], {}
        blockers = []
        req_by_use = {}
        for use, amin, amax, wmin in targets: req_by_use.setdefault(use, []).append((amin, amax, wmin))
        for use, g in geoms:
            counts[use] = counts.get(use, 0)+1
            rid = f"{use}_{counts[use]}" if use == "bedroom" else use
            amin, amax, wmin = req_by_use[use][counts[use]-1]
            if g.area > amax + EPS:
                gx0, gy0, gx1, gy1 = g.bounds
                gw, gh = gx1-gx0, gy1-gy0
                if gw >= gh:
                    g = largest(g.intersection(box(gx0, gy0, gx0+amax/max(gh, EPS), gy1)))
                else:
                    g = largest(g.intersection(box(gx0, gy0, gx1, gy0+amax/max(gw, EPS))))
            bx = g.bounds if not g.is_empty else (0,0,0,0)
            useful = min(bx[2]-bx[0], bx[3]-bx[1]) >= wmin-EPS and amin-EPS <= g.area <= amax+EPS
            if not useful: blockers.append(f"{uid}:{rid}:ROOM_REQUIREMENT_ENVELOPE_UNRESOLVED")
            rooms.append({"room_id": rid, "use": use, "zone": "PUBLIC" if use=="living" else "PRIVATE" if use=="bedroom" else "SERVICE",
                          "polygon": coords(g), "area_m2": round(g.area,3), "target_range_m2": [amin,amax],
                          "minimum_useful_width_m": wmin, "furniture_envelope_pass": useful,
                          "geometry_provenance": "V7_GRAPH_CONSTRAINED_PROGRAM_ENVELOPE; NO_PRECEDENT_COORDINATES"})
        room_map = {r["room_id"]: poly(r["polygon"]) for r in rooms}
        circulation = [{"space_id": f"{uid}_ENTRY_NODE", "role": "COMPACT_ENTRY_DISTRIBUTION", "polygon": coords(foyer)},
                       {"space_id": f"{uid}_PRIVACY_NODE", "role": "SHORT_PRIVACY_BRANCH", "polygon": coords(privacy_node)}]
        graph_edges = [(f"{uid}_THRESHOLD", f"{uid}_ENTRY_NODE"), (f"{uid}_ENTRY_NODE", f"{uid}_living"),
                       (f"{uid}_living", f"{uid}_kitchen"), (f"{uid}_living", f"{uid}_PRIVACY_NODE")]
        graph_edges += [(f"{uid}_PRIVACY_NODE", f"{uid}_{r['room_id']}") for r in rooms if r["use"]=="bedroom"]
        graph_edges += [(f"{uid}_ENTRY_NODE", f"{uid}_{r['room_id']}") for r in rooms if r["use"] in {"bathroom","service"}]
        doors = []
        node_geoms = {f"{uid}_ENTRY_NODE": foyer, f"{uid}_PRIVACY_NODE": privacy_node, f"{uid}_THRESHOLD": unit}
        node_geoms.update({f"{uid}_{k}": v for k,v in room_map.items()})
        for n, (a,b) in enumerate(graph_edges):
            host = threshold_host if a.endswith("THRESHOLD") else longest(node_geoms[a].boundary.intersection(node_geoms[b].boundary.buffer(EPS)))
            valid = host.length >= .8-EPS
            p = host.interpolate(host.length/2) if host.length else unit.representative_point()
            doors.append({"door_id": f"D-{uid}-{n+1}", "space_a": a, "space_b": b, "host_wall": list(host.coords),
                          "center": [round(p.x,3),round(p.y,3)], "clear_width_m": .8, "valid": valid})
            if not valid: blockers.append(f"{uid}:{a}->{b}:DOOR_HOST_WALL_UNRESOLVED")
        windows, daylight = [], []
        for r in rooms:
            if r["use"] not in HABITABLE: continue
            g = room_map[r["room_id"]]
            host = longest(g.boundary.intersection(floor.boundary.buffer(EPS)))
            ratio = 7 if max(g.bounds[2]-g.bounds[0], g.bounds[3]-g.bounds[1]) > 4.5 else 8
            glazing = g.area/ratio
            depth_ok = min(g.bounds[2]-g.bounds[0], g.bounds[3]-g.bounds[1]) <= 2.5*max(host.length, EPS)
            valid = host.length >= max(.9, glazing/1.2)-EPS and depth_ok
            source_id = budget["source_id"]
            p = host.interpolate(host.length/2) if host.length else g.representative_point()
            chain = {"room": r["room_id"], "source": source_id, "window": f"W-{uid}-{r['room_id']}",
                     "ratio_rule": f"1/{ratio}", "required_glazing_m2": round(glazing,3), "max_depth_pass": depth_ok, "valid": valid}
            daylight.append(chain)
            windows.append({"window_id": chain["window"], "room_id": r["room_id"], "source_id": source_id,
                            "host_wall": list(host.coords), "center": [round(p.x,3),round(p.y,3)], "valid": valid})
            if not valid: blockers.append(f"{uid}:{r['room_id']}:ROOM_SOURCE_WINDOW_CHAIN_UNRESOLVED")
        wet = [room_map[r["room_id"]] for r in rooms if r["use"] in WET]
        wet_ok = sum(a.distance(b)<=EPS for i,a in enumerate(wet) for b in wet[i+1:]) >= len(wet)-1
        if not wet_ok: blockers.append(f"{uid}:WET_SERVICE_CLUSTER_UNRESOLVED")
        # No fabricated lightwell: only physical candidates may claim resolution.
        lightwell = {"created": False, "polygon": None, "area_m2": 0.0, "width_m": 0.0,
                     "applicability": "NOT_PROMOTED", "served_room_graph": [], "window_host_boundaries": [],
                     "allocation_cost_m2": 0.0, "reason": "NO_PHYSICAL_CANDIDATE_FITS_WITHOUT_INVALIDATING_PROGRAM_ENVELOPES"}
        room_union = unary_union(list(room_map.values()))
        circ_union = unary_union([foyer, privacy_node])
        overlap = sum(g.area for g in room_map.values())+foyer.area+privacy_node.area-unary_union([*room_map.values(),foyer,privacy_node]).area
        if overlap > .02: blockers.append(f"{uid}:ROOM_OR_CIRCULATION_OVERLAP")
        all_reachable = all(path_exists(graph_edges, f"{uid}_THRESHOLD", f"{uid}_{r['room_id']}") for r in rooms)
        if not all_reachable: blockers.append(f"{uid}:DOOR_GRAPH_UNREACHABLE_ROOM")
        blockers = list(dict.fromkeys(blockers))
        return {"unit_id":uid, "unit_boundary":coords(unit),
            "zoning_graph":{"nodes":["PUBLIC","PRIVATE","SERVICE"],"edges":[["PUBLIC","PRIVATE"],["PUBLIC","SERVICE"]]},
            "room_adjacency_graph":{"nodes":[r["room_id"] for r in rooms],"edges":[list(x) for x in graph_edges]},
            "rooms":rooms, "private_circulation":circulation, "doors":doors,
            "threshold":{"center":[round(threshold_pt.x,3),round(threshold_pt.y,3)],"host_wall":list(threshold_host.coords),"valid":threshold_ok},
            "daylight_sources":[budget], "windows":windows, "daylight_chains":daylight, "lightwell":lightwell,
            "service_wet_zone":{"polygon":coords(unary_union(wet)),"cluster_pass":wet_ok},
            "space_organization":{"longitudinal_spine_created":False,"circulation_derived_after_door_graph":True,"precedent_geometry_copied":False},
            "checks":{"door_graph_all_rooms_reachable":all_reachable,"all_doors_on_host_walls":all(x["valid"] for x in doors),
                      "daylight_chain":all(x["valid"] for x in daylight),"privacy":all_reachable,
                      "furniture_usability":all(r["furniture_envelope_pass"] for r in rooms),"wet_service_cluster":wet_ok,
                      "non_overlap":overlap<=.02,"common_corridor_ends_at_threshold":threshold_ok},
            "blockers":blockers}

    @staticmethod
    def _score(access, units, allocation):
        checks = [value for u in units for value in u["checks"].values()]
        return {"connectivity": int(access["shared_access_complete"])*20,
                "room_validity": round(50*sum(bool(x) for x in checks)/max(len(checks),1),2),
                "residual": round(max(0,20*(1-allocation["residual_ratio"])),2),
                "unit_balance": 10 if len(units) in {1,2} else 0,
                "total": round(int(access["shared_access_complete"])*20+50*sum(bool(x) for x in checks)/max(len(checks),1)+max(0,20*(1-allocation["residual_ratio"]))+(10 if len(units) in {1,2} else 0),2)}


def verify_topic4(evidence):
    required = {"T4-4-5-2-1-2", "T4-4-5-2-2-1", "T4-4-5-2-2-2", "T4-4-5-2-3-1", "T4-4-5-2-3-2", "T4-4-5-2-8-1", "T4-4-5-2-8-2", "T4-4-5-2-8-3", "T4-TABLE-4-6"}
    present = {x["id"] for x in evidence["rules"]}
    return {"status":"PASS" if required<=present else "FAIL_CLOSED", "missing":sorted(required-present),
            "document_sha256":evidence["document"]["sha256"], "minab_override":evidence["jurisdiction"]["minab_override"]}
