"""Parcel 2 Architecture-only parking/ramp evidence checkpoint."""
from copy import deepcopy

from core.architecture.reasoning.parking_size_classification_authority_v1 import ParkingSizeClassificationAuthorityV1
from core.architecture.reasoning.ramp_vehicle_slope_constraint_authority_v1 import RampVehicleSlopeConstraintAuthorityV1


class Parcel2ParkingRampApplicabilityAuditV1:
    REQUIRED = {"parking_ownership", "minimum_required_parking_capacity", "ramp_enclosure"}

    def resolve(self, project_evidence=None, regulation_evidence=None, authoritative_capacity_evidence=None):
        original = deepcopy((project_evidence, regulation_evidence, authoritative_capacity_evidence))
        records = {r.get("id"): deepcopy(r) for r in (project_evidence or {}).get("evidence_records", [])
                   if isinstance(r, dict)}
        facts = {"ramp_use": self._project_fact("ramp_use", "vehicle_parking", project_evidence,
                                                 "checkpoint_scope_vehicle_parking")}
        for item_id in sorted(self.REQUIRED):
            facts[item_id] = self._record_fact(records.get(item_id), project_evidence)
        classification = ParkingSizeClassificationAuthorityV1().resolve(
            regulation_evidence, authoritative_capacity_evidence)
        facts["authoritative_achieved_or_final_capacity"] = self._capacity_fact(authoritative_capacity_evidence)
        facts["parking_size_class"] = self._classification_fact(classification)
        slope_facts = {"ramp_use": facts["ramp_use"], "parking_ownership": facts["parking_ownership"],
                       "ramp_enclosure": facts["ramp_enclosure"], "parking_size_class": facts["parking_size_class"]}
        applicability = {"contract": "ParkingRampApplicabilityAuditV1", "facts": slope_facts}
        slope = RampVehicleSlopeConstraintAuthorityV1().resolve(regulation_evidence, applicability)
        result = {
            "contract": "Parcel2ParkingRampApplicabilityAuditV1", "status": "resolved_checkpoint",
            "scope": "architecture_only_evidence_and_authority", "project_id": "parcel_2",
            "facts": facts, "parking_size_classification": classification,
            "slope_applicability_audit": applicability, "slope_constraint_authority": slope,
            "transition_status": "unresolved" if slope["status"] != "resolved" else "resolved",
            "blocker_next": ("authoritative_achieved_or_final_parking_capacity"
                             if classification["status"] != "resolved" else
                             ("explicit_regulation_clause_for_resolved_applicability" if slope["status"] != "resolved" else None)),
            "geometry_generated": False, "ramp_profile_generated": False, "ramp_placement_generated": False,
            "parking_integration_geometry_generated": False, "rooms_generated": False, "windows_generated": False,
            "structure_executed": False, "bim_executed": False, "ifc_executed": False,
            "render_executed": False, "image_generation_executed": False, "input_mutated": False,
        }
        result["input_mutated"] = original != (project_evidence, regulation_evidence, authoritative_capacity_evidence)
        return result

    @staticmethod
    def _record_fact(record, contract):
        if not isinstance(record, dict) or record.get("confirmation_status") != "confirmed":
            return {"status": "unresolved", "value": None, "authority_class": None, "provenance": [],
                    "failure_reasons": ["confirmed_project_requirement_missing"]}
        return {"status": "resolved", "value": deepcopy(record.get("value")),
                "semantic": record.get("semantic"), "authority_class": "PROJECT_REQUIREMENT",
                "source_kind": record.get("source_kind"), "provenance": [{
                    "contract": contract.get("contract"), "source": contract.get("source"),
                    "source_path": (record.get("source_path") or contract.get("source_path")) + "#" + record["key"],
                    "key": record["key"]}]}

    @staticmethod
    def _project_fact(name, value, contract, key):
        return {"status": "resolved", "value": value, "authority_class": "PROJECT_REQUIREMENT",
                "source_kind": "explicit_project_scope", "provenance": [{"contract": contract.get("contract"), "key": key}]}

    @staticmethod
    def _capacity_fact(fact):
        if not isinstance(fact, dict) or fact.get("status") != "resolved":
            return {"status": "unresolved", "value": None, "authority_class": None, "provenance": [],
                    "failure_reasons": ["authoritative_achieved_or_final_capacity_unresolved"]}
        return deepcopy(fact)

    @staticmethod
    def _classification_fact(result):
        if result["status"] != "resolved":
            return {"status": "unresolved", "value": None, "authority_class": None,
                    "source_kind": "regulation", "provenance": [], "failure_reasons": deepcopy(result["failure_reasons"])}
        return {"status": "resolved", "value": result["parking_size_class"],
                "authority_class": "HARD_REGULATION", "source_kind": "regulation",
                "provenance": deepcopy(result["provenance"])}
