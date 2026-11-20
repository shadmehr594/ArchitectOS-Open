# -*- coding: utf-8 -*-
"""CHAT_OBSERVATION_ATTRIBUTION_PARITY_V1 — focused CPU tests.

THE ASYMMETRY
-------------
Two projections read the same saved `provider_candidates`:

  * `image_understanding_v1._build_bridge_understanding` admits an ASSERTED
    UNVERIFIED claim whose verifier reason is EITHER
    `no_applicable_independent_corroboration` OR `claim_properties_not_verified`
    into `architectural_elements` — the band the report layer reads.

  * `vision_observation_mode_v1.build_observation` — the chat observation
    path — re-derives its own attributed band from the same candidates but
    admitted ONLY the first reason. A descriptive architectural claim
    ("top level has arched-top windows", "dark main door") therefore reached
    the report layer and not the chat layer.

WHAT THIS FILE PINS
-------------------
Eligible descriptive claims are retained in the chat band at the SAME lower
trust level — never promoted, never grounded, never given local evidence.
The exclusions the band already enforced (ambiguity, negation, interpretation,
unknowns, rejected claims, unsupported counts) must stay exactly as they are.

The tests call the REAL production functions. No reimplementation of the
attribution algorithm, no model call, no GPU.
"""

import json
import os

import pytest

from core.chat.response_adapter import ResponseAdapter
from core.vision.architectural_vision_interpreter_v1 import (
    ArchitecturalVisionInterpreterV1,
)
from core.vision.image_understanding_v1 import _build_bridge_understanding
from core.vision.vision_observation_mode_v1 import build_observation


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORPUS = os.path.join(ROOT, "runs", "vision_finished_facade_acceptance_v1")

FACADE_DIRS = {
    "A": "A_neue_nationalgalerie_2022",
    "B": "B_ref_10",
    "C": "C_ref_14",
    "D": "D_upload_042039a7_003",
}

CORROBORATION = "no_applicable_independent_corroboration"

DESCRIPTIVE = "claim_properties_not_verified"

#: Reasons that must NEVER admit a claim into the positive attributed band.
FORBIDDEN_REASONS = (
    "unknown_preserved",
    "negative_claim_requires_explicit_local_absence",
    "interpretation_is_not_observation",
    "numeric_category_mismatch",
    "verification_failed",
)

#: The descriptive claims the retention milestone proved are in the record and
#: that the report layer already carries as architectural elements.
DESCRIPTIVE_CLAIMS = {
    "A": [
        "slender, dark, square\u2011section columns",
    ],
    "B": [
        "Multiple large projecting columns/pilasters with simple block capitals "
        "and paneled/fluted shafts supporting the balcony and roof overhang",
    ],
    "C": [
        "to its right a small arched window with metal grille",
        "three stacked levels, each with a dark\u2011glazed rectangular window "
        "behind a projecting balcony and a smaller rectangular window to the "
        "right of it",
        "top level has arched\u2011top (round\u2011headed) windows",
        "the two lower upper levels have rectangular double\u2011pane windows",
        "rectangular windows flanking the central pedimented bay",
        "Pilasters/columns with capitals at corners and flanking the central bay",
    ],
    "D": [
        "brick piers/columns",
        "dark\u2011framed glass doors",
        "dark main door",
        "tall arched window",
        "tall narrow window",
        "projecting bay\u2011like window groups",
    ],
}

#: Attributed-band size after parity. Frozen so that neither a lost
#: corroboration claim nor an uncontrolled addition can pass unnoticed.
#:
#: CHAT_OBSERVATION_PRESENTATION_POLARITY_V1 re-baselined these from
#: 17 / 22 / 17 / 45 after the positive band was restricted to affirmative
#: presence. The exact entries removed were the eight ABSENT claims recorded
#: below (A 3, B 3, C 1, D 1); nothing else changed. They are not lost — each
#: is published in `reported_absences`.
EXPECTED_BAND_SIZE = {"A": 14, "B": 19, "C": 16, "D": 44}

#: A corroboration-only claim per facade — the pre-existing behaviour that must
#: not change.
CORROBORATION_SAMPLE = {
    "A": "floor\u2011to\u2011ceiling glass curtain wall",
    "B": "Two storeys visible",
    "C": "Tall, narrow, multi\u2011storey building clad in light beige/cream "
         "stone or rendered masonry with horizontal rustication lines",
    "D": "exposed red\u2011brown brick masonry",
}

