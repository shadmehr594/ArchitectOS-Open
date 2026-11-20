# ==========================================================
# ArchitectOS Teaching Meaning v1
#
# PHASE 08C — DETERMINISTIC MEANING NORMALIZATION
#
# Turns a raw user statement into a NORMALIZED RESTATEMENT so the
# assistant can say what it understood.
#
# Hard rules
#   - Deterministic. No LLM. No network. No provider.
#   - This is a RESTATEMENT, not truth.  Nothing here is validated
#     architecture; it is what the user APPEARS to have said.
#   - Works for Persian and English.
#   - Lexicons hold FEATURES (entities, relations, modality), never
#     whole sentences.
# ==========================================================


from __future__ import annotations


from core.conversation.turn_semantics_v1 import (
    match_form,
    script_of,
    extract_features,
    DEFINITIONAL_TOKENS,
    NORMATIVE_TOKENS,
    NEGATION_TOKENS,
    CORRECTNESS_TOKENS,
    ERROR_TOKENS,
    # curriculum foundation fix — shared vocabularies, ONE source of truth
    PERSIAN_COPULA_TOKENS,
    MIN_COPULA_DEFINITION_TOKENS,
    PATTERN_MARKERS,
    DECISION_MARKERS,
    ZONE_WORDS,
    ZONE_ASSIGNMENT_PHRASES,
    zone_word_in,
    is_zone_assignment,
    # TEACHING_CONTEXT_01 — a conditional design allowance
    is_conditional_allowance,
    contains_any,
)

# The zone vocabulary lives in Phase 11's zone model. Importing it keeps
# ONE source of truth: a zone assignment resolves to the SAME six zone
# names the rest of the system reasons with.
from core.curriculum.zone_model_v1 import (
    ZONE_PUBLIC,
    ZONE_SEMI_PUBLIC,
    ZONE_PRIVATE,
    ZONE_SERVICE,
    ZONE_CIRCULATION,
    ZONE_EXTERNAL,
    zone_display,
)


CONTRACT = "TeachingMeaningV1"
VERSION = "1.0"


# ----------------------------------------------------------
# DOMAIN / ENTITY / RELATION LEXICONS
# ----------------------------------------------------------

# canonical entity -> surface variants (Persian + English)
ENTITY_LEXICON = {

    "kitchen": (
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647",  # آشپزخانه
        "\u0645\u0637\u0628\u062e",        # مطبخ
        "kitchen",
    ),
    "dining": (
        "\u063a\u0630\u0627\u062e\u0648\u0631\u06cc",  # غذاخوری
        "\u0646\u0627\u0647\u0627\u0631\u062e\u0648\u0631\u06cc",  # ناهارخوری
        "dining",
        "diningroom",
    ),
    "living": (
        "\u0646\u0634\u06cc\u0645\u0646",  # نشیمن
        "\u067e\u0630\u06cc\u0631\u0627\u06cc\u06cc",  # پذیرایی
        "living",
        "livingroom",
        "lounge",
    ),
    "bedroom": (
        "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628",  # اتاق خواب
        "\u062e\u0648\u0627\u0628",        # خواب
        "bedroom",
    ),
    "bathroom": (
        "\u062d\u0645\u0627\u0645",        # حمام
        "\u0633\u0631\u0648\u06cc\u0633",  # سرویس
        "\u062a\u0648\u0627\u0644\u062a",  # توالت
        "\u062f\u0633\u062a\u0634\u0648\u06cc\u06cc",  # دستشویی
        "bathroom",
        "restroom",
        "wc",
    ),
    "entrance": (
        "\u0648\u0631\u0648\u062f\u06cc",  # ورودی
        "entrance",
        "entry",
        "foyer",
    ),
    "corridor": (
        "\u0631\u0627\u0647\u0631\u0648",  # راهرو
        "\u06a9\u0631\u06cc\u062f\u0648\u0631",  # کریدور
        "\u062f\u0627\u0644\u0627\u0646",  # دالان
        "corridor",
        "hallway",
        "hall",
    ),
    "balcony": (
        "\u0628\u0627\u0644\u06a9\u0646",  # بالکن
        "\u062a\u0631\u0627\u0633",        # تراس
        "\u0627\u06cc\u0648\u0627\u0646",  # ایوان
        "balcony",
        "terrace",
    ),
    "stair": (
        "\u067e\u0644\u0647",              # پله
        "\u0631\u0627\u0647\u067e\u0644\u0647",  # راهپله
        "stair",
        "stairs",
        "staircase",
    ),
    "window": (
        "\u067e\u0646\u062c\u0631\u0647",  # پنجره
        "window",
    ),
    "door": (
        # bare "در" is deliberately NOT used: it is also the very common
        # Persian preposition "in", so it would be a false positive.
        "\u062f\u0631\u0628",              # درب
        "\u062f\u0631 \u0648\u0631\u0648\u062f\u06cc",  # در ورودی
        "door",
    ),
    "wall": (
        "\u062f\u06cc\u0648\u0627\u0631",  # دیوار
        "wall",
    ),
    "facade": (
        "\u0646\u0645\u0627",              # نما
        "facade",
        "elevation",
    ),
    "roof": (
        "\u0633\u0642\u0641",              # سقف
        "\u0628\u0627\u0645",              # بام
        "roof",
    ),
    "garden": (
        "\u062d\u06cc\u0627\u0637",        # حیاط
        "\u0628\u0627\u063a",              # باغ
        "garden",
        "yard",
        "courtyard",
    ),
    "parking": (
        "\u067e\u0627\u0631\u06a9\u06cc\u0646\u06af",  # پارکینگ
        "parking",
        "garage",
    ),
    "storage": (
        "\u0627\u0646\u0628\u0627\u0631\u06cc",  # انباری
        "storage",
        "closet",
    ),
    "office": (
        "\u062f\u0641\u062a\u0631",        # دفتر
        "\u0627\u062f\u0627\u0631\u06cc",  # اداری
        "office",
        "study",
    ),
    "pool": (
        "\u0627\u0633\u062a\u062e\u0631",  # استخر
        "pool",
    ),
    "lobby": (
        "\u0644\u0627\u0628\u06cc",        # لابی
        "\u0633\u0631\u0633\u0631\u0627",  # سرسرا
        "lobby",
    ),
    "mezzanine": (
        "\u0646\u06cc\u0645\u200c\u0637\u0628\u0642\u0647",  # نیم‌طبقه
        "\u0646\u06cc\u0645 \u0637\u0628\u0642\u0647",  # نیم طبقه (match form)
        "mezzanine",
    ),
    # ==================================================
    # CLAUSE_ANALYSIS_01 — the OBJECTS a teacher actually names when
    # teaching a bedroom. Without "bed" the rule
    # "تخت دور از پنجره باشه بهتره" had NO subject of its own, so the
    # restatement picked the only entity it could see and produced
    # "پنجره باید دور از اتاق خواب و نشیمن باشد" — the subject inversion
    # the user reported.
    # ==================================================
    "bed": (
        "\u062a\u062e\u062a",              # تخت
        "bed",
    ),
    "wardrobe": (
        "\u06a9\u0645\u062f",              # کمد
        "\u06a9\u0644\u0648\u0632\u062a",  # کلوزت
        "\u0627\u062a\u0627\u0642 \u0644\u0628\u0627\u0633",  # اتاق لباس
        "\u0631\u062e\u062a\u06a9\u0646",  # رختکن
        "wardrobe",
        "dressing room",
    ),
}


