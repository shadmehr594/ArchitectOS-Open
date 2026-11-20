"""Architectural Spatial Geometry Intent Expansion v1 (ARCH-GEOMETRY-03).

The THIRD semantic bridge between the Architectural Intent Graph and future
geometry generation. The three bridges divide the problem like this:

    ARCH-GEOMETRY-01  architectural_geometry_intent
        what geometry will this NODE need?

    ARCH-GEOMETRY-02  architectural_opening_boundary_intent
        where does a space MEET something else, and what will that meeting need?

    ARCH-GEOMETRY-03  architectural_spatial_geometry_intent   <-- this module
        how is the building ASSEMBLED - what contains what, what encloses what,
        what separates what, what surfaces exist, and what tops it?

This module answers the assembly questions in six semantic blocks:

    1. space_containment   what level contains this space, and is it internal
                           or external?
    2. envelope            which boundaries form the building envelope, is it
                           continuous, which of it is protected, and how does
                           it relate to the facade?
    3. wall_intent         which SEPARATING surfaces are implied by the
                           boundaries - partitions, separating walls, core
                           enclosures, envelope walls?
    4. floor_intent        which floor SURFACES exist, how do levels relate,
                           and where is a floor interrupted by a vertical
                           element passing through it?
    5. roof_intent         what is the roof's semantic role, what relates to
                           it, and what weather/exposure obligations does it
                           carry?
    6. spatial_adjacency   a cross-check view of the relationships that
                           GEOMETRY-01 and GEOMETRY-02 already own.

CONTAINMENT IS A LEVEL QUESTION, NOT A GEOMETRIC ONE
---------------------------------------------------
Nothing here computes a position, a volume or a boundary curve. A space is
"contained by" the level that carries it:

- a ``building_space`` is contained by its own floor;
- a ``site_space`` is contained by the SITE, never by a storey - it sits at
  ``site_level`` and belongs to the site domain, so classifying it into a
  storey would leak a site node into the building;
- a ``vertical_element`` is contained by its SERVED FLOOR SET, not by one
  floor. A stair serving basement / ground / upper is genuinely contained by
  all three, and forcing it into one would destroy the one fact that makes it
  a vertical element.

WHAT THIS MODULE DELIBERATELY DOES NOT DO
-----------------------------------------
- create geometry, coordinates, polygons, meshes, walls, slabs or roofs
- decide any dimension: width, depth, height, thickness, area, volume, slope
- compute or copy an ELEVATION. ``ProjectLevelContractV1`` legitimately holds
  ``exact_levels`` in metres and a ``level_span`` derived by subtraction; the
  only things consumed from it are its SEMANTIC facts (notably
  ``roof_is_real_level``). A metre value never crosses into this contract.
- consume ``residential_private_terrace_topology_v1``, which returns a shapely
  polygon plus area/width/depth. Its terrace CONCEPT informs the vocabulary;
  its geometry is forbidden here.
- resolve a pending decision (vehicle access stays PENDING, facade approval
  stays PENDING)
- state that a space has no windows: "interior only" is a statement about what
  the program ENTAILS, never about walls
- mutate the input graph or the input contracts (every block is newly built)

NUMERIC EXCLUSION
-----------------
The same two guards as ARCH-GEOMETRY-01 and ARCH-GEOMETRY-02: declared intent
is cleaned as it is copied, and the whole finished record is swept afterwards.
Records carry NO counts - a count is structurally a number and could be misread
as a measurement.
"""

from __future__ import annotations

from typing import Any, Mapping


OUTPUT_TYPE = "architectural_spatial_geometry_intent"
OUTPUT_VERSION = "architectural_spatial_geometry_intent_v1"

# ---------------------------------------------------------------------------
# node kinds / edge types (mirrors the intent graph vocabulary)
# ---------------------------------------------------------------------------

NODE_BUILDING_SPACE = "building_space"
NODE_SITE_SPACE = "site_space"
NODE_VERTICAL_ELEMENT = "vertical_element"

EDGE_ADJACENCY = "adjacency"
EDGE_VISUAL = "visual_connection"
EDGE_CIRCULATION = "circulation"
EDGE_VERTICAL = "vertical_connection"
EDGE_VEHICLE = "vehicle_access"

# ---------------------------------------------------------------------------
# domain axes
# ---------------------------------------------------------------------------

DOMAIN_BUILDING = "building"
DOMAIN_SITE = "site"
SPACE_DOMAINS = (DOMAIN_BUILDING, DOMAIN_SITE)

DOMAIN_AXIS_SPACE = "space"
DOMAIN_AXIS_CIRCULATION = "circulation"

SITE_LEVEL = "site_level"

# ---------------------------------------------------------------------------
# boundary vocabulary - MUST agree with architectural_opening_boundary_intent_v1
# ---------------------------------------------------------------------------

BOUNDARY_ENVELOPE = "envelope_boundary"
BOUNDARY_INTERNAL = "internal_boundary"
BOUNDARY_CORE = "core_interface"
BOUNDARY_SITE_UNRESOLVED = "site_boundary_unresolved"
BOUNDARY_SITE_OPEN = "site_open_boundary"

ENVELOPE_BOUNDARIES = frozenset((BOUNDARY_ENVELOPE,))

# Separation vocabulary - MUST agree with GEOMETRY-02.
SEPARATION_REQUIRED = "separation_required"
SEPARATION_SHARED = "shared_circulation_permitted"
SEPARATION_NONE = "no_separation_requirement"

# Opening roles - MUST agree with GEOMETRY-02.
OPENING_GLAZING = "glazing_intent"
OPENING_EXTERNAL_ACCESS = "external_access_intent"
OPENING_INTERNAL_DOORWAY = "internal_doorway_intent"
OPENING_VERTICAL_ACCESS = "vertical_access_intent"
OPENING_VEHICLE_ACCESS = "vehicle_access_intent"

# ---------------------------------------------------------------------------
# BLOCK 1 - containment vocabulary
# ---------------------------------------------------------------------------

CONTAINED_BY_STOREY = "contained_by_storey"
CONTAINED_BY_SITE = "contained_by_site"
CONTAINED_BY_SERVED_LEVELS = "contained_by_served_levels"
CONTAINED_BY_NOTHING = "containment_unresolved"

CONTAINMENT_KINDS = (
    CONTAINED_BY_STOREY,
    CONTAINED_BY_SITE,
    CONTAINED_BY_SERVED_LEVELS,
    CONTAINED_BY_NOTHING,
)

