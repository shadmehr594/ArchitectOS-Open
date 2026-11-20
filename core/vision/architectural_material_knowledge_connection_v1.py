# -*- coding: utf-8 -*-
"""Connect observed facade material knowledge to a user replacement request.

This additive architectural-intelligence adapter reuses the existing
observation-to-ontology owner and the existing image-edit intent compiler. It
does not classify pixels, invent coordinates, mutate knowledge, or expose an
execution/rendering route.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, Iterable, List, Optional

from core.vision.observed_material_knowledge_v1 import (
    resolve_observed_material_knowledge,
)


CONTRACT = "ArchitecturalMaterialKnowledgeConnectionV1"
VERSION = "1.0"


_MATERIAL_CORRECTION = re.compile(
    r"^\s*(?:the\s+)?material\s+(?:you\s+)?identified\s+as\s+"
    r"(?P<previous>[a-z][a-z _-]{0,63}?)\s+is\s+actually\s+"
    r"(?P<corrected>[a-z][a-z _-]{0,63}?)\s*[.!?]?\s*$",
    flags=re.IGNORECASE,
)


# Literal extraction from clauses already classified as explicit preservation
# by ImageEditDeltaV1. This only gives stable names to words the user supplied.
_PROTECTED_COMPONENTS = (
    ("windows", (r"\bwindows?\b",)),
    ("doors", (r"\bdoors?\b",)),
    ("railings", (r"\brailings?\b", r"\bguardrails?\b", r"\bbalustrades?\b")),
    ("balconies", (r"\bbalcon(?:y|ies)\b",)),
    ("roof", (r"\broofs?\b",)),
    ("other non-target components", (
        r"\bother\s+non[- ]target\s+(?:architectural\s+)?components?\b",
    )),
)


def _protected_elements(clauses: Iterable[Any]) -> List[str]:
    """Canonical names explicitly present in preservation clauses, in order."""

    text = " ".join(str(item or "") for item in clauses)
    result: List[str] = []
    for canonical, patterns in _PROTECTED_COMPONENTS:
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            result.append(canonical)
    return result


def _target_material(material_id: str) -> Optional[Dict[str, Any]]:
    """Resolve the compiler's canonical material through the existing ontology."""

    if not material_id:
        return None

    from core.knowledge.architectural_knowledge_resolver import (
        ArchitecturalKnowledgeResolver,
    )

    record = (
        ArchitecturalKnowledgeResolver().data.get("materials", {}).get(material_id)
        or {}
    )
    if not record:
        return None

    return {
        "ontology_id": material_id,
        "ontology_normalized": record.get("normalized"),
        "ontology_material_type": record.get("material_type"),
        "ontology_properties": list(record.get("properties") or []),
        "source": "USER_INSTRUCTION",
        "visually_observed": False,
    }


def _execution_boundary() -> Dict[str, Any]:
    """The accepted current product boundary; never an executable capability."""

    return {
        "status": "NOT_YET_AVAILABLE",
        "precise_facade_material_transfer": False,
        "authorized": False,
        "reason": (
            "no validated spatial material-placement capability connects the "
            "knowledge contract to precise facade execution"
        ),
    }


def _ontology_material(term: str, source: str) -> Optional[Dict[str, Any]]:
    """Resolve one explicit material term through the installed ontology."""

    from core.knowledge.architectural_knowledge_resolver import (
        ArchitecturalKnowledgeResolver,
    )

    normalized_term = " ".join(str(term or "").lower().replace("_", " ").split())
    for material_id, record in (
        ArchitecturalKnowledgeResolver().data.get("materials", {}).items()
    ):
        names = [material_id.replace("_", " "), record.get("normalized")]
        names.extend(record.get("synonyms") or [])
        normalized_names = {
            " ".join(str(name or "").lower().replace("_", " ").split())
            for name in names
            if name
        }
        if normalized_term not in normalized_names:
            continue
        return {
            "ontology_id": material_id,
            "ontology_normalized": record.get("normalized"),
            "ontology_material_type": record.get("material_type"),
            "ontology_properties": list(record.get("properties") or []),
            "source": source,
            "visually_observed": False,
        }
    return None


