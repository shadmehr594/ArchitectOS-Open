"""Architectural Knowledge Classification (V1).

The missing intelligence layer between the extraction candidate and human
validation. It answers ONE question:

    "What TYPE of architectural knowledge is this?"

    Human Teaching -> Knowledge Extraction Candidate -> [THIS LAYER]
        -> Human Validation -> Architectural Knowledge Memory

It
    reads a candidate (or a natural teaching statement)
    classifies the knowledge TYPE (seven declared types)
    explains the classification NATURALLY (no schema, no field names)
    PROPOSES memory destinations — it writes nothing

It MUST NOT
    create a design / a plan / a geometry / a final decision
    optimize a layout / replace the architect
    write permanent memory automatically
    turn a human statement into an absolute law

Dependency direction

    this module  ->  core.conversation.teaching_meaning_v1                    (domains)
    this module  ->  core.knowledge.architectural_knowledge_extraction_engine_v1  (facets)
    this module  ->  core.knowledge.architectural_knowledge_memory_v1          (routing tables)
    this module  ->  core.knowledge.human_knowledge_validation_loop_v1         (facet labels)
    this module  ->  core.vision / core.render / core.bim / core.geometry / core.runtime  FORBIDDEN
"""

from __future__ import annotations


from typing import Any, Dict, List, Optional


from core.conversation.teaching_meaning_v1 import extract_meaning

from core.knowledge.architectural_knowledge_extraction_engine_v1 import (
    CONTRACT as CANDIDATE_CONTRACT,
    FACET_KEYS,
    extract_architectural_knowledge_candidate_v1,
)

from core.knowledge.human_knowledge_validation_loop_v1 import FACET_LABELS

from core.knowledge.architectural_knowledge_memory_v1 import (
    route_confirmed_entry,
)


CONTRACT = "ArchitecturalKnowledgeClassificationResultV1"

VERSION = "1.0"


# ----------------------------------------------------------
# TASK 2 — the seven knowledge types
# ----------------------------------------------------------

TYPE_PRINCIPLE = "PRINCIPLE"
TYPE_RELATIONSHIP = "RELATIONSHIP"
TYPE_CONSTRAINT = "CONSTRAINT"
TYPE_PREFERENCE = "PREFERENCE"
TYPE_EXAMPLE = "EXAMPLE"
TYPE_EXCEPTION = "EXCEPTION"
TYPE_CONTEXT_RULE = "CONTEXT_RULE"


KNOWLEDGE_TYPES = (
    TYPE_PRINCIPLE,
    TYPE_RELATIONSHIP,
    TYPE_CONSTRAINT,
    TYPE_PREFERENCE,
    TYPE_EXAMPLE,
    TYPE_EXCEPTION,
    TYPE_CONTEXT_RULE,
)


# ----------------------------------------------------------
# closed marker tables (they only RECOGNISE words already present)
# ----------------------------------------------------------

PREFERENCE_MARKERS = (
    "ترجیح می", "دوست دارم", "می پسندم", "میپسندم", "علاقه دارم", "من ترجیح",
    "i prefer", "i'd prefer", "i would prefer", "i like", "i want",
    "my preference", "i love",
)

EXAMPLE_MARKERS = (
    "این پلان", "این مثال", "در این پلان", "در این مثال", "این مورد",
    "مثلا", "مثال", "برای مثال", "در این پروژه",
    "this plan", "this example", "for example", "e.g.", "in this case",
    "case study",
)

CONSTRAINT_MARKERS = (
    "وجود ندارد", "امکان ندارد", "امکان پذیر نیست", "نمی شود", "نمیشود",
    "محدودیت", "مجبور", "الزام پروژه", "در این زمین",
    "cannot", "can not", "not possible", "constraint", "limited to",
    "restricted", "no space for",
)

EXCEPTION_MARKERS = (
    "شاید", "ممکن است", "ممکنه", "مگر", "به جز", "استثنا", "حذف",
    "unless", "except", "might", "may be removed", "may be eliminated",
    "does not always",
)

CONDITION_MARKERS = (
    "اگر", "وقتی", "زمانی که", "در ساختمان", "در واحد", "در پروژه",
    "در صورت", "در زمین", "در طبقات", "در طبقه",
    "when", "if ", "in a ", "for a ",
)

RULE_MARKERS = (
    "باید", "لازم است", "لازم", "should", "must", "required", "shall",
)


