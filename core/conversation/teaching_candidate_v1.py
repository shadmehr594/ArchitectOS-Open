# ==========================================================
# ArchitectOS Teaching Candidate v1
#
# PHASE 08C — TEACHING CANDIDATE CONTRACT
#
# A TeachingCandidate is something the user said that MAY later become
# learned architectural knowledge.  In Phase 08 it is ONLY a candidate.
#
# Semantic shape
#   candidate_id        stable id
#   project_id          owning project (isolation boundary)
#   source_turn_id      the conversational turn it came from
#   source_type         "text" | "voice"
#   language            "fa" | "en" | "mixed" | "unknown"
#   raw_statement       the user's words, verbatim
#   normalized_meaning  deterministic restatement (NOT truth)
#   domain              subject / domain
#   candidate_kind      preference | rule | constraint | definition |
#                       correction | observation
#   confidence          heuristic classifier confidence (not a probability
#                       of architectural correctness)
#   status              observed | needs_confirmation | rejected
#
# HARD RULE (Phase 08)
#   "learned" / "accepted_as_truth" DO NOT EXIST as statuses.  There is no
#   code path that can set them.  `promote()` is intentionally absent and
#   `assert_not_learned()` raises if a caller tries.
#
# Persistence
#   <project>/conversations/teaching_candidates.json   (atomic writes)
#   Candidates never leave their project.
# ==========================================================


from __future__ import annotations


import os
import time
import uuid


from core.project.project_workspace_v1 import (
    project_workspace,
    atomic_write_json,
    read_json,
)

from core.conversation.teaching_meaning_v1 import (
    extract_meaning,
    ALL_KNOWLEDGE_CLASSES,
    ALL_SCOPES,
    ALL_PROVENANCES,
    KNOWLEDGE_UNKNOWN,
    SCOPE_CURRENT_PROJECT,
    PROVENANCE_HUMAN_TEACHER,
)


CONTRACT = "TeachingCandidateV1"
VERSION = "1.0"


# ----------------------------------------------------------
# STATUSES
# ----------------------------------------------------------

STATUS_OBSERVED = "observed"
STATUS_NEEDS_CONFIRMATION = "needs_confirmation"
STATUS_REJECTED = "rejected"


ALLOWED_STATUSES = (
    STATUS_OBSERVED,
    STATUS_NEEDS_CONFIRMATION,
    STATUS_REJECTED,
)


# Explicitly forbidden in Phase 08.  Kept as a named tuple so the
# refusal is testable and self-documenting.
FORBIDDEN_STATUSES = (
    "learned",
    "accepted_as_truth",
    "accepted",
    "truth",
    "confirmed",
    "active",
    "permanent",
)


# Phase 08 does NOT implement permanent learning.
PERMANENT_LEARNING_IMPLEMENTED = False


SOURCE_TYPES = ("text", "voice")


CANDIDATE_KINDS = (
    "preference",
    "rule",
    "constraint",
    "definition",
    "correction",
    "observation",
)


# PHASE 09 — the candidate carries a LEARNING TAXONOMY so that facts,
# patterns, preferences, project decisions and observations can never
# collapse into one category.  Vocabularies live in teaching_meaning_v1.
KNOWLEDGE_CLASSES = ALL_KNOWLEDGE_CLASSES

SCOPES = ALL_SCOPES

PROVENANCES = ALL_PROVENANCES


MAX_CANDIDATES = 500


def new_candidate_id():

    return "tc_" + uuid.uuid4().hex[:12]


def new_turn_id():

    return "turn_" + uuid.uuid4().hex[:12]


# ----------------------------------------------------------
# CONTRACT
# ----------------------------------------------------------

