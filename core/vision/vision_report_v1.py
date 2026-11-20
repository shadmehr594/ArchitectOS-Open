# ==========================================================
# ArchitectOS Vision Report v1
#
# VISION_REPORT_LANGUAGE_01
#
# THE PROBLEM (user-reported, with their own session as evidence)
#
# The user uploaded a bedroom photo and asked in Persian
# ("حالایه عکس رو بارگزاری میکنم تو ببین از این چی میفهمی؟"). The
# assistant answered in ENGLISH:
#
#   1. Possible architectural space:
#   bedroom (confidence: HIGH)
#   2. Visible elements:
#   - entrance threshold visible
#   ...
#
# ...while the SAME response declared `output_language: "persian"`. The
# reply contradicted its own language contract.
#
# `core/chat/response_adapter.build_architectural_vision_message` was a
# hardcoded English string builder. The interpretation contract it
# renders has a CLOSED, bounded vocabulary (16 observed elements, 11
# space types, 5 spatial relations, 9 unknowns, 3 interpretations, 5
# limitations), so a complete, honest display map is possible.
#
# This module renders that contract in the requested language. The
# English output is byte-for-byte the historical string, so nothing
# changes for an English conversation.
#
# Read-only: no LLM, no network, no storage. An unmapped phrase is
# passed through in its original wording rather than dropped — a
# translation gap must never become a missing finding.
# ==========================================================


from __future__ import annotations


import re


CONTRACT = "VisionReportV1"
VERSION = "1.0"


# ----------------------------------------------------------
# SECTION HEADERS
# ----------------------------------------------------------

PHRASES = {

    "en": {
        "space_header": "1. Possible architectural space:",
        "confidence": "(confidence: %s)",
        "elements_header": "2. Visible elements:",
        "relations_header": "3. Possible spatial relations:",
        "unknowns_header": "4. Uncertain or undetermined:",
        "none": "- not determinable from image",
    },

    "fa": {
        "space_header": "۱. فضای معماری احتمالی:",
        "confidence": "(میزان اطمینان: %s)",
        "elements_header": "۲. عناصر قابل مشاهده:",
        "relations_header": "۳. روابط فضایی احتمالی:",
        "unknowns_header": "۴. نامشخص یا تعیین‌نشده:",
        "none": "- از تصویر قابل تعیین نیست",
    },
}


# ----------------------------------------------------------
# DISPLAY MAPS — the interpretation contract's CLOSED vocabulary
# ----------------------------------------------------------

SPACE_TYPE_DISPLAY = {

    "master bedroom": "اتاق خواب مستر",
    "bedroom": "اتاق خواب",
    "living room": "نشیمن",
    "kitchen": "آشپزخانه",
    "bathroom": "سرویس بهداشتی",
    "wc": "سرویس بهداشتی / WC",
    "pantry": "آبدارخانه",
    "storage": "انباری",
    "dining": "غذاخوری",
    "stair": "پله",
    "service": "فضای خدماتی",
    "corridor": "راهرو",
    "balcony": "بالکن",
    "entrance": "ورودی",
    "garden": "محوطه / باغ",
    "facade": "نمای ساختمان",
    # ARCHITECTURAL_VISION_OBSERVATION_V2 — a drawing is its OWN category:
    # a plan is a layout of many spaces, never one room.
    "plan": "پلان (نقشهٔ معماری)",
    "diagram": "دیاگرام",
    "service room": "فضای خدماتی",
    "dining room": "غذاخوری",
    "unknown": "نامشخص",
}


CONFIDENCE_DISPLAY = {

    "HIGH": "زیاد",
    "MEDIUM": "متوسط",
    "LOW": "کم",
}


PHRASE_DISPLAY = {

    # ---- observed elements ----
    "sleeping element visible": "عنصر خواب (تخت) دیده می‌شود",
    "daylight opening visible": "بازشوِ نور (پنجره) دیده می‌شود",
    "opening visible": "بازشو دیده می‌شود",
    "projecting outdoor platform visible": "بالکن بیرون‌آمده دیده می‌شود",
    "entrance threshold visible": "آستانهٔ ورودی دیده می‌شود",
    "facade plane visible": "صفحهٔ نما دیده می‌شود",
    "enclosed room volume visible": "حجم بستهٔ اتاق دیده می‌شود",
    "circulation passage visible": "مسیر گردش دیده می‌شود",
    "kitchen work zone visible": "ناحیهٔ کار آشپزخانه دیده می‌شود",
    "sanitary zone visible": "ناحیهٔ بهداشتی دیده می‌شود",
    "seating element visible": "عنصر نشستن دیده می‌شود",
    "storage or dressing element visible": "عنصر انبار یا لباس دیده می‌شود",
    "landscape area visible": "ناحیهٔ محوطه دیده می‌شود",
    "vertical enclosure surface visible": "سطح قائم (دیوار) دیده می‌شود",
    "horizontal floor plane visible": "صفحهٔ افقی کف دیده می‌شود",
    "private sleeping room visible": "اتاق خواب خصوصی دیده می‌شود",

    # ---- ARCHITECTURAL_VISION_GROUNDING_V1 ----
    "double bed arrangement visible": "چیدمان تخت دونفره دیده می‌شود",
    "sanitary fixture visible": "سرویس بهداشتی دیده می‌شود",
    "work surface visible": "سطح کار (میز) دیده می‌شود",
    "storage volume visible": "حجم انبار دیده می‌شود",

    # ---- spatial relations ----
    "Openings are arranged within the visible facade plane.":
        "بازشوها در صفحهٔ نمای قابل مشاهده چیده شده‌اند.",
    "The projecting outdoor platform is connected to the facade plane.":
        "بالکن بیرون‌آمده به صفحهٔ نما متصل است.",
    "The entrance threshold is part of the visible exterior composition.":
        "آستانهٔ ورودی بخشی از ترکیب بیرونیِ قابل مشاهده است.",
    "The daylight opening is associated with the enclosed sleeping space.":
        "بازشوِ نور به فضای بستهٔ خواب مربوط است.",
    "The seating element is located within the same visible room zone.":
        "عنصر نشستن در همان ناحیهٔ قابل مشاهدهٔ اتاق قرار دارد.",
    "Window openings are reported by the provider, but no visible opening was grounded.":
        "بازشوهای پنجره را مدل بینایی گزارش کرده است، اما هیچ بازشوی "
        "دیداری‌ای تعیین‌مکان (ground) نشد.",

    # ---- interpretations ----
    "The visible composition is interpreted as an exterior facade plane.":
        "ترکیب قابل مشاهده به‌عنوان صفحهٔ نمای بیرونی تفسیر می‌شود.",
    "The visible sleeping element supports an enclosed sleeping-space interpretation.":
        "عنصر خوابِ قابل مشاهده، تفسیر یک فضای بستهٔ خواب را پشتیبانی می‌کند.",

    # ---- possible functions ----
    "possible building entrance or exterior frontage":
        "احتمالاً ورودی ساختمان یا نمای بیرونی",
    "possible private couple bedroom":
        "احتمالاً اتاق خواب خصوصی زوجین",
    "likely bedroom": "به‌احتمال زیاد اتاق خواب",

    # ---- unknowns ----
    "exact floor count is not determinable from the visible evidence":
        "تعداد دقیق طبقات از شواهد دیداری قابل تعیین نیست",
    "structural system is not determinable from the image":
        "سیستم سازه‌ای از تصویر قابل تعیین نیست",

    # ---- inspection-outcome unknowns ----
    #
    # VISION_FIRST_FACADE_GROUNDING_V1 — the interpreter states its own
    # inspection outcome as a reason string. These five were absent from this
    # table, so `display_phrase` fell through and printed RAW ENGLISH inside a
    # Persian answer ("… reliable architectural evidence has not been
    # established."). Every one of them is now translated.
    "reliable architectural evidence has not been established":
        "شاهد معماری قابل اعتمادی برای این تصویر تثبیت نشد",
    "completed local inspection did not establish grounded architectural evidence":
        "بررسی محلی انجام‌شده شاهد معماری مستندی به دست نداد",
    "partial local evidence is available; semantic observations remain unknown":
        "شاهد محلی جزئی موجود است؛ مشاهدات معنایی نامشخص مانده‌اند",
    "local analysis capability unavailable; image evidence remains unknown":
        "قابلیت تحلیل محلی در دسترس نیست؛ شواهد تصویری نامشخص مانده است",
    "vision provider unavailable or failed; image evidence remains unknown":
        "سرویس بینایی در دسترس نبود یا خطا داد؛ شواهد تصویری نامشخص مانده است",
    "private bathroom connection is not visible":
        "اتصال سرویس خصوصی دیده نمی‌شود",
    "dressing or closet zone is not visible":
        "ناحیهٔ لباس یا کلوزت دیده نمی‌شود",
    "the private bathroom connection is not reported in the visible evidence (unknown, not absent)":
        "اتصال سرویس خصوصی در شواهد تصویری گزارش نشده است (نامشخص، نه غایب)",
    "the dressing or closet zone is not reported in the visible evidence (unknown, not absent)":
        "ناحیهٔ لباس یا کلوزت در شواهد تصویری گزارش نشده است (نامشخص، نه غایب)",
    "the private bathroom connection is reported without sufficient visible evidence (unverified)":
        "اتصال سرویس خصوصی بدون شاهد تصویری کافی گزارش شده است (تأییدنشده)",
    "the dressing or closet zone is reported without sufficient visible evidence (unverified)":
        "ناحیهٔ لباس یا کلوزت بدون شاهد تصویری کافی گزارش شده است (تأییدنشده)",
    "the visible evidence states that the private bathroom connection is not visible":
        "شواهد تصویری می‌گوید اتصال سرویس خصوصی دیده نمی‌شود",
    "the visible evidence states that the dressing or closet zone is not visible":
        "شواهد تصویری می‌گوید ناحیهٔ لباس یا کلوزت دیده نمی‌شود",
    "space type is not determinable from the image":
        "نوع فضا از تصویر قابل تعیین نیست",
    "functional use is not determinable from the image":
        "کاربری فضا از تصویر قابل تعیین نیست",
    "spatial relations are not determinable from the available evidence":
        "روابط فضایی از شواهد موجود قابل تعیین نیست",
    "no reliable architectural elements are sufficiently visible":
        "هیچ عنصر معماری قابل اعتمادی به‌اندازهٔ کافی دیده نمی‌شود",
    "some provider observations remain unresolved":
        "برخی مشاهدات مدل بینایی هنوز حل‌نشده مانده است",
    "exact dimensions, room areas, north orientation, materials and the structural system are not determinable from the visible evidence":
        "ابعاد دقیق، مساحت اتاق‌ها، جهت شمال، مصالح و سیستم سازه‌ای از شواهد "
        "دیداری قابل تعیین نیستند",

    # ---- limitations ----
    "interpretation is limited to visible image evidence":
        "تفسیر فقط محدود به شواهد دیداری تصویر است",
    "observed elements and inferred meanings are kept separate":
        "عناصر مشاهده‌شده و معناهای استنتاجی از هم جدا نگه داشته شده‌اند",
    "geometry is non-authoritative":
        "هندسهٔ استخراج‌شده اعتبار قطعی ندارد",
    "dimensions, hidden geometry, and unseen floors are not inferred":
        "ابعاد، هندسهٔ پنهان و طبقات دیده‌نشده استنتاج نمی‌شوند",
    "materials and structural systems are not asserted without visible evidence":
        "مصالح و سیستم سازه‌ای بدون شاهد دیداری اظهار نمی‌شوند",
}


# ARCHITECTURAL_VISION_OBSERVATION_V2 — the plan reading's own vocabulary.
# Keyed by LANGUAGE: an English answer must never carry a Persian zone or
# tier label. The `evidence` VALUES stay in the provider's own wording in
# both languages — they are a quotation, not a translation.

TIER_DISPLAY = {

    "fa": {
        "visible": "مشاهده‌شده",
        "observed": "مشاهده‌شده",
        "likely": "احتمالی",
        "unverified": "تأییدنشده",
        "reported": "گزارش‌شده",
        "symbol_reading": "خوانش نماد پلان",
        "provider_only": "فقط مدل بینایی",
        "unknown": "نامشخص",
    },

    "en": {
        "visible": "observed",
        "observed": "observed",
        "likely": "likely",
        "unverified": "unverified",
        "reported": "reported",
        "symbol_reading": "plan symbol reading",
        "provider_only": "provider only",
        "unknown": "unknown",
    },
}


