"""Fail-closed adapter from a real parking/ramp producer result to the promotion gate."""
from copy import deepcopy


class RealParkingRampValidatedResultAdapterV1:
    """Bind producer selection to acceptance and ramp evidence without selecting anything."""

    def adapt(self, producer_result=None, acceptance=None, slope_validation=None,
              endpoint_binding=None, hypothesis_id=None):
        original = deepcopy((producer_result, acceptance, slope_validation,
                             endpoint_binding, hypothesis_id))
        producer = producer_result if isinstance(producer_result, dict) else {}
        accepted = acceptance if isinstance(acceptance, dict) else {}
        selected = producer.get("selected_candidate")
        failures = []
        if producer.get("source") != "BasementRampParkingDesignReasonerV2":
            failures.append("supported_real_producer_contract_required")
        if producer.get("selection_status") != "resolved" or not isinstance(selected, dict):
            failures.append("producer_selected_candidate_required")
        candidate_id = selected.get("candidate_id") if isinstance(selected, dict) else None
        if not candidate_id:
            failures.append("candidate_identity_missing")
        if accepted.get("source") != "BasementVehicleArchitecturalAcceptanceV2":
            failures.append("architectural_acceptance_contract_required")
        if accepted.get("validation_status") != "accepted" or accepted.get("automated_geometry_pass") is not True:
            failures.append("complete_architectural_acceptance_required")
        if accepted.get("human_visual_acceptance") not in ("accepted", "not_required"):
            failures.append("human_visual_acceptance_or_explicit_not_required_required")
        if candidate_id != accepted.get("candidate_id"):
            failures.append("acceptance_candidate_binding_mismatch")
        achieved = accepted.get("achieved_parking_capacity")
        if not isinstance(achieved, int) or isinstance(achieved, bool) or achieved < 0:
            failures.append("accepted_achieved_parking_capacity_required")
        if not accepted.get("accepted_result_evidence"):
            failures.append("accepted_result_evidence_required")
        if not isinstance(endpoint_binding, dict) or endpoint_binding.get("contract") != "AuthoritativeRampEndpointBindingContractV1" or endpoint_binding.get("status") != "resolved" or endpoint_binding.get("binding_resolved") is not True:
            failures.append("authoritative_endpoint_binding_required")
        if not isinstance(slope_validation, dict) or slope_validation.get("contract") != "RampSlopeProfileValidationV1" or slope_validation.get("status") != "validated" or slope_validation.get("slope_validated") is not True:
            failures.append("validated_ramp_slope_profile_required")
        provenance = deepcopy(producer.get("provenance") or [])
        if not provenance:
            failures.append("producer_provenance_required")
        result = {
            "contract": self.__class__.__name__, "status": "rejected" if failures else "adapted",
            "candidate": None, "failure_reasons": sorted(set(failures)),
            "selection_performed": False, "geometry_copied": False, "input_mutated": False,
        }
        if not failures:
            result["candidate"] = {
                "candidate_id": candidate_id, "candidate_status": "design_result",
                "selected_status": "selected",
                "selection_evidence": [{"source": producer.get("source"),
                                        "selection_status": producer.get("selection_status"),
                                        "candidate_id": candidate_id}],
                "validation_status": "accepted",
                "validation_evidence": deepcopy(accepted["accepted_result_evidence"]) + [{
                    "contract": slope_validation["contract"], "status": slope_validation["status"],
                    "endpoint_binding": deepcopy(endpoint_binding),
                }],
                "achieved_capacity": achieved,
                "achieved_capacity_evidence": deepcopy(accepted["accepted_result_evidence"]),
                "hypothesis_id": hypothesis_id,
                "provenance": provenance + [{"contract": accepted["source"],
                    "candidate_id": candidate_id}, {"contract": self.__class__.__name__}],
            }
        result["input_mutated"] = original != (producer_result, acceptance, slope_validation,
                                                 endpoint_binding, hypothesis_id)
        return result
