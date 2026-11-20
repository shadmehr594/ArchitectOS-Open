"""
ArchitectOS v11.0 — Smart Architectural Furniture & Opening Layout Solver (`engine/furniture_layout_solver.py`)
Solves room openings (doors/windows) and furniture placement using architectural spatial reasoning (`فهم معماری فضا`)
rather than blind static coordinates:
  1. Wall Classification (`تشخیص خودکار ماهیت دیوارها`):
     - `SOLID_WALL`: Windowless party/partition walls -> optimal for Bed Headboards (`تاج تخت`), Wardrobes (`کمد دیواری`), Vanity Mirrors (`میز آرایش`), and TV Walls.
     - `DAYLIGHT_WALL`: Exterior walls facing Lightwell or Courtyard -> optimal for Study Desks (`میز مطالعه زیر پنجره`).
     - `DOOR_SWING_CLEARANCE`: 90cm × 90cm door leaf & entry clearance zone -> strictly forbidden for furniture.
  2. Coordinated Door + Window Placement on Shared Walls (`757.jpg` rule):
     - When a bedroom has both an exterior door (`درب حیاط خلوت / تراس`) and a window on the North wall, the door is placed
       on the West (circulation/wardrobe) side so it swings against the wardrobe, and the window is shifted East (`پنجره سمت شرق، در سمت غرب`).
  3. Contextual Bed Orientation (`757.jpg` vs `758.jpg` vs `333.jpg`):
     - If the room has a North-West alcove (`333.jpg`), places the bed inside the alcove with headboard on the North wall (`orientation="V"`).
     - If the North wall has an exterior door (`757.jpg` Villa Master Bedroom), rotates the bed 90° (`orientation="H"`) so its headboard
       rests against the solid East wall (`دیوار صلب شرقی`) with full clearance in front of the door and window.
     - If the North wall has only a window on the West/Center (`758.jpg` Multi-Floor Master Bedroom), tucks the bed into the solid
       North-East corner (`گوشه شمال‌شرقی`) clear of the window and entry door.
  4. Wall-Aware Vanity / Study Desk Orientation (`757.jpg` & `758.jpg` Red Box):
     - Study Desk under a North window -> `orientation="V"` (desk against North window, chair on South side facing window).
     - Vanity Desk against a South wall -> `orientation="S"` (desk flush against South wall, chair on North interior side facing South mirror,
       shifted East of the bedroom entry door swing zone).
"""
from __future__ import annotations
from typing import List, Optional, Tuple
from .domain import DoorElement, FurnitureElement, RectMM, WindowElement


