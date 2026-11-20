# -*- coding: utf-8 -*-
"""ARCHITECTURAL_LEARNING_RUNTIME_BRIDGE_V1

The runtime bridge that connects the EXISTING architectural-intelligence
layers into one human learning cycle:

    Human Conversation
      -> Teaching Detection            (existing teaching_foundation_v1)
      -> Existing Knowledge Extraction (existing extraction engine)
      -> Existing Classification       (existing classification layer)
      -> Human Validation              (existing validation loop)
      -> Existing Memory               (existing knowledge memory)
      -> Persistent Memory Boundary    (this module: path resolution only)
      -> Runtime Retrieval             (existing associative retrieval)
      -> Architectural Reasoning       (existing reasoning + quality layers)
      -> Natural Response              (this module: orchestration text only)

WHAT THIS MODULE IS
-------------------
An ORCHESTRATION layer. It owns exactly four things:

  1. the runtime decision table (which existing layer runs for which turn),
  2. a SEMANTIC CONCEPT ASSOCIATION graph (meaning-based matching that runs
     IN ADDITION to -- never instead of -- the existing associative retrieval),
  3. a CONTEXT / EXCEPTION preservation pass over the extracted candidate,
  4. the runtime trace.

WHAT THIS MODULE IS NOT
-----------------------
It does NOT extract knowledge, does NOT classify, does NOT decide truth,
does NOT learn automatically and does NOT generate design. It never renders,
never calls ComfyUI, and never produces geometry, CAD, BIM or IFC.

Every knowledge decision is delegated to the existing modules; this module
only decides WHICH of them to call and HOW to phrase the result.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

# ----------------------------------------------------------------------
# the EXISTING layers this bridge orchestrates (no logic is duplicated)
# ----------------------------------------------------------------------

from core.knowledge.architectural_knowledge_extraction_engine_v1 import (
    extract_architectural_knowledge_candidate_v1,
)

from core.knowledge.architectural_knowledge_classification_v1 import (
    classify_knowledge,
)

from core.knowledge.human_knowledge_validation_loop_v1 import (
    open_review,
    build_confirmation_prompt,
)

# TEACHING CONTENT CAPTURE V1 — when a teaching turn carries BOTH the
# announcement and the proposition in the SAME utterance, the bridge must
# propose the PROPOSITION, never the announcement. Additive, deterministic,
# and it does NOT touch the classifier, the boundary or the ladder.
from core.conversation.teaching_content_extraction_v1 import (
    content_after_preamble,
)

from core.knowledge.architectural_knowledge_memory_v1 import (
    ArchitecturalKnowledgeMemoryV1,
)

from core.knowledge.architectural_associative_retrieval_v1 import (
    associative_retrieve,
)

from core.knowledge.architectural_reasoning_v1 import (
    reason_design,
    FIXED_TOKENS,
    FLEXIBLE_TOKENS,
)

from core.knowledge.architectural_reasoning_quality_v1 import (
    improve_reasoning,
)

# PERSIAN_OUTPUT_ORTHOGRAPHY_V1 — response-side safety net.
# The teaching path echoes the user's raw wording back inside the
# confirmation prompt, so a user misspelling («حیات خلوت», «زخیره»)
# would otherwise reach the ASSISTANT RESPONSE TEXT verbatim. The same
# tiny, context-aware normaliser used by the canonical chat path is
# applied here at the single response choke point. It never touches the
# raw transcript, the pending candidate, STT, dictation or routing.
from core.chat.persian_output_orthography_v1 import (
    persian_output_orthography,
)


CONTRACT = "ArchitecturalLearningRuntimeBridgeV1"
VERSION = "1.0"

BRIDGE_ENGINE = "architectural_learning_runtime_bridge_v1"

# turn kinds (literals, so this module does not couple to the classifier)
_TURN_TEACHING = ("TEACHING_STATEMENT", "CORRECTION")
_TURN_ANSWERABLE = (
    "QUESTION",
    "NORMAL_CONVERSATION",
    "UNKNOWN",
    "KNOWLEDGE_REFLECTION",
)


# ======================================================================
# 1. SEMANTIC CONCEPT ASSOCIATION (requirement 4)
#
# A CLOSED architectural implication graph. It only CONNECTS concepts that
# the human already stated; it never invents a concept and never invents a
# knowledge item. If nothing stored carries the concept, the result is EMPTY.
# ======================================================================

# surface form (fa/en) -> concept seed
SURFACE_TO_CONCEPT: Tuple[Tuple[str, str], ...] = (
    # building type -> multiple floors
    ("duplex", "multiple_floors"),
    ("دوبلکس", "multiple_floors"),
    ("villa", "multiple_floors"),
    ("ویلا", "multiple_floors"),
    ("two storey", "multiple_floors"),
    ("two-storey", "multiple_floors"),
    ("multi storey", "multiple_floors"),
    ("multi-storey", "multiple_floors"),
    ("طبقه", "multiple_floors"),
    ("طبقات", "multiple_floors"),
    # vertical circulation
    ("vertical circulation", "vertical_circulation"),
    ("ارتباط عمودی", "vertical_circulation"),
    ("گردش عمودی", "vertical_circulation"),
    ("راه پله", "stair"),
    ("راهپله", "stair"),
    ("stair", "stair"),
    ("پله", "stair"),
    # area limitation
    ("small site", "area_limitation"),
    ("small plot", "area_limitation"),
    ("زمین کوچک", "area_limitation"),
    ("زمین کوچک است", "area_limitation"),
    ("محدود", "area_limitation"),
    ("کوچک", "area_limitation"),
    # optional features
    ("closet", "storage"),
    ("کلوزت", "storage"),
    ("کمد", "storage"),
    ("wardrobe", "storage"),
    ("انبار", "storage"),
    ("parking", "parking"),
    ("پارکینگ", "parking"),
    # privacy
    ("privacy", "privacy"),
    ("حریم", "privacy"),
    ("خصوصی", "privacy"),
    # spaces
    ("master bedroom", "master_bedroom"),
    ("اتاق مستر", "master_bedroom"),
    ("اتاق خواب مستر", "master_bedroom"),
    ("bedroom", "bedroom"),
    ("اتاق خواب", "bedroom"),
    # daylight
    ("daylight", "lighting"),
    ("lightwell", "lighting"),
    ("نورگیری", "lighting"),
    ("نور", "lighting"),
)

# concept -> concepts it IMPLIES (closed, one hop)
IMPLICATIONS: Dict[str, Tuple[str, ...]] = {
    "multiple_floors": ("vertical_circulation",),
    "vertical_circulation": ("stair", "core"),
    "area_limitation": ("optional_feature_conflict",),
    "optional_feature_conflict": ("storage", "parking"),
}

# concept -> the surface markers that PROVE the concept is present in a
# stored knowledge item (used to match against every facet, not just element)
CONCEPT_MARKERS: Dict[str, Tuple[str, ...]] = {
    "stair": ("stair", "راه پله", "راهپله", "پله", "staircase"),
    "core": ("core", "هسته"),
    "vertical_circulation": (
        "vertical_circulation", "vertical circulation", "ارتباط عمودی",
        "گردش عمودی",
    ),
    "multiple_floors": (
        "multiple_floors", "duplex", "دوبلکس", "villa", "ویلا", "طبقه",
        "multi", "two storey",
    ),
    "area_limitation": (
        "area_limitation", "small site", "زمین کوچک", "کوچک", "محدود",
        "small plot",
    ),
    "optional_feature_conflict": (
        "optional_feature_conflict", "اختیاری", "optional",
    ),
    "storage": ("storage", "closet", "کلوزت", "کمد", "wardrobe", "انبار"),
    "parking": ("parking", "پارکینگ"),
    "privacy": ("privacy", "حریم", "خصوصی"),
    "lighting": ("lighting", "daylight", "نور", "نورگیری"),
    "master_bedroom": ("master bedroom", "اتاق مستر", "مستر"),
    "bedroom": ("bedroom", "اتاق خواب"),
}

# the depth of the implication walk (bounded, so it can never run away)
MAX_HOPS = 2


def _norm(text: Any) -> str:
    """Fold Persian variants + ZWNJ so surface matching is stable."""

    s = str(text or "").lower()

    s = (
        s.replace("\u200c", " ")      # ZWNJ -> space
        .replace("\u064a", "\u06cc")  # arabic yeh -> persian yeh
        .replace("\u0643", "\u06a9")  # arabic kaf -> persian kaf
        .replace("_", " ")
    )

    return s


def extract_concepts(text: Any) -> List[str]:
    """The concept SEEDS a human actually stated (never invented)."""

    hay = _norm(text)

    seeds: List[str] = []

    for surface, concept in SURFACE_TO_CONCEPT:

        if surface in hay and concept not in seeds:

            seeds.append(concept)

    return seeds


def expand_concepts(seeds: List[str]) -> List[str]:
    """Expand seeds through the CLOSED implication graph (bounded)."""

    expanded: List[str] = list(seeds)

    frontier: List[str] = list(seeds)

    for _ in range(MAX_HOPS):

        nxt: List[str] = []

        for concept in frontier:

            for implied in IMPLICATIONS.get(concept, ()):

                if implied not in expanded:

                    expanded.append(implied)

                    nxt.append(implied)

        frontier = nxt

        if not frontier:

            break

    return expanded


def _entry_haystack(entry: Dict[str, Any]) -> str:
    """Every facet of a stored item — not only `element`."""

    parts: List[str] = []

    for key in (
        "element", "function", "relationship", "fixed_properties",
        "variable_properties", "context", "exceptions", "content",
        "human_explanation_basis", "source_space",
    ):

        value = entry.get(key)

        if isinstance(value, (list, tuple)):

            parts.extend(str(v) for v in value)

        elif value:

            parts.append(str(value))

    return _norm(" ".join(parts))


def semantic_match(
    memory: ArchitecturalKnowledgeMemoryV1,
    concepts: List[str],
) -> List[Dict[str, Any]]:
    """Stored items whose ANY facet carries one of the concepts.

    Returns [] when nothing stored carries the concept — never invents.
    """

    matched: List[Dict[str, Any]] = []

    if not concepts:

        return matched

    for entry in memory.active_entries():

        hay = _entry_haystack(entry)

        hits = [
            concept
            for concept in concepts
            if any(marker in hay for marker in CONCEPT_MARKERS.get(concept, (concept,)))
        ]

        if hits:

            matched.append({"entry": entry, "concepts": hits})

    return matched


# ======================================================================
# 2. CONTEXT / EXCEPTION PRESERVATION (requirement 5)
#
# The extraction engine files a Persian conditional under `context` only for
# some surface forms and never fills `exceptions`. This pass RESTORES both,
# without touching the engine and without ever converting a contextual rule
# into an absolute one.
# ======================================================================

# a stated condition -> the NORMALISED context tag
CONDITION_TAGS: Tuple[Tuple[Tuple[str, ...], Tuple[str, str]], ...] = (
    (("زمین کوچک", "زمین کوچک است", "small site", "small plot"), ("site_size", "small")),
    (("زمین بزرگ", "large site", "large plot"), ("site_size", "large")),
    (("شمالی", "north facing", "north-facing"), ("orientation", "north")),
    (("جنوبی", "south facing", "south-facing"), ("orientation", "south")),
    (("اقلیم", "climate"), ("climate", "stated")),
)

CONDITION_MARKERS = (
    "اگر", "در زمین", "در حالت", "در صورت", "وقتی", "زمانی که", "در ",
    "when", "if ", "in case", "on small", "on large",
)

# a stated exception -> the removal / optionality markers
EXCEPTION_MARKERS = (
    "حذف", "ممکن است", "بهتر است", "نه همیشه", "استثنا", "مگر", "به جز",
    "اختیاری", "لازم نیست", "ضروری نیست",
    "removed", "removing", "may be", "optional", "not always", "unless",
    "except",
)

OPTIONAL_SURFACES: Tuple[Tuple[str, str], ...] = (
    ("closet", "closet"), ("کلوزت", "closet"), ("wardrobe", "closet"),
    ("کمد", "closet"), ("storage", "storage"), ("انبار", "storage"),
    ("parking", "parking"), ("پارکینگ", "parking"),
)


def _clauses(text: Any) -> List[str]:
    """Split on the punctuation the human actually used (no NLP)."""

    raw = str(text or "")

    for sep in ("،", ",", "؛", ";", "ولی", "اما", "however", "but "):

        raw = raw.replace(sep, "|")

    return [c.strip() for c in raw.split("|") if c.strip()]


def augment_candidate(
    candidate: Optional[Dict[str, Any]],
    text: Any,
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Preserve context + exceptions. Returns (candidate, trace notes)."""

    notes: List[str] = []

    if not isinstance(candidate, dict):

        return candidate, notes

    context = list(candidate.get("context") or [])

    exceptions = list(candidate.get("exceptions") or [])

    for clause in _clauses(text):

        low = _norm(clause)

        # ---- context: a stated condition --------------------------------
        if any(marker in low for marker in CONDITION_MARKERS):

            for surfaces, (key, value) in CONDITION_TAGS:

                if any(_norm(s) in low for s in surfaces):

                    tag = "%s: %s" % (key, value)

                    if tag not in context:

                        context.append(tag)

                        notes.append("context_preserved:" + tag)

                    break

        # ---- exception: a stated removal / optionality -------------------
        if any(marker in low for marker in EXCEPTION_MARKERS):

            target = None

            for surface, name in OPTIONAL_SURFACES:

                if _norm(surface) in low:

                    target = name

                    break

            tag = (
                "%s: can become optional" % target
                if target
                else "stated exception"
            )

            if tag not in exceptions:

                exceptions.append(tag)

                notes.append("exception_preserved:" + tag)

    if context != (candidate.get("context") or []):

        candidate["context"] = context

    if exceptions != (candidate.get("exceptions") or []):

        candidate["exceptions"] = exceptions

    if context or exceptions:

        present = list(candidate.get("facets_present") or [])

        if context and "context" not in present:

            present.append("context")

        if exceptions and "exceptions" not in present:

            present.append("exceptions")

        candidate["facets_present"] = present

    return candidate, notes


