"""AUTHORITATIVE_SPATIAL_FRAMING_RETENTION_V1 — CPU-only acceptance.

Two legitimate, user-validated requirements were lost at the authoritative
T2I handoff when the second builder pass was skipped:

  * the balcony's UPPER-FLOOR location
  * the explicit whole-building framing requirement

They survived only in the discarded builder tail. These tests prove they are
carried by the EXISTING authoritative carriers (feature requirements and the
bounded RenderConstraintBlockV1), and — equally important — that nothing is
invented for a request that never stated them.

No GPU, no ComfyUI, no render.
"""

import pytest

from core.cognition.architectural_render_instruction_v1 import (
    FEATURE_SENTENCE_PREFIX,
    WHOLE_BUILDING_FRAMING_SENTENCE,
    _feature_requirements,
    _whole_building_visibility,
    build_constraint_block,
    build_render_instruction,
)


#: The exact request whose payload failed visual acceptance.
V2_REQUEST = (
    "یک ساختمان مسکونی سه‌طبقه طراحی و رندر کن. ساختمان در مجموع سه طبقه روی "
    "زمین داشته باشد: همکف و دو طبقه بالای آن. نمای ساختمان دارای پنجره‌های "
    "بلند و قوسی باشد. دقیقاً یک در ورودی اصلی چوبی طراحی کن. برای ساختمان "
    "بالکنی مشخص و قابل‌تشخیص در طبقات بالایی طراحی کن و برای همان بالکن نرده "
    "فلزی قرار بده. برای پشت‌بام جانپناه سنگی در نظر بگیر. نرده فلزی بالکن و "
    "جانپناه سنگی پشت‌بام دو عنصر متفاوت هستند و باید در محل صحیح خودشان قرار "
    "بگیرند. تمام عناصر باید از نظر معماری قابل‌تشخیص باشند. یک نمای پرسپکتیو "
    "خارجی از کل ساختمان در نور روز تولید کن، به‌طوریکه هر سه طبقه، ورودی، "
    "بالکن و بام دیده شوند."
)


def requirements(text):
    return {item["element"]: item for item in _feature_requirements(text)}


def block(text):
    return build_constraint_block(build_render_instruction(text, mode="text2img"))


# ---------------------------------------------------------------------------
# 1. THE BALCONY'S FLOOR IS PRESERVED
# ---------------------------------------------------------------------------

def test_balcony_is_a_requirement_with_its_stated_floor():
    found = requirements(V2_REQUEST)

    assert "balcony" in found

    assert found["balcony"]["floors"] == ["upper floor"]


def test_balcony_floor_reaches_the_constraint_block():
    text = block(V2_REQUEST)

    assert "include balcony on the upper floor" in text


def test_balcony_part_and_floor_are_not_confused():
    """The part ("balcony") and the floor ("upper floor") stay distinct."""

    assert "include balcony for the balcony" not in block(V2_REQUEST)


def test_a_the_railing_keeps_its_own_scope():
    """Adding the balcony requirement must not steal the railing's clause."""

    found = requirements(V2_REQUEST)

    assert found["railing"]["material"] == "metal"

    assert found["railing"]["locations"] == ["balcony"]

    assert found["railing"]["floors"] == []


def test_no_specific_storey_is_invented():
    lowered = block(V2_REQUEST).lower()

    for invented in ("first floor", "second floor", "third floor", "top floor"):
        assert invented not in lowered


def test_balcony_without_a_stated_floor_invents_none():
    found = requirements("یک ساختمان سه طبقه با بالکن طراحی کن")

    if "balcony" in found:
        assert found["balcony"]["floors"] == []

    assert "on the upper floor" not in block(
        "یک ساختمان سه طبقه با بالکن طراحی کن"
    )


# ---------------------------------------------------------------------------
# 2. THE WHOLE-BUILDING FRAMING IS PRESERVED
# ---------------------------------------------------------------------------

def test_whole_building_framing_is_detected():
    assert _whole_building_visibility(V2_REQUEST)


def test_whole_building_framing_reaches_the_constraint_block():
    assert WHOLE_BUILDING_FRAMING_SENTENCE in block(V2_REQUEST)


def test_whole_building_framing_is_absent_when_not_requested():
    for text in (
        "یک ساختمان مسکونی سه طبقه طراحی و رندر کن.",
        "یک نمای نزدیک از جزئیات نمای سنگی ساختمان سه طبقه رندر کن.",
        "یک ساختمان سه طبقه با پنجره‌های قوسی طراحی کن.",
    ):
        assert not _whole_building_visibility(text), text

        assert WHOLE_BUILDING_FRAMING_SENTENCE not in block(text), text


def test_whole_building_scope_of_work_is_not_a_camera_request():
    """"Renovate the WHOLE building" is scope, not framing."""

    assert not _whole_building_visibility(
        "کل ساختمان را بازسازی کن و نما را تغییر بده"
    )


def test_a_view_without_a_whole_building_noun_is_not_this_constraint():
    assert not _whole_building_visibility("نمای جنوبی ساختمان را رندر کن")


# ---------------------------------------------------------------------------
# 3. THE REGRESSIONS THIS FIX MUST NOT REINTRODUCE
# ---------------------------------------------------------------------------

def test_previous_contradictions_stay_absent():
    text = block(V2_REQUEST)

    lowered = text.lower()

    assert "single floor building" not in lowered

    for style in (
        "french classical", "beaux arts", "second empire", "french provincial",
    ):
        assert style not in lowered

    assert "the building has exactly 3 floors" in lowered


def test_floor_count_never_migrates_to_an_element():
    text = block(V2_REQUEST)

    assert "exactly 3 wood" not in text

    assert "exactly 3 balcony" not in text


def test_negation_still_authorises_nothing():
    """The negation is stated INSIDE the clause it governs.

    The shared splitter breaks "… و … اضافه نکن" into two fragments, so a
    prohibition written across the coordination is a pre-existing limitation
    of the splitter, not of this fix. Stated in one clause, it must authorise
    nothing — including the new located-part path.
    """

    assert requirements("بالکن در طبقات بالایی اضافه نکن") == {}

    assert requirements("نرده فلزی بالکن اضافه نکن") == {}


def test_observation_still_authorises_nothing():
    found = requirements(
        "بالکن در طبقات بالایی و نرده فلزی را فقط لیست کن"
    )

    assert found == {}


# ---------------------------------------------------------------------------
# 4. UNRELATED SPATIAL REQUESTS ARE NOT TREATED IDENTICALLY
# ---------------------------------------------------------------------------

def test_ground_floor_placement_is_carried_as_ground():
    text = block(
        "یک ساختمان دو طبقه با ایوان در طبقه همکف و نرده فلزی برای همان ایوان"
    )

    assert "on the ground floor" in text

    assert "on the upper floor" not in text


@pytest.mark.parametrize(
    "floor_phrase,expected",
    [
        ("در طبقات بالایی", "upper floor"),
        ("در طبقه بالا", "upper floor"),
        ("on the upper floor", "upper floor"),
    ],
)
def test_upper_floor_phrasings_all_resolve(floor_phrase, expected):
    found = requirements("برای ساختمان بالکنی مشخص " + floor_phrase + " طراحی کن")

    assert found["balcony"]["floors"] == [expected]


def test_single_wood_door_keeps_its_exact_count():
    text = block("یک ساختمان سه طبقه با دقیقاً یک در ورودی چوبی طراحی کن")

    assert "exactly 1 wood door for the entrance" in text
