# -*- coding: utf-8 -*-
"""DESCRIPTIVE_ARCHITECTURAL_CLAIM_RETENTION_V1 — focused CPU tests.

THE DEFECT
----------
`provider_candidate_verification_v1._decision()` returns
`("UNVERIFIED", "claim_properties_not_verified", [])` for a claim whose
`text` is not literally the kind name — i.e. for every DESCRIPTIVE claim:

    "top level has arched-top (round-headed) windows"     kind=window

Those claims are well-formed: the kind is a recognised architectural kind, the
certainty is ASSERTED, the quote carries no negation, and the claim carries no
total count. They are rejected only because they describe rather than name.

The attributed band in `image_understanding_v1.py` then admits exactly ONE
verification reason — `no_applicable_independent_corroboration` — so every
descriptive claim falls through both bands and never reaches
`architectural_elements`, the field the architectural observation consumes.

WHAT THIS FILE PINS
-------------------
* the descriptive claims exist in saved provider evidence, correctly typed;
* the verifier's own verdict and reason are unchanged by this milestone;
* retention puts them in the ATTRIBUTED band only — never CONFIRMED;
* `grounded` stays False and no independent evidence is invented;
* negated, ambiguous, unknown, interpretation and rejected claims stay out;
* floor counts, furniture controls and negative observations do not move.

RED before the production edit, GREEN after.

CPU only. No model call. No GPU. No render. No file is modified.
"""

import json
import os

import pytest

from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
from core.vision.image_understanding_v1 import build_understanding
from core.vision.observation_normalizer_v1 import parse_normalization


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORPUS = os.path.join(ROOT, "runs", "vision_finished_facade_acceptance_v1")

FACADES = {
    "A": os.path.join(CORPUS, "A_neue_nationalgalerie_2022"),
    "B": os.path.join(CORPUS, "B_ref_10"),
    "C": os.path.join(CORPUS, "C_ref_14"),
    "D": os.path.join(CORPUS, "D_upload_042039a7_003"),
}

#: The exact reasons the verifier can return. Only the two below are
#: attributable provider evidence; everything else stays out.
ATTRIBUTABLE_REASONS = {
    "no_applicable_independent_corroboration",
    "claim_properties_not_verified",
}

#: Reasons that must NEVER reach the attributed band.
NON_ATTRIBUTABLE_REASONS = (
    "unknown_preserved",
    "observer_ambiguity_preserved",
    "interpretation_is_not_observation",
    "negative_claim_requires_explicit_local_absence",
    "total_count_not_independently_established",
    "numeric_category_mismatch",
    "claimed_absence_conflicts_with_local_presence",
)


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _understanding(facade):
    """Run the CURRENT CPU chain on saved evidence, preserving provenance.

    `generation_status` is carried on `raw_observer` because
    `build_understanding` reads it from there. Omitting it produces a FALSE
    "visual observer generation incomplete" unknown — an audit-harness
    artifact recorded in the coverage audit, not a product behaviour.
    """
    folder = FACADES[facade]
    observer = _load(os.path.join(folder, "01_raw_observer.json"))
    normalizer = _load(os.path.join(folder, "02_normalizer.json"))

    diagnostics = {}
    structured = parse_normalization(
        normalizer["raw_text"], observer["raw_text"], diagnostics=diagnostics)

    normalization = {
        "status": "NORMALIZED",
        "structured": structured,
        "source_resolution_failures": diagnostics.get("source_resolution_failures") or [],
        "source_resolutions": diagnostics.get("source_resolutions") or [],
        "accepted_claim_count": diagnostics.get("accepted_claim_count"),
        "rejected_claim_count": diagnostics.get("rejected_claim_count"),
    }

    return build_understanding(
        {"contract": BRIDGE_CONTRACT,
         "raw_observer": {
             "raw_text": observer["raw_text"],
             "generation_status": observer.get("generation_status"),
             "done_reason": observer.get("done_reason"),
             "raw_truncated": observer.get("raw_truncated"),
             "provider": observer.get("provider"),
             "model": observer.get("model"),
             "observer_version": observer.get("observer_version"),
             "diagnostics": observer.get("diagnostics"),
         },
         "normalization": normalization},
        provider="ollama",
        model=normalizer.get("model") or "unknown",
        image_id=os.path.basename(folder),
        source_type="other",
    )


