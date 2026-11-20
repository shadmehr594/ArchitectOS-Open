# ==========================================================
# ArchitectOS — CONVERSATION INTENT BOUNDARY V1
#
# ONE authoritative, auditable top-level intent decision, taken
# BEFORE any downstream flow (teaching / architecture / general).
#
# It answers exactly one question:
#
#     Is this turn ...
#        GENERAL_CONVERSATION
#        ARCHITECTURE_CONVERSATION
#        TEACHING
#
# It is NOT a domain classifier. `architecture` is a SUBJECT;
# `teaching` is a USER INTENT. The two are orthogonal:
#
#     "معماری مدرن چیه؟"      subject=architecture  intent=conversation
#                                 -> ARCHITECTURE_CONVERSATION
#     "این قانون رو یاد بگیر"  subject=(none)       intent=teach-to-assistant
#                                 -> TEACHING
#
# DESIGN
# ------
# * Deterministic. No LLM, no network.
# * Non-sticky: the decision is made from the CURRENT turn's own
#   signal. Prior turns may only RESOLVE ambiguity — they never
#   force the same mode.
# * Additive: it does not modify `turn_semantics_v1.classify_turn`
#   (the frozen per-turn classifier) nor `teaching_foundation_v1`.
#   It reuses their vocabularies as the single source of truth.
#
# The module NEVER invents content, NEVER rewrites text, and NEVER
# stores anything.
# ==========================================================


from __future__ import annotations

from core.chat.negation_scope_v1 import affirmed_hit, has_contrastive_negation


CONTRACT = "ConversationIntentBoundaryV1"
VERSION = "1.0"


# ---- the three top-level intents --------------------------

GENERAL_CONVERSATION = "GENERAL_CONVERSATION"

ARCHITECTURE_CONVERSATION = "ARCHITECTURE_CONVERSATION"

TEACHING = "TEACHING"


# ==========================================================
# SIGNAL VOCABULARY (match-form; ZWNJ folded to a space)
# ==========================================================

# ---- 1. SELF-INTRODUCTION ---------------------------------
#
# The user is asking the ASSISTANT to introduce itself / say its
# name / describe its abilities. These are PERSON-identity turns,
# never teaching and never architecture, regardless of session
# state or of any architecture word elsewhere in the sentence.
#
# `match_form` folds ZWNJ and strips the combining hamza, so the
# markers below are written in that folded form.
_SELF_REFERENCE = (
    "\u062e\u0648\u062f\u062a",              # خودت
    "\u062e\u0648\u062f \u062a\u0648",        # خود تو
    "\u062e\u0648\u062f\u062a\u0648\u0646",   # خودتون
    "\u062e\u0648\u062f \u0634\u0645\u0627",  # خود شما
    "\u062e\u0648\u062f\u0634\u0648\u0646",   # خودشون
)

# verbs/words that turn a self-reference into a self-introduction
_INTRO_VERBS = (
    "\u0645\u0639\u0631\u0641\u06cc",          # معرفی
    "\u0645\u0639\u0631\u0641\u06cc \u06a9\u0646",  # معرفی کن
    "\u062a\u0648\u0636\u06cc\u062d \u0628\u062f\u0647",  # توضیح بده
    "\u0628\u0647 \u0645\u0646 \u0628\u06af\u0648",  # به من بگو (about self handled below)
)

# "who / what are you", "your name", "what can you do"
_IDENTITY_TOPICS = (
    "\u0627\u0633\u0645\u062a",              # اسمت
    "\u0627\u0633\u0645 \u062a\u0648",        # اسم تو
    "\u0627\u0633\u0645 \u0634\u0645\u0627",  # اسم شما
    "\u0646\u0627\u0645\u062a",              # نامت
    "\u062a\u0648 \u06a9\u06cc \u0647\u0633\u062a\u06cc",    # تو کی هستی
    "\u0634\u0645\u0627 \u06a9\u06cc \u0647\u0633\u062a\u06cc\u062f",  # شما کی هستید
    "\u06a9\u06cc \u0647\u0633\u062a\u06cc",  # کی هستی
    "\u0686\u06cc\u0633\u062a\u06cc",         # چیستی
    "\u0686\u06a9\u0627\u0631\u0647\u0627\u06cc\u06cc",  # چکارهایی
    "\u0686\u06a9\u0627\u0631 \u0645\u06cc \u062a\u0648\u0646\u06cc",  # چکار می تونی
    "\u0686\u0647 \u06a9\u0627\u0631\u0647\u0627\u06cc\u06cc",  # چه کارهایی
    "\u0686\u06cc \u0645\u06cc \u062a\u0648\u0646\u06cc",  # چی می تونی
    "\u062f\u0631 \u062e\u0635\u0648\u0635 \u062e\u0648\u062f\u062a",  # در خصوص خودت
)

# English (whitespace-normalised lower case)
_IDENTITY_TOPICS_EN = (
    "who are you",
    "what are you",
    "your name",
    "introduce yourself",
    "tell me about yourself",
    "what can you do",
    "what are your abilities",
    "who am i talking",
)


# ---- 2. TEACHING-TO-ARCHITECTOS EVIDENCE ------------------
#
# The user is trying to TRANSFER KNOWLEDGE TO the assistant. This
# requires an explicit teaching-transfer signal. It is NEVER
# inferred from architecture vocabulary, a declarative sentence,
# a correction, or an opinion.
#
# Direction guard: "معماری رو بهم یاد بده" / "teach me" is the
# user ASKING to learn — that is NOT teaching-to-the-assistant.

