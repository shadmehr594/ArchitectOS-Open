"""LicenceStateView + resolve_licence_state (V1) — a READ-ONLY licence read model.

This is the authoritative way to answer "what licence state does this claim
hold?" without touching the claim (whose `licence_reference` back-link may be
None) and without reading a client.

It is a READ. It
    does NOT create objects
    does NOT mint ids
    does NOT create events
    does NOT mutate a claim
    does NOT assign a licence
    does NOT decide truth

It reads ONLY governance-owned artefacts supplied to it
    LicenceRecord      (the licence artefact)
    EndorsementEvent   (an act that granted a licence state)
    governance-owned references (a known claim set)

Conflict policy (honest, deterministic)
    When the supplied artefacts disagree about the state, this model does NOT
    reconcile them silently. It returns licence_state=None with
    reason="conflicting_licence_states: [...]" — the project rule is to report an
    unresolved conflict rather than invent a resolution.

Dependency direction

    accessors  ->  licence / lineage      ALLOWED
    accessors  ->  any client subsystem   FORBIDDEN
    anything   ->  accessors              FORBIDDEN (this is a leaf read model)
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple


from core.governance.licence import LICENCE_STATES
from core.governance.lineage.lineage_reference_v1 import is_claim_reference


CONTRACT = "LicenceStateViewV1"

VERSION = "1.0"


# ----------------------------------------------------------
# provenance / reason codes
# ----------------------------------------------------------

REASON_MISSING_CLAIM = "missing_claim_reference"

REASON_INVALID_CLAIM = "invalid_claim_reference"

REASON_UNRESOLVED_CLAIM = "unresolved_claim_reference"

REASON_MISSING_LICENCE = "missing_licence"

REASON_FROM_RECORD = "resolved_from_licence_record"

REASON_FROM_EVENT = "resolved_from_endorsement_event"

REASON_CONFLICT = "conflicting_licence_states"


REASONS = (
    REASON_MISSING_CLAIM,
    REASON_INVALID_CLAIM,
    REASON_UNRESOLVED_CLAIM,
    REASON_MISSING_LICENCE,
    REASON_FROM_RECORD,
    REASON_FROM_EVENT,
)


SOURCE_RECORD = "licence_record"

SOURCE_EVENT = "endorsement_event"


class LicenceStateViewError(ValueError):
    """Raised when a read model is malformed."""


@dataclass(frozen=True)
class LicenceStateView:

    """An immutable, read-only answer about a claim's licence state."""

    claim_reference: Optional[str]

    licence_reference: Optional[str]

    licence_state: Optional[str]

    reason: str

    # A view reports. It acts on nothing.
    CREATES_OBJECTS = False

    MINTS_IDENTITIES = False

    CREATES_EVENTS = False

    MUTATES_CLAIMS = False

    ASSIGNS_LICENCES = False

    DECIDES_TRUTH = False

    def __post_init__(self):

        if self.licence_state is not None and self.licence_state not in LICENCE_STATES:

            raise LicenceStateViewError(
                "unknown licence_state: %r" % (self.licence_state,)
            )

        if not str(self.reason or "").strip():

            raise LicenceStateViewError("a view requires a reason")

    @property
    def resolved(self) -> bool:

        """True only when a single licence state was determined."""

        return self.licence_state is not None

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "claim_reference": self.claim_reference,
            "licence_reference": self.licence_reference,
            "licence_state": self.licence_state,
            "reason": self.reason,
            "resolved": self.resolved,
            "creates_objects": False,
            "mints_identities": False,
            "creates_events": False,
            "mutates_claims": False,
            "assigns_licences": False,
            "decides_truth": False,
        }

    def __repr__(self):

        return "LicenceStateView(claim=%r, state=%r, reason=%r)" % (
            self.claim_reference,
            self.licence_state,
            self.reason,
        )


def _text(value) -> str:

    return str(value or "").strip()


def _candidates(
    claim_reference: str,
    licence_records,
    endorsement_events,
) -> Tuple[Tuple[str, Optional[str], str], ...]:
    """Structural reads only. Nothing is created, mutated or assigned."""

    found = []

    for record in licence_records or ():

        if _text(getattr(record, "target_claim_reference", None)) != claim_reference:

            continue

        state = _text(getattr(record, "licence_state", None))

        if state not in LICENCE_STATES:

            continue

        reference = getattr(record, "licence_id", None)

        found.append(
            (state, str(reference) if reference else None, SOURCE_RECORD)
        )

    for event in endorsement_events or ():

        if _text(getattr(event, "target_claim_reference", None)) != claim_reference:

            continue

        state = _text(getattr(event, "new_licence", None))

        if state not in LICENCE_STATES:

            continue

        # An endorsement event is an act, not a licence artefact: it grants a
        # state but carries no `lic_` reference.
        found.append((state, None, SOURCE_EVENT))

    return tuple(found)


def resolve_licence_state(
    claim_reference,
    *,
    licence_records: Iterable[Any] = (),
    endorsement_events: Iterable[Any] = (),
    known_claim_references: Optional[Iterable[str]] = None,
) -> LicenceStateView:

    """Resolve a claim's licence state from governance-owned artefacts.

    Read-only. It never creates, mints, mutates or assigns anything.
    """

    text = _text(claim_reference)

    # ---- 1. the reference must be a claim reference ----
    if not text:

        return LicenceStateView(None, None, None, REASON_MISSING_CLAIM)

    if not is_claim_reference(text):

        return LicenceStateView(text, None, None, REASON_INVALID_CLAIM)

    if known_claim_references is not None:

        if text not in {str(item) for item in known_claim_references}:

            return LicenceStateView(text, None, None, REASON_UNRESOLVED_CLAIM)

    # ---- 2. gather the states the artefacts assert ----
    candidates = _candidates(text, licence_records, endorsement_events)

    if not candidates:

        return LicenceStateView(text, None, None, REASON_MISSING_LICENCE)

    # ---- 3. conflicting states are REPORTED, never silently reconciled ----
    distinct = sorted({state for state, _, _ in candidates})

    if len(distinct) > 1:

        return LicenceStateView(
            text,
            None,
            None,
            "%s: %r" % (REASON_CONFLICT, distinct),
        )

    state = distinct[0]

    # ---- 4. prefer a licence artefact's reference when one exists ----
    licence_reference = None

    source = SOURCE_EVENT

    for candidate_state, candidate_reference, candidate_source in candidates:

        if candidate_state == state and candidate_reference:

            licence_reference = candidate_reference

            source = candidate_source

            break

    return LicenceStateView(
        text,
        licence_reference,
        state,
        REASON_FROM_RECORD if source == SOURCE_RECORD else REASON_FROM_EVENT,
    )
