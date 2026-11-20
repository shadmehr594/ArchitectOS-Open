"""DAG safety check (V1) — STRUCTURAL validation only.

Checks
    * references point to existing ids (claim-shaped references only)
    * events reference existing objects
    * no forward references (an event may not reference the claim it creates)
    * no self references

Deliberately NOT implemented here (they belong to a future transition validator)
    * scope widening rules
    * licence transitions
    * knowledge admission rules

Read-only: this module never mutates a claim or an event.
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple


from core.governance.lineage.lineage_reference_v1 import (
    LineageReference,
    is_claim_reference,
)


CONTRACT = "DagSafetyV1"

VERSION = "1.0"


VIOLATION_DUPLICATE_CLAIM_ID = "duplicate_claim_id"

VIOLATION_SELF_REFERENCE = "self_reference"

VIOLATION_MISSING_REFERENCE = "missing_reference"

VIOLATION_FORWARD_REFERENCE = "forward_reference"

VIOLATION_NON_CLAIM_REFERENCE = "non_claim_reference"


@dataclass(frozen=True)
class DagViolation:

    code: str

    subject: str

    detail: str

    def to_dict(self) -> Dict[str, Any]:

        return {
            "code": self.code,
            "subject": self.subject,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class DagCheckReport:

    ok: bool

    violations: Tuple[DagViolation, ...]

    checked_claims: int

    checked_derivation_events: int

    checked_endorsement_events: int

    read_only: bool = True

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "ok": self.ok,
            "violations": [item.to_dict() for item in self.violations],
            "checked_claims": self.checked_claims,
            "checked_derivation_events": self.checked_derivation_events,
            "checked_endorsement_events": self.checked_endorsement_events,
            "read_only": True,
        }


def check_dag(
    *,
    claims: Iterable[Any] = (),
    derivation_events: Iterable[Any] = (),
    endorsement_events: Iterable[Any] = (),
    references: Optional[Mapping[str, LineageReference]] = None,
) -> DagCheckReport:

    """Structural DAG check over the supplied immutable objects."""

    violations = []

    claim_list = list(claims or ())

    derivation_list = list(derivation_events or ())

    endorsement_list = list(endorsement_events or ())

    reference_map = dict(references or {})

    # ---- index claims ----
    claim_ids = set()

    created_by = {}

    for claim in claim_list:

        claim_id = str(getattr(claim, "claim_id", "") or "")

        if claim_id in claim_ids:

            violations.append(
                DagViolation(
                    VIOLATION_DUPLICATE_CLAIM_ID,
                    claim_id,
                    "claim_id appears more than once",
                )
            )

        claim_ids.add(claim_id)

        creation_event = getattr(claim, "creation_event", None)

        if creation_event:

            created_by[str(creation_event)] = claim_id

    # ---- claims: resolvable parents, no self reference ----
    for claim in claim_list:

        claim_id = str(getattr(claim, "claim_id", "") or "")

        reference = reference_map.get(claim_id)

        if reference is not None:

            parents = reference.parent_claim_references

        else:

            parents = tuple(
                getattr(claim, "lineage_reference", ()) or ()
            )

        for parent in parents:

            parent_id = str(parent or "")

            if parent_id == claim_id:

                violations.append(
                    DagViolation(
                        VIOLATION_SELF_REFERENCE,
                        claim_id,
                        "a claim may not be its own parent",
                    )
                )

                continue

            if not is_claim_reference(parent_id):

                violations.append(
                    DagViolation(
                        VIOLATION_NON_CLAIM_REFERENCE,
                        claim_id,
                        "parent %r is not a claim reference" % (parent_id,),
                    )
                )

                continue

            if parent_id not in claim_ids:

                violations.append(
                    DagViolation(
                        VIOLATION_MISSING_REFERENCE,
                        claim_id,
                        "parent %r does not resolve" % (parent_id,),
                    )
                )

    # ---- derivation events ----
    for event in derivation_list:

        event_id = str(getattr(event, "event_id", "") or "")

        output = str(getattr(event, "output_claim_reference", "") or "")

        if not is_claim_reference(output):

            violations.append(
                DagViolation(
                    VIOLATION_NON_CLAIM_REFERENCE,
                    event_id,
                    "output %r is not a claim reference" % (output,),
                )
            )

        elif output not in claim_ids:

            violations.append(
                DagViolation(
                    VIOLATION_MISSING_REFERENCE,
                    event_id,
                    "output %r does not resolve" % (output,),
                )
            )

        inputs = tuple(getattr(event, "input_references", ()) or ())

        for item in inputs:

            item_id = str(item or "")

            if item_id == output:

                violations.append(
                    DagViolation(
                        VIOLATION_FORWARD_REFERENCE,
                        event_id,
                        "an event may not reference the claim it creates",
                    )
                )

                continue

            if is_claim_reference(item_id) and item_id not in claim_ids:

                violations.append(
                    DagViolation(
                        VIOLATION_MISSING_REFERENCE,
                        event_id,
                        "input %r does not resolve" % (item_id,),
                    )
                )

        # forward reference: the claim this event created may not be its input
        produced = created_by.get(event_id)

        if produced and produced in [str(item) for item in inputs]:

            violations.append(
                DagViolation(
                    VIOLATION_FORWARD_REFERENCE,
                    event_id,
                    "input references the claim this event created",
                )
            )

    # ---- endorsement events ----
    for event in endorsement_list:

        event_id = str(getattr(event, "event_id", "") or "")

        target = str(getattr(event, "target_claim_reference", "") or "")

        if not is_claim_reference(target):

            violations.append(
                DagViolation(
                    VIOLATION_NON_CLAIM_REFERENCE,
                    event_id,
                    "target %r is not a claim reference" % (target,),
                )
            )

        elif target not in claim_ids:

            violations.append(
                DagViolation(
                    VIOLATION_MISSING_REFERENCE,
                    event_id,
                    "target %r does not resolve" % (target,),
                )
            )

    return DagCheckReport(
        ok=not violations,
        violations=tuple(violations),
        checked_claims=len(claim_list),
        checked_derivation_events=len(derivation_list),
        checked_endorsement_events=len(endorsement_list),
    )
