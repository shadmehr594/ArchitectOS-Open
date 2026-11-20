# ==========================================================
# ArchitectOS Image Edit Delta Compiler v1
#
# IMAGE_TO_IMAGE_05 — PROMPT / DELTA AUTHORITY
#
# Problem it fixes
#   A conversational edit such as "همینو شب کن" (make this night)
#   was reaching ComfyUI as the generic img2img builder prompt,
#   which is a TEXT-TO-IMAGE facade/DAYLIGHT template
#   ("... Professional archviz render. Natural lighting.").
#   The user's requested delta either never entered the prompt or was
#   immediately contradicted by that generic tail, so the rendered
#   result stayed a daylight image.
#
# Resolution rule (approved IMAGE_TO_IMAGE_05 contract)
#   For an img2img EDIT the USER EDIT DELTA is authoritative.
#   The compiled prompt is composed in four explicit sections:
#
#       REFERENCE : what must be preserved from the source image
#       DELTA     : the exact appearance change the user asked for
#       PRESERVE  : the hard "do not redesign" constraints
#       QUALITY   : a bounded render-quality tail
#
#   In addition the compiler returns `conflict_terms`: deterministic
#   substrings that let the existing preset-tail filter remove the
#   generic builder-tail segments that directly contradict the delta
#   (for example "natural lighting" for a night edit, or a different
#   facade material for a material edit).
#
# Fully deterministic. No LLM call, no provider, no render.
# ==========================================================


from __future__ import annotations

import re


CONTRACT = "ImageEditDeltaV1"
VERSION = "1.0"


# ----------------------------------------------------------
# EDIT CLASSES
# ----------------------------------------------------------

EDIT_TIME_OF_DAY = "time_of_day_change"
EDIT_MATERIAL = "material_change"
EDIT_LIGHTING = "lighting_change"
EDIT_COLOR = "color_change"
# KNOWLEDGE_RUNTIME_CONNECTION_V2 — a recognised architectural style change is
# its own edit class. It was previously unrecognised here, so a style-only
# request compiled to `generic_edit` and fell back to plain img2img instead of
# the existing global Kontext edit route.
EDIT_STYLE = "style_change"
EDIT_GENERIC = "generic_edit"


TIME_NIGHT = "night"
TIME_DAY = "day"
TIME_SUNSET = "sunset"
TIME_SUNRISE = "sunrise"

# V4.3A — M4. The audit measured `morning`, `noon` and `dusk` as
# unclassified, so those requests silently fell back to the generic daylight
# builder tail ("golden hour natural lighting"). They are distinct
# illumination states, not aliases: morning is not golden hour, and noon is
# not sunrise. Each gets its own value, delta text and conflict set.
TIME_MORNING = "morning"
TIME_NOON = "noon"
TIME_DUSK = "dusk"


# ----------------------------------------------------------
# SIGNAL TABLES  (Persian colloquial + English)
# ----------------------------------------------------------

_NIGHT_SIGNALS = (
    "شب کن", "شبش کن", "شب بشه", "شب شه", "شبانه کن", "شبانه",
    "حالت شب", "زمان شب", "رندر شب", "نمای شب", "نور شب", "در شب",
    # V4.3A — M4: "شب رندر کن" (night-render, verb after the noun) and the
    # bare prepositional form were not matched by any existing signal.
    "شب رندر", "شب باشد", "را شب",
    "night", "nighttime", "night time", "night scene", "make it night",
)

_DAY_SIGNALS = (
    "روز کن", "روزش کن", "روز بشه", "روز شه", "حالت روز", "زمان روز",
    "رندر روز", "نمای روز", "در روز", "طی روز", "در طول روز",
    "روشنایی روز",
    "daytime", "daylight", "make it day", "day scene", "bright day",
)

_SUNSET_SIGNALS = (
    "غروب", "sunset", "golden hour",
)

_SUNRISE_SIGNALS = (
    "طلوع", "sunrise",
)

# V4.3A — M4. Deliberately narrow: "morning" never reaches the sunset or
# sunrise tables, and "noon" is never treated as sunrise.
#
# The bare word "morning" is NOT a signal on its own: "good morning" is a
# greeting, and after any render a false time-of-day delta would turn that
# greeting into an image edit. Only an explicit time construction matches.
_MORNING_SIGNALS = (
    "in the morning", "at morning", "this morning", ", morning",
    "morning light", "morning sun", "morning sky",
    "نور صبح", "هنگام صبح", "در صبح", "صبح زود", "صبح کن", "صبح بشه",
    "صبح شه", "بامداد",
)

_NOON_SIGNALS = (
    "at noon", "high noon", "noon light", "noon sun", "midday light",
    "midday sun", ", noon",
    "نور ظهر", "هنگام ظهر", "در ظهر", "ظهر کن", "ظهر بشه", "ظهر شه",
    "نیمروز",
)

_DUSK_SIGNALS = (
    "گرگ‌ومیش", "گرگ و میش", "گرگ‌ و میش", "dusk", "twilight", "blue hour",
)


_TIME_OF_DAY_SIGNAL_GROUPS = (
    (TIME_NIGHT, _NIGHT_SIGNALS),
    (TIME_DUSK, _DUSK_SIGNALS),
    (TIME_SUNSET, _SUNSET_SIGNALS),
    (TIME_SUNRISE, _SUNRISE_SIGNALS),
    (TIME_MORNING, _MORNING_SIGNALS),
    (TIME_NOON, _NOON_SIGNALS),
    (TIME_DAY, _DAY_SIGNALS),
)

# Bare state names are valid only after an explicit destination or contrast
# marker.  Keeping them out of the ordinary signal tables prevents source
# descriptions and greetings from becoming edits.  In a source-to-target
# construction Persian ``غروب`` denotes the requested dusk/evening state;
# the established standalone ``غروب`` signal remains TIME_SUNSET.
_DIRECTIONAL_TIME_TERMS = (
    (TIME_NIGHT, ("night time", "nighttime", "midnight", "night", "شب")),
    (TIME_DAY, ("daylight", "daytime", "day", "روز")),
    (TIME_DUSK, (
        "گرگ و میش", "گرگ‌ومیش", "گرگ‌ و میش", "blue hour",
        "twilight", "evening", "dusk", "غروب",
    )),
    (TIME_SUNSET, ("golden hour", "sunset")),
    (TIME_SUNRISE, ("sunrise", "طلوع")),
    (TIME_MORNING, ("morning", "صبح")),
    (TIME_NOON, ("midday", "noon", "ظهر")),
)

_TIME_CLAUSE_BOUNDARY_RE = re.compile(r"[،,;؛.!?؟\n]")
_TIME_TARGET_MARKER_RE = re.compile(
    r"(?:(?<![\w‌])به(?![\w‌])|(?<![a-z0-9])(?:into|to)(?![a-z0-9]))"
)
_TIME_CONTRAST_MARKER_RE = re.compile(
    r"(?:(?<![\w‌])بلکه(?![\w‌])|(?<![a-z0-9])but(?![a-z0-9]))"
)
_TIME_TRANSFORM_ACTIONS = (
    "تبدیل", "تغییر", "کن", "بده", "convert", "turn", "change", "make",
)
_TIME_SOURCE_CONTEXT_MARKERS = (
    "تصویر فعلی", "عکس فعلی", "تصویر منبع", "وضعیت فعلی",
    "current image", "source image", "existing image", "currently",
)

#: LIGHTING_QUALITY — a time word acting as a MODIFIER of an illumination
#: noun. "daylight illumination" is the light in the photograph; "daytime" on
#: its own is a destination state. Only the modifier form is context.
_TIME_ILLUMINATION_QUALIFIER_RE = re.compile(
    r"\b(?:daylight|daytime|sunlight|moonlight|night)\s+"
    r"(?:illumination|lighting|light|exposure|balance|quality|tone|"
    r"colou?r|temperature)\b"
    r"|نور\s*روز"
    r"|روشنایی\s*روز",
    re.IGNORECASE,
)


# (canonical material, (patterns...), (english prompt nouns...))
#
# KNOWLEDGE_RECOVERY_01 — the canonical names are the identifiers used by
# the existing material ontology (core/architecture/knowledge/
# material_ontology.json: travertine, marble, fire_brick, red_brick,
# natural_stone, stone, brick, ...). Specific entries are listed before the
# generic head nouns they are built on.
_MATERIALS = (
    ("travertine", ("تراورتن", "travertine"), "travertine stone"),
    ("marble", ("مرمر", "marble"), "marble"),
    ("natural_stone", ("سنگ طبیعی", "natural stone"), "natural stone"),
    ("fire_brick", ("آجر نسوز", "نسوز", "fire brick", "firebrick",
                    "refractory brick"), "fire resistant brick"),
    ("red_brick", ("آجر قرمز", "red brick"), "red brick"),
    ("stone", ("سنگ", "stone"), "natural stone"),
    ("wood", ("چوب", "ترمووود", "wood", "timber"), "wood"),
    ("glass", ("شیشه", "glass"), "glass"),
    ("brick", ("آجر", "brick"), "brick"),
    ("concrete", ("بتن", "concrete"), "concrete"),
    ("metal", ("فلز", "metal", "steel"), "metal"),
)

#: Persian material names are HEAD-INITIAL COMPOUNDS: a generic head noun
#: ("سنگ", "آجر") followed by the specific modifier ("تراورتن", "نسوز",
#: "قرمز"). A pure position rule therefore selects the generic head noun
#: ("سنگ تراورتن" -> stone) instead of the material the user named.
#:
#: These compounds are resolved first and their spans are consumed, which is
#: the same precedence the existing Persian architectural understanding
#: module already uses (`persian_architectural_understanding._match_lexicon`
#: consumes matched spans in table order). Canonical names are existing
#: ontology identifiers; no new material vocabulary is introduced.
_MATERIAL_COMPOUNDS = (
    ("travertine", ("سنگ تراورتن", "تراورتن سنگ")),
    ("marble", ("سنگ مرمر",)),
    ("natural_stone", ("سنگ طبیعی", "سنگ ساختمانی")),
    ("fire_brick", ("آجر نسوز نما", "آجر نسوز")),
    ("red_brick", ("آجر قرمز نما", "آجر قرمز")),
)

#: The NEW material follows these markers. Used only to disambiguate WHICH
#: mention is the requested material; it never adds or renames a material.
_REPLACEMENT_TARGET_MARKERS = (
    " به ", "با ", " to ", " into ", " with ", " as ",
    " به", "با",
)

#: The OLD (replaced) material follows these markers, so the requested
#: material is the part BEFORE them ("use wood instead of stone").
_REPLACEMENT_SOURCE_MARKERS = (
    "به جای", "به‌جای", "جای ", "instead of", "in place of", " from ",
)

# Material words that must be treated as CONFLICTING when a different
# material is requested (so the generic tail cannot override the delta).
_MATERIAL_CONFLICT_WORDS = {
    "stone": ("wood", "concrete", "glass facade", "brick", "metal",
              "travertine", "aluminum", "copper"),
    "travertine": ("wood", "concrete", "glass facade", "brick", "metal",
                   "aluminum", "copper"),
    "marble": ("wood", "concrete", "glass facade", "brick", "metal",
               "aluminum", "copper"),
    "natural_stone": ("wood", "concrete", "glass facade", "metal",
                      "aluminum", "copper"),
    "fire_brick": ("wood", "concrete", "glass facade", "metal",
                   "travertine", "aluminum", "copper"),
    "red_brick": ("wood", "concrete", "glass facade", "metal",
                  "travertine", "aluminum", "copper"),
    "wood": ("concrete", "glass facade", "brick", "metal", "travertine",
             "aluminum", "copper"),
    "glass": ("wood", "concrete", "brick", "metal", "travertine",
              "aluminum", "copper"),
    "brick": ("wood", "concrete", "glass facade", "metal", "travertine",
              "aluminum", "copper"),
    "concrete": ("wood", "glass facade", "brick", "metal", "travertine",
                 "aluminum", "copper"),
    "metal": ("wood", "concrete", "glass facade", "brick", "travertine",
              "aluminum", "copper"),
}


