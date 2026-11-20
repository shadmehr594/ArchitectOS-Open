# ==========================================================
# ArchitectOS Project Session v1
#
# PROJECT_WORKSPACE_UI_06 — 06A AUTOSAVE / CRASH RECOVERY
#
# Owns the lifecycle of "the project the user currently has open"
# and makes persistence happen automatically after every meaningful
# state change.
#
# Autosave triggers (called explicitly by the API layer so the set is
# auditable and testable):
#   user_message / assistant_response / upload / render_complete /
#   img2img_complete / asset_activated / mark_final / rename /
#   mode_change / profile_change / project_metadata
#
# Truthful save state
#   `saved` / `saving` / `failed` + `last_saved_at` + `last_error`.
#   The UI must never show "Saved" before the write actually
#   succeeded, so the state is only set to `saved` AFTER the atomic
#   write returns.
# ==========================================================


from __future__ import annotations


import os
import threading
import time


from config import runtime_config as RC

from core.project.project_workspace_v1 import project_workspace

from core.project.project_registry_bridge_v1 import (
    project_registry_bridge,
)

from core.project.conversation_store_v1 import conversation_store

from core.chat.chat_attachment import chat_attachment_service

from core.chat.session_registry_v1 import session_registry

from core.vision.image_registry_v1 import image_registry


CONTRACT = "ProjectSessionV1"
VERSION = "1.0"


# ==========================================================
# IMAGE_TURN_TRANSPORT_RECOVERY_01
#
# A vision turn runs for tens of seconds. If the browser loses the
# response on the way back (observed live: the Core answers 200, stores
# the turn, and the browser still reports a transport error), the
# workspace can RECOVER the reply the Core already stored instead of
# showing a bare network error and silently dropping the turn.
#
# Read-only helper. The key it feeds is additive.
# ==========================================================

def last_assistant_message(chat):

    """The newest stored assistant reply, or None."""

    messages = (chat or {}).get("messages") or []

    for message in reversed(messages):

        if (message or {}).get("role") != "assistant":

            continue

        text = (message or {}).get("text")

        if text:

            return str(text)

    return None


SAVE_SAVED = "saved"
SAVE_SAVING = "saving"
SAVE_FAILED = "failed"


AUTOSAVE_REASONS = (
    "user_message",
    "assistant_response",
    "upload",
    "render_complete",
    "img2img_complete",
    "asset_activated",
    "mark_final",
    "rename",
    "mode_change",
    "profile_change",
    "project_metadata",
    "project_opened",
    "manual",
)


