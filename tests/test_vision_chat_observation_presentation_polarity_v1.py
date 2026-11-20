# -*- coding: utf-8 -*-
"""CHAT_OBSERVATION_PRESENTATION_POLARITY_V1 — focused CPU tests.

THE USER-VISIBLE DEFECT
-----------------------
`render_observation()` printed the strict, locally corroborated band — which is
EMPTY for all four facades — and then a flat, unfiltered dump of every provider
candidate under one heading. The reply therefore opened with

    Elements visible in the image:
    • No visible element is reported with evidence.

and then listed 16–45 model claims. Two distinct facts were collapsed into one
false sentence, and the curated `attributed_elements` band was never read.

WHAT THIS FILE PINS
-------------------
1. Independently corroborated elements and model-reported descriptions are
   different sections with different wording.
2. "Nothing was corroborated" is never rendered as "the model saw nothing".
3. A claim whose polarity is ABSENT never enters the positive attributed band
   and is never printed as a positive observation.
4. Model-reported absences are still shown — under an explicit, unverified
   absence heading.
5. Each claim appears once.
6. The structured contract keeps every provider candidate.
7. English and Persian are both correct.
8. Observation-only output adds no classification, function or dimension.

All assertions run through the real production functions:
`build_observation`, `render_observation`, `ResponseAdapter.build_message`.
"""

import json
import os

import pytest

