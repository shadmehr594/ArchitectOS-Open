"""Evidence-only validation of ramp longitudinal slope profiles."""
from copy import deepcopy
import math


class RampSlopeProfileValidationV1:
    """Validate supplied path profiles without generating or changing geometry."""

    ALLOWED_AUTHORITIES = ("HARD_REGULATION", "PROJECT_REQUIREMENT", "DESIGN_CONFIRMATION")
    TRANSITION_ROLES = ("transition_start", "transition_end")
    EPS = 1e-7

    def resolve(
        self,
        endpoint_binding=None,
        maximum_slope_constraint=None,
        path_profiles=None,
        transition_constraints=None,
        allow_non_monotonic=False,
    ):
        original = deepcopy({
            "endpoint_binding": endpoint_binding,
            "maximum_slope_constraint": maximum_slope_constraint,
            "path_profiles": path_profiles,
            "transition_constraints": transition_constraints,
        })
        binding = deepcopy(endpoint_binding)
        main_constraint = deepcopy(maximum_slope_constraint)
        profiles = deepcopy(path_profiles)
        transitions = deepcopy(transition_constraints) if transition_constraints is not None else {}
        result = {
            "contract": "RampSlopeProfileValidationV1",
            "status": "unresolved",
            "slope_validated": False,
            "placement_validated": False,
            "parking_integration_validated": False,
            "geometry_generated": False,
            "path_results": [],
            "failure_reasons": [],
            "input_mutated": False,
        }

        failures = self._binding_failures(binding)
        main_maximum, constraint_failures = self._constraint(main_constraint, "maximum_slope")
        failures.extend(constraint_failures)
        if not isinstance(profiles, list) or not profiles:
            failures.append("path_profile_evidence_missing")
        if failures:
            result["failure_reasons"] = sorted(set(failures))
            result["input_mutated"] = original != {
                "endpoint_binding": endpoint_binding,
                "maximum_slope_constraint": maximum_slope_constraint,
                "path_profiles": path_profiles,
                "transition_constraints": transition_constraints,
            }
            return result

        start_z = float(binding["expected_start_z"])
        end_z = float(binding["expected_end_z"])
        direction = self._direction(start_z, end_z)
        seen = set()
        unresolved = []
        invalid = []
        for profile in profiles:
            path_result, path_unresolved, path_invalid = self._validate_path(
                profile, start_z, end_z, direction, main_maximum, transitions,
                bool(allow_non_monotonic), seen,
            )
            result["path_results"].append(path_result)
            unresolved.extend(path_unresolved)
            invalid.extend(path_invalid)

        if unresolved:
            result["failure_reasons"] = sorted(set(unresolved + invalid))
        elif invalid:
            result.update({"status": "invalid", "failure_reasons": sorted(set(invalid))})
        else:
            result.update({"status": "validated", "slope_validated": True})
        result["endpoint_binding"] = binding
        result["maximum_slope_constraint"] = main_constraint
        result["profile_direction"] = direction
        result["input_mutated"] = original != {
            "endpoint_binding": endpoint_binding,
            "maximum_slope_constraint": maximum_slope_constraint,
            "path_profiles": path_profiles,
            "transition_constraints": transition_constraints,
        }
        return result

    def _validate_path(self, profile, expected_start, expected_end, direction,
                       main_maximum, transition_constraints, allow_non_monotonic, seen):
        unresolved = []
        invalid = []
        path_id = profile.get("path_id") if isinstance(profile, dict) else None
        output = {"path_id": path_id, "status": "unresolved", "segment_results": [],
                  "failure_reasons": []}
        if not isinstance(profile, dict) or profile.get("contract") != "RampPathProfileEvidenceV1":
            unresolved.append("path_profile_contract_missing_or_invalid")
            output["failure_reasons"] = unresolved
            return output, unresolved, invalid
        if not isinstance(path_id, str) or not path_id or path_id in seen:
            unresolved.append("path_id_missing_or_duplicate")
        else:
            seen.add(path_id)
        if profile.get("status") != "resolved" or not isinstance(profile.get("provenance"), list) or not profile["provenance"]:
            unresolved.append(f"{path_id or 'unknown'}_profile_evidence_unresolved")
        segments = profile.get("segments")
        if not isinstance(segments, list) or not segments:
            unresolved.append(f"{path_id or 'unknown'}_segments_missing")
            output["failure_reasons"] = sorted(set(unresolved))
            return output, unresolved, invalid

        previous_end = None
        total_length = 0.0
        total_change = 0.0
        for index, segment in enumerate(segments):
            segment_result, segment_unresolved, segment_invalid = self._validate_segment(
                segment, index, direction, main_maximum, transition_constraints,
                allow_non_monotonic,
            )
            output["segment_results"].append(segment_result)
            unresolved.extend(f"{path_id}_{reason}" for reason in segment_unresolved)
            invalid.extend(f"{path_id}_{reason}" for reason in segment_invalid)
            if segment_result.get("numeric_inputs_valid"):
                segment_start = segment_result["start_z"]
                segment_end = segment_result["end_z"]
                if previous_end is not None and abs(segment_start - previous_end) > self.EPS:
                    invalid.append(f"{path_id}_elevation_discontinuity_at_segment_{index}")
                previous_end = segment_end
                total_length += segment_result["length"]
                total_change += segment_start - segment_end

        first = output["segment_results"][0]
        last = output["segment_results"][-1]
        if first.get("numeric_inputs_valid") and abs(first["start_z"] - expected_start) > self.EPS:
            invalid.append(f"{path_id}_start_endpoint_mismatch")
        if last.get("numeric_inputs_valid") and abs(last["end_z"] - expected_end) > self.EPS:
            invalid.append(f"{path_id}_end_endpoint_mismatch")
        if abs(total_change - (expected_start - expected_end)) > self.EPS:
            invalid.append(f"{path_id}_total_rise_inconsistent")

        reasons = sorted(set(unresolved + invalid))
        output.update({
            "status": "unresolved" if unresolved else ("invalid" if invalid else "validated"),
            "failure_reasons": reasons,
            "total_path_length": total_length,
            "total_elevation_change": total_change,
            "expected_elevation_change": expected_start - expected_end,
        })
        return output, unresolved, invalid

    def _validate_segment(self, segment, index, direction, main_maximum,
                          transition_constraints, allow_non_monotonic):
        unresolved = []
        invalid = []
        role = segment.get("role") if isinstance(segment, dict) else None
        output = {"segment_index": index, "role": role, "numeric_inputs_valid": False}
        if not isinstance(segment, dict):
            return output, [f"segment_{index}_evidence_invalid"], invalid
        if not isinstance(segment.get("provenance"), list) or not segment["provenance"]:
            unresolved.append(f"segment_{index}_provenance_missing")
        values = (segment.get("start_z"), segment.get("end_z"), segment.get("length"))
        if not all(self._finite(value) for value in values):
            unresolved.append(f"segment_{index}_numeric_evidence_invalid")
            return output, unresolved, invalid
        start_z, end_z, length = map(float, values)
        output.update({"numeric_inputs_valid": True, "start_z": start_z,
                       "end_z": end_z, "length": length})
        if length <= self.EPS:
            invalid.append(f"segment_{index}_length_not_positive")
            slope = None
        else:
            slope = abs(end_z - start_z) / length
        output["absolute_slope"] = slope

        maximum = main_maximum
        if role in self.TRANSITION_ROLES:
            constraint = transition_constraints.get(role) if isinstance(transition_constraints, dict) else None
            maximum, reasons = self._constraint(constraint, f"{role}_maximum_slope")
            unresolved.extend(f"segment_{index}_{reason}" for reason in reasons)
            minimum_length, length_reasons = self._optional_minimum_length(
                constraint, f"{role}_minimum_length"
            )
            unresolved.extend(f"segment_{index}_{reason}" for reason in length_reasons)
            output["applicable_minimum_length"] = minimum_length
            if minimum_length is not None and length + self.EPS < minimum_length:
                invalid.append(f"segment_{index}_length_below_minimum")
        output["applicable_maximum_slope"] = maximum
        if slope is not None and maximum is not None and slope > maximum + self.EPS:
            invalid.append(f"segment_{index}_slope_exceeds_maximum")

        delta = end_z - start_z
        reverse = ((direction == "descending" and delta > self.EPS) or
                   (direction == "ascending" and delta < -self.EPS) or
                   (direction == "level" and abs(delta) > self.EPS))
        if reverse and not allow_non_monotonic:
            invalid.append(f"segment_{index}_non_monotonic_reverse")
        output["monotonic_with_endpoint_direction"] = not reverse
        output["status"] = "unresolved" if unresolved else ("invalid" if invalid else "validated")
        output["failure_reasons"] = sorted(set(unresolved + invalid))
        return output, unresolved, invalid

    def _constraint(self, constraint, label):
        if not isinstance(constraint, dict):
            return None, [f"{label}_constraint_missing"]
        value = constraint.get("maximum_slope")
        valid = (
            constraint.get("status") == "resolved"
            and constraint.get("authority_class") in self.ALLOWED_AUTHORITIES
            and isinstance(constraint.get("provenance"), list)
            and bool(constraint["provenance"])
            and self._finite(value)
            and 0.0 < float(value) < 1.0
        )
        return (float(value), []) if valid else (None, [f"{label}_constraint_invalid_or_unauthorized"])

    def _optional_minimum_length(self, constraint, label):
        if not isinstance(constraint, dict) or "minimum_length" not in constraint:
            return None, []
        value = constraint.get("minimum_length")
        valid = (
            constraint.get("status") == "resolved"
            and constraint.get("authority_class") in self.ALLOWED_AUTHORITIES
            and isinstance(constraint.get("provenance"), list)
            and bool(constraint["provenance"])
            and constraint.get("length_unit") == "m"
            and self._finite(value)
            and float(value) > 0.0
        )
        return (float(value), []) if valid else (None, [f"{label}_constraint_invalid_or_unauthorized"])

    def _binding_failures(self, binding):
        valid = (
            isinstance(binding, dict)
            and binding.get("contract") == "AuthoritativeRampEndpointBindingContractV1"
            and binding.get("status") == "resolved"
            and binding.get("binding_resolved") is True
            and self._finite(binding.get("expected_start_z"))
            and self._finite(binding.get("expected_end_z"))
        )
        return [] if valid else ["authoritative_ramp_endpoint_binding_missing_or_unresolved"]

    def _direction(self, start_z, end_z):
        if start_z > end_z + self.EPS:
            return "descending"
        if start_z < end_z - self.EPS:
            return "ascending"
        return "level"

    @staticmethod
    def _finite(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
