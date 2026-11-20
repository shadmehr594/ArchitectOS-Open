"""Transient Architectural Understanding Contract V2.

This module is a pure semantic projection of the completed Architectural
Vision Interpreter V1 result. It does not create knowledge, memory, design
reasoning, geometry, CAD, BIM, rendering, or persistence.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalUnderstandingV2"
VERSION = "2.0"

RELATION_STATUSES = (
    "OBSERVED_RELATION",
    "BOUNDED_INFERENCE",
    "UNRESOLVED_RELATION",
)

CLAIM_TYPES = (
    "semantic_space",
    "functional_role",
    "functional_relationship",
    "spatial_relationship",
    "alternative_interpretation",
)

_NON_CLAIMS = (
    "not_permanent_knowledge",
    "not_design_reasoning",
    "not_geometry",
    "not_cad_or_bim",
    "not_authoritative_space_identity",
)

_FORBIDDEN_TERMS = (
    "verified_space",
    "knowledge_id",
    "ontology_assignment",
    "required",
    "optimized",
    "should",
    "recommended",
    "best",
    "privacy improvement",
    "bed_should_be_near_window",
    "window_optimizes_daylight",
    "best_layout",
)

_ELEMENT_PHRASE_TO_ID = {
    "sleeping element visible": "sleeping_element",
    "storage or dressing element visible": "wardrobe_or_closet",
    "sanitary zone visible": "bathroom_or_ensuite",
    "daylight opening visible": "window",
    "opening visible": "opening",
    "seating element visible": "seating",
    "projecting outdoor platform visible": "balcony",
    "entrance threshold visible": "entrance",
    "facade plane visible": "facade",
}

_RELATION_RULES = (
    (
        "The daylight opening is associated with the enclosed sleeping space.",
        "opening_associated_with_space",
        ("window",),
    ),
    (
        "The seating element is located within the same visible room zone.",
        "seating_within_visible_room_zone",
        ("seating",),
    ),
    (
        "Openings are arranged within the visible facade plane.",
        "opening_within_facade_plane",
        ("window", "opening"),
    ),
    (
        "The projecting outdoor platform is connected to the facade plane.",
        "platform_connected_to_facade_plane",
        ("balcony", "facade"),
    ),
    (
        "The entrance threshold is part of the visible exterior composition.",
        "entrance_threshold_in_facade_composition",
        ("entrance", "facade"),
    ),
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


def _grounding_statuses(grounding: Any) -> Dict[str, List[str]]:
    if not isinstance(grounding, dict):
        return {
            "visible": [],
            "unverified": [],
            "symbol_reading": [],
            "denied": [],
            "not_reported": [],
        }
    return {
        "visible": _list(grounding.get("visible_elements")),
        "unverified": _list(grounding.get("unverified_elements")),
        "symbol_reading": _list(grounding.get("symbol_readings")),
        "denied": _list(grounding.get("denied_elements")),
        "not_reported": _list(grounding.get("not_reported_elements")),
    }


def _evidence_ids(source: Dict[str, Any], statuses: Dict[str, List[str]]) -> List[str]:
    evidence = []
    for values in statuses.values():
        evidence.extend(value for value in values if isinstance(value, str))

    for phrase in _list(source.get("observed_elements")):
        if isinstance(phrase, str):
            element_id = _ELEMENT_PHRASE_TO_ID.get(phrase)
            if element_id:
                evidence.append(element_id)

    return _unique(evidence)


def _status_for(element: str, statuses: Dict[str, List[str]]) -> List[str]:
    return [
        status
        for status, elements in statuses.items()
        if element in elements
    ]


def _uncertainty(
    source: Dict[str, Any],
    *,
    statuses: Iterable[str] = (),
    extra: Iterable[str] = (),
) -> Dict[str, Any]:
    unknowns = _list(source.get("unknowns"))
    unknowns.extend(deepcopy(list(extra)))
    return {
        "confidence": source.get("confidence"),
        "grounding_status": _unique(statuses),
        "unknowns": _unique(unknowns),
        "evidence_conflicts": _list(source.get("evidence_conflicts")),
    }


def _claim(
    claim_id: str,
    claim_type: str,
    source_evidence: Iterable[str],
    grounding_status: Iterable[str],
    interpretation_basis: Iterable[Any],
    uncertainty: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "claim_id": claim_id,
        "claim_type": claim_type,
        "source_evidence": _unique(source_evidence),
        "grounding_status": _unique(grounding_status),
        "interpretation_basis": _unique(interpretation_basis),
        "uncertainty": deepcopy(uncertainty),
    }


def _functional_role(space_type: Any) -> str | None:
    if space_type == "master bedroom":
        return "private_sleeping_space"
    if space_type == "bedroom":
        return "sleeping_space"
    return None


def _associated_element_specs():
    return (
        (
            "wardrobe_or_closet",
            "storage_associated",
            "sleeping_storage_relation",
        ),
        (
            "bathroom_or_ensuite",
            "sanitary_service_associated",
            "sleeping_sanitary_relation",
        ),
        (
            "wc",
            "sanitary_service_associated",
            "sleeping_sanitary_relation",
        ),
    )


def _typed_spatial_relationships(
    source: Dict[str, Any],
    statuses: Dict[str, List[str]],
    claim_trace: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    relationships = []
    existing = _list(source.get("spatial_relations"))
    basis = _list(source.get("classification_basis"))

    for index, relation_text in enumerate(existing, start=1):
        rule = next(
            (item for item in _RELATION_RULES if item[0] == relation_text),
            None,
        )
        if rule is None:
            relation_type = "unresolved_spatial_relation"
            evidence_reference = []
            relation_status = "UNRESOLVED_RELATION"
        else:
            _, relation_type, candidates = rule
            evidence_reference = [
                element
                for element in candidates
                if _status_for(element, statuses)
            ]
            relation_status = (
                "BOUNDED_INFERENCE"
                if evidence_reference
                else "UNRESOLVED_RELATION"
            )

        claim_id = "au2_claim_%03d" % (len(claim_trace) + 1)
        relation_uncertainty = _uncertainty(
            source,
            statuses=(
                status
                for element in evidence_reference
                for status in _status_for(element, statuses)
            ),
            extra=(
                ("relation evidence is unresolved",)
                if relation_status == "UNRESOLVED_RELATION"
                else ()
            ),
        )
        relation = {
            "relation_id": "au2_relation_%03d" % index,
            "relation_type": relation_type,
            "relation_status": relation_status,
            "evidence_reference": evidence_reference,
            "uncertainty": relation_uncertainty,
            "claim_id": claim_id,
        }
        relationships.append(relation)
        claim_trace.append(
            _claim(
                claim_id,
                "spatial_relationship",
                evidence_reference,
                relation_uncertainty["grounding_status"],
                basis + ([relation_text] if relation_text else []),
                relation_uncertainty,
            )
        )

    return relationships


def _assert_safe(value: Any) -> None:
    text = str(value).lower()
    for term in _FORBIDDEN_TERMS:
        if term in text:
            raise AssertionError(
                "ArchitecturalUnderstandingV2 emitted forbidden semantic term: "
                + term
            )


def build_architectural_understanding_v2(
    interpretation: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a deterministic, transient V2 projection from Interpreter output."""

    source = interpretation if isinstance(interpretation, dict) else {}
    grounding = source.get("grounding")
    statuses = _grounding_statuses(grounding)
    evidence_ids = _evidence_ids(source, statuses)
    basis = _list(source.get("classification_basis"))
    space_type = source.get("space_type")
    claim_trace: List[Dict[str, Any]] = []

    semantic_space_claim_id = "au2_claim_%03d" % (len(claim_trace) + 1)
    semantic_space_uncertainty = _uncertainty(
        source,
        statuses=(
            status
            for element in evidence_ids
            for status in _status_for(element, statuses)
        ),
    )
    semantic_space = {
        "label": space_type,
        "status": (
            "bounded_interpretation" if space_type not in (None, "unknown")
            else "undetermined"
        ),
        "basis": basis,
        "claim_id": semantic_space_claim_id,
    }
    claim_trace.append(
        _claim(
            semantic_space_claim_id,
            "semantic_space",
            evidence_ids,
            semantic_space_uncertainty["grounding_status"],
            basis,
            semantic_space_uncertainty,
        )
    )

    functional_understanding = {
        "role_candidates": [],
        "associated_elements": [],
        "functional_relationships": [],
    }

    role = _functional_role(space_type)
    sleeping_status = _status_for("sleeping_element", statuses)
    if role:
        role_claim_id = "au2_claim_%03d" % (len(claim_trace) + 1)
        role_uncertainty = _uncertainty(source, statuses=sleeping_status)
        functional_understanding["role_candidates"].append(
            {
                "role": role,
                "status": "bounded_interpretation",
                "claim_id": role_claim_id,
                "evidence_reference": ["sleeping_element"],
                "uncertainty": role_uncertainty,
            }
        )
        claim_trace.append(
            _claim(
                role_claim_id,
                "functional_role",
                ["sleeping_element"],
                sleeping_status,
                _list(source.get("architectural_interpretation")) + basis,
                role_uncertainty,
            )
        )

        for element, relationship, relation_type in _associated_element_specs():
            element_status = _status_for(element, statuses)
            if not any(
                status in ("visible", "unverified", "symbol_reading")
                for status in element_status
            ):
                # not_reported and denied are not positive association
                # evidence and must never become functional meaning.
                continue
            associated_claim_id = "au2_claim_%03d" % (len(claim_trace) + 1)
            associated_uncertainty = _uncertainty(
                source,
                statuses=element_status,
            )
            functional_understanding["associated_elements"].append(
                {
                    "element": element,
                    "relationship": relationship,
                    "claim_id": associated_claim_id,
                    "evidence_reference": [element],
                    "grounding_status": element_status,
                    "uncertainty": associated_uncertainty,
                }
            )
            claim_trace.append(
                _claim(
                    associated_claim_id,
                    "functional_relationship",
                    [element],
                    element_status,
                    basis,
                    associated_uncertainty,
                )
            )

            functional_claim_id = "au2_claim_%03d" % (len(claim_trace) + 1)
            functional_uncertainty = _uncertainty(
                source,
                statuses=_unique(sleeping_status + element_status),
            )
            functional_understanding["functional_relationships"].append(
                {
                    "type": relation_type,
                    "status": "BOUNDED_INFERENCE",
                    "claim_id": functional_claim_id,
                    "evidence_reference": ["sleeping_element", element],
                    "uncertainty": functional_uncertainty,
                }
            )
            claim_trace.append(
                _claim(
                    functional_claim_id,
                    "functional_relationship",
                    ["sleeping_element", element],
                    functional_uncertainty["grounding_status"],
                    basis,
                    functional_uncertainty,
                )
            )

    spatial_relationships = _typed_spatial_relationships(
        source,
        statuses,
        claim_trace,
    )

    primary_claim_id = semantic_space_claim_id
    primary = {
        "label": space_type,
        "status": semantic_space["status"],
        "claim_id": primary_claim_id,
    }

    alternatives = []
    unresolved = []
    if role and "sleeping_element" in evidence_ids:
        alternative_claim_id = "au2_claim_%03d" % (len(claim_trace) + 1)
        alternative_uncertainty = _uncertainty(
            source,
            statuses=sleeping_status,
            extra=("exact separation from a larger space is unresolved",),
        )
        alternative = {
            "label": "sleeping_area_inside_larger_space",
            "status": "alternative_interpretation",
            "claim_id": alternative_claim_id,
            "evidence_reference": ["sleeping_element"],
            "uncertainty": alternative_uncertainty,
        }
        alternatives.append(alternative)
        claim_trace.append(
            _claim(
                alternative_claim_id,
                "alternative_interpretation",
                ["sleeping_element"],
                sleeping_status,
                basis,
                alternative_uncertainty,
            )
        )

    if source.get("unknowns"):
        unresolved.extend(_list(source.get("unknowns")))

    understanding = {
        "contract": CONTRACT,
        "version": VERSION,
        "semantic_space": semantic_space,
        "functional_understanding": functional_understanding,
        "spatial_relationships": spatial_relationships,
        "claim_trace": claim_trace,
        "interpretation_states": {
            "primary": primary,
            "alternatives": alternatives,
            "unresolved": unresolved,
            "conflicts": _list(source.get("evidence_conflicts")),
        },
        "evidence_basis": {
            "observed_elements": _list(source.get("observed_elements")),
            "grounding_status": statuses,
            "classification_basis": basis,
        },
        "uncertainty": {
            "confidence": source.get("confidence"),
            "unknowns": _list(source.get("unknowns")),
            "expected_gaps": _list(source.get("expected_gaps")),
            "evidence_conflicts": _list(
                source.get("evidence_conflicts")
            ),
            "unverified_claims": _list(source.get("unverified_claims")),
        },
        "non_claims": list(_NON_CLAIMS),
        "geometry_authoritative": False,
        "read_only": True,
        "persistent": False,
    }

    _assert_safe(understanding)
    return understanding