# ======================================================================
# 3. PERSISTENT MEMORY BOUNDARY + PENDING REVIEW STORE
#
# The memory is the EXISTING ArchitecturalKnowledgeMemoryV1 — this module
# only resolves its path and keeps one instance. No second memory system.
# ======================================================================

_MEMORY: Optional[ArchitecturalKnowledgeMemoryV1] = None

_PENDING: Optional[Dict[str, Dict[str, Any]]] = None

_MEMORY_PATH_OVERRIDE: Optional[str] = None

_PENDING_PATH_OVERRIDE: Optional[str] = None


def _data_root() -> str:

    try:

        from config import runtime_config as RC

        return str(getattr(RC, "PROJECT_DATA_ROOT", None) or os.path.join(os.getcwd(), "data"))

    except Exception:

        return os.path.join(os.getcwd(), "data")


def memory_path() -> str:

    if _MEMORY_PATH_OVERRIDE:

        return _MEMORY_PATH_OVERRIDE

    return os.path.join(_data_root(), "learning", "knowledge_memory.json")


def pending_path() -> str:

    if _PENDING_PATH_OVERRIDE:

        return _PENDING_PATH_OVERRIDE

    return os.path.join(_data_root(), "learning", "pending_reviews.json")


def _ensure_parent(path: str) -> None:

    parent = os.path.dirname(path)

    if parent:

        os.makedirs(parent, exist_ok=True)


