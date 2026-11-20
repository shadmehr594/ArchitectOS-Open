"""Architectural Reasoning Quality (V1).

An ADDITIVE layer over `architectural_reasoning_v1`. It raises the reasoning
QUALITY without redesigning anything:

    retrieval + reasoning result
              ↓
    de-duplicate  ->  assemble DIMENSIONS  ->  evaluate CONTEXT
              ↓
    one combined, natural explanation

It
    de-duplicates the conflicts and the decisions
    ASSEMBLES the retrieved confirmed knowledge into architectural dimensions
    states, per item, whether it is CONTEXT-DEPENDENT (from the STORED fields only)
    renders ONE natural explanation

It MUST NOT
    invent a dependency / a dimension / a rule
    produce a design / a plan / a geometry / a render / CAD / BIM / IFC
    decide (the architect decides)

Dependency direction

    this module  ->  core.knowledge.architectural_reasoning_v1   (its phrase tables)
    this module  ->  core.vision / core.render / core.bim / core.geometry / core.runtime  FORBIDDEN
"""

from __future__ import annotations


from typing import Any, Dict, List, Optional, Tuple


from core.knowledge.architectural_reasoning_v1 import (
    CONFLICT_PHRASES,
    DECISION_PHRASES,
    REASONING_FOOTER,
    REASONING_HEADER,
)


CONTRACT = "ArchitecturalReasoningQualityV1"

VERSION = "1.0"


# ----------------------------------------------------------
# the architectural DIMENSIONS (a closed, declared table)
#
# A dimension only GROUPS stored entries. An empty dimension is omitted.
# ----------------------------------------------------------

DIMENSIONS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    (
        "circulation",
        ("circulation", "movement", "مسیر", "حرکت", "جابه", "ارتباط عمودی", "vertical"),
    ),
    (
        "privacy",
        ("privacy", "حریم", "خصوصی"),
    ),
    (
        "lighting",
        ("light", "lighting", "daylight", "نور", "روشنایی"),
    ),
    (
        "fixed_elements",
        ("structure", "stair", "سازه", "ساختار", "باکس", "ثابت", "fixed"),
    ),
    (
        "flexible_elements",
        ("closet", "wardrobe", "storage", "کلوزت", "کمد"),
    ),
    (
        "spatial_relationship",
        ("relationship", "رابطه", "نزدیک", "مجاور", "proximity"),
    ),
)


DIMENSION_LABELS = {
    "fa": {
        "circulation": "گردش",
        "privacy": "حریم",
        "lighting": "نورگیری",
        "fixed_elements": "عناصر ثابت",
        "flexible_elements": "عناصر انعطاف‌پذیر",
        "spatial_relationship": "روابط فضایی",
    },
    "en": {
        "circulation": "circulation",
        "privacy": "privacy",
        "lighting": "lighting",
        "fixed_elements": "fixed elements",
        "flexible_elements": "flexible elements",
        "spatial_relationship": "spatial relationships",
    },
}


QUALITY_LINES = {
    "fa": {
        "dimensions": "برای این زمینه، این موارد هم‌زمان مرتبط‌اند",
        "context_yes": "این دانش وابسته به زمینه است",
        "context_no": "برای این مورد زمینهٔ ثبت‌شده‌ای وجود ندارد",
    },
    "en": {
        "dimensions": "For this context, these are simultaneously relevant",
        "context_yes": "This knowledge is context-dependent",
        "context_no": "No stored context exists for this item",
    },
}


_NON_CLAIMS = {
    "not_a_rule": True,
    "not_invented": True,
    "not_a_design": True,
    "not_a_plan": True,
    "not_geometry": True,
    "not_cad_or_bim": True,
    "human_decides": True,
    "confirmed_memory_only": True,
}


class ArchitecturalReasoningQualityError(ValueError):
    """Raised when the quality boundary is misused."""


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


def _entry_text(entry) -> str:

    parts: List[str] = []

    for key in (
        "element", "function", "relationship", "content",
        "fixed_properties", "variable_properties", "context", "exceptions",
    ):

        value = entry.get(key)

        if isinstance(value, (list, tuple)):

            parts.extend(str(v) for v in value)

        elif value:

            parts.append(str(value))

    return " ".join(parts)


