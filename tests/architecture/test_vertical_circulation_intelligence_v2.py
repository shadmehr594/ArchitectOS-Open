"""Focused tests for semantic vertical circulation intelligence (ARCH-VERTICAL-02).

The module derives vertical CIRCULATION INTENT only: element type, role,
connections, floors, domain, protected zone, and a PENDING geometry status.
It never decides dimensions, never creates geometry, and never resolves the
vehicle access mode.
"""

import copy
import inspect

import pytest

import core.architecture.reasoning.vertical_circulation_intelligence_v2 as module
from core.architecture.reasoning.vertical_circulation_intelligence_v2 import (
    DOMAIN_COMMERCIAL,
    DOMAIN_MIXED_USE,
    DOMAIN_RESIDENTIAL,
    DOMAIN_SITE,
    ELEMENT_TYPES,
    GEOMETRY_STATE_PENDING,
    ROLE_COMMERCIAL,
    ROLE_OPTIONAL,
    ROLE_PRIMARY,
    ROLE_PUBLIC,
    ROLE_REQUIRED,
    ROLE_RESIDENTIAL,
    ROLE_SERVICE,
    ROLE_SHARED_CORE,
    ROLE_VEHICLE,
    VEHICLE_ACCESS_CANDIDATES,
    VEHICLE_ACCESS_PENDING,
    elements_of_type,
    elements_with_role,
    resolve_building_domain,
    resolve_vertical_circulation_intelligence,
    served_floors,
)


ELEMENT_KEYS = (
    "type",
    "role",
    "connects",
    "floors",
    "domain",
    "protected_zone",
    "geometry_status",
    "reasons",
)


def _resolve(**kwargs):
    return resolve_vertical_circulation_intelligence(**kwargs)


# ---------------------------------------------------------------------------
# contract shape
# ---------------------------------------------------------------------------

def test_contract_shape():
    contract = _resolve(building_type="villa", levels={"above_ground": 2})

    assert contract["type"] == "vertical_circulation_intelligence"
    assert contract["version"] == "vertical_circulation_intelligence_v2"
    assert sorted(contract.keys()) == [
        "building_domain",
        "building_type",
        "circulation_separation",
        "levels",
        "semantics",
        "served_floors",
        "status",
        "type",
        "vehicle_access",
        "version",
        "vertical_elements",
    ]


def test_every_element_has_the_required_keys():
    for building_type, levels in (
        ("villa", {"above_ground": 2}),
        ("office", {"above_ground": 2, "mezzanine": 1}),
        ("mixed_use", {"above_ground": 2}),
        ("parking", {"above_ground": 1}),
    ):
        contract = _resolve(building_type=building_type, levels=levels)

        assert contract["vertical_elements"]
        for element in contract["vertical_elements"]:
            assert sorted(element.keys()) == sorted(ELEMENT_KEYS)
            assert element["type"] in ELEMENT_TYPES
            assert element["role"]
            assert element["domain"]
            assert isinstance(element["protected_zone"], bool)


def test_geometry_status_is_always_pending():
    for building_type, levels in (
        ("villa", {"above_ground": 3}),
        ("office", {"above_ground": 2, "mezzanine": 1}),
        ("mixed_use", {"above_ground": 2}),
        ("parking", {"above_ground": 1}),
    ):
        contract = _resolve(building_type=building_type, levels=levels)

        for element in contract["vertical_elements"]:
            assert element["geometry_status"]["state"] == GEOMETRY_STATE_PENDING
            assert element["geometry_status"]["reason"]


def test_connects_are_adjacent_floor_pairs():
    contract = _resolve(
        building_type="villa", levels={"above_ground": 2, "basement": 1}
    )

    stair = elements_of_type(contract, "stair")[0]

    assert stair["floors"] == ["basement", "ground_floor", "upper_floor"]
    assert stair["connects"] == [
        ["basement", "ground_floor"],
        ["ground_floor", "upper_floor"],
    ]


# ---------------------------------------------------------------------------
# domain resolution
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "building_type,domain",
    [
        ("villa", DOMAIN_RESIDENTIAL),
        ("apartment", DOMAIN_RESIDENTIAL),
        ("residential", DOMAIN_RESIDENTIAL),
        ("office", DOMAIN_COMMERCIAL),
        ("shop", DOMAIN_COMMERCIAL),
        ("storage", DOMAIN_COMMERCIAL),
        ("mixed_use", DOMAIN_MIXED_USE),
        ("parking", DOMAIN_SITE),
    ],
)
def test_building_domain_resolution(building_type, domain):
    assert resolve_building_domain(building_type) == domain


