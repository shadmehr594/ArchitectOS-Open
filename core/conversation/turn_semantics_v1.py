# ==========================================================
# ArchitectOS Turn Semantics v1
#
# PHASE 08B — CONVERSATIONAL TURN SEMANTICS
#
# ONE provider-independent, deterministic classification of what a
# conversational turn IS:
#
#   QUESTION               the user asks something
#   INSTRUCTION            the user wants an ACTION performed
#   CORRECTION             the user says a previous answer/example was wrong
#   TEACHING_STATEMENT     the user states a preference / rule / definition
#   CONFIRMATION_REQUEST   the user asks what the assistant understood
#   NORMAL_CONVERSATION    greeting / small talk / no architectural signal
#   UNKNOWN                nothing could be classified
#
# Design constraints (Phase 08B)
#   - NO LLM, NO network, NO provider.  Pure deterministic features.
#   - MUST NOT depend on exact Persian phrases.  The classifier works on
#     FEATURES (morphology, modality, negation, interrogativity, verb
#     form, script) plus small curated FEATURE LEXICONS of function
#     words and verb stems.  The example sentences in the Phase 08 brief
#     are used as TESTS, never as hardcoded rules.
#   - Works for Persian AND English (and mixed).
#   - A statement is never treated as architectural truth here.  This
#     module only names the turn; 08C decides what (if anything) may
#     later become knowledge.
#
# IMPORTANT (08G boundary)
#   A TEACHING_STATEMENT and an INSTRUCTION are deliberately separated.
#     "آشپزخانه باید به غذاخوری نزدیک باشه."   -> TEACHING_STATEMENT
#     "یک خط 45 درجه بکش."                      -> INSTRUCTION
#   An instruction is NOT architectural knowledge.
# ==========================================================


from __future__ import annotations


import re


CONTRACT = "TurnSemanticsV1"
VERSION = "1.0"


# ----------------------------------------------------------
# TURN KINDS
# ----------------------------------------------------------

TURN_QUESTION = "QUESTION"
TURN_INSTRUCTION = "INSTRUCTION"
TURN_CORRECTION = "CORRECTION"
TURN_TEACHING_STATEMENT = "TEACHING_STATEMENT"
TURN_CONFIRMATION_REQUEST = "CONFIRMATION_REQUEST"
TURN_NORMAL_CONVERSATION = "NORMAL_CONVERSATION"
TURN_UNKNOWN = "UNKNOWN"

# PHASE 09 — TEACHING INTENT / ELICITATION
#
# "می خواهم راه پله را به تو یاد بدهم" is NOT an instruction and must
# never reach EXECUTE.  It is an offer to teach, and the correct answer
# is a clarifying question about which aspect is being taught.
TURN_OFFER_TO_TEACH = "OFFER_TO_TEACH"

# Alias: the brief calls this TEACHING_INTENT.
TEACHING_INTENT = TURN_OFFER_TO_TEACH

# TEACHING SESSION STATE FIX — READ-ONLY KNOWLEDGE REFLECTION
#
# "برداشت فعلی تو از این فضا چیست؟" ("what is your current
# understanding of this space?") is NOT a teaching turn and NOT a
# teach-back request. The user is asking the assistant to STATE WHAT IT
# ALREADY KNOWS from the existing corpus, before teaching anything.
#
# It must never create a candidate, store teaching, promote knowledge
# or start a lesson. It is answered from the existing read-only
# knowledge bridges.
TURN_KNOWLEDGE_REFLECTION = "KNOWLEDGE_REFLECTION"


ALL_TURN_KINDS = (
    TURN_QUESTION,
    TURN_INSTRUCTION,
    TURN_CORRECTION,
    TURN_TEACHING_STATEMENT,
    TURN_CONFIRMATION_REQUEST,
    TURN_NORMAL_CONVERSATION,
    TURN_OFFER_TO_TEACH,
    # TEACHING SESSION STATE FIX
    TURN_KNOWLEDGE_REFLECTION,
    TURN_UNKNOWN,
)


# Turn kinds that are a teaching intent (offer or request).
TEACHING_INTENT_KINDS = (TURN_OFFER_TO_TEACH,)


# TEACHING SESSION STATE FIX — read-only reflection turns.
# They are NOT teaching intents, NOT candidate turns and NOT teach-back
# requests: nothing is written and nothing is learned.
KNOWLEDGE_REFLECTION_KINDS = (TURN_KNOWLEDGE_REFLECTION,)


# Turn kinds whose content MAY later become learned knowledge.
# Phase 08 records them as CANDIDATES only.  Nothing is learned here.
CANDIDATE_TURN_KINDS = (
    TURN_TEACHING_STATEMENT,
    TURN_CORRECTION,
)


# Turn kinds that request a teach-back explanation.
TEACH_BACK_TURN_KINDS = (
    TURN_CONFIRMATION_REQUEST,
)


# ----------------------------------------------------------
# TEXT NORMALIZATION (matching form only — raw text is preserved)
# ----------------------------------------------------------

_ZWNJ = "\u200c"

_ARABIC_TO_PERSIAN = {
    "\u064a": "\u06cc",  # Arabic yeh   -> Persian yeh
    "\u0649": "\u06cc",  # Alef maksura -> Persian yeh
    "\u0643": "\u06a9",  # Arabic kaf   -> Persian kaf
    "\u0629": "\u0647",  # Teh marbuta  -> heh
    "\u06c0": "\u0647",  # Heh with yeh -> heh
}

_PERSIAN_DIGITS = "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9"

_QUESTION_MARKS = ("?", "\uff1f", "\u061f")


def match_form(text):
    """Deterministic lower-cased, punctuation-stripped matching form.

    The RAW user text is never destroyed; this form exists only so the
    same feature lexicon works across Persian, Arabic-script variants
    and English.
    """

    value = str(text or "")

    for source, target in _ARABIC_TO_PERSIAN.items():

        value = value.replace(source, target)

    value = value.replace(_ZWNJ, " ")

    value = value.replace("\u0640", "")  # tatweel

    # Persian/Arabic digits -> ASCII digits
    for index, digit in enumerate(_PERSIAN_DIGITS):

        value = value.replace(digit, str(index))

    value = value.lower()

    # keep letters + digits + spaces only
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def has_question_mark(text):

    raw = str(text or "")

    return any(mark in raw for mark in _QUESTION_MARKS)


def script_of(text):
    """Coarse script detection. 'persian' | 'english' | 'mixed' | 'unknown'."""

    persian = 0
    english = 0

    for char in str(text or ""):

        code = ord(char)

        if 0x0600 <= code <= 0x06FF or 0x0750 <= code <= 0x077F:

            persian += 1

        elif char.isalpha() and code < 0x0600:

            english += 1

    if persian and english:

        return "mixed"

    if persian:

        return "persian"

    if english:

        return "english"

    return "unknown"


# ----------------------------------------------------------
# FEATURE LEXICONS
#
# These are FEATURES (function words, modality markers, verb stems),
# not sentence templates.  A sentence is never matched as a whole.
# ----------------------------------------------------------

# --- interrogative function words / question starters ----------------

INTERROGATIVE_TOKENS = frozenset(
    (
        # Persian
        "\u0686\u06cc",        # چی
        "\u0686\u0647",        # چه
        "\u0686\u0631\u0627",  # چرا
        "\u0686\u0637\u0648\u0631",      # چطور
        "\u0686\u06af\u0648\u0646\u0647",  # چگونه
        "\u0686\u0637\u0648\u0631\u06cc",  # چطوری
        "\u06a9\u062c\u0627",  # کجا
        "\u06a9\u06cc",        # کی
        "\u0686\u0646\u062f",  # چند
        "\u0686\u0642\u062f\u0631",        # چقدر
        "\u06a9\u062f\u0627\u0645",        # کدام
        "\u0622\u06cc\u0627",  # آیا
        "\u0686\u0646\u062f\u0627\u0646",  # چندان
        # English
        "what", "why", "how", "where", "when", "which", "who",
        "whose", "whom", "whether",
    )
)


# --- understanding / teach-back verbs -------------------------------

UNDERSTANDING_STEMS = (
    # Persian stems (matched as substrings of a token)
    "\u0641\u0647\u0645\u06cc\u062f",  # فهمید
    "\u0641\u0647\u0645\u06cc\u062f\u06cc",  # فهمیدی
    "\u0645\u062a\u0648\u062c\u0647",  # متوجه
    "\u062f\u0631\u06a9",              # درک
    "\u0628\u0631\u062f\u0627\u0634\u062a",  # برداشت
    "\u06af\u06cc\u0631\u062a",        # گیرت
    # English
    "understand", "understood", "comprehend", "comprehended",
    "grasp", "grasped",
)

# explicit recall phrasings (feature phrases, not full sentences)
RECALL_MARKERS = (
    "\u0686\u06cc \u06af\u0641\u062a\u0645",      # چی گفتم
    "\u0686\u0647 \u06af\u0641\u062a\u0645",      # چه گفتم
    "\u06cc\u0627\u062f\u062a \u0647\u0633\u062a",  # یادت هست
    "\u0628\u06af\u0648 \u0686\u06cc",            # بگو چی
    "what did i say",
    "what did i tell you",
    "repeat back",
    "say back",
    "tell me what you understood",
    "what did you understand",
    "what do you understand",
    "did you understand",
    "do you understand what i said",
    "what did you get from",
)


# --- negation / error ------------------------------------------------

NEGATION_TOKENS = frozenset(
    (
        # Persian
        "\u0646\u0647",        # نه
        "\u062e\u06cc\u0631",  # خیر
        "\u0646\u06cc\u0633\u062a",        # نیست
        "\u0646\u06cc\u0633\u062a\u0647",  # نیسته
        "\u0646\u0628\u0648\u062f",        # نبود
        "\u0628\u0644\u06a9\u0647",        # بلکه
        # English
        "no", "not", "isnt", "arent", "wasnt", "werent",
        "dont", "doesnt", "didnt", "cannot", "cant", "instead",
    )
)


