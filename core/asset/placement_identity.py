"""Pure placement identity helper (Phase 3D-AH.1).

Derives ONE deterministic identity per furniture PLACEMENT - distinct from the
3D-FUTURE ``model_id`` (asset MODEL identity) and from the DiffuScene ``slot``
(source OBJECT metadata).

This module is pure and deliberately does NOT:

- read the filesystem
- use randomness, UUIDs, timestamps or a global counter
- hash geometry, positions or floats
- look up the asset registry or any model
- touch vertices, transforms or matrices

The identity is a plain deterministic string::

    <placement_scope>:placement:<ordinal six digits>

``placement_scope`` is a caller-supplied machine-safe token (the "which scene /
session" part), and ``ordinal`` is the zero-based index of the source item
within that scope. ``model_id`` is deliberately NOT part of the identity.
"""

from __future__ import annotations

import re


PLACEMENT_IDENTITY_STATUSES = ("resolved", "unresolved")
PLACEMENT_IDENTITY_RESOLVED = "resolved"
PLACEMENT_IDENTITY_UNRESOLVED = "unresolved"

REASON_SCOPE_MISSING = "placement_scope_missing"

ORDINAL_DIGITS = 6

# Conservative, machine-safe scope contract.
_SCOPE_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_placement_scope(placement_scope):
    """Return the scope unchanged, or raise. ``None`` is allowed."""

    if placement_scope is None:
        return None
    if isinstance(placement_scope, bool) or not isinstance(placement_scope, str):
        raise ValueError("placement_scope must be a non-empty string or None")
    if not placement_scope.strip():
        raise ValueError("placement_scope must not be whitespace-only")
    if _SCOPE_PATTERN.match(placement_scope) is None:
        raise ValueError(
            "placement_scope must contain only A-Z, a-z, 0-9, '.', '_' or '-'"
        )

    return placement_scope


def validate_ordinal(ordinal):
    if isinstance(ordinal, bool) or not isinstance(ordinal, int):
        raise ValueError("ordinal must be a non-negative integer")
    if ordinal < 0:
        raise ValueError("ordinal must be a non-negative integer")

    return ordinal


def format_placement_instance_id(placement_scope, ordinal):
    """Format ``<scope>:placement:<ordinal six digits>``."""

    scope = validate_placement_scope(placement_scope)
    if scope is None:
        raise ValueError(
            "placement_scope is required to format a placement identity"
        )
    ordinal = validate_ordinal(ordinal)

    return f"{scope}:placement:{ordinal:0{ORDINAL_DIGITS}d}"


def _validate_source_engine(source_engine):
    if source_engine is None:
        return None
    if not isinstance(source_engine, str) or not source_engine.strip():
        raise ValueError("source_engine must be a non-empty string or None")

    return source_engine


def build_placement_identity(
    *,
    placement_scope,
    ordinal,
    source_engine,
    source_slot=None,
):
    """Build one deterministic placement identity block.

    ``source_slot`` is PROVENANCE only: it never participates in the identity,
    so duplicate source slots still yield distinct identities because the
    ordinal differs.
    """

    ordinal = validate_ordinal(ordinal)
    scope = validate_placement_scope(placement_scope)
    engine = _validate_source_engine(source_engine)

    if scope is None:
        return {
            "status": PLACEMENT_IDENTITY_UNRESOLVED,
            "scope": None,
            "ordinal": ordinal,
            "source_engine": engine,
            "source_slot": source_slot,
            "instance_id": None,
            "reasons": [REASON_SCOPE_MISSING],
        }

    return {
        "status": PLACEMENT_IDENTITY_RESOLVED,
        "scope": scope,
        "ordinal": ordinal,
        "source_engine": engine,
        "source_slot": source_slot,
        "instance_id": format_placement_instance_id(scope, ordinal),
    }
