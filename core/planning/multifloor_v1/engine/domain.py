"""
ArchitectOS Parametric Architectural Space Planning & CAD Domain Model (v29.0 — Irregular Krocki & Boundary Topology Edition).
Incorporates all cumulative architectural, structural, parking, circulation, MEP, Krocki polygon, and 4-side street/neighbor rules.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ValidationStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"


class BuildingTypology(str, Enum):
    VILLA_1FLOOR = "VILLA_1FLOOR"
    DUPLEX_2FLOOR = "DUPLEX_2FLOOR"
    MULTIFLOOR_RESIDENTIAL = "MULTIFLOOR_RESIDENTIAL"
    MIXED_USE_MULTIFLOOR = "MIXED_USE_MULTIFLOOR"


class OccupancyType(str, Enum):
    VILLA_GROUND = "VILLA_GROUND"
    PILOTIS_PARKING_OPEN = "PILOTIS_PARKING_OPEN"
    PARKING_BASEMENT = "PARKING_BASEMENT"
    MIXED_GROUND = "MIXED_GROUND"
    RESIDENTIAL_TYPICAL = "RESIDENTIAL_TYPICAL"
    DUPLEX_LOWER = "DUPLEX_LOWER"
    DUPLEX_UPPER = "DUPLEX_UPPER"
    PENTHOUSE_STEPPED = "PENTHOUSE_STEPPED"
    ROOF_KHARPOSHTEH = "ROOF_KHARPOSHTEH"


@dataclass(frozen=True)
class RectMM:
    x_min: int
    y_min: int
    x_max: int
    y_max: int

    @property
    def width(self) -> int:
        return max(0, self.x_max - self.x_min)

    @property
    def height(self) -> int:
        return max(0, self.y_max - self.y_min)

    @property
    def area_m2(self) -> float:
        return round((self.width * self.height) / 1_000_000.0, 2)

    @property
    def aspect_ratio(self) -> float:
        mn = min(self.width, self.height)
        return round(max(self.width, self.height) / float(mn), 2) if mn > 0 else 1.0

    @property
    def center(self) -> Tuple[int, int]:
        return ((self.x_min + self.x_max) // 2, (self.y_min + self.y_max) // 2)

    def intersects_interior(self, other: "RectMM", tol_mm: int = 5) -> bool:
        dx = min(self.x_max, other.x_max) - max(self.x_min, other.x_min)
        dy = min(self.y_max, other.y_max) - max(self.y_min, other.y_min)
        return dx > tol_mm and dy > tol_mm


@dataclass
class DoorElement:
    door_id: str
    label_fa: str
    host_room_id: str
    target_room_id: str
    hinge_mm: Tuple[int, int]
    width_mm: int
    wall_orientation: str   # "H" or "V"
    swing_dir: str          # "N", "S", "E", "W"
    leaf_dir: str = "+"     # "+" or "-"
    is_main_entry: bool = False
    is_backyard_entry: bool = False
    is_sliding: bool = False


@dataclass
class WindowElement:
    window_id: str
    host_room_id: str
    target_zone: str
    x0_mm: int
    y0_mm: int
    x1_mm: int
    y1_mm: int
    wall_thickness_mm: int = 200
    orientation: str = "H"


@dataclass
class StairFlightDetail:
    core_rect_mm: RectMM
    structural_box_rect_mm: RectMM
    entrance_landing_rect_mm: RectMM
    intermediate_landing_rect_mm: RectMM
    flight1_rect_mm: RectMM
    flight2_rect_mm: RectMM
    well_gap_rect_mm: RectMM
    total_risers: int
    risers_per_flight: int
    treads_per_flight: int
    riser_height_mm: float
    tread_depth_mm: float
    floor_to_floor_height_mm: int
    z_start_mm: int
    z_mid_landing_mm: int
    z_end_mm: int
    orientation: str = "V"
    perimeter_beams: List[Tuple[Tuple[int, int], Tuple[int, int]]] = field(default_factory=list)
    core_columns: List[RectMM] = field(default_factory=list)


@dataclass
class ElevatorDetail:
    shaft_rect_mm: RectMM
    outer_wall_rect_mm: RectMM
    cab_rect_mm: RectMM
    door_center_mm: Tuple[int, int]
    door_width_mm: int
    door_orientation: str
    door_opens_toward: str = "N"


@dataclass
class FurnitureElement:
    furn_id: str
    room_id: str
    kind: str
    rect_mm: RectMM
    label_en: str = ""
    label_fa: str = ""
    orientation: str = "V"


@dataclass
class DimensionChain:
    dim_id: str
    p0_mm: Tuple[int, int]
    p1_mm: Tuple[int, int]
    offset_mm: int
    orientation: str
    text_label: str


@dataclass
class RoomSpace:
    room_id: str
    code_en: str
    label_fa: str
    unit_id: str
    space_category: str
    net_rect_mm: RectMM
    z_elevation_mm: int
    elevation_label: str
    natural_light: str
    is_open_edge_north: bool = False
    is_open_edge_south: bool = False
    is_open_edge_west: bool = False
    is_open_edge_east: bool = False
    is_open_pilotis_zone: bool = False
    is_open_front_terrace: bool = False
    parapet_height_cm: int = 100
    l_extension_rect_mm: Optional[RectMM] = None
    l_extension_label_fa: str = ""


@dataclass
class BackyardLightwell:
    void_id: str
    label_fa: str
    label_en: str
    position: str
    rect_mm: RectMM
    depth_mm: int
    target_area_m2: float
    z_elevation_mm: int = 100


@dataclass
class ColumnElement:
    col_id: str
    axis_label: str
    rect_mm: RectMM
    is_core_column: bool = False


@dataclass
class ParametricSiteSpec:
    width_x_mm: int = 10_000
    length_y_mm: int = 20_000
    separation_joint_mm: int = 50
    south_street_width_mm: int = 10_000
    party_walls: Tuple[str, ...] = ("NORTH", "EAST", "WEST")
    street_sides: Tuple[str, ...] = ("SOUTH",)
    boundary_neighbors: Dict[str, str] = field(
        default_factory=lambda: {"NORTH": "NEIGHBOR_LOT", "EAST": "NEIGHBOR_LOT", "SOUTH": "STREET", "WEST": "NEIGHBOR_LOT"}
    )
    site_area_m2: float = 200.0
    is_irregular_polygon: bool = False
    polygon_vertices_mm: Tuple[Tuple[int, int], ...] = ()
    south_y_west_mm: int = 0
    south_y_east_mm: int = 0
    north_y_west_mm: int = 20_000
    north_y_east_mm: int = 20_000
    flip_plan_north_south: bool = False
    expand_bed3_over_corridor: bool = False
    bed3_is_master: bool = False
    render_3d_facade_mode: bool = False
    render_facade_side: str = "SOUTH"
    facade_style_fa: str = "نئوکلاسیک (سنگ تراورتن کرم روشن)"
    facade_material_fa: str = "سنگ تراورتن کرم روشن"
    render_lighting_mode: str = "DAY_SUNNY"
    active_render_state: Dict[str, Any] = field(default_factory=dict)
    coverage_ratio: float = 0.60
    building_placement: str = "NORTH"
    lightwell_enabled: bool = True
    lightwell_position: str = "NORTH"
    lightwell_depth_mm: int = 1700
    lightwell_area_m2: float = 12.0
    include_dirty_kitchen: bool = True
    typology: BuildingTypology = BuildingTypology.VILLA_1FLOOR
    total_Privilege_floors: int = 1
    has_basement: bool = False
    pilotis_height_mm: int = 2520
    typical_floor_height_mm: int = 3240
    south_cantilever_mm: int = 1100
    courtyard_cantilever_mm: int = 0
    ext_wall_mm: int = 200
    int_wall_mm: int = 100


@dataclass
class FloorPlanDesignV3:
    floor_index: int
    name_fa: str
    name_en: str
    occupancy: OccupancyType
    z_elevation_mm: int
    elevation_code_str: str
    floor_height_mm: int
    unit_count: int
    gross_building_rect_mm: RectMM
    courtyards: List[Tuple[str, RectMM, str]]
    lightwells: List[BackyardLightwell]
    grid_x_mm: List[Tuple[str, int]]
    grid_y_mm: List[Tuple[str, int]]
    columns: List[ColumnElement]
    stair_detail: Optional[StairFlightDetail]
    elevator_detail: Optional[ElevatorDetail]
    rooms: List[RoomSpace]
    doors: List[DoorElement]
    windows: List[WindowElement]
    furniture: List[FurnitureElement]
    dimensions: List[DimensionChain]
    coverage_ratio_achieved: float
    gross_area_m2: float
    net_area_m2: float
    is_open_pilotis: bool = False
    turning_zone_rect_mm: Optional[RectMM] = None
    cantilever_zone_rect_mm: Optional[RectMM] = None
    pilotis_canopy_rect_mm: Optional[RectMM] = None
    pilotis_nw_canopy_rect_mm: Optional[RectMM] = None
    pilotis_pedestrian_path_rect_mm: Optional[RectMM] = None


@dataclass
class AuditReportV3:
    status: ValidationStatus
    checks_passed: Dict[str, bool]
    violations: List[str] = field(default_factory=list)
    summary_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class BuildingProjectResultV3:
    project_id: str
    project_title_fa: str
    user_prompt: str
    site: ParametricSiteSpec
    floors: List[FloorPlanDesignV3]
    audit: AuditReportV3
    saved_files: Dict[str, str] = field(default_factory=dict)
    roof_plan: Optional[FloorPlanDesignV3] = None