ERROR_TOKENS = frozenset(
    (
        # Persian
        "\u0627\u0634\u062a\u0628\u0627\u0647",  # اشتباه
        "\u0627\u0634\u062a\u0628\u0627\u0647\u0647",  # اشتباهه
        "\u063a\u0644\u0637",    # غلط
        "\u063a\u0644\u0637\u0647",  # غلطه
        "\u0646\u0627\u062f\u0631\u0633\u062a",  # نادرست
        "\u062e\u0637\u0627",    # خطا
        "\u063a\u0644\u0637\u0647",  # غلطه
        # English
        "wrong", "incorrect", "false", "mistake", "mistaken",
        "error", "inaccurate", "invalid",
    )
)


# --- correctness words (paired with negation -> correction) ----------

CORRECTNESS_TOKENS = frozenset(
    (
        "\u062f\u0631\u0633\u062a",  # درست
        "\u0635\u062d\u06cc\u062d",  # صحیح
        "correct", "right", "true", "accurate",
    )
)


# --- modality (deontic / normative) ----------------------------------

NORMATIVE_TOKENS = frozenset(
    (
        # Persian
        "\u0628\u0627\u06cc\u062f",          # باید
        "\u0628\u0627\u06cc\u0633\u062a\u06cc",  # بایستی
        "\u0646\u0628\u0627\u06cc\u062f",    # نباید
        "\u0628\u0647\u062a\u0631",          # بهتر
        "\u0628\u0647\u062a\u0631\u0647",    # بهتره
        "\u0644\u0627\u0632\u0645",          # لازم
        "\u0644\u0627\u0632\u0645\u0647",    # لازمه
        "\u0636\u0631\u0648\u0631\u06cc",    # ضروری
        "\u0645\u06cc\u0628\u0627\u06cc\u0633\u062a",  # میبایست
        "\u062a\u0631\u062c\u06cc\u062d",    # ترجیح
        "\u0627\u0648\u0644\u0648\u06cc\u062a",  # اولویت
        "\u0645\u0646\u0627\u0633\u0628",    # مناسب
        "\u062f\u0631\u0633\u062a",          # درست (normative when paired)
        # PHASE 09 — Persian normative markers that were missing, so real
        # teaching statements were falling through to NORMAL_CONVERSATION.
        "\u0645\u0647\u0645",        # مهم
        "\u0627\u0647\u0645\u06cc\u062a",  # اهمیت
        "\u0636\u0631\u0648\u0631\u062a",  # ضرورت
        "\u0627\u0644\u0632\u0627\u0645\u06cc",  # الزامی
        "\u0646\u06cc\u0627\u0632",  # نیاز
        "\u0646\u06cc\u0627\u0632\u0645\u0646\u062f",  # نیازمند
        "\u0627\u062d\u062a\u06cc\u0627\u062c",  # احتیاج
        # English
        "should", "shouldnt", "must", "mustnt", "ought",
        "need", "needs", "needed", "require", "required",
        "prefer", "preferred", "preferable", "preferably",
        "better", "best", "important", "necessary",
    )
)


# --- definitional ----------------------------------------------------

DEFINITIONAL_TOKENS = frozenset(
    (
        # Persian
        "\u06cc\u0639\u0646\u06cc",        # یعنی
        "\u0645\u0639\u0646\u06cc",        # معنی
        "\u0645\u0639\u0646\u0627",        # معنا
        "\u062a\u0639\u0631\u06cc\u0641",  # تعریف
        # English
        "means", "meaning", "refers", "defines", "defined",
        "definition", "represents", "denotes",
    )
)


# PHASE 09 — Persian COPULAR definitions ("X ... است" / "... هست").
# A definition in Persian frequently carries no explicit marker at all:
#   "راه پله ارتباط بین طبقات است"
# The copula is a morphological FEATURE, not a phrase rule. The length
# guard keeps short conversational copulas out of the definitional path.
PERSIAN_COPULA_TOKENS = frozenset(
    (
        "\u0627\u0633\u062a",        # است
        "\u0647\u0633\u062a",        # هست
        "\u0646\u06cc\u0633\u062a",  # نیست
        "\u0627\u0646\u062f",        # اند
        "\u0647\u0633\u062a\u0646\u062f",  # هستند
    )
)


MIN_COPULA_DEFINITION_TOKENS = 4


# --- disagreement openers (a turn that OPENS by denying) --------------
#
# CORRECTION_LOOP_01 — a correction that uses no error word at all.
#
# "نه فقط و فقط برای زوجین هست ، حتی برای مسن ها و میهمانان هم استفاده
#  نمیشود" denies the assistant's previous answer, but it carries neither
# an error marker ("اشتباه") nor a correctness word, so
# `correction_lexical` was False, the turn classified NORMAL_CONVERSATION
# and fell straight through to the generic LLM — which then INVENTED the
# opposite of what the teacher had just said.
#
# A bare "نه" (an answer to a yes/no question) must NOT count, so the
# opener alone is never sufficient: the turn must also be long enough to
# be a statement AND carry a copula of its own. That keeps
# "نه ممنون، خودم انجام میدم" out.
DISAGREEMENT_OPENERS = frozenset(
    (
        "\u0646\u0647",        # نه
        "\u062e\u06cc\u0631",  # خیر
        "\u0628\u0644\u06a9\u0647",  # بلکه
        "no", "nope",
    )
)


DISAGREEMENT_COPULA_TOKENS = frozenset(("is", "are", "was", "were"))


MIN_DISAGREEMENT_TOKENS = MIN_COPULA_DEFINITION_TOKENS


# --- curriculum foundation fix (CURRICULUM_PHASE_01 prep) -------------
#
# PATTERN and DECISION markers live HERE, in the lower-level module, so
# that the turn classifier and the knowledge-class ladder in
# `teaching_meaning_v1` share ONE vocabulary. A second copy is how the
# two layers would silently drift apart.

# A customary / typical arrangement. Phase 09 only had the frequency
# adverbs; "الگو" (pattern) itself was missing, so a statement that
# literally named a pattern was not recognised as one.
PATTERN_MARKERS = (
    "\u0645\u0639\u0645\u0648\u0644\u0627",        # معمولا
    "\u063a\u0627\u0644\u0628\u0627",              # غالبا
    "\u0639\u0645\u0648\u0645\u0627",              # عموما
    "\u0628\u06cc\u0634\u062a\u0631 \u0627\u0648\u0642\u0627\u062a",  # بیشتر اوقات
    "\u062f\u0631 \u0628\u06cc\u0634\u062a\u0631 \u0645\u0648\u0627\u0631\u062f",  # در بیشتر موارد
    "\u0645\u0639\u0645\u0648\u0644",              # معمول
    "\u062a\u062c\u0631\u0628\u0647 \u0646\u0634\u0627\u0646",  # تجربه نشان
    # ADDED — naming the pattern itself
    "\u0627\u0644\u06af\u0648",                    # الگو / الگوی / الگوها
    "\u0631\u0648\u06cc\u0647",                    # رویه
    "\u0639\u0631\u0641",                          # عرف
    "\u0633\u0646\u062a",                          # سنت
    "\u0631\u0627\u06cc\u062c",                    # رایج
    "usually",
    "typically",
    "generally",
    "often",
    "in most cases",
    "as a rule",
    "tends to",
    # ADDED — English pattern words
    "pattern",
    "common practice",
    "convention",
    "conventional",
)


# A decision taken FOR THIS PROJECT. Deliberately a DECISION verb, not
# the bare project marker: "این پروژه" alone appears in ordinary
# conversation, and turning every such sentence into a teaching turn
# would be a behaviour regression.
DECISION_MARKERS = (
    "\u062a\u0635\u0645\u06cc\u0645",              # تصمیم (گرفتیم/گرفته شد)
    "\u0642\u0631\u0627\u0631 \u0634\u062f",      # قرار شد
    "\u0645\u0642\u0631\u0631 \u0634\u062f",      # مقرر شد
    "\u062a\u0648\u0627\u0641\u0642",              # توافق
    "\u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0631\u062f\u06cc\u0645",  # انتخاب کردیم
    "\u0628\u0631\u06af\u0632\u06cc\u062f\u06cc\u0645",  # برگزیدیم
    "\u0645\u0635\u0648\u0628",                    # مصوب
    "we decided",
    "decided",
    "we chose",
    "we agreed",
    "agreed on",
    "decision",
)


def contains_any(form, markers):

    """Substring marker test on an already-normalised match form.

    Markers are PHRASES ("in most cases", "بیشتر اوقات"), not tokens, so
    a token-set intersection cannot find them.
    """

    return any(marker in form for marker in markers)


# --- zone assignment (CURRICULUM_FOUNDATION_FIX_02) -------------------
#
# A DESCRIPTIVE statement that assigns spaces to an architectural zone:
#
#     "ورودی و نشیمن در منطقه عمومی قرار می گیرند"
#
# It carries no normative / definitional / pattern / decision marker, so
# the turn gate used to drop it and NO CANDIDATE was ever built — which is
# exactly why Part 4 (Zoning) was the one unteachable part.
#
# TWO parts are required: a ZONE WORD and an ASSIGNMENT PHRASE. Requiring
# both keeps an incidental mention of the word "منطقه" from turning an
# ordinary sentence into a teaching turn.
#
# Written in MATCH FORM: `match_form` folds the Persian ZWNJ and the
# combining hamza to a space, so "منطقهٔ نیمه‌عمومی" arrives as
# "منطقه نیمه عمومی".

ZONE_WORDS = (
    # longest first, so the specific zone wins over the general one
    "\u0645\u0646\u0637\u0642\u0647 \u0646\u06cc\u0645\u0647 \u0639\u0645\u0648\u0645\u06cc",  # منطقه نیمه عمومی
    "\u0645\u0646\u0637\u0642\u0647 \u0639\u0645\u0648\u0645\u06cc",  # منطقه عمومی
    "\u0645\u0646\u0637\u0642\u0647 \u062e\u0635\u0648\u0635\u06cc",  # منطقه خصوصی
    "\u0645\u0646\u0637\u0642\u0647 \u062e\u062f\u0645\u0627\u062a\u06cc",  # منطقه خدماتی
    "\u0645\u0646\u0637\u0642\u0647 \u06af\u0631\u062f\u0634",  # منطقه گردش
    "\u0645\u0646\u0637\u0642\u0647 \u0628\u06cc\u0631\u0648\u0646\u06cc",  # منطقه بیرونی
    "\u0646\u06cc\u0645\u0647 \u0639\u0645\u0648\u0645\u06cc",  # نیمه عمومی
    "semi public zone",
    "semi-public zone",
    "public zone",
    "private zone",
    "service zone",
    "circulation zone",
    "external zone",
)


