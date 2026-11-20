"""Design-04 architecture-only floor/roof geometry contract.

The contract is a new immutable child of a verified Design-03 candidate.  It
contains evidence-bound 2D architectural surfaces only; it is deliberately
independent of structural, BIM, IFC, rendering, and site-orientation models.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any


CONTRACT = "Design04DerivedArchitecturalGeometryCandidateV1"
VERSION = "1.0"
VALID_STATUSES = {"DERIVED", "DERIVED_WITH_WARNINGS"}


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def canonical_design_04_document(value: Mapping[str, Any]) -> str:
    """Return deterministic Unicode JSON excluding recursive hash aliases."""
    if not isinstance(value, Mapping):
        raise ValueError("Design-04 candidate must be a mapping")
    payload = deepcopy(dict(value))
    payload.pop("candidate_hash", None)
    payload.pop("hash", None)
    return json.dumps(
        _json_value(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def design_04_semantic_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_design_04_document(value).encode("utf-8")).hexdigest()


def verify_design_04_candidate(value: Mapping[str, Any]) -> bool:
    if not isinstance(value, Mapping):
        return False
    if value.get("contract") != CONTRACT or str(value.get("contract_version")) != VERSION:
        return False
    if value.get("derivation_status") not in VALID_STATUSES:
        return False
    required = (
        "candidate_id", "candidate_version", "parent_candidate_id",
        "parent_candidate_version", "parent_candidate_hash", "parent_baseline_id",
        "parent_baseline_version", "parent_baseline_hash",
    )
    if any(not isinstance(value.get(key), str) or not value[key] for key in required):
        return False
    if not all(isinstance(value.get(key), list) for key in (
        "floor_geometries", "slab_geometries", "roof_geometries",
        "vertical_voids", "protected_zones", "geometry_checks",
        "unresolved_evidence", "required_downstream_rechecks",
    )):
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
    return isinstance(stored, str) and stored == design_04_semantic_hash(value)


__all__ = [
    "CONTRACT", "VERSION", "VALID_STATUSES", "canonical_design_04_document",
    "design_04_semantic_hash", "verify_design_04_candidate",
]
