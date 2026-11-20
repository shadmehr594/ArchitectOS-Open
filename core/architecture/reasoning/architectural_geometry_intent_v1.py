"""Architectural Geometry Intent Contract v1 (ARCH-GEOMETRY-01).

The contract between SEMANTIC architecture and FUTURE geometry generation. It
projects the Architectural Intent Graph into one geometry-intent record per
node, stating WHAT geometry will eventually be required and WHICH semantic
obligations it must satisfy - and nothing about how it looks.

This module deliberately does NOT:

- create geometry of any kind
- generate walls, slabs, openings, rooms or meshes
- produce any coordinate (``x`` / ``y`` / ``z``) or polygon
- produce any dimension (width, depth, height, area, rise, run, slope)
- read or write CAD, DWG, IFC or BIM data
- read the filesystem, use randomness, UUIDs or timestamps
- resolve a pending decision
- mutate the input graph (every block is newly built)

GEOMETRY IS ALWAYS PENDING
--------------------------
Every geometry block reports ``status: "pending"`` and every record carries a
pending ``geometry_status``.

A NUMERIC VALUE IS STRUCTURALLY EXCLUDED, IN TWO PLACES
-------------------------------------------------------
Program intent is cleaned as it is copied (``_non_numeric_intent``), and the
whole projected record is then swept (``_strip_numeric_leaves``) before it
leaves this module. The second guard exists because the first one is
incomplete on its own: a space node's source record carries
``resolved_dimensions`` and ``dimensional_requirements`` in the spatial
contract's ``metadata``, and those blocks reach this module only insofar as the
graph surfaces them. Relying on the graph node builder to keep dropping them
would make "no dimensions" an incidental property of an upstream module rather
than a guarantee of this contract. The sweep makes the guarantee structural:
whatever a future graph change surfaces, no numeric leaf survives here.

PRESERVED FROM THE GRAPH
------------------------
- site / building separation (each record keeps its node's domain)
- vertical relationships (vertical-element nodes appear in
  ``circulation_requirements.vertical_nodes``)
- protected zones (``geometry_requirements.protected_zone``)
- vehicle pending states (``circulation_requirements.vehicle_access_status``)

TWO DOMAIN AXES
---------------
``domain`` alone is ambiguous: a space node uses the building/site axis while a
vertical node uses the circulation axis, and ``"site"`` is a legal value on
BOTH (a space node placed at site level, and the vehicle element that serves
it). Every record therefore also carries ``domain_axis``. Only a
building/site crossing between two SPACE nodes counts as cross-domain — a room
reaching its own stair is internal circulation, not an exterior condition.
"""

from __future__ import annotations

from typing import Any, Mapping


OUTPUT_TYPE = "architectural_geometry_intent"
OUTPUT_VERSION = "architectural_geometry_intent_v1"

NODE_BUILDING_SPACE = "building_space"
NODE_SITE_SPACE = "site_space"
NODE_VERTICAL_ELEMENT = "vertical_element"

DOMAIN_BUILDING = "building"
DOMAIN_SITE = "site"

EDGE_ADJACENCY = "adjacency"
EDGE_VISUAL = "visual_connection"
EDGE_CIRCULATION = "circulation"
EDGE_VERTICAL = "vertical_connection"
EDGE_VEHICLE = "vehicle_access"

STATUS_PENDING = "pending"
GEOMETRY_STATE_PENDING = "pending"
GEOMETRY_REASON = "geometry_generation_not_authorized"

# Semantic opening intents (tokens only - never an opening, never a size).
OPENING_EXTERIOR_GLAZING = "exterior_glazing_intent"
OPENING_EXTERIOR_ACCESS = "exterior_access_intent"
OPENING_DAYLIGHT_PRIORITY_HIGH = "daylight_priority_high"

STATE_RESOLVED = "geometry_intent_resolved"
STATE_UNRESOLVED = "geometry_intent_unresolved"


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


SPACE_DOMAINS = (DOMAIN_BUILDING, DOMAIN_SITE)

DOMAIN_AXIS_SPACE = "space"
DOMAIN_AXIS_CIRCULATION = "circulation"


