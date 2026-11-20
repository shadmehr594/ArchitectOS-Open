"""Architectural Intent Understanding (V1).

Reads a NATURAL project request and structures it as ARCHITECTURAL INTENT,
before any design work.

    "یک خانه کوچک برای خانواده ۴ نفره می‌خواهم، نور خوب داشته باشد،
     حریم مناسب باشد و پارکینگ هم داشته باشد."
              ↓
    intent · requirements · constraints · preferences · priorities
    fixed elements · flexible elements
              ↓
    associative retrieval  ->  reasoning  ->  reasoning quality
              ↓
    an understanding (conflicts REPORTED, never solved)

It
    reads a natural request (no form, no JSON, no questionnaire)
    separates requirement · constraint · preference · priority · fixed · flexible
    connects the request to the CONFIRMED knowledge
    identifies a conflict — and never solves it

It MUST NOT
    generate a plan / geometry / CAD / BIM / IFC / a render / an image
    decide the design
    invent a requirement the human did not state

Dependency direction

    this module  ->  core.conversation.clause_analysis_v1                     (clause segmentation)
    this module  ->  core.knowledge.architectural_associative_retrieval_v1    (retrieval + surfaces)
    this module  ->  core.knowledge.architectural_reasoning_v1                (fixed/flexible tokens)
    this module  ->  core.knowledge.architectural_reasoning_quality_v1        (dimensions + context)
    this module  ->  core.vision / core.render / core.bim / core.geometry / core.runtime  FORBIDDEN
"""

from __future__ import annotations


import re

from typing import Any, Dict, List, Optional


from core.conversation.clause_analysis_v1 import segment

from core.knowledge.architectural_associative_retrieval_v1 import (
    SPACE_SURFACE,
    associative_retrieve,
)

from core.knowledge.architectural_reasoning_v1 import (
    FIXED_TOKENS,
    FLEXIBLE_TOKENS,
    reason_design,
)

from core.knowledge.architectural_reasoning_quality_v1 import improve_reasoning


CONTRACT = "ArchitecturalIntentUnderstandingV1"

VERSION = "1.0"


# ----------------------------------------------------------
# the building type (a closed surface vocabulary)
# ----------------------------------------------------------

BUILDING_TYPE_SURFACE: Dict[str, str] = {
    # specific types FIRST — "خانه دوبلکس" must read as duplex, not residential
    "آپارتمان": "apartment",
    "اپارتمان": "apartment",
    "apartment": "apartment",
    "دوبلکس": "duplex",
    "duplex": "duplex",
    "ویلا": "villa",
    "villa": "villa",
    "پنت‌هاوس": "penthouse",
    "پنتهاوس": "penthouse",
    "penthouse": "penthouse",
    "تجاری": "commercial",
    "اداری": "commercial",
    "commercial": "commercial",
    "مختلط": "mixed_use",
    "mixed use": "mixed_use",
    # the generic type LAST
    "خانه": "residential",
    "مسکونی": "residential",
    "residential": "residential",
}


# ----------------------------------------------------------
# the intent slots (closed marker tables)
# ----------------------------------------------------------

CONSTRAINT_MARKERS = (
    "کوچک", "محدود", "زمین کوچک", "خانه کوچک", "زیربنا کم", "کم باشد",
    "small", "limited", "tight", "constraint",
)

PREFERENCE_MARKERS = (
    "دوست دارم", "ترجیح می", "می پسندم", "میپسندم", "علاقه دارم",
    "prefer", "i like", "i want", "would like", "my preference",
)

PRIORITY_MARKERS = (
    "حریم", "نور", "روشنایی", "گردش", "ارتباط", "کیفیت", "کارایی", "خصوصی",
    "privacy", "light", "daylight", "circulation", "quality", "efficiency",
)

REQUIREMENT_MARKERS = (
    "لازم است", "نیاز دارم", "نیاز داریم", "نیاز است", "داشته باشد", "داشته باشه",
    "باید باشد", "می خواهم داشته",
    "need", "required", "require", "must have",
)

# A STRONG requirement is stated as a need; a weaker one ("... داشته باشد") only
# counts when the clause also names a program space — so "نور خوب داشته باشد"
# stays a PRIORITY while "پارکینگ داشته باشد" becomes a REQUIREMENT.
STRONG_REQUIREMENT_MARKERS = (
    "لازم است", "نیاز دارم", "نیاز داریم", "نیاز است",
    "must have", "required", "require",
)

# CONSTRAINT wins over a preference (a small site is a fact, not a wish);
# a PREFERENCE wins over a priority (a wish is explicit);
# a PRIORITY wins over a requirement (a quality the human stresses).
SLOT_ORDER = (
    ("constraint", CONSTRAINT_MARKERS),
    ("preference", PREFERENCE_MARKERS),
    ("priority", PRIORITY_MARKERS),
    ("requirement", REQUIREMENT_MARKERS),
)


