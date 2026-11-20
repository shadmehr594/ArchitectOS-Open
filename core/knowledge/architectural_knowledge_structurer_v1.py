# ==========================================================
# ArchitectOS Architectural Knowledge Structurer v1
#
# ARCHITECTURAL_KNOWLEDGE_STRUCTURER_V1
#
# Turns the teacher's OWN recorded statements into an architectural
# structure for one space:
#
#   teaching candidates  ->  Space Knowledge Representation
#
# It is a REPRESENTATION layer. It is NOT a learning system, it does NOT
# create permanent knowledge, it does NOT promote lessons, it does NOT
# touch the curriculum, the teaching memory or the architecture corpus,
# and it never calls an LLM or a renderer.
#
# WHAT IT READS (all frozen, none of it duplicated here):
#   * `teaching_candidate_store`   — what the human teacher actually said
#   * `space_types`                — the residential space registry
#                                    (category, privacy level, zone,
#                                     typical / discouraged adjacency)
#   * `space_query_v1.scan_spaces` — the canonical space scanner
#   * `teaching_meaning_v1`        — the frozen entity + relation lexicon
#   * `clause_analysis_v1`         — clause roles for a legacy message
#   * `teach_back_v1`              — the SUBJECT-SCOPE rule, so a rule
#                                    about another space can never enter
#                                    this structure
#
# WHAT IT ADDS: closed, documented surface-form tables (occupants, goals,
# requirements, colloquial aliases, rule patterns, area conditions). They
# only RECOGNISE words the teacher already used. Anything unrecognised is
# reported in `uncertainties`, never guessed.
#
# EVERY structured item carries its source candidate, its source
# statement, its status and its confidence (brief rule 3), and every
# field records which layer produced it (`field_sources`).
# ==========================================================


from __future__ import annotations


from copy import deepcopy
import re
from typing import Any, Dict, Iterable, List


from core.conversation.turn_semantics_v1 import match_form


CONTRACT = "ArchitecturalKnowledgeStructureV1"

VERSION = "1.0"


# Candidate-to-structure contract. The legacy teaching structurer below keeps
# its existing API and behavior; this additive function consumes only the
# transient ArchitecturalKnowledgeCandidateV1 contract.
CANDIDATE_CONTRACT = "ArchitecturalKnowledgeCandidateV1"
CANDIDATE_VERSION = "1.0"


# Statuses that are still teacher-sourced and not rejected.
GROUNDABLE_STATUSES = ("observed", "needs_confirmation")


# ----------------------------------------------------------
# 1. WHO THE SPACE IS FOR  (closed table)
# ----------------------------------------------------------

OCCUPANT_LEXICON = {

    "parents": ("والدین", "پدر و مادر", "پدرومادر", "parents"),

    "couple": (
        "زوجین", "زن و شوهر", "زنوشوهر", "زوج", "couple", "spouses",
    ),

    "children": (
        "بچه ها", "بچه‌ها", "بچه", "کودکان", "کودک", "فرزندان",
        "children", "kids",
    ),

    "guests": ("میهمانان", "میهمان", "مهمان", "مهمانان", "guests", "guest"),

    "elderly": ("مسن ها", "مسن‌ها", "مسن", "سالمندان", "elderly"),

    "household": ("خانواده", "اهل خانه", "ساکنان", "household", "family"),
}


OCCUPANT_DISPLAY = {

    "parents": {"fa": "والدین", "en": "parents"},

    "couple": {"fa": "زوجین", "en": "the couple"},

    "children": {"fa": "بچه‌ها", "en": "children"},

    "guests": {"fa": "میهمانان", "en": "guests"},

    "elderly": {"fa": "سالمندان", "en": "the elderly"},

    "household": {"fa": "خانواده", "en": "the household"},
}


# ----------------------------------------------------------
# 2. WHAT THE SPACE IS FOR  (closed table)
# ----------------------------------------------------------

GOAL_LEXICON = {

    "privacy": ("حریم", "محرمیت", "privacy"),

    "comfort": ("آرامش", "راحتی", "comfort"),

    "rest": ("استراحت", "خواب", "rest"),
}


GOAL_DISPLAY = {

    "privacy": {"fa": "حریم", "en": "privacy"},

    "comfort": {"fa": "آرامش", "en": "comfort"},

    "rest": {"fa": "استراحت", "en": "rest"},
}


# ----------------------------------------------------------
# 3. REQUIRED PROPERTIES  (closed table)
#
# Not entities: properties the teacher says the space NEEDS. They share
# `required_elements` with the frozen entity ids and are told apart by
# `kind` on every item.
# ----------------------------------------------------------

REQUIREMENT_LEXICON = {

    "daylight": ("نور طبیعی", "نور", "روشنایی", "نورگیر"),

    "ventilation": ("تهویه", "هوا خوری", "هواکش"),
}


REQUIREMENT_DISPLAY = {

    "daylight": {"fa": "نور طبیعی", "en": "daylight"},

    "ventilation": {"fa": "تهویه", "en": "ventilation"},
}


# A NEED the teacher stated can imply the element that delivers it. The
# derivation is recorded on the item itself (`implied_by`), never
# presented as something the teacher said.
REQUIREMENT_IMPLIES = {

    "daylight": ("window",),

    "ventilation": ("window",),
}


# ----------------------------------------------------------
# 4. COLLOQUIAL SURFACE FORMS  (lookup only)
#
# The teacher speaks colloquially. These are ONE-WAY normalisations used
# only to LOOK a word up in the frozen vocabularies — the teacher's own
# wording is what is reported back. Nothing here adds a new concept.
# ----------------------------------------------------------

COLLOQUIAL_ALIASES = {

    "حموم": "حمام",

    "سرویس فرنگی": "سرویس",

    "دستشویی فرنگی": "دستشویی",

    "اتاق مستر": "اتاق خواب مستر",

    "مستر": "اتاق خواب مستر",

    "کلوزت روم": "کلوزت",
}


# ----------------------------------------------------------
# 5. ELEMENT DISPLAY  (frozen entity ids only)
# ----------------------------------------------------------