class TeachingCandidate:

    CONTRACT = CONTRACT
    VERSION = VERSION

    FIELDS = (
        "candidate_id",
        "project_id",
        "source_turn_id",
        "source_type",
        "language",
        "raw_statement",
        "normalized_meaning",
        "domain",
        "candidate_kind",
        "confidence",
        "status",
        # PHASE 09 — learning taxonomy
        "knowledge_class",
        "scope",
        "provenance",
        "confidence_kind",
        "domain_tags",
        # CURRICULUM_FOUNDATION_FIX_02 — a descriptive zone assignment
        "zone_assignment",
        # TEACHING_CONTEXT_01 — the architectural space this teaching
        # statement is attached to (a corpus space id), so a following
        # statement can inherit the active topic.
        "space_topic",
        # additive, audit-only
        "entities",
        "relations",
        "polarity",
        "turn_kind",
        "created_at",
        "updated_at",
        "contract",
        "version",
    )

    def __init__(
        self,
        raw_statement="",
        project_id=None,
        source_turn_id=None,
        source_type="text",
        language="unknown",
        normalized_meaning="",
        domain="unknown",
        candidate_kind="observation",
        confidence=0.0,
        status=STATUS_OBSERVED,
        candidate_id=None,
        entities=None,
        relations=None,
        polarity="neutral",
        turn_kind=None,
        created_at=None,
        knowledge_class=None,
        scope=None,
        provenance=None,
        domain_tags=None,
        zone_assignment=None,
        space_topic=None,
        # CLAUSE_ANALYSIS_01 — which part of the message this is
        clause_role=None,
        clause_index=None,
        clause_count=None,
        source_statement=None,
        rationale=None,
    ):

        self.candidate_id = candidate_id or new_candidate_id()

        self.project_id = project_id

        self.source_turn_id = source_turn_id or new_turn_id()

        self.source_type = (
            source_type if source_type in SOURCE_TYPES else "text"
        )

        self.language = language or "unknown"

        self.raw_statement = str(raw_statement or "")

        self.normalized_meaning = str(normalized_meaning or "")

        self.domain = domain or "unknown"

        self.candidate_kind = (
            candidate_kind if candidate_kind in CANDIDATE_KINDS
            else "observation"
        )

        self.confidence = float(confidence or 0.0)

        # Heuristic LEARNING-STATE confidence — never a probability that
        # the statement is architecturally true.
        self.confidence_kind = "learning_state"

        self.status = self._validate_status(status)

        # ---- PHASE 09 — learning taxonomy (validated vocabularies) ----
        self.knowledge_class = (
            knowledge_class if knowledge_class in KNOWLEDGE_CLASSES
            else KNOWLEDGE_UNKNOWN
        )

        self.scope = scope if scope in SCOPES else SCOPE_CURRENT_PROJECT

        self.provenance = (
            provenance if provenance in PROVENANCES
            else PROVENANCE_HUMAN_TEACHER
        )

        self.domain_tags = list(domain_tags or [])

        # A resolved zone assignment: {zone, zone_label, phrase} or None.
        self.zone_assignment = (
            dict(zone_assignment)
            if isinstance(zone_assignment, dict)
            else None
        )

        # TEACHING_CONTEXT_01 — the corpus space id this statement is
        # attached to, or None. Used as the ACTIVE TOPIC for the next
        # teaching statement in this project.
        self.space_topic = (
            str(space_topic) if space_topic else None
        )

        # ==================================================
        # CLAUSE_ANALYSIS_01 — WHICH PART of the teacher's message this
        # candidate is.
        #
        # One long message can carry several rules plus their reasons.
        # `raw_statement` is now the CLAUSE, `source_statement` is the
        # whole message it came from, `clause_role` says whether this
        # part is a rule / definition / observation, and `rationale`
        # keeps the teacher's own explanation WITHOUT storing it as a
        # fact.
        # ==================================================
        self.clause_role = (
            str(clause_role) if clause_role else None
        )

        self.clause_index = (
            int(clause_index)
            if isinstance(clause_index, int)
            else None
        )

        self.clause_count = (
            int(clause_count)
            if isinstance(clause_count, int)
            else None
        )

        self.source_statement = (
            str(source_statement) if source_statement else None
        )

        self.rationale = (
            str(rationale) if rationale else None
        )

        self.entities = list(entities or [])

        self.relations = list(relations or [])

        self.polarity = polarity or "neutral"

        self.turn_kind = turn_kind

        self.created_at = created_at or time.time()

        self.updated_at = self.created_at

    # --------------------------------------------------

    @staticmethod
    def _validate_status(status):

        if status in FORBIDDEN_STATUSES:

            raise ValueError(
                "Phase 08 forbids teaching-candidate status %r: "
                "a user statement is not architectural truth."
                % (status,)
            )

        if status not in ALLOWED_STATUSES:

            raise ValueError(
                "unknown teaching-candidate status %r (allowed: %s)"
                % (status, ", ".join(ALLOWED_STATUSES))
            )

        return status

    def set_status(self, status):

        self.status = self._validate_status(status)

        self.updated_at = time.time()

        return self.status

    def to_dict(self):

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "candidate_id": self.candidate_id,
            "project_id": self.project_id,
            "source_turn_id": self.source_turn_id,
            "source_type": self.source_type,
            "language": self.language,
            "raw_statement": self.raw_statement,
            "normalized_meaning": self.normalized_meaning,
            "domain": self.domain,
            "candidate_kind": self.candidate_kind,
            "confidence": self.confidence,
            "status": self.status,
            # PHASE 09 — learning taxonomy
            "knowledge_class": self.knowledge_class,
            "scope": self.scope,
            "provenance": self.provenance,
            "confidence_kind": self.confidence_kind,
            "domain_tags": self.domain_tags,
            "zone_assignment": self.zone_assignment,
            "space_topic": self.space_topic,
            # CLAUSE_ANALYSIS_01 — which part of the message this is
            "clause_role": self.clause_role,
            "clause_index": self.clause_index,
            "clause_count": self.clause_count,
            "source_statement": self.source_statement,
            "rationale": self.rationale,
            "entities": self.entities,
            "relations": self.relations,
            "polarity": self.polarity,
            "turn_kind": self.turn_kind,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            # truth flags — machine readable, never optimistic
            "is_learned_knowledge": False,
            "is_permanent": False,
        }

    @classmethod
    def from_dict(cls, data):

        if not isinstance(data, dict):

            raise ValueError("candidate payload must be a dict")

        return cls(
            candidate_id=data.get("candidate_id"),
            project_id=data.get("project_id"),
            source_turn_id=data.get("source_turn_id"),
            source_type=data.get("source_type", "text"),
            language=data.get("language", "unknown"),
            raw_statement=data.get("raw_statement", ""),
            normalized_meaning=data.get("normalized_meaning", ""),
            domain=data.get("domain", "unknown"),
            candidate_kind=data.get("candidate_kind", "observation"),
            confidence=data.get("confidence", 0.0),
            status=data.get("status", STATUS_OBSERVED),
            entities=data.get("entities"),
            relations=data.get("relations"),
            polarity=data.get("polarity", "neutral"),
            turn_kind=data.get("turn_kind"),
            created_at=data.get("created_at"),
            knowledge_class=data.get("knowledge_class"),
            scope=data.get("scope"),
            provenance=data.get("provenance"),
            domain_tags=data.get("domain_tags"),
            zone_assignment=data.get("zone_assignment"),
            space_topic=data.get("space_topic"),
            clause_role=data.get("clause_role"),
            clause_index=data.get("clause_index"),
            clause_count=data.get("clause_count"),
            source_statement=data.get("source_statement"),
            rationale=data.get("rationale"),
        )


