"""
ArchitectOS Room Program Engine v1.0

Creates room requirements for different building programs.
"""


class RoomProgramEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🚪 Room Program Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # RESIDENTIAL STANDARD
    # ==================================================

    def residential_standard(
        self,
        data
    ):


        return {


            "type":
                "residential",


            "rooms":[


                {
                    "type":
                        "entrance"
                },


                {
                    "type":
                        "living",
                    "zone":
                        "public"
                },


                {
                    "type":
                        "dining",
                    "zone":
                        "public"
                },


                {
                    "type":
                        "master_bedroom",
                    "zone":
                        "private",
                    "light":
                        "lightwell_or_facade"
                },


                {
                    "type":
                        "bedroom",
                    "count":
                        data.get(
                            "bedrooms",
                            1
                        ),
                    "zone":
                        "private"
                },


                {
                    "type":
                        "kitchen_clean"
                },


                {
                    "type":
                        "kitchen_dirty"
                },


                {
                    "type":
                        "laundry"
                },


                {
                    "type":
                        "bathroom"
                },


                {
                    "type":
                        "wc"
                },


                {
                    "type":
                        "storage"
                },


                {
                    "type":
                        "closet"
                }

            ]

        }



    # ==================================================
    # PENTHOUSE
    # ==================================================

    def penthouse(
        self
    ):


        return {


            "type":
                "penthouse",


            "rooms":[


                {
                    "type":
                        "large_living"
                },


                {
                    "type":
                        "dining"
                },


                {
                    "type":
                        "kitchen_clean"
                },


                {
                    "type":
                        "kitchen_dirty"
                },


                {
                    "type":
                        "master_bedroom"
                },


                {
                    "type":
                        "master_bathroom"
                },


                {
                    "type":
                        "walk_in_closet"
                },


                {
                    "type":
                        "terrace"
                },


                {
                    "type":
                        "roof_garden"
                },


                {
                    "type":
                        "private_elevator_lobby"
                }

            ]

        }



    # ==================================================
    # MAIN
    # ==================================================

    def generate(
        self,
        request
    ):


        unit_type = request.get(
            "type",
            "residential"
        )


        if unit_type == "penthouse":

            return self.penthouse()



        return self.residential_standard(
            request
        )