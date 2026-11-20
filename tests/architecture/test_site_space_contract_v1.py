"""Focused tests for the Site Space Contract v1 (ARCH-SITE-01).

A site-level program space (authoritative ``floor == "site_level"``) must be
resolved into ``result["generated_site_spaces"]`` and must never appear in
``result["generated_spaces"]``, which continues to represent building / floor
architectural spaces.

``site_level`` is deliberately NOT a building floor: it is never added to
``allowed_floors`` and a site space is never relocated onto ``ground_floor``.
"""

import copy

import pytest

from core.architecture.reasoning.knowledge_space_generator import (
    KnowledgeSpaceGenerator,
)


VILLA = {"building_type": "villa", "levels": {"above_ground": 2}}


@pytest.fixture(scope="module")
def generator():
    return KnowledgeSpaceGenerator()


def _generate(generator, **intent):
    return generator.generate(dict(intent))


def _building(result):
    return [(space.get("name"), space.get("floor")) for space in result["generated_spaces"]]


def _site(result):
    return [(space.get("name"), space.get("floor")) for space in result["generated_site_spaces"]]


def _site_by_name(result, name):
    for space in result["generated_site_spaces"]:
        if space.get("name") == name:
            return space

    return None


# ---------------------------------------------------------------------------
# CASE A
# ---------------------------------------------------------------------------

def test_case_a_terrace_building_parking_site(generator):
    result = _generate(
        generator, **VILLA, requirements=["terrace", "parking"]
    )

    assert ("terrace", "ground_floor") in _building(result)
    assert "parking" not in [name for name, _ in _building(result)]

    parking = _site_by_name(result, "parking")
    assert parking is not None
    assert parking["floor"] == "site_level"
    assert parking["placement_domain"] == "site"


def test_case_a_terrace_keeps_its_building_floor(generator):
    result = _generate(
        generator, **VILLA, requirements=["terrace", "parking"]
    )

    terrace = next(
        space
        for space in result["generated_spaces"]
        if space["name"] == "terrace"
    )
    assert terrace["floor"] == "ground_floor"


# ---------------------------------------------------------------------------
# CASE B
# ---------------------------------------------------------------------------

def test_case_b_parking_only_in_site_spaces(generator):
    result = _generate(generator, **VILLA, requirements=["parking"])

    assert "parking" not in [name for name, _ in _building(result)]
    assert _site(result) == [("parking", "site_level")]


# ---------------------------------------------------------------------------
# CASE C
# ---------------------------------------------------------------------------

def test_case_c_garden_only_in_site_spaces(generator):
    result = _generate(generator, **VILLA, requirements=["garden"])

    assert "garden" not in [name for name, _ in _building(result)]
    garden = _site_by_name(result, "garden")
    assert garden is not None
    assert garden["floor"] == "site_level"


def test_case_c_parking_is_not_pulled_in_by_garden(generator):
    result = _generate(generator, **VILLA, requirements=["garden"])

    assert _site_by_name(result, "parking") is None


# ---------------------------------------------------------------------------
# CASE D
# ---------------------------------------------------------------------------

def test_case_d_terrace_only_leaves_site_spaces_empty(generator):
    result = _generate(generator, **VILLA, requirements=["terrace"])

    assert ("terrace", "ground_floor") in _building(result)
    assert result["generated_site_spaces"] == []


# ---------------------------------------------------------------------------
# CASE E
# ---------------------------------------------------------------------------

def test_case_e_no_requirements_emits_no_site_spaces(generator):
    result = _generate(generator, **VILLA, requirements=[])

    assert result["generated_site_spaces"] == []
    names = [name for name, _ in _building(result)]
    assert "parking" not in names
    assert "garden" not in names


def test_case_e_site_spaces_are_not_emitted_unrequested(generator):
    result = _generate(generator, **VILLA)

    assert result["generated_site_spaces"] == []


# ---------------------------------------------------------------------------
# CASE F
# ---------------------------------------------------------------------------

def test_case_f_string_form_parking_stays_site_level(generator):
    result = _generate(generator, **VILLA, spaces=["parking"])

    assert _site(result) == [("parking", "site_level")]
    assert "parking" not in [name for name, _ in _building(result)]


def test_case_f_no_ground_floor_relocation(generator):
    result = _generate(generator, **VILLA, spaces=["parking"])

    parking = _site_by_name(result, "parking")
    assert parking["floor"] == "site_level"
    assert parking["floor"] != "ground_floor"
    assert "floor_assignment_source" not in parking


# ---------------------------------------------------------------------------
# CASE G
# ---------------------------------------------------------------------------

