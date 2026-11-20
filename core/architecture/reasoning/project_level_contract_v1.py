"""Evidence-bearing human confirmation layer for project level elevations."""
from copy import deepcopy
import math


class ProjectLevelContractV1:
    EXACT_AUTHORITIES = ("HARD_REGULATION", "PROJECT_REQUIREMENT")
    TOLERANCE = 1e-7

    def resolve(self, level_contract=None, confirmations=None, range_hypotheses=None,
                project_semantics=None):
        source_contract = deepcopy(level_contract)
        source_confirmations = deepcopy(confirmations or [])
        records = self._legacy_records(source_contract) + self._confirmation_records(source_confirmations)
        rejected = [record for record in records if not self._acceptable(record)]
        accepted = [record for record in records if self._acceptable(record)]
        elevations, elevation_evidence, conflicts = self._seed_elevations(accepted)
        spans = [record for record in accepted if record["kind"] == "floor_to_floor_span"]
        self._derive_elevations(elevations, elevation_evidence, spans, conflicts)
        exact_levels = {} if conflicts else dict(sorted(elevations.items()))
        stair_contract = exact_levels if len(exact_levels) >= 2 else None
        explicit_ramp_levels = all(name in exact_levels for name in ("ramp_start", "ramp_arrival"))
        ramp_levels = ("ramp_start", "ramp_arrival") if explicit_ramp_levels else ("ground", "basement")
        ramp_missing = [name for name in ramp_levels if name not in exact_levels]
        ramp_dependency = {
            "contract": "RampLevelDependencyAuditV1",
            "status": "resolved" if not ramp_missing else "unresolved",
            "required_levels": list(ramp_levels),
            "missing_levels": ramp_missing,
            "level_span": (round(abs(exact_levels[ramp_levels[0]] - exact_levels[ramp_levels[1]]), 9)
                           if not ramp_missing else None),
            "endpoint_source": ("explicit_project_ramp_endpoints" if explicit_ramp_levels
                                else "legacy_ground_basement_fallback"),
            "authoritative_for_geometry": not ramp_missing,
            "placement_slope_parking_integration_validated": False,
        }
        status = "conflicted" if conflicts else ("resolved" if exact_levels else "unresolved")
        return {
            "contract": "ProjectLevelContractV1",
            "status": status,
            "exact_levels": exact_levels,
            "level_evidence": elevation_evidence if not conflicts else {},
            "accepted_confirmations": accepted,
            "rejected_confirmations": rejected,
            "conflicts": conflicts,
            "range_hypotheses": deepcopy(range_hypotheses or []),
            "range_hypotheses_authoritative": False,
            "project_semantics": self._semantic_audit(project_semantics),
            "authoritative_stair_level_contract": stair_contract,
            "ramp_level_dependency": ramp_dependency,
            "geometry_generated": False,
            "input_mutated": False,
        }

    @staticmethod
    def _semantic_audit(project_semantics):
        semantics = deepcopy(project_semantics or {})
        required = {
            "grade_is_not_ground_ffl": True,
            "basement_clear_height_is_not_floor_to_floor_span": True,
            "ramp_start_is_not_ground_ffl": True,
            "roof_is_real_level": True,
            "stairhouse_is_roof_superstructure_not_residential_floor": True,
        }
        mismatches = [key for key, expected in required.items()
                      if semantics.get(key) is not expected]
        return {"status": "resolved" if not mismatches else "unresolved",
                "facts": semantics, "required_facts": required,
                "missing_or_mismatched": mismatches,
                "authority_class": semantics.get("authority_class"),
                "provenance": deepcopy(semantics.get("provenance") or [])}

    def _legacy_records(self, contract):
        if not isinstance(contract, dict):
            return []
        section = contract.get("levels", contract)
        if not isinstance(section, dict):
            return []
        records = []
        for level, raw in section.items():
            value = raw.get("value") if isinstance(raw, dict) else raw
            authority = raw.get("authority_class") if isinstance(raw, dict) else contract.get("authority_class")
            provenance = raw.get("provenance") if isinstance(raw, dict) else contract.get("provenance")
            records.append({"kind": "level_elevation", "level": level, "value": value,
                            "unit": "m", "authority_class": authority,
                            "provenance": deepcopy(provenance)})
        return records

    @staticmethod
    def _confirmation_records(confirmations):
        return [deepcopy(record) for record in confirmations if isinstance(record, dict)]

    def _acceptable(self, record):
        if record.get("kind") not in ("level_elevation", "floor_to_floor_span"):
            return False
        if record.get("authority_class") not in self.EXACT_AUTHORITIES or not record.get("provenance"):
            return False
        if not self._finite(record.get("value")) or float(record["value"]) < 0 and record["kind"] == "floor_to_floor_span":
            return False
        if record["kind"] == "level_elevation":
            return bool(record.get("level"))
        return bool(record.get("from_level") and record.get("to_level") and
                    record["from_level"] != record["to_level"])

    def _seed_elevations(self, accepted):
        elevations, evidence, conflicts = {}, {}, []
        for record in accepted:
            if record["kind"] != "level_elevation":
                continue
            level, value = record["level"], float(record["value"])
            if level in elevations and abs(elevations[level] - value) > self.TOLERANCE:
                conflicts.append({"level": level, "reason": "conflicting_exact_elevations",
                                  "values": sorted([elevations[level], value])})
            else:
                elevations[level] = value
                evidence.setdefault(level, []).append(deepcopy(record))
        return elevations, evidence, conflicts

    def _derive_elevations(self, elevations, evidence, spans, conflicts):
        changed = True
        while changed:
            changed = False
            for span in spans:
                lower, upper, rise = span["from_level"], span["to_level"], float(span["value"])
                if lower in elevations and upper not in elevations:
                    elevations[upper] = round(elevations[lower] + rise, 9)
                    evidence[upper] = deepcopy(evidence[lower]) + [deepcopy(span)]
                    changed = True
                elif upper in elevations and lower not in elevations:
                    elevations[lower] = round(elevations[upper] - rise, 9)
                    evidence[lower] = deepcopy(evidence[upper]) + [deepcopy(span)]
                    changed = True
                elif lower in elevations and upper in elevations:
                    actual = elevations[upper] - elevations[lower]
                    if abs(actual - rise) > self.TOLERANCE:
                        conflict = {"from_level": lower, "to_level": upper,
                                    "reason": "span_conflicts_with_exact_elevations",
                                    "confirmed_span": rise, "derived_span": round(actual, 9)}
                        if conflict not in conflicts:
                            conflicts.append(conflict)

    @staticmethod
    def _finite(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
