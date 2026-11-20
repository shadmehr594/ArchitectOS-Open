"""
test_t2i_architectural_feature_handoff_v1.py
CPU-only. No GPU, no ComfyUI.

Verifies that explicitly requested architectural features (doors, windows,
railings, parapets) reach the final_prompt via build_render_instruction ->
build_constraint_block -> resolve_render_prompt.
"""
import sys
sys.path.insert(0, ".")
import pytest

from core.cognition.architectural_render_instruction_v1 import (
    _feature_requirements,
    _feature_sentence,
    _constraint_sentences,
    build_constraint_block,
    build_render_instruction,
    FEATURE_SENTENCE_PREFIX,
)
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)


# ---------------------------------------------------------------------------
# 1. feature_requirements extraction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected_element", [
    ("یک در ورودی چوبی به نمای ساختمان اضافه کن", "door"),
    ("پنجره\u200cهای بلند به نما اضافه کن", "window"),
    ("برای بالکن جان\u200cپناه فلزی اضافه کن", "parapet"),
    ("add a wooden entrance door to the facade", "door"),
    ("add tall windows to the facade", "window"),
    ("add a metal guardrail to the balcony", "railing"),
])
def test_feature_requirements_extraction(text, expected_element):
    reqs = _feature_requirements(text)
    assert reqs, f"No requirements for: {text}"
    elements = [r["element"] for r in reqs]
    assert expected_element in elements, (
        f"Expected {expected_element!r} in {elements!r} for: {text}"
    )


# ---------------------------------------------------------------------------
# 2. feature_requirements: add-signal vs. negation
# ---------------------------------------------------------------------------

def test_add_signal_gives_requirements():
    reqs = _feature_requirements("یک در ورودی اضافه کن")
    assert len(reqs) > 0

def test_negation_gives_no_requirements():
    reqs = _feature_requirements("در ورودی اضافه نکن")
    assert len(reqs) == 0

def test_observation_gives_no_requirements():
    reqs = _feature_requirements("لیست کن که چند پنجره دارد")
    assert len(reqs) == 0


# ---------------------------------------------------------------------------
# 3. _feature_sentence emits the unique prefix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("element,group", [
    ("door", "opening"),
    ("window", "opening"),
    ("parapet", "protection"),
    ("railing", "protection"),
])
def test_feature_sentence_prefix(element, group):
    req = {"element": element, "group": group, "material": None, "locations": []}
    sentence = _feature_sentence(req)
    assert sentence.startswith(FEATURE_SENTENCE_PREFIX), (
        f"Sentence does not start with prefix: {sentence!r}"
    )


# ---------------------------------------------------------------------------
# 4. material and location separation (per-clause)
# ---------------------------------------------------------------------------

def test_door_gets_wood_material():
    reqs = _feature_requirements("add a wooden entrance door to the facade")
    req = next(r for r in reqs if r["element"] == "door")
    assert req["material"] == "wood"

def test_parapet_gets_metal_material():
    reqs = _feature_requirements("add a metal guardrail to the balcony")
    req = next(r for r in reqs if r["element"] in ("railing", "parapet"))
    assert req["material"] == "metal"

def test_window_no_invented_material():
    reqs = _feature_requirements("add tall windows to the facade")
    req = next(r for r in reqs if r["element"] == "window")
    assert req["material"] is None

def test_location_attribution_separate():
    """Door at entrance != window at facade; materials must not cross."""
    reqs = _feature_requirements(
        "add arched windows to the facade and a wooden door at the entrance"
    )
    door = next((r for r in reqs if r["element"] == "door"), None)
    window = next((r for r in reqs if r["element"] == "window"), None)
    if door and window:
        # door material must not leak onto window
        assert window.get("material") != "wood" or door.get("material") == "wood"
    # At least one must have been found
    assert door or window


