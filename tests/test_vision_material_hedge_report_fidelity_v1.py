# -*- coding: utf-8 -*-
"""VISION_MATERIAL_HEDGE_REPORT_FIDELITY_V1 — focused CPU tests.

The pipeline already distinguishes a material the observer NAMED from one it
only CONSIDERED POSSIBLE: `architectural_observation_v1._material_hedged()`
sets `hedged: True`, and `observed_material_knowledge_v1` copies that flag onto
the knowledge entry. The user-facing report ignored it, so

    "Possibly marble"   and   "marble"

rendered byte-identically — a tentative identification was published as a
named material.

These tests pin the report contract:

* a hedged material is reported as TENTATIVE, with the model's own wording
  preserved so "possibly" / "appears to be" stay visible;
* an unhedged material keeps its existing wording, unchanged;
* one hedged observation does not make the whole report uncertain;
* an alternative ("stone or marble") is NOT a hedge and must not be converted
  into one, nor resolved into a choice;
* a material that is asserted elsewhere is not repeated as tentative;
* provenance and the knowledge contract are untouched.

SYNTHETIC fixtures only. No Ollama. No GPU. No ComfyUI. No ontology change.
"""

import pytest

from core.vision.architectural_observation_v1 import build_architectural_observation
from core.vision.observed_material_knowledge_v1 import (
    resolve_observed_material_knowledge,
)
from core.vision.vision_report_v1 import render_vision_report


#: The exact headers this milestone introduces. Quoted here deliberately: a
#: test that imported them from the module would pass even if the module
#: rendered nothing.
TENTATIVE_FA = "مصالحی که مدل با عدم‌قطعیت نام برده است"
TENTATIVE_EN = "Tentatively identified materials"

DEFINITE_FA = "مصالح نام‌برده‌شده توسط مدل"
DEFINITE_EN = "Materials named by the model"

ALTERNATIVES_FA = "گزینه‌های نام‌برده‌شده"
ALTERNATIVES_EN = "Alternatives the model named"


def _chain(phrases):
    """(observation, knowledge) for a list of observer phrases."""

    observation = build_architectural_observation(
        {"observed": list(phrases)},
        provider="synthetic",
        model="none",
    )

    knowledge = resolve_observed_material_knowledge(observation)

    return observation, knowledge


def _report(phrases, language="fa"):

    observation, knowledge = _chain(phrases)

    interpretation = {
        "architectural_observation": observation,
        "architectural_knowledge": knowledge,
    }

    return render_vision_report(interpretation, language)


def _section(report, header):
    """The one section that starts with `header`, or "".

    Sections are joined with a blank line by `render_vision_report`, so this
    isolates the block without depending on its neighbours.
    """

    for block in report.split("\n\n"):

        if block.startswith(header):

            return block

    return ""


def _labels_in(report, header):
    """Material labels listed in the section under `header`."""

    block = _section(report, header)

    labels = set()

    for line in block.splitlines()[1:]:

        line = line.strip().lstrip("•-").strip()

        if not line:

            continue

        labels.add(line.split("(")[0].strip())

    return labels


# ==========================================================
# A / B — a hedged material is reported as tentative
# ==========================================================


@pytest.mark.parametrize("language,tentative,definite", [
    ("fa", TENTATIVE_FA, DEFINITE_FA),
    ("en", TENTATIVE_EN, DEFINITE_EN),
])
def test_A_possibly_marble_is_reported_as_tentative(language, tentative, definite):
    """`Possibly marble` must not read as a named material."""

    report = _report(["Possibly marble"], language)

    assert tentative in report, (
        "a hedged material was published without any tentative wording")

    assert definite not in report, (
        "the hedged material was still listed among the materials the model "
        "named")


@pytest.mark.parametrize("language", ["fa", "en"])
def test_A_the_hedged_and_the_definite_report_are_no_longer_identical(language):
    """The defect: both inputs produced byte-identical text."""

    hedged = _report(["Possibly marble"], language)

    definite = _report(["marble"], language)

    assert hedged != definite, (
        "an uncertain identification still renders exactly like a confident one")