def _statement_for(entry) -> str:

    for key in ("function", "relationship", "content"):

        value = entry.get(key)

        if isinstance(value, (list, tuple)) and value:

            return str(value[0])

        if isinstance(value, str) and value:

            return value

    return ""


# ----------------------------------------------------------
# de-duplication (D1)
# ----------------------------------------------------------

def dedupe_conflicts(conflicts) -> List[Dict[str, Any]]:

    """One conflict per KIND, with the `between` lists merged."""

    merged: Dict[Any, Dict[str, Any]] = {}

    order: List[Any] = []

    for conflict in conflicts or []:

        if not isinstance(conflict, dict):

            continue

        kind = conflict.get("kind")

        if kind not in merged:

            entry = dict(conflict)

            entry["between"] = list(conflict.get("between") or [])

            merged[kind] = entry

            order.append(kind)

            continue

        for value in conflict.get("between") or []:

            if value not in merged[kind]["between"]:

                merged[kind]["between"].append(value)

    return [merged[kind] for kind in order]


def dedupe_decisions(decisions) -> List[Dict[str, Any]]:

    seen = set()

    result: List[Dict[str, Any]] = []

    for decision in decisions or []:

        if not isinstance(decision, dict):

            continue

        key = decision.get("kind") or decision.get("statement")

        if key in seen:

            continue

        seen.add(key)

        result.append(decision)

    return result


# ----------------------------------------------------------
# the DIMENSION assembly (GAP A)
# ----------------------------------------------------------

def assemble_dimensions(entries) -> List[Dict[str, Any]]:

    """Group the retrieved knowledge by architectural dimension."""

    result: List[Dict[str, Any]] = []

    for dimension, markers in DIMENSIONS:

        knowledge_ids: List[str] = []

        statements: List[str] = []

        for entry in entries or []:

            if not isinstance(entry, dict):

                continue

            if not _has_any(_entry_text(entry), markers):

                continue

            knowledge_id = entry.get("knowledge_id")

            if knowledge_id and knowledge_id not in knowledge_ids:

                knowledge_ids.append(knowledge_id)

            statement = _statement_for(entry)

            if statement and statement not in statements:

                statements.append(statement)

        # an empty dimension is OMITTED — never filled with general knowledge
        if knowledge_ids:

            result.append(
                {
                    "dimension": dimension,
                    "knowledge_ids": knowledge_ids,
                    "statements": statements,
                }
            )

    return result


# ----------------------------------------------------------
# the CONTEXT evaluation (GAP B)
# ----------------------------------------------------------

def evaluate_context(entries) -> List[Dict[str, Any]]:

    """What the STORED knowledge itself says about its context."""

    result: List[Dict[str, Any]] = []

    for entry in entries or []:

        if not isinstance(entry, dict):

            continue

        context = list(entry.get("context") or [])

        exceptions = list(entry.get("exceptions") or [])

        variable = list(entry.get("variable_properties") or [])

        dependent = bool(context or exceptions or variable)

        result.append(
            {
                "knowledge_id": entry.get("knowledge_id"),
                "context_dependent": dependent,
                "context": context,
                "exceptions": exceptions,
                "variable_properties": variable,
                # never invent a dependency: with nothing stored, we say so
                "note": "context_dependent" if dependent else "no_context_stored",
            }
        )

    return result


# ----------------------------------------------------------
# the combined natural explanation
# ----------------------------------------------------------

