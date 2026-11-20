"""Resolve occupancy only from complete, authoritative, provenance-bearing inputs."""
from copy import deepcopy
from hashlib import sha256
import json


REQUIRED_FIELDS = (
    "commercial_floor_scope", "commercial_use_type",
    "commercial_occupiable_area", "residential_design_population",
    "occupancy_conversion_rule",
)
FORBIDDEN_KEYS = {"geometry", "polygon", "coordinates", "bbox", "shaft", "lobby", "core", "h1", "h2"}


class AuthoritativeOccupancyScheduleV1:
    """Pure resolver: incomplete, conflicting, or weak evidence stays unresolved."""

    def build(self, *, project_id, design_brief, authority_registry):
        brief = deepcopy(design_brief)
        registry = deepcopy(authority_registry)
        self._reject_forbidden(brief)
        self._reject_forbidden(registry)
        records = brief.get("occupancy_inputs", {})
        fields = {name: self._resolve(name, records.get(name)) for name in REQUIRED_FIELDS}
        blockers = [name for name, item in fields.items() if item["status"] != "authoritative_resolved"]
        payload = {
            "contract": "AuthoritativeOccupancyScheduleV1",
            "project_id": project_id,
            "status": "authoritative_resolved" if not blockers else "unresolved_authoritative_occupancy_inputs",
            "fields": fields,
            "occupancy_schedule": self._schedule(fields) if not blockers else None,
            "required_human_or_authoritative_inputs": blockers,
            "research_authority": registry,
            "consumers": ["elevator", "egress", "stair", "parking", "circulation"],
            "geometry_generated": False,
            "defaults_applied": False,
        }
        payload["contract_fingerprint"] = self._fingerprint(payload)
        return payload

    def _resolve(self, name, record):
        empty = {"id": name, "status": "unresolved_authoritative_input", "value": None,
                 "provenance": [], "human_input_required": True}
        if not isinstance(record, dict):
            return empty
        if record.get("status") == "conflict":
            return {**empty, "status": "conflict", "conflicting_evidence": deepcopy(record.get("conflicting_evidence", []))}
        required = ("value", "authority_class", "source_reference", "provenance", "applicability")
        if record.get("evidence_status") != "authoritative" or any(record.get(k) in (None, "", []) for k in required):
            return {**empty, "non_authoritative_evidence": deepcopy(record)}
        if name == "commercial_occupiable_area":
            value = record["value"]
            if not isinstance(value, dict) or value.get("area_m2") is None or value.get("basis") not in {"net", "gross"}:
                return {**empty, "non_authoritative_evidence": deepcopy(record)}
        return {"id": name, "status": "authoritative_resolved", "value": deepcopy(record["value"]),
                "authority_class": record["authority_class"], "source_reference": record["source_reference"],
                "provenance": deepcopy(record["provenance"]), "applicability": deepcopy(record["applicability"]),
                "human_input_required": False}

    @staticmethod
    def _schedule(fields):
        return {
            "commercial": {
                "floor_scope": deepcopy(fields["commercial_floor_scope"]["value"]),
                "use_type": deepcopy(fields["commercial_use_type"]["value"]),
                "occupiable_area": deepcopy(fields["commercial_occupiable_area"]["value"]),
            },
            "residential": {"design_population": deepcopy(fields["residential_design_population"]["value"])},
            "conversion_rule": deepcopy(fields["occupancy_conversion_rule"]["value"]),
        }

    @classmethod
    def _reject_forbidden(cls, value, path="$" ):
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in FORBIDDEN_KEYS:
                    raise ValueError("forbidden geometry/sizing scope: %s.%s" % (path, key))
                cls._reject_forbidden(child, "%s.%s" % (path, key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                cls._reject_forbidden(child, "%s[%d]" % (path, index))

    @staticmethod
    def _fingerprint(value):
        return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
