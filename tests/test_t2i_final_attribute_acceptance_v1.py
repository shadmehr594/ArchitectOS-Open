"""T2I_FINAL_ATTRIBUTE_ACCEPTANCE_V1 — shape and explicit count survival.

CPU only. No GPU, no ComfyUI, no render.

MEASURED DEFECT (closed here)
-----------------------------
`_feature_requirements()` extracted element / group / material / locations but
never SHAPE or explicit COUNT, and `_feature_sentence()` never emitted them.
Three requests therefore lost part of their own requirement before the
constraint block was ever built:

  * "add tall windows"            -> "include windows"          (tall lost)
  * "add arched windows"          -> "include windows"          (arched lost)
  * "add a single wooden door"    -> "include wood doors"       (count lost)

These tests assert the attribute reaches the FINAL PROMPT through the
production chain:

    build_render_instruction -> build_constraint_block -> resolve_render_prompt

and assert the real `ChatArchitect._explicit_text_to_image_turn` guard, not a
copy of its condition.
"""

import sys

sys.path.insert(0, ".")

import pytest

from core.cognition.architectural_render_instruction_v1 import (
    FEATURE_SENTENCE_PREFIX,
    _feature_count,
    _feature_requirements,
    _feature_sentence,
    _feature_shapes,
    build_constraint_block,
    build_render_instruction,
)
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)

# ---------------------------------------------------------------------------
# helpers — the production chain, exactly as chat_architect/render_runtime use
# ---------------------------------------------------------------------------


def _block(text):
    return build_constraint_block(build_render_instruction(text))


def _final_prompt(text):
    instr = build_render_instruction(text)
    contract = dict(instr)
    contract["constraint_block"] = build_constraint_block(instr)
    result = resolve_render_prompt(
        compiled_prompt=instr.get("base_compiled_prompt"),
        architectural_instruction=contract,
    )
    return result


# ---------------------------------------------------------------------------
# 1. SHAPE extraction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text,shape", [
    ("add tall windows to the facade", "tall"),
    ("add arched windows to the facade", "arched"),
    ("پنجره‌های بلند به نما اضافه کن", "tall"),
    ("پنجره‌های قوسی به نما اضافه کن", "arched"),
    ("add a semi-circular window to the facade", "semi-circular"),
    ("add a round window to the facade", "circular"),
    ("add a wide entrance door", "wide"),
])
def test_shape_is_extracted(text, shape):
    reqs = _feature_requirements(text)
    assert reqs, "no requirement extracted for: %s" % text
    assert shape in reqs[0]["shapes"], (
        "shape %r missing from %r for: %s" % (shape, reqs[0], text)
    )


def test_specific_shape_wins_over_contained_one():
    """'semi-circular' must not also be reported as the 'circular' it contains."""
    assert _feature_shapes("add a semi-circular window") == ["semi-circular"]


def test_no_shape_is_invented():
    reqs = _feature_requirements("add tall windows to the facade")
    door = _feature_requirements("add a wooden door at the entrance")
    assert "arched" not in reqs[0]["shapes"]
    assert door[0]["shapes"] == [], "a shape was invented for a plain door"


def test_shape_word_boundary():
    """'background' must not yield the shape 'round'; 'widespread' not 'wide'."""
    assert _feature_shapes("add background windows") == []
    assert _feature_shapes("add widespread windows") == []


def test_comparative_is_not_a_shape():
    """'taller'/'بلندتر' name a change, never the absolute shape 'tall'."""
    assert _feature_shapes("make the windows taller") == []
    assert _feature_shapes("پنجره‌ها را بلندتر کن") == []


# ---------------------------------------------------------------------------
# 2. COUNT extraction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text,count", [
    ("add a single wooden door at the entrance", 1),
    ("add one tall window", 1),
    ("add two arched windows", 2),
    ("add three wooden doors at the entrance", 3),
    ("دو پنجره قوسی به نما اضافه کن", 2),
    ("سه‌تا در چوبی اضافه کن", 3),
    ("فقط یک در چوبی اضافه کن", 1),
])
def test_explicit_count_is_extracted(text, count):
    req = _feature_requirements(text)[0]
    assert req["count"] == count, (
        "count %r not extracted from %r (got %r)"
        % (count, text, req.get("count"))
    )


@pytest.mark.parametrize("text", [
    "add tall windows to the facade",
    "add arched windows to the facade",
    "یک پنجره بلند اضافه کن",
    "add wooden doors at the entrance",
    "پنجره‌های بلند به نما اضافه کن",
])
def test_no_count_is_invented(text):
    """A bare plural, or Persian's indefinite 'یک', states no count."""
    req = _feature_requirements(text)[0]
    assert req["count"] is None, (
        "a count was invented for %r: %r" % (text, req.get("count"))
    )