# Persian: the user will do the teaching.
_TEACH_OFFER_PERSIAN = (
    "\u06cc\u0627\u062f\u062a \u0628\u062f\u0645",         # یادت بدم
    "\u06cc\u0627\u062f\u062a \u0628\u062f\u0647\u0645",   # یادت بدهم
    "\u06cc\u0627\u062f \u0628\u062f\u0645",               # یاد بدم
    "\u06cc\u0627\u062f \u0628\u062f\u0647\u0645",         # یاد بدهم
    "\u06cc\u0627\u062f \u0628\u062f\u06cc\u0645",         # یاد بدیم
    "\u06cc\u0627\u062f\u062a\u0648\u0646 \u0628\u062f\u0645",  # یادتون بدم
    "\u0622\u0645\u0648\u0632\u0634 \u0628\u062f\u0645",   # آموزش بدم
    "\u062f\u0631\u0633 \u0628\u062f\u0645",               # درس بدم
    "\u06cc\u0627\u062f \u0645\u06cc \u062f\u0645",        # یاد می دم (spaced)
    "\u06cc\u0627\u062f \u0645\u06cc\u062f\u0645",         # یاد میدم (contracted)
    "\u06cc\u0627\u062f \u0645\u06cc \u062f\u0647\u0645",  # یاد میدهم
    "\u06cc\u0627\u062f \u0645\u06cc \u062f\u0647\u06cc\u0645",  # یاد میدهیم
    "\u0622\u0645\u0648\u0632\u0634 \u0645\u06cc\u062f\u0645",  # آموزش میدم
    "\u0622\u0645\u0648\u0632\u0634 \u0645\u06cc \u062f\u0647\u0645",  # آموزش میدهم
)

# Persian: an imperative asking the ASSISTANT to learn / remember /
# add to knowledge — the addressee is the assistant.
_TEACH_IMPERATIVE_TO_ASSISTANT = (
    "\u06cc\u0627\u062f \u0628\u06af\u06cc\u0631",         # یاد بگیر
    "\u06cc\u0627\u062f\u062a \u0628\u0627\u0634\u0647",   # یادت باشه
    "\u06cc\u0627\u062f \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634",  # یاد داشته باش
    "\u06cc\u0627\u062f\u0645 \u0628\u0627\u0634\u0647",   # یادم باشه (self, not addressed) — guarded
    "\u06cc\u0627\u062f \u0628\u0633\u067e\u0627\u0631",   # یاد بسپار
    "\u062d\u0641\u0637 \u06a9\u0646",                     # حفظ کن
    "\u0628\u0647 \u062e\u0627\u0637\u0631 \u0628\u0633\u067e\u0627\u0631",  # به خاطر بسپار
    "\u0627\u0636\u0627\u0641\u0647 \u06a9\u0646",         # اضافه کن
)

# Persian: "add to your knowledge" — needs the addressee to be
# the assistant's knowledge.
_KNOWLEDGE_ADDRESSEE = (
    "\u062f\u0627\u0646\u0634\u062a",        # دانشت
    "\u062f\u0627\u0646\u0634 \u062a\u0648",  # دانش تو
    "\u062f\u0627\u0646\u0634 \u0634\u0645\u0627",  # دانش شما
    "\u062f\u0627\u0646\u0634\u062a\u0627\u062a",  # دانشت ات (variant)
    "\u062d\u0627\u0641\u0638\u0647 \u0627\u062a",  # حافظه ات
    "\u062d\u0627\u0641\u0638\u0647 \u062a\u0648",  # حافظه تو
)

# Persian: an explicit "I want to teach you" volition phrase.
_VOLITION_TEACH = (
    "\u0645\u06cc \u062e\u0648\u0627\u0645",   # می خوام
    "\u0645\u06cc\u062e\u0648\u0627\u0645",    # میخوام
    "\u0645\u06cc \u062e\u0648\u0627\u06cc\u0645",  # می خوایم
    "\u0645\u06cc\u062e\u0648\u0627\u06cc\u0645",     # میخوایم
    "\u0642\u0635\u062f \u062f\u0627\u0631\u0645",  # قصد دارم
    "\u0642\u0631\u0627\u0631\u0647",          # قراره
)

# Persian: the teaching verb itself (یاد دادن / آموزش / تعلیم).
_TEACH_VERB = (
    "\u06cc\u0627\u062f \u0628\u062f\u0647",  # یاد بده
    "\u06cc\u0627\u062f \u0628\u062f\u0645",  # یاد بدم
    "\u0622\u0645\u0648\u0632\u0634",         # آموزش
    "\u062a\u0639\u0644\u06cc\u0645",         # تعلیم
    "\u062f\u0631\u0633 \u0628\u062f\u0647",  # درس بده
    "\u0627\u0635\u0644",                     # اصل (rule) — only with teach context
)

# Persian: the addressee is the assistant ("to you").
_ADDRESSEE_ASSISTANT = (
    "\u0628\u0647\u062a",            # بهت
    "\u0628\u0647 \u062a\u0648",     # به تو
    "\u0628\u0631\u0627\u062a",      # برات
    "\u0628\u0631\u0627\u06cc\u062a",  # برایت
    "\u0628\u0647 \u0634\u0645\u0627",  # به شما
    "\u0628\u0631\u0627\u06cc \u0634\u0645\u0627",  # برای شما
)

# English teaching-transfer markers.
_TEACH_EN_OFFER = (
    "i'm going to teach you",
    "i am going to teach you",
    "i'll teach you",
    "i will teach you",
    "let me teach you",
    "i want to teach you",
    "i'd like to teach you",
    "i would like to teach you",
    "we will teach you",
    "we're going to teach you",
)

_TEACH_EN_IMPERATIVE = (
    "remember this",
    "remember that",
    "remember it",
    "keep this in mind",
    "keep that in mind",
    "note this",
    "note that",
    "learn this",
    "memorize this",
    "add this to your knowledge",
    "add it to your knowledge",
    "store this",
    "log this",
)

# English: "teach me" means the user wants to LEARN — the opposite
# direction. Guarded so it never becomes TEACHING.
_LEARN_REQUEST_EN = (
    "teach me",
    "explain to me",
    "tell me about",
)