def get_memory() -> ArchitecturalKnowledgeMemoryV1:

    global _MEMORY

    if _MEMORY is None:

        _MEMORY = ArchitecturalKnowledgeMemoryV1(path=memory_path())

    return _MEMORY


def _load_pending() -> Dict[str, Dict[str, Any]]:

    global _PENDING

    if _PENDING is None:

        _PENDING = {}

        path = pending_path()

        if os.path.exists(path):

            try:

                with open(path, "r", encoding="utf-8") as fh:

                    loaded = json.load(fh)

                if isinstance(loaded, dict):

                    _PENDING = loaded

            except Exception:

                _PENDING = {}

    return _PENDING


def _save_pending() -> None:

    store = _load_pending()

    path = pending_path()

    try:

        _ensure_parent(path)

        tmp = path + ".tmp"

        with open(tmp, "w", encoding="utf-8") as fh:

            json.dump(store, fh, ensure_ascii=False, indent=2)

        os.replace(tmp, path)

    except Exception as e:

        print("LEARNING BRIDGE: pending store not saved:", e)


def reset_state(
    *,
    memory_path_: Optional[str] = None,
    pending_path_: Optional[str] = None,
) -> None:
    """Test/maintenance hook: drop the in-process singletons."""

    global _MEMORY, _PENDING, _MEMORY_PATH_OVERRIDE, _PENDING_PATH_OVERRIDE

    _MEMORY = None

    _PENDING = None

    _MEMORY_PATH_OVERRIDE = memory_path_

    _PENDING_PATH_OVERRIDE = pending_path_