# ARCHITECTURAL_VISION_EVIDENCE_PRECISION_V1 — why a claim is not a fact.

REASON_DISPLAY = {

    "fa": {
        "label_uncorroborated":
            "برچسب خوانده‌شده بدون هیچ شاهد دیگری در خروجی مدل بینایی",
        "furniture_symbol_on_drawing":
            "نام مبلمان در یک نقشه، خوانش نماد پلان است نه مشاهدهٔ شیء؛ "
            "کاربری را پشتیبانی می‌کند ولی فضا را اثبات نمی‌کند",
        "furniture_not_observed":
            "هیچ مبلمانی با شاهد قطعی مشاهده نشد",
        "unsupported_relation":
            "این رابطه کنار گذاشته شد چون دست‌کم یک سرِ آن فضای "
            "پشتیبانی‌شده نیست",
        "provider_label_not_grounded":
            "برچسب ادعایی مدل بینایی؛ خوانش محلی آن را تأیید نکرد",
        "provider_label_synonym_for_grounded_space":
            "برچسب ادعایی مدل بینایی؛ معادل فضایی است که خوانش محلی "
            "مستقل تأیید کرده — جای برچسب منبع را نمی‌گیرد",
        "window_not_grounded":
            "مدل بینایی فقط در فهرست عناصر گفته است؛ نه تعیین‌مکان (bounding) "
            "داده و نه بازشوی دیداری‌ای تعیین‌مکان شد",
    },

    "en": {
        "label_uncorroborated":
            "readable label with NO corroborating evidence anywhere else in "
            "the provider payload",
        "furniture_symbol_on_drawing":
            "a furniture name on a DRAWING is a plan-symbol reading, not an "
            "observed object — it supports a function, it does not "
            "establish a space",
        "furniture_not_observed": "no furniture was confidently observed",
        "unsupported_relation":
            "withheld: at least one endpoint is not a supported space",
        "provider_label_not_grounded":
            "provider label claim; the local reading did not confirm it",
        "provider_label_synonym_for_grounded_space":
            "provider label claim; a synonym for a space the local reading "
            "already grounded — it does not replace the source label",
        "window_not_grounded":
            "the provider listed it in its element list only; it supplied no "
            "localization and no visible opening was grounded",
    },
}


OPENING_DISPLAY = {

    "fa": {
        "door": "در / بازشو",
        "entrance": "ورودی",
        "window": "پنجره",
        "opening": "بازشو",
    },

    "en": {
        "door": "door",
        "entrance": "entrance",
        "window": "window",
        "opening": "opening",
    },
}


BUILDING_TYPE_DISPLAY = {

    "fa": {
        "residential": "مسکونی",
        "commercial": "تجاری",
        "office": "اداری",
        "mixed": "مختلط",
    },

    "en": {
        "residential": "residential",
        "commercial": "commercial",
        "office": "office",
        "mixed": "mixed use",
    },
}


# ARCHITECTURAL_VISION_EVIDENCE_PRECISION_V1 — the evidence-source names,
# so every published conclusion can say WHERE its evidence came from.

SOURCE_DISPLAY = {

    "fa": {
        "label": "برچسب خوانده‌شده",
        "geometry": "هندسهٔ دیده‌شده",
        "symbol": "نمادِ پلان",
        "furniture": "مبلمان/تجهیزات",
        "fixture": "تجهیزات بهداشتی",
        "relation": "رابطهٔ گزارش‌شده",
        "provider_only": "فقط مدل بینایی (بدون شاهد دیگر)",
        "local_ocr": "OCR محلی",
        "local_raster_geometry": "هندسهٔ رستری محلی",
    },

    "en": {
        "label": "read label",
        "geometry": "visible geometry",
        "symbol": "plan symbol",
        "furniture": "furniture / fixture",
        "fixture": "fixture",
        "relation": "stated relation",
        "provider_only": "provider only (no other evidence)",
        "local_ocr": "local OCR",
        "local_raster_geometry": "local raster geometry",
    },
}


WALL_DISPLAY = {

    "fa": {
        "enclosure": "دیوار محیطی (پیرامونی)",
        "partition": "دیوار جداکنندهٔ داخلی",
    },

    "en": {
        "enclosure": "perimeter / enclosure wall",
        "partition": "interior partition wall",
    },
}


FURNITURE_DISPLAY = {

    "fa": {
        "bed": "تخت",
        "sofa": "مبل",
        "couch": "مبل",
        "chair": "صندلی",
        "table": "میز",
        "desk": "میز کار",
        "cabinet": "کابینت",
        "counter": "کانتر",
        "wardrobe": "کمد",
        "closet": "کلوزت",
        "toilet": "توالت",
        "sink": "روشویی",
        "basin": "روشویی",
        "shower": "دوش",
        "bathtub": "وان",
    },

    "en": {},
}


PLAN_SECTION_HEADERS = {

    "en": {
        "labels": "5. Read labels — verbatim transcription:",
        "labels_note": "(the printed text exactly as read; the meaning is "
                       "shown separately and never replaces it)",
        "function": "means",
        "unmapped": "no space mapped",
        "occurrences": "occurrences",
        "spaces": "6. Space functions — interpretation:",
        "building": "Building type:",
        "furniture": "7. Inferred functions (from observed furniture):",
        "elements": "8. Architectural elements and openings:",
        "relations": "9. Spatial relationships (supported endpoints only):",
        "zones": "10. Zoning:",
        "unverified": "11. Unverified provider claims:",
        "unknowns": "12. Unknown / not determinable:",
        "none": "- none",
        "evidence": "evidence",
        "source": "source",
        "supporting_label": "provider label claim (unverified)",
    },

    "fa": {
        "labels": "۵. برچسب‌های خوانده‌شده — رونویسی عین متن:",
        "labels_note": "(متنی که خوانده شده، عیناً؛ معنا جداگانه نشان داده می‌شود "
                       "و هرگز جای متن اصلی را نمی‌گیرد)",
        "function": "معنا",
        "unmapped": "به فضایی نگاشت نشد",
        "occurrences": "نمونه",
        "spaces": "۶. کاربری فضاها — تفسیر:",
        "building": "نوع بنا:",
        "furniture": "۷. کاربری‌های استنتاج‌شده از مبلمان مشاهده‌شده:",
        "elements": "۸. عناصر معماری و بازشوها:",
        "relations": "۹. روابط فضایی (فقط با دو سرِ پشتیبانی‌شده):",
        "zones": "۱۰. پهنه‌بندی:",
        "unverified": "۱۱. ادعاهای تأییدنشدهٔ مدل بینایی:",
        "unknowns": "۱۲. نامشخص / قابل تعیین نیست:",
        "none": "- هیچ",
        "evidence": "شاهد",
        "source": "منبع",
        "supporting_label": "برچسب ادعایی مدل (تأییدنشده)",
    },
}


# The zone bands, in the order they are rendered. The open / semi-open
# band keeps a terrace or veranda out of the interior zoning.
ZONE_ORDER = (
    "public",
    "private",
    "service",
    "circulation",
    "open_semi_open",
    "external",
)


# ZONE_DISPLAY gains the open / semi-open band (TASK 4).

ZONE_DISPLAY = {

    "fa": {
        "public": "عمومی",
        "private": "خصوصی",
        "service": "خدماتی",
        "circulation": "گردش و دسترسی",
        "open_semi_open": "باز / نیمه‌باز",
        "external": "بیرونی",
    },

    "en": {
        "public": "public",
        "private": "private",
        "service": "service",
        "circulation": "circulation",
        "open_semi_open": "open / semi-open",
        "external": "external",
    },
}


def _language(value):

    text = str(value or "").strip().lower()

    if (
        text.startswith("fa")
        or text.startswith("persian")
        or text in ("ir", "farsi")
    ):

        return "fa"

    return "en"


def display_phrase(phrase, language="fa"):

    """The phrase in the requested language, or the original wording.

    Never returns an empty string for a non-empty input: a missing
    translation must not silently remove a finding.
    """

    text = str(phrase or "").strip()

    if not text:

        return ""

    if _language(language) == "en":

        return text

    if text in PHRASE_DISPLAY:

        return PHRASE_DISPLAY[text]

    # "possible <space_type> function" is the ONE templated phrase.
    if text.startswith("possible ") and text.endswith(" function"):

        inner = text[len("possible "):-len(" function")].strip()

        return "کاربری احتمالی: " + display_space_type(inner, "fa")

    # "The visible elements support a possible <space_type> interpretation."
    prefix = "The visible elements support a possible "

    if text.startswith(prefix) and text.endswith(" interpretation."):

        inner = text[len(prefix):-len(" interpretation.")].strip()

        return (
            "عناصر قابل مشاهده، تفسیر «%s» را ممکن می‌کنند."
            % display_space_type(inner, "fa")
        )

    # ==================================================
    # ARCHITECTURAL_VISION_OBSERVATION_V2 — the PLAN READING phrases.
    # Templated, so a plan answer stays in the conversation's language.
    # ==================================================

    # "possible <space> function (visible <furniture>)"
    if text.startswith("possible ") and " function (visible " in text:

        inner, _sep, rest = text[len("possible "):].partition(
            " function (visible "
        )

        return (
            "کاربری احتمالی: " + display_space_type(inner.strip(), "fa")
            + " (با شاهد " + rest.rstrip(")").strip() + ")"
        )

    # "The visible evidence places <a> adjacent to <b>."
    adjacency = re.match(
        r"^The visible evidence places (.+?) adjacent to (.+?)\.$", text
    )

    if adjacency:

        return (
            "شواهد دیداری، %s را مجاور %s نشان می‌دهد."
            % (
                display_space_type(adjacency.group(1), "fa"),
                display_space_type(adjacency.group(2), "fa"),
            )
        )

    # "The visible evidence shows a circulation space (<a>)."
    circulation = re.match(
        r"^The visible evidence shows a circulation space \((.+?)\)\.$",
        text,
    )

    if circulation:

        return (
            "شواهد دیداری یک فضای گردش (%s) را نشان می‌دهد."
            % display_space_type(circulation.group(1), "fa")
        )

    # "Circulation space named by the plan: <a>."
    named = re.match(
        r"^Circulation space named by the plan: (.+?)\.$", text
    )

    if named:

        return (
            "فضای گردشِ نام‌برده‌شده در پلان: %s."
            % display_space_type(named.group(1), "fa")
        )

    if text == "Visible door openings connect the spaces of the plan.":

        return "بازشوهای در، فضاهای پلان را به هم متصل می‌کنند."

    if text == "Visible window openings are reported on the plan.":

        return "بازشوهای پنجره در پلان گزارش شده‌اند (تأییدنشده)."

    # ARCHITECTURAL_VISION_EVIDENCE_PRECISION_V1 — the window is NOT
    # grounded, and the answer says exactly that.
    if text == ("Window openings are reported by the provider, but no "
                "visible opening was grounded."):

        return (
            "بازشوهای پنجره را مدل بینایی گزارش کرده است، اما هیچ بازشوی "
            "دیداری‌ای تعیین‌مکان (ground) نشد."
        )

    if text == (
        "Visible perimeter window openings are grounded by local raster geometry."
    ):

        return (
            "بازشوهای پنجرهٔ پیرامونی با تحلیل رستری محلی تعیین‌مکان شدند."
        )

    # "the <zone> is named by the visible evidence (likely)"
    named_zone = re.match(
        r"^the (.+?) is named by the visible evidence \(likely\)$", text
    )

    if named_zone:

        return (
            "%s با شواهد دیداری نام‌برده شده است (احتمالی)"
            % _zone_label(named_zone.group(1))
        )

    return text


def _zone_label(label):

    """A readable Persian label for the two private-zone phrases."""

    if "bathroom" in label:

        return "اتصال سرویس خصوصی"

    if "closet" in label or "dressing" in label:

        return "ناحیهٔ لباس یا کلوزت"

    return label


def display_space_type(space_type, language="fa"):

    text = str(space_type or "unknown").strip()

    if _language(language) == "en":

        return text

    return SPACE_TYPE_DISPLAY.get(text, text)


def display_confidence(confidence, language="fa"):

    text = str(confidence or "LOW").strip().upper()

    if _language(language) == "en":

        return text

    return CONFIDENCE_DISPLAY.get(text, text)


