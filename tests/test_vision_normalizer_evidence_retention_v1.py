# -*- coding: utf-8 -*-
"""VISION_NORMALIZER_EVIDENCE_RETENTION_V1 — focused CPU tests.

THE DEFECT
----------
Facade D's observer text states TWO coordinated negations:

    no parapet, roof terrace, or occupiable attic storey is visible
    no visible external stairs, balconies, or vertical‑circulation elements

The model distributed each one over its items, emitting per-item claims whose
shortened `source_quote` is not a verbatim substring:

    no roof terrace / no occupiable attic storey is visible
    no visible balconies / no visible vertical‑circulation elements

`parse_normalization` rejected all four (`field="source_quote"`,
`reason="no_match"`). Stage-C recovery cannot help: it only handles
`field="text"`, and it refuses anything that states absence. So the observation
kept `no parapet` and `no visible external stairs` — the two items that happened
to be verbatim — and dropped the other four.

That is not merely a loss, it is a DISTORTION: a report that says "no parapet"
while the observer also said "no roof terrace" implies the roof terrace was
checked and found, or was never examined. Neither is what the source says.

WHAT THIS FILE PINS
-------------------
A model-reported absence must survive as an ABSENCE — never as a visible
element, never as verified pixel evidence. The recovery is clause-level: the
verbatim negated clause is the evidence, and it carries every item the observer
listed.

FIXTURES
--------
`runs/vision_finished_facade_acceptance_v1/D_upload_042039a7_003/` — the saved
facade D observer text and model output. The observer text is used IMMUTABLE as
the grounding source; every quote asserted here is a real slice of it.

No model call. No GPU. No render. No prompt change.
"""

import json
import os

import pytest

from core.vision.observation_normalizer_v1 import parse_normalization
from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
from core.vision.image_understanding_v1 import build_understanding
from core.vision.architectural_vision_interpreter_v1 import interpret_architectural_vision


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORPUS = os.path.join(ROOT, "runs", "vision_finished_facade_acceptance_v1")

FACADE_DIRS = {
    "A": "A_neue_nationalgalerie_2022",
    "B": "B_ref_10",
    "C": "C_ref_14",
    "D": "D_upload_042039a7_003",
}

#: The two coordinated negations, verbatim from facade D's observer text.
#: The hyphen in the second one is U+2011, exactly as the source has it.
CLAUSE_ROOF = "no parapet, roof terrace, or occupiable attic storey is visible"
CLAUSE_CIRC = ("no visible external stairs, balconies, or "
               "vertical\u2011circulation elements")

#: The four rejected per-item claims, verbatim from the saved model output.
REJECTED_ITEMS = (
    "no roof terrace",
    "no occupiable attic storey is visible",
    "no visible balconies",
    "no visible vertical\u2011circulation elements",
)


def _load(case, name):
    with open(os.path.join(CORPUS, FACADE_DIRS[case], name), encoding="utf-8") as fh:
        return json.load(fh)


#: VISION_RETENTION_BASELINE_MIGRATION_V1 — the accepted post-retention
#: observation layer, pinned by `test_vision_image_type_medium_handoff_v1`
#: and re-used here so both suites read one baseline instead of two guesses.
RETENTION_BASELINE = os.path.join(
    ROOT, "tests", "fixtures", "vision", "retention_baseline_v1.json")


def _retention_baseline():
    with open(RETENTION_BASELINE, encoding="utf-8") as fh:
        return json.load(fh)


def _observer(case="D"):
    return _load(case, "01_raw_observer.json")


def _saved_normalization(case="D"):
    return _load(case, "02_normalizer.json")


def _normalize(model_json, source_text):
    diagnostics = {}
    structured = parse_normalization(model_json, source_text, diagnostics=diagnostics)
    return structured, diagnostics


def _chain(structured, diagnostics, raw_observer):
    """normalizer output -> real understanding -> real observation."""

    normalization = {
        "status": "NORMALIZED",
        "structured": structured,
        "source_resolution_failures": diagnostics["source_resolution_failures"],
        "source_resolutions": diagnostics.get("source_resolutions") or [],
        "accepted_claim_count": diagnostics["accepted_claim_count"],
        "rejected_claim_count": diagnostics["rejected_claim_count"],
    }

    understanding = build_understanding(
        {"contract": BRIDGE_CONTRACT, "raw_observer": raw_observer,
         "normalization": normalization},
        provider="ollama", model="qwen3.8:27b", image_id="D", source_type="other",
    )

    return understanding, interpret_architectural_vision(understanding)


