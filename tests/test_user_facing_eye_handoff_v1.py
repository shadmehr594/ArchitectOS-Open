# -*- coding: utf-8 -*-
"""R2_USER_FACING_EYE_HANDOFF_V1 — CPU acceptance for the answer handoff.

Proves that the architectural observation already produced by the EXISTING
pipeline reaches the two places an answer is built from:

  * `image_session_v1.build_grounded_prompt()` — the LLM-grounded context
  * `vision_report_v1.render_vision_report()` — the deterministic user text

and that it arrives ATTRIBUTED: an unverified model observation is never
presented as verified geometry, absence is never restated as presence, and a
reported count is never contradicted by "cannot be determined".

No Ollama. No GPU. Fixtures are the authentic saved live records.
"""

import json
import os

import pytest

from core.vision.image_understanding_v1 import build_understanding
from core.vision.architectural_vision_interpreter_v1 import interpret_architectural_vision
from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
from core.vision.image_session_v1 import build_grounded_prompt
from core.vision.vision_report_v1 import (
    render_vision_report, _without_floor_unknown, _reported_floor_count,
)
from core.vision.design_constraint_fidelity_v1 import observed_constraints


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIXTURES = {
    "V3": os.path.join(ROOT, "runs", "r2_live_normalizer_v13", "eye_V3_v13.json"),
    "ARM_A": os.path.join(ROOT, "runs", "r2_live_eye_v13_completion_v1", "eye_ARM_A_v13.json"),
    "ARM_B": os.path.join(ROOT, "runs", "r2_live_eye_v13_completion_v1", "eye_ARM_B_v13.json"),
    "B01": os.path.join(ROOT, "runs", "r2_live_eye_v13_completion_v1", "eye_B01_v13.json"),
}

PERSIAN_QUESTION = "این ساختمان چند طبقه دارد و چه مصالح و عناصری در نما دیده می‌شود؟"


def _record(key):
    with open(FIXTURES[key], encoding="utf-8") as fh:
        return json.load(fh)


def _chain(key):
    """The real production chain, from the saved bridge payload."""

    record = _record(key)

    understanding = build_understanding(
        {"contract": BRIDGE_CONTRACT,
         "raw_observer": record["raw_observer"],
         "normalization": record["normalization"]},
        provider="ollama", model="qwen3.8:27b", image_id=key, source_type="other")

    interpretation = interpret_architectural_vision(understanding)

    return understanding, interpretation, interpretation["architectural_observation"]


def _prompt(key, question=PERSIAN_QUESTION):
    understanding, _, observation = _chain(key)
    return build_grounded_prompt(question, understanding, observation=observation)


# ==========================================================
# 1. The floor reading reaches the answer context
# ==========================================================

@pytest.mark.parametrize("key,count,upper", [
    ("V3", 4, 3), ("ARM_A", 3, 2), ("ARM_B", 3, 2), ("B01", 3, 2),
])
def test_floor_reading_reaches_the_grounded_prompt(key, count, upper):
    prompt = _prompt(key)
    assert "storey count" in prompt
    assert "storeys visible: %d" % count in prompt
    assert "%d upper floors" % upper in prompt


@pytest.mark.parametrize("key,count", [("V3", 4), ("ARM_A", 3), ("ARM_B", 3), ("B01", 3)])
def test_floor_reading_is_labelled_unverified(key, count):
    prompt = _prompt(key)
    assert "MODEL OBSERVATION, unverified, confidence LOW" in prompt
    # the verified channel is never asserted
    assert "verified storeys" not in prompt.lower()


def test_floor_quote_is_carried_verbatim():
    prompt = _prompt("V3")
    assert "Total storeys visible (including ground floor): 4" in prompt


def test_parapet_exclusion_is_stated():
    prompt = _prompt("B01")
    assert "parapet / roof band NOT counted as a storey" in prompt


# ==========================================================
# 2. Materials and absence reach the answer context
# ==========================================================

def test_materials_reach_the_grounded_prompt():
    """CHANGED by VISION_MATERIAL_SEMANTICS_V1 — `steel` became `metal`.

    ARM_A's only metal is "black metal railing", a GENERIC metal. It used to
    reach the grounded prompt as `steel` because the marker table mapped the
    family onto the alloy. The prompt must carry what the observer said, so
    the expected term is `metal`; no explicit steel appears in this fixture.
    """
    prompt = _prompt("ARM_A")
    assert "materials named by the model" in prompt
    for material in ("glass", "stone", "brick", "metal"):
        assert material in prompt
    assert "steel" not in prompt, "a generic metal was reported as an alloy"


def test_negated_materials_are_not_named_as_present():
    prompt = _prompt("B01")
    materials_line = next(
        line for line in prompt.splitlines() if line.startswith("materials named by"))
    assert "plaster" not in materials_line
    assert "glass" not in materials_line
    assert "brick" in materials_line and "masonry" in materials_line