def _evidence_report(interpretation, language="en"):

    """The FULL evidence rendering of the interpretation, in `language`.

    ARCHITECTURAL_VISION_REPORT_UX_V1 — this is the pre-UX report, kept
    verbatim: every numbered section, every evidence source, every tier.
    It is the DEBUG / EVIDENCE surface (`render_vision_evidence_report`)
    and it is what the user-facing plan report replaced. Nothing here was
    deleted, so no diagnostic capability was lost.

    The English rendering is byte-for-byte the historical output.
    """

    if not isinstance(interpretation, dict):

        return ""

    lang = _language(language)

    text = PHRASES[lang]

    def block(values):

        items = [
            display_phrase(value, lang) for value in (values or [])
        ]

        items = [item for item in items if item]

        if not items:

            return text["none"]

        return "\n".join("- " + item for item in items)

    return (
        text["space_header"] + "\n"
        + display_space_type(
            interpretation.get("space_type") or "unknown", lang
        )
        + " "
        + text["confidence"]
        % display_confidence(
            interpretation.get("confidence") or "LOW", lang
        )
        + "\n\n"
        + text["elements_header"] + "\n"
        + block(interpretation.get("observed_elements"))
        + "\n\n"
        + text["relations_header"] + "\n"
        + block(interpretation.get("spatial_relations"))
        + "\n\n"
        + text["unknowns_header"] + "\n"
        + block(interpretation.get("unknowns"))
        # ==================================================
        # ARCHITECTURAL_VISION_OBSERVATION_V2 — the PLAN READING sections.
        #
        # Rendered only when the interpretation carries `plan_reading`, so
        # every non-plan answer (and every historical `ground=False`
        # answer) is byte-for-byte unchanged.
        # ==================================================
        + _plan_section(interpretation, lang)
        # ==================================================
        # ARCHITECTURAL_VISION_GROUNDING_V1 — an ADDITIVE fifth section.
        #
        # It is rendered only when the interpretation carries the
        # grounding contract, so the historical four-section output is
        # byte-for-byte unchanged (and so is the English rendering that
        # an English conversation pins).
        # ==================================================
        + _grounding_section(interpretation, lang)
    )


# ==========================================================
# ARCHITECTURAL_VISION_REPORT_UX_V1 — THE USER-FACING REPORT
#
# The evidence report above is what a debugger wants. This is what an
# architect wants: a short, natural, scannable explanation.
#
# It is a PURE PROJECTION of the same structured interpretation. It never
# invents an adjacency, a dimension or a space the contract does not carry;
# anything the contract does not support is DROPPED, never rewritten.
# Nothing is deleted: the full evidence stays available through
# `render_vision_evidence_report` and through the structured contract.
#
# The user-facing plan report is rendered in Persian because the grounded
# SOURCE LABELS are Persian and must be printed verbatim; an English
# conversation therefore keeps the historical rendering byte-for-byte.
# ==========================================================

NUMBER_WORDS = {

    2: "دو", 3: "سه", 4: "چهار", 5: "پنج", 6: "شش",
    7: "هفت", 8: "هشت", 9: "نه", 10: "ده",
}


ARCHITECTURAL_PHRASES = {

    "plan_use": "این تصویر یک پلان %s است.",
    "plan_plain": "این تصویر یک پلان معماری است.",

    "spaces": "در پلان %s دیده می‌شود.",

    "zone_private": "%s بخش خصوصی پلان را تشکیل می‌دهند.",
    "zone_private_one": "%s بخش خصوصی پلان است.",
    "zone_public_many": "%s فضاهای عمومی پلان هستند.",
    "zone_public": "%s فضای عمومی اصلی پلان است.",
    "zone_service": "%s در گروه فضاهای خدماتی قرار می‌گیرند.",
    "zone_service_one": "%s در گروه فضاهای خدماتی قرار می‌گیرد.",
    "zone_open": "%s فضاهای باز یا نیمه‌باز پلان هستند.",
    "zone_open_one": "%s فضای باز یا نیمه‌باز پلان است.",
    "zone_circulation": "فضای گردش و دسترسی: %s.",
    "zone_external": "فضاهای بیرونی: %s.",

    "adjacency": "%s و %s در پلان کنار یکدیگر قرار دارند.",
    "circulation_absent": "فضای گردش مستقلی در پلان نام برده نشده است.",
    "partition": "پلان به %s فضای بسته تقسیم شده است.",
    "partition_plain": "پلان به چند فضای بسته تقسیم شده است.",

    "windows": "چند پنجره در جداره‌های پیرامونی دیده می‌شود.",
    "window_one": "یک پنجره در جداره‌های پیرامونی دیده می‌شود.",

    "unknowns": "از روی این تصویر %s قابل تعیین نیست.",
    "unknowns_plain": "جزئیات دقیق این پلان از روی تصویر قابل تعیین نیست.",
    "orientation": "جهت شمال",
    "dimensions": "ابعاد دقیق و مساحت فضاها",
    "materials": "مصالح",
    "structure": "سیستم سازه‌ای",
}


# ==========================================================
# FACADE-03D — THE USER-FACING FACADE REPORT
#
# A facade / render is NOT a plan. When the canonical image type is a facade
# or an architectural render, the answer is a short description of the visible
# facade composition — never plan vocabulary (plan spaces, circulation,
# swing-door symbols). The model's own observations are appended separately by
# `render_vision_report`, still marked unverified.
# ==========================================================

FACADE_PHRASES = {

    "fa": {
        "render": "این تصویر یک رندر معماری (نمای ساختمان) است.",
        "facade": "این تصویر یک نمای معماری است.",
        "elements_header": "عناصر نمای قابل مشاهده:",
        "unknowns_header": "از روی این تصویر قابل تعیین نیست:",
        "note": (
            "این خوانش از طبقه‌بندی مدل بینایی می‌آید و هنوز با شاهد مستقل "
            "تأیید نشده است؛ از آن نتیجهٔ قطعی گرفته نمی‌شود."
        ),
    },

    "en": {
        "render": "This image is an architectural rendering (building facade).",
        "facade": "This image is an architectural facade.",
        "elements_header": "Visible facade elements:",
        "unknowns_header": "Not determinable from this image:",
        "note": (
            "This reading comes from the vision model's classification and is "
            "not yet confirmed by independent evidence; no definite conclusion "
            "is drawn from it."
        ),
    },
}


def _facade_report(interpretation, language="fa"):

    """The user-facing FACADE answer.

    FACADE-03D — a pure projection of the interpretation contract: the
    identification, the closed-vocabulary interpretation lines, the grounded
    observed elements, the spatial relations and the honest unknowns. It
    invents nothing and never emits plan vocabulary. The model's own
    observations are appended by the caller, still marked unverified.
    """

    lang = _language(language)

    text = FACADE_PHRASES[lang]

    paragraphs = []

    image_type = str(interpretation.get("image_type") or "").strip().lower()

    if "render" in image_type or "photo" in image_type:

        paragraphs.append(text["render"])

    else:

        paragraphs.append(text["facade"])

    interpretation_lines = [
        display_phrase(line, lang)
        for line in (interpretation.get("architectural_interpretation") or [])
    ]

    interpretation_lines = [line for line in interpretation_lines if line]

    if interpretation_lines:

        paragraphs.append(" ".join(interpretation_lines))

    elements = [
        display_phrase(element, lang)
        for element in (interpretation.get("observed_elements") or [])
    ]

    elements = [element for element in elements if element]

    if elements:

        paragraphs.append(
            text["elements_header"] + " " + "، ".join(elements) + "."
        )

    relations = [
        display_phrase(relation, lang)
        for relation in (interpretation.get("spatial_relations") or [])
    ]

    relations = [relation for relation in relations if relation]

    if relations:

        paragraphs.append(" ".join(relations))

    unknowns = [
        display_phrase(unknown, lang)
        for unknown in (interpretation.get("unknowns") or [])
    ]

    unknowns = [unknown for unknown in unknowns if unknown]

    if unknowns:

        paragraphs.append(
            text["unknowns_header"] + " " + "، ".join(unknowns) + "."
        )

    paragraphs.append(text["note"])

    return "\n\n".join(paragraphs)


def _fa_join(items):

    """A natural Persian enumeration: «الف، ب، ج و د»."""

    values = [item for item in (items or []) if item]

    if not values:

        return ""

    if len(values) == 1:

        return values[0]

    return "، ".join(values[:-1]) + " و " + values[-1]


def _counted_label(text, count):

    """«اتاق خواب» ×2 -> «دو اتاق خواب».  The source text is untouched."""

    if count <= 1:

        return text

    word = NUMBER_WORDS.get(count)

    if not word:

        return text

    return "%s %s" % (word, text)


def _grounded_read_labels(plan):

    """The printed room labels, grouped by EXACT text, in reading order.

    Only labels whose meaning the plan actually zones are kept, so a
    dimension string or a watermark can never enter the prose. The text
    itself is never translated, normalized or replaced.
    """

    grounded = set()

    for value in (plan.get("zones") or {}).values():

        for space in value or []:

            grounded.add(space)

    ordered = []
    seen = {}

    for entry in plan.get("read_labels") or []:

        if not isinstance(entry, dict):

            continue

        text = str(entry.get("text") or "").strip()
        space = entry.get("semantic_function")

        if not text or space not in grounded:

            continue

        if text in seen:

            seen[text]["count"] += 1

            continue

        record = {"text": text, "space": space, "count": 1}
        seen[text] = record
        ordered.append(record)

    return ordered


def _records_by_space(records):

    grouped = {}

    for record in records:

        grouped.setdefault(record["space"], []).append(record)

    return grouped


