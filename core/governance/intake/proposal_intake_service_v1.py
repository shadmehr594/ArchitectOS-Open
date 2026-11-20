"""ProposalIntakeService (V1) — the first governance-owned intake boundary.

`submit_proposal()` validates a proposal's SHAPE and returns a ProposalReceipt.

It MUST NOT
    call mint_claim()
    call mint_licence_record()
    create events
    create knowledge objects

This is INTAKE ONLY. Governance does not yet mint anything from a proposal.
"""

from __future__ import annotations


import hashlib
from typing import Optional


from core.governance.intake.proposal_receipt_v1 import (
    ProposalReceipt,
    build_proposal_receipt,
)
from core.governance.proposal import InterpretationProposal


CONTRACT = "ProposalIntakeServiceV1"

VERSION = "1.0"


# A proposal reference is a derived content digest — a REFERENCE, not a minted
# identity. Claim identity remains governance-minted and is not created here.
PROPOSAL_REFERENCE_PREFIX = "prp_"


FORBIDDEN_PROPOSAL_AUTHORITY_FIELDS = (
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


def _reference(proposal) -> str:

    """A derived content reference. Never raises, even on a malformed input."""

    try:

        payload = repr(proposal.to_dict())

    except Exception:

        payload = repr(proposal)

    digest = hashlib.sha256(
        payload.encode("utf-8", "ignore")
    ).hexdigest()[:16]

    return PROPOSAL_REFERENCE_PREFIX + digest


class ProposalIntakeService:

    """Stateless intake boundary. It acknowledges; it does not act."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    def submit_proposal(self, proposal) -> ProposalReceipt:

        """Validate the proposal shape. Return a receipt. Mint nothing."""

        # ---- 1. the proposal must BE a proposal ----
        if not isinstance(proposal, InterpretationProposal):

            return build_proposal_receipt(
                proposal_reference=None,
                accepted=False,
                reason="not an InterpretationProposal",
            )

        reference = _reference(proposal)

        # ---- 2. no authority field may be present ----
        for field in FORBIDDEN_PROPOSAL_AUTHORITY_FIELDS:

            if hasattr(proposal, field):

                return build_proposal_receipt(
                    proposal_reference=reference,
                    accepted=False,
                    reason=(
                        "proposal carries forbidden authority field: %s"
                        % (field,)
                    ),
                )

        # ---- 3. required fields ----
        if not str(getattr(proposal, "proposed_content", "") or "").strip():

            return build_proposal_receipt(
                proposal_reference=reference,
                accepted=False,
                reason="missing required field: proposed_content",
            )

        if not isinstance(getattr(proposal, "uncertainty", None), dict):

            return build_proposal_receipt(
                proposal_reference=reference,
                accepted=False,
                reason="missing required field: uncertainty must be a mapping",
            )

        if not isinstance(
            getattr(proposal, "trigger_references", None), (tuple, list)
        ):

            return build_proposal_receipt(
                proposal_reference=reference,
                accepted=False,
                reason=(
                    "missing required field: trigger_references must be a "
                    "sequence"
                ),
            )

        return build_proposal_receipt(
            proposal_reference=reference,
            accepted=True,
            reason="proposal received; shape valid",
        )

    def __repr__(self):

        return (
            "ProposalIntakeService(creates_claims=False, "
            "creates_licences=False, creates_events=False)"
        )


proposal_intake_service = ProposalIntakeService()