def test_case_g_dict_form_reuses_authoritative_typology(generator):
    result = _generate(generator, **VILLA, spaces=[{"name": "parking"}])

    parking = _site_by_name(result, "parking")
    assert parking is not None
    assert parking["floor"] == "site_level"
    assert parking["placement_domain"] == "site"
    assert parking["dimensional_requirements"] == {
        "minimum_area": 12,
        "preferred_area": 15,
        "minimum_width": 2.5,
        "minimum_depth": 5,
    }
    assert "parking" not in [name for name, _ in _building(result)]


def test_case_g_dict_form_preserves_architectural_intent(generator):
    result = _generate(generator, **VILLA, spaces=[{"name": "parking"}])

    parking = _site_by_name(result, "parking")
    assert parking["architectural_intent"]["vehicle_access_priority"] == "high"
    assert parking["protected_zone"] is True


# ---------------------------------------------------------------------------
# CASE H
# ---------------------------------------------------------------------------

def test_case_h_both_channels_produce_exactly_one_site_space(generator):
    result = _generate(
        generator,
        **VILLA,
        requirements=["parking"],
        spaces=["parking"],
    )

    assert _site(result) == [("parking", "site_level")]
    assert len(result["generated_site_spaces"]) == 1


# ---------------------------------------------------------------------------
# CASE I
# ---------------------------------------------------------------------------

def test_case_i_parking_building_type_stays_a_building_space(generator):
    result = _generate(generator, building_type="parking")

    assert ("parking", "ground_floor") in _building(result)
    assert "parking" not in [name for name, _ in _site(result)]
    assert result["generated_site_spaces"] == []


# ---------------------------------------------------------------------------
# CASE J
# ---------------------------------------------------------------------------

def test_case_j_mixed_use_parking_stays_a_building_space(generator):
    result = _generate(
        generator,
        building_type="mixed_use",
        requirements=["parking"],
    )

    assert ("parking", "ground_floor") in _building(result)
    assert "parking" not in [name for name, _ in _site(result)]


# ---------------------------------------------------------------------------
# contract invariants
# ---------------------------------------------------------------------------

def test_generated_site_spaces_key_is_always_present(generator):
    for intent in (
        dict(VILLA, requirements=["parking"]),
        dict(VILLA, requirements=[]),
        {"building_type": "parking"},
    ):
        result = generator.generate(dict(intent))
        assert "generated_site_spaces" in result
        assert isinstance(result["generated_site_spaces"], list)


@pytest.mark.parametrize(
    "intent",
    [
        dict(VILLA, requirements=["parking"]),
        dict(VILLA, requirements=["garden"]),
        dict(VILLA, spaces=["parking"]),
        dict(VILLA, spaces=[{"name": "parking"}]),
        dict(VILLA, requirements=["terrace", "parking"]),
    ],
    ids=["req", "garden", "str", "dict", "mixed"],
)
def test_site_space_invariants(generator, intent):
    result = generator.generate(dict(intent))

    for space in result["generated_site_spaces"]:
        assert space["floor"] == "site_level"
        assert space["placement_domain"] == "site"
        assert space["name"]
        assert space["canonical_name"]


def test_site_spaces_never_appear_in_generated_spaces(generator):
    result = _generate(
        generator, **VILLA, requirements=["terrace", "parking", "garden"]
    )

    building_names = {name for name, _ in _building(result)}
    site_names = {name for name, _ in _site(result)}

    assert site_names == {"parking", "garden"}
    assert building_names.isdisjoint(site_names)


def test_site_level_is_not_added_to_allowed_floors(generator):
    result = _generate(generator, **VILLA, requirements=["parking"])

    authority = result["floor_authority"]
    assert "site_level" not in authority["allowed_floors"]
    assert authority["allowed_floors"] == ["ground_floor", "upper_floor"]


def test_building_spaces_are_not_injected_with_new_metadata(generator):
    """The smallest compatible change: building spaces are untouched."""

    result = _generate(generator, **VILLA, requirements=["terrace"])

    for space in result["generated_spaces"]:
        assert "placement_domain" not in space


def test_site_records_are_plain_dicts_and_deterministic(generator):
    first = _generate(generator, **VILLA, requirements=["parking"])
    second = _generate(generator, **VILLA, requirements=["parking"])

    assert first["generated_site_spaces"] == second["generated_site_spaces"]
    assert first["generated_site_spaces"] is not second["generated_site_spaces"]


def test_generate_does_not_mutate_the_intent(generator):
    intent = dict(VILLA, requirements=["parking"])
    before = copy.deepcopy(intent)

    generator.generate(intent)

    assert intent == before


