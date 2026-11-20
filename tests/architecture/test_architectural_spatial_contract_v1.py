"""Focused tests for the unified Architectural Spatial Contract v1 (ARCH-SITE-04).

The contract is a NORMALISATION LAYER over the three architectural reasoning
producers. It maps any of their space records into one canonical shape:

    identity / domain / vertical / placement / semantic / relationships /
    geometry_status / metadata

It creates no geometry, assigns no coordinates, and never rewrites the
producers' APIs.
"""

import copy

import pytest

from core.architecture.reasoning.architectural_spatial_contract_v1 import (
    CONTRACT_TYPE,
    CONTRACT_VERSION,
    build_architectural_spatial_contract,
    normalize_spatial_contracts,
    resolve_spatial_domain,
    split_contracts_by_domain,
)
from core.architecture.reasoning.external_space_reasoner import (
    ExternalSpaceReasoner,
)
from core.architecture.reasoning.knowledge_space_generator import (
    KnowledgeSpaceGenerator,
)
from core.architecture.reasoning.layout_reasoner import LayoutReasoner


VILLA = {"building_type": "villa", "levels": {"above_ground": 2}}
DESIGN_CONCEPT = {"building_type": "villa"}

REQUIRED_BLOCKS = (
    "type",
    "version",
    "identity",
    "domain",
    "vertical",
    "placement",
    "semantic",
    "relationships",
    "geometry_status",
    "metadata",
    "status",
)


@pytest.fixture(scope="module")
def generator():
    return KnowledgeSpaceGenerator()


@pytest.fixture(scope="module")
def layout_reasoner():
    return LayoutReasoner()


@pytest.fixture(scope="module")
def external_reasoner():
    return ExternalSpaceReasoner()


@pytest.fixture(scope="module")
def chain(generator, layout_reasoner):
    generated = generator.generate(
        dict(VILLA, requirements=["garden", "terrace", "parking"])
    )
    layout = layout_reasoner.generate(
        generated["generated_spaces"],
        generated["relationships"],
        dict(DESIGN_CONCEPT),
        generated_site_spaces=generated["generated_site_spaces"],
    )

    return {"generated": generated, "layout": layout}


def _building_space(chain, name):
    return next(
        space
        for space in chain["generated"]["generated_spaces"]
        if space.get("name") == name
    )


def _site_space(chain, name):
    return next(
        space
        for space in chain["generated"]["generated_site_spaces"]
        if space.get("name") == name
    )


# ---------------------------------------------------------------------------
# contract shape
# ---------------------------------------------------------------------------

def test_contract_has_the_required_blocks(chain):
    contract = build_architectural_spatial_contract(_building_space(chain, "living"))

    assert sorted(contract.keys()) == sorted(REQUIRED_BLOCKS)
    assert contract["type"] == CONTRACT_TYPE
    assert contract["version"] == CONTRACT_VERSION


def test_contract_preserves_the_required_fields(chain):
    contract = build_architectural_spatial_contract(_building_space(chain, "living"))

    assert contract["identity"]["name"] == "living"
    assert contract["identity"]["canonical_name"]
    assert contract["domain"] in ("building", "site")
    assert contract["vertical"]["floor"] == "ground_floor"
    assert contract["placement"]["placement_domain"] == "building"
    assert "space_type" in contract["semantic"]
    assert "role" in contract["semantic"]
    assert "architectural_intent" in contract["semantic"]
    assert "connections" in contract["relationships"]
    assert set(contract["geometry_status"]) == {"state", "reason"}


# ---------------------------------------------------------------------------
# REQUIRED CASE 1 - living room is building domain
# ---------------------------------------------------------------------------

def test_case_1_living_is_building_domain(chain):
    contract = build_architectural_spatial_contract(_building_space(chain, "living"))

    assert contract["domain"] == "building"
    assert contract["placement"]["placement_domain"] == "building"
    assert contract["vertical"]["floor_domain"] == "building"


def test_case_1_all_rooms_are_building_domain(chain):
    contracts = normalize_spatial_contracts(chain["generated"]["generated_spaces"])

    assert contracts
    assert all(contract["domain"] == "building" for contract in contracts)
    names = {contract["identity"]["name"] for contract in contracts}
    assert {"entrance", "living", "dining", "kitchen", "terrace"} <= names


# ---------------------------------------------------------------------------
# REQUIRED CASE 2 - garden is site domain
# ---------------------------------------------------------------------------

