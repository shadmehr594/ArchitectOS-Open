"""Contract adapter for ground-level/pilotis parking design evidence."""
from copy import deepcopy


class PilotisParkingDesignProducerV1:
    """Normalize geometry-engine results; never validate, select, or promote them."""

    FLOOR_SCOPES = {"pilotis", "ground_level_parking"}

    def produce(self, hypothesis_id=None, floor_scope=None, candidates=None,
                authoritative_input_provenance=None, hypothesis_dependencies=None):
        original = deepcopy((hypothesis_id, floor_scope, candidates,
                             authoritative_input_provenance, hypothesis_dependencies))
        provenance = deepcopy(authoritative_input_provenance or [])
        dependencies = deepcopy(hypothesis_dependencies or {})
        failures = []
        if not hypothesis_id:
            failures.append("hypothesis_identity_required")
        if floor_scope not in self.FLOOR_SCOPES:
            failures.append("pilotis_or_ground_level_parking_scope_required")
        if not provenance or not all(isinstance(x, dict) and x.get("source") for x in provenance):
            failures.append("authoritative_input_provenance_required")
        if dependencies.get("ramp_not_required") != "same_level_vehicle_access_hypothesis":
            failures.append("ramp_not_required_hypothesis_dependency_required")

        normalized = [self._candidate(x, hypothesis_id, floor_scope, provenance, dependencies)
                      for x in (candidates or []) if isinstance(x, dict)]
        normalized.sort(key=lambda x: (-x["deterministic_ranking_metadata"]["candidate_capacity"],
                                       x["candidate_id"] or ""))
        for index, candidate in enumerate(normalized, 1):
            candidate["deterministic_ranking_metadata"]["rank"] = index
        if not normalized:
            failures.append("candidate_evidence_required")
        result = {
            "contract": self.__class__.__name__, "source": self.__class__.__name__,
            "status": "candidates_produced" if not failures else "pending_evidence",
            "hypothesis_id": hypothesis_id, "floor_scope": floor_scope,
            "authoritative_input_provenance": provenance,
            "hypothesis_dependencies": dependencies, "candidates": normalized,
            "selected_candidate": None, "selection_status": "not_performed",
            "validation_status": "not_performed", "promotion_status": "not_performed",
            "basement_deleted": False, "basement_necessity_evaluated": False,
            "failure_reasons": sorted(set(failures)), "input_mutated": False,
        }
        result["input_mutated"] = original != (hypothesis_id, floor_scope, candidates,
                                                authoritative_input_provenance,
                                                hypothesis_dependencies)
        return result

    def _candidate(self, raw, hypothesis_id, floor_scope, provenance, dependencies):
        stalls = deepcopy(raw.get("stall_geometries") or [])
        return {
            "candidate_id": raw.get("candidate_id"), "hypothesis_id": hypothesis_id,
            "floor_scope": floor_scope, "candidate_status": "candidate_evidence",
            "candidate_geometry_status": raw.get("candidate_geometry_status", "unknown"),
            "stall_geometries": stalls, "achieved_capacity_candidate": len(stalls),
            "vehicle_access_evidence": deepcopy(raw.get("vehicle_access_evidence")),
            "manoeuvre_aisle_circulation_evidence": deepcopy(raw.get("manoeuvre_aisle_circulation_evidence")),
            "stall_ingress_egress_evidence": deepcopy(raw.get("stall_ingress_egress_evidence")),
            "pedestrian_safety_evidence": deepcopy(raw.get("pedestrian_safety_evidence")),
            "compatibility_evidence": deepcopy(raw.get("compatibility_evidence")),
            "authoritative_input_provenance": deepcopy(provenance),
            "hypothesis_dependencies": deepcopy(dependencies),
            "deterministic_ranking_metadata": {
                "method": "capacity_descending_then_candidate_id_ascending",
                "candidate_capacity": len(stalls), "rank": None,
            },
            "selected_status": "not_selected", "validation_status": "not_validated",
            "authority_class": "NON_AUTHORITATIVE_DESIGN_CANDIDATE",
        }