# ======================================================================
# 4. LANGUAGE + TURN HELPERS
# ======================================================================

_PERSIAN_RANGE = ("\u0600", "\u06ff")


def is_persian(text: Any) -> bool:

    return any(_PERSIAN_RANGE[0] <= ch <= _PERSIAN_RANGE[1] for ch in str(text or ""))


def resolve_language(teaching_turn, text, context=None) -> str:

    if isinstance(teaching_turn, dict) and teaching_turn.get("language"):

        return str(teaching_turn.get("language"))

    if isinstance(context, dict) and context.get("language"):

        return str(context.get("language"))

    return "fa" if is_persian(text) else "en"


CONFIRM_MARKERS = (
    "تایید", "تأیید", "بله", "درست است", "درسته", "بله درست", "درسته بله",
    "confirm", "confirmed", "yes", "correct", "ok",
)


def is_confirmation(text: Any) -> bool:

    low = _norm(text).strip()

    if not low or len(low) > 40:

        return False

    return any(marker in low for marker in CONFIRM_MARKERS)


REQUEST_SURFACES = (
    "خانه", "آپارتمان", "واحد", "پروژه", "house", "apartment", "unit",
    "duplex", "دوبلکس", "villa", "ویلا", "penthouse",
)


def looks_like_project_request(text: Any) -> bool:

    """A PROGRAM request names a building and spaces — it is not teaching."""

    low = _norm(text)

    if not any(_norm(s) in low for s in REQUEST_SURFACES):

        return False

    spaces = [c for c in extract_concepts(text)]

    return len(spaces) >= 1


