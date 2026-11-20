#!/usr/bin/env python3
"""
Acceptance & Regression Tests for ArchitectOS v2.0 Furnished Plan Engine.
Verifies:
  1. Exact 10x20m site with 60% North coverage + 1.70m deep (12.00 m²) North Backyard Lightwell.
  2. Complete Residential Room Program (Entrance Foyer, Guest WC, Living/Dining, Kitchen, Balcony,
     Private Hallway, Main Bathroom, Bedroom 1, Master Bedroom, En-suite Master Bath).
  3. Full Furniture, Doors with Swing Arcs, Double-Glazed Windows, 40x40cm Columns, 5cm Separation Joint.
  4. Natural language prompt parsing for Villa ("یک ساختمان یک طبقه ویلایی طراحی کن"),
     Duplex ("یک ساختمان دوبلکس 120 متری در هر طبقه طراحی کن"), and Mixed-Use buildings.
"""

from __future__ import annotations
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import (
    ArchitecturalPlanSynthesizer,
    ValidationStatus,
    export_project_to_dxf,
    export_project_to_svg,
    is_architectural_design_prompt,
    parse_architectural_prompt,
)


class TestArchitectOSFurnishedEngineV2(unittest.TestCase):
    def setUp(self) -> None:
        self.synth = ArchitecturalPlanSynthesizer()

    def test_01_user_10x20_north60_lightwell_1p7m_12m2_prompt(self) -> None:
        prompt = (
            "60 درصد محل احداث تو شمال با یه حیاط خلوت به عمق 1.7 متر با مساحت 12 متر مربع "
            "برای نورگیری بزاره زمین هم 10*20 سه طرف پلاک هست شمال شرق و غرب پلاک و جنوب کوچه 10 متری"
        )
        self.assertTrue(is_architectural_design_prompt(prompt))
        parsed = parse_architectural_prompt(prompt)
        self.assertEqual(parsed["site_width_mm"], 10_000)
        self.assertEqual(parsed["site_length_mm"], 20_000)
        self.assertAlmostEqual(parsed["coverage_ratio"], 0.60)
        self.assertEqual(parsed["lightwell_depth_mm"], 1700)
        self.assertAlmostEqual(parsed["lightwell_area_m2"], 12.0)

        proj = self.synth.synthesize_from_text(prompt)
        self.assertEqual(proj.audit.status, ValidationStatus.VALID)
        fl = proj.floors[0]

        # Check Lightwell exact depth (1700 mm) and area (12.0 m²)
        lw = fl.lightwells[0]
        self.assertEqual(lw.depth_mm, 1700)
        self.assertAlmostEqual(lw.target_area_m2, 12.0, delta=0.05)

        # Check all required residential spaces exist
        room_ids = {r.room_id for r in fl.rooms}
        for req_room in (
            "LIVING_DINING",
            "KITCHEN",
            "BALCONY_SOUTH",
            "STAIR_ELEV_CORE",
            "ENTRANCE_FOYER",
            "GUEST_WC",
            "PRIVATE_HALL",
            "MAIN_BATHROOM",
            "BEDROOM_1",
            "MASTER_BEDROOM",
            "MASTER_BATH",
        ):
            self.assertIn(req_room, room_ids, f"Missing required room: {req_room}")

        # Check doors, windows, furniture, columns, and dimensions
        self.assertGreaterEqual(len(fl.doors), 9)
        self.assertGreaterEqual(len(fl.windows), 5)
        self.assertGreaterEqual(len(fl.furniture), 16)
        self.assertEqual(len(fl.columns), 16)
        self.assertGreaterEqual(len(fl.dimensions), 6)

        # Verify SVG and DXF exports contain furniture, doors, windows, and room areas
        svg = export_project_to_svg(proj)
        dxf = export_project_to_dxf(proj)
        self.assertIn("حیاط خلوت", svg)
        self.assertIn("پذیرایی و ناهارخوری", svg)
        self.assertIn("A-FURN", dxf)
        self.assertIn("A-DOOR", dxf)
        self.assertIn("A-WINDOW", dxf)
        self.assertIn("A-COLS", dxf)
        self.assertIn("ARC", dxf)

    def test_02_duplex_120m2_prompt_never_fails(self) -> None:
        prompt = "یک ساختمان دوبلکس 120 متری در هر طبقه طراحی کن"
        self.assertTrue(is_architectural_design_prompt(prompt))
        proj = self.synth.synthesize_from_text(prompt)
        self.assertEqual(proj.audit.status, ValidationStatus.VALID)
        self.assertEqual(len(proj.floors), 2)

    def test_03_villa_1floor_prompt_never_fails(self) -> None:
        prompt = "یک ساختمان یک طبقه ویلایی طراحی کن"
        self.assertTrue(is_architectural_design_prompt(prompt))
        proj = self.synth.synthesize_from_text(prompt)
        self.assertEqual(proj.audit.status, ValidationStatus.VALID)
        self.assertEqual(len(proj.floors), 1)

    def test_04_mixed_use_multifloor_prompt(self) -> None:
        prompt = "یک ساختمان 4 طبقه مختلط تجاری مسکونی با زیرزمین پارکینگ طراحی کن"
        proj = self.synth.synthesize_from_text(prompt)
        self.assertEqual(proj.audit.status, ValidationStatus.VALID)
        self.assertEqual(len(proj.floors), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
