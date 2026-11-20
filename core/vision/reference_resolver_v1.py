# ==========================================================
# ArchitectOS Image Reference Resolver v1
#
# VISION_IMAGE_REGISTRY_04
#
# Deterministic resolution of user references to images that already
# exist in the session registry, so the user never has to download
# and re-upload a render they already have.
#
# Supported (Persian + English)
#   active     : همین عکس / این تصویر / this image
#   last_render: رندر قبلی / آخرین رندر / previous render
#   last_image : عکس قبلی / آخرین عکس / last image
#   ordinal    : عکس دوم / تصویر سوم / second image
#
# Rules
#   - resolve ONLY within the current session
#   - never guess between multiple plausible images
#   - ambiguous / missing -> unresolved (caller asks for clarification)
#   - first matching rule wins (specific -> general)
# ==========================================================


from __future__ import annotations


import re


CONTRACT = "ImageReferenceResolutionV1"
VERSION = "1.0"


# ==========================================================
# IMAGE REFERENCE PATTERNS  (ordered: most specific first)
# ==========================================================

_ORDINAL_WORDS = {

    # persian
    "اول": 1, "یکم": 1, "اولین": 1,
    "دوم": 2, "دومین": 2,
    "سوم": 3, "سومین": 3,
    "چهارم": 4, "چهارمین": 4,
    "پنجم": 5, "پنجمین": 5,
    "ششم": 6, "هفتم": 7, "هشتم": 8, "نهم": 9, "دهم": 10,

    # english
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,

    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5,
    "6th": 6, "7th": 7, "8th": 8, "9th": 9, "10th": 10,
}


_ORDINAL_NOUNS = (
    "عکس", "تصویر", "رندر", "نگاره",
    "image", "picture", "photo", "render",
)


_ORDINAL_DIGIT_RE = re.compile(
    r"(?:عکس|تصویر|رندر|image|picture|photo|render)\s*(?:شماره\s*)?(\d{1,2})\b"
    r"|(\d{1,2})\s*(?:مین)?\s*(?:عکس|تصویر|رندر|image|picture|photo|render)",
    re.IGNORECASE,
)


_ORDINAL_WORD_RE = re.compile(
    r"(?:عکس|تصویر|رندر|image|picture|photo|render)\s*(?:شماره\s*)?([A-Za-z\u0600-\u06FF]+)"
    r"|([A-Za-z\u0600-\u06FF]+)\s*(?:عکس|تصویر|رندر|image|picture|photo|render)",
    re.IGNORECASE,
)


# ----------------------------------------------------------
# rule table: (kind, patterns)
# ----------------------------------------------------------

_REFERENCE_RULES = (

    # ---- last render (specific) ----
    ("last_render", (
        "رندر قبلی", "رندر آخر", "آخرین رندر", "رندر اخیر",
        "رندر پیشین", "رندر قبل",
        "previous render", "last render", "latest render",
        "the last render", "prior render",
    )),

    # ---- last uploaded image ----
    ("last_uploaded", (
        "عکس آپلود", "تصویر آپلود", "آخرین آپلود", "عکس ارسالی",
        "last uploaded", "last upload", "uploaded image",
    )),

    # ---- previous / last image (generic) ----
    ("last_image", (
        "عکس قبلی", "تصویر قبلی", "عکس آخر", "آخرین عکس",
        "آخرین تصویر", "عکس اخیر", "تصویر اخیر", "عکس قبل",
        "previous image", "previous picture", "last image",
        "last picture", "last photo", "previous photo",
    )),

    # ---- active / deictic image ----
    ("active", (
        "همین عکس", "همین تصویر", "همین رندر", "همین نگاره",
        "این عکس", "این تصویر", "این رندر",
        "عکس فعلی", "تصویر فعلی", "عکس بالا", "تصویر بالا",
        "this image", "this picture", "this photo", "this render",
        "current image", "the image above", "image above",
    )),
)


# ----------------------------------------------------------
# region / deictic element phrases (NOT image references)
# ----------------------------------------------------------

