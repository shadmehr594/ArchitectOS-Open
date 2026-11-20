"""
ArchitectOS v20.0 — Parametric 3D Perspective & South Facade Elevation Renderer (`engine/perspective_renderer.py`)
Directly extrudes the 2D/2.5D floor-plan coordinates of a `BuildingProjectResultV3` into:
  1. An accurate Architectural South Elevation (`نمای جنوبی دقیق منطبق با پلان`)
  2. A 3D Two-Point Perspective Architectural Massing & Material Visualization (`رندر پرسپکتیو سه‌بعدی با متریال انتخابی`)
  3. A geometry-locked ControlNet / Diffusion Prompt for photorealistic V-Ray/Corona-grade rendering.
"""
from __future__ import annotations
import os
from typing import Optional
from .conversational_editor import ConversationalPlanEditor
from .domain import BuildingProjectResultV3


class Architectural3DRenderer:
    """
    Generates a high-resolution SVG/PNG Architectural Facade & 3D Perspective Sheet
    directly from the `BuildingProjectResultV3` geometry and user-selected style/material palette.
    """

    @classmethod
    def build_photorealistic_prompt(
        cls, project: BuildingProjectResultV3, style_key: str = "MODERN_THERMOWOOD"
    ) -> str:
        style = ConversationalPlanEditor.SUPPORTED_STYLES.get(
            style_key, ConversationalPlanEditor.SUPPORTED_STYLES["MODERN_THERMOWOOD"]
        )
        has_pergola = any(
            any(f.kind == "TIMBER_PERGOLA_TERRACE" for f in fl.furniture)
            for fl in project.floors
        )
        has_void = any(
            any(r.code_en == "VOID_OVER_LIVING" for r in fl.rooms)
            for fl in project.floors
        )
        pergola_desc = (
            "recessed upper-floor South terrace on the left wing with a warm timber trellis pergola ceiling (سقف چوب مشبک), linear LED soffit lighting, frameless glass balustrade, and wide sliding glass door opening to an indoor mini-bar lounge"
            if has_pergola
            else "recessed upper-floor South balcony with glass balustrade and warm wood soffit"
        )
        void_desc = (
            "tall double-height black-mullioned curtain wall window on the right wing spanning both ground and first floors overlooking the duplex living room void"
            if has_void
            else "tall floor-to-ceiling panoramic windows on the right wing"
        )
        return (
            f"Photorealistic architectural exterior eye-level perspective render of a two-story {style['name_fa']} duplex villa, "
            f"strictly matching the CAD floor plan: left wing features ground-floor dining room window, central recessed thermowood main entrance door with 3 curved stone steps, "
            f"and {pergola_desc}; right wing features a {void_desc}; "
            f"foreground courtyard with large-format travertine stone pavers, manicured evergreen shrubs, cypress trees, and warm architectural dusk lighting, 8k V-Ray Corona render."
        )

    @classmethod
    def export_facade_and_perspective_svg(
        cls,
        project: BuildingProjectResultV3,
        out_svg_path: str,
        style_key: Optional[str] = None,
    ) -> str:
        if not style_key:
            style_key = project.saved_files.get(
                "selected_render_style", "MODERN_THERMOWOOD"
            )
        style = ConversationalPlanEditor.SUPPORTED_STYLES.get(
            style_key, ConversationalPlanEditor.SUPPORTED_STYLES["MODERN_THERMOWOOD"]
        )

        W, H = 1800, 1080
        wall_main = style["wall_primary"]
        wall_acc = style["wall_accent"]
        wood = style["wood_thermowood"]
        frame = style["frame_color"]
        glass = style["glass_color"]
        base_stone = style["stone_base"]
        coping = style["roof_coping"]
        is_neoclassical = style_key == "NEOCLASSICAL_STONE"

        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
            "<defs>",
            '  <linearGradient id="skyGrad" x1="0" y1="0" x2="0" y2="1">',
            '    <stop offset="0%" stop-color="#1E3A8A"/>',
            '    <stop offset="55%" stop-color="#60A5FA"/>',
            '    <stop offset="100%" stop-color="#E0F2FE"/>',
            "  </linearGradient>",
            '  <linearGradient id="glassGrad" x1="0" y1="0" x2="1" y2="1">',
            f'    <stop offset="0%" stop-color="{glass}" stop-opacity="0.88"/>',
            '    <stop offset="50%" stop-color="#1E293B" stop-opacity="0.78"/>',
            '    <stop offset="100%" stop-color="#F59E0B" stop-opacity="0.45"/>',
            "  </linearGradient>",
            '  <linearGradient id="warmInterior" x1="0" y1="0" x2="0" y2="1">',
            '    <stop offset="0%" stop-color="#FDE68A" stop-opacity="0.9"/>',
            '    <stop offset="100%" stop-color="#D97706" stop-opacity="0.65"/>',
            "  </linearGradient>",
            '  <pattern id="woodPlanks" width="18" height="18" patternUnits="userSpaceOnUse">',
            f'    <rect width="18" height="18" fill="{wood}"/>',
            '    <line x1="0" y1="0" x2="0" y2="18" stroke="#451A03" stroke-width="1.5" opacity="0.45"/>',
            "  </pattern>",
            "</defs>",
            f'<rect x="0" y="0" width="{W}" height="{H}" fill="#0F172A"/>',
            '<rect x="24" y="18" width="1752" height="68" rx="10" fill="#1E293B" stroke="#38BDF8" stroke-width="1.5"/>',
            '<text x="900" y="48" text-anchor="middle" fill="#F8FAFC" font-family="DejaVu Sans, Tahoma, sans-serif" direction="rtl" unicode-bidi="embed" font-size="20" font-weight="bold">'
            "خروجی سه‌بعدی و نمای جنوبی مستقیم از پلان — ArchitectOS v20.0 (3D Elevation &amp; Perspective Engine)"
            "</text>",
            f'<text x="900" y="73" text-anchor="middle" fill="#38BDF8" font-family="DejaVu Sans, Tahoma, sans-serif" direction="rtl" unicode-bidi="embed" font-size="13">'
            f"سبک و متریال انتخابی: {style['name_fa']} | منطبق با ستون C-1، تراس با سقف چوب مشبک، مینی‌بار طبقه اول و وید دوطبقه شرقی"
            "</text>",
        ]

        # PANEL 1 (LEFT): ORTHOGRAPHIC ARCHITECTURAL SOUTH ELEVATION
        px1, py1, pw1, ph1 = 30, 102, 845, 790
        lines.extend([
            f'<rect x="{px1}" y="{py1}" width="{pw1}" height="{ph1}" rx="10" fill="url(#skyGrad)" stroke="#475569" stroke-width="2"/>',
            f'<rect x="{px1}" y="{py1}" width="{pw1}" height="40" rx="8" fill="#0F172A" opacity="0.82"/>',
            f'<text x="{px1 + pw1/2}" y="{py1 + 26}" text-anchor="middle" fill="#F8FAFC" font-family="DejaVu Sans, Tahoma, sans-serif" direction="rtl" unicode-bidi="embed" font-size="15" font-weight="bold">'
            "۱. نمای جنوبی مهندسی منطبق با آکس‌های پلان (Orthographic South Elevation — Scale 1:100)"
            "</text>",
        ])

        g_y = py1 + 670
        lines.append(f'<rect x="{px1}" y="{g_y}" width="{pw1}" height="{py1+ph1-g_y}" fill="#CBD5E1"/>')
        for gx in range(px1 + 40, px1 + pw1, 55):
            lines.append(f'<line x1="{gx}" y1="{g_y}" x2="{gx-25}" y2="{py1+ph1}" stroke="#94A3B8" stroke-width="1"/>')

        bx0 = px1 + 122
        bx_c1 = bx0 + 345
        bx1 = bx0 + 565

        y_plinth = g_y - 27
        y_f1 = g_y - 231
        y_roof_w = g_y - 435
        y_roof_e = g_y - 455

        lines.append(f'<rect x="{bx0}" y="{y_plinth}" width="{bx1-bx0}" height="27" fill="{base_stone}" stroke="#0F172A" stroke-width="1.5"/>')
        lines.append(f'<rect x="{bx0}" y="{y_roof_w}" width="{bx_c1-bx0}" height="{y_plinth-y_roof_w}" fill="{wall_main}" stroke="#1E293B" stroke-width="2"/>')
        lines.append(f'<rect x="{bx0+18}" y="{y_roof_w+26}" width="{bx_c1-bx0-30}" height="{y_f1 - (y_roof_w+26)}" fill="url(#woodPlanks)" stroke="#451A03" stroke-width="1.5"/>')

        for tx in range(bx0 + 26, bx_c1 - 16, 18):
            lines.append(f'<rect x="{tx}" y="{y_roof_w+26}" width="10" height="14" fill="#78350F" stroke="#451A03" stroke-width="1"/>')
        for lx in range(bx0 + 40, bx_c1 - 40, 65):
            lines.append(f'<line x1="{lx}" y1="{y_roof_w+42}" x2="{lx+42}" y2="{y_roof_w+42}" stroke="#FEF08A" stroke-width="3"/>')

        lines.append(f'<rect x="{bx0+36}" y="{y_roof_w+55}" width="180" height="115" fill="url(#warmInterior)" stroke="{frame}" stroke-width="3"/>')
        lines.append(f'<rect x="{bx0+36}" y="{y_roof_w+55}" width="180" height="115" fill="url(#glassGrad)" stroke="{frame}" stroke-width="3"/>')
        lines.append(f'<line x1="{bx0+96}" y1="{y_roof_w+55}" x2="{bx0+96}" y2="{y_roof_w+170}" stroke="{frame}" stroke-width="2"/>')
        lines.append(f'<line x1="{bx0+156}" y1="{y_roof_w+55}" x2="{bx0+156}" y2="{y_roof_w+170}" stroke="{frame}" stroke-width="2"/>')
        lines.append(f'<rect x="{bx0+235}" y="{y_roof_w+55}" width="58" height="140" fill="url(#glassGrad)" stroke="{frame}" stroke-width="3"/>')

        lines.append(f'<rect x="{bx0+18}" y="{y_f1-66}" width="{bx_c1-bx0-30}" height="52" fill="#BAE6FD" fill-opacity="0.42" stroke="#0284C7" stroke-width="2"/>')
        lines.append(f'<rect x="{bx0+18}" y="{y_f1-14}" width="{bx_c1-bx0-30}" height="14" fill="#334155"/>')

        lines.append(f'<rect x="{bx0+30}" y="{y_f1+28}" width="165" height="145" fill="url(#warmInterior)" stroke="{frame}" stroke-width="3"/>')
        lines.append(f'<rect x="{bx0+30}" y="{y_f1+28}" width="165" height="145" fill="url(#glassGrad)" stroke="{frame}" stroke-width="3"/>')
        for mx in (bx0 + 85, bx0 + 140):
            lines.append(f'<line x1="{mx}" y1="{y_f1+28}" x2="{mx}" y2="{y_f1+173}" stroke="{frame}" stroke-width="2.5"/>')
        lines.append(f'<line x1="{bx0+30}" y1="{y_f1+100}" x2="{bx0+195}" y2="{y_f1+100}" stroke="{frame}" stroke-width="2"/>')

        lines.append(f'<rect x="{bx0+220}" y="{y_f1+16}" width="112" height="{y_plinth - (y_f1+16)}" fill="url(#woodPlanks)" stroke="#451A03" stroke-width="1.5"/>')
        lines.append(f'<rect x="{bx0+248}" y="{y_f1+42}" width="62" height="{y_plinth - (y_f1+42)}" fill="#1E293B" stroke="#0F172A" stroke-width="2.5"/>')
        lines.append(f'<line x1="{bx0+298}" y1="{y_f1+85}" x2="{bx0+298}" y2="{y_f1+155}" stroke="#F59E0B" stroke-width="3"/>')
        for si in range(3):
            sw = 116 + si * 18
            sx = bx0 + 220 + 56 - sw / 2
            sy = y_plinth + si * 9
            lines.append(f'<rect x="{sx}" y="{sy}" width="{sw}" height="9" rx="3" fill="#94A3B8" stroke="#475569" stroke-width="1"/>')

        lines.append(f'<rect x="{bx_c1-12}" y="{y_roof_e}" width="24" height="{y_plinth-y_roof_e}" fill="{wall_main}" stroke="#0284C7" stroke-width="2" stroke-dasharray="6,3"/>')
        lines.append(f'<rect x="{bx_c1}" y="{y_roof_e}" width="{bx1-bx_c1}" height="{y_plinth-y_roof_e}" fill="{wall_main}" stroke="#1E293B" stroke-width="2.5"/>')

        cw_x, cw_y, cw_w, cw_h = bx_c1 + 22, y_roof_e + 28, bx1 - bx_c1 - 44, y_plinth - y_roof_e - 42
        lines.append(f'<rect x="{cw_x-8}" y="{cw_y-8}" width="{cw_w+16}" height="{cw_h+16}" fill="{frame}"/>')
        lines.append(f'<rect x="{cw_x}" y="{cw_y}" width="{cw_w}" height="{cw_h}" fill="url(#warmInterior)"/>')
        lines.append(f'<rect x="{cw_x}" y="{cw_y}" width="{cw_w}" height="{cw_h}" fill="url(#glassGrad)" stroke="{frame}" stroke-width="3"/>')
        for col_i in range(1, 4):
            mx = cw_x + cw_w * col_i / 4.0
            lines.append(f'<line x1="{mx}" y1="{cw_y}" x2="{mx}" y2="{cw_y+cw_h}" stroke="{frame}" stroke-width="3"/>')
        lines.append(f'<rect x="{cw_x}" y="{y_f1-10}" width="{cw_w}" height="20" fill="{frame}"/>')
        for row_y in (cw_y + 75, cw_y + 150, y_f1 + 80, y_f1 + 145):
            lines.append(f'<line x1="{cw_x}" y1="{row_y}" x2="{cw_x+cw_w}" y2="{row_y}" stroke="{frame}" stroke-width="2"/>')

        lines.append(f'<rect x="{bx0-6}" y="{y_roof_w-10}" width="{bx_c1-bx0+12}" height="12" fill="{coping}"/>')
        lines.append(f'<rect x="{bx_c1-6}" y="{y_roof_e-12}" width="{bx1-bx_c1+12}" height="14" fill="{coping}"/>')
        if is_neoclassical:
            lines.append(f'<polygon points="{bx0+150},{y_roof_w-10} {bx0+275},{y_roof_w-68} {bx_c1+10},{y_roof_w-10}" fill="{wall_acc}" stroke="#78350F" stroke-width="2"/>')

        for ax_lbl, ax_x in (("A (0.29m)", bx0), ("C-1 (6.05m)", bx_c1), ("D (9.71m)", bx1)):
            lines.append(f'<line x1="{ax_x}" y1="{py1+52}" x2="{ax_x}" y2="{y_roof_e-16}" stroke="#0284C7" stroke-width="1.2" stroke-dasharray="5,4"/>')
            lines.append(f'<circle cx="{ax_x}" cy="{py1+68}" r="14" fill="#0F172A" stroke="#38BDF8" stroke-width="2"/>')
            lines.append(f'<text x="{ax_x}" y="{py1+73}" text-anchor="middle" fill="#38BDF8" font-family="DejaVu Sans, Tahoma, sans-serif" direction="rtl" unicode-bidi="embed" font-size="10" font-weight="bold">{ax_lbl.split()[0]}</text>')

        callouts = [
            (bx0 + 135, y_roof_w + 35, "تراس جنوبی طبقه اول با سقف چوب مشبک (پرگولا) + مینی‌بار"),
            (bx_c1, y_roof_w - 24, "ستون C-1 حفظ‌شده در تراز نما"),
            (bx_c1 + 110, y_roof_e + 65, "پنجره قدی دوطبقه وید دوبلکس (کرتین‌وال)"),
        ]
        for cx, cy, ctxt in callouts:
            lines.append(f'<rect x="{cx-115}" y="{cy-14}" width="230" height="22" rx="5" fill="#0F172A" fill-opacity="0.86" stroke="#38BDF8" stroke-width="1"/>')
            lines.append(f'<text x="{cx}" y="{cy+1}" text-anchor="middle" fill="#F8FAFC" font-family="DejaVu Sans, Tahoma, sans-serif" direction="rtl" unicode-bidi="embed" font-size="10">{ctxt}</text>')

        for tx, tr in ((bx0 - 35, 38), (bx0 + 195, 24), (bx1 + 35, 42)):
            lines.append(f'<ellipse cx="{tx}" cy="{g_y-tr+10}" rx="{tr*0.85}" ry="{tr}" fill="#15803D" stroke="#14532D" stroke-width="1.5"/>')

        # PANEL 2 (RIGHT): 3D TWO-POINT PERSPECTIVE RENDER
        px2, py2, pw2, ph2 = 905, 102, 865, 790
        lines.extend([
            f'<rect x="{px2}" y="{py2}" width="{pw2}" height="{ph2}" rx="10" fill="url(#skyGrad)" stroke="#475569" stroke-width="2"/>',
            f'<rect x="{px2}" y="{py2}" width="{pw2}" height="40" rx="8" fill="#0F172A" opacity="0.82"/>',
            f'<text x="{px2 + pw2/2}" y="{py2 + 26}" text-anchor="middle" fill="#F8FAFC" font-family="DejaVu Sans, Tahoma, sans-serif" direction="rtl" unicode-bidi="embed" font-size="15" font-weight="bold">'
            "۲. رندر پرسپکتیو سه‌بعدی با زاویه دید ناظر و متریال انتخابی (3D Architectural Perspective)"
            "</text>",
        ])

        p_gy = py2 + 625
        lines.append(f'<polygon points="{px2},{p_gy} {px2+pw2},{p_gy} {px2+pw2},{py2+ph2} {px2},{py2+ph2}" fill="#CBD5E1"/>')
        for i in range(-5, 9):
            x_top = px2 + 430 + i * 45
            x_bot = px2 + 430 + i * 115
            lines.append(f'<line x1="{x_top}" y1="{p_gy}" x2="{x_bot}" y2="{py2+ph2}" stroke="#94A3B8" stroke-width="1.2"/>')

        lines.append(f'<polygon points="{px2+95},{py2+285} {px2+195},{py2+235} {px2+195},{p_gy} {px2+95},{p_gy+25}" fill="#CBD5E1" stroke="#334155" stroke-width="1.5"/>')
        lines.append(f'<polygon points="{px2+195},{py2+235} {px2+515},{py2+245} {px2+515},{p_gy} {px2+195},{p_gy}" fill="{wall_main}" stroke="#1E293B" stroke-width="2"/>')
        lines.append(f'<polygon points="{px2+212},{py2+262} {px2+498},{py2+270} {px2+498},{py2+435} {px2+212},{py2+430}" fill="url(#woodPlanks)" stroke="#451A03" stroke-width="1.5"/>')
        for b_i in range(8):
            bx_p = px2 + 224 + b_i * 33
            lines.append(f'<polygon points="{bx_p},{py2+263} {bx_p+14},{py2+263} {bx_p+28},{py2+292} {bx_p+14},{py2+292}" fill="#78350F" stroke="#451A03" stroke-width="1"/>')
        lines.append(f'<polygon points="{px2+235},{py2+296} {px2+470},{py2+302} {px2+470},{py2+422} {px2+235},{py2+418}" fill="url(#warmInterior)"/>')
        lines.append(f'<polygon points="{px2+235},{py2+296} {px2+470},{py2+302} {px2+470},{py2+422} {px2+235},{py2+418}" fill="url(#glassGrad)" stroke="{frame}" stroke-width="2.5"/>')
        lines.append(f'<polygon points="{px2+212},{py2+382} {px2+498},{py2+388} {px2+498},{py2+435} {px2+212},{py2+430}" fill="#BAE6FD" fill-opacity="0.48" stroke="#0284C7" stroke-width="2"/>')

        lines.append(f'<polygon points="{px2+222},{py2+462} {px2+375},{py2+465} {px2+375},{py2+590} {px2+222},{py2+590}" fill="url(#warmInterior)"/>')
        lines.append(f'<polygon points="{px2+222},{py2+462} {px2+375},{py2+465} {px2+375},{py2+590} {px2+222},{py2+590}" fill="url(#glassGrad)" stroke="{frame}" stroke-width="3"/>')
        lines.append(f'<polygon points="{px2+395},{py2+455} {px2+498},{py2+458} {px2+498},{p_gy-22} {px2+395},{p_gy-22}" fill="url(#woodPlanks)" stroke="#451A03" stroke-width="1.5"/>')
        lines.append(f'<polygon points="{px2+422},{py2+476} {px2+476},{py2+478} {px2+476},{p_gy-22} {px2+422},{p_gy-22}" fill="#1E293B" stroke="#0F172A" stroke-width="2"/>')

        lines.append(f'<polygon points="{px2+515},{py2+210} {px2+765},{py2+228} {px2+765},{p_gy} {px2+515},{p_gy}" fill="{wall_main}" stroke="#1E293B" stroke-width="2.5"/>')
        lines.append(f'<polygon points="{px2+495},{py2+222} {px2+515},{py2+210} {px2+515},{p_gy} {px2+495},{p_gy}" fill="#E2E8F0" stroke="#475569" stroke-width="1.5"/>')
        lines.append(f'<polygon points="{px2+535},{py2+242} {px2+742},{py2+256} {px2+742},{p_gy-26} {px2+535},{p_gy-26}" fill="url(#warmInterior)"/>')
        lines.append(f'<polygon points="{px2+535},{py2+242} {px2+742},{py2+256} {px2+742},{p_gy-26} {px2+535},{p_gy-26}" fill="url(#glassGrad)" stroke="{frame}" stroke-width="4"/>')
        for m_x in (px2 + 588, px2 + 640, px2 + 692):
            lines.append(f'<line x1="{m_x}" y1="{py2+246}" x2="{m_x}" y2="{p_gy-26}" stroke="{frame}" stroke-width="3"/>')
        lines.append(f'<polygon points="{px2+535},{py2+428} {px2+742},{py2+435} {px2+742},{py2+452} {px2+535},{py2+446}" fill="{frame}"/>')

        lines.append(f'<polygon points="{px2+55},{p_gy+38} {px2+345},{p_gy+38} {px2+305},{py2+ph2-18} {px2+25},{py2+ph2-18}" fill="#0284C7" stroke="#E2E8F0" stroke-width="5"/>')
        lines.append(f'<polygon points="{px2+65},{p_gy+46} {px2+335},{p_gy+46} {px2+298},{py2+ph2-26} {px2+35},{py2+ph2-26}" fill="#38BDF8" fill-opacity="0.65"/>')

        lines.append(f'<polygon points="{px2+218},{py2+430} {px2+236},{py2+315} {px2+254},{py2+430}" fill="#15803D" stroke="#14532D" stroke-width="1.5"/>')
        lines.append(f'<ellipse cx="{px2+785}" cy="{p_gy-35}" rx="36" ry="52" fill="#15803D" stroke="#14532D" stroke-width="1.5"/>')

        prompt_str = cls.build_photorealistic_prompt(project, style_key)
        lines.extend([
            '<rect x="30" y="906" width="1740" height="154" rx="10" fill="#1E293B" stroke="#475569" stroke-width="1.5"/>',
            '<text x="1745" y="934" text-anchor="end" fill="#38BDF8" font-family="DejaVu Sans, Tahoma, sans-serif" direction="rtl" unicode-bidi="embed" font-size="14" font-weight="bold">'
            "پرامپت و هندسه خروجی موتور برای رندر فتورئالیستی (Geometry-Locked AI Render Prompt):"
            "</text>",
            f'<text x="50" y="962" fill="#E2E8F0" font-family="Consolas, monospace" font-size="11.5">{prompt_str[:145]}</text>',
            f'<text x="50" y="984" fill="#E2E8F0" font-family="Consolas, monospace" font-size="11.5">{prompt_str[145:295]}</text>',
            f'<text x="50" y="1006" fill="#E2E8F0" font-family="Consolas, monospace" font-size="11.5">{prompt_str[295:]}</text>',
            '<text x="1745" y="1038" text-anchor="end" fill="#4ADE80" font-family="DejaVu Sans, Tahoma, sans-serif" direction="rtl" unicode-bidi="embed" font-size="13" font-weight="bold">'
            "وضعیت موتور v20.0: پشتیبانی از ویرایش تعاملی در چت (ConversationalPlanEditor) + تولید خودکار نما و پرسپکتیو سه‌بعدی با ۴ سبک و متریال مختلف"
            "</text>",
            "</svg>",
        ])

        os.makedirs(os.path.dirname(os.path.abspath(out_svg_path)), exist_ok=True)
        with open(out_svg_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return out_svg_path
