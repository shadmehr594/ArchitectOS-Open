# ==========================================================
# ArchitectOS Architectural Intent Engine v1.2
# Persian Architectural Understanding Layer
#
# Persian Text
#        |
#        ↓
# Architectural Intent JSON
#        |
#        ↓
# Render / BIM / Video / CAD
#
# NEW:
# - Dynamic floor detection
# - Basement detection
# - Multi level architecture
# - BIM compatible levels schema
#
# ==========================================================


import re

from core.chat.negation_scope_v1 import (
    is_prohibited,
)
from core.cognition.architectural_render_instruction_v1 import (
    _floor_count as _shared_floor_count,
)
from core.knowledge.architectural_knowledge_resolver import (
    ArchitecturalKnowledgeResolver
)
from core.knowledge.knowledge_merge_engine import (
    KnowledgeMergeEngine
)


# VISUAL_ACCEPTANCE_BLOCKER_REPAIR_V1 — a term the user PROHIBITED is not a
# requirement. Persian puts the prohibition after its objects ("کاربری تجاری،
# استخر و تراس اضافه نکن"), so a plain `"تجاری" in text` test classified the
# turn as commercial/mixed-use and activated commercial knowledge defaults.
# The decision reuses the shared negation layer's trailing-prohibition span;
# no new parser and no new vocabulary is introduced here.
def _term_requested(text, term):
    """True when the user AFFIRMED ``term`` and did not prohibit it."""

    if not term or term not in text:

        return False

    return not is_prohibited(text, term)


# CHAT_CODE_REQUEST_ROUTING_FIX_V1 — "ماشین" ("car") must not match the
# substring inside "ماشین‌حساب" ("calculator"). Legitimate vehicle wording is
# preserved; only the calculator word is excluded.
_CALCULATOR_WORD_RE = re.compile(r"ماشین[\s\u200c]*حساب")

