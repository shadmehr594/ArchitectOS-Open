"""Conversation -> Runtime adapter (V1) — a runtime-owned PURE TRANSLATOR.

It converts a conversation artefact into NEUTRAL runtime input. It creates
NOTHING.

It
    reads a fixed ALLOWED field set
    DROPS conversation-native fields that are not governance-relevant
    REJECTS anything that tries to smuggle authority or truth
    composes the sanctioned governance ADAPTERS (never a factory)

It MUST NOT
    create an InterpretationProposal / Claim / LicenceRecord / event
    mint an identity
    transfer confidence / truth / approval / status
    call a governance FACTORY (build_proposal, mint_*, record_*_event, ...)
    persist

Two entry points (anti-promotion, structural)
    to_advisory_input(candidate)        -> advisory material only.
                                           NEVER a claim request. No token needed.
    to_claim_request_input(statement)   -> neutral proposal_fields.
                                           An EXPLICIT human act only: it REQUIRES a
                                           valid issued HumanActToken, which it
                                           consumes exactly once. A conversation
                                           artefact is refused.

Dependency direction

    runtime adapter  ->  core.governance.adapters   ALLOWED (sanctioned converters)
    runtime adapter  ->  core.runtime.human_act_token_v1   ALLOWED (runtime-local)
    runtime adapter  ->  conversation               duck-typed only (no import)
    conversation     ->  runtime / governance       FORBIDDEN
"""

from __future__ import annotations


from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple


from core.governance.adapters import (
    TeachingCandidateAdapterError,
    to_proposal_material,
)
from core.runtime.human_act_token_v1 import (
    HumanActToken,
    STATE_CONSUMED,
    STATE_ISSUED,
    STATE_RELEASED,
    consume_human_act_token,
    human_act_token_state,
)


CONTRACT = "RuntimeConversationAdapterV1"

VERSION = "1.0"


# ----------------------------------------------------------
# the ONLY conversation fields this adapter reads
# ----------------------------------------------------------

ALLOWED_SOURCE_FIELDS = (
    "raw_statement",
    "statement",
    "normalized_meaning",
    "language",
    "turn_kind",
    "candidate_kind",
    "provenance",
    "basis",
)


# Conversation-native fields that are deliberately NOT read. They are neither
# governance-relevant nor authoritative. Listed so the drop is auditable.
DROPPED_SOURCE_FIELDS = (
    "confidence",
    "confidence_kind",
    "status",
    "candidate_id",
    "source_turn_id",
    "project_id",
    "domain",
    "domain_tags",
    "knowledge_class",
    "scope",
    "zone_assignment",
    "space_topic",
    "entities",
    "relations",
    "polarity",
    "clause_role",
    "clause_index",
    "clause_count",
    "source_statement",
    "rationale",
    "created_at",
    "updated_at",
)


# Any of these on a source artefact is REFUSED: an attempt to smuggle authority
# or truth into a request.
FORBIDDEN_SOURCE_FIELDS = (
    "truth",
    "is_true",
    "truth_status",
    "verified_truth",
    "approval",
    "approved",
    "is_approved",
    "certainty",
    "probability",
    "confidence_as_truth",
    "claim_id",
    "licence_id",
    "license_id",
    "scope_authority",
    "knowledge_status",
    "fact_status",
    "is_fact",
)


# Only these turn kinds may produce a request.
ALLOWED_TURN_KINDS = ("TEACHING_STATEMENT", "CORRECTION")


# The neutral keys this adapter may emit for the executor's A2 path.
PROPOSAL_FIELD_KEYS = (
    "proposed_content",
    "proposed_claim_type",
    "trigger_references",
    "basis",
    "limitations",
    "language",
)


# Rejection codes for the explicit-human-act requirement.
REASON_TOKEN_REQUIRED = "token_required"

REASON_TOKEN_NOT_A_TOKEN = "token_not_a_token"

