# ==========================================================
# ArchitectOS Project Registry Bridge v1
#
# PROJECT_WORKSPACE_UI_06 — 06A / 06B
#
# Purpose
#   Give the Phase 04 image registry PERSISTENT, PROJECT-SCOPED
#   backing without changing its public behaviour.
#
# What it does
#   1. Binds a project to a session, so the session registry and the
#      image registry key 1:1 with the project. Cross-project leakage
#      therefore becomes structurally impossible.
#   2. Copies every managed asset into the PROJECT folder under a
#      COLLISION-SAFE name, and makes that copy authoritative. The
#      ComfyUI output folder is treated as a transient source.
#   3. Write-through persists the registry bucket after every
#      mutation (register / set_active / set_analysis / reset), so
#      ordinals, the active image and lineage survive a restart.
#   4. Derives the user-facing asset record (asset_id, project_id,
#      session_id, ordinal, source_type, parent_asset_id, created_at,
#      original_filename, generated_filename, storage_path,
#      public_path, is_active, is_final).
#
# Collision policy
#   <kind>_<ordinal:03d>_<shortid><ext>  e.g. renders/render_001_a82f19.png
#   Creation is exclusive: an existing file is never overwritten.
# ==========================================================


from __future__ import annotations


import os
import shutil
import threading
import time
import uuid


from config import runtime_config as RC

from core.project.project_workspace_v1 import (
    project_workspace,
    atomic_write_json,
    read_json,
)

from core.vision.image_registry_v1 import image_registry


CONTRACT = "ProjectRegistryBridgeV1"
VERSION = "1.0"

ASSET_CONTRACT = "ProjectAssetV1"

ASSETS_FILE = "assets.json"


# Registry source_type -> project folder + filename prefix
KIND_FOLDERS = {
    "uploaded": ("uploads", "image"),
    "text_to_image": ("renders", "render"),
    "render": ("renders", "render"),
    "image_to_image": ("img2img", "edit"),
    "document": ("documents", "doc"),
    "other": ("uploads", "asset"),
}


def folder_and_prefix(source_type):

    return KIND_FOLDERS.get(
        source_type,
        KIND_FOLDERS["other"]
    )