_TONE_LIGHT_SIGNALS = (
    "روشن", "روشن‌تر", "روشن تر", "light", "lighter", "light-coloured",
    "light colored",
)

_TONE_DARK_SIGNALS = (
    "تیره", "تیره‌تر", "تیره تر", "تیه", "dark", "darker",
)


_BRIGHTER_SIGNALS = (
    "روشن کن", "روشنش کن", "روشن‌تر کن", "روشن تر کن", "نور بیشتر",
    "نورش رو زیاد", "brighter", "more light", "brighten",
)

_DARKER_SIGNALS = (
    "تیره کن", "تیره‌تر کن", "تیره تر کن", "تیه کن", "کم نور", "نور کم",
    "darker", "dim the", "less light", "darker lighting",
)

_COLOR_SIGNALS = (
    "رنگ", "color", "colour", "رنگش",
)


# ----------------------------------------------------------
# LIGHTING QUALITY (R4_POSITIVE_INSTRUCTION_CONTRACT_V1)
#
# `EDIT_LIGHTING` used to express illumination INTENSITY only: `_BRIGHTER_
# SIGNALS` / `_DARKER_SIGNALS` answer "how much light". A request for warmer or
# more natural light answers a different question — "what kind of light" — and
# the two are not interchangeable: "warmer" is not "brighter".
#
# Measured consequence of the missing axis: the accepted R4 request
#   «نور روز این تصویر ساختمان را کمی گرم‌تر و طبیعی‌تر کن»
# compiled to `generic_edit`, so the delta was empty, the user's preservation
# clause was dropped, and the img2img fallback prompt (a facade-transformation
# template) became the only instruction. The user asked for light and the
# engine was asked for a facade.
#
# This is NOT a new top-level edit class. It is one additional axis inside the
# existing `lighting_change` contract, exactly as intensity already is.
#
# GOVERNANCE RULE: a quality signal only counts when an ILLUMINATION NOUN
# governs the same clause. That is what keeps these apart:
#   «آجر را گرم‌تر کن»      -> material/colour, not light  (material wins first)
#   «رنگ نما را گرم‌تر کن»  -> colour, not light           (no lighting noun)
#   «نور را گرم‌تر کن»      -> lighting quality            (lighting noun present)
# ----------------------------------------------------------

LIGHTING_QUALITY_WARMER = "warmer"
LIGHTING_QUALITY_COOLER = "cooler"
LIGHTING_QUALITY_NATURAL = "more_natural"

_LIGHTING_QUALITY_ORDER = (
    LIGHTING_QUALITY_WARMER,
    LIGHTING_QUALITY_COOLER,
    LIGHTING_QUALITY_NATURAL,
)

#: The governor. A quality word outside a clause containing one of these is a
#: material or colour request and must not be captured here.
_LIGHTING_NOUNS = (
    "نور", "روشنایی", "نورپردازی", "نوردهی", "نورده", "روشنایی روز",
    "lighting", "illumination", "light", "daylight",
)

#: Warmth. Deliberately excludes the bare «گرم» / "warm": «هوای گرم» and
#: "warm welcome" are not lighting requests, and the comparative form is what
#: a user actually writes when asking for a change.
_LIGHTING_WARM_SIGNALS = (
    "گرم‌تر", "گرم تر", "گرمتر", "گرم‌ترش", "گرمایش نور",
    "دمای رنگ گرم", "دمای رنگش را گرم",
    "warmer", "warm the light", "warm light", "warmer light",
    "warm colour temperature", "warm color temperature",
    "warmer colour temperature", "warmer color temperature",
)

_LIGHTING_COOL_SIGNALS = (
    "سردتر", "سرد تر", "سردترش", "دمای رنگ سرد",
    "cooler", "cool the light", "cool light", "cooler light",
    "cool colour temperature", "cool color temperature",
    "cooler colour temperature", "cooler color temperature",
)

#: Naturalness. «طبیعی‌تر» is a lighting-quality request only under a lighting
#: noun; «سنگ طبیعی» is a material and is claimed by the material class first.
_LIGHTING_NATURAL_SIGNALS = (
    "طبیعی‌تر", "طبیعی تر", "طبیعیتر", "طبیعی‌ترش",
    "more natural", "natural daylight", "more natural daylight",
    "natural light balance", "natural exposure",
)

#: Clauses are bounded the same way the rest of this module bounds them.
_LIGHTING_CLAUSE_RE = re.compile(r"[،,;؛.!?؟\n]+")


def _lighting_quality(haystack):

    """Return (quality, hits) for an illumination-QUALITY request.

    Deterministic and clause-scoped. Returns (None, []) when no illumination
    noun governs the quality word, so material and colour requests are never
    captured here. Warmth outranks coolness outranks naturalness when a clause
    carries more than one, because warmth is the more specific instruction.
    """

    for clause in _LIGHTING_CLAUSE_RE.split(haystack):

        if not clause:

            continue

        if not any(noun in clause for noun in _LIGHTING_NOUNS):

            continue

        for quality, signals in (
            (LIGHTING_QUALITY_WARMER, _LIGHTING_WARM_SIGNALS),
            (LIGHTING_QUALITY_COOLER, _LIGHTING_COOL_SIGNALS),
            (LIGHTING_QUALITY_NATURAL, _LIGHTING_NATURAL_SIGNALS),
        ):

            hits = _hits(clause, signals)

            if hits:

                return quality, hits

    return None, []


# ----------------------------------------------------------
# COLOUR VOCABULARY
#
# I2I_INSTRUCTION_FIDELITY_V1
#
# `_COLOR_SIGNALS` detects only the CONCEPT of colour, so a
# colour request used to compile to a directionless delta
# ("adjust the colour palette") and the requested target colour
# never entered the prompt. This table resolves WHICH colour, so
# the delta can state the requested change explicitly - the same
# contract the time-of-day and material classes already honour.
#
# Shape mirrors `_MATERIALS`: (canonical, patterns, english).
# This is a general vocabulary - no colour, surface or image is
# special-cased.
# ----------------------------------------------------------

_COLOURS = (
    ("white", ("سفید", "white"), "white"),
    ("black", ("سیاه", "مشکی", "black"), "black"),
    ("grey", ("خاکستری", "طوسی", "gray", "grey"), "grey"),
    ("beige", ("کرم", "بژ", "beige", "cream"), "beige"),
    ("brown", ("قهوه‌ای", "brown"), "brown"),
    ("red", ("قرمز", "سرخ", "red"), "red"),
    ("orange", ("نارنجی", "orange"), "orange"),
    ("yellow", ("زرد", "yellow"), "yellow"),
    ("green", ("سبز", "green"), "green"),
    ("turquoise", ("فیروزه‌ای", "turquoise"), "turquoise"),
    ("blue", ("آبی", "blue"), "blue"),
    ("purple", ("بنفش", "purple"), "purple"),
    ("pink", ("صورتی", "pink"), "pink"),
    ("silver", ("نقره‌ای", "نقره", "silver"), "silver"),
    ("golden", ("طلایی", "golden"), "golden"),
    ("bronze", ("برنزی", "bronze"), "bronze"),
)

# Generic builder-tail segments that contradict a directional
# colour change. The existing preset-tail filter removes them.
_COLOR_CONFLICT_TERMS = (
    "natural lighting",
    "improve facade appearance",
    "keeping the existing architectural identity",
)


# ----------------------------------------------------------
# FIXED SECTIONS
# ----------------------------------------------------------

_REFERENCE = (
    "REFERENCE: preserve the existing building identity, massing, "
    "camera angle, framing, composition and all major openings exactly "
    "as in the source image"
)

_PRESERVE = (
    "PRESERVE: do not redesign the building, do not change the volume, "
    "floor count, wall positions, roof shape, openings or structural "
    "layout"
)

# NEOCLASSICAL_FINAL_PROMPT_CONSISTENCY_V1 — PROBLEM B.
#
# "do not redesign the building" is ambiguous for a source-preserving facade
# redesign: the user asked exactly for a new architectural expression ON the
# existing building. The sentence now names WHICH thing must not be redesigned
# (the primary structure) instead of forbidding the redesign the user asked
# for. Emitted only when the delta carries a real style, so a material-only,
# lighting, colour or removal delta keeps the original wording byte for byte.
_PRESERVE_DESIGN = (
    "PRESERVE: redesign the architectural EXPRESSION of the existing facade "
    "only; do not redesign or reconstruct the primary building structure — "
    "keep the massing, floor count, structural frame, wall positions, roof "
    "shape, opening layout and camera perspective"
)

_QUALITY = (
    "QUALITY: photorealistic architectural visualization, high detail "
    "realistic materials, professional archviz render"
)


# ----------------------------------------------------------
# DELTA TEXTS
# ----------------------------------------------------------

