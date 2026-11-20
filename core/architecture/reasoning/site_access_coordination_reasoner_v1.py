"""Coordinate pedestrian and vehicle site-access candidates without geometry generation."""

import math


class SiteAccessCoordinationReasonerV1:
    VERSION = "1.0"
    TOLERANCE = 1e-7

    def coordinate(self, pedestrian_design, vehicle_contract, requirements=None):
        requirements = requirements if isinstance(requirements, dict) else {}
        pedestrians = self._pedestrians(pedestrian_design)
        vehicles, selected_system = self._vehicles(vehicle_contract)
        pedestrian_required = requirements.get("pedestrian_access_required", True)
        vehicle_required = requirements.get("vehicle_access_required", bool(vehicles))
        separation = self._number(requirements.get("minimum_clear_separation"))
        crossing_policy = requirements.get("crossing_policy")
        protected = self._polygons(requirements.get("protected_zones", []))
        parking = self._polygons(requirements.get("parking_circulation_zones", []))

        result = {
            "type": "site_access_coordination",
            "version": self.VERSION,
            "pedestrian_candidates": pedestrians,
            "vehicle_candidates": vehicles,
            "pairs": [],
            "selected_pair": None,
            "selection_status": "coordination_pending",
            "selection_reason": "complete_coordination_evidence_required",
            "unresolved_evidence": [],
            "source": self.__class__.__name__,
        }

        if not vehicle_required:
            return self._single_mode(result, pedestrians, "pedestrian", pedestrian_required)
        if not pedestrian_required:
            return self._single_mode(result, vehicles, "vehicle", vehicle_required, selected_system)
        if not pedestrians or not vehicles:
            result["unresolved_evidence"] = [
                "pedestrian_candidates" if not pedestrians else "vehicle_candidates"
            ]
            return result

        pairs = []
        for pedestrian in pedestrians:
            for vehicle in vehicles:
                pairs.append(self._pair(
                    pedestrian, vehicle, selected_system, separation,
                    crossing_policy, protected, parking,
                ))
        result["pairs"] = pairs
        feasible = [item for item in pairs if item["coordination_status"] == "feasible"]
        pending = [item for item in pairs if item["coordination_status"] == "coordination_pending"]
        if not feasible:
            result["selection_reason"] = (
                "pair_evidence_incomplete" if pending else "no_compatible_site_access_pair"
            )
            result["unresolved_evidence"] = sorted({
                reason for item in pending for reason in item["rejection_reasons"]
            })
            return result

        best_score = max(item["combined_score"] for item in feasible)
        winners = [item for item in feasible if abs(item["combined_score"] - best_score) <= self.TOLERANCE]
        if len(winners) != 1:
            result.update({
                "selection_status": "pending_tie",
                "selection_reason": "multiple_equal_evidence_coordination_pairs",
                "unresolved_evidence": ["decisive_site_access_coordination_evidence"],
            })
            return result
        winner = winners[0]
        winner["coordination_status"] = "resolved"
        result.update({
            "selected_pair": winner,
            "selection_status": "resolved",
            "selection_reason": "unique_highest_evidence_based_compatible_pair",
            "unresolved_evidence": [],
        })
        return result

    def _pair(self, pedestrian, vehicle, selected_system, separation, crossing_policy,
              protected, parking):
        pid, vid = pedestrian["candidate_id"], vehicle["candidate_id"]
        same_edge = pedestrian.get("access_edge_reference") == vehicle.get("access_edge_reference")
        p_interval, v_interval = pedestrian.get("access_interval"), vehicle.get("entrance_interval")
        reasons = []
        evidence = []
        overlap_status = "not_applicable"
        interval_separation = None
        separation_status = "not_applicable"
        if same_edge:
            if p_interval is None or v_interval is None:
                reasons.append("same_frontage_access_intervals_required")
                overlap_status = "unresolved"
            else:
                overlap = self._segments_overlap(p_interval, v_interval)
                overlap_status = "overlap" if overlap else "clear"
                evidence.append("frontage_interval_geometry_compared")
                if overlap:
                    reasons.append("pedestrian_vehicle_gate_interval_overlap")
                else:
                    interval_separation = self._segment_distance(p_interval, v_interval)
                    if separation is None:
                        separation_status = "unresolved"
                        reasons.append("minimum_clear_separation_required")
                    elif interval_separation + self.TOLERANCE < separation:
                        separation_status = "insufficient"
                        reasons.append("minimum_clear_separation_not_met")
                    else:
                        separation_status = "compliant"
                        evidence.append("minimum_clear_separation_verified")

        approach = pedestrian.get("approach_line")
        driveway = vehicle.get("driveway_corridor")
        ramp_zone = vehicle.get("transition_zone")
        crossing = self._geometry_conflict(approach, driveway)
        crossing_status = "clear"
        if crossing:
            if crossing_policy in ("controlled_crossing", "crossing_permitted"):
                crossing_status = "controlled"
                evidence.append("explicit_controlled_crossing_policy")
            else:
                crossing_status = "conflict"
                reasons.append("uncontrolled_pedestrian_vehicle_crossing")
        elif approach is None or driveway is None:
            crossing_status = "unresolved"
            reasons.append("approach_and_driveway_corridor_geometry_required")
        else:
            evidence.append("pedestrian_approach_driveway_intersection_checked")

        ramp_conflict = self._geometry_conflict(approach, ramp_zone)
        ramp_status = "conflict" if ramp_conflict else "clear"
        if ramp_zone is None and vehicle.get("ramp_geometry_required") is True:
            ramp_status = "unresolved"
            reasons.append("ramp_transition_zone_required")
        elif ramp_conflict:
            reasons.append("pedestrian_approach_intersects_ramp_transition_zone")
        else:
            evidence.append("ramp_transition_conflict_checked")

        parking_conflict = self._line_hits_polygons(approach, parking)
        parking_status = "conflict" if parking_conflict else "clear"
        if parking_conflict:
            reasons.append("pedestrian_approach_intersects_parking_circulation")
        else:
            evidence.append("parking_circulation_conflict_checked")
        protected_conflict = self._line_hits_polygons(approach, protected)
        protected_status = "conflict" if protected_conflict else "clear"
        if protected_conflict:
            reasons.append("pedestrian_approach_intersects_protected_zone")
        else:
            evidence.append("protected_zone_conflict_checked")

        hard = any(reason in reasons for reason in (
            "pedestrian_vehicle_gate_interval_overlap",
            "minimum_clear_separation_not_met",
            "uncontrolled_pedestrian_vehicle_crossing",
            "pedestrian_approach_intersects_ramp_transition_zone",
            "pedestrian_approach_intersects_parking_circulation",
            "pedestrian_approach_intersects_protected_zone",
        ))
        status = "not_feasible" if hard else "coordination_pending" if reasons else "feasible"
        p_score = pedestrian.get("candidate_score")
        v_score = vehicle.get("candidate_score")
        combined = float(p_score) + float(v_score) if self._number(p_score) is not None and self._number(v_score) is not None else None
        if combined is None and status == "feasible":
            status = "coordination_pending"
            reasons.append("comparable_candidate_scores_required")
        return {
            "pair_id": "PAIR-{}-{}".format(pid, vid),
            "pedestrian_candidate_id": pid,
            "vehicle_candidate_id": vid,
            "selected_system": selected_system,
            "same_edge": same_edge,
            "interval_separation": interval_separation,
            "minimum_clear_separation": separation,
            "separation_status": separation_status,
            "overlap_status": overlap_status,
            "crossing_status": crossing_status,
            "driveway_conflict_status": crossing_status,
            "ramp_transition_conflict_status": ramp_status,
            "parking_circulation_conflict_status": parking_status,
            "protected_zone_status": protected_status,
            "combined_score": combined,
            "coordination_status": status,
            "evidence_used": evidence,
            "rejection_reasons": reasons,
        }

    def _single_mode(self, result, candidates, mode, required, selected_system=None):
        if not required:
            result.update({"selection_status": "not_required", "selection_reason": "both_site_access_modes_not_required"})
            return result
        feasible = [item for item in candidates if item.get("geometry_status") in ("candidate", "resolved", "feasible")]
        if not feasible:
            result["unresolved_evidence"] = ["{}_candidate".format(mode)]
            return result
        scores = [self._number(item.get("candidate_score")) for item in feasible]
        if any(score is None for score in scores):
            result["unresolved_evidence"] = ["comparable_candidate_scores_required"]
            return result
        best = max(scores)
        winners = [item for item, score in zip(feasible, scores) if abs(score - best) <= self.TOLERANCE]
        if len(winners) != 1:
            result.update({"selection_status": "pending_tie", "selection_reason": "multiple_equal_{}_candidates".format(mode)})
            return result
        selected = winners[0]
        pair = {
            "pair_id": "{}-ONLY-{}".format(mode.upper(), selected["candidate_id"]),
            "pedestrian_candidate_id": selected["candidate_id"] if mode == "pedestrian" else None,
            "vehicle_candidate_id": selected["candidate_id"] if mode == "vehicle" else None,
            "selected_system": selected_system,
            "coordination_status": "resolved",
            "combined_score": best,
            "evidence_used": ["{}_only_program_requirement".format(mode)],
            "rejection_reasons": [],
        }
        result.update({
            "selected_pair": pair,
            "selection_status": "{}_only_resolved".format(mode),
            "selection_reason": "other_access_mode_explicitly_not_required",
            "unresolved_evidence": [],
        })
        return result

    def _pedestrians(self, contract):
        values = contract.get("candidates", []) if isinstance(contract, dict) else []
        result = []
        for value in values if isinstance(values, list) else []:
            if not isinstance(value, dict) or value.get("geometry_status") not in ("candidate", "resolved"):
                continue
            interval = self._line(value.get("access_segment") or value.get("access_interval"))
            result.append({
                "candidate_id": value.get("candidate_id", value.get("access_id")),
                "access_edge_reference": value.get("access_edge_reference", value.get("parcel_edge_reference")),
                "access_interval": interval,
                "access_point": self._point(value.get("access_point")),
                "approach_line": self._line(value.get("approach_line")),
                "clear_width": value.get("clear_width") or self._segment_length(interval),
                "candidate_score": value.get("candidate_score"),
                "geometry_status": value.get("geometry_status"),
                "source_candidate": value,
            })
        return [item for item in result if item["candidate_id"]]

    def _vehicles(self, contract):
        if not isinstance(contract, dict):
            return [], None
        selected_system = contract.get("selected_system")
        ramp = contract.get("ramp", contract)
        values = ramp.get("access_candidates", []) if isinstance(ramp, dict) else []
        result = []
        for value in values if isinstance(values, list) else []:
            if not isinstance(value, dict) or value.get("status") not in ("feasible", "candidate", "resolved"):
                continue
            interval = self._line(value.get("entrance_interval") or value.get("access_interval") or value.get("access_segment"))
            result.append({
                "candidate_id": value.get("candidate_id", value.get("access_id")),
                "selected_system": selected_system,
                "access_edge_reference": value.get("access_edge_reference", value.get("parcel_edge_id", value.get("edge_index"))),
                "entrance_interval": interval,
                "access_point": self._point(value.get("access_point") or value.get("entrance_center")),
                "driveway_corridor": value.get("driveway_corridor") or value.get("driveway_polygon") or value.get("driveway_centerline"),
                "clear_width": value.get("clear_width") or value.get("minimum_width"),
                "transition_zone": value.get("transition_zone") or value.get("ramp_transition_zone"),
                "ramp_geometry_required": value.get("ramp_geometry_required") is True,
                "candidate_score": value.get("candidate_score", value.get("coordination_score")),
                "geometry_status": value.get("status"),
                "source_candidate": value,
            })
        return [item for item in result if item["candidate_id"]], selected_system

    def _geometry_conflict(self, line, geometry):
        line = self._line(line)
        if line is None or geometry is None:
            return False
        polygon = self._polygon(geometry.get("polygon") if isinstance(geometry, dict) else geometry)
        if polygon:
            return self._line_hits_polygons(line, [polygon])
        other = self._line(geometry.get("centerline") if isinstance(geometry, dict) else geometry)
        return other is not None and self._segments_intersect(line, other)

    def _line_hits_polygons(self, line, polygons):
        line = self._line(line)
        if line is None:
            return False
        return any(
            self._point_in_polygon(line[0], polygon)
            or self._point_in_polygon(line[1], polygon)
            or any(self._segments_intersect(line, edge) for edge in self._edges(polygon))
            for polygon in polygons
        )

    def _segments_overlap(self, first, second):
        if abs(self._cross(first[0], first[1], second[0])) > self.TOLERANCE or abs(self._cross(first[0], first[1], second[1])) > self.TOLERANCE:
            return self._segments_intersect(first, second)
        axis = 0 if abs(first[1][0] - first[0][0]) >= abs(first[1][1] - first[0][1]) else 1
        return min(max(p[axis] for p in first), max(p[axis] for p in second)) > max(min(p[axis] for p in first), min(p[axis] for p in second)) + self.TOLERANCE

    def _segment_distance(self, first, second):
        return min(self._distance(a, b) for a in first for b in second)

    def _segments_intersect(self, first, second):
        a, b, c, d = first[0], first[1], second[0], second[1]
        c1, c2, c3, c4 = self._cross(a, b, c), self._cross(a, b, d), self._cross(c, d, a), self._cross(c, d, b)
        if ((c1 > self.TOLERANCE and c2 < -self.TOLERANCE) or
                (c1 < -self.TOLERANCE and c2 > self.TOLERANCE)) and (
                (c3 > self.TOLERANCE and c4 < -self.TOLERANCE) or
                (c3 < -self.TOLERANCE and c4 > self.TOLERANCE)):
            return True
        return (
            abs(c1) <= self.TOLERANCE and self._point_on_segment(c, first)
            or abs(c2) <= self.TOLERANCE and self._point_on_segment(d, first)
            or abs(c3) <= self.TOLERANCE and self._point_on_segment(a, second)
            or abs(c4) <= self.TOLERANCE and self._point_on_segment(b, second)
        )

    def _point_on_segment(self, point, line):
        return (
            min(line[0][0], line[1][0]) - self.TOLERANCE <= point[0] <= max(line[0][0], line[1][0]) + self.TOLERANCE
            and min(line[0][1], line[1][1]) - self.TOLERANCE <= point[1] <= max(line[0][1], line[1][1]) + self.TOLERANCE
        )

    def _point_in_polygon(self, point, polygon):
        inside = False
        for first, second in self._edges(polygon):
            if (first[1] > point[1]) != (second[1] > point[1]):
                crossing = (second[0] - first[0]) * (point[1] - first[1]) / (second[1] - first[1]) + first[0]
                if point[0] < crossing:
                    inside = not inside
        return inside

    def _polygons(self, values):
        result = []
        for value in values if isinstance(values, list) else []:
            polygon = self._polygon(value.get("polygon") if isinstance(value, dict) else value)
            if polygon:
                result.append(polygon)
        return result

    def _polygon(self, value):
        if not isinstance(value, list) or len(value) < 3:
            return None
        points = [self._point(item) for item in value]
        return points if all(points) else None

    def _line(self, value):
        if isinstance(value, dict):
            value = value.get("centerline") or value.get("line")
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return None
        points = [self._point(item) for item in value]
        return points if all(points) and self._distance(*points) > self.TOLERANCE else None

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

    @staticmethod
    def _distance(first, second):
        return math.hypot(first[0] - second[0], first[1] - second[1])

    def _segment_length(self, line):
        return self._distance(*line) if line else None

    @staticmethod
    def _cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    @staticmethod
    def _edges(polygon):
        return [[polygon[index], polygon[(index + 1) % len(polygon)]] for index in range(len(polygon))]