#: The accepted architectural baseline (see the baseline-migration report).
EXPECTED_SPACE_TYPE = {"A": "unknown", "B": "facade", "C": "unknown", "D": "entrance"}

EXPECTED_FLOORS = {"A": 1, "B": 2, "C": None, "D": 2}

EXPECTED_ELEMENTS = {"A": 5, "B": 15, "C": 15, "D": 19}

#: CHAT_OBSERVATION_PRESENTATION_POLARITY_V1 closed the pre-existing polarity
#: leak that this file used to freeze. The positive band admitted claims whose
#: polarity was ABSENT (A 3, B 3, C 1, D 1) because it gated on state, reason
#: and certainty but never on polarity. Those eight claims are now published in
#: `reported_absences` instead. The expected leakage is therefore ZERO, and any
#: future change that reintroduces one fails here.
EXPECTED_ABSENT_BAND_MEMBERS = {"A": 0, "B": 0, "C": 0, "D": 0}


def _load(case, name="03_understanding.json"):
    with open(os.path.join(CORPUS, FACADE_DIRS[case], name), encoding="utf-8") as fh:
        return json.load(fh)


def _understanding(case):
    """Replay the saved bridge payload through the REAL adapter.

    The whole saved record is passed so `generation_status` survives the
    replay; dropping it produces false incomplete-generation warnings.
    """

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


def _band(case):
    return _observation(case).get("attributed_elements") or []


def _band_names(case):
    return [entry.get("name") for entry in _band(case)]


def _candidates(case):
    return [c for c in _understanding(case).get("provider_candidates") or []
            if isinstance(c, dict)]


def _chat_text(case, language="en"):
    """The user-facing text, produced by the real response adapter."""

    observation = _observation(case, language)

    result = {
        "type": "image_observation",
        "engine": "vision+observation_mode",
        "result": observation,
        "observation": observation,
        "status": "success",
        "language": {
            "input_language": "english",
            "output_language": "english" if language == "en" else "persian",
            "guard_status": "not_applicable",
            "corrected": False,
        },
    }

    return ResponseAdapter().build_message(result)


# ==========================================================
# A — DESCRIPTIVE RETENTION
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_a1_descriptive_claims_reach_the_attributed_band(case):
    """An ASSERTED UNVERIFIED claim rejected only for DESCRIBING instead of
    naming must be published in the chat band, not silently dropped."""

    names = _band_names(case)

    for phrase in DESCRIPTIVE_CLAIMS[case]:

        assert phrase in names, (
            case + ": a descriptive architectural claim never reached the chat "
            "observation band: " + phrase)


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_a2_the_band_size_is_the_accepted_one(case):
    """Neither a lost corroboration claim nor an uncontrolled addition."""

    assert len(_band(case)) == EXPECTED_BAND_SIZE[case], (
        case + ": attributed band size changed")


def test_a3_the_band_is_not_empty_for_architectural_facades():
    """The band exists precisely so a facade whose evidence is provider-asserted
    does not render as 'no visible element was reported'."""

    for case in sorted(FACADE_DIRS):

        assert _band(case), case + ": the attributed band is empty"


# ==========================================================
# B — EXISTING BEHAVIOUR MUST NOT CHANGE
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_b1_corroboration_only_claims_are_still_published(case):
    """The reason the band originally admitted keeps working, unchanged."""

    assert CORROBORATION_SAMPLE[case] in _band_names(case), (
        case + ": a pre-existing attributed claim was lost")


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_b2_every_band_member_is_asserted_and_unverified(case):
    """Widening the reason set must not widen the trust gate."""

    for entry in _band(case):

        assert entry.get("status") == "reported, not independently confirmed"

        assert entry.get("confidence") == "not confirmed"

        assert entry.get("source") == "provider"

        assert entry.get("verification_reason") in (CORROBORATION, DESCRIPTIVE)


