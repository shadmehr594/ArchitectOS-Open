"""KnowledgeCandidate (V1) — an immutable, authority-free candidate.

A candidate RECORDS that a governed claim and licence state are eligible to
become a knowledge candidate. It is NOT truth, NOT approval and NOT fact
creation.

Allowed fields only
    candidate_reference, source_claim_reference, licence_reference, scope,
    lineage_reference

Forbidden
    truth, verified_truth, certainty, probability, confidence_as_truth,
    approved, fact_status, knowledge_status_as_authority
"""

from __future__ import annotations


import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple


CONTRACT = "KnowledgeCandidateV1"

VERSION = "1.0"


# A derived candidate reference. It is computed from the candidate's own
# content, so a caller can never supply it.
CANDIDATE_REFERENCE_PREFIX = "kcd_"


ALLOWED_CANDIDATE_FIELDS = (
    "candidate_reference",
    "source_claim_reference",
    "licence_reference",
    "scope",
    "lineage_reference",
)


FORBIDDEN_CANDIDATE_FIELDS = (
    "truth",
    "truth_status",
    "is_true",
    "verified_truth",
    "certainty",
    "probability",
    "confidence",
    "confidence_as_truth",
    "approved",
    "is_approved",
    "approval",
    "fact_status",
    "is_fact",
    "knowledge_status",
    "knowledge_status_as_authority",
    "knowledge_class",
)


class KnowledgeCandidateError(ValueError):
    """Raised when a candidate is malformed or carries authority."""


def _text(value) -> str:

    return str(value or "").strip()


def _refs(values) -> Tuple[str, ...]:

    if isinstance(values, str):

        return (_text(values),) if _text(values) else ()

    if not isinstance(values, (list, tuple)):

        return ()

    result = []

    for item in values:

        text = _text(item)

        if text and text not in result:

            result.append(text)

    return tuple(result)


@dataclass(frozen=True)
class KnowledgeCandidate:

    candidate_reference: str

    source_claim_reference: str

    licence_reference: str

    scope: str

    lineage_reference: Tuple[str, ...] = ()

    # A candidate records eligibility. It decides nothing.
    CREATES_TRUTH = False

    APPROVES_FACT = False

    CHANGES_CLAIM = False

    ASSIGNS_LICENCE = False

    def __post_init__(self):

        for value, name in (
            (self.candidate_reference, "candidate_reference"),
            (self.source_claim_reference, "source_claim_reference"),
            (self.licence_reference, "licence_reference"),
            (self.scope, "scope"),
        ):

            if not _text(value):

                raise KnowledgeCandidateError("%s is required" % (name,))

        object.__setattr__(
            self, "lineage_reference", _refs(self.lineage_reference)
        )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "candidate_reference": self.candidate_reference,
            "source_claim_reference": self.source_claim_reference,
            "licence_reference": self.licence_reference,
            "scope": self.scope,
            "lineage_reference": list(self.lineage_reference),
            "creates_truth": False,
            "approves_fact": False,
            "changes_claim": False,
            "assigns_licence": False,
        }

    def __repr__(self):

        return "KnowledgeCandidate(candidate_reference=%r, source=%r)" % (
            self.candidate_reference,
            self.source_claim_reference,
        )


def derive_candidate_reference(
    source_claim_reference,
    licence_reference,
    scope,
    lineage_reference: Iterable[str] = (),
) -> str:

    """A deterministic candidate reference, derived from the candidate itself."""

    payload = repr(
        (
            _text(source_claim_reference),
            _text(licence_reference),
            _text(scope),
            tuple(_refs(lineage_reference)),
        )
    )

    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    return CANDIDATE_REFERENCE_PREFIX + digest


def build_knowledge_candidate(
    *,
    source_claim_reference,
    licence_reference,
    scope,
    lineage_reference: Iterable[str] = (),
) -> KnowledgeCandidate:

    """Build a candidate. The reference is DERIVED here, never supplied."""

    parents = _refs(lineage_reference)

    return KnowledgeCandidate(
        candidate_reference=derive_candidate_reference(
            source_claim_reference,
            licence_reference,
            scope,
            parents,
        ),
        source_claim_reference=_text(source_claim_reference),
        licence_reference=_text(licence_reference),
        scope=_text(scope),
        lineage_reference=parents,
    )
