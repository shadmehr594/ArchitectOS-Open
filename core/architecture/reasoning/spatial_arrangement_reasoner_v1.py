"""
ArchitectOS Spatial Arrangement Reasoner V1

Creates intelligent spatial positions
from architectural layout decisions.
"""


class SpatialArrangementReasonerV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "📐 SPATIAL ARRANGEMENT REASONER V1 ONLINE"
        )



    # ==================================================
    # GENERATE ARRANGEMENT
    # ==================================================

    def generate(
        self,
        architectural_layout
    ):


        result = {

            "floors": {},

            "rules": [

                "public_spaces_connected",

                "service_supports_public",

                "private_zone_separated",

                "vertical_core_central"

            ]

        }



        spaces = architectural_layout.get(
            "spaces",
            []
        )



        for space in spaces:


            floor = self.resolve_floor(
                space
            )


            if floor not in result["floors"]:

                result["floors"][floor] = {

                    "spaces": [],

                    "cursor_x":0,

                    "cursor_y":0

                }



            position = self.place_space(
                space,
                result["floors"][floor]
            )


            result["floors"][floor]["spaces"].append(
                position
            )



        # remove internal counters

        for floor in result["floors"]:

            result["floors"][floor].pop(
                "cursor_x",
                None
            )

            result["floors"][floor].pop(
                "cursor_y",
                None
            )


        return result



    # ==================================================
    # FLOOR LOGIC
    # ==================================================

    def resolve_floor(
        self,
        space
    ):


        name = space.get(
            "name"
        )


        if name in [

            "master_bedroom",

            "bedroom",

            "bathroom"

        ]:

            return "upper_floor"


        return "ground_floor"



    # ==================================================
    # SPACE PLACEMENT LOGIC
    # ==================================================

    def place_space(
        self,
        space,
        floor_data
    ):


        name = space.get(
            "name"
        )


        dimensions = self.get_dimensions(
            name
        )


        x = floor_data["cursor_x"]

        y = floor_data["cursor_y"]



        item = {


            "name":
                name,


            "zone":
                space.get(
                    "zone"
                ),


            "x":
                x,


            "y":
                y,


            "width":
                dimensions["width"],


            "depth":
                dimensions["depth"]

        }



        floor_data["cursor_x"] += dimensions["width"]



        return item



    # ==================================================
    # DIMENSION KNOWLEDGE
    # ==================================================

    def get_dimensions(
        self,
        name
    ):


        data = {


            "living":
                {
                    "width":6,
                    "depth":5
                },


            "dining":
                {
                    "width":4,
                    "depth":4
                },


            "kitchen":
                {
                    "width":3,
                    "depth":4
                },


            "guest_wc":
                {
                    "width":2,
                    "depth":2
                },


            "master_bedroom":
                {
                    "width":5,
                    "depth":4
                },


            "bedroom":
                {
                    "width":4,
                    "depth":4
                },


            "bathroom":
                {
                    "width":2,
                    "depth":3
                },


            "stairs":
                {
                    "width":3,
                    "depth":5
                }

        }


        return data.get(

            name,

            {
                "width":4,
                "depth":4
            }

        )