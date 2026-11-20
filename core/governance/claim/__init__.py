"""Claim domain of the Claim Governance substrate (V1)."""

from __future__ import annotations


from core.governance.claim.claim_v1 import (
    CLAIM_TYPES,
    FORBIDDEN_CLAIM_FIELDS,
    IMMUTABLE_FIELDS,
    SCOPES,
    SOURCE_TYPES,
    Claim,
    ClaimIdentityError,
    ClaimImmutabilityError,
    ClaimVocabularyError,
    assert_no_forbidden_fields,
    mint_claim,
)


__all__ = (
    "Claim",
    "mint_claim",
    "assert_no_forbidden_fields",
    "ClaimIdentityError",
    "ClaimImmutabilityError",
    "ClaimVocabularyError",
    "CLAIM_TYPES",
    "SOURCE_TYPES",
    "SCOPES",
    "IMMUTABLE_FIELDS",
    "FORBIDDEN_CLAIM_FIELDS",
)
