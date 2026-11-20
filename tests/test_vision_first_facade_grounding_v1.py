# -*- coding: utf-8 -*-
"""VISION_FIRST_FACADE_GROUNDING_V1 — focused CPU tests.

Four confirmed defects, each measured on the authentic live v1.3 record for the
acceptance facade (`runs/r2_live_normalizer_v13/eye_V3_v13.json`, image sha
`ae77532b…`, 768x704). No Ollama, no GPU, no ComfyUI: every fixture is a saved
record replayed through the production chain.

  1. The storey reading and the observation list reached the user correctly
     (this is asserted as an INVARIANT, so a later change cannot silently
     regress it) — see `test_storey_count_reaches_the_user`.
  2. A Persian report carried an ENGLISH sentence, and that sentence
     contradicted the observation list printed directly below it.
  3. A restricted negation ("no visible columns OTHER THAN the ground-floor
     piers") was rendered as an absolute one ("no visible columns"), so the
     report denied columns it had just described as visible.
  4. The same observation was printed twice, once truncated.

Nothing here asserts a *visual* result. A PASS means the plumbing is correct;
it does NOT mean the vision model was verified on this image.
"""

import json
import os
import re

import pytest

from core.vision.architectural_observation_v1 import build_architectural_observation
from core.vision.architectural_vision_interpreter_v1 import interpret_architectural_vision
from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
from core.vision.image_understanding_v1 import build_understanding
from core.vision.vision_report_v1 import render_vision_report


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

V3_RECORD = os.path.join(ROOT, "runs", "r2_live_normalizer_v13", "eye_V3_v13.json")

EXPECTED_SHA = "ae77532be8dd80bbf35af1a04136b86d1689f9b0845b50325f0e4c8a5cde1ab4"

#: The exact sentence the interpreter emits when nothing was independently
#: corroborated. It is the one that leaked into Persian untranslated.
NO_EVIDENCE_REASON = "reliable architectural evidence has not been established"

#: The header the facade report prints before the model's own observations.
OBSERVATION_HEADER = "مشاهدات معماری مدل"


def _record():
    with open(V3_RECORD, encoding="utf-8") as fh:
        return json.load(fh)


def _chain():
    """The production chain: bridge -> understanding -> interpretation."""

    record = _record()

    understanding = build_understanding(
        {"contract": BRIDGE_CONTRACT,
         "raw_observer": record["raw_observer"],
         "normalization": record["normalization"]},
        provider="ollama", model="qwen3.8:27b", image_id="V3", source_type="other")

    return understanding, interpret_architectural_vision(understanding)


def _report(language="fa"):
    _, interpretation = _chain()
    return interpretation, render_vision_report(interpretation, language)


# ==========================================================
# A. Source identity — the fixture is the accepted image
# ==========================================================


def test_fixture_is_the_accepted_original():
    """E/F — the record belongs to the original facade, not a generated output."""

    record = _record()

    assert record["image"]["sha256"] == EXPECTED_SHA
    assert record["image"]["digest_ok"] is True
    assert record["image"]["dimensions"] == [768, 704]


# ==========================================================
# B. Invariants that must not regress
# ==========================================================


def test_storey_count_reaches_the_user():
    """G — a validly observed count is spoken, not withheld."""

    _, report = _report("fa")

    assert "4 طبقهٔ قابل مشاهده" in report
    assert "3 طبقهٔ بالایی" in report
    # The contradicted line is withheld from the RENDERED body only.
    assert "تعداد دقیق طبقات" not in report


def test_verified_floors_stays_null_so_no_render_pass_is_possible():
    """The observation is attributed, never promoted to verified geometry."""

    _, interpretation = _chain()

    observation = interpretation["architectural_observation"]
    assert observation["visible_floors"] is None

    reading = observation["visible_floors_observation"]
    assert reading["count"] == 4
    assert reading["trust_tier"] == "PROVIDER_OBSERVATION"
    assert reading["verification"] == "UNVERIFIED"
    assert reading["authoritative"] is False
    assert reading["confidence"] == "LOW"


def test_passage_is_never_reported_as_an_enclosed_room():
    """H — an open through-passage is not converted into an enclosed space."""

    _, report = _report("fa")

    assert "open through" in report.lower()
    assert "فضای بسته" not in report


def test_observation_stays_separate_from_interpretation():
    """A — the two modes keep their own contract keys."""

    _, interpretation = _chain()

    assert isinstance(interpretation.get("observed_elements"), list)
    assert isinstance(interpretation.get("architectural_interpretation"), list)
    # An interpretation line must never be echoed as a directly observed fact.
    observed = {str(item).lower() for item in interpretation["observed_elements"]}
    for line in interpretation.get("architectural_interpretation") or []:
        assert str(line).lower() not in observed


