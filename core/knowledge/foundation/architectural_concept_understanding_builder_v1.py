"""Production producer boundary for ArchitecturalConceptUnderstandingV1.

This module is the MISSING PRODUCER for `ArchitecturalConceptUnderstandingV1`.
It connects:

    ArchitecturalFoundationKnowledgeAccessV1
                  ↓
    ArchitecturalConceptUnderstandingV1

It is a transient, read-only, deterministic boundary. It performs **bounded
semantic grouping only**.

────────────────────────────────────────────────────────────────────────────
WHY THIS MODULE EXISTS (the seam it closes)
────────────────────────────────────────────────────────────────────────────

`build_architectural_concept_understanding_v1` is a strict contract gate: it
accepts *only* an `ArchitecturalFoundationKnowledgeAccessV1` dict. No module in
the repository produced one in the context the structure spine needs, so
Chain B could not be driven from real teaching data. This module is that
producer.

────────────────────────────────────────────────────────────────────────────
THE GROUPING DECISION (stated explicitly, because it is load-bearing)
────────────────────────────────────────────────────────────────────────────

The access boundary emits **one match per knowledge area**, so a single call
collapses every functional pattern into one match. The understanding boundary
then derives **one concept per match**, using only
`patterns[0]` for its semantic label. Therefore a naive area-level grouping
downstream-would yield *one* concept for N distinct patterns, and the
relationship boundary would find nothing to relate.

The structure spine is **pattern-level** (that is the decision record's clause:
`source_patterns` is the only canonical semantic identifier). So this builder
groups **per source pattern**, not per knowledge area — matching the canonical
key rather than the coarser area label. One pattern → one bounded group →
one concept.

This is *semantic grouping only*: the builder partitions data that already
exists. It does not derive meaning, rank, merge or interpret.

────────────────────────────────────────────────────────────────────────────
WHAT THIS DOES NOT DO
────────────────────────────────────────────────────────────────────────────

    - create an authoritative ontology
    - create permanent Knowledge
    - learn automatically
    - create design rules
    - create recommendations
    - create layout logic
    - create geometry
    - create CAD/BIM/IFC
    - access Memory
    - perform Design Reasoning

Every pattern, claim ID, evidence reference, grounding status and uncertainty
value emitted is a verbatim copy of a value that already existed upstream.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalConceptUnderstandingBuilderV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalFoundationKnowledgeAccessV1"
SOURCE_VERSION = "1.0"
TARGET_CONTRACT = "ArchitecturalConceptUnderstandingV1"
TARGET_VERSION = "1.0"

_KNOWN_AREAS = ("space_identity", "functional_relationship", "semantic_zone")

_STRUCTURAL_NON_CLAIMS = {
    "not_authoritative_ontology": True,
    "not_permanent_knowledge": True,
    "not_design_rule": True,
    "not_recommendation": True,
    "not_layout": True,
    "not_geometry": True,
    "not_design_solution": True,
    "not_design_reasoning": True,
    "not_memory": True,
    "not_learned_model": True,
}

_FORBIDDEN_TERMS = (
    "should",
    "must",
    "required",
    "optimal",
    "best",
    "recommended",
    "design_solution",
    "design_rule",
    "layout_rule",
    "placement",
    "geometry",
    "dimension",
    "cad",
    "bim",
    "ifc",
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


def _validate_access(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalConceptUnderstandingBuilderV1 requires an "
            "ArchitecturalFoundationKnowledgeAccessV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalConceptUnderstandingBuilderV1 accepts only "
            "ArchitecturalFoundationKnowledgeAccessV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalConceptUnderstandingBuilderV1 requires access version 1.0"
        )
    return value


def _validate_session(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalConceptUnderstandingBuilderV1 requires an "
            "ArchitecturalTeachingSessionV1 dict when matches are empty"
        )
    if value.get("contract") != "ArchitecturalTeachingSessionV1":
        raise ValueError(
            "ArchitecturalConceptUnderstandingBuilderV1 fallback accepts only "
            "ArchitecturalTeachingSessionV1"
        )
    if value.get("version") != "1.0":
        raise ValueError(
            "ArchitecturalConceptUnderstandingBuilderV1 requires session version 1.0"
        )
    return value


def _match_cases(match: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        case
        for case in _list(match.get("source_cases"))
        if isinstance(case, dict)
    ]


def _cases_by_pattern(match: Dict[str, Any]) -> Dict[Any, List[Dict[str, Any]]]:
    grouped: Dict[Any, List[Dict[str, Any]]] = {}
    for case in _match_cases(match):
        pattern = case.get("source_pattern")
        grouped.setdefault(pattern, []).append(case)
    return grouped


def _bounded_pattern_groups(access: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Partition access matches into one bounded group per source pattern."""
    groups: List[Dict[str, Any]] = []
    for match_index, match in enumerate(_list(access.get("matches"))):
        if not isinstance(match, dict):
            continue
        area = match.get("knowledge_area")
        by_pattern = _cases_by_pattern(match)

        # Deterministic, first-seen order — never sorted, never re-ranked.
        ordered_patterns: List[Any] = []
        for pattern in _list(match.get("source_patterns")):
            if pattern not in ordered_patterns:
                ordered_patterns.append(pattern)
        for pattern in by_pattern:
            if pattern not in ordered_patterns:
                ordered_patterns.append(pattern)

        for pattern in ordered_patterns:
            cases = by_pattern.get(pattern, [])
            if not cases:
                # Pattern declared at match level with no backing case. Emit a
                # bounded group with no cases rather than inventing one.
                groups.append(
                    {
                        "knowledge_area": area,
                        "source_patterns": [deepcopy(pattern)],
                        "source_cases": [],
                        "grounding_status": [],
                        "source_claim_ids": [],
                        "evidence_reference": _list(
                            match.get("evidence_reference")
                        ),
                        "uncertainty": [],
                        "unresolved_knowledge_areas": [] if area in _KNOWN_AREAS else [area],
                        "status": "bounded_semantic_group",
                        "source_match_index": match_index,
                    }
                )
                continue

            groups.append(
                {
                    "knowledge_area": area,
                    "source_patterns": [deepcopy(pattern)],
                    "source_cases": deepcopy(cases),
                    "grounding_status": _unique(
                        status
                        for case in cases
                        for status in _list(case.get("grounding_status"))
                    ),
                    "source_claim_ids": _unique(
                        claim_id
                        for case in cases
                        for claim_id in _list(case.get("source_claim_ids"))
                    ),
                    "evidence_reference": _unique(
                        evidence
                        for case in cases
                        for evidence in _list(case.get("evidence_reference"))
                    ),
                    "uncertainty": [
                        deepcopy(case.get("uncertainty"))
                        for case in cases
                        if case.get("uncertainty")
                    ],
                    "unresolved_knowledge_areas": [] if area in _KNOWN_AREAS else [area],
                    "status": "bounded_semantic_group",
                    "source_match_index": match_index,
                }
            )
    return groups


