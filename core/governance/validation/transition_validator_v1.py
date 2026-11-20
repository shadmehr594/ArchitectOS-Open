"""TransitionValidator (V1) — a read-only GUARD.

The validator does NOT create objects, does NOT mutate state and does NOT assign
licences. It answers only ALLOW / DENY + reason, as an immutable
TransitionResult.

Supported checks
    A) claim creation
    B) licence transition
    C) event validation (derivation, endorsement)
    D) knowledge-candidate eligibility helper (no candidate is created)

Deliberately NOT decided here (returned as NOT_IMPLEMENTED boundary results)
    * scope widening mathematics
    * experience aggregation
    * heuristic promotion rules
    * multiple endorsement aggregation

Dependency direction: validation -> claim / licence / events / lineage.
Never the reverse, and never a client subsystem.
"""

from __future__ import annotations


from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple


from core.governance.claim import (
    CLAIM_TYPES,
    FORBIDDEN_CLAIM_FIELDS,
    SCOPES,
    SOURCE_TYPES,
)
from core.governance.events import ACT_TYPES, OPERATION_TYPES
from core.governance.licence import (
    FORBIDDEN_LICENCE_STATES,
    LICENCE_STATES,
)
from core.governance.lineage.lineage_reference_v1 import (
    LineageReference,
    is_claim_reference,
)
from core.governance.validation.transition_result_v1 import (
    TransitionResult,
)


CONTRACT = "TransitionValidatorV1"

VERSION = "1.0"


# The licence transition table. A transition is legal only when it appears here.
ALLOWED_LICENCE_TRANSITIONS: Tuple[Tuple[str, str], ...] = (
    # forward
    ("unlicensed_hypothesis", "human_endorsed_hypothesis"),
    ("unlicensed_hypothesis", "candidate_for_learning"),
    ("human_endorsed_hypothesis", "candidate_for_learning"),
    ("candidate_for_learning", "generalized_experience"),
    ("generalized_experience", "heuristic_candidate"),
    # demotion (scope narrowing is always safe)
    ("human_endorsed_hypothesis", "unlicensed_hypothesis"),
    ("candidate_for_learning", "human_endorsed_hypothesis"),
    ("generalized_experience", "candidate_for_learning"),
    ("heuristic_candidate", "generalized_experience"),
)


# Fields that would make an endorsement mutate a claim's content.
_CONTENT_MUTATION_FIELDS = (
    "content",
    "new_content",
    "set_content",
    "mutate",
    "mutated_content",
)


def _present(value) -> bool:

    return bool(str(value or "").strip())


def _lineage_parents(lineage_reference) -> Tuple[str, ...]:

    if isinstance(lineage_reference, LineageReference):

        return lineage_reference.parent_claim_references

    return tuple(lineage_reference or ())


