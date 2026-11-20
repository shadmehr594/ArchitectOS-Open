"""Fail-closed architectural parking arrival and initial maneuvering evidence."""

from __future__ import annotations

from math import cos, hypot, isfinite, pi, sin


class ParkingArrivalManeuveringResolverV1:
    VERSION = "1.0"
    EPS = 1e-7

    def resolve(self, driveway, vehicle_opening, floor_geometry, walls, protected_zones, requirement):
        level = driveway.get("served_level") if isinstance(driveway, dict) else None
        base = {
            "served_level": level, "entry_interface": None, "arrival_point": None,
            "arrival_direction": None, "arrival_zone": None,
            "minimum_turning_radius": None, "maneuvering_envelope": None,
            "aisle_candidate": None, "required_clear_width": None,
            "wall_clearance": "pending", "obstacle_clearance": "pending",
            "geometry_status": "pending", "unresolved_evidence": [],
            "source": "parking_arrival_maneuvering_resolver_v1",
        }
        if not isinstance(requirement, dict) or requirement.get("evidence_status") not in ("authoritative", "resolved"):
            base["unresolved_evidence"].append("authoritative_parking_arrival_requirement")
            return base
        radius, clear_width = requirement.get("minimum_turning_radius"), requirement.get("required_clear_width")
        if not self._positive(radius): base["unresolved_evidence"].append("minimum_turning_radius")
        if not self._positive(clear_width): base["unresolved_evidence"].append("required_clear_width")
        line = driveway.get("centerline") if isinstance(driveway, dict) else None
        if not isinstance(line, list) or len(line) < 2:
            base["unresolved_evidence"].append("resolved_driveway_centerline")
        if not isinstance(vehicle_opening, dict) or vehicle_opening.get("geometry_status") != "resolved":
            base["unresolved_evidence"].append("resolved_vehicle_opening")
        if base["unresolved_evidence"]: return base
        start, end = self._point(line[-2]), self._point(line[-1])
        opening_center = self._point(vehicle_opening.get("opening_center"))
        if not all((start, end, opening_center)) or hypot(end[0]-start[0], end[1]-start[1]) <= self.EPS:
            base["unresolved_evidence"].append("valid_arrival_and_opening_geometry")
            return base
        if self._distance_to_segment(opening_center, self._point(line[0]), end) > self.EPS:
            base["unresolved_evidence"].append("driveway_passes_resolved_vehicle_opening")
            return base
        length = hypot(end[0]-start[0], end[1]-start[1])
        direction = [(end[0]-start[0])/length, (end[1]-start[1])/length]
        envelope = [[end[0]+float(radius)*cos(2*pi*i/24), end[1]+float(radius)*sin(2*pi*i/24)] for i in range(24)]
        floor = self._floor(level, floor_geometry)
        footprint = self._points((floor.get("footprint") or {}).get("points") if floor else None)
        if len(footprint) < 3:
            base["unresolved_evidence"].append("served_level_usable_footprint")
            return base
        floor_bbox, envelope_bbox = self._bbox(footprint), self._bbox(envelope)
        if not self._contains(floor_bbox, envelope_bbox):
            return base | {"arrival_point": end, "arrival_direction": direction,
                           "minimum_turning_radius": float(radius), "maneuvering_envelope": envelope,
                           "geometry_status": "not_feasible", "wall_clearance": "failed",
                           "unresolved_evidence": ["turning_envelope_outside_usable_footprint"]}
        conflicts = []
        for zone in protected_zones if isinstance(protected_zones, list) else []:
            if isinstance(zone, dict) and zone.get("type") == "vehicle_vertical_clearance":
                continue
            points = self._points(zone.get("polygon") if isinstance(zone, dict) else zone)
            if points and self._intersects(envelope_bbox, self._bbox(points)):
                conflicts.append(zone.get("type", zone.get("id", "protected_zone")) if isinstance(zone, dict) else "protected_zone")
        if conflicts:
            return base | {"arrival_point": end, "arrival_direction": direction,
                           "minimum_turning_radius": float(radius), "maneuvering_envelope": envelope,
                           "geometry_status": "not_feasible", "obstacle_clearance": "failed",
                           "conflicts": conflicts, "unresolved_evidence": ["maneuvering_envelope_conflict"]}
        for wall in walls if isinstance(walls, list) else []:
            if not isinstance(wall, dict) or wall.get("floor") != level: continue
            a, b = self._point(wall.get("start")), self._point(wall.get("end"))
            if a and b and self._distance_to_segment(end, a, b) + self.EPS < float(radius):
                return base | {"arrival_point": end, "arrival_direction": direction,
                               "minimum_turning_radius": float(radius), "maneuvering_envelope": envelope,
                               "geometry_status": "not_feasible", "wall_clearance": "failed",
                               "unresolved_evidence": ["arrival_turning_radius_intersects_wall"]}
        zone = {"type": "parking_arrival_zone", "polygon": envelope, "served_level": level,
                "protected_zone": True, "source": "resolved_turning_radius"}
        return base | {
            "entry_interface": vehicle_opening.get("opening_id"), "arrival_point": end,
            "arrival_direction": direction, "arrival_zone": zone,
            "minimum_turning_radius": float(radius), "maneuvering_envelope": envelope,
            "aisle_candidate": {"origin": end, "direction": direction, "geometry_status": "candidate"},
            "required_clear_width": float(clear_width), "wall_clearance": "clear",
            "obstacle_clearance": "clear", "geometry_status": "resolved", "unresolved_evidence": [],
        }

    def _floor(self, level, values):
        matches=[v for v in values or [] if isinstance(v,dict) and v.get("floor")==level]
        return matches[0] if len(matches)==1 else None
    @staticmethod
    def _point(v): return [float(v[0]),float(v[1])] if isinstance(v,(list,tuple)) and len(v)>=2 else None
    @staticmethod
    def _points(v): return [[float(p[0]),float(p[1])] for p in v or [] if isinstance(p,(list,tuple)) and len(p)>=2]
    @staticmethod
    def _bbox(p): return [min(x[0] for x in p),min(x[1] for x in p),max(x[0] for x in p),max(x[1] for x in p)]
    @staticmethod
    def _contains(a,b): return b[0]>=a[0] and b[1]>=a[1] and b[2]<=a[2] and b[3]<=a[3]
    @staticmethod
    def _intersects(a,b): return not(a[2]<=b[0] or a[0]>=b[2] or a[3]<=b[1] or a[1]>=b[3])
    @staticmethod
    def _positive(v): return isinstance(v,(int,float)) and isfinite(float(v)) and float(v)>0
    @classmethod
    def _distance_to_segment(cls,p,a,b):
        dx,dy=b[0]-a[0],b[1]-a[1]; den=dx*dx+dy*dy
        if den<=cls.EPS:return hypot(p[0]-a[0],p[1]-a[1])
        t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den))
        return hypot(p[0]-(a[0]+t*dx),p[1]-(a[1]+t*dy))