_DELTA_TIME_OF_DAY = {

    # ARCHITECTURAL_NIGHT_EXPOSURE_V1 — the night delta used to describe only
    # the ENVIRONMENT (dark sky, no daylight, deep shadows) and the LIGHT
    # SOURCES (interior glow, exterior landscape lighting). It never stated
    # that the architectural subject must stay readable, while `TIME_DAY` did
    # ("sunlit facade"). Measured consequence: a scene that is correctly
    # nighttime but professionally underexposed — facade at luma 1-2/255,
    # 30 % of the frame at pure black, only the windows visible.
    #
    # A dark sky does not require a black building. Night ENVIRONMENT and
    # subject VISIBILITY are complementary requirements, so the night delta
    # now carries both. This is the general contract for architectural night
    # relighting, not a value chosen for any particular image.
    # NIGHT_FACADE_LIGHTING_V1 — the visibility clause added above still
    # failed on GPU (facade luma 1.2/255, and the measured tensor placed the
    # SKY at 2.63/255 ABOVE the facade at 1.26/255). Reading the wording back
    # explains why: it described the requirement as an evaluation
    # ("remain clearly readable"), softened it ("subtle", "fill light"), and
    # named exactly one light source — the windows. A diffusion model renders
    # the sources it is given, so it produced glowing windows and an unlit
    # mass. The delta now states the LIGHTING CONDITION as a visible scene:
    # a dark sky, an exterior that is lit and therefore brighter than that
    # sky, and warm interior light as a secondary source. Still fixture-free
    # (ambient night light plus window spill), still no building-specific
    # noun, still no geometry.
    #
    # R3_NIGHT_MATERIAL_FIDELITY_CPU_V1 — GPU evidence (R3-NIGHT-02, output
    # `architectos_kontext_edit_00012_.png`) showed the building survived but
    # the brick did not: the wall was re-rendered as a high-chroma speckled
    # mosaic (facade chroma sigma 5.92 -> 14.55, saturation sigma 29.1 ->
    # 85.6, local contrast 30.6 -> 52.4). Two wording defects are visible in
    # the instruction itself, independently of any model hypothesis:
    #
    #   1. "clearly visible AND EVENLY LIT" literally requested uniform, flat
    #      illumination of the whole elevation — and the output was flatly
    #      lit. Replaced by controlled local lighting with gentle falloff and
    #      an explicit "without being uniformly lit".
    #   2. Material preservation said only "keeps its real material colour
    #      and surface texture". It never forbade RE-RENDERING the wall's
    #      units, and never named cladding, recolouring, saturation or
    #      growth — the four things the output actually did. Those
    #      prohibitions are now explicit and unit-level.
    #
    # The clause stays BUILDING-AGNOSTIC on purpose. `_DELTA_TIME_OF_DAY` is
    # the general night contract for any facade, and the accepted
    # `ARCHITECTURAL_NIGHT_EXPOSURE_V1` suite forbids building-specific nouns
    # here (no "brick", no "villa", no "portico"). Naming brick would fix this
    # one image and mis-instruct every concrete, glass or metal facade. When a
    # source's observed material is available, the decision block's
    # `fixed_elements` is the correct place to name it — not this contract.
    #
    # Neither change is claimed to fix the render. Only a supervised GPU
    # comparison can settle that.
    TIME_NIGHT: (
        "DELTA: convert the scene to true architectural night "
        "photography, dark night sky, no daylight. The building exterior is "
        "lit by real ambient night light and by controlled local "
        "architectural lighting with gentle falloff, and by warm light "
        "spilling from the windows, so the illuminated exterior is clearly "
        "brighter than the sky: the facade keeps its real material colour, "
        "its surface texture, its coursing and the appearance of each "
        "individual unit exactly as photographed, and no new cladding, "
        "recolouring, saturation boost, staining or growth is added to the "
        "walls; the roof, walls, columns and entrance stay clearly visible "
        "without being uniformly lit, and shadows are soft and open rather "
        "than crushed to black. Warm interior lighting glows through the "
        "existing windows only, with realistic nighttime exposure and the "
        "look of a long-exposure architectural photograph."
    ),

    TIME_DAY: (
        "DELTA: convert the scene to bright architectural daylight "
        "photography, clear blue daytime sky, soft natural daylight, "
        "sunlit facade, soft directional shadows, realistic daytime "
        "exposure, no night lighting"
    ),

    TIME_SUNSET: (
        "DELTA: convert the scene to warm golden-hour architectural "
        "photography, warm low sun, long soft shadows, warm sky gradient, "
        "cinematic realistic exposure"
    ),

    TIME_SUNRISE: (
        "DELTA: convert the scene to soft early-morning architectural "
        "photography, cool clear dawn sky, low warm sunlight, long soft "
        "shadows, realistic exposure"
    ),

    # V4.3A — M4. Morning is NOT golden hour: cooler, higher-contrast, fresher
    # light with a pale sky, and no warm low sun.
    TIME_MORNING: (
        "DELTA: convert the scene to crisp morning architectural photography, "
        "pale clear morning sky, fresh low-angle daylight, cool clean air, "
        "crisp long soft shadows, realistic exposure"
    ),

    # V4.3A — M4. Noon is NOT sunrise: the sun is high and the shadows are
    # short and hard.
    TIME_NOON: (
        "DELTA: convert the scene to high-noon architectural photography, "
        "high overhead sun, short hard shadows, bright clear blue sky, "
        "even full daylight, realistic exposure"
    ),

    # V4.3A — M4. Dusk is the blue hour after sunset: the warm horizon has
    # faded, artificial light is just starting.
    TIME_DUSK: (
        "DELTA: convert the scene to blue-hour architectural photography, "
        "deep blue twilight sky, fading warm horizon glow, interior and "
        "street lighting beginning to glow, soft low-contrast shadows, "
        "realistic exposure"
    ),
}


# ARCHITECTURAL_NIGHT_EXPOSURE_V1 — the night delta BEFORE subject-visibility
# was part of the contract. Kept verbatim because it is still the correct
# instruction for one legitimate request class: a user who explicitly asks for
# a minimally lit night image where only the windows read. Intentionally dark
# scenes must stay dark when they are asked for.
_DELTA_TIME_OF_DAY_NIGHT_MINIMAL = (
    "DELTA: convert the scene to true architectural night photography, "
    "dark night sky, interior architectural lighting illuminated and "
    "glowing through the windows, exterior landscape lighting, realistic "
    "nighttime exposure, deep shadows, no daylight"
)


# MOONLIT_NIGHT_V1 — the moonlit night contract.
#
# Selected only when the request grounds the scene in moonlight
# (`_moonlit`), never for a generic night request. It keeps every guarantee of
# the ordinary night delta — dark sky, no daylight, readable subject, warm
# interior — and adds the one thing the night delta could not express: a NAMED
# illuminant that reaches the exterior.
#
# MOONLIGHT_DIRECTION_V1 — two corrections after the first real render:
#
#   1. The previous text said the moonlight "falls across the exterior", which
#      states no RELATIONSHIP between the light, the camera and the surfaces.
#      Measured result: the camera-facing facade stayed at 4.4/255 while the
#      SKY rose to 7.4/255 — the model lit the sky, not the building. The
#      contract now names the direction photographically: front-lit, from an
#      elevated front-quarter, from behind the camera, falling directly on the
#      camera-facing surfaces.
#   2. "from a high clear moon" invited the model to DRAW a moon disc above the
#      roofline, which is not part of the building and was never requested. The
#      illuminant is now stated without requiring a visible moon, and the moon
#      is explicitly placed outside the frame.
#
# The abstract claim "brighter than the sky" was dropped: it is an OUTCOME, the
# model did not obey it, and a stated CAUSE (directional front light) is the
# instruction a diffusion model can actually act on.
#
# Deliberately fixture-free (a moon is not a fixture), element-generic (no
# building-specific noun, no material name), and geometry-free.
_DELTA_TIME_OF_DAY_MOONLIT = (
    "DELTA: convert the scene to a realistic moonlit architectural night "
    "photograph, deep navy-blue dark night sky, no daylight, no sunset "
    "glow. The scene is front-lit by soft cool moonlight arriving from an "
    "elevated front-quarter direction behind the camera, so the moonlight "
    "falls directly on the camera-facing surfaces: the facade, roof, walls, "
    "columns and entrance are lit and clearly readable, with their real "
    "material colour and surface texture. The shadows are soft, directional "
    "and natural, neither washed out nor crushed to black. The moon itself "
    "stays outside the frame and is not visible in the image. Warm interior "
    "lighting glows through the windows as a secondary source, with "
    "realistic nighttime exposure and the look of a long-exposure "
    "architectural photograph."
)


#: Bounded vocabulary for "I really do want this almost black".
#:
#: Only phrases that ask for MINIMAL illumination of the building itself
#: qualify. A bare "dark" or "very dark night" does NOT: those describe the
#: environment, which is what the default night delta already delivers.
_EXPLICIT_MINIMAL_ILLUMINATION_SIGNALS = (
    "almost black", "nearly black", "pitch black",
    "only the windows", "only its windows", "windows only",
    "no exterior lighting", "without exterior lighting",
    "unlit facade", "facade in darkness",
    "تقریبا سیاه", "تقریباً سیاه",
    "کاملا تاریک", "کاملاً تاریک",
    "فقط پنجره", "فقط پنجره ها",
    "بدون نور بیرونی", "نور بیرونی نداشته باشد",
    "نما در تاریکی",
)


def _explicit_minimal_illumination(haystack):
    """True when the request explicitly asks for a minimally lit building."""

    text = str(haystack or "")

    variants = (text, text.replace("\u200c", " "))

    return any(
        signal in variant
        for signal in _EXPLICIT_MINIMAL_ILLUMINATION_SIGNALS
        for variant in variants
    )


# MOONLIT_NIGHT_V1 — a moonlit night is a DIFFERENT lighting condition from a
# generic night, not a stronger wording of it. It names an illuminant: a single
# distant, cool, directionless source that lights every exterior surface. That
# is why it can make a facade readable without inventing a fixture, and why the
# generic night delta (which names only the windows) kept collapsing to a
# silhouette.
#
# The vocabulary is bounded and grounded: only an explicit moon reference
# qualifies. "Dark", "night" or "evening" alone must never select it, or every
# ordinary night request would be silently upgraded.
_MOONLIT_SIGNALS = (
    # English
    "moonlit", "moon light", "moonlight",
    "under the moon", "under a full moon", "under moonlight",
    "by moonlight", "in the moonlight", "moonlit night", "moonlit sky",
    # Persian — "مهتاب" is moonlight; "مهتابی" is moonlit
    "شب مهتابی", "مهتابی", "مهتاب",
    "نور مهتاب", "نور ماه", "زیر نور ماه", "شب با نور ماه",
    "روشنایی ماه", "نور ملایم ماه", "نور سرد ماه",
)

#: A request that explicitly asks for an almost-black building outranks a
#: moon reference: the darkness override stays authoritative.


def _moonlit(haystack):
    """True when the request grounds the scene in moonlight."""

    text = str(haystack or "")

    variants = (text, text.replace("\u200c", " "))

    return any(
        signal in variant
        for signal in _MOONLIT_SIGNALS
        for variant in variants
    )


#: MOONLIT_NIGHT_V1 — bounded vocabulary for "this material is being
#: PRESERVED, not replaced".
#:
#: The defect this repairs: `_detect_material` runs before time-of-day and
#: treats any material noun as a replacement request, so "make the brick
#: building moonlit, preserving its brick facade" compiled to a cladding
#: replacement. A material named inside a preservation statement is a
#: CONSTRAINT, not an instruction to repaint.
#:
#: Only explicit preservation phrasing qualifies. A bare material noun never
#: does, so genuine material-change requests are untouched.
_MATERIAL_PRESERVATION_SIGNALS = (
    # English
    "without changing its material", "without changing its materials",
    "without changing the material", "without changing the materials",
    "without changing materials", "without changing material",
    "do not change its material", "do not change the material",
    "do not change materials", "do not change the materials",
    "keep the material", "keep its material",
    "keep the materials", "keep its materials",
    "keep the facade brick", "keep the brick", "keep its brick",
    "preserve the material", "preserve its material",
    "preserve the materials", "preserve its materials",
    "preserve the brick", "preserve its brick", "preserving its brick",
    "preserve the facade material", "preserve facade material",
    "materials preserved", "material preserved",
    "same materials", "same material",
    "existing materials", "existing material",
    "original materials", "original material",
    "material unchanged", "materials unchanged",
    # Persian — "حفظ" is preserve
    "مصالح حفظ", "متریال حفظ", "آجر نما حفظ", "آجر حفظ",
    "نما حفظ شود", "حفظ شود", "حفظ بماند", "حفظ گردد", "حفظ شوند",
    "بدون تغییر مصالح", "بدون تغییر متریال",
    "مصالح ثابت", "متریال ثابت", "همان مصالح", "همان متریال",
    "مصالح تغییر نکند", "متریال تغییر نکند", "مصالح دست نخورد",
    "مصالح حفظ شود", "مصالح حفظ بشود",
    # KNOWLEDGE_RUNTIME_CONNECTION_V2 — Persian puts the object between the
    # noun and the verb ("مصالح آجر موجود را حفظ کن"), so a phrase-only list
    # missed the common "… را حفظ کن" form. These are the same preservation
    # imperative, matched on the verb side.
    "مصالح موجود", "متریال موجود", "را حفظ کن", "را حفظ کنید",
    "حفظ کن", "حفظ کنید", "دست نزن",
)

#: Verbs that make a material mention an actual REPLACEMENT even when
#: preservation phrasing also appears. A request that both replaces and
#: preserves is a genuine conflict; the replacement must not be suppressed.
_MATERIAL_REPLACEMENT_VERBS = (
    "replace", "replacing", "swap", "switch",
    "change the facade material", "change the material",
    "change its material", "change facade material",
    "convert the facade", "convert the material",
    "instead of", "in place of",
    "تبدیل", "جایگزین", "عوض", "تغییر بده", "تغییر دهید",
    "به جای", "به‌جای",
)


