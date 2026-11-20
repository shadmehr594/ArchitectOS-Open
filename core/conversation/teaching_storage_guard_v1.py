# ==========================================================
# ArchitectOS Teaching Storage Guard v1
#
# PHASE 09 — MEMORY SAFETY
#
# Teaching knowledge MUST stay project-scoped.  It must never be
# attached to the pre-existing GLOBAL memory store:
#
#   memory/chat_memory.json
#   memory/chat_context.json
#   memory/project_history.json
#   memory/cognitive_memory_v66.json
#
# This module audits and enforces that, and it is read-only apart from
# refusing writes: `assert_path_allowed()` raises for any forbidden
# target, and `audit()` only reads.
# ==========================================================


from __future__ import annotations


import json
import os


from config import runtime_config as RC

from core.project.project_workspace_v1 import project_workspace


CONTRACT = "TeachingStorageGuardV1"
VERSION = "1.0"


# The pre-existing GLOBAL (non project-scoped) memory store.
GLOBAL_MEMORY_DIR = os.path.join(RC.REPO_ROOT, "memory")


GLOBAL_MEMORY_FILES = (
    "chat_memory.json",
    "chat_context.json",
    "project_history.json",
    "cognitive_memory_v66.json",
)


# Markers that would prove teaching data leaked into global memory.
TEACHING_MARKERS = (
    "teaching_candidate",
    "teaching_candidates",
    "candidate_id",
    "knowledge_class",
    "promotion_request",
    "source_turn_id",
)


# The ONLY storage the teaching layer is allowed to use.
ALLOWED_TEACHING_FILES = (
    "teaching_candidates.json",
    "promotion_requests.json",
)


ALLOWED_SUBDIR = "conversations"


def _read_text(path):

    try:

        with open(path, "r", encoding="utf-8", errors="replace") as handle:

            return handle.read()

    except Exception:

        return None


class TeachingStorageGuardV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self):

        print(
            "\U0001f6e1\ufe0f TEACHING STORAGE GUARD v1.0 ONLINE "
            "(project-scoped only)"
        )

    # ======================================================
    # ALLOWED ROOT
    # ======================================================

    def allowed_root(self, project_id):

        return os.path.join(
            project_workspace.project_dir(project_id),
            ALLOWED_SUBDIR,
        )

    def is_allowed_path(self, project_id, path):

        if not project_id or not path:

            return False

        root = os.path.abspath(self.allowed_root(project_id))

        target = os.path.abspath(path)

        if os.path.dirname(target) != root:

            return False

        return os.path.basename(target) in ALLOWED_TEACHING_FILES

    def assert_path_allowed(self, project_id, path):

        if not self.is_allowed_path(project_id, path):

            raise PermissionError(
                "Teaching storage must be one of %s inside the project's "
                "%s/ folder. Refused: %s"
                % (
                    list(ALLOWED_TEACHING_FILES),
                    ALLOWED_SUBDIR,
                    path,
                )
            )

        return True

    def assert_not_global_memory(self, path):

        text = os.path.abspath(str(path or "")).lower()

        global_dir = os.path.abspath(GLOBAL_MEMORY_DIR).lower()

        if text.startswith(global_dir):

            raise PermissionError(
                "Teaching knowledge must never be attached to the global "
                "memory store: " + str(path)
            )

        for name in GLOBAL_MEMORY_FILES:

            if text.endswith(name.lower()):

                raise PermissionError(
                    "Teaching knowledge must never be written to %s" % name
                )

        return True

    # ======================================================
    # AUDIT  (read-only)
    # ======================================================

    def audit(self, project_ids=None):

        global_files = []

        leaked = []

        for name in GLOBAL_MEMORY_FILES:

            path = os.path.join(GLOBAL_MEMORY_DIR, name)

            exists = os.path.isfile(path)

            entry = {
                "file": name,
                "path": path,
                "exists": exists,
                "bytes": os.path.getsize(path) if exists else 0,
                "contains_teaching_data": False,
                "markers_found": [],
            }

            if exists:

                text = _read_text(path) or ""

                found = [
                    marker for marker in TEACHING_MARKERS
                    if marker in text
                ]

                entry["markers_found"] = found

                entry["contains_teaching_data"] = bool(found)

                if found:

                    leaked.append(name)

            global_files.append(entry)

        # ---- project-scoped teaching storage ----
        projects = []

        for project_id in (project_ids or []):

            candidates_path = os.path.join(
                self.allowed_root(project_id),
                "teaching_candidates.json",
            )

            requests_path = os.path.join(
                self.allowed_root(project_id),
                "promotion_requests.json",
            )

            payload = None

            if os.path.isfile(candidates_path):

                try:

                    payload = json.load(
                        open(candidates_path, "r", encoding="utf-8")
                    )

                except Exception:

                    payload = None

            projects.append(
                {
                    "project_id": project_id,
                    "allowed_root": self.allowed_root(project_id),
                    "candidates_path": candidates_path,
                    "candidates_exists": os.path.isfile(candidates_path),
                    "candidates_path_allowed": self.is_allowed_path(
                        project_id, candidates_path
                    ),
                    "requests_path_allowed": self.is_allowed_path(
                        project_id, requests_path
                    ),
                    "candidate_count": len(
                        (payload or {}).get("candidates") or []
                    ),
                    "inside_project": os.path.abspath(
                        candidates_path
                    ).startswith(
                        os.path.abspath(
                            project_workspace.project_dir(project_id)
                        )
                    ),
                }
            )

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "audit_type": "read_only",
            "global_memory_dir": GLOBAL_MEMORY_DIR,
            "global_memory_files": global_files,
            "global_memory_clean": not leaked,
            "leaked_into_global_memory": leaked,
            "allowed_teaching_files": list(ALLOWED_TEACHING_FILES),
            "allowed_subdir": ALLOWED_SUBDIR,
            "teaching_storage_is_project_scoped": True,
            "projects": projects,
            "writes_performed": 0,
        }


teaching_storage_guard = TeachingStorageGuardV1()
