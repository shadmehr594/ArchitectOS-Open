# -*- coding: utf-8 -*-
"""MATERIAL_HEDGE_PHRASE_FIDELITY_V1_1 — focused CPU tests.

V1 fixed the loss of hedging, but deduplicated the tentative section by
MATERIAL LABEL instead of by OBSERVATION. The observation vocabulary groups
marble under the `stone` family, so:

    "stone balustrade"        -> named: stone
    "Possibly marble cladding" -> tentative label: stone  -> filtered out
                                                              (label already named)

The whole tentative phrase disappeared from the report. A definite material in
one architectural component is NOT evidence about a different component, so
each tentative phrase is an independent claim and must survive on its own.

These tests pin:

* a tentative phrase is never deleted because its coarse family label is
  already asserted elsewhere;
* the model's wording is preserved verbatim;
* a duplicate identity is not repeated as a standalone assertion, but the
  distinct evidence phrase IS preserved (quote-only line);
* identical repeated evidence prints once; distinct phrases print separately;
* alternatives, definite wording and provenance are unchanged;
* a hedged knowledge lookup is described as a tentative term match.

Real observation → knowledge → report chain. SYNTHETIC inputs only.
No Ollama. No GPU. No ComfyUI. No ontology change.
"""

import pytest

from core.vision.architectural_observation_v1 import build_architectural_observation
from core.vision.observed_material_knowledge_v1 import (
    resolve_observed_material_knowledge,
)
from core.vision.vision_report_v1 import render_vision_report


TENTATIVE = {
    "fa": "مصالحی که مدل با عدم‌قطعیت نام برده است",
    "en": "Tentatively identified materials",
}

DEFINITE = {
    "fa": "مصالح نام‌برده‌شده توسط مدل",
    "en": "Materials named by the model",
}

ALTERNATIVES = {
    "fa": "گزینه‌های نام‌برده‌شده",
    "en": "Alternatives the model named",
}

KNOWLEDGE = {
    "fa": "از نظر دانش معماری",
    "en": "Architectural knowledge",
}


def _chain(phrases):

    observation = build_architectural_observation(
        {"observed": list(phrases)},
        provider="synthetic",
        model="none",
    )

    return observation, resolve_observed_material_knowledge(observation)


def _render(observation, knowledge, language):

    return render_vision_report(
        {"architectural_observation": observation,
         "architectural_knowledge": knowledge},
        language,
    )


def _report(phrases, language="fa"):

    observation, knowledge = _chain(phrases)

    return _render(observation, knowledge, language)


def _section(report, header):
    """The one section starting with `header`, or ""."""

    for block in report.split("\n\n"):

        if block.startswith(header):

            return block

    return ""


def _labels_in(report, header):
    """The material identity each line asserts, before any parenthetical.

    A quote-only line yields its quotation, never a bare material label — which
    is exactly the distinction this milestone must preserve.
    """

    labels = set()

    for line in _section(report, header).splitlines()[1:]:

        line = line.strip().lstrip("•-").strip()

        if line:

            labels.add(line.split("(")[0].strip())

    return labels


LANGS = ["fa", "en"]


# ==========================================================
# A — a tentative phrase is not deleted by a definite family label
# ==========================================================


@pytest.mark.parametrize("language", LANGS)
def test_A_the_tentative_cladding_phrase_survives(language):
    """`stone balustrade` must not erase `Possibly marble cladding`."""

    report = _report(["stone balustrade", "Possibly marble cladding"], language)

    tentative = _section(report, TENTATIVE[language])

    assert tentative, "the tentative section was dropped entirely"

    assert "Possibly marble cladding" in tentative, (
        "a distinct tentative observation was deleted because its coarse "
        "material family was already named")


@pytest.mark.parametrize("language", LANGS)
def test_A_the_definite_observation_remains(language):

    report = _report(["stone balustrade", "Possibly marble cladding"], language)

    assert "stone" in _labels_in(report, DEFINITE[language])


@pytest.mark.parametrize("language", LANGS)
def test_A_no_definite_marble_identity_is_invented(language):
    """The tentative phrase must not upgrade the cladding to marble."""

    report = _report(["stone balustrade", "Possibly marble cladding"], language)

    assert "marble" not in _labels_in(report, DEFINITE[language]), (
        "a hedged phrase became a definite material identity")


@pytest.mark.parametrize("language", LANGS)
def test_A_the_hedge_wording_is_verbatim(language):

    report = _report(["stone balustrade", "Possibly marble cladding"], language)

    assert "Possibly marble cladding" in report


# ==========================================================
# B — same family, different component
# ==========================================================


@pytest.mark.parametrize("language", LANGS)
def test_B_the_uncertain_trim_observation_survives(language):
    """`stone balustrade` + `possibly stone trim`: two claims, both kept."""

    report = _report(["stone balustrade", "possibly stone trim"], language)

    tentative = _section(report, TENTATIVE[language])

    assert tentative, "the tentative section was dropped entirely"

    assert "possibly stone trim" in tentative, (
        "the trim observation was discarded because the balustrade already "
        "named the same family")


@pytest.mark.parametrize("language", LANGS)
def test_B_stone_is_named_once(language):
    """The identity is asserted once — not twice, and not deleted."""

    report = _report(["stone balustrade", "possibly stone trim"], language)

    assert "stone" in _labels_in(report, DEFINITE[language])


@pytest.mark.parametrize("language", LANGS)
def test_B_the_quote_is_not_a_second_identity_assertion(language):
    """Deduplication must not happen by deleting the phrase.

    The tentative line may contain the word `stone` inside its QUOTATION; it
    must not assert `stone` as a standalone material label again.
    """

    report = _report(["stone balustrade", "possibly stone trim"], language)

    assert "stone" not in _labels_in(report, TENTATIVE[language]), (
        "the tentative section repeated the material identity as an assertion")


