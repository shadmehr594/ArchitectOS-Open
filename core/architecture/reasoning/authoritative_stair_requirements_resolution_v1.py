"""Fail-closed resolution of authoritative, non-geometric stair requirements."""
from copy import deepcopy
import math


class AuthoritativeStairRequirementsResolutionV1:
    """Merge independently authoritative stair evidence before footprint sizing."""

    CANONICAL_MAPPING = {"riser": "maximum_riser", "tread": "minimum_tread"}
    GOVERNED = (
        "clear_width", "maximum_riser", "minimum_tread", "flight_count",
        "floor_to_floor_height", "served_level_spans", "landing_required", "landing_depth",
        "maximum_rise_per_flight", "maximum_risers_per_flight",
        "minimum_landing_width_relation", "minimum_landing_dimension_relation",
    )
    FIELD_UNITS = {
        "clear_width": "m", "maximum_riser": "m", "minimum_tread": "m",
        "flight_count": "count", "floor_to_floor_spans": "m",
        "landing_required": "boolean", "landing_depth": "m",
        "maximum_rise_per_flight": "m", "maximum_risers_per_flight": "count",
        "minimum_landing_width_relation": "relation",
        "minimum_landing_dimension_relation": "relation",
    }
    REQUIRED_ACTION = {
        "clear_width": "human_input_required",
        "maximum_riser": "regulation_input_required",
        "minimum_tread": "regulation_input_required",
        "flight_count": "configuration_required",
        "floor_to_floor_spans": "level_contract_required",
        "landing_required": "configuration_required",
        "landing_depth": "regulation_input_required",
        "maximum_rise_per_flight": "regulation_input_required",
        "maximum_risers_per_flight": "conditional_regulation_applicability_required",
        "minimum_landing_width_relation": "regulation_input_required",
        "minimum_landing_dimension_relation": "regulation_input_required",
    }

    def resolve(self, demand_profile, requirements=None, regulations=None,
                level_contract=None, configuration=None, project_context=None):
        original = deepcopy(demand_profile)
        profile = deepcopy(demand_profile)
        requirements = deepcopy(requirements or {})
        regulations = deepcopy(regulations or {})
        levels = deepcopy(level_contract if level_contract is not None else requirements)
        configuration = deepcopy(configuration or {})
        project_context = deepcopy(project_context or {})
        audits = []

        for function in profile.get("functions", []):
            if function.get("function") != "stair":
                continue
            operational = function.setdefault("operational_requirements", {})
            operational.pop("flight_count_selection", None)
            operational.pop("constraint_evidence", None)
            for key in self.GOVERNED:
                operational.pop(key, None)

            fields = {
                "clear_width": self._resolve_candidates(
                    "clear_width", self._project_candidates(requirements, "core.stair_clear_width")),
                "maximum_riser": self._resolve_candidates(
                    "maximum_riser", self._regulation_candidates(
                        regulations, project_context, "maximum_riser", "riser")),
                "minimum_tread": self._resolve_candidates(
                    "minimum_tread", self._regulation_candidates(
                        regulations, project_context, "minimum_tread", "tread")),
                "flight_count": self._resolve_candidates(
                    "flight_count", self._configuration_candidates(configuration, "flight_count")),
                "floor_to_floor_spans": self._resolve_level_spans(levels, function.get("floor_scope", [])),
                "landing_required": self._resolve_candidates(
                    "landing_required", self._regulation_candidates(
                        regulations, project_context, "landing_required") +
                    self._configuration_candidates(configuration, "landing_required")),
                "landing_depth": self._resolve_candidates(
                    "landing_depth", self._regulation_candidates(
                        regulations, project_context, "landing_depth")),
                "maximum_rise_per_flight": self._resolve_candidates(
                    "maximum_rise_per_flight", self._regulation_candidates(
                        regulations, project_context, "maximum_rise_per_flight")),
                "maximum_risers_per_flight": self._resolve_candidates(
                    "maximum_risers_per_flight", self._regulation_candidates(
                        regulations, project_context, "maximum_risers_per_flight")),
                "minimum_landing_dimension_relation": self._resolve_candidates(
                    "minimum_landing_dimension_relation", self._regulation_candidates(
                        regulations, project_context, "minimum_landing_dimension_relation",
                        "minimum_landing_width_relation")),
            }
            fields["landing_depth"] = self._derive_landing_depth(
                fields["landing_depth"], fields["clear_width"],
                fields["minimum_landing_dimension_relation"])

            for key in ("clear_width", "maximum_riser", "minimum_tread", "flight_count"):
                if fields[key]["status"] == "resolved":
                    operational[key] = deepcopy(fields[key]["value"])
            if fields["flight_count"]["status"] == "resolved" and \
                    fields["flight_count"].get("authority_class") in (
                        "PROJECT_REQUIREMENT", "HARD_REGULATION", "DESIGN_CONFIRMATION"):
                operational["flight_count_selection"] = {
                    "status": "authoritative_selected",
                    "authority_class": fields["flight_count"]["authority_class"],
                    "provenance": deepcopy(fields["flight_count"]["provenance"]),
                }
            spans = fields["floor_to_floor_spans"]
            if spans["status"] == "resolved":
                operational["served_level_spans"] = deepcopy(spans["value"])
            flights = fields["flight_count"].get("value")
            for key in ("landing_required", "landing_depth"):
                if fields[key]["status"] == "resolved":
                    operational[key] = deepcopy(fields[key]["value"])
            for key in ("maximum_rise_per_flight", "maximum_risers_per_flight",
                        "minimum_landing_dimension_relation", "landing_depth"):
                if fields[key]["status"] == "resolved":
                    operational[key] = deepcopy(fields[key]["value"])
                    operational.setdefault("constraint_evidence", {})[key] = deepcopy(fields[key])

            resolved_records = [record for record in fields.values() if record["status"] == "resolved"]
            operational["provenance"] = list(dict.fromkeys(
                item for record in resolved_records for item in record["provenance"]))
            if resolved_records:
                operational["confidence"] = min(record["confidence"] for record in resolved_records)
            actions = sorted({self.REQUIRED_ACTION[name] for name, record in fields.items()
                              if record["status"] != "resolved" and
                              not (name in ("landing_required", "landing_depth") and flights != 2) and
                              name != "maximum_risers_per_flight"})
            audit = {"function_id": function.get("function_id"), "fields": deepcopy(fields),
                     "required_inputs": actions,
                     "status": "resolved" if not actions else
                               ("conflicted" if any(x["status"] == "conflicted" for x in fields.values())
                                else "unresolved")}
            audits.append(audit)

        return {
            "contract": "AuthoritativeStairRequirementsResolutionV1",
            "source_contract": demand_profile.get("contract"),
            "demand_profile": profile,
            "stair_requirement_audits": audits,
            "canonical_mapping": deepcopy(self.CANONICAL_MAPPING),
            "complete": bool(audits) and all(item["status"] == "resolved" for item in audits),
            "input_mutated": original != demand_profile,
            "geometry_generated": False,
        }

    def _derive_landing_depth(self, direct, clear_width, relation):
        """Resolve the straight-landing minimum dimension from authoritative inputs only."""
        if direct["status"] == "resolved":
            return direct
        if clear_width["status"] != "resolved" or relation["status"] != "resolved":
            return direct
        if relation["value"] != "not_less_than_stair_clear_width":
            return self._record("landing_depth", rejection_reasons=[{
                "source_path": relation.get("source_path"),
                "reasons": ["unsupported_landing_dimension_relation"],
            }])
        if not self._finite(clear_width["value"]) or float(clear_width["value"]) <= 0:
            return self._record("landing_depth", rejection_reasons=[{
                "source_path": clear_width.get("source_path"),
                "reasons": ["positive_authoritative_stair_clear_width_required"],
            }])
        record = self._record(
            "landing_depth", "resolved", float(clear_width["value"]),
            relation.get("source_contract"), relation.get("source_path"),
            "minimum_landing_dimension_relation",
            "resolved_authoritative_derived_relation",
            list(dict.fromkeys(clear_width["provenance"] + relation["provenance"])),
            min(clear_width["confidence"], relation["confidence"]),
            deepcopy(relation.get("applicability")))
        record.update({
            "constraint": "minimum", "operator": ">=",
            "resolution_rule": "authoritative_relation_bound",
            "resolution_provenance": {
                "expression": "minimum_landing_dimension >= stair_clear_width",
                "effective_value_source_path": clear_width.get("source_path"),
                "relation_source_path": relation.get("source_path"),
                "numeric_constant_introduced": False,
            },
            "accepted_evidence": [deepcopy(clear_width), deepcopy(relation)],
        })
        return record

    def _resolve_candidates(self, canonical_name, candidates):
        rejected = []
        accepted = []
        for item in candidates:
            validation = item.get("applicability_validation")
            if validation and validation.get("status") != "applicable":
                rejected.append({"source_path": item.get("source_path"),
                                 "reasons": deepcopy(validation.get("reasons", []))})
            elif not self._eligible(item):
                rejected.append({"source_path": item.get("source_path"),
                                 "reasons": ["authoritative_evidence_required"]})
            else:
                accepted.append(item)
        candidates = accepted
        if not candidates:
            return self._record(canonical_name, rejection_reasons=rejected)
        constraint_kinds = {item.get("constraint", "exact") for item in candidates}
        if canonical_name == "minimum_tread" and constraint_kinds == {"minimum"}:
            chosen = max(candidates, key=lambda item: float(item["value"]))
            record = self._record(
                canonical_name, "resolved", deepcopy(chosen["value"]),
                chosen.get("source_contract"), chosen.get("source_path"), chosen.get("key"),
                chosen.get("evidence_status"), deepcopy(chosen.get("provenance") or [chosen["source_path"]]),
                chosen.get("confidence", 1.0), deepcopy(chosen.get("applicability")))
            record.update({
                "constraint": "minimum", "operator": ">=",
                "resolution_rule": "strictest_applicable_minimum",
                "accepted_evidence": [self._evidence_summary(item) for item in candidates],
                "resolution_provenance": {
                    "effective_source_path": chosen.get("source_path"),
                    "reason": "highest_applicable_lower_bound",
                    "candidate_lower_bounds_m": [float(item["value"]) for item in candidates],
                },
            })
            return record
        if canonical_name in ("maximum_riser", "maximum_rise_per_flight",
                              "maximum_risers_per_flight") and constraint_kinds == {"maximum"}:
            chosen = min(candidates, key=lambda item: float(item["value"]))
            record = self._record(
                canonical_name, "resolved", deepcopy(chosen["value"]),
                chosen.get("source_contract"), chosen.get("source_path"), chosen.get("key"),
                chosen.get("evidence_status"), deepcopy(chosen.get("provenance") or [chosen["source_path"]]),
                chosen.get("confidence", 1.0), deepcopy(chosen.get("applicability")))
            record.update({
                "constraint": "maximum", "operator": "<=",
                "resolution_rule": "strictest_applicable_maximum",
                "accepted_evidence": [self._evidence_summary(item) for item in candidates],
                "resolution_provenance": {
                    "effective_source_path": chosen.get("source_path"),
                    "reason": "smallest_applicable_upper_bound",
                    "candidate_upper_bounds": [float(item["value"]) for item in candidates],
                },
            })
            if canonical_name == "maximum_riser":
                record["resolution_provenance"]["candidate_upper_bounds_m"] = \
                    record["resolution_provenance"]["candidate_upper_bounds"]
            return record
        values = []
        for item in candidates:
            if not any(self._same(item["value"], value) for value in values):
                values.append(item["value"])
        if len(values) != 1:
            return self._record(canonical_name, "conflicted", provenance=[
                item["source_path"] for item in candidates], confidence=0.0,
                applicability=[deepcopy(item.get("applicability")) for item in candidates],
                rejection_reasons=rejected)
        chosen = candidates[0]
        record = self._record(
            canonical_name, "resolved", deepcopy(chosen["value"]),
            chosen.get("source_contract"), chosen.get("source_path"), chosen.get("key"),
            chosen.get("evidence_status"), deepcopy(chosen.get("provenance") or [chosen["source_path"]]),
            chosen.get("confidence", 1.0), deepcopy(chosen.get("applicability")))
        record["authority_class"] = chosen.get("authority_class")
        return record

    def _resolve_level_spans(self, authority, floor_scope):
        contracts = self._contracts(authority)
        span_records = []
        for contract in contracts:
            levels = contract.get("levels", contract.get("level_elevations",
                                  contract.get("exact_levels", {})))
            if not isinstance(levels, dict):
                continue
            for lower, upper in zip(floor_scope, floor_scope[1:]):
                if lower not in levels or upper not in levels:
                    continue
                lower_item = self._level_candidate(contract, levels[lower], lower)
                upper_item = self._level_candidate(contract, levels[upper], upper)
                if not self._eligible(lower_item) or not self._eligible(upper_item):
                    continue
                span_records.append({"pair": (lower, upper), "lower": lower_item, "upper": upper_item})
        expected = list(zip(floor_scope, floor_scope[1:]))
        if not expected:
            return self._record("floor_to_floor_spans")
        selected = []
        for pair in expected:
            matches = [item for item in span_records if item["pair"] == pair]
            rises = []
            for item in matches:
                value = abs(float(item["upper"]["value"]) - float(item["lower"]["value"]))
                if value > 0 and not any(self._same(value, known) for known in rises):
                    rises.append(value)
            if len(rises) > 1:
                return self._record("floor_to_floor_spans", "conflicted",
                                    provenance=[x["lower"]["source_path"] for x in matches], confidence=0.0)
            if len(rises) != 1:
                return self._record("floor_to_floor_spans")
            selected.append((pair, matches[0], rises[0]))
        chain = [{"name": selected[0][0][0], "bottom": selected[0][1]["lower"]["value"]}]
        chain += [{"name": pair[1], "bottom": item["upper"]["value"]} for pair, item, _ in selected]
        provenance = [path for _, item, _ in selected for path in
                      (item["lower"]["source_path"], item["upper"]["source_path"])]
        first = selected[0][1]["lower"]
        return self._record("floor_to_floor_spans", "resolved", chain,
                            first.get("source_contract"), first.get("source_path"), "levels",
                            first.get("evidence_status"), list(dict.fromkeys(provenance)),
                            min(min(item["lower"].get("confidence", 1.0), item["upper"].get("confidence", 1.0))
                                for _, item, _ in selected), first.get("applicability"))

    def _project_candidates(self, authority, path):
        result = []
        for contract in self._contracts(authority):
            node = contract
            for part in path.split("."):
                node = node.get(part) if isinstance(node, dict) else None
            if node is not None:
                result.append(self._candidate(contract, node, "requirements." + path, path.split(".")[-1]))
        return result

    def _level_candidate(self, contract, value, level):
        source_path = "requirements.levels.%s" % level
        if contract.get("contract") != "ProjectLevelContractV1":
            return self._candidate(contract, value, source_path, level)
        records = contract.get("level_evidence", {}).get(level, [])
        valid = [record for record in records if isinstance(record, dict) and
                 record.get("authority_class") in ("HARD_REGULATION", "PROJECT_REQUIREMENT") and
                 record.get("provenance")]
        if contract.get("status") != "resolved" or not valid:
            return self._candidate({}, value, source_path, level)
        provenance = list(dict.fromkeys(item for record in valid
                                        for item in record.get("provenance", [])))
        return self._candidate({
            "contract": "ProjectLevelContractV1",
            "evidence_status": "resolved_authoritative_project_level_contract",
            "provenance": provenance,
            "confidence": 1.0,
        }, value, "level_contract.level_evidence.%s" % level, level)

    def _regulation_candidates(self, authority, project_context, *keys):
        result = []
        for contract in self._contracts(authority):
            for index, record in enumerate(contract.get("evidence_records", [])):
                if not isinstance(record, dict) or record.get("key") not in keys:
                    continue
                candidate = self._candidate(
                    contract, record,
                    "regulations.evidence_records.%d.%s" % (index, record.get("id", record["key"])),
                    record["key"])
                candidate["applicability_validation"] = self._validate_regulation_applicability(
                    candidate, project_context)
                candidate["regulation_complete"] = \
                    candidate["applicability_validation"]["status"] == "applicable"
                result.append(candidate)
            for section_name in ("stair_requirements", "stair"):
                section = contract.get(section_name, {})
                for key in keys:
                    if isinstance(section, dict) and key in section:
                        candidate = self._candidate(contract, section[key],
                                                    "regulations.%s.%s" % (section_name, key), key)
                        candidate["applicability_validation"] = self._validate_regulation_applicability(
                            candidate, project_context)
                        candidate["regulation_complete"] = candidate["applicability_validation"]["status"] == "applicable"
                        result.append(candidate)
        return result

    @staticmethod
    def _validate_regulation_applicability(candidate, project_context):
        """Require an explicit, exact applicability proof for the active project."""
        applicability = candidate.get("applicability")
        reasons = []
        if not isinstance(applicability, dict):
            reasons.append("explicit_applicability_required")
            applicability = {}
        if str(applicability.get("status", "")).lower() not in {
                "applicable", "explicitly_applicable", "verified_applicable"}:
            reasons.append("applicability_status_not_explicit")
        human_local = candidate.get("source_kind") == "human_confirmed_current_project_local_requirement"
        required_context = ("project_id", "jurisdiction") if human_local else (
            "project_id", "jurisdiction")
        for name in required_context:
            if not project_context.get(name):
                reasons.append("project_context_%s_required" % name)
            if not applicability.get(name):
                reasons.append("applicability_%s_required" % name)
        if not human_local:
            project_editions = project_context.get("editions")
            project_edition = project_context.get("edition")
            if not project_edition and not project_editions:
                reasons.append("project_context_edition_required")
            if not applicability.get("edition"):
                reasons.append("applicability_edition_required")
        occupancies = project_context.get("occupancies")
        applicable_occupancies = applicability.get("occupancies")
        if not human_local:
            if not isinstance(occupancies, (list, tuple, set)) or not occupancies:
                reasons.append("project_context_occupancies_required")
            if not isinstance(applicable_occupancies, (list, tuple, set)) or not applicable_occupancies:
                reasons.append("applicability_occupancies_required")
        for name in required_context:
            if project_context.get(name) and applicability.get(name) and \
                    applicability[name] != "*" and project_context[name] != applicability[name]:
                reasons.append("%s_mismatch" % name)
        if not human_local and applicability.get("edition"):
            allowed_editions = set(str(x) for x in (project_context.get("editions") or []))
            if project_context.get("edition"):
                allowed_editions.add(str(project_context["edition"]))
            if allowed_editions and str(applicability["edition"]) not in allowed_editions:
                reasons.append("edition_mismatch")
        if occupancies and applicable_occupancies and not set(occupancies).issubset(set(applicable_occupancies)):
            reasons.append("occupancy_scope_mismatch")
        if candidate.get("jurisdiction") != applicability.get("jurisdiction"):
            reasons.append("authority_jurisdiction_mismatch")
        if not human_local and candidate.get("edition") != applicability.get("edition"):
            reasons.append("authority_edition_mismatch")
        if not candidate.get("source"):
            reasons.append("source_required")
        if not candidate.get("source_reference"):
            reasons.append("source_reference_required")
        if human_local:
            if candidate.get("verification_status") != "human_confirmed_not_independently_document_verified":
                reasons.append("explicit_human_confirmation_status_required")
            if candidate.get("authority_scope") != "current_project_only":
                reasons.append("current_project_scope_required")
        return {"status": "inapplicable" if reasons else "applicable",
                "reasons": sorted(set(reasons)), "project_context": deepcopy(project_context)}

    def _configuration_candidates(self, authority, key):
        result = []
        for contract in self._contracts(authority):
            section = contract.get("stair", contract)
            if isinstance(section, dict) and key in section:
                result.append(self._candidate(contract, section[key], "configuration.stair.%s" % key, key))
        return result

    @staticmethod
    def _contracts(authority):
        if isinstance(authority, list):
            return [item for item in authority if isinstance(item, dict)]
        return [authority] if isinstance(authority, dict) else []

    @staticmethod
    def _candidate(contract, raw, source_path, key):
        payload = raw if isinstance(raw, dict) and "value" in raw else {"value": raw}
        return {
            "value": deepcopy(payload.get("value")), "unit": payload.get("unit"),
            "source_contract": payload.get("source_contract", contract.get("contract")),
            "source_path": payload.get("source_path", source_path), "key": payload.get("key", key),
            "evidence_status": payload.get("evidence_status", contract.get("evidence_status")),
            "provenance": deepcopy(payload.get("provenance", contract.get("provenance", [source_path]))),
            "confidence": float(payload.get("confidence", contract.get("confidence", 1.0))),
            "applicability": deepcopy(payload.get("applicability", contract.get("applicability"))),
            "source": payload.get("source", contract.get("source")),
            "jurisdiction": payload.get("jurisdiction", contract.get("jurisdiction")),
            "edition": payload.get("edition", contract.get("edition")),
            "source_reference": payload.get(
                "source_reference", payload.get("source_page_or_section",
                contract.get("source_reference", contract.get("source_page_or_section")))),
            "constraint": payload.get("constraint", contract.get("constraint", "exact")),
            "source_kind": payload.get("source_kind", contract.get("source_kind")),
            "authority_scope": payload.get("authority_scope", contract.get("authority_scope")),
            "verification_status": payload.get("verification_status", contract.get("verification_status")),
            "authority_class": payload.get("authority_class", contract.get("authority_class")),
            "code_document_name": payload.get("code_document_name", contract.get("code_document_name")),
            "source_url": payload.get("source_url", contract.get("source_url")),
            "clause": payload.get("clause", contract.get("clause")),
            "printed_page": payload.get("printed_page", contract.get("printed_page")),
            "pdf_page": payload.get("pdf_page", contract.get("pdf_page")),
            "derivation": deepcopy(payload.get("derivation", contract.get("derivation"))),
        }

    def _eligible(self, item):
        if not isinstance(item, dict) or item.get("value") is None:
            return False
        status = str(item.get("evidence_status") or "").lower()
        if not any(token in status for token in ("authoritative", "resolved", "verified")):
            return False
        value = item["value"]
        return isinstance(value, (bool, str)) or self._finite(value) or isinstance(value, (list, dict))

    def _record(self, canonical_name, status="unresolved", value=None, source_contract=None,
                source_path=None, key=None, evidence_status=None, provenance=None,
                confidence=0.0, applicability=None, rejection_reasons=None):
        return {"status": status, "value": value, "unit": self.FIELD_UNITS[canonical_name],
                "source_contract": source_contract, "source_path": source_path, "key": key,
                "evidence_status": evidence_status, "provenance": deepcopy(provenance or []),
                "confidence": float(confidence), "applicability": deepcopy(applicability),
                "rejection_reasons": deepcopy(rejection_reasons or []),
                "canonical_name": canonical_name, "authority_class": None}

    @staticmethod
    def _evidence_summary(item):
        return {key: deepcopy(item.get(key)) for key in (
            "value", "unit", "constraint", "source_contract", "source_path",
            "evidence_status", "provenance", "applicability", "source",
            "source_kind", "authority_scope", "verification_status", "source_reference",
            "code_document_name", "source_url", "clause", "printed_page", "pdf_page",
            "derivation")}

    @staticmethod
    def _finite(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))

    @staticmethod
    def _same(left, right):
        return left == right and type(left) is type(right)