ELEMENT_DISPLAY = {

    "bed": {"fa": "تخت", "en": "bed"},

    "wardrobe": {"fa": "کمد/کلوزت", "en": "wardrobe or closet"},

    "bathroom": {"fa": "حمام/سرویس", "en": "bathroom"},

    "window": {"fa": "پنجره", "en": "window"},

    "door": {"fa": "در", "en": "door"},

    "bedroom": {"fa": "اتاق خواب", "en": "bedroom"},

    "living": {"fa": "نشیمن/پذیرایی", "en": "living or reception"},

    "kitchen": {"fa": "آشپزخانه", "en": "kitchen"},

    "dining": {"fa": "غذاخوری", "en": "dining"},

    "storage": {"fa": "انباری", "en": "storage"},

    "entrance": {"fa": "ورودی", "en": "entrance"},

    "corridor": {"fa": "راهرو", "en": "corridor"},

    "balcony": {"fa": "بالکن", "en": "balcony"},

    "garden": {"fa": "حیاط", "en": "garden"},

    "office": {"fa": "دفتر", "en": "office"},
}


# A qualifier the teacher used stays attached to the frozen element id —
# "تخت دونفره" is the `bed` element with the `double` modifier, never a
# new id (the frozen lexicon owns these ids).
ELEMENT_MODIFIERS = {

    "دونفره": "double",

    "دو نفره": "double",

    "یک نفره": "single",

    "یکنفره": "single",

    "دیواری": "built_in",
}


# ----------------------------------------------------------
# 6. DESIGN-RULE PATTERNS  (closed table)
#
# A pattern fires only when EVERY group has a hit in the statement, and
# only for a statement that is NOT a definition (brief rule 1: a
# definition is never turned into a law).
# ----------------------------------------------------------

RULE_PATTERNS = (

    {
        "rule": "avoid_direct_view_to_bed_from_entry",
        "type": "privacy",
        "all_of": (
            ("دید", "دیدی", "visibility"),
            ("تخت", "تخت خواب", "bed"),
            ("درب", "درباز", "در باز", "ورودی", "آستانه", "entry"),
        ),
    },

    {
        "rule": "bed_away_from_window",
        "type": "placement",
        "all_of": (
            ("تخت", "تخت خواب", "bed"),
            ("پنجره", "window"),
            ("دور", "فاصله", "away"),
        ),
    },

    {
        "rule": "keep_away_from_public_zones",
        "type": "privacy",
        "all_of": (
            ("دور", "جدا", "away"),
            ("پذیرایی", "نشیمن", "عمومی", "میهمان", "مهمان", "public"),
        ),
    },

    {
        "rule": "preserve_privacy_and_boundary",
        "type": "privacy",
        "all_of": (
            ("حریم", "محرمیت", "privacy", "boundary"),
        ),
    },
)


RULE_DISPLAY = {

    "avoid_direct_view_to_bed_from_entry": {
        "fa": "تخت از دید ورودی پنهان باشد",
        "en": "the bed is not visible from the entry",
    },

    "bed_away_from_window": {
        "fa": "تخت نسبت به پنجره با فاصله جانمایی شود",
        "en": "the bed is placed away from the window",
    },

    "keep_away_from_public_zones": {
        "fa": "از فضاهای عمومی و مهمان دور باشد",
        "en": "kept away from public and guest zones",
    },

    "preserve_privacy_and_boundary": {
        "fa": "حریم و مرز خصوصی حفظ شود",
        "en": "privacy and its boundary are preserved",
    },
}


RULE_TYPE_DISPLAY = {

    "privacy": {"fa": "حریم", "en": "privacy"},

    "placement": {"fa": "جانمایی", "en": "placement"},
}


# ----------------------------------------------------------
# 7. AREA DEPENDENCY  (closed table)
# ----------------------------------------------------------

CONDITION_LEXICON = {

    "small_area": (
        "زیربنا کم", "زیربنای کم", "متراژ کم", "کوچک", "کم بود",
        "کوچک تر", "محدود",
    ),

    "large_area": (
        "زیربنا زیاد", "زیربنای زیاد", "زیربنای بالا", "متراژ بالا",
        "متراژ زیاد", "بزرگ", "زیاد باشه", "فضا بیشتر", "بیشتر باشد",
    ),

    "area_dependent": (
        "بستگی به جا", "بستگی به متراژ", "بسته به فضا", "بسته به متراژ",
        "بستگی داره",
    ),
}


CONDITION_DISPLAY = {

    "small_area": {"fa": "زیربنای کم", "en": "small area"},

    "large_area": {"fa": "زیربنای زیاد", "en": "large area"},

    "area_dependent": {"fa": "وابسته به متراژ", "en": "area dependent"},
}


# ----------------------------------------------------------
# 8. STRENGTH MARKERS  (closed table)
# ----------------------------------------------------------

REQUIREMENT_MARKERS = (
    "حتما", "حتماً", "باید", "نیاز داره", "نیاز دارد", "نیاز هست",
    "نیاز به", "نیازمند", "لازم", "الزام", "ضروری", "ممنوع", "نباید",
)


PREFERENCE_MARKERS = (
    "بهتره", "بهتر است", "بهتر باشه", "ترجیحا", "ترجیحاً",
    "در صورت امکان", "اگر امکان", "میشه", "میتوان", "می‌توان",
    "شاید", "ممکنه", "ممکن است", "کافیه", "کافی است",
)


CONDITIONAL_MARKERS = (
    "اگه", "اگر", "در صورت", "بستگی", "شاید", "ممکنه", "ممکن است",
    "بسته به", "وقتی",
)


# An occupant is only recorded as a USER of the space when the teacher
# attaches them to it — "اتاق خواب بچه ها" merely NAMES another room and
# must not make the children users of the master bedroom.
FOR_MARKERS = (
    "برای", "مخصوص", "مختص", "مربوط به", "belongs to", "for the",
)


# ----------------------------------------------------------
# 9. RENDERING PHRASES
# ----------------------------------------------------------