# internal / external classification.
CLASSIFICATION_INTERNAL = "internal_to_the_building"
CLASSIFICATION_EXTERNAL = "external_to_the_building"
CLASSIFICATION_SITE = "site_domain"
CLASSIFICATION_CIRCULATION = "circulation_domain"

# ---------------------------------------------------------------------------
# BLOCK 2 - envelope vocabulary
# ---------------------------------------------------------------------------

ENVELOPE_CONTINUITY_REQUIRED = "envelope_continuity_required"
ENVELOPE_CONTINUITY_INTERRUPTED = "envelope_continuity_interrupted_by_circulation"
ENVELOPE_CONTINUITY_PENDING = "envelope_continuity_pending_vehicle_mode"

ENVELOPE_OBLIGATION_WEATHER = "weather_tightness_obligation"
ENVELOPE_OBLIGATION_THERMAL = "thermal_separation_obligation"
ENVELOPE_OBLIGATION_DAYLIGHT = "daylight_obligation"
ENVELOPE_OBLIGATION_VIEW = "view_obligation"

# Facade relationship. The approval state is a DECLARED UNKNOWN, never settled
# here - GEOMETRY-02 established that facade evidence is not yet available.
FACADE_RELATION_EXTERIOR_FACING = "exterior_facing_boundary"
FACADE_RELATION_SITE_FACING = "site_facing_boundary"
FACADE_RELATION_PENDING = "facade_relationship_pending"

FACADE_APPROVAL_PENDING = "pending"

# ---------------------------------------------------------------------------
# BLOCK 3 - wall intent vocabulary (semantic only - never a wall)
# ---------------------------------------------------------------------------

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

# Constraints a wall must eventually satisfy. Tokens, never quantities.
WALL_CONSTRAINT_FIRE = "fire_protection_constraint"
WALL_CONSTRAINT_EGRESS = "egress_protection_constraint"
WALL_CONSTRAINT_SEPARATION = "domain_separation_constraint"
WALL_CONSTRAINT_PRIVACY = "privacy_separation_constraint"
WALL_CONSTRAINT_WEATHER = "weather_separation_constraint"
WALL_CONSTRAINT_ACOUSTIC = "acoustic_separation_constraint"
WALL_CONSTRAINT_GUARDING = "guarding_constraint"

# ---------------------------------------------------------------------------
# BLOCK 4 - floor / slab intent vocabulary
# ---------------------------------------------------------------------------

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

LEVEL_RELATION_ABOVE = "level_above"
LEVEL_RELATION_BELOW = "level_below"
LEVEL_RELATION_TOPMOST = "topmost_level"
LEVEL_RELATION_BOTTOM = "bottommost_level"

# A floor is interrupted where a vertical element passes through it.
FLOOR_INTERRUPTION_REQUIRED = "floor_penetration_required"
FLOOR_INTERRUPTION_NONE = "no_penetration_required"

# ---------------------------------------------------------------------------
# BLOCK 5 - roof intent vocabulary
# ---------------------------------------------------------------------------

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

ROOF_OBLIGATION_WEATHER = "weather_tightness_obligation"
ROOF_OBLIGATION_DRAINAGE = "drainage_intent"
ROOF_OBLIGATION_GUARDING = "guarding_obligation"
ROOF_OBLIGATION_PRIVACY = "privacy_control_obligation"
ROOF_OBLIGATION_ACCESS = "roof_access_intent"

# ---------------------------------------------------------------------------
# states
# ---------------------------------------------------------------------------

STATUS_PENDING = "pending"
STATUS_RESOLVED = "resolved"
STATUS_UNRESOLVED = "unresolved"
STATUS_NOT_REQUIRED = "not_required"

GEOMETRY_STATE_PENDING = "pending"
GEOMETRY_REASON = "geometry_generation_not_authorized"

VEHICLE_ACCESS_PENDING = "pending"

STATE_RESOLVED = "spatial_geometry_intent_resolved"
STATE_UNRESOLVED = "spatial_geometry_intent_unresolved"

# Semantic vehicle signals - never a name list.
VEHICLE_ELEMENT_TYPES = ("ramp", "car_lift")
VEHICLE_SPACE_TYPES = frozenset(
    ("parking", "vehicle_space", "vehicle_circulation", "loading_space")
)
VEHICLE_PLACEMENT_PRIORITY = "vehicle_access"

# Circulation roles that represent a means of egress.
PROTECTED_CIRCULATION_ROLES = frozenset(
    (
        "primary_vertical_circulation",
        "required_vertical_circulation",
        "public_vertical_circulation",
        "shared_core_vertical_circulation",
    )
)

# Occupancy tokens that make a level a ROOF level rather than a storey.
ROOF_LEVEL_TOKENS = frozenset(("roof", "roof_level", "roof_terrace", "bam"))
BASEMENT_LEVEL_TOKENS = frozenset(("basement", "basement_level", "zir_zamin"))
GROUND_LEVEL_TOKENS = frozenset(
    ("ground", "ground_floor", "ground_level", "g", "hamkaf")
)
MEZZANINE_LEVEL_TOKENS = frozenset(("mezzanine", "mezz", "nimeh_tabagheh"))
UPPER_LEVEL_TOKENS = frozenset(
    ("upper", "upper_floor", "upper_level", "first", "first_floor",
     "second", "second_floor", "third", "third_floor", "tabagheh")
)

# Semantic facts consumed from ProjectLevelContractV1 - names only, never values.
FACT_ROOF_IS_REAL_LEVEL = "roof_is_real_level"
FACT_STAIRHOUSE_IS_SUPERSTRUCTURE = (
    "stairhouse_is_roof_superstructure_not_residential_floor"
)
LEVEL_CONTRACT_SEMANTIC_FACTS = (
    FACT_ROOF_IS_REAL_LEVEL,
    FACT_STAIRHOUSE_IS_SUPERSTRUCTURE,
)


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
        raise ValueError(f"{label} must be a list")

    return list(value)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _non_numeric_intent(intent, reasons):
    """Copy declared intent, dropping numeric entries. First of two guards."""

    cleaned = {}
    dropped = []
    for key, value in intent.items():
        if _is_number(value):
            dropped.append(str(key))
            continue
        cleaned[key] = value

    if dropped:
        reasons.append("numeric_intent_entries_dropped_as_dimensions")

    return cleaned


def _strip_numeric_leaves(value, dropped):
    """Remove every numeric leaf from a finished record. Second, structural
    guard - it runs after the projection, so nothing upstream can leak through.
    Tuples are treated as lists so a metre RANGE such as ``(2.90, 3.40)``
    cannot survive either."""

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


