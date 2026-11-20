"""EndorsementRequest (V1) — an immutable, authority-free request.

The request ASKS governance to consider an endorsement. It carries no licence,
no truth, no approval and no claim mutation. Governance decides everything.

It may carry
    actor_reference, target_claim_reference, act_classification, requested_scope

It may NEVER carry
    a new licence, truth, approval, claim mutation, knowledge status
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Optional


from core.governance.act_classifier.act_classification_v1 import (
    ActClassification,
)


CONTRACT = "EndorsementRequestV1"

VERSION = "1.0"


ALLOWED_REQUEST_FIELDS = (
    "actor_reference",
    "target_claim_reference",
    "act_classification",
    "requested_scope",
)


FORBIDDEN_REQUEST_FIELDS = (
    "new_licence",
    "new_license",
    "licence",
    "license",
    "truth",
    "truth_status",
    "is_true",
    "approved",
    "is_approved",
    "approval",
    "content",
    "new_content",
    "claim_mutation",
    "knowledge_status",
)


class EndorsementRequestError(ValueError):
    """Raised when a request is malformed or carries authority."""


@dataclass(frozen=True)
class EndorsementRequest:

    actor_reference: str

    target_claim_reference: str

    act_classification: ActClassification

    requested_scope: Optional[str] = None

    # A request asks; it does not decide. Declared, not merely documented.
    REQUESTS_LICENCE = False

    DECIDES_TRUTH = False

    APPROVES_CLAIMS = False

    MUTATES_CLAIMS = False

    def __post_init__(self):

        if not isinstance(self.act_classification, ActClassification):

            raise EndorsementRequestError(
                "act_classification must be an ActClassification"
            )

        if not str(self.actor_reference or "").strip():

            raise EndorsementRequestError("actor_reference is required")

        if not str(self.target_claim_reference or "").strip():

            raise EndorsementRequestError(
                "target_claim_reference is required"
            )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "actor_reference": self.actor_reference,
            "target_claim_reference": self.target_claim_reference,
            "act_classification": self.act_classification.to_dict(),
            "requested_scope": self.requested_scope,
            "requests_licence": False,
            "decides_truth": False,
            "approves_claims": False,
            "mutates_claims": False,
        }

    def __repr__(self):

        return (
            "EndorsementRequest(actor=%r, target=%r, act=%r)"
            % (
                self.actor_reference,
                self.target_claim_reference,
                self.act_classification.act_type,
            )
        )


def build_endorsement_request(**fields) -> EndorsementRequest:

    """Build a request, refusing any field that would carry authority."""

    for key in fields:

        if key in FORBIDDEN_REQUEST_FIELDS:

            raise EndorsementRequestError(
                "a request may not carry %r — it asks, it does not decide"
                % (key,)
            )

        if key not in ALLOWED_REQUEST_FIELDS:

            raise EndorsementRequestError(
                "unknown request field: %r" % (key,)
            )

    return EndorsementRequest(**fields)
