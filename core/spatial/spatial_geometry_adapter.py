class SpatialGeometryAdapter:


    VERSION = "1.0"



    def __init__(
        self
    ):

        print(
            "🏗 SPATIAL GEOMETRY ADAPTER v1.0 ONLINE"
        )



    # ==================================================
    # SPACE TYPE RESOLVER
    # ==================================================

    def resolve_type(
        self,
        space
    ):


        name = space.get(
            "name"
        )


        zone = space.get(
            "zone"
        )


        if name == "parking":

            return "parking_floor"



        if zone == "commercial":

            return "commercial_unit"



        if name == "lobby":

            return "public_core"



        if name in [
            "food_court",
            "cinema",
            "entertainment"
        ]:

            return "entertainment_space"



        if zone == "public":

            return "public_space"



        if zone == "service":

            return "service_space"



        return "generic_space"



    # ==================================================
    # GEOMETRY RESOLVER
    # ==================================================

    def resolve_geometry(
        self,
        footprint
    ):


        mapping = {


            "front_block":
            {

                "shape":
                    "block",

                "position":
                    "front"

            },


            "central_core":
            {

                "shape":
                    "core",

                "position":
                    "center"

            },


            "rear_block":
            {

                "shape":
                    "block",

                "position":
                    "rear"

            },


            "parking_grid":
            {

                "shape":
                    "grid",

                "position":
                    "basement"

            }

        }



        return mapping.get(

            footprint,

            {

                "shape":
                    "generic",

                "position":
                    "unknown"

            }

        )



    # ==================================================
    # SPACE ADAPTER
    # ==================================================

    def adapt_space(
        self,
        space
    ):


        return {


            "type":
                "space",


            "name":
                space.get(
                    "name"
                ),


            "architectural_role":
                self.resolve_type(
                    space
                ),


            "zone":
                space.get(
                    "zone"
                ),


            "access":
                space.get(
                    "access"
                ),


            "geometry":
                self.resolve_geometry(
                    space.get(
                        "footprint"
                    )
                )

        }



    # ==================================================
    # FLOOR ADAPTER
    # ==================================================

    def adapt_floor(
        self,
        floor
    ):


        return {


            "level":
                floor.get(
                    "level"
                ),


            "spaces":
            [

                self.adapt_space(
                    space
                )

                for space in floor.get(
                    "spaces",
                    []
                )

            ]

        }



    # ==================================================
    # MAIN ADAPTER
    # ==================================================

    def adapt(
        self,
        geometry_model
    ):


        floors = geometry_model.get(
            "floors",
            []
        )



        return {


            "architectural_model":
            {


                "floors":
                [

                    self.adapt_floor(
                        floor
                    )

                    for floor in floors

                ]

            },


            "metadata":
            {

                "engine":
                    "Spatial Geometry Adapter",


                "version":
                    self.VERSION

            }

        }