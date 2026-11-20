"""LicenceAssignmentService (V1) — the boundary that assigns a licence.

Governance owns licence identity. This service validates the claim reference and
the licence transition, then mints a LicenceRecord.

It may NOT
    create a Claim
    modify a Claim
    create a Knowledge object
    decide truth
    bypass the TransitionValidator
    accept a client-supplied licence_id
"""

from __future__ import annotations


from typing import Iterable, Optional


from core.governance.licence import (
    LICENCE_STATES,
    mint_licence_record,
)
from core.governance.licensing.licence_assignment_request_v1 import (
    LicenceAssignmentRequest,
)
from core.governance.licensing.licence_assignment_result_v1 import (
    LicenceAssignmentResult,
    build_licence_assignment_result,
)
from core.governance.lineage.lineage_reference_v1 import is_claim_reference
from core.governance.validation import transition_validator


CONTRACT = "LicenceAssignmentServiceV1"

VERSION = "1.0"


class LicenceAssignmentService:

    """Stateless licensing boundary. It assigns; it decides nothing else."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    def assign_licence(
        self,
        request,
        *,
        previous_licence,
        known_claim_references: Optional[Iterable[str]] = None,
    ) -> LicenceAssignmentResult:

        # ---- 1. the request must be a request ----
        if not isinstance(request, LicenceAssignmentRequest):

            return self._deny(
                None, "an assignment requires a LicenceAssignmentRequest"
            )

        target = request.target_claim_reference

        # ---- 2. the target must be a claim reference ----
        if not is_claim_reference(target):

            return self._deny(
                target,
                "unknown claim reference: %r is not a claim reference"
                % (target,),
            )

        if known_claim_references is not None:

            known = {str(item) for item in known_claim_references}

            if str(target) not in known:

                return self._deny(
                    target, "unknown claim reference: %r" % (target,)
                )

        # ---- 3. the requested licence must be a known state ----
        if request.requested_licence not in LICENCE_STATES:

            return self._deny(
                target,
                "unknown licence state: %r" % (request.requested_licence,),
            )

        # ---- 4. the TransitionValidator decides, not the service ----
        check = transition_validator.validate_licence_transition(
            previous_licence=previous_licence,
            new_licence=request.requested_licence,
        )

        if not check.allowed:

            return self._deny(target, check.reason)

        # ---- 5. mint. The ONLY place an object is created. ----
        history = tuple(
            item
            for item in (request.basis_reference, request.actor_reference)
            if item
        )

        record = mint_licence_record(
            target_claim_reference=target,
            licence_state=request.requested_licence,
            history_reference=history,
        )

        return build_licence_assignment_result(
            assigned=True,
            licence_reference=record.licence_id,
            target_claim_reference=target,
            reason=(
                "licence assigned: %s -> %s"
                % (previous_licence, request.requested_licence)
            ),
            licence_record=record,
        )

    # ==================================================

    @staticmethod
    def _deny(target, reason) -> LicenceAssignmentResult:

        return build_licence_assignment_result(
            assigned=False,
            licence_reference=None,
            target_claim_reference=target,
            reason=reason,
            licence_record=None,
        )

    def __repr__(self):

        return (
            "LicenceAssignmentService(creates_claims=False, "
            "decides_truth=False, bypasses_validator=False)"
        )


licence_assignment_service = LicenceAssignmentService()
