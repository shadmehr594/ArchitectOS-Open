"""Lineage domain of the Claim Governance substrate (V1).

Lineage is a DERIVED VIEW, never an independent source of truth.

    sources   claim immediate references, derivation events, endorsement events
    product   a read-only view computed on demand

There is no mutable lineage database and no second graph authority.

Dependency direction (one-way, inside governance only):

    lineage  ->  claim / events / identity      ALLOWED
    claim / events  ->  lineage                 FORBIDDEN
    lineage  ->  any client subsystem           FORBIDDEN
"""

from __future__ import annotations


from core.governance.lineage.dag_safety_v1 import (
    DagCheckReport,
    DagViolation,
    check_dag,
)
from core.governance.lineage.lineage_reference_v1 import (
    REFERENCE_KINDS,
    LineageReference,
    LineageReferenceError,
    build_lineage_reference,
)
from core.governance.lineage.lineage_view_v1 import (
    LineageView,
    LineageViewError,
)


__all__ = (
    "LineageReference",
    "build_lineage_reference",
    "LineageReferenceError",
    "REFERENCE_KINDS",
    "LineageView",
    "LineageViewError",
    "check_dag",
    "DagCheckReport",
    "DagViolation",
)
