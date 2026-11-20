# ==========================================================
# ArchitectOS Image Intent Classifier v1
#
# VISION_IMAGE_REGISTRY_04
#
# Distinguishes what the user actually wants when an image is
# present in the conversation:
#
#   analyze   -> answer a question / describe the image
#   edit      -> modify the image (execution is Phase 05)
#   reference -> the user is pointing at an image to reuse later
#   upload_only -> image with no instruction
#
# Doctrine: an image + text message is NOT automatically an edit
# request.  Answering is non-destructive and is the safe default.
# ==========================================================


from __future__ import annotations


import os
import re


CONTRACT = "ImageIntentV1"
VERSION = "1.0"


INTENT_EDIT = "edit"
INTENT_ANALYZE = "analyze"
INTENT_REFERENCE = "reference"
INTENT_UPLOAD_ONLY = "upload_only"
# VISION_OBSERVATION_MODE_SEPARATION_V1 — a request for VISIBLE EVIDENCE
# ONLY. It is its own intent so the image path can answer with the
# observation contract instead of the architectural interpretation.
INTENT_OBSERVE = "observe"


# ==========================================================
# PERSIAN EDIT IMPERATIVES  (IMAGE_TO_IMAGE_05)
#
# Generated deterministically from approved appearance objects x
# change markers, e.g. "شب کن" / "سنگ کن" / "نورش رو".
# Bare nouns are NEVER edit signals on their own - a change marker
# is always required, so "چه رنگیه؟" stays a question.
# ==========================================================

_EDIT_OBJECTS = (
    "شب", "روز", "روشن", "تیره", "سنگ", "چوب", "شیشه",
    "متریال", "رنگ", "نور", "آجر", "بتن", "فلز",
)

_EDIT_MARKERS = (
    "کن", "کنید", "کنش", "بشه", "بشود", "شه", "عوض", "تغییر",
    "روشن‌تر", "تیره‌تر", "روشن تر", "تیره تر", "بده",
)

_EDIT_POSSESSIVE = (
    "ش رو", "شو", "ش را", "ش",
)


# Bare appearance nouns ("متریال" / "رنگ" / "نور") are only edit
# signals when the user marks the image as the OBJECT of the
# instruction ("اینو متریال" = "its material"). Object-marked
# contractions are used with imperatives, so questions such as
# "این عکس رنگش چیه؟" or "چه رنگیه؟" stay questions.
_BARE_APPEARANCE_NOUNS = (
    "متریال", "رنگ", "نور",
)

_OBJECT_ANCHORS = (
    "اینو", "همینو", "این رو", "همین رو", "این‌و", "همین‌و",
)


def _build_persian_edit_phrases():

    phrases = []

    for obj in _EDIT_OBJECTS:

        for marker in _EDIT_MARKERS:

            phrases.append(obj + " " + marker)

        for suffix in _EDIT_POSSESSIVE:

            phrases.append(obj + suffix + " " + "کن")

            phrases.append(obj + suffix + " " + "عوض")

    return tuple(
        dict.fromkeys(phrases)
    )


_PERSIAN_EDIT_PHRASES = _build_persian_edit_phrases()


# ----------------------------------------------------------
# EDIT signals (imperative modification of the image itself)
# ----------------------------------------------------------

_EDIT_PHRASES = (
    "ویرایش کن", "ویرایشش کن", "تغییر بده", "تغییرش بده", "عوض کن", "عوضش کن",
    "جایگزین کن", "حذف کن", "اضافه کن", "درستش کن", "اصلاح کن",
    "تبدیل کن", "تبدیلش کن", "بازطراحی کن", "رندر تولید کن", "رندر بگیر",
    # KNOWLEDGE_RECOVERY_01 — renovation/restoration imperatives were
    # missing, so "نمای ساختمان را بازسازی کن" produced no edit signal
    # and the turn never reached a render. Same imperative class as
    # "بازطراحی کن"; no new routing engine.
    "بازسازی کن", "بازسازی‌اش کن", "مرمت کن",
    "بدون تغییر فرم", "بدون تغییر", "روی این عکس", "روی همین عکس",
    "edit", "modify", "change the", "replace", "remove the", "add a",
    "restyle", "recolor", "retouch", "make it", "turn it into",
    "make the", "at night", "at daytime",
    # KNOWLEDGE_RUNTIME_CONNECTION_V2 — the Persian imperative "تبدیل کن" was
    # recognised but its English equivalent was not, so "Convert this facade
    # to neoclassical style" carried no edit signal at all and fell through to
    # the analysis path. These are the same imperative class, bounded to the
    # object-bearing forms.
    "convert this", "convert the", "convert it", "convert to",
    "transform this", "transform the",
) + _PERSIAN_EDIT_PHRASES


# These patterns cover natural Persian instructions where the attached image
# or facade is the grammatical object of an otherwise explicit edit command.
# They deliberately require an edit verb, so questions such as "این تصویر را
# تحلیل کن" continue to use the analysis path.
_PERSIAN_EDIT_PATTERNS = (
    re.compile(
        r"(?:این|همین)\s*(?:تصویر|عکس)\s*(?:را|رو)?\s+.*?"
        r"(?:تبدیل|تغییر|ویرایش|بازطراحی|بازسازی)\s*(?:ش\s*)?(?:کن|بده|کنید)"
    ),
    re.compile(
        r"نما\s*(?:را|رو)?\s+.*?"
        r"(?:تبدیل|تغییر|ویرایش|بازطراحی|بازسازی)\s*(?:ش\s*)?(?:کن|بده|کنید)"
    ),
)


# R4_PHOTO_SAFE_CHAT_BRIDGE_V1 — PHOTOGRAPHIC COLOUR-BALANCE EDIT SIGNAL
#
# MEASURED DEFECT (CPU, deterministic):
#
#   "تراز رنگ این عکس را کمی گرم‌تر کن."
#       -> intent = reference, reason = reference_phrase_only
#   "Slightly warm the photographic colour balance ..."
#       -> intent = analyze,  reason = safe_default_analyze
#
# Both carry no edit signal at all, so neither ever reached the image-edit
# owner — the accepted PHOTO-02 capability was unreachable from chat for two
# of its three primary positive requests. Only the third reached the owner,
# and only by accident: its PRESERVATION clause ("بدون تغییر") happens to be
# listed in `_EDIT_PHRASES` as an edit signal.
#
# These patterns are deliberately NARROW. Each requires a global
# colour-balance noun AND a warmth term AND an imperative verb, so:
#
#   * a question ("تراز رنگ این عکس چیست؟" / "What is the colour balance?")
#     does not match — there is no warmth term and no imperative;
#   * a localized recolour ("Warm the sky in this photo") does not match —
#     there is no global colour-balance noun;
#   * a lighting request ("نور روز ... را گرم‌تر کن") does not match — its
#     subject is daylight, not the colour balance, and it keeps the existing
#     `lighting_change` / `warmer` contract.
#
# No new compiler and no new router: this only extends the vocabulary the
# EXISTING `has_edit_signal()` already consults.
_PHOTOGRAPHIC_BALANCE_EDIT_PATTERNS = (
    re.compile(
        r"(?:تراز[\s\u200c]*رنگ|تعادل[\s\u200c]*رنگ|رنگ[\s\u200c]*کلی|رنگ[\s\u200c]*عمومی)"
        r".{0,90}?(?:گرم[\s\u200c]*تر|گرمتر)"
        r".{0,40}?(?:کن|کنید|بده)"
    ),
    re.compile(
        r"(?:گرم[\s\u200c]*تر|گرمتر)"
        r".{0,90}?(?:تراز[\s\u200c]*رنگ|تعادل[\s\u200c]*رنگ|رنگ[\s\u200c]*کلی|رنگ[\s\u200c]*عمومی)"
        r".{0,40}?(?:کن|کنید|بده)"
    ),
    re.compile(r"(?:warm|warmer).{0,60}?(?:colour|color)\s*balance"),
    re.compile(r"(?:colour|color)\s*balance.{0,60}?(?:warm|warmer)"),
)