# ==========================================================
# 2b. TEACHING_INTENT_TRIGGER_REPAIR_V1 — DIRECTION / TRANSFER GUARDS
#
# PROBLEM (audited): `_TEACH_VERB` contains the bare noun/adjective
# "آموزش" (and therefore also substring-matches "آموزشی"). Treating it
# as a teaching VERB makes the addressee rule fire on any sentence that
# merely MENTIONS something educational:
#
#   "یه کتاب آموزشی بهت معرفی کنم"      -> WRONGLY teaching
#   "میخوام یه ویدیوی آموزشی برات بفرستم" -> WRONGLY teaching
#
# but the user is offering a RESOURCE, not transferring knowledge.
#
# The truthful discriminator is the SAME one the brief states: detect
# the DIRECTION OF TRANSFER, not a keyword. Knowledge transfer needs a
# give/tell verb aimed at the assistant ("بهت بگم" / "بهت بدم"); a
# resource mention needs a recommend/send verb about a thing.
#
# Both tables below are folded at match time, like every other Persian
# table here, so they work in either spelling.
# ==========================================================

# A verb that actually CARRIES knowledge to the addressee
# ("I tell you", "I give you"). This is the transfer direction.
_TRANSFER_VERB_TO_ASSISTANT = (
    "\u0628\u06af\u0645",                    # بگم (I tell)
    "\u0628\u06af\u0648\u06cc\u0645",        # بگویم
    "\u0628\u062f\u0645",                    # بدم (I give)
    "\u0628\u062f\u0647\u0645",              # بدهم
    "\u0628\u06af\u0648",                    # بگو (tell — imperative)
    "\u06cc\u0627\u062f \u0628\u062f\u0645", # یاد بدم
    "\u06cc\u0627\u062f\u062a \u0628\u062f\u0645",  # یادت بدم
    "\u0645\u06cc \u06af\u0645",             # می گم
    "\u0645\u06cc\u06af\u0645",              # میگم
    "\u062a\u0648\u0636\u06cc\u062d \u0645\u06cc \u062f\u0645",  # توضیح می دم
)

# A verb that offers a RESOURCE / reference rather than knowledge.
# Presence of one of these (and no transfer verb) keeps a mere
# "آموزشی <noun>" mention OUT of TEACHING.
_RESOURCE_VERB = (
    "\u0645\u0639\u0631\u0641\u06cc",        # معرفی (introduce/recommend)
    "\u0628\u0641\u0631\u0633\u062a",        # بفرست / بفرستم (send)
    "\u0627\u0631\u0633\u0627\u0644",        # ارسال
    "\u0644\u06cc\u0646\u06a9",              # لینک
    "\u062f\u0627\u0646\u0644\u0648\u062f",  # دانلود
)

# A NOUN that names a RESOURCE (a thing about a topic), not knowledge
# itself. "یه کتاب آموزشی بهت معرفی کنم" offers a thing; "یه نکته
# آموزشی بهت بگم" transfers knowledge.
_RESOURCE_NOUN = (
    "\u06a9\u062a\u0627\u0628",              # کتاب
    "\u0648\u06cc\u062f\u06cc\u0648",        # ویدیو / ویدیوی
    "\u0641\u06cc\u0644\u0645",              # فیلم
    "\u062f\u0648\u0631\u0647",              # دوره (course)
    "\u06a9\u0644\u0627\u0633",              # کلاس
    "\u0645\u0642\u0627\u0644\u0647",        # مقاله
    "\u067e\u0648\u062f\u06a9\u0627\u0633\u062a",  # پادکست
    "\u0633\u0627\u06cc\u062a",              # سایت
    "\u0644\u06cc\u0646\u06a9",              # لینک
)

# A NOUN that names KNOWLEDGE ITSELF (a rule / tip / principle).
_KNOWLEDGE_NOUN = (
    "\u0646\u06a9\u062a\u0647",              # نکته (tip)
    "\u0645\u0637\u0644\u0628",              # مطلب (point/matter)
    "\u0627\u0635\u0644",                    # اصل (principle)
    "\u0642\u0627\u0646\u0648\u0646",        # قانون (rule)
    "\u0642\u0627\u0639\u062f\u0647",        # قاعده (rule)
    "\u0631\u0627\u0647\u0646\u0645\u0627",  # راهنما
    "\u062a\u062c\u0631\u0628\u0647",        # تجربه (experience)
    "\u062f\u0631\u0633",                    # درس (lesson)
    "\u062f\u0627\u0646\u0634",              # دانش
)

# "I HAVE (something) for you" — a possession offer. With a knowledge
# noun and an assistant addressee this is plainly offering to teach,
# exactly like the brief's "این یه نکته آموزشی برای توئه".
_POSSESSION_OFFER = (
    "\u062f\u0627\u0631\u0645",              # دارم (I have)
    "\u062f\u0627\u0631\u06cc\u0645",        # داریم
    "\u0647\u0633\u062a",                    # هست (there is)
)

# TEACHING CONTENT CAPTURE V1 — a first-person "I HAVE" possession.
#
# The rule below additionally accepts a possession offer with NO spoken
# addressee ("یه نکته آموزشی دارم" — "I have a teaching note"). Only the
# explicit first-person forms count there: "هست" alone is too weak to
# carry the transfer direction without an addressee.
_POSSESSION_HAVE = (
    "\u062f\u0627\u0631\u0645",              # دارم
    "\u062f\u0627\u0631\u06cc\u0645",        # داریم
)


