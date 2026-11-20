# ==========================================================
# ArchitectOS — V4.3A RENDER CONTROL WIRING
#
# Regression tests for the five narrow infrastructure corrections accepted
# from the V4.3 audit:
#
#   M1 — floor-count parsing (hyphen / storey spellings, Persian digits)
#   M2 — floor-count propagation into the existing PromptBuilder
#   M4 — time-of-day vocabulary for the I2I edit delta
#   M6 — Persian time-of-day terminology
#   M7 — same-building continuation routing
#
# NO GPU. NO COMFYUI. NO RENDER. Everything here is deterministic text
# transformation and routing.
#
# M3 (constraint-block floor sentence), M5 (render preset inference) and
# M8 (architectural_instruction through handle_image_edit) are OUT OF SCOPE
# for this phase; the tests that touch those areas assert that the accepted
# V4.2 behaviour is unchanged.
# ==========================================================

import pytest

from core.cognition.architectural_render_instruction_v1 import (
    _floor_count,
    build_constraint_block,
    build_render_instruction,
)
from core.cognition.architectural_terminology_v1 import (
    normalize_architectural_terms,
)
from core.chat.handlers.image_handler import ImageHandler
from core.intent_router import IntentRouter
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.prompt_intelligence.image_edit_delta_v1 import (
    compile_edit_delta,
    conflict_terms,
    delta_prompt,
    denoise_override,
    is_classified,
    is_same_subject_appearance_request,
)
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)
from core.render.prompt_builder import PromptBuilder
from core.vision.image_intent_v1 import classify_image_intent


# The generic img2img builder tail the audit measured. It is the text that
# used to contradict every time-of-day request.
GENERIC_BUILDER_TAIL = (
    "modern tower architectural visualization, single floor building, "
    "minimal modern architecture, architectural photography, 35mm lens, "
    "golden hour natural lighting, cinematic realistic render, "
    "physically accurate materials, 8k ultra realistic"
)


@pytest.fixture(scope="module")
def intent_engine():
    return ArchitecturalIntent()


@pytest.fixture(scope="module")
def prompt_builder():
    return PromptBuilder()


@pytest.fixture(scope="module")
def router():
    return IntentRouter()


def _prompt_text(intent, builder):
    built = builder.build({"architectural_intent": intent})
    return built.get("description", "") if isinstance(built, dict) else str(built)


def _compose(delta):
    """The exact I2I prompt the render path would send for this delta."""

    return resolve_render_prompt(
        compiled_prompt=delta_prompt(delta),
        builder_prompt=GENERIC_BUILDER_TAIL,
        preset_tail="",  # suppressed for img2img
        conflict_terms=tuple(conflict_terms(delta)),
    )


# ==========================================================
# 1 — FLOOR-COUNT SPELLING VARIANTS AND PERSIAN DIGITS
# ==========================================================

@pytest.mark.parametrize("text", [
    "Render a 30-floor tower",
    "Render a 30-storey tower",
    "Render a 30 story tower",
    "Render a 30 floors tower",
    "Render a tower with 30 floors",
    "برج ۳۰ طبقه",
    "برج ۳۰-طبقه",
])
def test_m1_floor_count_spellings_parse_to_thirty(intent_engine, text):
    intent = intent_engine.extract({"prompt": text})

    assert intent["levels"]["above_ground"] == 30
    assert intent["floor_count"]["source"] == "user_explicit"
    assert intent["floor_count"]["value"] == 30


def test_m1_render_instruction_floor_count_separator():
    """The V4.2 instruction parser now binds hyphenated forms.

    Only the separator behaviour changed; the sentence-filtering contract is
    asserted separately in test group 12.
    """

    assert _floor_count("Render a 30-floor tower")["value"] == 30
    assert _floor_count("Render a 30-storey tower")["value"] == 30
    assert _floor_count("برج ۳۰-طبقه")["value"] == 30

    # A dimension is still a dimension, never a floor count.
    assert _floor_count("a 30-metre facade") is None


