# ==========================================================
# ArchitectOS Knowledge Promotion Bridge v1
#
# PHASE 09 — WRITE BRIDGE PREPARATION
#
# A CONTROLLED FUTURE PROMOTION INTERFACE.  This module deliberately
# does NOT promote anything.
#
#   candidate
#      |
#   validation              <- deterministic, implemented here
#      |
#   future explicit approval <- recorded as a REQUEST, never executed
#      |
#   knowledge registry      <- NOT WRITTEN BY THIS PHASE
#
# Hard rules enforced in code:
#   - there is NO candidate -> knowledge path
#   - `promote()` raises NotImplementedError
#   - `PROMOTION_IMPLEMENTED = False`
#   - a promotion REQUEST is project-scoped bookkeeping, not knowledge
#   - nothing may ever target `memory/` (chat_memory.json,
#     chat_context.json, project_history.json, cognitive_memory_v66.json)
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

from core.conversation.teaching_candidate_v1 import (
    teaching_candidate_store,
    ALLOWED_STATUSES,
    FORBIDDEN_STATUSES,
    KNOWLEDGE_CLASSES,
    SCOPES,
    PROVENANCES,
    KNOWLEDGE_UNKNOWN,
)

from core.conversation.knowledge_read_bridge_v1 import (
    knowledge_read_bridge,
)


CONTRACT = "KnowledgePromotionBridgeV1"
VERSION = "1.0"


# Phase 09 does NOT implement promotion.
PROMOTION_IMPLEMENTED = False


STAGE_CANDIDATE = "candidate"
STAGE_VALIDATION = "validation"
STAGE_AWAITING_APPROVAL = "awaiting_explicit_approval"
STAGE_REJECTED_BY_VALIDATION = "rejected_by_validation"
STAGE_PROMOTED = "promoted"  # unreachable in Phase 09


ALL_STAGES = (
    STAGE_CANDIDATE,
    STAGE_VALIDATION,
    STAGE_AWAITING_APPROVAL,
    STAGE_REJECTED_BY_VALIDATION,
    STAGE_PROMOTED,
)


REQUEST_FILE = "promotion_requests.json"

MAX_REQUESTS = 200


# Paths that must NEVER be a promotion target (PHASE 09 §6).
FORBIDDEN_TARGETS = (
    "memory/",
    "memory\\",
    "chat_memory.json",
    "chat_context.json",
    "project_history.json",
    "cognitive_memory_v66.json",
)


# Known knowledge registries a future phase MAY target (declared only).
KNOWN_TARGETS = (
    "human_architectural_learning_registry_v1",
    "residential_pattern_library",
    "residential_negative_pattern_library",
    "architectural_ontology",
    "architectural_space_knowledge_v1",
)


def new_request_id():

    return "pr_" + uuid.uuid4().hex[:12]


def _is_forbidden_target(target):

    text = str(target or "").lower()

    return any(
        marker.lower() in text for marker in FORBIDDEN_TARGETS
    )


