class BIMSceneGraph:


    def __init__(self):

        print(
            "🏗️ BIM Scene Graph Engine v33.1 ACTIVE"
        )


    def build(self, state):


        graph = {


            "type":
            "BuildingInformationGraph",


            "project":
            state.get(
                "project",
                "ArchitectOS_Project"
            ),


            "levels":
            [],


            "elements":
            [],


            "spaces":
            [],


            "systems":
            {

            }


        }



        # ==========================
        # Geometry
        # ==========================

        geometry = state.get(
            "geometry_result",
            {}
        )


        floors = geometry.get(
            "floors",
            []
        )


        for floor in floors:


            level = {


                "id":
                f"Level_{floor.get('level')}",


                "level":
                floor.get(
                    "level"
                ),


                "elevation":
                floor.get(
                    "level",
                    0
                ),


                "elements":
                []

            }


            graph["levels"].append(
                level
            )



        # ==========================
        # Walls
        # ==========================


        for wall in geometry.get(
            "walls",
            []
        ):


            element = {


                "category":
                "Wall",


                "type":
                "IfcWall",


                "id":
                wall.get(
                    "object_id"
                ),


                "properties":
                {


                    "facade":
                    wall.get(
                        "id"
                    ),


                    "length":
                    wall.get(
                        "length"
                    ),


                    "height":
                    wall.get(
                        "height"
                    ),


                    "thickness":
                    wall.get(
                        "thickness"
                    ),


                    "mesh_ready":
                    wall.get(
                        "mesh_ready"
                    )


                }


            }


            graph["elements"].append(
                element
            )



        # ==========================
        # Openings
        # ==========================


        for opening in geometry.get(
            "openings",
            []
        ):


            graph["elements"].append(

                {


                    "category":
                    "Opening",


                    "type":
                    "IfcWindow"
                    if opening.get(
                        "type"
                    ) == "window"
                    else "IfcDoor",


                    "properties":
                    opening


                }

            )



        # ==========================
        # Furniture
        # ==========================


        furniture = state.get(
            "furniture_result",
            {}
        )


        for obj in furniture.get(
            "objects",
            []
        ):


            graph["elements"].append(

                {


                    "category":
                    "Furniture",


                    "type":
                    "InteriorObject",


                    "properties":
                    obj


                }

            )



        # ==========================
        # Roof
        # ==========================


        graph["systems"]["roof"] = state.get(
            "roof_result",
            {}
        )



        # ==========================
        # Materials
        # ==========================


        graph["systems"]["materials"] = state.get(
            "material_result",
            {}
        )



        # ==========================
        # Landscape
        # ==========================


        graph["systems"]["landscape"] = state.get(
            "landscape_result",
            {}
        )



        # ==========================
        # Lighting
        # ==========================


        graph["systems"]["lighting"] = state.get(
            "lighting_result",
            {}
        )



        # ==========================
        # Camera
        # ==========================


        graph["systems"]["camera"] = state.get(
            "camera_result",
            {}
        )



        # ==========================
        # Statistics
        # ==========================


        graph["statistics"] = {


            "levels":
            len(
                graph["levels"]
            ),


            "elements":
            len(
                graph["elements"]
            ),


            "systems":
            len(
                graph["systems"]
            )


        }



        state["bim_scene_graph"] = graph



        return state