ZONE_ASSIGNMENT_PHRASES = (
    # The prepositional construction "X در منطقه Y است / قرار دارد".
    # Without this, the copular form "... در منطقه عمومی است" was NOT an
    # assignment and fell through to DEFINITION.
    "\u062f\u0631 \u0645\u0646\u0637\u0642\u0647",  # در منطقه
    "\u0642\u0631\u0627\u0631 \u0645\u06cc \u06af\u06cc\u0631\u0646\u062f",  # قرار می گیرند
    "\u0642\u0631\u0627\u0631 \u0645\u06cc \u06af\u06cc\u0631\u062f",  # قرار می گیرد
    "\u0642\u0631\u0627\u0631 \u062f\u0627\u0631\u0646\u062f",  # قرار دارند
    "\u0642\u0631\u0627\u0631 \u062f\u0627\u0631\u062f",  # قرار دارد
    "\u0648\u0627\u0642\u0639 \u0634\u062f\u0647",  # واقع شده
    "\u062a\u0639\u0644\u0642 \u062f\u0627\u0631\u0646\u062f",  # تعلق دارند
    "\u062a\u0639\u0644\u0642 \u062f\u0627\u0631\u062f",  # تعلق دارد
    "\u0628\u062e\u0634\u06cc \u0627\u0632",  # بخشی از
    "\u062c\u0632\u0621",  # جزء
    "belongs to",
    "belong to",
    "is part of",
    "are part of",
    "sits in",
    "sit in",
    "falls in",
    "fall in",
    "is in the",
    "are in the",
)


def zone_word_in(form):

    """The most specific zone word present, or None."""

    for marker in ZONE_WORDS:

        if marker in form:

            return marker

    return None


def is_zone_assignment(form):

    """A zone word AND an assignment phrase must BOTH be present."""

    return bool(zone_word_in(form)) and contains_any(
        form, ZONE_ASSIGNMENT_PHRASES
    )


# --- TEACHING_CONTEXT_01 — CONDITIONAL DESIGN ALLOWANCE ---------------

# "اگر مساحت زمین و زیربنا اجازه بدهد، کلوزت روم هم می تواند داشته باشد"
# is a CONDITIONAL design allowance — architecturally a design rule, but
# it carries no normative marker, so the turn gate dropped it to
# NORMAL_CONVERSATION and no candidate was ever built.
#
# TWO parts are required, so an ordinary conditional sentence
# ("اگر باران بیاید می رویم") is never captured.
CONDITIONAL_OPENERS = (
    "\u0627\u06af\u0631",  # اگر
    "\u062f\u0631 \u0635\u0648\u0631\u062a\u06cc \u06a9\u0647",  # در صورتی که
    "\u0686\u0646\u0627\u0646\u0686\u0647",  # چنانچه
    "if ",
)

CONDITIONAL_ALLOWANCE_MODALS = (
    "\u0645\u06cc \u062a\u0648\u0627\u0646\u062f",  # می تواند
    "\u0645\u06cc \u062a\u0648\u0627\u0646\u0646\u062f",  # می توانند
    "\u0627\u062c\u0627\u0632\u0647 \u0628\u062f\u0647\u062f",  # اجازه بدهد
    "\u0627\u062c\u0627\u0632\u0647 \u0645\u06cc \u062f\u0647\u062f",  # اجازه می دهد
    "\u0627\u0645\u06a9\u0627\u0646 \u062f\u0627\u0631\u062f",  # امکان دارد
    "can have",
    "may have",
)


def is_conditional_allowance(form):

    """A conditional opener AND an allowance modal must BOTH be present."""

    return contains_any(form, CONDITIONAL_OPENERS) and contains_any(
        form, CONDITIONAL_ALLOWANCE_MODALS
    )


# --- teaching intent / elicitation (PHASE 09) -------------------------

# Verbs/markers that mean "teach" (feature phrases, not whole sentences).
TEACH_VERB_MARKERS = (
    # Persian — "یاد دادن" (to teach) in its inflected forms
    "\u06cc\u0627\u062f \u0628\u062f\u0647",        # یاد بده
    "\u06cc\u0627\u062f \u0628\u062f\u0647\u0645",  # یاد بدهم
    "\u06cc\u0627\u062f \u0628\u062f\u0647\u06cc",  # یاد بدهی
    "\u06cc\u0627\u062f \u0628\u062f\u0647\u06cc\u0645",  # یاد بدهیم
    "\u06cc\u0627\u062f\u062a \u0628\u062f\u0647",  # یادت بده
    "\u06cc\u0627\u062f\u0645 \u0628\u062f\u0647",  # یادم بده
    "\u06cc\u0627\u062f \u0628\u06af\u06cc\u0631",  # یاد بگیر (learn)
    "\u0622\u0645\u0648\u0632\u0634",        # آموزش
    "\u062a\u0639\u0644\u06cc\u0645",        # تعلیم
    "\u062f\u0631\u0633 \u0628\u062f\u0647",  # درس بده
    # CHAT RUNTIME REGRESSION FIX — first-person / colloquial forms.
    # "یادت بدم" ("I'll teach you") was missing: the list had the
    # imperative "یادت بده" but not the contracted 1st-person "بدم", so a
    # real user's teaching offer was not recognised as a teaching intent
    # at all and fell through to the general-chat fallback.
    "\u06cc\u0627\u062f\u062a \u0628\u062f\u0645",   # یادت بدم
    "\u06cc\u0627\u062f \u0628\u062f\u0645",         # یاد بدم
    "\u06cc\u0627\u062f\u062a \u0628\u062f\u0647\u0645",  # یادت بدهم
    "\u06cc\u0627\u062f\u062a\u0648\u0646 \u0628\u062f\u0645",  # یادتون بدم
    "\u06cc\u0627\u062f \u0628\u062f\u06cc\u0645",   # یاد بدیم
    "\u0622\u0645\u0648\u0632\u0634 \u0628\u062f\u0645",  # آموزش بدم
    "\u062f\u0631\u0633 \u0628\u062f\u0645",         # درس بدم
    # English
    "teach you",
    "teach me",
    "let me teach",
    "learn about",
    "explain to you",
)


# Volition / offer markers — the speaker signals intent to do something.
VOLITION_MARKERS = (
    # Persian
    "\u0645\u06cc \u062e\u0648\u0627\u0647\u0645",  # می خواهم
    "\u0645\u06cc\u062e\u0648\u0627\u0645",        # میخوام
    "\u0645\u06cc \u062e\u0648\u0627\u0647\u0645",  # می خواهم (ZWNJ form)
    "\u0642\u0635\u062f \u062f\u0627\u0631\u0645",  # قصد دارم
    "\u0645\u06cc \u062a\u0648\u0627\u0646\u0645",  # می توانم
    "\u0627\u062c\u0627\u0632\u0647 \u0628\u062f\u0647",  # اجازه بده
    # CHAT RUNTIME REGRESSION FIX — first-person plural / colloquial.
    # "میخوایم" ("we want") was missing: only the singular "میخوام" was
    # listed, so "میخوایم اولین جلسه آموزش معماری رو شروع کنیم" was not a
    # teaching intent and fell through to the general-chat fallback.
    "\u0645\u06cc\u062e\u0648\u0627\u06cc\u0645",        # میخوایم
    "\u0645\u06cc \u062e\u0648\u0627\u06cc\u0645",        # می خوایم
    "\u0645\u06cc \u062e\u0648\u0627\u0647\u06cc\u0645",  # می خواهیم
    "\u0645\u06cc\u062e\u0648\u0627\u06cc\u06cc\u062f",   # میخوایید
    "\u0645\u06cc \u062e\u0648\u0627\u06cc\u06cc\u062f",  # می خوایید
    "\u0642\u0635\u062f \u062f\u0627\u0631\u06cc\u0645",  # قصد داریم
    "\u0642\u0631\u0627\u0631\u0647",                    # قراره (it's decided)
    "\u0642\u0631\u0627\u0631 \u0627\u0633\u062a",        # قرار است
    # English
    "i want to",
    "i would like to",
    "i'd like to",
    "let me",
    "i will ",
    "i'll ",
    "can i ",
    "may i ",
    "shall i ",
    "would you like me to",
    "we want to",
    "we would like to",
)


# Addressee markers — the speaker is offering knowledge TO the assistant.
ADDRESSEE_MARKERS = (
    "\u0628\u0647 \u062a\u0648",        # به تو
    "\u0628\u0631\u0627\u062a",        # برات
    "\u0628\u0631\u0627\u06cc\u062a",  # برایت
    "\u062a\u0648 \u0631\u0627",        # تو را
    "\u0628\u0647 \u0634\u0645\u0627",  # به شما
    "\u0628\u0631\u0627\u06cc \u0634\u0645\u0627",  # برای شما
    "to you",
    "for you",
)


# --- TEACHING CONTENT CAPTURE V1 — USER -> ARCHITECTOS TRANSFER --------
#
# The teaching-intent rung (rung 0) required a volition, an assistant
# addressee or an explicit teach-request. TWO REAL user shapes carry the
# transfer DIRECTION structurally without any of those three:
#
#   "یه نکته آموزشی دارم"                  (I HAVE a teaching note)
#   "این رو یاد بگیر، سرویس بهتره ..."      (LEARN this — the assistant
#                                           is the addressee)
#
# Both are USER -> ARCHITECTOS. NEITHER may be inferred from the word
# "آموزشی" alone: the resource and learner shapes must stay OUT —
#   "یه ویدیوی آموزشی معرفی کن"
#   "این کتاب آموزشی خوبه؟"
#   "یه نکته آموزشی درباره معماری برام توضیح بده"
#   "می تونی یه آموزش درباره پلان بهم بدی؟"
#   "معماری رو بهم آموزش بده"
#
# ALL MARKERS ARE WRITTEN IN MATCH FORM (`match_form` preserves the
# alef-madda `آ`, folds the ZWNJ to a space and strips punctuation).

