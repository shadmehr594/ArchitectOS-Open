# ==========================================================
# ArchitectOS Render Profile v1.1
#
# IMAGE_TO_IMAGE_05 — TEST BUDGET POLICY  (+ PHASE 06 LOCKED REQUIREMENT)
#
# Functional/acceptance renders must use DRAFT or PREVIEW settings.
# Production / high-resolution rendering must NEVER be used
# automatically for functional acceptance tests.
#
# Four locked profiles (see also docs/audit/…_FINAL_CLOSURE_REPORT.md):
#
#   DRAFT    smallest validated functional setting  (pipeline smoke)
#   PREVIEW  functional acceptance                 (downscaled source)
#   QUALITY  human visual review                   (full resolution)
#   FINAL    production / final delivery           (frozen baseline)
#
# Design
#   - OFF by default: production behaviour is completely unchanged.
#   - Enabled per-run via the environment (or an explicit argument), so
#     acceptance scripts opt in without touching production defaults.
#   - DRAFT/PREVIEW never run at production source resolution: the
#     source is turned into a TEMPORARY downscaled working copy by
#     `core/render/image_preview_v1.py`, and the original asset stays
#     authoritative and untouched.
#   - The workflow JSON stays frozen. Only KSampler inputs are touched.
#
# Legacy API (is_draft / draft_steps / profile / ENV_FLAG / ENV_STEPS)
# is preserved byte for byte.
# ==========================================================


from __future__ import annotations


import os


CONTRACT = "RenderDraftProfileV1"
VERSION = "1.1"


# ----------------------------------------------------------
# LEGACY ENVIRONMENT SWITCHES (unchanged)
# ----------------------------------------------------------

ENV_FLAG = "ARCHITECTOS_RENDER_DRAFT"
ENV_STEPS = "ARCHITECTOS_RENDER_DRAFT_STEPS"


DEFAULT_DRAFT_STEPS = 8

_TRUTHY = ("1", "true", "yes", "on")


# ----------------------------------------------------------
# PROFILE CONTRACT  (IMAGE_TO_IMAGE_05 / PHASE 06 LOCK)
# ----------------------------------------------------------

PROFILE_DRAFT = "DRAFT"
PROFILE_PREVIEW = "PREVIEW"
PROFILE_QUALITY = "QUALITY"
PROFILE_FINAL = "FINAL"

PROFILE_ORDER = (
    PROFILE_DRAFT,
    PROFILE_PREVIEW,
    PROFILE_QUALITY,
    PROFILE_FINAL,
)

# Profiles functional tests are allowed to use.
TEST_PROFILES = (PROFILE_DRAFT, PROFILE_PREVIEW)

# Profiles that may run at production source resolution.
PRODUCTION_PROFILES = (PROFILE_QUALITY, PROFILE_FINAL)


ENV_PROFILE = "ARCHITECTOS_RENDER_PROFILE"
ENV_PREVIEW_EDGE = "ARCHITECTOS_PREVIEW_LONG_EDGE"


# `steps` = smallest validated functional value per profile.
# `long_edge` = preview source long edge (None -> keep source size).
PROFILES = {

    PROFILE_DRAFT: {
        "steps": 4,
        "long_edge": 384,
        "purpose": "fast pipeline smoke validation",
        "production_resolution": False,
    },

    PROFILE_PREVIEW: {
        "steps": 8,
        "long_edge": 448,
        "purpose": "functional acceptance",
        "production_resolution": False,
    },

    PROFILE_QUALITY: {
        "steps": 20,
        "long_edge": None,
        "purpose": "human visual review",
        "production_resolution": True,
    },

    PROFILE_FINAL: {
        "steps": 30,
        "long_edge": None,
        "purpose": "production / final delivery",
        "production_resolution": True,
    },
}


# ----------------------------------------------------------
# SEED POLICY  (PHASE 06 LOCKED REQUIREMENT)
# ----------------------------------------------------------

SEED_LOCK = "lock"
SEED_REROLL = "reroll"
SEED_REUSE = "reuse"

SEED_MODES = (SEED_LOCK, SEED_REROLL, SEED_REUSE)

ENV_SEED_MODE = "ARCHITECTOS_RENDER_SEED_MODE"
ENV_SEED_VALUE = "ARCHITECTOS_RENDER_SEED"


# ----------------------------------------------------------
# LEGACY API  (unchanged behaviour)
# ----------------------------------------------------------

def is_draft(explicit=None):
    """True when the draft/preview profile is active."""

    if explicit is not None:

        return bool(explicit)

    return (
        str(os.environ.get(ENV_FLAG, "")).strip().lower() in _TRUTHY
    )


def draft_steps():

    try:

        value = int(
            os.environ.get(ENV_STEPS, DEFAULT_DRAFT_STEPS)
        )

    except (TypeError, ValueError):

        return DEFAULT_DRAFT_STEPS

    if value <= 0 or value > 150:

        return DEFAULT_DRAFT_STEPS

    return value


def profile(explicit=None):
    """Resolve the effective legacy draft profile for one render."""

    draft = is_draft(explicit)

    resolved = resolve_profile(explicit=None)

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "draft": draft,

        # Only meaningful when draft is active.
        "steps": draft_steps() if draft else None,

        "env_flag": ENV_FLAG,

        "note": (
            "draft/preview steps for functional validation; "
            "production quality unchanged"
        ),

        # ---- IMAGE_TO_IMAGE_05 additive ----
        "profile": resolved.get("name"),
        "profile_active": resolved.get("active"),
        "preview_source": resolved.get("preview_source"),
        "preview_long_edge": resolved.get("long_edge"),
        "production_resolution": resolved.get("production_resolution"),
        "test_profile": resolved.get("test_profile"),

    }


