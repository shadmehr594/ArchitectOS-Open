"""Claim events (V1) — append-only.

Events are the ONLY mechanism allowed to represent change. They are immutable
and expose no mutation or deletion methods.

Two event types
    DerivationEvent   — an act that produced a claim from inputs
    EndorsementEvent  — an act that changed a claim's licence
"""

from __future__ import annotations


from typing import Any, Dict, Tuple


from core.governance import identity_v1
from core.governance.identity import reservation_v1
from core.governance.licence.licence_record_v1 import (
    FORBIDDEN_LICENCE_STATES,
    LICENCE_STATES,
)


CONTRACT = "ClaimEventsV1"

VERSION = "1.0"


OPERATION_TYPES = (
    "mint_from_proposal",
    "generalize",
    "correct",
    "contradict",
    "supersede",
)


ACT_TYPES = (
    "endorsement",
    "preference",
    "judgement",
    "expertise",
    "decision",
    "outcome",
    "correction",
)


_MINT_AUTHORITY = object()


class EventError(ValueError):
    """Raised when an event cannot be recorded."""


class _SealedEvent:

    """Shared immutability + append-only behaviour for event objects."""

    __slots__ = ("_sealed",)

    def __setattr__(self, name, value):

        if getattr(self, "_sealed", False):

            raise EventError(
                "events are immutable and append-only: cannot set %r" % (name,)
            )

        object.__setattr__(self, name, value)

    def __delattr__(self, name):

        raise EventError(
            "events are append-only: cannot delete %r" % (name,)
        )


class DerivationEvent(_SealedEvent):

    __slots__ = (
        "_event_id",
        "_input_references",
        "_output_claim_reference",
        "_operation_type",
        "_licence_check_result",
        "_sealed",
    )

    def __init__(
        self,
        *,
        event_id,
        input_references,
        output_claim_reference,
        operation_type,
        licence_check_result=None,
        _authority=None,
    ):

        if _authority is not _MINT_AUTHORITY:

            raise EventError(
                "DerivationEvent is recorded only by governance; use "
                "record_derivation_event()."
            )

        # Normalise once, so a generator input is never consumed twice.
        inputs = tuple(input_references or ())

        identity_v1.reject_vision_id(event_id)

        if not identity_v1.is_governance_id(event_id):

            raise EventError(
                "event_id must be governance-minted: %r" % (event_id,)
            )

        if operation_type not in OPERATION_TYPES:

            raise EventError(
                "unknown operation_type: %r" % (operation_type,)
            )

        if not str(output_claim_reference or "").strip():

            raise EventError("output_claim_reference is required")

        if not inputs:

            raise EventError(
                "a derivation event requires at least one input reference"
            )

        object.__setattr__(self, "_sealed", False)

        object.__setattr__(self, "_event_id", str(event_id))

        object.__setattr__(self, "_input_references", inputs)

        object.__setattr__(
            self, "_output_claim_reference", str(output_claim_reference)
        )

        object.__setattr__(self, "_operation_type", operation_type)

        object.__setattr__(
            self, "_licence_check_result", licence_check_result
        )

        object.__setattr__(self, "_sealed", True)

    @property
    def event_id(self):

        return self._event_id

    @property
    def input_references(self):

        return self._input_references

    @property
    def output_claim_reference(self):

        return self._output_claim_reference

    @property
    def operation_type(self):

        return self._operation_type

    @property
    def licence_check_result(self):

        return self._licence_check_result

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "event_type": "DerivationEvent",
            "version": VERSION,
            "event_id": self._event_id,
            "input_references": list(self._input_references),
            "output_claim_reference": self._output_claim_reference,
            "operation_type": self._operation_type,
            "licence_check_result": self._licence_check_result,
            "immutable": True,
            "append_only": True,
        }

    def __repr__(self):

        return "DerivationEvent(event_id=%r, operation=%r, output=%r)" % (
            self._event_id,
            self._operation_type,
            self._output_claim_reference,
        )