# ----------------------------------------------------------
# UNSUPPORTED PRECISE-GEOMETRY EDITS  (IMAGE_TO_IMAGE_05)
#
# Relocating / resizing openings or massing with stated dimensions is
# NOT a supported conversational edit. It must be refused truthfully
# rather than silently attempted.
# ----------------------------------------------------------

_GEOMETRY_VERBS = (
    "ببر", "جابه‌جا", "جابجا", "منتقل", "حرکت بده", "حرکتش بده",
    "بچرخون", "بچرخان", "بزرگ‌تر کن", "بزرگتر کن", "کوچک‌تر کن", "کوچکتر کن",
    "بلندتر کن", "کوتاه‌تر کن", "کوتاهتر کن", "بازتر کن", "تنگ‌تر کن", "تنگتر کن",
    "بکش راست", "بکش چپ", "ببر راست", "ببر چپ",
    "move", "shift", "relocate", "resize", "scale", "rotate", "translate",
    "widen", "narrow", "extend",
)


# ----------------------------------------------------------
# LOCALIZED ARCHITECTURAL COMPONENTS  (IMAGE_TO_IMAGE_05)
#
# A dimensioned / localized operation on ONE named component
# ("این پنجره رو حذف کن") is a precise geometric edit even when no
# numeric distance is stated. Global appearance edits
# ("نما رو سنگ کن") must never be caught here, so a component alone
# is not enough - a localized operation is always required.
# ----------------------------------------------------------

_LOCALIZED_COMPONENTS = (
    "پنجره", "پنجره‌ها", "پنجره ها", "بازشو", "بازشوها",
    "دیوار", "دیوارها", "درب", "در ورودی", "در رو", "این در", "همین در",
    "ستون", "ستون‌ها", "بالکن", "تراس", "سقف", "بام", "روف",
    "پله", "راه پله", "ورودی", "کف", "کفپوش", "قرنیز", "جان‌پناه",
    "window", "windows", "opening", "openings", "wall", "walls",
    "door", "doors", "column", "columns", "pillar", "balcony",
    "terrace", "ceiling", "roof", "stair", "stairs", "staircase",
    "entrance", "floor slab", "skirting",
)

_LOCALIZED_OPS = (
    "حذف کن", "حذفش کن", "پاک کن", "بردار", "اضافه کن", "اضافه‌اش کن",
    "جایگزین کن", "عوض کن", "جابه‌جا کن", "جابجا کن", "منتقل کن",
    "ببر", "بکش", "بچرخون", "بچرخان", "بزرگ کن", "بزرگ‌تر کن",
    "بزرگتر کن", "کوچک کن", "کوچک‌تر کن", "کوچکتر کن", "بلندتر کن",
    "کوتاه‌تر کن", "کوتاهتر کن", "بازتر کن", "تنگ‌تر کن", "تنگتر کن",
    "remove the", "delete the", "add a", "add the", "replace the",
    "move the", "shift the", "relocate the", "resize the", "enlarge",
    "shrink", "rotate the", "translate the", "widen the", "narrow the",
    "remove this", "remove that", "delete this", "delete that",
    "move this", "move that", "resize this", "resize that",
    "enlarge this", "shrink this", "rotate this", "shift this",
    "replace this",
)

_DIMENSION_WORDS = (
    "سانتی‌متر", "سانتیمتر", "سانتی متر", "سانتی", "سانت",
    "میلی‌متر", "میلیمتر", "میلی متر", "متر", "cm", "mm",
)


# ----------------------------------------------------------
# CLASSICAL_REDESIGN_SCOPE_V1 — localized vs global scope
#
# Tier 2 used to refuse whenever a component noun and an operation
# substring co-occurred. That conflates two different requests:
#
#   "Remove this particular column."          -> localized geometry
#   "Redesign the entire facade in an ornate  -> global architectural
#    Roman-classic language; replace the         redesign (authorised)
#    brick character with stone and add
#    compatible columns and an entrance."
#
# The second is the normal way to describe a facade redesign, and it was
# being refused for naming its own components. The discriminator is SCOPE,
# not vocabulary: a localized refusal needs a signal that the request points
# at ONE component.
#
# Two op classes are therefore separated:
#
#   STRICT  — destructive/positional operations that are local by nature
#             ("remove", "move", "enlarge"). These localize on their own and
#             are never overridden by global redesign language.
#   GENERIC — operations that are equally at home in a global redesign
#             ("replace", "add"). These localize only when the request also
#             carries a deictic anchor or a stated dimension, and never when
#             the request is explicitly facade/building-wide.
# ----------------------------------------------------------

_LOCALIZED_OPS_STRICT = (
    "حذف کن", "حذفش کن", "پاک کن", "بردار",
    "جابه‌جا کن", "جابجا کن", "منتقل کن",
    "ببر", "بکش", "بچرخون", "بچرخان",
    "بزرگ کن", "بزرگ‌تر کن", "بزرگتر کن",
    "کوچک کن", "کوچک‌تر کن", "کوچکتر کن",
    "بلندتر کن", "کوتاه‌تر کن", "کوتاهتر کن",
    "بازتر کن", "تنگ‌تر کن", "تنگتر کن",
    "remove the", "delete the", "move the", "shift the", "relocate the",
    "resize the", "enlarge", "shrink", "rotate the", "translate the",
    "widen the", "narrow the",
    # demonstrative forms ("Remove this particular column") — a deictic plus a
    # destructive verb is unambiguously one component.
    "remove this", "remove that", "delete this", "delete that",
    "move this", "move that", "resize this", "resize that",
    "enlarge this", "shrink this", "rotate this", "shift this",
)

_LOCALIZED_OPS_GENERIC = (
    "اضافه کن", "اضافه‌اش کن", "جایگزین کن", "عوض کن",
    "add a", "add the", "replace the", "replace this",
)