def _domain_axis(node):
    """Space nodes use the building/site axis; vertical nodes the circulation
    axis. ``domain`` alone is ambiguous, so the axis is stated explicitly."""

    if node.get("kind") == NODE_VERTICAL_ELEMENT:
        return DOMAIN_AXIS_CIRCULATION

    return DOMAIN_AXIS_SPACE


def _space_domain(node):
    """The SPACE domain of a node, or None for a circulation node.

    Only a building/site crossing counts as an exterior (cross-domain)
    adjacency - a space reaching its own stair is NOT exterior.
    """

    if node.get("kind") == NODE_VERTICAL_ELEMENT:
        return None

    domain = node.get("domain")

    return domain if domain in SPACE_DOMAINS else None


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _non_numeric_intent(intent, reasons):
    """Copy program intent, DROPPING any numeric entry.

    This is the first of the two numeric guards. Any entry whose value is
    numeric is dropped rather than passed on, so a dimension cannot ride along
    inside free-form program metadata.
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
    """Recursively remove every numeric leaf from a projected value.

    This is the second, structural numeric guard. It runs over the FINISHED
    record - after the semantic projection - so it cannot be defeated by a new
    numeric-bearing block appearing upstream. Booleans are preserved (they are
    ``int`` subclasses but are not dimensions). A mapping key whose value is
    numeric is removed entirely; a list element that is numeric is skipped.

    ``dropped`` collects the dotted paths of everything removed so the removal
    is reported rather than silent.
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


def _semantic_role(node):
    """Declared role, falling back to space_type / element type."""

    role = node.get("role")
    if isinstance(role, str) and role.strip():
        return role

    fallback = node.get("space_type") or node.get("element_type")
    if isinstance(fallback, str) and fallback.strip():
        return fallback

    return None


def _pending(status_reasons):
    return {"status": STATUS_PENDING, "reasons": list(status_reasons)}


# ---------------------------------------------------------------------------
# block builders
# ---------------------------------------------------------------------------

def _geometry_requirements(node, reasons):
    intent = node.get("architectural_intent")
    if not isinstance(intent, Mapping):
        intent = {}

    intent_reasons = []
    semantic_intent = _non_numeric_intent(intent, intent_reasons)

    requirements = []
    if node.get("protected_zone"):
        requirements.append("protected_zone_geometry_required")
    if semantic_intent.get("daylight_priority") == "high":
        requirements.append("daylight_geometry_priority_high")
    if semantic_intent.get("natural_ventilation") is True:
        requirements.append("natural_ventilation_required")

    block = {
        "status": STATUS_PENDING,
        "requires_geometry": True,
        "dimensional_status": STATUS_PENDING,
        "protected_zone": bool(node.get("protected_zone", False)),
        "semantic_intent": semantic_intent,
        "requirements": requirements,
        "reasons": [
            "geometry_generation_deferred_to_a_later_phase",
            *intent_reasons,
        ],
    }
    reasons.extend(intent_reasons)

    return block


def _adjacency_requirements(node_id, edges, node_by_id, reasons):
    adjacent = []
    visual = []
    cross_domain = []

    self_domain = _space_domain(node_by_id.get(node_id, {}))

    for edge in edges:
        if edge["from"] != node_id and edge["to"] != node_id:
            continue

        other_id = edge["to"] if edge["from"] == node_id else edge["from"]

        if edge["type"] == EDGE_ADJACENCY:
            adjacent.append(other_id)
        elif edge["type"] == EDGE_VISUAL:
            visual.append(other_id)

        other_domain = _space_domain(node_by_id.get(other_id, {}))
        if (
            self_domain is not None
            and other_domain is not None
            and self_domain != other_domain
        ):
            cross_domain.append(other_id)

    if cross_domain:
        reasons.append("cross_domain_adjacency_requires_exterior_treatment")

    return {
        "status": STATUS_PENDING,
        "adjacent_nodes": sorted(set(adjacent)),
        "visual_connections": sorted(set(visual)),
        "cross_domain_nodes": sorted(set(cross_domain)),
        "reasons": list(reasons),
    }


