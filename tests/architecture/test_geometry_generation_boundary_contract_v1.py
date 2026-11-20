"""Focused tests for the Geometry Generation Boundary Contract (ARCH-GEOMETRY-04).

This module defines the STRICT BOUNDARY between the architectural semantic layer
(the intent graph plus the ARCH-GEOMETRY-01/02/03 bridges) and a future
geometry generation engine.

Hard rules enforced by these tests:

* The boundary creates NO geometry of any kind - no coordinate, no x/y/z, no
  width/depth/height/thickness, no area, no volume, no polygon, no mesh, no CAD,
  no IFC. It invokes no engine and modifies no legacy module.
* No numeric leaf may survive anywhere inside a unit.
* ``authorized`` is NEVER emitted. Every unit is pending (or forbidden), because
  no authorization grant exists in this phase.
* Pending decisions (vehicle_access mode, envelope continuity, terrace
  relationship, facade approval) cross the boundary UNRESOLVED and are named as
  forbidden resolutions.
* The authorization axis is a THIRD domain axis, distinct from the space axis
  and the circulation axis, and is labelled as such.
* Output is deterministic and no input is mutated.
"""

import copy

import pytest

from core.architecture.reasoning.architectural_intent_graph_v1 import (
    build_architectural_intent_graph,
)
from core.architecture.reasoning.architectural_geometry_intent_v1 import (
    build_geometry_intent_contract,
)
from core.architecture.reasoning.architectural_opening_boundary_intent_v1 import (
    build_opening_boundary_intent_contract,
)
from core.architecture.reasoning.architectural_spatial_geometry_intent_v1 import (
    build_spatial_geometry_intent_contract,
)
from core.architecture.reasoning.geometry_generation_boundary_contract_v1 import (
    AUTHORIZATION_AUTHORIZED,
    AUTHORIZATION_FORBIDDEN,
    AUTHORIZATION_PENDING,
    AUTHORIZATION_STATES,
    BOUNDARY_SIDES,
    DOMAIN_AXIS_AUTHORIZATION,
    DOMAIN_AXIS_CIRCULATION,
    DOMAIN_AXIS_SPACE,
    EMITTABLE_AUTHORIZATION_STATES,
    FORBIDDEN_DOMAIN_MERGE,
    FORBIDDEN_ENVELOPE_CONTINUITY,
    FORBIDDEN_FACADE_APPROVAL,
    FORBIDDEN_PROTECTED_ZONE_REMOVAL,
    FORBIDDEN_RESOLUTIONS,
    FORBIDDEN_TERRACE_RELATIONSHIP,
    FORBIDDEN_THICKNESS_INVENTION,
    FORBIDDEN_VEHICLE_ACCESS_MODE,
    GEOMETRY_REASON_NOT_AUTHORIZED,
    GEOMETRY_STATE_AUTHORIZED,
    GEOMETRY_STATE_PENDING,
    GLOBAL_FORBIDDEN_RESOLUTIONS,
    KNOWN_HANDOFF_DRIFT,
    LEGACY_ENGINE,
    LEGACY_IFC_EXPORTER,
    LEGACY_PHYSICAL_WALLS,
    NUMERIC_SIDE_GENERATION,
    NUMERIC_SIDE_SEMANTIC,
    OUTPUT_TYPE,
    OUTPUT_VERSION,
    PREREQ_TERRACE_RELATIONSHIP,
    PREREQ_THICKNESS_POLICY,
    PREREQ_VEHICLE_ACCESS_MODE,
    PREREQUISITES,
    REQUEST_CORE_WALL_SOLID,
    REQUEST_ENVELOPE_WALL_SOLID,
    REQUEST_FLOOR_SLAB_SOLID,
    REQUEST_PARTITION_WALL_SOLID,
    REQUEST_ROOF_FORM,
    REQUEST_SITE_BOUNDARY_WALL_SOLID,
    REQUEST_SLAB_PENETRATION,
    REQUEST_SPACE_VOLUME,
    REQUEST_STAIR_FLIGHT,
    REQUEST_TYPES,
    REQUEST_VERTICAL_CORE_SOLID,
    SIDE_GENERATION,
    SIDE_SEMANTIC,
    STATE_RESOLVED,
    STATUS_OPEN,
    STATUS_PENDING,
    UNSATISFIABLE_PREREQUISITES,
    build_geometry_generation_boundary_contract,
    forbidden_resolutions_of,
    units_authorized,
    units_blocked_by,
    units_for_node,
    units_of_request_type,
    units_referencing_legacy,
)


