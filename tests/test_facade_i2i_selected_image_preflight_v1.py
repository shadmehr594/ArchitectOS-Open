"""FACADE_I2I_SELECTED_IMAGE_PREFLIGHT_V1 — the selected test request must
compile to a non-contradictory instruction.

The user approved one facade image and one exact redesign request:

    tests/manual_facade_i2i_v1/ArchitectOS_Facade_I2I_Test_Pack_V1/
        I2I_TEST_REQUEST_EN.txt

Before that request may be submitted to a real GPU job, the compiled canonical
delta must agree with it. Two compiler defects were measured on the real text:

D1. The component is named BEFORE the material:
        "Change only the window-frame finish to dark charcoal metal."
    `" to "` is a replacement-target marker, so the resolution window becomes
    "dark charcoal metal" and the WINDOW-FRAME metal is compiled as the facade
    cladding — the same contradiction the previous milestone fixed for the
    "material + component" order, in the opposite order.

D2. "daylight" is read as a light-tone request because tone matching is a plain
    substring test, so "Keep the original daylight composition" makes the new
    material "light" even when the user asked for "deep warm terracotta".

Both are the same class of defect: the compiler invents a material or tone claim
the user did not make. Both live in
`core/prompt_intelligence/image_edit_delta_v1.py`.
"""

import os

import pytest

from core.prompt_intelligence.image_edit_delta_v1 import (
    compile_edit_delta,
)


PACK = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "manual_facade_i2i_v1", "ArchitectOS_Facade_I2I_Test_Pack_V1",
)

REQUEST_PATH = os.path.join(PACK, "I2I_TEST_REQUEST_EN.txt")


def _request():
    if not os.path.isfile(REQUEST_PATH):
        pytest.skip("approved test request is not present")
    with open(REQUEST_PATH, encoding="utf-8") as handle:
        return handle.read().strip()


def _delta(text):
    return compile_edit_delta(text, image_edit=True)


def _prompt(delta):
    return str(delta.get("prompt") or "").lower()


# ==========================================================
# D1 — a component named BEFORE the material
# ==========================================================


def test_D1_the_approved_request_compiles_to_brick_not_metal():
    delta = _delta(_request())

    assert delta["material"] == "brick", delta["material"]
    assert "metal panel cladding" not in _prompt(delta)


def test_D1b_the_delta_never_claims_metal_cladding_for_this_request():
    prompt = _prompt(_delta(_request()))

    for banned in (
        "metal panel cladding",
        "architectural metal cladding",
        "controlled metallic reflection",
        "metal cladding",
    ):
        assert banned not in prompt, banned


def test_D1c_component_named_before_material_is_component_bound():
    """The general form, independent of the approved request."""

    assert _delta("Change only the window-frame finish to dark charcoal metal.")[
        "material"
    ] != "metal"

    assert _delta("Change the railings to black metal.")["material"] != "metal"

    assert _delta("Paint the entrance door dark metal.")["material"] != "metal"


def test_D1d_a_facade_cladding_request_still_compiles_to_metal():
    delta = _delta("Clad the facade in metal panels.")

    assert delta["material"] == "metal"
    assert "metal" in _prompt(delta)


def test_D1e_the_brick_facade_survives_as_the_material():
    delta = _delta(_request())

    assert delta["edit_class"] == "material_change"
    assert "brick" in _prompt(delta)


# ==========================================================
# D2 — "daylight" is not a light-tone request
# ==========================================================


def test_D2_daylight_does_not_set_the_light_tone():
    delta = _delta(_request())

    assert delta["material_tone"] != "light"


def test_D2b_daylight_alone_sets_no_tone():
    delta = _delta(
        "Replace the facade finish with terracotta brick. "
        "Keep the original daylight composition."
    )

    assert delta["material_tone"] is None


def test_D2c_an_explicit_light_request_still_sets_the_light_tone():
    assert _delta("Use a lighter stone on the facade.")["material_tone"] == "light"
    assert _delta("Make the brick light.")["material_tone"] == "light"


def test_D2d_an_explicit_dark_request_still_sets_the_dark_tone():
    assert _delta("Use dark brick on the facade.")["material_tone"] == "dark"


# ==========================================================
# Regression — the previous milestone's cases must still hold
# ==========================================================


@pytest.mark.parametrize(
    "text,expected",
    [
        (
            "Redesign this building in modern Iranian brick architecture "
            "with dark metal window frames.",
            "brick",
        ),
        ("Use brick on the facade with metal railings.", "brick"),
        ("Replace the brick facade with travertine.", "travertine"),
        ("Use wood instead of stone on the facade.", "wood"),
        ("Clad the facade in metal panels.", "metal"),
    ],
)
def test_R_previous_component_cases_unchanged(text, expected):
    assert _delta(text)["material"] == expected


def test_R2_geometry_authority_still_withholds_a_conflicting_edit():
    from core.prompt_intelligence.prompt_router import PromptRouter

    resolved = {
        "contract": "ResolvedFacadeKnowledgeV1",
        "version": "1.0",
        "canonical_style": "neoclassical",
        "facade_language": {"composition": ["classical order"]},
        "composition": ["classical grid"],
        "symmetry": [],
        "vertical_horizontal_emphasis": [],
        "solid_void_strategy": [],
        "entrance_hierarchy": [],
        "opening_treatment": [],
        "balcony_treatment": [],
        "parapet_treatment": [],
        "architectural_elements": {},
        "materials": {},
        "surface_strategy": {},
        "user_facade_details": [],
        "unresolved": [],
    }

    built = PromptRouter().build(
        {
            "prompt": "Add a triangular pediment; the roofline must stay unchanged",
            "architectural_intent": {
                "building_type": "villa",
                "normalized_prompt": (
                    "Add a triangular pediment; the roofline must stay unchanged"
                ),
                "preserve_geometry": True,
                "preserve_constraints": ["roofline", "overall_massing"],
                "resolved_facade_knowledge": resolved,
            },
        },
        mode="img2img",
    )["description"].lower()

    assert "triangular pediment" not in built
    assert "needs clarification" in built
