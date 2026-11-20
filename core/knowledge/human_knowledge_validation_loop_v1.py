"""Human Architectural Knowledge Validation Loop (V1).

The MISSING BRIDGE between an extracted candidate and permanent memory:

    ArchitecturalKnowledgeExtractionCandidateV1
              ↓
    Human Validation            <- THIS LAYER
              ↓
    ArchitecturalKnowledgeConfirmedEntryV1
              ↓
    Future Architectural Knowledge Memory   (NOT implemented here)

Core principle
    A human architect teaches naturally. ArchitectOS extracts. THE HUMAN
    CONFIRMS. Only confirmed knowledge may enter memory.

    The system NEVER assumes an extracted candidate is correct.

It
    represents a human REVIEWING an extracted candidate (a state machine)
    offers a natural confirmation prompt (not a schema)
    supports confirm / reject / request-refinement
    keeps the OLD candidate on a correction (never deletes)
    emits a storage-AGNOSTIC handoff descriptor

It MUST NOT
    auto-learn / auto-promote / approve by AI
    carry truth / confidence / authority
    write permanent memory
    design / render / generate geometry

Dependency direction

    this module  ->  core.knowledge.architectural_knowledge_extraction_engine_v1
    this module  ->  core.vision / core.render / core.bim / core.geometry / core.runtime  FORBIDDEN
"""

from __future__ import annotations


import time
import uuid

from copy import deepcopy

from typing import Any, Dict, List, Optional


from core.knowledge.architectural_knowledge_extraction_engine_v1 import (
    CONTRACT as CANDIDATE_CONTRACT,
    FACET_KEYS,
    extract_architectural_knowledge_candidate_v1,
)


REVIEW_CONTRACT = "ArchitecturalKnowledgeReviewV1"

ENTRY_CONTRACT = "ArchitecturalKnowledgeConfirmedEntryV1"

HANDOFF_CONTRACT = "ArchitecturalKnowledgeMemoryHandoffV1"

VERSION = "1.0"


# ----------------------------------------------------------
# the allowed review states (TASK 1)
# ----------------------------------------------------------

STATE_PENDING_REVIEW = "pending_review"

STATE_CONFIRMED = "confirmed"

STATE_REJECTED = "rejected"

STATE_REFINEMENT_REQUESTED = "refinement_requested"


REVIEW_STATES = (
    STATE_PENDING_REVIEW,
    STATE_CONFIRMED,
    STATE_REJECTED,
    STATE_REFINEMENT_REQUESTED,
)


# States the review must NEVER reach. A candidate is a candidate.
FORBIDDEN_STATES = (
    "learned",
    "learned_automatically",
    "approved_by_ai",
    "ai_approved",
    "truth",
    "auto_promoted",
    "automatically_promoted",
    "permanent",
    "promoted",
)


_NON_CLAIMS = {
    "not_learned_automatically": True,
    "not_approved_by_ai": True,
    "not_truth": True,
    "not_authority": True,
    "not_automatic_promotion": True,
    "not_permanent_memory_write": True,
    "not_design": True,
    "not_geometry": True,
    "not_cad_or_bim": True,
}


# ----------------------------------------------------------
# natural facet labels (TASK 6 — a conversation, not a schema)
# ----------------------------------------------------------

FACET_LABELS = {
    "fa": {
        "element": "عنصر",
        "function": "کارکرد",
        "relationship": "رابطه",
        "fixed_properties": "ویژگی ثابت",
        "variable_properties": "ویژگی متغیر",
        "context": "زمینه",
        "exceptions": "استثناها",
        "reason": "دلیل",
        "effect": "اثر",
    },
    "en": {
        "element": "Element",
        "function": "Function",
        "relationship": "Relationship",
        "fixed_properties": "Fixed property",
        "variable_properties": "Variable property",
        "context": "Context",
        "exceptions": "Exceptions",
        "reason": "Reason",
        "effect": "Effect",
    },
}


PHRASES = {
    "fa": {
        "intro": "این برداشت من از آموزش شماست:",
        "ask": "آیا درست استخراج شده؟ می‌توانید تأیید کنید، اصلاح کنید یا رد کنید.",
        "confirmed": "تأیید شد. این برداشت به‌عنوان دانش تأییدشدهٔ شما ثبت می‌شود.",
        "rejected": "رد شد. این برداشت ثبت نمی‌شود.",
        "refinement": "اصلاح شما ثبت شد. برداشت قبلی حذف نمی‌شود؛ یک اصلاح جدید ساخته می‌شود.",
    },
    "en": {
        "intro": "This is my reading of your teaching:",
        "ask": "Did I extract it correctly? You can confirm, correct, or reject it.",
        "confirmed": "Confirmed. This reading is recorded as your confirmed knowledge.",
        "rejected": "Rejected. This reading is not recorded.",
        "refinement": "Your correction is recorded. The previous reading is not deleted; a new refinement is created.",
    },
}