# A NOUN that names KNOWLEDGE ITSELF (a tip / rule / principle) — the
# thing a teacher OWNS and hands over. A LOCAL copy of the boundary's
# own table, so no frozen module is imported here.
TEACHING_KNOWLEDGE_NOUNS = (
    "\u0646\u06a9\u062a\u0647",        # نکته (tip)
    "\u0645\u0637\u0644\u0628",        # مطلب (point)
    "\u0627\u0635\u0644",              # اصل (principle)
    "\u0642\u0627\u0646\u0648\u0646",  # قانون (rule)
    "\u0642\u0627\u0639\u062f\u0647",  # قاعده (rule)
    "\u0631\u0627\u0647\u0646\u0645\u0627",  # راهنما (guide)
    "\u062a\u062c\u0631\u0628\u0647",  # تجربه (experience)
    "\u062f\u0631\u0633",              # درس (lesson)
    "\u062f\u0627\u0646\u0634",        # دانش (knowledge)
)

# A NOUN that names a RESOURCE (a thing ABOUT a topic), not knowledge.
TEACHING_RESOURCE_NOUNS = (
    "\u06a9\u062a\u0627\u0628",              # کتاب (book)
    "\u0648\u06cc\u062f\u06cc\u0648",        # ویدیو (video)
    "\u0641\u06cc\u0644\u0645",              # فیلم (film)
    "\u062f\u0648\u0631\u0647",              # دوره (course)
    "\u06a9\u0644\u0627\u0633",              # کلاس (class)
    "\u0645\u0642\u0627\u0644\u0647",        # مقاله (article)
    "\u067e\u0648\u062f\u06a9\u0627\u0633\u062a",  # پادکست (podcast)
    "\u0633\u0627\u06cc\u062a",              # سایت (site)
    "\u0644\u06cc\u0646\u06a9",              # لینک (link)
)

# The speaker's OWN possession — "I have". Matched as a WHOLE TOKEN
# (through `token_set`), so the negated "ندارم" ("I do NOT have") can
# never count as possession.
TEACHING_POSSESSION_VERBS = (
    "\u062f\u0627\u0631\u0645",        # دارم
    "\u062f\u0627\u0631\u06cc\u0645",  # داریم
)

# A LEARNER marker — the user is the one asking to BE TAUGHT, so the
# direction is ARCHITECTOS -> USER and this is never teaching-to-system.
TEACHING_LEARNER_MARKERS = (
    "\u0628\u0647\u0645",          # بهم (to me)
    "\u0628\u0647 \u0645\u0646",   # به من (to me)
    "\u0628\u0631\u0627\u0645",    # برام (for me)
)

# An imperative whose ADDRESSEE is the ASSISTANT: learn / remember. This
# is a TEACHING directive, not a design action, so it outranks the
# generic INSTRUCTION rung.
TEACHING_IMPERATIVES_TO_ASSISTANT = (
    "\u06cc\u0627\u062f \u0628\u06af\u06cc\u0631",  # یاد بگیر
    "\u06cc\u0627\u062f\u062a \u0628\u0627\u0634\u0647",  # یادت باشه
    "\u06cc\u0627\u062f \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634",  # یاد داشته باش
    "\u0628\u0647 \u062e\u0627\u0637\u0631 \u0628\u0633\u067e\u0627\u0631",  # به خاطر بسپار
    "\u06cc\u0627\u062f \u0628\u0633\u067e\u0627\u0631",  # یاد بسپار
)

# The ASSISTANT as the addressee — "to you". Matched as a WHOLE TOKEN
# (or an explicit two-word phrase), so the substring inside "بهتره"
# ("better") can never be mistaken for "بهت" ("to you").
TEACHING_ADDRESSEE_TOKENS = (
    "\u0628\u0647\u062a",              # بهت (to you)
    "\u0628\u0631\u0627\u062a",        # برات (for you)
    "\u0628\u0631\u0627\u06cc\u062a",  # برایت (for you)
)

TEACHING_ADDRESSEE_PHRASES = (
    "\u0628\u0647 \u062a\u0648",        # به تو
    "\u0628\u0647 \u0634\u0645\u0627",  # به شما
    "\u0628\u0631\u0627\u06cc \u0634\u0645\u0627",  # برای شما
)


def is_knowledge_possession_offer(form, token_set):

    """The speaker OWNS knowledge and is about to hand it over.

    Three parts are required — a knowledge noun, a first-person
    possession TOKEN and NO resource noun — plus a direction guard: a
    learner marker ("بهم" / "به من" / "برام") means the user is asking
    to be taught, so it disqualifies the turn.
    """

    form = form or ""

    if not any(noun in form for noun in TEACHING_KNOWLEDGE_NOUNS):

        return False

    if not (token_set & frozenset(TEACHING_POSSESSION_VERBS)):

        return False

    if any(noun in form for noun in TEACHING_RESOURCE_NOUNS):

        return False

    if any(marker in form for marker in TEACHING_LEARNER_MARKERS):

        return False

    return True


def is_teaching_imperative_to_assistant(form):

    """A learn / remember imperative whose addressee is the assistant."""

    return any(
        marker in (form or "")
        for marker in TEACHING_IMPERATIVES_TO_ASSISTANT
    )


def is_teaching_addressee_transfer(form, token_set, teach_verb):

    """The assistant is the ADDRESSEE and a teaching verb is present.

    "بهت یاد بدم" ("I tell you" — literally "to-you I give-learn") states
    the transfer direction without any volition word. The SAME guards as
    the possession shape apply, so a resource offer ("یه ویدیوی آموزشی
    برات بفرستم") and a learner request ("یه نکته آموزشی برام توضیح
    بده") never qualify.
    """

    form = form or ""

    if not teach_verb:

        return False

    if any(noun in form for noun in TEACHING_RESOURCE_NOUNS):

        return False

    if any(marker in form for marker in TEACHING_LEARNER_MARKERS):

        return False

    if token_set & frozenset(TEACHING_ADDRESSEE_TOKENS):

        return True

    return any(phrase in form for phrase in TEACHING_ADDRESSEE_PHRASES)


# ==========================================================
# TEACHING SESSION STATE FIX — READ-ONLY KNOWLEDGE REFLECTION
#
# A reflection turn asks the assistant to STATE WHAT IT ALREADY KNOWS.
# It is detected by a TWO-PART test wherever possible, because a single
# word over-captures: "برداشت" alone appears in ordinary statements
# ("برداشت من این است که ..."), and "چه چیزهایی" alone opens ordinary
# questions ("چه چیزهایی برای اتاق خواب لازم است؟").
#
# ALL MARKERS ARE WRITTEN IN MATCH FORM (`match_form`), which folds the
# Persian ZWNJ to a space and strips the combining hamza.
# ==========================================================

# 1. A topic phrase that names the CURRENT understanding.
KNOWLEDGE_REFLECTION_TOPIC_MARKERS = (
    "\u0628\u0631\u062f\u0627\u0634\u062a \u0641\u0639\u0644\u06cc",  # برداشت فعلی
    "\u0628\u0631\u062f\u0627\u0634\u062a \u062a\u0648",               # برداشت تو
    "\u0628\u0631\u062f\u0627\u0634\u062a\u062a",                      # برداشتت
    "\u0628\u0631\u062f\u0627\u0634\u062a \u0634\u0645\u0627",         # برداشت شما
    "\u062f\u0627\u0646\u0633\u062a\u0647 \u0641\u0639\u0644\u06cc",  # دانسته فعلی
    "\u062f\u0627\u0646\u0634 \u0641\u0639\u0644\u06cc",               # دانش فعلی
    "\u0627\u0637\u0644\u0627\u0639\u0627\u062a \u0641\u0639\u0644\u06cc",  # اطلاعات فعلی
    "\u062f\u0631\u06a9 \u0641\u0639\u0644\u06cc",                     # درک فعلی
    "\u0641\u0647\u0645 \u0641\u0639\u0644\u06cc",                     # فهم فعلی
    "\u0634\u0646\u0627\u062e\u062a \u0641\u0639\u0644\u06cc",         # شناخت فعلی
    "current understanding",
    "current knowledge",
)

# 2. An explicit "what do you know" probe.
KNOWLEDGE_PROBE_PHRASES = (
    "\u0686\u0647 \u0645\u06cc \u062f\u0627\u0646\u06cc",            # چه می دانی
    "\u0686\u06cc \u0645\u06cc \u062f\u0627\u0646\u06cc",            # چی می دانی
    "\u0686\u0642\u062f\u0631 \u0645\u06cc \u062f\u0627\u0646\u06cc",  # چقدر می دانی
    "\u0686\u0647 \u0627\u0637\u0644\u0627\u0639\u0627\u062a\u06cc \u062f\u0627\u0631\u06cc",  # چه اطلاعاتی داری
    "\u0686\u0647 \u0686\u06cc\u0632\u0647\u0627\u06cc\u06cc \u0645\u06cc \u062f\u0627\u0646\u06cc",  # چه چیزهایی می دانی
    "what do you know",
    # TEACHING_CONTEXT_01 — must be QUALIFIED. The bare
    # "what do you understand" is already a Phase 08 UNDERSTANDING_VERB
    # and drives the teach-back (CONFIRMATION_REQUEST) contract; adding
    # it unqualified here stole that turn. "…about <topic>" is the
    # knowledge-reflection form and keeps both contracts intact.
    "what do you understand about",
)

# 3. "چه چیزهایی ... می دانی" with intervening words
#    ("چه چیزهایی درباره آن می دانی؟"). Both parts are required.
KNOWLEDGE_PROBE_OPENERS = (
    "\u0686\u0647 \u0686\u06cc\u0632\u0647\u0627\u06cc\u06cc",  # چه چیزهایی
    "\u0686\u0647 \u0645\u0648\u0627\u0631\u062f\u06cc",        # چه مواردی
)

KNOWLEDGE_PROBE_VERBS = (
    "\u0645\u06cc \u062f\u0627\u0646\u06cc",    # می دانی
    "\u0645\u06cc \u062f\u0627\u0646\u06cc\u062f",  # می دانید
)

# 4. An explicit pre-teaching baseline request
#    ("قبل از اینکه من چیزی آموزش بدهم ..."). Both parts are required.
PRE_TEACHING_BASELINE_MARKERS = (
    "\u0642\u0628\u0644 \u0627\u0632",  # قبل از
    "before i teach",
)

