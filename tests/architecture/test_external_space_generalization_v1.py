"""Focused tests for external/site space generalization (ARCH-SITE-03).

ARCH-SITE-03 removed the last name-based external-space classification:

- ``external_candidates`` in LayoutReasoner (the name FILTER) is gone;
- the name branches in ExternalSpaceReasoner (name-based ENRICHMENT) are gone.

Site-ness is now read from the space's own authoritative semantics:

    placement_domain == "site"   (preferred)
    floor            == "site_level"

...and the semantic profile is selected from the space's own architectural
intent, never from its name. garden, courtyard, pool, landscape, driveway and
outdoor_kitchen therefore all behave identically when they carry site metadata,
with no code change for a new name.
"""

import copy
import inspect
import io
import tokenize

import pytest

import core.architecture.reasoning.external_space_reasoner as external_module
from core.architecture.reasoning.external_space_reasoner import (
    ExternalSpaceReasoner,
    has_vehicle_intent,
    is_site_space,
)
from core.architecture.reasoning.knowledge_space_generator import (
    KnowledgeSpaceGenerator,
)
from core.architecture.reasoning.layout_reasoner import LayoutReasoner


VILLA = {"building_type": "villa", "levels": {"above_ground": 2}}
DESIGN_CONCEPT = {"building_type": "villa"}

SITE_PROFILE_KEYS = (
    "space_type",
    "relation_to_building",
    "privacy",
    "placement_rule",
    "preferred_neighbors",
)


@pytest.fixture(scope="module")
def reasoner():
    return ExternalSpaceReasoner()


@pytest.fixture(scope="module")
def layout_reasoner():
    return LayoutReasoner()


@pytest.fixture(scope="module")
def generator():
    return KnowledgeSpaceGenerator()


def _code_source(module):
    """Module source with comments and string literals removed."""

    pieces = []
    for token in tokenize.generate_tokens(
        io.StringIO(inspect.getsource(module)).readline
    ):
        if token.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        pieces.append(token.string)

    return " ".join(pieces)


def _profile(space):
    return {key: space.get(key) for key in SITE_PROFILE_KEYS}


def _site_space(name, **overrides):
    space = {
        "name": name,
        "floor": "site_level",
        "placement_domain": "site",
    }
    space.update(overrides)

    return space


# ---------------------------------------------------------------------------
# the name-based mechanisms are gone
# ---------------------------------------------------------------------------

def test_external_candidates_whitelist_is_gone():
    import core.architecture.reasoning.layout_reasoner as layout_module

    assert "external_candidates" not in inspect.getsource(layout_module)


def test_external_reasoner_does_not_read_the_space_name():
    """The module no longer consults ``name`` at all - classification and
    profile selection are purely semantic."""

    assert '"name"' not in _code_source(external_module)


def test_external_reasoner_has_no_name_comparisons():
    code = _code_source(external_module)

    assert "name ==" not in code
    assert "name in" not in code


# ---------------------------------------------------------------------------
# TEST 1 - semantic site detection independent of name
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "space",
    [
        {"floor": "site_level"},
        {"placement_domain": "site"},
        {"floor": "site_level", "placement_domain": "site"},
    ],
    ids=["floor-only", "domain-only", "both"],
)
def test_site_detection_is_semantic(space):
    assert is_site_space(space) is True


@pytest.mark.parametrize(
    "space",
    [
        {"floor": "ground_floor"},
        {"floor": "upper_floor"},
        {},
        None,
        "garden",
    ],
    ids=["ground-floor", "upper-floor", "empty", "none", "string"],
)
def test_non_site_spaces_are_not_site(space):
    assert is_site_space(space) is False


@pytest.mark.parametrize(
    "name",
    [
        "garden",
        "courtyard",
        "pool",
        "landscape",
        "driveway",
        "outdoor_kitchen",
        "yard",
        "parking",
        "terrace",
        "something_never_seen_before",
    ],
)
def test_semantic_site_profile_is_independent_of_name(reasoner, name):
    """Every site space receives the same generic profile, whatever its name."""

    resolved = reasoner.resolve(_site_space(name))

    assert resolved["space_type"] == "landscape"
    assert resolved["relation_to_building"] == "visual_extension"
    assert resolved["privacy"] == "external"
    assert resolved["placement_rule"] == "open_edge"
    assert resolved["floor"] == "site_level"
    assert resolved["placement_domain"] == "site"


def test_unknown_name_matches_garden_exactly(reasoner):
    garden = reasoner.resolve(_site_space("garden"))
    unknown = reasoner.resolve(_site_space("totally_new_site_space"))

    assert _profile(unknown) == _profile(garden)


# ---------------------------------------------------------------------------
# TEST 2 - courtyard works without a whitelist entry
# ---------------------------------------------------------------------------

