"""Renderer-independent architectural drawing package."""

from .architectural_scene_v1 import ArchitecturalDrawingScene, Primitive
from .architectural_realization_v1 import ArchitecturalPlanRealizer
from .architectural_symbol_library_v1 import SYMBOL_LIBRARY, SPACE_FURNITURE_BUNDLES
from .furniture_placement_validator_v1 import FurniturePlacementValidator
from .interior_fixture_finish_clearance_v1 import (INTERIOR_FIXTURE_KNOWLEDGE, WET_SPACE_FINISH_CONTRACT,
    CLEARANCE_RULES, InteriorFixtureFinishValidator, FurnitureClearanceValidator, add_review_graphics, contracts)
from .semantic_opening_typology_v1 import (DOOR_TYPOLOGY_LIBRARY, WINDOW_TYPOLOGY_LIBRARY,
    SemanticOpeningEngine, TOPIC4_GLAZING_DEFAULT, TOPIC4_GLAZING_DEEP_ROOM)
from .svg_architectural_renderer_v1 import SvgArchitecturalRenderer
from .plan_model_to_scene_adapter_v1 import PlanModelToSceneAdapterV1
try:
    from .pdf_architectural_renderer_v1 import PdfArchitecturalRenderer
except ModuleNotFoundError:  # Geometry/test environments need not install the optional PDF backend.
    PdfArchitecturalRenderer = None

__all__ = [
    "ArchitecturalDrawingScene", "Primitive", "ArchitecturalPlanRealizer",
    "PlanModelToSceneAdapterV1",
    "SvgArchitecturalRenderer", "PdfArchitecturalRenderer",
    "INTERIOR_FIXTURE_KNOWLEDGE", "WET_SPACE_FINISH_CONTRACT", "CLEARANCE_RULES",
    "InteriorFixtureFinishValidator", "FurnitureClearanceValidator", "add_review_graphics", "contracts",
    "DOOR_TYPOLOGY_LIBRARY", "WINDOW_TYPOLOGY_LIBRARY", "SemanticOpeningEngine",
    "TOPIC4_GLAZING_DEFAULT", "TOPIC4_GLAZING_DEEP_ROOM",
]