def _material_correction(
    observed_facts: Dict[str, Any],
    instruction: str,
) -> Optional[Dict[str, Any]]:
    """Build existing transient teaching/review artifacts for one correction."""

    match = _MATERIAL_CORRECTION.match(str(instruction or ""))
    if match is None:
        return None

    previous_term = " ".join(match.group("previous").split())
    corrected_term = " ".join(match.group("corrected").split())
    previous_identity = _ontology_material(previous_term, "VISION_OBSERVATION")
    corrected_identity = _ontology_material(corrected_term, "USER_CORRECTION")
    user_correction = {
        "source": "USER_CORRECTION",
        "verbatim": instruction,
        "previous_material_term": previous_term,
        "corrected_material_term": corrected_term,
        "visually_observed": False,
    }
    boundary = {
        "spatial_grounding": {
            "status": "UNKNOWN",
            "coordinates": None,
            "mask": None,
            "grounded": False,
        },
        "permanent_learning": {
            "status": "UNCHANGED",
            "persistent": False,
            "written": False,
        },
    }

    if previous_identity is None or corrected_identity is None:
        return {
            "connection_status": "MATERIAL_CORRECTION_UNRESOLVED",
            "status": "UNRESOLVED_MATERIAL_IDENTITY",
            "previous_observation": None,
            "user_correction": user_correction,
            "corrected_material": corrected_identity,
            "teaching_candidate": None,
            "teaching_record": None,
            "knowledge_candidate": None,
            "confirmation_review": None,
            "confirmation_prompt": None,
            **boundary,
        }

    observed_entries = [
        entry
        for entry in (observed_facts.get("existing_materials") or [])
        if isinstance(entry, dict)
        and entry.get("ontology_id") == previous_identity["ontology_id"]
    ]
    if not observed_entries:
        return {
            "connection_status": "MATERIAL_CORRECTION_SOURCE_NOT_OBSERVED",
            "status": "SOURCE_MATERIAL_NOT_OBSERVED",
            "previous_observation": None,
            "user_correction": user_correction,
            "corrected_material": corrected_identity,
            "teaching_candidate": None,
            "teaching_record": None,
            "knowledge_candidate": None,
            "confirmation_review": None,
            "confirmation_prompt": None,
            **boundary,
        }

    previous_observation = copy.deepcopy(observed_entries[0])
    evidence_reference = {
        "source": "USER_CORRECTION",
        "previous_observation": copy.deepcopy(previous_observation),
        "observation_provenance": copy.deepcopy(
            observed_facts.get("provenance") or {}
        ),
        "corrected_material": copy.deepcopy(corrected_identity),
    }
    knowledge_structure = {
        "contract": "ArchitecturalKnowledgeStructureV1",
        "version": "1.0",
        "patterns": [
            {
                "pattern": "material_identification_correction",
                "space": "current_project_observed_surface",
                "associated_element": "facade_material_identity",
                "status": "USER_CORRECTION",
                "source_claim_ids": [],
                "evidence_reference": evidence_reference,
                "grounding_status": ["UNKNOWN"],
                "uncertainty": copy.deepcopy(boundary["spatial_grounding"]),
            }
        ],
        "evidence_basis": {
            "source": "USER_CORRECTION",
            "scope": "CURRENT_PROJECT",
            "not_visual_evidence": True,
        },
        "uncertainty": {
            "spatial_grounding": copy.deepcopy(boundary["spatial_grounding"]),
        },
    }

    from core.teaching.architectural_teaching_v1 import (
        build_architectural_teaching_candidate_v1,
    )
    from core.teaching.architectural_teaching_record_v1 import (
        build_architectural_teaching_record_v1,
    )
    from core.knowledge.human_knowledge_validation_loop_v1 import (
        build_confirmation_prompt,
        extract_architectural_knowledge_candidate_v1,
        open_review,
    )

    teaching_candidate = build_architectural_teaching_candidate_v1(
        knowledge_structure
    )
    teaching_record = build_architectural_teaching_record_v1(
        teaching_candidate,
        instruction,
    )
    knowledge_candidate = extract_architectural_knowledge_candidate_v1(
        teaching_record["human_explanation"],
        turn_kind="CORRECTION",
        language="en",
    )
    if knowledge_candidate is None:
        return {
            "connection_status": "MATERIAL_CORRECTION_UNRESOLVED",
            "status": "CANDIDATE_EXTRACTION_UNAVAILABLE",
            "previous_observation": previous_observation,
            "user_correction": user_correction,
            "corrected_material": corrected_identity,
            "teaching_candidate": teaching_candidate,
            "teaching_record": teaching_record,
            "knowledge_candidate": None,
            "confirmation_review": None,
            "confirmation_prompt": None,
            **boundary,
        }
    review = open_review(knowledge_candidate, language="en")

    return {
        "connection_status": "MATERIAL_CORRECTION_PENDING_CONFIRMATION",
        "status": "PENDING_CONFIRMATION",
        "previous_observation": previous_observation,
        "user_correction": user_correction,
        "corrected_material": corrected_identity,
        "teaching_candidate": teaching_candidate,
        "teaching_record": teaching_record,
        "knowledge_candidate": knowledge_candidate,
        "confirmation_review": review.to_dict(),
        "confirmation_prompt": build_confirmation_prompt(review, language="en"),
        **boundary,
    }


