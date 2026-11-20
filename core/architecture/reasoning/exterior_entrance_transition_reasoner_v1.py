import math


class ExteriorEntranceTransitionReasonerV1:
    """Resolve exterior entrance levels while failing closed on placement."""

    VERSION = "1.0"

    def resolve(self, architectural_intent, vertical_section=None):
        intent = architectural_intent if isinstance(architectural_intent, dict) else {}
        datum = intent.get("site_datum") if isinstance(intent.get("site_datum"), dict) else {}
        finished = intent.get("finished_floor") if isinstance(intent.get("finished_floor"), dict) else {}
        transition = intent.get("entrance_transition") if isinstance(intent.get("entrance_transition"), dict) else {}
        platform_input = transition.get("platform") if isinstance(transition.get("platform"), dict) else {}
        rules = intent.get("exterior_step_rules") if isinstance(intent.get("exterior_step_rules"), dict) else {}
        site_z = self._number(datum.get("elevation"))
        floor_z = self._number(finished.get("elevation"))
        evidence = [item for item in (datum.get("source_evidence"), finished.get("source_evidence"), transition.get("source_evidence")) if item]
        build_up = finished.get("floor_build_up")
        if not isinstance(build_up, dict):
            build_up = {"status": "unresolved", "source": "no_floor_build_up_evidence"}
        result = {"version": self.VERSION, "site_datum": dict(datum),
                  "finished_floor": dict(finished), "floor_build_up": dict(build_up),
                  "entrance_platform": {}, "exterior_steps": {}, "source_evidence": evidence}
        result["site_datum"].setdefault("status", "resolved" if site_z is not None else "unresolved")
        result["finished_floor"].setdefault("status", "resolved" if floor_z is not None else "unresolved")

        platform_z = self._number(platform_input.get("elevation"))
        if platform_z is None:
            platform_z = floor_z
        polygon = platform_input.get("polygon")
        platform_ready = self._polygon(polygon)
        result["entrance_platform"] = {
            "type": "exterior_platform", "elevation": platform_z,
            "connected_to": platform_input.get("connected_to", "main_entrance"),
            "polygon": polygon if platform_ready else None,
            "geometry_status": "resolved" if platform_ready else "pending",
            "geometry_generation_allowed": platform_ready,
            "source_evidence": platform_input.get("source_evidence", evidence),
        }
        if site_z is None or floor_z is None:
            result["status"] = "unresolved_level_evidence"
            result["exterior_steps"] = self._pending(site_z, floor_z, "missing_site_or_finished_floor_elevation", evidence)
            return result
        rise = abs(floor_z - site_z)
        if math.isclose(rise, 0.0, abs_tol=1e-9):
            result["status"] = "resolved_no_transition_required"
            result["exterior_steps"] = {**self._pending(site_z, floor_z, "no_level_difference", evidence),
                                         "required": False, "total_rise": 0.0,
                                         "riser_count": 0, "riser_height": 0.0,
                                         "geometry_status": "not_required"}
            return result

        count = self._positive_int(transition.get("riser_count"))
        explicit_height = self._positive(transition.get("riser_height"))
        maximum_riser = self._positive(rules.get("maximum_riser_height"))
        source = None
        if count:
            source = "user_explicit_riser_count"
        elif explicit_height and math.isclose(rise / explicit_height, round(rise / explicit_height), abs_tol=1e-7):
            count = int(round(rise / explicit_height))
            source = "user_explicit_riser_height"
        elif maximum_riser:
            count = int(math.ceil(rise / maximum_riser - 1e-12))
            source = "applicable_exterior_step_rule"
        else:
            result["status"] = "unresolved_step_rule"
            result["exterior_steps"] = self._pending(site_z, floor_z, "missing_riser_rule", evidence)
            result["exterior_steps"]["total_rise"] = rise
            return result

        tread_depth = self._positive(transition.get("tread_depth", rules.get("minimum_tread_depth")))
        tread_count = self._positive_int(transition.get("tread_count"))
        entrance = transition.get("entrance_geometry") if isinstance(transition.get("entrance_geometry"), dict) else {}
        start_point, end_point = entrance.get("start_point"), entrance.get("end_point")
        direction, width = entrance.get("direction"), self._positive(entrance.get("clear_width"))
        ready = bool(self._point(start_point) and self._point(end_point) and direction and width and tread_depth and tread_count and platform_ready)
        result["status"] = "resolved" if ready else "resolved_semantics"
        result["exterior_steps"] = {
            "type": "entrance_steps", "required": True, "start_z": site_z,
            "end_z": floor_z, "total_rise": rise, "riser_count": count,
            "riser_height": rise / count, "riser_resolution_source": source,
            "tread_count": tread_count, "tread_depth": tread_depth,
            "start_point": start_point if self._point(start_point) else None,
            "end_point": end_point if self._point(end_point) else None,
            "direction": direction, "clear_width": width,
            "connected_to": transition.get("connected_to", "main_entrance"),
            "geometry_status": "resolved" if ready else "pending",
            "geometry_generation_allowed": ready,
            "geometry_resolution_reason": "complete_authoritative_entrance_geometry" if ready else "entrance_position_platform_direction_width_or_tread_evidence_incomplete",
            "source_evidence": evidence,
        }
        return result

    @staticmethod
    def _pending(start_z, end_z, reason, evidence):
        return {"type": "entrance_steps", "required": None, "start_z": start_z,
                "end_z": end_z, "total_rise": None, "riser_count": None,
                "riser_height": None, "tread_count": None, "tread_depth": None,
                "start_point": None, "end_point": None, "direction": None,
                "connected_to": "main_entrance", "geometry_status": "pending",
                "geometry_generation_allowed": False,
                "geometry_resolution_reason": reason, "source_evidence": evidence}

    @staticmethod
    def _number(value):
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    @classmethod
    def _positive(cls, value):
        value = cls._number(value)
        return value if value is not None and value > 0 else None

    @classmethod
    def _positive_int(cls, value):
        value = cls._positive(value)
        return int(value) if value is not None and float(value).is_integer() else None

    @staticmethod
    def _point(value):
        return isinstance(value, (list, tuple)) and len(value) >= 2 and all(isinstance(v, (int, float)) for v in value[:2])

    @classmethod
    def _polygon(cls, value):
        return isinstance(value, list) and len(value) >= 3 and all(cls._point(point) for point in value)
