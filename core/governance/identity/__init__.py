"""Reserved identity of the Claim Governance substrate (V1).

A governance-owned, in-memory ledger of identities that have been minted but not
yet bound to an object. It lets an id be referenced before its object exists,
which resolves R6 (the claim <-> licence circular dependency).

    reserve_*()   -> a ReservedIdentity handle (identity_v1 mints the id)
    consume()     -> inside the mint factories, binds the id to one object
    release()     -> abandons a reservation

identity_v1 remains the ONLY identity authority. This package never generates an
id of its own and never replaces identity_v1.

Dependency direction

    identity.reservation_v1  ->  identity_v1               ALLOWED
    identity.reservation_v1  ->  any client subsystem      FORBIDDEN
"""

from __future__ import annotations


from core.governance.identity.reservation_v1 import (
    CONTRACT,
    KIND_CLAIM,
    KIND_DERIVATION_EVENT,
    KIND_ENDORSEMENT_EVENT,
    KIND_LICENCE,
    KINDS,
    REASON_CONSUMED,
    REASON_FORGED,
    REASON_KIND_MISMATCH,
    REASON_RELEASED,
    REASON_UNKNOWN,
    REASON_UNKNOWN_KIND,
    STATES,
    STATE_CONSUMED,
    STATE_RELEASED,
    STATE_RESERVED,
    ReservationError,
    ReservationLedger,
    ReservedIdentity,
    VERSION,
    consume_reservation,
    reservation_ledger,
    reserve_claim_id,
    reserve_derivation_event_id,
    reserve_endorsement_event_id,
    reserve_licence_id,
)


__all__ = (
    "ReservedIdentity",
    "ReservationLedger",
    "ReservationError",
    "reservation_ledger",
    "reserve_claim_id",
    "reserve_licence_id",
    "reserve_derivation_event_id",
    "reserve_endorsement_event_id",
    "consume_reservation",
    "KIND_CLAIM",
    "KIND_LICENCE",
    "KIND_DERIVATION_EVENT",
    "KIND_ENDORSEMENT_EVENT",
    "KINDS",
    "STATE_RESERVED",
    "STATE_CONSUMED",
    "STATE_RELEASED",
    "STATES",
    "REASON_UNKNOWN",
    "REASON_FORGED",
    "REASON_CONSUMED",
    "REASON_RELEASED",
    "REASON_KIND_MISMATCH",
    "REASON_UNKNOWN_KIND",
    "CONTRACT",
    "VERSION",
)
