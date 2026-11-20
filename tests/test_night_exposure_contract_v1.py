"""ARCHITECTURAL_NIGHT_EXPOSURE_V1 — night exposure contract regression.

WHY THIS FILE EXISTS
====================
The accepted Kontext night output (`06b6f644…`) was a correct night scene but a
professionally underexposed architectural image: facade at luma 1–2/255, 30.6 %
of the frame at pure black, only the windows readable.

Root cause (verified): `_DELTA_TIME_OF_DAY[TIME_NIGHT]` described the night
ENVIRONMENT (dark sky, no daylight, deep shadows) and the LIGHT SOURCES
(interior glow, exterior landscape lighting) but never required the
architectural SUBJECT to stay readable — while `TIME_DAY` did
("sunlit facade"). The model satisfied the instruction literally.

Night environment and subject visibility are complementary. This suite pins the
corrected contract and, just as importantly, pins the escape: a request that
explicitly asks for a minimally lit building must stay minimal.

CPU ONLY. NO GPU. NO COMFYUI. NO OLLAMA. NO NETWORK.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.prompt_intelligence.image_edit_delta_v1 import (  # noqa: E402
    TIME_NIGHT,
    compile_edit_delta,
    is_classified as is_classified_edit_delta,
)
from core.render.workflow_selector import WorkflowSelector  # noqa: E402
from core.vision.image_intent_v1 import detect_unsupported_geometry_edit  # noqa: E402

VISIBILITY_MARKER = "clearly brighter than the sky"
MINIMAL_MARKER = "deep shadows, no daylight"


def _delta(text):
    return compile_edit_delta(text)


def _has_visibility(delta):
    return VISIBILITY_MARKER in delta["delta_prompt"]


# ==========================================================
# 1. THE NIGHT CONTRACT ITSELF
# ==========================================================

PLAIN_NIGHT_REQUESTS = [
    "Convert this building to night.",
    "Make this building a realistic night scene.",
    "Convert this building to true night, not blue hour.",
    "Turn this into a nighttime architectural photograph.",
    "این ساختمان را به شب واقعی تبدیل کن.",
    "این ساختمان را شب کن.",
    "Convert this building to a very dark night scene.",
]


@pytest.mark.parametrize("text", PLAIN_NIGHT_REQUESTS)
def test_night_request_carries_subject_visibility(text):
    delta = _delta(text)

    assert delta["edit_class"] == "time_of_day_change"
    assert delta["edit_target"] == "scene"
    assert delta["time_of_day"] == TIME_NIGHT

    # the night ENVIRONMENT must still be asserted ...
    assert "dark night sky" in delta["delta_prompt"]
    assert "no daylight" in delta["delta_prompt"]

    # ... and so must the SUBJECT visibility that was missing
    assert _has_visibility(delta), delta["delta_prompt"]

    # no contradictory daylight survives
    assert "natural lighting" not in delta["delta_prompt"]


def test_night_contract_is_general_not_image_specific():
    """The contract must not encode any particular building."""

    prompt = _delta("Convert this building to night.")["delta_prompt"].lower()

    for forbidden in ("brick", "villa", "portico", "chimney", "minab"):
        assert forbidden not in prompt, forbidden


# ==========================================================
# 2. THE ESCAPE — INTENTIONALLY DARK MUST STAY DARK
# ==========================================================

MINIMAL_REQUESTS = [
    "Convert this building to night. Make it almost black, with only the "
    "windows illuminated.",
    "Convert this building to night with no exterior lighting.",
    "Convert this building to night. Keep the facade in darkness, only the "
    "windows illuminated.",
    "این ساختمان را به شب تبدیل کن. فقط پنجره ها روشن باشند و نما در تاریکی بماند.",
    "این ساختمان را شب کن، تقریباً سیاه با فقط پنجره های روشن.",
]


@pytest.mark.parametrize("text", MINIMAL_REQUESTS)
def test_explicit_minimal_illumination_is_respected(text):
    delta = _delta(text)

    assert delta["edit_class"] == "time_of_day_change"
    assert delta["time_of_day"] == TIME_NIGHT

    assert not _has_visibility(delta), (
        "An explicit minimal-illumination request was brightened: %r" % (text,)
    )
    assert MINIMAL_MARKER in delta["delta_prompt"]


def test_bare_almost_black_without_night_is_not_brightened():
    """No night reference means no time-of-day contract at all.

    `black` is a colour signal, so this pre-existing classification is a
    colour edit. The exposure contract must not attach a visibility clause to
    it either.
    """

    delta = _delta(
        "Make this building intentionally almost black, with only its "
        "windows illuminated."
    )

    assert delta["time_of_day"] is None
    assert not _has_visibility(delta)


# ==========================================================
# 3. GATE D — THE SEVEN SEMANTIC DISTINCTIONS
# ==========================================================

def test_d1_night_with_readable_architecture():
    delta = _delta(
        "Make this building a realistic night scene with readable architecture."
    )
    assert delta["edit_class"] == "time_of_day_change"
    assert delta["time_of_day"] == TIME_NIGHT
    assert _has_visibility(delta)


def test_d2_true_night_not_blue_hour():
    delta = _delta("Convert this building to true night, not blue hour.")
    assert delta["edit_class"] == "time_of_day_change"
    assert delta["time_of_day"] == TIME_NIGHT
    assert delta["time_of_day"] != "dusk"
    assert "twilight" not in delta["delta_prompt"]


def test_d3_intentional_darkness_preserved():
    delta = _delta(
        "Convert this building to night. Make it almost black, with only the "
        "windows illuminated."
    )
    assert delta["time_of_day"] == TIME_NIGHT
    assert not _has_visibility(delta)


def test_d4_night_back_to_daylight():
    delta = _delta("Convert this night scene back to daylight.")
    assert delta["edit_class"] == "time_of_day_change"
    assert delta["time_of_day"] == "day"
    assert "night" not in delta["delta_prompt"].lower().replace("no night", "")


def test_d5_material_only_does_not_touch_lighting():
    delta = _delta(
        "Change the facade material to travertine without changing its lighting."
    )
    assert delta["edit_class"] == "material_change"
    assert delta["edit_target"] == "facade"
    assert delta["material"] == "travertine"
    assert delta["time_of_day"] is None
    assert "natural lighting" not in delta["delta_prompt"]


def test_d6_preserved_night_exposure_with_material_change():
    delta = _delta(
        "Preserve the existing nighttime exposure while changing only the "
        "facade material to stone."
    )
    assert delta["edit_class"] == "material_change"
    assert delta["material"] == "stone"
    # a material edit asserts no lighting condition of its own
    assert delta["time_of_day"] is None


def test_d7_lighting_only_edit():
    delta = _delta(
        "Keep the existing building and change only the architectural lighting."
    )
    assert delta["time_of_day"] is None
    assert delta["edit_class"] in ("lighting_change", "generic_edit")


# ==========================================================
# 4. NO GEOMETRY INSTRUCTIONS, NO REGRESSION IN THE GUARDS
# ==========================================================

def test_night_delta_adds_no_geometry_instruction():
    prompt = _delta("Convert this building to night.")["delta_prompt"].lower()

    for forbidden in ("add floor", "remove floor", "new window", "new door",
                      "move wall", "extend", "redesign"):
        assert forbidden not in prompt, forbidden


@pytest.mark.parametrize("phrase", [
    "add a third floor",
    "طبقات را حفظ کن ولی یک طبقه اضافه کن",
    "Keep two floors, but add a third floor",
])
def test_floor_change_guard_still_refuses(phrase):
    guard = detect_unsupported_geometry_edit(phrase)
    assert guard["unsupported"] is True
    assert guard["reason"] == "floor_count_restructuring_not_supported"


def test_negation_handling_intact():
    # the polarity repair must still read the rejected dusk phrase correctly
    delta = _delta(
        "این ساختمان را به شب واقعی تبدیل کن. آسمان باید واقعاً تاریک باشد، "
        "نه آبی روشن یا حالت گرگ‌ومیش."
    )
    assert delta["time_of_day"] == TIME_NIGHT
    assert delta["time_of_day"] != "dusk"


# ==========================================================
# 5. ROUTING CONTRACT UNCHANGED
# ==========================================================

def test_night_edit_selects_kontext_without_a_mask():
    delta = _delta("Convert this building to night.")
    assert is_classified_edit_delta(delta)

    selected = WorkflowSelector().select({
        "engine": "flux",
        "mode": "img2img",
        "image": "source.png",
        "kontext_edit": True,
    })

    assert selected == "flux_kontext_edit.json"


def test_masked_request_still_selects_kontext():
    selected = WorkflowSelector().select({
        "engine": "flux",
        "mode": "img2img",
        "image": "source.png",
        "mask": {"filename": "m.png"},
    })
    assert selected == "flux_kontext_edit.json"


def test_plain_edit_without_kontext_still_uses_img2img():
    selected = WorkflowSelector().select({
        "engine": "flux",
        "mode": "img2img",
        "image": "source.png",
    })
    assert selected == "flux_img2img.json"


# ==========================================================
# 6. NIGHT_FACADE_LIGHTING_V1 — THE THREE-WAY DISTINCTION
#
# The previous visibility clause was measured to fail on GPU. These tests
# assert the properties that were missing, on the REAL compiled delta:
#   (a) the sky is dark AND the exterior is lit AND warm interior light
#       survives -- three separate, non-contradictory statements;
#   (b) the luminance ORDERING is stated (exterior brighter than sky), which
#       is the physical fact a night architectural photograph exhibits and
#       the exact relationship the failed output inverted;
#   (c) the light sources are ambient night light and window spill -- no
#       invented fixtures, no invented architecture.
# ==========================================================

FACADE_LIGHTING_REQUESTS = [
    # the task's own acceptance text
    "همین ساختمان را به شب واقعی تبدیل کن. آسمان تاریک باشد، اما نمای "
    "خارجی، سقف، ستون‌ها و ورودی ساختمان با نور محیطی طبیعی شب و نورپردازی "
    "ملایم معماری به‌وضوح قابل مشاهده باشند. نور گرم پنجره‌ها حفظ شود. شکل "
    "ساختمان و تمام عناصر معماری ثابت بمانند.",
    # the same request in English, and a bare one
    "Convert this building to a real night with a dark sky, but the exterior "
    "facade, roof, columns and entrance must be clearly visible under natural "
    "night ambient light and soft architectural lighting.",
    "Convert this building to night.",
]


@pytest.mark.parametrize("text", FACADE_LIGHTING_REQUESTS)
def test_night_delta_separates_sky_exterior_and_interior(text):
    delta = _delta(text)
    assert delta["time_of_day"] == TIME_NIGHT
    prompt = delta["delta_prompt"]

    # 1. dark sky is still asserted
    assert "dark night sky" in prompt
    assert "no daylight" in prompt

    # 2. the exterior is asserted as LIT, not merely "readable"
    assert "lit by real ambient night light" in prompt
    assert "clearly brighter than the sky" in prompt

    # 3. warm interior light is preserved as its own statement
    assert "warm interior lighting" in prompt.lower()
    assert "windows" in prompt.lower()


def test_night_delta_states_the_luminance_ordering():
    """The failure was an ORDERING failure: sky 2.63 > facade 1.26 /255.

    A delta that does not state which of the two is brighter leaves the model
    free to reproduce that inversion.
    """

    prompt = _delta("Convert this building to night.")["delta_prompt"].lower()

    assert "brighter than the sky" in prompt
    assert prompt.index("brighter than the sky") < prompt.index("warm interior")


def test_night_delta_names_the_surface_not_just_the_facade():
    """Roof and openings must be lit too -- the previous clause named three
    elements and the roof still rendered at 3-5/255."""

    prompt = _delta("Convert this building to night.")["delta_prompt"].lower()

    for element in ("facade", "roof", "walls", "entrance"):
        assert element in prompt, element


def test_night_delta_invents_no_fixture_and_no_architecture():
    prompt = _delta("Convert this building to night.")["delta_prompt"].lower()

    for forbidden in ("floodlight", "uplight", "up-light", "spotlight",
                      "wall washer", "lamp post", "street lamp", "sconce",
                      "led strip", "fixture"):
        assert forbidden not in prompt, forbidden


def test_night_delta_drops_the_hedges_that_weakened_it():
    """'subtle' and 'fill light' were the two hedges measured to have no
    effect; 'remain clearly readable' was an evaluation, not a scene."""

    prompt = _delta("Convert this building to night.")["delta_prompt"].lower()

    assert "subtle" not in prompt
    assert "fill light" not in prompt
    assert "remain clearly readable" not in prompt


def test_night_delta_is_not_special_cased_to_any_image():
    """No project id, hash, seed, filename or place name may enter the delta."""

    prompt = _delta("Convert this building to night.")["delta_prompt"].lower()

    for forbidden in ("project_", "09884e3a", "68a3addd", "1792710363",
                      "minab", "render_001", "sha256"):
        assert forbidden not in prompt, forbidden


def test_minimal_night_delta_is_unchanged_and_still_dark():
    """The escape hatch must not inherit the new illumination language."""

    delta = _delta(
        "Convert this building to night. Make it almost black, with only the "
        "windows illuminated."
    )
    prompt = delta["delta_prompt"]

    assert MINIMAL_MARKER in prompt
    assert "clearly brighter than the sky" not in prompt
    assert "ambient night light" not in prompt
