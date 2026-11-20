# ==========================================================
# ArchitectOS — V4.3D PROMPT INTEGRITY REGRESSION TESTS
#
# A lighting-only edit must not carry facade-restyle instructions, and must
# not lose the geometry contract while they are removed.
#
# NO GPU. NO COMFYUI. Pure prompt composition.
# ==========================================================

import pytest

from core.prompt_intelligence.image_edit_delta_v1 import (
    compile_edit_delta,
    conflict_terms,
    delta_prompt,
)
from core.prompt_intelligence.image_edit_prompt_builder import (
    ImageEditPromptBuilder,
)
from core.prompt_intelligence.prompt_router import PromptRouter
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)

FACADE_SECTION = "facade transformation"
QUALITY_LINE = "strongly express the requested architectural style"
NATURAL_LIGHT = "natural lighting"
FACADE_KNOWLEDGE = "apply the resolved architectos facade knowledge"
GEOMETRY = "geometry preservation"
FLOOR_CLAIM = "single floor building"

FACADE_INTENT = {
    "building_type": "tower",
    "style": "modern",
    "materials": [],
    "resolved_facade_knowledge": {
        "contract": "ResolvedFacadeKnowledgeV1",
        "version": "1.0",
        "canonical_style": "modern",
        "composition": ["simple geometry", "clean lines", "horizontal composition"],
        "architectural_elements": ["large openings", "glass surfaces"],
        "materials": ["glass", "stone"],
    },
}


def _builder_output(edit_class):
    intent = dict(FACADE_INTENT)
    if edit_class:
        intent["edit_delta"] = {"edit_class": edit_class}
    return ImageEditPromptBuilder().build(intent)


def _compose(text):
    """Compose exactly as the live path does: the compiled delta classifies the
    edit AND is handed to the builder."""

    delta = compile_edit_delta(text)

    builder_intent = dict(FACADE_INTENT)
    builder_intent["edit_delta"] = delta

    builder_prompt = ImageEditPromptBuilder().build(builder_intent)

    return resolve_render_prompt(
        compiled_prompt=delta_prompt(delta),
        builder_prompt=builder_prompt,
        preset_tail="",
        conflict_terms=tuple(conflict_terms(delta)),
    )


# ==========================================================
# BUILDER-LEVEL: WHICH SECTIONS SURVIVE WHICH EDIT CLASS
# ==========================================================

@pytest.mark.parametrize("edit_class", ["time_of_day_change", "lighting_change"])
def test_lighting_edit_has_no_facade_or_quality_section(edit_class):
    out = _builder_output(edit_class).lower()

    assert FACADE_SECTION not in out
    assert QUALITY_LINE not in out
    assert NATURAL_LIGHT not in out
    assert FACADE_KNOWLEDGE not in out


@pytest.mark.parametrize("edit_class", ["time_of_day_change", "lighting_change"])
def test_lighting_edit_keeps_the_geometry_contract(edit_class):
    out = _builder_output(edit_class).lower()

    assert GEOMETRY in out
    assert "preserve exactly" in out
    assert "camera angle" in out
    assert "floor count" in out


@pytest.mark.parametrize("edit_class", ["material_change", "color_change", None])
def test_material_and_colour_edits_keep_facade_knowledge(edit_class):
    out = _builder_output(edit_class).lower()

    assert FACADE_SECTION in out
    assert FACADE_KNOWLEDGE in out


def test_unknown_class_preserves_previous_behaviour():
    """No classification -> the builder must behave exactly as before."""

    out = _builder_output(None)

    assert len(out) > 1200
    assert FACADE_SECTION in out.lower()


# ==========================================================
# FORWARDING: edit_delta MUST SURVIVE PromptRouter
# ==========================================================

def test_prompt_router_forwards_edit_delta_from_architectural_intent():
    """`PromptRouter.build()` rebuilds its dict from `architectural_intent`
    only, so the handler must place the classification inside it."""

    router = PromptRouter()

    out = router.build(
        {
            "prompt": "same tower, night",
            "architectural_intent": dict(
                FACADE_INTENT,
                edit_delta={"edit_class": "time_of_day_change"},
            ),
        },
        mode="img2img",
    )

    low = str(out).lower()

    assert FACADE_SECTION not in low
    assert QUALITY_LINE not in low
    assert GEOMETRY in low


def test_prompt_router_without_edit_delta_is_unchanged():
    router = PromptRouter()

    out = router.build(
        {"prompt": "same tower", "architectural_intent": dict(FACADE_INTENT)},
        mode="img2img",
    )

    assert FACADE_SECTION in str(out).lower()


# ==========================================================
# COMPOSED PROMPT: THE ACTUAL SAMPLER TEXT
# ==========================================================

@pytest.mark.parametrize("text,marker", [
    ("same tower, morning", "crisp morning"),
    ("same tower, noon", "high-noon"),
    ("same tower, sunset", "golden-hour"),
    ("same tower, dusk", "blue-hour"),
    ("same tower, night", "night photography"),
])
def test_composed_lighting_prompt_is_clean(text, marker):
    resolution = _compose(text)
    final = resolution["final_prompt"]
    low = final.lower()

    # Contract intact.
    for clause in ("REFERENCE:", "DELTA:", "PRESERVE:", "QUALITY:"):
        assert clause in final

    # Intended lighting present.
    assert marker in low

    # No contamination.
    assert FACADE_SECTION not in low
    assert QUALITY_LINE not in low
    assert FACADE_KNOWLEDGE not in low
    assert NATURAL_LIGHT not in low
    assert FLOOR_CLAIM not in low

    # Geometry contract preserved.
    assert GEOMETRY in low


def test_sunset_keeps_golden_hour():
    resolution = _compose("same tower, sunset")

    assert "golden-hour" in resolution["final_prompt"].lower()
    assert "golden hour" not in resolution["removed_conflicting_tail_terms"]


def test_material_edit_still_carries_facade_knowledge():
    resolution = _compose("same tower, make the facade stone")

    assert FACADE_KNOWLEDGE in resolution["final_prompt"].lower()
    assert GEOMETRY in resolution["final_prompt"].lower()


def test_lighting_edit_does_not_remove_user_floor_constraint():
    """A genuine "30 story building" constraint must survive a night edit."""

    delta = compile_edit_delta("same tower, night")
    builder = ImageEditPromptBuilder().build(
        dict(FACADE_INTENT, edit_delta={"edit_class": "time_of_day_change"})
    ).replace(
        "PRESERVE EXACTLY:", "30 story building. PRESERVE EXACTLY:"
    )

    resolution = resolve_render_prompt(
        compiled_prompt=delta_prompt(delta),
        builder_prompt=builder,
        preset_tail="",
        conflict_terms=tuple(conflict_terms(delta)),
    )

    assert "30 story building" in resolution["final_prompt"]
