"""Governance-owned identity minting (V1).

INVARIANTS
    * identity is minted ONLY here;
    * a client-supplied id is never accepted;
    * a vision-derived id (`au2_claim_NNN`) is never accepted or migrated;
    * the identity registry is IMMUTABLE (a read-only mapping proxy).

SINGLE SOURCE OF TRUTH for governance reference prefixes. Every other module
imports these constants and predicates instead of re-declaring a literal such
as "clm_" or "lic_".

Boundary clarification: BOUNDARY CLARIFICATION AUDIT V1, Decision 1 (option B)
— `au2_claim_NNN` is a projection-local label and is discarded at mint time.

No import of any client subsystem.
"""

from __future__ import annotations


import types
import uuid


CONTRACT = "GovernanceIdentityV1"

VERSION = "1.0"


# ----------------------------------------------------------
# canonical reference prefixes — the ONLY place these literals live
# ----------------------------------------------------------

CLAIM_REFERENCE_PREFIX = "clm_"

LICENCE_REFERENCE_PREFIX = "lic_"

DERIVATION_EVENT_PREFIX = "dev_"

ENDORSEMENT_EVENT_PREFIX = "eev_"


# The identity registry is IMMUTABLE. A mapping proxy rejects any item
# assignment, so a caller can never re-point a kind to a different prefix.
_ID_KINDS = types.MappingProxyType(
    {
        "claim": CLAIM_REFERENCE_PREFIX,
        "licence": LICENCE_REFERENCE_PREFIX,
        "derivation_event": DERIVATION_EVENT_PREFIX,
        "endorsement_event": ENDORSEMENT_EVENT_PREFIX,
    }
)


# Every governance-minted id prefix (claim, licence, event).
GOVERNANCE_ID_PREFIXES = (
    CLAIM_REFERENCE_PREFIX,
    LICENCE_REFERENCE_PREFIX,
    DERIVATION_EVENT_PREFIX,
    ENDORSEMENT_EVENT_PREFIX,
)


# Lineage-eligible references. A licence is NOT a lineage node, so `lic_` is
# deliberately excluded from this set.
LINEAGE_REFERENCE_PREFIXES = (
    CLAIM_REFERENCE_PREFIX,
    DERIVATION_EVENT_PREFIX,
    ENDORSEMENT_EVENT_PREFIX,
)


_ID_HEX_LENGTH = 16


# Minted inside core/vision/architectural_understanding_v2.py. Governance must
# never adopt these as claim identity.
VISION_ID_PREFIXES = ("au2_",)


class IdentityError(ValueError):
    """Raised when an id cannot be minted, or is illegally supplied."""


def mint_id(kind):

    prefix = _ID_KINDS.get(str(kind or ""))

    if not prefix:

        raise IdentityError("unknown identity kind: %r" % (kind,))

    return prefix + uuid.uuid4().hex[:_ID_HEX_LENGTH]


def new_claim_id():

    return mint_id("claim")


def new_licence_id():

    return mint_id("licence")


def new_derivation_event_id():

    return mint_id("derivation_event")


def new_endorsement_event_id():

    return mint_id("endorsement_event")


# ----------------------------------------------------------
# reference shape predicates — SHAPE only, never existence
# ----------------------------------------------------------

def _starts_with_any(value, prefixes) -> bool:

    text = str(value or "")

    return any(text.startswith(prefix) for prefix in prefixes)


def is_claim_reference(value) -> bool:

    """True when the value is `clm_`-shaped. Shape only, no existence check."""

    return str(value or "").startswith(CLAIM_REFERENCE_PREFIX)


def is_licence_reference(value) -> bool:

    """True when the value is `lic_`-shaped. Shape only, no existence check."""

    return str(value or "").startswith(LICENCE_REFERENCE_PREFIX)


def is_event_reference(value) -> bool:

    """True when the value is a `dev_`/`eev_`-shaped event reference."""

    return _starts_with_any(
        value, (DERIVATION_EVENT_PREFIX, ENDORSEMENT_EVENT_PREFIX)
    )


def is_governance_id(value) -> bool:

    """True for any governance-minted id (claim, licence or event)."""

    return _starts_with_any(value, GOVERNANCE_ID_PREFIXES)


def is_lineage_reference(value) -> bool:

    """True for a lineage-eligible reference. A licence is NOT one."""

    return _starts_with_any(value, LINEAGE_REFERENCE_PREFIXES)


def reject_client_supplied_id(value):

    """Factories accept `<id>=None` only so that supplying one raises."""

    if value is None:

        return

    raise IdentityError(
        "identity is minted only by governance; a client-supplied id "
        "is not accepted: %r" % (value,)
    )


def reject_vision_id(value):

    text = str(value or "")

    if any(text.startswith(prefix) for prefix in VISION_ID_PREFIXES):

        raise IdentityError(
            "a vision-derived id must never enter governance: %r" % (value,)
        )
