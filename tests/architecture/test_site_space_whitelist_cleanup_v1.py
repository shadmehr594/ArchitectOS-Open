"""Cleanup guard for ARCH-SITE-01.1.

ARCH-SITE-01 introduced the site-space contract. An accidental NAME-BASED
whitelist (`site_level_allowed = {"garden", "parking", "yard", "ramp",
"vehicle_access"}`) had been added to the building-floor filter in the same
file. ARCH-SITE-01.1 removed it.

Site-space classification is DATA-DRIVEN on the authoritative program floor:

    program_space.get("floor") == "site_level"

...and never on the space name. These tests exist so the whitelist cannot
silently creep back in.
"""

import inspect
import re

import pytest

import core.architecture.reasoning.knowledge_space_generator as generator_module
from core.architecture.reasoning.knowledge_space_generator import (
    KnowledgeSpaceGenerator,
)


VILLA = {"building_type": "villa", "levels": {"above_ground": 2}}

# The exact names the removed whitelist listed.
REMOVED_WHITELIST_NAMES = ("garden", "parking", "yard", "ramp", "vehicle_access")


@pytest.fixture(scope="module")
def generator():
    return KnowledgeSpaceGenerator()


def _code_source(module):
    """Module source with comments and string literals removed."""

    import io
    import tokenize

    pieces = []
    for token in tokenize.generate_tokens(
        io.StringIO(inspect.getsource(module)).readline
    ):
        if token.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        pieces.append(token.string)

    return " ".join(pieces)


# ---------------------------------------------------------------------------
# the whitelist is gone
# ---------------------------------------------------------------------------

def test_site_level_allowed_identifier_is_absent():
    source = inspect.getsource(generator_module)

    assert "site_level_allowed" not in source


def test_no_name_based_site_classification_remains():
    """No executable code may compare a space NAME against a site-name set."""

    code = _code_source(generator_module)

    for name in REMOVED_WHITELIST_NAMES:
        assert f'"{name}"' not in code
        assert f"'{name}'" not in code

    # No membership test against any name collection for site purposes.
    assert not re.search(r"get\(\s*[\"']name[\"']\s*\)\s*in\s+", code)


def test_no_site_name_collection_literal_remains():
    code = _code_source(generator_module)

    # A literal set/list/tuple of the removed site names must not exist.
    for name in REMOVED_WHITELIST_NAMES:
        assert name not in code


# ---------------------------------------------------------------------------
# classification is floor-only
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", REMOVED_WHITELIST_NAMES + ("unknown_site_thing",))
def test_classification_depends_only_on_the_floor(generator, name):
    """The same name is a site space or not purely because of its floor."""

    assert generator._is_site_level_space(
        {"name": name, "floor": "site_level"}
    ) is True
    assert generator._is_site_level_space(
        {"name": name, "floor": "ground_floor"}
    ) is False
    assert generator._is_site_level_space({"name": name}) is False


def test_site_level_is_not_a_building_floor(generator):
    result = generator.generate(dict(VILLA, requirements=["parking"]))

    assert "site_level" not in result["floor_authority"]["allowed_floors"]


# ---------------------------------------------------------------------------
# the two required behaviours
# ---------------------------------------------------------------------------

def test_villa_parking_requirement_resolves_as_a_site_space(generator):
    result = generator.generate(dict(VILLA, requirements=["parking"]))

    site = [
        (space["name"], space["floor"])
        for space in result["generated_site_spaces"]
    ]
    assert site == [("parking", "site_level")]
    assert all(
        space["placement_domain"] == "site"
        for space in result["generated_site_spaces"]
    )
    assert "parking" not in [
        space["name"] for space in result["generated_spaces"]
    ]


def test_parking_building_type_keeps_its_building_floor(generator):
    result = generator.generate({"building_type": "parking"})

    assert ("parking", "ground_floor") in [
        (space["name"], space["floor"])
        for space in result["generated_spaces"]
    ]
    assert result["generated_site_spaces"] == []


def test_site_contract_still_holds_after_cleanup(generator):
    """Regression guard: the cleanup must not weaken the site contract."""

    result = generator.generate(
        dict(VILLA, requirements=["terrace", "parking", "garden"])
    )

    building = {space["name"] for space in result["generated_spaces"]}
    site = {space["name"] for space in result["generated_site_spaces"]}

    assert site == {"parking", "garden"}
    assert building.isdisjoint(site)
    assert "terrace" in building
