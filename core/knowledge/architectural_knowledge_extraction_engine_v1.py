"""Architectural Knowledge Extraction Engine (V1).

Turns a NATURAL human architectural teaching statement into a structured
Architectural Knowledge Candidate.

    teaching statement  ->  the extraction engine  ->  a candidate

It is a DETERMINISTIC interpreter. No LLM, no network, no render, no design.
The human talks naturally; the engine does the structuring.

It
    activates ONLY for a TEACHING_STATEMENT or a CORRECTION turn
    reads the meaning + clauses the conversation layer already produces
    fills the candidate facets it can RECOGNISE, and leaves the rest ABSENT
    keeps the human's own words in `human_basis` (verbatim)
    produces a CANDIDATE only

It MUST NOT
    answer a question / lecture back / hallucinate (no LLM)
    invent a missing facet
    convert a preference ("بهتر است") into an absolute rule ("باید")
    write Architectural Knowledge Memory
    emit geometry / CAD / BIM / a design

Contract note
    The name `ArchitecturalKnowledgeCandidateV1` is ALREADY taken by the
    vision-side rich candidate (`core/knowledge/architectural_knowledge_v1.py`).
    This layer therefore emits a DISTINCT contract,
    `ArchitecturalKnowledgeExtractionCandidateV1`, so the two can never be
    confused by a contract-equality check.

Dependency direction

    this module  ->  core.conversation.{turn_semantics_v1,
                                        teaching_meaning_v1,
                                        clause_analysis_v1}
    this module  ->  core.vision / core.render / core.bim / core.geometry / core.runtime  FORBIDDEN

Persian marker strings are written directly (UTF-8); matching normalises the
ZWNJ and the Arabic yeh/kaf so a natural spelling still matches.
"""

from __future__ import annotations


from typing import Any, Dict, List, Optional


from core.conversation.turn_semantics_v1 import (
    classify_turn,
    TURN_TEACHING_STATEMENT,
    TURN_CORRECTION,
    TURN_QUESTION,
    TURN_INSTRUCTION,
)

from core.conversation.teaching_meaning_v1 import extract_meaning

from core.conversation.clause_analysis_v1 import segment


CONTRACT = "ArchitecturalKnowledgeExtractionCandidateV1"

VERSION = "1.0"


# ----------------------------------------------------------
# the activation gate
# ----------------------------------------------------------

# The engine activates ONLY for these turn kinds.
TEACHING_TURN_KINDS = (
    TURN_TEACHING_STATEMENT,
    TURN_CORRECTION,
)


# ----------------------------------------------------------
# the candidate facets (all OPTIONAL — absent stays absent)
# ----------------------------------------------------------

FACET_KEYS = (
    "element",
    "function",
    "relationship",
    "fixed_properties",
    "variable_properties",
    "context",
    "exceptions",
    "reason",
    "effect",
)


# ----------------------------------------------------------
# closed marker tables (they only RECOGNISE words already present)
# ----------------------------------------------------------

EXCEPTION_MARKERS = (
    "مگر", "به جز", "بهجز", "استثنا", "جز در", "نه همیشه", "همیشه نیست",
    "نه،", "همه پروژه", "ممکن است متفاوت", "در واحد کوچک", "ساختمان کوچک",
    "except", "unless", "however", "but not", "not always", "not for all",
    "may differ", "does not apply",
)

# A building domain that may stand as an explicit context.
CONTEXT_DOMAINS = ("residential", "commercial", "mixed_use")

VARIABLE_MARKERS = (
    "تغییر می", "تغییر میکند", "متغیر", "متفاوت", "بسته به", "بستگی دارد",
    "با ارتفاع", "با اندازه", "varies", "changes", "variable", "depends",
    "depending",
)

FIXED_MARKERS = (
    "ثابت", "تغییر نمی", "یکسان", "بدون تغییر", "مانند قبل",
    "fixed", "constant", "unchanged", "stays the same", "remains",
)

FUNCTION_MARKERS = (
    "یکی از عناصر", "یکی از فضاهای", "یکی از اجزای", "عنصر", "کاربری",
    "نقش", "عملکرد", "به عنوان",
    "serves as", "functions as", "used for", "role of", "is one of",
    "function of",
)

RELATIONSHIP_MARKERS = (
    "نزدیک", "کنار", "مجاور", "ارتباط", "مرتبط", "وابسته", "در جوار",
    "near", "proximity", "connected", "adjacent", "relationship", "related",
)

CONTEXT_MARKERS = (
    "وقتی", "اگر", "در حالت", "در صورت", "زمانی که",
    "when", "if ", "in case", "in a ", "for a ",
)

REASON_MARKERS = (
    "چون", "زیرا", "به دلیل", "به خاطر", "به این دلیل",
    "because", "since", "due to", "as a result of",
)

