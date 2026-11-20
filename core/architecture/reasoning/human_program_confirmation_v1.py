"""Confirm human program intent without geometry, defaults, or silent reconciliation."""
from copy import deepcopy
from hashlib import sha256
import json

REQUIRED_SOLVE_INPUTS = ("residential_floors", "residential_units_per_floor")
FORBIDDEN_SOURCE_KINDS = {"historical_search_target", "historical_candidate", "geometry_candidate"}
FORBIDDEN_KEYS = {"geometry", "coordinates", "coordinate", "polygon", "polyline", "vertices",
                  "bbox", "bounding_box", "seed_geometry", "historical_geometry", "candidate_id"}


class ProgramConfirmationSemanticConsistencyAudit:
    """Audit the three semantic state layers without changing program meaning."""

    EXPECTED = {
        "authoritative_resolved": ("authoritative_resolved", "known"),
        "explicit_user_requirement_resolved": ("explicit_user_requirement_resolved", "known"),
        "human_design_intent_resolved": ("human_design_intent_resolved", "known"),
        "unresolved_authoritative_input": ("unresolved_authoritative_input", "unknown"),
        "conflicted_sources": ("conflicted_sources", "unknown"),
    }

    def audit(self, program_items):
        violations = []
        for item in program_items:
            status = item.get("status")
            expected = self.EXPECTED.get(status)
            if expected is None:
                violations.append({"id": item.get("id"), "problem": "unsupported_status", "status": status})
                continue
            expected_evidence, expected_demand = expected
            if item.get("evidence_status") != expected_evidence or item.get("downstream_demand_state") != expected_demand:
                violations.append({
                    "id": item.get("id"), "problem": "semantic_layer_mismatch",
                    "evidence_status": item.get("evidence_status"), "status": status,
                    "downstream_demand_state": item.get("downstream_demand_state"),
                    "expected_evidence_status": expected_evidence,
                    "expected_downstream_demand_state": expected_demand,
                })
        return {"contract": "ProgramConfirmationSemanticConsistencyAudit",
                "passed": not violations, "item_count": len(program_items), "violations": violations}


