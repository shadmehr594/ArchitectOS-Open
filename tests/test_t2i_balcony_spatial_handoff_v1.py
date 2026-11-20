"""T2I_BALCONY_SPATIAL_HANDOFF_V1 — spatial intent handoff (CPU only).

The one blocker left by `ARCHECTOS_T2I_FINAL_COUNT_GATE_V1.md`:

    {"name": "balcony", "properties": {"location": "upper_floors"}}
    -> "balcony placed naturally in architectural scene"

The semantic intent DID carry the validated upper-floor location and the
railing->balcony attachment; the positive prompt builder threw both away.

These tests cover the handoff and every regression check the mission lists.

No GPU. No ComfyUI. No render.
"""

import sys

sys.path.insert(0, ".")

import pytest

from core.render.prompt_builder import (
    PromptBuilder,
    _object_attachment_phrase,
    _object_location_phrase,
    _object_property_source,
    _object_spatial_phrase,
)

from core.cognition.architectural_render_instruction_v1 import (
    FEATURE_SENTENCE_PREFIX,
    _feature_requirements,
    build_constraint_block,
    build_render_instruction,
)


#: The exact V2 Persian production request (same text the preflight gate used).
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

#: The object list the semantic intent actually produced for that request.
V2_OBJECTS = [
    {"name": "entrance_door",
     "properties": {"material": "wood", "count": 1,
                    "location": "ground_floor"}},
    {"name": "balcony",
     "properties": {"location": "upper_floors", "visibility": "distinctive"}},
    {"name": "balcony_railing",
     "properties": {"material": "metal", "attached_to": "balcony"}},
    {"name": "rooftop_parapet",
     "properties": {"material": "stone", "location": "rooftop"}},
]

#: The SAME intent in the FLAT shape, captured from a later production run of
#: the identical request: the understanding layer emits both carriers, so the
#: handoff must read both.
V2_OBJECTS_FLAT = [
    {"name": "main_entrance_door", "material": "wood", "count": 1,
     "location": "ground_floor"},
    {"name": "balcony", "location": "upper_floors",
     "feature": "distinctive_and_visible"},
    {"name": "balcony_railing", "material": "metal", "location": "balcony"},
    {"name": "rooftop_parapet", "material": "stone", "location": "rooftop"},
    {"name": "windows", "shape": "tall_arched", "location": "facade"},
]

BASE_INTENT = {
    "building_type": "residential",
    "style": "contemporary",
    "floors": 3,
    "materials": ["wood", "metal", "stone"],
    "environment": ["exterior"],
}


def _description(objects):
    intent = dict(BASE_INTENT)
    intent["objects"] = objects

    built = PromptBuilder().build({"architectural_intent": intent})

    return built["description"] if isinstance(built, dict) else str(built)


def _object_segment(description, name):
    for segment in description.split(", "):
        if segment.startswith(name):
            return segment
    return ""


# ---------------------------------------------------------------------------
# 1. THE HANDOFF — LOCATION IS PRESERVED
# ---------------------------------------------------------------------------


def test_validated_upper_floor_location_reaches_the_prompt():
    description = _description(V2_OBJECTS)

    assert (
        "balcony on an upper floor placed naturally in architectural scene"
        in description
    )


def test_upper_floor_is_not_narrowed_to_a_specific_floor():
    """The user said "upper floors", never WHICH upper floor."""

    description = _description(V2_OBJECTS).lower()

    for invented in ("first floor", "second floor", "third floor",
                     "top floor", "1st floor", "2nd floor"):
        assert invented not in description


# ---------------------------------------------------------------------------
# 1b. THE FLAT CARRIER — SAME CLAIM, DIFFERENT SHAPE
# ---------------------------------------------------------------------------


def test_flat_object_properties_are_read_too():
    """A production run emitted `location` at the object's top level."""

    description = _description(V2_OBJECTS_FLAT)

    assert (
        "balcony on an upper floor placed naturally in architectural scene"
        in description
    )


