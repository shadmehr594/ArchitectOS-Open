"""Versioned contract and deterministic hash for Design-02 candidates.

The contract deliberately keeps the accepted ``boundary_extraction`` shape.
Design-02 may add semantic/reference overlays, but it may not edit or recreate
any accepted geometry record.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any


CONTRACT = "DerivedArchitecturalCandidateV1"
VERSION = "1.0"
DERIVATION_STATUS = "DERIVED_REFINEMENT"


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def canonical_derived_candidate_document(value: Mapping[str, Any]) -> str:
    """Return stable Unicode JSON excluding only recursive hash aliases."""
    if not isinstance(value, Mapping):
        raise ValueError("derived architectural candidate must be a mapping")
    payload = deepcopy(dict(value))
    payload.pop("candidate_hash", None)
    payload.pop("hash", None)
    return json.dumps(
        _json_value(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def derived_candidate_semantic_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        canonical_derived_candidate_document(value).encode("utf-8")
    ).hexdigest()


def verify_derived_architectural_candidate(value: Mapping[str, Any]) -> bool:
    """Verify identity, parent lineage, status, and stored hash."""
    if not isinstance(value, Mapping):
        return False
    if value.get("contract") != CONTRACT or str(value.get("contract_version")) != VERSION:
        return False
    if value.get("derivation_status") != DERIVATION_STATUS:
        return False
    required_text = (
        "candidate_id",
        "candidate_version",
        "parent_baseline_id",
        "parent_baseline_version",
        "parent_baseline_hash",
    )
    if any(not isinstance(value.get(key), str) or not value[key] for key in required_text):
        return False
    lineage = value.get("lineage")
    if not isinstance(lineage, Mapping):
        return False
    if (
        lineage.get("parent_baseline_id") != value.get("parent_baseline_id")
        or lineage.get("parent_baseline_version") != value.get("parent_baseline_version")
        or lineage.get("parent_baseline_hash") != value.get("parent_baseline_hash")
    ):
        return False
    stored = value.get("candidate_hash")
    return isinstance(stored, str) and stored == derived_candidate_semantic_hash(value)


__all__ = [
    "CONTRACT",
    "DERIVATION_STATUS",
    "VERSION",
    "canonical_derived_candidate_document",
    "derived_candidate_semantic_hash",
    "verify_derived_architectural_candidate",
]