#: KNOWLEDGE_MATERIAL_FIDELITY_V2 — material-governed preservation.
#:
#: The bounded phrase list above can only enumerate phrasings that do NOT
#: contain the material noun ("preserve the facade material"). Two ordinary
#: preservation instructions were therefore read as REPLACEMENTS:
#:
#:   "Preserve the existing brick finish"   -> brick replacement delta
#:   "do not change the brick material"     -> brick replacement delta
#:
#: The second one also discarded the lighting request it was attached to, so a
#: negation turned into the opposite instruction. The DETECTED material
#: mention is now checked against a preservation/negation governor in the SAME
#: clause. Clause scoping is what keeps a genuine replacement intact: in
#: "keep the windows, replace the facade with stone" the governor and the
#: material are in different clauses.
_PRESERVATION_GOVERNORS = (
    r"\bpreserv\w*",
    r"\bkeep\w*",
    r"\bretain\w*",
    r"\bmaintain\w*",
    r"\bdo\s+not\s+change",
    r"\bdon'?t\s+change",
    r"\bdo\s+not\s+modify",
    r"\bnot\s+change",
    r"\bwithout\s+changing",
    r"\bunchanged\b",
    # Persian
    r"حفظ",
    r"تغییر\s*نکن",
    r"تغییر\s*نکند",
    r"دست\s*نزن",
    r"بدون\s*تغییر",
    r"ثابت",
)

_NEGATION_CLAUSE_SPLIT = re.compile(
    r"[،,;؛.!?؟\n]|\bbut\b|\bwhile\b|\bwhilst\b",
    re.IGNORECASE,
)


def _material_patterns(material):
    """The existing material vocabulary entries for one canonical material."""

    patterns = []

    for canonical, candidates, _english in _MATERIALS:

        if canonical == material:

            patterns.extend(candidates)

    for canonical, candidates in _MATERIAL_COMPOUNDS:

        if canonical == material:

            patterns.extend(candidates)

    return patterns


def _material_preservation_in_clause(haystack, material):
    """True when the material mention ITSELF is governed by preservation."""

    patterns = _material_patterns(material)

    if not patterns:

        return False

    for variant in (haystack, haystack.replace("\u200c", " ")):

        for clause in _NEGATION_CLAUSE_SPLIT.split(variant):

            clause = clause.strip()

            if not clause or not any(p in clause for p in patterns):

                continue

            if not any(
                re.search(governor, clause)
                for governor in _PRESERVATION_GOVERNORS
            ):

                continue

            # The same clause must not also ask for a replacement.
            if any(verb in clause for verb in _MATERIAL_REPLACEMENT_VERBS):

                continue

            return True

    return False


def _material_is_preserved(haystack, time_of_day, style=None, material=None):
    """True when a material mention is a preservation CONSTRAINT.

    Requires three things together, so the suppression can never fire on a
    genuine material-change request:

      1. another intent exists (a lighting/time-of-day OR style request), so
         the material is merely being protected while something else changes;
      2. explicit preservation phrasing is present;
      3. no explicit replacement verb is present.

    `material` (the detected canonical material) enables the clause-scoped
    check above, which covers preservation instructions that name the material
    inside the preservation phrase.
    """

    if not time_of_day and not style:
        return False

    text = str(haystack or "")

    if material and _material_preservation_in_clause(text, material):

        return True

    variants = (text, text.replace("\u200c", " "))

    preserved = any(
        signal in variant
        for signal in _MATERIAL_PRESERVATION_SIGNALS
        for variant in variants
    )

    if not preserved:
        return False

    replaced = any(
        verb in variant
        for verb in _MATERIAL_REPLACEMENT_VERBS
        for variant in variants
    )

    return not replaced


# Conflicts removed from the GENERIC builder tail only.
#
# The two trailing entries target the builder's generic
# "replace the facade material" instruction. A time-of-day or
# lighting edit does not ask for a material change, so that generic
# instruction must not survive and silently repaint the facade.
_MATERIAL_POLLUTION_TERMS = (
    "surface material with",
    "replace only the facade",
)


#: V4.3B — the builder's default storey phrase. Never valid for an edit: the
#: source image is the authority on floor count, and the phrase contradicts any
#: multi-storey source.
_FALSE_DEFAULT_FLOOR_TERMS = (
    "single floor building",
)


_CONFLICT_TIME_OF_DAY = {

    TIME_NIGHT: (
        "natural lighting", "daylight", "bright day", "daytime",
        "golden hour", "sunlit", "clear sky", "midday", "bright natural",
        "soft directional shadows",
    ) + _MATERIAL_POLLUTION_TERMS,

    TIME_DAY: (
        "night scene", "night lighting", "deep blue sky",
        "warm lit windows", "evening", "dusk", "twilight",
        "artificial exterior lighting",
    ) + _MATERIAL_POLLUTION_TERMS,

    TIME_SUNSET: (
        "natural lighting", "daylight", "midday", "night scene",
        "deep blue sky",
    ) + _MATERIAL_POLLUTION_TERMS,

    TIME_SUNRISE: (
        "natural lighting", "daylight", "midday", "night scene",
        "deep blue sky",
    ) + _MATERIAL_POLLUTION_TERMS,

    # V4.3A — M4. A morning request must strip the generic tail's
    # "golden hour natural lighting": morning is a different illumination
    # state, and leaving it in is exactly the failure the audit measured.
    # "golden hour" is listed whole; a hyphenated mention inside the delta
    # text ("golden-hour" for a sunset request) is never matched against this
    # table, because only the builder tail is filtered.
    TIME_MORNING: (
        "golden hour", "sunset", "dusk", "twilight", "night scene",
        "deep blue sky", "warm lit windows", "warm low sun",
    ) + _MATERIAL_POLLUTION_TERMS,

    # V4.3A — M4. Noon strips the warm low-sun vocabulary.
    TIME_NOON: (
        "golden hour", "sunset", "dusk", "twilight", "night scene",
        "deep blue sky", "warm low sun", "long soft shadows",
    ) + _MATERIAL_POLLUTION_TERMS,

    # V4.3A — M4. Dusk keeps the deep-blue sky but must lose the bright
    # daylight and the golden-hour tail.
    TIME_DUSK: (
        "golden hour", "bright day", "daylight", "midday", "night scene",
        "warm low sun",
    ) + _MATERIAL_POLLUTION_TERMS,
}


_CONFLICT_LIGHTING = (
    "surface material with", "replace only the facade",
)


# ----------------------------------------------------------
# LIGHTING-QUALITY DELTAS (R4_POSITIVE_INSTRUCTION_CONTRACT_V1)
#
# Every sentence below is BUILDING-AGNOSTIC on purpose: this is the general
# contract for any facade, so it names no brick, villa, storey count or
# material. It states the change (colour temperature / naturalness) and the
# four things that must NOT move with it: time of day, sun position, sky and
# fixtures. A warmth request is not a sunset request and not a relight.
# ----------------------------------------------------------

_DELTA_LIGHTING_QUALITY = {

    LIGHTING_QUALITY_WARMER: (
        "DELTA: adjust only the illumination of the existing scene, make the "
        "existing daylight slightly warmer and more natural, a warmer colour "
        "temperature of the light falling on the existing surfaces, a softer "
        "and more natural daylight balance, keeping the same time of day, the "
        "same sun position and the same sky, no sunset, no golden hour, no "
        "night lighting, no new light fixtures"
    ),

    LIGHTING_QUALITY_COOLER: (
        "DELTA: adjust only the illumination of the existing scene, make the "
        "existing daylight slightly cooler and cleaner, a cooler colour "
        "temperature of the light falling on the existing surfaces, keeping "
        "the same time of day, the same sun position and the same sky, no "
        "sunset, no blue hour, no night lighting, no new light fixtures"
    ),

    LIGHTING_QUALITY_NATURAL: (
        "DELTA: adjust only the illumination of the existing scene, make the "
        "existing daylight more natural and better balanced, a more even "
        "natural daylight exposure across the existing surfaces without "
        "changing their material colour, keeping the same time of day, the "
        "same sun position and the same sky, no sunset, no golden hour, no "
        "night lighting, no new light fixtures"
    ),
}


#: Tail segments that would turn a lighting-quality edit into something else.
#: A conversion ("night scene", "golden hour") or a restyle ("facade
#: transformation") contradicts a request that keeps the same time of day.
_CONFLICT_LIGHTING_QUALITY = (
    "night scene", "night lighting", "dusk", "twilight", "golden hour",
    "sunset", "warm lit windows", "artificial exterior lighting",
    "deep shadows", "facade transformation", "renovation",
) + _CONFLICT_LIGHTING + _MATERIAL_POLLUTION_TERMS


_MATERIAL_DESCRIPTION = {

    # "stone" is intentionally generic.  It must not silently become natural
    # stone, travertine, marble or limestone when the user did not select a
    # species.
    "stone": "stone of unspecified species",
    "travertine": "natural travertine stone",
    "marble": "natural marble",
    "natural_stone": "natural stone",
    "fire_brick": "fired refractory facing brick",
    "red_brick": "fired red clay brick",
    "wood": "natural timber wood",
    "glass": "architectural glass",
    "brick": "fired clay brick",
    "concrete": "fair-faced architectural concrete",
    "metal": "architectural metal panel",
}


_MATERIAL_DETAIL = {

    "stone": (
        "visible stone texture; keep the stone species, colour, finish, "
        "module and joint pattern unspecified"
    ),

    "travertine": (
        "natural travertine stone surface with visible veining and stone "
        "texture"
    ),
    "marble": (
        "natural marble surface with visible marble veining; keep the finish "
        "and joint pattern unspecified unless requested"
    ),

    "natural_stone": (
        "natural stone surface and visible stone texture; keep the species, "
        "colour, finish, module and joint pattern unspecified"
    ),

    "fire_brick": (
        "fired refractory facing brick surface with visible brick texture; "
        "keep the brick module and joint pattern unchanged unless requested"
    ),

    "red_brick": (
        "fired red clay brick surface with visible brick bond and mortar "
        "joints"
    ),

    "wood": (
        "natural timber surface with visible wood grain; keep the species, "
        "colour and board pattern unspecified unless requested"
    ),

    "glass": (
        "clear architectural glazing, controlled reflection, slim frames, "
        "transparent facade surface"
    ),

    "brick": (
        "fired clay brick surface with visible brick bond and mortar joints; "
        "keep the brick colour, module and joint pattern unspecified unless "
        "requested"
    ),

    "concrete": (
        "fair-faced concrete surface, fine board-formed texture, crisp "
        "shadow gaps, monolithic material expression"
    ),

    "metal": (
        "architectural metal cladding, fine panel joints, controlled "
        "metallic reflection"
    ),
}


# ----------------------------------------------------------
# MATCHING HELPERS
# ----------------------------------------------------------

def _normalize(text):

    return " ".join(
        str(text or "").lower().split()
    )


# ==========================================================
# EXACT EDIT-SCOPE RETENTION V2
# ==========================================================
#
# `compile_edit_delta` is the authoritative owner of conversational image-edit
# semantics.  It previously retained the requested material but replaced the
# rest of the material clause with a generic sentence, so an explicitly named
# surface and the request's preservation clause were gone before ImageHandler,
# PromptBuilder or RenderRuntime could use them.
#
# These helpers retain only two bounded pieces of the user's instruction:
#   * the surface phrase governed by a material-replacement construction;
#   * clauses governed by an explicit preservation verb.
#
# They are not a component ontology and do not infer architecture.  Unnamed
# surfaces/components remain absent, and the full raw request is never copied.

_PRESERVATION_CLAUSE_BOUNDARY_RE = re.compile(
    r"[.!?؟;؛\n]+|\b(?:but|however|while|whilst)\b|(?:اما|ولی)",
    re.IGNORECASE,
)

_EXPLICIT_PRESERVATION_GOVERNOR_RE = re.compile(
    r"\b(?:preserv\w*|keep\w*|retain\w*|maintain\w*|"
    r"do\s+not\s+(?:change|alter|modify)|don'?t\s+(?:change|alter|modify)|"
    r"without\s+chang\w*)\b|"
    r"(?:حفظ\s*(?:کن|کنید|شود|بماند|گردد)?|نگه\s*دار|"
    r"تغییر\s*(?:نکن|نکنید|نکند|نده|ندهید)|دست\s*نزن|"
    r"بدون\s*تغییر|ثابت\s*بماند)",
    re.IGNORECASE,
)

