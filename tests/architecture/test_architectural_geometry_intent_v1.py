"""Focused tests for the Architectural Geometry Intent Contract (ARCH-GEOMETRY-01).

The contract projects the Architectural Intent Graph into one geometry-intent
record per node. It creates no geometry, no coordinate and no dimension, and it
resolves no pending decision.
"""

import copy

import pytest

from core.architecture.reasoning.architectural_geometry_intent_v1 import (
    DOMAIN_AXIS_CIRCULATION,
    DOMAIN_AXIS_SPACE,
    DOMAIN_BUILDING,
    DOMAIN_SITE,
    GEOMETRY_STATE_PENDING,
    OPENING_DAYLIGHT_PRIORITY_HIGH,
    OPENING_EXTERIOR_GLAZING,
    STATUS_PENDING,
    build_geometry_intent_contract,
    intent_for_node,
    pending_geometry_records,
    records_for_domain,
)
from core.architecture.reasoning.architectural_intent_graph_v1 import (
    build_architectural_intent_graph,
)
from core.architecture.reasoning.knowledge_space_generator import (
    KnowledgeSpaceGenerator,
)
from core.architecture.reasoning.layout_reasoner import LayoutReasoner
from core.architecture.reasoning.vertical_circulation_intelligence_v2 import (
    resolve_vertical_circulation_intelligence,
)


DESIGN_CONCEPT = {"building_type": "villa"}

VILLA_WITH_BASEMENT = {
    "building_type": "villa",
    "requirements": ["garden", "parking"],
    "levels": {"above_ground": 2, "basement": 1},
}

MIXED_USE = {"building_type": "mixed_use", "levels": {"above_ground": 2}}

RECORD_KEYS = (
    "node_id",
    "space_identity",
    "domain",
    "domain_axis",
    "floor",
    "semantic_role",
    "geometry_requirements",
    "adjacency_requirements",
    "opening_requirements",
    "circulation_requirements",
    "geometry_status",
)


@pytest.fixture(scope="module")
def generator():
    return KnowledgeSpaceGenerator()


@pytest.fixture(scope="module")
def reasoner():
    return LayoutReasoner()


def _graph(generator, reasoner, intent):
    generated = generator.generate(dict(intent))
    layout = reasoner.generate(
        generated["generated_spaces"],
        generated["relationships"],
        dict(DESIGN_CONCEPT),
        generated_site_spaces=generated["generated_site_spaces"],
    )
    circulation = resolve_vertical_circulation_intelligence(
        building_type=intent["building_type"], levels=intent.get("levels")
    )

    return build_architectural_intent_graph(
        spaces=generated["generated_spaces"] + generated["generated_site_spaces"],
        vertical_circulation=circulation,
        connections=layout["connections"],
    )


def _contract(generator, reasoner, intent):
    return build_geometry_intent_contract(_graph(generator, reasoner, intent))


def _record(contract, node_id):
    record = intent_for_node(contract, node_id)
    assert record is not None, f"no intent for {node_id}"

    return record


def _numeric_values(value):
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _numeric_values(child)]
    if isinstance(value, (list, tuple)):
        return [item for child in value for item in _numeric_values(child)]

    return []


# ---------------------------------------------------------------------------
# contract shape
# ---------------------------------------------------------------------------

