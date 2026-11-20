"""
ArchitectOS Building Stack Generator v1.0

Creates multi-level building structure.
"""


class BuildingStackGenerator:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🏢 Building Stack Generator v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # FLOOR CREATOR
    # ==================================================

    def create_floor(
        self,
        floor_data
    ):


        floor = {


            "level":
                floor_data.get(
                    "level"
                ),


            "type":
                floor_data.get(
                    "type"
                ),


            "features":
                floor_data.get(
                    "features",
                    []
                ),


            "units":
                floor_data.get(
                    "units",
                    0
                )

        }



        if "projection" in floor_data:


            floor["projection"] = (

                floor_data["projection"]

            )



        return floor



    # ==================================================
    # GENERATE
    # ==================================================

    def generate(
        self,
        building
    ):


        floors = []



        for floor_data in building.get(
            "floors",
            []
        ):


            floors.append(

                self.create_floor(

                    floor_data

                )

            )



        return {


            "site":
                building.get(
                    "site"
                ),


            "floors":
                floors,


            "floor_count":
                len(
                    floors
                )

        }