REGION_ELEMENTS = (

    ("window", ("پنجره", "پنجره ها", "پنجره‌ها", "window", "windows", "glazing")),

    ("wall", ("دیوار", "دیوارها", "wall", "walls")),

    ("door", ("در ", "درب", "door", "doors")),

    ("balcony", ("بالکن", "تراس", "balcony", "terrace")),

    ("column", ("ستون", "ستون ها", "column", "columns", "pillar")),

    ("facade", ("نما", "نمای", "facade", "façade")),

    ("floor", ("کف", "کفپوش", "floor surface", "flooring")),

    ("ceiling", ("سقف", "ceiling")),

    ("roof", ("بام", "روف", "roof")),

    ("stair", ("پله", "راه پله", "stair", "stairs", "staircase")),

    ("entrance", ("ورودی", "entrance", "entry")),

    ("region", (
        "قسمت", "بخش", "ناحیه", "منطقه", "جای",
        "part", "area", "section", "region", "zone",
    )),
)


_DEICTIC_PREFIXES = (
    "این", "همین", "آن", "این‌", "همین‌",
    "this", "that", "the", "these", "those",
)


# ----------------------------------------------------------
# COLLOQUIAL / BARE DEICTICS  (IMAGE_TO_IMAGE_05)
#
# "همینو" / "اینو" are the colloquial contractions of
# "همین را" / "این را" and are specific enough to match directly.
#
# Bare "همین" / "این" are extremely common in Persian, so they only
# count as an image reference when the message ALSO carries an edit
# signal ("این رو شب کن"). This keeps normal chat from hijacking.
# ----------------------------------------------------------

_COLLOQUIAL_ACTIVE = (
    "همینو", "اینو", "همین‌و", "این‌و", "همین رو", "این رو",
    "همینو شب", "اینو شب",
)

_BARE_DEICTIC = (
    "همین", "این", "همون", "اون",
)


def _match_colloquial_deictic(text):

    for phrase in _COLLOQUIAL_ACTIVE:

        if phrase in text:

            return phrase

    return None


def _match_bare_deictic_with_edit_signal(text):

    padded = " " + text + " "

    candidates = [
        token for token in _BARE_DEICTIC
        if (" " + token + " ") in padded
    ]

    if not candidates:

        return None

    try:

        from core.vision.image_intent_v1 import has_edit_signal

        has_edit, _ = has_edit_signal(text)

    except Exception:

        has_edit = False

    if not has_edit:

        return None

    return candidates[0]



def _has(text, phrase):

    return phrase in text



def _match_rule(text):

    for kind, patterns in _REFERENCE_RULES:

        for pattern in patterns:

            if _has(text, pattern):

                return kind, pattern

    return None, None



def _match_ordinal(text):

    match = _ORDINAL_DIGIT_RE.search(text)

    if match:

        value = match.group(1) or match.group(2)

        if value:

            try:

                return int(value), match.group(0).strip()

            except ValueError:

                pass

    match = _ORDINAL_WORD_RE.search(text)

    if match:

        word = (match.group(1) or match.group(2) or "").strip().lower()

        if word in _ORDINAL_WORDS:

            return _ORDINAL_WORDS[word], match.group(0).strip()

    return None, None



def is_region_reference(text):

    lowered = " " + str(text or "").lower() + " "

    for element, phrases in REGION_ELEMENTS:

        for phrase in phrases:

            if phrase.strip() and phrase in lowered:

                for prefix in _DEICTIC_PREFIXES:

                    if (prefix + " " + phrase) in lowered:

                        return True, element, phrase

                    if (prefix + phrase) in lowered and prefix in ("این", "همین", "this", "that"):

                        return True, element, phrase

    return False, None, None



# ==========================================================
# RESOLUTION
# ==========================================================

