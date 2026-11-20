"""Conversation interaction carrier (V1) — the CLEAN interactive interpretation output.

This is the neutral, immutable record the conversation interpretation layer emits
and the runtime `ClaimRequestMaterialAdapter` consumes. It carries ADVISORY
semantics only.

It carries EXACTLY five fields
    statement
    claim_type_hint
    basis
    limitations
    provenance

It MUST NOT carry
    confidence / confidence_kind / any score
    truth / truth_status / approval / certainty
    status / knowledge_status / fact_status
    any id (`candidate_id`, `source_turn_id`, `claim_id`, `licence_id`, ...)
    any governance reference (`clm_` / `lic_` / `dev_` / `eev_` / `kcd_`)
    a session reference, an interaction nonce, or any authority field

Dependency direction

    this module  ->  core.interpretation.conversation_claim_type_hint_v1  (the sibling layer)
    this module  ->  core.conversation / core.vision / core.governance / core.runtime  FORBIDDEN
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


from core.interpretation.conversation_claim_type_hint_v1 import (
    CLAIM_TYPE_HINT_VOCABULARY,
    PROVENANCE_CONVERSATION,
)


CONTRACT = "ConversationInteractionCarrierV1"

VERSION = "1.0"


# The EXACT contract. Nothing else may exist on the carrier.
CARRIER_FIELDS = (
    "statement",
    "claim_type_hint",
    "basis",
    "limitations",
    "provenance",
)


# Governance identity prefixes. A carrier reference may never carry one.
FORBIDDEN_REFERENCE_PREFIXES = (
    "clm_",
    "lic_",
    "dev_",
    "eev_",
    "kcd_",
)


REASON_NOT_A_STATEMENT = "carrier_not_a_statement"

REASON_UNKNOWN_CLAIM_TYPE = "carrier_unknown_claim_type"

REASON_GOVERNANCE_REFERENCE = "carrier_governance_reference"


REASONS = (
    REASON_NOT_A_STATEMENT,
    REASON_UNKNOWN_CLAIM_TYPE,
    REASON_GOVERNANCE_REFERENCE,
)


class ConversationInteractionCarrierError(ValueError):
    """Raised when a carrier field is malformed."""


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


def _reject_governance_reference(value, label) -> None:

    text = _text(value)

    for prefix in FORBIDDEN_REFERENCE_PREFIXES:

        if text.startswith(prefix):

            raise ConversationInteractionCarrierError(
                "%s: %s is a governance reference: %r"
                % (REASON_GOVERNANCE_REFERENCE, label, text)
            )


@dataclass(frozen=True)
class ConversationInteractionCarrier:

    """An immutable, advisory interactive interpretation carrier."""

    statement: str

    claim_type_hint: Optional[str] = None

    basis: Tuple[str, ...] = ()

    limitations: Tuple[str, ...] = ()

    provenance: str = PROVENANCE_CONVERSATION

    CONTRACT = CONTRACT

    VERSION = VERSION

    FIELDS = CARRIER_FIELDS

    # A carrier advises. It creates nothing and decides nothing.
    IS_ADVISORY = True

    CREATES_IDENTITY = False

    GRANTS_AUTHORITY = False

    CARRIES_CONFIDENCE = False

    DECIDES_TRUTH = False

    def __post_init__(self):

        text = _text(self.statement)

        if not text:

            raise ConversationInteractionCarrierError(
                "%s: statement is required" % (REASON_NOT_A_STATEMENT,)
            )

        object.__setattr__(self, "statement", text)

        if self.claim_type_hint is not None:

            token = _text(self.claim_type_hint)

            if token not in CLAIM_TYPE_HINT_VOCABULARY:

                raise ConversationInteractionCarrierError(
                    "%s: %r" % (REASON_UNKNOWN_CLAIM_TYPE, token)
                )

            object.__setattr__(self, "claim_type_hint", token)

        object.__setattr__(self, "basis", _items(self.basis))

        object.__setattr__(self, "limitations", _items(self.limitations))

        _reject_governance_reference(self.provenance, "provenance")

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "statement": self.statement,
            "claim_type_hint": self.claim_type_hint,
            "basis": list(self.basis),
            "limitations": list(self.limitations),
            "provenance": self.provenance,
            "is_advisory": True,
            "creates_identity": False,
            "grants_authority": False,
            "carries_confidence": False,
            "decides_truth": False,
        }

    def __repr__(self):

        return "ConversationInteractionCarrier(claim_type_hint=%r)" % (
            self.claim_type_hint,
        )
