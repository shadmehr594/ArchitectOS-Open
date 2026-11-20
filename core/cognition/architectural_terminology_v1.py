# ==========================================================
# ArchitectOS Architectural Terminology Normalization v1
#
# CHAT_LANGUAGE_02
#
# Deterministic, local, non-LLM architectural terminology
# normalization for the Persian / English / mixed chat path.
#
# Purpose
#   Guarantee that architectural concepts survive the Persian ->
#   English transition used by the downstream image/render prompt,
#   WITHOUT introducing a blind literal translator.
#
#   This module is a TERMINOLOGY layer, not an intent interpreter.
#   Intent interpretation remains owned by the canonical
#   PersianArchitecturalUnderstanding + ArchitecturalPromptCompiler
#   pair.  This layer only guarantees concept coverage.
#
# Covered concept families (required by CHAT_LANGUAGE_02):
#   facade / material / light / style / camera angle /
#   interior space / exterior space (+ render intent + building type)
#
# Design rules
#   - deterministic first: longest / most specific phrase wins
#   - original user text is never mutated or replaced
#   - no provider calls in the deterministic path
#   - the LLM is used ONLY as a single bounded last-resort assist
#     when the deterministic path produced nothing usable
# ==========================================================


from __future__ import annotations

import re

from core.chat.negation_scope_v1 import prohibition_spans


CONTRACT = "ArchitecturalTerminologyV1"
VERSION = "1.0"



# ==========================================================
# TERMINOLOGY TABLE
#
# (canonical_english, (patterns...))
#
# ORDER MATTERS: more specific / longer phrases must come first,
# because matching is first-match-wins per canonical entry.
# ==========================================================