class EndorsementEvent(_SealedEvent):

    __slots__ = (
        "_event_id",
        "_actor",
        "_target_claim_reference",
        "_previous_licence",
        "_new_licence",
        "_act_type",
        "_scope",
        "_ordering",
        "_sealed",
    )

    def __init__(
        self,
        *,
        event_id,
        actor,
        target_claim_reference,
        previous_licence,
        new_licence,
        act_type,
        scope,
        ordering,
        _authority=None,
    ):

        if _authority is not _MINT_AUTHORITY:

            raise EventError(
                "EndorsementEvent is recorded only by governance; use "
                "record_endorsement_event()."
            )

        identity_v1.reject_vision_id(event_id)

        if not identity_v1.is_governance_id(event_id):

            raise EventError(
                "event_id must be governance-minted: %r" % (event_id,)
            )

        if act_type not in ACT_TYPES:

            raise EventError("unknown act_type: %r" % (act_type,))

        if new_licence in FORBIDDEN_LICENCE_STATES:

            raise EventError(
                "an endorsement may never grant %r" % (new_licence,)
            )

        if new_licence not in LICENCE_STATES:

            raise EventError("unknown new_licence: %r" % (new_licence,))

        if previous_licence is not None and previous_licence not in LICENCE_STATES:

            raise EventError(
                "unknown previous_licence: %r" % (previous_licence,)
            )

        if not str(actor or "").strip():

            raise EventError("actor is required")

        if not str(target_claim_reference or "").strip():

            raise EventError("target_claim_reference is required")

        if ordering is None:

            raise EventError("an endorsement event requires an ordering")

        object.__setattr__(self, "_sealed", False)

        object.__setattr__(self, "_event_id", str(event_id))

        object.__setattr__(self, "_actor", str(actor))

        object.__setattr__(
            self, "_target_claim_reference", str(target_claim_reference)
        )

        object.__setattr__(self, "_previous_licence", previous_licence)

        object.__setattr__(self, "_new_licence", new_licence)

        object.__setattr__(self, "_act_type", act_type)

        object.__setattr__(self, "_scope", scope)

        object.__setattr__(self, "_ordering", ordering)

        object.__setattr__(self, "_sealed", True)

    @property
    def event_id(self):

        return self._event_id

    @property
    def actor(self):

        return self._actor

    @property
    def target_claim_reference(self):

        return self._target_claim_reference

    @property
    def previous_licence(self):

        return self._previous_licence

    @property
    def new_licence(self):

        return self._new_licence

    @property
    def act_type(self):

        return self._act_type

    @property
    def scope(self):

        return self._scope

    @property
    def ordering(self):

        return self._ordering

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "event_type": "EndorsementEvent",
            "version": VERSION,
            "event_id": self._event_id,
            "actor": self._actor,
            "target_claim_reference": self._target_claim_reference,
            "previous_licence": self._previous_licence,
            "new_licence": self._new_licence,
            "act_type": self._act_type,
            "scope": self._scope,
            "ordering": self._ordering,
            "immutable": True,
            "append_only": True,
        }

    def __repr__(self):

        return (
            "EndorsementEvent(event_id=%r, act_type=%r, target=%r, "
            "previous=%r, new=%r)"
            % (
                self._event_id,
                self._act_type,
                self._target_claim_reference,
                self._previous_licence,
                self._new_licence,
            )
        )


def record_derivation_event(
    *,
    input_references,
    output_claim_reference,
    operation_type,
    licence_check_result=None,
    event_id=None,
    reservation=None,
) -> DerivationEvent:

    """Record a derivation event. Ids are minted here, never accepted."""

    if reservation is not None:

        if event_id is not None:

            raise identity_v1.IdentityError(
                "an event may not be recorded with both a reservation and a "
                "client-supplied id"
            )

        resolved_event_id = reservation_v1.consume_reservation(
            reservation, reservation_v1.KIND_DERIVATION_EVENT
        )

    else:

        identity_v1.reject_client_supplied_id(event_id)

        resolved_event_id = identity_v1.new_derivation_event_id()

    return DerivationEvent(
        event_id=resolved_event_id,
        input_references=input_references,
        output_claim_reference=output_claim_reference,
        operation_type=operation_type,
        licence_check_result=licence_check_result,
        _authority=_MINT_AUTHORITY,
    )


def record_endorsement_event(
    *,
    actor,
    target_claim_reference,
    previous_licence,
    new_licence,
    act_type,
    scope,
    ordering,
    event_id=None,
    reservation=None,
) -> EndorsementEvent:

    """Record an endorsement event. Ids are minted here, never accepted."""

    if reservation is not None:

        if event_id is not None:

            raise identity_v1.IdentityError(
                "an event may not be recorded with both a reservation and a "
                "client-supplied id"
            )

        resolved_event_id = reservation_v1.consume_reservation(
            reservation, reservation_v1.KIND_ENDORSEMENT_EVENT
        )

    else:

        identity_v1.reject_client_supplied_id(event_id)

        resolved_event_id = identity_v1.new_endorsement_event_id()

    return EndorsementEvent(
        event_id=resolved_event_id,
        actor=actor,
        target_claim_reference=target_claim_reference,
        previous_licence=previous_licence,
        new_licence=new_licence,
        act_type=act_type,
        scope=scope,
        ordering=ordering,
        _authority=_MINT_AUTHORITY,
    )