_ENGLISH_PRESERVATION_PREFIX_RE = re.compile(
    r"\b(?:preserv\w*|keep\w*|retain\w*|maintain\w*|"
    r"do\s+not\s+(?:change|alter|modify)|don'?t\s+(?:change|alter|modify)|"
    r"without\s+chang\w*)\b",
    re.IGNORECASE,
)

_MATERIAL_TARGET_SURFACE_PATTERNS = (
    re.compile(
        r"\b(?:replace|change|swap)\s+(?:only\s+)?[^.;!?؟]+?"
        r"\b(?:on|of)\s+(?:the\s+)?(?P<surface>[^.;!?؟]+?)\s+"
        r"(?:with|to|into)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:material|finish|cladding)\s+(?:on|of)\s+(?:the\s+)?"
        r"(?P<surface>[^.;!?؟]+?)\s+(?:with|to|into)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:روی|بر\s*روی|در)\s+(?P<surface>[^.;!?؟]+?)\s+را\s+"
        r"(?:با|به)\s+",
        re.IGNORECASE,
    ),
)

_MATERIAL_SURFACE_MARKERS = (
    "surface", "surfaces", "plane", "planes", "wall", "walls",
    "facade", "façade", "roof", "column", "columns", "base", "plinth",
    "سطح", "سطوح", "صفحه", "دیوار", "نما", "سقف", "ستون", "ازاره",
)


def _clean_explicit_clause(value):

    return " ".join(str(value or "").strip(" ,،.;؛").split())


#: NEOCLASSICAL_LIVE_EVIDENCE_HANDOFF_V1 — "retaining wall" is a BUILDING
#: ELEMENT, not a preservation governor. The governor regex matches
#: `retain\w*`, so "Do not automatically apply facade stone to the courtyard,
#: retaining walls or neighbouring buildings" was read as a preservation
#: clause and its tail was emitted as "retaining walls or neighbouring
#: buildings" inside EXPLICIT PRESERVATION.
_RETAINING_WALL_RE = re.compile(r"\bretaining\s+walls?\b", re.IGNORECASE)


def _explicit_preservation_clauses(text):
    """Return only user clauses carrying an explicit preservation governor."""

    result = []

    for raw_clause in _PRESERVATION_CLAUSE_BOUNDARY_RE.split(str(text or "")):

        clause = _clean_explicit_clause(raw_clause)

        if not clause or not _EXPLICIT_PRESERVATION_GOVERNOR_RE.search(clause):

            continue

        # The noun phrase "retaining wall(s)" is removed before the governor
        # test. A clause whose ONLY governor was that noun is not a
        # preservation statement; a clause that also says "preserve"/"retain"
        # anywhere else is unaffected.
        if _RETAINING_WALL_RE.search(clause) and not (
            _EXPLICIT_PRESERVATION_GOVERNOR_RE.search(
                _RETAINING_WALL_RE.sub(" ", clause)
            )
        ):

            continue

        # English governors lead their object list, so discard unrelated text
        # before the governor. Persian commonly puts the verb after the object
        # list ("... را حفظ کن"), therefore its whole bounded clause is kept.
        english = _ENGLISH_PRESERVATION_PREFIX_RE.search(clause)

        if english:

            clause = _clean_explicit_clause(clause[english.start():])

        if clause and clause.lower() not in [item.lower() for item in result]:

            result.append(clause)

    return result


def _canonical_surface_phrase(surface):

    phrase = _clean_explicit_clause(surface)

    phrase = re.sub(r"^(?:the|these|those)\s+", "", phrase, flags=re.I)

    low = phrase.lower()

    if not phrase or len(phrase) > 140:

        return None

    if not any(marker in low for marker in _MATERIAL_SURFACE_MARKERS):

        return None

    # Preserve English phrases verbatim (case-normalized). For the established
    # Persian surface construction, translate only the words the request
    # actually supplied; no surface or scope is invented.
    if any("\u0600" <= char <= "\u06ff" for char in phrase):

        if "نما" in phrase and "دیوار" in phrase and "اصلی" in phrase:

            return "main facade wall planes"

        if "نما" in phrase and ("دیوار" in phrase or "سطح" in phrase):

            return "facade wall surfaces"

        if "سقف" in phrase:

            return "roof surfaces"

        if "ستون" in phrase:

            return "column surfaces"

    return low


def _explicit_material_target_surfaces(text):
    """The explicitly governed material surface, never a guessed default."""

    raw = str(text or "")

    for pattern in _MATERIAL_TARGET_SURFACE_PATTERNS:

        match = pattern.search(raw)

        if not match:

            continue

        surface = _canonical_surface_phrase(match.group("surface"))

        if surface:

            return [surface]

    return []


def _hits(haystack, phrases):

    return [
        phrase for phrase in phrases
        if phrase in haystack
    ]


def _time_term_pattern(term):

    escaped = re.escape(term)

    if term.isascii():

        return r"(?<![a-z0-9])" + escaped + r"(?![a-z0-9])"

    return escaped


def _directional_time_mentions(haystack, start=0, end=None):

    end = len(haystack) if end is None else end
    window = haystack[start:end]
    candidates = []

    for value, terms in _DIRECTIONAL_TIME_TERMS:

        for term in terms:

            for match in re.finditer(_time_term_pattern(term), window):

                candidates.append((
                    start + match.start(),
                    start + match.end(),
                    value,
                    term,
                ))

    # Prefer the longest term at an overlapping position: ``night time`` is
    # one mention, not both ``night time`` and ``night``.
    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    mentions = []

    for candidate in candidates:

        if any(
            candidate[0] < accepted[1] and candidate[1] > accepted[0]
            for accepted in mentions
        ):

            continue

        mentions.append(candidate)

    return mentions


def _time_clause_bounds(haystack, start, end):

    left = 0
    right = len(haystack)

    for boundary in _TIME_CLAUSE_BOUNDARY_RE.finditer(haystack):

        if boundary.end() <= start:

            left = boundary.end()

        elif boundary.start() >= end:

            right = boundary.start()
            break

    return left, right


def _time_mention_is_rejected(haystack, start, end):

    left, right = _time_clause_bounds(haystack, start, end)
    prefix = haystack[left:start]
    suffix = haystack[end:right]

    # Prefix rejection covers both contrast clauses (``نه غروب`` / ``not
    # twilight``) and imperative negation (``do not make it night``).
    if re.search(r"(?:^|\s)(?:نه|not|never)(?:\s|$)", prefix):

        return True

    if re.search(r"(?:^|\s)(?:نکن|نکنید)(?:\s|$)", prefix):

        return True

    # Persian imperative/copular negation follows the state name.
    if re.match(
        r"^\s*(?:نباشد|نباشه|نباش|نکن|نکنید|نشود|نشه|نیست|نمی‌باشد|نمی باشد)",
        suffix,
    ):

        return True

    if re.match(r"^\s*(?:should\s+not\s+be|must\s+not\s+be)", suffix):

        return True

    return False


def _time_mention_is_source(haystack, start, end):

    if not any(action in haystack for action in _TIME_TRANSFORM_ACTIONS):

        return False

    _left, right = _time_clause_bounds(haystack, start, end)

    return any(
        marker.start() >= end and marker.start() < right
        for marker in _TIME_TARGET_MARKER_RE.finditer(haystack)
    )


def _time_mention_is_context_only(haystack, start, end):

    left, right = _time_clause_bounds(haystack, start, end)
    clause = haystack[left:right]

    # LIGHTING_QUALITY (R4_POSITIVE_INSTRUCTION_CONTRACT_V1) — a time word
    # that directly QUALIFIES an illumination noun ("daylight illumination",
    # "daylight lighting", "daylight exposure") is naming the light that is
    # already in the picture, not asking for a new time of day. Measured
    # consequence of the missing rule: "Make the daylight illumination of this
    # existing architectural image slightly warmer" compiled to
    # `time_of_day_change / day`, i.e. a request to re-render the sky, the sun
    # and the shadows, and `_time_mention_is_context_only` could not catch it
    # because its own source markers ("existing image") do not match "existing
    # architectural image", and because "make" is a transform action.
    #
    # The rule is deliberately narrow: it needs the qualifier construction AND
    # no explicit destination marker in the clause. "Convert this night scene
    # to daytime" is answered by `_directional_time_target` before this
    # function is reached, and carries "to", so conversion recognition is not
    # weakened.
    if (
        _TIME_ILLUMINATION_QUALIFIER_RE.search(clause)
        and not _TIME_TARGET_MARKER_RE.search(clause)
    ):

        return True

    return (
        any(marker in clause for marker in _TIME_SOURCE_CONTEXT_MARKERS)
        and not any(action in clause for action in _TIME_TRANSFORM_ACTIONS)
    )


def _directional_time_target(haystack):

    # Explicit contrast makes the right-hand state authoritative.
    for marker in _TIME_CONTRAST_MARKER_RE.finditer(haystack):

        _left, right = _time_clause_bounds(
            haystack, marker.end(), marker.end()
        )

        for start, end, value, term in _directional_time_mentions(
            haystack, marker.end(), right
        ):

            if not _time_mention_is_rejected(haystack, start, end):

                return value, [term]

    if not any(action in haystack for action in _TIME_TRANSFORM_ACTIONS):

        return None, []

    # A state after ``به`` / ``to`` / ``into`` is the destination.  The
    # first valid mention in that destination clause wins; rejected later
    # alternatives cannot reverse it.
    for marker in _TIME_TARGET_MARKER_RE.finditer(haystack):

        _left, right = _time_clause_bounds(
            haystack, marker.end(), marker.end()
        )

        for start, end, value, term in _directional_time_mentions(
            haystack, marker.end(), right
        ):

            if not _time_mention_is_rejected(haystack, start, end):

                return value, [term]

    return None, []


def _affirmative_time_hits(haystack, signals):

    matched = []

    for phrase in signals:

        for occurrence in re.finditer(re.escape(phrase), haystack):

            start, end = occurrence.span()

            if _time_mention_is_rejected(haystack, start, end):

                continue

            if _time_mention_is_source(haystack, start, end):

                continue

            if _time_mention_is_context_only(haystack, start, end):

                continue

            matched.append(phrase)
            break

    return matched


def _detect_time_of_day(haystack):

    directional_value, directional_evidence = _directional_time_target(
        haystack
    )

    if directional_value:

        return directional_value, directional_evidence

    # Preserve the established specificity order for ordinary affirmative
    # requests, but admit only occurrences that are targets rather than a
    # rejected state, a transformation source, or a declarative source fact.
    for value, signals in _TIME_OF_DAY_SIGNAL_GROUPS:

        matched = _affirmative_time_hits(haystack, signals)

        if matched:

            return value, matched

    return None, []


# ==========================================================
# FACADE_I2I_SUBMISSION_SAFETY_V1 — COMPONENT-BOUND MATERIALS
#
# A material named next to one of these components is THAT component's
# material. "dark metal window frames" describes the frames; it is not a
# request to clad the wall in metal. "brick on the facade with metal railings"
# asks for brick, not for metal walls.
#
# Before this guard the replacement-TARGET window ("... with X") cut the text
# immediately before the component material, so a brick facade with metal
# window frames compiled to `material = metal` and emitted
# "replace the facade finish with dark architectural metal panel cladding" —
# a direct contradiction of the user's own request inside the same prompt.
#
# This is a bounded suffix test over vocabulary the module already reasons
# about. It is not a parser, and it adds no material vocabulary.
# ==========================================================

_COMPONENT_NOUNS_LATIN = (
    "window frame", "window frames", "window", "windows",
    "frame", "frames",
    "railing", "railings", "guardrail", "balustrade",
    "balcony", "balconies",
    "door", "doors",
    "shutter", "shutters", "grille", "grilles",
    "roof", "parapet", "gate", "gates",
)

