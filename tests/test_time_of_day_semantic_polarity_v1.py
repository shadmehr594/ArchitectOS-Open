"""Bounded CPU-only regression for time-of-day polarity and direction."""

import pytest

from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta


EXACT_ACCEPTANCE_REQUEST = (
    "همین ساختمان را به شب واقعی تبدیل کن. نور روز و روشنایی محیط را به "
    "نورپردازی طبیعی شب تغییر بده. آسمان باید واقعاً تاریک باشد، نه آبی "
    "روشن یا حالت گرگ‌ومیش. چراغ‌های موجود و روشنایی داخل ساختمان متناسب "
    "با شب دیده شوند. تعداد طبقات، شکل سقف، پنجره‌ها، دودکش‌ها، درها، "
    "ورودی، مصالح، بالکن‌ها، نرده‌ها، ابعاد و زاویه دوربین را تغییر نده و "
    "هیچ عنصر معماری جدیدی اضافه نکن."
)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("ساختمان را شب کن", "night"),
        ("به شب واقعی تبدیل کن", "night"),
        ("ساختمان را به شب واقعی تبدیل کن، نه گرگ‌ومیش", "night"),
        ("شب باشد، نه غروب", "night"),
        ("از روز به شب تبدیل کن", "night"),
        ("غروب را به شب تبدیل کن", "night"),
        ("از شب به روز تبدیل کن", "day"),
        ("نه شب، بلکه غروب", "dusk"),
        ("صبح را به غروب تبدیل کن", "dusk"),
        (EXACT_ACCEPTANCE_REQUEST, "night"),
        ("Make this building night, not twilight", "night"),
        ("Convert from dusk to midnight", "night"),
        ("Turn this nighttime scene into daylight", "day"),
        ("Not night, but dusk", "dusk"),
        ("Change the lighting to evening, not noon", "dusk"),
    ],
)
def test_affirmative_target_beats_source_or_rejected_state(text, expected):
    delta = compile_edit_delta(text)

    assert delta["edit_class"] == "time_of_day_change"
    assert delta["time_of_day"] == expected
    assert delta["evidence"]["time_of_day"]


@pytest.mark.parametrize(
    "text, forbidden",
    [
        ("گرگ‌ومیش نباشد", "dusk"),
        ("ساختمان را شب نکن", "night"),
        ("Do not make it night", "night"),
    ],
)
def test_rejected_state_does_not_fabricate_a_positive_target(text, forbidden):
    delta = compile_edit_delta(text)

    assert delta["time_of_day"] != forbidden
    assert delta["edit_class"] != "time_of_day_change"
    assert "time_of_day" not in delta["evidence"]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("ساختمان را به شب تبدیل کن؛ نه گرگ و میش.", "night"),
        ("ساختمان را به شب تبدیل کن - نه twilight!", "night"),
        ("Not night; but dusk.", "dusk"),
        ("Turn this nighttime scene into daylight.", "day"),
    ],
)
def test_punctuation_and_spacing_variants(text, expected):
    assert compile_edit_delta(text)["time_of_day"] == expected


@pytest.mark.parametrize(
    "text",
    [
        "The source image is currently dusk.",
        "تصویر فعلی در غروب است.",
    ],
)
def test_declarative_source_context_is_not_a_requested_target(text):
    delta = compile_edit_delta(text)

    assert delta["edit_class"] != "time_of_day_change"
    assert delta["time_of_day"] is None


def test_exact_acceptance_prompt_is_true_night_and_preserves_architecture():
    delta = compile_edit_delta(EXACT_ACCEPTANCE_REQUEST)
    prompt = delta["prompt"]
    evidence = delta["evidence"]["time_of_day"]

    assert delta["edit_class"] == "time_of_day_change"
    assert delta["time_of_day"] == "night"
    assert "true architectural night" in prompt
    assert "dark night sky" in prompt
    assert "realistic nighttime exposure" in prompt
    assert "do not redesign the building" in prompt
    assert "do not change the volume, floor count" in prompt
    assert "blue-hour architectural photography" not in prompt
    assert "deep blue twilight sky" not in prompt
    assert "fading warm horizon glow" not in prompt
    assert "گرگ‌ومیش" not in evidence
    assert "twilight" not in evidence