def _candidates(understanding):
    return understanding.get("provider_candidates") or []


def _by_text(understanding, needle):
    return [c for c in _candidates(understanding)
            if needle.casefold() in str(c.get("text") or "").casefold()]


def _architectural_elements(understanding):
    return understanding.get("architectural_elements") or []


def _attributed_texts(understanding):
    return understanding.get("observed_attributed") or []


def _retainable(understanding, kind):
    """Descriptive claims of `kind` that the safety classifier still admits.

    A claim can be UNVERIFIED / `claim_properties_not_verified` and STILL be
    correctly rejected — `classify_claim()` refuses unsupported orientation
    inference, for example. Those rejections are pre-existing policy and this
    milestone must not overturn them. They are excluded from the retention
    expectation and asserted separately below.
    """
    from core.vision.image_understanding_v1 import classify_claim

    return [c for c in _candidates(understanding)
            if c.get("kind") == kind
            and (c.get("verification") or {}).get("reason")
            == "claim_properties_not_verified"
            and classify_claim(str(c.get("text") or ""))[0] != "reject"]


def _classifier_rejected(understanding, kind):
    from core.vision.image_understanding_v1 import classify_claim

    return [c for c in _candidates(understanding)
            if c.get("kind") == kind
            and (c.get("verification") or {}).get("reason")
            == "claim_properties_not_verified"
            and classify_claim(str(c.get("text") or ""))[0] == "reject"]


# ======================================================================
# 1. the defect itself — descriptive claims must exist AND be excluded
# ======================================================================

def test_c_descriptive_window_claim_exists_in_saved_evidence():
    understanding = _understanding("C")

    hits = _by_text(understanding, "arched")

    assert hits, "the descriptive arched-window claim must exist in provider evidence"

    claim = hits[0]

    assert claim.get("kind") == "window"
    assert claim.get("certainty") == "ASSERTED"
    assert claim.get("state") == "UNVERIFIED"
    assert claim["verification"]["reason"] == "claim_properties_not_verified"
    assert claim.get("grounded") is False


def test_c_descriptive_window_claim_is_retained_as_attributed():
    """RED before the fix: the claim never reaches the attributed band."""
    understanding = _understanding("C")

    attributed = " ".join(_attributed_texts(understanding)).casefold()

    assert "arched" in attributed and "window" in attributed, (
        "the descriptive arched-window claim must be retained as ATTRIBUTED "
        "provider evidence, not dropped"
    )


def test_c_descriptive_window_claim_reaches_architectural_elements():
    understanding = _understanding("C")

    elements = " ".join(_architectural_elements(understanding)).casefold()

    assert "window" in elements, (
        "architectural_elements is the field the observation consumes; a "
        "described window must reach it"
    )


def test_c_all_descriptive_window_claims_are_retained():
    understanding = _understanding("C")

    descriptive = _retainable(understanding, "window")

    assert descriptive, "the saved evidence must contain descriptive window claims"

    attributed = " ".join(_attributed_texts(understanding)).casefold()

    missing = [c["text"] for c in descriptive
               if str(c["text"]).casefold() not in attributed]

    assert missing == [], "descriptive window claims still dropped: %r" % (missing,)


