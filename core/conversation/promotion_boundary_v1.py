# ==========================================================
# ArchitectOS Knowledge Promotion Boundary v1
#
# CORRECTION_LOOP_01
#
# The teacher can ASK for a received note to become permanent knowledge
# ("به دانش عمومی تبدیلش کن" / "make this permanent knowledge").
#
# Phase 08 deliberately does NOT implement promotion:
# `permanent_learning_implemented` is False, `knowledge_promotion_implemented`
# is False, and the phase briefs forbid silently promoting a user
# statement to learned knowledge. That is a DESIGN decision, not a bug.
#
# The BUG was the absence of a boundary. The request classified as
# INSTRUCTION, which is not short-circuited by the teaching layer, so it
# fell through to the generic LLM — and the LLM then FABRICATED a
# promotion: it "converted" an unrelated memory (materials / natural
# stone) into "public knowledge about the master bedroom" and reported
# the conversion as done. A system that cannot promote must SAY so.
#
# This module is:
#   - deterministic (no LLM, no network)
#   - read-only (writes nothing, promotes nothing, learns nothing)
#   - additive (it only ever fires on an explicit, two-part request)
#
# Two-part evidence, because a single word over-captures:
#   1. a knowledge TARGET noun ("دانش عمومی" / "حافظه" / "knowledge" ...)
#   2. a promotion STEM ("تبدیل" / "ثبت" / "ذخیره" / "convert" ...)
#      together with an imperative form
# so a statement ABOUT knowledge ("دانش عمومی یعنی ...") never matches.
# ==========================================================


from __future__ import annotations


from core.conversation.turn_semantics_v1 import match_form

# The "promotion is not implemented" truth belongs to the Phase 09
# promotion bridge. This module READS it instead of re-deriving it, so
# the two can never disagree.
from core.conversation.knowledge_promotion_bridge_v1 import (
    PROMOTION_IMPLEMENTED,
)


CONTRACT = "KnowledgePromotionBoundaryV1"
VERSION = "1.0"


# ----------------------------------------------------------
# EVIDENCE (written in MATCH FORM — match_form folds the ZWNJ to a
# space, so "تبدیلش" arrives as the tokens "تبدیل" + "ش")
# ----------------------------------------------------------

PROMOTION_TARGETS = frozenset(
    (
        # Persian
        "دانش عمومی",
        "دانش دائمی",
        "دانش دائم",
        "دانش ثابت",
        "دانش بلند مدت",
        "حافظه",
        "خاطره",
        # "به خاطر بسپار" arrives as the tokens "خاطر" + "بسپار"
        "خاطر",
        "دانش",
        # English
        "permanent knowledge",
        "public knowledge",
        "long term memory",
        "memory",
        "knowledge",
    )
)


PROMOTION_STEMS = frozenset(
    (
        # Persian
        "تبدیل",
        "ثبت",
        "ذخیره",
        "بسپار",
        "بگیر",
        "دائمی",
        # English
        "convert",
        "permanent",
        "remember",
        "save",
        "store",
    )
)


PROMOTION_IMPERATIVES = frozenset(
    (
        # Persian
        "کن",
        "کنید",
        "کنم",
        "بسپار",
        "بگیر",
        "بده",
        # English
        "convert",
        "make",
        "remember",
        "save",
        "store",
        "learn",
    )
)


PHRASES = {
    "fa": (
        "دریافت شد.\n"
        "اما تبدیل به دانش دائمی در این نسخه پیاده‌سازی نشده است.\n"
        "این نکته فقط به‌عنوان «دریافت‌شده» ثبت می‌شود و به دانش دائمی "
        "تبدیل نمی‌شود.\n"
        "من چیزی از خودم نمی‌سازم و ادعای تبدیل نمی‌کنم.\n"
        "هر وقت خواستید بپرسید چه فهمیدم."
    ),
    "en": (
        "Understood.\n"
        "Knowledge promotion is NOT implemented in this build.\n"
        "The note stays RECEIVED only; it does not become permanent "
        "knowledge.\n"
        "I will not invent a promotion or claim one happened.\n"
        "Ask me any time what I understood."
    ),
}


def is_promotion_request(text):
    """True only for an explicit, two-part promotion request.

    Deterministic. Never raises.
    """

    try:

        form = match_form(text)

    except Exception:

        return False

    if not form:

        return False

    tokens = [token for token in form.split(" ") if token]

    if not tokens:

        return False

    token_set = set(tokens)

    has_target = any(
        target in form for target in PROMOTION_TARGETS
    )

    # SUBSTRING, not token equality: with no ZWNJ the clitic glues onto
    # the stem ("تبدیلش کن" arrives as the single token "تبدیلش"), and
    # with a ZWNJ it does not ("تبدیل ش کن"). Both spellings must match,
    # and a token-set test silently missed the first one.
    has_stem = bool(token_set & PROMOTION_STEMS) or any(
        stem in form for stem in PROMOTION_STEMS
    )

    has_imperative = bool(token_set & PROMOTION_IMPERATIVES)

    return bool(has_target and has_stem and has_imperative)


def build_promotion_refusal(language="fa"):
    """The honest boundary response. Read-only: nothing is stored."""

    lang = "fa" if str(language or "").startswith("fa") else "en"

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "status": "success",

        "language": lang,

        "result": PHRASES[lang],

        "action": "refuse_knowledge_promotion",

        "mode": "READ_ONLY_PROMOTION_BOUNDARY",

        "promotion_requested": True,

        "promotion_implemented": PROMOTION_IMPLEMENTED,

        "promoted": False,

        "candidate_created": False,

        "learned_anything": False,

        "permanent_learning_implemented": PROMOTION_IMPLEMENTED,

        "llm_used": False,
        "network_used": False,
        "render_requested": False,
    }


promotion_boundary = {

    "contract": CONTRACT,
    "version": VERSION,

    "is_promotion_request": is_promotion_request,
    "build_promotion_refusal": build_promotion_refusal,
}


print(
    "PROMOTION BOUNDARY v1.0 ONLINE "
    "(promotion request -> honest refusal, no promotion, no LLM)"
)
