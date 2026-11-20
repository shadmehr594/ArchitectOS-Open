"""
Parametric Persian & English Natural Language Architectural Prompt Parser (v27.0).
Fixes all issues where the bot ignored user requests or repeated the same 10x20 Duplex plan:
  1. Distinguishes NEW plan creation requests (`is_new_plan_creation_prompt`) from incremental edits
     (`is_plan_modification_prompt`) so asking for a new design ("یک ساختمان ویلایی با 150 متر مربع در زمینی به مساحت 250 متر مربع طراحی کن")
     NEVER gets misclassified as an edit on an old Duplex!
  2. Extracts BOTH explicit dimensions (`10*20`, `12 در 25`) AND area-based specifications:
     - Site area in m² (`در زمینی به مساحت 250 متر مربع`, `قطعه زمین 200 مترمربع`, `زمین 300 متری`)
     - Building footprint / area in m² (`به مساحت 120 مترمربع`, `با 150 متر مربع`, `زیربنای 180 متر`)
     - Automatically derives `site_width_mm`, `site_length_mm`, and `coverage_ratio` from areas or active Krocki (`active_site_krocki`)!
  3. Extracts full architectural parameters & incremental edits:
     - `remove_duplex_void` & `void_replacement_room` ("وید طبقه بالا رو حذف کن و یه نشیمن خصوصی به جاش بزار")
     - `bedroom_count` (1, 2, 3, 4 bedrooms)
     - `kitchen_extra_width_mm` ("آشپزخانه بزرگتر / کوچکتر")
     - `living_extra_width_mm` ("پذیرایی / نشیمن بزرگتر / کوچکتر")
     - `terrace_extra_depth_mm` & `include_terrace` ("تراس بزرگتر / کوچکتر / حذف تراس")
     - `include_dirty_kitchen` ("با مطبخ / حذف مطبخ")
     - `lightwell_enabled`, `lightwell_depth_mm`, `lightwell_area_m2`
     - `typology` (`VILLA_1FLOOR`, `DUPLEX_2FLOOR`, `MULTIFLOOR_RESIDENTIAL`, `MIXED_USE_MULTIFLOOR`)
"""

from __future__ import annotations
import copy
import math
import re
from typing import Any, Dict, Optional
from .domain import BuildingTypology

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

_WORD_TO_INT = {
    "یک": 1, "یه": 1, "تک": 1,
    "دو": 2,
    "سه": 3,
    "چهار": 4,
    "پنج": 5,
    "شش": 6,
}


def normalize_persian_text(text: str) -> str:
    s = str(text or "").translate(_PERSIAN_DIGITS)
    s = (
        s.replace("ي", "ی")
        .replace("ك", "ک")
        .replace("\u200c", " ")
        .replace("×", "*")
        .replace("x", "*")
        .replace("X", "*")
        .replace("ساختمون", "ساختمان")
        .replace("آشپزخونه", "آشپزخانه")
        .replace("خونه", "خانه").replace("بمساحت", "به مساحت").replace("بامساحت", "با مساحت")
    )
    return " ".join(s.split())



_RENDER_EXPLICIT_KWS = (
    "رندر", "render", "پرسپکتیو", "ریسپکتیو",
    "نمای جنوبی", "نما جنوبی", "نمای شمالی", "نما شمالی",
    "نمای شرقی", "نما شرقی", "نمای غربی", "نما غربی",
    "نمای ساختمان", "نمای روبرو", "نمای شب", "نمای روز",
    "سه بعدی", "سه‌بعدی", "facade",
)

_RENDER_ITERATIVE_EDIT_KWS = (
    "رندر شب", "حالت شب", "شبش کن", "شب بگیر", "نورپردازی شب", "نورپردازی نما", "نورپردازی خطی", "وال واشر", "وال‌واشر",
    "رندر روز", "روزش کن", "روز آفتابی", "غروب", "هوای ابری", "ابری کن",
    "سبک نما", "متریال نما", "رنگ نما", "رنگ سنگ", "سنگ نما",
    "تراورتن", "سنگ سفید", "سنگ کرم", "سنگ تیره", "سنگ مشکی", "عباس آباد", "عباس‌آباد",
    "چوب ترمووود", "ترمووود", "چوب ترمو", "لوور چوبی",
    "آجر نما", "آجر نسوز", "آجری کن", "سیمان سفید", "بتن اکسپوز",
    "نئوکلاسیک", "نئو کلاسیک", "کلاسیک", "رومی", "مدرنش کن", "سبک مدرن", "مینیمال",
    "نرده صراحی", "صراحی سنگی", "نرده شیشه ای", "نرده شیشه‌ای", "نرده سنگی", "نرده فلزی",
    "فریم پنجره", "قاب پنجره",
)

_PLAN_2D_STRUCTURAL_EDIT_KWS = (
    "طراحی کن", "بچرخون", "بچرخان", "چرخش پلان", "حیاط خلوت", "پاسیو",
    "سطح اشغال", "مطبخ", "آشپزخانه", "پذیرایی", "اتاق خواب", "خواب مستر",
    "مینی بار", "مینی‌بار", "راهرو کنار", "تبدیلش کن به اتاق", "وید طبقه بالا",
    "حذف وید", "بستن وید", "پله", "آکس", "داکت",
)


def is_3d_render_or_render_edit_prompt(text: str, prev_params: Optional[Dict[str, Any]] = None) -> bool:
    s = normalize_persian_text(text).lower()
    if not s:
        return False
    has_2d_plan_cmd = any(k in s for k in _PLAN_2D_STRUCTURAL_EDIT_KWS) and "رندر" not in s
    if has_2d_plan_cmd:
        return False
    if any(k in s for k in _RENDER_EXPLICIT_KWS) and "طراحی کن" not in s:
        return True
    if any(k in s for k in _RENDER_ITERATIVE_EDIT_KWS) and "پلان" not in s and "طراحی کن" not in s:
        return True
    if isinstance(prev_params, dict) and (prev_params.get("render_3d_facade_mode") or prev_params.get("active_render_state")):
        if any(k in s for k in ("شب", "روز", "غروب", "سفید", "کرم", "تیره", "مشکی", "مدرن", "کلاسیک", "سنگ", "چوب", "آجر", "نور", "نرده", "پنجره", "درخت")) and not has_2d_plan_cmd:
            return True
    return False


def is_architectural_design_prompt(text: str) -> bool:
    s = normalize_persian_text(text).lower()
    if "فقط عناصر قابل مشاهده" in s or "observation only" in s:
        return False
    if is_3d_render_or_render_edit_prompt(s):
        return True
    keywords = (
        "طراحی", "پلان", "ساختمان", "ساخامن", "ویلایی", "ویلا", "دوبلکس", "طبقه",
        "حیاط خلوت", "حیا خلوت", "پاسیو", "نورگیر", "سطح اشغال", "محل احداث",
        "مسکونی", "تجاری", "زیرزمین", "پارکینگ", "زمین", "کوچه", "پلاک", "مطبخ", "آشپزخانه", "کروکی",
    )
    return any(k in s for k in keywords)


def is_new_plan_creation_prompt(text: str) -> bool:
    """
    Returns True when the user is requesting a NEW architectural plan design (e.g.
    "یک ساختمان ویلایی با 150 متر مربع در زمینی به مساحت 250 متر مربع در شمال زمین ساختمان را طراحی کن",
    "پلان دوبلکس ۵۵٪ جنوب",
    "روی این کروکی یک ساختمان ۳ طبقه طراحی کن") rather than editing a single element of an existing plan.
    """
    s = normalize_persian_text(text).lower()
    if is_3d_render_or_render_edit_prompt(s):
        return False

    has_explicit_edit_target = any(
        w in s
        for w in (
            "بزرگتر", "بزرگ‌تر", "کوچکتر", "کوچک‌تر", "حذف کن", "حذف و", "تبدیلش کن", "تبدیل کن",
            "به جاش", "بجاش", "جابجا کن", "عوض کن", "تغییر بده", "اصلاح کن",
            "بچرخون", "بچرخان", "چرخش", "قرینه کن", "برعکس کن", "سمت جنوب باشن", "سمت شمال باشن",
            "راهرو کنار", "به اتاق خواب اضافه", "مستر کن",
        )
    )

    has_site_spec = bool(
        re.search(r"(\d+(?:\.\d+)?)\s*(?:\*|در)\s*(\d+(?:\.\d+)?)", s)
        or re.search(r"(?:زمین|زمینی|قطعه|پلاک|کروکی|ملک).*?(\d+)\s*متر", s)
        or "روی این زمین" in s
        or "روی این کروکی" in s
        or "در این زمین" in s
        or "پلان جدید" in s
        or "از اول طراحی" in s
    )
    has_new_building_request = (
        ("طراحی کن" in s or "بکش" in s or "ترسیم کن" in s or "طراحی شود" in s or s.startswith("پلان") or "دوبلکس" in s or "ویلایی" in s)
        and any(w in s for w in ("ساختمان", "ساخامن", "خانه", "پلان", "ویلا", "دوبلکس", "اپارتمان", "آپارتمان"))
        and not has_explicit_edit_target
    )
    return has_site_spec or has_new_building_request


