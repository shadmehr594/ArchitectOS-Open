# -*- coding: utf-8 -*-
"""MATERIAL_NORMALIZATION_SPECIFICITY_V1 — focused CPU tests.

A material FAMILY is not a material SUBTYPE, and a material IDENTITY is not an
architectural APPLICATION. Three ontology records published an application the
source phrase never named:

    concrete -> "exposed concrete"      (a surface treatment, not the family)
    metal    -> "metal facade panels"   (a product form and a location)
    wood     -> "wood cladding"         (an application)

The same three records also carry the EXPLICIT forms ("exposed concrete",
"metal facade panels", "wood cladding") as synonyms, so before this milestone a
generic phrase and its qualified form were indistinguishable: `concrete wall`
and `exposed concrete wall` both published `exposed concrete`.

Semantic requirement, pinned here INDEPENDENTLY of the production JSON — a test
that derives its expectation from the artefact it checks cannot detect a wrong
artefact:

    generic form      -> the generic identity, no application
    explicit form     -> the qualifier the text itself provided

    concrete wall        -> concrete
    exposed concrete wall-> exposed concrete
    metal railing        -> metal
    metal facade panels  -> metal facade panels
    wooden door          -> wood
    wood cladding        -> wood cladding

Real observation -> knowledge -> report chain, and the real request path
(ArchitecturalIntent -> ArchitecturalKnowledgeResolver -> PromptBuilder ->
resolve_render_prompt -> WorkflowInjector node). SYNTHETIC inputs only.
No Ollama, no GPU, no ComfyUI, no render.
"""

from __future__ import annotations

import contextlib
import io
from functools import lru_cache

import pytest

from core.cognition.architectural_render_instruction_v1 import (
    build_constraint_block,
    build_render_instruction,
)
from core.knowledge.architectural_knowledge_resolver import (
    ArchitecturalKnowledgeResolver,
)
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)
from core.render.prompt_builder import PromptBuilder
from core.render.workflow_injector import WorkflowInjector
from core.vision.architectural_observation_v1 import build_architectural_observation
from core.vision.observed_material_knowledge_v1 import (
    resolve_observed_material_knowledge,
)
from core.vision.vision_report_v1 import render_vision_report


# ==========================================================
# The requirement, written out
# ==========================================================

GENERIC_CONCRETE = ("concrete", "concrete")
EXPOSED_CONCRETE = ("concrete", "exposed concrete")
GENERIC_METAL = ("metal", "metal")
PANEL_METAL = ("metal", "metal facade panels")
GENERIC_WOOD = ("wood", "wood")
CLADDING_WOOD = ("wood", "wood cladding")

#: Words that name an application, a product form or a surface treatment. None
#: of them may appear for a phrase that does not contain it.
CONCRETE_APPLICATION = ("exposed",)
METAL_APPLICATION = ("panel", "cladding", "facade")
WOOD_APPLICATION = ("cladding", "panel", "facade")

LANGS = ("fa", "en")

KNOWLEDGE_HEADER = {
    "fa": "از نظر دانش معماری",
    "en": "Architectural knowledge (term match",
}


# ==========================================================
# Harness
# ==========================================================

_RESOLVER = None


def _resolver():
    global _RESOLVER
    if _RESOLVER is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _RESOLVER = ArchitecturalKnowledgeResolver()
    return _RESOLVER


def _identities(text):
    """Ontology identities for `text` after containment suppression."""

    resolver = _resolver()
    candidates = resolver.material_candidates(text, text.lower())
    return [(item["id"], item["normalized"])
            for item in resolver.suppress_contained_materials(candidates)]


def _observe(phrase):
    with contextlib.redirect_stdout(io.StringIO()):
        return build_architectural_observation(
            {"observed": [phrase]}, provider="synthetic", model="none")


def _knowledge(phrase):
    with contextlib.redirect_stdout(io.StringIO()):
        return resolve_observed_material_knowledge(_observe(phrase))


def _entries(phrase):
    return _knowledge(phrase).get("materials") or []


