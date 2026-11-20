# ==========================================================
# ArchitectOS Render Preset Contract v1
#
# TEXT_TO_IMAGE_COMFY_03
#
# A small, explicit Text-to-Image preset layer for the single
# canonical flux.json workflow.
#
# Design constraints (locked scope):
#   - ONE workflow file (flux.json) + controlled parameter injection.
#     No per-preset workflow JSON files.
#   - A preset may control ONLY:
#       * prompt quality tail
#       * width / height
#       * steps            (KSampler.steps - safely injectable)
#       * seed mode        (random | fixed)
#       * render context tags
#   - A preset must NEVER override user architectural content:
#       building type, facade/material request, camera request,
#       day/night request, architectural style, explicit content.
#   - Preset selection is fully DETERMINISTIC. No LLM call is made
#     to choose a preset.
#
# Explicit user request always beats the inferred default.
# ==========================================================


CONTRACT = "RenderPresetV1"
VERSION = "1.0"


# ==========================================================
# PRESET TABLE
#
# Dimensions are multiples of 64 (latent-safe) and stay close to the
# previously proven 736x704 baseline to avoid VRAM regressions.
# ==========================================================

PRESETS = {

    # ------------------------------------------------------
    # EXTERIOR
    # ------------------------------------------------------

    "exterior_day": {

        "label": "Exterior - Day",

        "width": 768,
        "height": 704,
        "steps": 20,
        "seed_mode": "random",

        "quality_tail": (
            "bright natural daylight, clear sky, soft directional shadows, "
            "photorealistic architectural exterior, sharp architectural detail"
        ),

        "tags": {
            "space": "exterior",
            "time_of_day": "day",
            "lighting": "natural",
        },
    },

    "exterior_sunset": {

        "label": "Exterior - Sunset",

        "width": 768,
        "height": 704,
        "steps": 20,
        "seed_mode": "random",

        "quality_tail": (
            "warm golden hour sunset light, long soft shadows, warm sky gradient, "
            "photorealistic architectural exterior, cinematic realistic render"
        ),

        "tags": {
            "space": "exterior",
            "time_of_day": "sunset",
            "lighting": "golden_hour",
        },
    },

    "exterior_night": {

        "label": "Exterior - Night",

        "width": 768,
        "height": 704,
        "steps": 22,
        "seed_mode": "random",

        "quality_tail": (
            "night scene, warm lit windows glowing, "
            "controlled artificial exterior lighting, architectural night photography, "
            "deep blue sky, photorealistic architectural exterior"
        ),

        "tags": {
            "space": "exterior",
            "time_of_day": "night",
            "lighting": "artificial",
        },
    },

    # T2I_TALL_TOWER_PORTRAIT_PRESET_V1 — same proven night/sampler policy,
    # with a portrait latent for an explicitly countable tall tower.  The
    # 552,960-pixel latent is only 2.27% larger than exterior_night's 540,672
    # pixels and both dimensions are latent-safe multiples of 64.
    "exterior_night_tall": {

        "label": "Exterior - Night - Tall Tower",

        "width": 576,
        "height": 960,
        "steps": 22,
        "seed_mode": "random",

        "quality_tail": (
            "night scene, warm lit windows glowing, "
            "controlled artificial exterior lighting, architectural night photography, "
            "deep blue sky, photorealistic architectural exterior"
        ),

        "tags": {
            "space": "exterior",
            "time_of_day": "night",
            "lighting": "artificial",
        },
    },

    # ------------------------------------------------------
    # INTERIOR
    # ------------------------------------------------------

    "interior_day": {

        "label": "Interior - Day",

        "width": 704,
        "height": 768,
        "steps": 20,
        "seed_mode": "random",

        "quality_tail": (
            "daylit interior space, natural daylight through large windows, "
            "soft indirect bounce light, photorealistic interior architecture, "
            "accurate material detail"
        ),

        "tags": {
            "space": "interior",
            "time_of_day": "day",
            "lighting": "natural",
        },
    },

    "interior_warm": {

        "label": "Interior - Warm",

        "width": 704,
        "height": 768,
        "steps": 20,
        "seed_mode": "random",

        "quality_tail": (
            "warm interior lighting, cozy ambient light, warm material tones, "
            "soft indirect light, photorealistic interior architecture, "
            "accurate material detail"
        ),

        "tags": {
            "space": "interior",
            "time_of_day": "evening",
            "lighting": "warm",
        },
    },

    # ------------------------------------------------------
    # CONCEPT
    # ------------------------------------------------------

    "concept_architectural": {

        "label": "Concept Architectural",

        "width": 768,
        "height": 704,
        "steps": 24,
        "seed_mode": "random",

        "quality_tail": (
            "conceptual architectural visualization, clean presentation, "
            "neutral studio lighting, design-forward composition, "
            "clear readable architectural form"
        ),

        "tags": {
            "space": "unspecified",
            "time_of_day": "neutral",
            "lighting": "studio",
        },
    },
}


# Safe default when the request is clearly an exterior facade render
# but carries no explicit time-of-day signal.
DEFAULT_PRESET = "exterior_day"