def build_quality_explanation(result, *, language="fa") -> str:

    lang = _language(language)

    lines: List[str] = [REASONING_HEADER[lang]]

    for conflict in result["conflicts"]:

        phrase = CONFLICT_PHRASES[lang].get(conflict.get("kind"))

        if not phrase:

            continue

        between = list(conflict.get("between") or [])

        lines.append(
            "• " + phrase.format(
                target=between[0] if between else "",
                reason=between[1] if len(between) > 1 else "",
            )
        )

    for decision in result["decisions"]:

        phrase = DECISION_PHRASES[lang].get(decision.get("kind"))

        if phrase:

            lines.append("• " + phrase)

    if result["dimensions"]:

        labels = DIMENSION_LABELS[lang]

        names = [labels.get(d["dimension"], d["dimension"]) for d in result["dimensions"]]

        lines.append("• %s: %s." % (QUALITY_LINES[lang]["dimensions"], " · ".join(names)))

    dependent = [e for e in result["context_evaluation"] if e["context_dependent"]]

    if dependent:

        contexts: List[str] = []

        for item in dependent:

            for value in item["context"] + item["exceptions"] + item["variable_properties"]:

                if str(value) not in contexts:

                    contexts.append(str(value))

        suffix = (": " + "، ".join(contexts)) if contexts else ""

        lines.append("• " + QUALITY_LINES[lang]["context_yes"] + suffix + ".")

    lines.append(REASONING_FOOTER[lang])

    return "\n".join(lines)


# ----------------------------------------------------------
# the single public entry
# ----------------------------------------------------------

def _candidate_entries(retrieval, memory) -> List[Dict[str, Any]]:

    """The entries the quality step reasons over.

    For a BROAD question (no specific space was named) the candidate set is
    widened to the whole confirmed memory — a survey question ("what should be
    checked together?") must be able to reach every stored dimension. The
    widening NEVER invents an entry: it only includes entries the human taught.
    """

    entries = [
        e for e in ((retrieval or {}).get("entries") or []) if isinstance(e, dict)
    ]

    topics = (retrieval or {}).get("topics") or {}

    broad = not topics.get("spaces")

    if memory is not None and broad:

        seen = {e.get("knowledge_id") for e in entries}

        for entry in memory.active_entries():

            knowledge_id = entry.get("knowledge_id")

            if knowledge_id and knowledge_id not in seen:

                seen.add(knowledge_id)

                entries.append(entry)

    return entries


def improve_reasoning(
    reasoning_result,
    *,
    retrieval=None,
    memory=None,
    language=None,
) -> Dict[str, Any]:

    """De-duplicate, assemble the dimensions, evaluate the context."""

    if not isinstance(reasoning_result, dict):

        raise ArchitecturalReasoningQualityError(
            "improve_reasoning requires a reasoning result dict"
        )

    lang = _language(language)

    entries = _candidate_entries(retrieval, memory)

    conflicts = dedupe_conflicts(reasoning_result.get("conflicts"))

    decisions = dedupe_decisions(reasoning_result.get("decisions"))

    dimensions = assemble_dimensions(entries)

    context_evaluation = evaluate_context(entries)

    result: Dict[str, Any] = {
        "contract": CONTRACT,
        "version": VERSION,
        "language": lang,
        "conflicts": conflicts,
        "decisions": decisions,
        "dimensions": dimensions,
        "context_evaluation": context_evaluation,
        "used_knowledge": list(reasoning_result.get("used_knowledge") or []),
        "entry_count": len(entries),
        "human_review_required": True,
        "is_final_solution": False,
        "non_claims": dict(_NON_CLAIMS),
        "design_generated": False,
        "persistent": False,
        "read_only": True,
    }

    result["natural_explanation"] = build_quality_explanation(result, language=lang)

    return result


class ArchitecturalReasoningQualityV1:

    """The reasoning-quality boundary. Stateless."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    INVENTS_KNOWLEDGE = False

    GENERATES_DESIGN = False

    DECIDES_FINAL_DESIGN = False

    def improve(self, reasoning_result, **kwargs) -> Dict[str, Any]:

        return improve_reasoning(reasoning_result, **kwargs)

    def dimensions(self, entries) -> List[Dict[str, Any]]:

        return assemble_dimensions(entries)

    def context(self, entries) -> List[Dict[str, Any]]:

        return evaluate_context(entries)

    def __repr__(self):

        return "ArchitecturalReasoningQualityV1(additive=True)"


architectural_reasoning_quality = ArchitecturalReasoningQualityV1()
