"""Fail-closed architectural acceptance for pilotis parking candidates."""
from copy import deepcopy


class PilotisParkingArchitecturalAcceptanceV1:
    def evaluate(self, producer_result=None, candidate_id=None, minimum_required_capacity=None):
        original = deepcopy((producer_result, candidate_id, minimum_required_capacity))
        producer = producer_result if isinstance(producer_result, dict) else {}
        matches = [x for x in producer.get("candidates", [])
                   if isinstance(x, dict) and x.get("candidate_id") == candidate_id]
        candidate = matches[0] if len(matches) == 1 else {}
        stalls = candidate.get("stall_geometries")
        access = candidate.get("vehicle_access_evidence") or {}
        movement = candidate.get("manoeuvre_aisle_circulation_evidence") or {}
        ingress = candidate.get("stall_ingress_egress_evidence") or {}
        pedestrian = candidate.get("pedestrian_safety_evidence") or {}
        compatibility = candidate.get("compatibility_evidence") or {}
        capacity = len(stalls) if isinstance(stalls, list) else None
        compatibility_kinds = ("core", "entrance", "protected_zone", "commercial",
                               "public_use", "private_use")
        checks = {
            "producer_contract": producer.get("contract") == "PilotisParkingDesignProducerV1"
                and producer.get("status") == "candidates_produced",
            "candidate_identity_binding": len(matches) == 1 and bool(candidate_id),
            "pilotis_floor_scope": candidate.get("floor_scope") in ("pilotis", "ground_level_parking"),
            "authoritative_input_provenance": bool(candidate.get("authoritative_input_provenance")),
            "candidate_geometry": candidate.get("candidate_geometry_status") == "candidate_complete",
            "minimum_capacity": self._integer(capacity) and self._integer(minimum_required_capacity)
                and capacity >= minimum_required_capacity,
            "resolved_vehicle_access": access.get("status") == "resolved"
                and bool(access.get("endpoint")) and bool(access.get("evidence")),
            "connected_manoeuvre_aisle_circulation": movement.get("status") == "resolved"
                and movement.get("connected") is True and bool(movement.get("evidence")),
            "stall_ingress_egress": ingress.get("status") == "resolved"
                and ingress.get("all_stalls_independently_usable") is True
                and bool(ingress.get("evidence")),
            "pedestrian_safety": pedestrian.get("status") == "clear"
                and pedestrian.get("mandatory_route_blocked") is False
                and not pedestrian.get("conflicts") and bool(pedestrian.get("evidence")),
            "core_entrance_protected_use_compatibility": compatibility.get("inventory_complete") is True
                and not compatibility.get("conflicts")
                and all(compatibility.get(kind) == "clear" for kind in compatibility_kinds)
                and bool(compatibility.get("evidence")),
        }
        failed = [name for name, passed in checks.items() if not passed]
        accepted = not failed
        evidence = [{"source": self.__class__.__name__, "candidate_id": candidate_id,
                     "checks": deepcopy(checks), "parking_stall_count": capacity,
                     "floor_scope": candidate.get("floor_scope")}] if accepted else []
        result = {
            "contract": self.__class__.__name__, "source": self.__class__.__name__,
            "candidate_id": candidate_id, "candidate_geometry_status": candidate.get("candidate_geometry_status"),
            "validation_status": "accepted" if accepted else "failed",
            "selected_status": candidate.get("selected_status", "not_selected"),
            "automated_geometry_pass": accepted, "checks": checks, "failed_checks": failed,
            "achieved_parking_capacity_candidate": capacity,
            "certified_achieved_capacity": capacity if accepted else None,
            "accepted_result_evidence": evidence,
            "producer_provenance": deepcopy(candidate.get("authoritative_input_provenance") or []),
            "basement_deleted": False, "basement_necessity_evaluated": False,
            "input_mutated": False,
        }
        result["input_mutated"] = original != (producer_result, candidate_id, minimum_required_capacity)
        return result

    @staticmethod
    def _integer(value):
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0