REASON_TOKEN_UNKNOWN = "token_unknown"

REASON_TOKEN_CONSUMED = "token_consumed"

REASON_TOKEN_RELEASED = "token_released"


class ConversationAdapterError(ValueError):
    """Raised when a conversation artefact cannot be translated."""


def _text(value) -> str:

    return str(value or "").strip()


def _items(value) -> Tuple[str, ...]:

    if isinstance(value, str):

        return (_text(value),) if _text(value) else ()

    if not isinstance(value, (list, tuple)):

        return ()

    result = []

    for item in value:

        text = _text(item)

        if text and text not in result:

            result.append(text)

    return tuple(result)


def _has_field(source, name) -> bool:

    if isinstance(source, Mapping):

        return name in source

    return hasattr(source, name)


def _get(source, name, default=None):

    if isinstance(source, Mapping):

        return source.get(name, default)

    return getattr(source, name, default)


def _reject_forbidden_fields(source) -> None:

    for name in FORBIDDEN_SOURCE_FIELDS:

        if _has_field(source, name):

            raise ConversationAdapterError(
                "a conversation artefact may not carry %r — the adapter "
                "transfers neither authority nor truth" % (name,)
            )


def _reject_governance_identity(value, label) -> None:

    text = _text(value)

    if not text:

        return

    if (
        text.startswith("clm_")
        or text.startswith("lic_")
        or text.startswith("dev_")
        or text.startswith("eev_")
        or text.startswith("kcd_")
    ):

        raise ConversationAdapterError(
            "%s may not carry a governance identity: %r" % (label, text)
        )


def _resolve_turn_kind(source) -> Optional[str]:

    turn_kind = _text(_get(source, "turn_kind"))

    if not turn_kind:

        return None

    if turn_kind not in ALLOWED_TURN_KINDS:

        raise ConversationAdapterError(
            "turn kind %r may not produce a request (allowed: %s)"
            % (turn_kind, ", ".join(ALLOWED_TURN_KINDS))
        )

    return turn_kind


def _validate_intent(intent) -> HumanActToken:

    """Prove an explicit human act WITHOUT consuming it yet.

    Consumption happens only after every other check has passed, so a failed
    submission never burns the token.
    """

    if intent is None:

        raise ConversationAdapterError(
            "%s: a claim request requires an explicit human act "
            "(a HumanActToken)" % (REASON_TOKEN_REQUIRED,)
        )

    if not isinstance(intent, HumanActToken):

        raise ConversationAdapterError(
            "%s: got %r" % (REASON_TOKEN_NOT_A_TOKEN, type(intent).__name__)
        )

    state = human_act_token_state(intent.token_reference)

    if state is None:

        raise ConversationAdapterError(
            "%s: %r" % (REASON_TOKEN_UNKNOWN, intent.token_reference)
        )

    if state == STATE_CONSUMED:

        raise ConversationAdapterError(
            "%s: %r" % (REASON_TOKEN_CONSUMED, intent.token_reference)
        )

    if state == STATE_RELEASED:

        raise ConversationAdapterError(
            "%s: %r" % (REASON_TOKEN_RELEASED, intent.token_reference)
        )

    if state != STATE_ISSUED:

        raise ConversationAdapterError(
            "%s: %r" % (REASON_TOKEN_UNKNOWN, intent.token_reference)
        )

    return intent


