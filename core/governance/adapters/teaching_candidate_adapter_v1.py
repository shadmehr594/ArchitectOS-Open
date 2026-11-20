"""TeachingCandidate -> advisory proposal material adapter (V1).

Connects the existing TeachingCandidate to governance WITHOUT transferring
ownership. The candidate stays conversation-owned.

The candidate is consumed STRUCTURALLY (a mapping, or an object with
attributes), so this module never imports core.conversation.

Transfers
    provenance, candidate text, advisory category

NEVER transfers
    scope authority, knowledge_class authority, status as licence
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict


from core.governance.licence import LICENCE_STATES


CONTRACT = "TeachingCandidateAdapterV1"

VERSION = "1.0"


class TeachingCandidateAdapterError(ValueError):
    """Raised when a teaching candidate cannot be adapted."""


def _get(source, key):

    if isinstance(source, dict):

        return source.get(key)

    return getattr(source, key, None)


def _text(value) -> str:

    return str(value or "").strip()


@dataclass(frozen=True)
class TeachingProposalMaterial:

    candidate_text: str

    advisory_category: str

    provenance_reference: str

    # Advisory only. Nothing here is authority.
    ADVISORY = True

    GRANTS_SCOPE = False

    GRANTS_KNOWLEDGE_CLASS = False

    STATUS_IS_LICENCE = False

    CREATES_CLAIMS = False

    CREATES_LICENCES = False

    def __post_init__(self):

        if not self.candidate_text:

            raise TeachingCandidateAdapterError("candidate_text is required")

        if not self.advisory_category:

            raise TeachingCandidateAdapterError(
                "advisory_category is required"
            )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "candidate_text": self.candidate_text,
            "advisory_category": self.advisory_category,
            "provenance_reference": self.provenance_reference,
            "advisory": True,
            "grants_scope": False,
            "grants_knowledge_class": False,
            "status_is_licence": False,
            "creates_claims": False,
            "creates_licences": False,
        }

    def __repr__(self):

        return "TeachingProposalMaterial(category=%r, advisory=True)" % (
            self.advisory_category,
        )


def to_proposal_material(candidate) -> TeachingProposalMaterial:

    """Adapt a TeachingCandidate into ADVISORY proposal material."""

    if candidate is None:

        raise TeachingCandidateAdapterError("no candidate supplied")

    # A candidate status must never be read as a licence.
    status = _get(candidate, "status")

    if status in LICENCE_STATES:

        raise TeachingCandidateAdapterError(
            "a candidate status must never be used as a licence: %r"
            % (status,)
        )

    text = _text(_get(candidate, "normalized_meaning")) or _text(
        _get(candidate, "raw_statement")
    )

    if not text:

        raise TeachingCandidateAdapterError(
            "the candidate carries no usable text"
        )

    category = (
        _text(_get(candidate, "candidate_kind"))
        or _text(_get(candidate, "knowledge_class"))
        or "unknown"
    )

    provenance = _text(_get(candidate, "provenance")) or "unknown"

    return TeachingProposalMaterial(
        candidate_text=text,
        advisory_category=category,
        provenance_reference=provenance,
    )