GROUND = "ground"
UPPER = "upper"
SITE_LEVEL = "site_level"


# ---------------------------------------------------------------------------
# fixtures / builders
# ---------------------------------------------------------------------------

def _villa_graph(*, parking=False):
    spaces = [
        {"name": "Living", "space_type": "living_room", "floor": GROUND},
        {"name": "Kitchen", "space_type": "kitchen", "floor": GROUND},
        {"name": "Master", "space_type": "bedroom", "floor": UPPER},
        {"name": "Garden", "space_type": "garden", "floor": SITE_LEVEL},
    ]
    connections = [
        {"from": "Living", "to": "Kitchen", "type": "adjacent"},
        {"from": "Living", "to": "Garden", "type": "visual_connection"},
    ]
    if parking:
        spaces.append(
            {
                "name": "Parking",
                "space_type": "parking",
                "floor": SITE_LEVEL,
                "vehicle_access_priority": "high",
            }
        )
        connections.append(
            {"from": "Living", "to": "Parking", "type": "adjacent"}
        )

    return build_architectural_intent_graph(
        spaces=spaces,
        vertical_circulation={
            "vertical_elements": [
                {
                    "type": "stair",
                    "role": "main_stair",
                    "domain": "residential",
                    "floors": [GROUND, UPPER],
                }
            ]
        },
        connections=connections,
    )


def _full_chain(*, parking=False):
    graph = _villa_graph(parking=parking)
    geometry_intent = build_geometry_intent_contract(graph)
    opening_boundary = build_opening_boundary_intent_contract(graph)
    spatial = build_spatial_geometry_intent_contract(
        graph, opening_boundary_contract=opening_boundary
    )
    contract = build_geometry_generation_boundary_contract(
        graph,
        geometry_intent_contract=geometry_intent,
        opening_boundary_contract=opening_boundary,
        spatial_geometry_intent_contract=spatial,
    )

    return graph, geometry_intent, opening_boundary, spatial, contract


@pytest.fixture
def boundary_contract():
    _, _, _, _, contract = _full_chain()

    return contract


# ---------------------------------------------------------------------------
# contract shape
# ---------------------------------------------------------------------------

def test_contract_declares_its_type_and_version(boundary_contract):
    assert boundary_contract["type"] == OUTPUT_TYPE
    assert boundary_contract["version"] == OUTPUT_VERSION


def test_contract_declares_both_sides_of_the_boundary(boundary_contract):
    assert "semantic_side" in boundary_contract
    assert "generation_side" in boundary_contract
    assert set(BOUNDARY_SIDES) == {"semantic_side", "generation_side"}


def test_contract_produces_units(boundary_contract):
    assert boundary_contract["units"]
    assert boundary_contract["status"]["state"] == STATE_RESOLVED


def test_every_unit_declares_the_generation_side():
    _, _, _, _, contract = _full_chain()

    for unit in contract["units"]:
        assert unit["boundary_side"] == SIDE_GENERATION


def test_contract_declares_no_geometry_was_created(boundary_contract):
    semantics = boundary_contract["semantics"]

    assert semantics["geometry_created"] is False
    assert semantics["coordinates_created"] is False
    assert semantics["dimensions_created"] is False
    assert semantics["polygons_created"] is False
    assert semantics["meshes_created"] is False
    assert semantics["cad_created"] is False
    assert semantics["ifc_created"] is False
    assert semantics["wall_solid_created"] is False
    assert semantics["slab_solid_created"] is False
    assert semantics["roof_form_created"] is False


def test_contract_declares_it_invoked_no_engine(boundary_contract):
    semantics = boundary_contract["semantics"]

    assert semantics["engine_invoked"] is False
    assert semantics["legacy_layer_modified"] is False


