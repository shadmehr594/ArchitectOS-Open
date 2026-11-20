"""InteractiveRuntimeGateway (V1) — the runtime-owned interactive entry.

The gateway is a PURE ORCHESTRATOR. It orders the flow; governance decides.

It owns
    the nonce request flow
    the materialisation DELEGATION (it INVOKES the single producer, or CONSUMES a
        material the runtime entry supplies; it never assembles)
    the HumanActIssuerEvent construction
    the HumanActIssuer invocation
    the token lifetime INSIDE the gateway
    the ConversationAdapter invocation
    the LifecycleExecutor invocation

It MUST NOT
    construct a ClaimRequestMaterial / a statement mapping / claim_type_hint /
        basis / limitations   (the ClaimRequestMaterialAdapter is the ONLY producer)
    create a Claim / LicenceRecord / proposal object / event / candidate
    create a governance identity
    decide truth / confidence / admission / claim type
    persist anything
    retry or compensate
    let the token leave the gateway

Dependency direction

    gateway  ->  core.runtime.{interaction_nonce_v1, human_act_issuer_v1,
                                claim_request_material_adapter_v1,
                                conversation_adapter_v1, lifecycle_executor_v1}
    gateway  ->  core.governance / conversation / vision / knowledge   FORBIDDEN
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional


from core.runtime.claim_request_material_adapter_v1 import (
    ClaimRequestMaterialError,
    to_claim_request_material,
)
from core.runtime.conversation_adapter_v1 import (
    ConversationAdapterError,
    to_claim_request_input,
)
from core.runtime.human_act_issuer_v1 import (
    HumanActIssuer,
    HumanActIssuerError,
    HumanActIssuerEvent,
)
from core.runtime.interaction_nonce_v1 import (
    InteractionNonce,
    issue_interaction_nonce,
)
from core.runtime.lifecycle_executor_v1 import LifecycleExecutor


CONTRACT = "RuntimeInteractiveGatewayV1"

VERSION = "1.0"


# ----------------------------------------------------------
# stages
# ----------------------------------------------------------

STAGE_G1 = "G1_validate_request"

STAGE_G1M = "G1M_materialise"

STAGE_G2 = "G2_issuer_event"

STAGE_G3 = "G3_token"

STAGE_G4 = "G4_claim_request"

STAGE_G5 = "G5_lifecycle"

STAGE_G6 = "G6_return"


STAGES = (
    STAGE_G1,
    STAGE_G1M,
    STAGE_G2,
    STAGE_G3,
    STAGE_G4,
    STAGE_G5,
    STAGE_G6,
)


# ----------------------------------------------------------
# outcomes
# ----------------------------------------------------------

STATUS_ADMITTED = "admitted"

STATUS_DENIED = "denied"

STATUS_REFUSED = "refused"

STATUS_ERROR = "error"


STATUSES = (
    STATUS_ADMITTED,
    STATUS_DENIED,
    STATUS_REFUSED,
    STATUS_ERROR,
)


# ----------------------------------------------------------
# the request contract
# ----------------------------------------------------------

ALLOWED_REQUEST_FIELDS = (
    "session_reference",
    "raw_statement",
    "turn_kind",
    "language",
    "interaction_nonce",
)


FORBIDDEN_REQUEST_FIELDS = (
    # confidence
    "confidence",
    "confidence_kind",
    "confidence_as_truth",
    # truth / approval
    "truth",
    "truth_status",
    "is_true",
    "verified_truth",
    "approval",
    "approved",
    "is_approved",
    "certainty",
    "probability",
    "fact_status",
    "is_fact",
    # governance identities
    "claim_id",
    "claim_reference",
    "licence_id",
    "license_id",
    "licence_reference",
    "candidate_reference",
    "event_id",
    "derivation_event_reference",
    "endorsement_event_reference",
    # proposal / receipt objects
    "proposal",
    "proposal_fields",
    "interpretation_proposal",
    "proposal_receipt",
    # vision
    "auv2",
    "projection",
    # authority / status
    "scope",
    "licence",
    "license",
    "knowledge_status",
    "status",
)


# Fixed provenance for the interactive entry. These are CONSTANTS, not
# per-request decisions: the gateway never chooses a value per interaction.
INTERACTIVE_SOURCE_TYPE = "human_endorsement"

INTERACTIVE_ORIGIN = "interactive_gateway"

# NOTE: there is deliberately NO claim-type constant here. The claim type is
# carried ONLY by the ClaimRequestMaterial (its `claim_type_hint`); the gateway
# forwards it VERBATIM and NEVER substitutes a fallback. An absent hint stays
# absent (None) — the fallback must not be restored.


# The derivation provenance of an interactive claim. A claim must be derived from
# something; for the interactive path the derivation input is the interaction
# itself, referenced by its runtime-local nonce reference. This is a CONSTANT
# FORMAT, not a per-request decision.
INTERACTIVE_TRIGGER_PREFIX = "interaction:"


class InteractiveGatewayError(ValueError):
    """Raised when a gateway request or result is malformed."""


def _text(value) -> str:

    return str(value or "").strip()


def _reject_governance_reference(value, label) -> None:

    text = _text(value)

    for prefix in ("clm_", "lic_", "dev_", "eev_", "kcd_"):

        if text.startswith(prefix):

            raise InteractiveGatewayError(
                "%s may not carry a governance identity: %r" % (label, text)
            )


def _is_a_material(value) -> bool:

    """A duck-typed check: a claim request material carries the semantic fields.

    The gateway never imports the material CLASS (it consumes a value), so a
    caller-supplied material is accepted structurally and never re-derived.
    """

    return all(
        hasattr(value, name)
        for name in ("statement", "claim_type_hint", "basis", "limitations")
    )


@dataclass(frozen=True)
class InteractiveGatewayRequest:

    """An immutable transport request. Exactly five fields."""

    session_reference: str

    raw_statement: str

    turn_kind: str

    language: str

    interaction_nonce: Any

    def __post_init__(self):

        if not _text(self.session_reference):

            raise InteractiveGatewayError("session_reference is required")

        if not isinstance(self.raw_statement, str) or not self.raw_statement.strip():

            raise InteractiveGatewayError(
                "raw_statement must be a non-empty string"
            )

        if not _text(self.turn_kind):

            raise InteractiveGatewayError("turn_kind is required")

        if not _text(self.language):

            raise InteractiveGatewayError("language is required")

        if self.interaction_nonce is None:

            raise InteractiveGatewayError("interaction_nonce is required")

        _reject_governance_reference(self.session_reference, "session_reference")

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "session_reference": self.session_reference,
            "raw_statement": self.raw_statement,
            "turn_kind": self.turn_kind,
            "language": self.language,
            "interaction_nonce": getattr(
                self.interaction_nonce, "nonce_reference", self.interaction_nonce
            ),
        }

    def __repr__(self):

        return "InteractiveGatewayRequest(session=%r, turn_kind=%r)" % (
            self.session_reference,
            self.turn_kind,
        )


def build_gateway_request(**fields) -> InteractiveGatewayRequest:

    """Build a request, refusing a forbidden field or an unknown field."""

    for key in fields:

        if key in FORBIDDEN_REQUEST_FIELDS:

            raise InteractiveGatewayError(
                "a gateway request may not carry %r" % (key,)
            )

        if key not in ALLOWED_REQUEST_FIELDS:

            raise InteractiveGatewayError(
                "unknown gateway request field: %r" % (key,)
            )

    return InteractiveGatewayRequest(**fields)


@dataclass(frozen=True)
class GatewayResult:

    """The immutable outcome of one interactive flow. It NEVER carries a token."""

    completed: bool

    stage: str

    status: str

    reason: str

    lifecycle_result: Optional[Any] = None

    error_type: Optional[str] = None

    # The gateway orchestrates. It creates nothing and decides nothing.
    CREATES_IDENTITY = False

    DECIDES_TRUTH = False

    PERSISTS = False

    def __post_init__(self):

        if self.stage not in STAGES:

            raise InteractiveGatewayError("unknown stage: %r" % (self.stage,))

        if self.status not in STATUSES:

            raise InteractiveGatewayError("unknown status: %r" % (self.status,))

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "completed": self.completed,
            "stage": self.stage,
            "status": self.status,
            "reason": self.reason,
            "lifecycle_result": (
                self.lifecycle_result.to_dict()
                if self.lifecycle_result is not None
                else None
            ),
            "error_type": self.error_type,
            "creates_identity": False,
            "decides_truth": False,
            "persists": False,
        }

    def __repr__(self):

        return "GatewayResult(completed=%r, stage=%r, status=%r)" % (
            self.completed,
            self.stage,
            self.status,
        )


class InteractiveRuntimeGateway:

    """The single runtime entry. It orders the flow; governance decides."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    CREATES_IDENTITY = False

    DECIDES_TRUTH = False

    PERSISTS = False

    # --------------------------------------------------
    # the nonce request flow
    # --------------------------------------------------

    def request_nonce(self, session_reference) -> InteractionNonce:

        """Hand out a single-use, session-bound nonce for one interaction."""

        return issue_interaction_nonce(session_reference)

    # --------------------------------------------------
    # the interactive flow
    # --------------------------------------------------

    def submit(self, request, *, material=None) -> GatewayResult:

        """Run G1, G1M, G2..G6. Every outcome is a GatewayResult; nothing is raised.

        `material` is an OPTIONAL, pre-built ClaimRequestMaterial supplied by the
        runtime entry. When given, the gateway CONSUMES it and does NOT
        materialise from the request — the entry owns the interpretation. When
        omitted, the gateway materialises from the request exactly as before, so
        the existing `submit(request)` contract is UNCHANGED.
        """

        # ---- G1 validate the transport request ----
        validated = self._validate_request(request)

        if isinstance(validated, GatewayResult):

            return validated

        # ---- G1M materialise ----
        # The gateway INVOKES the single producer and CONSUMES the returned
        # material; a caller-supplied material is consumed AS-IS (never
        # re-derived, never re-assembled). It never constructs the material, a
        # statement mapping, a claim_type_hint, a basis or a limitation. A
        # material failure is a PRE-ACT failure: the nonce is untouched and no
        # token has been issued.
        if material is None:

            try:

                material = to_claim_request_material(validated)

            except ClaimRequestMaterialError as error:

                return self._refused(STAGE_G1M, str(error))

            except Exception as error:  # pragma: no cover - defensive

                return self._error(STAGE_G1M, error)

        elif not _is_a_material(material):

            return self._refused(
                STAGE_G1M,
                "the supplied material is not a claim request material",
            )

        # ---- G2 create the HumanActIssuerEvent ----
        try:

            event = HumanActIssuerEvent(
                turn_kind=validated.turn_kind,
                language=validated.language,
                session_reference=validated.session_reference,
                interaction_nonce=validated.interaction_nonce,
            )

        except Exception as error:  # pragma: no cover - defensive

            return self._error(STAGE_G2, error)

        # ---- G3 issue the HumanActToken ----
        try:

            token = HumanActIssuer().issue(event)

        except HumanActIssuerError as error:

            return self._refused(STAGE_G3, str(error))

        except Exception as error:  # pragma: no cover - defensive

            return self._error(STAGE_G3, error)

        # ---- G4 the claim request (the material + the token are consumed here) ----
        try:

            claim_request = to_claim_request_input(
                material.statement,
                intent=token,
                language=validated.language,
                proposed_claim_type=material.claim_type_hint,
                basis=material.basis,
                limitations=material.limitations,
                trigger_references=(
                    INTERACTIVE_TRIGGER_PREFIX
                    + str(
                        getattr(
                            validated.interaction_nonce,
                            "nonce_reference",
                            validated.interaction_nonce,
                        )
                    ),
                ),
            )

        except ConversationAdapterError as error:

            return self._refused(STAGE_G4, str(error))

        except Exception as error:  # pragma: no cover - defensive

            return self._error(STAGE_G4, error)

        # ---- G5 the lifecycle ----
        try:

            lifecycle_result = LifecycleExecutor().run(
                proposal_fields=dict(claim_request.proposal_fields),
                source_type=INTERACTIVE_SOURCE_TYPE,
                origin=INTERACTIVE_ORIGIN,
            )

        except Exception as error:  # pragma: no cover - defensive

            return self._error(STAGE_G5, error)

        # ---- G6 return ----
        return self._from_lifecycle(lifecycle_result)

    # ==================================================
    # internals
    # ==================================================

    @staticmethod
    def _validate_request(request):

        if isinstance(request, Mapping):

            for key in request:

                if key in FORBIDDEN_REQUEST_FIELDS:

                    return GatewayResult(
                        completed=False,
                        stage=STAGE_G1,
                        status=STATUS_REFUSED,
                        reason="a gateway request may not carry %r" % (key,),
                    )

                if key not in ALLOWED_REQUEST_FIELDS:

                    return GatewayResult(
                        completed=False,
                        stage=STAGE_G1,
                        status=STATUS_REFUSED,
                        reason="unknown gateway request field: %r" % (key,),
                    )

            try:

                request = InteractiveGatewayRequest(**dict(request))

            except (InteractiveGatewayError, TypeError) as error:

                return GatewayResult(
                    completed=False,
                    stage=STAGE_G1,
                    status=STATUS_REFUSED,
                    reason=str(error),
                )

        if not isinstance(request, InteractiveGatewayRequest):

            return GatewayResult(
                completed=False,
                stage=STAGE_G1,
                status=STATUS_REFUSED,
                reason="a gateway request must be an InteractiveGatewayRequest "
                "or a mapping; got %r" % (type(request).__name__,),
            )

        return request

    @staticmethod
    def _refused(stage, reason) -> GatewayResult:

        return GatewayResult(
            completed=False,
            stage=stage,
            status=STATUS_REFUSED,
            reason=str(reason),
        )

    @staticmethod
    def _error(stage, error) -> GatewayResult:

        return GatewayResult(
            completed=False,
            stage=stage,
            status=STATUS_ERROR,
            reason=str(error),
            error_type=type(error).__name__,
        )

    @staticmethod
    def _from_lifecycle(result) -> GatewayResult:

        if result.completed:

            status = STATUS_ADMITTED

        elif result.status == "error":

            status = STATUS_ERROR

        else:

            status = STATUS_DENIED

        return GatewayResult(
            completed=result.completed,
            stage=STAGE_G5,
            status=status,
            reason=result.reason,
            lifecycle_result=result,
            error_type=result.error_type,
        )

    def __repr__(self):

        return "InteractiveRuntimeGateway(orders_only=True, creates_identity=False)"


interactive_runtime_gateway = InteractiveRuntimeGateway()