# Deictic / partitive anchors: the request points at ONE thing.
_LOCALIZING_ANCHORS = (
    "this", "that", "these", "those", "particular", "only this", "only the",
    "the left", "the right", "its ", "its",
    "این", "همین", "آن", "همان", "سمت چپ", "سمت راست",
)

# Explicit facade/building-wide scope language.
_GLOBAL_SCOPE_TERMS = (
    "facade", "façade", "building", "whole", "entire", "overall",
    "redesign", "restyle", "transform", "renovation", "renovate",
    "architectural language", "character", "cladding", "style",
    "نما", "نمای", "کل ساختمان", "ساختمان", "بازطراحی",
)

_DIMENSION_NUMBER_RE = re.compile(
    r"\d+(\.\d+)?\s*"
    r"(cm|mm|سانتی‌متر|سانتیمتر|سانتی\s*متر|سانتی|سانت|"
    r"میلی‌متر|میلیمتر|میلی\s*متر|متر)\b",
    re.IGNORECASE,
)


# ----------------------------------------------------------
# PRECISE_EDIT_ROUTE_V1 — validated-mask route predicate
#
# A localized edit used to be refused unconditionally, because
# ArchitectOS had no route that could confine a change to one
# region. Such a route now exists and is the ONLY one: a
# caller-supplied selection mask on the Kontext graph, whose
# compositing node returns every pixel outside the mask from the
# source image unchanged.
#
# This predicate therefore answers a different question from the
# guard: not "is this a geometric edit?" but "is a validated
# localized route actually available for it?" It is the reuse of
# the existing validation, never a second one:
#
#   * the mask is the dict the request boundary BUILT AND
#     VALIDATED (`app.py` mask ingestion): a server-controlled
#     `filename` and the mask's measured `dimensions`. A bare
#     truthy string is NOT a mask — `bool("false")` is True, and a
#     filename string proves nothing was opened or measured;
#   * every mask reaching here was already proven to exist in the
#     ComfyUI input folder and to match the source image's
#     dimensions, because `app.py` refuses the request otherwise.
#     Those two fields are the evidence; no second validation and
#     no origin marker is required (the asset-name ingestion path
#     writes no marker, and requiring one would refuse a mask that
#     was validated);
#   * the graph must genuinely provide local editing, read from
#     the workflow itself by the existing capability contract.
#
# `kontext_edit` is read with the same strict normalization the
# request boundary uses (`app.py:1019`), never by truthiness.
# ----------------------------------------------------------

#: Mask `source` values written by the UPLOAD ingestion path. The
#: asset-name path (an existing ComfyUI input filename) validates the same
#: things but writes no `source`, so this is corroborating evidence only —
#: never a requirement, or every asset-name mask would be wrongly refused.
_VALIDATED_MASK_SOURCES = ("uploaded", "asset")

_KONTEXT_WORKFLOW = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "render", "workflows", "flux_kontext_edit.json",
)


def _mask_is_validated(mask):
    """True only for the mask representation validated ingestion produces.

    Both ingestion paths (`app.py`) converge on the same shape — a dict with a
    server-controlled `filename` and the mask's measured `dimensions` — because
    a mask is refused unless its file could be read and its size matched the
    source image. Those two fields are therefore the evidence:

      * `filename` must be a bare name, because a path-shaped value is
        rejected at the request boundary;
      * `dimensions` must be two positive integers, because they are only ever
        written after the mask file was actually opened and measured.

    A truthy string, a bare `{"filename": ...}` and any unmeasured dict all
    fail this, which is the point: a value that was never validated must be
    treated exactly like no mask at all.
    """

    if not isinstance(mask, dict):

        return False

    filename = str(mask.get("filename") or "").strip()

    if not filename:

        return False

    # the same path-shape rejection the request boundary applies
    if "/" in filename or "\\" in filename or filename in (".", ".."):

        return False

    dimensions = mask.get("dimensions")

    if not isinstance(dimensions, (list, tuple)) or len(dimensions) != 2:

        return False

    try:

        width, height = int(dimensions[0]), int(dimensions[1])

    except (TypeError, ValueError):

        return False

    return width > 0 and height > 0


def source_image_digest(path):
    """Server-computed identity of a source image: SHA-256 of its bytes.

    This is the ONLY trustworthy binding evidence, because it is derived from
    the file itself rather than from anything a caller claims. Returns None
    when the file cannot be read — a missing digest fails closed.
    """

    if not path:

        return None

    try:

        import hashlib

        digest = hashlib.sha256()

        with open(path, "rb") as handle:

            for chunk in iter(lambda: handle.read(1024 * 1024), b""):

                digest.update(chunk)

        return digest.hexdigest()

    except Exception:

        return None


def source_file_size(path):
    """Byte size of a source image, or None. Secondary corroboration only."""

    try:

        import os

        return os.path.getsize(path)

    except Exception:

        return None


def _mask_binding_is_verified(mask, context):
    """Is the mask provably bound to the source image of THIS turn?

    The evidence must be server-derived and impossible for a caller to forge:

      * `source_sha256` — the digest the ingestion boundary computed after it
        READ the mask and MEASURED it against the effective source image.
        A caller-supplied digest is worthless, so the caller's current source
        is re-hashed here and the two are compared. Both must exist and agree;
        matching dimensions are explicitly NOT accepted as identity.
      * `source_image_id` — the registry id of that same source, re-checked
        against the session's active image when one is resolvable.

    Fails closed on every missing or contradictory piece of evidence, which is
    what closes direct internal invocation: `ChatArchitect.handle()` performs
    no mask validation, so a mask that never passed ingestion carries no
    server digest and cannot bind.
    """

    digest = str(mask.get("source_sha256") or "").strip()

    if not digest:

        # No server-computed digest (a hand-built, forged or legacy mask).
        return False, "mask_source_digest_missing"

    # The digest of the source THIS turn will edit. It is computed either from
    # the resolved source path, or supplied in the context by the chat layer
    # for an image that is still bytes. Both are server-derived; neither is
    # read from the request or from the mask.
    current_path = context.get("source_image_path")

    context_digest = str(context.get("source_sha256") or "").strip()

    current_digest = None

    if current_path:

        # hashed from the file itself, so the claim is not what is trusted
        current_digest = source_image_digest(current_path)

    elif context_digest and context.get("source_identity_verified") is True:

        # A bare `source_sha256` in the context is caller data: only the chat
        # layer's source resolver may mark an identity as verified, and it
        # does so after hashing the image this turn will edit.
        current_digest = context_digest

    if not current_digest:

        return False, "source_image_unresolved"

    if current_digest != digest:

        return False, "mask_bound_to_a_different_source"

    if current_path:

        bound_size = mask.get("source_size_bytes")

        if isinstance(bound_size, int) and bound_size > 0:

            if source_file_size(current_path) != bound_size:

                return False, "mask_bound_to_a_different_source"

    bound_id = str(mask.get("source_image_id") or "").strip()

    active_id = str(context.get("active_image_id") or "").strip()

    if bound_id and active_id and bound_id != active_id:

        return False, "mask_bound_to_a_different_source"

    return True, "mask_bound_to_current_source"