class ArchitecturalKnowledgeValidationError(ValueError):
    """Raised when a review transition is not allowed."""


def _new_review_id():

    return "rev_" + uuid.uuid4().hex[:12]


def _new_entry_id():

    return "ake_" + uuid.uuid4().hex[:12]


def _language(value):

    return "en" if str(value or "").lower().startswith("en") else "fa"


def _validate_state(state):

    if state in FORBIDDEN_STATES:

        raise ArchitecturalKnowledgeValidationError(
            "a review may never reach state %r: only a HUMAN confirms "
            "knowledge." % (state,)
        )

    if state not in REVIEW_STATES:

        raise ArchitecturalKnowledgeValidationError(
            "unknown review state %r (allowed: %s)"
            % (state, ", ".join(REVIEW_STATES))
        )

    return state


# ==========================================================
# THE REVIEW (TASK 1)
# ==========================================================

class ArchitecturalKnowledgeReview:

    """A human reviewing one extracted candidate.

    States: pending_review -> confirmed | rejected | refinement_requested
    """

    CONTRACT = REVIEW_CONTRACT

    VERSION = VERSION

    STATES = REVIEW_STATES

    # A review creates nothing by itself and decides nothing.
    CREATES_PERMANENT_KNOWLEDGE = False

    AI_APPROVED = False

    AUTO_PROMOTED = False

    GRANTS_AUTHORITY = False

    CARRIES_CONFIDENCE = False

    def __init__(self, candidate, *, review_id=None, language=None):

        if not isinstance(candidate, dict):

            raise ArchitecturalKnowledgeValidationError(
                "a review requires an extraction candidate dict"
            )

        if candidate.get("contract") != CANDIDATE_CONTRACT:

            raise ArchitecturalKnowledgeValidationError(
                "a review accepts only %s (got %r)"
                % (CANDIDATE_CONTRACT, candidate.get("contract"))
            )

        self.review_id = review_id or _new_review_id()

        self.candidate = deepcopy(candidate)

        self.state = STATE_PENDING_REVIEW

        self.language = _language(language)

        self.human_confirmed = False

        self.note = None

        self.superseded_by = None

        self.created_at = time.time()

        self.updated_at = self.created_at

        self.history: List[Dict[str, Any]] = [
            {"state": STATE_PENDING_REVIEW, "at": self.created_at}
        ]

    # --------------------------------------------------

    def _transition(self, state, **extra):

        _validate_state(state)

        if self.state != STATE_PENDING_REVIEW:

            raise ArchitecturalKnowledgeValidationError(
                "review %s is %r and can no longer change state"
                % (self.review_id, self.state)
            )

        self.state = state

        self.updated_at = time.time()

        entry = {"state": state, "at": self.updated_at}

        entry.update(extra)

        self.history.append(entry)

        return self

    # --------------------------------------------------

    def confirm(self, note=None):

        """The HUMAN confirms the extraction."""

        self._transition(STATE_CONFIRMED, note=note)

        self.human_confirmed = True

        self.note = note

        return self

    def reject(self, reason=None):

        """The HUMAN rejects the extraction."""

        self._transition(STATE_REJECTED, reason=reason)

        self.note = reason

        return self

    def request_refinement(self, correction_text, *, language=None):

        """The HUMAN corrects the extraction (TASK 3).

        The OLD candidate is NOT deleted. A NEW refinement candidate + review
        are created, and this review records `superseded_by`.
        """

        if not isinstance(correction_text, str) or not correction_text.strip():

            raise ArchitecturalKnowledgeValidationError(
                "a refinement requires the human's correction text"
            )

        refinement_candidate = extract_architectural_knowledge_candidate_v1(
            correction_text,
            turn_kind="CORRECTION",
            language=language or self.language,
        )

        if refinement_candidate is None:

            raise ArchitecturalKnowledgeValidationError(
                "the correction could not be extracted into a candidate"
            )

        self._transition(STATE_REFINEMENT_REQUESTED)

        new_review = ArchitecturalKnowledgeReview(
            refinement_candidate,
            language=language or self.language,
        )

        self.superseded_by = new_review.review_id

        return new_review

    # --------------------------------------------------

    def to_confirmed_entry(self) -> Optional[Dict[str, Any]]:

        """The handoff artifact — ONLY when the human confirmed."""

        if self.state != STATE_CONFIRMED or not self.human_confirmed:

            return None

        candidate = self.candidate

        return {
            "contract": ENTRY_CONTRACT,
            "version": VERSION,
            "entry_id": _new_entry_id(),
            "review_id": self.review_id,
            "status": "confirmed",
            "confirmed_by": "HUMAN_TEACHER",
            "confirmed_at": self.updated_at,
            "candidate_kind": candidate.get("candidate_kind"),
            "turn_kind": candidate.get("turn_kind"),
            "facets": {key: list(candidate.get(key) or []) for key in FACET_KEYS},
            "facets_present": list(candidate.get("facets_present") or []),
            "human_basis": candidate.get("human_basis"),
            "is_absolute": False,
            "absolute_wording": list(candidate.get("absolute_wording") or []),
            "superseded_by": None,
            "non_claims": dict(_NON_CLAIMS),
            "persistent": False,
            "read_only": True,
        }

    # --------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:

        return {
            "contract": REVIEW_CONTRACT,
            "version": VERSION,
            "review_id": self.review_id,
            "candidate_contract": CANDIDATE_CONTRACT,
            "candidate": deepcopy(self.candidate),
            "state": self.state,
            "language": self.language,
            "human_confirmed": self.human_confirmed,
            "ai_approved": False,
            "auto_promoted": False,
            "grants_authority": False,
            "carries_confidence": False,
            "note": self.note,
            "superseded_by": self.superseded_by,
            "history": deepcopy(self.history),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "non_claims": dict(_NON_CLAIMS),
            "persistent": False,
            "read_only": True,
        }

    def __repr__(self):

        return "ArchitecturalKnowledgeReview(%s, state=%r)" % (
            self.review_id,
            self.state,
        )


