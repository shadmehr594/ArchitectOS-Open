"""ArchitectOS v21.0 — 4-mode render router.

Maps a chat render request onto one of the four explicit ComfyUI modes and
supplies that mode's sampling parameters. Classification is deterministic and
side-effect free so it can be tested without a GPU or a ComfyUI server.

Lives outside ``engine/`` so a future package refresh cannot overwrite it.
"""

from __future__ import annotations

import re

MODE_1_TXT2IMG = "MODE_1_TXT2IMG"
MODE_2_IMG2IMG_MATERIAL_STYLE_TRANSFER = "MODE_2_IMG2IMG_MATERIAL_STYLE_TRANSFER"
MODE_3_DAY_TO_NIGHT_RELIGHT = "MODE_3_DAY_TO_NIGHT_RELIGHT"
MODE_4_PLAN_TO_3D_RENDER = "MODE_4_PLAN_TO_3D_RENDER"

ALL_MODES = (
    MODE_1_TXT2IMG,
    MODE_2_IMG2IMG_MATERIAL_STYLE_TRANSFER,
    MODE_3_DAY_TO_NIGHT_RELIGHT,
    MODE_4_PLAN_TO_3D_RENDER,
)

# Parameters are the ones fixed by the v21 specification, not tunables.
MODE_PARAMS = {
    MODE_1_TXT2IMG: {
        "denoise": 1.00,
        "controlnet_strength": 0.00,
        "end_percent": None,
        "uso_lora": None,
        "latent": "EmptyLatentImage",
        "requires_image_b": False,
        "requires_day_render": False,
        "requires_active_plan": False,
    },
    MODE_2_IMG2IMG_MATERIAL_STYLE_TRANSFER: {
        "denoise": 0.78,
        "controlnet_strength": 0.72,
        "end_percent": 0.80,
        "uso_lora": 0.92,
        "latent": "VAEEncode",
        "requires_image_b": True,
        "requires_day_render": False,
        "requires_active_plan": False,
    },
    MODE_3_DAY_TO_NIGHT_RELIGHT: {
        "denoise": 0.46,
        "controlnet_strength": 0.94,
        "end_percent": 1.00,
        "uso_lora": 0.25,
        "latent": "VAEEncode",
        "requires_image_b": False,
        "requires_day_render": True,
        "requires_active_plan": False,
    },
    MODE_4_PLAN_TO_3D_RENDER: {
        "denoise": 0.92,
        "controlnet_strength": 0.88,
        "end_percent": 0.90,
        "uso_lora": 0.92,
        "latent": "EmptyLatentImage+ControlNet",
        "requires_image_b": False,
        "requires_day_render": False,
        "requires_active_plan": True,
    },
}

_NIGHT = (
    "شب", "شبانه", "نورپردازی شب", "غروب", "شامگاه",
    "night", "evening", "dusk", "twilight", "nocturnal",
)

_PERSPECTIVE = (
    "پرسپکتیو", "پرسپكتيو", "نما", "سه بعدی", "سه‌بعدی", "ایزومتریک",
    "perspective", "elevation", "3d", "isometric",
)

_MATERIAL = (
    "متریال", "سبک", "سنگ", "تراورتن", "آجر", "نئوکلاسیک", "کلاسیک",
    "بازطراحی", "روکار", "نماکاری", "سفیدکاری", "سفت‌کاری", "سفت کاری",
    "ترمووود", "چوب", "شیشه", "نمای جدید",
    "material", "style", "travertine", "brick", "neoclassical",
    "redesign", "cladding", "renovate",
)

_RAW_BUILDING = (
    "ساختمان خام", "ساختمان قدیمی", "آجر", "بلوک", "سیپورکس",
    "raw", "unfinished", "brick", "cinderblock",
)

_RENDER = ("رندر", "render", "تصویر", "عکس", "بگیر", "بساز")


def _has(text: str, needles) -> bool:
    s = (text or "").lower()
    return any(n.lower() in s for n in needles)


def classify_render_mode(
    text: str,
    *,
    has_image_b: bool = False,
    has_style_reference: bool = False,
    has_active_plan: bool = False,
    has_day_render: bool = False,
) -> str:
    """Classify a chat request into one of the four v21 modes.

    Order is significant: night relighting outranks everything (it must reuse
    the approved day render, never the raw building), then plan-to-3D (a plan
    is the authority), then material/style transfer, then plain text-to-image.
    """
    s = (text or "").strip()

    if not s:
        return MODE_1_TXT2IMG

    # MODE 3 — relight an existing day render. Requires a prior day render;
    # without one this is a fresh night concept, not a relight.
    if _has(s, _NIGHT) and has_day_render:
        return MODE_3_DAY_TO_NIGHT_RELIGHT

    # MODE 4 — an approved plan is the source of geometry.
    if has_active_plan and _has(s, _PERSPECTIVE):
        return MODE_4_PLAN_TO_3D_RENDER

    # MODE 2 — restyling/recladding an existing building image.
    if has_image_b and (_has(s, _MATERIAL) or _has(s, _RAW_BUILDING)):
        return MODE_2_IMG2IMG_MATERIAL_STYLE_TRANSFER

    if has_image_b and has_style_reference:
        return MODE_2_IMG2IMG_MATERIAL_STYLE_TRANSFER

    # A night ask with no day render still needs a building to relight; if one
    # was uploaded, treat it as material/style work rather than t2i.
    if _has(s, _NIGHT) and has_image_b:
        return MODE_2_IMG2IMG_MATERIAL_STYLE_TRANSFER

    return MODE_1_TXT2IMG


def params_for(mode: str) -> dict:
    return dict(MODE_PARAMS[mode])


def apply_mode_to_args(mode: str, args) -> None:
    """Overwrite the sampler args on an argparse namespace for this mode."""
    p = MODE_PARAMS[mode]
    args.denoise = p["denoise"]
    args.controlnet_strength = p["controlnet_strength"]
    args.end_percent = p["end_percent"]
    args.uso_lora = p["uso_lora"]
    args.render_mode = mode


def build_workflow(mode: str, base_workflow, positive: str, negative: str,
                   seed: int = 123456789):
    """Delegate to the engine's per-mode workflow builder."""
    from engine.unified_comfy_pipeline import build_mode_specific_stage2_workflow

    return build_mode_specific_stage2_workflow(
        base_workflow, mode, positive, negative, seed=seed
    )


def describe(mode: str) -> str:
    p = MODE_PARAMS[mode]
    end = "—" if p["end_percent"] is None else f"{p['end_percent']:.2f}"
    return (
        f"{mode}: denoise={p['denoise']:.2f} "
        f"controlnet={p['controlnet_strength']:.2f} end_percent={end}"
    )
