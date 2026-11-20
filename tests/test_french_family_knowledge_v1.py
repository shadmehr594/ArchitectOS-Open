# ==========================================================
# ArchitectOS — FRENCH FAMILY + STYLE-SPECIFIC EXPRESSION V1
#
# Regression tests for two measured defects:
#
#   1. french_classical / beaux_arts / second_empire /
#      french_provincial had NO canonical style record and NO
#      facade-language record, so the resolver returned
#      `style_semantics` unresolved and `elements: [UNKNOWN]`.
#
#   2. neoclassical declared its facade vocabulary in the style
#      ontology, but the resolver's element projection ignored it,
#      so every neoclassical render prompt carried the literal
#      sentinel "UNKNOWN" instead of columns / pilasters / cornices.
#
# The tests also pin the DISTINCTION the user asked for:
#   - characteristic elements belong to the style and are emitted;
#   - optional elements (cupola, sculpture, dormer) are emitted only
#     when the request names them;
#   - legitimate ornament is never suppressed for a rich style.
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

FRENCH = ("french_classical", "beaux_arts", "second_empire", "french_provincial")


def _load(name):
    return json.load(open(os.path.join(KNOWLEDGE, name), encoding="utf-8"))


@pytest.fixture(scope="module")
def styles():
    return _load("architectural_style_ontology.json")["styles"]


@pytest.fixture(scope="module")
def facade_languages():
    return _load("facade_language_ontology.json")["facade_languages"]


@pytest.fixture(scope="module")
def materials():
    return _load("material_ontology.json")["materials"]


@pytest.fixture(scope="module")
def resolver():
    return SharedFacadeKnowledgeResolverV1()


def _resolve(resolver, style, **extra):
    return resolver.resolve(dict({"style": style}, **extra))


# ==========================================================
# 1 — THE FOUR FAMILIES EXIST AND STAY DISTINCT
# ==========================================================

@pytest.mark.parametrize("style", FRENCH)
def test_style_record_exists(styles, style):
    assert style in styles, style
    record = styles[style]
    for key in ("synonyms", "character", "form_language", "facade_languages", "materials"):
        assert record.get(key), (style, key)


@pytest.mark.parametrize("style", FRENCH)
def test_facade_language_record_exists(facade_languages, style):
    assert style in facade_languages, style
    record = facade_languages[style]
    for key in ("composition", "elements", "materials"):
        assert record.get(key), (style, key)


def test_the_families_are_not_copies_of_each_other(styles):
    signatures = {}

    for style in FRENCH:
        record = styles[style]
        signatures[style] = (
            tuple(record["character"]),
            tuple(record["form_language"]),
        )

    assert len(set(signatures.values())) == len(FRENCH), signatures


def test_second_empire_owns_the_mansard_and_classicism_does_not(facade_languages):
    """Mansard is CHARACTERISTIC of Second Empire, optional elsewhere."""

    second = [item.lower() for item in facade_languages["second_empire"]["elements"]]
    classical = [item.lower() for item in facade_languages["french_classical"]["elements"]]

    assert any("mansard" in item for item in second)
    assert not any("mansard" in item for item in classical)


def test_beaux_arts_keeps_its_rich_ornament(facade_languages):
    """A rich style must not be stripped of legitimate ornament."""

    elements = [item.lower() for item in facade_languages["beaux_arts"]["elements"]]

    assert any("sculptural" in item for item in elements)
    assert any("capital" in item for item in elements)


# ==========================================================
# 2 — THE RESOLVER REACHES EVERY FAMILY
# ==========================================================

@pytest.mark.parametrize("style", FRENCH)
def test_every_family_resolves_without_a_style_gap(resolver, style):
    resolved = _resolve(resolver, style)

    assert resolved["canonical_style"] == style
    assert resolved["style_family"] == "french"
    assert "style_semantics" not in resolved["unresolved"]
    assert resolved["facade_language"]["name"] == style
    assert resolved["facade_language"]["elements"] != ["UNKNOWN"]
    assert resolved["composition"] != ["UNKNOWN"]


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("french", "french_classical"),
        ("french_classic", "french_classical"),
        ("beaux-arts", "beaux_arts"),
        ("haussmann", "second_empire"),
        ("napoleon_iii", "second_empire"),
        ("provence", "french_provincial"),
        ("provencal", "french_provincial"),
        ("نمای فرانسوی", "french_classical"),
    ],
)
def test_explicit_synonyms_map_to_one_family_member(resolver, alias, expected):
    resolved = _resolve(resolver, alias)

    assert resolved["canonical_style"] == expected