def _session_pattern_groups(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fallback: group teaching records directly, when access yields no match."""
    grouped: Dict[Any, List[Dict[str, Any]]] = {}
    order: List[Any] = []
    for record in _list(session.get("teaching_records")):
        if not isinstance(record, dict):
            continue
        pattern = record.get("source_pattern")
        if pattern not in order:
            order.append(pattern)
        grouped.setdefault(pattern, []).append(record)

    groups = []
    for pattern in order:
        records = grouped[pattern]
        case = {
            "source_pattern": deepcopy(pattern),
            "source_claim_ids": _unique(
                claim_id
                for record in records
                for claim_id in _list(record.get("source_claim_ids"))
            ),
            "evidence_reference": _unique(
                evidence
                for record in records
                for evidence in _list(record.get("evidence_reference"))
            ),
            "grounding_status": _unique(
                status
                for record in records
                for status in _list(record.get("grounding_status"))
            ),
            "uncertainty": deepcopy(records[0].get("uncertainty") or {}),
        }
        groups.append(
            {
                "knowledge_area": "functional_relationship",
                "source_patterns": [deepcopy(pattern)],
                "source_cases": [case],
                "grounding_status": case["grounding_status"],
                "source_claim_ids": case["source_claim_ids"],
                "evidence_reference": case["evidence_reference"],
                "uncertainty": [deepcopy(case["uncertainty"])] if case["uncertainty"] else [],
                "unresolved_knowledge_areas": [],
                "status": "bounded_semantic_group",
                "source_match_index": None,
            }
        )
    return groups


def build_architectural_concept_understanding_input_v1(
    foundation_access_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Produce a bounded understanding input from foundation knowledge access.

    The returned dict shares the `ArchitecturalFoundationKnowledgeAccessV1`
    contract surface and therefore IS acceptable by
    `build_architectural_concept_understanding_v1`. The ONLY structural change
    is that each match is split into one match per source pattern, so the
    downstream boundary derives one concept per pattern instead of one concept
    per knowledge area.

    `matches` and the envelope keys are passed through untouched so the
    downstream boundary's own validation and preservation rules apply
    unchanged. Transient (`persistent: False`), read-only (`read_only: True`).
    """
    access = _validate_access(foundation_access_result)

    groups = _bounded_pattern_groups(access)
    provenance = {
        "contract": CONTRACT,
        "version": VERSION,
        "source_contract": SOURCE_CONTRACT,
        "source_version": SOURCE_VERSION,
        "grouping_unit": "source_pattern",
        "grouping_only": True,
        "recovered_from": "access_matches",
    }

    if not groups:
        # Access returned no matches. Recover from the teaching session the
        # access boundary itself was sourced from — still the same lineage,
        # never a different input contract. This is recovery, not invention.
        session = access.get("source_session")
        if session is None:
            session = access.get("teaching_session")
        if session is not None and isinstance(session, dict):
            session = _validate_session(session)
            groups = _session_pattern_groups(session)
            provenance["recovered_from"] = "teaching_session"

    produced = deepcopy(access)
    produced["contract"] = SOURCE_CONTRACT
    produced["version"] = SOURCE_VERSION
    produced["matches"] = [
        {
            "knowledge_area": group["knowledge_area"],
            "source_cases": group["source_cases"],
            "source_patterns": group["source_patterns"],
            "evidence_reference": group["evidence_reference"],
            "uncertainty": group["uncertainty"],
            "grounding_status": group["grounding_status"],
            "source_claim_ids": group["source_claim_ids"],
            "status": "bounded_access_match",
        }
        for group in groups
    ]
    produced["source_patterns"] = _unique(
        pattern for group in groups for pattern in group["source_patterns"]
    )
    produced["source_claim_ids"] = _unique(
        claim_id for group in groups for claim_id in group["source_claim_ids"]
    )
    produced["grounding_status"] = _unique(
        status for group in groups for status in group["grounding_status"]
    )
    produced["knowledge_area_groups"] = groups
    produced["physical_inputs"] = []
    produced["non_claims"] = deepcopy(_STRUCTURAL_NON_CLAIMS)
    produced["persistent"] = False
    produced["read_only"] = True
    produced["produced_by"] = provenance
    _assert_no_forbidden_language(produced)
    return produced


def _assert_no_forbidden_language(result: Dict[str, Any]) -> None:
    """Refuse to emit rule-like or physical vocabulary.

    The scan reads only values this boundary authored. Upstream pass-throughs
    (`source_cases`, `source_evidence`, `uncertainty`, `matches`) are excluded
    because they are verbatim and were not written here, and `non_claims` is
    excluded because its keys legitimately contain the terms as negations.
    """
    authored = {
        "source_patterns": result.get("source_patterns"),
        "source_claim_ids": result.get("source_claim_ids"),
        "grounding_status": result.get("grounding_status"),
        "produced_by": result.get("produced_by"),
        "knowledge_area_groups": [
            {
                key: value
                for key, value in group.items()
                if key
                not in {
                    "source_cases",
                    "evidence_reference",
                    "uncertainty",
                    "grounding_status",
                    "source_claim_ids",
                }
            }
            for group in result.get("knowledge_area_groups") or []
        ],
    }
    serialized = str(authored).lower()
    for term in _FORBIDDEN_TERMS:
        if term in serialized:
            raise AssertionError(
                "ArchitecturalConceptUnderstandingBuilderV1 emitted forbidden "
                "term: " + term
            )
