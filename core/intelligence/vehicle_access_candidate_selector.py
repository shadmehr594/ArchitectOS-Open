"""
Architecture-first vehicle access candidate selector.

Consumes verified feasibility evidence and resolves a site access edge only
when architectural evidence produces a unique result. No geometry is created.
"""


class VehicleAccessCandidateSelector:

    VERSION = "1.0"

    def _pending(self, system_decision, scores, reason):
        return {
            "engine": "VEHICLE_ACCESS_CANDIDATE_SELECTOR",
            "version": self.VERSION,
            "status": "access_candidate_selection_pending",
            "selected_system": system_decision.get("selected_system"),
            "selected_access_candidate": None,
            "selected_access_id": None,
            "candidate_scores": scores,
            "evidence_used": [],
            "selection_reason": reason,
            "geometry_generation_allowed": False,
            "ramp_geometry_allowed": False,
            "driveway_geometry_allowed": False,
            "program_space_generation_allowed": False,
            "source_system_decision": system_decision,
        }

    def select(self, feasibility_result, system_decision, building_context=None):
        feasibility_result = feasibility_result or {}
        system_decision = system_decision or {}
        building_context = building_context or {}

        selected_system = system_decision.get("selected_system")
        coordination = building_context.get("site_access_coordination")
        coordinated_vehicle_id = None
        if isinstance(coordination, dict):
            if coordination.get("selection_status") not in ("resolved", "vehicle_only_resolved"):
                return self._pending(
                    system_decision,
                    [],
                    "pedestrian_vehicle_site_access_coordination_not_resolved",
                )
            selected_pair = coordination.get("selected_pair", {}) or {}
            coordinated_vehicle_id = selected_pair.get("vehicle_candidate_id")
            if not coordinated_vehicle_id:
                return self._pending(
                    system_decision,
                    [],
                    "coordinated_vehicle_access_candidate_missing",
                )

        # Preserve the existing system-level car-lift comparison. Access-edge
        # scoring must not override a verified car-lift decision.
        if selected_system == "car_lift" and system_decision.get("status") == "resolved":
            result = dict(system_decision)
            result.update(
                {
                    "engine": "VEHICLE_ACCESS_CANDIDATE_SELECTOR",
                    "version": self.VERSION,
                    "selected_system": "car_lift",
                    "candidate_scores": [],
                    "evidence_used": ["resolved_car_lift_system_preserved"],
                    "selection_reason": system_decision.get("selection_reason"),
                    "ramp_geometry_allowed": False,
                    "driveway_geometry_allowed": False,
                    "source_system_decision": system_decision,
                }
            )
            return result

        if system_decision.get("status") == "comparative_decision_pending":
            return self._pending(
                system_decision,
                [],
                "vehicle_ramp_and_car_lift_comparison_is_not_resolved",
            )

        ramp = feasibility_result.get("ramp", {}) or {}
        candidates = ramp.get("access_candidates", [])
        if not isinstance(candidates, list):
            candidates = []
        if coordinated_vehicle_id is not None:
            candidates = [
                candidate for candidate in candidates
                if isinstance(candidate, dict)
                and coordinated_vehicle_id in {
                    candidate.get("access_id"), candidate.get("candidate_id")
                }
            ]

        candidate_scores = []
        eligible_scores = []

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue

            disqualifiers = []
            evidence_used = []

            if candidate.get("status") != "feasible":
                disqualifiers.append("candidate_feasibility_not_verified")

            required_fields = (
                "access_id",
                "access_elevation",
                "target_elevation",
                "delta_z",
                "absolute_level_difference",
                "access_mode",
            )
            for field in required_fields:
                if candidate.get(field) is None:
                    disqualifiers.append(f"missing_{field}")

            edge_status = candidate.get("access_edge_status")
            source = candidate.get("source")
            edge_confirmed = (
                edge_status in ("confirmed", "verified", "user_confirmed")
                or (edge_status is None and source == "user_explicit")
            )
            if not edge_confirmed:
                disqualifiers.append("access_edge_not_confirmed")
            else:
                evidence_used.append("verified_vehicle_access_edge")

            score = 0.0
            absolute_difference = candidate.get("absolute_level_difference")
            required_run = candidate.get("required_run")

            if candidate.get("access_mode") == "direct_at_grade" and absolute_difference == 0:
                score += 100.0
                evidence_used.extend(
                    [
                        "direct_at_grade",
                        "zero_vertical_difference",
                        "parking_target_same_elevation",
                        "no_ramp_footprint_required",
                    ]
                )
            elif candidate.get("ramp_geometry_required") is True:
                if required_run is None:
                    disqualifiers.append("required_ramp_run_unresolved")
                if candidate.get("site_fit") is not True:
                    disqualifiers.append("ramp_site_fit_not_verified")
                if isinstance(absolute_difference, (int, float)):
                    score -= float(absolute_difference)
                    evidence_used.append("vertical_difference_penalty")
                if isinstance(required_run, (int, float)):
                    score -= float(required_run) / 100.0
                    evidence_used.append("ramp_run_footprint_penalty")

            score_record = {
                "access_id": candidate.get("access_id"),
                "score": score,
                "eligible": not disqualifiers,
                "evidence_used": evidence_used,
                "disqualifiers": disqualifiers,
                "candidate": candidate,
            }
            candidate_scores.append(score_record)
            if not disqualifiers:
                eligible_scores.append(score_record)

        if not eligible_scores:
            return self._pending(
                system_decision,
                candidate_scores,
                "no_access_candidate_has_complete_verified_evidence",
            )

        best_score = max(item["score"] for item in eligible_scores)
        winners = [item for item in eligible_scores if item["score"] == best_score]

        if len(winners) != 1:
            return self._pending(
                system_decision,
                candidate_scores,
                "equal_architectural_access_scores_without_decisive_evidence",
            )

        winner = winners[0]
        selected = winner["candidate"]
        direct_at_grade = selected.get("access_mode") == "direct_at_grade"
        ramp_required = selected.get("ramp_geometry_required") is True

        return {
            "engine": "VEHICLE_ACCESS_CANDIDATE_SELECTOR",
            "version": self.VERSION,
            "status": "resolved",
            "selected_system": "vehicle_ramp",
            "selected_access_candidate": selected,
            "selected_access_id": selected.get("access_id"),
            "candidate_scores": candidate_scores,
            "evidence_used": winner["evidence_used"],
            "selection_reason": (
                "direct_at_grade_parking_access_preferred_over_ramp"
                if direct_at_grade
                else "single_verified_ramp_access_candidate"
            ),
            "geometry_generation_allowed": True,
            "ramp_geometry_allowed": ramp_required,
            "driveway_geometry_allowed": True,
            "program_space_generation_allowed": True,
            "source_system_decision": system_decision,
            "site_access_coordination": coordination,
        }