def test_case_2_garden_is_site_domain(chain):
    contract = build_architectural_spatial_contract(_site_space(chain, "garden"))

    assert contract["domain"] == "site"
    assert contract["vertical"]["floor"] == "site_level"
    assert contract["placement"]["placement_domain"] == "site"


# ---------------------------------------------------------------------------
# REQUIRED CASE 3 - courtyard behaves like garden
# ---------------------------------------------------------------------------

def test_case_3_courtyard_matches_garden(external_reasoner):
    garden = external_reasoner.resolve(
        {"name": "garden", "floor": "site_level", "placement_domain": "site"}
    )
    courtyard = external_reasoner.resolve(
        {"name": "courtyard", "floor": "site_level", "placement_domain": "site"}
    )

    garden_contract = build_architectural_spatial_contract(garden)
    courtyard_contract = build_architectural_spatial_contract(courtyard)

    assert courtyard_contract["domain"] == "site"
    assert courtyard_contract["semantic"] == garden_contract["semantic"]
    assert courtyard_contract["geometry_status"] == garden_contract["geometry_status"]
    assert {
        key: type(value).__name__
        for key, value in courtyard_contract.items()
    } == {
        key: type(value).__name__
        for key, value in garden_contract.items()
    }


# ---------------------------------------------------------------------------
# REQUIRED CASE 4 - parking building space stays building domain
# ---------------------------------------------------------------------------

def test_case_4_parking_building_is_building_domain():
    contract = build_architectural_spatial_contract(
        {"name": "parking", "floor": "ground_floor"}
    )

    assert contract["domain"] == "building"
    assert contract["vertical"]["floor"] == "ground_floor"


def test_case_4_parking_building_type_stays_building(generator, layout_reasoner):
    generated = generator.generate({"building_type": "parking"})
    layout = layout_reasoner.generate(
        generated["generated_spaces"],
        generated["relationships"],
        dict(DESIGN_CONCEPT),
        generated_site_spaces=generated["generated_site_spaces"],
    )

    parts = split_contracts_by_domain(
        normalize_spatial_contracts(layout["space_registry"])
    )

    names = {contract["identity"]["name"] for contract in parts["building"]}
    assert "parking" in names
    assert parts["site"] == []


# ---------------------------------------------------------------------------
# REQUIRED CASE 5 - vehicle access site space keeps its vehicle semantics
# ---------------------------------------------------------------------------

def test_case_5_vehicle_site_space(external_reasoner):
    resolved = external_reasoner.resolve(
        {
            "name": "vehicle_access",
            "floor": "site_level",
            "placement_domain": "site",
            "architectural_intent": {"vehicle_access_priority": "high"},
        }
    )

    contract = build_architectural_spatial_contract(resolved)

    assert contract["domain"] == "site"
    assert contract["semantic"]["space_type"] == "vehicle_space"
    assert contract["semantic"]["architectural_intent"] == {
        "vehicle_access_priority": "high"
    }


def test_case_5_parking_site_space_keeps_vehicle_semantics(chain):
    contract = build_architectural_spatial_contract(_site_space(chain, "parking"))

    assert contract["domain"] == "site"
    assert contract["semantic"]["architectural_intent"].get(
        "vehicle_access_priority"
    ) == "high"


# ---------------------------------------------------------------------------
# site / building separation
# ---------------------------------------------------------------------------

def test_site_and_building_domains_are_separated(chain):
    contracts = normalize_spatial_contracts(
        chain["generated"]["generated_spaces"]
        + chain["generated"]["generated_site_spaces"]
    )
    parts = split_contracts_by_domain(contracts)

    building_names = {c["identity"]["name"] for c in parts["building"]}
    site_names = {c["identity"]["name"] for c in parts["site"]}

    assert "garden" in site_names
    assert "parking" in site_names
    assert building_names.isdisjoint(site_names)
    assert "terrace" in building_names


def test_no_site_space_is_classified_as_building(chain):
    parts = split_contracts_by_domain(
        normalize_spatial_contracts(chain["generated"]["generated_site_spaces"])
    )

    assert parts["building"] == []
    assert {c["identity"]["name"] for c in parts["site"]} == {
        "garden",
        "parking",
    }


def test_split_rejects_an_unknown_domain():
    with pytest.raises(ValueError, match="domain must be one of"):
        split_contracts_by_domain([{"domain": "roof"}])


# ---------------------------------------------------------------------------
# geometry readiness
# ---------------------------------------------------------------------------