EFFECT_MARKERS = (
    "کمتر", "بیشتر", "بهتر", "حفظ", "افزایش", "کاهش", "بهبود", "کم می",
    "reduce", "improve", "increase", "decrease", "less", "more", "better",
    "privacy", "circulation",
)

# The clause-level facet priority. FIRST match wins.
_CLAUSE_FACETS = (
    ("exceptions", EXCEPTION_MARKERS),
    ("variable_properties", VARIABLE_MARKERS),
    ("fixed_properties", FIXED_MARKERS),
    ("function", FUNCTION_MARKERS),
    ("relationship", RELATIONSHIP_MARKERS),
    ("context", CONTEXT_MARKERS),
)


# ----------------------------------------------------------
# the non-absolute guard
# ----------------------------------------------------------

# The engine must never AUTHOR an absolute rule. These terms may appear in the
# human's own words (kept in human_basis / the facet values), but never in the
# payload the engine itself writes.
ABSOLUTE_TERMS = (
    "must", "always", "required", "shall",
    "باید", "همیشه", "الزام", "لازم است",
)


_NON_CLAIMS = {
    "not_absolute_rule": True,
    "not_must": True,
    "not_always": True,
    "not_required": True,
    "not_design": True,
    "not_design_solution": True,
    "not_geometry": True,
    "not_cad_or_bim": True,
    "not_truth": True,
    "not_permanent_knowledge": True,
}


# ----------------------------------------------------------
# helpers
# ----------------------------------------------------------

def _norm(value) -> str:

    """Normalise for MARKER matching only (never for the stored value)."""

    text = str(value or "").lower()

    text = text.replace("\u200c", " ")   # ZWNJ -> space

    text = text.replace("\u064a", "\u06cc")  # Arabic yeh -> Persian yeh

    text = text.replace("\u0643", "\u06a9")  # Arabic kaf -> Persian kaf

    return text


def _has_any(text, markers) -> bool:

    form = _norm(text)

    return any(_norm(marker) in form for marker in markers)


def _unique(values) -> List[Any]:

    result: List[Any] = []

    for value in values:

        if value not in result:

            result.append(value)

    return result


def _classify_clause(text) -> Optional[str]:

    """The facet a clause belongs to, or None. FIRST match wins."""

    for facet, markers in _CLAUSE_FACETS:

        if _has_any(text, markers):

            return facet

    return None


def _teaching_turn_kind(text, language, context) -> Optional[str]:

    """The teaching turn kind of a message, or None.

    The whole-message classifier is single-statement oriented, so a MULTI-LINE
    teaching message can classify as NORMAL_CONVERSATION. The gate therefore
    also classifies each clause and accepts the message when ANY clause is a
    teaching statement / correction. A QUESTION (whole or clause-level) is
    still rejected.
    """

    whole = (classify_turn(text, language=language, context=context) or {}).get(
        "turn_kind"
    )

    if whole in TEACHING_TURN_KINDS:

        return whole

    # A question or an instruction NEVER activates the engine (hard reject).
    if whole in (TURN_QUESTION, TURN_INSTRUCTION):

        return whole

    for clause in segment(text):

        if not isinstance(clause, dict):

            continue

        clause_text = str(clause.get("text") or "").strip()

        if not clause_text:

            continue

        kind = (
            classify_turn(clause_text, language=language, context=context) or {}
        ).get("turn_kind")

        if kind in TEACHING_TURN_KINDS:

            return kind

        if kind in (TURN_QUESTION, TURN_INSTRUCTION):

            return kind

    return whole


def _split_causal(text):

    """Split at the first causal marker -> (main, reason). The reason keeps the
    human's own words for the rationale."""

    form = _norm(text)

    best = None

    for marker in REASON_MARKERS:

        index = form.find(_norm(marker))

        if index != -1 and (best is None or index < best[0]):

            best = (index, len(_norm(marker)))

    if best is None:

        return text, ""

    index, length = best

    main = text[:index]

    reason = text[index + length:]

    return main, reason.strip()


def _absolute_wording(values) -> List[str]:

    """Absolute terms the HUMAN used (reported, never converted)."""

    found: List[str] = []

    for value in values:

        form = _norm(value)

        for term in ABSOLUTE_TERMS:

            if _norm(term) in form and term not in found:

                found.append(term)

    return found


def _assert_engine_payload_clean(payload) -> None:

    """The payload the ENGINE authored must carry no absolute term."""

    text = _norm(str(payload))

    for term in ABSOLUTE_TERMS:

        if _norm(term) in text:

            raise AssertionError(
                "ArchitecturalKnowledgeExtractionCandidateV1 authored an "
                "absolute term: " + term
            )