#: Persian component nouns are matched as plain substrings: `\b` is defined on
#: ASCII word characters, so a word-boundary test is unreliable here. Only
#: unambiguous multi-character forms are listed ("در" would match "مدرن").
_COMPONENT_NOUNS_PERSIAN = (
    "قاب پنجره", "پنجره", "نرده", "بالکن", "ورودی",
)

_COMPONENT_PATTERN = re.compile(
    r"\b(?:" + "|".join(
        re.escape(noun) for noun in _COMPONENT_NOUNS_LATIN
    ) + r")\b"
)

#: Clause boundaries used to decide whether a material belongs to a component.
_CLAUSE_SEPARATORS = (",", ";", ".", " and ", " با ", " و ", " with ")

#: Words that put a clause on the FACADE. A clause containing one of these is
#: describing the wall, so a component noun elsewhere in it does not capture
#: the material ("replace the pale facade finish with terracotta brick").
_FACADE_SCOPE_WORDS = (
    "facade", "façade", "wall", "cladding", "elevation", "exterior", "skin",
    "نما", "دیوار",
)


def _clause_around(text, position, length):
    """Start and end offsets of the clause containing a mention."""

    start = 0

    for separator in _CLAUSE_SEPARATORS:

        index = text.rfind(separator, 0, position)

        if index != -1:
            start = max(start, index + len(separator))

    end = len(text)

    for separator in _CLAUSE_SEPARATORS:

        index = text.find(separator, position + length)

        if index != -1:
            end = min(end, index)

    return start, end


def _mention_is_component_bound(text, position, phrase):
    """True when a material mention governs a COMPONENT, not the wall finish.

    Two orders are covered, because a user may name the component either side
    of the material:

        "dark metal window frames"        -> component AFTER  the material
        "the window-frame finish to dark charcoal metal" -> component BEFORE

    Both are clause-bounded, so an unrelated clause can never bind the mention,
    and a clause that is explicitly about the facade always keeps the material
    as the facade finish.
    """

    text = str(text or "")

    if not text:

        return False

    start, end = _clause_around(text, position, len(phrase))

    # ---- component AFTER the material ----
    tail = " ".join(text[position + len(phrase):end].split()[:4])

    if tail:

        if _COMPONENT_PATTERN.search(tail):
            return True

        if any(noun in tail for noun in _COMPONENT_NOUNS_PERSIAN):
            return True

    # ---- component BEFORE the material ----
    head = text[start:position]

    if not head.strip():

        return False

    if any(word in head for word in _FACADE_SCOPE_WORDS):

        return False

    if _COMPONENT_PATTERN.search(head):
        return True

    return any(noun in head for noun in _COMPONENT_NOUNS_PERSIAN)


def _earliest_facade_mention(text, compounds, start=0, end=None):
    """Earliest material mention in `[start, end)` that is not component-bound.

    Returns `(relative_position, canonical, matched_phrases)` or None. The scan
    runs over the WHOLE text and is bounded by `start`/`end` rather than over a
    slice, so the component test still sees the words just outside the window —
    "the window-frame finish to dark charcoal metal" must stay bound to the
    frame even though "window-frame" sits before the resolution window.
    """

    limit = len(text) if end is None else end

    best = None

    for position, canonical, phrase in sorted(compounds):

        if not (start <= position < limit):
            continue

        if _mention_is_component_bound(text, position, phrase):
            continue

        best = (position - start, canonical, [phrase])

        break

    for canonical, patterns, _english in _MATERIALS:

        matched = _hits(text, patterns)

        if not matched:
            continue

        position = None

        for phrase in matched:

            candidate = text.find(phrase, start)

            while (
                candidate != -1
                and candidate < limit
                and _mention_is_component_bound(text, candidate, phrase)
            ):
                candidate = text.find(phrase, candidate + 1)

            if candidate == -1 or candidate >= limit:
                continue

            if position is None or candidate < position:
                position = candidate

        if position is None:
            continue

        if best is None or (position - start) < best[0]:
            best = (position - start, canonical, matched)

    return best


def _detect_material(haystack):

    """Resolve the REQUESTED material.

    KNOWLEDGE_RECOVERY_01 — two corrections to the previous pure
    position rule, which is preserved for the direction case it was
    written for:

    1. Compound names are resolved first and their spans consumed.
       Persian material names are head-initial ("سنگ تراورتن"), so a
       pure position rule returned the generic head noun. This is the
       same span-consumption precedence the existing Persian
       architectural understanding module already uses.

    2. The mention searched is restricted to the REPLACEMENT TARGET
       when the request states one, so "replace the brick facade with
       travertine" resolves to travertine and "use wood instead of
       stone" still resolves to wood.

    "use wood instead of stone" -> wood      (unchanged)
    "سنگ تراورتن"               -> travertine
    "آجر نسوز"                  -> fire_brick
    """

    # ---- 1. compounds first, longest pattern first, spans consumed ----

    remaining = haystack

    compounds = []

    for canonical, patterns in _MATERIAL_COMPOUNDS:

        for phrase in sorted(patterns, key=len, reverse=True):

            if phrase in remaining:

                compounds.append(
                    (remaining.index(phrase), canonical, phrase)
                )

                remaining = remaining.replace(phrase, " " * len(phrase))

                break

    # ---- 2. restrict to the requested (target) material mention ----

    window_start = 0

    window_end = len(remaining)

    target_marker_used = False

    source_positions = [
        remaining.index(marker)
        for marker in _REPLACEMENT_SOURCE_MARKERS
        if marker in remaining
    ]

    if source_positions:

        window_end = min(source_positions)

    else:

        target_positions = [
            remaining.rindex(marker) + len(marker)
            for marker in _REPLACEMENT_TARGET_MARKERS
            if marker in remaining
        ]

        if target_positions:

            window_start = max(target_positions)

            target_marker_used = True

    window = remaining[window_start:window_end]

    # ---- 3. earliest FACADE-bound mention inside the window ----

    best = _earliest_facade_mention(
        remaining, compounds, start=window_start, end=window_end
    )

    # SUBMISSION_SAFETY_V1 — a replacement TARGET window can contain nothing
    # but a component material ("... with dark metal window frames", "... to
    # dark charcoal metal"). In that case the marker was a specification, not a
    # replacement, and the facade material the user actually named sits before
    # it. Widening recovers it instead of promoting a window frame to wall
    # cladding.
    #
    # A SOURCE window is never widened: "use wood instead of stone" must keep
    # the replaced material excluded, exactly as before.
    if best is None and target_marker_used:

        best = _earliest_facade_mention(
            remaining, compounds, start=0, end=len(remaining)
        )

    if best is None:

        return None, []

    return best[1], best[2]


def _detect_replaced_material(haystack, target_material):
    """Material on the replaced surface, when the request explicitly names it."""

    text = str(haystack or "").replace("-", " ")

    # Work inside the material-operation sentence so a later preservation
    # clause cannot be mistaken for the replacement source.
    clauses = [
        clause.strip()
        for clause in re.split(r"[.!?؟\n]", text)
        if clause.strip()
    ]

    operation = next(
        (
            clause for clause in clauses
            if any(verb in clause for verb in _MATERIAL_REPLACEMENT_VERBS)
            and any(pattern in clause for pattern in _material_patterns(target_material))
        ),
        "",
    )

    if not operation:

        return None

    source_markers = [
        (operation.index(marker), marker)
        for marker in _REPLACEMENT_SOURCE_MARKERS
        if marker in operation
    ]

    if source_markers:

        position, marker = min(source_markers)

        candidate, _hits_found = _detect_material(
            operation[position + len(marker):]
        )

    else:

        target_markers = [
            (operation.rindex(marker), marker)
            for marker in _REPLACEMENT_TARGET_MARKERS
            if marker in operation
        ]

        if not target_markers:

            return None

        position, _marker = max(target_markers)

        candidate, _hits_found = _detect_material(operation[:position])

    if candidate and candidate != target_material:

        return candidate

    return None


def _tone_hits(haystack, signals):

    """Tone signals, matched on a word boundary for Latin patterns.

    SUBMISSION_SAFETY_V1 — a plain substring test read "daylight" as a request
    for a LIGHT material tone, so "keep the original daylight composition"
    turned a deep terracotta brick request into "light brick cladding". The
    boundary rule is the same one `_colour_hits` already uses, so "daylight"
    and "lighter" can no longer masquerade as the word "light".
    """

    found = []

    for signal in signals:

        if signal.isascii():

            if re.search(
                r"(?<![a-z0-9])" + re.escape(signal) + r"(?![a-z0-9])",
                haystack,
            ):

                found.append(signal)

        elif signal in haystack:

            found.append(signal)

    return found


def _detect_tone(haystack):

    light = _tone_hits(haystack, _TONE_LIGHT_SIGNALS)

    if light:

        return "light", light

    dark = _tone_hits(haystack, _TONE_DARK_SIGNALS)

    if dark:

        return "dark", dark

    return None, []


def _colour_hits(haystack, patterns):

    """Colour-name matching.

    A Latin colour name must match on a word boundary, so that
    "red" cannot be found inside "reduced"/"hundred". Non-Latin
    patterns keep the module's substring behaviour.
    """

    found = []

    for pattern in patterns:

        if pattern.isascii():

            if re.search(
                r"(?<![a-z0-9])" + re.escape(pattern) + r"(?![a-z0-9])",
                haystack
            ):

                found.append(pattern)

        elif pattern in haystack:

            found.append(pattern)

    return found


# Markers that introduce the TARGET colour of a change ("change X to <colour>").
# A colour that follows one of these is the requested colour; a colour that
# merely describes the current state ("change the RED wall to blue") is not.
_COLOUR_TARGET_MARKERS = (
    "to", "into", "towards", "toward", "become", "becomes",
    "به", "به رنگ", "به سمت",
)


def _colour_target_marker_position(haystack):

    """Position just after the LAST target marker, or None."""

    best = None

    for marker in _COLOUR_TARGET_MARKERS:

        if marker.isascii():

            for match in re.finditer(
                r"(?<![a-z0-9])" + re.escape(marker) + r"(?![a-z0-9])",
                haystack
            ):

                if best is None or match.end() > best:

                    best = match.end()

        else:

            start = 0

            while True:

                index = haystack.find(marker, start)

                if index < 0:

                    break

                end = index + len(marker)

                if best is None or end > best:

                    best = end

                start = index + 1

    return best


def _detect_colour(haystack):

    """Resolve WHICH colour the user asked for.

    A target marker wins ("change the red wall to blue" -> blue); otherwise the
    earliest-mentioned colour wins ("blue instead of red" -> blue).
    """

    mentions = []

    for canonical, patterns, _english in _COLOURS:

        matched = _colour_hits(haystack, patterns)

        if not matched:

            continue

        position = min(
            haystack.index(phrase) for phrase in matched
        )

        mentions.append((position, canonical, matched))

    if not mentions:

        return None, []

    marker = _colour_target_marker_position(haystack)

    if marker is not None:

        after = [item for item in mentions if item[0] >= marker]

        if after:

            chosen = min(after, key=lambda item: item[0])

            return chosen[1], chosen[2]

    chosen = min(mentions, key=lambda item: item[0])

    return chosen[1], chosen[2]


# ----------------------------------------------------------
# DELTA COMPILATION
# ----------------------------------------------------------

def _preservation_suffix(clauses):

    cleaned = [
        _clean_explicit_clause(clause)
        for clause in (clauses or ())
        if _clean_explicit_clause(clause)
    ]

    if not cleaned:

        return ""

    return "; EXPLICIT PRESERVATION: " + ". ".join(cleaned)


