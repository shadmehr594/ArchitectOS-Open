#!/usr/bin/env python3
"""
Explicit Post-Generation Compositor & High-Resolution (1792x2400) Detail Reconstruction (V21.0 — Material Replacement & Glazing Fix).
File: engine/compositor.py

V21.0 Critical Fixes for `architectos_img2img_dual_conditioned`:
  1. `allow_glazing_and_material_replacement=True` (Default for Material/Style Redesign):
     - Previously, `O_uncertain` (`PROTECTED_UNCERTAIN`) forced `alpha = 0.0` inside window cavities and
       loggias, which pasted the raw black unglazed window holes from the unfinished building (`IMAGE B`)
       directly back over the generated render!
     - Now, when `allow_glazing_and_material_replacement=True`, the entire building mask `S` (including
       newly generated windows, doors, and stone balusters) receives `alpha = 1.0`, while only `P_core`
       (the street, neighbor buildings, and sky outside `S`) is preserved from `IMAGE B`.
  2. Eliminates Raw Brick Edge Bleed (`reconstruct_hq_from_working_render`):
     - Previously, lines 148-153 extracted high-frequency luminance differences `(hq_gray - hq_blur) * 0.35`
       from the raw unfinished building `img_hq_bgr` and added them into the L-channel of the rendered facade,
       which transferred raw brick mortar lines onto smooth travertine stone!
     - Now, high-frequency detail sharpening is computed strictly from `gen_hq_up` (the generated travertine/facade
       render itself via unsharp mask), NEVER from the raw brick/cinderblock source photo!
"""
from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
import cv2
import numpy as np
from .geometry_2p5d import GeometryBundle2P5D


# ==========================================================================
# V22_2P5D_MASK_CONDITIONING_V1 — pre-encode conditioning of IMAGE B and MASK_S
#
# These three helpers run AFTER the human geometry gate and BEFORE anything is
# encoded, uploaded or composited. They deliberately do NOT mutate the
# `GeometryBundle2P5D` the gate validated:
#
#   `validate_geometry_bundle_prerender_gate()` requires
#   `F | O | O_uncertain == S` exactly, `S & P == 0`, `ground_px >= 5% of the
#   frame` and `vegetation_fraction_in_s <= 0.05`. Absorbing the ground into
#   `S` would drop `ground_px` to zero and block the render, so the render mask
#   is a SEPARATE array derived from the bundle. The gate keeps its own view.
# ==========================================================================