# ==========================================================
# C — V1 behaviour that must not regress
# ==========================================================


@pytest.mark.parametrize("language", LANGS)
def test_C_v1_behaviour_is_preserved(language):
    """`Brick wall` + `Possibly marble trim`."""

    report = _report(["Brick wall", "Possibly marble trim"], language)

    assert "brick" in _labels_in(report, DEFINITE[language])

    tentative = _section(report, TENTATIVE[language])

    assert "Possibly marble trim" in tentative

    assert "brick" not in tentative


# ==========================================================
# D / E / F — accepted behaviour unchanged
# ==========================================================


@pytest.mark.parametrize("language", LANGS)
def test_D_possibly_marble_stays_tentative(language):

    report = _report(["Possibly marble"], language)

    assert TENTATIVE[language] in report

    assert DEFINITE[language] not in report


@pytest.mark.parametrize("language", LANGS)
def test_E_white_marble_wall_keeps_its_definite_wording(language):

    report = _report(["White marble wall"], language)

    assert "stone" in _labels_in(report, DEFINITE[language])

    assert TENTATIVE[language] not in report


@pytest.mark.parametrize("language", LANGS)
def test_F_alternatives_are_unchanged(language):
    """`stone or marble panels` is a disjunction, not a hedge."""

    report = _report(["stone or marble panels"], language)

    assert ALTERNATIVES[language] in report

    assert TENTATIVE[language] not in report

    assert DEFINITE[language] not in report

    observation, _ = _chain(["stone or marble panels"])

    assert not (observation["material_observations"][0].get("materials") or [])


# ==========================================================
# G — dedupe by evidence, not by label
# ==========================================================


@pytest.mark.parametrize("language", LANGS)
def test_G_identical_repeated_evidence_prints_once(language):
    """The same observation twice is one line."""

    observation, knowledge = _chain(["Possibly marble"])

    entry = observation["material_observations"][0]

    duplicated = dict(observation, material_observations=[entry, dict(entry)])

    report = _render(duplicated, knowledge, language)

    assert report.count("Possibly marble") == 1, (
        "the same evidence phrase was printed more than once")


@pytest.mark.parametrize("language", LANGS)
def test_G_distinct_phrases_with_the_same_label_are_both_kept(language):
    """Two different phrases share the `stone` family — both must appear."""

    report = _report(["Possibly marble", "possibly marble cladding"], language)

    tentative = _section(report, TENTATIVE[language])

    assert "Possibly marble" in tentative

    assert "possibly marble cladding" in tentative


# ==========================================================
# H — a definite claim and a tentative claim about the same material
# ==========================================================


@pytest.mark.parametrize("language", LANGS)
def test_H_both_claims_are_preserved_and_distinguished(language):
    """The balustrade is stone; the trim is only *possibly* stone."""

    observation, knowledge = _chain(
        ["stone balustrade", "possibly stone trim"])

    report = _render(observation, knowledge, language)

    definite = _section(report, DEFINITE[language])

    tentative = _section(report, TENTATIVE[language])

    assert "stone" in definite, "the definite assertion was lost"

    assert "possibly stone trim" in tentative, (
        "the independent tentative claim was lost")

    # The material identity itself is NOT globally downgraded.
    ids = [entry.get("ontology_id") for entry in knowledge["materials"]]

    assert "stone" in ids


# ==========================================================
# I — the knowledge lookup says when the term match is tentative
# ==========================================================


@pytest.mark.parametrize("language", LANGS)
def test_I_a_hedged_term_match_is_described_as_tentative(language):
    """A hedged lookup must not read like a definite material identification."""

    observation, knowledge = _chain(
        ["stone balustrade", "Possibly marble cladding"])

    hedged = [entry for entry in knowledge["materials"]
              if entry.get("ontology_id") == "marble"]

    assert hedged and hedged[0].get("hedged") is True, (
        "fixture is wrong: the marble lookup should be hedged")

    report = _render(observation, knowledge, language)

    # Scoped to the KNOWLEDGE block: the tentative material section also uses
    # the word "احتمالی" / "tentative", so a whole-report assertion would pass
    # without the knowledge branch being fixed at all.
    knowledge_block = _section(report, KNOWLEDGE[language])

    assert "marble" in knowledge_block

    if language == "fa":

        assert "احتمالی" in knowledge_block, (
            "a hedged lookup was explained as if it were definite")

    else:

        assert "tentative" in knowledge_block.lower(), (
            "a hedged lookup was explained as if it were definite")


@pytest.mark.parametrize("language", LANGS)
def test_I_an_unhedged_term_match_is_not_called_tentative(language):
    """The tentative wording must be specific to hedged lookups."""

    report = _report(["Natural stone facade"], language)

    knowledge_block = _section(report, KNOWLEDGE[language])

    assert knowledge_block

    if language == "fa":

        assert "احتمالی" not in knowledge_block

    else:

        assert "tentative" not in knowledge_block.lower()


def test_I_the_knowledge_contract_is_unchanged():
    """Only the display changes; the lookup keeps its identity and flags."""

    _, knowledge = _chain(["stone balustrade", "Possibly marble cladding"])

    ids = [entry.get("ontology_id") for entry in knowledge["materials"]]

    assert ids.count("marble") == 1

    assert knowledge["verification"] == "UNVERIFIED"

    assert knowledge["authoritative"] is False

    assert knowledge["resolves_evidence"] is False

    for entry in knowledge["materials"]:

        assert entry["authoritative"] is False

        assert entry["resolves_evidence"] is False