def _opening_requirements(node, edges, adjacency, reasons):
    intents = []

    cross_domain = set(adjacency["cross_domain_nodes"])

    if node.get("kind") != NODE_VERTICAL_ELEMENT and cross_domain:
        for edge in edges:
            if edge["from"] != node["node_id"] and edge["to"] != node["node_id"]:
                continue

            other_id = (
                edge["to"] if edge["from"] == node["node_id"] else edge["from"]
            )
            if other_id not in cross_domain:
                continue

            if (
                edge["type"] == EDGE_VISUAL
                and OPENING_EXTERIOR_GLAZING not in intents
            ):
                intents.append(OPENING_EXTERIOR_GLAZING)
            elif (
                edge["type"] == EDGE_CIRCULATION
                and OPENING_EXTERIOR_ACCESS not in intents
            ):
                intents.append(OPENING_EXTERIOR_ACCESS)

        intent = node.get("architectural_intent")
        if (
            isinstance(intent, Mapping)
            and intent.get("daylight_priority") == "high"
        ):
            intents.append(OPENING_DAYLIGHT_PRIORITY_HIGH)

    if intents:
        reasons.append("opening_intent_requires_future_geometry")

    return {
        "status": STATUS_PENDING,
        "opening_intents": intents,
        "reasons": list(reasons),
    }


