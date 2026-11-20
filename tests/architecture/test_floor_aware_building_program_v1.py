"""Focused tests for floor-aware Building Program Knowledge (ARCH-PROGRAM-01).

The extension is ADDITIVE. It supplies the building domains and the floor-aware
semantics that ``BuildingProgramKnowledge`` lacks (apartment, shop, retail,
office, gym, storage; the six required semantic fields; mezzanine support),
while every existing building type is still served by
``BuildingProgramKnowledge`` byte-identically.
"""

import copy
import inspect

import pytest

import core.architecture.knowledge.floor_aware_building_program_v1 as program_module
from core.architecture.knowledge.building_program_knowledge import (
    BuildingProgramKnowledge,
)
from core.architecture.knowledge.floor_aware_building_program_v1 import (
    BUILDING_DOMAINS,
    COMMERCIAL,
    FLOOR_AWARE_PROGRAMS,
    MIXED_USE,
    PRIVACY_LEVELS,
    RESIDENTIAL,
    STORAGE_CATEGORIES,
    building_types_for_domain,
    floor_distribution,
    get_floor_aware_program,
    is_floor_aware_type,
    mezzanine_spaces,
    program_domain,
    site_spaces,
    spaces_on_floor,
)
from core.architecture.reasoning.knowledge_space_generator import (
    KnowledgeSpaceGenerator,
)


REQUIRED_SEMANTIC_FIELDS = (
    "space_type",
    "role",
    "floor_constraints",
    "privacy_requirements",
    "access_requirements",
    "architectural_intent",
)

EXISTING_TYPES = ("villa", "residential", "commercial", "mixed_use", "parking")


@pytest.fixture(scope="module")
def generator():
    return KnowledgeSpaceGenerator()


def _all_spaces(program):
    return list(program.get("required_spaces", [])) + list(
        program.get("optional_spaces", [])
    )


def _building_floors(result):
    return {space["floor"] for space in result["generated_spaces"]}


# ---------------------------------------------------------------------------
# building domains
# ---------------------------------------------------------------------------

def test_building_domains_cover_the_required_types():
    assert set(BUILDING_DOMAINS) == {RESIDENTIAL, COMMERCIAL, MIXED_USE}
    assert building_types_for_domain(RESIDENTIAL) == ("villa", "apartment")
    assert building_types_for_domain(COMMERCIAL) == (
        "shop",
        "retail",
        "office",
        "gym",
        "storage",
    )
    assert building_types_for_domain(MIXED_USE) == ("mixed_use",)


@pytest.mark.parametrize(
    "building_type,domain",
    [
        ("villa", RESIDENTIAL),
        ("apartment", RESIDENTIAL),
        ("shop", COMMERCIAL),
        ("retail", COMMERCIAL),
        ("office", COMMERCIAL),
        ("gym", COMMERCIAL),
        ("storage", COMMERCIAL),
        ("mixed_use", MIXED_USE),
    ],
)
def test_program_domain_resolution(building_type, domain):
    assert program_domain(building_type) == domain


def test_unknown_building_type_has_no_domain():
    assert program_domain("unknown_thing") is None
    assert program_domain(None) is None


@pytest.mark.parametrize(
    "building_type",
    ["apartment", "shop", "retail", "office", "gym", "storage"],
)
def test_extension_owns_the_new_building_types(building_type):
    assert is_floor_aware_type(building_type) is True


@pytest.mark.parametrize("building_type", ["villa", "commercial", "mixed_use"])
def test_extension_does_not_own_existing_types(building_type):
    assert is_floor_aware_type(building_type) is False


# ---------------------------------------------------------------------------
# residential floor distribution
# ---------------------------------------------------------------------------

