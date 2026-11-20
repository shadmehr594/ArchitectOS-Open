"""Promote only selected and validated design results into project facts."""
from copy import deepcopy
import math


class ValidatedDesignResultAuthorityPromotionV1:
    """Pure authority gate; selection, validation, publication and promotion remain distinct."""

    FORBIDDEN_CANDIDATE_STATES = {"failed", "historical", "merely_feasible", "feasible"}
    ACCEPTED_VALIDATION_STATUSES = {"complete", "accepted", "validated"}

    def promote(self, candidate=None, minimum_required_capacity=None, hypothesis=None):
        original = deepcopy((candidate, minimum_required_capacity, hypothesis))
        result = {
            "contract": "ValidatedDesignResultAuthorityPromotionV1",
            "status": "promotion_forbidden",
            "selection_status": self._field(candidate, "selected_status"),
            "validation_status": self._field(candidate, "validation_status"),
            "publication_status": "not_evaluated",
            "promotion_status": "forbidden",
            "authoritative_project_fact": None,
            "hypothesis_consistency": {"status": "not_evaluated", "hypothesis_id": None,
                                       "target_capacity": None, "achieved_capacity": self._field(candidate, "achieved_capacity")},
            "failure_reasons": [], "input_mutated": False,
        }
        failures = self._failures(candidate, minimum_required_capacity)
        if failures:
            result["failure_reasons"] = sorted(set(failures))
            return self._finish(result, original, candidate, minimum_required_capacity, hypothesis)
        achieved = candidate["achieved_capacity"]
        linked_id = candidate.get("hypothesis_id")
        target = hypothesis.get("target_capacity") if isinstance(hypothesis, dict) else None
        hypothesis_id = hypothesis.get("hypothesis_id") if isinstance(hypothesis, dict) else linked_id
        consistency = "match" if linked_id == hypothesis_id and achieved == target else "mismatch"
        result.update(
            status="promoted", promotion_status="promoted",
            authoritative_project_fact={
                "status": "resolved", "value": achieved,
                "semantic": "authoritative_achieved_capacity",
                "authority_class": "AUTHORITATIVE_PROJECT_FACT",
                "source_kind": "validated_design_result_authority_promotion",
                "provenance": [{"contract": self.__class__.__name__,
                                "candidate_id": candidate["candidate_id"],
                                "hypothesis_id": linked_id,
                                "selection_evidence": deepcopy(candidate["selection_evidence"]),
                                "validation_evidence": deepcopy(candidate["validation_evidence"]),
                                "achieved_capacity_evidence": deepcopy(candidate["achieved_capacity_evidence"]),
                                "candidate_provenance": deepcopy(candidate["provenance"])}]},
            hypothesis_consistency={"status": consistency, "hypothesis_id": hypothesis_id,
                                    "target_capacity": target, "achieved_capacity": achieved,
                                    "reclassification_required": consistency == "mismatch"})
        return self._finish(result, original, candidate, minimum_required_capacity, hypothesis)

    def _failures(self, candidate, minimum):
        if not isinstance(candidate, dict) or not candidate.get("candidate_id"):
            return ["candidate_identity_missing"]
        failures = []
        state = candidate.get("candidate_status")
        if state in self.FORBIDDEN_CANDIDATE_STATES:
            failures.append("candidate_state_forbids_promotion")
        if candidate.get("selected_status") != "selected" or not candidate.get("selection_evidence"):
            failures.append("evidence_bearing_selection_required")
        if candidate.get("validation_status") not in self.ACCEPTED_VALIDATION_STATUSES or not candidate.get("validation_evidence"):
            failures.append("complete_accepted_validation_evidence_required")
        achieved = candidate.get("achieved_capacity")
        if not self._integer(achieved) or not candidate.get("achieved_capacity_evidence"):
            failures.append("machine_readable_evidence_bearing_achieved_capacity_required")
        if not self._integer(minimum):
            failures.append("minimum_required_capacity_invalid")
        elif self._integer(achieved) and achieved < minimum:
            failures.append("achieved_capacity_below_minimum_required_capacity")
        if not candidate.get("hypothesis_id"):
            failures.append("hypothesis_link_required")
        if not candidate.get("provenance"):
            failures.append("candidate_provenance_required")
        return failures

    @staticmethod
    def _field(candidate, key):
        return candidate.get(key) if isinstance(candidate, dict) else None

    @staticmethod
    def _integer(value):
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0 and math.isfinite(float(value))

    @staticmethod
    def _finish(result, original, *current):
        result["input_mutated"] = original != current
        return result