class ArchitecturalIntent:


    VERSION = "1.2"



    def __init__(self):

        print(
            "🧠 ARCHITECTURAL INTENT ENGINE v1.2 ONLINE"
        )
    
        self.knowledge_resolver = ArchitecturalKnowledgeResolver()
        self.knowledge_merge_engine = KnowledgeMergeEngine()


    # ======================================================
    # EXTRACT
    # ======================================================

    def extract(
        self,
        design,
        context=None
    ):


        if not isinstance(
            design,
            dict
        ):

            design = {
                "prompt": str(design)
            }



        text = design.get(
            "prompt",
            ""
        )


        text_lower = text.lower()



        # ==================================================
        # CONTEXT
        # ==================================================

        site_context = {}

        constraints_context = {}

        if context:

            site_context = context.get(
                "site",
                {}
            )

            constraints_context = context.get(
                "site_constraints",
                {}
            )
            

        plan = design.get(
            "plan",
            {}
        )


        existing_intent = design.get(
            "architectural_intent",
            {}
        )

        print(
            "DEBUG EXISTING INTENT INPUT:",
            existing_intent
        )


        if not plan and isinstance(
            existing_intent,
            dict
        ):

            plan = existing_intent


        # ==================================================
        # BASE INTENT
        # ==================================================

        intent = {


            "building_type": "building",


            "style": None,


            "materials": [],


            "objects": [],


            "site":
                site_context,


            "environment": [],


            "functions": [],


            "spaces": [],


            "building_program": None,


            "zones": {

                "public": [],

                "private": [],

                "service": [],

                "commercial": []

            },


            "relationships": [],


            "site_constraints": {

                "coverage": None,

                "density": None,

                "setbacks": {},

                "building_position": {

                    "side": None,

                    "alignment": None,

                    "distance_from_boundary": None

                },

                "open_spaces": [],

                "access_elevations": [],

            },


            "vertical_transport": {

                "elevators": [],

                "stairs": [],

                "ramps": [],

                "escalators": []

            },

            # Project-authoritative vehicle entrance requirements.  Values are
            # intentionally empty unless supplied by the user/project contract.
            "vehicle_access": {},

            "vehicle_ramp_requirements": [],

            "parking_requirements": [],

            "window_requirements": [],

            "parking_pedestrian_requirements": [],

            "spatial_quality_requirements": {},

            "explicit_program_complete": False,

            "wall_thicknesses": {},


            "regulations": {

                "municipality": None,

                "fire_department": None,

                "optional": True

            },


            "camera": "architectural visualization",


            "mood": "professional archviz",



            # ==============================================
            # LEVEL SYSTEM
            # BIM / CAD / RENDER COMPATIBLE
            # ==============================================

            "levels": {

                "basement": 0,

                "ground": 1,

                "above_ground": 0,

                "mezzanine": 0,

                "total": 1

            },

            "site_datum": {},
            "finished_floor": {},
            "entrance_transition": {},
            "exterior_step_rules": {}


        }



        # ==================================================
        # PERSONAL CONTEXT STYLE
        # ==================================================

        context_style = None



        if isinstance(
            context,
            dict
        ):


            personal_context = context.get(
                "personal_context"
            )


            if isinstance(
                personal_context,
                dict
            ):


                preferences = personal_context.get(
                    "preferences"
                )


                if isinstance(
                    preferences,
                    dict
                ):

                    context_style = preferences.get(
                        "architecture_style"
                    )



        if context_style:

            intent["style"] = context_style



        # ==================================================
        # MERGE EXISTING INTENT
        # ==================================================

        if isinstance(
            existing_intent,
            dict
        ):


            for key, value in existing_intent.items():


                if key not in intent:

                    continue



                if isinstance(
                    value,
                    list
                ):

                    intent[key] = list(value)



                elif value is not None:

                    intent[key] = value
        # ==================================================
        # BUILDING TYPE
        # ==================================================

        if (
            "ویلا" in text
            or
            "villa" in text_lower
        ):

            intent["building_type"] = "villa"



        elif (
            "خانه" in text
            or
            "خونه" in text
            or
            "منزل" in text
            or
            "house" in text_lower
            or
            "home" in text_lower
        ):

            intent["building_type"] = "house"



        elif (
            "برج" in text
            or
            "tower" in text_lower
        ):

            intent["building_type"] = "tower"



        elif (
            "اداری" in text
            or
            "office" in text_lower
        ):

            intent["building_type"] = "office"


        elif (
            "بازار" in text
            or
            "بازارچه" in text
        ):

            intent["building_type"] = "market"


        elif (
            "پاساژ" in text
            or
            "مجتمع تجاری" in text
            or
            "مرکز خرید" in text
            or
            "مال" in text_lower
            or
            "shopping mall" in text_lower
        ):

            intent["building_type"] = "shopping_mall"



        elif (
            _term_requested(text, "تجاری")
            or
            "commercial" in text_lower
        ):

            intent["building_type"] = "commercial"


        elif (
            "پنت هاوس" in text
            or
            "penthouse" in text_lower
        ):

            intent["building_type"] = "penthouse"



        # ==================================================
        # FUNCTION DETECTION
        # USER PROGRAM REQUIREMENTS
        # ==================================================

        function_mapping = {

            "تجاری مسکونی":
                "mixed_use",

            "مسکونی تجاری":
                "mixed_use",

            "مختلط":
                "mixed_use",


            "تجاری":
                "commercial",

            "مغازه":
                "retail",

            "فروشگاه":
                "retail",

            "مغازه":
                "retail",

            "واحد تجاری":
                "retail",


            "shop":
                "retail",


            "مسکونی":
                "residential",

            "خانه":
                "residential",


            "باشگاه":
                "gym",

            "بدنسازی":
                "gym",


            "اداری":
                "office",


            "انباری":
                "storage",

            "انباری مسکونی":
                "residential_storage",

            "انباری تجاری":
                "commercial_storage",


            "پارکینگ":
                "parking",


            "رستوران":
                "restaurant",

            "کافه":
                "cafe",

            "هتل":
                "hotel",

            "اقامتی":
                "hospitality",

            "درمانگاه":
                "healthcare",

            "کلینیک":
                "healthcare",

            "مدرسه":
                "educational",

            "دانشگاه":
                "educational",

            "کارخانه":
                "industrial",

            "کارگاه":
                "industrial",

            "انبار":
                "warehouse"

        }



        for key, value in function_mapping.items():

            # VISUAL_ACCEPTANCE_BLOCKER_REPAIR_V1 — a prohibited term states no
            # function ("کاربری تجاری … اضافه نکن" must not add `commercial`).
            if key in text and not is_prohibited(text, key):

                if value not in intent["functions"]:

                    intent["functions"].append(
                        value
                    )



        # ==================================================
        # MIXED USE BUILDING
        # ==================================================

        if (
            "commercial" in intent["functions"]
            and
            "residential" in intent["functions"]
        ):

            intent["building_type"] = "mixed_use"



        # ==================================================
        # VERTICAL TRANSPORT
        # ==================================================

        if "آسانسور" in text:

            intent["vertical_transport"]["elevators"].append(
                {
                    "type":"passenger",
                    "count":1
                }
            )


        if "دو آسانسور" in text:

            intent["vertical_transport"]["elevators"] = [
                {
                    "type":"passenger",
                    "count":2
                }
            ]


        if "پله برقی" in text:

            intent["vertical_transport"]["escalators"].append(
                {
                    "count":1
                }
            )


        if "رمپ" in text:

            intent["vertical_transport"]["ramps"].append(
                {
                    "type":"vehicle"
                }
            )


        if "دو پله" in text:

            intent["vertical_transport"]["stairs"].append(
                {
                    "count":2
                }
            )


        # ==================================================
        # SPACE TO ZONE CLASSIFICATION
        # ==================================================

        space_zone_mapping = {


            # --------------------------
            # PUBLIC
            # --------------------------

            "lobby":
                "public",

            "reception":
                "public",

            "guest_room":
                "private",


            # --------------------------
            # PRIVATE
            # --------------------------

            "bedroom":
                "private",

            "master_bedroom":
                "private",

            "master_suite":
                "private",

            "dressing_room":
                "private",


            # --------------------------
            # SERVICE
            # --------------------------

            "bathroom":
                "service",

            "toilet":
                "service",

            "laundry_room":
                "service",

            "storage_room":
                "service",

            "parking_area":
                "service",


            # --------------------------
            # COMMERCIAL
            # --------------------------

            "shop":
                "commercial",

            "gym_space":
                "commercial",

            "sports_hall":
                "commercial",

            "retail":
                "commercial"

        }



        for space in intent["spaces"]:

            zone = space_zone_mapping.get(
                space
            )


            if zone:


                if space not in intent["zones"][zone]:

                    intent["zones"][zone].append(
                        space
                    )


        # ==================================================
        # ARCHITECTURAL RELATIONSHIP RULES
        # ==================================================

        spaces = intent["spaces"]


        # --------------------------
        # MASTER BEDROOM RELATIONS
        # --------------------------

        if (
            "master_bedroom" in spaces
            or
            "master_suite" in spaces
        ):

            intent["relationships"].append(
                {
                    "space": "master_suite",
                    "near": [
                        "bathroom",
                        "walk_in_closet"
                    ],
                    "zone": "private"
                }
            )



        # --------------------------
        # BEDROOM PRIVACY
        # --------------------------

        if (
            "bedroom" in spaces
        ):

            intent["relationships"].append(
                {
                    "space": "bedroom",
                    "requirement":
                        "private_zone_separation"
                }
            )



        # --------------------------
        # KITCHEN / DINING
        # --------------------------

        if (
            "kitchen" in spaces
        ):

            intent["relationships"].append(
                {
                    "space": "kitchen",
                    "near": [
                        "dining",
                        "living"
                    ]
                }
            )



        # --------------------------
        # LOBBY / CIRCULATION
        # --------------------------

        if (
            "lobby" in spaces
        ):

            intent["relationships"].append(
                {
                    "space": "lobby",
                    "connected_to": [
                        "entrance",
                        "vertical_core"
                    ]
                }
            )



            # --------------------------
            # COMMERCIAL ACCESS
            # --------------------------

        if (
            "shop" in spaces
            or
            "retail" in spaces
        ):

            intent["relationships"].append(
                {
                    "space": "retail",
                    "requirement":
                        "direct_street_access"
                }
            )



        # --------------------------
        # PARKING
        # --------------------------

        if (
            "parking_area" in spaces
        ):

            intent["relationships"].append(
                {
                    "space": "parking_area",
                    "near": [
                        "entrance",
                        "street"
                    ]
                }
            )



        # --------------------------
        # SERVICE SEPARATION
        # --------------------------

        if (
            "laundry_room" in spaces
            or
            "storage_room" in spaces
        ):

            intent["relationships"].append(
                {
                    "zone": "service",
                    "requirement":
                        "separate_from_private"
                }
            )


        # ==================================================
        # SPACE ZONING INTELLIGENCE
        # ==================================================

        zone_mapping = {


            # --------------------------
            # PUBLIC
            # --------------------------

            "لابی":
                "public",

            "پذیرایی":
                "public",

            "مغازه":
                "commercial",

            "فروشگاه":
                "commercial",

            "واحد تجاری":
                "commercial",


            # --------------------------
            # PRIVATE
            # --------------------------

            "اتاق خواب":
                "private",

            "خواب":
                "private",

            "مستر":
                "private",

            "اتاق مهمان":
                "private",


            # --------------------------
            # SERVICE
            # --------------------------

            "لاندری":
                "service",

            "رختشویی":
                "service",

            "انباری":
                "service",

            "پارکینگ":
                "service",

            "تاسیسات":
                "service"

        }



        for key, zone in zone_mapping.items():


            if key in text:


                if key not in intent["zones"][zone]:

                    intent["zones"][zone].append(
                        key
                    )


        # ==================================================
        # ARCHITECTURAL SPACE RELATION RULES
        # ==================================================

        relations = []


        if (
            "مستر" in text
            or
            "اتاق مستر" in text
        ):

            relations.append({

                "space":
                    "master_suite",

                "near":

                [
                    "bathroom",
                    "walk_in_closet"
                ]

            })



        if "لاندری" in text:

            relations.append({

                "space":
                    "laundry_room",

                "near":
                [
                    "kitchen",
                    "service_area"
                ]

            })



        if "انباری" in text:

            relations.append({

                "space":
                    "storage_room",

                "near":
                [
                    "parking",
                    "service_area"
                ]

            })


        for relation in relations:

            if relation not in intent["relationships"]:

                intent["relationships"].append(
                    relation
                )



        # ==================================================
        # FLOOR / LEVEL DETECTION
        #
        # Supports:
        # دو طبقه
        # 3 طبقه
        # سه طبقه
        # دوبلکس
        # basement
        # زیرزمین
        #
        # BIM + CAD READY
        # ==================================================


        levels = intent["levels"]



        # V4.3A — M1/M2 FLOOR-COUNT PROVENANCE
        #
        # The levels schema defaults `above_ground` to 1. That default is a
        # SCHEMA value, not a user statement: a request that names no storey
        # count must not be turned into an explicit one-floor building.
        #
        # `explicit_floor_value` is therefore set ONLY where a numeral is
        # parsed next to a floor noun, and it is the sole source of
        # `intent["floors"]` (the key PromptBuilder already reads). Keeping the
        # two apart is what prevents an implicit default from masquerading as
        # a requested floor count.
        explicit_floor_value = None
        explicit_floor_raw = ""



        # ------------------------------
        # Basement
        # ------------------------------

        if (
            "زیرزمین" in text
            or
            "basement" in text_lower
            or
            "underground" in text_lower
        ):

            levels["basement"] = 1



        # ------------------------------
        # Duplex
        # ------------------------------

        if (
            "دوبلکس" in text
            or
            "duplex" in text_lower
        ):

            levels["above_ground"] = max(
                levels["above_ground"],
                2
            )

        if (
            "تریپلکس" in text
            or
            "triplex" in text_lower
        ):

            levels["above_ground"] = max(
                levels["above_ground"],
                3
            )



        # ------------------------------
        # Explicit Floor Count — shared owner
        #
        # ENGLISH_FLOOR_COUNT_PARSER_PARITY_V1: Persian words, Persian/ASCII
        # digits and English words all use the render-instruction parser's
        # existing number scan and adjacency grammar. Both consumers therefore
        # share the same case, separator and fail-closed conflict behaviour.
        # ------------------------------

        import re



        parsed_floor = _shared_floor_count(text)

        if parsed_floor:

            levels["above_ground"] = int(
                parsed_floor["value"]
            )

            explicit_floor_value = levels["above_ground"]

            explicit_floor_raw = parsed_floor["raw"]

        basement_words = {
            "یک": 1, "دو": 2, "سه": 3, "چهار": 4,
            "پنج": 5, "شش": 6,
        }
        basement_match = re.search(
            r"(?:(\d+)|(یک|دو|سه|چهار|پنج|شش))\s*(?:طبقه\s*)?(?:زیرزمین|زیر زمین)",
            text,
        )
        if basement_match:
            levels["basement"] = (
                int(basement_match.group(1))
                if basement_match.group(1)
                else basement_words[basement_match.group(2)]
            )
            # A floor count attached to «زیرزمین» is not an above-ground
            # storey count. Preserve the default unless another explicit
            # above-ground count is present.
            basement_phrase = basement_match.group(0)
            remaining_text = text.replace(basement_phrase, "")
            if not re.search(r"(?:روی همکف|بالای همکف|طبقه روی زمین)", remaining_text):
                levels["above_ground"] = 1
                # V4.3A — the numeral that produced `explicit_floor_value` may
                # have been the BASEMENT count ("دو طبقه زیرزمین"). Only clear
                # it when the parsed span actually sits inside the basement
                # phrase; a separate above-ground count ("۳۰ طبقه و ۲ طبقه
                # زیرزمین") must survive.
                if explicit_floor_raw and explicit_floor_raw in basement_phrase:
                    explicit_floor_value = None
                    explicit_floor_raw = ""



        # ------------------------------
        # Commercial Mezzanine
        # ------------------------------

        if (
            "نیم طبقه" in text
            or "نیم‌طبقه" in text
            or "mezzanine" in text_lower
            or "split level" in text_lower
        ):
            levels["mezzanine"] = 1

        if (
            "نیم طبقه تجاری" in text
            or
            "نیم‌طبقه تجاری" in text
            or
            "commercial mezzanine" in text_lower
        ):

            if "commercial_mezzanine" not in intent["spaces"]:

                intent["spaces"].append(
                    "commercial_mezzanine"
                )


            if "retail_mezzanine" not in intent["functions"]:

                intent["functions"].append(
                    "retail_mezzanine"
                )

        


        # ------------------------------
        # Final Level Calculation
        # ------------------------------

        if levels["above_ground"] > 0:

            levels["ground"] = 1



        levels["total"] = (
            levels["basement"]
            +
            levels["above_ground"]
        )



        # ==================================================
        # STYLE
        #
        # KNOWLEDGE_RECOVERY_01 — ZWNJ-INSENSITIVE VIEW
        #
        # Persian compound style names are written with and
        # without the zero-width non-joiner ("نئوکلاسیک" /
        # "نئو کلاسیک"). The style tests below match against
        # this view so both spellings resolve identically.
        # It is used for STYLE matching only; nothing else in
        # this method is changed.
        # ==================================================

        style_text = text.replace("\u200c", "")

        if (
            "مدرن" in text
            or
            "modern" in text_lower
        ):

            intent["style"] = "modern"



        if (
            "لوکس" in text
            or
            "luxury" in text_lower
        ):

            intent["style"] = "luxury"



        if (
            "مینیمال" in text
            or
            "minimal" in text_lower
        ):

            intent["style"] = "minimal"



        if (
            "سنتی" in text
            or
            "ایرانی" in text
            or
            "traditional" in text_lower
        ):

            intent["style"] = "traditional"



        if (
            "کلاسیک" in text
            or
            "classic" in text_lower
        ):

            intent["style"] = "classic"



        # ==================================================
        # STYLE — ROMAN CLASSIC
        #
        # KNOWLEDGE_RUNTIME_CONNECTION_V2 — the ontology keys this family as
        # "roman_classic", but the generic classic test above also matched
        # "Roman classic" (it contains "classic"), so the canonical record was
        # never reached and the request degraded to plain "classic". This block
        # runs AFTER the classic block so the specific family owns the result,
        # exactly like the neoclassical block below.
        # ==================================================

        if (
            "roman classic" in text_lower
            or
            "roman classical" in text_lower
            or
            "roman-classic" in text_lower
            or
            "کلاسیک رومی" in style_text
            or
            "رومی کلاسیک" in style_text
        ):

            intent["style"] = "roman_classic"

        # ==================================================
        # STYLE — ISLAMIC ARCHITECTURE
        #
        # KNOWLEDGE_RUNTIME_CONNECTION_V2 — the Persian understanding module
        # already resolved "معماری اسلامی" to the canonical id, but this
        # intent extractor had no branch for it, so the style was dropped
        # between understanding and the compiled prompt (understand said
        # islamic_architecture, intent said None).
        # ==================================================

        if (
            "معماری اسلامی" in style_text
            or
            "سبک اسلامی" in style_text
            or
            "islamic architecture" in text_lower
            or
            "islamic style" in text_lower
        ):

            intent["style"] = "islamic_architecture"

        # ==================================================
        # STYLE — NEOCLASSICAL
        #
        # KNOWLEDGE_RECOVERY_01 — SUBSTRING COLLISION FIX
        #
        # "نئوکلاسیک" CONTAINS "کلاسیک", so the generic classic
        # test above also matched a neoclassical request and the
        # ontology's neoclassical record (columns, pilasters,
        # stone_frames, cornices, classical_windows) was never
        # reached. This block runs AFTER the classic block so the
        # specific style wins, and it never matches a plain
        # "کلاسیک" request.
        # ==================================================

        if (
            "نئوکلاسیک" in style_text
            or
            "نوکلاسیک" in style_text
            or
            "نئو کلاسیک" in style_text
            or
            "neoclassic" in text_lower
            or
            "neo-classic" in text_lower
            or
            "neo classic" in text_lower
        ):

            intent["style"] = "neoclassical"



        # ==================================================
        # STYLE — IRANIAN TRADITIONAL
        #
        # KNOWLEDGE_RECOVERY_01 — REGIONAL STYLE RESOLUTION
        #
        # The style ontology keys this style as
        # "iranian_traditional"; the generic token "traditional"
        # is NOT a key, so an unqualified traditional request
        # previously resolved to no facade knowledge at all.
        #
        # It is resolved here ONLY from Iranian-specific evidence.
        # An unqualified "سنتی" / "traditional" request keeps the
        # non-regional token "traditional" and is deliberately NOT
        # assigned a regional style.
        # ==================================================

        if (
            "سنتی ایرانی" in style_text
            or
            "ایرانی" in style_text
            or
            "بومی" in style_text
            or
            "iranian traditional" in text_lower
            or
            "persian architecture" in text_lower
            or
            "iranian architecture" in text_lower
        ):

            intent["style"] = "iranian_traditional"


        # VISUAL_KNOWLEDGE_INTEGRATION_COMPLETION_V1 — keep this existing
        # route aligned with the canonical style ids consumed by
        # SharedFacadeKnowledgeResolverV1.  Specific family evidence runs
        # after the generic classic/traditional checks so it owns the result.
        if (
            "آجر قزاقی" in style_text
            or "آجرقزاقی" in style_text
            or "نمای آجری ایرانی" in style_text
            or "آجرکاری ایرانی" in style_text
            or "qazaghi brick" in text_lower
            or "qazaqi brick" in text_lower
            or "iranian brick" in text_lower
            or "persian brick" in text_lower
        ):

            intent["style"] = "iranian_brick"

        if (
            "بوزار" in style_text
            or "beaux arts" in text_lower
            or "beaux-arts" in text_lower
        ):

            intent["style"] = "beaux_arts"

        if (
            "امپراتوری دوم" in style_text
            or "هوسمان" in style_text
            or "second empire" in text_lower
            or "haussmann" in text_lower
        ):

            intent["style"] = "second_empire"

        if (
            "پروانس" in style_text
            or "روستایی فرانسه" in style_text
            or "french provincial" in text_lower
            or "provencal" in text_lower
        ):

            intent["style"] = "french_provincial"

        if (
            "کلاسیک فرانسوی" in style_text
            or "نمای فرانسوی" in style_text
            or "french classical" in text_lower
        ):

            intent["style"] = "french_classical"

        if "معاصر" in style_text or "contemporary" in text_lower:

            intent["style"] = "modern"



        if (
            "روستیک" in text
            or
            "rustic" in text_lower
        ):

            intent["style"] = "rustic"
        

        # ==================================================
        # OBJECTS
        # ==================================================

        if (
            "خودرو" in text
            or
            (
                "ماشین" in text
                and not _CALCULATOR_WORD_RE.search(text)
            )
            or
            "car" in text_lower
        ):


            car = "modern car"



            if (
                "اسپرت" in text
                or
                "sport" in text_lower
            ):

                car = "sports car"



            if (
                "لوکس" in text
                or
                "luxury" in text_lower
            ):

                car = "luxury car"



            if "قرمز" in text:

                car = "red " + car


            elif "مشکی" in text:

                car = "black " + car


            elif "سفید" in text:

                car = "white " + car


            elif "آبی" in text:

                car = "blue " + car



            intent["objects"].append(
                car
            )



        # ==================================================
        # ENVIRONMENT
        # ==================================================

        if (
            "رودخانه" in text
            or
            "river" in text_lower
        ):

            intent["environment"].append(
                "riverside landscape"
            )



        if (
            "خروشان" in text
            or
            "flowing" in text_lower
            or
            "fast" in text_lower
        ):

            intent["environment"].append(
                "fast flowing river"
            )



        if (
            "جنگل" in text
            or
            "forest" in text_lower
        ):

            intent["environment"].append(
                "forest landscape"
            )



        if (
            "کوه" in text
            or
            "mountain" in text_lower
        ):

            intent["environment"].append(
                "mountain landscape"
            )



        # ==================================================
        # SITE
        # ==================================================

        if "حیاط" in text:
            site_features = intent["site"].setdefault("features", [])
            if "courtyard" not in site_features:
                site_features.append("courtyard")

            intent["environment"].append(
                "landscape garden"
            )


        if (
            "جلوی ویلا" in text
            or
            "جلوی خانه" in text
        ):
            site_features = intent["site"].setdefault("features", [])
            if "front yard" not in site_features:
                site_features.append("front yard")


        # ======================================================
        # PARKING INTELLIGENCE EXTRACTION
        # ======================================================

        parking_keywords = [
            "پارکینگ",
            "parking",
            "parking area"
        ]


        if any(
            k in text_lower or k in text
            for k in parking_keywords
        ):

            if "parking_area" not in intent["spaces"]:
                intent["spaces"].append(
                    "parking_area"
                )


            if "parking" not in intent["functions"]:
                intent["functions"].append(
                    "parking"
                )

            parking_count_match = re.search(
                r"(\d+)\s*(?:واحد\s*)?(?:پارکینگ|جای\s*پارک)",
                text,
            )
            if parking_count_match:
                intent["parking"] = {
                    "required_spaces": int(parking_count_match.group(1)),
                    "ramp_required": (
                        "رمپ" in text or "ramp" in text_lower
                    ),
                }


            if (
                "زیرزمین" in text
                or
                "basement" in text_lower
                or
                "زیر زمین" in text
            ):

                intent["levels"]["basement"] = 1


            if not isinstance(
                intent.get("site"),
                dict
            ):
                intent["site"] = {}

            site_features = intent["site"].setdefault(
                "features",
                []
            )


            if "driveway parking area" not in site_features:
                site_features.append(
                    "driveway parking area"
                )


        if "پارکینگ" in text:

            if "driveway parking area" not in site_features:
                site_features.append(
                    "driveway parking area"
                )


        if "روف گاردن" in text:

            if "roof garden" not in site_features:
                site_features.append(
                    "roof garden"
                )


        if "آلاچیق" in text:

            if "gazebo" not in site_features:
                site_features.append(
                    "gazebo"
                )


        if "آبنما" in text:

            if "water feature" not in site_features:
                site_features.append(
                    "water feature"
                )


        # ==================================================
        # SPACE RELATIONSHIP INTELLIGENCE
        # ==================================================

        if "relationships" not in intent:

            intent["relationships"] = []


        if (
            "master_bedroom" in intent["spaces"]
            and
            "bathroom" in intent["spaces"]
        ):

            intent["relationships"].append(
                {
                    "spaces": [
                        "master_bedroom",
                        "bathroom"
                    ],
                    "relation": "near"
                }
            )



        if (
            "master_bedroom" in intent["spaces"]
            and
            "walk_in_closet" in intent["spaces"]
        ):

            intent["relationships"].append(
                {
                    "spaces": [
                        "master_bedroom",
                        "walk_in_closet"
                    ],
                    "relation": "connected"
                }
            )



        if (
            "kitchen" in intent["spaces"]
            and
            "laundry_room" in intent["spaces"]
        ):

            intent["relationships"].append(
                {
                    "spaces": [
                        "kitchen",
                        "laundry_room"
                    ],
                    "relation": "service_connection"
                }
            )



        if (
            "lobby" in intent["spaces"]
            and
            "entrance" in intent["spaces"]
        ):

            intent["relationships"].append(
                {
                    "spaces": [
                        "entrance",
                        "lobby"
                    ],
                    "relation": "direct_access"
                }
            )


        # ==================================================
        # SPACE → ZONE CLASSIFICATION
        # ==================================================

        zone_map = {

            "lobby": "public",
            "living_room": "public",
            "reception": "public",

            "bedroom": "private",
            "master_bedroom": "private",
            "guest_room": "private",
            "walk_in_closet": "private",
            "dressing_room": "private",

            "kitchen": "service",
            "laundry_room": "service",
            "storage_room": "service",
            "toilet": "service",
            "bathroom": "service",

            "shop": "commercial",
            "commercial_mezzanine": "commercial",
            "gym_space": "commercial",
            "office_room": "commercial"
        }

        for space in intent["spaces"]:

            zone = zone_map.get(space)

            if zone:

                if space not in intent["zones"][zone]:

                    intent["zones"][zone].append(space)



        # ==================================================
        # SITE CONSTRAINT EXTRACTION
        # ==================================================

        import re

        # Site-access elevation evidence is candidate-specific.  It must not
        # be collapsed into a single building-level difference.
        site_constraints = intent.setdefault("site_constraints", {})
        access_elevations = site_constraints.setdefault(
            "access_elevations",
            [],
        )

        side_aliases = {
            "جنوبی": "south",
            "جنوب": "south",
            "شمالی": "north",
            "شمال": "north",
            "شرقی": "east",
            "شرق": "east",
            "غربی": "west",
            "غرب": "west",
        }
        access_type_aliases = {
            "معبر": "road",
            "خیابان": "main_road",
            "کوچه": "lane",
        }

        def explicit_number(raw_value):
            raw_value = str(raw_value).strip()
            if raw_value in ("صفر", "zero"):
                return 0.0
            raw_value = raw_value.replace("−", "-")
            if raw_value.startswith("منفی"):
                raw_value = "-" + raw_value[len("منفی"):].strip()
            return float(raw_value)

        access_pattern = re.compile(
            r"تراز\s*(معبر|خیابان|کوچه)\s*"
            r"(جنوبی|جنوب|شمالی|شمال|شرقی|شرق|غربی|غرب)"
            r"(?:\s*(?:برابر|مساوی|به\s*تراز))?\s*"
            r"(منفی\s*\d+(?:\.\d+)?|[-+]?\d+(?:\.\d+)?|صفر)"
        )

        parsed_accesses = []
        for access_match in access_pattern.finditer(text_lower):
            raw_type, raw_side, raw_elevation = access_match.groups()
            side = side_aliases[raw_side]
            access_type = access_type_aliases[raw_type]
            nearby_text = text_lower[
                max(0, access_match.start() - 30):access_match.end() + 45
            ]
            if raw_type == "کوچه" and "پشتی" in nearby_text:
                access_type = "rear_lane"
            elif raw_type == "معبر" and side == "south":
                access_type = "main_road"
            parsed_accesses.append(
                {
                    "id": f"{side}_{access_type}",
                    "side": side,
                    "type": access_type,
                    "elevation": explicit_number(raw_elevation),
                    "vehicle_access": True,
                    "source": "user_explicit",
                    "evidence": access_match.group(0),
                }
            )

        english_access_pattern = re.compile(
            r"(?:elevation\s*(?:of\s*)?)?"
            r"(south|north|east|west)\s*"
            r"(main\s+road|rear\s+lane|road|street|lane)"
            r"(?:\s*elevation)?\s*(?:is|=|at)?\s*"
            r"([-+]?\d+(?:\.\d+)?)"
        )
        for access_match in english_access_pattern.finditer(text_lower):
            side, raw_type, raw_elevation = access_match.groups()
            access_type = raw_type.replace(" ", "_")
            if access_type == "street":
                access_type = "main_road"
            parsed_accesses.append(
                {
                    "id": f"{side}_{access_type}",
                    "side": side,
                    "type": access_type,
                    "elevation": explicit_number(raw_elevation),
                    "vehicle_access": True,
                    "source": "user_explicit",
                    "evidence": access_match.group(0),
                }
            )

        rear_lane_pattern = re.compile(
            r"کوچه\s*پشتی\s*(?:با\s*)?تراز\s*"
            r"(منفی\s*\d+(?:\.\d+)?|[-+]?\d+(?:\.\d+)?|صفر)"
            r"(?:\s*دارد|\s*است)?"
        )
        for access_match in rear_lane_pattern.finditer(text_lower):
            # "rear" is explicit evidence; a cardinal side is intentionally
            # not invented when the user did not provide one.
            parsed_accesses.append(
                {
                    "id": "rear_lane",
                    "side": None,
                    "type": "rear_lane",
                    "elevation": explicit_number(access_match.group(1)),
                    "vehicle_access": True,
                    "source": "user_explicit",
                    "evidence": access_match.group(0),
                }
            )

        for access in parsed_accesses:
            access_elevations[:] = [
                existing for existing in access_elevations
                if existing.get("id") != access["id"]
            ]
            access_elevations.append(access)

        parking_elevation_match = re.search(
            r"تراز\s*پارکینگ(?:\s*(زیرزمین|همکف|basement|ground))?"
            r"(?:\s*(?:برابر|مساوی|به\s*تراز))?\s*"
            r"(منفی\s*\d+(?:\.\d+)?|[-+]?\d+(?:\.\d+)?|صفر)",
            text_lower,
        )
        if not parking_elevation_match:
            parking_elevation_match = re.search(
                r"(?:basement\s+)?parking(?:\s+level)?\s*"
                r"(?:elevation\s*)?(?:is|=|at)?\s*([-+]?\d+(?:\.\d+)?)",
                text_lower,
            )

        if parking_elevation_match:
            groups = parking_elevation_match.groups()
            raw_level = groups[0] if len(groups) > 1 else None
            raw_elevation = groups[-1]
            parking = intent.setdefault("parking", {})
            parking["level"] = (
                "basement"
                if raw_level in ("زیرزمین", "basement") or "زیرزمین" in parking_elevation_match.group(0)
                else "ground"
                if raw_level in ("همکف", "ground")
                else parking.get("level")
            )
            parking["elevation"] = explicit_number(raw_elevation)
            parking["elevation_source"] = "user_explicit"

        slope_percent_match = re.search(
            r"(?:شیب\s*مجاز\s*(?:رمپ)?|allowable\s+(?:vehicle\s+)?ramp\s+slope)"
            r"\s*(\d+(?:\.\d+)?)\s*(?:درصد|٪|%)",
            text_lower,
        )
        if slope_percent_match:
            intent["allowable_vehicle_ramp_slope_percent"] = float(
                slope_percent_match.group(1)
            )

        minimum_ramp_width_match = re.search(
            r"(?:حداقل\s*عرض\s*رمپ|minimum\s+(?:vehicle\s+)?ramp\s+width)"
            r"\s*(\d+(?:\.\d+)?)\s*(?:متر|m)?",
            text_lower,
        )
        if minimum_ramp_width_match:
            intent["minimum_vehicle_ramp_width"] = float(
                minimum_ramp_width_match.group(1)
            )

        turning_radius_match = re.search(
            r"(?:شعاع\s*گردش\s*(?:خودرو)?|vehicle\s+turning\s+radius)"
            r"\s*(\d+(?:\.\d+)?)\s*(?:متر|m)?",
            text_lower,
        )
        if turning_radius_match:
            intent["vehicle_turning_radius"] = float(
                turning_radius_match.group(1)
            )

        # User-selectable wall type thicknesses. Values are stored in metres
        # and restricted downstream to common 10/15/20/30/35 cm types.
        wall_patterns = {
            "interior": r"(?:دیوار\s*(?:داخلی|تیغه|پارتیشن)).{0,18}?(10|15|20|30|35)\s*(?:سانت|cm)",
            "exterior": r"(?:دیوار\s*(?:خارجی|پیرامونی|نما)).{0,18}?(10|15|20|30|35)\s*(?:سانت|cm)",
            "yard": r"(?:دیوار\s*(?:حیاط|محوطه|پلاک)).{0,18}?(10|15|20|30|35)\s*(?:سانت|cm)",
        }
        for wall_role, pattern in wall_patterns.items():
            wall_match = re.search(pattern, text_lower)
            if wall_match:
                intent["wall_thicknesses"][wall_role] = int(wall_match.group(1)) / 100.0

        road_width_match = re.search(
            r"(?:معبر|خیابان|کوچه)(?:\s+(?:شمالی|جنوبی|شرقی|غربی|به\s*عرض|عرض))*\s*(\d+(?:\.\d+)?)\s*(?:متر|m)",
            text_lower,
        )
        if road_width_match:
            intent["site_constraints"]["road"] = {
                "width": float(road_width_match.group(1))
            }
        if "دسترسی خودرو" in text or "ورودی خودرو" in text:
            intent["site_constraints"]["vehicle_access"] = {"required": True}
        if "دسترسی پیاده" in text or "ورودی پیاده" in text:
            intent["site_constraints"]["pedestrian_access"] = {"required": True}
        if "فضای سبز" in text or "محوطه سبز" in text:
            intent["site_constraints"]["landscape"] = {"required": True}
        if "دیوار حیاط" in text or "دیوار محوطه" in text:
            intent["site_constraints"]["boundary_wall"] = {
                "required": True,
                "thickness": intent["wall_thicknesses"].get("yard", 0.20),
            }

        # Site dimensions such as «زمین 20 در 30».
        site_size = re.search(
            r"(?:زمین|پلاک|سایت)\s*(\d+(?:\.\d+)?)\s*(?:در|x|×)\s*(\d+(?:\.\d+)?)",
            text_lower,
        )
        if site_size:
            intent["site"]["width"] = float(site_size.group(1))
            intent["site"]["depth"] = float(site_size.group(2))
            intent["site"]["area"] = (
                intent["site"]["width"] * intent["site"]["depth"]
            )

        if (
            (_term_requested(text, "تجاری") and _term_requested(text, "مسکونی"))
            or "mixed use" in text_lower
            or "mixed-use" in text_lower
        ):
            intent["building_type"] = "mixed_use_commercial_residential"
            intent["functions"] = list(dict.fromkeys(
                intent["functions"] + ["commercial", "residential"]
            ))


        # ------------------------------
        # Coverage / سطح اشغال
        # ------------------------------

        coverage_match = re.search(
            r"(\d+)\s*(?:درصد|٪|%)",
            text
        )

        if coverage_match:

            value = int(
                coverage_match.group(1)
            )

            if 10 <= value <= 100:

                intent["site_constraints"]["coverage"] = (
                    value / 100
                )



        # ------------------------------
        # Density / تراکم
        # ------------------------------

        density_match = re.search(
            r"تراکم\s*(\d+)",
            text
        )

        if density_match:

            intent["site_constraints"]["density"] = int(
                density_match.group(1)
            )



        # ------------------------------
        # Setbacks / عقب نشینی
        # ------------------------------

        directions = {

            "شمال": "north",

            "جنوب": "south",

            "شرق": "east",

            "غرب": "west"

        }


        for fa, en in directions.items():

            pattern = (
                r"(?:عقب[‌ ]?نشینی|فاصله)\s*"
                + fa
                + r".{0,12}?(\d+(?:\.\d+)?)\s*(?:متر|m)"
            )


            match = re.search(
                pattern,
                text
            )


            if match:

                intent["site_constraints"]["setbacks"][en] = float(
                    match.group(1)
                )



        # ------------------------------
        # Yards / حیاط
        # ------------------------------

        yard_match = re.search(
            r"(حیاط خلوت|حیاط جانبی|پاسیو)(?:.{0,30}?عرض\s*|\s*)(\d+(?:\.\d+)?)\s*متر(?!\s*مربع)",
            text
        )


        if yard_match:

            intent["site_constraints"]["open_spaces"].append({

                "type": yard_match.group(1),

                "width": float(
                    yard_match.group(2)
                )

            })



        # ------------------------------
        # Building Position / محل احداث بنا در سایت
        # ------------------------------

        position_mapping = {

            "شمال زمین": "north",
            "ضلع شمال زمین": "north",
            "ضلع شمال": "north",
            "سمت شمال": "north",

            "جنوب زمین": "south",
            "ضلع جنوب زمین": "south",
            "ضلع جنوب": "south",
            "سمت جنوب": "south",

            "شرق زمین": "east",
            "ضلع شرق زمین": "east",
            "ضلع شرق": "east",
            "سمت شرق": "east",

            "غرب زمین": "west",
            "ضلع غرب زمین": "west",
            "ضلع غرب": "west",
            "سمت غرب": "west",

            "وسط زمین": "center",
            "مرکز زمین": "center"

                }



        for key, side in position_mapping.items():

            if key in text:

                intent["site_constraints"]["building_position"]["side"] = side

                break



        # ------------------------------
        # Alignment / نحوه قرارگیری
        # ------------------------------

        if (
            "چسبیده" in text
            or
            "متصل" in text
            or
           "بدون فاصله" in text
        ):

            intent["site_constraints"]["building_position"]["alignment"] = (
                "attached"
            )



        elif (
            "با فاصله" in text
            or
            "عقب تر" in text
            or
            "عقب‌تر" in text
        ):

            intent["site_constraints"]["building_position"]["alignment"] = (
                "setback"
            )



        # ------------------------------
        # Distance From Boundary
        # فاصله بنا از مرز زمین
        # ------------------------------

        distance_match = re.search(
            r"(?:فاصله|عقب نشینی|عقب‌نشینی).*?(\d+(?:\.\d+)?)\s*(?:متر|m)",
            text
        )


        if distance_match:

            intent["site_constraints"]["building_position"]["distance_from_boundary"] = float(
                distance_match.group(1)
            )



        # ------------------------------
        # Light Wells / نورگیر
        # ------------------------------

        lightwell = re.search(
            r"نورگیر.*?(?:طبقه\s*)?(\d+).*?(?:تا).*?(?:طبقه\s*)?(\d+)",
            text
        )


        if lightwell:

            intent["site_constraints"]["open_spaces"].append({

                "type": "light_well",

                "from_floor": int(
                    lightwell.group(1)
                ),

                "to_floor": int(
                    lightwell.group(2)
                )

            })



        # ==================================================
        # PLAN ENRICHMENT
        # ==================================================

        if isinstance(
            plan,
            dict
        ):


            print(
                "DEBUG ARCH INTENT PLAN:",
                plan
            )



            if (
                plan.get("building_type")
                and
                intent["building_type"] == "building"
            ):

                intent["building_type"] = plan["building_type"]



            if (
                plan.get("style")
                and
                not intent["style"]
            ):

                intent["style"] = plan["style"]



            # LEVEL MERGE
            if isinstance(
                plan.get("levels"),
                dict
            ):

                for key, value in plan["levels"].items():

                    if key in intent["levels"]:

                        intent["levels"][key] = value



            for key in [
                "materials",
                "objects",
                "relationships"
            ]:


                values = plan.get(
                    key,
                    []
                )


                if isinstance(
                    values,
                    list
                ):


                    for item in values:

                        if item not in intent[key]:

                            intent[key].append(
                                item
                            )

            plan_site = plan.get("site")
            if isinstance(plan_site, dict):
                intent["site"].update(plan_site)



        # ==================================================
        # FINAL BIM LEVEL NORMALIZATION
        # ==================================================

        if intent["levels"]["above_ground"] <= 0:

            intent["levels"]["above_ground"] = 1



        if intent["levels"]["ground"] <= 0:

            intent["levels"]["ground"] = 1



        intent["levels"]["total"] = (
            intent["levels"]["basement"]
            +
            intent["levels"]["above_ground"]
        )


        # ==================================================
        # KNOWLEDGE RESOLUTION
        # ==================================================

        intent = self.knowledge_resolver.resolve(
            text,
            intent
        )


        intent = self.knowledge_merge_engine.merge(
            intent
        )

        # Explicit user constraints remain authoritative after knowledge
        # enrichment; category defaults must not overwrite mixed use or the
        # requested number of basement levels.
        if (
            (_term_requested(text, "تجاری") and _term_requested(text, "مسکونی"))
            or "mixed use" in text_lower
            or "mixed-use" in text_lower
        ):
            intent["building_type"] = "mixed_use_commercial_residential"
        if basement_match:
            intent["levels"]["basement"] = (
                int(basement_match.group(1))
                if basement_match.group(1)
                else basement_words[basement_match.group(2)]
            )
            intent["levels"]["total"] = (
                intent["levels"]["basement"]
                + intent["levels"]["above_ground"]
            )

        # ==================================================
        # EXPLICIT MIXED-USE PROGRAM CONTRACT
        # Keep detailed user requirements separate from broad typology
        # inference so downstream design/revision engines can apply them.
        # ==================================================
        program_constraints = {}

        road_side = next(
            (side for word, side in (("جنوب", "south"), ("شمال", "north"), ("شرق", "east"), ("غرب", "west"))
             if re.search(rf"(?:معبر|خیابان|کوچه)\s*(?:در\s*)?(?:ضلع\s*)?{word}|{word}\s*(?:پلاک\s*)?(?:معبر|خیابان|کوچه)", text)),
            None,
        )
        neighbors = []
        for word, side in (("شمال", "north"), ("جنوب", "south"), ("شرق", "east"), ("غرب", "west")):
            if re.search(rf"{word}.{{0,18}}(?:همسایه|پلاک)|(?:همسایه|پلاک).{{0,18}}{word}", text):
                neighbors.append(side)
        if road_side or neighbors:
            program_constraints["site_edges"] = {"road_side": road_side, "neighbor_sides": neighbors}

        placement_match = re.search(r"(?:ساختمان|بنا|احداث بنا).{0,24}?(شمال|جنوب|شرق|غرب)(?:\s*(?:پلاک|زمین))?", text)
        if placement_match:
            side_map = {"شمال": "north", "جنوب": "south", "شرق": "east", "غرب": "west"}
            placement_side = side_map[placement_match.group(1)]
            intent["site_constraints"]["building_position"]["side"] = placement_side
            program_constraints["building_position"] = placement_side

        coverage_by_level = {}
        ground_coverage = re.search(r"(?:همکف).{0,35}?(\d+(?:\.\d+)?)\s*(?:درصد|٪|%)\s*(?:سطح اشغال)?|(?:سطح اشغال).{0,20}?(?:همکف).{0,15}?(\d+(?:\.\d+)?)", text)
        residential_coverage = re.search(r"(?:طبقات\s*مسکونی|مسکونی).{0,35}?(\d+(?:\.\d+)?)\s*(?:درصد|٪|%)\s*(?:سطح اشغال)?", text)
        if ground_coverage:
            coverage_by_level["ground"] = float(ground_coverage.group(1) or ground_coverage.group(2)) / 100.0
        if residential_coverage:
            coverage_by_level["residential"] = float(residential_coverage.group(1)) / 100.0
        if coverage_by_level:
            program_constraints["coverage_by_level"] = coverage_by_level

        commercial_area = re.search(r"(?:واحد\s*)?تجاری.{0,18}?(\d+(?:\.\d+)?)\s*(?:متر\s*مربع|مترمربع|m2)", text_lower)
        if commercial_area:
            program_constraints["commercial"] = {"area": float(commercial_area.group(1)), "floor": "ground"}

        yard_area = re.search(r"حیاط\s*خلوت.{0,24}?(\d+(?:\.\d+)?)\s*(?:متر\s*مربع|مترمربع|m2)", text_lower)
        yard_width = re.search(r"(?:عرض\s*حیاط\s*خلوت|حیاط\s*خلوت.{0,35}?عرض).{0,12}?(\d+(?:\.\d+)?)\s*(?:متر|m)", text_lower)
        if yard_area or yard_width:
            program_constraints["backyard"] = {
                "side": "north" if "شمال" in text else None,
                "area": float(yard_area.group(1)) if yard_area else None,
                "width": float(yard_width.group(1)) if yard_width else None,
            }

        units_by_floor = {}
        word_counts = {"یک": 1, "دو": 2, "سه": 3, "چهار": 4}
        for floor_word, floor_name in (("اول", "F1"), ("دوم", "F2"), ("سوم", "F3")):
            match = re.search(rf"طبقه\s*{floor_word}.{{0,25}}?(\d+|یک|دو|سه|چهار)\s*واحد", text)
            if match:
                units_by_floor[floor_name] = int(match.group(1)) if match.group(1).isdigit() else word_counts[match.group(1)]
        if units_by_floor:
            program_constraints["residential_units_by_floor"] = units_by_floor
            intent["levels"]["above_ground"] = max(int(key[1:]) for key in units_by_floor)

        commercial_parking = re.search(r"(\d+|یک|دو|سه|چهار)\s*(?:واحد\s*)?پارکینگ.{0,12}?تجاری|پارکینگ.{0,12}?تجاری.{0,12}?(\d+|یک|دو|سه|چهار)", text)
        residential_parking = re.search(r"(\d+|یک|دو|سه|چهار)\s*(?:واحد\s*)?پارکینگ.{0,12}?مسکونی|پارکینگ.{0,12}?مسکونی.{0,12}?(\d+|یک|دو|سه|چهار)", text)
        def count_value(match):
            if not match:
                return None
            raw = next(group for group in match.groups() if group is not None)
            return int(raw) if raw.isdigit() else word_counts[raw]
        if commercial_parking or residential_parking:
            program_constraints["parking"] = {
                "commercial": count_value(commercial_parking),
                "residential": count_value(residential_parking),
                "location": "behind_commercial" if "پشت تجاری" in text else None,
            }

        if "خرپشته" in text or "اتاق آسانسور" in text:
            program_constraints["roof_level"] = {
                "floor": "F3", "stair_headroom": "خرپشته" in text,
                "elevator_room": "اتاق آسانسور" in text,
            }
        if "همه واحدها بالکن" in text or "تمام واحدها بالکن" in text:
            program_constraints["balcony_required_for_all_units"] = True
        projection = re.search(r"پیش[‌ ]?آمدگی.{0,25}?(\d+(?:\.\d+)?)\s*(?:متر|m)", text_lower)
        if projection:
            program_constraints["projection"] = {
                "depth": float(projection.group(1)),
                "side": "south" if "جنوب" in text else None,
                "levels": ["ground", "residential"],
            }
        if neighbors:
            program_constraints["separation_joint"] = {
                "required": True, "sides": neighbors, "basis": "building_height"
            }

        intent["program_constraints"] = program_constraints
        intent["levels"]["total"] = intent["levels"]["basement"] + intent["levels"]["above_ground"]

        signed_number = r"([+-]?\d+(?:[\.,]\d+)?)"
        datum_match = re.search(r"تراز\s*(?:حیاط|محوطه)(?:\s*مرجع)?\s*(?:=|است|برابر)?\s*" + signed_number, text)
        floor_match = re.search(r"(?:تراز\s*)?کف\s*(?:تمام[‌ ]?شده\s*)?ساختمان\s*(?:=|است|برابر)?\s*" + signed_number, text)
        platform_match = re.search(r"(?:تراز\s*)?سکوی\s*ورودی\s*(?:نیز\s*)?(?:در\s*تراز\s*)?(?:=|است|برابر)?\s*" + signed_number, text)
        riser_match = re.search(r"ارتفاع\s*(?:هر\s*)?رایزر\s*(?:=|است|برابر)?\s*" + signed_number, text)
        step_count_match = re.search(r"(\d+|یک|دو|سه|چهار)\s*پله", text)
        if datum_match:
            intent["site_datum"] = {"elevation": float(datum_match.group(1).replace(",", ".")), "source": "user_explicit", "source_evidence": datum_match.group(0)}
        if floor_match:
            intent["finished_floor"] = {"level": "F1", "elevation": float(floor_match.group(1).replace(",", ".")), "source": "user_explicit", "source_evidence": floor_match.group(0), "floor_build_up": {"status": "unresolved", "source": "no_material_or_layer_evidence"}}
        if platform_match:
            intent["entrance_transition"]["platform"] = {"elevation": float(platform_match.group(1).replace(",", ".")), "connected_to": "main_entrance", "source_evidence": platform_match.group(0)}
        if riser_match:
            intent["entrance_transition"]["riser_height"] = float(riser_match.group(1).replace(",", "."))
        if step_count_match:
            raw_count = step_count_match.group(1)
            intent["entrance_transition"]["riser_count"] = int(raw_count) if raw_count.isdigit() else word_counts[raw_count]
        if intent["entrance_transition"]:
            intent["entrance_transition"].setdefault("connected_to", "main_entrance")
            intent["entrance_transition"]["source_evidence"] = "user_explicit_exterior_entrance_transition"


        # ==================================================
        # HUMAN LEARNING REGISTRY  (READ-ONLY, ADVISORY)
        #
        # KNOWLEDGE_RECOVERY_01 — the 37 accepted human
        # architectural rules in
        # core/architecture/knowledge/
        # human_architectural_learning_registry_v1.json were not
        # reachable from the architectural reasoning path. They are
        # now read through the EXISTING read-only interface
        # (KnowledgeReadBridgeV1.learning_registry) and attached as
        # ADVISORY context on the reasoning contract.
        #
        # READ ONLY. The registry is append-only; the bridge's write
        # methods raise. Unconfirmed teaching candidates are NOT read
        # here and are NEVER promoted by this path.
        #
        # These rules are planning / reasoning constraints, not facade
        # text, so they are deliberately NOT written into any prompt
        # field: prompt_builder reads only its own named keys.
        # ==================================================

        try:

            from core.conversation.knowledge_read_bridge_v1 import (
                KnowledgeReadBridgeV1
            )

            intent["human_learning_rules"] = (
                self._relevant_human_learning_rules(
                    KnowledgeReadBridgeV1().learning_registry(),
                    text,
                    intent
                )
            )

        except Exception as e:

            print(
                "⚠️ HUMAN LEARNING REGISTRY READ SKIPPED:",
                e
            )

            intent["human_learning_rules"] = []


        # ==================================================
        # V4.3A — M2 FLOOR-COUNT PROPAGATION
        #
        # `intent["floors"]` is the key PromptBuilder already reads
        # (core/render/prompt_builder.py:333). Nothing populated it before, so
        # every render prompt fell through to `design.get("floors", 1)` and
        # asserted "single floor building" even for a 30-storey request.
        #
        # Only an EXPLICITLY stated count is written to `floors`. When the user
        # states none, the key is left absent so the existing default
        # behaviour is preserved byte for byte, and `floor_count.source`
        # records the distinction explicitly.
        # ==================================================

        if explicit_floor_value is not None:

            intent["floors"] = int(explicit_floor_value)

            intent["floor_count"] = {
                "contract": "FloorCountV1",
                "value": int(explicit_floor_value),
                "source": "user_explicit",
                "raw": explicit_floor_raw,
                "levels_above_ground": levels.get("above_ground"),
                "levels_total": levels.get("total"),
            }

        else:

            intent["floor_count"] = {
                "contract": "FloorCountV1",
                "value": None,
                "source": "unspecified",
                "raw": "",
                "levels_above_ground": levels.get("above_ground"),
                "levels_total": levels.get("total"),
            }


        # ==================================================
        # PLAN REQUIREMENTS CONNECTION V1
        #
        # Keep user-stated program facts separate from knowledge defaults and
        # from geometry claims. This is the existing intent owner's additive
        # contract for PlannerAgent; it does not generate a plan or geometry.
        # ==================================================

        plan_requirements = self._extract_plan_requirements(
            text,
            intent
        )

        if plan_requirements is not None:

            intent["plan_requirements"] = plan_requirements


        # ==================================================
        # DEBUG
        # ==================================================

        print(
            "🧠 ARCHITECTURAL INTENT:",
            intent
        )


        return intent


    # ======================================================
    # HUMAN LEARNING REGISTRY — RELEVANCE  (READ-ONLY)
    # ======================================================

    _HUMAN_RULE_TOKEN_SPLIT = re.compile(
        r"[^0-9a-z\u0600-\u06ff]+"
    )

    @classmethod
    def _human_rule_tokens(cls, value):

        return {
            token for token in cls._HUMAN_RULE_TOKEN_SPLIT.split(
                str(value or "").lower()
            )
            if len(token) >= 4
        }

    @classmethod
    def _relevant_human_learning_rules(cls, items, text, intent):

        """Return the ACTIVE registry rules relevant to this request.

        Provenance, scope and status are preserved verbatim. Nothing is
        rewritten, promoted or re-ranked.
        """

        haystack = " ".join(
            str(value or "")
            for value in (
                text,
                (intent or {}).get("building_type"),
            )
        )

        request_tokens = cls._human_rule_tokens(haystack)

        relevant = []

        for item in items or []:

            if not isinstance(item, dict):

                continue

            if not item.get("active"):

                continue

            scope = str(item.get("scope") or "")

            overlap = sorted(
                cls._human_rule_tokens(
                    " ".join(
                        str(item.get(key) or "")
                        for key in ("human_observation_fa",
                                    "generalized_rule")
                    )
                ) & request_tokens
            )

            if scope == "GENERAL" or overlap:

                relevant.append(
                    {
                        "id": item.get("id"),
                        "generalized_rule": item.get("generalized_rule"),
                        "scope": scope,
                        "provenance": item.get("provenance"),
                        "status": "active",
                        "match": (
                            "scope:GENERAL" if scope == "GENERAL"
                            else "term_overlap"
                        ),
                        "matched_terms": overlap,
                    }
                )

        return relevant


    # ======================================================
    # PLAN REQUIREMENTS CONNECTION V1
    # ======================================================

    _PLAN_NUMBER_TRANSLATION = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫٬",
        "01234567890123456789.,"
    )

    _PLAN_COUNT_WORDS = {
        "یک": 1, "يه": 1, "یه": 1,
        "دو": 2, "سه": 3, "چهار": 4,
        "پنج": 5, "شش": 6,
        "one": 1, "two": 2, "three": 3,
        "four": 4, "five": 5, "six": 6,
    }

    @classmethod
    def _plan_number(cls, raw):

        normalized = str(raw or "").translate(
            cls._PLAN_NUMBER_TRANSLATION
        ).replace(",", ".").lower()

        if normalized in cls._PLAN_COUNT_WORDS:
            return cls._PLAN_COUNT_WORDS[normalized]

        value = float(normalized)
        return int(value) if value.is_integer() else value

    @classmethod
    def _extract_plan_requirements(cls, text, intent):

        """Preserve explicit semantic plan requirements with provenance.

        The contract records validation as pending. It never infers room
        geometry or promotes knowledge recommendations into user requirements.
        """

        text = str(text or "")
        text_lower = text.lower()
        count_token = (
            r"[0-9۰-۹٠-٩]+|یک|يه|یه|دو|سه|چهار|پنج|شش|"
            r"one|two|three|four|five|six"
        )

        bedroom_count_match = None
        for pattern in (
            rf"(?P<count>{count_token})\s*[-‌ ]*خوابه",
            rf"(?P<count>{count_token})\s*(?:عدد\s*)?اتاق[\s‌-]*خواب",
            rf"(?P<count>{count_token})\s*bedrooms?",
        ):
            bedroom_count_match = re.search(pattern, text, re.IGNORECASE)
            if bedroom_count_match:
                break

        area_match = re.search(
            r"(?:(?P<approx>حدود|تقریباً|تقریبا|نزدیک\s+به|"
            r"approximately|approx\.?|about)\s*)?"
            r"(?P<value>[0-9۰-۹٠-٩]+(?:[\.,٫][0-9۰-۹٠-٩]+)?)\s*"
            r"(?:متر\s*مربع|مترمربع|m²|m2|sq\.?\s*m(?:eters?)?)",
            text,
            re.IGNORECASE
        )

        space_patterns = {
            "living": r"نشیمن|پذیرایی|living(?:\s+room)?",
            "kitchen": r"آشپزخانه|kitchen",
            "bedroom": r"اتاق[\s‌-]*خواب(?:‌?ها)?|خوابه|bedrooms?",
            "bathroom": r"سرویس\s*بهداشتی|حمام|bathrooms?|\bwc\b",
            "stairs": r"راه[\s‌-]*پله\s*داخلی|پله\s*داخلی|internal\s+stair",
            "parking": r"پارکینگ|parking|garage",
            "workspace": r"اتاق\s*کار|workspace|home\s+office|study\s+room",
        }
        matches = {
            name: re.search(pattern, text, re.IGNORECASE)
            for name, pattern in space_patterns.items()
        }

        if not (
            re.search(r"پلان|floor\s*plan|plan\s+design", text_lower)
            or area_match
            or any(matches.values())
        ):
            return None

        floor_contract = intent.get("floor_count", {})
        if not isinstance(floor_contract, dict):
            floor_contract = {}
        floor_requirement = {
            "value": floor_contract.get("value"),
            "source": floor_contract.get("source", "unspecified"),
            "source_evidence": floor_contract.get("raw", ""),
        }

        residential_match = re.search(
            r"واحد\s*مسکونی|مسکونی|residential(?:\s+unit)?",
            text,
            re.IGNORECASE
        )
        occupancy = None
        if residential_match and not is_prohibited(
            text, residential_match.group(0)
        ):
            occupancy = {
                "value": (
                    "residential_unit"
                    if re.search(r"واحد|unit", residential_match.group(0), re.I)
                    else "residential"
                ),
                "source": "user_explicit",
                "source_evidence": residential_match.group(0),
            }

        area = None
        if area_match:
            prefix = text[max(0, area_match.start() - 35):area_match.start()].lower()
            if re.search(r"ناخالص|زیربنای\s*ناخالص|gross", prefix):
                area_basis = "gross"
            elif re.search(r"خالص|مفید|net", prefix):
                area_basis = "net"
            else:
                area_basis = "unspecified"

            area_value = float(cls._plan_number(area_match.group("value")))
            area = {
                "value": area_value,
                "unit": "m2",
                "precision": "approximate" if area_match.group("approx") else "exact",
                "basis": area_basis,
                "role": "design_target",
                "source": "user_explicit",
                "source_evidence": area_match.group(0).strip(),
            }
            # ProgramIntentBridge already transfers these established fields.
            # Never map an unspecified area to gross or net.
            if area_basis == "gross":
                intent["gross_area"] = area_value
            elif area_basis == "net":
                intent["net_area"] = area_value

        optional_marker = re.compile(
            r"در\s*صورت\s*امکان|اختیاری|اگر\s*جا\s*شد|"
            r"پیشنهاد|optional|if\s+possible|may\s+include",
            re.IGNORECASE
        )
        spaces = []

        for space_type in (
            "living", "kitchen", "bedroom", "bathroom",
            "stairs", "parking", "workspace"
        ):
            match = matches.get(space_type)
            if not match or is_prohibited(text, match.group(0)):
                continue

            prefix = text[max(0, match.start() - 55):match.start()]
            suffix = text[match.end():min(len(text), match.end() + 20)]
            optional = bool(optional_marker.search(prefix) or optional_marker.search(suffix))
            count = None
            count_status = "unspecified"
            source_evidence = match.group(0)

            if space_type == "bedroom" and bedroom_count_match:
                count = int(cls._plan_number(bedroom_count_match.group("count")))
                count_status = "explicit"
                source_evidence = bedroom_count_match.group(0)

            if space_type == "parking":
                floor_assignment = "unspecified"
            elif space_type == "stairs":
                floor_assignment = (
                    "multi_floor_connection"
                    if (floor_requirement.get("value") or 0) > 1
                    else "unspecified"
                )
            elif floor_requirement.get("value") == 1:
                floor_assignment = "actual_single_floor"
            else:
                floor_assignment = "unspecified"

            spaces.append({
                "space_type": space_type,
                "required": not optional,
                "count": count,
                "count_status": count_status,
                "classification": (
                    "inferred_architectural_option"
                    if optional else "explicit_user_request"
                ),
                "source": "user_allowed_option" if optional else "user_explicit",
                "source_evidence": source_evidence,
                "floor_assignment": floor_assignment,
            })

        relationships = []
        living_kitchen_match = re.search(
            r"(?:نشیمن|پذیرایی).{0,45}?(?:آشپزخانه).{0,45}?"
            r"(?:ارتباط\s*مناسب|مرتبط|نزدیک)|"
            r"(?:living).{0,45}?(?:kitchen).{0,45}?"
            r"(?:suitable\s+connection|functional\s+relationship|connected)",
            text,
            re.IGNORECASE
        )
        if living_kitchen_match:
            relationships.append({
                "from": "living",
                "to": "kitchen",
                "type": "functional_connection",
                "requirement": "suitable_functional_relationship",
                "source": "user_explicit",
                "source_evidence": living_kitchen_match.group(0),
                "validation_status": "pending",
                "validation_requires": "spatial_evidence",
            })

        privacy_match = re.search(
            r"(?:اتاق[\s‌-]*خواب(?:‌?ها)?|bedrooms?).{0,50}?"
            r"(?:حریم\s*خصوصی|خصوصی|privacy)",
            text,
            re.IGNORECASE
        )
        if privacy_match:
            relationships.append({
                "from": "bedroom",
                "to": "public_zone",
                "type": "separation_requirement",
                "requirement": "private_zone_separation",
                "separates_from_zone": "public",
                "source": "user_explicit",
                "source_evidence": privacy_match.group(0),
                "validation_status": "pending",
                "validation_requires": "spatial_and_access_evidence",
            })

        bathroom_access_match = re.search(
            r"(?:سرویس\s*بهداشتی|حمام|bathroom).{0,70}?"
            r"(?:فضای\s*عمومی|public\s+zone).{0,55}?"
            r"(?:قابل\s*دسترسی|دسترسی|accessible)",
            text,
            re.IGNORECASE
        )
        if bathroom_access_match:
            relationships.append({
                "from": "public_zone",
                "to": "bathroom",
                "type": "access_requirement",
                "requirement": "accessible_from_public_zone",
                "source": "user_explicit",
                "source_evidence": bathroom_access_match.group(0),
                "validation_status": "pending",
                "validation_requires": "path_and_opening_evidence",
            })

        circulation_match = re.search(
            r"مسیرهای?\s*حرکت\s*منطقی|گردش(?:\s*داخلی)?\s*منطقی|"
            r"logical\s+(?:circulation|movement)",
            text,
            re.IGNORECASE
        )
        circulation = None
        if circulation_match:
            circulation = {
                "requirement": "logical",
                "source": "user_explicit",
                "source_evidence": circulation_match.group(0),
                "validation_status": "pending",
                "validation_requires": "path_evidence",
            }

        return {
            "contract": "ArchitecturalPlanRequirementsV1",
            "version": "1.0",
            "source": "user_request",
            "source_text": text,
            "occupancy": occupancy,
            "floor_count": floor_requirement,
            "area": area,
            "spaces": spaces,
            "relationships": relationships,
            "circulation": circulation,
            "geometry_validation": {
                "status": "pending",
                "reason": "semantic_requirements_only",
            },
            "provenance_classes": {
                "explicit_user_request": "authoritative_requirement",
                "inferred_architectural_option": "non_binding_option",
                "knowledge_based_recommendation": "non_user_requirement",
                "missing_information": "unresolved",
                "pending_validation": "not_yet_verified",
            },
        }