# ==========================================================
# TERMINOLOGY -> PRESET SIGNALS
#
# Consumed from the CHAT_LANGUAGE_02 deterministic terminology layer.
# ==========================================================

_NIGHT_TERMS = ("night lighting", "night render")
_SUNSET_TERMS = ("sunset lighting", "sunrise lighting")
_DAY_TERMS = ("natural lighting", "day render")
_WARM_TERMS = ("warm lighting", "soft lighting")

_INTERIOR_TERMS = (
    "interior space",
    "living room",
    "bedroom",
    "kitchen",
    "lobby",
)

_EXTERIOR_TERMS = (
    "exterior space",
    "exterior view",
    "facade",
    "south facade",
    "north facade",
    "east facade",
    "west facade",
    "main facade",
    "rear facade",
)

# Terms that mean "this is an architectural render request".
_RENDER_TERMS = (
    "architectural render",
    "photorealistic render",
    "architectural visualization",
    "3d visualization",
    "night render",
    "day render",
    "exterior view",
)


# ==========================================================
# PRESET-AWARE TAIL FILTERING  (TEXT_TO_IMAGE_COMFY_03B)
#
# The generic PromptBuilder tail is frozen and facade/lighting
# centric. It ends with "golden hour natural lighting, ..." and
# begins its facade clause with "approved facade design: ...",
# which silently overrode preset lighting / space intent.
#
# These tables let a preset make its own intent AUTHORITATIVE by
# removing ONLY conflicting generic filler segments from the
# builder tail. The compiled_render_prompt is never filtered, so
# user-requested architectural content is never suppressed.
#
# Matching is case-insensitive SUBSTRING match on a comma-separated
# builder-tail segment.
# ==========================================================

# Generic filler that is never worth sending to the model.
TAIL_NOISE = (
    "unknown",
)


# Facade / exterior-camera framing + wrong-lighting phrases.
_INTERIOR_CONFLICTS = (
    "golden hour",
    "sunset",
    "dusk",
    "twilight",
    "night",
    "evening",
    "facade",
    "exterior",
)


TAIL_CONFLICTS = {

    # clear daytime: no golden hour / dusk / night language
    "exterior_day": (
        "golden hour",
        "sunset",
        "dusk",
        "twilight",
        "night",
        "evening",
    ),

    # sunset: keep golden hour, drop bright-day and night language
    "exterior_sunset": (
        "bright day",
        "daylight",
        "midday",
        "night",
    ),

    # night: no daylight / golden hour / sunset language
    "exterior_night": (
        "daylight",
        "bright day",
        "midday",
        "golden hour",
        "sunset",
        "dusk",
    ),

    "exterior_night_tall": (
        "daylight",
        "bright day",
        "midday",
        "golden hour",
        "sunset",
        "dusk",
    ),

    # interior: no exterior camera framing, no wrong lighting
    "interior_day": _INTERIOR_CONFLICTS,

    "interior_warm": _INTERIOR_CONFLICTS,

    # neutral studio concept: nothing to filter
    "concept_architectural": (),
}


# Phrases a preset adds to make its own intent explicit. Purely
# camera / lighting framing - never architectural content.
TAIL_REINFORCEMENT = {

    "interior_day": (
        "interior architectural photography",
        "interior viewpoint",
        "camera inside the room",
        "interior composition",
    ),

    "interior_warm": (
        "interior architectural photography",
        "interior viewpoint",
        "camera inside the room",
        "interior composition",
    ),
}


def tail_conflicts(name):
    """Conflict terms to strip from the generic builder tail."""

    if not is_valid_preset(name):

        return ()

    return tuple(
        TAIL_CONFLICTS.get(name.strip(), ())
    ) + tuple(TAIL_NOISE)


def tail_reinforcement(name):
    """Preset framing phrases appended after the preset quality tail."""

    if not is_valid_preset(name):

        return ()

    return tuple(
        TAIL_REINFORCEMENT.get(name.strip(), ())
    )



# ==========================================================
# ACCESSORS
# ==========================================================

def is_valid_preset(name):

    return (
        isinstance(name, str)
        and name.strip() in PRESETS
    )


def available_presets():

    return sorted(
        PRESETS.keys()
    )


def get_preset(name):
    """Return a defensive copy of a preset definition."""

    if not is_valid_preset(name):

        return {}

    preset = PRESETS[name.strip()]

    return {

        "name": name.strip(),

        "label": preset["label"],

        "width": preset["width"],
        "height": preset["height"],
        "steps": preset["steps"],

        "seed_mode": preset["seed_mode"],
        "seed": preset.get("seed"),

        "quality_tail": preset["quality_tail"],

        "tags": dict(preset.get("tags") or {}),

    }


def build_quality_tail(name):

    if not is_valid_preset(name):

        return ""

    return PRESETS[name.strip()]["quality_tail"]


def render_params(name):
    """Only the render-affecting parameters of a preset."""

    if not is_valid_preset(name):

        return {}

    preset = PRESETS[name.strip()]

    params = {

        "width": preset["width"],
        "height": preset["height"],
        "steps": preset["steps"],
        "seed_mode": preset["seed_mode"],

    }

    if preset.get("seed") is not None:

        params["seed"] = preset["seed"]

    return params



