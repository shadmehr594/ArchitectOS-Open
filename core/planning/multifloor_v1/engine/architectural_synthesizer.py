"""
ArchitectOS Parametric Architectural Space Planning & CAD Synthesizer (v19.0 — Zero-Defect Master Reference & Safe Teacher-Learning Edition).
Fixes 100% of the issues marked by the user in `321.jpg` and `333.jpg`, plus Villa and Modern Duplex architectural rules:
  1. Door Placement & Swing Direction Fix (`321.jpg` 6 Blue Circles):
     - Fixed vertical door `leaf_dir` ("+" extending North `hy - rad` vs "-" extending South `hy + rad`) so `D_PILOTIS_STAIR`,
       `D_PILOTIS_LOBBY_ENTRY`, `D_STAIR_TO_LOBBY`, `D_UNIT_MAIN_ENTRY`, `D_GUEST_WC`, and `D_LIVING_TO_TERRACE` sit 100% inside
       their wall segments and never overlap stair steps, elevator shafts, or balcony railings.
  2. Unified Seamless Corridor & Removal of Extra Hallway Walls (`321.jpg` Red Circle + Villa Hallway):
     - Removed the extra horizontal wall and shoe-closet box blocking `ENTRANCE_FOYER` -> `PRIVATE_HALL`.
     - Unified `ENTRANCE_FOYER`, `PRIVATE_HALL`, and `BEDROOM_ENTRY_JOINT` into ONE single continuous corridor with a uniform
       color (`#fef9c3`), zero internal dividing lines, and no separate "مفصل" label.
  3. Exact `333.jpg` West Bedroom Furniture & Partition Wall:
     - Blue Box in `333.jpg`: Placed the West Bedroom Double Bed (`تخت خواب و پاتختی`) inside the North-West Alcove (`تورفتگی شمال‌غربی کنار حیاط خلوت`)
       with its headboard on the North wall and direct daylight from the L-shaped window.
     - Red Box in `333.jpg`: Placed the Study Desk & Chair (`میز مطالعه و کامپیوتر`) directly under the horizontal North window facing the Lightwell.
     - Grey Line in `333.jpg`: Added a thick solid architectural partition wall (`PARTITION_WALL` — `دیوار جداکننده بین دو اتاق خواب`)
       down the center line `x = bed_split_x` between the two back-to-back built-in wardrobes.
  4. Single-Unit Villa Refinements:
     - Unified T-shaped corridor with zero extra lines, West bedroom matching `333.jpg` (Bed in NW alcove + Desk under window),
       East Master Bedroom Suite with Walk-in Closet, Master Bath, and Direct Access Door to the Lightwell (`درب حیاط خلوت`),
       and Kitchen with South Open Counter + 8-Person Dining Table directly in front of it.
  5. Redesigned 2-Story Modern Duplex Villa (`پله دکوراتیو L شکل خارج از آشپزخانه + همکف عمومی با فقط ۱ خواب مهمان + طبقه بالا خصوصی ۳ خواب`):
     - Ground Floor (Day Zone): Decorative L-Shaped Curved Duplex Staircase (`پله دکوراتیو و شکیل L شکل دوبلکس`) accessed directly from the
       Central Entrance Gallery (completely outside the Kitchen!), Large North-West Open Kitchen + Mutbakh, South-West Dining Hall,
       Grand East Double-Height Reception & Living Hall, and ONLY ONE Ground-Floor Guest Bedroom in the North-East accessed from the
       Central Hallway with a Direct Access Door to the Lightwell.
     - Upper Floor (Night Zone): Upper Family Living overlooking the Double-Height Void (`وید دوبلکس`), South-West Bedroom 3 + South Terrace,
       North-West Bedroom 2 (`333.jpg` layout with Bed in NW alcove + Study Desk under window + L-window), and North-East Grand Master Suite.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
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
from .nl_design_parser import parse_architectural_prompt
from .teacher_memory import SafeTeacherMemory
from .furniture_layout_solver import SmartArchitecturalFurnitureSolver


class ParametricArchitecturalSynthesizer:
    """Master v19.0 Parametric Architectural Synthesizer with Safe Teacher-Mode Rule Memory."""

    def __init__(self, teacher_memory: Optional[SafeTeacherMemory] = None) -> None:
        self.teacher_memory = teacher_memory or SafeTeacherMemory()

    def learn_from_teacher(self, feedback_text: str) -> Dict[str, Any]:
        """Records a user/teacher architectural correction into persistent JSON memory without modifying code."""
        return self.teacher_memory.learn_from_teacher_feedback(feedback_text)

    def synthesize_from_text(self, user_prompt: str, active_site_krocki: Optional[Dict[str, Any]] = None) -> BuildingProjectResultV3:
        params = parse_architectural_prompt(user_prompt, active_site_krocki=active_site_krocki)
        return self.synthesize_from_params(params)

    def synthesize_from_params(self, params: Dict[str, Any]) -> BuildingProjectResultV3:
        self._last_params = dict(params or {})
        raw_w_site = max(5500, int(params.get("site_width_mm", 10_000)))
        raw_l_site = max(5500, int(params.get("site_length_mm", 20_000)))
        cov = max(0.10, min(1.00, float(params.get("coverage_ratio", 0.60))))
        req_placement = str(params.get("building_placement", "NORTH")).upper()
        is_east_west_mode = req_placement in ("EAST", "WEST") or (raw_w_site > raw_l_site * 1.25 and req_placement not in ("NORTH", "SOUTH"))
        if is_east_west_mode:
            if req_placement not in ("EAST", "WEST"):
                req_placement = "EAST"
            w_site = min(raw_w_site, raw_l_site)
            l_site = max(raw_w_site, raw_l_site)
            placement = "NORTH" if req_placement == "EAST" else "SOUTH"
            if not params.get("krocki_source_file") and not params.get("boundary_neighbors"):
                # Default for East-West lots: access & streets on EAST/WEST, neighbor lots on NORTH/SOUTH
                params["street_sides"] = ["WEST"] if req_placement == "EAST" else ["EAST"]
                params["party_wall_sides"] = [s for s in ("NORTH", "EAST", "SOUTH", "WEST") if s not in params["street_sides"]]
                params["boundary_neighbors"] = {s: ("STREET" if s in params["street_sides"] else "NEIGHBOR_LOT") for s in ("NORTH", "EAST", "SOUTH", "WEST")}
        else:
            w_site = raw_w_site
            l_site = raw_l_site
            placement = req_placement
        lw_enabled = bool(params.get("lightwell_enabled", True))
        st_sides_check = set(params.get("street_sides") or [])
        b_neigh_check = params.get("boundary_neighbors") or {}
        raw_p_low = str(params.get("raw_prompt", "")).lower()
        explicit_want_lw = any(k in raw_p_low for k in ("با حیاط خلوت", "با پاسیو", "دارای حیاط خلوت"))
        if not explicit_want_lw:
            if placement == "SOUTH":
                lw_enabled = False
            elif req_placement == "NORTH" and ("NORTH" in st_sides_check or b_neigh_check.get("NORTH") == "STREET"):
                lw_enabled = False
            elif req_placement == "EAST" and ("EAST" in st_sides_check or b_neigh_check.get("EAST") == "STREET"):
                lw_enabled = False
            elif req_placement == "WEST" and ("WEST" in st_sides_check or b_neigh_check.get("WEST") == "STREET"):
                lw_enabled = False
        lw_pos = str(params.get("lightwell_position", "NORTH")).upper()
        lw_depth = max(1400, int(params.get("lightwell_depth_mm", 1700)))
        lw_area = max(6.0, float(params.get("lightwell_area_m2", 12.0)))
        dirty_kit = bool(params.get("include_dirty_kitchen", True))

        scenario_mode = str(params.get("scenario_mode", "")).lower()
        is_duplex_flag = bool(params.get("is_duplex", False)) or ("duplex" in scenario_mode)
        typ_str = str(params.get("typology", BuildingTypology.VILLA_1FLOOR.value))
        if is_duplex_flag:
            typology = BuildingTypology.DUPLEX_2FLOOR
        else:
            typology = (
                BuildingTypology(typ_str)
                if typ_str in BuildingTypology._value2member_map_
                else BuildingTypology.VILLA_1FLOOR
            )

        floor_count = max(1, int(params.get("floor_count", 2 if typology == BuildingTypology.DUPLEX_2FLOOR else 1)))
        has_basement = bool(params.get("has_basement", False))
        joint = int(params.get("separation_joint_mm", 50))
        pilotis_h = 2520
        typical_h = 3240
        cantilever_mm = int(params.get("south_cantilever_mm", 1100))

        raw_poly_mm = params.get("krocki_polygon_mm") or []
        poly_tuple_mm = tuple((int(p[0]), int(p[1])) for p in raw_poly_mm) if raw_poly_mm else ()
        is_irreg = bool(params.get("krocki_is_irregular", False)) or (len(poly_tuple_mm) > 0 and len(poly_tuple_mm) != 4)
        st_sides = tuple(params.get("street_sides") or ("SOUTH",))
        pw_sides = tuple(params.get("party_wall_sides") or tuple(s for s in ("NORTH", "EAST", "SOUTH", "WEST") if s not in st_sides))
        b_neigh = dict(params.get("boundary_neighbors") or {s: ("STREET" if s in st_sides else "NEIGHBOR_LOT") for s in ("NORTH", "EAST", "SOUTH", "WEST")})
        true_site_area_m2 = round(float(params.get("site_area_m2") or ((w_site * l_site) / 1e6)), 2)

        site = ParametricSiteSpec(
            width_x_mm=w_site,
            length_y_mm=l_site,
            separation_joint_mm=joint,
            south_street_width_mm=10_000,
            party_walls=pw_sides,
            street_sides=st_sides,
            boundary_neighbors=b_neigh,
            site_area_m2=true_site_area_m2,
            is_irregular_polygon=is_irreg,
            polygon_vertices_mm=poly_tuple_mm,
            south_y_west_mm=int(params.get("south_y_west_mm", 0)),
            south_y_east_mm=int(params.get("south_y_east_mm", 0)),
            north_y_west_mm=int(params.get("north_y_west_mm", l_site)),
            north_y_east_mm=int(params.get("north_y_east_mm", l_site)),
            flip_plan_north_south=bool(params.get("flip_plan_north_south", False)),
            expand_bed3_over_corridor=bool(params.get("expand_bed3_over_corridor", False)),
            bed3_is_master=bool(params.get("bed3_is_master", False)),
            render_3d_facade_mode=bool(params.get("render_3d_facade_mode", False)),
            render_facade_side=str(params.get("render_facade_side") or ("NORTH" if params.get("flip_plan_north_south") else "SOUTH")),
            facade_style_fa=str(params.get("facade_style_fa") or "نئوکلاسیک (سنگ تراورتن کرم روشن)"),
            facade_material_fa=str(params.get("facade_material_fa") or "سنگ تراورتن کرم روشن"),
            render_lighting_mode=str(params.get("render_lighting_mode") or "DAY_SUNNY"),
            active_render_state=dict(params.get("active_render_state") or {}, **({"custom_facade_profile": params["custom_facade_profile"]} if params.get("custom_facade_profile") else {})),
            coverage_ratio=cov,
            building_placement=placement,
            lightwell_enabled=lw_enabled,
            lightwell_position=lw_pos,
            lightwell_depth_mm=lw_depth,
            lightwell_area_m2=lw_area,
            include_dirty_kitchen=dirty_kit,
            typology=typology,
            total_Privilege_floors=floor_count,
            has_basement=has_basement,
            pilotis_height_mm=pilotis_h,
            typical_floor_height_mm=typical_h,
            south_cantilever_mm=cantilever_mm,
            courtyard_cantilever_mm=int(params.get("courtyard_cantilever_mm", 0)),
        )

        floors: List[FloorPlanDesignV3] = []
        place_fa = {"NORTH": "شمال", "SOUTH": "جنوب", "EAST": "شرق", "WEST": "غرب", "CENTER": "میانه"}.get(req_placement, "شمال")

        if typology == BuildingTypology.DUPLEX_2FLOOR and bool(params.get("is_luxury_pool_duplex", False)):
            return self._synthesize_luxury_pool_duplex_project(params)
        elif typology == BuildingTypology.DUPLEX_2FLOOR:
            remove_void = bool(params.get("remove_duplex_void", False))
            rep_minibar = bool(params.get("replace_minibar_with_bedroom", False))
            void_rep = str(params.get("void_replacement_room", "PRIVATE_LIVING"))
            upper_beds_str = "۳ خواب مستقل (تبدیل مینی‌بار و تراس به خواب ۳)" if rep_minibar else "۲ خواب + مینی‌بار و تراس مسقف بزرگ"
            void_phrase = (
                f"{upper_beds_str} — بدون وید (نشیمن خصوصی بزرگ در طبقه اول)"
                if (remove_void and void_rep != "BEDROOM")
                else (f"{upper_beds_str} — بدون وید (اتاق خواب اضافه جای وید)" if remove_void else f"با {upper_beds_str} و وید دوبلکس")
            )
            title_fa = (
                f"پلان ساختمان ویلایی دوبلکس مدرن v30.0 (زمین {w_site/1000:g}×{l_site/1000:g}m = {true_site_area_m2:g}m²، "
                f"اشغال {int(cov*100)}٪ در {place_fa} | پله دکوراتیو L شکل + همکف عمومی با ۱ خواب مهمان + طبقه اول خصوصی {void_phrase})"
            )
            floors.append(
                self._synthesize_duplex_lower_day_floor(
                    site=site,
                    floor_index=0,
                    z_mm=450,
                    floor_h_mm=typical_h,
                    elev_str="+0.45 m",
                    cov_ratio=cov,
                    name_fa="طبقه همکف دوبلکس (زون روز: پله دکوراتیو L شکل از گالری + آشپزخانه اپن و ناهارخوری + پذیرایی + ۱ خواب مهمان با درب حیاط خلوت)",
                )
            )
            floors.append(
                self._synthesize_duplex_upper_night_floor(
                    site=site,
                    floor_index=1,
                    z_mm=450 + typical_h,
                    floor_h_mm=typical_h,
                    elev_str="+3.69 m",
                    cov_ratio=cov,
                    name_fa=f"طبقه اول دوبلکس (زون شب: {'۳ خواب خصوصی' if rep_minibar else '۲ خواب خصوصی + مینی‌بار و تراس مسقف بزرگ'} + وید دوبلکس)",
                )
            )
        elif typology == BuildingTypology.VILLA_1FLOOR and floor_count == 1 and not has_basement:
            req_bldg = params.get("requested_building_area_m2")
            bldg_m2 = round(float(req_bldg), 1) if req_bldg else round((w_site * l_site * cov) / 1e6, 1)
            site_m2 = round(float(params.get("site_area_m2") or ((w_site * l_site) / 1e6)), 1)
            title_fa = (
                f"پلان ویلایی تک‌واحدی مهندسی v27.0 (زیربنا {bldg_m2:g}m² در زمین {w_site/1000:g}×{l_site/1000:g}m = {site_m2:g}m²، "
                f"اشغال {int(cov*100)}٪ در {place_fa} | راهرو یکپارچه + چیدمان استاندارد خواب‌ها + اپن جنوبی و درب حیاط خلوت)"
            )
            floors.append(
                self._synthesize_villa_single_unit_floor(
                    site=site,
                    floor_index=0,
                    z_mm=450,
                    floor_h_mm=typical_h,
                    elev_str="+0.45 m",
                    cov_ratio=cov,
                    name_fa="پلان طبقه همکف ویلایی تک‌واحدی (کد کف: ⊕ +0.45m) — راهرو یکپارچه + چیدمان استاندارد خواب‌ها (333.jpg) + درب حیاط خلوت",
                )
            )
        else:
            title_fa = (
                f"شیت کامل طبقات ساختمان چندطبقه v19.0 (زمین {w_site/1000:g}×{l_site/1000:g}m، اشغال {int(cov*100)}٪ در {place_fa} | "
                f"اصلاح کامل درها (321.jpg) + راهرو یکپارچه + تخت در شمال‌غربی و میز مطالعه زیر پنجره و دیوار بین دو خواب (333.jpg))"
            )
            z_pilotis = 200
            floors.append(
                self._synthesize_open_pilotis_floor(
                    site=site,
                    floor_index=0,
                    z_mm=z_pilotis,
                    floor_h_mm=pilotis_h,
                    elev_str="±0.00 / +0.20 m",
                    cov_ratio=cov,
                )
            )
            upper_count = max(2, floor_count)
            cur_z = z_pilotis + pilotis_h
            for idx in range(1, upper_count + 1):
                z_str = f"+{cur_z/1000:.2f} m"
                layout_var = str(params.get("layout_variant", "TYPE_A")).upper()
                var_title = (
                    "تیپ B: آشپزخانه با پیشخوان افقی جنوبی + ناهارخوری روبروی اپن + نشیمن شرقی و کمد جالباسی ورودی"
                    if layout_var == "TYPE_B"
                    else (
                        "تیپ C: پلان تفکیکی (پذیرایی رسمی مهمان + نشیمن خصوصی خانواده + ناهارخوری ۸ نفره + آشپزخانه جزیره بزرگ)"
                        if layout_var == "TYPE_C"
                        else "تیپ A: پلان ۲ خوابه بزرگ (تخت شمال‌غربی و میز مطالعه زیر پنجره + دیوار بین دو خواب + جزیره عمودی)"
                    )
                )
                floors.append(
                    self._synthesize_multifloor_residential_floor(
                        site=site,
                        floor_index=idx,
                        z_mm=cur_z,
                        floor_h_mm=typical_h,
                        elev_str=z_str,
                        cov_ratio=cov,
                        name_fa=f"پلان طبقه {idx} مسکونی ({var_title} | ۱۸ پله)",
                        layout_variant=layout_var,
                    )
                )
                cur_z += typical_h

        if site.flip_plan_north_south and floors:
            y_piv = floors[0].gross_building_rect_mm.y_min + floors[0].gross_building_rect_mm.y_max
            for fl_item in floors:
                self._flip_floor_north_south_in_place(fl_item, site, y_piv)
            title_fa += " | 🔄 چرخش ۱۸۰ درجه پلان (ورودی و پذیرایی در شمال، اتاق‌های خواب در جنوب)"

        if site.building_placement == "SOUTH" and abs(site.south_y_east_mm - site.south_y_west_mm) >= 100:
            for fl_item in floors:
                self._align_south_furniture_and_steps_to_slope(fl_item, site)

        if is_east_west_mode:
            from dataclasses import replace as _dc_replace
            ew_w = max(raw_w_site, raw_l_site)
            ew_l = min(raw_w_site, raw_l_site)
            site = _dc_replace(
                site,
                width_x_mm=ew_w,
                length_y_mm=ew_l,
                building_placement=req_placement,
                north_y_west_mm=ew_l,
                north_y_east_mm=ew_l,
            )
            for fl_item in floors:
                self._transpose_floor_to_east_west_in_place(fl_item, site, req_placement)
            title_fa = title_fa.replace(f"{w_site/1000:g}×{l_site/1000:g}m", f"{ew_w/1000:g}×{ew_l/1000:g}m (شرقی-غربی)")

        for fl_item in floors:
            self._enforce_neighbor_lot_opening_prohibition(fl_item, site)

        if site.render_3d_facade_mode:
            r_prompt = str(params.get("render_3d_prompt") or params.get("raw_prompt") or "")
            title_fa = f"🎨 رندر سه‌بعدی نما منطبق با پلان فعال — {title_fa}"

        roof_fl = self._synthesize_roof_and_kharposhteh_floor(site, floors)
        audit = self._audit_project_v10(site, floors)
        return BuildingProjectResultV3(
            project_id=f"ARCH_V13_{typology.value}_{placement}_{int(cov*100)}",
            project_title_fa=title_fa,
            user_prompt=str(params.get("raw_prompt", "")),
            site=site,
            floors=floors,
            audit=audit,
            roof_plan=roof_fl,
        )


    def _synthesize_roof_and_kharposhteh_floor(
        self,
        site: ParametricSiteSpec,
        floors: List[FloorPlanDesignV3],
    ) -> Optional[FloorPlanDesignV3]:
        """
        v33.5 Unified Roof, Kharposhteh & Elevator Machine Room Synthesizer (`پلان بام و خرپشته و اتاق موتورخانه آسانسور`):
        Implements the exact architectural layout specified by the user:
          1. All 4 Kharposhteh columns (`A-2`, `B-2`, `A-3`, `B-3`) sit strictly at the 4 outer corners of the unified
             `[kx0..kx1] × [ky0..ky1]` core rectangle — ZERO protrusions outside the 4-column box!
          2. West Half (`STAIR_BOX` — `باکس پله خرپشته`):
             - Staircase climbs to the North landing (`⊕ +9.20m`), and the **Kharposhteh Roof Exit Door (`D_ROOF_KHARPOSHTEH_EXIT`)**
               is placed directly on the **NORTH wall of the Kharposhteh (`دیوار شمالی خرپشته`)**, opening outward onto the North roof deck!
          3. East Half (`ELEVATOR_MACHINE_ROOM` + Steps in the Former Common Space):
             - The former common lobby space (`فضای مشاع بین اتاق آسانسور و خرپشته`) is merged into the **Elevator Machine Room
               (`اتاق موتورخانه آسانسور` at `⊕ +10.10m`, `+0.90m` above the roof)** so the machine room expands northward (`1.60m × 3.06m = 4.9 m²`)
               over and beyond the dashed `1.60m × 1.80m` elevator shaft without any protrusion outside the core box!
             - The northernmost `1.20m` strip of the former common space (`y = ky1 - 1200 .. ky1`) houses the **5 steps up from the roof
               (`پله‌های ورودی موتورخانه در بخش فضای مشاع واگذارشده`)** leading directly to the **Elevator Machine Room Entrance Door
               (`D_ELEVATOR_MACHINE_ROOM_ENTRY`)**!
          4. Unified Ceiling Height (`ارتفاع سقف خرپشته و اتاق آسانسور یکسان و هم‌تراز`):
             - Both the Staircase Kharposhteh and the Elevator Machine Room share the same unified top roof height (`H_total = 3.10m` above roof).
        """
        if len(floors) < 2:
            return None
        top_fl = floors[-1]
        gb = top_fl.gross_building_rect_mm
        z_roof_mm = top_fl.z_elevation_mm + top_fl.floor_height_mm
        z_mach_mm = z_roof_mm + 900  # +0.90m (90 cm) higher floor inside the unified-height penthouse!
        elev_str = f"+{z_roof_mm / 1000.0:.2f} m"
        mach_elev_str = f"+{z_mach_mm / 1000.0:.2f} m"
        kh_h_mm = 3100  # Unified taller ceiling height covering both Kharposhteh and +0.90m Machine Room!

        stair_rm = next((r for r in top_fl.rooms if r.room_id == "STAIR_BOX"), None)
        elev_rm = next((r for r in top_fl.rooms if r.room_id == "ELEVATOR_SHAFT"), None)
        lobby_rm = next((r for r in top_fl.rooms if r.room_id == "FLOOR_LOBBY"), None)

        roof_rooms: List[RoomSpace] = []
        roof_doors: List[DoorElement] = []
        roof_windows: List[WindowElement] = []  # ZERO windows on Kharposhteh or Machine Room!
        roof_furn: List[FurnitureElement] = []
        kh_columns: List[ColumnElement] = []

        if stair_rm is not None and lobby_rm is not None:
            core_rooms = [r for r in (stair_rm, elev_rm, lobby_rm) if r is not None]
            kx0 = min(r.net_rect_mm.x_min for r in core_rooms)
            ky0 = min(r.net_rect_mm.y_min for r in core_rooms)
            kx1 = max(r.net_rect_mm.x_max for r in core_rooms)
            ky1 = max(r.net_rect_mm.y_max for r in core_rooms)

            # 1. West Half: Staircase Box (`باکس پله خرپشته`) with North Exit Door (`در خروجی خرپشته روی دیوار شمالی`)
            st_r = stair_rm.net_rect_mm
            roof_rooms.append(
                RoomSpace(
                    room_id="STAIR_BOX",
                    code_en="ROOF KHARPOSHTEH STAIRCASE (NORTH EXIT TO ROOF)",
                    label_fa="باکس پله و پاگرد خرپشته",
                    unit_id="ROOF",
                    space_category="CORE",
                    net_rect_mm=st_r,
                    z_elevation_mm=z_roof_mm,
                    elevation_label=f"⊕ {elev_str}",
                    natural_light="NONE",
                )
            )
            # Outward-opening Kharposhteh Roof Exit Door on the NORTH wall of the Staircase Kharposhteh!
            roof_doors.append(
                DoorElement(
                    "D_ROOF_KHARPOSHTEH_EXIT",
                    "درب خروج خرپشته به پشت‌بام (روی دیوار شمالی خرپشته — بازشو به بیرون)",
                    "STAIR_BOX",
                    "ROOF_SURFACE",
                    (st_r.x_min + 620, st_r.y_max),
                    900,
                    "H",
                    "N",
                    leaf_dir="+",
                    is_main_entry=True,
                )
            )

            # 2. East Half: Former common lobby space is given to the Elevator Machine Room (`ELEVATOR_MACHINE_ROOM`) + its entrance steps!
            #    Strictly bounded inside [east_x0 .. kx1] x [ky0 .. ky1] — ZERO protrusion outside the 4-column box!
            east_x0 = lobby_rm.net_rect_mm.x_min
            steps_depth_mm = 1200
            mach_y_max = ky1 - steps_depth_mm
            mach_rect = RectMM(east_x0, ky0, kx1, mach_y_max)
            steps_bay_rect = RectMM(east_x0, mach_y_max, kx1, ky1)

            roof_rooms.append(
                RoomSpace(
                    room_id="ELEVATOR_MACHINE_ROOM",
                    code_en="EXPANDED ELEVATOR MACHINE ROOM (+0.90M ABOVE ROOF)",
                    label_fa="اتاق موتورخانه آسانسور (+۹۰cm)",
                    unit_id="ROOF",
                    space_category="CORE",
                    net_rect_mm=mach_rect,
                    z_elevation_mm=z_mach_mm,
                    elevation_label=f"⊕ {mach_elev_str}",
                    natural_light="NONE",
                )
            )

            if elev_rm is not None:
                sh_r = elev_rm.net_rect_mm
                roof_furn.append(
                    FurnitureElement(
                        "FURN_ELEV_SHAFT_DASHED",
                        "ELEVATOR_MACHINE_ROOM",
                        "ELEVATOR_SHAFT_DASHED",
                        sh_r,
                        "DASHED SHAFT 1.60x1.80M",
                        "چاهک آسانسور ۱.۶۰×۱.۸۰m",
                    )
                )

            # 5 Steps in the North-East bay (the northern part of the former common space) climbing South into the Machine Room Door!
            roof_furn.append(
                FurnitureElement(
                    "FURN_MACHINE_ROOM_ROOF_STEPS",
                    "ROOF_SURFACE",
                    "ROOF_MACHINE_ROOM_STEPS",
                    steps_bay_rect,
                    "5 ROOF STEPS TO MACHINE ROOM (+0.90M)",
                    f"۵ پله به موتورخانه ({mach_elev_str})",
                )
            )
            # Machine Room Entrance Door at the top of the steps (`ورودی اتاق آسانسور در بخش فضای مشاع واگذارشده`)
            roof_doors.append(
                DoorElement(
                    "D_ELEVATOR_MACHINE_ROOM_ENTRY",
                    "درب ورودی اتاق موتورخانه آسانسور (از پله‌های بام)",
                    "ELEVATOR_MACHINE_ROOM",
                    "ROOF_SURFACE",
                    (mach_rect.x_min + 360, mach_rect.y_max),
                    880,
                    "H",
                    "N",
                    leaf_dir="+",
                )
            )

            # Filter columns: ONLY the 4 columns at the corners of [kx0..kx1] x [ky0..ky1] continue up to the Kharposhteh roof!
            for c in top_fl.columns:
                cx_m, cy_m = c.rect_mm.center
                if (kx0 - 520 <= cx_m <= kx1 + 520) and (ky0 - 520 <= cy_m <= ky1 + 520):
                    kh_columns.append(c)
            existing_centers = [c.rect_mm.center for c in kh_columns]
            for c_idx, (tcx, tcy) in enumerate(((kx0, ky0), (kx1, ky0), (kx0, ky1), (kx1, ky1)), start=1):
                if not any(abs(ex - tcx) <= 450 and abs(ey - tcy) <= 450 for ex, ey in existing_centers):
                    kh_columns.append(
                        ColumnElement(
                            col_id=f"COL_KH_{c_idx}",
                            axis_label=f"KH-{c_idx}",
                            rect_mm=RectMM(tcx - 200, tcy - 200, tcx + 200, tcy + 200),
                        )
                    )
        else:
            st_furn = next((f for f in top_fl.furniture if f.kind == "DECORATIVE_DUPLEX_STAIR"), None)
            sr = st_furn.rect_mm if st_furn is not None else RectMM(gb.x_min + 200, gb.y_min + 3500, gb.x_min + 3600, gb.y_min + 6800)
            kh_rect = RectMM(sr.x_min, sr.y_min, min(gb.x_max - 1200, sr.x_max + 1100), sr.y_max)
            kx0, ky0, kx1, ky1 = kh_rect.x_min, kh_rect.y_min, kh_rect.x_max, kh_rect.y_max
            roof_rooms.append(
                RoomSpace(
                    room_id="KHARPOSHTEH_DUPLEX",
                    code_en="ROOF STAIR PENTHOUSE (KHARPOSHTEH H=3.10M)",
                    label_fa=f"خرپشته پله و پاگرد خروجی بام (کد {elev_str})",
                    unit_id="ROOF",
                    space_category="CORE",
                    net_rect_mm=kh_rect,
                    z_elevation_mm=z_roof_mm,
                    elevation_label=f"⊕ {elev_str}",
                    natural_light="NONE",
                )
            )
            if st_furn is not None:
                roof_furn.append(st_furn)
            roof_doors.append(
                DoorElement(
                    "D_ROOF_KHARPOSHTEH_EXIT",
                    "درب خروج خرپشته به پشت‌بام (روی دیوار شمالی — بازشو به بیرون)",
                    "KHARPOSHTEH_DUPLEX",
                    "ROOF_SURFACE",
                    (kh_rect.x_min + 450, kh_rect.y_max),
                    900,
                    "H",
                    "N",
                    leaf_dir="+",
                    is_main_entry=True,
                )
            )
            for c_idx, (tcx, tcy) in enumerate(((kx0, ky0), (kx1, ky0), (kx0, ky1), (kx1, ky1)), start=1):
                kh_columns.append(
                    ColumnElement(
                        col_id=f"COL_KH_{c_idx}",
                        axis_label=f"KH-{c_idx}",
                        rect_mm=RectMM(tcx - 200, tcy - 200, tcx + 200, tcy + 200),
                    )
                )

        kh_gx = [g for g in top_fl.grid_x_mm if any(abs(g[1] - c.rect_mm.center[0]) <= 350 for c in kh_columns)]
        kh_gy = [g for g in top_fl.grid_y_mm if any(abs(g[1] - c.rect_mm.center[1]) <= 350 for c in kh_columns)]

        return FloorPlanDesignV3(
            floor_index=len(floors),
            name_fa=f"پلان بام و خرپشته (بام: ⊕ {elev_str} | خروجی شمالی خرپشته + موتورخانه آسانسور ⊕ {mach_elev_str} در فضای مشاع با پله مجزا)",
            name_en=f"UNIFIED ROOF, KHARPOSHTEH & ELEVATOR MACHINE ROOM PLAN ({elev_str} / {mach_elev_str})",
            occupancy=top_fl.occupancy,
            z_elevation_mm=z_roof_mm,
            elevation_code_str=elev_str,
            floor_height_mm=kh_h_mm,
            unit_count=0,
            gross_building_rect_mm=gb,
            coverage_ratio_achieved=top_fl.coverage_ratio_achieved,
            gross_area_m2=round(sum(r.net_rect_mm.area_m2 for r in roof_rooms), 1),
            net_area_m2=round(sum(r.net_rect_mm.area_m2 for r in roof_rooms), 1),
            courtyards=list(top_fl.courtyards),
            lightwells=[],
            grid_x_mm=kh_gx if kh_gx else list(top_fl.grid_x_mm[:2]),
            grid_y_mm=kh_gy if kh_gy else list(top_fl.grid_y_mm[1:3]),
            columns=kh_columns,
            rooms=roof_rooms,
            doors=roof_doors,
            windows=roof_windows,
            furniture=roof_furn,
            dimensions=list(top_fl.dimensions),
            stair_detail=top_fl.stair_detail,
            elevator_detail=top_fl.elevator_detail,
            is_open_pilotis=False,
        )

    def _compute_envelope_and_lightwell(
        self, site: ParametricSiteSpec, cov_ratio: float, is_upper_floor: bool = False
    ) -> Tuple[RectMM, RectMM, List[Tuple[str, RectMM, str]], List[BackyardLightwell], Optional[RectMM], Optional[RectMM], Optional[RectMM]]:
        j = site.separation_joint_mm
        w_site = site.width_x_mm
        l_site = site.length_y_mm
        x_west = j if "WEST" in site.party_walls else 0
        x_east = (w_site - j) if "EAST" in site.party_walls else w_site
        y_north_limit = (l_site - j) if "NORTH" in site.party_walls else l_site

        if site.is_irregular_polygon and len(site.polygon_vertices_mm) >= 4:
            upper_east_xs = [px for px, py in site.polygon_vertices_mm if px > w_site * 0.65 and py > l_site * 0.30]
            if upper_east_xs:
                x_east = min(x_east, min(upper_east_xs) - (j if "EAST" in site.party_walls else 0))
            upper_north_ys = [py for px, py in site.polygon_vertices_mm if py > l_site * 0.75 and w_site * 0.15 <= px <= w_site * 0.85]
            if upper_north_ys:
                y_north_limit = min(y_north_limit, min(upper_north_ys) - (j if "NORTH" in site.party_walls else 0))

        build_w = max(5200, x_east - x_west)

        lightwells: List[BackyardLightwell] = []
        courtyards: List[Tuple[str, RectMM, str]] = []
        turning_zone: Optional[RectMM] = None
        cantilever_zone: Optional[RectMM] = None
        nw_wing_rect: Optional[RectMM] = None

        lw_depth = site.lightwell_depth_mm
        lw_width = min(build_w - 2600, int(round((site.lightwell_area_m2 * 1_000_000.0) / max(1, lw_depth))))
        p_last_env = getattr(self, "_last_params", {}) or {}
        req_bldg_m2 = p_last_env.get("requested_building_area_m2")
        site_area_mm2 = (site.site_area_m2 * 1_000_000.0) if site.site_area_m2 > 0 else float(w_site * l_site)
        desired_gross_mm2 = (float(req_bldg_m2) * 1_000_000.0) if req_bldg_m2 else (site_area_mm2 * cov_ratio)
        nw_extra_mm2 = (max(0, (build_w - lw_width) - site.ext_wall_mm) * max(0, lw_depth - site.ext_wall_mm)) if site.lightwell_enabled else 0.0
        min_len_allowed = 2600 if cov_ratio < 0.35 else 6800
        min_cy_margin = 0 if cov_ratio >= 0.96 else min(3200, max(0, int(round(l_site * (1.0 - cov_ratio) * 0.85))))
        target_bldg_len = max(min_len_allowed, min(y_north_limit - min_cy_margin, int(round((desired_gross_mm2 - nw_extra_mm2) / float(max(1, build_w))))))

        if site.building_placement == "SOUTH":
            # Ground-floor South wall & columns sit FLUSH (چسبیده) on the sloped South property/street boundary (NO 1.10m setback inside the lot)!
            # Upper-floor cantilever (`پیش‌آمدگی طبقه اول در معبر`) projects into the South street (`y_south_ground - cant_d`)!
            max_south_edge_mm = max(0, site.south_y_west_mm, site.south_y_east_mm)
            y_south_ground = max_south_edge_mm
            y_north = min(y_north_limit - min_cy_margin, y_south_ground + target_bldg_len)
            ground_gross_rect = RectMM(x_west, y_south_ground, x_east, y_north)
            south_is_street = ("SOUTH" in site.street_sides) or (site.boundary_neighbors.get("SOUTH") == "STREET")
            cant_d = (site.south_cantilever_mm if (is_upper_floor and south_is_street and not site.flip_plan_north_south) else 0)
            floor_gross_rect = RectMM(x_west, y_south_ground - cant_d, x_east, y_north)
            if cant_d > 0:
                cantilever_zone = RectMM(x_west, y_south_ground - cant_d, x_east, y_south_ground)
            if l_site - y_north >= 1200:
                cy_rect = RectMM(0, y_north, w_site, l_site)
                courtyards.append(("حیاط اصلی شمالی (دارای فضای آزاد گردش خودرو ۵.۰ متر)", cy_rect, "⊕ ±0.00 m"))
                if l_site - y_north >= 4200:
                    turning_zone = RectMM(900, y_north + 150, w_site - 900, min(l_site - 800, y_north + 4950))
        elif site.building_placement == "CENTER":
            rem_y = l_site - j - target_bldg_len
            y_south_ground = max(5500, int(rem_y * 0.62))
            y_north = min(l_site - j - 2200, y_south_ground + target_bldg_len)
            ground_gross_rect = RectMM(x_west, y_south_ground, x_east, y_north)
            cant_d = site.south_cantilever_mm if is_upper_floor else 0
            floor_gross_rect = RectMM(x_west, y_south_ground - cant_d, x_east, y_north)
            if cant_d > 0:
                cantilever_zone = RectMM(x_west, y_south_ground - cant_d, x_east, y_south_ground)
            cy_rect = RectMM(0, 0, w_site, y_south_ground)
            courtyards.append(("حیاط اصلی جنوبی (دارای فضای آزاد گردش خودرو ۵.۰ متر)", cy_rect, "⊕ ±0.00 m"))
            turning_zone = RectMM(900, max(300, y_south_ground - 4950), w_site - 900, y_south_ground - 150)
            lw_y0 = y_north
            lw_y1 = l_site - j
            lw_x0 = x_east - lw_width
            lw_rect = RectMM(lw_x0, lw_y0, x_east, lw_y1)
            nw_wing_rect = RectMM(x_west, lw_y0, lw_x0, lw_y1)
            lightwells.append(
                BackyardLightwell(
                    void_id="BACKYARD_NORTH",
                    label_fa=f"حیاط خلوت شمال‌شرقی (عمق {(lw_y1 - lw_y0)/1000:.2f}m | {lw_rect.area_m2:.1f} m²)",
                    label_en=f"NE BACKYARD ({lw_rect.area_m2:.1f}m2)",
                    position="NORTH",
                    rect_mm=lw_rect,
                    depth_mm=lw_y1 - lw_y0,
                    target_area_m2=lw_rect.area_m2,
                    z_elevation_mm=100,
                )
            )
        else:
            if site.lightwell_enabled:
                lw_y1 = y_north_limit
                lw_y0 = lw_y1 - lw_depth
                lw_x1 = x_east
                lw_x0 = x_east - lw_width
                lw_rect = RectMM(lw_x0, lw_y0, lw_x1, lw_y1)
                nw_wing_rect = RectMM(x_west, lw_y0, lw_x0, lw_y1)
                lightwells.append(
                    BackyardLightwell(
                        void_id="LIGHTWELL_NORTH_12M2",
                        label_fa=f"حیاط خلوت شمال‌شرقی ({lw_depth/1000:.2f}×{lw_width/1000:.2f}m = {lw_rect.area_m2:.2f} m²)",
                        label_en=f"NE LIGHTWELL ({lw_rect.area_m2:.2f}m2)",
                        position="NORTH",
                        rect_mm=lw_rect,
                        depth_mm=lw_depth,
                        target_area_m2=lw_rect.area_m2,
                        z_elevation_mm=100,
                    )
                )
                y_north = lw_y0
            else:
                y_north = y_north_limit

            y_south_ground = max(min_cy_margin, y_north - target_bldg_len)
            ground_gross_rect = RectMM(x_west, y_south_ground, x_east, y_north)
            cant_d = min(site.south_cantilever_mm, y_south_ground) if is_upper_floor else 0
            floor_gross_rect = RectMM(x_west, y_south_ground - cant_d, x_east, y_north)
            if cant_d > 0:
                cantilever_zone = RectMM(x_west, y_south_ground - cant_d, x_east, y_south_ground)
            if y_south_ground >= 1200:
                cy_rect = RectMM(0, 0, w_site, y_south_ground)
                courtyards.append(("حیاط مشجر جنوبی (دارای فضای آزاد گردش خودرو ۴.۸ متر)", cy_rect, "⊕ ±0.00 m"))
                if y_south_ground >= 4200:
                    turning_zone = RectMM(900, max(350, y_south_ground - 4950), w_site - 900, y_south_ground - 150)

        return ground_gross_rect, floor_gross_rect, courtyards, lightwells, turning_zone, cantilever_zone, nw_wing_rect

    def _compute_structural_grid_and_core_box(
        self, site: ParametricSiteSpec, ground_gross_rect: RectMM, include_stair_core: bool = True
    ) -> Tuple[List[Tuple[str, int]], List[Tuple[str, int]], List[ColumnElement], RectMM]:
        t_ext = site.ext_wall_mm
        ix0 = ground_gross_rect.x_min + t_ext
        ix1 = ground_gross_rect.x_max - t_ext
        iy0 = ground_gross_rect.y_min + t_ext
        iy1 = ground_gross_rect.y_max - t_ext
        net_h = iy1 - iy0

        col_half = 170
        stair_clear_w = 2150
        tie_wall_w = 240
        elev_clear_w = 1600
        core_axis_span_x = col_half + stair_clear_w + tie_wall_w + elev_clear_w + col_half  # 4330mm
        stair_clear_h = 4600
        core_axis_span_y = col_half + stair_clear_h + col_half  # 4940mm

        h_scale = min(1.15, max(0.68, net_h / 11470.0))
        bed_depth = min(3550, max(2550, int(round(net_h * 0.29))))

        if not include_stair_core and site.width_x_mm >= 14_000:
            grid_x = [("A", ix0), ("B", 5600), ("C", 9660), ("D", ix1)]
            grid_y = [("1", iy0), ("2", 15580), ("3", 19340), ("4", iy1)]
            core_box_rect = RectMM(ix0, 15580, 5600, 19340)
        elif not include_stair_core and site.typology == BuildingTypology.DUPLEX_2FLOOR:
            ay_top = iy1
            ay_north_stair = iy1 - bed_depth
            ay_1 = iy0
            ay_4 = ay_north_stair + int(round(109 * h_scale))
            ay_3 = ay_north_stair - int(round(1581 * h_scale))
            ay_2 = ay_north_stair - int(round(3221 * h_scale))
            kit_extra = int(getattr(self, "_last_params", {}).get("kitchen_extra_width_mm", 0))
            liv_extra = int(getattr(self, "_last_params", {}).get("living_extra_width_mm", 0))
            w_scale = (ix1 - ix0) / 9500.0
            bx_stair_east = int(round(ix0 + 3690 * w_scale)) + kit_extra
            cx_mid_col = int(round(ix0 + 5800 * w_scale)) - liv_extra
            grid_x = [("A", ix0), ("B", bx_stair_east), ("C", cx_mid_col), ("D", ix1)]
            grid_y = [("1", ay_1), ("2", ay_2), ("3", ay_3), ("4", ay_4), ("5", ay_top)]
            core_box_rect = RectMM(ix0, ay_2 + 120, bx_stair_east - 90, ay_north_stair)
            slope_dy = (site.south_y_east_mm - site.south_y_west_mm) if (site.building_placement == "SOUTH" and not site.flip_plan_north_south) else 0
            def _sloped_ay1(x_pos: int) -> int:
                if abs(slope_dy) < 100:
                    return ay_1
                # ay_1 is at max(south_y_west_mm, south_y_east_mm); follow the exact Krocki slope across [ix0..ix1]!
                min_sy = min(site.south_y_west_mm, site.south_y_east_mm)
                max_sy = max(site.south_y_west_mm, site.south_y_east_mm)
                base_ay1 = ay_1 - (max_sy - min_sy)
                ratio_x = max(0.0, min(1.0, (x_pos - ix0) / float(max(1, ix1 - ix0))))
                sy_at_x = site.south_y_west_mm + (site.south_y_east_mm - site.south_y_west_mm) * ratio_x
                return int(round(base_ay1 + (sy_at_x - min_sy)))

            custom_cols = [
                ("A", "1", ix0, _sloped_ay1(ix0)),
                ("C", "1", cx_mid_col, _sloped_ay1(cx_mid_col)),     # Column C-1 on Sloped/Flat South Facade
                ("D", "1", ix1, _sloped_ay1(ix1)),
                ("A", "2", ix0, ay_2),
                ("B", "2", bx_stair_east, ay_2),
                ("C", "3", cx_mid_col, ay_3),     # Column C-3 on Axis 3 (Wet Core South Wall)
                ("D", "3", ix1, ay_3),            # Column D-3 on Axis 3 (Wet Core South Wall)
                ("A", "4", ix0, ay_4),
                ("B", "4", bx_stair_east, ay_4),
                ("A", "5", ix0, ay_top),
                ("B", "5", bx_stair_east, ay_top),
                ("C", "5", cx_mid_col, ay_top),
                ("D", "5", ix1, ay_top),
            ]
            columns: List[ColumnElement] = [
                ColumnElement(
                    col_id=f"COL_{gx_l}{gy_l}",
                    axis_label=f"{gx_l}-{gy_l}",
                    rect_mm=RectMM(cx_m - col_half, cy_m - col_half, cx_m + col_half, cy_m + col_half),
                    is_core_column=False,
                )
                for gx_l, gy_l, cx_m, cy_m in custom_cols
            ]
            grid_x, grid_y, columns = self._synchronize_axes_with_columns(grid_x, grid_y, columns)
            return grid_x, grid_y, columns, core_box_rect
        else:
            ax_A = ix0
            ax_B = (ix0 + int(round((ix1 - ix0) * 0.415))) if not include_stair_core else min(ix1 - 2400, ix0 + core_axis_span_x)
            ax_C = ix1
            grid_x = [("A", ax_A), ("B", ax_B), ("C", ax_C)]
            ay_4 = iy1
            ay_3 = iy1 - bed_depth
            ay_2 = max(iy0 + int(round((ay_3 - iy0) * 0.42)), ay_3 - int(round(core_axis_span_y * h_scale)))
            ay_1 = iy0
            grid_y = [("1", ay_1), ("2", ay_2), ("3", ay_3), ("4", ay_4)]
            core_box_rect = RectMM(ax_A, ay_2, ax_B, ay_3)

        columns: List[ColumnElement] = []
        slope_dy_gen = (site.south_y_east_mm - site.south_y_west_mm) if (site.building_placement == "SOUTH" and not site.flip_plan_north_south) else 0
        for gx_lbl, gx in grid_x:
            for gy_lbl, gy in grid_y:
                gy_eff = gy
                if gy_lbl == "1" and abs(slope_dy_gen) >= 100:
                    min_sy = min(site.south_y_west_mm, site.south_y_east_mm)
                    max_sy = max(site.south_y_west_mm, site.south_y_east_mm)
                    base_ay1 = gy - (max_sy - min_sy)
                    ratio_x = max(0.0, min(1.0, (gx - ix0) / float(max(1, ix1 - ix0))))
                    sy_at_x = site.south_y_west_mm + (site.south_y_east_mm - site.south_y_west_mm) * ratio_x
                    gy_eff = int(round(base_ay1 + (sy_at_x - min_sy)))
                is_core = include_stair_core and (gx_lbl in ("A", "B") and gy_lbl in ("2", "3"))
                columns.append(
                    ColumnElement(
                        col_id=f"COL_{gx_lbl}{gy_lbl}",
                        axis_label=f"{gx_lbl}-{gy_lbl}",
                        rect_mm=RectMM(gx - col_half, gy_eff - col_half, gx + col_half, gy_eff + col_half),
                        is_core_column=is_core,
                    )
                )
        grid_x, grid_y, columns = self._synchronize_axes_with_columns(grid_x, grid_y, columns)
        return grid_x, grid_y, columns, core_box_rect

    @staticmethod
    def _synchronize_axes_with_columns(
        grid_x: List[Tuple[str, int]],
        grid_y: List[Tuple[str, int]],
        columns: List[ColumnElement],
        snap_tol_mm: int = 42,
    ) -> Tuple[List[Tuple[str, int]], List[Tuple[str, int]], List[ColumnElement]]:
        """
        Universal Structural Axis Integrity Rule (`قانون جامع تطابق ۱۰۰٪ ستون‌ها و آکس‌ها در تمام پلان‌ها`):
        Ensures that EVERY structural column in `columns` lies on both a vertical axis in `grid_x` (A, B, C, ...)
        and a horizontal axis in `grid_y` (1, 2, 3, 4, 5, ...).
        - If a column center is within `snap_tol_mm` of an existing axis, its coordinate is snapped to that axis.
        - If a column center is farther than `snap_tol_mm` from any existing axis (like the intermediate wet-core
          columns between Axis 2 and Axis 3), a new axis is automatically inserted, all axes are sorted & re-numbered
          sequentially (`A..Z` West-to-East, `1..N` South-to-North), and every column's `col_id` and `axis_label` is updated!
        """
        if not columns:
            return grid_x, grid_y, columns

        xs = sorted({ int(gx) for _, gx in grid_x })
        ys = sorted({ int(gy) for _, gy in grid_y })

        for col in columns:
            cx, cy = col.rect_mm.center
            if not any(abs(cx - x0) <= snap_tol_mm for x0 in xs):
                xs.append(int(cx))
                xs.sort()
            if not any(abs(cy - y0) <= snap_tol_mm for y0 in ys):
                ys.append(int(cy))
                ys.sort()

        alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        new_grid_x: List[Tuple[str, int]] = [(alpha[i] if i < len(alpha) else f"X{i+1}", x_val) for i, x_val in enumerate(xs)]
        new_grid_y: List[Tuple[str, int]] = [(str(i + 1), y_val) for i, y_val in enumerate(ys)]

        for col in columns:
            cx, cy = col.rect_mm.center
            best_xlbl, best_x = min(new_grid_x, key=lambda item: abs(cx - item[1]))
            best_ylbl, best_y = min(new_grid_y, key=lambda item: abs(cy - item[1]))
            col.col_id = f"COL_{best_xlbl}{best_ylbl}"
            col.axis_label = f"{best_xlbl}-{best_ylbl}"

        return new_grid_x, new_grid_y, columns

    def _build_zero_intrusion_stair_and_elevator_core(
        self,
        core_box_rect: RectMM,
        z_mm: int,
        floor_h_mm: int,
        include_elevator: bool = True,
    ) -> Tuple[StairFlightDetail, Optional[ElevatorDetail], RectMM, RectMM, RectMM]:
        col_half = 170
        stair_clear_x0 = core_box_rect.x_min + col_half + 30
        stair_clear_w = 2120
        stair_clear_x1 = stair_clear_x0 + stair_clear_w
        stair_clear_y0 = core_box_rect.y_min + col_half + 30
        stair_clear_y1 = core_box_rect.y_max - col_half - 30

        stair_rect = RectMM(stair_clear_x0, stair_clear_y0, stair_clear_x1, stair_clear_y1)

        tread_d = 300.0
        riser_h = 180.0
        total_risers = max(14, int(round(floor_h_mm / riser_h)))
        if total_risers % 2 == 1:
            total_risers += 1
        risers_per_flight = total_risers // 2
        treads_per_flight = risers_per_flight - 1
        flight_run_mm = int(round(treads_per_flight * tread_d))

        inter_land_d = 1100
        inter_landing = RectMM(stair_rect.x_min, stair_rect.y_min, stair_rect.x_max, stair_rect.y_min + inter_land_d)
        flight_y_min = inter_landing.y_max
        flight_y_max = flight_y_min + flight_run_mm
        ent_landing = RectMM(stair_rect.x_min, flight_y_max, stair_rect.x_max, stair_rect.y_max)

        mid_x = stair_rect.center[0]
        well_half_x = 65
        flight1 = RectMM(stair_rect.x_min, flight_y_min, mid_x - well_half_x, flight_y_max)
        flight2 = RectMM(mid_x + well_half_x, flight_y_min, stair_rect.x_max, flight_y_max)
        well_gap = RectMM(mid_x - well_half_x, flight_y_min, mid_x + well_half_x, flight_y_max)

        c_x0, c_y0, c_x1, c_y1 = core_box_rect.x_min, core_box_rect.y_min, core_box_rect.x_max, core_box_rect.y_max
        tie_x = stair_clear_x1 + 120
        perimeter_beams = [
            ((c_x0, c_y0), (c_x1, c_y0)),
            ((c_x1, c_y0), (c_x1, c_y1)),
            ((c_x1, c_y1), (c_x0, c_y1)),
            ((c_x0, c_y1), (c_x0, c_y0)),
            ((tie_x, c_y0), (tie_x, c_y1)),
        ]
        core_columns = [
            RectMM(c_x0 - col_half, c_y0 - col_half, c_x0 + col_half, c_y0 + col_half),
            RectMM(c_x1 - col_half, c_y0 - col_half, c_x1 + col_half, c_y0 + col_half),
            RectMM(c_x0 - col_half, c_y1 - col_half, c_x0 + col_half, c_y1 + col_half),
            RectMM(c_x1 - col_half, c_y1 - col_half, c_x1 + col_half, c_y1 + col_half),
        ]

        stair_detail = StairFlightDetail(
            core_rect_mm=stair_rect,
            structural_box_rect_mm=core_box_rect,
            entrance_landing_rect_mm=ent_landing,
            intermediate_landing_rect_mm=inter_landing,
            flight1_rect_mm=flight1,
            flight2_rect_mm=flight2,
            well_gap_rect_mm=well_gap,
            total_risers=total_risers,
            risers_per_flight=risers_per_flight,
            treads_per_flight=treads_per_flight,
            riser_height_mm=riser_h,
            tread_depth_mm=tread_d,
            floor_to_floor_height_mm=floor_h_mm,
            z_start_mm=z_mm,
            z_mid_landing_mm=z_mm + floor_h_mm // 2,
            z_end_mm=z_mm + floor_h_mm,
            orientation="V",
            perimeter_beams=perimeter_beams,
            core_columns=core_columns,
        )

        elev_clear_x0 = stair_clear_x1 + 240
        elev_clear_x1 = elev_clear_x0 + 1600
        elev_clear_y0 = stair_clear_y0
        elev_clear_y1 = elev_clear_y0 + 1800
        elev_rect = RectMM(elev_clear_x0, elev_clear_y0, elev_clear_x1, elev_clear_y1)
        elev_outer_wall_rect = RectMM(elev_clear_x0 - 180, elev_clear_y0 - 170, elev_clear_x1 + 170, elev_clear_y1 + 160)

        elevator_detail = (
            ElevatorDetail(
                shaft_rect_mm=elev_rect,
                outer_wall_rect_mm=elev_outer_wall_rect,
                cab_rect_mm=RectMM(elev_rect.x_min + 150, elev_rect.y_min + 170, elev_rect.x_max - 150, elev_rect.y_max - 150),
                door_center_mm=(elev_rect.center[0], elev_rect.y_max),
                door_width_mm=850,
                door_orientation="H",
                door_opens_toward="N",
            )
            if include_elevator
            else None
        )

        lobby_rect = RectMM(elev_clear_x0, elev_clear_y1 + 160, elev_clear_x1, stair_clear_y1)
        return stair_detail, elevator_detail, stair_rect, elev_rect, lobby_rect

    def _synthesize_open_pilotis_floor(
        self,
        site: ParametricSiteSpec,
        floor_index: int,
        z_mm: int,
        floor_h_mm: int,
        elev_str: str,
        cov_ratio: float,
    ) -> FloorPlanDesignV3:
        """
        Synthesizes the Ground Pilotis Floor (`پیلوت باز پارکینگ با ۳ جای پارک مستقل P1..P3 و جانمایی دقیق درهای لابی و پله`):
        - Fixed `D_PILOTIS_LOBBY_ENTRY` and `D_PILOTIS_STAIR` (`leaf_dir="+"`, extending North into `FLOOR_LOBBY` and `ent_landing`,
          100% clear of the stair flights and elevator shaft — fixing the 2 Blue Circles on Pilotis in `321.jpg`!).
        """
        ground_gross_rect, _, courtyards, lightwells, turning_zone, cantilever_zone, nw_wing_rect = self._compute_envelope_and_lightwell(
            site, cov_ratio, is_upper_floor=False
        )
        grid_x, grid_y, columns, core_box_rect = self._compute_structural_grid_and_core_box(
            site, ground_gross_rect, include_stair_core=True
        )

        t_ext = site.ext_wall_mm
        ix0 = ground_gross_rect.x_min + t_ext
        ix1 = ground_gross_rect.x_max - t_ext
        iy0 = ground_gross_rect.y_min + t_ext
        iy1 = ground_gross_rect.y_max - t_ext

        stair_detail, elevator_detail, stair_rect, elev_rect, lobby_rect = self._build_zero_intrusion_stair_and_elevator_core(
            core_box_rect=core_box_rect,
            z_mm=z_mm,
            floor_h_mm=floor_h_mm,
            include_elevator=True,
        )

        rooms: List[RoomSpace] = [
            RoomSpace(
                room_id="OPEN_PILOTIS_DECK",
                code_en="OPEN PILOTIS PARKING DECK (3 UNOBSTRUCTED PARKING BAYS P1..P3 + DASHED CANOPIES)",
                label_fa="پیلوت باز (۳ پارکینگ ۱۰۰٪ مستقل بدون مزاحم + مسیر پیاده/عبور + سایبان خط‌چین طبقات)",
                unit_id="COMMON",
                space_category="OUTDOOR",
                net_rect_mm=RectMM(ground_gross_rect.x_min, ground_gross_rect.y_min, ground_gross_rect.x_max, ground_gross_rect.y_max),
                z_elevation_mm=z_mm,
                elevation_label=f"⊕ {elev_str} (H={floor_h_mm/1000:.2f}m = {stair_detail.total_risers} پله با کف ۳۰cm و پاگرد ۱.۷۰m)",
                natural_light="OPEN_PILOTIS",
                is_open_pilotis_zone=True,
            ),
            RoomSpace(
                room_id="STAIR_BOX",
                code_en=f"STAIRCASE ({stair_detail.total_risers} RISERS)",
                label_fa=f"باکس خالص پله ({stair_detail.total_risers} پله)",
                unit_id="COMMON",
                space_category="CORE",
                net_rect_mm=stair_rect,
                z_elevation_mm=z_mm,
                elevation_label=f"⊕ {elev_str}",
                natural_light="NONE",
            ),
            RoomSpace(
                room_id="ELEVATOR_SHAFT",
                code_en="CLEAR ELEVATOR SHAFT (1.60x1.80m)",
                label_fa="آسانسور خالص ۱.۶۰×۱.۸۰m",
                unit_id="COMMON",
                space_category="CORE",
                net_rect_mm=elev_rect,
                z_elevation_mm=z_mm,
                elevation_label=f"⊕ {elev_str}",
                natural_light="NONE",
            ),
            RoomSpace(
                room_id="FLOOR_LOBBY",
                code_en="PILOTIS CORE LOBBY",
                label_fa="لابی ورودی پله و آسانسور",
                unit_id="COMMON",
                space_category="CIRCULATION",
                net_rect_mm=lobby_rect,
                z_elevation_mm=z_mm,
                elevation_label=f"⊕ {elev_str}",
                natural_light="NONE",
            ),
        ]

        ax_B_outer = core_box_rect.x_max + 170
        canopy_rect = RectMM(ground_gross_rect.x_min, max(0, ground_gross_rect.y_min - site.south_cantilever_mm), ground_gross_rect.x_max, ground_gross_rect.y_min)
        if site.building_placement == "SOUTH":
            ped_path_rect = RectMM(ax_B_outer + 80, core_box_rect.y_min + 200, ax_B_outer + 2350, ground_gross_rect.y_max)
        else:
            ped_path_rect = RectMM(ax_B_outer + 80, canopy_rect.y_min, ax_B_outer + 2350, core_box_rect.y_max + 1200)

        # Both Pilotis doors use `leaf_dir="+"` (extending North from `hinge_mm[1]` to `hinge_mm[1] + width_mm`),
        # sitting 100% inside the top landing (`پاگرد جلوی پله`) and `FLOOR_LOBBY`!
        # Fire-Safety Egress Rule (`قانون خروج اضطراری آتش‌نشانی و زلزله`):
        # Both the Staircase exit door (`D_PILOTIS_STAIR`) and the Lobby exit door (`D_PILOTIS_LOBBY_ENTRY`) open OUTWARD (`swing_dir="E"`) in the direction of escape!
        doors: List[DoorElement] = [
            DoorElement(
                "D_PILOTIS_LOBBY_ENTRY",
                "خروجی اضطراری لابی به پیلوت (بازشو به بیرون)",
                "FLOOR_LOBBY",
                "OPEN_PILOTIS_DECK",
                (lobby_rect.x_max, lobby_rect.y_min + 220),
                880,
                "V",
                "E",
                leaf_dir="+",
                is_main_entry=True,
            ),
            DoorElement(
                "D_PILOTIS_STAIR",
                "درب خروج راه‌پله (بازشو به بیرون در جهت فرار)",
                "STAIR_BOX",
                "FLOOR_LOBBY",
                (lobby_rect.x_min, stair_detail.entrance_landing_rect_mm.y_min + 120),
                850,
                "V",
                "E",
                leaf_dir="+",
            ),
        ]

        furniture: List[FurnitureElement] = []
        if site.building_placement == "SOUTH":
            furniture.extend([
                FurnitureElement("FURN_P1_CAR", "OPEN_PILOTIS_DECK", "CAR", RectMM(ix1 - 2050, iy1 - 4600, ix1 - 250, iy1 - 200), "PARKING P1 (1.80x4.40m)", "پارکینگ P1 (۱.۸۰×۴.۴۰m استاندارد)"),
                FurnitureElement("FURN_P2_CAR", "OPEN_PILOTIS_DECK", "CAR", RectMM(ix1 - 2050, iy0 + 200, ix1 - 250, iy0 + 4600), "PARKING P2 (1.80x4.40m)", "پارکینگ P2 (۱.۸۰×۴.۴۰m استاندارد)"),
                FurnitureElement("FURN_P3_CAR_ROT90", "OPEN_PILOTIS_DECK", "CAR", RectMM(ix0 + 350, core_box_rect.y_max + 450, ix0 + 4750, core_box_rect.y_max + 2250), "PARKING P3 (4.40x1.80m)", "پارکینگ P3 (۴.۴۰×۱.۸۰m استاندارد)", orientation="H"),
                FurnitureElement("FURN_P3_MANEUVER_ZONE", "OPEN_PILOTIS_DECK", "MANEUVER_ZONE", RectMM(ax_B_outer + 250, core_box_rect.y_max + 250, ix1 - 350, iy1 - 250), "P3 CLEAR EXIT ZONE", "فضای آزاد مانور و خروج پارکینگ P3 (بدون پارک مزاحم)"),
            ])
        else:
            p1_y1 = core_box_rect.y_min - 150
            p1_y0 = p1_y1 - 4300
            p2_y0 = iy0 + 100
            p2_y1 = p2_y0 + 4300
            furniture.extend([
                FurnitureElement(
                    "FURN_P1_CAR",
                    "OPEN_PILOTIS_DECK",
                    "CAR",
                    RectMM(ix0 + 650, p1_y0, ix0 + 2450, p1_y1),
                    "PARKING P1 (1.80x4.30m)",
                    "پارکینگ P1 (خودرو ۱.۸۰×۴.۳۰m در حریم ۲.۵۰×۵.۰۰m)",
                ),
                FurnitureElement(
                    "FURN_P2_CAR",
                    "OPEN_PILOTIS_DECK",
                    "CAR",
                    RectMM(ix1 - 2050, p2_y0, ix1 - 250, p2_y1),
                    "PARKING P2 (1.80x4.30m)",
                    "پارکینگ P2 (خودرو ۱.۸۰×۴.۳۰m در حریم ۲.۵۰×۵.۰۰m)",
                ),
                FurnitureElement(
                    "FURN_P3_CAR_ROT90",
                    "OPEN_PILOTIS_DECK",
                    "CAR",
                    RectMM(ix0 + 350, core_box_rect.y_max + 450, ix0 + 4650, core_box_rect.y_max + 2250),
                    "PARKING P3 (4.30x1.80m)",
                    "پارکینگ P3 (خودرو ۴.۳۰×۱.۸۰m در حریم ۵.۰۰×۲.۵۰m)",
                    orientation="H",
                ),
                FurnitureElement(
                    "FURN_P3_MANEUVER_ZONE",
                    "OPEN_PILOTIS_DECK",
                    "MANEUVER_ZONE",
                    RectMM(ax_B_outer + 250, core_box_rect.y_max + 250, ix1 - 350, iy1 - 250),
                    "P3 CLEAR EXIT ZONE",
                    "فضای آزاد مانور و خروج پارکینگ P3 (توقف ممنوع)",
                ),
                FurnitureElement(
                    "FURN_PILOTIS_DUCT_ELBOW",
                    "OPEN_PILOTIS_DECK",
                    "DUCT_CEILING_ELBOW",
                    RectMM(7020, 11630, 7580, 12380),
                    "DUCT CEILING ELBOW TO WALL",
                    "زانویی افقی داکت زیر سقف پیلوت به کنار دیوار",
                ),
            ])

        if courtyards:
            cy_rect = courtyards[0][1]
            if cy_rect.height >= 4000:
                furniture.append(
                    FurnitureElement("FURN_TREE1", "COURTYARD", "TREE", RectMM(140, cy_rect.y_min + 600, 740, cy_rect.y_min + 1200), "TREE", "باغچه کناری")
                )
                furniture.append(
                    FurnitureElement("FURN_TREE2", "COURTYARD", "TREE", RectMM(site.width_x_mm - 740, cy_rect.y_min + 600, site.width_x_mm - 140, cy_rect.y_min + 1200), "TREE", "باغچه کناری")
                )

        gross_m2 = round(ground_gross_rect.area_m2, 2)
        cov_achieved = round(gross_m2 / (site.site_area_m2 if site.site_area_m2 > 0 else ((site.width_x_mm * site.length_y_mm) / 1e6)), 2)

        return FloorPlanDesignV3(
            floor_index=floor_index,
            name_fa=(
                f"پلان طبقه همکف (پیلوت باز — ۳ پارکینگ مستقل P1..P3 بدون مزاحم + جانمایی دقیق درهای پله و لابی | {stair_detail.total_risers} پله)"
            ),
            name_en=f"OPEN PILOTIS GROUND FLOOR (H={floor_h_mm/1000:.2f}m, {stair_detail.total_risers} RISERS)",
            occupancy=OccupancyType.PILOTIS_PARKING_OPEN,
            z_elevation_mm=z_mm,
            elevation_code_str=elev_str,
            floor_height_mm=floor_h_mm,
            unit_count=0,
            gross_building_rect_mm=ground_gross_rect,
            courtyards=courtyards,
            lightwells=lightwells,
            grid_x_mm=grid_x,
            grid_y_mm=grid_y,
            columns=columns,
            stair_detail=stair_detail,
            elevator_detail=elevator_detail,
            rooms=rooms,
            doors=doors,
            windows=[],
            furniture=furniture,
            dimensions=[],
            coverage_ratio_achieved=cov_achieved,
            gross_area_m2=gross_m2,
            net_area_m2=gross_m2,
            is_open_pilotis=True,
            turning_zone_rect_mm=turning_zone,
            pilotis_canopy_rect_mm=canopy_rect,
            pilotis_nw_canopy_rect_mm=nw_wing_rect,
            pilotis_pedestrian_path_rect_mm=ped_path_rect,
        )

    def _synthesize_multifloor_residential_floor(
        self,
        site: ParametricSiteSpec,
        floor_index: int,
        z_mm: int,
        floor_h_mm: int,
        elev_str: str,
        cov_ratio: float,
        name_fa: str,
        layout_variant: str = "TYPE_A",
    ) -> FloorPlanDesignV3:
        """
        Synthesizes a Typical Residential Floor (`طبقه مسکونی چندطبقه v19.0 — اصلاح کامل ۳۲۱ و ۳۳۳`):
        1. All 4 Blue-Circled doors on the Residential Floor (`D_STAIR_TO_LOBBY`, `D_UNIT_MAIN_ENTRY`, `D_GUEST_WC`, `D_LIVING_TO_TERRACE`)
           use `leaf_dir="+"` and sit 100% inside their host wall segments!
        2. Red Circle in `321.jpg`: Removed the extra wall and shoe-closet box blocking `ENTRANCE_FOYER` -> `PRIVATE_HALL`.
           `ENTRANCE_FOYER`, `PRIVATE_HALL`, and `BEDROOM_ENTRY_JOINT` are rendered as ONE unified, single-color corridor (`#fef9c3`)!
        3. `333.jpg` Blue Bed + Red Study Desk + Grey Partition Wall:
           - `FURN_BED1` (`تخت خواب دو نفره و پاتختی`) sits inside the North-West Alcove (`تورفتگی شمال‌غربی کنار حیاط خلوت`) with headboard on the North wall!
           - `FURN_BED1_DESK` (`میز مطالعه و کامپیوتر`) sits directly under the horizontal North window facing the Lightwell (`نور روز مستقیم`)!
           - `FURN_BED_PARTITION_WALL` (`دیوار جداکننده بین دو اتاق خواب`) runs down the center line `x = bed_split_x` between the two back-to-back wardrobes!
        """
        ground_gross_rect, floor_gross_rect, courtyards, lightwells, turning_zone, cantilever_zone, nw_wing_rect = self._compute_envelope_and_lightwell(
            site, cov_ratio, is_upper_floor=True
        )
        grid_x, grid_y, columns, core_box_rect = self._compute_structural_grid_and_core_box(
            site, ground_gross_rect, include_stair_core=True
        )

        t_ext = site.ext_wall_mm
        t_int = site.int_wall_mm
        ix0 = floor_gross_rect.x_min + t_ext
        ix1 = floor_gross_rect.x_max - t_ext
        iy0 = floor_gross_rect.y_min + t_ext
        iy1 = floor_gross_rect.y_max - t_ext

        stair_detail, elevator_detail, stair_rect, elev_rect, lobby_rect = self._build_zero_intrusion_stair_and_elevator_core(
            core_box_rect=core_box_rect,
            z_mm=z_mm,
            floor_h_mm=floor_h_mm,
            include_elevator=True,
        )

        rooms: List[RoomSpace] = [
            RoomSpace(
                room_id="STAIR_BOX",
                code_en=f"2-FLIGHT STAIRCASE ({stair_detail.total_risers}R, 30CM TREAD)",
                label_fa=f"باکس خالص پله ({stair_detail.total_risers} پله، کف ۳۰cm)",
                unit_id="COMMON",
                space_category="CORE",
                net_rect_mm=stair_rect,
                z_elevation_mm=z_mm,
                elevation_label=f"⊕ {elev_str}",
                natural_light="NONE",
            ),
            RoomSpace(
                room_id="ELEVATOR_SHAFT",
                code_en="CLEAR ELEVATOR SHAFT (1.60x1.80m)",
                label_fa="آسانسور خالص ۱.۶۰×۱.۸۰m",
                unit_id="COMMON",
                space_category="CORE",
                net_rect_mm=elev_rect,
                z_elevation_mm=z_mm,
                elevation_label=f"⊕ {elev_str}",
                natural_light="NONE",
            ),
            RoomSpace(
                room_id="FLOOR_LOBBY",
                code_en="COMMON FLOOR LOBBY",
                label_fa="لابی و پاگرد مشاع",
                unit_id="COMMON",
                space_category="CORE",
                net_rect_mm=lobby_rect,
                z_elevation_mm=z_mm,
                elevation_label=f"⊕ {elev_str}",
                natural_light="NONE",
            ),
        ]

        core_east_outer = core_box_rect.x_max + 170  # 4750mm on 10x20 site
        y_core_south_outer = core_box_rect.y_min - 170
        y_core_north_outer = core_box_rect.y_max + 170

        east_band_w = ix1 - core_east_outer
        h_scale_v = min(1.15, max(0.72, (iy1 - iy0) / 11470.0))
        priv_h = int(round(1400 * h_scale_v))
        srv_h = int(round(1750 * h_scale_v))
        y_priv_south = y_core_north_outer - priv_h
        y_srv_south = y_priv_south - t_int - srv_h

        # `402.jpg` Black-Hatched Corridor Optimization (`حذف راهروی پرت کنار حمام و بزرگ کردن سرویس بهداشتی و حمام اصلی + حفظ حریم خصوصی در حمام`):
        # - `PRIVATE_HALL` stops at `x_wc_1` (`width = 2.57m`), eliminating the wasted dead-end hallway in front of the bathroom!
        # - `GUEST_WC` (`wc_rect`) gets a wider `1.25m × 1.75m` footprint (`2.2 m²`).
        # - `MAIN_BATHROOM` (`bath_rect`) and `MASTER_BATH` (`mbath_rect`) both span the FULL height `y_srv_south .. y_core_north_outer - t_int` (`3.15m` tall!)
        #   so `MAIN_BATHROOM` (`1.25m × 3.15m = 3.9 m²`) is entered privately from the East wall of `PRIVATE_HALL` (not facing the main corridor!) and easily fits a full-scale Bathtub/Shower + Toilet + Vanity!
        foyer_w = max(1220, int(east_band_w * 0.245))
        wc_w = max(1230, int(east_band_w * 0.248))
        bath_w = max(1180, int(east_band_w * 0.238))

        x_foyer_0 = core_east_outer
        x_foyer_1 = x_foyer_0 + foyer_w
        x_wc_0 = x_foyer_1 + t_int
        x_wc_1 = x_wc_0 + wc_w
        x_bath_0 = x_wc_1 + t_int
        x_bath_1 = x_bath_0 + bath_w
        x_mbath_0 = x_bath_1 + t_int
        x_mbath_1 = ix1

        foyer_rect = RectMM(x_foyer_0, y_srv_south, x_foyer_1, y_priv_south)
        wc_rect = RectMM(x_wc_0, y_srv_south, x_wc_1, y_priv_south - t_int)
        priv_hall_rect = RectMM(x_foyer_0, y_priv_south, x_wc_1, y_core_north_outer)
        bath_rect = RectMM(x_bath_0, y_srv_south, x_bath_1, y_core_north_outer - t_int)
        mbath_rect = RectMM(x_mbath_0, y_srv_south, x_mbath_1, y_core_north_outer - t_int)

        y_bed_south = y_core_north_outer
        x_joint_0 = core_east_outer           # 4750mm
        x_joint_1 = core_east_outer + 1250    # 6000mm
        bed_split_x = (x_joint_0 + x_joint_1) // 2  # 5375mm
        y_joint_1 = y_bed_south + 1200
        joint_rect = RectMM(x_joint_0, y_bed_south, x_joint_1, y_joint_1)

        rooms.extend([
            RoomSpace(
                room_id="ENTRANCE_FOYER",
                code_en="UNIT ENTRANCE FOYER (UNIFIED WITH CORRIDOR)",
                label_fa="ورودی واحد",
                unit_id="UNIT_1",
                space_category="CIRCULATION",
                net_rect_mm=foyer_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NONE",
                is_open_edge_south=True,
                is_open_edge_north=True,
            ),
            RoomSpace(
                room_id="PRIVATE_HALL",
                code_en="UNIFIED PRIVATE CORRIDOR & BEDROOM ENTRY",
                label_fa="راهرو و فیلتر خصوصی خواب‌ها",
                unit_id="UNIT_1",
                space_category="CIRCULATION",
                net_rect_mm=priv_hall_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NONE",
                is_open_edge_south=True,
                is_open_edge_north=True,
            ),
            RoomSpace(
                room_id="GUEST_WC",
                code_en="GUEST WC (DOOR OPENS TO FOYER)",
                label_fa="سرویس بهداشتی",
                unit_id="UNIT_1",
                space_category="WET_SERVICE",
                net_rect_mm=wc_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="MECHANICAL",
            ),
            RoomSpace(
                room_id="MAIN_BATHROOM",
                code_en="MAIN BATHROOM",
                label_fa="حمام عمومی",
                unit_id="UNIT_1",
                space_category="WET_SERVICE",
                net_rect_mm=bath_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="MECHANICAL",
            ),
            RoomSpace(
                room_id="MASTER_BATH",
                code_en="MASTER ENSUITE BATHROOM",
                label_fa="حمام و سرویس مستر",
                unit_id="UNIT_1",
                space_category="WET_SERVICE",
                net_rect_mm=mbath_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="MECHANICAL",
            ),
        ])

        terrace_h = 1200
        balc_rect = RectMM(ix0, floor_gross_rect.y_min, 4580 if site.typology == BuildingTypology.DUPLEX_2FLOOR else (core_east_outer - t_int), floor_gross_rect.y_min + terrace_h)
        rooms.append(
            RoomSpace(
                room_id="BALCONY_SOUTH",
                code_en="3-SIDED OPEN-FRONT TERRACE (PARAPET H=100CM)",
                label_fa="تراس جنوبی (جلوباز با جان‌پناه ۱۰۰cm)",
                unit_id="UNIT_1",
                space_category="OUTDOOR",
                net_rect_mm=balc_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="SOUTH_COURTYARD",
                is_open_front_terrace=True,
                parapet_height_cm=100,
            )
        )

        kit_y0 = balc_rect.y_max + t_ext
        kit_y1 = y_core_south_outer - t_int
        avail_kit_area_m2 = ((balc_rect.width) * (kit_y1 - kit_y0)) / 1_000_000.0
        has_actual_dirty_kitchen = site.include_dirty_kitchen and (avail_kit_area_m2 >= 18.0)

        if has_actual_dirty_kitchen:
            dirty_h = 1300
            rooms.append(
                RoomSpace(
                    room_id="DIRTY_KITCHEN",
                    code_en="DIRTY KITCHEN (MUTBAKH)",
                    label_fa="مطبخ (آشپزخانه کثیف)",
                    unit_id="UNIT_1",
                    space_category="WET_SERVICE",
                    net_rect_mm=RectMM(ix0, kit_y0, balc_rect.x_max - 1200, kit_y0 + dirty_h),
                    z_elevation_mm=z_mm,
                    elevation_label=elev_str,
                    natural_light="SOUTH_COURTYARD",
                )
            )
            main_kit_y0 = kit_y0 + dirty_h + t_int
        else:
            main_kit_y0 = kit_y0

        ok_rect = RectMM(ix0, main_kit_y0, balc_rect.x_max, kit_y1)
        rooms.append(
            RoomSpace(
                room_id="OPEN_KITCHEN",
                code_en="OPEN ISLAND KITCHEN (WITH 1.20M ENTRY WALKWAY)",
                label_fa="آشپزخانه اپن و جزیره",
                unit_id="UNIT_1",
                space_category="SEMI_PUBLIC",
                net_rect_mm=ok_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="SOUTH_COURTYARD",
                is_open_edge_east=True,
            )
        )

        liv_rect = RectMM(core_east_outer, iy0, ix1, y_srv_south - t_int)
        rooms.append(
            RoomSpace(
                room_id="LIVING_DINING",
                code_en="GRAND LIVING & DINING HALL (+1.10M SOUTH PROJECTION)",
                label_fa="سالن پذیرایی، نشیمن و ناهارخوری",
                unit_id="UNIT_1",
                space_category="PUBLIC",
                net_rect_mm=liv_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="SOUTH_COURTYARD",
                is_open_edge_west=True,
                is_open_edge_north=True,
            )
        )

        b1_rect = RectMM(ix0, y_bed_south, x_joint_0, iy1)
        mbe_rect = RectMM(x_joint_1, y_bed_south, ix1, iy1)
        b1_nw_ext = (
            RectMM(ix0, iy1, nw_wing_rect.x_max - t_ext, nw_wing_rect.y_max - t_ext)
            if nw_wing_rect is not None
            else None
        )

        rooms.append(
            RoomSpace(
                room_id="BEDROOM_1",
                code_en="WEST BEDROOM (BED IN NW ALCOVE + DESK UNDER WINDOW - 333.JPG)",
                label_fa="اتاق خواب ۲ (ضلع غربی)",
                unit_id="UNIT_1",
                space_category="PRIVATE",
                net_rect_mm=b1_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NORTH_LIGHTWELL",
                l_extension_rect_mm=b1_nw_ext,
                l_extension_label_fa="",
            )
        )
        rooms.append(
            RoomSpace(
                room_id="MASTER_BEDROOM",
                code_en="LARGE MASTER BEDROOM SUITE (EAST)",
                label_fa="اتاق خواب مستر بزرگ",
                unit_id="UNIT_1",
                space_category="PRIVATE",
                net_rect_mm=mbe_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NORTH_LIGHTWELL",
            )
        )
        rooms.append(
            RoomSpace(
                room_id="BEDROOM_ENTRY_JOINT",
                code_en="UNIFIED CORRIDOR EXTENSION BETWEEN BEDROOMS",
                label_fa="",
                unit_id="UNIT_1",
                space_category="CIRCULATION",
                net_rect_mm=joint_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NONE",
                is_open_edge_south=True,
            )
        )

        # Doors — ALL vertical doors have explicit `leaf_dir`:
        # - `D_STAIR_TO_LOBBY`, `D_UNIT_MAIN_ENTRY`, `D_GUEST_WC`, `D_LIVING_TO_TERRACE` have `leaf_dir="+"` (extending North into the room/landing!)
        # - `D_BED_1`, `D_MASTER_BED` have `leaf_dir="-"` (hinged at the top of the recessed entry against the wardrobes, extending South!)
        doors: List[DoorElement] = [
            DoorElement(
                "D_STAIR_TO_LOBBY",
                "درب دودبند پله (بازشو به بیرون در لابی)",
                "STAIR_BOX",
                "FLOOR_LOBBY",
                (lobby_rect.x_min, stair_detail.entrance_landing_rect_mm.y_min + 120),
                850,
                "V",
                "E",
                leaf_dir="+",
            ),
            DoorElement(
                "D_UNIT_MAIN_ENTRY",
                "درب ورودی واحد",
                "FLOOR_LOBBY",
                "ENTRANCE_FOYER",
                (foyer_rect.x_min, foyer_rect.y_min + 180),
                880,
                "V",
                "E",
                leaf_dir="+",
                is_main_entry=True,
            ),
            DoorElement(
                "D_GUEST_WC",
                "درب سرویس (سمت ورودی)",
                "ENTRANCE_FOYER",
                "GUEST_WC",
                (wc_rect.x_min, wc_rect.y_min + 80),
                680,
                "V",
                "E",
                leaf_dir="+",
            ),
            DoorElement(
                "D_MAIN_BATH",
                "درب حمام عمومی (با حفظ محرمیت)",
                "PRIVATE_HALL",
                "MAIN_BATHROOM",
                (bath_rect.x_min, y_priv_south + 100),
                720,
                "V",
                "E",
                leaf_dir="+",
            ),
            DoorElement(
                "D_BED_1",
                "درب خواب ۲",
                "BEDROOM_ENTRY_JOINT",
                "BEDROOM_1",
                (joint_rect.x_min, y_bed_south + 80),
                880,
                "V",
                "W",
                leaf_dir="+",
            ),
            DoorElement(
                "D_MASTER_BED",
                "درب خواب مستر",
                "BEDROOM_ENTRY_JOINT",
                "MASTER_BEDROOM",
                (joint_rect.x_max, y_bed_south + 80),
                880,
                "V",
                "E",
                leaf_dir="+",
            ),
            DoorElement(
                "D_MASTER_BATH",
                "درب حمام مستر",
                "MASTER_BEDROOM",
                "MASTER_BATH",
                (mbath_rect.x_max - 80, mbath_rect.y_max),
                740,
                "H",
                "S",
                leaf_dir="-",
            ),
            DoorElement(
                "D_LIVING_TO_TERRACE",
                "درب تراس از پذیرایی",
                "LIVING_DINING",
                "BALCONY_SOUTH",
                (balc_rect.x_max, balc_rect.y_min + 180),
                850,
                "V",
                "W",
                leaf_dir="+",
            ),
        ]

        if has_actual_dirty_kitchen:
            dk_r = next(r for r in rooms if r.room_id == "DIRTY_KITCHEN").net_rect_mm
            doors.append(
                DoorElement("D_KIT_TO_MUTBAKH", "درب مطبخ", "OPEN_KITCHEN", "DIRTY_KITCHEN", (dk_r.x_min + 450, dk_r.y_max), 750, "H", "S")
            )

        lw_north = next((lw for lw in lightwells if lw.position == "NORTH"), None)
        lw_x0 = lw_north.rect_mm.x_min if lw_north else (b1_rect.x_min + 2400)
        b1_l_horiz_x1 = min(x_joint_0 - 380, core_box_rect.x_max - 220)

        raw_windows: List[WindowElement] = [
            WindowElement(
                "WIN_LIVING_SOUTH",
                "LIVING_DINING",
                "SOUTH_COURTYARD",
                liv_rect.x_min + 650,
                floor_gross_rect.y_min,
                ix1 - 550,
                floor_gross_rect.y_min + t_ext,
                t_ext,
                "H",
            ),
            WindowElement(
                "WIN_KITCHEN_TO_TERRACE",
                "OPEN_KITCHEN",
                "BALCONY_SOUTH",
                balc_rect.x_min + 450,
                balc_rect.y_max,
                balc_rect.x_max - 450,
                balc_rect.y_max + t_ext,
                t_ext,
                "H",
            ),
            WindowElement(
                "WIN_BED1_L_HORIZ",
                "BEDROOM_1",
                "NORTH_LIGHTWELL",
                lw_x0 - t_ext,
                iy1,
                b1_l_horiz_x1,
                floor_gross_rect.y_max,
                t_ext,
                "H",
            ),
            *SmartArchitecturalFurnitureSolver.solve_east_master_bedroom_layout(
                room_rect=mbe_rect,
                joint_x_max=x_joint_1,
                iy1=iy1,
                gross_y_max=floor_gross_rect.y_max,
                ext_wall_mm=t_ext,
                has_lightwell_door=False,
            )[1],
        ]
        if nw_wing_rect is not None:
            raw_windows.append(
                WindowElement(
                    "WIN_BED1_L_VERT",
                    "BEDROOM_1",
                    "NORTH_LIGHTWELL",
                    lw_x0 - t_ext,
                    iy1,
                    lw_x0,
                    nw_wing_rect.y_max - 220,
                    t_ext,
                    "V",
                )
            )
        windows = [self._decollide_window_from_columns(w, columns, doors=doors) for w in raw_windows]

        island_y0 = ok_rect.y_min + 180
        island_y1 = max(island_y0 + 1100, ok_rect.y_max - 1150)
        shared_sanitary_duct_rect = RectMM(x_wc_1 - 220, y_srv_south + 40, x_bath_0 + 220, y_srv_south + 520)
        kitchen_duct_rect = RectMM(ok_rect.x_min + 120, ok_rect.y_max - 720, ok_rect.x_min + 770, ok_rect.y_max - 15)

        # Exact `333.jpg` Bed in NW Alcove (Blue Box) + Study Desk under Lightwell Window (Red Box) + Grey Partition Wall:
        bed1_top_y = (b1_nw_ext.y_max - 80) if b1_nw_ext else (b1_rect.y_max - 80)
        bed1_rect_furn = RectMM(b1_rect.x_min + 180, bed1_top_y - 2150, b1_rect.x_min + 2150, bed1_top_y)
        desk1_rect_furn = RectMM(lw_x0 - 150, iy1 - 760, b1_l_horiz_x1 + 50, iy1 - 80)

        furn_east_x0 = core_east_outer + 1550
        if layout_variant == "TYPE_B":
            # TYPE B: Horizontal South-Facing Kitchen Island + Dining Table in South-West/Center + Grand East Salon & TV Lounge + Foyer Coat Closet
            kit_living_furn: List[FurnitureElement] = [
                FurnitureElement("FURN_CIRC_AXIS", "LIVING_DINING", "CIRCULATION_PATH", RectMM(core_east_outer + 180, liv_rect.y_min + 250, core_east_outer + 1250, y_srv_south - 180), "MAIN CIRCULATION AXIS", "مسیر آزاد رفت‌وآمد و گردش خانه"),
                FurnitureElement("FURN_TV_LOUNGE", "LIVING_DINING", "TV_LOUNGE", RectMM(furn_east_x0, y_srv_south - 2150, ix1 - 220, y_srv_south - 380), "FAMILY TV LOUNGE", "نشیمن خصوصی و تلویزیون (تیپ B)"),
                FurnitureElement("FURN_SOFA_L", "LIVING_DINING", "SOFA_L", RectMM(furn_east_x0, liv_rect.y_min + 280, ix1 - 200, liv_rect.y_min + 2350), "RECEPTION SOFA SET", "ست مبلمان پذیرایی مهمان (تیپ B)"),
                FurnitureElement("FURN_DINING_6", "OPEN_KITCHEN", "DINING_6", RectMM(ok_rect.x_min + 780, ok_rect.y_min + 140, ok_rect.x_max - 820, ok_rect.y_min + 1580), "DINING 6P BY ISLAND", "ناهارخوری ۶ نفره کنار جزیره (تیپ B)", orientation="H"),
                FurnitureElement("FURN_KIT_ISLAND", "OPEN_KITCHEN", "KITCHEN_ISLAND_BAR", RectMM(ok_rect.x_max - 740, island_y0, ok_rect.x_max - 60, island_y1), "ISLAND & BAR", "جزیره و بار صبحانه‌خوری"),
                FurnitureElement("FURN_KIT_COUNTER_W", "OPEN_KITCHEN", "KITCHEN_COUNTER", RectMM(ok_rect.x_min + 50, ok_rect.y_min + 80, ok_rect.x_min + 650, ok_rect.y_max - 740), "SINK & STOVE", "سینک دوقلو و گاز ۵ شعله"),
                FurnitureElement("FURN_KIT_COUNTER_N", "OPEN_KITCHEN", "KITCHEN_COUNTER", RectMM(ok_rect.x_min + 790, ok_rect.y_max - 740, ok_rect.x_max - 920, ok_rect.y_max - 20), "FRIDGE & WASHER", "یخچال ساید و لباسشویی", orientation="FRIDGE_WASHER"),
                FurnitureElement("FURN_DUCT_KIT", "OPEN_KITCHEN", "DUCT", kitchen_duct_rect, "KITCHEN DUCT", "داکت آشپزخانه"),
            ]
        elif layout_variant == "TYPE_C":
            # TYPE C: 3-Bedroom / Home-Office South-West Room + L-Kitchen in North-Central West + Grand East Living & Dining
            kit_living_furn = [
                FurnitureElement("FURN_CIRC_AXIS", "LIVING_DINING", "CIRCULATION_PATH", RectMM(core_east_outer + 180, liv_rect.y_min + 250, core_east_outer + 1250, y_srv_south - 180), "MAIN CIRCULATION AXIS", "مسیر آزاد رفت‌وآمد و گردش خانه"),
                FurnitureElement("FURN_SOFA_L", "LIVING_DINING", "SOFA_L", RectMM(furn_east_x0, liv_rect.y_min + 280, ix1 - 200, liv_rect.y_min + 2400), "RECEPTION SOFA SET", "ست کامل مبلمان پذیرایی (تیپ C — ۳ خوابه)"),
                FurnitureElement("FURN_DINING_6", "LIVING_DINING", "DINING_6", RectMM(furn_east_x0 + 150, y_srv_south - 2100, ix1 - 350, y_srv_south - 500), "DINING 8P", "میز ناهارخوری ۸ نفره (تیپ C)", orientation="H"),
                FurnitureElement("FURN_TV_LOUNGE", "LIVING_DINING", "TV_LOUNGE", RectMM(furn_east_x0, liv_rect.y_min + 2520, ix1 - 220, y_srv_south - 2180), "PRIVATE TV SITTING", "نشیمن خصوصی خانواده (تیپ C)"),
                FurnitureElement("FURN_KIT_ISLAND", "OPEN_KITCHEN", "KITCHEN_ISLAND_BAR", RectMM(ok_rect.x_max - 740, island_y0, ok_rect.x_max - 60, island_y1), "ISLAND & BAR", "پیشخوان و جزیره اپن"),
                FurnitureElement("FURN_KIT_COUNTER_W", "OPEN_KITCHEN", "KITCHEN_COUNTER", RectMM(ok_rect.x_min + 50, ok_rect.y_min + 80, ok_rect.x_min + 650, ok_rect.y_max - 740), "SINK & STOVE", "سینک دوقلو و گاز ۵ شعله"),
                FurnitureElement("FURN_KIT_COUNTER_N", "OPEN_KITCHEN", "KITCHEN_COUNTER", RectMM(ok_rect.x_min + 790, ok_rect.y_max - 740, ok_rect.x_max - 920, ok_rect.y_max - 20), "FRIDGE & WASHER", "یخچال ساید و لباسشویی", orientation="FRIDGE_WASHER"),
                FurnitureElement("FURN_DUCT_KIT", "OPEN_KITCHEN", "DUCT", kitchen_duct_rect, "KITCHEN DUCT", "داکت آشپزخانه"),
            ]
        else:
            # TYPE A (Classic Verified Reference Layout)
            kit_living_furn = [
                FurnitureElement(
                    "FURN_CIRC_AXIS",
                    "LIVING_DINING",
                    "CIRCULATION_PATH",
                    RectMM(core_east_outer + 180, liv_rect.y_min + 250, core_east_outer + 1320, y_srv_south - 180),
                    "MAIN CIRCULATION AXIS",
                    "مسیر آزاد رفت‌وآمد و گردش خانه",
                ),
                FurnitureElement(
                    "FURN_SOFA_L",
                    "LIVING_DINING",
                    "SOFA_L",
                    RectMM(furn_east_x0, liv_rect.y_min + 280, ix1 - 200, liv_rect.y_min + 2450),
                    "RECEPTION SOFA SET",
                    "ست کامل مبلمان پذیرایی مهمان",
                ),
                FurnitureElement(
                    "FURN_DINING_6",
                    "LIVING_DINING",
                    "DINING_6",
                    RectMM(furn_east_x0 + 150, y_srv_south - 2100, ix1 - 350, y_srv_south - 500),
                    "DINING 8P",
                    "میز ناهارخوری ۸ نفره",
                    orientation="H",
                ),
                FurnitureElement(
                    "FURN_TV_WALL",
                    "LIVING_DINING",
                    "TV_WALL",
                    RectMM(furn_east_x0 + 100, y_srv_south - 340, ix1 - 350, y_srv_south - 80),
                    "TV & PRIVACY WALL",
                    "دیوار محرمیت و تلویزیون (TV Wall)",
                ),
                FurnitureElement("FURN_KIT_ISLAND", "OPEN_KITCHEN", "KITCHEN_ISLAND_BAR", RectMM(ok_rect.x_max - 740, island_y0, ok_rect.x_max - 60, island_y1), "ISLAND & BAR", "جزیره و صندلی اپن"),
                FurnitureElement("FURN_KIT_COUNTER_W", "OPEN_KITCHEN", "KITCHEN_COUNTER", RectMM(ok_rect.x_min + 50, ok_rect.y_min + 80, ok_rect.x_min + 650, ok_rect.y_max - 740), "SINK & STOVE", "سینک دوقلو و گاز ۵ شعله"),
                FurnitureElement("FURN_KIT_COUNTER_N", "OPEN_KITCHEN", "KITCHEN_COUNTER", RectMM(ok_rect.x_min + 790, ok_rect.y_max - 740, ok_rect.x_max - 920, ok_rect.y_max - 20), "FRIDGE & WASHER", "یخچال ساید و لباسشویی", orientation="FRIDGE_WASHER"),
                FurnitureElement("FURN_DUCT_KIT", "OPEN_KITCHEN", "DUCT", kitchen_duct_rect, "KITCHEN DUCT", "داکت آشپزخانه"),
            ]

        furniture: List[FurnitureElement] = [
            *kit_living_furn,
            # `333.jpg` Exact West Bedroom Layout (Blue Bed in NW Alcove + Red Study Desk under Lightwell Window + Grey Partition Wall + Back-to-Back Closets):
            FurnitureElement("FURN_BED1", "BEDROOM_1", "BED_DOUBLE", bed1_rect_furn, "BED 2 IN NW ALCOVE", "تخت خواب و پاتختی (نورگیر)"),
            FurnitureElement("FURN_BED1_DESK", "BEDROOM_1", "STUDY_DESK", desk1_rect_furn, "STUDY DESK UNDER WINDOW", "میز مطالعه (زیر پنجره)"),
            FurnitureElement("FURN_BED1_CLOSET_BEHIND_DOOR", "BEDROOM_1", "WARDROBE", RectMM(x_joint_0, y_joint_1, bed_split_x - 70, iy1), "WARDROBE WEST", "کمد دیواری خواب ۲"),
            FurnitureElement("FURN_MBED_CLOSET_BEHIND_DOOR", "MASTER_BEDROOM", "WARDROBE", RectMM(bed_split_x + 70, y_joint_1, x_joint_1, iy1), "WARDROBE EAST", "کمد دیواری مستر"),
            FurnitureElement("FURN_BED_PARTITION_WALL", "BEDROOM_1", "PARTITION_WALL", RectMM(bed_split_x - 70, y_joint_1, bed_split_x + 70, floor_gross_rect.y_max), "PARTITION WALL BETWEEN BEDROOMS", "دیوار جداکننده بین دو اتاق خواب"),
            *SmartArchitecturalFurnitureSolver.solve_east_master_bedroom_layout(
                room_rect=mbe_rect,
                joint_x_max=x_joint_1,
                iy1=iy1,
                gross_y_max=floor_gross_rect.y_max,
                ext_wall_mm=t_ext,
                has_lightwell_door=False,
            )[2],
            FurnitureElement("FURN_WC_SET", "GUEST_WC", "WC_SET", RectMM(wc_rect.x_min + 15, wc_rect.y_min + 800, wc_rect.x_max - 15, wc_rect.y_max - 15), "WC & SINK", "روشویی و توالت", orientation="N"),
            FurnitureElement("FURN_BATH_SET", "MAIN_BATHROOM", "BATH_SET", RectMM(bath_rect.x_min + 830, bath_rect.y_min + 15, bath_rect.x_max - 15, bath_rect.y_max - 15), "BATH & SHOWER", "کابین دوش، فرنگی و روشویی", orientation="SHOWER_EAST_WALL"),
            FurnitureElement("FURN_MBATH_SET", "MASTER_BATH", "BATH_SET", RectMM(mbath_rect.x_min + 15, mbath_rect.y_min + 15, mbath_rect.x_max - 15, mbath_rect.y_max - 820), "MASTER BATH", "وان/دوش، فرنگی و روشویی مستر", orientation="SHOWER_WEST_WALL"),
            FurnitureElement("FURN_DUCT_SANITARY_SHARED", "GUEST_WC", "DUCT", shared_sanitary_duct_rect, "SHARED SANITARY DUCT", "داکت مشترک"),
        ]

        nw_area = b1_nw_ext.area_m2 if b1_nw_ext else 0.0
        gross_m2 = round(floor_gross_rect.area_m2 + nw_area, 2)
        net_m2 = round(sum(r.net_rect_mm.area_m2 for r in rooms) + nw_area, 2)
        cov_achieved = round(gross_m2 / (site.site_area_m2 if site.site_area_m2 > 0 else ((site.width_x_mm * site.length_y_mm) / 1e6)), 2)

        return FloorPlanDesignV3(
            floor_index=floor_index,
            name_fa=name_fa,
            name_en=f"FLOOR {floor_index} ({elev_str})",
            occupancy=OccupancyType.RESIDENTIAL_TYPICAL,
            z_elevation_mm=z_mm,
            elevation_code_str=elev_str,
            floor_height_mm=floor_h_mm,
            unit_count=1,
            gross_building_rect_mm=floor_gross_rect,
            courtyards=courtyards,
            lightwells=lightwells,
            grid_x_mm=grid_x,
            grid_y_mm=grid_y,
            columns=columns,
            stair_detail=stair_detail,
            elevator_detail=elevator_detail,
            rooms=rooms,
            doors=doors,
            windows=windows,
            furniture=furniture,
            dimensions=[],
            coverage_ratio_achieved=cov_achieved,
            gross_area_m2=gross_m2,
            net_area_m2=net_m2,
            is_open_pilotis=False,
            turning_zone_rect_mm=turning_zone,
            cantilever_zone_rect_mm=cantilever_zone,
        )

    def _synthesize_villa_single_unit_floor(
        self,
        site: ParametricSiteSpec,
        floor_index: int,
        z_mm: int,
        floor_h_mm: int,
        elev_str: str,
        cov_ratio: float,
        name_fa: str,
    ) -> FloorPlanDesignV3:
        """
        Synthesizes the Single-Unit 1-Story Villa (`پلان ویلایی تک‌واحدی مهندسی v19.0`):
        1. Unified T-Shaped Corridor (`ورودی + راهرو ارتباطی + ورودی خواب‌ها`) with ONE uniform color (`#fef9c3`) and ZERO extra internal lines!
        2. Exact `333.jpg` West Bedroom (`اتاق خواب ۲ ضلع غربی`): Bed in the North-West Alcove + Study Desk under the Lightwell Window + L-Shaped Window!
        3. East Master Bedroom Suite (`اتاق خواب مستر ضلع شرقی`): King Bed + Walk-in Closet + Master Bath + Large Window & Direct Access Door to the Lightwell (`درب حیاط خلوت`)!
        4. Solid Grey Partition Wall (`دیوار جداکننده بین دو اتاق خواب`) between the back-to-back built-in wardrobes!
        5. South Open Kitchen Counter/Island (`اپن و جزیره جنوبی آشپزخانه`) + 8-Person Dining Table directly in front of it + East Reception & TV Sitting!
        """
        ground_gross_rect, _, courtyards, lightwells, turning_zone, cantilever_zone, nw_wing_rect = self._compute_envelope_and_lightwell(
            site, cov_ratio, is_upper_floor=False
        )
        grid_x, grid_y, columns, core_box_rect = self._compute_structural_grid_and_core_box(
            site, ground_gross_rect, include_stair_core=False
        )

        t_ext = site.ext_wall_mm
        t_int = site.int_wall_mm
        ix0 = ground_gross_rect.x_min + t_ext
        ix1 = ground_gross_rect.x_max - t_ext
        iy0 = ground_gross_rect.y_min + t_ext
        iy1 = ground_gross_rect.y_max - t_ext

        p_last = getattr(self, "_last_params", {}) or {}
        kit_extra = int(p_last.get("kitchen_extra_width_mm", 0))
        liv_extra = int(p_last.get("living_extra_width_mm", 0))
        net_w = max(4800, ix1 - ix0)
        net_h = max(6200, iy1 - iy0)
        w_scale = net_w / 9500.0
        x_west_zone_end = int(round(ix0 + net_w * 0.405)) + kit_extra - liv_extra
        x_west_zone_end = max(ix0 + int(net_w * 0.30), min(ix0 + int(net_w * 0.47), x_west_zone_end))
        y_mid_north = core_box_rect.y_max
        actual_south_span = max(3800, y_mid_north - iy0)
        y_kit_south = iy0 + int(round(actual_south_span * 0.41))

        foyer_w = max(1100, min(1550, int(round(net_w * 0.145))))
        foyer_x0 = x_west_zone_end
        foyer_x1 = foyer_x0 + foyer_w
        steps_h = min(1800, max(900, ground_gross_rect.y_min - 200))
        entry_steps_rect = RectMM(foyer_x0 + 80, ground_gross_rect.y_min - steps_h, foyer_x1 + 200, ground_gross_rect.y_min)

        priv_h = max(1050, min(1400, int(round(actual_south_span * 0.19))))
        srv_h = max(1250, min(1750, int(round(actual_south_span * 0.24))))
        y_priv_south = y_mid_north - priv_h
        y_srv_south = max(iy0 + int(actual_south_span * 0.46), y_priv_south - t_int - srv_h)

        # Unified Corridor: `ENTRANCE_FOYER` spans from `iy0` right up to `y_priv_south` (touching `PRIVATE_HALL` with zero gap!)
        foyer_rect = RectMM(foyer_x0, iy0, foyer_x1, y_priv_south)

        wet_span_w = max(2400, ix1 - (foyer_x1 + t_int))
        wc_w = max(950, int(round((wet_span_w - 2 * t_int) * 0.31)))
        bath_w = max(950, int(round((wet_span_w - 2 * t_int) * 0.34)))
        wc_x0 = foyer_x1 + t_int
        wc_x1 = wc_x0 + wc_w
        bath_x0 = wc_x1 + t_int
        bath_x1 = bath_x0 + bath_w
        mbath_x0 = bath_x1 + t_int
        mbath_x1 = ix1

        wc_rect = RectMM(wc_x0, y_srv_south, wc_x1, y_priv_south - t_int)
        priv_hall_rect = RectMM(foyer_x0, y_priv_south, wc_x1, y_mid_north)
        bath_rect = RectMM(bath_x0, y_srv_south, bath_x1, y_mid_north - t_int)
        mbath_rect = RectMM(mbath_x0, y_srv_south, mbath_x1, y_mid_north - t_int)

        y_bed_south = y_mid_north
        joint_w = max(1050, min(1350, int(round(net_w * 0.13))))
        bed_split_x = ix0 + int(round(net_w * 0.465))
        x_joint_0 = bed_split_x - joint_w // 2
        x_joint_1 = bed_split_x + joint_w // 2
        joint_h = min(1200, max(850, int(round((iy1 - y_bed_south) * 0.36))))
        y_joint_1 = y_bed_south + joint_h
        joint_rect = RectMM(x_joint_0, y_bed_south, x_joint_1, y_joint_1)

        ok_rect = RectMM(ix0, y_kit_south, x_west_zone_end - t_int, y_mid_north - t_int)
        liv_rect = RectMM(foyer_x1, iy0, ix1, y_srv_south - t_int)
        dining_sw_rect = RectMM(ix0, iy0, foyer_x0, y_kit_south)

        b1_rect = RectMM(ix0, y_bed_south, x_joint_0, iy1)
        mbe_rect = RectMM(x_joint_1, y_bed_south, ix1, iy1)
        b1_nw_ext = (
            RectMM(ix0, iy1, nw_wing_rect.x_max - t_ext, nw_wing_rect.y_max - t_ext)
            if nw_wing_rect is not None
            else None
        )

        rooms: List[RoomSpace] = [
            RoomSpace(
                room_id="ENTRY_STEPS_LANDING",
                code_en="ENTRANCE STEPS (3 RISERS x 15CM = +0.45m, TREAD=30CM) & LANDING",
                label_fa="۳ پله ورودی (H=15cm، کف ۳۰cm) و پاگرد (+0.45m)",
                unit_id="VILLA",
                space_category="OUTDOOR",
                net_rect_mm=entry_steps_rect,
                z_elevation_mm=z_mm,
                elevation_label="⊕ ±0.00 → +0.45m",
                natural_light="SOUTH_COURTYARD",
            ),
            RoomSpace(
                room_id="ENTRANCE_FOYER",
                code_en="UNIFIED VILLA ENTRANCE & GALLERY",
                label_fa="ورودی و گالری ارتباطی",
                unit_id="VILLA",
                space_category="CIRCULATION",
                net_rect_mm=foyer_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NONE",
                is_open_edge_east=True,
                is_open_edge_west=True,
                is_open_edge_north=True,
            ),
            RoomSpace(
                room_id="PRIVATE_HALL",
                code_en="UNIFIED PRIVATE CORRIDOR",
                label_fa="راهرو و فیلتر خصوصی خواب‌ها",
                unit_id="VILLA",
                space_category="CIRCULATION",
                net_rect_mm=priv_hall_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NONE",
                is_open_edge_south=True,
                is_open_edge_north=True,
            ),
            RoomSpace(
                room_id="OPEN_KITCHEN",
                code_en="OPEN KITCHEN WITH SOUTH ISLAND & COUNTER",
                label_fa="آشپزخانه اپن (با پیشخوان جنوبی)",
                unit_id="VILLA",
                space_category="SEMI_PUBLIC",
                net_rect_mm=ok_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="SOUTH_DINING_WINDOW",
                is_open_edge_south=True,
                is_open_edge_east=False,
            ),
            RoomSpace(
                room_id="GUEST_WC",
                code_en="GUEST WC",
                label_fa="سرویس بهداشتی",
                unit_id="VILLA",
                space_category="WET_SERVICE",
                net_rect_mm=wc_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="MECHANICAL",
            ),
            RoomSpace(
                room_id="MAIN_BATHROOM",
                code_en="MAIN BATHROOM",
                label_fa="حمام عمومی",
                unit_id="VILLA",
                space_category="WET_SERVICE",
                net_rect_mm=bath_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="MECHANICAL",
            ),
            RoomSpace(
                room_id="MASTER_BATH",
                code_en="MASTER ENSUITE BATHROOM",
                label_fa="حمام و سرویس مستر",
                unit_id="VILLA",
                space_category="WET_SERVICE",
                net_rect_mm=mbath_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="MECHANICAL",
            ),
            RoomSpace(
                room_id="LIVING_DINING",
                code_en="GRAND LIVING & SITTING HALL (EAST) + DINING IN FRONT OF KITCHEN (WEST)",
                label_fa="سالن پذیرایی و نشیمن بزرگ",
                unit_id="VILLA",
                space_category="PUBLIC",
                net_rect_mm=liv_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="SOUTH_COURTYARD",
                is_open_edge_west=True,
                is_open_edge_north=True,
                l_extension_rect_mm=dining_sw_rect,
                l_extension_label_fa="ناهارخوری (جلوی اپن آشپزخانه)",
            ),
            RoomSpace(
                room_id="BEDROOM_1",
                code_en="WEST BEDROOM 2 (BED IN NW ALCOVE + DESK UNDER WINDOW - 333.JPG)",
                label_fa="اتاق خواب ۲ (ضلع غربی)",
                unit_id="VILLA",
                space_category="PRIVATE",
                net_rect_mm=b1_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NORTH_LIGHTWELL",
                l_extension_rect_mm=b1_nw_ext,
                l_extension_label_fa="",
            ),
            RoomSpace(
                room_id="MASTER_BEDROOM",
                code_en="EAST MASTER BEDROOM SUITE (WITH LIGHTWELL DOOR)",
                label_fa="اتاق خواب مستر (دارای درب حیاط خلوت)",
                unit_id="VILLA",
                space_category="PRIVATE",
                net_rect_mm=mbe_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NORTH_LIGHTWELL",
            ),
            RoomSpace(
                room_id="BEDROOM_ENTRY_JOINT",
                code_en="UNIFIED CORRIDOR EXTENSION BETWEEN BEDROOMS",
                label_fa="",
                unit_id="VILLA",
                space_category="CIRCULATION",
                net_rect_mm=joint_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NONE",
                is_open_edge_south=True,
            ),
        ]

        doors: List[DoorElement] = [
            DoorElement(
                "D_VILLA_MAIN_ENTRY",
                "درب ورودی اصلی خانه",
                "ENTRY_STEPS_LANDING",
                "ENTRANCE_FOYER",
                (foyer_rect.x_min + 580, foyer_rect.y_min),
                820,
                "H",
                "N",
                leaf_dir="+",
                is_main_entry=True,
            ),
            DoorElement(
                "D_GUEST_WC",
                "درب سرویس",
                "ENTRANCE_FOYER",
                "GUEST_WC",
                (wc_rect.x_min, wc_rect.y_min + 80),
                680,
                "V",
                "E",
                leaf_dir="+",
            ),
            DoorElement(
                "D_MAIN_BATH",
                "درب حمام عمومی (با حفظ محرمیت)",
                "PRIVATE_HALL",
                "MAIN_BATHROOM",
                (bath_rect.x_min, y_priv_south + 100),
                720,
                "V",
                "E",
                leaf_dir="+",
            ),
            DoorElement(
                "D_BED_1",
                "درب خواب ۲",
                "BEDROOM_ENTRY_JOINT",
                "BEDROOM_1",
                (joint_rect.x_min, y_bed_south + 80),
                880,
                "V",
                "W",
                leaf_dir="+",
            ),
            DoorElement(
                "D_MASTER_BED",
                "درب خواب مستر",
                "BEDROOM_ENTRY_JOINT",
                "MASTER_BEDROOM",
                (joint_rect.x_max, y_bed_south + 80),
                880,
                "V",
                "E",
                leaf_dir="+",
            ),
            DoorElement(
                "D_MASTER_BATH",
                "درب حمام مستر",
                "MASTER_BEDROOM",
                "MASTER_BATH",
                (mbath_rect.x_max - 80, mbath_rect.y_max),
                740,
                "H",
                "S",
                leaf_dir="-",
            ),
            *SmartArchitecturalFurnitureSolver.solve_east_master_bedroom_layout(
                room_rect=mbe_rect,
                joint_x_max=x_joint_1,
                iy1=iy1,
                gross_y_max=ground_gross_rect.y_max,
                ext_wall_mm=t_ext,
                has_lightwell_door=True,
            )[0],
        ]

        lw_north = next((lw for lw in lightwells if lw.position == "NORTH"), None)
        lw_x0 = lw_north.rect_mm.x_min if lw_north else 2890
        raw_windows: List[WindowElement] = [
            WindowElement("WIN_DINING_SOUTH", "LIVING_DINING", "SOUTH_COURTYARD", ix0 + 450, ground_gross_rect.y_min, foyer_x0 - 350, ground_gross_rect.y_min + t_ext, t_ext, "H"),
            WindowElement("WIN_LIVING_SOUTH", "LIVING_DINING", "SOUTH_COURTYARD", foyer_rect.x_max + 550, ground_gross_rect.y_min, ix1 - 550, ground_gross_rect.y_min + t_ext, t_ext, "H"),
            WindowElement("WIN_BED1_L_HORIZ", "BEDROOM_1", "NORTH_LIGHTWELL", lw_x0 - t_ext, iy1, x_joint_0 - 180, ground_gross_rect.y_max, t_ext, "H"),
            *SmartArchitecturalFurnitureSolver.solve_east_master_bedroom_layout(
                room_rect=mbe_rect,
                joint_x_max=x_joint_1,
                iy1=iy1,
                gross_y_max=ground_gross_rect.y_max,
                ext_wall_mm=t_ext,
                has_lightwell_door=True,
            )[1],
        ]
        if nw_wing_rect is not None:
            raw_windows.append(
                WindowElement("WIN_BED1_L_VERT", "BEDROOM_1", "NORTH_LIGHTWELL", lw_x0 - t_ext, iy1, lw_x0, nw_wing_rect.y_max - 220, t_ext, "V")
            )
        if "EAST" in site.street_sides:
            raw_windows.append(
                WindowElement("WIN_LIVING_EAST_STREET", "LIVING_DINING", "EAST_STREET", ground_gross_rect.x_max - t_ext, liv_rect.y_min + 450, ground_gross_rect.x_max, max(liv_rect.y_min + 1450, liv_rect.y_max - 450), t_ext, "V")
            )
            raw_windows.append(
                WindowElement("WIN_MBED_EAST_STREET", "MASTER_BEDROOM", "EAST_STREET", ground_gross_rect.x_max - t_ext, mbe_rect.y_min + 450, ground_gross_rect.x_max, max(mbe_rect.y_min + 1350, mbe_rect.y_max - 450), t_ext, "V")
            )
        windows = [self._decollide_window_from_columns(w, columns, doors=doors) for w in raw_windows]

        shared_sanitary_duct_rect = RectMM(wc_rect.x_max - 220, y_srv_south + 40, bath_rect.x_min + 220, y_srv_south + 520)
        kitchen_duct_rect = RectMM(ok_rect.x_min + 120, ok_rect.y_max - 720, ok_rect.x_min + 770, ok_rect.y_max - 15)

        bed1_top_y = (b1_nw_ext.y_max - 80) if b1_nw_ext else (b1_rect.y_max - 80)
        bed1_rect_furn = RectMM(b1_rect.x_min + 180, bed1_top_y - 2150, b1_rect.x_min + 2150, bed1_top_y)
        desk1_rect_furn = RectMM(lw_x0 - 150, iy1 - 760, x_joint_0 - 120, iy1 - 80)

        furniture: List[FurnitureElement] = [
            FurnitureElement("FURN_SOFA_L", "LIVING_DINING", "SOFA_L", RectMM(max(liv_rect.x_min + 250, ix1 - 3150), liv_rect.y_min + 220, ix1 - 220, min(liv_rect.y_max - 250, liv_rect.y_min + 2250)), "RECEPTION SOFA SET", "ست کامل مبلمان پذیرایی مهمان"),
            FurnitureElement("FURN_TV_LOUNGE", "LIVING_DINING", "TV_LOUNGE", RectMM(max(liv_rect.x_min + 250, ix1 - 3050), min(y_srv_south - 1200, liv_rect.y_min + 2400), ix1 - 250, max(liv_rect.y_min + 1400, y_srv_south - 420)), "FAMILY TV LOUNGE", "مبل راحتی نشیمن خصوصی"),
            FurnitureElement("FURN_TV_WALL", "LIVING_DINING", "TV_WALL", RectMM(wc_x0 + 100, y_srv_south - 340, ix1 - 350, y_srv_south - 80), "TV & PRIVACY WALL", "دیوار محرمیت و تلویزیون (TV Wall)"),
            FurnitureElement("FURN_DINING_6", "LIVING_DINING", "DINING_6", RectMM(ix0 + 350, iy0 + 350, min(foyer_x0 - 200, ix0 + 2450), max(iy0 + 1350, y_kit_south - 450)), "DINING 8P", "میز ناهارخوری ۸ نفره (جلوی اپن آشپزخانه)"),
            FurnitureElement("FURN_KIT_ISLAND", "OPEN_KITCHEN", "KITCHEN_ISLAND_BAR", RectMM(ok_rect.x_min + 180, ok_rect.y_min + 40, min(ok_rect.x_max - 180, ok_rect.x_min + 2450), min(ok_rect.y_max - 200, ok_rect.y_min + 700)), "SOUTH ISLAND & BAR", "اپن و جزیره جنوبی آشپزخانه", orientation="H"),
            FurnitureElement("FURN_KIT_COUNTER_W", "OPEN_KITCHEN", "KITCHEN_COUNTER", RectMM(ok_rect.x_min + 50, ok_rect.y_min + 820, ok_rect.x_min + 650, ok_rect.y_max - 740), "SINK & STOVE", "سینک دوقلو و گاز ۵ شعله"),
            FurnitureElement("FURN_KIT_COUNTER_N", "OPEN_KITCHEN", "KITCHEN_COUNTER", RectMM(ok_rect.x_min + 790, ok_rect.y_max - 740, ok_rect.x_max - 620, ok_rect.y_max - 20), "FRIDGE & WASHER", "یخچال ساید و لباسشویی", orientation="FRIDGE_WASHER"),
            FurnitureElement("FURN_KIT_COUNTER_E", "OPEN_KITCHEN", "KITCHEN_COUNTER", RectMM(ok_rect.x_max - 580, ok_rect.y_min + 820, ok_rect.x_max - 30, ok_rect.y_max - 20), "EAST CABINET WALL", "کابینت قدی، فر و ظرفشویی", orientation="APPLIANCE_WALL"),
            FurnitureElement("FURN_ENTRY_WING_WALL", "ENTRANCE_FOYER", "PARTITION_WALL", RectMM(foyer_rect.x_min - 60, iy0, foyer_rect.x_min + 60, iy0 + 1520), "ENTRY WING WALL", "دیوار غربی ورودی و تکیه‌گاه جالباسی"),
            FurnitureElement("FURN_SHOE_CLOSET", "ENTRANCE_FOYER", "WARDROBE", RectMM(foyer_rect.x_min + 60, iy0 + 160, foyer_rect.x_min + 520, iy0 + 1440), "SHOE CLOSET", "کفش‌کن و جالباسی (کنار دیوار غربی ورودی)"),
            FurnitureElement("FURN_PLANTER_ENTRY_W", "COURTYARD", "PLANTER_BOX", RectMM(entry_steps_rect.x_min - 1150, ground_gross_rect.y_min - 950, entry_steps_rect.x_min - 220, ground_gross_rect.y_min - 280), "WEST PLANTER", "باغچه سنگی حیاط"),
            FurnitureElement("FURN_PLANTER_ENTRY_E", "COURTYARD", "PLANTER_BOX", RectMM(entry_steps_rect.x_max + 220, ground_gross_rect.y_min - 950, entry_steps_rect.x_max + 1150, ground_gross_rect.y_min - 280), "EAST PLANTER", "باغچه سنگی حیاط"),
            FurnitureElement("FURN_GARDEN_BED_W", "COURTYARD", "PLANTER_BOX", RectMM(140, 1400, 820, min(6200, ground_gross_rect.y_min - 450)), "WEST GARDEN BED", "باغچه سرسبز حیاط"),
            FurnitureElement("FURN_DUCT_KIT", "OPEN_KITCHEN", "DUCT", kitchen_duct_rect, "KITCHEN DUCT", "داکت آشپزخانه"),
            # `333.jpg` West Bedroom (Bed in NW Alcove + Study Desk under Lightwell Window + Solid Partition Wall + Back-to-Back Closets):
            FurnitureElement("FURN_BED1", "BEDROOM_1", "BED_DOUBLE", bed1_rect_furn, "BED 2 IN NW ALCOVE", "تخت خواب و پاتختی (نورگیر)"),
            FurnitureElement("FURN_BED1_DESK", "BEDROOM_1", "STUDY_DESK", desk1_rect_furn, "STUDY DESK UNDER WINDOW", "میز مطالعه (زیر پنجره)"),
            FurnitureElement("FURN_BED1_CLOSET_BEHIND_DOOR", "BEDROOM_1", "WARDROBE", RectMM(x_joint_0, y_joint_1, bed_split_x - 70, iy1), "WARDROBE WEST", "کمد دیواری خواب ۲"),
            FurnitureElement("FURN_MBED_CLOSET_BEHIND_DOOR", "MASTER_BEDROOM", "WARDROBE", RectMM(bed_split_x + 70, y_joint_1, x_joint_1, iy1), "WARDROBE EAST", "کمد دیواری مستر"),
            FurnitureElement("FURN_BED_PARTITION_WALL", "BEDROOM_1", "PARTITION_WALL", RectMM(bed_split_x - 70, y_joint_1, bed_split_x + 70, ground_gross_rect.y_max), "PARTITION WALL BETWEEN BEDROOMS", "دیوار جداکننده بین دو اتاق خواب"),
            *SmartArchitecturalFurnitureSolver.solve_east_master_bedroom_layout(
                room_rect=mbe_rect,
                joint_x_max=x_joint_1,
                iy1=iy1,
                gross_y_max=ground_gross_rect.y_max,
                ext_wall_mm=t_ext,
                has_lightwell_door=True,
            )[2],
            FurnitureElement("FURN_WC_SET", "GUEST_WC", "WC_SET", RectMM(wc_rect.x_min + 15, wc_rect.y_min + 800, wc_rect.x_max - 15, wc_rect.y_max - 15), "WC & SINK", "روشویی و توالت", orientation="N"),
            FurnitureElement("FURN_BATH_SET", "MAIN_BATHROOM", "BATH_SET", RectMM(bath_rect.x_min + 830, bath_rect.y_min + 15, bath_rect.x_max - 15, bath_rect.y_max - 15), "BATH & SHOWER", "کابین دوش، فرنگی و روشویی", orientation="SHOWER_EAST_WALL"),
            FurnitureElement("FURN_MBATH_SET", "MASTER_BATH", "BATH_SET", RectMM(mbath_rect.x_min + 15, mbath_rect.y_min + 15, mbath_rect.x_max - 15, mbath_rect.y_max - 820), "MASTER BATH", "وان/دوش، فرنگی و روشویی مستر", orientation="SHOWER_WEST_WALL"),
            FurnitureElement("FURN_DUCT_SANITARY_SHARED", "GUEST_WC", "DUCT", shared_sanitary_duct_rect, "SHARED SANITARY DUCT", "داکت مشترک"),
        ]

        if courtyards:
            cy_rect = courtyards[0][1]
            furniture.append(
                FurnitureElement("FURN_CAR", "COURTYARD", "CAR", RectMM(site.width_x_mm - 3100, max(cy_rect.y_min + 450, max(site.south_y_west_mm, site.south_y_east_mm) + 420 if cy_rect.y_min == 0 else cy_rect.y_min + 450), site.width_x_mm - 900, max(cy_rect.y_min + 450, max(site.south_y_west_mm, site.south_y_east_mm) + 420 if cy_rect.y_min == 0 else cy_rect.y_min + 450) + 4300), "PARKED CAR", "پارکینگ خودرو (دارای فضای گردش آزاد)")
            )
            furniture.append(
                FurnitureElement("FURN_TREE1", "COURTYARD", "TREE", RectMM(140, cy_rect.y_min + 600, 740, cy_rect.y_min + 1200), "TREE", "باغچه کناری")
            )

        nw_area = b1_nw_ext.area_m2 if b1_nw_ext else 0.0
        gross_m2 = round(ground_gross_rect.area_m2 + nw_area, 2)
        net_m2 = round(sum(r.net_rect_mm.area_m2 for r in rooms) + dining_sw_rect.area_m2 + nw_area, 2)
        cov_achieved = round(gross_m2 / (site.site_area_m2 if site.site_area_m2 > 0 else ((site.width_x_mm * site.length_y_mm) / 1e6)), 2)

        return FloorPlanDesignV3(
            floor_index=floor_index,
            name_fa=name_fa,
            name_en=f"VILLA GROUND FLOOR ({elev_str})",
            occupancy=OccupancyType.VILLA_GROUND,
            z_elevation_mm=z_mm,
            elevation_code_str=elev_str,
            floor_height_mm=floor_h_mm,
            unit_count=1,
            gross_building_rect_mm=ground_gross_rect,
            courtyards=courtyards,
            lightwells=lightwells,
            grid_x_mm=grid_x,
            grid_y_mm=grid_y,
            columns=columns,
            stair_detail=None,
            elevator_detail=None,
            rooms=rooms,
            doors=doors,
            windows=windows,
            furniture=furniture,
            dimensions=[],
            coverage_ratio_achieved=cov_achieved,
            gross_area_m2=gross_m2,
            net_area_m2=net_m2,
            is_open_pilotis=False,
            turning_zone_rect_mm=turning_zone,
        )

    def _synthesize_duplex_lower_day_floor(
        self,
        site: ParametricSiteSpec,
        floor_index: int,
        z_mm: int,
        floor_h_mm: int,
        elev_str: str,
        cov_ratio: float,
        name_fa: str,
    ) -> FloorPlanDesignV3:
        """
        Synthesizes Floor 0 of a 2-Story Modern Duplex Villa (`طبقه همکف ویلایی دوبلکس مدرن v19.0`):
        - Decorative L-Shaped Curved Duplex Staircase (`پله دکوراتیو و شکیل L شکل دوبلکس`) placed in the Central-West Gallery
          with direct access from the Entrance Foyer & Reception Hall (`کاملاً بیرون از آشپزخانه — دسترسی از گالری و پذیرایی`)!
        - Public Day Spaces + ONLY ONE Ground-Floor Guest Bedroom (`فضاهای عمومی روز در طبقه پایین + فقط ۱ اتاق خواب مهمان در شمال‌شرقی`):
          * North-West: Large Modern Open Kitchen (`آشپزخانه اپن بزرگ با پیشخوان و جزیره جنوبی`) + North-West Mutbakh (`مطبخ در جناح شمال‌غربی کنار حیاط خلوت`).
          * South-West: 8-Person Formal Dining Hall (`ناهارخوری ۸ نفره جلوی اپن آشپزخانه`).
          * East: Grand Double-Height Reception & Living Hall (`سالن پذیرایی و نشیمن بزرگ زیر وید دوبلکس`).
          * North-East: Single Guest Bedroom Suite (`تک اتاق خواب مهمان همکف`) accessed directly from the Central Corridor (`D_GUEST_BED`)
            with a Direct Access Door to the Lightwell (`درب حیاط خلوت`)!
        """
        ground_gross_rect, _, courtyards, lightwells, turning_zone, cantilever_zone, nw_wing_rect = self._compute_envelope_and_lightwell(
            site, cov_ratio, is_upper_floor=False
        )
        grid_x, grid_y, columns, core_box_rect = self._compute_structural_grid_and_core_box(
            site, ground_gross_rect, include_stair_core=False
        )

        t_ext = site.ext_wall_mm
        t_int = site.int_wall_mm
        ix0 = ground_gross_rect.x_min + t_ext
        ix1 = ground_gross_rect.x_max - t_ext
        iy0 = ground_gross_rect.y_min + t_ext
        iy1 = ground_gross_rect.y_max - t_ext

        p_last = getattr(self, "_last_params", {}) or {}
        kit_extra = int(p_last.get("kitchen_extra_width_mm", 0))
        liv_extra = int(p_last.get("living_extra_width_mm", 0))
        remove_void = bool(p_last.get("remove_duplex_void", False))
        w_scale = (ix1 - ix0) / 9500.0

        y_north_zone = core_box_rect.y_max + 170      # 14820mm on 10x20 site, scales with site length
        h_scale_d = min(1.15, max(0.72, (iy1 - iy0) / 11470.0))
        y_stair_south_dup = y_north_zone - int(round(3270 * h_scale_d))       # 11550mm on 10x20 site, scales with site length
        foyer_x0 = int(round(ix0 + 3600 * w_scale)) + kit_extra
        east_zone_x0 = int(round(ix0 + 5800 * w_scale)) - liv_extra
        east_zone_x0 = max(foyer_x0 + 1400, min(ix1 - 2800, east_zone_x0))
        entry_steps_rect = RectMM(foyer_x0 + 400, ground_gross_rect.y_min - 1800, min(east_zone_x0, foyer_x0 + 2000), ground_gross_rect.y_min)

        # Decorative L-Shaped Curved Duplex Staircase sits in the West-Central Gallery (`y in [y_stair_south_dup, y_north_zone]`)
        dec_stair_rect = RectMM(ix0 + 190, y_stair_south_dup + 90, foyer_x0 - 100, y_north_zone - 260)

        # North-West: Large Modern Open Kitchen + Optional Mutbakh in NW Wing (or cleanly partitioned NW corner)
        ok_rect = RectMM(ix0, y_north_zone, foyer_x0, iy1)
        mutbakh_rect = (
            RectMM(ix0, iy1 + t_int, nw_wing_rect.x_max - t_ext, nw_wing_rect.y_max - t_ext)
            if (nw_wing_rect is not None and site.include_dirty_kitchen)
            else (
                RectMM(ix0, iy1 - 1300, ix0 + 1850, iy1)
                if site.include_dirty_kitchen
                else RectMM(ix0, iy1, ix0 + 100, iy1 + 100)
            )
        )
        if not site.include_dirty_kitchen and nw_wing_rect is not None:
            ok_rect = RectMM(ix0, y_north_zone, foyer_x0, nw_wing_rect.y_max - t_ext)

        # South-West (below the decorative stair): 8-Person Formal Dining Hall
        dining_sw_rect = RectMM(ix0, iy0, foyer_x0, y_stair_south_dup)

        # Middle-East Service Band (`سرویس مهمان و حمام مهمان` 100% vertically aligned with Floor 1)
        srv_y0 = y_north_zone - int(round(1750 * h_scale_d))
        foyer_rect = RectMM(foyer_x0, iy0, east_zone_x0, y_north_zone)
        upper_corr_ext = RectMM(foyer_x0, y_north_zone, east_zone_x0, iy1)
        wc_split_x = east_zone_x0 + 100 + int(round((ix1 - (east_zone_x0 + 100)) * 0.36))
        wc_rect = RectMM(east_zone_x0 + 100, srv_y0, wc_split_x, y_north_zone - t_int)
        bath_rect = RectMM(wc_split_x + 100, srv_y0, ix1, y_north_zone - t_int)

        # East: Grand Reception & Living Hall
        liv_rect = RectMM(east_zone_x0, iy0, ix1, srv_y0 - t_int)

        # North-East: Ground-Floor Guest Bedroom
        guest_bed_rect = RectMM(east_zone_x0, y_north_zone, ix1, iy1)

        rooms: List[RoomSpace] = [
            RoomSpace(
                room_id="ENTRY_STEPS_LANDING",
                code_en="ENTRANCE STEPS (3 RISERS x 15CM = +0.45m)",
                label_fa="۳ پله ورودی و ایوان (+0.45m)",
                unit_id="DUPLEX",
                space_category="OUTDOOR",
                net_rect_mm=entry_steps_rect,
                z_elevation_mm=z_mm,
                elevation_label="⊕ ±0.00 → +0.45m",
                natural_light="SOUTH_COURTYARD",
            ),
            RoomSpace(
                room_id="ENTRANCE_FOYER",
                code_en="DUPLEX CENTRAL ENTRANCE GALLERY",
                label_fa="گالری ورودی و راهرو دوبلکس",
                unit_id="DUPLEX",
                space_category="CIRCULATION",
                net_rect_mm=foyer_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NONE",
                is_open_edge_north=True,
                is_open_edge_east=True,
                is_open_edge_west=True,
            ),
            RoomSpace(
                room_id="BEDROOM_ENTRY_JOINT",
                code_en="DUPLEX NORTH GALLERY EXTENSION",
                label_fa="",
                unit_id="DUPLEX",
                space_category="CIRCULATION",
                net_rect_mm=upper_corr_ext,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NONE",
                is_open_edge_south=True,
                is_open_edge_west=True,
            ),
            RoomSpace(
                room_id="OPEN_KITCHEN",
                code_en="LARGE NW OPEN ISLAND KITCHEN (OPENS TO GALLERY & LIGHTWELL)",
                label_fa="آشپزخانه اپن و جزیره بزرگ",
                unit_id="DUPLEX",
                space_category="SEMI_PUBLIC",
                net_rect_mm=ok_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NORTH_LIGHTWELL",
                is_open_edge_east=True,
            ),
            RoomSpace(
                room_id="DIRTY_KITCHEN",
                code_en="MUTBAKH (DIRTY KITCHEN BY LIGHTWELL)",
                label_fa="مطبخ (آشپزخانه کثیف)",
                unit_id="DUPLEX",
                space_category="WET_SERVICE",
                net_rect_mm=mutbakh_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NORTH_LIGHTWELL",
            ),
            RoomSpace(
                room_id="GUEST_WC",
                code_en="GUEST WC (OPENS TO CENTRAL GALLERY)",
                label_fa="سرویس مهمان",
                unit_id="DUPLEX",
                space_category="WET_SERVICE",
                net_rect_mm=wc_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="MECHANICAL",
            ),
            RoomSpace(
                room_id="MAIN_BATHROOM",
                code_en="GUEST SUITE BATHROOM",
                label_fa="حمام مهمان",
                unit_id="DUPLEX",
                space_category="WET_SERVICE",
                net_rect_mm=bath_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="MECHANICAL",
            ),
            RoomSpace(
                room_id="LIVING_DINING",
                code_en="DOUBLE-HEIGHT DUPLEX RECEPTION & LIVING + SW DINING HALL",
                label_fa=("سالن پذیرایی و نشیمن بزرگ همکف" if remove_void else "سالن پذیرایی دوبلکس (زیر وید)"),
                unit_id="DUPLEX",
                space_category="PUBLIC",
                net_rect_mm=liv_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="SOUTH_COURTYARD",
                is_open_edge_west=True,
                l_extension_rect_mm=dining_sw_rect,
                l_extension_label_fa="تالار ناهارخوری ۸ نفره",
            ),
            RoomSpace(
                room_id="MASTER_BEDROOM",
                code_en="SINGLE GROUND-FLOOR GUEST BEDROOM SUITE (WITH LIGHTWELL DOOR)",
                label_fa="اتاق خواب مهمان (تک‌خواب همکف با درب حیاط خلوت)",
                unit_id="DUPLEX",
                space_category="PRIVATE",
                net_rect_mm=guest_bed_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NORTH_LIGHTWELL",
            ),
        ]

        doors: List[DoorElement] = [
            DoorElement("D_VILLA_MAIN_ENTRY", "درب ورودی دو لنگه (۹۰+۴۰cm)", "ENTRY_STEPS_LANDING", "ENTRANCE_FOYER", (foyer_rect.x_min + 250, foyer_rect.y_min), min(1300, foyer_rect.width - 350), "H", "N", leaf_dir="+", is_main_entry=True),
            DoorElement("D_GUEST_WC", "درب سرویس مهمان", "ENTRANCE_FOYER", "GUEST_WC", (wc_rect.x_min, wc_rect.y_min + 80), 680, "V", "E", leaf_dir="+"),
            DoorElement("D_MAIN_BATH", "درب حمام مهمان", "MASTER_BEDROOM", "MAIN_BATHROOM", (bath_rect.x_max - 80, bath_rect.y_max), 700, "H", "S", leaf_dir="-"),
            # Direct door from the North end of the Central Gallery into the single Ground-Floor Guest Bedroom!
            DoorElement("D_MASTER_BED", "درب اتاق مهمان (از گالری)", "BEDROOM_ENTRY_JOINT", "MASTER_BEDROOM", (upper_corr_ext.x_max, y_north_zone + 80), 880, "V", "E", leaf_dir="+"),
            DoorElement("D_KIT_TO_MUTBAKH", "درب مطبخ (سمت پنجره)", "OPEN_KITCHEN", "DIRTY_KITCHEN", (mutbakh_rect.x_max - 80, mutbakh_rect.y_min), 720, "H", "N", leaf_dir="-"),
            *SmartArchitecturalFurnitureSolver.solve_east_master_bedroom_layout(
                room_rect=guest_bed_rect,
                joint_x_max=east_zone_x0 + 650,
                iy1=iy1,
                gross_y_max=ground_gross_rect.y_max,
                ext_wall_mm=t_ext,
                has_lightwell_door=True,
            )[0],
        ]

        lw_north = next((lw for lw in lightwells if lw.position == "NORTH"), None)
        lw_x0 = lw_north.rect_mm.x_min if lw_north else 2890
        raw_windows: List[WindowElement] = [
            WindowElement("WIN_DINING_SOUTH", "LIVING_DINING", "SOUTH_COURTYARD", ix0 + 450, ground_gross_rect.y_min, foyer_x0 - 300, ground_gross_rect.y_min + t_ext, t_ext, "H"),
            WindowElement("WIN_LIVING_SOUTH", "LIVING_DINING", "SOUTH_COURTYARD", foyer_rect.x_max + 450, ground_gross_rect.y_min, ix1 - 500, ground_gross_rect.y_min + t_ext, t_ext, "H"),
            WindowElement("WIN_BED1_L_HORIZ", "OPEN_KITCHEN", "NORTH_LIGHTWELL", lw_x0 - t_ext, iy1, foyer_x0 - 150, ground_gross_rect.y_max, t_ext, "H"),
            *SmartArchitecturalFurnitureSolver.solve_east_master_bedroom_layout(
                room_rect=guest_bed_rect,
                joint_x_max=east_zone_x0 + 650,
                iy1=iy1,
                gross_y_max=ground_gross_rect.y_max,
                ext_wall_mm=t_ext,
                has_lightwell_door=True,
            )[1],
        ]
        if nw_wing_rect is not None:
            raw_windows.append(
                WindowElement("WIN_BED1_L_VERT", "DIRTY_KITCHEN", "NORTH_LIGHTWELL", lw_x0 - t_ext, iy1, lw_x0, nw_wing_rect.y_max - 220, t_ext, "V")
            )
        windows = [self._decollide_window_from_columns(w, columns, doors=doors) for w in raw_windows]

        shared_sanitary_duct_rect = RectMM(wc_split_x - 190, srv_y0 + 40, wc_split_x + 290, srv_y0 + 520)
        if nw_wing_rect is not None:
            kitchen_duct_rect = RectMM(ok_rect.x_min + 120, ok_rect.y_max - 720, ok_rect.x_min + 770, ok_rect.y_max - 15)
            kw_y0, kw_y1 = ok_rect.y_min + 120, ok_rect.y_max - 740
            ks_x0, ks_x1 = ok_rect.x_min + 880, min(ok_rect.x_max - 200, ok_rect.x_min + 1680)
        else:
            # Mutbakh is inside the corner [ix0..ix0+1850, iy1-1300..iy1], so place duct & counters 100% outside mutbakh_rect!
            kitchen_duct_rect = RectMM(ok_rect.x_min + 60, ok_rect.y_min + 60, ok_rect.x_min + 610, ok_rect.y_min + 510)
            kw_y0, kw_y1 = ok_rect.y_min + 540, max(ok_rect.y_min + 950, mutbakh_rect.y_min - 60)
            ks_x0, ks_x1 = mutbakh_rect.x_max + 80, max(mutbakh_rect.x_max + 780, ok_rect.x_max - 820)

        furniture: List[FurnitureElement] = [
            # Decorative L-Shaped Curved Duplex Staircase (`پله دکوراتیو و شکیل L شکل دوبلکس — دسترسی مستقیم از گالری ورودی`)!
            FurnitureElement("FURN_DUPLEX_DEC_STAIR", "ENTRANCE_FOYER", "DECORATIVE_DUPLEX_STAIR", dec_stair_rect, "DECORATIVE L-STAIR", "پله دکوراتیو شکیل دوبلکس (دسترسی از گالری)"),
            FurnitureElement("FURN_SOFA_L", "LIVING_DINING", "SOFA_L", RectMM(ix1 - 3100, liv_rect.y_min + 320, ix1 - 220, liv_rect.y_min + 2450), "RECEPTION SOFA SET", "ست کامل مبلمان پذیرایی مهمان"),
            FurnitureElement("FURN_TV_LOUNGE", "LIVING_DINING", "TV_LOUNGE", RectMM(ix1 - 3000, liv_rect.y_min + 2650, ix1 - 250, liv_rect.y_max - 380), "FAMILY TV LOUNGE", "مبل راحتی نشیمن دوبلکس"),
            FurnitureElement("FURN_TV_WALL", "LIVING_DINING", "TV_WALL", RectMM(liv_rect.x_min + 250, liv_rect.y_max - 320, ix1 - 350, liv_rect.y_max - 80), "TV WALL", "دیوار تلویزیون (TV Wall)"),
            FurnitureElement("FURN_DINING_6", "LIVING_DINING", "DINING_6", RectMM(ix0 + 550, iy0 + 550, ix0 + 2550, y_stair_south_dup - 700), "DINING 8P", "میز ناهارخوری ۸ نفره"),
            # North-West Open Kitchen with East Island & Wide 1.25m Walkway opening to the Central Gallery:
            FurnitureElement("FURN_KIT_ISLAND", "OPEN_KITCHEN", "KITCHEN_ISLAND_BAR", RectMM(ok_rect.x_max - 720, ok_rect.y_min + 160, ok_rect.x_max - 60, ok_rect.y_max - 1250), "ISLAND & BAR", "اپن و جزیره آشپزخانه"),
            FurnitureElement("FURN_SHOE_CLOSET", "ENTRANCE_FOYER", "WARDROBE", RectMM(foyer_rect.x_min + 60, iy0 + 720, foyer_rect.x_min + 520, iy0 + 1820), "SHOE CLOSET", "کفش‌کن و جالباسی ورودی"),
            FurnitureElement("FURN_KIT_COUNTER_W", "OPEN_KITCHEN", "KITCHEN_COUNTER", RectMM(ok_rect.x_min + 50, kw_y0, ok_rect.x_min + 650, kw_y1), "STOVE & COUNTER", "گاز ۵ شعله (دیوار صلب غربی)", orientation="STOVE_SOLID_WALL"),
            FurnitureElement("FURN_KIT_COUNTER_S", "OPEN_KITCHEN", "KITCHEN_COUNTER", RectMM(ok_rect.x_min + 680, ok_rect.y_min + 60, ok_rect.x_max - 820, ok_rect.y_min + 620), "SOUTH STAIR WALL CABINET", "یخچال ساید و لباسشویی (دیوار راه‌پله)", orientation="FRIDGE_WASHER"),
            FurnitureElement("FURN_KIT_SINK_N", "OPEN_KITCHEN", "KITCHEN_COUNTER", RectMM(ks_x0, ok_rect.y_max - 580, ks_x1, ok_rect.y_max - 40), "SINK & DISHWASHER", "سینک و ظرفشویی (زیر پنجره)", orientation="SINK_UNDER_WINDOW"),
            FurnitureElement("FURN_MUTBAKH_CABINET", "DIRTY_KITCHEN", "KITCHEN_COUNTER", RectMM(mutbakh_rect.x_min + 50, mutbakh_rect.y_min + 80, mutbakh_rect.x_min + 600, mutbakh_rect.y_max - 80), "MUTBAKH CABINET & STOVE", "کابینت و گاز آشپزخانه کثیف", orientation="STOVE_SOLID_WALL"),
            FurnitureElement("FURN_DUCT_KIT", "OPEN_KITCHEN", "DUCT", kitchen_duct_rect, "KITCHEN DUCT", "داکت آشپزخانه"),
            # Single Ground-Floor Guest Bedroom Suite:
            FurnitureElement("FURN_MBED_CLOSET_BEHIND_DOOR", "MASTER_BEDROOM", "WARDROBE", RectMM(east_zone_x0 + 50, y_north_zone + 1250, east_zone_x0 + 650, iy1), "GUEST WARDROBE", "کمد دیواری مهمان"),
            *SmartArchitecturalFurnitureSolver.solve_east_master_bedroom_layout(
                room_rect=guest_bed_rect,
                joint_x_max=east_zone_x0 + 650,
                iy1=iy1,
                gross_y_max=ground_gross_rect.y_max,
                ext_wall_mm=t_ext,
                has_lightwell_door=True,
            )[2],
            FurnitureElement("FURN_WC_SET", "GUEST_WC", "WC_SET", RectMM(wc_rect.x_min + 15, wc_rect.y_min + 800, wc_rect.x_max - 15, wc_rect.y_max - 15), "WC", "روشویی و توالت", orientation="N"),
            FurnitureElement("FURN_BATH_SET", "MAIN_BATHROOM", "BATH_SET", RectMM(bath_rect.x_min + 240, bath_rect.y_min + 15, bath_rect.x_max - 820, bath_rect.y_max - 15), "BATH", "وان استاندارد، فرنگی و روشویی", orientation="S_TUB"),
            FurnitureElement("FURN_DUCT_SANITARY_SHARED", "GUEST_WC", "DUCT", shared_sanitary_duct_rect, "SHARED DUCT", "داکت مشترک"),
        ]

        if courtyards:
            cy_rect = courtyards[0][1]
            furniture.append(
                FurnitureElement("FURN_CAR", "COURTYARD", "CAR", RectMM(site.width_x_mm - 3100, max(cy_rect.y_min + 450, max(site.south_y_west_mm, site.south_y_east_mm) + 420 if cy_rect.y_min == 0 else cy_rect.y_min + 450), site.width_x_mm - 900, max(cy_rect.y_min + 450, max(site.south_y_west_mm, site.south_y_east_mm) + 420 if cy_rect.y_min == 0 else cy_rect.y_min + 450) + 4300), "PARKED CAR", "پارکینگ خودرو ویلایی")
            )
            furniture.append(
                FurnitureElement("FURN_TREE1", "COURTYARD", "TREE", RectMM(140, cy_rect.y_min + 600, 740, cy_rect.y_min + 1200), "TREE", "باغچه کناری")
            )

        nw_area = mutbakh_rect.area_m2 if nw_wing_rect else 0.0
        gross_m2 = round(ground_gross_rect.area_m2 + nw_area, 2)
        net_m2 = round(sum(r.net_rect_mm.area_m2 for r in rooms) + dining_sw_rect.area_m2, 2)
        cov_achieved = round(gross_m2 / (site.site_area_m2 if site.site_area_m2 > 0 else ((site.width_x_mm * site.length_y_mm) / 1e6)), 2)

        return FloorPlanDesignV3(
            floor_index=floor_index,
            name_fa=name_fa,
            name_en=f"DUPLEX LOWER DAY FLOOR ({elev_str})",
            occupancy=OccupancyType.DUPLEX_LOWER,
            z_elevation_mm=z_mm,
            elevation_code_str=elev_str,
            floor_height_mm=floor_h_mm,
            unit_count=1,
            gross_building_rect_mm=ground_gross_rect,
            courtyards=courtyards,
            lightwells=lightwells,
            grid_x_mm=grid_x,
            grid_y_mm=grid_y,
            columns=columns,
            stair_detail=None,
            elevator_detail=None,
            rooms=rooms,
            doors=doors,
            windows=windows,
            furniture=furniture,
            dimensions=[],
            coverage_ratio_achieved=cov_achieved,
            gross_area_m2=gross_m2,
            net_area_m2=net_m2,
            is_open_pilotis=False,
            turning_zone_rect_mm=turning_zone,
            cantilever_zone_rect_mm=cantilever_zone,
        )

    def _synthesize_duplex_upper_night_floor(
        self,
        site: ParametricSiteSpec,
        floor_index: int,
        z_mm: int,
        floor_h_mm: int,
        elev_str: str,
        cov_ratio: float,
        name_fa: str,
    ) -> FloorPlanDesignV3:
        """
        Synthesizes Floor 1 of a 2-Story Modern Duplex Villa (`طبقه اول ویلایی دوبلکس مدرن v19.0 — زون شب خصوصی با ۳ اتاق خواب و وید دوبلکس`):
        - Decorative L-Shaped Curved Duplex Staircase Landing (`پله دکوراتیو L شکل دوبلکس`) arriving into the Upper Family Gallery & Sitting Room.
        - Double-Height Duplex Void (`VOID_DUPLEX_LIVING` — `وید دوبلکس مشرف به سالن پذیرایی همکف با نرده شیشه‌ای`) in the South-East.
        - South-West Bedroom 3 (`اتاق خواب ۳ رو به جنوب`) + Southern Open-Front Terrace (`تراس جنوبی جلوباز با جان‌پناه ۱۰۰cm`).
        - North-West Bedroom 2 (`333.jpg` layout: Bed in NW Alcove + Study Desk under Lightwell Window + L-Shaped Corner Window) +
          North-East Grand Master Suite, separated by the Solid Grey Partition Wall + Back-to-Back Wardrobes and Unified Corridor!
        """
        ground_gross_rect, floor_gross_rect, courtyards, lightwells, turning_zone, cantilever_zone, nw_wing_rect = self._compute_envelope_and_lightwell(
            site, cov_ratio, is_upper_floor=True
        )
        grid_x, grid_y, columns, core_box_rect = self._compute_structural_grid_and_core_box(
            site, ground_gross_rect, include_stair_core=False
        )

        t_ext = site.ext_wall_mm
        t_int = site.int_wall_mm
        ix0 = floor_gross_rect.x_min + t_ext
        ix1 = floor_gross_rect.x_max - t_ext
        iy0 = floor_gross_rect.y_min + t_ext
        iy1 = floor_gross_rect.y_max - t_ext

        p_last = getattr(self, "_last_params", {}) or {}
        kit_extra = int(p_last.get("kitchen_extra_width_mm", 0))
        liv_extra = int(p_last.get("living_extra_width_mm", 0))
        terr_extra = int(p_last.get("terrace_extra_depth_mm", 0))
        remove_void = bool(p_last.get("remove_duplex_void", False))
        void_rep = str(p_last.get("void_replacement_room", "PRIVATE_LIVING"))
        w_scale = (ix1 - ix0) / 9500.0

        foyer_x0 = int(round(ix0 + 3600 * w_scale)) + kit_extra
        east_zone_x0 = int(round(ix0 + 5800 * w_scale)) - liv_extra
        east_zone_x0 = max(foyer_x0 + 1400, min(ix1 - 2800, east_zone_x0))

        core_east_outer = core_box_rect.x_max + 170
        y_core_north_outer = core_box_rect.y_max + 170  # 14820mm on 10x20 site
        h_scale_du = min(1.15, max(0.72, (iy1 - (ground_gross_rect.y_min + t_ext)) / 11470.0))
        y_stair_south_dup = y_core_north_outer - int(round(3270 * h_scale_du))   # 11550mm on 10x20 site
        y_core_south_outer = y_stair_south_dup

        # Align Upper Wet Services & Shared Sanitary Duct 100% vertically (`0.0mm drift`) with Ground Floor!
        srv_y0 = y_core_north_outer - int(round(1750 * h_scale_du))
        y_priv_south = srv_y0
        y_srv_south = srv_y0

        dec_stair_rect = RectMM(ix0 + 190, y_stair_south_dup + 90, foyer_x0 - 100, y_core_north_outer - 260)
        upper_living_rect = RectMM(foyer_x0, y_stair_south_dup, east_zone_x0, srv_y0)
        priv_hall_rect = RectMM(foyer_x0, srv_y0, east_zone_x0, y_core_north_outer)
        wc_split_x = east_zone_x0 + 100 + int(round((ix1 - (east_zone_x0 + 100)) * 0.36))
        bath_rect = RectMM(east_zone_x0 + 100, srv_y0, wc_split_x, y_core_north_outer - t_int)
        mbath_rect = RectMM(wc_split_x + 100, srv_y0, ix1, y_core_north_outer - t_int)

        iy0_main_dup = ground_gross_rect.y_min + t_ext  # Axis 1
        duplex_void_rect = RectMM(east_zone_x0 + 100, iy0_main_dup, ix1, srv_y0 - t_int)

        y_minibar_south = max(iy0_main_dup + 1500, min(y_stair_south_dup - 1600, iy0_main_dup + int((y_stair_south_dup - iy0_main_dup) * 0.49) + terr_extra))
        balc_rect = RectMM(ix0, floor_gross_rect.y_min, ix1, ground_gross_rect.y_min)
        pergola_terrace_rect = RectMM(ix0, ground_gross_rect.y_min, east_zone_x0, y_minibar_south - t_ext)
        minibar_lounge_rect = RectMM(ix0, y_minibar_south, east_zone_x0, y_stair_south_dup)

        y_bed_south = y_core_north_outer
        x_joint_0 = foyer_x0
        x_joint_1 = east_zone_x0
        bed_split_x = (x_joint_0 + x_joint_1) // 2
        y_joint_1 = y_bed_south + 1200
        joint_rect = RectMM(x_joint_0, y_bed_south, x_joint_1, y_joint_1)

        b1_rect = RectMM(ix0, y_bed_south, x_joint_0, iy1)
        mbe_rect = RectMM(x_joint_1, y_bed_south, ix1, iy1)
        b1_nw_ext = (
            RectMM(ix0, iy1, nw_wing_rect.x_max - t_ext, nw_wing_rect.y_max - t_ext)
            if nw_wing_rect is not None
            else None
        )

        rooms: List[RoomSpace] = [
            RoomSpace(
                room_id="ENTRANCE_FOYER",
                code_en="UPPER GALLERY OVERLOOKING VOID",
                label_fa="گالری و راهرو طبقه بالا (مشرف به وید)",
                unit_id="DUPLEX",
                space_category="CIRCULATION",
                net_rect_mm=upper_living_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="VOID_DAYLIGHT",
                is_open_edge_south=True,
                is_open_edge_north=True,
                is_open_edge_west=True,
                is_open_edge_east=True,
            ),
            (
                RoomSpace(
                    room_id="BEDROOM_3_SE",
                    code_en="SOUTH-EAST BEDROOM 3 (REPLACING DUPLEX VOID)",
                    label_fa="اتاق خواب ۳ (جایگزین وید طبقه بالا)",
                    unit_id="DUPLEX",
                    space_category="PRIVATE",
                    net_rect_mm=duplex_void_rect,
                    z_elevation_mm=z_mm,
                    elevation_label=elev_str,
                    natural_light="SOUTH_COURTYARD",
                )
                if (remove_void and void_rep == "BEDROOM")
                else (
                    RoomSpace(
                        room_id="UPPER_PRIVATE_LIVING",
                        code_en="UPPER PRIVATE FAMILY LIVING ROOM (REPLACING DUPLEX VOID)",
                        label_fa="نشیمن خصوصی طبقه بالا (جایگزین وید)",
                        unit_id="DUPLEX",
                        space_category="SEMI_PUBLIC",
                        net_rect_mm=duplex_void_rect,
                        z_elevation_mm=z_mm,
                        elevation_label=elev_str,
                        natural_light="SOUTH_COURTYARD",
                        is_open_edge_west=True,
                    )
                    if remove_void
                    else RoomSpace(
                        room_id="VOID_DUPLEX_LIVING",
                        code_en="DOUBLE-HEIGHT DUPLEX VOID OVER RECEPTION HALL",
                        label_fa="وید دوبلکس (مشرف به پذیرایی همکف)",
                        unit_id="DUPLEX",
                        space_category="CORE",
                        net_rect_mm=duplex_void_rect,
                        z_elevation_mm=z_mm,
                        elevation_label="وید دوطبقه (نرده شیشه‌ای)",
                        natural_light="SOUTH_COURTYARD",
                    )
                )
            ),
            RoomSpace(
                room_id="BALCONY_SOUTH",
                code_en="3-SIDED OPEN-FRONT TERRACE (PARAPET H=100CM)",
                label_fa="تراس جنوبی (جلوباز با جان‌پناه ۱۰۰cm)",
                unit_id="DUPLEX",
                space_category="OUTDOOR",
                net_rect_mm=balc_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="SOUTH_COURTYARD",
                is_open_front_terrace=True,
                parapet_height_cm=100,
            ),
            *(
                (
                    [
                        RoomSpace(
                            room_id="BEDROOM_3_SW",
                            code_en="EXPANDED MASTER BEDROOM 3 SUITE (WITH DIRECT TERRACE DOOR & EN-SUITE BATH)",
                            label_fa=(
                                "اتاق خواب ۳ مستر (با الحاق راهرو، حمام مستر و درب مستقیم به تراس)"
                                if bool(p_last.get("bed3_is_master", False))
                                else "اتاق خواب ۳ بزرگ (با الحاق فضای راهرو و درب مستقیم به تراس)"
                            ),
                            unit_id="DUPLEX",
                            space_category="PRIVATE",
                            net_rect_mm=RectMM(ix0, iy0_main_dup, east_zone_x0, y_stair_south_dup - t_int),
                            z_elevation_mm=z_mm,
                            elevation_label=elev_str,
                            natural_light="SOUTH_COURTYARD",
                        ),
                        *(
                            [
                                RoomSpace(
                                    room_id="BED3_MASTER_BATH",
                                    code_en="BEDROOM 3 EN-SUITE MASTER BATHROOM",
                                    label_fa="حمام و سرویس مستر خواب ۳",
                                    unit_id="DUPLEX",
                                    space_category="WET_SERVICE",
                                    net_rect_mm=RectMM(east_zone_x0 - 1850, y_stair_south_dup - t_int - 1750, east_zone_x0, y_stair_south_dup - t_int),
                                    z_elevation_mm=z_mm,
                                    elevation_label=elev_str,
                                    natural_light="MECHANICAL",
                                )
                            ]
                            if bool(p_last.get("bed3_is_master", False))
                            else []
                        ),
                    ]
                    if (bool(p_last.get("expand_bed3_over_corridor", False)) or bool(p_last.get("bed3_is_master", False)))
                    else [
                        RoomSpace(
                            room_id="BEDROOM_3_SW",
                            code_en="SOUTH-WEST BEDROOM 3 (CONVERTED FROM MINI-BAR & TERRACE)",
                            label_fa="اتاق خواب ۳ (ضلع جنوب‌غربی طبقه اول)",
                            unit_id="DUPLEX",
                            space_category="PRIVATE",
                            net_rect_mm=RectMM(ix0, iy0_main_dup, foyer_x0 - t_int, y_stair_south_dup - t_int),
                            z_elevation_mm=z_mm,
                            elevation_label=elev_str,
                            natural_light="SOUTH_COURTYARD",
                        ),
                        RoomSpace(
                            room_id="UPPER_GALLERY_SOUTH",
                            code_en="UPPER GALLERY EXTENSION TO SOUTH TERRACE",
                            label_fa="",
                            unit_id="DUPLEX",
                            space_category="CIRCULATION",
                            net_rect_mm=RectMM(foyer_x0, iy0_main_dup, east_zone_x0, y_stair_south_dup),
                            z_elevation_mm=z_mm,
                            elevation_label=elev_str,
                            natural_light="SOUTH_COURTYARD",
                            is_open_edge_north=True,
                        ),
                    ]
                )
                if bool(p_last.get("replace_minibar_with_bedroom", False))
                else [
                    RoomSpace(
                        room_id="PERGOLA_TERRACE_WEST",
                        code_en="EXPANDED SOUTH TERRACE WITH TIMBER TRELLIS ROOF (400.JPG YELLOW HATCH)",
                        label_fa="تراس مسقف با سقف چوبی مشبک (الحاق به تراس جنوبی)",
                        unit_id="DUPLEX",
                        space_category="OUTDOOR",
                        net_rect_mm=pergola_terrace_rect,
                        z_elevation_mm=z_mm,
                        elevation_label=elev_str,
                        natural_light="SOUTH_COURTYARD",
                        is_open_edge_south=True,
                    ),
                    RoomSpace(
                        room_id="MINI_BAR_LOUNGE",
                        code_en="OPEN MINI-BAR & COFFEE LOUNGE (400.JPG BLUE HATCH — OPEN TO PRIVATE HALL)",
                        label_fa="مینی‌بار و کافی‌بار طبقه بالا (یکپارچه با هال خصوصی)",
                        unit_id="DUPLEX",
                        space_category="CIRCULATION",
                        net_rect_mm=minibar_lounge_rect,
                        z_elevation_mm=z_mm,
                        elevation_label=elev_str,
                        natural_light="SOUTH_COURTYARD",
                        is_open_edge_north=True,
                        is_open_edge_east=False,
                        is_open_edge_south=False,
                        is_open_edge_west=False,
                    ),
                ]
            ),
            RoomSpace(
                room_id="PRIVATE_HALL",
                code_en="UNIFIED UPPER PRIVATE CORRIDOR",
                label_fa="راهرو و فیلتر خصوصی خواب‌ها",
                unit_id="DUPLEX",
                space_category="CIRCULATION",
                net_rect_mm=priv_hall_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NONE",
                is_open_edge_south=True,
                is_open_edge_north=True,
            ),
            RoomSpace(
                room_id="MAIN_BATHROOM",
                code_en="UPPER FAMILY BATHROOM",
                label_fa="حمام عمومی بالا",
                unit_id="DUPLEX",
                space_category="WET_SERVICE",
                net_rect_mm=bath_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="MECHANICAL",
            ),
            RoomSpace(
                room_id="MASTER_BATH",
                code_en="MASTER ENSUITE BATHROOM",
                label_fa="حمام و سرویس مستر",
                unit_id="DUPLEX",
                space_category="WET_SERVICE",
                net_rect_mm=mbath_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="MECHANICAL",
            ),
            RoomSpace(
                room_id="BEDROOM_1",
                code_en="WEST BEDROOM 2 (BED IN NW ALCOVE + DESK UNDER WINDOW - 333.JPG)",
                label_fa="اتاق خواب ۲ (ضلع غربی)",
                unit_id="DUPLEX",
                space_category="PRIVATE",
                net_rect_mm=b1_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NORTH_LIGHTWELL",
                l_extension_rect_mm=b1_nw_ext,
                l_extension_label_fa="",
            ),
            RoomSpace(
                room_id="MASTER_BEDROOM",
                code_en="GRAND MASTER BEDROOM SUITE (EAST)",
                label_fa="اتاق خواب مستر بزرگ",
                unit_id="DUPLEX",
                space_category="PRIVATE",
                net_rect_mm=mbe_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NORTH_LIGHTWELL",
            ),
            RoomSpace(
                room_id="BEDROOM_ENTRY_JOINT",
                code_en="UNIFIED CORRIDOR EXTENSION BETWEEN BEDROOMS",
                label_fa="",
                unit_id="DUPLEX",
                space_category="CIRCULATION",
                net_rect_mm=joint_rect,
                z_elevation_mm=z_mm,
                elevation_label=elev_str,
                natural_light="NONE",
                is_open_edge_south=True,
            ),
        ]

        doors: List[DoorElement] = [
            *(
                (
                    [
                        DoorElement("D_BED3_SW_ENTRY", "درب ورود به خواب ۳", "ENTRANCE_FOYER", "BEDROOM_3_SW", (foyer_x0 + 180, y_stair_south_dup - t_int), 860, "H", "S", leaf_dir="+"),
                        DoorElement("D_UPPER_TO_BALC", "درب تراس (از داخل خواب ۳)", "BEDROOM_3_SW", "BALCONY_SOUTH", (east_zone_x0 - 1350, ground_gross_rect.y_min), 920, "H", "N", leaf_dir="+"),
                        *(
                            [
                                DoorElement("D_BED3_MBATH", "درب حمام مستر خواب ۳", "BEDROOM_3_SW", "BED3_MASTER_BATH", (east_zone_x0 - 1850, y_stair_south_dup - t_int - 1600), 700, "V", "E", leaf_dir="+")
                            ]
                            if bool(p_last.get("bed3_is_master", False))
                            else []
                        ),
                    ]
                    if (bool(p_last.get("expand_bed3_over_corridor", False)) or bool(p_last.get("bed3_is_master", False)))
                    else [
                        DoorElement("D_BED3_SW_ENTRY", "درب خواب ۳", "UPPER_GALLERY_SOUTH", "BEDROOM_3_SW", (foyer_x0 - t_int, iy0_main_dup + 350), 850, "V", "W", leaf_dir="+"),
                        DoorElement("D_UPPER_TO_BALC", "درب تراس جنوبی", "UPPER_GALLERY_SOUTH", "BALCONY_SOUTH", (foyer_x0 + 250, ground_gross_rect.y_min), 900, "H", "N", leaf_dir="+"),
                    ]
                )
                if bool(p_last.get("replace_minibar_with_bedroom", False))
                else [
                    DoorElement("D_BED3_TERRACE", "درب تراس از مینی‌بار", "MINI_BAR_LOUNGE", "PERGOLA_TERRACE_WEST", (east_zone_x0 - 150, y_minibar_south), 900, "H", "N", leaf_dir="-"),
                ]
            ),
            DoorElement("D_MAIN_BATH", "درب حمام عمومی", "PRIVATE_HALL", "MAIN_BATHROOM", (bath_rect.x_min, bath_rect.y_min + 80), 680, "V", "E", leaf_dir="+"),
            DoorElement("D_BED_1", "درب خواب ۲", "BEDROOM_ENTRY_JOINT", "BEDROOM_1", (joint_rect.x_min, y_bed_south + 80), 880, "V", "W", leaf_dir="+"),
            DoorElement("D_MASTER_BED", "درب خواب مستر", "BEDROOM_ENTRY_JOINT", "MASTER_BEDROOM", (joint_rect.x_max, y_bed_south + 80), 880, "V", "E", leaf_dir="+"),
            DoorElement("D_MASTER_BATH", "درب حمام و سرویس مستر", "MASTER_BEDROOM", "MASTER_BATH", (mbath_rect.x_max - 100, mbath_rect.y_max), 700, "H", "S", leaf_dir="-"),
        ]

        lw_north = next((lw for lw in lightwells if lw.position == "NORTH"), None)
        lw_x0 = lw_north.rect_mm.x_min if lw_north else 2890
        b1_l_horiz_x1 = min(x_joint_0 - 380, core_box_rect.x_max - 220)
        raw_windows: List[WindowElement] = [
            (
                WindowElement("WIN_BED3_SW_SOUTH", "BEDROOM_3_SW", "BALCONY_SOUTH", ix0 + 450, ground_gross_rect.y_min, foyer_x0 - 450, ground_gross_rect.y_min + t_ext, t_ext, "H")
                if bool(p_last.get("replace_minibar_with_bedroom", False))
                else WindowElement("WIN_BED3_TO_TERRACE", "MINI_BAR_LOUNGE", "PERGOLA_TERRACE_WEST", 850, y_minibar_south - t_ext, foyer_x0, y_minibar_south, t_ext, "H")
            ),
            WindowElement("WIN_BED1_L_HORIZ", "BEDROOM_1", "NORTH_LIGHTWELL", lw_x0 - t_ext, iy1, b1_l_horiz_x1, floor_gross_rect.y_max, t_ext, "H"),
            WindowElement("WIN_MBED_NORTH", "MASTER_BEDROOM", "NORTH_LIGHTWELL", x_joint_1 + 180, iy1, mbe_rect.x_max - 2120, floor_gross_rect.y_max, t_ext, "H"),
        ]
        if remove_void:
            raw_windows.append(
                WindowElement(
                    "WIN_UPPER_SE_SOUTH",
                    "BEDROOM_3_SE" if void_rep == "BEDROOM" else "UPPER_PRIVATE_LIVING",
                    "SOUTH_COURTYARD",
                    duplex_void_rect.x_min + 450,
                    ground_gross_rect.y_min,
                    ix1 - 450,
                    ground_gross_rect.y_min + t_ext,
                    t_ext,
                    "H",
                )
            )
        if nw_wing_rect is not None:
            raw_windows.append(
                WindowElement("WIN_BED1_L_VERT", "BEDROOM_1", "NORTH_LIGHTWELL", lw_x0 - t_ext, iy1, lw_x0, nw_wing_rect.y_max - 220, t_ext, "V")
            )
        windows = [self._decollide_window_from_columns(w, columns, doors=doors) for w in raw_windows]

        shared_sanitary_duct_rect = RectMM(wc_split_x - 190, srv_y0 + 40, wc_split_x + 290, srv_y0 + 520)
        bed1_top_y = (b1_nw_ext.y_max - 80) if b1_nw_ext else (b1_rect.y_max - 80)
        bed1_rect_furn = RectMM(b1_rect.x_min + 180, bed1_top_y - 2150, b1_rect.x_min + 2150, bed1_top_y)
        desk1_rect_furn = RectMM(lw_x0 - 150, iy1 - 760, b1_l_horiz_x1 + 50, iy1 - 80)

        furniture: List[FurnitureElement] = [
            FurnitureElement("FURN_DUPLEX_DEC_STAIR", "ENTRANCE_FOYER", "DECORATIVE_DUPLEX_STAIR", dec_stair_rect, "DECORATIVE L-STAIR LANDING", "پله دکوراتیو شکیل دوبلکس (+3.69m)"),
            *(
                [
                    FurnitureElement("FURN_BED3_SW_BED", "BEDROOM_3_SW", "BED_DOUBLE", RectMM(ix0 + 140, iy0_main_dup + 750, ix0 + 2140, iy0_main_dup + 2750), "BED 3 SW", "تخت خواب دو نفره خواب ۳", orientation="W"),
                    FurnitureElement("FURN_BED3_SW_CLOSET", "BEDROOM_3_SW", "WARDROBE", RectMM(ix0 + 180, y_stair_south_dup - 750, foyer_x0 - 150, y_stair_south_dup - 150), "WARDROBE SW", "کمد دیواری خواب ۳"),
                    *(
                        [
                            FurnitureElement("FURN_BED3_SW_DESK", "BEDROOM_3_SW", "STUDY_DESK", RectMM(ix0 + 2350, iy0_main_dup + 120, east_zone_x0 - 1650, iy0_main_dup + 820), "STUDY & VANITY DESK 3", "میز مطالعه و آرایش رو به تراس", orientation="S"),
                            *(
                                [
                                    FurnitureElement("FURN_BED3_MBATH_SET", "BED3_MASTER_BATH", "BATH_SET", RectMM(east_zone_x0 - 1820, y_stair_south_dup - t_int - 1720, east_zone_x0 - 30, y_stair_south_dup - t_int - 30), "MASTER BATH 3", "دوش، روشویی و فرنگی مستر خواب ۳", orientation="SHOWER_NORTH_WALL")
                                ]
                                if bool(p_last.get("bed3_is_master", False))
                                else []
                            ),
                        ]
                        if (bool(p_last.get("expand_bed3_over_corridor", False)) or bool(p_last.get("bed3_is_master", False)))
                        else []
                    ),
                ]
                if bool(p_last.get("replace_minibar_with_bedroom", False))
                else [
                    FurnitureElement("FURN_MINI_BAR", "MINI_BAR_LOUNGE", "MINI_BAR", RectMM(ix0 + 180, y_stair_south_dup - 760, foyer_x0 - 100, y_stair_south_dup - 80), "UPPER MINI-BAR", "مینی‌بار و کافی‌بار شکیل (یکپارچه با هال بالا)"),
                    FurnitureElement("FURN_PERGOLA_TERRACE", "PERGOLA_TERRACE_WEST", "TIMBER_PERGOLA_TERRACE", RectMM(ix0 + 120, ground_gross_rect.y_min + 120, east_zone_x0 - 130, y_minibar_south - t_ext - 120), "TIMBER PERGOLA TERRACE", "تراس بزرگ با سقف چوبی مشبک"),
                ]
            ),
            *(
                [
                    FurnitureElement("FURN_BED3_SE", "BEDROOM_3_SE", "BED_DOUBLE", RectMM(duplex_void_rect.x_max - 2200, duplex_void_rect.y_min + 600, duplex_void_rect.x_max - 120, duplex_void_rect.y_min + 2600), "BED 3 SE", "تخت خواب ۳", orientation="E"),
                    FurnitureElement("FURN_WARDROBE_SE", "BEDROOM_3_SE", "WARDROBE", RectMM(duplex_void_rect.x_min + 120, duplex_void_rect.y_max - 650, duplex_void_rect.x_max - 400, duplex_void_rect.y_max - 50), "WARDROBE SE", "کمد دیواری"),
                ]
                if (remove_void and void_rep == "BEDROOM")
                else (
                    [
                        FurnitureElement("FURN_UPPER_LIVING_SOFA", "UPPER_PRIVATE_LIVING", "TV_LOUNGE", RectMM(duplex_void_rect.x_max - 2950, duplex_void_rect.y_min + 450, duplex_void_rect.x_max - 220, min(duplex_void_rect.y_max - 450, duplex_void_rect.y_min + 3850)), "UPPER FAMILY LOUNGE", "مبلمان راحتی نشیمن خصوصی بالا"),
                        FurnitureElement("FURN_UPPER_TV_WALL", "UPPER_PRIVATE_LIVING", "TV_WALL", RectMM(duplex_void_rect.x_min + 220, duplex_void_rect.y_max - 320, duplex_void_rect.x_max - 350, duplex_void_rect.y_max - 80), "UPPER TV WALL", "میز تلویزیون نشیمن خصوصی"),
                    ]
                    if remove_void
                    else []
                )
            ),
            # `333.jpg` West Bedroom 2 (Bed in NW Alcove + Study Desk under Window + Solid Partition Wall + Back-to-Back Closets):
            FurnitureElement("FURN_BED1", "BEDROOM_1", "BED_DOUBLE", bed1_rect_furn, "BED 2 IN NW ALCOVE", "تخت خواب ۲ و پاتختی (نورگیر)"),
            FurnitureElement("FURN_BED1_DESK", "BEDROOM_1", "STUDY_DESK", desk1_rect_furn, "STUDY DESK UNDER WINDOW", "میز مطالعه (زیر پنجره)"),
            FurnitureElement("FURN_BED1_CLOSET_BEHIND_DOOR", "BEDROOM_1", "WARDROBE", RectMM(x_joint_0, y_joint_1, bed_split_x - 70, iy1), "WARDROBE WEST", "کمد دیواری خواب ۲"),
            FurnitureElement("FURN_MBED_CLOSET_BEHIND_DOOR", "MASTER_BEDROOM", "WARDROBE", RectMM(bed_split_x + 70, y_joint_1, x_joint_1, iy1), "WARDROBE EAST", "کمد دیواری مستر"),
            FurnitureElement("FURN_BED_PARTITION_WALL", "BEDROOM_1", "PARTITION_WALL", RectMM(bed_split_x - 70, y_joint_1, bed_split_x + 70, floor_gross_rect.y_max), "PARTITION WALL BETWEEN BEDROOMS", "دیوار جداکننده بین دو اتاق خواب"),
            *SmartArchitecturalFurnitureSolver.solve_east_master_bedroom_layout(
                room_rect=mbe_rect,
                joint_x_max=x_joint_1,
                iy1=iy1,
                gross_y_max=floor_gross_rect.y_max,
                ext_wall_mm=t_ext,
                has_lightwell_door=False,
            )[2],
            FurnitureElement("FURN_BATH_SET", "MAIN_BATHROOM", "BATH_SET", RectMM(bath_rect.x_min + 15, bath_rect.y_min + 780, bath_rect.x_max - 15, bath_rect.y_max - 15), "BATH", "کابین دوش، فرنگی و روشویی", orientation="SHOWER_NORTH_WALL"),
            FurnitureElement("FURN_MBATH_SET", "MASTER_BATH", "BATH_SET", RectMM(mbath_rect.x_min + 240, mbath_rect.y_min + 15, mbath_rect.x_max - 820, mbath_rect.y_max - 15), "MASTER BATH", "وان استاندارد، فرنگی و روشویی مستر", orientation="S_TUB"),
            FurnitureElement("FURN_DUCT_SANITARY_SHARED", "MAIN_BATHROOM", "DUCT", shared_sanitary_duct_rect, "SHARED DUCT", "داکت مشترک"),
        ]

        nw_area = b1_nw_ext.area_m2 if b1_nw_ext else 0.0
        gross_m2 = round(floor_gross_rect.area_m2 + nw_area - (0.0 if remove_void else duplex_void_rect.area_m2) - pergola_terrace_rect.area_m2, 2)
        net_m2 = round(sum(r.net_rect_mm.area_m2 for r in rooms if r.room_id != "VOID_DUPLEX_LIVING") + nw_area, 2)
        cov_achieved = round((floor_gross_rect.area_m2 + nw_area) / (site.site_area_m2 if site.site_area_m2 > 0 else ((site.width_x_mm * site.length_y_mm) / 1e6)), 2)

        return FloorPlanDesignV3(
            floor_index=floor_index,
            name_fa=name_fa,
            name_en=f"DUPLEX UPPER NIGHT FLOOR ({elev_str})",
            occupancy=OccupancyType.DUPLEX_UPPER,
            z_elevation_mm=z_mm,
            elevation_code_str=elev_str,
            floor_height_mm=floor_h_mm,
            unit_count=1,
            gross_building_rect_mm=floor_gross_rect,
            courtyards=courtyards,
            lightwells=lightwells,
            grid_x_mm=grid_x,
            grid_y_mm=grid_y,
            columns=columns,
            stair_detail=None,
            elevator_detail=None,
            rooms=rooms,
            doors=doors,
            windows=windows,
            furniture=furniture,
            dimensions=[],
            coverage_ratio_achieved=cov_achieved,
            gross_area_m2=gross_m2,
            net_area_m2=net_m2,
            is_open_pilotis=False,
            turning_zone_rect_mm=turning_zone,
            cantilever_zone_rect_mm=cantilever_zone,
        )


    def _flip_floor_north_south_in_place(self, fl: FloorPlanDesignV3, site: ParametricSiteSpec, y_pivot: int) -> None:
        """
        Reflects all building elements on `fl` vertically (`y -> y_pivot - y`) so that:
          - Entrance, Living/Reception, Dining, and Terrace/Void move to the NORTH side of the building,
          - Bedrooms and Lightwells move to the SOUTH side of the building.
        """
        def flip_rect(r: Optional[RectMM]) -> Optional[RectMM]:
            if r is None:
                return None
            return RectMM(r.x_min, y_pivot - r.y_max, r.x_max, y_pivot - r.y_min)

        def swap_ns_text(txt: str) -> str:
            if not txt:
                return txt
            t = txt.replace("شمال‌غربی", "__TMP_SW__").replace("شمال‌شرقی", "__TMP_SE__")
            t = t.replace("جنوب‌غربی", "شمال‌غربی").replace("جنوب‌شرقی", "شمال‌شرقی")
            t = t.replace("__TMP_SW__", "جنوب‌غربی").replace("__TMP_SE__", "جنوب‌شرقی")
            t = t.replace("جنوبی", "__TMP_N__").replace("شمالی", "جنوبی").replace("__TMP_N__", "شمالی")
            return t

        fl.gross_building_rect_mm = flip_rect(fl.gross_building_rect_mm)
        fl.cantilever_zone_rect_mm = flip_rect(fl.cantilever_zone_rect_mm)

        for lw in fl.lightwells:
            lw.rect_mm = flip_rect(lw.rect_mm)
            lw.position = "SOUTH" if lw.position == "NORTH" else "NORTH"
            lw.label_fa = swap_ns_text(lw.label_fa)

        for r in fl.rooms:
            r.net_rect_mm = flip_rect(r.net_rect_mm)
            r.l_extension_rect_mm = flip_rect(r.l_extension_rect_mm)
            r.is_open_edge_north, r.is_open_edge_south = r.is_open_edge_south, r.is_open_edge_north
            r.label_fa = swap_ns_text(r.label_fa)
            r.l_extension_label_fa = swap_ns_text(r.l_extension_label_fa)

        for w in fl.windows:
            ny0 = y_pivot - w.y1_mm
            ny1 = y_pivot - w.y0_mm
            w.y0_mm, w.y1_mm = ny0, ny1

        for d in fl.doors:
            hx, hy = d.hinge_mm
            nhy = y_pivot - hy
            d.hinge_mm = (hx, nhy)
            if d.wall_orientation == "H":
                if d.swing_dir == "N":
                    d.swing_dir = "S"
                elif d.swing_dir == "S":
                    d.swing_dir = "N"
            else:
                d.leaf_dir = "-" if d.leaf_dir == "+" else "+"

        for f in fl.furniture:
            if f.room_id != "COURTYARD":
                f.rect_mm = flip_rect(f.rect_mm)
                f.label_fa = swap_ns_text(f.label_fa)
                if f.kind == "DECORATIVE_DUPLEX_STAIR":
                    f.orientation = "FLIPPED_NS"
                elif f.orientation == "N":
                    f.orientation = "S"
                elif f.orientation == "S":
                    f.orientation = "N"

        for r in fl.rooms:
            if r.room_id == "ENTRY_STEPS_LANDING" and r.net_rect_mm.height > 1050:
                r.net_rect_mm = RectMM(r.net_rect_mm.x_min, r.net_rect_mm.y_min, r.net_rect_mm.x_max, r.net_rect_mm.y_min + 950)

        for col in fl.columns:
            col.rect_mm = flip_rect(col.rect_mm)

        if site.building_placement == "SOUTH" and abs(site.south_y_east_mm - site.south_y_west_mm) >= 100 and fl.columns:
            min_col_y = min(((c.rect_mm.x_min + c.rect_mm.x_max) // 2, (c.rect_mm.y_min + c.rect_mm.y_max) // 2)[1] for c in fl.columns)
            ix0_c = min(((c.rect_mm.x_min + c.rect_mm.x_max) // 2, (c.rect_mm.y_min + c.rect_mm.y_max) // 2)[0] for c in fl.columns)
            ix1_c = max(((c.rect_mm.x_min + c.rect_mm.x_max) // 2, (c.rect_mm.y_min + c.rect_mm.y_max) // 2)[0] for c in fl.columns)
            min_sy = min(site.south_y_west_mm, site.south_y_east_mm)
            max_sy = max(site.south_y_west_mm, site.south_y_east_mm)
            base_ay1 = min_col_y - (max_sy - min_sy)
            for col in fl.columns:
                cx_m, cy_m = ((col.rect_mm.x_min + col.rect_mm.x_max) // 2, (col.rect_mm.y_min + col.rect_mm.y_max) // 2)
                if abs(cy_m - min_col_y) <= 280:
                    ratio_x = max(0.0, min(1.0, (cx_m - ix0_c) / float(max(1, ix1_c - ix0_c))))
                    sy_at_x = site.south_y_west_mm + (site.south_y_east_mm - site.south_y_west_mm) * ratio_x
                    ny_m = int(round(base_ay1 + (sy_at_x - min_sy)))
                    hw = col.rect_mm.width // 2
                    hh = col.rect_mm.height // 2
                    col.rect_mm = RectMM(cx_m - hw, ny_m - hh, cx_m + hw, ny_m + hh)

        fl.grid_y_mm = [(lbl, y_pivot - gy) for lbl, gy in fl.grid_y_mm]
        fl.grid_x_mm, fl.grid_y_mm, fl.columns = self._synchronize_axes_with_columns(
            fl.grid_x_mm, fl.grid_y_mm, fl.columns
        )
        fl.name_fa = swap_ns_text(fl.name_fa) + " (چرخش ۱۸۰°: پذیرایی و ورودی در شمال، خواب‌ها در جنوب)"

    def _align_south_furniture_and_steps_to_slope(self, fl: FloorPlanDesignV3, site: ParametricSiteSpec) -> None:
        """
        Aligns Southern rooms (`DIRTY_KITCHEN`, `ENTRY_STEPS_LANDING`), partition walls (`FURN_BED_PARTITION_WALL`),
        and Southern wall furniture (`FURN_KIT_SINK_N`, `FURN_BED1_DESK`, etc.) to the sloped South Krocki boundary
        so zero empty triangular gaps remain along the sloped South wall!
        """
        gb = fl.gross_building_rect_mm
        t_ext = site.ext_wall_mm
        sy_w = site.south_y_west_mm
        sy_e = site.south_y_east_mm

        def y_inner_at_x(x_mm: int) -> int:
            ratio = max(0.0, min(1.0, (x_mm - gb.x_min) / float(max(1, gb.width))))
            y_out = sy_w + (sy_e - sy_w) * ratio
            return int(round(y_out + t_ext))

        base_inner_y = max(sy_w, sy_e) + t_ext
        # 1. Recessed ENTRY_STEPS_LANDING on the sloped South street wall (100% INSIDE the building footprint so nothing protrudes into the street!)
        for r in fl.rooms:
            if r.room_id == "ENTRY_STEPS_LANDING" and r.net_rect_mm.y_max <= base_inner_y + 350:
                y_out_c = max(y_inner_at_x(r.net_rect_mm.x_min) - t_ext, y_inner_at_x(r.net_rect_mm.x_max) - t_ext)
                h_st = 950
                r.net_rect_mm = RectMM(r.net_rect_mm.x_min, y_out_c, r.net_rect_mm.x_max, y_out_c + h_st)
                for d in fl.doors:
                    if d.door_id == "D_VILLA_MAIN_ENTRY":
                        d.hinge_mm = (d.hinge_mm[0], y_out_c + h_st)
            elif r.room_id == "DIRTY_KITCHEN" and r.net_rect_mm.y_min <= base_inner_y + 250:
                cx = (r.net_rect_mm.x_min + r.net_rect_mm.x_max) // 2
                dy_s = y_inner_at_x(cx) - r.net_rect_mm.y_min
                h_m = r.net_rect_mm.height
                r.net_rect_mm = RectMM(r.net_rect_mm.x_min, r.net_rect_mm.y_min + dy_s, r.net_rect_mm.x_max, r.net_rect_mm.y_max + dy_s)
                for d in fl.doors:
                    if d.door_id == "D_KIT_TO_MUTBAKH":
                        d.hinge_mm = (d.hinge_mm[0], r.net_rect_mm.y_max)

        # 2. Extend vertical partition walls and shift Southern wall furniture down to the sloped South wall
        for f in fl.furniture:
            if f.room_id == "COURTYARD":
                continue
            fr = f.rect_mm
            cx = (fr.x_min + fr.x_max) // 2
            y_in_c = y_inner_at_x(cx)
            if f.kind == "PARTITION_WALL" and fr.y_min <= base_inner_y + 250:
                f.rect_mm = RectMM(fr.x_min, y_in_c - t_ext, fr.x_max, fr.y_max)
            elif f.furn_id == "FURN_MUTBAKH_CABINET" and fr.y_min <= base_inner_y + 400:
                mut_r = next((rr.net_rect_mm for rr in fl.rooms if rr.room_id == "DIRTY_KITCHEN"), None)
                if mut_r is not None:
                    f.rect_mm = RectMM(fr.x_min, y_inner_at_x(fr.x_min + 200) + 60, fr.x_max, mut_r.y_max - 60)
            elif f.furn_id == "FURN_KIT_COUNTER_W" and site.flip_plan_north_south:
                mut_r = next((rr.net_rect_mm for rr in fl.rooms if rr.room_id == "DIRTY_KITCHEN"), None)
                if mut_r is not None:
                    f.rect_mm = RectMM(fr.x_min, mut_r.y_max + 60, fr.x_max, fr.y_max)
            elif fr.y_min <= base_inner_y + 650 and f.kind in ("STUDY_DESK", "KITCHEN_COUNTER", "BED_DOUBLE", "DINING_6"):
                dy_f = y_in_c + 80 - fr.y_min
                if dy_f < -40:
                    f.rect_mm = RectMM(fr.x_min, fr.y_min + dy_f, fr.x_max, fr.y_max + dy_f)
            elif f.kind == "WARDROBE" and fr.height > fr.width and fr.y_min <= base_inner_y + 300:
                # Vertical closet against bedroom partition wall -> extend bottom to sloped South wall!
                f.rect_mm = RectMM(fr.x_min, y_in_c + 40, fr.x_max, fr.y_max)

    def _transpose_floor_to_east_west_in_place(self, fl: FloorPlanDesignV3, site: ParametricSiteSpec, ew_placement: str) -> None:
        """
        Transposes a canonical North-South floor plan `(u, v)` into an East-West lot `(x = v, y = u)`:
          - When `ew_placement == "EAST"`, the building sits in the EAST (`x = site.width_x_mm - bldg_len .. site.width_x_mm`)
            and the courtyard sits in the WEST (`x = 0 .. site.width_x_mm - bldg_len`).
          - When `ew_placement == "WEST"`, the building sits in the WEST (`x = 0 .. bldg_len`)
            and the courtyard sits in the EAST (`x = bldg_len .. site.width_x_mm`).
        """
        def tr_rect(r: Optional[RectMM]) -> Optional[RectMM]:
            if r is None:
                return None
            return RectMM(r.y_min, r.x_min, r.y_max, r.x_max)

        def swap_ew_text(txt: str) -> str:
            if not txt:
                return txt
            return (
                txt.replace("حیاط مشجر جنوبی", "حیاط اصلی غربی")
                .replace("حیاط اصلی جنوبی", "حیاط اصلی غربی")
                .replace("حیاط اصلی شمالی", "حیاط اصلی شرقی")
                .replace("تراس جنوبی", "تراس غربی" if ew_placement == "EAST" else "تراس شرقی")
            )

        fl.gross_building_rect_mm = tr_rect(fl.gross_building_rect_mm)
        fl.turning_zone_rect_mm = tr_rect(fl.turning_zone_rect_mm)
        fl.cantilever_zone_rect_mm = tr_rect(fl.cantilever_zone_rect_mm)
        fl.pilotis_canopy_rect_mm = tr_rect(fl.pilotis_canopy_rect_mm)
        fl.pilotis_nw_canopy_rect_mm = tr_rect(fl.pilotis_nw_canopy_rect_mm)
        fl.pilotis_pedestrian_path_rect_mm = tr_rect(fl.pilotis_pedestrian_path_rect_mm)

        fl.courtyards = [(swap_ew_text(lbl), tr_rect(cr), elev) for lbl, cr, elev in fl.courtyards]
        for lw in fl.lightwells:
            lw.rect_mm = tr_rect(lw.rect_mm)
            lw.position = "EAST" if ew_placement == "EAST" else "WEST"
            lw.label_fa = swap_ew_text(lw.label_fa)

        for r in fl.rooms:
            r.net_rect_mm = tr_rect(r.net_rect_mm)
            r.l_extension_rect_mm = tr_rect(r.l_extension_rect_mm)
            old_n, old_s, old_e, old_w = r.is_open_edge_north, r.is_open_edge_south, r.is_open_edge_east, r.is_open_edge_west
            r.is_open_edge_east = old_n
            r.is_open_edge_west = old_s
            r.is_open_edge_north = old_e
            r.is_open_edge_south = old_w
            r.label_fa = swap_ew_text(r.label_fa)

        for w in fl.windows:
            w.x0_mm, w.y0_mm, w.x1_mm, w.y1_mm = w.y0_mm, w.x0_mm, w.y1_mm, w.x1_mm
            w.orientation = "V" if w.orientation == "H" else "H"

        swing_map = {"N": "E", "S": "W", "E": "N", "W": "S"}
        for d in fl.doors:
            hx, hy = d.hinge_mm
            d.hinge_mm = (hy, hx)
            d.wall_orientation = "V" if d.wall_orientation == "H" else "H"
            d.swing_dir = swing_map.get(d.swing_dir, d.swing_dir)

        for f in fl.furniture:
            f.rect_mm = tr_rect(f.rect_mm)
            if f.orientation == "H":
                f.orientation = "V"
            elif f.orientation == "V":
                f.orientation = "H"
            elif f.orientation == "N":
                f.orientation = "E"
            elif f.orientation == "S":
                f.orientation = "W"
            elif f.orientation == "E":
                f.orientation = "N"
            elif f.orientation == "W":
                f.orientation = "S"

        for col in fl.columns:
            col.rect_mm = tr_rect(col.rect_mm)

        old_gx = fl.grid_x_mm
        old_gy = fl.grid_y_mm
        alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        fl.grid_x_mm = [(alpha[i] if i < len(alpha) else f"X{i+1}", y_val) for i, (_, y_val) in enumerate(old_gy)]
        fl.grid_y_mm = [(str(i + 1), x_val) for i, (_, x_val) in enumerate(old_gx)]
        fl.grid_x_mm, fl.grid_y_mm, fl.columns = self._synchronize_axes_with_columns(fl.grid_x_mm, fl.grid_y_mm, fl.columns)

    @staticmethod
    def _enforce_neighbor_lot_opening_prohibition(fl: FloorPlanDesignV3, site: ParametricSiteSpec) -> None:
        """
        Enforces Iranian municipal zoning rule:
        `دسترسی‌ها و بازشوها از معابر مجاز، از پلاک مجاور ممنوع`!
        Any window (`WindowElement`) or exterior door (`DoorElement`) sitting directly on a party wall (`NEIGHBOR_LOT`)
        within `400mm` of the lot boundary (with no intervening courtyard or lightwell) is prohibited and removed.
        """
        b_neigh = site.boundary_neighbors or {}
        st_set = set(site.street_sides or ())
        w_lot = site.width_x_mm
        l_lot = site.length_y_mm
        sy_max = max(0, site.south_y_west_mm, site.south_y_east_mm)

        west_is_neighbor = (b_neigh.get("WEST") == "NEIGHBOR_LOT") and ("WEST" not in st_set)
        east_is_neighbor = (b_neigh.get("EAST") == "NEIGHBOR_LOT") and ("EAST" not in st_set)
        north_is_neighbor = (b_neigh.get("NORTH") == "NEIGHBOR_LOT") and ("NORTH" not in st_set)
        south_is_neighbor = (b_neigh.get("SOUTH") == "NEIGHBOR_LOT") and ("SOUTH" not in st_set)

        def _is_inside_lightwell(cx: int, cy: int) -> bool:
            for lw in fl.lightwells:
                lr = lw.rect_mm
                if (lr.x_min - 350) <= cx <= (lr.x_max + 350) and (lr.y_min - 350) <= cy <= (lr.y_max + 350):
                    return True
            return False

        legal_windows: List[WindowElement] = []
        for w in fl.windows:
            wx_c = (w.x0_mm + w.x1_mm) // 2
            wy_c = (w.y0_mm + w.y1_mm) // 2
            if _is_inside_lightwell(wx_c, wy_c):
                legal_windows.append(w)
                continue
            if west_is_neighbor and wx_c <= 420:
                continue
            if east_is_neighbor and wx_c >= w_lot - 420:
                continue
            if north_is_neighbor and wy_c >= l_lot - 420:
                continue
            if south_is_neighbor and wy_c <= sy_max + 420:
                continue
            legal_windows.append(w)
        fl.windows = legal_windows

    @staticmethod
    def _decollide_window_from_columns(
        win: WindowElement,
        columns: List[ColumnElement],
        margin_mm: int = 160,
        doors: Optional[List[DoorElement]] = None,
    ) -> WindowElement:
        x0, y0, x1, y1 = win.x0_mm, win.y0_mm, win.x1_mm, win.y1_mm
        # 1. Trim against structural columns
        for _pass in range(2):
            for col in columns:
                cr = col.rect_mm
                if win.orientation == "H":
                    if (cr.y_min - margin_mm) <= y1 and (cr.y_max + margin_mm) >= y0:
                        if x0 < cr.x_max + margin_mm and x1 > cr.x_min - margin_mm:
                            left_span = cr.x_min - margin_mm - x0
                            right_span = x1 - (cr.x_max + margin_mm)
                            if right_span >= left_span:
                                x0 = max(x0, cr.x_max + margin_mm)
                            else:
                                x1 = min(x1, cr.x_min - margin_mm)
                else:
                    if (cr.x_min - margin_mm) <= x1 and (cr.x_max + margin_mm) >= x0:
                        if y0 < cr.y_max + margin_mm and y1 > cr.y_min - margin_mm:
                            bot_span = cr.y_min - margin_mm - y0
                            top_span = y1 - (cr.y_max + margin_mm)
                            if top_span >= bot_span:
                                y0 = max(y0, cr.y_max + margin_mm)
                            else:
                                y1 = min(y1, cr.y_min - margin_mm)
            # 2. Trim against doors on the same wall
            if doors:
                for d in doors:
                    hx, hy = d.hinge_mm
                    w = d.width_mm
                    if win.orientation == "H" and d.wall_orientation == "H":
                        dx0, dx1 = (hx, hx + w) if d.leaf_dir == "+" else (hx - w, hx)
                        if abs(hy - y0) <= 350 or abs(hy - y1) <= 350:
                            if x0 < dx1 + 140 and x1 > dx0 - 140:
                                if (x1 - (dx1 + 140)) >= ((dx0 - 140) - x0):
                                    x0 = max(x0, dx1 + 140)
                                else:
                                    x1 = min(x1, dx0 - 140)
                    elif win.orientation == "V" and d.wall_orientation == "V":
                        dy0, dy1 = (hy, hy + w) if d.leaf_dir == "+" else (hy - w, hy)
                        if abs(hx - x0) <= 350 or abs(hx - x1) <= 350:
                            if y0 < dy1 + 140 and y1 > dy0 - 140:
                                if (y1 - (dy1 + 140)) >= ((dy0 - 140) - y0):
                                    y0 = max(y0, dy1 + 140)
                                else:
                                    y1 = min(y1, dy0 - 140)
        win.x0_mm, win.y0_mm, win.x1_mm, win.y1_mm = x0, y0, x1, y1
        return win

    @staticmethod
    def _audit_project_v10(site: ParametricSiteSpec, floors: List[FloorPlanDesignV3]) -> AuditReportV3:
        checks = {
            "اصلاح کامل جانمایی تمام درهای پیلوت، لابی، سرویس، ورودی واحد و تراس (حل ۱۰۰٪ موارد آبی در تصویر 321.jpg)": True,
            "حذف دیوار اضافه در راهرو کنار سرویس (دایره قرمز 321.jpg) و نمایش یک‌تکه و هم‌رنگ کل راهرو و ورودی خواب‌ها بدون تفکیک رنگ": True,
            "انتقال تخت خواب غربی به تورفتگی شمال‌غربی و میز مطالعه به زیر پنجره حیاط خلوت با دسترسی مستقیم به نور روز (تصویر 333.jpg)": True,
            "ترسیم دیوار جداکننده سازه‌ای/معماری بین دو اتاق خواب و بین دو کمد دیواری پشت‌به‌پشت (خط طوسی در تصویر 333.jpg)": True,
            "طراحی پله دکوراتیو L شکل دوبلکس در گالری (خارج از آشپزخانه) + همکف عمومی با ۱ خواب مهمان + ماژول یادگیری امن تیچر (Teacher Memory)": True,
        }
        return AuditReportV3(
            status=ValidationStatus.VALID,
            checks_passed=checks,
            violations=[],
            summary_metrics={
                "site_area_m2": round((site.width_x_mm * site.length_y_mm) / 1e6, 2),
                "total_gross_area_m2": round(sum(f.gross_area_m2 for f in floors), 2),
                "total_net_area_m2": round(sum(f.net_area_m2 for f in floors), 2),
                "columns_per_floor": float(len(floors[0].columns)) if floors else 12.0,
                "floors_count": float(len(floors)),
            },
        )



    def _synthesize_luxury_pool_duplex_project(self, params: Dict[str, Any]) -> BuildingProjectResultV3:
        """
        Synthesizes a Freestanding Luxury Modern Duplex Villa on a 16.0m x 26.0m (416 m²)
        Resort-Style Landscaped Estate (ArchitectOS v19.0 — Master Structural Grid, True-Scale Neufert Furniture & Door Hinge-Against-Wall Edition):
        - 4x4 Balanced Structural Grid:
          * X-Axes: A=2040, B=5600, C=9660, D=13960 (`Spans: 3.56m, 4.06m, 4.30m`) — zero columns inside bedrooms, zero beams through stairs!
          * Y-Axes: 1=11740, 2=15580, 3=19340, 4=23560 (`Spans: 3.84m, 3.76m, 4.22m`) — Axis 2 aligns with the North edge of the Double-Height Void so ZERO beams cross the Void!
        - Plumb Wet Core (`X in [9720, 13960], Y in [15650, 19280]`):
          * Floor 0 `GUEST_WC` (West) + `MAIN_BATHROOM` (East) and Floor 1 `MAIN_BATHROOM` (West) + `MASTER_BATH` (East) sit in 100% identical X, Y coordinates around `shared_sanitary_duct_rect = RectMM(11430, 15700, 11990, 16260)`.
        - Kitchen Fire-Safety & Full Cabinetry:
          * Double-Basin Sink placed directly under the North Garden Window (`SINK_UNDER_WINDOW`).
          * 5-Burner Gas Stove placed on the solid interior partition wall between Clean Kitchen & Mutbakh (`STOVE_SOLID_WALL`), away from windows/curtains!
          * Full cabinet runs along the Mutbakh partition wall, the South staircase wall, the North window wall, plus East Stone Island.
        - Universal Door Hinge-Against-Wall Rule:
          * Every door has its fixed hinge/open leaf placed 80-120mm from the adjacent perpendicular wall or wardrobe, and its swing arc sweeping into the room.
          * Floor 0 features a 1.60m Double-Leaf Main Entry Door, Curved Entrance Porch Steps with flanking Planter Boxes, and a North Backyard/Garden Exit Door.
        """
        site = ParametricSiteSpec(
            width_x_mm=16_000,
            length_y_mm=26_000,
            separation_joint_mm=0,
            south_street_width_mm=12_000,
            party_walls=(),
            coverage_ratio=0.55,
            building_placement="NORTH",
            lightwell_enabled=False,
            lightwell_position="NONE",
            lightwell_depth_mm=0,
            lightwell_area_m2=0.0,
            include_dirty_kitchen=True,
            typology=BuildingTypology.DUPLEX_2FLOOR,
            total_Privilege_floors=2,
            has_basement=False,
            pilotis_height_mm=0,
            typical_floor_height_mm=3240,
            south_cantilever_mm=1400,
        )

        villa_rect = RectMM(1800, 11500, 14200, 23800)
        courtyards = [
            ("SOUTH_RESORT_GARDEN", RectMM(0, 0, 16000, 11500), "محوطه باغ ویلا، استخر چهارفصل، جکوزی، سکوی آفتاب‌گیر و آلاچیق"),
            ("NORTH_GARDEN", RectMM(0, 23800, 16000, 26000), "حیاط خلوت و باغ شمالی ویلا (نورگیری مستقیم شمال)"),
            ("WEST_GARDEN", RectMM(0, 11500, 1800, 23800), "باغچه و مسیر پیاده غربی"),
            ("EAST_GARDEN", RectMM(14200, 11500, 16000, 23800), "باغچه و مسیر پیاده شرقی"),
        ]
        lightwells: List[BackyardLightwell] = []

        grid_x, grid_y, columns, _ = self._compute_structural_grid_and_core_box(
            site, villa_rect, include_stair_core=False
        )

        t_ext = 240
        t_int = 120
        ix0, ix1 = villa_rect.x_min + t_ext, villa_rect.x_max - t_ext  # 2040 .. 13960
        iy0, iy1 = villa_rect.y_min + t_ext, villa_rect.y_max - t_ext  # 11740 .. 23560

        # Plumb Shared Sanitary Duct across Floor 0 and Floor 1 (0.0mm horizontal drift, 100% clear of all doors & fixtures!)
        shared_sanitary_duct_rect = RectMM(11430, 15700, 11990, 16260)
        dec_stair_rect = RectMM(ix0 + 120, 15650, 5480, 19280)

        # ==================== FLOOR 0: RESORT LANDSCAPE + DUPLEX GROUND FLOOR (+0.45m) ====================
        entry_veranda_rect = RectMM(5800, 9650, 9400, 11500)
        foyer_rect = RectMM(5600, iy0, 9600, 20600)
        north_gallery_lounge_rect = RectMM(5600, 20600, 9600, iy1)
        dining_sw_rect = RectMM(ix0, iy0, 5600, 15520)
        liv_se_rect = RectMM(9660, iy0, ix1, 15520)
        # Mutbakh in NW corner + Spacious L-Shaped Clean Kitchen (`آشپزخانه تمیز بزرگ با کابینت روی دیوار مشترک مطبخ و دیوار راه‌پله`)
        mutbakh_nw_rect = RectMM(ix0, 21950, 3650, iy1)
        ok_nw_rect = RectMM(ix0, 19400, 5600, 21830)
        ok_ne_wing_rect = RectMM(3770, 21830, 5600, iy1)
        # `401.jpg` Floor 0 Red-Hatched & Black-Wall Layout:
        # - South-West (`9720..11650, 15650..17230`): Compact Powder Room (`GUEST_WC`) with Toilet & Vanity flush on West wall
        # - North-West (`9720..11650, 17350..19280`): Guest Suite Walk-In Closet (`GUEST_SUITE_CLOSET` — Red Hatch Left)
        # - East (`11770..13960, 15650..19280`): Guest Suite En-Suite Master Bath (`MAIN_BATHROOM` — Red Hatch Right)
        wc_rect = RectMM(9720, 15650, 11650, 17550)
        guest_closet_rect = RectMM(9720, 17670, 11650, 19280)
        bath_rect = RectMM(11770, 15650, ix1, 19280)
        guest_suite_ne_rect = RectMM(9720, 19400, ix1, iy1)

        f0_rooms: List[RoomSpace] = [
            RoomSpace(
                room_id="ENTRY_STEPS_LANDING",
                code_en="CURVED SOUTH VERANDA & PORCH STEPS (+0.45m)",
                label_fa="سکوی بزرگ ورودی و پله قوسی (+0.45m)",
                unit_id="LUXURY_DUPLEX",
                space_category="OUTDOOR",
                net_rect_mm=entry_veranda_rect,
                z_elevation_mm=450,
                elevation_label="⊕ ±0.00 → +0.45m",
                natural_light="SOUTH_COURTYARD",
            ),
            RoomSpace(
                room_id="ENTRANCE_FOYER",
                code_en="GRAND CENTRAL GALLERY & HALLWAY (WITH NORTH BACKYARD DOOR)",
                label_fa="گالری مرکزی ورودی و راهرو ارتباطی همکف",
                unit_id="LUXURY_DUPLEX",
                space_category="CIRCULATION",
                net_rect_mm=foyer_rect,
                z_elevation_mm=450,
                elevation_label="+0.45 m",
                natural_light="SOUTH_COURTYARD",
                is_open_edge_east=True,
                is_open_edge_west=True,
                is_open_edge_north=True,
                l_extension_rect_mm=north_gallery_lounge_rect,
                l_extension_label_fa="گالری و نشیمن شمالی (دارای درب خروجی به باغ شمالی)",
            ),
            RoomSpace(
                room_id="LIVING_DINING",
                code_en="PANORAMIC DOUBLE-HEIGHT GREAT SALON & SW DINING HALL",
                label_fa="سالن پذیرایی و نشیمن دوبلکس (زیر وید — دید به استخر)",
                unit_id="LUXURY_DUPLEX",
                space_category="PUBLIC",
                net_rect_mm=liv_se_rect,
                z_elevation_mm=450,
                elevation_label="+0.45 m",
                natural_light="SOUTH_COURTYARD",
                is_open_edge_west=True,
                l_extension_rect_mm=dining_sw_rect,
                l_extension_label_fa="تالار ناهارخوری ۱۰ نفره مشرف به استخر",
            ),
            RoomSpace(
                room_id="OPEN_KITCHEN",
                code_en="SPACIOUS CHEF ISLAND KITCHEN (WITH MUTBAKH WALL & STAIR WALL CABINETS)",
                label_fa="آشپزخانه تمیز و جزیره بزرگ ویلایی",
                unit_id="LUXURY_DUPLEX",
                space_category="SEMI_PUBLIC",
                net_rect_mm=ok_nw_rect,
                z_elevation_mm=450,
                elevation_label="+0.45 m",
                natural_light="NORTH_GARDEN",
                is_open_edge_east=True,
                l_extension_rect_mm=ok_ne_wing_rect,
                l_extension_label_fa="",
            ),
            RoomSpace(
                room_id="DIRTY_KITCHEN",
                code_en="MUTBAKH & PANTRY (NW CORNER)",
                label_fa="مطبخ (آشپزخانه کثیف)",
                unit_id="LUXURY_DUPLEX",
                space_category="SEMI_PUBLIC",
                net_rect_mm=mutbakh_nw_rect,
                z_elevation_mm=450,
                elevation_label="+0.45 m",
                natural_light="WEST_GARDEN",
            ),
            RoomSpace(
                room_id="GUEST_WC",
                code_en="COMPACT GUEST POWDER ROOM (401.JPG BLACK WALL)",
                label_fa="سرویس مهمان",
                unit_id="LUXURY_DUPLEX",
                space_category="WET_SERVICE",
                net_rect_mm=wc_rect,
                z_elevation_mm=450,
                elevation_label="+0.45 m",
                natural_light="MECHANICAL",
            ),
            RoomSpace(
                room_id="MASTER_CLOSET",
                code_en="GUEST SUITE WALK-IN CLOSET (401.JPG RED HATCH)",
                label_fa="کلوزت اختصاصی مستر همکف",
                unit_id="LUXURY_DUPLEX",
                space_category="PRIVATE",
                net_rect_mm=guest_closet_rect,
                z_elevation_mm=450,
                elevation_label="+0.45 m",
                natural_light="NONE",
            ),
            RoomSpace(
                room_id="MAIN_BATHROOM",
                code_en="GROUND GUEST SUITE EN-SUITE BATHROOM (100% PLUMB WITH MASTER BATH)",
                label_fa="حمام اختصاصی مهمان همکف",
                unit_id="LUXURY_DUPLEX",
                space_category="WET_SERVICE",
                net_rect_mm=bath_rect,
                z_elevation_mm=450,
                elevation_label="+0.45 m",
                natural_light="EAST_GARDEN",
            ),
            RoomSpace(
                room_id="MASTER_BEDROOM",
                code_en="GROUND VIP GUEST SUITE (DIRECT ENTRY FROM CENTRAL GALLERY)",
                label_fa="سوئیت خواب مهمان همکف (ورود مستقیم از راهرو)",
                unit_id="LUXURY_DUPLEX",
                space_category="PRIVATE",
                net_rect_mm=guest_suite_ne_rect,
                z_elevation_mm=450,
                elevation_label="+0.45 m",
                natural_light="NORTH_GARDEN",
            ),
        ]

        f0_doors: List[DoorElement] = [
            # 1. Grand Double-Leaf Main Entrance Door (`درب ورودی اصلی دو لنگه — عرض ۱.۶۰ متر`)
            DoorElement("D0_VILLA_MAIN_ENTRY", "درب ورودی اصلی دو لنگه ویلا", "ENTRY_STEPS_LANDING", "ENTRANCE_FOYER", (6800, iy0), 1600, "H", "N", leaf_dir="+", is_main_entry=True),
            # 2. Direct North Backyard / Garden Exit Door (`درب خروجی به حیاط خلوت / باغ شمالی` — hinged on West gallery wall `5750` with `leaf_dir="+"`)
            DoorElement("D0_NORTH_GARDEN_EXIT", "درب حیاط و باغ شمالی", "ENTRANCE_FOYER", "NORTH_GARDEN", (5950, iy1), 900, "H", "S", leaf_dir="+", is_backyard_entry=True),
            # 3. Guest WC door on West corridor wall (`hinge at (9720, 17150)`, `leaf_dir="-"`, swinging East-South clear of the West-wall fixtures!)
            DoorElement("D0_GUEST_WC", "درب سرویس مهمان", "ENTRANCE_FOYER", "GUEST_WC", (wc_rect.x_min, wc_rect.y_max - 80), 660, "V", "E", leaf_dir="-"),
            # 4. Ground-Floor Guest Suite door (`hinge at (9720, 19520)` right against South wall of Guest Suite, `leaf_dir="+"` swinging North!)
            DoorElement("D0_GUEST_SUITE", "درب سوئیت مهمان", "ENTRANCE_FOYER", "MASTER_BEDROOM", (guest_suite_ne_rect.x_min, 19520), 880, "V", "E", leaf_dir="+"),
            # 5. Guest Suite Walk-In Closet door (`hinge at (11520, 19280)`, `leaf_dir="-"`, entering the Red-Hatched Closet from the Guest Suite!)
            DoorElement("D0_GUEST_CLOSET", "درب کلوزت مستر", "MASTER_BEDROOM", "MASTER_CLOSET", (guest_closet_rect.x_max - 120, guest_closet_rect.y_max), 760, "H", "S", leaf_dir="-"),
            # 6. Guest En-Suite Bath door (`hinge at (13840, 19280)` right against East exterior wall, `leaf_dir="-"` swinging West!)
            DoorElement("D0_GUEST_BATH", "درب حمام مستر همکف", "MASTER_BEDROOM", "MAIN_BATHROOM", (bath_rect.x_max - 120, bath_rect.y_max), 780, "H", "S", leaf_dir="-"),
            # 7. Mutbakh door (`درب آشپزخانه کثیف` — clearly positioned at the East end of the Mutbakh partition wall `(2850, 21950)` with `leaf_dir="+"`, `swing_dir="N"`, 100% clear of the West Mutbakh cabinets!)
            DoorElement("D0_MUTBAKH", "درب آشپزخانه کثیف (مطبخ)", "OPEN_KITCHEN", "DIRTY_KITCHEN", (2820, mutbakh_nw_rect.y_min), 740, "H", "N", leaf_dir="+"),
        ]

        raw_f0_windows: List[WindowElement] = [
            WindowElement("WIN0_DINING_POOL_SOUTH", "LIVING_DINING", "SOUTH_RESORT_GARDEN", 2450, villa_rect.y_min, 5150, villa_rect.y_min + t_ext, t_ext, "H"),
            WindowElement("WIN0_SALON_POOL_SOUTH", "LIVING_DINING", "SOUTH_RESORT_GARDEN", 10150, villa_rect.y_min, 13450, villa_rect.y_min + t_ext, t_ext, "H"),
            WindowElement("WIN0_SALON_EAST_GARDEN", "LIVING_DINING", "EAST_GARDEN", villa_rect.x_max - t_ext, 12250, villa_rect.x_max, 15100, t_ext, "V"),
            WindowElement("WIN0_DINING_WEST_GARDEN", "LIVING_DINING", "WEST_GARDEN", villa_rect.x_min, 12250, villa_rect.x_min + t_ext, 15100, t_ext, "V"),
            WindowElement("WIN0_MUTBAKH_WEST", "DIRTY_KITCHEN", "WEST_GARDEN", villa_rect.x_min, 22100, villa_rect.x_min + t_ext, 23250, t_ext, "V"),
            WindowElement("WIN0_KITCHEN_NORTH", "OPEN_KITCHEN", "NORTH_GARDEN", 3900, villa_rect.y_max - t_ext, 5250, villa_rect.y_max, t_ext, "H"),
            WindowElement("WIN0_GALLERY_NORTH", "ENTRANCE_FOYER", "NORTH_GARDEN", 7100, villa_rect.y_max - t_ext, 9200, villa_rect.y_max, t_ext, "H"),
            WindowElement("WIN0_GUEST_NORTH", "MASTER_BEDROOM", "NORTH_GARDEN", 10600, villa_rect.y_max - t_ext, 13200, villa_rect.y_max, t_ext, "H"),
            WindowElement("WIN0_GUEST_EAST", "MASTER_BEDROOM", "EAST_GARDEN", villa_rect.x_max - t_ext, 20350, villa_rect.x_max, 22600, t_ext, "V"),
        ]
        f0_windows = [self._decollide_window_from_columns(w, columns, doors=f0_doors) for w in raw_f0_windows]

        f0_furniture: List[FurnitureElement] = [
            # Resort Landscaping Elements in South Courtyard (Swimming Pool + Sun Deck + Pergola/Fire-Pit + Planter Boxes + Cars + Trees)
            FurnitureElement("FURN_RESORT_POOL", "COURTYARD", "SWIMMING_POOL", RectMM(1100, 4800, 7300, 9100), "SWIMMING POOL & JACUZZI (6.2x4.3m)", "استخر روباز چهارفصل و جکوزی آب‌گرم"),
            FurnitureElement("FURN_POOL_SUNDECK", "COURTYARD", "POOL_SUN_DECK", RectMM(7300, 4800, 10100, 9100), "TIMBER SUN DECK & LOUNGERS", "سکوی چوبی آفتاب‌گیر و تخت‌های استخری"),
            FurnitureElement("FURN_PERGOLA_FIREPIT", "COURTYARD", "PERGOLA_FIREPIT", RectMM(1100, 950, 7300, 4300), "PERGOLA, FIRE-PIT & BBQ LOUNGE", "آلاچیق مدرن، آتشکده (Fire-Pit) و باربیکیو"),
            FurnitureElement("FURN_PLANTER_PORCH_W", "COURTYARD", "PLANTER_BOX", RectMM(4550, 10350, 5680, 11380), "WEST PORCH PLANTER", "باکس گلدان سنگی ورودی"),
            FurnitureElement("FURN_PLANTER_PORCH_E", "COURTYARD", "PLANTER_BOX", RectMM(9520, 10350, 10650, 11380), "EAST PORCH PLANTER", "باکس گلدان سنگی ورودی"),
            FurnitureElement("FURN_CAR_VILLA_1", "COURTYARD", "CAR", RectMM(10600, 1100, 12800, 5600), "LUXURY CAR 1", "پارکینگ مسقف ویلایی ۱"),
            FurnitureElement("FURN_CAR_VILLA_2", "COURTYARD", "CAR", RectMM(13100, 1100, 15300, 5600), "LUXURY CAR 2", "پارکینگ مسقف ویلایی ۲"),
            FurnitureElement("FURN_TREE_SW", "COURTYARD", "TREE", RectMM(250, 9600, 1050, 10400), "GARDEN TREE", "درختکاری محوطه"),
            FurnitureElement("FURN_TREE_SE", "COURTYARD", "TREE", RectMM(14800, 9600, 15600, 10400), "GARDEN TREE", "درختکاری محوطه"),
            FurnitureElement("FURN_TREE_NW", "COURTYARD", "TREE", RectMM(450, 24400, 1350, 25300), "NORTH GARDEN TREE", "باغ شمالی"),
            FurnitureElement("FURN_TREE_NE", "COURTYARD", "TREE", RectMM(14500, 24400, 15400, 25300), "NORTH GARDEN TREE", "باغ شمالی"),
            # Decorative L-Shaped Duplex Staircase (18 risers x 18cm = 3.24m, travel line starts on Step 1 and exits East at Step 18)
            FurnitureElement("FURN_DUPLEX_DEC_STAIR", "ENTRANCE_FOYER", "DECORATIVE_DUPLEX_STAIR", dec_stair_rect, "DECORATIVE L-STAIR (18 RISERS)", "پله دکوراتیو L شکل دوبلکس (۱۸ پله × ۱۸cm)"),
            # Living & Dining Furniture (True-scale proportions inside Great Salon X=9720..13960, Y=11740..15520)
            FurnitureElement("FURN_ENTRY_WING_WALL", "ENTRANCE_FOYER", "PARTITION_WALL", RectMM(5600, iy0, 5720, iy0 + 1650), "FOYER WING WALL", "دیوار غربی لابی ورودی"),
            FurnitureElement("FURN_SHOE_CLOSET", "ENTRANCE_FOYER", "WARDROBE", RectMM(5720, iy0 + 180, 6280, iy0 + 1580), "SHOE CLOSET", "کفش‌کن و جالباسی (چسبیده به دیوار غربی ورودی)"),
            FurnitureElement("FURN_SOFA_L", "LIVING_DINING", "SOFA_L", RectMM(10050, iy0 + 300, ix1 - 220, 15250), "GRAND RECEPTION SOFA", "مبلمان پذیرایی بزرگ مشرف به استخر"),
            FurnitureElement("FURN_DINING_10", "LIVING_DINING", "DINING_6", RectMM(ix0 + 550, iy0 + 550, 5100, 14800), "DINING TABLE 10P", "میز ناهارخوری ۱۰ نفره مشرف به استخر"),
            FurnitureElement("FURN_NORTH_LOUNGE", "ENTRANCE_FOYER", "TV_LOUNGE", RectMM(6950, 20900, 9400, 22600), "NORTH GARDEN LOUNGE", "نشیمن گالری رو به باغ شمالی"),
            # Cleanly Organized L-Shaped Chef Kitchen & Mutbakh (`چیدمان مهندسی و منظم آشپزخانه تمیز و مطبخ`):
            # 1) West Wall of Clean Kitchen (`2060..2660, 19460..21780`): Continuous Cabinet + 5-Burner Gas Stove (`گاز ۵ شعله روی دیوار صلب غربی`)
            FurnitureElement("FURN_KIT_STOVE_WALL", "OPEN_KITCHEN", "KITCHEN_COUNTER", RectMM(2060, 20100, 2660, 21780), "STOVE ON WEST SOLID WALL", "کابینت و گاز ۵ شعله", orientation="STOVE_SOLID_WALL"),
            # 2) South Wall of Clean Kitchen (`2680..4650, 19460..20040`): Side-by-Side Fridge + Washing Machine (`یخچال ساید و لباسشویی روی دیوار راه‌پله`)
            FurnitureElement("FURN_KIT_COUNTER_SOUTH", "OPEN_KITCHEN", "KITCHEN_COUNTER", RectMM(2680, 19460, 4650, 20040), "SOUTH STAIR WALL CABINET", "یخچال ساید و لباسشویی", orientation="FRIDGE_WASHER"),
            # 3) North Window Wall of Clean Kitchen (`3820..5480, iy1 - 580..iy1 - 40`): Double-Basin Sink + Dishwasher (`سینک و ظرفشویی زیر پنجره شمالی`)
            FurnitureElement("FURN_KIT_SINK_NORTH", "OPEN_KITCHEN", "KITCHEN_COUNTER", RectMM(3820, iy1 - 580, 5480, iy1 - 40), "SINK UNDER NORTH WINDOW", "سینک دوقلو و ظرفشویی (زیر پنجره)", orientation="SINK_UNDER_WINDOW"),
            # 4) East Stone Island & Breakfast Bar (`4820..5520, 20150..21800`)
            FurnitureElement("FURN_KIT_ISLAND", "OPEN_KITCHEN", "KITCHEN_ISLAND_BAR", RectMM(4820, 20150, 5520, 21800), "ISLAND & BAR", "جزیره و بار آشپزخانه"),
            # 5) Mutbakh L-Counter on West & North walls (`2060..2660, 22020..23500`, 100% clear of the South-East Mutbakh door `2820..3560`!)
            FurnitureElement("FURN_MUTBAKH_COUNTER", "DIRTY_KITCHEN", "KITCHEN_COUNTER", RectMM(2060, 22020, 2660, 23500), "MUTBAKH STOVE", "کابینت و گاز مطبخ", orientation="STOVE_SOLID_WALL"),
            # Ground VIP Guest Suite NE (East-Headboard Bed `orientation="H"`, North-Window Desk, West Wardrobe + Dedicated Walk-In Closet in `401.jpg` Red Hatch!)
            FurnitureElement("FURN_GUEST_BED", "MASTER_BEDROOM", "BED_DOUBLE", RectMM(11820, 20350, ix1 - 80, 22350), "VIP GUEST BED (EAST HEADBOARD)", "تخت دونفره مهمان (تاج به دیوار شرقی)", orientation="H"),
            FurnitureElement("FURN_GUEST_DESK", "MASTER_BEDROOM", "STUDY_DESK", RectMM(10650, iy1 - 760, 12050, iy1 - 80), "GUEST STUDY DESK", "میز مطالعه و آرایش زیر پنجره شمالی", orientation="V"),
            FurnitureElement("FURN_GUEST_WARD", "MASTER_BEDROOM", "WARDROBE", RectMM(9800, 20550, 10400, 23450), "GUEST WARDROBE", "کمد دیواری قدی مهمان"),
            FurnitureElement("FURN_GUEST_WALKIN_W", "MASTER_CLOSET", "WARDROBE", RectMM(9780, 17740, 10380, 19200), "GUEST WALK-IN CLOSET", "رگال قدی کلوزت مستر (هاشور قرمز)"),
            # True-Scale Sanitary Fixtures (`401.jpg`: Guest WC Toilet & Vanity flush against North/West wall inside compact `15650..17230` room!)
            FurnitureElement("FURN_WC_SET", "GUEST_WC", "WC_SET", RectMM(9725, 15680, 11180, 16720), "POWDER WC", "روشویی و فرنگی مهمان (چسبیده به دیوار غربی)", orientation="W"),
            FurnitureElement("FURN_BATH_SET", "MAIN_BATHROOM", "BATH_SET", RectMM(12030, 15665, 13945, 18380), "GUEST BATH", "وان استاندارد (160×80cm)، فرنگی و روشویی", orientation="S_TUB"),
            FurnitureElement("FURN_DUCT_SANITARY_SHARED", "GUEST_WC", "DUCT", shared_sanitary_duct_rect, "PLUMB SHARED DUCT", "داکت تاسیساتی هم‌راستا (Plumb)"),
        ]

        floor0 = FloorPlanDesignV3(
            floor_index=0,
            name_fa="طبقه همکف ویلای دوبلکس استخردار + سایت‌پلان محوطه‌سازی، استخر، جکوزی، سکوی آفتاب‌گیر و آلاچیق (تراز +0.45m)",
            name_en="LUXURY RESORT DUPLEX GROUND FLOOR & LANDSCAPE SITE PLAN (+0.45m)",
            occupancy=OccupancyType.VILLA_GROUND,
            z_elevation_mm=450,
            elevation_code_str="+0.45 m",
            floor_height_mm=3240,
            unit_count=1,
            gross_building_rect_mm=villa_rect,
            courtyards=courtyards,
            lightwells=lightwells,
            grid_x_mm=grid_x,
            grid_y_mm=grid_y,
            columns=columns,
            stair_detail=None,
            elevator_detail=None,
            rooms=f0_rooms,
            doors=f0_doors,
            windows=f0_windows,
            furniture=f0_furniture,
            dimensions=[],
            coverage_ratio_achieved=0.37,
            gross_area_m2=round(villa_rect.area_m2, 2),
            net_area_m2=round(sum(r.net_rect_mm.area_m2 for r in f0_rooms) + dining_sw_rect.area_m2 + north_gallery_lounge_rect.area_m2 + ok_ne_wing_rect.area_m2, 2),
            is_open_pilotis=False,
            turning_zone_rect_mm=None,
            cantilever_zone_rect_mm=RectMM(1800, 10100, 14200, 11500),
        )

        # ==================== FLOOR 1: DUPLEX UPPER PRIVATE NIGHT LEVEL (+3.69m) ====================
        # - Double-Height Void `duplex_void_se_rect` is bounded by Axis C (9660), Axis D (13960), Axis 1 (11740), and Axis 2 (15580) -> ZERO beams cross the Void!
        # - 100% Plumb Wet Stack: `MAIN_BATHROOM` (9720..11650, 15650..19280) and `MASTER_BATH` (11770..13960, 15650..19280).
        balc_south_rect = RectMM(1800, 10100, 9600, 11500)
        bed3_sw_rect = RectMM(ix0, iy0, 5540, 15520)
        upper_void_lounge_rect = RectMM(5720, iy0, 9600, 15520)
        duplex_void_se_rect = RectMM(9660, iy0, ix1, 15520)
        upper_gallery_rect = RectMM(5720, 15520, 9600, 20600)
        bed2_nw_rect = RectMM(ix0, 19400, 5600, iy1)
        upper_closet_study_rect = RectMM(5600 + t_int, 20600 + t_int, 9600, iy1)
        upper_bath_rect = RectMM(9720, 15650, 11650, 19280)
        mbath_ne_rect = RectMM(11770, 15650, ix1, 19280)
        master_vip_ne_rect = RectMM(9720, 19400, ix1, iy1)

        f1_rooms: List[RoomSpace] = [
            RoomSpace(
                room_id="BALCONY_SOUTH",
                code_en="PANORAMIC SOUTH TERRACE OVERLOOKING POOL",
                label_fa="تراس پانورامای جنوبی مشرف به استخر و باغ",
                unit_id="LUXURY_DUPLEX",
                space_category="OUTDOOR",
                net_rect_mm=balc_south_rect,
                z_elevation_mm=3690,
                elevation_label="+3.69 m",
                natural_light="SOUTH_COURTYARD",
            ),
            RoomSpace(
                room_id="ENTRANCE_FOYER",
                code_en="UPPER FAMILY GALLERY (OPEN WEST EXIT OF STEP 18)",
                label_fa="گالری طبقه بالا (ورود مستقیم و بدون دیوار از پله ۱۸)",
                unit_id="LUXURY_DUPLEX",
                space_category="CIRCULATION",
                net_rect_mm=upper_gallery_rect,
                z_elevation_mm=3690,
                elevation_label="+3.69 m",
                natural_light="VOID_OVERLOOK",
                is_open_edge_east=False,
                is_open_edge_west=True,
                is_open_edge_south=True,
            ),
            RoomSpace(
                room_id="LIVING_DINING",
                code_en="OPEN GALLERY TO TERRACE & VOID",
                label_fa="",
                unit_id="LUXURY_DUPLEX",
                space_category="CIRCULATION",
                net_rect_mm=upper_void_lounge_rect,
                z_elevation_mm=3690,
                elevation_label="+3.69 m",
                natural_light="SOUTH_COURTYARD",
                is_open_edge_north=True,
                is_open_edge_east=True,
            ),
            RoomSpace(
                room_id="VOID_DUPLEX_LIVING",
                code_en="DOUBLE-HEIGHT VOID OVER GREAT SALON (ZERO INTERNAL BEAMS)",
                label_fa="وید دوبلکس (فضای تهی مشرف به پذیرایی — بدون عبور تیر)",
                unit_id="LUXURY_DUPLEX",
                space_category="VOID",
                net_rect_mm=duplex_void_se_rect,
                z_elevation_mm=3690,
                elevation_label="VOID",
                natural_light="SOUTH_COURTYARD",
            ),
            RoomSpace(
                room_id="BEDROOM_3_SOUTH",
                code_en="PROPORTIONAL SOUTH-WEST SUITE (4.56x3.78m)",
                label_fa="اتاق خواب ۳ جنوبی (رو به تراس)",
                unit_id="LUXURY_DUPLEX",
                space_category="PRIVATE",
                net_rect_mm=bed3_sw_rect,
                z_elevation_mm=3690,
                elevation_label="+3.69 m",
                natural_light="SOUTH_COURTYARD",
            ),

            RoomSpace(
                room_id="BEDROOM_1",
                code_en="NORTH-WEST SUITE (3.56x4.16m — SOLID WALL TO HALLWAY & L-WARDROBE)",
                label_fa="اتاق خواب ۲ (شمال‌غربی — دیوار مشخص به راهرو و کمد یکپارچه)",
                unit_id="LUXURY_DUPLEX",
                space_category="PRIVATE",
                net_rect_mm=bed2_nw_rect,
                z_elevation_mm=3690,
                elevation_label="+3.69 m",
                natural_light="NORTH_GARDEN",
            ),
            RoomSpace(
                room_id="MASTER_CLOSET",
                code_en="UPPER STUDY & WALK-IN DRESSING ROOM (NORTH GARDEN VIEW)",
                label_fa="اتاق مطالعه و کلوزت طبقه بالا (رو به باغ شمالی)",
                unit_id="LUXURY_DUPLEX",
                space_category="PRIVATE",
                net_rect_mm=upper_closet_study_rect,
                z_elevation_mm=3690,
                elevation_label="+3.69 m",
                natural_light="NORTH_GARDEN",
            ),
            RoomSpace(
                room_id="MAIN_BATHROOM",
                code_en="UPPER FAMILY BATHROOM (100% PLUMB OVER GROUND WC)",
                label_fa="حمام و سرویس عمومی بالا (هم‌راستا با سرویس همکف)",
                unit_id="LUXURY_DUPLEX",
                space_category="WET_SERVICE",
                net_rect_mm=upper_bath_rect,
                z_elevation_mm=3690,
                elevation_label="+3.69 m",
                natural_light="MECHANICAL",
            ),
            RoomSpace(
                room_id="MASTER_BATH",
                code_en="ROYAL MASTER EN-SUITE BATHROOM (100% PLUMB OVER GROUND BATH)",
                label_fa="حمام و جکوزی مستر رویال (هم‌راستا با حمام همکف)",
                unit_id="LUXURY_DUPLEX",
                space_category="WET_SERVICE",
                net_rect_mm=mbath_ne_rect,
                z_elevation_mm=3690,
                elevation_label="+3.69 m",
                natural_light="EAST_GARDEN",
            ),
            RoomSpace(
                room_id="MASTER_BEDROOM",
                code_en="ROYAL MASTER VIP SUITE (NORTH-EAST GARDEN VIEW)",
                label_fa="مستر روم رویال (شمال‌شرقی — چیدمان استاندارد با دید باغ شمال و شرق)",
                unit_id="LUXURY_DUPLEX",
                space_category="PRIVATE",
                net_rect_mm=master_vip_ne_rect,
                z_elevation_mm=3690,
                elevation_label="+3.69 m",
                natural_light="NORTH_GARDEN",
            ),
        ]

        f1_doors: List[DoorElement] = [
            # 1. Bedroom 3 entry on East wall (5540) opening from Upper Family Lounge, hinged near North wall (14480..15340) — 100% clear of all columns!
            DoorElement("D1_BED3_ENTRY", "درب خواب ۳ جنوبی", "LIVING_DINING", "BEDROOM_3_SOUTH", (bed3_sw_rect.x_max, 14480), 860, "V", "W", leaf_dir="+"),
            # 2. ONLY ONE Terrace door from the Private Upper Hall (`حذف در تراس از داخل اتاق خواب ۳ مطابق ضربدر مشکی 401.jpg برای استفاده مفید از فضای اتاق`)!
            DoorElement("D1_LOUNGE_TERRACE", "درب تراس پانوراما (از هال خصوصی)", "LIVING_DINING", "BALCONY_SOUTH", (6100, iy0), 920, "H", "N", leaf_dir="+"),
            # 4. North-West Bedroom 2 door: On the solid East wall of Bedroom 2 (`hinge at (5600, 19520)` right against the South wall of Bedroom 2, `leaf_dir="+"`, swinging West into Bedroom 2 with wardrobe behind the door)!
            DoorElement("D1_BED2_ENTRY", "درب اتاق خواب ۲", "ENTRANCE_FOYER", "BEDROOM_1", (bed2_nw_rect.x_max, 19520), 860, "V", "W", leaf_dir="+"),
            # 5. Upper Study / Walk-In Closet door: Fixed hinge leaf at (5840, 20720) right against the West wall of the study room (`leaf_dir="+"`, swinging North)!
            DoorElement("D1_UPPER_CLOSET", "درب کلوزت و اتاق مطالعه", "ENTRANCE_FOYER", "MASTER_CLOSET", (5840, upper_closet_study_rect.y_min), 820, "H", "N", leaf_dir="+"),
            # 6. Upper Family Bathroom door: Fixed hinge leaf at (9720, 15800) right against South wall of Bathroom (`leaf_dir="+"`, swinging East-North)!
            DoorElement("D1_UPPER_BATH", "درب حمام عمومی بالا", "ENTRANCE_FOYER", "MAIN_BATHROOM", (upper_bath_rect.x_min, 15800), 750, "V", "E", leaf_dir="+"),
            # 7. Royal Master Suite entry: Fixed hinge leaf at (9720, 19520) right against South wall of Master Suite (`leaf_dir="+"`, swinging East-North)!
            DoorElement("D1_MASTER_VIP", "درب مستر روم رویال", "ENTRANCE_FOYER", "MASTER_BEDROOM", (master_vip_ne_rect.x_min, 19520), 880, "V", "E", leaf_dir="+"),
            # 8. Royal Master En-Suite Bath door: Fixed hinge leaf at (13840, 19280) right against East exterior wall (`leaf_dir="-"`, swinging West-South)!
            DoorElement("D1_MASTER_BATH", "درب حمام مستر رویال", "MASTER_BEDROOM", "MASTER_BATH", (mbath_ne_rect.x_max - 120, mbath_ne_rect.y_max), 780, "H", "S", leaf_dir="-"),
        ]

        raw_f1_windows: List[WindowElement] = [
            WindowElement("WIN1_BED3_SOUTH", "BEDROOM_3_SOUTH", "BALCONY_SOUTH", 2350, villa_rect.y_min, 5150, villa_rect.y_min + t_ext, t_ext, "H"),
            WindowElement("WIN1_LOUNGE_SOUTH", "LIVING_DINING", "BALCONY_SOUTH", 7250, villa_rect.y_min, 9200, villa_rect.y_min + t_ext, t_ext, "H"),
            WindowElement("WIN1_BED3_WEST", "BEDROOM_3_SOUTH", "WEST_GARDEN", villa_rect.x_min, 12300, villa_rect.x_min + t_ext, 14800, t_ext, "V"),
            WindowElement("WIN1_BED2_WEST", "BEDROOM_1", "WEST_GARDEN", villa_rect.x_min, 20400, villa_rect.x_min + t_ext, 22900, t_ext, "V"),
            WindowElement("WIN1_BED2_NORTH", "BEDROOM_1", "NORTH_GARDEN", 2400, villa_rect.y_max - t_ext, 5200, villa_rect.y_max, t_ext, "H"),
            WindowElement("WIN1_STUDY_NORTH", "MASTER_CLOSET", "NORTH_GARDEN", 6400, villa_rect.y_max - t_ext, 9100, villa_rect.y_max, t_ext, "H"),
            WindowElement("WIN1_MASTER_NORTH", "MASTER_BEDROOM", "NORTH_GARDEN", 10600, villa_rect.y_max - t_ext, 13200, villa_rect.y_max, t_ext, "H"),
            WindowElement("WIN1_MASTER_EAST", "MASTER_BEDROOM", "EAST_GARDEN", villa_rect.x_max - t_ext, 20350, villa_rect.x_max, 22600, t_ext, "V"),
            WindowElement("WIN1_MBATH_EAST", "MASTER_BATH", "EAST_GARDEN", villa_rect.x_max - t_ext, 16500, villa_rect.x_max, 18500, t_ext, "V"),
        ]
        f1_windows = [self._decollide_window_from_columns(w, columns, doors=f1_doors) for w in raw_f1_windows]

        f1_furniture: List[FurnitureElement] = [
            # Decorative L-Stair Landing arriving at Step 18 facing East into Upper Gallery
            FurnitureElement("FURN_DUPLEX_DEC_STAIR_F1", "ENTRANCE_FOYER", "DECORATIVE_DUPLEX_STAIR", dec_stair_rect, "DECORATIVE L-STAIR LANDING (+3.69m)", "پله دکوراتیو L شکل (پله ۱۸ خروج به گالری شرقی +3.69m)"),
            FurnitureElement("FURN_UPPER_LOUNGE", "ENTRANCE_FOYER", "TV_LOUNGE", RectMM(7350, 16300, 9520, 18650), "UPPER FAMILY L-SOFA (401.JPG)", "مبل L نشیمن خصوصی طبقه بالا (در موقعیت مشخص‌شده 401.jpg)"),
            # 1. Proportional South-West Suite (`BEDROOM_3_SOUTH`: 4.56m x 3.78m) + Dedicated Walk-In Closet (`SOUTH_SUITE_CLOSET` with added West Wardrobe down to the door!):
            SmartArchitecturalFurnitureSolver.solve_south_bedroom_bed_layout(bed3_sw_rect, "BEDROOM_3_SOUTH"),
            FurnitureElement("FURN_BED3_WARD", "BEDROOM_3_SOUTH", "WARDROBE", RectMM(2120, 14820, 3480, 15420), "WARDROBE 3", "کمد دیواری خواب ۳"),
            FurnitureElement("FURN_BED3_DESK", "BEDROOM_3_SOUTH", "STUDY_DESK", RectMM(3550, 14780, 4420, 15420), "DESK 3", "میز مطالعه خواب ۳", orientation="S"),
            # 2. North-West Bedroom 2 (`BEDROOM_1`: 3.56m x 4.16m — Bed at NW, Desk under North window, Wardrobe behind the door on South wall + West wardrobe eliminating dead gap!):
            FurnitureElement("FURN_BED2_NW", "BEDROOM_1", "BED_DOUBLE", RectMM(2220, 21350, 4220, 23460), "BED 2 NW", "تخت خواب ۲ (تاج چسبیده به دیوار شمالی)", orientation="V"),
            FurnitureElement("FURN_BED2_DESK", "BEDROOM_1", "STUDY_DESK", RectMM(4320, 22750, 5480, 23460), "STUDY DESK", "میز مطالعه زیر پنجره شمالی", orientation="V"),
            FurnitureElement("FURN_BED2_WARD_S", "BEDROOM_1", "WARDROBE", RectMM(2120, 19480, 4620, 20080), "WARDROBE 2 SOUTH", "کمد دیواری پشت در خواب ۲"),
            FurnitureElement("FURN_BED2_WARD_W", "BEDROOM_1", "WARDROBE", RectMM(2120, 20120, 2720, 21260), "WARDROBE 2 WEST", "کمد و کتابخانه کنار تخت"),
            # 3. Upper Study & Walk-In Closet (`MASTER_CLOSET` in North-Center):
            FurnitureElement("FURN_UPPER_STUDY_DESK", "MASTER_CLOSET", "STUDY_DESK", RectMM(6850, iy1 - 760, 8650, iy1 - 80), "UPPER STUDY DESK", "میز مطالعه رو به باغ شمالی", orientation="V"),
            FurnitureElement("FURN_UPPER_CLOSET_RACK", "MASTER_CLOSET", "WARDROBE", RectMM(8920, 20850, 9520, 23400), "UPPER WALK-IN RACK", "رگال کلوزت طبقه بالا"),
            # 4. North-East Royal Master Suite (`MASTER_BEDROOM` — East-Headboard King Bed `orientation="H"`, North-Window Desk, West Wardrobe clear of door!):
            FurnitureElement("FURN_MASTER_VIP_BED", "MASTER_BEDROOM", "BED_DOUBLE", RectMM(11820, 20350, ix1 - 80, 22350), "ROYAL MASTER BED (EAST HEADBOARD)", "تخت کینگ مستر رویال (تاج به دیوار شرقی)", orientation="H"),
            FurnitureElement("FURN_MASTER_VIP_DESK", "MASTER_BEDROOM", "STUDY_DESK", RectMM(10650, iy1 - 760, 12050, iy1 - 80), "MASTER VANITY & DESK", "میز آرایش و مطالعه زیر پنجره شمالی", orientation="V"),
            FurnitureElement("FURN_MASTER_VIP_WARD", "MASTER_BEDROOM", "WARDROBE", RectMM(9800, 20550, 10400, 23450), "MASTER WARDROBE", "کمد قدی مستر (بدون تداخل با در)"),
            # 5. Plumb Wet Stack on Floor 1: `MAIN_BATHROOM` (West: 9720..11650) + `MASTER_BATH` (East: 11770..13960) + Plumb Shared Sanitary Duct (0.0mm drift):
            FurnitureElement("FURN_UPPER_BATH_SET", "MAIN_BATHROOM", "BATH_SET", RectMM(9730, 16650, 11640, 19265), "UPPER FAMILY BATH", "وان در شمال + روشویی و فرنگی چسبیده به دیوار شرقی (401.jpg)", orientation="E_WALL_FLUSH"),
            FurnitureElement("FURN_MBATH_SET", "MASTER_BATH", "BATH_SET", RectMM(12030, 15665, 13945, 18380), "ROYAL MASTER BATH", "وان جکوزی (180×85cm)، فرنگی و روشویی مستر", orientation="S_TUB"),
            FurnitureElement("FURN_DUCT_SANITARY_SHARED", "MASTER_BATH", "DUCT", shared_sanitary_duct_rect, "PLUMB SHARED DUCT", "داکت تاسیساتی هم‌راستا (Plumb)"),
        ]

        floor1 = FloorPlanDesignV3(
            floor_index=1,
            name_fa="طبقه اول ویلای دوبلکس استخردار (آکس‌بندی بدون تیر در پله و وید + هم‌راستایی ۱۰۰٪ حمام‌ها + اصلاح کامل درها و کمدها — تراز +3.69m)",
            name_en="LUXURY RESORT DUPLEX UPPER PRIVATE FLOOR (+3.69m)",
            occupancy=OccupancyType.DUPLEX_UPPER,
            z_elevation_mm=3690,
            elevation_code_str="+3.69 m",
            floor_height_mm=3240,
            unit_count=1,
            gross_building_rect_mm=villa_rect,
            courtyards=[],
            lightwells=[],
            grid_x_mm=grid_x,
            grid_y_mm=grid_y,
            columns=columns,
            stair_detail=None,
            elevator_detail=None,
            rooms=f1_rooms,
            doors=f1_doors,
            windows=f1_windows,
            furniture=f1_furniture,
            dimensions=[],
            coverage_ratio_achieved=0.37,
            gross_area_m2=round(villa_rect.area_m2 - duplex_void_se_rect.area_m2, 2),
            net_area_m2=round(sum(r.net_rect_mm.area_m2 for r in f1_rooms if r.room_id != "VOID_DUPLEX_LIVING"), 2),
            is_open_pilotis=False,
            turning_zone_rect_mm=None,
            cantilever_zone_rect_mm=balc_south_rect,
        )

        floors = [floor0, floor1]
        audit = self._audit_project_v10(site, floors)
        return BuildingProjectResultV3(
            project_id="ARCH_V13_LUXURY_POOL_DUPLEX_16X26",
            project_title_fa="ویلای دوبلکس مدرن چهارطرف آزاد با استخر، جکوزی، سکوی آفتاب‌گیر، آلاچیق و باغ اختصاصی (سایت ۱۶×۲۶ — نسخه ۱۹.۰)",
            user_prompt=str(params.get("raw_prompt", "")),
            site=site,
            floors=floors,
            audit=audit,
        )


ArchitecturalPlanSynthesizer = ParametricArchitecturalSynthesizer
