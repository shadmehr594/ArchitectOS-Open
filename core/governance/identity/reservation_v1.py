"""Reserved identity ledger (V1) — governance-owned, in-memory.

A reservation mints a governance id WITHOUT binding it to an object yet, so an
id can be referenced before its object exists. This is what resolves R6: a
licence can target a claim that has not been minted yet.

INVARIANTS
    * the ledger NEVER generates an id — it calls identity_v1 for every id;
    * identity_v1 remains the ONLY id authority (uuid4 lives only there);
    * the ledger is governance-owned and in-memory (no persistence);
    * a ReservedIdentity is a HANDLE, not an authority: consumption is validated
      against the ledger, so a forged handle is rejected;
    * lifecycle: reserved -> consumed | released (both terminal).

Dependency direction

    reservation_v1  ->  identity_v1                        ALLOWED
    reservation_v1  ->  any client subsystem               FORBIDDEN
    claim / licence / events  ->  reservation_v1           ALLOWED (consume only)

This module declares no `clm_` / `lic_` / `dev_` / `eev_` literal; it refers to
identity kinds by name and delegates generation to identity_v1.
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Optional


from core.governance import identity_v1


CONTRACT = "GovernanceReservationV1"

VERSION = "1.0"


# ----------------------------------------------------------
# identity kinds (names, never prefixes)
# ----------------------------------------------------------

KIND_CLAIM = "claim"

KIND_LICENCE = "licence"

KIND_DERIVATION_EVENT = "derivation_event"

KIND_ENDORSEMENT_EVENT = "endorsement_event"


KINDS = (
    KIND_CLAIM,
    KIND_LICENCE,
    KIND_DERIVATION_EVENT,
    KIND_ENDORSEMENT_EVENT,
)


# kind -> the identity_v1 minting call. identity_v1 is the ONLY generator.
_GENERATORS = {
    KIND_CLAIM: identity_v1.new_claim_id,
    KIND_LICENCE: identity_v1.new_licence_id,
    KIND_DERIVATION_EVENT: identity_v1.new_derivation_event_id,
    KIND_ENDORSEMENT_EVENT: identity_v1.new_endorsement_event_id,
}


# ----------------------------------------------------------
# lifecycle states
# ----------------------------------------------------------

STATE_RESERVED = "reserved"

STATE_CONSUMED = "consumed"

STATE_RELEASED = "released"


STATES = (
    STATE_RESERVED,
    STATE_CONSUMED,
    STATE_RELEASED,
)


# ----------------------------------------------------------
# rejection codes (carried in the exception message)
# ----------------------------------------------------------

REASON_UNKNOWN = "reservation_unknown"

REASON_FORGED = "reservation_forged"

REASON_CONSUMED = "reservation_consumed"

REASON_RELEASED = "reservation_released"

REASON_KIND_MISMATCH = "reservation_kind_mismatch"

REASON_UNKNOWN_KIND = "reservation_unknown_kind"


class ReservationError(ValueError):
    """Raised when a reservation cannot be minted, consumed or released."""


@dataclass(frozen=True)
class ReservedIdentity:

    """An immutable HANDLE to a governance-minted, not-yet-bound identity."""

    identity: str

    kind: str

    state: str = STATE_RESERVED

    # A handle points at an id. It grants no authority and binds nothing.
    CREATES_IDENTITY = False

    BINDS_OBJECT = False

    GRANTS_AUTHORITY = False

    def __post_init__(self):

        if self.kind not in KINDS:

            raise ReservationError(
                "%s: unknown identity kind %r"
                % (REASON_UNKNOWN_KIND, self.kind)
            )

        if self.state not in STATES:

            raise ReservationError(
                "unknown reservation state: %r" % (self.state,)
            )

        if not str(self.identity or "").strip():

            raise ReservationError("a reservation requires an identity")

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "identity": self.identity,
            "kind": self.kind,
            "state": self.state,
            "creates_identity": False,
            "binds_object": False,
            "grants_authority": False,
        }

    def __repr__(self):

        return "ReservedIdentity(kind=%r, state=%r)" % (self.kind, self.state)


class ReservationLedger:

    """In-memory ledger of reserved identities. It tracks; it does not decide."""

    __slots__ = ("_entries",)

    CONTRACT = CONTRACT

    VERSION = VERSION

    def __init__(self):

        self._entries: Dict[str, str] = {}

    # --------------------------------------------------
    # reservation
    # --------------------------------------------------

    def reserve(self, kind) -> ReservedIdentity:

        """Mint a reserved id. identity_v1 is the ONLY generator."""

        generator = _GENERATORS.get(kind)

        if generator is None:

            raise ReservationError(
                "%s: %r" % (REASON_UNKNOWN_KIND, kind)
            )

        identity = generator()

        self._entries[identity] = STATE_RESERVED

        return ReservedIdentity(
            identity=identity,
            kind=kind,
            state=STATE_RESERVED,
        )

    # --------------------------------------------------
    # introspection
    # --------------------------------------------------

    def state_of(self, identity) -> Optional[str]:

        return self._entries.get(str(identity or ""))

    def is_reserved(self, identity) -> bool:

        return self.state_of(identity) == STATE_RESERVED

    def is_consumed(self, identity) -> bool:

        return self.state_of(identity) == STATE_CONSUMED

    def is_released(self, identity) -> bool:

        return self.state_of(identity) == STATE_RELEASED

    def count(self) -> int:

        return len(self._entries)

    # --------------------------------------------------
    # consumption — the ONLY way a reserved id becomes usable
    # --------------------------------------------------

    def consume(self, reservation, expected_kind) -> str:

        """Validate a handle against the ledger, mark it consumed, return the id."""

        if not isinstance(reservation, ReservedIdentity):

            raise ReservationError(
                "%s: not a ReservedIdentity handle" % (REASON_UNKNOWN,)
            )

        if reservation.kind != expected_kind:

            raise ReservationError(
                "%s: handle kind %r, expected %r"
                % (REASON_KIND_MISMATCH, reservation.kind, expected_kind)
            )

        state = self._entries.get(reservation.identity)

        if state is None:

            # A forged handle carries an id that was never reserved.
            raise ReservationError(
                "%s: identity was never reserved" % (REASON_UNKNOWN,)
            )

        if state == STATE_CONSUMED:

            raise ReservationError(
                "%s: identity was already consumed" % (REASON_CONSUMED,)
            )

        if state == STATE_RELEASED:

            raise ReservationError(
                "%s: identity was released" % (REASON_RELEASED,)
            )

        self._entries[reservation.identity] = STATE_CONSUMED

        return reservation.identity

    # --------------------------------------------------
    # release
    # --------------------------------------------------

    def release(self, reservation) -> ReservedIdentity:

        if not isinstance(reservation, ReservedIdentity):

            raise ReservationError(
                "%s: not a ReservedIdentity handle" % (REASON_UNKNOWN,)
            )

        state = self._entries.get(reservation.identity)

        if state is None:

            raise ReservationError(
                "%s: identity was never reserved" % (REASON_UNKNOWN,)
            )

        if state == STATE_CONSUMED:

            raise ReservationError(
                "%s: identity was already consumed" % (REASON_CONSUMED,)
            )

        if state == STATE_RELEASED:

            raise ReservationError(
                "%s: identity was already released" % (REASON_RELEASED,)
            )

        self._entries[reservation.identity] = STATE_RELEASED

        return ReservedIdentity(
            identity=reservation.identity,
            kind=reservation.kind,
            state=STATE_RELEASED,
        )

    def __repr__(self):

        return "ReservationLedger(entries=%d)" % (len(self._entries),)


# The governance-owned ledger. All mint factories consume from this instance.
reservation_ledger = ReservationLedger()


def reserve_claim_id() -> ReservedIdentity:

    return reservation_ledger.reserve(KIND_CLAIM)


def reserve_licence_id() -> ReservedIdentity:

    return reservation_ledger.reserve(KIND_LICENCE)


def reserve_derivation_event_id() -> ReservedIdentity:

    return reservation_ledger.reserve(KIND_DERIVATION_EVENT)


def reserve_endorsement_event_id() -> ReservedIdentity:

    return reservation_ledger.reserve(KIND_ENDORSEMENT_EVENT)


def consume_reservation(reservation, expected_kind) -> str:

    """Consume from the shared ledger. Used by the governance mint factories."""

    return reservation_ledger.consume(reservation, expected_kind)
