import math


class MainEntranceOpeningPlacementSelectorV1:
    """Resolve an ambiguous main entrance from explicit pedestrian approach geometry."""

    VERSION = "1.0"
    TOLERANCE = 1e-7

    def resolve(self, openings, physical_walls, spaces, floor_geometry, site_geometry):
        if not isinstance(openings, list):
            return []

        walls_by_id = {
            wall.get("wall_id"): wall
            for wall in physical_walls if isinstance(wall, dict) and wall.get("wall_id")
        }
        approaches = self._resolved_approaches(site_geometry)
        resolved = []

        for source_opening in openings:
            if not isinstance(source_opening, dict):
                continue
            opening = dict(source_opening)
            if not self._eligible(opening):
                resolved.append(opening)
                continue

            opening["placement_resolution_status"] = "pending"
            opening["placement_resolution_reason"] = (
                "architectural_entrance_placement_evidence_incomplete"
            )
            opening["placement_evidence_used"] = []

            footprint = self._floor_footprint(opening.get("floor"), floor_geometry)
            entrance_space = self._entrance_space(opening, spaces)
            if len(approaches) != 1 or footprint is None or entrance_space is None:
                resolved.append(opening)
                continue

            approach = approaches[0]
            access_start, access_end = approach["line"]
            if self._point_in_polygon(access_start, footprint):
                opening["placement_resolution_reason"] = (
                    "site_access_approach_must_originate_outside_building_footprint"
                )
                resolved.append(opening)
                continue

            matches = []
            for wall_id in opening.get("candidate_wall_ids", []):
                wall = walls_by_id.get(wall_id)
                if not self._topology_matches(opening, entrance_space, wall, footprint):
                    continue
                center = self._segment_intersection(access_start, access_end, wall["start"], wall["end"])
                if center is not None and self._opening_fits(center, wall, opening.get("width")):
                    matches.append((wall, center))

            if len(matches) != 1:
                # Preserve the host resolver's fail-closed ambiguity contract.
                opening["placement_resolution_reason"] = (
                    "site_access_and_facade_topology_do_not_select_one_candidate"
                )
                resolved.append(opening)
                continue

            wall, center = matches[0]
            boundary_ids = wall.get("boundary_ids", [])
            opening["host_wall_id"] = wall.get("wall_id")
            opening["host_boundary_id"] = boundary_ids[0] if len(boundary_ids) == 1 else None
            opening["center"] = center
            opening["host_resolution_status"] = "resolved_from_architectural_placement_evidence"
            opening["host_resolution_reason"] = (
                "unique_candidate_intersected_by_resolved_site_access_approach"
            )
            opening["placement_resolution_status"] = "resolved"
            opening["placement_resolution_reason"] = (
                "site_access_entrance_topology_facade_edge_and_footprint_agree"
            )
            opening["placement_access_id"] = approach["access_id"]
            opening["placement_approach_line"] = [
                list(approach["line"][0]), list(approach["line"][1])
            ]
            opening["placement_evidence_used"] = [
                approach["evidence"],
                "entrance_space_topology",
                "candidate_wall_on_building_footprint_facade_edge",
                "opening_center_from_approach_facade_intersection",
            ]
            resolved.append(opening)

        return resolved

    def _eligible(self, opening):
        return (
            opening.get("category") == "main_entrance"
            and opening.get("host_resolution_status") == "host_pending_multiple_candidates"
            and len(opening.get("candidate_wall_ids", [])) > 1
        )

    def _resolved_approaches(self, site_geometry):
        if not isinstance(site_geometry, dict):
            return []
        sources = []
        for key in ("pedestrian_access", "main_entrance_access"):
            value = site_geometry.get(key)
            if isinstance(value, dict):
                sources.append(value)
        for value in site_geometry.get("site_accesses", []):
            if isinstance(value, dict) and value.get("type") in {
                "pedestrian_access", "main_entrance_access"
            }:
                sources.append(value)

        result = []
        for index, access in enumerate(sources):
            status = access.get("geometry_status", access.get("resolution_status"))
            line = access.get("approach_line")
            if status != "resolved" or not self._valid_line(line):
                continue
            result.append({
                "line": [self._point(line[0]), self._point(line[1])],
                "access_id": access.get("access_id", access.get("id")),
                "evidence": access.get("access_id") or access.get("id") or access.get("source") or f"resolved_site_access_{index}",
            })
        return result

    def _entrance_space(self, opening, spaces):
        matches = [
            space for space in spaces if isinstance(space, dict)
            and space.get("name") == opening.get("space")
            and space.get("floor") == opening.get("floor")
        ]
        return matches[0] if len(matches) == 1 else None

    def _floor_footprint(self, floor, floor_geometry):
        matches = []
        for item in floor_geometry if isinstance(floor_geometry, list) else []:
            if not isinstance(item, dict) or item.get("floor") != floor:
                continue
            footprint = item.get("footprint", {})
            points = footprint.get("points") if isinstance(footprint, dict) else None
            if self._valid_polygon(points):
                matches.append([self._point(point) for point in points])
        return matches[0] if len(matches) == 1 else None

    def _topology_matches(self, opening, entrance_space, wall, footprint):
        if not isinstance(wall, dict) or wall.get("is_exterior") is not True:
            return False
        if opening.get("space") not in wall.get("spaces", []):
            return False
        space_footprint = entrance_space.get("footprint", {})
        space_points = space_footprint.get("points") if isinstance(space_footprint, dict) else None
        return (
            self._valid_line([wall.get("start"), wall.get("end")])
            and self._segment_on_polygon(wall["start"], wall["end"], footprint)
            and self._valid_polygon(space_points)
            and self._segment_on_polygon(wall["start"], wall["end"], space_points)
        )

    def _opening_fits(self, center, wall, width):
        try:
            width = float(width)
        except (TypeError, ValueError):
            return False
        if width > 20:
            width /= 1000.0
        if width <= 0:
            return False
        a, b = self._point(wall["start"]), self._point(wall["end"])
        return min(self._distance(center, a), self._distance(center, b)) + self.TOLERANCE >= width / 2.0

    def _segment_on_polygon(self, start, end, polygon):
        start, end = self._point(start), self._point(end)
        return any(
            self._point_on_segment(start, polygon[index], polygon[(index + 1) % len(polygon)])
            and self._point_on_segment(end, polygon[index], polygon[(index + 1) % len(polygon)])
            for index in range(len(polygon))
        )

    def _point_on_boundary(self, point, polygon):
        return any(
            self._point_on_segment(point, polygon[i], polygon[(i + 1) % len(polygon)])
            for i in range(len(polygon))
        )

    def _segment_intersection(self, a, b, c, d):
        a, b, c, d = map(self._point, (a, b, c, d))
        rx, ry = b[0] - a[0], b[1] - a[1]
        sx, sy = d[0] - c[0], d[1] - c[1]
        denominator = rx * sy - ry * sx
        if abs(denominator) <= self.TOLERANCE:
            return None
        qx, qy = c[0] - a[0], c[1] - a[1]
        t = (qx * sy - qy * sx) / denominator
        u = (qx * ry - qy * rx) / denominator
        if -self.TOLERANCE <= t <= 1 + self.TOLERANCE and -self.TOLERANCE <= u <= 1 + self.TOLERANCE:
            return [a[0] + t * rx, a[1] + t * ry]
        return None

    def _point_in_polygon(self, point, polygon):
        if self._point_on_boundary(point, polygon):
            return True
        x, y = point
        inside = False
        for index in range(len(polygon)):
            x1, y1 = polygon[index]
            x2, y2 = polygon[(index + 1) % len(polygon)]
            if (y1 > y) != (y2 > y):
                crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
                if x < crossing_x:
                    inside = not inside
        return inside

    def _point_on_segment(self, point, start, end):
        point, start, end = map(self._point, (point, start, end))
        cross = (point[0] - start[0]) * (end[1] - start[1]) - (point[1] - start[1]) * (end[0] - start[0])
        if abs(cross) > self.TOLERANCE:
            return False
        return (
            min(start[0], end[0]) - self.TOLERANCE <= point[0] <= max(start[0], end[0]) + self.TOLERANCE
            and min(start[1], end[1]) - self.TOLERANCE <= point[1] <= max(start[1], end[1]) + self.TOLERANCE
        )

    def _valid_line(self, line):
        return isinstance(line, (list, tuple)) and len(line) == 2 and all(self._valid_point(point) for point in line)

    def _valid_polygon(self, polygon):
        return isinstance(polygon, list) and len(polygon) >= 3 and all(self._valid_point(point) for point in polygon)

    def _valid_point(self, point):
        return isinstance(point, (list, tuple)) and len(point) >= 2 and all(isinstance(value, (int, float)) for value in point[:2])

    def _point(self, point):
        return [float(point[0]), float(point[1])]

    def _distance(self, a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])
