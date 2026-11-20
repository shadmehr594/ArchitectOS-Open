import json
import math
from pathlib import Path


class DXFCanonicalWallFaceOpeningJambPairResolverV1:
    """Read-only physical-wall face pairing and opening-void validation."""

    VERSION = "1.0"
    TOLERANCE = 1e-4
    PARALLEL_TOLERANCE = 0.02
    MIN_OVERLAP_RATIO = 0.75
    WIDTH_TOLERANCE = 0.20

    def resolve(self, wall_opening_contract, output_path=None):
        if wall_opening_contract.get("canonical_view_id") != "VIEW-001":
            return self._pending("canonical_VIEW_001_contract_required")
        segments = wall_opening_contract.get("wall_graph", {}).get("segments", [])
        tracks = self._face_tracks(segments)
        pairs = self._face_pairs(tracks, segments)
        thicknesses = [self._thickness(pair) for pair in pairs]
        voids = [void for pair in pairs for void in self._voids(pair)]
        door_associations = [self._associate(item, voids, "door") for item in wall_opening_contract.get("door_world_geometry", [])]
        window_associations = [self._associate(item, voids, "window") for item in wall_opening_contract.get("window_world_geometry", [])]
        physical_walls = self._physical_walls(pairs, voids)
        enclosure = self._enclosure(physical_walls)
        unresolved = self._unresolved(pairs, door_associations, window_associations, enclosure)
        result = {
            "version": self.VERSION,
            "analysis_mode": "READ_ONLY_REFERENCE_EVIDENCE",
            "canonical_view_id": "VIEW-001",
            "wall_face_pair_candidates": pairs,
            "wall_thickness_candidates": thicknesses,
            "physical_wall_candidates": physical_walls,
            "opening_void_candidates": voids,
            "opening_association_contract": {
                "doors": door_associations, "windows": window_associations,
            },
            "door_associations": door_associations,
            "window_associations": window_associations,
            "building_enclosure_status": enclosure,
            "main_entrance_status": "UNRESOLVED",
            "evidence_status": "AUTHORITATIVE_DXF_WITH_INFERRED_PAIRING",
            "unresolved_items": unresolved,
            "production_pipeline_consumable": False,
            "provenance": {
                "source_contract_version": wall_opening_contract.get("version"),
                "canonical_view_id": wall_opening_contract.get("canonical_view_id"),
                "source_handles": wall_opening_contract.get("wall_graph", {}).get("source_handles", []),
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

    def _face_tracks(self, segments):
        groups = {}
        for segment in segments:
            direction = self._canonical_direction(segment["direction"])
            normal = [-direction[1], direction[0]]
            offset = self._dot(segment["start"], normal)
            key = (round(math.atan2(direction[1], direction[0]), 5), round(offset, 5))
            values = sorted((self._dot(segment["start"], direction), self._dot(segment["end"], direction)))
            groups.setdefault(key, {"direction": direction, "normal": normal, "offset": offset, "members": []})["members"].append(
                {"start": values[0], "end": values[1], "segment_id": segment["id"],
                 "source_handles": segment["source_handles"]}
            )
        tracks = []
        for index, group in enumerate(groups.values(), 1):
            members = sorted(group["members"], key=lambda item: item["start"])
            tracks.append({"track_id": f"FACE-TRACK-{index:03d}", "direction": group["direction"],
                           "normal": group["normal"], "offset": group["offset"],
                           "span": [min(item["start"] for item in members), max(item["end"] for item in members)],
                           "intervals": members,
                           "source_handles": sorted({h for item in members for h in item["source_handles"]})})
        return tracks

    def _face_pairs(self, tracks, segments):
        result = []
        for index, first in enumerate(tracks):
            for second in tracks[index + 1:]:
                if abs(self._cross(first["direction"], second["direction"])) > self.PARALLEL_TOLERANCE:
                    continue
                overlap = max(0.0, min(first["span"][1], second["span"][1]) - max(first["span"][0], second["span"][0]))
                first_length = first["span"][1] - first["span"][0]
                second_length = second["span"][1] - second["span"][0]
                ratio = overlap / max(first_length, second_length, self.TOLERANCE)
                offset = abs(second["offset"] - first["offset"])
                if ratio < self.MIN_OVERLAP_RATIO or offset <= self.TOLERANCE or offset >= overlap:
                    continue
                synchronized = self._synchronized_gaps(first, second)
                caps = self._end_cap_handles(first, second, segments)
                if not synchronized and len(caps) < 2:
                    continue
                result.append({
                    "id": f"WALL-CAND-{len(result)+1:03d}",
                    "face_a": first, "face_b": second, "offset_distance": offset,
                    "direction": first["direction"], "length": overlap,
                    "overlap_ratio": ratio,
                    "source_handles": sorted(set(first["source_handles"] + second["source_handles"] + caps)),
                    "end_cap_handles": caps, "synchronized_gap_count": len(synchronized),
                    "synchronized_gaps": synchronized,
                    "confidence": 1.0 if synchronized and len(caps) >= 1 else 0.9 if synchronized or len(caps) >= 2 else 0.0,
                    "evidence": ["parallel face tracks", "directional consistency", "overlap ratio"]
                                + (["synchronized interruptions"] if synchronized else [])
                                + (["explicit end-cap continuity"] if len(caps) >= 2 else []),
                    "status": "candidate",
                })
        self._mark_ambiguity(result)
        return result

    def _synchronized_gaps(self, first, second):
        a_gaps, b_gaps = self._track_gaps(first), self._track_gaps(second)
        result = []
        for a in a_gaps:
            for b in b_gaps:
                start, end = max(a[0], b[0]), min(a[1], b[1])
                if end - start > self.TOLERANCE:
                    result.append({"start": start, "end": end, "width": end - start,
                                   "face_a_adjacent_segments": a[2], "face_b_adjacent_segments": b[2]})
        return result

    def _track_gaps(self, track):
        result = []
        intervals = track["intervals"]
        for left, right in zip(intervals, intervals[1:]):
            if right["start"] - left["end"] > self.TOLERANCE:
                result.append((left["end"], right["start"], [left["segment_id"], right["segment_id"]]))
        return result

    def _end_cap_handles(self, first, second, segments):
        handles = []
        for parameter in (max(first["span"][0], second["span"][0]), min(first["span"][1], second["span"][1])):
            a = self._track_point(first, parameter)
            b = self._track_point(second, parameter)
            for segment in segments:
                if self._segment_connects(segment, a, b):
                    handles.extend(segment["source_handles"]); break
        return sorted(set(handles))

    def _segment_connects(self, segment, a, b):
        return ((self._distance(segment["start"], a) <= self.TOLERANCE and self._distance(segment["end"], b) <= self.TOLERANCE)
                or (self._distance(segment["end"], a) <= self.TOLERANCE and self._distance(segment["start"], b) <= self.TOLERANCE))

    def _mark_ambiguity(self, pairs):
        memberships = {}
        for pair in pairs:
            for track in (pair["face_a"]["track_id"], pair["face_b"]["track_id"]):
                memberships.setdefault(track, []).append(pair["id"])
        for pair in pairs:
            competing = sorted(set(memberships[pair["face_a"]["track_id"]] + memberships[pair["face_b"]["track_id"]]) - {pair["id"]})
            pair["competing_wall_candidate_ids"] = competing
            pair["status"] = "pending_multiple_face_pairs" if competing else "resolved_face_pair"

    @staticmethod
    def _thickness(pair):
        return {"wall_candidate_id": pair["id"], "thickness": pair["offset_distance"],
                "evidence": ["orthogonal distance between proven parallel face tracks"],
                "status": "pending_ambiguous_pair" if pair["status"] != "resolved_face_pair" else "resolved_candidate"}

    def _voids(self, pair):
        result = []
        for gap in pair["synchronized_gaps"]:
            a0 = self._track_point(pair["face_a"], gap["start"])
            a1 = self._track_point(pair["face_a"], gap["end"])
            b1 = self._track_point(pair["face_b"], gap["end"])
            b0 = self._track_point(pair["face_b"], gap["start"])
            adjacent = gap["face_a_adjacent_segments"] + gap["face_b_adjacent_segments"]
            handles = []
            for track in (pair["face_a"], pair["face_b"]):
                for interval in track["intervals"]:
                    if interval["segment_id"] in adjacent: handles.extend(interval["source_handles"])
            result.append({"id": f"OPENING-VOID-{pair['id']}-{len(result)+1:02d}",
                           "wall_candidate_id": pair["id"], "void_polygon": [a0, a1, b1, b0, a0],
                           "width": gap["width"], "orientation": pair["direction"],
                           "source_handles": sorted(set(handles)),
                           "status": "pending_wall_face_ambiguity" if pair["status"] != "resolved_face_pair" else "resolved_void_candidate",
                           "evidence": ["synchronized interruption on both parallel wall faces"]})
        return result

    def _associate(self, geometry, voids, kind):
        from shapely.geometry import LineString, Polygon

        object_id = geometry.get(f"{kind}_id")
        candidates = []
        world_lines = [LineString([item["start"], item["end"]]) for item in geometry.get("segments", [])]
        for void in voids:
            polygon = Polygon(void["void_polygon"])
            overlap = any(line.intersects(polygon) and line.intersection(polygon).length > self.TOLERANCE for line in world_lines)
            axis = geometry.get("opening_axis")
            parallel = axis is not None and abs(self._cross(axis, void["orientation"])) <= self.PARALLEL_TOLERANCE
            width = geometry.get("width_candidate")
            compatible = width is not None and abs(width - void["width"]) <= max(self.WIDTH_TOLERANCE, void["width"] * 0.20)
            if overlap and parallel and compatible:
                candidates.append(void)
        status = "resolved" if len(candidates) == 1 and candidates[0]["status"] == "resolved_void_candidate" else "pending_multiple_candidates" if len(candidates) > 1 else "pending_wall_face_ambiguity" if len(candidates) == 1 else "unresolved"
        selected = candidates[0] if status == "resolved" else None
        return {f"{kind}_id": object_id, "source_handle": geometry.get("source_handle"),
                "opening_void_id": selected["id"] if selected else None,
                "wall_candidate_id": selected["wall_candidate_id"] if selected else None,
                "candidate_opening_void_ids": [item["id"] for item in candidates],
                "status": status, "confidence": 1.0 if selected else 0.0,
                "evidence": ["world block geometry overlaps void", "compatible projected width", "rotation parallel to wall faces"] if candidates else ["complete block-to-void validation unavailable"]}

    @staticmethod
    def _physical_walls(pairs, voids):
        return [{"id": pair["id"], "faces": [pair["face_a"]["track_id"], pair["face_b"]["track_id"]],
                 "centerline": DXFCanonicalWallFaceOpeningJambPairResolverV1._centerline(pair),
                 "thickness": pair["offset_distance"],
                 "openings": [void["id"] for void in voids if void["wall_candidate_id"] == pair["id"]],
                 "source_handles": pair["source_handles"],
                 "status": "resolved_candidate" if pair["status"] == "resolved_face_pair" else "pending_ambiguity"}
                for pair in pairs]

    def _enclosure(self, walls):
        from shapely.geometry import LineString
        from shapely.ops import polygonize, unary_union

        resolved = [wall for wall in walls if wall["status"] == "resolved_candidate"]
        lines = [LineString(wall["centerline"]) for wall in resolved]
        loops = list(polygonize(unary_union(lines))) if lines else []
        return {"status": "resolved" if len(loops) == 1 else "pending_multiple_enclosures" if len(loops) > 1 else "UNRESOLVED",
                "candidate_count": len(loops),
                "candidates": [{"id": f"PHYSICAL-ENC-{index:03d}", "polygon": self._polygon(poly),
                                "evidence": ["closed resolved physical-wall centerline continuity"]}
                               for index, poly in enumerate(loops, 1)],
                "selected_enclosure_id": loops and len(loops) == 1 and "PHYSICAL-ENC-001" or None,
                "selection_rule": "unique topology only; area not used"}

    @staticmethod
    def _unresolved(pairs, doors, windows, enclosure):
        result = []
        if any(pair["status"] != "resolved_face_pair" for pair in pairs): result.append("ambiguous_wall_face_pairs")
        result += [f"{item['door_id']}:opening" for item in doors if item["status"] != "resolved"]
        result += [f"{item['window_id']}:opening" for item in windows if item["status"] != "resolved"]
        if enclosure["status"] != "resolved": result.append("building_enclosure")
        result += ["main_entrance", "exterior_interior_classification"]
        return result

    def _pending(self, reason):
        return {"version": self.VERSION, "analysis_mode": "READ_ONLY_REFERENCE_EVIDENCE",
                "canonical_view_id": None, "wall_face_pair_candidates": [], "wall_thickness_candidates": [],
                "physical_wall_candidates": [], "opening_void_candidates": [],
                "opening_association_contract": {"doors": [], "windows": []},
                "building_enclosure_status": {"status": "UNRESOLVED"}, "main_entrance_status": "UNRESOLVED",
                "evidence_status": "UNRESOLVED", "unresolved_items": [reason],
                "production_pipeline_consumable": False}

    @staticmethod
    def _track_point(track, parameter):
        direction, normal = track["direction"], track["normal"]
        return [direction[0] * parameter + normal[0] * track["offset"],
                direction[1] * parameter + normal[1] * track["offset"]]

    @staticmethod
    def _centerline(pair):
        start = max(pair["face_a"]["span"][0], pair["face_b"]["span"][0])
        end = min(pair["face_a"]["span"][1], pair["face_b"]["span"][1])
        a0 = DXFCanonicalWallFaceOpeningJambPairResolverV1._track_point(pair["face_a"], start)
        b0 = DXFCanonicalWallFaceOpeningJambPairResolverV1._track_point(pair["face_b"], start)
        a1 = DXFCanonicalWallFaceOpeningJambPairResolverV1._track_point(pair["face_a"], end)
        b1 = DXFCanonicalWallFaceOpeningJambPairResolverV1._track_point(pair["face_b"], end)
        return [[(a0[0]+b0[0])/2, (a0[1]+b0[1])/2], [(a1[0]+b1[0])/2, (a1[1]+b1[1])/2]]

    @staticmethod
    def _canonical_direction(direction): return direction if direction[0] > 0 or (abs(direction[0]) < 1e-12 and direction[1] >= 0) else [-direction[0], -direction[1]]
    @staticmethod
    def _dot(a, b): return a[0] * b[0] + a[1] * b[1]
    @staticmethod
    def _cross(a, b): return a[0] * b[1] - a[1] * b[0]
    @staticmethod
    def _distance(a, b): return math.hypot(a[0] - b[0], a[1] - b[1])
    @staticmethod
    def _polygon(poly): return [[float(x), float(y)] for x, y in poly.exterior.coords]
