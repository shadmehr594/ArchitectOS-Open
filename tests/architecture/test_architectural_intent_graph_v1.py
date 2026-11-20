"""Focused tests for the unified Architectural Intent Graph (ARCH-CONTRACT-02).

The graph fuses the spatial contract (space nodes), the vertical circulation
contract (vertical-element nodes) and the LayoutReasoner connections (edges).
It creates no geometry, decides no dimension, and resolves no pending decision.
"""

import copy

import pytest

from core.architecture.reasoning.architectural_intent_graph_v1 import (
    EDGE_ADJACENCY,
    EDGE_CIRCULATION,
    EDGE_TYPES,
    EDGE_VEHICLE,
    EDGE_VERTICAL,
    EDGE_VISUAL,
    NODE_BUILDING_SPACE,
    NODE_KINDS,
    NODE_SITE_SPACE,
    NODE_VERTICAL_ELEMENT,
    build_architectural_intent_graph,
    edges_of_type,
    edges_touching,
    has_edge,
    nodes_of_kind,
)
from core.architecture.reasoning.knowledge_space_generator import (
    KnowledgeSpaceGenerator,
)
from core.architecture.reasoning.layout_reasoner import LayoutReasoner
from core.architecture.reasoning.vertical_circulation_intelligence_v2 import (
    resolve_vertical_circulation_intelligence,
)


DESIGN_CONCEPT = {"building_type": "villa"}

VILLA_WITH_SITE = {
    "building_type": "villa",
    "requirements": ["garden", "parking"],
    "levels": {"above_ground": 2},
}

VILLA_WITH_BASEMENT = {
    "building_type": "villa",
    "requirements": ["garden", "parking"],
    "levels": {"above_ground": 2, "basement": 1},
}

MIXED_USE = {"building_type": "mixed_use", "levels": {"above_ground": 2}}


@pytest.fixture(scope="module")
def generator():
    return KnowledgeSpaceGenerator()


@pytest.fixture(scope="module")
def reasoner():
    return LayoutReasoner()


def _chain(generator, reasoner, intent):
    generated = generator.generate(dict(intent))
    layout = reasoner.generate(
        generated["generated_spaces"],
        generated["relationships"],
        dict(DESIGN_CONCEPT),
        generated_site_spaces=generated["generated_site_spaces"],
    )

    return generated, layout


def _graph(generator, reasoner, intent, levels=None):
    generated, layout = _chain(generator, reasoner, intent)
    circulation = resolve_vertical_circulation_intelligence(
        building_type=intent["building_type"],
        levels=levels if levels is not None else intent.get("levels"),
    )

    return build_architectural_intent_graph(
        spaces=generated["generated_spaces"] + generated["generated_site_spaces"],
        vertical_circulation=circulation,
        connections=layout["connections"],
    )


def _node(graph, node_id):
    return next(
        (node for node in graph["nodes"] if node["node_id"] == node_id), None
    )


def _first_of_type(graph, element_type):
    return next(
        node
        for node in nodes_of_kind(graph, NODE_VERTICAL_ELEMENT)
        if node["element_type"] == element_type
    )


# ---------------------------------------------------------------------------
# graph shape
# ---------------------------------------------------------------------------

def test_graph_shape(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)

    assert graph["type"] == "architectural_intent_graph"
    assert graph["version"] == "architectural_intent_graph_v1"
    assert sorted(graph.keys()) == [
        "circulation_separation",
        "domains",
        "edges",
        "nodes",
        "pending_decisions",
        "semantics",
        "status",
        "type",
        "version",
    ]


def test_all_three_node_kinds_are_present(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)

    for kind in NODE_KINDS:
        assert nodes_of_kind(graph, kind), f"no {kind} node"


SPACE_DOMAINS = ("building", "site")
CIRCULATION_DOMAINS = ("residential", "commercial", "mixed_use", "site")


def test_nodes_carry_the_required_attributes(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)

    for node in graph["nodes"]:
        assert node["node_id"]
        assert node["kind"] in NODE_KINDS
        # ``domain`` has two axes, disambiguated by ``kind``.
        if node["kind"] == NODE_VERTICAL_ELEMENT:
            assert node["domain"] in CIRCULATION_DOMAINS
        else:
            assert node["domain"] in SPACE_DOMAINS
        assert isinstance(node["protected_zone"], bool)
        assert node["geometry_status"]["state"] == "pending"
        assert node["geometry_status"]["reason"]