@pytest.mark.parametrize("language", ["fa", "en"])
def test_A_the_model_wording_is_preserved(language):
    """The qualifier itself must remain visible to the reader."""

    report = _report(["Possibly marble"], language)

    assert "Possibly marble" in report, (
        "the original evidence phrase was dropped, so the reader cannot see "
        "why the material is uncertain")


@pytest.mark.parametrize("language,tentative", [
    ("fa", TENTATIVE_FA),
    ("en", TENTATIVE_EN),
])
def test_B_appears_to_be_is_reported_as_tentative(language, tentative):
    """A tentative APPEARANCE is uncertainty too, not only the word 'possibly'."""

    report = _report(["appears to be stone"], language)

    assert tentative in report

    assert "appears to be stone" in report


# ==========================================================
# C / D — ordinary unhedged material wording is unchanged
# ==========================================================


@pytest.mark.parametrize("language,tentative,definite", [
    ("fa", TENTATIVE_FA, DEFINITE_FA),
    ("en", TENTATIVE_EN, DEFINITE_EN),
])
@pytest.mark.parametrize("phrase", ["White marble wall", "Natural stone facade"])
def test_C_D_unhedged_material_keeps_its_existing_wording(
        phrase, language, tentative, definite):
    """The accepted wording must not move or gain a qualifier."""

    report = _report([phrase], language)

    assert definite in report, "the named-materials section disappeared"

    assert tentative not in report, (
        "an unhedged material was reported as tentative")


@pytest.mark.parametrize("language", ["fa", "en"])
def test_C_unhedged_material_is_byte_identical_to_the_previous_contract(language):
    """No hedge present means no new section and no changed label list."""

    report = _report(["White marble wall"], language)

    assert "stone" in _labels_in(
        report, DEFINITE_FA if language == "fa" else DEFINITE_EN)


# ==========================================================
# E — one hedged observation does not make the report uncertain
# ==========================================================


@pytest.mark.parametrize("language,tentative,definite", [
    ("fa", TENTATIVE_FA, DEFINITE_FA),
    ("en", TENTATIVE_EN, DEFINITE_EN),
])
def test_E_only_the_hedged_material_is_qualified(language, tentative, definite):
    """`Brick wall` + `Possibly marble trim`: brick stays ordinary."""

    report = _report(["Brick wall", "Possibly marble trim"], language)

    definite_block = _section(report, definite)

    tentative_block = _section(report, tentative)

    assert "brick" in definite_block, (
        "the confidently named material lost its ordinary entry")

    assert "brick" not in tentative_block, (
        "a confident material was also reported as tentative")

    assert "Possibly marble trim" in tentative_block, (
        "the hedged observation is not identified by its own wording")


@pytest.mark.parametrize("language,tentative", [
    ("fa", TENTATIVE_FA),
    ("en", TENTATIVE_EN),
])
def test_E_the_report_is_not_globally_marked_uncertain(language, tentative):
    """The tentative block appears once, as a section — not as a verdict."""

    report = _report(["Brick wall", "Possibly marble trim"], language)

    assert report.count(tentative) == 1


# ==========================================================
# F — an alternative is not a hedge
# ==========================================================


@pytest.mark.parametrize("language,tentative,alternatives", [
    ("fa", TENTATIVE_FA, ALTERNATIVES_FA),
    ("en", TENTATIVE_EN, ALTERNATIVES_EN),
])
def test_F_an_alternative_stays_an_alternative(language, tentative, alternatives):
    """`stone or marble panels` names two materials and chooses neither.

    It must not be relabelled as a hedge, and neither side may be selected.
    """

    report = _report(["stone or marble panels"], language)

    assert alternatives in report, "the alternatives section was lost"

    assert tentative not in report, (
        "a disjunction was misrepresented as an uncertainty hedge")