@dataclass(frozen=True)
class ConversationRuntimeInput:

    """Neutral runtime input produced from a conversation artefact."""

    proposal_fields: Optional[Mapping]

    advisory_material: Optional[Any] = None

    language: str = "unknown"

    turn_kind: Optional[str] = None

    traceability_reference: Optional[str] = None

    # A translator reports. It creates nothing and decides nothing.
    CREATES_IDENTITY = False

    CREATES_OBJECTS = False

    TRANSFERS_CONFIDENCE = False

    DECIDES_TRUTH = False

    PERSISTS = False

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "proposal_fields": (
                dict(self.proposal_fields)
                if self.proposal_fields is not None
                else None
            ),
            "advisory_material": (
                self.advisory_material.to_dict()
                if self.advisory_material is not None
                else None
            ),
            "language": self.language,
            "turn_kind": self.turn_kind,
            "traceability_reference": self.traceability_reference,
            "creates_identity": False,
            "creates_objects": False,
            "transfers_confidence": False,
            "decides_truth": False,
            "persists": False,
        }

    def __repr__(self):

        return "ConversationRuntimeInput(claim_request=%r, advisory=%r)" % (
            self.proposal_fields is not None,
            self.advisory_material is not None,
        )


def to_advisory_input(
    candidate,
    *,
    traceability_reference: Optional[str] = None,
) -> ConversationRuntimeInput:

    """TeachingCandidate -> ADVISORY input. NEVER a claim request.

    `confidence`, `status` and every conversation-local id are dropped. The
    advisory material is produced by the SANCTIONED governance adapter, not by a
    governance factory.
    """

    if candidate is None:

        raise ConversationAdapterError("no candidate supplied")

    _reject_forbidden_fields(candidate)

    turn_kind = _resolve_turn_kind(candidate)

    text = _text(_get(candidate, "normalized_meaning")) or _text(
        _get(candidate, "raw_statement")
    )

    if not text:

        raise ConversationAdapterError("the candidate carries no usable text")

    _reject_governance_identity(traceability_reference, "traceability_reference")

    try:

        material = to_proposal_material(candidate)

    except TeachingCandidateAdapterError as error:

        raise ConversationAdapterError(str(error))

    return ConversationRuntimeInput(
        # an advisory artefact NEVER becomes a claim request
        proposal_fields=None,
        advisory_material=material,
        language=_text(_get(candidate, "language")) or "unknown",
        turn_kind=turn_kind,
        traceability_reference=_text(traceability_reference) or None,
    )


def to_claim_request_input(
    statement,
    *,
    intent=None,
    language: str = "unknown",
    proposed_claim_type: Optional[str] = None,
    trigger_references: Iterable[str] = (),
    basis: Iterable[str] = (),
    limitations: Iterable[str] = (),
    traceability_reference: Optional[str] = None,
) -> ConversationRuntimeInput:

    """An EXPLICIT human claim request -> neutral `proposal_fields`.

    `statement` MUST be a plain string. A conversation artefact (a
    TeachingCandidate) is REFUSED, so a candidate can never become a claim
    request.

    `intent` MUST be a valid, issued `HumanActToken`. It is consumed EXACTLY
    ONCE, and only after every other check has passed — a rejected submission
    never burns the token.
    """

    # 1. the statement must be a plain string (anti-promotion)
    if not isinstance(statement, str):

        raise ConversationAdapterError(
            "an explicit claim request requires a plain statement string; a "
            "conversation artefact can never become a claim request"
        )

    text = statement.strip()

    if not text:

        raise ConversationAdapterError("the claim request statement is empty")

    # 2. an explicit human act must be proven (validated, not yet consumed)
    _validate_intent(intent)

    # 3. traceability must never be a governance identity
    _reject_governance_identity(traceability_reference, "traceability_reference")

    # 4. the neutral fields
    fields = {
        "proposed_content": text,
        "proposed_claim_type": proposed_claim_type,
        "trigger_references": _items(trigger_references),
        "basis": _items(basis),
        "limitations": _items(limitations),
        "language": _text(language) or "unknown",
    }

    # 5. the submission is committed: consume the act EXACTLY ONCE
    consume_human_act_token(intent)

    return ConversationRuntimeInput(
        proposal_fields=MappingProxyType(fields),
        advisory_material=None,
        language=fields["language"],
        turn_kind=None,
        traceability_reference=_text(traceability_reference) or None,
    )