# ----------------------------------------------------------
# the single public entry
# ----------------------------------------------------------

def extract_architectural_knowledge_candidate_v1(
    text,
    *,
    turn_kind: Optional[str] = None,
    language: Optional[str] = None,
    context: Any = None,
) -> Optional[Dict[str, Any]]:

    """Extract a structured candidate from a natural teaching statement.

    Returns None when the turn is NOT a teaching statement or a correction
    (a question, a design request or general chat creates NO candidate).
    """

    if not isinstance(text, str) or not text.strip():

        return None

    # ---- TASK 1 — the activation gate ----
    if turn_kind is None:

        turn_kind = _teaching_turn_kind(text, language, context)

    if turn_kind not in TEACHING_TURN_KINDS:

        return None

    meaning = extract_meaning(text, turn_kind=turn_kind, context=context)

    main_text, reason_text = _split_causal(text)

    clauses = [
        clause for clause in segment(main_text) if isinstance(clause, dict)
    ]

    facets: Dict[str, List[Any]] = {key: [] for key in FACET_KEYS}

    # ---- element — the normalised entities ----
    topic = meaning.get("space_topic")

    facets["element"] = _unique(list(meaning.get("entities") or []))

    # ---- the clause-level facets ----
    for clause in clauses:

        clause_text = str(clause.get("text") or "").strip()

        if not clause_text:

            continue

        facet = _classify_clause(clause_text)

        if facet and clause_text not in facets[facet]:

            facets[facet].append(clause_text)

    # ---- relationship — fall back to the normalised relations ----
    if not facets["relationship"]:

        facets["relationship"] = _unique(list(meaning.get("relations") or []))

    # ---- reason / effect (TASK 3) ----
    if reason_text:

        facets["reason"] = [reason_text]

        if _has_any(reason_text, EFFECT_MARKERS):

            facets["effect"] = [reason_text]

    # ---- context — the building domain(s) + the active space topic ----
    domains = meaning.get("domains_detected") or [meaning.get("domain")]

    for detected in domains:

        if detected in CONTEXT_DOMAINS and detected not in facets["context"]:

            facets["context"].append(detected)

    if topic and topic not in facets["context"]:

        facets["context"].append(topic)

    # ---- which facets were actually extracted ----
    facets_present = [key for key in FACET_KEYS if facets[key]]

    # ---- TASK 4 — non-absolute: report the human's absolute wording, never
    # convert it, and never author one ----
    absolute_wording = _absolute_wording(
        [value for key in FACET_KEYS for value in facets[key]]
    )

    candidate: Dict[str, Any] = {
        "contract": CONTRACT,
        "version": VERSION,
        "candidate_kind": "correction" if turn_kind == TURN_CORRECTION else "teaching",
        "turn_kind": turn_kind,
        "status": "proposed",
        "is_absolute": False,
        "absolute_wording": absolute_wording,
        "facets_present": facets_present,
        "human_basis": str(text),
        "knowledge_class": meaning.get("knowledge_class"),
        "scope": meaning.get("scope"),
        "provenance": meaning.get("provenance"),
        "space_topic": topic,
        "non_claims": dict(_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }

    for key in FACET_KEYS:

        candidate[key] = list(facets[key])

    # ---- TASK 5 — a correction carries a REFINEMENT, never a deletion ----
    if turn_kind == TURN_CORRECTION:

        candidate["refinement"] = {
            "adds_context": list(facets["context"]),
            "adds_exceptions": list(facets["exceptions"]),
            "narrowing": True,
            "deletes": [],
            "overwrites_silently": False,
            "supersedes": None,
        }

    # ---- the engine-authored payload must carry no absolute term ----
    # (the `non_claims` KEYS are excluded: they literally contain the terms,
    #  e.g. `not_must`, so scanning them would always trip)
    _assert_engine_payload_clean(
        {
            "contract": CONTRACT,
            "version": VERSION,
            "candidate_kind": candidate["candidate_kind"],
            "status": "proposed",
            "facets_present": facets_present,
        }
    )

    return candidate


class ArchitecturalKnowledgeExtractionEngineV1:

    """The extraction engine. Stateless, deterministic."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    IS_DETERMINISTIC = True

    LLM_USED = False

    NETWORK_USED = False

    CREATES_PERMANENT_KNOWLEDGE = False

    def extract(self, text, **kwargs) -> Optional[Dict[str, Any]]:

        return extract_architectural_knowledge_candidate_v1(text, **kwargs)

    def __repr__(self):

        return (
            "ArchitecturalKnowledgeExtractionEngineV1("
            "deterministic=True, candidate_only=True)"
        )


architectural_knowledge_extraction_engine = ArchitecturalKnowledgeExtractionEngineV1()
