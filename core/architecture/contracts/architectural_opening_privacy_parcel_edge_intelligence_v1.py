"""Contracts and deterministic identity for Design-03 intelligence.

This module describes an additive, non-geometric child of a verified
``DerivedArchitecturalCandidateV1``.  It intentionally does not provide any
geometry realization API.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any


CONTRACT = "Design03DerivedArchitecturalCandidateV1"
VERSION = "1.0"
DERIVATION_STATUS = "INTELLIGENCE_ENRICHMENT"
OPENING_CONTRACT = "ArchitecturalOpeningIntelligenceV1"
PRIVACY_CONTRACT = "ArchitecturalPrivacyAssessmentV1"
PARCEL_EDGE_CONTRACT = "ArchitecturalParcelEdgeRelationV1"
OPENING_PARCEL_CONTRACT = "ArchitecturalOpeningParcelRelationV1"


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def canonical_design_03_document(value: Mapping[str, Any]) -> str:
    if not isinstance(value, Mapping):
        raise ValueError("Design-03 candidate must be a mapping")
    payload = deepcopy(dict(value))
    payload.pop("candidate_hash", None)
    payload.pop("hash", None)
    return json.dumps(
        _json_value(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def design_03_semantic_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_design_03_document(value).encode("utf-8")).hexdigest()


def verify_design_03_candidate(value: Mapping[str, Any]) -> bool:
    if not isinstance(value, Mapping):
        return False
    if value.get("contract") != CONTRACT or str(value.get("contract_version")) != VERSION:
        return False
    if value.get("derivation_status") != DERIVATION_STATUS:
        return False
    required_text = (
        "candidate_id", "candidate_version", "parent_candidate_id",
        "parent_candidate_version", "parent_candidate_hash",
        "parent_baseline_id", "parent_baseline_version", "parent_baseline_hash",
    )
    if any(not isinstance(value.get(key), str) or not value[key] for key in required_text):
        return False
    lineage = value.get("lineage")
    if not isinstance(lineage, Mapping):
        return False
    if any(
        lineage.get(key) != value.get(key)
        for key in (
            "parent_candidate_id", "parent_candidate_version", "parent_candidate_hash",
            "parent_baseline_id", "parent_baseline_version", "parent_baseline_hash",
        )
    ):
        return False
    payload_contracts = {
        "opening_intelligence": OPENING_CONTRACT,
        "privacy_assessments": PRIVACY_CONTRACT,
        "parcel_edge_relations": PARCEL_EDGE_CONTRACT,
        "opening_parcel_relations": OPENING_PARCEL_CONTRACT,
    }
    for key, contract in payload_contracts.items():
        records = value.get(key)
        if not isinstance(records, list):
            return False
        if any(not isinstance(item, Mapping) or item.get("contract") != contract for item in records):
            return False
    stored = value.get("candidate_hash")
    return isinstance(stored, str) and stored == design_03_semantic_hash(value)


__all__ = [
    "CONTRACT", "DERIVATION_STATUS", "OPENING_CONTRACT", "OPENING_PARCEL_CONTRACT",
    "PARCEL_EDGE_CONTRACT", "PRIVACY_CONTRACT", "VERSION",
    "canonical_design_03_document", "design_03_semantic_hash", "verify_design_03_candidate",
]
