"""Fail-closed, non-spatial stair-footprint sizing from explicit evidence."""
from copy import deepcopy
import math


class VerticalCirculationFootprintSizingV1:
    REQUIRED = ("clear_width", "maximum_riser", "minimum_tread", "flight_count")

    def resolve(self, demand_profile):
        profile = deepcopy(demand_profile)
        audits = []
        for fn in profile.get("functions", []):
            if fn.get("function") != "stair":
                continue
            sizing = fn.setdefault("spatial_sizing", {})
            evidence = fn.get("operational_requirements") or {}
            result = self._derive(evidence)
            audits.append({"function_id": fn.get("function_id"), **deepcopy(result)})
            sizing["vertical_circulation_footprint"] = deepcopy(result)
            if result["status"] == "resolved":
                count = sizing.get("count", fn.get("quantity", 1))
                if not self._positive(count):
                    result = {**result, "status": "unresolved", "missing_inputs": ["positive_count"]}
                    sizing["vertical_circulation_footprint"] = deepcopy(result)
                    audits[-1] = {"function_id": fn.get("function_id"), **deepcopy(result)}
                    continue
                sizing.update({
                    "sizing_mode": "DERIVED_GEOMETRIC_FOOTPRINT",
                    "derived_footprint": result["footprint_area_m2"],
                    "resolved_spatial_area": result["footprint_area_m2"] * float(count),
                    "area_unit": "m2", "status": "resolved",
                    "source": "explicit_vertical_circulation_evidence",
                    "provenance": deepcopy(result["provenance"]),
                    "confidence": result["confidence"],
                })
        return {"contract": "VerticalCirculationFootprintSizingV1",
                "source_contract": demand_profile.get("contract"), "demand_profile": profile,
                "stair_audits": audits, "count_is_area": False,
                "geometry_generated": False, "complete": all(x["status"] == "resolved" for x in audits)}

    def _derive(self, evidence):
        missing = [key for key in self.REQUIRED if not self._positive(evidence.get(key))]
        selection = evidence.get("flight_count_selection") or {}
        if selection.get("status") != "authoritative_selected" or \
                selection.get("authority_class") not in (
                    "PROJECT_REQUIREMENT", "HARD_REGULATION", "DESIGN_CONFIRMATION"):
            missing.append("authoritative_stair_configuration_selection")
        rise, rise_source = self._rise(evidence)
        if rise is None:
            missing.append("floor_to_floor_height_or_authoritative_level_spans")
        flights = evidence.get("flight_count")
        if self._positive(flights) and (int(flights) != float(flights) or int(flights) not in (1, 2)):
            missing.append("supported_flight_count_1_or_2")
        if self._positive(flights) and int(flights) > 1:
            if evidence.get("landing_required") is not True:
                missing.append("landing_required_true")
            if not self._positive(evidence.get("landing_depth")):
                missing.append("landing_depth")
        missing = list(dict.fromkeys(missing))
        base = {"status": "unresolved", "missing_inputs": missing, "area_unit": "m2",
                "geometry_generated": False, "direction_used": False, "placement_used": False}
        if missing:
            return base
        flights = int(flights); rise = float(rise)
        risers = int(math.ceil(rise / float(evidence["maximum_riser"]) - 1e-12))
        if risers < flights:
            return {**base, "missing_inputs": ["valid_riser_distribution"]}
        split = self._split(risers, flights)
        treads = [max(value - 1, 0) for value in split]
        length = max(treads) * float(evidence["minimum_tread"])
        if flights == 2:
            length += float(evidence["landing_depth"])
        width = float(evidence["clear_width"]) * flights
        provenance = list(deepcopy(evidence.get("provenance") or []))
        provenance += ["operational_requirements." + key for key in self.REQUIRED]
        provenance.append(rise_source)
        if flights == 2:
            provenance += ["operational_requirements.landing_required", "operational_requirements.landing_depth"]
        return {**base, "status": "resolved", "missing_inputs": [], "footprint_length_m": length,
                "footprint_width_m": width, "footprint_area_m2": length * width,
                "floor_to_floor_height_m": rise, "riser_count": risers,
                "flight_count": flights, "flight_riser_distribution": split,
                "stair_type": deepcopy(evidence.get("stair_type")),
                "provenance": list(dict.fromkeys(provenance)),
                "confidence": float(evidence.get("confidence", 0.8))}

    def _rise(self, evidence):
        direct = evidence.get("floor_to_floor_height")
        if self._positive(direct):
            return float(direct), "operational_requirements.floor_to_floor_height"
        spans = evidence.get("served_level_spans")
        if not isinstance(spans, list) or len(spans) < 2:
            return None, None
        values = [item.get("bottom") for item in spans if isinstance(item, dict)]
        if len(values) != len(spans) or any(not self._numeric(value) for value in values):
            return None, None
        rises = [abs(float(b) - float(a)) for a, b in zip(values, values[1:])]
        if not rises or any(value <= 0 for value in rises):
            return None, None
        return max(rises), "operational_requirements.served_level_spans"

    @staticmethod
    def _split(count, parts):
        quotient, remainder = divmod(count, parts)
        return [quotient + (1 if index < remainder else 0) for index in range(parts)]

    @staticmethod
    def _numeric(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))

    def _positive(self, value):
        return self._numeric(value) and float(value) > 0