def _domain_axis(node):
    if node.get("kind") == NODE_VERTICAL_ELEMENT:
        return DOMAIN_AXIS_CIRCULATION

    return DOMAIN_AXIS_SPACE


def _space_domain(node):
    """Building/site domain for a SPACE node, None for a circulation node.

    Only a building/site crossing between two SPACE nodes is an exterior
    condition. A space reaching its own stair is internal circulation - the
    graph flags that edge cross_domain by comparing raw domain strings across
    two different axes, and that must not be inherited here.
    """

    if node.get("kind") == NODE_VERTICAL_ELEMENT:
        return None

    domain = node.get("domain")

    return domain if domain in SPACE_DOMAINS else None


def _is_vertical(node):
    return node.get("kind") == NODE_VERTICAL_ELEMENT


def _space_type(node):
    return node.get("space_type") or node.get("element_type")


def _is_vehicle_element(node):
    return _is_vertical(node) and _space_type(node) in VEHICLE_ELEMENT_TYPES


def _is_vehicle_space(node):
    """Semantic vehicle SPACE test - never a name list."""

    if _is_vertical(node):
        return False

    if _space_type(node) in VEHICLE_SPACE_TYPES:
        return True

    intent = node.get("architectural_intent")
    if not isinstance(intent, Mapping):
        return False

    if intent.get("vehicle_access_priority"):
        return True

    return intent.get("placement_priority") == VEHICLE_PLACEMENT_PRIORITY


def _is_protected_zone(node):
    if node.get("protected_zone"):
        return True

    return node.get("role") in PROTECTED_CIRCULATION_ROLES


def _is_roof_level(floor):
    if not isinstance(floor, str):
        return False

    lowered = floor.strip().lower()

    return lowered in ROOF_LEVEL_TOKENS or lowered.startswith("roof")


def _is_basement_level(floor):
    if not isinstance(floor, str):
        return False

    lowered = floor.strip().lower()

    return lowered in BASEMENT_LEVEL_TOKENS or lowered.startswith("basement")


def _is_ground_level(floor):
    if not isinstance(floor, str):
        return False

    return floor.strip().lower() in GROUND_LEVEL_TOKENS


def _is_mezzanine_level(floor):
    if not isinstance(floor, str):
        return False

    return floor.strip().lower() in MEZZANINE_LEVEL_TOKENS


def _is_upper_level(floor):
    if not isinstance(floor, str):
        return False

    lowered = floor.strip().lower()

    return lowered in UPPER_LEVEL_TOKENS or lowered.startswith("upper")


def _pending_geometry():
    return {"state": GEOMETRY_STATE_PENDING, "reason": GEOMETRY_REASON}


def _edge_between(edges, a, b):
    """Find every edge joining two node ids, deterministically ordered."""

    found = []
    for edge in edges:
        pair = {edge.get("from"), edge.get("to")}
        if pair == {a, b}:
            found.append(edge)

    found.sort(key=lambda edge: (str(edge.get("type")), str(edge.get("edge_id"))))

    return found


# ---------------------------------------------------------------------------
# graph-side boundary index (GEOMETRY-02 shapes, rebuilt locally)
# ---------------------------------------------------------------------------

def _boundary_type_of(self_node, other_node):
    """Classify a boundary from domain axes only - mirrors GEOMETRY-02.

    Rebuilt rather than imported so this module stays self-contained and reads
    the graph directly, which is what lets it be validated against GEOMETRY-02.
    """

    if _is_vertical(self_node) or _is_vertical(other_node):
        return BOUNDARY_CORE

    self_domain = _space_domain(self_node)
    other_domain = _space_domain(other_node)

    if self_domain == DOMAIN_SITE and other_domain == DOMAIN_SITE:
        return BOUNDARY_SITE_OPEN

    if {self_domain, other_domain} == {DOMAIN_BUILDING, DOMAIN_SITE}:
        if _is_vehicle_element(other_node) or _is_vehicle_space(other_node):
            return BOUNDARY_SITE_UNRESOLVED

        return BOUNDARY_ENVELOPE

    return BOUNDARY_INTERNAL


def _boundaries_of(node, node_by_id, edges):
    """Rebuild this node's boundary list in GEOMETRY-02's shape and order."""

    boundaries = []
    for edge in edges:
        if edge.get("from") != node["node_id"] and edge.get("to") != node["node_id"]:
            continue

        other_id = edge["to"] if edge.get("from") == node["node_id"] else edge["from"]
        other = node_by_id.get(other_id)
        if other is None:
            continue

        boundary_type = _boundary_type_of(node, other)

        boundaries.append(
            {
                "boundary_id": f"{boundary_type}:{node['node_id']}->{other_id}",
                "boundary_type": boundary_type,
                "counterpart_node_id": other_id,
                "counterpart_kind": other.get("kind"),
                "counterpart_domain": other.get("domain"),
                "counterpart_space_domain": _space_domain(other),
                "counterpart_protected_zone": _is_protected_zone(other),
                "edge_type": edge.get("type"),
                "edge_status": edge.get("status"),
                "is_envelope": boundary_type in ENVELOPE_BOUNDARIES,
                "is_vehicle_related": (
                    _is_vehicle_element(other) or _is_vehicle_space(other)
                ),
            }
        )

    boundaries.sort(key=lambda boundary: boundary["boundary_id"])

    return boundaries


# ---------------------------------------------------------------------------
# BLOCK 1 - space containment intent
# ---------------------------------------------------------------------------