# ==========================================================
# 2 — EXPLICIT VERSUS UNSPECIFIED FLOOR COUNTS
# ==========================================================

def test_m2_unspecified_floor_count_is_not_an_explicit_one(intent_engine):
    intent = intent_engine.extract({"prompt": "Render a tower"})

    # The schema default stays 1 ...
    assert intent["levels"]["above_ground"] == 1

    # ... but it is NOT promoted into a requested count.
    assert "floors" not in intent
    assert intent["floor_count"]["value"] is None
    assert intent["floor_count"]["source"] == "unspecified"


def test_m2_explicit_one_floor_is_distinguishable(intent_engine):
    intent = intent_engine.extract({"prompt": "Render a 1 floor pavilion"})

    assert intent["floor_count"]["source"] == "user_explicit"
    assert intent["floor_count"]["value"] == 1
    assert intent["floors"] == 1


def test_m2_basement_count_is_not_an_above_ground_count(intent_engine):
    """"دو طبقه زیرزمین" is a basement, not a two-storey building."""

    intent = intent_engine.extract({"prompt": "دو طبقه زیرزمین"})

    assert intent["levels"]["above_ground"] == 1
    assert intent["floor_count"]["source"] == "unspecified"
    assert "floors" not in intent


# ==========================================================
# 3 — FLOOR-COUNT PROPAGATION INTO THE PROMPT
# ==========================================================

def test_m2_floor_count_reaches_prompt_builder(intent_engine, prompt_builder):
    intent = intent_engine.extract({"prompt": "Render a 30-floor tower"})
    text = _prompt_text(intent, prompt_builder)

    assert "30 story building" in text


def test_m2_prompt_builder_does_not_invent_a_default_floor_count(
    intent_engine, prompt_builder
):
    """No explicit count -> no hard floor-count claim is emitted."""

    intent = intent_engine.extract({"prompt": "Render a tower"})
    text = _prompt_text(intent, prompt_builder)

    assert intent["floor_count"]["value"] is None
    assert intent["floor_count"]["source"] == "unspecified"
    assert "single floor building" not in text
    assert " story building" not in text


# ==========================================================
# 4 — NO CONTRADICTORY SINGLE-FLOOR STATEMENT
# ==========================================================

def test_m2_explicit_thirty_floor_has_no_single_floor_contradiction(
    intent_engine, prompt_builder
):
    for text in (
        "Render a 30-floor tower",
        "Render a 30-storey tower",
        "برج ۳۰ طبقه",
    ):
        intent = intent_engine.extract({"prompt": text})
        prompt = _prompt_text(intent, prompt_builder)

        assert "single floor building" not in prompt
        assert "30 story building" in prompt


# ==========================================================
# 5 — TIME-OF-DAY VOCABULARY
# ==========================================================

@pytest.mark.parametrize("text,expected", [
    ("same tower, morning", "morning"),
    ("same tower, sunrise", "sunrise"),
    ("same tower, noon", "noon"),
    ("same tower, sunset", "sunset"),
    ("same tower, golden hour", "sunset"),
    ("same tower, dusk", "dusk"),
    ("same tower, night", "night"),
])
def test_m4_time_of_day_vocabulary(text, expected):
    delta = compile_edit_delta(text)

    assert is_classified(delta)
    assert delta["edit_class"] == "time_of_day_change"
    assert delta["time_of_day"] == expected
    assert denoise_override(delta) == 0.30


def test_m4_morning_is_not_golden_hour():
    delta = compile_edit_delta("same tower, morning")
    prompt = delta_prompt(delta).lower()

    assert "morning" in prompt
    assert "golden-hour" not in prompt
    assert "golden hour" not in prompt


def test_m4_noon_is_not_sunrise():
    delta = compile_edit_delta("same tower, noon")
    prompt = delta_prompt(delta).lower()

    assert "noon" in prompt
    assert "dawn" not in prompt
    assert "sunrise" not in prompt


