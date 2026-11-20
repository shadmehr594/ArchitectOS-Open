"""Transient grouped ArchitecturalTeachingSessionV1 container."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalTeachingSessionV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalTeachingRecordV1"
SOURCE_VERSION = "1.0"

_NON_CLAIMS = (
    "not_memory",
    "not_learned_model",
    "not_design_rule",
)


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


def _validate_record(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalTeachingSessionV1 requires "
            "ArchitecturalTeachingRecordV1 dicts"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalTeachingSessionV1 accepts only "
            "ArchitecturalTeachingRecordV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalTeachingSessionV1 requires record version 1.0"
        )
    return value


def _record_evidence(record: Dict[str, Any]) -> List[Any]:
    return _list(record.get("evidence_reference"))


def _record_uncertainty(record: Dict[str, Any]) -> Dict[str, Any]:
    value = record.get("uncertainty")
    return deepcopy(value) if isinstance(value, dict) else {}


def _topic(records: List[Dict[str, Any]]) -> str:
    topics = _unique(record.get("teaching_topic") for record in records)
    if len(topics) == 1 and topics[0]:
        return topics[0]
    return "architectural_teaching_session"


def build_architectural_teaching_session_v1(
    teaching_records: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    """Group validated TeachingRecordV1 objects into a transient session."""
    if teaching_records is None:
        raise TypeError("teaching_records must be an iterable of record dicts")
    if isinstance(teaching_records, (dict, str, bytes)):
        raise TypeError("teaching_records must be an iterable of record dicts")
    if isinstance(teaching_records, (list, tuple)):
        raw_records = teaching_records
    else:
        try:
            raw_records = list(teaching_records)
        except TypeError as exc:
            raise TypeError(
                "teaching_records must be an iterable of record dicts"
            ) from exc
    records = [_validate_record(record) for record in raw_records]
    if not records:
        raise ValueError("teaching session requires at least one record")

    topics = _unique(record.get("teaching_topic") for record in records)
    patterns = _unique(record.get("source_pattern") for record in records)
    evidence = _unique(
        evidence
        for record in records
        for evidence in _record_evidence(record)
    )
    uncertainties = [
        _record_uncertainty(record)
        for record in records
        if _record_uncertainty(record)
    ]

    session = {
        "contract": CONTRACT,
        "version": VERSION,
        "session_topic": _topic(records),
        "teaching_records": deepcopy(records),
        "source_patterns": patterns,
        "evidence_basis": {
            "source_contract": SOURCE_CONTRACT,
            "source_version": SOURCE_VERSION,
            "teaching_topics": topics,
            "source_patterns": patterns,
            "evidence_reference": evidence,
        },
        "uncertainty": {
            "records": uncertainties,
            "record_count": len(records),
        },
        "non_claims": list(_NON_CLAIMS),
        "persistent": False,
    }
    return session