def test_space_nodes_carry_floor_information(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)

    for node in nodes_of_kind(graph, NODE_BUILDING_SPACE):
        assert node["floor"]

    for node in nodes_of_kind(graph, NODE_SITE_SPACE):
        assert node["floor"] == "site_level"


def test_vertical_nodes_carry_their_served_floors(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)

    for node in nodes_of_kind(graph, NODE_VERTICAL_ELEMENT):
        assert node["element_type"]
        assert node["floors"]
        assert node["floor"] is None


def test_node_identity_is_unique(generator, reasoner):
    """Regression: master_bedroom and bedroom both canonicalise to ``bedroom``,
    so the canonical name must NOT be the node key."""

    graph = _graph(generator, reasoner, VILLA_WITH_SITE)
    ids = [node["node_id"] for node in graph["nodes"]]

    assert len(ids) == len(set(ids))


def test_distinct_spaces_sharing_a_canonical_name_stay_distinct(
    generator, reasoner
):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)

    upper_bedrooms = [
        node
        for node in nodes_of_kind(graph, NODE_BUILDING_SPACE)
        if node["floor"] == "upper_floor" and node["canonical_name"] == "bedroom"
    ]

    assert len(upper_bedrooms) >= 2
    assert len({node["node_id"] for node in upper_bedrooms}) == len(
        upper_bedrooms
    )


# ---------------------------------------------------------------------------
# domain separation
# ---------------------------------------------------------------------------

def test_domains_are_separated(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)
    domains = graph["domains"]

    building = set(domains["building"])
    site = set(domains["site"])
    vertical = set(domains["vertical"])

    assert building
    assert site
    assert vertical
    assert building.isdisjoint(site)
    assert building.isdisjoint(vertical)
    assert site.isdisjoint(vertical)


def test_site_nodes_are_never_classified_as_building(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)

    for node in nodes_of_kind(graph, NODE_SITE_SPACE):
        assert node["domain"] == "site"

    for node in nodes_of_kind(graph, NODE_BUILDING_SPACE):
        assert node["domain"] == "building"


def test_cross_domain_edges_are_flagged(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)

    visual = edges_of_type(graph, EDGE_VISUAL)
    garden_edges = [
        edge for edge in visual if edge["to"].startswith("site:garden")
    ]

    assert garden_edges
    assert garden_edges[0]["cross_domain"] is True


# ---------------------------------------------------------------------------
# REQUIRED: living -> garden visual connection
# ---------------------------------------------------------------------------

def test_living_to_garden_visual_connection(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)

    assert has_edge(
        graph,
        EDGE_VISUAL,
        "building:living@ground_floor",
        "site:garden@site_level",
    )


def test_garden_is_a_site_node(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)

    garden = _node(graph, "site:garden@site_level")

    assert garden is not None
    assert garden["kind"] == NODE_SITE_SPACE
    assert garden["domain"] == "site"


# ---------------------------------------------------------------------------
# REQUIRED: living -> stair vertical connection
# ---------------------------------------------------------------------------

def test_living_to_stair_vertical_connection(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)
    stair = _first_of_type(graph, "stair")

    assert has_edge(
        graph,
        EDGE_VERTICAL,
        "building:living@ground_floor",
        stair["node_id"],
    )


def test_vertical_elements_connect_into_the_graph(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)

    for element in nodes_of_kind(graph, NODE_VERTICAL_ELEMENT):
        incident = edges_touching(graph, element["node_id"])
        assert incident, f"{element['node_id']} is not connected"


def test_vertical_edges_only_join_served_floors(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)
    node_by_id = {node["node_id"]: node for node in graph["nodes"]}

    for edge in edges_of_type(graph, EDGE_VERTICAL):
        element = node_by_id[edge["to"]]
        space = node_by_id[edge["from"]]
        assert space["floor"] in element["floors"]


# ---------------------------------------------------------------------------
# REQUIRED: parking -> ramp pending vehicle connection
# ---------------------------------------------------------------------------

def test_parking_to_ramp_pending_vehicle_connection(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_BASEMENT)
    ramp = _first_of_type(graph, "ramp")

    assert has_edge(
        graph,
        EDGE_VEHICLE,
        "site:parking@site_level",
        ramp["node_id"],
    )


