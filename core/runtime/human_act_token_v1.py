"""HumanActToken (V1) — a runtime-owned, one-shot explicit-human-act boundary.

A token is the runtime's PROOF that a user turn was observed. It is not a
governance identity, not a claim/licence/event/candidate reference, and it
carries no authority.

It is
    immutable (a frozen value object)
    runtime-owned (issued and tracked by a runtime ledger)
    one-shot (issued -> consumed | released, both terminal)

It is NOT
    a governance identity (`clm_` / `lic_` / `dev_` / `eev_` / `kcd_`)
    a claim / licence / event / candidate reference
    a carrier of confidence, truth, approval or status

Dependency direction

    this module  ->  stdlib only
    this module  ->  core.governance / conversation / vision / knowledge  FORBIDDEN

The token reference is generated with the STANDARD LIBRARY (`uuid`). Governance's
id authority (`identity_v1`) is never called.
"""

from __future__ import annotations


import uuid


from dataclasses import dataclass
from typing import Any, Dict, Optional


CONTRACT = "RuntimeHumanActTokenV1"

VERSION = "1.0"


# ----------------------------------------------------------
# the runtime-local reference
# ----------------------------------------------------------

# A runtime-LOCAL prefix. It is deliberately NOT a governance prefix.
REFERENCE_PREFIX = "hat_"


# Governance identity prefixes. A token reference (or a session reference) may
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

STATE_RELEASED = "released"


STATES = (
    STATE_ISSUED,
    STATE_CONSUMED,
    STATE_RELEASED,
)


# Only a teaching / correction act may be represented.
ALLOWED_TURN_KINDS = ("TEACHING_STATEMENT", "CORRECTION")


# ----------------------------------------------------------
# rejection codes
# ----------------------------------------------------------

REASON_UNKNOWN = "token_unknown"

REASON_CONSUMED = "token_consumed"

REASON_RELEASED = "token_released"

REASON_NOT_A_TOKEN = "token_not_a_token"

REASON_FORBIDDEN_REFERENCE = "token_forbidden_reference"

REASON_UNKNOWN_TURN_KIND = "token_unknown_turn_kind"

REASON_MISSING_FIELD = "token_missing_field"

REASON_UNKNOWN_STATE = "token_unknown_state"


REASONS = (
    REASON_UNKNOWN,
    REASON_CONSUMED,
    REASON_RELEASED,
    REASON_NOT_A_TOKEN,
    REASON_FORBIDDEN_REFERENCE,
    REASON_UNKNOWN_TURN_KIND,
    REASON_MISSING_FIELD,
    REASON_UNKNOWN_STATE,
)


class HumanActTokenError(ValueError):
    """Raised when a token cannot be issued, consumed or released."""


def _text(value) -> str:

    return str(value or "").strip()


def new_token_reference() -> str:

    """A runtime-LOCAL reference. Never a governance identity."""

    return REFERENCE_PREFIX + uuid.uuid4().hex[:16]


def _reject_governance_reference(value) -> None:

    text = _text(value)

    for prefix in FORBIDDEN_REFERENCE_PREFIXES:

        if text.startswith(prefix):

            raise HumanActTokenError(
                "%s: %r" % (REASON_FORBIDDEN_REFERENCE, text)
            )


@dataclass(frozen=True)
class HumanActToken:

    """An immutable, runtime-owned proof of an observed human act."""

    token_reference: str

    turn_kind: str

    language: str = "unknown"

    session_reference: Optional[str] = None

    state: str = STATE_ISSUED

    # A token proves an act. It creates nothing and grants nothing.
    CREATES_IDENTITY = False

    GRANTS_AUTHORITY = False

    CARRIES_CONFIDENCE = False

    DECIDES_TRUTH = False

    def __post_init__(self):

        if not _text(self.token_reference):

            raise HumanActTokenError(
                "%s: token_reference is required" % (REASON_MISSING_FIELD,)
            )

        _reject_governance_reference(self.token_reference)

        if self.turn_kind not in ALLOWED_TURN_KINDS:

            raise HumanActTokenError(
                "%s: %r" % (REASON_UNKNOWN_TURN_KIND, self.turn_kind)
            )

        if self.state not in STATES:

            raise HumanActTokenError(
                "%s: %r" % (REASON_UNKNOWN_STATE, self.state)
            )

        if self.session_reference is not None:

            _reject_governance_reference(self.session_reference)

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "token_reference": self.token_reference,
            "turn_kind": self.turn_kind,
            "language": self.language,
            "session_reference": self.session_reference,
            "state": self.state,
            "creates_identity": False,
            "grants_authority": False,
            "carries_confidence": False,
            "decides_truth": False,
        }

    def __repr__(self):

        return "HumanActToken(reference=%r, state=%r)" % (
            self.token_reference,
            self.state,
        )