def test_residential_floor_distribution(generator):
    result = generator.generate(
        {"building_type": "apartment", "levels": {"above_ground": 2}}
    )

    floors = _building_floors(result)
    assert floors == {"ground_floor", "upper_floor"}

    ground = {
        space["name"]
        for space in result["generated_spaces"]
        if space["floor"] == "ground_floor"
    }
    upper = {
        space["name"]
        for space in result["generated_spaces"]
        if space["floor"] == "upper_floor"
    }

    assert {"entrance", "living", "kitchen", "corridor"} <= ground
    assert {"bedroom", "bathroom", "corridor"} <= upper


def test_apartment_upper_floor_is_filtered_without_two_levels(generator):
    result = generator.generate(
        {"building_type": "apartment", "levels": {"above_ground": 1}}
    )

    assert _building_floors(result) == {"ground_floor"}


def test_residential_domain_includes_villa_and_apartment():
    for building_type in building_types_for_domain(RESIDENTIAL):
        program = get_floor_aware_program(building_type)
        assert program

    assert floor_distribution(get_floor_aware_program("apartment")) == {
        "ground_floor": ["entrance", "living", "kitchen", "corridor", "storage"],
        "upper_floor": ["bedroom", "bathroom", "corridor", "balcony"],
    }


# ---------------------------------------------------------------------------
# commercial floor distribution
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "building_type", ["shop", "retail", "office", "gym", "storage"]
)
def test_commercial_programs_are_ground_anchored(building_type):
    distribution = floor_distribution(get_floor_aware_program(building_type))

    assert "ground_floor" in distribution
    assert distribution["ground_floor"]


def test_commercial_floor_distribution_end_to_end(generator):
    result = generator.generate(
        {"building_type": "office", "levels": {"above_ground": 2}}
    )

    floors = _building_floors(result)
    assert floors == {"ground_floor", "upper_floor"}

    names = {space["name"] for space in result["generated_spaces"]}
    assert {"reception", "open_office", "meeting_room", "office_upper"} <= names


def test_commercial_mezzanine_requires_a_mezzanine_level(generator):
    without = generator.generate(
        {"building_type": "shop", "levels": {"above_ground": 1}}
    )
    with_mezzanine = generator.generate(
        {"building_type": "shop", "levels": {"above_ground": 1, "mezzanine": 1}}
    )

    assert "mezzanine" not in _building_floors(without)
    assert "mezzanine" in _building_floors(with_mezzanine)


# ---------------------------------------------------------------------------
# mixed-use separation
# ---------------------------------------------------------------------------

def test_mixed_use_separates_commercial_and_residential(generator):
    result = generator.generate(
        {"building_type": "mixed_use", "levels": {"above_ground": 2}}
    )

    ground = {
        space["name"]
        for space in result["generated_spaces"]
        if space["floor"] == "ground_floor"
    }
    upper = {
        space["name"]
        for space in result["generated_spaces"]
        if space["floor"] == "upper_floor"
    }

    # Commercial programme on the ground floor.
    assert "retail" in ground
    # Residential programme above.
    assert {"living", "kitchen", "bedroom", "bathroom"} <= upper
    assert ground.isdisjoint(upper - {"corridor"})


def test_mixed_use_keeps_both_domains_populated(generator):
    result = generator.generate(
        {"building_type": "mixed_use", "levels": {"above_ground": 2}}
    )

    assert _building_floors(result) == {"ground_floor", "upper_floor"}
    assert len(result["generated_spaces"]) >= 9


# ---------------------------------------------------------------------------
# mezzanine semantic support
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "building_type", ["shop", "retail", "office", "gym", "storage"]
)
def test_mezzanine_spaces_exist_in_commercial_programs(building_type):
    mezzanines = mezzanine_spaces(get_floor_aware_program(building_type))

    assert mezzanines
    for space in mezzanines:
        assert space["floor"] == "mezzanine"
        assert space["floor_constraints"]["role"] == "commercial_mezzanine"
        assert space["floor_constraints"]["constraints"]["partial_floor"] is True