def _facade_d():
    observer = _observer("D")
    structured, diagnostics = _normalize(
        _saved_normalization("D")["raw_text"], observer["raw_text"])
    return _chain(structured, diagnostics, observer)


def _negatives(interpretation):
    return interpretation["architectural_observation"].get("negative_observations") or []


def _negative_phrases(interpretation):
    return [entry.get("evidence_phrase") for entry in _negatives(interpretation)]


def _visible_phrases(interpretation):
    return [entry.get("evidence_phrase")
            for entry in interpretation["architectural_observation"]
            .get("architectural_elements") or []
            if entry.get("status") == "visible"]


def _unclassified(interpretation):
    return [entry.get("evidence_phrase")
            for entry in interpretation["architectural_observation"]
            .get("unclassified_observations") or []]


def _payload(**slots):
    """The saved facade D structured payload with categories replaced."""

    base = json.loads(json.dumps(_saved_normalization("D")["structured"]))

    for category in ("observed_elements", "walls", "structural_elements",
                     "spatial_relationships", "vertical_circulation"):
        base[category] = []

    base["openings"] = {"doors": [], "windows": [], "other_openings": []}

    for key, value in slots.items():
        base[key] = value

    return base


def _claim(text, kind, quote=None, certainty="ASSERTED", count=None):
    return {"text": text, "source_quote": quote if quote is not None else text,
            "kind": kind, "certainty": certainty, "count": count}


# ==========================================================
# A — the four coordinated negative claims
# ==========================================================


def test_a1_the_roof_terrace_absence_is_preserved():
    _, interpretation = _facade_d()

    phrases = " | ".join(_negative_phrases(interpretation))

    assert "roof terrace" in phrases, (
        "the observer stated 'no parapet, roof terrace, ... is visible' but the "
        "roof terrace absence was dropped")


def test_a2_the_occupiable_attic_storey_absence_is_preserved():
    _, interpretation = _facade_d()

    phrases = " | ".join(_negative_phrases(interpretation))

    assert "attic storey" in phrases, (
        "the observer stated 'no ... occupiable attic storey is visible' but the "
        "attic storey absence was dropped")


def test_a3_the_balcony_absence_is_preserved():
    _, interpretation = _facade_d()

    phrases = " | ".join(_negative_phrases(interpretation))

    assert "balcon" in phrases, (
        "the observer stated 'no visible ... balconies ...' but the balcony "
        "absence was dropped")


def test_a4_the_vertical_circulation_absence_is_preserved():
    _, interpretation = _facade_d()

    phrases = " | ".join(_negative_phrases(interpretation))

    assert "vertical\u2011circulation" in phrases, (
        "the observer stated 'no visible ... vertical-circulation elements' but "
        "that absence was dropped")


@pytest.mark.parametrize("item", REJECTED_ITEMS)
def test_a5_a_negative_item_never_becomes_a_visible_element(item):
    _, interpretation = _facade_d()

    for phrase in _visible_phrases(interpretation):

        assert item.lower() not in phrase.lower(), (
            "an absence was published as a VISIBLE element: " + repr(phrase))


@pytest.mark.parametrize("item", REJECTED_ITEMS)
def test_a6_a_negative_item_is_never_published_as_visible_in_unclassified(item):
    _, interpretation = _facade_d()

    for phrase in _unclassified(interpretation):

        assert item.lower() not in phrase.lower(), (
            "an absence was filed as an unclassified VISIBLE observation: "
            + repr(phrase))


def test_a7_absence_is_recorded_as_absence_not_as_verification():
    """A recorded absence is a model claim, never independent pixel proof."""

    _, interpretation = _facade_d()

    records = [entry for entry in _negatives(interpretation)
               if "roof terrace" in str(entry.get("evidence_phrase", ""))]

    assert records, "no record to inspect"

    for record in records:

        assert record.get("status") == "absent"

        assert record.get("confidence") in ("LOW", "MEDIUM")

        assert record.get("verified") is not True

        assert record.get("grounded") is not True


