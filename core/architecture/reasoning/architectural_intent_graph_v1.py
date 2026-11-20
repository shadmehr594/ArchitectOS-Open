"""Unified Architectural Intent Graph (ARCH-CONTRACT-02).

Fuses the three architectural reasoning contracts into ONE graph:

    architectural_spatial_contract_v1  -> building-space and site-space NODES
    vertical_circulation_intelligence_v2 -> vertical-element NODES
    LayoutReasoner connections          -> relationship EDGES

Node kinds:

    building_space
    site_space
    vertical_element

Edge types (the graph vocabulary):

    adjacency
    visual_connection
    circulation
    vertical_connection
    vehicle_access

This module is SEMANTIC INTENT ONLY. It deliberately does NOT:

- create geometry, coordinates, polygons or placements
- decide any dimension
- resolve a pending decision (vehicle access mode stays PENDING)
- read the filesystem, use randomness, UUIDs or timestamps
- mutate any input (every node and edge is newly built)
- modify the three source contracts or their producers

DOMAIN SEPARATION IS PRESERVED
------------------------------
A node keeps the domain of its own contract, and the graph records which nodes
belong to which domain. A cross-domain EDGE is allowed and is flagged, because a
building space may legitimately have a visual connection to a site space - but a
site node is never re-classified as a building node, or the reverse.

NOTE ON THE ``domain`` FIELD - two axes, disambiguated by ``kind``:

- a SPACE node (``building_space`` / ``site_space``) uses the SPACE axis:
  ``"building"`` or ``"site"``;
- a VERTICAL element node uses the CIRCULATION axis: ``"residential"``,
  ``"commercial"``, ``"mixed_use"`` or ``"site"`` - it states which domain's
  circulation the element serves, which is what makes a mixed-use shared core
  distinguishable from its domain-confined circulation.

PENDING DECISIONS ARE PROPAGATED, NOT RESOLVED
---------------------------------------------
Every node carries ``geometry_status`` (pending). A ``vehicle_access`` edge is
emitted with ``status: "pending"`` because the ramp-vs-car-lift mode is a
placeholder. The graph reports the outstanding decisions in
``pending_decisions`` and resolves none of them.
"""

from __future__ import annotations

from typing import Any, Mapping


OUTPUT_TYPE = "architectural_intent_graph"
OUTPUT_VERSION = "architectural_intent_graph_v1"

NODE_BUILDING_SPACE = "building_space"
NODE_SITE_SPACE = "site_space"
NODE_VERTICAL_ELEMENT = "vertical_element"
NODE_KINDS = (NODE_BUILDING_SPACE, NODE_SITE_SPACE, NODE_VERTICAL_ELEMENT)

EDGE_ADJACENCY = "adjacency"
EDGE_VISUAL = "visual_connection"
EDGE_CIRCULATION = "circulation"
EDGE_VERTICAL = "vertical_connection"
EDGE_VEHICLE = "vehicle_access"
EDGE_TYPES = (
    EDGE_ADJACENCY,
    EDGE_VISUAL,
    EDGE_CIRCULATION,
    EDGE_VERTICAL,
    EDGE_VEHICLE,
)

# Source relationship vocabulary -> graph edge vocabulary.
# Observed LayoutReasoner connection types: adjacent, semantic_adjacent,
# visual_connection, direct_connection, private_connection, service_connection,
# vertical_connection.
SOURCE_EDGE_MAP = {
    "adjacent": EDGE_ADJACENCY,
    "semantic_adjacent": EDGE_ADJACENCY,
    "visual_connection": EDGE_VISUAL,
    "direct_connection": EDGE_CIRCULATION,
    "private_connection": EDGE_CIRCULATION,
    "service_connection": EDGE_CIRCULATION,
    "vertical_connection": EDGE_VERTICAL,
}

DOMAIN_BUILDING = "building"
DOMAIN_SITE = "site"

GEOMETRY_STATE_PENDING = "pending"

VEHICLE_ELEMENT_TYPES = ("ramp", "car_lift")

# Semantic (NOT name-based) vehicle signals.
VEHICLE_SPACE_TYPES = frozenset(
    ("parking", "vehicle_space", "vehicle_circulation", "loading_space")
)
VEHICLE_PLACEMENT_PRIORITY = "vehicle_access"