def _containment(node, boundaries, reasons):
    """What contains this node, and is it internal or external?

    Containment is a LEVEL question. A site space is contained by the SITE and
    is never classified into a storey; a vertical element is contained by its
    served floor SET.
    """

    kind = node.get("kind")
    floor = node.get("floor")

    # Default classification for an unknown node kind. It is overwritten by
    # every recognised branch below; an unknown kind stays interior because
    # nothing in the program evidences an envelope around it.
    classification = CLASSIFICATION_INTERNAL

    if kind == NODE_SITE_SPACE:
        containment_kind = CONTAINED_BY_SITE
        contained_by = [SITE_LEVEL]
        classification = CLASSIFICATION_SITE
        reasons.append("site_space_is_contained_by_the_site_never_a_storey")
    elif kind == NODE_VERTICAL_ELEMENT:
        served = list(node.get("floors") or [])
        containment_kind = CONTAINED_BY_SERVED_LEVELS
        contained_by = served
        classification = CLASSIFICATION_CIRCULATION
        if not served:
            containment_kind = CONTAINED_BY_NOTHING
            reasons.append("vertical_element_declares_no_served_levels")
        else:
            reasons.append("vertical_element_is_contained_by_its_served_levels")
    elif kind == NODE_BUILDING_SPACE:
        if floor:
            containment_kind = CONTAINED_BY_STOREY
            contained_by = [floor]
            reasons.append("building_space_is_contained_by_its_storey")
        else:
            containment_kind = CONTAINED_BY_NOTHING
            contained_by = []
            reasons.append("building_space_declares_no_floor")
    else:
        containment_kind = CONTAINED_BY_NOTHING
        contained_by = []
        reasons.append("unknown_node_kind_cannot_be_contained")

    # Internal / external classification follows from the containment kind and
    # the envelope boundaries, never from a name.
    if classification != CLASSIFICATION_SITE:
        if kind == NODE_VERTICAL_ELEMENT:
            classification = CLASSIFICATION_CIRCULATION
        elif any(boundary["is_envelope"] for boundary in boundaries):
            classification = CLASSIFICATION_EXTERNAL
            reasons.append("envelope_boundary_makes_this_space_external_facing")
        else:
            classification = CLASSIFICATION_INTERNAL
            reasons.append(
                "no_envelope_boundary_is_entailed_by_the_program"
            )

    return {
        "status": (
            STATUS_RESOLVED
            if containment_kind != CONTAINED_BY_NOTHING
            else STATUS_UNRESOLVED
        ),
        "containment_kind": containment_kind,
        "contained_by_levels": sorted(set(str(level) for level in contained_by)),
        "classification": classification,
        "floor": floor,
        "domain_axis": _domain_axis(node),
        "space_domain": _space_domain(node),
        "geometry_status": _pending_geometry(),
        "reasons": sorted(set(reasons)),
    }


# ---------------------------------------------------------------------------
# BLOCK 2 - envelope intent
# ---------------------------------------------------------------------------

def _envelope(node, boundaries, reasons):
    """Which boundaries form the envelope, is it continuous, what is protected,
    and how does it relate to the facade?"""

    envelope = [boundary for boundary in boundaries if boundary["is_envelope"]]
    unresolved = [
        boundary
        for boundary in boundaries
        if boundary["boundary_type"] == BOUNDARY_SITE_UNRESOLVED
    ]

    segments = [boundary["boundary_id"] for boundary in envelope]
    protected_segments = [
        boundary["boundary_id"]
        for boundary in envelope
        if boundary["counterpart_protected_zone"] or _is_protected_zone(node)
    ]

    if envelope:
        continuity = ENVELOPE_CONTINUITY_REQUIRED
        reasons.append("envelope_is_present_and_must_remain_continuous")
    elif unresolved:
        # A vehicle boundary is part of the envelope but its mode is a pending
        # decision, so continuity cannot be asserted yet.
        continuity = ENVELOPE_CONTINUITY_PENDING
        reasons.append("envelope_continuity_pending_vehicle_access_mode")
    else:
        continuity = ENVELOPE_CONTINUITY_REQUIRED
        reasons.append("no_envelope_boundary_on_this_node")

    if protected_segments:
        reasons.append("envelope_touches_a_protected_zone")

    # Facade relationship: which way the envelope faces, and is it approved?
    if envelope:
        site_facing = [
            boundary
            for boundary in envelope
            if boundary["counterpart_node_id"].startswith("site:")
        ]
        facade_relation = (
            FACADE_RELATION_SITE_FACING
            if site_facing
            else FACADE_RELATION_EXTERIOR_FACING
        )
        facade_approval = FACADE_APPROVAL_PENDING
        reasons.append("facade_relationship_declared_but_approval_pending")
    elif unresolved:
        facade_relation = FACADE_RELATION_PENDING
        facade_approval = FACADE_APPROVAL_PENDING
        reasons.append("facade_relationship_pending_vehicle_mode_decision")
    else:
        facade_relation = None
        facade_approval = None

    obligations = []
    if envelope:
        obligations.extend(
            (ENVELOPE_OBLIGATION_WEATHER, ENVELOPE_OBLIGATION_THERMAL)
        )
        intent = node.get("architectural_intent")
        if isinstance(intent, Mapping):
            if intent.get("daylight_priority") == "high":
                obligations.append(ENVELOPE_OBLIGATION_DAYLIGHT)
            if intent.get("natural_ventilation") is True:
                obligations.append(ENVELOPE_OBLIGATION_DAYLIGHT)

    return {
        "status": (
            STATUS_UNRESOLVED
            if continuity == ENVELOPE_CONTINUITY_PENDING
            else STATUS_RESOLVED
        ),
        "is_envelope_participant": bool(envelope) or bool(unresolved),
        "envelope_boundary_ids": sorted(segments),
        "envelope_segment_count_is_zero": not segments,
        "continuity_status": continuity,
        "protected_boundary_ids": sorted(set(protected_segments)),
        "facade_relationship": facade_relation,
        "facade_approval_status": facade_approval,
        "obligations": sorted(set(obligations)),
        "geometry_status": _pending_geometry(),
        "reasons": sorted(set(reasons)),
    }


# ---------------------------------------------------------------------------
# BLOCK 3 - wall intent
# ---------------------------------------------------------------------------