# ==========================================================
# B — the recessed glazed entry
# ==========================================================


def test_b1_the_recessed_glazed_entry_relation_survives():
    """V7.3 Stage-C already recovers this; it must not regress."""

    understanding, interpretation = _facade_d()

    report = understanding.get("element_evidence_report") or {}

    assert report.get("stage_c_recovered_claims", 0) >= 1

    recovered = [entry for entry in (understanding.get("element_evidence") or {})
                 .get("elements") or [] if entry.get("recovered")]

    assert recovered, "Stage-C recovered nothing from facade D"


def test_b2_the_entry_relation_is_a_real_source_slice():
    observer = _observer("D")

    quote = ("a recessed glazed entry (dark\u2011framed glass doors) under a flat "
             "dark canopy")

    assert quote in observer["raw_text"]


# ==========================================================
# C — the tall arched window above the main door
# ==========================================================


def test_c1_the_arched_window_relation_survives():
    understanding, _ = _facade_d()

    recovered = [entry for entry in (understanding.get("element_evidence") or {})
                 .get("elements") or [] if entry.get("recovered")]

    assert len(recovered) >= 2, (
        "both spatial relations with authentic quotes should be recovered, got "
        + repr(len(recovered)))


def test_c2_the_window_relation_is_a_real_source_slice():
    observer = _observer("D")

    quote = ("a tall arched window with a fanlight\u2011type curved top and dark "
             "mullions above a dark main door")

    assert quote in observer["raw_text"]


# ==========================================================
# D — a genuine source-quote mismatch stays rejected
# ==========================================================


def test_d1_an_unsupported_quotation_is_not_admitted():
    observer = _observer("D")

    structured, diagnostics = _normalize(
        json.dumps(_payload(observed_elements=[
            _claim("underground parking", "parking",
                   quote="a two-level underground parking garage beneath the courtyard"),
        ])),
        observer["raw_text"],
    )

    assert structured["observed_elements"] == []

    assert diagnostics["rejected_claim_count"] == 1

    assert diagnostics["source_resolution_failures"][0]["reason"] == "no_match"


def test_d2_an_unsupported_quote_never_reaches_the_observation():
    observer = _observer("D")

    structured, diagnostics = _normalize(
        json.dumps(_payload(observed_elements=[
            _claim("underground parking", "parking",
                   quote="a two-level underground parking garage beneath the courtyard"),
        ])),
        observer["raw_text"],
    )

    _, interpretation = _chain(structured, diagnostics, observer)

    assert "parking" not in " ".join(_negative_phrases(interpretation)).lower()

    assert "parking" not in " ".join(_visible_phrases(interpretation)).lower()


# ==========================================================
# E — a summary label with an authentic quote
# ==========================================================


def test_e1_a_concise_label_with_a_real_quote_is_recovered():
    """The Stage-C contract, exercised on a real facade D quote."""

    observer = _observer("D")

    structured, diagnostics = _normalize(
        json.dumps(_payload(spatial_relationships=[
            _claim("recessed glazed entry under a flat dark canopy", "relation",
                   quote="a recessed glazed entry (dark\u2011framed glass doors) "
                         "under a flat dark canopy"),
        ])),
        observer["raw_text"],
    )

    assert diagnostics["rejected_claim_count"] == 1

    understanding, _ = _chain(structured, diagnostics, observer)

    assert (understanding.get("element_evidence_report") or {}).get(
        "stage_c_recovered_claims") == 1


# ==========================================================
# F — a fabricated architectural label
# ==========================================================


def test_f1_a_fabricated_label_is_not_recovered_from_another_element():
    """The source mentions a brick arch; it never mentions a bell tower."""

    observer = _observer("D")

    structured, diagnostics = _normalize(
        json.dumps(_payload(spatial_relationships=[
            _claim("bell tower above the brick arch", "relation",
                   quote="two brick arches forming a tall portal on the right"),
        ])),
        observer["raw_text"],
    )

    understanding, _ = _chain(structured, diagnostics, observer)

    assert (understanding.get("element_evidence_report") or {}).get(
        "stage_c_recovered_claims") == 0


