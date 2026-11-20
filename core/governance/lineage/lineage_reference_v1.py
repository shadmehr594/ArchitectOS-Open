"""LineageReference (V1) — an immutable, authority-free reference structure.

A reference is a POINTER. It grants no authority, creates no claim and changes
no claim. It is a value object, never a store.

Three reference kinds
    parent_claim_references   claims this claim was derived from
    trigger_references        external observations that prompted it
    evidence_references       external evidence it rests on

A reference may point outside governance (an observation element is not a
governance object). Only claim-shaped references are resolvable; the DAG safety
helper checks those.

No import of any client subsystem.
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple


# The reference prefixes and the claim-shape predicate are re-exported from the
# single source of truth (identity_v1) so no literal "clm_"/"dev_"/"eev_" is
# duplicated anywhere in governance.
from core.governance.identity_v1 import (
    CLAIM_REFERENCE_PREFIX,
    DERIVATION_EVENT_PREFIX,
    ENDORSEMENT_EVENT_PREFIX,
    is_claim_reference,
    is_lineage_reference,
)


CONTRACT = "LineageReferenceV1"

VERSION = "1.0"


REFERENCE_KINDS = (
    "parent_claim_references",
    "trigger_references",
    "evidence_references",
)


# Reference classification. The prefixes live in identity_v1 (imported above).
# Only claim-shaped references are resolvable inside governance; a licence is
# NOT a lineage node. Every other reference is external (an observation
# element, a provider phrase, an authored rule, ...) and is never checked for
# existence.
def is_governance_reference(value) -> bool:

    return is_lineage_reference(value)


def is_external_reference(value) -> bool:

    return not is_lineage_reference(value)


class LineageReferenceError(ValueError):
    """Raised when a reference structure is malformed."""


def _clean(values: Iterable[Any], kind: str) -> Tuple[str, ...]:

    result = []

    for value in values or ():

        text = str(value or "").strip()

        if not text:

            raise LineageReferenceError(
                "%s may not contain an empty reference" % (kind,)
            )

        if text not in result:

            result.append(text)

    return tuple(result)


@dataclass(frozen=True)
class LineageReference:

    parent_claim_references: Tuple[str, ...] = ()

    trigger_references: Tuple[str, ...] = ()

    evidence_references: Tuple[str, ...] = ()

    # A reference has NO authority. Declared, not merely documented.
    AUTHORITY = False

    CREATES_CLAIMS = False

    CHANGES_CLAIMS = False

    STORES_LINEAGE = False

    def __post_init__(self):

        for kind in REFERENCE_KINDS:

            object.__setattr__(
                self, kind, _clean(getattr(self, kind), kind)
            )

    def all_references(self) -> Tuple[str, ...]:

        return tuple(
            self.parent_claim_references
            + self.trigger_references
            + self.evidence_references
        )

    def references_itself(self, claim_id) -> bool:

        """True when the reference set contains its own subject."""

        return str(claim_id or "") in self.all_references()

    def count(self) -> int:

        return len(self.all_references())

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "parent_claim_references": list(self.parent_claim_references),
            "trigger_references": list(self.trigger_references),
            "evidence_references": list(self.evidence_references),
            "authority": False,
            "creates_claims": False,
            "changes_claims": False,
            "stores_lineage": False,
        }

    def __repr__(self):

        return (
            "LineageReference(parents=%r, triggers=%r, evidence=%r)"
            % (
                self.parent_claim_references,
                self.trigger_references,
                self.evidence_references,
            )
        )


def build_lineage_reference(**fields) -> LineageReference:

    """Build a reference structure, refusing unknown reference kinds."""

    for key in fields:

        if key not in REFERENCE_KINDS:

            raise LineageReferenceError(
                "unknown reference kind: %r" % (key,)
            )

    return LineageReference(**fields)
