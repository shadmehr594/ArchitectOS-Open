"""Unified Architectural Spatial Contract v1 (ARCH-SITE-04).

A NORMALISATION LAYER between the three architectural reasoning producers:

    KnowledgeSpaceGenerator  -> generated_spaces / generated_site_spaces
    LayoutReasoner           -> space_registry / external_spaces
    ExternalSpaceReasoner    -> the derived external site profile

Those producers emit related but divergent space dictionaries (see the audit in
the phase report: 18 / 18 / 21 / 15 / 8 keys respectively, with 10 fields
duplicated between the site generator and the external reasoner and no shared
``domain`` or ``geometry_status`` field at all).

This module maps any of those records into ONE canonical shape WITHOUT
rewriting the producers:

    identity          name, canonical_name
    domain            "building" | "site"
    vertical          floor
    placement         placement_domain
    semantic          space_type, role, architectural_intent
    relationships     connections
    geometry_status   {state: pending|resolved, reason}
    metadata          every remaining authoritative field, verbatim

This module is a PURE ADAPTER. It deliberately does NOT:

- create, move or infer geometry, coordinates, polygons, elevations or placement
- authorise geometry (``geometry_status`` defaults to ``pending``)
- place a site space in a floor layout, or turn it into a room
- modify, replace or wrap the APIs of the three producers
- read the filesystem, use randomness, UUIDs or timestamps
- mutate its input (every block is newly built)

GEOMETRY READINESS
------------------
``geometry_status`` is a DECLARATION, not a measurement. It defaults to
``{"state": "pending", "reason": "geometry_not_authorized"}`` because this
phase creates no geometry. A source record may carry its own well-formed
``geometry_status`` mapping, in which case it is validated and carried through;
nothing is ever upgraded to ``resolved`` here.
"""

from __future__ import annotations

from typing import Any, Mapping


CONTRACT_TYPE = "architectural_spatial_contract"
CONTRACT_VERSION = "architectural_spatial_contract_v1"

DOMAIN_BUILDING = "building"
DOMAIN_SITE = "site"
DOMAINS = (DOMAIN_BUILDING, DOMAIN_SITE)

SITE_FLOOR = "site_level"
SITE_PLACEMENT_DOMAIN = "site"

GEOMETRY_STATE_PENDING = "pending"
GEOMETRY_STATE_RESOLVED = "resolved"
GEOMETRY_STATES = (GEOMETRY_STATE_PENDING, GEOMETRY_STATE_RESOLVED)

STATE_RESOLVED = "spatial_contract_resolved"
STATE_UNRESOLVED = "spatial_contract_unresolved"

# Keys promoted into named blocks; everything else is preserved in ``metadata``.
_PROMOTED_KEYS = frozenset(
    {
        "name",
        "canonical_name",
        "floor",
        "placement_domain",
        "space_type",
        "role",
        "architectural_intent",
        "geometry_status",
    }
)

DEFAULT_GEOMETRY_REASON = "geometry_not_authorized"


# ---------------------------------------------------------------------------
# validation helpers
# ---------------------------------------------------------------------------

def _non_empty_string(value, label):
    if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")

    return value


def _optional_string(value, label):
    if value is None:
        return None

    return _non_empty_string(value, label)


def _mapping_copy(value, label):
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")

    return dict(value)


# ---------------------------------------------------------------------------
# domain resolution
# ---------------------------------------------------------------------------

def resolve_spatial_domain(space):
    """Return ``"site"`` or ``"building"`` from the space's own semantics.

    Site-ness is data-driven on the authoritative semantic fields, never on the
    space name:

        placement_domain == "site"   (preferred)
        floor            == "site_level"
    """

    if not isinstance(space, Mapping):
        raise ValueError("space must be a mapping")

    if space.get("placement_domain") == SITE_PLACEMENT_DOMAIN:
        return DOMAIN_SITE

    if space.get("floor") == SITE_FLOOR:
        return DOMAIN_SITE

    return DOMAIN_BUILDING


def _geometry_status(space, domain):
    """Validate a declared geometry status, else declare it pending."""

    declared = space.get("geometry_status")

    if declared is None:
        reason = DEFAULT_GEOMETRY_REASON
        if domain == DOMAIN_SITE:
            reason = "site_geometry_not_authorized"

        return {"state": GEOMETRY_STATE_PENDING, "reason": reason}

    if not isinstance(declared, Mapping):
        raise ValueError("space geometry_status must be a mapping")

    state = declared.get("state")
    if isinstance(state, bool) or state not in GEOMETRY_STATES:
        raise ValueError(
            "space geometry_status.state must be one of: "
            + ", ".join(GEOMETRY_STATES)
        )

    reason = declared.get("reason")
    if reason is not None and (
        isinstance(reason, bool) or not isinstance(reason, str)
    ):
        raise ValueError("space geometry_status.reason must be a string or None")

    return {"state": state, "reason": reason}


