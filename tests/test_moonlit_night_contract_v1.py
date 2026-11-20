"""MOONLIT_NIGHT_V1 — moonlit lighting contract + material-preservation routing.

Two confirmed defects are covered:

  DEFECT 1 — a moonlit request compiled to the generic night delta, discarding
             every moonlit attribute (moon / moonlit / moonlight / navy / cool /
             blue all absent), so the model was asked for an unlit night.

  DEFECT 2 — a material noun used in a PRESERVATION statement hijacked the edit
             class, so "make the brick building moonlit, preserving its brick
             facade" compiled to a cladding REPLACEMENT.

The RED section does not rely on a remembered result: disabling the two new
predicates (`_moonlit`, `_material_is_preserved`) restores the pre-change
decision path exactly, and the defects reappear. That proves both that the
defects were real and that these tests are sensitive to them.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import core.prompt_intelligence.image_edit_delta_v1 as delta_mod  # noqa: E402
from core.prompt_intelligence.image_edit_delta_v1 import (  # noqa: E402
    TIME_NIGHT,
    compile_edit_delta,
)
from core.vision.image_intent_v1 import detect_unsupported_geometry_edit  # noqa: E402

MOON_MARKER = "soft cool moonlight"
NAVY_MARKER = "navy-blue dark night sky"
DIRECTION_MARKER = "behind the camera"
MOON_ABSENT_MARKER = "outside the frame"
MINIMAL_MARKER = "deep shadows, no daylight"


def _d(text):
    return compile_edit_delta(text)


def _p(text):
    return compile_edit_delta(text)["delta_prompt"]


# ==========================================================
# 1. RED — the pre-change decision path, reproduced exactly
# ==========================================================

@pytest.fixture
def pre_change(monkeypatch):
    """Disable both new predicates, restoring the previous behaviour."""

    monkeypatch.setattr(delta_mod, "_moonlit", lambda haystack: False)
    monkeypatch.setattr(
        delta_mod, "_material_is_preserved",
        # 4th parameter added by HAIKU_ARCHITECTURAL_KNOWLEDGE_FIDELITY_V2
        # (the detected material, so preservation can be clause-scoped).
        lambda haystack, tod, style=None, material=None: False
    )


def test_red_moonlit_intent_is_lost_without_the_modifier(pre_change):
    """DEFECT 1, reproduced: every moonlit attribute disappears."""

    prompt = _p("Convert this building into a realistic moonlit night with a "
                "dark navy sky and soft cool moonlight on the facade.").lower()

    assert "moon" not in prompt
    assert "navy" not in prompt
    assert "cool" not in prompt
    # and it collapsed onto the ordinary night contract
    assert "lit by real ambient night light" in prompt


def test_red_material_preservation_misroutes_to_replacement(pre_change):
    """DEFECT 2, reproduced: a preserved material becomes a replacement."""

    delta = _d("Make the brick villa moonlit without changing its materials")

    assert delta["edit_class"] == "material_change"
    assert delta["material"] == "brick"
    assert "replace" in delta["delta_prompt"].lower()


def test_red_persian_preservation_misroutes(pre_change):
    delta = _d("ساختمان آجری را مهتابی کن، آجر نما حفظ شود")

    assert delta["edit_class"] == "material_change"


# ==========================================================
# 2. GREEN — moonlit requests keep the night class and the moonlight
# ==========================================================

MOONLIT_EN = [
    "Convert this building into a realistic moonlit night.",
    "Make it a moonlit night with a dark navy sky.",
    "Soft moonlight on the existing facade, night scene.",
    "Under moonlight, the building at night.",
    "Convert this building to night under a full moon.",
]

MOONLIT_FA = [
    "این ساختمان را در شب مهتابی واقعی تبدیل کن.",
    "نور مهتاب را روی نما بینداز، شب باشد.",
    "شب با نور ماه، آسمان سرمه‌ای.",
    "نور ماه روی ساختمان بتابد.",
]


@pytest.mark.parametrize("text", MOONLIT_EN + MOONLIT_FA)
def test_moonlit_request_stays_a_night_edit_and_carries_moonlight(text):
    delta = _d(text)

    assert delta["edit_class"] == "time_of_day_change", text
    assert delta["time_of_day"] == TIME_NIGHT, text

    prompt = delta["delta_prompt"]
    low = prompt.lower()

    # the illuminant is named
    assert MOON_MARKER in low
    # MOONLIGHT_DIRECTION_V1 — the light is related to the CAMERA and the
    # camera-facing surfaces, not just "somewhere on the exterior"
    assert DIRECTION_MARKER in low
    assert "camera-facing surfaces" in low
    assert "front-lit" in low
    # the moon is not drawn into the frame
    assert MOON_ABSENT_MARKER in low
    # the sky is navy, not a black void
    assert NAVY_MARKER in low
    # warm interior survives as a secondary source
    assert "warm interior" in low
    # night is still night
    assert "no daylight" in prompt


def test_moonlit_delta_names_readable_architectural_surfaces():
    prompt = _p("Make this a moonlit night.").lower()

    for element in ("facade", "roof", "walls", "columns", "entrance"):
        assert element in prompt, element

    assert "surface texture" in prompt
    assert "material colour" in prompt


def test_moonlit_delta_excludes_daylight_and_sunset():
    prompt = _p("Make this a moonlit night.").lower()

    assert "no daylight" in prompt
    assert "no sunset" in prompt
    # never affirmatively requests them
    assert "sunlit" not in prompt
    assert "golden hour" not in prompt
    assert "twilight" not in prompt
    assert "dawn" not in prompt


# ==========================================================
# 3. GREEN — moonlight must be grounded, never inferred
# ==========================================================

GENERIC_NIGHT = [
    "Convert this building to night.",
    "Make this building a realistic night scene.",
    "Turn this into a nighttime architectural photograph.",
    "این ساختمان را به شب واقعی تبدیل کن.",
    "Convert this building to a very dark night scene.",
]


@pytest.mark.parametrize("text", GENERIC_NIGHT)
def test_generic_night_is_not_upgraded_to_moonlit(text):
    prompt = _p(text)

    assert "moon" not in prompt.lower()
    assert "navy" not in prompt.lower()
    # the ordinary night contract is unchanged
    assert "lit by real ambient night light" in prompt


def test_minimal_illumination_outranks_moonlight():
    """An explicit almost-black request did not ask for a lit building."""

    prompt = _p("Convert this building to a moonlit night, but almost black "
                "with only the windows illuminated.")

    assert MINIMAL_MARKER in prompt
    assert "moonlight" not in prompt.lower()


# ==========================================================
# 4. GREEN — material preservation vs explicit replacement
# ==========================================================

def test_english_preservation_is_a_night_edit_with_material_protected():
    delta = _d("Make the brick villa moonlit without changing its materials")

    assert delta["edit_class"] == "time_of_day_change"
    assert delta["time_of_day"] == TIME_NIGHT
    assert delta["material"] is None
    assert delta["evidence"]["material_preserved"] == ["brick"]
    assert "moonlight" in delta["delta_prompt"].lower()
    assert "replace" not in delta["delta_prompt"].lower()


def test_persian_preservation_is_a_night_edit_with_material_protected():
    delta = _d("ساختمان آجری را مهتابی کن، آجر نما حفظ شود")

    assert delta["edit_class"] == "time_of_day_change"
    assert delta["time_of_day"] == TIME_NIGHT
    assert delta["material"] is None
    assert delta["evidence"]["material_preserved"] == ["آجر"]


def test_keep_the_facade_brick_is_a_night_edit():
    delta = _d("Keep the facade brick and make the sky moonlit")

    assert delta["edit_class"] == "time_of_day_change"
    assert delta["material"] is None
    assert "moonlight" in delta["delta_prompt"].lower()


@pytest.mark.parametrize("text,expected", [
    ("Replace the brick facade with stone", "stone"),
    ("نمای آجری را به سنگ تبدیل کن", "stone"),
    ("Change the facade material to travertine", "travertine"),
    ("Use wood instead of stone on the facade", "wood"),
])
def test_explicit_replacement_still_compiles_as_a_material_change(text, expected):
    delta = _d(text)

    assert delta["edit_class"] == "material_change", text
    assert delta["material"] == expected, text
    assert "replace" in delta["delta_prompt"].lower()


def test_replacement_and_lighting_together_are_not_silently_discarded():
    """F: both domains present — replacement owns the delta, the lighting
    request is recorded rather than dropped."""

    delta = _d("Make the building moonlit and replace brick with stone")

    assert delta["edit_class"] == "material_change"
    assert delta["material"] == "stone"
    assert delta["evidence"]["also_requested"] == ["time_of_day:night"]


def test_preservation_phrasing_does_not_suppress_a_real_replacement():
    """A request that both replaces and preserves must keep the replacement."""

    delta = _d("Replace the brick facade with stone, keeping the roof intact")

    assert delta["edit_class"] == "material_change"
    assert delta["material"] == "stone"


# ==========================================================
# 5. GREEN — accepted behaviour that must not move
# ==========================================================

def test_negated_dusk_still_resolves_to_night():
    delta = _d("این ساختمان را به شب واقعی تبدیل کن. آسمان باید واقعاً تاریک "
               "باشد، نه آبی روشن یا حالت گرگ‌ومیش.")

    assert delta["time_of_day"] == TIME_NIGHT
    assert delta["time_of_day"] != "dusk"
    assert "twilight" not in delta["delta_prompt"]


def test_night_to_day_is_still_day():
    delta = _d("Convert this night scene back to daylight.")

    assert delta["time_of_day"] == "day"
    assert "moon" not in delta["delta_prompt"].lower()
    assert "navy" not in delta["delta_prompt"].lower()


def test_day_sunset_sunrise_deltas_are_untouched():
    assert "sunlit facade" in _p("Convert this building to bright daylight.")
    assert "golden-hour" in _p("Convert this building to sunset.")
    assert "dawn sky" in _p("Convert this building to sunrise.")


@pytest.mark.parametrize("phrase", [
    "add a third floor",
    "طبقات را حفظ کن ولی یک طبقه اضافه کن",
    "Keep two floors, but add a third floor",
])
def test_floor_restructuring_guard_still_refuses(phrase):
    guard = detect_unsupported_geometry_edit(phrase)

    assert guard["unsupported"] is True
    assert guard["reason"] == "floor_count_restructuring_not_supported"


# ==========================================================
# 6. GENER ALITY — no image, no building, no geometry, no fixture
# ==========================================================

def test_moonlit_delta_is_general_not_image_specific():
    prompt = _p("Make this a moonlit night.").lower()

    for forbidden in ("brick", "villa", "portico", "chimney", "minab",
                      "project_", "09884e3a", "1792710363", "sha256"):
        assert forbidden not in prompt, forbidden


def test_moonlit_delta_adds_no_geometry_and_no_fixture():
    prompt = _p("Make this a moonlit night.").lower()

    for forbidden in ("add floor", "remove floor", "new window", "new door",
                      "move wall", "extend", "redesign",
                      "floodlight", "uplight", "spotlight", "wall washer",
                      "lamp post", "street lamp", "sconce", "fixture"):
        assert forbidden not in prompt, forbidden


# ==========================================================
# 7. MOONLIGHT_DIRECTION_V1 — light direction relative to the camera
#
# The first real moonlit render measured facade 4.4/255 against sky 7.4/255:
# the model lit the SKY, not the camera-facing building, because the delta
# said the moonlight "falls across the exterior" — a directionless phrase.
# It also drew a moon disc above the roofline. These tests pin the correction.
# ==========================================================

def test_moonlit_delta_relates_light_to_the_camera():
    low = _p("Make this a moonlit night.").lower()

    assert "front-lit" in low
    assert "behind the camera" in low
    assert "camera-facing surfaces" in low
    assert "elevated front-quarter direction" in low


def test_moonlit_delta_keeps_the_moon_out_of_frame():
    low = _p("Make this a moonlit night.").lower()

    assert "outside the frame" in low
    assert "not visible in the image" in low


def test_moonlit_delta_no_longer_invites_a_drawn_moon():
    """'from a high clear moon' is what produced the moon disc."""

    low = _p("Make this a moonlit night.").lower()

    assert "from a high clear moon" not in low
    assert "visible moon" not in low


def test_moonlit_delta_requests_no_artificial_fixture():
    low = _p("Make this a moonlit night.").lower()

    for forbidden in ("spotlight", "floodlight", "flood light", "uplight",
                      "up-light", "wall washer", "lamp", "sconce",
                      "artificial light", "light fixture"):
        assert forbidden not in low, forbidden


def test_moonlit_delta_keeps_shadows_directional_not_washed_out():
    low = _p("Make this a moonlit night.").lower()

    assert "directional" in low
    assert "washed out" in low
    assert "crushed to black" in low


def test_direction_correction_leaves_ordinary_night_untouched():
    low = _p("Convert this building to night.").lower()

    assert "behind the camera" not in low
    assert "camera-facing surfaces" not in low
    assert "outside the frame" not in low
    assert "lit by real ambient night light" in low


def test_direction_correction_leaves_minimal_night_untouched():
    low = _p("Convert this building to night. Make it almost black, with "
             "only the windows illuminated.").lower()

    assert "behind the camera" not in low
    assert MINIMAL_MARKER in low


def test_direction_correction_keeps_material_preservation():
    delta = _d("Make the brick villa moonlit without changing its materials")

    assert delta["edit_class"] == "time_of_day_change"
    assert delta["material"] is None
    assert delta["evidence"]["material_preserved"] == ["brick"]
    assert "behind the camera" in delta["delta_prompt"].lower()


def test_direction_correction_keeps_floor_guard():
    guard = detect_unsupported_geometry_edit("add a third floor")

    assert guard["unsupported"] is True


def test_moonlit_delta_requests_no_geometry_or_camera_change():
    low = _p("Make this a moonlit night.").lower()

    for forbidden in ("add floor", "remove floor", "new window", "new door",
                      "move wall", "extend", "redesign", "change the camera",
                      "move the camera"):
        assert forbidden not in low, forbidden
