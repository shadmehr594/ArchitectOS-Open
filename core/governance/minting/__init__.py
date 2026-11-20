"""Claim minting of the Claim Governance substrate (V1).

The boundary that turns an ACCEPTED proposal into a governance-owned Claim.

    accepted InterpretationProposal + ProposalReceipt
        -> validate eligibility
        -> mint a governance-owned Claim
        -> create the creation (derivation) event
        -> ClaimMintResult

Governance alone mints identity and alone creates claim objects. This boundary
does NOT assign a licence, does NOT approve truth, does NOT create a knowledge
or candidate object, and does NOT widen scope.

Dependency direction

    minting  ->  proposal / claim / events / validation / lineage / licence  ALLOWED
    minting  ->  vision / conversation / knowledge / reasoning               FORBIDDEN
"""

from __future__ import annotations


from core.governance.minting.claim_mint_result_v1 import (
    FORBIDDEN_RESULT_FIELDS,
    ClaimMintResult,
    ClaimMintResultError,
    build_claim_mint_result,
)
from core.governance.minting.claim_minting_service_v1 import (
    ClaimMintingService,
    claim_minting_service,
)


__all__ = (
    "ClaimMintResult",
    "build_claim_mint_result",
    "ClaimMintResultError",
    "FORBIDDEN_RESULT_FIELDS",
    "ClaimMintingService",
    "claim_minting_service",
)
