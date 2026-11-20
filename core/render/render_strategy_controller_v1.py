# ==========================================================
# ArchitectOS Render Strategy Controller v1
#
# PROJECT_WORKSPACE_UI_06 — MODE SELECTOR + RENDER STRATEGY + SEED
#
# Architecture (locked)
#
#   USER INTENT
#     -> Render Strategy Controller        <- THIS MODULE
#     -> validated parameters
#     -> isolated workflow copy
#     -> execution
#
# The controller may control VALIDATED FIELDS ONLY:
#   render profile / steps / resolution when safe / seed policy /
#   img2img preservation level / denoise / approved preset /
#   approved workflow selection.
#
# It must NEVER mutate an arbitrary node graph, and it must never let
# an LLM write workflow JSON.
#
# Disabled modes never silently execute another route: they return a
# truthful refusal.
# ==========================================================


from __future__ import annotations


from core.render.render_draft_v1 import (
    PROFILE_DRAFT,
    PROFILE_PREVIEW,
    PROFILE_QUALITY,
    PROFILE_FINAL,
    PROFILE_ORDER,
    TEST_PROFILES,
    resolve_profile,
    resolve_seed,
    quality_override,
    SEED_LOCK,
    SEED_REROLL,
    SEED_REUSE,
)


CONTRACT = "RenderStrategyControllerV1"
VERSION = "1.0"


# ----------------------------------------------------------
# MODES
# ----------------------------------------------------------

MODE_AUTO = "auto"
MODE_CHAT = "chat"
MODE_TEXT_TO_IMAGE = "text_to_image"
MODE_IMAGE_TO_IMAGE = "image_to_image"
MODE_ANALYZE_IMAGE = "analyze_image"

# PLAN_DESIGN_MODE_V1 — the parametric CAD plan surface.
#
# This is an ACTIVE mode, not a reserved one: the producer exists
# (`ParametricArchitecturalSynthesizer` + the exporters) and answers with a
# real sheet. It is deliberately NOT a render mode — it never reaches
# ComfyUI, and the chat turn returns a plan before any render dispatch.
MODE_PLAN_DESIGN = "plan_design"

MODE_TEXT_TO_VIDEO = "text_to_video"
MODE_IMAGE_TO_VIDEO = "image_to_video"


# Modes the backend can actually execute today.
ACTIVE_MODES = (
    MODE_AUTO,
    MODE_CHAT,
    MODE_TEXT_TO_IMAGE,
    MODE_IMAGE_TO_IMAGE,
    MODE_ANALYZE_IMAGE,
    MODE_PLAN_DESIGN,
)

# Reserved until the backend exists. Never silently re-routed.
RESERVED_MODES = (
    MODE_TEXT_TO_VIDEO,
    MODE_IMAGE_TO_VIDEO,
)


MODE_LABELS = {
    MODE_AUTO: "Auto",
    MODE_CHAT: "Chat",
    MODE_TEXT_TO_IMAGE: "Text → Image",
    MODE_IMAGE_TO_IMAGE: "Image → Image",
    MODE_ANALYZE_IMAGE: "Analyze Image",
    MODE_PLAN_DESIGN: "Plan Design (طراحی و ویرایش پلان)",
    MODE_TEXT_TO_VIDEO: "Text → Video",
    MODE_IMAGE_TO_VIDEO: "Image → Video",
}


def normalize_mode(value):

    if value is None:

        return MODE_AUTO

    key = str(value).strip().lower().replace(" ", "_").replace("-", "_")

    aliases = {
        "": MODE_AUTO,
        "auto": MODE_AUTO,
        "chat": MODE_CHAT,
        "text_to_image": MODE_TEXT_TO_IMAGE,
        "text2image": MODE_TEXT_TO_IMAGE,
        "t2i": MODE_TEXT_TO_IMAGE,
        "image_to_image": MODE_IMAGE_TO_IMAGE,
        "image2image": MODE_IMAGE_TO_IMAGE,
        "i2i": MODE_IMAGE_TO_IMAGE,
        "analyze": MODE_ANALYZE_IMAGE,
        "analyze_image": MODE_ANALYZE_IMAGE,
        "plan": MODE_PLAN_DESIGN,
        "plan_design": MODE_PLAN_DESIGN,
        "plandesign": MODE_PLAN_DESIGN,
        "text_to_video": MODE_TEXT_TO_VIDEO,
        "text2video": MODE_TEXT_TO_VIDEO,
        "image_to_video": MODE_IMAGE_TO_VIDEO,
        "image2video": MODE_IMAGE_TO_VIDEO,
    }

    return aliases.get(key, key)