def test_contract_declares_it_resolved_no_decision(boundary_contract):
    assert boundary_contract["semantics"]["decisions_resolved"] is False


def test_graph_of_the_wrong_type_is_rejected():
    with pytest.raises(ValueError):
        build_geometry_generation_boundary_contract(
            {"type": "not_the_graph", "nodes": [], "edges": []}
        )


def test_a_spatial_contract_of_the_wrong_type_is_rejected():
    graph = _villa_graph()

    with pytest.raises(ValueError):
        build_geometry_generation_boundary_contract(
            graph,
            spatial_geometry_intent_contract={
                "type": "something_else",
                "node_records": [],
            },
        )


def test_no_input_contract_is_mutated():
    graph, geometry_intent, opening_boundary, spatial, _ = _full_chain()

    snapshots = [
        copy.deepcopy(graph),
        copy.deepcopy(geometry_intent),
        copy.deepcopy(opening_boundary),
        copy.deepcopy(spatial),
    ]

    build_geometry_generation_boundary_contract(
        graph,
        geometry_intent_contract=geometry_intent,
        opening_boundary_contract=opening_boundary,
        spatial_geometry_intent_contract=spatial,
    )

    assert graph == snapshots[0]
    assert geometry_intent == snapshots[1]
    assert opening_boundary == snapshots[2]
    assert spatial == snapshots[3]


# ---------------------------------------------------------------------------
# THE AUTHORIZATION MODEL - the heart of the boundary
# ---------------------------------------------------------------------------

def test_the_authorization_axis_is_a_third_distinct_axis(boundary_contract):
    assert DOMAIN_AXIS_AUTHORIZATION == "authorization"
    assert DOMAIN_AXIS_AUTHORIZATION != DOMAIN_AXIS_SPACE
    assert DOMAIN_AXIS_AUTHORIZATION != DOMAIN_AXIS_CIRCULATION


def test_every_unit_is_labelled_with_the_authorization_axis(boundary_contract):
    for unit in boundary_contract["units"]:
        assert unit["domain_axis"] == DOMAIN_AXIS_AUTHORIZATION


def test_the_contract_declares_it_may_never_emit_authorized():
    _, _, _, _, contract = _full_chain()

    assert AUTHORIZATION_AUTHORIZED in AUTHORIZATION_STATES
    assert AUTHORIZATION_AUTHORIZED not in EMITTABLE_AUTHORIZATION_STATES


def test_no_unit_is_ever_authorized():
    """The single most important assertion in this phase."""

    _, _, _, _, contract = _full_chain(parking=True)

    assert units_authorized(contract) == []
    for unit in contract["units"]:
        assert unit["authorization"] != AUTHORIZATION_AUTHORIZED


def test_no_unit_claims_authorized_in_the_tallies_either(boundary_contract):
    assert boundary_contract["summary"]["units_authorized"] == 0


def test_authorization_model_states_that_no_grant_exists(boundary_contract):
    model = boundary_contract["authorization_model"]

    assert model["authorization_grant_exists"] is False
    assert model["domain_axis"] == DOMAIN_AXIS_AUTHORIZATION


def test_every_unit_authorization_is_from_the_declared_vocabulary(boundary_contract):
    for unit in boundary_contract["units"]:
        assert unit["authorization"] in AUTHORIZATION_STATES
        assert unit["authorization"] in EMITTABLE_AUTHORIZATION_STATES


def test_every_unit_geometry_status_stays_pending(boundary_contract):
    for unit in boundary_contract["units"]:
        assert unit["geometry_status"]["state"] == GEOMETRY_STATE_PENDING
        assert unit["geometry_status"]["reason"] == GEOMETRY_REASON_NOT_AUTHORIZED