@pytest.mark.parametrize("bad", ["", "   ", None, 3, True, [], {}])
def test_invalid_building_type_is_rejected(bad):
    with pytest.raises(ValueError, match="building_type"):
        _resolve(building_type=bad)


# ---------------------------------------------------------------------------
# residential stairs
# ---------------------------------------------------------------------------

def test_residential_stairs_are_emitted():
    contract = _resolve(building_type="villa", levels={"above_ground": 2})

    stairs = elements_of_type(contract, "stair")

    assert len(stairs) == 1
    assert stairs[0]["role"] == ROLE_PRIMARY
    assert stairs[0]["domain"] == DOMAIN_RESIDENTIAL
    assert stairs[0]["protected_zone"] is True


def test_single_storey_residential_has_no_vertical_element():
    contract = _resolve(building_type="villa", levels={"above_ground": 1})

    assert contract["vertical_elements"] == []
    assert contract["served_floors"] == ["ground_floor"]


def test_basement_adds_a_vertical_transition():
    contract = _resolve(
        building_type="villa", levels={"above_ground": 1, "basement": 1}
    )

    assert "basement" in contract["served_floors"]
    assert elements_of_type(contract, "stair")


# ---------------------------------------------------------------------------
# elevator requirement
# ---------------------------------------------------------------------------

def test_elevator_is_optional_for_two_storey_residential():
    contract = _resolve(building_type="villa", levels={"above_ground": 2})

    elevators = elements_of_type(contract, "elevator")

    assert len(elevators) == 1
    assert elevators[0]["role"] == ROLE_OPTIONAL
    assert elevators[0]["protected_zone"] is False


def test_elevator_is_required_for_three_storey_residential():
    contract = _resolve(building_type="villa", levels={"above_ground": 3})

    elevators = elements_of_type(contract, "elevator")

    assert len(elevators) == 1
    assert elevators[0]["role"] == ROLE_REQUIRED
    assert elevators[0]["protected_zone"] is True


def test_explicit_elevator_requirement_is_honoured():
    contract = _resolve(
        building_type="villa",
        levels={"above_ground": 2},
        requirements=["elevator"],
    )

    elevators = elements_of_type(contract, "elevator")

    assert elevators[0]["role"] == ROLE_REQUIRED
    assert "elevator_explicitly_required" in elevators[0]["reasons"]


def test_no_elevator_for_single_storey():
    contract = _resolve(building_type="villa", levels={"above_ground": 1})

    assert elements_of_type(contract, "elevator") == []


# ---------------------------------------------------------------------------
# commercial public / service circulation
# ---------------------------------------------------------------------------

def test_commercial_separates_public_and_service_circulation():
    contract = _resolve(
        building_type="office", levels={"above_ground": 2, "mezzanine": 1}
    )

    public = elements_with_role(contract, ROLE_PUBLIC)
    service = elements_with_role(contract, ROLE_SERVICE)

    assert public
    assert service
    assert all(element["domain"] == DOMAIN_COMMERCIAL for element in public)
    assert all(element["domain"] == DOMAIN_COMMERCIAL for element in service)

    # Public circulation is a protected means of egress; service is not.
    assert all(element["protected_zone"] is True for element in public)
    assert all(element["protected_zone"] is False for element in service)


def test_commercial_service_circulation_absent_without_a_second_level():
    contract = _resolve(building_type="shop", levels={"above_ground": 1})

    assert elements_with_role(contract, ROLE_SERVICE) == []


def test_commercial_public_circulation_reaches_the_mezzanine():
    contract = _resolve(
        building_type="shop", levels={"above_ground": 1, "mezzanine": 1}
    )

    stair = elements_of_type(contract, "stair")[0]

    assert stair["floors"] == ["ground_floor", "mezzanine"]
    assert ["ground_floor", "mezzanine"] in stair["connects"]


# ---------------------------------------------------------------------------
# mixed-use shared core and separation
# ---------------------------------------------------------------------------

def test_mixed_use_has_a_shared_core():
    contract = _resolve(building_type="mixed_use", levels={"above_ground": 2})

    shared = elements_with_role(contract, ROLE_SHARED_CORE)

    assert shared
    assert all(element["domain"] == DOMAIN_MIXED_USE for element in shared)
    assert all(element["protected_zone"] is True for element in shared)


