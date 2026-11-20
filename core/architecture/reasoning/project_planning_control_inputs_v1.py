"""Pure project-input and validation workflow for architecture planning controls."""
from copy import deepcopy
from hashlib import sha256
import json

FIELDS = ("allowed_FAR", "max_site_coverage", "commercial_area_target", "commercial_use_type", "local_regulation_jurisdiction")
COVERAGE_REQUIRED = ("id", "floor_scope", "use", "value_percent", "authority_class", "source_reference", "provenance", "applicability")


class ProjectPlanningControlInputsV1:
    def resolve(self, project_inputs, local_validator=None, national_validator=None):
        original = deepcopy(project_inputs or {})
        fields = {}
        for name in FIELDS:
            value = deepcopy(original.get(name))
            fields[name] = {"value": value, "status": "project_requirement" if value is not None else "unresolved",
                            "authority_class": "PROJECT_REQUIREMENT", "human_input_required": value is None}
        controls = self._coverage_controls(original.get("coverage_controls"))
        legacy_coverage_present = original.get("max_site_coverage") is not None
        fields["coverage_controls"] = {"value": controls,
                                       "status": "project_requirement" if controls else ("not_applicable_legacy_scalar_present" if legacy_coverage_present else "unresolved"),
                                       "authority_class": "PROJECT_REQUIREMENT",
                                       "human_input_required": not bool(controls) and not legacy_coverage_present}
        if controls:
            fields["max_site_coverage"]["human_input_required"] = False
            fields["max_site_coverage"]["status"] = "not_applicable_floor_aware_controls_present"
        local = self._run(local_validator, fields)
        national = self._run(national_validator, fields)
        statuses = [local["status"], national["status"]]
        status = "unresolved" if any(x == "unresolved" for x in statuses) or any(x["human_input_required"] for x in fields.values()) else (
            "conflict" if "conflict" in statuses else "approval_required" if "approval_required" in statuses else "pass")
        result = {"contract": "ProjectPlanningControlInputsV1", "workflow": ["PROJECT_REQUIREMENT", "LOCAL_REGULATION_VALIDATION", "NATIONAL_REGULATION_VALIDATION"],
                  "fields": fields, "local_validation": local, "national_validation": national, "status": status,
                  "project_inputs_preserved": True, "defaults_applied": False}
        result["contract_fingerprint"] = sha256(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        return result

    @staticmethod
    def _coverage_controls(value):
        if value is None:
            return []
        if not isinstance(value, list) or not value:
            raise ValueError("coverage_controls must be a non-empty list")
        controls = deepcopy(value)
        ids = set()
        for record in controls:
            if not isinstance(record, dict) or any(record.get(key) in (None, "", []) for key in COVERAGE_REQUIRED):
                raise ValueError("coverage control requires floor/use scope and complete provenance")
            if record["id"] in ids:
                raise ValueError("coverage control ids must be unique")
            if not 0 <= float(record["value_percent"]) <= 100:
                raise ValueError("coverage percent must be between 0 and 100")
            ids.add(record["id"])
        return controls

    @staticmethod
    def _run(validator, fields):
        if validator is None:
            return {"status": "unresolved", "reason": "validator_not_provided", "input_overwritten": False}
        before = deepcopy(fields)
        result = validator.validate(deepcopy(fields))
        if fields != before:
            raise RuntimeError("validator mutated project inputs")
        if result.get("input_overwritten"):
            raise RuntimeError("validator may not overwrite project inputs")
        return deepcopy(result)
