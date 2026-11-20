"""T2I_MODE_PROPAGATION_V1 — the compiler must describe the RIGHT task.

Guards the defect measured in ARCHITECTOS_LIVE_PRODUCT_SMOKE_ACCEPTANCE_V2 §3:

  A fresh text-to-image request was compiled as FACADE_REFINEMENT, so the
  positive prompt opened "Refine the existing facade. Apply the changes to the
  facade expression only." - instructions to preserve a source facade that does
  not exist in a generation. The material section also emitted
  "Use light light travertine stone." because the tone was baked into the
  material word and prepended again.

Run:
  ./.venv/Scripts/python.exe -m pytest tests/test_t2i_mode_propagation_v1.py -q \
      --basetemp=runs/_pytest_tmp_t2i
"""

import pytest

from core.prompt_intelligence.persian_architectural_understanding import understand
from core.prompt_intelligence.architectural_prompt_compiler_v1 import (
    MODES,
    PRODUCT_MODE_ALIASES,
    architectural_prompt_compiler,
    compile_prompt,
)


PERSIAN_T2I = "یک ویلای نئوکلاسیک با نمای تراورتن روشن رندر کن."


# ----------------------------------------------------------
# 1. MODE RESOLUTION
# ----------------------------------------------------------

def test_product_mode_vocabulary_resolves_to_compiler_modes():
    assert architectural_prompt_compiler._normalize_mode("text_to_image") == "TEXT_TO_IMAGE"
    assert architectural_prompt_compiler._normalize_mode("image_to_image") == "IMAGE_EDIT"
    assert architectural_prompt_compiler._normalize_mode("chat") == "ARCHITECTURAL_GENERAL"
    assert architectural_prompt_compiler._normalize_mode("analyze_image") == "ARCHITECTURAL_GENERAL"


def test_compiler_own_vocabulary_still_works():
    for mode in MODES:
        assert architectural_prompt_compiler._normalize_mode(mode) == mode


def test_auto_and_unknown_modes_keep_inference():
    """`auto` is not authoritative - it must not force a mode."""
    assert architectural_prompt_compiler._normalize_mode("auto") is None
    assert architectural_prompt_compiler._normalize_mode(None) is None
    assert architectural_prompt_compiler._normalize_mode("") is None
    assert architectural_prompt_compiler._normalize_mode(42) is None


def test_every_alias_target_is_a_real_mode():
    for product, compiler_mode in PRODUCT_MODE_ALIASES.items():
        assert compiler_mode in MODES, product


# ----------------------------------------------------------
# 2. T2I MUST NOT PRESERVE A NON-EXISTENT FACADE
# ----------------------------------------------------------

def test_text_to_image_is_not_compiled_as_facade_refinement():
    """The measured regression: no mode => FACADE_REFINEMENT."""
    understanding = understand(PERSIAN_T2I)

    inferred = compile_prompt(understanding)
    assert inferred["mode"] == "FACADE_REFINEMENT"

    explicit = compile_prompt(understanding, mode="text_to_image")
    assert explicit["mode"] == "TEXT_TO_IMAGE"


def test_text_to_image_prompt_does_not_ask_to_refine_an_existing_facade():
    understanding = understand(PERSIAN_T2I)
    prompt = compile_prompt(understanding, mode="text_to_image")["positive_prompt"]

    assert prompt.startswith("Generate an architectural visualization.")
    assert "Refine the existing" not in prompt
    assert "Apply the changes to the facade expression only" not in prompt
    assert "existing" not in prompt.lower()


def test_mode_reaches_the_compiler_through_context_too():
    understanding = understand(PERSIAN_T2I)
    prompt = compile_prompt(
        understanding, context={"mode": "text_to_image"}
    )["positive_prompt"]

    assert prompt.startswith("Generate an architectural visualization.")


def test_image_edit_still_receives_preservation_policy():
    """The edit path must not lose its geometry policy when the mode is set."""
    understanding = understand(PERSIAN_T2I)
    prompt = compile_prompt(understanding, mode="image_to_image")["positive_prompt"]

    assert prompt.startswith("Refine the existing architectural image.")
    assert "authoritative geometry reference" in prompt
    assert "Do not relocate preserved windows or openings." in prompt


def test_resolved_mode_is_recorded_in_provenance():
    understanding = understand(PERSIAN_T2I)
    result = compile_prompt(understanding, mode="text_to_image")
    assert result["provenance"]["mode"] == "TEXT_TO_IMAGE"


# ----------------------------------------------------------
# 3. MATERIAL TONE MUST NOT REPEAT
# ----------------------------------------------------------

@pytest.mark.parametrize("primary,tone,expected", [
    # the measured live case: the tone is baked into the material word
    ("travertine", "light", "Use light travertine stone."),
    ("light_travertine_stone", "light", "Use light travertine stone."),
    ("dark_brick", "dark", "Use dark brick."),
    # a tone that genuinely qualifies the material must survive
    ("red_brick", "dark", "Use dark red brick."),
    ("travertine", None, "Use light travertine stone."),
])
def test_material_tone_is_never_duplicated(primary, tone, expected):
    lines = architectural_prompt_compiler._compile_materials(
        {"materials": {"primary": primary, "tone": tone}}
    )
    assert lines == [expected]


def test_material_ids_never_leak_underscores_into_the_prompt():
    lines = architectural_prompt_compiler._compile_materials(
        {"materials": {"primary": "warm_oak_cladding", "tone": None}}
    )
    assert "_" not in lines[0]


def test_comparative_tone_is_still_emitted():
    lines = architectural_prompt_compiler._compile_materials(
        {"materials": {"primary": "brick", "tone": "light", "tone_direction": "increase"}}
    )
    assert lines == ["Use a lighter brick tone."]