class ProjectSession:

    VERSION = VERSION

    def __init__(self):

        self._lock = threading.RLock()

        self._project_id = None

        self._save_state = {}

        print("🗂️ PROJECT SESSION v1.0 ONLINE (autosave)")

    # ======================================================
    # CURRENT PROJECT
    # ======================================================

    def current_project_id(self):

        return self._project_id

    def is_open(self):

        return bool(self._project_id)

    # ======================================================
    # SAVE STATE
    # ======================================================

    def _state_for(self, project_id):

        return self._save_state.setdefault(project_id, {

            "contract": "ProjectSaveStateV1",
            "version": VERSION,

            "project_id": project_id,

            "state": SAVE_SAVED,
            "last_saved_at": None,
            "last_reason": None,
            "last_error": None,
            "save_count": 0,
        })

    def save_state(self, project_id=None):

        project_id = project_id or self._project_id

        if not project_id:

            return {
                "contract": "ProjectSaveStateV1",
                "version": VERSION,
                "project_id": None,
                "state": "no_project",
                "last_saved_at": None,
                "last_error": None,
                "save_count": 0,
            }

        return dict(self._state_for(project_id))

    # ======================================================
    # OPEN / CLOSE
    # ======================================================

    def open(self, project_id):

        manifest = project_workspace.load(project_id)

        if not manifest:

            return None

        with self._lock:

            self._project_id = project_id

            # 1. bind the registry (hydrates ordinals / active / lineage)
            project_registry_bridge.bind(project_id)

            session_id = manifest.get("session_id") or project_id

            # 2. hydrate the conversation for this project's session
            bundle = session_registry.resolve(session_id)

            conversation_state = bundle.get("conversation_state")

            restored = conversation_store.hydrate(
                project_id,
                conversation_state,
                session_id=session_id,
            )

            # 3. migrate any asset that still lives outside the project
            self.adopt_pending_assets(project_id)

            # 4. persist + mark opened
            project_workspace.touch_opened(project_id)

            self.autosave(project_id, reason="project_opened")

            manifest = project_workspace.load(project_id)

        print(
            "📂 PROJECT OPENED:",
            project_id,
            "| messages restored:",
            restored
        )

        return manifest

    def close(self):

        with self._lock:

            project_id = self._project_id

            if project_id:

                try:

                    self.autosave(project_id, reason="project_metadata")

                except Exception as error:

                    print("⚠️ CLOSE AUTOSAVE ERROR:", error)

            self._project_id = None

            project_registry_bridge.unbind()

        return {"status": "closed", "project_id": project_id}

    # ======================================================
    # ASSET MIGRATION INTO THE PROJECT
    # ======================================================

    def adopt_pending_assets(self, project_id):

        """Copy every unmanaged asset into the project folder.

        The managed copy becomes authoritative, so after a restart the
        project is self-contained and cannot collide with another
        project's files.
        """

        manifest = project_workspace.load(project_id)

        if not manifest:

            return 0

        session_id = manifest.get("session_id") or project_id

        project_dir = os.path.abspath(
            project_workspace.project_dir(project_id)
        )

        adopted = 0

        for record in image_registry.list(session_id):

            path = record.get("path")

            if not path or not os.path.isfile(path):

                continue

            if os.path.abspath(str(path)).startswith(project_dir):

                continue

            managed = project_registry_bridge.adopt_asset(
                project_id,
                path,
                record.get("source_type") or "other",
            )

            if not managed:

                continue

            attachment = dict(record.get("attachment") or {})

            if managed.get("public_path"):

                attachment["url"] = managed["public_path"]

                attachment["thumbnail_url"] = managed["public_path"]

            attachment["storage_root"] = "project_media"

            image_registry.update_record(
                session_id,
                record.get("image_id"),
                {
                    "path": managed["storage_path"],
                    "attachment": attachment,
                    "managed": True,
                    "managed_folder": managed["folder"],
                    "original_source_path": path,
                    "generated_filename": managed["generated_filename"],
                },
            )

            adopted += 1

        return adopted

    # ======================================================
    # AUTOSAVE
    # ======================================================

    def autosave(self, project_id=None, reason="manual"):

        project_id = project_id or self._project_id

        if not project_id:

            return {
                "status": "skipped",
                "reason": "no_open_project",
            }

        state = self._state_for(project_id)

        state["state"] = SAVE_SAVING

        state["last_reason"] = reason

        try:

            manifest = project_workspace.load(project_id)

            if not manifest:

                raise FileNotFoundError(
                    "project manifest missing: " + str(project_id)
                )

            session_id = manifest.get("session_id") or project_id

            # 0. make sure every asset has a project-scoped managed copy
            self.adopt_pending_assets(project_id)

            # 1. managed assets + registry bucket
            assets_payload = project_registry_bridge.save(project_id)

            # 2. conversation history
            bundle = session_registry.resolve(session_id)

            conversation_state = bundle.get("conversation_state")

            chat_payload = conversation_store.save(
                project_id,
                getattr(conversation_state, "state", {}) or {},
                session_id=session_id,
            )

            # 3. project metadata
            project_workspace.update_fields(project_id, {

                "updated_at": time.time(),

                "active_asset_id": (
                    (assets_payload or {}).get("active_asset_id")
                ),

                "last_uploaded_asset_id": (
                    (assets_payload or {}).get("last_uploaded_asset_id")
                ),

                "last_render_asset_id": (
                    (assets_payload or {}).get("last_render_asset_id")
                ),

                "last_derived_asset_id": (
                    (assets_payload or {}).get("last_derived_asset_id")
                ),

                "asset_count": (assets_payload or {}).get("asset_count"),

                "message_count": chat_payload.get("message_count"),

                "last_save_reason": reason,
            })

            # only NOW may the UI say "Saved"
            state["state"] = SAVE_SAVED

            state["last_saved_at"] = time.time()

            state["last_error"] = None

            state["save_count"] = int(state.get("save_count") or 0) + 1

        except Exception as error:

            state["state"] = SAVE_FAILED

            state["last_error"] = type(error).__name__ + ": " + str(error)

            print("⚠️ AUTOSAVE FAILED:", state["last_error"])

        return dict(state)

    # ======================================================
    # RECOVERY SUMMARY
    # ======================================================

    def recovery_summary(self, project_id):

        manifest = project_workspace.load(project_id)

        if not manifest:

            return None

        gallery = project_registry_bridge.gallery(project_id)

        chat = conversation_store.load(project_id)

        return {

            "contract": "ProjectRecoverySummaryV1",
            "version": VERSION,

            "project_id": project_id,
            "project_name": manifest.get("project_name"),
            "status": manifest.get("status"),

            "storage_path": project_workspace.project_dir(project_id),

            "message_count": chat.get("message_count"),

            # IMAGE_TURN_TRANSPORT_RECOVERY_01 — additive. Lets the
            # workspace recover a reply the Core stored even when the
            # browser never received the HTTP response.
            "last_assistant_message": last_assistant_message(chat),

            "asset_count": gallery.get("asset_count"),

            "ordinals": [
                a.get("ordinal") for a in (gallery.get("assets") or [])
            ],

            "active_asset_id": gallery.get("active_asset_id"),
            "last_uploaded_asset_id": gallery.get("last_uploaded_asset_id"),
            "last_render_asset_id": gallery.get("last_render_asset_id"),
            "last_derived_asset_id": gallery.get("last_derived_asset_id"),

            "lineage": [
                {
                    "asset_id": a.get("asset_id"),
                    "ordinal": a.get("ordinal"),
                    "parent_asset_id": a.get("parent_asset_id"),
                }
                for a in (gallery.get("assets") or [])
            ],

            "save_state": self.save_state(project_id),
        }

    # ======================================================
    # TRANSCRIPT — READ-ONLY PROJECTION
    # ======================================================

    def transcript(self, project_id):

        """The persisted conversation of ONE project, read-only.

        PROJECT_HISTORY_RESTORATION_V1 — `recovery_summary()` reports only
        `message_count`, so the workspace could show "Restored 6 messages"
        without being able to render a single one. This exposes the stored
        turns themselves.

        It only READS `<project>/conversations/chat.json`. It never writes,
        migrates, repairs or re-creates anything, and it never merges data
        from another project: the path is derived from `project_id` alone,
        so the project boundary is the storage boundary.
        """

        chat = conversation_store.load(project_id)

        messages = chat.get("messages")

        if not isinstance(messages, list):

            return []

        transcript = []

        for index, entry in enumerate(messages):

            if not isinstance(entry, dict):

                continue

            role = entry.get("role")

            # Only the two conversational roles are ever rendered. A record
            # with an unknown role is skipped, never guessed at.
            if role not in ("user", "assistant"):

                continue

            transcript.append({

                "role": role,

                "text": str(entry.get("text") or ""),

                # SENT_MESSAGE_EDIT_V1 — a stable reference for THIS stored
                # message. `seq:<n>` for a sequenced turn, `legacy:<hash>`
                # for a message written before turn_seq existed. Never the
                # array index: the 100-message cap would shift it.
                "message_ref": conversation_store.message_ref(messages, index),

                # SENT_MESSAGE_EDIT_V1 — set when a later revision
                # invalidated this branch. The message is still shown (it
                # is never deleted) but it is NOT active context.
                "superseded_by": entry.get("superseded_by"),

                # CHAT-02C.2 — attachments are passed through the EXISTING
                # public allowlist (`public_attachment`), so the client only
                # ever receives display fields. Internal resolution data
                # (`storage_root`, `relative_path`) and raw payloads
                # (`audio_bytes`) never leave the server, and the client is
                # never trusted to resolve a path itself: it gets a URL that
                # `/artifacts/<root_key>/<path>` re-validates on every fetch.
                "attachments": [
                    chat_attachment_service.public_attachment(item)
                    for item in (entry.get("attachments") or [])
                    if isinstance(item, dict)
                ],

                "at": entry.get("at"),
            })

        return transcript


# ==========================================================
# SINGLETON
# ==========================================================

project_session = ProjectSession()