TERMINOLOGY = (

    # ------------------------------------------------------
    # FACADE ORIENTATION  (must precede the generic "facade")
    # ------------------------------------------------------

    ("south facade", ("نمای جنوبی", "نمای جنوب", "south facade", "southern facade")),
    ("north facade", ("نمای شمالی", "نمای شمال", "north facade", "northern facade")),
    ("east facade", ("نمای شرقی", "نمای شرق", "east facade", "eastern facade")),
    ("west facade", ("نمای غربی", "نمای غرب", "west facade", "western facade")),
    ("main facade", ("نمای اصلی", "نمای روبرو", "main facade", "principal facade")),
    ("rear facade", ("نمای پشتی", "نمای عقب", "rear facade", "back facade")),

    # ------------------------------------------------------
    # FACADE (generic)
    # ------------------------------------------------------

    ("facade", ("نمای", "نماي", "نما", "facade", "façade")),

    # ------------------------------------------------------
    # MATERIAL
    # ------------------------------------------------------

    ("material", ("متریال", "متریالش", "متریال ها", "مصالح", "material", "materials")),
    ("glass facade", ("نمای شیشه", "شیشه ای", "شیشه‌ای", "glazed facade", "glass facade")),
    ("Qazaghi brick detailing", ("آجر قزاقی", "آجرقزاقی", "qazaghi brick", "qazaqi brick")),
    ("architectural tilework", ("کاشی‌کاری", "کاشی کاری", "کاشیکاری", "architectural tilework", "glazed tilework")),
    ("glass", ("شیشه", "glass")),
    ("stone", ("سنگ", "stone")),
    ("brick", ("آجر", "brick")),
    ("wood", ("چوب", "ترمووود", "wood", "timber")),
    ("concrete", ("بتن", "concrete")),
    ("metal", ("فلز", "metal", "steel")),
    ("travertine", ("تراورتن", "travertine")),

    # ------------------------------------------------------
    # LIGHT
    # ------------------------------------------------------

    ("natural lighting", ("نور طبیعی", "نور روز", "روشنایی روز", "نور خورشید", "natural light", "natural lighting", "daylight")),
    ("sunset lighting", ("نور غروب", "نور گرگ و میش", "نور گرگ‌ومیش", "نمای غروب", "در غروب", "موقع غروب", "هنگام غروب", "غروب", "sunset", "sunset light", "sunset lighting", "golden hour")),
    ("sunrise lighting", ("نور طلوع", "نمای طلوع", "در طلوع", "طلوع", "sunrise", "sunrise light", "sunrise lighting")),
    # IMAGE_TO_IMAGE_05 — imperative forms ("شب کن" = make it night) so an
    # edit instruction actually produces compiled prompt content.
    ("night lighting", ("نور شب", "نورپردازی شب", "نورپردازی شبانه", "نمای شب", "در شب", "شبانه", "حالت شب", "زمان شب", "رندر شب", "شب رندر", "شب کن", "شبش کن", "شب بشه", "شب شه", "شبانه کن", "شب باشد", "night", "night lighting", "night light", "make it night")),
    # V4.3A — M6. Time-of-day vocabulary the terminology layer did not carry.
    # Patterns are deliberately CONSTRUCTIONS, never the bare word: "morning"
    # alone is a greeting ("good morning") and must not become an
    # architectural signal.
    ("morning lighting", ("morning light", "morning lighting", "in the morning", "early morning light", "نور صبح", "صبح زود", "هنگام صبح", "صبح کن", "صبح بشه", "صبح شه")),
    ("noon lighting", ("noon light", "noon lighting", "at noon", "high noon", "midday light", "نور ظهر", "هنگام ظهر", "نیمروز", "ظهر کن", "ظهر بشه", "ظهر شه")),
    ("dusk lighting", ("dusk", "twilight", "blue hour", "گرگ‌ومیش", "گرگ و میش")),
    ("artificial lighting", ("نور مصنوعی", "نورپردازی مصنوعی", "artificial light", "artificial lighting")),
    ("lighting design", ("نورپردازی", "lighting design", "lighting scheme")),
    ("warm lighting", ("نور گرم", "نور ملایم گرم", "warm light", "warm lighting")),
    ("soft lighting", ("نور ملایم", "soft light", "soft lighting")),
    ("lighting", ("نور", "light", "lighting")),

    # ------------------------------------------------------
    # STYLE
    # ------------------------------------------------------

    ("Iranian brick style", ("نمای آجری ایرانی", "آجرکاری ایرانی", "iranian brick", "persian brick")),
    ("traditional Iranian style", ("سنتی ایرانی", "معماری ایرانی", "iranian traditional", "persian architecture", "iranian architecture")),
    ("Islamic architectural style", ("معماری اسلامی", "islamic architecture")),
    ("Beaux-Arts style", ("بوزار", "beaux arts", "beaux-arts")),
    ("Second Empire style", ("امپراتوری دوم", "هوسمان", "second empire", "haussmann")),
    ("French Provincial style", ("پروانس", "روستایی فرانسه", "french provincial", "provencal")),
    ("French Classical style", ("کلاسیک فرانسوی", "نمای فرانسوی", "french classical")),
    ("modern style", ("سبک مدرن", "مدرن", "معاصر", "modern style", "modern", "contemporary")),
    ("classical style", ("سبک کلاسیک", "کلاسیک", "classical style", "classic style")),
    ("minimal style", ("سبک مینیمال", "مینیمال", "مینیمالیستی", "minimal style", "minimalist")),
    ("traditional style", ("سبک سنتی", "سنتی", "traditional style")),
    ("industrial style", ("سبک صنعتی", "صنعتی", "industrial style")),
    ("neoclassical style", ("سبک نئوکلاسیک", "نئوکلاسیک", "نوکلاسیک", "neoclassical")),
    ("luxury style", ("سبک لوکس", "لاکچری", "لوکس", "luxury style", "luxurious")),
    ("style", ("سبک", "استایل", "style")),

    # ------------------------------------------------------
    # ARCHITECTURAL ELEMENTS / EXPLICIT SITE FEATURES
    # ------------------------------------------------------

    ("orsi windows", ("پنجره ارسی", "پنجره‌های ارسی", "ارسی", "orosi window", "orsi window")),
    ("brick lattice screens", ("آجر مشبک", "شبکه آجری", "brick lattice", "brick screen")),
    ("geometric brick relief", ("آجرکاری برجسته", "نقش برجسته آجری", "geometric brick relief")),
    ("deep brick reveals", ("بازشوی عمیق آجری", "قاب عمیق آجری", "deep brick reveal")),
    ("brick paving", ("کف‌سازی آجری", "کف سازی آجری", "کف آجری", "brick paving")),
    ("plants", ("گیاهان", "گیاه", "گلدان", "plants", "planting", "potted plants")),
    ("water feature", ("آب‌نما", "آبنما", "water feature")),

    # ------------------------------------------------------
    # CAMERA ANGLE / VIEW
    # ------------------------------------------------------

    ("low camera angle", ("زاویه پایین", "از پایین", "low angle", "low camera angle")),
    ("high camera angle", ("زاویه بالا", "از بالا", "high angle", "high camera angle")),
    ("eye level view", ("زاویه چشم", "eye level", "eye-level view")),
    ("aerial view", ("نمای هوایی", "هوایی", "aerial view", "bird's eye view", "birds eye view")),
    ("perspective view", ("پرسپکتیو", "نمای پرسپکتیو", "perspective view")),
    ("frontal view", ("نمای روبرو", "روبرو", "frontal view", "front view")),
    ("three quarter view", ("سه چهارم", "سه ربع", "سه‌ربع", "three quarter view", "three-quarter view", "3/4 view")),
    ("camera angle", ("زاویه دوربین", "زاویه دید", "camera angle", "view angle", "camera view")),
    ("framing", ("کادر", "کادربندی", "framing", "composition framing")),

    # ------------------------------------------------------
    # INTERIOR / EXTERIOR SPACE
    # ------------------------------------------------------

    ("interior space", ("فضای داخلی", "داخلی", "فضای درونی", "interior space", "interior")),
    ("exterior space", ("فضای خارجی", "خارجی", "محوطه", "exterior space", "exterior")),
    ("living room", ("نشیمن", "اتاق نشیمن", "living room")),
    ("bedroom", ("اتاق خواب", "bedroom")),
    ("kitchen", ("آشپزخانه", "kitchen")),
    ("lobby", ("لابی", "ورودی داخلی", "lobby")),
    ("courtyard", ("حیاط", "حیاط مرکزی", "courtyard")),
    ("landscape", ("محوطه سازی", "محوطه‌سازی", "landscape", "landscaping")),

    # ------------------------------------------------------
    # RENDER INTENT / QUALITY
    # ------------------------------------------------------

    ("photorealistic render", ("رندر واقع گرایانه", "رندر واقع‌گرایانه", "رئال", "واقع گرایانه", "واقع‌گرایانه", "photorealistic render", "photorealistic")),
    ("architectural render", ("رندر", "رندرگیری", "رندر بگیر", "architectural render", "render")),
    ("architectural visualization", ("ویژوال", "ویژوالیزیشن", "archviz", "architectural visualization")),
    ("3d visualization", ("سه بعدی", "3d", "three dimensional", "3d visualization")),
    ("night render", ("رندر شب", "نمای شبانه", "night render")),
    ("day render", ("نمای روز", "در روز", "رندر روز", "حالت روز", "زمان روز", "طی روز", "در طول روز", "صبح", "روز کن", "روزش کن", "روز بشه", "روز شه", "daytime", "during the day", "day render", "daylight render", "make it day")),
    ("high quality", ("کیفیت بالا", "high quality", "highly detailed")),
    ("exterior view", ("نمای خارجی", "exterior view")),

    # ------------------------------------------------------
    # BUILDING TYPE
    # ------------------------------------------------------

    ("villa", ("ویلا", "ویلایی", "villa")),
    ("apartment building", ("آپارتمان", "apartment building", "apartment")),
    ("tower", (
        "برج", "tower", "high-rise", "high rise", "skyscraper",
        "بلندمرتبه", "بلند مرتبه",
    )),
    ("complex", ("مجتمع", "complex")),
    ("building", ("ساختمان", "ساختمون", "بنا", "building")),
)