# ======================================================================
# 5. THE RESPONSE SHAPE (mirrors the existing chat contract)
# ======================================================================

def _chat_response(
    text: str,
    language: str,
    session_id: Optional[str],
    teaching: Dict[str, Any],
    trace: List[str],
) -> Dict[str, Any]:

    # PERSIAN_OUTPUT_ORTHOGRAPHY_V1 — normalise the RESPONSE-side text only.
    #
    # The confirmation prompt echoes the learned wording, which was
    # extracted verbatim from the user turn. That means a user misspelling
    # can appear inside ArchitectOS's own reply. Apply the same small,
    # context-aware normaliser the canonical chat path uses, so the
    # ASSISTANT response shows standard Iranian Persian spelling while a
    # legitimate «حیات» (life) is left untouched.
    #
    # Scope: response text only. The raw transcript, the pending candidate
    # and everything frozen (STT, dictation, routing) are unchanged.
    orthography = None

    if language == "fa" and any("\u0600" <= ch <= "\u06FF" for ch in str(text or "")):

        orthography = persian_output_orthography.normalize(text)

        text = orthography["text"]

    return {
        "type": "chat",
        "engine": BRIDGE_ENGINE,
        "status": "success",
        "result": text,
        "session_id": session_id,
        "language": {
            "input_language": "persian" if is_persian(text) else "english",
            "output_language": "persian" if language == "fa" else "english",
            "guard_status": "validated",
            "corrected": False,
            "decision": None,
            # PERSIAN_OUTPUT_ORTHOGRAPHY_V1 — recorded, not hidden.
            "orthography_changed": bool(
                orthography and orthography.get("changed")
            ),
            "orthography_changes": (orthography or {}).get("changes") or [],
        },
        "teaching": teaching,
        "capability": "architectural_learning",
        "render_handoff": {
            "compiled_render_prompt": "",
            "compiled_prompt_source": "none",
            "render_runtime_received_prompt": None,
        },
        "render_requested": False,
        "learning_runtime": {
            "contract": CONTRACT,
            "version": VERSION,
            "trace": list(trace),
            "design_generated": False,
            "geometry_generated": False,
            "render_requested": False,
        },
    }


# ======================================================================
# 6. THE DECISION TABLE
# ======================================================================

def bridge(
    teaching_turn,
    text,
    context=None,
    session_id=None,
) -> Optional[Dict[str, Any]]:
    """The single entry point. Returns a chat response, or None to decline.

    Declining (None) means: "not mine" — the caller's existing behaviour runs
    completely unchanged.
    """

    try:

        return _bridge_impl(teaching_turn, text, context, session_id)

    except Exception as e:

        print("LEARNING RUNTIME BRIDGE ERROR:", e)

        return None