def test_c_the_duplication_is_recorded_not_counted_as_windows():
    """Six claims across two category paths are NOT six physical windows."""
    understanding = _understanding("C")

    descriptive = [c for c in _candidates(understanding)
                   if c.get("kind") == "window"
                   and c["verification"].get("reason") == "claim_properties_not_verified"]

    distinct_texts = {str(c["text"]) for c in descriptive}

    assert len(distinct_texts) < len(descriptive), (
        "the same claim is expected on more than one category path"
    )

    categories = {c.get("category") for c in descriptive}

    assert len(categories) > 1, (
        "duplication arises from multiple categories: %r" % (categories,)
    )


# ======================================================================
# 2. facade D — doors
# ======================================================================

def test_d_descriptive_door_claims_are_retained():
    understanding = _understanding("D")

    doors = _retainable(understanding, "door")

    assert doors, "the saved evidence must contain descriptive door claims"

    attributed = " ".join(_attributed_texts(understanding)).casefold()

    missing = [c["text"] for c in doors if str(c["text"]).casefold() not in attributed]

    assert missing == [], "descriptive door claims still dropped: %r" % (missing,)


def test_d_reports_whether_a_typed_window_candidate_exists():
    """Recorded, not asserted either way — the test must not invent one."""
    understanding = _understanding("D")

    windows = [c for c in _candidates(understanding) if c.get("kind") == "window"]

    # Documented outcome, whatever it is: this milestone must not fabricate a
    # window claim to make a test pass.
    assert isinstance(windows, list)

    if not windows:
        pytest.skip("no typed window candidate exists on facade D — "
                    "remaining window classification gap, recorded in the report")


# ======================================================================
# 3. facade B — fluted columns
# ======================================================================

def test_b_descriptive_column_claim_is_retained():
    understanding = _understanding("B")

    columns = _retainable(understanding, "column")

    assert columns, "the saved evidence must contain a retainable descriptive column claim"

    attributed = " ".join(_attributed_texts(understanding)).casefold()

    missing = [c["text"] for c in columns if str(c["text"]).casefold() not in attributed]

    assert missing == [], "descriptive column claims still dropped: %r" % (missing,)


def test_b_the_claim_wording_is_preserved_verbatim():
    understanding = _understanding("B")

    columns = _retainable(understanding, "column")

    assert columns

    attributed = _attributed_texts(understanding)

    for claim in columns:
        assert claim["text"] in attributed, (
            "retention must keep the observer's own wording, not a rewrite: %r"
            % (claim["text"],)
        )


def test_b_orientation_rejected_claims_stay_rejected():
    """A pre-existing safety rejection must survive this milestone.

    "two front corner columns, two mid columns, and at least one rear column"
    is `claim_properties_not_verified` but `classify_claim()` refuses it as
    `unsupported_orientation`. Retention must not overturn that.
    """
    understanding = _understanding("B")

    rejected = _classifier_rejected(understanding, "column")

    assert rejected, "the orientation claim is expected in the saved evidence"

    attributed = set(_attributed_texts(understanding))

    for claim in rejected:
        assert claim["text"] not in attributed, (
            "a claim rejected by the safety classifier must not be attributed: %r"
            % (claim["text"],)
        )


# ======================================================================
# 4. facade A — square-section columns
# ======================================================================

def test_a_descriptive_column_claim_is_retained():
    understanding = _understanding("A")

    columns = _retainable(understanding, "column")

    assert columns, "the saved evidence must contain descriptive column claims"

    attributed = " ".join(_attributed_texts(understanding)).casefold()

    missing = [c["text"] for c in columns if str(c["text"]).casefold() not in attributed]

    assert missing == [], "descriptive column claims still dropped: %r" % (missing,)


# ======================================================================
# 5. trust boundary — the core acceptance requirement
# ======================================================================

