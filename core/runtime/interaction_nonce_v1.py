"""InteractionNonce (V1) — a runtime-owned, single-use interaction nonce.

A nonce is the runtime's FRESHNESS evidence for one interactive action. It is a
runtime-local value: not a governance identity, not a claim/licence/event/candidate
reference, and it carries no authority.

It is
    immutable (a frozen value object)
    runtime-owned (generated and tracked by a runtime ledger)
    single-use (issued -> consumed | expired, both terminal)
    session-bound (bound to exactly one session at generation)

It is NOT
    a governance identity (`clm_` / `lic_` / `dev_` / `eev_` / `kcd_`)
    a claim / licence / event / candidate reference
    a carrier of confidence, truth, approval or status

Dependency direction

    this module  ->  stdlib only
    this module  ->  core.governance / conversation / vision / knowledge  FORBIDDEN

The reference is generated with the STANDARD LIBRARY (`secrets`). Governance's id
authority (`identity_v1`) is never called.
"""

from __future__ import annotations


import secrets


from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


CONTRACT = "RuntimeInteractionNonceV1"

VERSION = "1.0"


# ----------------------------------------------------------
# the runtime-local reference
# ----------------------------------------------------------

# A runtime-LOCAL prefix. It is deliberately NOT a governance prefix.
REFERENCE_PREFIX = "inx_"


# Governance identity prefixes. A nonce reference (or a session reference) may
# never carry one. Declared locally because this module must not import
# governance.
FORBIDDEN_REFERENCE_PREFIXES = (
    "clm_",
    "lic_",
    "dev_",
    "eev_",
    "kcd_",
)


# ----------------------------------------------------------
# states
# ----------------------------------------------------------

STATE_ISSUED = "issued"

STATE_CONSUMED = "consumed"

STATE_EXPIRED = "expired"


STATES = (
    STATE_ISSUED,
    STATE_CONSUMED,
    STATE_EXPIRED,
)


# ----------------------------------------------------------
# rejection codes
# ----------------------------------------------------------

REASON_UNKNOWN = "nonce_unknown"

REASON_CONSUMED = "nonce_consumed"

REASON_EXPIRED = "nonce_expired"

REASON_NOT_A_NONCE = "nonce_not_a_nonce"

REASON_SESSION_MISMATCH = "nonce_session_mismatch"

REASON_FORBIDDEN_REFERENCE = "nonce_forbidden_reference"

REASON_MISSING_FIELD = "nonce_missing_field"

REASON_UNKNOWN_STATE = "nonce_unknown_state"


REASONS = (
    REASON_UNKNOWN,
    REASON_CONSUMED,
    REASON_EXPIRED,
    REASON_NOT_A_NONCE,
    REASON_SESSION_MISMATCH,
    REASON_FORBIDDEN_REFERENCE,
    REASON_MISSING_FIELD,
    REASON_UNKNOWN_STATE,
)


class InteractionNonceError(ValueError):
    """Raised when a nonce cannot be issued, consumed or expired."""


def _text(value) -> str:

    return str(value or "").strip()


def new_nonce_reference() -> str:

    """A runtime-LOCAL reference. Never a governance identity."""

    return REFERENCE_PREFIX + secrets.token_hex(16)


def _reject_governance_reference(value, label) -> None:

    text = _text(value)

    for prefix in FORBIDDEN_REFERENCE_PREFIXES:

        if text.startswith(prefix):

            raise InteractionNonceError(
                "%s: %s=%r" % (REASON_FORBIDDEN_REFERENCE, label, text)
            )


@dataclass(frozen=True)
class InteractionNonce:

    """An immutable, runtime-owned, single-use interaction nonce."""

    nonce_reference: str

    session_reference: str

    state: str = STATE_ISSUED

    # A nonce is freshness evidence. It creates nothing and grants nothing.
    CREATES_IDENTITY = False

    GRANTS_AUTHORITY = False

    CARRIES_CONFIDENCE = False

    DECIDES_TRUTH = False

    def __post_init__(self):

        if not _text(self.nonce_reference):

            raise InteractionNonceError(
                "%s: nonce_reference is required" % (REASON_MISSING_FIELD,)
            )

        if not _text(self.session_reference):

            raise InteractionNonceError(
                "%s: session_reference is required" % (REASON_MISSING_FIELD,)
            )

        _reject_governance_reference(self.nonce_reference, "nonce_reference")

        _reject_governance_reference(self.session_reference, "session_reference")

        if self.state not in STATES:

            raise InteractionNonceError(
                "%s: %r" % (REASON_UNKNOWN_STATE, self.state)
            )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "nonce_reference": self.nonce_reference,
            "session_reference": self.session_reference,
            "state": self.state,
            "creates_identity": False,
            "grants_authority": False,
            "carries_confidence": False,
            "decides_truth": False,
        }

    def __repr__(self):

        return "InteractionNonce(reference=%r, state=%r)" % (
            self.nonce_reference,
            self.state,
        )