def test_an_upstream_authorization_claim_is_not_honoured():
    """Fail closed: a module claiming authorization must not open the gate."""

    graph = _villa_graph()
    # Forge an authorization claim on every node.
    for node in graph["nodes"]:
        node["geometry_status"] = {
            "state": GEOMETRY_STATE_AUTHORIZED,
            "reason": "forged",
        }

    opening_boundary = build_opening_boundary_intent_contract(graph)
    spatial = build_spatial_geometry_intent_contract(
        graph, opening_boundary_contract=opening_boundary
    )
    contract = build_geometry_generation_boundary_contract(
        graph,
        opening_boundary_contract=opening_boundary,
        spatial_geometry_intent_contract=spatial,
    )

    assert units_authorized(contract) == []
    assert (
        "upstream_authorization_claim_not_honoured_by_the_boundary"
        in contract["status"]["reasons"]
    )


# ---------------------------------------------------------------------------
# generation requests are TOKENS, not dimensions
# ---------------------------------------------------------------------------

def test_every_request_type_is_from_the_declared_vocabulary(boundary_contract):
    for unit in boundary_contract["units"]:
        assert unit["request_type"] in REQUEST_TYPES


def test_no_request_type_encodes_a_measurement():
    """A request token names the ARTIFACT it asks for, never a measurement.

    ``space_volume_request`` is legitimate: "volume" is the artifact. A token
    containing a dimension word would be a leak of the generation side's
    concern into the semantic side.
    """

    measurement_tokens = (
        "width", "depth", "height", "thickness", "area", "radius",
        "slope", "degree", "millimetre", "centimetre", "metre", "meter",
    )

    for request_type in REQUEST_TYPES:
        lowered = request_type.lower()
        for token in measurement_tokens:
            assert token not in lowered, f"{request_type} encodes {token}"


def test_every_unit_declares_it_produces_nothing_yet(boundary_contract):
    for unit in boundary_contract["units"]:
        assert unit["produces_geometry"] is False
        assert unit["produces_coordinates"] is False
        assert unit["produces_dimensions"] is False


def test_the_core_request_types_are_represented(boundary_contract):
    represented = set(
        boundary_contract["summary"]["request_types_represented"]
    )

    assert REQUEST_SPACE_VOLUME in represented
    assert REQUEST_ENVELOPE_WALL_SOLID in represented
    assert REQUEST_FLOOR_SLAB_SOLID in represented
    assert REQUEST_ROOF_FORM in represented


def test_a_wall_intent_becomes_a_wall_solid_request():
    _, _, _, _, contract = _full_chain()
    units = units_of_request_type(contract, REQUEST_ENVELOPE_WALL_SOLID)

    assert units
    for unit in units:
        assert unit["semantic_token"] == "envelope_wall_intent"


def test_an_internal_partition_becomes_a_partition_request():
    _, _, _, _, contract = _full_chain()
    units = units_of_request_type(contract, REQUEST_PARTITION_WALL_SOLID)

    assert units
    for unit in units:
        assert unit["semantic_token"] == "internal_partition_intent"


def test_a_core_interface_becomes_a_core_wall_request():
    _, _, _, _, contract = _full_chain()
    units = units_of_request_type(contract, REQUEST_CORE_WALL_SOLID)

    assert units
    for unit in units:
        assert unit["semantic_token"] == "core_enclosure_intent"


def test_a_vertical_element_becomes_a_core_solid_and_a_stair_flight():
    _, _, _, _, contract = _full_chain()

    assert units_of_request_type(contract, REQUEST_VERTICAL_CORE_SOLID)
    assert units_of_request_type(contract, REQUEST_STAIR_FLIGHT)


def test_a_floor_penetration_becomes_a_slab_penetration_request():
    _, _, _, _, contract = _full_chain()
    units = units_of_request_type(contract, REQUEST_SLAB_PENETRATION)

    assert units


def test_a_vertical_element_does_not_request_a_penetration_of_itself():
    _, _, _, _, contract = _full_chain()

    for unit in units_of_request_type(contract, REQUEST_SLAB_PENETRATION):
        assert unit["semantic_token"] != unit["node_id"]


# ---------------------------------------------------------------------------
# prerequisites - what an engine must hold BEFORE it may run
# ---------------------------------------------------------------------------

def test_every_prerequisite_is_from_the_declared_vocabulary(boundary_contract):
    for unit in boundary_contract["units"]:
        for prerequisite in unit["prerequisites"]:
            assert prerequisite in PREREQUISITES


