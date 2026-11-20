"""Proposal boundary of the Claim Governance substrate (V1)."""

from __future__ import annotations


from core.governance.proposal.interpretation_proposal_v1 import (
    ALLOWED_PROPOSAL_FIELDS,
    FORBIDDEN_PROPOSAL_FIELDS,
    InterpretationProposal,
    ProposalAuthorityError,
    build_proposal,
)


__all__ = (
    "InterpretationProposal",
    "ProposalAuthorityError",
    "ALLOWED_PROPOSAL_FIELDS",
    "FORBIDDEN_PROPOSAL_FIELDS",
    "build_proposal",
)
