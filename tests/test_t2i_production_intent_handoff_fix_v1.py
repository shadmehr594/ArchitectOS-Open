"""T2I_PRODUCTION_INTENT_HANDOFF_FIX_V1 — CPU-only production acceptance.

Deterministic, no GPU, no ComfyUI, no network, no render.

The six required architectural requirements of the acceptance request must
reach the RESOLVED render prompt through the REAL consumers:

    build_render_instruction -> build_constraint_block -> resolve_render_prompt

The request text is the exact text used by
`runs/t2i_visual_acceptance_v1/capture_production_payload.py`.

Nothing here hand-writes a replacement prompt: every string under test is
produced by the production modules, and the assertions only READ them.
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
from core.cognition.architectural_terminology_v1 import (
    normalize_architectural_terms,
)
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)
from core.render.render_preset_v1 import (
    build_quality_tail,
    resolve_preset,
)

#: The EXACT acceptance request (identical to the production capture script).
REQUEST = (
    "یک ساختمان مسکونی سه‌طبقه طراحی و رندر کن. ساختمان در مجموع سه طبقه روی "
    "زمین داشته باشد: همکف و دو طبقه بالای آن. نمای ساختمان دارای پنجره‌های "
    "بلند و قوسی باشد. دقیقاً یک در ورودی اصلی چوبی طراحی کن. برای بالکن نرده "
    "فلزی قرار بده و برای پشت‌بام جان‌پناه سنگی در نظر بگیر. تمام عناصر باید "
    "از نظر معماری قابل‌تشخیص و در محل صحیح باشند. یک نمای پرسپکتیو خارجی از "
    "ساختمان در نور روز تولید کن."
)


def _instruction(text):
    """The production instruction contract for one T2I request."""

    return build_render_instruction(
        text,
        mode="text_to_image",
        context={"mode": "text_to_image", "routing_source": "manual"},
    )


def _contract(text):
    instruction = _instruction(text)

    contract = dict(instruction)

    contract["constraint_block"] = build_constraint_block(instruction)

    return instruction, contract


def _final_prompt(text):
    instruction, contract = _contract(text)

    result = resolve_render_prompt(
        compiled_prompt=instruction.get("base_compiled_prompt"),
        architectural_instruction=contract,
    )

    return result


def _constraint_block(text):
    return _contract(text)[1]["constraint_block"]


def _sentences(block):
    """The per-feature sentences of a constraint block, prefix stripped."""

    return [
        part.strip()
        for part in str(block or "").split(FEATURE_SENTENCE_PREFIX)
        if part.strip()
    ]


def _sentence_for(block, element_word):
    for sentence in _sentences(block):
        if element_word in sentence:
            return sentence
    return ""


# ---------------------------------------------------------------------------
# 1. THE SIX REQUIRED REQUIREMENTS REACH THE RESOLVED PROMPT
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fragment", [
    # 1. exactly three above-ground storeys
    "The building has exactly 3 floors.",
    # 2. tall AND arched facade windows
    "include arched tall windows for the facade",
    # 3. exactly one wooden main entrance door, at the entrance
    "include exactly 1 wood door for the entrance",
    # 4. metal balcony railing
    "include metal railing for the balcony",
    # 5. stone rooftop parapet
    "include stone parapet for the rooftop",
])
def test_required_requirement_reaches_the_resolved_prompt(fragment):
    result = _final_prompt(REQUEST)

    assert result.get("instruction_applied") is True

    assert fragment in result.get("final_prompt", ""), (
        "requirement %r missing from the resolved prompt:\n%r"
        % (fragment, result.get("final_prompt"))
    )


def test_daytime_exterior_perspective_is_preserved():
    """Requirement 6 — the real terminology + preset consumers keep it."""

    terminology = normalize_architectural_terms(REQUEST)

    terms = terminology.get("canonical_terms") or []

    assert "perspective view" in terms
    assert "exterior space" in terms

    preset = resolve_preset(terminology)

    assert preset.get("name") == "exterior_day"

    assert "daylight" in build_quality_tail(preset.get("name"))


# ---------------------------------------------------------------------------
# 2. FORBIDDEN CLAIMS ARE ABSENT
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("forbidden", [
    "single floor building",
    "exactly 3 wood door",
    "exactly 3 wooden door",
    "wood doors for the entrance and rooftop",
    "door for the rooftop",
    "door for the entrance and rooftop",
    "tall windows for the rooftop",
    "stone railing for the balcony",
    "metal parapet",
])
def test_forbidden_claim_is_absent(forbidden):
    final = _final_prompt(REQUEST).get("final_prompt", "")

    assert forbidden not in final, (
        "forbidden claim %r reached the resolved prompt:\n%r"
        % (forbidden, final)
    )


# ---------------------------------------------------------------------------
# 3. THE DOOR: ONE, WOODEN, AT THE ENTRANCE — AND NOWHERE ELSE
# ---------------------------------------------------------------------------


def test_door_is_exactly_one_wooden_entrance_door():
    block = _constraint_block(REQUEST)

    sentence = _sentence_for(block, "door")

    assert "exactly 1 wood door" in sentence
    assert "for the entrance" in sentence

    # the storey count never becomes the door count
    assert "exactly 3" not in sentence

    # the door is never placed on the rooftop or the facade
    assert "rooftop" not in sentence
    assert "facade" not in sentence


def test_storey_count_is_never_an_element_count():
    """The validated floor count must stay a building property."""

    # "in total three storeys" is the BUILDING's storey count. It must never
    # become the count of the door named in the coordinated clause.
    leaked = next(
        r for r in _feature_requirements(
            "ساختمان در مجموع سه طبقه روی زمین داشته باشد و یک در چوبی اضافه کن"
        )
        if r["element"] == "door"
    )

    assert leaked["count"] is None, (
        "the storey count leaked into the door count"
    )

    # A genuine explicit quantity is still read: "exactly one door" is 1.
    explicit = next(
        r for r in _feature_requirements("دقیقاً یک در ورودی اصلی چوبی طراحی کن")
        if r["element"] == "door"
    )

    assert explicit["count"] == 1
    assert explicit["locations"] == ["entrance"]


# ---------------------------------------------------------------------------
# 4. THE WINDOWS: BOTH SHAPES SURVIVE COORDINATION
# ---------------------------------------------------------------------------


def test_windows_keep_tall_and_arched():
    block = _constraint_block(REQUEST)

    sentence = _sentence_for(block, "window")

    assert "tall" in sentence
    assert "arched" in sentence


# ---------------------------------------------------------------------------
# 5. RAILING AND PARAPET ARE DIFFERENT ELEMENTS
# ---------------------------------------------------------------------------


def test_balcony_railing_and_rooftop_parapet_are_distinct():
    block = _constraint_block(REQUEST)

    railing = _sentence_for(block, "railing")
    parapet = _sentence_for(block, "parapet")

    assert "metal railing" in railing
    assert "for the balcony" in railing
    assert "rooftop" not in railing

    assert "stone parapet" in parapet
    assert "for the rooftop" in parapet
    assert "balcony" not in parapet


# ---------------------------------------------------------------------------
# 6. DECIMAL DIMENSIONS ARE NOT QUANTITIES
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "add a tall window 3.5 m",
    "add a tall window 3.5m",
    "add a 2.4 m wide window",
    "add a 2.4m wide window",
    "add 2 m tall windows",
])
def test_decimal_dimension_is_not_a_count(text):
    reqs = _feature_requirements(text)

    assert reqs, "no requirement extracted for: %s" % text

    assert reqs[0]["count"] is None, (
        "a dimension became a count for %r: %r" % (text, reqs[0].get("count"))
    )

    final = _final_prompt(text).get("final_prompt", "")

    assert "exactly" not in final, (
        "a dimension produced an explicit quantity for %r:\n%r" % (text, final)
    )


@pytest.mark.parametrize("text,count", [
    ("add 3 arched windows", 3),
    ("add two arched windows", 2),
    ("add a single wooden door at the entrance", 1),
])
def test_real_quantities_still_reach_the_prompt(text, count):
    """The fix must not silence a genuine count."""

    assert _feature_requirements(text)[0]["count"] == count

    final = _final_prompt(text).get("final_prompt", "")

    assert "exactly %d" % count in final


# ---------------------------------------------------------------------------
# 7. PERSIAN "در" — THE NOUN VS THE PREPOSITION
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "در مجموع سه طبقه روی زمین داشته باشد",
    "ساختمان در مجموع سه طبقه دارد",
    "پنجره‌ها را در نظر بگیر",
    "در محل صحیح قرار بده",
])
def test_prepositional_dar_is_not_a_door(text):
    assert not any(
        r["element"] == "door" for r in _feature_requirements(text)
    ), "the preposition 'در' invented a door in %r" % text


def test_coordinated_dar_still_names_a_door():
    reqs = _feature_requirements(
        "ساختمان در مجموع سه طبقه دارد و یک در چوبی اضافه کن"
    )

    door = next(r for r in reqs if r["element"] == "door")

    assert door["material"] == "wood"
    assert door["count"] is None


# ---------------------------------------------------------------------------
# 8. NEGATION / PRESERVATION / OBSERVATION CONTROLS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "پنجره اضافه نکن",
    "پنجره‌ها را حفظ کن",
    "تعداد پنجره‌ها را بررسی کن",
    "هندسه ساختمان را تغییر نده",
    "لیست کن که چند پنجره دارد",
])
def test_no_feature_reaches_the_block(text):
    assert FEATURE_SENTENCE_PREFIX not in _constraint_block(text)


def test_removal_then_addition_keeps_only_the_addition():
    reqs = {r["element"] for r in _feature_requirements(
        "در را حذف کن و پنجره اضافه کن"
    )}

    assert reqs == {"window"}


def test_preservation_then_addition_keeps_only_the_addition():
    reqs = {r["element"] for r in _feature_requirements(
        "پنجره‌ها را حفظ کن و در چوبی اضافه کن"
    )}

    assert reqs == {"door"}


# ---------------------------------------------------------------------------
# 9. MULTI-ELEMENT REQUESTS KEEP INDEPENDENT ATTRIBUTES
# ---------------------------------------------------------------------------


def test_multi_element_attributes_do_not_cross():
    reqs = {
        r["element"]: r
        for r in _feature_requirements(
            "add arched windows to the facade and a single wooden door at the "
            "entrance"
        )
    }

    window, door = reqs["window"], reqs["door"]

    assert window["shapes"] == ["arched"]
    assert window["count"] is None
    assert window["locations"] == ["facade"]
    assert window["material"] is None

    assert door["count"] == 1
    assert door["material"] == "wood"
    assert door["locations"] == ["entrance"]
    assert door["shapes"] == []


def test_railing_and_parapet_keep_their_own_material_and_location():
    reqs = {
        r["element"]: r
        for r in _feature_requirements(
            "نرده فلزی برای بالکن و جان‌پناه سنگی برای پشت‌بام طراحی کن"
        )
    }

    assert reqs["railing"]["material"] == "metal"
    assert reqs["railing"]["locations"] == ["balcony"]

    assert reqs["parapet"]["material"] == "stone"
    assert reqs["parapet"]["locations"] == ["rooftop"]