"""Architecture-only integration of a real producer with the authority lifecycle."""
from copy import deepcopy

from core.architecture.reasoning.parcel2_parking_ramp_applicability_audit_v1 import Parcel2ParkingRampApplicabilityAuditV1
from core.architecture.reasoning.real_parking_ramp_validated_result_adapter_v1 import RealParkingRampValidatedResultAdapterV1
from core.architecture.reasoning.validated_design_result_authority_promotion_v1 import ValidatedDesignResultAuthorityPromotionV1


class RealParkingRampLifecycleIntegrationV1:
    def run(self, project_evidence=None, regulation_evidence=None, hypothesis=None,
            producer_result=None, acceptance=None, slope_validation=None, endpoint_binding=None):
        original = deepcopy((project_evidence, regulation_evidence, hypothesis, producer_result,
                             acceptance, slope_validation, endpoint_binding))
        minimum = self._minimum(project_evidence)
        adapter = RealParkingRampValidatedResultAdapterV1().adapt(
            producer_result, acceptance, slope_validation, endpoint_binding,
            (hypothesis or {}).get("hypothesis_id"))
        promotion = ValidatedDesignResultAuthorityPromotionV1().promote(
            adapter.get("candidate"), minimum, hypothesis)
        fact = promotion.get("authoritative_project_fact")
        audit = Parcel2ParkingRampApplicabilityAuditV1().resolve(
            project_evidence, regulation_evidence, fact)
        slope = audit.get("slope_constraint_authority") or {}
        ready = promotion.get("promotion_status") == "promoted" and slope.get("status") == "resolved"
        result = {
            "contract": self.__class__.__name__, "status": "completed",
            "adapter": adapter, "promotion": promotion, "authoritative_audit": audit,
            "publication": {"status": "ready" if ready else "blocked", "published": False,
                            "publication_authorized": ready},
            "auto_selection_performed": False, "selection_is_validation": False,
            "validation_is_promotion": False, "promotion_is_publication": False,
            "candidate_geometry_exposed_to_authoritative_audit": False,
            "structure_executed": False, "bim_executed": False, "ifc_executed": False,
            "render_executed": False, "input_mutated": False,
        }
        result["input_mutated"] = original != (project_evidence, regulation_evidence, hypothesis,
                                                producer_result, acceptance, slope_validation,
                                                endpoint_binding)
        return result

    @staticmethod
    def _minimum(project_evidence):
        rows = (project_evidence or {}).get("evidence_records", [])
        matches = [row for row in rows if isinstance(row, dict)
                   and row.get("id") == "minimum_required_parking_capacity"
                   and row.get("confirmation_status") == "confirmed"]
        value = matches[0].get("value") if len(matches) == 1 else None
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