def _architectural_report(interpretation, plan):

    """Five short paragraphs an architect would actually write.

    ARCHITECTURAL_VISION_REPORT_UX_V1 — the user-facing plan answer:
    what the image is, the grounded spaces, the organisation, the access
    and openings, and the architecturally meaningful unknowns. No
    confidence tiers, no evidence taxonomy, no provider vocabulary.
    """

    if plan.get("panel_readings") and plan.get("fusion"):
        from core.vision.local_plan_sheet_v1 import render_sheet_report
        return render_sheet_report(plan)

    text = ARCHITECTURAL_PHRASES

    paragraphs = []

    # ---- 1. what the image is ----
    building = plan.get("building_type") or {}

    use = BUILDING_TYPE_DISPLAY["fa"].get(
        str(building.get("value") or "").strip().lower()
    )

    paragraphs.append(
        text["plan_use"] % use if use else text["plan_plain"]
    )

    grounded_items = [item for item in plan.get("furniture") or []
                      if item.get("source") == "local_raster_symbol_topology"
                      and item.get("status") == "visible"]
    if grounded_items:
        paragraphs[0] = (
            "این تصویر یک پلان مسکونی مبله را نشان می‌دهد."
            if use == BUILDING_TYPE_DISPLAY["fa"].get("residential")
            else "این تصویر یک پلان مبله را نشان می‌دهد."
        )
        supported = {entry.get("space") for entry in plan.get("inferred_functions") or []}
        functions = []
        for function, phrase in (
            ("bedroom", "فضاهای خواب و خصوصی"),
            ("living room", "نشیمن و فضای مشترک"),
            ("kitchen", "آشپزخانه و بخش خدماتی"),
            ("bathroom", "حمام یا سرویس بهداشتی"),
            ("dining", "فعالیت غذاخوری"),
        ):
            if function in supported:
                functions.append(phrase)
        if functions:
            paragraphs.append("چیدمان قابل مشاهده احتمالاً شامل " + _fa_join(functions) + " است.")
        labels = {
            "bed": "تخت", "sofa": "مبلمان نشیمن", "seating": "مبلمان نشیمن", "chair": "صندلی",
            "dining_surface": "سطح غذاخوری", "kitchen_counter": "کانتر و کابینت آشپزخانه",
            "kitchen_sink_arrangement": "سینک", "sanitary_fixture": "تجهیزات سرویس",
            "storage_cabinet": "کمد",
        }
        visible = list(dict.fromkeys(labels[item["class"]] for item in grounded_items))
        paragraphs.append("مبلمان و تجهیزات دیده‌شده شامل " + _fa_join(visible) + " است.")

    # ---- 2. the grounded spaces (source labels, with multiplicity) ----
    records = _grounded_read_labels(plan)

    if records:

        paragraphs.append(
            text["spaces"] % _fa_join(
                [_counted_label(r["text"], r["count"]) for r in records]
            )
        )

    # ---- 3. spatial organisation ----
    zones = plan.get("zones") or {}

    by_space = _records_by_space(records)

    def names(space_names):

        """(counted source labels, total grounded instances) for a zone."""

        collected = []
        total = 0

        for space in space_names or []:

            for record in by_space.get(space) or []:

                collected.append(
                    _counted_label(record["text"], record["count"])
                )

                total += record["count"]

        return collected, total

    organisation = []

    for space_names, many, one in (
        (zones.get("private"), text["zone_private"], text["zone_private_one"]),
        (zones.get("public"), text["zone_public_many"], text["zone_public"]),
        (zones.get("service"), text["zone_service"], text["zone_service_one"]),
        (zones.get("open_semi_open"), text["zone_open"], text["zone_open_one"]),
    ):

        labels, total = names(space_names)

        if not labels:

            continue

        organisation.append(
            (one if total == 1 else many) % _fa_join(labels)
        )

    for space_names, template in (
        (zones.get("circulation"), text["zone_circulation"]),
        (zones.get("external"), text["zone_external"]),
    ):

        labels, _total = names(space_names)

        if labels:

            organisation.append(template % _fa_join(labels))

    if organisation:

        paragraphs.append(" ".join(organisation))

    # ---- 4. circulation, connection and openings ----
    access = []

    for relation in plan.get("relations") or []:

        if not isinstance(relation, dict):

            continue

        between = relation.get("between") or []
        verified = relation.get("between_verified") or []

        if len(between) != 2 or not all(verified):

            continue

        endpoints = []

        for space in between:

            group = by_space.get(space) or []

            if not group:

                break

            endpoints.append(
                _counted_label(group[0]["text"], group[0]["count"])
            )

        if len(endpoints) == 2:

            access.append(text["adjacency"] % (endpoints[0], endpoints[1]))

    connected = bool(access)

    partition = ((plan.get("wall_reading") or {}).get("partition") or {})

    room_count = partition.get("room_count")

    if isinstance(room_count, int) and room_count > 1:

        word = NUMBER_WORDS.get(room_count)

        access.append(
            text["partition"] % word if word else text["partition_plain"]
        )

    elif partition.get("multiple_spaces"):

        access.append("پلان چند فضای جداشده دارد؛ تعداد دقیق فضاهای بسته از این تصویر قطعی نیست.")

    else:

        access.append("تعداد دقیق فضاهای بسته از این تصویر مشخص نیست.")

    element_items = plan.get("architectural_elements") or []
    stair_items = [e for e in element_items if e.get("type") == "stair"]
    if not connected and not names(zones.get("circulation"))[0] and not stair_items:

        access.append(text["circulation_absent"])

    window_instances = 0

    for opening in plan.get("openings") or []:

        if not isinstance(opening, dict):

            continue

        if opening.get("kind") != "window":

            continue

        if opening.get("status") != "visible":

            continue

        window_instances += int(opening.get("instance_count") or 0)

    if window_instances > 1:

        access.append(text["windows"])

    elif window_instances == 1:

        access.append(text["window_one"])

    if access:

        paragraphs.append(" ".join(access))

    # Project only locally grounded instances; no new analysis or provider call.
    symbols = []
    if stair_items:
        count = len(stair_items)
        symbols.append(
            (NUMBER_WORDS.get(count, str(count)) + " مسیر پله‌ای در پلان قابل تشخیص است.")
            if count > 1 else "یک مسیر پله‌ای در پلان قابل تشخیص است."
        )
        counts = [e.get("attributes", {}).get("step_count") for e in stair_items]
        if all(type(n) is int and 1 <= n <= 100 for n in counts) and len(set(counts)) == 1:
            symbols.append("در " + ("هرکدام" if count > 1 else "این مسیر") + " " + NUMBER_WORDS.get(counts[0], str(counts[0])) + " پله قابل شمارش است.")
    meanings = plan.get("element_interpretation") or []
    level = next((m.get("plan_level_relationship") for m in meanings if m.get("plan_level_relationship")), None)
    if level:
        def number(value):
            return ("%g" % value).translate(str.maketrans("0123456789.", "۰۱۲۳۴۵۶۷۸۹٫"))
        def level_number(value):
            return (("+" if value > 0 else "") + ("%.2f" % value)).translate(str.maketrans("0123456789.", "۰۱۲۳۴۵۶۷۸۹٫"))
        symbols.append("کدهای تراز " + level_number(level["from_m"]) + " و " + level_number(level["to_m"]) + " خوانده می‌شوند؛ اختلاف تراز " + number(level["difference_m"]) + " متر است.")
        derived = next((m for m in meanings if m.get("type") == "derived_stair_riser" and m.get("provenance") == "computed_from_grounded_evidence" and m.get("association") == "general_unassigned"), None)
        if derived:
            symbols.append("با " + number(derived["step_count"]) + " پله و این اختلاف تراز، ارتفاع تقریبی هر پله " + number(derived["derived_riser_cm"]) + " سانتی‌متر محاسبه می‌شود.")
    rises = [m for m in meanings if m.get("rise_basis") == "grounded_step_count_times_grounded_riser"]
    for rise in rises:
        symbols.append("اختلاف ارتفاع یکی از مسیرهای پله‌ای از تعداد پله و ارتفاع درج‌شدهٔ آن، " + ("%g" % rise["total_rise_m"]) + " متر به‌دست می‌آید.")
    if any(m.get("type") == "service_shaft_candidate" for m in meanings):
        symbols.append("یک فضای محصور کوچک کنار بخش بهداشتی، احتمالاً داکت خدماتی است.")
    if any(e.get("type") == "door" for e in element_items):
        symbols.append("نمادهای بازشوی در نیز قابل تشخیص‌اند.")
    if any(m.get("type") == "structural_grid_organization_candidate" for m in meanings):
        symbols.append("نشانه‌های ستون احتمالی و محورهای شبکه نیز دیده می‌شوند.")
    elif any(e.get("type") == "axis" for e in element_items):
        symbols.append("نشانه‌های محورهای شبکه در پلان دیده می‌شوند.")
    if symbols:
        paragraphs.append(" ".join(symbols))

    # ---- 5. what the image cannot determine ----
    missing = []

    for key, phrase in (
        ("orientation_stated", text["orientation"]),
        ("dimensions_stated", text["dimensions"]),
        ("materials_stated", text["materials"]),
        ("structure_stated", text["structure"]),
    ):

        if plan.get(key) is False:

            missing.append(phrase)

    paragraphs.append(
        text["unknowns"] % _fa_join(missing) if missing
        else text["unknowns_plain"]
    )

    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def render_vision_evidence_report(interpretation, language="en"):

    """DEBUG / EVIDENCE MODE — the full pre-UX rendering, both languages."""

    return _evidence_report(interpretation, language)


PROVIDER_SUMMARY_PHRASES = {
    "fa": {
        "drawing_type": (
            "مدل تصویر را «%s» تشخیص داده است؛ این تشخیص هنوز با شاهد مستقل "
            "تأیید نشده."
        ),
        "grounded_header": "مشاهدات تأییدشده با شاهد مستقل:",
        "observations_header": "مشاهدات معماری مدل (تأییدنشده با شاهد مستقل):",
        "texts_header": "متن و اعداد خوانده‌شده توسط مدل (تأییدنشده):",
        "ambiguous_header": "خوانش‌های مبهم مدل:",
        "unknowns_header": "مواردی که مدل نامشخص اعلام کرده است:",
        "item": "• %s",
        "note": (
            "بخش‌های بالا مشاهدات مدل بینایی است و با شاهد مستقل تأیید نشده‌اند؛ "
            "از آن‌ها نتیجهٔ قطعی گرفته نمی‌شود."
        ),
    },
    "en": {
        "drawing_type": (
            "The model identified the image as \"%s\"; this identification is "
            "not yet confirmed by independent evidence."
        ),
        "grounded_header": "Confirmed by independent evidence:",
        "observations_header": "Model architectural observations (not independently verified):",
        "texts_header": "Text and numbers read by the model (not independently verified):",
        "ambiguous_header": "Ambiguous model readings:",
        "unknowns_header": "What the model states as unknown:",
        "item": "- %s",
        "note": (
            "The sections above are the vision model's observations and are not "
            "confirmed by independent evidence; no definite conclusion is drawn "
            "from them."
        ),
    },
}


# ==========================================================
# R2_USER_FACING_EYE_HANDOFF_V1
#
# The user-facing report could say "the exact number of storeys cannot be
# determined" while the model had in fact counted them, and it printed
# "no balconies" as a positive observation. The architectural observation
# contract already carries both facts; this section speaks them.
#
# Additive only: it renders nothing unless the interpretation carries an
# `architectural_observation` with content, so legacy interpretations and
# plan reports keep their exact historical output.
# ==========================================================

