"""ArchitectOS — Geometry Generation Boundary Contract v1.

ARCH-GEOMETRY-04: the STRICT BOUNDARY between

    Architectural Geometry Intent              (the semantic layer)
                    |
                    |  <-- THIS CONTRACT -->
                    |
    Future Geometry Generation Engine          (the geometric layer)

WHAT THIS MODULE IS
-------------------
A contract that states, per semantic unit, WHAT a future geometry generation
engine would be permitted to do, WHAT semantic evidence it must first hold,
and WHAT it is FORBIDDEN to resolve. It is the machine-readable seam between
the two layers, so the hand-off is explicit instead of accidental.

WHAT THIS MODULE IS NOT
-----------------------
It generates NOTHING:

- no geometry, no coordinate, no x/y/z, no width/depth/height/thickness,
  no area, no volume, no polygon, no mesh, no CAD, no IFC;
- it does not create, cut, extrude, sweep or tessellate anything;
- it does not resolve any pending decision;
- it does not wire the semantic bridges into the live pipeline.

Every generation request it emits carries ``geometry_status: pending`` - the
boundary contract AUTHORIZES NOTHING BY ITSELF. It describes the gate; it does
not open it.

THE THREE-TIER AUTHORIZATION MODEL
----------------------------------
``geometry_status`` is the single source of authorization in the semantic
layer. This contract formalizes three states on a THIRD domain axis:

    SPACE axis          : building / site
    CIRCULATION axis    : residential / commercial / mixed_use / site
    AUTHORIZATION axis  : pending / authorized / forbidden      <-- this phase

``authorized`` is NEVER emitted by this module. No unit can be authorized
without an external grant that does not exist yet, so every request stays
``pending`` (or ``forbidden`` where a prerequisite is structurally absent).
Fail-closed: absence of evidence is never an authorization.

THE LEGACY LAYER IS NAMED, NOT MODIFIED
---------------------------------------
A live, legacy geometric chain already exists and is authoritative today:

    reasoning/architectural_geometry_intent_generator_v1   (misnamed: resolves
                                                            real metric values)
              |
    geometry/architectural_geometry_engine_v2              (real geometry,
                                                            coordinates,
                                                            thicknesses)
              |
    bim/architectural_to_bim_element_bridge_v1
              |
    bim/architectural_ifc_exporter_v2                       -> ifcopenshell

Every generation request therefore carries ``legacy_layer_reference``, naming
the existing module that currently owns that concern. This module does not
import, invoke, modify or replace any of them. Naming the migration surface is
the point; performing the migration is a separate, deliberate phase.

Pure function. No filesystem, no randomness, no mutation of any input.
Malformed input raises ``ValueError``.
"""

from __future__ import annotations

from typing import Any, Mapping


OUTPUT_TYPE = "geometry_generation_boundary"
OUTPUT_VERSION = "geometry_generation_boundary_contract_v1"

# ---------------------------------------------------------------------------
# the two sides of the boundary
# ---------------------------------------------------------------------------

SIDE_SEMANTIC = "semantic_side"
SIDE_GENERATION = "generation_side"
BOUNDARY_SIDES = (SIDE_SEMANTIC, SIDE_GENERATION)

# ---------------------------------------------------------------------------
# the THIRD domain axis - authorization
# ---------------------------------------------------------------------------

DOMAIN_AXIS_AUTHORIZATION = "authorization"

AUTHORIZATION_PENDING = "pending"
AUTHORIZATION_FORBIDDEN = "forbidden"
AUTHORIZATION_AUTHORIZED = "authorized"

AUTHORIZATION_STATES = (
    AUTHORIZATION_PENDING,
    AUTHORIZATION_FORBIDDEN,
    AUTHORIZATION_AUTHORIZED,
)

#: States this module is permitted to emit. ``authorized`` is deliberately
#: absent: the boundary contract can withhold, never grant.
EMITTABLE_AUTHORIZATION_STATES = (
    AUTHORIZATION_PENDING,
    AUTHORIZATION_FORBIDDEN,
)

# ---------------------------------------------------------------------------
# generation request types - the semantic name of a future geometric artifact.
# These are TOKENS, not dimensions. Nothing here implies a size or a shape.
# ---------------------------------------------------------------------------

REQUEST_SPACE_VOLUME = "space_volume_request"
REQUEST_ENVELOPE_WALL_SOLID = "envelope_wall_solid_request"
REQUEST_PARTITION_WALL_SOLID = "partition_wall_solid_request"
REQUEST_SEPARATING_WALL_SOLID = "separating_wall_solid_request"
REQUEST_CORE_WALL_SOLID = "core_wall_solid_request"
REQUEST_SITE_BOUNDARY_WALL_SOLID = "site_boundary_wall_solid_request"
REQUEST_FLOOR_SLAB_SOLID = "floor_slab_solid_request"
REQUEST_ROOF_SLAB_SOLID = "roof_slab_solid_request"
REQUEST_BASEMENT_SLAB_SOLID = "basement_slab_solid_request"
REQUEST_SITE_SURFACE = "site_surface_request"
REQUEST_SLAB_PENETRATION = "slab_penetration_request"
REQUEST_GLAZING_OPENING = "glazing_opening_request"
REQUEST_EXTERNAL_ACCESS_OPENING = "external_access_opening_request"
REQUEST_INTERNAL_DOORWAY_OPENING = "internal_doorway_opening_request"
REQUEST_VERTICAL_ACCESS_OPENING = "vertical_access_opening_request"
REQUEST_VEHICLE_ACCESS_OPENING = "vehicle_access_opening_request"
REQUEST_VERTICAL_CORE_SOLID = "vertical_core_solid_request"
REQUEST_STAIR_FLIGHT = "stair_flight_request"
REQUEST_ROOF_FORM = "roof_form_request"

