"""ProposalReceipt (V1) — the immutable acknowledgement of an intake.

A receipt RECORDS RECEIPT. It creates no claim, grants no licence, assigns no
scope and carries no truth or knowledge status.

It may carry
    proposal_reference, accepted, reason

It may NEVER carry
    claim_id, licence, scope, truth, knowledge status
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Optional


CONTRACT = "ProposalReceiptV1"

VERSION = "1.0"


ALLOWED_RECEIPT_FIELDS = (
    "proposal_reference",
    "accepted",
    "reason",
)


FORBIDDEN_RECEIPT_FIELDS = (
    "claim_id",
    "licence",
    "license",
    "scope",
    "scope_authority",
    "truth",
    "truth_status",
    "is_true",
    "knowledge_status",
    "approved",
    "is_approved",
)


class ProposalReceiptError(ValueError):
    """Raised when a receipt is malformed or carries authority."""


@dataclass(frozen=True)
class ProposalReceipt:

    proposal_reference: Optional[str]

    accepted: bool

    reason: str

    # A receipt acknowledges; it does not act. Declared, not merely documented.
    CREATES_CLAIMS = False

    CREATES_LICENCES = False

    CREATES_EVENTS = False

    ASSIGNS_SCOPE = False

    CARRIES_TRUTH = False

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "proposal_reference": self.proposal_reference,
            "accepted": self.accepted,
            "reason": self.reason,
            "creates_claims": False,
            "creates_licences": False,
            "creates_events": False,
            "assigns_scope": False,
            "carries_truth": False,
        }

    def __repr__(self):

        return "ProposalReceipt(accepted=%r, reference=%r)" % (
            self.accepted,
            self.proposal_reference,
        )


def build_proposal_receipt(**fields) -> ProposalReceipt:

    """Build a receipt, refusing any field that would carry authority."""

    for key in fields:

        if key in FORBIDDEN_RECEIPT_FIELDS:

            raise ProposalReceiptError(
                "a receipt may not carry %r — it records receipt only" % (key,)
            )

        if key not in ALLOWED_RECEIPT_FIELDS:

            raise ProposalReceiptError(
                "unknown receipt field: %r" % (key,)
            )

    return ProposalReceipt(**fields)