def _kontext_local_edit_available():

    """True only when the Kontext graph really carries local editing.

    Delegates to the existing capability contract, so the answer is derived
    from the workflow graph and never asserted here.
    """

    try:

        from core.render.image_edit_capability_v1 import capability_flags

        return bool(capability_flags(_KONTEXT_WORKFLOW).get("supports_local_edit"))

    except BaseException:

        # An unreadable capability contract is not evidence of a route.
        return False


def precise_localized_route_available(context=None):
    """Resolve whether a validated masked-Kontext route exists for this turn.

    Returns a small contract so the guard, the callers and the refusal text can
    all state the SAME reason rather than each re-deriving one.
    """

    context = context if isinstance(context, dict) else {}

    mask = context.get("mask")

    if not _mask_is_validated(mask):

        return {
            "contract": "PreciseLocalizedRouteV1",
            "available": False,
            "reason": "no_validated_mask",
        }

    # `app.py` writes this flag only after the mask was read, measured and
    # matched against the source image on THIS request.
    if not context.get("precision_controls_supplied"):

        return {
            "contract": "PreciseLocalizedRouteV1",
            "available": False,
            "reason": "mask_not_bound_to_this_source",
        }

    # MASK_SOURCE_BINDING_V1 — structural plausibility is not binding. The mask
    # must carry a SERVER-COMPUTED digest that re-verifies against the source
    # image this turn will actually edit. Every failure below fails closed.
    _bound, _bind_reason = _mask_binding_is_verified(mask, context)

    if not _bound:

        return {
            "contract": "PreciseLocalizedRouteV1",
            "available": False,
            "reason": _bind_reason,
        }

    # strict parse — "false"/"0"/"" are all False, unlike bool("false")
    kontext = str(context.get("kontext_edit", "")).strip().lower() in (
        "1", "true", "yes", "on",
    )

    if not kontext:

        return {
            "contract": "PreciseLocalizedRouteV1",
            "available": False,
            "reason": "kontext_edit_not_selected",
        }

    if not _kontext_local_edit_available():

        return {
            "contract": "PreciseLocalizedRouteV1",
            "available": False,
            "reason": "local_edit_unavailable_in_workflow",
        }

    return {
        "contract": "PreciseLocalizedRouteV1",
        "available": True,
        "reason": "validated_mask_with_kontext_local_edit",
        "mask_filename": str(mask.get("filename") or "").strip(),
    }


# ----------------------------------------------------------
# FLOOR RESTRUCTURING PATTERNS (FLOOR_RESTRUCTURING_EXECUTION_GUARD_V1)
#
# MIXED_CLAUSE_ORDINAL_FIX_V1 — two defects in the original guard are
# corrected here, and nothing else about it changes:
#
#   1. Preservation was a SENTENCE-WIDE veto. `is_floor_restructuring_edit()`
#      returned False if any preservation pattern matched anywhere in the
#      input, discarding an affirmative restructuring clause it had already
#      found. `طبقات را حفظ کن ولی یک طبقه اضافه کن` therefore passed.
#      Preservation is now CLAUSE-scoped: a preservation clause protects only
#      the operation it constrains and can never cancel an affirmative clause
#      elsewhere in the message.
#
#   2. The English addition family accepted cardinals only
#      (`a|an|one|two|...|\d+`), so ordinals never matched at all —
#      `add a third floor` passed even standalone. Ordinals are now covered by
#      the same bounded vocabulary (`_ORDINALS_EN`); no general number parser
#      is introduced.
#
# Negation is handled where it belongs: a restructuring match that is negated
# inside its own clause is not an affirmative request. Persian negation is
# already structural — every Persian pattern requires the affirmative verb
# form (کن / کنید / بشه / بشود / نمایید), which `نکن` cannot satisfy.
# ----------------------------------------------------------

_ORDINALS_EN = (
    r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth"
    r"|1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th)"
)

# The floor noun, spelled consistently for both languages' English patterns.
# `stories?` cannot match the singular `story` (it expands to `storie(s)`), so
# `add a fourth story` was invisible to every pattern that used it. One bounded
# vocabulary constant now covers floor / floors / storey / storeys / story /
# stories.
_FLOOR_NOUN_EN = r"(?:floors?|storeys?|stor(?:y|ies))"

# Retained preservation vocabulary. Under clause scoping these patterns no
# longer veto a whole message; they describe what a preservation clause is.
_FLOOR_PRESERVATION_PATTERNS = (
    re.compile(r"\b(?:keep|preserve|preserving)\b.*?\b(?:floors?|storeys?|stories?|floor\s+count)\b", re.IGNORECASE),
    re.compile(r"\b(?:do\s+not|don't|without)\s+(?:add\s+or\s+remove|change|changing|altering|modifying)\s+(?:any\s+)?(?:floors?|storeys?|stories?|floor\s+count)\b", re.IGNORECASE),
    re.compile(r"\bno\s+change\s+to\s+(?:the\s+)?(?:floors?|storeys?|stories?|floor\s+count)\b", re.IGNORECASE),
    re.compile(r"بدون\s+(?:تغییر|دست\s*زدن|کم\s*و\s*زیاد\s*کردن)\s+(?:در\s+)?(?:تعداد\s+)?طبقات"),
    re.compile(r"(?:تعداد\s+)?طبقات\s*(?:را\s*)?(?:تغییر\s+نده|عوض\s+نکن|دست\s+نزن|ثابت|حفظ)"),
    re.compile(r"(?:اضافه|کم|حذف)\s+نکن"),
)

_NUM_WORDS_EN = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
_RANGE_WORDS_EN = rf"(?:between\s+\w+\s+and\s+\w+|\w+\s+to\s+\w+|{_NUM_WORDS_EN})"
_NUM_WORDS_FA = r"(?:\d+|یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده|۱|۲|۳|۴|۵|۶|۷|۸|۹|۰)"
_RANGE_WORDS_FA = rf"(?:بین\s+\S+\s+تا\s+\S+|\S+\s+تا\s+\S+|{_NUM_WORDS_FA})"

