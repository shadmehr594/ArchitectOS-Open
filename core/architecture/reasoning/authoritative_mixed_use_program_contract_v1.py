"""Build an authoritative program contract from explicit, provenance-rich evidence."""
from copy import deepcopy
from hashlib import sha256
import json


REQUIREMENT_TYPES = {"hard", "preferred", "optional", "unresolved"}
GEOMETRY_KEYS = {
    "geometry", "coordinates", "coordinate", "polygon", "polyline", "vertices",
    "bbox", "bounding_box", "x", "y", "seed_geometry", "historical_geometry",
}


class AuthoritativeMixedUseProgramContractV1:
    """Resolve explicit evidence without inventing program defaults.

    Evidence records are deliberately produced by project adapters. This class does
    not search paths, interpret filenames, or contain Parcel-specific knowledge.
    """

    def build(self, *, project_id, requested_items, evidence_records):
        requested = [deepcopy(item) for item in requested_items]
        evidence = [deepcopy(record) for record in evidence_records]
        self._reject_geometry(requested)
        self._reject_geometry(evidence)
        grouped = {}
        for record in evidence:
            self._validate_evidence(record)
            grouped.setdefault(record["id"], []).append(record)

        items = [self._resolve(spec, grouped.get(spec["id"], [])) for spec in requested]
        payload = {
            "contract": "AuthoritativeMixedUseProgramContractV1",
            "project_id": project_id,
            "program_items": items,
            "resolved_items": [item for item in items if item["evidence_status"] == "authoritative_resolved"],
            "unresolved_items": [item for item in items if item["evidence_status"] == "unresolved_authoritative_program_input"],
            "conflicted_items": [item for item in items if item["evidence_status"] == "conflict"],
            "geometry_inference_used": False,
            "defaults_promoted_to_authority": False,
        }
        payload["contract_fingerprint"] = self._fingerprint(payload)
        return payload

    def _resolve(self, spec, records):
        base = self._empty_item(spec)
        authoritative = [r for r in records if r.get("authoritative") is True]
        if not authoritative:
            base["non_authoritative_evidence"] = records
            return base

        signatures = {self._fingerprint(self._meaning(r)) for r in authoritative}
        if len(signatures) > 1:
            base.update({
                "evidence_status": "conflict",
                "conflicting_evidence": authoritative,
                "human_decision_required": True,
                "confidence": min(float(r["confidence"]) for r in authoritative),
            })
            return base

        record = authoritative[0]
        requirement_type = record["requirement_type"]
        base.update({key: deepcopy(value) for key, value in self._meaning(record).items() if key != "id"})
        base.update({
            "requirement_type": requirement_type,
            "source": record["source"],
            "source_contract": record["source_contract"],
            "source_path": record["source_path"],
            "provenance": deepcopy(record["provenance"]),
            "confidence": float(record["confidence"]),
            "applicability": deepcopy(record["applicability"]),
            "evidence_status": "authoritative_resolved",
            "human_decision_required": bool(record.get("human_decision_required", False)),
        })
        return base

    @staticmethod
    def _empty_item(spec):
        return {
            "id": spec["id"],
            "function": spec.get("function", spec["id"]),
            "requirement_type": "unresolved",
            "quantity": None, "capacity": None, "area": None, "count": None,
            "floor_scope": None, "vertical_scope": None,
            "semantics": deepcopy(spec.get("semantics", {})),
            "source": None, "source_contract": None, "source_path": None,
            "provenance": [], "confidence": 0.0,
            "applicability": deepcopy(spec.get("applicability", {})),
            "evidence_status": "unresolved_authoritative_program_input",
            "human_decision_required": True,
            "program_failure": False,
        }

    @staticmethod
    def _meaning(record):
        excluded = {
            "authoritative", "source", "source_contract", "source_path", "provenance",
            "confidence", "applicability", "evidence_status", "human_decision_required",
            "note",
        }
        return {key: deepcopy(value) for key, value in record.items() if key not in excluded}

    @staticmethod
    def _validate_evidence(record):
        required = {"id", "requirement_type", "source", "source_contract", "source_path",
                    "provenance", "confidence", "applicability", "authoritative"}
        missing = sorted(required.difference(record))
        if missing:
            raise ValueError("incomplete evidence metadata: " + ", ".join(missing))
        if record["requirement_type"] not in REQUIREMENT_TYPES - {"unresolved"}:
            raise ValueError("resolved evidence must be hard, preferred, or optional")
        if record["authoritative"] and not record["provenance"]:
            raise ValueError("authoritative evidence requires provenance")

    @classmethod
    def _reject_geometry(cls, value, path="$"):
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in GEOMETRY_KEYS:
                    raise ValueError("geometry is forbidden in program contract: %s.%s" % (path, key))
                cls._reject_geometry(child, "%s.%s" % (path, key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                cls._reject_geometry(child, "%s[%s]" % (path, index))

    @staticmethod
    def _fingerprint(value):
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return sha256(encoded.encode("utf-8")).hexdigest()
