"""V22_2P5D_MASK_CONDITIONING_V1 — CPU contract tests.

Covers the four changes authorised for `run_single_render.py` /
`engine/compositor.py`:

1. roof starter-rebar rods are inpainted out of `P_sky`;
2. `mask_S`'s top boundary is raised to `y = 64` across the right roof bay;
3. the ground artifact is folded into the editable render mask and its prompt
   is appended only when it actually added pixels;
4. MODE_3 switches the USO style LoRA off and drives the V22 night pre-pass /
   geometry lock.

CPU only. No ComfyUI call, no GPU, no model load.
"""

import json
import os
import pathlib
import sys
import types

import numpy as np
import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE_ROOT = REPO_ROOT / "ArchitectOS_2P5D_Repair_v21"

for _path in (str(PACKAGE_ROOT), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.append(_path)


from engine.compositor import (  # noqa: E402
    extend_mask_top_boundary_right_bay,
    include_ground_in_render_mask,
    inpaint_roof_rebar_spikes,
)

import run_single_render as runner  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

H, W = 200, 300
BUILDING_TOP = 40


def _scene():
    """Bright sky over a building that fills the frame, with rebar rods above
    the roof line — the real B01 geometry (building ~80 % of the frame)."""

    img = np.full((H, W, 3), 205, dtype=np.uint8)

    # building body
    img[BUILDING_TOP:, 40:260] = (120, 115, 110)

    sky = np.zeros((H, W), dtype=np.uint8)
    sky[:BUILDING_TOP, :] = 1
    sky[BUILDING_TOP:, :40] = 1
    sky[BUILDING_TOP:, 260:] = 1

    building = np.zeros((H, W), dtype=np.uint8)
    building[BUILDING_TOP:, 40:260] = 1

    # two thin vertical rods protruding above the roof
    for x in (100, 150):
        img[8:BUILDING_TOP, x:x + 3] = (25, 25, 25)

    # a WIDE parapet stub: 60 px of horizontal support, must survive
    img[28:BUILDING_TOP, 180:240] = (60, 60, 60)

    return img, sky, building


# ---------------------------------------------------------------------------
# (1) Roof rebar inpainting
# ---------------------------------------------------------------------------

def test_thin_vertical_rods_are_inpainted_out_of_the_sky():
    img, sky, building = _scene()

    cleaned, stats = inpaint_roof_rebar_spikes(img, sky, building)

    assert stats["contract"] == "RoofRebarInpaintV1"
    assert stats["inpainted"] is True
    assert stats["bar_components"] >= 2

    # the rods are gone: their pixels now match the surrounding sky
    for x in (100, 150):
        before = img[12:34, x + 1].mean()
        after = cleaned[12:34, x + 1].mean()
        assert before < 40
        assert after > 150, (x, before, after)


def test_wide_parapet_is_not_mistaken_for_rebar():
    img, sky, building = _scene()

    cleaned, _ = inpaint_roof_rebar_spikes(img, sky, building)

    # the 60 px wide stub keeps its value
    assert np.array_equal(cleaned[30:38, 190:230], img[30:38, 190:230])


def test_building_pixels_are_never_modified():
    img, sky, building = _scene()

    cleaned, _ = inpaint_roof_rebar_spikes(img, sky, building)

    assert np.array_equal(cleaned[building > 0], img[building > 0])


def test_clean_sky_is_a_no_op():
    img, sky, building = _scene()
    img[8:BUILDING_TOP, 100:103] = 205
    img[8:BUILDING_TOP, 150:153] = 205

    cleaned, stats = inpaint_roof_rebar_spikes(img, sky, building)

    assert stats["inpainted"] is False
    assert stats["reason"] in (
        "no_thin_dark_structure_in_sky",
        "no_thin_vertical_bars_found",
    )
    assert np.array_equal(cleaned, img)


def test_border_touching_structures_are_not_treated_as_rods():
    """A neighbour-building edge at the frame border is not a rebar rod."""

    img, sky, building = _scene()

    # a dark vertical band running off the left edge
    img[5:BUILDING_TOP, 0:4] = (30, 30, 30)

    cleaned, stats = inpaint_roof_rebar_spikes(img, sky, building)

    # whatever else was removed, the border band itself must survive
    assert np.array_equal(cleaned[5:BUILDING_TOP, 0:2], img[5:BUILDING_TOP, 0:2])


def test_empty_masks_are_a_no_op():
    img, _, _ = _scene()

    cleaned, stats = inpaint_roof_rebar_spikes(
        img, np.zeros((H, W), np.uint8), np.zeros((H, W), np.uint8)
    )

    assert stats["inpainted"] is False
    assert stats["reason"] == "empty_masks"
    assert np.array_equal(cleaned, img)


# ---------------------------------------------------------------------------
# (2) Right-bay parapet boundary extension
# ---------------------------------------------------------------------------

def test_right_bay_top_boundary_is_raised_to_y_64():
    mask = np.zeros((H, W), dtype=np.uint8)
    mask[64:, 40:150] = 1      # left bay already at 64
    mask[90:, 150:260] = 1     # right bay starts 26 px lower

    out, stats = extend_mask_top_boundary_right_bay(mask, y=64)

    assert stats["contract"] == "MaskTopBoundaryExtensionV1"
    assert stats["y"] == 64
    assert stats["pixels_added"] > 0
    assert stats["columns_extended"] > 0

    # the right bay is now continuous from y=64
    assert out[64:90, 200].all()
    assert out[64:90, 255].all()

    # the left bay is untouched (it was already at 64)
    assert np.array_equal(out[:, :150], mask[:, :150])


def test_no_pixels_are_added_outside_the_building_extent():
    mask = np.zeros((H, W), dtype=np.uint8)
    mask[90:, 40:260] = 1

    out, _ = extend_mask_top_boundary_right_bay(mask, y=64)

    assert out[:, :40].sum() == 0
    assert out[:, 260:].sum() == 0


def test_columns_far_below_y_are_skipped_not_bridged():
    mask = np.zeros((H, W), dtype=np.uint8)
    mask[64:, 40:200] = 1
    mask[190:, 200:260] = 1   # a recessed bay starting far below

    out, stats = extend_mask_top_boundary_right_bay(mask, y=64, max_extension_px=40)

    assert stats["columns_skipped_far"] > 0
    # nothing was drawn in the empty gap above the recessed bay
    assert out[64:190, 230].sum() == 0


def test_empty_mask_is_a_no_op():
    mask = np.zeros((H, W), dtype=np.uint8)

    out, stats = extend_mask_top_boundary_right_bay(mask, y=64)

    assert stats["pixels_added"] == 0
    assert out.sum() == 0


# ---------------------------------------------------------------------------
# (3) Ground inclusion
# ---------------------------------------------------------------------------

def test_ground_is_added_to_the_render_mask():
    mask = np.zeros((H, W), dtype=np.uint8)
    mask[100:180, 50:200] = 1

    ground = np.zeros((H, W), dtype=np.uint8)
    ground[180:, :] = 1

    out, stats = include_ground_in_render_mask(mask, ground)

    assert stats["included"] is True
    assert stats["added_pixels"] == int(ground[180:, :].size)
    assert out[180:, :].all()
    assert out[100:180, 50:200].all()

    # strictly binary — validate_real_distinct_input_artifacts() rejects
    # anything that is not {0, 255} after scaling by 255.
    assert set(np.unique(out).tolist()) == {0, 1}


def test_missing_ground_mask_leaves_the_render_mask_unchanged():
    mask = np.zeros((H, W), dtype=np.uint8)
    mask[100:180, 50:200] = 1

    out, stats = include_ground_in_render_mask(mask, None)

    assert stats["included"] is False
    assert stats["reason"] == "no_ground_mask"
    assert np.array_equal(out, mask)


def test_ground_mask_shape_mismatch_is_refused():
    mask = np.zeros((H, W), dtype=np.uint8)
    ground = np.zeros((H // 2, W), dtype=np.uint8)

    with pytest.raises(ValueError):
        include_ground_in_render_mask(mask, ground)


# ---------------------------------------------------------------------------
# (4) Stage-2 graph conditioning
# ---------------------------------------------------------------------------

def _stage2_graph():
    path = PACKAGE_ROOT / "workflows" / "stage2_flux_2p5d_render.json"

    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def test_mode_constants_match_the_router():
    from core.render import unified_4mode_router_v21 as router

    assert (
        runner.MODE_3_DAY_TO_NIGHT_RELIGHT
        == router.MODE_3_DAY_TO_NIGHT_RELIGHT
    )
    assert (
        runner.MODE_2_IMG2IMG_MATERIAL_STYLE_TRANSFER
        == router.MODE_2_IMG2IMG_MATERIAL_STYLE_TRANSFER
    )


def test_mask_conditioning_is_scoped_to_mode_2_and_mode_3():
    assert runner.mask_conditioning_active(
        runner.MODE_2_IMG2IMG_MATERIAL_STYLE_TRANSFER
    ) is True
    assert runner.mask_conditioning_active(
        runner.MODE_3_DAY_TO_NIGHT_RELIGHT
    ) is True

    # every other route keeps its previous masks and pixels exactly
    assert runner.mask_conditioning_active("MODE_1_TXT2IMG") is False
    assert runner.mask_conditioning_active("MODE_4_PLAN_TO_3D_RENDER") is False
    assert runner.mask_conditioning_active(None) is False


def test_mode_3_switches_the_uso_lora_off():
    graph = _stage2_graph()
    args = types.SimpleNamespace(uso_lora=0.25)

    trace = runner.apply_stage2_conditioning(
        graph,
        mode=runner.MODE_3_DAY_TO_NIGHT_RELIGHT,
        args=args,
        ground_pixels_added=0,
    )

    assert graph["320"]["inputs"]["strength_model"] == 0.0
    assert trace["uso_lora_strength_model"] == 0.0


def test_mode_2_keeps_the_router_lora_value():
    graph = _stage2_graph()
    args = types.SimpleNamespace(uso_lora=0.92)

    trace = runner.apply_stage2_conditioning(
        graph,
        mode=runner.MODE_2_IMG2IMG_MATERIAL_STYLE_TRANSFER,
        args=args,
        ground_pixels_added=0,
    )

    assert graph["320"]["inputs"]["strength_model"] == 0.92
    assert trace["uso_lora_strength_model"] == 0.92


def test_legacy_path_leaves_the_lora_at_the_graph_value():
    graph = _stage2_graph()
    original = graph["320"]["inputs"]["strength_model"]
    args = types.SimpleNamespace()  # no uso_lora at all

    runner.apply_stage2_conditioning(
        graph, mode=None, args=args, ground_pixels_added=0
    )

    assert graph["320"]["inputs"]["strength_model"] == original


def test_ground_prompt_is_appended_only_when_pixels_were_added():
    graph = _stage2_graph()
    base = graph["206"]["inputs"]["text"]
    args = types.SimpleNamespace(uso_lora=None)

    trace = runner.apply_stage2_conditioning(
        graph, mode=None, args=args, ground_pixels_added=1234
    )

    assert trace["ground_prompt_applied"] is True
    assert graph["206"]["inputs"]["text"] == (
        base.rstrip(" ,") + ", " + runner.GROUND_PAVING_PROMPT
    )
    assert graph["206"]["inputs"]["text"].count(runner.GROUND_PAVING_PROMPT) == 1


def test_no_ground_pixels_leaves_the_prompt_untouched():
    graph = _stage2_graph()
    base = graph["206"]["inputs"]["text"]
    args = types.SimpleNamespace(uso_lora=None)

    trace = runner.apply_stage2_conditioning(
        graph, mode=None, args=args, ground_pixels_added=0
    )

    assert trace["ground_prompt_applied"] is False
    assert graph["206"]["inputs"]["text"] == base


def test_ground_prompt_text_is_the_authorised_instruction():
    assert runner.GROUND_PAVING_PROMPT == (
        "honed cream travertine stone courtyard paving and "
        "manicured green border shrubs"
    )
    assert runner.NIGHT_DETAIL_PRESERVATION_WEIGHT == 0.75
    assert runner.DEFAULT_MASK_S_TOP_Y == 64


# ---------------------------------------------------------------------------
# End-to-end mask composition (no I/O, no ComfyUI)
# ---------------------------------------------------------------------------

def test_full_mask_pipeline_is_binary_and_ordered():
    """rebar -> parapet -> ground, exactly as run_single_render applies them."""

    img, sky, building = _scene()

    cleaned, rebar_stats = inpaint_roof_rebar_spikes(img, sky, building)

    # a mask whose right bay still starts below y=64 — the case the extension
    # exists for
    render_mask = np.zeros((H, W), dtype=np.uint8)
    render_mask[64:, 40:150] = 1
    render_mask[90:, 150:260] = 1

    render_mask, ext_stats = extend_mask_top_boundary_right_bay(render_mask, y=64)

    ground = np.zeros((H, W), dtype=np.uint8)
    ground[180:, :] = 1
    render_mask, ground_stats = include_ground_in_render_mask(render_mask, ground)

    assert rebar_stats["inpainted"] is True
    assert ext_stats["pixels_added"] > 0
    assert ground_stats["added_pixels"] > 0

    assert set(np.unique(render_mask * 255).tolist()) == {0, 255}
    assert cleaned.shape == img.shape == (H, W, 3)
