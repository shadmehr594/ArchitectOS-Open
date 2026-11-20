import json
import math
from pathlib import Path


class DXFPhysicalWallAssemblyContinuityResolverV1:
    """Read-only propagation of proven face pairs into wall assemblies."""

    VERSION = "1.0"
    TOLERANCE = 1e-4
    THICKNESS_RATIO_TOLERANCE = 0.08

    def resolve(self, face_contract, output_path=None):
        if face_contract.get("canonical_view_id") != "VIEW-001":
            return self._pending("canonical_VIEW_001_face_contract_required")
        walls = face_contract.get("physical_wall_candidates", [])
        pairs = {item["id"]: item for item in face_contract.get("wall_face_pair_candidates", [])}
        junctions = self._junctions(walls, pairs)
        assemblies = self._assemblies(walls, pairs, junctions)
        wall_by_void = {
            void_id: wall["id"]
            for wall in walls for void_id in wall.get("openings", [])
        }
        assembly_by_wall = {
            wall_id: assembly["id"]
            for assembly in assemblies for wall_id in assembly["wall_candidate_ids"]
        }
        voids = face_contract.get("opening_void_candidates", [])
        openings = self._openings(voids, wall_by_void, assembly_by_wall, assemblies)
        doors = self._validate_blocks(
            face_contract.get("door_associations", []), openings, "door"
        )
        windows = self._validate_blocks(
            face_contract.get("window_associations", []), openings, "window"
        )
        enclosure = self._enclosures(assemblies)
        unresolved = self._unresolved(assemblies, doors, windows, enclosure)
        result = {
            "version": self.VERSION,
            "analysis_mode": "READ_ONLY_REFERENCE_EVIDENCE",
            "canonical_view_id": "VIEW-001",
            "junctions": junctions,
            "physical_wall_assembly_candidates": assemblies,
            "opening_on_wall_candidates": openings,
            "door_validation": doors,
            "window_validation": windows,
            "enclosure_reevaluation": enclosure,
            "entrance_evidence_status": "UNRESOLVED",
            "evidence_status": "AUTHORITATIVE_INPUT_WITH_INFERRED_ASSEMBLY_PROPAGATION",
            "unresolved_items": unresolved,
            "production_pipeline_consumable": False,
            "provenance": {
                "source_contract_version": face_contract.get("version"),
                "canonical_view_id": face_contract.get("canonical_view_id"),
                "source_handles": face_contract.get("provenance", {}).get("source_handles", []),
            },
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

    def _junctions(self, walls, pairs):
        from shapely.geometry import LineString

        result = []
        for index, first in enumerate(walls):
            first_line = LineString(first["centerline"])
            for second in walls[index + 1:]:
                second_line = LineString(second["centerline"])
                intersection = first_line.intersection(second_line)
                if intersection.geom_type != "Point":
                    continue
                point = [float(intersection.x), float(intersection.y)]
                first_end = self._endpoint(point, first["centerline"])
                second_end = self._endpoint(point, second["centerline"])
                directions = [self._direction(first["centerline"]), self._direction(second["centerline"])]
                parallel = abs(self._cross(*directions)) <= self.TOLERANCE
                kind = "COLLINEAR" if parallel else "L" if first_end and second_end else "T" if first_end or second_end else "X"
                compatible = self._compatible_thickness(first["thickness"], second["thickness"])
                first_pair, second_pair = pairs.get(first["id"], {}), pairs.get(second["id"], {})
                unambiguous = (
                    first.get("status") == second.get("status") == "resolved_candidate"
                    and first_pair.get("status") == second_pair.get("status") == "resolved_face_pair"
                )
                # Endpoint/intersection incidence is mandatory; distance is never used as propagation evidence.
                propagation = compatible and unambiguous and (kind in {"L", "T", "X"} or (kind == "COLLINEAR" and first_end and second_end))
                result.append({
                    "id": f"JUNCTION-{len(result)+1:03d}", "wall_a": first["id"], "wall_b": second["id"],
                    "point": point, "type": kind, "endpoint_on_a": first_end, "endpoint_on_b": second_end,
                    "thickness_compatible": compatible, "propagation_allowed": propagation,
                    "status": "resolved_continuity" if propagation else "pending",
                    "evidence": ["exact centerline intersection", "face-pair termination behavior",
                                 "extracted thickness compatibility"],
                })
        return result

    def _assemblies(self, walls, pairs, junctions):
        adjacency = {wall["id"]: set() for wall in walls}
        for junction in junctions:
            if junction["propagation_allowed"]:
                adjacency[junction["wall_a"]].add(junction["wall_b"])
                adjacency[junction["wall_b"]].add(junction["wall_a"])
        wall_map = {wall["id"]: wall for wall in walls}
        components, unseen = [], set(adjacency)
        while unseen:
            seed = min(unseen); unseen.remove(seed); stack = [seed]; members = []
            while stack:
                current = stack.pop(); members.append(current)
                for neighbor in adjacency[current]:
                    if neighbor in unseen:
                        unseen.remove(neighbor); stack.append(neighbor)
            components.append(sorted(members))
        result = []
        for index, members in enumerate(components, 1):
            member_walls = [wall_map[item] for item in members]
            member_junctions = [item for item in junctions if item["wall_a"] in members and item["wall_b"] in members]
            ambiguous = any(wall.get("status") != "resolved_candidate" or pairs.get(wall["id"], {}).get("status") != "resolved_face_pair" for wall in member_walls)
            result.append({
                "id": f"WALL-ASSEMBLY-{index:03d}",
                "wall_candidate_ids": members,
                "face_segments": sorted({face for wall in member_walls for face in wall.get("faces", [])}),
                "face_geometry": [
                    {"wall_candidate_id": wall["id"], "face_a": pairs.get(wall["id"], {}).get("face_a"),
                     "face_b": pairs.get(wall["id"], {}).get("face_b")}
                    for wall in member_walls
                ],
                "centerline_candidate": [wall["centerline"] for wall in member_walls],
                "thickness_candidates": sorted({round(float(wall["thickness"]), 9) for wall in member_walls}),
                "junctions": [item["id"] for item in member_junctions if item["propagation_allowed"]],
                "source_handles": sorted({handle for wall in member_walls for handle in wall.get("source_handles", [])}),
                "status": "pending_ambiguity" if ambiguous else "resolved_continuous_wall",
                "evidence": ["resolved face-pair membership"] + (["junction-driven face propagation"] if len(members) > 1 else ["standalone proven face pair"]),
            })
        return result

    def _openings(self, voids, wall_by_void, assembly_by_wall, assemblies):
        assembly_map = {item["id"]: item for item in assemblies}
        result = []
        for void in voids:
            wall_id = wall_by_void.get(void["id"])
            assembly_id = assembly_by_wall.get(wall_id)
            assembly = assembly_map.get(assembly_id)
            resolved = void.get("status") == "resolved_void_candidate" and assembly and assembly["status"] == "resolved_continuous_wall"
            result.append({
                "wall_assembly_id": assembly_id, "wall_candidate_id": wall_id,
                "void_id": void["id"], "width": void["width"], "orientation": void["orientation"],
                "void_polygon": void.get("void_polygon"),
                "source_handles": void.get("source_handles", []),
                "jamb_continuity_proven": void.get("status") == "resolved_void_candidate",
                "evidence": void.get("evidence", []) + (["preserved through resolved wall assembly"] if resolved else ["wall assembly remains ambiguous"]),
                "status": "resolved_candidate" if resolved else "pending",
            })
        return result

    @staticmethod
    def _validate_blocks(associations, openings, kind):
        opening_map = {item["void_id"]: item for item in openings}
        result = []
        for association in associations:
            object_id = association.get(f"{kind}_id")
            opening = opening_map.get(association.get("opening_void_id"))
            resolved = association.get("status") == "resolved" and opening and opening["status"] == "resolved_candidate"
            result.append({
                f"{kind}_id": object_id, "source_handle": association.get("source_handle"),
                "wall_assembly_id": opening.get("wall_assembly_id") if resolved else None,
                "opening_void_id": opening.get("void_id") if resolved else None,
                "status": "validated" if resolved else association.get("status", "UNRESOLVED"),
                "evidence": association.get("evidence", []) + (["opening preserved on continuous assembly"] if resolved else ["continuous unique wall assembly unavailable"]),
            })
        return result

    def _enclosures(self, assemblies):
        from shapely.geometry import LineString
        from shapely.ops import polygonize, unary_union

        resolved = [item for item in assemblies if item["status"] == "resolved_continuous_wall"]
        lines = [LineString(line) for assembly in resolved for line in assembly["centerline_candidate"]]
        polygons = list(polygonize(unary_union(lines))) if lines else []
        candidates = []
        for index, polygon in enumerate(polygons, 1):
            boundary = polygon.boundary
            participating = []
            covered = 0.0
            for assembly in resolved:
                for line in assembly["centerline_candidate"]:
                    overlap = boundary.intersection(LineString(line)).length
                    if overlap > self.TOLERANCE:
                        participating.append(assembly["id"]); covered += overlap
            score = min(1.0, covered / max(polygon.length, self.TOLERANCE))
            candidates.append({"id": f"ASSEMBLY-ENCLOSURE-{index:03d}",
                               "polygon": [[float(x), float(y)] for x, y in polygon.exterior.coords],
                               "wall_assembly_ids": sorted(set(participating)),
                               "continuity_score": score,
                               "evidence": ["closed wall-assembly centerline topology"]})
        return {"enclosure_candidates": candidates,
                "continuity_score": max((item["continuity_score"] for item in candidates), default=0.0),
                "status": "candidate_available" if candidates else "UNRESOLVED",
                "selected_enclosure_id": None,
                "selection_reason": "automatic enclosure selection forbidden"}

    @staticmethod
    def _unresolved(assemblies, doors, windows, enclosure):
        result = []
        if any(item["status"] != "resolved_continuous_wall" for item in assemblies): result.append("ambiguous_wall_assemblies")
        result += [f"{item['door_id']}:wall_assembly" for item in doors if item["status"] != "validated"]
        result += [f"{item['window_id']}:wall_assembly" for item in windows if item["status"] != "validated"]
        if enclosure["status"] != "candidate_available": result.append("building_enclosure")
        result += ["main_entrance", "exterior_interior_classification"]
        return result

    def _compatible_thickness(self, first, second):
        return abs(first - second) <= max(self.TOLERANCE, max(first, second) * self.THICKNESS_RATIO_TOLERANCE)

    def _endpoint(self, point, centerline):
        return self._distance(point, centerline[0]) <= self.TOLERANCE or self._distance(point, centerline[-1]) <= self.TOLERANCE

    @staticmethod
    def _direction(centerline):
        a, b = centerline[0], centerline[-1]
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        return [(b[0] - a[0]) / length, (b[1] - a[1]) / length] if length else [0.0, 0.0]

    @staticmethod
    def _cross(a, b): return a[0] * b[1] - a[1] * b[0]
    @staticmethod
    def _distance(a, b): return math.hypot(a[0] - b[0], a[1] - b[1])

    def _pending(self, reason):
        return {"version": self.VERSION, "analysis_mode": "READ_ONLY_REFERENCE_EVIDENCE",
                "canonical_view_id": None, "junctions": [], "physical_wall_assembly_candidates": [],
                "opening_on_wall_candidates": [], "door_validation": [], "window_validation": [],
                "enclosure_reevaluation": {"enclosure_candidates": [], "continuity_score": 0.0, "status": "UNRESOLVED"},
                "entrance_evidence_status": "UNRESOLVED", "evidence_status": "UNRESOLVED",
                "unresolved_items": [reason], "production_pipeline_consumable": False}