def is_plan_modification_prompt(text: str) -> bool:
    """
    Detects follow-up conversational requests to modify the active floor plan across unlimited turns.
    Crucially returns False if `is_new_plan_creation_prompt(text)` is True so new design prompts
    never get stuck editing the previous building!
    """
    s = normalize_persian_text(text).lower()
    if is_new_plan_creation_prompt(s):
        return False
    if is_3d_render_or_render_edit_prompt(s):
        return True
    edit_action_keywords = (
        "بزرگتر", "بزرگ‌تر", "بزرگ تر", "کوچکتر", "کوچک‌تر", "کوچک تر",
        "عوض کن", "تغییر بده", "اصلاح کن", "اضافه کن", "کم کن", "حذف کن", "بردار",
        "جابجا کن", "به جاش", "بجاش", "بزار", "بذار", "تبدیل کن",
        "وید", "نشیمن خصوصی", "مطبخ", "آشپزخانه", "پذیرایی", "اتاق خواب", "خواب مستر",
        "سرویس", "حمام", "پله", "حیاط خلوت", "پاسیو", "تراس", "بالکن", "ستون",
        "دوبلکسش کن", "ویلایی کن", "یک طبقه کن", "متفاوت",
        "بچرخون", "بچرخان", "چرخش", "قرینه", "برعکس", "مینی بار", "مینی‌بار",
        "تبدیلش کن", "تبدیل کن", "سمت جنوب", "سمت شمال", "تامین کن", "نور اتاق",
        "در جنوب", "تو جنوب", "جنوب ملک", "در شمال", "تو شمال", "شمال ملک", "در شرق", "تو شرق", "شرق ملک", "شرق زمین", "در غرب", "تو غرب", "غرب ملک", "غرب زمین", "شرقی غربی", "از معبر بگیر", "از معبر تامین", "حذف حیاط خلوت", "حذف پاسیو", "حیاط خلوت رو حذف", "حیاط خلوت را حذف",
    )
    return any(k in s for k in edit_action_keywords)