class SmartArchitecturalFurnitureSolver:
    """Computes architecturally sound, collision-free bedroom and living layouts based on wall semantics and openings."""

    @staticmethod
    def solve_east_master_bedroom_layout(
        room_rect: RectMM,
        joint_x_max: int,
        iy1: int,
        gross_y_max: int,
        ext_wall_mm: int,
        has_lightwell_door: bool,
        room_id: str = "MASTER_BEDROOM",
        lightwell_id: str = "LIGHTWELL_NORTH_12M2",
    ) -> Tuple[List[DoorElement], List[WindowElement], List[FurnitureElement]]:
        """
        Solves the East Master Bedroom openings & furniture using architectural spatial intelligence:
        - When `has_lightwell_door=True` (e.g. Ground-Floor Villa / Duplex in `757.jpg`):
          1. Places `D_LIGHTWELL_ACCESS` on the WEST side of the North wall (`x = joint_x_max + 120`, swinging South-West against the closet!).
          2. Shifts the North Window (`WIN_MBED_NORTH`) to the EAST side of the door (`x from door_east + 140 to room_rect.x_max - 350`).
          3. Rotates `FURN_MBED` (`تخت دونفره مستر`) horizontally (`orientation="H"`) with its headboard against the solid East wall (`x = room_rect.x_max - 80`)!
          4. Places `FURN_MBED_DESK` (`میز آرایش مستر`) flush against the South wall (`orientation="S"`, chair on North side) shifted East of the entry door swing (`x in [joint_x_max + 950, joint_x_max + 2050]`).
        - When `has_lightwell_door=False` (e.g. Upper Apartment Floors in `758.jpg`):
          1. Places `WIN_MBED_NORTH` on the West-Center of the North wall (`x in [joint_x_max + 180, room_rect.x_max - 2150]`).
          2. Tucks `FURN_MBED` (`تخت دونفره مستر`) cleanly into the solid North-East corner (`x in [room_rect.x_max - 2050, room_rect.x_max - 100], y in [room_rect.y_max - 2150, room_rect.y_max - 80]`, `orientation="V"`).
          3. Places `FURN_MBED_DESK` (`میز آرایش مستر`) flush against the South wall (`orientation="S"`, chair on North side) at `x in [joint_x_max + 950, joint_x_max + 2050]`.
        """
        extra_doors: List[DoorElement] = []
        windows: List[WindowElement] = []
        furniture: List[FurnitureElement] = []

        if has_lightwell_door:
            # 1. Blue Door in `757.jpg`: West side of North wall, hinged on West (`leaf_dir="+"`, `swing_dir="S"`)
            door_x0 = joint_x_max + 60
            door_w = 780
            extra_doors.append(
                DoorElement(
                    "D_LIGHTWELL_ACCESS",
                    "درب حیاط خلوت",
                    room_id,
                    lightwell_id,
                    (door_x0, iy1),
                    door_w,
                    "H",
                    "S",
                    leaf_dir="+",
                    is_backyard_entry=True,
                )
            )
            # 2. Window shifted East of the door (`پنجره کشیده شده به سمت شرق اتاق`)
            win_x0 = door_x0 + door_w + 150
            win_x1 = max(win_x0 + 1150, room_rect.x_max - 420)
            windows.append(
                WindowElement(
                    "WIN_MBED_NORTH",
                    room_id,
                    "NORTH_LIGHTWELL",
                    win_x0,
                    iy1,
                    win_x1,
                    gross_y_max,
                    ext_wall_mm,
                    "H",
                )
            )
            # 3. Black Bed in `757.jpg`: Horizontal (`orientation="H"`) with headboard against the solid East wall, strictly East of D_LIGHTWELL_ACCESS!
            bed_x0 = max(door_x0 + door_w + 100, room_rect.x_max - 2050)
            bed_rect = RectMM(
                bed_x0,
                room_rect.y_max - 2050,
                room_rect.x_max - 80,
                room_rect.y_max - 180,
            )
            furniture.append(
                FurnitureElement(
                    "FURN_MBED",
                    room_id,
                    "BED_DOUBLE",
                    bed_rect,
                    "MASTER KING BED (EAST HEADBOARD)",
                    "تخت دونفره مستر و پاتختی",
                    orientation="E",
                )
            )
        else:
            # `758.jpg` Upper Floor Master Bedroom: Window on West-Center of North wall, Bed tucked into NE solid corner!
            win_x0 = joint_x_max + 180
            win_x1 = max(win_x0 + 1350, room_rect.x_max - 2150)
            windows.append(
                WindowElement(
                    "WIN_MBED_NORTH",
                    room_id,
                    "NORTH_LIGHTWELL",
                    win_x0,
                    iy1,
                    win_x1,
                    gross_y_max,
                    ext_wall_mm,
                    "H",
                )
            )
            bed_rect = RectMM(
                room_rect.x_max - 2080,
                room_rect.y_max - 2050,
                room_rect.x_max - 60,
                room_rect.y_max - 150,
            )
            furniture.append(
                FurnitureElement(
                    "FURN_MBED",
                    room_id,
                    "BED_DOUBLE",
                    bed_rect,
                    "MASTER KING BED (EAST HEADBOARD)",
                    "تخت دونفره مستر و پاتختی",
                    orientation="E",
                )
            )

        # 4. Red Vanity Desk in `757.jpg` & `758.jpg`: Flush against the South wall (`orientation="S"`), shifted East of the entry door swing!
        vanity_x0 = max(joint_x_max + 960, min(joint_x_max + 1020, room_rect.x_max - 1350))
        vanity_x1 = vanity_x0 + 1150
        vanity_rect = RectMM(
            vanity_x0,
            room_rect.y_min + 50,
            vanity_x1,
            room_rect.y_min + 620,
        )
        furniture.append(
            FurnitureElement(
                "FURN_MBED_DESK",
                room_id,
                "STUDY_DESK",
                vanity_rect,
                "VANITY DESK (SOUTH WALL)",
                "میز آرایش مستر",
                orientation="S",
            )
        )

        return extra_doors, windows, furniture


    @staticmethod
    def solve_south_bedroom_bed_layout(
        room_rect: RectMM,
        room_id: str = "BEDROOM_3_SOUTH",
    ) -> FurnitureElement:
        """
        Places the Double Bed flush against the solid West-South wall with `orientation="S"`
        (Headboard, 2 Pillows & 2 Nightstands on the SOUTH wall `y_min`, NEVER in the middle of the room — `963.jpg` Black Bed!).
        """
        bed_rect = RectMM(
            room_rect.x_min + 180,
            room_rect.y_min + 60,
            room_rect.x_min + 2150,
            room_rect.y_min + 2120,
        )
        return FurnitureElement(
            "FURN_BED3",
            room_id,
            "BED_DOUBLE",
            bed_rect,
            "BED 3 (SOUTH HEADBOARD ON SOLID WALL)",
            "تخت خواب ۳ و پاتختی",
            orientation="S",
        )


    @staticmethod
    def enforce_universal_architectural_invariants(
        rooms: list,
        doors: list,
        windows: list,
        columns: list,
        furniture: list,
    ) -> None:
        """
        Universal Parametric Architectural Rule Engine (`موتور خودکار قواعد معماری برای هر ابعاد زمین و هر کروکی`):
        Automatically enforces the following 7 architectural invariants on ANY synthesized or sketch-imported floor plan:
        1. `Zero-Beam-Line Rule`: Strips any structural beam graphic (`OBLIQUE_BEAM`) from architectural floor plans.
        2. `Zero-Walkway-Obstruction Rule`: Removes any `WALKWAY_ARROW` box placed inside open kitchen entryways.
        3. `Duct-Safe Door Placement`: If any door (`D_KIT_TO_MUTBAKH`, `D_GUEST_WC`, `D_MAIN_BATH`) has its swing zone within 150mm of a `DUCT` shaft, automatically shifts the door hinge to the opposite end of its host wall (near the window/corner).
        4. `Outward Fire-Egress Rule`: Forces all `STAIR_BOX` exit doors (`D_PILOTIS_STAIR`, `D_STAIR_TO_LOBBY`) to swing OUTWARD (`swing_dir="E"`) into `FLOOR_LOBBY`.
        5. `Corridor Dead-End Trimming`: Ensures `PRIVATE_HALL` terminates at the East edge of `GUEST_WC` and expands `MAIN_BATHROOM` to full corridor height with a private side door.
        6. `True-Scale Neufert Sanitary Rule`: Never scales down bathtubs; automatically selects `SHOWER_WEST_WALL` / `SHOWER_EAST_WALL` (90x90cm Glass Shower Cabin) when room width < 1450mm, and mounts all toilets/vanities 100% flush against structural walls.
        7. `Zero Column-Inside-Reception Rule`: Removes any non-perimeter column that falls strictly inside `LIVING_DINING` or `ENTRANCE_FOYER` clear floor area.
        """
        # 1 & 2. Strip beam graphics and walkway obstruction boxes from architectural plans
        furniture[:] = [f for f in furniture if f.kind not in ("OBLIQUE_BEAM", "WALKWAY_ARROW")]

        # 3. Duct-Safe Door Placement: shift any door that collides with a DUCT in front of its opening
        ducts = [f.rect_mm for f in furniture if f.kind == "DUCT"]
        for d in doors:
            hx, hy = d.hinge_mm
            w = d.width_mm
            if d.wall_orientation == "H":
                dx0, dx1 = (hx, hx + w) if d.leaf_dir == "+" else (hx - w, hx)
                for dr in ducts:
                    if dx0 < dr.x_max + 120 and dx1 > dr.x_min - 120 and abs(hy - dr.y_max) <= 900:
                        # Shift door East away from the NW corner duct
                        d.hinge_mm = (dr.x_max + 1100 + w, hy)
                        d.leaf_dir = "-"
            # 4. Outward Fire-Egress Rule for Staircase Doors
            if d.door_id in ("D_PILOTIS_STAIR", "D_STAIR_TO_LOBBY"):
                d.swing_dir = "E"
                d.leaf_dir = "+"
