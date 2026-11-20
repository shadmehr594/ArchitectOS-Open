"""Reference registry of the Claim Governance substrate (V1).

An append-only, governance-safe ledger of the references that governance
operations RETURNED. It stores references only — it never creates an id, never
mints an identity, never synthesises a reference, never mutates a governance
object, and never decides policy or truth.

    ReferenceRegistry()          an empty registry
    append(entry)                the ONLY mutation (returns conflicts explicitly)
    lookup_by_claim(...)         the stored entry for a claim
    known_claim_references()     the stored claim references
    known_licence_references()   the stored licence references
    snapshot()                   an immutable view

Identity ownership remains with identity_v1.

Dependency direction

    registry  ->  identity_v1 / claim (scope vocabulary)     ALLOWED
    registry  ->  any client subsystem / runtime / app.py    FORBIDDEN
    anything  ->  registry                                   FORBIDDEN
"""

from __future__ import annotations


from core.governance.registry.reference_registry_v1 import (
    CONTRACT,
    ENTRY_FIELDS,
    FORBIDDEN_ENTRY_FIELDS,
    ReferenceRegistry,
    ReferenceRegistryEntry,
    ReferenceRegistryError,
    RegistryAppendResult,
    STATUS_APPENDED,
    STATUS_CONFLICT,
    STATUS_DUPLICATE,
    STATUS_FORBIDDEN_FIELD,
    STATUS_INVALID,
    STATUSES,
    VERSION,
)


__all__ = (
    "ReferenceRegistry",
    "ReferenceRegistryEntry",
    "RegistryAppendResult",
    "ReferenceRegistryError",
    "ENTRY_FIELDS",
    "FORBIDDEN_ENTRY_FIELDS",
    "STATUSES",
    "STATUS_APPENDED",
    "STATUS_DUPLICATE",
    "STATUS_CONFLICT",
    "STATUS_INVALID",
    "STATUS_FORBIDDEN_FIELD",
    "CONTRACT",
    "VERSION",
)
