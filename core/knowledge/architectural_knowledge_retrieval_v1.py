"""Architectural Knowledge Retrieval (V1).

Lets a human ASK what ArchitectOS has learned, and answers naturally from
CONFIRMED memory only.

    Conversation -> Query Understanding -> Memory Retrieval -> Natural Answer

Core rule
    "I must be able to talk to ArchitectOS like an architect — not fill a form."

It
    receives a NATURAL question (no form, no schema)
    understands the architectural topic (space / relationship / broad)
    searches CONFIRMED memory only (the active revisions)
    answers in SPOKEN language — never JSON, never a database dump

It MUST NOT
    generate a design / plan / render / geometry
    infer missing knowledge / invent rules / optimize / decide
    complete from general knowledge

Dependency direction

    this module  ->  core.conversation.teaching_meaning_v1                (query entities)
    this module  ->  core.knowledge.architectural_knowledge_memory_v1     (the memory read API)
    this module  ->  core.knowledge.human_knowledge_validation_loop_v1    (facet labels)
    this module  ->  core.vision / core.render / core.bim / core.geometry / core.runtime  FORBIDDEN
"""

from __future__ import annotations


from typing import Any, Dict, List, Optional


from core.conversation.teaching_meaning_v1 import extract_meaning

from core.knowledge.architectural_knowledge_extraction_engine_v1 import FACET_KEYS

from core.knowledge.human_knowledge_validation_loop_v1 import FACET_LABELS

from core.knowledge.architectural_knowledge_memory_v1 import (
    SPACE_TO_CATEGORY,
)


CONTRACT = "ArchitecturalKnowledgeRetrievalBoundaryV1"

VERSION = "1.0"


# ----------------------------------------------------------
# the honest no-knowledge answer (TASK 4)
# ----------------------------------------------------------

NO_KNOWLEDGE = {
    "fa": "این مورد هنوز در حافظه معماری آموزش داده نشده است.",
    "en": "This has not been taught to the architectural memory yet.",
}


HEADERS = {
    "fa": {
        "one": "از آموزش‌های تأییدشدهٔ شما دربارهٔ «{topic}»:",
        "all": "از آموزش‌های تأییدشدهٔ شما:",
    },
    "en": {
        "one": "From your confirmed teaching about \"{topic}\":",
        "all": "From your confirmed teaching:",
    },
}


FOOTERS = {
    "fa": "(این دانش فقط از آموزش‌های تأییدشدهٔ شماست و هیچ پیشنهاد طراحی نمی‌دهد.)",
    "en": "(This knowledge comes only from your confirmed teaching and makes no design suggestion.)",
}


# A relationship query ("closet" vs the stored "storage") — the meaning lexicon
# normalises the same space differently at query and teach time.
SPACE_SYNONYMS = {
    "wardrobe": ("wardrobe", "storage", "closet"),
    "storage": ("storage", "closet", "wardrobe"),
    "closet": ("closet", "storage", "wardrobe"),
}


# A space query also covers its residential family (a "bedroom" question
# should reach the master bedroom — TASK 3).
RELATED_PATHS = {
    "Residential/Bedroom": ("Residential/Master_Bedroom",),
    "Residential/Master_Bedroom": ("Residential/Bedroom",),
}


_NON_CLAIMS = {
    "confirmed_memory_only": True,
    "not_general_knowledge": True,
    "not_inferred": True,
    "not_a_design": True,
    "not_a_plan": True,
    "not_geometry": True,
    "not_cad_or_bim": True,
    "not_a_decision": True,
}


class ArchitecturalKnowledgeRetrievalError(ValueError):
    """Raised when the retrieval boundary is misused."""


def _norm(value) -> str:

    text = str(value or "").lower()

    text = text.replace("\u200c", " ")

    text = text.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")

    return " ".join(text.split())


def _language(value) -> str:

    return "en" if str(value or "").lower().startswith("en") else "fa"


def _unique(values) -> List[str]:

    result: List[str] = []

    for value in values:

        if value and value not in result:

            result.append(value)

    return result


# ----------------------------------------------------------
# TASK 3 — query understanding
# ----------------------------------------------------------

def understand_query(question) -> Dict[str, Any]:

    """Understand a natural architectural question."""

    meaning = extract_meaning(str(question or ""))

    spaces: List[str] = []

    for entity in meaning.get("entities") or []:

        text = _norm(entity)

        if text and text not in spaces:

            spaces.append(text)

    topic = meaning.get("space_topic")

    if topic:

        text = _norm(topic)

        if text and text not in spaces:

            spaces.append(text)

    kind = "broad"

    if len(spaces) >= 2:

        kind = "relationship"

    elif len(spaces) == 1:

        kind = "space"

    topic_label = " و ".join(spaces) if spaces else None

    return {
        "spaces": spaces,
        "relations": list(meaning.get("relations") or []),
        "kind": kind,
        "topic_label": topic_label,
    }


# ----------------------------------------------------------
# retrieval helpers
# ----------------------------------------------------------

def _tokens(entry) -> List[str]:

    tokens: List[str] = []

    for value in (entry.get("element") or []) + (entry.get("context") or []):

        text = _norm(value)

        if text:

            tokens.append(text)

    return tokens


def _mentions(entry, space) -> bool:

    names = SPACE_SYNONYMS.get(_norm(space), (_norm(space),))

    tokens = _tokens(entry)

    for name in names:

        for token in tokens:

            if name == token or name in token or token in name:

                return True

    return False


