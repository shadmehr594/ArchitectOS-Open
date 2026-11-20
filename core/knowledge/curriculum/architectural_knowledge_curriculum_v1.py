"""Transient ArchitecturalKnowledgeCurriculumV1 container."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalKnowledgeCurriculumV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalTeachingSessionV1"
SOURCE_VERSION = "1.0"

_NON_CLAIMS = (
    "not_design_rule",
    "not_recommendation",
    "not_authoritative_knowledge",
    "not_memory",
    "not_learned_model",
)

_FORBIDDEN_TERMS = (
    "should",
    "must",
    "required",
    "optimal",
    "best",
    "recommended",
    "design_solution",
    "layout_rule",
    "placement",
    "geometry",
    "dimension",
    "cad",
    "bim",
    "ifc",
)

_FUNCTIONAL_PATTERNS = {
    "sleeping_storage_relation",
    "sleeping_sanitary_relation",
    "circulation_connection_relation",
    "opening_space_relation",
    "opening_associated_with_space",
    "opening_within_facade_plane",
    "entrance_threshold_in_facade_composition",
}
_SPACE_IDENTITY_TERMS = {
    "bedroom",
    "kitchen",
    "bathroom",
    "entrance",
    "corridor",
    "living_space",
    "living_room",
}
_SEMANTIC_ZONE_TERMS = {
    "private_space",
    "service_space",
    "circulation_space",
    "public_space",
}


def _list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return deepcopy(value)
    if isinstance(value, tuple):
        return deepcopy(list(value))
    if value is None:
        return []
    return [deepcopy(value)]


def _unique(values: Iterable[Any]) -> List[Any]:
    result = []
    for value in values:
        if value not in result:
            result.append(deepcopy(value))
    return result


def _validate_session(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalKnowledgeCurriculumV1 requires an "
            "ArchitecturalTeachingSessionV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalKnowledgeCurriculumV1 accepts only "
            "ArchitecturalTeachingSessionV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalKnowledgeCurriculumV1 requires session version 1.0"
        )
    return value


def _pattern_area(pattern: Any) -> str:
    if pattern in _FUNCTIONAL_PATTERNS:
        return "functional_association"
    if pattern in _SPACE_IDENTITY_TERMS:
        return "space_identity"
    if pattern in _SEMANTIC_ZONE_TERMS:
        return "semantic_zone"
    if isinstance(pattern, str):
        lowered = pattern.lower()
        if any(term in lowered for term in ("sleeping", "storage", "sanitary", "opening", "circulation")):
            return "functional_association"
        if any(term in lowered for term in ("bedroom", "kitchen", "bathroom", "entrance", "corridor", "living")):
            return "space_identity"
        if any(term in lowered for term in ("private", "service", "public", "zone")):
            return "semantic_zone"
    return "unresolved"


def _record_claim_ids(record: Dict[str, Any]) -> List[Any]:
    return _list(record.get("source_claim_ids"))


def _record_evidence(record: Dict[str, Any]) -> List[Any]:
    return _list(record.get("evidence_reference"))


def build_architectural_knowledge_curriculum_v1(
    teaching_session: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a transient curriculum container from TeachingSessionV1 only."""
    session = _validate_session(teaching_session)
    records = [
        record
        for record in _list(session.get("teaching_records"))
        if isinstance(record, dict)
    ]
    if not records:
        raise ValueError("ArchitecturalTeachingSessionV1 contains no teaching records")

    learning_cases = []
    grouped: Dict[str, List[Dict[str, Any]]] = {
        "space_identity": [],
        "functional_association": [],
        "semantic_zone": [],
        "unresolved": [],
    }
    for record in records:
        pattern = record.get("source_pattern")
        area = _pattern_area(pattern)
        item = {
            "teaching_topic": record.get("teaching_topic"),
            "source_pattern": pattern,
            "human_explanation": record.get("human_explanation"),
            "source_claim_ids": _record_claim_ids(record),
            "evidence_reference": _record_evidence(record),
            "grounding_status": _list(record.get("grounding_status")),
            "uncertainty": deepcopy(record.get("uncertainty") or {}),
            "semantic_area": area,
        }
        learning_cases.append(item)
        grouped[area].append(item)

    semantic_groups = [
        {
            "semantic_area": area,
            "cases": deepcopy(grouped[area]),
            "source_patterns": _unique(
                case.get("source_pattern") for case in grouped[area]
            ),
            "status": "bounded_curriculum_group",
        }
        for area in ("space_identity", "functional_association", "semantic_zone")
        if grouped[area]
    ]
    source_evidence = [
        {
            "source_pattern": case.get("source_pattern"),
            "source_claim_ids": _list(case.get("source_claim_ids")),
            "evidence_reference": _list(case.get("evidence_reference")),
            "grounding_status": _list(case.get("grounding_status")),
        }
        for case in learning_cases
    ]
    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "curriculum_domain": "foundation_spatial_semantics",
        "learning_cases": learning_cases,
        "semantic_groups": semantic_groups,
        "source_evidence": source_evidence,
        "uncertainty": {
            "session": deepcopy(session.get("uncertainty") or {}),
            "records": [
                deepcopy(case.get("uncertainty") or {})
                for case in learning_cases
                if case.get("uncertainty")
            ],
        },
        "non_claims": list(_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }
    text = str(
        {key: value for key, value in result.items() if key != "non_claims"}
    ).lower()
    for term in _FORBIDDEN_TERMS:
        if term in text:
            raise AssertionError(
                "ArchitecturalKnowledgeCurriculumV1 emitted forbidden term: "
                + term
            )
    return result