def test_geometry_remains_pending(chain):
    for space in (
        _building_space(chain, "living"),
        _site_space(chain, "garden"),
    ):
        contract = build_architectural_spatial_contract(space)

        assert contract["geometry_status"]["state"] == "pending"
        assert contract["geometry_status"]["reason"]


def test_geometry_is_never_upgraded_by_the_adapter():
    """The adapter carries a declared status but never resolves one itself."""

    contract = build_architectural_spatial_contract(
        {"name": "living", "floor": "ground_floor"}
    )

    assert contract["geometry_status"]["state"] == "pending"


def test_a_declared_geometry_status_is_carried_through():
    contract = build_architectural_spatial_contract(
        {
            "name": "living",
            "floor": "ground_floor",
            "geometry_status": {"state": "resolved", "reason": "verified"},
        }
    )

    assert contract["geometry_status"] == {
        "state": "resolved",
        "reason": "verified",
    }


@pytest.mark.parametrize(
    "bad",
    [
        {"state": "unknown"},
        {"state": "pending", "reason": 3},
        "x",
        [],
    ],
    ids=["bad-state", "bad-reason", "str", "list"],
)
def test_malformed_geometry_status_is_rejected(bad):
    with pytest.raises(ValueError):
        build_architectural_spatial_contract(
            {
                "name": "living",
                "floor": "ground_floor",
                "geometry_status": bad,
            }
        )


# ---------------------------------------------------------------------------
# no coordinates / geometry created
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "space",
    [
        {"name": "living", "floor": "ground_floor"},
        {"name": "garden", "floor": "site_level", "placement_domain": "site"},
    ],
    ids=["building", "site"],
)
def test_no_coordinates_are_created(space):
    contract = build_architectural_spatial_contract(space)

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield key
                yield from walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from walk(item)

    keys = set(walk(contract))

    for forbidden in (
        "x",
        "y",
        "z",
        "coordinates",
        "polygon",
        "geometry",
        "bounds",
        "position",
        "centroid",
        "elevation",
        "footprint",
        "width",
        "depth",
    ):
        assert forbidden not in keys


def test_metadata_is_preserved_verbatim(chain):
    space = _site_space(chain, "parking")
    contract = build_architectural_spatial_contract(space)

    assert contract["metadata"]["dimensional_requirements"] == (
        space["dimensional_requirements"]
    )
    assert contract["metadata"]["zone"] == space["zone"]


# ---------------------------------------------------------------------------
# relationships
# ---------------------------------------------------------------------------

def test_connections_are_carried_for_the_space(chain):
    contract = build_architectural_spatial_contract(
        _building_space(chain, "living"),
        connections=chain["layout"]["connections"],
    )

    connections = contract["relationships"]["connections"]
    assert connections
    assert all(
        "living" in (str(c.get("from")), str(c.get("to"))) for c in connections
    )


def test_no_connections_supplied_yields_an_empty_list(chain):
    contract = build_architectural_spatial_contract(_building_space(chain, "living"))

    assert contract["relationships"]["connections"] == []


@pytest.mark.parametrize("bad", ["x", 3, {}], ids=["str", "int", "dict"])
def test_malformed_connections_are_rejected(bad):
    with pytest.raises(ValueError, match="connections must be a list"):
        build_architectural_spatial_contract(
            {"name": "living", "floor": "ground_floor"},
            connections=bad,
        )


# ---------------------------------------------------------------------------
# determinism / no mutation
# ---------------------------------------------------------------------------

def test_contract_is_deterministic(chain):
    space = _site_space(chain, "garden")

    first = build_architectural_spatial_contract(space)
    second = build_architectural_spatial_contract(space)

    assert first == second
    assert first is not second


def test_input_is_not_mutated(chain):
    for space in (
        _building_space(chain, "living"),
        _site_space(chain, "garden"),
    ):
        before = copy.deepcopy(space)

        build_architectural_spatial_contract(space)

        assert space == before


def test_chain_output_is_not_mutated(chain):
    before = copy.deepcopy(chain)

    normalize_spatial_contracts(
        chain["generated"]["generated_spaces"]
        + chain["generated"]["generated_site_spaces"],
        connections=chain["layout"]["connections"],
    )

    assert chain == before


def test_contract_does_not_alias_the_source(chain):
    space = _site_space(chain, "garden")
    contract = build_architectural_spatial_contract(space)

    contract["metadata"]["zone"] = "mutated"

    assert space["zone"] != "mutated"


