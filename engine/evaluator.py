#!/usr/bin/env python3
"""
Honest, Fail-Closed Architectural Geometry & Style Evaluator (V2.2).
File: engine/evaluator.py

V2.2 Targeted Corrections:
  - BLOCKER C FIX (Real Pipeline Integration of Authenticated Bay Provenance into G5):
      * Integrates `transition_bundle_provenance_with_authenticated_review` directly into
        `evaluate_architectural_transfer` so an Ed25519-authenticated human review record
        transitions `bay_provenance` from `DA3_CURVED_BAY_CANDIDATE_REQUIRES_HUMAN_CONFIRMATION`
        to `BAY_GEOMETRY_HUMAN_REVIEW_CONFIRMED` in real operational flow without `dataclasses.replace`.
      * Preserves fail-closed `UNKNOWN_UNVERIFIED_BAY_MASK` whenever human review is missing,
        unapproved, forged, tampered, or lacks a trusted signing key.
  - SECTION 7 FIX (`_evaluate_floor_lines_g2` Secondary Horizontal Line Evaluation):
      * Evaluates `secondary_cornices_y` (`secondary_ref` vs `secondary_gen`) alongside primary
        floor lines (`f_ref` vs `f_gen`).
      * Ensures decorative cornices, roof parapet caps, and balcony bases remain distinct from
        primary floor slabs and flags `FAIL_SECONDARY_CORNICE_MISCLASSIFIED_AS_PRIMARY_FLOOR`
        if a secondary element is falsely promoted into an extra storey slab.
"""
from __future__ import annotations
import dataclasses
from datetime import datetime
import pathlib
from typing import Any, Dict, List, Optional
import cv2
import numpy as np
from .geometry_2p5d import (
    GeometryBundle2P5D,
    compute_normals_from_da3_depth,
    extract_geometry_bundle_2p5d,
    transition_bundle_provenance_with_authenticated_review,
    validate_geometry_bundle_prerender_gate,
)

try:
    from scipy.optimize import linear_sum_assignment
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


@dataclasses.dataclass
class HonestEvaluationResult:
    overall_status: str
    overall_pass: bool
    gate_verdicts: Dict[str, str]
    metrics: Dict[str, Any]
    failure_reasons: List[str]


def _chamfer_symmetric(edges_ref: np.ndarray, edges_gen: np.ndarray) -> Optional[float]:
    if int(np.sum(edges_ref > 0)) == 0 or int(np.sum(edges_gen > 0)) == 0:
        return None
    dist_ref = cv2.distanceTransform((edges_ref == 0).astype(np.uint8), cv2.DIST_L2, 3)
    dist_gen = cv2.distanceTransform((edges_gen == 0).astype(np.uint8), cv2.DIST_L2, 3)
    d1 = float(np.mean(dist_gen[edges_ref > 0]))
    d2 = float(np.mean(dist_ref[edges_gen > 0]))
    return 0.5 * (d1 + d2)


