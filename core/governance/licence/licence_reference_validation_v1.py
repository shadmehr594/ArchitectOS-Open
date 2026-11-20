"""LicenceReferenceValidation (V1) — shape/existence validation of a reference.

A boundary that answers ONE question: is this a well-formed licence reference,
and (when a known set is supplied) does it exist?

It is a CHECK, never an action. It
    does NOT create a LicenceRecord
    does NOT mutate a Claim
    does NOT assign a licence state
    does NOT decide truth

Allowed inputs
    a licence reference
    (optional) a set of known licence references

The reference prefix is imported from the single source of truth (identity_v1);
this module declares no "lic_" literal of its own.

No import of any client subsystem.
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional


from core.governance.identity_v1 import (
    LICENCE_REFERENCE_PREFIX,
    is_licence_reference,
)


CONTRACT = "LicenceReferenceValidationV1"

VERSION = "1.0"


RULE_ALLOWED = "allowed"

RULE_MISSING = "missing_licence_reference"

RULE_INVALID = "invalid_licence_reference"

RULE_UNRESOLVED = "unresolved_licence_reference"


RULE_CODES = (
    RULE_ALLOWED,
    RULE_MISSING,
    RULE_INVALID,
    RULE_UNRESOLVED,
)


class LicenceReferenceValidationError(ValueError):
    """Raised when a validation result is malformed."""


@dataclass(frozen=True)
class LicenceReferenceValidation:

    valid: bool

    licence_reference: Optional[str]

    reason: str

    rule_code: str

    # A check reports shape/existence. It acts on nothing.
    CREATES_LICENCE = False

    MUTATES_CLAIM = False

    ASSIGNS_TRUTH = False

    def __post_init__(self):

        if self.rule_code not in RULE_CODES:

            raise LicenceReferenceValidationError(
                "unknown rule_code: %r" % (self.rule_code,)
            )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "valid": self.valid,
            "licence_reference": self.licence_reference,
            "reason": self.reason,
            "rule_code": self.rule_code,
            "creates_licence": False,
            "mutates_claim": False,
            "assigns_truth": False,
        }

    def __repr__(self):

        return "LicenceReferenceValidation(valid=%r, rule_code=%r)" % (
            self.valid,
            self.rule_code,
        )


def validate_licence_reference(
    licence_reference,
    *,
    known_licence_references: Optional[Iterable[str]] = None,
) -> LicenceReferenceValidation:

    """Validate a licence reference. SHAPE only, plus OPTIONAL existence."""

    text = str(licence_reference or "").strip()

    if not text:

        return LicenceReferenceValidation(
            valid=False,
            licence_reference=None,
            reason="licence reference is required",
            rule_code=RULE_MISSING,
        )

    if not is_licence_reference(text):

        return LicenceReferenceValidation(
            valid=False,
            licence_reference=text,
            reason=(
                "licence reference is not governance-shaped (expected %r): %r"
                % (LICENCE_REFERENCE_PREFIX, text)
            ),
            rule_code=RULE_INVALID,
        )

    if known_licence_references is not None:

        known = {str(item) for item in known_licence_references}

        if text not in known:

            return LicenceReferenceValidation(
                valid=False,
                licence_reference=text,
                reason="licence reference does not resolve: %r" % (text,),
                rule_code=RULE_UNRESOLVED,
            )

    return LicenceReferenceValidation(
        valid=True,
        licence_reference=text,
        reason="licence reference is well-formed",
        rule_code=RULE_ALLOWED,
    )
