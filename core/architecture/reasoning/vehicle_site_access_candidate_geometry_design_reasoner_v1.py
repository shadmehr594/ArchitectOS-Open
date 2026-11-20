"""Architecture-first vehicle site-access candidate geometry design.

Designs evidence-backed frontage, entrance, driveway, and optional ramp
transition candidates. It does not design parking layouts or manoeuvring paths.
"""

import math


class VehicleSiteAccessCandidateGeometryDesignReasonerV1:
    VERSION = "1.0"
    TOLERANCE = 1e-7

    def design(self, site_geometry, feasibility, system_decision):
        site = site_geometry if isinstance(site_geometry, dict) else {}
        feasibility = feasibility if isinstance(feasibility, dict) else {}
        system_decision = system_decision if isinstance(system_decision, dict) else {}
        result = {
            "type": "vehicle_site_access_candidate_geometry_design",
            "version": self.VERSION,
            "selected_vehicle_system": system_decision.get("selected_system"),
            "access_candidates": [],
            "selected_candidate": None,
            "selection_status": "pending",
            "selection_reason": "complete_vehicle_site_geometry_evidence_required",
            "unresolved_evidence": [],
            "source": self.__class__.__name__,
        }
        parcel = self._polygon(site.get("parcel_boundary"))
        conflict_complete = (
            site.get("conflict_inventory_complete") is True
            or site.get("conflict_inventory_status") in ("complete", "resolved_complete")
        )
        ramp = feasibility.get("ramp", {}) if isinstance(feasibility.get("ramp"), dict) else {}
        source_candidates = ramp.get("access_candidates", [])
        source_candidates = source_candidates if isinstance(source_candidates, list) else []
        width = self._number(ramp.get("minimum_width"))
        missing = []
        if parcel is None:
            missing.append("authoritative_parcel_boundary")
        if not conflict_complete:
            missing.append("complete_conflict_inventory")
        if width is None or width <= 0:
            missing.append("vehicle_entrance_clear_width")
        if not source_candidates:
            missing.append("confirmed_vehicle_access_candidate")
        if missing:
            result["unresolved_evidence"] = missing
            return result

        zones = self._zones(site, (
            "conflict_zones", "protected_zones", "pedestrian_reserved_zones",
            "fixed_obstacles", "reserved_site_regions", "setback_zones",
        ))
        buildings = self._building_polygons(site)
        designed = []
        for source in source_candidates:
            if not isinstance(source, dict) or source.get("status") != "feasible":
                continue
            reference = source.get(
                "access_edge_reference", source.get("parcel_edge_id", source.get("edge_index"))
            )
            frontage = self._confirmed_edge(reference, site, parcel)
            target_reference, target_point, target_evidence = self._parking_target(source, site)
            target_region = self._parking_target_region(source, site)
            if frontage is None or (target_point is None and target_region is None):
                designed.append(self._pending_candidate(
                    source, reference,
                    ["confirmed_vehicle_access_frontage"] if frontage is None
                    else ["authoritative_parking_target_or_region"],
                ))
                continue
            intervals = self._feasible_center_intervals(frontage, width, zones)
            if not intervals:
                designed.append(self._pending_candidate(source, reference, ["feasible_frontage_interval"]))
                continue
            if target_point is not None:
                for index, interval in enumerate(intervals):
                    designed.append(self._design_candidate(
                        source, reference, frontage, interval, index, width,
                        target_reference, target_point, target_evidence,
                        parcel, buildings, zones, site, system_decision,
                    ))
            else:
                designed.extend(self._design_ramp_region_candidates(
                    source, reference, frontage, intervals, width,
                    target_reference, target_region, parcel, buildings,
                    zones, site, system_decision,
                ))
        result["access_candidates"] = designed
        valid = [item for item in designed if item.get("geometry_status") == "resolved_candidate"]
        if not valid:
            result["selection_reason"] = "no_resolved_vehicle_site_access_geometry_candidate"
            result["unresolved_evidence"] = sorted({
                value for item in designed for value in item.get("unresolved_evidence", [])
            })
            return result
        best = max(item["candidate_score"] for item in valid)
        winners = [item for item in valid if abs(item["candidate_score"] - best) <= self.TOLERANCE]
        if len(winners) != 1:
            for item in winners:
                item["selection_status"] = "pending_tie"
                item["selection_reason"] = "equal_vehicle_geometry_evidence_and_score"
            result.update({
                "selection_status": "pending_tie",
                "selection_reason": "multiple_equal_vehicle_site_access_geometry_candidates",
                "unresolved_evidence": ["decisive_vehicle_site_geometry_evidence"],
            })
            return result
        winner = winners[0]
        winner["selection_status"] = "selected_for_coordination"
        winner["selection_reason"] = "unique_highest_evidence_based_geometry_candidate"
        result.update({
            "selected_candidate": winner,
            "selection_status": "candidate_selected_for_coordination",
            "selection_reason": "unique_best_vehicle_geometry_candidate_available",
            "unresolved_evidence": [],
        })
        return result

    def _design_candidate(self, source, reference, frontage, center_interval, index,
                          width, target_reference, target, target_evidence,
                          parcel, buildings, zones, site, system_decision):
        projected, parameter = self._projection(target, frontage)
        center_parameter = min(max(parameter, center_interval[0]), center_interval[1])
        access_point = self._at(frontage, center_parameter)
        half_parameter = width / (2.0 * self._length(frontage))
        entrance = [
            self._at(frontage, center_parameter - half_parameter),
            self._at(frontage, center_parameter + half_parameter),
        ]
        centerline = [access_point, target]
        corridor = self._corridor(access_point, target, width)
        candidate_id = "VEH-{}-I{}".format(reference, index + 1)
        contract = dict(source)
        contract.update({
            "candidate_id": candidate_id,
            "source": self.__class__.__name__,
            "source_evidence": [
                "confirmed_vehicle_access_frontage", "explicit_vehicle_clear_width",
                target_evidence, "feasible_frontage_interval",
                "parking_target_projection_to_frontage",
            ],
            "access_edge_reference": reference,
            "frontage_segment": frontage,
            "feasible_frontage_interval": [
                self._at(frontage, center_interval[0]), self._at(frontage, center_interval[1])
            ],
            "entrance_interval": entrance,
            "entrance_width": width,
            "access_point": access_point,
            "parking_target_reference": target_reference,
            "parking_target_point": target,
            "driveway_centerline": centerline,
            "driveway_corridor": corridor,
            "driveway_width": width,
            "clear_width": width,
            "selected_vehicle_system": system_decision.get("selected_system"),
            "ramp_required": source.get("ramp_geometry_required") is True,
            "ramp_transition_zone": None,
            "transition_zone": None,
            "protected_zone_status": "pending",
            "conflict_status": "pending",
            "parcel_containment_status": "pending",
            "driveway_building_conflict_status": "pending",
            "candidate_score": None,
            "geometry_status": "pending",
            "selection_status": "candidate",
            "selection_reason": None,
            "unresolved_evidence": [],
        })
        if corridor is None:
            return self._reject(contract, "parking_target_equals_access_point")
        if not self._polygon_inside(corridor, parcel):
            return self._reject(contract, "driveway_corridor_leaves_parcel", "parcel_containment_status")
        contract["parcel_containment_status"] = "resolved_inside_parcel"
        if self._polygon_hits_any(corridor, zones):
            return self._reject(contract, "driveway_corridor_intersects_conflict_zone", "conflict_status")
        contract["protected_zone_status"] = "clear"
        contract["conflict_status"] = "clear"
        building_entry_allowed = source.get("building_entry_allowed") is True
        if self._polygon_hits_any(corridor, buildings) and not building_entry_allowed:
            return self._reject(contract, "driveway_corridor_intersects_building", "driveway_building_conflict_status")
        contract["driveway_building_conflict_status"] = (
            "authorized_target_entry" if building_entry_allowed else "clear"
        )
        if source.get("ramp_geometry_required") is True:
            transition = self._ramp_transition(contract, source, frontage, parcel, zones)
            if transition is None:
                contract["unresolved_evidence"].append("complete_ramp_transition_dimensions")
                contract["selection_reason"] = "ramp_transition_evidence_incomplete_or_conflicting"
                return contract
            contract["ramp_transition_zone"] = transition
            contract["transition_zone"] = transition
            contract["source_evidence"].append("explicit_ramp_transition_dimensions")
        path_length = self._length(centerline)
        available_center_length = (
            center_interval[1] - center_interval[0]
        ) * self._length(frontage)
        contract["candidate_score"] = 1000.0 + available_center_length - path_length
        contract["geometry_status"] = "resolved_candidate"
        contract["selection_reason"] = "frontage_driveway_and_target_geometry_valid"
        contract["source_evidence"].extend([
            "driveway_corridor_inside_parcel", "explicit_conflict_inventory_checked",
            "building_collision_checked", "parking_target_connectivity",
            "frontage_flexibility_and_path_length_evaluated",
        ])
        return contract

    def _ramp_transition(self, contract, source, frontage, parcel, zones):
        length = self._number(source.get("ramp_transition_length"))
        width = self._number(source.get("ramp_transition_width"))
        if length is None or width is None or length <= 0 or width <= 0:
            return None
        start, target = contract["access_point"], contract["parking_target_point"]
        total = self._distance(start, target)
        if total + self.TOLERANCE < length:
            return None
        direction = [(target[0] - start[0]) / total, (target[1] - start[1]) / total]
        end = [start[0] + direction[0] * length, start[1] + direction[1] * length]
        polygon = self._corridor(start, end, width)
        if polygon is None or not self._polygon_inside(polygon, parcel) or self._polygon_hits_any(polygon, zones):
            return None
        return {"polygon": polygon, "length": length, "width": width, "source": "explicit_ramp_transition_dimensions"}

    def _feasible_center_intervals(self, frontage, width, zones):
        length = self._length(frontage)
        if width > length + self.TOLERANCE:
            return []
        half = width / (2.0 * length)
        intervals = [[half, 1.0 - half]]
        for polygon in zones:
            blocked = self._edge_polygon_interval(frontage, polygon)
            if blocked is None:
                continue
            expanded = [max(half, blocked[0] - half), min(1.0 - half, blocked[1] + half)]
            intervals = self._subtract(intervals, expanded)
        return [item for item in intervals if item[1] + self.TOLERANCE >= item[0]]

    def _parking_target(self, source, site):
        point = self._point(source.get("parking_target_point") or source.get("target_point"))
        reference = source.get("parking_target_reference", source.get("target_level"))
        evidence = source.get("parking_target_source")
        if point is not None and evidence:
            return reference, point, str(evidence)
        targets = site.get("parking_access_points")
        value = targets.get(reference) if isinstance(targets, dict) else None
        if isinstance(value, dict):
            point = self._point(value.get("point"))
            evidence = value.get("source") or value.get("evidence")
        else:
            point = self._point(value)
            evidence = site.get("parking_access_points_source")
        return (reference, point, str(evidence)) if point is not None and evidence else (reference, None, None)

    def _parking_target_region(self, source, site):
        value = source.get("parking_target_region")
        evidence = source.get("parking_target_source")
        if value is None:
            regions = site.get("parking_target_regions", {})
            reference = source.get("parking_target_reference", source.get("target_level"))
            value = regions.get(reference) if isinstance(regions, dict) else None
            evidence = evidence or site.get("parking_target_regions_source")
        if isinstance(value, dict):
            evidence = value.get("source") or evidence
            value = value.get("polygon") or value.get("points")
        polygon = self._polygon(value)
        return polygon if polygon is not None and evidence else None

    def _design_ramp_region_candidates(self, source, reference, frontage, intervals,
                                       width, target_reference, target_region,
                                       parcel, buildings, zones, site, system_decision):
        """Create only geometrically critical placements for a straight ramp.

        The ends of feasible centre intervals are topology events, not fixed
        frontage samples.  They remain separate candidates; an equal pair is
        deliberately left tied.
        """
        run = self._number(source.get("required_run"))
        if source.get("ramp_geometry_required") is not True or run is None or run <= 0:
            return [self._pending_candidate(source, reference, ["authoritative_parking_target_point"])]
        normal = self._inward_normal(frontage, parcel)
        if normal is None:
            return [self._pending_candidate(source, reference, ["unique_inward_frontage_normal"])]
        ramp_interval = self._straight_corridor_parameter_interval(
            frontage, parcel, normal, run, width
        )
        if ramp_interval is None:
            return [self._pending_candidate(source, reference, ["ramp_corridor_inside_parcel"])]
        clipped_intervals = []
        for interval in intervals:
            lo = max(interval[0], ramp_interval[0])
            hi = min(interval[1], ramp_interval[1])
            if hi + self.TOLERANCE >= lo:
                clipped_intervals.append([lo, hi])
        values = []
        for interval_index, interval in enumerate(clipped_intervals):
            parameters = [interval[0]] if abs(interval[1]-interval[0]) <= self.TOLERANCE else [interval[0], interval[1]]
            for boundary_index, parameter in enumerate(parameters):
                access = self._at(frontage, parameter)
                target = [access[0] + normal[0]*run, access[1] + normal[1]*run]
                if not self._point_inside(target, target_region):
                    continue
                candidate = self._design_candidate(
                    source, reference, frontage, [parameter, parameter],
                    interval_index*2+boundary_index, width, target_reference,
                    target, "authoritative_parking_target_region_and_required_ramp_run",
                    parcel, buildings, zones, site, system_decision,
                )
                if candidate.get("geometry_status") == "resolved_candidate":
                    candidate["parking_target_region"] = target_region
                    candidate["source_evidence"] = [
                        "ramp_exit_derived_from_required_run_and_inward_normal"
                        if item == "parking_target_projection_to_frontage" else item
                        for item in candidate["source_evidence"]
                    ]
                    candidate["source_evidence"].append("feasible_interval_boundary_event")
                values.append(candidate)
        return values or [self._pending_candidate(source, reference, ["ramp_exit_inside_parking_target_region"])]

    def _straight_corridor_parameter_interval(self, frontage, parcel, normal, run, width):
        """Clip the moving straight-ramp corridor against a convex parcel.

        Every corridor vertex is affine in the frontage parameter, so each
        parcel half-plane produces an exact parameter bound.  This avoids a
        hidden sample grid or midpoint preference.
        """
        a, b = frontage
        dx, dy = b[0]-a[0], b[1]-a[1]
        length = self._length(frontage)
        if length <= self.TOLERANCE:
            return None
        tx, ty = dx/length, dy/length
        half = float(width)/2.0
        bases = [
            [a[0]+tx*half, a[1]+ty*half],
            [a[0]-tx*half, a[1]-ty*half],
            [a[0]+normal[0]*run+tx*half, a[1]+normal[1]*run+ty*half],
            [a[0]+normal[0]*run-tx*half, a[1]+normal[1]*run-ty*half],
        ]
        area2 = sum(p[0]*q[1]-q[0]*p[1] for p, q in zip(parcel, parcel[1:]+parcel[:1]))
        sign = 1.0 if area2 >= 0 else -1.0
        lo, hi = 0.0, 1.0
        for p, q in zip(parcel, parcel[1:]+parcel[:1]):
            ex, ey = q[0]-p[0], q[1]-p[1]
            for base in bases:
                constant = sign*(ex*(base[1]-p[1])-ey*(base[0]-p[0]))
                coefficient = sign*(ex*dy-ey*dx)
                if abs(coefficient) <= self.TOLERANCE:
                    if constant < -self.TOLERANCE:
                        return None
                    continue
                bound = -constant/coefficient
                if coefficient > 0:
                    lo = max(lo, bound)
                else:
                    hi = min(hi, bound)
                if hi + self.TOLERANCE < lo:
                    return None
        return [max(0.0, lo), min(1.0, hi)]

    def _inward_normal(self, frontage, parcel):
        a, b = frontage
        length = self._length(frontage)
        if length <= self.TOLERANCE:
            return None
        midpoint = [(a[0]+b[0])/2.0, (a[1]+b[1])/2.0]
        normals = [[-(b[1]-a[1])/length, (b[0]-a[0])/length],
                   [(b[1]-a[1])/length, -(b[0]-a[0])/length]]
        inside = []
        probe = min(0.05, length*0.005)
        for normal in normals:
            point = [midpoint[0]+normal[0]*probe, midpoint[1]+normal[1]*probe]
            if self._point_inside(point, parcel):
                inside.append(normal)
        return inside[0] if len(inside) == 1 else None

    @staticmethod
    def _point_inside(point, polygon):
        inside = False
        x, y = point
        for a, b in zip(polygon, polygon[1:] + polygon[:1]):
            if ((a[1] > y) != (b[1] > y)):
                cross_x = (b[0]-a[0])*(y-a[1])/(b[1]-a[1]) + a[0]
                if x < cross_x:
                    inside = not inside
        return inside

    def _confirmed_edge(self, reference, site, parcel):
        edges = site.get("parcel_edges", [])
        for index, edge in enumerate(edges if isinstance(edges, list) else []):
            if not isinstance(edge, dict) or edge.get("confirmed") is not True:
                continue
            if reference not in (edge.get("id"), edge.get("access_id"), edge.get("edge_index", index)):
                continue
            line = self._line([edge.get("start") or edge.get("edge_start"), edge.get("end") or edge.get("edge_end")])
            if line:
                return line
            edge_index = edge.get("edge_index", index)
            if isinstance(edge_index, int) and 0 <= edge_index < len(parcel):
                return [parcel[edge_index], parcel[(edge_index + 1) % len(parcel)]]
        return None

    def _building_polygons(self, site):
        values = site.get("building_footprints", [])
        if not values and site.get("building_footprint") is not None:
            values = [site.get("building_footprint")]
        return self._polygon_values(values)

    def _zones(self, site, keys):
        result = []
        for key in keys:
            result.extend(self._polygon_values(site.get(key, [])))
        return result

    def _polygon_values(self, values):
        if isinstance(values, dict):
            values = values.get("polygons", [values])
        if not isinstance(values, list):
            return []
        if self._polygon(values):
            return [self._polygon(values)]
        result = []
        for value in values:
            polygon = self._polygon(value.get("polygon", value.get("points")) if isinstance(value, dict) else value)
            if polygon:
                result.append(polygon)
        return result

    def _edge_polygon_interval(self, edge, polygon):
        values = []
        for point in polygon:
            if self._on_segment(point, edge):
                values.append(self._projection(point, edge)[1])
        for polygon_edge in self._edges(polygon):
            point = self._intersection(edge, polygon_edge)
            if point is not None:
                values.append(self._projection(point, edge)[1])
        for point in edge:
            if self._point_in_polygon(point, polygon):
                values.append(self._projection(point, edge)[1])
        if not values:
            return None
        return [max(0.0, min(values)), min(1.0, max(values))]

    @staticmethod
    def _subtract(intervals, cut):
        result = []
        for start, end in intervals:
            if cut[1] <= start or cut[0] >= end:
                result.append([start, end])
            else:
                if cut[0] > start:
                    result.append([start, cut[0]])
                if cut[1] < end:
                    result.append([cut[1], end])
        return result

    def _corridor(self, start, end, width):
        length = self._distance(start, end)
        if length <= self.TOLERANCE:
            return None
        nx = -(end[1] - start[1]) / length * width / 2.0
        ny = (end[0] - start[0]) / length * width / 2.0
        return [[start[0] + nx, start[1] + ny], [end[0] + nx, end[1] + ny],
                [end[0] - nx, end[1] - ny], [start[0] - nx, start[1] - ny]]

    def _polygon_inside(self, inner, outer):
        return all(self._point_in_or_on(point, outer) for point in inner)

    def _polygon_hits_any(self, polygon, others):
        return any(self._polygons_intersect(polygon, other) for other in others)

    def _polygons_intersect(self, first, second):
        if any(self._point_in_polygon(point, second) for point in first):
            return True
        if any(self._point_in_polygon(point, first) for point in second):
            return True
        return any(self._intersection(a, b) is not None for a in self._edges(first) for b in self._edges(second))

    def _point_in_or_on(self, point, polygon):
        return self._point_in_polygon(point, polygon) or any(
            self._on_segment(point, edge) for edge in self._edges(polygon)
        )

    def _point_in_polygon(self, point, polygon):
        inside = False
        for first, second in self._edges(polygon):
            if (first[1] > point[1]) != (second[1] > point[1]):
                x = (second[0] - first[0]) * (point[1] - first[1]) / (second[1] - first[1]) + first[0]
                if point[0] < x:
                    inside = not inside
        return inside

    def _intersection(self, first, second):
        a, b, c, d = first[0], first[1], second[0], second[1]
        rx, ry, sx, sy = b[0] - a[0], b[1] - a[1], d[0] - c[0], d[1] - c[1]
        denominator = rx * sy - ry * sx
        if abs(denominator) <= self.TOLERANCE:
            return None
        qx, qy = c[0] - a[0], c[1] - a[1]
        t, u = (qx * sy - qy * sx) / denominator, (qx * ry - qy * rx) / denominator
        return self._at(first, t) if -self.TOLERANCE <= t <= 1 + self.TOLERANCE and -self.TOLERANCE <= u <= 1 + self.TOLERANCE else None

    def _on_segment(self, point, line):
        return abs(self._cross(line[0], line[1], point)) <= self.TOLERANCE and (
            min(line[0][0], line[1][0]) - self.TOLERANCE <= point[0] <= max(line[0][0], line[1][0]) + self.TOLERANCE
            and min(line[0][1], line[1][1]) - self.TOLERANCE <= point[1] <= max(line[0][1], line[1][1]) + self.TOLERANCE
        )

    def _projection(self, point, line):
        dx, dy = line[1][0] - line[0][0], line[1][1] - line[0][1]
        parameter = ((point[0] - line[0][0]) * dx + (point[1] - line[0][1]) * dy) / (dx * dx + dy * dy)
        return self._at(line, parameter), parameter

    @staticmethod
    def _at(line, parameter):
        return [line[0][0] + parameter * (line[1][0] - line[0][0]), line[0][1] + parameter * (line[1][1] - line[0][1])]

    @staticmethod
    def _cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    @staticmethod
    def _edges(polygon):
        return [[polygon[index], polygon[(index + 1) % len(polygon)]] for index in range(len(polygon))]

    def _line(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return None
        points = [self._point(item) for item in value]
        return points if all(point is not None for point in points) and self._distance(*points) > self.TOLERANCE else None

    def _polygon(self, value):
        if not isinstance(value, list) or len(value) < 3:
            return None
        points = [self._point(item) for item in value]
        return points if all(point is not None for point in points) else None

    @staticmethod
    def _point(value):
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            try:
                return [float(value[0]), float(value[1])]
            except (TypeError, ValueError):
                pass
        return None

    @staticmethod
    def _number(value):
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _length(self, line):
        return self._distance(line[0], line[1])

    @staticmethod
    def _distance(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def _pending_candidate(self, source, reference, missing):
        result = dict(source)
        result.update({
            "candidate_id": "VEH-{}-PENDING".format(reference),
            "source": self.__class__.__name__,
            "access_edge_reference": reference,
            "geometry_status": "pending",
            "selection_status": "pending",
            "selection_reason": "required_vehicle_site_geometry_evidence_missing",
            "unresolved_evidence": missing,
        })
        return result

    @staticmethod
    def _reject(contract, reason, status_field=None):
        contract["geometry_status"] = "not_feasible"
        contract["selection_status"] = "rejected"
        contract["selection_reason"] = reason
        contract["unresolved_evidence"] = []
        if status_field:
            contract[status_field] = "conflict"
        return contract
