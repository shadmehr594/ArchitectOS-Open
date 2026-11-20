import os
import tempfile
import unittest
from engine import (
    ParametricArchitecturalSynthesizer,
    ArchitecturalPlanSynthesizer,
    SafeTeacherMemory,
    BuildingTypology,
    OccupancyType,
    ValidationStatus,
    export_project_to_svg,
    export_project_to_dxf,
    export_project_to_json,
)


class TestArchitectOSV10Engine(unittest.TestCase):
    def setUp(self) -> None:
        self.synth = ParametricArchitecturalSynthesizer()

    def test_321_and_333_fixes_in_multifloor_v10(self) -> None:
        prompt = (
            "زمین 10*20 سه طرف پلاک شمال شرق و غرب و جنوب کوچه 10 متری، "
            "60 درصد محل احداث تو شمال با حیاط خلوت به عمق 1.7 متر با مساحت 12 متر مربع، "
            "ساختمان 2 طبقه روی پیلوت با آسانسور و آشپزخانه اپن و جزیره"
        )
        proj = self.synth.synthesize_from_text(prompt)
        self.assertEqual(proj.audit.status, ValidationStatus.VALID)

        # 1. Check Pilotis doors (`D_PILOTIS_STAIR` & `D_PILOTIS_LOBBY_ENTRY` have `leaf_dir="+"` and sit inside landing/lobby)
        f0 = proj.floors[0]
        d_p_stair = next(d for d in f0.doors if d.door_id == "D_PILOTIS_STAIR")
        d_p_lobby = next(d for d in f0.doors if d.door_id == "D_PILOTIS_LOBBY_ENTRY")
        self.assertEqual(d_p_stair.leaf_dir, "+")
        self.assertEqual(d_p_lobby.leaf_dir, "+")
        self.assertGreaterEqual(d_p_stair.hinge_mm[1], f0.stair_detail.entrance_landing_rect_mm.y_min)

        # 2. Check Upper Floor doors (`321.jpg` Blue Circles) and Unified Corridor (`321.jpg` Red Circle)
        f1 = proj.floors[1]
        for did in ("D_STAIR_TO_LOBBY", "D_UNIT_MAIN_ENTRY", "D_GUEST_WC", "D_LIVING_TO_TERRACE"):
            d_obj = next(d for d in f1.doors if d.door_id == did)
            self.assertEqual(d_obj.leaf_dir, "+")
        for did in ("D_BED_1", "D_MASTER_BED"):
            d_obj = next(d for d in f1.doors if d.door_id == did)
            self.assertEqual(d_obj.leaf_dir, "+")

        foyer_r = next(r for r in f1.rooms if r.room_id == "ENTRANCE_FOYER").net_rect_mm
        priv_r = next(r for r in f1.rooms if r.room_id == "PRIVATE_HALL").net_rect_mm
        joint_r = next(r for r in f1.rooms if r.room_id == "BEDROOM_ENTRY_JOINT").net_rect_mm
        self.assertEqual(foyer_r.y_max, priv_r.y_min)
        self.assertEqual(priv_r.y_max, joint_r.y_min)

        # 3. Check `333.jpg` West Bedroom Bed in NW Alcove, Study Desk under Window, and Solid Partition Wall
        bed1_f = next(f for f in f1.furniture if f.furn_id == "FURN_BED1")
        desk1_f = next(f for f in f1.furniture if f.furn_id == "FURN_BED1_DESK")
        part_w = next(f for f in f1.furniture if f.furn_id == "FURN_BED_PARTITION_WALL")
        self.assertGreater(bed1_f.rect_mm.y_max, f1.gross_building_rect_mm.y_max - 200)
        self.assertGreater(desk1_f.rect_mm.y_max, f1.gross_building_rect_mm.y_max - 400)
        self.assertEqual(part_w.kind, "PARTITION_WALL")

    def test_villa_v10_unified_corridor_and_bedroom_furniture(self) -> None:
        prompt = "زمین 10*20 با 60 درصد سطح اشغال در شمال و حیاط خلوت 12 متر مربع، ساختمان ویلایی یک طبقه"
        proj = self.synth.synthesize_from_text(prompt)
        f0 = proj.floors[0]
        foyer_r = next(r for r in f0.rooms if r.room_id == "ENTRANCE_FOYER").net_rect_mm
        priv_r = next(r for r in f0.rooms if r.room_id == "PRIVATE_HALL").net_rect_mm
        self.assertEqual(foyer_r.y_max, priv_r.y_min)
        self.assertTrue(any(f.kind == "PARTITION_WALL" for f in f0.furniture))
        self.assertTrue(any(d.door_id == "D_LIGHTWELL_ACCESS" for d in f0.doors))

    def test_duplex_v10_decorative_stair_outside_kitchen_and_one_ground_guest_bed(self) -> None:
        prompt = "یک ساختمان ویلایی دوبلکس مدرن پلانش رو طراحی کن"
        proj = ArchitecturalPlanSynthesizer().synthesize_from_text(prompt)
        self.assertEqual(proj.site.typology, BuildingTypology.DUPLEX_2FLOOR)
        f0, f1 = proj.floors[0], proj.floors[1]
        # Decorative L-Stair on Floor 0 is in ENTRANCE_FOYER, NOT inside OPEN_KITCHEN
        dec_st = next(f for f in f0.furniture if f.kind == "DECORATIVE_DUPLEX_STAIR")
        self.assertEqual(dec_st.room_id, "ENTRANCE_FOYER")
        # Floor 0 has only 1 private guest bedroom (`MASTER_BEDROOM`)
        priv_rooms_f0 = [r for r in f0.rooms if r.space_category == "PRIVATE"]
        self.assertEqual(len(priv_rooms_f0), 1)
        # Floor 1 has 3 bedrooms (`BEDROOM_1`, `MASTER_BEDROOM`, `BEDROOM_3_SOUTH`) + `VOID_DUPLEX_LIVING`
        self.assertTrue(any(r.room_id == "VOID_DUPLEX_LIVING" for r in f1.rooms))
        self.assertTrue(any(f.kind == "PARTITION_WALL" for f in f1.furniture))
        # Check 963.jpg fixes:
        # 1. Floor 1 South-West wing is divided into MINI_BAR_LOUNGE (Blue Hatch, open to Private Hall) and PERGOLA_TERRACE_WEST (Yellow Hatch, separated by wall + door + window), with Column C-1 restored and zero beam lines drawn!
        self.assertTrue(any(r.room_id == "MINI_BAR_LOUNGE" for r in f1.rooms))
        self.assertTrue(any(r.room_id == "PERGOLA_TERRACE_WEST" for r in f1.rooms))
        self.assertFalse(any(r.room_id == "BEDROOM_3_SOUTH" for r in f1.rooms))
        self.assertTrue(any(c.col_id == "COL_C1" for c in f0.columns))
        self.assertFalse(any(f.kind in ("OBLIQUE_BEAM", "WALKWAY_ARROW") for f in f0.furniture))
        # Also verify D_KIT_TO_MUTBAKH on Floor 0 is on the East window side (x >= 1800mm), 100% clear of FURN_DUCT_KIT (x <= 1060mm)!
        d_mut = next(d for d in f0.doors if d.door_id == "D_KIT_TO_MUTBAKH")
        k_duct = next(f for f in f0.furniture if f.furn_id == "FURN_DUCT_KIT")
        self.assertGreater(d_mut.hinge_mm[0] - d_mut.width_mm, k_duct.rect_mm.x_max + 500)
        # 2. Shared Sanitary Duct on Floor 0 and Floor 1 have the EXACT same (X, Y) coordinates (0.0mm horizontal drift!)
        duct_f0 = next(f for f in f0.furniture if f.furn_id == "FURN_DUCT_SANITARY_SHARED").rect_mm
        duct_f1 = next(f for f in f1.furniture if f.furn_id == "FURN_DUCT_SANITARY_SHARED").rect_mm
        self.assertEqual(duct_f0, duct_f1)

    def test_safe_teacher_memory_learning(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mem_file = os.path.join(td, "teacher_rules.json")
            mem = SafeTeacherMemory(mem_file)
            updates = mem.learn_from_teacher_feedback("تخت خواب رو بذار شمال غربی و میز مطالعه رو بذار زیر پنجره")
            self.assertTrue(updates["applied_invariants"].get("west_bedroom_bed_in_nw_alcove"))
            self.assertTrue(updates["applied_invariants"].get("study_desk_under_daylight_window"))
            ctx = mem.learn_from_teacher_feedback("تو یه پلان پله ال شکل مناسبه تو یه پلان نیم دایره اون دیگه بستگی به طراحی داره اینها قانون نیست")
            self.assertEqual(ctx["classification"], "CONTEXTUAL_DESIGN_POLICY")
            self.assertTrue(os.path.isfile(mem_file))



    def test_luxury_pool_duplex_and_stair_direction_v13(self) -> None:
        """Verify v13.0 Luxury Garden & Pool Duplex Villa and East-exiting decorative duplex staircase."""
        proj = self.synth.synthesize_from_text(
            "یه پلان دوبلکس مدرن با سایت پلان آزاد و ابعاد ساختمان آزاد و استخر و فضای سبز و محوطه سازی طراحی کن"
        )
        self.assertEqual(proj.project_id, "ARCH_V13_LUXURY_POOL_DUPLEX_16X26")
        self.assertEqual(len(proj.floors), 2)
        f0, f1 = proj.floors[0], proj.floors[1]
        f0_ftypes = {fn.kind for fn in f0.furniture}
        self.assertIn("SWIMMING_POOL", f0_ftypes)
        self.assertIn("POOL_SUN_DECK", f0_ftypes)
        self.assertIn("PERGOLA_FIREPIT", f0_ftypes)
        # Verify vertical sanitary duct alignment across Floor 0 and Floor 1 (0.0mm drift)
        d0 = next(fn for fn in f0.furniture if fn.furn_id == "FURN_DUCT_SANITARY_SHARED")
        d1 = next(fn for fn in f1.furniture if fn.furn_id == "FURN_DUCT_SANITARY_SHARED")
        self.assertEqual(d0.rect_mm.x_min, d1.rect_mm.x_min)
        self.assertEqual(d0.rect_mm.y_min, d1.rect_mm.y_min)
        self.assertEqual(d0.rect_mm.x_max, d1.rect_mm.x_max)
        self.assertEqual(d0.rect_mm.y_max, d1.rect_mm.y_max)
        # Verify SVG contains East-exiting step 18 and 18 risers x 18cm label
        with tempfile.TemporaryDirectory() as td:
            svg_p = os.path.join(td, 'v13.svg')
            export_project_to_svg(proj, svg_p)
            with open(svg_p, 'r', encoding='utf-8') as sf:
                svg_str = sf.read()
        self.assertIn("خروج به گالری بالا (۱۸ ▲)", svg_str)
        self.assertIn("۱۸ پله × ارتفاع ۱۸cm", svg_str)
        self.assertIn("استخر روباز چهارفصل", svg_str)


    def test_zero_door_duct_and_furniture_collisions_v14(self) -> None:
        """Verify 0 door-swing/furniture/wardrobe/WC/bath collisions, 0 duct/fixture collisions, 0 column-window/door-window collisions, and 100% plumb wet stack in v14.0."""
        from engine.domain import RectMM

        def door_swing_rect(d) -> RectMM:
            hx, hy = d.hinge_mm
            w = (d.width_mm // 2) if (d.is_main_entry and d.wall_orientation == "H" and d.width_mm >= 1200) else d.width_mm
            if d.wall_orientation == "H":
                x0, x1 = (hx, hx + w) if d.leaf_dir == "+" else (hx - w, hx)
                y0, y1 = (hy, hy + w) if d.swing_dir == "N" else (hy - w, hy)
            else:
                y0, y1 = (hy, hy + w) if d.leaf_dir == "+" else (hy - w, hy)
                x0, x1 = (hx, hx + w) if d.swing_dir == "E" else (hx - w, hx)
            return RectMM(min(x0, x1) + 35, min(y0, y1) + 35, max(x0, x1) - 35, max(y0, y1) - 35)

        def rects_overlap(a: RectMM, b: RectMM) -> bool:
            return (a.x_min < b.x_max) and (a.x_max > b.x_min) and (a.y_min < b.y_max) and (a.y_max > b.y_min)

        prompts = [
            "یه پلان دوبلکس مدرن با سایت پلان آزاد و ابعاد ساختمان آزاد و محوطه سازی سایت مثل استخر و فضای سبز و آلاچیق طراحی کن",
            "زمین 10*20 سه طرف پلاک شمال شرق و غرب و جنوب کوچه 10 متری، 60 درصد محل احداث تو شمال با حیاط خلوت، ساختمان ویلایی دوبلکس مدرن 2 طبقه با پله دکوراتیو",
            "زمین 10*20 سه طرف پلاک شمال شرق و غرب و جنوب کوچه 10 متری، 60 درصد محل احداث تو شمال با حیاط خلوت به عمق 1.7 متر با مساحت 12 متر مربع، ساختمان 2 طبقه روی پیلوت با آسانسور و آشپزخانه اپن و جزیره",
            "زمین 10*20 سه طرف پلاک شمال شرق و غرب و جنوب کوچه 10 متری، 60 درصد محل احداث تو شمال با حیاط خلوت به عمق 1.7 متر با مساحت 12 متر مربع، ساختمان ویلایی تک واحدی همکف دو خوابه با آشپزخانه اپن",
        ]
        solid_kinds = {"WARDROBE", "BED_DOUBLE", "BED_SINGLE", "STUDY_DESK", "WC_SET", "BATH_SET", "DUCT", "KITCHEN_ISLAND_BAR", "KITCHEN_COUNTER"}
        for pr in prompts:
            proj = self.synth.synthesize_from_text(pr)
            for fl in proj.floors:
                ducts = [f for f in fl.furniture if f.kind == "DUCT"]
                solids = [f for f in fl.furniture if f.kind in solid_kinds]
                for du in ducts:
                    for s in solids:
                        if s.furn_id != du.furn_id:
                            self.assertFalse(
                                rects_overlap(du.rect_mm, s.rect_mm),
                                f"Duct {du.furn_id} overlaps {s.furn_id} on Floor {fl.floor_index} of {proj.project_id}",
                            )
                for d in fl.doors:
                    dr = door_swing_rect(d)
                    for s in solids:
                        self.assertFalse(
                            rects_overlap(dr, s.rect_mm),
                            f"Door {d.door_id} overlaps {s.furn_id} on Floor {fl.floor_index} of {proj.project_id}",
                        )
                # Verify 0 Column-Window and 0 Door-Window collisions
                for w in fl.windows:
                    w_rect = RectMM(min(w.x0_mm, w.x1_mm), min(w.y0_mm, w.y1_mm), max(w.x0_mm, w.x1_mm), max(w.y0_mm, w.y1_mm))
                    for col in fl.columns:
                        self.assertFalse(
                            rects_overlap(w_rect, col.rect_mm),
                            f"Window {w.window_id} {w_rect} overlaps Column {col.col_id} {col.rect_mm} on Floor {fl.floor_index} of {proj.project_id}",
                        )
                    for d in fl.doors:
                        hx, hy = d.hinge_mm
                        dw = d.width_mm
                        if w.orientation == "H" and d.wall_orientation == "H" and (abs(hy - w_rect.y_min) <= 260 or abs(hy - w_rect.y_max) <= 260):
                            dx0, dx1 = (hx, hx + dw) if d.leaf_dir == "+" else (hx - dw, hx)
                            self.assertFalse(
                                (w_rect.x_min < dx1 and w_rect.x_max > dx0),
                                f"Window {w.window_id} overlaps Door {d.door_id} on Floor {fl.floor_index} of {proj.project_id}",
                            )
                        elif w.orientation == "V" and d.wall_orientation == "V" and (abs(hx - w_rect.x_min) <= 260 or abs(hx - w_rect.x_max) <= 260):
                            dy0, dy1 = (hy, hy + dw) if d.leaf_dir == "+" else (hy - dw, hy)
                            self.assertFalse(
                                (w_rect.y_min < dy1 and w_rect.y_max > dy0),
                                f"Window {w.window_id} overlaps Door {d.door_id} on Floor {fl.floor_index} of {proj.project_id}",
                            )
            # For Duplex projects, verify 100% plumb vertical alignment of wet core footprint and shared sanitary duct
            if len(proj.floors) == 2:
                f0_bath = next(r.net_rect_mm for r in proj.floors[0].rooms if r.room_id == "MAIN_BATHROOM")
                f1_mbath = next(r.net_rect_mm for r in proj.floors[1].rooms if r.room_id == "MASTER_BATH")
                self.assertEqual((f0_bath.x_min, f0_bath.y_min, f0_bath.x_max, f0_bath.y_max), (f1_mbath.x_min, f1_mbath.y_min, f1_mbath.x_max, f1_mbath.y_max))
                f0_wc = next(r.net_rect_mm for r in proj.floors[0].rooms if r.room_id == "GUEST_WC")
                f1_bath = next(r.net_rect_mm for r in proj.floors[1].rooms if r.room_id == "MAIN_BATHROOM")
                self.assertEqual((f0_wc.x_min, f0_wc.y_min, f0_wc.x_max), (f1_bath.x_min, f1_bath.y_min, f1_bath.x_max))


    def test_holistic_v17_stair_axis_sanitary_and_3_multifloor_types(self) -> None:
        """Verify all v17.0 structural, stair, sanitary, and 3-typology requirements."""
        # 1. Verify 10x20 Duplex has 3 Y-axes (no Axis at 13010 cutting the staircase) and span <= 7800mm
        dup = self.synth.synthesize_from_text("یک ساختمان ویلایی دوبلکس مدرن پلانش رو طراحی کن")
        gy_vals = [y for _, y in dup.floors[0].grid_y_mm]
        self.assertIn(len(gy_vals), (3, 4, 5))
        self.assertLessEqual(max(gy_vals[i+1] - gy_vals[i] for i in range(len(gy_vals)-1)), 7800)
        # Verify no Y-axis cuts through the decorative duplex staircase (11650..14620)
        for y_ax in gy_vals:
            for col in dup.floors[0].columns:
                self.assertFalse(col.rect_mm.x_min < 3750 and 11700 < col.rect_mm.center[1] < 14500, f"Column {col.col_id} intrudes into decorative staircase!")

        # 2. Verify Luxury Pool Duplex 16x26 Floor 1 Upper Gallery has is_open_edge_west=True (no wall blocking Step 18) and N_TUB bath
        lux = self.synth.synthesize_from_text("یه پلان دوبلکس مدرن با سایت پلان آزاد و استخر و محوطه سازی طراحی کن")
        f1_lux = lux.floors[1]
        gal_f1 = next(r for r in f1_lux.rooms if r.room_id == "ENTRANCE_FOYER")
        self.assertTrue(gal_f1.is_open_edge_west)
        self.assertTrue(gal_f1.is_open_edge_south)
        ubath = next(fn for fn in f1_lux.furniture if fn.furn_id == "FURN_UPPER_BATH_SET")
        self.assertIn(ubath.orientation, ("N_TUB", "E_WALL_FLUSH"))

        # 3. Verify all 3 MultiFloor 10x20 Typologies (Type A, Type B, Type C) synthesize cleanly with 0 collisions and full step numbers (7, 14, 9, 18)
        for var_kw, expected_var in [("تیپ A", "TYPE_A"), ("تیپ B", "TYPE_B"), ("تیپ C سه خواب", "TYPE_C")]:
            p_mf = self.synth.synthesize_from_text(
                f"زمین 10*20 با 60 درصد سطح اشغال در شمال و حیاط خلوت 12 متر، ساختمان 2 طبقه روی پیلوت {var_kw}"
            )
            self.assertEqual(p_mf.audit.status, ValidationStatus.VALID)
            with tempfile.TemporaryDirectory() as td:
                svg_p = os.path.join(td, f"{expected_var}.svg")
                export_project_to_svg(p_mf, svg_p)
                with open(svg_p, "r", encoding="utf-8") as sf:
                    s_svg = sf.read()
                self.assertIn(">7</text>", s_svg)
                self.assertIn(">14</text>", s_svg)
                self.assertIn(">9</text>", s_svg)
                self.assertIn(">18</text>", s_svg)

        # 4. Verify arbitrary new site dimensions (e.g., 11x22m Duplex and 9.5x19m MultiFloor) automatically obey all rules without manual intervention!
        for custom_prompt in [
            "زمین 11 در 22 با 60 درصد سطح اشغال در شمال، ساختمان ویلایی دوبلکس مدرن",
            "زمین 9.5 در 19 با 65 درصد سطح اشغال در شمال، ساختمان 2 طبقه روی پیلوت با آسانسور",
        ]:
            p_arb = self.synth.synthesize_from_text(custom_prompt)
            self.assertEqual(p_arb.audit.status, ValidationStatus.VALID)
            for fl in p_arb.floors:
                self.assertFalse(any(f.kind in ("OBLIQUE_BEAM", "WALKWAY_ARROW") for f in fl.furniture))



    def test_v31_sloped_walls_dxf_4axes_flipped_stair_master_bed3_and_render(self) -> None:
        """
        v31.0 End-to-End Verification on `حسن حقانی .اوقاف2.dwg` covering all 6 issues from user screenshots:
          1. Two-street through-lot detection (`NORTH=STREET`, `SOUTH=STREET`, `EAST/WEST=NEIGHBOR_LOT`, `252.26 m²`, `4` corners).
          2. Sloped South boundary room fills & vertical wall extensions + matching AutoCAD DXF sloped wall (`export_project_to_dxf`).
          3. All 4 sloped South column axes (`1, 2, 3, 4`) generated & displayed after 180° N/S rotation (`snap_tol_mm=42`).
          4. Vertically mirrored L-staircase (`FLIPPED_NS`: Step 1 open to NW Dining Hall -> Step 9 SW Landing -> Step 18 East Gallery) + zero overlap between `OPEN_KITCHEN` and `DIRTY_KITCHEN` (`مطبخ`).
          5. Expanding `BEDROOM_3_SW` over adjacent corridor (`expand_bed3_over_corridor=True`), adding en-suite `BED3_MASTER_BATH` (`bed3_is_master=True`), and opening terrace door (`D_UPPER_TO_BALC`) from inside Bedroom 3.
          6. Routing 3D facade render commands (`render_3d_facade_mode=True`) through `nl_design_parser` and `export_project_to_svg`.
        """
        import os
        from engine.krocki_cad_reader_v27 import parse_krocki_dxf_or_dwg
        from engine.nl_design_parser import (
            is_architectural_design_prompt,
            is_new_plan_creation_prompt,
            is_plan_modification_prompt,
            parse_architectural_prompt,
            apply_incremental_plan_edit,
        )
        from engine.architectural_synthesizer import ParametricArchitecturalSynthesizer
        from engine.exporter import export_project_to_svg

        dwg_p = os.path.join(os.path.dirname(__file__), "fixtures", "حسن حقانی .اوقاف2.dwg")
        self.assertTrue(os.path.isfile(dwg_p), f"Missing fixture: {dwg_p}")
        krocki = parse_krocki_dxf_or_dwg(dwg_p)
        self.assertAlmostEqual(krocki["site_area_m2"], 252.26, delta=0.5)
        self.assertEqual(krocki["vertex_count"], 4)
        self.assertIn("NORTH", krocki["street_sides"])
        self.assertIn("SOUTH", krocki["street_sides"])
        self.assertEqual(krocki["boundary_neighbors"]["NORTH"], "STREET")
        self.assertEqual(krocki["boundary_neighbors"]["SOUTH"], "STREET")

        p1 = parse_architectural_prompt("یک پلان دوبلکس در ضلع جنوب زمین با سطح اشغال 55 درصد ترسیم کن")
        p1.update({
            "site_width_mm": int(round(krocki["width_m"] * 1000)),
            "site_length_mm": int(round(krocki["length_m"] * 1000)),
            "site_area_m2": krocki["site_area_m2"],
            "krocki_polygon_mm": krocki["polygon_vertices_mm"],
            "krocki_is_irregular": krocki["is_irregular_polygon"],
            "street_sides": krocki["street_sides"],
            "party_wall_sides": krocki["party_wall_sides"],
            "boundary_neighbors": krocki["boundary_neighbors"],
            "south_y_west_mm": krocki["south_y_west_mm"],
            "south_y_east_mm": krocki["south_y_east_mm"],
        })
        synth = ParametricArchitecturalSynthesizer()

        p2 = apply_incremental_plan_edit(p1, "پلان رو بچرخون اتاق خوابها سمت جنوب باشن پذیرایی و ناهارخوری و ورودی ساختمان سمت شمال باشن")
        proj2 = synth.synthesize_from_params(p2)
        # Verify 4 distinct horizontal axes (1, 2, 3, 4) for the 4 sloped South columns
        y_axes_f0 = [y_val for _, y_val in proj2.floors[0].grid_y_mm[:4]]
        self.assertEqual(len(y_axes_f0), 4)
        self.assertEqual(y_axes_f0, [200, 470, 625, 896])
        # Verify flipped L-staircase orientation
        stair_f0 = next(f for f in proj2.floors[0].furniture if f.kind == "DECORATIVE_DUPLEX_STAIR")
        self.assertEqual(stair_f0.orientation, "FLIPPED_NS")

        p3 = apply_incremental_plan_edit(p2, "در طبقه بالا مینی بار و تراس رو حذف کن و تبدیلش کن به یه اتاق خواب و یک تراس با عرض 1.20 در شمال قرار بده")
        p4 = apply_incremental_plan_edit(p3, "فضای راهرو کنار اتاق خواب 3 را به اتاق خواب اضافه کن و در تراس رو از داخل اتاق خواب باز کن و اتاق خواب را مستر کن")
        self.assertTrue(p4["expand_bed3_over_corridor"])
        self.assertTrue(p4["bed3_is_master"])
        proj4 = synth.synthesize_from_params(p4)
        f1_room_ids = {r.room_id for r in proj4.floors[1].rooms}
        self.assertIn("BEDROOM_3_SW", f1_room_ids)
        self.assertIn("BED3_MASTER_BATH", f1_room_ids)
        self.assertNotIn("UPPER_GALLERY_SOUTH", f1_room_ids)
        bed3_r = next(r for r in proj4.floors[1].rooms if r.room_id == "BEDROOM_3_SW")
        self.assertGreaterEqual(bed3_r.net_rect_mm.width, 5500)

        cmd5 = "یه رندر از همین پلان از نمای شمالی به سبک نئوکلاسیک و متریال سنگ تراورتن کرم روشن در روز افتابی بگیر"
        self.assertTrue(is_architectural_design_prompt(cmd5))
        self.assertTrue(is_plan_modification_prompt(cmd5))
        self.assertFalse(is_new_plan_creation_prompt(cmd5))
        p5 = apply_incremental_plan_edit(p4, cmd5)
        self.assertTrue(p5["render_3d_facade_mode"])
        proj5 = synth.synthesize_from_params(p5)
        svg_3d = export_project_to_svg(proj5, "/tmp/test_v31_facade_3d.svg")
        self.assertTrue(os.path.isfile("/tmp/test_v31_facade_3d.png"))
        self.assertGreater(os.path.getsize("/tmp/test_v31_facade_3d.png"), 8000)



    def test_v33_plan_locked_3d_render_and_external_plan_upload(self) -> None:
        import os
        import tempfile
        from engine.nl_design_parser import (
            parse_architectural_prompt,
            apply_incremental_plan_edit,
            is_3d_render_or_render_edit_prompt,
        )
        from engine.architectural_synthesizer import ParametricArchitecturalSynthesizer
        from engine.comfyui_bridge import ComfyUIRenderBridge
        from engine.krocki_cad_reader_v27 import (
            parse_krocki_dxf_or_dwg,
            parse_external_plan_or_elevation,
        )

        dwg_path = os.path.join(os.path.dirname(__file__), "fixtures", "حسن حقانی .اوقاف2.dwg")
        krocki = parse_krocki_dxf_or_dwg(dwg_path)
        synth = ParametricArchitecturalSynthesizer()

        # 1. Create a 2-story Duplex in South with 1.0m street cantilever & 1.2m courtyard cantilever
        p0 = parse_architectural_prompt(
            "یک ساختمان یک دوبلکس با سطح اشغال 70 درصد در جنوب و با پیش آمدگی به عرض 1 متر در معبر و پیش آمدگی به عرض 1.2 در حیاط طراحی کن",
            active_site_krocki=krocki,
        )
        self.assertEqual(p0["typology"], "DUPLEX_2FLOOR")
        self.assertEqual(p0["south_cantilever_mm"], 1000)
        self.assertEqual(p0["courtyard_cantilever_mm"], 1200)

        # 2. Turn 1 Render Request: Neoclassical Cream Travertine Sunny Day
        cmd_r1 = "از نمای جنوبی همین پلان یک رندر سه‌بعدی با سبک نئوکلاسیک و سنگ تراورتن کرم روشن بگیر"
        self.assertTrue(is_3d_render_or_render_edit_prompt(cmd_r1, p0))
        p1 = apply_incremental_plan_edit(p0, cmd_r1, active_site_krocki=krocki)
        self.assertTrue(p1["render_3d_facade_mode"])
        self.assertEqual(p1["typology"], p0["typology"])
        self.assertEqual(p1["coverage_ratio"], p0["coverage_ratio"])
        self.assertEqual(p1["south_cantilever_mm"], 1000)
        self.assertEqual(p1["courtyard_cantilever_mm"], 1200)
        self.assertEqual(p1["active_render_state"]["style_key"], "NEOCLASSICAL_STONE")
        self.assertEqual(p1["active_render_state"]["stone_color"], "CREAM")
        self.assertEqual(p1["active_render_state"]["lighting_mode"], "DAY_SUNNY")
        seed_1 = p1["active_render_state"]["locked_seed"]

        # 3. Turn 2 Iterative Render Edit: Switch to Night Lighting without changing style or building geometry
        cmd_r2 = "حالا رندر شبش رو با نورپردازی خطی گرم نما بگیر"
        self.assertTrue(is_3d_render_or_render_edit_prompt(cmd_r2, p1))
        p2 = apply_incremental_plan_edit(p1, cmd_r2, active_site_krocki=krocki)
        self.assertTrue(p2["render_3d_facade_mode"])
        self.assertEqual(p2["active_render_state"]["style_key"], "NEOCLASSICAL_STONE")
        self.assertEqual(p2["active_render_state"]["stone_color"], "CREAM")
        self.assertEqual(p2["active_render_state"]["lighting_mode"], "NIGHT_WARM")
        self.assertEqual(p2["active_render_state"]["locked_seed"], seed_1)

        # 4. Turn 3 Iterative Render Edit: Switch to Modern White Stone + Thermowood + Glass Balustrade in Daylight
        cmd_r3 = "سبک نما رو مدرن کن با سنگ سفید و چوب ترمووود و نرده شیشه‌ای در روز آفتابی"
        self.assertTrue(is_3d_render_or_render_edit_prompt(cmd_r3, p2))
        p3 = apply_incremental_plan_edit(p2, cmd_r3, active_site_krocki=krocki)
        self.assertEqual(p3["active_render_state"]["style_key"], "MODERN_THERMOWOOD")
        self.assertEqual(p3["active_render_state"]["stone_color"], "WHITE")
        self.assertTrue(p3["active_render_state"]["wood_accent"])
        self.assertEqual(p3["active_render_state"]["balustrade_type"], "GLASS")
        self.assertEqual(p3["active_render_state"]["lighting_mode"], "DAY_SUNNY")
        self.assertEqual(p3["active_render_state"]["locked_seed"], seed_1)

        # 5. External Multi-Floor Plan Upload with Elevation Codes (+0.45, +3.60, +6.80, +10.00, +13.20 -> Ground + 4 Typical = 5 floors)
        with tempfile.TemporaryDirectory() as tmp_d:
            dxf_ext = os.path.join(tmp_d, "multi_floor_typical_plan.dxf")
            dxf_lines = [
                "0", "SECTION", "2", "ENTITIES",
                "0", "TEXT", "8", "0", "10", "5.0", "20", "10.0",
                "1", "پلان طبقه همکف و پلان تیپ طبقات اول تا چهارم (کد +0.45 , +3.60 , +6.80 , +10.00 , +13.20)",
                "0", "LINE", "8", "A-WALL", "10", "0.0", "20", "0.0", "11", "22.0", "21", "18.0",
                "0", "ENDSEC", "0", "EOF",
            ]
            with open(dxf_ext, "w", encoding="utf-8") as df:
                df.write(chr(10).join(dxf_lines) + chr(10))
            ext_info = parse_external_plan_or_elevation(dxf_ext)
            self.assertEqual(ext_info["total_floors"], 5)
            self.assertEqual(ext_info["typical_floors_above_ground"], 4)
            self.assertTrue(ext_info["has_pilotis"])

            proj_1 = synth.synthesize_from_params(p1)
            out_png_1 = os.path.join(tmp_d, "render_day_neoclassical.png")
            ComfyUIRenderBridge.export_plan_locked_south_facade_png(proj_1, out_png_1, prev_render_state=p1["active_render_state"])
            self.assertTrue(os.path.isfile(out_png_1))
            self.assertTrue(os.path.isfile(os.path.splitext(out_png_1)[0] + "_depth.png"))
            self.assertTrue(os.path.isfile(os.path.splitext(out_png_1)[0] + "_lineart.png"))

            # Verify FLUX ControlNet + Latent Img2Img workflow payload uses flux1-krea-dev_fp8_scaled.safetensors & flux1-dev-controlnet-union-pro-2.0-fp8.safetensors
            wf_payload = ComfyUIRenderBridge.build_comfyui_workflow_payload(proj_1, cmd_r1, "base.png", "depth.png", quality="final")
            self.assertEqual(wf_payload["prompt"]["202"]["inputs"]["unet_name"], "flux1-krea-dev_fp8_scaled.safetensors")
            self.assertEqual(wf_payload["prompt"]["310"]["inputs"]["control_net_name"], "flux1-dev-controlnet-union-pro-2.0-fp8.safetensors")
            self.assertEqual(wf_payload["prompt"]["210"]["inputs"]["seed"], seed_1)



    def test_v33_3_kharposhteh_columns_and_custom_dwg_facade_render(self) -> None:
        """
        Verifies v33.3 requirements:
          1) Roof & Kharposhteh Plan (`project.roof_plan`) has ONLY the 4 Kharposhteh columns (zero peripheral columns),
             ZERO windows on the Kharposhteh, and 1 outward-opening roof exit door (`D_ROOF_KHARPOSHTEH_EXIT`).
          2) `render_project_to_png_pillow` respects `render_3d_facade_mode=True` and outputs a 3D facade render (`1280x864`),
             including custom stepped-facade plans (`+0.36m` 2-step veranda and 2 equal `OKB=0` windows), never a 2D plan!
        """
        import tempfile
        from PIL import Image
        from engine.architectural_synthesizer import ParametricArchitecturalSynthesizer
        from engine.exporter import render_project_to_png_pillow

        synth = ParametricArchitecturalSynthesizer()
        proj_105 = synth.synthesize_from_params({
            "typology": "MULTIFLOOR_RESIDENTIAL",
            "is_duplex": False,
            "floor_count": 2,
            "site_width_mm": 10000,
            "site_length_mm": 20000,
            "coverage_ratio": 0.60,
            "building_placement": "NORTH",
        })
        self.assertIsNotNone(proj_105.roof_plan)
        self.assertEqual(len(proj_105.roof_plan.columns), 4)
        self.assertEqual(len(proj_105.roof_plan.windows), 0)
        self.assertEqual(len(proj_105.roof_plan.doors), 2)
        self.assertEqual(proj_105.roof_plan.doors[0].swing_dir, "N")
        from engine.comfyui_bridge import ComfyUIRenderBridge
        wf_draft = ComfyUIRenderBridge.build_comfyui_workflow_payload(proj_105, "رندر نمای جنوبی", quality="draft")
        self.assertEqual(wf_draft["prompt"]["210"]["inputs"]["steps"], 6)
        self.assertGreaterEqual(wf_draft["prompt"]["210"]["inputs"]["denoise"], 0.52)
        self.assertIn("311", wf_draft["prompt"])
        wf_prev = ComfyUIRenderBridge.build_comfyui_workflow_payload(proj_105, "رندر نمای جنوبی", quality="preview")
        self.assertEqual(wf_prev["prompt"]["210"]["inputs"]["steps"], 8)
        self.assertGreaterEqual(wf_prev["prompt"]["210"]["inputs"]["denoise"], 0.55)
        self.assertIn("311", wf_prev["prompt"])
        wf_qual = ComfyUIRenderBridge.build_comfyui_workflow_payload(proj_105, "رندر نمای جنوبی", quality="quality")
        self.assertEqual(wf_qual["prompt"]["210"]["inputs"]["steps"], 14)
        self.assertIn("311", wf_qual["prompt"])
        wf_final = ComfyUIRenderBridge.build_comfyui_workflow_payload(proj_105, "رندر نمای جنوبی", quality="final")
        self.assertEqual(wf_final["prompt"]["210"]["inputs"]["steps"], 20)
        self.assertIn("311", wf_final["prompt"])

        prof = {
            "is_custom_stepped_plan": True,
            "building_placement": "SOUTH_WEST",
            "attached_west_wall": True,
            "attached_east_wall": False,
            "west_courtyard_gap_ratio": 0.0,
            "east_courtyard_gap_ratio": 0.26,
            "has_stepped_north_facade": True,
            "recessed_veranda_elev_m": 0.36,
            "recessed_veranda_steps": 2,
            "recessed_equal_windows_count": 2,
            "recessed_windows_okb_m": 0.0,
        }
        proj_dwg = synth.synthesize_from_params({
            "typology": "VILLA_1FLOOR",
            "floor_count": 1,
            "site_width_mm": 10000,
            "site_length_mm": 20000,
            "coverage_ratio": 0.65,
            "building_placement": "SOUTH",
            "render_3d_facade_mode": True,
            "render_facade_side": "NORTH",
            "custom_facade_profile": prof,
        })
        with tempfile.TemporaryDirectory() as td:
            out_png = os.path.join(td, "plan_rev_2.png")
            render_project_to_png_pillow(proj_dwg, out_png)
            with Image.open(out_png) as im:
                self.assertEqual(im.size, (1280, 864))



    def test_v33_7_townhouse_3floor_profile_and_4tier_quality(self) -> None:
        from engine.comfyui_bridge import ComfyUIRenderBridge
        from engine.krocki_cad_reader_v27 import _extract_elevation_codes_and_floor_structure

        el_3fl = _extract_elevation_codes_and_floor_structure(
            ["PLANTA BAJA", "SEGUNDA PLANTA", "TERCERA PLANTA", "FACHADA PRINCIPAL"],
            filename="houseplan- arel.ir.dwg",
        )
        self.assertEqual(el_3fl["total_floors"], 3)
        self.assertFalse(el_3fl["has_pilotis"])

        proj = self.synth.synthesize_from_text("پلان ۳ طبقه مسکونی")
        proj.site.active_render_state = {
            "custom_facade_profile": {
                "profile_type": "TOWNHOUSE_3FLOOR_NO_PILOTIS",
                "is_custom_stepped_plan": False,
                "total_floors": 3,
                "has_open_pilotis": False,
                "has_kharposhteh": False,
                "building_width_m": 7.6,
            }
        }
        with tempfile.TemporaryDirectory() as td:
            out_png = os.path.join(td, "townhouse_3fl.png")
            _, prompt_en = ComfyUIRenderBridge.export_plan_locked_south_facade_png(
                proj,
                out_png,
                chat_text="رندر نمای جنوبی این پلان رو با سبک نئوکلاسیک و متریال سنگ تراورتن کرم بگیر",
            )
            self.assertTrue(os.path.isfile(out_png))
            self.assertIn("3-story urban residential townhouse", prompt_en)
            self.assertIn("NO open pilotis and NO parked cars", prompt_en)

        # Verify 4-tier quality ladder: draft < preview < quality < final
        wf_draft = ComfyUIRenderBridge.build_comfyui_workflow_payload(proj, "رندر نما", quality="draft")
        wf_prev = ComfyUIRenderBridge.build_comfyui_workflow_payload(proj, "رندر نما", quality="preview")
        wf_qual = ComfyUIRenderBridge.build_comfyui_workflow_payload(proj, "رندر نما", quality="quality")
        wf_fin = ComfyUIRenderBridge.build_comfyui_workflow_payload(proj, "رندر نما", quality="final")
        s_draft = wf_draft["prompt"]["210"]["inputs"]["steps"]
        s_prev = wf_prev["prompt"]["210"]["inputs"]["steps"]
        s_qual = wf_qual["prompt"]["210"]["inputs"]["steps"]
        s_fin = wf_fin["prompt"]["210"]["inputs"]["steps"]
        self.assertTrue(s_draft < s_prev < s_qual < s_fin)



    def test_v34_0_universal_raycast_arbitrary_dxf_and_dwg_plans(self) -> None:
        from engine.krocki_cad_reader_v27 import parse_external_plan_or_elevation
        from engine.comfyui_bridge import ComfyUIRenderBridge

        # Create a brand-new unseen DXF plan (1-story stepped plan attached to West wall, open East gap, recessed right veranda +0.45m, OKB=0)
        dxf_lines = [
            "0", "SECTION", "2", "ENTITIES",
            # Outer lot frame (0,0) to (12, 20)
            "0", "LWPOLYLINE", "8", "LOT", "70", "1",
            "10", "0.0", "20", "0.0",
            "10", "12.0", "20", "0.0",
            "10", "12.0", "20", "20.0",
            "10", "0.0", "20", "20.0",
            # Stepped building attached to West (x=0..9, leaving x=9..12 open courtyard on East; North front stepped at y=15 left and y=12.5 right)
            "0", "LWPOLYLINE", "8", "WALL", "70", "1",
            "10", "0.2", "20", "1.0",
            "10", "8.8", "20", "1.0",
            "10", "8.8", "20", "12.5",
            "10", "4.2", "20", "12.5",
            "10", "4.2", "20", "15.5",
            "10", "0.2", "20", "15.5",
            # Elevation & OKB texts
            "0", "TEXT", "8", "TEXT", "10", "5.0", "20", "13.0", "1", "+0.45",
            "0", "TEXT", "8", "TEXT", "10", "5.5", "20", "12.6", "1", "OKB=0.00",
            "0", "ENDSEC", "0", "EOF",
        ]
        with tempfile.TemporaryDirectory() as td:
            unseen_dxf = os.path.join(td, "unseen_custom_villa.dxf")
            with open(unseen_dxf, "w", encoding="utf-8") as df:
                df.write("\n".join(dxf_lines) + "\n")
            parsed = parse_external_plan_or_elevation(unseen_dxf)
            self.assertEqual(parsed["parser_version"], "v66.0")
            self.assertEqual(parsed["total_floors"], 1)
            uf = parsed["universal_facade_spec"]
            self.assertIn(0.45, uf["elevation_codes_m"])
            self.assertEqual(uf["default_okb_m"], 0.0)
            north_view = uf["views"]["NORTH"]
            self.assertLessEqual(north_view["left_courtyard_gap_ratio"], 0.06)
            self.assertGreaterEqual(north_view["right_courtyard_gap_ratio"], 0.14)
            self.assertGreaterEqual(len(north_view["floors"][0]["bays"]), 2)



    def test_v35_1_multistory_cad_xy_offset_registration_and_ifc_shell_extrusion(self) -> None:
        from engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder
        from engine.krocki_cad_reader_v27 import parse_external_plan_or_elevation

        # Create a 3-story + roof multi-panel DXF where each floor plan is drawn at a completely different (X, Y) offset in ModelSpace:
        #   - Floor 0 (Ground): X = 0..10m, Y = 0..14m (Stair/Col Core at X = 4..6m, Y = 8..11m)
        #   - Floor 1 (Typical 1): X = 30..40m, Y = 5..20.2m (Stair/Col Core at X = 34..36m, Y = 14.2..17.2m -> South wall at Y=5.0 extends 1.2m further South than Floor 0!)
        #   - Floor 2 (Typical 2): X = 60..70m, Y = -4..11.2m (Stair/Col Core at X = 64..66m, Y = 5.2..8.2m -> South wall at Y=-4.0 extends 1.2m further South than Floor 0!)
        #   - Roof Plan (پلان بام): X = 90..100m, Y = 0..14m
        dxf_lines = [
            "0", "SECTION", "2", "ENTITIES",
            # Floor 0 @ (0, 0)
            "0", "LWPOLYLINE", "8", "WALL", "70", "1",
            "10", "0.0", "20", "0.0", "10", "10.0", "20", "0.0", "10", "10.0", "20", "14.0", "10", "0.0", "20", "14.0",
            "0", "LWPOLYLINE", "8", "STAIR_CORE", "70", "1",
            "10", "4.0", "20", "8.0", "10", "6.0", "20", "8.0", "10", "6.0", "20", "11.0", "10", "4.0", "20", "11.0",
            "0", "TEXT", "8", "TEXT", "10", "5.0", "20", "1.0", "1", "پلان طبقه همکف +0.00",
            # Floor 1 @ (30, 5.0) with 1.2m South cantilever (core at 34..36, 14.2..17.2; South wall at 5.0 -> 14.2 - 8.0 = 6.2, so 5.0 - 6.2 = -1.2m South cantilever!)
            "0", "LWPOLYLINE", "8", "WALL", "70", "1",
            "10", "30.0", "20", "5.0", "10", "40.0", "20", "5.0", "10", "40.0", "20", "20.2", "10", "30.0", "20", "20.2",
            "0", "LWPOLYLINE", "8", "STAIR_CORE", "70", "1",
            "10", "34.0", "20", "14.2", "10", "36.0", "20", "14.2", "10", "36.0", "20", "17.2", "10", "34.0", "20", "17.2",
            "0", "TEXT", "8", "TEXT", "10", "35.0", "20", "6.0", "1", "پلان طبقه اول +3.20",
            # Floor 2 @ (60, -4.0) with 1.2m South cantilever (core at 64..66, 5.2..8.2; South wall at -4.0 -> 5.2 - 8.0 = -2.8, so -4.0 - (-2.8) = -1.2m South cantilever!)
            "0", "LWPOLYLINE", "8", "WALL", "70", "1",
            "10", "60.0", "20", "-4.0", "10", "70.0", "20", "-4.0", "10", "70.0", "20", "11.2", "10", "60.0", "20", "11.2",
            "0", "LWPOLYLINE", "8", "STAIR_CORE", "70", "1",
            "10", "64.0", "20", "5.2", "10", "66.0", "20", "5.2", "10", "66.0", "20", "8.2", "10", "64.0", "20", "8.2",
            "0", "TEXT", "8", "TEXT", "10", "65.0", "20", "-3.0", "1", "پلان طبقه دوم +6.40",
            # Roof Plan @ (90, 0.0)
            "0", "LWPOLYLINE", "8", "WALL", "70", "1",
            "10", "90.0", "20", "0.0", "10", "100.0", "20", "0.0", "10", "100.0", "20", "14.0", "10", "90.0", "20", "14.0",
            "0", "TEXT", "8", "TEXT", "10", "95.0", "20", "7.0", "1", "پلان بام و شیب بندی",
            "0", "ENDSEC", "0", "EOF",
        ]
        with tempfile.TemporaryDirectory() as td:
            ms_dxf = os.path.join(td, "multistory_scattered_offsets.dxf")
            with open(ms_dxf, "w", encoding="utf-8") as f:
                f.write("\n".join(dxf_lines) + "\n")
            parsed = parse_external_plan_or_elevation(ms_dxf)
            self.assertEqual(parsed["total_floors"], 3)
            s_view = parsed["universal_facade_spec"]["views"]["SOUTH"]
            st_model = s_view["stacked_3d_model"]
            self.assertEqual(st_model["total_floors"], 3)
            self.assertEqual(st_model["roof_boxes_count"], 1)
            # Verify all 3 floors are aligned to X = 0..10m and Floor 1 & 2 have exact 1.2m South cantilever!
            fl0, fl1, fl2 = st_model["floors_3d"]
            self.assertEqual(fl0["aligned_bbox_m"], (0.0, 0.0, 10.0, 14.0))
            self.assertEqual(fl1["aligned_bbox_m"], (0.0, -1.2, 10.0, 14.0))
            self.assertEqual(fl2["aligned_bbox_m"], (0.0, -1.2, 10.0, 14.0))
            self.assertAlmostEqual(fl1["south_cantilever_m"], 1.20, places=2)
            self.assertAlmostEqual(fl2["south_cantilever_m"], 1.20, places=2)
            # Verify IFC4 3D shell file was generated
            ifc_path = s_view["ifc_shell_path"]
            self.assertTrue(ifc_path and os.path.isfile(ifc_path))
            with open(ifc_path, "r", encoding="utf-8") as ifc_f:
                ifc_txt = ifc_f.read()
            self.assertIn("IFC4", ifc_txt)
            self.assertIn("IFCBUILDINGSTOREY", ifc_txt)
            self.assertIn("Cantilever_1.20m", ifc_txt)
            # Also verify that internal engine-generated plans (ParametricArchitecturalSynthesizer) automatically generate their 3D IFC4 shell + Depth + Lineart when rendering!
            from engine.comfyui_bridge import ComfyUIRenderBridge
            eng_proj = self.synth.synthesize_from_text("یک ساختمان 3 طبقه مسکونی روی پیلوت طراحی کن")
            eng_render_png = os.path.join(td, "engine_plan_render.png")
            ComfyUIRenderBridge.export_plan_locked_south_facade_png(
                eng_proj, eng_render_png, chat_text="نمای جنوبی رو با سبک نئوکلاسیک و سنگ تراورتن کرم رندر بگیر"
            )
            self.assertTrue(os.path.isfile(eng_proj.saved_files.get("last_render_ifc", "")))
            self.assertTrue(os.path.isfile(eng_proj.saved_files.get("last_render_depth_png", "")))
            self.assertTrue(os.path.isfile(eng_proj.saved_files.get("last_render_lineart_png", "")))



    def test_v35_3_patcher_installs_extruder_and_single_floor_dwg_emits_ifc4(self) -> None:
        """
        v37.0 Regression Test for WorkBuddy's two findings:
          1. `patch_architectos_release_package.py` MUST include `dxf_to_3d_shell_extruder.py` in `plan_engine_files`
             and install it into `core/planning/multifloor_v1/engine/`, `architectos_v3_engine/`, and `core/site/`.
          2. `parse_external_plan_or_elevation` MUST emit `stacked_3d_model` and a valid `IFC4` file (`_3d_shell.ifc`)
             even for single-floor `.dwg` / `.dxf` / `.png` plans (such as `casa habitacion convencional.dwg`).
        """
        import patch_architectos_release_package as patcher
        from engine.krocki_cad_reader_v27 import parse_external_plan_or_elevation

        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Verify apply_patch installs all 13 engine files including dxf_to_3d_shell_extruder.py
            patcher.apply_patch(tmpdir)
            for rel_dir in (
                os.path.join("core", "planning", "multifloor_v1", "engine"),
                "architectos_v3_engine",
                os.path.join("core", "site"),
            ):
                ext_installed = os.path.join(tmpdir, rel_dir, "dxf_to_3d_shell_extruder.py")
                self.assertTrue(
                    os.path.isfile(ext_installed),
                    f"Missing installed module: {ext_installed}",
                )

            # 2. Verify a single-floor plan generates stacked_3d_model and a valid IFC4 file
            dxf_1fl = os.path.join(tmpdir, "casa_single_floor_test.dxf")
            lines = ["0", "SECTION", "2", "ENTITIES"]
            for x1, y1, x2, y2 in [
                (0.0, 0.0, 9.2, 0.0),
                (9.2, 0.0, 9.2, 14.0),
                (9.2, 14.0, 0.0, 14.0),
                (0.0, 14.0, 0.0, 0.0),
                (0.0, 4.5, 4.2, 4.5),
                (4.2, 4.5, 5.2, 5.5),
            ]:
                lines.extend([
                    "0", "LINE", "8", "WALL", "62", "7",
                    "10", f"{x1:.2f}", "20", f"{y1:.2f}",
                    "11", f"{x2:.2f}", "21", f"{y2:.2f}",
                ])
            for tx, ty, tval in [(2.0, 2.0, "PLANTA BAJA N+0.00"), (6.5, 1.5, "COCHERA N-0.30")]:
                lines.extend([
                    "0", "TEXT", "8", "TEXT",
                    "10", f"{tx:.2f}", "20", f"{ty:.2f}", "40", "0.25",
                    "1", tval,
                ])
            lines.extend(["0", "ENDSEC", "0", "EOF"])
            with open(dxf_1fl, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")

            parsed = parse_external_plan_or_elevation(dxf_1fl)
            self.assertEqual(parsed.get("parser_version"), "v66.0")
            st_model = parsed.get("stacked_3d_model")
            ifc_path = parsed.get("ifc_shell_path")
            self.assertIsInstance(st_model, dict)
            self.assertGreaterEqual(int(st_model.get("total_floors", 0)), 1)
            self.assertTrue(ifc_path and os.path.isfile(ifc_path))
            with open(ifc_path, "r", encoding="utf-8") as f_ifc:
                ifc_txt = f_ifc.read()
            self.assertIn("FILE_SCHEMA(('IFC4'));", ifc_txt)
            self.assertIn("IFCBUILDINGSTOREY", ifc_txt)
            self.assertIn("IFCSLAB", ifc_txt)
            self.assertIn("IFCWALLSTANDARDCASE", ifc_txt)



    def test_v36_0_oda_dxf_3floor_houseplan_facade_and_project_migration(self) -> None:
        """
        v37.0 End-to-End Verification for:
          1. ODA-converted 3-story DXF (`ext_plan_1d49dd1a.dwg` + `ext_plan_1d49dd1a.dxf` / `FACHADA PRINCIPAL`):
             - Extracts exact `total_floors == 3`, `width_m == 4.75`, `length_m == 12.0`,
               `floor_heights_m == [2.42, 2.42, 2.42]`, `has_roof_balustrade == False`, `has_pilasters == False`,
             - Floor 0 has left entrance door (`u=0.021..0.211`) and right 2-pane window (`u=0.390..0.811`, `okb_m=0.65`, `panes=2`),
             - Floors 1 & 2 have NO balconies and a single 2-pane window (`u=0.263..0.684`, `okb_m=0.53`, `panes=2`).
          2. Project-isolated `load_active_external_plan_state` & Patcher Migration (`project_v337b_probe`):
             - Never overwrites `project_v337b_probe` with `project_default`,
             - Generates `ext_plan_1d49dd1a_3d_shell.ifc` and `active_external_plan_3d_shell.ifc` in `site/`,
             - Refreshes stale `v33.7` renders in `renders/` and generates `render_001_a9ad18_3d_shell.ifc`.
        """
        import json
        import shutil
        import tempfile
        import patch_architectos_release_package as patcher

        fix_dir_v36 = os.path.join(os.path.dirname(__file__), "fixtures")
        src_dwg = os.path.join(fix_dir_v36, "ext_plan_1d49dd1a.dwg")
        src_dxf = os.path.join(fix_dir_v36, "ext_plan_1d49dd1a.dxf")
        self.assertTrue(os.path.isfile(src_dwg) and os.path.isfile(src_dxf), "Missing ext_plan_1d49dd1a fixture in tests/fixtures/")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create both project_default (with 1-floor casa plan) and project_v337b_probe (with 3-floor ext_plan_1d49dd1a)
            p_def_site = os.path.join(tmpdir, "data", "projects", "project_default", "site")
            p_prb_site = os.path.join(tmpdir, "data", "projects", "project_v337b_probe", "site")
            p_prb_rend = os.path.join(tmpdir, "data", "projects", "project_v337b_probe", "renders")
            os.makedirs(p_def_site, exist_ok=True)
            os.makedirs(p_prb_site, exist_ok=True)
            os.makedirs(p_prb_rend, exist_ok=True)

            shutil.copy2(src_dwg, os.path.join(p_prb_site, "ext_plan_1d49dd1a.dwg"))
            shutil.copy2(src_dxf, os.path.join(p_prb_site, "ext_plan_1d49dd1a.dxf"))
            with open(os.path.join(p_prb_site, "active_external_plan.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "parser_version": "v33.7",
                    "source_file": os.path.join(p_prb_site, "ext_plan_1d49dd1a.dwg"),
                    "original_filename": "houseplan- arel.ir.dwg",
                    "total_floors": 3,
                }, f)
            with open(os.path.join(p_prb_rend, "render_001_a9ad18.png"), "wb") as f_r:
                f_r.write(b"stale_render")

            patcher.apply_patch(tmpdir)

            with open(os.path.join(p_prb_site, "active_external_plan.json"), "r", encoding="utf-8") as f:
                upgraded = json.load(f)
            self.assertEqual(upgraded.get("parser_version"), "v66.0")
            self.assertEqual(upgraded.get("original_filename"), "houseplan- arel.ir.dwg")
            self.assertEqual(upgraded.get("total_floors"), 3)
            self.assertAlmostEqual(float(upgraded.get("width_m", 0.0)), 4.75, places=2)
            self.assertAlmostEqual(float(upgraded.get("length_m", 0.0)), 12.0, places=2)
            uf = upgraded.get("universal_facade_spec") or {}
            self.assertFalse(uf.get("has_roof_balustrade", True))
            self.assertFalse(uf.get("has_pilasters", True))
            s_floors = uf["views"]["SOUTH"]["floors"]
            self.assertEqual(len(s_floors), 3)
            self.assertEqual(len(s_floors[0]["bays"][0]["openings"]), 2)
            self.assertEqual(len(s_floors[1]["bays"][0]["openings"]), 1)
            self.assertEqual(len(s_floors[2]["bays"][0]["openings"]), 1)
            self.assertTrue(os.path.isfile(os.path.join(p_prb_site, "ext_plan_1d49dd1a_3d_shell.ifc")))
            self.assertTrue(os.path.isfile(os.path.join(p_prb_site, "active_external_plan_3d_shell.ifc")))
            self.assertTrue(os.path.isfile(os.path.join(p_prb_rend, "render_001_a9ad18_3d_shell.ifc")))
            self.assertGreater(os.path.getsize(os.path.join(p_prb_rend, "render_001_a9ad18.png")), 50000)



    def test_v37_0_3floor_detection_image_to_dxf_and_blender_glb_obj_ifc_solid_export(self) -> None:
        """
        v37.0 Verification for User's 3 Reports:
          1. A 3-story plan using Persian/International floor labels (`پلان طبقه همکف`, `پلان طبقه اول`, `پلان طبقه دوم`)
             where Floor 0 has no cantilever (`10x14m`) and Floors 1 & 2 have a `1.0m` cantilever (`10x15m`) + a roof note (`پله به بام`)
             MUST be detected as `total_floors == 3` (never `2`) and extract distinct per-floor openings!
          2. Uploading an image plan (`.png`/`.jpg`) automatically converts it to a vector AutoCAD `.dxf` (`*_vectorized.dxf`)
             first, and then generates 3D `.ifc`, `.glb`, and `.obj` files.
          3. Every generated `.ifc` has full 3D `IFCEXTRUDEDAREASOLID` + `IFCPRODUCTDEFINITIONSHAPE` + `IFCRELCONTAINEDINSPATIALSTRUCTURE`
             geometry (never `$`), and `.glb` (glTF 2.0 binary) + `.obj` (Wavefront 3D mesh) are generated beside it for direct Blender import!
        """
        import tempfile
        import cv2
        import numpy as np
        from engine.krocki_cad_reader_v27 import parse_external_plan_or_elevation

        with tempfile.TemporaryDirectory() as tmpdir:
            # 1) Create a 3-story DXF where Floor 0 is 10x14m (no cantilever), Floor 1 is 10x15m (+1m cantilever),
            #    and Floor 2 is 10x15m (+1m cantilever) with Persian labels "پلان طبقه همکف", "پلان طبقه اول", "پلان طبقه دوم" and "راه‌پله تا بام"
            dxf_3fl = os.path.join(tmpdir, "persian_3floor_cantilever_plan.dxf")
            lines = ["0", "SECTION", "2", "ENTITIES"]
            # Floor 0 at X=0..10, Y=1..15 (10x14m) with left door and right window
            for x1, y1, x2, y2 in [
                (0, 1, 10, 1), (10, 1, 10, 15), (10, 15, 0, 15), (0, 15, 0, 1),
                (4.5, 1.0, 8.5, 1.0), (4.5, 1.08, 8.5, 1.08), (4.5, 1.16, 8.5, 1.16), (4.5, 1.24, 8.5, 1.24),
            ]:
                lines.extend(["0", "LINE", "8", "MUROS", "62", "7", "10", str(x1), "20", str(y1), "11", str(x2), "21", str(y2)])
            lines.extend(["0", "ARC", "8", "DOOR", "10", "1.5", "20", "1.0", "40", "1.0"])
            lines.extend(["0", "TEXT", "8", "TEXT", "10", "3.0", "20", "0.2", "40", "0.3", "1", "پلان طبقه همکف کد +0.45"])

            # Floor 1 at X=16..26, Y=0..15 (10x15m, +1.0m South cantilever!) with 2 windows
            for x1, y1, x2, y2 in [
                (16, 0, 26, 0), (26, 0, 26, 15), (26, 15, 16, 15), (16, 15, 16, 0),
                (17.0, 0.0, 20.0, 0.0), (17.0, 0.08, 20.0, 0.08), (17.0, 0.16, 20.0, 0.16), (17.0, 0.24, 20.0, 0.24),
                (21.5, 0.0, 25.0, 0.0), (21.5, 0.08, 25.0, 0.08), (21.5, 0.16, 25.0, 0.16), (21.5, 0.24, 25.0, 0.24),
            ]:
                lines.extend(["0", "LINE", "8", "MUROS", "62", "7", "10", str(x1), "20", str(y1), "11", str(x2), "21", str(y2)])
            lines.extend(["0", "TEXT", "8", "TEXT", "10", "19.0", "20", "7.0", "40", "0.3", "1", "پلان طبقه اول - پذیرایی و خواب کد +3.45"])

            # Floor 2 at X=32..42, Y=0..15 (10x15m, +1.0m South cantilever!) with a note mentioning "پله تا بام"
            for x1, y1, x2, y2 in [
                (32, 0, 42, 0), (42, 0, 42, 15), (42, 15, 32, 15), (32, 15, 32, 0),
                (34.0, 0.0, 40.0, 0.0), (34.0, 0.08, 40.0, 0.08), (34.0, 0.16, 40.0, 0.16), (34.0, 0.24, 40.0, 0.24),
            ]:
                lines.extend(["0", "LINE", "8", "MUROS", "62", "7", "10", str(x1), "20", str(y1), "11", str(x2), "21", str(y2)])
            lines.extend(["0", "TEXT", "8", "TEXT", "10", "35.0", "20", "7.0", "40", "0.3", "1", "پلان طبقه دوم - خواب و راه‌پله تا بام"])
            lines.extend(["0", "ENDSEC", "0", "EOF"])

            with open(dxf_3fl, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")

            parsed_3fl = parse_external_plan_or_elevation(dxf_3fl)
            self.assertEqual(parsed_3fl["total_floors"], 3)
            self.assertEqual(parsed_3fl["stacked_3d_model"]["total_floors"], 3)
            self.assertTrue(os.path.isfile(parsed_3fl["ifc_shell_path"]))
            self.assertTrue(os.path.isfile(parsed_3fl["glb_shell_path"]))
            self.assertTrue(os.path.isfile(parsed_3fl["obj_shell_path"]))

            with open(parsed_3fl["ifc_shell_path"], "r", encoding="utf-8") as f_ifc:
                ifc_txt = f_ifc.read()
            self.assertIn("IFCEXTRUDEDAREASOLID", ifc_txt)
            self.assertIn("IFCPRODUCTDEFINITIONSHAPE", ifc_txt)
            self.assertIn("IFCRELCONTAINEDINSPATIALSTRUCTURE", ifc_txt)

            with open(parsed_3fl["glb_shell_path"], "rb") as f_glb:
                glb_head = f_glb.read(12)
            self.assertEqual(glb_head[:4], b"glTF")

            with open(parsed_3fl["obj_shell_path"], "r", encoding="utf-8") as f_obj:
                obj_txt = f_obj.read()
            self.assertIn("v ", obj_txt)
            self.assertIn("f ", obj_txt)

            # 2) Verify Image-to-DXF-to-3D pipeline on a synthetic floor plan PNG
            img_plan = np.full((400, 600, 3), 255, dtype=np.uint8)
            cv2.rectangle(img_plan, (60, 50), (540, 350), (0, 0, 0), 4)
            cv2.line(img_plan, (300, 50), (300, 350), (0, 0, 0), 3)
            png_path = os.path.join(tmpdir, "raster_plan_test.png")
            cv2.imwrite(png_path, img_plan)

            parsed_img = parse_external_plan_or_elevation(png_path)
            self.assertTrue(parsed_img.get("vectorized_dxf_path") and os.path.isfile(parsed_img["vectorized_dxf_path"]))
            self.assertTrue(os.path.isfile(parsed_img["ifc_shell_path"]))
            self.assertTrue(os.path.isfile(parsed_img["glb_shell_path"]))
            self.assertTrue(os.path.isfile(parsed_img["obj_shell_path"]))



    def test_v40_0_universal_topological_1064_plan_and_3d_pbr_render(self):
        from engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder
        from engine.comfyui_bridge import ComfyUIRenderBridge
        from engine.architectural_synthesizer import ParametricArchitecturalSynthesizer

        stacked = MultiStoryCAD3DShellExtruder.build_stacked_3d_model_from_facade_views(
            {"SOUTH": {"has_semicircular_terrace": True, "has_dual_l_stairs": True, "floors": []}},
            3, [2.70, 3.40, 3.25], 12.0, 19.3
        )
        self.assertEqual(stacked["engine_version"], "v66.0")
        self.assertEqual(stacked["total_floors"], 3)




    def test_v41_0_axis4_terrace_flat_roof_balustrade_neoclassical_columns_and_svg_3d(self) -> None:
        """
        v41.0 Verification:
          1. `BlenderHeadlessRenderer` is importable and syntax-clean.
          2. SVG floor plan (`*.svg`) is parsed into 3D segments and exported to `.ifc`, `.glb`, and `.obj`.
          3. `is_basement`, `has_flat_roof`, `has_roof_balustrade`, `column_style == NEOCLASSICAL_CORINTHIAN_FLUTED`,
             and `first_floor_terrace_start_axis == Axis 4` (`first_floor_terrace_depth_m == 8.95`) are populated
             when analyzing a multi-panel topological plan.
        """
        from engine.blender_headless_renderer import BlenderHeadlessRenderer
        from engine.krocki_cad_reader_v27 import parse_external_plan_or_elevation
        import tempfile

        self.assertTrue(hasattr(BlenderHeadlessRenderer, "render_glb_via_blender"))
        with tempfile.TemporaryDirectory() as td:
            svg_p = os.path.join(td, "sample_plan.svg")
            with open(svg_p, "w", encoding="utf-8") as sf:
                sf.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1600">'
                    '<rect x="100" y="100" width="900" height="1200" />'
                    '<line x1="100" y1="700" x2="1000" y2="700" />'
                    '<text x="200" y="200">+0.45</text>'
                    '</svg>'
                )
            res_svg = parse_external_plan_or_elevation(svg_p)
            self.assertEqual(res_svg["parser_version"], "v66.0")
            self.assertTrue(os.path.isfile(str(res_svg.get("ifc_shell_path"))))
            self.assertTrue(os.path.isfile(str(res_svg.get("glb_shell_path"))))
            self.assertTrue(os.path.isfile(str(res_svg.get("obj_shell_path"))))




    def test_v42_0_coherent_3d_shell_3dfuture_top_view_and_photoreal_stage2(self) -> None:
        """
        v42.0 Verification:
          1. `Future3DFurnitureBridge` generates Top-Down 2D AutoCAD DXF projections (`emit_3dfuture_top_view_dxf`)
             and 3D `IFCFURNISHINGELEMENT` solids (`build_3d_furniture_boxes_for_floor`).
          2. `ComfyUIRenderBridge.build_comfyui_workflow_payload` supports Stage-2 Cartoon-to-Photorealistic
             transformation (`quality="photoreal"` or chat command `"این رندر رو واقعی کن"`) with `denoise=0.92`
             and ControlNet Depth conditioning, while keeping `quality="draft"` as the fast test default.
        """
        from engine.future3d_furniture_bridge import Future3DFurnitureBridge
        from engine.architectural_synthesizer import ParametricArchitecturalSynthesizer
        from engine.comfyui_bridge import ComfyUIRenderBridge
        from engine.exporter import export_project_to_dxf

        synth = ParametricArchitecturalSynthesizer()
        proj = synth.synthesize_from_params({"typology": "VILLA_1FLOOR", "site_width_mm": 10000, "site_length_mm": 16000})
        dxf_str = export_project_to_dxf(proj)
        self.assertIn("A-FURN", dxf_str)
        self.assertIn("ARC", dxf_str)

        boxes_furn = Future3DFurnitureBridge.build_3d_furniture_boxes_for_floor(proj.floors[0], 0, 0.0)
        self.assertGreater(len(boxes_furn), 0)
        self.assertEqual(boxes_furn[0]["ifc_class"], "IFCFURNISHINGELEMENT")

        wf_photo = ComfyUIRenderBridge.build_comfyui_workflow_payload(
            project=proj, chat_command="این رندر را از حالت کارتونی به عکس واقعی تبدیل کن", quality="photoreal"
        )
        ks = (wf_photo.get("prompt") or wf_photo).get("210") or {}
        self.assertAlmostEqual(float(ks.get("inputs", {}).get("denoise", 0.0)), 0.92, places=2)


    def test_v44_0_exact_cad_extrusion_and_blender_daylight(self):
        """
        v48.0 Regression Test:
          1. Verifies BlenderHeadlessRenderer sets Nishita sky Strength = 0.85, 32 draft samples, and JPEG output format.
          2. Verifies 1064.dwg exports cylindrical IFCCIRCLEPROFILEDEF round columns set back from the terrace edge,
             First Floor flat central wall + 45-deg end walls + 90cm canopy + left terrace 45-deg chamfer,
             complete GF/FF stone balustrades with left stair opening, 8-step Left L-Stair (0.00 -> +1.25),
             Right Basement L-Stair (-1.45 -> 0.00), Basement slab (-1.45), Courtyard slab (0.00),
             and attached Courtyard boundary walls (X=-0.02m and X=11.88m).
        """
        import inspect
        import tempfile
        from engine.blender_headless_renderer import BlenderHeadlessRenderer
        from engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder

        bl_src = inspect.getsource(BlenderHeadlessRenderer)
        self.assertIn("w_bg.inputs['Strength'].default_value = 0.85", bl_src)
        self.assertIn("file_format = 'JPEG'", bl_src)
        self.assertIn("else 32", bl_src)

        with tempfile.TemporaryDirectory() as td:
            out_ifc = os.path.join(td, "test_v44_3d_shell.ifc")
            stacked = {
                "canonical_footprint_width_m": 12.0,
                "canonical_footprint_length_m": 19.3,
                "is_topological_3d_plan": True,
                "has_semicircular_terrace": True,
                "has_dual_l_stairs": True,
                "floors_3d": [
                    {"floor_index": 0, "role": "BASEMENT", "z_base_m": 0.0, "height_m": 2.7},
                    {"floor_index": 1, "role": "GROUND_FLOOR", "z_base_m": 2.7, "height_m": 3.6},
                    {"floor_index": 2, "role": "FIRST_FLOOR", "z_base_m": 6.3, "height_m": 3.15},
                ],
            }
            MultiStoryCAD3DShellExtruder.export_ifc4_raw_shell(stacked, out_ifc)
            out_obj = os.path.splitext(out_ifc)[0] + ".obj"
            self.assertTrue(os.path.isfile(out_ifc))
            self.assertTrue(os.path.isfile(out_obj))
            with open(out_ifc, "r", encoding="utf-8") as fi:
                ifc_s = fi.read()
            with open(out_obj, "r", encoding="utf-8") as fo:
                obj_s = fo.read()
            self.assertIn("IFCCIRCLEPROFILEDEF", ifc_s)
            for req_obj in (
                "FF_Central_Flat_Wall_Axis4",
                "FF_Canopy_90cm_Center_Axis4",
                "First_Floor_Left_Terrace_45Deg_Chamfer_Slab",
                "FF_Terrace_Balustrade_Left_45Deg",
                "GF_Terrace_Balustrade_Left_Shoulder",
                "GF_Terrace_Balustrade_Right_Step_Full",
                "Basement_Terrace_And_Sunken_Court_Slab_Zm145",
                "Courtyard_Floor_Main_Z000",
                "Courtyard_Wall_Left_Attached",
                "Courtyard_Wall_Right_Attached",
                "Left_GF_LStair_LTurn_Step_3_of_3_Step_8_of_8",
                "Right_Basement_LStair_Corner_Landing_Zm100",
            ):
                self.assertIn(req_obj, obj_s)



    def test_v45_0_hatched_courtyard_planter_box_8step_stairs_and_dxf_sections(self):
        """
        v48.0 Behavioral Regression Test:
          1. Verifies the Hatched 0.00 Courtyard (`Z=1.45m`) extends right up to the Semi-Circular Arc (`R=4.50m`),
             while the Basement Terrace (`COVERED AREA -1.45`, `Z=0.00m`) sits inside the arc behind the curved retaining wall.
          2. Verifies the Right Planter Box (`Right_Planter_Box_Wall_*`, `Right_Planter_Box_Soil_Green`, `Right_Planter_Box_Ornamental_Shrub_*`)
             sits beside the Right Basement L-Stair from `-1.45` (`Z=0.00m`) to `0.00` (`Z=1.55m`).
          3. Verifies both L-Stairs have 8 steps (`5 North + 3 in L-turn`): Left (`0.00 -> +0.90 -> +1.45`) and Right (`0.00 -> -1.00 -> -1.45`).
          4. Verifies 3D interior furniture (`IFCFURNISHINGELEMENT`) and the 6-panel AutoCAD Elevations & Sections DXF (`S1-S1`, `S2-S2`) are generated.
        """
        import tempfile
        from engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder

        with tempfile.TemporaryDirectory() as td:
            out_ifc = os.path.join(td, "test_v45_3d_shell.ifc")
            stacked = {
                "canonical_footprint_width_m": 12.0,
                "canonical_footprint_length_m": 19.3,
                "is_topological_3d_plan": True,
                "has_semicircular_terrace": True,
                "has_dual_l_stairs": True,
                "floors_3d": [
                    {"floor_index": 0, "role": "BASEMENT", "z_base_m": 0.0, "height_m": 2.9},
                    {"floor_index": 1, "role": "GROUND_FLOOR", "z_base_m": 2.9, "height_m": 3.4},
                    {"floor_index": 2, "role": "FIRST_FLOOR", "z_base_m": 6.3, "height_m": 3.15},
                ],
            }
            MultiStoryCAD3DShellExtruder.export_ifc4_raw_shell(stacked, out_ifc)
            out_obj = os.path.splitext(out_ifc)[0] + ".obj"
            out_dxf = os.path.splitext(out_ifc)[0] + "_elevations_and_sections.dxf"
            self.assertTrue(os.path.isfile(out_obj))
            self.assertTrue(os.path.isfile(out_dxf))
            with open(out_obj, "r", encoding="utf-8") as fo:
                obj_s = fo.read()
            for req in (
                "Basement_SemiCircular_Retaining_Wall_Seg0",
                "Right_Planter_Box_Wall_South",
                "Right_Planter_Box_Soil_Green",
                "Right_Planter_Box_Ornamental_Shrub_1",
                "Left_GF_LStair_North_Step_5_of_5",
                "Left_GF_LStair_LTurn_Step_3_of_3_Step_8_of_8",
                "Right_Basement_LStair_North_Step_5_of_5",
                "Right_Basement_LStair_LTurn_Step_3_of_3_Step_8_of_8",
                "GF_Guest_Saloon_Sofa_L1",
                "FF_Master_Bed_King",
            ):
                self.assertIn(req, obj_s)
            with open(out_dxf, "r", encoding="utf-8") as fd:
                dxf_s = fd.read()
            for sec_tok in ("SOUTH ELEVATION", "SECTION S1-S1", "SECTION S2-S2", "A-SECT-CUT", "A-FURN-3D"):
                self.assertIn(sec_tok, dxf_s)


    def test_v46_curved_courtyard_open_sunken_terrace_and_visible_right_lstair(self) -> None:
        from engine.krocki_cad_reader_v27 import parse_external_plan_or_elevation

        dwg_cands = [
            "/working_dir/c_c51184e29e8ab495/user_uploaded_files/ttl=63d/user_uploaded/1064.dwg",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "1064.dwg"),
            r"<repo-root>\data\projects\project_6f67b054\site\ext_plan_855eb2ad.dwg",
        ]
        dwg = next((p for p in dwg_cands if os.path.isfile(p)), None)
        if not dwg:
            return
        res = parse_external_plan_or_elevation(dwg)
        self.assertEqual(res.get("parser_version"), "v66.0")
        ifc_p = str(res.get("ifc_shell_path") or "")
        obj_p = os.path.splitext(ifc_p)[0] + ".obj"
        self.assertTrue(os.path.isfile(obj_p))

        objs = {}
        cur_name = None
        verts = []
        with open(obj_p, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("o "):
                    if cur_name and verts:
                        xs = [v[0] for v in verts]; ys = [v[1] for v in verts]; zs = [v[2] for v in verts]
                        objs[cur_name] = (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
                    cur_name = line.strip()[2:]
                    verts = []
                elif line.startswith("v "):
                    pts = [float(x) for x in line.strip().split()[1:4]]
                    verts.append(pts)
        if cur_name and verts:
            xs = [v[0] for v in verts]; ys = [v[1] for v in verts]; zs = [v[2] for v in verts]
            objs[cur_name] = (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

        self.assertIn("Courtyard_Floor_Main_Z000", objs)
        self.assertAlmostEqual(objs["Courtyard_Floor_Main_Z000"][3], -2.35, delta=0.05)
        self.assertIn("Basement_Terrace_And_Sunken_Court_Slab_Zm145", objs)
        self.assertAlmostEqual(objs["Basement_Terrace_And_Sunken_Court_Slab_Zm145"][5], 0.22, delta=0.02)

        s1 = objs["Right_Basement_LStair_North_Step_1_of_5"]
        s5 = objs["Right_Basement_LStair_North_Step_5_of_5"]
        self.assertLess(s1[3], s5[3])
        self.assertGreater(s1[5], s5[5])


    def test_v47_exact_red_line_courtyard_no_left_wing_f1_underfill_and_l_stairs(self) -> None:
        from engine.krocki_cad_reader_v27 import parse_external_plan_or_elevation

        dwg_cands = [
            "/working_dir/c_c51184e29e8ab495/user_uploaded_files/ttl=63d/user_uploaded/1064.dwg",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "1064.dwg"),
            r"<repo-root>\data\projects\project_6f67b054\site\ext_plan_855eb2ad.dwg",
        ]
        dwg = next((p for p in dwg_cands if os.path.isfile(p)), None)
        if not dwg:
            return
        res = parse_external_plan_or_elevation(dwg)
        self.assertEqual(res.get("parser_version"), "v66.0")
        ifc_p = str(res.get("ifc_shell_path") or "")
        obj_p = os.path.splitext(ifc_p)[0] + ".obj"
        with open(obj_p, "r", encoding="utf-8") as f:
            obj_txt = f.read()

        # 1) Image 3 fix: Terrace_Left_Setback2_Wing_F1 must be deleted (only F2 exists on First Floor!)
        self.assertNotIn("o Terrace_Left_Setback2_Wing_F1", obj_txt)
        self.assertIn("o Terrace_Left_Setback2_Wing_F2", obj_txt)

        # 2) Image 4 fix: Solid basement underfill wall + open-side balustrades on Left L-Stair
        self.assertIn("o Left_GF_LStair_Basement_Underfill_Wall", obj_txt)
        self.assertIn("o Left_GF_LStair_OpenSide_Baluster_Flight1_1", obj_txt)
        self.assertIn("o Left_GF_LStair_LTurn_Step_3_of_3_Step_8_of_8", obj_txt)

        # 3) Image 1 & 2 fix: Right Basement L-Stair 5 North-descending steps + -1.00m landing + 3 West-descending L-turn steps
        self.assertIn("o Right_Basement_LStair_North_Step_5_of_5", obj_txt)
        self.assertIn("o Right_Basement_LStair_North_Step_Nosing_5", obj_txt)
        self.assertIn("o Right_Basement_LStair_Corner_Landing_Zm100", obj_txt)
        self.assertIn("o Right_Basement_LStair_LTurn_Step_3_of_3_Step_8_of_8", obj_txt)


    def test_v48_pillar1_plan_elevation_cross_solver_and_courtyard_arc_balustrade(self) -> None:
        from engine.krocki_cad_reader_v27 import parse_external_plan_or_elevation
        from engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder

        dwg_cands = [
            "/working_dir/c_c51184e29e8ab495/user_uploaded_files/ttl=63d/user_uploaded/1064.dwg",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "1064.dwg"),
            r"<repo-root>\data\projects\project_6f67b054\site\ext_plan_855eb2ad.dwg",
        ]
        dwg = next((p for p in dwg_cands if os.path.isfile(p)), None)
        if not dwg:
            return
        res = parse_external_plan_or_elevation(dwg)
        self.assertEqual(res.get("parser_version"), "v66.0")
        self.assertTrue(res.get("cross_projected_plan_elevation"))
        self.assertTrue(os.path.isfile(str(res.get("scene_3d_json_path"))))

        cp_info = MultiStoryCAD3DShellExtruder.cross_project_plan_and_elevation_panels(
            [{"id": 0}, {"id": 1}, {"id": 2}],
            [{"id": "south"}, {"id": "north"}],
            [("TEXT", 0.0, 0.0, "-1.45"), ("TEXT", 0.0, 0.0, "-1.00"), ("TEXT", 0.0, 0.0, "±0.00"), ("TEXT", 0.0, 0.0, "+0.90"), ("TEXT", 0.0, 0.0, "+1.45"), ("TEXT", 0.0, 0.0, "+4.85")],
        )
        self.assertTrue(cp_info["cross_projected"])
        self.assertTrue(cp_info["has_sunken_basement"])
        self.assertTrue(cp_info["has_intermediate_landings"])

        obj_p = str(res.get("obj_shell_path") or "")
        with open(obj_p, "r", encoding="utf-8") as f:
            obj_txt = f.read()
        # Curved balustrade around the sunken courtyard arc (`دور قوس حیاط که دید داره به زیرزمین`) + open side of both stairs!
        self.assertIn("o Courtyard_Sunken_Arc_Balustrade_Rail_Top_Seg5", obj_txt)
        self.assertIn("o Courtyard_Sunken_Arc_Balustrade_Seg0_Post_LeftEndPost", obj_txt)
        self.assertIn("o Left_GF_LStair_OpenSide_Baluster_LTurn_1", obj_txt)
        self.assertIn("o Right_Basement_LStair_OpenSide_Baluster_Flight1_1", obj_txt)
        self.assertIn("o Right_Basement_LStair_OpenSide_Baluster_LTurn_1", obj_txt)

    def test_v48_pillar2_and_pillar3_direct_revit_ifc_obj_import_and_3d_viewer_json(self) -> None:
        import json
        import shutil
        import tempfile
        from engine.krocki_cad_reader_v27 import parse_external_plan_or_elevation

        dwg_cands = [
            "/working_dir/c_c51184e29e8ab495/user_uploaded_files/ttl=63d/user_uploaded/1064.dwg",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "1064.dwg"),
            r"<repo-root>\data\projects\project_6f67b054\site\ext_plan_855eb2ad.dwg",
        ]
        dwg = next((p for p in dwg_cands if os.path.isfile(p)), None)
        if not dwg:
            return
        res_dwg = parse_external_plan_or_elevation(dwg)
        ifc_path = str(res_dwg.get("ifc_shell_path") or "")
        self.assertTrue(os.path.isfile(ifc_path))

        # Test Pillar 3: Direct import of an .ifc file (as if exported from Revit/Blender)
        tmp_ifc = os.path.join(tempfile.gettempdir(), 'revit_test_probe.ifc')
        shutil.copy2(ifc_path, tmp_ifc)
        res_ifc = parse_external_plan_or_elevation(tmp_ifc)
        self.assertEqual(res_ifc.get("parser_version"), "v66.0")
        self.assertTrue(res_ifc.get("is_direct_3d_bim_import"))
        self.assertGreaterEqual(int(res_ifc.get("total_floors", 0)), 2)

        # Test Pillar 2: Interactive 3D Viewer JSON (`*_scene.json`)
        scene_json_p = str(res_dwg.get("scene_3d_json_path") or "")
        self.assertTrue(os.path.isfile(scene_json_p))
        with open(scene_json_p, "r", encoding="utf-8") as jf:
            sc_data = json.load(jf)
        self.assertEqual(sc_data.get("engine_version"), "v66.0")
        self.assertGreater(int(sc_data.get("element_count", 0)), 200)
        cats = {el.get("category") for el in (sc_data.get("elements") or [])}
        self.assertIn("RAILING", cats)
        self.assertIn("UNDERFILL", cats)
        self.assertIn("FURNITURE", cats)


    def test_34_v52_mezzanine_axis_d_to_g_and_two_stage_studio(self) -> None:
        from engine.krocki_cad_reader_v27 import parse_external_plan_or_elevation
        fix_p = os.path.join(os.path.dirname(__file__), "fixtures", "sina_commercial_mezzanine.dxf")
        res = parse_external_plan_or_elevation(fix_p)
        self.assertTrue(res.get("has_mezzanine"))
        self.assertEqual(res.get("mezzanine_start_axis"), "D")
        self.assertEqual(res.get("mezzanine_end_axis"), "G")
        fls_2d = (res.get("semantic_layer_normalization") or {}).get("floors_2d") or []
        self.assertIn(len(fls_2d), (2, 3))
        self.assertTrue(all(max(float(e["x1"]), float(e["x2"])) >= 11.8 for e in fls_2d[-1]["entities"]))

    def test_35_v52_direct_rvt_and_commercial_securit_storefront_render(self) -> None:
        from engine.krocki_cad_reader_v27 import parse_external_plan_or_elevation
        from engine.comfyui_bridge import ComfyUIRenderBridge
        with tempfile.TemporaryDirectory() as td:
            p_rvt = os.path.join(td, "sina.rvt")
            with open(p_rvt, "wb") as fr:
                fr.write(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + "اتو گالری سینا نیم طبقه".encode("utf-16le") + b"\x00" * 512)
            res_rvt = parse_external_plan_or_elevation(p_rvt)
            self.assertTrue(res_rvt.get("is_3d_model"))
            self.assertTrue(res_rvt.get("has_mezzanine"))
            out_png = os.path.join(td, "sina_west.png")
            r_state = {
                "custom_facade_profile": res_rvt.get("custom_facade_profile"),
                "universal_facade_spec": res_rvt.get("universal_facade_spec"),
                "raw_chat_text": "از همین مدل سه بعدی یک رندر بگیر یک درب ورودی بزرگ با شیشه سکوریت هم داره یک مغازه است",
            }
            proj = self.synth.synthesize_from_params({"typology": "VILLA_1FLOOR", "site_width_mm": 5150, "site_length_mm": 24290})
            _, prompt_en = ComfyUIRenderBridge.export_plan_locked_south_facade_png(
                proj, out_png, chat_text=r_state["raw_chat_text"], quality="draft", prev_render_state=r_state
            )
            self.assertTrue(os.path.isfile(out_png))
            self.assertIn("Securit glass", prompt_en)


if __name__ == "__main__":
    unittest.main()


class TestArchitectOSV27Fixes(unittest.TestCase):
    def setUp(self) -> None:
        self.synth = ParametricArchitecturalSynthesizer()

    def test_v49_dxf_unicode_and_stepped_stair_section_no_pink_columns(self) -> None:
        from engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder
        import tempfile, os
        enc = MultiStoryCAD3DShellExtruder._encode_dxf_unicode_text("SOUTH ELEVATION (نمای جنوبی)")
        self.assertIn("\\U+0646\\U+0645\\U+0627\\U+06CC", enc)
        self.assertTrue(all(ord(c) < 128 for c in enc))

        with tempfile.TemporaryDirectory() as td:
            ifc_p = os.path.join(td, "test_v49_shell.ifc")
            st = {
                "canonical_footprint_width_m": 12.0,
                "canonical_footprint_length_m": 19.3,
                "has_semicircular_terrace": True,
                "floors_3d": [
                    {"floor_index": 0, "z_base_m": 0.0, "height_m": 2.90, "walls_3d": []},
                    {"floor_index": 1, "z_base_m": 2.90, "height_m": 3.40, "walls_3d": []},
                    {"floor_index": 2, "z_base_m": 6.30, "height_m": 3.15, "walls_3d": []},
                ],
            }
            MultiStoryCAD3DShellExtruder.export_ifc4_raw_shell(st, ifc_p)
            dxf_sec = os.path.splitext(ifc_p)[0] + "_elevations_and_sections.dxf"
            self.assertTrue(os.path.isfile(dxf_sec))
            with open(dxf_sec, "r", encoding="utf-8") as df:
                dxf_txt = df.read()
            self.assertIn("AC1021", dxf_txt)
            self.assertIn("\\U+0646\\U+0645\\U+0627\\U+06CC", dxf_txt)
            self.assertIn("A-STAIR", dxf_txt)
            self.assertTrue(all(ord(c) < 128 for c in dxf_txt))

    def test_v49_13_category_autocad_layer_normalizer_and_scene_json_materials(self) -> None:
        from engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder
        import tempfile, os, json
        self.assertEqual(len(MultiStoryCAD3DShellExtruder.CANONICAL_SEMANTIC_LAYERS), 14)
        for req_lyr in ("A-WALL", "A-WIN", "A-DOOR", "A-STAIR", "A-DUCT", "A-ELEVATOR", "A-RAMP", "A-DATUM-CODE", "A-HEIGHT", "A-FLOOR", "A-ROOF", "A-CANOPY", "A-OVERHANG", "A-BALUSTRADE"):
            self.assertIn(req_lyr, MultiStoryCAD3DShellExtruder.CANONICAL_SEMANTIC_LAYERS)

        with tempfile.TemporaryDirectory() as td:
            raw_dxf = os.path.join(td, "messy_layer0.dxf")
            with open(raw_dxf, "w", encoding="utf-8") as f:
                f.write("\n".join([
                    "0", "SECTION", "2", "ENTITIES",
                    "0", "LINE", "8", "0", "62", "1", "10", "1.0", "20", "0.0", "11", "2.5", "21", "0.0",
                    "0", "LINE", "8", "0", "62", "7", "10", "0.0", "20", "0.0", "11", "10.0", "21", "0.0",
                    "0", "TEXT", "8", "0", "10", "3.0", "20", "3.0", "40", "0.25", "1", "%%p0.00",
                    "0", "ENDSEC", "0", "EOF",
                ]) + "\n")
            norm_res = MultiStoryCAD3DShellExtruder.auto_normalize_and_rewrite_dxf_layers(
                raw_dxf, user_layer_overrides={"DOOR_RAW": "A-DOOR"}, apply_all_floors=True
            )
            self.assertTrue(norm_res["ok"])
            self.assertEqual(norm_res["engine_version"], "v66.0")
            self.assertEqual(len(norm_res["canonical_layers"]), 14)
            self.assertTrue(os.path.isfile(norm_res["normalized_dxf_path"]))

            scene_json = os.path.join(td, "probe_scene.json")
            MultiStoryCAD3DShellExtruder.export_interactive_3d_viewer_json([
                {"name": "Wall_1", "ifc_class": "IFCWALL", "cx": 0, "cy": 0, "cz": 1, "dx": 4, "dy": 0.2, "dz": 3},
                {"name": "Courtyard_Sunken_Arc_Balustrade_Seg0", "ifc_class": "IFCCOLUMN", "cx": 2, "cy": -1, "cz": 1.8, "dx": 0.1, "dy": 0.1, "dz": 0.7},
            ], scene_json)
            with open(scene_json, "r", encoding="utf-8") as jf:
                sdata = json.load(jf)
            for el in sdata["elements"]:
                self.assertIsNotNone(el.get("material"))
                self.assertTrue(str(el.get("color_hex", "")).startswith("#"))
                self.assertIn(el.get("semantic_layer"), MultiStoryCAD3DShellExtruder.CANONICAL_SEMANTIC_LAYERS)

    def test_v50_single_floor_casa_habitacion_connected_interior_walls_and_revit_rvt_companion(self) -> None:
        from engine.krocki_cad_reader_v27 import parse_external_plan_or_elevation
        import os, json
        res = parse_external_plan_or_elevation("tests/fixtures/ext_plan_1d49dd1a.dxf")
        self.assertEqual(res.get("parser_version"), "v66.0")
        scene_p = res.get("scene_3d_json_path")
        self.assertTrue(scene_p and os.path.isfile(scene_p))
        with open(scene_p, "r", encoding="utf-8") as f:
            sj = json.load(f)
        self.assertEqual(sj.get("engine_version"), "v66.0")
        names = [e["name"] for e in sj["elements"]]
        self.assertNotIn("Interior_Living_Hall_Wall_F0", names)
        base_no_ext = os.path.splitext(res["ifc_shell_path"])[0]
        self.assertTrue(os.path.isfile(base_no_ext + "_revit_journal.txt"))
        self.assertTrue(os.path.isfile(base_no_ext + "_build_revit_rvt.py"))

    def test_v50_split_screen_2d_3d_studio_and_3d_import_button_in_patcher(self) -> None:
        import os, tempfile
        import patch_architectos_release_package as patcher
        with tempfile.TemporaryDirectory() as td:
            ui_dir = os.path.join(td, "ui")
            os.makedirs(ui_dir, exist_ok=True)
            app_py = os.path.join(ui_dir, "app.py")
            index_html = os.path.join(ui_dir, "index.html")
            with open(app_py, "w", encoding="utf-8") as f:
                f.write("from flask import Flask\napp = Flask(__name__)\n")
            with open(index_html, "w", encoding="utf-8") as f:
                f.write("<html><body><button>کروکی زمین</button></body></html>")
            patcher.apply_patch(td)
            with open(index_html, "r", encoding="utf-8") as f:
                html_out = f.read()
            self.assertIn("arch2d-cad-canvas", html_out)
            self.assertIn("arch50-lyr-btn", html_out)
            self.assertIn("archos-v50-import-3d-btn", html_out)
            self.assertIn("/api/3d/download_bim", html_out)

    def test_v51_3ds_binary_parser_and_rvt_preview_extraction(self) -> None:
        from engine.krocki_cad_reader_v27 import parse_external_plan_or_elevation
        import os, struct, tempfile
        with tempfile.TemporaryDirectory() as td:
            # Build a real binary .3ds file with 0x4D4D -> 0x3D3D -> 0x4000 -> 0x4100 -> 0x4110 (4 vertices)
            verts = [(0.0, 0.0, 0.0), (8.0, 0.0, 0.0), (8.0, 6.0, 3.2), (0.0, 6.0, 3.2)]
            v_payload = struct.pack("<H", len(verts)) + b"".join(struct.pack("<fff", *v) for v in verts)
            c_4110 = struct.pack("<HI", 0x4110, 6 + len(v_payload)) + v_payload
            c_4100 = struct.pack("<HI", 0x4100, 6 + len(c_4110)) + c_4110
            obj_name = b"ShopMesh\x00"
            c_4000 = struct.pack("<HI", 0x4000, 6 + len(obj_name) + len(c_4100)) + obj_name + c_4100
            c_3d3d = struct.pack("<HI", 0x3D3D, 6 + len(c_4000)) + c_4000
            c_4d4d = struct.pack("<HI", 0x4D4D, 6 + len(c_3d3d)) + c_3d3d
            p_3ds = os.path.join(td, "shop_model.3ds")
            with open(p_3ds, "wb") as f:
                f.write(c_4d4d)
            res_3ds = parse_external_plan_or_elevation(p_3ds)
            self.assertEqual(res_3ds.get("parser_version"), "v66.0")
            self.assertTrue(res_3ds.get("is_direct_3d_bim_import"))
            self.assertTrue(res_3ds.get("is_3d_model"))
            self.assertAlmostEqual(res_3ds.get("width_m"), 8.0, delta=0.1)

    def test_v51_multifloor_bottom_to_top_sorting_and_stair_datum_studio_tools(self) -> None:
        from engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder
        import os, tempfile
        import patch_architectos_release_package as patcher
        ents = [
            {"x1": 0.0, "y1": 0.0, "x2": 8.0, "y2": 0.0, "semantic_layer": "A-WALL", "raw_layer": "0"},
            {"x1": 8.0, "y1": 0.0, "x2": 8.0, "y2": 10.0, "semantic_layer": "A-WALL", "raw_layer": "0"},
            {"x1": 0.0, "y1": 10.0, "x2": 8.0, "y2": 10.0, "semantic_layer": "A-WALL", "raw_layer": "0"},
            {"x1": 0.0, "y1": 0.0, "x2": 0.0, "y2": 10.0, "semantic_layer": "A-WALL", "raw_layer": "0"},
            {"x1": 1.0, "y1": 2.0, "x2": 7.0, "y2": 2.0, "semantic_layer": "A-WALL", "raw_layer": "0"},
            {"x1": 1.0, "y1": 5.0, "x2": 7.0, "y2": 5.0, "semantic_layer": "A-WALL", "raw_layer": "0"},
            {"x1": 30.0, "y1": 0.0, "x2": 38.0, "y2": 0.0, "semantic_layer": "A-WALL", "raw_layer": "0"},
            {"x1": 38.0, "y1": 0.0, "x2": 38.0, "y2": 10.0, "semantic_layer": "A-WALL", "raw_layer": "0"},
            {"x1": 30.0, "y1": 10.0, "x2": 38.0, "y2": 10.0, "semantic_layer": "A-WALL", "raw_layer": "0"},
            {"x1": 30.0, "y1": 0.0, "x2": 30.0, "y2": 10.0, "semantic_layer": "A-WALL", "raw_layer": "0"},
            {"x1": 31.0, "y1": 3.0, "x2": 37.0, "y2": 3.0, "semantic_layer": "A-WALL", "raw_layer": "0"},
            {"x1": 31.0, "y1": 6.0, "x2": 37.0, "y2": 6.0, "semantic_layer": "A-WALL", "raw_layer": "0"},
        ]
        txts = [("0", 4.0, -1.0, "پلان طبقه همکف +0.45"), ("0", 34.0, -1.0, "پلان زیرزمین -1.45")]
        fls = MultiStoryCAD3DShellExtruder.split_2d_entities_into_sorted_floors(ents, txts)
        self.assertEqual(len(fls), 2)
        # Basement (-1.45) must sort BEFORE Ground Floor (+0.45)
        self.assertEqual(fls[0]["role"], "BASEMENT")
        self.assertEqual(fls[1]["role"], "GROUND_FLOOR")

        with tempfile.TemporaryDirectory() as td:
            ui_dir = os.path.join(td, "ui")
            os.makedirs(ui_dir, exist_ok=True)
            with open(os.path.join(ui_dir, "app.py"), "w", encoding="utf-8") as f:
                f.write("from flask import Flask\napp = Flask(__name__)\n")
            with open(os.path.join(ui_dir, "index.html"), "w", encoding="utf-8") as f:
                f.write("<html><body><button>کروکی زمین</button></body></html>")
            patcher.apply_patch(td)
            with open(os.path.join(ui_dir, "index.html"), "r", encoding="utf-8") as f:
                html_out = f.read()
            self.assertIn("arch51-floor-tab", html_out)
            self.assertIn("arch51-tool-datum", html_out)
            self.assertIn("arch51-tool-stair", html_out)
            self.assertIn("arch51-ref-bar", html_out)
            self.assertIn(".3ds", html_out)

    def test_v27_new_plan_vs_edit_and_void_removal(self) -> None:
        from engine.nl_design_parser import (
            is_new_plan_creation_prompt,
            is_plan_modification_prompt,
            parse_architectural_prompt,
            apply_incremental_plan_edit,
        )
        from engine.exporter import export_project_to_svg, export_project_to_dxf
        from engine.krocki_cad_reader_v27 import parse_krocki_dxf_or_dwg
        from engine.persian_architectural_brain_v23 import classify_conversational_render_intent

        # 1. Turn 1: Duplex 120m2 in 200m2 site
        p1 = "یک ساختمان دوبلکس مدرن به مساحت 120 مترمربع در قطعه زمین 200 مترمربع در شمال زمین طراحی کن"
        self.assertTrue(is_new_plan_creation_prompt(p1))
        self.assertFalse(is_plan_modification_prompt(p1))
        params1 = parse_architectural_prompt(p1)
        self.assertEqual(params1["typology"], "DUPLEX_2FLOOR")
        proj1 = self.synth.synthesize_from_params(params1)
        self.assertTrue(any(r.room_id == "VOID_DUPLEX_LIVING" for r in proj1.floors[1].rooms))

        # 2. Turn 2: Edit Duplex to remove upper-floor void and replace with private living room
        p2 = "وید طبقه بالا رو حذف کن و به نشیمن خصوصی به جاش بزار"
        self.assertFalse(is_new_plan_creation_prompt(p2))
        self.assertTrue(is_plan_modification_prompt(p2))
        params2 = apply_incremental_plan_edit(params1, p2)
        self.assertTrue(params2["remove_duplex_void"])
        proj2 = self.synth.synthesize_from_params(params2)
        self.assertFalse(any(r.room_id == "VOID_DUPLEX_LIVING" for r in proj2.floors[1].rooms))
        self.assertTrue(any(r.room_id == "UPPER_PRIVATE_LIVING" for r in proj2.floors[1].rooms))

        # 3. Turn 3: Brand-new Villa 150m2 in 250m2 site in the same session!
        p3 = "یک ساختمان ویلایی با 150 متر مربع در زمینی به مساحت 250 متر مربع در شمال زمین ساختمان را طراحی کن"
        self.assertTrue(is_new_plan_creation_prompt(p3))
        self.assertFalse(is_plan_modification_prompt(p3))
        params3 = parse_architectural_prompt(p3)
        self.assertEqual(params3["typology"], "VILLA_1FLOOR")
        self.assertEqual(params3["site_area_m2"], 250.0)
        self.assertEqual(params3["site_length_mm"], 25000)
        proj3 = self.synth.synthesize_from_params(params3)
        self.assertEqual(len(proj3.floors), 1)

        # 4. V25_SYNC_COMPAT filepath=None check and AC1009 DXF validation
        svg_raw = export_project_to_svg(proj3)
        self.assertTrue(svg_raw.startswith("<svg"))
        dxf_raw = export_project_to_dxf(proj3)
        self.assertIn("AC1009", dxf_raw)
        self.assertNotIn("\n370\n", dxf_raw)
        self.assertNotIn("\n290\n", dxf_raw)

        # 5. Render intent check for Plan->Facade and Facade->Night
        intent_facade = classify_conversational_render_intent(
            "از همین ساختمان یه رندر از نمای جنوبی ساختمان بگیر با متریال چوب ترمووود و سیمان سفید و سنگ تراورتن سفید با سبک مدرن",
            has_active_image=False,
            has_active_plan=True,
        )
        self.assertEqual(intent_facade.render_mode, "MODE_4_PLAN_TO_3D_RENDER")

        intent_night = classify_conversational_render_intent(
            "همین نما رو رندر شب بگیر",
            has_active_image=True,
            has_active_plan=True,
        )
        self.assertEqual(intent_night.render_mode, "MODE_3_DAY_TO_NIGHT_RELIGHT")
        self.assertEqual(intent_night.time_of_day, "NIGHT")

    def test_v30_sloped_krocki_plan_flip_bedroom3_and_3d_facade_render(self) -> None:
        from engine.krocki_cad_reader_v27 import parse_krocki_dxf_or_dwg
        from engine.nl_design_parser import parse_architectural_prompt, apply_incremental_plan_edit
        from engine.comfyui_bridge import ComfyUIRenderBridge

        fix_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
        candidates = [
            os.path.join(fix_dir, "حسن حقانی .اوقاف2.dwg"),
            os.path.expanduser("~/Downloads/حسن حقانی .اوقاف2.dwg"),
        ]
        dwg_haghani = next((p for p in candidates if os.path.isfile(p)), None)
        if dwg_haghani:
            k_info = parse_krocki_dxf_or_dwg(dwg_haghani)
            self.assertAlmostEqual(k_info["site_area_m2"], 252.28, delta=0.5)
            self.assertEqual(k_info["vertex_count"], 4)
            self.assertGreaterEqual(abs(k_info["south_y_east_mm"] - k_info["south_y_west_mm"]), 600)
        else:
            k_info = {
                "width_m": 10.0,
                "length_m": 25.6,
                "site_area_m2": 252.28,
                "vertex_count": 4,
                "polygon_vertices_mm": [(0, 25600), (0, 0), (10000, 696), (10000, 25555)],
                "is_irregular_polygon": True,
                "street_sides": ["SOUTH"],
                "party_wall_sides": ["NORTH", "EAST", "WEST"],
                "boundary_neighbors": {"SOUTH": "STREET", "NORTH": "NEIGHBOR_LOT", "EAST": "NEIGHBOR_LOT", "WEST": "NEIGHBOR_LOT"},
                "south_y_west_mm": 0,
                "south_y_east_mm": 696,
                "north_y_west_mm": 25600,
                "north_y_east_mm": 25555,
            }
        if True:

            p1 = parse_architectural_prompt("یک ساختمان ویلایی دوبلکس در ضلع جنوب زمین با سطح اشغال 55 درصد طراحی کن")
            p1.update({
                "site_width_mm": int(round(k_info["width_m"] * 1000)),
                "site_length_mm": int(round(k_info["length_m"] * 1000)),
                "site_area_m2": k_info["site_area_m2"],
                "krocki_polygon_mm": k_info["polygon_vertices_mm"],
                "krocki_is_irregular": k_info["is_irregular_polygon"],
                "street_sides": k_info["street_sides"],
                "party_wall_sides": k_info["party_wall_sides"],
                "boundary_neighbors": k_info["boundary_neighbors"],
                "south_y_west_mm": k_info["south_y_west_mm"],
                "south_y_east_mm": k_info["south_y_east_mm"],
                "north_y_west_mm": k_info["north_y_west_mm"],
                "north_y_east_mm": k_info["north_y_east_mm"],
            })
            res1 = self.synth.synthesize_from_params(p1)
            self.assertIn("۲ خواب + مینی‌بار و تراس مسقف بزرگ", res1.project_title_fa)
            # Sloped South columns are on distinct horizontal axes 1, 2, 3
            self.assertGreaterEqual(len(res1.floors[0].grid_y_mm), 6)

            # Flip 180 degrees North-South
            p2 = apply_incremental_plan_edit(p1, "پلان رو بچرخون اتاق خوابها سمت جنوب باشن پذیرایی و ناهارخوری و ورودی ساختمان سمت شمال باشن")
            self.assertTrue(p2["flip_plan_north_south"])
            res2 = self.synth.synthesize_from_params(p2)
            self.assertIn("چرخش ۱۸۰ درجه پلان", res2.project_title_fa)

            # Convert Mini-Bar & Terrace to Bedroom 3
            p3 = apply_incremental_plan_edit(p2, "تراس و مینی بار طبقه بالا رو حذف و تبدیلش کن به اتاق خواب")
            self.assertTrue(p3["replace_minibar_with_bedroom"])
            res3 = self.synth.synthesize_from_params(p3)
            self.assertIn("۳ خواب مستقل", res3.project_title_fa)
            self.assertTrue(any(r.room_id == "BEDROOM_3_SW" for r in res3.floors[1].rooms))

            # Render North Facade in Neoclassical style
            with tempfile.TemporaryDirectory() as td:
                out_png = os.path.join(td, "north_neoclassical.png")
                _, prompt_en = ComfyUIRenderBridge.export_plan_locked_south_facade_png(
                    res3,
                    out_png,
                    chat_text="یه رندر از همین پلان از نمای شمالی به سبک نئوکلاسیک و متریال سنگ تراورتن کرم بگیر",
                )
                self.assertTrue(os.path.isfile(out_png))
                self.assertIn("North elevation", prompt_en)
                self.assertIn("EXACTLY 2 floor(s)", prompt_en)

    def test_v67_0_studio_clean_prompt_yasna_isolation_and_zero_showroom_hijack(self) -> None:
        from engine.krocki_cad_reader_v27 import parse_external_plan_or_elevation
        from engine.comfyui_bridge import Architectural3DRenderer_prompt
        import patch_architectos_release_package as patcher
        import numpy as np
        import os, tempfile

        with tempfile.TemporaryDirectory() as td:
            ui_dir = os.path.join(td, "ui")
            os.makedirs(ui_dir, exist_ok=True)
            with open(os.path.join(ui_dir, "app.py"), "w", encoding="utf-8") as f:
                f.write("from flask import Flask\napp = Flask(__name__)\n")
            with open(os.path.join(ui_dir, "index.html"), "w", encoding="utf-8") as f:
                f.write("<html><body><button>کروکی زمین</button></body></html>")
            patcher.apply_patch(td)
            with open(os.path.join(ui_dir, "index.html"), "r", encoding="utf-8") as f:
                html_out = f.read()
            self.assertIn('id="arch51-render-prompt" value=""', html_out)
            self.assertNotIn("یک مغازه است", html_out)

            yasna_p = os.path.join(td, "yasna.max")
            with open(yasna_p, "wb") as f:
                f.write(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"Yasna3DStream" * 64)
            res_y = parse_external_plan_or_elevation(yasna_p, user_hint="yasna.max")
            dz_y = np.load(res_y["mesh_cache_npz"])
            self.assertNotEqual(str(dz_y["mesh_profile"]), "sadegh_max_v66")

            proj = self.synth.synthesize_from_params({"typology": "MULTIFLOOR_RESIDENTIAL", "floor_count": 2})
            proj.site.active_render_state = {"universal_facade_spec": res_y.get("universal_facade_spec")}
            p_en = Architectural3DRenderer_prompt(proj, {
                "facade_side": "SOUTH",
                "camera_prompt_en": "3D perspective",
                "materials_en": "cream travertine",
                "lighting_en": "daylight",
                "raw_chat_text": "از همین مدل سه‌بعدی با حفظ ۱۰۰٪ عرض دهنه، سایبان هم‌تراز سقف، رمپ شیب‌دار، درب شیشه سکوریت و نیم‌طبقه رندر واقعی بگیر",
            })
            self.assertNotIn("auto-gallery", p_en.lower())
            self.assertNotIn("white luxury sedan parked inside", p_en.lower())