def _evaluate_floor_lines_g2(
    f_ref: np.ndarray,
    f_gen: np.ndarray,
    secondary_gen: Optional[np.ndarray] = None,
    secondary_ref: Optional[np.ndarray] = None,
    max_single_level_dev_px: float = 4.0,
    max_mean_dev_px: float = 2.5,
) -> Dict[str, Any]:
    """
    BLOCKER 2 & SECTION 7 FIX — Ordered One-to-One Primary Floor-Line Matching +
    Secondary Architectural Line Evaluation.
    """
    ref_arr = np.sort(np.asarray(f_ref, dtype=np.float64).ravel())
    gen_arr = np.sort(np.asarray(f_gen, dtype=np.float64).ravel())
    sec_ref_arr = (
        np.sort(np.asarray(secondary_ref, dtype=np.float64).ravel())
        if secondary_ref is not None
        else np.array([], dtype=np.float64)
    )
    sec_gen_arr = (
        np.sort(np.asarray(secondary_gen, dtype=np.float64).ravel())
        if secondary_gen is not None
        else np.array([], dtype=np.float64)
    )

    if len(ref_arr) == 0:
        return {
            "status": "UNKNOWN_INSUFFICIENT_REFERENCE_FLOOR_EVIDENCE",
            "pass": False,
            "ref_floor_lines_y": [],
            "gen_floor_lines_y": gen_arr.tolist(),
        }

    if len(gen_arr) == 0:
        return {
            "status": "FAIL_NO_OUTPUT_FLOOR_LINES",
            "pass": False,
            "ref_floor_lines_y": ref_arr.tolist(),
            "gen_floor_lines_y": [],
        }

    if len(gen_arr) < len(ref_arr):
        return {
            "status": "FAIL_MISSING_ARCHITECTURAL_FLOOR_LINE",
            "pass": False,
            "ref_count": int(len(ref_arr)),
            "gen_count": int(len(gen_arr)),
            "ref_floor_lines_y": ref_arr.tolist(),
            "gen_floor_lines_y": gen_arr.tolist(),
            "reason": f"Expected {len(ref_arr)} floor lines {ref_arr.tolist()}, but generated output has only {len(gen_arr)}: {gen_arr.tolist()}.",
        }

    if len(gen_arr) > len(ref_arr):
        promoted_cornices = []
        if len(sec_ref_arr) > 0:
            for gy in gen_arr:
                if all(abs(gy - ry) > 6.0 for ry in ref_arr):
                    if any(abs(gy - sy) <= 6.0 for sy in sec_ref_arr):
                        promoted_cornices.append(float(gy))
        return {
            "status": "FAIL_INVENTED_EXTRA_FLOOR_LINE",
            "pass": False,
            "ref_count": int(len(ref_arr)),
            "gen_count": int(len(gen_arr)),
            "ref_floor_lines_y": ref_arr.tolist(),
            "gen_floor_lines_y": gen_arr.tolist(),
            "secondary_cornice_misclassified_as_floor_y": promoted_cornices,
            "reason": (
                f"Expected {len(ref_arr)} primary floor lines {ref_arr.tolist()}, but generated output has "
                f"{len(gen_arr)}: {gen_arr.tolist()}"
                + (
                    f" (secondary cornice(s) {promoted_cornices} falsely promoted to floor lines)."
                    if promoted_cornices
                    else "."
                )
            ),
        }

    min_ref_spacing = float(np.min(np.diff(ref_arr))) if len(ref_arr) >= 2 else 28.0
    min_allowed_spacing = max(12.0, 0.50 * min_ref_spacing)
    if len(gen_arr) >= 2 and float(np.min(np.diff(gen_arr))) < min_allowed_spacing:
        return {
            "status": "FAIL_COLLAPSED_OR_DUPLICATED_FLOOR_LINES",
            "pass": False,
            "ref_floor_lines_y": ref_arr.tolist(),
            "gen_floor_lines_y": gen_arr.tolist(),
            "min_gen_spacing_px": round(float(np.min(np.diff(gen_arr))), 2),
            "min_required_spacing_px": round(min_allowed_spacing, 2),
        }

    per_level_devs = np.abs(gen_arr - ref_arr)
    max_dev = float(np.max(per_level_devs))
    mean_dev = float(np.mean(per_level_devs))
    passed = bool(max_dev <= max_single_level_dev_px and mean_dev <= max_mean_dev_px)

    # Section 7: Meaningfully evaluate secondary horizontal lines (cornices, parapet cap, slab upper edges)
    if secondary_gen is None and secondary_ref is None:
        sec_eval = {
            "secondary_status": "UNKNOWN_SECONDARY_LINES_NOT_PROVIDED",
            "ref_secondary_cornices_y": [],
            "gen_secondary_cornices_y": [],
        }
    elif len(sec_ref_arr) == 0 and len(sec_gen_arr) == 0:
        sec_eval = {
            "secondary_status": "UNKNOWN_NO_SECONDARY_LINES_DETECTED",
            "ref_secondary_cornices_y": [],
            "gen_secondary_cornices_y": [],
        }
    else:
        # Verify secondary lines do not collide with primary floor lines (must stay > 8 px apart)
        collided_with_primary = [
            float(sy) for sy in sec_gen_arr if any(abs(sy - fy) <= 8.0 for fy in gen_arr)
        ]
        matched_sec_devs = []
        for s_ref_y in sec_ref_arr:
            if len(sec_gen_arr) > 0:
                d_min = float(np.min(np.abs(sec_gen_arr - s_ref_y)))
                if d_min <= 6.0:
                    matched_sec_devs.append(d_min)
        sec_recall = len(matched_sec_devs) / float(max(len(sec_ref_arr), 1)) if len(sec_ref_arr) > 0 else 1.0
        if collided_with_primary:
            sec_status = "FAIL_SECONDARY_COLLIDED_WITH_PRIMARY_FLOOR"
            passed = False
        elif len(sec_ref_arr) > 0 and len(sec_gen_arr) == 0:
            sec_status = "UNKNOWN_SECONDARY_LINES_MISSING_IN_GEN"
        elif sec_recall >= 0.65:
            sec_status = "PASS_SECONDARY_DISTINCT_AND_ALIGNED"
        else:
            sec_status = "WARN_SECONDARY_PARTIAL_ALIGNMENT"

        sec_eval = {
            "secondary_status": sec_status,
            "ref_secondary_cornices_y": [int(round(x)) for x in sec_ref_arr.tolist()],
            "gen_secondary_cornices_y": [int(round(x)) for x in sec_gen_arr.tolist()],
            "secondary_matched_count": len(matched_sec_devs),
            "secondary_recall": round(sec_recall, 3),
            "secondary_mean_deviation_px": round(float(np.mean(matched_sec_devs)), 3) if matched_sec_devs else None,
            "collided_with_primary_floor_y": collided_with_primary,
        }

    return {
        "status": "PASS" if passed else "FAIL_FLOOR_LINE_POSITION_DRIFT",
        "pass": passed,
        "ref_count": int(len(ref_arr)),
        "gen_count": int(len(gen_arr)),
        "ref_floor_lines_y": ref_arr.tolist(),
        "gen_floor_lines_y": gen_arr.tolist(),
        "ordered_per_level_deviations_px": [round(float(d), 3) for d in per_level_devs],
        "max_level_deviation_px": round(max_dev, 3),
        "mean_level_deviation_px": round(mean_dev, 3),
        "secondary_cornices_y": [int(round(x)) for x in sec_gen_arr.tolist()],
        "secondary_elements_evaluation": sec_eval,
    }