def is_active_mode(mode):

    return normalize_mode(mode) in ACTIVE_MODES


def is_reserved_mode(mode):

    return normalize_mode(mode) in RESERVED_MODES


# ----------------------------------------------------------
# QUALITY REQUESTED FROM CHAT INTENT
#
# Deterministic keyword table. No LLM writes workflow JSON.
# ----------------------------------------------------------

_QUALITY_INTENT = (

    # FINAL
    (PROFILE_FINAL, (
        "همینه، نهایی بگیر", "همینه نهایی بگیر", "نهایی بگیر", "نهاییش کن",
        "فاینال", "نسخه نهایی", "خروجی نهایی",
        "final render", "final quality", "final version", "ship it",
    )),

    # QUALITY
    (PROFILE_QUALITY, (
        "کیفیتش رو بهتر کن", "کیفیت رو بهتر کن", "کیفیت بهتر", "کیفیت بالا",
        "با کیفیت", "رزولوشن بالا", "دقت بالا",
        "higher quality", "high quality", "better quality", "quality render",
    )),

    # PREVIEW
    (PROFILE_PREVIEW, (
        "یه پیش نمایش بگیر", "پیش نمایش", "پیش‌نمایش", "پریویو",
        "preview", "preview render",
    )),

    # DRAFT
    (PROFILE_DRAFT, (
        "یه تست سریع بده", "تست سریع", "سریع بگیر", "یه تست بگیر",
        "فقط تست", "اسکچ", "اسکیس",
        "quick test", "draft", "fast test", "rough", "smoke test",
    )),
)


_SEED_INTENT = (

    (SEED_LOCK, (
        "همین فرم رو نگه دار", "همین رو نگه دار", "فرم رو نگه دار",
        "قفل سید", "همین سید", "همون سید",
        "keep the form", "keep the seed", "lock seed", "same seed",
    )),

    (SEED_REUSE, (
        "همون قبلی", "سید قبلی", "مثل قبل",
        "reuse seed", "previous seed",
    )),

    (SEED_REROLL, (
        "یه گزینه دیگه بده", "یه گزینه دیگه", "یکی دیگه بده", "تنوع بده",
        "دوباره بگیر", "از نو بگیر",
        "another option", "reroll", "new seed", "try again", "give me another",
    )),
)


def _match(table, haystack):

    for value, phrases in table:

        for phrase in phrases:

            if phrase in haystack:

                return value, phrase

    return None, None


def infer_quality_from_text(text):

    haystack = " ".join(str(text or "").lower().split())

    if not haystack:

        return None, None

    return _match(_QUALITY_INTENT, haystack)


def infer_seed_from_text(text):

    haystack = " ".join(str(text or "").lower().split())

    if not haystack:

        return None, None

    return _match(_SEED_INTENT, haystack)


# ----------------------------------------------------------
# RESOLUTION
# ----------------------------------------------------------

