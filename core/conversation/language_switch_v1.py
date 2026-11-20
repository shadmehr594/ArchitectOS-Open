# ==========================================================
# ArchitectOS Language Switch v1
#
# VISION_REPORT_LANGUAGE_01
#
# THE PROBLEM (user-reported, with their own session as evidence)
#
# The assistant analysed a photo in ENGLISH inside a Persian
# conversation. The user then asked, in Persian:
#
#     "میشه تحلیل عکستو فارسی برام بگی"
#     (could you tell me your analysis of the photo in Persian?)
#
# The assistant did not understand it as a language request at all. It
# classified the turn as NORMAL_CONVERSATION, fell through to the
# generic LLM, and the LLM treated "عکستو فارسی" as an ARCHITECTURAL
# TERM — inventing a whole discussion of "عکستو فارسی" as a design made
# of thresholds, windows, "آروین" and "قوسه".
#
# This module is the missing intent. It is deterministic: no LLM, no
# network.
#
# TWO-PART EVIDENCE, because a single word over-captures:
#   1. a LANGUAGE NAME  (فارسی / انگلیسی / Persian / English / Farsi)
#   2. a REQUEST MARKER (بگو / جواب بده / توضیح بده / بنویس / ترجمه /
#                        tell / answer / explain / reply / in)
# so a statement that merely mentions a language is not a switch.
#
# When the project still holds its last image interpretation, the
# analysis is RE-RENDERED in the requested language — that is what the
# teacher actually asked for. Nothing is invented: it is the same
# contract, rendered again.
# ==========================================================


from __future__ import annotations


from core.conversation.turn_semantics_v1 import match_form


CONTRACT = "LanguageSwitchV1"
VERSION = "1.0"


LANGUAGE_FA = "fa"
LANGUAGE_EN = "en"


# ---- part 1: the language NAME (match form) ----

FA_MARKERS = (
    "\u0641\u0627\u0631\u0633\u06cc",   # فارسی
    "\u067e\u0627\u0631\u0633\u06cc",   # پارسی
    "\u0641\u0627\u0631\u0633\u06cc \u0632\u0628\u0627\u0646",  # فارسی زبان
    "farsi",
    "persian",
)

EN_MARKERS = (
    "\u0627\u0646\u06af\u0644\u06cc\u0633\u06cc",   # انگلیسی
    "\u0627\u0646\u06af\u0644\u06cc\u0633\u06cc \u0632\u0628\u0627\u0646",  # انگلیسی زبان
    "english",
    "ingilisi",
)


# ---- part 2: the REQUEST marker ----

REQUEST_MARKERS = (
    # Persian
    "\u0628\u06af\u0648",              # بگو
    "\u0628\u06af\u06cc",              # بگی
    "\u0628\u06af\u06cc\u062f",        # بگید
    "\u0628\u06af\u0648\u06cc\u06cc\u062f",  # بگویید
    "\u062c\u0648\u0627\u0628",        # جواب
    "\u067e\u0627\u0633\u062e",        # پاسخ
    "\u062a\u0648\u0636\u06cc\u062d",  # توضیح
    "\u0628\u0646\u0648\u06cc\u0633",  # بنویس
    "\u062a\u0631\u062c\u0645\u0647",  # ترجمه
    "\u06cc\u0639\u0646\u06cc",        # یعنی
    # English
    "tell",
    "say",
    "answer",
    "explain",
    "reply",
    "speak",
    "write",
    "translate",
    "switch",
    "in ",
)


PHRASES = {

    "fa": {
        "switched_only": (
            "چشم. از این به بعد فارسی پاسخ می‌دهم."
        ),
        "rerendered": (
            "چشم. این هم همان تحلیل تصویر، این بار فارسی:"
        ),
        "no_analysis": (
            "چشم. از این به بعد فارسی پاسخ می‌دهم.\n"
            "تحلیلی از تصویر در این پروژه ثبت نشده که دوباره فارسی "
            "بگویم؛ اگر تصویر را دوباره بفرستید، فارسی تحلیل می‌کنم."
        ),
        "english_switch": (
            "باشه. از این به بعد انگلیسی جواب می‌دهم."
        ),
    },

    "en": {
        "switched_only": "Sure. I will answer in English from now on.",
        "rerendered": (
            "Sure. Here is the same image analysis, in English this time:"
        ),
        "no_analysis": (
            "Sure. I will answer in English from now on.\n"
            "No image analysis is recorded in this project that I could "
            "re-render; send the image again and I will analyse it in "
            "English."
        ),
        "english_switch": "Sure. I will answer in English from now on.",
    },
}


def _language_marker(form):

    """The requested language, or None."""

    for marker in FA_MARKERS:

        if marker in form:

            return LANGUAGE_FA

    for marker in EN_MARKERS:

        if marker in form:

            return LANGUAGE_EN

    return None


def detect_language_request(text):

    """The requested reply language, or None.

    Deterministic. Never raises.
    """

    try:

        form = match_form(text)

    except Exception:

        return None

    if not form:

        return None

    requested = _language_marker(form)

    if not requested:

        return None

    # A language name alone is not a request ("فارسی سخته").
    if not any(marker in form for marker in REQUEST_MARKERS):

        return None

    return requested


def build_language_switch(language, interpretation=None,
                          project_id=None, image_analysis_available=None):

    """The honest reply to a language-switch request.

    Re-renders the project's last image interpretation when one exists,
    because that is what "analyse the photo for me in Persian" asks for.
    Read-only: nothing is created, learned or rendered.
    """

    lang = LANGUAGE_FA if language == LANGUAGE_FA else LANGUAGE_EN

    text = PHRASES[lang]

    re_rendered = None

    if isinstance(interpretation, dict) and interpretation:

        try:

            from core.vision.vision_report_v1 import render_vision_report

            re_rendered = render_vision_report(interpretation, lang)

        except Exception as error:

            print(
                "LANGUAGE SWITCH RE-RENDER ERROR:",
                type(error).__name__,
                error,
            )

            re_rendered = None

    if re_rendered:

        result = text["rerendered"] + "\n\n" + re_rendered

    elif image_analysis_available is False:

        result = text["no_analysis"]

    else:

        result = text["switched_only"]

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "status": "success",

        "language": lang,

        "result": result,

        "action": "switch_reply_language",

        "requested_language": lang,

        "re_rendered_analysis": bool(re_rendered),

        "analysis": re_rendered,

        "project_id": project_id,

        "candidate": None,
        "permanent_learning": False,
        "routed_to_execute": False,
        "llm_used": False,
        "network_used": False,
        "render_requested": False,
    }


def language_label(language):

    return "فارسی" if language == LANGUAGE_FA else "English"


language_switch = {

    "contract": CONTRACT,
    "version": VERSION,

    "detect": detect_language_request,
    "build": build_language_switch,
    "label": language_label,

    "LANGUAGE_FA": LANGUAGE_FA,
    "LANGUAGE_EN": LANGUAGE_EN,
}


print(
    "LANGUAGE SWITCH v1.0 ONLINE "
    "(a language request is answered, not handed to the LLM)"
)