# The classification priority. FIRST match wins.
#   a preference must never be mistaken for a rule;
#   an exception must beat a context rule.
TYPE_PRIORITY = (
    (TYPE_PREFERENCE, PREFERENCE_MARKERS),
    (TYPE_EXAMPLE, EXAMPLE_MARKERS),
    (TYPE_CONSTRAINT, CONSTRAINT_MARKERS),
    (TYPE_EXCEPTION, EXCEPTION_MARKERS),
    (TYPE_CONTEXT_RULE, None),          # handled by _is_context_rule
    (TYPE_RELATIONSHIP, None),          # handled by the relationship facet
    (TYPE_PRINCIPLE, None),             # the safe default
)


# ----------------------------------------------------------
# TASK 5 — finer sub-path PROPOSALS (never a silent taxonomy change)
# ----------------------------------------------------------

PROPOSED_SUBPATHS = (
    (
        ("ارتباط عمودی", "vertical circulation"),
        "Global/Circulation/Vertical_Circulation",
    ),
    (
        ("چندطبقه", "چند طبقه", "طبقات", "multi floor", "multi-storey",
         "multi storey", "multi_level"),
        "Building_Types/Residential/Multi_Floor",
    ),
)


DOMAIN_SCOPE = {
    "residential": "Residential",
    "commercial": "Commercial",
    "mixed_use": "Mixed_Use",
}


REUSABILITY = {
    TYPE_PRINCIPLE: "reusable",
    TYPE_RELATIONSHIP: "reusable_contextual",
    TYPE_CONSTRAINT: "project_specific",
    TYPE_PREFERENCE: "personal",
    TYPE_EXAMPLE: "case_specific",
    TYPE_EXCEPTION: "reusable_limiter",
    TYPE_CONTEXT_RULE: "reusable_conditional",
}


ABSOLUTE_TERMS = (
    "must", "always", "required", "shall",
    "باید", "همیشه", "الزام", "لازم است",
)


_NON_CLAIMS = {
    "not_an_absolute_rule": True,
    "not_confidence": True,
    "not_truth": True,
    "not_authority": True,
    "not_ai_approved": True,
    "not_automatic_learning": True,
    "not_a_design": True,
    "not_a_plan": True,
    "not_geometry": True,
    "not_cad_or_bim": True,
    "not_a_decision": True,
    "does_not_write_memory": True,
}


# ----------------------------------------------------------
# TASK 7 — natural per-type sentences (never a schema)
# ----------------------------------------------------------

TYPE_SENTENCES = {
    "fa": {
        TYPE_PRINCIPLE: "این یک اصل معماری عمومی است.",
        TYPE_RELATIONSHIP: "این یک رابطهٔ فضایی بین {elements} است.",
        TYPE_CONSTRAINT: "این یک محدودیت یا شرط همین پروژه است.",
        TYPE_PREFERENCE: "این یک ترجیح شخصی شماست و به‌عنوان قانون عمومی ثبت نمی‌شود.",
        TYPE_EXAMPLE: "این یک مثال یا نمونهٔ خاص است، نه یک قاعدهٔ عمومی.",
        TYPE_EXCEPTION: "این یک استثناست؛ شرایطی که یک قاعده را تغییر می‌دهد.",
        TYPE_CONTEXT_RULE: "این یک قاعدهٔ وابسته به شرایط است.",
    },
    "en": {
        TYPE_PRINCIPLE: "This is a general architectural principle.",
        TYPE_RELATIONSHIP: "This is a spatial relationship between {elements}.",
        TYPE_CONSTRAINT: "This is a limitation or a project condition.",
        TYPE_PREFERENCE: "This is your personal preference — it is not stored as a general rule.",
        TYPE_EXAMPLE: "This is a specific example, not a general rule.",
        TYPE_EXCEPTION: "This is an exception — a condition that changes a rule.",
        TYPE_CONTEXT_RULE: "This is a rule that applies only under conditions.",
    },
}


RESPONSE_HEADER = {
    "fa": "برداشت من از آموزش شما:",
    "en": "This is my reading of your teaching:",
}


RESPONSE_REASON = {"fa": "دلیل مطرح‌شده", "en": "Stated reason"}
RESPONSE_CONTEXT = {"fa": "این مورد وابسته به شرایط", "en": "This depends on the context"}