REQUEST_TYPES = (
    REQUEST_SPACE_VOLUME,
    REQUEST_ENVELOPE_WALL_SOLID,
    REQUEST_PARTITION_WALL_SOLID,
    REQUEST_SEPARATING_WALL_SOLID,
    REQUEST_CORE_WALL_SOLID,
    REQUEST_SITE_BOUNDARY_WALL_SOLID,
    REQUEST_FLOOR_SLAB_SOLID,
    REQUEST_ROOF_SLAB_SOLID,
    REQUEST_BASEMENT_SLAB_SOLID,
    REQUEST_SITE_SURFACE,
    REQUEST_SLAB_PENETRATION,
    REQUEST_GLAZING_OPENING,
    REQUEST_EXTERNAL_ACCESS_OPENING,
    REQUEST_INTERNAL_DOORWAY_OPENING,
    REQUEST_VERTICAL_ACCESS_OPENING,
    REQUEST_VEHICLE_ACCESS_OPENING,
    REQUEST_VERTICAL_CORE_SOLID,
    REQUEST_STAIR_FLIGHT,
    REQUEST_ROOF_FORM,
)

# ---------------------------------------------------------------------------
# vocabulary inherited from the semantic layer - REUSED, never re-invented.
# ---------------------------------------------------------------------------

DOMAIN_AXIS_SPACE = "space"
DOMAIN_AXIS_CIRCULATION = "circulation"

DOMAIN_BUILDING = "building"
DOMAIN_SITE = "site"
SPACE_DOMAINS = (DOMAIN_BUILDING, DOMAIN_SITE)

NODE_BUILDING_SPACE = "building_space"
NODE_SITE_SPACE = "site_space"
NODE_VERTICAL_ELEMENT = "vertical_element"

BOUNDARY_ENVELOPE = "envelope_boundary"
BOUNDARY_INTERNAL = "internal_boundary"
BOUNDARY_CORE = "core_interface"
BOUNDARY_SITE_UNRESOLVED = "site_boundary_unresolved"
BOUNDARY_SITE_OPEN = "site_open_boundary"
BOUNDARY_TYPES = (
    BOUNDARY_ENVELOPE,
    BOUNDARY_INTERNAL,
    BOUNDARY_CORE,
    BOUNDARY_SITE_UNRESOLVED,
    BOUNDARY_SITE_OPEN,
)

OPENING_GLAZING = "glazing_intent"
OPENING_EXTERNAL_ACCESS = "external_access_intent"
OPENING_INTERNAL_DOORWAY = "internal_doorway_intent"
OPENING_VERTICAL_ACCESS = "vertical_access_intent"
OPENING_VEHICLE_ACCESS = "vehicle_access_intent"
OPENING_ROLES = (
    OPENING_GLAZING,
    OPENING_EXTERNAL_ACCESS,
    OPENING_INTERNAL_DOORWAY,
    OPENING_VERTICAL_ACCESS,
    OPENING_VEHICLE_ACCESS,
)

WALL_ENVELOPE = "envelope_wall_intent"
WALL_SEPARATING = "separating_wall_intent"
WALL_PARTITION = "internal_partition_intent"
WALL_CORE_ENCLOSURE = "core_enclosure_intent"
WALL_SITE_BOUNDARY = "site_boundary_wall_intent"
WALL_INTENT_TYPES = (
    WALL_ENVELOPE,
    WALL_SEPARATING,
    WALL_PARTITION,
    WALL_CORE_ENCLOSURE,
    WALL_SITE_BOUNDARY,
)

FLOOR_SURFACE = "floor_surface_intent"
FLOOR_ROOF_SURFACE = "roof_surface_intent"
FLOOR_BASEMENT_SURFACE = "basement_surface_intent"
FLOOR_SITE_SURFACE = "site_surface_intent"
FLOOR_INTENT_TYPES = (
    FLOOR_SURFACE,
    FLOOR_ROOF_SURFACE,
    FLOOR_BASEMENT_SURFACE,
    FLOOR_SITE_SURFACE,
)

ROOF_ROLE_OCCUPIABLE_TERRACE = "occupiable_roof_terrace"
ROOF_ROLE_TOP_TERMINATION = "top_termination_of_the_envelope"
ROOF_ROLE_SUPERSTRUCTURE = "roof_superstructure_level"
ROOF_ROLE_SITE_LEVEL = "site_level_surface"
ROOF_ROLES = (
    ROOF_ROLE_OCCUPIABLE_TERRACE,
    ROOF_ROLE_TOP_TERMINATION,
    ROOF_ROLE_SUPERSTRUCTURE,
    ROOF_ROLE_SITE_LEVEL,
)

FLOOR_INTERRUPTION_REQUIRED = "floor_penetration_required"

# ---------------------------------------------------------------------------
# geometry status - the semantic layer's authorization token
# ---------------------------------------------------------------------------

GEOMETRY_STATE_PENDING = "pending"
GEOMETRY_STATE_AUTHORIZED = "authorized"
GEOMETRY_STATES = (GEOMETRY_STATE_PENDING, GEOMETRY_STATE_AUTHORIZED)

#: The exact reason string the three semantic bridges stamp. It is the reason
#: the boundary contract must echo, so a consumer can trace the gate back.
GEOMETRY_REASON_NOT_AUTHORIZED = "geometry_generation_not_authorized"

# ---------------------------------------------------------------------------
# prerequisite vocabulary - what an engine must first HOLD
# ---------------------------------------------------------------------------

PREREQ_SPACE_CONTAINMENT = "space_containment_resolved"
PREREQ_DOMAIN_SEPARATION = "domain_separation_decided"
PREREQ_BOUNDARY_TYPE = "boundary_type_resolved"
PREREQ_ENVELOPE_CONTINUITY = "envelope_continuity_decided"
PREREQ_OPENING_ROLE = "opening_role_resolved"
PREREQ_PROTECTED_ZONE = "protected_zone_resolved"
PREREQ_LEVEL_ORDER = "level_order_resolved"
PREREQ_ROOF_ROLE = "roof_role_resolved"
PREREQ_TERRACE_RELATIONSHIP = "terrace_relationship_evidenced"
PREREQ_VEHICLE_ACCESS_MODE = "vehicle_access_mode_decided"
PREREQ_VERTICAL_SERVED_LEVELS = "vertical_served_levels_resolved"
PREREQ_THICKNESS_POLICY = "thickness_policy_authorized"
PREREQ_FACADE_APPROVAL = "facade_approval_granted"

