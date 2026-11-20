"""Focused tests for Opening + Boundary Intelligence (ARCH-GEOMETRY-02).

The contract projects the Architectural Intent Graph into one record per node,
carrying the boundaries that node participates in and the SEMANTIC opening
obligations those boundaries create. It creates no boundary, no opening, no
coordinate and no dimension, and it resolves no pending decision.
"""

import copy

import pytest

from core.architecture.reasoning.architectural_intent_graph_v1 import (
    build_architectural_intent_graph,
)
from core.architecture.reasoning.architectural_opening_boundary_intent_v1 import (
    BOUNDARY_CORE,
    BOUNDARY_ENVELOPE,
    BOUNDARY_INTERNAL,
    BOUNDARY_SITE_OPEN,
    BOUNDARY_TYPES,
    DOMAIN_AXIS_CIRCULATION,
    DOMAIN_AXIS_SPACE,
    DOMAIN_BUILDING,
    DOMAIN_SITE,
    EXPOSURE_EXTERIOR,
    EXPOSURE_INTERIOR,
    EXPOSURE_INTERIOR_ONLY,
    EXPOSURE_SITE_INTERNAL,
    EXPOSURE_UNRESOLVED,
    GEOMETRY_STATE_PENDING,
    OBLIGATION_DAYLIGHT,
    OBLIGATION_EGRESS,
    OBLIGATION_FIRE_PROTECTION,
    OBLIGATION_NATURAL_VENTILATION,
    OBLIGATION_PRIVACY_CONTROL,
    OBLIGATION_VIEW,
    OBLIGATION_WEATHER_TIGHTNESS,
    OPENING_EXTERNAL_ACCESS,
    OPENING_GLAZING,
    OPENING_INTERNAL_DOORWAY,
    OPENING_ROLES,
    OPENING_VEHICLE_ACCESS,
    OPENING_VERTICAL_ACCESS,
    SEPARATION_REQUIRED,
    SEPARATION_SHARED,
    STATUS_FORBIDDEN,
    STATUS_PENDING,
    STATUS_RESOLVED,
    STATUS_UNRESOLVED,
    boundaries_of_type,
    build_opening_boundary_intent_contract,
    envelope_boundaries,
    openings_with_role,
    pending_openings,
    record_for_node,
)
from core.architecture.reasoning.knowledge_space_generator import (
    KnowledgeSpaceGenerator,
)
from core.architecture.reasoning.layout_reasoner import LayoutReasoner
from core.architecture.reasoning.vertical_circulation_intelligence_v2 import (
    resolve_vertical_circulation_intelligence,
)


VILLA_WITH_SITE = {
    "building_type": "villa",
    "requirements": ["garden", "parking"],
    "levels": {"above_ground": 2, "basement": 1},
}

MIXED_USE = {"building_type": "mixed_use", "levels": {"above_ground": 2}}

PARKING_ONLY = {
    "building_type": "parking",
    "levels": {"above_ground": 1, "basement": 1},
}

RECORD_KEYS = (
    "node_id",
    "space_identity",
    "domain",
    "domain_axis",
    "space_domain",
    "floor",
    "semantic_role",
    "is_protected_zone",
    "declared_intent",
    "exposure_status",
    "boundaries",
    "opens",
    "declared_opening_obligations",
    "geometry_status",
)

BOUNDARY_KEYS = (
    "boundary_id",
    "boundary_type",
    "exposure",
    "axis",
    "domain_pair",
    "counterpart_node_id",
    "counterpart_kind",
    "counterpart_domain",
    "edge_type",
    "edge_status",
    "separation",
    "obligations",
    "protected_zone",
    "is_envelope",
    "geometry_status",
    "status",
    "reasons",
)