def _wall_intent(self_node, boundary, circulation_separation, reasons):
    """The semantic of the wall a boundary implies. NO wall is created."""

    boundary_type = boundary["boundary_type"]
    constraints = []

    if boundary_type == BOUNDARY_ENVELOPE:
        wall_intent = WALL_ENVELOPE
        constraints.extend(
            (WALL_CONSTRAINT_WEATHER, WALL_CONSTRAINT_ACOUSTIC)
        )
    elif boundary_type == BOUNDARY_CORE:
        wall_intent = WALL_CORE_ENCLOSURE
        constraints.extend((WALL_CONSTRAINT_FIRE, WALL_CONSTRAINT_EGRESS))
    elif boundary_type == BOUNDARY_SITE_OPEN:
        wall_intent = WALL_SITE_BOUNDARY
        reasons.append("site_open_edge_may_carry_a_site_boundary_wall")
    elif boundary_type == BOUNDARY_SITE_UNRESOLVED:
        # A vehicle-related building/site meeting is NOT an interior partition:
        # its wall semantic is a site boundary whose guarding is pending the
        # ramp-vs-car-lift decision. Classifying it as a partition would claim
        # an interior relationship the program has not established.
        wall_intent = WALL_SITE_BOUNDARY
        reasons.append(
            "vehicle_boundary_is_a_site_boundary_not_an_interior_partition"
        )
    else:
        # An internal boundary is a PARTITION unless the program requires the
        # two sides to stay separate, in which case it is a SEPARATING wall.
        separation = circulation_separation
        separation_required = bool(
            isinstance(separation, Mapping)
            and separation.get("separation_required")
        )
        self_domain = self_node.get("domain")
        other_domain = boundary.get("counterpart_domain")

        if separation_required and self_domain != other_domain:
            wall_intent = WALL_SEPARATING
            constraints.append(WALL_CONSTRAINT_SEPARATION)
            reasons.append(
                "domain_separation_makes_this_a_separating_wall_not_a_partition"
            )
        else:
            wall_intent = WALL_PARTITION
            constraints.append(WALL_CONSTRAINT_ACOUSTIC)

    if boundary["counterpart_protected_zone"] or _is_protected_zone(self_node):
        if WALL_CONSTRAINT_FIRE not in constraints:
            constraints.append(WALL_CONSTRAINT_FIRE)
        reasons.append("protected_zone_imposes_a_fire_constraint")

    if boundary_type == BOUNDARY_SITE_UNRESOLVED:
        constraints.append(WALL_CONSTRAINT_GUARDING)
        reasons.append("vehicle_boundary_constraints_pending_mode_decision")

    return {
        "wall_intent_id": f"{wall_intent}:{boundary['boundary_id']}",
        "wall_intent_type": wall_intent,
        "boundary_id": boundary["boundary_id"],
        "boundary_type": boundary_type,
        "counterpart_node_id": boundary["counterpart_node_id"],
        "separates": sorted(
            str(value)
            for value in (
                _space_domain(self_node) or self_node.get("domain"),
                boundary.get("counterpart_domain"),
            )
            if value
        ),
        "constraints": sorted(set(constraints)),
        "is_protected_zone_boundary": bool(
            boundary["counterpart_protected_zone"] or _is_protected_zone(self_node)
        ),
        "geometry_status": _pending_geometry(),
        "status": (
            STATUS_PENDING
            if boundary_type == BOUNDARY_SITE_UNRESOLVED
            else STATUS_RESOLVED
        ),
        "reasons": sorted(set(reasons)),
    }


def _wall(node, boundaries, circulation_separation, reasons):
    intents = []
    for boundary in boundaries:
        boundary_reasons = [f"wall_intent_from_boundary:{boundary['boundary_type']}"]
        intents.append(
            _wall_intent(node, boundary, circulation_separation, boundary_reasons)
        )

    if not intents:
        reasons.append("node_implies_no_wall_intent")

    return {
        "status": STATUS_PENDING,
        "wall_intents": intents,
        "geometry_status": _pending_geometry(),
        "reasons": sorted(set(reasons)),
    }


# ---------------------------------------------------------------------------
# BLOCK 4 - floor / slab intent
# ---------------------------------------------------------------------------

def _floor_intent_type(floor):
    if floor == SITE_LEVEL:
        return FLOOR_SITE_SURFACE
    if _is_roof_level(floor):
        return FLOOR_ROOF_SURFACE
    if _is_basement_level(floor):
        return FLOOR_BASEMENT_SURFACE

    return FLOOR_SURFACE


def _floor_index(node_by_id, circulation_separation):
    """Build the level stack from node floors plus served floors.

    The ORDER is what matters. No elevation is consulted or derived.
    """

    floors = set()
    for node in node_by_id.values():
        if _is_vertical(node):
            floors.update(str(level) for level in (node.get("floors") or []))
        elif node.get("floor"):
            floors.add(str(node["floor"]))

    # Ordering is semantic, not numeric: site, basement(s), ground, mezzanine,
    # upper, roof. Floor names arrive from the graph in the producer's own
    # vocabulary (``ground`` / ``upper`` / ``basement`` / ``roof``), so the
    # ranker matches on token PREFIX rather than on one literal spelling - a
    # literal set would silently drop the common short forms to the unknown
    # bucket and sort ``roof`` before ``ground``.
    def rank(floor):
        if floor == SITE_LEVEL:
            return (0, floor)
        if _is_basement_level(floor):
            return (1, floor)
        if _is_ground_level(floor):
            return (2, floor)
        if _is_mezzanine_level(floor):
            return (3, floor)
        if _is_upper_level(floor):
            return (4, floor)
        if _is_roof_level(floor):
            return (5, floor)

        return (6, floor)

    ordered = sorted(floors, key=rank)

    return ordered


def _floor(node, node_by_id, floors_ordered, reasons):
    """The floor SURFACE intent for the level(s) this node touches, plus the
    level relationships and where a floor is interrupted."""

    kind = node.get("kind")

    if kind == NODE_VERTICAL_ELEMENT:
        touched = [str(level) for level in (node.get("floors") or [])]
    elif node.get("floor"):
        touched = [str(node["floor"])]
    else:
        touched = []

    intents = []
    for floor in sorted(set(touched)):
        if floor not in floors_ordered:
            reasons.append("floor_not_in_the_derived_level_stack")
            continue

        index = floors_ordered.index(floor)

        relation_above = (
            floors_ordered[index + 1] if index + 1 < len(floors_ordered) else None
        )
        relation_below = floors_ordered[index - 1] if index > 0 else None

        relations = []
        if relation_above is None:
            relations.append(LEVEL_RELATION_TOPMOST)
        if relation_below is None:
            relations.append(LEVEL_RELATION_BOTTOM)

        # A floor is interrupted where a VERTICAL ELEMENT passes through it.
        # A stair serving this floor and the one above genuinely penetrates it.
        penetrations = []
        for other in sorted(node_by_id.values(), key=lambda item: item["node_id"]):
            if not _is_vertical(other):
                continue
            if _is_vehicle_element(other):
                # The ramp crosses levels too, but its mode is pending, so the
                # interruption cannot be asserted yet.
                continue
            served = [str(level) for level in (other.get("floors") or [])]
            if floor in served and len(served) > 1:
                penetrations.append(
                    {
                        "vertical_node_id": other["node_id"],
                        "vertical_element_type": _space_type(other),
                        "interruption": FLOOR_INTERRUPTION_REQUIRED,
                    }
                )

        intents.append(
            {
                "floor_intent_id": f"{_floor_intent_type(floor)}:{floor}",
                "floor_intent_type": _floor_intent_type(floor),
                "level": floor,
                "level_index_from_bottom": index,
                "level_above": relation_above,
                "level_below": relation_below,
                "level_relations": sorted(relations),
                "penetrations": penetrations,
                "penetration_count_is_zero": not penetrations,
                "is_occupied_by_this_node": True,
                "geometry_status": _pending_geometry(),
                "status": STATUS_PENDING,
            }
        )

    if not intents:
        reasons.append("node_touches_no_level")

    # The ROOF is a level in its own right - the level contract asserts
    # ``roof_is_real_level``. It is recorded here so a consumer cannot treat the
    # building as terminating without a surface.
    roof_levels = [floor for floor in floors_ordered if _is_roof_level(floor)]
    site_levels = [floor for floor in floors_ordered if floor == SITE_LEVEL]

    return {
        "status": STATUS_PENDING,
        "floor_intents": intents,
        "roof_levels_present": roof_levels,
        "site_levels_present": site_levels,
        "level_stack": floors_ordered,
        "geometry_status": _pending_geometry(),
        "reasons": sorted(set(reasons)),
    }


