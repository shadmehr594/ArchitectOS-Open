"""Synthetic, bounded proof of the parking/ramp epistemic lifecycle."""
from copy import deepcopy

from core.architecture.reasoning.conditional_regulation_applicability_evaluation_v1 import (
    ConditionalRegulationApplicabilityEvaluationV1,
)
from core.architecture.reasoning.parcel2_parking_ramp_applicability_audit_v1 import (
    Parcel2ParkingRampApplicabilityAuditV1,
)
from core.architecture.reasoning.validated_design_result_authority_promotion_v1 import (
    ValidatedDesignResultAuthorityPromotionV1,
)


class SyntheticParkingRampLifecycleOrchestrationV1:
    """Compose existing authorities without geometry, mutation, or inferred facts."""

    MAX_HYPOTHESES = ConditionalRegulationApplicabilityEvaluationV1.MAX_HYPOTHESES
    MAX_CANDIDATES = 64

    def run(self, project_evidence=None, regulation_evidence=None, hypotheses=None, candidates=None):
        original = deepcopy((project_evidence, regulation_evidence, hypotheses, candidates))
        hypothesis_items = list(hypotheses or [])
        candidate_items = list(candidates or [])
        result = self._envelope()

        identity_failures = self._identity_failures(hypothesis_items, candidate_items)
        if len(hypothesis_items) > self.MAX_HYPOTHESES:
            identity_failures.append("hypothesis_limit_exceeded")
        if len(candidate_items) > self.MAX_CANDIDATES:
            identity_failures.append("candidate_limit_exceeded")
        minimum = self._minimum(project_evidence)
        if minimum is None:
            identity_failures.append("confirmed_minimum_required_capacity_missing_or_invalid")
        if identity_failures:
            result.update(status="rejected", failure_reasons=sorted(set(identity_failures)))
            return self._finish(result, original, project_evidence, regulation_evidence, hypotheses, candidates)

        ordered_hypotheses = sorted(hypothesis_items, key=lambda row: str(row["hypothesis_id"]))
        ordered_candidates = sorted(candidate_items, key=lambda row: str(row["candidate_id"]))
        candidates_by_hypothesis = {str(row.get("hypothesis_id")): row for row in ordered_candidates}
        achieved = [{"hypothesis_id": row.get("hypothesis_id"),
                     "achieved_capacity": row.get("achieved_capacity")}
                    for row in ordered_candidates]

        conditional = ConditionalRegulationApplicabilityEvaluationV1().evaluate(
            ordered_hypotheses,
            (regulation_evidence or {}).get("parking_size_classification"),
            (regulation_evidence or {}).get("clauses"),
            regulation_evidence,
            achieved,
        )
        pre_promotion_audit = Parcel2ParkingRampApplicabilityAuditV1().resolve(
            project_evidence, regulation_evidence, None)
        rows = []
        for evaluation in conditional["evaluations"]:
            hypothesis_id = str(evaluation.get("hypothesis_id"))
            hypothesis = next(row for row in ordered_hypotheses
                              if str(row["hypothesis_id"]) == hypothesis_id)
            candidate = candidates_by_hypothesis.get(hypothesis_id)
            eligible_for_validation = evaluation.get("hypothesis_status") != "hypothesis_rejected"
            candidate_for_gate = candidate if eligible_for_validation else None
            promotion = ValidatedDesignResultAuthorityPromotionV1().promote(
                candidate_for_gate, minimum, hypothesis)
            fact = promotion["authoritative_project_fact"]
            authoritative_audit = Parcel2ParkingRampApplicabilityAuditV1().resolve(
                project_evidence, regulation_evidence, fact)
            publication = self._publication(promotion, authoritative_audit)
            rows.append({
                "hypothesis_id": evaluation.get("hypothesis_id"),
                "target_capacity": evaluation.get("target_capacity"),
                "hypothesis_evaluation": evaluation,
                "selection": {"status": (promotion["selection_status"] if eligible_for_validation
                                           else "ineligible_hypothesis"),
                              "evidence": (deepcopy((candidate or {}).get("selection_evidence", []))
                                           if eligible_for_validation else [])},
                "validation": {"status": (promotion["validation_status"] if eligible_for_validation
                                            else "not_evaluated"),
                               "evidence": (deepcopy((candidate or {}).get("validation_evidence", []))
                                            if eligible_for_validation else []),
                               "achieved_capacity": ((candidate or {}).get("achieved_capacity")
                                                     if eligible_for_validation else None)},
                "promotion": promotion,
                "authoritative_audit": authoritative_audit,
                "publication": publication,
            })
        result.update(status="completed", minimum_required_capacity=minimum,
                      conditional_evaluation=conditional,
                      authoritative_audit_before_promotion=pre_promotion_audit,
                      lifecycles=rows)
        return self._finish(result, original, project_evidence, regulation_evidence, hypotheses, candidates)

    def _envelope(self):
        return {
            "contract": "SyntheticParkingRampLifecycleOrchestrationV1",
            "status": "rejected",
            "scope": "architecture_only_synthetic_no_geometry",
            "bounded": True,
            "limits": {"maximum_hypotheses": self.MAX_HYPOTHESES,
                       "maximum_candidates": self.MAX_CANDIDATES},
            "minimum_required_capacity": None,
            "conditional_evaluation": None,
            "authoritative_audit_before_promotion": None,
            "lifecycles": [],
            "failure_reasons": [],
            "selection_is_validation": False,
            "validation_is_promotion": False,
            "promotion_is_publication": False,
            "geometry_generated": False,
            "ramp_profile_generated": False,
            "structure_executed": False,
            "bim_executed": False,
            "ifc_executed": False,
            "render_executed": False,
            "image_generation_executed": False,
            "input_mutated": False,
        }

    @staticmethod
    def _minimum(project_evidence):
        records = (project_evidence or {}).get("evidence_records", [])
        matches = [row for row in records if isinstance(row, dict)
                   and row.get("id") == "minimum_required_parking_capacity"
                   and row.get("confirmation_status") == "confirmed"]
        if len(matches) != 1:
            return None
        value = matches[0].get("value")
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

    @staticmethod
    def _identity_failures(hypotheses, candidates):
        failures = []
        hypothesis_ids = [str(row.get("hypothesis_id")) for row in hypotheses
                          if isinstance(row, dict) and row.get("hypothesis_id") is not None]
        candidate_ids = [str(row.get("candidate_id")) for row in candidates
                         if isinstance(row, dict) and row.get("candidate_id") is not None]
        candidate_hypothesis_ids = [str(row.get("hypothesis_id")) for row in candidates
                                    if isinstance(row, dict) and row.get("hypothesis_id") is not None]
        if len(hypothesis_ids) != len(hypotheses):
            failures.append("hypothesis_identity_missing")
        if len(candidate_ids) != len(candidates):
            failures.append("candidate_identity_missing")
        if len(set(hypothesis_ids)) != len(hypothesis_ids):
            failures.append("duplicate_or_conflicting_hypothesis_ids")
        if len(set(candidate_ids)) != len(candidate_ids):
            failures.append("duplicate_or_conflicting_candidate_ids")
        if len(set(candidate_hypothesis_ids)) != len(candidate_hypothesis_ids):
            failures.append("multiple_candidates_for_hypothesis_forbidden")
        if any(hid not in set(hypothesis_ids) for hid in candidate_hypothesis_ids):
            failures.append("candidate_links_unknown_hypothesis")
        return failures

    @staticmethod
    def _publication(promotion, audit):
        promoted = promotion.get("promotion_status") == "promoted"
        slope = audit.get("slope_constraint_authority") or {}
        ready = promoted and slope.get("status") == "resolved"
        return {
            "status": "ready" if ready else "blocked",
            "published": False,
            "publication_authorized": ready,
            "blockers": [] if ready else (["promotion_required"] if not promoted else
                                           ["authoritative_ramp_slope_rule_unresolved"]),
        }

    @staticmethod
    def _finish(result, original, *current):
        result["input_mutated"] = original != current
        return result
