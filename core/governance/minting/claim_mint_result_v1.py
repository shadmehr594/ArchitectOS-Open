"""ClaimMintResult (V1) — the immutable outcome of a minting attempt.

It carries the created claim reference, the creation event reference and an
immutable status. It carries NO licence decision, NO truth, NO approval, NO
knowledge status and NO confidence-as-truth.

It may carry
    created, claim_reference, creation_event_reference, reason, claim

It may NEVER carry
    truth status, approval status, knowledge status, confidence-as-truth,
    licence decision, scope authority
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Optional


CONTRACT = "ClaimMintResultV1"

VERSION = "1.0"


ALLOWED_RESULT_FIELDS = (
    "created",
    "claim_reference",
    "creation_event_reference",
    "reason",
    "claim",
)


FORBIDDEN_RESULT_FIELDS = (
    "truth",
    "truth_status",
    "is_true",
    "approval",
    "approved",
    "is_approved",
    "knowledge_status",
    "knowledge_class",
    "confidence",
    "confidence_as_truth",
    "licence",
    "license",
    "licence_state",
    "licence_reference",
    "scope",
    "scope_authority",
)


class ClaimMintResultError(ValueError):
    """Raised when a mint result is malformed or carries authority."""


@dataclass(frozen=True)
class ClaimMintResult:

    created: bool

    claim_reference: Optional[str]

    creation_event_reference: Optional[str]

    reason: str

    claim: Optional[Any] = None

    # A mint result reports creation. It decides nothing else.
    ASSIGNS_LICENCE = False

    APPROVES_TRUTH = False

    CREATES_KNOWLEDGE = False

    CARRIES_CONFIDENCE_AS_TRUTH = False

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "created": self.created,
            "claim_reference": self.claim_reference,
            "creation_event_reference": self.creation_event_reference,
            "reason": self.reason,
            "assigns_licence": False,
            "approves_truth": False,
            "creates_knowledge": False,
            "carries_confidence_as_truth": False,
        }

    def __repr__(self):

        return "ClaimMintResult(created=%r, claim_reference=%r)" % (
            self.created,
            self.claim_reference,
        )


def build_claim_mint_result(**fields) -> ClaimMintResult:

    """Build a result, refusing any field that would carry authority."""

    for key in fields:

        if key in FORBIDDEN_RESULT_FIELDS:

            raise ClaimMintResultError(
                "a mint result may not carry %r — minting is not licensing"
                % (key,)
            )

        if key not in ALLOWED_RESULT_FIELDS:

            raise ClaimMintResultError(
                "unknown mint result field: %r" % (key,)
            )

    return ClaimMintResult(**fields)