# ---------------------------------------------------------------------------
# classification is floor-driven, not name-driven
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "space,expected",
    [
        ({"name": "parking", "floor": "site_level"}, True),
        ({"name": "yard", "floor": "site_level"}, True),
        ({"name": "future_site_thing", "floor": "site_level"}, True),
        ({"name": "parking", "floor": "ground_floor"}, False),
        ({"name": "parking"}, False),
        ({"name": "garden", "floor": "upper_floor"}, False),
        ("parking", False),
        (None, False),
    ],
    ids=[
        "site-parking",
        "site-yard",
        "site-unknown-name",
        "ground-floor-parking",
        "no-floor",
        "upper-floor-garden",
        "string",
        "none",
    ],
)
def test_site_level_classification_is_data_driven(generator, space, expected):
    assert generator._is_site_level_space(space) is expected


def test_resolve_site_template_requires_an_authoritative_floor(generator):
    result = _generate(generator, **VILLA, requirements=["parking"])
    templates = {
        "parking": {"name": "parking", "floor": "site_level"},
    }

    # no floor declared -> resolves through the name
    assert generator._resolve_site_template(
        {"name": "parking"}, templates
    ) is not None
    # explicit site floor -> resolves
    assert generator._resolve_site_template(
        {"name": "parking", "floor": "site_level"}, templates
    ) is not None
    # explicit BUILDING floor -> never a site space
    assert generator._resolve_site_template(
        {"name": "parking", "floor": "ground_floor"}, templates
    ) is None
    # unknown name -> never a site space
    assert generator._resolve_site_template(
        {"name": "living"}, templates
    ) is None
    assert result["generated_site_spaces"]


# ---------------------------------------------------------------------------
# generic handling for a future REQUIRED site-level space
# ---------------------------------------------------------------------------

_REQUIRED_SITE_PROGRAM = {
    "required_spaces": [
        {"name": "entrance", "zone": "public", "floor": "ground_floor"},
        {
            "name": "yard",
            "zone": "external",
            "floor": "site_level",
            "dimensional_requirements": {"minimum_area": 10},
        },
    ],
    "optional_spaces": [],
    "relationships": [],
}


def test_required_site_level_space_is_not_silently_lost(generator, monkeypatch):
    """Generic handling: a future REQUIRED site space is emitted without being
    requested, and does not appear among building spaces."""

    monkeypatch.setattr(
        generator.program_knowledge,
        "get_program",
        lambda building_type, functions=None: copy.deepcopy(
            _REQUIRED_SITE_PROGRAM
        ),
    )

    result = generator.generate({"building_type": "villa"})

    assert _site(result) == [("yard", "site_level")]
    assert "yard" not in [name for name, _ in _building(result)]
    assert ("entrance", "ground_floor") in _building(result)


def test_required_site_space_is_deduplicated_when_also_requested(
    generator, monkeypatch
):
    monkeypatch.setattr(
        generator.program_knowledge,
        "get_program",
        lambda building_type, functions=None: copy.deepcopy(
            _REQUIRED_SITE_PROGRAM
        ),
    )

    result = generator.generate(
        {"building_type": "villa", "requirements": ["yard"]}
    )

    assert _site(result) == [("yard", "site_level")]


# ---------------------------------------------------------------------------
# existing building-space behaviour is preserved
# ---------------------------------------------------------------------------

def test_balcony_still_resolves_as_a_building_space(generator):
    result = _generate(generator, **VILLA, requirements=["balcony"])

    assert ("balcony", "upper_floor") in _building(result)
    assert result["generated_site_spaces"] == []


def test_required_building_spaces_are_unaffected(generator):
    result = _generate(generator, **VILLA, requirements=["parking"])

    names = [name for name, _ in _building(result)]
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
        assert required in names


def test_site_contract_does_not_disturb_building_output(generator):
    """Requesting a site space must not change the building-space output."""

    without_site = _generate(generator, **VILLA, requirements=["terrace"])
    with_site = _generate(
        generator, **VILLA, requirements=["terrace", "parking"]
    )

    assert _building(without_site) == _building(with_site)


def test_site_contract_does_not_inject_relationship_endpoints(generator):
    """Relationship routing is unchanged in this phase.

    NOTE: the villa program's own relationship list already references the
    site-level space ``garden`` (living -> garden, visual_connection). That is
    pre-existing program data and is deliberately preserved here. Site-space
    relationship routing is deferred to a later phase.
    """

    without_site = _generate(generator, **VILLA, requirements=["terrace"])
    with_site = _generate(
        generator, **VILLA, requirements=["terrace", "parking"]
    )

    assert without_site["relationships"] == with_site["relationships"]


def test_preexisting_garden_relationship_is_preserved(generator):
    """Documents the observed relationship gap rather than fixing it."""

    result = _generate(generator, **VILLA, requirements=["garden"])

    endpoints = set()
    for relationship in result.get("relationships", []):
        if isinstance(relationship, dict):
            endpoints.add(str(relationship.get("from")))
            endpoints.add(str(relationship.get("to")))

    assert "garden" in endpoints