_FLOOR_RESTRUCTURE_PATTERNS = (
    # English: make it N floors / make this building N-storey / between X and Y floors
    re.compile(rf"\bmake\s+(?:it|this(?:\s+\w+)?|the\s+\w+)\s+{_RANGE_WORDS_EN}\s+{_FLOOR_NOUN_EN}\b", re.IGNORECASE),
    re.compile(rf"\bmake\s+(?:it|this\s+\w+|the\s+\w+)\s+{_RANGE_WORDS_EN}-(?:storey|story|floor)\b", re.IGNORECASE),
    re.compile(rf"\b(?:convert|turn|change)\b.*?\b(?:into|to)\s+(?:a\s+)?{_RANGE_WORDS_EN}-(?:storey|story|floor)\b", re.IGNORECASE),
    re.compile(rf"\bchange\b.*?\bto\s+{_RANGE_WORDS_EN}\s+{_FLOOR_NOUN_EN}\b", re.IGNORECASE),
    re.compile(rf"\b(?:increase|decrease|reduce|change)\s+(?:the\s+)?floor\s+count\b", re.IGNORECASE),
    re.compile(rf"\b(?:increase|reduce|decrease)\s+(?:it\s+)?to\s+(?:at\s+most\s+|at\s+least\s+|up\s+to\s+)?{_RANGE_WORDS_EN}\s+{_FLOOR_NOUN_EN}\b", re.IGNORECASE),
    re.compile(rf"\b(?:add|introduce)\s+(?:another\s+)?(?:a|an|one|two|three|four|five|six|\d+)?\s*(?:more\s+)?{_FLOOR_NOUN_EN}\b", re.IGNORECASE),
    re.compile(rf"\b(?:remove|delete)\s+(?:another\s+)?(?:a|an|one|two|three|four|five|six|\d+)?\s*(?:more\s+)?{_FLOOR_NOUN_EN}\b", re.IGNORECASE),

    # English ordinals — `add a third floor`, `add the third floor`,
    # `add a 3rd floor`, `add a fourth storey`. Same bounded vocabulary as
    # above; the determiner slot is optional so both forms are covered.
    re.compile(rf"\b(?:add|introduce)\s+(?:a\s+|an\s+|the\s+)?{_ORDINALS_EN}\s+{_FLOOR_NOUN_EN}\b", re.IGNORECASE),
    re.compile(rf"\b(?:remove|delete)\s+(?:a\s+|an\s+|the\s+)?{_ORDINALS_EN}\s+{_FLOOR_NOUN_EN}\b", re.IGNORECASE),

    # Persian
    # تعداد طبقات را افزایش/کاهش/بیشتر/تغییر بده
    re.compile(rf"تعداد\s+طبقات(?:ش)?\s*(?:را\s*)?(?:به\s+.*?\s+)?(?:افزایش|کاهش|بیشتر|کمتر|زیاد|کم|تغییر|عوض|سه|چهار|دو|\d+)\s*(?:بده|کن|کنید|نمایید)"),
    # N طبقه کن / سه طبقه کن / بین دو تا چهار طبقه کن / ۴ طبقه کن
    re.compile(rf"(?:به\s+)?{_RANGE_WORDS_FA}\s+طبقه\s*(?:ش\s*)?(?:کن|کنید|بشه|بشود|نما|نمایید)"),
    # یک طبقه اضافه کن / طبقه سوم را اضافه کن / طبقه اضافه کن
    re.compile(rf"(?:یک|دو|سه|چهار|\d+|دیگر|دیگری)?\s*طبقه\s*(?:دیگر\s*)?(?:به\s+(?:این\s+)?\S+\s+)?اضافه\s*(?:ش\s*)?(?:کن|کنید|بشه|بشود|نمایید)"),
    re.compile(rf"طبقه\s+(?:سوم|چهارم|پنجم|دوم|اول|\S+ام)\s*(?:را\s*)?(?:به\s+(?:این\s+)?\S+\s+)?اضافه\s*(?:ش\s*)?(?:کن|کنید|بشه|بشود|نمایید)"),
    # یک طبقه کم کن / حذف کن
    re.compile(rf"(?:یک|دو|سه|چهار|\d+)?\s*طبقه\s*(?:از\s+(?:این\s+)?\S+\s+)?(?:کم|حذف|برداشته)\s*(?:ش\s*)?(?:کن|کنید|بشه|بشود|نمایید)"),
)

# A floor request is scoped to its own clause. Sentence punctuation and
# contrastive conjunctions end a clause; a preservation clause on one side of
# them cannot reach across to the other.
#: SENTENCE-level boundaries. A negation never governs across one of these.
#:
#: I2I_CAPABILITY_GATE_REPAIR_V1 — split into two levels. The previous
#: single-level splitter treated commas and full stops alike, so
#: "Do not add floors, remove floors, or change the geometry." broke into three
#: fragments and "remove floors" lost the negation that governs it. It was then
#: read as an AFFIRMATIVE request to remove floors, and the whole facade edit
#: was refused as unsupported geometric restructuring.
_FLOOR_SENTENCE_SPLIT_RE = re.compile(
    r"[;؛.!?؟]+"
    r"|\b(?:but|however|although|though|yet)\b"
    r"|(?:^|\s)(?:ولی|اما|بلکه)(?=\s|$)"
)

#: CLAUSE-level boundaries INSIDE a sentence.
_FLOOR_CLAUSE_SPLIT_RE = re.compile(r"[،,]+")

#: A comma fragment that CONTINUES a list already opened by a negation.
_FLOOR_LIST_CONTINUATION_RE = re.compile(r"^(?:or|and|nor)\b", re.IGNORECASE)

_FLOOR_RESTRUCTURE_VERB_START_RE = re.compile(
    r"^(?:add|adding|introduce|introducing|remove|removing|delete|deleting"
    r"|change|changing|modify|modifying)\b",
    re.IGNORECASE,
)

_FLOOR_ANY_NEGATION_RE = re.compile(
    r"\b(?:do\s+not|don't|does\s+not|doesn't|never|avoid)\b",
    re.IGNORECASE,
)

# Bounded English negation that governs a following restructuring verb.
#
# The optional bridge covers a single negated COORDINATION — `do not add or
# remove floors` — where one negation governs two restructuring verbs. It is
# deliberately narrow: only the restructuring verbs themselves may sit between
# the negation and the match, so an unrelated clause cannot suppress a real
# addition. Erring toward "not negated" keeps the guard on the refusing side.
_FLOOR_NEGATION_BEFORE_RE = re.compile(
    r"\b(?:do\s+not|don't|does\s+not|doesn't|never|avoid)\b"
    r"(?:\s+(?:add|introduce|remove|delete)\s+or)?\s*$",
    re.IGNORECASE,
)

#: A negation that governs a COMMA-SEPARATED list of restructuring verbs.
#:
#: I2I_CAPABILITY_GATE_REPAIR_V1 — the anchored regex above only recognises a
#: negation immediately before the verb (or one "add or remove" bridge). A list
#: such as "do not add floors, remove floors, or change the geometry" puts a
#: completed list item between the negation and the verb, so the anchor missed
#: it and the second item read as affirmative.
#:
#: Deliberately narrow: between the negation and the verb under test only
#: COMPLETE earlier list items may appear — a restructuring verb, an optional
#: determiner/numeral, an optional floor noun — joined by commas or a
#: coordinator. Anything else (a new subject, another predicate, a non-floor
#: noun such as "geometry") breaks the bridge, so "do not touch the roof, add
#: two floors" still reads as an affirmative request.
_FLOOR_NEGATED_LIST_BRIDGE_RE = re.compile(
    r"\b(?:do\s+not|don't|does\s+not|doesn't|never|avoid)\b"
    r"(?:\s*,?\s*(?:or|and|nor)?\s*"
    r"(?:add|adding|introduce|introducing|remove|removing|delete|deleting"
    r"|change|changing|modify|modifying)"
    r"(?:\s+(?:the|a|an|\d+|one|two|three|four|five|six|seven|eight|nine|ten))?"
    r"(?:\s+(?:floor|floors|storey|storeys|story|stories|level|levels"
    r"|طبقه|طبقات))?"
    r")+"
    r"\s*,?\s*(?:or|and|nor)?\s*$",
    re.IGNORECASE,
)


