"""Read models of the Claim Governance substrate (V1).

A read model ANSWERS a question about governance artefacts. It is a leaf: it
imports governance areas, and nothing inside governance imports it. It never
creates, mints, mutates or assigns anything, and it never imports a client.

    resolve_licence_state(claim_reference, ...) -> LicenceStateView

Dependency direction

    accessors  ->  licence / lineage      ALLOWED
    accessors  ->  any client subsystem   FORBIDDEN
"""

from __future__ import annotations


from core.governance.accessors.licence_state_accessor_v1 import (
    CONTRACT,
    REASONS,
    REASON_CONFLICT,
    REASON_FROM_EVENT,
    REASON_FROM_RECORD,
    REASON_INVALID_CLAIM,
    REASON_MISSING_CLAIM,
    REASON_MISSING_LICENCE,
    REASON_UNRESOLVED_CLAIM,
    SOURCE_EVENT,
    SOURCE_RECORD,
    LicenceStateView,
    LicenceStateViewError,
    VERSION,
    resolve_licence_state,
)


__all__ = (
    "LicenceStateView",
    "resolve_licence_state",
    "LicenceStateViewError",
    "REASONS",
    "REASON_MISSING_CLAIM",
    "REASON_INVALID_CLAIM",
    "REASON_UNRESOLVED_CLAIM",
    "REASON_MISSING_LICENCE",
    "REASON_FROM_RECORD",
    "REASON_FROM_EVENT",
    "REASON_CONFLICT",
    "SOURCE_RECORD",
    "SOURCE_EVENT",
    "CONTRACT",
    "VERSION",
)