def test_contract_shape(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    assert contract["type"] == "architectural_geometry_intent"
    assert contract["version"] == "architectural_geometry_intent_v1"
    assert sorted(contract.keys()) == [
        "circulation_separation",
        "domains",
        "node_intents",
        "pending_decisions",
        "semantics",
        "status",
        "type",
        "version",
    ]


def test_every_record_has_the_required_keys(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    assert contract["node_intents"]
    for record in contract["node_intents"]:
        assert sorted(record.keys()) == sorted(RECORD_KEYS)


def test_one_record_per_graph_node(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_BASEMENT)
    contract = build_geometry_intent_contract(graph)

    assert [record["node_id"] for record in contract["node_intents"]] == [
        node["node_id"] for node in graph["nodes"]
    ]


# ---------------------------------------------------------------------------
# REQUIRED: living room geometry intent
# ---------------------------------------------------------------------------

def test_living_room_geometry_intent(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)
    living = _record(contract, "building:living@ground_floor")

    assert living["space_identity"]["name"] == "living"
    assert living["domain"] == DOMAIN_BUILDING
    assert living["domain_axis"] == DOMAIN_AXIS_SPACE
    assert living["floor"] == "ground_floor"
    assert living["semantic_role"]
    assert living["geometry_status"]["state"] == GEOMETRY_STATE_PENDING


def test_living_geometry_requirements_are_pending(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)
    requirements = _record(
        contract, "building:living@ground_floor"
    )["geometry_requirements"]

    assert requirements["status"] == STATUS_PENDING
    assert requirements["requires_geometry"] is True
    assert requirements["dimensional_status"] == STATUS_PENDING
    assert isinstance(requirements["protected_zone"], bool)
    assert requirements["semantic_intent"]
    assert requirements["reasons"]


def test_living_adjacency_and_circulation_requirements(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)
    living = _record(contract, "building:living@ground_floor")

    assert living["adjacency_requirements"]["adjacent_nodes"]
    assert living["circulation_requirements"]["vertical_nodes"]
    assert living["adjacency_requirements"]["status"] == STATUS_PENDING


# ---------------------------------------------------------------------------
# REQUIRED: garden remains site semantic
# ---------------------------------------------------------------------------

def test_garden_remains_site_semantic(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)
    garden = _record(contract, "site:garden@site_level")

    assert garden["domain"] == DOMAIN_SITE
    assert garden["domain_axis"] == DOMAIN_AXIS_SPACE
    assert garden["floor"] == "site_level"
    assert garden["geometry_status"]["state"] == GEOMETRY_STATE_PENDING


def test_garden_is_not_a_building_record(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    building_ids = {
        record["node_id"]
        for record in records_for_domain(
            contract, DOMAIN_BUILDING, axis=DOMAIN_AXIS_SPACE
        )
    }

    assert "site:garden@site_level" not in building_ids


def test_site_and_building_records_are_separated(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    site = records_for_domain(contract, DOMAIN_SITE, axis=DOMAIN_AXIS_SPACE)
    building = records_for_domain(
        contract, DOMAIN_BUILDING, axis=DOMAIN_AXIS_SPACE
    )

    assert {record["node_id"] for record in site} == {
        "site:garden@site_level",
        "site:parking@site_level",
    }
    assert building
    assert {r["node_id"] for r in site}.isdisjoint(
        {r["node_id"] for r in building}
    )


def test_garden_exterior_glazing_intent(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)
    living = _record(contract, "building:living@ground_floor")

    assert living["adjacency_requirements"]["cross_domain_nodes"] == [
        "site:garden@site_level"
    ]
    assert OPENING_EXTERIOR_GLAZING in (
        living["opening_requirements"]["opening_intents"]
    )
    assert OPENING_DAYLIGHT_PRIORITY_HIGH in (
        living["opening_requirements"]["opening_intents"]
    )


# ---------------------------------------------------------------------------
# REQUIRED: stair geometry pending
# ---------------------------------------------------------------------------

def test_stair_geometry_is_pending(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    stairs = [
        record
        for record in contract["node_intents"]
        if record["space_identity"]["kind"] == "vertical_element"
        and record["semantic_role"] == "primary_vertical_circulation"
    ]

    assert stairs
    for record in stairs:
        assert record["geometry_status"]["state"] == GEOMETRY_STATE_PENDING
        assert record["domain_axis"] == DOMAIN_AXIS_CIRCULATION
        assert record["floor"] is None


def test_stair_is_not_treated_as_an_exterior_adjacency(generator, reasoner):
    """A space reaching its own stair is internal circulation, not a
    building/site crossing."""

    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)
    living = _record(contract, "building:living@ground_floor")

    for node_id in living["adjacency_requirements"]["cross_domain_nodes"]:
        assert node_id.startswith("site:")


def test_vertical_relationships_are_preserved(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    for record in contract["node_intents"]:
        if record["space_identity"]["kind"] != "vertical_element":
            continue

        connected = any(
            record["node_id"] in other["circulation_requirements"]["vertical_nodes"]
            for other in contract["node_intents"]
        )
        assert connected, f"{record['node_id']} is not referenced anywhere"


def test_ramps_are_vertical_relationships_not_only_vehicle_ones(generator, reasoner):
    """A ramp moves something between levels, so it must answer the question
    "which vertical elements serve this node?" - not only the vehicle one.

    The graph wires vehicle elements with a ``vehicle_access`` edge and other
    elements with a ``vertical_connection`` edge. That distinction encodes the
    PENDING ramp-vs-car-lift decision, NOT verticality. Collapsing it into
    ``vehicle_nodes`` alone would hide the ramp from any consumer that reads
    only ``vertical_nodes``.
    """

    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)
    parking = _record(contract, "site:parking@site_level")
    requirements = parking["circulation_requirements"]

    ramps = [
        node_id
        for node_id in requirements["vehicle_nodes"]
        if "ramp" in node_id
    ]
    assert ramps

    for ramp_id in ramps:
        assert ramp_id in requirements["vertical_nodes"], (
            f"{ramp_id} is a vehicle node but missing from vertical_nodes"
        )


def test_vertical_connection_edges_are_not_reported_as_cross_domain(
    generator, reasoner
):
    """A building space reaching its own stair is internal circulation.

    The graph flags the edge cross_domain because it compares the raw domain
    strings across two different axes ("building" vs "residential"). The
    geometry contract must not inherit that: only a building/site crossing
    between SPACE nodes is an exterior condition.
    """

    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)
    living = _record(contract, "building:living@ground_floor")

    # The living room IS served by a stair and a lift...
    assert living["circulation_requirements"]["vertical_nodes"]

    # ...and that must not have produced a single cross-domain adjacency.
    assert living["adjacency_requirements"]["cross_domain_nodes"] == [
        "site:garden@site_level"
    ]


def test_no_vertical_element_record_is_ever_cross_domain(generator, reasoner):
    """Exhaustive form of the rule above, across every space node."""

    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    vertical_ids = {
        record["node_id"]
        for record in contract["node_intents"]
        if record["domain_axis"] == DOMAIN_AXIS_CIRCULATION
    }
    assert vertical_ids

    for record in contract["node_intents"]:
        if record["domain_axis"] != DOMAIN_AXIS_SPACE:
            continue

        leaked = vertical_ids & set(
            record["adjacency_requirements"]["cross_domain_nodes"]
        )
        assert not leaked, f"{record['node_id']} reports {leaked} as cross-domain"


def test_site_domain_on_both_axes_is_disambiguated(generator, reasoner):
    """``"site"`` is a legal value on BOTH axes: the parking space (space axis)
    and the ramp that serves it (circulation axis). Only ``domain_axis``
    separates them."""

    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    site_space = [
        record
        for record in contract["node_intents"]
        if record["domain"] == DOMAIN_SITE
        and record["domain_axis"] == DOMAIN_AXIS_SPACE
    ]
    site_circulation = [
        record
        for record in contract["node_intents"]
        if record["domain"] == DOMAIN_SITE
        and record["domain_axis"] == DOMAIN_AXIS_CIRCULATION
    ]

    assert {record["node_id"] for record in site_space} == {
        "site:garden@site_level",
        "site:parking@site_level",
    }
    assert any(
        "ramp" in record["node_id"] for record in site_circulation
    )
    assert {r["node_id"] for r in site_space}.isdisjoint(
        {r["node_id"] for r in site_circulation}
    )


# ---------------------------------------------------------------------------
# REQUIRED: ramp geometry pending
# ---------------------------------------------------------------------------

def test_ramp_geometry_is_pending(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    ramps = [
        record
        for record in contract["node_intents"]
        if record["semantic_role"] == "vehicle_vertical_circulation"
    ]

    assert ramps
    for record in ramps:
        assert record["geometry_status"]["state"] == GEOMETRY_STATE_PENDING
        assert record["geometry_status"]["reason"]


def test_vehicle_pending_state_is_preserved(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)
    parking = _record(contract, "site:parking@site_level")

    assert parking["circulation_requirements"]["vehicle_access_status"] == (
        STATUS_PENDING
    )
    assert parking["circulation_requirements"]["vehicle_nodes"]


def test_vehicle_decision_is_propagated_not_resolved(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    decisions = {decision["decision"] for decision in contract["pending_decisions"]}

    assert "vehicle_access_mode" in decisions
    assert contract["semantics"]["decisions_resolved"] is False


def test_non_vehicle_site_space_has_no_vehicle_connection(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)
    garden = _record(contract, "site:garden@site_level")

    assert garden["circulation_requirements"]["vehicle_nodes"] == []
    assert garden["circulation_requirements"]["vehicle_access_status"] is None


# ---------------------------------------------------------------------------
# REQUIRED: mixed-use separation
# ---------------------------------------------------------------------------

def test_mixed_use_separation_is_carried(generator, reasoner):
    contract = _contract(generator, reasoner, MIXED_USE)

    separation = contract["circulation_separation"]

    assert separation is not None
    assert separation["shared_core"] is True
    assert separation["separation_required"] is True


def test_mixed_use_records_keep_their_domain(generator, reasoner):
    contract = _contract(generator, reasoner, MIXED_USE)

    for record in contract["node_intents"]:
        if record["domain_axis"] == DOMAIN_AXIS_SPACE:
            assert record["domain"] in (DOMAIN_BUILDING, DOMAIN_SITE)
        else:
            assert record["domain"] in (
                "residential",
                "commercial",
                "mixed_use",
                "site",
            )


def test_mixed_use_shared_core_is_visible_in_the_contract(generator, reasoner):
    contract = _contract(generator, reasoner, MIXED_USE)

    shared = [
        record
        for record in contract["node_intents"]
        if record["semantic_role"] == "shared_core_vertical_circulation"
    ]

    assert shared


# ---------------------------------------------------------------------------
# protected zones
# ---------------------------------------------------------------------------

def test_protected_zone_is_preserved(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    stair = next(
        record
        for record in contract["node_intents"]
        if record["semantic_role"] == "primary_vertical_circulation"
    )
    service_stair = next(
        (
            record
            for record in contract["node_intents"]
            if record["semantic_role"] == "service_vertical_circulation"
        ),
        None,
    )

    assert stair["geometry_requirements"]["protected_zone"] is True
    if service_stair is not None:
        assert service_stair["geometry_requirements"]["protected_zone"] is False


def test_protected_zone_requirement_token(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    stair = next(
        record
        for record in contract["node_intents"]
        if record["semantic_role"] == "primary_vertical_circulation"
    )

    assert "protected_zone_geometry_required" in (
        stair["geometry_requirements"]["requirements"]
    )


# ---------------------------------------------------------------------------
# no geometry / no coordinates / no dimensions
# ---------------------------------------------------------------------------

def test_no_numeric_value_anywhere_in_the_contract(generator, reasoner):
    """Structural guarantee: no dimension can leak into this contract."""

    for intent in (VILLA_WITH_BASEMENT, MIXED_USE):
        contract = _contract(generator, reasoner, intent)

        assert _numeric_values(contract) == []


def test_dimensions_injected_upstream_are_stripped_at_the_boundary(
    generator, reasoner
):
    """The numeric guarantee must not depend on an upstream module continuing
    to drop dimensions.

    The spatial contract deliberately preserves ``resolved_dimensions`` and
    ``dimensional_requirements`` in ``metadata``, and the graph node builder
    surfaces a node's ``architectural_intent`` verbatim. Injecting dimensions
    into both simulates the future graph change that WOULD surface them: the
    flat numeric entries are dropped by the intent cleaner, and the sweep is
    the backstop for anything reaching the record another way.
    """

    graph = _graph(generator, reasoner, VILLA_WITH_BASEMENT)

    for node in graph["nodes"]:
        node["resolved_dimensions"] = {
            "width": 4.2,
            "depth": 5.5,
            "area": 23.1,
            "status": "resolved_from_circulation",
        }
        node["dimensional_requirements"] = {
            "minimum_width": 3.0,
            "preferred_area": 24.0,
        }
        # architectural_intent IS projected, so this is the live leak vector.
        node["architectural_intent"] = {
            **dict(node.get("architectural_intent") or {}),
            "ceiling_height": 3.2,
            "target_area": 24.0,
            "daylight_priority": "high",
        }

    contract = build_geometry_intent_contract(graph)

    assert _numeric_values(contract) == []
    assert "numeric_intent_entries_dropped_as_dimensions" in (
        contract["status"]["reasons"]
    )


def test_the_record_sweep_is_a_real_backstop():
    """Unit-level proof that the sweep removes nested numeric leaves and
    reports what it removed, independently of which keys the projection
    currently carries."""

    from core.architecture.reasoning.architectural_geometry_intent_v1 import (
        _strip_numeric_leaves,
    )

    dropped = []
    cleaned = _strip_numeric_leaves(
        {
            "keep": "value",
            "drop_scalar": 4.2,
            "nested": {"depth": 5.5, "ok": "kept"},
            "list": [1, "kept", 2.5],
            "flag": True,
        },
        dropped,
    )

    assert cleaned == {
        "keep": "value",
        "nested": {"ok": "kept"},
        "list": ["kept"],
        "flag": True,
    }
    assert sorted(dropped) == ["depth", "drop_scalar"]


def test_numeric_guard_preserves_booleans_and_strings(generator, reasoner):
    """Booleans are ``int`` subclasses but are not dimensions, and must not be
    caught by the numeric guard."""

    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)
    living = _record(contract, "building:living@ground_floor")

    assert living["geometry_requirements"]["requires_geometry"] is True
    assert isinstance(living["geometry_requirements"]["protected_zone"], bool)
    assert contract["semantics"]["metadata_only"] is True
    assert contract["semantics"]["geometry_created"] is False
    assert living["space_identity"]["kind"] == "building_space"


def test_no_coordinate_or_geometry_keys(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    def keys(value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield key
                yield from keys(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from keys(item)

    present = set(keys(contract))

    for forbidden in (
        "coordinates",
        "polygon",
        "geometry",
        "bounds",
        "position",
        "centroid",
        "footprint",
        "walls",
        "slabs",
        "openings",
        "mesh",
        "vertices",
        "x",
        "y",
        "z",
    ):
        assert forbidden not in present


def test_semantics_declare_no_geometry(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    assert contract["semantics"] == {
        "metadata_only": True,
        "geometry_created": False,
        "coordinates_created": False,
        "dimensions_created": False,
        "polygons_created": False,
        "openings_generated": False,
        "walls_generated": False,
        "slabs_generated": False,
        "decisions_resolved": False,
    }


def test_every_record_geometry_is_pending(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    assert len(pending_geometry_records(contract)) == len(
        contract["node_intents"]
    )


def test_a_resolved_source_state_is_forced_back_to_pending(generator, reasoner):
    """This phase never authorises geometry, whatever the source claims."""

    graph = _graph(generator, reasoner, VILLA_WITH_BASEMENT)
    graph["nodes"][0]["geometry_status"] = {
        "state": "resolved",
        "reason": "claimed_elsewhere",
    }

    contract = build_geometry_intent_contract(graph)

    assert contract["node_intents"][0]["geometry_status"]["state"] == (
        GEOMETRY_STATE_PENDING
    )
    assert "source_geometry_state_forced_pending" in contract["status"]["reasons"]


# ---------------------------------------------------------------------------
# determinism / no mutation
# ---------------------------------------------------------------------------

def test_contract_is_deterministic(generator, reasoner):
    first = _contract(generator, reasoner, VILLA_WITH_BASEMENT)
    second = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    assert first == second
    assert first is not second


def test_graph_is_not_mutated(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_BASEMENT)
    before = copy.deepcopy(graph)

    build_geometry_intent_contract(graph)

    assert graph == before


def test_mutating_the_contract_does_not_corrupt_later_builds(
    generator, reasoner
):
    graph = _graph(generator, reasoner, VILLA_WITH_BASEMENT)

    first = build_geometry_intent_contract(graph)
    first["node_intents"][0]["domain"] = "mutated"
    first["node_intents"][0]["geometry_requirements"]["requirements"].append(
        "injected"
    )

    second = build_geometry_intent_contract(graph)

    assert second["node_intents"][0]["domain"] != "mutated"
    assert "injected" not in (
        second["node_intents"][0]["geometry_requirements"]["requirements"]
    )


# ---------------------------------------------------------------------------
# validation / helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad",
    [None, "x", 3, []],
    ids=["none", "str", "int", "list"],
)
def test_non_graph_input_is_rejected(bad):
    with pytest.raises(ValueError, match="graph must be a mapping"):
        build_geometry_intent_contract(bad)


def test_empty_mapping_is_rejected_as_the_wrong_type():
    """An empty dict IS a mapping, so it passes the mapping guard and fails the
    type guard. The distinction matters: the message tells the caller which
    contract they violated."""

    with pytest.raises(ValueError, match="graph.type must be"):
        build_geometry_intent_contract({})


def test_wrong_graph_type_is_rejected():
    with pytest.raises(ValueError, match="graph.type must be"):
        build_geometry_intent_contract({"type": "something_else"})


def test_intent_for_unknown_node_is_none(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    assert intent_for_node(contract, "building:does_not_exist@nowhere") is None


def test_records_for_domain_axis_validation(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    with pytest.raises(ValueError, match="axis must be"):
        records_for_domain(contract, DOMAIN_SITE, axis="sideways")


def test_records_for_domain_separates_the_axes(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_BASEMENT)

    space_site = records_for_domain(contract, DOMAIN_SITE, axis=DOMAIN_AXIS_SPACE)
    circulation_site = records_for_domain(
        contract, DOMAIN_SITE, axis=DOMAIN_AXIS_CIRCULATION
    )

    assert all(r["domain_axis"] == DOMAIN_AXIS_SPACE for r in space_site)
    assert all(
        r["domain_axis"] == DOMAIN_AXIS_CIRCULATION for r in circulation_site
    )
    assert {r["node_id"] for r in space_site}.isdisjoint(
        {r["node_id"] for r in circulation_site}
    )