# ---------------------------------------------------------------------------
# BLOCK 5 - roof intent
# ---------------------------------------------------------------------------

def _roof(node, node_by_id, boundaries, floors_ordered, level_facts, reasons):
    """The roof's semantic role, what relates to it, and its exposure duties.

    FAIL CLOSED: a terrace is only asserted when the graph actually carries a
    site space or level related to the topmost level. Otherwise the terrace is
    a declared UNKNOWN, never invented.
    """

    topmost = None
    for floor in reversed(floors_ordered):
        if floor == SITE_LEVEL:
            continue
        topmost = floor
        break

    # Only the node(s) sitting on the topmost level (or a vertical element
    # serving it) carry roof intent, so the block is not repeated everywhere.
    touches_top = False
    if topmost is not None:
        if _is_vertical(node):
            touches_top = topmost in [str(f) for f in (node.get("floors") or [])]
        elif node.get("floor"):
            touches_top = str(node["floor"]) == topmost

    is_roof_level_node = _is_roof_level(node.get("floor"))

    if not touches_top and not is_roof_level_node:
        return {
            "status": STATUS_NOT_REQUIRED,
            "roof_role": None,
            "applies": False,
            "geometry_status": _pending_geometry(),
            "reasons": ["node_does_not_touch_the_topmost_level"],
        }

    # A site space can itself be the roof surface when the programme places the
    # roof at site level (a garden roof), which is a relationship, not geometry.
    if node.get("kind") == NODE_SITE_SPACE:
        role = ROOF_ROLE_SITE_LEVEL
        reasons.append("site_space_at_the_topmost_level_is_a_roof_surface")
    elif is_roof_level_node or level_facts.get(FACT_ROOF_IS_REAL_LEVEL) is True:
        role = ROOF_ROLE_TOP_TERMINATION
        reasons.append("level_contract_asserts_the_roof_is_a_real_level")
    else:
        role = ROOF_ROLE_TOP_TERMINATION
        reasons.append("topmost_level_terminates_the_envelope")

    # Terrace relationship: only when evidenced.
    terrace_related = [
        boundary["counterpart_node_id"]
        for boundary in boundaries
        if boundary["counterpart_node_id"].startswith("site:")
    ]
    terrace_required = bool(terrace_related)

    if terrace_related:
        reasons.append("site_space_at_the_topmost_level_supports_a_roof_terrace")
        role = ROOF_ROLE_OCCUPIABLE_TERRACE
    else:
        reasons.append("no_terrace_relationship_is_evidenced_terrace_stays_unknown")

    obligations = [ROOF_OBLIGATION_WEATHER, ROOF_OBLIGATION_DRAINAGE]
    if terrace_required:
        obligations.extend(
            (ROOF_OBLIGATION_GUARDING, ROOF_OBLIGATION_PRIVACY, ROOF_OBLIGATION_ACCESS)
        )

    if level_facts.get(FACT_STAIRHOUSE_IS_SUPERSTRUCTURE) is not True:
        reasons.append("stairhouse_superstructure_fact_not_asserted")

    return {
        "status": (
            STATUS_RESOLVED if terrace_required else STATUS_UNRESOLVED
        ),
        "roof_role": role,
        "applies": True,
        "serves_level": topmost,
        "terrace_required": terrace_required,
        "terrace_related_node_ids": sorted(set(terrace_related)),
        "terrace_status": (
            STATUS_RESOLVED if terrace_required else STATUS_UNRESOLVED
        ),
        "exposure": "exterior",
        "obligations": sorted(set(obligations)),
        "level_facts_consumed": {
            fact: level_facts.get(fact) for fact in LEVEL_CONTRACT_SEMANTIC_FACTS
        },
        "geometry_status": _pending_geometry(),
        "reasons": sorted(set(reasons)),
    }


# ---------------------------------------------------------------------------
# BLOCK 6 - spatial adjacency intent (PRESERVE, never re-derive)
# ---------------------------------------------------------------------------