# ==========================================================
# 6 — ENGLISH AND PERSIAN TIME-OF-DAY REQUESTS
# ==========================================================

@pytest.mark.parametrize("text,expected", [
    ("همین برج را صبح کن", "morning"),
    ("همین برج را ظهر کن", "noon"),
    ("همین برج را هنگام غروب رندر کن", "sunset"),
    ("همین برج را در گرگ‌ومیش رندر کن", "dusk"),
    ("همین برج را شب کن", "night"),
    ("همین برج را شب رندر کن", "night"),
])
def test_m4_persian_time_of_day(text, expected):
    delta = compile_edit_delta(text)

    assert is_classified(delta)
    assert delta["time_of_day"] == expected


def test_m6_persian_night_reaches_the_preset_layer():
    """`شب رندر کن` produced no canonical term before M6, so the frozen preset
    layer fell back to the daylight default."""

    terminology = normalize_architectural_terms("همین برج را شب رندر کن")

    assert "night lighting" in terminology["canonical_terms"]


@pytest.mark.parametrize("text,canonical", [
    ("in the morning", "morning lighting"),
    ("at noon", "noon lighting"),
    ("dusk", "dusk lighting"),
    ("نور صبح", "morning lighting"),
    ("نور ظهر", "noon lighting"),
    ("گرگ‌ومیش", "dusk lighting"),
])
def test_m6_new_time_of_day_terminology(text, canonical):
    terminology = normalize_architectural_terms(text)

    assert canonical in terminology["canonical_terms"]


def test_m6_greetings_are_not_new_time_of_day_signals():
    """M6 must not turn a greeting into a time-of-day signal.

    `صبح بخیر` is deliberately excluded from the strict list: the PRE-EXISTING
    "day render" entry already matches a bare `صبح`, so it was an
    architectural signal before V4.3A and this phase does not change that
    (documented as a known limitation in the V4.3A report).
    """

    for text in ("good morning", "good afternoon", "ظهر بخیر"):
        terminology = normalize_architectural_terms(text)

        assert terminology["canonical_terms"] == []
        assert terminology["has_architectural_signal"] is False

    # The pre-existing mapping is unchanged, and it never becomes an edit.
    assert normalize_architectural_terms("صبح بخیر")["canonical_terms"] == ["day render"]
    assert is_classified(compile_edit_delta("صبح بخیر")) is False


# ==========================================================
# 7 — CORRECT I2I DELTA AND PRESERVATION INSTRUCTIONS
# ==========================================================

@pytest.mark.parametrize("text", [
    "same tower, morning",
    "same tower, noon",
    "same tower, sunset",
    "same tower, dusk",
    "same tower, night",
])
def test_m4_delta_keeps_reference_and_preserve(text):
    delta = compile_edit_delta(text)
    prompt = delta_prompt(delta)

    assert prompt.startswith("REFERENCE:")
    assert "DELTA:" in prompt
    assert "PRESERVE:" in prompt

    # The preservation clause must name the immutable quantities.
    for token in ("massing", "camera angle", "floor count", "openings"):
        assert token in prompt


@pytest.mark.parametrize("text,forbidden", [
    ("same tower, morning", "golden hour"),
    ("same tower, noon", "golden hour"),
    ("same tower, dusk", "golden hour"),
])
def test_m4_conflicting_generic_lighting_is_removed(text, forbidden):
    resolution = _compose(compile_edit_delta(text))

    assert forbidden not in resolution["final_prompt"].lower()
    assert forbidden in resolution["removed_conflicting_tail_terms"]


def test_m4_sunset_keeps_hyphenated_golden_hour():
    """A sunset request must not lose `golden-hour` merely because the token
    carries a hyphen."""

    resolution = _compose(compile_edit_delta("same tower, sunset"))

    assert "golden-hour" in resolution["final_prompt"].lower()
    assert "golden hour" not in resolution["removed_conflicting_tail_terms"]


