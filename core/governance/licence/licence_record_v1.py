"""LicenceRecord (V1) — permission to use a claim.

Licence means PERMISSION TO USE. It does NOT mean truth, probability or
confidence. No licence state may represent a "non-evidence fact".

The initial vocabulary is closed. Adding a state is a governance change, not a
client action.
"""

from __future__ import annotations


from typing import Any, Dict, Tuple


from core.governance import identity_v1
from core.governance.identity import reservation_v1


CONTRACT = "LicenceRecordV1"

VERSION = "1.0"


LICENCE_STATES = (
    "unlicensed_hypothesis",
    "human_endorsed_hypothesis",
    "candidate_for_learning",
    "generalized_experience",
    "heuristic_candidate",
)


FORBIDDEN_LICENCE_STATES = (
    "fact",
    "observation_fact",
    "non_evidence_fact",
    "truth",
    "probability",
    "confidence",
    "universal_rule",
)


# The vocabulary must never contain a forbidden state. Checked at import time.
assert not set(LICENCE_STATES) & set(FORBIDDEN_LICENCE_STATES), (
    "a licence state may never represent truth or a non-evidence fact"
)


_MINT_AUTHORITY = object()


class LicenceError(ValueError):
    """Raised when a licence cannot be minted, or a state is not permitted."""


class LicenceRecord:

    __slots__ = (
        "_licence_id",
        "_target_claim_reference",
        "_licence_state",
        "_history_reference",
        "_sealed",
    )

    def __init__(
        self,
        *,
        licence_id,
        target_claim_reference,
        licence_state,
        history_reference=(),
        _authority=None,
    ):

        if _authority is not _MINT_AUTHORITY:

            raise LicenceError(
                "LicenceRecord is minted only by governance; use "
                "mint_licence_record()."
            )

        identity_v1.reject_vision_id(licence_id)

        if not identity_v1.is_governance_id(licence_id):

            raise LicenceError(
                "licence_id must be governance-minted: %r" % (licence_id,)
            )

        if licence_state in FORBIDDEN_LICENCE_STATES:

            raise LicenceError(
                "forbidden licence_state %r: licence never means truth, "
                "probability or confidence" % (licence_state,)
            )

        if licence_state not in LICENCE_STATES:

            raise LicenceError(
                "unknown licence_state: %r" % (licence_state,)
            )

        if not str(target_claim_reference or "").strip():

            raise LicenceError("target_claim_reference is required")

        object.__setattr__(self, "_sealed", False)

        object.__setattr__(self, "_licence_id", str(licence_id))

        object.__setattr__(
            self, "_target_claim_reference", str(target_claim_reference)
        )

        object.__setattr__(self, "_licence_state", licence_state)

        object.__setattr__(
            self, "_history_reference", tuple(history_reference or ())
        )

        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name, value):

        if getattr(self, "_sealed", False):

            raise LicenceError(
                "LicenceRecord is immutable: cannot set %r" % (name,)
            )

        object.__setattr__(self, name, value)

    def __delattr__(self, name):

        raise LicenceError(
            "LicenceRecord is immutable: cannot delete %r" % (name,)
        )

    @property
    def licence_id(self):

        return self._licence_id

    @property
    def target_claim_reference(self):

        return self._target_claim_reference

    @property
    def licence_state(self):

        return self._licence_state

    @property
    def history_reference(self):

        return self._history_reference

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "licence_id": self._licence_id,
            "target_claim_reference": self._target_claim_reference,
            "licence_state": self._licence_state,
            "history_reference": list(self._history_reference),
            "means": "permission_to_use",
        }

    def __repr__(self):

        return "LicenceRecord(licence_id=%r, state=%r, target=%r)" % (
            self._licence_id,
            self._licence_state,
            self._target_claim_reference,
        )


def mint_licence_record(
    *,
    target_claim_reference,
    licence_state,
    history_reference=(),
    licence_id=None,
    reservation=None,
) -> LicenceRecord:

    """The ONLY public way to create a LicenceRecord.

    A governance-minted `reservation` (see
    core.governance.identity.reservation_v1) is the only accepted source of
    identity besides governance's own fresh mint.
    """

    if reservation is not None:

        if licence_id is not None:

            raise identity_v1.IdentityError(
                "a licence may not be minted with both a reservation and a "
                "client-supplied id"
            )

        resolved_licence_id = reservation_v1.consume_reservation(
            reservation, reservation_v1.KIND_LICENCE
        )

    else:

        identity_v1.reject_client_supplied_id(licence_id)

        resolved_licence_id = identity_v1.new_licence_id()

    return LicenceRecord(
        licence_id=resolved_licence_id,
        target_claim_reference=target_claim_reference,
        licence_state=licence_state,
        history_reference=history_reference,
        _authority=_MINT_AUTHORITY,
    )