# Concept families used for coverage reporting / tests.
FAMILIES = {

    "facade": (
        "south facade", "north facade", "east facade", "west facade",
        "main facade", "rear facade", "facade",
    ),

    "material": (
        "material", "glass facade", "Qazaghi brick detailing",
        "architectural tilework", "glass", "stone", "brick",
        "wood", "concrete", "metal", "travertine",
    ),

    "light": (
        "natural lighting", "sunset lighting", "sunrise lighting",
        "night lighting", "artificial lighting", "lighting design",
        "warm lighting", "soft lighting", "lighting",
        # V4.3A — M6.
        "morning lighting", "noon lighting", "dusk lighting",
    ),

    "style": (
        "Iranian brick style", "traditional Iranian style",
        "Islamic architectural style", "Beaux-Arts style",
        "Second Empire style", "French Provincial style",
        "French Classical style", "modern style", "classical style", "minimal style",
        "traditional style", "industrial style", "neoclassical style",
        "luxury style", "style",
    ),

    "camera": (
        "low camera angle", "high camera angle", "eye level view",
        "aerial view", "perspective view", "frontal view",
        "three quarter view", "camera angle", "framing",
    ),

    "space": (
        "interior space", "exterior space", "living room", "bedroom",
        "kitchen", "lobby", "courtyard", "landscape",
    ),

    "element": (
        "orsi windows", "brick lattice screens", "geometric brick relief",
        "deep brick reveals", "brick paving", "plants", "water feature",
    ),

    "render": (
        "photorealistic render", "architectural render",
        "architectural visualization", "3d visualization",
        "night render", "day render", "high quality", "exterior view",
    ),
}