def _continues_negated_list(previous, part):
    """True when `part` continues a list opened by a negation in `previous`."""

    if not _FLOOR_ANY_NEGATION_RE.search(previous):

        return False

    return bool(
        _FLOOR_LIST_CONTINUATION_RE.match(part)
        or _FLOOR_RESTRUCTURE_VERB_START_RE.match(part)
    )


def _floor_clauses(text):
    """Split a message into the clauses a floor request is scoped to.

    I2I_CAPABILITY_GATE_REPAIR_V1 — sentence first, then clause, then merge.

    A negation governs a comma-separated list but never crosses a sentence
    boundary. Splitting sentences first and re-attaching a comma fragment that
    continues a negated list keeps "do not add floors, remove floors, or change
    the geometry" as ONE negated clause, while "Do not touch the roof. Add two
    floors." still yields a separate, affirmative second clause.
    """

    clauses = []

    for sentence in _FLOOR_SENTENCE_SPLIT_RE.split(str(text or "")):

        sentence = (sentence or "").strip()

        if not sentence:

            continue

        merged = []

        for part in _FLOOR_CLAUSE_SPLIT_RE.split(sentence):

            part = part.strip()

            if not part:

                continue

            if merged and _continues_negated_list(merged[-1], part):

                merged[-1] = merged[-1] + ", " + part

                continue

            merged.append(part)

        clauses.extend(merged)

    return clauses


def _restructure_match_is_negated(clause, match):
    """True when the clause negates this restructuring verb."""

    prefix = clause[:match.start()]

    if _FLOOR_NEGATION_BEFORE_RE.search(prefix):

        return True

    # I2I_CAPABILITY_GATE_REPAIR_V1 — a negation governing a comma-separated
    # list: "do not add floors, remove floors, or change the geometry".
    return bool(_FLOOR_NEGATED_LIST_BRIDGE_RE.search(prefix))


def _clause_has_affirmative_restructure(clause):
    """True when this clause, on its own, asks to change the floor count."""

    lowered = " ".join(clause.lower().replace("\u200c", " ").split())

    for pattern in _FLOOR_RESTRUCTURE_PATTERNS:

        for candidate in (clause, lowered):

            for match in pattern.finditer(candidate):

                if not _restructure_match_is_negated(candidate, match):

                    return True

    return False


def is_floor_restructuring_edit(text):
    """Detect whether text affirmatively requests adding, removing, or changing floors.

    MIXED_CLAUSE_ORDINAL_FIX_V1 — clause-scoped and negation-aware:

      * an affirmative restructuring clause is detected even when another
        clause asks to preserve the floor count (rule A),
      * a negated restructuring verb is never read as an affirmative request
        (rule B),
      * a preservation clause constrains only itself, so clause order does not
        change the verdict (rules C and E),
      * when an explicit addition and a preservation clause coexist, the
        unsupported structural operation is still refused (rule F).
    """

    raw = str(text or "").strip()

    if not raw:

        return False

    for clause in _floor_clauses(raw):

        if _clause_has_affirmative_restructure(clause):

            return True

    return False


def _geometry_verb_present(verb, lowered):
    """True when `verb` occurs as a WORD, not as a substring.

    I2I_CAPABILITY_GATE_REPAIR_V1 — the previous containment test
    (``verb in lowered``) matched "move" INSIDE "remove", so a facade request
    whose only mention of floors was the PRESERVE clause "Do not add floors,
    remove floors, or change the geometry" produced a bare geometry verb and
    was refused by tier 3 as an unsupported geometric edit.

    English verbs are matched on word boundaries. Persian phrases stay
    substring-matched: they are already specific multi-character phrases and
    Persian does not use ASCII word separators.
    """

    if verb.isascii():

        return bool(
            re.search(r"\b%s\b" % re.escape(verb), lowered)
        )

    return verb in lowered


