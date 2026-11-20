"""ClaimMintingService (V1) — the boundary that mints a Claim from a proposal.

Governance alone mints claim identity and alone creates claim objects. This
service validates eligibility and then mints.

It does NOT assign a licence, does NOT approve truth, does NOT create a
knowledge or candidate object, does NOT widen scope, and does NOT modify the
proposal it was given.

ORDERING CONSTRAINT (V1)
    The claim is minted before its creation event, because the event's
    `output_claim_reference` must be the minted claim id, while the claim's
    `creation_event` back-reference would need the event id first. Both
    factories mint identity internally, so a fully linked pair cannot be
    produced in one pass without weakening the invariant "identity is minted
    only by governance". The link is therefore carried by the event's output
    reference and by ClaimMintResult.
"""

from __future__ import annotations


from typing import Any, Iterable, Optional


from core.governance.claim import (
    CLAIM_TYPES,
    SCOPES,
    SOURCE_TYPES,
    mint_claim,
)
from core.governance.events import record_derivation_event
from core.governance.identity import reservation_v1
from core.governance.identity_v1 import CLAIM_REFERENCE_PREFIX
from core.governance.licence import validate_licence_reference
from core.governance.lineage.lineage_reference_v1 import is_claim_reference
from core.governance.minting.claim_mint_result_v1 import (
    ClaimMintResult,
    build_claim_mint_result,
)
from core.governance.proposal import InterpretationProposal
from core.governance.validation import transition_validator


CONTRACT = "ClaimMintingServiceV1"

VERSION = "1.0"


CREATION_OPERATION_TYPE = "mint_from_proposal"


# This boundary does not decide a licence, so the licence check is DEFERRED.
DEFERRED_LICENCE_CHECK = "deferred"


# Minting never widens. A new claim starts at the narrowest scope unless
# governance explicitly asks for another valid one.
DEFAULT_SCOPE = "single_case"


# The claim <-> creation-event back-reference is now REACHABLE: when the caller
# supplies a governance-owned derivation-event reservation, the claim is minted
# carrying `creation_event` and the reservation is consumed by the event. With
# no reservation the back-reference stays None (the original deferred default).
CLAIM_CREATION_EVENT_BACKREFERENCE_DEFERRED = False


# A shape probe: the validator checks that the event's output is a claim
# reference. The probe is derived from the single source prefix, never a
# duplicated literal.
_CLAIM_SHAPE_PROBE = CLAIM_REFERENCE_PREFIX + "0000000000000000"


_FORBIDDEN_PROPOSAL_AUTHORITY_FIELDS = (
    "claim_id",
    "licence",
    "license",
    "scope",
    "scope_authority",
    "truth",
    "truth_status",
    "is_true",
    "knowledge_status",
    "approved",
    "is_approved",
)


def _present(value) -> bool:

    return bool(str(value or "").strip())


def _receipt_is_accepted(receipt) -> bool:

    """Structural check for an accepted receipt, without importing intake."""

    if receipt is None:

        return False

    if isinstance(receipt, InterpretationProposal):

        return False

    if getattr(receipt, "accepted", None) is not True:

        return False

    return hasattr(receipt, "proposal_reference") and hasattr(receipt, "reason")