def test_f2_a_fabricated_subject_does_not_create_an_absence():
    observer = _observer("D")

    structured, diagnostics = _normalize(
        json.dumps(_payload(observed_elements=[
            _claim("no underground parking", "parking"),
        ])),
        observer["raw_text"],
    )

    _, interpretation = _chain(structured, diagnostics, observer)

    assert "parking" not in " ".join(_negative_phrases(interpretation)).lower()


# ==========================================================
# G — negation is never promoted
# ==========================================================


def test_g1_a_negated_phrase_never_appears_as_a_positive_element():
    _, interpretation = _facade_d()

    visible = " | ".join(_visible_phrases(interpretation)).lower()

    for word in ("parapet", "roof terrace", "attic", "balcon", "circulation",
                 "external stairs"):

        assert word not in visible, (
            "negated subject published as visible: " + word)


def test_g2_every_negative_record_is_marked_absent():
    _, interpretation = _facade_d()

    for record in _negatives(interpretation):

        assert record.get("status") == "absent"


# ==========================================================
# H — duplicate claims do not inflate the element count
# ==========================================================


def test_h1_a_coordinated_clause_is_recorded_once():
    _, interpretation = _facade_d()

    phrases = _negative_phrases(interpretation)

    roof = [p for p in phrases if p and "roof terrace" in p]

    assert len(roof) <= 1, "the same clause was recorded more than once: " + repr(roof)


def test_h2_the_element_count_is_not_inflated():
    """19 counts DISTINCT evidence phrases — not provider paths, not windows.

    VISION_RETENTION_BASELINE_MIGRATION_V1: the pre-retention layer held 13.
    `DESCRIPTIVE_ARCHITECTURAL_CLAIM_RETENTION_V1` admits six descriptive
    claims the observer ASSERTED and the verifier left UNVERIFIED, so the
    accepted count is 19. The count is re-baselined against that exact delta
    only: a lost element, an unrelated addition, a duplicated phrase, a
    promoted claim or an invented floor still fails.
    """

    understanding, interpretation = _facade_d()

    observation = interpretation["architectural_observation"]

    elements = observation["architectural_elements"]

    baseline = _retention_baseline()["facades"]["D"]

    # ---- the accepted count, and the accepted count only -------------------
    assert len(elements) == 19, "the accepted element count is 19, not %d" % len(elements)

    assert len(elements) == baseline["current_element_count"], (
        "the element count does not match the pinned baseline")

    # ---- 13 + 6: the growth is exactly the authorised retention -----------
    retained = {entry["evidence_phrase"] for entry in baseline["retained_delta"]}

    assert len(retained) == 6, "the pinned retention delta is six claims"

    historical = {entry["evidence_phrase"] for entry in baseline["historical_elements"]}

    assert len(historical) == 13, "the pre-retention layer held 13 elements"

    assert baseline["historical_element_count"] == 13

    phrases = [entry["evidence_phrase"] for entry in elements]

    assert set(phrases) - retained == historical, (
        "the element set is not the historical set plus the authorised delta")

    assert retained <= set(phrases), "a retained element is missing from the observation"

    # ---- a duplicate provider path is not a second physical element -------
    assert len(set(phrases)) == len(phrases), (
        "the same evidence phrase was counted more than once")

    # ---- every element is a VISIBLE element, none is an absence -----------
    assert all(entry["status"] == "visible" for entry in elements)

    # ---- retention is not verification ------------------------------------
    candidates = {}

    for candidate in understanding.get("provider_candidates") or []:

        candidates.setdefault(candidate.get("text"), []).append(candidate)

    for phrase in sorted(retained):

        claims = candidates.get(phrase) or []

        assert claims, "no provider claim for a retained element: " + phrase

        assert all(claim.get("state") == "UNVERIFIED" for claim in claims), (
            "a retained claim is not UNVERIFIED: " + phrase)

        assert all(claim.get("grounded") is False for claim in claims), (
            "a retained claim is grounded: " + phrase)

        assert all((claim.get("verification") or {}).get("local_evidence") == []
                   for claim in claims), (
            "a retained claim carries local evidence: " + phrase)

        assert all((claim.get("verification") or {}).get("reason")
                   in ("no_applicable_independent_corroboration",
                       "claim_properties_not_verified") for claim in claims), (
            "a retained claim rests on a non-attributable reason: " + phrase)

    # ---- no floor inflation, no scene-type drift --------------------------
    assert (observation["visible_floors"] or {}).get("count") == 2, (
        "retention must not change the authoritative floor count")

    assert interpretation["space_type"] == "entrance", (
        "retention must not change the scene type")

    assert not any("floor" in (entry.get("kind") or []) for entry in elements
                   if entry["evidence_phrase"] in retained)


