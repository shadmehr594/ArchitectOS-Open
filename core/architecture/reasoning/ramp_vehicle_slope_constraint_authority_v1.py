"""Resolve vehicle-parking-ramp slope constraints from exact source evidence."""
from copy import deepcopy
import math


class RampVehicleSlopeConstraintAuthorityV1:
    """Select one exact regulation clause without geometry or policy defaults."""

    REQUIRED_SOURCE_KIND = "primary_regulation_document_reproduction"
    APPLICABILITY_CONTRACT = "ParkingRampApplicabilityAuditV1"
    ALLOWED_FACT_AUTHORITIES = {"PROJECT_REQUIREMENT", "HARD_REGULATION", "AUTHORITATIVE_PROJECT_FACT"}

    def resolve(self, regulation_evidence=None, applicability=None):
        original = deepcopy({"regulation_evidence": regulation_evidence, "applicability": applicability})
        evidence = deepcopy(regulation_evidence)
        audit = deepcopy(applicability)
        context = self._resolved_context(audit)
        result = {
            "contract": "RampVehicleSlopeConstraintAuthorityResultV1",
            "status": "unresolved",
            "maximum_slope_constraint": None,
            "transition_constraints": {
                "transition_start": self._unresolved_transition("transition_start"),
                "transition_end": self._unresolved_transition("transition_end"),
            },
            "selected_clause": None,
            "failure_reasons": [],
            "input_mutated": False,
        }
        failures = self._source_failures(evidence)
        failures.extend(self._applicability_failures(audit))
        if context.get("ramp_use") != "vehicle_parking":
            failures.append("vehicle_parking_ramp_applicability_required")
        if failures:
            result["failure_reasons"] = sorted(set(failures))
            return self._finish(result, original, regulation_evidence, applicability)

        matches = [clause for clause in evidence["clauses"] if self._matches(clause.get("applicability"), context)]
        if len(matches) != 1:
            result["failure_reasons"] = [
                "applicable_regulation_clause_missing" if not matches else "multiple_applicable_regulation_clauses"
            ]
            return self._finish(result, original, regulation_evidence, applicability)

        clause = matches[0]
        main = clause.get("maximum_main_running_slope") or {}
        start = clause.get("transition_start") or {}
        end = clause.get("transition_end") or {}
        numeric = (main.get("value"), start.get("maximum_slope"), start.get("minimum_length"),
                   end.get("maximum_slope"), end.get("minimum_length"))
        if (main.get("semantic") != "hard_maximum" or main.get("unit") != "ratio"
                or not all(self._positive(value) for value in numeric)):
            result["failure_reasons"] = ["selected_clause_constraint_evidence_invalid"]
            return self._finish(result, original, regulation_evidence, applicability)

        provenance = self._provenance(evidence, clause)
        result.update({
            "status": "resolved",
            "selected_clause": clause["id"],
            "maximum_slope_constraint": {
                "contract": "RampMaximumSlopeConstraintV1", "status": "resolved",
                "maximum_slope": float(main["value"]), "unit": "ratio",
                "semantic": "maximum_main_running_slope", "authority_class": "HARD_REGULATION",
                "applicability": deepcopy(clause["applicability"]), "provenance": provenance,
            },
            "transition_constraints": {
                "transition_start": self._transition(clause, start, "transition_start", provenance),
                "transition_end": self._transition(clause, end, "transition_end", provenance),
            },
        })
        return self._finish(result, original, regulation_evidence, applicability)

    def _applicability_failures(self, audit):
        if not isinstance(audit, dict) or audit.get("contract") != self.APPLICABILITY_CONTRACT:
            return ["evidence_bearing_applicability_audit_required"]
        facts = audit.get("facts")
        if not isinstance(facts, dict):
            return ["applicability_facts_missing"]
        failures = []
        for key, fact in facts.items():
            if not isinstance(fact, dict):
                failures.append("invalid_applicability_fact:" + str(key)); continue
            if fact.get("status") == "resolved":
                if fact.get("authority_class") not in self.ALLOWED_FACT_AUTHORITIES or not fact.get("provenance"):
                    failures.append("resolved_applicability_fact_lacks_authority_or_provenance:" + str(key))
                if fact.get("source_kind") in {"geometry_candidate", "candidate_geometry", "geometry_derived"}:
                    failures.append("geometry_or_candidate_fact_forbidden:" + str(key))
        return failures

    @staticmethod
    def _resolved_context(audit):
        if not isinstance(audit, dict) or not isinstance(audit.get("facts"), dict):
            return {}
        return {key: deepcopy(fact.get("value")) for key, fact in audit["facts"].items()
                if isinstance(fact, dict) and fact.get("status") == "resolved"}

    def _source_failures(self, evidence):
        if not isinstance(evidence, dict) or evidence.get("contract") != "IranTopic4VehicleParkingRampSlopeEvidenceV1":
            return ["regulation_evidence_contract_missing_or_invalid"]
        source = evidence.get("source") or {}
        if (evidence.get("status") != "resolved_source_evidence"
                or evidence.get("scope") != "vehicle_parking_ramps_only"
                or source.get("kind") != self.REQUIRED_SOURCE_KIND
                or not source.get("document_url")
                or not isinstance(source.get("provenance"), list) or not source["provenance"]
                or not isinstance(evidence.get("clauses"), list) or not evidence["clauses"]):
            return ["regulation_source_not_primary_or_unresolved"]
        return []

    def _matches(self, rule, context):
        if not isinstance(rule, dict):
            return False
        for key, expected in rule.items():
            actual = context.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif isinstance(expected, dict) and key == "ramp_length_m":
                if not self._finite(actual):
                    return False
                boundary = float(expected["value"])
                if expected.get("operator") == "greater_than" and not float(actual) > boundary:
                    return False
                if expected.get("operator") == "less_than" and not float(actual) < boundary:
                    return False
            elif actual != expected:
                return False
        return True

    @staticmethod
    def _provenance(evidence, clause):
        source = evidence["source"]
        return [{
            "jurisdiction": evidence["jurisdiction"], "document": evidence["document"],
            "edition": evidence["edition"], "publisher": evidence["publisher"],
            "clause": clause["clause"], "printed_page": source["printed_page"],
            "pdf_page_index_zero_based": source["pdf_page_index_zero_based"],
            "source_kind": source["kind"], "source_url": source["document_url"],
            "retrieved_on": source["retrieved_on"], "evidence_record_id": clause["id"],
        }]

    @staticmethod
    def _transition(clause, value, role, provenance):
        return {
            "contract": "RampTransitionSlopeConstraintV1", "status": "resolved",
            "role": role, "maximum_slope": float(value["maximum_slope"]), "unit": "ratio",
            "minimum_length": float(value["minimum_length"]), "length_unit": value["length_unit"],
            "semantic": "vehicle_ramp_endpoint_transition", "authority_class": "HARD_REGULATION",
            "applicability": deepcopy(clause["applicability"]), "provenance": deepcopy(provenance),
        }

    @staticmethod
    def _unresolved_transition(role):
        return {"contract": "RampTransitionSlopeConstraintV1", "status": "unresolved",
                "role": role, "maximum_slope": None, "minimum_length": None,
                "failure_reasons": ["applicable_transition_constraint_unresolved"]}

    @staticmethod
    def _finish(result, original, evidence, applicability):
        result["input_mutated"] = original != {
            "regulation_evidence": evidence, "applicability": applicability
        }
        return result

    @staticmethod
    def _finite(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))

    def _positive(self, value):
        return self._finite(value) and float(value) > 0.0