OBSERVATION_SECTION_PHRASES = {
    "fa": {
        "floors_header": "طبقات قابل مشاهده (مشاهدهٔ مدل، تأییدنشده با شاهد مستقل):",
        "floors_with_ground": (
            "%s طبقهٔ قابل مشاهده، شامل همکف و %s طبقهٔ بالایی."
        ),
        "floors_total": "%s طبقهٔ قابل مشاهده (مجموع).",
        "floors_no_ground": "%s طبقهٔ قابل مشاهده.",
        "parapet_note": "جان‌پناه یا باند بام به‌عنوان طبقه شمرده نشده است.",
        "partial_note": (
            "بخشی از ساختمان در کادر تصویر نیست؛ این شمارش حداقل تعداد است."
        ),
        "materials_header": "مصالح نام‌برده‌شده توسط مدل (تأییدنشده):",
        # ---- VISION_MATERIAL_HEDGE_REPORT_FIDELITY_V1 ----
        # The observation already records `hedged`. A material the model only
        # CONSIDERED POSSIBLE is a different level of evidence from one it
        # NAMED, so it is reported separately; in one list, "Possibly marble"
        # reads exactly like "marble".
        "tentative_header": (
            "مصالحی که مدل با عدم‌قطعیت نام برده است (تأییدنشده):"
        ),
        # The model's own wording is quoted so the qualifier ("possibly",
        # "appears to be") stays visible; the label alone would hide it.
        "tentative_item": "• %s (عبارت مدل: «%s»)",
        # MATERIAL_HEDGE_PHRASE_FIDELITY_V1_1 — when this phrase's coarse
        # family is ALREADY named by a different observation, the identity is
        # not repeated, but the phrase is NOT deleted: it is a separate claim
        # about a separate component. Quote only.
        "tentative_quote_item": "• مشاهدهٔ احتمالی دیگر: «%s»",
        # ---- VISION_MATERIAL_SEMANTICS_V1 ----
        # "stone or marble" names two materials and chooses neither.
        "alternatives_header": (
            "گزینه‌های نام‌برده‌شده که مدل هیچ‌کدام را قطعی نگفته است "
            "(تأییدنشده):"
        ),
        "alternative_join": " یا ",
        "negative_header": (
            "مواردی که مدل صریحاً غایب یا نادیدنی گزارش کرده است:"
        ),
        "negative_note": (
            "این موارد شاهدِ نبودِ عنصر در این تصویر است، نه اثبات نبودِ آن در "
            "ساختمان."
        ),
        "item": "• %s",
        # ---- ARCHITECTURAL_KNOWLEDGE_HANDOFF_V1 ----
        # The observation lists the material; this says what the TERM means.
        # The header states plainly that a lookup is not independent
        # confirmation, so the reader cannot mistake knowledge for evidence.
        "knowledge_header": (
            "از نظر دانش معماری (تطبیق اصطلاح، نه تأیید مستقل تصویر):"
        ),
        "knowledge_item": (
            "• «%s» با دستهٔ دانشی «%s» مطابقت دارد؛ ویژگی‌های عمومی: %s."
        ),
        "knowledge_no_properties": "• «%s» با دستهٔ دانشی «%s» مطابقت دارد.",
        # MATERIAL_HEDGE_PHRASE_FIDELITY_V1_1 — a hedged observation resolves
        # to the same ontology identity, but the LOOKUP is tentative: it must
        # not read as a definite identification of the pictured material.
        "knowledge_tentative_item": (
            "• «%s» با دستهٔ دانشی «%s» مطابقت دارد، اما این یک تطبیق اصطلاحی "
            "احتمالی است، نه شناسایی قطعی مصالح؛ ویژگی‌های عمومی: %s."
        ),
        "knowledge_tentative_no_properties": (
            "• «%s» با دستهٔ دانشی «%s» مطابقت دارد، اما این یک تطبیق اصطلاحی "
            "احتمالی است، نه شناسایی قطعی مصالح."
        ),
        # A term offered as one side of an "or": explained, not established.
        "knowledge_alternative_item": (
            "• «%s» با دستهٔ دانشی «%s» مطابقت دارد، اما تنها یک گزینه است و "
            "به‌عنوان مصالح قطعی ثبت نشده است."
        ),
        "knowledge_subtype_note": (
            "نوع دقیق و مشخصات فیزیکی این مصالح از این تصویر تعیین نمی‌شود."
        ),
        "style_note": (
            "سبک معماری از این شواهد قابل تعیین نیست (شواهد ناکافی)."
        ),
    },
    "en": {
        "floors_header": "Visible storeys (model observation, not independently verified):",
        "floors_with_ground": (
            "%s storeys are visible, including the ground floor and %s upper "
            "floors."
        ),
        "floors_total": "%s storeys are visible in total.",
        "floors_no_ground": "%s storeys are visible.",
        "parapet_note": "The parapet or roof band is not counted as a storey.",
        "partial_note": (
            "Part of the building is outside the frame, so this count is a "
            "minimum."
        ),
        "materials_header": "Materials named by the model (not independently verified):",
        # ---- VISION_MATERIAL_HEDGE_REPORT_FIDELITY_V1 ----
        "tentative_header": "Tentatively identified materials (unverified):",
        "tentative_item": "- %s (model wording: \"%s\")",
        # MATERIAL_HEDGE_PHRASE_FIDELITY_V1_1 — quote-only line when the
        # family is already named elsewhere; the phrase itself is never lost.
        "tentative_quote_item": "- Additional tentative observation: \"%s\"",
        "alternatives_header": (
            "Alternatives the model named without choosing "
            "(not independently verified):"
        ),
        "alternative_join": " OR ",
        "negative_header": "The model explicitly reports as absent or not visible:",
        "negative_note": (
            "These are evidence that the element is not present in THIS image, "
            "not proof that the building lacks it."
        ),
        "item": "- %s",
        # ---- ARCHITECTURAL_KNOWLEDGE_HANDOFF_V1 ----
        "knowledge_header": (
            "Architectural knowledge (term match, not independent image "
            "confirmation):"
        ),
        "knowledge_item": (
            "\"%s\" matches the knowledge category \"%s\"; general "
            "properties: %s."
        ),
        "knowledge_no_properties": (
            "\"%s\" matches the knowledge category \"%s\"."
        ),
        # MATERIAL_HEDGE_PHRASE_FIDELITY_V1_1
        "knowledge_tentative_item": (
            "\"%s\" matches the knowledge category \"%s\", but this is a "
            "tentative term match, not a definite identification of the "
            "material; general properties: %s."
        ),
        "knowledge_tentative_no_properties": (
            "\"%s\" matches the knowledge category \"%s\", but this is a "
            "tentative term match, not a definite identification of the "
            "material."
        ),
        "knowledge_alternative_item": (
            "\"%s\" matches the knowledge category \"%s\", but it is only one "
            "of the alternatives named and is not recorded as established."
        ),
        "knowledge_subtype_note": (
            "The precise subtype and physical specifications are not "
            "established by this image."
        ),
        "style_note": (
            "The architectural style cannot be determined from this evidence "
            "(insufficient evidence)."
        ),
    },
}


#: An unknown that says the storey count is undeterminable. It is honest while
#: no reading exists, but it directly contradicts a reported count, so it is
#: withheld from the RENDERED text once one does. The contract keeps it.
_FLOOR_UNKNOWN_WORDS = ("floor", "storey", "storeys", "طبقه")
_FLOOR_UNDETERMINED_WORDS = (
    "not determinable", "cannot be determined", "undetermined", "unknown",
    "قابل تعیین نیست",
)


def _is_floor_undetermined_unknown(value):
    low = str(value).lower()
    if not any(word in low for word in _FLOOR_UNKNOWN_WORDS):
        return False
    return any(word in low for word in _FLOOR_UNDETERMINED_WORDS)


def _reported_floor_count(interpretation):
    """The storey count the model reported, or None."""

    observation = interpretation.get("architectural_observation")

    if not isinstance(observation, dict):
        return None

    floors = observation.get("visible_floors_observation")

    if isinstance(floors, dict) and isinstance(floors.get("count"), int):
        return floors["count"]

    return None


def _without_floor_unknown(interpretation):
    """A render-only copy with the contradicted floor unknown withheld."""

    unknowns = interpretation.get("unknowns")

    if not isinstance(unknowns, list):
        return interpretation

    kept = [item for item in unknowns if not _is_floor_undetermined_unknown(item)]

    if len(kept) == len(unknowns):
        return interpretation

    renderable = dict(interpretation)
    renderable["unknowns"] = kept

    return renderable


# ==========================================================
# VISION_FIRST_FACADE_GROUNDING_V1 — "no evidence" beside the evidence
# ==========================================================
#
# MEASURED DEFECT: for a PHOTOGRAPH the interpreter's `observed` band is always
# empty, because it holds independently CORROBORATED evidence and a photograph
# has no local plan to corroborate against. The `if not observed:` branch in
# `architectural_vision_interpreter_v1` therefore fired on EVERY photographic
# turn and emitted "reliable architectural evidence has not been established".
#
# The rendered report then printed that sentence immediately above nine
# observed elements and a four-storey reading: the user was told both "here is
# what the model saw" and "no reliable architectural evidence exists".
#
# The statement is true of the CORROBORATED channel only, and the report
# already says so in its own words ("این خوانش … با شاهد مستقل تأیید نشده
# است"). It is therefore WITHHELD FROM THE RENDERED BODY ONLY — the same
# treatment, and for the same reason, as the contradicted floor unknown above.
# `interpretation["unknowns"]` keeps it, so the contract stays honest and a
# consumer reading the contract sees no change.
_UNESTABLISHED_EVIDENCE_UNKNOWNS = frozenset({
    "reliable architectural evidence has not been established",
    "completed local inspection did not establish grounded architectural evidence",
    "partial local evidence is available; semantic observations remain unknown",
})


def _without_unestablished_evidence(interpretation):
    """A render-only copy without the contradicted "no evidence" reasons."""

    unknowns = interpretation.get("unknowns")

    if not isinstance(unknowns, list):

        return interpretation

    kept = [
        item for item in unknowns
        if str(item).strip() not in _UNESTABLISHED_EVIDENCE_UNKNOWNS
    ]

    if len(kept) == len(unknowns):

        return interpretation

    renderable = dict(interpretation)
    renderable["unknowns"] = kept

    return renderable


def _architectural_observation_sections(interpretation, language="en"):
    """Speak the storey reading, materials and absence evidence.

    Returns [] when there is nothing to say, so a legacy interpretation renders
    byte-for-byte as before.
    """

    observation = interpretation.get("architectural_observation")

    if not isinstance(observation, dict):

        return []

    lang = _language(language)

    text = OBSERVATION_SECTION_PHRASES[lang]

    sections = []

    floors = observation.get("visible_floors_observation")

    if isinstance(floors, dict) and isinstance(floors.get("count"), int):

        count = floors["count"]

        upper = floors.get("upper_floors")

        if floors.get("count_scope") == "TOTAL" and floors.get(
                "ground_floor_included") and isinstance(upper, int):

            line = text["floors_with_ground"] % (count, upper)

        elif floors.get("count_scope") == "TOTAL":

            line = text["floors_total"] % count

        else:

            line = text["floors_no_ground"] % count

        body = [text["floors_header"], line]

        if floors.get("roof_band_excluded"):

            body.append(text["parapet_note"])

        if floors.get("whole_building_visible") is False:

            body.append(text["partial_note"])

        sections.append("\n".join(body))

    materials = observation.get("material_observations") or []

    # VISION_MATERIAL_HEDGE_REPORT_FIDELITY_V1 — `hedged` is recorded by the
    # observer (`_material_hedged`) and copied by the knowledge adapter, but it
    # was never rendered, so "Possibly marble" and "marble" produced identical
    # text. The flag is the ONLY uncertainty evidence used here: no second
    # detector, no new vocabulary. A hedged material leaves the named list.
    named = sorted({
        material
        for entry in materials
        if isinstance(entry, dict) and entry.get("hedged") is not True
        for material in (entry.get("materials") or [])
    })

    if named:

        sections.append(
            text["materials_header"] + "\n" + text["item"] % ", ".join(named)
        )

    # A material the model named only tentatively is reported as tentative, and
    # its own wording is quoted. One hedged observation does not make the rest
    # of the report uncertain: this is a separate section, not a verdict.
    #
    # MATERIAL_HEDGE_PHRASE_FIDELITY_V1_1 — each tentative phrase is an
    # INDEPENDENT claim. Deduplicating by material LABEL deleted whole
    # observations: the vocabulary groups marble under the `stone` family, so
    # "stone balustrade" (definite) silently erased "Possibly marble cladding"
    # (tentative), and "possibly stone trim" with it. A definite material in
    # one component is not evidence about another component. The phrase is
    # therefore never dropped; only a redundant IDENTITY repetition is avoided,
    # by quoting the phrase without repeating the label.
    tentative = []

    seen_phrases = set()

    for entry in materials:

        if not isinstance(entry, dict) or entry.get("hedged") is not True:

            continue

        phrase = entry.get("evidence_phrase") or entry.get("descriptor") or ""

        if not phrase:

            continue

        # The same evidence twice is one line; two different phrases stay two
        # lines even when they share a canonical material label.
        key = phrase.strip().lower()

        if key in seen_phrases:

            continue

        seen_phrases.add(key)

        labels = [material for material in (entry.get("materials") or [])
                  if material not in named]

        if labels:

            line = text["tentative_item"] % (", ".join(labels), phrase)

        else:

            line = text["tentative_quote_item"] % phrase

        tentative.append(line)

    if tentative:

        sections.append(
            text["tentative_header"] + "\n" + "\n".join(tentative)
        )

    # VISION_MATERIAL_SEMANTICS_V1 — the observer named these but chose none of
    # them. They are reported as alternatives, never folded into the list
    # above, so a decision the model did NOT make cannot read as a fact.
    alternatives = [
        group for entry in materials
        if isinstance(entry, dict)
        for group in (entry.get("material_alternatives") or [])
        if group
    ]

    if alternatives:

        # Two observer sentences can carry the same alternative set; the
        # reader needs the distinction once, not once per sentence.
        unique = []

        for group in alternatives:

            if group not in unique:

                unique.append(group)

        sections.append(
            text["alternatives_header"] + "\n" + "\n".join(
                text["item"] % text["alternative_join"].join(group)
                for group in unique
            )
        )

    negative = observation.get("negative_observations") or []

    # Name only the clause that actually states absence. `negated_texts` holds
    # verbatim contiguous slices of the observer's wording, so a mixed sentence
    # ("Exposed masonry …, no plaster or cladding") is reported as
    # "no plaster or cladding" instead of reprinting the whole sentence.
    # The full original wording stays available in `evidence_phrase`.
    lines = []

    for entry in negative:

        if not isinstance(entry, dict):
            continue

        fragments = [
            str(fragment)
            for fragment in (entry.get("negated_texts") or [])
            if fragment
        ]

        if fragments:

            for fragment in fragments:
                if fragment not in lines:
                    lines.append(fragment)

        elif entry.get("evidence_phrase"):

            lines.append(str(entry["evidence_phrase"]))

    if lines:

        sections.append("\n".join(
            [text["negative_header"]]
            + [text["item"] % line for line in lines]
            + [text["negative_note"]]
        ))

    # ==================================================
    # ARCHITECTURAL_KNOWLEDGE_HANDOFF_V1 — what the material TERM means
    #
    # The materials section above lists the term the observer used; this block
    # explains it through the installed architectural ontology. It is presented
    # as a term match, never as independent confirmation of the image, and it
    # states that the subtype and the physical specifications are not
    # established. Empty for a legacy interpretation, so nothing changes there.
    # ==================================================
    knowledge = interpretation.get("architectural_knowledge")

    if isinstance(knowledge, dict):

        entries = [
            entry for entry in (knowledge.get("materials") or [])
            if isinstance(entry, dict) and entry.get("ontology_id")
        ]

        # VISION_MATERIAL_SEMANTICS_V1 — a term the observer offered as ONE
        # SIDE of an "or" is explained but never presented as established.
        candidates = [
            entry for entry in (knowledge.get("material_candidates") or [])
            if isinstance(entry, dict) and entry.get("ontology_id")
        ]

        if entries or candidates:

            body = [text["knowledge_header"]]

            for entry in entries:

                identity = (entry.get("ontology_normalized")
                            or entry["ontology_id"])
                matched = entry.get("matched_term") or entry["ontology_id"]
                properties = entry.get("ontology_properties") or []

                # MATERIAL_HEDGE_PHRASE_FIDELITY_V1_1 — the observation behind
                # this lookup was hedged, so the lookup itself is tentative.
                # Display only: the contract keeps the entry in `materials`.
                hedged = entry.get("hedged") is True

                if properties:

                    body.append(
                        (text["knowledge_tentative_item"] if hedged
                         else text["knowledge_item"]) % (
                            matched, identity, ", ".join(properties)
                        )
                    )

                else:

                    body.append(
                        (text["knowledge_tentative_no_properties"] if hedged
                         else text["knowledge_no_properties"]) % (
                            matched, identity
                        )
                    )

            for entry in candidates:

                identity = (entry.get("ontology_normalized")
                            or entry["ontology_id"])
                matched = entry.get("matched_term") or entry["ontology_id"]

                body.append(text["knowledge_alternative_item"] % (
                    matched, identity
                ))

            body.append(text["knowledge_subtype_note"])

            if (knowledge.get("style") or {}).get("status") == (
                    "INSUFFICIENT_EVIDENCE"):

                body.append(text["style_note"])

            sections.append("\n".join(body))

    return sections


