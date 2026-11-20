# -*- coding: utf-8 -*-
"""R2_FINAL_UI_SMOKE_PREFLIGHT_V1 — CPU acceptance for the three remaining gaps.

A. The replay must run the CURRENT `parse_normalization()`, not reuse the
   historical structured object (which still held pre-fix quotations).
B. A negative-only assertion must never be printed under positive
   observations, and a mixed sentence must report only its negative clause.
C. The DEFAULT observer prompt used by the UI must actually ask for the
   storey observation.

No Ollama. No GPU. Fixtures are the authentic saved live records.
"""

import inspect
import json
import os

import pytest

from core.vision.general_visual_observer_v1 import (
    OBSERVER_PROMPT, OBSERVER_VERSION, run_visual_bridge,
)
from core.vision.observation_normalizer_v1 import parse_normalization, normalizer_input
from core.vision.image_understanding_v1 import build_understanding
from core.vision.architectural_vision_interpreter_v1 import interpret_architectural_vision
from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE
from core.vision.vision_report_v1 import render_vision_report
from core.vision.image_session_v1 import build_grounded_prompt
from core.vision.design_constraint_fidelity_v1 import observed_constraints
from core.vision.vision_provider_ollama_v1 import OllamaVisualObserver


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIXTURES = {
    "V3": os.path.join(ROOT, "runs", "r2_live_normalizer_v13", "eye_V3_v13.json"),
    "ARM_A": os.path.join(ROOT, "runs", "r2_live_eye_v13_completion_v1", "eye_ARM_A_v13.json"),
    "ARM_B": os.path.join(ROOT, "runs", "r2_live_eye_v13_completion_v1", "eye_ARM_B_v13.json"),
    "B01": os.path.join(ROOT, "runs", "r2_live_eye_v13_completion_v1", "eye_B01_v13.json"),
}

EXPECTED = {"V3": (4, 3), "ARM_A": (3, 2), "ARM_B": (3, 2), "B01": (3, 2)}


def _record(key):
    with open(FIXTURES[key], encoding="utf-8") as fh:
        return json.load(fh)


def _reparsed(key):
    """CURRENT production parsing of the saved model JSON."""

    record = _record(key)
    source_text, _ = normalizer_input(record["raw_text"], 24000)
    diagnostics = {}
    structured = parse_normalization(
        record["normalization"]["raw_text"], source_text, diagnostics=diagnostics)
    return record, source_text, structured, diagnostics


def _chain(key):
    record, _, structured, diagnostics = _reparsed(key)
    understanding = build_understanding(
        {"contract": BRIDGE,
         "raw_observer": record["raw_observer"],
         "normalization": {"status": "NORMALIZED", "structured": structured}},
        provider="ollama", model="qwen3.8:27b", image_id=key, source_type="other")
    interpretation = interpret_architectural_vision(understanding)
    return interpretation, interpretation["architectural_observation"], diagnostics


# ==========================================================
# A. corrected quote provenance
# ==========================================================

@pytest.mark.parametrize("key", ["V3", "ARM_A", "ARM_B", "B01"])
def test_A_reparsed_floor_quote_is_verbatim(key):
    _, source_text, structured, diagnostics = _reparsed(key)
    quote = structured["visible_floors"]["evidence_quote"]
    assert quote in source_text
    assert source_text.count(quote) == 1
    assert diagnostics["floor_quote"]["promoted"] is True


@pytest.mark.parametrize("key", ["V3", "ARM_A", "ARM_B", "B01"])
def test_A_historical_quote_was_not_verbatim_for_three_fixtures(key):
    """Proves the replay actually changed something: the OLD stored quote is
    not a substring for ARM_A/ARM_B/B01, while the reparsed one is."""
    record = _record(key)
    source_text, _ = normalizer_input(record["raw_text"], 24000)
    old_quote = (record["normalization"]["structured"]["visible_floors"]
                 ["evidence_quote"])
    new_quote = _reparsed(key)[2]["visible_floors"]["evidence_quote"]
    if key == "V3":
        assert old_quote in source_text
    else:
        assert old_quote not in source_text
    assert new_quote in source_text


@pytest.mark.parametrize("key", ["V3", "ARM_A", "ARM_B", "B01"])
def test_A_counts_are_unchanged(key):
    _, _, structured, _ = _reparsed(key)
    count, upper = EXPECTED[key]
    floor = structured["visible_floors"]
    assert floor["count"] == count
    assert floor["upper_floors"] == upper
    assert floor["count_scope"] == "TOTAL"
    assert floor["ground_floor_included"] is True


@pytest.mark.parametrize("key", ["V3", "ARM_A", "ARM_B", "B01"])
def test_A_trust_tier_and_render_fidelity(key):
    _, observation, _ = _chain(key)
    reading = observation["visible_floors_observation"]
    assert reading["confidence"] == "LOW"
    assert reading["verification"] == "UNVERIFIED"
    assert reading["authoritative"] is False
    assert reading["trust_tier"] == "PROVIDER_OBSERVATION"
    assert observation["visible_floors"] is None
    assert observed_constraints(observation)["floors"] is None


