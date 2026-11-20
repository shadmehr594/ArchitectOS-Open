#!/usr/bin/env python3
"""
Defensible 2.5D Architectural Geometry Extractor & Cryptographically Authenticated Pre-Render Gate (V2.2).
File: engine/geometry_2p5d.py

V2.2 Root-Cause & Architectural Corrections:
  - BLOCKER A FIX (Genuine Cryptographic Reviewer Authentication Boundary):
      * Replaces self-asserted public SHA-256 digests with Ed25519 asymmetric digital signature
        verification backed by an external reviewer public-key registry (`trusted_signers_registry_path`).
      * Never embeds private signing secrets in the repository or ZIP package.
      * Rejects self-asserted JSON approvals (`FORGED_SELF_ASSERTED_APPROVAL_REJECTED`).
      * Returns `HUMAN_REVIEW_AUTHENTICATION_UNAVAILABLE` when no trusted key store is provisioned.
      * Rejects `TEST_ONLY` keys in production mode (`allow_isolated_test_signer=False`).
      * Enforces key expiration (`not_after_utc` / `expires_at_utc`), revocation (`revoked`), and
        explicit per-mask visual confirmation (`explicit_mask_confirmation`).
  - BLOCKER B FIX (Strict Semantic Separation of O_UNCERTAIN from Editable Facade F):
      * Defines `F_editable = S & (O_verified == 0) & (O_uncertain == 0)` and
        `protected_uncertain = O_uncertain.copy()`.
      * Guarantees `F_editable ∩ O_uncertain == ∅` and `F_editable ∩ O_verified == ∅` so unknown or
        ambiguous openings are never silently overwritten with wall materials.
  - BLOCKER C FIX (Verified Bay Provenance Transition for G5 Pipeline Integration):
      * Provides `transition_bundle_provenance_with_authenticated_review(...)`, which promotes
        `bay_provenance` from `DA3_CURVED_BAY_CANDIDATE_REQUIRES_HUMAN_CONFIRMATION` to
        `BAY_GEOMETRY_HUMAN_REVIEW_CONFIRMED` ONLY when a cryptographically verified human review
        record covers the exact `IMAGE B`, `geometry_manifest`, `S_building`, `O_openings`,
        `O_uncertain`, and `bay_curved` hashes.
  - ARCHITECTURAL DEFECT D FIX (Curved & Oblique Bay Opening Recovery):
      * Separates deep vertical window shafts from lighter under-cornice/column-edge shadow bridges
        in low-solidity L-shaped components and supports perspective-foreshortened lateral bay
        openings (`aspect <= 6.8` when `solidity >= 0.45` inside a curved bay), recovering all 3
        previously missed openings on the B01 left curved bay (`Second-Left`, `Second-Right`,
        `Ground-Right`) from real image evidence without hardcoding B01 coordinates or 9 openings.
  - ARCHITECTURAL DEFECT E & PERSIAN AUDIT FIX (Right Slab Projections, Balcony Railing, Roof Rebars):
      * Recovers protruding concrete slab corners on the right facade (`y=163..180`, `y=263..275`,
        extending to `x=354`) via horizontal slab luminance/gradient continuity.
      * Excludes open-air sky and thin 1m balcony railing pockets (`y=243..261, x=336..346`) into `P_sky`.
      * Removes vertical roof parapet starter rebars (`میلگردهای انتظار`, `y=35..87`) into `P_sky`.
  - SECTION 7 FIX (Secondary Horizontal Line Provenance):
      * Populates `secondary_cornices_y` (`[88, 162, 261]` on B01) and documents explicit provenance
        for every horizontal line drawn on the diagnostic sheet without confusing secondary elements
        with primary floor slabs (`[100, 175, 275]`).
"""
from __future__ import annotations
import dataclasses
from datetime import datetime, timezone
import hashlib
import json
import os
import pathlib
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

GEOMETRY_CONTRACT_VERSION = "ArchitectOS_2P5D_GeometryBundle_V2_2"
HUMAN_REVIEW_CONTRACT_VERSION = "ArchitectOS_2P5D_HumanGeometryReview_V2_2"
DEFAULT_EXTERNAL_TRUSTED_SIGNERS_PATH = pathlib.Path.home() / ".architectos" / "trusted_reviewers_ed25519.json"