RELATION_LEXICON = {

    "near": (
        "\u0646\u0632\u062f\u06cc\u06a9",  # نزدیک
        "\u0645\u062c\u0627\u0648\u0631",  # مجاور
        "\u06a9\u0646\u0627\u0631",        # کنار
        "\u0686\u0633\u0628\u06cc\u062f\u0647",  # چسبیده
        "\u0647\u0645\u062c\u0648\u0627\u0631",  # همجوار
        "near",
        "close",
        "adjacent",
        "next",
        "beside",
    ),
    "far": (
        "\u062f\u0648\u0631",              # دور
        "\u0641\u0627\u0635\u0644\u0647",  # فاصله
        "\u062c\u062f\u0627",              # جدا
        "far",
        "away",
        "separate",
        "apart",
        "distant",
    ),
    "facing": (
        "\u0645\u0634\u0631\u0641",        # مشرف
        "\u0631\u0648 \u0628\u0647",        # رو به
        "\u0631\u0648\u0628\u0647\u200c\u0631\u0648",  # روبه‌رو
        "facing",
        "overlooking",
        "oriented",
    ),
    "vertical": (
        "\u0628\u0627\u0644\u0627\u06cc",  # بالای
        "\u0632\u06cc\u0631",              # زیر
        "above",
        "below",
        "under",
        "upstairs",
        "downstairs",
    ),
    "connected": (
        "\u0645\u062a\u0635\u0644",        # متصل
        "\u0648\u0635\u0644",              # وصل
        "\u0627\u0631\u062a\u0628\u0627\u0637",  # ارتباط
        "connected",
        "connect",
        "linked",
        "access",
    ),
    "size": (
        "\u0628\u0632\u0631\u06af\u062a\u0631",  # بزرگتر
        "\u06a9\u0648\u0686\u06a9\u062a\u0631",  # کوچکتر
        "\u0648\u0633\u06cc\u0639",        # وسیع
        "bigger",
        "larger",
        "smaller",
        "wider",
    ),
    "sequence": (
        "\u0642\u0628\u0644",              # قبل
        "\u0628\u0639\u062f",              # بعد
        "before",
        "after",
        "then",
        "first",
    ),
}


DOMAIN_LEXICON = {

    "material": (
        "\u0633\u0646\u06af",              # سنگ
        "\u0686\u0648\u0628",              # چوب
        "\u0622\u062c\u0631",              # آجر
        "\u0634\u06cc\u0634\u0647",        # شیشه
        "\u0628\u062a\u0646",              # بتن
        "\u0641\u0644\u0632",              # فلز
        "stone",
        "wood",
        "brick",
        "glass",
        "concrete",
        "metal",
        "marble",
        "material",
    ),
    "lighting": (
        "\u0646\u0648\u0631",              # نور
        "\u0631\u0648\u0634\u0646\u0627\u06cc\u06cc",  # روشنایی
        "\u0646\u0648\u0631\u06af\u06cc\u0631\u06cc",  # نورگیری
        "light",
        "lighting",
        "daylight",
        "sunlight",
        "brightness",
    ),
    "proportion": (
        "\u0627\u0628\u0639\u0627\u062f",  # ابعاد
        "\u0627\u0646\u062f\u0627\u0632\u0647",  # اندازه
        "\u0646\u0633\u0628\u062a",        # نسبت
        "\u0645\u0642\u06cc\u0627\u0633",  # مقیاس
        "\u0627\u0631\u062a\u0641\u0627\u0639",  # ارتفاع
        "\u0639\u0631\u0636",              # عرض
        "dimension",
        "size",
        "proportion",
        "ratio",
        "scale",
        "height",
        "width",
    ),
    "geometry": (
        "\u0632\u0627\u0648\u06cc\u0647",  # زاویه
        "\u062f\u0631\u062c\u0647",        # درجه
        "\u062e\u0637",                    # خط
        "\u0641\u0631\u0645",              # فرم
        "\u0634\u06a9\u0644",              # شکل
        "angle",
        "degree",
        "line",
        "shape",
        "form",
        "geometry",
    ),
    "circulation": (
        "\u0645\u0633\u06cc\u0631",        # مسیر
        "\u062f\u0633\u062a\u0631\u0633\u06cc",  # دسترسی
        "circulation",
        "access",
        "path",
        "route",
    ),
    "style": (
        "\u0645\u062f\u0631\u0646",        # مدرن
        "\u06a9\u0644\u0627\u0633\u06cc\u06a9",  # کلاسیک
        "\u0633\u0646\u062a\u06cc",        # سنتی
        "\u0633\u0628\u06a9",              # سبک
        "modern",
        "classic",
        "traditional",
        "style",
    ),
    # ---- PHASE 09 additions (brief-defined domain vocabulary) ----
    "space": (
        "\u0641\u0636\u0627",              # فضا
        "\u0641\u0636\u0627\u06cc",        # فضای
        "\u0627\u062a\u0627\u0642",        # اتاق
        "\u0639\u0631\u0635\u0647",        # عرصه
        "space",
        "room",
        "area",
    ),
    "adjacency": (
        "\u0645\u062c\u0627\u0648\u0631\u062a",        # مجاورت
        "\u0647\u0645\u062c\u0648\u0627\u0631\u06cc",  # همجواری
        "\u0647\u0645\u0633\u0627\u06cc\u06af\u06cc",  # همسایگی
        "adjacency",
        "adjacent",
        "proximity",
    ),
    "structure": (
        "\u0633\u0627\u0632\u0647",        # سازه
        "\u0627\u0633\u06a9\u0644\u062a",  # اسکلت
        "\u0633\u062a\u0648\u0646",        # ستون
        "\u062a\u06cc\u0631",              # تیر
        "\u0628\u0627\u0631\u0628\u0631",  # باربر
        "structure",
        "structural",
        "column",
        "beam",
        "loadbearing",
    ),
    "facade": (
        "\u0646\u0645\u0627",              # نما
        "\u067e\u0648\u0633\u062a\u0647",  # پوسته
        "\u0628\u062f\u0646\u0647",        # بدنه
        "facade",
        "elevation",
        "cladding",
        "envelope",
    ),
    "residential": (
        "\u0645\u0633\u06a9\u0648\u0646\u06cc",        # مسکونی
        "\u062e\u0627\u0646\u0647",                    # خانه
        "\u0648\u06cc\u0644\u0627",                    # ویلا
        "\u0622\u067e\u0627\u0631\u062a\u0645\u0627\u0646",  # آپارتمان
        "\u0645\u0633\u06a9\u0646",                    # مسکن
        "residential",
        "housing",
        "villa",
        "apartment",
        "dwelling",
    ),
    "commercial": (
        "\u062a\u062c\u0627\u0631\u06cc",              # تجاری
        "\u0641\u0631\u0648\u0634\u06af\u0627\u0647",  # فروشگاه
        "\u0645\u063a\u0627\u0632\u0647",              # مغازه
        "\u067e\u0627\u0633\u0627\u0698",              # پاساژ
        "commercial",
        "retail",
        "shop",
        "store",
        "mall",
    ),
}


