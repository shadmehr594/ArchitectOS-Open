"""Opening + Boundary Intelligence v1 (ARCH-GEOMETRY-02).

The second semantic bridge between the Architectural Intent Graph and future
geometry generation. ARCH-GEOMETRY-01 answers "what geometry will this NODE
need?". This module answers the two questions that sit between a node and its
geometry:

    WHERE does a space meet something else?   -> boundary_intent
    WHAT will that meeting eventually need?   -> opening_intent

Both answers are SEMANTIC. No boundary and no opening is created here; each is
described as an obligation with a pending state.

WHY BOUNDARY IS DERIVED SEMANTICALLY
------------------------------------
``opening_reasoner_v2`` already contains a geometric exposure resolver
(``resolve_exterior_exposure``), but it requires ``physical_walls`` carrying
``is_exterior`` - geometry that does not exist yet. Exposure must therefore be
derivable BEFORE any wall exists, from the intent graph alone:

    a building space joined to a site space by any edge is EXPOSED on that
    side, because the two domains cannot share a wall interior to the building
    without an envelope boundary between them.

A building space with no site relation is ``interior_only``. That is a
statement about INTENT, not about walls: it says no exterior boundary is
entailed by the program, and it stays ``pending`` because a building space
could still be exposed for reasons the graph does not yet carry.

This module deliberately does NOT:

- create geometry, coordinates, polygons, walls, boundaries or openings
- decide any dimension (width, height, sill, head, area, rise, run, slope)
- read or write CAD, DWG, IFC or BIM data
- place an opening on a host wall, or compute an opening centre
- read the filesystem, use randomness, UUIDs or timestamps
- resolve a pending decision (vehicle access stays PENDING)
- select an opening by SPACE NAME, or by any name whitelist
- mutate the input graph (every block is newly built)

OPACITY OF THE OLD NAME WHITELIST
---------------------------------
``opening_reasoner_v2.resolve_residential`` dispatches on
``name in ["living", "family_room"]`` and returns literal millimetre sizes. It
returns ``[]`` - silently - for any name not on its list. This module replaces
that dispatch with four semantic sources, none of which is a name:

1. EDGE TYPE       - a ``visual_connection`` to a site space is a glazing
                     obligation; a ``circulation`` edge to a site space is an
                     access obligation.
2. DOMAIN CROSSING - any building/site meeting creates an ENVELOPE boundary,
                     which is what makes the opening exterior at all.
3. CIRCULATION     - an interior ``circulation`` edge between two building
                     spaces only functions if an internal opening exists. This
                     intent is emitted nowhere else today.
4. DECLARED INTENT - ``daylight_priority`` / ``natural_ventilation`` /
                     ``privacy_level`` create obligations regardless of
                     adjacency, so a room with no edge at all still gets them.

Anything a semantic source cannot settle is emitted as ``pending`` with a named
reason, never guessed.

NUMERIC EXCLUSION
-----------------
The same two-guard strategy as ARCH-GEOMETRY-01: the semantic intent copied
from a node is cleaned as it is copied, and the whole finished RECORD is then
swept so no numeric leaf can survive. An opening that declares no size cannot
leak a size.

The sweep applies to the per-node records only. The two contract-level
summaries (``boundary_summary`` / ``opening_summary``) do contain integers, and
they are the ONLY numbers in the contract: they are aggregate TALLIES of
records, published deliberately so a reader never has to count, and they are
structurally incapable of being a dimension. Record-level counts are kept out
of the records for exactly that reason.
"""

from __future__ import annotations

from typing import Any, Mapping


OUTPUT_TYPE = "architectural_opening_boundary_intent"
OUTPUT_VERSION = "architectural_opening_boundary_intent_v1"

# Node kinds (mirrors the intent graph vocabulary).
NODE_BUILDING_SPACE = "building_space"
NODE_SITE_SPACE = "site_space"
NODE_VERTICAL_ELEMENT = "vertical_element"

# Edge types (mirrors the intent graph vocabulary).
EDGE_ADJACENCY = "adjacency"
EDGE_VISUAL = "visual_connection"
EDGE_CIRCULATION = "circulation"
EDGE_VERTICAL = "vertical_connection"
EDGE_VEHICLE = "vehicle_access"