def test_m4_time_of_day_does_not_request_geometry_changes():
    for text in (
        "same tower, morning",
        "same tower, noon",
        "same tower, sunset",
        "same tower, dusk",
        "same tower, night",
    ):
        delta = compile_edit_delta(text)

        assert delta["edit_class"] == "time_of_day_change"
        assert delta.get("material") is None
        # A lighting edit must never be reported as a material edit.
        assert "replace only the facade" in conflict_terms(delta)


# ==========================================================
# 8 — ROUTING WHEN A SOURCE IMAGE EXISTS
# ==========================================================

SOURCE_STATE = {
    "last_render_asset": {"path": "base.png", "filename": "base.png"},
    "last_image_asset": {"path": "base.png", "filename": "base.png"},
    "last_route_intent": "image",
}


@pytest.mark.parametrize("text", [
    "same tower, morning",
    "same tower, sunset",
    "same tower, night",
    "Render the same tower at sunset",
    "همین برج را شب کن",
    "همان ساختمان را هنگام غروب رندر کن",
])
def test_m7_routes_to_image_edit(router, text):
    result = router.route(text, image=None, context={"conversation_state": SOURCE_STATE})

    assert result["intent"] == "image"
    assert result["mode"] == "edit"
    assert result["source"] == "same_subject_appearance_variation"


def test_m7_does_not_discard_the_source_for_a_render_verb(router):
    """`Render the same tower at sunset` used to reset `last_render_asset` and
    become a fresh text-to-image request."""

    result = router.route(
        "Render the same tower at sunset",
        image=None,
        context={"conversation_state": SOURCE_STATE},
    )

    assert result["mode"] != "generate"


def test_m7_vision_gate_treats_same_subject_as_edit(router):
    result = classify_image_intent("same tower, morning", router)

    assert result["intent"] == "edit"
    assert result["reason"] == "same_subject_appearance_variation"


def test_m7_predicate_requires_both_halves():
    assert is_same_subject_appearance_request("same tower, sunset") is True
    # Same subject, no appearance delta.
    assert is_same_subject_appearance_request("same tower") is False
    # Appearance delta, no same-subject reference.
    assert is_same_subject_appearance_request("make it sunset") is False


# ==========================================================
# 9 — SAFE ROUTING WHEN NO SOURCE IMAGE EXISTS
# ==========================================================

@pytest.mark.parametrize("text", [
    "same tower, morning",
    "Render the same tower at sunset",
    "همین برج را شب کن",
])
def test_m7_no_source_means_no_forced_edit(router, text):
    result = router.route(text, image=None, context={"conversation_state": {}})

    assert result["mode"] != "edit"


# ==========================================================
# 10 — GENERAL CONVERSATION MUST NOT BECOME IMAGE EDITING
# ==========================================================

@pytest.mark.parametrize("text", [
    "good morning",
    "hello, how are you",
    "is this the same building?",
    "write me a python function",
    "design a new building",
    "render a new tower at sunset",
])
def test_m7_general_conversation_is_not_an_edit(router, text):
    result = router.route(text, image=None, context={"conversation_state": SOURCE_STATE})

    assert result["mode"] != "edit"


def test_m7_greetings_are_not_classified_as_time_of_day_edits():
    for text in ("good morning", "good evening", "good afternoon"):
        assert is_classified(compile_edit_delta(text)) is False


# ==========================================================
# 11 — STABLE COMMON-BASE SELECTION ACROSS THREE VARIANTS
# ==========================================================

class _StubState:
    """Minimal ConversationState surface used by handle_image_edit."""

    def __init__(self, data):
        self._data = dict(data)

    def get(self, *args, **kwargs):
        if not args and not kwargs:
            return dict(self._data)
        return self._data.get(*args, **kwargs)

    def update(self, patch):
        self._data.update(patch)

    def add_message(self, *args, **kwargs):
        return None