# ----------------------------------------------------------
# PHASE 09 — KNOWLEDGE CLASS / SCOPE / PROVENANCE MARKERS
#
# These are FEATURE phrases (markers), never whole sentences.
# ----------------------------------------------------------

# The statement is about THIS project / plan / example.
PROJECT_MARKERS = (
    "\u0627\u06cc\u0646 \u067e\u0631\u0648\u0698\u0647",        # این پروژه
    "\u062f\u0631 \u0627\u06cc\u0646 \u067e\u0631\u0648\u0698\u0647",  # در این پروژه
    "\u0627\u06cc\u0646 \u067e\u0644\u0627\u0646",              # این پلان
    "\u0627\u06cc\u0646 \u0646\u0642\u0634\u0647",              # این نقشه
    "\u0627\u06cc\u0646 \u0645\u062b\u0627\u0644",              # این مثال
    "\u062f\u0631 \u0627\u06cc\u0646 \u0645\u062b\u0627\u0644",  # در این مثال
    "\u0627\u06cc\u0646 \u0645\u0648\u0631\u062f",              # این مورد
    "\u0627\u06cc\u0646 \u0637\u0631\u062d",                    # این طرح
    "\u0627\u06cc\u0646 \u0633\u0627\u062e\u062a\u0645\u0627\u0646",  # این ساختمان
    "\u067e\u0631\u0648\u0698\u0647 \u0645\u0646",              # پروژه من
    "\u062f\u0631 \u0627\u06cc\u0646\u062c\u0627",              # در اینجا
    "this project",
    "the project",
    "this plan",
    "this example",
    "this case",
    "this design",
    "this building",
    "our project",
    "in this ",
    "here,",
)

# The user states a personal preference.
PREFERENCE_MARKERS = (
    "\u062a\u0631\u062c\u06cc\u062d \u0645\u06cc",  # ترجیح می...
    "\u062f\u0648\u0633\u062a \u062f\u0627\u0631\u0645",  # دوست دارم
    "\u0645\u06cc \u067e\u0633\u0646\u062f\u0645",        # می پسندم
    "\u0639\u0644\u0627\u0642\u0647 \u062f\u0627\u0631\u0645",  # علاقه دارم
    "\u0645\u0646 \u062a\u0631\u062c\u06cc\u062d",        # من ترجیح
    "i prefer",
    "i'd prefer",
    "i would prefer",
    "i like",
    "my preference",
    "i want",
)

# Typical / heuristic wording -> a PATTERN, not an absolute rule.
#
# MOVED to `turn_semantics_v1` by the curriculum foundation fix and
# imported at the top of this module, so the turn classifier and this
# ladder share ONE vocabulary. The list GREW: "الگو" / "رویه" / "عرف" /
# "سنت" / "رایج" / "pattern" / "convention" were missing, so a statement
# that literally named a pattern was not recognised as one.

# Zone phrase -> the Phase 11 zone constant. Longest-first in ZONE_WORDS
# means the SPECIFIC zone always wins, so "منطقه نیمه عمومی" is not read
# as "منطقه عمومی".
ZONE_PHRASE_TO_ZONE = {
    "\u0645\u0646\u0637\u0642\u0647 \u0646\u06cc\u0645\u0647 \u0639\u0645\u0648\u0645\u06cc": ZONE_SEMI_PUBLIC,
    "\u0645\u0646\u0637\u0642\u0647 \u0639\u0645\u0648\u0645\u06cc": ZONE_PUBLIC,
    "\u0645\u0646\u0637\u0642\u0647 \u062e\u0635\u0648\u0635\u06cc": ZONE_PRIVATE,
    "\u0645\u0646\u0637\u0642\u0647 \u062e\u062f\u0645\u0627\u062a\u06cc": ZONE_SERVICE,
    "\u0645\u0646\u0637\u0642\u0647 \u06af\u0631\u062f\u0634": ZONE_CIRCULATION,
    "\u0645\u0646\u0637\u0642\u0647 \u0628\u06cc\u0631\u0648\u0646\u06cc": ZONE_EXTERNAL,
    "\u0646\u06cc\u0645\u0647 \u0639\u0645\u0648\u0645\u06cc": ZONE_SEMI_PUBLIC,
    "semi public zone": ZONE_SEMI_PUBLIC,
    "semi-public zone": ZONE_SEMI_PUBLIC,
    "public zone": ZONE_PUBLIC,
    "private zone": ZONE_PRIVATE,
    "service zone": ZONE_SERVICE,
    "circulation zone": ZONE_CIRCULATION,
    "external zone": ZONE_EXTERNAL,
}


def resolve_zone_phrase(form):

    """The zone a statement names, or None."""

    marker = zone_word_in(form)

    if not marker:

        return None

    return ZONE_PHRASE_TO_ZONE.get(marker)


# Regulation / standard / numeric-limit wording -> ARCHITECTURAL_FACT.
FACT_MARKERS = (
    "\u0636\u0648\u0627\u0628\u0637",              # ضوابط
    "\u0645\u0642\u0631\u0631\u0627\u062a",        # مقررات
    "\u0627\u0633\u062a\u0627\u0646\u062f\u0627\u0631\u062f",  # استاندارد
    "\u0645\u0628\u062d\u062b",                    # مبحث
    "\u062d\u062f\u0627\u0642\u0644",              # حداقل
    "\u062d\u062f\u0627\u06a9\u062b\u0631",        # حداکثر
    "\u0637\u0628\u0642",                          # طبق
    "\u0628\u0631 \u0627\u0633\u0627\u0633",        # بر اساس
    "\u0622\u06cc\u06cc\u0646 \u0646\u0627\u0645\u0647",  # آیین نامه
    "regulation",
    "code",
    "standard",
    "minimum",
    "maximum",
    "according to",
    "per the",
    "building code",
)

# The knowledge came from an external reference, not from the teacher.
EXTERNAL_REFERENCE_MARKERS = (
    "\u0637\u0628\u0642 \u0645\u0628\u062d\u062b",              # طبق مبحث
    "\u0628\u0631 \u0627\u0633\u0627\u0633 \u0645\u0642\u0631\u0631\u0627\u062a",  # بر اساس مقررات
    "\u0645\u0642\u0631\u0631\u0627\u062a \u0645\u0644\u06cc",  # مقررات ملی
    "\u062f\u0631 \u0627\u0633\u062a\u0627\u0646\u062f\u0627\u0631\u062f",  # در استاندارد
    "according to the code",
    "per the code",
    "the code says",
    "the standard says",
    "building code",
)


# ----------------------------------------------------------
# PHASE 09 — KNOWLEDGE CLASS / SCOPE / PROVENANCE VOCABULARY
# ----------------------------------------------------------

KNOWLEDGE_ARCHITECTURAL_FACT = "ARCHITECTURAL_FACT"
KNOWLEDGE_DESIGN_RULE = "DESIGN_RULE"
KNOWLEDGE_PATTERN = "PATTERN"
KNOWLEDGE_PREFERENCE = "PREFERENCE"
KNOWLEDGE_PROJECT_DECISION = "PROJECT_DECISION"
KNOWLEDGE_OBSERVATION = "OBSERVATION"
KNOWLEDGE_UNKNOWN = "UNKNOWN"


