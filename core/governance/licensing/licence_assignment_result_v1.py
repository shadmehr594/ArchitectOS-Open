"""LicenceAssignmentResult (V1) — the immutable outcome of a licence assignment.

It carries the assignment flag, the licence reference, the target claim
reference, a reason and (on success) the governance-owned LicenceRecord. It
carries NO truth, NO approval, NO confidence and NO knowledge status.

It may carry
    assigned, licence_reference, target_claim_reference, reason, licence_record

It may NEVER carry
    truth, approval, confidence, knowledge status, claim_id, licence_id

The `licence_record` is exposed so a runtime can resolve the licence state (the
G3 accessor) and source `previous_licence` without re-minting. It is NOT
serialised by to_dict(); the object is immutable, so no ownership transfers.
Precedent: ClaimMintResult.claim.
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Optional


CONTRACT = "LicenceAssignmentResultV1"

VERSION = "1.0"


ALLOWED_RESULT_FIELDS = (
    "assigned",
    "licence_reference",
    "target_claim_reference",
    "reason",
    "licence_record",
)


FORBIDDEN_RESULT_FIELDS = (
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
    "claim_id",
    "licence_id",
    "license_id",
    "scope",
)


class LicenceAssignmentResultError(ValueError):
    """Raised when a result is malformed or carries authority."""


@dataclass(frozen=True)
class LicenceAssignmentResult:

    assigned: bool

    licence_reference: Optional[str]

    target_claim_reference: Optional[str]

    reason: str

    # The governance-owned artefact, exposed so a runtime can resolve the licence
    # state (G3) and source `previous_licence` without re-minting. Immutable, and
    # NOT serialised by to_dict().
    licence_record: Optional[Any] = None

    # An assignment reports a licence. It decides nothing else.
    CREATES_CLAIMS = False

    DECIDES_TRUTH = False

    CREATES_KNOWLEDGE = False

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "assigned": self.assigned,
            "licence_reference": self.licence_reference,
            "target_claim_reference": self.target_claim_reference,
            "reason": self.reason,
            "creates_claims": False,
            "decides_truth": False,
            "creates_knowledge": False,
        }

    def __repr__(self):

        return "LicenceAssignmentResult(assigned=%r, licence_reference=%r)" % (
            self.assigned,
            self.licence_reference,
        )


def build_licence_assignment_result(**fields) -> LicenceAssignmentResult:

    """Build a result, refusing any field that would carry authority."""

    for key in fields:

        if key in FORBIDDEN_RESULT_FIELDS:

            raise LicenceAssignmentResultError(
                "a licence assignment result may not carry %r — assigning a "
                "licence is not deciding truth" % (key,)
            )

        if key not in ALLOWED_RESULT_FIELDS:

            raise LicenceAssignmentResultError(
                "unknown result field: %r" % (key,)
            )

    return LicenceAssignmentResult(**fields)
