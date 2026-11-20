#!/usr/bin/env python3
"""
ArchitectOS V23.0 — Conversational Persian & English Architectural Intelligence Engine (`persian_architectural_brain_v23.py`)
File: core/render/persian_architectural_brain_v23.py

Solves two critical production gaps identified in live user testing (`image_3e78fb.jpg` & `00003/00004`):
  1. COLLOQUIAL PERSIAN RENDER INTENT & FOLLOW-UP ROUTING (`چرا "حالا همین ساختمون رو از یه زاویه دیگه رندر شبش بگیر" رندر نگرفت؟`):
     - Previously, the chat router failed to recognize colloquial Persian render/edit follow-ups with attached pronominal
       clitics (`رندر شبش بگیر`, `شبش کن`, `رندرش کن`, `نماش رو عوض کن`, `همین ساختمون رو ... بگیر`) as active ComfyUI render
       commands, routing them instead to the text-only JSON summary message (`🏠 طراحی معماری آماده شد...`).
     - `classify_conversational_render_intent(user_text, has_active_image, has_active_plan)` accurately parses colloquial
       Persian and English commands and routes them to the exact execution pipeline:
         * `MODE_3_DAY_TO_NIGHT_RELIGHT`: When the user asks for a night/dusk version of the current/previous building
           (`رندر شبش بگیر`, `شبش کن`, `نورپردازی شب همین ساختمون`, `ببرش تو شب`).
         * `MODE_2_IMG2IMG_CAMERA_OR_STYLE_EDIT`: When the user asks to change the camera angle (`از یه زاویه دیگه`, `نمای سه‌رخ`,
           `پرسپکتیو از بغل`) or change material/style/courtyard/parapet of an active image.
         * `MODE_1_TXT2IMG_EXACT_FLOORS`: When the user requests a new building with `N >= 5` floors (`یه برج ۲۷ طبقه ...`).
         * `MODE_1_TXT2IMG_STANDARD`: When the user requests a new low-rise render from text.
         * `MODE_4_PLAN_TO_3D_RENDER`: When the user asks to render an approved 2D floor plan.

  2. ARCHITECTURAL PROMPT INTELLIGENCE (`build_expert_comfyui_prompts`):
     - Translates short, colloquial Persian user prompts into comprehensive, architecturally rigorous English positive and
       negative prompts for FLUX / SDXL ControlNet, automatically injecting:
         * Complete roof parapet & cornice termination (`continuous stone balustrade parapet across entire roofline, zero protruding rebar rods`),
         * Complete site & courtyard landscaping (`paved travertine stone foreground courtyard with manicured evergreen borders, zero raw construction dirt`),
         * Glazing & fenestration completeness (`full double-glazed reflective architectural glass windows with dark mullions in all openings`),
         * Style-specific architectural vocabulary (Iranian Neoclassical/Roman Travertine, Modern Thermowood & White Stucco, Brick & Exposed Concrete, High-Rise Curtain Wall).
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_PERSIAN_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def normalize_colloquial_persian(text: str) -> str:
    if not isinstance(text, str):
        return ""
    s = text.translate(_PERSIAN_DIGITS)
    s = (
        s.replace("ي", "ی")
        .replace("ك", "ک")
        .replace("\u200c", " ")
        .replace("ساختمون", "ساختمان")
        .replace("خونه", "خانه")
        .replace("پشت بوم", "بام")
        .replace("پشت‌بوم", "بام")
        .replace("جن پناه", "جان پناه")
        .replace("جان‌پناه", "جان پناه")
        .replace("دیگه", "دیگر")
        .replace("همون", "همان")
    )
    s = re.sub(r"(?<!\S)یه(?!\S)", "یک", s)
    s = re.sub(r"(?<!\S)رو(?!\S)", "را", s)
    s = re.sub(r"(?<!\S)اون(?!\S)", "آن", s)
    return " ".join(s.split())


@dataclass(frozen=True)
class ArchitecturalIntentAnalysis:
    is_render_or_visual_edit_request: bool
    render_mode: str
    requested_floors: Optional[int]
    time_of_day: str  # "DAY", "NIGHT", "DUSK"
    camera_angle: str  # "SAME_VIEW", "NEW_PERSPECTIVE_ANGLE", "FRONT_ELEVATION", "BIRDS_EYE"
    style_key: str
    materials_en: List[str]
    architectural_completion_rules_en: List[str]
    positive_prompt_en: str
    negative_prompt_en: str
    explanation_fa: str = ""


# Comprehensive Persian -> English Architectural Lexicon
STYLE_VOCABULARY: Dict[str, Dict[str, Any]] = {
    "NEOCLASSICAL_TRAVERTINE": {
        "keywords_fa": ("نئوکلاسیک", "کلاسیک", "رومی", "صراحی", "سرستون", "سنتوری", "neoclassical", "classical"),
        "style_en": "luxury Iranian neoclassical architectural facade",
        "default_materials_en": [
            "large-format smooth honed cream-beige Iranian travertine stone ashlar slabs",
            "fluted Corinthian stone pilasters with carved classical capitals",
            "continuous carved cream travertine stone baluster railings (نرده صراحی سنگی) along all balconies and roof parapets",
            "carved classical stone window architraves, headers, and triangular pediments",
            "continuous level classical stone roof cornice molding",
        ],
    },
    "MODERN_THERMOWOOD": {
        "keywords_fa": ("مدرن", "ترمووود", "ترمو", "مینیمال", "سقف چوبی", "پرگولا", "modern", "thermowood"),
        "style_en": "contemporary minimalist luxury modern architectural facade",
        "default_materials_en": [
            "crisp smooth white micro-cement stucco volumes",
            "warm horizontal natural thermowood timber cladding and slatted wood soffits",
            "frameless laminated glass balustrades on terraces and roof parapets",
            "slim matte-black aluminum floor-to-ceiling window frames and mullions",
            "clean flat dark metal roof parapet coping",
        ],
    },
    "BRICK_CONCRETE_MODERN": {
        "keywords_fa": ("آجر", "آجری", "بتن اکسپوز", "بتن", "رستیک", "brick", "concrete"),
        "style_en": "contemporary Iranian brick and exposed concrete architectural facade",
        "default_materials_en": [
            "precision-laid warm red-ochre Iranian firebrick masonry panels",
            "smooth architectural board-formed exposed concrete spandrel bands",
            "matte charcoal-black aluminum double-glazed window frames",
            "clean stone parapet coping across the entire roofline",
        ],
    },
}

MATERIAL_OVERRIDE_MAP: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("تراورتن کرم", "تراورتن روشن", "سنگ کرم", "سنگ عباس آباد"), "smooth honed cream-beige Iranian travertine stone slabs"),
    (("تراورتن", "سنگ تراورتن"), "honed natural travertine stone cladding"),
    (("مرمر", "سنگ مرمر"), "polished veined marble stone slabs"),
    (("سنگ مشکی", "بازالت", "گرانیت مشکی"), "honed dark basalt and Nero Marquina stone accents"),
    (("ترمووود", "چوب ترمو", "چوب"), "warm architectural thermowood timber louvers and cladding"),
    (("سیمان سفید", "پلاستر سفید"), "smooth white architectural stucco finish"),
    (("آجر قرمز", "آجر نسوز", "آجر"), "warm textured architectural firebrick masonry"),
    (("بتن اکسپوز", "بتن"), "architectural board-formed exposed concrete"),
    (("کرتین وال", "شیشه قدی", "نمای شیشه ای"), "floor-to-ceiling black-mullioned aluminum curtain wall glazing"),
    (("نرده سنگی", "صراحی"), "continuous carved stone baluster railings across all balconies and roof parapets"),
)


def extract_floor_count_colloquial(text: str) -> Optional[int]:
    s = normalize_colloquial_persian(text)
    # Check negation first
    for m in re.finditer(r"(?<![\d.,])(\d{1,3})\s*(?:طبقه|اشکوب|story|stories|storey|storeys|floors?)", s, re.IGNORECASE):
        val = int(m.group(1))
        if not (1 <= val <= 150):
            continue
        start, end = m.span()
        before = s[max(0, start - 24):start].lower()
        after = s[end:end + 26].lower()
        if any(neg in before for neg in ("نمی", "نه ", "بدون", "not ", "no ", "without ")):
            continue
        if any(neg in after for neg in ("نمی خواهم", "نمیخواهم", "لازم نیست", "نباشد")):
            continue
        return val
    return None


def classify_conversational_render_intent(
    user_text: str,
    *,
    has_active_image: bool = False,
    has_active_plan: bool = False,
) -> ArchitecturalIntentAnalysis:
    """
    Master conversational intent analyzer & prompt builder for Persian/English chat requests.
    Guarantees that follow-up requests like:
      - "حالا همین ساختمون رو از یه زاویه دیگه رندر شبش بگیر"
      - "میلگردها رو حذف کن و حیاط رو سنگفرش کن و نرده سنگی رو ادامه بده"
      - "یه برج 27 طبقه با سبک نئوکلاسیک و متریال سنگ تراورتن کرم رندر بگیر"
    ALWAYS trigger the ComfyUI render pipeline instead of falling through to a text-only stub!
    """
    raw = str(user_text or "").strip()
    norm = normalize_colloquial_persian(raw)
    low = norm.lower()

    # 1. Detect if this is a visual render / image edit request
    render_triggers = (
        "رندر", "ریسپکتیو", "پرسپکتیو", "نما", "شب", "شبش", "غروب", "روز",
        "زاویه", "متریال", "سنگ", "آجر", "چوب", "نئوکلاسیک", "مدرن", "کلاسیک",
        "برج", "ساختمان", "طبقه", "میلگرد", "جان پناه", "نرده", "حیاط", "محوطه",
        "پنجره", "render", "night", "day", "facade", "tower", "style", "material",
    )
    # Exclude pure 2D floor-plan-only drafting requests unless they also ask for a render/3D/facade
    is_pure_2d_plan_request = (
        any(k in low for k in ("پلان", "آکس", "داکت", "مطبخ", "کمد دیواری"))
        and not any(k in low for k in ("رندر", "پرسپکتیو", "سه بعدی", "سه‌بعدی", "نمای", "شب"))
    )
    is_render_req = any(k in low for k in render_triggers) and not is_pure_2d_plan_request

    # 2. Detect Time of Day ("NIGHT", "DUSK", "DAY")
    is_night = any(
        k in low
        for k in (
            "رندر شب", "رندر شبش", "شبش بگیر", "شبش کن", "نمای شب", "در شب",
            "نورپردازی شب", "حالت شب", "تو شب", "night", "blue hour", "twilight",
        )
    )
    is_dusk = any(k in low for k in ("غروب", "عصر", "dusk", "golden hour", "sunset"))
    time_of_day = "NIGHT" if is_night else ("DUSK" if is_dusk else "DAY")

    # 3. Detect Camera Angle / View Change
    wants_new_angle = any(
        k in low
        for k in (
            "زاویه دیگه", "زاویه دیگر", "یه زاویه", "یک زاویه", "سه رخ", "سه‌رخ",
            "از بغل", "از کنار", "دید پرنده", "ایزومتریک", "another angle", "different angle",
        )
    )
    if any(k in low for k in ("دید پرنده", "بالا", "bird", "aerial")):
        camera_angle = "BIRDS_EYE"
    elif wants_new_angle:
        camera_angle = "NEW_PERSPECTIVE_ANGLE"
    elif any(k in low for k in ("نمای روبرو", "نمای جنوبی", "front elevation")):
        camera_angle = "FRONT_ELEVATION"
    else:
        camera_angle = "SAME_VIEW"

    # 4. Detect Reference to Current / Previous Active Building ("همین نما", "همین ساختمون", "همون", "رندر شب بگیر")
    refers_to_active = has_active_image and (
        any(
            k in low
            for k in (
                "همین", "همان", "این نما", "همین نما", "این ساختمان", "این بنا", "شبش", "روزش",
                "رندر شب", "رندر روز", "رندرش", "نمای شب", "نمای روز", "تغییر", "عوض کن",
                "میلگرد", "جان پناه", "حیاطش", "محوطه", "ادامه بده", "حذف کن",
            )
        )
        or is_night
    )

    # 5. Extract Floor Count
    floors = extract_floor_count_colloquial(norm)

    # 6. Detect Style & Materials
    detected_style = "NEOCLASSICAL_TRAVERTINE"
    for skey, sdata in STYLE_VOCABULARY.items():
        if any(kw in low for kw in sdata["keywords_fa"]):
            detected_style = skey
            break

    style_meta = STYLE_VOCABULARY[detected_style]
    materials_en: List[str] = []
    for kw_tuple, mat_en in MATERIAL_OVERRIDE_MAP:
        if any(k in low for k in kw_tuple):
            materials_en.append(mat_en)
    for default_m in style_meta["default_materials_en"]:
        if default_m not in materials_en:
            materials_en.append(default_m)

    # 7. Select Exact Execution Mode
    wants_plan_facade_render = has_active_plan and (
        any(k in low for k in ("از پلان", "پلان را رندر", "پلان رو رندر", "سه بعدی پلان", "نمای پلان", "نمای جنوبی", "از همین ساختمان", "همین ساختمان را رندر", "همین ساختمان یک رندر"))
        and not (has_active_image and is_night and "نمای جنوبی" not in low)
    )
    if wants_plan_facade_render:
        render_mode = "MODE_4_PLAN_TO_3D_RENDER"
    elif refers_to_active and (is_night or any(k in low for k in ("رندر روز", "روزش بگیر", "در روز", "نمای روز"))) and not wants_new_angle:
        # Strict Zero-Drift Bidirectional Day <-> Night Relighting on the active image!
        render_mode = "MODE_3_DAY_TO_NIGHT_RELIGHT"
    elif refers_to_active and (wants_new_angle or not is_night):
        # Image-to-Image / Reference-conditioned edit (or new camera angle of active building with USO style lock)
        render_mode = "MODE_2_IMG2IMG_MATERIAL_STYLE_TRANSFER"
    elif floors is not None and floors >= 3:
        render_mode = "MODE_1_TXT2IMG_EXACT_FLOORS"
    else:
        render_mode = "MODE_1_TXT2IMG_STANDARD"

    # 8. Mandatory Architectural Completion Rules (prevents rebar spikes, raw dirt yards, and broken parapets!)
    completion_rules_en = [
        "clean continuous horizontal roof parapet and cornice across the entire building width with zero protruding rebar rods or construction spikes",
        "continuous unbroken balustrade railing across all balcony and roof parapet bays all the way to the building corners",
        "fully landscaped and paved foreground courtyard with large-format stone pavers and manicured evergreen planter borders (zero raw construction dirt or rubble)",
        "complete double-glazed reflective glass windows with crisp mullions and architectural doors installed in all openings",
    ]

    # 9. Construct Rich English Positive & Negative Prompts for FLUX / ComfyUI
    floor_desc = (
        f"monumental {floors}-story high-rise architectural tower ({floors} distinct stacked floor tiers, full building from street-level podium to top roof crown 100% inside frame with generous sky margin above roof)"
        if (floors and floors >= 5)
        else (f"{floors}-story architectural building" if floors else "multi-story architectural building")
    )

    if camera_angle == "NEW_PERSPECTIVE_ANGLE":
        cam_desc = "three-quarter two-point eye-level architectural perspective view from a 35-degree corner angle showing both the front facade and side depth"
    elif camera_angle == "BIRDS_EYE":
        cam_desc = "elevated three-quarter bird's-eye architectural perspective view"
    elif camera_angle == "FRONT_ELEVATION":
        cam_desc = "straight-on symmetrical front architectural elevation view, 50mm tilt-shift architectural lens"
    else:
        cam_desc = "eye-level architectural exterior photography preserving the exact camera perspective and building proportions"

    if time_of_day == "NIGHT":
        light_desc = (
            "architectural blue-hour night photography, deep twilight blue sky (luma <= 38), "
            "facade warmly and clearly illuminated by 3000K linear LED wall-washer uplights on all columns/pilasters, "
            "warm eaves downlights under every cornice, warm 2900K cozy interior chandelier glow through all glass windows, "
            "and warm landscape bollard lights illuminating the paved stone courtyard (facade clearly visible, never pitch-black)"
        )
    elif time_of_day == "DUSK":
        light_desc = (
            "golden-hour sunset dusk architectural photography, warm directional sunlight grazing the stone relief combined with warm 3000K architectural soffit and window lighting"
        )
    else:
        light_desc = "crisp natural sunny daylight architectural photography with soft realistic shadows and sky reflections on double-glazed windows"

    pos_prompt = (
        f"Masterpiece 8k photorealistic architectural photography, {cam_desc}, {floor_desc}, "
        f"{style_meta['style_en']}, materials: {', '.join(materials_en[:4])}; "
        f"architectural perfection: {'; '.join(completion_rules_en)}; "
        f"lighting: {light_desc}, ultra-detailed V-Ray Corona Renderer."
    )

    neg_prompt = (
        "protruding roof rebar rods, steel starter bars on roof, unfinished roof parapet, missing balustrade on right side, "
        "broken skyline corner, raw construction dirt yard, mud, rubble, gravel debris, unglazed black window holes, "
        "raw orange hollow clay bricks, grey cinderblocks, rubble stone, mortar bleed, cropped roof, building cut off at top edge, "
        "pitch-black silhouette facade, altered window positions, deformed perspective, watermark, text, blurry"
    )

    return ArchitecturalIntentAnalysis(
        is_render_or_visual_edit_request=is_render_req,
        render_mode=render_mode,
        requested_floors=floors,
        time_of_day=time_of_day,
        camera_angle=camera_angle,
        style_key=detected_style,
        materials_en=materials_en,
        architectural_completion_rules_en=completion_rules_en,
        positive_prompt_en=pos_prompt,
        negative_prompt_en=neg_prompt,
        explanation_fa=f"تشخیص هوشمند معماری: مود={render_mode} | زمان={time_of_day} | زاویه={camera_angle} | طبقات={floors or 'حفظ تصویر فعلی'}",
    )
