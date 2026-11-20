# ==========================================================
# ArchitectOS — I2I_INSTRUCTION_FIDELITY_V1
#
# NO GPU. NO COMFYUI SUBMISSION. NO MODEL INSTALLATION.
#
# Covers the two defects fixed in this task:
#
#   1. A colour-change instruction compiled to a directionless delta
#      ("adjust the colour palette") so the requested target colour never
#      reached the diffusion model.
#   2. A confirmed render-submit failure was reported as "pending".
#
# The vocabulary is general: no colour, surface or test image is
# special-cased anywhere below.
# ==========================================================

from unittest.mock import MagicMock

import pytest

from core.prompt_intelligence.image_edit_delta_v1 import (
    compile_edit_delta,
    is_classified,
    EDIT_COLOR,
    EDIT_MATERIAL,
    EDIT_TIME_OF_DAY,
    EDIT_GENERIC,
)
from core.render.render_result_bridge import RenderResultBridge


# ==========================================================
# 1. COLOUR DELTA MUST NAME THE REQUESTED COLOUR
# ==========================================================

def test_colour_change_names_the_requested_colour_english():
    delta = compile_edit_delta(
        "Change the wall colour to blue while preserving the rest."
    )
    assert delta["edit_class"] == EDIT_COLOR
    assert delta["color"] == "blue"
    assert "blue" in delta["delta_prompt"].lower()
    assert "DELTA:" in delta["prompt"]


def test_colour_change_names_the_requested_colour_persian():
    """A Persian colour request needs no colour noun to qualify."""
    delta = compile_edit_delta("نمای ساختمان را آبی کن")
    assert delta["edit_class"] == EDIT_COLOR
    assert delta["color"] == "blue"
    assert "blue" in delta["delta_prompt"].lower()


def test_other_colours_resolve_generically():
    for text, expected in (
        ("make the facade red", "red"),
        ("the colour should become green", "green"),
        ("نمای ساختمان را قرمز کن", "red"),
        ("use a black finish", "black"),
    ):
        delta = compile_edit_delta(text)
        assert delta["color"] == expected, (text, delta["color"])
        assert expected in delta["delta_prompt"].lower(), text


def test_target_colour_wins_over_the_current_colour():
    """A colour that only describes the CURRENT state must not be chosen.

    "Change the red wall ... to blue" must resolve to blue: the target marker
    ("to") outranks the earlier colour mention ("red").
    """
    delta = compile_edit_delta(
        "Change the red wall of the existing building to blue."
    )
    assert delta["color"] == "blue", delta
    assert "to blue" in delta["delta_prompt"].lower()

    assert compile_edit_delta("turn the white facade into green")["color"] == "green"
    assert compile_edit_delta("make the grey building become blue")["color"] == "blue"

    # no target marker -> the requested colour is the one mentioned
    assert compile_edit_delta("use blue instead of red")["color"] == "blue"


def test_colour_delta_no_longer_contradicts_a_repaint():
    """'keep the same materials' directly contradicted a colour change."""
    delta = compile_edit_delta("Change the wall colour to blue")
    assert "keep the same materials" not in delta["delta_prompt"].lower()


def test_colour_without_a_named_colour_keeps_previous_wording():
    delta = compile_edit_delta("رنگش رو عوض کن")
    assert delta["edit_class"] == EDIT_COLOR
    assert delta["color"] is None
    assert "adjust the colour palette" in delta["delta_prompt"]


def test_latin_colour_names_match_on_word_boundaries():
    """'reduced' / 'hundred' must not be read as the colour red."""
    assert compile_edit_delta("reduce the noise")["edit_class"] == EDIT_GENERIC
    assert compile_edit_delta("a hundred colours")["color"] is None


# ==========================================================
# 2. NO REGRESSION IN THE OTHER EDIT CLASSES
# ==========================================================