# ==========================================================
# C — CLAIMS THAT MUST STAY OUT
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_c1_forbidden_reasons_never_enter_the_band(case):
    """Unknowns, negated claims, interpretations, numeric mismatches and
    verifier failures are not positive evidence and must stay out."""

    for entry in _band(case):

        assert entry.get("verification_reason") not in FORBIDDEN_REASONS, (
            case + ": a claim with a forbidden reason entered the band: "
            + str(entry.get("name")))


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_c2_ambiguous_and_contradicted_claims_stay_out(case):
    """Only UNVERIFIED claims are eligible; AMBIGUOUS / CONTRADICTED / REJECTED
    states are withheld."""

    names = {name.lower() for name in _band_names(case) if name}

    for candidate in _candidates(case):

        state = candidate.get("state")

        if state in ("AMBIGUOUS", "CONTRADICTED", "REJECTED"):

            text = str(candidate.get("text") or "").strip().lower()

            assert text not in names, (
                case + ": a " + str(state) + " claim entered the band: " + text)


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_c3_the_widening_adds_no_negated_claim(case):
    """Retention must not turn an absence into positive attributed evidence.

    Scope note: the band ALREADY admitted negated claims before this change
    (`PRE_EXISTING_ABSENT_BAND_MEMBERS`, a separate open polarity defect). This
    test asserts the widening adds none — it does not pretend the older leak
    is fixed, and `test_c3b` freezes it so it can neither grow nor be forgotten.
    """

    for phrase in DESCRIPTIVE_CLAIMS[case]:

        for candidate in _candidates(case):

            if candidate.get("text") == phrase:

                assert candidate.get("polarity") != "ABSENT", (
                    case + ": the widening admitted a negated claim: " + phrase)


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_c3b_no_negated_claim_is_in_the_positive_band(case):
    """A stated absence is never a positive attributed observation.

    HISTORY: this test used to FREEZE a known leak — the band admitted claims
    whose polarity was ABSENT because it gated on state, reason and certainty
    but never on polarity, so `no parapet` was published as a reported
    observation. CHAT_OBSERVATION_PRESENTATION_POLARITY_V1 closed it by
    requiring affirmative presence, and moved those claims into
    `reported_absences`. The expectation is now ZERO, and it fails if any
    future change puts a negated claim back into the positive band.
    """

    absent_texts = {
        str(c.get("text") or "").strip().lower()
        for c in _candidates(case)
        if c.get("polarity") == "ABSENT"
    }

    leaked = [name for name in _band_names(case)
              if name and name.lower() in absent_texts]

    assert len(leaked) == EXPECTED_ABSENT_BAND_MEMBERS[case], (
        case + ": negated claims are back in the positive band: " + repr(leaked))

    assert leaked == [], case + ": zero negated claims expected in the band"


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_c4_no_floor_kind_is_added_by_the_widening(case):
    """Retention must not let a descriptive claim become a storey reading.

    A window claim may *mention* levels ("three stacked levels, each with a
    window"); what it may not do is enter the band as a FLOOR element. The
    authoritative count is guarded separately by `test_f3`.
    """

    for phrase in DESCRIPTIVE_CLAIMS[case]:

        entries = [e for e in _band(case) if e.get("name") == phrase]

        assert entries, case + ": claim absent from the band: " + phrase

        kinds = entries[0].get("kind") or []

        if isinstance(kinds, str):

            kinds = [kinds]

        assert not (set(kinds) & {"floor", "storey", "story", "level"}), (
            case + ": a retained claim entered the band as a floor reading: "
            + phrase)


# ==========================================================
# D — TRUST PRESERVATION
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_d1_retained_claims_keep_their_lower_trust(case):
    """Inclusion in the chat band is not verification."""

    for phrase in DESCRIPTIVE_CLAIMS[case]:

        entry = next(e for e in _band(case) if e.get("name") == phrase)

        assert entry.get("confidence") == "not confirmed"

        assert entry.get("status") == "reported, not independently confirmed"

        assert entry.get("evidence_class") == "provider observation (unconfirmed)"

        assert entry.get("source") == "provider"

        assert entry.get("verification_reason") == DESCRIPTIVE

        # the evidence quote is the provider's own wording, never a rewrite
        assert entry.get("evidence")


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_d2_the_band_never_contains_confirmed_evidence(case):
    """No band member may come from the independently corroborated path."""

    confirmed = {
        str(c.get("text") or "").strip()
        for c in _candidates(case)
        if c.get("state") == "CONFIRMED"
    }

    for entry in _band(case):

        assert entry.get("name") not in confirmed, (
            case + ": a CONFIRMED claim was published in the attributed band")


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_d3_no_band_member_carries_local_evidence(case):
    """The chat band is provider-attributed evidence; local corroboration is
    what would make it CONFIRMED, so it must be empty here."""

    names = {e.get("name") for e in _band(case)}

    for candidate in _candidates(case):

        if candidate.get("text") in names:

            verification = candidate.get("verification") or {}

            assert not verification.get("local_evidence"), (
                case + ": a band member carries local evidence")

            assert candidate.get("grounded") is False, (
                case + ": a band member is grounded")