def _match_openings_bipartite(O_ref: np.ndarray, O_gen: np.ndarray, max_dist_px: float = 8.0) -> Dict[str, Any]:
    n_r, lbl_r, stats_r, cents_r = cv2.connectedComponentsWithStats(O_ref.astype(np.uint8))
    n_g, lbl_g, stats_g, cents_g = cv2.connectedComponentsWithStats(O_gen.astype(np.uint8))
    num_ref = n_r - 1
    num_gen = n_g - 1

    if num_ref == 0:
        return {
            "status": "UNKNOWN_NO_REF_OPENINGS",
            "pass": False,
            "num_ref_openings": 0,
            "num_gen_openings": num_gen,
        }
    if num_gen == 0:
        return {
            "status": "FAIL_ZERO_OPENINGS_IN_OUTPUT",
            "pass": False,
            "num_ref_openings": num_ref,
            "num_gen_openings": 0,
            "recall": 0.0,
            "precision": 0.0,
        }

    c_r = cents_r[1:].astype(np.float64)
    c_g = cents_g[1:].astype(np.float64)
    cost = np.linalg.norm(c_r[:, None, :] - c_g[None, :, :], axis=-1)

    if HAS_SCIPY:
        row_ind, col_ind = linear_sum_assignment(cost)
        pairs = list(zip(row_ind.tolist(), col_ind.tolist()))
    else:
        pairs = []
        used_g = set()
        for i in range(num_ref):
            j = int(np.argmin(cost[i]))
            if j not in used_g and int(np.argmin(cost[:, j])) == i:
                pairs.append((i, j))
                used_g.add(j)

    matched_dists = []
    matched_ious = []
    valid_matches = 0
    for r_idx, g_idx in pairs:
        d = float(cost[r_idx, g_idx])
        if d <= max_dist_px:
            m_r = lbl_r == (r_idx + 1)
            m_g = lbl_g == (g_idx + 1)
            iou = float(np.sum(m_r & m_g)) / float(max(np.sum(m_r | m_g), 1))
            matched_dists.append(d)
            matched_ious.append(iou)
            if iou >= 0.35:
                valid_matches += 1

    recall = valid_matches / float(num_ref)
    precision = valid_matches / float(num_gen)
    med_disp = float(np.median(matched_dists)) if matched_dists else 99.0
    mean_iou = float(np.mean(matched_ious)) if matched_ious else 0.0

    passed = bool(recall >= 0.80 and precision >= 0.75 and med_disp <= 3.5)
    return {
        "status": "PASS" if passed else "FAIL",
        "pass": passed,
        "num_ref_openings": num_ref,
        "num_gen_openings": num_gen,
        "valid_matched_openings": valid_matches,
        "recall": round(recall, 3),
        "precision": round(precision, 3),
        "median_centroid_displacement_px": round(med_disp, 3),
        "mean_matched_opening_iou": round(mean_iou, 3),
    }


