"""
ArchitectOS v27.0 — Parametric Multi-Floor, Villa, Duplex, Krocki CAD Reader & 3D Render Engine
(`core/planning/multifloor_v1/engine/__init__.py`)
"""
from .domain import (
    AuditReportV3,
    BackyardLightwell,
    BuildingProjectResultV3,
    BuildingTypology,
    ColumnElement,
    DimensionChain,
    DoorElement,
    ElevatorDetail,
    FloorPlanDesignV3,
    FurnitureElement,
    OccupancyType,
    ParametricSiteSpec,
    RectMM,
    RoomSpace,
    StairFlightDetail,
    ValidationStatus,
    WindowElement,
)
from .nl_design_parser import (
    apply_incremental_plan_edit,
    build_render_state_from_plan_or_prev_render,
    is_architectural_design_prompt,
    is_new_plan_creation_prompt,
    is_plan_modification_prompt,
    normalize_persian_text,
    parse_architectural_prompt,
)
from .teacher_memory import SafeTeacherMemory
from .furniture_layout_solver import SmartArchitecturalFurnitureSolver
from .conversational_editor import ConversationalPlanEditor
from .perspective_renderer import Architectural3DRenderer
from .comfyui_bridge import ComfyUIRenderBridge
from .architectural_synthesizer import ParametricArchitecturalSynthesizer
from .exporter import (
    export_project_to_dxf,
    export_project_to_json,
    export_project_to_svg,
    render_project_to_png_pillow,
    render_svg_to_png_persian_bidi,
)
from .krocki_cad_reader_v27 import (
    convert_dwg_to_dxf_fast,
    export_krocki_preview_svg,
    parse_krocki_dxf_or_dwg,
)

# Backward-compatibility alias for callers importing ArchitecturalPlanSynthesizer
ArchitecturalPlanSynthesizer = ParametricArchitecturalSynthesizer

__all__ = [
    "AuditReportV3",
    "BackyardLightwell",
    "BuildingProjectResultV3",
    "BuildingTypology",
    "ColumnElement",
    "DimensionChain",
    "DoorElement",
    "ElevatorDetail",
    "FloorPlanDesignV3",
    "FurnitureElement",
    "OccupancyType",
    "ParametricSiteSpec",
    "RectMM",
    "RoomSpace",
    "StairFlightDetail",
    "ValidationStatus",
    "WindowElement",
    "normalize_persian_text",
    "is_architectural_design_prompt",
    "is_new_plan_creation_prompt",
    "is_plan_modification_prompt",
    "parse_architectural_prompt",
    "apply_incremental_plan_edit",
    "build_render_state_from_plan_or_prev_render",
    "SafeTeacherMemory",
    "SmartArchitecturalFurnitureSolver",
    "ConversationalPlanEditor",
    "Architectural3DRenderer",
    "ComfyUIRenderBridge",
    "ParametricArchitecturalSynthesizer",
    "ArchitecturalPlanSynthesizer",
    "export_project_to_svg",
    "export_project_to_dxf",
    "export_project_to_json",
    "render_project_to_png_pillow",
    "render_svg_to_png_persian_bidi",
    "convert_dwg_to_dxf_fast",
    "parse_krocki_dxf_or_dwg",
    "export_krocki_preview_svg",
]