# ==========================================================
# DETERMINISTIC INFERENCE
# ==========================================================

def _terms_set(terminology):

    if not isinstance(terminology, dict):

        return set()

    return set(
        terminology.get("canonical_terms") or []
    )


def _is_countable_tall_tower(terms, architectural_instruction):
    """True only for a user-authored, countable tall-tower composition.

    The render-instruction owner has already separated requested floor counts
    from descriptions/negations and only emits ``floor_count_framing`` when a
    complete-building countable view is applicable.  Reusing that contract
    avoids a second intent classifier and prevents an incidental number from
    changing the latent aspect ratio.
    """

    if "tower" not in terms or not isinstance(architectural_instruction, dict):
        return False

    constraints = architectural_instruction.get("constraints")

    if not isinstance(constraints, dict):
        return False

    framing_count = constraints.get("floor_count_framing")
    provenance = constraints.get("floor_count_provenance")

    if not isinstance(framing_count, int) or framing_count < 8:
        return False

    if not isinstance(provenance, dict):
        return False

    return bool(
        provenance.get("hard_constraint") is True
        and provenance.get("source") in ("USER_TEXT", "USER_CONFIRMATION")
        and provenance.get("value") == framing_count
    )


def infer_preset(terminology, architectural_instruction=None):
    """Deterministic preset inference from terminology signals only.

    Returns (preset_name, reason). preset_name may be None when the
    request carries no usable architectural/render signal.
    """

    terms = _terms_set(terminology)

    if not terms:

        return None, "no_terminology_signal"

    is_interior = bool(
        terms & set(_INTERIOR_TERMS)
    )

    is_exterior = bool(
        terms & set(_EXTERIOR_TERMS)
    )

    is_render = bool(
        terms & set(_RENDER_TERMS)
    )

    is_night = bool(
        terms & set(_NIGHT_TERMS)
    )

    is_sunset = bool(
        terms & set(_SUNSET_TERMS)
    )

    is_day = bool(
        terms & set(_DAY_TERMS)
    )

    is_warm = bool(
        terms & set(_WARM_TERMS)
    )


    # ------------------------------------------------------
    # INTERIOR
    # ------------------------------------------------------

    if is_interior:

        if is_warm:

            return "interior_warm", "interior+warm_light"

        if is_night:

            return "interior_warm", "interior+night_light"

        return "interior_day", "interior_space"


    # ------------------------------------------------------
    # EXTERIOR
    # ------------------------------------------------------

    if is_night:

        if _is_countable_tall_tower(terms, architectural_instruction):

            return "exterior_night_tall", "explicit_night+countable_tall_tower"

        return "exterior_night", "explicit_night"


    if is_sunset:

        return "exterior_sunset", "explicit_sunset"


    if is_exterior and is_day:

        return "exterior_day", "exterior+explicit_day"


    # Explicit day/night style lighting on a render request.
    if is_render and is_day:

        return "exterior_day", "render+day_light"


    if is_exterior:

        return DEFAULT_PRESET, "exterior_default"


    # ------------------------------------------------------
    # AMBIGUOUS -> safe default for render requests only
    # ------------------------------------------------------

    if is_render:

        return DEFAULT_PRESET, "render_default"


    return None, "insufficient_signal"



# ==========================================================
# CANONICAL RESOLUTION
# ==========================================================

def resolve_preset(
    terminology=None,
    explicit=None,
    architectural_instruction=None,
):
    """Resolve the preset for one render request.

    Precedence:
      1. explicit preset parameter (caller / API)
      2. deterministic inference from the user's own wording
      3. safe default for render requests
      4. none (no preset) -> generic behaviour preserved
    """

    # ------------------------------------------------------
    # 1. EXPLICIT
    # ------------------------------------------------------

    if explicit:

        if is_valid_preset(explicit):

            resolved = get_preset(explicit)

            resolved["contract"] = CONTRACT
            resolved["version"] = VERSION
            resolved["source"] = "explicit"
            resolved["reason"] = "explicit_preset_parameter"

            return resolved

        # unknown explicit preset -> fall through to inference,
        # and record that the request was rejected.
        rejected = str(explicit)

    else:

        rejected = None


    # ------------------------------------------------------
    # 2 / 3. INFERENCE
    # ------------------------------------------------------

    name, reason = infer_preset(
        terminology,
        architectural_instruction=architectural_instruction,
    )


    if not name:

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "name": None,
            "preset": None,

            "source": "none",
            "reason": reason,

            "width": None,
            "height": None,
            "steps": None,
            "seed_mode": None,
            "seed": None,

            "quality_tail": "",
            "tags": {},

            "rejected_explicit": rejected,

        }


    resolved = get_preset(name)

    resolved["contract"] = CONTRACT
    resolved["version"] = VERSION
    resolved["source"] = (
        "default" if reason.endswith("_default") else "inferred"
    )
    resolved["reason"] = reason
    resolved["rejected_explicit"] = rejected

    return resolved
