"""LineageView (V1) — a READ-ONLY derived view.

Lineage is not a source of truth. This view holds no lineage database and
exposes no write path: it indexes the *supplied immutable objects* (claims,
events, references) and computes every answer on demand.

It answers
    "What created this claim?"
    "What claims and events are connected?"

It may expose
    claim_id, parent claims, trigger references, evidence references,
    derivation events, endorsement events

It may NOT
    store independent lineage state, mutate a claim or an event, or assert
    lineage that the supplied objects do not support.

Dependency direction: lineage -> claim / events. Never the reverse.
"""

from __future__ import annotations


from typing import Any, Dict, Iterable, Mapping, Optional, Tuple


from core.governance.lineage.lineage_reference_v1 import (
    LineageReference,
    is_claim_reference,
)


CONTRACT = "LineageViewV1"

VERSION = "1.0"


class LineageViewError(ValueError):
    """Raised when the view is built from an invalid input."""


class LineageView:

    __slots__ = (
        "_claims",
        "_derivations",
        "_endorsements",
        "_references",
        "_sealed",
    )

    def __init__(
        self,
        *,
        claims: Iterable[Any] = (),
        derivation_events: Iterable[Any] = (),
        endorsement_events: Iterable[Any] = (),
        references: Optional[Mapping[str, LineageReference]] = None,
    ):

        claims_index: Dict[str, Any] = {}

        for claim in claims or ():

            claim_id = getattr(claim, "claim_id", None)

            if not claim_id:

                raise LineageViewError(
                    "a claim without claim_id cannot be indexed"
                )

            claims_index[str(claim_id)] = claim

        references_index: Dict[str, LineageReference] = {}

        for claim_id, reference in dict(references or {}).items():

            # Guard against external lineage injection: only a LineageReference
            # value object may be supplied, never an arbitrary payload.
            if not isinstance(reference, LineageReference):

                raise LineageViewError(
                    "references must be LineageReference value objects; "
                    "got %r" % (type(reference).__name__,)
                )

            references_index[str(claim_id)] = reference

        object.__setattr__(self, "_sealed", False)

        object.__setattr__(self, "_claims", claims_index)

        object.__setattr__(
            self, "_derivations", tuple(derivation_events or ())
        )

        object.__setattr__(
            self, "_endorsements", tuple(endorsement_events or ())
        )

        object.__setattr__(self, "_references", references_index)

        object.__setattr__(self, "_sealed", True)

    # --------------------------------------------------
    # read-only guard
    # --------------------------------------------------

    def __setattr__(self, name, value):

        if getattr(self, "_sealed", False):

            raise LineageViewError(
                "LineageView is read-only: cannot set %r" % (name,)
            )

        object.__setattr__(self, name, value)

    def __delattr__(self, name):

        raise LineageViewError(
            "LineageView is read-only: cannot delete %r" % (name,)
        )

    # --------------------------------------------------
    # queries (all derived on demand)
    # --------------------------------------------------

    def exists(self, claim_id) -> bool:

        return str(claim_id or "") in self._claims

    def claim(self, claim_id):

        return self._claims.get(str(claim_id or ""))

    def parents(self, claim_id) -> Tuple[str, ...]:

        """Parent claims, from the supplied reference or the claim itself."""

        key = str(claim_id or "")

        reference = self._references.get(key)

        if reference is not None:

            return reference.parent_claim_references

        claim = self._claims.get(key)

        if claim is None:

            return ()

        return tuple(getattr(claim, "lineage_reference", ()) or ())

    def trigger_references(self, claim_id) -> Tuple[str, ...]:

        reference = self._references.get(str(claim_id or ""))

        return reference.trigger_references if reference else ()

    def evidence_references(self, claim_id) -> Tuple[str, ...]:

        reference = self._references.get(str(claim_id or ""))

        return reference.evidence_references if reference else ()

    def derivation_events(self, claim_id) -> Tuple[Any, ...]:

        """Derivation events whose output is this claim."""

        key = str(claim_id or "")

        return tuple(
            event
            for event in self._derivations
            if str(getattr(event, "output_claim_reference", "")) == key
        )

    def endorsement_events(self, claim_id) -> Tuple[Any, ...]:

        """Endorsement events whose target is this claim."""

        key = str(claim_id or "")

        return tuple(
            event
            for event in self._endorsements
            if str(getattr(event, "target_claim_reference", "")) == key
        )

    # --------------------------------------------------
    # the two questions
    # --------------------------------------------------

    def what_created(self, claim_id) -> Dict[str, Any]:

        """'What created this claim?'"""

        key = str(claim_id or "")

        claim = self._claims.get(key)

        return {
            "contract": CONTRACT,
            "question": "what_created",
            "claim_id": key,
            "exists": claim is not None,
            "creation_event": getattr(claim, "creation_event", None),
            "origin": getattr(claim, "origin", None),
            "source_type": getattr(claim, "source_type", None),
            "parents": list(self.parents(key)),
            "trigger_references": list(self.trigger_references(key)),
            "evidence_references": list(self.evidence_references(key)),
            "derivation_events": [
                event.event_id for event in self.derivation_events(key)
            ],
            "derived": True,
            "read_only": True,
        }

    def connected(self, claim_id) -> Dict[str, Any]:

        """'What claims and events are connected?'"""

        key = str(claim_id or "")

        return {
            "contract": CONTRACT,
            "question": "connected",
            "claim_id": key,
            "exists": key in self._claims,
            "parents": list(self.parents(key)),
            "trigger_references": list(self.trigger_references(key)),
            "evidence_references": list(self.evidence_references(key)),
            "derivation_events": [
                event.event_id for event in self.derivation_events(key)
            ],
            "endorsement_events": [
                event.event_id for event in self.endorsement_events(key)
            ],
            "derived": True,
            "read_only": True,
        }

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "claims_indexed": len(self._claims),
            "derivation_events_indexed": len(self._derivations),
            "endorsement_events_indexed": len(self._endorsements),
            "references_supplied": len(self._references),
            "derived": True,
            "read_only": True,
            "stores_lineage_state": False,
        }

    def __repr__(self):

        return "LineageView(claims=%d, derivations=%d, endorsements=%d)" % (
            len(self._claims),
            len(self._derivations),
            len(self._endorsements),
        )