def test_courtyard_is_recognised(reasoner):
    resolved = reasoner.resolve(_site_space("courtyard"))

    assert resolved["space_type"] == "landscape"
    assert resolved["relation_to_building"] == "visual_extension"
    assert resolved["placement_domain"] == "site"


def test_courtyard_matches_garden(reasoner):
    assert _profile(reasoner.resolve(_site_space("courtyard"))) == _profile(
        reasoner.resolve(_site_space("garden"))
    )


# ---------------------------------------------------------------------------
# TEST 3 - pool works without a whitelist entry
# ---------------------------------------------------------------------------

def test_pool_is_recognised(reasoner):
    resolved = reasoner.resolve(_site_space("pool"))

    assert resolved["space_type"] == "landscape"
    assert resolved["placement_domain"] == "site"


def test_pool_matches_garden(reasoner):
    assert _profile(reasoner.resolve(_site_space("pool"))) == _profile(
        reasoner.resolve(_site_space("garden"))
    )


# ---------------------------------------------------------------------------
# TEST 4 - parking building space stays in the building domain
# ---------------------------------------------------------------------------

def test_parking_building_space_is_not_a_site_space(reasoner):
    building_parking = {"name": "parking", "floor": "ground_floor"}

    assert is_site_space(building_parking) is False

    resolved = reasoner.resolve(dict(building_parking))

    # Returned unchanged: no site profile is applied.
    assert resolved == building_parking
    assert resolved.get("space_type") is None
    assert resolved.get("placement_domain") is None


def test_parking_building_type_stays_in_the_building_domain(
    generator, layout_reasoner
):
    generated = generator.generate({"building_type": "parking"})

    layout = layout_reasoner.generate(
        generated["generated_spaces"],
        generated["relationships"],
        dict(DESIGN_CONCEPT),
        generated_site_spaces=generated["generated_site_spaces"],
    )

    registry = [
        (space.get("name"), space.get("floor"))
        for space in layout["space_registry"]
    ]
    assert ("parking", "ground_floor") in registry
    assert layout["external_spaces"] == []


def test_terrace_building_space_is_not_reclassified(reasoner):
    building_terrace = {"name": "terrace", "floor": "ground_floor"}

    assert is_site_space(building_terrace) is False
    assert reasoner.resolve(dict(building_terrace)) == building_terrace


# ---------------------------------------------------------------------------
# TEST 5 - existing garden behaviour unchanged
# ---------------------------------------------------------------------------

def test_garden_profile_is_unchanged(reasoner):
    resolved = reasoner.resolve(_site_space("garden"))

    assert resolved["space_type"] == "landscape"
    assert resolved["relation_to_building"] == "visual_extension"
    assert resolved["privacy"] == "external"
    assert resolved["placement_rule"] == "open_edge"
    assert resolved["preferred_neighbors"] == ["living", "dining", "terrace"]


def test_garden_through_the_full_flow(generator, layout_reasoner):
    generated = generator.generate(
        dict(VILLA, requirements=["garden", "terrace"])
    )

    layout = layout_reasoner.generate(
        generated["generated_spaces"],
        generated["relationships"],
        dict(DESIGN_CONCEPT),
        generated_site_spaces=generated["generated_site_spaces"],
    )

    garden = next(
        space
        for space in layout["external_spaces"]
        if space.get("name") == "garden"
    )
    assert garden["floor"] == "site_level"
    assert garden["placement_domain"] == "site"
    assert garden["space_type"] == "landscape"
    assert garden["relation_to_building"] == "visual_extension"


# ---------------------------------------------------------------------------
# semantic vehicle profile (no name list)
# ---------------------------------------------------------------------------

def test_vehicle_intent_selects_the_vehicle_profile(reasoner):
    parking = _site_space(
        "parking",
        architectural_intent={
            "vehicle_access_priority": "high",
            "placement_priority": "vehicle_access",
        },
    )

    resolved = reasoner.resolve(parking)

    assert resolved["space_type"] == "vehicle_space"
    assert resolved["relation_to_building"] == "service_access"
    assert resolved["placement_rule"] == "road_edge"


def test_vehicle_intent_is_semantic_not_named():
    assert has_vehicle_intent(
        {"name": "any_name", "architectural_intent": {"vehicle_access_priority": "high"}}
    ) is True
    assert has_vehicle_intent(
        {"name": "parking", "architectural_intent": {}}
    ) is False
    assert has_vehicle_intent({"name": "parking"}) is False


def test_a_non_vehicle_site_space_named_parking_is_landscape(reasoner):
    """Profile comes from intent, not from the name."""

    resolved = reasoner.resolve(_site_space("parking"))

    assert resolved["space_type"] == "landscape"


