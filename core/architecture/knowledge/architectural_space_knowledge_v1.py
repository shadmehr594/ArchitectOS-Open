"""Reusable, jurisdiction-aware architectural knowledge (no geometry generation).

All normative and numeric claims are records with provenance.  Local overlays
are opt-in.  Historical Parcel2 contracts are deliberately not imported.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable


class Provenance(str, Enum):
    IRAN_NATIONAL_VERIFIED_REGULATION = "IRAN_NATIONAL_VERIFIED_REGULATION"
    MINAB_LOCAL_VERIFIED_RULE = "MINAB_LOCAL_VERIFIED_RULE"
    PROJECT_CONTRACT = "PROJECT_CONTRACT"
    USER_REQUESTED_PROJECT_RULE = "USER_REQUESTED_PROJECT_RULE"
    ARCHITECTURAL_DESIGN_HEURISTIC = "ARCHITECTURAL_DESIGN_HEURISTIC"
    GLOBAL_REFERENCE_HEURISTIC = "GLOBAL_REFERENCE_HEURISTIC"
    UNRESOLVED_LOCAL_RULE = "UNRESOLVED_LOCAL_RULE"


NATIONAL_SOURCE = {
    "document_id": "IRAN_TOPIC4_1396",
    "title_fa": "مبحث چهارم مقررات ملی ساختمان - الزامات عمومی ساختمان",
    "edition": "ویرایش سوم ۱۳۹۶",
    "sha256": "d1bf218bd5e346158a7f2a64bf929096c95b6330d1bd50d097c17bea9dff94d2",
}


def claim(value: Any, provenance: Provenance, evidence_id: str, **source: Any) -> dict:
    return {"value": value, "provenance": provenance.value, "evidence_id": evidence_id, "source": source or None}


def national(value: Any, evidence_id: str, clause: str, pdf_page: int, printed_page: int) -> dict:
    return claim(value, Provenance.IRAN_NATIONAL_VERIFIED_REGULATION, evidence_id,
                 **NATIONAL_SOURCE, clause=clause, pdf_page=pdf_page, printed_page=printed_page)


HABITABLE_FLOOR = {
    "minimum_area_m2": national(6.5, "T4-4-5-2-2-1", "4-5-2-2-1", 65, 52),
    "minimum_clear_width_m": national(2.15, "T4-4-5-2-2-2", "4-5-2-2-2", 65, 52),
    "minimum_clear_height_m": national(2.4, "T4-4-5-2-2-3", "4-5-2-2-3", 65, 52),
}


def heuristic(value: Any, evidence_id: str) -> dict:
    return claim(value, Provenance.ARCHITECTURAL_DESIGN_HEURISTIC, evidence_id)


def _space(name_fa: str, definition: str, primary: str, privacy: str, circulation: str,
           *, enclosure="CONDITIONAL", door="CONDITIONAL", open_plan=False,
           connections=(), low_quality=(), transit=False, daylight="CONDITIONAL",
           sources=(), ventilation="CONDITIONAL", wet=False, acoustic="MEDIUM",
           furniture=(), ownership="PRIVATE", special=(), habitable=False,
           dimensions: dict | None = None) -> dict:
    verified = deepcopy(HABITABLE_FLOOR) if habitable else {}
    return {
        "semantic_class": None, "names": {"fa": name_fa, "en": ""},
        "functional_definition": definition, "primary_function": primary,
        "occupancy_use_pattern": "OCCUPIED_DESTINATION" if "DESTINATION" in circulation else "SUPPORT_OR_TRANSITION",
        "privacy_class": privacy, "circulation_role": circulation,
        "requires_enclosure": enclosure, "requires_door": door,
        "door_optional": door == "OPTIONAL", "open_connection_allowed": open_plan,
        "may_be_open_plan": open_plan, "typical_direct_connections": list(connections),
        "forbidden_or_low_quality_connections": list(low_quality), "can_be_transit_node": transit,
        "daylight_requirement": daylight, "acceptable_daylight_sources": list(sources),
        "ventilation_requirement": ventilation, "wet_zone": wet,
        "acoustic_privacy_sensitivity": acoustic, "furniture_use_zone_requirements": list(furniture),
        "clear_dimension_requirements": {"verified_regulation": verified, "project_contract": {},
                                         "design_heuristic": dimensions or {}},
        "area_requirements": {"verified_regulation": verified.get("minimum_area_m2"), "project_contract": None,
                              "design_heuristic": (dimensions or {}).get("target_area_m2")},
        "aspect_ratio_guidance": (dimensions or {}).get("aspect_ratio"),
        "usable_wall_requirements": (dimensions or {}).get("usable_wall"),
        "door_swing_clearance_requirements": heuristic("VERIFY_USE_ZONE_CONFLICT", "DOOR_USE_ZONE_PROXY_V1"),
        "window_exposure_requirements": list(sources), "common_private_ownership_semantics": ownership,
        "special_validation_rules": list(special),
    }


EXTERIOR = ("PUBLIC_STREET", "PUBLIC_WAY", "PRIVATE_YARD", "REAR_YARD", "COURTYARD", "VALID_LIGHTWELL", "TERRACE_TO_VALID_OPEN_SPACE")


SPACE_SPECS = {
    "UNIT_ENTRY": _space("ورودی واحد", "آستانه کنترل‌شده میان مشاع و واحد خصوصی", "ورود و فیلتر", "TRANSITION", "TRANSITION_DISTRIBUTOR", door="REQUIRED", open_plan=True, connections=("FOYER_SHOE_OFF","LIVING_RECEPTION","GENERAL_HALL"), low_quality=("BEDROOM_SINGLE","BEDROOM_DOUBLE"), transit=True, furniture=("ENTRY_CLEARANCE",), special=("COMMON_TO_PRIVATE_ENTRY_ONLY",)),
    "FOYER_SHOE_OFF": _space("هشتی/کفش‌کن", "فضای مکث، تعویض کفش و نگهداری وسایل ورودی", "فیلتر ورودی", "TRANSITION", "DISTRIBUTOR", door="OPTIONAL", open_plan=True, connections=("UNIT_ENTRY","LIVING_RECEPTION","GENERAL_HALL","GUEST_WC"), transit=True, furniture=("SHOE_STORAGE","COAT_STORAGE","CLEAR_ROUTE")),
    "LIVING_RECEPTION": _space("نشیمن/پذیرایی", "فضای عمومی خانه برای نشستن، گفت‌وگو و پذیرایی", "زندگی عمومی", "PUBLIC", "DESTINATION_DISTRIBUTOR_PASS_THROUGH_ALLOWED", door="OPTIONAL", open_plan=True, connections=("DINING","OPEN_KITCHEN","TERRACE_BALCONY","PRIVATE_HALL_CORRIDOR"), transit=True, daylight="REQUIRED", sources=EXTERIOR, acoustic="MEDIUM", furniture=("SEATING_OR_CONVERSATION_ZONE","CLEAR_CIRCULATION_STRIP"), habitable=True, special=("PASS_THROUGH_MUST_NOT_DESTROY_USE_ZONE",)),
    "GENERAL_HALL": _space("هال عمومی/خانوادگی", "فضای جمع خانوادگی که می‌تواند توزیع‌کننده باشد", "زندگی خانوادگی", "SEMI_PUBLIC", "DESTINATION_DISTRIBUTOR", door="OPTIONAL", open_plan=True, connections=("LIVING_RECEPTION","DINING","PRIVATE_HALL_CORRIDOR"), transit=True, daylight="REQUIRED", sources=EXTERIOR, furniture=("SEATING_ZONE","CLEAR_ROUTE"), habitable=True),
    "FAMILY_HALL": _space("هال خانوادگی", "نشیمن نیمه‌خصوصی خانواده", "جمع خانوادگی", "SEMI_PUBLIC", "DESTINATION_DISTRIBUTOR", door="OPTIONAL", open_plan=True, connections=("PRIVATE_HALL_CORRIDOR","BEDROOM_SINGLE","BEDROOM_DOUBLE"), transit=True, daylight="REQUIRED", sources=EXTERIOR, furniture=("SEATING_ZONE","CLEAR_ROUTE"), habitable=True),
    "DINING": _space("غذاخوری", "محل میز غذا و استفاده پیرامونی آن", "صرف غذا", "SEMI_PUBLIC", "DESTINATION_PASS_THROUGH_ALLOWED", door="OPTIONAL", open_plan=True, connections=("LIVING_RECEPTION","OPEN_KITCHEN","CLOSED_KITCHEN"), transit=True, daylight="PREFERRED", sources=EXTERIOR+("BORROWED_OPEN_PLAN_DAYLIGHT",), furniture=("TABLE_ZONE","CHAIR_PULL_OUT_ZONE","CLEAR_ROUTE"), habitable=True),
    "OPEN_KITCHEN": _space("آشپزخانه باز", "فضای تهیه غذا در میدان پیوسته عمومی", "تهیه غذا", "SERVICE", "DESTINATION_PASS_THROUGH_ALLOWED", enclosure="OPEN_FIELD", door="NOT_REQUIRED", open_plan=True, connections=("DINING","LIVING_RECEPTION"), low_quality=("BEDROOM_SINGLE",), transit=True, daylight="DIRECT_OR_SAME_OPEN_PLAN_FIELD", sources=EXTERIOR+("BORROWED_OPEN_PLAN_DAYLIGHT",), ventilation="REQUIRED", wet=True, furniture=("CABINET_APPLIANCE_RUN","WORKTOP","CLEAR_PASSAGE"), special=("BORROWED_LIGHT_ONLY_WITH_GENUINE_OPEN_PLAN",)),
    "CLOSED_KITCHEN": _space("آشپزخانه بسته", "فضای محصور تهیه غذا", "تهیه غذا", "SERVICE", "DESTINATION_PASS_THROUGH_FORBIDDEN", enclosure="REQUIRED", door="REQUIRED_OR_CODE_DEPENDENT", connections=("DINING","LIVING_RECEPTION","SERVICE_ROUTE"), low_quality=("BEDROOM_SINGLE","BEDROOM_DOUBLE"), daylight="JURISDICTION_DEPENDENT", sources=EXTERIOR, ventilation="REQUIRED", wet=True, furniture=("CABINET_APPLIANCE_RUN","WORK_SEQUENCE","CLEAR_PASSAGE"), special=("NOT_PRIVATE_ROOM_TRANSIT_NODE",)),
    "BEDROOM_SINGLE": _space("اتاق خواب یک‌نفره", "مقصد خصوصی خواب یک نفر با تخت، کمد و گردش", "خواب یک نفر", "PRIVATE", "DESTINATION_PASS_THROUGH_FORBIDDEN", enclosure="REQUIRED", door="REQUIRED", connections=("PRIVATE_HALL_CORRIDOR","FAMILY_HALL"), low_quality=("BEDROOM_DOUBLE","FAMILY_BATHROOM","GUEST_WC"), daylight="REQUIRED", sources=EXTERIOR, ventilation="REQUIRED", acoustic="HIGH", furniture=("SINGLE_BED_ZONE","WARDROBE_WALL","BED_SIDE_AND_FOOT_CIRCULATION"), habitable=True, special=("NO_UNRELATED_ROOM_THROUGH_ROUTE",)),
    "BEDROOM_DOUBLE": _space("اتاق خواب دونفره", "مقصد خصوصی خواب دو نفر با تخت دونفره، کمد و گردش دوطرفه", "خواب دو نفر", "PRIVATE", "DESTINATION_PASS_THROUGH_FORBIDDEN", enclosure="REQUIRED", door="REQUIRED", connections=("PRIVATE_HALL_CORRIDOR","FAMILY_HALL"), low_quality=("BEDROOM_SINGLE","FAMILY_BATHROOM","GUEST_WC"), daylight="REQUIRED", sources=EXTERIOR, ventilation="REQUIRED", acoustic="HIGH", furniture=("DOUBLE_BED_ZONE","WARDROBE_WALL","BED_SIDE_AND_FOOT_CIRCULATION"), habitable=True, special=("NO_UNRELATED_ROOM_THROUGH_ROUTE",)),
    "MASTER_BEDROOM_SLEEPING": _space("بخش خواب مستر", "بخش خواب نورگیر مجموعه مستر", "خواب اصلی", "PRIVATE", "DESTINATION_PASS_THROUGH_FORBIDDEN", enclosure="REQUIRED", door="REQUIRED", connections=("PRIVATE_HALL_CORRIDOR","DRESSING","ENSUITE"), daylight="REQUIRED", sources=EXTERIOR, ventilation="REQUIRED", acoustic="HIGH", furniture=("DOUBLE_BED_ZONE","BED_CIRCULATION"), habitable=True, special=("SLEEPING_ZONE_REMAINS_DAYLIGHTED","SUITE_DEPENDENT_CONNECTIONS_ALLOWED")),
    "DRESSING": _space("رختکن", "فضای پوشاک وابسته به اتاق مستر", "تعویض و نگهداری لباس", "PRIVATE", "DESTINATION_OR_SUITE_TRANSITION", enclosure="REQUIRED", door="OPTIONAL", connections=("MASTER_BEDROOM_SLEEPING","ENSUITE"), transit=True, furniture=("WARDROBE_RUNS","DRESSING_PASSAGE")),
    "ENSUITE": _space("حمام مستر", "فضای بهداشتی خصوصی وابسته به مستر", "بهداشت خصوصی", "PRIVATE", "DESTINATION_PASS_THROUGH_FORBIDDEN", enclosure="REQUIRED", door="REQUIRED", connections=("MASTER_BEDROOM_SLEEPING","DRESSING"), daylight="NOT_REQUIRED_IF_VALID_VENTILATION", ventilation="REQUIRED", wet=True, acoustic="HIGH", furniture=("FIXTURE_ZONES","DOOR_CLEARANCE"), special=("NO_TRANSIT",)),
    "FAMILY_BATHROOM": _space("حمام خانوادگی", "فضای بهداشتی مشترک واحد در حوزه خصوصی", "بهداشت", "PRIVATE", "DESTINATION_PASS_THROUGH_FORBIDDEN", enclosure="REQUIRED", door="REQUIRED", connections=("PRIVATE_HALL_CORRIDOR",), low_quality=("LIVING_RECEPTION","DINING"), ventilation="REQUIRED", wet=True, acoustic="HIGH", furniture=("FIXTURE_ZONES","DOOR_CLEARANCE"), special=("NO_TRANSIT",)),
    "GUEST_WC": _space("سرویس مهمان", "توالت مهمان نزدیک حوزه ورودی/عمومی با دید کنترل‌شده", "بهداشت مهمان", "SERVICE", "DESTINATION_PASS_THROUGH_FORBIDDEN", enclosure="REQUIRED", door="REQUIRED", connections=("FOYER_SHOE_OFF","PUBLIC_TRANSITION"), low_quality=("DIRECT_DOMINANT_VIEW_FROM_LIVING","DINING"), ventilation="REQUIRED", wet=True, acoustic="HIGH", furniture=("WC","BASIN","DOOR_CLEARANCE"), special=("NO_TRANSIT","SCREEN_FROM_PUBLIC_VIEW")),
    "SEPARATE_WC": _space("توالت مستقل", "فضای محصور توالت مستقل", "بهداشت", "SERVICE", "DESTINATION_PASS_THROUGH_FORBIDDEN", enclosure="REQUIRED", door="REQUIRED", connections=("PRIVATE_HALL_CORRIDOR","PUBLIC_TRANSITION"), ventilation="REQUIRED", wet=True, acoustic="HIGH", furniture=("WC","DOOR_CLEARANCE"), special=("NO_TRANSIT",)),
    "STORAGE_LINEN": _space("انباری/لینن", "فضای نگهداری داخلی", "ذخیره", "SERVICE", "DESTINATION_PASS_THROUGH_FORBIDDEN", enclosure="REQUIRED", door="REQUIRED", connections=("PRIVATE_HALL_CORRIDOR","SERVICE_ROUTE"), furniture=("SHELVING","ACCESS_CLEARANCE"), special=("NO_RESIDENTIAL_TRANSIT",)),
    "LAUNDRY_UTILITY": _space("رختشویخانه/خدمات", "فضای شست‌وشو و تجهیزات خانگی", "خدمات خانگی", "SERVICE", "DESTINATION_PASS_THROUGH_FORBIDDEN", enclosure="REQUIRED", door="REQUIRED", connections=("SERVICE_ROUTE","PRIVATE_HALL_CORRIDOR"), ventilation="REQUIRED", wet=True, furniture=("APPLIANCE_ZONE","SERVICE_CLEARANCE")),
    "PRIVATE_HALL_CORRIDOR": _space("راهرو/هال خصوصی", "رابط مشتق از گراف برای حفظ دسترسی و حریم", "اتصال", "TRANSITION", "DISTRIBUTOR", door="NOT_REQUIRED", open_plan=True, connections=("BEDROOM_SINGLE","BEDROOM_DOUBLE","MASTER_BEDROOM_SLEEPING","FAMILY_BATHROOM"), transit=True, furniture=("CLEAR_ROUTE",), special=("DERIVED_NOT_TARGET_ROOM","MINIMIZE_AND_JUSTIFY","NO_USELESS_TERMINATION")),
    "TERRACE_BALCONY": _space("تراس/بالکن", "مقصد نیمه‌باز قابل استفاده متصل به واحد", "اقامت کوتاه بیرونی", "SEMI_PUBLIC", "DESTINATION", enclosure="SEMI_OPEN", door="REQUIRED", connections=("LIVING_RECEPTION","MASTER_BEDROOM_SLEEPING"), daylight="OPEN_TO_VALID_EXTERIOR", sources=("PUBLIC_STREET","PRIVATE_YARD","COURTYARD"), ventilation="OPEN_AIR", furniture=("USABLE_STANDING_OR_SEATING_ZONE",), special=("USABLE_SHAPE_AND_DEPTH","REAL_ROOM_CONNECTION")),
    "PRIVATE_YARD": _space("حیاط خصوصی", "فضای باز قابل استفاده متعلق به واحد", "فضای باز", "ENVIRONMENTAL", "DESTINATION", enclosure="OPEN_TO_SKY", door="OPTIONAL", connections=("LIVING_RECEPTION","TERRACE_BALCONY"), daylight="SOURCE", ventilation="SOURCE", ownership="PRIVATE", special=("NOT_LIGHTWELL",)),
    "COURTYARD": _space("حیاط/میان‌سرا", "فضای باز به آسمان که می‌تواند قابل استفاده باشد", "فضای باز و نور", "ENVIRONMENTAL", "ENVIRONMENTAL_VOID_OR_DESTINATION", enclosure="OPEN_TO_SKY", door="OPTIONAL", connections=("LIVING_RECEPTION","DINING"), daylight="SOURCE", ventilation="SOURCE", ownership="PRIVATE_OR_COMMON", special=("DISTINCT_FROM_LIGHTWELL",)),
    "LIGHTWELL": _space("نورگیر", "خلأ محیطی باز به آسمان برای نور/تهویه، نه اتاق یا راهرو", "نور و تهویه", "ENVIRONMENTAL", "ENVIRONMENTAL_VOID", enclosure="OPEN_TO_SKY", door="NOT_REQUIRED", daylight="SOURCE_IF_LEGAL", ventilation="SOURCE_IF_LEGAL", ownership="PRIVATE_OR_COMMON", special=("NOT_ROOM","NOT_CORRIDOR","ACTUAL_SHARED_BOUNDARY_REQUIRED","NO_ACCESS_EDGE_UNLESS_COURTYARD_ACCESS_EXPLICIT")),
}


SPACE_SPECS.update({
    "COMMON_ENTRANCE": _space("ورودی مشترک", "آستانه عمومی ساختمان", "ورود مشترک", "COMMON", "TRANSITION", door="REQUIRED", connections=("LOBBY","COMMON_CORRIDOR_GALLERY"), transit=True, ownership="COMMON"),
    "LOBBY": _space("لابی", "فضای توزیع عمومی ساختمان", "توزیع", "COMMON", "DISTRIBUTOR", door="OPTIONAL", open_plan=True, connections=("COMMON_ENTRANCE","STAIR","ELEVATOR_LOBBY"), transit=True, ownership="COMMON"),
    "COMMON_CORRIDOR_GALLERY": _space("راهرو/گالری مشترک", "مسیر افقی مشاع", "توزیع مشترک", "COMMON", "DISTRIBUTOR", door="NOT_REQUIRED", connections=("COMMON_LANDING","UNIT_ENTRY"), transit=True, ownership="COMMON", special=("MUST_NOT_BE_ABSORBED_BY_PRIVATE_UNIT",)),
    "COMMON_LANDING": _space("پاگرد مشترک", "سطح امن پیش از ورودی واحد و دسترسی عمودی", "توزیع امن", "COMMON", "DISTRIBUTOR", connections=("STAIR","ELEVATOR_LOBBY","UNIT_ENTRY"), transit=True, ownership="COMMON", special=("SAME_LEVEL_BEFORE_UNIT_ENTRY","DOOR_SWING_SAFE",)),
    "STAIR": _space("پله", "دسترسی عمودی ساختمان", "حرکت عمودی", "COMMON", "VERTICAL_ACCESS", enclosure="CODE_DEPENDENT", door="CODE_DEPENDENT", connections=("COMMON_LANDING","LOBBY"), transit=True, ownership="COMMON", special=("VERTICALLY_ALIGNED_CONTRACT",)),
    "ELEVATOR": _space("آسانسور", "حمل عمودی", "حرکت عمودی", "COMMON", "VERTICAL_ACCESS", enclosure="REQUIRED", door="REQUIRED", connections=("ELEVATOR_LOBBY",), transit=True, ownership="COMMON", special=("VERTICALLY_ALIGNED_CONTRACT",)),
    "ELEVATOR_LOBBY": _space("لابی آسانسور", "واسطه امن آسانسور و توزیع افقی", "انتقال", "COMMON", "DISTRIBUTOR", connections=("ELEVATOR","COMMON_LANDING","COMMON_CORRIDOR_GALLERY"), transit=True, ownership="COMMON"),
    "COMMON_ROOF": _space("بام مشترک", "فضای باز مشاع بام", "بام", "COMMON", "DESTINATION", enclosure="OPEN_TO_SKY", connections=("COMMON_LANDING","ROOF_SERVICE_ENCLOSURE"), ownership="COMMON"),
    "ROOF_SERVICE_ENCLOSURE": _space("خرپشته/فضای خدمات بام", "پوشش پایانه پله/تأسیسات بام، نه فضای مسکونی", "خدمات بام", "COMMON", "DESTINATION", enclosure="REQUIRED", door="REQUIRED", connections=("COMMON_ROOF","STAIR"), ownership="COMMON", special=("NOT_HABITABLE_ROOM",)),
    "SHARED_LIGHTWELL_COURTYARD": _space("نورگیر/حیاط مشترک", "خلأ محیطی مشترک باز به آسمان", "نور و تهویه مشترک", "ENVIRONMENTAL", "ENVIRONMENTAL_VOID", enclosure="OPEN_TO_SKY", ownership="COMMON", special=("NOT_CIRCULATION","MULTI_UNIT_BOUNDARY_ALLOWED",)),
    "PILOTIS": _space("پیلوتی", "حوزه باز یا نیمه‌باز همکف زیر حجم بالایی که می‌تواند میزبان پارکینگ/دسترسی/مشاع باشد", "ظرف فضایی همکف", "COMMON", "CONTAINER_NOT_USE", enclosure="OPEN_OR_PARTLY_OPEN", connections=("PARKING_BAY","MANEUVER_ZONE","PEDESTRIAN_ONLY_ACCESS"), transit=True, ownership="COMMON", special=("PILOTIS_IS_NOT_PARKING",)),
    "PARKING_BAY": _space("جای پارک", "مقصد توقف خودرو وابسته به مسیر پیوسته و مانور", "توقف خودرو", "COMMON", "VEHICLE_DESTINATION", enclosure="CONDITIONAL", connections=("MANEUVER_ZONE",), ownership="COMMON", furniture=("VEHICLE_RECTANGLE","DOOR_CLEARANCE"), special=("ACCESS_AND_MANEUVER_REQUIRED",)),
    "MANEUVER_ZONE": _space("فضای مانور", "حوزه بدون مانع برای رسیدن/چرخش خودرو", "مانور خودرو", "COMMON", "VEHICLE_TRANSIT", enclosure="CONDITIONAL", connections=("PARKING_BAY","SHARED_VEHICLE_PEDESTRIAN_ACCESS"), transit=True, ownership="COMMON", special=("OBSTACLE_FREE_CONTINUITY",)),
    "SHARED_VEHICLE_PEDESTRIAN_ACCESS": _space("دسترسی مشترک خودرو/پیاده", "هندسه مشترک با دو جریان معنایی صریح", "دسترسی مختلط", "COMMON", "VEHICLE_TRANSIT", connections=("MANEUVER_ZONE","LOBBY"), transit=True, ownership="COMMON", special=("FLOWS_REMAIN_SEMANTICALLY_DISTINCT",)),
    "PEDESTRIAN_ONLY_ACCESS": _space("دسترسی فقط پیاده", "مسیر پیاده مستقل از خودرو", "حرکت پیاده", "COMMON", "TRANSITION", connections=("COMMON_ENTRANCE","LOBBY"), transit=True, ownership="COMMON"),
    "COMMERCIAL_SHOP": _space("تجاری/فروشگاه", "مقصد عمومی تجاری مرتبط با بر خیابان", "فعالیت تجاری", "PUBLIC", "DESTINATION", enclosure="REQUIRED", door="REQUIRED", connections=("COMMERCIAL_ENTRANCE_FRONTAGE","SERVICE_LOADING_ZONE"), daylight="PREFERRED", sources=("PUBLIC_STREET","PUBLIC_WAY"), furniture=("CUSTOMER_ZONE","DISPLAY_OR_SERVICE_ZONE","CLEAR_ROUTE"), special=("PUBLIC_FRONTAGE_EXPECTED","RESIDENTIAL_PRIVATE_CIRCULATION_SEPARATED_UNLESS_PROGRAM_ALLOWS",)),
    "COMMERCIAL_ENTRANCE_FRONTAGE": _space("ورودی/بر تجاری", "رابط مستقیم فضای تجاری با عرصه عمومی", "ورود عمومی", "PUBLIC", "TRANSITION", door="REQUIRED", connections=("PUBLIC_STREET","COMMERCIAL_SHOP"), transit=True),
    "SERVICE_LOADING_ZONE": _space("بارگیری/خدمات", "مسیر و حوزه خدمات تجاری", "خدمات", "SERVICE", "VEHICLE_TRANSIT_OR_DESTINATION", connections=("COMMERCIAL_SHOP","VEHICLE_ACCESS"), transit=True),
})

for key, spec in SPACE_SPECS.items():
    spec["semantic_class"] = key
    spec["names"]["en"] = key.replace("_", " ").title()


EDGE_TYPES = ("OPEN_CONNECTION", "DOOR_CONNECTION", "PUBLIC_TO_PRIVATE_TRANSITION",
              "COMMON_TO_PRIVATE_ENTRY", "SERVICE_ACCESS", "VEHICLE_ACCESS",
              "VERTICAL_ACCESS", "DAYLIGHT_ADJACENCY", "VENTILATION_ADJACENCY")

NON_TRANSIT = {k for k, v in SPACE_SPECS.items() if "PASS_THROUGH_FORBIDDEN" in v["circulation_role"]}


MINAB_OVERLAY = {
    "jurisdiction": "MINAB", "activation": "EXPLICIT_SELECTION_ONLY",
    "source": {"document_id": "MINAB_DETAILED_PLAN_VOL4_SPRING_1400", "title_fa": "طرح تفصیلی شهر میناب، جلد ۴، ضوابط و مقررات", "edition": "بهار ۱۴۰۰", "sha256": "13b2c9a9e7279ca3b4641ec0dc1c9b175adbc1474c52c5dad562746aa3e05db2", "promulgation_status": "UNRESOLVED"},
    "rules": [{"id":"MINAB_21_1_MAIN_SPACE_LIGHTWELL","provenance":Provenance.MINAB_LOCAL_VERIFIED_RULE.value,"clause":"21-1","pdf_page":33,"printed_page":29,"status":"TEXT_VERIFIED_NOT_ENFORCEABLE","conflict":"TABLE_WIDTH_VS_PROSE_3M_AND_EXACT_200_BOUNDARY","values":{"minimum_area_m2":12.0,"table_width_m":{"north_south_over_200":1.7,"east_west_over_200":2.0,"north_south_101_199_or_pilot":1.5,"east_west_101_199_or_pilot":2.0},"prose_minimum_width_m":3.0}}, {"id":"MINAB_21_2_CENTRAL_LIGHTWELL_AIRFLOW","provenance":Provenance.MINAB_LOCAL_VERIFIED_RULE.value,"clause":"21-2","pdf_page":33,"printed_page":29,"status":"TEXT_VERIFIED_NOT_ENFORCEABLE","values":{"natural_airflow_required":True}}],
    "unresolved": [
        {"id":"MINAB_REAR_YARD_ORIENTATION_DIMENSIONS","provenance":Provenance.UNRESOLVED_LOCAL_RULE.value,"missing_evidence":"Exact clause/table with rear-yard minimum width and area by east-west versus north-south parcel"},
        {"id":"MINAB_KITCHEN_LIGHTWELL_DIMENSIONS","provenance":Provenance.UNRESOLVED_LOCAL_RULE.value,"missing_evidence":"Exact Minab clause/table distinguishing kitchen-lighting court width and area"},
        {"id":"MINAB_8_5M_SOUTH_6_5M_NORTH","provenance":Provenance.UNRESOLVED_LOCAL_RULE.value,"missing_evidence":"No cited Minab clause/page in current evidence registry; values must not be enforced"},
        {"id":"MINAB_PROMULGATION_AND_PARCEL_APPLICABILITY","provenance":Provenance.UNRESOLVED_LOCAL_RULE.value,"missing_evidence":"Approval/promulgation sheet plus zoning/map applicability for target parcel"},
    ]
}


NATIONAL_DAYLIGHT_RULES = [
    {"id":"HABITABLE_MIN_AREA","field":"minimum_area_m2","claim":HABITABLE_FLOOR["minimum_area_m2"]},
    {"id":"HABITABLE_MIN_WIDTH","field":"minimum_clear_width_m","claim":HABITABLE_FLOOR["minimum_clear_width_m"]},
    {"id":"HABITABLE_MIN_HEIGHT","field":"minimum_clear_height_m","claim":HABITABLE_FLOOR["minimum_clear_height_m"]},
    {"id":"DIRECT_OPENING","claim":national(True,"T4-4-5-2-3-1","4-5-2-3-1",66,53),"applicability":"HABITABLE_ROOM"},
    {"id":"GLAZING_DEFAULT","claim":national("1/8","T4-4-5-2-3-2","4-5-2-3-2",66,53)},
    {"id":"GLAZING_ONE_WINDOW_DEPTH_GT_4_5","claim":national("1/7","T4-4-5-2-3-2","4-5-2-3-2",66,53)},
    {"id":"MAX_DAYLIGHT_DEPTH","claim":national(7.0,"T4-4-5-2-8-3","4-5-2-8-3",68,55)},
    {"id":"HABITABLE_COURT_GROUP_1_5","claims":{"minimum_area_m2":national(12.0,"T4-4-5-8-3-5","4-5-8-3-5",78,65),"minimum_width_m":national(3.0,"T4-4-5-8-3-5","4-5-8-3-5",78,65)},"applicability":"BUILDING_GROUP_1_5_AND_HABITABLE_OR_OCCUPATIONAL"},
    {"id":"KITCHEN_STORAGE_COURT_GROUP_1_5","claims":{"minimum_area_m2":national(6.0,"T4-4-5-8-3-6","4-5-8-3-6",78,65),"minimum_width_m":national(2.0,"T4-4-5-8-3-6","4-5-8-3-6",78,65)},"applicability":"BUILDING_GROUP_1_5_AND_EXCLUSIVE_KITCHEN_OR_STORAGE"},
    {"id":"OPPOSING_WINDOWS_INDEPENDENT_OCCUPANCIES","claim":national(3.0,"T4-4-5-8-3-10","4-5-8-3-10",79,66)},
    {"id":"SKYLIGHT_MAX_REQUIRED_LIGHT_SHARE","status":"UNRESOLVED_SOURCE_REQUIRED","requested_value":"50%","reason":"Not present in current verified Topic 4 evidence registry; not enforced"},
]


DAYLIGHT_SOURCE_QUALITY = {"PUBLIC_STREET":100,"PUBLIC_WAY":100,"PRIVATE_YARD":90,"REAR_YARD":85,"COURTYARD":75,"TERRACE_TO_VALID_OPEN_SPACE":70,"VALID_LIGHTWELL":55,"BORROWED_OPEN_PLAN_DAYLIGHT":35,"ROOM_TO_ROOM_WINDOW":0,"WINDOW_TO_COMMON_CORRIDOR":0,"CONSTRAINED_NEIGHBOR_EDGE":0}


@dataclass
class Resolution:
    space_type: str
    jurisdiction: str | None
    knowledge: dict
    applied_rules: list[dict]
    warnings: list[str]

    def to_dict(self) -> dict:
        return {"space_type":self.space_type,"jurisdiction":self.jurisdiction,"knowledge":self.knowledge,"applied_rules":self.applied_rules,"warnings":self.warnings}


class ArchitecturalKnowledgeResolver:
    """Resolve space knowledge without allowing heuristics to override law."""
    precedence = ("USER_REQUESTED_PROJECT_RULE", "MINAB_LOCAL_VERIFIED_RULE", "IRAN_NATIONAL_VERIFIED_REGULATION", "PROJECT_CONTRACT", "ARCHITECTURAL_DESIGN_HEURISTIC", "GLOBAL_REFERENCE_HEURISTIC")

    @classmethod
    def resolve(cls, space_type: str, jurisdiction: str | None = None,
                project_contract: dict | None = None, user_requirements: dict | None = None) -> dict:
        key = space_type.upper()
        if key not in SPACE_SPECS:
            raise KeyError(f"UNKNOWN_SPACE_TYPE:{space_type}")
        warnings, applied = [], []
        knowledge = deepcopy(SPACE_SPECS[key])
        for rule in NATIONAL_DAYLIGHT_RULES:
            if rule.get("status") == "UNRESOLVED_SOURCE_REQUIRED":
                warnings.append(rule["id"] + ":UNRESOLVED_SOURCE_REQUIRED")
            elif key in {"LIVING_RECEPTION","GENERAL_HALL","FAMILY_HALL","DINING","BEDROOM_SINGLE","BEDROOM_DOUBLE","MASTER_BEDROOM_SLEEPING"}:
                applied.append(rule)
        if (jurisdiction or "").upper() == "MINAB":
            applied.extend(MINAB_OVERLAY["rules"])
            warnings.extend(x["id"] + ":UNRESOLVED_LOCAL_RULE" for x in MINAB_OVERLAY["unresolved"])
        for channel, data, provenance in (("project_contract", project_contract or {}, Provenance.PROJECT_CONTRACT), ("user_requirements", user_requirements or {}, Provenance.USER_REQUESTED_PROJECT_RULE)):
            for field, value in data.items():
                if field.startswith("minimum_") and field in knowledge.get("clear_dimension_requirements",{}).get("verified_regulation",{}):
                    legal = knowledge["clear_dimension_requirements"]["verified_regulation"][field]["value"]
                    if isinstance(value,(int,float)) and value < legal:
                        warnings.append(f"{channel}:{field}:REJECTED_BELOW_VERIFIED_REGULATION")
                        continue
                knowledge[field] = claim(value, provenance, f"{channel.upper()}:{field}")
                applied.append({"field":field,"claim":knowledge[field]})
        return Resolution(key, jurisdiction, knowledge, applied, warnings).to_dict()

    @staticmethod
    def validate_circulation(spaces: dict[str,str], edges: Iterable[tuple[str,str,str]]) -> dict:
        failures, adjacency = [], {k:[] for k in spaces}
        for a,b,kind in edges:
            if kind not in EDGE_TYPES: failures.append(f"UNKNOWN_EDGE_TYPE:{kind}")
            if a not in spaces or b not in spaces: failures.append(f"UNKNOWN_NODE:{a}:{b}"); continue
            adjacency[a].append(b); adjacency[b].append(a)
        for node, semantic in spaces.items():
            if semantic in NON_TRANSIT and len(adjacency[node]) > 1:
                failures.append(f"FORBIDDEN_TRANSIT_NODE:{node}:{semantic}")
            if semantic == "PRIVATE_HALL_CORRIDOR" and len(adjacency[node]) < 2:
                failures.append(f"UNJUSTIFIED_CORRIDOR:{node}")
            if semantic == "PARKING_BAY" and not any(spaces.get(n)=="MANEUVER_ZONE" for n in adjacency[node]):
                failures.append(f"PARKING_WITHOUT_MANEUVER:{node}")
        return {"passed":not failures,"failures":sorted(set(failures)),"adjacency":adjacency}

    @staticmethod
    def assess_daylight(space_type: str, source_type: str, jurisdiction: str | None = None,
                        source_legal: bool | None = None, boundary_shared: bool = True,
                        open_plan_same_field: bool = False) -> dict:
        source = source_type.upper(); invalid = source in {"ROOM_TO_ROOM_WINDOW","WINDOW_TO_COMMON_CORRIDOR","CONSTRAINED_NEIGHBOR_EDGE"}
        if source == "BORROWED_OPEN_PLAN_DAYLIGHT" and not open_plan_same_field: invalid = True
        if source in {"VALID_LIGHTWELL","COURTYARD"} and not boundary_shared: invalid = True
        legal = bool(source_legal) if source_legal is not None else (not invalid and source not in {"BORROWED_OPEN_PLAN_DAYLIGHT"})
        warnings = []
        if (jurisdiction or "").upper() == "MINAB": warnings.extend(x["id"] for x in MINAB_OVERLAY["unresolved"])
        return {"space_type":space_type,"source_type":source,"DAYLIGHT_LEGALITY":{"passed":legal,"jurisdiction":jurisdiction,"invalid_default":invalid,"warnings":warnings},"DAYLIGHT_ARCHITECTURAL_QUALITY":{"score":DAYLIGHT_SOURCE_QUALITY.get(source,10),"source_quality_rank":sorted(DAYLIGHT_SOURCE_QUALITY,key=DAYLIGHT_SOURCE_QUALITY.get,reverse=True).index(source)+1 if source in DAYLIGHT_SOURCE_QUALITY else None,"provenance":Provenance.GLOBAL_REFERENCE_HEURISTIC.value}}

    @staticmethod
    def furniture_proxy(space_type: str, available_zones: Iterable[str]) -> dict:
        required = set(SPACE_SPECS[space_type]["furniture_use_zone_requirements"]); available=set(available_zones)
        missing=sorted(required-available)
        return {"passed":not missing,"missing":missing,"provenance":Provenance.ARCHITECTURAL_DESIGN_HEURISTIC.value,"evidence_id":"FUNCTIONAL_USE_ZONE_PROXY_V1"}


def ontology_document() -> dict:
    return {"schema":"ARCHITECTURAL_SPACE_KNOWLEDGE_V1","numeric_policy":"EVERY_NUMERIC_OR_NORMATIVE_ITEM_REQUIRES_PROVENANCE","space_types":deepcopy(SPACE_SPECS)}


def circulation_document() -> dict:
    return {"schema":"MULTISCALE_CIRCULATION_KNOWLEDGE_V1","edge_types":list(EDGE_TYPES),"levels":{"INTERNAL_DWELLING":["UNIT_ENTRY","PUBLIC_OR_DISTRIBUTION","PRIVATE_TRANSITION","PRIVATE_DESTINATIONS"],"COMMON_BUILDING":["COMMON_ENTRANCE","LOBBY_OR_CORE","STAIR_OR_ELEVATOR","COMMON_LANDING","COMMON_CORRIDOR_GALLERY","UNIT_ENTRY"],"EXTERNAL_PEDESTRIAN":["STREET","SITE_OR_BUILDING_ENTRY","PEDESTRIAN_ROUTE","CORE_OR_LOBBY"],"EXTERNAL_VEHICLE":["STREET","VEHICLE_ENTRY","ACCESS","MANEUVER_ZONE","PARKING_BAY"],"EXTERNAL_COMMERCIAL":["STREET","COMMERCIAL_ENTRANCE_FRONTAGE","COMMERCIAL_SHOP"]},"non_transit_semantics":sorted(NON_TRANSIT)}
