"""Architecture-first pedestrian site access design.

This reasoner designs candidates from project geometry.  It deliberately does
not validate or publish an access; that remains the responsibility of
PedestrianAccessGeometryResolverV1.
"""

import math


class PedestrianSiteAccessDesignReasonerV1:
    VERSION = "1.0"
    TOLERANCE = 1e-7

    def design(self, site_geometry, floor_geometry, spaces, physical_walls=None):
        site = site_geometry if isinstance(site_geometry, dict) else {}
        result = self._pending("required_project_geometry_incomplete")
        parcel = self._polygon(site.get("parcel_boundary"))
        entrance = self._unique_entrance_space(spaces)
        building = self._unique_floor_footprint(
            floor_geometry, entrance.get("floor") if entrance else None
        )
        width = self._positive_number(
            site.get("pedestrian_access_width", self._preference(site, "access_width"))
        )
        road_edges = self._confirmed_access_edges(site, parcel)
        zones = self._zones(site, ("protected_zones", "pedestrian_conflict_zones"))
        vehicle_zones = self._zones(
            site, ("vehicle_access_zones", "vehicle_circulation_zones", "parking_access_zones")
        )

        result["input_evidence"] = {
            "parcel_boundary": parcel is not None,
            "confirmed_access_edges": [item[0] for item in road_edges],
            "building_footprint": building is not None,
            "entrance_space_footprint": entrance is not None,
            "pedestrian_access_width": width,
            "setbacks_supplied": "setbacks" in site,
            "protected_zones_supplied": "protected_zones" in site,
            "vehicle_zones_supplied": any(key in site for key in (
                "vehicle_access_zones", "vehicle_circulation_zones", "parking_access_zones"
            )),
        }
        missing = []
        for value, name in ((parcel, "parcel_boundary"), (building, "building_footprint"),
                            (entrance, "entrance_space_footprint"), (width, "pedestrian_access_width")):
            if value is None:
                missing.append(name)
        if not road_edges:
            missing.append("confirmed_road_access_edge")
        if not any(key in site for key in ("setback_zones", "setbacks")):
            missing.append("setback_evidence")
        if not any(key in site for key in ("protected_zones", "pedestrian_conflict_zones")):
            missing.append("pedestrian_conflict_zone_inventory")
        if not any(key in site for key in (
            "vehicle_access_zones", "vehicle_circulation_zones", "parking_access_zones"
        )):
            missing.append("vehicle_access_and_circulation_inventory")
        if missing:
            result["unresolved_evidence"] = missing
            return result

        target_edges = self._shared_facade_edges(entrance["polygon"], building)
        if not target_edges:
            result["selection_reason"] = "entrance_space_has_no_proven_building_facade_edge"
            result["unresolved_evidence"] = ["entrance_space_building_facade_topology"]
            return result

        candidates = []
        for edge_reference, edge in road_edges:
            intervals = self._feasible_intervals(edge, width, site, zones, vehicle_zones)
            for interval_index, interval in enumerate(intervals):
                for target_index, target in enumerate(target_edges):
                    samples = self._candidate_samples(edge, interval, target, site)
                    for sample_index, (access_point, target_point, route) in enumerate(samples):
                        candidates.append(self._candidate(
                            edge_reference, edge, interval, interval_index, target,
                            target_index, entrance, parcel, building, width, zones, vehicle_zones,
                            access_point, target_point, route, sample_index,
                        ))

        result["candidates"] = candidates
        feasible = [item for item in candidates if item["geometry_status"] == "candidate"]
        if not feasible:
            result["selection_reason"] = "no_feasible_straight_pedestrian_approach"
            result["unresolved_evidence"] = ["feasible_access_interval_and_straight_approach"]
            return result

        best_score = max(item["candidate_score"] for item in feasible)
        best = [item for item in feasible if abs(item["candidate_score"] - best_score) <= self.TOLERANCE]
        if len(best) != 1:
            for item in best:
                item["selection_status"] = "pending_tie"
                item["selection_reason"] = "equal_architectural_evidence_and_score"
            result.update({
                "selection_status": "pending_tie",
                "selection_reason": "multiple_equal_evidence_pedestrian_access_candidates",
                "geometry_status": "pending",
                "selected_access": None,
                "unresolved_evidence": ["unique_architectural_preference_or_constraint"],
            })
            return result

        selected = best[0]
        selected["selection_status"] = "selected"
        selected["selection_reason"] = "unique_highest_evidence_based_candidate_score"
        for item in feasible:
            if item is not selected:
                item["selection_status"] = "not_selected"
                item["selection_reason"] = "lower_evidence_based_candidate_score"
        published = dict(selected)
        published["access_id"] = published["candidate_id"]
        published["parcel_edge_reference"] = published["access_edge_reference"]
        published["source_evidence"] = list(published["evidence_used"])
        published["geometry_status"] = "candidate"
        result.update({
            "selection_status": "selected_unique_candidate",
            "selection_reason": "one_candidate_has_unique_best_architectural_evidence",
            "geometry_status": "candidate",
            "selected_access": published,
            "unresolved_evidence": [],
        })
        return result

    def _candidate(self, edge_reference, edge, interval, interval_index, target,
                   target_index, entrance, parcel, building, width, zones, vehicle_zones,
                   access_point, target_point, route, sample_index):
        candidate_id = "PED-{}-I{}-T{}-C{}".format(edge_reference, interval_index + 1, target_index + 1, sample_index + 1)
        _, parameter = self._projection_on_line(access_point, edge)
        base = {
            "candidate_id": candidate_id,
            "parcel_edge_id": edge_reference,
            "access_edge_reference": edge_reference,
            "access_point": None,
            "access_segment": None,
            "approach_start": None,
            "approach_end": target_point,
            "approach_line": None,
            "approach_length": None,
            "building_target_edge": {"start": list(target[0]), "end": list(target[1])},
            "entrance_space_target": entrance["id"],
            "feasible_interval": self._interval_geometry(edge, interval),
            "clearance_status": "resolved",
            "conflict_status": "pending",
            "vehicle_conflict_status": "pending",
            "setback_status": "resolved",
            "evidence_used": [
                "authoritative_parcel_boundary", "confirmed_road_access_edge",
                "entrance_space_shared_building_facade", "required_clear_access_width",
                "entrance_space_centroid_axis_projected_to_shared_facade",
            ],
            "candidate_score": None,
            "selection_status": "candidate_not_selected",
            "selection_reason": None,
            "geometry_status": "not_feasible",
            "source": self.__class__.__name__,
        }
        if parameter < interval[0] - self.TOLERANCE or parameter > interval[1] + self.TOLERANCE:
            base["selection_reason"] = "target_projection_outside_feasible_access_interval"
            return base
        access_segment = self._centered_segment(edge, access_point, width)
        approach = route
        if not self._segment_inside_polygon(approach, parcel):
            base["selection_reason"] = "straight_approach_leaves_parcel"
            return base
        if self._segment_hits_polygons(approach, zones):
            base.update({"conflict_status": "conflict", "selection_reason": "protected_zone_blocks_straight_approach"})
            return base
        if self._segment_hits_polygons(approach, vehicle_zones):
            base.update({"conflict_status": "clear", "vehicle_conflict_status": "conflict",
                         "selection_reason": "vehicle_circulation_blocks_straight_approach"})
            return base
        if self._segment_enters_building_before_target(approach, building):
            base["selection_reason"] = "approach_intersects_building_before_target_facade"
            return base
        length = self._distance(access_point, target_point)
        preference_score = self._preference_score(access_point, target, edge_reference, base)
        # All terms are evidence-backed: valid direct arrival and route length.
        score = 1000.0 - length + preference_score
        base.update({
            "access_point": access_point,
            "access_segment": access_segment,
            "approach_start": access_point,
            "approach_line": approach,
            "approach_length": length,
            "conflict_status": "clear",
            "vehicle_conflict_status": "clear",
            "candidate_score": score,
            "geometry_status": "candidate",
        })
        base["evidence_used"].extend([
            "straight_segment_inside_parcel", "protected_zones_clear",
            "vehicle_access_and_circulation_clear", "building_intersection_only_at_target",
            "route_length_evaluation",
        ])
        return base

    def _candidate_samples(self, edge, interval, target, site):
        """Sample real door positions and regenerate a route for each pair."""
        if not site.get("generate_multiple_candidates"):
            target_point, _ = self._projection_on_line(
                self._polygon_centroid(self._unique_entrance_space(site.get("_spaces", []))["polygon"]), target
            ) if site.get("_spaces") else (self._midpoint(target), .5)
            access_point, _ = self._projection_on_line(target_point, edge)
            return [(access_point, target_point, [access_point, target_point])]
        fractions=(.15,.35,.5,.65,.85)
        access_points=[self._at(edge,interval[0]+(interval[1]-interval[0])*f) for f in fractions]
        target_points=[self._at(target,f) for f in (.2,.5,.8)]
        samples=[]
        for access in access_points:
            for destination in target_points:
                direct=[access,destination]
                elbows=([access,[access[0],destination[1]],destination],
                        [access,[destination[0],access[1]],destination])
                routes=[direct]+[r for r in elbows if self._distance(r[0],r[1])>self.TOLERANCE and self._distance(r[1],r[2])>self.TOLERANCE]
                route=min(routes,key=lambda r:sum(self._distance(a,b) for a,b in zip(r,r[1:])))
                samples.append((access,destination,route))
        unique=[]
        for sample in samples:
            signature=tuple(round(v,7) for p in sample[2] for v in p)
            if signature not in {tuple(round(v,7) for p in x[2] for v in p) for x in unique}:unique.append(sample)
        return unique

    def _feasible_intervals(self, edge, width, site, zones, vehicle_zones):
        length = self._distance(edge[0], edge[1])
        if length + self.TOLERANCE < width:
            return []
        intervals = [[width / (2.0 * length), 1.0 - width / (2.0 * length)]]
        blocked = zones + vehicle_zones + self._zones(site, ("setback_zones", "setbacks"))
        for polygon in blocked:
            cut = self._edge_polygon_interval(edge, polygon)
            if cut is not None:
                intervals = self._subtract_interval(intervals, cut)
        return [item for item in intervals if (item[1] - item[0]) * length + self.TOLERANCE >= width]

    def _confirmed_access_edges(self, site, parcel):
        if parcel is None:
            return []
        references = []
        raw = site.get("confirmed_road_access_edges", [])
        if not isinstance(raw, list):
            raw = []
        references.extend(raw)
        single = site.get("access_edge_index")
        if single is not None:
            references.append(single)
        edges = site.get("parcel_edges", []) if isinstance(site.get("parcel_edges"), list) else []
        for edge in edges:
            if not isinstance(edge, dict) or not edge.get("confirmed"):
                continue
            if edge.get("relation") not in ("road", "access", "road_access", None):
                continue
            references.append(edge.get("id", edge.get("edge_index")))
        preference = site.get("pedestrian_access_preference", {})
        required_reference = preference.get("access_edge_reference") if isinstance(preference, dict) else None
        if required_reference is not None:
            references = [reference for reference in references if reference == required_reference]
        result = []
        for reference in references:
            edge = self._edge_by_reference(reference, edges, parcel)
            if edge is not None and all(reference != item[0] for item in result):
                result.append((reference, edge))
        return result

    def _edge_by_reference(self, reference, edges, parcel):
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            if reference in (edge.get("id"), edge.get("edge_index")):
                line = self._line([edge.get("start"), edge.get("end")])
                if line:
                    return line
        if isinstance(reference, int) and 0 <= reference < len(parcel):
            return [parcel[reference], parcel[(reference + 1) % len(parcel)]]
        return None

    def _shared_facade_edges(self, entrance, building):
        result = []
        for first in self._edges(entrance):
            for second in self._edges(building):
                overlap = self._collinear_overlap(first, second)
                if overlap and self._distance(overlap[0], overlap[1]) > self.TOLERANCE:
                    if not any(self._same_segment(overlap, existing) for existing in result):
                        result.append(overlap)
        return result

    def _unique_floor_footprint(self, floor_geometry, entrance_floor=None):
        found = []
        for item in floor_geometry if isinstance(floor_geometry, list) else []:
            if not isinstance(item, dict):
                continue
            floor_alias = lambda value: "F1" if value in ("F1", "ground", "ground_floor") else value
            if entrance_floor is not None and floor_alias(item.get("floor")) != floor_alias(entrance_floor):
                continue
            footprint = item.get("footprint") or item.get("parcel_envelope") or {}
            polygon = self._polygon(footprint.get("points") if isinstance(footprint, dict) else None)
            if polygon is not None:
                found.append(polygon)
        return found[0] if len(found) == 1 else None

    def _unique_entrance_space(self, spaces):
        found = []
        for index, space in enumerate(spaces if isinstance(spaces, list) else []):
            if not isinstance(space, dict) or space.get("name") not in ("entrance", "main_entrance"):
                continue
            footprint = space.get("footprint", {})
            polygon = self._polygon(footprint.get("points") if isinstance(footprint, dict) else None)
            if polygon:
                found.append({
                    "id": space.get("id", space.get("name", "entrance-{}".format(index))),
                    "floor": space.get("floor"),
                    "polygon": polygon,
                })
        return found[0] if len(found) == 1 else None

    def _preference(self, site, key):
        value = site.get("pedestrian_access_preference", {})
        return value.get(key) if isinstance(value, dict) else None

    def _preference_score(self, access_point, target, edge_reference, candidate):
        # Reserved for explicit, measurable user preferences. V1 intentionally
        # adds no implicit orientation or coordinate preference.
        return 0.0

    def _zones(self, site, keys):
        result = []
        for key in keys:
            values = site.get(key, [])
            if not isinstance(values, list):
                continue
            for value in values:
                polygon = self._polygon(value.get("polygon") if isinstance(value, dict) else value)
                if polygon:
                    result.append(polygon)
        return result

    def _edge_polygon_interval(self, edge, polygon):
        values = []
        for point in polygon:
            projected, parameter = self._projection_on_line(point, edge)
            if self._distance(projected, point) <= self.TOLERANCE and -self.TOLERANCE <= parameter <= 1 + self.TOLERANCE:
                values.append(max(0.0, min(1.0, parameter)))
        for polygon_edge in self._edges(polygon):
            intersection = self._segment_intersection(edge, polygon_edge)
            if intersection is not None:
                values.append(self._parameter(intersection, edge))
        if not values:
            midpoint = self._midpoint(edge)
            if self._point_in_polygon(midpoint, polygon):
                return [0.0, 1.0]
            return None
        return [max(0.0, min(values)), min(1.0, max(values))]

    @staticmethod
    def _subtract_interval(intervals, cut):
        result = []
        for start, end in intervals:
            if cut[1] <= start or cut[0] >= end:
                result.append([start, end])
                continue
            if cut[0] > start:
                result.append([start, cut[0]])
            if cut[1] < end:
                result.append([cut[1], end])
        return result

    def _interval_geometry(self, edge, interval):
        return [self._at(edge, interval[0]), self._at(edge, interval[1])]

    def _centered_segment(self, edge, center, width):
        length = self._distance(edge[0], edge[1])
        unit = [(edge[1][0] - edge[0][0]) / length, (edge[1][1] - edge[0][1]) / length]
        return [[center[0] - unit[0] * width / 2, center[1] - unit[1] * width / 2],
                [center[0] + unit[0] * width / 2, center[1] + unit[1] * width / 2]]

    def _segment_inside_polygon(self, line, polygon):
        return all(self._point_in_or_on(self._at(line, index / 20.0), polygon) for index in range(21))

    def _segment_hits_polygons(self, line, polygons):
        return any(self._line_intersects_polygon_interior(line, polygon) for polygon in polygons)

    def _line_intersects_polygon_interior(self, line, polygon):
        if any(self._point_in_polygon(self._at(line, index / 20.0), polygon) for index in range(1, 20)):
            return True
        return any(self._segment_intersection(line, edge) is not None for edge in self._edges(polygon))

    def _segment_enters_building_before_target(self, line, building):
        return any(self._point_in_polygon(self._at(line, index / 20.0), building) for index in range(20))

    def _collinear_overlap(self, first, second):
        if abs(self._cross(first[0], first[1], second[0])) > self.TOLERANCE or abs(self._cross(first[0], first[1], second[1])) > self.TOLERANCE:
            return None
        use_x = abs(first[1][0] - first[0][0]) >= abs(first[1][1] - first[0][1])
        axis = 0 if use_x else 1
        ordered = sorted([first[0], first[1]], key=lambda point: point[axis])
        low = max(min(point[axis] for point in first), min(point[axis] for point in second))
        high = min(max(point[axis] for point in first), max(point[axis] for point in second))
        if high <= low + self.TOLERANCE:
            return None
        denominator = ordered[1][axis] - ordered[0][axis]
        return [self._at(ordered, (low - ordered[0][axis]) / denominator),
                self._at(ordered, (high - ordered[0][axis]) / denominator)]

    def _segment_intersection(self, first, second):
        a, b, c, d = first[0], first[1], second[0], second[1]
        rx, ry, sx, sy = b[0] - a[0], b[1] - a[1], d[0] - c[0], d[1] - c[1]
        denominator = rx * sy - ry * sx
        if abs(denominator) <= self.TOLERANCE:
            return None
        qx, qy = c[0] - a[0], c[1] - a[1]
        t, u = (qx * sy - qy * sx) / denominator, (qx * ry - qy * rx) / denominator
        return self._at(first, t) if -self.TOLERANCE <= t <= 1 + self.TOLERANCE and -self.TOLERANCE <= u <= 1 + self.TOLERANCE else None

    def _projection_on_line(self, point, line):
        dx, dy = line[1][0] - line[0][0], line[1][1] - line[0][1]
        parameter = ((point[0] - line[0][0]) * dx + (point[1] - line[0][1]) * dy) / (dx * dx + dy * dy)
        return self._at(line, parameter), parameter

    def _parameter(self, point, line):
        return self._projection_on_line(point, line)[1]

    def _point_in_or_on(self, point, polygon):
        return self._point_in_polygon(point, polygon) or any(abs(self._cross(edge[0], edge[1], point)) <= self.TOLERANCE and
            min(edge[0][0], edge[1][0]) - self.TOLERANCE <= point[0] <= max(edge[0][0], edge[1][0]) + self.TOLERANCE and
            min(edge[0][1], edge[1][1]) - self.TOLERANCE <= point[1] <= max(edge[0][1], edge[1][1]) + self.TOLERANCE for edge in self._edges(polygon))

    def _point_in_polygon(self, point, polygon):
        inside = False
        for edge in self._edges(polygon):
            if (edge[0][1] > point[1]) != (edge[1][1] > point[1]):
                crossing = (edge[1][0] - edge[0][0]) * (point[1] - edge[0][1]) / (edge[1][1] - edge[0][1]) + edge[0][0]
                if point[0] < crossing:
                    inside = not inside
        return inside

    @staticmethod
    def _cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def _same_segment(self, first, second):
        return (self._distance(first[0], second[0]) <= self.TOLERANCE and self._distance(first[1], second[1]) <= self.TOLERANCE) or (self._distance(first[0], second[1]) <= self.TOLERANCE and self._distance(first[1], second[0]) <= self.TOLERANCE)

    @staticmethod
    def _at(line, parameter):
        return [line[0][0] + parameter * (line[1][0] - line[0][0]), line[0][1] + parameter * (line[1][1] - line[0][1])]

    @staticmethod
    def _midpoint(line):
        return [(line[0][0] + line[1][0]) / 2.0, (line[0][1] + line[1][1]) / 2.0]

    def _polygon_centroid(self, polygon):
        twice_area = 0.0
        x_sum = 0.0
        y_sum = 0.0
        for first, second in self._edges(polygon):
            cross = first[0] * second[1] - second[0] * first[1]
            twice_area += cross
            x_sum += (first[0] + second[0]) * cross
            y_sum += (first[1] + second[1]) * cross
        if abs(twice_area) <= self.TOLERANCE:
            return [
                sum(point[0] for point in polygon) / len(polygon),
                sum(point[1] for point in polygon) / len(polygon),
            ]
        return [x_sum / (3.0 * twice_area), y_sum / (3.0 * twice_area)]

    @staticmethod
    def _distance(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    @staticmethod
    def _edges(polygon):
        return [[polygon[index], polygon[(index + 1) % len(polygon)]] for index in range(len(polygon))]

    def _polygon(self, value):
        if not isinstance(value, list) or len(value) < 3:
            return None
        points = [self._point(point) for point in value]
        return points if all(point is not None for point in points) else None

    def _line(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return None
        points = [self._point(point) for point in value]
        return points if all(point is not None for point in points) and self._distance(*points) > self.TOLERANCE else None

    @staticmethod
    def _point(value):
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            try:
                return [float(value[0]), float(value[1])]
            except (TypeError, ValueError):
                pass
        return None

    @staticmethod
    def _positive_number(value):
        try:
            value = float(value)
            return value if value > 0 else None
        except (TypeError, ValueError):
            return None

    def _pending(self, reason):
        return {
            "type": "pedestrian_access_design",
            "version": self.VERSION,
            "candidates": [],
            "selected_access": None,
            "selection_status": "pending",
            "selection_reason": reason,
            "geometry_status": "pending",
            "input_evidence": {},
            "unresolved_evidence": [],
            "source": self.__class__.__name__,
        }
