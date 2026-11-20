"""Fail-closed elevator sizing authority resolution for Architecture only."""
from copy import deepcopy


class AuthoritativeElevatorSizingResolutionV1:
    """Consume design confirmation and official evidence without selecting equipment."""

    CONTRACT = "AuthoritativeElevatorSizingResolutionV1"
    FORBIDDEN_SHAFTS_MM = {(1800, 1800)}

    def resolve(self, *, project_evidence, regulation_evidence, elevator_required):
        project = deepcopy(project_evidence)
        regulation = deepcopy(regulation_evidence)
        selection = self._count_selection(project)
        rules = {r.get("rule_id"): r for r in regulation.get("evidence_records", [])}
        access_rule = rules.get("topic15_15_2_1_5_accessible_elevator", {})
        minima_rule = rules.get("topic15_15_2_1_9_accessible_car_and_door_minima", {})
        traffic_rule = rules.get("topic15_15_2_1_12_traffic_calculation_dependency", {})
        shaft_rule = rules.get("topic15_15_2_2_2_1_shaft_dependency", {})
        minima = deepcopy(minima_rule.get("requirement", {}))
        count = selection["elevator"]["count"]["value"]
        if count != 1:
            raise ValueError("approved Parcel 2 elevator count must be exactly 1")
        if tuple(minima.get("cabin_minimum_mm", {}).values()) in self.FORBIDDEN_SHAFTS_MM:
            raise ValueError("legacy 1.8x1.8 shaft leakage is forbidden")
        official = all(r.get("authority_class") == "HARD_REGULATION" for r in
                       (access_rule, minima_rule, traffic_rule, shaft_rule))
        if not official:
            raise ValueError("complete authoritative Topic 15 evidence is required")
        unresolved = ["rated_capacity", "system_type", "speed", "door_type_or_arrangement"]
        return {
            "contract": self.CONTRACT,
            "project_id": project.get("project_id"),
            "elevator_required": {"status": "RESOLVED_REQUIRED", "value": bool(elevator_required)},
            "count": {
                "status": "RESOLVED_DESIGN_CONFIRMATION", "value": count,
                "authority_class": selection["authority_class"],
                "source_kind": selection["source_kind"],
                "source_reference": selection["source_reference"],
                "provenance": deepcopy(selection["provenance"]),
            },
            "accessibility": {
                "status": "RESOLVED_REQUIRED", "minimum_accessible_count": 1,
                "cabin_minimum_mm": minima["cabin_minimum_mm"],
                "clear_door_minimum_mm": minima["clear_door_minimum_mm"],
                "provenance": [
                    {"contract": regulation["contract"], "clause": access_rule["clause"],
                     "source_reference": regulation["source_reference"]},
                    {"contract": regulation["contract"], "clause": minima_rule["clause"],
                     "source_reference": regulation["source_reference"]},
                ],
            },
            "capacity_options": {"status": "UNRESOLVED", "candidates": [],
                "dependencies": ["traffic_calculation"], "provenance": [{"clause": traffic_rule["clause"]}]},
            "shaft_options": {"status": "UNRESOLVED", "candidates": [],
                "dependencies": deepcopy(shaft_rule["requirement"]["shaft_dependencies"]),
                "provenance": [{"clause": shaft_rule["clause"]}]},
            "equipment_selection": {"type": None, "model": None, "speed": None,
                "door_arrangement": None, "status": "UNRESOLVED"},
            "machine_room_status": {"mr_mrl": None, "status": "UNRESOLVED"},
            "appendix_2": {"status": "DEPENDENCIES_UNRESOLVED", "candidates": [],
                "unresolved_dependencies": unresolved},
            "legacy_1_8x1_8_used": False,
            "lobby_sizing_gate": "STOP_ELEVATOR_SIZING_NOT_LEGITIMATELY_RESOLVED_OR_RANGED",
            "core_reservation_gate": "STOP_ELEVATOR_SIZING_NOT_LEGITIMATELY_RESOLVED_OR_RANGED",
            "geometry_generated": False,
            "input_mutated": False,
        }

    @staticmethod
    def _count_selection(project):
        matches = [r for r in project.get("evidence_records", [])
                   if r.get("id") == "elevator_count_selection"]
        if len(matches) != 1:
            raise ValueError("exactly one elevator count design confirmation is required")
        record = matches[0]
        required = {
            "authority_class": "DESIGN_CONFIRMATION",
            "source_kind": "human_confirmed_design_selection",
            "confirmation_status": "confirmed",
        }
        if any(record.get(k) != v for k, v in required.items()):
            raise ValueError("invalid elevator count design confirmation authority")
        exclusions = set(record.get("scope_exclusions", []))
        needed = {"rated_capacity_persons", "rated_capacity_kg", "type", "model", "speed",
                  "door_arrangement", "shaft_geometry", "machine_room_status", "mr_mrl"}
        if not needed.issubset(exclusions) or not record.get("source_reference") or not record.get("provenance"):
            raise ValueError("elevator count confirmation scope or provenance is incomplete")
        return record
