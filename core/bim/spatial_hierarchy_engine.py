class SpatialHierarchyEngine:


    """
    BIM Spatial Hierarchy Engine v39.0


    Building
        |
        +-- Levels
              |
              +-- Spaces
                    |
                    +-- Elements


    BIM Ready Spatial Structure

    """



    def __init__(self):

        print(
            "🏢 Spatial Hierarchy Engine v39.0 ACTIVE"
        )





    # =====================================================
    # BUILD SPATIAL HIERARCHY
    # =====================================================


    def build(
        self,
        elements,
        levels
    ):


        print(
            "▶️ BUILD SPATIAL HIERARCHY v39"
        )



        hierarchy = {


            "building":

                "BUILDING_001",



            "levels":

                []

        }




        level_map = {}



        for level in levels:


            level_id = level.get(
                "id"
            )


            level_map[level_id] = {


                "id":

                    level_id,


                "name":

                    level.get(
                        "name"
                    ),


                "elevation":

                    level.get(
                        "elevation",
                        0
                    ),


                "spaces":

                    []

            }





        # =====================================================
        # CREATE DEFAULT SPACES
        # =====================================================


        for level_id, level_data in level_map.items():


            index = level_id.split("_")[-1]



            space = {


                "id":

                    f"SPACE_L{index}_MAIN",



                "name":

                    f"Level {index} Main Space",



                "elements":

                    []

            }



            level_data["spaces"].append(

                space

            )





        # =====================================================
        # ASSIGN ELEMENTS
        # =====================================================


        for element in elements:


            level_id = element.get(

                "level",

                "LEVEL_0"

            )



            if level_id in level_map:


                space = level_map[level_id]["spaces"][0]



                space["elements"].append(

                    element.get(
                        "id"
                    )

                )





        hierarchy["levels"] = list(

            level_map.values()

        )





        print(

            f"🏢 LEVELS PROCESSED: {len(hierarchy['levels'])}"

        )



        total_spaces = sum(

            len(level["spaces"])

            for level in hierarchy["levels"]

        )



        print(

            f"🚪 SPACES GENERATED: {total_spaces}"

        )



        return hierarchy