# ----------------------------------------------------------
# PROFILE RESOLUTION
# ----------------------------------------------------------

def is_valid_profile(name):

    return (
        isinstance(name, str)
        and name.strip().upper() in PROFILES
    )


def is_test_profile(name):

    return (
        isinstance(name, str)
        and name.strip().upper() in TEST_PROFILES
    )


def available_profiles():

    return list(PROFILE_ORDER)


def _env_long_edge():

    try:

        return int(os.environ.get(ENV_PREVIEW_EDGE))

    except (TypeError, ValueError):

        return None


def resolve_profile(explicit=None):
    """Resolve the render profile for one request.

    Precedence:
      1. explicit profile name
      2. ARCHITECTOS_RENDER_PROFILE
      3. legacy ARCHITECTOS_RENDER_DRAFT flag -> PREVIEW
      4. OFF -> production behaviour unchanged
    """

    rejected = None

    requested = explicit or os.environ.get(ENV_PROFILE)

    if requested:

        if is_valid_profile(requested):

            return _describe(requested.strip().upper(), "explicit"
                             if explicit else "env")

        rejected = str(requested)

    # ---- legacy draft flag ----
    if is_draft():

        return _describe(PROFILE_PREVIEW, "legacy_draft_flag")

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "name": None,
        "active": False,

        "steps": None,
        "long_edge": None,

        "preview_source": False,
        "production_resolution": True,

        "upscale": False,
        "quality_pass": False,

        "test_profile": False,

        "source": "default_off",
        "reason": "profile_disabled_production_unchanged",

        "rejected_explicit": rejected,

        "production_unchanged": True,

        "note": (
            "no profile active: production behaviour is byte-for-byte "
            "unchanged"
        ),
    }


def _describe(name, source):

    spec = PROFILES[name]

    long_edge = spec["long_edge"]

    if long_edge is not None:

        override = _env_long_edge()

        if override:

            long_edge = override

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "name": name,
        "active": True,

        "steps": spec["steps"],
        "long_edge": long_edge,

        "purpose": spec["purpose"],

        "preview_source": long_edge is not None,

        # DRAFT/PREVIEW must never run at production resolution.
        "production_resolution": spec["production_resolution"],

        # The frozen workflows contain no upscale node and no second
        # quality pass, so these stay false and are reported truthfully.
        "upscale": False,
        "quality_pass": False,

        "test_profile": name in TEST_PROFILES,

        "source": source,
        "reason": "profile_selected",

        "rejected_explicit": None,

        "production_unchanged": False,

        "note": (
            "functional test profile: downscaled temporary working copy, "
            "original asset untouched"
            if long_edge is not None
            else "production resolution profile"
        ),
    }


def test_profile(explicit=None):
    """The profile functional acceptance tests must use.

    Defaults to PREVIEW. Refuses to return a production profile, so a
    functional test can never accidentally request QUALITY/FINAL.
    """

    resolved = resolve_profile(explicit=explicit)

    if not resolved.get("active"):

        resolved = _describe(PROFILE_PREVIEW, "test_default")

        resolved["reason"] = "test_profile_default"

    if not resolved.get("test_profile"):

        resolved = _describe(PROFILE_PREVIEW, "test_default")

        resolved["reason"] = "production_profile_refused_for_tests"

        resolved["rejected_explicit"] = explicit

    return resolved


def assert_test_profile(resolved):

    """Guard used by harnesses: raise if a production profile is used."""

    if not isinstance(resolved, dict):

        raise ValueError("render profile contract required")

    if resolved.get("production_resolution"):

        raise ValueError(
            "production resolution profile is forbidden for functional tests"
        )

    if not resolved.get("test_profile"):

        raise ValueError(
            "functional tests must use DRAFT or PREVIEW"
        )

    return True


def quality_override(value=None):
    """Explicit quality override. OFF unless explicitly requested."""

    if value is None:

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "override": False,
            "profile": None,
            "source": "default_off",
        }

    if not is_valid_profile(value):

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "override": False,
            "profile": None,
            "source": "rejected_invalid",
            "rejected_explicit": str(value),
        }

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "override": True,
        "profile": str(value).strip().upper(),
        "source": "explicit_quality_override",
    }


# ----------------------------------------------------------
# SEED POLICY
# ----------------------------------------------------------

def resolve_seed(mode=None, seed=None, previous_seed=None, render_id=None):
    """Deterministic seed policy.

      lock   -> reuse an explicit seed exactly (reproducible)
      reroll -> derive a new deterministic seed from render_id/time
      reuse  -> reuse the previous seed in the session
    """

    requested = mode or os.environ.get(ENV_SEED_MODE)

    if requested and str(requested).strip().lower() in SEED_MODES:

        mode = str(requested).strip().lower()

    elif requested:

        mode = None

    if seed is None:

        try:

            seed = int(os.environ.get(ENV_SEED_VALUE))

        except (TypeError, ValueError):

            seed = None

    if mode is None:

        mode = SEED_LOCK if seed is not None else SEED_REROLL

    if mode == SEED_LOCK:

        resolved = seed

        reason = "explicit_seed_locked"

    elif mode == SEED_REUSE:

        resolved = previous_seed

        reason = "previous_seed_reused"

    else:

        base = render_id

        if base is None:

            import time

            base = time.time()

        resolved = int(base)

        reason = "seed_rerolled_from_render_id"

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "mode": mode,

        "seed": resolved,

        "previous_seed": previous_seed,

        "reason": reason,

        "reproducible": resolved is not None,

    }


def describe():

    return profile()