# The two domain axes. ``domain`` alone is ambiguous: "site" is legal on both.
DOMAIN_BUILDING = "building"
DOMAIN_SITE = "site"
SPACE_DOMAINS = (DOMAIN_BUILDING, DOMAIN_SITE)

DOMAIN_AXIS_SPACE = "space"
DOMAIN_AXIS_CIRCULATION = "circulation"

# ---------------------------------------------------------------------------
# boundary taxonomy
# ---------------------------------------------------------------------------

# A building space meeting a site space: the building envelope.
BOUNDARY_ENVELOPE = "envelope_boundary"
# A building space meeting another building space: an internal partition.
BOUNDARY_INTERNAL = "internal_boundary"
# A circulation element meeting anything: a core interface.
BOUNDARY_CORE = "core_interface"
# A building/site meeting whose exterior character is not yet settled.
BOUNDARY_SITE_UNRESOLVED = "site_boundary_unresolved"
# A site space meeting another site space: an open-site edge.
BOUNDARY_SITE_OPEN = "site_open_boundary"

BOUNDARY_TYPES = (
    BOUNDARY_ENVELOPE,
    BOUNDARY_INTERNAL,
    BOUNDARY_CORE,
    BOUNDARY_SITE_UNRESOLVED,
    BOUNDARY_SITE_OPEN,
)

# Boundary exposures: is this boundary against the outside, or inside?
EXPOSURE_EXTERIOR = "exterior"
EXPOSURE_INTERIOR = "interior"
EXPOSURE_SITE_INTERNAL = "site_internal"
EXPOSURE_UNRESOLVED = "unresolved"
# No exterior boundary is entailed by the program. A statement about INTENT,
# never a claim that the space will have no windows.
EXPOSURE_INTERIOR_ONLY = "interior_only_as_far_as_intent_is_concerned"

# A boundary that sits on the building envelope carries the load of daylight,
# weather and privacy; an internal one does not.
ENVELOPE_BOUNDARIES = frozenset((BOUNDARY_ENVELOPE,))

# ---------------------------------------------------------------------------
# opening taxonomy (SEMANTIC ROLES - never a size, never a product)
# ---------------------------------------------------------------------------

# WHAT the opening does, not how big it is.
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

# Obligations an opening must eventually satisfy. Tokens, never quantities.
OBLIGATION_DAYLIGHT = "daylight_obligation"
OBLIGATION_NATURAL_VENTILATION = "natural_ventilation_obligation"
OBLIGATION_VIEW = "view_obligation"
OBLIGATION_PRIVACY_CONTROL = "privacy_control_obligation"
OBLIGATION_EGRESS = "egress_obligation"
OBLIGATION_FIRE_PROTECTION = "fire_protection_obligation"
OBLIGATION_GUARDING = "guarding_obligation"
OBLIGATION_WEATHER_TIGHTNESS = "weather_tightness_obligation"

# The physical treatment an opening must eventually reconcile with the
# boundary's own requirements. A separation requirement is NOT softened.
SEPARATION_REQUIRED = "separation_required"
SEPARATION_SHARED = "shared_circulation_permitted"
SEPARATION_NONE = "no_separation_requirement"

# ---------------------------------------------------------------------------
# states
# ---------------------------------------------------------------------------

STATUS_PENDING = "pending"
STATUS_RESOLVED = "resolved"
STATUS_FORBIDDEN = "forbidden"
STATUS_UNRESOLVED = "unresolved"

GEOMETRY_STATE_PENDING = "pending"
GEOMETRY_REASON_BOUNDARY = "boundary_geometry_not_authorized"
GEOMETRY_REASON_OPENING = "opening_geometry_not_authorized"

VEHICLE_ACCESS_PENDING = "pending"

STATE_CONTRACT_RESOLVED = "opening_boundary_intent_resolved"
STATE_CONTRACT_UNRESOLVED = "opening_boundary_intent_unresolved"

# Semantic vehicle signals - never a name list.
VEHICLE_ELEMENT_TYPES = ("ramp", "car_lift")
VEHICLE_SPACE_TYPES = frozenset(
    ("parking", "vehicle_space", "vehicle_circulation", "loading_space")
)
VEHICLE_PLACEMENT_PRIORITY = "vehicle_access"