def _active_unique(entries) -> List[Dict[str, Any]]:

    result: List[Dict[str, Any]] = []

    seen = set()

    for entry in entries:

        if not isinstance(entry, dict):

            continue

        # TASK 6 — a superseded revision is never returned as current
        if entry.get("status") != "active":

            continue

        knowledge_id = entry.get("knowledge_id")

        if knowledge_id in seen:

            continue

        seen.add(knowledge_id)

        result.append(entry)

    return result


def _retrieve_for_space(memory, space) -> List[Dict[str, Any]]:

    """Retrieve a space's knowledge EXPANSIVELY along the taxonomy."""

    found: List[Dict[str, Any]] = []

    seen = set()

    def add(entry):

        knowledge_id = entry.get("knowledge_id")

        if knowledge_id not in seen:

            seen.add(knowledge_id)

            found.append(entry)

    # 1 — the space itself (element / context / its category)
    for entry in memory.find_by_space(space):

        add(entry)

    # 2 — the space's residential family (e.g. bedroom <-> master bedroom)
    for entry in memory.active_entries():

        for path in entry.get("category_path") or []:

            related = RELATED_PATHS.get(path)

            if not related:

                continue

            for candidate in related:

                if _mentions(entry, space) or _category_matches_space(candidate, space):

                    add(entry)

    # 3 — cross-space entries that mention the space
    for entry in memory.find_by_category("Cross_Space_Relationships"):

        if _mentions(entry, space):

            add(entry)

    # 4 — Global knowledge that mentions the space
    for entry in memory.active_entries():

        paths = entry.get("category_path") or []

        if any(str(path).startswith("Global/") for path in paths) and _mentions(entry, space):

            add(entry)

    return _active_unique(found)


def _category_matches_space(category, space) -> bool:

    mapped = SPACE_TO_CATEGORY.get(_norm(space))

    return bool(mapped) and mapped == category


def _retrieve_for_relationship(memory, spaces) -> List[Dict[str, Any]]:

    """Knowledge that relates the given spaces."""

    found: List[Dict[str, Any]] = []

    for entry in memory.active_entries():

        mentioned = [s for s in spaces if _mentions(entry, s)]

        if len(mentioned) >= 2:

            found.append(entry)

        elif mentioned and entry.get("relationship"):

            found.append(entry)

    return _active_unique(found)


# ----------------------------------------------------------
# TASK 2 — the natural answer
# ----------------------------------------------------------

def _merge_facets(entries) -> Dict[str, List[str]]:

    merged: Dict[str, List[str]] = {key: [] for key in FACET_KEYS}

    for entry in entries:

        for key in FACET_KEYS:

            for value in entry.get(key) or []:

                if value not in merged[key]:

                    merged[key].append(value)

    return merged


def render_answer(entries, *, language="fa", topic=None) -> str:

    """A SPOKEN architectural answer — never JSON, never a schema."""

    lang = _language(language)

    labels = FACET_LABELS[lang]

    phrases = HEADERS[lang]

    header = phrases["one"].format(topic=topic) if topic else phrases["all"]

    merged = _merge_facets(entries)

    lines = [header]

    for key in FACET_KEYS:

        values = merged[key]

        if not values:

            continue

        lines.append("• %s: %s" % (labels[key], "؛ ".join(str(v) for v in values)))

    lines.append(FOOTERS[lang])

    return "\n".join(lines)


# ----------------------------------------------------------
# the single public entry
# ----------------------------------------------------------

def retrieve(question, memory, *, language=None) -> Dict[str, Any]:

    """Answer a natural architectural question from CONFIRMED memory only."""

    if memory is None:

        raise ArchitecturalKnowledgeRetrievalError(
            "retrieval requires an ArchitecturalKnowledgeMemoryV1 instance"
        )

    understood = understand_query(question)

    lang = _language(language or _guess_language(question))

    entries: List[Dict[str, Any]] = []

    if understood["kind"] == "relationship":

        entries = _retrieve_for_relationship(memory, understood["spaces"])

    elif understood["kind"] == "space":

        for space in understood["spaces"]:

            entries.extend(_retrieve_for_space(memory, space))

    else:

        for space in understood["spaces"]:

            entries.extend(_retrieve_for_space(memory, space))

    entries = _active_unique(entries)

    result: Dict[str, Any] = {
        "contract": CONTRACT,
        "version": VERSION,
        "question": str(question),
        "language": lang,
        "understanding": understood,
        "found": bool(entries),
        "entry_count": len(entries),
        "knowledge_ids": [e.get("knowledge_id") for e in entries],
        "entries": entries,
        "non_claims": dict(_NON_CLAIMS),
        "design_generated": False,
        "persistent": False,
        "read_only": True,
    }

    if entries:

        result["answer"] = render_answer(
            entries, language=lang, topic=understood["topic_label"]
        )

    else:

        # TASK 4 — never complete from general knowledge
        result["answer"] = NO_KNOWLEDGE[lang]

        result["no_knowledge"] = True

    return result


def _guess_language(text) -> str:

    return "en" if str(text or "").isascii() else "fa"


class ArchitecturalKnowledgeRetrievalBoundaryV1:

    """The retrieval boundary. Stateless."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    GENERATES_DESIGN = False

    INFERS_KNOWLEDGE = False

    def retrieve(self, question, memory, **kwargs) -> Dict[str, Any]:

        return retrieve(question, memory, **kwargs)

    def understand(self, question) -> Dict[str, Any]:

        return understand_query(question)

    def render(self, entries, **kwargs) -> str:

        return render_answer(entries, **kwargs)

    def __repr__(self):

        return "ArchitecturalKnowledgeRetrievalBoundaryV1(confirmed_only=True)"


architectural_knowledge_retrieval = ArchitecturalKnowledgeRetrievalBoundaryV1()
