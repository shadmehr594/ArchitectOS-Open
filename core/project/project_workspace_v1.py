# ==========================================================
# ArchitectOS Project Workspace v1
#
# PROJECT_WORKSPACE_UI_06 — 06A PERSISTENT PROJECT WORKSPACE
#
# Core principle
#   PROJECT DATA MUST SURVIVE APPLICATION RESTARTS.
#   Session-only memory is not acceptable.
#
# Design
#   - One project = one folder = one `project.json` manifest.
#   - Internal identity is ALWAYS `project_id`; the display name is
#     user-defined and may repeat freely.
#   - Every write is ATOMIC (temp file in the same directory +
#     os.replace), so a crash can never leave a half-written
#     manifest.
#   - Deletion is a deliberate two-step contract: `delete_project`
#     moves the project into a quarantine/trash root and marks the
#     status `deleted`. Files are never hard-erased by default.
#   - All paths come from `config.runtime_config`. Nothing here
#     hardcodes a storage path.
# ==========================================================


from __future__ import annotations


import json
import os
import shutil
import threading
import time
import uuid


from config import runtime_config as RC


CONTRACT = "ProjectWorkspaceV1"
VERSION = "1.0"


STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"
STATUS_DELETED = "deleted"

STATUSES = (STATUS_ACTIVE, STATUS_ARCHIVED, STATUS_DELETED)


# ----------------------------------------------------------
# ATOMIC JSON IO
# ----------------------------------------------------------

def atomic_write_json(path, payload):

    """Write JSON atomically. A crash cannot corrupt the target."""

    folder = os.path.dirname(os.path.abspath(path))

    os.makedirs(folder, exist_ok=True)

    temp_path = os.path.join(
        folder,
        ".tmp_" + uuid.uuid4().hex[:12] + "_" + os.path.basename(path),
    )

    try:

        with open(temp_path, "w", encoding="utf-8") as handle:

            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                indent=2,
                default=str,
            )

            handle.flush()

            os.fsync(handle.fileno())

        # Atomic on the same filesystem / volume.
        os.replace(temp_path, path)

        return path

    except Exception:

        try:

            if os.path.isfile(temp_path):

                os.remove(temp_path)

        except Exception:

            pass

        raise


def read_json(path, default=None):

    try:

        with open(path, "r", encoding="utf-8") as handle:

            return json.load(handle)

    except Exception:

        return default


# ----------------------------------------------------------
# NAMING
# ----------------------------------------------------------

def new_project_id():

    return "project_" + uuid.uuid4().hex[:8]


def safe_display_name(name):

    cleaned = " ".join(str(name or "").split()).strip()

    return cleaned[:120]


# ----------------------------------------------------------
# WORKSPACE
# ----------------------------------------------------------