def resolve_strategy(
    user_text="",
    requested_mode=None,
    requested_profile=None,
    seed_mode=None,
    seed_value=None,
    previous_seed=None,
    render_id=None,
    resolved_mode=None,
    allow_production_profile=False,
):

    """Resolve the validated render strategy for one request.

    Returns a contract dict. `blocked` is True for a reserved mode, in
    which case the caller must refuse rather than route elsewhere.
    """

    mode = normalize_mode(requested_mode)

    # ---- reserved / unknown modes must never silently execute ----
    if mode in RESERVED_MODES:

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "blocked": True,
            "blocked_reason": "mode_not_implemented",

            "requested_mode": mode,
            "resolved_mode": None,
            "routing_source": "manual",

            "message": (
                MODE_LABELS.get(mode, mode)
                + " is not implemented yet. "
                "Available modes: Auto, Chat, Text → Image, "
                "Image → Image, Analyze Image, Plan Design."
            ),

            "active_modes": list(ACTIVE_MODES),
            "reserved_modes": list(RESERVED_MODES),
        }

    if mode != MODE_AUTO and mode not in ACTIVE_MODES:

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "blocked": True,
            "blocked_reason": "unknown_mode",

            "requested_mode": mode,
            "resolved_mode": None,
            "routing_source": "manual",

            "message": "Unknown mode: " + str(requested_mode),

            "active_modes": list(ACTIVE_MODES),
            "reserved_modes": list(RESERVED_MODES),
        }

    # ---- mode routing ----
    if mode == MODE_AUTO:

        final_mode = normalize_mode(resolved_mode) or MODE_CHAT

        routing_source = "auto"

    else:

        final_mode = mode

        routing_source = "manual"

    # ---- render profile ----
    profile_name = requested_profile

    profile_source = "explicit"

    if not profile_name or str(profile_name).strip().lower() == "auto":

        inferred, evidence = infer_quality_from_text(user_text)

        if inferred:

            profile_name = inferred

            profile_source = "chat_intent:" + str(evidence)

        else:

            profile_name = None

            profile_source = "auto"

    if profile_name:

        profile = resolve_profile(explicit=profile_name)

        if not profile.get("active"):

            profile = resolve_profile()

    else:

        profile = resolve_profile()

    if (
        profile.get("production_resolution")
        and not allow_production_profile
    ):

        # Interactive default is PREVIEW/Auto. QUALITY/FINAL must be an
        # explicit, recorded override - never automatic.
        profile = dict(profile)

        profile["requires_quality_override"] = True

    # ---- seed policy ----
    seed_resolved = resolve_seed(
        mode=seed_mode,
        seed=seed_value,
        previous_seed=previous_seed,
        render_id=render_id,
    )

    inferred_seed_mode, seed_evidence = infer_seed_from_text(user_text)

    if inferred_seed_mode and not seed_mode:

        seed_resolved = resolve_seed(
            mode=inferred_seed_mode,
            seed=seed_value,
            previous_seed=previous_seed,
            render_id=render_id,
        )

        seed_resolved["reason"] = (
            "chat_intent:" + str(seed_evidence)
        )

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "blocked": False,
        "blocked_reason": None,

        # ---- required request metadata ----
        "requested_mode": mode,
        "resolved_mode": final_mode,
        "routing_source": routing_source,

        # ---- validated render fields ONLY ----
        "render_profile": profile.get("name"),
        "profile_source": profile_source,
        "profile_contract": profile,

        "steps": profile.get("steps"),

        "preview_long_edge": profile.get("long_edge"),
        "preview_source": profile.get("preview_source"),

        "production_resolution": profile.get("production_resolution"),
        "requires_quality_override": profile.get(
            "requires_quality_override", False
        ),

        "upscale": profile.get("upscale", False),
        "quality_pass": profile.get("quality_pass", False),

        # ---- seed ----
        "seed_mode": seed_resolved.get("mode"),
        "seed": seed_resolved.get("seed"),
        "seed_policy": seed_resolved,

        # ---- guard: the controller never edits a node graph ----
        "mutates_node_graph": False,

        "allowed_fields": [
            "render_profile",
            "steps",
            "resolution_when_safe",
            "seed_policy",
            "preservation_level",
            "denoise",
            "approved_preset",
            "approved_workflow",
        ],

        "mode_label": MODE_LABELS.get(final_mode, final_mode),

        "active_modes": list(ACTIVE_MODES),
        "reserved_modes": list(RESERVED_MODES),
        "available_profiles": list(PROFILE_ORDER),
        "test_profiles": list(TEST_PROFILES),
    }


def mode_catalog():

    return {

        "contract": "RenderModeCatalogV1",
        "version": VERSION,

        "default": MODE_AUTO,

        "active": [
            {"value": m, "label": MODE_LABELS[m]}
            for m in ACTIVE_MODES
        ],

        "reserved": [
            {"value": m, "label": MODE_LABELS[m], "enabled": False}
            for m in RESERVED_MODES
        ],

        "quality": [
            {"value": "auto", "label": "Auto"},
            {"value": PROFILE_DRAFT, "label": "Draft"},
            {"value": PROFILE_PREVIEW, "label": "Preview"},
            {"value": PROFILE_QUALITY, "label": "Quality"},
            {"value": PROFILE_FINAL, "label": "Final"},
        ],

        "seed": [
            {"value": "auto", "label": "Auto"},
            {"value": SEED_LOCK, "label": "Lock"},
            {"value": SEED_REUSE, "label": "Reuse"},
            {"value": SEED_REROLL, "label": "New / Reroll"},
        ],

        "quality_override": quality_override(),
    }