# Canonical english -> family (reverse index, built once).
_TERM_FAMILY = {
    term: family
    for family, terms in FAMILIES.items()
    for term in terms
}


# Terms that mean the request is render/visual oriented.
_RENDER_TRIGGER_FAMILIES = ("render", "camera", "light")


# Terms that count as architectural signal even without an explicit
# render trigger (a facade / material / space request is architectural).
_ARCHITECTURAL_FAMILIES = (
    "facade", "material", "light", "style", "camera", "space", "element",
)


# Short Persian nouns that are unsafe as raw substrings: ``برج`` occurs in
# ``برجسته`` (relief), and ``نما`` occurs in ``آب‌نما`` (water feature).
_WHOLE_TOKEN_PATTERNS = {"برج", "نما"}


def _pattern_present(haystack, pattern):
    lowered = str(pattern or "").lower()
    if lowered in _WHOLE_TOKEN_PATTERNS:
        return re.search(
            r"(?<![\w\u200c-])" + re.escape(lowered) + r"(?![\w\u200c-])",
            haystack,
        ) is not None
    return lowered in haystack



# ==========================================================
# DETERMINISTIC MATCHING
# ==========================================================

def _normalize_for_match(text):
    """Lowercase + collapse whitespace. Never mutates the caller text."""

    return " ".join(
        str(text or "").lower().split()
    )


# ==========================================================
# RENDER_INTENT_RELIABILITY_V1 — NEGATION AWARENESS
#
# `extract_terms` matched raw substrings, so a term the user explicitly
# REJECTED was emitted as an affirmative requirement. "true night, not dusk"
# produced both `night lighting` and `dusk lighting`, and the compiled prompt
# then asked for dusk while the instruction layer forbade it
# ("Do NOT use or repeat: dusk."). The rejection is already carried by
# `negations.rejected_span`; the terminology layer must simply not claim the
# same word as a requirement.
#
# A pattern only counts as present when at least one of its occurrences sits
# OUTSIDE a negation window, so "night, not dusk" keeps night and drops dusk.
# ==========================================================

_NEGATION_MARKERS = (
    "not ", "not,", "no ", "without ", "avoid ", "never ", "don't ", "do not ",
    "isn't ", "instead of ",
    "نه ", "نمی", "بدون ", "نشه", "نباشد", "نکن", "به جای ",
)

_NEGATION_WINDOW = 24