PRE_TEACHING_BASELINE_OBJECTS = (
    "\u0622\u0645\u0648\u0632\u0634",  # آموزش
    "\u062f\u0631\u0633",              # درس
    "\u062a\u062f\u0631\u06cc\u0633",  # تدریس
    "\u06cc\u0627\u062f \u0628\u062f\u0647\u0645",  # یاد بدهم
)


def is_knowledge_reflection(form):

    """True when the turn asks what the assistant ALREADY knows.

    Read-only. Two-part tests are used so a stray single word cannot
    capture an ordinary statement or an ordinary question.
    """

    form = form or ""

    if any(marker in form for marker in KNOWLEDGE_REFLECTION_TOPIC_MARKERS):

        return True

    if any(marker in form for marker in KNOWLEDGE_PROBE_PHRASES):

        return True

    if (
        any(opener in form for opener in KNOWLEDGE_PROBE_OPENERS)
        and any(verb in form for verb in KNOWLEDGE_PROBE_VERBS)
    ):

        return True

    if (
        any(
            marker in form
            for marker in PRE_TEACHING_BASELINE_MARKERS
        )
        and any(
            obj in form
            for obj in PRE_TEACHING_BASELINE_OBJECTS
        )
    ):

        return True

    return False


# The six aspects offered by the elicitation (brief-defined vocabulary).
TEACHING_ASPECTS = (
    ("stair_types", "انواع پله", "stair types"),
    ("dimensions", "تناسبات و ابعاد", "proportions and dimensions"),
    ("drawing", "ترسیم", "drawing"),
    ("floor_connection", "ارتباط با طبقات", "connection to floors"),
    ("regulations", "ضوابط", "regulations"),
    ("design_application", "کاربرد در طراحی", "application in design"),
)


def teaching_aspects(language="fa"):

    index = 1 if str(language or "").startswith("fa") else 2

    return [
        {"key": item[0], "label": item[index]}
        for item in TEACHING_ASPECTS
    ]


# --- greeting / small talk -------------------------------------------

GREETING_TOKENS = frozenset(
    (
        # Persian
        "\u0633\u0644\u0627\u0645",          # سلام
        "\u062f\u0631\u0648\u062f",          # درود
        "\u0645\u0645\u0646\u0648\u0646",    # ممنون
        "\u0645\u0631\u0633\u06cc",          # مرسی
        "\u0633\u067e\u0627\u0633",          # سپاس
        "\u062e\u0633\u062a\u0647",          # خسته
        "\u0686\u0637\u0648\u0631\u06cc",    # چطوری
        # English
        "hi", "hello", "hey", "yo", "greetings",
        "thanks", "thank", "cheers",
    )
)


# --- Persian imperative verb detection -------------------------------

# Words that start with 'ب' but are NOT imperative verbs.
_NON_IMPERATIVE_B_WORDS = frozenset(
    (
        "\u0628\u0627\u06cc\u062f",        # باید
        "\u0628\u0627\u06cc\u0633\u062a\u06cc",  # بایستی
        "\u0628\u0647\u062a\u0631",        # بهتر
        "\u0628\u0647\u062a\u0631\u0647",  # بهتره
        "\u0628\u0633\u06cc\u0627\u0631",  # بسیار
        "\u0628\u0639\u062f",              # بعد
        "\u0628\u0631\u0627\u06cc",        # برای
        "\u0628\u062f\u0648\u0646",        # بدون
        "\u0628\u0639\u0636\u06cc",        # بعضی
        "\u0628\u0627\u0644\u0627",        # بالا
        "\u0628\u0627\u0644\u0627\u062a\u0631",  # بالاتر
        "\u0628\u06cc\u0646",              # بین
        "\u0628\u0644\u0647",              # بله
        "\u0628\u0644\u06cc",              # بلی
        "\u0628\u0644\u06a9\u0647",        # بلکه
        "\u0628\u0631",                    # بر
        "\u0628\u0627\u0632",              # باز
        "\u0628\u06cc\u0634",              # بیش
        "\u0628\u06cc\u0634\u062a\u0631",  # بیشتر
        "\u0628\u062f",                    # بد
        "\u0628\u0644\u0646\u062f",        # بلند
        "\u0628\u062e\u0634\u06cc",        # بخشی
        "\u0628\u0631\u062e\u06cc",        # برخی
        "\u0628\u0646\u0638\u0631",        # بنظر
        "\u0628\u0631\u0627\u0633\u0627\u0633",  # براساس
        "\u0628\u0627\u0628\u062a",        # بابت
        "\u0628\u0627\u0644\u0627\u062e\u0631\u0647",  # بالاخره
        # "to be" forms — subjunctive/indicative, NOT imperative verbs
        "\u0628\u0627\u0634\u0647",        # باشه
        "\u0628\u0627\u0634\u062f",        # باشد
        "\u0628\u0627\u0634\u0645",        # باشم
        "\u0628\u0627\u0634\u06cc",        # باشی
        "\u0628\u0627\u0634\u06cc\u0645",  # باشیم
        "\u0628\u0627\u0634\u0646\u062f",  # باشند
        "\u0628\u0634\u0647",              # بشه
        "\u0628\u0634\u0648\u062f",        # بشود
        "\u0628\u0648\u062f\u0646",        # بودن
        "\u0628\u0648\u062f",              # بود
        "\u0628\u0627\u0634",              # باش
    )
)


# Suffixes that mark subjunctive / indicative "to be" forms rather than
# an imperative verb.
_PERSIAN_NON_IMPERATIVE_SUFFIXES = (
    "\u0627\u0634\u0647",        # اشه
    "\u0627\u0634\u062f",        # اشد
    "\u0627\u0634\u0645",        # اشم
    "\u0627\u0634\u06cc",        # اشی
    "\u0627\u0634\u06cc\u0645",  # اشیم
    "\u0627\u0634\u0646\u062f",  # اشند
)


# Explicit common imperative forms.  PHASE 09 — this lexicon (plus the
# compound-verb morphology below) is now the PRIMARY evidence for a
# Persian imperative.  The old blanket "'ب' prefix means imperative"
# heuristic has been REMOVED: it classified ordinary architectural nouns
# (بام، باغ، بنا، بلوک، برنامه، بهینه، بیرونی ...) as instructions and
# silently dropped real teaching statements.
_PERSIAN_IMPERATIVE_EXACT = frozenset(
    (
        "\u0628\u06a9\u0634",        # بکش
        "\u0628\u0633\u0627\u0632",  # بساز
        "\u0628\u0628\u0631",        # ببر
        "\u0628\u06cc\u0627\u0631",  # بیار
        "\u0628\u06cc\u0627\u0648\u0631",  # بیاور
        "\u0628\u062f\u0647",        # بده
        "\u0628\u06af\u06cc\u0631",  # بگیر
        "\u0628\u06af\u0648",        # بگو
        "\u0628\u0631\u0648",        # برو
        "\u0628\u06cc\u0627",        # بیا
        "\u0628\u0632\u0646",        # بزن
        "\u0628\u0630\u0627\u0631",  # بذار
        "\u0628\u06af\u0630\u0627\u0631",  # بگذار
        "\u0628\u0628\u06cc\u0646",  # ببین
        "\u0628\u0646\u0648\u06cc\u0633",  # بنویس
        "\u0628\u0641\u0631\u0633\u062a",  # بفرست
        "\u0628\u0631\u062f\u0627\u0631",  # بردار
        "\u0628\u0646\u062f\u0627\u0632",  # بنداز
        "\u0628\u06cc\u0646\u062f\u0627\u0632",  # بینداز
        "\u0628\u0686\u06cc\u0646",  # بچین
        "\u0628\u0634\u06a9\u0646",  # بشکن
        "\u0628\u06a9\u0646",        # بکن
        "\u0628\u0628\u0646\u062f",  # ببند
        "\u0628\u06af\u0631\u062f\u0627\u0646",  # بگردان
        "\u0628\u0686\u0631\u062e\u0627\u0646",  # بچرخان
        "\u0628\u0686\u0631\u062e\u0648\u0646",  # بچرخون
        "\u0628\u062a\u0631\u0627\u0634",  # بتراش
        "\u0628\u0631\u06cc\u0632",  # بریز
        "\u0628\u0633\u0646\u062c",  # بسنج
        "\u0628\u0645\u0627\u0646",  # بمان
        "\u0628\u062a\u0627\u0628",  # بتاب
        "\u0628\u067e\u06cc\u0686",  # بپیچ
        "\u0628\u0628\u0627\u0641",  # بباف
        "\u0628\u0645\u0627\u0644",  # بمال
        "\u0628\u0633\u0627\u0628",  # بساب
        "\u0628\u0634\u0648\u06cc",  # بشوی
        "\u0628\u06a9\u0648\u0628",  # بکوب
        "\u0628\u0633\u0648\u0632",  # بسوز
        "\u0628\u067e\u0632",        # بپز
        "\u0628\u067e\u0648\u0634",  # بپوش
        "\u0628\u067e\u0631\u0633",  # بپرس
        "\u0628\u0646\u0634\u0648\u0646",  # بنشون
        "\u0628\u0646\u0645\u0627",  # بنما
        "\u0628\u0632\u062f\u0627",  # بزدا
        "\u0628\u062e\u0634\u06a9",  # بخشک
        "\u0628\u0648\u0631\u0632",  # بورز
        "\u0646\u06a9\u0646",        # نکن
        "\u06a9\u0646",              # کن
        "\u06a9\u0646\u06cc\u062f",  # کنید
        "\u0628\u062f\u06cc\u062f",  # بدید
        "\u0628\u062f\u0647\u06cc\u062f",  # بدهید
        "\u0628\u0633\u0627\u0632\u06cc\u062f",  # بسازید
        "\u0628\u06a9\u0634\u06cc\u062f",  # بکشید
        "\u0628\u0628\u0631\u06cc\u062f",  # ببرید
        "\u062a\u063a\u06cc\u06cc\u0631 \u0628\u062f\u0647",  # تغییر بده
        "\u0627\u0636\u0627\u0641\u0647 \u06a9\u0646",  # اضافه کن
        "\u062d\u0630\u0641 \u06a9\u0646",  # حذف کن
    )
)


