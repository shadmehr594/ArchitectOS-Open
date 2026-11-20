"""LicenceAssignmentRequest (V1) — an immutable, authority-free request.

It ASKS governance to assign a licence. It carries no truth, no approval, no
confidence and no knowledge status, and it injects no identity.

It may carry ONLY
    target_claim_reference, requested_licence, basis_reference, actor_reference

It may NEVER carry
    truth, approval, confidence, knowledge status, claim_id, licence_id
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Optional


from core.governance.licence import FORBIDDEN_LICENCE_STATES


CONTRACT = "LicenceAssignmentRequestV1"

VERSION = "1.0"


ALLOWED_REQUEST_FIELDS = (
    "target_claim_reference",
    "requested_licence",
    "basis_reference",
    "actor_reference",
)


# Licence states a REQUEST may never ask for: the existing vocabulary's
# forbidden states, plus the ones this boundary names explicitly.
FORBIDDEN_REQUESTED_LICENCES = tuple(
    dict.fromkeys(
        FORBIDDEN_LICENCE_STATES
        + (
            "verified_truth",
            "certainty",
            "verified",
            "approved",
            "true",
        )
    )
)


FORBIDDEN_REQUEST_FIELDS = (
    # truth / approval / confidence / certainty / knowledge
    "truth",
    "truth_status",
    "is_true",
    "verified_truth",
    "approval",
    "approved",
    "is_approved",
    "confidence",
    "confidence_as_truth",
    "certainty",
    "probability",
    "knowledge_status",
    "knowledge_class",
    # identity injection
    "claim_id",
    "licence_id",
    "license_id",
    # content / scope
    "content",
    "new_content",
    "scope",
    "scope_authority",
)


class LicenceAssignmentRequestError(ValueError):
    """Raised when a request is malformed or carries authority."""


@dataclass(frozen=True)
class LicenceAssignmentRequest:

    target_claim_reference: str

    requested_licence: str

    basis_reference: Optional[str] = None

    actor_reference: Optional[str] = None

    # A request asks; it decides nothing. Declared, not merely documented.
    GRANTS_TRUTH = False

    APPROVES_FACTS = False

    CARRIES_CONFIDENCE = False

    SUPPLIES_IDENTITY = False

    def __post_init__(self):

        if not str(self.target_claim_reference or "").strip():

            raise LicenceAssignmentRequestError(
                "target_claim_reference is required"
            )

        if not str(self.requested_licence or "").strip():

            raise LicenceAssignmentRequestError(
                "requested_licence is required"
            )

        if self.requested_licence in FORBIDDEN_REQUESTED_LICENCES:

            raise LicenceAssignmentRequestError(
                "a request may never ask for %r — a licence is not truth, "
                "probability, confidence or certainty"
                % (self.requested_licence,)
            )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "target_claim_reference": self.target_claim_reference,
            "requested_licence": self.requested_licence,
            "basis_reference": self.basis_reference,
            "actor_reference": self.actor_reference,
            "grants_truth": False,
            "approves_facts": False,
            "carries_confidence": False,
            "supplies_identity": False,
        }

    def __repr__(self):

        return (
            "LicenceAssignmentRequest(target=%r, requested=%r)"
            % (self.target_claim_reference, self.requested_licence)
        )


def build_licence_assignment_request(**fields) -> LicenceAssignmentRequest:

    """Build a request, refusing any field that would carry authority."""

    for key in fields:

        if key in FORBIDDEN_REQUEST_FIELDS:

            raise LicenceAssignmentRequestError(
                "a request may not carry %r — it asks, it does not decide"
                % (key,)
            )

        if key not in ALLOWED_REQUEST_FIELDS:

            raise LicenceAssignmentRequestError(
                "unknown request field: %r" % (key,)
            )

    return LicenceAssignmentRequest(**fields)