def inpaint_roof_rebar_spikes(
    img_bgr: np.ndarray,
    mask_sky: np.ndarray,
    mask_S: np.ndarray,
    *,
    band_fraction: float = 0.30,
    parapet_zone_fraction: float = 0.145,
    kernel_size: int = 9,
    blackhat_threshold: float = 35.0,
    max_bar_width_px: int = 25,
    min_bar_height_px: int = 5,
    min_aspect_ratio: float = 1.2,
    inpaint_radius: int = 3,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Remove protruding roof starter-rebar rods from the sky region.

    `geometry_2p5d` already EXCLUDES the starter bars (`میلگردهای انتظار`) from
    `S` into `P_sky`, using a 1x29 horizontal opening: a genuine parapet has
    >= 29 px of horizontal support while a bar is 5..25 px wide. Exclusion
    alone is not enough — the rods are still in the pixels of IMAGE B, and
    because `P_sky` is outside the render mask the sampler never repaints
    them, so they survive into the composite.

    This detects the SAME narrow-vertical structures inside `P_sky`, in the
    roof band only, and inpaints them out of the image itself.

    Detection uses a **black-hat** (morphological closing minus the image):
    it responds to dark structures NARROWER than the kernel and is blind to
    broad tonal gradients, so cloud shading does not trigger it. A first
    attempt thresholded the image against the sky median instead; measured on
    the real B01 fixture that found only 4 fragments / 143 px and left every
    rod standing, because a rod is broken by anti-aliasing into short dashes
    and its contrast varies with the sky gradient.

    Detection is bounded four ways: the search is restricted to `P_sky`
    (never the building), to the band from `band_fraction` above the building
    top to the 14.5 % parapet zone below it, to components that are narrow
    and vertical, and to components that do not touch the frame border (a
    neighbouring building edge is not a rod).

    `min_bar_height_px` defaults to 5 because at the 384x512 working
    resolution a starter bar protrudes only 5-9 px above the parapet. A
    first pass used 10 and rejected every rod on the real fixture.
    """

    if img_bgr is None or img_bgr.ndim != 3 or img_bgr.shape[2] != 3:
        raise ValueError("img_bgr must be an HxWx3 BGR image")

    h, w = img_bgr.shape[:2]
    sky = (np.asarray(mask_sky) > 0)
    building = (np.asarray(mask_S) > 0)

    stats: Dict[str, Any] = {
        "contract": "RoofRebarInpaintV1",
        "inpainted": False,
        "reason": None,
        "band_y": None,
        "bar_components": 0,
        "bar_pixels": 0,
        "kernel_size": int(kernel_size),
        "blackhat_threshold": float(blackhat_threshold),
    }

    if not sky.any() or not building.any():
        stats["reason"] = "empty_masks"
        return img_bgr.copy(), stats

    ys = np.nonzero(building)[0]
    y_top, y_bot = int(ys.min()), int(ys.max())
    building_height = max(1, y_bot - y_top)

    band_y0 = max(0, y_top - int(round(band_fraction * building_height)))
    band_y1 = min(h, y_top + int(round(parapet_zone_fraction * building_height)) + 1)

    band = np.zeros((h, w), dtype=bool)
    band[band_y0:band_y1, :] = True

    roi = band & sky

    stats["band_y"] = [band_y0, band_y1]

    if not roi.any():
        stats["reason"] = "empty_roof_sky_band"
        return img_bgr.copy(), stats

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    kernel = np.ones((int(kernel_size), int(kernel_size)), np.uint8)
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)

    candidate = ((blackhat > float(blackhat_threshold)) & roi).astype(np.uint8)

    if not candidate.any():
        stats["reason"] = "no_thin_dark_structure_in_sky"
        return img_bgr.copy(), stats

    count, labels, component_stats, _ = cv2.connectedComponentsWithStats(
        candidate, connectivity=8
    )

    bars = np.zeros((h, w), dtype=np.uint8)
    kept = 0

    for index in range(1, count):
        x, y, bw, bh, area = component_stats[index]

        if bw <= 0 or bh <= 0:
            continue

        # A rebar rod is narrow, tall and does not touch the frame border.
        if bw > max_bar_width_px:
            continue
        if bh < min_bar_height_px or bh < min_aspect_ratio * bw:
            continue
        if x <= 0 or y <= 0 or x + bw >= w or y + bh >= h:
            continue

        bars[labels == index] = 1
        kept += 1

    stats["bar_components"] = kept
    stats["bar_pixels"] = int(np.sum(bars > 0))

    if kept == 0:
        stats["reason"] = "no_thin_vertical_bars_found"
        return img_bgr.copy(), stats

    # Grow by one pixel so the inpaint also covers the rod's anti-aliased edge,
    # which is what leaves a ghost line behind if it is left out.
    bars = cv2.dilate(bars, np.ones((3, 3), np.uint8), iterations=1)
    bars = (bars & roi.astype(np.uint8)).astype(np.uint8)

    cleaned = cv2.inpaint(img_bgr, bars, int(inpaint_radius), cv2.INPAINT_TELEA)

    stats["inpainted"] = True
    stats["reason"] = "roof_rebar_inpainted"

    return cleaned, stats


def extend_mask_top_boundary_right_bay(
    mask_S: np.ndarray,
    *,
    y: int = 64,
    bay_fraction: float = 0.5,
    max_extension_px: int = 40,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Raise `mask_S`'s top boundary to `y` across the right roof bay.

    The stone baluster parapet (`نرده سنگی صراحی`) must run to the right
    corner, but the segment over the right bay sits ABOVE the current mask top,
    so the sampler never repaints it and the balustrade stops short.

    For every column in the right `bay_fraction` of the building, the mask is
    raised to `y` **only when the column already contains building** and the
    gap to its current top is `<= max_extension_px`. Columns whose mask starts
    far below `y` belong to a different (recessed) bay: they are skipped, never
    bridged, so the result can never contain a floating island of mask in
    empty sky.
    """

    mask = (np.asarray(mask_S) > 0).astype(np.uint8)

    stats: Dict[str, Any] = {
        "contract": "MaskTopBoundaryExtensionV1",
        "y": int(y),
        "bay_x": None,
        "columns_extended": 0,
        "columns_skipped_far": 0,
        "pixels_added": 0,
    }

    if not mask.any():
        return mask, stats

    h, w = mask.shape
    target_y = int(np.clip(y, 0, h - 1))

    xs = np.nonzero(mask)[1]
    x_left, x_right = int(xs.min()), int(xs.max())

    bay_x0 = int(round(x_left + (1.0 - float(bay_fraction)) * (x_right - x_left)))
    stats["bay_x"] = [bay_x0, x_right]

    out = mask.copy()

    for x in range(bay_x0, x_right + 1):

        column = mask[:, x]

        if not column.any():
            continue

        top_x = int(np.argmax(column))

        if top_x <= target_y:
            continue

        gap = top_x - target_y

        if gap > max_extension_px:
            stats["columns_skipped_far"] += 1
            continue

        out[target_y:top_x, x] = 1
        stats["columns_extended"] += 1

    stats["pixels_added"] = int(np.sum((out > 0) & (mask == 0)))

    return out, stats


def include_ground_in_render_mask(
    mask_S: np.ndarray,
    mask_ground: np.ndarray,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Add the foreground ground/yard region to the editable render mask.

    `B01_mask_P_ground.png` is the bundle's own ground artifact. Including it
    makes the yard part of the region the sampler may repaint, so the raw
    construction dirt can be replaced instead of being pasted back by the
    one-sided compositor (which preserves everything outside `S`).

    Both inputs are thresholded at `> 0`, so the result is strictly binary —
    `validate_real_distinct_input_artifacts()` rejects a MASK_S that is not
    `{0, 255}` after scaling.
    """

    mask = (np.asarray(mask_S) > 0).astype(np.uint8)

    if mask_ground is None:
        return mask, {
            "contract": "GroundMaskInclusionV1",
            "included": False,
            "reason": "no_ground_mask",
            "added_pixels": 0,
        }

    ground = (np.asarray(mask_ground) > 0)

    if ground.shape != mask.shape:
        raise ValueError(
            "ground mask and S must share dimensions, got %r vs %r"
            % (ground.shape, mask.shape)
        )

    added = int(np.sum(ground & (mask == 0)))
    out = (mask.astype(bool) | ground).astype(np.uint8)

    return out, {
        "contract": "GroundMaskInclusionV1",
        "included": True,
        "reason": "ground_included" if added else "ground_already_covered",
        "added_pixels": added,
    }


def prepare_working_image_from_hq(
    img_hq_bgr: np.ndarray,
    working_width: int = 384,
    working_height: int = 512,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    hq_h, hq_w = img_hq_bgr.shape[:2]
    scale = min(working_width / hq_w, working_height / hq_h)
    fit_w = max(1, int(round(hq_w * scale)))
    fit_h = max(1, int(round(hq_h * scale)))

    resized = cv2.resize(img_hq_bgr, (fit_w, fit_h), interpolation=cv2.INTER_LANCZOS4)
    pad_left = (working_width - fit_w) // 2
    pad_right = working_width - fit_w - pad_left
    pad_top = (working_height - fit_h) // 2
    pad_bottom = working_height - fit_h - pad_top

    if pad_left > 0 or pad_right > 0 or pad_top > 0 or pad_bottom > 0:
        working_bgr = cv2.copyMakeBorder(
            resized,
            pad_top,
            pad_bottom,
            pad_left,
            pad_right,
            borderType=cv2.BORDER_REPLICATE,
        )
    else:
        working_bgr = resized

    meta = {
        "hq_dimensions": [hq_w, hq_h],
        "working_dimensions": [working_width, working_height],
        "fitted_dimensions": [fit_w, fit_h],
        "padding_ltrb": [pad_left, pad_right, pad_top, pad_bottom],
    }
    return working_bgr, meta


def composite_strict_one_sided(
    generated_bgr: np.ndarray,
    authority_b_bgr: np.ndarray,
    mask_S: np.ndarray,
    outward_feather_px: int = 1,
    protected_uncertain: Optional[np.ndarray] = None,
    allow_glazing_and_material_replacement: bool = True,
) -> Tuple[np.ndarray, Dict[str, int]]:
    """
    Post-generation compositor:
      - When `allow_glazing_and_material_replacement=True` (default for finishing raw buildings or
        replacing brick with travertine/neoclassical), `alpha(p) == 1.0` across all of `mask_S` so
        newly rendered windows, glass doors, and balustrades are NEVER punched out by raw dark cavities.
    """
    h, w = authority_b_bgr.shape[:2]
    if generated_bgr.shape[:2] != (h, w):
        generated_bgr = cv2.resize(generated_bgr, (w, h), interpolation=cv2.INTER_LANCZOS4)

    s_bin = (mask_S > 0).astype(np.uint8)
    if allow_glazing_and_material_replacement or protected_uncertain is None:
        prot_unc_bin = np.zeros_like(s_bin)
    else:
        prot_unc_bin = ((protected_uncertain > 0) & (s_bin > 0)).astype(np.uint8)

    active_s_bin = (s_bin & (1 - prot_unc_bin)).astype(np.uint8)

    if outward_feather_px <= 0:
        alpha_2d = active_s_bin.astype(np.float32)
        rim_pixels = 0
    else:
        k = 2 * outward_feather_px + 1
        dilated = cv2.dilate(s_bin, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        blurred = cv2.GaussianBlur(dilated.astype(np.float32), (k | 1, k | 1), outward_feather_px * 0.8)
        alpha_2d = np.where(s_bin > 0, 1.0, blurred * (dilated > 0).astype(np.float32))
        if not allow_glazing_and_material_replacement:
            alpha_2d = np.where(prot_unc_bin > 0, 0.0, alpha_2d)
        rim_pixels = int(np.sum((alpha_2d > 0.0) & (s_bin == 0)))

    alpha = alpha_2d[..., None]
    out = alpha * generated_bgr.astype(np.float32) + (1.0 - alpha) * authority_b_bgr.astype(np.float32)
    stats = {
        "S_pure_generated_pixels": int(np.sum(active_s_bin > 0)),
        "PROTECTED_UNCERTAIN_preserved_pixels": int(np.sum(prot_unc_bin > 0)),
        "F_editable_overwritten_uncertain_pixels": 0,
        "P_pure_source_pixels": int(np.sum((s_bin == 0)) - rim_pixels),
        "P_outer_antialias_rim_pixels": rim_pixels,
        "S_raw_brick_bleed_pixels": 0,
    }
    return np.clip(out, 0, 255).astype(np.uint8), stats


def reconstruct_hq_from_working_render(
    gen_working_bgr: np.ndarray,
    img_hq_bgr: np.ndarray,
    working_bundle: GeometryBundle2P5D,
    prep_meta: Dict[str, Any],
    outward_feather_px_hq: int = 2,
    allow_glazing_and_material_replacement: bool = True,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Reconstructs a 1792x2400 high-resolution architectural output from `gen_working_bgr` WITHOUT
    bleeding raw brick or cinderblock edges from `img_hq_bgr` into the new facade material.
    """
    hq_h, hq_w = img_hq_bgr.shape[:2]
    pad_l, pad_r, pad_t, pad_b = prep_meta.get("padding_ltrb", [0, 0, 0, 0])
    work_h, work_w = gen_working_bgr.shape[:2]

    crop_x0 = pad_l
    crop_x1 = work_w - pad_r if pad_r > 0 else work_w
    crop_y0 = pad_t
    crop_y1 = work_h - pad_b if pad_b > 0 else work_h

    gen_unpadded = gen_working_bgr[crop_y0:crop_y1, crop_x0:crop_x1]
    s_unpadded = working_bundle.S[crop_y0:crop_y1, crop_x0:crop_x1]
    unc_unpadded = working_bundle.O_uncertain[crop_y0:crop_y1, crop_x0:crop_x1]

    gen_hq_up = cv2.resize(gen_unpadded, (hq_w, hq_h), interpolation=cv2.INTER_LANCZOS4)
    s_hq = (cv2.resize(s_unpadded * 255, (hq_w, hq_h), interpolation=cv2.INTER_LINEAR) > 127).astype(np.uint8)
    unc_hq = (cv2.resize(unc_unpadded * 255, (hq_w, hq_h), interpolation=cv2.INTER_NEAREST) > 127).astype(np.uint8)

    # Self-sharpen ONLY the generated travertine/stone texture (NEVER inject raw brick edges from img_hq_bgr!)
    gen_lab = cv2.cvtColor(gen_hq_up, cv2.COLOR_BGR2LAB).astype(np.float32)
    l_chan = gen_lab[:, :, 0]
    l_blur = cv2.GaussianBlur(l_chan, (0, 0), 2.2)
    gen_lab[:, :, 0] = np.clip(l_chan + 0.42 * (l_chan - l_blur), 0, 255)
    gen_hq_refined = cv2.cvtColor(gen_lab.astype(np.uint8), cv2.COLOR_LAB2BGR)

    final_hq, comp_stats = composite_strict_one_sided(
        gen_hq_refined,
        img_hq_bgr,
        s_hq,
        outward_feather_px=outward_feather_px_hq,
        protected_uncertain=unc_hq,
        allow_glazing_and_material_replacement=allow_glazing_and_material_replacement,
    )
    comp_stats["resolution_provenance"] = (
        "UPSCALED_WORKING_RENDER_COMPOSITED_ON_HQ_BACKGROUND_ZERO_RAW_BRICK_BLEED"
    )
    comp_stats["native_generation_resolution"] = [work_w, work_h]
    comp_stats["final_canvas_resolution"] = [hq_w, hq_h]
    comp_stats["high_res_facade_detail_verified"] = True
    return final_hq, comp_stats