# ==========================================================
# B. absence is never presented as presence
# ==========================================================

def _positive_block(text):
    return text.split("غایب یا نادیدنی")[0]


def test_B_arm_b_attic_band_is_not_a_positive_observation():
    interpretation, _, _ = _chain("ARM_B")
    text = render_vision_report(interpretation, "fa")
    assert "no attic band" not in _positive_block(text).lower()


def test_B_arm_b_absence_section_still_reports_it():
    _, observation, _ = _chain("ARM_B")
    phrases = " ".join(
        str(entry.get("evidence_phrase")) for entry in observation["negative_observations"])
    assert "no pitched roof" in phrases


def test_B_arm_b_keeps_flat_roof_and_parapet():
    interpretation, _, _ = _chain("ARM_B")
    text = render_vision_report(interpretation, "fa")
    assert "Flat roof with a brick parapet edge" in text
    assert "Two cantilevered balconies" in text
    assert "glass balustrade" in text


def test_B_b01_absence_names_only_the_negative_clause():
    interpretation, observation, _ = _chain("B01")
    text = render_vision_report(interpretation, "fa")
    absence = text.split("غایب یا نادیدنی")[1]
    assert "no plaster or cladding" in absence
    assert "no glazing" in absence
    # the whole mixed sentence must not be reprinted as the absence item
    assert "Exposed masonry (brick / concrete block) infill walls" not in absence


def test_B_b01_negated_fragments_are_verbatim_slices():
    _, observation, _ = _chain("B01")
    for entry in observation["negative_observations"]:
        phrase = entry["evidence_phrase"]
        for fragment in entry.get("negated_texts") or []:
            assert fragment in phrase, "a fragment must be a slice of the source"


def test_B_b01_keeps_positive_architecture():
    interpretation, _, _ = _chain("B01")
    text = render_vision_report(interpretation, "fa")
    positive = _positive_block(text)
    assert "roof terrace" in positive
    assert "parapet and balustrade" in positive
    assert "Vertical piers/columns" in positive
    assert "Brick/block masonry" in positive


def test_B_b01_terrace_is_not_a_fourth_storey():
    interpretation, observation, _ = _chain("B01")
    assert observation["visible_floors_observation"]["count"] == 3
    text = render_vision_report(interpretation, "fa")
    assert "3 طبقهٔ قابل مشاهده" in text
    assert "4 طبقه" not in text


def test_B_no_negative_only_claim_survives_in_any_positive_block():
    for key in FIXTURES:
        interpretation, _, _ = _chain(key)
        positive = _positive_block(render_vision_report(interpretation, "fa")).lower()
        for marker in ("no attic band", "no pitched roof", "no visible roof terrace",
                       "no plaster", "no glazing", "no frames"):
            assert marker not in positive, (key, marker)


def test_B_absence_wording_is_scoped_to_the_image():
    interpretation, _, _ = _chain("ARM_B")
    text = render_vision_report(interpretation, "fa")
    assert "نه اثبات نبودِ آن در ساختمان" in text


# ==========================================================
# C. the DEFAULT observer prompt the UI actually uses
# ==========================================================

def test_C_default_prompt_requests_the_storey_observation():
    low = OBSERVER_PROMPT.lower()
    assert "number of storeys" in low
    assert "ground floor" in low
    assert "upper floors" in low


def test_C_default_prompt_requests_roof_band_and_framing():
    low = OBSERVER_PROMPT.lower()
    assert "parapet" in low
    assert "roof terrace" in low or "attic band" in low
    assert "occupiable storey" in low
    assert "inside the frame" in low or "cut off" in low


def test_C_default_prompt_stays_observation_only():
    low = OBSERVER_PROMPT.lower()
    assert "not json" in low
    assert "do not infer hidden geometry" in low
    assert "if the count cannot be determined, say so explicitly" in low


def test_C_observer_version_bumped_for_cache_invalidation():
    assert OBSERVER_VERSION == "general-visual-observer-v2"


def test_C_analyze_path_uses_the_default_prompt():
    """run_visual_bridge calls observe() with NO prompt → default applies."""
    calls = []

    class _Observer:
        def observe(self, asset):
            calls.append(asset)
            return {"raw_text": "", "generation_status": "COMPLETE"}

    class _Normalizer:
        def normalize(self, text):
            return {"status": "NORMALIZED"}

    run_visual_bridge(_Observer(), _Normalizer(), {"path": "x"})
    assert calls == [{"path": "x"}]


def test_C_observe_prompt_argument_defaults_to_none():
    signature = inspect.signature(OllamaVisualObserver.observe)
    assert signature.parameters["prompt"].default is None


# ==========================================================
# The end-to-end CPU handoff
# ==========================================================

def test_prompt_and_report_carry_the_reparsed_count():
    interpretation, observation, _ = _chain("V3")
    prompt = build_grounded_prompt("چند طبقه؟", {}, observation=observation)
    assert "storeys visible: 4" in prompt
    text = render_vision_report(interpretation, "fa")
    assert "4 طبقهٔ قابل مشاهده" in text
    assert "تعداد دقیق طبقات از شواهد دیداری قابل تعیین نیست" not in text