class KnowledgePromotionBridgeV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, store=None, read_bridge=None):

        self.store = store or teaching_candidate_store

        self.read_bridge = read_bridge or knowledge_read_bridge

        print(
            "\U0001f512 KNOWLEDGE PROMOTION BRIDGE v1.0 ONLINE "
            "(validation only \u2014 promotion NOT implemented)"
        )

    # ======================================================
    # VALIDATION
    # ======================================================

    def validate_candidate(self, candidate, project_id=None):

        """Deterministic validation of a candidate for a FUTURE promotion.

        This never promotes anything. It answers the question "is this
        candidate even eligible to be considered later?".
        """

        checks = []

        blockers = []

        warnings = []

        candidate = candidate or {}

        def check(name, passed, detail=None, blocking=True):

            checks.append(
                {"check": name, "passed": bool(passed), "detail": detail}
            )

            if not passed and blocking:

                blockers.append(name)

            elif not passed:

                warnings.append(name)

            return bool(passed)

        # ---- identity ----
        check(
            "has_candidate_id",
            bool(candidate.get("candidate_id")),
            candidate.get("candidate_id"),
        )

        check(
            "has_source_turn_id",
            bool(candidate.get("source_turn_id")),
            candidate.get("source_turn_id"),
        )

        check(
            "has_raw_statement",
            bool(str(candidate.get("raw_statement") or "").strip()),
            None,
        )

        # ---- project binding (isolation is mandatory) ----
        bound_project = candidate.get("project_id")

        check(
            "project_bound",
            bool(bound_project),
            bound_project,
        )

        if project_id:

            check(
                "project_matches_request",
                bound_project == project_id,
                {"candidate": bound_project, "request": project_id},
            )

        # ---- status must stay a CANDIDATE status ----
        status = candidate.get("status")

        check(
            "status_allowed",
            status in ALLOWED_STATUSES,
            status,
        )

        check(
            "status_not_permanent",
            status not in FORBIDDEN_STATUSES,
            status,
        )

        check(
            "not_already_learned",
            candidate.get("is_learned_knowledge") is not True
            and candidate.get("is_permanent") is not True,
            None,
        )

        # ---- PHASE 09 taxonomy ----
        check(
            "knowledge_class_present",
            candidate.get("knowledge_class") in KNOWLEDGE_CLASSES,
            candidate.get("knowledge_class"),
        )

        check(
            "knowledge_class_known",
            candidate.get("knowledge_class") != KNOWLEDGE_UNKNOWN,
            candidate.get("knowledge_class"),
        )

        check(
            "scope_present",
            candidate.get("scope") in SCOPES,
            candidate.get("scope"),
        )

        check(
            "provenance_present",
            candidate.get("provenance") in PROVENANCES,
            candidate.get("provenance"),
        )

        check(
            "domain_present",
            bool(candidate.get("domain"))
            and candidate.get("domain") != "unknown",
            candidate.get("domain"),
        )

        check(
            "normalized_meaning_present",
            bool(str(candidate.get("normalized_meaning") or "").strip()),
            None,
        )

        # ---- conflicts with the existing corpus (read-only lookup) ----
        conflict = self._corpus_conflict(candidate)

        check(
            "no_corpus_conflict",
            not conflict.get("conflict"),
            conflict,
            blocking=False,
        )

        return {
            "contract": CONTRACT + ".Validation",
            "version": VERSION,
            "candidate_id": candidate.get("candidate_id"),
            "project_id": bound_project,
            "passed": not blockers,
            "blockers": blockers,
            "warnings": warnings,
            "checks": checks,
            "corpus_consulted": True,
            "read_only": True,
            "writes_performed": 0,
            "promotion_implemented": False,
        }

    # ------------------------------------------------------

    def _corpus_conflict(self, candidate):

        """Read-only check against the EXISTING corpus.

        Reports whether the corpus already contains an item with the
        same generalization, so a future phase does not duplicate it.
        """

        try:

            existing = self.read_bridge.learning_registry()

        except Exception as error:

            return {
                "conflict": False,
                "checked": False,
                "error": type(error).__name__ + ": " + str(error),
            }

        text = str(candidate.get("raw_statement") or "").strip().lower()

        matches = [
            item.get("id")
            for item in existing
            if text
            and str(item.get("human_observation_fa") or "").strip().lower()
            == text
        ]

        return {
            "conflict": bool(matches),
            "checked": True,
            "registry_size": len(existing),
            "matching_items": matches,
        }

    # ======================================================
    # PROMOTION REQUEST  (recorded, never executed)
    # ======================================================

    def path(self, project_id):

        if not project_id:

            return None

        return os.path.join(
            project_workspace.project_dir(project_id),
            "conversations",
            REQUEST_FILE,
        )

    def load_requests(self, project_id):

        path = self.path(project_id)

        if not path:

            return []

        payload = read_json(path, default=None)

        if not isinstance(payload, dict):

            return []

        return list(payload.get("requests") or [])

    def request_promotion(
        self,
        candidate_id,
        project_id,
        target_registry=None,
        requested_by="human",
        note=None,
    ):

        """Record an EXPLICIT promotion request. Never promotes."""

        if not project_id:

            return {
                "status": "error",
                "error": "project_id_required",
                "promotion_implemented": False,
            }

        if not project_workspace.exists(project_id):

            return {
                "status": "error",
                "error": "project_not_found",
                "project_id": project_id,
                "promotion_implemented": False,
            }

        target = target_registry or "human_architectural_learning_registry_v1"

        if _is_forbidden_target(target):

            return {
                "status": "error",
                "error": "forbidden_target",
                "target_registry": target,
                "reason": (
                    "Teaching knowledge must never be attached to the "
                    "global memory store."
                ),
                "promotion_implemented": False,
            }

        candidate = self.store.get(project_id, candidate_id)

        if candidate is None:

            return {
                "status": "error",
                "error": "candidate_not_found",
                "candidate_id": candidate_id,
                "project_id": project_id,
                "promotion_implemented": False,
            }

        validation = self.validate_candidate(
            candidate, project_id=project_id
        )

        request = {
            "request_id": new_request_id(),
            "candidate_id": candidate_id,
            "project_id": project_id,
            "target_registry": target,
            "requested_by": requested_by,
            "note": note,
            "created_at": time.time(),
            "stage": (
                STAGE_AWAITING_APPROVAL
                if validation["passed"]
                else STAGE_REJECTED_BY_VALIDATION
            ),
            "validation": validation,
            "approved": False,
            "approved_by": None,
            "approved_at": None,
            "promoted": False,
            "promotion_implemented": False,
        }

        path = self.path(project_id)

        payload = read_json(path, default=None)

        if not isinstance(payload, dict):

            payload = {
                "contract": CONTRACT,
                "version": VERSION,
                "project_id": project_id,
                "promotion_implemented": False,
                "requests": [],
            }

        requests = list(payload.get("requests") or [])

        requests.append(request)

        payload["requests"] = requests[-MAX_REQUESTS:]

        payload["project_id"] = project_id

        payload["promotion_implemented"] = False

        atomic_write_json(path, payload)

        return {
            "status": "success",
            "request": request,
            "validation": validation,
            "promotion_implemented": False,
            "knowledge_registry_written": False,
            "message": (
                "Request recorded. Promotion requires an explicit future "
                "approval step and is NOT implemented in Phase 09."
            ),
        }

    # ======================================================
    # PROMOTION  (intentionally impossible)
    # ======================================================

    def promote(self, *args, **kwargs):

        raise NotImplementedError(
            "PHASE 09 does not implement knowledge promotion. A teaching "
            "candidate can never become knowledge automatically."
        )

    def approve(self, *args, **kwargs):

        raise NotImplementedError(
            "PHASE 09 does not implement promotion approval. Explicit "
            "approval belongs to a later phase."
        )

    # ======================================================
    # SAFETY / SELF-CHECK
    # ======================================================

    def status(self, project_id=None):

        requests = self.load_requests(project_id) if project_id else []

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "promotion_implemented": False,
            "approval_implemented": False,
            "direct_candidate_to_knowledge_path": False,
            "global_memory_used": False,
            "targets_forbidden": list(FORBIDDEN_TARGETS),
            "known_targets": list(KNOWN_TARGETS),
            "project_id": project_id,
            "request_count": len(requests),
            "requests_awaiting_approval": len(
                [
                    r for r in requests
                    if r.get("stage") == STAGE_AWAITING_APPROVAL
                ]
            ),
            "requests_promoted": 0,
        }

    def assert_no_direct_path(self):

        """Prove the forbidden shortcut does not exist."""

        if PROMOTION_IMPLEMENTED:

            raise AssertionError("Phase 09 must not implement promotion")

        for name in ("promote", "approve"):

            method = getattr(self, name)

            try:

                method("x", "y")

            except NotImplementedError:

                continue

            raise AssertionError(
                "%s() must raise NotImplementedError in Phase 09" % name
            )

        return True


knowledge_promotion_bridge = KnowledgePromotionBridgeV1()