def test_mezzanine_was_absent_before_this_extension():
    """Documents the gap: mezzanine did not exist in the base program layer."""

    source = inspect.getsource(BuildingProgramKnowledge)

    assert "mezzanine" not in source.lower()


def test_mezzanine_is_a_recognised_floor_in_the_extension():
    assert "mezzanine" in program_module.FLOOR_CONSTRAINTS
    assert (
        program_module.FLOOR_CONSTRAINTS["mezzanine"]["height_source"]
        == "floor_aware_building_program"
    )


# ---------------------------------------------------------------------------
# storage categories
# ---------------------------------------------------------------------------

def test_storage_categories_are_declared():
    assert STORAGE_CATEGORIES == (
        "general_storage",
        "cold_storage",
        "archive_storage",
        "equipment_storage",
    )


def test_storage_building_type_has_a_categorised_storage_space():
    program = get_floor_aware_program("storage")

    storage_spaces = [
        space
        for space in _all_spaces(program)
        if space.get("storage_category")
    ]

    assert storage_spaces
    for space in storage_spaces:
        assert space["storage_category"] in STORAGE_CATEGORIES
        assert space["space_type"] == "storage_space"


def test_storage_categories_are_used_across_commercial_types():
    used = {
        space.get("storage_category")
        for building_type in ("shop", "office", "gym", "storage")
        for space in _all_spaces(get_floor_aware_program(building_type))
        if space.get("storage_category")
    }

    assert used <= set(STORAGE_CATEGORIES)
    assert used == {"general_storage", "archive_storage", "equipment_storage"}


def test_storage_loading_bay_declares_vehicle_access():
    program = get_floor_aware_program("storage")

    loading = next(
        space for space in _all_spaces(program) if space["name"] == "loading_bay"
    )

    assert loading["access_requirements"]["vehicle_access"] is True


# ---------------------------------------------------------------------------
# required semantic fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "building_type",
    ["apartment", "shop", "retail", "office", "gym", "storage"],
)
def test_every_new_space_carries_the_required_semantic_fields(building_type):
    program = get_floor_aware_program(building_type)

    for space in _all_spaces(program):
        for field in REQUIRED_SEMANTIC_FIELDS:
            assert field in space, f"{building_type}/{space['name']} missing {field}"


@pytest.mark.parametrize(
    "building_type",
    ["apartment", "shop", "office"],
)
def test_semantic_fields_are_well_formed(building_type):
    program = get_floor_aware_program(building_type)

    for space in _all_spaces(program):
        assert isinstance(space["space_type"], str) and space["space_type"]
        assert isinstance(space["role"], str) and space["role"]
        assert isinstance(space["floor_constraints"], dict)
        assert space["floor_constraints"]["role"]
        assert isinstance(space["privacy_requirements"], dict)
        assert space["privacy_requirements"]["level"] in PRIVACY_LEVELS
        assert isinstance(space["access_requirements"], dict)
        assert isinstance(space["architectural_intent"], dict)


def test_semantics_survive_into_generated_spaces(generator):
    result = generator.generate(
        {"building_type": "shop", "levels": {"above_ground": 1}}
    )

    retail = next(
        space for space in result["generated_spaces"] if space["name"] == "retail_floor"
    )

    assert retail["space_type"] == "retail_space"
    assert retail["role"] == "primary"
    assert retail["floor_constraints"]["role"] == "public_access_level"
    assert retail["privacy_requirements"]["level"] == "public"
    assert retail["architectural_intent"]["daylight_priority"] == "high"


# ---------------------------------------------------------------------------
# additive / backward compatible
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("building_type", EXISTING_TYPES)
def test_existing_types_delegate_unchanged(building_type):
    base = BuildingProgramKnowledge().get_program(building_type)
    extended = get_floor_aware_program(building_type)

    assert extended == base


def test_unknown_building_type_still_returns_empty():
    assert get_floor_aware_program("unknown_thing") == {}