def _connections_for(space, connections):
    """Filter a relationship list down to the connections touching ``space``.

    Matching is by ``name`` or ``canonical_name``, case-insensitively. The
    relationship records are copied verbatim.
    """

    if connections is None:
        return []

    if isinstance(connections, (str, bytes)) or not isinstance(
        connections, (list, tuple)
    ):
        raise ValueError("connections must be a list of mappings or None")

    identities = {
        str(value).lower()
        for value in (space.get("name"), space.get("canonical_name"))
        if value
    }

    selected = []
    for connection in connections:
        if not isinstance(connection, Mapping):
            continue

        endpoints = {
            str(connection.get("from", "")).lower(),
            str(connection.get("to", "")).lower(),
        }

        if identities & endpoints:
            selected.append(dict(connection))

    return selected


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def build_architectural_spatial_contract(space, *, connections=None):
    """Normalise ONE producer space record into the unified spatial contract.

    ``space`` may come from any of the three producers. ``connections`` is an
    OPTIONAL relationship list (for example ``LayoutReasoner``'s ``connections``
    output); the subset touching this space is carried in
    ``relationships.connections``.

    Pure function: no geometry, no coordinates, no filesystem, and the input is
    never mutated. Malformed input raises ``ValueError``.
    """

    if not isinstance(space, Mapping):
        raise ValueError("space must be a mapping")
    if not space:
        raise ValueError("space must not be empty")

    name = _non_empty_string(space.get("name"), "space name")

    reasons = []
    canonical_name = _optional_string(
        space.get("canonical_name"), "space canonical_name"
    )
    if canonical_name is None:
        # This adapter NORMALISES, it does not canonicalise: canonicalisation is
        # owned by SpaceIdentityMapper. Falling back is recorded, not silent.
        canonical_name = name
        reasons.append("canonical_name_not_supplied_fell_back_to_name")

    domain = resolve_spatial_domain(space)

    floor = _optional_string(space.get("floor"), "space floor")
    if domain == DOMAIN_SITE:
        if floor is None:
            floor = SITE_FLOOR
            reasons.append("site_floor_asserted_from_domain")
        elif floor != SITE_FLOOR:
            # A site domain with a building floor is a contradictory record.
            # Fail closed rather than emit a contract that says site+ground_floor.
            raise ValueError(
                "a site space must declare floor "
                f"{SITE_FLOOR!r}; got {floor!r} - site and building "
                "semantics conflict"
            )

    placement_domain = space.get("placement_domain")
    if placement_domain is None:
        placement_domain = domain
    else:
        placement_domain = _non_empty_string(
            placement_domain, "space placement_domain"
        )
        if placement_domain not in DOMAINS:
            raise ValueError(
                "space placement_domain must be one of: " + ", ".join(DOMAINS)
            )
        if placement_domain != domain:
            raise ValueError(
                "space placement_domain conflicts with its resolved domain: "
                f"{placement_domain!r} != {domain!r}"
            )

    metadata = {
        key: value for key, value in space.items() if key not in _PROMOTED_KEYS
    }

    contract = {
        "type": CONTRACT_TYPE,
        "version": CONTRACT_VERSION,
        "identity": {"name": name, "canonical_name": canonical_name},
        "domain": domain,
        "vertical": {"floor": floor, "floor_domain": domain},
        "placement": {"placement_domain": placement_domain},
        "semantic": {
            "space_type": space.get("space_type"),
            "role": space.get("role"),
            "architectural_intent": _mapping_copy(
                space.get("architectural_intent"),
                "space architectural_intent",
            ),
        },
        "relationships": {"connections": _connections_for(space, connections)},
        "geometry_status": _geometry_status(space, domain),
        "metadata": metadata,
        "status": {
            "state": STATE_RESOLVED,
            "reasons": reasons,
        },
    }

    return contract


def normalize_spatial_contracts(spaces, *, connections=None):
    """Normalise a sequence of producer space records, order preserved."""

    if isinstance(spaces, (str, bytes)) or not isinstance(spaces, (list, tuple)):
        raise ValueError("spaces must be a list of mappings")

    return [
        build_architectural_spatial_contract(space, connections=connections)
        for space in spaces
    ]


def split_contracts_by_domain(contracts):
    """Partition normalised contracts into the building and site domains.

    Site spaces are NEVER placed in the building bucket, so a caller cannot
    accidentally treat a site space as a room.
    """

    if isinstance(contracts, (str, bytes)) or not isinstance(
        contracts, (list, tuple)
    ):
        raise ValueError("contracts must be a list of mappings")

    building = []
    site = []
    for contract in contracts:
        domain = contract.get("domain")
        if domain == DOMAIN_SITE:
            site.append(contract)
        elif domain == DOMAIN_BUILDING:
            building.append(contract)
        else:
            raise ValueError(
                "contract domain must be one of: " + ", ".join(DOMAINS)
            )

    return {"building": building, "site": site}
