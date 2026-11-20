"""Focused tests for the site relationship handoff (ARCH-SITE-02).

KnowledgeSpaceGenerator emits two domains:

    generated_spaces       -> building domain (floor == building floor)
    generated_site_spaces  -> site domain     (floor == "site_level")

LayoutReasoner consumes the building domain. This phase adds an OPTIONAL
``generated_site_spaces`` handoff so relationship endpoints that reference a
site space resolve to the SITE domain using authoritative site metadata -
data-driven on the authoritative program floor, never on a name list.

Site spaces must NOT become rooms, must NOT be placed in the floor layout, and
no site geometry may be created.
"""

import copy

import pytest

from core.architecture.reasoning.knowledge_space_generator import (
    KnowledgeSpaceGenerator,
)
from core.architecture.reasoning.layout_reasoner import LayoutReasoner


VILLA = {"building_type": "villa", "levels": {"above_ground": 2}}
DESIGN_CONCEPT = {"building_type": "villa"}


@pytest.fixture(scope="module")
def generator():
    return KnowledgeSpaceGenerator()


@pytest.fixture(scope="module")
def reasoner():
    return LayoutReasoner()


def _generate(generator, **intent):
    return generator.generate(dict(intent))


def _layout(reasoner, generated, *, with_site=True):
    if with_site:
        return reasoner.generate(
            generated["generated_spaces"],
            generated["relationships"],
            dict(DESIGN_CONCEPT),
            generated_site_spaces=generated["generated_site_spaces"],
        )

    return reasoner.generate(
        generated["generated_spaces"],
        generated["relationships"],
        dict(DESIGN_CONCEPT),
    )


def _external(layout, name):
    for space in layout["external_spaces"]:
        if space.get("name") == name:
            return space

    return None


def _villa_with_garden(generator):
    return _generate(
        generator, **VILLA, requirements=["garden", "terrace"]
    )


# ---------------------------------------------------------------------------
# CASE 1 - garden exists only in generated_site_spaces
# ---------------------------------------------------------------------------

def test_case_1_garden_exists_only_in_site_domain(generator):
    generated = _villa_with_garden(generator)

    site_names = [s["name"] for s in generated["generated_site_spaces"]]
    building_names = [s["name"] for s in generated["generated_spaces"]]

    assert site_names == ["garden"]
    assert "garden" not in building_names
    assert "terrace" in building_names


def test_case_1_site_space_carries_site_floor_and_domain(generator):
    generated = _villa_with_garden(generator)

    garden = generated["generated_site_spaces"][0]
    assert garden["floor"] == "site_level"
    assert garden["placement_domain"] == "site"


# ---------------------------------------------------------------------------
# CASE 2 - living -> garden resolves to the site domain
# ---------------------------------------------------------------------------

def test_case_2_relationship_exists(generator):
    generated = _villa_with_garden(generator)

    assert {
        "from": "living",
        "to": "garden",
        "type": "visual_connection",
    } in generated["relationships"]


def test_case_2_relationship_target_resolves_to_site_domain(generator, reasoner):
    generated = _villa_with_garden(generator)
    layout = _layout(reasoner, generated)

    garden = _external(layout, "garden")
    assert garden is not None
    assert garden["floor"] == "site_level"
    assert garden["placement_domain"] == "site"
    assert garden["zone"] == "external"
    assert garden["semantic_role"] == "architectural_external"


def test_case_2_site_metadata_is_preserved(generator, reasoner):
    generated = _villa_with_garden(generator)
    layout = _layout(reasoner, generated)

    garden = _external(layout, "garden")
    source = generated["generated_site_spaces"][0]

    assert garden["dimensional_requirements"] == (
        source["dimensional_requirements"]
    )
    assert garden["architectural_intent"] == source["architectural_intent"]
    assert garden["protected_zone"] == source["protected_zone"]


def test_case_2_connection_is_retained(generator, reasoner):
    generated = _villa_with_garden(generator)
    layout = _layout(reasoner, generated)

    garden_connections = [
        connection
        for connection in layout["connections"]
        if "garden" in (str(connection.get("from")), str(connection.get("to")))
    ]
    assert garden_connections
    assert garden_connections[0]["from"] == "living"


# ---------------------------------------------------------------------------
# CASE 3 - garden is not inserted into generated_spaces / the room layout
# ---------------------------------------------------------------------------

def test_case_3_garden_is_not_a_room(generator, reasoner):
    generated = _villa_with_garden(generator)
    layout = _layout(reasoner, generated)

    registry_names = [space.get("name") for space in layout["space_registry"]]
    assert "garden" not in registry_names


