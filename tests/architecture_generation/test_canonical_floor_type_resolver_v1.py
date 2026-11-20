from copy import deepcopy

from core.architecture.floor_type_resolver_v1 import CanonicalFloorTypeResolverV1
from core.architecture.vertical_building_section_engine import VerticalBuildingSectionEngine


def test_canonical_level_roles_are_non_residential_where_required():
    resolver = CanonicalFloorTypeResolverV1()
    assert resolver.resolve("basement", {})["type"] == "basement"
    assert resolver.resolve("residential_floor_1", {})["type"] == "residential"
    assert resolver.resolve("residential_floor_2", {})["type"] == "residential"
    assert resolver.resolve("roof", {})["type"] == "roof"
    assert resolver.resolve("stairhouse", {})["type"] == "roof_superstructure"


def test_ground_and_unknown_levels_fail_closed_without_program_evidence():
    resolver = CanonicalFloorTypeResolverV1()
    assert resolver.resolve("ground", {})["type"] is None
    assert resolver.resolve("arbitrary", {})["type"] is None


def test_program_roles_resolve_f_aliases_and_explicit_type_is_preserved_without_mutation():
    program = {"spaces": [{"name": "L", "floor": "F1", "role": "living"}],
               "vertical_organization": {"F1": ["L"]}}
    frozen = deepcopy(program)
    resolver = CanonicalFloorTypeResolverV1()
    assert resolver.resolve("F1", program)["type"] == "residential"
    marker = {"canonical": "custom"}
    assert resolver.resolve("F1", program, marker)["type"] == marker
    assert program == frozen


def test_vertical_engine_does_not_apply_general_residential_fallback():
    program = {"vertical_organization": {"ground": [], "roof": [], "stairhouse": []},
               "floor_heights": {"ground": 3, "roof": 1, "stairhouse": 2}}
    levels = {x["name"]: x for x in VerticalBuildingSectionEngine().generate(program)["levels"]}
    assert levels["ground"]["type"] is None
    assert levels["roof"]["type"] == "roof"
    assert levels["stairhouse"]["type"] == "roof_superstructure"
