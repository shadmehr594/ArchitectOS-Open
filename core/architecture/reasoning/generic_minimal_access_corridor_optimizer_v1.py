"""Geometry-derived trimming and residual recovery for access-first candidates."""
from __future__ import annotations

from copy import deepcopy
from math import hypot

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union


class GenericMinimalAccessCorridorOptimizerV1:
    """Trim ingress to the furthest required stall/aisle access and recover residual."""

    EPS = 1e-7

    def optimize(self, domain_evidence, frontage_evidence, candidates):
        original = deepcopy((domain_evidence, frontage_evidence, candidates))
        domain = Polygon(domain_evidence["polygon"])
        frontage = LineString(frontage_evidence["segment"])
        optimized = [self._optimize_candidate(domain, frontage, item) for item in candidates]
        return {
            "contract": "GenericMinimalAccessCorridorOptimizerV1",
            "candidates": optimized,
            "candidate_count": len(optimized),
            "selected_candidate": None,
            "final_selection_performed": False,
            "input_mutated": original != (domain_evidence, frontage_evidence, candidates),
        }

    def _optimize_candidate(self, domain, frontage, source):
        item = deepcopy(source)
        old_corridor_raw = Polygon(item["vehicle_corridor"])
        old_corridor = old_corridor_raw.intersection(domain)
        aisle = Polygon(item["aisle_manoeuvre"]).intersection(domain)
        stalls = [Polygon(stall["polygon"]) for stall in item["stalls"]]
        core = Polygon(item["temp_core"])
        pedestrian = Polygon(item["public_pedestrian_path"]).intersection(domain)
        entrance = LineString(item["vehicle_entrance"])

        start = entrance.centroid
        raw_points = list(old_corridor_raw.exterior.coords)[:-1]
        far_distance = max(Point(p).distance(frontage) for p in raw_points)
        far_points = [p for p in raw_points if abs(Point(p).distance(frontage) - far_distance) <= self.EPS]
        far = (sum(p[0] for p in far_points) / len(far_points), sum(p[1] for p in far_points) / len(far_points))
        vx, vy = far[0] - start.x, far[1] - start.y
        norm = hypot(vx, vy)
        ux, uy = vx / norm, vy / norm

        access_depths = []
        for stall in stalls:
            shared = stall.boundary.intersection(aisle.boundary.buffer(self.EPS))
            if shared.is_empty:
                shared = stall.boundary.intersection(aisle.buffer(self.EPS))
            if shared.is_empty:
                access_depths.append(float("inf"))
                continue
            access_depths.append(max(
                (point[0] - start.x) * ux + (point[1] - start.y) * uy
                for point in self._points(shared)
            ))

        required_length = max(access_depths) if access_depths else 0.0
        terminal = Point(start.x + ux * required_length, start.y + uy * required_length)
        axis = LineString([start, terminal])
        half_width = entrance.length / 2.0
        trimmed = axis.buffer(half_width, cap_style=2).intersection(old_corridor).intersection(domain)
        if trimmed.geom_type != "Polygon":
            trimmed = max(getattr(trimmed, "geoms", []), key=lambda g: g.area)

        shared_pedestrian = pedestrian.intersection(aisle)
        pedestrian_exclusive = pedestrian.difference(aisle)
        mandatory = unary_union(stalls + [aisle, core, pedestrian_exclusive])
        residual = domain.difference(mandatory)
        components = [residual] if residual.geom_type == "Polygon" else list(getattr(residual, "geoms", []))
        frontage_connected = [p for p in components if p.area > self.EPS and p.buffer(self.EPS).intersection(frontage).length > self.EPS]
        commercial = max(frontage_connected, key=lambda p: (p.area, p.intersection(frontage).length)) if frontage_connected else None

        old_length = max((p[0] - start.x) * ux + (p[1] - start.y) * uy for p in raw_points)
        old_commercial = Polygon(item["direct_commercial_street_frontage_region"])
        no_conflict = all(trimmed.intersection(zone).area <= self.EPS for zone in stalls + [core])
        reachable = all(stall.distance(aisle) <= self.EPS for stall in stalls)
        commercial_clear = commercial is not None and commercial.intersection(mandatory).area <= self.EPS
        gates = {
            "parking_minimum_3": len(stalls) >= 3,
            "corridor_terminates_at_furthest_required_stall_access": abs(axis.length - required_length) <= self.EPS,
            "vehicle_frontage_to_aisle": trimmed.buffer(self.EPS).intersects(frontage) and trimmed.buffer(self.EPS).intersects(aisle),
            "no_stall_or_core_conflict": no_conflict,
            "all_stalls_independently_reachable": reachable,
            "pedestrian_path_preserved": pedestrian.buffer(self.EPS).intersects(frontage),
            "commercial_direct_frontage": commercial is not None and commercial.buffer(self.EPS).intersection(frontage).length > self.EPS,
            "commercial_frontage_connected": commercial is not None and commercial.geom_type == "Polygon",
            "reclaimed_commercial_clear_of_mandatory_zones": commercial_clear,
        }
        item.update({
            "vehicle_corridor_v2_original": self._coords(old_corridor),
            "vehicle_corridor": self._coords(trimmed),
            "vehicle_corridor_axis": self._line_coords(axis),
            "vehicle_corridor_terminal_basis": "furthest_required_stall_to_aisle_access_boundary",
            "public_pedestrian_path": self._coords(pedestrian),
            "pedestrian_exclusive_region": self._geometry_coords(pedestrian_exclusive),
            "pedestrian_shared_with_manoeuvre_region": self._geometry_coords(shared_pedestrian),
            "direct_commercial_street_frontage_region": self._coords(commercial) if commercial else [],
            "commercial_candidate_area_m2": round(commercial.area, 6) if commercial else 0.0,
            "geometric_residual_area_m2": round(residual.area, 6),
            "metrics": {
                "old_vehicle_corridor_area_m2": round(old_corridor_raw.area, 6),
                "old_vehicle_corridor_length_m": round(old_length, 6),
                "new_minimal_vehicle_corridor_area_m2": round(trimmed.area, 6),
                "new_minimal_vehicle_corridor_length_m": round(axis.length, 6),
                "reclaimed_corridor_area_m2": round(old_corridor_raw.difference(trimmed).area, 6),
                "old_commercial_candidate_area_m2": round(old_commercial.area, 6),
                "new_commercial_candidate_area_m2": round(commercial.area, 6) if commercial else 0.0,
                "commercial_area_gain_m2": round((commercial.area if commercial else 0.0) - old_commercial.area, 6),
                "pedestrian_shared_area_m2": round(shared_pedestrian.area, 6),
                "pedestrian_exclusive_area_m2": round(pedestrian_exclusive.area, 6),
            },
            "gates": gates,
            "all_gates_pass": all(gates.values()),
            "blockers": [name for name, passed in gates.items() if not passed],
            "selection_status": "not_selected",
        })
        return item

    @staticmethod
    def _points(geometry):
        if geometry.geom_type == "Point":
            return [geometry.coords[0]]
        if geometry.geom_type in {"LineString", "LinearRing"}:
            return list(geometry.coords)
        points = []
        for part in getattr(geometry, "geoms", []):
            points.extend(GenericMinimalAccessCorridorOptimizerV1._points(part))
        return points

    @staticmethod
    def _coords(poly):
        return [[round(x, 9), round(y, 9)] for x, y in list(poly.exterior.coords)[:-1]]

    @staticmethod
    def _line_coords(line):
        return [[round(x, 9), round(y, 9)] for x, y in line.coords]

    @classmethod
    def _geometry_coords(cls, geometry):
        if geometry.is_empty:
            return []
        if geometry.geom_type == "Polygon":
            return cls._coords(geometry)
        return [cls._coords(part) for part in geometry.geoms if part.geom_type == "Polygon"]