STRUCTURE_PHRASES = {

    "fa": {

        "header": "بر اساس آموزش‌های دریافت‌شده، %s:",

        "definition": "• تعریف: %s",

        "category_users": "• فضای %s %s است",

        "goals": "• نیاز به %s دارد",

        "required": "• %s لازم دارد",

        "optional": "• معمولاً %s دارد (در صورت امکان)",

        "near": "• نزدیک به %s",

        "avoid": "• دور از %s",

        "rule": "• %s",

        "condition": "• اگر %s باشد: %s",

        "uncertain_header": (
            "مواردی که هنوز به صورت قانون قطعی ثبت نشده:"
        ),

        "uncertain_item": "• %s  (منبع: %s — وضعیت: %s)",

        "uncertain_none": (
            "• مورد نامشخص خاصی ثبت نشده است؛ ولی همهٔ موارد بالا فقط "
            "«دریافت‌شده» هستند."
        ),

        "source_human": "مدرس انسانی",

        "status_observed": "دریافت‌شده (تأییدنشده)",

        "status_pending": "در انتظار تأیید",

        "note": (
            "این ساختار فقط از گفته‌های ثبت‌شدهٔ شما ساخته شده و چیزی "
            "به دانش دائمی تبدیل نشده است."
        ),
    },

    "en": {

        "header": "From what you have taught me, %s:",

        "definition": "• Definition: %s",

        "category_users": "• A %s space for %s",

        "goals": "• Needs %s",

        "required": "• Requires %s",

        "optional": "• Usually has %s (where possible)",

        "near": "• Near %s",

        "avoid": "• Kept away from %s",

        "rule": "• %s",

        "condition": "• If %s: %s",

        "uncertain_header": "Not yet recorded as a definitive rule:",

        "uncertain_item": "• %s  (source: %s — status: %s)",

        "uncertain_none": (
            "• No specific open item is recorded; every item above is "
            "still only \"received\"."
        ),

        "source_human": "human teacher",

        "status_observed": "received (not confirmed)",

        "status_pending": "awaiting confirmation",

        "note": (
            "This structure is built only from what you recorded; "
            "nothing has become permanent knowledge."
        ),
    },
}


CATEGORY_DISPLAY = {

    "PRIVATE": {"fa": "خصوصی", "en": "private"},

    "SEMI_PUBLIC": {"fa": "نیمه‌عمومی", "en": "semi-public"},

    "PUBLIC": {"fa": "عمومی", "en": "public"},

    "SERVICE": {"fa": "خدماتی", "en": "service"},

    "CIRCULATION": {"fa": "ارتباطی", "en": "circulation"},

    "EXTERNAL": {"fa": "بیرونی", "en": "external"},
}


SPACE_NAME_OVERRIDES = {

    "private": {"fa": "خصوصی", "en": "private"},

    "public": {"fa": "عمومی", "en": "public"},

    "semi-public": {"fa": "نیمه‌عمومی", "en": "semi-public"},

    "service": {"fa": "خدماتی", "en": "service"},

    "circulation": {"fa": "ارتباطی", "en": "circulation"},

    "external": {"fa": "بیرونی", "en": "external"},
}


# ----------------------------------------------------------
# TEXT HELPERS
# ----------------------------------------------------------

_WORD = "\u0600-\u06FF\u200cA-Za-z0-9"


def _form(text):

    """The canonical matching form (never used to split text)."""

    try:

        return match_form(text or "")

    except Exception:

        return str(text or "").lower()


def _contains(form, phrase):

    """A word-START hit for a short phrase, a plain hit otherwise.

    Persian attaches its suffixes to the RIGHT ("حریمش", "دیدی",
    "نورگیر"), so a surface form is matched at a word START rather than
    on both sides — otherwise `حریم` would miss `حریمش` and the
    teacher's own rule would be dropped. Used for rules, goals and
    occupants, whose words carry the teacher's suffixes.
    """

    needle = _form(phrase)

    if not needle:

        return False

    if " " in needle:

        return needle in form

    return re.search(
        r"(?<![" + _WORD + r"])" + re.escape(needle), form
    ) is not None


def _contains_whole(form, phrase):

    """A whole-word hit.

    Used for ELEMENT nouns. `کمد دیواری` (a built-in closet) must reach
    the `wardrobe` element and must NOT also be read as a `wall`.
    """

    needle = _form(phrase)

    if not needle:

        return False

    return re.search(
        r"(?<![" + _WORD + r"])"
        + re.escape(needle)
        + r"(?![" + _WORD + r"])",
        form,
    ) is not None


def _hits(form, lexicon):

    """Every lexicon key whose surface form occurs, in table order."""

    return [key for key, _surface in _hits_with_surface(form, lexicon)]


def _hits_with_surface(form, lexicon):

    """(key, surface) for every lexicon key that occurs, table order."""

    found = []

    for key, surfaces in lexicon.items():

        for surface in surfaces:

            if _contains(form, surface):

                found.append((key, surface))

                break

    return found


# How far after an ANCHOR an occupant still belongs to it.
# "مخصوص والدین هست و اتاق خواب بچه ها" attaches the parents only.
_OCCUPANT_WINDOW = 24


def _occupant_anchors(space_id):

    """The space's own name(s) from the frozen corpus.

    The exact name the STATEMENT used is added at the call site, through
    the canonical scanner.
    """

    anchors = []

    try:

        from core.curriculum.space_types_v1 import space_types

        record = space_types.space(space_id) or {}

        name = record.get("name") or {}

        for surface in (
            list(record.get("aliases") or [])
            + [name.get("fa"), name.get("en")]
        ):

            if surface and surface not in anchors:

                anchors.append(surface)

    except Exception:

        pass

    return anchors


def _occupants_after_marker(form, own_surfaces=()):

    """Occupants the teacher attached to the space.

    Only inside the short window that follows an ANCHOR: a "for / مخصوص"
    marker, the space's own name, or the exact name the statement used
    for the space ("اتاق خواب مستر اتاق والدین هست"). "اتاق خواب مستر
    داریم ... و اتاق خواب بچه ها" must not make the children users of the
    master bedroom.
    """

    anchors = list(FOR_MARKERS) + [
        surface for surface in own_surfaces if surface
    ]

    found = []

    for marker in anchors:

        needle = _form(marker)

        if not needle:

            continue

        start = 0

        while True:

            index = form.find(needle, start)

            if index < 0:

                break

            window = form[index + len(needle):index + len(needle) + _OCCUPANT_WINDOW]

            for occupant, surfaces in OCCUPANT_LEXICON.items():

                if occupant in found:

                    continue

                for surface in surfaces:

                    if _contains(window, surface):

                        found.append(occupant)

                        break

            start = index + len(needle)

    return found