def _evaluate_curved_bay_3d(
    ref_bundle: GeometryBundle2P5D,
    gen_da3_depth_bgr: Optional[np.ndarray],
    img_b_bgr: np.ndarray,
    img_gen_bgr: np.ndarray,
    min_signed_ratio: float = 0.70,
    max_signed_ratio: float = 1.35,
) -> Dict[str, Any]:
    """
    BLOCKER 1 & BLOCKER C FIX — G5 Signed Curvature & Authenticated Provenance Evaluation.
    Requires `ref_bundle.bay_provenance` to be `"BAY_GEOMETRY_HUMAN_REVIEW_CONFIRMED"` (or
    `"HUMAN_GEOMETRY_REVIEW_CONFIRMED"`). Unverified candidate masks return `UNKNOWN_UNVERIFIED_BAY_MASK`.
    """
    bay = (ref_bundle.bay_mask > 0) & (ref_bundle.valid_roi > 0) & (ref_bundle.S > 0)
    o_dil = cv2.dilate((ref_bundle.O | ref_bundle.O_uncertain), np.ones((5, 5), np.uint8)) > 0
    bay_wall = bay & (~o_dil)

    s_px = int(np.sum(ref_bundle.S > 0))
    bay_px = int(np.sum(bay))
    if int(np.sum(bay_wall)) < 500 or bay_px < int(0.08 * max(s_px, 1)):
        return {
            "status": "FAIL_INVALID_OR_TINY_BAY_MASK",
            "pass": False,
            "reason": f"Curved bay mask ({bay_px} px) is too small or spatially invalid relative to building S ({s_px} px).",
        }

    bys, bxs = np.where(bay)
    if int(np.min(bxs)) < 20 or (int(np.max(bxs)) - int(np.min(bxs))) < 45:
        return {
            "status": "FAIL_BAY_MISPLACED_AT_IMAGE_EDGE",
            "pass": False,
            "reason": f"Bay mask x-span [{int(np.min(bxs))}..{int(np.max(bxs))}] is misplaced in the image edge margin.",
        }

    allowed_confirmed_provenances = {
        "BAY_GEOMETRY_HUMAN_REVIEW_CONFIRMED",
        "HUMAN_GEOMETRY_REVIEW_CONFIRMED",
    }
    if (
        ref_bundle.bay_provenance not in allowed_confirmed_provenances
        or "UNCONFIRMED" in ref_bundle.bay_provenance
        or "UNVERIFIED" in ref_bundle.bay_provenance
        or "CANDIDATE" in ref_bundle.bay_provenance
        or "REQUIRES" in ref_bundle.bay_provenance
    ):
        return {
            "status": "UNKNOWN_UNVERIFIED_BAY_MASK",
            "pass": False,
            "bay_provenance": ref_bundle.bay_provenance,
            "reason": f"Bay provenance is `{ref_bundle.bay_provenance}`; G5 refuses PASS on unverified bay masks.",
        }

    if ref_bundle.depth_map is None or gen_da3_depth_bgr is None:
        return {
            "status": "UNKNOWN_MISSING_DA3_DEPTH",
            "pass": False,
            "reason": "Model-derived DA3 depth map is required for both B01 and generated output to verify 3D curvature.",
        }

    lab_b = cv2.cvtColor(img_b_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab_g = cv2.cvtColor(img_gen_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    bay_delta_e = float(np.mean(np.linalg.norm(lab_g[bay_wall] - lab_b[bay_wall], axis=-1)))
    if bay_delta_e < 12.0:
        return {
            "status": "FAIL_UNCHANGED_RAW_PIXELS_IN_BAY",
            "pass": False,
            "bay_deltaE_LAB": round(bay_delta_e, 2),
            "reason": "Generated bay pixels are nearly identical to raw IMAGE B; copying does not prove geometry preservation.",
        }

    h, w = img_gen_bgr.shape[:2]
    gen_depth, gen_normals = compute_normals_from_da3_depth(gen_da3_depth_bgr, (h, w))

    non_bay_roi = (ref_bundle.valid_roi > 0) & (~bay)
    ref_d_all = ref_bundle.depth_map[non_bay_roi]
    gen_d_all = gen_depth[non_bay_roi]
    iqr_ref = float(np.percentile(ref_d_all, 85) - np.percentile(ref_d_all, 15))
    iqr_gen = float(np.percentile(gen_d_all, 85) - np.percentile(gen_d_all, 15))
    if iqr_ref < 0.015 or iqr_gen < 0.015:
        return {
            "status": "UNKNOWN_DEGENERATE_MONOCULAR_DEPTH_RANGE",
            "pass": False,
            "iqr_ref": round(iqr_ref, 4),
            "iqr_gen": round(iqr_gen, 4),
            "reason": "Monocular depth dynamic range is too flat for reliable 3D curvature comparison.",
        }
    s_affine = iqr_gen / iqr_ref

    x_min, x_max = int(np.min(bxs)), int(np.max(bxs))
    valid_x, prof_ref, prof_gen = [], [], []
    for x in range(x_min, x_max + 1):
        col = bay_wall[:, x]
        if int(np.sum(col)) >= 8:
            valid_x.append(float(x))
            prof_ref.append(float(np.percentile(ref_bundle.depth_map[col, x], 75)))
            prof_gen.append(float(np.percentile(gen_depth[col, x], 75)))

    if len(valid_x) < 12:
        return {
            "status": "UNKNOWN_INSUFFICIENT_BAY_COLUMNS",
            "pass": False,
        }

    u = np.linspace(-1.0, 1.0, len(valid_x))
    z_ref = np.array(prof_ref, dtype=np.float64)
    z_gen_aligned = np.array(prof_gen, dtype=np.float64) / max(s_affine, 1e-4)

    coeffs_ref = np.polyfit(u, z_ref, 2)
    coeffs_gen = np.polyfit(u, z_gen_aligned, 2)
    a_ref_signed = float(coeffs_ref[0])
    a_gen_signed = float(coeffs_gen[0])

    fit_ref = np.polyval(coeffs_ref, u)
    fit_gen = np.polyval(coeffs_gen, u)
    r2_ref = 1.0 - float(np.sum((z_ref - fit_ref) ** 2)) / (float(np.sum((z_ref - np.mean(z_ref)) ** 2)) + 1e-8)
    r2_gen = 1.0 - float(np.sum((z_gen_aligned - fit_gen) ** 2)) / (
        float(np.sum((z_gen_aligned - np.mean(z_gen_aligned)) ** 2)) + 1e-8
    )

    if abs(a_ref_signed) < 0.012 or r2_ref < 0.65:
        return {
            "status": "UNKNOWN_WEAK_REFERENCE_CURVATURE_EVIDENCE",
            "pass": False,
            "a_ref_signed": round(a_ref_signed, 5),
            "r2_ref": round(r2_ref, 4),
        }

    signed_curv_ratio = float(a_gen_signed / a_ref_signed)

    nx_ref = ref_bundle.normals_map[:, :, 0][bay_wall].ravel()
    nx_gen = gen_normals[:, :, 0][bay_wall].ravel()
    if float(np.std(nx_ref)) < 1e-5 or float(np.std(nx_gen)) < 1e-5:
        nx_corr = 0.0
    else:
        nx_corr = float(np.corrcoef(nx_ref, nx_gen)[0, 1])

    diagnostics = {
        "bay_provenance": ref_bundle.bay_provenance,
        "a_ref_signed": round(a_ref_signed, 5),
        "a_gen_signed": round(a_gen_signed, 5),
        "signed_curvature_ratio": round(signed_curv_ratio, 4),
        "allowed_ratio_bounds": [min_signed_ratio, max_signed_ratio],
        "r2_ref": round(r2_ref, 4),
        "r2_gen": round(r2_gen, 4),
        "normal_nx_pearson_r": round(nx_corr, 4),
        "affine_depth_scale": round(s_affine, 4),
        "bay_deltaE_LAB": round(bay_delta_e, 2),
    }

    if signed_curv_ratio <= 0.0 or nx_corr < 0.0:
        return {
            "status": "FAIL_REVERSED_CURVATURE_ORIENTATION",
            "pass": False,
            "reason": f"Curvature sign reversed (a_ref={a_ref_signed:.4f}, a_gen={a_gen_signed:.4f}, ratio={signed_curv_ratio:.3f}).",
            **diagnostics,
        }

    if signed_curv_ratio < min_signed_ratio:
        return {
            "status": "FAIL_CURVATURE_FLATTENED",
            "pass": False,
            "reason": f"Signed curvature ratio {signed_curv_ratio:.3f} is below lower bound {min_signed_ratio}.",
            **diagnostics,
        }

    if signed_curv_ratio > max_signed_ratio:
        return {
            "status": "FAIL_CURVATURE_EXAGGERATED_OUT_OF_BOUNDS",
            "pass": False,
            "reason": f"Signed curvature ratio {signed_curv_ratio:.3f} exceeds upper bound {max_signed_ratio}.",
            **diagnostics,
        }

    if r2_gen < 0.65 or nx_corr < 0.75:
        return {
            "status": "FAIL_BAY_SURFACE_DISTORTED",
            "pass": False,
            "reason": f"Bay surface profile is distorted (R2_gen={r2_gen:.3f}, nx_corr={nx_corr:.3f}).",
            **diagnostics,
        }

    return {
        "status": "PASS",
        "pass": True,
        **diagnostics,
    }


def _evaluate_structural_edges_g6(
    ref_bundle: GeometryBundle2P5D,
    gen_bundle: GeometryBundle2P5D,
    max_chamfer_px: float = 2.5,
) -> Dict[str, Any]:
    """
    BLOCKER 5 FIX — Evaluates G6 exclusively on STRUCTURAL_MACRO_EDGES (`dG`),
    rejecting reference edge maps contaminated by brick mortar texture.
    """
    roi = ref_bundle.valid_roi > 0
    s_px = max(int(np.sum((ref_bundle.S > 0) & roi)), 1)
    ref_macro = (ref_bundle.dG > 0) & roi
    gen_macro = (gen_bundle.dG > 0) & roi
    macro_px = int(np.sum(ref_macro))
    tex_px = int(np.sum((ref_bundle.dG_texture > 0) & roi)) if hasattr(ref_bundle, "dG_texture") else 0
    macro_density = macro_px / float(s_px)

    if macro_px < 400:
        return {
            "status": "UNKNOWN_INSUFFICIENT_STRUCTURAL_EDGES",
            "pass": False,
            "dG_macro_pixels": macro_px,
        }

    if macro_density > 0.090:
        return {
            "status": "UNKNOWN_TEXTURE_CONTAMINATED_STRUCTURAL_EDGES",
            "pass": False,
            "dG_macro_pixels": macro_px,
            "dG_texture_pixels": tex_px,
            "macro_density_in_S": round(macro_density, 4),
            "reason": f"Reference structural edge density ({macro_density:.3f}) exceeds 0.090 macro threshold due to texture contamination.",
        }

    chamfer = _chamfer_symmetric(ref_macro.astype(np.uint8), gen_macro.astype(np.uint8))
    if chamfer is None:
        return {"status": "UNKNOWN", "pass": False, "chamfer_px": None}

    passed = bool(chamfer <= max_chamfer_px)
    return {
        "status": "PASS" if passed else "FAIL_STRUCTURAL_ALIGNMENT_DRIFT",
        "pass": passed,
        "chamfer_px": round(chamfer, 3),
        "dG_macro_pixels": macro_px,
        "dG_texture_excluded_pixels": tex_px,
        "macro_density_in_S": round(macro_density, 4),
    }


def _wasserstein_1d(u: np.ndarray, v: np.ndarray, quantiles: int = 100) -> float:
    q = np.linspace(0.01, 0.99, quantiles)
    uq = np.quantile(u, q)
    vq = np.quantile(v, q)
    return float(np.mean(np.abs(uq - vq)))


def _evaluate_style_and_anti_copy(
    img_b_bgr: np.ndarray,
    img_gen_bgr: np.ndarray,
    img_a_style_bgr: Optional[np.ndarray],
    ref_bundle: GeometryBundle2P5D,
    gen_bundle: GeometryBundle2P5D,
) -> Dict[str, Any]:
    roi = ref_bundle.valid_roi > 0
    f_mask = (ref_bundle.F > 0) & roi
    if not np.any(f_mask):
        return {"status": "UNKNOWN_EMPTY_F_MASK", "anti_copy_pass": False, "style_pass": False}

    lab_b = cv2.cvtColor(img_b_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab_g = cv2.cvtColor(img_gen_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)

    delta_e_f = float(np.mean(np.linalg.norm(lab_g[f_mask] - lab_b[f_mask], axis=-1)))
    anti_copy_pass = bool(delta_e_f >= 12.0)

    if img_a_style_bgr is None:
        return {
            "status": "UNKNOWN_MISSING_STYLE_IMAGE_A",
            "anti_copy_deltaE_LAB": round(delta_e_f, 2),
            "anti_copy_pass": anti_copy_pass,
            "style_pass": False,
        }

    lab_a = cv2.cvtColor(img_a_style_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    a_flat = lab_a.reshape(-1, 3)
    b_f = lab_b[f_mask]
    g_f = lab_g[f_mask]

    w_ba = sum(_wasserstein_1d(b_f[:, c], a_flat[:, c]) for c in range(3)) / 3.0
    w_ga = sum(_wasserstein_1d(g_f[:, c], a_flat[:, c]) for c in range(3)) / 3.0
    wasserstein_improvement = w_ba - w_ga

    sky_bleed_ratio = float(np.sum((gen_bundle.S > 0) & (ref_bundle.P_sky > 0))) / float(
        max(np.sum(ref_bundle.S > 0), 1)
    )
    no_dome_bleed = sky_bleed_ratio <= 0.035

    style_pass = bool(anti_copy_pass and no_dome_bleed and (wasserstein_improvement > 1.5 or w_ga < 18.0))
    return {
        "status": "PASS" if style_pass else "FAIL",
        "anti_copy_deltaE_LAB": round(delta_e_f, 2),
        "anti_copy_pass": anti_copy_pass,
        "lab_wasserstein_B_to_A": round(w_ba, 2),
        "lab_wasserstein_Gen_to_A": round(w_ga, 2),
        "lab_wasserstein_improvement": round(wasserstein_improvement, 2),
        "sky_dome_bleed_ratio": round(sky_bleed_ratio, 4),
        "no_dome_bleed_pass": no_dome_bleed,
        "style_pass": style_pass,
    }


def evaluate_architectural_transfer(
    img_b_bgr: np.ndarray,
    img_gen_bgr: np.ndarray,
    img_a_style_bgr: Optional[np.ndarray],
    ref_bundle: GeometryBundle2P5D,
    gen_da3_depth_bgr: Optional[np.ndarray] = None,
    bundle_dir: Optional[pathlib.Path] = None,
    approval_file_path: Optional[pathlib.Path] = None,
    trusted_signers_registry_path: Optional[pathlib.Path] = None,
    allow_isolated_test_signer: bool = False,
    current_utc: Optional[datetime] = None,
) -> HonestEvaluationResult:
    """
    V2.2 End-to-End Architectural Transfer Evaluator.
    If `bundle_dir` or `approval_file_path` is provided, performs an authenticated provenance
    transition (`transition_bundle_provenance_with_authenticated_review`) so `G5` evaluates
    the real approved bundle when—and only when—an Ed25519-signed human review record is verified.
    """
    h, w = img_b_bgr.shape[:2]
    if img_gen_bgr.shape[:2] != (h, w):
        img_gen_bgr = cv2.resize(img_gen_bgr, (w, h), interpolation=cv2.INTER_LANCZOS4)

    review_transition_info = None
    if bundle_dir is not None or approval_file_path is not None:
        ref_bundle, review_transition_info = transition_bundle_provenance_with_authenticated_review(
            img_working_bgr=img_b_bgr,
            bundle=ref_bundle,
            bundle_dir=bundle_dir,
            approval_file_path=approval_file_path,
            trusted_signers_registry_path=trusted_signers_registry_path,
            allow_isolated_test_signer=allow_isolated_test_signer,
            current_utc=current_utc,
        )

    ref_gate = validate_geometry_bundle_prerender_gate(
        img_b_bgr,
        ref_bundle,
        bundle_dir=bundle_dir,
        approval_file_path=approval_file_path,
        trusted_signers_registry_path=trusted_signers_registry_path,
        allow_isolated_test_signer=allow_isolated_test_signer,
        current_utc=current_utc,
    )
    if not ref_gate["AUTOMATED_GEOMETRY_CHECKS_PASSED"]:
        invalid_verdicts = {
            "G1_silhouette": "FAIL_INVALID_REFERENCE_MASK",
            "G2_floor_lines": "FAIL_INVALID_REFERENCE_MASK",
            "G3_openings_bipartite": "FAIL_INVALID_REFERENCE_MASK",
            "G4_opening_arch_contours": "FAIL_INVALID_REFERENCE_MASK",
            "G5_curved_bay_3d": "FAIL_INVALID_REFERENCE_MASK",
            "G6_camera_structural_alignment": "FAIL_INVALID_REFERENCE_MASK",
            "AntiCopy_facade_change": "FAIL_INVALID_REFERENCE_MASK",
            "Style_neoclassical_transfer": "FAIL_INVALID_REFERENCE_MASK",
        }
        return HonestEvaluationResult(
            overall_status="FAIL_DEFECTIVE_REFERENCE_GEOMETRY",
            overall_pass=False,
            gate_verdicts=invalid_verdicts,
            metrics={"reference_geometry_gate": ref_gate},
            failure_reasons=["REFERENCE_GEOMETRY_FAILED_PRERENDER_GATE"] + ref_gate["blocking_reasons"],
        )

    gen_bundle = extract_geometry_bundle_2p5d(img_gen_bgr, da3_depth_bgr=gen_da3_depth_bgr)
    roi = ref_bundle.valid_roi > 0

    # G1: Building Silhouette IoU
    s_ref = (ref_bundle.S > 0) & roi
    s_gen = (gen_bundle.S > 0) & roi
    g1_iou = float(np.sum(s_ref & s_gen)) / float(max(np.sum(s_ref | s_gen), 1))
    g1_pass = g1_iou >= 0.92

    # G2: Ordered 1-to-1 Floor-Line Matching + Secondary Architectural Line Evaluation
    g2_res = _evaluate_floor_lines_g2(
        ref_bundle.floor_lines_y,
        gen_bundle.floor_lines_y,
        secondary_gen=gen_bundle.secondary_cornices_y,
        secondary_ref=ref_bundle.secondary_cornices_y,
    )
    g2_pass = bool(g2_res["pass"])

    # G3: 1-to-1 Bipartite Verified Opening Matching
    g3_res = _match_openings_bipartite(ref_bundle.O & ref_bundle.valid_roi, gen_bundle.O & ref_bundle.valid_roi)
    g3_pass = bool(g3_res["pass"])

    # G4: Verified Opening & Arch Contour Chamfer Distance
    dO_ref = ((ref_bundle.O > 0) & (cv2.erode(ref_bundle.O, np.ones((3, 3), np.uint8)) == 0)) & roi
    dO_gen = ((gen_bundle.O > 0) & (cv2.erode(gen_bundle.O, np.ones((3, 3), np.uint8)) == 0)) & roi
    g4_chamfer = _chamfer_symmetric(dO_ref.astype(np.uint8), dO_gen.astype(np.uint8))
    g4_pass = bool(g4_chamfer is not None and g4_chamfer <= 3.0)
    g4_status = "PASS" if g4_pass else ("UNKNOWN" if g4_chamfer is None else "FAIL")

    # G5: Signed & Bounded 3D Curved Projecting Bay Verification
    g5_res = _evaluate_curved_bay_3d(ref_bundle, gen_da3_depth_bgr, img_b_bgr, img_gen_bgr)
    g5_pass = bool(g5_res["pass"])

    # G6: Macro Structural Boundary Alignment
    g6_res = _evaluate_structural_edges_g6(ref_bundle, gen_bundle)
    g6_pass = bool(g6_res["pass"])

    # Style & Anti-Copy Gate
    style_res = _evaluate_style_and_anti_copy(img_b_bgr, img_gen_bgr, img_a_style_bgr, ref_bundle, gen_bundle)
    anti_copy_pass = bool(style_res["anti_copy_pass"])
    style_pass = bool(style_res["style_pass"])

    gate_verdicts = {
        "G1_silhouette": "PASS" if g1_pass else "FAIL",
        "G2_floor_lines": g2_res["status"],
        "G3_openings_bipartite": g3_res["status"],
        "G4_opening_arch_contours": g4_status,
        "G5_curved_bay_3d": g5_res["status"],
        "G6_camera_structural_alignment": g6_res["status"],
        "AntiCopy_facade_change": "PASS" if anti_copy_pass else "FAIL_COPY_DETECTED",
        "Style_neoclassical_transfer": style_res["status"],
    }

    failures = [k for k, v in gate_verdicts.items() if v != "PASS"]
    has_unknown = any("UNKNOWN" in v for v in gate_verdicts.values())
    overall_pass = len(failures) == 0

    if overall_pass:
        overall_status = "PASS_QUANTITATIVE_AWAITING_HUMAN_GATE3"
    elif has_unknown:
        overall_status = "UNKNOWN_OR_FAIL_INCOMPLETE_EVIDENCE"
    else:
        overall_status = "FAIL"

    return HonestEvaluationResult(
        overall_status=overall_status,
        overall_pass=overall_pass,
        gate_verdicts=gate_verdicts,
        metrics={
            "G1_silhouette_iou": round(g1_iou, 4),
            "G2_floor_lines": g2_res,
            "G3_openings": g3_res,
            "G4_opening_chamfer_px": round(g4_chamfer, 3) if g4_chamfer is not None else None,
            "G5_curved_bay_3d": g5_res,
            "G6_structural_macro": g6_res,
            "style_and_anti_copy": style_res,
            "authenticated_provenance_transition": review_transition_info,
        },
        failure_reasons=failures,
    )


def generate_gate3_inspection_sheet(
    img_b_bgr: np.ndarray,
    img_a_style_bgr: np.ndarray,
    img_gen_bgr: np.ndarray,
    ref_bundle: GeometryBundle2P5D,
    out_path: pathlib.Path,
) -> pathlib.Path:
    h, w = img_b_bgr.shape[:2]
    p_b = img_b_bgr.copy()
    p_a = cv2.resize(img_a_style_bgr, (w, h), interpolation=cv2.INTER_LANCZOS4)
    p_g = cv2.resize(img_gen_bgr, (w, h), interpolation=cv2.INTER_LANCZOS4)
    p_ov = p_g.copy()

    dS = (ref_bundle.S > 0) & (cv2.erode(ref_bundle.S, np.ones((3, 3), np.uint8)) == 0)
    dO = (ref_bundle.O > 0) & (cv2.erode(ref_bundle.O, np.ones((3, 3), np.uint8)) == 0)
    dBay = (ref_bundle.bay_mask > 0) & (cv2.erode(ref_bundle.bay_mask, np.ones((3, 3), np.uint8)) == 0)

    p_ov[dS] = (255, 255, 0)
    p_ov[dO] = (255, 0, 255)
    p_ov[dBay] = (0, 255, 255)
    for fy in ref_bundle.floor_lines_y:
        if 0 <= fy < h:
            p_ov[max(0, fy - 1) : min(h, fy + 1), :] = (0, 215, 255)

    def _add_header(panel: np.ndarray, title: str) -> np.ndarray:
        bar = np.full((36, panel.shape[1], 3), (24, 30, 42), dtype=np.uint8)
        cv2.putText(bar, title, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (240, 245, 250), 1, cv2.LINE_AA)
        return np.vstack([bar, panel])

    c1 = _add_header(p_b, "1. IMAGE B (Geometry Authority)")
    c2 = _add_header(p_a, "2. IMAGE A (Style Authority)")
    c3 = _add_header(p_g, "3. Generated Output")
    c4 = _add_header(p_ov, "4. Output + B01 Wireframe Overlay")

    sep = np.full((c1.shape[0], 6, 3), (60, 75, 95), dtype=np.uint8)
    sheet = np.hstack([c1, sep, c2, sep, c3, sep, c4])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), sheet)
    return out_path
