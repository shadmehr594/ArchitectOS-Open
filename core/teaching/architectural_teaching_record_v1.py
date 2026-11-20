"""Transient human explanation records for ArchitecturalTeachingCandidateV1."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalTeachingRecordV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalTeachingCandidateV1"
SOURCE_VERSION = "1.0"

_NON_CLAIMS = (
    "not_memory",
    "not_permanent_knowledge",
    "not_design_rule",
)

_FORBIDDEN_TERMS = (
    "should",
    "must",
    "always",
    "optimal",
    "best",
    "required",
)
_OPINION_MARKERS = (
    "architectural opinion",
    "architectural example",
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


def _validate_candidate(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalTeachingRecordV1 requires an "
            "ArchitecturalTeachingCandidateV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalTeachingRecordV1 accepts only "
            "ArchitecturalTeachingCandidateV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalTeachingRecordV1 requires candidate version 1.0"
        )
    return value


def _marker_present(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _OPINION_MARKERS)


def _validate_explanation(explanation: Any) -> str:
    if not isinstance(explanation, str):
        raise TypeError("human explanation must be a string")
    text = explanation.strip()
    if not text:
        raise ValueError("human explanation must not be empty")
    lowered = text.lower()
    if not _marker_present(text):
        for term in _FORBIDDEN_TERMS:
            if term in lowered:
                raise ValueError(
                    "human explanation contains restricted rule-like wording: "
                    + term
                )
    return text


def _candidate_uncertainty(
    candidate: Dict[str, Any],
    unit: Dict[str, Any],
) -> Dict[str, Any]:
    result = {}
    source = candidate.get("uncertainty")
    if isinstance(source, dict):
        result.update(deepcopy(source))
    unit_uncertainty = unit.get("uncertainty")
    if isinstance(unit_uncertainty, dict):
        result["source_unit"] = deepcopy(unit_uncertainty)
    return result


def build_architectural_teaching_record_v1(
    teaching_candidate: Dict[str, Any],
    explanation: str,
) -> Dict[str, Any]:
    """Attach one human explanation to one bounded teaching unit."""
    candidate = _validate_candidate(teaching_candidate)
    human_explanation = _validate_explanation(explanation)
    units = [
        unit
        for unit in _list(candidate.get("teaching_units"))
        if isinstance(unit, dict)
    ]
    if not units:
        raise ValueError("teaching candidate contains no teaching units")

    unit = units[0]
    source_pattern = unit.get("source_pattern")
    record = {
        "contract": CONTRACT,
        "version": VERSION,
        "teaching_topic": unit.get("topic") or "",
        "source_pattern": source_pattern or "",
        "human_explanation": human_explanation,
        "evidence_reference": _unique(
            _list(unit.get("evidence_reference"))
        ),
        "claim_boundary": {
            "is_rule": False,
            "is_design_decision": False,
        },
        "uncertainty": _candidate_uncertainty(candidate, unit),
        "non_claims": list(_NON_CLAIMS),
        "persistent": False,
    }
    return record