def test_an_unknown_style_still_fails_closed(resolver):
    resolved = _resolve(resolver, "brutalist_gothic")

    assert resolved["canonical_style"] == "brutalist_gothic"
    assert "style_semantics" in resolved["unresolved"]


# ==========================================================
# 3 — OPTIONAL VS CHARACTERISTIC
# ==========================================================

@pytest.mark.parametrize("style", ("french_classical", "beaux_arts", "french_provincial"))
def test_optional_elements_are_not_injected_automatically(resolver, style):
    resolved = _resolve(resolver, style)

    text = json.dumps(resolved["facade_language"], ensure_ascii=False).lower()

    assert "cupola" not in text
    assert "figural sculpture" not in text


def test_an_optional_element_is_emitted_when_the_request_names_it(resolver):
    resolved = _resolve(resolver, "french_classical", facade_details=["cupola"])

    text = json.dumps(resolved["facade_language"], ensure_ascii=False).lower()

    assert "cupola" in text


def test_mansard_is_emitted_for_second_empire_without_being_asked(resolver):
    resolved = _resolve(resolver, "second_empire")

    text = json.dumps(resolved["facade_language"], ensure_ascii=False).lower()

    assert "mansard" in text


def test_optional_element_does_not_leak_across_families(resolver):
    resolved = _resolve(resolver, "french_provincial")

    text = json.dumps(resolved["facade_language"], ensure_ascii=False).lower()

    assert "mansard" not in text


# ==========================================================
# 4 — NEOCLASSICAL'S DECLARED VOCABULARY NOW RESOLVES
# ==========================================================

def test_neoclassical_no_longer_reports_unknown_elements(resolver, styles):
    resolved = _resolve(resolver, "neoclassical")

    elements = resolved["facade_language"]["elements"]

    assert elements != ["UNKNOWN"]
    assert set(elements) == set(styles["neoclassical"]["facade_languages"])


def test_a_style_with_a_facade_record_is_not_widened_by_the_fallback(resolver, styles):
    """classic has a facade-language record; the fallback must not touch it."""

    resolved = _resolve(resolver, "classic")
    facade_elements = resolved["facade_language"]["elements"]

    assert facade_elements != ["UNKNOWN"]
    assert set(facade_elements) != set(styles["classic"]["facade_languages"])


# ==========================================================
# 5 — MATERIALS
# ==========================================================

@pytest.mark.parametrize("style", FRENCH)
def test_french_styles_resolve_real_material_ids(resolver, materials, style):
    resolved = _resolve(resolver, style)

    primary = resolved["materials"]["primary"]

    assert primary != ["UNKNOWN"]

    for name in primary:
        assert name in materials, (style, name)


@pytest.mark.parametrize("style", FRENCH)
def test_each_french_style_is_tagged_on_its_materials(materials, style):
    tagged = [
        name
        for name, record in materials.items()
        if style in (record.get("styles") or [])
    ]

    assert tagged, style


# ==========================================================
# 6 — THE KNOWLEDGE REACHES THE RENDER PROMPT
# ==========================================================

def test_french_elements_reach_the_built_render_prompt(resolver):
    from core.render.prompt_builder import PromptBuilder

    resolved = _resolve(resolver, "beaux_arts")

    prompt = PromptBuilder().build(
        {"style": "beaux_arts", "resolved_facade_knowledge": resolved}
    )

    lowered = str(prompt).lower()

    assert "approved facade design" in lowered
    assert "paired columns" in lowered
    assert "sculptural relief panels" in lowered


def test_the_unknown_sentinel_never_reaches_the_prompt(resolver):
    from core.render.prompt_builder import PromptBuilder

    resolved = _resolve(resolver, "neoclassical")

    prompt = str(
        PromptBuilder().build(
            {"style": "neoclassical", "resolved_facade_knowledge": resolved}
        )
    )

    assert "UNKNOWN" not in prompt
    assert "columns" in prompt.lower()
    assert "pilasters" in prompt.lower()