# ---- 3. USER-REQUESTS-TEACHING-FROM-ARCHITECTOS -----------
#
# "معماری رو بهم یاد بده" / "teach me about X" — the user is the
# LEARNER. This is ARCHITECTURE_CONVERSATION (if the subject is
# architecture) or GENERAL_CONVERSATION, NEVER TEACHING.
_LEARN_REQUEST_PERSIAN = (
    "\u06cc\u0627\u062f \u0628\u062f\u0647",   # یاد بده
    "\u06cc\u0627\u062f\u0645 \u0628\u062f\u0647",  # یادم بده
    "\u06cc\u0627\u062f \u0628\u062f\u06cc",   # یاد بدهی (guarded by بهم/به من)
    "\u0628\u0647\u0645 \u06cc\u0627\u062f",   # بهم یاد
    "\u0628\u0647 \u0645\u0646 \u06cc\u0627\u062f",  # به من یاد
    "\u0622\u0645\u0648\u0632\u0634 \u0628\u062f\u0647",  # آموزش بده
    "\u062a\u0648\u0636\u06cc\u062d \u0628\u062f\u0647",  # توضیح بده
    "\u0628\u0631\u0627\u0645 \u0628\u06af\u0648",  # برام بگو
)

# First-person learner markers (the user says they want to learn).
_LEARNER_FIRST_PERSON = (
    "\u0628\u0647\u0645",            # بهم (to me)
    "\u0628\u0647 \u0645\u0646",     # به من
    "\u0645\u06cc \u062e\u0648\u0627\u0645 \u06cc\u0627\u062f",  # می خوام یاد
    "\u0645\u06cc\u062e\u0648\u0627\u0645 \u06cc\u0627\u062f",    # میخوام یاد
)


# ---- 4. ARCHITECTURE SUBJECT -----------------------------
#
# Subject vocabulary. This decides SUBJECT ONLY — it never decides
# TEACHING. Reused (as a closed set) so the boundary stays
# deterministic and explainable.
_ARCHITECTURE_SUBJECT = (
    "\u0645\u0639\u0645\u0627\u0631\u06cc",           # معماری
    "\u067e\u0644\u0627\u0646",                       # پلان
    "\u062a\u0631\u0627\u062d",                       # طراحی
    "\u0633\u0627\u062e\u062a\u0645\u0627\u0646",     # ساختمان
    "\u0646\u0645\u0627",                             # نما
    "\u067e\u0631\u0648\u0698\u0647",                 # پروژه
    "\u0641\u0636\u0627",                             # فضا
    "\u0627\u062a\u0627\u0642",                       # اتاق
    "\u0627\u0634\u067e\u0632\u062e\u0627\u0646\u0647",  # آشپزخانه -> اشپزخانه (folded)
    "\u0627\u0634\u067e\u0632\u062e\u0648\u0646\u0647",  # آشپزخونه -> اشپزخونه (folded)
    "\u0646\u0634\u06cc\u0645\u0646",                 # نشیمن
    "\u067e\u0630\u06cc\u0631\u0627\u06cc\u06cc",     # پذیرایی
    "\u0646\u0648\u0631 \u0637\u0628\u06cc\u0639\u06cc",  # نور طبیعی
    "\u062f\u06cc\u0648\u0627\u0631",                 # دیوار
    "\u067e\u0646\u062c\u0631\u0647",                 # پنجره
    "\u0648\u0631\u0648\u062f\u06cc",                 # ورودی
    "\u062d\u06cc\u0627\u0637",                       # حیاط
    "\u0645\u0633\u0627\u062d\u062a",                 # مساحت
    "\u0645\u062a\u0631\u0627\u0698",                 # متراژ
    "\u0637\u0628\u0642\u0647",                       # طبقه
    "\u0633\u0627\u06cc\u0647",                       # سایه
    "\u0645\u0635\u0627\u0644\u062d",                 # مصالح
    "\u0645\u062f\u0631\u0646",                       # مدرن
    "\u0633\u0646\u062a\u06cc",                       # سنتی
    "\u062a\u0631\u0627\u0632\u0647",                 # تراز
    "\u062f\u0631\u0627\u06cc",                       # دری
)

_ARCHITECTURE_SUBJECT_EN = (
    "architecture",
    "architectural",
    "floor plan",
    "open floor plan",
    "open-plan",
    "design",
    "building",
    "facade",
    "façade",
    "plan",
    "layout",
    "space planning",
    "interior",
    "kitchen",
    "bedroom",
    "living room",
    "natural light",
    "daylight",
    "house",
    "villa",
    "structural",
    "materials",
    # KNOWLEDGE_RECOVERY_01 — "materials" above is matched as a substring
    # against the user's text, so a request that says only "material"
    # (singular) never matched it. The singular form and the facade
    # surface nouns are the vocabulary an architectural edit actually
    # uses, so they are added here. Matching is unchanged; only the
    # vocabulary grows. This is a SUBJECT decision only — it never
    # authorises a render (ImageIntentV1 owns that).
    "material",
    "wall",
    "walls",
    "cladding",
    "modern architecture",
)

# ---- 5. CONVERSATIONAL / NON-ARCHITECTURE SUBJECT ---------
#
# A topic that clearly belongs to general conversation. Used ONLY
# to keep architecture from being inferred when the user names a
# non-architectural topic (e.g. "بیا درباره آشپزی حرف بزنیم"
# when the intent is COOKING, not kitchen design).
_NON_ARCHITECTURE_TOPIC = (
    "\u0622\u0634\u067e\u0632\u06cc",                 # آشپزی (cooking)
    "\u063a\u0630\u0627",                             # غذا (food)
    "\u067e\u062e\u062a",                             # پخت
    "\u0641\u0648\u062a\u0628\u0627\u0644",           # فوتبال
    "\u0645\u0648\u0633\u06cc\u0642\u06cc",           # موسیقی
    "\u0633\u06cc\u0646\u0645\u0627",                 # سینما
    "\u0633\u0641\u0631",                             # سفر
    "\u0633\u0644\u0627\u0645\u062a",                 # سلامت
    "\u0648\u0631\u0632\u0634",                       # ورزش
    "\u0647\u0648\u0627",                             # هوا
)