def _report(phrase, language):
    with contextlib.redirect_stdout(io.StringIO()):
        observation = _observe(phrase)
        return render_vision_report(
            {"architectural_observation": observation,
             "architectural_knowledge":
                 resolve_observed_material_knowledge(observation)},
            language,
        )


def _knowledge_section(report, language):
    """Only the knowledge block of `report` — not the material list above it."""

    for section in report.split("\n\n"):
        if KNOWLEDGE_HEADER[language] in section:
            return section
    return ""


@lru_cache(maxsize=None)
def _intent(text):
    with contextlib.redirect_stdout(io.StringIO()):
        return ArchitecturalIntent().extract({"prompt": text})


def _request_materials(text):
    return list(_intent(text).get("materials") or [])


def _synthetic_workflow():
    return {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "template positive"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "template negative"}},
        "3": {"class_type": "KSampler",
              "inputs": {"positive": ["1", 0], "negative": ["2", 0],
                         "seed": 1, "steps": 1, "denoise": 1.0}},
    }


def _render_prompt(text):
    """The real request chain, up to the sampler-facing positive text."""

    intent = _intent(text)
    instruction = build_render_instruction(text, mode="text2img")
    provenance = (instruction.get("constraints") or {}).get(
        "floor_count_provenance") or {}
    handoff = {
        "contract": "RenderConstraintBlockV1",
        "version": "1.0",
        "constraint_block": build_constraint_block(instruction),
        "source": "render_instruction.english_instruction",
        "floor_count": (provenance.get("value")
                        if provenance.get("source") in ("USER_TEXT",
                                                        "USER_CONFIRMATION")
                        else None),
    }
    with contextlib.redirect_stdout(io.StringIO()):
        built = PromptBuilder().build(
            {"prompt": "Architectural visualization request",
             "architectural_intent": intent})
        resolved = resolve_render_prompt(
            compiled_prompt="Architectural visualization of the requested building.",
            builder_prompt=built.get("description") or "",
            architectural_instruction=handoff,
        )
        final_prompt = resolved.get("prompt") or resolved.get("final_prompt") or ""
        workflow = WorkflowInjector().inject_prompt(
            _synthetic_workflow(), final_prompt, None)
    return final_prompt, workflow["1"]["inputs"]["text"]


# ==========================================================
# 1. Generic materials stay generic
# ==========================================================


@pytest.mark.parametrize("text", ["concrete wall", "a concrete wall surface"])
def test_generic_concrete_does_not_become_exposed_concrete(text):

    identities = _identities(text)

    assert identities == [GENERIC_CONCRETE], (
        "a generic concrete phrase published a surface treatment: %r"
        % (identities,))


@pytest.mark.parametrize("text", ["metal railing", "metal handrail"])
def test_generic_metal_does_not_become_facade_panels(text):

    identities = _identities(text)

    assert identities == [GENERIC_METAL], (
        "a generic metal phrase published a product form: %r" % (identities,))


@pytest.mark.parametrize("text", ["wooden door", "wood trim"])
def test_generic_wood_does_not_become_cladding(text):

    identities = _identities(text)

    assert identities == [GENERIC_WOOD], (
        "a generic wood phrase published an application: %r" % (identities,))


def test_persian_generic_concrete_is_generic():
    assert _identities("بتن") == [GENERIC_CONCRETE]


def test_persian_generic_metal_is_generic():
    assert _identities("فلز") == [GENERIC_METAL]


def test_persian_generic_wood_is_generic():
    assert _identities("چوب") == [GENERIC_WOOD]


# ==========================================================
# 2. An explicit qualifier survives — and is actually READ
# ==========================================================


def test_explicit_exposed_concrete_keeps_its_treatment():
    assert _identities("exposed concrete wall") == [EXPOSED_CONCRETE]


def test_explicit_persian_exposed_concrete_keeps_its_treatment():
    assert _identities("بتن اکسپوز") == [EXPOSED_CONCRETE]


def test_explicit_metal_facade_panels_keep_the_panel_application():
    assert _identities("metal facade panels") == [PANEL_METAL]