# Roles that represent a means of egress and are therefore protected zones.
PROTECTED_CIRCULATION_ROLES = frozenset(
    (
        "primary_vertical_circulation",
        "required_vertical_circulation",
        "public_vertical_circulation",
        "shared_core_vertical_circulation",
    )
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
    """Copy declared program intent, dropping numeric entries.

    First of the two numeric guards. Kept identical in behaviour to the
    ARCH-GEOMETRY-01 guard so both contracts filter identically.
    """

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
    """Recursively remove every numeric leaf from a finished record.

    Second, structural numeric guard: it runs after the semantic projection, so
    a numeric-bearing block appearing anywhere upstream cannot leak through.
    Booleans are preserved - they are ``int`` subclasses but not dimensions.
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


def _domain_axis(node):
    """Space nodes use the building/site axis; vertical nodes the circulation
    axis. ``domain`` alone is ambiguous, so the axis is stated explicitly."""

    if node.get("kind") == NODE_VERTICAL_ELEMENT:
        return DOMAIN_AXIS_CIRCULATION

    return DOMAIN_AXIS_SPACE


def _space_domain(node):
    """The SPACE domain of a node, or None for a circulation node.

    Only a building/site crossing between two SPACE nodes is an envelope
    condition. A space reaching its own stair is NOT exterior - the graph
    flags that edge ``cross_domain`` because it compares raw domain strings
    across two different axes ("building" vs "residential"). Respecting the
    axis is what keeps a stair from being reported as a facade.
    """

    if node.get("kind") == NODE_VERTICAL_ELEMENT:
        return None

    domain = node.get("domain")

    return domain if domain in SPACE_DOMAINS else None


def _is_vertical(node):
    return node.get("kind") == NODE_VERTICAL_ELEMENT


def _space_type(node):
    return node.get("space_type") or node.get("element_type")


def _is_vehicle_node(node):
    """Semantic vehicle ELEMENT test - never a name list."""

    if not _is_vertical(node):
        return False

    return _space_type(node) in VEHICLE_ELEMENT_TYPES


def _is_vehicle_space(node):
    """Semantic vehicle SPACE test - never a name list.

    Mirrors the intent graph's semantic test so a parking space is recognised
    by its declared space type or placement priority, not by being called
    "parking".
    """

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
    """A protected zone is declared, and may also be implied by an egress role."""

    if node.get("protected_zone"):
        return True

    return node.get("role") in PROTECTED_CIRCULATION_ROLES


def _intent_block(status, reasons, **fields):
    block = {"status": status}
    block.update(fields)
    block["reasons"] = list(reasons)

    return block


def _pending_geometry(reason):
    return {"state": GEOMETRY_STATE_PENDING, "reason": reason}


# ---------------------------------------------------------------------------
# boundary derivation
# ---------------------------------------------------------------------------

def _boundary_type(self_axis, self_domain, other_axis, other_domain,
                   other_is_vehicle):
    """Classify a boundary from domain axes ONLY - never from a name.

    Returns ``(boundary_type, exposure)``.
    """

    # A circulation element meeting a space is a core interface, whatever
    # domain the space sits in.
    if self_axis == DOMAIN_AXIS_CIRCULATION or other_axis == DOMAIN_AXIS_CIRCULATION:
        return BOUNDARY_CORE, EXPOSURE_INTERIOR

    # Site to site: an open-site edge, internal to the site.
    if self_domain == DOMAIN_SITE and other_domain == DOMAIN_SITE:
        return BOUNDARY_SITE_OPEN, EXPOSURE_SITE_INTERNAL

    # Building to site: THE ENVELOPE. A vehicle meeting is handled separately
    # below because its access mode is a pending decision.
    if {self_domain, other_domain} == {DOMAIN_BUILDING, DOMAIN_SITE}:
        if other_is_vehicle:
            return BOUNDARY_SITE_UNRESOLVED, EXPOSURE_UNRESOLVED

        return BOUNDARY_ENVELOPE, EXPOSURE_EXTERIOR

    # Building to building: an internal partition.
    return BOUNDARY_INTERNAL, EXPOSURE_INTERIOR


def _boundary_obligations(boundary_type, exposure, self_node, other_node,
                          separation, reasons):
    """The obligations a boundary imposes, as tokens.

    The list is derived from the BOUNDARY TYPE and the participants' declared
    intent. It never states a quantity.
    """

    obligations = []

    if boundary_type in ENVELOPE_BOUNDARIES:
        # An envelope boundary is the only place daylight, view and weather
        # are at stake, and the only place a privacy control can be defeated
        # by a neighbour - so the obligation set is stated explicitly rather
        # than inferred from what happens to be declared.
        obligations.extend(
            (
                OBLIGATION_DAYLIGHT,
                OBLIGATION_VIEW,
                OBLIGATION_WEATHER_TIGHTNESS,
            )
        )
        reasons.append("envelope_boundary_carries_daylight_view_and_weather_load")

        self_intent = self_node.get("architectural_intent") or {}
        if not isinstance(self_intent, Mapping):
            self_intent = {}
        other_intent = other_node.get("architectural_intent") or {}
        if not isinstance(other_intent, Mapping):
            other_intent = {}

        if (
            self_intent.get("daylight_priority") == "high"
            or other_intent.get("daylight_priority") == "high"
        ):
            reasons.append("daylight_priority_declared_high_on_an_envelope")

        if (
            self_intent.get("natural_ventilation") is True
            or other_intent.get("natural_ventilation") is True
        ):
            obligations.append(OBLIGATION_NATURAL_VENTILATION)
            reasons.append("natural_ventilation_declared")

        # A privacy-sensitive space against an exterior edge needs control; the
        # requirement is recorded, never resolved into a device or a size.
        privacy = self_intent.get("privacy_level")
        if privacy in ("high", "medium", "private"):
            obligations.append(OBLIGATION_PRIVACY_CONTROL)
            reasons.append("privacy_level_requires_control_on_envelope")

    if boundary_type == BOUNDARY_INTERNAL:
        # An internal boundary must remain separable where the program demands
        # it. The separation state is carried, not applied.
        if separation == SEPARATION_REQUIRED:
            obligations.append(OBLIGATION_PRIVACY_CONTROL)
            reasons.append("internal_boundary_must_preserve_separation")

    if boundary_type == BOUNDARY_CORE:
        # A core interface is a means of egress.
        obligations.extend((OBLIGATION_EGRESS, OBLIGATION_FIRE_PROTECTION))
        reasons.append("circulation_core_interface_is_a_means_of_egress")

    if boundary_type == BOUNDARY_SITE_UNRESOLVED:
        reasons.append("vehicle_boundary_exposure_pending_mode_decision")

    if boundary_type == BOUNDARY_SITE_OPEN:
        reasons.append("site_internal_edge_has_no_envelope_obligation")

    return sorted(set(obligations))


def _boundary_separation(self_node, other_node, circulation_separation):
    """Carry the mixed-use separation obligation across a boundary.

    A shared core and a domain-confined core must not be flattened together: a
    boundary that crosses from one use to another inherits
    ``separation_required`` even when the two sides sit on the same floor.
    """

    separation = circulation_separation
    if not isinstance(separation, Mapping):
        return SEPARATION_NONE

    if not separation.get("separation_required"):
        return SEPARATION_NONE

    self_domain = self_node.get("domain")
    other_domain = other_node.get("domain")

    # A vertical node's domain names the use its circulation serves, so a
    # shared core meeting a use domain is a SHARED case, and a use domain
    # meeting a different use domain is a SEPARATION case.
    if self_domain and other_domain and self_domain != other_domain:
        return SEPARATION_REQUIRED

    return SEPARATION_SHARED


def _build_boundary(
    node, other, edge, node_by_id, circulation_separation, reasons
):
    """Build ONE boundary record for a node/other meeting."""

    self_axis = _domain_axis(node)
    other_axis = _domain_axis(other)

    boundary_type, exposure = _boundary_type(
        self_axis,
        _space_domain(node),
        other_axis,
        _space_domain(other),
        _is_vehicle_node(other) or _is_vehicle_space(other),
    )

    separation = _boundary_separation(node, other, circulation_separation)
    obligations = _boundary_obligations(
        boundary_type, exposure, node, other, separation, reasons
    )

    # A boundary records which domain pair it separates. This is what keeps a
    # building/site boundary distinguishable from a building/building one even
    # when both are labelled "interior".
    domain_pair = sorted(
        str(value)
        for value in (
            _space_domain(node) or node.get("domain"),
            _space_domain(other) or other.get("domain"),
        )
        if value
    )

    return {
        "boundary_id": f"{boundary_type}:{node['node_id']}->{other['node_id']}",
        "boundary_type": boundary_type,
        "exposure": exposure,
        "axis": self_axis,
        "domain_pair": domain_pair,
        "counterpart_node_id": other["node_id"],
        "counterpart_kind": other.get("kind"),
        "counterpart_domain": other.get("domain"),
        "edge_type": edge.get("type"),
        "edge_status": edge.get("status"),
        "separation": separation,
        "obligations": obligations,
        "protected_zone": bool(
            _is_protected_zone(node) or _is_protected_zone(other)
        ),
        "is_envelope": boundary_type in ENVELOPE_BOUNDARIES,
        "geometry_status": _pending_geometry(GEOMETRY_REASON_BOUNDARY),
        "status": (
            STATUS_PENDING
            if exposure == EXPOSURE_UNRESOLVED
            else STATUS_RESOLVED
        ),
        "reasons": list(reasons),
    }


def _boundaries_for(node, node_by_id, edges, circulation_separation, reasons):
    """Every boundary this node participates in, deterministically ordered."""

    boundaries = []
    for edge in edges:
        if edge.get("from") != node["node_id"] and edge.get("to") != node["node_id"]:
            continue

        other_id = (
            edge["to"] if edge.get("from") == node["node_id"] else edge["from"]
        )
        other = node_by_id.get(other_id)
        if other is None:
            # A dangling edge is reported, never invented into a boundary.
            reasons.append("boundary_endpoint_not_a_graph_node")
            continue

        edge_reasons = [f"boundary_from_edge:{edge.get('type')}"]
        boundaries.append(
            _build_boundary(
                node,
                other,
                edge,
                node_by_id,
                circulation_separation,
                edge_reasons,
            )
        )

    boundaries.sort(key=lambda boundary: boundary["boundary_id"])

    return boundaries


# ---------------------------------------------------------------------------
# opening derivation
# ---------------------------------------------------------------------------

def _opening_for(node, boundary, role, obligations, reasons):
    """Build ONE semantic opening intent on ONE boundary."""

    opening_reasons = list(reasons)
    if boundary["exposure"] == EXPOSURE_UNRESOLVED:
        opening_reasons.append(
            "opening_exposure_unresolved_pending_mode_decision"
        )

    status = STATUS_PENDING
    if boundary["boundary_type"] == BOUNDARY_SITE_OPEN:
        # A site-to-site edge is not an opening at all; it is recorded so the
        # absence is a declared decision rather than an omission.
        status = STATUS_FORBIDDEN
        opening_reasons.append("open_site_edge_hosts_no_opening")

    return {
        "opening_id": f"{role}:{node['node_id']}->{boundary['counterpart_node_id']}",
        "opening_role": role,
        "boundary_id": boundary["boundary_id"],
        "boundary_type": boundary["boundary_type"],
        "exposure": boundary["exposure"],
        "counterpart_node_id": boundary["counterpart_node_id"],
        "obligations": sorted(set(obligations)),
        "separation": boundary["separation"],
        "serves_protected_zone": boundary["protected_zone"],
        "geometry_status": _pending_geometry(GEOMETRY_REASON_OPENING),
        "dimensional_status": STATUS_PENDING,
        "status": status,
        "reasons": sorted(set(opening_reasons)),
    }


def _openings_for(node, boundaries, edges, reasons):
    """Derive opening intent from four semantic sources - never from a name."""

    openings = []

    for boundary in boundaries:
        boundary_id = boundary["boundary_id"]
        edge_type = boundary["edge_type"]
        boundary_type = boundary["boundary_type"]
        obligations = boundary["obligations"]

        # SOURCE 1 + 2: edge type against a boundary that is exterior.
        if edge_type == EDGE_VISUAL and boundary["is_envelope"]:
            openings.append(
                _opening_for(
                    node,
                    boundary,
                    OPENING_GLAZING,
                    [
                        OBLIGATION_DAYLIGHT,
                        OBLIGATION_VIEW,
                        *obligations,
                    ],
                    ["visual_connection_across_the_envelope_requires_glazing"],
                )
            )
        elif edge_type == EDGE_CIRCULATION and boundary["is_envelope"]:
            openings.append(
                _opening_for(
                    node,
                    boundary,
                    OPENING_EXTERNAL_ACCESS,
                    [OBLIGATION_EGRESS, OBLIGATION_WEATHER_TIGHTNESS, *obligations],
                    ["circulation_connection_across_the_envelope_requires_access"],
                )
            )
        # SOURCE 3: an interior circulation edge only functions with a doorway.
        elif edge_type == EDGE_CIRCULATION and boundary_type == BOUNDARY_INTERNAL:
            openings.append(
                _opening_for(
                    node,
                    boundary,
                    OPENING_INTERNAL_DOORWAY,
                    [*obligations],
                    ["internal_circulation_connection_requires_a_doorway"],
                )
            )
        # A vertical connection is a core interface: the opening is the access
        # to the core, and any protected-zone obligation rides on it.
        elif edge_type == EDGE_VERTICAL and boundary_type == BOUNDARY_CORE:
            core_obligations = [*obligations]
            if boundary["protected_zone"]:
                core_obligations.append(OBLIGATION_FIRE_PROTECTION)
            openings.append(
                _opening_for(
                    node,
                    boundary,
                    OPENING_VERTICAL_ACCESS,
                    core_obligations,
                    ["vertical_connection_requires_core_access"],
                )
            )
        # The vehicle mode is a PENDING decision (ramp vs car lift). The
        # opening intent is emitted pending and never resolved here.
        elif edge_type == EDGE_VEHICLE:
            openings.append(
                _opening_for(
                    node,
                    boundary,
                    OPENING_VEHICLE_ACCESS,
                    [OBLIGATION_GUARDING],
                    [
                        "vehicle_access_opening_mode_pending",
                        "vehicle_access_mode_not_resolved",
                    ],
                )
            )

    return openings


def _declared_opening_obligations(node, boundaries, reasons):
    """SOURCE 4: obligations declared by the space itself.

    A space may declare a daylight or ventilation need with NO adjacency at
    all. ``opening_reasoner_v2`` cannot express this: it derives openings from
    the space NAME, so a space whose name is not on its list gets ``[]`` even
    when its own intent says it needs daylight. That silent empty result is the
    specific gap this block closes.
    """

    intent = node.get("architectural_intent")
    if not isinstance(intent, Mapping):
        intent = {}

    obligations = []
    if intent.get("daylight_priority") == "high":
        obligations.append(OBLIGATION_DAYLIGHT)
        reasons.append("daylight_declared_high")
    if intent.get("natural_ventilation") is True:
        obligations.append(OBLIGATION_NATURAL_VENTILATION)
        reasons.append("natural_ventilation_declared")
    if intent.get("privacy_level") in ("high", "private"):
        obligations.append(OBLIGATION_PRIVACY_CONTROL)
        reasons.append("privacy_level_declared_high")

    if not obligations:
        return None

    envelope_boundary_ids = sorted(
        boundary["boundary_id"]
        for boundary in boundaries
        if boundary["is_envelope"]
    )

    if envelope_boundary_ids:
        status = STATUS_RESOLVED
        reasons.append("declared_obligation_bound_to_a_resolved_envelope")
    else:
        # No envelope boundary means no host is known. The obligation is real
        # but unplaceable, and is declared unresolved rather than dropped.
        status = STATUS_UNRESOLVED
        reasons.append("declared_opening_obligation_has_no_envelope_boundary")

    return {
        "obligation_scope": "declared_by_space_intent",
        "obligations": sorted(set(obligations)),
        "candidate_boundary_ids": envelope_boundary_ids,
        "host_status": (
            STATUS_RESOLVED if envelope_boundary_ids else STATUS_UNRESOLVED
        ),
        "geometry_status": _pending_geometry(GEOMETRY_REASON_OPENING),
        "dimensional_status": STATUS_PENDING,
        "status": status,
        "reasons": sorted(set(reasons)),
    }


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def build_opening_boundary_intent_contract(graph):
    """Project an Architectural Intent Graph into a boundary + opening contract.

    Returns a metadata-only contract with one record per graph node, in graph
    node order. Each record carries the boundaries the node participates in and
    the semantic opening obligations those boundaries create. Every geometry
    block is ``pending``; no coordinate, no polygon and no dimension exists.

    Pure function: the input graph is never mutated. Malformed input raises
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

    circulation_separation = graph.get("circulation_separation")

    contract_reasons = []
    records = []

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

        boundaries = _boundaries_for(
            node,
            node_by_id,
            edges,
            circulation_separation,
            node_reasons,
        )
        openings = _openings_for(node, boundaries, edges, node_reasons)
        declared = _declared_opening_obligations(node, boundaries, node_reasons)

        self_domain = _space_domain(node)
        axis = _domain_axis(node)

        envelope_boundaries = [
            boundary["boundary_id"]
            for boundary in boundaries
            if boundary["is_envelope"]
        ]

        if envelope_boundaries:
            exposure_status = EXPOSURE_EXTERIOR
        elif node.get("kind") == NODE_SITE_SPACE:
            # A site space that hosts or serves vehicle access has an exposure
            # that is still PENDING: the ramp-vs-car-lift mode decides whether
            # the boundary to it is a graded opening or a shaft, so its
            # exposure must not be silently flattened to "site_internal".
            if _is_vehicle_node(node) or _is_vehicle_space(node):
                exposure_status = EXPOSURE_UNRESOLVED
                node_reasons.append(
                    "site_space_vehicle_exposure_pending_mode_decision"
                )
            else:
                exposure_status = EXPOSURE_SITE_INTERNAL
        else:
            # No envelope boundary is entailed by the program. This is a
            # statement about INTENT, not about walls, so it stays a declared
            # unknown rather than being resolved to "no windows".
            exposure_status = EXPOSURE_INTERIOR_ONLY

        record = {
            "node_id": node_id,
            "space_identity": {
                "name": node.get("name"),
                "canonical_name": node.get("canonical_name"),
                "kind": node.get("kind"),
                "space_type": _space_type(node),
            },
            "domain": node.get("domain"),
            "domain_axis": axis,
            "space_domain": self_domain,
            "floor": node.get("floor"),
            "semantic_role": node.get("role"),
            "is_protected_zone": _is_protected_zone(node),
            "declared_intent": declared_intent,
            "exposure_status": exposure_status,
            "boundaries": boundaries,
            "opens": openings,
            "declared_opening_obligations": declared,
            "geometry_status": _pending_geometry(GEOMETRY_REASON_OPENING),
        }

        # Second numeric guard: sweep the FINISHED record. Whatever a future
        # graph change surfaces, no numeric leaf can reach the contract.
        #
        # NOTE: boundary_count / opening_count are intentionally NOT fields of
        # the record. A count is structurally a number, so putting one in the
        # record would make the sweep fire on every node and would also give a
        # consumer a number that could be mistaken for a measurement. The counts
        # are published in ``boundary_summary`` / ``opening_summary`` instead,
        # outside the swept records.
        dropped_paths = []
        record = _strip_numeric_leaves(record, dropped_paths)
        if dropped_paths:
            contract_reasons.append(
                "numeric_values_stripped_at_contract_boundary"
            )

        records.append(record)
        contract_reasons.extend(intent_reasons)
        contract_reasons.extend(node_reasons)

        if not boundaries:
            contract_reasons.append("node_has_no_boundary")

    # --- contract-level pending decisions (propagated, never resolved) -----
    pending_decisions = []
    vehicle_access = graph.get("vehicle_access")
    if isinstance(vehicle_access, Mapping) and vehicle_access.get("status") == VEHICLE_ACCESS_PENDING:
        pending_decisions.append(
            {
                "decision": "vehicle_access_opening_mode",
                "status": VEHICLE_ACCESS_PENDING,
                "candidates": list(vehicle_access.get("candidates", [])),
                "reasons": ["vehicle_access_opening_mode_not_resolved"],
            }
        )

    for record in records:
        for opening in record["opens"]:
            if opening["opening_role"] == OPENING_VEHICLE_ACCESS:
                pending_decisions.append(
                    {
                        "decision": f"vehicle_access_opening:{opening['opening_id']}",
                        "status": VEHICLE_ACCESS_PENDING,
                        "candidates": [],
                        "reasons": ["vehicle_access_opening_mode_not_resolved"],
                    }
                )

    for record in records:
        declared = record["declared_opening_obligations"]
        if declared and declared["host_status"] == STATUS_UNRESOLVED:
            pending_decisions.append(
                {
                    "decision": f"opening_host:{record['node_id']}",
                    "status": STATUS_UNRESOLVED,
                    "candidates": [],
                    "reasons": ["declared_opening_obligation_has_no_envelope_boundary"],
                }
            )

    boundary_counts = {}
    for record in records:
        for boundary in record["boundaries"]:
            boundary_counts[boundary["boundary_type"]] = (
                boundary_counts.get(boundary["boundary_type"], 0) + 1
            )

    opening_counts = {}
    for record in records:
        for opening in record["opens"]:
            opening_counts[opening["opening_role"]] = (
                opening_counts.get(opening["opening_role"], 0) + 1
            )

    return {
        "type": OUTPUT_TYPE,
        "version": OUTPUT_VERSION,
        "node_records": records,
        "boundary_summary": {
            "by_type": dict(sorted(boundary_counts.items())),
            "envelope_boundary_count": sum(
                1
                for record in records
                for boundary in record["boundaries"]
                if boundary["is_envelope"]
            ),
        },
        "opening_summary": {
            "by_role": dict(sorted(opening_counts.items())),
            "forbidden_count": sum(
                1
                for record in records
                for opening in record["opens"]
                if opening["status"] == STATUS_FORBIDDEN
            ),
        },
        "circulation_separation": circulation_separation,
        "pending_decisions": pending_decisions,
        "semantics": {
            "metadata_only": True,
            "geometry_created": False,
            "coordinates_created": False,
            "dimensions_created": False,
            "polygons_created": False,
            "boundaries_created": False,
            "openings_created": False,
            "host_walls_assigned": False,
            "decisions_resolved": False,
        },
        "status": {
            "state": STATE_CONTRACT_RESOLVED if records else STATE_CONTRACT_UNRESOLVED,
            "reasons": sorted(set(contract_reasons)),
        },
    }


# ---------------------------------------------------------------------------
# queries
# ---------------------------------------------------------------------------

def record_for_node(contract, node_id):
    """Return the boundary/opening record for one node, or None."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")

    for record in contract.get("node_records", []):
        if record.get("node_id") == node_id:
            return record

    return None


def boundaries_of_type(contract, boundary_type):
    """Return every boundary of one type, across all records."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")
    if boundary_type not in BOUNDARY_TYPES:
        raise ValueError(
            "boundary_type must be one of: " + ", ".join(BOUNDARY_TYPES)
        )

    return [
        boundary
        for record in contract.get("node_records", [])
        for boundary in record.get("boundaries", [])
        if boundary.get("boundary_type") == boundary_type
    ]


def openings_with_role(contract, opening_role):
    """Return every opening with one semantic role, across all records."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")
    if opening_role not in OPENING_ROLES:
        raise ValueError(
            "opening_role must be one of: " + ", ".join(OPENING_ROLES)
        )

    return [
        opening
        for record in contract.get("node_records", [])
        for opening in record.get("opens", [])
        if opening.get("opening_role") == opening_role
    ]


def envelope_boundaries(contract):
    """Return every building-envelope boundary in the contract."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")

    return [
        boundary
        for record in contract.get("node_records", [])
        for boundary in record.get("boundaries", [])
        if boundary.get("is_envelope")
    ]


def pending_openings(contract):
    """Return every opening whose geometry is still pending."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")

    return [
        opening
        for record in contract.get("node_records", [])
        for opening in record.get("opens", [])
        if (opening.get("geometry_status") or {}).get("state")
        == GEOMETRY_STATE_PENDING
    ]