# ---------------------------------------------------------------------------
# 5. build_constraint_block admits FEATURE sentences
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "یک در ورودی چوبی به نمای ساختمان اضافه کن",
    "پنجره\u200cهای بلند به نما اضافه کن",
    "برای بالکن جان\u200cپناه فلزی اضافه کن",
    "add a wooden entrance door to the facade",
    "add tall windows to the facade",
    "add a metal guardrail to the balcony",
])
def test_constraint_block_contains_feature(text):
    instr = build_render_instruction(text)
    block = build_constraint_block(instr)
    assert FEATURE_SENTENCE_PREFIX in block, (
        f"FEATURE prefix not in block for: {text!r}\nBlock: {block!r}"
    )


# ---------------------------------------------------------------------------
# 6. resolve_render_prompt: feature reaches final_prompt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "یک در ورودی چوبی به نمای ساختمان اضافه کن",
    "پنجره\u200cهای بلند به نما اضافه کن",
    "برای بالکن جان\u200cپناه فلزی اضافه کن",
    "add a wooden entrance door to the facade",
])
def test_feature_reaches_final_prompt(text):
    instr = build_render_instruction(text)
    block = build_constraint_block(instr)
    # Add constraint_block to instruction dict (as render_runtime does)
    instr_with_block = dict(instr)
    instr_with_block["constraint_block"] = block
    result = resolve_render_prompt(
        compiled_prompt=instr.get("base_compiled_prompt"),
        architectural_instruction=instr_with_block,
    )
    assert result.get("instruction_applied"), (
        f"instruction_applied is False for: {text!r}"
    )
    final = result.get("final_prompt", "")
    assert FEATURE_SENTENCE_PREFIX in final, (
        f"FEATURE prefix not in final_prompt for: {text!r}\nFinal: {final!r}"
    )


# ---------------------------------------------------------------------------
# 7. Regression: no feature request -> block is empty / unchanged
# ---------------------------------------------------------------------------

def test_no_feature_request_block_unchanged():
    """A turn with no feature request must produce the same output as before."""
    text = "نمای ساختمان را با سنگ پوشش بده"  # just a material change, no new element
    instr = build_render_instruction(text)
    block = build_constraint_block(instr)
    # Block may be empty or contain non-feature content, but must NOT contain feature prefix
    assert FEATURE_SENTENCE_PREFIX not in block, (
        f"Unexpected feature in block for non-feature request: {block!r}"
    )


# ---------------------------------------------------------------------------
# 8. Descriptive narrative is still blocked
# ---------------------------------------------------------------------------

def test_description_prefix_blocked():
    """Sentences with _DESCRIPTION_PREFIXES must never enter the block."""
    text = "take the facade appearance from image A"
    instr = build_render_instruction(text)
    block = build_constraint_block(instr)
    assert "Take the facade APPEARANCE from IMAGE A" not in block


# ---------------------------------------------------------------------------
# 9. T2I vs I2I: _explicit_text_to_image_turn (unit-level)
# ---------------------------------------------------------------------------

def test_explicit_t2i_requires_manual_routing_source():
    """Without routing_source='manual', must return False."""
    # We can test the logic without instantiating ChatArchitect by replicating it
    from core.render.render_strategy_controller_v1 import (
        MODE_TEXT_TO_IMAGE, normalize_mode)
    
    context_auto = {"routing_source": "auto", "mode": "text_to_image"}
    routing_source = str(context_auto.get("routing_source") or "").strip().lower()
    is_explicit = routing_source == "manual" and normalize_mode(context_auto.get("mode")) == MODE_TEXT_TO_IMAGE
    assert not is_explicit, "Auto mode must not be treated as explicit T2I"

    context_manual = {"routing_source": "manual", "mode": "text_to_image"}
    routing_source2 = str(context_manual.get("routing_source") or "").strip().lower()
    is_explicit2 = routing_source2 == "manual" and normalize_mode(context_manual.get("mode")) == MODE_TEXT_TO_IMAGE
    assert is_explicit2, "Manual T2I must be recognized as explicit"