def test_explicit_wood_cladding_keeps_the_application():
    assert _identities("wood cladding") == [CLADDING_WOOD]


def test_panel_application_is_read_from_the_phrase_not_guessed():
    """`matched_term` is the evidence. Before the correction the panel words
    were never matched at all: the phrase produced `metal` as the evidence and
    `metal facade panels` as the identity, so the identity was a coincidence
    rather than a reading of the text."""

    entries = _entries("metal facade panels")

    assert entries

    assert entries[0]["matched_term"] == "metal facade panels", (
        "the application was not read from the phrase: %r"
        % (entries[0]["matched_term"],))


def test_cladding_application_is_read_from_the_phrase_not_guessed():

    entries = _entries("wood cladding")

    assert entries

    assert entries[0]["matched_term"] == "wood cladding"


def test_thermowood_cladding_keeps_both_the_material_and_the_application():
    """The named material is thermowood; the named application is cladding.

    Dropping "thermo" would lose specificity the text provided; adding a
    facade or a panel would invent one it did not.
    """

    identities = _identities("thermowood cladding")

    assert [identity for identity, _normalized in identities] == ["wood"]

    normalized = identities[0][1]

    assert "thermowood" in normalized
    assert "cladding" in normalized
    assert "panel" not in normalized
    assert "facade" not in normalized


# ==========================================================
# 3. Slash-separated components keep their own scope
# ==========================================================


def test_slash_separated_materials_do_not_inherit_each_others_application():
    """"dark metal/wood trim" names two families and one shared application.

    The application is "trim" — neither component may borrow "panels" or
    "cladding" from the other's record.
    """

    identities = _identities("dark metal/wood trim")

    assert {identity for identity, _normalized in identities} == {"metal", "wood"}

    published = " ".join(normalized for _identity, normalized in identities)

    assert "panel" not in published
    assert "cladding" not in published


# ==========================================================
# 4. Negation, uncertainty, alternatives
# ==========================================================


def test_negated_metal_panels_are_not_a_positive_material():

    observation = _observe("No metal panels")

    labels = [label
              for entry in (observation.get("material_observations") or [])
              for label in (entry.get("materials") or [])]

    assert labels == []

    assert _knowledge("No metal panels")["materials"] == []

    assert _request_materials("No metal panels") == []


def test_hedged_explicit_concrete_keeps_both_the_hedge_and_the_treatment():

    entries = _observe("Possibly exposed concrete").get(
        "material_observations") or []

    assert entries and entries[0].get("hedged") is True

    knowledge = _entries("Possibly exposed concrete")

    assert knowledge

    assert knowledge[0]["ontology_normalized"] == "exposed concrete"

    assert knowledge[0].get("hedged") is True


def test_concrete_or_stone_remains_an_alternative():
    """The vision path keeps both sides as CANDIDATES, not assertions."""

    observation = _observe("concrete or stone")

    entries = observation.get("material_observations") or []

    assert entries

    assert entries[0].get("materials") == []

    assert entries[0].get("material_alternatives") == [["concrete", "stone"]]

    knowledge = _knowledge("concrete or stone")

    assert knowledge["materials"] == []

    assert knowledge["status"] == "CANDIDATES_ONLY"

    candidates = [entry["ontology_normalized"]
                  for entry in knowledge["material_candidates"]]

    assert "concrete" in candidates

    # The request path has never modelled alternatives; it must keep BOTH
    # sides and collapse neither into the other.
    requested = _request_materials("concrete or stone")

    assert "concrete" in requested
    assert "natural stone facade" in requested


# ==========================================================
# 5. The earlier brick corrections are intact
# ==========================================================


@pytest.mark.parametrize("text,expected", [
    ("brick facade", ("brick", "brick facade")),
    ("red brick", ("brick_red", "red brick facade")),
    ("fire brick", ("fire_brick", "fire resistant brick facade")),
    ("نمای آجری", ("brick", "brick facade")),
])
def test_brick_identity_corrections_are_unchanged(text, expected):
    assert _identities(text) == [expected]