# ==========================================================
# E — CHAT / REPORT PARITY
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_e1_every_descriptive_claim_the_report_carries_the_chat_band_carries(
        case):
    """The parity that matters: evidence must not disappear because the user
    viewed it through chat instead of the report."""

    interpretation = ArchitecturalVisionInterpreterV1().interpret(
        _understanding(case))

    report_phrases = {
        entry.get("evidence_phrase")
        for entry in interpretation["architectural_observation"]
        ["architectural_elements"]
    }

    names = set(_band_names(case))

    for phrase in DESCRIPTIVE_CLAIMS[case]:

        assert phrase in report_phrases, (
            case + ": the report layer lost a descriptive claim")

        assert phrase in names, (
            case + ": the report carries this claim but chat does not: " + phrase)


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_e2_the_user_facing_text_carries_the_claims_with_uncertainty(case):
    """End to end through the real response adapter: the user can read what the
    model reported, and is told it is unverified."""

    text = _chat_text(case)

    for phrase in DESCRIPTIVE_CLAIMS[case]:

        assert phrase in text, (
            case + ": the user-facing chat text does not mention: " + phrase)

    assert "unverified" in text


def test_e3_the_persian_chat_text_is_not_silently_empty():
    """The chat path supports Persian; the claims must survive that route too."""

    text = _chat_text("C", "fa")

    for phrase in DESCRIPTIVE_CLAIMS["C"]:

        assert phrase in text, "fa: the chat text does not mention: " + phrase


# ==========================================================
# F — GENUINE REGRESSION CONTROLS
# ==========================================================


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_f1_space_type_is_unchanged(case):
    """The chat contract never classifies, and the architectural layer keeps
    the accepted classification."""

    interpretation = ArchitecturalVisionInterpreterV1().interpret(
        _understanding(case))

    assert interpretation["space_type"] == EXPECTED_SPACE_TYPE[case]

    assert _observation(case)["space_type"] is None, (
        case + ": the chat observation contract must not publish a space type")


def test_f2_facade_c_is_not_a_balcony_scene():
    interpretation = ArchitecturalVisionInterpreterV1().interpret(
        _understanding("C"))

    assert interpretation["space_type"] != "balcony"


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_f3_no_floor_is_invented(case):
    """The authoritative storey count is owned by the architectural layer; the
    chat observation contract deliberately carries no floor field, so retention
    cannot inflate one."""

    interpretation = ArchitecturalVisionInterpreterV1().interpret(
        _understanding(case))

    floors = interpretation["architectural_observation"]["visible_floors"]

    assert floors.get("count") == EXPECTED_FLOORS[case]

    assert "visible_floors" not in _observation(case), (
        case + ": the chat contract must not publish an authoritative floor count")


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_f4_the_element_count_is_not_inflated_by_the_chat_path(case):
    interpretation = ArchitecturalVisionInterpreterV1().interpret(
        _understanding(case))

    assert len(interpretation["architectural_observation"]
               ["architectural_elements"]) == EXPECTED_ELEMENTS[case]


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_f5_negative_observations_remain_negative(case):
    """An absence stays an absence: it may never enter the strict `elements`
    band as visible evidence."""

    interpretation = ArchitecturalVisionInterpreterV1().interpret(
        _understanding(case))

    negatives = interpretation["architectural_observation"][
        "negative_observations"]

    for entry in negatives:

        assert entry.get("status") == "absent"

    visible = {e.get("evidence_phrase") for e in _observation(case)["elements"]}

    for entry in negatives:

        assert entry.get("evidence_phrase") not in visible, (
            case + ": a negated observation was published as visible evidence")


@pytest.mark.parametrize("case", sorted(FACADE_DIRS))
def test_f6_duplicate_provider_paths_do_not_duplicate_band_entries(case):
    """A phrase asserted through two provider paths is one observation."""

    names = [name for name in _band_names(case) if name]

    lowered = [name.lower() for name in names]

    assert len(set(lowered)) == len(lowered), (
        case + ": the same claim was published twice")