def _normalised_surfaces(text):

    """The text plus its colloquial normalisation, for LOOKUP only."""

    form = _form(text)

    extra = form

    for colloquial, canonical in COLLOQUIAL_ALIASES.items():

        if _contains(form, colloquial):

            extra = extra + " " + _form(canonical)

    return form, extra


def _elements(text):

    """(entity_id, surface, modifier) for every frozen element named."""

    from core.conversation.teaching_meaning_v1 import ENTITY_LEXICON

    form, lookup = _normalised_surfaces(text)

    modifier = None

    for surface, name in ELEMENT_MODIFIERS.items():

        if _contains(form, surface):

            modifier = name

            break

    found = []

    seen = set()

    for entity_id, surfaces in ENTITY_LEXICON.items():

        for surface in surfaces:

            if _contains_whole(lookup, surface):

                if entity_id in seen:

                    break

                seen.add(entity_id)

                found.append((entity_id, surface, modifier))

                break

    return found


def _space_mentions(text):

    """(space_id, matched surface) for every corpus space named."""

    try:

        from core.curriculum.space_query_v1 import scan_spaces

        mentions = scan_spaces(text)

    except Exception:

        return []

    return [(mention[0], mention[1]) for mention in (mentions or [])]


def _space_ids(text):

    """The corpus spaces a statement names, in position order.

    The CANONICAL scanner only. A colloquial form ("حموم", "کلوزت") is
    deliberately NOT turned into a space mention here: those words are
    the teacher's elements ("a closet and a bathroom for that room"),
    and promoting them to a relation target would drop them from the
    element lists.
    """

    return [space_id for space_id, _surface in _space_mentions(text)]


def _inside_a_space_name(surface, mention_surfaces):

    """Is this matched word part of a LONGER space name the statement used?

    "اتاق خواب" inside the matched name "اتاق خواب مستر" is a reference
    to the SPACE — not an element of it, and the "خواب" inside it is not
    a goal either. But a word that IS the whole matched name is the
    space itself being named as a thing ("کلوزت و حمام اضافه می‌شود"
    really does add a bathroom), so it stays.
    """

    if not surface:

        return False

    for mention in mention_surfaces:

        if mention and surface != mention and surface in mention:

            return True

    return False


_SPACE_OF_ENTITY = {}


def _entity_space_id(entity_id):

    """The corpus space an element id resolves to, or None.

    Resolved through the frozen entity lexicon's OWN surface forms, so
    "نشیمن" reaches LIVING_RECEPTION while "تخت" reaches nothing.
    """

    if entity_id in _SPACE_OF_ENTITY:

        return _SPACE_OF_ENTITY[entity_id]

    resolved = None

    try:

        from core.conversation.teaching_meaning_v1 import ENTITY_LEXICON

        from core.curriculum.space_types_v1 import space_types

        for surface in ENTITY_LEXICON.get(entity_id) or []:

            record = space_types.resolve(surface)

            if record:

                resolved = record.get("space_id")

                break

    except Exception:

        resolved = None

    _SPACE_OF_ENTITY[entity_id] = resolved

    return resolved


def _rules(form, is_definition):

    """The design-rule patterns this statement satisfies."""

    if is_definition:

        return []

    found = []

    for pattern in RULE_PATTERNS:

        if all(
            any(_contains(form, phrase) for phrase in group)
            for group in pattern["all_of"]
        ):

            found.append(pattern)

    return found


def _conditions(form):

    return _hits(form, CONDITION_LEXICON)


def _strength(form, role, polarity):

    """`required` / `optional` for an element of this statement."""

    if any(_contains(form, marker) for marker in REQUIREMENT_MARKERS):

        return "required"

    if any(_contains(form, marker) for marker in PREFERENCE_MARKERS):

        return "optional"

    if polarity in ("require",):

        return "required"

    if polarity in ("prefer", "avoid"):

        return "optional"

    if role in ("OBSERVATION", None) and polarity in ("neutral", "define"):

        return "optional"

    return "optional"


# ----------------------------------------------------------
# STATEMENT EXPANSION
# ----------------------------------------------------------

def _statement_from(candidate, text, role):

    return {

        "text": text,

        "role": role,

        "knowledge_class": candidate.get("knowledge_class"),

        "polarity": candidate.get("polarity"),

        "status": candidate.get("status"),

        "confidence": candidate.get("confidence"),

        "candidate_id": candidate.get("candidate_id"),

        "scope": candidate.get("scope"),
    }


def _statements(candidates, space_id):

    """One entry per teacher statement about this space.

    A clause candidate is already one statement. A candidate recorded
    BEFORE the clause analyser is one WHOLE message: it is re-analysed
    READ-ONLY here and only its in-scope clauses are kept, through the
    same subject-scope rule the grounded answer uses.

    Unlike the grounded answer's rule list, OBSERVATION clauses are kept:
    an observation is exactly what becomes an optional element or an area
    dependency here (brief rule 2), it is just never turned into a law.
    """

    from core.conversation.clause_analysis_v1 import knowledge_clauses

    from core.conversation.teach_back_v1 import _in_subject_scope

    statements = []

    for candidate in candidates:

        text = candidate.get("raw_statement") or ""

        if not text:

            continue

        role = candidate.get("clause_role")

        if role:

            if _in_subject_scope(text, space_id):

                statements.append(_statement_from(candidate, text, role))

            continue

        try:

            clauses = knowledge_clauses(text)

        except Exception:

            clauses = []

        kept = 0

        for clause in clauses or []:

            clause_text = clause.get("text") or ""

            if not clause_text or not _in_subject_scope(clause_text, space_id):

                continue

            statements.append(
                _statement_from(candidate, clause_text, clause.get("role"))
            )

            kept += 1

        if not kept and _in_subject_scope(text, space_id):

            statements.append(_statement_from(candidate, text, None))

    return statements


# ----------------------------------------------------------
# CORPUS SKELETON
# ----------------------------------------------------------

def _corpus(space_id):

    try:

        from core.curriculum.space_types_v1 import space_types

        record = space_types.space(space_id)

    except Exception:

        return {}

    return record or {}


def _label(space_id, language):

    record = _corpus(space_id)

    name = (record.get("name") or {}).get(language)

    if not name:

        name = (record.get("name") or {}).get("fa")

    return name or str(space_id or "")


