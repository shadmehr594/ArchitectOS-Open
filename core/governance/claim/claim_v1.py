"""Claim (V1) — the governance-minted immutable claim entity.

INVARIANTS
    * identity is minted ONLY by governance (`mint_claim`);
    * claim_id, content, origin, source_type, claim_type and original_scope
      are immutable after minting;
    * there are NO mutation methods;
    * there is NO truth field of any kind.

FORBIDDEN fields (must never exist on a claim)
    truth_score, confidence_as_truth, approval_as_fact, human_validated_truth,
    truth, is_true, probability, confidence
"""

from __future__ import annotations


from typing import Any, Dict, Optional, Tuple


from core.governance import identity_v1
from core.governance.identity import reservation_v1


CONTRACT = "ClaimV1"

VERSION = "1.0"


CLAIM_TYPES = (
    "existence",
    "semantic_space",
    "functional_role",
    "functional_relationship",
    "spatial_relationship",
    "alternative_interpretation",
)


SOURCE_TYPES = (
    "observation_evidence",
    "generated_hypothesis",
    "human_endorsement",
    "learned_experience",
    "validated_outcome",
    "authored_rule",
)


SCOPES = (
    "single_case",
    "current_project",
    "similar_cases",
    "general",
)


IMMUTABLE_FIELDS = (
    "claim_id",
    "content",
    "origin",
    "source_type",
    "claim_type",
    "original_scope",
)


FORBIDDEN_CLAIM_FIELDS = (
    "truth_score",
    "confidence_as_truth",
    "approval_as_fact",
    "human_validated_truth",
    "truth",
    "is_true",
    "probability",
    "confidence",
)


# Module-private mint authority: only this module may construct a Claim.
_MINT_AUTHORITY = object()


class ClaimIdentityError(PermissionError):
    """Raised when identity is supplied from outside governance."""


class ClaimImmutabilityError(AttributeError):
    """Raised on any attempt to mutate a minted claim."""


class ClaimVocabularyError(ValueError):
    """Raised when a value is not in the closed vocabulary."""


class Claim:

    __slots__ = (
        "_claim_id",
        "_content",
        "_origin",
        "_source_type",
        "_claim_type",
        "_original_scope",
        "_lineage_reference",
        "_licence_reference",
        "_creation_event",
        "_sealed",
    )

    def __init__(
        self,
        *,
        claim_id,
        content,
        origin,
        source_type,
        claim_type,
        original_scope,
        lineage_reference=(),
        licence_reference=None,
        creation_event=None,
        _authority=None,
    ):

        if _authority is not _MINT_AUTHORITY:

            raise ClaimIdentityError(
                "Claim identity is minted only by governance; use "
                "mint_claim() instead of constructing Claim directly."
            )

        identity_v1.reject_vision_id(claim_id)

        if not identity_v1.is_governance_id(claim_id):

            raise ClaimIdentityError(
                "claim_id must be governance-minted: %r" % (claim_id,)
            )

        text = str(content or "").strip()

        if not text:

            raise ClaimVocabularyError("content is required")

        if source_type not in SOURCE_TYPES:

            raise ClaimVocabularyError(
                "unknown source_type: %r" % (source_type,)
            )

        if claim_type not in CLAIM_TYPES:

            raise ClaimVocabularyError(
                "unknown claim_type: %r" % (claim_type,)
            )

        if original_scope not in SCOPES:

            raise ClaimVocabularyError(
                "unknown scope: %r" % (original_scope,)
            )

        object.__setattr__(self, "_sealed", False)

        object.__setattr__(self, "_claim_id", str(claim_id))

        object.__setattr__(self, "_content", text)

        object.__setattr__(self, "_origin", str(origin or ""))

        object.__setattr__(self, "_source_type", source_type)

        object.__setattr__(self, "_claim_type", claim_type)

        object.__setattr__(self, "_original_scope", original_scope)

        object.__setattr__(
            self, "_lineage_reference", tuple(lineage_reference or ())
        )

        object.__setattr__(self, "_licence_reference", licence_reference)

        object.__setattr__(self, "_creation_event", creation_event)

        object.__setattr__(self, "_sealed", True)

    # --------------------------------------------------
    # immutability
    # --------------------------------------------------

    def __setattr__(self, name, value):

        if getattr(self, "_sealed", False):

            raise ClaimImmutabilityError(
                "Claim is immutable after minting: cannot set %r" % (name,)
            )

        object.__setattr__(self, name, value)

    def __delattr__(self, name):

        raise ClaimImmutabilityError(
            "Claim is immutable: cannot delete %r" % (name,)
        )

    # --------------------------------------------------
    # read-only accessors
    # --------------------------------------------------

    @property
    def claim_id(self):

        return self._claim_id

    @property
    def content(self):

        return self._content

    @property
    def origin(self):

        return self._origin

    @property
    def source_type(self):

        return self._source_type

    @property
    def claim_type(self):

        return self._claim_type

    @property
    def original_scope(self):

        return self._original_scope

    @property
    def lineage_reference(self):

        return self._lineage_reference

    @property
    def licence_reference(self):

        return self._licence_reference

    @property
    def creation_event(self):

        return self._creation_event

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "claim_id": self._claim_id,
            "content": self._content,
            "origin": self._origin,
            "source_type": self._source_type,
            "claim_type": self._claim_type,
            "original_scope": self._original_scope,
            "lineage_reference": list(self._lineage_reference),
            "licence_reference": self._licence_reference,
            "creation_event": self._creation_event,
            "immutable": True,
        }

    def __repr__(self):

        return (
            "Claim(claim_id=%r, claim_type=%r, source_type=%r, scope=%r)"
            % (
                self._claim_id,
                self._claim_type,
                self._source_type,
                self._original_scope,
            )
        )


def assert_no_forbidden_fields(mapping):

    """Refuse a payload that carries a truth-bearing field."""

    for key in (mapping or {}):

        if key in FORBIDDEN_CLAIM_FIELDS:

            raise ClaimVocabularyError(
                "forbidden claim field %r must never exist" % (key,)
            )

    return True


def mint_claim(
    *,
    content,
    origin,
    source_type,
    claim_type,
    original_scope,
    lineage_reference=(),
    licence_reference=None,
    creation_event=None,
    claim_id=None,
    reservation=None,
) -> Claim:

    """The ONLY public way to create a Claim.

    `claim_id` exists solely so that supplying one raises: identity is minted
    here and never accepted from a client. A governance-minted `reservation`
    (see core.governance.identity.reservation_v1) is the ONLY other accepted
    source of identity, and it is consumed here.
    """

    if reservation is not None:

        if claim_id is not None:

            raise identity_v1.IdentityError(
                "a claim may not be minted with both a reservation and a "
                "client-supplied id"
            )

        resolved_claim_id = reservation_v1.consume_reservation(
            reservation, reservation_v1.KIND_CLAIM
        )

    else:

        identity_v1.reject_client_supplied_id(claim_id)

        resolved_claim_id = identity_v1.new_claim_id()

    return Claim(
        claim_id=resolved_claim_id,
        content=content,
        origin=origin,
        source_type=source_type,
        claim_type=claim_type,
        original_scope=original_scope,
        lineage_reference=lineage_reference,
        licence_reference=licence_reference,
        creation_event=creation_event,
        _authority=_MINT_AUTHORITY,
    )
