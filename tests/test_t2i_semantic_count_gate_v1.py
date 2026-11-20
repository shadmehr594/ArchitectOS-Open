"""T2I_FINAL_COUNT_GATE_V1 — semantic count gate (CPU only).

The single confirmed blocker of `ARCHITECTOS_T2I_VISUAL_ACCEPTANCE_V2.md`:

    نرده فلزی بالکن و جانپناه سنگی پشت‌بام دو عنصر متفاوت هستند
    -> include exactly 2 stone parapet for the rooftop      (WRONG)

"دو عنصر متفاوت" describes a relationship between two element TYPES. It is not
a quantity of parapets.

The correction is narrow: a numeral that QUALIFIES an element-type noun
("عنصر/نوع/گونه", "element/type/kind") is not read as a count of this element.
A numeral that qualifies the element itself ("دو جانپناه سنگی") still counts.

No GPU. No ComfyUI. No render.
"""

import sys

sys.path.insert(0, ".")

import pytest

from core.cognition.architectural_render_instruction_v1 import (
    FEATURE_SENTENCE_PREFIX,
    _feature_requirements,
    build_constraint_block,
    build_render_instruction,
)

#: The exact production clause that produced the false count.
PRODUCTION_CLAUSE = (
    "نرده فلزی بالکن و جان‌پناه سنگی پشت‌بام دو عنصر متفاوت هستند و باید در محل "
    "صحیح خودشان قرار بگیرند"
)


def _count_of(text, element):
    """The count extracted for ``element``, or a sentinel when absent."""

    requirements = {r["element"]: r for r in _feature_requirements(text)}

    if element not in requirements:

        return "ABSENT"

    return requirements[element]["count"]


# ---------------------------------------------------------------------------
# 1. ELEMENT-TYPE RELATIONSHIPS ARE NOT QUANTITIES
# ---------------------------------------------------------------------------


def test_production_clause_has_no_invented_parapet_count():
    """The exact production blocker: 'دو عنصر متفاوت' must not be 2 parapets."""

    assert _count_of(PRODUCTION_CLAUSE, "parapet") in (None, "ABSENT")


@pytest.mark.parametrize("text", [
    "جانپناه سنگی و نرده فلزی دو عنصر متفاوت هستند",
    "دو عنصر متفاوت هستند و جانپناه سنگی اضافه کن",
    "دو نوع جانپناه سنگی اضافه کن",
    "two different elements and add a stone parapet",
    "2 elements differ and add a stone parapet",
])
def test_element_type_statement_never_becomes_a_count(text):
    assert _count_of(text, "parapet") in (None, "ABSENT"), (
        "an element-TYPE statement became a parapet count for %r" % text
    )


def test_the_same_numeral_still_counts_a_real_element():
    """'دو جانپناه سنگی' IS a quantity; only the type statement is ignored."""

    text = "دو جانپناه سنگی روی پشت‌بام طراحی کن"

    assert _count_of(text, "parapet") == 2


def test_type_statement_does_not_silence_a_separate_real_quantity():
    text = "دو عنصر متفاوت هستند و دو جانپناه سنگی اضافه کن"

    assert _count_of(text, "parapet") == 2


# ---------------------------------------------------------------------------
# 2. EXPLICIT QUANTITIES KEEP WORKING
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text,element,count", [
    ("دقیقاً یک در چوبی اضافه کن", "door", 1),
    ("دو پنجره قوسی اضافه کن", "window", 2),
    ("add 3 arched windows", "window", 3),
    ("add a single wooden door at the entrance", "door", 1),
])
def test_explicit_quantity_is_still_read(text, element, count):
    assert _count_of(text, element) == count


def test_dimension_is_still_not_a_count():
    assert _count_of("add a tall window 3.5m", "window") is None
    assert _count_of("add a tall window 3.5 m", "window") is None


# ---------------------------------------------------------------------------
# 3. NO CROSS-CLAUSE COUNT TRANSFER
# ---------------------------------------------------------------------------


def test_floor_count_never_becomes_a_door_or_parapet_count():
    reqs = {
        r["element"]: r
        for r in _feature_requirements("سه طبقه و یک در ورودی طراحی کن")
    }

    # The storey numeral must not migrate into the door's count.
    assert reqs["door"]["count"] != 3

    # Documented rule: a BARE "یک" is the Persian indefinite article, so it is
    # deliberately not a count. A REINFORCED "دقیقاً یک" is (see §2 above).
    assert reqs["door"]["count"] is None


def test_floor_count_reaches_the_contract():
    instruction = build_render_instruction(
        "سه طبقه و یک در ورودی طراحی کن",
        mode="text_to_image",
        context={"mode": "text_to_image"},
    )

    block = build_constraint_block(instruction)

    assert "exactly 3 floors" in block


# ---------------------------------------------------------------------------
# 4. NEGATION / PRESERVATION / OBSERVATION CONTROLS ARE UNCHANGED
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "پنجره اضافه نکن",
    "پنجره‌ها را حفظ کن",
    "تعداد پنجره‌ها را بررسی کن",
    "هندسه ساختمان را تغییر نده",
])
def test_no_feature_reaches_the_block(text):
    block = build_constraint_block(build_render_instruction(text))

    assert FEATURE_SENTENCE_PREFIX not in block


def test_removal_then_addition_keeps_only_the_addition():
    """A refused feature is never resurrected by a following coordination."""

    elements = {r["element"] for r in _feature_requirements(
        "در را حذف کن و پنجره اضافه کن"
    )}

    assert elements == {"window"}