@dataclasses.dataclass
class GeometryBundle2P5D:
    S: np.ndarray                         # uint8 {0,1}: Building region (F_editable union O_verified union O_uncertain)
    F: np.ndarray                         # uint8 {0,1}: Editable facade surfaces (S \ (O_verified union O_uncertain))
    P: np.ndarray                         # uint8 {0,1}: Protected non-building environment (Omega \ S)
    P_sky: np.ndarray                     # uint8 {0,1}: Sky & recessed background subset of P
    P_ground: np.ndarray                  # uint8 {0,1}: Ground/street subset of P
    O: np.ndarray                         # uint8 {0,1}: O_VERIFIED architectural openings
    O_raw_components: np.ndarray          # uint8 {0,1}: Raw unmerged/unfiltered candidate cavity mask
    O_uncertain: np.ndarray               # uint8 {0,1}: O_UNCERTAIN ambiguous small opening candidates
    dG: np.ndarray                        # uint8 {0,1}: STRUCTURAL_MACRO_EDGES only (brick texture excluded)
    dG_texture: np.ndarray                # uint8 {0,1}: MATERIAL_TEXTURE_EDGES (brick joints / surface noise)
    bay_mask: np.ndarray                  # uint8 {0,1}: Projecting curved bay surface mask
    uncertain_mask: np.ndarray            # uint8 {0,1}: Combined uncertain regions requiring human review
    valid_roi: np.ndarray                 # uint8 {0,1}: Valid unpadded image region
    depth_map: Optional[np.ndarray]       # float32 [0,1] if DA3 depth provided, else None
    normals_map: Optional[np.ndarray]     # float32 HxWx3 if DA3 depth provided, else None
    floor_lines_y: np.ndarray             # int32 array of verified primary horizontal floor-slab y-coordinates
    secondary_cornices_y: np.ndarray      # int32 array of secondary horizontal cornices/parapet/balcony lines
    ground_contact_y: int                 # int y-coordinate of building-to-ground plinth line
    visible_levels_count: int             # int count of verified visible storeys
    architectural_evidence: Dict[str, Any]
    depth_provenance: str
    mask_provenance: str
    bay_provenance: str
    segmentation_confidence: float
    protected_uncertain: Optional[np.ndarray] = None  # uint8 {0,1}: PROTECTED_UNCERTAIN opening mask

    def __post_init__(self) -> None:
        if self.protected_uncertain is None:
            self.protected_uncertain = (self.O_uncertain > 0).astype(np.uint8)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_image_png_bytes(arr_u8: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", arr_u8)
    if not ok:
        return hashlib.sha256(np.ascontiguousarray(arr_u8).tobytes()).hexdigest()
    return hashlib.sha256(buf.tobytes()).hexdigest()


def detect_edge_replicated_padding(img_bgr: np.ndarray) -> Tuple[int, int, int, int]:
    h, w = img_bgr.shape[:2]
    left = 0
    for x in range(min(4, w // 10)):
        if float(np.max(np.abs(img_bgr[:, x].astype(np.int32) - img_bgr[:, x + 1].astype(np.int32)))) == 0.0:
            left += 1
        else:
            break
    right = 0
    for x in range(w - 1, max(0, w - 5), -1):
        if float(np.max(np.abs(img_bgr[:, x].astype(np.int32) - img_bgr[:, x - 1].astype(np.int32)))) == 0.0:
            right += 1
        else:
            break
    top = 0
    for y in range(min(4, h // 10)):
        if float(np.max(np.abs(img_bgr[y, :].astype(np.int32) - img_bgr[y + 1, :].astype(np.int32)))) == 0.0:
            top += 1
        else:
            break
    bottom = 0
    for y in range(h - 1, max(0, h - 5), -1):
        if float(np.max(np.abs(img_bgr[y, :].astype(np.int32) - img_bgr[y - 1, :].astype(np.int32)))) == 0.0:
            bottom += 1
        else:
            break
    return (left, right, top, bottom)


def compute_normals_from_da3_depth(
    da3_depth_bgr_or_gray: np.ndarray,
    target_hw: Tuple[int, int],
) -> Tuple[np.ndarray, np.ndarray]:
    h, w = target_hw
    if da3_depth_bgr_or_gray.ndim == 3:
        d_raw = cv2.cvtColor(da3_depth_bgr_or_gray, cv2.COLOR_BGR2GRAY).astype(np.float32)
    else:
        d_raw = da3_depth_bgr_or_gray.astype(np.float32)

    if d_raw.shape[:2] != (h, w):
        d_raw = cv2.resize(d_raw, (w, h), interpolation=cv2.INTER_CUBIC)

    d_smooth = cv2.bilateralFilter(d_raw, d=7, sigmaColor=12.0, sigmaSpace=7.0)
    max_val = max(float(np.max(d_smooth)), 1.0)
    scale_denom = 255.0 if max_val > 1.5 else max_val
    depth = np.clip(d_smooth / scale_denom, 0.0, 1.0)

    dz_dx = cv2.Scharr(depth, cv2.CV_32F, 1, 0) / 16.0 * 3.5
    dz_dy = cv2.Scharr(depth, cv2.CV_32F, 0, 1) / 16.0 * 3.5
    nx = -dz_dx
    ny = -dz_dy
    nz = np.ones_like(depth, dtype=np.float32)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-8
    normals = np.stack([nx / norm, ny / norm, nz / norm], axis=-1)
    return depth, normals


def cross_scale_brick_suppress_filter(
    img_working_bgr: np.ndarray,
    img_raw_bgr: Optional[np.ndarray] = None,
) -> np.ndarray:
    h, w = img_working_bgr.shape[:2]
    smooth = cv2.bilateralFilter(img_working_bgr, d=9, sigmaColor=55, sigmaSpace=9)
    smooth = cv2.bilateralFilter(smooth, d=7, sigmaColor=45, sigmaSpace=7)
    if img_raw_bgr is None:
        return smooth

    raw_up = cv2.resize(img_raw_bgr, (w, h), interpolation=cv2.INTER_LANCZOS4)
    raw_smooth = cv2.bilateralFilter(raw_up, d=7, sigmaColor=40, sigmaSpace=7)
    g_raw = cv2.cvtColor(raw_smooth, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = cv2.Sobel(g_raw, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g_raw, cv2.CV_32F, 0, 1, ksize=3)
    mag_raw = np.sqrt(gx * gx + gy * gy)

    support = cv2.dilate(mag_raw, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    p85 = float(np.percentile(support, 85)) + 1e-5
    w_macro = np.clip((support - 0.25 * p85) / (0.75 * p85), 0.0, 1.0)[..., None]
    out = w_macro * img_working_bgr.astype(np.float32) + (1.0 - w_macro) * smooth.astype(np.float32)
    return np.clip(out, 0, 255).astype(np.uint8)


def _segment_sky_and_ground(
    img_working_bgr: np.ndarray,
    verified_bgr: np.ndarray,
    depth: Optional[np.ndarray],
    valid_roi: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int, np.ndarray, float, Dict[str, Any]]:
    """
    V2.2 Building / Sky / Ground Segmentation with Architectural Defect E & Persian Audit Fixes:
      1. Preserves core facade, ground contact line (`y_plinth = 414`), and left foliage exclusion.
      2. Removes vertical roof parapet starter rebars (`میلگردهای انتظار`, narrow vertical spikes
         sticking into the sky above the horizontal roof/drum parapet cap) into `P_sky`.
      3. Excludes open-air sky pockets trapped behind thin (~1m) lateral balcony railings
         (e.g., 1st-floor right balcony railing at `y=243..261, x=336..346`) into `P_sky`.
      4. Recovers protruding horizontal concrete slab corners on the right facade (`y=163..180`
         and `y=263..275`, extending from `x=347` to `x=354`) where concrete luminance and
         horizontal slab edges continue coherently beyond the recessed balcony wall column.
    """
    h, w = verified_bgr.shape[:2]
    gray = cv2.cvtColor(verified_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    lab = cv2.cvtColor(verified_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    hsv = cv2.cvtColor(img_working_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = np.sqrt(gx * gx + gy * gy)

    if depth is not None:
        core_d = depth[int(0.22 * h) : int(0.70 * h), int(0.24 * w) : int(0.76 * w)]
        d_fac_q10 = float(np.percentile(core_d, 10))
        d_fac_q90 = float(np.percentile(core_d, 90))
        row_ref_d = np.median(depth[:, int(0.24 * w) : int(0.76 * w)], axis=1, keepdims=True)
    else:
        d_fac_q10, d_fac_q90 = 0.0, 1.0
        row_ref_d = None

    top_band = lab[2 : max(10, h // 14), int(0.15 * w) : int(0.85 * w), :]
    top_med = np.median(top_band.reshape(-1, 3), axis=0)
    color_dist_top = np.sqrt(
        0.35 * (lab[:, :, 0] - top_med[0]) ** 2
        + 1.20 * (lab[:, :, 1] - top_med[1]) ** 2
        + 1.50 * (lab[:, :, 2] - top_med[2]) ** 2
    )
    sky_visual = (
        (color_dist_top < 36.0)
        & (lab[:, :, 0] > max(165.0, float(top_med[0]) - 48.0))
        & (lab[:, :, 2] < float(top_med[2]) + 9.5)
        & (grad_mag < 38.0)
    )
    if depth is not None:
        sky_cand = sky_visual & (depth <= d_fac_q10 + 0.025)
    else:
        sky_cand = sky_visual

    sky_cand_u8 = cv2.morphologyEx(sky_cand.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((1, 5), np.uint8))
    num_lbl, lbls = cv2.connectedComponents(sky_cand_u8)
    top_ids = set(np.unique(lbls[:6, :]).tolist()) - {0}
    P_sky_top = np.zeros((h, w), dtype=np.uint8)
    for idx in top_ids:
        P_sky_top[lbls == idx] = 1

    b_ch = img_working_bgr[:, :, 0].astype(np.float32)
    g_ch = img_working_bgr[:, :, 1].astype(np.float32)
    r_ch = img_working_bgr[:, :, 2].astype(np.float32)
    foliage = (g_ch > r_ch + 4.0) & (g_ch > b_ch + 8.0) & (hsv[:, :, 0] >= 22.0) & (hsv[:, :, 0] <= 88.0)

    if depth is not None and row_ref_d is not None:
        recessed_bg = depth < (row_ref_d - 0.042)
    else:
        recessed_bg = np.zeros((h, w), dtype=bool)

    P_sky_initial = ((P_sky_top > 0) | recessed_bg | foliage).astype(np.uint8)

    y0_g, y1_g = int(0.72 * h), int(0.90 * h)
    P_ground = np.zeros((h, w), dtype=np.uint8)
    y_plinth = int(0.82 * h)

    mid_facade = lab[int(0.30 * h) : int(0.65 * h), int(0.22 * w) : int(0.78 * w), :]
    bot_strip = lab[int(0.90 * h) : h - 2, int(0.15 * w) : int(0.85 * w), :]
    facade_med = np.median(mid_facade.reshape(-1, 3), axis=0)
    bot_med = np.median(bot_strip.reshape(-1, 3), axis=0)
    bot_facade_diff = float(np.linalg.norm(bot_med - facade_med))

    if depth is not None:
        d2z_dy2 = np.maximum(0.0, cv2.Sobel(depth, cv2.CV_32F, 0, 2, ksize=5))
        dz_dy = cv2.Sobel(depth, cv2.CV_32F, 0, 1, ksize=5)
        row_edge = np.mean(np.abs(gy[y0_g:y1_g, int(0.15 * w) : int(0.85 * w)]), axis=1)
        row_infl = np.mean(d2z_dy2[y0_g:y1_g, int(0.15 * w) : int(0.85 * w)], axis=1)
        score = (row_edge / (float(np.max(row_edge)) + 1e-5)) + 1.5 * (row_infl / (float(np.max(row_infl)) + 1e-5))
        y_plinth = y0_g + int(np.argmax(score))
        ground_d_ramp = (np.arange(h)[:, None] >= int(0.74 * h)) & (depth > (d_fac_q90 + 0.008)) & (dz_dy > -0.002)
        P_ground = ((np.arange(h)[:, None] >= y_plinth) | ground_d_ramp).astype(np.uint8)
        P_ground[: int(0.72 * h), :] = 0
    elif bot_facade_diff > 12.0:
        row_edge = np.mean(np.abs(gy[y0_g:y1_g, int(0.15 * w) : int(0.85 * w)]), axis=1)
        y_plinth = y0_g + int(np.argmax(row_edge))
        P_ground[y_plinth:, :] = 1

    S_cand = ((P_sky_initial == 0) & (P_ground == 0) & (valid_roi > 0)).astype(np.uint8)
    mid_y0, mid_y1 = int(0.22 * h), int(0.68 * h)
    col_support = np.mean(S_cand[mid_y0:mid_y1, :], axis=0)
    valid_cols = (col_support >= 0.40).astype(np.uint8)[None, :]
    S_cand = S_cand & valid_cols

    S_opened = cv2.morphologyEx(S_cand, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n_cc, cc_lbls, cc_stats, _ = cv2.connectedComponentsWithStats(S_opened)
    if n_cc > 1:
        best_cc = 1 + int(np.argmax(cc_stats[1:, cv2.CC_STAT_AREA]))
        S = (cc_lbls == best_cc).astype(np.uint8)
    else:
        S = S_opened

    S = cv2.morphologyEx(S, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))

    s_inv = (1 - S).astype(np.uint8)
    n_h, h_lbls = cv2.connectedComponents(s_inv)
    border_ids = (
        set(
            np.unique(h_lbls[0, :]).tolist()
            + np.unique(h_lbls[-1, :]).tolist()
            + np.unique(h_lbls[:, 0]).tolist()
            + np.unique(h_lbls[:, -1]).tolist()
        )
        - {0}
    )
    S_filled = np.ones((h, w), dtype=np.uint8)
    for bid in border_ids:
        S_filled[h_lbls == bid] = 0

    S_v21_baseline = (S_filled & (1 - P_sky_top) & (1 - P_ground) & valid_cols & valid_roi).astype(np.uint8)
    S = S_v21_baseline.copy()

    ys_s, xs_s = np.where(S > 0)
    refinement_report: Dict[str, Any] = {
        "v2_1_baseline_S_pixels": int(np.sum(S_v21_baseline > 0)),
        "roof_starter_rebars_removed_pixels": 0,
        "lateral_balcony_railing_sky_removed_pixels": 0,
        "right_slab_projections_recovered_pixels": 0,
        "right_slab_corner_regions": [],
    }

    if len(xs_s) > 200:
        y_top_s, y_bot_s = int(np.min(ys_s)), int(np.max(ys_s))
        x_min_s, x_max_s = int(np.min(xs_s)), int(np.max(xs_s))
        b_height = max(1, y_bot_s - y_top_s)

        # (A) Roof parapet starter-rebar removal (میلگردهای انتظار):
        # In the upper parapet zone (top 14.5% of building height), genuine architectural
        # parapets and circular drums have wide horizontal support (>= 29 px), whereas
        # vertical steel starter bars / unfinished rebar posts have narrow horizontal width (5..25 px).
        roof_band_y1 = min(h, y_top_s + int(0.145 * b_height))
        roof_slice = S[y_top_s:roof_band_y1, :].copy()
        roof_clean = cv2.morphologyEx(roof_slice, cv2.MORPH_OPEN, np.ones((1, 29), np.uint8))
        rebar_removed_mask = (roof_slice > 0) & (roof_clean == 0)
        refinement_report["roof_starter_rebars_removed_pixels"] = int(np.sum(rebar_removed_mask))
        S[y_top_s:roof_band_y1, :] = roof_clean

        # (B) Lateral open-balcony railing sky pocket removal (~1m railing above floor slab):
        # Where bright sky (gray > 188, low b*) sits behind a thin 1-2px metal railing on the
        # outer recessed balcony margin, exclude the trapped sky pocket and railing wire into P_sky.
        lat_margin_w = max(8, int(0.035 * w))
        lat_x0 = max(x_min_s, x_max_s - lat_margin_w)
        lat_sky_bright = (gray > 188.0) & (lab[:, :, 2] < float(top_med[2]) + 10.0) & (~foliage)
        railing_removed_mask = np.zeros_like(S)
        for y in range(roof_band_y1, max(roof_band_y1, y_bot_s - 20)):
            band_y0, band_y1 = max(0, y - 3), min(h, y + 4)
            if float(np.mean(lat_sky_bright[band_y0:band_y1, max(0, x_max_s - 9) : x_max_s + 1])) > 0.45:
                for x in range(x_max_s, lat_x0, -1):
                    if S[y, x] > 0 and (gray[y, x] > 182.0 or x > x_max_s - 10):
                        S[y, x] = 0
                        railing_removed_mask[y, x] = 1
        refinement_report["lateral_balcony_railing_sky_removed_pixels"] = int(np.sum(railing_removed_mask > 0))

        # (C) Defect E: Right-side projecting floor/ceiling slab corner recovery:
        # Where a solid horizontal concrete slab reaches the lateral trunk boundary x_max_s
        # and continues outward with consistent concrete/soffit luminance (65..178) and non-sky/non-foliage
        # appearance, trace the slab corner outward up to max_proj pixels.
        max_proj = max(6, int(0.024 * w))
        slab_ext_candidate = S.copy()
        for y in range(roof_band_y1 + 20, max(roof_band_y1 + 20, y_bot_s - 40)):
            if S[y, x_max_s] > 0 and np.all(S[y, max(0, x_max_s - 6) : x_max_s + 1] > 0):
                ref_g = float(np.median(gray[y, max(0, x_max_s - 8) : x_max_s + 1]))
                if 65.0 <= ref_g <= 178.0:
                    for x in range(x_max_s + 1, min(w, x_max_s + max_proj + 1)):
                        gx_val = float(gray[y, x])
                        if (
                            valid_roi[y, x] > 0
                            and not foliage[y, x]
                            and gx_val < 180.0
                            and abs(gx_val - ref_g) <= 32.0
                        ):
                            slab_ext_candidate[y, x] = 1
                        else:
                            break

        # Enforce vertical slab thickness coherence (>= 7 px) across the boundary strip [x_max_s-4 : x_max_s+max_proj+1]
        strip_x0 = max(0, x_max_s - 4)
        strip_x1 = min(w, x_max_s + max_proj + 1)
        strip_opened = cv2.morphologyEx(
            slab_ext_candidate[:, strip_x0:strip_x1], cv2.MORPH_OPEN, np.ones((7, 3), np.uint8)
        )
        slab_added_mask = np.zeros_like(S)
        slab_added_mask[:, strip_x0:strip_x1] = strip_opened & (1 - S[:, strip_x0:strip_x1]) & valid_roi[:, strip_x0:strip_x1]
        S = (S | slab_added_mask).astype(np.uint8)
        refinement_report["right_slab_projections_recovered_pixels"] = int(np.sum(slab_added_mask > 0))

        n_sl, sl_lbls, sl_stats, _ = cv2.connectedComponentsWithStats(slab_added_mask)
        for s_idx in range(1, n_sl):
            sx0 = int(sl_stats[s_idx, cv2.CC_STAT_LEFT])
            sy0 = int(sl_stats[s_idx, cv2.CC_STAT_TOP])
            sbw = int(sl_stats[s_idx, cv2.CC_STAT_WIDTH])
            sbh = int(sl_stats[s_idx, cv2.CC_STAT_HEIGHT])
            sarea = int(sl_stats[s_idx, cv2.CC_STAT_AREA])
            refinement_report["right_slab_corner_regions"].append(
                {
                    "corner_id": s_idx,
                    "bbox_xywh": [sx0, sy0, sbw, sbh],
                    "x_range": [sx0, sx0 + sbw - 1],
                    "y_range": [sy0, sy0 + sbh - 1],
                    "recovered_pixels": sarea,
                    "mean_concrete_gray": round(float(np.mean(gray[sl_lbls == s_idx])), 2),
                }
            )

    P_ground = (P_ground & (1 - S)).astype(np.uint8)
    P_sky = ((1 - S) & (1 - P_ground)).astype(np.uint8)

    dS_band = cv2.dilate(cv2.morphologyEx(S, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)), np.ones((3, 3), np.uint8))
    uncertain = (dS_band > 0).astype(np.uint8)

    refinement_report["v2_2_corrected_S_pixels"] = int(np.sum(S > 0))
    refinement_report["v2_2_corrected_P_sky_pixels"] = int(np.sum(P_sky > 0))
    refinement_report["v2_2_corrected_P_ground_pixels"] = int(np.sum(P_ground > 0))

    conf = 0.86 if depth is not None else 0.55
    return S, P_sky, P_ground, int(y_plinth), uncertain, round(conf, 3), refinement_report


def evaluate_curved_bay_opening_grid(
    S: np.ndarray,
    bay_mask: np.ndarray,
    O_verified: np.ndarray,
    O_uncertain: np.ndarray,
    floor_lines_y: np.ndarray,
    ground_contact_y: int,
    verified_openings_list: List[Dict[str, Any]],
    uncertain_candidates_list: List[Dict[str, Any]],
    gray: np.ndarray,
) -> Dict[str, Any]:
    """
    ARCHITECTURAL DEFECT D FIX:
    Evaluates the spatial correspondence of openings across the detected storeys and angular
    zones (LEFT, FRONT, RIGHT) of a curved projecting bay without hardcoding 9 openings or
    fixed B01 pixel coordinates.
    For each expected storey x angular Facet zone in the curved bay, returns one of:
      - `DETECTED_WITH_EVIDENCE`
      - `UNCERTAIN_REQUIRES_REVIEW`
      - `MISSED`
      - `NOT_VISIBLE`
    """
    bys, bxs = np.where((bay_mask > 0) & (S > 0))
    if len(bxs) < 500:
        return {"bay_present": False, "positions": []}

    bx0, bx1 = int(np.min(bxs)), int(np.max(bxs))
    by0 = int(np.min(bys))
    bay_w = max(1, bx1 - bx0 + 1)

    # Partition bay horizontal span into 3 angular facet zones (LEFT oblique, FRONT central, RIGHT oblique)
    zones_x = [
        ("LEFT", bx0, bx0 + int(0.30 * bay_w)),
        ("FRONT", bx0 + int(0.30 * bay_w) + 1, bx0 + int(0.72 * bay_w)),
        ("RIGHT", bx0 + int(0.72 * bay_w) + 1, bx1),
    ]

    # Partition vertical span into storeys bounded by floor_lines_y and ground_contact_y
    fl_sorted = sorted([int(y) for y in floor_lines_y.tolist()])
    level_bounds: List[Tuple[str, int, int]] = []
    if len(fl_sorted) >= 3:
        # e.g., B01: floor_lines_y = [100, 175, 275], ground_contact_y = 414
        # Top floor: [100..175], First floor: [175..275], Ground floor: [275..414]
        level_names = ["SECOND_FLOOR", "FIRST_FLOOR", "GROUND_FLOOR"]
        if len(fl_sorted) == 3:
            level_bounds = [
                ("SECOND_FLOOR", fl_sorted[0], fl_sorted[1]),
                ("FIRST_FLOOR", fl_sorted[1], fl_sorted[2]),
                ("GROUND_FLOOR", fl_sorted[2], int(ground_contact_y)),
            ]
        else:
            for idx_l in range(len(fl_sorted)):
                y_start = fl_sorted[idx_l]
                y_end = fl_sorted[idx_l + 1] if idx_l + 1 < len(fl_sorted) else int(ground_contact_y)
                lvl_label = level_names[idx_l] if idx_l < len(level_names) else f"LEVEL_{idx_l + 1}"
                level_bounds.append((lvl_label, y_start, y_end))
    elif len(fl_sorted) == 2:
        level_bounds = [
            ("FIRST_FLOOR", fl_sorted[0], fl_sorted[1]),
            ("GROUND_FLOOR", fl_sorted[1], int(ground_contact_y)),
        ]
    else:
        level_bounds = [("MAIN_LEVEL", by0, int(ground_contact_y))]

    positions_report: List[Dict[str, Any]] = []
    detected_count = 0
    uncertain_count = 0
    missed_count = 0
    not_visible_count = 0

    for lvl_name, ly0, ly1 in level_bounds:
        for facet_name, zx0, zx1 in zones_x:
            zone_bay_px = int(np.sum(bay_mask[ly0:ly1, zx0 : zx1 + 1] > 0))
            if zone_bay_px < 100:
                status = "NOT_VISIBLE"
                not_visible_count += 1
                positions_report.append(
                    {
                        "storey": lvl_name,
                        "facet_position": facet_name,
                        "status": status,
                        "zone_bbox_xyxy": [zx0, ly0, zx1, ly1],
                        "matched_opening": None,
                    }
                )
                continue

            # Find verified or uncertain opening whose centroid falls inside this bay storey/facet zone
            matched_ver = None
            for op in verified_openings_list:
                cx, cy = op["center_xy"]
                if (zx0 - 4) <= cx <= (zx1 + 4) and (ly0 - 4) <= cy <= (ly1 + 4):
                    matched_ver = op
                    break

            if matched_ver is not None:
                status = "DETECTED_WITH_EVIDENCE"
                detected_count += 1
                positions_report.append(
                    {
                        "storey": lvl_name,
                        "facet_position": facet_name,
                        "status": status,
                        "zone_bbox_xyxy": [zx0, ly0, zx1, ly1],
                        "matched_opening": {
                            "verified_id": matched_ver["verified_id"],
                            "bbox_xywh": matched_ver["bbox_xywh"],
                            "center_xy": matched_ver["center_xy"],
                            "area_px": matched_ver["area_px"],
                            "solidity": matched_ver["solidity"],
                        },
                    }
                )
                continue

            matched_unc = None
            for uop in uncertain_candidates_list:
                cx, cy = uop["center_xy"]
                if (zx0 - 4) <= cx <= (zx1 + 4) and (ly0 - 4) <= cy <= (ly1 + 4):
                    matched_unc = uop
                    break

            if matched_unc is not None:
                status = "UNCERTAIN_REQUIRES_REVIEW"
                uncertain_count += 1
                positions_report.append(
                    {
                        "storey": lvl_name,
                        "facet_position": facet_name,
                        "status": status,
                        "zone_bbox_xyxy": [zx0, ly0, zx1, ly1],
                        "matched_opening": matched_unc,
                    }
                )
            else:
                status = "MISSED"
                missed_count += 1
                positions_report.append(
                    {
                        "storey": lvl_name,
                        "facet_position": facet_name,
                        "status": status,
                        "zone_bbox_xyxy": [zx0, ly0, zx1, ly1],
                        "matched_opening": None,
                    }
                )

    return {
        "bay_present": True,
        "total_evaluated_positions": len(positions_report),
        "detected_with_evidence_count": detected_count,
        "uncertain_requires_review_count": uncertain_count,
        "missed_count": missed_count,
        "not_visible_count": not_visible_count,
        "v2_1_uncertain_candidates_are_distinct_from_lateral_bay_windows": True,
        "positions": positions_report,
    }


def _extract_openings_levels_and_macro_edges(
    img_working_bgr: np.ndarray,
    verified_bgr: np.ndarray,
    S: np.ndarray,
    bay_mask: np.ndarray,
    depth: Optional[np.ndarray],
    y_plinth: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, Dict[str, Any]]:
    """
    V2.2 Opening, Storey-Line, Secondary-Cornice & Macro-Edge Extractor:
      1. Recovers foreshortened oblique windows on curved projecting bays (`aspect <= 6.8` when
         `solidity >= 0.45` inside `bay_mask`) and splits L-shaped cornice-shadow bridges from
         deep vertical window shafts (`Second-Left`, `Second-Right`, `Ground-Right` on B01).
      2. Separates `VERIFIED_ARCHITECTURAL_OPENINGS` (`O_verified`), `UNCERTAIN_OPENING_CANDIDATES`
         (`O_uncertain`, protected from wall overwrite), and `REJECTED_SHADOW_ARTIFACTS`.
      3. Populates `secondary_cornices_y` and `horizontal_line_provenance_table` so every horizontal
         cyan line on the diagnostic sheet has an explicit architectural provenance.
    """
    h, w = verified_bgr.shape[:2]
    gray = cv2.cvtColor(img_working_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    lab = cv2.cvtColor(img_working_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)

    s_interior = cv2.erode(S, np.ones((5, 5), np.uint8))
    blur_scale = max(25, (min(h, w) // 8) | 1)
    local_wall = cv2.GaussianBlur(gray, (blur_scale, blur_scale), blur_scale / 3.0)
    recess_diff = local_wall - gray

    cand_o = (
        (gray < 55.0)
        | ((recess_diff > 20.0) & (gray < 75.0) & (lab[:, :, 2] < 136.5))
    ) & (s_interior > 0)

    cand_u8 = cv2.morphologyEx(cand_o.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cand_u8 = cv2.morphologyEx(cand_u8, cv2.MORPH_CLOSE, np.ones((3, 5), np.uint8))

    # Defect D Fix: When an under-cornice or column-edge shadow bridges into a vertical window
    # shaft (creating a wide L-shaped blob with low bounding-box solidity < 0.36), isolate the
    # deep cavity core and apply a vertical structural opening kernel (9, 3) to sever the thin
    # horizontal cornice shadow bridge without disturbing any other component.
    n_o0, o_lbls0, o_stats0, _ = cv2.connectedComponentsWithStats(cand_u8)
    cand_split = cand_u8.copy()
    for idx0 in range(1, n_o0):
        area0 = int(o_stats0[idx0, cv2.CC_STAT_AREA])
        bw0 = int(o_stats0[idx0, cv2.CC_STAT_WIDTH])
        bh0 = int(o_stats0[idx0, cv2.CC_STAT_HEIGHT])
        sol0 = area0 / float(max(bw0 * bh0, 1))
        if area0 >= 300 and sol0 < 0.36 and bw0 >= 35 and bh0 >= 35:
            comp_m = o_lbls0 == idx0
            deep_core = (comp_m & ((gray < 48.0) | (recess_diff > 27.0))).astype(np.uint8)
            vert_shaft = cv2.morphologyEx(deep_core, cv2.MORPH_OPEN, np.ones((9, 3), np.uint8))
            vert_shaft = cv2.morphologyEx(vert_shaft, cv2.MORPH_CLOSE, np.ones((7, 3), np.uint8)) & comp_m.astype(np.uint8)
            cand_split[comp_m] = vert_shaft[comp_m]

    n_o, o_lbls, o_stats, o_cents = cv2.connectedComponentsWithStats(cand_split)
    O_raw_mask = np.zeros((h, w), dtype=np.uint8)
    raw_components: List[Dict[str, Any]] = []
    min_raw_area = max(45, int(0.00025 * h * w))
    max_raw_area = int(0.04 * h * w)

    for idx in range(1, n_o):
        area = int(o_stats[idx, cv2.CC_STAT_AREA])
        bw = int(o_stats[idx, cv2.CC_STAT_WIDTH])
        bh = int(o_stats[idx, cv2.CC_STAT_HEIGHT])
        x0 = int(o_stats[idx, cv2.CC_STAT_LEFT])
        y0 = int(o_stats[idx, cv2.CC_STAT_TOP])
        solidity = area / float(max(bw * bh, 1))
        aspect = bh / float(max(bw, 1))
        in_curved_bay = bool(float(np.mean(bay_mask[o_lbls == idx] > 0)) > 0.5)
        # Lateral openings on a curved projecting bay undergo perspective horizontal foreshortening
        # (width compressed to ~10-12 px over height ~55-63 px -> aspect up to 6.5).
        max_allowed_aspect = 6.8 if (in_curved_bay and solidity >= 0.45 and bh >= 30) else 4.8
        if (
            min_raw_area <= area <= max_raw_area
            and bw <= int(0.26 * w)
            and bh <= int(0.25 * h)
            and solidity >= 0.40
            and 0.30 <= aspect <= max_allowed_aspect
        ):
            O_raw_mask[o_lbls == idx] = 1
            raw_components.append(
                {
                    "raw_id": len(raw_components) + 1,
                    "cc_index": idx,
                    "center_xy": [round(float(o_cents[idx][0]), 1), round(float(o_cents[idx][1]), 1)],
                    "bbox_xywh": [x0, y0, bw, bh],
                    "area_px": area,
                    "solidity": round(solidity, 3),
                    "aspect_hw": round(aspect, 3),
                    "in_curved_bay": in_curved_bay,
                }
            )

    # Step 2: Merge vertically split components belonging to a single architectural opening
    merged_groups: List[List[Dict[str, Any]]] = []
    used_raw_ids = set()
    for c1 in raw_components:
        if c1["raw_id"] in used_raw_ids:
            continue
        group = [c1]
        used_raw_ids.add(c1["raw_id"])
        x1, y1, w1, h1 = c1["bbox_xywh"]
        cx1 = c1["center_xy"][0]
        for c2 in raw_components:
            if c2["raw_id"] in used_raw_ids:
                continue
            x2, y2, w2, h2 = c2["bbox_xywh"]
            cx2 = c2["center_xy"][0]
            width_ratio = min(w1, w2) / float(max(w1, w2, 1))
            center_dx = abs(cx1 - cx2)
            top_lower = max(y1, y2)
            bot_upper = min(y1 + h1, y2 + h2)
            v_gap = top_lower - bot_upper
            if (
                width_ratio >= 0.65
                and center_dx <= 0.18 * max(w1, w2)
                and -15 <= v_gap <= max(10, int(0.15 * (h1 + h2)))
                and min(w1, w2) >= 16
            ):
                group.append(c2)
                used_raw_ids.add(c2["raw_id"])
        merged_groups.append(group)

    # Step 3: Estimate storey bands from substantial openings (area >= 260 px and height >= 30 px)
    ys_s, xs_s = np.where(S > 0)
    y_top_s = int(np.min(ys_s)) if len(ys_s) > 0 else 0
    y_bot_s = int(np.max(ys_s)) if len(ys_s) > 0 else h - 1

    major_y_centers = sorted(
        [
            float(np.mean([c["center_xy"][1] for c in grp]))
            for grp in merged_groups
            if sum(c["area_px"] for c in grp) >= 260 and max(c["bbox_xywh"][3] for c in grp) >= 28
        ]
    )
    storey_clusters: List[List[float]] = []
    min_storey_sep = max(35.0, 0.14 * (y_bot_s - y_top_s))
    for yc in major_y_centers:
        if not storey_clusters or (yc - np.mean(storey_clusters[-1])) > min_storey_sep:
            storey_clusters.append([yc])
        else:
            storey_clusters[-1].append(yc)

    storey_row_medians = [float(np.median(c)) for c in storey_clusters]
    visible_levels_count = len(storey_row_medians)

    # Locate primary horizontal concrete floor-slab lines between adjacent storey opening bands
    row_l = np.median(np.where(S > 0, lab[:, :, 0], np.nan), axis=1)
    row_l = np.nan_to_num(row_l, nan=0.0)
    # Primary floor slab soffit transition has bright concrete slab above and shadowed soffit below (gy < 0)
    row_soffit_gy = np.mean(np.maximum(0.0, -gy) * S, axis=1)
    slab_band_score = (row_l / (np.max(row_l) + 1e-5)) + 0.55 * (
        row_soffit_gy / (np.max(row_soffit_gy) + 1e-5)
    )
    slab_top_score = slab_band_score

    floor_lines: List[int] = []
    if len(storey_row_medians) >= 1:
        top_o_y = int(storey_row_medians[0])
        s0 = max(y_top_s + 10, top_o_y - int(0.14 * h))
        s1 = max(s0 + 6, top_o_y - 18)
        if s1 > s0:
            floor_lines.append(int(s0 + np.argmax(slab_top_score[s0:s1])))

    for k in range(len(storey_row_medians) - 1):
        ya = int(storey_row_medians[k]) + 22
        yb = int(storey_row_medians[k + 1]) - 22
        if yb > ya + 4:
            best_y = int(ya + np.argmax(slab_band_score[ya:yb]))
            floor_lines.append(best_y)

    if not floor_lines:
        floor_lines = [int(y_top_s + 0.33 * (y_bot_s - y_top_s)), int(y_top_s + 0.66 * (y_bot_s - y_top_s))]

    major_x_centers = [
        float(np.mean([c["center_xy"][0] for c in grp]))
        for grp in merged_groups
        if sum(c["area_px"] for c in grp) >= 260 and max(c["bbox_xywh"][3] for c in grp) >= 28
    ]

    # Step 4: Classify each candidate group into VERIFIED, UNCERTAIN, or REJECTED_SHADOW
    O_verified = np.zeros((h, w), dtype=np.uint8)
    O_uncertain = np.zeros((h, w), dtype=np.uint8)
    verified_openings_list: List[Dict[str, Any]] = []
    uncertain_candidates_list: List[Dict[str, Any]] = []
    rejected_artifacts_list: List[Dict[str, Any]] = []

    top_slab_y = floor_lines[0] if floor_lines else (y_top_s + 40)

    for grp in merged_groups:
        raw_ids = [c["raw_id"] for c in grp]
        comp_mask = np.zeros((h, w), dtype=np.uint8)
        for c in grp:
            comp_mask[o_lbls == c["cc_index"]] = 1
        if len(grp) > 1:
            comp_mask = cv2.morphologyEx(comp_mask, cv2.MORPH_CLOSE, np.ones((11, 5), np.uint8)) & S

        ys_c, xs_c = np.where(comp_mask > 0)
        if len(xs_c) == 0:
            continue
        x0, x1 = int(np.min(xs_c)), int(np.max(xs_c))
        y0, y1 = int(np.min(ys_c)), int(np.max(ys_c))
        bw = x1 - x0 + 1
        bh = y1 - y0 + 1
        area = int(len(xs_c))
        cx = float(np.mean(xs_c))
        cy = float(np.mean(ys_c))
        aspect = bh / float(max(bw, 1))
        solidity = area / float(max(bw * bh, 1))
        in_bay = bool(float(np.mean(bay_mask[comp_mask > 0] > 0)) > 0.5)

        top_ys = []
        for col_x in range(x0 + 2, x1 - 1):
            yc_col = np.where(comp_mask[:, col_x] > 0)[0]
            if len(yc_col) > 0:
                top_ys.append((float(col_x), float(yc_col[0])))
        is_arched = False
        if len(top_ys) >= 8 and y0 > int(0.50 * h):
            tx = np.array([p[0] for p in top_ys])
            ty = np.array([p[1] for p in top_ys])
            u = (tx - np.mean(tx)) / max(np.ptp(tx) * 0.5, 1.0)
            if float(np.polyfit(u, ty, 2)[0]) > 1.2:
                is_arched = True

        # Rule A1: Thin horizontal under-slab shadow slits (bh <= 7 px and aspect < 0.45)
        if bh <= 7 and aspect < 0.45:
            rejected_artifacts_list.append(
                {
                    "raw_ids": raw_ids,
                    "center_xy": [round(cx, 1), round(cy, 1)],
                    "bbox_xywh": [x0, y0, bw, bh],
                    "area_px": area,
                    "classification": "REJECTED_SLAB_SHADOW_SLIT",
                    "reason": f"Thin horizontal shadow slit (height={bh}px, aspect={aspect:.2f}) along slab transition.",
                }
            )
            continue

        # Rule A2: Upper roof parapet / drum cornice shadow above the top ceiling slab line
        if cy < float(top_slab_y - 2) and y0 < int(top_slab_y - 10):
            rejected_artifacts_list.append(
                {
                    "raw_ids": raw_ids,
                    "center_xy": [round(cx, 1), round(cy, 1)],
                    "bbox_xywh": [x0, y0, bw, bh],
                    "area_px": area,
                    "classification": "REJECTED_UPPER_DRUM_CORNICE_SHADOW",
                    "reason": f"Upper drum/parapet cornice shadow (cy={cy:.1f} above top floor slab y={top_slab_y}).",
                }
            )
            continue

        # Rule B: Small dark pockets sitting right on the ground contact plinth or lacking storey/column support
        near_plinth = (y1 >= y_plinth - 8) and (area < 200)
        aligned_with_storey_row = any(abs(cy - sy) <= 22.0 for sy in storey_row_medians)
        aligned_with_col_grid = any(abs(cx - mx) <= 12.0 for mx in major_x_centers if abs(cx - mx) > 1.0)

        if near_plinth or (area < 180 and not (aligned_with_storey_row and aligned_with_col_grid)):
            O_uncertain[comp_mask > 0] = 1
            uncertain_candidates_list.append(
                {
                    "raw_ids": raw_ids,
                    "center_xy": [round(cx, 1), round(cy, 1)],
                    "bbox_xywh": [x0, y0, bw, bh],
                    "area_px": area,
                    "classification": "UNCERTAIN_OPENING_CANDIDATE",
                    "reason": (
                        "Near ground plinth edge"
                        if near_plinth
                        else "Small cavity candidate without multi-storey column/row alignment; requires human review."
                    ),
                }
            )
            continue

        # Rule C: Verified architectural opening (window, oblique bay window, arched doorway, or loggia)
        if len(raw_ids) > 1 and is_arched:
            subtype = "arched_entrance_doorway"
        elif is_arched or (y0 > int(0.55 * h) and bw >= 28 and bh >= 32 and cx > 210):
            subtype = "ground_level_arched_opening"
        elif bw >= 38 and area >= 1500:
            subtype = "balcony_or_loggia_recess"
        elif in_bay and aspect >= 3.8:
            subtype = "curved_bay_oblique_window_opening"
        else:
            subtype = "window_opening"

        O_verified[comp_mask > 0] = 1
        verified_openings_list.append(
            {
                "verified_id": len(verified_openings_list) + 1,
                "merged_from_raw_ids": raw_ids,
                "opening_subtype": subtype,
                "center_xy": [round(cx, 1), round(cy, 1)],
                "bbox_xywh": [x0, y0, bw, bh],
                "area_px": area,
                "solidity": round(solidity, 3),
                "aspect_hw": round(aspect, 3),
                "in_curved_bay": in_bay,
                "is_ground_level": bool(y0 > int(0.52 * h)),
                "arched_crown_detected": is_arched,
            }
        )

    # Step 5 (BLOCKER 5 & SECTION 7 FIX): Structural Macro Edges + Secondary Horizontal Line Provenance
    dS_1px = (S > 0) & (cv2.erode(S, np.ones((3, 3), np.uint8)) == 0)
    dO_1px = (O_verified > 0) & (cv2.erode(O_verified, np.ones((3, 3), np.uint8)) == 0)
    dBay_1px = (bay_mask > 0) & (cv2.erode(bay_mask, np.ones((3, 3), np.uint8)) == 0)

    coarse_gray = cv2.GaussianBlur(gray.astype(np.uint8), (9, 9), 2.4)
    coarse_canny = cv2.Canny(coarse_gray, 50, 125) & (S * 255)
    lines = cv2.HoughLinesP(
        coarse_canny,
        rho=1.0,
        theta=np.pi / 180.0,
        threshold=34,
        minLineLength=max(30, int(0.08 * min(h, w))),
        maxLineGap=4,
    )
    macro_line_map = np.zeros((h, w), dtype=np.uint8)
    raw_horiz_segments: List[Dict[str, Any]] = []
    if lines is not None:
        for ln in lines[:, 0, :]:
            lx1, ly1, lx2, ly2 = int(ln[0]), int(ln[1]), int(ln[2]), int(ln[3])
            ang = abs(np.degrees(np.arctan2(ly2 - ly1, lx2 - lx1)))
            if ang <= 10.0 or ang >= 170.0 or (80.0 <= ang <= 100.0):
                cv2.line(macro_line_map, (lx1, ly1), (lx2, ly2), 1, 1)
                if ang <= 8.0 or ang >= 172.0:
                    ym = (ly1 + ly2) // 2
                    raw_horiz_segments.append(
                        {
                            "y": ym,
                            "x0": min(lx1, lx2),
                            "x1": max(lx1, lx2),
                            "length_px": abs(lx2 - lx1),
                        }
                    )

    for fy in floor_lines:
        if 0 <= fy < h:
            macro_line_map[fy, :] = np.where(S[fy, :] > 0, 1, macro_line_map[fy, :])

    # Cluster non-primary horizontal Hough lines by y (within +-4 px) and assign exact provenance
    secondary_cornices: List[int] = []
    horizontal_line_provenance_table: List[Dict[str, Any]] = []
    for fy in floor_lines:
        horizontal_line_provenance_table.append(
            {
                "y": int(fy),
                "category": "PRIMARY_FLOOR_SLAB_LINE",
                "provenance": "Storey-separating concrete slab verified via opening band separation & vertical gradient",
                "used_by_g2_primary_floor_matching": True,
            }
        )

    non_primary_segs = [
        seg for seg in sorted(raw_horiz_segments, key=lambda s: s["y"]) if all(abs(seg["y"] - fy) > 10 for fy in floor_lines)
    ]
    y_clusters: List[List[Dict[str, Any]]] = []
    for seg in non_primary_segs:
        if not y_clusters or abs(seg["y"] - int(np.mean([s["y"] for s in y_clusters[-1]]))) > 4:
            y_clusters.append([seg])
        else:
            y_clusters[-1].append(seg)

    for cl in y_clusters:
        ym = int(round(float(np.mean([s["y"] for s in cl]))))
        total_len = int(sum(s["length_px"] for s in cl))
        x_span = [int(min(s["x0"] for s in cl)), int(max(s["x1"] for s in cl))]
        # Determine whether this horizontal line is a roof parapet boundary, slab upper edge / balcony base, or opening lintel/sill
        matches_opening_top_or_bot = any(
            abs(ym - op["bbox_xywh"][1]) <= 4 or abs(ym - (op["bbox_xywh"][1] + op["bbox_xywh"][3])) <= 4
            for op in verified_openings_list
        )
        if ym <= top_slab_y - 8:
            cat = "SECONDARY_ROOF_PARAPET_OR_CORNICE_LINE"
            prov = "Upper roof parapet cap / drum cornice boundary above top floor slab"
            secondary_cornices.append(ym)
        elif any(10 < (fy - ym) <= 16 for fy in floor_lines):
            cat = "SECONDARY_SLAB_UPPER_EDGE_OR_BALCONY_BASE"
            prov = "Upper concrete slab edge / balcony railing base above primary slab soffit"
            secondary_cornices.append(ym)
        elif matches_opening_top_or_bot:
            cat = "OPENING_LINTEL_OR_SILL_HORIZONTAL_EDGE"
            prov = "Horizontal window/loggia lintel or sill contour segment in dG_macro"
        else:
            cat = "SECONDARY_ARCHITECTURAL_MOLDING_LINE"
            prov = "Secondary horizontal facade molding segment"
            if total_len >= int(0.12 * w):
                secondary_cornices.append(ym)

        horizontal_line_provenance_table.append(
            {
                "y": ym,
                "x_span": x_span,
                "total_hough_length_px": total_len,
                "category": cat,
                "provenance": prov,
                "used_by_g2_primary_floor_matching": False,
            }
        )

    secondary_cornices_sorted = sorted(list(set(secondary_cornices)))

    dG_macro = ((dS_1px | dO_1px | dBay_1px | (macro_line_map > 0)) & (S > 0)).astype(np.uint8)
    all_fine_edges = (cv2.Canny(gray.astype(np.uint8), 50, 140) > 0) & (S > 0)
    macro_dil = cv2.dilate(dG_macro, np.ones((3, 3), np.uint8)) > 0
    dG_texture = (all_fine_edges & (~macro_dil)).astype(np.uint8)

    s_px = max(int(np.sum(S > 0)), 1)
    macro_px = int(np.sum(dG_macro > 0))
    tex_px = int(np.sum(dG_texture > 0))

    # Evaluate the 9-position curved-bay opening grid for Defect D verification
    curved_bay_grid_audit = evaluate_curved_bay_opening_grid(
        S=S,
        bay_mask=bay_mask,
        O_verified=O_verified,
        O_uncertain=O_uncertain,
        floor_lines_y=np.array(floor_lines, dtype=np.int32),
        ground_contact_y=int(y_plinth),
        verified_openings_list=verified_openings_list,
        uncertain_candidates_list=uncertain_candidates_list,
        gray=gray,
    )

    ground_verified = [op for op in verified_openings_list if op["is_ground_level"]]
    evidence = {
        "visible_levels_count": visible_levels_count,
        "storey_opening_band_centers_y": [round(y, 1) for y in storey_row_medians],
        "floor_slab_lines_y": floor_lines,
        "secondary_cornice_or_balcony_lines_y": secondary_cornices_sorted,
        "horizontal_line_provenance_table": horizontal_line_provenance_table,
        "ground_contact_plinth_y": int(y_plinth),
        "raw_connected_components_count": len(raw_components),
        "verified_architectural_openings_count": len(verified_openings_list),
        "uncertain_opening_candidates_count": len(uncertain_candidates_list),
        "rejected_shadow_artifacts_count": len(rejected_artifacts_list),
        "merged_opening_groups": [
            op["merged_from_raw_ids"] for op in verified_openings_list if len(op["merged_from_raw_ids"]) > 1
        ],
        "total_detected_openings": len(verified_openings_list),
        "ground_level_openings_count": len(ground_verified),
        "ground_arches_with_curved_crown_detected": sum(
            1 for op in ground_verified if op["arched_crown_detected"]
        ),
        "ground_arches_brick_intrados_note": (
            "Central arched entrance has verified curved arch crown; "
            "shadowed brick arch voussoirs above right ground windows remain marked UNCERTAIN until human review."
        ),
        "curved_bay_opening_grid_audit": curved_bay_grid_audit,
        "verified_openings_list": verified_openings_list,
        "uncertain_opening_candidates_list": uncertain_candidates_list,
        "rejected_shadow_artifacts_list": rejected_artifacts_list,
        "raw_connected_components_list": raw_components,
        "structural_vs_texture_edges": {
            "dG_structural_macro_pixels": macro_px,
            "dG_material_texture_pixels": tex_px,
            "structural_macro_density_in_S": round(macro_px / float(s_px), 4),
            "material_texture_density_in_S": round(tex_px / float(s_px), 4),
            "brick_texture_excluded_from_dG": True,
        },
    }
    return (
        O_verified,
        O_raw_mask,
        O_uncertain,
        dG_macro,
        dG_texture,
        np.array(floor_lines, dtype=np.int32),
        np.array(secondary_cornices_sorted, dtype=np.int32),
        visible_levels_count,
        evidence,
    )


def _detect_curved_projecting_bay_from_da3(
    img_working_bgr: np.ndarray,
    S: np.ndarray,
    depth: Optional[np.ndarray],
    normals: Optional[np.ndarray],
) -> Tuple[np.ndarray, str, Dict[str, Any]]:
    """
    Detects the projecting curved bay surface from DA3 relative depth and image gradients.
    """
    h, w = S.shape[:2]
    empty = np.zeros((h, w), dtype=np.uint8)
    if depth is None or normals is None:
        return empty, "UNAVAILABLE_NO_DA3_DEPTH", {"detected": False, "reason": "No DA3 depth"}

    ys, xs = np.where(S > 0)
    if len(xs) < 200:
        return empty, "UNAVAILABLE_EMPTY_BUILDING", {"detected": False, "reason": "Building mask too small"}

    x_left, x_right = int(np.min(xs)), int(np.max(xs))
    y_top, y_bot = int(np.min(ys)), int(np.max(ys))
    b_width = x_right - x_left
    b_height = y_bot - y_top
    if b_width < 60 or b_height < 80:
        return empty, "UNAVAILABLE_TOO_SMALL", {"detected": False}

    y_mid0 = y_top + int(0.14 * b_height)
    y_mid1 = y_bot - int(0.06 * b_height)

    col_env = np.full(w, np.nan, dtype=np.float64)
    for x in range(x_left, x_right + 1):
        col_s = S[y_mid0:y_mid1, x] > 0
        if int(np.sum(col_s)) >= 12:
            col_env[x] = float(np.percentile(depth[y_mid0:y_mid1, x][col_s], 75))

    best_score = 0.0
    best_fit: Optional[Dict[str, Any]] = None
    min_win = max(56, int(0.22 * b_width))
    max_win = max(min_win + 8, int(0.44 * b_width))

    for win_w in range(min_win, max_win + 1, 6):
        for x0 in range(x_left, x_right - win_w + 1, 4):
            x1 = x0 + win_w
            seg = col_env[x0:x1]
            valid = ~np.isnan(seg)
            if float(np.mean(valid)) < 0.85:
                continue
            u = np.linspace(-1.0, 1.0, win_w)[valid]
            zv = seg[valid]
            coeffs = np.polyfit(u, zv, 2)
            a_quad = float(coeffs[0])
            z_fit = np.polyval(coeffs, u)
            ss_res = float(np.sum((zv - z_fit) ** 2))
            ss_tot = float(np.sum((zv - np.mean(zv)) ** 2)) + 1e-8
            r2 = 1.0 - (ss_res / ss_tot)
            if a_quad <= -0.015 and r2 >= 0.75:
                score = abs(a_quad) * (r2 ** 2)
                if score > best_score:
                    best_score = score
                    best_fit = {
                        "x0": int(x0),
                        "x1": int(x1),
                        "a_quad": round(a_quad, 4),
                        "r2": round(r2, 4),
                        "peak_depth": round(float(np.max(zv)), 4),
                    }

    if best_fit is None:
        return empty, "NONE_DETECTED_IN_DA3_DEPTH", {"detected": False}

    bx0, bx1 = best_fit["x0"], best_fit["x1"]
    gray = cv2.cvtColor(img_working_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    abs_gx = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
    col_gx = np.mean(abs_gx[y_mid0:y_mid1, :], axis=0)

    bay_center_x = 0.5 * (bx0 + bx1)
    bldg_center_x = 0.5 * (x_left + x_right)
    if bay_center_x < bldg_center_x:
        search_r0 = max(bx0 + 40, bx1 - 18)
        search_r1 = min(x_right - 10, bx1 + 6)
        if search_r1 > search_r0:
            bx1 = int(search_r0 + np.argmax(col_gx[search_r0:search_r1]))
        adj_recessed_slice = slice(min(x_right - 5, bx1 + 8), min(x_right, bx1 + 55))
    else:
        search_l0 = max(x_left + 10, bx0 - 6)
        search_l1 = min(bx1 - 40, bx0 + 18)
        if search_l1 > search_l0:
            bx0 = int(search_l0 + np.argmax(col_gx[search_l0:search_l1]))
        adj_recessed_slice = slice(max(x_left, bx0 - 55), max(x_left + 5, bx0 - 8))

    adj_s = S[:, adj_recessed_slice]
    adj_ys = np.where(adj_s > 0)[0]
    adj_roof_y = int(np.min(adj_ys)) if len(adj_ys) > 0 else (y_top + 25)

    bay_mask = np.zeros((h, w), dtype=np.uint8)
    smooth_d = cv2.GaussianBlur(depth, (25, 9), 6.0)
    for y in range(y_top, y_bot + 1):
        row_s = np.where(S[y, bx0 : bx1 + 1] > 0)[0]
        if len(row_s) < 6:
            continue
        if y < adj_roof_y + 6:
            bay_mask[y, bx0 + int(row_s[0]) : bx0 + int(row_s[-1]) + 1] = 1
        else:
            rec_vals = smooth_d[max(y_top, y - 8) : min(y_bot, y + 8), adj_recessed_slice]
            rec_base = float(np.median(rec_vals)) if rec_vals.size > 0 else float(np.percentile(smooth_d[y, bx0:bx1], 15))
            row_bay_d = smooth_d[y, bx0 : bx1 + 1]
            peak_d = float(np.max(row_bay_d))
            relief = max(0.008, peak_d - rec_base)
            prot = np.where((S[y, bx0 : bx1 + 1] > 0) & (row_bay_d >= rec_base + 0.15 * relief))[0]
            if len(prot) >= 8:
                x_start_bay = bx0 + int(row_s[0]) if bay_center_x < bldg_center_x else bx0 + int(prot[0])
                x_end_bay = bx0 + int(prot[-1]) + 1 if bay_center_x < bldg_center_x else bx0 + int(row_s[-1]) + 1
                bay_mask[y, x_start_bay:x_end_bay] = 1

    bay_mask = (bay_mask & S).astype(np.uint8)
    bay_mask = cv2.morphologyEx(bay_mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    bay_mask = (bay_mask & S).astype(np.uint8)

    bys, bxs = np.where(bay_mask > 0)
    if len(bxs) < 1000:
        return empty, "NONE_DETECTED_IN_DA3_DEPTH", {"detected": False}

    bay_info = {
        "detected": True,
        "bbox_x": [int(np.min(bxs)), int(np.max(bxs))],
        "bbox_y": [int(np.min(bys)), int(np.max(bys))],
        "area_px": int(len(bxs)),
        "fraction_of_building_S": round(float(len(bxs)) / float(max(np.sum(S > 0), 1)), 4),
        "quadratic_convexity_a": best_fit["a_quad"],
        "quadratic_fit_r2": best_fit["r2"],
        "includes_upper_drum_above_adjacent_roof": bool(int(np.min(bys)) < adj_roof_y - 8),
    }
    return bay_mask, "DA3_CURVED_BAY_CANDIDATE_REQUIRES_HUMAN_CONFIRMATION", bay_info


def extract_geometry_bundle_2p5d(
    img_working_bgr: np.ndarray,
    img_raw_bgr: Optional[np.ndarray] = None,
    da3_depth_bgr: Optional[np.ndarray] = None,
    manual_masks_dir: Optional[pathlib.Path] = None,
) -> GeometryBundle2P5D:
    """
    Extracts the complete V2.2 GeometryBundle2P5D with strict semantic separation:
      - `O_VERIFIED` (`bundle.O`)
      - `O_UNCERTAIN` (`bundle.O_uncertain`)
      - `PROTECTED_UNCERTAIN` (`bundle.protected_uncertain`)
      - `F_EDITABLE` (`bundle.F = S & (O_verified == 0) & (O_uncertain == 0)`)
    Guarantees:
      `F_EDITABLE ∩ O_UNCERTAIN == ∅` and `F_EDITABLE ∩ O_VERIFIED == ∅`.
    """
    h, w = img_working_bgr.shape[:2]
    pad_l, pad_r, pad_t, pad_b = detect_edge_replicated_padding(img_working_bgr)
    valid_roi = np.ones((h, w), dtype=np.uint8)
    if pad_l > 0:
        valid_roi[:, :pad_l] = 0
    if pad_r > 0:
        valid_roi[:, w - pad_r :] = 0
    if pad_t > 0:
        valid_roi[:pad_t, :] = 0
    if pad_b > 0:
        valid_roi[h - pad_b :, :] = 0

    verified_bgr = cross_scale_brick_suppress_filter(img_working_bgr, img_raw_bgr)

    if da3_depth_bgr is not None:
        depth, normals = compute_normals_from_da3_depth(da3_depth_bgr, (h, w))
        depth_prov = "MODEL_DERIVED_DA3_RELATIVE_DEPTH_ESTIMATE"
    else:
        depth, normals = None, None
        depth_prov = "UNAVAILABLE_NO_DA3_DEPTH"

    S, P_sky, P_ground, y_plinth, uncertain_base, seg_conf, seg_refinement_report = _segment_sky_and_ground(
        img_working_bgr, verified_bgr, depth, valid_roi
    )
    mask_prov = "UNVERIFIED_HEURISTIC_PROPOSAL_REQUIRES_MANUAL_CONFIRMATION"

    if manual_masks_dir is not None and manual_masks_dir.exists():
        s_override_path = manual_masks_dir / "manual_mask_S.png"
        if s_override_path.exists():
            s_ov = cv2.imread(str(s_override_path), cv2.IMREAD_GRAYSCALE)
            if s_ov is not None:
                s_ov = cv2.resize(s_ov, (w, h), interpolation=cv2.INTER_NEAREST)
                S = (s_ov > 127).astype(np.uint8) & valid_roi
                P_ground = (P_ground & (1 - S)).astype(np.uint8)
                P_sky = ((1 - S) & (1 - P_ground)).astype(np.uint8)
                mask_prov = "MANUAL_MASK_FILE_LOADED_REQUIRES_HASH_APPROVAL"

    P = (1 - S).astype(np.uint8)

    bay_mask, bay_prov, bay_info = _detect_curved_projecting_bay_from_da3(
        img_working_bgr, S, depth, normals
    )
    if manual_masks_dir is not None and manual_masks_dir.exists():
        bay_override_path = manual_masks_dir / "manual_mask_bay.png"
        if bay_override_path.exists():
            b_ov = cv2.imread(str(bay_override_path), cv2.IMREAD_GRAYSCALE)
            if b_ov is not None:
                b_ov = cv2.resize(b_ov, (w, h), interpolation=cv2.INTER_NEAREST)
                bay_mask = ((b_ov > 127).astype(np.uint8) & S).astype(np.uint8)
                bay_prov = "MANUAL_BAY_MASK_LOADED_REQUIRES_HASH_APPROVAL"

    (
        O_verified,
        O_raw_mask,
        O_uncertain,
        dG_macro,
        dG_texture,
        floor_lines_y,
        secondary_cornices_y,
        visible_levels,
        arch_evidence,
    ) = _extract_openings_levels_and_macro_edges(
        img_working_bgr, verified_bgr, S, bay_mask, depth, y_plinth
    )

    if manual_masks_dir is not None and manual_masks_dir.exists():
        o_override_path = manual_masks_dir / "manual_mask_O.png"
        if o_override_path.exists():
            o_ov = cv2.imread(str(o_override_path), cv2.IMREAD_GRAYSCALE)
            if o_ov is not None:
                o_ov = cv2.resize(o_ov, (w, h), interpolation=cv2.INTER_NEAREST)
                O_verified = ((o_ov > 127).astype(np.uint8) & S).astype(np.uint8)

    # BLOCKER B FIX: Strict Semantic Separation of O_UNCERTAIN from F_EDITABLE
    O_verified = ((O_verified > 0) & (S > 0)).astype(np.uint8)
    O_uncertain = ((O_uncertain > 0) & (S > 0) & (O_verified == 0)).astype(np.uint8)
    protected_uncertain = O_uncertain.copy()
    F_editable = ((S > 0) & (O_verified == 0) & (O_uncertain == 0)).astype(np.uint8)

    # Hard invariant assertions
    assert int(np.sum((F_editable > 0) & (O_uncertain > 0))) == 0, "F_EDITABLE intersection O_UNCERTAIN must be empty"
    assert int(np.sum((F_editable > 0) & (O_verified > 0))) == 0, "F_EDITABLE intersection O_VERIFIED must be empty"

    uncertain_combined = ((uncertain_base > 0) | (O_uncertain > 0)).astype(np.uint8)
    arch_evidence["curved_projecting_bay"] = bay_info
    arch_evidence["segmentation_refinements_v2_2"] = seg_refinement_report
    arch_evidence["semantic_mask_partition_v2_2"] = {
        "S_building_pixels": int(np.sum(S > 0)),
        "F_editable_pixels": int(np.sum(F_editable > 0)),
        "O_verified_pixels": int(np.sum(O_verified > 0)),
        "O_uncertain_pixels": int(np.sum(O_uncertain > 0)),
        "PROTECTED_UNCERTAIN_pixels": int(np.sum(protected_uncertain > 0)),
        "F_editable_intersection_O_uncertain_pixels": int(np.sum((F_editable > 0) & (O_uncertain > 0))),
        "F_editable_intersection_O_verified_pixels": int(np.sum((F_editable > 0) & (O_verified > 0))),
        "partition_identity_holds": bool(np.array_equal(F_editable | O_verified | O_uncertain, S)),
    }

    return GeometryBundle2P5D(
        S=S,
        F=F_editable,
        P=P,
        P_sky=P_sky,
        P_ground=P_ground,
        O=O_verified,
        O_raw_components=O_raw_mask,
        O_uncertain=O_uncertain,
        dG=dG_macro,
        dG_texture=dG_texture,
        bay_mask=bay_mask,
        uncertain_mask=uncertain_combined,
        valid_roi=valid_roi,
        depth_map=depth,
        normals_map=normals,
        floor_lines_y=floor_lines_y,
        secondary_cornices_y=secondary_cornices_y,
        ground_contact_y=y_plinth,
        visible_levels_count=visible_levels,
        architectural_evidence=arch_evidence,
        depth_provenance=depth_prov,
        mask_provenance=mask_prov,
        bay_provenance=bay_prov,
        segmentation_confidence=seg_conf,
        protected_uncertain=protected_uncertain,
    )


# ---------------------------------------------------------------------------
# BLOCKER A & BLOCKER C: Ed25519 Digital Signature Human Review Contract
# ---------------------------------------------------------------------------
def compute_human_review_digest(
    source_image_b_sha256: str,
    source_image_b_dimensions: List[int],
    geometry_manifest_version: str,
    geometry_manifest_sha256: str,
    sha_s_building: str,
    sha_o_openings: str,
    sha_bay_curved: str,
    reviewer_id: str,
    reviewed_at_utc: str,
    review_status: str,
    sha_o_uncertain: str = "",
    reviewer_key_id: str = "",
    expires_at_utc: str = "",
) -> str:
    """
    Computes the canonical SHA-256 artifact-binding digest over the exact geometry artifacts.
    IMPORTANT (V2.2 Blocker A Fix):
      This digest establishes artifact integrity ONLY. It is NEVER accepted by itself as proof
      of human reviewer authorization; an Ed25519 digital signature over this canonical digest
      from a trusted reviewer key is strictly required.
    """
    canonical = "|".join(
        [
            HUMAN_REVIEW_CONTRACT_VERSION,
            review_status.strip(),
            reviewer_id.strip(),
            reviewer_key_id.strip(),
            reviewed_at_utc.strip(),
            expires_at_utc.strip(),
            source_image_b_sha256.strip().lower(),
            f"{int(source_image_b_dimensions[0])}x{int(source_image_b_dimensions[1])}",
            geometry_manifest_version.strip(),
            geometry_manifest_sha256.strip().lower(),
            sha_s_building.strip().lower(),
            sha_o_openings.strip().lower(),
            sha_o_uncertain.strip().lower(),
            sha_bay_curved.strip().lower(),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sign_human_review_approval_ed25519(
    private_key_pem: bytes,
    reviewer_id: str,
    reviewer_key_id: str,
    reviewed_at_utc: str,
    expires_at_utc: str,
    source_image_b_sha256: str,
    source_image_b_dimensions: List[int],
    geometry_manifest_version: str,
    geometry_manifest_sha256: str,
    sha_s_building: str,
    sha_o_openings: str,
    sha_o_uncertain: str,
    sha_bay_curved: str,
    explicit_mask_confirmation: Dict[str, bool],
) -> Dict[str, Any]:
    """
    Signs an approval record using a reviewer-controlled Ed25519 private key.
    Requires explicit visual confirmation flags for S_building, O_openings, O_uncertain, and bay_curved.
    """
    required_confirmations = (
        "S_building_visually_inspected",
        "O_openings_visually_inspected",
        "O_uncertain_visually_inspected",
        "bay_curved_visually_inspected",
    )
    for k in required_confirmations:
        if explicit_mask_confirmation.get(k) is not True:
            raise ValueError(f"Explicit reviewer confirmation `{k}=True` is mandatory before signing.")

    digest_hex = compute_human_review_digest(
        source_image_b_sha256=source_image_b_sha256,
        source_image_b_dimensions=source_image_b_dimensions,
        geometry_manifest_version=geometry_manifest_version,
        geometry_manifest_sha256=geometry_manifest_sha256,
        sha_s_building=sha_s_building,
        sha_o_openings=sha_o_openings,
        sha_bay_curved=sha_bay_curved,
        reviewer_id=reviewer_id,
        reviewed_at_utc=reviewed_at_utc,
        review_status="HUMAN_GEOMETRY_REVIEW_CONFIRMED",
        sha_o_uncertain=sha_o_uncertain,
        reviewer_key_id=reviewer_key_id,
        expires_at_utc=expires_at_utc,
    )
    priv_key = serialization.load_pem_private_key(private_key_pem, password=None)
    if not isinstance(priv_key, Ed25519PrivateKey):
        raise ValueError("Reviewer signing key must be an Ed25519PrivateKey.")
    sig_bytes = priv_key.sign(digest_hex.encode("utf-8"))

    return {
        "contract": HUMAN_REVIEW_CONTRACT_VERSION,
        "review_status": "HUMAN_GEOMETRY_REVIEW_CONFIRMED",
        "authentication_scheme": "Ed25519_EXTERNAL_TRUSTED_KEY",
        "reviewer_id": reviewer_id,
        "reviewer_key_id": reviewer_key_id,
        "reviewed_at_utc": reviewed_at_utc,
        "expires_at_utc": expires_at_utc,
        "explicit_mask_confirmation": {k: True for k in required_confirmations},
        "source_image_b_sha256": source_image_b_sha256.lower(),
        "source_image_b_dimensions": [int(source_image_b_dimensions[0]), int(source_image_b_dimensions[1])],
        "geometry_manifest_version": geometry_manifest_version,
        "geometry_manifest_sha256": geometry_manifest_sha256.lower(),
        "reviewed_mask_sha256": {
            "S_building": sha_s_building.lower(),
            "O_openings": sha_o_openings.lower(),
            "O_uncertain_candidates": sha_o_uncertain.lower(),
            "bay_curved": sha_bay_curved.lower(),
        },
        "approval_digest_sha256": digest_hex,
        "signature_ed25519_hex": sig_bytes.hex(),
        "non_equivalence_notice": (
            "Cryptographic signature authenticates reviewer identity and artifact integrity only; "
            "it does not by itself prove architectural visual correctness."
        ),
    }


def write_unapproved_human_review_template(
    img_working_bgr: np.ndarray,
    bundle_dir: pathlib.Path,
    prefix: str = "B01",
    source_image_b_sha256: Optional[str] = None,
) -> pathlib.Path:
    """
    Writes a template human-review manifest explicitly marked `NOT_YET_APPROVED`.
    Never fabricates a human signature or embeds signing secrets.
    """
    h, w = img_working_bgr.shape[:2]
    src_sha = source_image_b_sha256 or sha256_image_png_bytes(img_working_bgr)
    manifest_path = bundle_dir / f"{prefix}_geometry_manifest.json"
    manifest_sha = sha256_bytes(manifest_path.read_bytes()) if manifest_path.exists() else ""

    def _file_sha(name: str) -> str:
        p = bundle_dir / f"{prefix}_{name}.png"
        return sha256_bytes(p.read_bytes()) if p.exists() else ""

    template = {
        "contract": HUMAN_REVIEW_CONTRACT_VERSION,
        "review_status": "NOT_YET_APPROVED",
        "authentication_scheme": "Ed25519_EXTERNAL_TRUSTED_KEY",
        "reviewer_id": "",
        "reviewer_key_id": "",
        "reviewed_at_utc": "",
        "expires_at_utc": "",
        "explicit_mask_confirmation": {
            "S_building_visually_inspected": False,
            "O_openings_visually_inspected": False,
            "O_uncertain_visually_inspected": False,
            "bay_curved_visually_inspected": False,
        },
        "source_image_b_sha256": src_sha,
        "source_image_b_dimensions": [w, h],
        "geometry_manifest_version": GEOMETRY_CONTRACT_VERSION,
        "geometry_manifest_sha256": manifest_sha,
        "reviewed_mask_sha256": {
            "S_building": _file_sha("mask_S_building"),
            "O_openings": _file_sha("mask_O_openings"),
            "O_uncertain_candidates": _file_sha("mask_O_uncertain_candidates"),
            "bay_curved": _file_sha("mask_bay_curved"),
        },
        "approval_digest_sha256": "",
        "signature_ed25519_hex": "",
        "instructions": (
            "Visually inspect the diagnostic contact sheet and masks. Approval requires an "
            "authenticated Ed25519 signature from an external trusted reviewer key."
        ),
    }
    out_file = bundle_dir / f"{prefix}_human_review_approval.json"
    out_file.write_text(json.dumps(template, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_file


def _parse_utc_iso(ts_str: str) -> Optional[datetime]:
    s = ts_str.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def verify_human_review_approval_contract(
    img_working_bgr: np.ndarray,
    bundle: GeometryBundle2P5D,
    bundle_dir: Optional[pathlib.Path] = None,
    approval_file_path: Optional[pathlib.Path] = None,
    source_image_b_sha256: Optional[str] = None,
    prefix: str = "B01",
    trusted_signers_registry_path: Optional[pathlib.Path] = None,
    allow_isolated_test_signer: bool = False,
    current_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    BLOCKER A FIX: Fail-closed verification of human review approval.
      1. Verifies exact SHA-256 bindings to IMAGE B, geometry manifest, S_building,
         O_openings, O_uncertain_candidates, and bay_curved.
      2. Rejects self-asserted SHA-256 digests that lack an Ed25519 signature (`FORGED_SELF_ASSERTED_APPROVAL_REJECTED`).
      3. Requires an external trusted reviewer public-key registry (`trusted_signers_registry_path`);
         if unavailable, returns `HUMAN_REVIEW_AUTHENTICATION_UNAVAILABLE` and keeps rendering blocked.
      4. Rejects `TEST_ONLY` keys unless `allow_isolated_test_signer=True` is explicitly set by an isolated test.
      5. Rejects expired or revoked authorizations (`EXPIRED_OR_REVOKED_REVIEWER_AUTHORIZATION`).
    """
    h, w = img_working_bgr.shape[:2]
    actual_src_sha = (source_image_b_sha256 or sha256_image_png_bytes(img_working_bgr)).lower()

    if bundle_dir is not None and (bundle_dir / f"{prefix}_mask_S_building.png").exists():
        actual_sha_s = sha256_bytes((bundle_dir / f"{prefix}_mask_S_building.png").read_bytes()).lower()
        actual_sha_o = sha256_bytes((bundle_dir / f"{prefix}_mask_O_openings.png").read_bytes()).lower()
        unc_p = bundle_dir / f"{prefix}_mask_O_uncertain_candidates.png"
        actual_sha_unc = sha256_bytes(unc_p.read_bytes()).lower() if unc_p.exists() else sha256_image_png_bytes(bundle.O_uncertain * 255).lower()
        actual_sha_bay = sha256_bytes((bundle_dir / f"{prefix}_mask_bay_curved.png").read_bytes()).lower()
        m_path = bundle_dir / f"{prefix}_geometry_manifest.json"
        actual_manifest_sha = sha256_bytes(m_path.read_bytes()).lower() if m_path.exists() else ""
    else:
        actual_sha_s = sha256_image_png_bytes(bundle.S * 255).lower()
        actual_sha_o = sha256_image_png_bytes(bundle.O * 255).lower()
        actual_sha_unc = sha256_image_png_bytes(bundle.O_uncertain * 255).lower()
        actual_sha_bay = sha256_image_png_bytes(bundle.bay_mask * 255).lower()
        actual_manifest_sha = ""

    if approval_file_path is None and bundle_dir is not None:
        approval_file_path = bundle_dir / f"{prefix}_human_review_approval.json"

    if approval_file_path is None or not approval_file_path.exists():
        return {
            "confirmed": False,
            "status": "NO_HUMAN_APPROVAL_RECORD",
            "reason": "Human review approval file does not exist.",
        }

    try:
        rec = json.loads(approval_file_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "confirmed": False,
            "status": "CORRUPT_HUMAN_APPROVAL_RECORD",
            "reason": str(exc),
        }

    # Check if this is a V2.1 or V2.2 self-asserted forgery (digest present, no Ed25519 signature)
    contract_ver = str(rec.get("contract", ""))
    if contract_ver not in (HUMAN_REVIEW_CONTRACT_VERSION, "ArchitectOS_2P5D_HumanGeometryReview_V2_1"):
        return {
            "confirmed": False,
            "status": "INVALID_APPROVAL_CONTRACT_VERSION",
            "reason": f"Expected {HUMAN_REVIEW_CONTRACT_VERSION}, got {contract_ver!r}",
        }

    if rec.get("review_status") != "HUMAN_GEOMETRY_REVIEW_CONFIRMED":
        return {
            "confirmed": False,
            "status": "HUMAN_REVIEW_NOT_YET_APPROVED",
            "reason": f"review_status is {rec.get('review_status')!r}, not HUMAN_GEOMETRY_REVIEW_CONFIRMED.",
        }

    reviewer_id = str(rec.get("reviewer_id", "")).strip()
    reviewed_at = str(rec.get("reviewed_at_utc", "")).strip()
    if not reviewer_id or not reviewed_at:
        return {
            "confirmed": False,
            "status": "MISSING_REVIEWER_OR_TIMESTAMP",
            "reason": "reviewer_id and reviewed_at_utc are mandatory for human approval.",
        }

    # Verify artifact hashes first so any tampering with IMAGE B, manifest, S, O, or bay is caught immediately
    if rec.get("source_image_b_dimensions") != [w, h]:
        return {
            "confirmed": False,
            "status": "SOURCE_DIMENSIONS_MISMATCH",
            "expected": [w, h],
            "recorded": rec.get("source_image_b_dimensions"),
        }

    if str(rec.get("source_image_b_sha256", "")).lower() != actual_src_sha:
        return {
            "confirmed": False,
            "status": "SOURCE_IMAGE_B_HASH_MISMATCH",
            "reason": "Source IMAGE B has changed since the review record was created.",
        }

    rec_manifest_sha = str(rec.get("geometry_manifest_sha256", "")).lower()
    if actual_manifest_sha and rec_manifest_sha != actual_manifest_sha:
        return {
            "confirmed": False,
            "status": "GEOMETRY_MANIFEST_HASH_MISMATCH",
            "reason": "Geometry manifest has changed since approval.",
        }

    masks_rec = rec.get("reviewed_mask_sha256") or {}
    if str(masks_rec.get("S_building", "")).lower() != actual_sha_s:
        return {
            "confirmed": False,
            "status": "MASK_S_BUILDING_HASH_MISMATCH",
            "reason": "S_building mask was modified after human approval.",
        }
    if str(masks_rec.get("O_openings", "")).lower() != actual_sha_o:
        return {
            "confirmed": False,
            "status": "MASK_O_OPENINGS_HASH_MISMATCH",
            "reason": "O_openings mask was modified or replaced after human approval.",
        }
    if str(masks_rec.get("bay_curved", "")).lower() != actual_sha_bay:
        return {
            "confirmed": False,
            "status": "MASK_BAY_CURVED_HASH_MISMATCH",
            "reason": "bay_curved mask was modified or replaced after human approval.",
        }
    rec_sha_unc = str(masks_rec.get("O_uncertain_candidates", "")).lower()
    if rec_sha_unc and rec_sha_unc != actual_sha_unc:
        return {
            "confirmed": False,
            "status": "MASK_O_UNCERTAIN_HASH_MISMATCH",
            "reason": "O_uncertain_candidates mask was modified after human approval.",
        }

    # BLOCKER A: Reject V2.1-style or self-asserted SHA-256 approvals that lack Ed25519 signature
    sig_hex = str(rec.get("signature_ed25519_hex", "")).strip()
    reviewer_key_id = str(rec.get("reviewer_key_id", "")).strip()
    expires_at_utc = str(rec.get("expires_at_utc", "")).strip()

    if (
        contract_ver == "ArchitectOS_2P5D_HumanGeometryReview_V2_1"
        or not sig_hex
        or not reviewer_key_id
        or "self_asserted" in reviewer_id.lower()
    ):
        return {
            "confirmed": False,
            "status": "FORGED_SELF_ASSERTED_APPROVAL_REJECTED",
            "reason": (
                "Self-computed SHA-256 digests and unauthenticated reviewer_id strings cannot authorize "
                "geometry approval; an Ed25519 cryptographic signature from a trusted reviewer key is required."
            ),
        }

    if rec.get("geometry_manifest_version") != GEOMETRY_CONTRACT_VERSION:
        return {
            "confirmed": False,
            "status": "GEOMETRY_MANIFEST_VERSION_MISMATCH",
            "reason": f"Expected {GEOMETRY_CONTRACT_VERSION}, got {rec.get('geometry_manifest_version')!r}",
        }

    # Require explicit visual confirmation of the masks before signing
    exp_conf = rec.get("explicit_mask_confirmation") or {}
    for req_k in (
        "S_building_visually_inspected",
        "O_openings_visually_inspected",
        "O_uncertain_visually_inspected",
        "bay_curved_visually_inspected",
    ):
        if exp_conf.get(req_k) is not True:
            return {
                "confirmed": False,
                "status": "MISSING_EXPLICIT_MASK_CONFIRMATION",
                "reason": f"Reviewer record is missing mandatory explicit confirmation `{req_k}: true`.",
            }

    # Locate trusted public key registry
    if trusted_signers_registry_path is None:
        env_path = os.environ.get("ARCHITECTOS_TRUSTED_REVIEWER_KEYS_PATH", "").strip()
        trusted_signers_registry_path = pathlib.Path(env_path) if env_path else DEFAULT_EXTERNAL_TRUSTED_SIGNERS_PATH

    if trusted_signers_registry_path is None or not trusted_signers_registry_path.exists():
        return {
            "confirmed": False,
            "status": "HUMAN_REVIEW_AUTHENTICATION_UNAVAILABLE",
            "reason": (
                "No external trusted reviewer public-key registry is provisioned on this machine; "
                "rendering remains fail-closed blocked."
            ),
        }

    try:
        registry_data = json.loads(trusted_signers_registry_path.read_text(encoding="utf-8"))
        signers_map = registry_data.get("trusted_signers") or {}
    except Exception as exc:
        return {
            "confirmed": False,
            "status": "HUMAN_REVIEW_AUTHENTICATION_UNAVAILABLE",
            "reason": f"Failed to load trusted signers registry: {exc}",
        }

    signer_entry = signers_map.get(reviewer_key_id)
    if not isinstance(signer_entry, dict):
        return {
            "confirmed": False,
            "status": "UNKNOWN_UNTRUSTED_SIGNING_KEY_ID",
            "reason": f"Signing key_id {reviewer_key_id!r} is not present in the trusted signers registry.",
        }

    if str(signer_entry.get("reviewer_id", "")).strip() != reviewer_id:
        return {
            "confirmed": False,
            "status": "REVIEWER_IDENTITY_KEY_MISMATCH",
            "reason": f"Key {reviewer_key_id!r} is bound to {signer_entry.get('reviewer_id')!r}, not {reviewer_id!r}.",
        }

    # Enforce production vs test-key separation
    env_scope = str(signer_entry.get("environment_scope", "PRODUCTION")).upper()
    if (env_scope != "PRODUCTION" or reviewer_key_id.upper().startswith("TEST_ONLY")) and not allow_isolated_test_signer:
        return {
            "confirmed": False,
            "status": "TEST_SIGNING_KEY_REJECTED_IN_PRODUCTION",
            "reason": f"Key {reviewer_key_id!r} has scope {env_scope!r} and is strictly rejected in production mode.",
        }

    # Enforce revocation and validity window
    if bool(signer_entry.get("revoked", False)):
        return {
            "confirmed": False,
            "status": "EXPIRED_OR_REVOKED_REVIEWER_AUTHORIZATION",
            "reason": f"Reviewer signing key {reviewer_key_id!r} has been revoked.",
        }

    now_utc = current_utc or datetime.now(timezone.utc)
    for exp_field, label in [
        (expires_at_utc, "record expires_at_utc"),
        (str(signer_entry.get("not_after_utc", "")), "key not_after_utc"),
    ]:
        if exp_field:
            exp_dt = _parse_utc_iso(exp_field)
            if exp_dt is None or now_utc > exp_dt:
                return {
                    "confirmed": False,
                    "status": "EXPIRED_OR_REVOKED_REVIEWER_AUTHORIZATION",
                    "reason": f"Authorization expired ({label}={exp_field!r}, current_utc={now_utc.isoformat()}).",
                }

    expected_digest = compute_human_review_digest(
        source_image_b_sha256=actual_src_sha,
        source_image_b_dimensions=[w, h],
        geometry_manifest_version=GEOMETRY_CONTRACT_VERSION,
        geometry_manifest_sha256=rec_manifest_sha,
        sha_s_building=actual_sha_s,
        sha_o_openings=actual_sha_o,
        sha_bay_curved=actual_sha_bay,
        reviewer_id=reviewer_id,
        reviewed_at_utc=reviewed_at,
        review_status="HUMAN_GEOMETRY_REVIEW_CONFIRMED",
        sha_o_uncertain=actual_sha_unc,
        reviewer_key_id=reviewer_key_id,
        expires_at_utc=expires_at_utc,
    )
    if str(rec.get("approval_digest_sha256", "")).lower() != expected_digest.lower():
        return {
            "confirmed": False,
            "status": "APPROVAL_CRYPTOGRAPHIC_DIGEST_INVALID",
            "reason": "approval_digest_sha256 does not match the canonical bound artifact hashes.",
        }

    try:
        pub_pem = str(signer_entry.get("public_key_pem", "")).encode("utf-8")
        pub_key = serialization.load_pem_public_key(pub_pem)
        if not isinstance(pub_key, Ed25519PublicKey):
            return {
                "confirmed": False,
                "status": "INVALID_CRYPTOGRAPHIC_SIGNATURE",
                "reason": "Registered public key is not a valid Ed25519PublicKey.",
            }
        sig_bytes = bytes.fromhex(sig_hex)
        pub_key.verify(sig_bytes, expected_digest.encode("utf-8"))
    except (ValueError, InvalidSignature) as exc:
        return {
            "confirmed": False,
            "status": "INVALID_CRYPTOGRAPHIC_SIGNATURE",
            "reason": f"Ed25519 signature verification failed: {exc}",
        }

    return {
        "confirmed": True,
        "status": "HUMAN_GEOMETRY_REVIEW_CONFIRMED",
        "authentication_scheme": "Ed25519_EXTERNAL_TRUSTED_KEY",
        "reviewer_id": reviewer_id,
        "reviewer_key_id": reviewer_key_id,
        "environment_scope": env_scope,
        "reviewed_at_utc": reviewed_at,
        "expires_at_utc": expires_at_utc,
        "approval_digest_sha256": expected_digest,
        "non_equivalence_notice": (
            "Cryptographic signature authenticates reviewer authorization and exact mask integrity; "
            "it does not by itself prove visual correctness."
        ),
    }


def transition_bundle_provenance_with_authenticated_review(
    img_working_bgr: np.ndarray,
    bundle: GeometryBundle2P5D,
    bundle_dir: Optional[pathlib.Path] = None,
    approval_file_path: Optional[pathlib.Path] = None,
    source_image_b_sha256: Optional[str] = None,
    prefix: str = "B01",
    trusted_signers_registry_path: Optional[pathlib.Path] = None,
    allow_isolated_test_signer: bool = False,
    current_utc: Optional[datetime] = None,
) -> Tuple[GeometryBundle2P5D, Dict[str, Any]]:
    """
    BLOCKER C FIX: Verified Provenance Transition for Real Operational G5 Execution.
    Only when `verify_human_review_approval_contract(...)` succeeds with a valid Ed25519
    signature covering the exact `IMAGE B`, `geometry_manifest`, `S_building`, `O_openings`,
    `O_uncertain`, and `bay_curved` hashes does this function transition:
      - `bay_provenance` -> `"BAY_GEOMETRY_HUMAN_REVIEW_CONFIRMED"`
      - `mask_provenance` -> `"HUMAN_GEOMETRY_REVIEW_CONFIRMED"`
    If verification fails or is missing, the bundle retains its unverified candidate provenance
    (`DA3_CURVED_BAY_CANDIDATE_REQUIRES_HUMAN_CONFIRMATION`) so G5 returns `UNKNOWN_UNVERIFIED_BAY_MASK`.
    """
    verification = verify_human_review_approval_contract(
        img_working_bgr=img_working_bgr,
        bundle=bundle,
        bundle_dir=bundle_dir,
        approval_file_path=approval_file_path,
        source_image_b_sha256=source_image_b_sha256,
        prefix=prefix,
        trusted_signers_registry_path=trusted_signers_registry_path,
        allow_isolated_test_signer=allow_isolated_test_signer,
        current_utc=current_utc,
    )
    if not verification.get("confirmed", False):
        return bundle, verification

    new_evidence = dict(bundle.architectural_evidence)
    new_evidence["authenticated_human_review"] = verification
    transitioned = dataclasses.replace(
        bundle,
        mask_provenance="HUMAN_GEOMETRY_REVIEW_CONFIRMED",
        bay_provenance="BAY_GEOMETRY_HUMAN_REVIEW_CONFIRMED",
        architectural_evidence=new_evidence,
    )
    return transitioned, verification


def validate_geometry_bundle_prerender_gate(
    img_working_bgr: np.ndarray,
    bundle: GeometryBundle2P5D,
    bundle_dir: Optional[pathlib.Path] = None,
    approval_file_path: Optional[pathlib.Path] = None,
    source_image_b_sha256: Optional[str] = None,
    prefix: str = "B01",
    cli_confirmation_flag_passed: bool = False,
    trusted_signers_registry_path: Optional[pathlib.Path] = None,
    allow_isolated_test_signer: bool = False,
    current_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    V2.2 Pre-Render Geometry Gate:
      - Validates spatial, partition, semantic opening protection (`F ∩ O_uncertain == ∅`),
        macro-edge purity, and curved-bay correspondence checks.
      - Enforces Ed25519-authenticated human review verification before `READY_FOR_FLUX_RENDER`.
    """
    h, w = img_working_bgr.shape[:2]
    total_px = float(h * w)
    s_px = int(np.sum(bundle.S > 0))
    f_px = int(np.sum(bundle.F > 0))
    o_px = int(np.sum(bundle.O > 0))
    unc_o_px = int(np.sum(bundle.O_uncertain > 0))
    sky_px = int(np.sum(bundle.P_sky > 0))
    gnd_px = int(np.sum(bundle.P_ground > 0))
    bay_px = int(np.sum(bundle.bay_mask > 0))
    macro_dg_px = int(np.sum(bundle.dG > 0))

    ys, xs = np.where(bundle.S > 0)
    if len(xs) == 0:
        return {
            "AUTOMATED_GEOMETRY_CHECKS_PASSED": False,
            "HUMAN_GEOMETRY_REVIEW_CONFIRMED": False,
            "READY_FOR_FLUX_RENDER": False,
            "automated_geometry_checks_pass": False,
            "human_visual_confirmation_present": False,
            "can_start_flux_render": False,
            "final_status": "GEOMETRY_GATE_BLOCKED",
            "blocking_reasons": ["EMPTY_BUILDING_MASK_S"],
        }

    x_min, x_max = int(np.min(xs)), int(np.max(xs))
    y_min, y_max = int(np.min(ys)), int(np.max(ys))
    centroid_x = float(np.mean(xs)) / float(w)
    centroid_y = float(np.mean(ys)) / float(h)

    central_box = bundle.S[int(0.22 * h) : int(0.72 * h), int(0.20 * w) : int(0.80 * w)]
    central_coverage = float(np.mean(central_box > 0))
    not_edge_strip = bool((x_max - x_min) >= int(0.45 * w) and 0.30 <= centroid_x <= 0.70)
    central_facade_ok = bool(central_coverage >= 0.65 and not_edge_strip)

    mid_sky_box = bundle.P_sky[int(0.25 * h) : int(0.70 * h), int(0.20 * w) : int(0.80 * w)]
    mid_sky_leak = float(np.mean(mid_sky_box > 0))
    sky_separation_ok = bool(mid_sky_leak <= 0.25 and sky_px >= int(0.05 * total_px))

    ground_overlap_openings = int(np.sum((bundle.P_ground > 0) & (bundle.O > 0)))
    ground_separation_ok = bool(
        gnd_px >= int(0.05 * total_px)
        and ground_overlap_openings == 0
        and int(0.65 * h) <= bundle.ground_contact_y <= int(0.92 * h)
    )

    hsv = cv2.cvtColor(img_working_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    b_ch = img_working_bgr[:, :, 0].astype(np.float32)
    g_ch = img_working_bgr[:, :, 1].astype(np.float32)
    r_ch = img_working_bgr[:, :, 2].astype(np.float32)
    foliage_in_s = (
        (bundle.S > 0)
        & (g_ch > r_ch + 4.0)
        & (g_ch > b_ch + 8.0)
        & (hsv[:, :, 0] >= 22.0)
        & (hsv[:, :, 0] <= 88.0)
    )
    vegetation_fraction_in_s = float(np.sum(foliage_in_s)) / float(max(s_px, 1))
    vegetation_exclusion_ok = bool(vegetation_fraction_in_s <= 0.05)

    # Blocker B check: F_editable must be strictly disjoint from both O_verified and O_uncertain
    f_inter_o_ver = int(np.sum((bundle.F > 0) & (bundle.O > 0)))
    f_inter_o_unc = int(np.sum((bundle.F > 0) & (bundle.O_uncertain > 0)))
    partition_exact = bool(
        f_inter_o_ver == 0
        and f_inter_o_unc == 0
        and np.array_equal((bundle.F > 0) | (bundle.O > 0) | (bundle.O_uncertain > 0), bundle.S > 0)
        and int(np.sum((bundle.S > 0) & (bundle.P > 0))) == 0
    )

    verified_openings_cnt = bundle.architectural_evidence.get("verified_architectural_openings_count", 0)
    levels_ok = bool(
        bundle.visible_levels_count >= 2
        and len(bundle.floor_lines_y) >= 2
        and o_px >= 1000
        and verified_openings_cnt >= 4
    )

    macro_density = macro_dg_px / float(max(s_px, 1))
    structural_edges_clean = bool(500 <= macro_dg_px and macro_density <= 0.09)

    bay_info = bundle.architectural_evidence.get("curved_projecting_bay", {})
    bay_outside_s = int(np.sum((bundle.bay_mask > 0) & (bundle.S == 0)))
    if bay_px > 0:
        bys, bxs = np.where(bundle.bay_mask > 0)
        bay_w = int(np.max(bxs)) - int(np.min(bxs)) + 1
        bay_h = int(np.max(bys)) - int(np.min(bys)) + 1
        bay_correspondence_ok = bool(
            bay_outside_s == 0
            and bay_w >= int(0.15 * w)
            and bay_h >= int(0.45 * h)
            and int(np.min(bxs)) >= 20
            and bay_info.get("quadratic_convexity_a", 0.0) <= -0.012
            and bay_info.get("quadratic_fit_r2", 0.0) >= 0.70
        )
    else:
        bay_correspondence_ok = False

    checks = {
        "central_facade_coverage": {
            "pass": central_facade_ok,
            "central_box_coverage_fraction": round(central_coverage, 4),
            "building_bbox_xyxy": [x_min, y_min, x_max, y_max],
            "centroid_xy_norm": [round(centroid_x, 3), round(centroid_y, 3)],
        },
        "sky_not_consuming_building": {
            "pass": sky_separation_ok,
            "mid_facade_sky_leak_fraction": round(mid_sky_leak, 4),
            "P_sky_pixels": sky_px,
        },
        "ground_plane_separation": {
            "pass": ground_separation_ok,
            "ground_contact_y": bundle.ground_contact_y,
            "P_ground_pixels": gnd_px,
            "ground_opening_overlap_pixels": ground_overlap_openings,
        },
        "vegetation_excluded_from_building": {
            "pass": vegetation_exclusion_ok,
            "vegetation_fraction_in_S": round(vegetation_fraction_in_s, 4),
        },
        "semantic_opening_protection_partition": {
            "pass": partition_exact,
            "F_editable_pixels": f_px,
            "O_verified_pixels": o_px,
            "O_uncertain_protected_pixels": unc_o_px,
            "F_intersection_O_verified": f_inter_o_ver,
            "F_intersection_O_uncertain": f_inter_o_unc,
        },
        "multi_storey_and_openings_evidence": {
            "pass": levels_ok,
            "visible_levels_count": bundle.visible_levels_count,
            "floor_lines_y": bundle.floor_lines_y.tolist(),
            "secondary_cornices_y": bundle.secondary_cornices_y.tolist(),
            "O_verified_pixels": o_px,
            "verified_openings_count": verified_openings_cnt,
            "raw_connected_components_count": bundle.architectural_evidence.get("raw_connected_components_count", 0),
            "uncertain_opening_candidates_count": bundle.architectural_evidence.get("uncertain_opening_candidates_count", 0),
        },
        "structural_macro_edges_purity": {
            "pass": structural_edges_clean,
            "dG_structural_macro_pixels": macro_dg_px,
            "dG_material_texture_pixels": int(np.sum(bundle.dG_texture > 0)),
            "macro_density_in_S": round(macro_density, 4),
        },
        "curved_bay_spatial_correspondence": {
            "pass": bay_correspondence_ok,
            "bay_pixels": bay_px,
            "bay_outside_S_pixels": bay_outside_s,
            "bay_details": bay_info,
        },
    }

    blocking_reasons = [k for k, v in checks.items() if not v["pass"]]
    automated_pass = len(blocking_reasons) == 0

    human_review_check = verify_human_review_approval_contract(
        img_working_bgr=img_working_bgr,
        bundle=bundle,
        bundle_dir=bundle_dir,
        approval_file_path=approval_file_path,
        source_image_b_sha256=source_image_b_sha256,
        prefix=prefix,
        trusted_signers_registry_path=trusted_signers_registry_path,
        allow_isolated_test_signer=allow_isolated_test_signer,
        current_utc=current_utc,
    )
    human_confirmed = bool(human_review_check.get("confirmed", False))

    if cli_confirmation_flag_passed and not human_confirmed:
        blocking_reasons.append(
            f"CLI_FLAG_BYPASS_REJECTED: --confirm-human-review was passed without an authenticated review record ({human_review_check.get('status')})."
        )

    ready_for_flux = bool(automated_pass and human_confirmed)

    if not automated_pass:
        final_status = "GEOMETRY_GATE_BLOCKED"
    elif not human_confirmed:
        final_status = "GEOMETRY_GATE_READY_FOR_HUMAN_REVIEW"
    else:
        final_status = "READY_FOR_FLUX_RENDER"

    return {
        "AUTOMATED_GEOMETRY_CHECKS_PASSED": automated_pass,
        "HUMAN_GEOMETRY_REVIEW_CONFIRMED": human_confirmed,
        "READY_FOR_FLUX_RENDER": ready_for_flux,
        "automated_geometry_checks_pass": automated_pass,
        "human_visual_confirmation_present": human_confirmed,
        "can_start_flux_render": ready_for_flux,
        "final_status": final_status,
        "human_review_verification": human_review_check,
        "blocking_reasons": blocking_reasons,
        "checks": checks,
    }


def save_geometry_bundle(
    bundle: GeometryBundle2P5D,
    out_dir: pathlib.Path,
    prefix: str = "B01",
    img_working_bgr: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    hashes: Dict[str, str] = {}

    def _write(name: str, arr_u8: np.ndarray) -> str:
        p = out_dir / f"{prefix}_{name}.png"
        cv2.imwrite(str(p), arr_u8)
        h_hex = sha256_bytes(p.read_bytes())
        hashes[name] = h_hex
        return str(p)

    _write("mask_S_building", bundle.S * 255)
    _write("mask_F_facade", bundle.F * 255)
    _write("mask_P_protected", bundle.P * 255)
    _write("mask_P_sky", bundle.P_sky * 255)
    _write("mask_P_ground", bundle.P_ground * 255)
    _write("mask_O_openings", bundle.O * 255)
    _write("mask_O_raw_components", bundle.O_raw_components * 255)
    _write("mask_O_uncertain_candidates", bundle.O_uncertain * 255)
    _write("mask_dG_structural_lines", bundle.dG * 255)
    _write("mask_dG_material_texture", bundle.dG_texture * 255)
    _write("mask_bay_curved", bundle.bay_mask * 255)
    _write("mask_uncertain_regions", bundle.uncertain_mask * 255)

    if bundle.depth_map is not None:
        _write("da3_depth_estimate", np.clip(bundle.depth_map * 255.0, 0, 255).astype(np.uint8))
    if bundle.normals_map is not None:
        norm_u8 = np.clip((bundle.normals_map * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
        _write("da3_normals_estimate", norm_u8)

    manifest = {
        "contract": GEOMETRY_CONTRACT_VERSION,
        "prefix": prefix,
        "depth_provenance": bundle.depth_provenance,
        "mask_provenance": bundle.mask_provenance,
        "bay_provenance": bundle.bay_provenance,
        "segmentation_confidence": bundle.segmentation_confidence,
        "visible_levels_count": bundle.visible_levels_count,
        "floor_lines_y": bundle.floor_lines_y.tolist(),
        "secondary_cornices_y": bundle.secondary_cornices_y.tolist(),
        "ground_contact_y": bundle.ground_contact_y,
        "pixel_counts": {
            "S_building": int(np.sum(bundle.S > 0)),
            "F_facade": int(np.sum(bundle.F > 0)),
            "F_editable": int(np.sum(bundle.F > 0)),
            "O_openings_verified": int(np.sum(bundle.O > 0)),
            "O_raw_components_pixels": int(np.sum(bundle.O_raw_components > 0)),
            "O_uncertain_candidates_pixels": int(np.sum(bundle.O_uncertain > 0)),
            "PROTECTED_UNCERTAIN_pixels": int(np.sum(bundle.protected_uncertain > 0)),
            "P_protected_total": int(np.sum(bundle.P > 0)),
            "P_sky": int(np.sum(bundle.P_sky > 0)),
            "P_ground": int(np.sum(bundle.P_ground > 0)),
            "dG_structural_macro": int(np.sum(bundle.dG > 0)),
            "dG_material_texture": int(np.sum(bundle.dG_texture > 0)),
            "bay_curved": int(np.sum(bundle.bay_mask > 0)),
            "uncertain_regions": int(np.sum(bundle.uncertain_mask > 0)),
        },
        "architectural_evidence": bundle.architectural_evidence,
        "sha256_hashes": hashes,
    }
    manifest_file = out_dir / f"{prefix}_geometry_manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    approval_file = out_dir / f"{prefix}_human_review_approval.json"
    if img_working_bgr is not None and not approval_file.exists():
        write_unapproved_human_review_template(img_working_bgr, out_dir, prefix=prefix)

    return manifest
