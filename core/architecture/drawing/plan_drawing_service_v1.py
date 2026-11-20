"""PlanDrawingServiceV1 — render a design model's plan model to a viewable artefact.

This service is the single call site that turns an
:class:`~core.architecture.model.architectural_plan_model.ArchitecturalPlanModel`
into a rendered, human-readable plan file on disk.

It is deliberately thin. All translation lives in
:class:`~core.architecture.drawing.plan_model_to_scene_adapter_v1.PlanModelToSceneAdapterV1`
and all drawing lives in the existing realizer and renderers. This module only:

1. invokes the adapter,
2. picks a renderer,
3. writes the artefact,
4. returns a small, serialisable descriptor for the chat layer.

Nothing here invents geometry, coordinates, dimensions, or labels. When the
adapter cannot resolve a room, the service records that fact and still returns a
descriptor, so the caller can report a partial plan honestly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .plan_model_to_scene_adapter_v1 import PlanModelToSceneAdapterV1
from .svg_architectural_renderer_v1 import SvgArchitecturalRenderer

OUTPUT_TYPE = "plan_drawing"
OUTPUT_VERSION = "plan_drawing_service_v1"

#: Artefact directory, relative to the repository root.
OUTPUT_SUBDIRECTORY = ("outputs", "plan_drawings")

SVG = "svg"
PDF = "pdf"


def _repo_root() -> Path:
    """Repository root, derived from this file's location."""

    return Path(__file__).resolve().parents[3]


class PlanDrawingServiceV1:
    """Produce a rendered plan artefact for a design model."""

    VERSION = OUTPUT_VERSION

    def __init__(
        self,
        adapter: PlanModelToSceneAdapterV1 | None = None,
        output_root: Path | None = None,
    ):

        self.adapter = adapter or PlanModelToSceneAdapterV1()

        self.output_root = (
            Path(output_root)
            if output_root is not None
            else _repo_root().joinpath(*OUTPUT_SUBDIRECTORY)
        )

        print(f"🖼️ PLAN DRAWING SERVICE {self.VERSION} ONLINE")

    # ==================================================
    # PUBLIC API
    # ==================================================

    def render(
        self,
        design_model: Any,
        candidate_id: str | None = None,
        formats: tuple[str, ...] = (SVG,),
    ) -> dict[str, Any]:
        """Render the design model's plan as a viewable artefact.

        Returns a descriptor. ``status`` is one of:

        - ``"ready"``   — at least one artefact was written.
        - ``"empty"``   — the adapter resolved no rooms; nothing was drawn.
        - ``"unavailable"`` — the design model carried no plan model.
        """

        plan_model = getattr(design_model, "plan_model", None)

        if not isinstance(plan_model, dict) or not plan_model:
            return self._unavailable("design_model_has_no_plan_model")

        layout = getattr(design_model, "layout", None)
        spatial_contract = getattr(design_model, "spatial_contract", None)
        architectural_geometry = getattr(
            design_model, "architectural_geometry", None
        )

        try:
            scene = self.adapter.realize(
                plan_model,
                layout,
                spatial_contract,
                architectural_geometry,
                candidate_id=candidate_id,
            )
        except Exception as error:  # fail closed; never fabricate a plan
            return self._unavailable(f"adapter_failed: {error}")

        summary = scene.metadata.get("plan_summary", {}) or {}

        if not (scene.metadata.get("room_resolution", {}) or {}).get("drawn_rooms"):
            return {
                "status": "empty",
                "type": OUTPUT_TYPE,
                "version": OUTPUT_VERSION,
                "reason": "no_resolved_room_footprints",
                "scene": scene.to_dict(),
                "plan_summary": summary,
                "pending_rooms": scene.metadata.get("pending_rooms", []),
            }

        artefacts = self._write(scene, candidate_id or scene.candidate_id, formats)

        if not artefacts:
            return self._unavailable("no_renderer_produced_an_artefact")

        return {
            "status": "ready",
            "type": OUTPUT_TYPE,
            "version": OUTPUT_VERSION,
            "candidate_id": scene.candidate_id,
            "format": artefacts[0]["format"],
            "path": artefacts[0]["path"],
            "artefacts": artefacts,
            "plan_summary": summary,
            "room_resolution": scene.metadata.get("room_resolution", {}),
            "pending_rooms": scene.metadata.get("pending_rooms", []),
            "withheld_openings": scene.metadata.get("withheld_openings", {}),
            "scene": scene.to_dict(),
        }

    # ==================================================
    # WRITING
    # ==================================================

    def _write(
        self,
        scene: Any,
        candidate_id: str,
        formats: tuple[str, ...],
    ) -> list[dict[str, Any]]:

        directory = self.output_root / self._stamp()

        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            return []

        written: list[dict[str, Any]] = []

        for fmt in formats:

            path = directory / f"{self._filename(candidate_id, fmt)}"

            try:
                if fmt == SVG:
                    SvgArchitecturalRenderer().render(scene, path)
                elif fmt == PDF:
                    if not self._render_pdf(scene, path):
                        continue
                else:
                    continue
            except Exception:
                continue

            if path.exists():
                written.append(
                    {
                        "format": fmt,
                        "path": str(path),
                        "filename": path.name,
                        "bytes": path.stat().st_size,
                    }
                )

        return written

    def _render_pdf(self, scene: Any, path: Path) -> bool:
        """Render PDF when the optional backend is installed. Never a hard dependency."""

        try:
            from .pdf_architectural_renderer_v1 import PdfArchitecturalRenderer
        except ModuleNotFoundError:
            return False

        if PdfArchitecturalRenderer is None:
            return False

        PdfArchitecturalRenderer().render(scene, path)

        return True

    def _stamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S%f")

    def _filename(self, candidate_id: str, fmt: str) -> str:
        safe = "".join(
            ch if (ch.isalnum() or ch in "-_") else "_" for ch in str(candidate_id)
        )
        return f"PLAN_{safe}.{fmt}"

    # ==================================================
    # FAIL-CLOSED HELPERS
    # ==================================================

    def _unavailable(self, reason: str) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "type": OUTPUT_TYPE,
            "version": OUTPUT_VERSION,
            "reason": reason,
        }