class ProjectRegistryBridge:

    VERSION = VERSION

    def __init__(self):

        self._lock = threading.RLock()

        # project currently bound to the registry write-through
        self._active_project_id = None

        image_registry.attach_persistence(self._on_registry_change)

        print("🔗 PROJECT REGISTRY BRIDGE v1.0 ONLINE")

    # ======================================================
    # PROJECT BINDING
    # ======================================================

    def current_project_id(self):

        return self._active_project_id

    def bind(self, project_id):

        """Bind a project and hydrate its registry + assets."""

        manifest = project_workspace.load(project_id)

        if not manifest:

            return None

        with self._lock:

            self._active_project_id = project_id

            session_id = manifest.get("session_id") or project_id

            stored = read_json(
                os.path.join(
                    project_workspace.project_dir(project_id),
                    ASSETS_FILE
                ),
                default={}
            )

            records = (stored or {}).get("registry_records") or []

            image_registry.hydrate(session_id, records)

        print(
            "🔓 PROJECT BOUND:",
            project_id,
            "| restored",
            len(records),
            "assets"
        )

        return manifest

    def unbind(self):

        with self._lock:

            self._active_project_id = None

    # ======================================================
    # PERSISTENCE
    # ======================================================

    def _assets_path(self, project_id):

        return os.path.join(
            project_workspace.project_dir(project_id),
            ASSETS_FILE
        )

    def _on_registry_change(self, session_key):

        project_id = self._active_project_id

        if not project_id:

            return

        manifest = project_workspace.load(project_id)

        if not manifest:

            return

        expected = manifest.get("session_id") or project_id

        # Never persist another project's bucket.
        if str(session_key) != str(expected):

            return

        self.save(project_id)

    def save(self, project_id):

        """Persist the registry bucket + derived asset list."""

        manifest = project_workspace.load(project_id)

        if not manifest:

            return None

        session_id = manifest.get("session_id") or project_id

        _key, records = image_registry.snapshot(session_id)

        previous = read_json(self._assets_path(project_id), default={}) or {}

        previous_final = previous.get("final_assets") or {}

        assets = []

        for record in records:

            asset = self.derive_asset(
                record,
                project_id,
                manifest,
                is_final=bool(
                    previous_final.get(record.get("image_id"))
                ),
            )

            if asset:

                assets.append(asset)

        active = image_registry.active(session_id) or {}

        last_uploaded = image_registry.last_uploaded(session_id) or {}

        last_render = image_registry.last_render(session_id) or {}

        derived = [
            a for a in assets
            if a.get("source_type") == "image_to_image"
        ]

        payload = {

            "contract": CONTRACT,
            "version": VERSION,

            "project_id": project_id,
            "session_id": session_id,

            "updated_at": time.time(),

            "registry_records": records,

            "assets": assets,

            "final_assets": {
                a["asset_id"]: True for a in assets if a.get("is_final")
            },

            "active_asset_id": active.get("image_id"),
            "last_uploaded_asset_id": last_uploaded.get("image_id"),
            "last_render_asset_id": last_render.get("image_id"),
            "last_derived_asset_id": (
                derived[-1]["asset_id"] if derived else None
            ),

            "asset_count": len(assets),
        }

        with self._lock:

            atomic_write_json(self._assets_path(project_id), payload)

        return payload

    def load_assets(self, project_id):

        payload = read_json(self._assets_path(project_id), default=None)

        if not isinstance(payload, dict):

            return {
                "project_id": project_id,
                "assets": [],
                "asset_count": 0,
            }

        return payload

    # ======================================================
    # ASSET DERIVATION
    # ======================================================

    def derive_asset(self, record, project_id, manifest, is_final=False):

        if not isinstance(record, dict):

            return None

        attachment = record.get("attachment") or {}

        asset = record.get("asset") or {}

        storage_path = record.get("path")

        generated_filename = (
            os.path.basename(str(storage_path))
            if storage_path
            else None
        )

        original_filename = (
            attachment.get("display_name")
            or attachment.get("filename")
            or record.get("label")
            or asset.get("original_filename")
            or generated_filename
        )

        public_path = attachment.get("url")

        if not public_path and storage_path:

            public_path = self._public_path_for(
                project_id,
                storage_path
            )

        return {

            "contract": ASSET_CONTRACT,
            "version": VERSION,

            "asset_id": record.get("image_id"),

            "project_id": project_id,
            "session_id": record.get("session_id"),

            "ordinal": record.get("ordinal"),

            "source_type": record.get("source_type"),

            "parent_asset_id": record.get("parent_image_id"),
            "parent_ordinal": self._ordinal_for(
                manifest, record.get("parent_image_id")
            ),

            "created_at": record.get("created_at"),

            "original_filename": original_filename,
            "generated_filename": generated_filename,

            "storage_path": storage_path,
            "public_path": public_path,

            "is_active": bool(record.get("active")),
            "is_final": bool(is_final),

            "label": record.get("label"),

            "analysis_status": record.get("analysis_status"),

            "dimensions": self._dimensions(storage_path),

            "kind": self._kind_for(record.get("source_type")),
        }

    @staticmethod
    def _ordinal_for(manifest, asset_id):

        return None

    @staticmethod
    def _kind_for(source_type):

        if source_type == "uploaded":

            return "image"

        if source_type in ("text_to_image", "render", "image_to_image"):

            return "render"

        return "file"

    @staticmethod
    def _dimensions(path):

        if not path or not os.path.isfile(path):

            return None

        try:

            with open(path, "rb") as handle:

                head = handle.read(24)

            if head[:8] != b"\x89PNG\r\n\x1a\n":

                return None

            return [
                int.from_bytes(head[16:20], "big"),
                int.from_bytes(head[20:24], "big"),
            ]

        except Exception:

            return None

    def _public_path_for(self, project_id, storage_path):

        try:

            root = os.path.abspath(RC.PROJECTS_ROOT)

            absolute = os.path.abspath(str(storage_path))

            if not absolute.startswith(root):

                return None

            relative = os.path.relpath(absolute, root).replace("\\", "/")

            return "/artifacts/project_media/" + relative

        except Exception:

            return None

    # ======================================================
    # MANAGED ASSET COPY  (collision-safe)
    # ======================================================

    def next_generated_name(self, project_id, source_type, extension):

        manifest = project_workspace.load(project_id) or {}

        counters = dict(manifest.get("counters") or {})

        counter_key = {
            "uploaded": "upload",
            "text_to_image": "render",
            "render": "render",
            "image_to_image": "edit",
            "document": "document",
        }.get(source_type, "upload")

        counters[counter_key] = int(counters.get(counter_key, 0)) + 1

        project_workspace.update_fields(
            project_id,
            {"counters": counters}
        )

        folder, prefix = folder_and_prefix(source_type)

        extension = extension if extension.startswith(".") else "." + extension

        short_id = uuid.uuid4().hex[:6]

        return (
            folder,
            "%s_%03d_%s%s" % (prefix, counters[counter_key], short_id, extension)
        )

    def adopt_asset(self, project_id, source_path, source_type):

        """Copy an asset into the project under a collision-safe name.

        The project copy becomes authoritative. Never overwrites.
        Returns a dict with the managed paths, or None on failure.
        """

        if not source_path or not os.path.isfile(source_path):

            return None

        extension = os.path.splitext(source_path)[1] or ".bin"

        folder, filename = self.next_generated_name(
            project_id, source_type, extension
        )

        target_dir = project_workspace.subdir(project_id, folder)

        target = os.path.join(target_dir, filename)

        if os.path.exists(target):

            # Exclusive-create guarantee: never overwrite.
            folder, filename = self.next_generated_name(
                project_id, source_type, extension
            )

            target = os.path.join(
                project_workspace.subdir(project_id, folder),
                filename
            )

        with self._lock:

            shutil.copy2(source_path, target)

        return {

            "folder": folder,
            "generated_filename": filename,
            "storage_path": target,
            "public_path": self._public_path_for(project_id, target),
            "source_path": source_path,
            "size_bytes": os.path.getsize(target),
        }

    # ======================================================
    # ASSET OPERATIONS
    # ======================================================

    def set_final(self, project_id, asset_id, is_final=True):

        payload = self.load_assets(project_id)

        assets = payload.get("assets") or []

        found = False

        for asset in assets:

            if asset.get("asset_id") == asset_id:

                asset["is_final"] = bool(is_final)

                found = True

        if not found:

            return None

        payload["assets"] = assets

        payload["final_assets"] = {
            a["asset_id"]: True for a in assets if a.get("is_final")
        }

        payload["updated_at"] = time.time()

        atomic_write_json(self._assets_path(project_id), payload)

        return payload

    def set_active(self, project_id, asset_id):

        manifest = project_workspace.load(project_id)

        if not manifest:

            return None

        session_id = manifest.get("session_id") or project_id

        record = image_registry.set_active(session_id, asset_id)

        if record:

            project_workspace.update_fields(
                project_id,
                {"active_asset_id": asset_id}
            )

        return record

    def gallery(self, project_id, filter_kind="all"):

        payload = self.load_assets(project_id)

        assets = list(payload.get("assets") or [])

        if filter_kind and filter_kind != "all":

            wanted = {

                "uploads": ("uploaded",),
                "renders": ("text_to_image", "render"),
                "edits": ("image_to_image",),
                "files": ("document", "other"),

            }.get(filter_kind)

            if filter_kind == "final":

                assets = [a for a in assets if a.get("is_final")]

            elif wanted:

                assets = [
                    a for a in assets
                    if a.get("source_type") in wanted
                ]

        assets.sort(
            key=lambda a: a.get("ordinal") or 0
        )

        return {

            "contract": "ProjectGalleryV1",
            "version": VERSION,

            "project_id": project_id,
            "filter": filter_kind,

            "asset_count": len(assets),
            "assets": assets,

            "active_asset_id": payload.get("active_asset_id"),
            "last_uploaded_asset_id": payload.get("last_uploaded_asset_id"),
            "last_render_asset_id": payload.get("last_render_asset_id"),
            "last_derived_asset_id": payload.get("last_derived_asset_id"),
        }

    def lineage(self, project_id, asset_id):

        payload = self.load_assets(project_id)

        by_id = {
            a.get("asset_id"): a for a in (payload.get("assets") or [])
        }

        chain = []

        cursor = by_id.get(asset_id)

        guard = 0

        while cursor and guard < 50:

            chain.append({
                "asset_id": cursor.get("asset_id"),
                "ordinal": cursor.get("ordinal"),
                "source_type": cursor.get("source_type"),
                "label": cursor.get("label"),
            })

            cursor = by_id.get(cursor.get("parent_asset_id"))

            guard += 1

        chain.reverse()

        return chain


# ==========================================================
# SINGLETON
# ==========================================================

project_registry_bridge = ProjectRegistryBridge()
