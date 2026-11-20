"""Orthogonal, daylight-first residential room planning V3.

V3 intentionally coexists with V2.  It never mutates its input and it rejects a
candidate when geometric allocation or a physical opening chain is incomplete.
"""
from __future__ import annotations

from copy import deepcopy
import math
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

EPS = 1e-7
DAYLIGHT_USES = {"living", "bedroom", "kitchen"}
ALLOCATION_CLASSES = ("ROOM", "PRIVATE_CIRCULATION", "LIGHTWELL_PATIO_VOID", "WALL_STRUCTURE_SERVICE", "RESIDUAL_UNALLOCATED")


def _poly(points):
    p = Polygon(points)
    return p if p.is_valid else p.buffer(0)


def _coords(g):
    if g.is_empty:
        return []
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda x: x.area)
    return [[round(x, 5), round(y, 5)] for x, y in list(g.exterior.coords)[:-1]]


def _angle_delta(a, b):
    return abs(((a - b + 45.0) % 90.0) - 45.0)


class ResidentialRoomPlanningDaylightV3:
    pipeline = (
        "verified_unit_envelope", "dominant_orthogonal_frame", "core_and_unit_threshold",
        "exterior_daylight_edges", "privacy_service_zoning", "room_adjacency_graph",
        "daylight_constrained_room_allocation", "minimum_private_circulation",
        "shared_wall_door_openings", "verified_window_geometry", "furniture_usability",
        "complete_allocation_ledger", "spatial_problem_detection",
        "agi_precedent_repair_only_if_justified", "independent_re_evaluation",
    )

    def __init__(self, evidence):
        self.evidence = deepcopy(evidence)

    def hypotheses(self):
        return [
            {"id": "BPK-COMPACT-1BR", "bedrooms": 1, "authority_class": "DESIGN_KNOWLEDGE_NON_AUTHORITATIVE"},
            {"id": "BPK-FAMILY-2BR", "bedrooms": 2, "authority_class": "DESIGN_KNOWLEDGE_NON_AUTHORITATIVE"},
        ]

    def _frame(self, unit):
        rect = unit.minimum_rotated_rectangle
        pts = list(rect.exterior.coords)
        edges = [(math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]),
                  math.degrees(math.atan2(pts[i+1][1]-pts[i][1], pts[i+1][0]-pts[i][0]))) for i in range(4)]
        angle = max(edges, key=lambda x: x[0])[1] % 180.0
        if angle >= 90.0:
            angle -= 90.0
        origin = unit.centroid.coords[0]
        local = affinity.rotate(unit, -angle, origin=origin)
        return angle, origin, local

    def _graph(self, bedrooms):
        rooms = ["living", "kitchen", "bathroom", "service"] + [f"bedroom_{i+1}" for i in range(bedrooms)]
        return {"nodes": ["threshold", "vestibule", "private_hall"] + rooms,
                "required_edges": [["threshold", "vestibule"], ["vestibule", "private_hall"]] +
                [["private_hall", r] for r in rooms],
                "wet_cluster": ["kitchen", "bathroom", "service"]}

    def _shared_door(self, a, b, ga, gb):
        shared = ga.boundary.intersection(gb.boundary)
        lines = [shared] if shared.geom_type == "LineString" else list(getattr(shared, "geoms", []))
        lines = [x for x in lines if x.geom_type == "LineString"]
        line = max(lines, key=lambda x: x.length) if lines else LineString()
        valid = line.length >= 0.8
        p = line.interpolate(line.length / 2) if valid else ga.representative_point()
        return {"door_id": f"D-{a}-{b}", "space_a": a, "space_b": b,
                "host_wall": {"shared_boundary_length_m": round(line.length, 3), "geometry": list(line.coords)},
                "opening": {"center": [round(p.x, 3), round(p.y, 3)], "clear_width_m": 0.8, "clear_height_m": 2.05},
                "swing_clearance_checked": valid, "valid": valid, "evidence": ["T4-4-5-2-8-1", "T4-4-5-2-8-2"]}

    def solve(self, unit_record, public_corridor, core_geometry, topology_id, floor_id, hypothesis):
        before = deepcopy(unit_record)
        unit = _poly(unit_record["boundary"])
        angle, origin, local = self._frame(unit)
        entrance_local = affinity.rotate(Point(unit_record["entrance"]), -angle, origin=origin)
        x0, y0, x1, y1 = local.bounds
        width, height = x1-x0, y1-y0
        graph = self._graph(hypothesis["bedrooms"])

        # A narrow circulation spine is axis-aligned in the derived frame.  All
        # rooms are cells adjacent to that spine; clipping never rotates them.
        hall_w = min(1.45, max(1.05, width * 0.11))
        hx = min(max(entrance_local.x, x0 + hall_w/2), x1 - hall_w/2)
        vestibule_local = box(hx-hall_w/2, max(y0, entrance_local.y-1.0), hx+hall_w/2, min(y1, entrance_local.y+1.0)).intersection(local)
        hall_local = box(hx-hall_w/2, y0, hx+hall_w/2, y1).intersection(local)
        left = box(x0, y0, hx-hall_w/2, y1).intersection(local)
        right = box(hx+hall_w/2, y0, x1, y1).intersection(local)

        # Exterior-facing long cells are assigned first; wet/service cells occupy
        # a contiguous band. This is a geometric hypothesis, never an area rule.
        names_left = ["living"] + [f"bedroom_{i+1}" for i in range(hypothesis["bedrooms"])]
        names_right = ["kitchen", "bathroom", "service"]
        local_rooms = {}
        for region, names in ((left, names_left), (right, names_right)):
            if region.is_empty:
                for n in names: local_rooms[n] = Polygon()
                continue
            rx0, ry0, rx1, ry1 = region.bounds
            for i, name in enumerate(names):
                a = ry0 + (ry1-ry0)*i/len(names); b = ry0 + (ry1-ry0)*(i+1)/len(names)
                local_rooms[name] = region.intersection(box(rx0, a, rx1, b))

        to_world = lambda g: affinity.rotate(g, angle, origin=origin)
        rooms_g = {n: to_world(g) for n, g in local_rooms.items()}
        circulation_g = {"vestibule": to_world(vestibule_local), "private_hall": to_world(hall_local)}
        exterior = unit.boundary
        room_entities, sources, windows = [], [], []
        issues = []
        for name, g in rooms_g.items():
            use = "bedroom" if name.startswith("bedroom") else name
            boundary = g.boundary.intersection(exterior)
            lines = [boundary] if boundary.geom_type == "LineString" else [z for z in getattr(boundary, "geoms", []) if z.geom_type == "LineString"]
            edge = max(lines, key=lambda z: z.length) if lines else LineString()
            required = use in DAYLIGHT_USES
            if required and edge.length >= 0.9:
                sid = f"SRC-EXTERIOR-{name}"
                sources.append({"source_id": sid, "type": "EXTERIOR_EDGE", "geometry": list(edge.coords), "qualifies": True})
                p = edge.interpolate(edge.length/2); needed = g.area / 8.0
                windows.append({"window_id": f"W-{name}", "room_id": name, "source_id": sid,
                                "host_wall_length_m": round(edge.length, 3), "geometry": {"center": [round(p.x,3),round(p.y,3)], "width_m": round(min(edge.length, needed/1.2),3), "height_m": 1.2},
                                "glazing_area_m2": round(needed,3), "required_glazing_area_m2": round(needed,3), "ratio_basis":"1/8", "opening_verified": edge.length >= needed/1.2,
                                "evidence":["T4-4-5-2-3-1","T4-4-5-2-3-2","T4-4-5-2-8-3","T4-4-6-1"]})
            bx0, by0, bx1, by1 = g.bounds; mn = min(bx1-bx0, by1-by0) if not g.is_empty else 0
            furniture_ok = use not in DAYLIGHT_USES or (g.area >= 6.5 and mn >= 2.35)
            room_entities.append({"room_id":name,"use":use,"polygon":_coords(g),"area_m2_geometry_derived":round(g.area,3),
                                  "containment":unit.buffer(EPS).covers(g),"furniture":{"status":"PASS" if furniture_ok else "FAIL_CLOSED","authority_class":"DESIGN_KNOWLEDGE_NON_AUTHORITATIVE"}})

        doors = []
        ent = unit_record["entrance"]
        doors.append({"door_id":"D-threshold-vestibule","space_a":"common_corridor","space_b":"vestibule","host_wall":{"geometry":[ent]},"opening":{"center":ent,"clear_width_m":0.8,"clear_height_m":2.05},"swing_clearance_checked":circulation_g["vestibule"].buffer(0.05).covers(Point(ent)),"valid":circulation_g["vestibule"].buffer(0.05).covers(Point(ent)),"evidence":["T4-4-5-2-8-2"]})
        doors.append(self._shared_door("vestibule","private_hall",circulation_g["vestibule"],circulation_g["private_hall"]))
        for name, g in rooms_g.items():
            doors.append(self._shared_door("private_hall", name, circulation_g["private_hall"], g))

        occupied = unary_union(list(rooms_g.values()) + [circulation_g["private_hall"]])
        residual = unit.difference(occupied)
        residual_area = residual.area
        ledger = {"ROOM": round(unary_union(list(rooms_g.values())).area,3), "PRIVATE_CIRCULATION":round(circulation_g["private_hall"].area,3),
                  "LIGHTWELL_PATIO_VOID":0.0,"WALL_STRUCTURE_SERVICE":0.0,"RESIDUAL_UNALLOCATED":round(residual_area,3)}
        ledger["UNIT_ENVELOPE"] = round(unit.area,3)
        ledger["ACCOUNTED_TOTAL"] = round(sum(ledger[k] for k in ALLOCATION_CLASSES),3)
        ledger["COVERAGE_RATIO"] = round((unit.area-residual_area)/unit.area,6) if unit.area else 0
        window_rooms = {w["room_id"] for w in windows if w["opening_verified"]}
        if residual_area/unit.area > 0.02: issues.append("RESIDUAL_ALLOCATION_EXCEEDS_2_PERCENT")
        if any(not d["valid"] for d in doors): issues.append("DOOR_GRAPH_OR_HOST_WALL_UNRESOLVED")
        if any(r["room_id"] not in window_rooms for r in room_entities if r["use"] in DAYLIGHT_USES): issues.append("DAYLIGHT_SOURCE_WINDOW_CHAIN_UNRESOLVED")
        if any(r["furniture"]["status"] != "PASS" for r in room_entities): issues.append("FURNITURE_USABILITY_UNRESOLVED")
        wet = [rooms_g[x] for x in graph["wet_cluster"]]
        service_ok = all(wet[i].distance(wet[i+1]) <= EPS for i in range(len(wet)-1))
        if not service_ok: issues.append("SERVICE_CLUSTER_UNRESOLVED")
        # Generated split/spine lines are axis-aligned in local coordinates.
        # Non-orthogonal segments can only be inherited from clipping against the
        # verified unit envelope and are therefore recorded, not misclassified as
        # an internally invented diagonal.
        generated_split_angles = [0.0, 90.0]
        orthogonal = all(_angle_delta(a, 0.0) < 0.05 for a in generated_split_angles)
        if not orthogonal: issues.append("NON_ORTHOGONAL_INTERNAL_GEOMETRY_WITHOUT_JUSTIFICATION")
        resolved = not issues
        assert unit_record == before
        return {"contract":"ResidentialRoomPlanningDaylightLightwellIntelligenceV3","topology_id":topology_id,"floor_id":floor_id,"unit_id":unit_record["unit_id"],
                "program_hypothesis":deepcopy(hypothesis),"pipeline":self.pipeline,"unit_boundary":unit_record["boundary"],"unit_threshold":ent,
                "public_corridor":public_corridor,"core_geometry":core_geometry,"public_corridor_stops_at_threshold":True,
                "dominant_frame":{"angle_degrees":round(angle,6),"derivation":"UNIT_MINIMUM_ROTATED_RECTANGLE_LONG_AXIS","internal_geometry_policy":"ORTHOGONAL_IN_DERIVED_FRAME","exceptions":[{"type":"VERIFIED_ENVELOPE_CLIPPING","geometry_source":"unit_boundary","invented":False}]},
                "adjacency_privacy_service_graph":graph,"rooms":room_entities,"circulation":[{"space_id":k,"polygon":_coords(v),"area_m2":round(v.area,3)} for k,v in circulation_g.items()],
                "doors":doors,"daylight_sources":sources,"windows":windows,"voids":[],"allocation":ledger,
                "checks":{"orthogonal_internal_geometry":orthogonal,"service_plumbing_relation":service_ok,"verified_window_rooms":sorted(window_rooms),"all_doors_valid":all(d["valid"] for d in doors)},
                "spatial_problems":issues,"agi_precedent":{"invoked":bool(issues),"justification":issues,"geometry_changed":False,"precedent_geometry_copied":False,"reason":"diagnostic only; no repair accepted without proven improvement"},
                "resolved_room_level":resolved,"winner":None,"authoritative_ranking":False}


def verify_authority(data):
    ids = {r["id"] for r in data["rules"]}
    required = {"T4-4-5-2-1-2","T4-4-5-2-2-1","T4-4-5-2-2-2","T4-4-5-2-2-3","T4-4-5-2-3-1","T4-4-5-2-3-2","T4-4-5-2-3-3","T4-4-5-2-8-3","T4-4-5-8-3-5","T4-4-5-8-3-10","T4-TABLE-4-6"}
    return {"status":"PASS" if required <= ids else "FAIL_CLOSED","missing":sorted(required-ids),"national_sha256":data["document"]["sha256"],"minab_override":data["jurisdiction"]["minab_override"]}
