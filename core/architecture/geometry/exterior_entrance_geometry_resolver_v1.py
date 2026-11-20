import math


class ExteriorEntranceGeometryResolverV1:
    """Resolve exterior entrance XY geometry strictly from supplied evidence."""

    VERSION = "1.0"

    def resolve(self, architectural_geometry, semantic_transition):
        geometry = architectural_geometry if isinstance(architectural_geometry, dict) else {}
        transition = semantic_transition if isinstance(semantic_transition, dict) else {}
        result = {
            "version": self.VERSION,
            "status": "pending",
            "main_entrance": self._pending_entrance("main_entrance_opening_unresolved"),
            "entrance_threshold": self._pending_threshold(transition=transition),
            "exterior_platform_geometry": self._pending_platform(transition),
            "entrance_steps_geometry": self._pending_steps(transition),
            "conflict_validation": {"status": "pending", "evidence_used": [], "limitations": []},
            "source": "ExteriorEntranceGeometryResolverV1",
        }

        entrances = [
            opening for opening in geometry.get("openings", [])
            if isinstance(opening, dict)
            and opening.get("type") == "door"
            and opening.get("category") == "main_entrance"
        ]
        if len(entrances) != 1:
            result["main_entrance"]["missing_evidence"] = [
                "unique_main_entrance_opening"
            ]
            return result

        opening = entrances[0]
        host_id = opening.get("host_wall_id")
        walls = {
            wall.get("wall_id", wall.get("id")): wall
            for wall in geometry.get("physical_walls", [])
            if isinstance(wall, dict)
        }
        wall = walls.get(host_id)
        if not host_id or not isinstance(wall, dict):
            result["main_entrance"] = self._pending_entrance(
                "resolved_opening_host_geometry_required", opening
            )
            return result

        wall_start, wall_end = self._point(wall.get("start")), self._point(wall.get("end"))
        center = self._point(
            opening.get("entrance_center", opening.get("center", opening.get("opening_center")))
        )
        width = self._positive(opening.get("clear_width", opening.get("width")))
        footprint = self._building_footprint(geometry, opening.get("floor"))
        if not wall_start or not wall_end or not center or width is None or not footprint:
            missing = []
            if not wall_start or not wall_end:
                missing.append("host_wall_segment")
            if not center:
                missing.append("opening_center")
            if width is None:
                missing.append("opening_width")
            if not footprint:
                missing.append("building_footprint")
            result["main_entrance"] = self._pending_entrance(
                "main_entrance_geometry_incomplete", opening, missing
            )
            return result

        normal = self._exterior_normal(wall_start, wall_end, footprint)
        if normal is None:
            result["main_entrance"] = self._pending_entrance(
                "exterior_side_unresolved", opening, ["exterior_normal"]
            )
            return result
        tangent = self._unit((wall_end[0] - wall_start[0], wall_end[1] - wall_start[1]))
        result["main_entrance"] = {
            "opening_id": opening.get("id"), "host_wall_id": host_id,
            "wall_start": wall_start, "wall_end": wall_end,
            "entrance_center": center, "entrance_width": width,
            "entrance_orientation": tangent, "exterior_normal": normal,
            "resolution_status": "resolved",
            "evidence_used": ["opening.category=main_entrance", "resolved_host_wall_id",
                              "opening_center", "host_exterior_wall", "building_footprint"],
            "missing_evidence": [],
        }

        finished_floor = transition.get("finished_floor", {})
        site_datum = transition.get("site_datum", {})
        platform_semantic = transition.get("entrance_platform", {})
        steps_semantic = transition.get("exterior_steps", {})
        if not isinstance(finished_floor, dict):
            finished_floor = {}
        if not isinstance(site_datum, dict):
            site_datum = {}
        if not isinstance(platform_semantic, dict):
            platform_semantic = {}
        if not isinstance(steps_semantic, dict):
            steps_semantic = {}

        threshold_z = self._number(finished_floor.get("elevation"))
        platform_z = self._number(platform_semantic.get("elevation"))
        site_z = self._number(site_datum.get("elevation"))
        step_start_z = self._number(steps_semantic.get("start_z"))
        step_end_z = self._number(steps_semantic.get("end_z"))
        level_values = (threshold_z, platform_z, site_z, step_start_z, step_end_z)
        if any(value is None for value in level_values):
            result["entrance_threshold"] = self._pending_threshold(
                "finished_floor_platform_site_and_step_level_evidence_required",
                opening,
                transition,
            )
            result["exterior_platform_geometry"] = self._pending_platform(
                transition, ["resolved_entrance_threshold_levels"]
            )
            result["entrance_steps_geometry"] = self._pending_steps(
                transition, ["resolved_entrance_threshold_levels"]
            )
            return result
        if not (
            math.isclose(threshold_z, platform_z, abs_tol=1e-8)
            and math.isclose(threshold_z, step_end_z, abs_tol=1e-8)
            and math.isclose(site_z, step_start_z, abs_tol=1e-8)
        ):
            result["entrance_threshold"] = self._pending_threshold(
                "entrance_level_evidence_conflict",
                opening,
                transition,
            )
            result["exterior_platform_geometry"] = self._pending_platform(
                transition, ["consistent_finished_floor_platform_and_step_levels"]
            )
            result["entrance_steps_geometry"] = self._pending_steps(
                transition, ["consistent_site_datum_and_threshold_step_levels"]
            )
            return result

        result["entrance_threshold"] = {
            "type": "main_entrance_threshold",
            "opening_id": opening.get("id"),
            "host_wall_id": host_id,
            "center": center,
            "elevation": threshold_z,
            "finished_floor_level": finished_floor.get("level", opening.get("floor")),
            "resolution_status": "resolved",
            "resolution_reason": "resolved_opening_and_consistent_authoritative_levels",
            "evidence_used": [
                "resolved_main_entrance_opening",
                "finished_floor_elevation",
                "entrance_platform_elevation",
                "exterior_steps_end_z",
            ],
            "missing_evidence": [],
            "source": self.__class__.__name__,
        }

        platform_rules = transition.get("platform_rules", {})
        if not isinstance(platform_rules, dict):
            platform_rules = {}
        depth = self._positive(platform_rules.get("minimum_depth", platform_semantic.get("depth")))
        side_clearance = self._nonnegative(platform_rules.get("side_clearance"))
        explicit_width = self._positive(platform_semantic.get("width"))
        platform_width = explicit_width
        width_source = "explicit_platform_width" if explicit_width else None
        if platform_width is None and side_clearance is not None:
            platform_width = width + 2.0 * side_clearance
            width_source = "entrance_width_plus_explicit_side_clearance"
        missing = []
        if depth is None:
            missing.append("platform_depth_rule_or_evidence")
        if platform_width is None:
            missing.append("platform_width_or_side_clearance_rule")
        if missing:
            result["exterior_platform_geometry"] = self._pending_platform(transition, missing)
            return result

        platform = self._platform_polygon(center, tangent, normal, platform_width, depth)
        conflict = self._validate_polygon(
            platform, footprint, geometry, require_outside_building=True
        )
        result["conflict_validation"] = conflict
        if conflict["status"] != "clear":
            result["exterior_platform_geometry"] = self._pending_platform(
                transition, ["platform_conflict_or_site_limit_unresolved"]
            )
            return result
        result["exterior_platform_geometry"] = {
            "type": "exterior_platform", "connected_to": "main_entrance",
            "connected_opening_id": opening.get("id"),
            "threshold_elevation": threshold_z,
            "elevation": platform_z, "polygon": platform,
            "width": platform_width, "depth": depth, "orientation": normal,
            "host_wall_id": host_id, "geometry_status": "resolved",
            "geometry_generation_allowed": True,
            "evidence_used": [width_source, "explicit_platform_depth", "resolved_exterior_normal"],
            "missing_evidence": [], "source": self.__class__.__name__,
        }

        tread_depth = self._positive(steps_semantic.get("tread_depth"))
        tread_count = self._positive_int(steps_semantic.get("tread_count"))
        clear_width = self._positive(steps_semantic.get("clear_width")) or platform_width
        step_missing = []
        if tread_depth is None:
            step_missing.append("tread_depth_rule_or_evidence")
        if tread_count is None:
            step_missing.append("tread_count_evidence")
        if clear_width is None:
            step_missing.append("step_clear_width")
        if step_missing:
            result["entrance_steps_geometry"] = self._pending_steps(transition, step_missing)
            result["status"] = "platform_resolved_steps_pending"
            return result

        half = clear_width / 2.0
        platform_outer = (center[0] + normal[0] * depth, center[1] + normal[1] * depth)
        run = tread_depth * tread_count
        start = (platform_outer[0] + normal[0] * run, platform_outer[1] + normal[1] * run)
        end = platform_outer
        step_polygon = [
            [start[0] - tangent[0] * half, start[1] - tangent[1] * half],
            [start[0] + tangent[0] * half, start[1] + tangent[1] * half],
            [end[0] + tangent[0] * half, end[1] + tangent[1] * half],
            [end[0] - tangent[0] * half, end[1] - tangent[1] * half],
        ]
        step_conflict = self._validate_polygon(
            step_polygon, footprint, geometry, require_outside_building=True
        )
        result["conflict_validation"] = step_conflict
        if step_conflict["status"] != "clear":
            result["entrance_steps_geometry"] = self._pending_steps(
                transition, ["step_conflict_or_site_limit_unresolved"]
            )
            result["status"] = "platform_resolved_steps_rejected"
            return result
        edges = []
        for index in range(tread_count + 1):
            distance = index * tread_depth
            point = (end[0] + normal[0] * distance, end[1] + normal[1] * distance)
            edges.append([
                [point[0] - tangent[0] * half, point[1] - tangent[1] * half],
                [point[0] + tangent[0] * half, point[1] + tangent[1] * half],
            ])
        result["entrance_steps_geometry"] = {
            "type": "exterior_entrance_steps", "connected_to": "main_entrance",
            "connected_opening_id": opening.get("id"),
            "threshold_elevation": threshold_z,
            "start_z": steps_semantic.get("start_z"), "end_z": steps_semantic.get("end_z"),
            "total_rise": steps_semantic.get("total_rise"),
            "riser_count": steps_semantic.get("riser_count"),
            "riser_height": steps_semantic.get("riser_height"),
            "tread_count": tread_count, "tread_depth": tread_depth,
            "clear_width": clear_width, "start_point": list(start), "end_point": list(end),
            "direction": [-normal[0], -normal[1]],
            "walking_line": [list(start), list(end)], "step_edges": edges,
            "polygon": step_polygon, "geometry_status": "resolved",
            "geometry_generation_allowed": True,
            "evidence_used": ["semantic_vertical_transition", "explicit_tread_contract",
                              "resolved_platform", "resolved_exterior_normal"],
            "missing_evidence": [], "source": self.__class__.__name__,
        }
        result["status"] = "resolved"
        return result

    def _building_footprint(self, geometry, floor):
        for item in geometry.get("floor_geometry", []):
            if isinstance(item, dict) and (floor is None or item.get("floor") == floor):
                points = self._footprint_points(item)
                if points:
                    return points
        for item in geometry.get("slabs", []):
            if isinstance(item, dict) and (floor is None or item.get("floor") == floor):
                points = self._footprint_points(item)
                if points:
                    return points
        return None

    def _exterior_normal(self, start, end, footprint):
        tangent = self._unit((end[0] - start[0], end[1] - start[1]))
        if tangent is None:
            return None
        normal = (-tangent[1], tangent[0])
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        centroid = self._centroid(footprint)
        toward_inside = (centroid[0] - midpoint[0], centroid[1] - midpoint[1])
        if normal[0] * toward_inside[0] + normal[1] * toward_inside[1] > 0:
            normal = (-normal[0], -normal[1])
        return [normal[0], normal[1]]

    def _validate_polygon(self, polygon, building, geometry, require_outside_building=False):
        evidence = ["exact_candidate_polygon", "building_footprint"]
        if require_outside_building and any(self._strictly_inside(point, building) for point in polygon):
            return {"status": "conflict", "reason": "candidate_enters_building_interior",
                    "evidence_used": evidence, "limitations": []}
        parcel = self._polygon_from_value(geometry.get("site_geometry", {}).get("parcel_boundary"))
        if parcel:
            evidence.append("parcel_boundary")
            if any(not self._inside_or_boundary(point, parcel) for point in polygon):
                return {"status": "conflict", "reason": "candidate_outside_parcel",
                        "evidence_used": evidence, "limitations": []}
        conflicts = geometry.get("protected_zones", []) or geometry.get("conflict_zones", [])
        for zone in conflicts:
            zone_polygon = self._footprint_points(zone) if isinstance(zone, dict) else self._polygon_from_value(zone)
            if zone_polygon and self._polygons_intersect(polygon, zone_polygon):
                return {"status": "conflict", "reason": "candidate_intersects_protected_zone",
                        "evidence_used": evidence + ["protected_zone_polygon"], "limitations": []}
        limitations = [] if parcel else ["parcel_boundary_unavailable"]
        return {"status": "clear", "reason": "no_conflict_in_available_authoritative_geometry",
                "evidence_used": evidence, "limitations": limitations}

    @staticmethod
    def _platform_polygon(center, tangent, normal, width, depth):
        half = width / 2.0
        a = [center[0] - tangent[0] * half, center[1] - tangent[1] * half]
        b = [center[0] + tangent[0] * half, center[1] + tangent[1] * half]
        return [a, b, [b[0] + normal[0] * depth, b[1] + normal[1] * depth],
                [a[0] + normal[0] * depth, a[1] + normal[1] * depth]]

    @staticmethod
    def _pending_entrance(reason, opening=None, missing=None):
        opening = opening if isinstance(opening, dict) else {}
        return {"opening_id": opening.get("id"), "host_wall_id": opening.get("host_wall_id"),
                "wall_start": None, "wall_end": None, "entrance_center": None,
                "entrance_width": opening.get("width"), "entrance_orientation": None,
                "exterior_normal": None, "resolution_status": "pending",
                "resolution_reason": reason, "evidence_used": [],
                "missing_evidence": missing or []}

    @staticmethod
    def _pending_threshold(reason="resolved_main_entrance_and_level_evidence_required", opening=None, transition=None):
        opening = opening if isinstance(opening, dict) else {}
        transition = transition if isinstance(transition, dict) else {}
        finished = transition.get("finished_floor", {})
        finished = finished if isinstance(finished, dict) else {}
        return {"type": "main_entrance_threshold", "opening_id": opening.get("id"),
                "host_wall_id": opening.get("host_wall_id"), "center": None,
                "elevation": finished.get("elevation"),
                "finished_floor_level": finished.get("level", opening.get("floor")),
                "resolution_status": "pending", "resolution_reason": reason,
                "evidence_used": [], "missing_evidence": [reason],
                "source": "ExteriorEntranceGeometryResolverV1"}

    @staticmethod
    def _pending_platform(transition, missing=None):
        semantic = transition.get("entrance_platform", {}) if isinstance(transition, dict) else {}
        return {"type": "exterior_platform", "connected_to": "main_entrance",
                "elevation": semantic.get("elevation"), "polygon": None, "width": None,
                "depth": None, "orientation": None, "host_wall_id": None,
                "geometry_status": "pending", "geometry_generation_allowed": False,
                "evidence_used": [], "missing_evidence": missing or ["resolved_main_entrance_geometry"],
                "source": "ExteriorEntranceGeometryResolverV1"}

    @staticmethod
    def _pending_steps(transition, missing=None):
        semantic = transition.get("exterior_steps", {}) if isinstance(transition, dict) else {}
        keys = ("start_z", "end_z", "total_rise", "riser_count", "riser_height",
                "tread_count", "tread_depth", "clear_width")
        result = {key: semantic.get(key) for key in keys}
        result.update({"type": "exterior_entrance_steps", "connected_to": "main_entrance",
                       "start_point": None, "end_point": None, "direction": None,
                       "walking_line": None, "step_edges": [], "polygon": None,
                       "geometry_status": "pending", "geometry_generation_allowed": False,
                       "evidence_used": [], "missing_evidence": missing or ["resolved_platform_geometry"],
                       "source": "ExteriorEntranceGeometryResolverV1"})
        return result

    @staticmethod
    def _point(value):
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            try:
                return [float(value[0]), float(value[1])]
            except (TypeError, ValueError):
                return None
        return None

    @classmethod
    def _footprint_points(cls, item):
        footprint = item.get("footprint", item.get("polygon"))
        if isinstance(footprint, dict):
            footprint = footprint.get("points", footprint.get("source_points"))
        return cls._polygon_from_value(footprint)

    @classmethod
    def _polygon_from_value(cls, value):
        if not isinstance(value, list) or len(value) < 3:
            return None
        points = [cls._point(point) for point in value]
        return points if all(points) else None

    @staticmethod
    def _positive(value):
        try:
            number = float(value)
            return number if number > 0 else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _number(value):
        try:
            return float(value) if not isinstance(value, bool) else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _positive_int(cls, value):
        number = cls._positive(value)
        return int(number) if number is not None and number.is_integer() else None

    @staticmethod
    def _nonnegative(value):
        try:
            number = float(value)
            return number if number >= 0 else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _unit(vector):
        length = math.hypot(vector[0], vector[1])
        return (vector[0] / length, vector[1] / length) if length > 1e-9 else None

    @staticmethod
    def _centroid(polygon):
        return (sum(p[0] for p in polygon) / len(polygon),
                sum(p[1] for p in polygon) / len(polygon))

    @classmethod
    def _strictly_inside(cls, point, polygon):
        return cls._inside_or_boundary(point, polygon) and not cls._on_boundary(point, polygon)

    @staticmethod
    def _inside_or_boundary(point, polygon):
        if ExteriorEntranceGeometryResolverV1._on_boundary(point, polygon):
            return True
        x, y = point
        inside = False
        j = len(polygon) - 1
        for i in range(len(polygon)):
            xi, yi = polygon[i]; xj, yj = polygon[j]
            if (yi > y) != (yj > y):
                cross = (xj - xi) * (y - yi) / (yj - yi) + xi
                if x < cross:
                    inside = not inside
            j = i
        return inside

    @staticmethod
    def _on_boundary(point, polygon):
        for index, start in enumerate(polygon):
            end = polygon[(index + 1) % len(polygon)]
            cross = (point[0] - start[0]) * (end[1] - start[1]) - (point[1] - start[1]) * (end[0] - start[0])
            if abs(cross) <= 1e-8 and min(start[0], end[0]) - 1e-8 <= point[0] <= max(start[0], end[0]) + 1e-8 and min(start[1], end[1]) - 1e-8 <= point[1] <= max(start[1], end[1]) + 1e-8:
                return True
        return False

    @classmethod
    def _polygons_intersect(cls, first, second):
        if any(cls._inside_or_boundary(point, second) for point in first):
            return True
        if any(cls._inside_or_boundary(point, first) for point in second):
            return True
        for i, a in enumerate(first):
            b = first[(i + 1) % len(first)]
            for j, c in enumerate(second):
                d = second[(j + 1) % len(second)]
                if cls._segments_intersect(a, b, c, d):
                    return True
        return False

    @staticmethod
    def _segments_intersect(a, b, c, d):
        def orientation(p, q, r):
            return (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
        return orientation(a, b, c) * orientation(a, b, d) < 0 and orientation(c, d, a) * orientation(c, d, b) < 0