def _display(table, key, language, fallback=None):

    entry = table.get(key)

    if not isinstance(entry, dict):

        return fallback if fallback is not None else str(key or "")

    value = entry.get(language) or entry.get("fa") or entry.get("en")

    if value:

        return value

    return fallback if fallback is not None else str(key or "")


def _join(values, language):

    rendered = [value for value in values if value]

    if not rendered:

        return ""

    if language == "fa":

        return "، ".join(rendered)

    if len(rendered) == 1:

        return rendered[0]

    return ", ".join(rendered[:-1]) + " and " + rendered[-1]


# ==========================================================
# THE STRUCTURER
# ==========================================================

def structure_space_knowledge(
    project_id=None,
    space_id=None,
    language="fa",
    store=None,
    include_corpus=True,
):

    """Structure the teacher's recorded knowledge for ONE space, or None.

    READ-ONLY. Returns None when the project has no teacher-recorded
    knowledge for this space, so the caller keeps its existing behaviour.

    `include_corpus` adds the frozen space registry's own skeleton
    (category, privacy level, zone, adjacency) as a SEPARATELY LABELLED
    contribution — it never fills a teacher-owned field.
    """

    if not project_id or not space_id:

        return None

    lang = "fa" if str(language or "").startswith("fa") else "en"

    if store is None:

        from core.conversation.teaching_candidate_v1 import (
            teaching_candidate_store,
        )

        store = teaching_candidate_store

    try:

        entries = store.candidates(project_id)

    except Exception:

        return None

    candidates = [

        entry for entry in (entries or [])

        if (entry or {}).get("space_topic") == space_id

        and (entry or {}).get("provenance") == "HUMAN_TEACHER"

        and (entry or {}).get("status") in GROUNDABLE_STATUSES
    ]

    if not candidates:

        return None

    statements = _statements(candidates, space_id)

    corpus = _corpus(space_id) if include_corpus else {}

    structure = {

        "contract": CONTRACT,

        "version": VERSION,

        "space_id": space_id,

        "space_category": "",

        "definition": "",

        "users": [],

        "primary_goals": [],

        "privacy_level": "",

        "required_elements": [],

        "optional_elements": [],

        "spatial_relations": {"near": [], "avoid": []},

        "design_rules": [],

        "size_dependency": [],

        "uncertainties": [],

        "provenance": "HUMAN_TEACHER",
    }

    items = []

    field_sources = {}

    source_candidates = []

    def item(field, value, statement, kind=None, **extra):

        entry = {

            "field": field,

            "value": value,

            "statement": statement.get("text"),

            "candidate_id": statement.get("candidate_id"),

            "status": statement.get("status"),

            "confidence": statement.get("confidence"),

            "scope": statement.get("scope"),

            "provenance": "HUMAN_TEACHER",

        }

        if kind:

            entry["kind"] = kind

        entry.update(extra)

        items.append(entry)

        if statement.get("candidate_id") not in source_candidates:

            source_candidates.append(statement.get("candidate_id"))

        return entry

    users = []

    goals = []

    required = []

    optional = []

    near = []

    avoid = []

    rules = []

    dependencies = {}

    uncertainties = []

    definitions = []

    for statement in statements:

        text = statement["text"]

        form = _form(text)

        role = statement.get("role")

        knowledge_class = statement.get("knowledge_class")

        # The MEANING layer owns "this is a definition", not the clause
        # analyser: it labels a plain preference ("تخت دور از پنجره بهتر
        # است") as DEFINITION, which would silently suppress the rule the
        # teacher actually stated.
        is_definition = knowledge_class == "DEFINITION"

        polarity = statement.get("polarity")

        strength = _strength(form, role, polarity)

        produced = False

        # ---- the spaces this statement NAMES --------------------------
        #
        # The first mention is the SUBJECT of the statement, the rest are
        # relation targets. Neither is an element of this space: "the
        # bedrooms must be far from the living areas" does not say the
        # bedroom needs a living area. A word that is part of a space
        # NAME ("اتاق خواب" in "اتاق خواب مستر") is a space reference
        # too, never an element or a goal.
        named = _space_mentions(text)

        mentions = [space_id for space_id, _surface in named]

        mention_surfaces = [surface for _id, surface in named]

        relation_targets = []

        if len(mentions) > 1:

            relation_targets = [
                mention for mention in mentions[1:] if mention != space_id
            ]

        if is_definition:

            definitions.append(statement)

            item("definition", text, statement)

            produced = True

        # ---- occupants ------------------------------------------------
        #
        # Only when the teacher ATTACHES them to this space: inside the
        # short window that follows a "for / مخصوص" marker or the space's
        # OWN name (the corpus aliases plus the exact name this statement
        # used), or in a CLEAN definition of this space.
        own_surfaces = [
            surface for mention_id, surface in named if mention_id == space_id
        ]

        own_surfaces.extend(_occupant_anchors(space_id))

        user_hits = _occupants_after_marker(form, own_surfaces)

        if not user_hits:

            other_spaces = [
                mention for mention in mentions if mention != space_id
            ]

            if is_definition and not other_spaces:

                user_hits = _hits(form, OCCUPANT_LEXICON)

        for occupant in user_hits:

            if occupant not in users:

                users.append(occupant)

                item("users", occupant, statement)

                produced = True

        for goal, goal_surface in _hits_with_surface(form, GOAL_LEXICON):

            if _inside_a_space_name(goal_surface, mention_surfaces):

                continue

            if goal not in goals:

                goals.append(goal)

                item("primary_goals", goal, statement)

                produced = True

        for requirement in _hits(form, REQUIREMENT_LEXICON):

            if strength == "required":

                if requirement not in required:

                    required.append(requirement)

                    item(
                        "required_elements", requirement, statement,
                        kind="requirement",
                    )

                    for implied in REQUIREMENT_IMPLIES.get(requirement, ()):

                        if implied not in required:

                            required.append(implied)

                            item(
                                "required_elements", implied, statement,
                                kind="implied_element",
                                implied_by=requirement,
                            )

            elif requirement not in optional:

                optional.append(requirement)

                item(
                    "optional_elements", requirement, statement,
                    kind="requirement",
                )

            produced = True

        matched_rules = _rules(form, is_definition)

        # A statement that states a RULE about an element (the bed, the
        # door, the window) does not also claim that element: the rule is
        # already recorded, and "the bed is not visible from the door"
        # must not turn the door into an optional element of the space.
        element_source = not matched_rules

        for element_id, surface, modifier in _elements(text):

            # A DEFINITION says what the space IS, never what it holds.
            if is_definition or not element_source:

                break

            # A space the statement names (subject or target) is a
            # relation participant, not an element of this space, and a
            # word inside a space NAME is a space reference.
            element_space = _entity_space_id(element_id)

            if element_space and element_space in mentions:

                continue

            if _inside_a_space_name(surface, mention_surfaces):

                continue

            extra = {"surface": surface}

            if modifier:

                extra["modifier"] = modifier

            if strength == "required":

                if element_id not in required:

                    required.append(element_id)

                    item(
                        "required_elements", element_id, statement,
                        kind="element", **extra
                    )

            elif element_id not in optional and element_id not in required:

                optional.append(element_id)

                item(
                    "optional_elements", element_id, statement,
                    kind="element", **extra
                )

            produced = True

        for pattern in matched_rules:

            rule = {

                "rule": pattern["rule"],

                "type": pattern["type"],

                "strength": (
                    "rule"
                    if (role == "RULE" or knowledge_class == "DESIGN_RULE")
                    else "observation"
                ),

                "sources": [{
                    "statement": text,
                    "candidate_id": statement.get("candidate_id"),
                    "status": statement.get("status"),
                    "confidence": statement.get("confidence"),
                }],
            }

            existing = next(
                (
                    entry for entry in rules
                    if entry["rule"] == rule["rule"]
                ),
                None,
            )

            if existing is None:

                rules.append(rule)

            else:

                if rule["strength"] == "rule":

                    existing["strength"] = "rule"

                if not any(
                    source.get("statement") == text
                    for source in existing["sources"]
                ):

                    existing["sources"].extend(rule["sources"])

            item(
                "design_rules", pattern["rule"], statement,
                kind="rule", type=pattern["type"],
            )

            produced = True

        # ---- relations: SPACE targets only ------------------------------

        relations = []

        try:

            from core.conversation.teaching_meaning_v1 import (
                extract_meaning,
            )

            relations = extract_meaning(text).get("relations") or []

        except Exception:

            relations = []

        if relations and relation_targets:

            if "near" in relations or "connected" in relations:

                for target in relation_targets:

                    if target not in near:

                        near.append(target)

                        item(
                            "spatial_relations.near", target, statement,
                            kind="space",
                        )

                        produced = True

            if "far" in relations:

                for target in relation_targets:

                    if target not in avoid:

                        avoid.append(target)

                        item(
                            "spatial_relations.avoid", target, statement,
                            kind="space",
                        )

                        produced = True

        conditions = _conditions(form)

        if conditions:

            elements = [
                element_id for element_id, _s, _m in _elements(text)
            ]

            for condition in conditions:

                if condition == "area_dependent":

                    continue

                bucket = dependencies.setdefault(condition, [])

                for element_id in elements:

                    if element_id not in bucket:

                        bucket.append(element_id)

                item(
                    "size_dependency", condition, statement,
                    kind="condition", elements=elements,
                )

                produced = True

        conditional = any(
            _contains(form, marker) for marker in CONDITIONAL_MARKERS
        )

        if conditional and not conditions:

            uncertainties.append({
                "statement": text,
                "candidate_id": statement.get("candidate_id"),
                "status": statement.get("status"),
                "confidence": statement.get("confidence"),
                "reason": "conditional",
            })

        elif not produced:

            uncertainties.append({
                "statement": text,
                "candidate_id": statement.get("candidate_id"),
                "status": statement.get("status"),
                "confidence": statement.get("confidence"),
                "reason": "unstructured",
            })

    # ---- definition --------------------------------------------------

    if definitions:

        structure["definition"] = definitions[0]["text"]

        field_sources["definition"] = "HUMAN_TEACHER"

    elif corpus.get("functional_definition"):

        structure["definition"] = corpus["functional_definition"]

        field_sources["definition"] = "CORPUS"

    # ---- category ----------------------------------------------------

    category = ""

    for statement in statements:

        form = _form(statement["text"])

        if _contains(form, "خصوصی") or _contains(form, "حریم خصوصی"):

            category = "private"

            field_sources["space_category"] = "HUMAN_TEACHER"

            break

        if _contains(form, "عمومی"):

            category = "public"

            field_sources["space_category"] = "HUMAN_TEACHER"

            break

    if not category:

        corpus_category = str(corpus.get("category") or "").lower()

        if corpus_category:

            category = corpus_category

            field_sources["space_category"] = "CORPUS"

    structure["space_category"] = category

    privacy = str(corpus.get("privacy_level") or "").lower()

    structure["privacy_level"] = privacy

    if privacy:

        field_sources["privacy_level"] = "CORPUS"

    structure["users"] = users

    structure["primary_goals"] = goals

    # An element the teacher says the space NEEDS is never also listed as
    # optional.
    optional = [key for key in optional if key not in required]

    structure["required_elements"] = required

    structure["optional_elements"] = optional

    if users:

        field_sources["users"] = "HUMAN_TEACHER"

    if goals:

        field_sources["primary_goals"] = "HUMAN_TEACHER"

    if required:

        field_sources["required_elements"] = "HUMAN_TEACHER"

    if optional:

        field_sources["optional_elements"] = "HUMAN_TEACHER"

    # ---- adjacency: corpus skeleton + teacher relations ---------------

    for target in corpus.get("typical_adjacent") or []:

        if target not in near:

            near.append(target)

            items.append({
                "field": "spatial_relations.near",
                "value": target,
                "statement": None,
                "candidate_id": None,
                "status": None,
                "confidence": None,
                "kind": "space",
                "provenance": "CORPUS",
            })

    for target in corpus.get("discouraged_adjacent") or []:

        if target not in avoid:

            avoid.append(target)

            items.append({
                "field": "spatial_relations.avoid",
                "value": target,
                "statement": None,
                "candidate_id": None,
                "status": None,
                "confidence": None,
                "kind": "space",
                "provenance": "CORPUS",
            })

    structure["spatial_relations"] = {"near": near, "avoid": avoid}

    if near:

        field_sources["spatial_relations.near"] = (
            "HUMAN_TEACHER+CORPUS"
            if any(
                entry["provenance"] == "HUMAN_TEACHER"
                for entry in items
                if entry["field"] == "spatial_relations.near"
            )
            else "CORPUS"
        )

    if avoid:

        field_sources["spatial_relations.avoid"] = (
            "HUMAN_TEACHER+CORPUS"
            if any(
                entry["provenance"] == "HUMAN_TEACHER"
                for entry in items
                if entry["field"] == "spatial_relations.avoid"
            )
            else "CORPUS"
        )

    structure["design_rules"] = rules

    if rules:

        field_sources["design_rules"] = "HUMAN_TEACHER"

    structure["size_dependency"] = [
        {"condition": condition, "elements": elements}
        for condition, elements in dependencies.items()
    ]

    if dependencies:

        field_sources["size_dependency"] = "HUMAN_TEACHER"

    structure["uncertainties"] = uncertainties

    if uncertainties:

        field_sources["uncertainties"] = "HUMAN_TEACHER"

    # ---- additive, read-only bookkeeping ------------------------------

    structure["space_label"] = _label(space_id, lang)

    structure["definition_source"] = field_sources.get("definition", "")

    structure["definitions"] = [
        {
            "statement": statement["text"],
            "candidate_id": statement.get("candidate_id"),
            "status": statement.get("status"),
            "confidence": statement.get("confidence"),
        }
        for statement in definitions
    ]

    structure["zone"] = corpus.get("zone")

    structure["functional_role"] = corpus.get("functional_role")

    structure["functional_definition"] = corpus.get("functional_definition")

    structure["daylight_requirement"] = corpus.get("daylight_requirement")

    structure["acoustic_privacy_sensitivity"] = corpus.get(
        "acoustic_privacy_sensitivity"
    )

    structure["items"] = items

    structure["field_sources"] = field_sources

    structure["sources"] = {

        "teaching_candidates": source_candidates,

        "corpus": corpus.get("sources") or [],

        "corpus_used": bool(corpus),
    }

    structure["statement_count"] = len(statements)

    structure["status"] = "success"

    structure["language"] = lang

    # A structure is a READ. Nothing is created, learned or rendered.
    structure["is_knowledge"] = False
    structure["is_action"] = False
    structure["candidate_created"] = False
    structure["learned_anything"] = False
    structure["stored_teaching"] = False
    structure["permanent_learning_implemented"] = False
    structure["promoted"] = False
    structure["curriculum_modified"] = False
    structure["architecture_rules_modified"] = False
    structure["teaching_memory_modified"] = False
    structure["routed_to_execute"] = False
    structure["llm_used"] = False
    structure["network_used"] = False
    structure["render_requested"] = False
    structure["comfy_invoked"] = False

    return structure


