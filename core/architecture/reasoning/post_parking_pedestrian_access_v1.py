"""Internal pedestrian access from pilot parking stalls to the common core."""
from math import hypot

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union


class PostParkingPedestrianAccessV1:
    """Prove a topological internal route without asserting regulatory approval."""

    EPS = 1e-6

    def resolve(self, stalls, lobby, core, vehicle_zones, parcel, path_width):
        lobby, core, parcel = Polygon(lobby), Polygon(core), Polygon(parcel)
        stall_shapes = [(s["stall_id"], Polygon(s["polygon"])) for s in stalls]
        vehicle_union = unary_union([Polygon(p) for p in vehicle_zones])
        results = []
        for stall_id, stall in stall_shapes:
            exit_point = self._nearest_boundary_point(stall, lobby.centroid)
            target = self._nearest_boundary_point(lobby, exit_point)
            alternatives = self._alternatives(exit_point, target)
            other_stalls = unary_union([p for sid, p in stall_shapes if sid != stall_id])
            accepted = []
            diagnostics = []
            for strategy, coordinates in alternatives:
                centerline = LineString(coordinates)
                corridor = centerline.buffer(path_width / 2.0, cap_style=2, join_style=2)
                outside = corridor.difference(parcel).area
                stall_collision = corridor.intersection(other_stalls).area
                arrival_clearance = lobby.buffer(path_width / 2.0, cap_style=2, join_style=2)
                core_collision = corridor.intersection(core.difference(arrival_clearance)).area
                crossing = centerline.intersection(vehicle_union)
                crossing_count = self._crossing_count(crossing)
                diagnostic = {
                    "strategy": strategy,
                    "centerline": self._line(centerline),
                    "protected_pedestrian_segment": self._polys(corridor),
                    "path_length": centerline.length,
                    "crossing_count": crossing_count,
                    "crossing_points": self._points(crossing),
                    "outside_parcel_area": outside,
                    "other_stall_collision_area": stall_collision,
                    "core_collision_area": core_collision,
                }
                diagnostics.append(diagnostic)
                if outside <= self.EPS and stall_collision <= self.EPS and core_collision <= self.EPS:
                    accepted.append(diagnostic)
            chosen = min(accepted, key=lambda a: (a["crossing_count"], a["path_length"])) if accepted else None
            results.append({
                "stall_id": stall_id,
                "stall_exit_point": [exit_point.x, exit_point.y],
                "parking_to_lobby_path": chosen["centerline"] if chosen else None,
                "protected_pedestrian_segment": chosen["protected_pedestrian_segment"] if chosen else [],
                "parking_to_core_access_status": (
                    "resolved_separated" if chosen and chosen["crossing_count"] == 0
                    else "resolved_with_controlled_crossing_pending_validation" if chosen
                    else "not_feasible"
                ),
                "parking_to_core_path_length": chosen["path_length"] if chosen else None,
                "parking_to_core_crossing_count": chosen["crossing_count"] if chosen else None,
                "parking_to_core_vehicle_conflict_status": (
                    "clear" if chosen and chosen["crossing_count"] == 0
                    else "controlled_crossing_requires_validation" if chosen
                    else "unresolved"
                ),
                "crossing_points": chosen["crossing_points"] if chosen else [],
                "route_strategies_tested": [a["strategy"] for a in diagnostics],
                "route_diagnostics": diagnostics,
                "regulatory_status": "pending_rule_resolution",
            })
        accessible = all(r["parking_to_core_access_status"] != "not_feasible" for r in results)
        return {
            "contract": "PostParkingPedestrianAccessV1",
            "stall_results": results,
            "parking_to_core_access_status": "topology_resolved_pending_crossing_validation" if accessible else "not_feasible",
            "parking_to_core_path_length": max((r["parking_to_core_path_length"] or 0 for r in results), default=0),
            "parking_to_core_crossing_count": sum((r["parking_to_core_crossing_count"] or 0 for r in results)),
            "parking_to_core_vehicle_conflict_status": (
                "controlled_crossings_require_validation" if accessible and any(r["parking_to_core_crossing_count"] for r in results)
                else "clear" if accessible else "unresolved"
            ),
            "all_parking_users_reach_core_internally": accessible,
            "independently_usable_parking_count": 0,
            "independently_usable_status": "pending_vehicle_model_validation" if accessible else "not_feasible",
        }

    @staticmethod
    def _nearest_boundary_point(polygon, point):
        distance = polygon.exterior.project(point)
        return polygon.exterior.interpolate(distance)

    @staticmethod
    def _alternatives(a, b):
        return [
            ("direct", [(a.x, a.y), (b.x, b.y)]),
            ("orthogonal_x_then_y", [(a.x, a.y), (b.x, a.y), (b.x, b.y)]),
            ("orthogonal_y_then_x", [(a.x, a.y), (a.x, b.y), (b.x, b.y)]),
        ]

    @staticmethod
    def _crossing_count(geometry):
        if geometry.is_empty:
            return 0
        if geometry.geom_type in ("Point", "LineString"):
            return 1
        return len(getattr(geometry, "geoms", [geometry]))

    @staticmethod
    def _points(geometry):
        if geometry.is_empty:
            return []
        if geometry.geom_type == "Point":
            return [[geometry.x, geometry.y]]
        if geometry.geom_type == "LineString":
            p = geometry.interpolate(0.5, normalized=True)
            return [[p.x, p.y]]
        points = []
        for part in getattr(geometry, "geoms", []):
            points.extend(PostParkingPedestrianAccessV1._points(part))
        return points

    @staticmethod
    def _line(line):
        return [[float(x), float(y)] for x, y in line.coords]

    @staticmethod
    def _polys(geometry):
        parts = [geometry] if geometry.geom_type == "Polygon" else list(getattr(geometry, "geoms", []))
        return [[[float(x), float(y)] for x, y in list(p.exterior.coords)[:-1]] for p in parts if p.geom_type == "Polygon"]