class InteractionNonceLedger:

    """In-memory, runtime-owned ledger of issued interaction nonces."""

    __slots__ = ("_entries",)

    CONTRACT = CONTRACT

    VERSION = VERSION

    def __init__(self):

        # nonce_reference -> (state, session_reference)
        self._entries: Dict[str, Tuple[str, str]] = {}

    # --------------------------------------------------
    # issue
    # --------------------------------------------------

    def issue(self, session_reference) -> InteractionNonce:

        """Issue a single-use nonce bound to one session."""

        nonce = InteractionNonce(
            nonce_reference=new_nonce_reference(),
            session_reference=session_reference,
            state=STATE_ISSUED,
        )

        self._entries[nonce.nonce_reference] = (
            STATE_ISSUED,
            nonce.session_reference,
        )

        return nonce

    # --------------------------------------------------
    # lookup
    # --------------------------------------------------

    def _entry(self, nonce_reference) -> Optional[Tuple[str, str]]:

        return self._entries.get(_text(nonce_reference))

    def state_of(self, nonce_reference) -> Optional[str]:

        entry = self._entry(nonce_reference)

        return entry[0] if entry else None

    def session_of(self, nonce_reference) -> Optional[str]:

        entry = self._entry(nonce_reference)

        return entry[1] if entry else None

    def is_issued(self, nonce_reference) -> bool:

        return self.state_of(nonce_reference) == STATE_ISSUED

    def is_consumed(self, nonce_reference) -> bool:

        return self.state_of(nonce_reference) == STATE_CONSUMED

    def is_expired(self, nonce_reference) -> bool:

        return self.state_of(nonce_reference) == STATE_EXPIRED

    def count(self) -> int:

        return len(self._entries)

    # --------------------------------------------------
    # consumption / expiry
    # --------------------------------------------------

    def _validated_entry(self, nonce) -> Tuple[str, str]:

        if not isinstance(nonce, InteractionNonce):

            raise InteractionNonceError(
                "%s: not an InteractionNonce" % (REASON_NOT_A_NONCE,)
            )

        entry = self._entries.get(nonce.nonce_reference)

        if entry is None:

            # a forged nonce carries a reference the ledger never issued
            raise InteractionNonceError(
                "%s: never issued" % (REASON_UNKNOWN,)
            )

        return entry

    def consume(self, nonce, session_reference) -> InteractionNonce:

        """Consume a nonce EXACTLY once, for the session it was bound to."""

        state, bound_session = self._validated_entry(nonce)

        if state == STATE_CONSUMED:

            raise InteractionNonceError(
                "%s: already consumed" % (REASON_CONSUMED,)
            )

        if state == STATE_EXPIRED:

            raise InteractionNonceError(
                "%s: was expired" % (REASON_EXPIRED,)
            )

        if _text(session_reference) != bound_session:

            raise InteractionNonceError(
                "%s: nonce is bound to another session" % (REASON_SESSION_MISMATCH,)
            )

        self._entries[nonce.nonce_reference] = (STATE_CONSUMED, bound_session)

        return InteractionNonce(
            nonce_reference=nonce.nonce_reference,
            session_reference=bound_session,
            state=STATE_CONSUMED,
        )

    def expire(self, nonce) -> InteractionNonce:

        """Expire a nonce EXACTLY once."""

        state, bound_session = self._validated_entry(nonce)

        if state == STATE_CONSUMED:

            raise InteractionNonceError(
                "%s: already consumed" % (REASON_CONSUMED,)
            )

        if state == STATE_EXPIRED:

            raise InteractionNonceError(
                "%s: already expired" % (REASON_EXPIRED,)
            )

        self._entries[nonce.nonce_reference] = (STATE_EXPIRED, bound_session)

        return InteractionNonce(
            nonce_reference=nonce.nonce_reference,
            session_reference=bound_session,
            state=STATE_EXPIRED,
        )

    def __repr__(self):

        return "InteractionNonceLedger(entries=%d)" % (len(self._entries),)


# The runtime-owned ledger.
interaction_nonce_ledger = InteractionNonceLedger()


def issue_interaction_nonce(session_reference) -> InteractionNonce:

    return interaction_nonce_ledger.issue(session_reference)


def consume_interaction_nonce(nonce, session_reference) -> InteractionNonce:

    return interaction_nonce_ledger.consume(nonce, session_reference)


def expire_interaction_nonce(nonce) -> InteractionNonce:

    return interaction_nonce_ledger.expire(nonce)


def interaction_nonce_state(nonce) -> Optional[str]:

    reference = (
        nonce.nonce_reference if isinstance(nonce, InteractionNonce) else nonce
    )

    return interaction_nonce_ledger.state_of(reference)
