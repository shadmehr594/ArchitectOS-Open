"""Evidence-gated elevator requirement reasoning for Architecture.

This resolver deliberately keeps semantic requirements separate from regulatory
height requirements.  A height rule is never inferred from a numeric threshold
alone: its authority, source, provenance, comparison and measurement datum must
all be explicit.
"""
from copy import deepcopy
import math


class ElevatorRegulationRequirementReasoningV1:
    """Resolve independent elevator triggers without producing sizing claims."""

    REGULATION_AUTHORITIES = frozenset(("HARD_REGULATION",))
    EXCLUDED_OCCUPIABLE_TOKENS = frozenset(
        ("roof", "stairhouse", "machine_room", "elevator_room", "penthouse")
    )

    def resolve(
        self,
        level_contract=None,
        building_type=None,
        requirements=None,
        regulation_evidence=None,
        occupiable_levels=None,
    ):
        source_contract = deepcopy(level_contract or {})
        source_requirements = deepcopy(requirements or [])
        source_regulation = deepcopy(regulation_evidence)
        source_occupiable = deepcopy(occupiable_levels)

        exact_levels = source_contract.get("exact_levels", {})
        if not isinstance(exact_levels, dict):
            exact_levels = {}
        usable_levels = {
            str(name): float(value)
            for name, value in exact_levels.items()
            if self._finite(value)
        }
        occupied = self._resolve_occupiable_levels(usable_levels, source_occupiable)

        normalized_type = str(building_type or "").strip().lower()
        normalized_requirements = {
            str(item).strip().lower() for item in source_requirements
            if isinstance(item, str)
        }
        multi_level = len(occupied) > 1
        semantic_trigger = multi_level and normalized_type in {
            "commercial", "mixed_use", "mixed_use_commercial_residential"
        }
        explicit_trigger = bool({"elevator", "lift"} & normalized_requirements)
        accessibility_trigger = bool({
            "accessible", "accessibility", "disabled_access",
            "wheelchair_access", "universal_access",
        } & normalized_requirements)

        height_result = self._resolve_height_trigger(
            usable_levels, occupied, source_regulation
        )
        triggers = []
        if explicit_trigger:
            triggers.append({
                "trigger": "explicit_project_requirement",
                "reason_code": "ELEVATOR_EXPLICITLY_REQUIRED",
                "evidence_path": "requirements",
                "authority_class": "PROJECT_REQUIREMENT",
                "provenance": ["requirements"],
            })
        if accessibility_trigger:
            triggers.append({
                "trigger": "accessibility_requirement",
                "reason_code": "ELEVATOR_REQUIRED_FOR_ACCESSIBILITY",
                "evidence_path": "requirements",
                "authority_class": "PROJECT_REQUIREMENT",
                "provenance": ["requirements"],
            })
        if semantic_trigger:
            triggers.append({
                "trigger": "multilevel_commercial_semantic",
                "reason_code": "ELEVATOR_REQUIRED_MULTILEVEL_COMMERCIAL_SEMANTIC",
                "evidence_path": "decision_context.building_type_and_occupiable_levels",
                "authority_class": "SEMANTIC_INFERENCE",
                "provenance": ["building_type", "project_level_contract"],
            })
        if height_result["triggered"]:
            triggers.append({
                "trigger": "regulatory_height",
                "reason_code": "ELEVATOR_REQUIRED_REGULATORY_HEIGHT",
                "evidence_path": height_result["evidence_path"],
                "authority_class": height_result["authority_class"],
                "provenance": deepcopy(height_result["provenance"]),
            })

        return {
            "contract": "ElevatorRegulationRequirementReasoningV1",
            "status": "resolved" if height_result["status"] != "invalid_regulation_input"
            else "invalid_regulation_input",
            "elevator_required": bool(triggers),
            "active_triggers": triggers,
            "semantic_trigger": {
                "triggered": semantic_trigger,
                "reason_code": "ELEVATOR_REQUIRED_MULTILEVEL_COMMERCIAL_SEMANTIC",
                "evidence_path": "decision_context.building_type_and_occupiable_levels",
            },
            "regulatory_height_trigger": height_result,
            "occupiable_height_context": {
                "occupiable_levels": occupied,
                "highest_occupiable_level": max(occupied, key=occupied.get) if occupied else None,
                "highest_occupiable_elevation_m": max(occupied.values()) if occupied else None,
                "default_exclusions": sorted(self.EXCLUDED_OCCUPIABLE_TOKENS),
                "roof_and_stairhouse_excluded_by_default": True,
            },
            "elevator_count": None,
            "elevator_capacity": None,
            "sizing_status": "independent_evidence_required",
            "geometry_generated": False,
            "input_mutated": False,
        }

    def _resolve_height_trigger(self, levels, occupied, evidence):
        invalid = self._regulation_problem(evidence)
        if invalid:
            return {
                "status": "regulation_input_required" if evidence is None else "invalid_regulation_input",
                "triggered": False,
                "reason_code": "ELEVATOR_HEIGHT_REGULATION_INPUT_REQUIRED",
                "problem": invalid,
                "threshold_m": None,
                "measurement_datum_level": None,
                "measured_height_m": None,
                "evidence_path": None,
                "authority_class": None,
                "provenance": [],
            }

        datum = evidence["measurement_datum_level"]
        if datum not in levels or not occupied:
            return {
                "status": "unresolved_level_dependency",
                "triggered": False,
                "reason_code": "ELEVATOR_HEIGHT_LEVEL_INPUT_REQUIRED",
                "problem": "measurement datum or occupiable level is unavailable",
                "threshold_m": float(evidence["threshold_m"]),
                "measurement_datum_level": datum,
                "measured_height_m": None,
                "evidence_path": evidence["evidence_path"],
                "authority_class": evidence["authority_class"],
                "provenance": deepcopy(evidence["provenance"]),
            }
        measured = max(occupied.values()) - levels[datum]
        threshold = float(evidence["threshold_m"])
        comparison = evidence["comparison"]
        triggered = measured > threshold if comparison == "greater_than" else measured >= threshold
        return {
            "status": "resolved",
            "triggered": triggered,
            "reason_code": "ELEVATOR_REQUIRED_REGULATORY_HEIGHT" if triggered
            else "ELEVATOR_REGULATORY_HEIGHT_NOT_EXCEEDED",
            "problem": None,
            "threshold_m": threshold,
            "comparison": comparison,
            "measurement_datum_level": datum,
            "highest_occupiable_level": max(occupied, key=occupied.get),
            "measured_height_m": round(measured, 9),
            "evidence_path": evidence["evidence_path"],
            "authority_class": evidence["authority_class"],
            "provenance": deepcopy(evidence["provenance"]),
        }

    def _regulation_problem(self, evidence):
        if evidence is None:
            return "authoritative elevator height regulation evidence is missing"
        if not isinstance(evidence, dict):
            return "regulation evidence must be a mapping"
        if evidence.get("authority_class") not in self.REGULATION_AUTHORITIES:
            return "regulation authority is not HARD_REGULATION"
        if not evidence.get("source_reference") or not evidence.get("provenance"):
            return "regulation source reference or provenance is missing"
        if not evidence.get("evidence_path"):
            return "regulation evidence path is missing"
        if evidence.get("comparison") not in ("greater_than", "greater_than_or_equal"):
            return "regulation comparison is missing or unsupported"
        if not evidence.get("measurement_datum_level"):
            return "regulation measurement datum is missing"
        if not self._finite(evidence.get("threshold_m")) or float(evidence["threshold_m"]) < 0:
            return "regulation threshold is missing or invalid"
        return None

    def _resolve_occupiable_levels(self, levels, explicit):
        if explicit is not None:
            names = [str(name) for name in explicit if str(name) in levels]
        else:
            names = [
                name for name in levels
                if not any(token in name.lower() for token in self.EXCLUDED_OCCUPIABLE_TOKENS)
                and not name.lower().startswith(("site", "ramp", "basement"))
            ]
        return dict(sorted((name, levels[name]) for name in names))

    @staticmethod
    def _finite(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