# PHASE 09 — REAL imperative evidence: the present stem of the verb.
# A token is treated as an imperative only when it is 'ب' + a KNOWN stem
# (or a known compound form).  Nouns that merely start with 'ب' can no
# longer masquerade as instructions.
PERSIAN_VERB_STEMS = frozenset(
    (
        "\u06a9\u0634",        # کش   -> بکش
        "\u0633\u0627\u0632",  # ساز  -> بساز
        "\u0628\u0631",        # بر   -> ببر
        "\u0622\u0648\u0631",  # آور  -> بیاور
        "\u062f\u0647",        # ده   -> بده
        "\u062f",              # د    -> بد (blocklisted as a bare token)
        "\u06af\u06cc\u0631",  # گیر  -> بگیر
        "\u06af\u0648",        # گو   -> بگو
        "\u06af\u0648\u06cc",  # گوی  -> بگوی
        "\u0631\u0648",        # رو   -> برو
        "\u0632\u0646",        # زن   -> بزن
        "\u06af\u0630\u0627\u0631",  # گذار -> بگذار
        "\u0686\u0631\u062e\u0627\u0646",  # چرخان
        "\u0686\u0631\u062e\u0648\u0646",  # چرخون
        "\u06af\u0631\u062f\u0627\u0646",  # گردان
        "\u0646\u0648\u06cc\u0633",  # نویس
        "\u0641\u0631\u0633\u062a",  # فرست
        "\u067e\u0648\u0634",  # پوش
        "\u067e\u0631\u0633",  # پرس
        "\u0645\u0627\u0646",  # مان  -> بمان
        "\u0645\u0648\u0646",  # مون  -> بمون
        "\u0646\u0634\u0648\u0646",  # نشون
        "\u0646\u0645\u0627",  # نما  -> بنما
        "\u0633\u0646\u062c",  # سنج
        "\u0686\u06cc\u0646",  # چین
        "\u0631\u06cc\u0632",  # ریز
        "\u062a\u0631\u0627\u0634",  # تراش
        "\u06a9\u0627\u0648",  # کاو
        "\u0634\u06a9\u0646",  # شکن
        "\u0627\u0646\u062f\u0627\u0632",  # انداز
        "\u0628\u0646\u062f",  # بند  -> ببند
        "\u0633\u0648\u0632",  # سوز
        "\u067e\u0632",        # پز
        "\u0645\u0627\u0644",  # مال
        "\u0633\u0627\u0628",  # ساب
        "\u06a9\u0648\u0628",  # کوب
        "\u0628\u0627\u0641",  # باف
        "\u067e\u06cc\u0686",  # پیچ
        "\u062a\u0627\u0628",  # تاب
        "\u0634\u0648\u06cc",  # شوی
        "\u062e\u0634\u06a9",  # خشک
        "\u0632\u062f\u0627",  # زدا
        "\u0648\u0631\u0632",  # ورز
    )
)


# Compound-verb suffixes that mark an imperative/directive verb.
_PERSIAN_IMPERATIVE_SUFFIXES = (
    "\u06a9\u0646",        # کن
    "\u06a9\u0646\u06cc\u062f",  # کنید
    "\u0628\u062f\u0647",  # بده
    "\u0628\u062f\u06cc\u062f",  # بدید
    "\u0628\u062f\u0647\u06cc\u062f",  # بدهید
    "\u0628\u0633\u0627\u0632",  # بساز
)


# PHASE 09 — heads of Persian COMPOUND verbs (noun/adjective + کن/بده ...).
# The suffix alone is NOT evidence: nouns such as بالکن (balcony) and
# مسکن (housing) end in "کن".  A joined compound form is only accepted
# when its head is a known compound-verb element.
PERSIAN_COMPOUND_VERB_HEADS = frozenset(
    (
        "\u062a\u063a\u06cc\u06cc\u0631",  # تغییر
        "\u0627\u0636\u0627\u0641\u0647",  # اضافه
        "\u062d\u0630\u0641",        # حذف
        "\u0631\u0633\u0645",        # رسم
        "\u0627\u062f\u0627\u0645\u0647",  # ادامه
        "\u062a\u0648\u0636\u06cc\u062d",  # توضیح
        "\u062f\u0631\u0633\u062a",  # درست
        "\u0628\u0631\u0631\u0633\u06cc",  # بررسی
        "\u062a\u062d\u0644\u06cc\u0644",  # تحلیل
        "\u062e\u0644\u0627\u0635\u0647",  # خلاصه
        "\u062a\u0628\u062f\u06cc\u0644",  # تبدیل
        "\u0627\u0646\u062a\u062e\u0627\u0628",  # انتخاب
        "\u0645\u0631\u062a\u0628",  # مرتب
        "\u0627\u062c\u0631\u0627",  # اجرا
        "\u0627\u0635\u0644\u0627\u062d",  # اصلاح
        "\u062a\u06a9\u0645\u06cc\u0644",  # تکمیل
        "\u062a\u0646\u0637\u06cc\u0645",  # تنظیم
        "\u062c\u0627\u0628\u0647\u200c\u062c\u0627",  # جابه‌جا
        "\u0634\u0631\u0648\u0639",  # شروع
        "\u067e\u0627\u06cc\u0627\u0646",  # پایان
        "\u067e\u0627\u06a9",        # پاک
        "\u0628\u0627\u0632",        # باز
        "\u0628\u0633\u062a",        # بست
        "\u0630\u062e\u06cc\u0631\u0647",  # ذخیره
        "\u062e\u0631\u0648\u062c\u06cc",  # خروجی
        "\u062a\u0631\u062c\u0645\u0647",  # ترجمه
        "\u0637\u0631\u0627\u062d\u06cc",  # طراحی
        "\u0633\u0627\u062e\u062a",  # ساخت
        "\u0645\u062d\u0627\u0633\u0628\u0647",  # محاسبه
        "\u0627\u0631\u0632\u06cc\u0627\u0628\u06cc",  # ارزیابی
        "\u0645\u0642\u0627\u06cc\u0633\u0647",  # مقایسه
        "\u062a\u0642\u0633\u06cc\u0645",  # تقسیم
        "\u062a\u0631\u06a9\u06cc\u0628",  # ترکیب
        "\u0627\u062f\u063a\u0627\u0645",  # ادغام
        "\u0627\u0646\u062a\u0642\u0627\u0644",  # انتقال
        "\u06a9\u067e\u06cc",        # کپی
        "\u062c\u0633\u062a\u062c\u0648",  # جستجو
        "\u0646\u0645\u0627\u06cc\u0634",  # نمایش
        "\u067e\u0646\u0647\u0627\u0646",  # پنهان
        "\u0641\u0639\u0627\u0644",  # فعال
        "\u062a\u0639\u0631\u06cc\u0641",  # تعریف
        "\u062a\u0634\u062e\u06cc\u0635",  # تشخیص
        "\u0645\u0634\u062e\u0635",  # مشخص
        "\u0637\u0628\u0642\u0647\u200c\u0628\u0646\u062f\u06cc",  # طبقه‌بندی
        "\u06af\u0631\u0648\u0647\u200c\u0628\u0646\u062f\u06cc",  # گروه‌بندی
        "\u0645\u0642\u06cc\u0627\u0633",  # مقیاس
        "\u0686\u0631\u062e\u0634",  # چرخش
        "\u0622\u06cc\u0646\u0647",  # آینه
        "\u062a\u06a9\u0631\u0627\u0631",  # تکرار
        "\u0631\u0646\u062f\u0631",  # رندر
        "\u067e\u0644\u0627\u0646",  # پلان
        "\u0646\u0642\u0634\u0647",  # نقشه
        "\u062c\u062f\u0648\u0644",  # جدول
        "\u0646\u0645\u0648\u062f\u0627\u0631",  # نمودار
        "\u06af\u0632\u0627\u0631\u0634",  # گزارش
        "\u0644\u0627\u06cc\u0647",  # لایه
        "\u0628\u0644\u0648\u06a9",  # بلوک
        "\u0645\u062f\u0644",        # مدل
        "\u0637\u0631\u062d",        # طرح
        "\u067e\u06cc\u0634\u0646\u0647\u0627\u062f",  # پیشنهاد
        "\u062d\u0627\u0644\u062a",  # حالت
        "\u062d\u062c\u0645",        # حجم
        "\u0645\u062a\u0631\u06cc\u0627\u0644",  # متریال
        "\u0645\u0635\u0627\u0644\u062d",  # مصالح
        "\u0631\u0646\u06af",        # رنگ
        "\u0628\u0627\u0641\u062a",  # بافت
        "\u0627\u0631\u062a\u0641\u0627\u0639",  # ارتفاع
        "\u0639\u0631\u0636",        # عرض
        "\u0637\u0648\u0644",        # طول
        "\u0639\u0645\u0642",        # عمق
        "\u0641\u0627\u0635\u0644\u0647",  # فاصله
        "\u0627\u0646\u062f\u0627\u0632\u0647",  # اندازه
        "\u0627\u0628\u0639\u0627\u062f",  # ابعاد
        "\u0645\u0633\u0627\u062d\u062a",  # مساحت
        "\u0638\u0631\u0641\u06cc\u062a",  # ظرفیت
        "\u062a\u0639\u062f\u0627\u062f",  # تعداد
        "\u0645\u0642\u062f\u0627\u0631",  # مقدار
        "\u062f\u0631\u0635\u062f",  # درصد
        "\u06a9\u0645",              # کم
        "\u0632\u06cc\u0627\u062f",  # زیاد
        "\u0628\u0644\u0646\u062f",  # بلند
        "\u067e\u0627\u06cc\u06cc\u0646",  # پایین
        "\u0628\u0627\u0644\u0627",  # بالا
        "\u062f\u0648\u0631",        # دور
        "\u0646\u0632\u062f\u06cc\u06a9",  # نزدیک
        "\u0686\u0631\u062e",        # چرخ
    )
)


# Indicative prefixes: 'می' / 'نمی' -> NOT imperative.
_PERSIAN_INDICATIVE_PREFIXES = (
    "\u0645\u06cc",        # می
    "\u0646\u0645\u06cc",  # نمی
)