_NON_ARCHITECTURE_TOPIC_EN = (
    "cooking",
    "food",
    "recipe",
    "football",
    "music",
    "movie",
    "travel",
    "weather",
    "health",
)

# ---- 6. CONVERSATION-REPAIR (NOT teaching) ---------------
#
# A correction / repair of the CURRENT exchange is conversation,
# never learning. These markers force GENERAL_CONVERSATION.
_REPAIR_MARKERS = (
    "\u0645\u0646\u0637\u0648\u0631\u0645 \u0627\u06cc\u0646 \u0646\u0628\u0648\u062f",  # منظورم این نبود
    "\u0646\u0647 \u0645\u0646\u0637\u0648\u0631\u0645",  # نه منظورم
    "\u0642\u0635\u062f\u0645 \u0627\u06cc\u0646 \u0646\u0628\u0648\u062f",  # قصد این نبود
    "\u0627\u0634\u062a\u0628\u0627\u0647 \u06a9\u0631\u062f\u0645",  # اشتباه کردم
    "\u0645\u0646\u0637\u0648\u0631\u0645 \u0631\u0648 \u062f\u0631\u0633\u062a",  # منظورم رو درست
    "\u0627\u06cc\u0646 \u0631\u0648 \u0642\u0628\u0648\u0644 \u0646\u062f\u0627\u0631\u0645",  # این رو قبول ندارم
    "\u0627\u0635\u0644\u0627\u062d\u0634 \u06a9\u0646",  # اصلاحش کن
    "\u062f\u0631\u0633\u062a\u0634 \u06a9\u0646",        # درستش کن
)

_REPAIR_MARKERS_EN = (
    "that's not what i meant",
    "thats not what i meant",
    "that is not what i meant",
    "i didn't mean that",
    "i did not mean that",
    "not what i meant",
    "you misunderstood",
    "i disagree",
    "that's wrong",
    "thats wrong",
    "fix it",
    "correct that",
)


# ==========================================================
# MATCH FORM
# ==========================================================

def _fold(text):
    """Persian match-fold: ZWNJ -> space, strip combining hamza.

    Deliberately a LOCAL copy of the same two folds `match_form`
    applies, so this boundary can normalise for SUBJECT detection
    without importing the frozen classifier. It performs no other
    transformation and invents nothing.
    """

    value = str(text or "")

    value = value.replace("\u200c", " ")   # ZWNJ -> space

    value = value.replace("\u0623", "\u0627")  # أ -> ا

    value = value.replace("\u0625", "\u0627")  # إ -> ا

    value = value.replace("\u0622", "\u0627")  # آ -> ا

    value = value.replace("\u0629", "\u0647")  # ة -> ه

    value = " ".join(value.split())

    return value.strip()


def _contains_any(haystack, needles):

    return any(needle in haystack for needle in needles)


# ==========================================================
# TEACHING_INTENT_TRIGGER_REPAIR_V1 — FOLD-NORMALISED MATCHING
#
# DEFECT (audited): matching runs on `_fold(text)` (which lowers
# آ/أ/إ -> ا and ة -> ه), but the vocabulary below is written in
# ORDINARY Persian spelling — several markers contain آ. A marker
# like "آموزش" can therefore NEVER match the folded text "اموزش",
# so those markers were silently dead. Measured dead markers:
#   _TEACH_OFFER_PERSIAN : "آموزش بدم", "آموزش میدم", "آموزش می دهم"
#   _TEACH_VERB          : "آموزش"
#   _LEARN_REQUEST_PERSIAN: "آموزش بده"
#   _NON_ARCHITECTURE_TOPIC: "آشپزی"
#
# The fix is deliberately NOT to hand-rewrite the vocabulary (which
# would drift again). Instead the marker itself is folded at match
# time, so the SAME table works whatever spelling it is written in.
# `_fold` is idempotent, so a marker already in folded form is
# unchanged. This is the smallest truthful repair: it makes the
# existing intent logic actually see the words it was written for.
# ==========================================================

def _fold_matches(haystack, needles):
    """`_contains_any` for the FOLDED haystack, folding each needle
    first. Use this for every Persian vocabulary table so a marker
    containing آ/أ/إ/ة still matches."""

    return any(_fold(needle) in haystack for needle in needles)


def _has_negated_subject(form, lower):
    """A subject word is present but the user NEGATED it.

    GENERAL_CONVERSATION_CORRECTION_V1 — "معمایی گفتم نه معماری" names the
    architecture subject only to reject it. The subject decision already
    ignores a negated marker; this helper reports that it happened, so the
    correction can be surfaced as `conversation_repair`.
    """

    present = (
        _fold_matches(form, _ARCHITECTURE_SUBJECT)
        or _contains_any(lower, _ARCHITECTURE_SUBJECT_EN)
    )

    if not present:

        return False

    affirmed = (
        affirmed_hit(
            form,
            tuple(_fold(marker) for marker in _ARCHITECTURE_SUBJECT),
        )
        or affirmed_hit(lower, _ARCHITECTURE_SUBJECT_EN)
    )

    return not affirmed


# Punctuation that ends a word in the raw text. `_fold` does NOT strip
# it, so the whole-word helper below has to.
_WORD_SEPARATORS = (
    ":", "\u060c", "\u061b", ";", ",", "-", "\u2014", "\u2013",
    ".", "!", "?", "\u061f", "\u2026", "\u00ab", "\u00bb",
    "\"", "'", "(", ")", "[", "]", "{", "}", "|", "/", "\\",
)


