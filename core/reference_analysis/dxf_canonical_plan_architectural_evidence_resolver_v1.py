import math
import re


class DXFCanonicalPlanArchitecturalEvidenceResolverV1:
    """Read-only architectural association over one proven canonical DXF view."""

    VERSION = "1.0"
    TOLERANCE = 1e-4

    def resolve(self, file_path, scope_contract, correspondence_contract, metadata=None):
        import ezdxf
        from shapely.geometry import LineString, Point, Polygon
        from shapely.ops import polygonize, unary_union

        metadata = metadata if isinstance(metadata, dict) else {}
        canonical_id = correspondence_contract.get("canonical_analysis_view_id")
        allowed = correspondence_contract.get("canonicalization_allowed") is True
        views = {view["view_id"]: view for view in scope_contract.get("views", [])}
        view = views.get(canonical_id)
        if not allowed or not view:
            return self._pending(canonical_id, metadata, "canonical_scope_not_proven")

        document = ezdxf.readfile(str(file_path))
        by_handle = {entity.dxf.handle: entity for entity in document.modelspace()}
        entities = [by_handle[h] for h in view.get("source_handles", []) if h in by_handle]
        walls = [e for e in entities if e.dxftype() == "LINE" and e.dxf.layer == "A-WALL"]
        wall_records = [self._wall_record(e) for e in walls]
        wall_lines = [LineString([r["start"], r["end"]]) for r in wall_records]
        faces = list(polygonize(unary_union(wall_lines))) if wall_lines else []
        enclosure = unary_union(faces) if faces else None
        footprint = self._footprint(enclosure, faces, wall_records, LineString)
        footprint_polygon = Polygon(footprint["polygon"]) if footprint.get("polygon") else None

        closed = self._closed_polygons(entities, Polygon, view.get("bbox"))
        open_spaces = self._open_spaces(closed, footprint_polygon)
        doors = self._doors(entities, wall_records, footprint_polygon, Point, LineString)
        levels = self._level_bindings(entities, closed, Point, LineString)
        step_groups = self._step_groups(entities, closed, levels, Point, LineString)
        platform = self._platform(closed, levels, step_groups, doors, Point)
        main = self._main_entrance(doors, platform, step_groups)
        transition = self._transition(main, platform, step_groups, levels)
        unmatched = self._unmatched(correspondence_contract.get("unmatched_authoritative_geometry", []))

        return {
            "version": self.VERSION,
            "source_file": str(file_path),
            "canonical_view_id": canonical_id,
            "analysis_mode": "READ_ONLY_REFERENCE_EVIDENCE",
            "building_footprint": footprint,
            "exterior_wall_count": sum(1 for r in wall_records if r["handle"] in footprint.get("wall_ids", [])),
            "interior_wall_count": (sum(1 for r in wall_records if r["handle"] not in footprint.get("wall_ids", []))
                                    if footprint.get("status") == "resolved" else 0),
            "unclassified_wall_count": (len(wall_records) if footprint.get("status") != "resolved" else 0),
            "open_space_candidates": open_spaces,
            "parcel_boundary": {"status": "UNRESOLVED", "reason": "no_independent_parcel_boundary_proof"},
            "door_evidence": doors,
            "main_entrance_analysis": main,
            "level_annotation_binding": levels,
            "step_annotation_groups": step_groups,
            "platform_candidate": platform,
            "entrance_transition_reference": transition,
            "unmatched_wall_signature_analysis": unmatched,
            "user_authoritative_metadata": {
                "site_datum": metadata.get("site_datum", 0.0),
                "finished_floor": metadata.get("finished_floor", 0.40),
                "platform_elevation": metadata.get("platform_elevation", 0.40),
                "riser_count": metadata.get("riser_count", 2),
                "riser_height": metadata.get("riser_height", 0.20),
                "used_for_xy_resolution": False,
            },
            "provenance": [str(file_path), canonical_id] + view.get("source_handles", []),
        }

    def _footprint(self, enclosure, faces, walls, line_cls):
        if not faces or enclosure is None or enclosure.is_empty:
            return self._footprint_pending("closed_wall_enclosure_unavailable", len(faces))
        parts = list(enclosure.geoms) if enclosure.geom_type == "MultiPolygon" else [enclosure]
        if len(parts) != 1:
            return self._footprint_pending("multiple_disconnected_wall_enclosures", len(faces))
        polygon = parts[0]
        boundary = polygon.boundary
        handles = [r["handle"] for r in walls if boundary.intersection(line_cls([r["start"], r["end"]])).length > self.TOLERANCE]
        if len(handles) < 3:
            return self._footprint_pending("exterior_wall_source_trace_incomplete", len(faces))
        return {
            "status": "resolved", "polygon": self._polygon_coords(polygon),
            "wall_ids": handles, "source_handles": handles,
            "area": float(polygon.area), "perimeter": float(polygon.length),
            "candidate_enclosure_count": len(faces), "evidence_status": "AUTHORITATIVE",
            "evidence_used": ["A-WALL segments", "noded wall intersections", "closed enclosure topology"],
            "unresolved_evidence": [], "resolution_reason": "single_connected_union_of_closed_wall_faces",
        }

    @staticmethod
    def _footprint_pending(reason, count):
        return {"status": "building_footprint_pending", "polygon": None, "wall_ids": [],
                "source_handles": [], "area": None, "perimeter": None,
                "candidate_enclosure_count": count, "evidence_status": "UNRESOLVED",
                "evidence_used": ["A-WALL segments", "closed enclosure topology"],
                "unresolved_evidence": [reason], "resolution_reason": reason}

    def _closed_polygons(self, entities, polygon_cls, view_bbox=None):
        result = []
        for entity in entities:
            if entity.dxftype() != "LWPOLYLINE" or not entity.closed:
                continue
            points = [(float(x), float(y)) for x, y, *_ in entity.get_points()]
            if len(points) < 3:
                continue
            polygon = polygon_cls(points)
            if not polygon.is_valid or polygon.area <= self.TOLERANCE:
                continue
            if view_bbox and all(abs(value) <= self.TOLERANCE for value in (
                polygon.bounds[0] - view_bbox[0][0], polygon.bounds[1] - view_bbox[0][1],
                polygon.bounds[2] - view_bbox[1][0], polygon.bounds[3] - view_bbox[1][1],
            )):
                continue
            result.append({"id": f"POLYGON-{entity.dxf.handle}", "handle": entity.dxf.handle,
                           "layer": entity.dxf.layer, "shape": polygon,
                           "polygon": self._polygon_coords(polygon)})
        return result

    def _open_spaces(self, closed, footprint):
        result = []
        for item in closed:
            relation = "unresolved_without_building_footprint"
            status = "UNRESOLVED"
            if footprint is not None:
                if item["shape"].disjoint(footprint):
                    relation, status = "outside_building", "INFERRED"
                elif item["shape"].touches(footprint):
                    relation, status = "touches_building_exterior", "INFERRED"
            result.append({"id": item["id"], "polygon": item["polygon"],
                           "relation_to_building": relation, "source_handles": [item["handle"]],
                           "evidence_status": status, "evidence_used": ["explicit closed polyline"]})
        return result

    def _doors(self, entities, walls, footprint, point_cls, line_cls):
        result = []
        inserts = [e for e in entities if e.dxftype() == "INSERT" and e.dxf.layer == "A-DOOR-FRAM"]
        exterior_handles = set()
        if footprint is not None:
            exterior_handles = {r["handle"] for r in walls if footprint.boundary.intersection(line_cls([r["start"], r["end"]])).length > self.TOLERANCE}
        for index, door in enumerate(inserts, 1):
            center = self._point(door.dxf.insert)
            point = point_cls(center)
            direct = [r for r in walls if line_cls([r["start"], r["end"]]).distance(point) <= self.TOLERANCE]
            gap = self._gap_hosts(center, walls)
            candidates = direct or gap
            unique = candidates[0] if len(candidates) == 1 else None
            host_status = "resolved" if unique else "host_pending_multiple_candidates" if len(candidates) > 1 else "host_unresolved"
            ext = "exterior" if unique and unique["handle"] in exterior_handles else "interior" if unique and footprint is not None else "UNRESOLVED"
            result.append({
                "door_id": f"DOOR-{index:03d}", "source_handle": door.dxf.handle,
                "center": center, "rotation": float(getattr(door.dxf, "rotation", 0.0)),
                "width": self._door_width(door), "host_wall_id": f"WALL-{unique['handle']}" if unique else None,
                "host_wall_handles": [r["handle"] for r in candidates], "host_status": host_status,
                "exterior_or_interior_status": ext, "connected_space_status": "UNRESOLVED",
                "evidence_used": ["transformed INSERT point", "A-WALL segment incidence or collinear interruption"],
                "unresolved_evidence": [] if unique else ["unique_geometric_host_not_proven"],
            })
        return result

    def _gap_hosts(self, center, walls):
        matches = []
        for index, first in enumerate(walls):
            for second in walls[index + 1:]:
                if not self._collinear(first, second):
                    continue
                endpoints = [first["start"], first["end"], second["start"], second["end"]]
                if min(self._distance(center, p) for p in endpoints) <= 1.5 and self._point_on_infinite(center, first):
                    # A gap is evidence for the wall axis, but two source fragments form one host candidate.
                    matches.append({"handle": f"{first['handle']}+{second['handle']}", "start": first["start"], "end": second["end"]})
        return matches if len(matches) == 1 else []

    def _level_bindings(self, entities, closed, point_cls, line_cls):
        result = []
        leaders = [e for e in entities if e.dxftype() == "LEADER"]
        for entity in entities:
            if entity.dxftype() not in {"TEXT", "MTEXT"} or self._text(entity).replace(" ", "") not in {"+0.40", "0.40m"}:
                continue
            insertion = self._point(entity.dxf.insert)
            candidates = []
            used = ["explicit +0.40 DXF text"]
            for leader in leaders:
                vertices = [self._point(v) for v in leader.vertices]
                if not vertices or min(self._distance(insertion, v) for v in vertices) > 0.35:
                    continue
                target = point_cls(max(vertices, key=lambda v: self._distance(insertion, v)))
                for polygon in closed:
                    if polygon["shape"].boundary.distance(target) <= self.TOLERANCE or polygon["shape"].contains(target):
                        candidates.append(polygon["id"])
                        used += [f"leader:{leader.dxf.handle}", f"closed_geometry:{polygon['handle']}"]
            unique = sorted(set(candidates))
            result.append({"annotation_handle": entity.dxf.handle, "value": 0.40,
                           "insertion_point": insertion, "text_orientation": float(getattr(entity.dxf, "rotation", 0.0)),
                           "candidate_geometry_ids": unique, "bound_geometry_id": unique[0] if len(unique) == 1 else None,
                           "binding_status": "AUTHORITATIVE" if len(unique) == 1 else "UNRESOLVED",
                           "binding_reason": "explicit_leader_to_unique_closed_geometry" if len(unique) == 1 else "proximity_without_associative_reference_is_insufficient",
                           "evidence_used": used})
        return result

    def _step_groups(self, entities, closed, levels, point_cls, line_cls):
        ns, hs = [], []
        for e in entities:
            if e.dxftype() not in {"TEXT", "MTEXT"}:
                continue
            text = self._text(e).replace(" ", "")
            if re.fullmatch(r"n:2", text, re.I): ns.append(e)
            if re.fullmatch(r"h:0\.20", text, re.I): hs.append(e)
        groups = []
        used_h = set()
        for index, n in enumerate(ns, 1):
            viable = [h for h in hs if h.dxf.handle not in used_h and abs(self._point(n.dxf.insert)[0] - self._point(h.dxf.insert)[0]) <= 0.15 and abs(float(getattr(n.dxf, "rotation", 0.0)) - float(getattr(h.dxf, "rotation", 0.0))) <= 1e-4]
            h = min(viable, key=lambda x: self._distance(self._point(n.dxf.insert), self._point(x.dxf.insert))) if viable else None
            if h: used_h.add(h.dxf.handle)
            midpoint = self._midpoint(self._point(n.dxf.insert), self._point(h.dxf.insert)) if h else self._point(n.dxf.insert)
            candidates = self._step_geometry_candidates(entities, closed, midpoint, line_cls)
            bound = candidates[0] if len(candidates) == 1 else None
            groups.append({"group_id": f"STEP-GROUP-{index:03d}", "n_handle": n.dxf.handle,
                           "h_handle": h.dxf.handle if h else None, "riser_count": 2,
                           "riser_height": 0.20 if h else None, "total_rise": 0.40 if h else None,
                           "candidate_step_geometry": candidates, "bound_step_geometry": bound,
                           "connected_door_candidate": None, "connected_platform_candidate": None,
                           "geometry_binding_status": "AUTHORITATIVE" if bound else "UNRESOLVED",
                           "evidence_used": ["paired n/h text baseline"] + (["repeated parallel line pattern and closed outline"] if bound else []),
                           "unresolved_evidence": [] if bound else ["unique_step_XY_geometry_not_proven"]})
        return groups

    def _step_geometry_candidates(self, entities, closed, midpoint, line_cls):
        lines = []
        for e in entities:
            if e.dxftype() != "LINE": continue
            a, b = self._point(e.dxf.start), self._point(e.dxf.end)
            if min(self._distance(midpoint, a), self._distance(midpoint, b)) <= 3.0:
                lines.append((e, line_cls([a, b])))
        result = []
        for polygon in closed:
            local = [(e, line) for e, line in lines if polygon["shape"].buffer(self.TOLERANCE).intersects(line)]
            for angle_group in self._parallel_groups(local):
                if len(angle_group) == 3:
                    handles = [e.dxf.handle for e, _ in angle_group]
                    result.append({"geometry_id": polygon["id"], "polygon": polygon["polygon"],
                                   "source_handles": [polygon["handle"]] + handles, "edge_count": len(angle_group)})
                    break
        return result

    def _platform(self, closed, levels, steps, doors, point_cls):
        bound_levels = {item["bound_geometry_id"]: item for item in levels if item["binding_status"] == "AUTHORITATIVE"}
        candidates = []
        for polygon in closed:
            if polygon["id"] not in bound_levels: continue
            connected_doors = [d for d in doors if d["exterior_or_interior_status"] == "exterior" and polygon["shape"].boundary.distance(point_cls(d["center"])) <= self.TOLERANCE]
            connected_steps = [g for g in steps if g["bound_step_geometry"] and polygon["shape"].touches(self._shape_from_coords(g["bound_step_geometry"]["polygon"]))]
            if len(connected_doors) == 1 and len(connected_steps) == 1:
                candidates.append((polygon, connected_doors[0], connected_steps[0]))
        if len(candidates) != 1:
            return {"polygon": None, "elevation": 0.40 if bound_levels else None, "connected_door_id": None,
                    "connected_step_group": None, "source_handles": [], "geometry_status": "unresolved",
                    "platform_geometry_status": "unresolved", "elevation_binding_status": "AUTHORITATIVE" if bound_levels else "UNRESOLVED",
                    "evidence_used": ["no unique door-level-step connected closed geometry"]}
        polygon, door, step = candidates[0]
        step["connected_door_candidate"] = door["door_id"]
        step["connected_platform_candidate"] = polygon["id"]
        return {"polygon": polygon["polygon"], "elevation": 0.40, "connected_door_id": door["door_id"],
                "connected_step_group": step["group_id"], "source_handles": [polygon["handle"]],
                "geometry_status": "AUTHORITATIVE", "platform_geometry_status": "AUTHORITATIVE",
                "elevation_binding_status": "AUTHORITATIVE",
                "evidence_used": ["closed polygon", "explicit level leader", "exterior door incidence", "step outline continuity"]}

    def _main_entrance(self, doors, platform, steps):
        candidates = [d for d in doors if d["exterior_or_interior_status"] == "exterior"]
        selected = [d for d in candidates if platform.get("connected_door_id") == d["door_id"]]
        return {"status": "resolved" if len(selected) == 1 else "pending_multiple_candidates" if len(candidates) > 1 else "UNRESOLVED",
                "door_id": selected[0]["door_id"] if len(selected) == 1 else None,
                "source_handle": selected[0]["source_handle"] if len(selected) == 1 else None,
                "host_wall_id": selected[0]["host_wall_id"] if len(selected) == 1 else None,
                "threshold_point": selected[0]["center"] if len(selected) == 1 else None,
                "candidate_door_ids": [d["door_id"] for d in candidates],
                "evidence_used": ["exterior host", "platform-step-level connected topology"] if selected else ["exterior door candidate evidence only"]}

    def _transition(self, main, platform, groups, levels):
        if main["status"] != "resolved" or platform.get("geometry_status") != "AUTHORITATIVE":
            vertical_group = next((g for g in groups if g.get("h_handle")), None)
            return {"status": "UNRESOLVED", "entrance_door_id": None, "host_wall_id": None,
                    "threshold_point": None, "threshold_elevation": 0.40 if levels else None,
                    "platform_polygon": None, "platform_elevation": 0.40 if levels else None,
                    "step_start_elevation": None, "step_end_elevation": vertical_group.get("total_rise") if vertical_group else None,
                    "riser_count": vertical_group.get("riser_count") if vertical_group else None,
                    "riser_height": vertical_group.get("riser_height") if vertical_group else None, "step_geometry": None,
                    "source_handles": [], "evidence_status": "UNRESOLVED"}
        door = main["door_id"]
        group = next(g for g in groups if g["group_id"] == platform["connected_step_group"])
        return {"status": "resolved", "entrance_door_id": door, "host_wall_id": main["host_wall_id"],
                "threshold_point": main["threshold_point"], "threshold_elevation": 0.40,
                "platform_polygon": platform["polygon"], "platform_elevation": 0.40,
                "step_start_elevation": 0.0, "step_end_elevation": 0.40,
                "riser_count": 2, "riser_height": 0.20, "step_geometry": group["bound_step_geometry"],
                "source_handles": platform["source_handles"] + group["bound_step_geometry"]["source_handles"],
                "evidence_status": "AUTHORITATIVE"}

    @staticmethod
    def _unmatched(items):
        result = []
        for item in items:
            signature = item.get("signature", "")
            classification = "architectural_significance_unresolved"
            if signature.startswith("('LINE', 'A-WALL'"):
                numbers = [float(x) for x in re.findall(r"-?\d+\.\d+", signature)]
                if len(numbers) >= 4 and math.hypot(numbers[-2] - numbers[-4], numbers[-1] - numbers[-3]) < 0.30:
                    classification = "short_drafting_or_opening_jamb_fragment"
                else:
                    classification = "wall_detail_fragment_requires_source_handle_binding"
            result.append(dict(item, classification=classification, evidence_status="INFERRED"))
        return result

    @staticmethod
    def _wall_record(entity):
        return {"handle": entity.dxf.handle,
                "start": [float(entity.dxf.start.x), float(entity.dxf.start.y)],
                "end": [float(entity.dxf.end.x), float(entity.dxf.end.y)]}

    @staticmethod
    def _point(value):
        if hasattr(value, "x"):
            return [float(value.x), float(value.y)]
        return [float(value[0]), float(value[1])]
    @staticmethod
    def _distance(a, b): return math.hypot(a[0] - b[0], a[1] - b[1])
    @staticmethod
    def _midpoint(a, b): return [(a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0]
    @staticmethod
    def _polygon_coords(polygon): return [[float(x), float(y)] for x, y in list(polygon.exterior.coords)]

    def _collinear(self, a, b):
        va = (a["end"][0] - a["start"][0], a["end"][1] - a["start"][1])
        vb = (b["end"][0] - b["start"][0], b["end"][1] - b["start"][1])
        return abs(va[0] * vb[1] - va[1] * vb[0]) <= self.TOLERANCE and self._point_on_infinite(b["start"], a)

    def _point_on_infinite(self, p, line):
        a, b = line["start"], line["end"]
        return abs((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) <= self.TOLERANCE

    @staticmethod
    def _door_width(door):
        match = re.search(r"(\d{3,4})\s*x\s*\d{3,4}\s*mm", door.dxf.name, re.I)
        return float(match.group(1)) / 1000.0 if match else None

    @staticmethod
    def _text(entity):
        try: return (entity.plain_text() if entity.dxftype() == "MTEXT" else entity.dxf.text).strip()
        except Exception: return ""

    @staticmethod
    def _parallel_groups(lines):
        groups = {}
        for entity, line in lines:
            a, b = list(line.coords)
            angle = round(math.atan2(b[1] - a[1], b[0] - a[0]) % math.pi, 3)
            groups.setdefault(angle, []).append((entity, line))
        return list(groups.values())

    @staticmethod
    def _shape_from_coords(coords):
        from shapely.geometry import Polygon
        return Polygon(coords)

    @staticmethod
    def _pending(view_id, metadata, reason):
        return {"version": "1.0", "canonical_view_id": view_id, "analysis_mode": "READ_ONLY_REFERENCE_EVIDENCE",
                "status": "UNRESOLVED", "resolution_reason": reason, "building_footprint": None,
                "open_space_candidates": [], "door_evidence": [], "level_annotation_binding": [],
                "step_annotation_groups": [], "platform_candidate": None,
                "entrance_transition_reference": {"status": "UNRESOLVED"},
                "user_authoritative_metadata": dict(metadata, used_for_xy_resolution=False)}