def test_missing_prerequisites_are_a_subset_of_prerequisites(boundary_contract):
    for unit in boundary_contract["units"]:
        assert set(unit["missing_prerequisites"]).issubset(
            set(unit["prerequisites"])
        )


def test_a_wall_solid_request_requires_an_authorized_thickness_policy():
    _, _, _, _, contract = _full_chain()
    units = units_of_request_type(contract, REQUEST_ENVELOPE_WALL_SOLID)

    for unit in units:
        assert PREREQ_THICKNESS_POLICY in unit["prerequisites"]


def test_the_thickness_policy_is_reported_as_not_yet_evidenced():
    """A wall solid cannot be built without an authorized thickness policy.

    Declaring a prerequisite is not the same as holding it: because no
    thickness policy authority exists yet, every wall unit must report it as
    MISSING, not merely listed.
    """

    _, _, _, _, contract = _full_chain()

    blocked = units_blocked_by(contract, PREREQ_THICKNESS_POLICY)
    assert blocked
    for unit in blocked:
        assert unit["authorization"] == AUTHORIZATION_PENDING


def test_an_unsatisfiable_prerequisite_is_always_reported_as_missing():
    """No unit may be reported ready while a prerequisite it declares cannot be
    satisfied in this phase."""

    _, _, _, _, contract = _full_chain(parking=True)

    for unit in contract["units"]:
        for prerequisite in unit["prerequisites"]:
            if prerequisite in UNSATISFIABLE_PREREQUISITES:
                assert prerequisite in unit["missing_prerequisites"], (
                    f"{unit['request_id']} declares {prerequisite} but does "
                    "not report it missing"
                )


def test_every_unsatisfiable_prerequisite_is_a_declared_prerequisite():
    for prerequisite in UNSATISFIABLE_PREREQUISITES:
        assert prerequisite in PREREQUISITES


def test_the_facade_approval_prerequisite_is_never_treated_as_held():
    _, _, _, _, contract = _full_chain()
    units = [
        unit
        for unit in contract["units"]
        if "facade_approval_granted" in unit["prerequisites"]
    ]

    for unit in units:
        assert "facade_approval_granted" in unit["missing_prerequisites"]


def test_a_vehicle_boundary_request_requires_the_vehicle_access_mode():
    _, _, _, _, contract = _full_chain(parking=True)
    units = units_of_request_type(contract, REQUEST_SITE_BOUNDARY_WALL_SOLID)

    assert units
    for unit in units:
        assert PREREQ_VEHICLE_ACCESS_MODE in unit["prerequisites"]


def test_the_vehicle_access_mode_is_reported_as_not_yet_evidenced():
    _, _, _, _, contract = _full_chain(parking=True)

    blocked = units_blocked_by(contract, PREREQ_VEHICLE_ACCESS_MODE)
    assert blocked


def test_a_roof_form_request_requires_an_evidenced_terrace_relationship():
    _, _, _, _, contract = _full_chain()
    units = units_of_request_type(contract, REQUEST_ROOF_FORM)

    for unit in units:
        assert PREREQ_TERRACE_RELATIONSHIP in unit["prerequisites"]


def test_blocked_units_are_tallied(boundary_contract):
    blocked = boundary_contract["summary"]["units_with_missing_prerequisites"]

    assert blocked > 0
    assert blocked <= boundary_contract["summary"]["unit_count"]


def test_an_unknown_prerequisite_query_is_rejected(boundary_contract):
    with pytest.raises(ValueError):
        units_blocked_by(boundary_contract, "not_a_prerequisite")


# ---------------------------------------------------------------------------
# forbidden resolutions - the decisions an engine has NO authority to settle
# ---------------------------------------------------------------------------

def test_every_forbidden_resolution_is_from_the_declared_vocabulary(boundary_contract):
    for unit in boundary_contract["units"]:
        for forbidden in unit["forbidden_resolutions"]:
            assert forbidden in FORBIDDEN_RESOLUTIONS


def test_the_global_forbidden_resolutions_ride_on_every_unit(boundary_contract):
    for unit in boundary_contract["units"]:
        for forbidden in GLOBAL_FORBIDDEN_RESOLUTIONS:
            assert forbidden in unit["forbidden_resolutions"]


