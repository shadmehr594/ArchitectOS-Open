"""EndorsementService (V1) — the only place an EndorsementEvent is created.

Responsibilities of `prepare_endorsement_event()`
    1. receive a classified act
    2. verify the act is an ENDORSEMENT
    3. validate the target claim reference
    4. call the TransitionValidator
    5. create the EndorsementEvent ONLY after validation passes

Only endorsement is licence-affecting. preference / judgement / decision /
outcome / unknown are DENIED.

The service never creates a claim, never creates a LicenceRecord, never assigns
truth, and never bypasses the validator.
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Iterable, Optional


from core.governance.endorsement.endorsement_request_v1 import (
    EndorsementRequest,
)
from core.governance.events import record_endorsement_event
from core.governance.identity_v1 import is_claim_reference
from core.governance.licence import (
    FORBIDDEN_LICENCE_STATES,
    LICENCE_STATES,
)
from core.governance.validation import (
    RULE_CODES as VALIDATION_RULE_CODES,
)
from core.governance.validation import transition_validator


CONTRACT = "EndorsementServiceV1"

VERSION = "1.0"


# The single licence an endorsement may grant. An endorsement raises a claim to
# "a human endorsed this" — nothing more.
ENDORSEMENT_LICENCE = "human_endorsed_hypothesis"


# The act that may affect a licence.
LICENCE_AFFECTING_ACTS = ("endorsement",)


SERVICE_RULE_CODES = (
    "allowed",
    "not_a_request",
    "act_not_endorsement",
    "missing_ordering",
    "licence_candidate_not_permitted",
)


@dataclass(frozen=True)
class EndorsementPreparationResult:

    allowed: bool

    reason: str

    rule_code: str

    event: Optional[Any] = None

    validation: Optional[Any] = None

    def __post_init__(self):

        if (
            self.rule_code not in SERVICE_RULE_CODES
            and self.rule_code not in VALIDATION_RULE_CODES
        ):

            raise ValueError("unknown rule_code: %r" % (self.rule_code,))

    def to_dict(self):

        return {
            "contract": CONTRACT,
            "allowed": self.allowed,
            "reason": self.reason,
            "rule_code": self.rule_code,
            "event_id": getattr(self.event, "event_id", None),
            "validation": (
                self.validation.to_dict() if self.validation else None
            ),
        }

    def __repr__(self):

        return "EndorsementPreparationResult(allowed=%r, rule_code=%r)" % (
            self.allowed,
            self.rule_code,
        )


class EndorsementService:

    """Stateless governance service. It holds no state and no licence."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    # ==================================================

    def prepare_endorsement_event(
        self,
        request,
        *,
        ordering,
        previous_licence=None,
        new_licence_candidate=None,
        known_claim_references: Optional[Iterable[str]] = None,
    ) -> EndorsementPreparationResult:

        """Validate, then create the EndorsementEvent. Or deny and create none."""

        # ---- 1. the request must be a request ----
        if not isinstance(request, EndorsementRequest):

            return self._deny(
                "not_a_request",
                "an endorsement requires an EndorsementRequest",
            )

        classification = request.act_classification

        # ---- 2. only endorsement is licence-affecting ----
        if classification.act_type not in LICENCE_AFFECTING_ACTS:

            return self._deny(
                "act_not_endorsement",
                "act %r is not licence-affecting; only endorsement may raise "
                "a licence" % (classification.act_type,),
            )

        # ---- 3. ordering is required by the event contract ----
        if ordering is None:

            return self._deny(
                "missing_ordering", "an endorsement requires an ordering"
            )

        # ---- 4. the target must be a claim reference ----
        target = request.target_claim_reference

        if not is_claim_reference(target):

            return self._deny(
                "event_targets_observation",
                "an endorsement may target a claim only, never observation: %r"
                % (target,),
            )

        if known_claim_references is not None:

            known = {str(item) for item in known_claim_references}

            if str(target) not in known:

                return self._deny(
                    "unresolved_reference",
                    "target claim %r does not resolve" % (target,),
                )

        # ---- 5. the licence candidate must not be invented ----
        if new_licence_candidate is not None:

            if new_licence_candidate in FORBIDDEN_LICENCE_STATES:

                return self._deny(
                    "forbidden_licence",
                    "an endorsement may never grant %r"
                    % (new_licence_candidate,),
                )

            if new_licence_candidate not in LICENCE_STATES:

                return self._deny(
                    "unknown_new_licence",
                    "unknown licence state: %r" % (new_licence_candidate,),
                )

            if new_licence_candidate != ENDORSEMENT_LICENCE:

                return self._deny(
                    "licence_candidate_not_permitted",
                    "an endorsement may only grant %r, not %r"
                    % (ENDORSEMENT_LICENCE, new_licence_candidate),
                )

        new_licence = new_licence_candidate or ENDORSEMENT_LICENCE

        # ---- 6. the validator decides, not the service ----
        licence_check = transition_validator.validate_licence_transition(
            previous_licence=previous_licence,
            new_licence=new_licence,
        )

        if not licence_check.allowed:

            return self._from_validation(licence_check)

        event_check = transition_validator.validate_endorsement_event(
            actor=request.actor_reference,
            target_claim_reference=target,
            previous_licence=previous_licence,
            new_licence=new_licence,
            act_type=classification.act_type,
            ordering=ordering,
        )

        if not event_check.allowed:

            return self._from_validation(event_check)

        # ---- 7. only now is the event created ----
        event = record_endorsement_event(
            actor=request.actor_reference,
            target_claim_reference=target,
            previous_licence=previous_licence,
            new_licence=new_licence,
            act_type=classification.act_type,
            scope=request.requested_scope,
            ordering=ordering,
        )

        return EndorsementPreparationResult(
            allowed=True,
            reason=(
                "endorsement event prepared after validation: %s -> %s"
                % (previous_licence, new_licence)
            ),
            rule_code="allowed",
            event=event,
            validation=licence_check,
        )

    # ==================================================

    @staticmethod
    def _deny(rule_code, reason) -> EndorsementPreparationResult:

        return EndorsementPreparationResult(
            allowed=False,
            reason=reason,
            rule_code=rule_code,
            event=None,
            validation=None,
        )

    @staticmethod
    def _from_validation(validation) -> EndorsementPreparationResult:

        return EndorsementPreparationResult(
            allowed=False,
            reason=validation.reason,
            rule_code=validation.rule_code,
            event=None,
            validation=validation,
        )

    def __repr__(self):

        return (
            "EndorsementService(creates_claims=False, assigns_truth=False, "
            "bypasses_validator=False)"
        )


endorsement_service = EndorsementService()