def _extract_site_and_building_areas(s: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Extracts `(site_area_m2, building_area_m2)` from Persian prompts like:
      - "یک ساختمان دوبلکس مدرن به مساحت 120 مترمربع در قطعه زمین 200 مترمربع در شمال زمین طراحی کن"
      - "یک ساختمان ویلایی با 150 متر مربع در زمینی به مساحت 250 متر مربع در شمال زمین ساختمان را طراحی کن"
      - "زمین 300 متری با زیربنای 180 متر"
    """
    site_area: Optional[float] = None
    bldg_area: Optional[float] = None

    # 1. Look for explicit site area (`در قطعه زمین 200 مترمربع`, `در زمینی به مساحت 250 متر مربع`, `زمین 300 متری`)
    m_site = re.search(
        r"(?:قطعه\s*زمین|زمینی\s*به\s*مساحت|زمین\s*به\s*مساحت|مساحت\s*زمین|در\s*زمین|زمین)\s*(\d+(?:\.\d+)?)\s*(?:متر\s*مربع|مترمربع|متری|متر)",
        s,
    )
    if m_site:
        site_area = float(m_site.group(1))

    # 2. Look for building footprint / area (`ساختمان ... به مساحت 120 مترمربع`, `ساختمان ... با 150 متر مربع`, `زیربنای 150 متر`)
    # Remove the matched site substring first so we don't match the site number twice
    s_without_site = s[:m_site.start()] + " " + s[m_site.end():] if m_site else s
    m_bldg = re.search(
        r"(?:به\s*مساحت|بمساحت|با\s*مساحت|بامساحت|زیربنا(?:ی)?|سطح\s*اشغال|بنا(?:ی)?|با)\s*(\d+(?:\.\d+)?)\s*(?:متر\s*مربع|مترمربع|متری|متر)",
        s_without_site,
    )
    if m_bldg:
        val = float(m_bldg.group(1))
        if val >= 40.0:
            bldg_area = val

    return site_area, bldg_area


def _extract_bedroom_count(s: str) -> Optional[int]:
    m_num = re.search(r"(\d+)\s*(?:اتاق\s*خواب|خوابه|خواب)", s)
    if m_num:
        return max(1, min(6, int(m_num.group(1))))
    for w_fa, n_val in _WORD_TO_INT.items():
        if re.search(rf"\b{w_fa}\s*(?:اتاق\s*خواب|خوابه|خواب)\b", s):
            return n_val
    return None


def parse_architectural_prompt(
    text: str,
    active_site_krocki: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    s = normalize_persian_text(text)
    sl = s.lower()

    # 1. Start from Krocki dimensions if an uploaded CAD Krocki is active in the session
    width_m = float(active_site_krocki.get("width_m", 10.0)) if active_site_krocki else 10.0
    length_m = float(active_site_krocki.get("length_m", 20.0)) if active_site_krocki else 20.0
    site_area_m2 = float(active_site_krocki.get("site_area_m2", width_m * length_m)) if active_site_krocki else None

    is_east_west_prompt = any(
        k in sl
        for k in (
            "شرقی غربی", "شرقی-غربی", "شرقی و غربی",
            "در شرق", "تو شرق", "شرق زمین", "شرق ملک", "ضلع شرق", "ضلع شرقی", "بخش شرق", "سمت شرق زمین",
            "در غرب", "تو غرب", "غرب زمین", "غرب ملک", "ضلع غرب", "ضلع غربی", "بخش غرب", "سمت غرب زمین",
        )
    ) and not ("خواب" in sl and ("شرق" in sl or "غرب" in sl))

    # Check explicit W x L in prompt (overrides default if user typed e.g. `12*25` or `10 در 20`)
    m_dim = re.search(r"(\d+(?:\.\d+)?)\s*(?:[\*\-]|در)\s*(\d+(?:\.\d+)?)", s)
    explicit_wl = False
    if m_dim:
        a, b = float(m_dim.group(1)), float(m_dim.group(2))
        if a >= 5.0 and b >= 5.0:
            if is_east_west_prompt:
                width_m, length_m = max(a, b), min(a, b)
            else:
                width_m, length_m = min(a, b), max(a, b)
            site_area_m2 = round(width_m * length_m, 2)
            explicit_wl = True
    else:
        m_w = re.search(r"(?:عرض\s*(?:زمین|ملک|پلاک|قطعه)|شمال و جنوب\s*(?:زمین)?)\s*(\d+(?:\.\d+)?)\s*متر", s)
        m_l = re.search(r"(?:طول\s*(?:زمین|ملک|پلاک|قطعه)|شرق و غرب\s*(?:زمین)?)\s*(\d+(?:\.\d+)?)\s*متر", s)
        if m_w and float(m_w.group(1)) >= 5.0:
            width_m = float(m_w.group(1))
            explicit_wl = True
        if m_l and float(m_l.group(1)) >= 5.0:
            length_m = float(m_l.group(1))
            explicit_wl = True

    # 2. Extract site area & building footprint area in m² (e.g. `با 150 متر مربع در زمینی به مساحت 250 متر مربع`)
    parsed_site_area, parsed_bldg_area = _extract_site_and_building_areas(s)
    if parsed_site_area and parsed_site_area >= 70.0 and not explicit_wl and not active_site_krocki:
        site_area_m2 = parsed_site_area
        # Derive clean architectural parcel dimensions W x L whose product equals `parsed_site_area`:
        # Standard Iranian urban lots have frontage 10m..14m and depth 18m..30m (aspect ~1:2).
        if abs(parsed_site_area - 200.0) <= 1.0:
            width_m, length_m = 10.0, 20.0
        elif abs(parsed_site_area - 250.0) <= 1.0:
            width_m, length_m = 10.0, 25.0
        elif abs(parsed_site_area - 300.0) <= 1.0:
            width_m, length_m = 12.0, 25.0
        else:
            width_m = round(max(8.0, min(16.0, math.sqrt(parsed_site_area / 2.0))), 2)
            length_m = round(parsed_site_area / width_m, 2)

    effective_site_area = site_area_m2 or (width_m * length_m)

    # 3. Coverage ratio (%) & Explicit Building Footprint Area (`parsed_bldg_area`)
    coverage_ratio = 0.60
    m_cov = re.search(r"(\d+(?:\.\d+)?)\s*(?:درصد|%|٪)", s)
    if m_cov:
        val = float(m_cov.group(1))
        if 10 <= val <= 100:
            coverage_ratio = round(val / 100.0, 2)
    if parsed_bldg_area is not None:
        # If the user explicitly stated a building footprint area (e.g. "بمساحت 100 متر مربع در 60 درصد شمالی زمین"),
        # always honor the exact requested building area (`100 m2`) rather than letting `60%` overwrite it to `120 m2`!
        if not parsed_site_area and not explicit_wl and not active_site_krocki and parsed_bldg_area > 150.0:
            effective_site_area = round(parsed_bldg_area / coverage_ratio, 1)
            width_m = round(max(9.0, min(15.0, math.sqrt(effective_site_area / 2.0))), 2)
            length_m = round(effective_site_area / width_m, 2)
        ratio = parsed_bldg_area / max(50.0, effective_site_area)
        coverage_ratio = round(max(0.10, min(1.00, ratio)), 3)

    # 4. Building Placement ("NORTH", "SOUTH", "EAST", "WEST", "CENTER")
    has_east_placement = (
        any(p in sl for p in (
            "در شرق", "تو شرق", "شرق ملک", "شرق زمین", "ضلع شرق", "ضلع شرقی", "بخش شرق", "قسمت شرق",
            "محل احداث در شرق", "محل احداث تو شرق", "ساخت در شرق", "اشغال در شرق", "طراحی در شرق",
            "احداث در شرق", "استقرار در شرق", "ببر شرق", "به شرق",
        ))
        or bool(re.search(r"(?:پلان|ساختمان|ویلا|دوبلکس|اشغال|\d+٪|\d+%).*?شرق(?!ی غربی)", sl))
    ) and not ("خواب" in sl and "شرق" in sl)
    has_west_placement = (
        any(p in sl for p in (
            "در غرب", "تو غرب", "غرب ملک", "غرب زمین", "ضلع غرب", "ضلع غربی", "بخش غرب", "قسمت غرب",
            "محل احداث در غرب", "محل احداث تو غرب", "ساخت در غرب", "اشغال در غرب", "طراحی در غرب",
            "احداث در غرب", "استقرار در غرب", "ببر غرب", "به غرب",
        ))
        or bool(re.search(r"(?:پلان|ساختمان|ویلا|دوبلکس|اشغال|\d+٪|\d+%).*?غرب", sl))
    ) and not ("خواب" in sl and "غرب" in sl) and "شرقی غربی" not in sl and "شرقی-غربی" not in sl
    has_south_placement = (
        any(p in sl for p in (
            "در جنوب", "تو جنوب", "جنوب ملک", "جنوب زمین", "ضلع جنوب", "بخش جنوب", "قسمت جنوب",
            "محل احداث در جنوب", "محل احداث تو جنوب", "ساخت در جنوب", "اشغال در جنوب", "طراحی در جنوب",
            "احداث در جنوب", "استقرار در جنوب", "ببر جنوب", "برو جنوب", "به جنوب",
        ))
        or bool(re.search(r"(?:پلان|ساختمان|ویلا|دوبلکس|اشغال|\d+٪|\d+%).*?جنوب", sl))
        or sl.strip().endswith("جنوب")
    ) and not ("خواب" in sl and "سمت جنوب" in sl and "پذیرایی" in sl)
    has_center_placement = any(p in sl for p in ("محل احداث در وسط", "محل احداث در میانه", "وسط زمین", "مرکز زمین", "در وسط", "میانه زمین"))
    has_north_placement = any(p in sl for p in (
        "در شمال", "تو شمال", "شمال ملک", "شمال زمین", "ضلع شمال", "بخش شمال", "قسمت شمال",
        "محل احداث در شمال", "محل احداث تو شمال", "ساخت در شمال", "اشغال در شمال", "طراحی در شمال",
    ))
    if has_east_placement:
        placement = "EAST"
    elif has_west_placement:
        placement = "WEST"
    elif has_south_placement:
        placement = "SOUTH"
    elif has_center_placement:
        placement = "CENTER"
    elif has_north_placement:
        placement = "NORTH"
    elif is_east_west_prompt or (active_site_krocki and float(active_site_krocki.get("width_m", 10.0)) > float(active_site_krocki.get("length_m", 20.0)) * 1.25):
        placement = "EAST"
    else:
        placement = "NORTH"

    if placement in ("EAST", "WEST") and width_m < length_m and not active_site_krocki:
        width_m, length_m = length_m, width_m

    # 5. Smart Backyard / Lightwell Detection:
    # Rule: When the building edge faces a Street (`معبر`) or internal Courtyard (`حیاط`), rooms get direct natural light
    # from the street/courtyard so NO lightwell (`حیاط خلوت`) is needed unless explicitly requested!
    krocki_streets = set((active_site_krocki or {}).get("street_sides") or [])
    krocki_b_neigh = (active_site_krocki or {}).get("boundary_neighbors") or {}
    explicit_want_lw = any(k in sl for k in ("با حیاط خلوت", "با پاسیو", "حیاط خلوت در", "پاسیو در", "دارای حیاط خلوت"))
    explicit_no_lw = any(k in sl for k in ("بدون پاسیو", "بدون حیاط خلوت", "حذف پاسیو", "حذف حیاط خلوت", "نیازی به حیاط خلوت ندار", "حیاط خلوت رو حذف", "حیاط خلوت را حذف"))

    if explicit_no_lw:
        lw_enabled = False
    elif explicit_want_lw:
        lw_enabled = True
    elif placement == "SOUTH":
        # Building in South: North faces North Courtyard, South faces South Street -> direct light on both sides, no lightwell needed!
        lw_enabled = False
    elif placement == "NORTH" and ("NORTH" in krocki_streets or krocki_b_neigh.get("NORTH") == "STREET" or "شمال معبر" in sl or "شمالش کوچه" in sl or "شمال ملک معبر" in sl):
        # Building in North AND North is a Street (`معبر شمالی`): direct light from North Street -> no lightwell needed!
        lw_enabled = False
    elif placement == "EAST" and ("EAST" in krocki_streets or krocki_b_neigh.get("EAST") == "STREET"):
        lw_enabled = False
    elif placement == "WEST" and ("WEST" in krocki_streets or krocki_b_neigh.get("WEST") == "STREET"):
        lw_enabled = False
    else:
        lw_enabled = True
    lw_depth_m = 1.70
    lw_area_m2 = 12.0
    m_depth = re.search(r"عمق\s*(\d+(?:\.\d+)?)\s*متر", s)
    if m_depth:
        lw_depth_m = float(m_depth.group(1))
    m_lw_area = re.search(r"(?:حیاط خلوت|حیا خلوت|پاسیو|نورگیر).*?مساحت\s*(\d+(?:\.\d+)?)\s*متر", s)
    if m_lw_area:
        lw_area_m2 = float(m_lw_area.group(1))

    lw_pos = "NORTH" if placement == "NORTH" else ("SOUTH" if placement == "SOUTH" else "NORTH")

    # 6. Dirty Kitchen (مطبخ / آشپزخانه کثیف)
    include_dirty_kitchen = True
    if "بدون مطبخ" in sl or "بدون آشپزخانه کثیف" in sl or "حذف مطبخ" in sl:
        include_dirty_kitchen = False

    # 7. Typology & Floor Count
    has_basement = any(w in sl for w in ("زیرزمین", "basement"))
    is_duplex = any(w in sl for w in ("دوبلکس", "duplex"))
    is_luxury_pool_duplex = is_duplex and any(w in sl for w in ("استخر", "سایت پلان آزاد", "محوطه سازی", "محوطه‌سازی", "باغ ویلا", "pool"))
    is_mixed = any(w in sl for w in ("مختلط", "تجاری", "mixed", "commercial"))
    is_villa = any(w in sl for w in ("ویلایی", "ویلا", "villa", "یک طبقه", "1 طبقه", "تک طبقه")) and not is_duplex

    m_fl = re.search(r"(\d+)\s*طبقه", s)
    explicit_floors = int(m_fl.group(1)) if m_fl else None
    if explicit_floors is None:
        for w_fa, n_val in _WORD_TO_INT.items():
            if re.search(rf"\b{w_fa}\s*طبقه\b", s):
                explicit_floors = n_val
                break

    if is_duplex:
        typology = BuildingTypology.DUPLEX_2FLOOR
        floor_count = 2
    elif is_mixed:
        typology = BuildingTypology.MIXED_USE_MULTIFLOOR
        floor_count = explicit_floors if (explicit_floors and explicit_floors >= 2) else 3
        has_basement = True
    elif (explicit_floors and explicit_floors >= 2 and not is_villa) or any(w in sl for w in ("چند طبقه", "چندطبقه", "پیلوت", "آپارتمان", "دو طبقه", "سه طبقه")):
        typology = BuildingTypology.MULTIFLOOR_RESIDENTIAL
        floor_count = explicit_floors if (explicit_floors and explicit_floors >= 2) else 2
    elif is_villa:
        typology = BuildingTypology.VILLA_1FLOOR
        floor_count = 1
    else:
        typology = BuildingTypology.VILLA_1FLOOR if (explicit_floors == 1 or not explicit_floors) else BuildingTypology.MULTIFLOOR_RESIDENTIAL
        floor_count = explicit_floors or 1

    # 8. Bedroom count & Void options
    bedroom_count = _extract_bedroom_count(s)
    if bedroom_count is None:
        bedroom_count = 3 if typology == BuildingTypology.DUPLEX_2FLOOR else 2

    remove_duplex_void = bool(
        any(w in sl for w in (" بدون وید", "حذف وید", "وید طبقه بالا را حذف", "وید طبقه بالا رو حذف", "بستن وید"))
    )
    void_replacement_room = "PRIVATE_LIVING"
    if remove_duplex_void and any(w in sl for w in ("اتاق خواب", "خواب")):
        void_replacement_room = "BEDROOM"

    layout_variant = (
        "TYPE_C"
        if (bedroom_count >= 3 or any(k in sl for k in ("تیپ c", "تیپ ۳", "تیپ 3", "سه خواب", "3 خواب", "type c")))
        else (
            "TYPE_B"
            if any(k in sl for k in ("تیپ b", "تیپ ۲", "تیپ 2", "جزیره افقی", "آشپزخانه میانی", "type b"))
            else "TYPE_A"
        )
    )

    # Parse explicit Street Cantilever (`پیش‌آمدگی در معبر`) & Courtyard Cantilever (`پیش‌آمدگی در حیاط`)
    street_cant_mm = 1100
    yard_cant_mm = 0
    m_st_cant = re.search(
        r"(?:پیش\s*آمدگی|پیش‌آمدگی|کنسول)\s*(?:به\s*)?(?:عرض|عمق)?\s*(\d+(?:\.\d+)?)\s*(?:متر|m)?\s*(?:در|سمت|رو\s*به)\s*(?:معبر|کوچه|گذر|خیابان)",
        s,
    )
    if m_st_cant:
        v_c = float(m_st_cant.group(1))
        street_cant_mm = int(round(v_c * 1000)) if v_c < 10.0 else int(round(v_c * 10))
    m_yd_cant = re.search(
        r"(?:پیش\s*آمدگی|پیش‌آمدگی|کنسول)\s*(?:به\s*)?(?:عرض|عمق)?\s*(\d+(?:\.\d+)?)\s*(?:متر|m)?\s*(?:در|سمت|رو\s*به)\s*(?:حیاط|داخل\s*ملک)",
        s,
    )
    if m_yd_cant:
        v_y = float(m_yd_cant.group(1))
        yard_cant_mm = int(round(v_y * 1000)) if v_y < 10.0 else int(round(v_y * 10))

    params: Dict[str, Any] = {
        "raw_prompt": text,
        "site_width_mm": int(round(width_m * 1000)),
        "site_length_mm": int(round(length_m * 1000)),
        "site_area_m2": round(effective_site_area, 2),
        "requested_building_area_m2": round(parsed_bldg_area or (width_m * length_m * coverage_ratio), 2),
        "coverage_ratio": coverage_ratio,
        "building_placement": placement,
        "lightwell_enabled": lw_enabled,
        "lightwell_position": lw_pos,
        "lightwell_depth_mm": int(round(lw_depth_m * 1000)),
        "lightwell_area_m2": lw_area_m2,
        "include_dirty_kitchen": include_dirty_kitchen,
        "typology": typology.value,
        "is_duplex": (typology == BuildingTypology.DUPLEX_2FLOOR),
        "floor_count": floor_count,
        "bedroom_count": bedroom_count,
        "has_basement": has_basement,
        "is_luxury_pool_duplex": is_luxury_pool_duplex,
        "remove_duplex_void": remove_duplex_void,
        "void_replacement_room": void_replacement_room,
        "replace_minibar_with_bedroom": bool("مینی بار" in sl and "حذف" in sl),
        "expand_bed3_over_corridor": bool(any(k in sl for k in ("راهرو کنار", "به اتاق خواب اضافه", "در تراس رو از", "درب تراس را از", "در تراس را از"))),
        "bed3_is_master": bool(any(k in sl for k in ("اتاق خواب را مستر", "اتاق خواب رو مستر", "مستر کن", "خواب 3 را مستر", "خواب ۳ را مستر"))),
        "render_3d_facade_mode": is_3d_render_or_render_edit_prompt(text),
        "render_3d_prompt": text if is_3d_render_or_render_edit_prompt(text) else "",
        "flip_plan_north_south": bool(
            any(w in sl for w in ("پلان رو بچرخون", "پلان را بچرخان", "برعکس کن", "قرینه کن"))
            or (("خواب" in sl and "سمت جنوب" in sl) and ("پذیرایی" in sl or "ورودی" in sl) and "سمت شمال" in sl)
        ),
        "kitchen_extra_width_mm": 0,
        "living_extra_width_mm": 0,
        "terrace_extra_depth_mm": 0,
        "south_cantilever_mm": street_cant_mm,
        "courtyard_cantilever_mm": yard_cant_mm,
        "separation_joint_mm": 50,
        "pilotis_height_mm": 2400,
        "typical_floor_height_mm": 3240,
        "layout_variant": layout_variant,
    }
    if active_site_krocki:
        params["krocki_polygon_mm"] = active_site_krocki.get("polygon_vertices_mm") or []
        params["krocki_source_file"] = active_site_krocki.get("source_file")
        params["krocki_is_irregular"] = bool(active_site_krocki.get("is_irregular_polygon", False))
        params["krocki_parcel_number"] = active_site_krocki.get("parcel_number")
        params["street_sides"] = active_site_krocki.get("street_sides") or ["SOUTH"]
        params["party_wall_sides"] = active_site_krocki.get("party_wall_sides") or ["NORTH", "EAST", "WEST"]
        params["boundary_neighbors"] = active_site_krocki.get("boundary_neighbors") or {"NORTH": "NEIGHBOR_LOT", "EAST": "NEIGHBOR_LOT", "SOUTH": "STREET", "WEST": "NEIGHBOR_LOT"}
        params["boundary_labels_fa"] = active_site_krocki.get("boundary_labels_fa") or {}
        params["south_y_west_mm"] = int(active_site_krocki.get("south_y_west_mm", 0))
        params["south_y_east_mm"] = int(active_site_krocki.get("south_y_east_mm", 0))
        params["north_y_west_mm"] = int(active_site_krocki.get("north_y_west_mm", int(round(length_m * 1000))))
        params["north_y_east_mm"] = int(active_site_krocki.get("north_y_east_mm", int(round(length_m * 1000))))
    if params.get("render_3d_facade_mode"):
        r_st = update_geometry_locked_render_state(None, text, params)
        params["active_render_state"] = r_st
        params["render_facade_side"] = r_st["facade_side"]
        params["facade_style_fa"] = r_st["style_label_fa"]
        params["facade_material_fa"] = r_st["stone_label_fa"]
        params["render_lighting_mode"] = r_st["lighting_mode"]
    return params


def apply_incremental_plan_edit(
    prev_params: Dict[str, Any],
    edit_prompt: str,
    active_site_krocki: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Applies unlimited consecutive user edits (`وید طبقه بالا رو حذف کن و یه نشیمن خصوصی به جاش بزار`,
    `آشپزخانه را بزرگتر کن`, `پذیرایی را بزرگتر کن`, `۳ خوابه کن`, `یک طبقه ویلایی کن`, etc.)
    onto `prev_params` and returns the updated parameter dictionary for immediate re-synthesis.
    """
    s = normalize_persian_text(edit_prompt)
    sl = s.lower()

    # If the user actually typed a brand-new building/site design request, start fresh from parse_architectural_prompt!
    if not prev_params or is_new_plan_creation_prompt(s):
        return parse_architectural_prompt(edit_prompt, active_site_krocki=active_site_krocki)

    merged = copy.deepcopy(prev_params)
    if active_site_krocki:
        merged["site_width_mm"] = int(round(float(active_site_krocki.get("width_m", 10.0)) * 1000))
        merged["site_length_mm"] = int(round(float(active_site_krocki.get("length_m", 20.0)) * 1000))
        merged["site_area_m2"] = round(float(active_site_krocki.get("site_area_m2", 200.0)), 2)
        merged["krocki_polygon_mm"] = active_site_krocki.get("polygon_vertices_mm") or []
        merged["krocki_source_file"] = active_site_krocki.get("source_file")
        merged["krocki_is_irregular"] = bool(active_site_krocki.get("is_irregular_polygon", False))
        merged["krocki_parcel_number"] = active_site_krocki.get("parcel_number")
        merged["street_sides"] = active_site_krocki.get("street_sides") or ["SOUTH"]
        merged["party_wall_sides"] = active_site_krocki.get("party_wall_sides") or ["NORTH", "EAST", "WEST"]
        merged["boundary_neighbors"] = dict(active_site_krocki.get("boundary_neighbors") or {"NORTH": "NEIGHBOR_LOT", "EAST": "NEIGHBOR_LOT", "SOUTH": "STREET", "WEST": "NEIGHBOR_LOT"})
        merged["south_y_west_mm"] = int(active_site_krocki.get("south_y_west_mm", 0))
        merged["south_y_east_mm"] = int(active_site_krocki.get("south_y_east_mm", 0))
        merged["north_y_west_mm"] = int(active_site_krocki.get("north_y_west_mm", merged["site_length_mm"]))
        merged["north_y_east_mm"] = int(active_site_krocki.get("north_y_east_mm", merged["site_length_mm"]))
    merged["raw_prompt"] = f"{merged.get('raw_prompt', '')} | EDIT: {edit_prompt}".strip(" |")
    merged["edit_revision"] = int(merged.get("edit_revision", 0)) + 1
    applied_changes: list[str] = []

    # 0. v33.0 CRITICAL GEOMETRY LOCK FOR 3D FACADE RENDER & ITERATIVE RENDER EDITS:
    # When the user requests a 3D render of the active plan OR asks for iterative changes to the render
    # (e.g., changing day/night lighting, changing facade style between Neoclassical/Modern, changing stone color or thermowood,
    # or changing balustrades), we freeze 100% of the 2D floor plan & 3D building massing/openings and ONLY update `active_render_state`!
    if is_3d_render_or_render_edit_prompt(edit_prompt, prev_params):
        merged["render_3d_facade_mode"] = True
        merged["render_3d_prompt"] = edit_prompt
        r_state = update_geometry_locked_render_state(merged.get("active_render_state"), edit_prompt, merged)
        merged["active_render_state"] = r_state
        merged["render_facade_side"] = r_state["facade_side"]
        merged["facade_style_fa"] = r_state["style_label_fa"]
        merged["facade_material_fa"] = r_state["stone_label_fa"]
        merged["render_lighting_mode"] = r_state["lighting_mode"]
        merged["last_edit_summary_fa"] = (
            f"رندر سه‌بعدی {r_state['facade_label_fa']} با قفل ۱۰۰٪ فرم، حجم و بازشوهای پلان به‌روزرسانی شد: "
            f"{r_state['style_label_fa']} | نورپردازی: {r_state['time_label_fa']}"
        )
        return merged
    else:
        merged["render_3d_facade_mode"] = False

    # 1. Check if new explicit site dimensions or areas were given
    m_dim = re.search(r"(\d+(?:\.\d+)?)\s*(?:[\*\-]|در)\s*(\d+(?:\.\d+)?)", s)
    if m_dim:
        a, b = float(m_dim.group(1)), float(m_dim.group(2))
        if a >= 5.0 and b >= 5.0:
            merged["site_width_mm"] = int(round(min(a, b) * 1000))
            merged["site_length_mm"] = int(round(max(a, b) * 1000))
            merged["site_area_m2"] = round(min(a, b) * max(a, b), 2)
            applied_changes.append(f"ابعاد زمین به {min(a,b):g}×{max(a,b):g}m تغییر یافت")

    parsed_site_area, parsed_bldg_area = _extract_site_and_building_areas(s)
    if parsed_site_area and parsed_site_area >= 70.0:
        w_m = round(max(8.0, min(16.0, math.sqrt(parsed_site_area / 2.0))), 2)
        if abs(parsed_site_area - 200.0) <= 1.0:
            w_m = 10.0
        elif abs(parsed_site_area - 250.0) <= 1.0:
            w_m = 10.0
        elif abs(parsed_site_area - 300.0) <= 1.0:
            w_m = 12.0
        l_m = round(parsed_site_area / w_m, 2)
        merged["site_width_mm"] = int(round(w_m * 1000))
        merged["site_length_mm"] = int(round(l_m * 1000))
        merged["site_area_m2"] = round(parsed_site_area, 2)
        applied_changes.append(f"مساحت زمین به {parsed_site_area:g}m² ({w_m:g}×{l_m:g}m) تغییر یافت")

    # 2. Check coverage ratio or building footprint area update
    m_cov = re.search(r"(\d+(?:\.\d+)?)\s*(?:درصد|%|٪)", s)
    if parsed_bldg_area is not None:
        site_a = (merged["site_width_mm"] / 1000.0) * (merged["site_length_mm"] / 1000.0)
        merged["coverage_ratio"] = round(max(0.10, min(1.00, parsed_bldg_area / max(50.0, site_a))), 3)
        merged["requested_building_area_m2"] = parsed_bldg_area
        applied_changes.append(f"مساحت زیربنا به {parsed_bldg_area:g}m² (سطح اشغال {int(round(merged['coverage_ratio']*100))}٪) تغییر یافت")
    elif m_cov:
        val = float(m_cov.group(1))
        if 10 <= val <= 100:
            merged["coverage_ratio"] = round(val / 100.0, 2)
            site_a = (merged["site_width_mm"] / 1000.0) * (merged["site_length_mm"] / 1000.0)
            merged["requested_building_area_m2"] = round(site_a * merged["coverage_ratio"], 1)
            applied_changes.append(f"سطح اشغال به {int(val)}٪ تغییر یافت")
    if False:
        site_a = (merged["site_width_mm"] / 1000.0) * (merged["site_length_mm"] / 1000.0)
        merged["coverage_ratio"] = round(max(0.10, min(1.00, parsed_bldg_area / max(50.0, site_a))), 2)
        merged["requested_building_area_m2"] = parsed_bldg_area
        applied_changes.append(f"مساحت زیربنا به {parsed_bldg_area:g}m² (سطح اشغال {int(merged['coverage_ratio']*100)}٪) تغییر یافت")

    # 3. Check Duplex Void Removal / Replacement (`وید طبقه بالا رو حذف کن و یه نشیمن خصوصی به جاش بزار`)
    if "وید" in sl or "void" in sl:
        if any(w in sl for w in ("حذف", "بردار", "ببند", "نباشه", "بدون", "به جاش", "بجاش", "تبدیل")):
            merged["remove_duplex_void"] = True
            if any(w in sl for w in ("خواب", "اتاق")):
                merged["void_replacement_room"] = "BEDROOM"
                applied_changes.append("وید طبقه بالا حذف شد و اتاق خواب جدید جایگزین آن گردید")
            else:
                merged["void_replacement_room"] = "PRIVATE_LIVING"
                applied_changes.append("وید طبقه بالا حذف شد و نشیمن خصوصی طبقه اول جایگزین آن گردید")
        elif any(w in sl for w in ("اضافه", "برگردون", "بزار", "ایجاد")) and "به جاش" not in sl and "بجاش" not in sl:
            merged["remove_duplex_void"] = False
            applied_changes.append("وید دوبلکس در طبقه بالا بازگردانی شد")

    # 4. Check Kitchen expansion / reduction (`آشپزخانه رو بزرگتر کن`)
    if any(k in sl for k in ("آشپزخانه", "kitchen")) and "کثیف" not in sl:
        cur_k = int(merged.get("kitchen_extra_width_mm", 0))
        if any(w in sl for w in ("بزرگتر", "بزرگ‌تر", "بزرگ تر", "وسیع", "بیشتر", "اضافه")):
            merged["kitchen_extra_width_mm"] = min(1100, cur_k + 500)
            applied_changes.append("عرض و مساحت آشپزخانه افزایش یافت")
        elif any(w in sl for w in ("کوچکتر", "کوچک‌تر", "کوچک تر", "کمتر")):
            merged["kitchen_extra_width_mm"] = max(-600, cur_k - 400)
            applied_changes.append("عرض و مساحت آشپزخانه کاهش یافت")

    # 5. Check Living / Reception Hall expansion / reduction (`پذیرایی / نشیمن رو بزرگتر کن`)
    if any(k in sl for k in ("پذیرایی", "نشیمن", "سالن")) and "وید" not in sl:
        cur_l = int(merged.get("living_extra_width_mm", 0))
        if any(w in sl for w in ("بزرگتر", "بزرگ‌تر", "بزرگ تر", "وسیع", "بیشتر")):
            merged["living_extra_width_mm"] = min(900, cur_l + 450)
            merged["kitchen_extra_width_mm"] = max(-600, int(merged.get("kitchen_extra_width_mm", 0)) - 350)
            applied_changes.append("سالن پذیرایی و نشیمن بزرگ‌تر شد")
        elif any(w in sl for w in ("کوچکتر", "کوچک‌تر", "کوچک تر", "کمتر")):
            merged["living_extra_width_mm"] = max(-600, cur_l - 400)
            applied_changes.append("سالن پذیرایی کوچک‌تر شد")

    # 6. Check Terrace / Balcony modifications (`تراس رو بزرگتر کن / حذف کن`)
    if any(k in sl for k in ("تراس", "بالکن", "ایوان")):
        cur_t = int(merged.get("terrace_extra_depth_mm", 0))
        if any(w in sl for w in ("بزرگتر", "بزرگ‌تر", "بزرگ تر", "بیشتر", "عمیق")):
            merged["terrace_extra_depth_mm"] = min(900, cur_t + 400)
            applied_changes.append("عمق تراس جنوبی افزایش یافت")
        elif any(w in sl for w in ("کوچکتر", "کوچک‌تر", "کوچک تر", "کمتر")):
            merged["terrace_extra_depth_mm"] = max(-500, cur_t - 350)
            applied_changes.append("عمق تراس جنوبی کاهش یافت")

    # 7. Check Lightwell / Backyard changes (`حیاط خلوت / پاسیو`)
    if any(k in sl for k in ("حیاط خلوت", "حیا خلوت", "پاسیو", "نورگیر")):
        m_depth = re.search(r"عمق\s*(\d+(?:\.\d+)?)\s*متر", s)
        m_area = re.search(r"مساحت\s*(\d+(?:\.\d+)?)\s*متر", s)
        if m_depth:
            merged["lightwell_depth_mm"] = int(round(float(m_depth.group(1)) * 1000))
        if m_area:
            merged["lightwell_area_m2"] = float(m_area.group(1))
        if any(w in sl for w in ("بزرگتر", "بزرگ‌تر", "بزرگ تر")) and not (m_depth or m_area):
            merged["lightwell_depth_mm"] = int(merged.get("lightwell_depth_mm", 1700)) + 350
            merged["lightwell_area_m2"] = float(merged.get("lightwell_area_m2", 12.0)) + 3.0
            applied_changes.append("عمق و مساحت حیاط خلوت افزایش یافت")
        if "حذف" in sl or "بدون" in sl:
            merged["lightwell_enabled"] = False
            applied_changes.append("حیاط خلوت حذف شد")
        elif "اضافه" in sl:
            merged["lightwell_enabled"] = True
            applied_changes.append("حیاط خلوت اضافه شد")

    # 8. Check Dirty Kitchen (`مطبخ`) toggle
    if "مطبخ" in sl or "آشپزخانه کثیف" in sl:
        if "حذف" in sl or "بدون" in sl:
            merged["include_dirty_kitchen"] = False
            applied_changes.append("مطبخ (آشپزخانه کثیف) حذف شد")
        elif "اضافه" in sl or "با مطبخ" in sl:
            merged["include_dirty_kitchen"] = True
            applied_changes.append("مطبخ (آشپزخانه کثیف) اضافه شد")

    # 9. Check Bedroom count changes (`۳ خوابه کن`, `یک خواب اضافه کن`) — excluding "به اتاق خواب اضافه کن"
    is_corridor_to_bed_merge = any(k in sl for k in ("راهرو کنار", "فضای راهرو", "به اتاق خواب اضافه", "به خواب اضافه", "در تراس رو از", "درب تراس را از", "در تراس را از"))
    new_beds = None if is_corridor_to_bed_merge else _extract_bedroom_count(s)
    if new_beds is not None:
        merged["bedroom_count"] = new_beds
        if new_beds >= 3:
            merged["layout_variant"] = "TYPE_C"
        applied_changes.append(f"تعداد اتاق‌های خواب به {new_beds} خواب تغییر یافت")
    elif "خواب" in sl and "اضافه" in sl and "وید" not in sl and not is_corridor_to_bed_merge:
        merged["bedroom_count"] = min(4, int(merged.get("bedroom_count", 2)) + 1)
        if merged["bedroom_count"] >= 3:
            merged["layout_variant"] = "TYPE_C"
        applied_changes.append(f"یک اتاق خواب اضافه شد ({merged['bedroom_count']} خواب)")

    # 10a. Check Plan North-South Zone Flip / Rotation (`پلان رو بچرخون اتاق خوابها سمت جنوب باشن پذیرایی و ناهارخوری و ورودی ساختمان سمت شمال باشن`)
    is_zone_flip_cmd = bool(
        any(w in sl for w in ("بچرخون", "بچرخان", "چرخش پلان", "برعکس کن", "قرینه کن", "جای خواب و پذیرایی"))
        or (("خواب" in sl and ("سمت جنوب" in sl or "در جنوب" in sl or "جنوب ساختم" in sl)) and any(w in sl for w in ("پذیرایی", "ناهارخوری", "ورودی")))
        or (("پذیرایی" in sl or "ورودی" in sl) and ("سمت شمال" in sl or "شمال ساختم" in sl))
    )
    if is_zone_flip_cmd:
        if ("خواب" in sl and "جنوب" in sl) or ("پذیرایی" in sl and "شمال" in sl):
            merged["flip_plan_north_south"] = True
        else:
            merged["flip_plan_north_south"] = not bool(merged.get("flip_plan_north_south", False))
        applied_changes.append("پلان ۱۸۰ درجه چرخانده شد (ورودی، پذیرایی و ناهارخوری در ضلع شمال ساختمان و اتاق‌های خواب در ضلع جنوب ساختمان قرار گرفتند)")

    # 10b. Check Mini-Bar & Terrace -> Bedroom 3 Conversion (`تراس و مینی بار طبقه بالا رو حذف و تبدیلش کن به اتاق خواب`)
    if any(w in sl for w in ("مینی بار", "مینی‌بار", "کافی بار", "کافی‌بار", "تراس مسقف")) or ("تراس" in sl and ("خواب" in sl or "تبدیل" in sl) and not is_corridor_to_bed_merge):
        if any(w in sl for w in ("حذف", "تبدیل", "به جاش", "بجاش", "اتاق خواب", "خواب")):
            merged["replace_minibar_with_bedroom"] = True
            applied_changes.append("مینی‌بار و تراس مسقف طبقه اول حذف شد و به اتاق خواب سوم تبدیل گردید")
        elif any(w in sl for w in ("اضافه", "برگردون")):
            merged["replace_minibar_with_bedroom"] = False
            applied_changes.append("مینی‌بار و تراس مسقف طبقه اول بازگردانی شد")

    # 10b-2. Check Expanding Bedroom 3 over Adjacent Corridor + Opening Terrace Door from Bedroom 3 + Making Bedroom 3 Master
    if is_corridor_to_bed_merge or any(w in sl for w in ("راهرو کنار", "به اتاق خواب اضافه", "در تراس رو از داخل اتاق", "در تراس را از داخل اتاق", "اتاق خواب را مستر", "اتاق خواب رو مستر", "خواب 3 را مستر", "خواب ۳ را مستر", "مستر کن")):
        merged["replace_minibar_with_bedroom"] = True
        if is_corridor_to_bed_merge or any(w in sl for w in ("راهرو", "در تراس", "درب تراس")):
            merged["expand_bed3_over_corridor"] = True
            applied_changes.append("فضای راهرو کنار اتاق خواب ۳ حذف و به مساحت اتاق خواب ۳ الحاق شد و درب تراس مستقیماً از داخل اتاق خواب ۳ باز گردید")
        if any(w in sl for w in ("مستر", "حمام اختصاصی", "سرویس مستر")):
            merged["bed3_is_master"] = True
            merged["expand_bed3_over_corridor"] = True
            applied_changes.append("اتاق خواب ۳ به مستر روم (دارای حمام و سرویس مستر اختصاصی) تبدیل شد")

    # 10e. Check 3D Facade / Perspective Render Request on the Active Plan
    is_3d_render_req = any(k in sl for k in ("رندر", "render", "پرسپکتیو", "ریسپکتیو", "نمای شمالی", "نمای جنوبی")) and "طراحی کن" not in sl
    merged["render_3d_facade_mode"] = bool(is_3d_render_req)
    if is_3d_render_req:
        merged["render_3d_prompt"] = edit_prompt
        applied_changes.append(f"تولید رندر سه‌بعدی نما منطبق با پلان فعال ({edit_prompt})")

    # 10c. Check User Declaring a Street on North/East/West (`در شمال قطعه معبر داریم ... نور اتاق خواب هارو از ضلع شمال تامین کن`)
    if any(w in sl for w in ("معبر", "کوچه", "خیابان", "نور اتاق")):
        st_list = list(merged.get("street_sides") or ["SOUTH"])
        b_map = dict(merged.get("boundary_neighbors") or {"NORTH": "NEIGHBOR_LOT", "EAST": "NEIGHBOR_LOT", "SOUTH": "STREET", "WEST": "NEIGHBOR_LOT"})
        for side_k, fa_k in (("NORTH", "شمال"), ("EAST", "شرق"), ("WEST", "غرب"), ("SOUTH", "جنوب")):
            if fa_k in sl and any(w in sl for w in ("معبر", "کوچه", "خیابان", "نور")):
                if side_k not in st_list:
                    st_list.append(side_k)
                b_map[side_k] = "STREET"
        merged["street_sides"] = st_list
        merged["party_wall_sides"] = [s for s in ("NORTH", "EAST", "SOUTH", "WEST") if s not in st_list]
        merged["boundary_neighbors"] = b_map

    # 10d. Check Building Placement (`شمال زمین / جنوب زمین / وسط زمین` — only when not flipping internal room zones!)
    if not is_zone_flip_cmd:
        if (
            any(p in sl for p in (
                "در جنوب", "تو جنوب", "جنوب ملک", "جنوب زمین", "ضلع جنوب", "بخش جنوب", "قسمت جنوب",
                "محل احداث در جنوب", "محل احداث تو جنوب", "ساخت در جنوب", "اشغال در جنوب", "طراحی در جنوب",
                "احداث در جنوب", "استقرار در جنوب", "ببر جنوب", "برو جنوب", "به جنوب",
            ))
            or bool(re.search(r"(?:پلان|ساختمان|ویلا|دوبلکس|اشغال|\d+٪|\d+%).*?جنوب", sl))
            or sl.strip().endswith("جنوب")
        ) and not ("خواب" in sl and "سمت جنوب" in sl and "پذیرایی" in sl):
            merged["building_placement"] = "SOUTH"
            applied_changes.append("محل احداث ساختمان به جنوب زمین منتقل شد")
        elif any(p in sl for p in ("در وسط زمین", "وسط زمین", "میانه زمین")):
            merged["building_placement"] = "CENTER"
            applied_changes.append("محل احداث ساختمان به میانه زمین منتقل شد")
        elif any(p in sl for p in ("محل احداث در شمال", "ساخت در شمال", "اشغال در شمال", "ضلع شمال زمین", "در شمال زمین", "شمال زمین", "در شمال ملک", "شمال ملک", "ببر شمال")):
            merged["building_placement"] = "NORTH"
            st_sides_m = set(merged.get("street_sides") or [])
            b_neigh_m = merged.get("boundary_neighbors") or {}
            if "NORTH" in st_sides_m or b_neigh_m.get("NORTH") == "STREET":
                merged["lightwell_enabled"] = False
            applied_changes.append("محل احداث ساختمان به شمال زمین منتقل شد")
        elif any(p in sl for p in ("در شرق", "تو شرق", "شرق زمین", "شرق ملک", "ضلع شرق", "ضلع شرقی", "محل احداث در شرق", "ساخت در شرق", "اشغال در شرق", "ببر شرق")) and not ("خواب" in sl and "شرق" in sl):
            merged["building_placement"] = "EAST"
            if int(merged.get("site_width_mm", 10000)) < int(merged.get("site_length_mm", 20000)):
                merged["site_width_mm"], merged["site_length_mm"] = merged["site_length_mm"], merged["site_width_mm"]
            applied_changes.append("محل احداث ساختمان به ضلع شرق زمین منتقل شد")
        elif any(p in sl for p in ("در غرب", "تو غرب", "غرب زمین", "غرب ملک", "ضلع غرب", "ضلع غربی", "محل احداث در غرب", "ساخت در غرب", "اشغال در غرب", "ببر غرب")) and not ("خواب" in sl and "غرب" in sl):
            merged["building_placement"] = "WEST"
            if int(merged.get("site_width_mm", 10000)) < int(merged.get("site_length_mm", 20000)):
                merged["site_width_mm"], merged["site_length_mm"] = merged["site_length_mm"], merged["site_width_mm"]
            applied_changes.append("محل احداث ساختمان به ضلع غرب زمین منتقل شد")

    # 11. Check Typology / Floor count / Variant changes (`پلان متفاوت`, `تیپ B/C`, `دوبلکس`, `ویلایی`, `چند طبقه`)
    if "دوبلکس" in sl:
        merged["typology"] = BuildingTypology.DUPLEX_2FLOOR.value
        merged["floor_count"] = 2
        merged["is_duplex"] = True
        if "استخر" in sl or "محوطه" in sl:
            merged["is_luxury_pool_duplex"] = True
        applied_changes.append("تیپ ساختمان به دوبلکس ۲ طبقه تغییر یافت")
    elif any(w in sl for w in ("ویلایی", "ویلا", "یک طبقه", "1 طبقه", "تک طبقه", "ویلایی تک")) and "دوبلکس" not in sl:
        merged["typology"] = BuildingTypology.VILLA_1FLOOR.value
        merged["floor_count"] = 1
        merged["is_duplex"] = False
        merged["is_luxury_pool_duplex"] = False
        applied_changes.append("تیپ ساختمان به ویلایی تک‌واحدی (یک طبقه) تغییر یافت")

    m_fl = re.search(r"(\d+)\s*طبقه", s)
    if m_fl and "دوبلکس" not in sl and "یک طبقه" not in sl and "1 طبقه" not in sl:
        fl_n = int(m_fl.group(1))
        if fl_n >= 2:
            merged["typology"] = BuildingTypology.MULTIFLOOR_RESIDENTIAL.value
            merged["floor_count"] = fl_n
            merged["is_duplex"] = False
            applied_changes.append(f"تیپ ساختمان به آپارتمان چندطبقه ({fl_n} طبقه مسکونی روی پیلوت) تغییر یافت")

    if any(w in sl for w in ("متفاوت", "تیپ دیگر", "طرح دیگر", "عوض کن", "تغییر بده")) and not applied_changes:
        cur_var = str(merged.get("layout_variant", "TYPE_A"))
        merged["layout_variant"] = "TYPE_B" if cur_var == "TYPE_A" else ("TYPE_C" if cur_var == "TYPE_B" else "TYPE_A")
        applied_changes.append(f"چیدمان پلان به {merged['layout_variant']} تغییر یافت")

    merged["last_edit_summary_fa"] = " | ".join(applied_changes) if applied_changes else f"اعمال دستور ویرایش: {edit_prompt}"
    return merged



def update_geometry_locked_render_state(
    prev_render_state: Optional[Dict[str, Any]],
    user_prompt: str,
    plan_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    v33.0 Geometry-Locked Iterative 3D Render State Manager:
    Updates ONLY visual, material, style, lighting, balustrade, frame, and camera parameters in `active_render_state`
    while keeping 100% of the building 3D massing, floor count, cantilevers, windows, and doors locked to `plan_params`.
    """
    s = normalize_persian_text(user_prompt or "")
    sl = s.lower()
    p = plan_params or {}
    st = copy.deepcopy(prev_render_state) if isinstance(prev_render_state, dict) else {}

    placement = str(p.get("building_placement", "NORTH")).upper()
    flipped = bool(p.get("flip_plan_north_south", False))

    # 1. Facade Side (SOUTH, NORTH, EAST, WEST) — preserved across iterative edits unless explicitly changed!
    if any(k in sl for k in ("نمای شمالی", "نما شمالی", "ضلع شمالی", "سمت شمال", "جبهه شمالی", "north")):
        st["facade_side"] = "NORTH"
    elif any(k in sl for k in ("نمای جنوبی", "نما جنوبی", "ضلع جنوبی", "سمت جنوب", "جبهه جنوبی", "south")):
        st["facade_side"] = "SOUTH"
    elif any(k in sl for k in ("نمای شرقی", "نما شرقی", "ضلع شرقی", "سمت شرق", "east")):
        st["facade_side"] = "EAST"
    elif any(k in sl for k in ("نمای غربی", "نما غربی", "ضلع غربی", "سمت غرب", "west")):
        st["facade_side"] = "WEST"
    elif any(k in sl for k in ("سمت حیاط", "رو به حیاط", "از داخل حیاط", "نمای حیاط")):
        st["facade_side"] = "NORTH" if placement == "SOUTH" else ("SOUTH" if placement == "NORTH" else ("WEST" if placement == "EAST" else "EAST"))
    elif any(k in sl for k in ("سمت معبر", "سمت کوچه", "سمت خیابان", "رو به کوچه", "رو به معبر")):
        st["facade_side"] = placement if placement in ("NORTH", "SOUTH", "EAST", "WEST") else "SOUTH"
    elif "facade_side" not in st:
        st["facade_side"] = "NORTH" if flipped else "SOUTH"

    facade_labels = {
        "SOUTH": "نمای جنوبی",
        "NORTH": "نمای شمالی",
        "EAST": "نمای شرقی",
        "WEST": "نمای غربی",
    }
    st["facade_label_fa"] = facade_labels.get(st["facade_side"], "نمای جنوبی")

    # 2. Camera Mode — preserved across iterative edits unless explicitly changed!
    if any(k in sl for k in ("دید پرنده", "ایزومتریک", "از بالا", "aerial", "bird")):
        st["camera_mode"] = "BIRDS_EYE_3D"
    elif any(k in sl for k in ("پرسپکتیو", "ریسپکتیو", "سه رخ", "سه‌رخ", "زاویه")):
        st["camera_mode"] = "PERSPECTIVE_COURTYARD"
    elif any(k in sl for k in ("نمای روبرو", "تمام رخ", "elevation")):
        st["camera_mode"] = "SOUTH_ELEVATION"
    elif "camera_mode" not in st:
        st["camera_mode"] = "SOUTH_ELEVATION"

    # 3. Architectural Style — preserved across iterative edits unless explicitly changed!
    if any(k in sl for k in ("نئوکلاسیک", "نئو کلاسیک", "کلاسیک", "رومی", "صراحی", "سرستون", "سنتوری", "neoclassical", "classical")):
        st["style_key"] = "NEOCLASSICAL_STONE"
    elif any(k in sl for k in ("آجر", "آجری", "بتن اکسپوز", "brick")):
        st["style_key"] = "MODERN_BRICK_CONCRETE"
    elif any(k in sl for k in ("مینیمال", "minimal", "سیمان سفید")):
        st["style_key"] = "MINIMAL_WHITE"
    elif any(k in sl for k in ("مدرن", "ترمووود", "چوب ترمو", "لوور چوبی", "modern")):
        st["style_key"] = "MODERN_THERMOWOOD"
    elif "style_key" not in st:
        st["style_key"] = "NEOCLASSICAL_STONE"

    # 4. Primary Stone / Wall Color & Material — preserved across iterative edits unless explicitly changed!
    if any(k in sl for k in ("سنگ سفید", "تراورتن سفید", "عباس آباد سفید", "عباس‌آباد سفید", "سفید عباس", "رنگ سفید", "سفید کن", "سفیدش کن", "سیمان سفید")):
        st["stone_color"] = "WHITE"
        st["stone_label_fa"] = "سنگ تراورتن سفید عباس‌آباد ممتاز"
    elif any(k in sl for k in ("سنگ تیره", "سنگ مشکی", "ذغالی", "بازالت", "تیره کن", "مشکی کن")):
        st["stone_color"] = "DARK_BASALT"
        st["stone_label_fa"] = "سنگ بازالت و مرمر تیره مدرن"
    elif any(k in sl for k in ("آجر", "آجری", "نسوز")):
        st["stone_color"] = "TERRACOTTA_BRICK"
        st["stone_label_fa"] = "آجر نسوز رستیک و سنگ کرم"
    elif any(k in sl for k in ("سنگ کرم", "تراورتن کرم", "کرم روشن", "بژ", "کرم کن", "تراورتن")):
        st["stone_color"] = "CREAM"
        st["stone_label_fa"] = "سنگ تراورتن کرم روشن ابزارخورده"
    elif "stone_color" not in st:
        if st["style_key"] == "NEOCLASSICAL_STONE":
            st["stone_color"] = "CREAM"
            st["stone_label_fa"] = "سنگ تراورتن کرم روشن ابزارخورده"
        elif st["style_key"] == "MODERN_BRICK_CONCRETE":
            st["stone_color"] = "TERRACOTTA_BRICK"
            st["stone_label_fa"] = "آجر نسوز رستیک و بتن اکسپوز"
        else:
            st["stone_color"] = "WHITE"
            st["stone_label_fa"] = "سنگ تراورتن سفید و میکروسمنت"

    # 5. Thermowood Timber Accent (`چوب ترمووود`) — preserved across turns!
    if any(k in sl for k in ("بدون چوب", "حذف چوب", "تمام سنگ")):
        st["wood_accent"] = False
    elif any(k in sl for k in ("ترمووود", "چوب", "لوور چوبی", "thermowood", "wood")):
        st["wood_accent"] = True
    elif "wood_accent" not in st:
        st["wood_accent"] = st["style_key"] in ("MODERN_THERMOWOOD", "MODERN_BRICK_CONCRETE")

    # 6. Balustrade / Railing Type (`STONE_BALUSTER` vs `GLASS` vs `DARK_METAL`) — preserved across turns!
    if any(k in sl for k in ("نرده شیشه", "نرده شیشه‌ای", "جان پناه شیشه", "شیشه ای کن")):
        st["balustrade_type"] = "GLASS"
    elif any(k in sl for k in ("صراحی", "نرده سنگی", "صراحی سنگی")):
        st["balustrade_type"] = "STONE_BALUSTER"
    elif any(k in sl for k in ("نرده فلزی", "حفاظ فلزی", "نرده مشکی")):
        st["balustrade_type"] = "DARK_METAL"
    elif "balustrade_type" not in st or any(k in sl for k in ("مدرنش کن", "سبک مدرن", "نئوکلاسیکش کن", "سبک نئوکلاسیک")):
        st["balustrade_type"] = "STONE_BALUSTER" if st["style_key"] == "NEOCLASSICAL_STONE" else "GLASS"

    # 7. Window Frame Color (`DARK_CHARCOAL` vs `BRONZE_GOLD` vs `WHITE`) — preserved across turns!
    if any(k in sl for k in ("فریم مشکی", "قاب مشکی", "پنجره مشکی")):
        st["window_frame_color"] = "DARK_CHARCOAL"
    elif any(k in sl for k in ("فریم طلایی", "فریم برنزی", "قاب طلایی")):
        st["window_frame_color"] = "BRONZE_GOLD"
    elif any(k in sl for k in ("فریم سفید", "قاب سفید")):
        st["window_frame_color"] = "WHITE"
    elif "window_frame_color" not in st:
        st["window_frame_color"] = "BRONZE_GOLD" if st["style_key"] == "NEOCLASSICAL_STONE" else "DARK_CHARCOAL"

    # 8. Lighting & Time of Day (`DAY_SUNNY` vs `GOLDEN_HOUR` vs `NIGHT_WARM` vs `OVERCAST`) — preserved across turns!
    if any(k in sl for k in ("شب", "نورپردازی شب", "حالت شب", "شبش", "night")):
        st["lighting_mode"] = "NIGHT_WARM"
        st["time_label_fa"] = "شب با نورپردازی خطی گرم و وال‌واشر نما"
    elif any(k in sl for k in ("غروب", "عصر", "طلایی", "dusk", "sunset", "golden")):
        st["lighting_mode"] = "GOLDEN_HOUR"
        st["time_label_fa"] = "غروب طلایی با نورپردازی گرم نما"
    elif any(k in sl for k in ("ابری", "بارانی", "ملایم", "overcast")):
        st["lighting_mode"] = "OVERCAST"
        st["time_label_fa"] = "روز ابری ملایم"
    elif any(k in sl for k in ("روز", "آفتابی", "خورشید", "day", "sunny")):
        st["lighting_mode"] = "DAY_SUNNY"
        st["time_label_fa"] = "روز آفتابی با سایه‌های طبیعی"
    elif "lighting_mode" not in st:
        st["lighting_mode"] = "DAY_SUNNY"
        st["time_label_fa"] = "روز آفتابی با سایه‌های طبیعی"

    if any(k in sl for k in ("نورپردازی", "نور خطی", "نور مخفی", "وال واشر", "وال‌واشر")):
        st["linear_facade_led"] = True
    elif "linear_facade_led" not in st:
        st["linear_facade_led"] = True

    style_names_fa = {
        "NEOCLASSICAL_STONE": "نئوکلاسیک (ابزار سنگی کلاسیک، سرستون و قاب‌بندی پنجره)",
        "MODERN_THERMOWOOD": "مدرن (ترکیب سنگ، چوب ترمووود و شیشه قدی)",
        "MODERN_BRICK_CONCRETE": "مدرن آجری (آجر نسوز رستیک، بتن اکسپوز و فریم تیره)",
        "MINIMAL_WHITE": "مینیمال (حجم خالص سفید و شیشه سرتاسری)",
    }
    wood_str = " + لوور و زیرسقف چوب ترمووود" if st.get("wood_accent") else ""
    rail_str = "نرده صراحی سنگی" if st.get("balustrade_type") == "STONE_BALUSTER" else ("نرده شیشه‌ای فریم‌لس" if st.get("balustrade_type") == "GLASS" else "نرده فلزی مشکی")
    st["style_label_fa"] = f"{style_names_fa.get(st['style_key'], 'نئوکلاسیک')} | {st['stone_label_fa']}{wood_str} | {rail_str}"

    # Deterministic locked seed tied purely to plan geometry & facade side so iterative edits never shift building geometry!
    w_mm = int(p.get("site_width_mm", 10000))
    l_mm = int(p.get("site_length_mm", 20000))
    fl_c = int(p.get("floor_count", 2 if p.get("is_duplex") else 1))
    side_idx = {"SOUTH": 1, "NORTH": 2, "EAST": 3, "WEST": 4}.get(st["facade_side"], 1)
    st["locked_seed"] = 20260000 + (w_mm // 100) * 10 + fl_c * 100 + side_idx
    st["render_revision"] = int(st.get("render_revision", 0)) + 1

    hist = list(st.get("edit_history_fa") or [])
    if user_prompt:
        hist.append(user_prompt.strip())
    st["edit_history_fa"] = hist[-10:]
    return st


def build_render_state_from_plan_or_prev_render(
    active_plan_params: Dict[str, Any],
    user_prompt: str,
    prev_render_state: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Bridges the Multi-Turn Plan Engine to the ComfyUI Render Pipeline (`پل ارتباطی دوطرفه پلان و رندر`):
    - When the user approves a plan and says "از همین ساختمان یه رندر از نمای جنوبی بگیر", extracts the exact
      floor count, typology, building width, window layout, style, materials, lighting (`day` vs `night`), and camera perspective.
    - When the user iterates on renders ("همین نما رو رندر شب بگیر", "متریالش رو به آجر قرمز تغییر بده", "زاویه رو عوض کن"),
      preserves the locked building geometry/floor count (`floors`, `scaffold_seed`, `last_day_render_path`) while updating
      only the requested lighting, material, style, or camera attributes!
    """
    s = normalize_persian_text(user_prompt)
    sl = s.lower()
    state = copy.deepcopy(prev_render_state or {})

    # 1. Floor count & Typology from active_plan_params first!
    m_fl = re.search(r"(\d+)\s*طبقه", s)
    if m_fl:
        state["floors"] = int(m_fl.group(1))
    elif active_plan_params and ("floors" not in state or any(k in sl for k in ("همین ساختمان", "همین پلان", "این پلان", "نمای جنوبی"))):
        typ = str(active_plan_params.get("typology", "VILLA_1FLOOR"))
        if typ == "DUPLEX_2FLOOR" or active_plan_params.get("is_duplex"):
            state["floors"] = 2
            state["plan_typology"] = "DUPLEX_2FLOOR"
        elif typ in ("MULTIFLOOR_RESIDENTIAL", "MIXED_USE_MULTIFLOOR"):
            state["floors"] = int(active_plan_params.get("floor_count", 3)) + 1  # +1 for pilotis ground floor
            state["plan_typology"] = typ
        else:
            state["floors"] = 1
            state["plan_typology"] = "VILLA_1FLOOR"
    elif "floors" not in state:
        state["floors"] = 2

    if active_plan_params:
        state["plan_site_width_m"] = round(int(active_plan_params.get("site_width_mm", 10000)) / 1000.0, 2)
        state["plan_site_length_m"] = round(int(active_plan_params.get("site_length_mm", 20000)) / 1000.0, 2)
        state["plan_coverage_ratio"] = float(active_plan_params.get("coverage_ratio", 0.60))
        state["plan_remove_void"] = bool(active_plan_params.get("remove_duplex_void", False))

    # 2. Architectural Style (`modern`, `neoclassical`, `minimal`, `brick_traditional`)
    if any(w in sl for w in ("نئوکلاسیک", "کلاسیک", "رومی", "neoclassical", "classic")):
        state["style"] = "neoclassical"
    elif any(w in sl for w in ("مینیمال", "minimal")):
        state["style"] = "minimal"
    elif any(w in sl for w in ("مدرن", "modern")):
        state["style"] = "modern"
    elif "style" not in state:
        state["style"] = "modern"

    # 3. Facade Materials (`travertine`, `red_brick`, `thermowood`, `white_cement`, `glass_curtain`)
    new_mats = []
    if any(w in sl for w in ("تراورتن سفید", "سنگ سفید", "white travertine")):
        new_mats.append("white honed Iranian travertine stone slabs")
    elif any(w in sl for w in ("تراورتن", "سنگ کرم", "سنگ روشن", "travertine")):
        new_mats.append("cream honed Iranian travertine stone slabs")
    if any(w in sl for w in ("چوب ترمووود", "ترمووود", "چوب ترمو", "چوب", "thermowood", "wood")):
        new_mats.append("warm horizontal natural thermowood timber louvers and cladding")
    if any(w in sl for w in ("سیمان سفید", "پلاستر سفید", "ورق سفید", "white cement", "white stucco")):
        new_mats.append("crisp smooth white micro-cement architectural stucco")
    if any(w in sl for w in ("آجر قرمز", "آجر نما", "آجر", "red brick", "brick")):
        new_mats.append("warm textured red-ochre Iranian architectural firebrick")
    if any(w in sl for w in ("بتن اکسپوز", "بتن", "exposed concrete")):
        new_mats.append("architectural board-formed exposed concrete")

    if new_mats:
        state["materials"] = new_mats
    elif not state.get("materials"):
        state["materials"] = [
            "crisp smooth white micro-cement architectural stucco",
            "warm horizontal natural thermowood timber louvers",
            "white honed Iranian travertine stone slabs",
        ]

    # 4. Lighting Mode (`day` vs `night` — triggers Stage-2 Locked Night Chain when switching to night!)
    if any(w in sl for w in ("شب", "شبش", "night", "غروب", "نورپردازی شب")):
        state["lighting"] = "night"
        state["use_locked_night_chain"] = bool(
            (prev_render_state and (prev_render_state.get("last_day_render_path") or prev_render_state.get("last_render_path")))
        )
    elif any(w in sl for w in ("روز", "روزش", "day", "خورشید")):
        state["lighting"] = "day"
        state["use_locked_night_chain"] = False
    elif "lighting" not in state:
        state["lighting"] = "day"
        state["use_locked_night_chain"] = False

    # 5. Camera View (`frontal_elevation` when user asks for `نمای جنوبی` / `نمای روبرو`, else `three_quarter_perspective`)
    if any(w in sl for w in ("نمای جنوبی", "نما جنوبی", "نمای روبرو", "روبرو", "elevation", "frontal")):
        state["camera_view"] = "south_elevation"
    elif any(w in sl for w in ("سه رخ", "سه‌رخ", "پرسپکتیو", "زاویه دیگر", "زاویه دیگه", "سه گوشه", "perspective", "angle")):
        state["camera_view"] = "three_quarter_perspective"
    elif "camera_view" not in state:
        state["camera_view"] = "south_elevation"

    state["render_revision"] = int(state.get("render_revision", 0)) + 1
    return state