def test_case_3_garden_has_no_floor_layout_placement(generator, reasoner):
    generated = _villa_with_garden(generator)
    layout = _layout(reasoner, generated)

    assert "garden" not in str(layout["floor_distribution"])
    assert "garden" not in str(layout["zones"])


def test_case_3_garden_receives_no_spatial_coordinates(generator, reasoner):
    """A site space may carry a COORDINATE-FREE semantic placeholder in
    ``spatial_layout`` - that is pre-existing behaviour, deferred pending
    parcel geometry. It must never receive real coordinates or a floor.
    """

    generated = _villa_with_garden(generator)
    layout = _layout(reasoner, generated)

    entries = [
        entry
        for entry in layout["spatial_layout"]
        if entry.get("name") == "garden"
    ]

    for entry in entries:
        assert entry.get("floor") is None
        for key in ("x", "y", "width", "depth"):
            assert entry.get(key) is None
        assert entry.get("coordinate_mode") == "parcel_pending"
        assert entry.get("edge_decision_status") == "unresolved"


def test_case_3_spatial_layout_gets_only_a_coordinate_free_site_node(
    generator, reasoner
):
    """ARCH-SITE-03 removed the name-based external fallback.

    The handoff is now the ONLY way a site node reaches the layout, so it does
    introduce a site entry in spatial_layout - but that entry is coordinate
    free and explicitly deferred pending parcel geometry. No placement is made.
    """

    generated = _villa_with_garden(generator)

    with_site = _layout(reasoner, generated, with_site=True)
    without_site = _layout(reasoner, generated, with_site=False)

    def garden_entries(layout):
        return [
            entry
            for entry in layout["spatial_layout"]
            if entry.get("name") == "garden"
        ]

    # Without site metadata there is no site node at all.
    assert garden_entries(without_site) == []

    # With the handoff there is exactly one, and it carries no coordinates.
    entries = garden_entries(with_site)
    assert len(entries) == 1
    for key in ("x", "y", "width", "depth"):
        assert entries[0].get(key) is None
    assert entries[0].get("coordinate_mode") == "parcel_pending"


def test_case_3_no_site_geometry_or_coordinates_are_created(
    generator, reasoner
):
    generated = _villa_with_garden(generator)
    layout = _layout(reasoner, generated)

    garden = _external(layout, "garden")

    for key in (
        "coordinates",
        "polygon",
        "geometry",
        "bounds",
        "position",
        "centroid",
        "elevation",
        "z",
    ):
        assert key not in garden


# ---------------------------------------------------------------------------
# CASE 4 - existing room layout behaviour is unchanged
# ---------------------------------------------------------------------------

def test_case_4_layout_keys_unchanged(generator, reasoner):
    generated = _villa_with_garden(generator)
    layout = _layout(reasoner, generated)

    assert sorted(layout.keys()) == [
        "connections",
        "external_spaces",
        "floor_distribution",
        "layout_strategy",
        "space_registry",
        "spatial_layout",
        "zones",
    ]


def test_case_4_building_layout_is_identical_with_and_without_handoff(
    generator, reasoner
):
    generated = _villa_with_garden(generator)

    with_site = _layout(reasoner, generated, with_site=True)
    without_site = _layout(reasoner, generated, with_site=False)

    assert with_site["space_registry"] == without_site["space_registry"]
    assert with_site["floor_distribution"] == without_site["floor_distribution"]
    assert with_site["zones"] == without_site["zones"]
    assert with_site["connections"] == without_site["connections"]


def test_case_4_terrace_remains_a_building_space(generator, reasoner):
    generated = _villa_with_garden(generator)
    layout = _layout(reasoner, generated)

    registry_names = [space.get("name") for space in layout["space_registry"]]
    assert "terrace" in registry_names
    # A building space is never turned into an external site node.
    assert _external(layout, "terrace") is None


def test_case_4_required_building_spaces_are_present(generator, reasoner):
    generated = _villa_with_garden(generator)
    layout = _layout(reasoner, generated)

    registry_names = {space.get("name") for space in layout["space_registry"]}
    for required in (
        "entrance",
        "living",
        "dining",
        "kitchen",
        "guest_wc",
        "stairs",
        "corridor",
        "master_bedroom",
        "bedroom",
        "bathroom",
    ):
        assert required in registry_names


# ---------------------------------------------------------------------------
# backward compatibility
# ---------------------------------------------------------------------------

