"""HumanActIssuer (V1) — the ONLY component that issues a HumanActToken.

The issuer is runtime-owned. It accepts an interaction event that carries a
runtime-issued, single-use, session-bound nonce, validates it, consumes the nonce
and only then issues a token through the existing runtime token mechanism.

It
    validates an event
    consumes the nonce (after ALL validation passes)
    issues the token via `core.runtime.human_act_token_v1`

It MUST NOT
    import governance
    create a Claim / LicenceRecord / event / candidate
    carry confidence, truth, approval or status
    persist anything
    trigger automatically, or issue in a background context

Dependency direction

    this module  ->  core.runtime.interaction_nonce_v1   ALLOWED (runtime-local)
    this module  ->  core.runtime.human_act_token_v1     ALLOWED (runtime-local)
    this module  ->  core.governance / conversation / vision / knowledge  FORBIDDEN
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Optional


from core.runtime.human_act_token_v1 import (
    ALLOWED_TURN_KINDS,
    HumanActToken,
    issue_human_act_token,
)
from core.runtime.interaction_nonce_v1 import (
    STATE_CONSUMED,
    STATE_EXPIRED,
    STATE_ISSUED,
    consume_interaction_nonce,
    interaction_nonce_ledger,
    interaction_nonce_state,
)


CONTRACT = "RuntimeHumanActIssuerV1"

VERSION = "1.0"


# ----------------------------------------------------------
# rejection codes
# ----------------------------------------------------------

REASON_NOT_AN_EVENT = "issuer_not_an_event"

REASON_MISSING_SESSION = "issuer_missing_session"

REASON_UNKNOWN_TURN_KIND = "issuer_unknown_turn_kind"

REASON_MISSING_NONCE = "issuer_missing_nonce"

REASON_UNKNOWN_NONCE = "issuer_unknown_nonce"

REASON_SESSION_MISMATCH = "issuer_nonce_session_mismatch"

REASON_NONCE_CONSUMED = "issuer_nonce_consumed"

REASON_NONCE_EXPIRED = "issuer_nonce_expired"


REASONS = (
    REASON_NOT_AN_EVENT,
    REASON_MISSING_SESSION,
    REASON_UNKNOWN_TURN_KIND,
    REASON_MISSING_NONCE,
    REASON_UNKNOWN_NONCE,
    REASON_SESSION_MISMATCH,
    REASON_NONCE_CONSUMED,
    REASON_NONCE_EXPIRED,
)


class HumanActIssuerError(ValueError):
    """Raised when an interaction event cannot be turned into a token."""


def _text(value) -> str:

    return str(value or "").strip()


@dataclass(frozen=True)
class HumanActIssuerEvent:

    """An immutable, runtime-owned carrier of an observed interaction.

    It is a pure value object: it performs NO validation of its own. The issuer
    validates the event (see `HumanActIssuer.issue`).
    """

    turn_kind: str

    language: str

    session_reference: str

    interaction_nonce: Any

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "turn_kind": self.turn_kind,
            "language": self.language,
            "session_reference": self.session_reference,
            "interaction_nonce": getattr(
                self.interaction_nonce, "nonce_reference", self.interaction_nonce
            ),
        }

    def __repr__(self):

        return "HumanActIssuerEvent(turn_kind=%r, session=%r)" % (
            self.turn_kind,
            self.session_reference,
        )


class HumanActIssuer:

    """The single runtime component allowed to issue a HumanActToken."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    # The issuer issues a runtime-local proof. It creates no identity.
    CREATES_IDENTITY = False

    GRANTS_AUTHORITY = False

    CARRIES_CONFIDENCE = False

    DECIDES_TRUTH = False

    def issue(self, event) -> HumanActToken:

        """Validate an event, consume its nonce, then issue a token.

        Nothing is consumed until EVERY validation has passed.
        """

        # ---- 1. the event must be an event ----
        if not isinstance(event, HumanActIssuerEvent):

            raise HumanActIssuerError(
                "%s: got %r" % (REASON_NOT_AN_EVENT, type(event).__name__)
            )

        # ---- 2. the session must be present ----
        session = _text(event.session_reference)

        if not session:

            raise HumanActIssuerError(
                "%s: session_reference is required" % (REASON_MISSING_SESSION,)
            )

        # ---- 3. only a teaching / correction act may be represented ----
        if event.turn_kind not in ALLOWED_TURN_KINDS:

            raise HumanActIssuerError(
                "%s: %r" % (REASON_UNKNOWN_TURN_KIND, event.turn_kind)
            )

        # ---- 4. the nonce must be present ----
        nonce = event.interaction_nonce

        if nonce is None:

            raise HumanActIssuerError(
                "%s: an interaction nonce is required" % (REASON_MISSING_NONCE,)
            )

        # ---- 5. the nonce must be a runtime-issued nonce ----
        reference = getattr(nonce, "nonce_reference", None)

        state = interaction_nonce_state(reference)

        if state is None:

            raise HumanActIssuerError(
                "%s: %r" % (REASON_UNKNOWN_NONCE, reference)
            )

        # ---- 6. the nonce must belong to the SAME session ----
        bound_session = interaction_nonce_ledger.session_of(reference)

        if bound_session != session:

            raise HumanActIssuerError(
                "%s: nonce is bound to another session" % (REASON_SESSION_MISMATCH,)
            )

        # ---- 7. the nonce must still be issued ----
        if state == STATE_CONSUMED:

            raise HumanActIssuerError(
                "%s: nonce was already consumed" % (REASON_NONCE_CONSUMED,)
            )

        if state == STATE_EXPIRED:

            raise HumanActIssuerError(
                "%s: nonce was expired" % (REASON_NONCE_EXPIRED,)
            )

        if state != STATE_ISSUED:

            raise HumanActIssuerError(
                "%s: %r" % (REASON_UNKNOWN_NONCE, reference)
            )

        # ---- 8. every check passed: consume the nonce ----
        consume_interaction_nonce(nonce, session)

        # ---- 9. only now is the token issued ----
        return issue_human_act_token(
            turn_kind=event.turn_kind,
            language=_text(event.language) or "unknown",
            session_reference=session,
        )

    def __repr__(self):

        return "HumanActIssuer(issues_tokens=True, creates_identity=False)"


human_act_issuer = HumanActIssuer()
