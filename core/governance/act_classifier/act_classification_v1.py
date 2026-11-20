"""ActClassification (V1) — the immutable output of the act classifier.

A classification states WHICH KIND OF ACT occurred. It states nothing about the
world: it does not approve a claim, does not assert truth, does not grant a
licence and does not create knowledge.

It may carry
    act_type, raw_text_reference, language, confidence_descriptor

It may NEVER carry
    claim_id, licence, scope, truth_status, knowledge_status
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Optional


CONTRACT = "ActClassificationV1"

VERSION = "1.0"


ACT_TYPES = (
    "endorsement",
    "preference",
    "judgement",
    "decision",
    "outcome",
    "unknown",
)


CONFIDENCE_DESCRIPTORS = (
    "explicit",
    "weak",
    "none",
)


ALLOWED_CLASSIFICATION_FIELDS = (
    "act_type",
    "raw_text_reference",
    "language",
    "confidence_descriptor",
)


FORBIDDEN_CLASSIFICATION_FIELDS = (
    "claim_id",
    "licence",
    "license",
    "scope",
    "truth_status",
    "knowledge_status",
    "truth",
    "is_true",
    "approved",
    "is_approved",
)


class ActClassificationError(ValueError):
    """Raised when a classification is malformed or carries authority."""


@dataclass(frozen=True)
class ActClassification:

    act_type: str

    raw_text_reference: Optional[str] = None

    language: str = "unknown"

    confidence_descriptor: str = "none"

    # The classifier decides NOTHING beyond the act kind.
    DECIDES_TRUTH = False

    CREATES_CLAIMS = False

    CREATES_LICENCES = False

    CREATES_EVENTS = False

    APPROVES_CLAIMS = False

    def __post_init__(self):

        if self.act_type not in ACT_TYPES:

            raise ActClassificationError(
                "unknown act_type: %r" % (self.act_type,)
            )

        if self.confidence_descriptor not in CONFIDENCE_DESCRIPTORS:

            raise ActClassificationError(
                "unknown confidence_descriptor: %r"
                % (self.confidence_descriptor,)
            )

    def is_unknown(self) -> bool:

        return self.act_type == "unknown"

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "act_type": self.act_type,
            "raw_text_reference": self.raw_text_reference,
            "language": self.language,
            "confidence_descriptor": self.confidence_descriptor,
            "decides_truth": False,
            "creates_claims": False,
            "creates_licences": False,
            "creates_events": False,
            "approves_claims": False,
        }

    def __repr__(self):

        return (
            "ActClassification(act_type=%r, confidence=%r)"
            % (self.act_type, self.confidence_descriptor)
        )


def build_act_classification(**fields) -> ActClassification:

    """Build a classification, refusing any field that would carry authority."""

    for key in fields:

        if key in FORBIDDEN_CLASSIFICATION_FIELDS:

            raise ActClassificationError(
                "a classification may not carry %r — it classifies an act, "
                "it does not decide anything" % (key,)
            )

        if key not in ALLOWED_CLASSIFICATION_FIELDS:

            raise ActClassificationError(
                "unknown classification field: %r" % (key,)
            )

    return ActClassification(**fields)