def _bridge_impl(teaching_turn, text, context, session_id):

    turn_kind = (teaching_turn or {}).get("turn_kind")

    candidate = (teaching_turn or {}).get("candidate")

    raw = str(text or "").strip()

    if not raw:

        return None

    language = resolve_language(teaching_turn, raw, context)

    session = (
        session_id
        or ((context or {}).get("session_id") if isinstance(context, dict) else None)
        or "default"
    )

    # ---- gate 1: a human CONFIRMATION of a pending learning --------------
    if is_confirmation(raw) and session in _load_pending():

        return _confirm(session, language)

    # ---- gate 2: a TEACHING statement / correction ----------------------
    if (
        candidate is not None
        and turn_kind in _TURN_TEACHING
        and not looks_like_project_request(raw)
    ):

        # ==================================================
        # TEACHING CONTENT CAPTURE V1
        #
        # THE DEFECT (real manual browser test): the teacher announces the
        # teaching intent AND supplies the actual content in the SAME turn —
        #
        #   "میخوام یه نکته آموزشی رو بهت بگم اگه آشپزخونه به حیاط خلوت
        #    نزدیکتر باشه برای طراحیمون بهتره"
        #
        # The classifier's rung 0 returns OFFER_TO_TEACH, `observe_turn`
        # recovers it to a TEACHING_STATEMENT candidate (only when the
        # content is real), and THIS bridge then proposed the knowledge
        # from `raw` — the WHOLE announcement. The extraction engine
        # therefore quoted the announcement itself as the rule:
        #
        #   relationship: ['میخوام یه نکته آموزشی رو بهت بگم ... بهتره']
        #
        # i.e. the assistant restated "I want to tell you a teaching note"
        # as if it were the design principle, instead of the principle.
        #
        # The PROPOSITION is already available deterministically: when the
        # turn carries an embedded proposition, `content_after_preamble`
        # returns it in the teacher's OWN wording. Propose THAT.
        #
        # A PURE OFFER ("میخوام یه نکته بهت یاد بدم") has no proposition, so
        # `content_after_preamble` returns None and `teaching_text` stays
        # the raw text — every existing behaviour is preserved byte for
        # byte for every other turn shape (plain statements, corrections,
        # and offers that reach this gate without content).
        # ==================================================

        teaching_text = content_after_preamble(raw)

        if not teaching_text:

            teaching_text = raw

        return _propose(
            teaching_text, turn_kind, session, language, full_raw=raw
        )

    # ---- gate 3: a question / request answerable from learned memory -----
    if turn_kind in _TURN_ANSWERABLE or looks_like_project_request(raw):

        return _answer(raw, language, session)

    return None


# ----------------------------------------------------------------------
# gate 2 — teach -> extract -> classify -> validate -> propose
# ----------------------------------------------------------------------

def _propose(raw, turn_kind, session, language, full_raw=None):

    """Propose one learning from the turn's PROPOSITION.

    TEACHING CONTENT CAPTURE V1 — `raw` is the proposition actually being
    taught (the announcement removed when the turn carried one);
    `full_raw` is the teacher's COMPLETE utterance, kept so the pending
    record can still show exactly what was said. When `full_raw` is None
    the two are the same text and the previous behaviour is unchanged.
    """

    trace = ["teaching_detected:" + str(turn_kind)]

    if full_raw is None:

        full_raw = raw

    elif str(full_raw).strip() != str(raw).strip():

        trace.append("preamble_removed")

    candidate = extract_architectural_knowledge_candidate_v1(
        raw, turn_kind=turn_kind, language=language
    )

    if candidate is None:

        trace.append("extraction:empty")

        return None

    trace.append("extraction:ok")

    candidate, notes = augment_candidate(candidate, raw)

    trace.extend(notes or [])

    # EXISTING classification (informational — never stored as truth)
    try:

        classification = classify_knowledge(candidate, language=language)

        knowledge_type = classification.get("knowledge_type")

        trace.append("classification:" + str(knowledge_type))

    except Exception:

        classification = {}

        knowledge_type = None

        trace.append("classification:unavailable")

    # a CORRECTION supersedes the matching active revision (never deletes)
    previous_revision = None

    if turn_kind == "CORRECTION":

        previous_revision = _find_supersede_target(candidate)

        trace.append(
            "supersede_target:" + str(previous_revision or "none")
        )

    review = open_review(candidate, language=language)

    pending = _load_pending()

    pending[session] = {
        "candidate": candidate,
        "review_id": review.review_id,
        "text": raw,
        # TEACHING CONTENT CAPTURE V1 — the teacher's COMPLETE utterance,
        # kept for audit. `text` above is the PROPOSITION that is actually
        # being proposed when the turn carried an announcement.
        "full_text": full_raw,
        "turn_kind": turn_kind,
        "previous_revision": previous_revision,
        "language": language,
        "knowledge_type": knowledge_type,
        "at": time.time(),
    }

    _save_pending()

    trace.append("review_opened:pending_human_confirmation")

    prompt = build_confirmation_prompt(review, language=language)

    hint = (
        "\n\nبرای ثبت دائمی «تایید» بگویید. تا آن زمان هیچ چیزی ذخیره نمی‌شود."
        if language == "fa"
        else "\n\nSay \"confirm\" to store this permanently. Nothing is stored until then."
    )

    return _chat_response(
        prompt + hint,
        language,
        session,
        teaching={
            "action": "propose_learning",
            "knowledge_type": knowledge_type,
            "review_id": review.review_id,
            "candidate": candidate,
            "awaiting_human_confirmation": True,
            "permanent_learning": False,
            "memory_written": False,
            "llm_used": False,
        },
        trace=trace,
    )