# ==========================================================
# ARCHITECTURAL_MATERIAL_USER_REPORT_V1
#
# Read-only projection of the interpreter's existing, non-executable
# `ArchitecturalMaterialKnowledgeConnectionV1` record. This code derives no
# request, knowledge, protection or spatial fact and calls no execution path.
# ==========================================================

MATERIAL_CONNECTION_PHRASES = {
    "fa": {
        "header": "درک درخواست جایگزینی مصالح (غیرقابل‌اجرا):",
        "observed_header": "مصالح موجودِ مشاهده‌شده (منبع: مشاهدهٔ بینایی؛ تأیید مستقل: نشده):",
        "observed_item": "• %s — هویت دانشی: %s؛ اطمینان مشاهده: %s؛ وضعیت: %s",
        "observed_missing": "مصالح موجودِ مشاهده‌شده: از شواهد بینایی موجود تعیین نشده است (UNVERIFIED).",
        "provenance": "منشأ مشاهده: %s",
        "provenance_missing": "منشأ مشاهده: در قرارداد ثبت نشده است.",
        "requested": "مصالح جایگزین درخواستی کاربر (منبع: دستور کاربر؛ مشاهدهٔ بصری نشده): %s",
        "instruction": "متن دستور کاربر: «%s»",
        "operation": "تفسیر تغییر: جایگزینی مصالح (MATERIAL_REPLACEMENT)، نه صرفاً تغییر رنگ.",
        "targets": "سطوح هدفِ اعلام‌شده توسط کاربر: %s",
        "targets_missing": "سطوح هدف: در دستور کاربر ثبت نشده است.",
        "protected": "اجزای محافظت‌شده فقط طبق دستور صریح کاربر: %s",
        "protected_missing": "اجزای محافظت‌شده: هیچ موردی از دستور صریح کاربر ثبت نشده است.",
        "spatial_unknown": "مبنای مکانی: نامشخص (UNKNOWN)؛ هیچ مختصات یا ماسکی ایجاد نشده است.",
        "spatial_status": "مبنای مکانی: %s.",
        "execution_unavailable": "قابلیت انتقال دقیق مصالح نما: هنوز در دسترس نیست (NOT_YET_AVAILABLE)؛ این گزارش رندر تولید نکرده است.",
        "execution_status": "وضعیت قابلیت انتقال دقیق مصالح نما: %s.",
        "not_learned": "یادگیری دائمی: انجام نشده است (learned=false).",
    },
    "en": {
        "header": "Material-replacement understanding (non-executable):",
        "observed_header": "Observed existing material (source: vision observation; not independently verified):",
        "observed_item": "- %s — knowledge identity: %s; observation confidence: %s; verification: %s",
        "observed_missing": "Observed existing material: not established by the available vision evidence (UNVERIFIED).",
        "provenance": "Observation provenance: %s",
        "provenance_missing": "Observation provenance: not recorded in the contract.",
        "requested": "User-requested replacement material (source: user instruction; not visually observed): %s",
        "instruction": "User instruction: \"%s\"",
        "operation": "Interpretation: material replacement (MATERIAL_REPLACEMENT), not simple recoloring.",
        "targets": "User-stated target surfaces: %s",
        "targets_missing": "Target surfaces: not recorded in the user instruction.",
        "protected": "Protected components, only as explicitly stated by the user: %s",
        "protected_missing": "Protected components: none recorded from an explicit user instruction.",
        "spatial_unknown": "Spatial grounding: UNKNOWN; no coordinates or mask were created.",
        "spatial_status": "Spatial grounding: %s.",
        "execution_unavailable": "Precise facade material-transfer capability: NOT_YET_AVAILABLE; this report did not produce a render.",
        "execution_status": "Precise facade material-transfer capability status: %s.",
        "not_learned": "Permanent learning: not performed (learned=false).",
    },
}


MATERIAL_CORRECTION_PHRASES = {
    "fa": {
        "header": "اصلاح مصالح در انتظار تأیید انسانی:",
        "previous": "مشاهدهٔ بصری قبلی (بدون بازنویسی): %s؛ اطمینان: %s؛ وضعیت: %s",
        "provenance": "منشأ مشاهدهٔ قبلی: %s",
        "correction": "اصلاح کاربر (USER_CORRECTION؛ نه شاهد بصری): «%s»",
        "corrected": "هویت اصلاح‌شدهٔ پیشنهادی (مشاهدهٔ بصری نشده): %s",
        "pending": "وضعیت نامزد دانشی: PENDING_CONFIRMATION",
        "spatial": "مبنای مکانی: UNKNOWN؛ هیچ مختصات یا ماسکی ایجاد نشده است.",
        "execution": "قابلیت انتقال دقیق مصالح نما: NOT_YET_AVAILABLE؛ هیچ رندری تولید نشده است.",
        "learning": "هیچ یادگیری دائمی انجام نشده است؛ دانش دائمی بدون تأیید صریح تغییر نمی‌کند.",
        "prompt": "درخواست تأیید: %s",
    },
    "en": {
        "header": "Material correction awaiting human confirmation:",
        "previous": "Previous visual observation (preserved): %s; confidence: %s; verification: %s",
        "provenance": "Previous observation provenance: %s",
        "correction": "User correction (USER_CORRECTION; not visual evidence): \"%s\"",
        "corrected": "Proposed corrected identity (not visually observed): %s",
        "pending": "Knowledge candidate status: PENDING_CONFIRMATION",
        "spatial": "Spatial grounding: UNKNOWN; no coordinates or mask were created.",
        "execution": "Precise facade material-transfer capability: NOT_YET_AVAILABLE; no render was produced.",
        "learning": "No permanent learning has occurred; permanent knowledge remains unchanged without explicit confirmation.",
        "prompt": "Confirmation request: %s",
    },
}


def _material_correction_sections(connection, language="en"):
    """Project the existing pending review without confirming or persisting it."""

    correction = connection.get("material_correction") or {}
    if correction.get("status") != "PENDING_CONFIRMATION":
        return []
    text = MATERIAL_CORRECTION_PHRASES[_language(language)]
    previous = correction.get("previous_observation") or {}
    corrected = correction.get("corrected_material") or {}

    def identity(entry):
        material_id = entry.get("ontology_id")
        name = entry.get("ontology_normalized") or material_id or "UNKNOWN"
        return ("%s [%s]" % (name, material_id)
                if material_id and name != material_id else str(name))

    lines = [
        text["header"],
        text["previous"] % (
            identity(previous),
            previous.get("observation_confidence") or "UNKNOWN",
            previous.get("verification") or "UNVERIFIED",
        ),
    ]
    provenance = (connection.get("observed_facts") or {}).get("provenance") or {}
    provenance_parts = [
        "%s=%s" % (key, provenance.get(key))
        for key in ("provider", "model", "image_id", "source_type")
        if provenance.get(key) not in (None, "")
    ]
    if provenance_parts:
        lines.append(text["provenance"] % ", ".join(provenance_parts))
    lines.extend([
        text["correction"] % ((correction.get("user_correction") or {}).get(
            "verbatim") or ""),
        text["corrected"] % identity(corrected),
        text["pending"],
        text["spatial"],
        text["execution"],
        text["learning"],
    ])
    if correction.get("confirmation_prompt"):
        lines.append(text["prompt"] % correction["confirmation_prompt"])
    return ["\n".join(lines)]


def _material_connection_sections(interpretation, language="en"):

    """Render the accepted material connection without deriving new facts."""

    connection = interpretation.get("architectural_material_knowledge_connection")
    if not isinstance(connection, dict):
        return []
    if connection.get("status") == "MATERIAL_CORRECTION_PENDING_CONFIRMATION":
        return _material_correction_sections(connection, language)
    if connection.get("status") != "CONNECTED":
        return []
    architectural = connection.get("architectural_interpretation")
    if not isinstance(architectural, dict):
        return []

    text = MATERIAL_CONNECTION_PHRASES[_language(language)]
    lines = [text["header"]]
    observed = connection.get("observed_facts") or {}
    material_lines = []
    for entry in (observed.get("existing_materials") or []):
        if not isinstance(entry, dict):
            continue
        descriptor = (entry.get("descriptor") or entry.get("source_quote")
                      or entry.get("ontology_normalized") or entry.get("ontology_id"))
        if not descriptor:
            continue
        ontology_id = entry.get("ontology_id")
        normalized = entry.get("ontology_normalized") or ontology_id or "UNKNOWN"
        identity = ("%s [%s]" % (normalized, ontology_id)
                    if ontology_id and normalized != ontology_id else str(normalized))
        confidence = (entry.get("observation_confidence")
                      or entry.get("confidence") or "UNKNOWN")
        verification = (entry.get("verification")
                        or entry.get("observation_verification")
                        or observed.get("verification") or "UNVERIFIED")
        material_lines.append(text["observed_item"] % (
            descriptor, identity, confidence, verification
        ))
    if material_lines:
        lines.append(text["observed_header"])
        lines.extend(material_lines)
    else:
        lines.append(text["observed_missing"])

    provenance = observed.get("provenance") or {}
    provenance_parts = [
        "%s=%s" % (key, provenance.get(key))
        for key in ("provider", "model", "image_id", "source_type")
        if provenance.get(key) not in (None, "")
    ]
    lines.append(text["provenance"] % ", ".join(provenance_parts)
                 if provenance_parts else text["provenance_missing"])

    requested = architectural.get("requested_material") or {}
    requested_id = requested.get("ontology_id")
    requested_name = requested.get("ontology_normalized") or requested_id or "UNKNOWN"
    requested_display = ("%s [%s]" % (requested_name, requested_id)
                         if requested_id and requested_name != requested_id
                         else str(requested_name))
    lines.append(text["requested"] % requested_display)

    instruction = connection.get("user_instruction") or {}
    if instruction.get("verbatim"):
        lines.append(text["instruction"] % instruction["verbatim"])
    if (architectural.get("operation") == "MATERIAL_REPLACEMENT"
            and architectural.get("recoloring_only") is False):
        lines.append(text["operation"])

    targets = [str(item) for item in (architectural.get("target_surfaces") or []) if item]
    lines.append(text["targets"] % ", ".join(targets)
                 if targets else text["targets_missing"])
    protected = [str(item) for item in (architectural.get("protected_elements") or []) if item]
    lines.append(text["protected"] % ", ".join(protected)
                 if protected else text["protected_missing"])

    spatial = architectural.get("spatial_grounding") or {}
    spatial_status = str(spatial.get("status") or "UNKNOWN")
    if (spatial_status == "UNKNOWN" and spatial.get("coordinates") is None
            and spatial.get("mask") is None and spatial.get("grounded") is False):
        lines.append(text["spatial_unknown"])
    else:
        lines.append(text["spatial_status"] % spatial_status)

    execution = connection.get("execution_capability") or {}
    execution_status = str(execution.get("status") or "UNKNOWN")
    if (execution_status == "NOT_YET_AVAILABLE"
            and execution.get("precise_facade_material_transfer") is False):
        lines.append(text["execution_unavailable"])
    else:
        lines.append(text["execution_status"] % execution_status)
    if connection.get("learned") is False:
        lines.append(text["not_learned"])
    return ["\n".join(lines)]


