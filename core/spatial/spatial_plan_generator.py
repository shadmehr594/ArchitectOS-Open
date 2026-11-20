class SpatialPlanGenerator:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🏗 SPATIAL PLAN GENERATOR v1.0 ONLINE"
        )



    # ==================================================
    # CREATE SPACE OBJECT
    # ==================================================

    def create_space(
        self,
        name,
        zone,
        position,
        access=None
    ):


        return {

            "name":
                name,

            "zone":
                zone,

            "position":
                position,

            "access":
                access

        }



    # ==================================================
    # GENERATE GROUND FLOOR
    # ==================================================

    def generate_ground_floor(
        self,
        layout_logic
    ):


        spaces = []



        zones = layout_logic.get(
            "zones",
            {}
        )



        for space in zones.get(
            "front_zone",
            []
        ):


            spaces.append(
                self.create_space(
                    space,
                    "commercial",
                    "front",
                    "public"
                )
            )



        for space in zones.get(
            "central_zone",
            []
        ):


            spaces.append(
                self.create_space(
                    space,
                    "public",
                    "center",
                    "public"
                )
            )



        for space in zones.get(
            "entertainment_zone",
            []
        ):


            spaces.append(
                self.create_space(
                    space,
                    "public",
                    "rear",
                    "public"
                )
            )



        return {

            "level":
                "ground_floor",

            "spaces":
                spaces

        }



    # ==================================================
    # GENERATE SERVICE LEVEL
    # ==================================================

    def generate_basement(
        self,
        layout_logic
    ):


        spaces = []



        for space in layout_logic.get(
            "zones",
            {}
        ).get(
            "service_zone",
            []
        ):


            spaces.append(

                self.create_space(
                    space,
                    "service",
                    "basement",
                    "service"
                )

            )



        return {

            "level":
                "basement",

            "spaces":
                spaces

        }



    # ==================================================
    # CONNECTIONS
    # ==================================================

    def generate_connections(
        self,
        layout_logic
    ):


        return layout_logic.get(
            "relationships",
            []
        )



    # ==================================================
    # MAIN GENERATOR
    # ==================================================

    def generate(
        self,
        layout_logic
    ):


        plan = {


            "building":

            {


                "ground_floor":

                    self.generate_ground_floor(
                        layout_logic
                    ),


                "basement":

                    self.generate_basement(
                        layout_logic
                    )

            },


            "connections":

                self.generate_connections(
                    layout_logic
                ),


            "metadata":

            {

                "engine":
                    "Spatial Plan Generator",


                "version":
                    self.VERSION

            }

        }



        return plan