# NEOCLASSICAL_FINAL_PROMPT_CONSISTENCY_V1 — PROBLEM C.
#
# The generic travertine detail asks for "visible veining", which for a
# restrained neoclassical design reads as strongly veined marble and invites
# the source brick/block coursing to be carried through the finished stone.
# This variant is used ONLY when the delta also carries a real style, so an
# unrelated user asking for travertine keeps the existing wording exactly.
_RESTRAINED_TRAVERTINE_DETAIL = (
    "restrained light cream travertine with natural subtle porosity, "
    "restrained grain and colour variation, and coherent ashlar courses with "
    "realistic joints; no exaggerated golden marble veining and no brick or "
    "block coursing carried through the stone"
)


def _material_delta(
    material,
    tone,
    target_surfaces=None,
    preservation_clauses=None,
    replaced_material=None,
    design_restyle=False,
):

    description = _MATERIAL_DESCRIPTION.get(material, material)

    if tone == "light":

        description = "light " + description

    elif tone == "dark":

        description = "dark " + description

    detail = _MATERIAL_DETAIL.get(material, description)

    if design_restyle and material == "travertine":

        detail = _RESTRAINED_TRAVERTINE_DETAIL

    surfaces = [
        str(surface).strip()
        for surface in (target_surfaces or ())
        if str(surface).strip()
    ]

    if surfaces:

        target = " and ".join(surfaces)

        delta = (
            "DELTA: replace only the existing finish on the " + target
            + " with " + description + " cladding, " + detail
            + "; AUTHORIZED MATERIAL TARGET: only " + target
            + " may receive the replacement material; no other surface is "
            "authorized"
        )

    else:

        delta = (
            "DELTA: replace the facade finish with " + description
            + " cladding, " + detail
            + ", apply it only to the facade surfaces whose finish is being "
            "replaced"
        )

    if design_restyle:

        # NEOCLASSICAL_FINAL_PROMPT_CONSISTENCY_V1 — PROBLEM A.
        #
        # "keep every other … architectural element unchanged" forbade the
        # decorative stone the SAME request authorises. The protected set is
        # now named as the primary structure, and the additions are stated as
        # relief on the existing planes — which is what distinguishes an
        # authorised addition from geometry drift.
        delta += (
            "; keep every other material, base, frame, trim, opening and "
            "structural element unchanged, and keep the same building; the "
            "requested decorative stone elements are additions applied as "
            "relief on the existing wall planes, not replacements of those "
            "elements"
        )

    else:

        delta += (
            "; keep every other material, base, frame, trim, opening and "
            "architectural element unchanged, and keep the same building"
        )

    delta += _preservation_suffix(preservation_clauses)

    if preservation_clauses and replaced_material:

        source_name = {
            "red_brick": "brick",
            "brick": "brick",
            "fire_brick": "fire brick",
        }.get(
            replaced_material,
            _MATERIAL_DESCRIPTION.get(replaced_material, replaced_material),
        )

        delta += (
            "; MATERIAL BOUNDARY: the named protected components must retain "
            "their existing materials; any existing " + source_name
            + " on those protected components must remain " + source_name
        )

    return delta


# ==========================================================
# ARCHITECTURAL STYLE — KNOWLEDGE_RUNTIME_CONNECTION_V2
# ==========================================================
#
# The style is NOT re-parsed here. `persian_architectural_understanding` is the
# existing authoritative bilingual style reader, and
# `architectural_prompt_compiler_v1.STYLE_WORD` is the existing canonical-id to
# English-phrase vocabulary. This module only CONNECTS those to the executable
# edit instruction — which is precisely the link that was missing, and the
# reason a recognised style never reached the prompt.

def _style_word(style_id):
    """Reuse the compiler's existing style vocabulary. No second table."""

    try:

        from core.prompt_intelligence.architectural_prompt_compiler_v1 import (
            STYLE_WORD,
        )

        return STYLE_WORD.get(style_id, str(style_id).replace("_", " "))

    except Exception:

        return str(style_id).replace("_", " ")


def _detect_style(haystack, image_edit=False):
    """Return (canonical_style_id, mentions) for an EDIT turn, else (None, []).

    A style mention becomes an edit instruction only when the turn is known to
    be an edit of an existing subject: either the caller asserts it
    (`image_edit`), or the text refers to the current building ("this facade",
    "همین ساختمان"). That gate is what keeps "Generate a modern villa" a
    text-to-image request.
    """

    if not haystack:

        return None, []

    if not image_edit and not any(
        marker in haystack for marker in _SAME_SUBJECT_MARKERS
    ):

        return None, []

    try:

        from core.prompt_intelligence.persian_architectural_understanding import (
            understand,
        )

        understanding = understand(haystack)

    except Exception:

        return None, []

    style = (understanding or {}).get("style") or {}

    target = style.get("target")

    if not target:

        return None, []

    return target, list(style.get("mentions") or [])


def _style_clause(style_id):
    """The executable style instruction, with preservation of the source."""

    word = _style_word(style_id)

    return (
        "change the architectural style of the existing building to " + word
        + ", apply the " + word + " facade language to the existing surfaces, "
        "keep the same building, the same geometry and the same windows"
    )


def _style_delta(style_id, preservation_clauses=None):

    return (
        "DELTA: " + _style_clause(style_id)
        + _preservation_suffix(preservation_clauses)
    )