class ArchitecturalKnowledgeClassificationError(ValueError):
    """Raised when the classifier is misused."""


def _norm(value) -> str:

    text = str(value or "").lower()

    text = text.replace("\u200c", " ")

    text = text.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")

    return " ".join(text.split())


def _has_any(text, markers) -> bool:

    form = _norm(text)

    return any(_norm(marker) in form for marker in markers)


def _matched(text, markers) -> List[str]:

    form = _norm(text)

    return [m for m in markers if _norm(m) in form]


def _language(value) -> str:

    return "en" if str(value or "").lower().startswith("en") else "fa"


# ----------------------------------------------------------
# the input view (a candidate OR a natural statement)
# ----------------------------------------------------------

def _candidate_from(source, language) -> Optional[Dict[str, Any]]:

    if isinstance(source, dict):

        if source.get("contract") != CANDIDATE_CONTRACT:

            raise ArchitecturalKnowledgeClassificationError(
                "classification accepts only %s or a natural statement "
                "(got contract %r)" % (CANDIDATE_CONTRACT, source.get("contract"))
            )

        return source

    if isinstance(source, str) and source.strip():

        # a raw teaching statement — derive the facets with an explicit turn kind
        return extract_architectural_knowledge_candidate_v1(
            source, turn_kind="TEACHING_STATEMENT", language=language
        )

    return None


# ----------------------------------------------------------
# TASK 2 — the classification
# ----------------------------------------------------------

def _is_context_rule(text) -> bool:

    return _has_any(text, CONDITION_MARKERS) and _has_any(text, RULE_MARKERS)


# The primary-type priority. FIRST match wins.
PRIORITY_ORDER = (
    TYPE_PREFERENCE,
    TYPE_EXAMPLE,
    TYPE_CONSTRAINT,
    TYPE_EXCEPTION,
    TYPE_CONTEXT_RULE,
    TYPE_RELATIONSHIP,
    TYPE_PRINCIPLE,
)


def _loose_types(text, facets) -> List[str]:

    """Every type whose signal is present (a condition alone counts)."""

    types: List[str] = []

    if _has_any(text, PREFERENCE_MARKERS):

        types.append(TYPE_PREFERENCE)

    if _has_any(text, EXAMPLE_MARKERS):

        types.append(TYPE_EXAMPLE)

    if _has_any(text, CONSTRAINT_MARKERS):

        types.append(TYPE_CONSTRAINT)

    if _has_any(text, EXCEPTION_MARKERS):

        types.append(TYPE_EXCEPTION)

    if _has_any(text, CONDITION_MARKERS):

        types.append(TYPE_CONTEXT_RULE)

    if facets.get("relationship") and len(facets.get("element") or []) >= 2:

        types.append(TYPE_RELATIONSHIP)

    return types


def classify_type(text, facets) -> Dict[str, Any]:

    """The knowledge type of a statement. FIRST match wins."""

    loose = _loose_types(text, facets)

    primary = TYPE_PRINCIPLE

    reasoning = "a general statement with no rule, condition or relation"

    for candidate in PRIORITY_ORDER:

        if candidate == TYPE_PRINCIPLE:

            break

        if candidate == TYPE_CONTEXT_RULE:

            # a bare condition is not a context RULE — it needs a rule word
            if _is_context_rule(text):

                primary = candidate

                reasoning = "a condition plus a rule word"

                break

            continue

        if candidate in loose:

            primary = candidate

            reasoning = {
                TYPE_PREFERENCE: "a personal-preference marker",
                TYPE_EXAMPLE: "an example marker",
                TYPE_CONSTRAINT: "a constraint marker",
                TYPE_EXCEPTION: "an exception marker",
                TYPE_RELATIONSHIP: "a relationship between two or more elements",
            }[candidate]

            break

    secondary = [t for t in loose if t != primary]

    return {
        "knowledge_type": primary,
        "secondary_types": secondary,
        "reasoning_basis": [reasoning],
    }


# ----------------------------------------------------------
# TASK 3 — the result contract
# ----------------------------------------------------------

def _applicable_scope(knowledge_type, meaning) -> str:

    if knowledge_type in (TYPE_PREFERENCE, TYPE_CONSTRAINT, TYPE_EXAMPLE):

        return "CURRENT_PROJECT"

    for detected in meaning.get("domains_detected") or []:

        if detected in DOMAIN_SCOPE:

            return DOMAIN_SCOPE[detected]

    return "GENERAL"