from core.chat.response_adapter import ResponseAdapter
from core.vision.architectural_vision_interpreter_v1 import (
    ArchitecturalVisionInterpreterV1,
)
from core.vision.image_understanding_v1 import _build_bridge_understanding
from core.vision.vision_observation_mode_v1 import (
    build_observation,
    render_observation,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORPUS = os.path.join(ROOT, "runs", "vision_finished_facade_acceptance_v1")

FACADE_DIRS = {
    "A": "A_neue_nationalgalerie_2022",
    "B": "B_ref_10",
    "C": "C_ref_14",
    "D": "D_upload_042039a7_003",
}

#: Section headings the renderer must publish, per language.
HEADERS = {
    "en": {
        "corroborated": "Elements visible in the image:",
        "attributed": "Reported by the vision model",
        "absence": "Model-reported absences",
        "uncertain": "Claims the model left uncertain",
    },
    "fa": {
        "corroborated": "عناصر قابل مشاهده در تصویر:",
        "attributed": "گزارش مدل بینایی",
        "absence": "نبودِ گزارش‌شده توسط مدل",
        "uncertain": "ادعاهایی که مدل نامشخص گذاشته",
    },
}

#: The sentence that must never be printed when provider claims exist.
FALSE_EMPTY_STATEMENT = "No visible element is reported with evidence."

#: Architectural descriptions the user must be able to read.
DESCRIPTIVE = {
    "C": [
        "top level has arched\u2011top (round\u2011headed) windows",
        "rectangular windows flanking the central pedimented bay",
    ],
    "D": [
        "dark main door",
        "dark\u2011framed glass doors",
        "tall arched window",
    ],
}

EXPECTED_SPACE_TYPE = {"A": "unknown", "B": "facade", "C": "unknown", "D": "entrance"}

EXPECTED_FLOORS = {"A": 1, "B": 2, "C": None, "D": 2}

EXPECTED_ELEMENTS = {"A": 5, "B": 15, "C": 15, "D": 19}

#: Reasons that may never reach the positive attributed band.
NON_ATTRIBUTABLE = (
    "unknown_preserved",
    "negative_claim_requires_explicit_local_absence",
    "interpretation_is_not_observation",
    "numeric_category_mismatch",
    "verification_failed",
)


def _load(case, name="03_understanding.json"):
    with open(os.path.join(CORPUS, FACADE_DIRS[case], name), encoding="utf-8") as fh:
        return json.load(fh)


def _understanding(case):
    """Replay the saved bridge payload; `generation_status` is preserved."""

    saved = _load(case)

    return _build_bridge_understanding(
        saved["visual_observer_bridge"],
        provider=saved["provider"], model=saved["model"],
        image_id=saved["image_id"], source_type=saved["source_type"],
        source_hash=saved["source_hash"],
        local_plan_reading=saved.get("local_plan_reading"),
    )


def _observation(case, language="en"):
    return build_observation(_understanding(case), language=language)


def _chat_text(case, language="en"):
    """The user-facing text through the real response adapter."""

    observation = _observation(case, language)

    result = {
        "type": "image_observation",
        "engine": "vision+observation_mode",
        "result": observation,
        "observation": observation,
        "status": "success",
        "language": {
            "input_language": "english" if language == "en" else "persian",
            "output_language": "english" if language == "en" else "persian",
            "guard_status": "not_applicable",
            "corrected": False,
        },
    }

    return ResponseAdapter().build_message(result)


def _section(text, header):
    """The bullet lines under `header`, or [] when the section is absent."""

    lines = text.splitlines()

    for index, line in enumerate(lines):

        if line.strip().startswith(header):

            body = []

            for follow in lines[index + 1:]:

                if follow.strip().startswith("•"):

                    body.append(follow)

                elif follow.strip():

                    break

            return body

    return []


def _candidates(case):
    return [c for c in _understanding(case).get("provider_candidates") or []
            if isinstance(c, dict)]


def _absent_texts(case):
    return {
        str(c.get("text") or "").strip()
        for c in _candidates(case)
        if c.get("polarity") == "ABSENT"
    }


def _band(case):
    return _observation(case).get("attributed_elements") or []


# ==========================================================
# A — POSITIVE ATTRIBUTED DESCRIPTIONS ARE RENDERED
# ==========================================================


@pytest.mark.parametrize("case", ["C", "D"])
def test_a1_the_response_publishes_a_model_reported_section(case):
    """A curated section for provider descriptions must exist and be non-empty."""

    body = _section(_chat_text(case), HEADERS["en"]["attributed"])

    assert body, (
        case + ": the response has no model-reported section — the curated "
        "attributed band is still not rendered")


@pytest.mark.parametrize("case", sorted(DESCRIPTIVE))
def test_a2_architectural_descriptions_are_readable_in_that_section(case):
    """Windows and doors the model described must be readable where they belong."""

    body = "\n".join(_section(_chat_text(case), HEADERS["en"]["attributed"]))

    assert body, case + ": no model-reported section"

    for phrase in DESCRIPTIVE[case]:

        assert phrase in body, (
            case + ": an architectural description is missing from the "
            "model-reported section: " + phrase)


def test_a3_the_renderer_consumes_the_band_not_the_raw_dump():
    """Proof the band is the source: an entry added ONLY to the band is shown.

    The raw `provider_candidates` list is untouched, so a renderer that still
    walks the dump cannot produce this sentence.
    """

    observation = _observation("D")

    sentinel = "SENTINEL-PROBE-claim only in the attributed band"

    observation["attributed_elements"] = list(observation["attributed_elements"]) + [{
        "name": sentinel,
        "label": sentinel,
        "kind": ["window"],
        "category": "openings.windows",
        "evidence": sentinel,
        "evidence_class": "provider observation (unconfirmed)",
        "confidence": "not confirmed",
        "status": "reported, not independently confirmed",
        "source": "provider",
        "verification_reason": "claim_properties_not_verified",
        "polarity": "PRESENT",
    }]

    text = render_observation(observation, "en")

    assert sentinel in text, (
        "the renderer ignores `attributed_elements` and prints the raw dump")


# ==========================================================
# B — NO MISLEADING EMPTY-OBSERVATION STATEMENT
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_b1_the_response_never_says_the_model_saw_nothing(case):
    """Provider claims exist, so that sentence is false."""

    text = _chat_text(case)

    assert FALSE_EMPTY_STATEMENT not in text, (
        case + ": the reply still claims no element was reported, although the "
        "model reported " + str(len(_candidates(case))) + " claims")


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_b2_corroboration_and_observation_are_distinguished(case):
    """"Nothing independently corroborated" must be stated as such, not as
    "nothing observed"."""

    text = _chat_text(case).lower()

    assert "corroborat" in text, (
        case + ": the reply does not say whether anything was independently "
        "corroborated")


# ==========================================================
# C — POLARITY SAFETY
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_c1_no_absent_claim_enters_the_positive_band(case):
    """A model-reported absence is not a positive attributed observation."""

    absent = _absent_texts(case)

    names = {entry.get("name") for entry in _band(case)}

    leaked = absent & names

    assert not leaked, (
        case + ": negated claims sit in the positive attributed band: "
        + repr(sorted(leaked)))


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_c2_no_absent_claim_is_printed_as_a_positive_observation(case):
    """It may appear only under the model-reported absence heading."""

    text = _chat_text(case)

    absence_body = "\n".join(_section(text, HEADERS["en"]["absence"]))

    attributed_body = "\n".join(_section(text, HEADERS["en"]["attributed"]))

    for phrase in _absent_texts(case):

        assert phrase not in attributed_body, (
            case + ": a negated claim is listed as a positive description: "
            + phrase)

        if phrase in text:

            assert phrase in absence_body, (
                case + ": a negated claim is printed outside the absence "
                "section: " + phrase)


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_c3_every_band_entry_is_affirmatively_present(case):
    """Only affirmatively present claims are positive observations.

    The band records the polarity it admitted on, so this is checked on the
    contract itself rather than re-derived from the candidate list.
    """

    for entry in _band(case):

        assert entry.get("polarity") == "PRESENT", (
            case + ": a claim with polarity " + repr(entry.get("polarity"))
            + " is in the positive band: " + str(entry.get("name")))


# ==========================================================
# D — NEGATIVE CLAIMS REMAIN AVAILABLE
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_d1_model_reported_absences_are_presented(case):
    """A stated absence must not be silently discarded."""

    body = "\n".join(_section(_chat_text(case), HEADERS["en"]["absence"]))

    assert body, case + ": no model-reported absence section"

    for phrase in _absent_texts(case):

        assert phrase in body, (
            case + ": a model-reported absence was dropped: " + phrase)


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_d2_absences_are_marked_unverified(case):
    """A reported absence is not proven absence."""

    observation = _observation(case)

    absences = observation.get("reported_absences") or []

    assert absences, case + ": the contract carries no reported absences"

    for entry in absences:

        assert entry.get("confidence") == "not confirmed"

        assert entry.get("status") == "reported, not independently confirmed"


# ==========================================================
# E — NO DUPLICATION
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_e1_each_claim_is_printed_once(case):
    """The curated band replaced the raw dump; printing both would duplicate."""

    text = _chat_text(case)

    for phrase in list(DESCRIPTIVE.get(case, [])) + sorted(_absent_texts(case)):

        assert text.count(phrase) == 1, (
            case + ": a claim is printed %d times: %s"
            % (text.count(phrase), phrase))


# ==========================================================
# F — FULL AUDIT PROVENANCE
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_f1_the_contract_keeps_every_provider_candidate(case):
    """The human view is curated; the structured record is complete.

    `category == "interpretations"` is excluded from the observation contract
    by a pre-existing, deliberate rule — an interpretation is not an
    observation. Every other candidate is preserved verbatim.
    """

    observation = _observation(case)

    expected = [c for c in _candidates(case) if c.get("category") != "interpretations"]

    assert len(observation["provider_candidates"]) == len(expected)

    assert {c["text"] for c in observation["provider_candidates"]} == (
        {c["text"] for c in expected})


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_f2_no_claim_is_rewritten_in_the_contract(case):
    """Every candidate text is preserved verbatim, including the rejected ones."""

    contract_texts = {c.get("text") for c in _observation(case)["provider_candidates"]}

    for candidate in _candidates(case):

        if candidate.get("category") == "interpretations":

            continue

        assert candidate.get("text") in contract_texts


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_f3_ambiguous_claims_are_never_promoted(case):
    """An ambiguous claim is not a positive architectural observation."""

    text = _chat_text(case)

    attributed_body = "\n".join(_section(text, HEADERS["en"]["attributed"]))

    for candidate in _candidates(case):

        if candidate.get("state") == "AMBIGUOUS" or (
                candidate.get("certainty") == "AMBIGUOUS"):

            phrase = str(candidate.get("text") or "").strip()

            assert phrase not in attributed_body, (
                case + ": an ambiguous claim is presented as a description: "
                + phrase)


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_f4_non_attributable_reasons_are_not_in_the_band(case):
    """Unknowns, interpretations and numeric mismatches stay out."""

    by_text = {str(c.get("text") or "").strip(): c for c in _candidates(case)}

    for entry in _band(case):

        candidate = by_text.get(entry.get("name"))

        if candidate is None:

            continue

        reason = (candidate.get("verification") or {}).get("reason")

        assert reason not in NON_ATTRIBUTABLE, (
            case + ": a claim with reason " + repr(reason) + " is in the band")


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_f5_every_contract_claim_reaches_the_human_view(case):
    """Curating the view must not silently drop architectural content.

    Every claim the observation contract carries appears in exactly one of the
    published bands. A claim the verifier withheld is still shown — as a
    report, not as evidence.
    """

    text = _chat_text(case)

    for candidate in _observation(case)["provider_candidates"]:

        phrase = str(candidate.get("text") or "").strip()

        assert phrase and phrase in text, (
            case + ": a contract claim is missing from the reply: " + phrase)


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_f6_withheld_claims_are_never_presented_as_evidence(case):
    """A claim the verifier did not admit stays a report."""

    observation = _observation(case)

    for entry in observation.get("withheld_claims") or []:

        assert entry.get("confidence") == "not confirmed"

        assert entry.get("status") == "reported, not admitted as observation evidence"

        assert entry.get("evidence_class") == (
            "provider claim (withheld by the verifier)")

        assert entry.get("name") not in {
            e.get("name") for e in observation["attributed_elements"]}


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_f7_the_bands_are_mutually_exclusive(case):
    """One claim, one band — otherwise the reply repeats itself."""

    observation = _observation(case)

    names = []

    for key in ("attributed_elements", "reported_absences",
                "uncertain_claims", "withheld_claims"):

        names.extend(e.get("name", "").lower() for e in observation.get(key) or [])

    assert len(set(names)) == len(names), (
        case + ": a claim is published in more than one band")


# ==========================================================
# G — ENGLISH AND PERSIAN
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_g1_persian_publishes_persian_headings(case):
    text = _chat_text(case, "fa")

    for key in ("attributed", "absence"):

        assert HEADERS["fa"][key] in text, (
            case + ": missing Persian heading " + key)


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_g2_persian_leaks_no_english_heading(case):
    text = _chat_text(case, "fa")

    for key, header in HEADERS["en"].items():

        if key == "corroborated":

            continue

        assert header not in text, (
            case + ": English heading leaked into the Persian reply: " + header)


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_g3_english_publishes_english_headings(case):
    text = _chat_text(case, "en")

    for key in ("attributed", "absence"):

        assert HEADERS["en"][key] in text, (
            case + ": missing English heading " + key)


@pytest.mark.parametrize("case", sorted(DESCRIPTIVE))
def test_g4_persian_keeps_the_verbatim_quote(case):
    """The provider's own words are not translated away."""

    text = _chat_text(case, "fa")

    for phrase in DESCRIPTIVE[case]:

        assert phrase in text


# ==========================================================
# H — STRICT OBSERVATION SEPARATION
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_h1_no_space_type_or_function_is_added(case):
    observation = _observation(case)

    assert observation["space_type"] is None

    assert not observation["possible_function"]

    assert not observation["design_reasoning"]


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_h2_no_dimension_or_floor_count_is_invented(case):
    observation = _observation(case)

    assert "visible_floors" not in observation

    text = _chat_text(case).lower()

    for forbidden in ("square metre", "sqm", "m2", "floor count", "طبقه:"):
        assert forbidden not in text, case + ": invented measurement: " + forbidden


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_h3_an_interpretation_is_never_published(case):
    """`category == "interpretations"` is withheld from the contract by an
    existing rule; a curated band must not re-admit it through the back door.

    This is a real regression guard: the first version of the withheld band
    iterated the UNFILTERED candidate list and republished facade D's
    "residential building" / "two-storey dwelling" interpretations.
    """

    text = _chat_text(case)

    observation = _observation(case)

    contract_categories = {c.get("category")
                           for c in observation["provider_candidates"]}

    assert "interpretations" not in contract_categories

    for candidate in _candidates(case):

        if candidate.get("category") != "interpretations":

            continue

        phrase = str(candidate.get("text") or "").strip()

        # Exact bullet match, not a substring: "residential building" occurs
        # inside the legitimate claim "…exterior elevation (facade) of a
        # residential building", and that is not a leak.
        published = [
            line for line in text.splitlines()
            if line.strip().startswith("• «" + phrase + "»")
        ]

        assert not published, (
            case + ": an interpretation was published as an observation: "
            + phrase)


# ==========================================================
# PRESERVED ARCHITECTURAL BASELINE
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_p1_element_counts_are_unchanged(case):
    interpretation = ArchitecturalVisionInterpreterV1().interpret(
        _understanding(case))

    assert len(interpretation["architectural_observation"]
               ["architectural_elements"]) == EXPECTED_ELEMENTS[case]


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_p2_floor_counts_are_unchanged(case):
    interpretation = ArchitecturalVisionInterpreterV1().interpret(
        _understanding(case))

    assert interpretation["architectural_observation"]["visible_floors"].get(
        "count") == EXPECTED_FLOORS[case]


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_p3_space_types_are_unchanged(case):
    interpretation = ArchitecturalVisionInterpreterV1().interpret(
        _understanding(case))

    assert interpretation["space_type"] == EXPECTED_SPACE_TYPE[case]