def detect_unsupported_geometry_edit(text, context=None):
    """Detect a precise geometric edit that this phase must refuse.

    Deterministic. Three escalating tiers:

      dimensioned_geometry_edit_not_supported
        a geometry verb together with a stated dimension
        ("این پنجره رو 80 سانت ببر راست")

      localized_geometry_edit_not_supported
        a localized operation on ONE named architectural component
        ("این پنجره رو حذف کن")

      geometry_edit_not_supported
        a bare geometry verb with no other context

    A global appearance edit ("نما رو سنگ کن", "همینو شب کن") is never
    flagged: it needs a geometry verb or a localized component
    operation.

    PRECISE_EDIT_ROUTE_V1 — tier 2 is now refused only while no validated
    localized route exists. When `context` carries a validated
    caller-supplied selection mask and Kontext local editing is really
    selected, that request is NOT unsupported, because an existing route can
    execute it (see `precise_localized_route_available`). Tiers 1 and 3 are
    unchanged, and every request without a validated mask behaves exactly as
    before. No `context` (the default) means no route.
    """

    raw = str(text or "")

    lowered = " ".join(raw.lower().split())

    matched = []

    # CLASSICAL_REDESIGN_SCOPE_V1 — "large-scale", "small-scale" and
    # "full-scale" are adjectives describing stone or modelling, not the verb
    # "scale". Stripping the compounds before verb detection keeps tier 3
    # honest without weakening it for "scale the window".
    _verb_scan = lowered
    for _compound in (
        "large-scale", "small-scale", "full-scale",
        "large scale", "small scale", "full scale",
    ):
        _verb_scan = _verb_scan.replace(_compound, "largeformat")

    geometry = [
        verb for verb in _GEOMETRY_VERBS
        if _geometry_verb_present(verb, _verb_scan)
    ]

    if geometry:

        matched.extend(geometry)


    has_dimension = bool(_DIMENSION_NUMBER_RE.search(raw)) or any(
        word in lowered for word in _DIMENSION_WORDS
        if word not in ("متر",)  # bare "متر" alone is too weak
    )


    components = [
        item for item in _LOCALIZED_COMPONENTS
        if item in lowered
    ]

    localized_ops = [
        op for op in _LOCALIZED_OPS
        if op in lowered
    ]


    # ---- scope resolution (CLASSICAL_REDESIGN_SCOPE_V1) ----
    _strict_ops = [op for op in localized_ops if op in _LOCALIZED_OPS_STRICT]

    _generic_ops = [op for op in localized_ops if op in _LOCALIZED_OPS_GENERIC]

    _has_anchor = bool(has_dimension) or any(
        anchor in lowered for anchor in _LOCALIZING_ANCHORS
    )

    _global_scope = any(term in lowered for term in _GLOBAL_SCOPE_TERMS)

    # A generic operation ("add", "replace") is local unless the request is
    # explicitly facade/building-wide. Requiring a deictic as well was too
    # strict: "add a new railing to the balcony" names one component and is a
    # localized edit, while "replace the brick facade character with stone"
    # carries global scope and is a redesign. Scope, not deixis, decides.
    _is_localized = bool(_strict_ops) or bool(
        _generic_ops and not _global_scope
    )

    _scope_evidence = {
        "strict_ops": _strict_ops,
        "generic_ops": _generic_ops,
        "localizing_anchor": _has_anchor,
        "global_scope": _global_scope,
        "resolved_scope": "localized" if _is_localized else "global",
    }

    # ---- tier 0: floor-count restructuring edit ----
    #
    # FLOOR_RESTRUCTURING_EXECUTION_GUARD_V1 — an affirmative request to add,
    # remove or change the building's total number of floors cannot be performed
    # reliably by the standard image-edit workflow (flux_img2img.json has
    # supports_geometry_edit=False). It must be refused truthfully before
    # submission rather than emitting contradictory prompts or corrupted images.
    if is_floor_restructuring_edit(raw):

        return {
            "contract": "UnsupportedGeometryEditV1",
            "version": VERSION,
            "unsupported": True,
            "reason": "floor_count_restructuring_not_supported",
            "message": (
                "Changing the building's number of floors cannot currently be "
                "performed reliably with the selected image-edit workflow."
            ),
            "matched": ["floor_count_restructuring"],
            "components": components,
            "localized_ops": localized_ops,
            "dimension": has_dimension,
        }

    # ---- tier 1: geometry verb + stated dimension ----
    if geometry and has_dimension:

        return {
            "contract": "UnsupportedGeometryEditV1",
            "version": VERSION,
            "unsupported": True,
            "reason": "dimensioned_geometry_edit_not_supported",
            "matched": matched,
            "components": components,
            "localized_ops": localized_ops,
            "dimension": True,
        }


    # ---- tier 2: localized operation on a named component ----
    #
    # PRECISE_EDIT_ROUTE_V1 — a localized edit is refused unless a validated
    # route can actually execute it. The route is NOT checked by a truthy mask
    # value: a mask that cannot be proven validated is treated exactly like no
    # mask, so `m = "<anything>"` can never weaken this guard. Everything else
    # (tier 1 dimensioned, tier 3 bare verb, no mask, stale mask, Kontext off
    # or absent) still refuses below.
    if components and localized_ops:

        # CLASSICAL_REDESIGN_SCOPE_V1 — the scope was resolved above, before
        # the tiers. A component noun plus a generic operation is not enough:
        # only a strict local op, or a generic op with a deictic anchor
        # outside a facade-wide request, makes this a localized edit.
        if not _is_localized:

            # An authorised global facade redesign. Fall through: tier 3 may
            # still refuse a bare geometry verb, and tier 1 has already
            # refused anything with a stated dimension.
            components = components

        else:

            _route = precise_localized_route_available(context)

            if _route.get("available"):

                return {
                    "contract": "UnsupportedGeometryEditV1",
                    "version": VERSION,
                    "unsupported": False,
                    "reason": None,
                    "matched": matched,
                    "components": components,
                    "localized_ops": localized_ops,
                    "dimension": has_dimension,
                    "scope_evidence": _scope_evidence,
                    "routed_to": "flux_kontext_edit.json",
                    "precise_route": _route,
                }

            return {
                "contract": "UnsupportedGeometryEditV1",
                "version": VERSION,
                "unsupported": True,
                "reason": "localized_geometry_edit_not_supported",
                "matched": matched,
                "components": components,
                "localized_ops": localized_ops,
                "dimension": has_dimension,
                "scope_evidence": _scope_evidence,
                "precise_route": _route,
            }


    # ---- tier 3: bare geometry verb ----
    if geometry:

        return {
            "contract": "UnsupportedGeometryEditV1",
            "version": VERSION,
            "unsupported": True,
            "reason": "geometry_edit_not_supported",
            "matched": matched,
            "components": components,
            "localized_ops": localized_ops,
            "dimension": has_dimension,
            "scope_evidence": _scope_evidence,
        }

    return {
        "contract": "UnsupportedGeometryEditV1",
        "version": VERSION,
        "unsupported": False,
        "reason": None,
        "matched": [],
        "components": components,
        "localized_ops": localized_ops,
        "dimension": has_dimension,
        "scope_evidence": _scope_evidence,
    }


def has_edit_signal(text, intent_router=None):
    """Shared deterministic edit predicate (used by the resolver too)."""

    raw = str(text or "").strip()

    lowered = " ".join(raw.lower().split())

    if not lowered:

        return False, []


    matched = _contains_any(lowered, _EDIT_PHRASES)

    for pattern in _PERSIAN_EDIT_PATTERNS:

        if pattern.search(lowered):

            matched.append("persian_explicit_edit_pattern")

    # R4_PHOTO_SAFE_CHAT_BRIDGE_V1 — an explicit photographic global
    # colour-balance warmth instruction is an edit instruction. The pattern
    # itself requires the imperative, so a question about the colour balance
    # still has no edit signal.
    for pattern in _PHOTOGRAPHIC_BALANCE_EDIT_PATTERNS:

        if pattern.search(lowered):

            matched.append("photographic_colour_balance_edit_pattern")

            break


    # bare appearance noun + object-marked deictic -> edit
    if not matched:

        has_anchor = any(
            anchor in lowered for anchor in _OBJECT_ANCHORS
        )

        if has_anchor:

            nouns = _contains_any(lowered, _BARE_APPEARANCE_NOUNS)

            if nouns:

                matched.extend(nouns)


    if intent_router is not None:

        try:

            if intent_router.is_image_edit_request(raw):

                matched.append("intent_router.is_image_edit_request")

        except Exception:

            pass


    return bool(matched), matched


# ----------------------------------------------------------
# API MODE CONTRACT
# ----------------------------------------------------------

MODE_IMAGE_ANALYSIS = "IMAGE_ANALYSIS"
MODE_IMAGE_EDIT = "IMAGE_EDIT"
MODE_CHAT_WITH_IMAGE = "CHAT_WITH_IMAGE"
MODE_IMAGE_UPLOAD = "IMAGE_UPLOAD"
MODE_TEXT_TO_IMAGE = "TEXT_TO_IMAGE"
MODE_CHAT = "CHAT"
# VISION_OBSERVATION_MODE_SEPARATION_V1
MODE_IMAGE_OBSERVATION = "IMAGE_OBSERVATION"


