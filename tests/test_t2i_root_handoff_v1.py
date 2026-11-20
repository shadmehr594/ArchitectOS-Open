"""ROOT_HANDOFF_V1 — regression tests for the shared intent -> prompt handoff.

The corrections under test all live at ONE boundary: the structured
architectural intent handed to the sampler prompt. Each test states the class
property, not one example:

1. element IDENTITY comes from the clause's own order ("which element is this
   clause about"), never from the element table's report order;
2. a clause that only REFERENCES another element donates nothing to it;
3. a word has ONE owner: naming a LOCATION is not naming an element;
4. attribute SCOPE stops at the first mention of a different element;
5. the "در" homograph is resolved by the clause's STRUCTURE and by the
   module's own vocabularies, not by a list of fittings;
6. a decimal dimension is spliced before ANY consumer reads the clauses.

CPU only: no GPU, no ComfyUI job, no render.
"""

import sys

import pytest

sys.path.insert(0, ".")

from core.cognition.architectural_render_instruction_v1 import (  # noqa: E402
    _feature_requirements,
    build_constraint_block,
    build_render_instruction,
)

Z = "\u200c"


def requirements(text):

    return {item["element"]: item for item in _feature_requirements(text)}


def block(text):

    return build_constraint_block(
        build_render_instruction(
            text, mode="text_to_image", context={"mode": "text_to_image"}
        )
    )


# ---------------------------------------------------------------------------
# 1 — the "در" homograph: a location phrase, not a door
# ---------------------------------------------------------------------------

LOCATION_CASES = [
    ("در نما پنجره بگذار", "window", ["facade"], None),
    ("در پشت" + Z + "بام یک نورگیر بگذار", "window", ["rooftop"], None),
    ("در پشتبام یک نورگیر بگذار", "window", ["rooftop"], None),
    ("در راه" + Z + "پله پنجره نورگیر بگذار", "window", ["staircase"], None),
    ("در تراس نرده فلزی بگذار", "railing", ["terrace"], "metal"),
    ("در پشت" + Z + "بام جانپناه سنگی بگذار", "parapet", ["rooftop"], "stone"),
    ("در طبقات بالایی پنجره بگذار", "window", [], None),
    ("در طبقات پایین نرده فلزی بگذار", "railing", [], "metal"),
    ("در طبقهای دیگر پنجره قوسی بگذار", "window", [], None),
]


@pytest.mark.parametrize("text,element,locations,material", LOCATION_CASES)
def test_door_homograph_resolves_to_the_location(
    text, element, locations, material
):

    found = requirements(text)

    assert "door" not in found

    assert element in found

    assert found[element]["locations"] == locations

    assert found[element]["material"] == material


def test_location_phrase_does_not_fabricate_a_door_in_the_prompt():

    text = "در پشت" + Z + "بام جانپناه سنگی بگذار"

    assert "door" not in block(text)

    assert "stone parapet for the rooftop" in block(text)


DOOR_COMPOUND_CASES = [
    ("دقیقاً یک در ورودی چوبی طراحی کن", "wood", ["entrance"], 1),
    ("دو در چوبی روی نما اضافه کن", "wood", ["facade"], 2),
    ("در ورودی فلزی برای ورودی اضافه کن", "metal", ["entrance"], None),
    ("در بالکن یک در چوبی بگذار", "wood", ["balcony"], None),
    ("در نما یک در چوبی بگذار", "wood", ["facade"], None),
]


@pytest.mark.parametrize("text,material,locations,count", DOOR_COMPOUND_CASES)
def test_genuine_door_compounds_keep_the_noun_reading(
    text, material, locations, count
):

    found = requirements(text)

    assert list(found) == ["door"]

    assert found["door"]["material"] == material

    assert found["door"]["locations"] == locations

    assert found["door"]["count"] == count


def test_door_compound_next_to_another_element_stays_a_door():

    found = requirements("در ورودی و پنجره قوسی اضافه کن")

    assert set(found) == {"door", "window"}

    assert found["door"]["locations"] == ["entrance"]

    assert found["window"]["shapes"] == ["arched"]


# ---------------------------------------------------------------------------
# 2 and 4 — identity by clause order, and a reference donates nothing
# ---------------------------------------------------------------------------

def test_parapet_clause_that_refers_to_the_railing_stays_a_parapet():

    text = (
        "جانپناه سنگی پشت" + Z + "بام هم داشته باشد که با نرده بالکن "
        "متفاوت باشد"
    )

    found = requirements(text)

    assert set(found) == {"parapet"}

    assert found["parapet"]["material"] == "stone"

    assert found["parapet"]["locations"] == ["rooftop"]


def test_reference_clause_does_not_donate_its_location():

    text = (
        "برای همان بالکن نرده فلزی قرار بده. "
        "جانپناه سنگی پشت" + Z + "بام هم داشته باشد که با نرده بالکن "
        "متفاوت باشد"
    )

    found = requirements(text)

    assert found["railing"]["locations"] == ["balcony"]

    assert found["parapet"]["locations"] == ["rooftop"]


def test_comparison_wording_is_not_a_request():

    text = "نرده فلزی بالکن با جانپناه سنگی پشت" + Z + "بام فرق دارد."

    found = requirements(text)

    assert found["railing"]["locations"] == ["balcony"]

    assert "parapet" not in found

    assert "door" not in found


def test_element_table_order_no_longer_decides_identity():

    # window is named before door; the TABLE reports door first.
    assert list(requirements("یک پنجره چوبی و یک در فلزی اضافه کن")) == [
        "window",
        "door",
    ]


# ---------------------------------------------------------------------------
# 3 — one owner per word: a LOCATION is not an element
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "برای پشت" + Z + "بام کاشی بگذار",
        "لبه بام را بپوشان",
        "برای روف کاشی بگذار",
    ],
)
def test_naming_a_rooftop_never_builds_a_parapet(text):

    assert "parapet" not in requirements(text)


def test_rooftop_is_still_reported_as_the_parapet_location():

    found = requirements("جانپناه سنگی پشت" + Z + "بام اضافه کن")

    assert found["parapet"]["locations"] == ["rooftop"]


# ---------------------------------------------------------------------------
# 5 — a decimal dimension is spliced before anything reads the clauses
# ---------------------------------------------------------------------------

def test_decimal_dimension_does_not_drop_the_element():

    found = requirements(
        "یک پنجره بلند و قوسی به ارتفاع ۳.۵ متر روی نما بگذار"
    )

    assert set(found) == {"window"}

    assert found["window"]["shapes"] == ["arched", "tall"]

    assert found["window"]["locations"] == ["facade"]

    assert found["window"]["count"] is None


def test_dimension_is_never_a_count():

    assert "exactly 3" not in block("add a 2.4 m wide window on the facade")

    assert "exactly 5" not in block("add a 2.4 m wide window on the facade")


# ---------------------------------------------------------------------------
# 6 — safeguards that must not move
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "پنجره اضافه نکن",
        "نرده را حذف کن",
        "پنجرهها را دست نزن",
        "تعداد پنجرهها را بررسی کن",
        "هندسه ساختمان را تغییر نده",
    ],
)
def test_negation_observation_and_preservation_authorise_nothing(text):

    assert requirements(text) == {}


def test_preservation_still_reaches_the_prompt():

    assert (
        "do NOT move or relocate the windows"
        in block("پنجرهها را دست نزن")
    )


def test_floor_count_never_migrates_to_an_element():

    text = "ساختمان سه طبقه طراحی کن و یک در ورودی چوبی بگذار."

    text_block = block(text)

    assert "exactly 3 floors" in text_block

    assert "exactly 3 wood" not in text_block