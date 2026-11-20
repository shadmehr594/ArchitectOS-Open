"""Proposal intake of the Claim Governance substrate (V1).

The FIRST governance-owned intake boundary.

    InterpretationProposal
        -> submit_proposal()
        -> ProposalReceipt

Intake validates a proposal's SHAPE and returns a receipt. It does not mint a
claim, does not create a licence, does not append an event and does not admit
knowledge. It records receipt only.

Dependency direction

    intake  ->  core.governance.proposal      ALLOWED
    intake  ->  any client subsystem          FORBIDDEN
"""

from __future__ import annotations


from core.governance.intake.proposal_intake_service_v1 import (
    FORBIDDEN_PROPOSAL_AUTHORITY_FIELDS,
    PROPOSAL_REFERENCE_PREFIX,
    ProposalIntakeService,
    proposal_intake_service,
)
from core.governance.intake.proposal_receipt_v1 import (
    FORBIDDEN_RECEIPT_FIELDS,
    ProposalReceipt,
    ProposalReceiptError,
    build_proposal_receipt,
)


__all__ = (
    "ProposalReceipt",
    "build_proposal_receipt",
    "ProposalReceiptError",
    "FORBIDDEN_RECEIPT_FIELDS",
    "ProposalIntakeService",
    "proposal_intake_service",
    "FORBIDDEN_PROPOSAL_AUTHORITY_FIELDS",
    "PROPOSAL_REFERENCE_PREFIX",
)