def _is_persian_imperative_token(token):

    if not token:

        return False

    if token in _NON_IMPERATIVE_B_WORDS:

        return False

    for prefix in _PERSIAN_INDICATIVE_PREFIXES:

        if token.startswith(prefix):

            return False

    # 3rd person plural / plural indicative endings are not imperative
    if token.endswith("\u0646\u062f"):  # ند

        return False

    for suffix in _PERSIAN_NON_IMPERATIVE_SUFFIXES:

        if token.endswith(suffix):

            return False

    if token in _PERSIAN_IMPERATIVE_EXACT:

        return True

    # PHASE 09 — 'ب' + a KNOWN verb stem is real imperative evidence.
    # (The previous blanket 'ب' prefix rule was unsafe and has been
    # removed; it turned بام / باغ / بنا / بلوک / برنامه / بهینه /
    # بیرونی into "instructions".)
    if (
        token.startswith("\u0628")  # ب
        and len(token) >= 3
        and re.match(r"^[\u0600-\u06FF]+$", token)
        and token[1:] in PERSIAN_VERB_STEMS
    ):

        return True

    # compound verb: <head>کن / <head>کنید / <head>بده ...
    #
    # PHASE 09 — the suffix ALONE is not evidence. Nouns such as بالکن
    # (balcony) and مسکن (housing) end in "کن", so a joined compound
    # form is only accepted when its head is a known compound-verb
    # element.
    if len(token) >= 4:

        for suffix in _PERSIAN_IMPERATIVE_SUFFIXES:

            if token.endswith(suffix) and len(token) > len(suffix):

                head = token[: -len(suffix)]

                if head in PERSIAN_COMPOUND_VERB_HEADS:

                    return True

    return False


# --- English imperative detection ------------------------------------

ENGLISH_ACTION_VERBS = frozenset(
    (
        "draw", "make", "create", "build", "render", "generate",
        "add", "remove", "delete", "change", "modify", "move",
        "shift", "rotate", "scale", "resize", "replace", "show",
        "give", "explain", "summarize", "summarise", "describe",
        "list", "write", "design", "place", "put", "set", "turn",
        "convert", "translate", "analyze", "analyse", "check",
        "verify", "open", "close", "save", "export", "import",
        "continue", "stop", "use", "apply", "keep", "preserve",
        "extend", "expand", "shrink", "increase", "decrease",
        "shorten", "lengthen", "start", "reduce", "improve",
        "adjust", "attach", "insert", "duplicate", "arrange",
        "sketch", "plot", "compute", "calculate", "optimize",
        "optimise", "fill", "empty", "align", "mirror",
    )
)


_ENGLISH_POLITE_PREFIXES = (
    "please", "now", "then", "also", "just", "could", "can",
    "would", "will", "kindly", "go", "ahead",
)


def _is_english_imperative(tokens):

    for token in tokens:

        if token in _ENGLISH_POLITE_PREFIXES:

            continue

        return token in ENGLISH_ACTION_VERBS

    return False


# ----------------------------------------------------------
# FEATURE EXTRACTION
# ----------------------------------------------------------

def extract_features(text, language=None):

    """Deterministic, provider-free feature extraction."""

    raw = str(text or "")

    form = match_form(raw)

    tokens = [t for t in form.split(" ") if t]

    token_set = set(tokens)

    question_mark = has_question_mark(raw)

    script = script_of(raw)

    interrogative = bool(token_set & INTERROGATIVE_TOKENS)

    understanding = any(
        stem in token
        for token in tokens
        for stem in UNDERSTANDING_STEMS
    )

    recall_phrase = any(marker in form for marker in RECALL_MARKERS)

    negation = bool(token_set & NEGATION_TOKENS)

    error = bool(token_set & ERROR_TOKENS)

    correction_lexical = bool(
        error or (negation and bool(token_set & CORRECTNESS_TOKENS))
    )

    normative = bool(token_set & NORMATIVE_TOKENS)

    definitional = bool(token_set & DEFINITIONAL_TOKENS)

    # PHASE 09 — Persian copular definition ("... است" / "... هست")
    copula_definition = bool(
        tokens
        and len(tokens) >= MIN_COPULA_DEFINITION_TOKENS
        and tokens[-1] in PERSIAN_COPULA_TOKENS
    )

    definitional = definitional or copula_definition

    # CORRECTION_LOOP_01 — a denial that carries no error word.
    # See DISAGREEMENT_OPENERS: opener + statement length + a copula.
    disagreement_opener = bool(
        tokens
        and tokens[0] in DISAGREEMENT_OPENERS
        and len(tokens) >= MIN_DISAGREEMENT_TOKENS
        and any(
            token in PERSIAN_COPULA_TOKENS
            or token in DISAGREEMENT_COPULA_TOKENS
            for token in tokens
        )
    )

    # ---- curriculum foundation fix ----
    #
    # A customary statement ("معمولاً ...") and a project decision
    # ("در این پروژه تصمیم گرفتیم ...") are teaching statements even
    # though neither is normative nor definitional. Without these two
    # features such a turn was classified NORMAL_CONVERSATION, so no
    # candidate was ever built and the knowledge ladder never ran.
    pattern_marker = contains_any(form, PATTERN_MARKERS)

    decision_marker = contains_any(form, DECISION_MARKERS)

    # A descriptive ZONE ASSIGNMENT is a teaching statement too. Without
    # this, "ورودی و نشیمن در منطقه عمومی قرار می گیرند" was
    # NORMAL_CONVERSATION and Part 4 (Zoning) could not be taught at all.
    zone_assignment = is_zone_assignment(form)

    # TEACHING_CONTEXT_01 — a conditional design allowance.
    conditional_allowance = is_conditional_allowance(form)

    greeting = bool(token_set & GREETING_TOKENS)

    persian_imperative = any(
        _is_persian_imperative_token(token) for token in tokens
    )

    english_imperative = _is_english_imperative(tokens)

    imperative = persian_imperative or english_imperative

    # ---- PHASE 09 — teaching intent ----
    teach_verb = any(marker in form for marker in TEACH_VERB_MARKERS)

    volition = any(marker in form for marker in VOLITION_MARKERS)

    addressee = any(marker in form for marker in ADDRESSEE_MARKERS)

    # TEACHING CONTENT CAPTURE V1 — the USER -> ARCHITECTOS transfer
    # STRUCTURE, independent of the word "آموزشی". Three shapes:
    #   * the speaker OWNS knowledge         ("یه نکته آموزشی دارم")
    #   * an assistant-directed learn verb   ("این رو یاد بگیر، ...")
    #   * the assistant is the addressee and a teaching verb is present
    #     ("بهت یاد بدم ...")
    # The direction guards (resource nouns, learner markers) live in the
    # helpers, so no keyword alone can ever promote a turn.
    knowledge_possession_offer = is_knowledge_possession_offer(
        form, token_set
    )

    teaching_imperative_to_assistant = (
        is_teaching_imperative_to_assistant(form)
    )

    teaching_addressee_transfer = is_teaching_addressee_transfer(
        form, token_set, teach_verb
    )

    teaching_transfer_to_assistant = bool(
        knowledge_possession_offer
        or teaching_imperative_to_assistant
        or teaching_addressee_transfer
    )

    # A request form of the teaching verb is enough on its own
    # ("راه پله را به من یاد بده" / "teach me about stairs").
    teach_request = (
        "\u06cc\u0627\u062f \u0628\u062f\u0647" in form   # یاد بده
        or "\u06cc\u0627\u062f\u0645 \u0628\u062f\u0647" in form  # یادم بده
        or "\u0622\u0645\u0648\u0632\u0634 \u0628\u062f\u0647" in form  # آموزش بده
        or "teach me" in form
    )

    teaching_intent = bool(
        teach_verb and (volition or addressee or teach_request)
    ) or teaching_transfer_to_assistant

    # TEACHING SESSION STATE FIX — read-only knowledge reflection.
    # Checked independently of teaching_intent because a message can
    # carry BOTH ("می خواهم درس را شروع کنم ... بگو برداشت فعلی تو
    # چیست؟"). The reflection wins: the user is asking for a baseline,
    # not teaching yet.
    knowledge_reflection = is_knowledge_reflection(form)

    teaching_intent_direction = None

    if teaching_intent:

        offer_markers = (
            addressee
            or "\u06cc\u0627\u062f \u0628\u062f\u0647\u0645" in form   # یاد بدهم
            or "\u06cc\u0627\u062f \u0628\u062f\u0647\u06cc" in form   # یاد بدهی
            or "\u06cc\u0627\u062f \u0628\u062f\u0647\u06cc\u0645" in form  # یاد بدهیم
            # CHAT RUNTIME REGRESSION FIX — 1st-person offers. Without
            # these, "قراره من یادت بدم ..." was read as a teaching
            # REQUEST instead of the offer it plainly is.
            or "\u06cc\u0627\u062f\u062a \u0628\u062f\u0645" in form   # یادت بدم
            or "\u06cc\u0627\u062f \u0628\u062f\u0645" in form         # یاد بدم
            or "\u06cc\u0627\u062f\u062a \u0628\u062f\u0647\u0645" in form  # یادت بدهم
            or "\u06cc\u0627\u062f\u062a\u0648\u0646 \u0628\u062f\u0645" in form  # یادتون بدم
            or "\u06cc\u0627\u062f \u0628\u062f\u06cc\u0645" in form   # یاد بدیم
            or "\u0622\u0645\u0648\u0632\u0634 \u0628\u062f\u0645" in form  # آموزش بدم
            or "\u062f\u0631\u0633 \u0628\u062f\u0645" in form         # درس بدم
            or "teach you" in form
        )

        teaching_intent_direction = (
            "user_offers_to_teach" if offer_markers
            else "user_requests_teaching"
        )

    # A question with no question mark is still a question when it both
    # opens with an interrogative and contains a question-like verb, or
    # when the interrogative word sits at the END ("... یعنی چی"), which
    # is a normal Persian question shape.
    interrogative_strong = (
        question_mark
        or (interrogative and _starts_interrogative(tokens))
        or (interrogative and _ends_interrogative(tokens))
        or (interrogative and understanding)
    )

    return {

        "contract": CONTRACT + ".Features",
        "version": VERSION,

        "raw_text": raw,
        "match_form": form,
        "tokens": tokens,

        "language": language or _language_from_script(script),
        "script": script,

        "has_question_mark": question_mark,
        "interrogative": interrogative,
        "interrogative_strong": interrogative_strong,

        "understanding_verb": understanding,
        "recall_phrase": recall_phrase,

        "negation": negation,
        "error": error,
        "correction_lexical": correction_lexical,
        "disagreement_opener": disagreement_opener,

        "normative": normative,
        "definitional": definitional,
        "copula_definition": copula_definition,
        "pattern_marker": pattern_marker,
        "decision_marker": decision_marker,
        "zone_assignment": zone_assignment,
        # TEACHING_CONTEXT_01
        "conditional_allowance": conditional_allowance,
        "greeting": greeting,

        "imperative": imperative,
        "persian_imperative": persian_imperative,
        "english_imperative": english_imperative,

        # PHASE 09 — teaching intent
        "teach_verb": teach_verb,
        "volition": volition,
        "addressee": addressee,
        "teach_request": teach_request,
        "teaching_intent": teaching_intent,
        # TEACHING CONTENT CAPTURE V1 — USER -> ARCHITECTOS transfer
        "knowledge_possession_offer": knowledge_possession_offer,
        "teaching_imperative_to_assistant": (
            teaching_imperative_to_assistant
        ),
        "teaching_addressee_transfer": teaching_addressee_transfer,
        "teaching_transfer_to_assistant": teaching_transfer_to_assistant,
        # TEACHING SESSION STATE FIX
        "knowledge_reflection": knowledge_reflection,
        "teaching_intent_direction": teaching_intent_direction,
    }