def test_vehicle_edge_is_pending(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_BASEMENT)

    for edge in edges_of_type(graph, EDGE_VEHICLE):
        assert edge["status"] == "pending"
        assert edge["pending_reason"] == "vehicle_access_mode_not_resolved"
        assert edge["geometry_status"]["state"] == "pending"


def test_non_vehicle_site_space_is_not_wired_to_the_ramp(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_BASEMENT)
    ramp = _first_of_type(graph, "ramp")

    assert not has_edge(
        graph,
        EDGE_VEHICLE,
        "site:garden@site_level",
        ramp["node_id"],
    )


def test_pending_vehicle_decision_is_propagated_not_resolved(
    generator, reasoner
):
    graph = _graph(generator, reasoner, VILLA_WITH_BASEMENT)

    decisions = {
        decision["decision"]: decision for decision in graph["pending_decisions"]
    }

    assert "vehicle_access_mode" in decisions
    assert decisions["vehicle_access_mode"]["status"] == "pending"
    assert decisions["vehicle_access_mode"]["candidates"] == ["ramp", "car_lift"]


# ---------------------------------------------------------------------------
# REQUIRED: mixed-use circulation separation
# ---------------------------------------------------------------------------

def test_mixed_use_circulation_separation_is_carried(generator, reasoner):
    graph = _graph(generator, reasoner, MIXED_USE)

    separation = graph["circulation_separation"]

    assert separation is not None
    assert separation["shared_core"] is True
    assert separation["separation_required"] is True


def test_mixed_use_shared_core_is_a_connected_node(generator, reasoner):
    graph = _graph(generator, reasoner, MIXED_USE)

    shared = [
        node
        for node in nodes_of_kind(graph, NODE_VERTICAL_ELEMENT)
        if node["role"] == "shared_core_vertical_circulation"
    ]

    assert shared
    for node in shared:
        assert edges_touching(graph, node["node_id"])


def test_mixed_use_keeps_domain_separation(generator, reasoner):
    graph = _graph(generator, reasoner, MIXED_USE)

    assert graph["domains"]["building"]
    assert graph["domains"]["vertical"]
    assert set(graph["domains"]["building"]).isdisjoint(
        graph["domains"]["vertical"]
    )


# ---------------------------------------------------------------------------
# edge vocabulary
# ---------------------------------------------------------------------------

def test_only_the_declared_edge_types_are_emitted(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_BASEMENT)

    for edge in graph["edges"]:
        assert edge["type"] in EDGE_TYPES


def test_source_relationship_types_are_mapped(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)

    # The villa relationships include adjacency, direct_connection and
    # visual_connection.
    types = {edge["type"] for edge in graph["edges"]}

    assert EDGE_ADJACENCY in types
    assert EDGE_VISUAL in types
    assert EDGE_CIRCULATION in types


def test_edges_never_self_loop(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)

    for edge in graph["edges"]:
        assert edge["from"] != edge["to"]


def test_edges_always_reference_existing_nodes(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)
    ids = {node["node_id"] for node in graph["nodes"]}

    for edge in graph["edges"]:
        assert edge["from"] in ids
        assert edge["to"] in ids


def test_edge_ids_are_unique(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)
    ids = [edge["edge_id"] for edge in graph["edges"]]

    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# no geometry
# ---------------------------------------------------------------------------

def _walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_keys(item)


@pytest.mark.parametrize(
    "intent", [VILLA_WITH_SITE, VILLA_WITH_BASEMENT, MIXED_USE]
)
def test_no_geometry_coordinates_or_dimensions(generator, reasoner, intent):
    graph = _graph(generator, reasoner, intent)
    keys = set(_walk_keys(graph))

    for forbidden in (
        "coordinates",
        "polygon",
        "geometry",
        "bounds",
        "position",
        "centroid",
        "footprint",
        "x",
        "y",
        "z",
        "width",
        "depth",
        "height",
        "area",
    ):
        assert forbidden not in keys, f"graph produced {forbidden}"


def test_semantics_declare_no_geometry_and_no_resolved_decisions(
    generator, reasoner
):
    graph = _graph(generator, reasoner, VILLA_WITH_BASEMENT)

    assert graph["semantics"] == {
        "metadata_only": True,
        "geometry_created": False,
        "coordinates_created": False,
        "dimensions_decided": False,
        "decisions_resolved": False,
    }


