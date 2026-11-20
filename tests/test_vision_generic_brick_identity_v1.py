# -*- coding: utf-8 -*-
"""VISION_GENERIC_BRICK_IDENTITY_V1 — focused CPU tests.

Two confirmed defects:

1. The red-brick record declared `"brick facade"` as one of its synonyms, so a
   generic English phrase resolved to the SPECIFIC red identity. The same
   synonym also made `fire brick facade` produce BOTH `brick_red` and
   `fire_brick`.
2. The vision observation vocabulary knew `آجر` but not the adjectival `آجری`,
   so `نمای آجری` — an alias the ontology already declares — produced no
   material observation at all and the knowledge lookup never ran.

Semantic requirement, pinned here INDEPENDENTLY of the production JSON:

    generic brick   -> "brick facade"
    red brick       -> "red brick facade"
    fire brick      -> "fire resistant brick facade"

A colour or subtype may appear only when the text supports it.

Real observation -> knowledge -> report chain, and the real request-path
resolver. SYNTHETIC inputs only. No Ollama. No GPU. No ComfyUI.
"""

import contextlib
import io

import pytest

from core.knowledge.architectural_knowledge_resolver import (
    ArchitecturalKnowledgeResolver,
)
from core.vision.architectural_observation_v1 import build_architectural_observation
from core.vision.observed_material_knowledge_v1 import (
    resolve_observed_material_knowledge,
)
from core.vision.vision_report_v1 import render_vision_report


#: The semantic requirement, written out. Deliberately NOT read from the
#: ontology under test — a test that derives its expectation from the artefact
#: it is checking cannot detect a wrong artefact.
GENERIC = ("brick", "brick facade")
RED = ("brick_red", "red brick facade")
FIRE = ("fire_brick", "fire resistant brick facade")


_RESOLVER = None


def _resolver():
    global _RESOLVER
    if _RESOLVER is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _RESOLVER = ArchitecturalKnowledgeResolver()
    return _RESOLVER


def _identities(text):
    """Ontology identities for `text`, after containment suppression.

    Returns `[(id, normalized)]` in resolution order.
    """

    resolver = _resolver()

    candidates = resolver.material_candidates(text, text.lower())

    return [(item["id"], item["normalized"])
            for item in resolver.suppress_contained_materials(candidates)]


def _ids(text):
    return [identity for identity, _normalized in _identities(text)]


def _observe(phrase):

    return build_architectural_observation(
        {"observed": [phrase]}, provider="synthetic", model="none")


def _knowledge(phrase):

    return resolve_observed_material_knowledge(_observe(phrase))


def _report(phrase, language):

    observation = _observe(phrase)

    return render_vision_report(
        {"architectural_observation": observation,
         "architectural_knowledge": resolve_observed_material_knowledge(observation)},
        language,
    )


def _labels(phrase):

    entries = _observe(phrase).get("material_observations") or []

    return [label for entry in entries for label in (entry.get("materials") or [])]


LANGS = ["fa", "en"]


# ==========================================================
# 1. Generic English brick stays generic
# ==========================================================


@pytest.mark.parametrize("text", ["brick facade", "a brick facade surface"])
def test_generic_english_brick_resolves_to_generic_brick(text):

    identities = _identities(text)

    assert identities == [GENERIC], (
        "a generic brick phrase resolved to a colour-specific identity: %r"
        % (identities,))


@pytest.mark.parametrize("text", ["brick facade", "a brick facade surface"])
def test_generic_brick_never_publishes_a_colour(text):

    for identity, normalized in _identities(text):

        assert "red" not in normalized.lower(), (
            "an unsupported colour was published: %r" % (normalized,))


def test_brick_facade_does_not_resolve_to_the_red_record():

    assert "brick_red" not in _ids("brick facade")


# ==========================================================
# 2. Explicit red and fire identities are preserved
# ==========================================================


@pytest.mark.parametrize("text", ["red brick facade", "red brick"])
def test_explicit_red_brick_is_still_red(text):

    assert _identities(text) == [RED]


def test_explicit_fire_brick_is_only_fire_brick():
    """`fire brick facade` must not also produce a red-brick identity.

    The old `"brick facade"` synonym matched inside this phrase, so the phrase
    resolved to `brick_red` AND `fire_brick` at once.
    """

    assert _identities("fire brick facade") == [FIRE], (
        "an explicit fire-brick phrase produced an extra identity")