def open_material_correction_review(
    connection: Dict[str, Any],
    *,
    language: Optional[str] = None,
):
    """Re-open the existing pending review; this confirms or persists nothing."""

    correction = (connection or {}).get("material_correction") or {}
    candidate = correction.get("knowledge_candidate")
    review_data = correction.get("confirmation_review") or {}
    review_id = review_data.get("review_id") if isinstance(review_data, dict) else None
    if (
        correction.get("status") != "PENDING_CONFIRMATION"
        or not candidate
        or not isinstance(review_data, dict)
        or review_data.get("contract") != "ArchitecturalKnowledgeReviewV1"
        or review_data.get("state") != "pending_review"
        or review_data.get("human_confirmed") is not False
        or review_data.get("candidate") != candidate
        or not isinstance(review_id, str)
        or not review_id.strip()
    ):
        raise ValueError("material correction has no pending confirmation candidate")

    from core.knowledge.human_knowledge_validation_loop_v1 import (
        ArchitecturalKnowledgeReview,
    )

    return ArchitecturalKnowledgeReview(
        candidate,
        review_id=review_id,
        language=language or review_data.get("language"),
    )


def admit_confirmed_material_correction(
    connection: Dict[str, Any],
    review: Any,
    *,
    path: str,
    confirmed_by: str,
) -> Dict[str, Any]:
    """Persist one explicitly confirmed, CURRENT_PROJECT correction."""

    correction = (connection or {}).get("material_correction") or {}
    candidate = correction.get("knowledge_candidate")
    review_data = correction.get("confirmation_review") or {}
    expected_review_id = (
        review_data.get("review_id") if isinstance(review_data, dict) else None
    )
    if (
        correction.get("status") != "PENDING_CONFIRMATION"
        or not isinstance(expected_review_id, str)
        or not expected_review_id.strip()
        or review_data.get("contract") != "ArchitecturalKnowledgeReviewV1"
        or review_data.get("state") != "pending_review"
        or review_data.get("human_confirmed") is not False
        or review_data.get("candidate") != candidate
        or getattr(review, "review_id", None) != expected_review_id
        or getattr(review, "state", None) != "confirmed"
        or getattr(review, "human_confirmed", False) is not True
        or getattr(review, "candidate", None) != candidate
    ):
        raise ValueError("material correction must be explicitly confirmed")
    if not str(path or "").strip():
        raise ValueError("an explicit ledger path is required")
    if not str(confirmed_by or "").strip():
        raise ValueError("confirmed_by is required")

    entry = review.to_confirmed_entry()
    if entry is None or entry.get("review_id") != expected_review_id:
        raise ValueError("material correction must be explicitly confirmed")
    previous = correction["previous_observation"]
    corrected = correction["corrected_material"]
    rule = {
        # One pending review has one stable ledger identity. The existing
        # append-only owner rejects this id on replay, so a second confirmation
        # cannot append the same correction twice.
        "id": "material_correction_%s" % expected_review_id,
        "source_checkpoint": "ARCHITECTURAL_MATERIAL_CORRECTION_TEACHING_V1",
        "human_observation_fa": correction["user_correction"]["verbatim"],
        "generalized_rule": (
            "For this CURRENT_PROJECT observation only, record %s instead of "
            "%s as the confirmed material identity; do not generalize it."
            % (
                corrected.get("ontology_normalized") or corrected["ontology_id"],
                previous.get("ontology_normalized") or previous["ontology_id"],
            )
        ),
        "scope": "CURRENT_PROJECT",
        "knowledge_kind": "PROJECT_MATERIAL_CORRECTION",
        "previous_observation": copy.deepcopy(previous),
        "user_correction": copy.deepcopy(correction["user_correction"]),
        "corrected_material": copy.deepcopy(corrected),
        "spatial_grounding": copy.deepcopy(correction["spatial_grounding"]),
        "execution_capability": copy.deepcopy(
            connection.get("execution_capability") or {}
        ),
        "confirmation_entry": entry,
        "applies_to": {
            "domains": ["facade"],
            "operations": ["material_identification_correction"],
        },
    }

    from core.architecture.knowledge.human_learning_ledger_v1 import (
        append_accepted_rule,
    )

    return append_accepted_rule(
        rule,
        path=path,
        confirmed_by=confirmed_by,
    )