def _find_supersede_target(candidate) -> Optional[str]:
    """The active revision this correction refines — the CLOSEST match only.

    A correction supersedes the item it is ABOUT. It never deletes anything and
    never touches an unrelated item (a weak overlap is refused).
    """

    elements = set(candidate.get("element") or [])

    if not elements:

        return None

    best_id = None

    best_score = 0.0

    try:

        for entry in get_memory().active_entries():

            entry_elements = set(entry.get("element") or [])

            if not entry_elements:

                continue

            overlap = len(elements & entry_elements)

            if not overlap:

                continue

            score = overlap / float(len(elements | entry_elements))

            if score > best_score:

                best_score = score

                best_id = entry.get("knowledge_id")

    except Exception:

        return None

    # a correction only refines a genuinely related item
    if best_score < 0.5:

        return None

    return best_id


# ----------------------------------------------------------------------
# gate 1 — the human confirms -> existing memory
# ----------------------------------------------------------------------

def _confirm(session, language):

    trace = ["confirmation_detected"]

    pending = _load_pending()

    record = pending.get(session)

    if not record:

        return None

    candidate = record.get("candidate")

    review = open_review(candidate, language=record.get("language") or language)

    review.confirm()

    trace.append("review_confirmed:human")

    entry = review.to_confirmed_entry()

    if entry is None:

        trace.append("confirmed_entry:none")

        return None

    memory = get_memory()

    memory_entry = memory.add_confirmed_entry(
        entry,
        previous_revision=record.get("previous_revision"),
    )

    trace.append("memory_written:" + str(memory_entry.get("knowledge_id")))
    trace.append("revision:" + str(memory_entry.get("revision")))

    del pending[session]

    _save_pending()

    if language == "fa":

        text = (
            "ثبت شد.\n"
            "این اصل را به‌عنوان دانشِ تأییدشدهٔ خودتان در حافظهٔ معماری نگه می‌دارم "
            "و از این پس هنگام بررسی پروژه‌های تازه از آن استفاده می‌کنم.\n"
            "تصمیم نهایی با معمار است."
        )

    else:

        text = (
            "Stored.\n"
            "I am keeping this as your confirmed architectural knowledge and will "
            "use it when reasoning about new projects.\n"
            "The final decision remains with the architect."
        )

    return _chat_response(
        text,
        language,
        session,
        teaching={
            "action": "confirm_learning",
            "knowledge_id": memory_entry.get("knowledge_id"),
            "revision": memory_entry.get("revision"),
            "category_path": memory_entry.get("category_path"),
            "context": memory_entry.get("context"),
            "exceptions": memory_entry.get("exceptions"),
            "is_absolute": False,
            "permanent_learning": True,
            "memory_written": True,
            "llm_used": False,
        },
        trace=trace,
    )


# ----------------------------------------------------------------------
# gate 3 — a new question answered from learned memory
# ----------------------------------------------------------------------