# ---------------------------------------------------------------------------
# TEST 6 - no coordinates / geometry
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name", ["garden", "courtyard", "pool", "driveway"]
)
def test_no_coordinates_or_geometry_are_created(reasoner, name):
    resolved = reasoner.resolve(_site_space(name))

    for key in (
        "x",
        "y",
        "z",
        "width",
        "depth",
        "coordinates",
        "polygon",
        "geometry",
        "bounds",
        "position",
        "centroid",
        "elevation",
        "footprint",
    ):
        assert key not in resolved


def test_full_flow_creates_no_site_coordinates(generator, layout_reasoner):
    generated = generator.generate(
        dict(VILLA, requirements=["garden", "terrace"])
    )
    layout = layout_reasoner.generate(
        generated["generated_spaces"],
        generated["relationships"],
        dict(DESIGN_CONCEPT),
        generated_site_spaces=generated["generated_site_spaces"],
    )

    for entry in layout["spatial_layout"]:
        if entry.get("name") != "garden":
            continue
        for key in ("x", "y", "width", "depth"):
            assert entry.get(key) is None
        assert entry.get("coordinate_mode") == "parcel_pending"


# ---------------------------------------------------------------------------
# TEST 7 - no mutation of input data
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["garden", "courtyard", "pool"])
def test_input_is_not_mutated(reasoner, name):
    space = _site_space(name)
    before = copy.deepcopy(space)

    reasoner.resolve(space)

    assert space == before


def test_non_site_input_is_not_mutated(reasoner):
    space = {"name": "parking", "floor": "ground_floor"}
    before = copy.deepcopy(space)

    reasoner.resolve(space)

    assert space == before


def test_returned_mapping_is_a_new_dict(reasoner):
    space = _site_space("garden")

    resolved = reasoner.resolve(space)

    assert resolved is not space


def test_full_flow_does_not_mutate_generator_output(generator, layout_reasoner):
    generated = generator.generate(
        dict(VILLA, requirements=["garden", "terrace"])
    )
    before = copy.deepcopy(generated)

    layout_reasoner.generate(
        generated["generated_spaces"],
        generated["relationships"],
        dict(DESIGN_CONCEPT),
        generated_site_spaces=generated["generated_site_spaces"],
    )

    assert generated == before


# ---------------------------------------------------------------------------
# TEST 8 - deterministic output
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["garden", "courtyard", "pool"])
def test_resolution_is_deterministic(reasoner, name):
    first = reasoner.resolve(_site_space(name))
    second = reasoner.resolve(_site_space(name))

    assert first == second
    assert first is not second


def test_full_flow_is_deterministic(generator, layout_reasoner):
    generated = generator.generate(
        dict(VILLA, requirements=["garden", "terrace"])
    )

    def run():
        return layout_reasoner.generate(
            generated["generated_spaces"],
            generated["relationships"],
            dict(DESIGN_CONCEPT),
            generated_site_spaces=generated["generated_site_spaces"],
        )

    assert run()["external_spaces"] == run()["external_spaces"]


# ---------------------------------------------------------------------------
# integration - a new site name flows through the whole chain unchanged
# ---------------------------------------------------------------------------

_SITE_PROGRAM = {
    "required_spaces": [
        {"name": "living", "zone": "public", "floor": "ground_floor"},
    ],
    "optional_spaces": [
        {
            "name": "courtyard",
            "zone": "external",
            "floor": "site_level",
            "dimensional_requirements": {"minimum_area": 30},
        },
        {
            "name": "pool",
            "zone": "external",
            "floor": "site_level",
            "dimensional_requirements": {"minimum_area": 18},
        },
    ],
    "relationships": [
        {"from": "living", "to": "courtyard", "type": "visual_connection"},
        {"from": "living", "to": "pool", "type": "visual_connection"},
    ],
}


def test_new_site_names_flow_through_without_code_changes(
    generator, layout_reasoner, monkeypatch
):
    monkeypatch.setattr(
        generator.program_knowledge,
        "get_program",
        lambda building_type, functions=None: copy.deepcopy(_SITE_PROGRAM),
    )

    generated = generator.generate(
        {"building_type": "villa", "requirements": ["courtyard", "pool"]}
    )
    assert sorted(
        space["name"] for space in generated["generated_site_spaces"]
    ) == ["courtyard", "pool"]

    layout = layout_reasoner.generate(
        generated["generated_spaces"],
        generated["relationships"],
        dict(DESIGN_CONCEPT),
        generated_site_spaces=generated["generated_site_spaces"],
    )

    resolved = {space["name"]: space for space in layout["external_spaces"]}
    assert set(resolved) == {"courtyard", "pool"}

    for name in ("courtyard", "pool"):
        assert resolved[name]["space_type"] == "landscape"
        assert resolved[name]["floor"] == "site_level"
        assert resolved[name]["placement_domain"] == "site"
        assert resolved[name]["dimensional_requirements"] == {
            "minimum_area": 30 if name == "courtyard" else 18
        }