# ADDED by the curriculum foundation fix. A DEFINITION is its own
# category: "راه پله ارتباط بین طبقات است" defines what a stair IS,
# which is neither a rule, nor a pattern, nor a fact about a standard.
# Before this it collapsed into ARCHITECTURAL_FACT.
KNOWLEDGE_DEFINITION = "DEFINITION"


ALL_KNOWLEDGE_CLASSES = (
    KNOWLEDGE_ARCHITECTURAL_FACT,
    KNOWLEDGE_DESIGN_RULE,
    KNOWLEDGE_PATTERN,
    KNOWLEDGE_DEFINITION,
    KNOWLEDGE_PREFERENCE,
    KNOWLEDGE_PROJECT_DECISION,
    KNOWLEDGE_OBSERVATION,
    KNOWLEDGE_UNKNOWN,
)


SCOPE_GENERAL = "GENERAL"
SCOPE_CURRENT_PROJECT = "CURRENT_PROJECT"

ALL_SCOPES = (SCOPE_GENERAL, SCOPE_CURRENT_PROJECT)


PROVENANCE_HUMAN_TEACHER = "HUMAN_TEACHER"
PROVENANCE_SYSTEM = "SYSTEM"
PROVENANCE_EXTERNAL_REFERENCE = "EXTERNAL_REFERENCE"

ALL_PROVENANCES = (
    PROVENANCE_HUMAN_TEACHER,
    PROVENANCE_SYSTEM,
    PROVENANCE_EXTERNAL_REFERENCE,
)


# Knowledge classes that describe the world in general (eligible for
# GENERAL scope). Everything else defaults to CURRENT_PROJECT — the safe
# direction, because generalizing by accident is the dangerous one.
#
# DEFINITION is generalizable: what a stair IS does not change per
# project. A project marker still forces CURRENT_PROJECT, because the
# project check runs FIRST in the ladder.
_GENERALIZABLE_CLASSES = (
    KNOWLEDGE_ARCHITECTURAL_FACT,
    KNOWLEDGE_DESIGN_RULE,
    KNOWLEDGE_PATTERN,
    KNOWLEDGE_DEFINITION,
    KNOWLEDGE_PREFERENCE,
)


def _any_in(form, markers):

    return any(marker in form for marker in markers)


# ----------------------------------------------------------
# DISPLAY VOCABULARIES (for human-readable teach-back only)
# ----------------------------------------------------------

ENTITY_DISPLAY = {
    "kitchen": {"fa": "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647", "en": "kitchen"},
    "dining": {"fa": "\u063a\u0630\u0627\u062e\u0648\u0631\u06cc", "en": "dining room"},
    "living": {"fa": "\u0646\u0634\u06cc\u0645\u0646", "en": "living room"},
    "bedroom": {"fa": "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628", "en": "bedroom"},
    "bathroom": {"fa": "\u0633\u0631\u0648\u06cc\u0633 \u0628\u0647\u062f\u0627\u0634\u062a\u06cc", "en": "bathroom"},
    "entrance": {"fa": "\u0648\u0631\u0648\u062f\u06cc", "en": "entrance"},
    "corridor": {"fa": "\u0631\u0627\u0647\u0631\u0648", "en": "corridor"},
    "balcony": {"fa": "\u0628\u0627\u0644\u06a9\u0646", "en": "balcony"},
    "stair": {"fa": "\u0631\u0627\u0647\u067e\u0644\u0647", "en": "stair"},
    "window": {"fa": "\u067e\u0646\u062c\u0631\u0647", "en": "window"},
    "door": {"fa": "\u062f\u0631", "en": "door"},
    "wall": {"fa": "\u062f\u06cc\u0648\u0627\u0631", "en": "wall"},
    "facade": {"fa": "\u0646\u0645\u0627", "en": "facade"},
    "roof": {"fa": "\u0633\u0642\u0641", "en": "roof"},
    "garden": {"fa": "\u062d\u06cc\u0627\u0637", "en": "garden"},
    "parking": {"fa": "\u067e\u0627\u0631\u06a9\u06cc\u0646\u06af", "en": "parking"},
    "storage": {"fa": "\u0627\u0646\u0628\u0627\u0631\u06cc", "en": "storage"},
    "office": {"fa": "\u062f\u0641\u062a\u0631", "en": "office"},
    "pool": {"fa": "\u0627\u0633\u062a\u062e\u0631", "en": "pool"},
    "lobby": {"fa": "\u0644\u0627\u0628\u06cc", "en": "lobby"},
    "mezzanine": {"fa": "\u0646\u06cc\u0645\u200c\u0637\u0628\u0642\u0647", "en": "mezzanine"},
}


RELATION_DISPLAY = {
    "near": {
        "fa": "\u0646\u0632\u062f\u06cc\u06a9 / \u0645\u062c\u0627\u0648\u0631",
        "en": "near / adjacent to",
    },
    "far": {"fa": "\u062f\u0648\u0631 \u0627\u0632", "en": "away from"},
    "facing": {"fa": "\u0645\u0634\u0631\u0641 \u0628\u0647", "en": "facing"},
    "vertical": {"fa": "\u062f\u0631 \u0637\u0628\u0642\u0647\u0654 \u0628\u0627\u0644\u0627/\u067e\u0627\u06cc\u06cc\u0646", "en": "above/below"},
    "connected": {"fa": "\u0645\u062a\u0635\u0644 \u0628\u0647", "en": "connected to"},
    "size": {"fa": "\u0627\u0632 \u0646\u0638\u0631 \u0627\u0646\u062f\u0627\u0632\u0647 \u0646\u0633\u0628\u062a \u0628\u0647", "en": "in size relative to"},
    "sequence": {"fa": "\u062f\u0631 \u062a\u0631\u062a\u06cc\u0628 \u0646\u0633\u0628\u062a \u0628\u0647", "en": "in sequence relative to"},
}


DOMAIN_DISPLAY = {
    "spatial_relationship": {"fa": "\u0631\u0627\u0628\u0637\u0647\u0654 \u0641\u0636\u0627\u06cc\u06cc", "en": "spatial relationship"},
    "material": {"fa": "\u0645\u0635\u0627\u0644\u062d", "en": "material"},
    "lighting": {"fa": "\u0646\u0648\u0631 \u0648 \u0631\u0648\u0634\u0646\u0627\u06cc\u06cc", "en": "lighting"},
    "proportion": {"fa": "\u062a\u0646\u0627\u0633\u0628\u0627\u062a", "en": "proportion"},
    "geometry": {"fa": "\u0647\u0646\u062f\u0633\u0647", "en": "geometry"},
    "circulation": {"fa": "\u062f\u0633\u062a\u0631\u0633\u06cc \u0648 \u06af\u0631\u062f\u0634", "en": "circulation"},
    "style": {"fa": "\u0633\u0628\u06a9", "en": "style"},
    "program": {"fa": "\u0628\u0631\u0646\u0627\u0645\u0647\u0654 \u0641\u0636\u0627\u0647\u0627", "en": "space program"},
    # PHASE 09 domains
    "space": {"fa": "\u0641\u0636\u0627", "en": "space"},
    "adjacency": {"fa": "\u0645\u062c\u0627\u0648\u0631\u062a", "en": "adjacency"},
    "structure": {"fa": "\u0633\u0627\u0632\u0647", "en": "structure"},
    "facade": {"fa": "\u0646\u0645\u0627", "en": "facade"},
    "residential": {"fa": "\u0645\u0633\u06a9\u0648\u0646\u06cc", "en": "residential"},
    "commercial": {"fa": "\u062a\u062c\u0627\u0631\u06cc", "en": "commercial"},
    "unknown": {"fa": "\u0646\u0627\u0645\u0634\u062e\u0635", "en": "unspecified"},
}