# ==========================================================
# THE CONFIRMATION PROMPT (TASK 2 + TASK 6 — natural, not a schema)
# ==========================================================

def build_confirmation_prompt(review, *, language=None) -> str:

    """A natural reading of the extraction, asked as a question.

    It NEVER says "Enter the Element field" — it says what it understood.
    """

    lang = _language(language or getattr(review, "language", None))

    phrases = PHRASES[lang]

    labels = FACET_LABELS[lang]

    candidate = review.candidate

    lines = [phrases["intro"]]

    for key in FACET_KEYS:

        values = [str(v) for v in (candidate.get(key) or []) if str(v).strip()]

        if not values:

            continue

        lines.append("• %s: %s" % (labels[key], "؛ ".join(values)))

    lines.append("")

    lines.append(phrases["ask"])

    return "\n".join(lines)


# ==========================================================
# THE MEMORY HANDOFF (TASK 4 — the boundary only)
# ==========================================================

def handoff_confirmed_entry(entry) -> Dict[str, Any]:

    """A storage-AGNOSTIC handoff descriptor.

    It declares the target and that memory is NOT implemented. It carries NO
    storage path, so the validation layer never knows storage details.
    """

    if not isinstance(entry, dict) or entry.get("contract") != ENTRY_CONTRACT:

        raise ArchitecturalKnowledgeValidationError(
            "handoff requires a confirmed entry (%s)" % (ENTRY_CONTRACT,)
        )

    return {
        "contract": HANDOFF_CONTRACT,
        "version": VERSION,
        "entry_id": entry.get("entry_id"),
        "review_id": entry.get("review_id"),
        "target": "ArchitecturalKnowledgeMemory",
        "memory_implemented": False,
        "written": False,
        "storage_agnostic": True,
        "storage_reference": None,
        "persistent": False,
        "read_only": True,
    }


# ==========================================================
# the public factory
# ==========================================================

def open_review(candidate, *, language=None) -> ArchitecturalKnowledgeReview:

    """Open a human review for an extracted candidate."""

    return ArchitecturalKnowledgeReview(candidate, language=language)


class HumanKnowledgeValidationLoopV1:

    """The validation loop. Stateless; the review carries the state."""

    __slots__ = ()

    CONTRACT = REVIEW_CONTRACT

    VERSION = VERSION

    AI_APPROVED = False

    AUTO_PROMOTED = False

    def open(self, candidate, **kwargs) -> ArchitecturalKnowledgeReview:

        return open_review(candidate, **kwargs)

    def prompt(self, review, **kwargs) -> str:

        return build_confirmation_prompt(review, **kwargs)

    def handoff(self, entry) -> Dict[str, Any]:

        return handoff_confirmed_entry(entry)

    def __repr__(self):

        return "HumanKnowledgeValidationLoopV1(human_confirms=True)"


human_knowledge_validation_loop = HumanKnowledgeValidationLoopV1()
