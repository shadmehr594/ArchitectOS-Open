"""Transient Architectural Understanding Contract V1.

This module is a read-only semantic projection of the existing architectural
vision interpretation. It does not create knowledge, memory, design reasoning,
geometry, CAD, BIM, or persistence.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


CONTRACT = "ArchitecturalUnderstandingV1"
VERSION = "1.0"


_NON_CLAIMS = (
    "not_permanent_knowledge",
    "not_design_reasoning",
    "not_geometry",
    "not_cad_or_bim",
    "not_authoritative_space_identity",
)


def _list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return deepcopy(value)
    if isinstance(value, tuple):
        return deepcopy(list(value))
    if value is None:
        return []
    return [deepcopy(value)]


def _grounding_status(grounding: Any, key: str) -> List[Any]:
    if not isinstance(grounding, dict):
        return []
    return _list(grounding.get(key))


def build_architectural_understanding(
    interpretation: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a transient semantic projection from Interpreter output.

    The function consumes only the existing Interpreter contract. It does not
    call providers, write storage, contact Knowledge/Teaching/Memory, or add
    design recommendations.
    """

    source = interpretation if isinstance(interpretation, dict) else {}
    grounding = source.get("grounding")
    space_type = source.get("space_type")
    possible_function = _list(source.get("possible_function"))
    architectural_interpretation = _list(
        source.get("architectural_interpretation")
    )
    spatial_relations = _list(source.get("spatial_relations"))
    observed_elements = _list(source.get("observed_elements"))
    classification_basis = _list(source.get("classification_basis"))

    if space_type == "unknown":
        semantic_space_status = "undetermined"
    elif space_type:
        semantic_space_status = "bounded_interpretation"
    else:
        semantic_space_status = "undetermined"

    understanding = {
        "contract": CONTRACT,
        "version": VERSION,
        "semantic_space": {
            "label": space_type,
            "status": semantic_space_status,
            "basis": classification_basis,
        },
        "functional_role": {
            "candidates": possible_function,
            "interpretation": architectural_interpretation,
        },
        "spatial_relationships": spatial_relations,
        "evidence_basis": {
            "observed_elements": observed_elements,
            "grounding_status": {
                "visible": _grounding_status(grounding, "visible_elements"),
                "unverified": _grounding_status(
                    grounding, "unverified_elements"
                ),
                "symbol_reading": _grounding_status(
                    grounding, "symbol_readings"
                ),
                "denied": _grounding_status(grounding, "denied_elements"),
                "not_reported": _grounding_status(
                    grounding, "not_reported_elements"
                ),
            },
            "classification_basis": classification_basis,
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

    return understanding
