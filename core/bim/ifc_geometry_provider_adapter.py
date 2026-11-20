"""
ArchitectOS IFC Geometry Provider Adapter v1.0

Connects IFC Geometry Bridge output
to IFC Geometry Provider.
"""


class IFCGeometryProviderAdapter:


    VERSION = "1.0"



    def __init__(
        self,
        provider=None
    ):


        self.provider = provider


        print(
            f"🔌 IFC Geometry Provider Adapter v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # DISPATCH
    # ==================================================

    def create_geometry(
        self,
        element
    ):


        element_type = element.get(
            "type"
        )



        if element_type == "IfcWall":


            return self.create_wall(
                element
            )



        elif element_type == "IfcSpace":


            return self.create_space(
                element
            )



        elif element_type in [

            "IfcDoor",

            "IfcWindow"

        ]:


            return self.create_opening(
                element
            )



        return None



    # ==================================================
    # WALL
    # ==================================================

    def create_wall(
        self,
        element
    ):


        return {


            "entity":
                "IfcWall",


            "geometry":

            {

                "start":
                    element.get(
                        "start"
                    ),

                "end":
                    element.get(
                        "end"
                    ),

                "height":
                    element.get(
                        "height"
                    ),

                "thickness":
                    element.get(
                        "thickness"
                    )

            },


            "level":
                element.get(
                    "level"
                )

        }



    # ==================================================
    # SPACE
    # ==================================================

    def create_space(
        self,
        element
    ):


        return {


            "entity":
                "IfcSpace",


            "geometry":

            {

                "polygon":
                    element.get(
                        "polygon"
                    ),

                "height":
                    element.get(
                        "height"
                    )

            },


            "level":
                element.get(
                    "level"
                )

        }



    # ==================================================
    # OPENINGS
    # ==================================================

    def create_opening(
        self,
        element
    ):


        return {


            "entity":
                element.get(
                    "type"
                ),


            "host":
                element.get(
                    "host_room"
                ),


            "level":
                element.get(
                    "level"
                )

        }



    # ==================================================
    # GENERATE
    # ==================================================

    def generate(
        self,
        bridge_result
    ):


        output = []


        for element in bridge_result.get(
            "ifc_geometry_input",
            []
        ):


            geometry = self.create_geometry(
                element
            )


            if geometry:

                output.append(
                    geometry
                )



        return {


            "ifc_entities":
                output

        }