def _answer(raw, language, session):

    memory = get_memory()

    seeds = extract_concepts(raw)

    if not seeds:

        return None

    concepts = expand_concepts(seeds)

    trace = ["concepts:" + ",".join(concepts)]

    # the EXISTING associative retrieval still runs (never replaced)
    base = associative_retrieve(raw, memory, language=language)

    base_entries = list(base.get("entries") or [])

    trace.append("associative_retrieval:%d" % len(base_entries))

    # the ADDITIVE semantic association
    semantic = semantic_match(memory, concepts)

    trace.append("semantic_match:%d" % len(semantic))

    merged: List[Dict[str, Any]] = []

    seen = set()

    for entry in base_entries + [m["entry"] for m in semantic]:

        kid = entry.get("knowledge_id")

        if kid and kid not in seen:

            seen.add(kid)

            merged.append(entry)

    if not merged:

        trace.append("declined:no_learned_knowledge")

        return None

    # translate the human's own words into the structured context the
    # EXISTING reasoning layer expects (derived, never invented)
    reasoning_context, derivation = _derive_reasoning_context(raw, concepts, merged)

    trace.extend(derivation)

    retrieval_view = {
        "entries": merged,
        "found": True,
        "topics": dict(base.get("topics") or {}),
    }

    reasoning = reason_design(
        reasoning_context,
        memory=memory,
        retrieval=retrieval_view,
        language=language,
    )

    quality = improve_reasoning(
        reasoning,
        retrieval=retrieval_view,
        memory=memory,
        language=language,
    )

    trace.append("reasoning_conflicts:%d" % len(reasoning.get("conflicts") or []))

    text = _render_answer(raw, language, merged, reasoning, quality, concepts)

    return _chat_response(
        text,
        language,
        session,
        teaching={
            "action": "answer_from_learned_memory",
            "used_knowledge": [
                {
                    "knowledge_id": e.get("knowledge_id"),
                    "element": list(e.get("element") or []),
                    "revision": e.get("revision"),
                    "context": list(e.get("context") or []),
                    "exceptions": list(e.get("exceptions") or []),
                }
                for e in merged
            ],
            "concepts": concepts,
            "conflicts": [c.get("kind") for c in (reasoning.get("conflicts") or [])],
            "candidate": None,
            "permanent_learning": False,
            "memory_written": False,
            "llm_used": False,
        },
        trace=trace,
    )


def _derive_reasoning_context(
    raw: str,
    concepts: List[str],
    entries: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[str]]:

    """Derive the structured context FROM the human's own concepts."""

    trace: List[str] = []

    context: Dict[str, Any] = {"request": raw}

    if "area_limitation" in concepts:

        context["area_limited"] = True

        trace.append("derived:area_limited")

    fixed: List[str] = []

    optional: List[str] = []

    for entry in entries:

        for element in entry.get("element") or []:

            if element in FIXED_TOKENS and element not in fixed:

                fixed.append(element)

            if element in FLEXIBLE_TOKENS and element not in optional:

                optional.append(element)

    modifications = []

    if "area_limitation" in concepts:

        for f in fixed:

            for o in optional:

                modifications.append({"target": f, "reason": o})

    if modifications:

        context["requested_modifications"] = modifications

        trace.append("derived:requested_modifications")

    return context, trace


def _render_answer(raw, language, entries, reasoning, quality, concepts) -> str:

    lines: List[str] = []

    if language == "fa":

        lines.append("بر پایهٔ دانشی که از شما آموختم و تأیید کردید:")

        for entry in entries:

            elements = "، ".join(entry.get("element") or [])

            basis = entry.get("human_explanation_basis") or ""

            lines.append("• %s — «%s»" % (elements, basis))

        lines.append("")
        lines.append("این را از درخواست شما برداشت کردم: %s" % " ← ".join(concepts))

        explanation = quality.get("natural_explanation") or ""

        if explanation:

            lines.append("")
            lines.append(explanation)

        if "تصمیم نهایی با معمار است" not in explanation:

            lines.append("")
            lines.append("تصمیم نهایی با معمار است.")

    else:

        lines.append("Based on the knowledge I learned from you and you confirmed:")

        for entry in entries:

            elements = ", ".join(entry.get("element") or [])

            basis = entry.get("human_explanation_basis") or ""

            lines.append("• %s — \"%s\"" % (elements, basis))

        lines.append("")
        lines.append("This is how I read your request: %s" % " -> ".join(concepts))

        explanation = quality.get("natural_explanation") or ""

        if explanation:

            lines.append("")
            lines.append(explanation)

        if "final decision remains with the architect" not in explanation:

            lines.append("")
            lines.append("The final decision remains with the architect.")

    return "\n".join(lines)


# ======================================================================
# 7. THE CLASS (mirrors the other knowledge layers)
# ======================================================================

class ArchitecturalLearningRuntimeBridgeV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    GENERATES_GEOMETRY = False
    GENERATES_DESIGN = False
    WRITES_MEMORY_WITHOUT_CONFIRMATION = False
    DUPLICATES_EXTRACTION = False
    DUPLICATES_CLASSIFICATION = False
    DUPLICATES_MEMORY = False

    def bridge(self, teaching_turn, text, context=None, session_id=None):

        return bridge(teaching_turn, text, context, session_id=session_id)

    def concepts(self, text):

        return expand_concepts(extract_concepts(text))

    def memory(self):

        return get_memory()

    def pending(self):

        return dict(_load_pending())


architectural_learning_runtime = ArchitecturalLearningRuntimeBridgeV1()
