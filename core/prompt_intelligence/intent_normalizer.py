# ==========================================================
# ArchitectOS Intent Normalizer v1.3
# LLM Semantic Intent -> ArchitectOS Internal Format
#
# Compatibility Bridge:
# - LLM Parser schema
# - PromptBuilder schema
# - Architectural Intent schema
#
# Fixed:
# - Persian building detection
# - house/villa normalization
# - safer building_type fallback
#
# ==========================================================


class IntentNormalizer:


    VERSION = "1.3"



    def __init__(self):

        print(
            "🔄 INTENT NORMALIZER v1.3 ONLINE"
        )



    # ======================================================
    # STYLE NORMALIZATION
    # ======================================================

    def normalize_style(
        self,
        style
    ):


        if not style:

            return None



        value = str(style).strip()

        normalized = value.lower()



        if any(
            x in normalized
            for x in [
                "traditional",
                "iranian",
                "سنتی",
                "ایرانی"
            ]
        ):

            return value



        if any(
            x in normalized
            for x in [
                "modern",
                "مدرن"
            ]
        ):

            return "modern"



        if any(
            x in normalized
            for x in [
                "classic",
                "کلاسیک"
            ]
        ):

            return "classic"



        return value



    # ======================================================
    # BUILDING TYPE NORMALIZATION
    # ======================================================

    def normalize_building_type(
        self,
        value
    ):


        if not value:

            return "building"



        text = str(
            value
        ).strip().lower()



        # Persian house keywords

        if any(
            key in text
            for key in [

                "خانه",
                "خونه",
                "منزل",
                "ویلایی",
                "ویلا",
                "villa",
                "house",
                "residential"

            ]
        ):

            return "house"



        if any(
            key in text
            for key in [

                "آپارتمان",
                "اپارتمان",
                "apartment"

            ]
        ):

            return "apartment"



        if any(
            key in text
            for key in [

                "برج",
                "tower"

            ]
        ):

            return "tower"



        if any(
            key in text
            for key in [

                "ساختمان",
                "building"

            ]
        ):

            return "building"



        return text



    # ======================================================
    # CLEAN VALUE
    # ======================================================

    def clean(
        self,
        value
    ):


        if isinstance(
            value,
            str
        ):

            return value.strip()



        return value



    # ======================================================
    # CLEAN LIST
    # ======================================================

    def clean_list(
        self,
        value
    ):


        if not isinstance(
            value,
            list
        ):

            return []


        return [

            self.clean(x)

            for x in value

        ]



    # ======================================================
    # NORMALIZE
    # ======================================================

    def normalize(
        self,
        intent
    ):


        if not isinstance(
            intent,
            dict
        ):

            return {}



        result = {}



        # ==================================================
        # BUILDING EXTRACTION
        # ==================================================

        building = intent.get(
            "building",
            {}
        )


        raw_building_type = None


        raw_style = None



        if isinstance(
            intent.get(
                "building_type"
            ),
            str
        ):

            raw_building_type = intent.get(
                "building_type"
            )


            raw_style = intent.get(
                "style"
            )



        elif isinstance(
            building,
            dict
        ):


            raw_building_type = (

                building.get(
                    "type"
                )

                or

                building.get(
                    "building_type"
                )

            )


            raw_style = building.get(
                "style"
            )



        # ==================================================
        # FALLBACK FROM RAW USER CONTEXT
        # ==================================================

        if not raw_building_type:


            raw_text = str(

                intent.get(
                    "prompt",
                    ""
                )

            )


            raw_building_type = raw_text



        building_type = self.normalize_building_type(
            raw_building_type
        )


        style = self.normalize_style(
            raw_style
        )



        result["building_type"] = building_type


        result["style"] = style



        result["building"] = {


            "type":

                building_type,


            "style":

                style

        }



        # ==================================================
        # MATERIALS
        # ==================================================

        result["materials"] = self.clean_list(

            intent.get(
                "materials",
                []
            )

        )



        # ==================================================
        # OBJECTS
        # ==================================================

        result["objects"] = self.clean_list(

            intent.get(
                "objects",
                []
            )

        )



        # ==================================================
        # ENVIRONMENT
        # ==================================================

        result["environment"] = self.clean_list(

            intent.get(
                "environment",
                []
            )

        )



        # ==================================================
        # SITE
        # ==================================================

        result["site"] = self.clean_list(

            intent.get(
                "site",
                []
            )

        )



        # ==================================================
        # RENDER CONTEXT
        # ==================================================

        result["camera"] = self.clean(

            intent.get(
                "camera",
                ""
            )

        )


        result["lighting"] = self.clean(

            intent.get(
                "lighting",
                ""
            )

        )


        result["atmosphere"] = self.clean(

            intent.get(
                "atmosphere",
                ""
            )

        )



        print(
            "🔄 NORMALIZED INTENT v1.3:",
            result
        )



        return result





# ==========================================================
# SINGLETON
# ==========================================================


intent_normalizer = IntentNormalizer()