def _circulation_requirements(node_id, edges, reasons):
    circulation = []
    vertical = []
    vehicle = []
    vehicle_status = None

    for edge in edges:
        if edge["from"] != node_id and edge["to"] != node_id:
            continue

        other_id = edge["to"] if edge["from"] == node_id else edge["from"]

        if edge["type"] == EDGE_CIRCULATION:
            circulation.append(other_id)
        elif edge["type"] == EDGE_VERTICAL:
            vertical.append(other_id)
        elif edge["type"] == EDGE_VEHICLE:
            vehicle.append(other_id)
            # A vehicle element (ramp / car lift) IS a vertical element: it
            # moves something between levels. The graph wires vehicle elements
            # with a dedicated ``vehicle_access`` edge instead of a
            # ``vertical_connection`` edge, so this is the only place the
            # relationship can be recovered. Without this, a consumer asking
            # "which vertical elements serve this node?" would miss the ramp
            # entirely - the two edge types are a distinction of PENDING
            # DECISION (ramp vs car lift), not of verticality.
            if other_id not in vertical:
                vertical.append(other_id)
            # The vehicle access MODE is a pending decision; it is propagated,
            # never resolved here.
            if edge.get("status") == STATUS_PENDING:
                vehicle_status = STATUS_PENDING

    if vehicle_status == STATUS_PENDING:
        reasons.append("vehicle_access_mode_pending_propagated")

    return {
        "status": STATUS_PENDING,
        "circulation_nodes": sorted(set(circulation)),
        "vertical_nodes": sorted(set(vertical)),
        "vehicle_nodes": sorted(set(vehicle)),
        "vehicle_access_status": vehicle_status,
        "reasons": list(reasons),
    }


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def build_geometry_intent_contract(graph):
    """Project an Architectural Intent Graph into a geometry intent contract.

    Returns a metadata-only contract with one record per graph node, in graph
    node order. Every geometry block is ``pending``, no coordinate and no
    dimension is produced, and no pending decision is resolved.

    Pure function: the input graph is never mutated. Malformed input raises
    ``ValueError``.
    """

    if not isinstance(graph, Mapping):
        raise ValueError("graph must be a mapping")
    if graph.get("type") != "architectural_intent_graph":
        raise ValueError(
            "graph.type must be 'architectural_intent_graph'"
        )

    nodes = _sequence(graph.get("nodes"), "graph nodes")
    edges = _sequence(graph.get("edges"), "graph edges")

    for edge in edges:
        if not isinstance(edge, Mapping):
            raise ValueError("graph edges must be mappings")

    node_by_id = {
        node["node_id"]: node
        for node in nodes
        if isinstance(node, Mapping) and node.get("node_id")
    }

    contract_reasons = []
    records = []

    for node in nodes:
        if not isinstance(node, Mapping):
            raise ValueError("graph nodes must be mappings")

        node_id = node.get("node_id")
        if not node_id:
            raise ValueError("graph node is missing node_id")

        node_reasons = []

        geometry_requirements = _geometry_requirements(node, node_reasons)
        adjacency = _adjacency_requirements(
            node_id, edges, node_by_id, node_reasons
        )
        opening = _opening_requirements(
            node, edges, adjacency, node_reasons
        )
        circulation = _circulation_requirements(node_id, edges, node_reasons)

        geometry_status = node.get("geometry_status")
        if not isinstance(geometry_status, Mapping):
            geometry_status = {
                "state": GEOMETRY_STATE_PENDING,
                "reason": GEOMETRY_REASON,
            }
        else:
            geometry_status = dict(geometry_status)
            if geometry_status.get("state") != GEOMETRY_STATE_PENDING:
                # This phase never authorises geometry, whatever the source says.
                geometry_status = {
                    "state": GEOMETRY_STATE_PENDING,
                    "reason": GEOMETRY_REASON,
                }
                node_reasons.append("source_geometry_state_forced_pending")

        record = {
            "node_id": node_id,
            "space_identity": {
                "name": node.get("name"),
                "canonical_name": node.get("canonical_name"),
                "kind": node.get("kind"),
            },
            "domain": node.get("domain"),
            "domain_axis": _domain_axis(node),
            "floor": node.get("floor"),
            "semantic_role": _semantic_role(node),
            "geometry_requirements": geometry_requirements,
            "adjacency_requirements": adjacency,
            "opening_requirements": opening,
            "circulation_requirements": circulation,
            "geometry_status": geometry_status,
        }

        # Second numeric guard: sweep the FINISHED record. Whatever a future
        # graph change surfaces, no numeric leaf can reach the contract.
        dropped_paths = []
        record = _strip_numeric_leaves(record, dropped_paths)
        if dropped_paths:
            contract_reasons.append(
                "numeric_values_stripped_at_contract_boundary"
            )

        records.append(record)

        if geometry_requirements["reasons"]:
            contract_reasons.extend(geometry_requirements["reasons"])

        # Node-level reasons (including a forced-pending source state) are
        # surfaced on the contract so they cannot be lost.
        contract_reasons.extend(node_reasons)

    return {
        "type": OUTPUT_TYPE,
        "version": OUTPUT_VERSION,
        "node_intents": records,
        "domains": dict(graph.get("domains") or {}),
        "circulation_separation": graph.get("circulation_separation"),
        "pending_decisions": list(graph.get("pending_decisions") or []),
        "semantics": {
            "metadata_only": True,
            "geometry_created": False,
            "coordinates_created": False,
            "dimensions_created": False,
            "polygons_created": False,
            "openings_generated": False,
            "walls_generated": False,
            "slabs_generated": False,
            "decisions_resolved": False,
        },
        "status": {
            "state": STATE_RESOLVED if records else STATE_UNRESOLVED,
            "reasons": sorted(set(contract_reasons)),
        },
    }


def intent_for_node(contract, node_id):
    """Return the geometry intent record for one node, or None."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")

    for record in contract.get("node_intents", []):
        if record.get("node_id") == node_id:
            return record

    return None


def records_for_domain(contract, domain, axis=None):
    """Return the intent records for one domain.

    ``axis`` is OPTIONAL: pass ``"space"`` to exclude vertical-element records
    (whose ``domain`` is a circulation domain that can also be ``"site"``).
    """

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")

    if axis is not None and axis not in (
        DOMAIN_AXIS_SPACE,
        DOMAIN_AXIS_CIRCULATION,
    ):
        raise ValueError(
            "axis must be 'space', 'circulation' or None"
        )

    return [
        record
        for record in contract.get("node_intents", [])
        if record.get("domain") == domain
        and (axis is None or record.get("domain_axis") == axis)
    ]


def pending_geometry_records(contract):
    """Return every record whose geometry is still pending."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")

    return [
        record
        for record in contract.get("node_intents", [])
        if (record.get("geometry_status") or {}).get("state")
        == GEOMETRY_STATE_PENDING
    ]
