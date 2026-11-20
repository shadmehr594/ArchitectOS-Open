"""Bounded, non-authoritative regulation evaluation under design hypotheses."""
from copy import deepcopy
import math


class ConditionalRegulationApplicabilityEvaluationV1:
    """Evaluate regulation applicability without creating project authority."""

    MAX_HYPOTHESES = 64
    MAX_CLAUSES = 256
    AUTHORITY_CLASS = "DESIGN_HYPOTHESIS"

    def evaluate(self, hypotheses=None, regulatory_classification_definition=None,
                 regulation_clauses=None, regulation_evidence=None, achieved_results=None):
        original = deepcopy((hypotheses, regulatory_classification_definition,
                             regulation_clauses, regulation_evidence, achieved_results))
        items = list(hypotheses or [])
        results_by_id = {str(item.get("hypothesis_id")): item for item in (achieved_results or [])
                         if isinstance(item, dict) and item.get("hypothesis_id") is not None}
        envelope = {
            "contract": "ConditionalRegulationApplicabilityEvaluationV1",
            "status": "evaluated",
            "evaluations": [],
            "bounded": True,
            "limits": {"maximum_hypotheses": self.MAX_HYPOTHESES,
                       "maximum_clauses": self.MAX_CLAUSES},
            "failure_reasons": [],
            "input_mutated": False,
        }
        if len(items) > self.MAX_HYPOTHESES:
            envelope.update(status="rejected", failure_reasons=["hypothesis_limit_exceeded"])
            return self._finish(envelope, original, hypotheses, regulatory_classification_definition,
                                regulation_clauses, regulation_evidence, achieved_results)
        clauses = list(regulation_clauses or [])
        if len(clauses) > self.MAX_CLAUSES:
            envelope.update(status="rejected", failure_reasons=["clause_limit_exceeded"])
            return self._finish(envelope, original, hypotheses, regulatory_classification_definition,
                                regulation_clauses, regulation_evidence, achieved_results)
        envelope["evaluations"] = [self._evaluate_one(
            item, regulatory_classification_definition, clauses, regulation_evidence,
            results_by_id.get(str(item.get("hypothesis_id"))))
            for item in sorted(items, key=lambda row: str(row.get("hypothesis_id", "")))]
        return self._finish(envelope, original, hypotheses, regulatory_classification_definition,
                            regulation_clauses, regulation_evidence, achieved_results)

    def _evaluate_one(self, item, definition, clauses, evidence, achieved):
        hypothesis_id = item.get("hypothesis_id") if isinstance(item, dict) else None
        base = {
            "hypothesis_id": hypothesis_id,
            "hypothesis_status": "hypothesis_rejected",
            "lifecycle_statuses": ["hypothesis_rejected"],
            "target_capacity": item.get("target_capacity") if isinstance(item, dict) else None,
            "authority_class": self.AUTHORITY_CLASS,
            "authoritative": False,
            "provisional_size_class": None,
            "conditional_clause": None,
            "failure_reasons": [],
        }
        failures = self._hypothesis_failures(item)
        failures.extend(self._source_failures(definition, clauses, evidence))
        if failures:
            base["failure_reasons"] = sorted(set(failures))
            return base
        target = item["target_capacity"]
        matches = [row for row in definition["classes"] if self._contains(row, target)]
        if len(matches) != 1:
            base["failure_reasons"] = ["provisional_classification_missing_or_ambiguous"]
            return base
        size_class = matches[0]["class"]
        context = {"ramp_use": "vehicle_parking", "parking_size_class": size_class,
                   "parking_ownership": item["parking_ownership"],
                   "ramp_enclosure": item["ramp_enclosure"]}
        clause_matches = [row for row in clauses if self._matches(row.get("applicability"), context)]
        base.update(hypothesis_status="hypothesis_valid",
                    lifecycle_statuses=["hypothesis_valid"],
                    provisional_size_class={"value": size_class,
                        "status": "hypothesis_valid", "scope": hypothesis_id,
                        "authority_class": self.AUTHORITY_CLASS, "authoritative": False})
        if len(clause_matches) == 1:
            clause = clause_matches[0]
            base["lifecycle_statuses"].append("conditional_applicable")
            base["conditional_clause"] = {
                "status": "conditional_under_hypothesis", "clause_id": clause.get("id"),
                "scope": hypothesis_id, "authority_class": self.AUTHORITY_CLASS,
                "authoritative": False, "applicability": deepcopy(clause.get("applicability")),
                "provenance": self._conditional_provenance(evidence, clause),
            }
        else:
            base["lifecycle_statuses"].append("conditional_unresolved")
            base["failure_reasons"] = ["conditional_clause_missing" if not clause_matches
                                       else "conditional_clause_ambiguous"]
        if isinstance(achieved, dict) and achieved.get("achieved_capacity") != target:
            base["hypothesis_status"] = "invalidated_by_result"
            base["lifecycle_statuses"].append("invalidated_by_result")
            base["invalidation"] = {"reason": "achieved_capacity_mismatch",
                                    "achieved_capacity": achieved.get("achieved_capacity")}
        return base

    @staticmethod
    def _hypothesis_failures(item):
        if not isinstance(item, dict) or not item.get("hypothesis_id"):
            return ["hypothesis_identity_missing"]
        failures = []
        target = item.get("target_capacity"); minimum = item.get("minimum_required_capacity")
        if not ConditionalRegulationApplicabilityEvaluationV1._integer(target):
            failures.append("target_capacity_must_be_nonnegative_integer")
        if not ConditionalRegulationApplicabilityEvaluationV1._integer(minimum):
            failures.append("minimum_required_capacity_must_be_nonnegative_integer")
        if not failures and target < minimum:
            failures.append("target_capacity_below_minimum_required_capacity")
        if item.get("parking_ownership") is None:
            failures.append("parking_ownership_missing")
        if item.get("ramp_enclosure") is None:
            failures.append("ramp_enclosure_missing")
        return failures

    @staticmethod
    def _source_failures(definition, clauses, evidence):
        if not isinstance(definition, dict) or definition.get("status") != "resolved_source_evidence":
            return ["regulatory_classification_definition_invalid"]
        if not isinstance(definition.get("classes"), list) or not definition["classes"]:
            return ["regulatory_classification_boundaries_invalid"]
        if not isinstance(evidence, dict) or evidence.get("status") != "resolved_source_evidence":
            return ["regulation_evidence_invalid"]
        if not isinstance(clauses, list):
            return ["regulation_clauses_invalid"]
        return []

    @staticmethod
    def _contains(row, value):
        lower = row.get("minimum_capacity"); upper = row.get("maximum_capacity")
        return isinstance(lower, int) and value >= lower and (upper is None or value <= upper)

    @staticmethod
    def _matches(rule, context):
        if not isinstance(rule, dict):
            return False
        for key, expected in rule.items():
            actual = context.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif isinstance(expected, dict):
                return False
            elif actual != expected:
                return False
        return True

    @staticmethod
    def _conditional_provenance(evidence, clause):
        source = evidence.get("source") or {}
        return [{"document": evidence.get("document"), "edition": evidence.get("edition"),
                 "clause": clause.get("clause"), "evidence_record_id": clause.get("id"),
                 "source_kind": source.get("kind"), "source_url": source.get("document_url")}]

    @staticmethod
    def _integer(value):
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0 and math.isfinite(float(value))

    @staticmethod
    def _finish(result, original, *current):
        result["input_mutated"] = original != current
        return result
