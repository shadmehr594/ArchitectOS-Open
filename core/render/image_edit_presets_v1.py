# ==========================================================
# ArchitectOS Image-Edit Preservation Levels v1
#
# IMAGE_TO_IMAGE_05
#
# Deterministic preservation/strength contract for img2img.
#
# Levels (approved ranges):
#   high_preservation -> denoise 0.20 - 0.30   (default)
#   balanced          -> denoise 0.35 - 0.45
#   creative          -> denoise 0.50 - 0.60
#
# A conversational architectural edit must NOT restructure the
# building, so the default for conversational edits is
# high_preservation.
#
# Selection is fully deterministic. No LLM call is ever made to
# choose a preservation level.
# ==========================================================


CONTRACT = "ImageEditPreservationV1"
VERSION = "1.0"


DEFAULT_LEVEL = "high_preservation"


# ----------------------------------------------------------
# LEVEL TABLE
# ----------------------------------------------------------

LEVELS = {

    "high_preservation": {
        "label": "High preservation",
        "denoise": 0.25,
        "min": 0.20,
        "max": 0.30,
        "description": (
            "keep the building form and composition, change only "
            "appearance (lighting, materials, tone)"
        ),
    },

    "balanced": {
        "label": "Balanced",
        "denoise": 0.40,
        "min": 0.35,
        "max": 0.45,
        "description": (
            "keep the overall form while allowing moderate "
            "appearance and detail changes"
        ),
    },

    "creative": {
        "label": "Creative",
        "denoise": 0.55,
        "min": 0.50,
        "max": 0.60,
        "description": (
            "allow a noticeably different interpretation while "
            "keeping the architectural subject"
        ),
    },
}


LEVEL_ORDER = (
    "high_preservation",
    "balanced",
    "creative",
)


# ----------------------------------------------------------
# DETERMINISTIC TEXT SIGNALS
# ----------------------------------------------------------

_HIGH_SIGNALS = (
    "دست نزن", "دست نزنید", "بدون تغییر", "تغییر نده", "حفظ کن", "همون بمونه",
    "همان بماند", "فقط نور", "فقط متریال", "کمی", "یه کم", "یه‌کم", "ملایم",
    "آروم", "آرام", "جزئی", "خفیف", "ساده",
    "preserve", "keep the", "keep it", "unchanged", "same form", "no change",
    "minor", "subtle", "slight", "gently", "only the",
)

_BALANCED_SIGNALS = (
    "متعادل", "متعادلانه", "معتدل", "نسبی",
    "balanced", "moderate", "medium", "mid",
)

_CREATIVE_SIGNALS = (
    "خلاقانه", "خلاق", "متفاوت", "کاملاً عوض", "کاملا عوض", "از نو", "دوباره طراحی",
    "جسورانه", "آزاد", "خیلی تغییر",
    "creative", "bold", "free", "very different", "reimagine", "from scratch",
)


def _contains_any(text, phrases):

    return [
        phrase for phrase in phrases
        if phrase in text
    ]



# ==========================================================
# ACCESSORS
# ==========================================================

def is_valid_level(name):

    return (
        isinstance(name, str)
        and name.strip() in LEVELS
    )


def available_levels():

    return list(LEVEL_ORDER)


def get_level(name):

    if not is_valid_level(name):

        return {}

    level = LEVELS[name.strip()]

    return {
        "level": name.strip(),
        "label": level["label"],
        "denoise": level["denoise"],
        "min": level["min"],
        "max": level["max"],
        "description": level["description"],
    }


def clamp_denoise(value, level=None):
    """Clamp a denoise value into the level's approved range."""

    try:

        value = float(value)

    except (TypeError, ValueError):

        return None

    bounds = LEVELS.get(level) if is_valid_level(level) else None

    if bounds is None:

        return None

    if value < bounds["min"]:

        return bounds["min"]

    if value > bounds["max"]:

        return bounds["max"]

    return round(value, 3)



# ==========================================================
# RESOLUTION
# ==========================================================

def infer_level(text):
    """Deterministic level inference. Returns (level, reason)."""

    lowered = " ".join(str(text or "").lower().split())

    if not lowered:

        return DEFAULT_LEVEL, "default_conversational_edit"

    if _contains_any(lowered, _CREATIVE_SIGNALS):

        return "creative", "creative_signal"

    if _contains_any(lowered, _HIGH_SIGNALS):

        return DEFAULT_LEVEL, "preservation_signal"

    if _contains_any(lowered, _BALANCED_SIGNALS):

        return "balanced", "balanced_signal"

    # conversational architectural edits default to preserving form
    return DEFAULT_LEVEL, "default_conversational_edit"


def resolve_preservation(text=None, explicit=None):
    """Resolve the preservation contract for one img2img request.

    Precedence:
      1. explicit level
      2. explicit denoise value (clamped into its level range)
      3. deterministic inference from the user's wording
      4. default conversational edit -> high_preservation
    """

    rejected = None


    # ---- explicit level ----
    if explicit:

        if is_valid_level(explicit):

            resolved = get_level(explicit)

            resolved.update({
                "contract": CONTRACT,
                "version": VERSION,
                "source": "explicit_level",
                "reason": "explicit_preservation_parameter",
                "explicit_denoise": None,
            })

            return resolved

        rejected = str(explicit)


    # ---- inference ----
    level, reason = infer_level(text)

    resolved = get_level(level)

    resolved.update({
        "contract": CONTRACT,
        "version": VERSION,
        "source": (
            "default" if reason.startswith("default") else "inferred"
        ),
        "reason": reason,
        "rejected_explicit": rejected,
        "explicit_denoise": None,
    })

    return resolved


def resolve_preservation_with_denoise(
    text=None,
    explicit=None,
    denoise=None
):
    """As resolve_preservation, plus an optional explicit denoise.

    An explicit denoise is clamped into the resolved level's approved
    range, so the level contract can never be violated.
    """

    resolved = resolve_preservation(text=text, explicit=explicit)

    if denoise is None:

        return resolved

    clamped = clamp_denoise(denoise, resolved.get("level"))

    if clamped is None:

        return resolved

    resolved["denoise"] = clamped

    resolved["explicit_denoise"] = clamped

    resolved["source"] = resolved.get("source", "inferred") + "+denoise"

    return resolved
