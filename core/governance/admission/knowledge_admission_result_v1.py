"""KnowledgeAdmissionResult (V1) — the immutable outcome of knowledge admission.

An admission result is a JUDGEMENT of a GATE, never a truth engine. It carries
exactly three fields and creates nothing, mutates nothing and assigns nothing.

Allowed fields (exactly these three)
    admitted, candidate_reference, reason

It may NEVER carry
    truth, truth_status, is_true, verified_truth, certainty, probability,
    confidence, confidence_as_truth, approval, approved, is_approved,
    fact_status, is_fact, knowledge_status, knowledge_class, scope,
    scope_escalation, licence, licence_reference, licence_id, created_licence

Admission is not truth. Admitting a candidate does NOT make it true, does NOT
approve a fact and does NOT create a licence.
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Optional


CONTRACT = "KnowledgeAdmissionResultV1"

VERSION = "1.0"


ALLOWED_RESULT_FIELDS = (
    "admitted",
    "candidate_reference",
    "reason",
)


FORBIDDEN_RESULT_FIELDS = (
    "truth",
    "truth_status",
    "is_true",
    "verified_truth",
    "certainty",
    "probability",
    "confidence",
    "confidence_as_truth",
    "approval",
    "approved",
    "is_approved",
    "fact_status",
    "is_fact",
    "knowledge_status",
    "knowledge_class",
    "scope",
    "scope_escalation",
    "licence",
    "license",
    "licence_state",
    "licence_reference",
    "licence_id",
    "license_id",
    "created_licence",
    "licence_creation",
)


# A boundary result that is explicitly NOT a decision. It is carried in the
# `reason` field, because the result has no rule_code field of its own.
NOT_IMPLEMENTED_REASON_PREFIX = "not implemented in V1: "


class KnowledgeAdmissionResultError(ValueError):
    """Raised when a result is malformed or carries authority."""


@dataclass(frozen=True)
class KnowledgeAdmissionResult:

    admitted: bool

    candidate_reference: Optional[str]

    reason: str

    # An admission reports eligibility. It decides nothing else.
    CREATES_TRUTH = False

    APPROVES_FACT = False

    ESCALATES_SCOPE = False

    CREATES_LICENCE = False

    MUTATES_CLAIM = False

    def to_dict(self) -> Dict[str, Any]:
        """A 3-field view. It never exposes a truth or authority field."""

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "admitted": self.admitted,
            "candidate_reference": self.candidate_reference,
            "reason": self.reason,
            "creates_truth": False,
            "approves_fact": False,
            "escalates_scope": False,
            "creates_licence": False,
            "mutates_claim": False,
        }

    def __repr__(self):

        return "KnowledgeAdmissionResult(admitted=%r, candidate_reference=%r)" % (
            self.admitted,
            self.candidate_reference,
        )


def build_knowledge_admission_result(**fields) -> KnowledgeAdmissionResult:
    """Build a result, refusing any field that would carry authority."""

    for key in fields:

        if key in FORBIDDEN_RESULT_FIELDS:

            raise KnowledgeAdmissionResultError(
                "an admission result may not carry %r — admission is not "
                "truth, approval or licensing" % (key,)
            )

        if key not in ALLOWED_RESULT_FIELDS:

            raise KnowledgeAdmissionResultError(
                "unknown admission result field: %r" % (key,)
            )

    return KnowledgeAdmissionResult(**fields)


def not_implemented_admission_result(feature) -> KnowledgeAdmissionResult:
    """An explicit NOT_IMPLEMENTED boundary result. It decides nothing."""

    return KnowledgeAdmissionResult(
        admitted=False,
        candidate_reference=None,
        reason=NOT_IMPLEMENTED_REASON_PREFIX + str(feature),
    )