def test_count_word_is_not_matched_inside_a_longer_word():
    """Persian 'دو' (two) is a substring of 'دوم' (second)."""
    assert _feature_count("پنجره‌های طبقه دوم") is None


def test_double_leaf_is_not_a_count():
    """'دو لنگه' is a leaf configuration, not a count of doors."""
    req = _feature_requirements("یک در دو لنگه چوبی اضافه کن")
    assert req and req[0]["count"] is None


@pytest.mark.parametrize("text,count", [
    ("add 3 arched windows", 3),
    ("4 پنجره قوسی اضافه کن", 4),
    ("۲ پنجره قوسی اضافه کن", 2),
])
def test_digit_count_is_extracted(text, count):
    """A numeral states a count in either script and either word order."""
    req = _feature_requirements(text)[0]
    assert req["count"] == count


@pytest.mark.parametrize("text", [
    "add a 2.4 m wide window",
    "add a 2.4m wide window",
    "add 2 m tall windows",
    "add a tall window 3.5 m",
    # The clause splitter breaks on ".", so the first half ends in a bare "3";
    # an ATTACHED unit ("3.5m") must not let that "3" become a count.
    "add a tall window 3.5m",
])
def test_dimension_is_not_a_count(text):
    """A dimension measures the element; it must never become a count."""
    req = _feature_requirements(text)[0]
    assert req["count"] is None, (
        "a dimension became a count for %r: %r" % (text, req.get("count"))
    )


# ---------------------------------------------------------------------------
# 3. EMISSION — the sentence states what the user stated
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text,expected", [
    ("add tall windows to the facade", "tall windows"),
    ("add arched windows to the facade", "arched windows"),
    ("add a single wooden door at the entrance", "exactly 1 wood door"),
    ("add two arched windows", "arched windows"),
    ("پنجره‌های بلند به نما اضافه کن", "tall windows"),
    ("پنجره‌های قوسی به نما اضافه کن", "arched windows"),
])
def test_sentence_states_the_attribute(text, expected):
    sentence = _feature_sentence(_feature_requirements(text)[0])
    assert sentence.startswith(FEATURE_SENTENCE_PREFIX)
    assert expected in sentence, (
        "expected %r in %r" % (expected, sentence)
    )


def test_count_two_is_emitted_as_plural():
    sentence = _feature_sentence(_feature_requirements("add two arched windows")[0])
    assert "exactly 2 arched windows" in sentence


def test_sentence_without_attributes_is_unchanged():
    """A plain request must render exactly as it did before this change."""
    sentence = _feature_sentence(
        {"element": "window", "group": "opening", "material": None,
         "locations": ["facade"], "shapes": [], "count": None}
    )
    assert sentence == (
        "REQUIRED ARCHITECTURAL FEATURE — include windows for the facade, "
        "an opening in the building envelope; render it visibly."
    )


def test_legacy_requirement_dict_has_no_attributes():
    """A requirement built without the new keys must still render."""
    sentence = _feature_sentence(
        {"element": "door", "group": "opening", "material": "wood",
         "locations": []}
    )
    assert "include wood doors" in sentence


# ---------------------------------------------------------------------------
# 4. ATTRIBUTION — attributes never cross between elements
# ---------------------------------------------------------------------------


def test_attributes_do_not_cross_elements():
    reqs = _feature_requirements(
        "add arched windows to the facade and a single wooden door at the "
        "entrance"
    )
    by_element = {r["element"]: r for r in reqs}
    window, door = by_element["window"], by_element["door"]
    assert window["shapes"] == ["arched"]
    assert window["count"] is None
    assert window["material"] is None
    assert door["shapes"] == []
    assert door["count"] == 1
    assert door["material"] == "wood"
    assert door["locations"] == ["entrance"]
    assert window["locations"] == ["facade"]


def test_material_and_location_still_attributed_per_clause():
    reqs = _feature_requirements("add a metal guardrail to the balcony")
    req = next(r for r in reqs if r["element"] == "railing")
    assert req["material"] == "metal"
    assert req["locations"] == ["balcony"]


