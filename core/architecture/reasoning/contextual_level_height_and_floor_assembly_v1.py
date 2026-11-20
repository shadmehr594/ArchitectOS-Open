"""Evidence-bearing, range-based architectural level semantics; no geometry."""
from copy import deepcopy
import math
from .project_level_contract_v1 import ProjectLevelContractV1


class ContextualLevelHeightAndFloorAssemblyV1:
    AUTHORITY_CLASSES = (
        "HARD_REGULATION", "PROJECT_REQUIREMENT", "HUMAN_CONFIRMED_DESIGN_RANGE",
        "KNOWLEDGE_DERIVED_RANGE", "SYSTEM_PREFERENCE",
    )
    COMPONENTS = (
        "usable_height", "floor_assembly_thickness",
        "finished_floor_raise_above_grade", "finished_floor_raise_above_road",
        "basement_ceiling_above_grade",
    )
    HUMAN_CONFIRMED_RANGES = (
        ("commercial_usable_height", "usable_height", (3.60, 4.70), ("commercial", "pilotis")),
        ("residential_usable_height", "usable_height", (2.90, 3.40), ("residential",)),
        ("residential_raised_ffl_plinth", "finished_floor_raise_above_grade", (.36, .40), ("residential",)),
        ("garden_house_special_raised_ffl", "finished_floor_raise_above_grade", (.60, .90), ("garden_house",)),
        ("commercial_pilotis_drainage_raise", "finished_floor_raise_above_road", (.10, .20), ("commercial", "pilotis")),
        ("basement_ceiling_above_grade_observed", "basement_ceiling_above_grade", (.20, 1.40), ("basement",)),
    )

    def resolve(self, context=None):
        source = deepcopy(context or {})
        occupancies = tuple(sorted(set(source.get("occupancies", []))))
        evidence = self._explicit_evidence(source)
        evidence.extend(self._knowledge_evidence(occupancies))
        fields = {name: self._field(name, evidence, source) for name in self.COMPONENTS}
        floor_to_floor = self._floor_to_floor(fields)
        project_levels = ProjectLevelContractV1().resolve(
            source.get("level_contract"), source.get("human_level_confirmations"),
            floor_to_floor["hypotheses"])
        return {
            "contract": "ContextualLevelHeightAndFloorAssemblyV1",
            "architecture_only": True,
            "authority_classes": list(self.AUTHORITY_CLASSES),
            "fields": fields,
            "floor_to_floor": floor_to_floor,
            "project_level_contract": project_levels,
            "unresolved_inputs": self._unresolved(fields, floor_to_floor, source),
            "drainage_alternatives": ["grading", "site_drainage", "entrance_threshold", "finished_floor_raise_above_road"],
            "geometry_generated": False,
            "input_mutated": source != (context or {}),
        }

    def _knowledge_evidence(self, occupancies):
        records = []
        for evidence_id, component, bounds, applies_to in self.HUMAN_CONFIRMED_RANGES:
            if occupancies and not set(occupancies).intersection(applies_to):
                continue
            records.append({
                "evidence_id": evidence_id, "component": component,
                "range": {"min": bounds[0], "max": bounds[1]}, "unit": "m",
                "authority_class": "HUMAN_CONFIRMED_DESIGN_RANGE",
                "provenance": ["human_confirmed_architectural_design_knowledge_checkpoint"],
                "applicability": {"occupancies": list(applies_to), "status": "contextual"},
                "confidence": 1.0,
            })
        return records

    @staticmethod
    def _explicit_evidence(source):
        records = source.get("evidence", [])
        return deepcopy(records) if isinstance(records, list) else []

    def _field(self, component, evidence, source):
        candidates = []
        for item in evidence:
            if not isinstance(item, dict) or item.get("component") != component:
                continue
            normalized = self._normalize(item)
            if normalized:
                candidates.append(normalized)
        rejected = []
        if component == "finished_floor_raise_above_road":
            applicable = self._drainage_applicable(source)
            if not applicable:
                rejected = deepcopy(candidates)
                candidates = []
                reason = "site_runoff_or_adjacent_datum_risk_evidence_required"
            else:
                reason = None
        else:
            reason = None
        return {"status": "candidate_range" if candidates else "unresolved", "candidates": candidates,
                "rejected_candidates": rejected, "applicability_reason": reason}

    def _floor_to_floor(self, fields):
        usable = fields["usable_height"]["candidates"]
        assembly = fields["floor_assembly_thickness"]["candidates"]
        hypotheses = []
        for height in usable:
            for build_up in assembly:
                lo = round(height["range"]["min"] + build_up["range"]["min"], 9)
                hi = round(height["range"]["max"] + build_up["range"]["max"], 9)
                hypotheses.append({
                    "range": {"min": lo, "max": hi}, "unit": "m",
                    "components": [height["evidence_id"], build_up["evidence_id"]],
                    "provenance": list(dict.fromkeys(height["provenance"] + build_up["provenance"])),
                    "status": "hypothesis_not_exact_level",
                })
        return {"status": "hypotheses_available" if hypotheses else "partial_unresolved",
                "hypotheses": hypotheses,
                "excluded_components": ["finished_floor_raise_above_grade", "finished_floor_raise_above_road", "basement_ceiling_above_grade"],
                "derivation_rule": "usable_height_plus_compatible_floor_assembly_only"}

    def _normalize(self, item):
        authority = item.get("authority_class")
        if authority not in self.AUTHORITY_CLASSES or not item.get("provenance"):
            return None
        raw = item.get("range")
        if raw is None and self._finite(item.get("value")):
            raw = {"min": float(item["value"]), "max": float(item["value"])}
        if not isinstance(raw, dict) or not self._finite(raw.get("min")) or not self._finite(raw.get("max")):
            return None
        lo, hi = float(raw["min"]), float(raw["max"])
        if lo < 0 or hi < lo:
            return None
        return {"evidence_id": item.get("evidence_id", item["component"]), "range": {"min": lo, "max": hi},
                "unit": item.get("unit", "m"), "authority_class": authority,
                "provenance": deepcopy(item["provenance"]), "applicability": deepcopy(item.get("applicability")),
                "confidence": float(item.get("confidence", 1.0))}

    @staticmethod
    def _drainage_applicable(source):
        risk = source.get("drainage_context", {})
        if not isinstance(risk, dict) or risk.get("status") not in ("applicable", "verified_applicable"):
            return False
        return bool(risk.get("site_runoff_risk") or risk.get("adjacent_datum_risk")) and bool(risk.get("provenance"))

    @classmethod
    def _exact_levels(cls, contract):
        if not isinstance(contract, dict):
            return {}
        section = contract.get("levels", contract)
        result = {}
        for name, raw in section.items() if isinstance(section, dict) else ():
            value = raw.get("value") if isinstance(raw, dict) else raw
            authority = raw.get("authority_class") if isinstance(raw, dict) else contract.get("authority_class")
            provenance = raw.get("provenance") if isinstance(raw, dict) else contract.get("provenance")
            if cls._finite(value) and authority in ("HARD_REGULATION", "PROJECT_REQUIREMENT") and provenance:
                result[name] = float(value)
        return result

    @staticmethod
    def _unresolved(fields, floor_to_floor, source):
        missing = [name for name, record in fields.items() if record["status"] == "unresolved"]
        if floor_to_floor["status"] != "hypotheses_available":
            missing.append("compatible_usable_height_and_floor_assembly_thickness")
        if not source.get("level_contract"):
            missing.append("exact_project_level_elevations_for_stair_spans")
        return sorted(set(missing))

    @staticmethod
    def _finite(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
