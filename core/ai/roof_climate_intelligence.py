class RoofClimateIntelligence:


    def __init__(self):

        print(
            "🌦️ Roof Climate Intelligence Engine v28.6.1 ACTIVE"
        )



    def recommend(
        self,
        context
    ):


        climate = context.get(
            "climate",
            "temperate"
        )


        rainfall = context.get(
            "rainfall",
            "medium"
        )


        snow = context.get(
            "snow",
            False
        )


        coastal = context.get(
            "coastal",
            False
        )



        if snow:

            roof = "gable"

            reason = "snow_load_management"



        elif coastal:

            roof = "hip"

            reason = "wind_resistance"



        elif climate == "hot":


            if rainfall == "high":

                roof = "flat"

                reason = "hot_climate_with_drainage"


            else:

                roof = "flat"

                reason = "thermal_mass_and_green_roof"



        elif rainfall == "high":


            roof = "gable"

            reason = "rainwater_management"



        else:


            roof = "flat"

            reason = "general_residential_default"



        return {


            "engine":
            "roof_climate_intelligence_v28.6.1",


            "status":
            "recommended",


            "recommendation":

            {

                "roof_type":
                roof,


                "reason":
                reason

            },


            "confidence":
            0.9

        }