# ----------------------------------------------------------
# BUILDER
# ----------------------------------------------------------

# Turn kinds that may produce a candidate at all.
_CANDIDATE_TURN_KINDS = (
    "TEACHING_STATEMENT",
    "CORRECTION",
)


def build_candidate(
    text,
    project_id=None,
    source_turn_id=None,
    source_type="text",
    language=None,
    turn_kind=None,
    context=None,
    clause_role=None,
    clause_index=None,
    clause_count=None,
    source_statement=None,
    rationale=None,
):

    """Build a candidate from a user statement.

    `context` is OPTIONAL and additive: it carries the teaching context
    (an `active_topic` space id) down to the meaning extraction, so a
    follow-up statement stays attached to the active architectural space.

    Returns None when the turn is not a teaching/correction turn — an
    INSTRUCTION, QUESTION or small-talk turn must never become a
    teaching candidate.
    """

    if turn_kind not in _CANDIDATE_TURN_KINDS:

        return None

    meaning = extract_meaning(text, turn_kind=turn_kind, context=context)

    if language:

        meaning["language"] = language

    # Phase 08/09 status policy:
    #   a statement that carries no architectural domain signal at all
    #   is `rejected` (nothing usable was observed); everything else is
    #   `observed` until a later phase explicitly asks the user.
    if meaning.get("domain") == "unknown":

        status = STATUS_REJECTED

    else:

        status = STATUS_OBSERVED

    return TeachingCandidate(

        raw_statement=str(text or ""),

        project_id=project_id,

        source_turn_id=source_turn_id,

        source_type=source_type,

        language=meaning.get("language", "unknown"),

        normalized_meaning=meaning.get("normalized_meaning", ""),

        domain=meaning.get("domain", "unknown"),

        candidate_kind=meaning.get("candidate_kind", "observation"),

        confidence=meaning.get("confidence", 0.0),

        status=status,

        entities=meaning.get("entities"),

        relations=meaning.get("relations"),

        polarity=meaning.get("polarity", "neutral"),

        turn_kind=turn_kind,

        # PHASE 09 — learning taxonomy
        knowledge_class=meaning.get("knowledge_class"),

        scope=meaning.get("scope"),

        provenance=meaning.get("provenance"),

        domain_tags=meaning.get("domain_tags"),

        # CURRICULUM_FOUNDATION_FIX_02 — carry the resolved zone
        zone_assignment=meaning.get("zone_assignment"),

        # TEACHING_CONTEXT_01 — carry the resolved architectural space
        space_topic=meaning.get("space_topic"),

        # CLAUSE_ANALYSIS_01 — which part of the message this is
        clause_role=clause_role,

        clause_index=clause_index,

        clause_count=clause_count,

        source_statement=source_statement,

        rationale=rationale,
    )


# ----------------------------------------------------------
# STORE  (project-scoped, persisted, candidates only)
# ----------------------------------------------------------