PREREQUISITES = (
    PREREQ_SPACE_CONTAINMENT,
    PREREQ_DOMAIN_SEPARATION,
    PREREQ_BOUNDARY_TYPE,
    PREREQ_ENVELOPE_CONTINUITY,
    PREREQ_OPENING_ROLE,
    PREREQ_PROTECTED_ZONE,
    PREREQ_LEVEL_ORDER,
    PREREQ_ROOF_ROLE,
    PREREQ_TERRACE_RELATIONSHIP,
    PREREQ_VEHICLE_ACCESS_MODE,
    PREREQ_VERTICAL_SERVED_LEVELS,
    PREREQ_THICKNESS_POLICY,
    PREREQ_FACADE_APPROVAL,
)

#: Prerequisites that cannot be evidenced in this phase, because the authority
#: that would grant them does not exist yet. Declaring them is not the same as
#: holding them, so a unit requiring one of these is ALWAYS blocked - it must
#: never be reported as ready.
UNSATISFIABLE_PREREQUISITES = frozenset(
    (
        PREREQ_THICKNESS_POLICY,
        PREREQ_FACADE_APPROVAL,
        PREREQ_VEHICLE_ACCESS_MODE,
        PREREQ_ENVELOPE_CONTINUITY,
        PREREQ_TERRACE_RELATIONSHIP,
        PREREQ_DOMAIN_SEPARATION,
    )
)

# ---------------------------------------------------------------------------
# forbidden resolutions - decisions the semantic layer left OPEN and which a
# generation engine has NO authority to settle.
# ---------------------------------------------------------------------------

FORBIDDEN_VEHICLE_ACCESS_MODE = "resolve_vehicle_access_mode"
FORBIDDEN_ENVELOPE_CONTINUITY = "resolve_envelope_continuity"
FORBIDDEN_TERRACE_RELATIONSHIP = "invent_terrace_relationship"
FORBIDDEN_FACADE_APPROVAL = "grant_facade_approval"
FORBIDDEN_DOMAIN_MERGE = "merge_separated_domains"
FORBIDDEN_PROTECTED_ZONE_REMOVAL = "remove_protected_zone"
FORBIDDEN_THICKNESS_INVENTION = "invent_wall_thickness"
FORBIDDEN_LEVEL_INVENTION = "invent_a_level"
FORBIDDEN_CONTAINMENT_OVERRIDE = "override_space_containment"

FORBIDDEN_RESOLUTIONS = (
    FORBIDDEN_VEHICLE_ACCESS_MODE,
    FORBIDDEN_ENVELOPE_CONTINUITY,
    FORBIDDEN_TERRACE_RELATIONSHIP,
    FORBIDDEN_FACADE_APPROVAL,
    FORBIDDEN_DOMAIN_MERGE,
    FORBIDDEN_PROTECTED_ZONE_REMOVAL,
    FORBIDDEN_THICKNESS_INVENTION,
    FORBIDDEN_LEVEL_INVENTION,
    FORBIDDEN_CONTAINMENT_OVERRIDE,
)

#: The forbidden resolutions that apply to EVERY unit, regardless of type -
#: they are global invariants of the boundary, not per-unit choices.
GLOBAL_FORBIDDEN_RESOLUTIONS = (
    FORBIDDEN_DOMAIN_MERGE,
    FORBIDDEN_PROTECTED_ZONE_REMOVAL,
    FORBIDDEN_THICKNESS_INVENTION,
    FORBIDDEN_LEVEL_INVENTION,
    FORBIDDEN_CONTAINMENT_OVERRIDE,
)

# ---------------------------------------------------------------------------
# legacy layer reference - the EXISTING module that owns each concern today.
# Named for migration accounting only. Never imported, never invoked.
# ---------------------------------------------------------------------------

LEGACY_ENGINE = "core/architecture/geometry/architectural_geometry_engine_v2.py"
LEGACY_INTENT_GENERATOR = (
    "core/architecture/geometry/architectural_geometry_intent_generator_v1.py"
)
LEGACY_BOUNDARY_SEGMENTS = (
    "core/architecture/geometry/architectural_boundary_segment_resolver_v1.py"
)
LEGACY_PHYSICAL_WALLS = (
    "core/architecture/geometry/architectural_physical_wall_resolver_v1.py"
)
LEGACY_PHYSICAL_OPENINGS = (
    "core/architecture/geometry/architectural_physical_opening_resolver_v1.py"
)
LEGACY_OPENING_HOSTS = (
    "core/architecture/geometry/architectural_opening_host_resolver_v1.py"
)
LEGACY_STAIR_GEOMETRY = (
    "core/architecture/geometry/architectural_stair_geometry_resolver_v1.py"
)
LEGACY_BIM_BRIDGE = (
    "core/architecture/bim/architectural_to_bim_element_bridge_v1.py"
)
LEGACY_IFC_EXPORTER = "core/architecture/bim/architectural_ifc_exporter_v2.py"

LEGACY_REFERENCES = (
    LEGACY_ENGINE,
    LEGACY_INTENT_GENERATOR,
    LEGACY_BOUNDARY_SEGMENTS,
    LEGACY_PHYSICAL_WALLS,
    LEGACY_PHYSICAL_OPENINGS,
    LEGACY_OPENING_HOSTS,
    LEGACY_STAIR_GEOMETRY,
    LEGACY_BIM_BRIDGE,
    LEGACY_IFC_EXPORTER,
)