def test_material_and_time_of_day_are_unchanged():
    night = compile_edit_delta("همینو شب کن")
    assert night["edit_class"] == EDIT_TIME_OF_DAY
    assert "night" in night["prompt"].lower()

    stone = compile_edit_delta("رندر قبلی رو سنگ روشن کن")
    assert stone["edit_class"] == EDIT_MATERIAL
    assert stone["material"] == "stone"
    assert stone["material_tone"] == "light"
    # A generic stone request must retain generic specificity.  The explicit
    # tone is preserved, but no stone species is inferred.
    assert "light stone of unspecified species" in stone["prompt"]
    assert "travertine" not in stone["delta_prompt"]
    assert "marble" not in stone["delta_prompt"]


def test_non_edit_text_stays_generic():
    for text in ("یه ویلای مدرن میخوام", "", "سلام"):
        delta = compile_edit_delta(text)
        assert delta["edit_class"] == EDIT_GENERIC, text
        assert not is_classified(delta), text


def test_delta_compilation_is_deterministic():
    text = "Change the wall colour to blue while preserving the rest."
    assert compile_edit_delta(text) == compile_edit_delta(text)


def test_delta_prompt_carries_the_four_sections():
    delta = compile_edit_delta("make the facade red")
    for section in ("REFERENCE:", "DELTA:", "PRESERVE:", "QUALITY:"):
        assert section in delta["prompt"], section


# ==========================================================
# 3. RENDER ERROR STATUS
# ==========================================================

@pytest.fixture()
def bridge():
    b = RenderResultBridge()
    b.comfy = MagicMock()          # no network, no history polling
    return b


def test_submit_error_is_error_not_pending(bridge):
    result = bridge.resolve(
        {
            "engine": "comfyui",
            "status": "submit_error",
            "execution": {
                "status": "error",
                "message": "connection refused",
                "prompt_id": None,
            },
        }
    )
    assert result["status"] == "error"
    assert "refused" in str(result["error"])


def test_missing_prompt_id_is_error(bridge):
    result = bridge.resolve(
        {
            "engine": "comfyui",
            "status": "missing_prompt_id",
            "execution": {"status": "submitted"},
        }
    )
    assert result["status"] == "error"


def test_unknown_engine_is_error(bridge):
    result = bridge.resolve({"status": "unknown_engine", "engine": "nope"})
    assert result["status"] == "error"


def test_failed_execution_with_prompt_id_is_error(bridge):
    result = bridge.resolve(
        {
            "engine": "comfyui",
            "status": "error",
            "prompt_id": "abc",
            "execution": {"status": "error", "message": "oom"},
        }
    )
    assert result["status"] == "error"


def test_queued_job_without_prompt_id_is_still_pending(bridge):
    result = bridge.resolve(
        {"engine": "comfyui", "status": "submitted", "execution": {"status": "submitted"}}
    )
    assert result["status"] == "pending"


def test_debug_mode_is_untouched(bridge):
    result = bridge.resolve({"debug": True})
    assert result["status"] == "debug"


def test_bridge_records_the_real_file_existence_flag(bridge):
    """KNOWN LIMITATION — reported, NOT fixed in this task.

    `resolve()` still returns status="success" for an image filename that does
    not exist on disk; it only records the truth in `image.exists`. That is
    pre-existing behaviour deliberately pinned by
    tests/test_render_result_bridge_contract.py (which asserts success for a
    fictional "test_render.png"), so it is outside the reported defect and is
    documented here rather than changed without approval.
    """
    bridge.comfy.history = MagicMock(return_value={})
    result = bridge.resolve(
        {
            "engine": "comfyui",
            "status": "success",
            "prompt_id": "p1",
            "execution": {
                "status": "success",
                "prompt_id": "p1",
                "images": [
                    {
                        "filename": "definitely_not_on_disk_9f3a.png",
                        "subfolder": "",
                        "type": "output",
                    }
                ],
            },
        }
    )
    assert result["image"]["exists"] is False