class HumanProgramConfirmationV1:
    def build(self, *, authoritative_contract, evidence_contract, daylight_deficit_state="UNKNOWN"):
        base, evidence = deepcopy(authoritative_contract), deepcopy(evidence_contract)
        self._reject_forbidden(base); self._reject_forbidden(evidence)
        self._validate(evidence)
        records = [self._trace(r, evidence) for r in evidence["evidence_records"]]
        grouped = {}
        for record in records: grouped.setdefault(record["id"], []).append(record)
        items, seen = [], set()
        for base_item in base.get("program_items", []):
            seen.add(base_item["id"]); items.append(self._resolve(base_item, grouped.get(base_item["id"], [])))
        for item_id, rs in grouped.items():
            if item_id not in seen: items.append(self._resolve({"id": item_id, "function": item_id}, rs))
        blockers = [x for x in REQUIRED_SOLVE_INPUTS if not self._known(items, x)]
        payload = {
            "contract": "HumanProgramConfirmationV1", "project_id": base.get("project_id"),
            "source_contract": evidence["contract"], "source_path": evidence["source_path"],
            "program_items": items,
            "lightwell_eligibility": {"daylight_deficit_state": daylight_deficit_state,
                "eligible": daylight_deficit_state == "KNOWN_DEFICIT", "default_eligible": False,
                "trigger_state": "KNOWN_DEFICIT"},
            "required_human_decisions_for_clean_solve": blockers,
            "clean_parcel_2_resolve_ready": not blockers,
            "geometry_inference_used": False, "historical_candidate_data_used": False,
            "defaults_applied": False, "parcel_2_resolve_executed": False,
            "final_selection_performed": False, "winner": None,
            "room_layout_generated": False, "final_windows_generated": False,
            "structure_executed": False, "bim_executed": False,
            "ifc_executed": False, "render_executed": False,
        }
        payload["contract_fingerprint"] = self._fingerprint(payload)
        return payload

    def _resolve(self, base_item, records):
        item = deepcopy(base_item)
        if not records:
            if item.get("evidence_status") == "authoritative_resolved" and not item.get("conflicting_evidence"):
                item.update(evidence_status="authoritative_resolved", status="authoritative_resolved",
                            downstream_demand_state="known")
            else:
                item.update(evidence_status="unresolved_authoritative_input",
                            status="unresolved_authoritative_input", downstream_demand_state="unknown")
            return item
        if len({self._fingerprint(self._meaning(r)) for r in records}) > 1:
            item.update(evidence_status="conflicted_sources", status="conflicted_sources",
                        downstream_demand_state="unknown",
                        conflicting_evidence=records)
            return item
        record = records[0]; item.update(self._meaning(record))
        for key in ("source", "source_contract", "source_path", "key", "provenance", "confidence",
                    "source_kind", "confirmation_status", "evidence_role", "requirement_type", "applicability"):
            item[key] = deepcopy(record[key])
        item["status"] = ("explicit_user_requirement_resolved" if record["evidence_role"] == "requirement"
                          else "human_design_intent_resolved")
        item["evidence_status"] = item["status"]
        item["downstream_demand_state"] = "known"
        return item

    @staticmethod
    def _trace(record, contract):
        result = deepcopy(record)
        record_source_path = result.get("source_path") or contract["source_path"]
        result.update(source=contract["source"], source_contract=contract["source_contract"],
                      source_path=record_source_path + "#" + record["key"],
                      provenance=[{"contract": contract["contract"], "key": record["key"],
                                   "source_path": record_source_path}])
        return result

    @staticmethod
    def _meaning(record):
        meta = {"id", "source", "source_contract", "source_path", "key", "provenance", "confidence",
                "source_kind", "confirmation_status", "evidence_role", "requirement_type", "applicability"}
        return {k: deepcopy(v) for k, v in record.items() if k not in meta}

    @staticmethod
    def _known(items, item_id):
        item = next((x for x in items if x["id"] == item_id), None)
        return bool(item and item.get("downstream_demand_state") == "known"
                    and (item.get("count") is not None or item.get("value") is not None))

    @staticmethod
    def _validate(contract):
        required_contract = {"contract", "project_id", "source", "source_contract", "source_path", "evidence_records"}
        if required_contract - set(contract): raise ValueError("incomplete human evidence contract")
        required = {"id", "requirement_type", "evidence_role", "source_kind", "confirmation_status",
                    "key", "confidence", "applicability"}
        for record in contract["evidence_records"]:
            if required - set(record): raise ValueError("incomplete evidence record")
            if record["source_kind"] in FORBIDDEN_SOURCE_KINDS:
                raise ValueError("historical geometry/candidate evidence is forbidden")
            if record["evidence_role"] == "design_intent" and record["requirement_type"] == "hard":
                raise ValueError("design intent cannot become hard regulation")
            if record["evidence_role"] == "reasoning_context" and record.get("binding") is not False:
                raise ValueError("reasoning context cannot hardcode topology")
            if record["source_kind"] == "explicit_user_requirement" and record["evidence_role"] != "requirement":
                raise ValueError("explicit user requirement must be recorded as requirement")

    @classmethod
    def _reject_forbidden(cls, value, path="$"):
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in FORBIDDEN_KEYS:
                    raise ValueError("geometry or historical candidate data is forbidden: %s.%s" % (path, key))
                cls._reject_forbidden(child, "%s.%s" % (path, key))
        elif isinstance(value, list):
            for i, child in enumerate(value): cls._reject_forbidden(child, "%s[%d]" % (path, i))

    @staticmethod
    def _fingerprint(value):
        return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                 default=str).encode("utf-8")).hexdigest()