class TransitionValidator:

    """Stateless read-only guard. It holds no state and exposes no write path."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    # ==================================================
    # A) claim creation
    # ==================================================

    def validate_claim_creation(
        self,
        *,
        identity=None,
        origin=None,
        source_type=None,
        claim_type=None,
        licence_reference=None,
        creation_event=None,
        lineage_reference=(),
        payload: Optional[Mapping[str, Any]] = None,
    ) -> TransitionResult:

        if not _present(identity):

            return TransitionResult.deny(
                "missing_identity",
                "a claim requires a governance-minted identity",
            )

        if not _present(origin):

            return TransitionResult.deny(
                "missing_origin", "a claim requires an origin"
            )

        if not _present(source_type):

            return TransitionResult.deny(
                "missing_source_type", "a claim requires a source_type"
            )

        if source_type not in SOURCE_TYPES:

            return TransitionResult.deny(
                "unknown_source_type",
                "unknown source_type: %r" % (source_type,),
            )

        if not _present(claim_type):

            return TransitionResult.deny(
                "missing_claim_type", "a claim requires a claim_type"
            )

        if claim_type not in CLAIM_TYPES:

            return TransitionResult.deny(
                "unknown_claim_type",
                "unknown claim_type: %r" % (claim_type,),
            )

        if not _present(licence_reference):

            return TransitionResult.deny(
                "missing_licence_reference",
                "a claim may not exist without a licence reference",
            )

        if not _present(creation_event):

            return TransitionResult.deny(
                "missing_creation_event",
                "a claim requires a creation event",
            )

        for key in (payload or {}):

            if key in FORBIDDEN_CLAIM_FIELDS:

                return TransitionResult.deny(
                    "forbidden_truth_field",
                    "forbidden claim field %r must never exist" % (key,),
                )

        for parent in _lineage_parents(lineage_reference):

            parent_id = str(parent or "").strip()

            if not parent_id:

                return TransitionResult.deny(
                    "invalid_lineage", "empty lineage reference"
                )

            if parent_id == str(identity):

                return TransitionResult.deny(
                    "invalid_lineage",
                    "a claim may not be its own parent",
                )

            if not is_claim_reference(parent_id):

                return TransitionResult.deny(
                    "invalid_lineage",
                    "parent %r is not a claim reference" % (parent_id,),
                )

        return TransitionResult.allow("claim creation permitted")

    # ==================================================
    # B) licence transition
    # ==================================================

    def validate_licence_transition(
        self,
        *,
        previous_licence=None,
        new_licence=None,
    ) -> TransitionResult:

        if not _present(previous_licence):

            return TransitionResult.deny(
                "unknown_previous_licence",
                "previous_licence is required",
            )

        if previous_licence not in LICENCE_STATES:

            return TransitionResult.deny(
                "unknown_previous_licence",
                "unknown previous_licence: %r" % (previous_licence,),
            )

        if new_licence in FORBIDDEN_LICENCE_STATES:

            return TransitionResult.deny(
                "forbidden_licence",
                "licence never means %r" % (new_licence,),
            )

        if not _present(new_licence):

            return TransitionResult.deny(
                "unknown_new_licence", "new_licence is required"
            )

        if new_licence not in LICENCE_STATES:

            return TransitionResult.deny(
                "unknown_new_licence",
                "unknown new_licence: %r" % (new_licence,),
            )

        if (previous_licence, new_licence) not in ALLOWED_LICENCE_TRANSITIONS:

            return TransitionResult.deny(
                "undefined_transition",
                "transition %r -> %r is not defined"
                % (previous_licence, new_licence),
            )

        return TransitionResult.allow(
            "licence transition permitted: %s -> %s"
            % (previous_licence, new_licence)
        )

    # ==================================================
    # C) event validation
    # ==================================================

    def validate_derivation_event(
        self,
        *,
        input_references: Iterable[str] = (),
        output_claim_reference=None,
        operation_type=None,
        licence_check_result=None,
        known_references: Optional[Iterable[str]] = None,
    ) -> TransitionResult:

        inputs = tuple(input_references or ())

        if not inputs:

            return TransitionResult.deny(
                "missing_event_field",
                "a derivation event requires input references",
            )

        if not _present(output_claim_reference):

            return TransitionResult.deny(
                "missing_event_field",
                "a derivation event requires an output claim reference",
            )

        if not is_claim_reference(output_claim_reference):

            return TransitionResult.deny(
                "unresolved_reference",
                "output %r is not a claim reference"
                % (output_claim_reference,),
            )

        if not _present(operation_type):

            return TransitionResult.deny(
                "missing_event_field",
                "a derivation event requires an operation type",
            )

        if operation_type not in OPERATION_TYPES:

            return TransitionResult.deny(
                "unknown_operation_type",
                "unknown operation_type: %r" % (operation_type,),
            )

        if not _present(licence_check_result):

            return TransitionResult.deny(
                "missing_event_field",
                "a derivation event requires a licence check result",
            )

        if known_references is not None:

            known = {str(item) for item in known_references}

            for item in inputs:

                item_id = str(item or "")

                if is_claim_reference(item_id) and item_id not in known:

                    return TransitionResult.deny(
                        "unresolved_reference",
                        "input %r does not resolve" % (item_id,),
                    )

        return TransitionResult.allow("derivation event permitted")

    def validate_endorsement_event(
        self,
        *,
        actor=None,
        target_claim_reference=None,
        previous_licence=None,
        new_licence=None,
        act_type=None,
        ordering=None,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> TransitionResult:

        if not _present(actor):

            return TransitionResult.deny(
                "missing_event_field", "an endorsement requires an actor"
            )

        if not _present(target_claim_reference):

            return TransitionResult.deny(
                "missing_event_field",
                "an endorsement requires a target claim reference",
            )

        if not is_claim_reference(target_claim_reference):

            return TransitionResult.deny(
                "event_targets_observation",
                "an endorsement may target a claim only, never observation: %r"
                % (target_claim_reference,),
            )

        if not _present(previous_licence):

            return TransitionResult.deny(
                "missing_event_field",
                "an endorsement requires the previous licence",
            )

        if not _present(new_licence):

            return TransitionResult.deny(
                "missing_event_field",
                "an endorsement requires the new licence",
            )

        if not _present(act_type):

            return TransitionResult.deny(
                "missing_event_field", "an endorsement requires an act type"
            )

        if act_type not in ACT_TYPES:

            return TransitionResult.deny(
                "unknown_act_type", "unknown act_type: %r" % (act_type,)
            )

        if ordering is None:

            return TransitionResult.deny(
                "missing_event_field", "an endorsement requires an ordering"
            )

        if new_licence in FORBIDDEN_LICENCE_STATES:

            return TransitionResult.deny(
                "event_creates_truth",
                "an endorsement may never grant %r" % (new_licence,),
            )

        if new_licence not in LICENCE_STATES:

            return TransitionResult.deny(
                "unknown_new_licence",
                "unknown new_licence: %r" % (new_licence,),
            )

        if previous_licence not in LICENCE_STATES:

            return TransitionResult.deny(
                "unknown_previous_licence",
                "unknown previous_licence: %r" % (previous_licence,),
            )

        for key in (payload or {}):

            if key in _CONTENT_MUTATION_FIELDS:

                return TransitionResult.deny(
                    "event_mutates_content",
                    "an event may not carry %r — content is immutable" % (key,),
                )

        return TransitionResult.allow("endorsement event permitted")

    # ==================================================
    # D) knowledge-candidate eligibility (no object created)
    # ==================================================

    def can_be_candidate(
        self,
        claim,
        *,
        known_claim_ids: Optional[Iterable[str]] = None,
    ) -> TransitionResult:

        """Answers whether a claim is ELIGIBLE. Creates no candidate."""

        if claim is None:

            return TransitionResult.deny(
                "claim_not_typed", "no claim supplied"
            )

        source_type = getattr(claim, "source_type", None)

        claim_type = getattr(claim, "claim_type", None)

        if source_type not in SOURCE_TYPES or claim_type not in CLAIM_TYPES:

            return TransitionResult.deny(
                "claim_not_typed",
                "a candidate claim must carry a known source_type and claim_type",
            )

        if getattr(claim, "original_scope", None) not in SCOPES:

            return TransitionResult.deny(
                "claim_not_scoped", "a candidate claim must carry a known scope"
            )

        if not _present(getattr(claim, "licence_reference", None)):

            return TransitionResult.deny(
                "claim_not_licensed",
                "a candidate claim must carry a licence reference",
            )

        claim_id = str(getattr(claim, "claim_id", "") or "")

        parents = tuple(getattr(claim, "lineage_reference", ()) or ())

        for parent in parents:

            parent_id = str(parent or "")

            if parent_id == claim_id or not is_claim_reference(parent_id):

                return TransitionResult.deny(
                    "claim_lineage_incomplete",
                    "lineage reference %r is not a valid parent" % (parent_id,),
                )

            if known_claim_ids is not None:

                if parent_id not in {str(item) for item in known_claim_ids}:

                    return TransitionResult.deny(
                        "claim_lineage_incomplete",
                        "lineage reference %r does not resolve" % (parent_id,),
                    )

        return TransitionResult.allow("claim is eligible to be a candidate")

    # ==================================================
    # COMPOSITION RULE LIMITATION
    #
    # These decisions belong to a later phase. The validator returns an explicit
    # NOT_IMPLEMENTED boundary result rather than guessing.
    # ==================================================

    def validate_scope_widening(self, *args, **kwargs) -> TransitionResult:

        return TransitionResult.not_implemented("scope widening mathematics")

    def validate_experience_aggregation(self, *args, **kwargs) -> TransitionResult:

        return TransitionResult.not_implemented("experience aggregation")

    def validate_heuristic_promotion(self, *args, **kwargs) -> TransitionResult:

        return TransitionResult.not_implemented("heuristic promotion rules")

    def validate_multiple_endorsement_aggregation(
        self, *args, **kwargs
    ) -> TransitionResult:

        return TransitionResult.not_implemented(
            "multiple endorsement aggregation"
        )

    def __repr__(self):

        return "TransitionValidator(read_only=True, creates_objects=False)"


transition_validator = TransitionValidator()
