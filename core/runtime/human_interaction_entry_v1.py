"""Human interaction entry (V1) — the runtime entry that connects the
conversation interpretation to the interactive gateway.

It
    runs the conversation interpretation adapter (`core.interpretation`)
    builds the clean carrier
    builds the `ClaimRequestMaterial` from the carrier
    hands the REQUEST (the act proof) and the MATERIAL (the semantics) to the
    existing `InteractiveRuntimeGateway`

It MUST NOT
    interpret — the interpretation layer owns meaning
    select or default a claim type
    carry confidence / truth / status / approval
    import governance
    touch the token (the gateway contains it) or the nonce lifecycle

Dependency direction

    entry  ->  core.interpretation.conversation_interpretation_adapter_v1
    entry  ->  core.runtime.{claim_request_material_adapter_v1,
                              interactive_runtime_gateway_v1}
    entry  ->  core.conversation / core.vision / core.governance   FORBIDDEN

The gateway remains orchestration-only: it CONSUMES the material the entry
supplies and never re-derives it. The token stays inside the gateway.
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional


from core.interpretation.conversation_interpretation_adapter_v1 import (
    to_interaction_carrier,
)
from core.runtime.claim_request_material_adapter_v1 import (
    to_claim_request_material,
)
from core.runtime.interactive_runtime_gateway_v1 import (
    GatewayResult,
    InteractiveRuntimeGateway,
    STAGE_G1,
    STATUS_REFUSED,
    build_gateway_request,
)


CONTRACT = "RuntimeHumanInteractionEntryV1"

VERSION = "1.0"


REASON_NOT_AN_INTERACTION = "entry_not_an_interaction"

REASON_MISSING_FIELD = "entry_missing_field"


REASONS = (
    REASON_NOT_AN_INTERACTION,
    REASON_MISSING_FIELD,
)


class HumanInteractionError(ValueError):
    """Raised when an interaction is malformed before any flow starts."""


def _text(value) -> str:

    return str(value or "").strip()


@dataclass(frozen=True)
class HumanInteraction:

    """An immutable transport interaction. Exactly five fields, no score."""

    session_reference: str

    statement: str

    turn_kind: str

    language: str

    interaction_nonce: Any

    def __post_init__(self):

        if not _text(self.session_reference):

            raise HumanInteractionError(
                "%s: session_reference" % (REASON_MISSING_FIELD,)
            )

        if not isinstance(self.statement, str) or not self.statement.strip():

            raise HumanInteractionError(
                "%s: statement" % (REASON_MISSING_FIELD,)
            )

        if not _text(self.turn_kind):

            raise HumanInteractionError(
                "%s: turn_kind" % (REASON_MISSING_FIELD,)
            )

        if not _text(self.language):

            raise HumanInteractionError(
                "%s: language" % (REASON_MISSING_FIELD,)
            )

        if self.interaction_nonce is None:

            raise HumanInteractionError(
                "%s: interaction_nonce" % (REASON_MISSING_FIELD,)
            )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "session_reference": self.session_reference,
            "statement": self.statement,
            "turn_kind": self.turn_kind,
            "language": self.language,
            "interaction_nonce": getattr(
                self.interaction_nonce, "nonce_reference", self.interaction_nonce
            ),
        }

    def __repr__(self):

        return "HumanInteraction(session=%r, turn_kind=%r)" % (
            self.session_reference,
            self.turn_kind,
        )


class HumanInteractionEntry:

    """The runtime entry. It interprets, then delegates to the gateway."""

    __slots__ = ("_gateway",)

    CONTRACT = CONTRACT

    VERSION = VERSION

    CREATES_IDENTITY = False

    DECIDES_TRUTH = False

    PERSISTS = False

    def __init__(self, gateway=None):

        self._gateway = (
            gateway if gateway is not None else InteractiveRuntimeGateway()
        )

    @property
    def gateway(self) -> InteractiveRuntimeGateway:

        return self._gateway

    # --------------------------------------------------
    # the nonce request flow (unchanged — delegated)
    # --------------------------------------------------

    def request_nonce(self, session_reference):

        return self._gateway.request_nonce(session_reference)

    # --------------------------------------------------
    # the interaction flow
    # --------------------------------------------------

    def submit(self, interaction) -> GatewayResult:

        """Interpret the statement, build the material, then run the gateway."""

        if isinstance(interaction, Mapping):

            try:

                interaction = HumanInteraction(**dict(interaction))

            except (HumanInteractionError, TypeError) as error:

                return self._refused(str(error))

        if not isinstance(interaction, HumanInteraction):

            return self._refused(
                "%s: got %r"
                % (REASON_NOT_AN_INTERACTION, type(interaction).__name__)
            )

        # ---- interpretation (the layer owns meaning; the runtime does not) ----
        carrier = to_interaction_carrier(interaction.statement)

        # ---- the material (the single producer builds it) ----
        material = to_claim_request_material(carrier)

        # ---- the act-proof request (the five-field contract is preserved) ----
        request = build_gateway_request(
            session_reference=interaction.session_reference,
            raw_statement=carrier.statement,
            turn_kind=interaction.turn_kind,
            language=interaction.language,
            interaction_nonce=interaction.interaction_nonce,
        )

        # ---- the gateway CONSUMES the material; it never re-derives it ----
        return self._gateway.submit(request, material=material)

    @staticmethod
    def _refused(reason) -> GatewayResult:

        return GatewayResult(
            completed=False,
            stage=STAGE_G1,
            status=STATUS_REFUSED,
            reason=str(reason),
        )

    def __repr__(self):

        return "HumanInteractionEntry(interprets_then_delegates=True)"


human_interaction_entry = HumanInteractionEntry()