STATE_RESOLVED = "intent_graph_resolved"
STATE_UNRESOLVED = "intent_graph_unresolved"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _mapping(value, label):
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping or None")

    return dict(value)


def _sequence(value, label):
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be a list")

    return list(value)


def _is_normalised_contract(record):
    return (
        isinstance(record, Mapping)
        and record.get("type") == "architectural_spatial_contract"
    )


def _space_node_id(contract):
    """Node identity is the space's OWN name plus its floor.

    The canonical name is NOT used as the node key: several distinct spaces can
    canonicalise to the same value (``master_bedroom`` and ``bedroom`` both
    canonicalise to ``bedroom``), which would collapse them into one node. A
    program declares at most one space per (name, floor), so this pair is
    unique, and the canonical name is still carried as an attribute.
    """

    return (
        f"{contract['domain']}:"
        f"{contract['identity']['name']}@"
        f"{contract['vertical']['floor']}"
    )


def _element_node_id(element, index):
    floors = "-".join(element.get("floors", []) or ["unserved"])

    return (
        f"vertical:{element.get('type')}:{element.get('role')}@{floors}#{index}"
    )


def _pending_geometry(reason):
    return {"state": GEOMETRY_STATE_PENDING, "reason": reason}


def _is_vehicle_node(node):
    """Semantic vehicle test - never a name list."""

    if node.get("space_type") in VEHICLE_SPACE_TYPES:
        return True

    intent = node.get("architectural_intent") or {}
    if not isinstance(intent, Mapping):
        return False

    if intent.get("vehicle_access_priority"):
        return True

    return intent.get("placement_priority") == VEHICLE_PLACEMENT_PRIORITY


# ---------------------------------------------------------------------------
# node builders
# ---------------------------------------------------------------------------

def _space_node(contract):
    return {
        "node_id": _space_node_id(contract),
        "kind": (
            NODE_SITE_SPACE
            if contract["domain"] == DOMAIN_SITE
            else NODE_BUILDING_SPACE
        ),
        "name": contract["identity"]["name"],
        "canonical_name": contract["identity"]["canonical_name"],
        "domain": contract["domain"],
        "floor": contract["vertical"]["floor"],
        "space_type": contract["semantic"]["space_type"],
        "role": contract["semantic"]["role"],
        "architectural_intent": dict(
            contract["semantic"]["architectural_intent"]
        ),
        "protected_zone": bool(
            (contract.get("metadata") or {}).get("protected_zone", False)
        ),
        "element_type": None,
        "floors": None,
        "geometry_status": dict(contract["geometry_status"]),
    }


def _element_node(element, index):
    return {
        "node_id": _element_node_id(element, index),
        "kind": NODE_VERTICAL_ELEMENT,
        "name": element.get("role"),
        "canonical_name": element.get("role"),
        "domain": element.get("domain"),
        "floor": None,
        "space_type": element.get("type"),
        "role": element.get("role"),
        "architectural_intent": {},
        "protected_zone": bool(element.get("protected_zone", False)),
        "element_type": element.get("type"),
        "floors": list(element.get("floors", []) or []),
        "geometry_status": dict(
            element.get("geometry_status")
            or _pending_geometry("vertical_geometry_not_authorized")
        ),
    }


# ---------------------------------------------------------------------------
# edge builders
# ---------------------------------------------------------------------------

def _edge(edge_type, source, target, domain, reasons, status="resolved",
          pending_reason=None):
    edge = {
        "edge_id": f"{edge_type}:{source}->{target}",
        "type": edge_type,
        "from": source,
        "to": target,
        "domain": domain,
        "cross_domain": False,
        "status": status,
        "pending_reason": pending_reason,
        "geometry_status": _pending_geometry("edge_geometry_not_authorized"),
        "reasons": list(reasons),
    }

    return edge