# ==========================================================
# 6. No new identity was invented to express the qualifier
# ==========================================================


@pytest.mark.parametrize("identity", ["concrete", "metal", "wood"])
def test_the_three_identities_are_unchanged(identity):
    materials = _resolver().data.get("materials", {})

    assert identity in materials

    assert materials[identity].get("normalized") == identity, (
        "the canonical form of %r still carries an application: %r"
        % (identity, materials[identity].get("normalized")))


@pytest.mark.parametrize("identity",
                         ["exposed_concrete", "metal_panels",
                          "metal_facade_panels", "wood_cladding"])
def test_no_subtype_identity_was_added(identity):
    assert identity not in _resolver().data.get("materials", {})


# ==========================================================
# 7. Reporting — the reader is told what the term means, not more
# ==========================================================


@pytest.mark.parametrize("language", LANGS)
def test_generic_concrete_report_does_not_say_exposed(language):

    section = _knowledge_section(_report("concrete wall", language), language)

    assert section, "the knowledge block disappeared"

    assert "concrete" in section

    assert "exposed" not in section, (
        "the report published a surface treatment the phrase never named")


@pytest.mark.parametrize("language", LANGS)
def test_explicit_concrete_report_still_says_exposed(language):

    section = _knowledge_section(
        _report("exposed concrete wall", language), language)

    assert "exposed concrete" in section


@pytest.mark.parametrize("language", LANGS)
def test_generic_metal_report_does_not_say_panels(language):

    section = _knowledge_section(_report("metal railing", language), language)

    assert section

    assert "panel" not in section


@pytest.mark.parametrize("language", LANGS)
def test_generic_wood_report_does_not_say_cladding(language):

    section = _knowledge_section(_report("wooden door", language), language)

    assert section

    assert "cladding" not in section


@pytest.mark.parametrize("language", LANGS)
def test_persian_generic_concrete_report_is_generic(language):

    section = _knowledge_section(_report("بتن", language), language)

    assert section

    assert "exposed" not in section


@pytest.mark.parametrize("language", LANGS)
def test_persian_explicit_concrete_report_keeps_the_treatment(language):

    section = _knowledge_section(_report("بتن اکسپوز", language), language)

    assert "exposed concrete" in section


# ==========================================================
# 8. Request path — the ontology is shared with the render path
# ==========================================================


@pytest.mark.parametrize("text,expected", [
    ("concrete wall", ["concrete"]),
    ("exposed concrete wall", ["exposed concrete"]),
    ("metal railing", ["metal"]),
    ("metal facade panels", ["metal facade panels"]),
    ("wooden door", ["wood"]),
    ("wood cladding", ["wood cladding"]),
])
def test_request_materials_carry_exactly_the_specificity_of_the_text(
        text, expected):

    assert _request_materials(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("بتن", ["concrete"]),
    ("بتن اکسپوز", ["exposed concrete"]),
    ("فلز", ["metal"]),
    ("چوب", ["wood"]),
])
def test_persian_request_materials_are_equivalent(text, expected):

    assert _request_materials(text) == expected


def test_request_for_thermowood_cladding_keeps_thermowood():
    """`thermowood` is a named material, not a wood generic.

    The ontology already declares it; the request path must not reduce it to
    the family.
    """

    requested = _request_materials("thermowood cladding")

    assert requested

    assert "thermowood" in requested[0]
    assert "cladding" in requested[0]


@pytest.mark.parametrize("text,forbidden", [
    ("concrete wall", "exposed concrete"),
    ("metal railing", "metal facade panels"),
    ("wooden door", "wood cladding"),
])
def test_render_prompt_does_not_assert_an_unnamed_application(text, forbidden):

    final_prompt, positive = _render_prompt(text)

    assert forbidden not in positive, (
        "the sampler was told %r for a request that never said it" % (forbidden,))

    assert forbidden not in final_prompt


def test_render_prompt_keeps_an_explicit_application():

    _final_prompt, positive = _render_prompt("metal facade panels")

    assert "metal facade panels" in positive