# ==========================================================
# ANSWER-STYLE RENDERING
# ==========================================================

def render_structured_answer(structure, language="fa"):

    """The structure as the teacher's answer style, or "".

    Deterministic: every line is a template filled from the structure.
    Nothing is inferred here, and an empty structure renders nothing.
    """

    if not structure:

        return ""

    lang = "fa" if str(language or "").startswith("fa") else "en"

    text = STRUCTURE_PHRASES[lang]

    # The label follows the RENDERED language, not the language the
    # structure happened to be built in.
    label = _label(structure.get("space_id"), lang) or (
        structure.get("space_label") or ""
    )

    lines = [text["header"] % label]

    definition = structure.get("definition") or ""

    if definition:

        lines.append(text["definition"] % definition)

    users = [
        _display(OCCUPANT_DISPLAY, key, lang)
        for key in structure.get("users") or []
    ]

    category = structure.get("space_category") or ""

    category_label = _display(
        SPACE_NAME_OVERRIDES, category, lang, fallback=category
    )

    if category_label and users:

        lines.append(
            text["category_users"] % (category_label, _join(users, lang))
        )

    elif category_label:

        lines.append(
            (text["category_users"] % (category_label, "")).rstrip()
        )

    goals = [
        _display(GOAL_DISPLAY, key, lang)
        for key in structure.get("primary_goals") or []
    ]

    if goals:

        lines.append(text["goals"] % _join(goals, lang))

    required = [
        _display(
            REQUIREMENT_DISPLAY if key in REQUIREMENT_DISPLAY else ELEMENT_DISPLAY,
            key,
            lang,
        )
        for key in structure.get("required_elements") or []
    ]

    if required:

        lines.append(text["required"] % _join(required, lang))

    optional = [
        _display(
            REQUIREMENT_DISPLAY if key in REQUIREMENT_DISPLAY else ELEMENT_DISPLAY,
            key,
            lang,
        )
        for key in structure.get("optional_elements") or []
    ]

    if optional:

        lines.append(text["optional"] % _join(optional, lang))

    near = [
        _label(key, lang) for key in (structure.get("spatial_relations") or {}).get("near") or []
    ]

    if near:

        lines.append(text["near"] % _join(near, lang))

    avoid = [
        _label(key, lang) for key in (structure.get("spatial_relations") or {}).get("avoid") or []
    ]

    if avoid:

        lines.append(text["avoid"] % _join(avoid, lang))

    for rule in structure.get("design_rules") or []:

        rendered = _display(RULE_DISPLAY, rule.get("rule"), lang)

        if not rendered:

            continue

        if rule.get("strength") == "observation" and lang == "fa":

            rendered = rendered + " (به‌عنوان مشاهده، نه قانون قطعی)"

        elif rule.get("strength") == "observation":

            rendered = rendered + " (as an observation, not a definitive rule)"

        if lang == "en":

            rendered = rendered[:1].upper() + rendered[1:]

        lines.append(text["rule"] % rendered)

    for dependency in structure.get("size_dependency") or []:

        condition = _display(
            CONDITION_DISPLAY, dependency.get("condition"), lang
        )

        elements = [
            _display(
                REQUIREMENT_DISPLAY if key in REQUIREMENT_DISPLAY else ELEMENT_DISPLAY,
                key,
                lang,
            )
            for key in dependency.get("elements") or []
        ]

        if condition and elements:

            lines.append(
                text["condition"] % (condition, _join(elements, lang))
            )

    uncertainties = structure.get("uncertainties") or []

    # The section is always part of the answer style: what is NOT yet a
    # definitive rule is stated even when the list is empty, because every
    # recorded item is still only "received".
    lines.append(text["uncertain_header"])

    if uncertainties:

        for entry in uncertainties:

            status = (
                text["status_pending"]
                if entry.get("status") == "needs_confirmation"
                else text["status_observed"]
            )

            lines.append(
                text["uncertain_item"]
                % (entry.get("statement") or "", text["source_human"], status)
            )

    else:

        lines.append(text["uncertain_none"])

    lines.append(text["note"])

    rendered = "\n".join(line for line in lines if line)

    return rendered