def _mark_cross_domain(edge, node_by_id):
    source = node_by_id.get(edge["from"])
    target = node_by_id.get(edge["to"])
    if source is None or target is None:
        return edge

    if source["domain"] != target["domain"]:
        edge["cross_domain"] = True

    return edge


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def build_architectural_intent_graph(
    *,
    spaces,
    vertical_circulation=None,
    connections=None,
):
    """Build the unified architectural intent graph.

    ``spaces`` is a list of space records - either already-normalised
    ``architectural_spatial_contract`` mappings, or raw producer records that
    are normalised here via the spatial contract. ``vertical_circulation`` is an
    OPTIONAL ``vertical_circulation_intelligence`` contract whose elements
    become graph nodes and are wired into the graph. ``connections`` is an
    OPTIONAL relationship list whose entries become graph edges.

    Pure function: no geometry, no coordinates, no filesystem, no randomness,
    and no input is mutated. Malformed input raises ``ValueError``.
    """

    raw_spaces = _sequence(spaces, "spaces")
    raw_connections = _sequence(connections, "connections")
    circulation = _mapping(vertical_circulation, "vertical_circulation")

    from core.architecture.reasoning.architectural_spatial_contract_v1 import (
        build_architectural_spatial_contract,
    )

    contracts = []
    for record in raw_spaces:
        if _is_normalised_contract(record):
            contracts.append(dict(record))
        else:
            contracts.append(build_architectural_spatial_contract(record))

    nodes = []
    reasons = []

    building_ids = []
    site_ids = []
    seen_node_ids = set()
    for contract in contracts:
        node = _space_node(contract)
        # Defensive: node identity must be unique. A collision would silently
        # merge two distinct spaces, so it is resolved deterministically and
        # reported rather than allowed to collapse the graph.
        if node["node_id"] in seen_node_ids:
            reasons.append("duplicate_space_node_identity_resolved_by_suffix")
            suffix = 1
            while f"{node['node_id']}#{suffix}" in seen_node_ids:
                suffix += 1
            node["node_id"] = f"{node['node_id']}#{suffix}"
        seen_node_ids.add(node["node_id"])

        nodes.append(node)
        if node["domain"] == DOMAIN_SITE:
            site_ids.append(node["node_id"])
        else:
            building_ids.append(node["node_id"])

    elements = _sequence(
        circulation.get("vertical_elements"), "vertical_elements"
    )
    vertical_ids = []
    for index, element in enumerate(elements):
        if not isinstance(element, Mapping):
            continue
        node = _element_node(element, index)
        nodes.append(node)
        vertical_ids.append(node["node_id"])

    node_by_id = {node["node_id"]: node for node in nodes}
    node_by_name = {}
    for node in nodes:
        if node["kind"] == NODE_VERTICAL_ELEMENT:
            continue
        for key in (node["name"], node["canonical_name"]):
            if key:
                node_by_name.setdefault(str(key).lower(), node)

    edges = []
    seen_edge_ids = set()

    def _add(edge):
        if edge["from"] not in node_by_id or edge["to"] not in node_by_id:
            return False
        if edge["from"] == edge["to"]:
            return False
        if edge["edge_id"] in seen_edge_ids:
            return False
        seen_edge_ids.add(edge["edge_id"])
        edges.append(_mark_cross_domain(edge, node_by_id))

        return True

    # --- source relationship edges ---------------------------------------
    unmapped = set()
    dropped = 0
    for connection in raw_connections:
        if not isinstance(connection, Mapping):
            continue

        source_name = connection.get("from")
        target_name = connection.get("to")
        if not source_name or not target_name:
            continue

        source = node_by_name.get(str(source_name).lower())
        target = node_by_name.get(str(target_name).lower())
        if source is None or target is None:
            # An endpoint that is not a graph node (for example a vertical
            # element referenced by name) cannot form an edge yet.
            dropped += 1
            continue

        source_type = connection.get("type")
        edge_type = SOURCE_EDGE_MAP.get(source_type)
        edge_reasons = [f"source_relationship:{source_type}"]
        if edge_type is None:
            unmapped.add(str(source_type))
            edge_type = EDGE_ADJACENCY
            edge_reasons.append("unmapped_source_relationship_type")

        _add(
            _edge(
                edge_type,
                source["node_id"],
                target["node_id"],
                source["domain"],
                edge_reasons,
            )
        )

    if unmapped:
        reasons.append("unmapped_source_relationship_types_recorded")
    if dropped:
        reasons.append("some_source_relationship_endpoints_are_not_graph_nodes")

    # --- vertical element edges ------------------------------------------
    for node in nodes:
        if node["kind"] != NODE_VERTICAL_ELEMENT:
            continue
        if node["element_type"] in VEHICLE_ELEMENT_TYPES:
            continue

        served = set(node["floors"] or [])
        for space in nodes:
            if space["kind"] == NODE_VERTICAL_ELEMENT:
                continue
            if space["floor"] not in served:
                continue

            _add(
                _edge(
                    EDGE_VERTICAL,
                    space["node_id"],
                    node["node_id"],
                    space["domain"],
                    ["space_floor_served_by_vertical_element"],
                )
            )

    # --- vehicle edges (PENDING by design) -------------------------------
    vehicle_nodes = [
        node
        for node in nodes
        if node["kind"] == NODE_VERTICAL_ELEMENT
        and node["element_type"] in VEHICLE_ELEMENT_TYPES
    ]

    if vehicle_nodes:
        vehicle_spaces = [
            node
            for node in nodes
            if node["kind"] != NODE_VERTICAL_ELEMENT and _is_vehicle_node(node)
        ]

        if not vehicle_spaces:
            reasons.append("vehicle_element_unconnected_no_semantic_vehicle_space")

        for element in vehicle_nodes:
            for space in vehicle_spaces:
                _add(
                    _edge(
                        EDGE_VEHICLE,
                        space["node_id"],
                        element["node_id"],
                        space["domain"],
                        ["semantic_vehicle_space_connects_to_vehicle_element"],
                        status="pending",
                        pending_reason="vehicle_access_mode_not_resolved",
                    )
                )

    # --- pending decisions (propagated, never resolved) ------------------
    pending_decisions = []
    vehicle_access = circulation.get("vehicle_access")
    if isinstance(vehicle_access, Mapping):
        if vehicle_access.get("status") == "pending":
            pending_decisions.append(
                {
                    "decision": "vehicle_access_mode",
                    "status": "pending",
                    "candidates": list(vehicle_access.get("candidates", [])),
                    "reasons": list(vehicle_access.get("reasons", [])),
                }
            )

    for node in nodes:
        if node["geometry_status"].get("state") == GEOMETRY_STATE_PENDING:
            continue
        pending_decisions.append(
            {
                "decision": f"geometry:{node['node_id']}",
                "status": "pending",
                "candidates": [],
                "reasons": [],
            }
        )

    return {
        "type": OUTPUT_TYPE,
        "version": OUTPUT_VERSION,
        "nodes": nodes,
        "edges": edges,
        "domains": {
            DOMAIN_BUILDING: building_ids,
            DOMAIN_SITE: site_ids,
            "vertical": vertical_ids,
        },
        "circulation_separation": circulation.get("circulation_separation"),
        "pending_decisions": pending_decisions,
        "semantics": {
            "metadata_only": True,
            "geometry_created": False,
            "coordinates_created": False,
            "dimensions_decided": False,
            "decisions_resolved": False,
        },
        "status": {
            "state": STATE_RESOLVED if nodes else STATE_UNRESOLVED,
            "reasons": reasons,
        },
    }


