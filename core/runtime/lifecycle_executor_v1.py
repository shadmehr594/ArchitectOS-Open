"""Runtime Lifecycle Executor (V1) — runtime-owned orchestration over governance.

This is the RUNTIME layer. It orchestrates the canonical A1..A8 lifecycle by
calling governance boundaries. It owns ONLY:

    execution order (A1..A8)
    the ReferenceRegistry instance lifecycle
    the ordering counter (reserved for the human-feedback path)
    failure-propagation policy

It NEVER:
    mints an identity (no uuid4 / mint_id / new_*_id)
    constructs a Claim / LicenceRecord / DerivationEvent / EndorsementEvent
    synthesises or transforms a reference
    decides truth / confidence / approval
    persists state
    bypasses a governance validator

Dependency direction

    runtime  ->  governance     ALLOWED
    governance -> runtime       FORBIDDEN
    governance -> client        FORBIDDEN

The executor holds references returned by governance results. It holds no
authoritative copy of any governance object.
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Optional


from core.governance.accessors import REASON_CONFLICT, resolve_licence_state
from core.governance.adapters import Auv2AdapterError, to_proposal
from core.governance.admission import (
    build_knowledge_candidate,
    knowledge_admission_service,
)
from core.governance.claim import mint_claim
from core.governance.claim.claim_v1 import ClaimIdentityError, ClaimVocabularyError
from core.governance.events import EventError, record_derivation_event
from core.governance.identity.reservation_v1 import (
    ReservationError,
    reserve_claim_id,
    reserve_derivation_event_id,
)
from core.governance.identity_v1 import IdentityError
from core.governance.intake import proposal_intake_service
from core.governance.licensing import (
    build_licence_assignment_request,
    licence_assignment_service,
)
from core.governance.proposal import (
    ProposalAuthorityError,
    build_proposal,
)
from core.governance.registry import (
    STATUS_APPENDED,
    STATUS_DUPLICATE,
    ReferenceRegistry,
)


CONTRACT = "RuntimeLifecycleExecutorV1"

VERSION = "1.0"


# ----------------------------------------------------------
# stages
# ----------------------------------------------------------

STAGE_A1 = "A1_adapter"

STAGE_A2 = "A2_proposal"

STAGE_A3 = "A3_receipt"

STAGE_A4 = "A4_reservation"

STAGE_A5 = "A5_licence"

STAGE_A6 = "A6_mint"

STAGE_A7 = "A7_registry"

STAGE_A8 = "A8_admission"


STAGES = (
    STAGE_A1,
    STAGE_A2,
    STAGE_A3,
    STAGE_A4,
    STAGE_A5,
    STAGE_A6,
    STAGE_A7,
    STAGE_A8,
)


# ----------------------------------------------------------
# outcomes
# ----------------------------------------------------------

STATUS_ADMITTED = "admitted"

STATUS_DENIED = "denied"

STATUS_ERROR = "error"


STATUSES = (STATUS_ADMITTED, STATUS_DENIED, STATUS_ERROR)


# The substrate's documented initial licence state for a fresh claim (the only
# entry point of the transition table for a new claim).
INITIAL_LICENCE_STATE = "unlicensed_hypothesis"


# The derivation-event operation recorded at claim creation.
CREATION_OPERATION_TYPE = "mint_from_proposal"


# An append is accepted only when it is a new entry or an identical duplicate.
ACCEPTED_APPEND_STATUSES = (STATUS_APPENDED, STATUS_DUPLICATE)


class LifecycleExecutorError(ValueError):
    """Raised when the executor itself is misused."""


@dataclass(frozen=True)
class LifecycleResult:

    """The immutable outcome of one A1..A8 execution."""

    completed: bool

    stage: str

    status: str

    reason: str

    proposal_reference: Optional[str] = None

    claim_reference: Optional[str] = None

    derivation_event_reference: Optional[str] = None

    licence_reference: Optional[str] = None

    licence_state: Optional[str] = None

    candidate_reference: Optional[str] = None

    error_type: Optional[str] = None

    admission: Optional[Any] = None

    # The runtime orchestrates. It creates nothing and decides nothing.
    CREATES_IDENTITY = False

    CREATES_OBJECTS = False

    DECIDES_TRUTH = False

    PERSISTS = False

    def __post_init__(self):

        if self.stage not in STAGES:

            raise LifecycleExecutorError("unknown stage: %r" % (self.stage,))

        if self.status not in STATUSES:

            raise LifecycleExecutorError("unknown status: %r" % (self.status,))

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "completed": self.completed,
            "stage": self.stage,
            "status": self.status,
            "reason": self.reason,
            "proposal_reference": self.proposal_reference,
            "claim_reference": self.claim_reference,
            "derivation_event_reference": self.derivation_event_reference,
            "licence_reference": self.licence_reference,
            "licence_state": self.licence_state,
            "candidate_reference": self.candidate_reference,
            "error_type": self.error_type,
            "creates_identity": False,
            "creates_objects": False,
            "decides_truth": False,
            "persists": False,
        }

    def __repr__(self):

        return "LifecycleResult(completed=%r, stage=%r, status=%r)" % (
            self.completed,
            self.stage,
            self.status,
        )


class LifecycleExecutor:

    """Runtime orchestrator for A1..A8. Stateless with respect to governance."""

    __slots__ = ("_registry", "_licence_records", "_ordering")

    CONTRACT = CONTRACT

    VERSION = VERSION

    def __init__(self, registry=None):

        self._registry = (
            registry if registry is not None else ReferenceRegistry()
        )

        # runtime-owned records, used to source `previous_licence` through G3
        self._licence_records = []

        # runtime-owned monotonic ordering counter (human-feedback path)
        self._ordering = 0

    # --------------------------------------------------
    # runtime-owned resources
    # --------------------------------------------------

    @property
    def registry(self) -> ReferenceRegistry:

        return self._registry

    def next_ordering(self) -> int:

        """The runtime-owned monotonic counter (reserved for endorsements)."""

        self._ordering += 1

        return self._ordering

    def __repr__(self):

        return "LifecycleExecutor(entries=%d, ordering=%d)" % (
            self._registry.count(),
            self._ordering,
        )

    # --------------------------------------------------
    # the lifecycle
    # --------------------------------------------------

    def run(
        self,
        auv2=None,
        *,
        proposal_fields=None,
        language: str = "unknown",
        source_type,
        origin,
        requested_licence: str = "candidate_for_learning",
        basis_reference: Optional[str] = None,
        actor_reference: Optional[str] = None,
        scope: str = "single_case",
        previous_licence: Optional[str] = None,
    ) -> LifecycleResult:

        """Execute A1..A8. Provide exactly one of `auv2` or `proposal_fields`."""

        if (auv2 is None) == (proposal_fields is None):

            return self._error(
                STAGE_A1,
                "provide exactly one of auv2 or proposal_fields",
            )

        # ---- A1 / A2: obtain an InterpretationProposal ----
        if auv2 is not None:

            try:

                proposal = to_proposal(auv2, language=language)

            except Auv2AdapterError as error:

                return self._error(STAGE_A1, error)

        else:

            try:

                proposal = build_proposal(**dict(proposal_fields))

            except ProposalAuthorityError as error:

                return self._error(STAGE_A2, error)

        # ---- A3: submit the proposal ----
        receipt = proposal_intake_service.submit_proposal(proposal)

        if not receipt.accepted:

            return self._denied(
                STAGE_A3,
                receipt.reason,
                proposal_reference=receipt.proposal_reference,
            )

        # ---- A4: reserve the claim and derivation-event identities ----
        claim_reservation = reserve_claim_id()

        event_reservation = reserve_derivation_event_id()

        # ---- A5: assign the licence to the RESERVED claim id ----
        # The target claim is a reservation, not a registered claim, so no
        # known-reference set is supplied (shape-only validation).
        prior = previous_licence

        if prior is None:

            prior_view = resolve_licence_state(
                claim_reservation.identity,
                licence_records=tuple(self._licence_records),
            )

            if prior_view.reason.startswith(REASON_CONFLICT):

                return self._denied(STAGE_A5, prior_view.reason)

            prior = prior_view.licence_state or INITIAL_LICENCE_STATE

        request = build_licence_assignment_request(
            target_claim_reference=claim_reservation.identity,
            requested_licence=requested_licence,
            basis_reference=basis_reference,
            actor_reference=actor_reference,
        )

        assignment = licence_assignment_service.assign_licence(
            request,
            previous_licence=prior,
        )

        if not assignment.assigned:

            return self._denied(STAGE_A5, assignment.reason)

        if assignment.licence_record is None:

            return self._error(
                STAGE_A5,
                "assignment reported success without a LicenceRecord",
            )

        # the returned record is the authoritative source for the state
        self._licence_records.append(assignment.licence_record)

        licence_view = resolve_licence_state(
            claim_reservation.identity,
            licence_records=[assignment.licence_record],
        )

        # ---- A6: mint the claim and its creation event ----
        try:

            claim = mint_claim(
                content=proposal.proposed_content,
                origin=origin,
                source_type=source_type,
                claim_type=proposal.proposed_claim_type,
                original_scope=scope,
                lineage_reference=(),
                licence_reference=assignment.licence_reference,
                creation_event=event_reservation.identity,
                reservation=claim_reservation,
            )

            event = record_derivation_event(
                input_references=proposal.trigger_references,
                output_claim_reference=claim.claim_id,
                operation_type=CREATION_OPERATION_TYPE,
                licence_check_result="allowed",
                reservation=event_reservation,
            )

        except (
            ClaimVocabularyError,
            ClaimIdentityError,
            EventError,
            ReservationError,
            IdentityError,
        ) as error:

            return self._error(STAGE_A6, error)

        # invariants — the reserved identities must be the minted ones
        if claim.claim_id != claim_reservation.identity:

            return self._error(
                STAGE_A6, "minted claim id does not match the reservation"
            )

        if claim.creation_event != event.event_id:

            return self._error(
                STAGE_A6, "claim.creation_event does not match the event id"
            )

        if claim.licence_reference != assignment.licence_reference:

            return self._error(
                STAGE_A6, "claim licence reference does not match the assignment"
            )

        # ---- A7: registry append (EXACTLY ONCE, before admission) ----
        append_result = self._registry.append(
            {
                "claim_reference": claim.claim_id,
                "proposal_reference": receipt.proposal_reference,
                "derivation_event_reference": event.event_id,
                "licence_reference": assignment.licence_reference,
                "scope": scope,
            }
        )

        if append_result.status not in ACCEPTED_APPEND_STATUSES:

            return self._denied(STAGE_A7, append_result.reason)

        # ---- A8: build the candidate, then admit ----
        candidate = build_knowledge_candidate(
            source_claim_reference=claim.claim_id,
            licence_reference=assignment.licence_reference,
            scope=scope,
        )

        admission = knowledge_admission_service.admit(
            candidate,
            claim=claim,
            known_claim_references=self._registry.known_claim_references(),
            known_licence_references=self._registry.known_licence_references(),
        )

        if not admission.admitted:

            return self._denied(
                STAGE_A8,
                admission.reason,
                proposal_reference=receipt.proposal_reference,
                claim_reference=claim.claim_id,
                derivation_event_reference=event.event_id,
                licence_reference=assignment.licence_reference,
                licence_state=licence_view.licence_state,
                admission=admission,
            )

        return LifecycleResult(
            completed=True,
            stage=STAGE_A8,
            status=STATUS_ADMITTED,
            reason=admission.reason,
            proposal_reference=receipt.proposal_reference,
            claim_reference=claim.claim_id,
            derivation_event_reference=event.event_id,
            licence_reference=assignment.licence_reference,
            licence_state=licence_view.licence_state,
            candidate_reference=admission.candidate_reference,
            admission=admission,
        )

    # --------------------------------------------------
    # failure constructors — governance results are preserved verbatim
    # --------------------------------------------------

    def _denied(self, stage, reason, **references) -> LifecycleResult:

        return LifecycleResult(
            completed=False,
            stage=stage,
            status=STATUS_DENIED,
            reason=str(reason),
            **references,
        )

    @staticmethod
    def _error(stage, error) -> LifecycleResult:

        return LifecycleResult(
            completed=False,
            stage=stage,
            status=STATUS_ERROR,
            reason=str(error),
            error_type=type(error).__name__,
        )


lifecycle_executor = LifecycleExecutor()