def _spatial_adjacency(node, node_by_id, edges, reasons):
    """A cross-check view of what GEOMETRY-01 and GEOMETRY-02 already own.

    Nothing new is decided here. The ids and counts must MATCH the other two
    contracts so a consumer can verify all three agree.
    """

    adjacent = []
    visual = []
    circulation = []
    vertical = []
    vehicle = []

    for edge in edges:
        if edge.get("from") != node["node_id"] and edge.get("to") != node["node_id"]:
            continue

        other_id = edge["to"] if edge.get("from") == node["node_id"] else edge["from"]
        edge_type = edge.get("type")

        if edge_type == EDGE_ADJACENCY:
            adjacent.append(other_id)
        elif edge_type == EDGE_VISUAL:
            visual.append(other_id)
        elif edge_type == EDGE_CIRCULATION:
            circulation.append(other_id)
        elif edge_type == EDGE_VERTICAL:
            vertical.append(other_id)
        elif edge_type == EDGE_VEHICLE:
            vehicle.append(other_id)
            # A vehicle element IS vertical; GEOMETRY-01 records it in
            # vertical_nodes as well, and this contract must agree.
            vertical.append(other_id)

    reasons.append("adjacency_is_a_preserved_view_not_a_re_derivation")

    return {
        "status": STATUS_PENDING,
        "adjacent_node_ids": sorted(set(adjacent)),
        "visual_connection_node_ids": sorted(set(visual)),
        "circulation_node_ids": sorted(set(circulation)),
        "vertical_node_ids": sorted(set(vertical)),
        "vehicle_node_ids": sorted(set(vehicle)),
        "relationship_count_is_zero": not any(
            (adjacent, visual, circulation, vertical, vehicle)
        ),
        "geometry_status": _pending_geometry(),
        "reasons": sorted(set(reasons)),
    }


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def build_spatial_geometry_intent_contract(
    graph,
    *,
    opening_boundary_contract=None,
    level_contract_semantics=None,
):
    """Expand the Architectural Intent Graph into the assembly-level spatial
    geometry intent contract.

    ``opening_boundary_contract`` is the OPTIONAL ARCH-GEOMETRY-02 output. When
    supplied, its boundary ids are ECHOED so a consumer can cross-check the two
    contracts agree; nothing in it is modified or re-derived.

    ``level_contract_semantics`` is an OPTIONAL mapping of SEMANTIC facts from
    ``ProjectLevelContractV1`` (for example ``roof_is_real_level``). Only the
    named semantic flags are read - an elevation, a span or a height range is
    ignored, because this contract admits no numeric leaf.

    Pure function: neither input is mutated. Malformed input raises
    ``ValueError``.
    """

    if not isinstance(graph, Mapping):
        raise ValueError("graph must be a mapping")
    if graph.get("type") != "architectural_intent_graph":
        raise ValueError("graph.type must be 'architectural_intent_graph'")

    nodes = _sequence(graph.get("nodes"), "graph nodes")
    edges = _sequence(graph.get("edges"), "graph edges")

    for edge in edges:
        if not isinstance(edge, Mapping):
            raise ValueError("graph edges must be mappings")

    node_by_id = {}
    for node in nodes:
        if not isinstance(node, Mapping):
            raise ValueError("graph nodes must be mappings")
        node_id = node.get("node_id")
        if not node_id:
            raise ValueError("graph node is missing node_id")
        node_by_id[node_id] = node

    # Consume ONLY the named semantic facts; drop every other key, so an
    # elevation or a span cannot arrive here under a different name.
    raw_facts = _mapping(level_contract_semantics, "level_contract_semantics")
    level_facts = {
        fact: raw_facts[fact]
        for fact in LEVEL_CONTRACT_SEMANTIC_FACTS
        if fact in raw_facts
    }
    level_fact_reasons = []
    if raw_facts and len(level_facts) != len(raw_facts):
        level_fact_reasons.append(
            "non_semantic_level_contract_entries_ignored"
        )

    circulation_separation = graph.get("circulation_separation")

    # OPTIONAL cross-check against GEOMETRY-02.
    echo_index = {}
    if isinstance(opening_boundary_contract, Mapping):
        for record in opening_boundary_contract.get("node_records", []) or []:
            if not isinstance(record, Mapping):
                continue
            node_id = record.get("node_id")
            if not node_id:
                continue
            echo_index[node_id] = sorted(
                boundary.get("boundary_id")
                for boundary in (record.get("boundaries") or [])
                if isinstance(boundary, Mapping) and boundary.get("boundary_id")
            )

    floors_ordered = _floor_index(node_by_id, circulation_separation)

    contract_reasons = list(level_fact_reasons)
    records = []
    seams = []

    for node in nodes:
        node_id = node["node_id"]
        node_reasons = []

        intent_reasons = []
        declared_intent = _non_numeric_intent(
            node.get("architectural_intent")
            if isinstance(node.get("architectural_intent"), Mapping)
            else {},
            intent_reasons,
        )

        boundaries = _boundaries_of(node, node_by_id, edges)
        containment = _containment(node, boundaries, node_reasons)
        envelope = _envelope(node, boundaries, node_reasons)
        wall = _wall(node, boundaries, circulation_separation, node_reasons)
        floor = _floor(node, node_by_id, floors_ordered, node_reasons)
        roof = _roof(
            node, node_by_id, boundaries, floors_ordered, level_facts, node_reasons
        )
        adjacency = _spatial_adjacency(node, node_by_id, edges, node_reasons)

        # Echoed GEOMETRY-02 boundary ids, plus an agreement flag.
        echoed = echo_index.get(node_id)
        local_ids = sorted(boundary["boundary_id"] for boundary in boundaries)
        if echoed is None:
            boundary_echo = {
                "echoed": False,
                "agrees_with_opening_boundary_contract": None,
                "boundary_ids": local_ids,
            }
        else:
            boundary_echo = {
                "echoed": True,
                "agrees_with_opening_boundary_contract": echoed == local_ids,
                "boundary_ids": local_ids,
            }
            if echoed != local_ids:
                node_reasons.append(
                    "boundary_ids_disagree_with_opening_boundary_contract"
                )

        if boundary_echo["echoed"]:
            contract_reasons.append("boundary_ids_echoed_from_geometry_02")

        record = {
            "node_id": node_id,
            "space_identity": {
                "name": node.get("name"),
                "canonical_name": node.get("canonical_name"),
                "kind": node.get("kind"),
                "space_type": _space_type(node),
            },
            "domain": node.get("domain"),
            "domain_axis": _domain_axis(node),
            "space_domain": _space_domain(node),
            "floor": node.get("floor"),
            "semantic_role": node.get("role"),
            "is_protected_zone": _is_protected_zone(node),
            "declared_intent": declared_intent,
            "space_containment": containment,
            "envelope": envelope,
            "wall_intent": wall,
            "floor_intent": floor,
            "roof_intent": roof,
            "spatial_adjacency": adjacency,
            "boundary_echo": boundary_echo,
            "geometry_status": _pending_geometry(),
        }

        # Second numeric guard: sweep the FINISHED record. A metre RANGE such as
        # ``(2.90, 3.40)`` or an elevation would be removed here.
        dropped_paths = []
        record = _strip_numeric_leaves(record, dropped_paths)
        if dropped_paths:
            contract_reasons.append(
                "numeric_values_stripped_at_contract_boundary"
            )

        records.append(record)
        contract_reasons.extend(intent_reasons)
        contract_reasons.extend(node_reasons)

        # Seams: where the envelope is discontinuous because two adjacent
        # spaces disagree about being envelope participants.
        seams.extend(
            _seams_of(node, node_by_id, edges, node_reasons)
        )

    # --- preserved pending decisions (never resolved) ---------------------
    pending_decisions = []
    graph_pending = _sequence(graph.get("pending_decisions"), "pending_decisions")
    for decision in graph_pending:
        if isinstance(decision, Mapping):
            pending_decisions.append(dict(decision))

    pending_decisions.append(
        {
            "decision": "envelope_continuity",
            "status": STATUS_PENDING,
            "candidates": [],
            "reasons": ["envelope_geometry_not_authorized_in_this_phase"],
        }
    )
    if any(
        record["roof_intent"].get("terrace_status") == STATUS_UNRESOLVED
        for record in records
        if record["roof_intent"].get("applies")
    ):
        pending_decisions.append(
            {
                "decision": "roof_terrace",
                "status": STATUS_UNRESOLVED,
                "candidates": [],
                "reasons": ["no_terrace_relationship_is_evidenced"],
            }
        )

    # --- summaries (the only numbers in the contract) --------------------
    def _tally(key, field, value):
        return sum(1 for record in records if record[key].get(field) == value)

    wall_tally = {}
    for record in records:
        for intent in record["wall_intent"]["wall_intents"]:
            wall_tally[intent["wall_intent_type"]] = (
                wall_tally.get(intent["wall_intent_type"], 0) + 1
            )

    floor_tally = {}
    for record in records:
        for intent in record["floor_intent"]["floor_intents"]:
            floor_tally[intent["floor_intent_type"]] = (
                floor_tally.get(intent["floor_intent_type"], 0) + 1
            )

    roof_tally = {}
    for record in records:
        if record["roof_intent"].get("applies"):
            role = record["roof_intent"].get("roof_role")
            roof_tally[role] = roof_tally.get(role, 0) + 1

    return {
        "type": OUTPUT_TYPE,
        "version": OUTPUT_VERSION,
        "node_records": records,
        "level_stack": floors_ordered,
        "envelope_seams": seams,
        "summary": {
            "containment_by_kind": {
                kind: _tally("space_containment", "containment_kind", kind)
                for kind in CONTAINMENT_KINDS
            },
            "classification_by_kind": {
                kind: _tally("space_containment", "classification", kind)
                for kind in (
                    CLASSIFICATION_INTERNAL,
                    CLASSIFICATION_EXTERNAL,
                    CLASSIFICATION_SITE,
                    CLASSIFICATION_CIRCULATION,
                )
            },
            "envelope_participants": _tally(
                "envelope", "is_envelope_participant", True
            ),
            "wall_intents_by_type": dict(sorted(wall_tally.items())),
            "floor_intents_by_type": dict(sorted(floor_tally.items())),
            "roof_intents_by_role": dict(sorted(roof_tally.items())),
        },
        "circulation_separation": circulation_separation,
        "level_contract_semantics_consumed": {
            fact: level_facts.get(fact) for fact in LEVEL_CONTRACT_SEMANTIC_FACTS
        },
        "pending_decisions": pending_decisions,
        "semantics": {
            "metadata_only": True,
            "geometry_created": False,
            "coordinates_created": False,
            "dimensions_created": False,
            "polygons_created": False,
            "meshes_created": False,
            "wall_geometry_created": False,
            "slab_geometry_created": False,
            "roof_geometry_created": False,
            "elevations_consumed": False,
            "decisions_resolved": False,
        },
        "status": {
            "state": STATE_RESOLVED if records else STATE_UNRESOLVED,
            "reasons": sorted(set(contract_reasons)),
        },
    }