def test_both_shapes_agree_on_the_spatial_claim():
    nested = {
        obj["name"]: _object_spatial_phrase(
            obj["name"], _object_property_source(obj)
        )
        for obj in V2_OBJECTS
    }
    flat = {
        obj["name"]: _object_spatial_phrase(
            obj["name"], _object_property_source(obj)
        )
        for obj in V2_OBJECTS_FLAT
    }

    for name in ("balcony", "rooftop_parapet"):
        assert nested[name] == flat[name]


def test_nested_properties_win_when_both_carriers_are_present():
    obj = {
        "name": "balcony",
        "location": "ground_floor",          # flat carrier
        "properties": {"location": "upper_floors"},   # nested carrier
    }

    assert _object_property_source(obj) == {"location": "upper_floors"}


def test_property_source_of_a_non_object_is_empty():
    for value in (None, "balcony", ["balcony"], 7):
        assert _object_property_source(value) == {}


def test_flat_shape_never_promotes_an_unstated_floor():
    description = _description([
        {"name": "balcony", "feature": "distinctive"},
        {"name": "railing", "material": "metal"},
    ])

    assert "balcony placed naturally in architectural scene" in description
    assert "upper floor" not in description
    assert "ground floor" not in description


def test_ground_floor_balcony_is_not_promoted():
    description = _description(
        [{"name": "balcony", "properties": {"location": "ground_floor"}}]
    )

    assert "balcony on the ground floor" in description
    assert "upper floor" not in description


@pytest.mark.parametrize("properties", [
    {},
    {"location": ""},
    {"location": None},
    {"location": "unknown"},
    {"location": "second_floor"},
    {"location": "4th storey, rear wing"},
])
def test_unknown_floor_never_invents_a_location(properties):
    description = _description([{"name": "balcony", "properties": properties}])

    assert "balcony placed naturally in architectural scene" in description

    for invented in ("ground floor", "upper floor", "rooftop", "terrace"):
        assert invented not in description


def test_location_already_implied_by_the_name_is_not_repeated():
    """`rooftop_parapet` already says rooftop; it is not said twice."""

    description = _description(V2_OBJECTS)

    assert (
        "rooftop_parapet placed naturally in architectural scene" in description
    )
    assert "rooftop_parapet on the rooftop" not in description


# ---------------------------------------------------------------------------
# 2. THE HANDOFF — ATTACHMENT IS PRESERVED, AND NOTHING IS SWAPPED
# ---------------------------------------------------------------------------


def test_railing_is_attached_to_the_balcony_not_the_rooftop():
    description = _description(V2_OBJECTS)

    assert (
        "balcony_railing attached to the balcony placed naturally "
        "in architectural scene" in description
    )

    railing = _object_segment(description, "balcony_railing").lower()

    assert "rooftop" not in railing


def test_rooftop_parapet_never_becomes_a_railing():
    description = _description(V2_OBJECTS)

    parapet = _object_segment(description, "rooftop_parapet").lower()

    assert "railing" not in parapet
    assert "balcony" not in parapet


def test_attachment_to_another_element_is_kept_as_stated():
    description = _description(
        [{"name": "railing", "properties": {"attached_to": "rooftop parapet"}}]
    )

    assert "railing attached to the rooftop parapet" in description


@pytest.mark.parametrize("value", [
    None,
    "",
    "unknown",
    "none",
    "null",
    "it",
    "the building",
    "x" * 41,
    "balcony; drop table",
])
def test_invalid_attachment_target_is_never_spoken(value):
    assert _object_attachment_phrase(value) == ""


def test_attachment_is_only_spoken_for_a_known_target():
    description = _description([{"name": "railing", "properties": {}}])

    assert "attached to" not in description


# ---------------------------------------------------------------------------
# 3b. MODE ISOLATION — I2I / EDIT MUST NOT INHERIT TEXT SPATIAL PHRASES
# ---------------------------------------------------------------------------