def test_backward_compatible_without_the_new_argument(generator, reasoner):
    """Existing callers pass three positional arguments and still work.

    ARCH-SITE-03 removed the legacy name-based external fallback, so a caller
    that passes NO site metadata no longer receives name-inferred site nodes.
    The API contract is unchanged; the site DOMAIN now requires site metadata,
    which is the point of the site contract.
    """

    generated = _villa_with_garden(generator)

    layout = reasoner.generate(
        generated["generated_spaces"],
        generated["relationships"],
        dict(DESIGN_CONCEPT),
    )

    assert isinstance(layout["external_spaces"], list)
    assert layout["external_spaces"] == []
    assert _external(layout, "garden") is None

    # Building-domain output is unaffected.
    registry_names = [space.get("name") for space in layout["space_registry"]]
    assert "terrace" in registry_names
    assert "garden" not in registry_names


def test_signature_keeps_existing_parameters_positional(reasoner):
    import inspect

    parameters = list(
        inspect.signature(LayoutReasoner.generate).parameters
    )

    assert parameters[:5] == [
        "self",
        "spaces",
        "relationships",
        "design_concept",
        "space_program",
    ]
    assert "generated_site_spaces" in parameters

    signature = inspect.signature(LayoutReasoner.generate)
    assert signature.parameters["generated_site_spaces"].default is None


def test_site_handoff_is_optional_and_tolerates_malformed_input(
    generator, reasoner
):
    generated = _villa_with_garden(generator)

    for bad in (None, [], "x", 3, {}, [None, "x", 3]):
        layout = reasoner.generate(
            generated["generated_spaces"],
            generated["relationships"],
            dict(DESIGN_CONCEPT),
            generated_site_spaces=bad,
        )
        assert isinstance(layout["external_spaces"], list)


# ---------------------------------------------------------------------------
# the handoff is data-driven, not name-driven
# ---------------------------------------------------------------------------

_NON_WHITELISTED_PROGRAM = {
    "required_spaces": [
        {"name": "living", "zone": "public", "floor": "ground_floor"},
    ],
    "optional_spaces": [
        {
            "name": "courtyard",
            "zone": "external",
            "floor": "site_level",
            "dimensional_requirements": {"minimum_area": 30},
        }
    ],
    "relationships": [
        {"from": "living", "to": "courtyard", "type": "visual_connection"}
    ],
}


def test_non_whitelisted_site_space_is_handed_off(generator, reasoner, monkeypatch):
    """A site space whose NAME is not in the legacy external-candidate list
    must still resolve to the site domain."""

    monkeypatch.setattr(
        generator.program_knowledge,
        "get_program",
        lambda building_type, functions=None: copy.deepcopy(
            _NON_WHITELISTED_PROGRAM
        ),
    )

    generated = generator.generate(
        {"building_type": "villa", "requirements": ["courtyard"]}
    )
    assert [s["name"] for s in generated["generated_site_spaces"]] == [
        "courtyard"
    ]

    layout = _layout(reasoner, generated)
    courtyard = _external(layout, "courtyard")

    assert courtyard is not None
    assert courtyard["floor"] == "site_level"
    assert courtyard["placement_domain"] == "site"
    assert courtyard["dimensional_requirements"] == {"minimum_area": 30}


def test_non_whitelisted_site_space_is_dropped_without_the_handoff(
    generator, reasoner, monkeypatch
):
    """Documents the gap this phase closes."""

    monkeypatch.setattr(
        generator.program_knowledge,
        "get_program",
        lambda building_type, functions=None: copy.deepcopy(
            _NON_WHITELISTED_PROGRAM
        ),
    )

    generated = generator.generate(
        {"building_type": "villa", "requirements": ["courtyard"]}
    )
    layout = _layout(reasoner, generated, with_site=False)

    assert _external(layout, "courtyard") is None


# ---------------------------------------------------------------------------
# determinism / no mutation
# ---------------------------------------------------------------------------

def test_handoff_is_deterministic(generator, reasoner):
    generated = _villa_with_garden(generator)

    first = _layout(reasoner, generated)
    second = _layout(reasoner, generated)

    assert first["external_spaces"] == second["external_spaces"]


def test_handoff_does_not_mutate_its_inputs(generator, reasoner):
    generated = _villa_with_garden(generator)
    site_before = copy.deepcopy(generated["generated_site_spaces"])
    spaces_before = copy.deepcopy(generated["generated_spaces"])

    _layout(reasoner, generated)

    assert generated["generated_site_spaces"] == site_before
    assert generated["generated_spaces"] == spaces_before