class _CapturingBridge:
    """Captures the source path the handler selected, then stops."""

    def __init__(self):
        self.captured = None

    def process_upload(self, *args, **kwargs):
        self.captured = args[1] if len(args) > 1 else None
        raise RuntimeError("stop_after_capture")


def _select_source(state_data, image):
    bridge = _CapturingBridge()
    handler = ImageHandler(None, None, None, bridge, None, None, _StubState(state_data))
    handler.handle_image_edit(text="same tower, sunset", image=image)
    return bridge.captured


def test_m7_explicit_base_image_is_used_unchanged():
    """The EXISTING source-selection mechanism: an explicitly supplied image
    always wins over the last render."""

    state = {"last_image_asset": {"path": "variant_morning.png"}}

    assert _select_source(state, {"path": "base.png"}) == "base.png"


def test_m7_default_fallback_chains_the_previous_variant():
    """DOCUMENTED GAP (V4.3A §D).

    With no explicit source, the handler falls back to `last_image_asset`,
    which the previous variant's render overwrote. Three variants submitted
    this way would chain morning -> sunset -> night instead of sharing one
    frozen base. The invariant therefore requires an explicit base image per
    variant; no frozen-base selector exists yet.
    """

    state = {"last_image_asset": {"path": "variant_morning.png"}}

    assert _select_source(state, None) == "variant_morning.png"


def test_m7_three_variants_share_one_base_when_supplied_explicitly():
    """C1-C10 pre-condition: identical source for all three variants."""

    state = {"last_image_asset": {"path": "variant_morning.png"}}
    sources = []

    for variant in ("morning", "sunset", "night"):
        # The base is re-supplied each turn and is never the previous output.
        sources.append(_select_source(state, {"path": "base.png"}))
        state["last_image_asset"] = {"path": "variant_%s.png" % variant}

    assert sources == ["base.png", "base.png", "base.png"]


# ==========================================================
# 12 — NO REGRESSION IN THE ACCEPTED V4.2 INSTRUCTION HANDOFF
# ==========================================================

def test_v42_floor_sentence_is_still_outside_the_constraint_block():
    """M3 is explicitly deferred: the accepted V4.2 sentence-filtering
    contract must be unchanged, so the floor specification is still excluded
    from the block (only the conflict note is admitted)."""

    instruction = {
        "english_instruction": (
            "The building has exactly 30 floors. "
            "Note: the target building (IMAGE B) shows 8 visible floor "
            "level(s), which differs from the requested 30 floor(s); this "
            "conflict must be resolved before rendering."
        ),
        "hard_constraints": [],
    }

    block = build_constraint_block(instruction)

    assert "exactly 30 floors" not in block
    assert "Note: the target building" in block


def test_v42_shape_and_temporary_sentences_still_admitted():
    instruction = {
        "english_instruction": (
            "The target building has CURVED balcony fronts. "
            "Reported TEMPORARY construction objects are present."
        ),
        "hard_constraints": [
            "Temporary construction objects are never architectural features."
        ],
    }

    block = build_constraint_block(instruction)

    assert "CURVED" in block
    assert "never architectural features" in block
    assert "Reported TEMPORARY" in block


def test_v42_instruction_still_produces_the_floor_sentence():
    """M1 made the parser bind hyphenated spellings; the sentence itself is
    unchanged."""

    instruction = build_render_instruction("Render a 30-floor tower", mode="text_to_image")
    prose = instruction["english_instruction"]

    assert "The building has exactly 30 floors." in prose


def test_v42_resolver_still_places_the_block_between_content_and_tail():
    resolution = resolve_render_prompt(
        compiled_prompt="architectural render, tower",
        builder_prompt=GENERIC_BUILDER_TAIL,
        architectural_instruction={
            "constraint_block": "Keep the target building's massing unchanged.",
        },
    )

    final = resolution["final_prompt"]

    assert final.startswith("architectural render, tower.")
    assert final.index("Keep the target building") < final.index("35mm lens")
    assert resolution["instruction_applied"] is True