# ---------------------------------------------------------------------------
# graph queries
# ---------------------------------------------------------------------------

def nodes_of_kind(graph, kind):
    """Return the nodes of one kind."""

    if not isinstance(graph, Mapping):
        raise ValueError("graph must be a mapping")
    if kind not in NODE_KINDS:
        raise ValueError("kind must be one of: " + ", ".join(NODE_KINDS))

    return [node for node in graph.get("nodes", []) if node.get("kind") == kind]


def edges_of_type(graph, edge_type):
    """Return the edges of one type."""

    if not isinstance(graph, Mapping):
        raise ValueError("graph must be a mapping")
    if edge_type not in EDGE_TYPES:
        raise ValueError("edge_type must be one of: " + ", ".join(EDGE_TYPES))

    return [edge for edge in graph.get("edges", []) if edge.get("type") == edge_type]


def edges_touching(graph, node_id):
    """Return every edge incident to ``node_id``."""

    if not isinstance(graph, Mapping):
        raise ValueError("graph must be a mapping")

    return [
        edge
        for edge in graph.get("edges", [])
        if node_id in (edge.get("from"), edge.get("to"))
    ]


def has_edge(graph, edge_type, source, target):
    """True when an edge of ``edge_type`` connects source -> target."""

    if edge_type not in EDGE_TYPES:
        raise ValueError("edge_type must be one of: " + ", ".join(EDGE_TYPES))

    return any(
        edge.get("type") == edge_type
        and edge.get("from") == source
        and edge.get("to") == target
        for edge in edges_of_type(graph, edge_type)
    )