def test_image_edit_modes_do_not_inherit_the_text_spatial_phrases():
    from core.prompt_intelligence.prompt_router import PromptRouter

    intent = dict(BASE_INTENT)
    intent["objects"] = V2_OBJECTS_FLAT

    router = PromptRouter()

    text = router.build(
        {"architectural_intent": intent, "prompt": "x"}, mode="text2img"
    )["description"]

    assert "on an upper floor" in text

    for mode in ("img2img", "image_edit", "edit"):

        edited = router.build(
            {"architectural_intent": intent, "prompt": "x"}, mode=mode
        )["description"]

        assert "on an upper floor" not in edited
        assert "rooftop" not in edited.lower()


# ---------------------------------------------------------------------------
# 3. EXISTING BUILDER BEHAVIOUR IS PRESERVED
# ---------------------------------------------------------------------------


def test_string_objects_are_unaffected():
    description = _description(["an old oak tree"])

    assert (
        "an old oak tree placed naturally in architectural scene" in description
    )


def test_car_and_pool_mappings_are_unaffected():
    description = _description([
        {"name": "car", "properties": {"color": "red"}},
        {"name": "pool", "properties": {}},
    ])

    assert "parked naturally in front of the building" in description
    assert "swimming pool integrated with landscape beside the house" in description


def test_objects_without_properties_are_unaffected():
    description = _description([{"name": "bench"}])

    assert "bench placed naturally in architectural scene" in description


def test_spatial_phrase_is_empty_without_structured_properties():
    assert _object_spatial_phrase("balcony", None) == ""
    assert _object_spatial_phrase("balcony", "upper_floors") == ""
    assert _object_spatial_phrase("balcony", ["upper_floors"]) == ""


# ---------------------------------------------------------------------------
# 4. THE CONSTRAINT LAYER IS UNCHANGED (requirements A, B, C, E, F)
# ---------------------------------------------------------------------------


def _block(text=V2_REQUEST):
    return build_constraint_block(
        build_render_instruction(
            text,
            mode="text_to_image",
            context={"mode": "text_to_image"},
        )
    )


def test_arched_tall_windows_and_single_wooden_door_are_preserved():
    block = _block()

    assert "arched tall windows for the facade" in block
    assert "exactly 1 wood door for the entrance" in block


def test_exactly_three_storeys_are_preserved():
    block = _block()

    assert "exactly 3 floors" in block
    assert "single floor building" not in block


def test_metal_railing_and_stone_parapet_stay_separate():
    block = _block()

    assert "metal railing for the balcony" in block
    assert "stone parapet for the rooftop" in block
    assert "metal parapet" not in block
    assert "stone railing" not in block


def test_the_fake_exactly_2_stone_parapet_never_returns():
    assert "exactly 2 stone parapet" not in _block()

    assert _object_location_phrase("balcony", "upper_floors")


def test_dimension_35m_is_still_not_a_count():
    requirements = {
        r["element"]: r
        for r in _feature_requirements("add a tall window 3.5m")
    }

    assert requirements["window"]["count"] is None


@pytest.mark.parametrize("text", [
    "پنجره اضافه نکن",
    "پنجره‌ها را حفظ کن",
    "تعداد پنجره‌ها را بررسی کن",
    "هندسه ساختمان را تغییر نده",
])
def test_preservation_and_negation_instructions_remain_intact(text):
    block = build_constraint_block(build_render_instruction(text))

    assert FEATURE_SENTENCE_PREFIX not in block


def test_only_one_effective_door_requirement_reaches_the_prompt():
    """Incidental Persian prepositions must add no SECOND door requirement.

    "قابل‌تشخیص در طبقات بالایی طراحی کن" contains the preposition "در"
    ("in"), not a door. The request states ONE door, so the block must state
    exactly one.
    """

    block = _block()

    assert block.lower().count("door") == 1
    assert "include doors" not in block