# Which structured provider categories are ARCHITECTURAL observations, and
# which are TEXT / NUMERIC content. Order is the reporting order.
_SUMMARY_ELEMENT_CATEGORIES = (
    "observed_elements", "walls", "structural_elements",
    "vertical_circulation", "openings.doors", "openings.windows",
    "openings.other_openings", "furniture", "fixtures",
    "spatial_relationships",
)

# Order = reporting priority. Exact readings and the scale come BEFORE the
# looser OCR candidates, so a long tail of guesses cannot push the lot table,
# the coordinate table or the scale out of a concise answer.
_SUMMARY_TEXT_CATEGORIES = (
    "scale", "ocr_exact", "level_codes", "orientation",
    "dimensions", "provider_ocr_candidate", "ocr_partial",
)

_SUMMARY_MAX_ITEMS = 18


def _summary_candidates(interpretation):
    """The provider candidates the default answer may report."""

    if not isinstance(interpretation, dict):
        return []
    grounding = interpretation.get("grounding")
    if isinstance(grounding, dict) and grounding.get("provider_candidates"):
        return grounding.get("provider_candidates") or []
    return interpretation.get("provider_candidates") or []


def _dedupe(values, limit=_SUMMARY_MAX_ITEMS):
    out = []
    for value in values:
        text = " ".join(str(value or "").split())
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _dedupe_contained(values, limit=_SUMMARY_MAX_ITEMS):
    """Drop a bullet that is wholly contained in a longer one.

    VISION_FIRST_FACADE_GROUNDING_V1 — the normalizer may place the SAME source
    sentence in two categories with different quote spans. The facade then
    printed the same observation twice, the second time truncated:

        • A large open through-passage (arcade) at ground level in the centre,
          framed by brick piers/columns
        • A large open through-passage (arcade) at ground level in the centre

    Only a STRICT substring is dropped, so nothing is lost: the surviving
    bullet contains every word of the dropped one. Applied to the element
    bullets only — the text group holds short OCR labels ("left" inside
    "left-centre") where containment is not redundancy.
    """

    items = _dedupe(values, max(limit, len(values)))

    lowered = [item.lower() for item in items]

    kept = [
        item for index, item in enumerate(items)
        if not any(lowered[index] != other and lowered[index] in other
                   for other in lowered)
    ]

    return kept[:limit]


def _provider_observation_summary(interpretation, language="en"):
    """A concise, CATEGORISED summary of the model's own observation.

    VISION_END_TO_END_RETENTION_FIX_V1 — reporting is not grounding. Every
    section states its own verification state: an unverified model observation
    is REPORTED (never hidden) and never presented as independently proven.
    Provider confidence alone still grounds nothing.

    Returns [] when the interpretation carries no provider observation at all,
    so a legacy interpretation renders exactly as before.
    """

    candidates = _summary_candidates(interpretation)

    if not candidates:

        return []

    lang = _language(language)

    text = PROVIDER_SUMMARY_PHRASES[lang]

    paragraphs = []

    drawing = None

    # R2_USER_FACING_EYE_HANDOFF_V1 — a phrase the observation contract has
    # classified as absence must not ALSO be printed as a positive model
    # observation. It is reported once, in its own section, as absence.
    _observation = interpretation.get("architectural_observation")

    from core.vision.architectural_observation_v1 import _states_absence

    absent_phrases = {
        str(entry.get("evidence_phrase"))
        for entry in (
            (_observation or {}).get("negative_observations") or []
            if isinstance(_observation, dict)
            else []
        )
        if isinstance(entry, dict) and entry.get("evidence_phrase")
    }

    # Grouped by category so the reporting order is stable and the most
    # consequential content (scale, dimensions, level codes, then OCR) is
    # never pushed out by a long tail of minor labels.
    element_groups = {category: [] for category in _SUMMARY_ELEMENT_CATEGORIES}

    text_groups = {category: [] for category in _SUMMARY_TEXT_CATEGORIES}

    ambiguous, unknowns, grounded = [], [], []

    for claim in candidates:

        if not isinstance(claim, dict):

            continue

        category = claim.get("category")

        value = claim.get("text")

        if value and str(value) in absent_phrases:

            # Reported as absence elsewhere; never as a present element.
            continue

        # R2_FINAL_UI_SMOKE_PREFLIGHT_V1 — a NEGATIVE-ONLY assertion such as
        # "no separate attic band" states that something is not there. It must
        # never sit under "model architectural observations". The detector is
        # the observation owner's own (`_states_absence`), not a second one.
        if value and _states_absence(str(value)):

            continue

        if category == "drawing_type":

            drawing = drawing or value

            continue

        if claim.get("state") == "CONFIRMED" and claim.get("grounded"):

            grounded.append(value)

            continue

        if category == "unknowns" or claim.get("certainty") == "UNKNOWN":

            unknowns.append(value)

            continue

        if claim.get("certainty") == "AMBIGUOUS" or claim.get("state") == "AMBIGUOUS":

            ambiguous.append(value)

            continue

        if category in element_groups:

            element_groups[category].append(value)

        elif category in text_groups:

            text_groups[category].append(value)

    elements = [value for category in _SUMMARY_ELEMENT_CATEGORIES
                for value in element_groups[category]]

    texts = [value for category in _SUMMARY_TEXT_CATEGORIES
             for value in text_groups[category]]

    if drawing:

        from core.vision.drawing_type_v1 import canonical_drawing_type

        canonical = canonical_drawing_type(drawing)

        # The canonical type is never asserted as a fact here: it is the
        # MODEL's identification, reported with its verification state.
        paragraphs.append(text["drawing_type"] % " — ".join(
            [part for part in (drawing, canonical) if part]
        ))

    for header, values in (
        ("grounded_header", _dedupe(grounded)),
        ("observations_header", _dedupe_contained(elements)),
        ("texts_header", _dedupe(texts)),
        ("ambiguous_header", _dedupe(ambiguous, 6)),
        ("unknowns_header", _dedupe(unknowns, 6)),
    ):

        if not values:

            continue

        paragraphs.append(text[header] + "\n" + "\n".join(
            text["item"] % value for value in values
        ))

    if paragraphs:

        paragraphs.append(text["note"])

    return paragraphs


def render_vision_report(interpretation, language="en"):

    """The USER-FACING architectural report, in `language`.

    ARCHITECTURAL_VISION_REPORT_UX_V1 — a PLAN (`plan_reading`) is
    answered with a short architectural explanation in Persian, because
    the grounded SOURCE LABELS are Persian and must be printed verbatim.

    VISION_END_TO_END_RETENTION_FIX_V1 — the default answer now ALSO reports
    the model's own structured observation, categorised and with its
    verification state, so a correct observer reading is not discarded. The
    section is additive and appears only when the interpretation actually
    carries provider observation, so a legacy interpretation and an English
    conversation keep their historical rendering byte-for-byte.
    """

    if not isinstance(interpretation, dict):

        return ""

    lang = _language(language)

    plan = interpretation.get("plan_reading")

    summary = _provider_observation_summary(interpretation, lang)

    # R2_USER_FACING_EYE_HANDOFF_V1 — storeys, materials and absence evidence.
    # Empty for a legacy interpretation, so nothing changes for those.
    sections = _architectural_observation_sections(interpretation, lang)

    # ARCHITECTURAL_MATERIAL_USER_REPORT_V1 — read-only projection of the
    # already-built connection. Empty for every ordinary/non-replacement turn.
    material_sections = _material_connection_sections(interpretation, lang)

    # A reported storey count contradicts "the count cannot be determined".
    # Withhold that one line from the RENDERED body; the contract keeps it.
    renderable = (
        _without_floor_unknown(interpretation)
        if _reported_floor_count(interpretation) is not None
        else interpretation
    )

    # "no reliable architectural evidence has been established" contradicts the
    # observation list this same report is about to print. Withheld only when
    # that list is actually rendered, so a turn with nothing observed still
    # admits it. The contract keeps the unknown either way.
    if summary:

        renderable = _without_unestablished_evidence(renderable)

    if lang == "fa":

        if isinstance(plan, dict):

            body = _architectural_report(interpretation, plan)

            # A plan keeps its historical rendering: the observation sections
            # describe a photograph, not a drawing.
            parts = [body] + summary + material_sections
            return "\n\n".join(parts) if len(parts) > 1 else body

        # ==================================================
        # FACADE-03D — a facade / render is NOT a plan.
        #
        # Answer it as a facade: a short identification, the closed-vocabulary
        # interpretation lines and the honest unknowns, followed by the model's
        # own observations (still marked unverified). No plan vocabulary —
        # plan spaces, circulation or swing-door symbols — is emitted.
        # ==================================================
        if interpretation.get("space_type") == "facade":

            body = _facade_report(renderable, lang)

            parts = [body] + summary + sections + material_sections

            return "\n\n".join(parts) if len(parts) > 1 else body

        if summary or sections or material_sections:

            return "\n\n".join(summary + sections + material_sections)

    body = _evidence_report(renderable, lang)

    parts = [body] + sections + material_sections
    return "\n\n".join(parts) if len(parts) > 1 else body


# ==========================================================
# EVIDENCE RENDERING — STRUCTURED-EVIDENCE SAFETY
#
# An evidence array legitimately mixes PLAIN STRINGS (provider phrases,
# verbatim label text) with STRUCTURED RECORDS (localized raster regions
# carrying region_id / bbox_pixels / confidence / corroboration, and any
# future structured evidence object).
#
# The DEBUG / EVIDENCE surface must render BOTH: a structured record is
# summarised into readable text — never handed to `str.join`, never
# flattened away, and never discarded. The structured contract itself is
# unchanged; only its display is normalised here. The user-facing concise
# report does not use these helpers.
# ==========================================================


def _evidence_text(value):
    """Readable text for ONE evidence entry (total, never raises)."""

    if isinstance(value, str):

        return value

    if isinstance(value, bool):

        return str(value)

    if isinstance(value, (int, float)):

        return str(value)

    if isinstance(value, dict):

        parts = []

        phrase = value.get("evidence_phrase") or value.get("phrase")

        if phrase:

            parts.append(str(phrase))

        identifier = value.get("region_id") or value.get("item_id")

        if identifier:

            parts.append(str(identifier))

        box = value.get("bbox_pixels")

        if isinstance(box, (list, tuple)) and len(box) == 4:

            parts.append("[" + ", ".join(str(edge) for edge in box) + "]")

        tier = value.get("confidence")

        if tier:

            parts.append("(" + str(tier) + ")")

        if parts:

            return " ".join(parts)

        # Unknown structured record: keep it auditable rather than dropping it.
        return "; ".join(
            "%s=%s" % (key, _evidence_text(item))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )

    if isinstance(value, (list, tuple)):

        return ", ".join(_evidence_text(item) for item in value)

    return str(value)


def _join_evidence(values, separator=", "):
    """Join an evidence array that may hold strings and structured records."""

    return separator.join(
        rendered
        for rendered in (_evidence_text(value) for value in (values or []))
        if rendered
    )


