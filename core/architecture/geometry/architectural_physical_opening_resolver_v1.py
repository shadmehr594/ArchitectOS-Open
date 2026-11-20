"""Fail-closed conversion of resolved opening contracts into physical wall voids."""

from __future__ import annotations

from copy import deepcopy
from math import hypot, isfinite


class ArchitecturalPhysicalOpeningResolverV1:
    VERSION = "1.0"
    EPSILON = 1e-7

    @staticmethod
    def _number(value):
        return isinstance(value, (int, float)) and isfinite(float(value))

    @classmethod
    def _dimension(cls, value):
        if not cls._number(value) or float(value) <= 0:
            return None
        value = float(value)
        return value / 1000.0 if value > 50.0 else value

    @staticmethod
    def _point(value):
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            if all(isinstance(item, (int, float)) for item in value[:2]):
                return [float(value[0]), float(value[1])]
        return None

    @classmethod
    def _project(cls, point, start, end):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = hypot(dx, dy)
        if length <= cls.EPSILON:
            return None
        ux, uy = dx / length, dy / length
        along = (point[0] - start[0]) * ux + (point[1] - start[1]) * uy
        distance = abs((point[0] - start[0]) * uy - (point[1] - start[1]) * ux)
        return along, distance, length, ux, uy

    def resolve(self, openings, walls):
        resolved_walls = deepcopy(walls if isinstance(walls, list) else [])
        walls_by_id = {
            wall.get("wall_id", wall.get("id")): wall for wall in resolved_walls
            if isinstance(wall, dict) and wall.get("wall_id", wall.get("id"))
        }
        resolved_openings = []
        for source in openings if isinstance(openings, list) else []:
            if not isinstance(source, dict):
                continue
            opening = dict(source)
            opening["geometry_status"] = "pending"
            opening["geometry_generation_allowed"] = False
            wall = walls_by_id.get(opening.get("host_wall_id"))
            width, height = self._dimension(opening.get("width")), self._dimension(opening.get("height"))
            if not isinstance(wall, dict) or width is None or height is None:
                opening["physical_resolution_reason"] = "unique_host_width_height_required"
                resolved_openings.append(opening)
                continue
            if opening.get("type") == "window" and wall.get("is_exterior") is not True:
                if opening.get("semantic_scope") != "interior_opening":
                    opening["physical_resolution_reason"] = "window_requires_exterior_wall"
                    resolved_openings.append(opening)
                    continue
            start, end = self._point(wall.get("start")), self._point(wall.get("end"))
            if start is None or end is None:
                opening["physical_resolution_reason"] = "host_segment_invalid"
                resolved_openings.append(opening)
                continue
            center = self._point(opening.get("opening_center") or opening.get("center"))
            position = opening.get("position_on_host")
            base = self._project(start, start, end)
            if base is None:
                opening["physical_resolution_reason"] = "host_segment_invalid"
                resolved_openings.append(opening)
                continue
            length, ux, uy = base[2], base[3], base[4]
            if center is None and self._number(position):
                along = float(position) * length if 0.0 <= float(position) <= 1.0 else float(position)
                center = [start[0] + ux * along, start[1] + uy * along]
            projection = self._project(center, start, end) if center is not None else None
            clearance = self._dimension(opening.get("end_clearance")) or 0.0
            if (projection is None or projection[1] > self.EPSILON
                    or projection[0] - width / 2.0 < clearance - self.EPSILON
                    or projection[0] + width / 2.0 > length - clearance + self.EPSILON):
                opening["physical_resolution_reason"] = "resolved_placement_not_inside_usable_host"
                resolved_openings.append(opening)
                continue
            a, b = projection[0] - width / 2.0, projection[0] + width / 2.0
            opening.update({
                "opening_center": center,
                "opening_start": [start[0] + ux * a, start[1] + uy * a],
                "opening_end": [start[0] + ux * b, start[1] + uy * b],
                "symbol_start": [start[0] + ux * a, start[1] + uy * a],
                "symbol_end": [start[0] + ux * b, start[1] + uy * b],
                "resolved_width": width, "resolved_height": height,
                "position_on_host": projection[0] / length,
                "geometry_status": "resolved", "geometry_generation_allowed": True,
                "physical_resolution_reason": "resolved_contract_cut_into_host_wall",
            })
            wall.setdefault("physical_openings", []).append({
                "opening_id": opening.get("opening_id") or opening.get("id"),
                "type": opening.get("type"), "start_distance": a, "end_distance": b,
                "start": opening["opening_start"], "end": opening["opening_end"],
                "width": width, "height": height, "geometry_status": "resolved",
            })
            resolved_openings.append(opening)
        for wall in resolved_walls:
            start, end = self._point(wall.get("start")), self._point(wall.get("end"))
            if start is None or end is None:
                continue
            length = hypot(end[0] - start[0], end[1] - start[1])
            if length <= self.EPSILON:
                continue
            ux, uy = (end[0] - start[0]) / length, (end[1] - start[1]) / length
            intervals = sorted(
                (item["start_distance"], item["end_distance"])
                for item in wall.get("physical_openings", [])
                if item.get("geometry_status") == "resolved"
            )
            cursor, segments = 0.0, []
            for a, b in intervals:
                if a > cursor + self.EPSILON:
                    segments.append({"start": [start[0]+ux*cursor, start[1]+uy*cursor],
                                     "end": [start[0]+ux*a, start[1]+uy*a]})
                cursor = max(cursor, b)
            if cursor < length - self.EPSILON:
                segments.append({"start": [start[0]+ux*cursor, start[1]+uy*cursor], "end": end})
            wall["solid_segments"] = segments
            wall["opening_aware_geometry"] = True
        return resolved_openings, resolved_walls

    def vehicle_opening(self, walls, driveway, width, height):
        """Resolve the unique target-level exterior wall crossed by a driveway."""
        centerline = driveway.get("centerline") if isinstance(driveway, dict) else None
        if not isinstance(centerline, list) or len(centerline) < 2:
            return {"geometry_status": "pending", "reason": "driveway_centerline_missing"}
        p, q = self._point(centerline[0]), self._point(centerline[-1])
        matches = []
        for wall in walls if isinstance(walls, list) else []:
            if not isinstance(wall, dict) or wall.get("is_exterior") is not True:
                continue
            if wall.get("floor") != driveway.get("served_level"):
                continue
            a, b = self._point(wall.get("start")), self._point(wall.get("end"))
            hit = self._intersection(p, q, a, b) if all((p, q, a, b)) else None
            if hit is not None:
                matches.append((wall, hit))
        if len(matches) != 1:
            return {"geometry_status": "pending", "reason": "vehicle_host_wall_not_unique", "candidate_count": len(matches)}
        wall, center = matches[0]
        opening = {
            "opening_id": "vehicle_" + str(driveway.get("access_id")) + "_opening",
            "id": "vehicle_" + str(driveway.get("access_id")) + "_opening",
            "type": "vehicle_entrance", "category": "vehicle_entrance",
            "floor": driveway.get("served_level"), "host_wall_id": wall.get("wall_id"),
            "opening_center": center, "width": width, "height": height,
            "source": "vehicle_entrance_contract",
        }
        openings, updated = self.resolve([opening], walls)
        return openings[0] | {"physical_walls": updated}

    @classmethod
    def _intersection(cls, p, q, a, b):
        rx, ry, sx, sy = q[0]-p[0], q[1]-p[1], b[0]-a[0], b[1]-a[1]
        denominator = rx*sy - ry*sx
        if abs(denominator) <= cls.EPSILON:
            return None
        apx, apy = a[0]-p[0], a[1]-p[1]
        t, u = (apx*sy-apy*sx)/denominator, (apx*ry-apy*rx)/denominator
        if -cls.EPSILON <= t <= 1+cls.EPSILON and -cls.EPSILON <= u <= 1+cls.EPSILON:
            return [p[0]+t*rx, p[1]+t*ry]
        return None
