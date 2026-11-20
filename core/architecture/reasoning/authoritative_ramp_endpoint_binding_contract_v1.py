"""Fail-closed, evidence-bearing authority binding for ramp level endpoints."""
from copy import deepcopy
import math


class AuthoritativeRampEndpointBindingContractV1:
    """Bind authoritative ramp endpoints without validating their geometry."""

    ALLOWED_AUTHORITIES = ("HARD_REGULATION", "PROJECT_REQUIREMENT", "DESIGN_CONFIRMATION")
    ENDPOINTS = (("start", "ramp_start"), ("end", "ramp_arrival"))
    TOLERANCE = 1e-7

    def resolve(self, project_level_contract=None):
        source = deepcopy(project_level_contract)
        result = {
            "contract": "AuthoritativeRampEndpointBindingContractV1",
            "status": "unresolved",
            "binding_resolved": False,
            "endpoints": {},
            "expected_start_z": None,
            "expected_end_z": None,
            "failure_reasons": [],
            "level_dependency_resolved": False,
            "placement_slope_parking_integration_validated": False,
            "geometry_generated": False,
            "input_mutated": False,
        }
        if not isinstance(source, dict) or source.get("contract") != "ProjectLevelContractV1":
            result["failure_reasons"] = ["project_level_contract_missing_or_invalid"]
            return result
        if source.get("status") == "conflicted" or source.get("conflicts"):
            result.update({"status": "conflicted", "failure_reasons": ["project_level_contract_conflicted"]})
            return result

        dependency = source.get("ramp_level_dependency")
        if not isinstance(dependency, dict) or dependency.get("status") != "resolved":
            result["failure_reasons"] = ["ramp_level_dependency_unresolved"]
            return result
        if dependency.get("endpoint_source") != "explicit_project_ramp_endpoints":
            result["failure_reasons"] = ["explicit_ramp_endpoints_required_no_fallback"]
            return result

        exact = source.get("exact_levels") or {}
        evidence = source.get("level_evidence") or {}
        failures = []
        endpoints = {}
        for endpoint_id, key in self.ENDPOINTS:
            endpoint, endpoint_failures = self._endpoint(endpoint_id, key, exact, evidence)
            failures.extend(endpoint_failures)
            if endpoint is not None:
                endpoints[endpoint_id] = endpoint
        if failures:
            result["failure_reasons"] = sorted(set(failures))
            result["status"] = "conflicted" if any("conflicting" in reason for reason in failures) else "unresolved"
            return result

        result.update({
            "status": "resolved",
            "binding_resolved": True,
            "endpoints": endpoints,
            "expected_start_z": endpoints["start"]["elevation"],
            "expected_end_z": endpoints["end"]["elevation"],
            "level_dependency_resolved": True,
        })
        return result

    def _endpoint(self, endpoint_id, key, exact, evidence):
        if key not in exact or not self._finite(exact.get(key)):
            return None, [f"{key}_missing_or_invalid"]
        records = evidence.get(key)
        if not isinstance(records, list) or not records:
            return None, [f"{key}_evidence_missing"]

        value = float(exact[key])
        accepted = []
        observed = []
        for record in records:
            if not isinstance(record, dict):
                return None, [f"{key}_provenance_invalid"]
            authority = record.get("authority_class")
            provenance = record.get("provenance")
            record_value = record.get("value")
            if authority not in self.ALLOWED_AUTHORITIES or not isinstance(provenance, list) or not provenance:
                return None, [f"{key}_provenance_invalid"]
            if record.get("kind") == "level_elevation" and self._finite(record_value):
                observed.append(float(record_value))
                if abs(float(record_value) - value) > self.TOLERANCE:
                    return None, [f"{key}_conflicting_evidence"]
            accepted.append(deepcopy(record))
        if observed and max(observed) - min(observed) > self.TOLERANCE:
            return None, [f"{key}_conflicting_evidence"]

        authorities = sorted({record["authority_class"] for record in accepted})
        provenance = []
        for record in accepted:
            for item in record["provenance"]:
                if item not in provenance:
                    provenance.append(deepcopy(item))
        endpoint = {
            "id": endpoint_id,
            "key": key,
            "elevation": value,
            "unit": "m",
            "source_contract": "ProjectLevelContractV1",
            "source_path": f"level_evidence.{key}",
            "authority_class": authorities[0] if len(authorities) == 1 else authorities,
            "evidence_status": "authoritative",
            "provenance": provenance,
            "confidence": "exact_authoritative_evidence",
            "evidence": accepted,
        }
        return endpoint, []

    @staticmethod
    def _finite(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