def _starts_interrogative(tokens):

    if not tokens:

        return False

    return tokens[0] in INTERROGATIVE_TOKENS


def _ends_interrogative(tokens):

    if not tokens:

        return False

    return tokens[-1] in INTERROGATIVE_TOKENS


def _language_from_script(script):

    if script == "persian":

        return "fa"

    if script == "english":

        return "en"

    if script == "mixed":

        return "mixed"

    return "unknown"


# ----------------------------------------------------------
# CLASSIFIER
# ----------------------------------------------------------

class TurnSemanticsClassifierV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    # --------------------------------------------------
    # PRECEDENCE
    #
    # -1 KNOWLEDGE_REFLECTION  (TEACHING SESSION STATE FIX — read-only;
    #                          "what do you already know?" beats both
    #                          the teaching intent and teach-back)
    # 0 OFFER_TO_TEACH        (PHASE 09 — teaching intent)
    # 1 CONFIRMATION_REQUEST  (very specific: understanding verb + ask)
    # 2 CORRECTION            (negation/error about a previous statement)
    # 3 TEACHING_STATEMENT    (normative/definitional, NOT directive,
    #                          NOT interrogative)
    # 4 INSTRUCTION           (directive verb -> an ACTION)
    # 5 QUESTION              (interrogative)
    # 6 NORMAL_CONVERSATION   (greeting / small talk / other content)
    # 7 UNKNOWN               (empty)
    # --------------------------------------------------

    def classify(self, text, language=None, context=None):

        raw = str(text or "")

        if not raw.strip():

            return self._result(
                TURN_UNKNOWN,
                0.0,
                {"reason": "empty_text"},
                {},
            )

        features = extract_features(raw, language=language)

        # ---- -1 READ-ONLY KNOWLEDGE REFLECTION ----
        #
        # "برداشت فعلی تو از این فضا چیست؟" / "چه چیزهایی درباره آن
        # می دانی؟" asks the assistant to STATE WHAT IT ALREADY KNOWS.
        # The user is NOT teaching yet, so this must not enter the
        # elicitation flow, and it must not be answered from the
        # teaching-candidate store either.
        #
        # It is checked FIRST because a real message can carry both:
        #   "می خواهم اولین درس را شروع کنم. موضوع: اتاق خواب. قبل از
        #    اینکه آموزش بدهم، بگو برداشت فعلی تو چیست؟"
        if features["knowledge_reflection"]:

            return self._result(
                TURN_KNOWLEDGE_REFLECTION,
                0.8,
                {"reason": "knowledge_reflection_request"},
                features,
            )

        # ---- 0 TEACHING INTENT / OFFER_TO_TEACH (PHASE 09) ----
        #
        # An offer (or a request) to teach is NEVER an instruction and
        # must never reach EXECUTE.  It is answered by asking which
        # aspect is being taught.
        if features["teaching_intent"]:

            return self._result(
                TURN_OFFER_TO_TEACH,
                0.85,
                {"reason": "teaching_intent"},
                features,
            )

        # ---- 1 CONFIRMATION_REQUEST ----
        #
        # Either an explicit recall phrasing, or an understanding verb
        # combined with an actual request signal.  "متوجه شدم"
        # ("I understood") is a statement, so the bare understanding
        # verb is not enough on its own.
        if features["recall_phrase"]:

            return self._result(
                TURN_CONFIRMATION_REQUEST,
                0.9,
                {"reason": "recall_phrase"},
                features,
            )

        if features["understanding_verb"] and features["interrogative_strong"]:

            return self._result(
                TURN_CONFIRMATION_REQUEST,
                0.75,
                {"reason": "understanding_verb_and_question"},
                features,
            )

        # ---- 2 CORRECTION ----
        #
        # An error marker ("اشتباه" / "wrong" / ...) or an explicit
        # denial of correctness ("درست نیست" / "not correct").  A pure
        # question about correctness ("is this wrong?") stays a QUESTION.
        #
        # CORRECTION_LOOP_01 — a plain denial opener ("نه ... هست") counts
        # too. It is evidence only in the two-part form defined by
        # DISAGREEMENT_OPENERS, so a bare "نه" answer is unaffected.
        if (
            features["correction_lexical"]
            or features["disagreement_opener"]
        ) and (
            features["negation"] or not features["has_question_mark"]
        ):

            confidence = 0.6

            if features["negation"]:

                confidence = 0.85

            if features["error"]:

                confidence = max(confidence, 0.7)

            # A denial opener is a deliberate correction, not an aside.
            if features["disagreement_opener"]:

                confidence = max(confidence, 0.8)

            return self._result(
                TURN_CORRECTION,
                confidence,
                {"reason": "error_or_denial_marker"},
                features,
            )

        # ---- 3 TEACHING_STATEMENT ----
        #
        # Curriculum foundation fixes: a CUSTOMARY statement, a PROJECT
        # DECISION and a ZONE ASSIGNMENT are teaching statements too.
        # Requiring only normative/definitional made
        # "معمولاً ... است", "در این پروژه تصمیم گرفتیم ..." and
        # "ورودی و نشیمن در منطقه عمومی قرار می گیرند" fall through to
        # NORMAL_CONVERSATION, so no candidate was built.
        if (
            (
                features["normative"]
                or features["definitional"]
                or features["pattern_marker"]
                or features["decision_marker"]
                or features["zone_assignment"]
                # TEACHING_CONTEXT_01 — a conditional design allowance
                or features["conditional_allowance"]
            )
            and not features["imperative"]
            and not features["interrogative_strong"]
        ):

            confidence = 0.7

            if features["normative"] and features["definitional"]:

                confidence = 0.8

            return self._result(
                TURN_TEACHING_STATEMENT,
                confidence,
                {"reason": "normative_or_definitional_statement"},
                features,
            )

        # ---- 4 INSTRUCTION ----
        if features["imperative"] and not features["interrogative_strong"]:

            return self._result(
                TURN_INSTRUCTION,
                0.75,
                {"reason": "directive_verb"},
                features,
            )

        # ---- 5 QUESTION ----
        if features["interrogative_strong"]:

            return self._result(
                TURN_QUESTION,
                0.8,
                {"reason": "interrogative"},
                features,
            )

        # ---- 6 NORMAL_CONVERSATION ----
        if features["greeting"] or features["tokens"]:

            return self._result(
                TURN_NORMAL_CONVERSATION,
                0.5 if features["greeting"] else 0.4,
                {
                    "reason": (
                        "greeting"
                        if features["greeting"]
                        else "no_strong_signal"
                    )
                },
                features,
            )

        # ---- 7 UNKNOWN ----
        return self._result(
            TURN_UNKNOWN,
            0.0,
            {"reason": "no_features"},
            features,
        )

    # --------------------------------------------------

    def _result(self, turn_kind, confidence, meta, features):

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "turn_kind": turn_kind,

            "is_question": turn_kind == TURN_QUESTION,
            "is_instruction": turn_kind == TURN_INSTRUCTION,
            "is_correction": turn_kind == TURN_CORRECTION,
            "is_teaching_statement": (
                turn_kind == TURN_TEACHING_STATEMENT
            ),
            "is_confirmation_request": (
                turn_kind == TURN_CONFIRMATION_REQUEST
            ),
            "is_normal_conversation": (
                turn_kind == TURN_NORMAL_CONVERSATION
            ),

            # PHASE 09 — teaching intent
            "is_teaching_intent": turn_kind in TEACHING_INTENT_KINDS,
            "teaching_intent": turn_kind in TEACHING_INTENT_KINDS,
            "wants_elicitation": turn_kind in TEACHING_INTENT_KINDS,
            "teaching_intent_direction": (
                features or {}
            ).get("teaching_intent_direction"),

            # TEACHING SESSION STATE FIX — read-only reflection.
            "is_knowledge_reflection": (
                turn_kind in KNOWLEDGE_REFLECTION_KINDS
            ),
            "wants_knowledge_reflection": (
                turn_kind in KNOWLEDGE_REFLECTION_KINDS
            ),

            # Phase 08: a candidate turn is recorded, never learned.
            "may_produce_candidate": turn_kind in CANDIDATE_TURN_KINDS,
            "wants_teach_back": turn_kind in TEACH_BACK_TURN_KINDS,

            # An instruction is an ACTION request, never knowledge.
            "is_action_request": turn_kind == TURN_INSTRUCTION,

            "confidence": round(float(confidence), 3),

            "reason": meta.get("reason"),

            "language": (features or {}).get("language", "unknown"),

            "features": {
                key: value
                for key, value in (features or {}).items()
                if key not in ("raw_text", "match_form", "tokens")
            },

            "provider": "deterministic",
            "llm_used": False,
            "network_used": False,
        }


turn_semantics = TurnSemanticsClassifierV1()


def classify_turn(text, language=None, context=None):

    return turn_semantics.classify(
        text,
        language=language,
        context=context,
    )
