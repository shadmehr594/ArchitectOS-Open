# ==========================================================
# ArchitectOS — IRANIAN ARCHITECTURAL KNOWLEDGE V1
#
# Measured defects this file pins (V4.1 §6 D1):
#
#   `iranian_brick` declared the material `brick_red`, which is NOT
#   a material id (the id is `red_brick`) — it never resolved.
#
#   `islamic_architecture` declared `brick`, `tile`, `ceramic` —
#   none of them ids — so 3 of its 4 materials never resolved.
#
#   Neither Iranian style carried the elements the user asked for:
#   orsi windows, brick latticework/screening, geometric brickwork,
#   tilework.
#
# The Iranian styles must also stay DISTINCT from each other.
#
# NO GPU. NO COMFYUI. NO NETWORK.
# ==========================================================

import json
import os

import pytest

from core.architecture.knowledge.resolved_facade_knowledge import (
    SharedFacadeKnowledgeResolverV1,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE = os.path.join(ROOT, "core", "architecture", "knowledge")


@pytest.fixture(scope="module")
def materials():
    return json.load(
        open(os.path.join(KNOWLEDGE, "material_ontology.json"), encoding="utf-8")
    )["materials"]


@pytest.fixture(scope="module")
def resolver():
    return SharedFacadeKnowledgeResolverV1()


@pytest.mark.parametrize(
    "style",
    ["iranian_brick", "iranian_traditional", "islamic_architecture"],
)
def test_every_declared_material_resolves(resolver, materials, style):
    resolved = resolver.resolve({"style": style})

    primary = resolved["materials"]["primary"]

    assert primary != ["UNKNOWN"]

    for name in primary:
        assert name in materials, (style, name)

    assert resolved["materials"]["resolved"], style


def test_iranian_brick_does_not_reference_a_non_existent_material(resolver):
    resolved = resolver.resolve({"style": "iranian_brick"})

    assert "brick_red" not in resolved["materials"]["primary"]
    assert "red_brick" in resolved["materials"]["primary"]


def test_glazed_tile_exists_and_is_tagged(materials):
    assert "glazed_tile" in materials
    assert "islamic_architecture" in materials["glazed_tile"]["styles"]
    assert "iranian_traditional" in materials["glazed_tile"]["styles"]


@pytest.mark.parametrize(
    "style,expected",
    [
        ("iranian_brick", ("brick lattice screens", "geometric brick relief")),
        ("iranian_traditional", ("orsi_window", "tile_work")),
    ],
)
def test_the_requested_iranian_elements_are_present(resolver, style, expected):
    resolved = resolver.resolve({"style": style})

    elements = resolved["facade_language"]["elements"]

    for item in expected:
        assert item in elements, (style, item)


def test_the_iranian_styles_stay_distinct(resolver):
    brick = set(resolver.resolve({"style": "iranian_brick"})["facade_language"]["elements"])
    traditional = set(
        resolver.resolve({"style": "iranian_traditional"})["facade_language"]["elements"]
    )

    assert brick != traditional
    assert "orsi_window" not in brick
    assert "brick lattice screens" not in traditional


def test_iranian_brick_reaches_the_render_prompt(resolver):
    from core.render.prompt_builder import PromptBuilder

    resolved = resolver.resolve({"style": "iranian_brick"})

    prompt = str(
        PromptBuilder().build(
            {"style": "iranian_brick", "resolved_facade_knowledge": resolved}
        )
    ).lower()

    assert "approved facade design" in prompt
    assert "brick lattice screens" in prompt
    assert "geometric brick relief" in prompt
    assert "unknown" not in prompt
