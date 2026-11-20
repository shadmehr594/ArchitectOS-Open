"""Fail-closed physical stair geometry resolved from architectural evidence."""

from __future__ import annotations

import math
from typing import Any


class ArchitecturalStairGeometryResolverV1:
    VERSION = "1.0"

    def resolve(self, element: dict[str, Any]) -> dict[str, Any]:
        base = {
            "stair_id": element.get("stair_id") or element.get("id") or element.get("name"),
            "stair_type": (element.get("parameters") or {}).get("stair_type"),
            "served_levels": list(element.get("served_levels") or []),
            "geometry_status": "unresolved",
            "source_evidence": {
                "levels": element.get("span_source"),
                "rules": "vertical_core_sizing.parameters",
                "placement": "authoritative_vertical_core_zone",
            },
        }
        parameters = element.get("parameters") if isinstance(element.get("parameters"), dict) else {}
        spans = element.get("served_level_spans") or []
        missing = []
        if len(spans) < 2:
            missing.append("two_authoritative_served_levels")
        start_level = spans[0] if spans else {}
        end_level = spans[-1] if spans else {}
        start_z = start_level.get("bottom")
        end_z = end_level.get("bottom")
        if not self._numeric(start_z) or not self._numeric(end_z):
            missing.append("authoritative_start_end_elevation")
        clear_width = parameters.get("clear_width")
        maximum_riser = parameters.get("maximum_riser", parameters.get("riser"))
        tread_depth = parameters.get("minimum_tread", parameters.get("tread"))
        flight_count = parameters.get("flight_count")
        headroom = parameters.get("headroom")
        for name, value in (
            ("clear_width", clear_width), ("maximum_riser", maximum_riser),
            ("minimum_tread", tread_depth), ("flight_count", flight_count),
            ("headroom", headroom),
        ):
            if not self._positive(value):
                missing.append(name)
        zone = self._zone(element, parameters)
        if not zone:
            missing.append("authoritative_protected_core_footprint")
        if parameters.get("conflict_evidence_complete") is not True:
            missing.append("complete_conflict_evidence")
        if missing:
            return base | {
                "geometry_status": "insufficient_evidence",
                "placement_status": "pending",
                "missing_evidence": missing,
                "protected_zone": zone,
            }

        start_z, end_z = float(start_z), float(end_z)
        total_rise = abs(end_z - start_z)
        if total_rise <= 0:
            return base | {
                "geometry_status": "invalid_vertical_span",
                "placement_status": "pending",
                "start_z": start_z, "end_z": end_z, "total_rise": total_rise,
            }
        maximum_riser = float(maximum_riser)
        riser_count = int(math.ceil(total_rise / maximum_riser - 1e-12))
        riser_height = total_rise / riser_count
        flight_count = int(flight_count)
        if flight_count not in (1, 2) or riser_count < flight_count:
            return base | {
                "geometry_status": "unsupported_flight_layout",
                "placement_status": "pending",
                "riser_count": riser_count,
            }
        landing_required = bool(parameters.get("landing_required", flight_count > 1))
        landing_depth = parameters.get("landing_depth")
        if flight_count > 1 and (not landing_required or not self._positive(landing_depth)):
            return base | {
                "geometry_status": "insufficient_evidence",
                "placement_status": "pending",
                "missing_evidence": ["landing_geometry"],
            }

        polygon = self._points(zone)
        min_x, max_x, min_y, max_y = self._bounds(polygon)
        along_x = (max_x - min_x) >= (max_y - min_y)
        length = (max_x - min_x) if along_x else (max_y - min_y)
        breadth = (max_y - min_y) if along_x else (max_x - min_x)
        risers_per_flight = self._split(riser_count, flight_count)
        treads_per_flight = [max(count - 1, 0) for count in risers_per_flight]
        required_length = max(treads_per_flight) * float(tread_depth)
        if flight_count == 2:
            required_length += float(landing_depth)
        required_breadth = float(clear_width) * flight_count
        if required_length > length + 1e-9 or required_breadth > breadth + 1e-9:
            return base | {
                "geometry_status": "core_footprint_insufficient",
                "placement_status": "failed_closed",
                "required_footprint": {"length": required_length, "width": required_breadth},
                "available_footprint": {"length": length, "width": breadth},
                "protected_zone": zone,
            }

        def world(u: float, v: float) -> list[float]:
            return [min_x + u, min_y + v] if along_x else [min_x + v, min_y + u]

        sign = 1.0 if end_z >= start_z else -1.0
        flights = []
        landings = []
        current_z = start_z
        walking_line = []
        for index, (flight_risers, flight_treads) in enumerate(zip(risers_per_flight, treads_per_flight)):
            run = flight_treads * float(tread_depth)
            if flight_count == 1 or index == 0:
                start_u, end_u = 0.0, run
                v0, v1 = index * float(clear_width), (index + 1) * float(clear_width)
            else:
                start_u = required_length - float(landing_depth)
                end_u = start_u - run
                v0, v1 = float(clear_width), 2.0 * float(clear_width)
            flight_start_z = current_z
            flight_end_z = current_z + sign * flight_risers * riser_height
            center_v = (v0 + v1) / 2.0
            centerline = [world(start_u, center_v) + [flight_start_z], world(end_u, center_v) + [flight_end_z]]
            flight_polygon = [world(start_u, v0), world(end_u, v0), world(end_u, v1), world(start_u, v1)]
            tread_lines = []
            for tread_index in range(1, flight_treads + 1):
                ratio = tread_index / max(flight_treads, 1)
                u = start_u + (end_u - start_u) * ratio
                tread_lines.append([world(u, v0), world(u, v1)])
            flights.append({
                "flight_id": f"{base['stair_id']}_flight_{index + 1}",
                "start_point": centerline[0][:2], "end_point": centerline[-1][:2],
                "start_z": flight_start_z, "end_z": flight_end_z,
                "riser_count": flight_risers, "tread_count": flight_treads,
                "riser_height": riser_height, "tread_depth": float(tread_depth),
                "width": float(clear_width), "centerline": centerline,
                "polygon": flight_polygon,
                "direction": "up" if sign > 0 else "down",
                "tread_lines": tread_lines,
                "source_evidence": base["source_evidence"],
            })
            if not walking_line:
                walking_line.append(centerline[0])
            walking_line.append(centerline[-1])
            current_z = flight_end_z
            if index == 0 and flight_count == 2:
                landing_u0 = required_length - float(landing_depth)
                landing_polygon = [
                    world(landing_u0, 0.0), world(required_length, 0.0),
                    world(required_length, 2.0 * float(clear_width)),
                    world(landing_u0, 2.0 * float(clear_width)),
                ]
                landing = {
                    "landing_id": f"{base['stair_id']}_landing_1",
                    "z": current_z, "polygon": landing_polygon,
                    "width": 2.0 * float(clear_width), "depth": float(landing_depth),
                    "geometry_status": "resolved",
                    "source_evidence": base["source_evidence"],
                }
                landings.append(landing)
                landing_center = world(required_length - float(landing_depth) / 2.0, float(clear_width)) + [current_z]
                walking_line.append(landing_center)

        stair_polygon = [world(0.0, 0.0), world(required_length, 0.0),
                         world(required_length, required_breadth), world(0.0, required_breadth)]
        conflicts = self._conflicts(stair_polygon, parameters.get("conflict_zones") or [])
        if conflicts:
            return base | {
                "geometry_status": "placement_conflict",
                "placement_status": "failed_closed",
                "conflicts": conflicts,
                "protected_zone": zone,
            }
        slab_opening = {
            "opening_id": f"{base['stair_id']}_stairwell_opening",
            "type": "stairwell_slab_opening",
            "host_level": end_level.get("name"),
            "z": end_z,
            "polygon": stair_polygon,
            "served_levels": list(base["served_levels"]),
            "geometry_status": "resolved",
            "source_evidence": "resolved_stair_penetrates_served_level_slab",
        }
        return base | {
            "type": "stair_geometry",
            "start_level": start_level.get("name"), "end_level": end_level.get("name"),
            "start_point": flights[0]["start_point"], "end_point": flights[-1]["end_point"],
            "start_z": start_z, "end_z": end_z, "total_rise": total_rise,
            "clear_width": float(clear_width), "riser_count": riser_count,
            "riser_height": riser_height, "tread_count": sum(treads_per_flight),
            "tread_depth": float(tread_depth), "flight_count": flight_count,
            "flights": flights, "landings": landings,
            "walking_line": walking_line, "centerline": walking_line,
            "direction": "up" if sign > 0 else "down", "headroom": float(headroom),
            "stairwell_opening_required": True, "slab_opening": slab_opening,
            "protected_zone": zone, "polygon": stair_polygon,
            "geometry_status": "resolved", "placement_status": "resolved",
        }

    def _zone(self, element: dict[str, Any], parameters: dict[str, Any]) -> Any:
        location = element.get("location_intent") if isinstance(element.get("location_intent"), dict) else {}
        return (location.get("protected_zone") or location.get("footprint") or location.get("polygon")
                or parameters.get("protected_zone") or parameters.get("core_footprint"))

    def _points(self, value: Any) -> list[list[float]]:
        if isinstance(value, dict):
            value = value.get("points") or value.get("polygon")
        if not isinstance(value, list):
            return []
        return [[float(point[0]), float(point[1])] for point in value if isinstance(point, (list, tuple)) and len(point) >= 2]

    def _bounds(self, points: list[list[float]]) -> tuple[float, float, float, float]:
        xs, ys = [point[0] for point in points], [point[1] for point in points]
        return min(xs), max(xs), min(ys), max(ys)

    def _split(self, count: int, parts: int) -> list[int]:
        quotient, remainder = divmod(count, parts)
        return [quotient + (1 if index < remainder else 0) for index in range(parts)]

    def _conflicts(self, polygon: list[list[float]], zones: list[Any]) -> list[Any]:
        a = self._bounds(polygon)
        found = []
        for zone in zones:
            points = self._points(zone)
            if not points:
                continue
            b = self._bounds(points)
            if a[0] < b[1] and a[1] > b[0] and a[2] < b[3] and a[3] > b[2]:
                found.append(zone.get("id") if isinstance(zone, dict) else zone)
        return found

    def _numeric(self, value: Any) -> bool:
        return isinstance(value, (int, float)) and math.isfinite(float(value))

    def _positive(self, value: Any) -> bool:
        return self._numeric(value) and float(value) > 0