# ==========================================================
# ARCHITECTURAL KNOWLEDGE CANDIDATE -> STRUCTURE V1
# ==========================================================


def _candidate_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return deepcopy(value)
    if isinstance(value, tuple):
        return deepcopy(list(value))
    if value is None:
        return []
    return [deepcopy(value)]


def _candidate_unique(values: Iterable[Any]) -> List[Any]:
    result = []
    for value in values:
        if value not in result:
            result.append(deepcopy(value))
    return result


def _candidate_claim_ids(item: Dict[str, Any]) -> List[str]:
    return _candidate_list(item.get("source_claim_ids"))


def _candidate_evidence(item: Dict[str, Any]) -> List[Any]:
    return _candidate_list(item.get("evidence_reference"))


def _candidate_statuses(item: Dict[str, Any]) -> List[Any]:
    return _candidate_list(item.get("grounding_status"))


def _validate_knowledge_candidate(candidate: Any) -> Dict[str, Any]:
    if not isinstance(candidate, dict):
        raise TypeError(
            "ArchitecturalKnowledgeStructureV1 requires an "
            "ArchitecturalKnowledgeCandidateV1 dict"
        )
    if candidate.get("contract") != CANDIDATE_CONTRACT:
        raise ValueError(
            "ArchitecturalKnowledgeStructureV1 accepts only "
            "ArchitecturalKnowledgeCandidateV1"
        )
    if candidate.get("version") != CANDIDATE_VERSION:
        raise ValueError(
            "ArchitecturalKnowledgeStructureV1 requires candidate version 1.0"
        )
    return candidate