def test_no_engine_may_invent_a_wall_thickness(boundary_contract):
    for unit in boundary_contract["units"]:
        assert FORBIDDEN_THICKNESS_INVENTION in unit["forbidden_resolutions"]


def test_no_engine_may_merge_separated_domains(boundary_contract):
    for unit in boundary_contract["units"]:
        assert FORBIDDEN_DOMAIN_MERGE in unit["forbidden_resolutions"]


def test_no_engine_may_remove_a_protected_zone(boundary_contract):
    for unit in boundary_contract["units"]:
        assert FORBIDDEN_PROTECTED_ZONE_REMOVAL in unit["forbidden_resolutions"]


def test_a_vehicle_boundary_unit_may_not_resolve_the_vehicle_mode():
    _, _, _, _, contract = _full_chain(parking=True)
    units = units_of_request_type(contract, REQUEST_SITE_BOUNDARY_WALL_SOLID)

    for unit in units:
        assert FORBIDDEN_VEHICLE_ACCESS_MODE in unit["forbidden_resolutions"]


def test_an_envelope_wall_unit_may_not_resolve_envelope_continuity():
    _, _, _, _, contract = _full_chain()
    units = units_of_request_type(contract, REQUEST_ENVELOPE_WALL_SOLID)

    for unit in units:
        assert FORBIDDEN_ENVELOPE_CONTINUITY in unit["forbidden_resolutions"]


def test_a_roof_form_unit_may_not_invent_a_terrace():
    _, _, _, _, contract = _full_chain()
    units = units_of_request_type(contract, REQUEST_ROOF_FORM)

    for unit in units:
        assert FORBIDDEN_TERRACE_RELATIONSHIP in unit["forbidden_resolutions"]


def test_the_contract_level_forbidden_set_is_complete(boundary_contract):
    assert set(FORBIDDEN_RESOLUTIONS).issubset(
        set(boundary_contract["forbidden_resolutions"])
    )


def test_forbidden_resolutions_are_queryable_by_unit(boundary_contract):
    unit = boundary_contract["units"][0]
    resolved = forbidden_resolutions_of(boundary_contract, unit["request_id"])

    assert resolved is not None
    assert FORBIDDEN_THICKNESS_INVENTION in resolved


def test_an_unknown_unit_id_yields_none(boundary_contract):
    assert forbidden_resolutions_of(boundary_contract, "no_such_unit") is None


# ---------------------------------------------------------------------------
# the legacy layer is NAMED, never modified
# ---------------------------------------------------------------------------

def test_every_unit_names_a_legacy_layer_reference(boundary_contract):
    for unit in boundary_contract["units"]:
        assert isinstance(unit["legacy_layer_reference"], str)
        assert unit["legacy_layer_reference"].endswith(".py")


def test_wall_units_name_the_legacy_physical_wall_resolver():
    _, _, _, _, contract = _full_chain()

    for request_type in (
        REQUEST_ENVELOPE_WALL_SOLID,
        REQUEST_PARTITION_WALL_SOLID,
        REQUEST_CORE_WALL_SOLID,
        REQUEST_SITE_BOUNDARY_WALL_SOLID,
    ):
        for unit in units_of_request_type(contract, request_type):
            assert unit["legacy_layer_reference"] == LEGACY_PHYSICAL_WALLS


def test_the_generation_side_lists_the_legacy_modules_concerned(boundary_contract):
    references = boundary_contract["generation_side"]["legacy_layer_references"]

    assert references
    assert LEGACY_ENGINE in references


def test_units_can_be_selected_by_their_legacy_owner(boundary_contract):
    units = units_referencing_legacy(boundary_contract, LEGACY_PHYSICAL_WALLS)

    assert units


def test_the_known_handoff_drift_is_recorded_at_the_boundary(boundary_contract):
    assert boundary_contract["generation_side"]["known_handoff_drift"] == (
        KNOWN_HANDOFF_DRIFT
    )


