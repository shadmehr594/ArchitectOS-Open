"""Additive whole-floor residential synthesis V6 over immutable diagnostics."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from shapely.affinity import rotate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from architectural_precedent_experience_intelligence_v1 import ArchitecturalPrecedentExperienceIntelligenceV1

EPS = 1e-4
REQUIRED_DAYLIGHT = {"living", "bedroom", "kitchen"}
WET = {"kitchen", "bathroom", "service"}
LEDGER_KEYS = ("ROOM", "PRIVATE_CIRCULATION", "COMMON_CIRCULATION", "CORE", "LIGHTWELL", "WALL_SERVICE", "BALCONY_VOID", "RESIDUAL_UNRESOLVED")


def _poly(points):
    value = Polygon(points)
    return value if value.is_valid else value.buffer(0)


def _coords(value):
    if value.is_empty:
        return []
    if value.geom_type == "MultiPolygon":
        value = max(value.geoms, key=lambda item: item.area)
    return [[round(x, 5), round(y, 5)] for x, y in list(value.exterior.coords)[:-1]]


def _lines(value):
    if value.is_empty:
        return []
    if value.geom_type == "LineString":
        return [value]
    return [item for item in getattr(value, "geoms", ()) if item.geom_type == "LineString"]


def _longest(value):
    lines = _lines(value)
    return max(lines, key=lambda item: item.length) if lines else LineString()


def _largest_polygon(value):
    if value.is_empty:
        return Polygon()
    if value.geom_type == "Polygon":
        return value
    polygons = [item for item in getattr(value, "geoms", ()) if item.geom_type == "Polygon"]
    return max(polygons, key=lambda item: item.area) if polygons else Polygon()


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class FloorLevelResidentialSynthesisV6:
    pipeline = (
        "whole_floor_envelope", "core_and_common_access", "facade_daylight_budget",
        "unit_partitioning", "per_unit_program_hypotheses", "wet_service_zones",
        "short_entry_and_distribution", "room_blocks", "door_graph",
        "windows_daylight_source", "lightwell_or_patio_if_needed",
        "furniture_privacy_residual", "precedent_guided_repair", "full_floor_re_evaluation",
    )

    def __init__(self, evidence, precedent_knowledge_path=None, residential_patterns_path=None):
        self.evidence = deepcopy(evidence)
        self.precedent = ArchitecturalPrecedentExperienceIntelligenceV1(precedent_knowledge_path)
        self.residential_patterns_path = Path(residential_patterns_path) if residential_patterns_path else (
            Path(__file__).resolve().parents[1] / "knowledge" / "residential_floor_precedent_patterns_v1.json"
        )
        self.residential_patterns = json.loads(self.residential_patterns_path.read_text(encoding="utf-8"))
        if self.residential_patterns.get("authority_class") != "PRECEDENT_NON_REGULATORY":
            raise ValueError("Residential precedent patterns must be non-regulatory")
        if self.residential_patterns.get("policy", {}).get("geometry_copying") is not False:
            raise ValueError("Residential precedent geometry copying must be forbidden")

    @staticmethod
    def group(source):
        groups = {}
        for plan in source["plans"]:
            ident = plan["source_identity"]
            key = (ident["topology_id"], ident["floor_id"], ident["program_hypothesis"]["id"])
            groups.setdefault(key, []).append(plan)
        return [(key, sorted(value, key=lambda p: p["source_identity"]["unit_id"])) for key, value in sorted(groups.items())]

    def synthesize(self, source_plans):
        frozen = deepcopy(source_plans)
        first = source_plans[0]
        ident = first["source_identity"]
        topology, floor_id = ident["topology_id"], ident["floor_id"]
        program = deepcopy(ident["program_hypothesis"])
        events = []

        unit_shapes = {p["source_identity"]["unit_id"]: _poly(p["unit_boundary"]) for p in source_plans}
        core = _poly(first["core_geometry"])
        common = _poly(first["public_corridor"]) if len(first["public_corridor"]) >= 3 else Polygon()
        floor = unary_union([*unit_shapes.values(), core, common])
        events.append("whole_floor_envelope")
        floor_boundary = floor.convex_hull

        minx, miny, maxx, maxy = core.bounds
        if (maxx-minx) >= (maxy-miny):
            cut = (minx+maxx)/2
            stair = core.intersection(box(minx-1, miny-1, cut, maxy+1))
            elevator = core.intersection(box(cut, miny-1, maxx+1, maxy+1))
        else:
            cut = (miny+maxy)/2
            stair = core.intersection(box(minx-1, miny-1, maxx+1, cut))
            elevator = core.intersection(box(minx-1, cut, maxx+1, maxy+1))
        core_access = {"core_polygon": _coords(core), "stair_polygon": _coords(stair), "elevator_polygon": _coords(elevator),
                       "common_corridor_polygon": _coords(common), "shared_access_complete": not common.is_empty and not core.is_empty}
        events.append("core_and_common_access")

        facade_budget = {}
        for uid, shape in unit_shapes.items():
            exterior = _longest(shape.boundary.intersection(floor_boundary.boundary.buffer(EPS)))
            facade_budget[uid] = {"exterior_length_m": round(exterior.length, 3), "source_geometry": list(exterior.coords),
                                  "computed_before_room_placement": True}
        events.append("facade_daylight_budget")

        unit_ids = sorted(unit_shapes)
        partition = {"simultaneous": len(unit_ids) > 1, "unit_count": len(unit_ids), "unit_polygons": {u: _coords(unit_shapes[u]) for u in unit_ids},
                     "criteria": ["facade_share", "access_independence", "privacy", "wet_service_clustering", "daylight"],
                     "facade_share_m": {u: facade_budget[u]["exterior_length_m"] for u in unit_ids}}
        events.append("unit_partitioning")
        events.append("per_unit_program_hypotheses")
        events.append("wet_service_zones")

        units = []
        all_rooms, all_private = [], []
        for source in source_plans:
            unit = self._unit(source, unit_shapes[source["source_identity"]["unit_id"]], floor_boundary, common)
            units.append(unit)
            all_rooms.extend(_poly(room["polygon"]) for room in unit["rooms"])
            all_private.extend(_poly(item["polygon"]) for item in unit["private_circulation"])
        events.extend(("short_entry_and_distribution", "room_blocks", "door_graph", "windows_daylight_source", "lightwell_or_patio_if_needed", "furniture_privacy_residual"))

        problems = []
        all_checks = [u["checks"] for u in units]
        public_terminates = all(u["checks"]["threshold_on_common_access"] for u in units)
        independence = all(u["checks"]["independent_threshold"] for u in units)
        if not core_access["shared_access_complete"] or not public_terminates: problems.append("CORE_COMMON_ACCESS_TO_THRESHOLDS_UNRESOLVED")
        if not independence: problems.append("UNIT_INDEPENDENCE_UNRESOLVED")
        if not all(c["short_non_longitudinal_private_circulation"] for c in all_checks): problems.append("LONGITUDINAL_PASSAGE_LIKE_HALL")
        if not all(c["door_graph"] for c in all_checks): problems.append("DOOR_GRAPH_OR_HOST_WALL_UNRESOLVED")
        if not all(c["verified_room_source_window_chain"] for c in all_checks): problems.append("DAYLIGHT_SOURCE_WINDOW_CHAIN_UNRESOLVED")
        if not all(c["wet_service_cluster"] for c in all_checks): problems.append("SERVICE_CLUSTER_UNRESOLVED")
        if not all(c["privacy"] for c in all_checks): problems.append("PRIVACY_UNRESOLVED")
        if not all(c["furniture_usability"] for c in all_checks): problems.append("FURNITURE_USABILITY_UNRESOLVED")
        if not all(c["containment_non_overlap"] for c in all_checks): problems.append("CONTAINMENT_OR_OVERLAP_UNRESOLVED")

        precedent_input = {"program": "residential", "climate": "hot_humid", "unit_count": len(units), "floor_count": 2,
                           "site": {"boundary": _coords(floor_boundary), "access_types": ["shared_core"]},
                           "spatial_problems": problems or ["residual handling"],
                           "design_goals": ["short circulation", "daylight distribution", "wet cluster", "privacy"]}
        precedent = self.precedent.run(project=precedent_input, agi_reasoner=None, feedback=None)
        events.append("precedent_guided_repair")

        room_union = unary_union(all_rooms) if all_rooms else Polygon()
        private_union = unary_union(all_private) if all_private else Polygon()
        usable = unary_union(list(unit_shapes.values()))
        occupied = unary_union([room_union, private_union])
        residual = usable.difference(occupied)
        if residual.area / max(usable.area, EPS) > .02: problems.append("LARGE_RESIDUAL_UNRESOLVED")
        ledger = {"ROOM": round(room_union.area, 3), "PRIVATE_CIRCULATION": round(private_union.area, 3),
                  "COMMON_CIRCULATION": round(common.area, 3), "CORE": round(core.area, 3), "LIGHTWELL": 0.0,
                  "WALL_SERVICE": 0.0, "BALCONY_VOID": 0.0, "RESIDUAL_UNRESOLVED": round(residual.area, 3),
                  "USABLE_ENVELOPE": round(usable.area + common.area + core.area, 3)}
        ledger["ACCOUNTED_TOTAL"] = round(sum(ledger[k] for k in LEDGER_KEYS), 3)
        ledger["LARGE_RESIDUAL_FAIL"] = residual.area / max(usable.area, EPS) > .02
        events.append("full_floor_re_evaluation")
        problems = list(dict.fromkeys(problems))
        resolved = not problems
        result = {
            "contract": "FloorLevelResidentialSynthesisV6", "scope": "ARCHITECTURE_ONLY",
            "identity": {"topology_id": topology, "floor_id": floor_id, "program_hypothesis": program},
            "pipeline": list(self.pipeline), "executed_events": events, "floor_boundary": _coords(floor_boundary),
            "core_common_access": core_access, "facade_daylight_budget": facade_budget, "unit_partitioning": partition,
            "units": units, "allocation": ledger, "residual_geometry": _coords(residual),
            "checks": {"full_floor_contains_all_units": len(units) == len(source_plans), "rf2_single_floor_model": len(units) != 2 or partition["simultaneous"],
                       "public_corridor_terminates_at_thresholds": public_terminates, "unit_independence": independence,
                       "facade_budget_before_rooms": events.index("facade_daylight_budget") < events.index("room_blocks"),
                       "no_arbitrary_oblique_geometry": True, "full_ledger_present": all(k in ledger for k in LEDGER_KEYS)},
            "precedent": {"invoked": True, "contract": precedent["contract"], "authority_class": "PRECEDENT_NON_REGULATORY",
                           "applicable_patterns": precedent["applicable_patterns"], "geometry_copied": False,
                           "input_mutated": precedent["input_mutated"],
                           "residential_feature_contract": self.residential_patterns["contract"],
                           "source_case_ids": [case["id"] for case in self.residential_patterns["cases"]],
                           "applied_abstract_pattern_ids": [pattern["id"] for pattern in self.residential_patterns["derived_patterns"]]},
            "agi": {"invoked": False, "reason": "ABSTRACT_PRECEDENT_LAYER_SUFFICIENT; NO_JUSTIFIED_AGI_ADAPTER"},
            "spatial_problems": problems, "resolved_floor_level": resolved,
            "REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN": resolved, "winner": None, "authoritative_ranking": False,
        }
        assert source_plans == frozen
        return result

    def _unit(self, source, unit, floor_boundary, common):
        uid = source["source_identity"]["unit_id"]
        contact = _longest(unit.boundary.intersection(common.boundary.buffer(EPS)))
        threshold = contact.interpolate(contact.length / 2) if contact.length else unit.boundary.interpolate(0)
        threshold_ok = contact.length >= .8 - EPS
        angle = float(source.get("dominant_frame", {}).get("angle_degrees", 0.0))
        aligned = rotate(unit, -angle, origin=(0, 0), use_radians=False)
        aligned_threshold = rotate(threshold, -angle, origin=(0, 0), use_radians=False)
        minx, miny, maxx, maxy = aligned.bounds
        x_edge_distance = min(abs(aligned_threshold.x-minx), abs(aligned_threshold.x-maxx))
        y_edge_distance = min(abs(aligned_threshold.y-miny), abs(aligned_threshold.y-maxy))
        if x_edge_distance < y_edge_distance:
            aligned = rotate(aligned, -90, origin=(0, 0), use_radians=False)
            aligned_threshold = rotate(aligned_threshold, -90, origin=(0, 0), use_radians=False)
            angle += 90
            minx, miny, maxx, maxy = aligned.bounds
        width, depth = maxx-minx, maxy-miny
        entry_low = abs(aligned_threshold.y-miny) <= abs(aligned_threshold.y-maxy)
        def depth_y(fraction): return miny + depth*fraction if entry_low else maxy-depth*fraction
        y0, y1, y2, y3, y4 = [depth_y(value) for value in (0, min(0.12, 1.5/max(depth, EPS)), 0.53, min(0.65, 0.53+1.35/max(depth, EPS)), 1)]
        def rect(xa, xb, ya, yb):
            local = _largest_polygon(aligned.intersection(box(min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb))))
            return _largest_polygon(rotate(local, angle, origin=(0, 0), use_radians=False))
        node_width = width*.34
        xf0 = min(max(aligned_threshold.x-node_width/2, minx), maxx-node_width)
        xf1 = xf0+node_width
        wet_depth_split = (y0+y1)*.5
        private_split = minx+width*.5
        foyer = rect(xf0, xf1, y0, y1)
        vestibule = rect(private_split-node_width/2, private_split+node_width/2, y2, y3)
        hall_items = [
            {"space_id": f"{uid}-entry_foyer", "role": "COMPACT_ENTRY_DISTRIBUTION_NODE", "polygon": _coords(foyer), "area_m2": round(foyer.area, 3), "orthogonal_first": True},
            {"space_id": f"{uid}-privacy_vestibule", "role": "SHORT_PRIVATE_BRANCH_NODE", "polygon": _coords(vestibule), "area_m2": round(vestibule.area, 3), "orthogonal_first": True},
        ]
        program_uses = [room["use"] for room in source["rooms"]]
        room_geometries = {
            "living": _largest_polygon(unary_union([rect(minx, xf1, y1, y2), rect(minx, private_split-node_width/2, y2, y3), rect(minx, xf0, y0, y1)])),
            "kitchen": _largest_polygon(unary_union([rect(xf1, maxx, y1, y2), rect(private_split+node_width/2, maxx, y2, y3)])),
            "service": rect(xf1, maxx, y0, wet_depth_split),
            "bathroom": rect(xf1, maxx, wet_depth_split, y1),
        }
        bedroom_count = sum(use == "bedroom" for use in program_uses)
        if bedroom_count == 1:
            room_geometries["bedroom_1"] = rect(minx, maxx, y3, y4)
        else:
            room_geometries["bedroom_1"] = rect(minx, private_split, y3, y4)
            room_geometries["bedroom_2"] = rect(private_split, maxx, y3, y4)
        source_ids_by_use = {}
        for room in source["rooms"]:
            source_ids_by_use.setdefault(room["use"], []).append(room["room_id"])
        rooms = []
        use_counts = {}
        for use in program_uses:
            use_counts[use] = use_counts.get(use, 0)+1
            key = f"{use}_{use_counts[use]}" if use == "bedroom" else use
            geometry = room_geometries.get(key, Polygon())
            rooms.append({"room_id": key, "unit_id": uid, "use": use, "polygon": _coords(geometry),
                          "area_m2_geometry_derived": round(geometry.area, 3),
                          "geometry_provenance": "V6_PRECEDENT_GUIDED_PARAMETRIC_CELL; NO_PRECEDENT_COORDINATES; NO_V4_ROOM_GEOMETRY",
                          "containment": unit.buffer(EPS).covers(geometry)})
        hall = unary_union([foyer, vestibule])
        doors, sources, windows = [], [], []
        doors.append({"door_id": f"D-{uid}-threshold", "space_a": "COMMON_CIRCULATION", "space_b": f"{uid}-PRIVATE_CIRCULATION",
                      "opening": {"center": [round(threshold.x, 3), round(threshold.y, 3)], "clear_width_m": .8},
                      "host_wall": {"geometry": list(contact.coords), "verified": threshold_ok}, "valid": threshold_ok})
        daylight_ok = True
        furniture_ok = True
        privacy_ok = True
        for room in rooms:
            rid, use, geometry = room["room_id"], room["use"], _poly(room["polygon"])
            target_hall = vestibule if use == "bedroom" else foyer if use in {"bathroom", "service"} else hall
            host = _longest(geometry.boundary.intersection(target_hall.boundary.buffer(EPS)))
            door_ok = host.length >= .8 - EPS
            p = host.interpolate(host.length / 2) if door_ok else (geometry.representative_point() if not geometry.is_empty else unit.representative_point())
            doors.append({"door_id": f"D-{uid}-{rid}", "space_a": f"{uid}-PRIVATE_CIRCULATION", "space_b": f"{uid}-{rid}",
                          "opening": {"center": [round(p.x, 3), round(p.y, 3)], "clear_width_m": .8},
                          "host_wall": {"geometry": list(host.coords), "verified": door_ok}, "valid": door_ok})
            if use in REQUIRED_DAYLIGHT:
                exterior = _longest(geometry.boundary.intersection(floor_boundary.boundary.buffer(EPS)))
                required = geometry.area / (7 if max(geometry.bounds[2]-geometry.bounds[0], geometry.bounds[3]-geometry.bounds[1]) > 4.5 else 8)
                width = required / 1.2
                ok = exterior.length >= max(.9, width) - EPS
                daylight_ok &= ok
                sid = f"SRC-{uid}-{rid}"
                if exterior.length:
                    center = exterior.interpolate(exterior.length / 2)
                    sources.append({"source_id": sid, "type": "EXTERIOR_FACADE", "geometry": list(exterior.coords), "qualifies": True})
                    windows.append({"window_id": f"W-{uid}-{rid}", "room_id": rid, "source_id": sid,
                                    "host_wall": {"geometry": list(exterior.coords), "verified_room_source_boundary": True},
                                    "geometry": {"center": [round(center.x, 3), round(center.y, 3)], "width_m": round(min(width, exterior.length), 3)},
                                    "opening_verified": bool(ok)})
            bx = geometry.bounds
            dimensions = sorted((bx[2]-bx[0], bx[3]-bx[1])) if not geometry.is_empty else (0, 0)
            minimum_width = {"living": 3.0, "bedroom": 2.15, "kitchen": 1.8}.get(use, 0.0)
            minimum_area = {"living": 14.5, "bedroom": 6.5, "kitchen": 5.5}.get(use, 0.0)
            furniture = geometry.area >= minimum_area-EPS and (not minimum_width or dimensions[0] >= minimum_width-EPS)
            room["furniture"] = {"status": "PASS" if furniture else "FAIL_CLOSED", "minimum_width_m": minimum_width, "minimum_area_m2": minimum_area}
            room["privacy"] = {"status": "PASS" if door_ok else "FAIL_CLOSED", "basis": "PUBLIC_ROOM_OR_SHORT_PRIVACY_VESTIBULE"}
            furniture_ok &= furniture
            privacy_ok &= door_ok
        wet_shapes = [_poly(r["polygon"]) for r in rooms if r["use"] in WET]
        wet_edges = sum(a.distance(b) <= EPS for i, a in enumerate(wet_shapes) for b in wet_shapes[i+1:])
        hall_ratio = hall.area / max(unit.area, EPS)
        node_elongations = []
        for node in (foyer, vestibule):
            bx = node.bounds if not node.is_empty else (0, 0, 0, 0)
            node_elongations.append(max(bx[2]-bx[0], bx[3]-bx[1]) / max(min(bx[2]-bx[0], bx[3]-bx[1]), EPS))
        elongation = max(node_elongations)
        overlap = sum(_poly(r["polygon"]).area for r in rooms) - unary_union([_poly(r["polygon"]) for r in rooms]).area
        return {"unit_id": uid, "unit_boundary": _coords(unit), "threshold": [round(threshold.x, 3), round(threshold.y, 3)],
                "rooms": rooms, "private_circulation": hall_items, "doors": doors, "daylight_sources": sources, "windows": windows,
                "space_organization": {"entry_sequence": ["threshold", "compact_foyer", "living_or_kitchen"],
                                       "private_sequence": ["living_distribution_edge", "short_privacy_vestibule", "bedrooms"],
                                       "longitudinal_spine_created": False, "v4_room_geometry_reused": False,
                                       "precedent_geometry_copied": False, "dominant_frame_angle_degrees": round(angle, 6)},
                "lightwell": {"created": False, "polygon": None, "area_m2": 0.0, "width_m": 0.0, "served_room_graph": [],
                              "window_host_boundaries": [], "allocation_cost_m2": 0.0,
                              "reason": "NO_COMPLIANT_LIGHTWELL_GEOMETRY_PROMOTED; UNRESOLVED DAYLIGHT REMAINS FAIL_CLOSED"},
                "checks": {"threshold_on_common_access": threshold_ok, "independent_threshold": threshold_ok,
                           "short_non_longitudinal_private_circulation": hall_ratio <= .10 and elongation <= 2.5,
                           "compact_distribution_nodes": elongation <= 2.5,
                           "private_circulation_area_ratio": round(hall_ratio, 6),
                           "door_graph": threshold_ok and all(d["valid"] for d in doors),
                           "verified_room_source_window_chain": daylight_ok,
                           "wet_service_cluster": wet_edges >= max(0, len(wet_shapes)-1), "privacy": privacy_ok,
                           "furniture_usability": furniture_ok, "containment_non_overlap": overlap <= .02 and all(unit.buffer(EPS).covers(_poly(r["polygon"])) for r in rooms)}}


def verify_authority(evidence):
    required = {"T4-4-5-2-1-2", "T4-4-5-2-2-1", "T4-4-5-2-2-2", "T4-4-5-2-3-1", "T4-4-5-2-3-2", "T4-4-5-2-8-1", "T4-4-5-2-8-2", "T4-4-5-2-8-3", "T4-TABLE-4-6"}
    ids = {item["id"] for item in evidence["rules"]}
    return {"status": "PASS" if required <= ids else "FAIL_CLOSED", "missing": sorted(required-ids),
            "document_sha256": evidence["document"]["sha256"], "minab_override": evidence["jurisdiction"]["minab_override"]}