class ProjectWorkspace:

    VERSION = VERSION

    def __init__(self, projects_root=None, trash_root=None):

        self.projects_root = (
            projects_root or RC.PROJECTS_ROOT
        )

        self.trash_root = (
            trash_root or RC.PROJECT_TRASH_ROOT
        )

        self._lock = threading.RLock()

        os.makedirs(self.projects_root, exist_ok=True)

        os.makedirs(self.trash_root, exist_ok=True)

        print("📁 PROJECT WORKSPACE v1.0 ONLINE (persistent)")

    # ======================================================
    # PATHS
    # ======================================================

    def project_dir(self, project_id):

        return os.path.join(
            self.projects_root,
            str(project_id)
        )

    def manifest_path(self, project_id):

        return os.path.join(
            self.project_dir(project_id),
            RC.PROJECT_MANIFEST_FILE
        )

    def subdir(self, project_id, name):

        if name not in RC.PROJECT_SUBDIRS:

            raise ValueError("unknown project subdir: " + str(name))

        path = os.path.join(self.project_dir(project_id), name)

        os.makedirs(path, exist_ok=True)

        return path

    def ensure_dirs(self, project_id):

        os.makedirs(self.project_dir(project_id), exist_ok=True)

        for name in RC.PROJECT_SUBDIRS:

            os.makedirs(
                os.path.join(self.project_dir(project_id), name),
                exist_ok=True
            )

        return self.project_dir(project_id)

    # ======================================================
    # READ
    # ======================================================

    def exists(self, project_id):

        return os.path.isfile(self.manifest_path(project_id))

    def load(self, project_id):

        if not project_id:

            return None

        manifest = read_json(self.manifest_path(project_id))

        if not isinstance(manifest, dict):

            return None

        return manifest

    def list_projects(self, status=None, include_deleted=False):

        results = []

        if not os.path.isdir(self.projects_root):

            return results

        for entry in sorted(os.listdir(self.projects_root)):

            if not entry.startswith("project_"):

                continue

            manifest = self.load(entry)

            if not manifest:

                continue

            project_status = manifest.get("status")

            if project_status == STATUS_DELETED and not include_deleted:

                continue

            if status and project_status != status:

                continue

            results.append(manifest)

        return results

    def list_recent(self, limit=20, include_archived=False):

        projects = self.list_projects()

        if not include_archived:

            projects = [
                p for p in projects
                if p.get("status") == STATUS_ACTIVE
            ]

        projects.sort(
            key=lambda p: p.get("last_opened_at")
            or p.get("updated_at")
            or p.get("created_at")
            or 0,
            reverse=True,
        )

        return projects[: max(1, int(limit))]

    def list_archived(self):

        return self.list_projects(status=STATUS_ARCHIVED)

    # ======================================================
    # WRITE
    # ======================================================

    def _save(self, manifest):

        with self._lock:

            manifest["updated_at"] = time.time()

            atomic_write_json(
                self.manifest_path(manifest["project_id"]),
                manifest,
            )

            return manifest

    def create(self, name, description=None):

        display = safe_display_name(name)

        if not display:

            raise ValueError("project name is required")

        project_id = new_project_id()

        now = time.time()

        manifest = {

            "contract": CONTRACT,
            "version": VERSION,

            # internal identity
            "project_id": project_id,

            # user-defined display name (may repeat)
            "project_name": display,

            "description": safe_display_name(description) or None,

            "created_at": now,
            "updated_at": now,
            "last_opened_at": now,

            "status": STATUS_ACTIVE,

            "schema": 1,

            # ---- project-scoped state (hydrated on open) ----
            "session_id": project_id,

            "counters": {
                "upload": 0,
                "render": 0,
                "edit": 0,
                "document": 0,
                "export": 0,
            },

            "ui": {
                "mode": "auto",
                "render_profile": "auto",
                "seed_mode": "auto",
                "seed_value": None,
            },

            "active_asset_id": None,
            "last_uploaded_asset_id": None,
            "last_render_asset_id": None,
            "last_derived_asset_id": None,
        }

        with self._lock:

            self.ensure_dirs(project_id)

            atomic_write_json(self.manifest_path(project_id), manifest)

        print("🆕 PROJECT CREATED:", project_id, "|", display)

        return manifest

    def touch_opened(self, project_id):

        manifest = self.load(project_id)

        if not manifest:

            return None

        manifest["last_opened_at"] = time.time()

        return self._save(manifest)

    def rename(self, project_id, name):

        manifest = self.load(project_id)

        if not manifest:

            return None

        display = safe_display_name(name)

        if not display:

            raise ValueError("project name is required")

        manifest["project_name"] = display

        return self._save(manifest)

    def update_fields(self, project_id, fields):

        manifest = self.load(project_id)

        if not manifest:

            return None

        if isinstance(fields, dict):

            for key, value in fields.items():

                if key in ("project_id", "created_at"):

                    continue

                manifest[key] = value

        return self._save(manifest)

    def set_status(self, project_id, status):

        if status not in STATUSES:

            raise ValueError("invalid project status: " + str(status))

        manifest = self.load(project_id)

        if not manifest:

            return None

        manifest["status"] = status

        return self._save(manifest)

    # ======================================================
    # ARCHIVE / RESTORE
    # ======================================================

    def archive(self, project_id):

        return self.set_status(project_id, STATUS_ARCHIVED)

    def restore(self, project_id):

        return self.set_status(project_id, STATUS_ACTIVE)

    # ======================================================
    # DELETE  (safe, two-step)
    # ======================================================

    def delete(self, project_id, hard=False, confirmed=False):

        """Delete a project.

        Default behaviour is SAFE:
          - the folder is MOVED into the trash root (nothing erased)
          - the manifest status becomes `deleted`
          - `hard=True` erases the trashed folder, and requires
            `confirmed=True` explicitly.
        """

        manifest = self.load(project_id)

        if not manifest:

            return None

        manifest["status"] = STATUS_DELETED

        manifest["deleted_at"] = time.time()

        self._save(manifest)

        source = self.project_dir(project_id)

        destination = os.path.join(
            self.trash_root,
            str(project_id) + "_" + str(int(time.time()))
        )

        with self._lock:

            try:

                if os.path.isdir(source):

                    shutil.move(source, destination)

                    manifest["trashed_to"] = destination

            except Exception as error:

                manifest["trash_error"] = (
                    type(error).__name__ + ": " + str(error)
                )

        result = {
            "project_id": project_id,
            "status": STATUS_DELETED,
            "mode": "hard" if hard else "safe",
            "trashed_to": manifest.get("trashed_to"),
            "files_erased": False,
            "manifest": manifest,
        }

        if hard:

            if not confirmed:

                result["error"] = "hard_delete_requires_confirmation"

                result["mode"] = "safe"

                return result

            try:

                if os.path.isdir(destination):

                    shutil.rmtree(destination)

                result["files_erased"] = True

            except Exception as error:

                result["error"] = type(error).__name__ + ": " + str(error)

        return result

    def restore_from_trash(self, project_id, trashed_to):

        """Recover a safely deleted project."""

        target = self.project_dir(project_id)

        if os.path.isdir(target):

            return None

        if not trashed_to or not os.path.isdir(trashed_to):

            return None

        with self._lock:

            shutil.move(trashed_to, target)

        manifest = self.load(project_id)

        if manifest:

            manifest["status"] = STATUS_ACTIVE

            manifest.pop("trashed_to", None)

            manifest.pop("deleted_at", None)

            self._save(manifest)

        return manifest

    # ======================================================
    # EXPORT
    # ======================================================

    def export(self, project_id, destination=None):

        """Export the project manifest + managed assets.

        No DWG/IFC is promised: only files that actually exist inside
        the project folder are exported, together with lineage
        metadata.
        """

        manifest = self.load(project_id)

        if not manifest:

            return None

        source = self.project_dir(project_id)

        stamp = time.strftime("%Y%m%d_%H%M%S")

        if not destination:

            destination = os.path.join(
                self.subdir(project_id, "exports"),
                "architectos_export_"
                + str(project_id)
                + "_"
                + stamp
            )

        os.makedirs(destination, exist_ok=True)

        exported = []

        for root, _dirs, files in os.walk(source):

            if os.path.abspath(root).startswith(
                os.path.abspath(destination)
            ):

                continue

            for filename in files:

                absolute = os.path.join(root, filename)

                relative = os.path.relpath(absolute, source)

                target = os.path.join(destination, relative)

                os.makedirs(os.path.dirname(target), exist_ok=True)

                try:

                    shutil.copy2(absolute, target)

                    exported.append({
                        "relative_path": relative.replace("\\", "/"),
                        "size_bytes": os.path.getsize(target),
                    })

                except Exception as error:

                    exported.append({
                        "relative_path": relative.replace("\\", "/"),
                        "error": type(error).__name__,
                    })

        manifest_out = {

            "contract": "ProjectExportManifestV1",
            "version": "1.0",

            "exported_at": time.time(),
            "destination": destination,

            "project": manifest,

            "assets": exported,

            "asset_count": len(exported),
        }

        atomic_write_json(
            os.path.join(destination, "export_manifest.json"),
            manifest_out,
        )

        return manifest_out

    # ======================================================
    # DIAGNOSTICS
    # ======================================================

    def storage_report(self, project_id):

        manifest = self.load(project_id)

        if not manifest:

            return None

        report = {
            "project_id": project_id,
            "project_name": manifest.get("project_name"),
            "storage_path": self.project_dir(project_id),
            "folders": {},
        }

        for name in RC.PROJECT_SUBDIRS:

            path = os.path.join(self.project_dir(project_id), name)

            files = 0

            size = 0

            if os.path.isdir(path):

                for root, _dirs, names in os.walk(path):

                    for filename in names:

                        files += 1

                        try:

                            size += os.path.getsize(
                                os.path.join(root, filename)
                            )

                        except Exception:

                            pass

            report["folders"][name] = {
                "path": path,
                "files": files,
                "bytes": size,
            }

        return report


# ==========================================================
# SINGLETON
# ==========================================================

project_workspace = ProjectWorkspace()