def _candidate_uncertainty(
    candidate: Dict[str, Any],
    items: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    source = candidate.get("uncertainty")
    result = deepcopy(source) if isinstance(source, dict) else {}
    result["items"] = [
        deepcopy(item["uncertainty"])
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("uncertainty"), dict)
    ]
    return result


def _candidate_pattern(item: Dict[str, Any]) -> Dict[str, Any]:
    relationship = item.get("pattern")
    associated_element = {
        "sleeping_storage_relation": "storage_associated",
        "sleeping_sanitary_relation": "sanitary_service_associated",
    }.get(relationship)
    return {
        "pattern_type": "space_element_association",
        "pattern": relationship,
        "space": item.get("space"),
        "associated_element": associated_element,
        "status": "observed_pattern",
        "source_claim_ids": _candidate_claim_ids(item),
        "evidence_reference": _candidate_evidence(item),
        "grounding_status": _candidate_statuses(item),
        "interpretation_basis": _candidate_list(
            item.get("interpretation_basis")
        ),
        "uncertainty": deepcopy(item.get("uncertainty") or {}),
    }


def _candidate_space_model(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "space": item.get("space"),
        "status": "observed_pattern",
        "source_claim_ids": _candidate_claim_ids(item),
        "evidence_reference": _candidate_evidence(item),
        "grounding_status": _candidate_statuses(item),
        "interpretation_basis": _candidate_list(
            item.get("interpretation_basis")
        ),
        "uncertainty": deepcopy(item.get("uncertainty") or {}),
    }


def _candidate_element_model(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "space": item.get("space"),
        "element": item.get("element"),
        "association": item.get("association"),
        "status": "observed_pattern",
        "source_claim_ids": _candidate_claim_ids(item),
        "evidence_reference": _candidate_evidence(item),
        "grounding_status": _candidate_statuses(item),
        "interpretation_basis": _candidate_list(
            item.get("interpretation_basis")
        ),
        "uncertainty": deepcopy(item.get("uncertainty") or {}),
    }


def _candidate_relationship_model(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "relationship_type": item.get("relationship_type"),
        "status": "observed_pattern",
        "source_claim_ids": _candidate_claim_ids(item),
        "evidence_reference": _candidate_evidence(item),
        "grounding_status": _candidate_statuses(item),
        "uncertainty": deepcopy(item.get("uncertainty") or {}),
    }


def build_architectural_knowledge_structure_v1(
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    """Structure only a transient ArchitecturalKnowledgeCandidateV1."""
    source = _validate_knowledge_candidate(candidate)
    patterns = [
        _candidate_pattern(item)
        for item in _candidate_list(source.get("patterns"))
        if isinstance(item, dict)
    ]
    space_models = [
        _candidate_space_model(item)
        for item in _candidate_list(source.get("space_associations"))
        if isinstance(item, dict)
    ]
    element_models = [
        _candidate_element_model(item)
        for item in _candidate_list(source.get("element_associations"))
        if isinstance(item, dict)
    ]
    relationship_models = [
        _candidate_relationship_model(item)
        for item in _candidate_list(source.get("semantic_relationships"))
        if isinstance(item, dict)
    ]

    source_info = source.get("source") or {}
    evidence_chain = source.get("evidence_chain") or {}
    structure = {
        "contract": CONTRACT,
        "version": VERSION,
        "patterns": patterns,
        "space_models": space_models,
        "element_models": element_models,
        "relationship_models": relationship_models,
        "evidence_basis": {
            "source_contract": source_info.get("contract"),
            "source_version": source_info.get("version"),
            "claim_ids": _candidate_unique(
                source_info.get("claim_ids")
                or evidence_chain.get("claim_ids")
                or []
            ),
            "source_evidence": _candidate_unique(
                evidence_chain.get("source_evidence") or []
            ),
            "grounding_status": _candidate_unique(
                evidence_chain.get("grounding_status") or []
            ),
            "interpretation_basis": _candidate_unique(
                evidence_chain.get("interpretation_basis") or []
            ),
        },
        "uncertainty": _candidate_uncertainty(
            source,
            patterns + space_models + element_models + relationship_models,
        ),
        "non_claims": [
            "not_design_rule",
            "not_permanent_knowledge",
            "not_memory",
            "not_geometry",
        ],
        "is_training_ready": True,
        "persistent": False,
    }
    return structure
