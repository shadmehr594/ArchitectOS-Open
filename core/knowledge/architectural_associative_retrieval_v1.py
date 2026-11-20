"""Architectural Associative Retrieval (V1).

Closes GAP 1 (an IMPLICIT question) and GAP 2 (a MULTI-entity question) of
`ARCHITECTURAL_LEARNING_USAGE_VALIDATION_V1_PARTIAL`, WITHOUT modifying the
existing retrieval boundary.

    question -> multi-topic extraction -> direct retrieval
             -> associative expansion -> combined natural answer

It
    extracts ALL architectural topics of a question (not just one)
    associates STORED confirmed knowledge through
        shared spaces · shared relationships · shared principles
        · shared categories · confirmed architectural relations
        · a declared CONCEPT BRIDGE
    reaches a stored item from a question that only IMPLIES it
    combines several confirmed memories into one natural answer

It MUST NOT
    invent a rule / a universal law / a general assumption
    add knowledge the human never taught
    learn automatically / make a design decision
    generate a plan / geometry / CAD / BIM / IFC / a render

Dependency direction

    this module  ->  core.conversation.teaching_meaning_v1                       (query entities)
    this module  ->  core.knowledge.architectural_knowledge_memory_v1            (the memory + vocabularies)
    this module  ->  core.knowledge.architectural_knowledge_retrieval_v1         (the existing retrieval)
    this module  ->  core.vision / core.render / core.bim / core.geometry / core.runtime  FORBIDDEN
"""

from __future__ import annotations


from typing import Any, Dict, List, Optional, Set, Tuple


from core.conversation.teaching_meaning_v1 import extract_meaning

from core.knowledge.architectural_knowledge_memory_v1 import (
    PRINCIPLE_TO_CATEGORY,
)

from core.knowledge.architectural_knowledge_retrieval_v1 import (
    NO_KNOWLEDGE,
    render_answer,
    retrieve,
)


CONTRACT = "ArchitecturalAssociativeRetrievalV1"

VERSION = "1.0"


# ----------------------------------------------------------
# a Persian/English SURFACE vocabulary (word recognition ONLY)
#
# It never adds knowledge — a surface form only becomes a HANDLE that must
# resolve to a STORED, confirmed entry.
# ----------------------------------------------------------

SPACE_SURFACE: Dict[str, str] = {
    "اتاق خواب": "bedroom",
    "اتاق مستر": "master bedroom",
    "مستر": "master bedroom",
    "سوئیت مستر": "master bedroom",
    "حمام": "bathroom",
    "سرویس": "bathroom",
    "توالت": "wc",
    "کلوزت": "closet",
    "کمد": "closet",
    "آشپزخانه": "kitchen",
    "پذیرایی": "living",
    "نشیمن": "living",
    "پارکینگ": "parking",
    "ورودی": "entrance",
    "راه پله": "stair",
    "پله": "stair",
    "نورگیر": "lightwell",
    "حیاط": "courtyard",
    "بالکن": "balcony",
    "تراس": "terrace",
    "پنجره": "window",
    "در": "door",
}


# ----------------------------------------------------------
# the CONCEPT BRIDGE (a declared, closed table)
#
# A concept connects a QUESTION word to a STORED word. It only CONNECTS; if no
# stored entry carries the concept, the result is empty.
# ----------------------------------------------------------

CONCEPT_MARKERS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    (
        "vertical_circulation",
        ("طبقه", "طبقات", "عمودی", "ارتباط عمودی", "طبقه دوم", "floor", "storey",
         "story", "vertical"),
    ),
    (
        "circulation",
        ("مسیر", "حرکت", "جابه", "movement", "circulation", "circulate"),
    ),
    (
        "lighting",
        ("نور", "نورگیری", "روشنایی", "light", "daylight"),
    ),
    (
        "privacy",
        ("حریم", "خصوصی", "privacy", "private"),
    ),
    (
        "storage",
        ("کلوزت", "کمد", "closet", "wardrobe", "storage"),
    ),
    (
        "structure",
        ("سازه", "ساختار", "باکس", "structure", "structural"),
    ),
)