# ---------------------------------------------------------------------------
# 5. PRODUCTION CHAIN — the attribute reaches final_prompt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text,expected", [
    ("add tall windows to the facade", "tall windows"),
    ("add arched windows to the facade", "arched windows"),
    ("add a single wooden door at the entrance", "exactly 1 wood door"),
    ("پنجره‌های بلند به نما اضافه کن", "tall windows"),
    ("پنجره‌های قوسی به نما اضافه کن", "arched windows"),
    ("یک در ورودی چوبی به نما اضافه کن", "wood doors"),
])
def test_attribute_reaches_final_prompt(text, expected):
    result = _final_prompt(text)
    assert result.get("instruction_applied") is True, (
        "instruction not applied for: %s" % text
    )
    final = result.get("final_prompt", "")
    assert FEATURE_SENTENCE_PREFIX in final
    assert expected in final, (
        "expected %r in final_prompt for %r\nfinal: %r"
        % (expected, text, final)
    )


def test_block_is_deterministic():
    text = "add tall arched windows to the facade"
    assert _block(text) == _block(text)


def test_block_keeps_the_feature_within_budget():
    """The feature sentence is never crowded out by the 1100-char budget."""
    from core.cognition.architectural_render_instruction_v1 import (
        CONSTRAINT_BLOCK_BUDGET,
    )
    block = _block(
        "add a single stone wooden door with a tall arched frame to the "
        "south facade and a metal guardrail to the balcony"
    )
    assert block
    assert len(block) <= CONSTRAINT_BLOCK_BUDGET
    assert FEATURE_SENTENCE_PREFIX in block


# ---------------------------------------------------------------------------
# 6. REGRESSION — requests that ask for no feature are untouched
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "نمای ساختمان را با سنگ پوشش بده",
    "در ورودی اضافه نکن",
    "لیست کن که چند پنجره دارد",
    "make the windows taller",
])
def test_no_feature_no_block(text):
    assert FEATURE_SENTENCE_PREFIX not in _block(text)


# ---------------------------------------------------------------------------
# 7. THE REAL T2I / I2I GUARD
#
# The guard is `ChatArchitect._explicit_text_to_image_turn`. It is exercised on
# a real ChatArchitect instance — never on a re-implementation of its
# condition, which is what the previous test in this repository did.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_chat():
    import types

    from core.chat.chat_architect import ChatArchitect

    return ChatArchitect(types.SimpleNamespace())


@pytest.mark.parametrize("context,expected", [
    ({"routing_source": "manual", "mode": "text_to_image"}, True),
    ({"routing_source": "manual", "mode": "image_to_image"}, False),
    ({"routing_source": "auto", "mode": "text_to_image"}, False),
    ({"routing_source": "manual"}, False),
    ({"mode": "text_to_image"}, False),
    ({}, False),
    (None, False),
])
def test_real_t2i_guard(real_chat, context, expected):
    assert real_chat._explicit_text_to_image_turn(context) is expected


def test_real_guard_is_fail_closed_on_unreadable_mode(real_chat):
    assert real_chat._explicit_text_to_image_turn(
        {"routing_source": "manual", "mode": object()}
    ) is False


# ---------------------------------------------------------------------------
# 8. COORDINATED DESCRIPTIONS (PERSIAN_COORDINATION_FIX_V1)
#
# The shared clause splitter breaks on "و" / "and". These tests pin the LOCAL
# recovery in `_segment_scope`: the fragments coordination separated are
# re-united for EXTRACTION only. `split_clauses` itself is not changed, and
# every authorisation / negation test still runs on the result.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text,expected", [
    # coordination split a shape list from its element and verb
    ("پنجره‌های بلند و قوسی به نما اضافه کن",
     {"window": (["arched", "tall"], None, None, ["facade"])}),
    # a coordinated descriptor before the element (English)
    ("add tall and arched windows to the facade",
     {"window": (["arched", "tall"], None, None, ["facade"])}),
    # two elements, one shared verb: each keeps its own attributes
    ("یک در چوبی و دو پنجره قوسی اضافه کن",
     {"door": ([], None, "wood", []),
      "window": (["arched"], 2, None, [])}),
    # two protection elements, each with its own material and location
    ("نرده فلزی برای بالکن و جان‌پناه سنگی برای پشت‌بام طراحی کن",
     {"railing": ([], None, "metal", ["balcony"]),
      "parapet": ([], None, "stone", ["rooftop"])}),
])
def test_coordinated_request_keeps_every_attribute(text, expected):
    reqs = {r["element"]: r for r in _feature_requirements(text)}
    assert set(reqs) == set(expected), (
        "elements extracted for %r: %r" % (text, sorted(reqs))
    )
    for element, (shapes, count, material, locations) in expected.items():
        req = reqs[element]
        assert req["shapes"] == shapes, (text, element, req)
        assert req["count"] == count, (text, element, req)
        assert req["material"] == material, (text, element, req)
        assert req["locations"] == locations, (text, element, req)