# ==========================================================
# C. Defect 2 — English sentence, and the contradiction
# ==========================================================


def test_persian_report_carries_no_untranslated_meta_unknown():
    """A Persian answer must not contain the raw English reason."""

    _, report = _report("fa")

    assert NO_EVIDENCE_REASON not in report, (
        "an English sentence is being rendered into a Persian report:\n" + report)


def test_report_does_not_deny_evidence_it_is_printing():
    """The report must not say no evidence exists while listing observations."""

    _, report = _report("fa")

    assert OBSERVATION_HEADER in report, "precondition: observations are rendered"
    assert NO_EVIDENCE_REASON not in report
    assert "شواهد معماری قابل اعتمادی" not in report


def test_contract_keeps_the_unknown_even_though_the_report_withholds_it():
    """The withhold is a RENDERING decision; the contract stays honest."""

    _, interpretation = _chain()

    assert NO_EVIDENCE_REASON in (interpretation.get("unknowns") or [])


def test_no_observation_still_admits_that_nothing_was_established():
    """The withhold must be conditional, not a blanket suppression."""

    interpretation = interpret_architectural_vision(
        {"image_type": "unknown", "observed": [], "inferred": [],
         "unresolved": [], "architectural_elements": [],
         "text_labels_if_visible": [], "confidence": "LOW"},
        ground=False,
    )

    report = render_vision_report(interpretation, "fa")

    assert NO_EVIDENCE_REASON not in report, "no English in a Persian report"
    assert "قابل اعتماد" in report or "قابل تعیین" in report, (
        "with nothing observed the report must still admit it:\n" + report)


# ==========================================================
# D. Defect 3 — restricted negation rendered as absolute
# ==========================================================


def _mixed_observation():
    return build_architectural_observation(
        {"observed": ["no visible columns other than the ground-floor piers of "
                      "the arcade"],
         "confidence": "LOW"},
        provider="ollama", model="qwen3.8:27b", image_id="synthetic",
        source_type="other",
    )


def test_absence_fragment_keeps_the_restrictive_qualifier():
    """'other than the piers' restricts the negation and must survive."""

    observation = _mixed_observation()

    fragments = [
        fragment
        for entry in observation.get("negative_observations") or []
        for fragment in (entry.get("negated_texts") or [])
    ]

    assert fragments, "the absence must still be recorded"
    assert any("other than the ground-floor piers" in fragment
               for fragment in fragments), (
        "the qualifier was cut, inverting the meaning: %r" % (fragments,))


def test_the_exception_itself_stays_a_visible_element():
    """Guard: extending the DISPLAY must not re-negate the exception."""

    observation = _mixed_observation()

    kinds = {
        kind
        for entry in observation.get("architectural_elements") or []
        for kind in (entry.get("kind") or [])
    }

    assert "pier" in kinds, "the exception clause names a real element"
    assert "column" not in kinds


def test_persian_report_does_not_deny_columns_it_described():
    """The rendered report must not contain the absolutised absence."""

    _, report = _report("fa")

    assert "brick piers/columns" in report, "precondition: piers are reported"
    assert not re.search(r"^• no visible columns$", report, re.MULTILINE), (
        "the report denies the columns it just listed:\n" + report)


# ==========================================================
# E. Defect 4 — the same observation printed twice
# ==========================================================


def test_one_bullet_per_observation():
    """A truncated duplicate of the passage must not be printed as well."""

    _, report = _report("fa")

    passage_lines = [
        line for line in report.splitlines()
        if "through" in line.lower() and "passage" in line.lower()
    ]

    assert len(passage_lines) == 1, (
        "the through-passage is reported %d times:\n%s"
        % (len(passage_lines), "\n".join(passage_lines)))


# ==========================================================
# F. Language isolation
# ==========================================================


def test_english_report_has_no_persian():
    _, report = _report("en")

    assert not re.search(r"[\u0600-\u06FF]", report)


def test_persian_report_keeps_the_english_evidence_verbatim():
    """Quoted evidence stays in the observer's own words — that is deliberate."""

    _, report = _report("fa")

    assert "Full-height exterior walls of variegated red/brown/buff brick" in report


# ==========================================================
# G. No hardcoded answer for the acceptance image
# ==========================================================


@pytest.mark.parametrize("filename", [
    "architectural_observation_v1.py",
    "architectural_vision_interpreter_v1.py",
    "vision_report_v1.py",
    "image_understanding_v1.py",
])
def test_production_code_does_not_know_the_acceptance_answer(filename):
    """J — no storey count, passage verdict or image digest is baked in."""

    path = os.path.join(ROOT, "core", "vision", filename)
    with open(path, encoding="utf-8") as fh:
        source = fh.read()

    assert "00263" not in source
    assert "ae77532b" not in source
