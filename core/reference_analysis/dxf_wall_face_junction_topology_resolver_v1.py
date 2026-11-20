import json
import math
from pathlib import Path


class DXFWallFaceJunctionTopologyResolverV1:
    """Read-only junction proof based on face endpoints, never centerlines alone."""

    VERSION = "1.0"
    TOLERANCE = 1e-4

    def resolve(self, continuity_contract_path, output_path=None):
        contract = json.loads(Path(continuity_contract_path).read_text(encoding="utf-8"))
        if contract.get("canonical_view_id") != "VIEW-001":
            return self._pending("canonical_VIEW_001_continuity_contract_required")
        assemblies = contract.get("physical_wall_assembly_candidates", [])
        junctions, rejected = self._junctions(assemblies)
        updated = self._update_assemblies(assemblies, junctions)
        openings = self._opening_reevaluation(contract.get("opening_on_wall_candidates", []), updated)
        doors = self._validate(contract.get("door_validation", []), openings, "door")
        windows = self._validate(contract.get("window_validation", []), openings, "window")
        enclosure = self._enclosure(updated)
        result = {
            "version": self.VERSION,
            "analysis_mode": "READ_ONLY_REFERENCE_EVIDENCE",
            "canonical_view_id": "VIEW-001",
            "face_endpoint_graph": self._endpoint_graph(assemblies),
            "junctions": junctions,
            "rejected_false_intersections": rejected,
            "physical_wall_assembly_candidates": updated,
            "opening_reevaluation": openings,
            "door_validation": doors,
            "window_validation": windows,
            "enclosure_test": enclosure,
            "entrance_evidence_status": "UNRESOLVED",
            "evidence_status": "AUTHORITATIVE_FACE_GEOMETRY_WITH_INFERRED_TOPOLOGY",
            "unresolved_items": self._unresolved(updated, doors, windows, enclosure),
            "production_pipeline_consumable": False,
            "provenance": {"source_contract": str(continuity_contract_path),
                           "source_contract_version": contract.get("version")},
        }
        if output_path:
            self.write_contract(result, output_path)
        return result

    @staticmethod
    def write_contract(contract, output_path):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _endpoint_graph(self, assemblies):
        nodes = {}
        edges = []
        for assembly in assemblies:
            for face in self._faces(assembly):
                start, end = self._face_endpoints(face)
                for point, termination in ((start, "start"), (end, "end")):
                    key = self._round(point)
                    nodes.setdefault(key, {"point": list(key), "terminations": []})["terminations"].append(
                        {"assembly_id": assembly["id"], "face_id": face.get("track_id"), "termination": termination}
                    )
                edges.append({"assembly_id": assembly["id"], "face_id": face.get("track_id"),
                              "start": start, "end": end,
                              "overlap_intervals": [[item["start"], item["end"]] for item in face.get("intervals", [])]})
        return {"nodes": [{"node_id": f"FACE-NODE-{index:04d}", **value}
                           for index, value in enumerate(nodes.values(), 1)],
                "face_edges": edges, "status": "resolved"}

    def _junctions(self, assemblies):
        from shapely.geometry import LineString

        accepted, rejected = [], []
        for index, first in enumerate(assemblies):
            for second in assemblies[index + 1:]:
                center_relation = self._center_relation(first, second, LineString)
                if center_relation is None:
                    continue
                contacts = self._face_contacts(first, second, LineString)
                kind = center_relation["type"]
                status, reason = self._classify(kind, contacts, center_relation, first, second)
                record = {"id": f"FACE-JUNCTION-{len(accepted)+len(rejected)+1:04d}",
                          "assembly_a": first["id"], "assembly_b": second["id"],
                          "point": center_relation["point"], "type": kind,
                          "face_continuities": contacts, "face_continuity_count": len(contacts),
                          "junction_status": status, "reason": reason,
                          "evidence": ["face endpoint/termination graph", "face-chain intersection",
                                       "centerline used only for candidate discovery"]}
                if status == "resolved": accepted.append(record)
                else:
                    record["rejection_status"] = "preserved_false_or_incomplete_intersection_evidence"
                    rejected.append(record)
        return accepted, rejected

    def _center_relation(self, first, second, line_cls):
        for a in first.get("centerline_candidate", []):
            for b in second.get("centerline_candidate", []):
                intersection = line_cls(a).intersection(line_cls(b))
                if intersection.geom_type == "LineString" and not intersection.is_empty:
                    return {"type": "COINCIDENT_PROJECTION", "point": list(intersection.centroid.coords)[0],
                            "a_endpoint": False, "b_endpoint": False}
                if intersection.geom_type != "Point": continue
                point = [float(intersection.x), float(intersection.y)]
                a_end, b_end = self._endpoint(point, a), self._endpoint(point, b)
                directions = self._direction(a), self._direction(b)
                parallel = abs(self._cross(directions[0], directions[1])) <= self.TOLERANCE
                kind = "COLLINEAR" if parallel else "L" if a_end and b_end else "T" if a_end or b_end else "X"
                return {"type": kind, "point": point, "a_endpoint": a_end, "b_endpoint": b_end}
        return None

    def _face_contacts(self, first, second, line_cls):
        result = []
        for a in self._faces(first):
            a_line = line_cls(self._face_endpoints(a))
            for b in self._faces(second):
                b_line = line_cls(self._face_endpoints(b))
                intersection = a_line.intersection(b_line)
                if intersection.geom_type != "Point": continue
                point = [float(intersection.x), float(intersection.y)]
                result.append({"face_a": a.get("track_id"), "face_b": b.get("track_id"),
                               "point": point, "endpoint_on_a": self._endpoint(point, list(a_line.coords)),
                               "endpoint_on_b": self._endpoint(point, list(b_line.coords))})
        return result

    def _classify(self, kind, contacts, relation, first, second):
        unambiguous = first.get("status") == second.get("status") == "resolved_continuous_wall"
        if not unambiguous:
            return "unresolved", "competing_or_unresolved_face_assembly"
        if kind == "L" and len([c for c in contacts if c["endpoint_on_a"] and c["endpoint_on_b"]]) >= 2:
            return "resolved", "two_face_chains_terminate_continuously_at_corner"
        if kind == "T":
            terminating = "a" if relation["a_endpoint"] else "b"
            key = f"endpoint_on_{terminating}"
            if len([c for c in contacts if c[key]]) >= 2:
                return "resolved", "two_terminating_faces_meet_continuous_host_faces"
        if kind == "X" and len(contacts) >= 4 and all(not c["endpoint_on_a"] and not c["endpoint_on_b"] for c in contacts):
            return "resolved", "four_face_continuities_proven"
        if kind == "COLLINEAR" and len([c for c in contacts if c["endpoint_on_a"] and c["endpoint_on_b"]]) >= 2:
            return "resolved", "two_collinear_face_chains_terminate_continuously"
        return "unresolved", "centerline_intersection_without_required_face_continuity"

    def _update_assemblies(self, assemblies, junctions):
        adjacency = {item["id"]: set() for item in assemblies}
        for junction in junctions:
            adjacency[junction["assembly_a"]].add(junction["assembly_b"])
            adjacency[junction["assembly_b"]].add(junction["assembly_a"])
        source = {item["id"]: item for item in assemblies}
        components, unseen = [], set(adjacency)
        while unseen:
            seed = min(unseen); unseen.remove(seed); stack = [seed]; members = []
            while stack:
                current = stack.pop(); members.append(current)
                for neighbor in adjacency[current]:
                    if neighbor in unseen: unseen.remove(neighbor); stack.append(neighbor)
            components.append(sorted(members))
        result = []
        for index, members in enumerate(components, 1):
            originals = [source[item] for item in members]
            linked = [junction for junction in junctions if junction["assembly_a"] in members and junction["assembly_b"] in members]
            ambiguous = any(item.get("status") != "resolved_continuous_wall" for item in originals)
            possible_contacts = max(1, 2 * max(1, len(members) - 1))
            score = min(1.0, sum(item["face_continuity_count"] for item in linked) / possible_contacts)
            result.append({"assembly_id": f"TOPOLOGY-ASSEMBLY-{index:03d}",
                           "source_assembly_ids": members,
                           "junctions": [item["id"] for item in linked],
                           "connected_faces": sorted({face for item in originals for face in item.get("face_segments", [])}),
                           "centerline_candidate": [line for item in originals for line in item.get("centerline_candidate", [])],
                           "face_geometry": [face for item in originals for face in item.get("face_geometry", [])],
                           "source_handles": sorted({h for item in originals for h in item.get("source_handles", [])}),
                           "continuity_score": score,
                           "status": "pending_ambiguity" if ambiguous else "resolved_topology",
                           "merge_status": "merged_by_proven_face_junction" if len(members) > 1 else "not_merged"})
        return result

    @staticmethod
    def _opening_reevaluation(openings, assemblies):
        assembly_by_source = {source_id: assembly for assembly in assemblies for source_id in assembly["source_assembly_ids"]}
        result = []
        for opening in openings:
            assembly = assembly_by_source.get(opening.get("wall_assembly_id"))
            valid = (opening.get("status") == "resolved_candidate"
                     and opening.get("jamb_continuity_proven") is True
                     and assembly and assembly["status"] == "resolved_topology")
            result.append(dict(opening,
                               topology_assembly_id=assembly["assembly_id"] if valid else None,
                               status="resolved" if valid else "pending",
                               topology_evidence=["unique host assembly", "same face chain", "preserved jamb continuity"] if valid else ["unique topology and jamb continuity not jointly proven"]))
        return result

    @staticmethod
    def _validate(items, openings, kind):
        opening_map = {item["void_id"]: item for item in openings}
        result = []
        for item in items:
            opening = opening_map.get(item.get("opening_void_id"))
            valid = item.get("status") == "validated" and opening and opening["status"] == "resolved"
            result.append({f"{kind}_id": item.get(f"{kind}_id"), "source_handle": item.get("source_handle"),
                           "topology_assembly_id": opening.get("topology_assembly_id") if valid else None,
                           "opening_void_id": opening.get("void_id") if valid else None,
                           "status": "validated" if valid else item.get("status", "UNRESOLVED"),
                           "evidence": item.get("evidence", []) + (["face-junction topology validated"] if valid else ["face-junction topology remains incomplete"])})
        return result

    def _enclosure(self, assemblies):
        from shapely.geometry import LineString
        from shapely.ops import polygonize, unary_union

        lines = [(assembly, line) for assembly in assemblies if assembly["status"] == "resolved_topology"
                 for line in assembly["centerline_candidate"]]
        polygons = list(polygonize(unary_union([LineString(line) for _, line in lines]))) if lines else []
        candidates = []
        for index, polygon in enumerate(polygons, 1):
            boundary = polygon.boundary; handles, segments, covered = set(), [], 0.0
            for assembly, line in lines:
                overlap = boundary.intersection(LineString(line)).length
                if overlap > self.TOLERANCE:
                    handles.update(assembly["source_handles"]); segments.append(line); covered += overlap
            candidates.append({"id": f"FACE-ENCLOSURE-{index:03d}",
                               "boundary_segments": segments,
                               "source_handles": sorted(handles),
                               "continuity_score": min(1.0, covered / max(polygon.length, self.TOLERANCE)),
                               "polygon": [[float(x), float(y)] for x, y in polygon.exterior.coords]})
        return {"enclosure_candidates": candidates,
                "boundary_segments": [segment for item in candidates for segment in item["boundary_segments"]],
                "continuity_score": max((item["continuity_score"] for item in candidates), default=0.0),
                "status": "candidate_available" if candidates else "UNRESOLVED",
                "selected_enclosure_id": None,
                "selection_reason": "area/first-candidate selection forbidden"}

    @staticmethod
    def _unresolved(assemblies, doors, windows, enclosure):
        result = []
        if any(item["status"] != "resolved_topology" for item in assemblies): result.append("ambiguous_wall_topology")
        result += [f"{item['door_id']}:opening_topology" for item in doors if item["status"] != "validated"]
        result += [f"{item['window_id']}:opening_topology" for item in windows if item["status"] != "validated"]
        if enclosure["status"] != "candidate_available": result.append("building_enclosure")
        result += ["main_entrance", "platform", "stairs"]
        return result

    @staticmethod
    def _faces(assembly):
        result = []
        for record in assembly.get("face_geometry", []):
            for key in ("face_a", "face_b"):
                if record.get(key): result.append(record[key])
        return result

    @staticmethod
    def _face_endpoints(face):
        direction, normal, offset, span = face["direction"], face["normal"], face["offset"], face["span"]
        return [[direction[0]*span[0]+normal[0]*offset, direction[1]*span[0]+normal[1]*offset],
                [direction[0]*span[1]+normal[0]*offset, direction[1]*span[1]+normal[1]*offset]]

    def _endpoint(self, point, line):
        return self._distance(point, line[0]) <= self.TOLERANCE or self._distance(point, line[-1]) <= self.TOLERANCE

    @staticmethod
    def _direction(line):
        a, b = line[0], line[-1]; length = math.hypot(b[0]-a[0], b[1]-a[1])
        return [(b[0]-a[0])/length, (b[1]-a[1])/length] if length else [0.0, 0.0]
    @staticmethod
    def _cross(a, b): return a[0]*b[1]-a[1]*b[0]
    @staticmethod
    def _distance(a, b): return math.hypot(a[0]-b[0], a[1]-b[1])
    def _round(self, point): return tuple(round(value, 6) for value in point)

    def _pending(self, reason):
        return {"version": self.VERSION, "analysis_mode": "READ_ONLY_REFERENCE_EVIDENCE",
                "canonical_view_id": None, "face_endpoint_graph": {"nodes": [], "face_edges": [], "status": "UNRESOLVED"},
                "junctions": [], "rejected_false_intersections": [], "physical_wall_assembly_candidates": [],
                "opening_reevaluation": [], "door_validation": [], "window_validation": [],
                "enclosure_test": {"enclosure_candidates": [], "boundary_segments": [], "continuity_score": 0.0, "status": "UNRESOLVED"},
                "entrance_evidence_status": "UNRESOLVED", "evidence_status": "UNRESOLVED",
                "unresolved_items": [reason], "production_pipeline_consumable": False}