def compile_edit_delta(text, image_edit=False):

    """Deterministically compile one conversational edit into a
    structured, authoritative img2img prompt + conflict terms.

    Returns a JSON-safe contract dict. `edit_class` is
    `generic_edit` when nothing could be classified; callers must then
    fall back to the previous behaviour.
    """

    raw = str(text or "")

    haystack = _normalize(raw)

    result = {

        "contract": CONTRACT,
        "version": VERSION,

        "raw_text": raw,
        "normalized_text": haystack,

        "edit_class": EDIT_GENERIC,
        "edit_target": "scene",
        "time_of_day": None,
        # LIGHTING_QUALITY (R4_POSITIVE_INSTRUCTION_CONTRACT_V1) — the
        # quality axis of `lighting_change`: warmer / cooler / more_natural.
        # None for every other class, including the intensity sub-cases.
        "lighting_quality": None,
        "style": None,
        "material": None,
        "material_tone": None,
        "color": None,

        # EXACT_EDIT_SCOPE_RETENTION_V2 — request-scoped clauses retained by
        # the existing edit contract. Empty unless this classified edit uses
        # them; no architectural component or surface is inferred.
        "target_surfaces": [],
        "explicit_preservation_clauses": [],
        "replaced_material": None,

        "delta_prompt": "",
        "prompt": "",
        "conflict_terms": [],

        "evidence": {},
    }

    if not haystack:

        return result

    explicit_target_surfaces = _explicit_material_target_surfaces(raw)

    explicit_preservation_clauses = _explicit_preservation_clauses(raw)

    # ------------------------------------------------------
    # CLASS PRECEDENCE
    #
    # A material request wins over a lighting request, because
    # "سنگ روشن کن" is "light stone", not "make it brighter".
    #
    # MOONLIT_NIGHT_V1 — with two bounded exceptions:
    #
    #   1. An explicit moon reference is itself a night request, so
    #      "make it moonlit" classifies as night even without the word
    #      "night". Only a grounded moon mention does this.
    #   2. A material named inside a PRESERVATION statement is a
    #      constraint, not a replacement request, so it must not hijack
    #      the class. See `_material_is_preserved`.
    # ------------------------------------------------------

    time_of_day, tod_hits = _detect_time_of_day(haystack)

    if time_of_day is None and _moonlit(haystack):

        time_of_day = TIME_NIGHT

        tod_hits = [
            signal for signal in _MOONLIT_SIGNALS if signal in haystack
        ] or ["moonlight"]

    material, material_hits = _detect_material(haystack)

    # KNOWLEDGE_RUNTIME_CONNECTION_V2 — the recognised architectural style is
    # read once here, through the existing style reader, and then carried by
    # whichever edit class wins. It is never silently dropped.
    style, style_hits = _detect_style(haystack, image_edit=image_edit)

    material_preserved = bool(material) and _material_is_preserved(
        haystack, time_of_day, style, material
    )

    if material and not material_preserved:

        tone, tone_hits = _detect_tone(haystack)

        result["edit_class"] = EDIT_MATERIAL
        result["edit_target"] = "facade"
        result["material"] = material
        result["material_tone"] = tone

        replaced_material = _detect_replaced_material(haystack, material)

        result["target_surfaces"] = explicit_target_surfaces

        result["explicit_preservation_clauses"] = (
            explicit_preservation_clauses
        )

        result["replaced_material"] = replaced_material

        result["evidence"] = {
            "material": material_hits,
            "tone": tone_hits,
        }

        # A replacement and a lighting request may both be present. The
        # material replacement owns the delta (an explicit replacement is
        # the stronger instruction), but the lighting domain is recorded
        # rather than silently discarded.
        if time_of_day:

            result["evidence"]["also_requested"] = [
                "time_of_day:%s" % time_of_day
            ]

        result["delta_prompt"] = _material_delta(
            material,
            tone,
            target_surfaces=explicit_target_surfaces,
            preservation_clauses=explicit_preservation_clauses,
            replaced_material=replaced_material,
            # A combined style + material request is a facade DESIGN whose
            # finish happens to be a material; a bare material request is not.
            design_restyle=bool(style),
        )

        # KNOWLEDGE_RUNTIME_CONNECTION_V2 — combined style + material. The
        # material owns the class (an explicit replacement is the stronger
        # instruction), but the requested STYLE must survive into the
        # executable instruction instead of being discarded.
        if style:

            result["style"] = style

            result["explicit_preservation_clauses"] = (
                explicit_preservation_clauses
            )

            result["evidence"]["style"] = style_hits

            result["delta_prompt"] = (
                result["delta_prompt"] + ", and " + _style_clause(style)
            )

        # The conflict table never contains the requested material, so
        # every entry is a genuinely competing material mention in the
        # generic builder tail.
        #
        # A material-only edit must also NOT assert a lighting
        # condition: the generic builder tail ends with "Natural
        # lighting", which would push a material edit on a night source
        # back to daylight. Removing it leaves the prompt
        # lighting-neutral so the source illumination is preserved.
        result["conflict_terms"] = list(
            _MATERIAL_CONFLICT_WORDS.get(material, ())
        ) + ["natural lighting"]

    else:

        if time_of_day:

            result["edit_class"] = EDIT_TIME_OF_DAY
            result["edit_target"] = "scene"
            result["time_of_day"] = time_of_day

            result["evidence"] = {"time_of_day": tod_hits}

            if material_preserved:

                result["evidence"]["material_preserved"] = material_hits

            # ARCHITECTURAL_NIGHT_EXPOSURE_V1 — a night relight defaults to
            # the architectural-exposure contract; the minimal variant is
            # used only when the user explicitly asked for it.
            #
            # MOONLIT_NIGHT_V1 — an explicit moon reference selects the
            # moonlit contract. The darkness override still outranks it: a
            # user who asked for an almost-black building did not ask for a
            # lit one.
            if (
                time_of_day == TIME_NIGHT
                and _explicit_minimal_illumination(haystack)
            ):

                result["delta_prompt"] = _DELTA_TIME_OF_DAY_NIGHT_MINIMAL

            elif (
                time_of_day == TIME_NIGHT
                and _moonlit(haystack)
            ):

                result["delta_prompt"] = _DELTA_TIME_OF_DAY_MOONLIT

            else:

                result["delta_prompt"] = _DELTA_TIME_OF_DAY[time_of_day]

            result["conflict_terms"] = list(
                _CONFLICT_TIME_OF_DAY[time_of_day]
            )

        elif style:

            # KNOWLEDGE_RUNTIME_CONNECTION_V2 — STYLE-ONLY EDIT.
            #
            # A recognised architectural style previously had no branch here,
            # so the request compiled to `generic_edit`, the routing layer saw
            # no appearance edit, and the turn fell back to plain img2img
            # instead of the existing global Kontext edit route. The style is
            # now an executable instruction that preserves the source.
            result["edit_class"] = EDIT_STYLE
            result["edit_target"] = "facade"
            result["style"] = style

            result["explicit_preservation_clauses"] = (
                explicit_preservation_clauses
            )

            result["evidence"] = {"style": style_hits}

            if material_preserved:

                result["evidence"]["material_preserved"] = material_hits

            result["delta_prompt"] = _style_delta(
                style,
                preservation_clauses=explicit_preservation_clauses,
            )

            result["conflict_terms"] = []

        else:

            # ----------------------------------------------
            # LIGHTING QUALITY (R4_POSITIVE_INSTRUCTION_CONTRACT_V1)
            #
            # Sits INSIDE the existing `lighting_change` class and after the
            # time-of-day and style branches, so conversion and restyle
            # precedence are unchanged: "make this scene a warm sunset" is
            # still a sunset, not a warmth tweak.
            #
            # It is tested BEFORE the intensity signals because a quality
            # request is the more specific instruction; a clause carrying both
            # ("brighter and warmer") is answered on the quality axis, and the
            # intensity wording is not silently converted into a brightness
            # demand the user did not separate from the temperature change.
            # ----------------------------------------------

            lighting_quality, quality_hits = _lighting_quality(haystack)

            if lighting_quality:

                result["edit_class"] = EDIT_LIGHTING
                result["edit_target"] = "scene"
                result["lighting_quality"] = lighting_quality

                result["evidence"] = {
                    "lighting_quality": quality_hits,
                }

                if material_preserved:

                    result["evidence"]["material_preserved"] = material_hits

                # EXACT EDIT-SCOPE RETENTION — a lighting edit is exactly the
                # case where the user says "and do not touch the materials or
                # the openings". Those clauses used to be computed and then
                # dropped on every branch except material and style, so the
                # only surviving record of the constraint was the raw turn.
                result["explicit_preservation_clauses"] = (
                    explicit_preservation_clauses
                )

                result["delta_prompt"] = (
                    _DELTA_LIGHTING_QUALITY[lighting_quality]
                    + _preservation_suffix(explicit_preservation_clauses)
                )

                result["conflict_terms"] = list(
                    _CONFLICT_LIGHTING_QUALITY
                )

            else:

                brighter = _hits(haystack, _BRIGHTER_SIGNALS)
                darker = _hits(haystack, _DARKER_SIGNALS)

                if brighter or darker:

                    result["edit_class"] = EDIT_LIGHTING
                    result["edit_target"] = "scene"

                    result["evidence"] = {
                        "brighter": brighter,
                        "darker": darker,
                    }

                    if brighter:

                        result["delta_prompt"] = (
                            "DELTA: raise the illumination of the existing "
                            "scene, brighter architectural lighting, more light "
                            "on the facade, clearer shadow detail, same time of "
                            "day, same materials"
                        )

                        result["conflict_terms"] = list(
                            _CONFLICT_LIGHTING
                        ) + [
                            "night scene", "deep shadows", "underexposed",
                        ]

                    else:

                        result["delta_prompt"] = (
                            "DELTA: lower the illumination of the existing "
                            "scene, darker architectural lighting, less light on "
                            "the facade, deeper shadows, same time of day, same "
                            "materials"
                        )

                        result["conflict_terms"] = list(
                            _CONFLICT_LIGHTING
                        ) + [
                            "bright natural", "bright day", "sunlit",
                        ]

                else:

                    color_hits = _hits(haystack, _COLOR_SIGNALS)

                    colour, colour_hits = _detect_colour(haystack)

                    # Either an explicit colour noun ("colour", "رنگ") or a
                    # named colour ("blue", "آبی") makes this a colour edit, so
                    # a Persian instruction needs no colour noun to qualify.
                    if color_hits or colour_hits:

                        result["edit_class"] = EDIT_COLOR
                        result["edit_target"] = "facade"

                        result["evidence"] = {"color": color_hits or colour_hits}

                        result["color"] = colour

                        if colour_hits:

                            result["evidence"]["color_name"] = colour_hits

                        if colour:

                            # I2I_INSTRUCTION_FIDELITY_V1 - a colour change is
                            # only expressed if the delta NAMES the requested
                            # colour. "keep the same materials" is dropped
                            # because it directly contradicted a repaint.
                            result["delta_prompt"] = (
                                "DELTA: change the facade colour of the existing "
                                "building to " + colour + ", recolour the "
                                "existing facade surfaces " + colour + ", keep "
                                "the same building, the same geometry and the "
                                "same openings"
                            )

                            result["conflict_terms"] = list(
                                _COLOR_CONFLICT_TERMS
                            )

                        else:

                            # No colour named - keep the previous wording
                            # rather than inventing a target colour.
                            result["delta_prompt"] = (
                                "DELTA: adjust the colour palette of the existing "
                                "facade, refine the material colour and tone, keep "
                                "the same materials and the same geometry"
                            )

    # ------------------------------------------------------
    # V4.3B — A. FALSE DEFAULT FLOOR CLAIM
    #
    # The generic img2img builder tail always states "single floor building":
    # PromptBuilder emits that phrase whenever no explicit floor count is
    # present, and an edit turn normally carries none.
    #
    # For an EDIT the SOURCE IMAGE governs the storey count, so that phrase is
    # never a valid constraint. It contradicts any source with more than one
    # floor, and it silently inserts a floor-count specification the user did
    # not ask for. Removing it is a conflict-term removal — no numeric count is
    # invented and no architectural constraint is added.
    #
    # Applied to every CLASSIFIED delta (time of day, lighting, material,
    # colour) because the defect is a property of the builder default, not of
    # one edit class. A genuine user floor constraint is unaffected: the delta
    # path never emits "single floor building", and a user-stated count arrives
    # through the intent/builder path as "<N> story building".
    # ------------------------------------------------------

    if result["delta_prompt"]:

        result["conflict_terms"] = (
            list(result["conflict_terms"])
            + list(_FALSE_DEFAULT_FLOOR_TERMS)
        )


    # ------------------------------------------------------
    # AUTHORITATIVE PROMPT
    # ------------------------------------------------------

    if result["delta_prompt"]:

        # NEOCLASSICAL_FINAL_PROMPT_CONSISTENCY_V1 — a delta that carries a
        # real style is a facade DESIGN, so it gets the design preservation
        # sentence. Every other classified delta keeps the original wording.
        _style_token = str(result.get("style") or "").strip().lower()

        _design_restyle = bool(_style_token) and _style_token not in (
            "unknown", "none", "existing",
        )

        result["prompt"] = ", ".join((
            _REFERENCE,
            result["delta_prompt"],
            _PRESERVE_DESIGN if _design_restyle else _PRESERVE,
            _QUALITY,
        ))

    return result


# ----------------------------------------------------------
# CONVENIENCE
# ----------------------------------------------------------

def is_classified(delta):

    return bool(
        isinstance(delta, dict)
        and delta.get("edit_class")
        and delta.get("edit_class") != EDIT_GENERIC
    )


def delta_prompt(delta):

    if not isinstance(delta, dict):

        return ""

    return delta.get("prompt") or ""


def conflict_terms(delta):

    if not isinstance(delta, dict):

        return ()

    return tuple(delta.get("conflict_terms") or ())


# Deterministic preservation escalation for material replacement.
# IMAGE_TO_IMAGE_05: a correct material prompt at
# high_preservation (denoise 0.25) only produced a partial surface
# change, so a facade material REPLACEMENT is deterministically
# escalated to the approved BALANCED band. It never jumps to
# creative.
MATERIAL_REPLACEMENT_LEVEL = "balanced"


# Deterministic strength for a time-of-day conversion.
#
# The approved high_preservation contract is described as
# "keep the building form and composition, change only appearance
# (lighting, materials, tone)" - a day <-> night conversion is
# exactly a lighting change, so the LEVEL stays high_preservation.
# Within that level the strongest approved strength (0.30, the band
# maximum) is used, because a global illumination change needs more
# than the 0.25 default while geometry must still be preserved.
TIME_OF_DAY_DENOISE = 0.30


def preservation_level(delta):

    if not isinstance(delta, dict):

        return None

    if delta.get("edit_class") == EDIT_MATERIAL:

        return MATERIAL_REPLACEMENT_LEVEL

    return None


def denoise_override(delta):

    """Deterministic strength inside the resolved level's band."""

    if not isinstance(delta, dict):

        return None

    if delta.get("edit_class") == EDIT_TIME_OF_DAY:

        return TIME_OF_DAY_DENOISE

    return None


# ==========================================================
# V4.3A — M7  SAME-SUBJECT APPEARANCE CONTINUATION
#
# The audit measured that the natural multi-variant phrasing never reached
# the edit path:
#
#   "same tower, sunset"          -> classified as ANALYZE
#   "Render the same tower at sunset" -> classified as a NEW text-to-image
#                                        request ("IGNORE OLD RENDER STATE")
#
# Both discard the source image, so geometry/massing/camera cannot be
# preserved. The vocabulary that identifies "an appearance variation of the
# building we already have" belongs here, next to the delta that describes
# the variation itself, and is shared by the vision intent gate and the
# intent router.
#
# The predicate NEVER decides whether a source image exists — the caller owns
# that check — and it is vetoed by any explicit request for a NEW building.
# ==========================================================

_SAME_SUBJECT_MARKERS = (
    "same tower", "same building", "same house", "same villa",
    "same facade", "the same", "this same", "same one",
    # KNOWLEDGE_RUNTIME_CONNECTION_V2 — "Convert this facade to …" is a
    # reference to the CURRENT building, but only the "same X" forms were
    # recognised, so an explicit English edit of this building was not
    # identified as a same-subject request at all.
    "this facade", "this building", "this house", "this villa", "this tower",
    "این نما", "این ساختمان", "این بنا", "این ویلا", "این برج",
    "همین برج", "همین ساختمان", "همین بنا", "همین ویلا", "همین نما",
    "همان برج", "همان ساختمان", "همان بنا", "همان ویلا",
    "همینو", "همونو",
)

# An explicit request for a DIFFERENT building always wins: it is a new
# subject, not a variant of the current one.
_NEW_BUILDING_MARKERS = (
    "new building", "new tower", "new house", "new villa", "new design",
    "different building", "different tower", "another building",
    "another tower", "from scratch",
    "ساختمان جدید", "برج جدید", "بنای جدید", "ویلای جدید",
    "ساختمان دیگر", "برج دیگر", "طراحی جدید", "از نو",
)

_APPEARANCE_EDIT_CLASSES = (
    EDIT_TIME_OF_DAY,
    EDIT_LIGHTING,
    EDIT_COLOR,
    EDIT_MATERIAL,
    # KNOWLEDGE_RUNTIME_CONNECTION_V2 — a style change is an appearance edit of
    # the existing building, so it must select the same global maskless Kontext
    # route as the other appearance classes.
    EDIT_STYLE,
)


def is_same_subject_appearance_request(text):
    """True when the turn asks for an APPEARANCE variation of the SAME subject.

    Deterministic. BOTH conditions are required:

      * a same-subject reference ("same tower", "همین برج", ...);
      * a classified appearance delta (time of day / lighting / colour /
        material).

    Vetoed by a question mark and by any explicit request for a NEW building.
    """

    haystack = _normalize(text)

    if not haystack:

        return False

    if "?" in haystack or "؟" in haystack:

        return False

    if any(marker in haystack for marker in _NEW_BUILDING_MARKERS):

        return False

    if not any(marker in haystack for marker in _SAME_SUBJECT_MARKERS):

        return False

    delta = compile_edit_delta(text)

    return delta.get("edit_class") in _APPEARANCE_EDIT_CLASSES
