"""Resolve program intent from provenance-rich contracts without geometry or defaults."""
from copy import deepcopy
from hashlib import sha256
import json


STATUSES = {
    "authoritative_resolved", "human_design_intent_resolved",
    "preferred_unconfirmed", "optional_unconfirmed",
    "unresolved_authoritative_input", "conflicted_sources",
}
CONFIRMED_SOURCE_KINDS = {"regulation", "project_requirement", "explicit_user_requirement"}
HUMAN_SOURCE_KINDS = {"human_design_decision", "human_preference"}
IGNORED_SOURCE_KINDS = {"historical_search_target", "historical_candidate", "geometry_candidate"}
FORBIDDEN_KEYS = {
    "geometry", "coordinates", "coordinate", "polygon", "polyline", "vertices",
    "bbox", "bounding_box", "seed_geometry", "historical_geometry", "candidate_id",
}
META_KEYS = {
    "id", "requirement_type", "source_kind", "confirmation_status", "source",
    "source_contract", "source_path", "key", "provenance", "confidence",
    "applicability", "note",
}


class ProgramIntentResolutionV1:
    """Classify authoritative requirements and human design intent explicitly."""

    def build(self, *, authoritative_contract, evidence_records):
        base = deepcopy(authoritative_contract)
        records = [deepcopy(record) for record in evidence_records]
        self._reject_forbidden_payload(base)
        self._reject_forbidden_payload(records)
        grouped = {}
        ignored = []
        for record in records:
            if record.get("source_kind") in IGNORED_SOURCE_KINDS:
                ignored.append(record)
                continue
            self._validate_record(record)
            grouped.setdefault(record["id"], []).append(record)

        items = []
        for item in base.get("program_items", []):
            if item.get("evidence_status") == "authoritative_resolved":
                items.append(self._from_authoritative_contract(item))
            else:
                items.append(self._resolve_open_item(item, grouped.get(item["id"], [])))

        payload = {
            "contract": "ProgramIntentResolutionV1",
            "project_id": base.get("project_id"),
            "source_contract": base.get("contract"),
            "source_contract_fingerprint": base.get("contract_fingerprint"),
            "program_items": items,
            "status_index": {status: [i["id"] for i in items if i["status"] == status]
                             for status in sorted(STATUSES)},
            "ignored_evidence": ignored,
            "geometry_inference_used": False,
            "historical_candidate_data_used": False,
            "defaults_applied": False,
        }
        payload["contract_fingerprint"] = self._fingerprint(payload)
        return payload

    def _from_authoritative_contract(self, item):
        required = ("source_contract", "source_path", "provenance")
        if any(not item.get(key) for key in required):
            raise ValueError("resolved authoritative item requires complete provenance")
        result = deepcopy(item)
        result["status"] = "authoritative_resolved"
        result["key"] = self._source_key(item["source_path"])
        result["downstream_demand_state"] = "known"
        return result

    def _resolve_open_item(self, item, records):
        result = deepcopy(item)
        result["evidence_status"] = None
        confirmed = [r for r in records if r["confirmation_status"] == "confirmed"]
        if confirmed:
            signatures = {self._fingerprint(self._meaning(r)) for r in confirmed}
            if len(signatures) > 1:
                return self._finish(result, "conflicted_sources", confirmed, unknown=True)
            record = confirmed[0]
            status = ("human_design_intent_resolved" if record["source_kind"] in HUMAN_SOURCE_KINDS
                      or record["source_kind"] == "explicit_user_requirement"
                      else "authoritative_resolved")
            result.update(deepcopy(self._meaning(record)))
            result.update(self._trace(record))
            result["requirement_type"] = record["requirement_type"]
            return self._finish(result, status, confirmed, unknown=False)

        preferred = [r for r in records if r["requirement_type"] == "preferred"]
        optional = [r for r in records if r["requirement_type"] == "optional"]
        if preferred:
            return self._finish(result, "preferred_unconfirmed", preferred, unknown=True)
        if optional:
            return self._finish(result, "optional_unconfirmed", optional, unknown=True)
        return self._finish(result, "unresolved_authoritative_input", [], unknown=True)

    @staticmethod
    def _finish(item, status, evidence, *, unknown):
        item["status"] = status
        item["evidence_status"] = status
        item["resolution_evidence"] = deepcopy(evidence)
        item["human_decision_required"] = status not in {
            "authoritative_resolved", "human_design_intent_resolved"
        }
        item["downstream_demand_state"] = "unknown" if unknown else "known"
        item["program_failure"] = False
        return item

    @staticmethod
    def _trace(record):
        return {key: deepcopy(record[key]) for key in (
            "source", "source_contract", "source_path", "key", "provenance",
            "confidence", "applicability", "source_kind", "confirmation_status"
        )}

    @staticmethod
    def _meaning(record):
        return {key: deepcopy(value) for key, value in record.items() if key not in META_KEYS}

    @staticmethod
    def _source_key(source_path):
        return source_path.rsplit("#", 1)[1] if "#" in source_path else source_path

    @staticmethod
    def _validate_record(record):
        required = {
            "id", "requirement_type", "source_kind", "confirmation_status", "source",
            "source_contract", "source_path", "key", "provenance", "confidence", "applicability",
        }
        missing = sorted(key for key in required if not record.get(key) and record.get(key) != 0)
        if missing:
            raise ValueError("resolution evidence requires provenance fields: " + ", ".join(missing))
        if record["requirement_type"] not in {"hard", "preferred", "optional"}:
            raise ValueError("requirement_type must be hard, preferred, or optional")
        if record["confirmation_status"] not in {"confirmed", "unconfirmed"}:
            raise ValueError("confirmation_status must be confirmed or unconfirmed")
        if record["source_kind"] == "human_preference" and record["requirement_type"] == "hard":
            raise ValueError("human preference cannot become a hard requirement")
        if record["confirmation_status"] == "confirmed" and record["source_kind"] not in (
                CONFIRMED_SOURCE_KINDS | HUMAN_SOURCE_KINDS):
            raise ValueError("confirmed evidence has an unsupported source kind")

    @classmethod
    def _reject_forbidden_payload(cls, value, path="$"):
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in FORBIDDEN_KEYS:
                    raise ValueError("geometry or historical candidate data is forbidden: %s.%s" % (path, key))
                cls._reject_forbidden_payload(child, "%s.%s" % (path, key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                cls._reject_forbidden_payload(child, "%s[%d]" % (path, index))

    @staticmethod
    def _fingerprint(value):
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return sha256(encoded.encode("utf-8")).hexdigest()