@pytest.mark.parametrize("language", ["fa", "en"])
def test_F_the_alternative_keeps_both_sides(language):
    """Neither side of the 'or' may become an assertion."""

    observation, _ = _chain(["stone or marble panels"])

    entries = observation.get("material_observations") or []

    assert entries, "the phrase produced no material observation"

    assert not (entries[0].get("materials") or []), (
        "one side of the disjunction was asserted")

    assert entries[0].get("material_alternatives") == [["stone", "marble"]]

    assert entries[0].get("hedged") is not True, (
        "a disjunction is not a hedge")


# ==========================================================
# G — a material asserted elsewhere is not repeated as tentative
# ==========================================================


@pytest.mark.parametrize("language,tentative,definite", [
    ("fa", TENTATIVE_FA, DEFINITE_FA),
    ("en", TENTATIVE_EN, DEFINITE_EN),
])
def test_G_a_definite_material_is_not_duplicated_as_tentative(
        language, tentative, definite):
    """`stone balustrade` + `possibly stone trim`.

    MATERIAL_HEDGE_PHRASE_FIDELITY_V1_1 — the original form of this test
    asserted `"stone" not in tentative_section`. That is unsatisfiable: the
    model's own phrase is "possibly stone trim", so preserving the evidence
    necessarily puts the word `stone` inside the quotation. The only way to
    satisfy it was to DELETE the observation — which is the defect V1.1 fixes.

    The contract is therefore about IDENTITY assertions, not substrings: the
    tentative section must not assert `stone` as a standalone material label,
    while the verbatim phrase must survive.
    """

    report = _report(["stone balustrade", "possibly stone trim"], language)

    assert "stone" in _section(report, definite)

    assert "stone" not in _labels_in(report, tentative), (
        "the tentative section repeated the material identity as an assertion")

    assert "possibly stone trim" in _section(report, tentative), (
        "the evidence phrase was deleted to avoid repeating the label")


# ==========================================================
# H — provenance and the knowledge contract are unchanged
# ==========================================================


def test_H_the_hedge_flag_survives_in_the_knowledge_contract():
    """The report change must not move the entry out of `materials`.

    `knowledge["materials"]` keeps the hedged identity, flagged — this
    milestone does not redefine the contract, only its display.
    """

    _, knowledge = _chain(["Possibly marble"])

    ids = [entry.get("ontology_id") for entry in knowledge["materials"]]

    assert "marble" in ids, "the hedged identity was moved out of `materials`"

    hedged = [entry for entry in knowledge["materials"]
              if entry.get("ontology_id") == "marble"]

    assert all(entry.get("hedged") is True for entry in hedged)


def test_H_provenance_fields_are_untouched():
    """A lookup never verifies an image."""

    _, knowledge = _chain(["Possibly marble"])

    assert knowledge["verification"] == "UNVERIFIED"

    assert knowledge["authoritative"] is False

    assert knowledge["resolves_evidence"] is False

    assert knowledge["learned"] is False

    for entry in knowledge["materials"]:

        assert entry["authoritative"] is False

        assert entry["verification"] == "UNVERIFIED"

        assert entry["resolves_evidence"] is False

        assert entry["subtype_established"] is False

        assert entry["specifications_established"] is False

        assert "established" not in entry, (
            "an `established` key was added to the established list")


def test_H_no_style_is_inferred_from_a_hedged_material():

    _, knowledge = _chain(["Possibly marble"])

    assert knowledge["style"]["status"] == "INSUFFICIENT_EVIDENCE"

    assert knowledge["style"]["assigned"] is None


@pytest.mark.parametrize("language", ["fa", "en"])
def test_H_the_report_still_disclaims_verification(language):
    """The tentative section must not read as confirmation."""

    report = _report(["Possibly marble"], language)

    if language == "fa":

        assert "تأییدنشده" in report

    else:

        # The English surface has always phrased this as "not independently
        # verified" / "not independent image confirmation".
        assert ("not independently verified" in report
                or "not independent image confirmation" in report)


def test_H_the_observation_still_carries_the_hedge_flag():
    """The report reads an existing flag; it does not invent a detector."""

    observation, _ = _chain(["Possibly marble"])

    entries = observation.get("material_observations") or []

    assert entries and entries[0].get("hedged") is True