def _fold_word_matches(haystack, needles):
    """`_fold_matches` with WHOLE-WORD semantics.

    Used for the possession verbs, so a negated "ندارم" ("I do NOT have")
    or a longer word that merely CONTAINS the stem can never be read as
    possession.

    `_fold` folds the ZWNJ to a space but PRESERVES punctuation, so a
    separator such as the colon in "نکته آموزشی دارم: ..." would glue
    itself to the token. Punctuation is therefore turned into a space
    here, which is exactly what a word boundary means.
    """

    value = str(haystack or "")

    for separator in _WORD_SEPARATORS:

        value = value.replace(separator, " ")

    padded = " " + " ".join(value.split()) + " "

    return any(
        (" " + _fold(needle) + " ") in padded for needle in needles
    )


# ==========================================================
# THE BOUNDARY
# ==========================================================

class ConversationIntentBoundaryV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self):

        pass

    # ------------------------------------------------------
    # PUBLIC ENTRY
    # ------------------------------------------------------

    def classify(
        self,
        text,
        *,
        raw_text=None,
        interpreted_utterance=None,
        previous_intent=None,
        context=None,
        language=None,
    ):
        """Return the authoritative top-level intent decision.

        The decision is made from the CURRENT turn. `previous_intent`
        and `context` may only RESOLVE ambiguity — they never force
        the same mode.
        """

        raw = str(raw_text if raw_text is not None else text or "")

        # Use the interpreted utterance for UNDERSTANDING when the
        # voice layer supplied one; fall back to the raw transcript.
        working = str(
            interpreted_utterance
            if interpreted_utterance is not None
            else (text if text is not None else raw)
        )

        form = _fold(working)

        lower = form.lower()

        signals = []

        # ==================================================
        # DECISION 0 — CONVERSATION REPAIR (highest priority)
        #
        # A correction/repair of the current exchange is
        # conversation, never learning. Checked first, so a
        # repair turn can never be captured by a teaching
        # imperative elsewhere in the sentence.
        # ==================================================
        if (
            _fold_matches(form, _REPAIR_MARKERS)
            or _contains_any(lower, _REPAIR_MARKERS_EN)
        ):

            signals.append("conversation_repair")

            return self._decision(
                GENERAL_CONVERSATION,
                0.9,
                signals,
                "correction/repair of the current exchange: handled as "
                "conversation, never as learning",
                raw,
                working,
                previous_intent,
            )

        # ==================================================
        # DECISION 1 — SELF-INTRODUCTION
        #
        # "خودت رو معرفی کن" / "Who are you?" is a PERSON-identity
        # turn. It is NEVER teaching, whatever the session state.
        # ==================================================
        if self._is_self_introduction(form, lower):

            signals.append("self_introduction")

            return self._decision(
                GENERAL_CONVERSATION,
                0.95,
                signals,
                "self-introduction / identity request about the assistant",
                raw,
                working,
                previous_intent,
            )

        # ==================================================
        # DECISION 2 — USER ASKS ARCHITECTOS TO TEACH THEM
        #
        # "معماری رو بهم یاد بده" / "teach me about X" — the user
        # is the LEARNER. This is the direction guard: it is NOT
        # the user teaching the assistant.
        # ==================================================
        if self._is_learn_request(form, lower):

            signals.append("user_requests_teaching")

            subject = self._subject(form, lower)

            intent = (
                ARCHITECTURE_CONVERSATION
                if subject == "architecture"
                else GENERAL_CONVERSATION
            )

            return self._decision(
                intent,
                0.9,
                signals + ["subject:" + subject],
                "user asks the assistant to teach them (user is the "
                "learner) — never teaching-to-the-assistant",
                raw,
                working,
                previous_intent,
            )

        # ==================================================
        # DECISION 3 — TEACHING-TO-ARCHITECTOS
        #
        # Requires EXPLICIT knowledge-transfer evidence. Never
        # inferred from architecture vocabulary, a declaration, a
        # correction, or an opinion.
        # ==================================================
        teach_signal = self._teaching_evidence(form, lower, signals)

        if teach_signal:

            return self._decision(
                TEACHING,
                0.9,
                signals,
                "explicit knowledge-transfer intent to the assistant: "
                + teach_signal,
                raw,
                working,
                previous_intent,
            )

        # ==================================================
        # DECISION 4 — SUBJECT (architecture vs general)
        #
        # Subject decides only which CONVERSATION this is. It
        # never promotes a turn to TEACHING.
        # ==================================================
        subject = self._subject(form, lower)

        signals.append("subject:" + subject)

        # GENERAL_CONVERSATION_CORRECTION_V1 — a contrastive correction of the
        # current exchange is conversation repair, whichever side of the
        # contrast carries the architecture subject:
        #
        #   "معمایی گفتم نه معماری"  -> the architecture subject is negated
        #   "معماری گفتم نه معمایی"  -> the architecture subject is affirmed
        #   "اتاق ۱۲ متره، نه ۱۰ متر" -> a dimension is corrected
        #
        # The signal rides along with whatever subject the turn really has, so
        # it never overrides the subject decision — a turn that negates
        # architecture AND asks about architecture keeps its architectural
        # subject. It is deliberately subject-agnostic: a correction is not
        # only about architecture.
        if _has_negated_subject(form, lower) or has_contrastive_negation(working):

            signals.append("conversation_repair")

        if subject == "architecture":

            return self._decision(
                ARCHITECTURE_CONVERSATION,
                0.8,
                signals,
                "architecture subject present, conversational intent",
                raw,
                working,
                previous_intent,
            )

        return self._decision(
            GENERAL_CONVERSATION,
            0.8,
            signals,
            "no teaching-transfer evidence and no architecture subject",
            raw,
            working,
            previous_intent,
        )

    # ------------------------------------------------------
    # SIGNAL HELPERS
    # ------------------------------------------------------

    def _is_self_introduction(self, form, lower):

        # Persian — a self-reference + an introduction verb, or an
        # identity topic.
        if _fold_matches(form, _SELF_REFERENCE) and (
            _fold_matches(form, _INTRO_VERBS)
            or _fold_matches(form, _IDENTITY_TOPICS)
        ):

            return True

        # A bare identity topic ("اسمت چیه؟", "تو کی هستی").
        if _fold_matches(form, _IDENTITY_TOPICS):

            return True

        # English.
        if _contains_any(lower, _IDENTITY_TOPICS_EN):

            return True

        return False

    def _is_learn_request(self, form, lower):
        """The user asks the ASSISTANT to teach THEM."""

        if _contains_any(lower, _LEARN_REQUEST_EN):

            return True

        # Persian: an explicit learner addressee + a teaching verb.
        if (
            _fold_matches(form, _LEARNER_FIRST_PERSON)
            and _fold_matches(form, _LEARN_REQUEST_PERSIAN)
        ):

            return True

        # "یادم بده" (teach me) is unambiguous on its own.
        if "\u06cc\u0627\u062f\u0645 \u0628\u062f\u0647" in form:  # یادم بده

            return True

        return False

    # ------------------------------------------------------
    # TEACHING_INTENT_TRIGGER_REPAIR_V1 — teach-verb evidence
    # ------------------------------------------------------

    def _has_teach_verb_evidence(self, form):
        """True when the sentence carries a GENUINE teaching verb.

        `_TEACH_VERB` mixes a real verb stem ("یاد بده") with the bare
        noun/adjective "آموزش". Only the verb stems count on their own;
        "آموزش" counts ONLY when a transfer verb carries it to the
        assistant ("بهت بگم" / "بهت بدم"). A resource offer
        ("... رو بهت معرفی کنم" / "... برات بفرستم") never qualifies.
        """

        # A real teach verb stem other than the ambiguous noun "آموزش".
        if "یاد بده" in form:          # یاد بده / یاد بدم / یاد بدهم ...
            return True

        if "\u062a\u0639\u0644\u06cc\u0645" in form:   # تعلیم
            return True

        if "\u062f\u0631\u0633 \u0628\u062f\u0647" in form:  # درس بده
            return True

        # The ambiguous "آموزش" needs a transfer verb AND must not be a
        # bare resource offer.
        has_education_word = "\u0627\u0645\u0648\u0632\u0634" in form   # آموزش(ی)

        if has_education_word:

            has_transfer_verb = _fold_matches(
                form, _TRANSFER_VERB_TO_ASSISTANT
            )

            has_resource_verb = _fold_matches(form, _RESOURCE_VERB)

            # A resource verb with no transfer verb is a mention, not
            # teaching — even though "آموزشی" is present.
            if has_resource_verb and not has_transfer_verb:
                return False

            return has_transfer_verb

        return False

    def _teaching_evidence(self, form, lower, signals):
        """Return a reason string when the user is teaching the
        assistant, else None. Appends the matched signal name."""

        # ---- English explicit transfer ----------------
        if _contains_any(lower, _TEACH_EN_OFFER):

            signals.append("en_offer_to_teach")

            return "en_offer_to_teach"

        if _contains_any(lower, _TEACH_EN_IMPERATIVE):

            # "remember this rule" is teaching only when it is not a
            # learn request (already handled above).
            signals.append("en_imperative_remember")

            return "en_imperative_remember"

        # ---- Persian: explicit offer ("یادت بدم") -----
        if _fold_matches(form, _TEACH_OFFER_PERSIAN):

            signals.append("fa_offer_to_teach")

            return "fa_offer_to_teach"

        # ---- Persian: "بهت ... یاد میدم" --------------
        #
        # TEACHING_INTENT_TRIGGER_REPAIR_V1 — DIRECTION GUARD.
        #
        # "یاد" is a genuine teach/remember stem: with an assistant
        # addressee it is teaching on its own ("یه نکته بهت یاد بدم").
        #
        # "آموزش" is BOTH a noun and an adjective, so on its own it only
        # says the sentence is ABOUT education. It must therefore be
        # backed by a real transfer verb aimed at the assistant
        # ("بهت بگم" / "بهت بدم"). Without that, a sentence that merely
        # offers a resource stays out of TEACHING:
        #   "یه کتاب آموزشی بهت معرفی کنم"      -> not teaching
        #   "میخوام یه ویدیوی آموزشی برات بفرستم" -> not teaching
        if (
            _fold_matches(form, _ADDRESSEE_ASSISTANT)
            and (
                "\u06cc\u0627\u062f" in form   # یاد (teach/remember)
                or self._has_teach_verb_evidence(form)
            )
        ):

            signals.append("fa_addressee_teach")

            return "fa_addressee_teach"

        # ---- Persian: "می خوام ... بهت یاد بدم" -------
        if (
            _fold_matches(form, _VOLITION_TEACH)
            and self._has_teach_verb_evidence(form)
            and _fold_matches(form, _ADDRESSEE_ASSISTANT)
        ):

            signals.append("fa_volition_teach")

            return "fa_volition_teach"

        # ---- Persian: possession offer of KNOWLEDGE ---
        #
        # TEACHING_INTENT_TRIGGER_REPAIR_V1.
        #
        # "این یه نکته آموزشی برای توئه" / "نکته آموزشی دارم برات" states
        # that the user POSSESSES a piece of KNOWLEDGE for the assistant.
        # The direction is USER -> ARCHITECTOS, so it is teaching even
        # though no transfer verb ("بگم"/"بدم") appears.
        #
        # This must NOT reach a resource noun ("کتاب"/"ویدیو"): having a
        # book for someone is not having knowledge to hand over, and
        # "یه کتاب آموزشی دارم برات" must stay out of TEACHING.
        if (
            _fold_matches(form, _ADDRESSEE_ASSISTANT)
            and _fold_matches(form, _POSSESSION_OFFER)
            and _fold_matches(form, _KNOWLEDGE_NOUN)
            and not _fold_matches(form, _RESOURCE_NOUN)
        ):

            signals.append("fa_possess_knowledge_offer")

            return "fa_possess_knowledge_offer"

        # ---- Persian: possession of KNOWLEDGE, no spoken addressee ----
        #
        # TEACHING CONTENT CAPTURE V1.
        #
        # "یه نکته آموزشی دارم" ("I have a teaching note") states the
        # speaker POSSESSES knowledge and is about to hand it over. The
        # direction is USER -> ARCHITECTOS even though no addressee
        # pronoun ("بهت" / "برات") is spoken. It used to fall to
        # GENERAL_CONVERSATION and be answered as small talk, and the
        # version with its proposition attached
        # ("یه نکته آموزشی دارم: ورودی مستقیم به پذیرایی نباشه") fell to
        # ARCHITECTURE_CONVERSATION on the subject word alone.
        #
        # The TRANSFER STRUCTURE is required — a knowledge noun the
        # speaker OWNS ("... دارم") — and three guards keep the resource
        # and learner shapes out:
        #   "این کتاب آموزشی خوبه؟"                        -> resource noun
        #   "یه ویدیوی آموزشی معرفی کن"                    -> resource noun
        #   "یه نکته آموزشی درباره معماری برام توضیح بده"   -> learner marker
        #   "می تونی یه آموزش درباره پلان بهم بدی؟"         -> learner marker
        #
        # The possession verb is matched as a WHOLE WORD, so "ندارم"
        # ("I do NOT have") is never possession.
        if (
            _fold_word_matches(form, _POSSESSION_HAVE)
            and _fold_matches(form, _KNOWLEDGE_NOUN)
            and not _fold_matches(form, _RESOURCE_NOUN)
            and not _fold_matches(form, _LEARNER_FIRST_PERSON)
        ):

            signals.append("fa_possess_knowledge_offer")

            return "fa_possess_knowledge_offer"

        # ---- Persian: imperative to the assistant -----
        if _fold_matches(form, _TEACH_IMPERATIVE_TO_ASSISTANT):

            # "حفظ کن" / "اضافه کن" need an assistant addressee or a
            # knowledge addressee, so an ordinary "این رو درست کن"
            # never becomes teaching. The "یاد..." imperatives
            # ("یاد بگیر", "یادت باشه") are unambiguous on their own.
            has_knowledge_addressee = _fold_matches(
                form, _KNOWLEDGE_ADDRESSEE
            )

            has_assistant_addressee = _fold_matches(
                form, _ADDRESSEE_ASSISTANT
            )

            unambiguous = (
                "\u06cc\u0627\u062f \u0628\u06af\u06cc\u0631" in form      # یاد بگیر
                or "\u06cc\u0627\u062f\u062a \u0628\u0627\u0634\u0647" in form  # یادت باشه
                or "\u06cc\u0627\u062f \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634" in form  # یاد داشته باش
                or "\u0628\u0647 \u062e\u0627\u0637\u0631 \u0628\u0633\u067e\u0627\u0631" in form  # به خاطر بسپار
                or "\u06cc\u0627\u062f \u0628\u0633\u067e\u0627\u0631" in form  # یاد بسپار
            )

            if unambiguous or has_knowledge_addressee or has_assistant_addressee:

                signals.append("fa_imperative_to_assistant")

                return "fa_imperative_to_assistant"

        # ---- Persian: "می خوام ... حفظ کنی" ----------
        if (
            _fold_matches(form, _VOLITION_TEACH)
            and (
                "\u062d\u0641\u0638 \u06a9\u0646\u06cc" in form   # حفظ کنی
                or "\u06cc\u0627\u062f \u0628\u06af\u06cc\u0631\u06cc" in form  # یاد بگیری
                or "\u06cc\u0627\u062f \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u06cc" in form  # یاد داشته باشی
            )
        ):

            signals.append("fa_volition_remember")

            return "fa_volition_remember"

        return None

    def _subject(self, form, lower):
        """Return "architecture" or "general" — SUBJECT only."""

        # A clearly non-architectural topic wins unless an
        # architecture word is ALSO present.
        has_non_arch = (
            _fold_matches(form, _NON_ARCHITECTURE_TOPIC)
            or _contains_any(lower, _NON_ARCHITECTURE_TOPIC_EN)
        )

        # GENERAL_CONVERSATION_CORRECTION_V1 — a subject word inside a
        # negation is NOT an affirmation of that subject. Without this,
        # "معمایی گفتم نه معماری" (mystery, NOT architecture) was classified
        # ARCHITECTURE_CONVERSATION purely because the REJECTED word appeared,
        # and the assistant then reaffirmed the subject the user had refused.
        has_arch = (
            affirmed_hit(
                form,
                tuple(_fold(marker) for marker in _ARCHITECTURE_SUBJECT),
            )
            or affirmed_hit(lower, _ARCHITECTURE_SUBJECT_EN)
        )

        if has_arch:

            return "architecture"

        if has_non_arch:

            return "general"

        return "general"

    # ------------------------------------------------------
    # DECISION OBJECT
    # ------------------------------------------------------

    def _decision(
        self,
        intent,
        confidence,
        signals,
        reason,
        raw,
        working,
        previous_intent,
    ):

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "intent": intent,

            "confidence": round(float(confidence), 3),

            "signals": list(signals),

            "reason": reason,

            "source": "current_turn",

            # Honesty + auditability: the boundary never rewrites.
            "raw_transcript": raw,

            "interpreted_utterance": working,

            "previous_intent": previous_intent,

            "sticky_override": False,

            "is_teaching": intent == TEACHING,

            "is_architecture": intent == ARCHITECTURE_CONVERSATION,

            "is_general": intent == GENERAL_CONVERSATION,
        }


# ==========================================================
# MODULE-LEVEL SINGLETON + FUNCTION (project convention)
# ==========================================================

conversation_intent_boundary = ConversationIntentBoundaryV1()


def classify_conversation_intent(text, **kwargs):

    return conversation_intent_boundary.classify(text, **kwargs)