class TeachingCandidateStoreV1:

    CONTRACT = "TeachingCandidateStoreV1"
    VERSION = VERSION

    FILE = "teaching_candidates.json"

    def __init__(self):

        print(
            "\U0001f4da TEACHING CANDIDATE STORE v1.0 ONLINE "
            "(candidates only \u2014 no permanent learning)"
        )

    # --------------------------------------------------

    def path(self, project_id):

        """Storage path.

        Deliberately does NOT use `project_workspace.subdir()`, which
        creates folders: a read must never materialise a project. Only
        `save()` creates the folder, and it is only ever called for a
        project that really exists.
        """

        if not project_id:

            return None

        return os.path.join(
            project_workspace.project_dir(project_id),
            "conversations",
            self.FILE,
        )

    def _empty(self, project_id):

        return {

            "contract": self.CONTRACT,
            "version": VERSION,

            "project_id": project_id,

            "permanent_learning_implemented": False,

            "allowed_statuses": list(ALLOWED_STATUSES),

            "candidates": [],
        }

    # --------------------------------------------------

    def load(self, project_id):

        path = self.path(project_id)

        if not path:

            return self._empty(project_id)

        payload = read_json(path, default=None)

        if not isinstance(payload, dict):

            return self._empty(project_id)

        payload.setdefault("candidates", [])

        payload["permanent_learning_implemented"] = False

        payload["allowed_statuses"] = list(ALLOWED_STATUSES)

        return payload

    def save(self, project_id, payload):

        path = self.path(project_id)

        if not path:

            return None

        # A candidate belongs to a REAL project. Refuse to materialise a
        # project folder for a bare session id.
        if not project_workspace.exists(project_id):

            print(
                "PHASE 08: refusing to persist teaching candidates for a "
                "non-project session:",
                project_id,
            )

            return None

        payload = dict(payload or {})

        payload["contract"] = self.CONTRACT

        payload["version"] = VERSION

        payload["project_id"] = project_id

        payload["permanent_learning_implemented"] = False

        payload["allowed_statuses"] = list(ALLOWED_STATUSES)

        payload["updated_at"] = time.time()

        # Defensive: refuse to persist a forbidden status even if a
        # caller hand-built the payload.
        for entry in payload.get("candidates") or []:

            status = (entry or {}).get("status")

            if status in FORBIDDEN_STATUSES:

                raise ValueError(
                    "refusing to persist forbidden candidate status %r"
                    % (status,)
                )

        atomic_write_json(path, payload)

        return payload

    # --------------------------------------------------

    def record(
        self,
        project_id,
        candidate,
        turn_kind=None,
    ):

        """Append a candidate. Returns the persisted candidate dict."""

        if candidate is None:

            return None

        if isinstance(candidate, TeachingCandidate):

            entry = candidate.to_dict()

        elif isinstance(candidate, dict):

            entry = dict(candidate)

            entry["status"] = TeachingCandidate._validate_status(
                entry.get("status", STATUS_OBSERVED)
            )

        else:

            raise ValueError("candidate must be a TeachingCandidate or dict")

        entry["project_id"] = project_id

        payload = self.load(project_id)

        candidates = list(payload.get("candidates") or [])

        candidates.append(entry)

        payload["candidates"] = candidates[-MAX_CANDIDATES:]

        payload["candidate_count"] = len(payload["candidates"])

        self.save(project_id, payload)

        return entry

    # --------------------------------------------------

    def candidates(self, project_id, status=None, domain=None):

        entries = list(self.load(project_id).get("candidates") or [])

        if status:

            entries = [e for e in entries if e.get("status") == status]

        if domain:

            entries = [e for e in entries if e.get("domain") == domain]

        return entries

    def get(self, project_id, candidate_id):

        for entry in self.candidates(project_id):

            if entry.get("candidate_id") == candidate_id:

                return entry

        return None

    def count(self, project_id):

        return len(self.candidates(project_id))

    def learned_count(self, project_id):

        """Always 0 in Phase 08 — permanent learning is not implemented."""

        return len(
            [
                e for e in self.candidates(project_id)
                if e.get("status") in FORBIDDEN_STATUSES
            ]
        )

    def clear(self, project_id):

        return self.save(project_id, self._empty(project_id))

    # --------------------------------------------------

    def assert_not_learned(self, project_id):

        """Raise if any candidate somehow carries a permanent status."""

        for entry in self.candidates(project_id):

            if entry.get("status") in FORBIDDEN_STATUSES:

                raise AssertionError(
                    "Phase 08 violation: candidate %s has permanent "
                    "status %r"
                    % (entry.get("candidate_id"), entry.get("status"))
                )

        return True

    def promote(self, *args, **kwargs):

        raise NotImplementedError(
            "Phase 08 does not implement permanent learning. A teaching "
            "candidate cannot be promoted to learned knowledge in this "
            "phase."
        )


teaching_candidate_store = TeachingCandidateStoreV1()