@pytest.mark.parametrize("building_type", EXISTING_TYPES)
def test_existing_generator_output_is_preserved(generator, building_type):
    result = generator.generate(
        {"building_type": building_type, "levels": {"above_ground": 2}}
    )

    assert result["generated_spaces"]
    assert isinstance(result["generated_site_spaces"], list)


def test_villa_site_contract_still_works(generator):
    result = generator.generate(
        {
            "building_type": "villa",
            "requirements": ["garden", "parking"],
            "levels": {"above_ground": 2},
        }
    )

    assert [
        (space["name"], space["floor"], space["placement_domain"])
        for space in result["generated_site_spaces"]
    ] == [("garden", "site_level", "site"), ("parking", "site_level", "site")]

    building_names = {space["name"] for space in result["generated_spaces"]}
    assert "garden" not in building_names
    assert "parking" not in building_names


def test_extension_program_carries_no_site_spaces():
    """The new domains are building domains; site spaces stay site_level."""

    for building_type in FLOOR_AWARE_PROGRAMS:
        program = get_floor_aware_program(building_type)
        assert site_spaces(program) == []


def test_program_table_is_not_mutated_by_consumers():
    before = copy.deepcopy(FLOOR_AWARE_PROGRAMS)

    program = get_floor_aware_program("shop")
    program["required_spaces"][0]["name"] = "mutated"

    assert FLOOR_AWARE_PROGRAMS == before


def test_get_program_returns_a_copy():
    first = get_floor_aware_program("office")
    second = get_floor_aware_program("office")

    assert first == second
    assert first is not second


# ---------------------------------------------------------------------------
# no geometry
# ---------------------------------------------------------------------------

def test_programs_create_no_geometry_or_coordinates():
    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield key
                yield from walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from walk(item)

    for building_type in FLOOR_AWARE_PROGRAMS:
        keys = set(walk(get_floor_aware_program(building_type)))

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
        ):
            assert forbidden not in keys, f"{building_type} carries {forbidden}"


def test_generated_spaces_carry_no_geometry_for_new_domains(generator):
    result = generator.generate(
        {"building_type": "apartment", "levels": {"above_ground": 2}}
    )

    for space in result["generated_spaces"]:
        for forbidden in (
            "coordinates",
            "polygon",
            "geometry",
            "bounds",
            "position",
            "centroid",
        ):
            assert forbidden not in space


def test_module_imports_are_pure():
    import ast

    tree = ast.parse(inspect.getsource(program_module))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])

    # "core" is this project's own package (the module delegates to
    # BuildingProgramKnowledge); no third-party or geometry import is allowed.
    assert names <= {"__future__", "typing", "copy", "core"}


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "building_type", ["apartment", "shop", "retail", "office", "gym", "storage"]
)
def test_program_is_deterministic(building_type):
    assert get_floor_aware_program(building_type) == get_floor_aware_program(
        building_type
    )


def test_generation_is_deterministic(generator):
    intent = {"building_type": "apartment", "levels": {"above_ground": 2}}

    first = generator.generate(dict(intent))
    second = generator.generate(dict(intent))

    assert first["generated_spaces"] == second["generated_spaces"]
    assert first["generated_site_spaces"] == second["generated_site_spaces"]


def test_floor_distribution_helper_is_deterministic():
    program = get_floor_aware_program("office")

    assert floor_distribution(program) == floor_distribution(program)


def test_spaces_on_floor_helper():
    program = get_floor_aware_program("apartment")

    assert [space["name"] for space in spaces_on_floor(program, "mezzanine")] == []
    assert [space["name"] for space in spaces_on_floor(program, "upper_floor")] == [
        "bedroom",
        "bathroom",
        "corridor",
        "balcony",
    ]


@pytest.mark.parametrize("bad", [None, "x", 3, []])
def test_floor_distribution_rejects_non_mappings(bad):
    with pytest.raises(ValueError, match="program must be a mapping"):
        floor_distribution(bad)
