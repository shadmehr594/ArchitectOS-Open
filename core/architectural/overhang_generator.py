class OverhangGenerator:


    def __init__(self):

        print(
            "🏢 Overhang & Solar Projection Engine v25.6.1 ACTIVE"
        )


    def generate(
        self,
        data
    ):

        # ==========================
        # CONFIGURATION
        # ==========================

        enabled = data.get(
            "enabled",
            False
        )


        # اگر طراح نخواست پیش‌آمدگی داشته باشیم
        if not enabled:

            return {

                "engine":
                "overhang_generator_v25.6.1",

                "status":
                "skipped",

                "reason":
                "overhang_disabled"

            }


        facade = data.get(
            "facade",
            None
        )


        floors = data.get(
            "floors",
            []
        )


        projection = data.get(
            "projection",
            None
        )


        overhang_type = data.get(
            "type",
            "cantilever"
        )


        purpose = data.get(
            "purpose",
            "architectural_projection"
        )


        # اگر عمق پیش آمدگی تعریف نشده باشد
        if projection is None:

            return {

                "engine":
                "overhang_generator_v25.6.1",

                "status":
                "skipped",

                "reason":
                "projection_not_defined"

            }


        # ==========================
        # SOLAR ANALYSIS
        # ==========================

        solar_control = False


        if facade in [
            "south",
            "east",
            "west"
        ]:

            solar_control = True



        # ==========================
        # GENERATION
        # ==========================

        element = {

            "type":
            "overhang",


            "overhang_type":
            overhang_type,


            "facade":
            facade,


            "floors":
            floors,


            "projection_m":
            projection,


            "purpose":
            purpose,


            "solar_control":
            solar_control

        }


        return {

            "engine":
            "overhang_generator_v25.6.1",


            "status":
            "generated",


            "elements":[
                element
            ]

        }