def test_absence_reaches_the_prompt_as_absence():
    prompt = _prompt("V3")
    assert "reported ABSENT or NOT VISIBLE" in prompt
    assert "never restate these as present" in prompt


# ==========================================================
# 3. The rendered user text
# ==========================================================

def test_rendered_report_states_the_storey_count():
    _, interpretation, _ = _chain("V3")
    text = render_vision_report(interpretation, "fa")
    assert "4 طبقهٔ قابل مشاهده" in text
    assert "شامل همکف و 3 طبقهٔ بالایی" in text


def test_rendered_report_no_longer_claims_undeterminable_floors():
    _, interpretation, _ = _chain("V3")
    text = render_vision_report(interpretation, "fa")
    assert "تعداد دقیق طبقات از شواهد دیداری قابل تعیین نیست" not in text


def test_rendered_report_keeps_other_unknowns():
    _, interpretation, _ = _chain("V3")
    text = render_vision_report(interpretation, "fa")
    assert "سیستم سازه‌ای" in text


def test_rendered_report_separates_absence():
    _, interpretation, _ = _chain("V3")
    text = render_vision_report(interpretation, "fa")
    assert "غایب یا نادیدنی" in text
    # the absence must not be listed under the positive observations header
    positive_block = text.split("غایب یا نادیدنی")[0]
    assert "No balconies, no external stairs" not in positive_block


def test_rendered_report_b01_keeps_terrace_but_not_as_a_storey():
    _, interpretation, _ = _chain("B01")
    text = render_vision_report(interpretation, "fa")
    assert "3 طبقهٔ قابل مشاهده" in text
    assert "جان‌پناه یا باند بام به‌عنوان طبقه شمرده نشده است" in text
    # the terrace itself is a real positive observation
    assert "roof terrace" in text


def test_rendered_report_english_also_works():
    _, interpretation, _ = _chain("ARM_A")
    text = render_vision_report(interpretation, "en")
    assert "3 storeys are visible" in text
    assert "not independently verified" in text


# ==========================================================
# 4. Safety: no promotion, no contradiction
# ==========================================================

@pytest.mark.parametrize("key", ["V3", "ARM_A", "ARM_B", "B01"])
def test_verified_channel_stays_null_and_render_cannot_pass(key):
    _, _, observation = _chain(key)
    assert observation["visible_floors"] is None
    assert observation["visible_floors_observation"]["confidence"] == "LOW"
    assert observation["visible_floors_observation"]["verification"] == "UNVERIFIED"
    assert observation["visible_floors_observation"]["authoritative"] is False
    assert observed_constraints(observation)["floors"] is None


def test_floor_unknown_is_withheld_only_from_the_render():
    _, interpretation, _ = _chain("V3")
    assert "exact floor count is not determinable from the visible evidence" in (
        interpretation["unknowns"])
    rendered = _without_floor_unknown(interpretation)
    assert "exact floor count is not determinable from the visible evidence" not in (
        rendered["unknowns"])
    # other unknowns survive
    assert any("structural" in item for item in rendered["unknowns"])


def test_floor_unknown_survives_when_no_count_was_reported():
    """The withhold is CONDITIONAL: with no reading, the honest unknown stays."""
    _, interpretation, _ = _chain("V3")
    stripped = dict(interpretation)
    observation = dict(interpretation["architectural_observation"])
    observation["visible_floors_observation"] = None
    stripped["architectural_observation"] = observation
    assert _reported_floor_count(stripped) is None
    text = render_vision_report(stripped, "fa")
    assert "تعداد دقیق طبقات از شواهد دیداری قابل تعیین نیست" in text


# ==========================================================
# 5. Safe failure and no invented content
# ==========================================================

def test_observation_argument_is_optional_and_falls_back_to_extras():
    """Without the observation, the storey reading still arrives (extras),
    but absence evidence — which lives only on the observation — is NOT
    invented."""
    understanding, _, _ = _chain("V3")
    prompt = build_grounded_prompt(PERSIAN_QUESTION, understanding)
    assert "IMAGE VISUAL EVIDENCE" in prompt
    assert "storeys visible: 4" in prompt
    assert "reported ABSENT" not in prompt


def test_empty_understanding_fails_safely():
    prompt = build_grounded_prompt("hello", {})
    assert "UNAVAILABLE" in prompt
    assert "storey count" not in prompt


def test_prompt_adds_no_unsupported_elements():
    prompt = _prompt("ARM_A")
    for invented in ("swimming pool", "garage door", "elevator", "chimney"):
        assert invented not in prompt.lower()


def test_persian_question_is_preserved_verbatim():
    prompt = _prompt("V3")
    assert PERSIAN_QUESTION in prompt


def test_legacy_interpretation_renders_unchanged():
    """No architectural_observation → no new sections at all."""
    legacy = {"space_type": "facade", "unknowns": ["something unknown"]}
    text = render_vision_report(legacy, "fa")
    assert "طبقات قابل مشاهده" not in text
    assert "غایب یا نادیدنی" not in text