def build_architectural_material_knowledge_connection(
    observation: Any,
    user_text: str,
    *,
    observed_knowledge: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a non-executable material-replacement understanding contract.

    Observation and knowledge inputs are copied, never mutated. A non-material
    request returns ``NO_MATERIAL_REPLACEMENT`` rather than manufacturing an
    operation or target.
    """

    from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta

    observation_block = observation if isinstance(observation, dict) else {}
    knowledge = (
        copy.deepcopy(observed_knowledge)
        if isinstance(observed_knowledge, dict)
        else resolve_observed_material_knowledge(observation_block)
    )
    instruction = str(user_text or "").strip()
    delta = compile_edit_delta(instruction, image_edit=True) if instruction else {}
    preservation_clauses = list(delta.get("explicit_preservation_clauses") or [])

    result: Dict[str, Any] = {
        "contract": CONTRACT,
        "version": VERSION,
        "status": "NO_MATERIAL_REPLACEMENT",
        "observed_facts": {
            "source": "VISION_OBSERVATION",
            "verification": knowledge.get("verification", "UNVERIFIED"),
            "authoritative": False,
            "provenance": copy.deepcopy(observation_block.get("provenance") or {}),
            "existing_materials": copy.deepcopy(knowledge.get("materials") or []),
        },
        "user_instruction": {
            "source": "USER_INSTRUCTION",
            "verbatim": instruction,
            "preservation_clauses": preservation_clauses,
        },
        "architectural_interpretation": None,
        "execution_capability": _execution_boundary(),
        "learned": False,
    }

    correction = _material_correction(result["observed_facts"], instruction)
    if correction is not None:
        result["status"] = correction.pop("connection_status")
        result["material_correction"] = correction
        return result

    if delta.get("edit_class") != "material_change" or not delta.get("material"):
        return result

    requested = _target_material(str(delta.get("material")))
    if requested is None:
        result["status"] = "TARGET_MATERIAL_UNRESOLVED"
        return result

    existing_ids = [
        entry.get("ontology_id")
        for entry in result["observed_facts"]["existing_materials"]
        if isinstance(entry, dict) and entry.get("ontology_id")
    ]

    result["status"] = "CONNECTED"
    result["architectural_interpretation"] = {
        "operation": "MATERIAL_REPLACEMENT",
        "recoloring_only": False,
        "observed_source_material_ids": existing_ids,
        "instruction_source_material": delta.get("replaced_material"),
        "requested_material": requested,
        "target_surfaces": list(delta.get("target_surfaces") or []),
        "protected_elements": _protected_elements(preservation_clauses),
        "spatial_grounding": {
            "status": "UNKNOWN",
            "coordinates": None,
            "mask": None,
            "grounded": False,
        },
    }
    return result


__all__ = [
    "CONTRACT",
    "VERSION",
    "admit_confirmed_material_correction",
    "build_architectural_material_knowledge_connection",
    "open_material_correction_review",
]