def test_mixed_use_separates_commercial_and_residential_circulation():
    contract = _resolve(building_type="mixed_use", levels={"above_ground": 2})

    separation = contract["circulation_separation"]

    assert separation["shared_core"] is True
    assert separation["separation_required"] is True
    assert separation["commercial_floors"] == ["ground_floor"]
    assert separation["residential_floors"] == ["ground_floor", "upper_floor"]
    assert separation["residential_vertical_circulation_required"] is True
    # A single-level commercial domain declares no vertical element of its own.
    assert separation["commercial_vertical_circulation_required"] is False


def test_mixed_use_residential_circulation_is_its_own_element():
    contract = _resolve(building_type="mixed_use", levels={"above_ground": 2})

    residential = elements_with_role(contract, ROLE_RESIDENTIAL)

    assert len(residential) == 1
    assert residential[0]["domain"] == DOMAIN_RESIDENTIAL


def test_mixed_use_commercial_circulation_with_a_mezzanine():
    contract = _resolve(
        building_type="mixed_use", levels={"above_ground": 2, "mezzanine": 1}
    )

    separation = contract["circulation_separation"]

    assert separation["commercial_floors"] == ["ground_floor", "mezzanine"]
    assert separation["commercial_vertical_circulation_required"] is True
    assert elements_with_role(contract, ROLE_COMMERCIAL)


def test_non_mixed_use_has_no_separation_block():
    for building_type in ("villa", "office"):
        contract = _resolve(building_type=building_type, levels={"above_ground": 2})

        assert contract["circulation_separation"] is None


# ---------------------------------------------------------------------------
# parking ramp reasoning
# ---------------------------------------------------------------------------

def test_parking_building_emits_a_ramp_element():
    contract = _resolve(building_type="parking", levels={"above_ground": 1})

    ramps = elements_of_type(contract, "ramp")

    assert len(ramps) == 1
    assert ramps[0]["role"] == ROLE_VEHICLE
    assert ramps[0]["domain"] == DOMAIN_SITE
    assert ramps[0]["protected_zone"] is False
    assert ramps[0]["floors"] == ["site_level", "ground_floor"]


def test_basement_parking_ramp_connects_the_basement():
    contract = _resolve(
        building_type="villa", levels={"above_ground": 2, "basement": 1}
    )

    ramps = elements_of_type(contract, "ramp")

    assert len(ramps) == 1
    assert ramps[0]["connects"] == [["site_level", "basement"]]


def test_no_ramp_without_a_vehicle_level():
    contract = _resolve(building_type="villa", levels={"above_ground": 2})

    assert elements_of_type(contract, "ramp") == []


# ---------------------------------------------------------------------------
# vehicle_access_pending preserved
# ---------------------------------------------------------------------------

def test_vehicle_access_stays_pending():
    for building_type, levels in (
        ("parking", {"above_ground": 1}),
        ("villa", {"above_ground": 2, "basement": 1}),
        ("villa", {"above_ground": 2}),
    ):
        contract = _resolve(building_type=building_type, levels=levels)
        vehicle = contract["vehicle_access"]

        assert vehicle["status"] == VEHICLE_ACCESS_PENDING
        assert vehicle["mode"] is None
        assert vehicle["decided"] is False
        assert tuple(vehicle["candidates"]) == VEHICLE_ACCESS_CANDIDATES


def test_vehicle_access_is_never_decided_even_with_evidence():
    contract = _resolve(
        building_type="parking",
        levels={"above_ground": 1},
        vehicle_access_evidence={"preferred_mode": "car_lift", "source": "user"},
    )

    vehicle = contract["vehicle_access"]

    assert vehicle["status"] == VEHICLE_ACCESS_PENDING
    assert vehicle["mode"] is None
    assert vehicle["decided"] is False
    # Evidence is preserved as provenance only.
    assert vehicle["evidence"] == {"preferred_mode": "car_lift", "source": "user"}


def test_vehicle_access_geometry_status_is_pending():
    contract = _resolve(building_type="parking", levels={"above_ground": 1})

    geometry = contract["vehicle_access"]["geometry_status"]

    assert geometry["state"] == GEOMETRY_STATE_PENDING


def test_car_lift_is_never_emitted():
    """The ramp/car-lift choice is a placeholder, so no car_lift element is
    produced in this phase."""

    for building_type, levels in (
        ("parking", {"above_ground": 1}),
        ("villa", {"above_ground": 3, "basement": 2}),
    ):
        contract = _resolve(building_type=building_type, levels=levels)

        assert elements_of_type(contract, "car_lift") == []