def resolve_reference(text, session_id, registry=None):
    """Resolve a user reference to a registered session image."""

    if registry is None:

        from core.vision.image_registry_v1 import image_registry

        registry = image_registry


    lowered = " ".join(str(text or "").lower().split())


    base = {

        "contract": CONTRACT,
        "version": VERSION,

        "session_id": str(session_id),

        "target_image_id": None,
        "target_ordinal": None,
        "target_phrase": None,
        "reference_kind": None,

        "candidates": [],

    }


    if not lowered:

        base["status"] = "not_a_reference"
        base["reason"] = "empty_text"

        return base


    total = registry.count(session_id)


    # ------------------------------------------------------
    # ORDINAL (checked first: "عکس دوم" must not match "عکس")
    # ------------------------------------------------------

    ordinal, phrase = _match_ordinal(lowered)

    if ordinal is not None:

        if total == 0:

            base["status"] = "unresolved"
            base["reason"] = "no_images_in_session"
            base["reference_kind"] = "ordinal"
            base["target_ordinal"] = ordinal
            base["target_phrase"] = phrase

            return base

        record = registry.by_ordinal(session_id, ordinal)

        if record is None:

            base["status"] = "unresolved"
            base["reason"] = "ordinal_out_of_range"
            base["reference_kind"] = "ordinal"
            base["target_ordinal"] = ordinal
            base["target_phrase"] = phrase
            base["candidates"] = [
                r["image_id"] for r in registry.list(session_id)
            ]

            return base

        base["status"] = "resolved"
        base["reference_kind"] = "ordinal"
        base["target_ordinal"] = ordinal
        base["target_phrase"] = phrase
        base["target_image_id"] = record["image_id"]
        base["candidates"] = [record["image_id"]]

        return base


    # ------------------------------------------------------
    # KEYWORD RULES
    # ------------------------------------------------------

    kind, phrase = _match_rule(lowered)


    # ------------------------------------------------------
    # COLLOQUIAL / BARE DEICTICS (IMAGE_TO_IMAGE_05)
    # ------------------------------------------------------

    if kind is None:

        colloquial = _match_colloquial_deictic(lowered)

        if colloquial:

            kind, phrase = "active", colloquial

        else:

            bare = _match_bare_deictic_with_edit_signal(lowered)

            if bare:

                kind, phrase = "active", bare


    if kind is None:

        base["status"] = "not_a_reference"
        base["reason"] = "no_reference_phrase"

        return base


    if total == 0:

        base["status"] = "unresolved"
        base["reason"] = "no_images_in_session"
        base["reference_kind"] = kind
        base["target_phrase"] = phrase

        return base


    record = None


    if kind == "active":

        record = registry.active(session_id)

        if record is None:

            # no explicit active flag -> fall back to most recent
            record = registry.last(session_id)

    elif kind == "last_render":

        record = registry.last_render(session_id)

        if record is None:

            base["status"] = "unresolved"
            base["reason"] = "no_render_in_session"
            base["reference_kind"] = kind
            base["target_phrase"] = phrase
            base["candidates"] = [
                r["image_id"] for r in registry.list(session_id)
            ]

            return base

    elif kind == "last_uploaded":

        record = registry.last_uploaded(session_id)

        if record is None:

            base["status"] = "unresolved"
            base["reason"] = "no_upload_in_session"
            base["reference_kind"] = kind
            base["target_phrase"] = phrase

            return base

    else:

        record = registry.last(session_id)


    if record is None:

        base["status"] = "unresolved"
        base["reason"] = "no_matching_image"
        base["reference_kind"] = kind
        base["target_phrase"] = phrase

        return base


    base["status"] = "resolved"
    base["reference_kind"] = kind
    base["target_phrase"] = phrase
    base["target_image_id"] = record["image_id"]
    base["target_ordinal"] = record["ordinal"]
    base["candidates"] = [record["image_id"]]

    return base



# ==========================================================
# REGION / DEICTIC ELEMENT REFERENCE
# ==========================================================

def resolve_region_reference(
    text,
    target_image_id=None,
    understanding=None,
):
    """Build a grounded region reference. Never fabricates a bbox."""

    is_region, element, phrase = is_region_reference(text)


    result = {

        "contract": "ImageRegionReferenceV1",
        "version": VERSION,

        "target_image_id": target_image_id,
        "target_phrase": phrase,
        "candidate_element_type": element,

        "region": None,
        "bbox": None,

        "confidence": "LOW",
        "grounded": False,

        "unresolved": [],

    }


    if not is_region:

        result["status"] = "not_a_region_reference"
        result["unresolved"].append("no_deictic_element_phrase")

        return result


    result["status"] = "unresolved"


    if target_image_id is None:

        result["unresolved"].append("no_target_image")

        return result


    supports_grounding = False

    if isinstance(understanding, dict):

        supports_grounding = bool(
            (understanding.get("safety") or {}).get(
                "supports_region_grounding"
            )
        )


    # does the analysis actually confirm this element is visible?
    confirmed = False

    if isinstance(understanding, dict) and element:

        blob = " ".join(

            (understanding.get("architectural_elements") or [])
            + (understanding.get("observed") or [])

        ).lower()

        confirmed = element in blob or phrase in blob


    if confirmed:

        result["confidence"] = "MEDIUM"


    if not supports_grounding:

        result["unresolved"].append("no_region_grounding")

    else:

        result["unresolved"].append("provider_grounding_not_returned")


    if not confirmed:

        result["unresolved"].append("element_not_confirmed_in_analysis")


    if confirmed and supports_grounding:

        result["status"] = "grounded"


    return result
