"""Design-05 architecture-owned structural-readiness contract.

The contract describes constraints that a future structural synthesizer may
consume.  It contains no grid, support points, members, sizing, or loads.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any


CONTRACT = "Design05StructuralReadinessCandidateV1"
VERSION = "1.0"
INPUT_CONTRACT = "StructuralArchitectureInputV1"
VALID_READINESS_STATUSES = {
    "READY_FOR_STRUCTURAL_SYNTHESIS",
    "READY_WITH_ARCHITECTURAL_GAPS",
    "BLOCKED_PROTECTED_ZONE",
    "BLOCKED_GEOMETRY_EVIDENCE",
    "BLOCKED_VERTICAL_VOID_EVIDENCE",
    "INSUFFICIENT_ARCHITECTURAL_EVIDENCE",
}


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def canonical_design_05_document(value: Mapping[str, Any]) -> str:
    """Return deterministic Unicode JSON without recursive hash aliases."""
    if not isinstance(value, Mapping):
        raise ValueError("Design-05 candidate must be a mapping")
    payload = deepcopy(dict(value))
    payload.pop("candidate_hash", None)
    payload.pop("hash", None)
    return json.dumps(
        _json_value(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def design_05_semantic_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_design_05_document(value).encode("utf-8")).hexdigest()


def verify_design_05_candidate(value: Mapping[str, Any]) -> bool:
    if not isinstance(value, Mapping):
        return False
    if value.get("contract") != CONTRACT or str(value.get("contract_version")) != VERSION:
        return False
    if value.get("readiness_status") not in VALID_READINESS_STATUSES:
        return False
    required_text = (
        "candidate_id", "candidate_version", "parent_candidate_id",
        "parent_candidate_version", "parent_candidate_hash", "parent_baseline_id",
        "parent_baseline_version", "parent_baseline_hash",
    )
    if any(not isinstance(value.get(key), str) or not value[key] for key in required_text):
        return False
    required_lists = (
        "architectural_authority_refs", "protected_zones", "exclusion_zones",
        "eligible_support_regions", "vertical_void_constraints",
        "opening_clearance_constraints", "access_circulation_constraints",
        "floor_roof_constraints", "structural_input_requirements",
        "unresolved_architectural_evidence", "readiness_checks",
        "required_downstream_rechecks", "evidence_source_audit",
    )
    if any(not isinstance(value.get(key), list) for key in required_lists):
        return False
    handoff = value.get("structural_architecture_input")
    if not isinstance(handoff, Mapping) or handoff.get("contract") != INPUT_CONTRACT:
        return False
    lineage = value.get("lineage")
    if not isinstance(lineage, Mapping):
        return False
    for key in (
        "parent_candidate_id", "parent_candidate_version", "parent_candidate_hash",
        "parent_baseline_id", "parent_baseline_version", "parent_baseline_hash",
    ):
        if lineage.get(key) != value.get(key):
            return False
    stored = value.get("candidate_hash")
    return isinstance(stored, str) and stored == design_05_semantic_hash(value)


__all__ = [
    "CONTRACT", "INPUT_CONTRACT", "VALID_READINESS_STATUSES", "VERSION",
    "canonical_design_05_document", "design_05_semantic_hash",
    "verify_design_05_candidate",
]