def _plan_section(interpretation, lang):

    """The PLAN READING sections, grouped by EVIDENCE TYPE.

    ARCHITECTURAL_VISION_LABEL_COMPLETENESS_V1 — the report keeps FOUR
    things apart that used to be merged:

      5  READ LABELS        the verbatim printed text + its occurrence
                            count; the meaning is a SEPARATE field
      6  SPACE FUNCTIONS    the interpretation, with its evidence source
      7  INFERRED FUNCTIONS functions from OBSERVED furniture only
      8  ELEMENTS/OPENINGS  walls, doors, windows
      9  RELATIONSHIPS      supported endpoints only
      10 ZONING             incl. the open / semi-open band
      11 UNVERIFIED CLAIMS  provider-only spaces, furniture, relations
      12 UNKNOWN            what could not be determined
    """

    plan = interpretation.get("plan_reading")

    if not isinstance(plan, dict):

        return ""

    text = PLAN_SECTION_HEADERS[lang]

    separator = "\u060c " if lang == "fa" else ", "

    def block(values):

        rendered = [value for value in (values or []) if value]

        if not rendered:

            return text["none"]

        return "\n".join("- " + value for value in rendered)

    # ---- 5. READ LABELS (verbatim + multiplicity) ----
    read_labels = plan.get("read_labels") or []

    counts = {}

    for entry in read_labels:

        label = entry.get("text")

        counts[label] = counts.get(label, 0) + 1

    labels = []

    for entry in read_labels:

        label = entry.get("text")

        line = '"' + str(label) + '"'

        if counts.get(label, 1) > 1:

            line += " (#%s)" % entry.get("occurrence")

        function = entry.get("semantic_function")

        if function:

            line += " \u2014 " + text["function"] + ": "

            line += display_space_type(function, lang)

            zone = entry.get("zone")

            if zone:

                line += " (" + ZONE_DISPLAY[lang].get(zone, zone) + ")"

        else:

            line += " \u2014 " + text["unmapped"]

        if entry.get("evidence_type") == "local_ocr":

            box = entry.get("bbox_pixels") or []
            source_bits = [
                text["source"] + ": " + SOURCE_DISPLAY[lang]["local_ocr"]
            ]

            if len(box) == 4:

                location_label = "مکان پیکسلی" if lang == "fa" else "pixel location"
                source_bits.append(
                    "%s: (%s, %s)-(%s, %s)" % (
                        location_label,
                        *(str(round(float(value), 1)) for value in box),
                    )
                )

            confidence_label = "اطمینان" if lang == "fa" else "confidence"
            source_bits.append(
                confidence_label + ": "
                + display_confidence(entry.get("confidence") or "LOW", lang)
            )
            line += " [" + "؛ ".join(source_bits) + "]"

            raw_ocr = entry.get("raw_ocr")

            if raw_ocr and entry.get("correction"):

                raw_label = "OCR خام" if lang == "fa" else "raw OCR"
                line += " — " + raw_label + ': "' + str(raw_ocr) + '"'

        labels.append(line)

    if labels:

        labels.append(text["labels_note"])

    # ---- 6. SPACE FUNCTIONS ----
    spaces = []

    for entry in (plan.get("named_spaces") or []):

        line = display_space_type(entry.get("space"), lang)

        zone = entry.get("zone")

        if zone:

            line += " (" + ZONE_DISPLAY[lang].get(zone, zone) + ")"

        evidence = _join_evidence(entry.get("evidence"))

        if evidence:

            line += " \u2014 " + text["evidence"] + ": " + evidence

        line += " [" + text["source"] + ": " + SOURCE_DISPLAY[lang]["label"] + "]"

        spaces.append(line)

    for entry in (plan.get("geometry_spaces") or []):

        line = display_space_type(entry.get("space"), lang)

        zone = entry.get("zone")

        if zone:

            line += " (" + ZONE_DISPLAY[lang].get(zone, zone) + ")"

        line += " [" + text["source"] + ": " + SOURCE_DISPLAY[lang]["geometry"] + "]"

        claims = entry.get("provider_label_claim") or []

        if claims:

            line += " \u2014 " + text["supporting_label"] + ": " + ", ".join(claims)

        spaces.append(line)

    building = plan.get("building_type") or {}

    building_line = ""

    if building.get("value"):

        building_line = (
            "\n" + text["building"] + " "
            + BUILDING_TYPE_DISPLAY[lang].get(
                building["value"], building["value"]
            )
            + " (" + TIER_DISPLAY[lang].get(
                building.get("status"), building.get("status") or ""
            ) + ")"
        )

        evidence = separator.join(
            display_space_type(name, lang)
            for name in (building.get("evidence") or [])
        )

        if evidence:

            building_line += " \u2014 " + text["evidence"] + ": " + evidence

    # ---- 7. INFERRED FUNCTIONS ----
    functions = []

    for entry in plan.get("inferred_functions") or []:

        space = entry.get("space")

        if not space:

            continue

        line = display_space_type(space, lang)

        evidence = _join_evidence(entry.get("evidence"))

        if evidence:

            line += " \u2014 " + text["evidence"] + ": " + evidence

        line += " [" + text["source"] + ": " + SOURCE_DISPLAY[lang]["furniture"] + "]"

        functions.append(line)

    if not functions:

        functions.append(REASON_DISPLAY[lang]["furniture_not_observed"])

    # ---- 8. ELEMENTS + OPENINGS ----
    elements = []

    for entry in plan.get("openings") or []:

        kind = entry.get("kind")

        if not kind:

            continue

        line = OPENING_DISPLAY[lang].get(kind, kind)

        line += " (" + TIER_DISPLAY[lang].get(
            entry.get("status"), entry.get("status") or ""
        ) + ")"

        evidence = _join_evidence(entry.get("evidence"))

        if evidence:

            line += " \u2014 " + text["evidence"] + ": " + evidence

        instances = entry.get("instances") or []

        if instances:

            count_label = "تعداد" if lang == "fa" else "count"
            location_label = "مکان پیکسلی" if lang == "fa" else "pixel locations"
            line += " \u2014 " + count_label + ": " + str(len(instances))
            boxes = [
                item.get("bbox_pixels") for item in instances
                if isinstance(item, dict) and len(item.get("bbox_pixels") or []) == 4
            ]

            if boxes:

                line += " \u2014 " + location_label + ": " + "; ".join(
                    "(%s, %s)-(%s, %s)" % tuple(
                        str(round(float(value), 1)) for value in box
                    )
                    for box in boxes
                )

        if kind == "window" and entry.get("status") != "visible":

            line += " \u2014 " + REASON_DISPLAY[lang]["window_not_grounded"]

        elements.append(line)

    walls = plan.get("wall_reading") or {}

    for kind in ("enclosure", "partition"):

        entry = walls.get(kind) or {}

        status = entry.get("status")

        if not status or status == "unknown":

            continue

        line = WALL_DISPLAY[lang].get(kind, kind)

        line += " (" + TIER_DISPLAY[lang].get(status, status) + ")"

        if kind == "partition" and entry.get("room_count"):

            count = entry["room_count"]

            line += " \u2014 " + text["evidence"] + ": " + (
                "%d \u0641\u0636\u0627\u06cc \u0646\u0627\u0645\u200c\u0628\u0631\u062f\u0647\u200c\u0634\u062f\u0647 \u06a9\u0647 \u0628\u0627 \u062e\u0637\u0648\u0637 \u062f\u06cc\u0648\u0627\u0631\u0650 \u062f\u06cc\u062f\u0647\u200c\u0634\u062f\u0647 \u0627\u0632 \u0647\u0645 \u062c\u062f\u0627 \u0634\u062f\u0647\u200c\u0627\u0646\u062f" % count
                if lang == "fa"
                else "%d named rooms separated by the visible wall lines" % count
            )

        else:

            evidence = _join_evidence(entry.get("evidence"))

            if evidence:

                line += " \u2014 " + text["evidence"] + ": " + evidence

        elements.append(line)

    # ---- 9. RELATIONSHIPS (supported endpoints only) ----
    relations = []

    for entry in plan.get("relations") or []:

        between = entry.get("between") or []

        if entry.get("kind") == "adjacency" and len(between) == 2:

            relations.append(
                display_space_type(between[0], lang) + " \u2194 "
                + display_space_type(between[1], lang)
                + " [" + text["source"] + ": "
                + SOURCE_DISPLAY[lang]["relation"]
                + " \u2014 "
                + _join_evidence(entry.get("evidence")) + "]"
            )

        elif entry.get("kind") == "circulation":

            relations.append(
                "circulation: "
                + separator.join(
                    display_space_type(name, lang) for name in between
                )
                + " [" + text["source"] + ": "
                + SOURCE_DISPLAY[lang]["relation"] + "]"
            )

    # ---- 10. ZONING ----
    zones = plan.get("zones") or {}

    zone_lines = []

    for zone in ZONE_ORDER:

        names = zones.get(zone) or []

        if not names:

            continue

        zone_lines.append(
            ZONE_DISPLAY[lang].get(zone, zone) + ": "
            + separator.join(
                display_space_type(name, lang) for name in names
            )
        )

    # ---- 11. UNVERIFIED PROVIDER CLAIMS ----
    unverified = []

    for claim in plan.get("unsupported_claims") or []:

        line = display_space_type(claim.get("space"), lang)

        line += " (" + TIER_DISPLAY[lang].get(
            claim.get("status"), claim.get("status") or ""
        ) + ")"

        evidence = _join_evidence(claim.get("evidence"))

        if evidence:

            line += " \u2014 " + text["evidence"] + ": " + evidence

        reason = REASON_DISPLAY[lang].get(claim.get("reason_code"))

        if reason:

            line += " \u2014 " + reason

        unverified.append(line)

    for relation in plan.get("unsupported_relations") or []:

        between = relation.get("between") or []

        unverified.append(
            separator.join(
                display_space_type(name, lang) for name in between
            )
            + " (" + TIER_DISPLAY[lang]["unverified"] + ")"
            + " \u2014 " + REASON_DISPLAY[lang]["unsupported_relation"]
            + " \u2014 " + text["evidence"] + ": "
            + _join_evidence(relation.get("evidence"))
        )

    # LOCAL_PLAN_READING_V1 — the provider's own label claims are kept
    # AUDITABLE in the contract (`plan_reading.provider_label_claims`,
    # and verbatim in `raw_observations`) but are deliberately NOT printed:
    # once grounded local evidence owns the transcription, a hallucinated
    # provider label must not reappear in the user-facing answer at all.

    for item in plan.get("furniture") or []:

        if item.get("usable_for_space_inference"):

            continue

        unverified.append(
            FURNITURE_DISPLAY[lang].get(
                str(item.get("name", "")).lower(), item.get("name")
            )
            + " (" + TIER_DISPLAY[lang].get(
                item.get("status"), item.get("status") or ""
            ) + ")"
            + " \u2014 " + text["evidence"] + ": "
            + str(item.get("name"))
            + " \u2014 "
            + REASON_DISPLAY[lang]["furniture_symbol_on_drawing"]
        )

    # ---- 12. UNKNOWN ----
    tiers = interpretation.get("evidence_tiers") or {}

    unknown_lines = []

    for phrase in tiers.get("unknown") or []:

        unknown_lines.append(
            display_phrase(phrase, lang) + " \u2014 " + (
                "\u0627\u0646\u062a\u0638\u0627\u0631 \u0645\u06cc\u200c\u0631\u0641\u062a \u062f\u06cc\u062f\u0647 \u0634\u0648\u062f \u0648\u0644\u06cc \u062a\u0623\u06cc\u06cc\u062f \u0646\u0634\u062f"
                if lang == "fa" else "expected, never confirmed"
            )
        )

    return (
        "\n\n" + text["labels"] + "\n" + block(labels)
        + "\n\n" + text["spaces"] + building_line + "\n" + block(spaces)
        + "\n\n" + text["furniture"] + "\n" + block(functions)
        + "\n\n" + text["elements"] + "\n" + block(elements)
        + "\n\n" + text["relations"] + "\n" + block(relations)
        + "\n\n" + text["zones"] + "\n" + block(zone_lines)
        + "\n\n" + text["unverified"] + "\n" + block(unverified)
        + "\n\n" + text["unknowns"] + "\n" + block(unknown_lines)
    )


def _grounding_section(interpretation, lang):

    """The grounded evidence section, or "" when there is no grounding."""

    grounding = interpretation.get("grounding")

    if not isinstance(grounding, dict):

        return ""

    try:

        from core.vision.architectural_vision_grounding_v1 import (
            render_grounding,
        )

        rendered = render_grounding(grounding, lang)

    except Exception:

        return ""

    if not rendered:

        return ""

    return "\n\n" + rendered


vision_report = {

    "contract": CONTRACT,
    "version": VERSION,

    "render": render_vision_report,
    "display_phrase": display_phrase,
    "display_space_type": display_space_type,
    "display_confidence": display_confidence,
}


print(
    "VISION REPORT v1.0 ONLINE "
    "(the image analysis answers in the conversation's language)"
)
