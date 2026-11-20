"""FACADE_PROMPT_BUILDER_FINAL_CORRECTION_V3 — RED/GREEN.

Drives the REAL `ImageEditPromptBuilder.build()` — no LLM, no GPU, no ComfyUI.

The three remaining defects all live in `image_edit_prompt_builder.py`:
  A. a second block claims "verbatim user instruction, authoritative"
  B. a static sentence forbids the cornices/pilasters the user requested
  C. the target is described as a "villa" regardless of its real category
"""

import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PACK = os.path.join(
    ROOT, "tests", "manual_facade_i2i_v1", "ArchitectOS_Reference_Style_Test_V1"
)
REQUEST = os.path.join(PACK, "REFERENCE_STYLE_REQUEST_EN.txt")

# A compiler-style tag list: exactly what the failed GPU job placed under the
# "verbatim user instruction" label.
COMPILED_TAGS = (
    "neoclassical residential architectural visualization, , light ivory "
    "natural stone, cream travertine-like facade cladding, exterior "
    "architectural presentation, architectural photography, 35mm lens"
)


def _request():
    with open(REQUEST, encoding="utf-8") as fh:
        return fh.read().strip()


def _build(
    *,
    user_prompt=None,
    normalized_prompt=None,
    building_type="residential",
    materials=None,
):
    from core.prompt_intelligence.image_edit_prompt_builder import (
        ImageEditPromptBuilder,
    )

    request = _request()

    intent = {
        "_user_prompt": user_prompt if user_prompt is not None else request,
        "edit_delta": {"edit_class": "style_change"},
        "architectural_intent": {
            "request_type": "edit",
            "building_type": building_type,
            "style": "neoclassical",
            "materials": materials
            if materials is not None
            else [
                "light ivory natural stone",
                "cream travertine-like facade cladding",
            ],
            "preserve_geometry": True,
            "preserve_constraints": {"reference_geometry": True},
            "normalized_prompt": (
                normalized_prompt if normalized_prompt is not None else request
            ),
        },
    }

    built = ImageEditPromptBuilder().build(intent)

    if isinstance(built, dict):
        return built.get("prompt") or ""

    return built if isinstance(built, str) else ""


def _claims(text):
    return re.findall(r"\(verbatim[^)]*authoritative\)", text, re.I)


# ==========================================================
# A / B / C — authority and provenance
# ==========================================================


def test_A_the_builder_does_not_claim_verbatim_authority():
    """The authoritative block belongs to the preservation contract.

    The builder is a DERIVED channel: it must not mint a second verbatim claim.
    """

    text = _build()

    assert _claims(text) == [], (
        "the builder minted a verbatim-authority claim: " f"{_claims(text)}"
    )


def test_B_compiled_tags_are_never_labelled_verbatim():
    """The failed job put a tag list under the 'verbatim' label."""

    text = _build(user_prompt=COMPILED_TAGS)

    assert _claims(text) == []
    # and the tags must not be presented as the user's own words
    assert "verbatim" not in text.lower()


def test_B2_compiled_tags_are_labelled_as_derived():
    text = _build(user_prompt=COMPILED_TAGS)
    low = text.lower()

    assert "derived" in low or "compiled" in low, text[-400:]


def test_C_the_real_user_request_is_preserved():
    text = _build()
    request = _request()

    # a distinctive sentence from the user's own request must survive
    probe = "not a brick facade recolored beige"
    assert probe in text.lower()


# ==========================================================
# D / E / F / G — decorative vs structural
# ==========================================================


def test_D_applied_cornice_detailing_is_permitted():
    low = _build().lower()

    assert "do not add cornices" not in low, "cornices still forbidden"
    assert "cornice" in low


def test_E_shallow_pilaster_relief_is_permitted():
    low = _build().lower()

    assert "do not add cornices, pilasters" not in low
    assert "pilaster" in low


def test_F_structural_changes_remain_forbidden():
    low = _build().lower()

    for forbidden in ("structural columns", "load-bearing", "added building volume",
                      "new balcon", "floor count", "roofline"):
        assert forbidden in low, f"missing prohibition: {forbidden}"


def test_G_preservation_of_openings_and_roofline_is_intact():
    low = _build().lower()

    assert "opening" in low
    assert "preserve exactly" in low or "keep" in low


# ==========================================================
# H / I — building type
# ==========================================================


def test_H_an_apartment_is_not_described_as_a_villa():
    low = _build(building_type="residential").lower()

    assert "villa" not in low, "target described as a villa"


def test_H2_an_explicit_apartment_type_is_not_a_villa():
    low = _build(building_type="apartment").lower()

    assert "villa" not in low
    assert "apartment" in low


def test_I_a_grounded_villa_target_may_be_called_a_villa():
    low = _build(building_type="villa").lower()

    assert "villa" in low, "a genuinely grounded villa lost its type"


# ==========================================================
# J / K — material and roles
# ==========================================================


def test_J_material_is_cream_stone_not_brick():
    low = _build().lower()

    assert "travertine" in low
    assert "cream" in low or "ivory" in low
    # brick may only appear as a prohibition
    assert "brick cladding" not in low or "no red/orange brick" in low


def test_K_semantic_roles_are_unchanged():
    from core.cognition.architectural_render_instruction_v1 import (
        dual_image_role_block,
    )

    block = " ".join(dual_image_role_block())

    assert "TARGET_BUILDING" in block
    assert "STYLE_REFERENCE" in block
    assert "(IMAGE A)" not in block


# ==========================================================
# L — unrelated behaviour
# ==========================================================


def test_L_single_image_and_t2i_unchanged():
    from core.render.workflow_selector import WorkflowSelector

    selector = WorkflowSelector()

    assert selector.select({"engine": "flux"}) == "flux.json"
    assert selector.select({"engine": "flux", "mode": "edit"}) == "flux_img2img.json"
    assert (
        selector.select({"engine": "flux", "dual_image": True, "conditioned": True})
        == "flux_img2img_dual_conditioned.json"
    )


def test_L2_no_material_request_still_builds():
    text = _build(materials=[])

    assert isinstance(text, str)
    assert text.strip()
