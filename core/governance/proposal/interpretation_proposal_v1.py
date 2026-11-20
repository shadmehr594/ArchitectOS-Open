"""InterpretationProposal (V1) — the authority-free input boundary.

A proposal is a REQUEST. It has no authority, creates no identity and creates
no claim. Governance may accept, alter or reject it.

MAY carry
    proposed_content, proposed_claim_type, trigger_references, basis,
    uncertainty, limitations, language

MAY NEVER carry
    claim_id, licence, scope authority, truth status, knowledge status
"""

from __future__ import annotations


from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


CONTRACT = "InterpretationProposalV1"

VERSION = "1.0"


ALLOWED_PROPOSAL_FIELDS = (
    "proposed_content",
    "proposed_claim_type",
    "trigger_references",
    "basis",
    "uncertainty",
    "limitations",
    "language",
)


FORBIDDEN_PROPOSAL_FIELDS = (
    "claim_id",
    "licence",
    "license",
    "scope",
    "scope_authority",
    "truth_status",
    "knowledge_status",
    "truth",
    "is_true",
    "confidence_as_truth",
    "approval_as_fact",
)


class ProposalAuthorityError(PermissionError):
    """Raised when a proposal tries to carry authority it does not have."""


@dataclass(frozen=True)
class InterpretationProposal:

    proposed_content: str

    trigger_references: Tuple[str, ...] = ()

    basis: Tuple[str, ...] = ()

    uncertainty: Dict[str, Any] = field(default_factory=dict)

    limitations: Tuple[str, ...] = ()

    language: str = "unknown"

    proposed_claim_type: Optional[str] = None

    # A proposal has NO authority. Declared here, not merely documented.
    AUTHORITY = False

    CREATES_IDENTITY = False

    CREATES_CLAIMS = False

    def __post_init__(self):

        if not str(self.proposed_content or "").strip():

            raise ValueError("proposed_content is required")

    def to_dict(self):

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "proposed_content": self.proposed_content,
            "proposed_claim_type": self.proposed_claim_type,
            "trigger_references": list(self.trigger_references),
            "basis": list(self.basis),
            "uncertainty": dict(self.uncertainty),
            "limitations": list(self.limitations),
            "language": self.language,
            "authority": False,
            "creates_identity": False,
            "creates_claims": False,
        }


def build_proposal(**fields):

    """Build a proposal, refusing any field that would carry authority."""

    for key in fields:

        if key in FORBIDDEN_PROPOSAL_FIELDS:

            raise ProposalAuthorityError(
                "a proposal may not carry %r — a proposal has no authority"
                % (key,)
            )

        if key not in ALLOWED_PROPOSAL_FIELDS:

            raise ProposalAuthorityError(
                "unknown proposal field: %r" % (key,)
            )

    return InterpretationProposal(**fields)