_NON_CLAIMS = {
    "confirmed_memory_only": True,
    "not_invented": True,
    "not_general_knowledge": True,
    "not_a_rule": True,
    "not_a_design": True,
    "not_a_plan": True,
    "not_geometry": True,
    "not_cad_or_bim": True,
    "human_decides": True,
}


class ArchitecturalAssociativeRetrievalError(ValueError):
    """Raised when the associative boundary is misused."""


def _norm(value) -> str:

    text = str(value or "").lower()

    text = text.replace("\u200c", " ")

    text = text.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")

    return " ".join(text.split())


def _language(value) -> str:

    return "en" if str(value or "").lower().startswith("en") else "fa"


def _entry_text(entry) -> str:

    parts: List[str] = []

    for key in ("element", "function", "relationship", "content",
                "fixed_properties", "variable_properties", "context", "exceptions"):

        values = entry.get(key)

        if isinstance(values, (list, tuple)):

            parts.extend(str(v) for v in values)

        elif values:

            parts.append(str(values))

    return " ".join(parts)


def _entry_concepts(entry) -> Set[str]:

    form = _norm(_entry_text(entry))

    return {
        concept
        for concept, markers in CONCEPT_MARKERS
        if any(_norm(marker) in form for marker in markers)
    }


# ----------------------------------------------------------
# multi-topic extraction (GAP 2)
# ----------------------------------------------------------

def extract_topics(question, memory) -> Dict[str, List[str]]:

    """Every architectural topic of a question — not just the first."""

    form = _norm(question)

    spaces: List[str] = []

    categories: List[str] = []

    concepts: List[str] = []

    def add(bucket, value):

        if value and value not in bucket:

            bucket.append(value)

    # 1 — the meaning layer's entities
    for entity in extract_meaning(str(question or "")).get("entities") or []:

        add(spaces, _norm(entity))

    # 2 — the Persian/English surface vocabulary
    for surface, token in SPACE_SURFACE.items():

        if _norm(surface) in form:

            add(spaces, token)

    # 3 — the STORED element tokens found in the question
    for entry in memory.active_entries():

        for token in entry.get("element") or []:

            if _norm(token) in form:

                add(spaces, _norm(token))

    # 4 — the STORED category names found in the question
    for entry in memory.active_entries():

        for path in entry.get("category_path") or []:

            leaf = _norm(str(path).split("/")[-1])

            if leaf and (leaf in form or leaf.replace("_", " ") in form):

                add(categories, str(path))

    # 5 — the principle vocabulary
    for word, path in PRINCIPLE_TO_CATEGORY.items():

        if _norm(word) in form:

            add(categories, path)

    # 6 — the concept bridge
    for concept, markers in CONCEPT_MARKERS:

        if any(_norm(marker) in form for marker in markers):

            add(concepts, concept)

    return {"spaces": spaces, "categories": categories, "concepts": concepts}


# ----------------------------------------------------------
# direct + associative retrieval
# ----------------------------------------------------------

def _active_by_id(memory) -> Dict[str, Dict[str, Any]]:

    return {e.get("knowledge_id"): e for e in memory.active_entries()}


def _direct(memory, topics) -> List[Dict[str, Any]]:

    found: List[Dict[str, Any]] = []

    seen: Set[str] = set()

    def add(entry):

        knowledge_id = entry.get("knowledge_id")

        if knowledge_id and knowledge_id not in seen:

            seen.add(knowledge_id)

            found.append(entry)

    for space in topics["spaces"]:

        for entry in memory.find_by_space(space):

            add(entry)

    for path in topics["categories"]:

        for entry in memory.find_by_category(path):

            add(entry)

    # the concept bridge — a stored entry that carries the question's concept
    concepts = set(topics["concepts"])

    if concepts:

        for entry in memory.active_entries():

            if _entry_concepts(entry) & concepts:

                add(entry)

    return found