class HumanActTokenLedger:

    """In-memory, runtime-owned ledger of issued human-act tokens."""

    __slots__ = ("_entries",)

    CONTRACT = CONTRACT

    VERSION = VERSION

    def __init__(self):

        self._entries: Dict[str, str] = {}

    # --------------------------------------------------
    # issue
    # --------------------------------------------------

    def issue(
        self,
        *,
        turn_kind,
        language: str = "unknown",
        session_reference: Optional[str] = None,
    ) -> HumanActToken:

        """Issue a one-shot token for an OBSERVED human act."""

        token = HumanActToken(
            token_reference=new_token_reference(),
            turn_kind=turn_kind,
            language=language,
            session_reference=session_reference,
            state=STATE_ISSUED,
        )

        self._entries[token.token_reference] = STATE_ISSUED

        return token

    # --------------------------------------------------
    # lookup
    # --------------------------------------------------

    def state_of(self, token_reference) -> Optional[str]:

        return self._entries.get(_text(token_reference))

    def is_issued(self, token_reference) -> bool:

        return self.state_of(token_reference) == STATE_ISSUED

    def is_consumed(self, token_reference) -> bool:

        return self.state_of(token_reference) == STATE_CONSUMED

    def is_released(self, token_reference) -> bool:

        return self.state_of(token_reference) == STATE_RELEASED

    def count(self) -> int:

        return len(self._entries)

    # --------------------------------------------------
    # consumption / release
    # --------------------------------------------------

    def _validated_state(self, token) -> str:

        if not isinstance(token, HumanActToken):

            raise HumanActTokenError(
                "%s: not a HumanActToken" % (REASON_NOT_A_TOKEN,)
            )

        state = self._entries.get(token.token_reference)

        if state is None:

            # a forged token carries a reference the ledger never issued
            raise HumanActTokenError(
                "%s: never issued" % (REASON_UNKNOWN,)
            )

        return state

    def consume(self, token) -> HumanActToken:

        """Consume a token EXACTLY once. Returns the consumed token."""

        state = self._validated_state(token)

        if state == STATE_CONSUMED:

            raise HumanActTokenError(
                "%s: already consumed" % (REASON_CONSUMED,)
            )

        if state == STATE_RELEASED:

            raise HumanActTokenError(
                "%s: was released" % (REASON_RELEASED,)
            )

        self._entries[token.token_reference] = STATE_CONSUMED

        return HumanActToken(
            token_reference=token.token_reference,
            turn_kind=token.turn_kind,
            language=token.language,
            session_reference=token.session_reference,
            state=STATE_CONSUMED,
        )

    def release(self, token) -> HumanActToken:

        """Release a token EXACTLY once. Returns the released token."""

        state = self._validated_state(token)

        if state == STATE_CONSUMED:

            raise HumanActTokenError(
                "%s: already consumed" % (REASON_CONSUMED,)
            )

        if state == STATE_RELEASED:

            raise HumanActTokenError(
                "%s: already released" % (REASON_RELEASED,)
            )

        self._entries[token.token_reference] = STATE_RELEASED

        return HumanActToken(
            token_reference=token.token_reference,
            turn_kind=token.turn_kind,
            language=token.language,
            session_reference=token.session_reference,
            state=STATE_RELEASED,
        )

    def __repr__(self):

        return "HumanActTokenLedger(entries=%d)" % (len(self._entries),)


# The runtime-owned ledger.
human_act_token_ledger = HumanActTokenLedger()


def issue_human_act_token(
    *,
    turn_kind,
    language: str = "unknown",
    session_reference: Optional[str] = None,
) -> HumanActToken:

    return human_act_token_ledger.issue(
        turn_kind=turn_kind,
        language=language,
        session_reference=session_reference,
    )


def consume_human_act_token(token) -> HumanActToken:

    return human_act_token_ledger.consume(token)


def release_human_act_token(token) -> HumanActToken:

    return human_act_token_ledger.release(token)


def human_act_token_state(token_reference) -> Optional[str]:

    return human_act_token_ledger.state_of(token_reference)