def _absolute_wording(text, values) -> List[str]:

    found: List[str] = []

    haystack = _norm(text) + " " + " ".join(_norm(v) for v in values)

    for term in ABSOLUTE_TERMS:

        if _norm(term) in haystack and term not in found:

            found.append(term)

    return found


# ----------------------------------------------------------
# TASK 7 — the natural response
# ----------------------------------------------------------

def build_natural_response(result, *, language="fa") -> str:

    lang = _language(language)

    sentences = TYPE_SENTENCES[lang]

    template = sentences[result["knowledge_type"]]

    elements = list(result.get("_elements") or [])

    text = template.format(elements=" و ".join(str(e) for e in elements) if elements else "…")

    lines = [RESPONSE_HEADER[lang], "«%s»" % result.get("human_explanation_basis"), "", text]

    reason = list(result.get("reasoning_evidence") or [])

    if reason:

        lines.append("%s: %s." % (RESPONSE_REASON[lang], "؛ ".join(str(r) for r in reason)))

    context = list(result.get("context") or [])

    if context:

        lines.append("%s %s است." % (RESPONSE_CONTEXT[lang], "، ".join(str(c) for c in context)))

    if result["knowledge_type"] == TYPE_PREFERENCE:

        lines.append(sentences[TYPE_PREFERENCE])

    return "\n".join(lines)


# ----------------------------------------------------------
# the single public entry
# ----------------------------------------------------------

def classify_knowledge(source, *, language=None) -> Dict[str, Any]:

    """Classify a candidate (or a natural teaching statement)."""

    lang = _language(language or ("fa" if isinstance(source, str) else "fa"))

    candidate = _candidate_from(source, lang)

    if candidate is None:

        raise ArchitecturalKnowledgeClassificationError(
            "classification needs a non-empty statement or a candidate"
        )

    text = str(candidate.get("human_basis") or "")

    facets = {key: list(candidate.get(key) or []) for key in FACET_KEYS}

    meaning = extract_meaning(text)

    decision = classify_type(text, facets)

    knowledge_type = decision["knowledge_type"]

    # ---- TASK 5 — the memory DESTINATION PROPOSAL (never a write) ----
    routing = route_confirmed_entry({"facets": facets, "human_basis": text})

    proposed = list(routing["paths"])

    for markers, path in PROPOSED_SUBPATHS:

        if _has_any(text, markers) and path not in proposed:

            proposed.append(path)

    reasoning_evidence = list(facets.get("reason") or []) + list(facets.get("effect") or [])

    result: Dict[str, Any] = {
        "contract": CONTRACT,
        "version": VERSION,
        "knowledge_type": knowledge_type,
        "secondary_types": list(decision.get("secondary_types") or []),
        "reasoning_basis": decision["reasoning_basis"],
        "reasoning_evidence": reasoning_evidence,
        "applicable_scope": _applicable_scope(knowledge_type, meaning),
        "context": list(facets.get("context") or []),
        "exceptions": list(facets.get("exceptions") or []),
        "reusability": REUSABILITY[knowledge_type],
        "memory_destination_candidate": proposed,
        "pending_category_proposals": list(routing["pending_proposals"]),
        "human_explanation_basis": text,
        # safety
        "is_absolute": False,
        "absolute_wording": _absolute_wording(
            text, facets.get("relationship") + facets.get("element")
        ),
        "non_claims": dict(_NON_CLAIMS),
        "memory_written": False,
        "design_generated": False,
        "persistent": False,
        "read_only": True,
        # private helper for the natural response
        "_elements": list(facets.get("element") or []),
    }

    result["natural_response"] = build_natural_response(result, language=lang)

    return result


class ArchitecturalKnowledgeClassificationV1:

    """The classification boundary. Stateless."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    TYPES = KNOWLEDGE_TYPES

    CREATES_DESIGN = False

    WRITES_MEMORY = False

    def classify(self, source, **kwargs) -> Dict[str, Any]:

        return classify_knowledge(source, **kwargs)

    def natural_response(self, result, **kwargs) -> str:

        return build_natural_response(result, **kwargs)

    def __repr__(self):

        return "ArchitecturalKnowledgeClassificationV1(classifies_only=True)"


architectural_knowledge_classification = ArchitecturalKnowledgeClassificationV1()
