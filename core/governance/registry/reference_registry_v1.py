"""ReferenceRegistry (V1) — an append-only, governance-safe reference registry.

The registry STORES references that governance operations returned. It is a
ledger of pointers, never a source of identity.

It
    stores references only
    never creates ids
    never mints identities
    never synthesises claim / licence / event / candidate references
    never changes a governance object
    never decides policy
    never decides truth

Identity ownership remains with identity_v1. This module declares no
`clm_` / `lic_` / `dev_` / `eev_` literal of its own: every identity prefix is
read from identity_v1. Derived references (proposal `prp_`, candidate `kcd_`) are
stored as opaque non-empty references — the ledger does not depend on the intake
or admission boundary that owns those prefixes.

Conflict policy
    Append is the ONLY mutation. A duplicate IDENTICAL entry is deterministic
    (idempotent, not stored twice). A CONFLICTING entry (same claim_reference,
    different content) is NEVER silently written over: it is returned as an
    explicit `conflict` result and the stored entry is left untouched.

Dependency direction

    registry  ->  identity_v1 / claim (scope vocabulary)   ALLOWED
    registry  ->  any client subsystem / runtime / app.py  FORBIDDEN
    anything  ->  registry                                 FORBIDDEN
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple


from core.governance import identity_v1
from core.governance.claim import SCOPES


CONTRACT = "GovernanceReferenceRegistryV1"

VERSION = "1.0"


# ----------------------------------------------------------
# the stored shape
# ----------------------------------------------------------

ENTRY_FIELDS = (
    "claim_reference",
    "proposal_reference",
    "derivation_event_reference",
    "endorsement_event_reference",
    "licence_reference",
    "knowledge_candidate_reference",
    "scope",
)


# A reference registry may NEVER carry authority.
FORBIDDEN_ENTRY_FIELDS = (
    "truth",
    "truth_status",
    "is_true",
    "verified_truth",
    "confidence",
    "confidence_as_truth",
    "certainty",
    "probability",
    "approval",
    "approved",
    "is_approved",
    "fact_status",
    "is_fact",
    "knowledge_status",
    "knowledge_class",
    "licence_state",
    "licence_record",
    "claim",
    "endorsement_event",
    "derivation_event",
)


# ----------------------------------------------------------
# append outcomes
# ----------------------------------------------------------

STATUS_APPENDED = "appended"

STATUS_DUPLICATE = "duplicate_identical"

STATUS_CONFLICT = "conflict"

STATUS_INVALID = "invalid_entry"

STATUS_FORBIDDEN_FIELD = "forbidden_field"


STATUSES = (
    STATUS_APPENDED,
    STATUS_DUPLICATE,
    STATUS_CONFLICT,
    STATUS_INVALID,
    STATUS_FORBIDDEN_FIELD,
)


class ReferenceRegistryError(ValueError):
    """Raised when an entry or a result is malformed."""


def _text(value) -> str:

    return str(value or "").strip()


def _is_derivation_event_reference(value) -> bool:

    return _text(value).startswith(identity_v1.DERIVATION_EVENT_PREFIX)


def _is_endorsement_event_reference(value) -> bool:

    return _text(value).startswith(identity_v1.ENDORSEMENT_EVENT_PREFIX)


@dataclass(frozen=True)
class ReferenceRegistryEntry:

    """An immutable record of the references a governance act produced."""

    claim_reference: str

    proposal_reference: Optional[str] = None

    derivation_event_reference: Optional[str] = None

    endorsement_event_reference: Optional[str] = None

    licence_reference: Optional[str] = None

    knowledge_candidate_reference: Optional[str] = None

    scope: Optional[str] = None

    # An entry points at references. It owns nothing.
    CREATES_IDENTITY = False

    OWNS_REFERENCE = False

    STORES_OBJECTS = False

    DECIDES_TRUTH = False

    def __post_init__(self):

        # normalise so duplicate detection is stable
        for name in ENTRY_FIELDS:

            value = getattr(self, name)

            if isinstance(value, str):

                object.__setattr__(self, name, value.strip() or None)

        if not self.claim_reference:

            raise ReferenceRegistryError("claim_reference is required")

        if not identity_v1.is_claim_reference(self.claim_reference):

            raise ReferenceRegistryError(
                "claim_reference has an unknown identity shape: %r"
                % (self.claim_reference,)
            )

        checks = (
            (
                "derivation_event_reference",
                self.derivation_event_reference,
                _is_derivation_event_reference,
            ),
            (
                "endorsement_event_reference",
                self.endorsement_event_reference,
                _is_endorsement_event_reference,
            ),
            (
                "licence_reference",
                self.licence_reference,
                identity_v1.is_licence_reference,
            ),
        )

        for name, value, predicate in checks:

            if value is None:

                continue

            if not predicate(value):

                raise ReferenceRegistryError(
                    "%s has an unknown identity shape: %r" % (name, value)
                )

        # Derived references (proposal `prp_`, candidate `kcd_`) are owned by the
        # intake / admission boundaries. This ledger deliberately does NOT depend
        # on those boundaries, so it only refuses a GOVERNANCE IDENTITY placed in
        # a derived-reference field.
        for name in ("proposal_reference", "knowledge_candidate_reference"):

            value = getattr(self, name)

            if value is None:

                continue

            if identity_v1.is_governance_id(value):

                raise ReferenceRegistryError(
                    "%s must not carry a governance identity id: %r"
                    % (name, value)
                )

        if self.scope is not None and self.scope not in SCOPES:

            raise ReferenceRegistryError(
                "unknown scope: %r" % (self.scope,)
            )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "claim_reference": self.claim_reference,
            "proposal_reference": self.proposal_reference,
            "derivation_event_reference": self.derivation_event_reference,
            "endorsement_event_reference": self.endorsement_event_reference,
            "licence_reference": self.licence_reference,
            "knowledge_candidate_reference": self.knowledge_candidate_reference,
            "scope": self.scope,
            "creates_identity": False,
            "owns_reference": False,
            "stores_objects": False,
            "decides_truth": False,
        }

    def __repr__(self):

        return "ReferenceRegistryEntry(claim_reference=%r)" % (
            self.claim_reference,
        )


@dataclass(frozen=True)
class RegistryAppendResult:

    """The immutable outcome of an append. A conflict is never silent."""

    appended: bool

    status: str

    reason: str

    entry: Optional[ReferenceRegistryEntry] = None

    def __post_init__(self):

        if self.status not in STATUSES:

            raise ReferenceRegistryError(
                "unknown append status: %r" % (self.status,)
            )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": CONTRACT,
            "appended": self.appended,
            "status": self.status,
            "reason": self.reason,
            "entry": self.entry.to_dict() if self.entry else None,
        }

    def __repr__(self):

        return "RegistryAppendResult(appended=%r, status=%r)" % (
            self.appended,
            self.status,
        )


class ReferenceRegistry:

    """Append-only, in-memory registry of governance references.

    It exposes no delete and no update: append is the ONLY mutation.
    """

    __slots__ = ("_by_claim",)

    CONTRACT = CONTRACT

    VERSION = VERSION

    def __init__(self):

        self._by_claim: Dict[str, ReferenceRegistryEntry] = {}

    # --------------------------------------------------
    # append — the ONLY mutation
    # --------------------------------------------------

    def append(self, entry) -> RegistryAppendResult:

        """Append a reference entry. Never overwrites; returns conflicts."""

        if isinstance(entry, Mapping):

            for key in entry:

                if key in FORBIDDEN_ENTRY_FIELDS:

                    return RegistryAppendResult(
                        False,
                        STATUS_FORBIDDEN_FIELD,
                        "a registry entry may not carry %r" % (key,),
                        None,
                    )

                if key not in ENTRY_FIELDS:

                    return RegistryAppendResult(
                        False,
                        STATUS_INVALID,
                        "unknown registry entry field: %r" % (key,),
                        None,
                    )

            try:

                entry = ReferenceRegistryEntry(**dict(entry))

            except (ReferenceRegistryError, TypeError) as error:

                return RegistryAppendResult(
                    False, STATUS_INVALID, str(error), None
                )

        if not isinstance(entry, ReferenceRegistryEntry):

            return RegistryAppendResult(
                False,
                STATUS_INVALID,
                "a registry entry must be a ReferenceRegistryEntry (or a "
                "mapping); got %r" % (type(entry).__name__,),
                None,
            )

        existing = self._by_claim.get(entry.claim_reference)

        if existing is not None:

            if existing == entry:

                return RegistryAppendResult(
                    False,
                    STATUS_DUPLICATE,
                    "an identical entry is already stored for claim %r"
                    % (entry.claim_reference,),
                    existing,
                )

            return RegistryAppendResult(
                False,
                STATUS_CONFLICT,
                "a different entry already exists for claim %r; it is not "
                "overwritten" % (entry.claim_reference,),
                existing,
            )

        self._by_claim[entry.claim_reference] = entry

        return RegistryAppendResult(
            True, STATUS_APPENDED, "entry appended", entry
        )

    # --------------------------------------------------
    # reads
    # --------------------------------------------------

    def lookup_by_claim(self, claim_reference) -> Optional[ReferenceRegistryEntry]:

        return self._by_claim.get(_text(claim_reference))

    def known_claim_references(self) -> Tuple[str, ...]:

        return tuple(self._by_claim.keys())

    def known_licence_references(self) -> Tuple[str, ...]:

        return tuple(
            entry.licence_reference
            for entry in self._by_claim.values()
            if entry.licence_reference
        )

    def snapshot(self) -> Tuple[ReferenceRegistryEntry, ...]:

        """An immutable view. Later appends do not change it."""

        return tuple(self._by_claim.values())

    def count(self) -> int:

        return len(self._by_claim)

    def __len__(self):

        return len(self._by_claim)

    def __repr__(self):

        return "ReferenceRegistry(entries=%d, append_only=True)" % (
            len(self._by_claim),
        )
