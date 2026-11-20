import json
import math
from pathlib import Path


class DXFCanonicalWallTopologyOpeningResolverV1:
    """Read-only wall topology and block-to-opening evidence resolver."""

    VERSION = "1.0"
    PRECISION = 6
    COLLINEAR_TOLERANCE = 1e-4
    MATCH_TOLERANCE = 0.12
    MIN_GAP = 0.05
    MAX_GAP = 3.0
    SHORT_FRAGMENT = 0.30

    def resolve(self, file_path, canonical_reference_scope, architectural_evidence=None,
                correspondence_contract=None, output_path=None):
        import ezdxf
        from shapely.geometry import LineString
        from shapely.ops import polygonize, unary_union

        architectural_evidence = architectural_evidence or {}
        correspondence_contract = correspondence_contract or {}
        canonical_id, view = self._canonical_view(canonical_reference_scope, architectural_evidence)
        if canonical_id != "VIEW-001" or view is None:
            return self._pending(canonical_id, "canonical_VIEW_001_scope_unavailable")

        document = ezdxf.readfile(str(file_path))
        by_handle = {entity.dxf.handle: entity for entity in document.modelspace()}
        entities = [by_handle[h] for h in view.get("source_handles", []) if h in by_handle]
        raw = [self._raw_wall(entity, canonical_id) for entity in entities
               if entity.dxftype() == "LINE" and entity.dxf.layer == "A-WALL"]
        normalized, duplicates = self._normalize(raw)
        topology = self._topology(normalized, LineString, polygonize, unary_union)
        gaps = self._gaps(normalized)

        doors = [entity for entity in entities if entity.dxftype() == "INSERT" and entity.dxf.layer == "A-DOOR-FRAM"]
        windows = [entity for entity in entities if entity.dxftype() == "INSERT" and entity.dxf.layer == "A-GLAZ"]
        door_geometry = [self._world_geometry(entity, f"DOOR-{index:03d}") for index, entity in enumerate(doors, 1)]
        window_geometry = [self._world_geometry(entity, f"WINDOW-{index:03d}") for index, entity in enumerate(windows, 1)]
        door_associations = [self._associate(item, gaps, "door") for item in door_geometry]
        window_associations = [self._associate(item, gaps, "window") for item in window_geometry]
        door_hosts = [self._host_contract(item, gaps) for item in door_associations]
        window_hosts = [self._host_contract(item, gaps) for item in window_associations]
        contexts = [self._context(item, topology) for item in door_hosts]
        unmatched_source = correspondence_contract.get("unmatched_authoritative_geometry") or architectural_evidence.get("unmatched_wall_signature_analysis", [])
        unmatched = self._unmatched(unmatched_source, gaps)
        unresolved = self._unresolved(topology, door_hosts, window_hosts, contexts)

        contract = {
            "version": self.VERSION,
            "analysis_mode": "READ_ONLY_REFERENCE_EVIDENCE",
            "canonical_view_id": canonical_id,
            "source_file": str(file_path),
            "wall_graph": {
                "raw_segment_count": len(raw), "normalized_segment_count": len(normalized),
                "segments": normalized, "nodes": topology["nodes"],
                "source_handles": [item["source_handle"] for item in raw],
                "duplicate_groups": duplicates,
                "short_drafting_fragment_candidates": [item for item in normalized if item["fragment_status"] == "short_fragment_candidate"],
                "normalization_status": "resolved",
            },
            "wall_topology": topology,
            "enclosure_candidates": topology["enclosure_candidates"],
            "opening_candidates": gaps,
            "door_world_geometry": door_geometry,
            "window_world_geometry": window_geometry,
            "door_opening_associations": door_associations,
            "window_opening_associations": window_associations,
            "door_associations": door_hosts,
            "window_associations": window_hosts,
            "door_context": contexts,
            "unmatched_wall_analysis": unmatched,
            "evidence_status": "AUTHORITATIVE_DXF_WITH_UNRESOLVED_ASSOCIATIONS" if unresolved else "AUTHORITATIVE_DXF",
            "unresolved_items": unresolved,
            "production_pipeline_consumable": False,
            "provenance": {"view_id": canonical_id, "source_handles": view.get("source_handles", [])},
        }
        if output_path:
            self.write_contract(contract, output_path)
        return contract

    @staticmethod
    def write_contract(contract, output_path):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _canonical_view(self, scope, evidence):
        canonical_id = evidence.get("canonical_view_id")
        if canonical_id is None:
            canonical_id = scope.get("canonical_analysis_view_id") or scope.get("selected_view_id")
        views = {view.get("view_id"): view for view in scope.get("views", [])}
        return canonical_id, views.get(canonical_id)

    def _raw_wall(self, entity, view_id):
        start, end = self._point(entity.dxf.start), self._point(entity.dxf.end)
        vector = [end[0] - start[0], end[1] - start[1]]
        length = math.hypot(*vector)
        direction = [vector[0] / length, vector[1] / length] if length else [0.0, 0.0]
        return {"id": f"RAW-WALL-{entity.dxf.handle}", "source_handle": entity.dxf.handle,
                "source_handles": [entity.dxf.handle], "start": start, "end": end,
                "length": length, "direction": direction, "layer": entity.dxf.layer,
                "view_id": view_id}

    def _normalize(self, raw):
        grouped = {}
        duplicate_groups = []
        for item in raw:
            start, end = self._ordered(item["start"], item["end"])
            key = (self._round_point(start), self._round_point(end))
            if key in grouped:
                grouped[key]["source_handles"].append(item["source_handle"])
            else:
                grouped[key] = dict(item, start=start, end=end, source_handles=[item["source_handle"]])
        unique = list(grouped.values())
        for item in unique:
            if len(item["source_handles"]) > 1:
                duplicate_groups.append({"geometry": [item["start"], item["end"]], "source_handles": item["source_handles"]})

        line_groups = {}
        for item in unique:
            direction = self._canonical_direction(item["direction"])
            normal = [-direction[1], direction[0]]
            offset = round(item["start"][0] * normal[0] + item["start"][1] * normal[1], 5)
            angle = round(math.atan2(direction[1], direction[0]), 5)
            line_groups.setdefault((angle, offset), []).append(item)

        merged = []
        for items in line_groups.values():
            direction = self._canonical_direction(items[0]["direction"])
            origin = items[0]["start"]
            intervals = []
            for item in items:
                values = [self._projection(item["start"], origin, direction), self._projection(item["end"], origin, direction)]
                intervals.append([min(values), max(values), item])
            intervals.sort(key=lambda value: value[0])
            current = None
            for low, high, item in intervals:
                if current is None or low > current[1] + self.COLLINEAR_TOLERANCE:
                    if current is not None:
                        merged.append(self._merged_record(origin, direction, current))
                    current = [low, high, list(item["source_handles"]), item["layer"], item["view_id"]]
                else:
                    current[1] = max(current[1], high)
                    current[2].extend(item["source_handles"])
            if current is not None:
                merged.append(self._merged_record(origin, direction, current))
        merged.sort(key=lambda item: (item["start"], item["end"], item["source_handles"]))
        for index, item in enumerate(merged, 1):
            item["id"] = f"WALL-SEG-{index:03d}"
        return merged, duplicate_groups

    def _merged_record(self, origin, direction, interval):
        low, high, handles, layer, view_id = interval
        start = [origin[0] + direction[0] * low, origin[1] + direction[1] * low]
        end = [origin[0] + direction[0] * high, origin[1] + direction[1] * high]
        length = high - low
        return {"id": None, "source_handle": handles[0], "source_handles": sorted(set(handles)),
                "start": start, "end": end, "length": length, "direction": direction,
                "layer": layer, "view_id": view_id,
                "fragment_status": "short_fragment_candidate" if length < self.SHORT_FRAGMENT else "retained_wall_segment"}

    def _topology(self, segments, line_cls, polygonize, unary_union):
        lines = [line_cls([item["start"], item["end"]]) for item in segments]
        nodes_by_segment = {item["id"]: {self._round_point(item["start"]), self._round_point(item["end"])} for item in segments}
        for index, first in enumerate(lines):
            for j in range(index + 1, len(lines)):
                intersection = first.intersection(lines[j])
                points = []
                if intersection.geom_type == "Point": points = [intersection]
                elif intersection.geom_type == "MultiPoint": points = list(intersection.geoms)
                for point in points:
                    value = self._round_point([point.x, point.y])
                    nodes_by_segment[segments[index]["id"]].add(value)
                    nodes_by_segment[segments[j]["id"]].add(value)
        all_nodes = sorted(set().union(*nodes_by_segment.values())) if nodes_by_segment else []
        adjacency = {item["id"]: set() for item in segments}
        for i, first in enumerate(segments):
            for second in segments[i + 1:]:
                if nodes_by_segment[first["id"]] & nodes_by_segment[second["id"]]:
                    adjacency[first["id"]].add(second["id"]); adjacency[second["id"]].add(first["id"])
        components, unseen = [], set(adjacency)
        while unseen:
            seed, stack, members = min(unseen), [], []
            stack.append(seed); unseen.remove(seed)
            while stack:
                current = stack.pop(); members.append(current)
                for neighbor in adjacency[current]:
                    if neighbor in unseen: unseen.remove(neighbor); stack.append(neighbor)
            components.append({"component_id": f"COMP-{len(components)+1:03d}", "segment_ids": sorted(members)})
        union = unary_union(lines) if lines else None
        faces = list(polygonize(union)) if union is not None else []
        enclosures = [{"enclosure_id": f"ENC-{index:03d}", "polygon": self._polygon(poly),
                       "area": float(poly.area), "perimeter": float(poly.length),
                       "evidence_status": "AUTHORITATIVE_CLOSED_WALL_TOPOLOGY"}
                      for index, poly in enumerate(faces, 1)]
        disconnected = [item["id"] for item in segments if not adjacency[item["id"]]]
        return {"components": components, "loops": enclosures, "enclosure_candidates": enclosures,
                "disconnected_segments": disconnected, "nodes": [{"node_id": f"NODE-{i:04d}", "point": list(p)} for i, p in enumerate(all_nodes, 1)],
                "status": "resolved" if len(enclosures) == 1 else "pending_multiple_enclosures" if len(enclosures) > 1 else "unresolved_no_enclosure",
                "footprint_selected": False}

    def _gaps(self, segments):
        groups = {}
        for item in segments:
            direction = self._canonical_direction(item["direction"])
            normal = [-direction[1], direction[0]]
            key = (round(math.atan2(direction[1], direction[0]), 5),
                   round(item["start"][0] * normal[0] + item["start"][1] * normal[1], 5))
            origin = item["start"]
            values = [self._projection(item["start"], [0, 0], direction), self._projection(item["end"], [0, 0], direction)]
            groups.setdefault(key, []).append((min(values), max(values), item, direction))
        result = []
        for values in groups.values():
            values.sort(key=lambda value: value[0])
            for first, second in zip(values, values[1:]):
                gap = second[0] - first[1]
                if not self.MIN_GAP <= gap <= self.MAX_GAP: continue
                direction = first[3]
                left = [direction[0] * first[1], direction[1] * first[1]]
                # Restore offset by using the facing endpoint already on the source line.
                endpoint = min((first[2]["start"], first[2]["end"]), key=lambda p: abs(self._projection(p, [0, 0], direction) - first[1]))
                delta = [endpoint[0] - left[0], endpoint[1] - left[1]]
                start = endpoint
                end = [direction[0] * second[0] + delta[0], direction[1] * second[0] + delta[1]]
                result.append({"id": f"OPENING-GAP-{len(result)+1:03d}",
                               "host_segment_left": first[2]["id"], "host_segment_right": second[2]["id"],
                               "host_wall_handles": sorted(set(first[2]["source_handles"] + second[2]["source_handles"])),
                               "gap_start": start, "gap_end": end, "gap_center": self._midpoint(start, end),
                               "gap_width": gap, "orientation": direction,
                               "evidence": ["adjacent collinear non-overlapping wall segments", "bounded physical gap"]})
        return result

    def _world_geometry(self, insert, object_id):
        segments, entity_types = [], []
        for virtual in insert.virtual_entities():
            entity_types.append(virtual.dxftype())
            if virtual.dxftype() == "LINE":
                segments.append({"type": "LINE", "start": self._point(virtual.dxf.start), "end": self._point(virtual.dxf.end)})
            elif virtual.dxftype() == "LWPOLYLINE":
                points = [[float(x), float(y)] for x, y, *_ in virtual.get_points()]
                for a, b in zip(points, points[1:] + ([points[0]] if virtual.closed else [])):
                    segments.append({"type": "LWPOLYLINE_EDGE", "start": a, "end": b})
            elif virtual.dxftype() == "ARC":
                arc = virtual.dxf
                points = [[float(arc.center.x + arc.radius * math.cos(math.radians(angle))),
                           float(arc.center.y + arc.radius * math.sin(math.radians(angle)))]
                          for angle in (arc.start_angle, (arc.start_angle + arc.end_angle) / 2.0, arc.end_angle)]
                for a, b in zip(points, points[1:]): segments.append({"type": "ARC_CHORD", "start": a, "end": b})
        points = [point for segment in segments for point in (segment["start"], segment["end"])]
        if points:
            bbox = [[min(p[0] for p in points), min(p[1] for p in points)], [max(p[0] for p in points), max(p[1] for p in points)]]
            center = self._midpoint(bbox[0], bbox[1])
            lines = [segment for segment in segments if segment["type"] == "LINE"]
            dominant = max(lines, key=lambda s: self._distance(s["start"], s["end"])) if lines else None
            orientation = self._unit(dominant["start"], dominant["end"]) if dominant else None
            width = self._extent(points, center, orientation) if orientation else None
        else:
            bbox, center, orientation, width = None, None, None, None
        return {"door_id" if object_id.startswith("DOOR") else "window_id": object_id,
                "source_handle": insert.dxf.handle, "block_name": insert.dxf.name,
                "segments": segments, "polygon": None, "bbox": bbox, "center": center,
                "insertion_point": self._point(insert.dxf.insert), "rotation": float(insert.dxf.rotation),
                "scale": [float(insert.dxf.xscale), float(insert.dxf.yscale)],
                "opening_axis": orientation, "width_candidate": width,
                "evidence": ["block definition entities", "full INSERT translation/rotation/scale transform", "world-coordinate virtual entities"],
                "entity_types": sorted(set(entity_types))}

    def _associate(self, geometry, gaps, kind):
        object_id = geometry[f"{kind}_id"]
        candidates = []
        if geometry["center"] and geometry["opening_axis"]:
            for gap in gaps:
                parallel = abs(self._cross(geometry["opening_axis"], gap["orientation"])) <= 0.08
                perpendicular_distance = abs(self._cross(gap["orientation"], [geometry["center"][0] - gap["gap_center"][0], geometry["center"][1] - gap["gap_center"][1]]))
                center_projection = self._projection(geometry["center"], gap["gap_start"], gap["orientation"])
                inside = -self.MATCH_TOLERANCE <= center_projection <= gap["gap_width"] + self.MATCH_TOLERANCE
                compatible = geometry["width_candidate"] is not None and abs(geometry["width_candidate"] - gap["gap_width"]) <= max(0.18, gap["gap_width"] * 0.20)
                if parallel and perpendicular_distance <= self.MATCH_TOLERANCE and inside and compatible:
                    candidates.append(gap)
        status = "resolved" if len(candidates) == 1 else "pending_multiple_candidates" if len(candidates) > 1 else "unresolved"
        return {f"{kind}_id": object_id, "source_handle": geometry["source_handle"],
                "opening_gap_id": candidates[0]["id"] if len(candidates) == 1 else None,
                "candidate_gap_ids": [item["id"] for item in candidates], "status": status,
                "confidence": 1.0 if len(candidates) == 1 else 0.0,
                "evidence": ["world block geometry contained by gap", "compatible projected width", "parallel opening and wall axes"] if candidates else ["complete geometric match unavailable"]}

    @staticmethod
    def _host_contract(association, gaps):
        kind = "door" if "door_id" in association else "window"
        object_id = association[f"{kind}_id"]
        gap = next((item for item in gaps if item["id"] == association.get("opening_gap_id")), None)
        resolved = association["status"] == "resolved" and gap is not None
        return {f"{kind}_id": object_id, "source_handle": association["source_handle"],
                "host_wall_id": f"HOST-{gap['host_segment_left']}+{gap['host_segment_right']}" if resolved else None,
                "host_wall_handles": gap["host_wall_handles"] if resolved else [],
                "opening_id": gap["id"] if resolved else None,
                "host_status": "resolved" if resolved else association["status"],
                "evidence_used": ["resolved block-to-gap match", "two collinear source wall segments"] if resolved else association["evidence"]}

    @staticmethod
    def _context(host, topology):
        door_id = host["door_id"]
        if host["host_status"] != "resolved" or topology["status"] != "resolved":
            return {"door_id": door_id, "exterior_candidate": False, "interior_candidate": False,
                    "status": "pending", "evidence": ["final footprint unavailable"]}
        return {"door_id": door_id, "exterior_candidate": False, "interior_candidate": False,
                "status": "pending", "evidence": ["host resolved; open-side topology requires a separately proven footprint"]}

    def _unmatched(self, items, gaps):
        gap_points = [p for gap in gaps for p in (gap["gap_start"], gap["gap_end"])]
        result = []
        for item in items:
            signature = item.get("signature", "")
            numbers = self._signature_numbers(signature)
            classification = "unresolved"
            if item.get("view") != "a": classification = "detail_fragment_outside_canonical_view"
            elif len(numbers) >= 4:
                start, end = numbers[-4:-2], numbers[-2:]
                length = self._distance(start, end)
                if any(self._distance(point, start) <= self.COLLINEAR_TOLERANCE or self._distance(point, end) <= self.COLLINEAR_TOLERANCE for point in gap_points):
                    classification = "opening_jamb"
                elif length < self.SHORT_FRAGMENT: classification = "drafting_fragment"
                else: classification = "detail_fragment"
            result.append(dict(item, classification=classification,
                               evidence=["canonical signature geometry", "opening-gap endpoint incidence"],
                               evidence_status="AUTHORITATIVE" if classification == "opening_jamb" else "INFERRED"))
        return result

    @staticmethod
    def _unresolved(topology, doors, windows, contexts):
        result = []
        if topology["status"] != "resolved": result.append("building_footprint_not_selected")
        result += [f"{item['door_id']}:host" for item in doors if item["host_status"] != "resolved"]
        result += [f"{item['window_id']}:host" for item in windows if item["host_status"] != "resolved"]
        if any(item["status"] == "pending" for item in contexts): result.append("door_exterior_interior_classification")
        result += ["main_entrance", "platform", "stairs", "pedestrian_access"]
        return result

    def _pending(self, view_id, reason):
        return {"version": self.VERSION, "canonical_view_id": view_id, "analysis_mode": "READ_ONLY_REFERENCE_EVIDENCE",
                "wall_graph": {"segments": [], "nodes": [], "source_handles": [], "normalization_status": "unresolved"},
                "wall_topology": {"components": [], "loops": [], "enclosure_candidates": [], "disconnected_segments": [], "status": "unresolved"},
                "enclosure_candidates": [], "opening_candidates": [], "door_associations": [], "window_associations": [],
                "door_context": [], "unmatched_wall_analysis": [], "evidence_status": "UNRESOLVED",
                "unresolved_items": [reason], "production_pipeline_consumable": False}

    @staticmethod
    def _point(value): return [float(value.x), float(value.y)] if hasattr(value, "x") else [float(value[0]), float(value[1])]
    @staticmethod
    def _distance(a, b): return math.hypot(a[0] - b[0], a[1] - b[1])
    @staticmethod
    def _midpoint(a, b): return [(a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0]
    @staticmethod
    def _projection(point, origin, direction): return (point[0] - origin[0]) * direction[0] + (point[1] - origin[1]) * direction[1]
    @staticmethod
    def _cross(a, b): return a[0] * b[1] - a[1] * b[0]
    @staticmethod
    def _ordered(a, b): return (a, b) if tuple(a) <= tuple(b) else (b, a)
    def _round_point(self, point): return tuple(round(value, self.PRECISION) for value in point)
    @staticmethod
    def _canonical_direction(direction): return direction if direction[0] > 0 or (abs(direction[0]) < 1e-12 and direction[1] >= 0) else [-direction[0], -direction[1]]
    @staticmethod
    def _unit(a, b):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        return [(b[0] - a[0]) / length, (b[1] - a[1]) / length] if length else [0.0, 0.0]
    def _extent(self, points, origin, direction):
        values = [self._projection(point, origin, direction) for point in points]
        return max(values) - min(values)
    @staticmethod
    def _polygon(poly): return [[float(x), float(y)] for x, y in poly.exterior.coords]
    @staticmethod
    def _signature_numbers(signature):
        import re
        return [float(value) for value in re.findall(r"-?\d+\.\d+", signature)]