def test_fire_brick_without_the_facade_word_is_unchanged():

    assert _identities("fire brick") == [FIRE]


# ==========================================================
# 3. Persian forms — observation AND ontology
# ==========================================================


@pytest.mark.parametrize("phrase", ["نمای آجری", "آجری", "آجر"])
def test_persian_brick_is_observed(phrase):
    """The vision vocabulary must see the adjectival form."""

    assert _labels(phrase) == ["brick"], (
        "the Persian brick form produced no material observation")


@pytest.mark.parametrize("phrase", ["نمای آجری", "آجری", "آجر"])
def test_persian_brick_resolves_to_generic_brick(phrase):

    assert _identities(phrase) == [GENERIC]


@pytest.mark.parametrize("phrase", ["نمای آجری", "آجری", "آجر"])
def test_persian_brick_knowledge_is_generic(phrase):

    knowledge = _knowledge(phrase)

    assert [entry["ontology_id"] for entry in knowledge["materials"]] == ["brick"]

    assert knowledge["status"] == "RESOLVED"


def test_persian_red_brick_stays_red():

    assert _identities("آجر قرمز") == [RED]


def test_persian_fire_brick_stays_fire():

    assert _identities("آجر نسوز") == [FIRE]


# ==========================================================
# 4. Negation, uncertainty, alternatives, mixed components
# ==========================================================


def test_negated_brick_is_not_a_positive_assertion():

    observation = _observe("No brick facade")

    assert _labels("No brick facade") == []

    knowledge = _knowledge("No brick facade")

    assert knowledge["materials"] == []


def test_uncertain_brick_keeps_its_uncertainty_and_its_generic_identity():

    entries = _observe("Possibly brick facade").get("material_observations") or []

    assert entries and entries[0].get("hedged") is True

    assert entries[0].get("materials") == ["brick"]

    assert _ids("Possibly brick facade") == ["brick"]


def test_brick_or_stone_remains_an_alternative():

    entries = _observe("brick or stone").get("material_observations") or []

    assert entries

    assert entries[0].get("materials") == []

    assert entries[0].get("material_alternatives") == [["brick", "stone"]]

    knowledge = _knowledge("brick or stone")

    assert knowledge["materials"] == []

    assert knowledge["status"] == "CANDIDATES_ONLY"


def test_generic_and_specific_brick_in_one_phrase_are_both_kept():
    """`brick wall with red brick trim` — two components, two claims."""

    identities = _ids("brick wall with red brick trim")

    assert "brick" in identities, "the generic wall brick was lost"

    assert "brick_red" in identities, "the explicit red trim was lost"


# ==========================================================
# 5. Reporting — the reader must not be told "red" without support
# ==========================================================


@pytest.mark.parametrize("language", LANGS)
def test_generic_brick_report_does_not_say_red(language):

    report = _report("brick facade", language)

    assert "brick facade" in report

    assert "red brick facade" not in report, (
        "the report asserted a brick colour the text never supported")


@pytest.mark.parametrize("language", LANGS)
def test_explicit_red_brick_report_still_says_red(language):

    assert "red brick facade" in _report("red brick", language)


@pytest.mark.parametrize("language", LANGS)
def test_persian_brick_report_is_generic(language):

    report = _report("نمای آجری", language)

    assert "brick" in report

    assert "red brick facade" not in report


# ==========================================================
# 6. Request path — the ontology is shared with the render path
# ==========================================================


def _request_materials(text):
    """The real request-side resolver used by the render path."""

    from core.prompt_intelligence.architectural_intent import ArchitecturalIntent

    with contextlib.redirect_stdout(io.StringIO()):

        intent = ArchitecturalIntent().extract({"prompt": text})

    return list(intent.get("materials") or [])


def test_request_path_generic_brick_is_generic():

    assert _request_materials("brick facade") == ["brick facade"]


def test_request_path_explicit_red_brick_is_red():

    assert _request_materials("red brick") == ["red brick facade"]


def test_request_path_explicit_fire_brick_is_fire():

    assert _request_materials("آجر نسوز") == ["fire resistant brick facade"]


def test_request_path_persian_brick_is_generic():

    assert _request_materials("نمای آجری") == ["brick facade"]