def test_normalize_preserves_order(chain):
    spaces = chain["generated"]["generated_spaces"]
    contracts = normalize_spatial_contracts(spaces)

    assert [c["identity"]["name"] for c in contracts] == [
        space.get("name") for space in spaces
    ]


# ---------------------------------------------------------------------------
# domain resolution and validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "space,expected",
    [
        ({"name": "living", "floor": "ground_floor"}, "building"),
        ({"name": "bedroom", "floor": "upper_floor"}, "building"),
        ({"name": "garden", "floor": "site_level"}, "site"),
        ({"name": "garden", "placement_domain": "site"}, "site"),
        (
            {"name": "courtyard", "floor": "site_level", "placement_domain": "site"},
            "site",
        ),
        ({"name": "parking", "floor": "ground_floor"}, "building"),
    ],
    ids=[
        "ground",
        "upper",
        "site-floor",
        "site-domain",
        "both",
        "building-parking",
    ],
)
def test_domain_resolution_is_semantic(space, expected):
    assert resolve_spatial_domain(space) == expected


def test_domain_is_independent_of_name(external_reasoner):
    for name in ("garden", "courtyard", "pool", "driveway", "anything_new"):
        resolved = external_reasoner.resolve(
            {"name": name, "floor": "site_level", "placement_domain": "site"}
        )
        contract = build_architectural_spatial_contract(resolved)

        assert contract["domain"] == "site"


def test_conflicting_placement_domain_is_rejected():
    with pytest.raises(ValueError, match="site and building semantics conflict"):
        build_architectural_spatial_contract(
            {"name": "living", "floor": "ground_floor", "placement_domain": "site"}
        )


def test_canonical_name_fallback_is_recorded():
    contract = build_architectural_spatial_contract(
        {"name": "living", "floor": "ground_floor"}
    )

    assert contract["identity"]["canonical_name"] == "living"
    assert "canonical_name_not_supplied_fell_back_to_name" in (
        contract["status"]["reasons"]
    )


@pytest.mark.parametrize(
    "bad",
    [None, "x", 3, [], object()],
    ids=["none", "str", "int", "list", "object"],
)
def test_non_mapping_space_is_rejected(bad):
    with pytest.raises(ValueError, match="space must be a mapping"):
        build_architectural_spatial_contract(bad)


def test_empty_space_is_rejected():
    with pytest.raises(ValueError, match="space must not be empty"):
        build_architectural_spatial_contract({})


@pytest.mark.parametrize("bad", ["", "   ", None, 3, True])
def test_malformed_name_is_rejected(bad):
    with pytest.raises(ValueError, match="name"):
        build_architectural_spatial_contract(
            {"name": bad, "floor": "ground_floor"}
        )


def test_api_is_keyword_only_for_connections():
    import inspect

    signature = inspect.signature(build_architectural_spatial_contract)

    assert signature.parameters["connections"].kind is (
        inspect.Parameter.KEYWORD_ONLY
    )
    assert signature.parameters["connections"].default is None


# ---------------------------------------------------------------------------
# existing LayoutReasoner behaviour preserved
# ---------------------------------------------------------------------------

def test_layout_reasoner_output_is_unchanged_by_normalisation(chain):
    """Normalising must not modify the layout it reads from."""

    layout_before = copy.deepcopy(chain["layout"])

    normalize_spatial_contracts(
        chain["layout"]["space_registry"],
        connections=chain["layout"]["connections"],
    )
    normalize_spatial_contracts(
        chain["layout"]["external_spaces"],
        connections=chain["layout"]["connections"],
    )

    assert chain["layout"] == layout_before


def test_layout_reasoner_still_separates_rooms_and_site(chain):
    layout = chain["layout"]

    registry_names = {space.get("name") for space in layout["space_registry"]}
    external_names = {space.get("name") for space in layout["external_spaces"]}

    assert "living" in registry_names
    assert "terrace" in registry_names
    assert "garden" in external_names
    assert "garden" not in registry_names
    assert registry_names.isdisjoint(external_names)


def test_contract_domain_matches_layout_buckets(chain):
    layout = chain["layout"]

    building = split_contracts_by_domain(
        normalize_spatial_contracts(layout["space_registry"])
    )
    site = split_contracts_by_domain(
        normalize_spatial_contracts(layout["external_spaces"])
    )

    assert all(c["domain"] == "building" for c in building["building"])
    assert all(c["domain"] == "site" for c in site["site"])
    assert building["site"] == []
    assert site["building"] == []
