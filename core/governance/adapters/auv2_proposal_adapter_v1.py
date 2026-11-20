"""AUv2 -> InterpretationProposal adapter (V1).

Connects the existing ArchitecturalUnderstandingV2 projection to governance
WITHOUT transferring ownership. The projection stays vision-owned.

The projection is consumed STRUCTURALLY (it is a plain mapping), so this module
never imports core.vision and governance acquires no client dependency.

Transfers
    content, proposed claim type, trigger references, uncertainty,
    limitations, basis, language

NEVER transfers
    au2_claim_NNN identity, claim_id, licence, scope authority,
    knowledge status, truth status

AUv2 ids are projection-local. They are DISCARDED, never preserved as Claim
identity (BOUNDARY CLARIFICATION AUDIT V1, Decision 1, option B).
"""

from __future__ import annotations


from typing import Any, Dict, List, Optional, Tuple


from core.governance.proposal import build_proposal


CONTRACT = "Auv2ProposalAdapterV1"

VERSION = "1.0"


# Projection-local identity minted inside core/vision/. Never preserved.
PROJECTION_ID_PREFIX = "au2_"


FORBIDDEN_TRANSFER_KEYS = (
    "claim_id",
    "licence",
    "license",
    "scope",
    "scope_authority",
    "truth_status",
    "knowledge_status",
    "truth",
    "is_true",
    "approved",
)


# A trace claim legitimately carries its OWN projection-local claim_id, so that
# key is not rejected on a claim entry — it is simply never transferred. Only
# authority-bearing keys are refused there.
FORBIDDEN_CLAIM_TRANSFER_KEYS = tuple(
    key for key in FORBIDDEN_TRANSFER_KEYS if key != "claim_id"
)


class Auv2AdapterError(ValueError):
    """Raised when a projection cannot be adapted."""


def _text(value) -> str:

    return str(value or "").strip()


def _items(value) -> Tuple[str, ...]:

    if isinstance(value, str):

        return (_text(value),) if _text(value) else ()

    if not isinstance(value, (list, tuple)):

        return ()

    result: List[str] = []

    for item in value:

        text = _text(item)

        if text and text not in result:

            result.append(text)

    return tuple(result)


def _strip_projection_ids(value) -> Any:

    """Recursively drop any projection-local id, so it can never transfer."""

    if isinstance(value, str):

        return None if value.startswith(PROJECTION_ID_PREFIX) else value

    if isinstance(value, dict):

        cleaned = {}

        for key, item in value.items():

            if str(key).startswith(PROJECTION_ID_PREFIX):

                continue

            result = _strip_projection_ids(item)

            if result is not None:

                cleaned[key] = result

        return cleaned

    if isinstance(value, (list, tuple)):

        return [
            result
            for result in (_strip_projection_ids(item) for item in value)
            if result is not None
        ]

    return value


def _reject_forbidden_keys(mapping, keys=FORBIDDEN_TRANSFER_KEYS) -> None:

    for key in (mapping or {}):

        if key in keys:

            raise Auv2AdapterError(
                "a projection may not transfer %r to governance" % (key,)
            )


def _primary_claim_id(auv2) -> Optional[str]:

    states = auv2.get("interpretation_states")

    if not isinstance(states, dict):

        return None

    primary = states.get("primary")

    if not isinstance(primary, dict):

        return None

    return _text(primary.get("claim_id")) or None


def _build(auv2, language):

    if not isinstance(auv2, dict):

        raise Auv2AdapterError(
            "an AUv2 projection must be a mapping"
        )

    _reject_forbidden_keys(auv2)

    trace = auv2.get("claim_trace")

    if not isinstance(trace, (list, tuple)):

        raise Auv2AdapterError(
            "an AUv2 projection must carry a claim_trace sequence"
        )

    # AUv2's own declaration of what it is NOT. Used as the proposal's
    # limitations rather than inventing new ones.
    limitations = _items(auv2.get("non_claims"))

    primary_id = _primary_claim_id(auv2)

    # AUv2 keeps the human-readable label on `semantic_space`, not on each trace
    # claim. The primary claim therefore takes that label as its content.
    semantic_space = auv2.get("semantic_space")

    semantic_label = (
        _text(semantic_space.get("label"))
        if isinstance(semantic_space, dict)
        else ""
    )

    proposals = []

    primary_index = 0

    for claim in trace:

        if not isinstance(claim, dict):

            continue

        _reject_forbidden_keys(claim, keys=FORBIDDEN_CLAIM_TRANSFER_KEYS)

        is_primary = bool(primary_id) and _text(claim.get("claim_id")) == primary_id

        content = (
            _text(claim.get("label"))
            or (semantic_label if is_primary else "")
            or _text(claim.get("claim_type"))
        )

        if not content:

            continue

        proposal = build_proposal(
            proposed_content=content,
            proposed_claim_type=_text(claim.get("claim_type")) or None,
            # AUv2 does not separate a trigger from evidence, so the grounded
            # elements are recorded as triggers and evidence stays empty
            # rather than being fabricated.
            trigger_references=_items(claim.get("source_evidence")),
            uncertainty=_strip_projection_ids(
                dict(claim.get("uncertainty") or {})
            ),
            limitations=limitations,
            basis=_items(claim.get("interpretation_basis")),
            language=language,
        )

        proposals.append(proposal)

        if primary_id and _text(claim.get("claim_id")) == primary_id:

            primary_index = len(proposals) - 1

    if not proposals:

        raise Auv2AdapterError(
            "the projection contains no adaptable claim"
        )

    return tuple(proposals), primary_index


def to_proposals(auv2, *, language: str = "unknown"):

    """One InterpretationProposal per claim in the projection's claim trace."""

    return _build(auv2, language)[0]


def to_proposal(auv2, *, language: str = "unknown"):

    """The proposal for the projection's PRIMARY claim."""

    proposals, primary_index = _build(auv2, language)

    return proposals[primary_index]