# ==========================================================
# I — integrity accounting
# ==========================================================


def test_i1_accepted_plus_rejected_accounts_for_every_claim():
    """The fix REDISTRIBUTES claims between accepted and rejected; it never
    makes a claim vanish. Two items are recovered and two become
    `duplicate_of_recovered_clause`, so the total is conserved at the 65 the
    model produced (59 accepted + 6 rejected in the saved record)."""

    observer = _observer("D")

    structured, diagnostics = _normalize(
        _saved_normalization("D")["raw_text"], observer["raw_text"])

    saved = _saved_normalization("D")

    produced = saved["accepted_claim_count"] + saved["rejected_claim_count"]

    assert (diagnostics["accepted_claim_count"]
            + diagnostics["rejected_claim_count"]) == produced, (
        "every claim the model produced must still be accounted for")


def test_i1b_recovery_moves_claims_rather_than_dropping_them():
    observer = _observer("D")

    _, diagnostics = _normalize(
        _saved_normalization("D")["raw_text"], observer["raw_text"])

    saved = _saved_normalization("D")

    assert diagnostics["accepted_claim_count"] > saved["accepted_claim_count"]

    assert diagnostics["rejected_claim_count"] < saved["rejected_claim_count"]


def test_i1c_a_duplicate_is_recorded_as_covered_not_as_a_mismatch():
    observer = _observer("D")

    _, diagnostics = _normalize(
        _saved_normalization("D")["raw_text"], observer["raw_text"])

    reasons = [entry["reason"] for entry in diagnostics["source_resolution_failures"]]

    assert "duplicate_of_recovered_clause" in reasons


def test_i2_recovery_is_recorded_rather_than_silent():
    """A recovered claim's ORIGINAL model wording stays auditable."""

    observer = _observer("D")

    _, diagnostics = _normalize(
        _saved_normalization("D")["raw_text"], observer["raw_text"])

    recorded = [entry["claim"]["text"]
                for entry in diagnostics.get("source_resolutions") or []]

    assert "no roof terrace" in recorded, (
        "the model's own wording must survive in the audit trail")


def test_i3_a_recovery_never_claims_verbatim_text():
    """Every admitted quote must still be a real slice of the source."""

    observer = _observer("D")

    structured, _ = _normalize(
        _saved_normalization("D")["raw_text"], observer["raw_text"])

    def walk(category, claim):
        assert claim["source_quote"] in observer["raw_text"], (
            "admitted quote is not a source slice: " + repr(claim["source_quote"]))
        assert claim["text"] in claim["source_quote"], (
            "admitted text is not inside its own quote: " + repr(claim["text"]))

    for category in ("observed_elements", "walls", "structural_elements",
                     "spatial_relationships", "vertical_circulation"):

        for claim in structured[category]:
            walk(category, claim)

    for category, claims in structured["openings"].items():
        for claim in claims:
            walk(category, claim)


# ==========================================================
# J — A/B/C are untouched
# ==========================================================


@pytest.mark.parametrize("case", ("A", "B", "C"))
def test_j1_no_rejection_appears_on_the_other_facades(case):
    observer = _observer(case)

    _, diagnostics = _normalize(
        _saved_normalization(case)["raw_text"], observer["raw_text"])

    assert diagnostics["rejected_claim_count"] == 0


@pytest.mark.parametrize("case", ("A", "B", "C"))
def test_j2_the_accepted_claim_count_is_unchanged(case):
    observer = _observer(case)

    _, diagnostics = _normalize(
        _saved_normalization(case)["raw_text"], observer["raw_text"])

    assert diagnostics["accepted_claim_count"] == \
        _saved_normalization(case)["accepted_claim_count"]
