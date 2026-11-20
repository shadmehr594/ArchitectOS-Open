"""Focused tests for Architectural Spatial Geometry Intent (ARCH-GEOMETRY-03).

This module is the THIRD semantic bridge. It expands the Architectural Intent
Graph into an assembly-level spatial geometry intent contract with six semantic
blocks:

    space_containment   - what contains a space, and is it internal or external
    envelope            - envelope participation, continuity, facade relation
    wall_intent         - the wall SEMANTIC a boundary implies
    floor_intent        - floor surface intent, level relationships, penetrations
    roof_intent         - roof semantic role, terrace relationship, exposure
    spatial_adjacency   - the preserved relationship view

Hard rules enforced by these tests:

* NO geometry of any kind is created - no coordinate, no x/y/z, no width,
  depth, height, thickness, area, volume, polygon, mesh, CAD or IFC entity.
* NO numeric leaf may survive anywhere inside a node record.
* ``geometry_status`` is pending on every block and every record.
* No pending decision is resolved. Building/site separation, mixed-use domain
  separation, vertical circulation semantics, vehicle_access pending,
  protected_zone and opening/boundary intent are all PRESERVED.
* Output is deterministic and neither input is mutated.
"""

import copy

import pytest

from core.architecture.reasoning.architectural_intent_graph_v1 import (
    build_architectural_intent_graph,
)
from core.architecture.reasoning.architectural_opening_boundary_intent_v1 import (
    build_opening_boundary_intent_contract,
)
from core.architecture.reasoning.architectural_spatial_geometry_intent_v1 import (
    BOUNDARY_CORE,
    BOUNDARY_ENVELOPE,
    BOUNDARY_INTERNAL,
    BOUNDARY_SITE_OPEN,
    BOUNDARY_SITE_UNRESOLVED,
    CLASSIFICATION_CIRCULATION,
    CLASSIFICATION_EXTERNAL,
    CLASSIFICATION_INTERNAL,
    CLASSIFICATION_SITE,
    CONTAINED_BY_SERVED_LEVELS,
    CONTAINED_BY_SITE,
    CONTAINED_BY_STOREY,
    CONTAINMENT_KINDS,
    DOMAIN_AXIS_CIRCULATION,
    DOMAIN_AXIS_SPACE,
    DOMAIN_BUILDING,
    DOMAIN_SITE,
    ENVELOPE_CONTINUITY_REQUIRED,
    ENVELOPE_OBLIGATION_THERMAL,
    ENVELOPE_OBLIGATION_WEATHER,
    FACADE_APPROVAL_PENDING,
    FACADE_RELATION_EXTERIOR_FACING,
    FACADE_RELATION_SITE_FACING,
    FACT_ROOF_IS_REAL_LEVEL,
    FLOOR_INTENT_TYPES,
    FLOOR_ROOF_SURFACE,
    FLOOR_SITE_SURFACE,
    FLOOR_SURFACE,
    FLOOR_INTERRUPTION_REQUIRED,
    GEOMETRY_STATE_PENDING,
    NODE_VERTICAL_ELEMENT,
    OUTPUT_TYPE,
    OUTPUT_VERSION,
    ROOF_ROLE_OCCUPIABLE_TERRACE,
    ROOF_ROLE_TOP_TERMINATION,
    SITE_LEVEL,
    STATE_RESOLVED,
    STATUS_NOT_REQUIRED,
    STATUS_PENDING,
    STATUS_RESOLVED,
    STATUS_UNRESOLVED,
    WALL_CONSTRAINT_ACOUSTIC,
    WALL_CONSTRAINT_GUARDING,
    WALL_CONSTRAINT_WEATHER,
    WALL_CORE_ENCLOSURE,
    WALL_ENVELOPE,
    WALL_INTENT_TYPES,
    WALL_PARTITION,
    WALL_SEPARATING,
    WALL_SITE_BOUNDARY,
    build_spatial_geometry_intent_contract,
    envelope_records,
    floor_intents_of_type,
    pending_geometry_blocks,
    record_for_node,
    records_with_classification,
    roof_records,
    wall_intents_of_type,
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

UPPER = "upper"
GROUND = "ground"
ROOF = "roof"


def _graph(spaces, vertical=None, connections=None):
    return build_architectural_intent_graph(
        spaces=spaces,
        vertical_circulation=vertical,
        connections=connections,
    )


def _villa_vertical(*, protected=False):
    return {
        "vertical_elements": [
            {
                "type": "stair",
                "role": "main_stair",
                "domain": "residential",
                "floors": [GROUND, UPPER],
                "protected_zone": protected,
            }
        ]
    }


@pytest.fixture
def living_garden_graph():
    """A ground living room that opens onto a garden, plus a stair core."""

    return _graph(
        spaces=[
            {"name": "Living", "space_type": "living_room", "floor": GROUND},
            {"name": "Kitchen", "space_type": "kitchen", "floor": GROUND},
            {"name": "Master", "space_type": "bedroom", "floor": UPPER},
            {"name": "Garden", "space_type": "garden", "floor": SITE_LEVEL},
        ],
        vertical=_villa_vertical(),
        connections=[
            {"from": "Living", "to": "Kitchen", "type": "adjacent"},
            {"from": "Living", "to": "Garden", "type": "visual_connection"},
        ],
    )


@pytest.fixture
def parking_graph():
    """A building space meeting a vehicle site space: the boundary is pending."""

    return _graph(
        spaces=[
            {"name": "Living", "space_type": "living_room", "floor": GROUND},
            {
                "name": "Parking",
                "space_type": "parking",
                "floor": SITE_LEVEL,
                "vehicle_access_priority": "high",
            },
        ],
        connections=[
            {"from": "Living", "to": "Parking", "type": "adjacent"},
        ],
    )


def _build_living_garden():
    graph = _graph(
        spaces=[
            {"name": "Living", "space_type": "living_room", "floor": GROUND},
            {"name": "Kitchen", "space_type": "kitchen", "floor": GROUND},
            {"name": "Master", "space_type": "bedroom", "floor": UPPER},
            {"name": "Garden", "space_type": "garden", "floor": SITE_LEVEL},
        ],
        vertical=_villa_vertical(),
        connections=[
            {"from": "Living", "to": "Kitchen", "type": "adjacent"},
            {"from": "Living", "to": "Garden", "type": "visual_connection"},
        ],
    )

    return graph, build_spatial_geometry_intent_contract(graph)


# ---------------------------------------------------------------------------
# contract shape
# ---------------------------------------------------------------------------

def test_contract_declares_its_type_and_version():
    _, contract = _build_living_garden()

    assert contract["type"] == OUTPUT_TYPE
    assert contract["version"] == OUTPUT_VERSION


def test_every_graph_node_produces_exactly_one_record():
    graph, contract = _build_living_garden()

    graph_ids = sorted(node["node_id"] for node in graph["nodes"])
    record_ids = sorted(record["node_id"] for record in contract["node_records"])

    assert record_ids == graph_ids


def test_every_record_carries_all_six_semantic_blocks():
    _, contract = _build_living_garden()

    expected = {
        "space_containment",
        "envelope",
        "wall_intent",
        "floor_intent",
        "roof_intent",
        "spatial_adjacency",
    }

    for record in contract["node_records"]:
        assert expected.issubset(record.keys())


def test_contract_declares_no_geometry_was_created():
    _, contract = _build_living_garden()
    semantics = contract["semantics"]

    assert semantics["geometry_created"] is False
    assert semantics["coordinates_created"] is False
    assert semantics["dimensions_created"] is False
    assert semantics["polygons_created"] is False
    assert semantics["meshes_created"] is False
    assert semantics["wall_geometry_created"] is False
    assert semantics["slab_geometry_created"] is False
    assert semantics["roof_geometry_created"] is False


def test_input_graph_is_not_mutated():
    graph, _ = _build_living_garden()
    before = copy.deepcopy(graph)

    build_spatial_geometry_intent_contract(graph)

    assert graph == before


def test_graph_of_the_wrong_type_is_rejected():
    with pytest.raises(ValueError):
        build_spatial_geometry_intent_contract(
            {"type": "something_else", "nodes": [], "edges": []}
        )


# ---------------------------------------------------------------------------
# 1 - space containment intent
# ---------------------------------------------------------------------------

def test_building_space_is_contained_by_its_storey():
    _, contract = _build_living_garden()
    record = record_for_node(contract, f"{DOMAIN_BUILDING}:Living@{GROUND}")

    containment = record["space_containment"]

    assert containment["containment_kind"] == CONTAINED_BY_STOREY
    assert containment["contained_by_levels"] == [GROUND]
    assert containment["floor"] == GROUND


def test_site_space_is_contained_by_the_site_never_a_storey():
    _, contract = _build_living_garden()
    record = record_for_node(contract, f"{DOMAIN_SITE}:Garden@{SITE_LEVEL}")

    containment = record["space_containment"]

    assert containment["containment_kind"] == CONTAINED_BY_SITE
    assert containment["contained_by_levels"] == [SITE_LEVEL]
    assert containment["classification"] == CLASSIFICATION_SITE


def test_vertical_element_is_contained_by_its_served_level_set():
    _, contract = _build_living_garden()
    vertical = next(
        record
        for record in contract["node_records"]
        if record["space_identity"]["kind"] == NODE_VERTICAL_ELEMENT
    )

    containment = vertical["space_containment"]

    assert containment["containment_kind"] == CONTAINED_BY_SERVED_LEVELS
    assert containment["contained_by_levels"] == sorted([GROUND, UPPER])


def test_containment_kind_is_always_from_the_declared_vocabulary():
    _, contract = _build_living_garden()

    for record in contract["node_records"]:
        assert record["space_containment"]["containment_kind"] in CONTAINMENT_KINDS


def test_a_space_touching_the_envelope_is_classified_external():
    _, contract = _build_living_garden()
    record = record_for_node(contract, f"{DOMAIN_BUILDING}:Living@{GROUND}")

    assert record["space_containment"]["classification"] == (
        CLASSIFICATION_EXTERNAL
    )


def test_a_space_with_no_envelope_boundary_is_classified_internal():
    _, contract = _build_living_garden()
    record = record_for_node(contract, f"{DOMAIN_BUILDING}:Kitchen@{GROUND}")

    assert record["space_containment"]["classification"] == (
        CLASSIFICATION_INTERNAL
    )


def test_the_vertical_element_is_classified_into_the_circulation_axis():
    _, contract = _build_living_garden()
    vertical = next(
        record
        for record in contract["node_records"]
        if record["space_identity"]["kind"] == NODE_VERTICAL_ELEMENT
    )

    assert vertical["space_containment"]["classification"] == (
        CLASSIFICATION_CIRCULATION
    )
    assert vertical["domain_axis"] == DOMAIN_AXIS_CIRCULATION


def test_space_axis_and_circulation_axis_are_not_conflated():
    _, contract = _build_living_garden()

    for record in contract["node_records"]:
        axis = record["domain_axis"]

        if record["space_identity"]["kind"] == NODE_VERTICAL_ELEMENT:
            assert axis == DOMAIN_AXIS_CIRCULATION
        else:
            assert axis == DOMAIN_AXIS_SPACE


def test_records_can_be_selected_by_classification():
    _, contract = _build_living_garden()

    site_records = records_with_classification(contract, CLASSIFICATION_SITE)
    ids = [record["node_id"] for record in site_records]

    assert ids == [f"{DOMAIN_SITE}:Garden@{SITE_LEVEL}"]


# ---------------------------------------------------------------------------
# 2 - envelope intent
# ---------------------------------------------------------------------------

def test_building_site_meeting_produces_an_envelope_boundary():
    _, contract = _build_living_garden()
    record = record_for_node(contract, f"{DOMAIN_BUILDING}:Living@{GROUND}")

    envelope = record["envelope"]

    assert envelope["is_envelope_participant"] is True
    assert envelope["envelope_boundary_ids"] == [
        f"{BOUNDARY_ENVELOPE}:{DOMAIN_BUILDING}:Living@{GROUND}"
        f"->{DOMAIN_SITE}:Garden@{SITE_LEVEL}"
    ]


def test_envelope_carries_weather_and_thermal_obligations():
    _, contract = _build_living_garden()
    record = record_for_node(contract, f"{DOMAIN_BUILDING}:Living@{GROUND}")

    obligations = record["envelope"]["obligations"]

    assert ENVELOPE_OBLIGATION_WEATHER in obligations
    assert ENVELOPE_OBLIGATION_THERMAL in obligations


def test_envelope_continuity_is_required_and_never_asserted_geometrically():
    _, contract = _build_living_garden()

    for record in envelope_records(contract):
        assert record["envelope"]["continuity_status"] == (
            ENVELOPE_CONTINUITY_REQUIRED
        )


def test_facade_relationship_is_declared_but_approval_stays_pending():
    _, contract = _build_living_garden()
    record = record_for_node(contract, f"{DOMAIN_BUILDING}:Living@{GROUND}")

    envelope = record["envelope"]

    assert envelope["facade_relationship"] in (
        FACADE_RELATION_SITE_FACING,
        FACADE_RELATION_EXTERIOR_FACING,
    )
    assert envelope["facade_approval_status"] == FACADE_APPROVAL_PENDING


def test_envelope_does_not_create_any_boundary_geometry():
    _, contract = _build_living_garden()

    for record in envelope_records(contract):
        assert record["envelope"]["geometry_status"]["state"] == (
            GEOMETRY_STATE_PENDING
        )


# ---------------------------------------------------------------------------
# 3 - wall intent (no wall geometry)
# ---------------------------------------------------------------------------

def test_envelope_boundary_carries_an_envelope_wall_intent():
    _, contract = _build_living_garden()
    intents = wall_intents_of_type(contract, WALL_ENVELOPE)

    assert intents
    for intent in intents:
        assert intent["boundary_type"] == BOUNDARY_ENVELOPE
        assert WALL_CONSTRAINT_WEATHER in intent["constraints"]


def test_internal_boundary_between_two_building_spaces_is_a_partition():
    _, contract = _build_living_garden()

    intents = [
        intent
        for intent in wall_intents_of_type(contract, WALL_PARTITION)
        if intent["boundary_type"] == BOUNDARY_INTERNAL
    ]

    assert intents
    assert WALL_CONSTRAINT_ACOUSTIC in intents[0]["constraints"]


def test_a_vertical_element_interface_is_a_core_enclosure():
    _, contract = _build_living_garden()
    intents = wall_intents_of_type(contract, WALL_CORE_ENCLOSURE)

    assert intents
    for intent in intents:
        assert intent["boundary_type"] == BOUNDARY_CORE


def test_a_vehicle_site_boundary_is_a_site_wall_not_an_interior_partition():
    """Regression: an unresolved vehicle boundary must NOT be a partition."""

    graph = _graph(
        spaces=[
            {"name": "Living", "space_type": "living_room", "floor": GROUND},
            {
                "name": "Parking",
                "space_type": "parking",
                "floor": SITE_LEVEL,
                "vehicle_access_priority": "high",
            },
        ],
        connections=[{"from": "Living", "to": "Parking", "type": "adjacent"}],
    )
    contract = build_spatial_geometry_intent_contract(graph)

    record = record_for_node(contract, f"{DOMAIN_BUILDING}:Living@{GROUND}")
    intents = record["wall_intent"]["wall_intents"]

    vehicle = [
        intent
        for intent in intents
        if intent["boundary_type"] == BOUNDARY_SITE_UNRESOLVED
    ]

    assert vehicle, "the vehicle boundary must be present"
    assert vehicle[0]["wall_intent_type"] == WALL_SITE_BOUNDARY
    assert vehicle[0]["wall_intent_type"] != WALL_PARTITION


def test_a_vehicle_site_boundary_keeps_guarding_pending():
    graph = _graph(
        spaces=[
            {"name": "Living", "space_type": "living_room", "floor": GROUND},
            {
                "name": "Parking",
                "space_type": "parking",
                "floor": SITE_LEVEL,
                "vehicle_access_priority": "high",
            },
        ],
        connections=[{"from": "Living", "to": "Parking", "type": "adjacent"}],
    )
    contract = build_spatial_geometry_intent_contract(graph)

    record = record_for_node(contract, f"{DOMAIN_BUILDING}:Living@{GROUND}")
    vehicle = [
        intent
        for intent in record["wall_intent"]["wall_intents"]
        if intent["boundary_type"] == BOUNDARY_SITE_UNRESOLVED
    ]

    assert vehicle[0]["status"] == STATUS_PENDING
    assert WALL_CONSTRAINT_GUARDING in vehicle[0]["constraints"]


def test_no_wall_geometry_is_ever_created():
    _, contract = _build_living_garden()

    for wall_type in WALL_INTENT_TYPES:
        for intent in wall_intents_of_type(contract, wall_type):
            assert intent["geometry_status"]["state"] == GEOMETRY_STATE_PENDING

    assert contract["semantics"]["wall_geometry_created"] is False


# ---------------------------------------------------------------------------
# 4 - floor / slab intent (no slab geometry)
# ---------------------------------------------------------------------------

def test_floor_surface_intent_exists_for_an_occupied_storey():
    _, contract = _build_living_garden()
    surfaces = floor_intents_of_type(contract, FLOOR_SURFACE)

    levels = {surface["level"] for surface in surfaces}
    assert GROUND in levels


def test_level_relationships_are_semantic_neighbours_not_elevations():
    _, contract = _build_living_garden()
    surfaces = {
        surface["level"]: surface
        for surface in floor_intents_of_type(contract, FLOOR_SURFACE)
    }

    ground = surfaces[GROUND]

    assert ground["level_above"] == UPPER
    assert ground["level_below"] == SITE_LEVEL


def test_a_roof_level_gets_a_roof_surface_intent():
    graph = _graph(
        spaces=[
            {"name": "Living", "space_type": "living_room", "floor": GROUND},
            {"name": "Master", "space_type": "bedroom", "floor": UPPER},
            {"name": "Roof", "space_type": "roof_access", "floor": ROOF},
        ],
        vertical=_villa_vertical(),
    )
    contract = build_spatial_geometry_intent_contract(graph)

    surfaces = floor_intents_of_type(contract, FLOOR_ROOF_SURFACE)
    assert surfaces


def test_a_vertical_element_records_the_floor_it_penetrates():
    _, contract = _build_living_garden()
    surfaces = floor_intents_of_type(contract, FLOOR_SURFACE)

    ground = next(surface for surface in surfaces if surface["level"] == GROUND)

    assert ground["penetrations"]
    assert ground["penetrations"][0]["interruption"] == (
        FLOOR_INTERRUPTION_REQUIRED
    )


def test_no_slab_geometry_is_ever_created():
    _, contract = _build_living_garden()

    for record in contract["node_records"]:
        assert record["floor_intent"]["geometry_status"]["state"] == (
            GEOMETRY_STATE_PENDING
        )
        for intent in record["floor_intent"]["floor_intents"]:
            assert intent["geometry_status"]["state"] == GEOMETRY_STATE_PENDING

    assert contract["semantics"]["slab_geometry_created"] is False


# ---------------------------------------------------------------------------
# 5 - roof intent
# ---------------------------------------------------------------------------

def test_only_the_topmost_node_carries_roof_intent():
    _, contract = _build_living_garden()

    ground = record_for_node(contract, f"{DOMAIN_BUILDING}:Living@{GROUND}")
    upper = record_for_node(contract, f"{DOMAIN_BUILDING}:Master@{UPPER}")

    assert ground["roof_intent"]["applies"] is False
    assert ground["roof_intent"]["status"] == STATUS_NOT_REQUIRED
    assert upper["roof_intent"]["applies"] is True


def test_roof_intent_carries_weather_and_drainage_obligations():
    _, contract = _build_living_garden()
    roof = next(
        record["roof_intent"]
        for record in roof_records(contract)
        if record["node_id"] == f"{DOMAIN_BUILDING}:Master@{UPPER}"
    )

    assert "weather_tightness_obligation" in roof["obligations"]
    assert "drainage_intent" in roof["obligations"]


def test_a_terrace_is_never_invented_without_an_evidenced_relationship():
    """FAIL CLOSED: no terrace is asserted when none is evidenced."""

    _, contract = _build_living_garden()

    for record in roof_records(contract):
        roof = record["roof_intent"]
        if roof["roof_role"] != ROOF_ROLE_OCCUPIABLE_TERRACE:
            assert roof["terrace_required"] is False
            assert roof["terrace_status"] == STATUS_UNRESOLVED


def test_an_evidenced_site_space_turns_the_rooftop_into_an_occupiable_terrace():
    """When a site space is related to the topmost level, the terrace is
    ASSERTED - it is a relationship carried by the graph, not a guess."""

    graph = _graph(
        spaces=[
            {"name": "Master", "space_type": "bedroom", "floor": UPPER},
            {"name": "RoofGarden", "space_type": "garden", "floor": SITE_LEVEL},
        ],
        connections=[
            {"from": "Master", "to": "RoofGarden", "type": "visual_connection"}
        ],
    )
    contract = build_spatial_geometry_intent_contract(graph)

    record = record_for_node(contract, f"{DOMAIN_BUILDING}:Master@{UPPER}")
    roof = record["roof_intent"]

    assert roof["applies"] is True
    assert roof["terrace_required"] is True
    assert roof["terrace_status"] == STATUS_RESOLVED
    assert roof["roof_role"] == ROOF_ROLE_OCCUPIABLE_TERRACE
    assert f"{DOMAIN_SITE}:RoofGarden@{SITE_LEVEL}" in roof["terrace_related_node_ids"]


def test_an_occupiable_terrace_imposes_guarding_and_access_obligations():
    graph = _graph(
        spaces=[
            {"name": "Master", "space_type": "bedroom", "floor": UPPER},
            {"name": "RoofGarden", "space_type": "garden", "floor": SITE_LEVEL},
        ],
        connections=[
            {"from": "Master", "to": "RoofGarden", "type": "visual_connection"}
        ],
    )
    contract = build_spatial_geometry_intent_contract(graph)

    roof = record_for_node(
        contract, f"{DOMAIN_BUILDING}:Master@{UPPER}"
    )["roof_intent"]

    assert "guarding_obligation" in roof["obligations"]
    assert "roof_access_intent" in roof["obligations"]


def test_roof_intent_records_the_level_contract_facts_it_consumed():
    graph = _graph(
        spaces=[
            {"name": "Living", "space_type": "living_room", "floor": GROUND},
            {"name": "Master", "space_type": "bedroom", "floor": UPPER},
        ],
        vertical=_villa_vertical(),
    )
    contract = build_spatial_geometry_intent_contract(
        graph,
        level_contract_semantics={FACT_ROOF_IS_REAL_LEVEL: True},
    )

    roof = next(
        record["roof_intent"]
        for record in roof_records(contract)
        if record["node_id"] == f"{DOMAIN_BUILDING}:Master@{UPPER}"
    )

    assert roof["roof_role"] == ROOF_ROLE_TOP_TERMINATION
    assert roof["level_facts_consumed"][FACT_ROOF_IS_REAL_LEVEL] is True


def test_no_roof_geometry_is_ever_created():
    _, contract = _build_living_garden()

    for record in roof_records(contract):
        assert record["roof_intent"]["geometry_status"]["state"] == (
            GEOMETRY_STATE_PENDING
        )

    assert contract["semantics"]["roof_geometry_created"] is False


# ---------------------------------------------------------------------------
# 6 - spatial adjacency intent (opening + circulation preservation)
# ---------------------------------------------------------------------------

def test_adjacency_preserves_the_relationship_view():
    _, contract = _build_living_garden()
    record = record_for_node(contract, f"{DOMAIN_BUILDING}:Living@{GROUND}")

    adjacency = record["spatial_adjacency"]

    assert f"{DOMAIN_BUILDING}:Kitchen@{GROUND}" in adjacency["adjacent_node_ids"]
    assert f"{DOMAIN_SITE}:Garden@{SITE_LEVEL}" in (
        adjacency["visual_connection_node_ids"]
    )


def test_adjacency_records_the_vertical_node_it_touches():
    _, contract = _build_living_garden()
    record = record_for_node(contract, f"{DOMAIN_BUILDING}:Living@{GROUND}")

    assert record["spatial_adjacency"]["vertical_node_ids"]


def test_adjacency_creates_no_geometry():
    _, contract = _build_living_garden()

    for record in contract["node_records"]:
        assert record["spatial_adjacency"]["geometry_status"]["state"] == (
            GEOMETRY_STATE_PENDING
        )


# ---------------------------------------------------------------------------
# opening / boundary intent compatibility with ARCH-GEOMETRY-02
# ---------------------------------------------------------------------------

def test_boundary_ids_are_echoed_from_the_opening_boundary_contract():
    graph, _ = _build_living_garden()
    opening_boundary = build_opening_boundary_intent_contract(graph)

    contract = build_spatial_geometry_intent_contract(
        graph, opening_boundary_contract=opening_boundary
    )

    for record in contract["node_records"]:
        echo = record["boundary_echo"]
        assert echo["echoed"] is True
        assert echo["agrees_with_opening_boundary_contract"] is True


def test_boundary_echo_is_absent_rather_than_faked_when_no_contract_is_given():
    _, contract = _build_living_garden()

    for record in contract["node_records"]:
        echo = record["boundary_echo"]
        assert echo["echoed"] is False
        assert echo["agrees_with_opening_boundary_contract"] is None


def test_stair_core_interface_is_compatible_with_the_boundary_taxonomy():
    _, contract = _build_living_garden()

    for intent in wall_intents_of_type(contract, WALL_CORE_ENCLOSURE):
        assert intent["boundary_type"] == BOUNDARY_CORE


# ---------------------------------------------------------------------------
# mixed-use separation
# ---------------------------------------------------------------------------

def test_mixed_use_separation_is_preserved_and_never_resolved():
    graph = build_architectural_intent_graph(
        spaces=[
            {"name": "Shop", "space_type": "retail", "floor": GROUND},
            {
                "name": "Apartment",
                "space_type": "living_room",
                "floor": GROUND,
            },
        ],
        vertical_circulation={
            "vertical_elements": [
                {
                    "type": "stair",
                    "role": "shared_core_vertical_circulation",
                    "domain": "mixed_use",
                    "floors": [GROUND, UPPER],
                }
            ]
        },
    )
    contract = build_spatial_geometry_intent_contract(graph)

    # The separation decision is carried through, not resolved here.
    assert "circulation_separation" in contract
    assert contract["semantics"]["decisions_resolved"] is False


# ---------------------------------------------------------------------------
# protected zone
# ---------------------------------------------------------------------------

def test_a_protected_circulation_node_imposes_a_fire_constraint():
    graph = _graph(
        spaces=[
            {"name": "Living", "space_type": "living_room", "floor": GROUND},
        ],
        vertical=_villa_vertical(protected=True),
    )
    contract = build_spatial_geometry_intent_contract(graph)

    record = record_for_node(contract, f"{DOMAIN_BUILDING}:Living@{GROUND}")
    core_intents = [
        intent
        for intent in record["wall_intent"]["wall_intents"]
        if intent["boundary_type"] == BOUNDARY_CORE
    ]

    assert core_intents
    assert core_intents[0]["is_protected_zone_boundary"] is True


# ---------------------------------------------------------------------------
# vehicle_access pending preservation
# ---------------------------------------------------------------------------

def test_vehicle_access_decision_is_carried_as_pending():
    graph = _graph(
        spaces=[
            {"name": "Living", "space_type": "living_room", "floor": GROUND},
            {
                "name": "Parking",
                "space_type": "parking",
                "floor": SITE_LEVEL,
                "vehicle_access_priority": "high",
            },
        ],
        connections=[{"from": "Living", "to": "Parking", "type": "adjacent"}],
    )
    contract = build_spatial_geometry_intent_contract(graph)

    record = record_for_node(contract, f"{DOMAIN_BUILDING}:Living@{GROUND}")
    vehicle = [
        intent
        for intent in record["wall_intent"]["wall_intents"]
        if intent["boundary_type"] == BOUNDARY_SITE_UNRESOLVED
    ]

    assert vehicle[0]["status"] == STATUS_PENDING


# ---------------------------------------------------------------------------
# no numeric leakage
# ---------------------------------------------------------------------------

def _numeric_leaves(value, path="", found=None):
    if found is None:
        found = []

    if isinstance(value, bool):
        return found
    if isinstance(value, (int, float)):
        found.append(path)
    elif isinstance(value, dict):
        for key, item in value.items():
            _numeric_leaves(item, f"{path}.{key}", found)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _numeric_leaves(item, f"{path}[{index}]", found)

    return found


def test_no_numeric_leaf_survives_inside_any_node_record():
    """The strongest guard: a finished record may contain NO number at all."""

    _, contract = _build_living_garden()

    for record in contract["node_records"]:
        leaks = _numeric_leaves(record, record["node_id"])
        assert leaks == [], f"numeric leak in {record['node_id']}: {leaks}"


def test_no_numeric_leaf_survives_for_a_graph_declaring_elevations():
    """An elevation or span in the level contract must not reach a record."""

    graph = _graph(
        spaces=[
            {"name": "Living", "space_type": "living_room", "floor": GROUND},
            {"name": "Master", "space_type": "bedroom", "floor": UPPER},
        ],
        vertical=_villa_vertical(),
    )
    contract = build_spatial_geometry_intent_contract(
        graph,
        level_contract_semantics={
            FACT_ROOF_IS_REAL_LEVEL: True,
            "exact_levels": {GROUND: 0.0, UPPER: 3.0},
            "floor_to_floor_metres": 3.0,
        },
    )

    for record in contract["node_records"]:
        leaks = _numeric_leaves(record, record["node_id"])
        assert leaks == []


def test_every_geometry_status_is_pending_everywhere():
    _, contract = _build_living_garden()

    for record in contract["node_records"]:
        assert record["geometry_status"]["state"] == GEOMETRY_STATE_PENDING

        for block in (
            "space_containment",
            "envelope",
            "wall_intent",
            "floor_intent",
            "roof_intent",
            "spatial_adjacency",
        ):
            assert record[block]["geometry_status"]["state"] == (
                GEOMETRY_STATE_PENDING
            )


def test_pending_geometry_blocks_are_queryable():
    _, contract = _build_living_garden()

    blocks = pending_geometry_blocks(contract)

    assert blocks


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------

def test_output_is_deterministic_for_identical_input():
    graph = _graph(
        spaces=[
            {"name": "Living", "space_type": "living_room", "floor": GROUND},
            {"name": "Garden", "space_type": "garden", "floor": SITE_LEVEL},
        ],
        vertical=_villa_vertical(),
        connections=[{"from": "Living", "to": "Garden", "type": "visual_connection"}],
    )

    first = build_spatial_geometry_intent_contract(graph)
    second = build_spatial_geometry_intent_contract(graph)

    assert first == second


def test_level_stack_is_ordered_semantically_not_alphabetically():
    """Regression: 'roof' must never sort before 'ground'/'upper'."""

    graph = _graph(
        spaces=[
            {"name": "Living", "space_type": "living_room", "floor": GROUND},
            {"name": "Master", "space_type": "bedroom", "floor": UPPER},
            {"name": "Roof", "space_type": "roof_access", "floor": ROOF},
            {"name": "Garden", "space_type": "garden", "floor": SITE_LEVEL},
        ],
        vertical=_villa_vertical(),
    )
    contract = build_spatial_geometry_intent_contract(graph)

    assert contract["level_stack"] == [SITE_LEVEL, GROUND, UPPER, ROOF]


def test_a_declared_elevation_is_not_consumed_as_a_level():
    graph = _graph(
        spaces=[
            {"name": "Living", "space_type": "living_room", "floor": GROUND},
            {"name": "Master", "space_type": "bedroom", "floor": UPPER},
        ],
        vertical=_villa_vertical(),
    )
    contract = build_spatial_geometry_intent_contract(
        graph,
        level_contract_semantics={"exact_levels": {GROUND: 0.0, UPPER: 3.0}},
    )

    assert contract["semantics"]["elevations_consumed"] is False
    assert contract["level_stack"] == [GROUND, UPPER]


# ---------------------------------------------------------------------------
# level contract semantics - only the named facts are read
# ---------------------------------------------------------------------------

def test_level_contract_semantics_only_reports_the_named_facts():
    graph = _graph(
        spaces=[
            {"name": "Living", "space_type": "living_room", "floor": GROUND},
        ],
    )
    contract = build_spatial_geometry_intent_contract(
        graph,
        level_contract_semantics={
            FACT_ROOF_IS_REAL_LEVEL: True,
            "some_elevation": 3.0,
        },
    )

    consumed = contract["level_contract_semantics_consumed"]

    assert consumed[FACT_ROOF_IS_REAL_LEVEL] is True
    assert "some_elevation" not in consumed


def test_non_semantic_level_entries_are_reported_as_ignored():
    graph = _graph(
        spaces=[
            {"name": "Living", "space_type": "living_room", "floor": GROUND},
        ],
    )
    contract = build_spatial_geometry_intent_contract(
        graph,
        level_contract_semantics={
            FACT_ROOF_IS_REAL_LEVEL: True,
            "some_elevation": 3.0,
        },
    )

    assert "non_semantic_level_contract_entries_ignored" in (
        contract["status"]["reasons"]
    )


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def test_contract_status_is_resolved_when_records_exist():
    _, contract = _build_living_garden()

    assert contract["status"]["state"] == STATE_RESOLVED


def test_summary_tallies_are_the_only_numbers_in_the_contract():
    _, contract = _build_living_garden()

    summary = contract["summary"]
    for key in (
        "containment_by_kind",
        "classification_by_kind",
        "wall_intents_by_type",
        "floor_intents_by_type",
        "roof_intents_by_role",
    ):
        assert key in summary
        for value in summary[key].values():
            assert isinstance(value, int)

    assert isinstance(summary["envelope_participants"], int)