OPENING_KEYS = (
    "opening_id",
    "opening_role",
    "boundary_id",
    "boundary_type",
    "exposure",
    "counterpart_node_id",
    "obligations",
    "separation",
    "serves_protected_zone",
    "geometry_status",
    "dimensional_status",
    "status",
    "reasons",
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
        {"building_type": intent["building_type"]},
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
    return build_opening_boundary_intent_contract(
        _graph(generator, reasoner, intent)
    )


def _record(contract, node_id):
    record = record_for_node(contract, node_id)
    assert record is not None, f"no record for {node_id}"

    return record


def _record_numeric_values(value):
    """Numeric leaves INSIDE a per-node record (the swept surface)."""

    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [value]
    if isinstance(value, dict):
        return [
            item for child in value.values() for item in _record_numeric_values(child)
        ]
    if isinstance(value, (list, tuple)):
        return [
            item for child in value for item in _record_numeric_values(child)
        ]

    return []


def _all_numeric_values(value):
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _all_numeric_values(child)]
    if isinstance(value, (list, tuple)):
        return [item for child in value for item in _all_numeric_values(child)]

    return []


# ---------------------------------------------------------------------------
# contract shape
# ---------------------------------------------------------------------------

def test_contract_shape(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    assert contract["type"] == "architectural_opening_boundary_intent"
    assert contract["version"] == "architectural_opening_boundary_intent_v1"
    assert sorted(contract.keys()) == [
        "boundary_summary",
        "circulation_separation",
        "node_records",
        "opening_summary",
        "pending_decisions",
        "semantics",
        "status",
        "type",
        "version",
    ]


def test_every_record_has_the_required_keys(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    assert contract["node_records"]
    for record in contract["node_records"]:
        assert sorted(record.keys()) == sorted(RECORD_KEYS)


def test_one_record_per_graph_node(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)
    contract = build_opening_boundary_intent_contract(graph)

    assert [record["node_id"] for record in contract["node_records"]] == [
        node["node_id"] for node in graph["nodes"]
    ]


def test_boundary_and_opening_key_sets(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    boundaries = [
        boundary
        for record in contract["node_records"]
        for boundary in record["boundaries"]
    ]
    openings = [
        opening for record in contract["node_records"] for opening in record["opens"]
    ]

    assert boundaries
    assert openings
    for boundary in boundaries:
        assert sorted(boundary.keys()) == sorted(BOUNDARY_KEYS)
    for opening in openings:
        assert sorted(opening.keys()) == sorted(OPENING_KEYS)


# ---------------------------------------------------------------------------
# boundary model
# ---------------------------------------------------------------------------

def test_envelope_boundary_is_derived_from_a_building_site_meeting(
    generator, reasoner
):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)
    living = _record(contract, "building:living@ground_floor")

    envelopes = [
        boundary
        for boundary in living["boundaries"]
        if boundary["boundary_type"] == BOUNDARY_ENVELOPE
    ]

    assert len(envelopes) == 1
    assert envelopes[0]["counterpart_node_id"] == "site:garden@site_level"
    assert envelopes[0]["exposure"] == EXPOSURE_EXTERIOR
    assert envelopes[0]["is_envelope"] is True


def test_envelope_boundary_carries_the_full_exterior_obligation_set(
    generator, reasoner
):
    """An envelope is where daylight, view and weather are at stake."""

    contract = _contract(generator, reasoner, VILLA_WITH_SITE)
    envelope = envelope_boundaries(contract)[0]

    for obligation in (
        OBLIGATION_DAYLIGHT,
        OBLIGATION_VIEW,
        OBLIGATION_WEATHER_TIGHTNESS,
    ):
        assert obligation in envelope["obligations"]


def test_internal_boundary_between_two_building_spaces(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)
    living = _record(contract, "building:living@ground_floor")

    internal = [
        boundary
        for boundary in living["boundaries"]
        if boundary["boundary_type"] == BOUNDARY_INTERNAL
    ]

    assert internal
    for boundary in internal:
        assert boundary["exposure"] == EXPOSURE_INTERIOR
        assert boundary["is_envelope"] is False
        assert boundary["domain_pair"] == [DOMAIN_BUILDING, DOMAIN_BUILDING]


def test_core_interface_is_recognised_for_a_vertical_element(generator, reasoner):
    """A space reaching its own stair is a CORE interface, never a facade.

    The graph flags that edge cross_domain because it compares raw domain
    strings across two different axes. The boundary layer must not inherit it.
    """

    contract = _contract(generator, reasoner, VILLA_WITH_SITE)
    living = _record(contract, "building:living@ground_floor")

    cores = [
        boundary
        for boundary in living["boundaries"]
        if boundary["boundary_type"] == BOUNDARY_CORE
    ]

    assert cores
    for boundary in cores:
        assert boundary["exposure"] == EXPOSURE_INTERIOR
        assert boundary["is_envelope"] is False
        assert boundary["counterpart_kind"] == "vertical_element"


def test_core_interface_carries_egress_and_fire_obligations(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)
    core = boundaries_of_type(contract, BOUNDARY_CORE)[0]

    assert OBLIGATION_EGRESS in core["obligations"]
    assert OBLIGATION_FIRE_PROTECTION in core["obligations"]


def test_no_vertical_element_is_ever_an_envelope(generator, reasoner):
    """Exhaustive: the semantic bug must not resurface as a spurious facade."""

    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    for record in contract["node_records"]:
        for boundary in record["boundaries"]:
            if boundary["counterpart_kind"] == "vertical_element":
                assert boundary["is_envelope"] is False
                assert boundary["boundary_type"] == BOUNDARY_CORE
                assert boundary["exposure"] != EXPOSURE_EXTERIOR


def test_boundary_types_are_all_from_the_taxonomy(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    for record in contract["node_records"]:
        for boundary in record["boundaries"]:
            assert boundary["boundary_type"] in BOUNDARY_TYPES


def test_every_boundary_is_symmetric_across_its_two_endpoints(generator, reasoner):
    """A boundary is a relation: both participants must see it, with the same
    type and exposure, and each listing the other as counterpart."""

    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    index = {}
    for record in contract["node_records"]:
        for boundary in record["boundaries"]:
            key = (record["node_id"], boundary["counterpart_node_id"])
            index[key] = boundary

    assert index
    for (node_id, counterpart), boundary in index.items():
        mirror = index.get((counterpart, node_id))
        assert mirror is not None, f"{node_id} -> {counterpart} is not mirrored"
        assert mirror["boundary_type"] == boundary["boundary_type"]
        assert mirror["exposure"] == boundary["exposure"]
        assert mirror["is_envelope"] == boundary["is_envelope"]


# ---------------------------------------------------------------------------
# opening intent - the four semantic sources
# ---------------------------------------------------------------------------

def test_visual_connection_across_the_envelope_yields_glazing(
    generator, reasoner
):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)
    glazing = openings_with_role(contract, OPENING_GLAZING)

    assert glazing
    for opening in glazing:
        assert opening["boundary_type"] == BOUNDARY_ENVELOPE
        assert opening["exposure"] == EXPOSURE_EXTERIOR
        assert OBLIGATION_DAYLIGHT in opening["obligations"]
        assert OBLIGATION_VIEW in opening["obligations"]


def test_internal_circulation_connection_yields_a_doorway(generator, reasoner):
    """SOURCE 3: an interior circulation edge only functions with an opening.

    This intent is emitted NOWHERE else - neither the intent graph nor the
    ARCH-GEOMETRY-01 contract expresses an internal doorway.
    """

    contract = _contract(generator, reasoner, VILLA_WITH_SITE)
    doorways = openings_with_role(contract, OPENING_INTERNAL_DOORWAY)

    assert doorways
    for opening in doorways:
        assert opening["boundary_type"] == BOUNDARY_INTERNAL
        assert opening["exposure"] == EXPOSURE_INTERIOR


def test_vertical_connection_yields_core_access(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)
    access = openings_with_role(contract, OPENING_VERTICAL_ACCESS)

    assert access
    for opening in access:
        assert opening["boundary_type"] == BOUNDARY_CORE


def test_declared_intent_yields_obligations_without_any_adjacency(
    generator, reasoner
):
    """SOURCE 4: a space may declare daylight with no edge at all.

    This is the specific gap the name-whitelist reasoner leaves: a space whose
    name is not on its list receives ``[]`` silently, even when its own intent
    declares a need.
    """

    contract = _contract(generator, reasoner, VILLA_WITH_SITE)
    with_declared = [
        record
        for record in contract["node_records"]
        if record["declared_opening_obligations"] is not None
    ]

    assert with_declared
    for record in with_declared:
        declared = record["declared_opening_obligations"]
        assert declared["obligation_scope"] == "declared_by_space_intent"
        assert declared["obligations"]
        assert declared["dimensional_status"] == STATUS_PENDING


def test_living_declares_daylight_and_ventilation(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)
    living = _record(contract, "building:living@ground_floor")
    declared = living["declared_opening_obligations"]

    assert OBLIGATION_DAYLIGHT in declared["obligations"]
    assert OBLIGATION_NATURAL_VENTILATION in declared["obligations"]
    assert declared["host_status"] == STATUS_RESOLVED
    assert declared["candidate_boundary_ids"]


def test_a_declared_obligation_with_no_envelope_stays_unresolved(
    generator, reasoner
):
    """Fail closed: an obligation with no placeable host is declared, not
    silently placed or silently dropped."""

    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    unplaced = [
        record
        for record in contract["node_records"]
        if record["declared_opening_obligations"] is not None
        and record["declared_opening_obligations"]["host_status"]
        == STATUS_UNRESOLVED
    ]

    for record in unplaced:
        declared = record["declared_opening_obligations"]
        assert declared["candidate_boundary_ids"] == []
        assert declared["status"] == STATUS_UNRESOLVED
        assert "declared_opening_obligation_has_no_envelope_boundary" in (
            contract["status"]["reasons"]
        )


def test_opening_roles_are_all_from_the_taxonomy(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    for record in contract["node_records"]:
        for opening in record["opens"]:
            assert opening["opening_role"] in OPENING_ROLES


def test_no_opening_is_selected_by_space_name(generator, reasoner):
    """The old reasoner dispatched on ``name in ["living", "family_room"]`` and
    returned ``[]`` for anything else. Every opening here must be justified by a
    boundary plus a semantic source, never by the space's name."""

    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    for record in contract["node_records"]:
        boundary_ids = {
            boundary["boundary_id"] for boundary in record["boundaries"]
        }
        for opening in record["opens"]:
            assert opening["boundary_id"] in boundary_ids
            assert opening["reasons"]


# ---------------------------------------------------------------------------
# REQUIRED: vehicle access remains unresolved
# ---------------------------------------------------------------------------

def test_vehicle_access_opening_is_pending(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)
    vehicle = openings_with_role(contract, OPENING_VEHICLE_ACCESS)

    assert vehicle
    for opening in vehicle:
        assert opening["status"] == STATUS_PENDING
        assert (opening["geometry_status"]["state"] == GEOMETRY_STATE_PENDING)
        assert "vehicle_access_mode_not_resolved" in opening["reasons"]


def test_vehicle_access_mode_is_never_decided(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    assert contract["semantics"]["decisions_resolved"] is False

    decisions = {d["decision"] for d in contract["pending_decisions"]}
    assert any("vehicle_access" in decision for decision in decisions)

    for decision in contract["pending_decisions"]:
        assert decision["status"] in (STATUS_PENDING, STATUS_UNRESOLVED)


def test_parking_exposure_stays_unresolved(generator, reasoner):
    """A vehicle space's exposure depends on the ramp-vs-car-lift mode, so it
    must not be flattened to a settled value."""

    contract = _contract(generator, reasoner, VILLA_WITH_SITE)
    parking = _record(contract, "site:parking@site_level")

    assert parking["exposure_status"] == EXPOSURE_UNRESOLVED
    assert "site_space_vehicle_exposure_pending_mode_decision" in (
        contract["status"]["reasons"]
    )


def test_parking_alone_with_basement_still_pends(generator, reasoner):
    contract = _contract(generator, reasoner, PARKING_ONLY)

    assert openings_with_role(contract, OPENING_VEHICLE_ACCESS)
    assert contract["semantics"]["decisions_resolved"] is False


def test_garden_has_no_vehicle_opening(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)
    garden = _record(contract, "site:garden@site_level")

    roles = {opening["opening_role"] for opening in garden["opens"]}
    assert OPENING_VEHICLE_ACCESS not in roles


# ---------------------------------------------------------------------------
# REQUIRED: building / site separation
# ---------------------------------------------------------------------------

def test_garden_is_site_domain_and_not_a_building_space(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)
    garden = _record(contract, "site:garden@site_level")

    assert garden["space_domain"] == DOMAIN_SITE
    assert garden["domain"] == DOMAIN_SITE
    assert garden["domain_axis"] == DOMAIN_AXIS_SPACE
    assert garden["space_identity"]["kind"] == "site_space"


def test_building_and_site_records_are_separated(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    building = [
        record
        for record in contract["node_records"]
        if record["domain_axis"] == DOMAIN_AXIS_SPACE
        and record["space_domain"] == DOMAIN_BUILDING
    ]
    site = [
        record
        for record in contract["node_records"]
        if record["domain_axis"] == DOMAIN_AXIS_SPACE
        and record["space_domain"] == DOMAIN_SITE
    ]

    assert building
    assert {record["node_id"] for record in site} == {
        "site:garden@site_level",
        "site:parking@site_level",
    }
    assert {r["node_id"] for r in building}.isdisjoint(
        {r["node_id"] for r in site}
    )


def test_site_domain_on_both_axes_is_disambiguated(generator, reasoner):
    """``"site"`` is legal on BOTH axes: the parking space and the ramp that
    serves it. Only ``domain_axis`` / ``space_domain`` separate them."""

    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    site_space_records = [
        record
        for record in contract["node_records"]
        if record["space_domain"] == DOMAIN_SITE
    ]
    site_circulation_records = [
        record
        for record in contract["node_records"]
        if record["domain_axis"] == DOMAIN_AXIS_CIRCULATION
        and record["domain"] == DOMAIN_SITE
    ]

    assert site_space_records
    assert site_circulation_records
    assert {r["node_id"] for r in site_space_records}.isdisjoint(
        {r["node_id"] for r in site_circulation_records}
    )


def test_exposure_status_is_consistent_with_the_boundaries(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    for record in contract["node_records"]:
        has_envelope = any(
            boundary["is_envelope"] for boundary in record["boundaries"]
        )
        if has_envelope:
            assert record["exposure_status"] == EXPOSURE_EXTERIOR
        elif record["space_identity"]["kind"] == "building_space":
            assert record["exposure_status"] == EXPOSURE_INTERIOR_ONLY


# ---------------------------------------------------------------------------
# REQUIRED: mixed-use circulation separation preserved
# ---------------------------------------------------------------------------

def test_mixed_use_separation_is_carried(generator, reasoner):
    contract = _contract(generator, reasoner, MIXED_USE)

    assert contract["circulation_separation"] is not None
    assert contract["circulation_separation"]["separation_required"] is True


def test_mixed_use_boundaries_carry_the_separation_state(generator, reasoner):
    contract = _contract(generator, reasoner, MIXED_USE)

    states = {
        boundary["separation"]
        for record in contract["node_records"]
        for boundary in record["boundaries"]
    }

    assert states
    assert states <= {SEPARATION_REQUIRED, SEPARATION_SHARED}


def test_mixed_use_residential_and_commercial_do_not_share_their_core(
    generator, reasoner
):
    """A shared core and a domain-confined core must not be flattened together.

    A vertical element whose domain names a single use is that use's own
    circulation; the shared core is the one whose domain is the mixed-use
    domain.
    """

    contract = _contract(generator, reasoner, MIXED_USE)

    vertical_domains = {
        record["domain"]
        for record in contract["node_records"]
        if record["domain_axis"] == DOMAIN_AXIS_CIRCULATION
    }

    assert "mixed_use" in vertical_domains
    assert vertical_domains & {"residential", "commercial"}


def test_mixed_use_shared_core_is_reachable(generator, reasoner):
    contract = _contract(generator, reasoner, MIXED_USE)

    shared = [
        record
        for record in contract["node_records"]
        if record["domain_axis"] == DOMAIN_AXIS_CIRCULATION
        and record["domain"] == "mixed_use"
    ]

    assert shared
    for record in shared:
        assert record["boundaries"]


# ---------------------------------------------------------------------------
# REQUIRED: protected zones preserved
# ---------------------------------------------------------------------------

def test_protected_circulation_core_is_flagged(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    stair = next(
        record
        for record in contract["node_records"]
        if record["semantic_role"] == "primary_vertical_circulation"
    )

    assert stair["is_protected_zone"] is True


def test_protected_zone_propagates_onto_the_boundary_and_opening(
    generator, reasoner
):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    stair_boundaries = [
        boundary
        for boundary in boundaries_of_type(contract, BOUNDARY_CORE)
        if "stair" in boundary["counterpart_node_id"]
        or "primary_vertical_circulation" in boundary["counterpart_node_id"]
    ]

    assert stair_boundaries
    assert any(boundary["protected_zone"] for boundary in stair_boundaries)

    protected_openings = [
        opening
        for opening in openings_with_role(contract, OPENING_VERTICAL_ACCESS)
        if opening["serves_protected_zone"]
    ]
    assert protected_openings
    for opening in protected_openings:
        assert OBLIGATION_FIRE_PROTECTION in opening["obligations"]


# ---------------------------------------------------------------------------
# REQUIRED: no geometry, no coordinates, no dimensions
# ---------------------------------------------------------------------------

def test_no_numeric_value_inside_any_record(generator, reasoner):
    """Structural guarantee: no dimension can leak into a record."""

    for intent in (VILLA_WITH_SITE, MIXED_USE, PARKING_ONLY):
        contract = _contract(generator, reasoner, intent)

        for record in contract["node_records"]:
            assert _record_numeric_values(record) == []


def test_the_only_numbers_are_aggregate_tallies(generator, reasoner):
    """The sweep covers records. Everything numeric left in the contract must be
    a TALLY of records - a count, which is structurally incapable of being a
    dimension - and nothing else."""

    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    # 1. No number survives anywhere inside a per-node record.
    assert [
        value
        for record in contract["node_records"]
        for value in _record_numeric_values(record)
    ] == []

    # 2. The summaries hold only non-negative integer tallies.
    for key in ("boundary_summary", "opening_summary"):
        summary = contract[key]
        for inner, value in summary.items():
            if isinstance(value, dict):
                assert all(
                    isinstance(count, int) and count >= 0
                    for count in value.values()
                ), f"{key}.{inner} must be a tally of non-negative integers"
            else:
                assert isinstance(value, int) and value >= 0, (
                    f"{key}.{inner} must be a non-negative integer tally"
                )

    # 3. Those tallies are the whole numeric surface of the contract.
    assert set(_all_numeric_values(contract)) == {
        *contract["boundary_summary"]["by_type"].values(),
        contract["boundary_summary"]["envelope_boundary_count"],
        *contract["opening_summary"]["by_role"].values(),
        contract["opening_summary"]["forbidden_count"],
    }


def test_no_count_is_smuggled_into_a_record(generator, reasoner):
    """A count inside a record would give a consumer a number that could be
    mistaken for a measurement, so records carry none."""

    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    for record in contract["node_records"]:
        assert "boundary_count" not in record
        assert "opening_count" not in record
        assert _record_numeric_values(record) == []


def test_no_coordinate_or_geometry_keys(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

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
        "polygons",
        "bounds",
        "position",
        "centroid",
        "footprint",
        "opening_center",
        "wall_id",
        "host_wall_id",
        "candidate_wall_ids",
        "start",
        "end",
        "mesh",
        "vertices",
        "width",
        "height",
        "depth",
        "area",
        "sill_height",
        "head_height",
        "x",
        "y",
        "z",
    ):
        assert forbidden not in present


def test_semantics_declare_no_geometry(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    assert contract["semantics"] == {
        "metadata_only": True,
        "geometry_created": False,
        "coordinates_created": False,
        "dimensions_created": False,
        "polygons_created": False,
        "boundaries_created": False,
        "openings_created": False,
        "host_walls_assigned": False,
        "decisions_resolved": False,
    }


def test_every_boundary_and_opening_geometry_is_pending(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    for record in contract["node_records"]:
        assert record["geometry_status"]["state"] == GEOMETRY_STATE_PENDING

        for boundary in record["boundaries"]:
            assert boundary["geometry_status"]["state"] == GEOMETRY_STATE_PENDING

    assert len(pending_openings(contract)) == len(
        [
            opening
            for record in contract["node_records"]
            for opening in record["opens"]
        ]
    )


def test_dimensions_injected_upstream_are_stripped(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)

    for node in graph["nodes"]:
        node["architectural_intent"] = {
            **dict(node.get("architectural_intent") or {}),
            "ceiling_height": 3.2,
            "target_area": 24.0,
            "daylight_priority": "high",
        }

    contract = build_opening_boundary_intent_contract(graph)

    for record in contract["node_records"]:
        assert _record_numeric_values(record) == []
    assert "numeric_intent_entries_dropped_as_dimensions" in (
        contract["status"]["reasons"]
    )


def test_openings_declare_no_size(generator, reasoner):
    """An opening intent must carry NO dimensional claim at all."""

    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    for record in contract["node_records"]:
        for opening in record["opens"]:
            assert opening["dimensional_status"] == STATUS_PENDING
            assert _record_numeric_values(opening) == []


# ---------------------------------------------------------------------------
# site open boundary
# ---------------------------------------------------------------------------

def test_site_to_site_edge_hosts_no_opening(generator, reasoner):
    """A site-to-site edge is not an opening. It is recorded FORBIDDEN so the
    absence is a declared decision rather than an omission."""

    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    for record in contract["node_records"]:
        for opening in record["opens"]:
            if opening["boundary_type"] == BOUNDARY_SITE_OPEN:
                assert opening["status"] == STATUS_FORBIDDEN
                assert "open_site_edge_hosts_no_opening" in opening["reasons"]


# ---------------------------------------------------------------------------
# determinism / no mutation / validation
# ---------------------------------------------------------------------------

def test_contract_is_deterministic(generator, reasoner):
    first = _contract(generator, reasoner, VILLA_WITH_SITE)
    second = _contract(generator, reasoner, VILLA_WITH_SITE)

    assert first == second
    assert first is not second


def test_graph_is_not_mutated(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)
    before = copy.deepcopy(graph)

    build_opening_boundary_intent_contract(graph)

    assert graph == before


def test_mutating_the_contract_does_not_corrupt_later_builds(generator, reasoner):
    graph = _graph(generator, reasoner, VILLA_WITH_SITE)

    first = build_opening_boundary_intent_contract(graph)
    first["node_records"][0]["domain"] = "mutated"
    first["node_records"][0]["boundaries"].append({"injected": True})

    second = build_opening_boundary_intent_contract(graph)

    assert second["node_records"][0]["domain"] != "mutated"
    assert all(
        "injected" not in boundary
        for boundary in second["node_records"][0]["boundaries"]
    )


@pytest.mark.parametrize(
    "bad", [None, "x", 3, []], ids=["none", "str", "int", "list"]
)
def test_non_graph_input_is_rejected(bad):
    with pytest.raises(ValueError, match="graph must be a mapping"):
        build_opening_boundary_intent_contract(bad)


def test_empty_mapping_is_rejected_as_the_wrong_type():
    with pytest.raises(ValueError, match="graph.type must be"):
        build_opening_boundary_intent_contract({})


def test_record_for_unknown_node_is_none(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    assert record_for_node(contract, "building:does_not_exist@nowhere") is None


def test_boundaries_of_type_validates_the_taxonomy(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    with pytest.raises(ValueError, match="boundary_type must be"):
        boundaries_of_type(contract, "not_a_boundary_type")


def test_openings_with_role_validates_the_taxonomy(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    with pytest.raises(ValueError, match="opening_role must be"):
        openings_with_role(contract, "not_an_opening_role")


def test_records_with_no_boundary_are_reported(generator, reasoner):
    contract = _contract(generator, reasoner, VILLA_WITH_SITE)

    for record in contract["node_records"]:
        if not record["boundaries"]:
            assert "node_has_no_boundary" in contract["status"]["reasons"]