def _is_negated(haystack, pattern):
    """True when the OPERATIVE occurrence of `pattern` is negated.

    FACADE_STYLE_TRANSFER_FAILURE_CORRECTION_V1 — the previous rule required
    EVERY occurrence to sit in a negation window, so one descriptive mention
    un-forbade a material. Measured on the accepted facade request: it says
    "not a brick facade recolored beige" AND "No red/orange brick redesign",
    yet `brick` was still claimed as a REQUESTED material (node 206 carried
    "... the base., material, brick, natural lighting") because the target
    building is described as "the approved beige-brick residential building".
    The render then produced a brick facade.

    Two narrow refinements, no new vocabulary:

      * a HYPHEN-ATTACHED occurrence ("beige-brick") is a descriptor of the
        source building, never a requested material, so it is not affirmative;
      * among the remaining occurrences the LAST one is operative — a request
        that forbids a material after naming it has forbidden it, and one that
        asks for it last has asked for it.

    "night, not dusk" still keeps night and drops dusk. "Do not use brick on
    the ground floor; use brick on the upper floors" still keeps brick.
    """

    pattern = str(pattern or "").lower()

    if not pattern:
        return False

    positions = []
    start = haystack.find(pattern)

    while start != -1:
        positions.append(start)
        start = haystack.find(pattern, start + 1)

    if not positions:
        return False

    def _is_descriptor(index):
        # "beige-brick" / "stone-clad": the token qualifies a noun, it is not
        # an instruction to apply that material.
        return index > 0 and haystack[index - 1] == "-"

    def _in_negation_window(index):
        window = haystack[max(0, index - _NEGATION_WINDOW):index]
        return any(marker in window for marker in _NEGATION_MARKERS)

    def _in_prohibition_span(index):
        return any(
            low <= index < high
            for low, high in prohibition_spans(haystack)
        )

    operative = [index for index in positions if not _is_descriptor(index)]

    if not operative:
        # Every mention is a hyphenated descriptor: nothing was requested.
        return True

    return (
        _in_negation_window(operative[-1])
        or _in_prohibition_span(operative[-1])
    )


# ==========================================================
# RENDER_INTENT_RELIABILITY_V1 — "INTERIOR LIGHTS" IS NOT A ROOM
#
# `("interior space", (..., "interior"))` fired on the bare word, so
# "warm interior lights visible through the windows of an exterior building
# at night" produced BOTH `interior space` and `exterior space`. The preset
# resolver tests interior before night, so an exterior night building was
# rendered as an interior room (704x768, "camera inside the room").
#
# "Interior" that qualifies a LIGHT SOURCE describes illumination, not a
# space. The test is deliberately narrow: the light noun must sit next to the
# word, and an explicit space phrase always wins.
# ==========================================================

_INTERIOR_SPACE_PHRASES = ("interior space", "فضای داخلی", "فضای درونی")

_INTERIOR_WORDS = ("interior", "داخلی")

_LIGHT_NOUNS = (
    "light", "lights", "lighting", "illuminat", "glow", "lamp", "lit",
    "نور", "روشنایی",
)

_LIGHT_QUALIFIER_WINDOW = 14


def _interior_is_a_space(haystack):
    """False when every mention of "interior" qualifies a light source."""

    if any(phrase in haystack for phrase in _INTERIOR_SPACE_PHRASES):
        return True

    positions = []
    for word in _INTERIOR_WORDS:
        start = haystack.find(word)
        while start != -1:
            positions.append((start, word))
            start = haystack.find(word, start + 1)

    if not positions:
        return False

    for index, word in positions:
        before = haystack[max(0, index - _LIGHT_QUALIFIER_WINDOW):index]
        after = haystack[index + len(word):index + len(word) + _LIGHT_QUALIFIER_WINDOW]
        if not any(noun in before or noun in after for noun in _LIGHT_NOUNS):
            return True

    return False


def extract_terms(text):
    """Deterministically extract canonical architectural English terms.

    Returns a dict:
      matched          -> [{"canonical":..., "family":..., "evidence":...}]
      canonical_terms  -> ordered unique canonical english terms
      families         -> ordered unique families
      has_render_signal-> bool
      has_architectural_signal -> bool
    """

    haystack = _normalize_for_match(text)

    matched = []
    seen = set()

    for canonical, patterns in TERMINOLOGY:

        for pattern in patterns:

            if _pattern_present(haystack, pattern):

                # RENDER_INTENT_RELIABILITY_V1 — a rejected term is not a
                # requirement. Try the next pattern rather than claiming it.
                if _is_negated(haystack, pattern):

                    continue

                # RENDER_INTENT_RELIABILITY_V1 — "interior lights" is a light
                # source, not a room.
                if canonical == "interior space" and not _interior_is_a_space(haystack):

                    continue

                if canonical in seen:

                    break

                seen.add(canonical)

                matched.append({

                    "canonical": canonical,

                    "family": _TERM_FAMILY.get(canonical, "other"),

                    "evidence": pattern,

                })

                break

    # ``نئوکلاسیک`` contains ``کلاسیک``.  The more specific valid style owns
    # that span; retaining both would turn one explicit style into two intents.
    if "neoclassical style" in seen and "classical style" in seen:
        matched = [
            item for item in matched if item["canonical"] != "classical style"
        ]
        seen.discard("classical style")

    canonical_terms = [
        item["canonical"] for item in matched
    ]

    families = []

    for item in matched:

        if item["family"] not in families:

            families.append(item["family"])

    return {

        "matched": matched,

        "canonical_terms": canonical_terms,

        "families": families,

        "has_render_signal": any(
            f in families for f in _RENDER_TRIGGER_FAMILIES
        ),

        "has_architectural_signal": any(
            f in families for f in _ARCHITECTURAL_FAMILIES
        ),

    }