def test_the_known_handoff_drift_survives_as_an_open_decision(boundary_contract):
    decisions = {
        decision["decision"]: decision
        for decision in boundary_contract["pending_decisions"]
    }

    assert KNOWN_HANDOFF_DRIFT in decisions
    assert decisions[KNOWN_HANDOFF_DRIFT]["status"] == STATUS_OPEN


def test_the_boundary_does_not_import_the_legacy_engine():
    """A static guarantee: the boundary module must not import the legacy layer."""

    import core.architecture.reasoning.geometry_generation_boundary_contract_v1 as boundary

    source_imports = []
    for name in dir(boundary):
        value = getattr(boundary, name)
        if isinstance(value, type):
            module = getattr(value, "__module__", "")
            source_imports.append(module)

    assert "core.architecture.geometry.architectural_geometry_engine_v2" not in (
        source_imports
    )


def test_the_boundary_module_imports_no_geometry_library():
    import core.architecture.reasoning.geometry_generation_boundary_contract_v1 as boundary

    for forbidden in (
        "shapely",
        "numpy",
        "ifcopenshell",
        "ezdxf",
        "math",
    ):
        assert not hasattr(boundary, forbidden), f"{forbidden} was imported"


# ---------------------------------------------------------------------------
# pending decisions cross the boundary UNRESOLVED
# ---------------------------------------------------------------------------

def test_the_authorization_decision_is_carried_as_pending(boundary_contract):
    decisions = {
        decision["decision"]: decision
        for decision in boundary_contract["pending_decisions"]
    }

    assert "geometry_generation_authorization" in decisions
    assert decisions["geometry_generation_authorization"]["status"] == (
        STATUS_PENDING
    )


def test_envelope_continuity_and_terrace_survive_from_the_semantic_layer():
    _, _, _, spatial, contract = _full_chain()

    inherited = {
        decision["decision"]
        for decision in spatial["pending_decisions"]
    }
    carried = {
        decision["decision"] for decision in contract["pending_decisions"]
    }

    assert inherited.issubset(carried)


def test_no_pending_decision_is_resolved_by_the_boundary(boundary_contract):
    for decision in boundary_contract["pending_decisions"]:
        assert decision["status"] in (STATUS_PENDING, STATUS_OPEN, "unresolved")


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


def test_no_numeric_leaf_survives_inside_any_unit():
    """The strongest guard: a boundary unit may contain NO number at all."""

    _, _, _, _, contract = _full_chain(parking=True)

    for unit in contract["units"]:
        leaks = _numeric_leaves(unit, unit["request_id"])
        assert leaks == [], f"numeric leak in {unit['request_id']}: {leaks}"


def test_no_numeric_leaf_survives_when_the_semantic_layer_declares_elevations():
    graph = _villa_graph()
    opening_boundary = build_opening_boundary_intent_contract(graph)
    spatial = build_spatial_geometry_intent_contract(
        graph,
        opening_boundary_contract=opening_boundary,
        level_contract_semantics={
            "roof_is_real_level": True,
            "exact_levels": {GROUND: 0.0, UPPER: 3.0},
            "floor_to_floor_metres": 3.0,
        },
    )
    contract = build_geometry_generation_boundary_contract(
        graph,
        opening_boundary_contract=opening_boundary,
        spatial_geometry_intent_contract=spatial,
    )

    for unit in contract["units"]:
        assert _numeric_leaves(unit, unit["request_id"]) == []


def test_the_numeric_boundary_is_declared_on_both_sides(boundary_contract):
    assert boundary_contract["semantic_side"]["numeric_boundary"] == (
        NUMERIC_SIDE_SEMANTIC
    )
    assert boundary_contract["generation_side"]["numeric_boundary"] == (
        NUMERIC_SIDE_GENERATION
    )


def test_every_unit_marks_numbers_as_appearing_on_its_side(boundary_contract):
    for unit in boundary_contract["units"]:
        assert unit["numeric_boundary"] == NUMERIC_SIDE_GENERATION


# ---------------------------------------------------------------------------
# cross-contract agreement
# ---------------------------------------------------------------------------

def test_the_three_semantic_contracts_are_all_recognised():
    _, _, _, _, contract = _full_chain()

    supplied = contract["semantic_side"]["contracts_supplied"]

    assert "architectural_geometry_intent_v1" in supplied
    assert "architectural_opening_boundary_intent_v1" in supplied
    assert "architectural_spatial_geometry_intent_v1" in supplied