SLOT_LABELS = {
    "fa": {
        "intent": "نوع پروژه",
        "requirement": "نیازها",
        "constraint": "محدودیت‌ها",
        "preference": "ترجیح‌ها",
        "priority": "اولویت‌ها",
        "fixed_elements": "عناصر ثابت",
        "flexible_elements": "عناصر انعطاف‌پذیر",
    },
    "en": {
        "intent": "Project type",
        "requirement": "Requirements",
        "constraint": "Constraints",
        "preference": "Preferences",
        "priority": "Priorities",
        "fixed_elements": "Fixed elements",
        "flexible_elements": "Flexible elements",
    },
}


UNDERSTANDING_HEADER = {
    "fa": "برداشت من از درخواست شما:",
    "en": "This is my reading of your request:",
}

UNDERSTANDING_FOOTER = {
    "fa": "این برداشت را با دانش تأییدشدهٔ شما مقایسه کردم؛ تصمیم نهایی با معمار است.",
    "en": "I compared this with your confirmed knowledge; the architect makes the final decision.",
}


_NON_CLAIMS = {
    "not_a_design": True,
    "not_a_plan": True,
    "not_geometry": True,
    "not_cad_or_bim": True,
    "not_invented": True,
    "confirmed_memory_only": True,
    "human_decides": True,
}


class ArchitecturalIntentUnderstandingError(ValueError):
    """Raised when the intent boundary is misused."""


def _norm(value) -> str:

    text = str(value or "").lower()

    text = text.replace("\u200c", " ")

    text = text.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")

    return " ".join(text.split())


def _has_any(text, markers) -> bool:

    form = _norm(text)

    return any(_norm(marker) in form for marker in markers)


def _language(value) -> str:

    return "en" if str(value or "").lower().startswith("en") else "fa"


def _ascii_digits(text) -> str:

    result = []

    for char in str(text or ""):

        code = ord(char)

        if 0x06F0 <= code <= 0x06F9:          # Persian digits

            result.append(chr(ord("0") + code - 0x06F0))

        elif 0x0660 <= code <= 0x0669:        # Arabic-Indic digits

            result.append(chr(ord("0") + code - 0x0660))

        else:

            result.append(char)

    return "".join(result)


def _unique(values) -> List[str]:

    result: List[str] = []

    for value in values:

        if value and value not in result:

            result.append(value)

    return result


# ----------------------------------------------------------
# the intent slots
# ----------------------------------------------------------

def _classify_clause(text) -> Optional[str]:

    for slot, markers in SLOT_ORDER:

        if _has_any(text, markers):

            return slot

    return None


def detect_building_type(text) -> Optional[str]:

    form = _norm(text)

    for surface, building_type in BUILDING_TYPE_SURFACE.items():

        if _norm(surface) in form:

            return building_type

    return None


NUMBER_WORDS = {
    "یک": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5, "شش": 6, "هفت": 7,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
}


def detect_household(text) -> Dict[str, Any]:

    form = _norm(_ascii_digits(text))

    household: Dict[str, Any] = {}

    match = re.search(r"([0-9]+)\s*(?:نفره|نفر|member|person)", form)

    if match:

        household["size"] = int(match.group(1))

    children = re.search(r"(?:با\s*)?([0-9]+)\s*(?:بچه|فرزند|child|kid)", form)

    if children:

        household["children"] = int(children.group(1))

    if "children" not in household:

        for word, value in NUMBER_WORDS.items():

            if re.search(r"%s\s*(?:بچه|فرزند|child|kid)" % _norm(word), form):

                household["children"] = value

                break

    return household


def detect_program(text) -> List[str]:

    form = _norm(text)

    program: List[str] = []

    for surface, token in SPACE_SURFACE.items():

        if _norm(surface) in form and token not in program:

            program.append(token)

    return program


def detect_elements(text, vocabulary) -> List[str]:

    """Resolve a Persian/English surface form, then test the token."""

    form = _norm(text)

    resolved: List[str] = []

    for surface, token in SPACE_SURFACE.items():

        if _norm(surface) in form and token not in resolved:

            resolved.append(token)

    for token in resolved:

        for candidate in vocabulary:

            if _norm(candidate).replace("_", " ") == _norm(token).replace("_", " "):

                if candidate not in resolved:

                    resolved.append(candidate)

    return [value for value in resolved if value in vocabulary]


# ----------------------------------------------------------
# the natural understanding
# ----------------------------------------------------------