# PHASE 09 — learning taxonomy displays
KNOWLEDGE_CLASS_DISPLAY = {
    "ARCHITECTURAL_FACT": {"fa": "\u062f\u0627\u062f\u0647\u0654 \u0645\u0639\u0645\u0627\u0631\u06cc", "en": "architectural fact"},
    "DESIGN_RULE": {"fa": "\u0642\u0627\u0639\u062f\u0647\u0654 \u0637\u0631\u0627\u062d\u06cc", "en": "design rule"},
    "PATTERN": {"fa": "\u0627\u0644\u06af\u0648", "en": "pattern"},
    "DEFINITION": {"fa": "\u062a\u0639\u0631\u06cc\u0641", "en": "definition"},
    "PREFERENCE": {"fa": "\u062a\u0631\u062c\u06cc\u062d \u06a9\u0627\u0631\u0628\u0631", "en": "preference"},
    "PROJECT_DECISION": {"fa": "\u062a\u0635\u0645\u06cc\u0645 \u067e\u0631\u0648\u0698\u0647", "en": "project decision"},
    "OBSERVATION": {"fa": "\u0645\u0634\u0627\u0647\u062f\u0647", "en": "observation"},
    "UNKNOWN": {"fa": "\u0646\u0627\u0645\u0634\u062e\u0635", "en": "unknown"},
}


SCOPE_DISPLAY = {
    "GENERAL": {"fa": "\u0639\u0645\u0648\u0645\u06cc", "en": "general"},
    "CURRENT_PROJECT": {"fa": "\u0645\u062e\u0635\u0648\u0635 \u0627\u06cc\u0646 \u067e\u0631\u0648\u0698\u0647", "en": "this project only"},
}


PROVENANCE_DISPLAY = {
    "HUMAN_TEACHER": {"fa": "\u0622\u0645\u0648\u0632\u0634 \u06a9\u0627\u0631\u0628\u0631", "en": "human teacher"},
    "SYSTEM": {"fa": "\u0633\u06cc\u0633\u062a\u0645", "en": "system"},
    "EXTERNAL_REFERENCE": {"fa": "\u0645\u0646\u0628\u0639 \u062e\u0627\u0631\u062c\u06cc", "en": "external reference"},
}


KIND_DISPLAY = {
    "preference": {"fa": "\u062a\u0631\u062c\u06cc\u062d", "en": "preference"},
    "rule": {"fa": "\u0642\u0627\u0639\u062f\u0647", "en": "rule"},
    "constraint": {"fa": "\u0645\u062d\u062f\u0648\u062f\u06cc\u062a", "en": "constraint"},
    "definition": {"fa": "\u062a\u0639\u0631\u06cc\u0641", "en": "definition"},
    "correction": {"fa": "\u0627\u0635\u0644\u0627\u062d", "en": "correction"},
    "observation": {"fa": "\u0645\u0634\u0627\u0647\u062f\u0647", "en": "observation"},
}


STATUS_DISPLAY = {
    "observed": {"fa": "\u0641\u0642\u0637 \u062f\u0631\u06cc\u0627\u0641\u062a\u200c\u0634\u062f\u0647", "en": "observed only"},
    "needs_confirmation": {"fa": "\u0646\u06cc\u0627\u0632\u0645\u0646\u062f \u062a\u0623\u06cc\u06cc\u062f", "en": "needs confirmation"},
    "rejected": {"fa": "\u0631\u062f \u0634\u062f\u0647", "en": "rejected"},
}


def display(mapping, key, language="en"):

    entry = mapping.get(key) or {}

    return entry.get(language) or entry.get("en") or str(key)


def entity_display(entity, language="en"):

    """Display label for an entity key.

    TEACHING_CONTEXT_01 — a corpus space id (MASTER_BEDROOM_SLEEPING) is
    not an ENTITY_LEXICON key, so it resolves through the corpus name
    instead of leaking the raw id into the reply. Unknown keys are still
    returned unchanged, exactly as before.
    """

    label = display(ENTITY_DISPLAY, entity, language)

    if label and label != str(entity):

        return label

    if is_space_id(entity):

        try:

            from core.curriculum.space_types_v1 import space_types

            record = space_types.space(entity) or {}

            name = record.get("name") or {}

            resolved = name.get(
                "fa" if str(language or "").startswith("fa") else "en"
            )

            if resolved:

                return resolved

        except Exception:

            pass

    return label


def relation_display(relation, language="en"):

    return display(RELATION_DISPLAY, relation, language)


def domain_display(domain, language="en"):

    return display(DOMAIN_DISPLAY, domain, language)


def kind_display(kind, language="en"):

    return display(KIND_DISPLAY, kind, language)


def status_display(status, language="en"):

    return display(STATUS_DISPLAY, status, language)


def knowledge_class_display(value, language="en"):

    return display(KNOWLEDGE_CLASS_DISPLAY, value, language)


def scope_display(value, language="en"):

    return display(SCOPE_DISPLAY, value, language)


def provenance_display(value, language="en"):

    return display(PROVENANCE_DISPLAY, value, language)


def restate(meaning, language="en"):

    """Human-readable restatement of an extracted meaning.

    This is what the assistant SAYS it understood.  It is a restatement
    of the user's words, never a claim of architectural truth.
    """

    if not isinstance(meaning, dict):

        return ""

    kind = meaning.get("candidate_kind")

    subject = meaning.get("subject")

    objects = meaning.get("objects") or []

    relation = meaning.get("primary_relation")

    polarity = meaning.get("polarity")

    if language == "fa":

        if kind == "correction":

            return (
                "\u0634\u0645\u0627 \u06af\u0641\u062a\u06cc\u062f \u06a9\u0647 "
                "\u0628\u062e\u0634\u06cc \u0627\u0632 \u067e\u0627\u0633\u062e "
                "\u06cc\u0627 \u0645\u062b\u0627\u0644 \u0642\u0628\u0644\u06cc "
                "\u0646\u0627\u062f\u0631\u0633\u062a \u0627\u0633\u062a."
            )

        if kind == "definition":

            return (
                "\u0634\u0645\u0627 \u06cc\u06a9 \u062a\u0639\u0631\u06cc\u0641 "
                "\u0627\u0631\u0627\u0626\u0647 \u062f\u0627\u062f\u06cc\u062f."
            )

        if subject and relation and objects:

            target = " \u0648 ".join(
                entity_display(o, "fa") for o in objects
            )

            verb = (
                "\u0646\u0628\u0627\u06cc\u062f "
                if polarity == "avoid"
                else (
                    "\u0628\u0627\u06cc\u062f "
                    if polarity == "require"
                    else "\u0628\u0647\u062a\u0631 \u0627\u0633\u062a "
                )
            )

            return "%s %s%s %s \u0628\u0627\u0634\u062f." % (
                entity_display(subject, "fa"),
                verb,
                relation_display(relation, "fa"),
                target,
            )

        if subject:

            return (
                "\u0634\u0645\u0627 \u062f\u0631\u0628\u0627\u0631\u0647\u0654 "
                "%s \u0627\u0637\u0644\u0627\u0639\u0627\u062a\u06cc "
                "\u062f\u0627\u062f\u06cc\u062f." % entity_display(subject, "fa")
            )

        return (
            "\u0634\u0645\u0627 \u06cc\u06a9 \u0646\u06a9\u062a\u0647\u0654 "
            "\u0645\u0639\u0645\u0627\u0631\u06cc \u0628\u06cc\u0627\u0646 "
            "\u06a9\u0631\u062f\u06cc\u062f."
        )

    # English
    if kind == "correction":

        return "You said that part of the previous answer or example is wrong."

    if kind == "definition":

        return "You gave a definition."

    if subject and relation and objects:

        target = " and ".join(entity_display(o, "en") for o in objects)

        verb = (
            "must not be "
            if polarity == "avoid"
            else ("must be " if polarity == "require" else "should be ")
        )

        return "The %s %s%s the %s." % (
            entity_display(subject, "en"),
            verb,
            relation_display(relation, "en"),
            target,
        )

    if subject:

        return "You gave information about the %s." % entity_display(subject, "en")

    return "You stated an architectural point."


