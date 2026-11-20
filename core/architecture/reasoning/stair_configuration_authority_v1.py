"""Fail-closed, non-geometric stair configuration hypothesis authority."""
from copy import deepcopy
import math


class StairConfigurationAuthorityV1:
    """Evaluate scalar flight-count feasibility without selecting a design."""

    PREREQUISITES = ("maximum_riser", "minimum_tread")

    def resolve(self, demand_profile, selection_authority=None):
        original = deepcopy(demand_profile)
        profile = deepcopy(demand_profile)
        selection_authority = deepcopy(selection_authority or {})
        audits = []
        for function in profile.get("functions", []):
            if function.get("function") != "stair":
                continue
            evidence = function.get("operational_requirements") or {}
            audit = self._evaluate(function.get("function_id"), evidence, selection_authority)
            audits.append(deepcopy(audit))
            evidence = function.setdefault("operational_requirements", {})
            evidence.pop("flight_count", None)
            evidence.pop("flight_count_selection", None)
            if audit["status"] == "authoritative_selected":
                evidence["flight_count"] = audit["selected_flight_count"]
                evidence["flight_count_selection"] = {
                    "status": "authoritative_selected",
                    "authority_class": audit["selection_authority_class"],
                    "provenance": deepcopy(audit["selection_provenance"]),
                }
                evidence["provenance"] = list(dict.fromkeys(
                    list(evidence.get("provenance") or []) + audit["selection_provenance"]))
        return {"contract": "StairConfigurationAuthorityV1",
                "source_contract": demand_profile.get("contract"), "demand_profile": profile,
                "stair_configuration_audits": audits,
                "complete": bool(audits) and all(x["status"] == "authoritative_selected" for x in audits),
                "input_mutated": original != demand_profile, "geometry_generated": False}

    def _evaluate(self, function_id, evidence, authority):
        rise, rise_source = self._rise(evidence)
        missing = [name for name in self.PREREQUISITES if not self._positive(evidence.get(name))]
        if rise is None:
            missing.append("authoritative_rise_or_level_spans")
        base = {"function_id": function_id, "status": "unresolved_prerequisites",
                "configuration_hypotheses": [], "rejected_hypotheses": [],
                "required_inputs": sorted(set(missing)), "selected_flight_count": None,
                "selection_provenance": [], "geometry_generated": False}
        if missing:
            return base
        rise = float(rise)
        maximum_riser = float(evidence["maximum_riser"])
        minimum_tread = float(evidence["minimum_tread"])
        span_calculations = self._span_calculations(evidence, maximum_riser)
        risers = int(math.ceil(rise / maximum_riser - 1e-12))
        if risers < 1:
            return {**base, "status": "no_feasible_hypothesis",
                    "required_inputs": [], "rejected_hypotheses": [{
                        "flight_count": 1, "reasons": ["positive_riser_count_required"]}]}
        maximum_per_flight = evidence.get("maximum_risers_per_flight")
        maximum_rise_per_flight = evidence.get("maximum_rise_per_flight")
        hypotheses = []
        rejected = []
        span_evaluations = self._span_evaluations(
            span_calculations, maximum_rise_per_flight, maximum_per_flight,
            evidence.get("landing_depth"))
        one_valid = all(item["one_flight_status"] == "feasible" for item in span_evaluations)
        if one_valid:
            hypotheses.append(self._hypothesis(
                1, risers, rise, minimum_tread, rise_source, False, None, span_calculations))
        else:
            rejected.append({"flight_count": 1, "reasons": sorted(set(
                reason for item in span_evaluations for reason in item["one_flight_reasons"])) ,
                "evidence": self._constraint_evidence(evidence, (
                    "maximum_rise_per_flight", "maximum_risers_per_flight"))})
        landing_required = evidence.get("landing_required")
        landing_depth = evidence.get("landing_depth")
        split = [risers // 2 + risers % 2, risers // 2]
        distribution_valid = risers >= 2 and all(
            item["two_flight_scalar_status"] == "feasible" for item in span_evaluations)
        landing_relation = evidence.get("minimum_landing_dimension_relation") or \
            evidence.get("minimum_landing_width_relation")
        landing_requirement_supported = landing_required is True or bool(landing_relation)
        if landing_requirement_supported and self._positive(landing_depth) and distribution_valid:
            hypotheses.append(self._hypothesis(
                2, risers, rise, minimum_tread, rise_source, True,
                float(landing_depth), span_calculations))
        else:
            reasons = []
            if not landing_requirement_supported:
                reasons.append("authoritative_landing_requirement_required")
            if not self._positive(landing_depth):
                reasons.append("authoritative_landing_depth_required")
            if not distribution_valid:
                reasons.append("valid_riser_distribution_required")
            rejected.append({"flight_count": 2, "reasons": reasons,
                             "evidence": self._constraint_evidence(evidence, (
                                 "maximum_rise_per_flight", "maximum_risers_per_flight",
                                 "minimum_landing_dimension_relation", "landing_depth"))})
        base.update({"configuration_hypotheses": hypotheses, "rejected_hypotheses": rejected,
                     "required_inputs": [], "span_evaluations": span_evaluations,
                     "landing_requirements": {
                         "minimum_landing_dimension_relation": landing_relation,
                         "minimum_landing_depth_m": landing_depth,
                         "landing_depth_evidence": deepcopy(
                             (evidence.get("constraint_evidence") or {}).get("landing_depth")),
                         "resolved": bool(landing_relation) and self._positive(landing_depth)}})
        if not hypotheses:
            unresolved = sorted(set(reason for item in rejected for reason in item["reasons"]
                                    if reason.startswith("authoritative_") or
                                    reason.endswith("_required")))
            return {**base, "status": "no_feasible_hypothesis", "required_inputs": unresolved}
        selected = self._selected(authority)
        feasible_counts = [item["flight_count"] for item in hypotheses]
        if selected and selected["flight_count"] in feasible_counts:
            return {**base, "status": "authoritative_selected",
                    "selected_flight_count": selected["flight_count"],
                    "selection_provenance": selected["provenance"],
                    "selection_authority_class": selected["authority_class"]}
        if len(hypotheses) == 1:
            return {**base, "status": "uniquely_feasible",
                    "required_inputs": ["project_design_selection_required"]}
        return {**base, "status": "human_input_required",
                "required_inputs": ["project_design_selection_required"]}

    @staticmethod
    def _hypothesis(flights, risers, rise, tread, rise_source, landing, landing_depth,
                    span_calculations):
        quotient, remainder = divmod(risers, flights)
        distribution = [quotient + (1 if index < remainder else 0) for index in range(flights)]
        tread_counts = [max(value - 1, 0) for value in distribution]
        return {"flight_count": flights, "feasibility_status": "feasible",
                "riser_count": risers, "actual_riser_height_m": rise / risers,
                "flight_riser_distribution": distribution,
                "flight_tread_distribution": tread_counts,
                "flight_run_requirements_m": [value * tread for value in tread_counts],
                "total_tread_run_requirement_m": sum(tread_counts) * tread,
                "landing_dependency": landing, "landing_depth_m": landing_depth,
                "rise_source": rise_source,
                "span_calculations": deepcopy(span_calculations)}

    def _span_calculations(self, evidence, maximum_riser):
        spans = evidence.get("served_level_spans")
        if not isinstance(spans, list) or len(spans) < 2:
            rise = float(evidence["floor_to_floor_height"])
            count = int(math.ceil(rise / maximum_riser - 1e-12))
            return [{"from_level": None, "to_level": None, "rise_m": rise,
                     "riser_count": count, "actual_riser_height_m": rise / count}]
        result = []
        for lower, upper in zip(spans, spans[1:]):
            rise = abs(float(upper["bottom"]) - float(lower["bottom"]))
            count = int(math.ceil(rise / maximum_riser - 1e-12))
            result.append({"from_level": lower.get("name"), "to_level": upper.get("name"),
                           "rise_m": rise, "riser_count": count,
                           "actual_riser_height_m": rise / count})
        return result

    def _span_evaluations(self, spans, maximum_rise, maximum_risers, landing_depth):
        result = []
        for span in spans:
            one_reasons = []
            if self._positive(maximum_rise) and span["rise_m"] > float(maximum_rise) + 1e-12:
                one_reasons.append("maximum_rise_per_flight_exceeded")
            if self._positive(maximum_risers) and span["riser_count"] > int(maximum_risers):
                one_reasons.append("maximum_risers_per_flight_exceeded")
            first, second = self._split(span["riser_count"], 2)
            two_reasons = []
            if self._positive(maximum_rise) and span["rise_m"] / 2 > float(maximum_rise) + 1e-12:
                two_reasons.append("maximum_rise_per_flight_exceeded")
            if self._positive(maximum_risers) and max(first, second) > int(maximum_risers):
                two_reasons.append("maximum_risers_per_flight_exceeded")
            result.append({**deepcopy(span),
                "one_flight_status": "feasible" if not one_reasons else "invalid",
                "one_flight_reasons": one_reasons,
                "two_flight_scalar_status": "feasible" if not two_reasons else "invalid",
                "two_flight_scalar_reasons": two_reasons,
                "two_flight_status": "feasible" if not two_reasons and self._positive(landing_depth)
                                     else "unresolved" if not two_reasons else "invalid",
                "two_flight_reasons": two_reasons or ([] if self._positive(landing_depth)
                                                       else ["authoritative_landing_depth_required"])})
        return result

    @staticmethod
    def _split(count, parts):
        quotient, remainder = divmod(count, parts)
        return [quotient + (1 if index < remainder else 0) for index in range(parts)]

    @staticmethod
    def _constraint_evidence(evidence, names):
        records = evidence.get("constraint_evidence") or {}
        return {name: deepcopy(records[name]) for name in names if name in records}

    def _selected(self, authority):
        section = authority.get("stair", authority) if isinstance(authority, dict) else {}
        raw = section.get("flight_count") if isinstance(section, dict) else None
        payload = raw if isinstance(raw, dict) else {"value": raw}
        value = payload.get("value")
        status = str(payload.get("evidence_status", authority.get("evidence_status", ""))).lower()
        source_reference = payload.get("source_reference", authority.get("source_reference"))
        authority_class = payload.get("authority_class", authority.get("authority_class"))
        source_kind = payload.get("source_kind", authority.get("source_kind"))
        allowed = authority_class in ("PROJECT_REQUIREMENT", "HARD_REGULATION") or \
            source_kind in ("human_confirmed_design_selection", "design_confirmation")
        if not (self._positive(value) and int(value) == float(value) and
                "authoritative_selected" in status and source_reference and allowed):
            return None
        return {"flight_count": int(value), "provenance": deepcopy(
            payload.get("provenance", authority.get("provenance", [source_reference]))),
            "authority_class": authority_class or "DESIGN_CONFIRMATION"}

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
    def _numeric(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))

    def _positive(self, value):
        return self._numeric(value) and float(value) > 0