def build_natural_understanding(result, *, language="fa") -> str:

    lang = _language(language)

    labels = SLOT_LABELS[lang]

    lines = [UNDERSTANDING_HEADER[lang]]

    intent = result["intent"]

    if intent.get("building_type"):

        text = str(intent["building_type"])

        if intent.get("household", {}).get("size"):

            text += " — %d" % intent["household"]["size"]

        lines.append("• %s: %s" % (labels["intent"], text))

    for slot in ("requirement", "constraint", "preference", "priority"):

        values = result[slot]

        if values:

            lines.append("• %s: %s" % (labels[slot], "؛ ".join(str(v) for v in values)))

    for slot in ("fixed_elements", "flexible_elements"):

        values = result[slot]

        if values:

            lines.append("• %s: %s" % (labels[slot], "؛ ".join(str(v) for v in values)))

    lines.append(UNDERSTANDING_FOOTER[lang])

    return "\n".join(lines)


# ----------------------------------------------------------
# the single public entry
# ----------------------------------------------------------

def understand_intent(request, *, memory=None, language=None) -> Dict[str, Any]:

    """Read a natural project request as architectural intent."""

    if not isinstance(request, str) or not request.strip():

        raise ArchitecturalIntentUnderstandingError(
            "intent understanding needs a non-empty request"
        )

    lang = _language(language or ("en" if request.isascii() else "fa"))

    clauses = [
        str(c.get("text") or "").strip()
        for c in segment(request)
        if isinstance(c, dict)
    ]

    clauses = [c for c in clauses if c]

    if not clauses:

        clauses = [request.strip()]

    slots: Dict[str, List[str]] = {
        "requirement": [], "constraint": [], "preference": [], "priority": [],
    }

    for clause in clauses:

        # a clause may fill MORE than one slot — "حریم مناسب باشد و پارکینگ
        # داشته باشد" is both a PRIORITY and a REQUIREMENT
        if _has_any(clause, CONSTRAINT_MARKERS) and clause not in slots["constraint"]:

            slots["constraint"].append(clause)

        if _has_any(clause, PREFERENCE_MARKERS) and clause not in slots["preference"]:

            slots["preference"].append(clause)

        if _has_any(clause, PRIORITY_MARKERS) and clause not in slots["priority"]:

            slots["priority"].append(clause)

        strong = _has_any(clause, STRONG_REQUIREMENT_MARKERS)

        weak = bool(detect_program(clause)) and _has_any(clause, REQUIREMENT_MARKERS)

        if (strong or weak) and clause not in slots["requirement"]:

            slots["requirement"].append(clause)

    intent = {
        "building_type": detect_building_type(request),
        "household": detect_household(request),
        "program": detect_program(request),
    }

    fixed_elements = detect_elements(request, FIXED_TOKENS)

    flexible_elements = detect_elements(request, FLEXIBLE_TOKENS)

    # ---- connect to the CONFIRMED knowledge ----
    retrieval: Dict[str, Any] = {}

    reasoning: Dict[str, Any] = {}

    quality: Dict[str, Any] = {}

    if memory is not None:

        retrieval = associative_retrieve(request, memory, language=lang)

        context = {
            "building_type": intent["building_type"],
            "area_limitation": bool(slots["constraint"]),
            "user_requirements": slots["requirement"] + slots["preference"],
            "topic": " ".join(
                intent["program"]
                + retrieval.get("topics", {}).get("spaces", [])
                + retrieval.get("topics", {}).get("concepts", [])
            ),
        }

        reasoning = reason_design(context, retrieval=retrieval)

        quality = improve_reasoning(
            reasoning, retrieval=retrieval, memory=memory, language=lang
        )

    result: Dict[str, Any] = {
        "contract": CONTRACT,
        "version": VERSION,
        "language": lang,
        "request": str(request),
        "intent": intent,
        "requirement": slots["requirement"],
        "constraint": slots["constraint"],
        "preference": slots["preference"],
        "priority": slots["priority"],
        "fixed_elements": fixed_elements,
        "flexible_elements": flexible_elements,
        "retrieved_knowledge": list(retrieval.get("entries") or []),
        "retrieval_ids": list(retrieval.get("knowledge_ids") or []),
        "dimensions": list(quality.get("dimensions") or []),
        "conflicts": list(quality.get("conflicts") or []),
        "context_evaluation": list(quality.get("context_evaluation") or []),
        "unresolved_questions": list(reasoning.get("unresolved_questions") or []),
        "human_review_required": True,
        "is_final_solution": False,
        "design_generated": False,
        "non_claims": dict(_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }

    result["natural_understanding"] = build_natural_understanding(result, language=lang)

    return result


class ArchitecturalIntentUnderstandingV1:

    """The intent-understanding boundary. Stateless, deterministic."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    GENERATES_DESIGN = False

    GENERATES_GEOMETRY = False

    DECIDES_FINAL_DESIGN = False

    def understand(self, request, **kwargs) -> Dict[str, Any]:

        return understand_intent(request, **kwargs)

    def __repr__(self):

        return "ArchitecturalIntentUnderstandingV1(understanding_only=True)"


architectural_intent_understanding = ArchitecturalIntentUnderstandingV1()
