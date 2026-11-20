"""I2I_DENOISE_AUTHORITY_V1 — CPU precedence tests.

The completed run executed denoise 0.40 while the acceptance expectation was
0.30. This pins where 0.40 comes from and how the levels interact.

No GPU, no ComfyUI POST, no inference.
"""

import json
import os

import pytest

from core.prompt_intelligence.image_edit_delta_v1 import (
    compile_edit_delta,
    denoise_override,
    preservation_level,
)
from core.render.image_edit_presets_v1 import (
    LEVELS,
    clamp_denoise,
    resolve_preservation,
    resolve_preservation_with_denoise,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAT = os.path.join(ROOT, "data", "projects", "project_7b6016d9",
                    "conversations", "chat.json")

REAL_REQUEST = (
    "Do not add floors, remove floors, or change the geometry. "
    "Only change the exterior facade treatment to light cream travertine."
)


def _persisted_request():
    if not os.path.isfile(CHAT):
        return REAL_REQUEST
    with open(CHAT, encoding="utf-8") as fh:
        return json.load(fh)["messages"][10]["text"]


# ---------------------------------------------------------------- provenance

def test_material_change_selects_the_balanced_level():
    delta = compile_edit_delta(_persisted_request(), image_edit=True)

    assert delta.get("edit_class") == "material_change"
    assert preservation_level(delta) == "balanced"


def test_material_change_supplies_no_explicit_denoise():
    delta = compile_edit_delta(_persisted_request(), image_edit=True)

    # Only time-of-day edits carry a strength override.
    assert denoise_override(delta) is None


def test_balanced_level_resolves_to_0_40_without_an_explicit_value():
    delta = compile_edit_delta(_persisted_request(), image_edit=True)

    resolved = resolve_preservation_with_denoise(
        text=_persisted_request(),
        explicit=preservation_level(delta),
        denoise=denoise_override(delta),
    )

    assert resolved["level"] == "balanced"
    assert resolved["denoise"] == 0.40
    # The decisive field: nothing explicit was requested.
    assert resolved["explicit_denoise"] is None


def test_the_escalation_is_a_level_default_not_a_clamp():
    """0.40 is balanced's own default, not 0.30 pushed up."""

    assert LEVELS["balanced"]["denoise"] == 0.40
    assert clamp_denoise(0.40, "balanced") == 0.40

    # A genuine 0.30 clamped into balanced would become the range floor.
    assert clamp_denoise(0.30, "balanced") == 0.35


# ---------------------------------------------------------------- precedence

def test_explicit_level_beats_the_edit_class_contract():
    resolved = resolve_preservation_with_denoise(
        text=_persisted_request(),
        explicit="high_preservation",
        denoise=None,
    )

    assert resolved["level"] == "high_preservation"
    assert resolved["denoise"] == 0.25
    assert resolved["source"] == "explicit_level"


def test_explicit_denoise_is_clamped_into_the_level_range():
    assert clamp_denoise(0.30, "high_preservation") == 0.30
    assert clamp_denoise(0.10, "high_preservation") == 0.20
    assert clamp_denoise(0.90, "high_preservation") == 0.30
    assert clamp_denoise(0.30, "balanced") == 0.35


def test_without_a_delta_the_default_is_high_preservation():
    resolved = resolve_preservation(text="make it nicer")

    assert resolved["level"] == "high_preservation"
    assert resolved["denoise"] == 0.25


def test_time_of_day_carries_its_own_strength():
    delta = compile_edit_delta("همینو شب کن", image_edit=True)

    assert denoise_override(delta) == 0.30

    resolved = resolve_preservation_with_denoise(
        text="همینو شب کن",
        explicit=preservation_level(delta),
        denoise=denoise_override(delta),
    )

    low = LEVELS[resolved["level"]]["min"]
    high = LEVELS[resolved["level"]]["max"]

    assert low <= resolved["denoise"] <= high
    assert resolved["explicit_denoise"] == 0.30


# ---------------------------------------------------------------- contract

def test_level_bands_are_the_documented_ones():
    assert (LEVELS["high_preservation"]["min"],
            LEVELS["high_preservation"]["max"]) == (0.20, 0.30)
    assert (LEVELS["balanced"]["min"], LEVELS["balanced"]["max"]) == (0.35, 0.45)
    assert (LEVELS["creative"]["min"], LEVELS["creative"]["max"]) == (0.50, 0.60)


def test_zero_point_three_is_not_reachable_without_an_explicit_denoise():
    """The product exposes a LEVEL, not a denoise value."""

    # high_preservation's DEFAULT is 0.25; 0.30 is only its ceiling.
    assert resolve_preservation(text="", explicit="high_preservation")["denoise"] == 0.25

    # No level resolves to exactly 0.30 by default.
    defaults = {name: level["denoise"] for name, level in LEVELS.items()}

    assert 0.30 not in defaults.values()