def _expand(memory, seeds) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:

    """One associative hop over the STORED confirmed knowledge."""

    seed_ids = {e.get("knowledge_id") for e in seeds}

    seed_tokens: Set[str] = set()

    seed_categories: Set[str] = set()

    seed_concepts: Set[str] = set()

    for entry in seeds:

        seed_tokens.update(_norm(t) for t in (entry.get("element") or []))

        seed_categories.update(entry.get("category_path") or [])

        seed_concepts.update(_entry_concepts(entry))

    found: List[Dict[str, Any]] = []

    trace: List[Dict[str, Any]] = []

    for entry in memory.active_entries():

        knowledge_id = entry.get("knowledge_id")

        if knowledge_id in seed_ids:

            continue

        channels: List[str] = []

        if seed_tokens & {_norm(t) for t in (entry.get("element") or [])}:

            channels.append("shared_space")

        if seed_categories & set(entry.get("category_path") or []):

            channels.append("shared_category")

        shared_concepts = seed_concepts & _entry_concepts(entry)

        if shared_concepts:

            channels.append("shared_concept:%s" % ",".join(sorted(shared_concepts)))

        if channels:

            found.append(entry)

            trace.append({"knowledge_id": knowledge_id, "via": channels})

    return found, trace


# ----------------------------------------------------------
# the single public entry
# ----------------------------------------------------------

def associative_retrieve(question, memory, *, language=None) -> Dict[str, Any]:

    """Retrieve confirmed knowledge associatively — never inventing any."""

    if memory is None:

        raise ArchitecturalAssociativeRetrievalError(
            "associative retrieval requires an ArchitecturalKnowledgeMemoryV1"
        )

    lang = _language(language)

    topics = extract_topics(question, memory)

    direct = _direct(memory, topics)

    associated, trace = _expand(memory, direct)

    by_id = _active_by_id(memory)

    combined: List[Dict[str, Any]] = []

    seen: Set[str] = set()

    for entry in direct + associated:

        knowledge_id = entry.get("knowledge_id")

        if knowledge_id in by_id and knowledge_id not in seen:

            seen.add(knowledge_id)

            combined.append(by_id[knowledge_id])

    # the existing retrieval remains authoritative for an EXPLICIT question
    base = retrieve(question, memory, language=lang)

    for entry in base.get("entries") or []:

        knowledge_id = entry.get("knowledge_id")

        if knowledge_id not in seen:

            seen.add(knowledge_id)

            combined.append(entry)

    direct_ids = [e.get("knowledge_id") for e in direct if e.get("knowledge_id") in seen]

    associated_ids = [e.get("knowledge_id") for e in associated if e.get("knowledge_id") in seen]

    result: Dict[str, Any] = {
        "contract": CONTRACT,
        "version": VERSION,
        "question": str(question),
        "language": lang,
        "topics": topics,
        "direct_ids": direct_ids,
        "associated_ids": associated_ids,
        "association_trace": trace,
        "found": bool(combined),
        "entry_count": len(combined),
        "knowledge_ids": [e.get("knowledge_id") for e in combined],
        "entries": combined,
        "non_claims": dict(_NON_CLAIMS),
        "design_generated": False,
        "memory_written": False,
        "persistent": False,
        "read_only": True,
    }

    if combined:

        label = "، ".join(topics["spaces"] + topics["categories"] + topics["concepts"]) or None

        result["answer"] = render_answer(combined, language=lang, topic=label)

    else:

        result["answer"] = NO_KNOWLEDGE[lang]

        result["no_knowledge"] = True

    return result


class ArchitecturalAssociativeRetrievalV1:

    """The associative retrieval boundary. Stateless."""

    __slots__ = ()

    CONTRACT = CONTRACT

    VERSION = VERSION

    INVENTS_KNOWLEDGE = False

    GENERATES_DESIGN = False

    def retrieve(self, question, memory, **kwargs) -> Dict[str, Any]:

        return associative_retrieve(question, memory, **kwargs)

    def topics(self, question, memory) -> Dict[str, List[str]]:

        return extract_topics(question, memory)

    def __repr__(self):

        return "ArchitecturalAssociativeRetrievalV1(confirmed_only=True)"


architectural_associative_retrieval = ArchitecturalAssociativeRetrievalV1()