@pytest.mark.parametrize("text,expected", [
    ("پنجره‌های بلند و قوسی به نما اضافه کن", "arched tall windows"),
    ("add tall and arched windows to the facade", "arched tall windows"),
    ("یک در چوبی و دو پنجره قوسی اضافه کن", "wood doors"),
])
def test_coordinated_request_reaches_final_prompt(text, expected):
    final = _final_prompt(text).get("final_prompt", "")
    assert expected in final, (
        "expected %r in final_prompt for %r\nfinal: %r"
        % (expected, text, final)
    )


def test_coordinated_door_does_not_inherit_the_window_shape():
    """The door in a shared-verb list must not become arched, nor count 2."""
    reqs = {r["element"]: r for r in _feature_requirements(
        "یک در چوبی و دو پنجره قوسی اضافه کن"
    )}
    door = reqs["door"]
    assert door["shapes"] == []
    assert door["count"] is None
    assert door["material"] == "wood"


@pytest.mark.parametrize("text", [
    "پنجره اضافه نکن",
    "پنجره‌های بلند و قوسی نصب نکن",
    "تعداد پنجره‌ها را بررسی کن",
    "هندسه ساختمان را تغییر نده",
    "پنجره‌ها را حفظ کن",
    "پنجره‌ها را حفظ کن و در چوبی اضافه کن",
    "add arched windows and no door",
])
def test_coordination_does_not_resurrect_a_refused_feature(text):
    """A negated, observed or preserved element is never a request."""
    # Deterministic per case: which element the request genuinely asks for.
    allowed = {
        "پنجره‌ها را حفظ کن و در چوبی اضافه کن": {"door"},
        "add arched windows and no door": {"window"},
    }.get(text, set())
    for req in _feature_requirements(text):
        assert req["element"] in allowed, (text, req)


def test_removal_then_addition_keeps_only_the_addition():
    reqs = _feature_requirements("در را حذف کن و پنجره اضافه کن")
    assert [r["element"] for r in reqs] == ["window"]
    assert reqs[0]["shapes"] == []


# ---------------------------------------------------------------------------
# 9. FINAL PROMPT SEMANTIC CONSISTENCY
#
# These assert the RESOLVED `final_prompt` — the string the sampler receives —
# not the intermediate constraint block. Two semantic defects only became
# visible at that layer:
#
#   * a removal was compiled as `Replace the windows expression`;
#   * a preserved element was announced as the scope of change.
# ---------------------------------------------------------------------------


def test_removal_is_never_compiled_as_a_replacement():
    """`حذف` is a removal, not a replace of whatever element was scanned."""
    final = _final_prompt("در را حذف کن و پنجره اضافه کن").get("final_prompt", "")
    assert "Replace the windows expression" not in final
    assert "Remove the existing doors" in final, (
        "the removal must be stated explicitly\nfinal: %r" % final
    )


def test_removal_does_not_suppress_the_coordinated_addition():
    final = _final_prompt("در را حذف کن و پنجره اضافه کن").get("final_prompt", "")
    assert "include windows" in final, final


def test_preserved_element_is_not_announced_as_the_scope_of_change():
    """The window is protected here; the change is the wooden door."""
    final = _final_prompt("پنجره‌ها را حفظ کن و در چوبی اضافه کن").get(
        "final_prompt", ""
    )
    assert "Apply the changes to the window system" not in final, (
        "a preserved element must not be targeted for alteration\nfinal: %r"
        % final
    )
    assert "include wood doors" in final, final


def test_preserved_element_keeps_its_preservation_sentence():
    final = _final_prompt("پنجره‌ها را حفظ کن و در چوبی اضافه کن").get(
        "final_prompt", ""
    )
    assert "Preserve the current window locations" in final, final


def test_genuine_window_change_still_announces_the_window_scope():
    """The guard must not silence a scope the user really is changing."""
    from core.prompt_intelligence.persian_architectural_understanding import (
        understand,
    )
    from core.prompt_intelligence.architectural_prompt_compiler_v1 import (
        compile_prompt,
    )

    prompt = compile_prompt(
        understand("پنجره‌ها را تغییر بده"), mode="IMAGE_EDIT"
    )["positive_prompt"]
    assert "Apply the changes to the window system" in prompt, prompt


@pytest.mark.parametrize("text,expected", [
    ("پنجره و در و نرده اضافه کن", ["windows", "doors", "railing"]),
])
def test_three_element_chain_keeps_every_element(text, expected):
    final = _final_prompt(text).get("final_prompt", "")
    for noun in expected:
        assert "include %s" % noun in final, (
            "%r missing from final_prompt for %r\nfinal: %r"
            % (noun, text, final)
        )