def build_mode_contract(response, has_image=False):
    """Return the authoritative API/UI routing contract for a completed turn.

    This maps the already-executed native result; it never changes routing.
    Keeping it beside the image-intent classifier prevents the API and UI from
    independently inferring a mode from attachment presence or UI selection.
    """

    response = response if isinstance(response, dict) else {}
    vision = response.get("vision")
    vision = vision if isinstance(vision, dict) else {}

    image_intent = vision.get("intent") or response.get("intent")
    output = response.get("type") or "chat"

    # ROUTING_TRUTHFULNESS_V1 — an EXECUTED render outranks an inferred
    # intent. A dual-image restyle can be classified as a reference/chat
    # intent and still reach ComfyUI; the envelope used to report
    # `mode: CHAT_WITH_IMAGE, render: false` for a turn that had in fact
    # rendered, which is a false negative about the product's own behaviour.
    # This contract maps what happened, so the executed output decides first.
    if output == "image_render":

        mode = MODE_IMAGE_EDIT if has_image else MODE_TEXT_TO_IMAGE

    elif has_image:

        if image_intent == INTENT_EDIT:

            mode = MODE_IMAGE_EDIT

        elif image_intent == INTENT_OBSERVE or output == "image_observation":

            # VISION_OBSERVATION_MODE_SEPARATION_V1 — observation is its
            # own mode, and it never renders.
            mode = MODE_IMAGE_OBSERVATION

        elif image_intent == INTENT_UPLOAD_ONLY or output == "image_upload":

            mode = MODE_IMAGE_UPLOAD

        elif image_intent in (INTENT_ANALYZE, INTENT_REFERENCE) or output in (
            "image_analysis", "image_reference"
        ):

            mode = MODE_IMAGE_ANALYSIS

        else:

            mode = MODE_CHAT_WITH_IMAGE

    elif output == "image_render":

        mode = MODE_TEXT_TO_IMAGE

    else:

        mode = MODE_CHAT

    return {
        "contract": "ImageModeRoutingV1",
        "version": VERSION,
        "mode": mode,
        "intent": image_intent or ("image_generation" if mode == MODE_TEXT_TO_IMAGE else "chat"),
        "input": "image" if has_image else "text",
        "output": output,
        "render": (
            output == "image_render"
            or mode in (MODE_IMAGE_EDIT, MODE_TEXT_TO_IMAGE)
        ),
    }


# ----------------------------------------------------------
# ANALYZE signals (question / description request)
# ----------------------------------------------------------

_ANALYZE_PHRASES = (
    "چیه", "چیست", "چی هست", "چه چیزی", "توضیح بده", "شرح بده", "تحلیل کن",
    "بررسی کن", "بگو", "بگو چه", "چند", "چطوره", "چه سبکی", "چه متریالی",
    "دیده میشه", "دیده می‌شه", "مشخصه", "مشخص است",
    "what", "describe", "explain", "analyze", "analyse", "tell me",
    "how many", "what is", "what's", "which", "identify", "is there",
)

# ----------------------------------------------------------
# REFERENCE signals (pointing, not acting)
# ----------------------------------------------------------

_REFERENCE_PHRASES = (
    "همین عکس", "این عکس", "همین تصویر", "این تصویر", "همین رندر", "این رندر",
    "رندر قبلی", "آخرین رندر", "عکس قبلی", "آخرین عکس",
    "this image", "this picture", "this render", "last render",
    "previous render", "last image", "previous image",
)


_QUESTION_MARKS = ("?", "؟")


def _contains_any(text, phrases):

    hits = [
        phrase for phrase in phrases
        if phrase in text
    ]

    return hits


def classify_image_intent(text, intent_router=None):
    """Classify an image-bearing message.

    Returns a deterministic contract dict. Never returns "edit" unless
    an explicit modification signal is present.
    """

    raw = str(text or "").strip()

    lowered = " ".join(raw.lower().split())


    result = {

        "contract": CONTRACT,
        "version": VERSION,

        "intent": INTENT_ANALYZE,
        "reason": None,
        "matched": [],

        "is_question": any(mark in raw for mark in _QUESTION_MARKS),

    }


    if not lowered:

        result["intent"] = INTENT_UPLOAD_ONLY
        result["reason"] = "no_instruction"

        return result


    # ---- edit first (highest consequence, must be explicit) ----
    _, edit_hits = has_edit_signal(raw, intent_router)

    if edit_hits:

        result["intent"] = INTENT_EDIT
        result["reason"] = "explicit_edit_signal"
        result["matched"] = edit_hits

        return result


    # ---- observation only (before analyze: "list the visible elements"
    #      is a question shape, and the analyze branch would swallow it) ----
    #
    # VISION_OBSERVATION_MODE_SEPARATION_V1 — two-part detection lives in
    # the observation layer, so the request has ONE owner.
    try:

        from core.vision.vision_observation_mode_v1 import (
            detect_observation_request,
        )

        wants_observation = detect_observation_request(raw)

    except Exception:

        wants_observation = False

    if wants_observation:

        result["intent"] = INTENT_OBSERVE
        result["reason"] = "observation_request"
        result["matched"] = ["visible_evidence"]

        return result


    # ---- analyze ----
    analyze_hits = _contains_any(lowered, _ANALYZE_PHRASES)

    if analyze_hits or result["is_question"]:

        result["intent"] = INTENT_ANALYZE
        result["reason"] = (
            "question" if result["is_question"] else "analyze_signal"
        )
        result["matched"] = analyze_hits

        return result


    # ---- same-subject appearance variation (V4.3A — M7) ----
    #
    # "same tower, morning" / "same building at sunset" carries no explicit
    # modification verb, so it used to fall through to `safe_default_analyze`
    # and the turn became a vision Q&A instead of a render. A same-subject
    # reference PLUS a classified appearance delta is an edit: it asks for a
    # new appearance of the SAME building, and the caller has already
    # established that an image exists.
    #
    # This branch is placed after the question/observation gates, so it can
    # never capture "is this the same building as the photo?".
    try:

        from core.prompt_intelligence.image_edit_delta_v1 import (
            is_same_subject_appearance_request,
        )

        same_subject_appearance = is_same_subject_appearance_request(raw)

    except Exception:

        same_subject_appearance = False

    if same_subject_appearance:

        result["intent"] = INTENT_EDIT
        result["reason"] = "same_subject_appearance_variation"
        result["matched"] = ["same_subject", "appearance_delta"]

        return result


    # ---- reference only (no action verb) ----
    reference_hits = _contains_any(lowered, _REFERENCE_PHRASES)

    if reference_hits:

        result["intent"] = INTENT_REFERENCE
        result["reason"] = "reference_phrase_only"
        result["matched"] = reference_hits

        return result


    # ---- default: describe / answer (non-destructive) ----
    result["intent"] = INTENT_ANALYZE
    result["reason"] = "safe_default_analyze"

    return result