def _seams_of(node, node_by_id, edges, reasons):
    """Envelope seams: adjacent SPACE nodes that disagree about being envelope
    participants, which means the envelope is not continuous across them."""

    seams = []
    if _is_vertical(node):
        return seams

    self_participates = any(
        boundary["is_envelope"] for boundary in _boundaries_of(node, node_by_id, edges)
    )

    for edge in edges:
        if edge.get("from") != node["node_id"] and edge.get("to") != node["node_id"]:
            continue

        other_id = edge["to"] if edge["from"] == node["node_id"] else edge["from"]
        other = node_by_id.get(other_id)
        if other is None or _is_vertical(other):
            continue

        # Only a building-to-building meeting can carry an envelope seam.
        if _space_domain(node) != DOMAIN_BUILDING:
            continue
        if _space_domain(other) != DOMAIN_BUILDING:
            continue

        other_participates = any(
            boundary["is_envelope"]
            for boundary in _boundaries_of(other, node_by_id, edges)
        )

        if self_participates != other_participates:
            seams.append(
                {
                    "seam_id": f"envelope_seam:{node['node_id']}->{other_id}",
                    "from_node_id": node["node_id"],
                    "to_node_id": other_id,
                    "from_is_envelope_participant": self_participates,
                    "to_is_envelope_participant": other_participates,
                    "continuity": ENVELOPE_CONTINUITY_INTERRUPTED,
                    "geometry_status": _pending_geometry(),
                    "status": STATUS_PENDING,
                    "reasons": ["adjacent_building_spaces_disagree_about_envelope"],
                }
            )
            reasons.append("envelope_seam_detected")

    return seams


# ---------------------------------------------------------------------------
# queries
# ---------------------------------------------------------------------------

def record_for_node(contract, node_id):
    """Return the spatial geometry intent record for one node, or None."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")

    for record in contract.get("node_records", []):
        if record.get("node_id") == node_id:
            return record

    return None


def records_with_classification(contract, classification):
    """Return records carrying one internal/external classification."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")

    return [
        record
        for record in contract.get("node_records", [])
        if (record.get("space_containment") or {}).get("classification")
        == classification
    ]


def wall_intents_of_type(contract, wall_intent_type):
    """Return every wall intent of one type, across all records."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")
    if wall_intent_type not in WALL_INTENT_TYPES:
        raise ValueError(
            "wall_intent_type must be one of: " + ", ".join(WALL_INTENT_TYPES)
        )

    return [
        intent
        for record in contract.get("node_records", [])
        for intent in (record.get("wall_intent") or {}).get("wall_intents", [])
        if intent.get("wall_intent_type") == wall_intent_type
    ]


def floor_intents_of_type(contract, floor_intent_type):
    """Return every floor intent of one type, across all records."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")
    if floor_intent_type not in FLOOR_INTENT_TYPES:
        raise ValueError(
            "floor_intent_type must be one of: " + ", ".join(FLOOR_INTENT_TYPES)
        )

    return [
        intent
        for record in contract.get("node_records", [])
        for intent in (record.get("floor_intent") or {}).get("floor_intents", [])
        if intent.get("floor_intent_type") == floor_intent_type
    ]


def roof_records(contract):
    """Return every record whose roof intent applies."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")

    return [
        record
        for record in contract.get("node_records", [])
        if (record.get("roof_intent") or {}).get("applies")
    ]


def envelope_records(contract):
    """Return every record participating in the building envelope."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")

    return [
        record
        for record in contract.get("node_records", [])
        if (record.get("envelope") or {}).get("is_envelope_participant")
    ]


def pending_geometry_blocks(contract):
    """Return every block whose geometry is still pending."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")

    pending = []
    for record in contract.get("node_records", []):
        for key in (
            "space_containment",
            "envelope",
            "wall_intent",
            "floor_intent",
            "roof_intent",
            "spatial_adjacency",
        ):
            block = record.get(key) or {}
            if (block.get("geometry_status") or {}).get("state") == (
                GEOMETRY_STATE_PENDING
            ):
                pending.append(
                    {"node_id": record["node_id"], "block": key}
                )

    return pending
