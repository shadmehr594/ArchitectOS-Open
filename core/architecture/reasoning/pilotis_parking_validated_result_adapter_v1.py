"""Bind accepted pilotis parking and explicit selection for authority promotion."""
from copy import deepcopy


class PilotisParkingValidatedResultAdapterV1:
    def adapt(self, producer_result=None, acceptance=None, selection=None):
        original = deepcopy((producer_result, acceptance, selection))
        producer = producer_result if isinstance(producer_result, dict) else {}
        accepted = acceptance if isinstance(acceptance, dict) else {}
        selected = selection if isinstance(selection, dict) else {}
        candidate_id = accepted.get("candidate_id")
        failures = []
        if producer.get("contract") != "PilotisParkingDesignProducerV1":
            failures.append("pilotis_producer_contract_required")
        if (accepted.get("contract") != "PilotisParkingArchitecturalAcceptanceV1"
                or accepted.get("validation_status") != "accepted"
                or accepted.get("automated_geometry_pass") is not True
                or not accepted.get("accepted_result_evidence")):
            failures.append("complete_pilotis_architectural_acceptance_required")
        if selected.get("selected_status") != "selected" or not selected.get("selection_evidence"):
            failures.append("evidence_bearing_selection_required")
        if selected.get("candidate_id") != candidate_id:
            failures.append("selection_candidate_binding_mismatch")
        matches = [x for x in producer.get("candidates", []) if x.get("candidate_id") == candidate_id]
        if len(matches) != 1:
            failures.append("producer_candidate_binding_mismatch")
        candidate = matches[0] if len(matches) == 1 else {}
        if candidate.get("hypothesis_dependencies", {}).get("ramp_not_required") != "same_level_vehicle_access_hypothesis":
            failures.append("ramp_not_required_hypothesis_dependency_required")
        achieved = accepted.get("certified_achieved_capacity")
        candidate_capacity = candidate.get("achieved_capacity_candidate")
        if (not isinstance(achieved, int) or isinstance(achieved, bool)
                or achieved < 0 or achieved != candidate_capacity):
            failures.append("certified_capacity_candidate_binding_mismatch")
        result = {"contract": self.__class__.__name__, "status": "rejected" if failures else "adapted",
                  "candidate": None, "failure_reasons": sorted(set(failures)),
                  "selection_performed": False, "geometry_copied": False, "input_mutated": False}
        if not failures:
            result["candidate"] = {
                "candidate_id": candidate_id, "candidate_status": "design_result",
                "selected_status": "selected", "selection_evidence": deepcopy(selected["selection_evidence"]),
                "validation_status": "accepted",
                "validation_evidence": deepcopy(accepted["accepted_result_evidence"]),
                "achieved_capacity": achieved,
                "achieved_capacity_evidence": deepcopy(accepted["accepted_result_evidence"]),
                "hypothesis_id": candidate.get("hypothesis_id"),
                "provenance": deepcopy(candidate.get("authoritative_input_provenance")) + [
                    {"contract": accepted["contract"], "candidate_id": candidate_id},
                    {"contract": self.__class__.__name__}],
            }
        result["input_mutated"] = original != (producer_result, acceptance, selection)
        return result