@pytest.mark.parametrize("facade", sorted(FACADES))
def test_retention_never_promotes_a_claim(facade):
    """A retained claim must stay UNVERIFIED, ungrounded, reason intact."""
    understanding = _understanding(facade)

    for claim in _candidates(understanding):
        reason = (claim.get("verification") or {}).get("reason")

        if reason != "claim_properties_not_verified":
            continue

        assert claim.get("state") == "UNVERIFIED", (
            "retention must not change the verification state: %r" % (claim,)
        )
        assert claim.get("grounded") is False, (
            "a descriptive claim must never become grounded: %r" % (claim,)
        )
        assert claim["verification"].get("local_evidence") == [], (
            "no independent evidence may be invented: %r" % (claim,)
        )


@pytest.mark.parametrize("facade", sorted(FACADES))
def test_confirmed_semantics_are_unchanged(facade):
    """CONFIRMED remains reserved for independently corroborated claims."""
    understanding = _understanding(facade)

    for claim in _candidates(understanding):
        if claim.get("state") != "CONFIRMED":
            continue

        assert claim["verification"].get("reason") == "independent_local_type_presence"
        assert claim.get("grounded") is True


@pytest.mark.parametrize("facade", sorted(FACADES))
def test_non_attributable_reasons_never_reach_the_attributed_band(facade):
    understanding = _understanding(facade)

    attributed = set(_attributed_texts(understanding))

    for claim in _candidates(understanding):
        reason = (claim.get("verification") or {}).get("reason")

        if reason not in NON_ATTRIBUTABLE_REASONS:
            continue

        assert claim["text"] not in attributed, (
            "reason %r must not be attributed: %r" % (reason, claim["text"])
        )


@pytest.mark.parametrize("facade", sorted(FACADES))
def test_rejected_and_ambiguous_claims_stay_out(facade):
    understanding = _understanding(facade)

    attributed = set(_attributed_texts(understanding))

    for claim in _candidates(understanding):
        if claim.get("state") in ("AMBIGUOUS", "REJECTED", "CONTRADICTED"):
            assert claim["text"] not in attributed, (
                "%s claim must not be attributed: %r"
                % (claim.get("state"), claim["text"])
            )


@pytest.mark.parametrize("facade", sorted(FACADES))
def test_every_attributed_claim_carries_an_attributable_reason(facade):
    understanding = _understanding(facade)

    reasons = {
        str(c["text"]): (c.get("verification") or {}).get("reason")
        for c in _candidates(understanding)
    }

    for text in _attributed_texts(understanding):
        assert reasons.get(text) in ATTRIBUTABLE_REASONS, (
            "attributed claim %r has reason %r" % (text, reasons.get(text))
        )


# ======================================================================
# 6. invariants that must not move
# ======================================================================

def test_provider_floor_reading_is_unchanged():
    """The PROVIDER reading must not move.

    `visible_floors_observation.count` is the provider's own claim — 4 on
    facade C. The AUTHORITATIVE `visible_floors.count` is a different field on
    the observation contract and stays `null`; that is asserted in the
    real-image acceptance, not here.
    """
    expected = {"A": 1, "B": 2, "C": 4, "D": 2}

    for facade, count in expected.items():
        understanding = _understanding(facade)
        extras = understanding.get("observation_extras") or {}
        reading = extras.get("visible_floors_observation") or {}

        assert reading.get("count") == count, (
            "facade %s provider floor reading moved: %r"
            % (facade, reading.get("count"))
        )

        assert reading.get("authoritative") is False, (
            "facade %s provider floor reading must stay non-authoritative" % facade
        )


def test_no_unknowns_are_invented():
    for facade in FACADES:
        understanding = _understanding(facade)

        texts = json.dumps(understanding.get("unresolved") or []).casefold()

        assert "generation incomplete" not in texts, (
            "facade %s reports a false incomplete-generation unknown" % facade
        )


def test_descriptive_claims_are_asserted_not_ambiguous():
    """The retention band is for ASSERTED observations only."""
    for facade in FACADES:
        understanding = _understanding(facade)

        for claim in _candidates(understanding):
            if claim["verification"].get("reason") != "claim_properties_not_verified":
                continue

            assert claim.get("certainty") == "ASSERTED", claim