# ----------------------------------------------------------
# HELPERS
# ----------------------------------------------------------

def _token_positions(form, tokens):

    """Map each token to the character offset of its FIRST occurrence."""

    positions = {}

    cursor = 0

    for token in tokens:

        index = form.find(token, cursor)

        if index < 0:

            index = cursor

        positions.setdefault(token, index)

        cursor = index + len(token)

    return positions


def _find(canonical_map, form, tokens, token_set, order_by_position=False):

    """Return canonical keys whose surface variants appear in the text.

    TEACHING_CONTEXT_01 — `order_by_position` orders the hits by where
    they actually occur in the user's text. The default keeps the
    historical lexicon order, so the relation and domain lookups are
    byte-for-byte unchanged.

    The SET of hits is identical either way: this changes ordering only,
    never which keys are found and never their canonical normalisation.
    """

    positions = _token_positions(form, tokens)

    hits = []

    for order, (canonical, variants) in enumerate(canonical_map.items()):

        for variant in variants:

            if " " in variant:

                index = form.find(variant)

                if index < 0:

                    continue

            elif variant in token_set:

                index = positions.get(variant, -1)

            else:

                continue

            hits.append((index, order, canonical))

            break

    if order_by_position:

        # Ties fall back to the lexicon order, so the result is stable.
        hits.sort(key=lambda item: (item[0], item[1]))

    return [canonical for _position, _order, canonical in hits]


def _language(script, features):

    if script == "persian":

        return "fa"

    if script == "english":

        return "en"

    if script == "mixed":

        return "mixed"

    return (features or {}).get("language", "unknown")


# ==========================================================
# TEACHING_CONTEXT_01 — ARCHITECTURAL SUBJECT RESOLUTION
#
# The subject of a teaching statement used to be `entities[0]`, and
# `entities` was ordered by the LEXICON, so any sentence mentioning both
# "نشیمن" and "اتاق خواب" reported `subject=living`. Two narrow,
# architectural-domain-specific corrections:
#
#   1. an EXPLICIT COMPOSITE space in this sentence wins
#      ("اتاق خواب مستر" -> MASTER_BEDROOM_SLEEPING)
#   2. otherwise the ACTIVE architectural topic of this teaching
#      conversation is inherited, but only when the sentence does not
#      name a DIFFERENT space
#
# Both reuse the existing corpus resolver — no new vocabulary, no new
# space ids, no curriculum change.
# ==========================================================


def is_space_id(value):

    """True for a corpus space id (MASTER_BEDROOM_SLEEPING), never for a
    generic word ("architecture")."""

    text = str(value or "")

    return bool(text) and "_" in text and text == text.upper() and (
        text.replace("_", "").isalnum()
    )


def _space_ids():

    try:

        from core.curriculum.space_types_v1 import space_types

        return tuple(space_types.spaces().keys())

    except Exception:

        return ()


def _same_space_family(first, second):

    """True when two corpus space ids share a meaningful token.

    MASTER_BEDROOM_SLEEPING and BEDROOM_DOUBLE share "BEDROOM";
    MASTER_BEDROOM_SLEEPING and LIVING_RECEPTION share nothing.
    """

    if not first or not second:

        return False

    left = set(str(first).upper().split("_"))

    right = set(str(second).upper().split("_"))

    return bool(left & right)


def _longest_flat_variant(entities):

    longest = 0

    for entity in entities or []:

        for variant in ENTITY_LEXICON.get(entity, ()):

            longest = max(longest, len(match_form(variant).split(" ")))

    return longest


def _explicit_composite_space(form, entities):

    """The corpus space for an EXPLICIT composite mention, or None.

    Only a mention that is STRICTLY LONGER than the longest flat entity
    variant present may replace the flat entity:

      "اتاق خواب مستر"  (3 tokens)  beats flat "اتاق خواب" (2) -> wins
      "اتاق خواب"       (2 tokens)  equals flat "اتاق خواب" (2) -> flat

    The corpus scanner already does longest-match, non-overlapping,
    position-ordered scanning, so it is reused rather than reimplemented.
    """

    try:

        from core.curriculum.space_query_v1 import scan_spaces

        mentions = scan_spaces(form)

    except Exception:

        return None

    if not mentions:

        return None

    longest = _longest_flat_variant(entities)

    best = None

    for space_id, alias in mentions:

        width = len(match_form(alias).split(" "))

        if width > longest and (best is None or width > best[0]):

            best = (width, space_id)

    if best is None:

        return None

    return best[1]


# --- CORRECTION_LOOP_01 — EXCLUSIVE CONTRAST --------------------------
#
# "not X, ONLY Y": a denial that corrects a classification, e.g.
# "برای میهمانان نیست فقط برای زوجین هست".
#
# A bare denial ("من امروز حالم خوب نیست") is NOT a correction of the
# topic, and the inherited topic alone must never drag such a sentence
# into the space domain — so the contrast word is required as well.
CONTRAST_TOKENS = frozenset(
    (
        "\u0641\u0642\u0637",    # فقط   (only)
        "\u0628\u0644\u06a9\u0647",  # بلکه  (but rather)
        "\u062a\u0646\u0647\u0627",  # تنها  (only)
        "only", "instead", "rather",
    )
)


def _is_exclusive_contrast(token_set, negation):

    """True when the sentence denies one option and asserts another."""

    return bool(negation and (token_set & CONTRAST_TOKENS))


def _active_topic(context):

    """The inherited architectural topic, when the caller supplies one."""

    if not isinstance(context, dict):

        return None

    value = context.get("active_topic")

    return value if is_space_id(value) else None


def _leading_space(form):

    """The first corpus space mentioned in this sentence, or None."""

    try:

        from core.curriculum.space_query_v1 import scan_spaces

        mentions = scan_spaces(form)

    except Exception:

        return None

    return mentions[0][0] if mentions else None