# ---------------------------------------------------------------------------
# no geometry / no dimensions
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
    "building_type,levels",
    [
        ("villa", {"above_ground": 3, "basement": 1}),
        ("office", {"above_ground": 2, "mezzanine": 1}),
        ("mixed_use", {"above_ground": 2}),
        ("parking", {"above_ground": 1}),
    ],
)
def test_no_geometry_coordinates_or_dimensions(building_type, levels):
    contract = _resolve(building_type=building_type, levels=levels)
    keys = set(_walk_keys(contract))

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
        "rise",
        "run",
        "slope",
        "length",
        "area",
        "capacity",
    ):
        assert forbidden not in keys, f"{building_type} produced {forbidden}"


def test_semantics_declare_no_geometry_and_no_dimensions():
    contract = _resolve(building_type="villa", levels={"above_ground": 3})

    assert contract["semantics"] == {
        "metadata_only": True,
        "geometry_created": False,
        "coordinates_created": False,
        "dimensions_decided": False,
        "vehicle_access_mode_decided": False,
    }


# ---------------------------------------------------------------------------
# determinism / no mutation / purity
# ---------------------------------------------------------------------------

def test_resolution_is_deterministic():
    first = _resolve(building_type="mixed_use", levels={"above_ground": 2})
    second = _resolve(building_type="mixed_use", levels={"above_ground": 2})

    assert first == second
    assert first is not second


def test_inputs_are_not_mutated():
    levels = {"above_ground": 2, "basement": 1}
    requirements = ["elevator"]
    evidence = {"preferred_mode": "ramp"}
    before = copy.deepcopy((levels, requirements, evidence))

    _resolve(
        building_type="villa",
        levels=levels,
        requirements=requirements,
        vehicle_access_evidence=evidence,
    )

    assert (levels, requirements, evidence) == before


def test_returned_elements_do_not_alias_module_state():
    first = _resolve(building_type="villa", levels={"above_ground": 2})
    first["vertical_elements"][0]["role"] = "mutated"
    first["vertical_elements"][0]["floors"].append("injected")

    second = _resolve(building_type="villa", levels={"above_ground": 2})

    assert second["vertical_elements"][0]["role"] == ROLE_PRIMARY
    assert "injected" not in second["vertical_elements"][0]["floors"]


def test_module_imports_are_pure():
    import ast

    tree = ast.parse(inspect.getsource(module))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])

    assert names <= {"__future__", "typing", "core"}


# ---------------------------------------------------------------------------
# helpers and validation
# ---------------------------------------------------------------------------

def test_served_floors_are_ascending():
    assert served_floors({"above_ground": 2, "basement": 1, "mezzanine": 1}) == [
        "basement",
        "ground_floor",
        "mezzanine",
        "upper_floor",
    ]


@pytest.mark.parametrize(
    "levels,bad_key",
    [
        ({"above_ground": -1}, "above_ground"),
        ({"basement": -2}, "basement"),
        ({"above_ground": "many"}, "above_ground"),
    ],
)
def test_invalid_level_counts_are_rejected(levels, bad_key):
    with pytest.raises(ValueError, match="levels"):
        _resolve(building_type="villa", levels=levels)


@pytest.mark.parametrize("bad", ["x", 3, [1, 2]], ids=["str", "int", "list"])
def test_invalid_levels_container_is_rejected(bad):
    with pytest.raises(ValueError, match="levels must be a mapping"):
        _resolve(building_type="villa", levels=bad)


@pytest.mark.parametrize("bad", ["elevator", 3, {}], ids=["str", "int", "dict"])
def test_invalid_requirements_container_is_rejected(bad):
    with pytest.raises(ValueError, match="requirements must be a list"):
        _resolve(building_type="villa", requirements=bad)


def test_elements_of_type_rejects_unknown_types():
    contract = _resolve(building_type="villa", levels={"above_ground": 2})

    with pytest.raises(ValueError, match="element_type must be one of"):
        elements_of_type(contract, "escalator")


@pytest.mark.parametrize("bad", [None, "x", 3])
def test_elements_helpers_reject_non_mappings(bad):
    with pytest.raises(ValueError, match="contract must be a mapping"):
        elements_of_type(bad, "stair")

    with pytest.raises(ValueError, match="contract must be a mapping"):
        elements_with_role(bad, ROLE_PRIMARY)


def test_status_is_resolved():
    contract = _resolve(building_type="villa", levels={"above_ground": 2})

    assert contract["status"]["state"] == "vertical_circulation_resolved"
    assert contract["status"]["reasons"]
