"""Safe chat attachment registration and public-path resolution."""

from __future__ import annotations

import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

from werkzeug.utils import secure_filename


class ChatAttachmentServiceV1:
    VERSION = "1.1"
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

    def __init__(self, roots: Optional[Dict[str, os.PathLike]] = None) -> None:
        project_root = Path(__file__).resolve().parents[2]

        # PROJECT_WORKSPACE_UI_06 — every storage root now comes from
        # the single runtime config source. No hardcoded paths.
        from config import runtime_config as _RC

        configured = roots or {
            "user_media": project_root / "uploads" / "chat_media",
            "comfy_output": Path(_RC.COMFYUI_OUTPUT_DIR),
            "architectos_output": project_root / "outputs",
            "architectos_export": project_root / "exports",
            # Project-scoped managed assets. The public URL is
            # /artifacts/project_media/<project_id>/<relative_path>.
            "project_media": Path(_RC.PROJECTS_ROOT),
            # VISUAL_REFERENCE_UX_V2 — the two read-only reference
            # collections. Registered here so previews go through the SAME
            # validated resolver as every other artifact (`_inside()` +
            # `..` rejection + is_file()) instead of a new file route.
            # Nothing is written to these roots; the originals are never
            # moved, renamed or modified.
            "reference_library": Path(_RC.REFERENCE_LIBRARY_ROOT),
            "reference_classical": Path(_RC.REFERENCE_CLASSICAL_ROOT),
        }
        self.roots = {name: Path(path).resolve() for name, path in configured.items()}

        # CHAT_ATTACHMENT_ROOTS_OPTIONAL_01 — `roots` is an OPTIONAL caller
        # supplied map, and every accessor in this class already treats an
        # absent root as "not available" (`self.roots.get(root_key)`). Only
        # these two `mkdir` calls assumed the keys were present, so a caller
        # passing a partial map crashed at construction with KeyError instead
        # of getting the graceful behaviour the rest of the class provides.
        for _root_key in ("user_media", "project_media"):
            _root = self.roots.get(_root_key)
            if _root is not None:
                _root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _inside(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _kind_for(mime_type: str, requested: Optional[str] = None) -> str:
        if requested:
            return requested
        if mime_type.startswith("image/"):
            return "image"
        if mime_type.startswith("video/"):
            return "video"
        if mime_type == "application/pdf" or mime_type.startswith("text/"):
            return "document"
        return "file"

    def _public_url(self, root_key: str, relative_path: Path) -> str:
        encoded = quote(relative_path.as_posix(), safe="/")
        return f"/artifacts/{root_key}/{encoded}"

    def attachment_for_path(
        self,
        path: os.PathLike,
        *,
        root_key: str,
        source: str,
        kind: Optional[str] = None,
        display_name: Optional[str] = None,
        status: str = "ready",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        root = self.roots.get(root_key)
        if root is None:
            return None
        resolved = Path(path).resolve()
        if not self._inside(resolved, root) or not resolved.is_file():
            return None
        relative = resolved.relative_to(root)
        mime_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        attachment_kind = self._kind_for(mime_type, kind)
        public_url = self._public_url(root_key, relative)
        return {
            "id": "attachment_" + uuid.uuid4().hex[:12],
            "kind": attachment_kind,
            "mime_type": mime_type,
            "filename": resolved.name,
            "display_name": display_name or resolved.name,
            "url": public_url,
            "thumbnail_url": public_url if attachment_kind in ("image", "render") else None,
            "size_bytes": resolved.stat().st_size,
            "source": source,
            "status": status,
            "metadata": metadata or {},
            "storage_root": root_key,
            "relative_path": relative.as_posix(),
        }

    def save_upload(
        self,
        file_storage: Any,
        *,
        source: str = "user_upload",
        kind: Optional[str] = None,
    ) -> Dict[str, Any]:
        original = secure_filename(getattr(file_storage, "filename", "") or "upload")
        extension = Path(original).suffix.lower()
        if kind == "image" and extension not in self.IMAGE_EXTENSIONS:
            return {"status": "error", "error": "unsupported_image_format"}
        stored_name = f"{uuid.uuid4().hex[:12]}_{original}"
        target = (self.roots["user_media"] / stored_name).resolve()
        if not self._inside(target, self.roots["user_media"]):
            return {"status": "error", "error": "invalid_upload_path"}
        file_storage.save(str(target))
        stream = getattr(file_storage, "stream", None)
        if stream is not None and hasattr(stream, "seek"):
            stream.seek(0)
        attachment = self.attachment_for_path(
            target,
            root_key="user_media",
            source=source,
            kind=kind,
            display_name=original,
        )
        if attachment is None:
            return {"status": "error", "error": "attachment_registration_failed"}
        return {"status": "ready", "path": str(target), "attachment": attachment}

    def from_comfy_output(self, image: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(image, dict):
            return None
        filename = secure_filename(str(image.get("filename") or ""))
        if not filename:
            return None
        subfolder = str(image.get("subfolder") or "").replace("\\", "/").strip("/")
        relative = Path(subfolder) / filename if subfolder else Path(filename)
        return self.attachment_for_path(
            self.roots["comfy_output"] / relative,
            root_key="comfy_output",
            source="comfyui_output",
            kind="render",
            metadata={
                "comfy_type": image.get("type", "output"),
                "subfolder": subfolder,
            },
        )

    def resolve_public_path(self, root_key: str, relative_path: str) -> Optional[Path]:
        root = self.roots.get(root_key)
        if root is None or not relative_path:
            return None
        candidate_text = str(relative_path).replace("\\", "/")
        candidate_path = Path(candidate_text)
        if candidate_path.is_absolute() or ".." in candidate_path.parts:
            return None
        candidate = (root / candidate_path).resolve()
        if not self._inside(candidate, root) or not candidate.is_file():
            return None
        return candidate

    @staticmethod
    def public_attachment(attachment: Dict[str, Any]) -> Dict[str, Any]:
        allowed = (
            "id",
            "kind",
            "mime_type",
            "filename",
            "display_name",
            "url",
            "thumbnail_url",
            "size_bytes",
            "source",
            "status",
            "metadata",
        )
        return {key: attachment.get(key) for key in allowed if attachment.get(key) is not None}


chat_attachment_service = ChatAttachmentServiceV1()