# ---------------------------------------------------------------------------
# determinism / no mutation
# ---------------------------------------------------------------------------

def test_graph_is_deterministic(generator, reasoner):
    first = _graph(generator, reasoner, VILLA_WITH_SITE)
    second = _graph(generator, reasoner, VILLA_WITH_SITE)

    assert first == second
    assert first is not second


def test_inputs_are_not_mutated(generator, reasoner):
    generated, layout = _chain(generator, reasoner, VILLA_WITH_SITE)
    circulation = resolve_vertical_circulation_intelligence(
        building_type="villa", levels=VILLA_WITH_SITE["levels"]
    )
    spaces = generated["generated_spaces"] + generated["generated_site_spaces"]

    before = copy.deepcopy((spaces, circulation, layout["connections"]))

    build_architectural_intent_graph(
        spaces=spaces,
        vertical_circulation=circulation,
        connections=layout["connections"],
    )

    assert (spaces, circulation, layout["connections"]) == before


def test_mutating_the_graph_does_not_corrupt_later_builds(generator, reasoner):
    first = _graph(generator, reasoner, VILLA_WITH_SITE)
    first["nodes"][0]["node_id"] = "mutated"
    first["edges"].clear()

    second = _graph(generator, reasoner, VILLA_WITH_SITE)

    assert second["nodes"]
    assert second["edges"]
    assert second["nodes"][0]["node_id"] != "mutated"


# ---------------------------------------------------------------------------
# optional inputs / validation
# ---------------------------------------------------------------------------

def test_graph_without_vertical_circulation_still_builds(generator, reasoner):
    generated, layout = _chain(generator, reasoner, VILLA_WITH_SITE)

    graph = build_architectural_intent_graph(
        spaces=generated["generated_spaces"],
        connections=layout["connections"],
    )

    assert graph["nodes"]
    assert nodes_of_kind(graph, NODE_VERTICAL_ELEMENT) == []


def test_graph_without_connections_still_builds(generator, reasoner):
    generated, _ = _chain(generator, reasoner, VILLA_WITH_SITE)

    graph = build_architectural_intent_graph(
        spaces=generated["generated_spaces"]
    )

    assert graph["nodes"]
    assert graph["edges"] == []


def test_empty_graph_is_unresolved():
    graph = build_architectural_intent_graph(spaces=[])

    assert graph["nodes"] == []
    assert graph["status"]["state"] == "intent_graph_unresolved"


def test_normalised_contracts_are_accepted(generator, reasoner):
    from core.architecture.reasoning.architectural_spatial_contract_v1 import (
        build_architectural_spatial_contract,
    )

    generated, _ = _chain(generator, reasoner, VILLA_WITH_SITE)
    contracts = [
        build_architectural_spatial_contract(space)
        for space in generated["generated_spaces"]
    ]

    graph = build_architectural_intent_graph(spaces=contracts)

    assert len(nodes_of_kind(graph, NODE_BUILDING_SPACE)) == len(contracts)


@pytest.mark.parametrize("bad", ["x", 3, {}, None], ids=["str", "int", "dict", "none"])
def test_invalid_spaces_container_is_rejected(bad):
    if bad is None:
        # None means "no spaces supplied" and is accepted as empty.
        assert build_architectural_intent_graph(spaces=None)["nodes"] == []
        return

    with pytest.raises(ValueError, match="spaces must be a list"):
        build_architectural_intent_graph(spaces=bad)


@pytest.mark.parametrize("bad", ["x", 3], ids=["str", "int"])
def test_invalid_connections_container_is_rejected(bad):
    with pytest.raises(ValueError, match="connections must be a list"):
        build_architectural_intent_graph(spaces=[], connections=bad)


def test_query_helpers_validate_their_arguments(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)

    with pytest.raises(ValueError, match="kind must be one of"):
        nodes_of_kind(graph, "roof")

    with pytest.raises(ValueError, match="edge_type must be one of"):
        edges_of_type(graph, "teleport")

    with pytest.raises(ValueError, match="edge_type must be one of"):
        has_edge(graph, "teleport", "a", "b")

    with pytest.raises(ValueError, match="graph must be a mapping"):
        edges_touching(None, "a")
