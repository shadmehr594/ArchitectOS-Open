class RoofIntelligenceEngine:


    def __init__(self):

        print(
            "🏠 Roof Intelligence Engine v28.6 ACTIVE"
        )


        self.roof_types = {


            "flat":

            {

                "default_slope":
                2,

                "max_slope":
                5,

                "uses":
                [

                    "green_roof",

                    "terrace",

                    "solar_panel"

                ]

            },


            "gable":

            {

                "default_slope":
                30,

                "range":
                [

                    20,

                    45

                ],

                "uses":
                [

                    "rain",

                    "snow"

                ]

            },


            "hip":

            {

                "default_slope":
                30,

                "range":
                [

                    20,

                    40

                ]

            },


            "shed":

            {

                "default_slope":
                15,

                "custom":
                True

            },


            "mansard":

            {

                "default_slope":
                35

            },


            "custom":

            {

                "custom":
                True

            }

        }



    def generate(
        self,
        roof_config
    ):


        if not roof_config.get(
            "enabled",
            True
        ):


            return {


                "engine":
                "roof_intelligence_v28.6",


                "status":
                "skipped",


                "reason":
                "roof_disabled"

            }



        roof_type = roof_config.get(

            "type",

            "flat"

        )



        if roof_type not in self.roof_types:

            roof_type = "flat"



        data = self.roof_types[

            roof_type

        ]



        slope = roof_config.get(

            "slope",

            data.get(
                "default_slope",
                0
            )

        )



        green_roof = roof_config.get(

            "green_roof",

            False

        )



        material = roof_config.get(

            "material",

            "concrete"

        )



        drainage = (

            True

            if slope > 0

            else False

        )



        return {


            "engine":

            "roof_intelligence_v28.6",


            "status":

            "generated",


            "roof":

            {

                "type":

                roof_type,


                "slope_degree":

                slope,


                "material":

                material,


                "green_roof":

                green_roof,


                "drainage":

                drainage

            },


            "geometry_ready":

            True

        }