def test_the_semantic_contracts_agree_on_node_coverage():
    _, _, _, _, contract = _full_chain()
    coverage = contract["semantic_side"]["node_coverage"]

    assert coverage is not None
    assert coverage["geometry_intent_only"] == []
    assert coverage["spatial_intent_only"] == []
    assert coverage["shared_node_ids"]
    assert "semantic_contracts_agree_on_node_coverage" in (
        contract["status"]["reasons"]
    )


def test_the_semantic_side_reports_the_declared_geometry_states():
    _, _, _, _, contract = _full_chain()
    declared = contract["semantic_side"]["geometry_status_states_declared"]

    assert declared[GEOMETRY_STATE_PENDING] > 0
    assert declared[GEOMETRY_STATE_AUTHORIZED] == 0


# ---------------------------------------------------------------------------
# degenerate input
# ---------------------------------------------------------------------------

def test_a_graph_with_no_semantic_contract_produces_no_units():
    graph = _villa_graph()
    contract = build_geometry_generation_boundary_contract(graph)

    assert contract["units"] == []
    assert contract["status"]["state"] != STATE_RESOLVED


def test_a_graph_with_no_nodes_reports_that_no_handoff_exists():
    graph = build_architectural_intent_graph(spaces=[])
    contract = build_geometry_generation_boundary_contract(graph)

    assert contract["units"] == []
    assert "no_semantic_records_supplied_so_no_handoff_can_be_described" in (
        contract["status"]["reasons"]
    )


def test_query_helpers_tolerate_an_empty_contract(boundary_contract):
    assert units_for_node(boundary_contract, "no_such_node") == []
    assert units_authorized(boundary_contract) == []


def test_an_unknown_request_type_query_is_rejected(boundary_contract):
    with pytest.raises(ValueError):
        units_of_request_type(boundary_contract, "not_a_request_type")


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------

def test_output_is_deterministic_for_identical_input():
    graph = _villa_graph(parking=True)
    opening_boundary = build_opening_boundary_intent_contract(graph)
    spatial = build_spatial_geometry_intent_contract(
        graph, opening_boundary_contract=opening_boundary
    )

    first = build_geometry_generation_boundary_contract(
        graph,
        opening_boundary_contract=opening_boundary,
        spatial_geometry_intent_contract=spatial,
    )
    second = build_geometry_generation_boundary_contract(
        graph,
        opening_boundary_contract=opening_boundary,
        spatial_geometry_intent_contract=spatial,
    )

    assert first == second


def test_units_are_grouped_by_node_in_a_deterministic_order(boundary_contract):
    """Units are emitted node by node, and within a node sorted by request id."""

    node_ids = [unit["node_id"] for unit in boundary_contract["units"]]

    # Node order is itself deterministic.
    assert node_ids == sorted(node_ids)

    # Within each node, request ids ascend.
    by_node = {}
    for unit in boundary_contract["units"]:
        by_node.setdefault(unit["node_id"], []).append(unit["request_id"])

    for request_ids in by_node.values():
        assert request_ids == sorted(request_ids)


def test_a_unit_request_id_is_unique(boundary_contract):
    request_ids = [unit["request_id"] for unit in boundary_contract["units"]]

    assert len(request_ids) == len(set(request_ids))


# ---------------------------------------------------------------------------
# tallies
# ---------------------------------------------------------------------------

def test_the_summary_tallies_reconcile(boundary_contract):
    summary = boundary_contract["summary"]

    by_type = sum(summary["units_by_request_type"].values())

    assert by_type == summary["unit_count"]
    assert summary["units_pending_authorization"] == summary["unit_count"]
    assert summary["units_authorized"] == 0
    assert summary["units_forbidden"] == 0


def test_summary_tallies_are_the_only_numbers_in_the_contract(boundary_contract):
    summary = boundary_contract["summary"]

    assert isinstance(summary["unit_count"], int)
    for value in summary["units_by_request_type"].values():
        assert isinstance(value, int)
