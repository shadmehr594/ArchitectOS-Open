# ==========================================================
# ArchitectOS Intent Router Bridge v69.3
# GOD CORE Router -> Cognitive Intent Engine
# Compatible with Brain v21.7
# Unified Design Family Routing + Update Intelligence
# ==========================================================


from core.cognition.intent_engine import intent_engine



class IntentRouter:


    VERSION = "v69.3"



    def __init__(self):

        print(
            "🧠 Intent Router Bridge v69.3 UPDATE INTELLIGENCE ACTIVE"
        )



    # ======================================================
    # DESIGN UPDATE DETECTOR
    # ======================================================

    def detect_update(
        self,
        text
    ):


        update_words = [

            "بزرگ",
            "بزرگتر",
            "بزرگ‌تر",
            "کوچک",
            "کوچکتر",
            "کوچک‌تر",
            "تغییر",
            "اصلاح",
            "اضافه",
            "حذف",
            "تبدیل",
            "کن",
            "کنم",
            "شود",
            "replace",
            "update",
            "modify",
            "change",
            "expand",
            "reduce"

        ]


        target_words = [

            "استخر",
            "pool",

            "آشپزخانه",
            "kitchen",

            "نما",
            "facade",

            "سنگ",
            "stone",

            "اتاق",
            "خواب",
            "bedroom",

            "بام",
            "roof"

        ]



        has_operation = any(

            word in text.lower()

            for word in update_words

        )



        has_target = any(

            word in text.lower()

            for word in target_words

        )



        return (

            has_operation
            and
            has_target

        )



    # ======================================================
    # MAIN ROUTE
    # ======================================================

    def route(
        self,
        text
    ):


        text = (

            text
            or
            ""

        ).strip()



        # ==================================================
        # UPDATE FAST PATH v69.3
        # ==================================================

        if self.detect_update(
            text
        ):

            return "design_update"



        try:


            result = intent_engine.analyze(
                text
            )



            # IntentResult support

            if hasattr(
                result,
                "intent"
            ):

                intent = result.intent



            elif isinstance(
                result,
                dict
            ):

                intent = result.get(
                    "intent"
                )



            else:

                intent = None


            # ==================================================
            # PROJECT EXPORT
            # ==================================================

            if intent == "project_export":

                return "project_export"



            # ==================================================
            # CHAT
            # ==================================================

            if intent == "chat":

                return "chat"

           
            # ==================================================
            # EXPORT
            # ==================================================

            if intent == "project_export":

                return "project_export"



            # ==================================================
            # IMAGE
            # ==================================================

            if intent == "image_generation":

                return "image_generation"


            # ==================================================
            # EXPORT
            # ==================================================

            if intent == "export_request":

                return "export_request"



            # ==================================================
            # DESIGN FAMILY
            # ==================================================

            if intent == "villa_design":

                return "villa_design"



            if intent == "apartment_design":

                return "apartment_design"



            if intent == "highrise_design":

                return "highrise_design"



            if intent == "design_request":

                return "design_request"



        except Exception as e:


            print(

                "Intent Router Error:",
                e

            )



        # ==================================================
        # FALLBACK
        # ==================================================

        t = text.lower()



        if (

            "villa" in t
            or
            "ویلا" in t

        ):

            return "villa_design"



        if (

            "apartment" in t
            or
            "آپارتمان" in t

        ):

            return "apartment_design"



        if (

            "tower" in t
            or
            "highrise" in t
            or
            "برج" in t

        ):

            return "highrise_design"



        if (

            "house" in t
            or
            "building" in t
            or
            "خانه" in t

        ):

            return "design_request"



        return "chat"