def build_terminology_prompt(term_result):
    """Deterministic English prompt fragment from extracted terms.

    Preserves concept coverage. Returns "" when nothing matched.
    """

    if not isinstance(term_result, dict):

        return ""

    terms = term_result.get("canonical_terms") or []

    if not terms:

        return ""

    # ------------------------------------------------------
    # Order for readability: subject -> material -> element -> light ->
    # style -> camera -> space -> render/quality
    # ------------------------------------------------------

    order = (
        "facade", "material", "element", "light", "style", "camera", "space",
        "render", "other",
    )

    buckets = {
        key: [] for key in order
    }

    for term in terms:

        family = _TERM_FAMILY.get(term, "other")

        buckets.setdefault(family, []).append(term)

    ordered = []

    for key in order:

        for term in buckets.get(key, []):

            if term not in ordered:

                ordered.append(term)

    return ", ".join(ordered)



# ==========================================================
# COMPILED PROMPT AUGMENTATION
# ==========================================================

def augment_compiled_prompt(compiled_positive, term_result):
    """Append deterministic term coverage to a compiled positive prompt.

    Deterministic, deduplicated, order-stable. The compiled prompt
    produced by the canonical compiler always stays authoritative and
    first; this only fills in concepts it did not express.
    """

    base = " ".join(
        str(compiled_positive or "").split()
    )

    fragment = build_terminology_prompt(term_result)

    if not fragment:

        return base

    lowered = base.lower()

    additions = [
        term
        for term in fragment.split(", ")
        if term and term.lower() not in lowered
    ]

    if not additions:

        return base

    if not base:

        return ", ".join(additions)

    return base + ", " + ", ".join(additions)



# ==========================================================
# BOUNDED LLM ASSIST  (single call, architectural only)
# ==========================================================

TRANSLATION_SYSTEM_INSTRUCTION = (
    "You are an architectural terminology translator. "
    "Translate the user's architectural request into a short ENGLISH "
    "image-generation prompt. "
    "Rules: keep architectural meaning exact; never invent features that "
    "are not in the request; never add camera or style choices that were "
    "not requested; output ONLY the English prompt with no explanation, "
    "no quotes and no bullet points."
)


def bounded_llm_translate(text, llm_callable=None):
    """ONE bounded LLM assist. Returns (prompt, error).

    Used only as a last resort when the deterministic architectural
    path produced nothing usable. Never retried, never looped.
    """

    if llm_callable is None:

        return None, "no_llm_callable"

    try:

        result = llm_callable(

            TRANSLATION_SYSTEM_INSTRUCTION
            + "\n\nREQUEST:\n"
            + str(text or "")

        )

    except Exception as e:

        return None, type(e).__name__ + ": " + str(e)

    if not result:

        return None, "empty_llm_response"

    cleaned = " ".join(
        str(result).split()
    ).strip().strip('"').strip()

    if not cleaned:

        return None, "empty_llm_response"

    return cleaned, None



# ==========================================================
# CANONICAL TERMINOLOGY STEP
# ==========================================================

def normalize_architectural_terms(text):
    """Entry point for the canonical language path."""

    result = extract_terms(text)

    result["contract"] = CONTRACT
    result["version"] = VERSION
    result["terminology_prompt"] = build_terminology_prompt(result)

    return result
