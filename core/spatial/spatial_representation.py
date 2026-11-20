class SpatialRepresentation:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🏗 SPATIAL REPRESENTATION ENGINE v1.0 ONLINE"
        )



    # ==================================================
    # GRAPH REPRESENTATION
    # ==================================================

    def build_graph(
        self,
        state
    ):


        spatial = state.spatial.get(
            "model",
            {}
        )


        graph = {


            "nodes":
                spatial.get(
                    "nodes",
                    []
                ),


            "connections":
                spatial.get(
                    "connections",
                    []
                )

        }


        return graph



    # ==================================================
    # FLOOR REPRESENTATION
    # ==================================================

    def build_floor_plan(
        self,
        state
    ):


        plan = state.get_plan()


        building = plan.get(
            "building",
            {}
        )


        floors = {}



        for floor_name, floor in building.items():


            floors[floor_name] = {


                "level":
                    floor.get(
                        "level"
                    ),


                "spaces":
                    [
                        {

                            "name":
                                space.get(
                                    "name"
                                ),


                            "zone":
                                space.get(
                                    "zone"
                                ),


                            "position":
                                space.get(
                                    "position"
                                ),


                            "access":
                                space.get(
                                    "access"
                                )

                        }

                        for space in floor.get(
                            "spaces",
                            []
                        )

                    ]

            }



        return floors



    # ==================================================
    # RENDER PAYLOAD
    # ==================================================

    def build_render_payload(
        self,
        state
    ):


        return {


            "building_type":
                state.get_project_type(),


            "plan":
                self.build_floor_plan(
                    state
                ),


            "camera":
                state.get_render_context().get(
                    "camera"
                ),


            "mood":
                state.get_render_context().get(
                    "mood"
                )

        }



    # ==================================================
    # COMPLETE REPRESENTATION
    # ==================================================

    def generate(
        self,
        state
    ):


        return {


            "spatial_graph":
                self.build_graph(
                    state
                ),


            "floor_plan":
                self.build_floor_plan(
                    state
                ),


            "render_payload":
                self.build_render_payload(
                    state
                ),


            "metadata":
            {

                "engine":
                    "Spatial Representation Engine",


                "version":
                    self.VERSION

            }

        }