def resolve_teaching_subject(entities, form, context=None):

    """Resolve the architectural subject of a teaching statement.

    Precedence:
      1. an EXPLICIT composite space in this sentence
      2. the inherited ACTIVE topic, when the sentence names no space or
         names one in the same family (so an explicit DIFFERENT space is
         never overridden)
      3. the earliest-mentioned flat entity (historical behaviour)
    """

    composite = _explicit_composite_space(form, entities)

    if composite:

        return composite, "explicit_composite"

    active = _active_topic(context)

    if active:

        leading = _leading_space(form)

        if leading is None or _same_space_family(leading, active):

            return active, "inherited_active_topic"

    if entities:

        return entities[0], "earliest_entity"

    return None, "none"


# ----------------------------------------------------------
# MEANING EXTRACTION
# ----------------------------------------------------------

def extract_meaning(text, turn_kind=None, context=None):

    """Deterministic normalized restatement of a user statement.

    `context` is OPTIONAL and additive. When it carries an
    `active_topic` (a corpus space id) the subject may inherit it —
    see `resolve_teaching_subject`. A caller that passes nothing gets
    the previous behaviour, except for the entity ORDERING fix.
    """

    raw = str(text or "")

    form = match_form(raw)

    tokens = [t for t in form.split(" ") if t]

    token_set = set(tokens)

    script = script_of(raw)

    features = extract_features(raw)

    # TEACHING_CONTEXT_01 — entities are ordered by their position in the
    # user's text. The SET is unchanged; only the order is.
    entities = _find(
        ENTITY_LEXICON, form, tokens, token_set, order_by_position=True
    )

    # ======================================================
    # CORRECTION_LOOP_01 — SUBJECT RESOLUTION MOVED ABOVE THE DOMAIN LADDER
    #
    # The subject used to be resolved at the END of this function, after
    # the domain ladder had already run. That order made a follow-up
    # correction in an ongoing space conversation ("برای میهمانان نیست
    # فقط برای زوجین هست" — a master-bedroom statement that names no
    # space of its own) keep `domain = "unknown"`, and
    # `teaching_candidate_v1.build_candidate` stores an unknown-domain
    # statement as `rejected`. The user's correction was therefore thrown
    # away, and the same question was answered from the generic LLM again
    # and again.
    #
    # A statement that RESOLVES to a known space IS a statement about
    # that space — either because it names one explicitly or because the
    # project's own teaching history supplies the active topic. Resolving
    # the subject first lets the domain ladder see that.
    # ======================================================
    subject, subject_source = resolve_teaching_subject(
        entities, form, context=context
    )

    # The corpus space the statement is attached to, when one was
    # resolved (explicit composite or inherited). `None` for a plain
    # flat-entity statement, so the historical shape is preserved.
    space_topic = (
        subject if subject_source in ("explicit_composite",
                                      "inherited_active_topic")
        else None
    )

    relations = _find(RELATION_LEXICON, form, tokens, token_set)

    domains = _find(DOMAIN_LEXICON, form, tokens, token_set)

    normative = bool(token_set & NORMATIVE_TOKENS)

    definitional = bool(token_set & DEFINITIONAL_TOKENS)

    negation = bool(token_set & NEGATION_TOKENS)

    correctness = bool(token_set & CORRECTNESS_TOKENS)

    error = bool(token_set & ERROR_TOKENS)

    # ---- domain ----
    #
    # PHASE 09 — the brief-defined domain vocabulary (space, adjacency,
    # structure, facade, residential, commercial) is now producible, and
    # a relation between recognised spaces yields `adjacency`.
    # `spatial_relationship` is retained for the two-entity + relation
    # case so Phase 08 behaviour is unchanged.
    if len(entities) >= 2 and relations:

        domain = "spatial_relationship"

    elif relations and entities:

        domain = "adjacency"

    elif domains:

        domain = domains[0]

    elif entities:

        domain = "space"

    # CORRECTION_LOOP_01 — a statement that resolves to a KNOWN space is
    # about that space even when it carries no entity of its own. Without
    # this rung the domain stayed `unknown`, `build_candidate` stored the
    # turn as `rejected`, and a correction could never be learned.
    #
    # DELIBERATELY NARROW: the inherited topic alone is NOT enough, or
    # any irrelevant sentence in a space conversation ("من امروز حالم
    # خوب نیست") would be recorded as knowledge about that space. The
    # sentence must ALSO carry an EXCLUSIVE CONTRAST ("not X, only Y") —
    # which is exactly what a correction of the topic looks like:
    #   "برای میهمانان نیست فقط برای زوجین هست"
    elif space_topic and _is_exclusive_contrast(token_set, negation):

        domain = "space"

    else:

        domain = "unknown"

    # ---- PHASE 09 — knowledge class / scope / provenance ----
    project_scoped = _any_in(form, PROJECT_MARKERS)

    preference_marker = _any_in(form, PREFERENCE_MARKERS)

    pattern_marker = _any_in(form, PATTERN_MARKERS)

    fact_marker = _any_in(form, FACT_MARKERS)

    external_reference = _any_in(form, EXTERNAL_REFERENCE_MARKERS)

    # Curriculum foundation fix — Persian COPULAR definitions.
    #
    # "اتاق خواب فضای خصوصی است" and "راه پله ارتباط بین طبقات است"
    # carry no explicit definition word, so `definitional` was False and
    # they collapsed into OBSERVATION. The rule below is the SAME one the
    # turn classifier already applies, shared so the two layers cannot
    # disagree about what a definition is.
    copula_definition = bool(
        tokens
        and len(tokens) >= MIN_COPULA_DEFINITION_TOKENS
        and tokens[-1] in PERSIAN_COPULA_TOKENS
    )

    is_definitional = definitional or copula_definition

    # CURRICULUM_FOUNDATION_FIX_02 — a ZONE ASSIGNMENT.
    #
    # "ورودی و نشیمن در منطقه عمومی قرار می گیرند" is a descriptive
    # statement of fact about the architectural model, so it becomes an
    # ARCHITECTURAL_FACT. It is tested BEFORE `is_definitional` because
    # such a sentence often ends in a copula ("... در منطقه عمومی است")
    # and would otherwise be filed as a definition of a term.
    zone_assignment_zone = (
        resolve_zone_phrase(form) if is_zone_assignment(form) else None
    )

    # TEACHING_CONTEXT_01 — a conditional design allowance
    # ("اگر ... اجازه بدهد ... می تواند داشته باشد"). Architecturally a
    # design rule, but it carries no normative marker, so without this
    # rung it reached the ladder as UNKNOWN.
    conditional_allowance = is_conditional_allowance(form)

    # ORDER MATTERS, and it was wrong before.
    #
    #  * PATTERN no longer requires a normative marker. A customary
    #    statement is a pattern in its own right, so it is tested BEFORE
    #    definitional and before normative — "معمولاً ... است" and
    #    "معمولاً ... باید ..." are both PATTERNs.
    #  * A ZONE ASSIGNMENT is an ARCHITECTURAL_FACT about the model.
    #  * DEFINITION is its own class instead of being folded into
    #    ARCHITECTURAL_FACT.
    #  * A project marker still wins over everything, so a project
    #    decision can never be generalised.
    if project_scoped:

        knowledge_class = KNOWLEDGE_PROJECT_DECISION

    elif preference_marker:

        knowledge_class = KNOWLEDGE_PREFERENCE

    elif pattern_marker:

        knowledge_class = KNOWLEDGE_PATTERN

    elif zone_assignment_zone:

        knowledge_class = KNOWLEDGE_ARCHITECTURAL_FACT

    elif is_definitional:

        knowledge_class = KNOWLEDGE_DEFINITION

    elif fact_marker and normative:

        knowledge_class = KNOWLEDGE_ARCHITECTURAL_FACT

    elif normative:

        knowledge_class = KNOWLEDGE_DESIGN_RULE

    # TEACHING_CONTEXT_01 — a conditional design allowance is a
    # DESIGN_RULE too, tested AFTER the normative rung so an explicitly
    # normative statement keeps its existing class.
    elif conditional_allowance:

        knowledge_class = KNOWLEDGE_DESIGN_RULE

    elif domain != "unknown":

        knowledge_class = KNOWLEDGE_OBSERVATION

    else:

        knowledge_class = KNOWLEDGE_UNKNOWN

    # Scope defaults to CURRENT_PROJECT: an unrecognised statement must
    # never be generalised by accident.
    if project_scoped or knowledge_class not in _GENERALIZABLE_CLASSES:

        scope = SCOPE_CURRENT_PROJECT

    else:

        scope = SCOPE_GENERAL

    if external_reference:

        provenance = PROVENANCE_EXTERNAL_REFERENCE

    else:

        provenance = PROVENANCE_HUMAN_TEACHER

    # ---- candidate kind ----
    if turn_kind == "CORRECTION" or (error and negation):

        candidate_kind = "correction"

    elif zone_assignment_zone:

        # Checked BEFORE the definitional branch: a zone statement often
        # ends in a copula ("... در منطقه عمومی است"), which would
        # otherwise label it a "definition" of a term.
        candidate_kind = "observation"

    elif is_definitional and not normative:

        # `is_definitional`, not the bare `definitional`: a Persian
        # copular definition carries no explicit marker, so using the
        # old flag labelled every definition an "observation".
        candidate_kind = "definition"

    elif normative and (negation or "avoid" in form):

        candidate_kind = "constraint"

    elif normative:

        candidate_kind = (
            "rule"
            if any(
                marker in token_set
                for marker in (
                    "\u0628\u0627\u06cc\u062f",        # باید
                    "\u0646\u0628\u0627\u06cc\u062f",  # نباید
                    "must",
                    "mustnt",
                    "required",
                    "necessary",
                )
            )
            else "preference"
        )

    # TEACHING_CONTEXT_01 — a conditional design allowance is a rule
    # that only applies when its condition holds.
    elif conditional_allowance:

        candidate_kind = "rule"

    else:

        candidate_kind = "observation"

    # ---- polarity ----
    if zone_assignment_zone:

        # A zone assignment ASSERTS a fact about the model. "define"
        # (from the copula branch) would be misleading here.
        polarity = "state"

    elif is_definitional:

        polarity = "define"

    elif normative and negation:

        polarity = "avoid"

    elif normative:

        polarity = "require" if candidate_kind == "rule" else "prefer"

    # TEACHING_CONTEXT_01 — "conditional" keeps the statement's
    # conditionality visible instead of flattening it to "require".
    elif conditional_allowance:

        polarity = "conditional"

    else:

        polarity = "neutral"

    # ---- normalized restatement ----
    #
    # TEACHING_CONTEXT_01 — the subject is no longer blindly
    # `entities[0]`. See `resolve_teaching_subject`.
    # CORRECTION_LOOP_01 — `subject` / `subject_source` / `space_topic`
    # are resolved ABOVE the domain ladder now; they are reused here.

    objects = [entity for entity in entities[1:]] if len(entities) > 1 else []

    relation = relations[0] if relations else None

    parts = []

    parts.append(domain)

    if subject:

        parts.append("subject=" + subject)

    if relation and objects:

        parts.append(
            "relation=%s(%s -> %s)"
            % (relation, subject, ", ".join(objects))
        )

    elif objects:

        parts.append("related=" + ", ".join(objects))

    elif subject:

        parts.append("subject_only")

    parts.append("kind=" + candidate_kind)

    parts.append("polarity=" + polarity)

    # TEACHING_CONTEXT_01 — keep the conditionality visible, so a
    # conditional allowance is never read back as an unconditional rule.
    if conditional_allowance:

        parts.append("conditional=true")

    # PHASE 09 — learning taxonomy is part of the normalized restatement
    parts.append("knowledge_class=" + knowledge_class)

    parts.append("scope=" + scope)

    parts.append("provenance=" + provenance)

    normalized_meaning = "; ".join(parts)

    # human-readable restatement (Persian / English) is produced by
    # teach_back_v1 so this module stays a pure normalizer.

    confidence = 0.35

    if entities:

        confidence += 0.2

    if relations:

        confidence += 0.15

    if normative or is_definitional:

        confidence += 0.15

    if domain != "unknown":

        confidence += 0.1

    confidence = min(0.95, round(confidence, 3))

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "raw_statement": raw,

        "language": _language(script, features),
        "script": script,

        "domain": domain,
        "domains_detected": domains,

        "entities": entities,
        "relations": relations,

        "subject": subject,
        "objects": objects,
        "primary_relation": relation,

        # TEACHING_CONTEXT_01 — the resolved architectural space (a
        # corpus space id) and how the subject was chosen. Additive:
        # `space_topic` is None for a plain flat-entity statement.
        "space_topic": space_topic,
        "subject_source": subject_source,

        "candidate_kind": candidate_kind,
        "polarity": polarity,

        # TEACHING_CONTEXT_01 — True when the statement is a conditional
        # design allowance ("if ... allows, it can also have ...").
        "conditional": conditional_allowance,

        # PHASE 09 — learning taxonomy
        "knowledge_class": knowledge_class,
        "scope": scope,
        "provenance": provenance,
        "domain_tags": _domain_tags(
            domain, domains, entities, relations, knowledge_class
        ),

        "normative": normative,
        "definitional": definitional,
        # ADDED by the curriculum foundation fix: the EFFECTIVE
        # definitional flag, which also covers a Persian copular
        # definition ("... است" / "... هست"). `definitional` above is
        # kept as the raw explicit-marker flag so no consumer breaks.
        "is_definitional": is_definitional,
        "copula_definition": copula_definition,
        # CURRICULUM_FOUNDATION_FIX_02 — a descriptive zone assignment.
        # `zone` is the resolved Phase 11 zone constant, or None when the
        # statement names no zone.
        "zone_assignment": (
            {
                "zone": zone_assignment_zone,
                "zone_label": zone_display(zone_assignment_zone, "en"),
                "phrase": zone_word_in(form),
            }
            if zone_assignment_zone
            else None
        ),
        "negation": negation,
        "correctness_word": correctness,

        "normalized_meaning": normalized_meaning,

        # Heuristic LEARNING-STATE confidence, never a probability that
        # the statement is architecturally true.
        "confidence": confidence,
        "confidence_kind": "learning_state",

        "deterministic": True,
        "llm_used": False,
        "network_used": False,
    }


def _domain_tags(domain, domains, entities, relations, knowledge_class):

    """Additive, de-duplicated domain tag set for a meaning."""

    tags = []

    for value in [domain] + list(domains):

        if value and value not in tags:

            tags.append(value)

    if relations and "adjacency" not in tags:

        tags.append("adjacency")

    if entities and "space" not in tags:

        tags.append("space")

    return tags