#: The known-broken seam: the BIM bridge reads ``physical_walls`` while its
#: test supplies ``boundaries``. Recorded here so the drift is tracked at the
#: boundary rather than rediscovered.
KNOWN_HANDOFF_DRIFT = "physical_walls_vs_boundaries_handoff_shape_mismatch"

# ---------------------------------------------------------------------------
# numeric boundary declaration
# ---------------------------------------------------------------------------

NUMERIC_SIDE_SEMANTIC = "may_not_contain_numeric_leaves"
NUMERIC_SIDE_GENERATION = "numbers_may_first_appear_here"
NUMERIC_SIDES = (NUMERIC_SIDE_SEMANTIC, NUMERIC_SIDE_GENERATION)

# ---------------------------------------------------------------------------
# contract-level states
# ---------------------------------------------------------------------------

STATE_RESOLVED = "geometry_generation_boundary_resolved"
STATE_UNRESOLVED = "geometry_generation_boundary_unresolved"

STATUS_PENDING = "pending"
STATUS_FORBIDDEN = "forbidden"
STATUS_OPEN = "open"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _mapping(value, label):
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")

    return dict(value)


def _sequence(value, label):
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be a sequence")

    return list(value)


def _non_empty_string(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")

    return value


def _pending_geometry():
    return {
        "state": GEOMETRY_STATE_PENDING,
        "reason": GEOMETRY_REASON_NOT_AUTHORIZED,
    }


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _strip_numeric_leaves(value, dropped):
    """Structural guard: remove every numeric leaf from a FINISHED unit.

    A boundary contract must contain no number at all, so a metric leak from
    any upstream contract is removed and reported rather than carried.
    """

    if _is_number(value):
        return None
    if isinstance(value, Mapping):
        cleaned = {}
        for key, item in value.items():
            if _is_number(item):
                dropped.append(str(key))
                continue
            cleaned[key] = _strip_numeric_leaves(item, dropped)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [
            _strip_numeric_leaves(item, dropped)
            for item in value
            if not _is_number(item)
        ]

    return value


# ---------------------------------------------------------------------------
# boundary typing - derived from axes only, never from a name
# ---------------------------------------------------------------------------

def _node_kind(node):
    return node.get("kind")


def _space_domain(node):
    """Return the SPACE-axis domain, or None for a circulation node.

    Circulation nodes carry the CIRCULATION axis, so they must never be read
    as a space domain - that conflation is what caused the ``cross_domain``
    false flag in ARCH-GEOMETRY-01.
    """

    if node.get("kind") == NODE_VERTICAL_ELEMENT:
        return None

    domain = node.get("domain")

    return domain if domain in SPACE_DOMAINS else None


def _domain_axis(node):
    if node.get("kind") == NODE_VERTICAL_ELEMENT:
        return DOMAIN_AXIS_CIRCULATION

    return DOMAIN_AXIS_SPACE


def _request_for_wall(wall_intent_type):
    """Map a semantic wall intent to the generation request an engine would get."""

    return {
        WALL_ENVELOPE: REQUEST_ENVELOPE_WALL_SOLID,
        WALL_SEPARATING: REQUEST_SEPARATING_WALL_SOLID,
        WALL_PARTITION: REQUEST_PARTITION_WALL_SOLID,
        WALL_CORE_ENCLOSURE: REQUEST_CORE_WALL_SOLID,
        WALL_SITE_BOUNDARY: REQUEST_SITE_BOUNDARY_WALL_SOLID,
    }.get(wall_intent_type)


def _request_for_floor(floor_intent_type):
    return {
        FLOOR_SURFACE: REQUEST_FLOOR_SLAB_SOLID,
        FLOOR_ROOF_SURFACE: REQUEST_ROOF_SLAB_SOLID,
        FLOOR_BASEMENT_SURFACE: REQUEST_BASEMENT_SLAB_SOLID,
        FLOOR_SITE_SURFACE: REQUEST_SITE_SURFACE,
    }.get(floor_intent_type)


def _request_for_opening(opening_role):
    return {
        OPENING_GLAZING: REQUEST_GLAZING_OPENING,
        OPENING_EXTERNAL_ACCESS: REQUEST_EXTERNAL_ACCESS_OPENING,
        OPENING_INTERNAL_DOORWAY: REQUEST_INTERNAL_DOORWAY_OPENING,
        OPENING_VERTICAL_ACCESS: REQUEST_VERTICAL_ACCESS_OPENING,
        OPENING_VEHICLE_ACCESS: REQUEST_VEHICLE_ACCESS_OPENING,
    }.get(opening_role)


def _measurement_implying_tokens():
    """Request tokens that would encode a MEASUREMENT, not an artifact name.

    A request may be named after the artifact it asks for (``wall_solid``); it
    may never be named after a dimension of that artifact.
    """

    return (
        "width", "depth", "height", "thickness", "area", "radius",
        "slope", "degree", "millimetre", "centimetre", "metre",
    )


def _prerequisites_for_request(request_type):
    """Which semantic facts an engine must HOLD before this request may run.

    Every request needs the unit's containment and boundary/level context;
    the rest is specific to what is being asked for.
    """

    base = [PREREQ_SPACE_CONTAINMENT, PREREQ_BOUNDARY_TYPE]

    specific = {
        REQUEST_SPACE_VOLUME: [PREREQ_LEVEL_ORDER],
        REQUEST_ENVELOPE_WALL_SOLID: [
            PREREQ_ENVELOPE_CONTINUITY,
            PREREQ_THICKNESS_POLICY,
        ],
        REQUEST_PARTITION_WALL_SOLID: [PREREQ_THICKNESS_POLICY],
        REQUEST_SEPARATING_WALL_SOLID: [
            PREREQ_DOMAIN_SEPARATION,
            PREREQ_THICKNESS_POLICY,
        ],
        REQUEST_CORE_WALL_SOLID: [
            PREREQ_PROTECTED_ZONE,
            PREREQ_THICKNESS_POLICY,
        ],
        REQUEST_SITE_BOUNDARY_WALL_SOLID: [
            PREREQ_VEHICLE_ACCESS_MODE,
            PREREQ_THICKNESS_POLICY,
        ],
        REQUEST_FLOOR_SLAB_SOLID: [PREREQ_LEVEL_ORDER, PREREQ_THICKNESS_POLICY],
        REQUEST_ROOF_SLAB_SOLID: [PREREQ_LEVEL_ORDER, PREREQ_THICKNESS_POLICY],
        REQUEST_BASEMENT_SLAB_SOLID: [
            PREREQ_LEVEL_ORDER,
            PREREQ_THICKNESS_POLICY,
        ],
        REQUEST_SITE_SURFACE: [PREREQ_LEVEL_ORDER],
        REQUEST_SLAB_PENETRATION: [
            PREREQ_LEVEL_ORDER,
            PREREQ_VERTICAL_SERVED_LEVELS,
        ],
        REQUEST_GLAZING_OPENING: [PREREQ_OPENING_ROLE, PREREQ_FACADE_APPROVAL],
        REQUEST_EXTERNAL_ACCESS_OPENING: [
            PREREQ_OPENING_ROLE,
            PREREQ_FACADE_APPROVAL,
        ],
        REQUEST_INTERNAL_DOORWAY_OPENING: [PREREQ_OPENING_ROLE],
        REQUEST_VERTICAL_ACCESS_OPENING: [
            PREREQ_OPENING_ROLE,
            PREREQ_VERTICAL_SERVED_LEVELS,
        ],
        REQUEST_VEHICLE_ACCESS_OPENING: [
            PREREQ_OPENING_ROLE,
            PREREQ_VEHICLE_ACCESS_MODE,
        ],
        REQUEST_VERTICAL_CORE_SOLID: [
            PREREQ_PROTECTED_ZONE,
            PREREQ_VERTICAL_SERVED_LEVELS,
        ],
        REQUEST_STAIR_FLIGHT: [PREREQ_VERTICAL_SERVED_LEVELS],
        REQUEST_ROOF_FORM: [PREREQ_ROOF_ROLE, PREREQ_TERRACE_RELATIONSHIP],
    }

    return sorted(set(base + specific.get(request_type, [])))


def _forbidden_for_request(request_type):
    """The decisions this request may not settle."""

    specific = {
        REQUEST_ENVELOPE_WALL_SOLID: [FORBIDDEN_ENVELOPE_CONTINUITY],
        REQUEST_SITE_BOUNDARY_WALL_SOLID: [FORBIDDEN_VEHICLE_ACCESS_MODE],
        REQUEST_VEHICLE_ACCESS_OPENING: [FORBIDDEN_VEHICLE_ACCESS_MODE],
        REQUEST_GLAZING_OPENING: [FORBIDDEN_FACADE_APPROVAL],
        REQUEST_EXTERNAL_ACCESS_OPENING: [FORBIDDEN_FACADE_APPROVAL],
        REQUEST_ROOF_FORM: [FORBIDDEN_TERRACE_RELATIONSHIP],
        REQUEST_CORE_WALL_SOLID: [
            FORBIDDEN_PROTECTED_ZONE_REMOVAL,
        ],
        REQUEST_VERTICAL_CORE_SOLID: [FORBIDDEN_PROTECTED_ZONE_REMOVAL],
    }

    return sorted(set(list(GLOBAL_FORBIDDEN_RESOLUTIONS) + specific.get(request_type, [])))


def _legacy_reference_for_request(request_type):
    return {
        REQUEST_SPACE_VOLUME: LEGACY_ENGINE,
        REQUEST_ENVELOPE_WALL_SOLID: LEGACY_PHYSICAL_WALLS,
        REQUEST_PARTITION_WALL_SOLID: LEGACY_PHYSICAL_WALLS,
        REQUEST_SEPARATING_WALL_SOLID: LEGACY_PHYSICAL_WALLS,
        REQUEST_CORE_WALL_SOLID: LEGACY_PHYSICAL_WALLS,
        REQUEST_SITE_BOUNDARY_WALL_SOLID: LEGACY_PHYSICAL_WALLS,
        REQUEST_FLOOR_SLAB_SOLID: LEGACY_ENGINE,
        REQUEST_ROOF_SLAB_SOLID: LEGACY_ENGINE,
        REQUEST_BASEMENT_SLAB_SOLID: LEGACY_ENGINE,
        REQUEST_SITE_SURFACE: LEGACY_ENGINE,
        REQUEST_SLAB_PENETRATION: LEGACY_ENGINE,
        REQUEST_GLAZING_OPENING: LEGACY_PHYSICAL_OPENINGS,
        REQUEST_EXTERNAL_ACCESS_OPENING: LEGACY_PHYSICAL_OPENINGS,
        REQUEST_INTERNAL_DOORWAY_OPENING: LEGACY_PHYSICAL_OPENINGS,
        REQUEST_VERTICAL_ACCESS_OPENING: LEGACY_OPENING_HOSTS,
        REQUEST_VEHICLE_ACCESS_OPENING: LEGACY_PHYSICAL_OPENINGS,
        REQUEST_VERTICAL_CORE_SOLID: LEGACY_ENGINE,
        REQUEST_STAIR_FLIGHT: LEGACY_STAIR_GEOMETRY,
        REQUEST_ROOF_FORM: LEGACY_ENGINE,
    }.get(request_type, LEGACY_ENGINE)


# ---------------------------------------------------------------------------
# unit builder
# ---------------------------------------------------------------------------

def _unit(request_type, *, node_id, source_layer, semantic_token,
          missing_prerequisites):
    """Build one boundary unit. Authorization is ALWAYS pending here."""

    prerequisites = _prerequisites_for_request(request_type)

    # A prerequisite this phase cannot satisfy is ALWAYS missing, regardless of
    # what the caller passed: declaring a need is not the same as meeting it.
    missing = set(missing_prerequisites)
    missing.update(
        prerequisite
        for prerequisite in prerequisites
        if prerequisite in UNSATISFIABLE_PREREQUISITES
    )
    missing = sorted(missing)

    # Fail closed: a unit whose prerequisite set is not fully evidenced stays
    # pending and says which evidence is absent. It is NEVER authorized.
    authorization = AUTHORIZATION_PENDING
    status = STATUS_PENDING

    reasons = ["geometry_generation_is_not_authorized_in_this_phase"]
    if missing:
        reasons.append("prerequisites_not_yet_evidenced")

    return {
        "request_id": f"{request_type}:{semantic_token}:{node_id}",
        "request_type": request_type,
        "node_id": node_id,
        "source_layer": source_layer,
        "semantic_token": semantic_token,
        "boundary_side": SIDE_GENERATION,
        "domain_axis": DOMAIN_AXIS_AUTHORIZATION,
        "authorization": authorization,
        "status": status,
        "prerequisites": prerequisites,
        "missing_prerequisites": missing,
        "forbidden_resolutions": _forbidden_for_request(request_type),
        "legacy_layer_reference": _legacy_reference_for_request(request_type),
        "numeric_boundary": NUMERIC_SIDE_GENERATION,
        "produces_geometry": False,
        "produces_coordinates": False,
        "produces_dimensions": False,
        "geometry_status": _pending_geometry(),
        "reasons": sorted(set(reasons)),
    }


# ---------------------------------------------------------------------------
# per-node projection
# ---------------------------------------------------------------------------

def _units_for_node(node, spatial_intent_record):
    """Emit the generation units a node's spatial intent would imply.

    A node with NO spatial intent record yields NO unit - the boundary cannot
    describe a hand-off for a unit the semantic layer never described.
    """

    if spatial_intent_record is None:
        return []

    node_id = node.get("node_id")
    units = []

    # --- space volume -----------------------------------------------------
    units.append(
        _unit(
            REQUEST_SPACE_VOLUME,
            node_id=node_id,
            source_layer="architectural_spatial_geometry_intent_v1",
            semantic_token=node.get("kind"),
            missing_prerequisites=(
                []
                if spatial_intent_record.get("space_containment", {}).get(
                    "status"
                )
                == "resolved"
                else [PREREQ_SPACE_CONTAINMENT]
            ),
        )
    )

    # --- walls, from the semantic wall intents ---------------------------
    wall_block = spatial_intent_record.get("wall_intent") or {}
    for intent in wall_block.get("wall_intents") or []:
        request_type = _request_for_wall(intent.get("wall_intent_type"))
        if request_type is None:
            continue

        missing = []
        if intent.get("boundary_type") == BOUNDARY_SITE_UNRESOLVED:
            missing.append(PREREQ_VEHICLE_ACCESS_MODE)
        if intent.get("wall_intent_type") == WALL_SEPARATING:
            missing.append(PREREQ_DOMAIN_SEPARATION)
        if intent.get("is_protected_zone_boundary"):
            missing.append(PREREQ_PROTECTED_ZONE)

        units.append(
            _unit(
                request_type,
                node_id=node_id,
                source_layer="architectural_spatial_geometry_intent_v1",
                semantic_token=intent.get("wall_intent_type"),
                missing_prerequisites=missing,
            )
        )

    # --- slabs, from the semantic floor intents --------------------------
    floor_block = spatial_intent_record.get("floor_intent") or {}
    for intent in floor_block.get("floor_intents") or []:
        request_type = _request_for_floor(intent.get("floor_intent_type"))
        if request_type is None:
            continue

        units.append(
            _unit(
                request_type,
                node_id=node_id,
                source_layer="architectural_spatial_geometry_intent_v1",
                semantic_token=intent.get("floor_intent_type"),
                missing_prerequisites=[],
            )
        )

        # A floor penetrated by a vertical element needs its own request. The
        # vertical element does not raise one against itself: its own passage
        # through a level it serves is described by the level's surface, not by
        # a separate penetration of itself.
        for penetration in intent.get("penetrations") or []:
            if penetration.get("interruption") != FLOOR_INTERRUPTION_REQUIRED:
                continue
            if penetration.get("vertical_node_id") == node_id:
                continue
            units.append(
                _unit(
                    REQUEST_SLAB_PENETRATION,
                    node_id=node_id,
                    source_layer="architectural_spatial_geometry_intent_v1",
                    semantic_token=penetration.get("vertical_node_id"),
                    missing_prerequisites=[],
                )
            )

    # --- roof form, from the semantic roof intent ------------------------
    roof_block = spatial_intent_record.get("roof_intent") or {}
    if roof_block.get("applies"):
        missing = []
        if roof_block.get("roof_role") is None:
            missing.append(PREREQ_ROOF_ROLE)
        if roof_block.get("terrace_status") == "unresolved":
            missing.append(PREREQ_TERRACE_RELATIONSHIP)

        units.append(
            _unit(
                REQUEST_ROOF_FORM,
                node_id=node_id,
                source_layer="architectural_spatial_geometry_intent_v1",
                semantic_token=roof_block.get("roof_role"),
                missing_prerequisites=missing,
            )
        )

    # --- openings, from the semantic opening/boundary contract -----------
    opening_block = spatial_intent_record.get("opening_intents") or {}
    for opening in opening_block.get("openings") or []:
        request_type = _request_for_opening(opening.get("opening_role"))
        if request_type is None:
            continue

        units.append(
            _unit(
                request_type,
                node_id=node_id,
                source_layer="architectural_opening_boundary_intent_v1",
                semantic_token=opening.get("opening_role"),
                missing_prerequisites=(
                    [PREREQ_OPENING_ROLE]
                    if opening.get("status") != "resolved"
                    else []
                ),
            )
        )

    # --- vertical core solids -------------------------------------------
    if node.get("kind") == NODE_VERTICAL_ELEMENT:
        missing = [] if node.get("floors") else [PREREQ_VERTICAL_SERVED_LEVELS]

        units.append(
            _unit(
                REQUEST_VERTICAL_CORE_SOLID,
                node_id=node_id,
                source_layer="architectural_spatial_geometry_intent_v1",
                semantic_token=node.get("space_type") or node.get("element_type"),
                missing_prerequisites=missing,
            )
        )
        units.append(
            _unit(
                REQUEST_STAIR_FLIGHT,
                node_id=node_id,
                source_layer="architectural_spatial_geometry_intent_v1",
                semantic_token=node.get("space_type") or node.get("element_type"),
                missing_prerequisites=missing,
            )
        )

    # Deterministic order, and dedupe on request_id.
    by_id = {}
    for unit in units:
        by_id[unit["request_id"]] = unit

    return [by_id[key] for key in sorted(by_id)]


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def build_geometry_generation_boundary_contract(
    graph,
    *,
    geometry_intent_contract=None,
    opening_boundary_contract=None,
    spatial_geometry_intent_contract=None,
):
    """Build the boundary contract between the semantic layer and a future
    geometry generation engine.

    ``spatial_geometry_intent_contract`` is the ARCH-GEOMETRY-03 output and is
    the primary input: it supplies the wall, floor and roof intents the
    boundary describes. ``opening_boundary_contract`` (ARCH-GEOMETRY-02)
    supplies the opening intents. ``geometry_intent_contract``
    (ARCH-GEOMETRY-01) is accepted for cross-check agreement.

    Every input is read-only: none is mutated, and no geometry is created.
    Malformed input raises ``ValueError``.
    """

    if not isinstance(graph, Mapping):
        raise ValueError("graph must be a mapping")
    if graph.get("type") != "architectural_intent_graph":
        raise ValueError("graph.type must be 'architectural_intent_graph'")

    nodes = _sequence(graph.get("nodes"), "graph nodes")
    for node in nodes:
        if not isinstance(node, Mapping):
            raise ValueError("graph nodes must be mappings")

    spatial = _mapping(
        spatial_geometry_intent_contract, "spatial_geometry_intent_contract"
    )
    opening = _mapping(
        opening_boundary_contract, "opening_boundary_contract"
    )
    geometry_intent = _mapping(
        geometry_intent_contract, "geometry_intent_contract"
    )

    contract_reasons = []
    node_by_id = {}
    for node in nodes:
        node_id = node.get("node_id")
        if not node_id:
            raise ValueError("graph node is missing node_id")
        node_by_id[node_id] = node

    # --- index the semantic-side records ---------------------------------
    spatial_index = {}
    if spatial:
        if spatial.get("type") != "architectural_spatial_geometry_intent":
            raise ValueError(
                "spatial_geometry_intent_contract.type must be "
                "'architectural_spatial_geometry_intent'"
            )
        for record in spatial.get("node_records", []) or []:
            if isinstance(record, Mapping) and record.get("node_id"):
                spatial_index[record["node_id"]] = record

    opening_index = {}
    if opening:
        for record in opening.get("node_records", []) or []:
            if isinstance(record, Mapping) and record.get("node_id"):
                opening_index[record["node_id"]] = record

    geometry_index = {}
    if geometry_intent:
        for record in geometry_intent.get("node_intents", []) or []:
            if isinstance(record, Mapping) and record.get("node_id"):
                geometry_index[record["node_id"]] = record

    # --- merge opening intents into the spatial record view --------------
    merged = {}
    for node_id, record in spatial_index.items():
        view = dict(record)
        opening_record = opening_index.get(node_id)
        if opening_record is not None:
            view["opening_intents"] = {
                "openings": list(opening_record.get("opens") or []),
            }
        merged[node_id] = view

    # --- state of the semantic side --------------------------------------
    declared_pending = 0
    declared_authorized = 0
    for node in nodes:
        status = node.get("geometry_status")
        if isinstance(status, Mapping):
            if status.get("state") == GEOMETRY_STATE_PENDING:
                declared_pending += 1
            elif status.get("state") == GEOMETRY_STATE_AUTHORIZED:
                declared_authorized += 1

    if declared_authorized:
        # An upstream module claiming authorization would bypass the gate.
        # Report it rather than honour it - the boundary never grants.
        contract_reasons.append(
            "upstream_authorization_claim_not_honoured_by_the_boundary"
        )

    # --- units ------------------------------------------------------------
    units = []
    for node in sorted(nodes, key=lambda item: str(item.get("node_id"))):
        node_id = node["node_id"]
        units.extend(_units_for_node(node, merged.get(node_id)))

    # Second numeric guard: sweep the FINISHED units.
    dropped_paths = []
    cleaned_units = []
    for unit in units:
        cleaned = _strip_numeric_leaves(unit, dropped_paths)
        cleaned_units.append(cleaned)
    if dropped_paths:
        contract_reasons.append("numeric_values_stripped_at_boundary")
    units = cleaned_units

    # --- requests declared executable-later, but NEVER now ---------------
    request_types_seen = sorted({unit["request_type"] for unit in units})
    if not request_types_seen:
        contract_reasons.append(
            "no_semantic_records_supplied_so_no_handoff_can_be_described"
        )

    # --- cross-check agreement with GEOMETRY-01 --------------------------
    geometry_agreement = None
    if geometry_index:
        shared = sorted(set(geometry_index) & set(merged))
        geometry_agreement = {
            "shared_node_ids": shared,
            "geometry_intent_only": sorted(set(geometry_index) - set(merged)),
            "spatial_intent_only": sorted(set(merged) - set(geometry_index)),
        }
        if geometry_agreement["geometry_intent_only"] or (
            geometry_agreement["spatial_intent_only"]
        ):
            contract_reasons.append("semantic_contracts_cover_different_node_sets")
        else:
            contract_reasons.append("semantic_contracts_agree_on_node_coverage")

    # --- pending decisions carried across the boundary -------------------
    pending_decisions = []
    for decision in _sequence(
        spatial.get("pending_decisions"), "pending_decisions"
    ) if spatial else []:
        if isinstance(decision, Mapping):
            pending_decisions.append(dict(decision))

    pending_decisions.append(
        {
            "decision": "geometry_generation_authorization",
            "status": STATUS_PENDING,
            "candidates": [],
            "reasons": [
                "no_authorization_grant_exists_in_this_phase",
            ],
        }
    )
    pending_decisions.append(
        {
            "decision": KNOWN_HANDOFF_DRIFT,
            "status": STATUS_OPEN,
            "candidates": [],
            "reasons": [
                "pre_existing_legacy_handoff_shape_mismatch_is_unresolved",
            ],
        }
    )

    # --- tallies (the only numbers in the contract) ----------------------
    def _tally(field, value):
        return sum(1 for unit in units if unit.get(field) == value)

    blocked = sum(1 for unit in units if unit["missing_prerequisites"])

    return {
        "type": OUTPUT_TYPE,
        "version": OUTPUT_VERSION,
        "units": units,
        "semantic_side": {
            "contracts_supplied": sorted(
                name
                for name, supplied in (
                    ("architectural_geometry_intent_v1", bool(geometry_index)),
                    ("architectural_opening_boundary_intent_v1", bool(opening_index)),
                    ("architectural_spatial_geometry_intent_v1", bool(spatial_index)),
                )
                if supplied
            ),
            "domain_axis": DOMAIN_AXIS_SPACE,
            "numeric_boundary": NUMERIC_SIDE_SEMANTIC,
            "geometry_status_states_declared": {
                GEOMETRY_STATE_PENDING: declared_pending,
                GEOMETRY_STATE_AUTHORIZED: declared_authorized,
            },
            "node_coverage": geometry_agreement,
        },
        "generation_side": {
            "domain_axis": DOMAIN_AXIS_AUTHORIZATION,
            "numeric_boundary": NUMERIC_SIDE_GENERATION,
            "legacy_layer_references": sorted(
                {unit["legacy_layer_reference"] for unit in units}
            ),
            "known_handoff_drift": KNOWN_HANDOFF_DRIFT,
        },
        "summary": {
            "unit_count": len(units),
            "request_types_represented": request_types_seen,
            "units_by_request_type": {
                request_type: _tally("request_type", request_type)
                for request_type in REQUEST_TYPES
                if _tally("request_type", request_type)
            },
            "units_pending_authorization": _tally(
                "authorization", AUTHORIZATION_PENDING
            ),
            "units_authorized": _tally("authorization", AUTHORIZATION_AUTHORIZED),
            "units_forbidden": _tally("authorization", AUTHORIZATION_FORBIDDEN),
            "units_with_missing_prerequisites": blocked,
        },
        "authorization_model": {
            "domain_axis": DOMAIN_AXIS_AUTHORIZATION,
            "states": list(AUTHORIZATION_STATES),
            "states_this_contract_may_emit": list(
                EMITTABLE_AUTHORIZATION_STATES
            ),
            "authorization_grant_exists": False,
        },
        "forbidden_resolutions": list(FORBIDDEN_RESOLUTIONS),
        "prerequisite_vocabulary": list(PREREQUISITES),
        "pending_decisions": pending_decisions,
        "semantics": {
            "metadata_only": True,
            "geometry_created": False,
            "coordinates_created": False,
            "dimensions_created": False,
            "polygons_created": False,
            "meshes_created": False,
            "cad_created": False,
            "ifc_created": False,
            "wall_solid_created": False,
            "slab_solid_created": False,
            "roof_form_created": False,
            "engine_invoked": False,
            "legacy_layer_modified": False,
            "decisions_resolved": False,
        },
        "status": {
            "state": STATE_RESOLVED if units else STATE_UNRESOLVED,
            "reasons": sorted(set(contract_reasons)),
        },
    }


# ---------------------------------------------------------------------------
# query helpers
# ---------------------------------------------------------------------------

def units_for_node(contract, node_id):
    """Return every boundary unit for one node, or an empty list."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")

    return [
        unit
        for unit in contract.get("units", [])
        if unit.get("node_id") == node_id
    ]


def units_of_request_type(contract, request_type):
    """Return every unit of one request type."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")
    if request_type not in REQUEST_TYPES:
        raise ValueError(
            "request_type must be one of: " + ", ".join(REQUEST_TYPES)
        )

    return [
        unit
        for unit in contract.get("units", [])
        if unit.get("request_type") == request_type
    ]


def units_authorized(contract):
    """Return every unit that claims authorization. Always empty in this phase."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")

    return [
        unit
        for unit in contract.get("units", [])
        if unit.get("authorization") == AUTHORIZATION_AUTHORIZED
    ]


def units_blocked_by(contract, prerequisite):
    """Return every unit blocked on one prerequisite."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")
    if prerequisite not in PREREQUISITES:
        raise ValueError(
            "prerequisite must be one of: " + ", ".join(PREREQUISITES)
        )

    return [
        unit
        for unit in contract.get("units", [])
        if prerequisite in (unit.get("missing_prerequisites") or [])
    ]


def units_referencing_legacy(contract, legacy_module):
    """Return every unit whose concern is owned by one legacy module today."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")

    return [
        unit
        for unit in contract.get("units", [])
        if unit.get("legacy_layer_reference") == legacy_module
    ]


def forbidden_resolutions_of(contract, unit_id):
    """Return the forbidden resolutions attached to one unit, or None."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")

    for unit in contract.get("units", []):
        if unit.get("request_id") == unit_id:
            return list(unit.get("forbidden_resolutions") or [])

    return None