class ClaimMintingService:

    """Stateless minting boundary. It mints; it decides nothing else."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    def mint_claim_from_proposal(
        self,
        proposal,
        receipt,
        *,
        source_type,
        origin,
        claim_type=None,
        scope=DEFAULT_SCOPE,
        lineage_reference: Iterable[str] = (),
        licence_reference=None,
        known_claim_references: Optional[Iterable[str]] = None,
        creation_event_reservation=None,
    ) -> ClaimMintResult:

        # ---- 1. the receipt must be accepted ----
        if not _receipt_is_accepted(receipt):

            return self._deny(
                "proposal receipt is not accepted; nothing is minted"
            )

        # ---- 2. the proposal must BE a proposal ----
        if not isinstance(proposal, InterpretationProposal):

            return self._deny("input is not an InterpretationProposal")

        # ---- 3. no authority field may be present ----
        for field in _FORBIDDEN_PROPOSAL_AUTHORITY_FIELDS:

            if hasattr(proposal, field):

                return self._deny(
                    "proposal carries forbidden authority field: %s"
                    % (field,)
                )

        # ---- 4. required content ----
        content = str(
            getattr(proposal, "proposed_content", "") or ""
        ).strip()

        if not content:

            return self._deny("proposal has no content to mint")

        # ---- 5. claim type (governance decides; the proposal's is advisory) ----
        resolved_claim_type = claim_type or getattr(
            proposal, "proposed_claim_type", None
        )

        if resolved_claim_type not in CLAIM_TYPES:

            return self._deny(
                "invalid claim type: %r" % (resolved_claim_type,)
            )

        # ---- 6. source type ----
        if source_type not in SOURCE_TYPES:

            return self._deny("invalid source type: %r" % (source_type,))

        # ---- 7. origin must be explicit ----
        if not _present(origin):

            return self._deny("origin must be explicit")

        # ---- 8. scope must be valid (this boundary never widens) ----
        if scope not in SCOPES:

            return self._deny("invalid scope: %r" % (scope,))

        # ---- 8b. a supplied licence reference must be shape-valid ----
        # This boundary does NOT assign a licence and does NOT check existence;
        # it only refuses a malformed reference. Existence stays deferred.
        if licence_reference is not None:

            licence_check = validate_licence_reference(licence_reference)

            if not licence_check.valid:

                return self._deny(
                    "invalid licence reference: %s" % (licence_check.reason,)
                )

            licence_reference = licence_check.licence_reference

        # ---- 8c. a creation-event reservation must be governance-owned ----
        # The ONLY accepted source of a creation-event identity is a governance
        # reservation (identity.reservation_v1). A raw client-supplied event id
        # is never accepted. This is validated BEFORE the claim is minted, so an
        # invalid reservation cannot leave a half-linked claim behind.
        resolved_creation_event = None

        if creation_event_reservation is not None:

            if not isinstance(
                creation_event_reservation, reservation_v1.ReservedIdentity
            ):

                return self._deny(
                    "creation event reservation is not a ReservedIdentity; a "
                    "client-supplied event id is never accepted"
                )

            if (
                creation_event_reservation.kind
                != reservation_v1.KIND_DERIVATION_EVENT
            ):

                return self._deny(
                    "creation event reservation has the wrong kind: %r"
                    % (creation_event_reservation.kind,)
                )

            if not reservation_v1.reservation_ledger.is_reserved(
                creation_event_reservation.identity
            ):

                return self._deny(
                    "creation event reservation is not reserved: %r"
                    % (creation_event_reservation.identity,)
                )

            resolved_creation_event = creation_event_reservation.identity

        # ---- 9. lineage structural checks ----
        parents = tuple(lineage_reference or ())

        for parent in parents:

            parent_id = str(parent or "").strip()

            if not parent_id:

                return self._deny("empty lineage reference")

            if not is_claim_reference(parent_id):

                return self._deny(
                    "lineage reference %r is not a claim reference"
                    % (parent_id,)
                )

        if known_claim_references is not None:

            known = {str(item) for item in known_claim_references}

            for parent_id in parents:

                if str(parent_id) not in known:

                    return self._deny(
                        "lineage reference %r does not resolve" % (parent_id,)
                    )

        # ---- 10. a claim must be derived from something ----
        inputs = (
            tuple(getattr(proposal, "trigger_references", ()) or ())
            + parents
        )

        if not inputs:

            return self._deny("a claim must be derived from something")

        # ---- 11. the validator checks the creation event shape ----
        event_check = transition_validator.validate_derivation_event(
            input_references=inputs,
            output_claim_reference=_CLAIM_SHAPE_PROBE,
            operation_type=CREATION_OPERATION_TYPE,
            licence_check_result=DEFERRED_LICENCE_CHECK,
        )

        if not event_check.allowed:

            return self._deny(
                "creation event rejected: %s" % (event_check.reason,)
            )

        # ---- 12. mint. The ONLY place an object is created. ----
        claim = mint_claim(
            content=content,
            origin=origin,
            source_type=source_type,
            claim_type=resolved_claim_type,
            original_scope=scope,
            lineage_reference=parents,
            licence_reference=licence_reference,
            creation_event=resolved_creation_event,
        )

        event = record_derivation_event(
            input_references=inputs,
            output_claim_reference=claim.claim_id,
            operation_type=CREATION_OPERATION_TYPE,
            licence_check_result=DEFERRED_LICENCE_CHECK,
            reservation=creation_event_reservation,
        )

        return build_claim_mint_result(
            created=True,
            claim_reference=claim.claim_id,
            creation_event_reference=event.event_id,
            reason=(
                "claim minted; creation event recorded; licence deferred"
            ),
            claim=claim,
        )

    # ==================================================

    @staticmethod
    def _deny(reason) -> ClaimMintResult:

        return build_claim_mint_result(
            created=False,
            claim_reference=None,
            creation_event_reference=None,
            reason=reason,
            claim=None,
        )

    def __repr__(self):

        return (
            "ClaimMintingService(assigns_licence=False, approves_truth=False, "
            "creates_knowledge=False)"
        )


claim_minting_service = ClaimMintingService()
