"""CPU acceptance for the v22 experimental high-rise / night capabilities.

Scope: pure CPU. No GPU, no ComfyUI submission, no model load, no network.
Every assertion here is about *deterministic image synthesis and graph
wiring*. None of it proves that FLUX renders the requested number of storeys,
and none of it proves a night render is visually convincing.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from core.render.experimental.architectos_v22_highrise_night_v1 import (
    MIN_HIGH_RISE_FLOORS,
    MODE_DAY_TO_NIGHT_RELIGHT,
    MODE_TXT2IMG_EXACT_FLOORS,
    MissingControlNetNodeError,
    build_mode_specific_stage2_workflow,
    kelvin_to_bgr,
    lock_night_render_to_day_geometry,
    parse_requested_floor_count,
    parse_requested_floor_count_detail,
    requires_exact_floor_control,
    synthesize_day_to_night_prepass,
    synthesize_exact_n_story_tower_controlnet,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "core" / "render" / "workflows"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _load(name: str) -> dict:
    return json.loads((WORKFLOWS / name).read_text("utf-8"))


def _synthetic_day_render(w: int = 384, h: int = 352):
    rng = np.random.default_rng(11)
    img = np.zeros((h, w, 3), dtype=np.uint8)
    horizon = int(h * 0.20)
    for y in range(horizon):
        t = y / max(1, horizon - 1)
        img[y, :] = (int(235 - 40 * t), int(215 - 30 * t), int(185 - 25 * t))
    img[horizon:, :] = (120, 122, 124)

    fx0, fx1 = int(w * 0.12), int(w * 0.88)
    fy0, fy1 = int(h * 0.24), int(h * 0.88)
    facade = np.full((fy1 - fy0, fx1 - fx0, 3), 0, dtype=np.float32)
    facade[:] = np.array([78, 104, 158], dtype=np.float32)
    facade = np.clip(facade + rng.normal(0, 7, facade.shape[:2])[..., None], 0, 255)
    for yy in range(0, fy1 - fy0, 9):
        facade[yy:yy + 1, :] *= 0.82
    img[fy0:fy1, fx0:fx1] = facade.astype(np.uint8)

    mask_O = np.zeros((h, w), dtype=np.uint8)
    cols, rows = 5, 4
    cw, ch = (fx1 - fx0) // cols, (fy1 - fy0) // rows
    for r in range(rows):
        for c in range(cols):
            wx0 = fx0 + c * cw + int(cw * 0.22)
            wx1 = fx0 + c * cw + int(cw * 0.78)
            wy0 = fy0 + r * ch + int(ch * 0.20)
            wy1 = fy0 + r * ch + int(ch * 0.72)
            img[wy0:wy1, wx0:wx1] = (46, 52, 58)
            mask_O[wy0:wy1, wx0:wx1] = 255

    mask_S = np.zeros((h, w), dtype=np.uint8)
    mask_S[fy0:fy1, fx0:fx1] = 255
    mask_sky = np.zeros((h, w), dtype=np.uint8)
    mask_sky[:horizon, :] = 255
    return img, mask_S, mask_O, mask_sky


# ---------------------------------------------------------------------------
# floor-count parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("\u0633\u0627\u062e\u062a\u0645\u0627\u0646 \u06f2\u06f5 \u0637\u0628\u0642\u0647", 25),
        ("\u0633\u0627\u062e\u062a\u0645\u0627\u0646 25 \u0637\u0628\u0642\u0647", 25),
        ("25-story tower", 25),
        ("a 12 storey building", 12),
        ("8 floors", 8),
        ("\u06f1\u06f2 \u0637\u0628\u0642\u0647", 12),
        ("3 floors", 3),
        ("\u06f1 \u0637\u0628\u0642\u0647", 1),
        ("a house with a nice garden", None),
        ("", None),
    ],
)
def test_parse_positive_counts(text, expected):
    assert parse_requested_floor_count(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "no 25 floors",
        "without 12 storeys",
        "\u0633\u0627\u062e\u062a\u0645\u0627\u0646 25 \u0637\u0628\u0642\u0647 \u0646\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645",
        "\u0628\u062f\u0648\u0646 8 \u0637\u0628\u0642\u0647",
    ],
)
def test_parse_negated_counts_return_none(text):
    reading = parse_requested_floor_count_detail(text)
    assert reading.count is None
    assert reading.negated is True
    assert reading.is_exact is False


def test_parse_does_not_treat_post_qualifier_as_negation():
    # "25 floors, not more" affirms 25; only the negative-verb family negates.
    assert parse_requested_floor_count("25 floors, not more") == 25


def test_parse_ignores_numeral_inside_larger_number():
    assert parse_requested_floor_count("area 1,250 m2 with 6 floors") == 6


def test_gate_threshold():
    assert MIN_HIGH_RISE_FLOORS == 5
    assert requires_exact_floor_control(5) is True
    assert requires_exact_floor_control(4) is False
    assert requires_exact_floor_control(None) is False


# ---------------------------------------------------------------------------
# scaffold synthesis
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [5, 12, 25, 40])
def test_scaffold_tier_count_is_exact(n):
    _, meta = synthesize_exact_n_story_tower_controlnet(
        num_floors=n, canvas_width=896, canvas_height=1344, podium_floors=2
    )
    assert meta["tier_count"] == n
    assert meta["tier_count_matches_request"] is True
    assert meta["podium_floors"] == 2
    assert meta["tower_floors"] == n - 2


@pytest.mark.parametrize("n", [5, 12, 25, 40])
def test_scaffold_margins_and_no_cropping(n):
    _, meta = synthesize_exact_n_story_tower_controlnet(
        num_floors=n, canvas_width=896, canvas_height=1344, podium_floors=2
    )
    assert meta["cropped"] is False
    assert meta["top_margin_satisfied"] is True
    assert meta["bottom_margin_satisfied"] is True
    # Requested margins are a floor, never a ceiling: a width-constrained fit
    # legitimately leaves more sky, which can only reduce crop risk.
    assert meta["margins_actual"]["top"] >= 0.12 - 1e-3
    assert meta["margins_actual"]["bottom"] >= 0.10 - 1e-3


@pytest.mark.parametrize("n", [25, 40])
def test_tall_tower_binds_height_so_margin_is_exact(n):
    _, meta = synthesize_exact_n_story_tower_controlnet(
        num_floors=n, canvas_width=896, canvas_height=1344, podium_floors=2
    )
    assert meta["fit_bound"] == "height"
    assert abs(meta["margins_actual"]["top"] - 0.12) < 0.01


def test_scaffold_is_deterministic():
    _, a = synthesize_exact_n_story_tower_controlnet(25, 896, 1344, 2)
    _, b = synthesize_exact_n_story_tower_controlnet(25, 896, 1344, 2)
    assert a["sha256_png"] == b["sha256_png"]


def test_scaffold_carries_no_building_identity():
    _, meta = synthesize_exact_n_story_tower_controlnet(25, 896, 1344, 2)
    assert meta["carries_building_identity"] is False
    assert meta["perspective"] == "two_point"
    # Only the two camera-facing faces are drawn; drawing all four produces
    # spurious chevrons that ControlNet can read as real articulation.
    assert meta["visible_faces"] == 2
    assert meta["horizontal_edges_per_ring"] == 2


def test_scaffold_is_lineart_on_white():
    """The ControlNet map must read as lineart: white field, dark strokes."""
    img, _ = synthesize_exact_n_story_tower_controlnet(12, 256, 384, 2)
    white = (img.min(axis=2) >= 250).mean()
    dark = (img.max(axis=2) < 60).mean()
    assert white > 0.85, "background should dominate a lineart map"
    assert dark > 0.005, "strokes must be present and dark"
    assert white + dark < 1.0, "antialiasing should produce intermediate greys"


@pytest.mark.parametrize("n", [25, 40])
def test_measured_scanline_runs_match_drawn_rings(n):
    """Count horizontal line crossings on a column inside the visible face.

    Expected crossings are ``N + 1`` ring levels. The podium roof edge and the
    tower base edge share a storey height but not a footprint, so they project
    to slightly different rows and add one extra crossing while they remain
    resolvable; at tighter tier spacing they merge. Both outcomes are
    legitimate, so the assertion is bounded by those two cases rather than
    pinned to a single number.
    """
    img, _ = synthesize_exact_n_story_tower_controlnet(n, 896, 1344, 2)
    ink = img.min(axis=2) < 250
    col_counts = ink.sum(axis=0)
    near_x = int(np.argmax(col_counts))
    left_x = int(np.where(col_counts > 0)[0].min())
    x = near_x - int(0.35 * (near_x - left_x))
    col = ink[:, x]
    runs = 0
    prev = False
    for v in col:
        if v and not prev:
            runs += 1
        prev = bool(v)
    assert runs in (n + 1, n + 2)


def test_scaffold_rejects_misaligned_canvas():
    with pytest.raises(ValueError):
        synthesize_exact_n_story_tower_controlnet(10, 100, 100, 2)


def test_scaffold_rejects_podium_larger_than_building():
    with pytest.raises(ValueError):
        synthesize_exact_n_story_tower_controlnet(2, 256, 384, 5)


def test_scaffold_rejects_zero_floors():
    with pytest.raises(ValueError):
        synthesize_exact_n_story_tower_controlnet(0, 256, 384, 0)


# ---------------------------------------------------------------------------
# graph construction
# ---------------------------------------------------------------------------


def test_mode1_params_exact():
    wf = build_mode_specific_stage2_workflow(
        _load("flux.json"),
        MODE_TXT2IMG_EXACT_FLOORS,
        "full building from podium to roof crown inside frame",
        "cropped tower",
        control_image_name="scaffold.png",
    )
    assert wf["210"]["inputs"]["denoise"] == 0.96
    assert wf["311"]["inputs"]["strength"] == 0.86
    assert wf["311"]["inputs"]["end_percent"] == 0.88
    assert wf["311"]["inputs"]["start_percent"] == 0.0
    # text-to-image must stay text-to-image: latent still comes from the
    # EmptyLatentImage, not from a VAEEncode of the control map.
    assert wf["210"]["inputs"]["latent_image"] == ["211", 0]
    assert wf["210"]["inputs"]["positive"] == ["311", 0]
    assert wf["210"]["inputs"]["negative"] == ["311", 1]
    assert wf["311"]["inputs"]["image"] == ["312", 0]
    assert wf["312"]["inputs"]["image"] == "scaffold.png"
    assert wf["311"]["inputs"]["vae"] == ["205", 0]


def test_mode3_params_exact():
    wf = build_mode_specific_stage2_workflow(
        _load("flux_img2img_dual_conditioned.json"),
        MODE_DAY_TO_NIGHT_RELIGHT,
        "blue-hour night photography",
        "daylight",
        control_image_name="night_control.png",
        source_image_name="night_prepass.png",
    )
    assert wf["210"]["inputs"]["denoise"] == 0.34
    assert wf["311"]["inputs"]["strength"] == 0.96
    assert wf["311"]["inputs"]["end_percent"] == 1.00
    assert wf["311"]["inputs"]["start_percent"] == 0.0
    assert wf["312"]["inputs"]["image"] == "night_control.png"
    assert wf["300"]["inputs"]["image"] == "night_prepass.png"
    # img2img latent still comes from the source VAEEncode
    assert wf["210"]["inputs"]["latent_image"] == ["301", 0]


def test_mode3_fails_closed_without_controlnet():
    with pytest.raises(MissingControlNetNodeError):
        build_mode_specific_stage2_workflow(
            _load("flux_img2img.json"),
            MODE_DAY_TO_NIGHT_RELIGHT,
            "night",
            "day",
        )


def test_mode1_fails_closed_without_control_image():
    with pytest.raises(MissingControlNetNodeError):
        build_mode_specific_stage2_workflow(
            _load("flux.json"), MODE_TXT2IMG_EXACT_FLOORS, "a", "b"
        )


def test_builder_does_not_mutate_input_graph():
    base = _load("flux.json")
    snapshot = json.dumps(base, sort_keys=True)
    build_mode_specific_stage2_workflow(
        base, MODE_TXT2IMG_EXACT_FLOORS, "x", "y", control_image_name="c.png"
    )
    assert json.dumps(base, sort_keys=True) == snapshot


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        build_mode_specific_stage2_workflow(_load("flux.json"), "MODE_9", "a", "b")


def test_canonical_workflow_files_unmodified():
    # Guard against accidental in-place edits by any future refactor.
    expected = {
        "flux.json": "C2B9C603C58FE6A21E93643EDCBF5A71F65CFFD4AF061771562D84FA013961C4",
    }
    import hashlib

    for name, digest in expected.items():
        got = hashlib.sha256((WORKFLOWS / name).read_bytes()).hexdigest().upper()
        assert got == digest


# ---------------------------------------------------------------------------
# night prepass
# ---------------------------------------------------------------------------


def test_prepass_enforces_facade_luminance_floor():
    day, mask_S, mask_O, mask_sky = _synthetic_day_render()
    _, meta = synthesize_day_to_night_prepass(
        day, mask_S, mask_O, mask_sky, min_facade_luminance_floor=0.38
    )
    assert meta["facade_luma_ratio"] is not None
    assert meta["facade_luma_ratio"] >= 0.38 - 1e-6
    assert meta["facade_floor_satisfied"] is True


def test_prepass_does_not_leave_facade_brighter_than_day():
    day, mask_S, mask_O, mask_sky = _synthetic_day_render()
    _, meta = synthesize_day_to_night_prepass(
        day, mask_S, mask_O, mask_sky, min_facade_luminance_floor=0.38
    )
    assert meta["facade_luma_ratio"] <= 1.0 + 1e-6
    assert meta["facade_not_brighter_than_day"] is True


def test_prepass_darkens_the_sky():
    day, mask_S, mask_O, mask_sky = _synthetic_day_render()
    _, meta = synthesize_day_to_night_prepass(
        day, mask_S, mask_O, mask_sky, min_facade_luminance_floor=0.38
    )
    assert meta["sky_darkened"] is True
    # The R3 NIGHT-05 target was sky luma <= 40 against a daylight ~190.
    assert meta["sky_luma_after"] <= 40.0


def test_prepass_warms_openings_and_walls():
    day, mask_S, mask_O, mask_sky = _synthetic_day_render()
    out, meta = synthesize_day_to_night_prepass(
        day, mask_S, mask_O, mask_sky, min_facade_luminance_floor=0.38
    )
    assert meta["interior_glow_delta"] > 0
    assert meta["uplight_delta"] > 0
    # Openings must end up warm: red channel above blue.
    o = mask_O > 0
    assert out[o][:, 2].mean() > out[o][:, 0].mean()


def test_prepass_is_deterministic():
    day, mask_S, mask_O, mask_sky = _synthetic_day_render()
    _, a = synthesize_day_to_night_prepass(day, mask_S, mask_O, mask_sky)
    _, b = synthesize_day_to_night_prepass(day, mask_S, mask_O, mask_sky)
    assert a["output_sha256"] == b["output_sha256"]


def test_prepass_rejects_impossible_floor_above_ceiling():
    day, mask_S, mask_O, mask_sky = _synthetic_day_render()
    with pytest.raises(ValueError):
        synthesize_day_to_night_prepass(
            day, mask_S, mask_O, mask_sky,
            min_facade_luminance_floor=0.9, facade_luma_ceiling_ratio=0.5,
        )


def test_prepass_rejects_mask_shape_mismatch():
    day, _, mask_O, _ = _synthetic_day_render()
    with pytest.raises(ValueError):
        synthesize_day_to_night_prepass(day, np.zeros((10, 10), np.uint8), mask_O)


# ---------------------------------------------------------------------------
# geometry lock
# ---------------------------------------------------------------------------


def _night_pair():
    day, mask_S, mask_O, mask_sky = _synthetic_day_render()
    night_pre, _ = synthesize_day_to_night_prepass(day, mask_S, mask_O, mask_sky)
    # Simulated sampler damage: invented vertical mullion + global darkening.
    comfy = night_pre.copy()
    h, w = comfy.shape[:2]
    cv2.line(comfy, (w // 2, 0), (w // 2, h), (10, 10, 10), 3)
    comfy = np.clip(comfy.astype(np.float32) * 0.6, 0, 255).astype(np.uint8)
    return day, comfy, mask_S


def test_lock_raises_high_frequency_correlation_with_day():
    day, comfy, mask_S = _night_pair()
    _, meta = lock_night_render_to_day_geometry(day, comfy, mask_S, 0.65)
    before = meta["hf_correlation_with_day_before"]
    after = meta["hf_correlation_with_day_after"]
    assert before is not None and after is not None
    assert after > before
    assert meta["hf_correlation_gain"] > 0.20
    assert meta["hf_dominated_by_day"] is True


def test_lock_preserves_sampler_low_frequency():
    day, comfy, mask_S = _night_pair()
    _, meta = lock_night_render_to_day_geometry(day, comfy, mask_S, 0.65)
    # Lighting/atmosphere come from the sampler; only detail is replaced.
    assert meta["low_frequency_delta_vs_sampler"] < 6.0


def test_lock_full_weight_maximises_detail_recovery():
    day, comfy, mask_S = _night_pair()
    _, meta = lock_night_render_to_day_geometry(day, comfy, mask_S, 1.0)
    assert meta["exact_detail_copy"] is True
    assert meta["hf_correlation_with_day_after"] > 0.95


def test_lock_rejects_out_of_range_weight():
    day, comfy, mask_S = _night_pair()
    with pytest.raises(ValueError):
        lock_night_render_to_day_geometry(day, comfy, mask_S, 1.5)


def test_lock_rejects_shape_mismatch():
    day, comfy, mask_S = _night_pair()
    with pytest.raises(ValueError):
        lock_night_render_to_day_geometry(day, comfy[:10, :10], mask_S)


# ---------------------------------------------------------------------------
# colour temperature
# ---------------------------------------------------------------------------


def test_kelvin_is_warm_at_2900_and_neutral_at_6500():
    b2900, g2900, r2900 = kelvin_to_bgr(2900)
    b6500, g6500, r6500 = kelvin_to_bgr(6500)
    assert r2900 > g2900 > b2900          # warm
    assert r2900 > r6500 or b2900 < b6500  # warmer than daylight
    assert abs(r6500 - b6500) < 30         # near neutral
    for v in (b2900, g2900, r2900, b6500, g6500, r6500):
        assert 0.0 <= v <= 255.0


def test_exterior_washer_is_cooler_than_interior_glow():
    b_i, _, r_i = kelvin_to_bgr(2900)
    b_e, _, r_e = kelvin_to_bgr(3000)
    # Higher Kelvin => more blue, less red.
    assert b_e >= b_i
    assert r_e <= r_i
