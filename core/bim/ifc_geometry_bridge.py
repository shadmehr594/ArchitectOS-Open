"""
ArchitectOS IFC Geometry Bridge v1.0

Connects BIM Geometry Adapter output
to IFC Geometry Provider.
"""


class IFCGeometryBridge:


    VERSION = "1.0"



    def __init__(
        self,
        geometry_provider=None
    ):


        self.geometry_provider = geometry_provider


        print(
            f"🔗 IFC Geometry Bridge v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # SPACE
    # ==================================================

    def prepare_space(
        self,
        element
    ):


        return {


            "type":
                "IfcSpace",


            "polygon":
                element.get(
                    "polygon"
                ),


            "height":
                element.get(
                    "height",
                    3.2
                ),


            "level":
                element.get(
                    "level"
                )

        }



    # ==================================================
    # WALL
    # ==================================================

    def prepare_wall(
        self,
        element
    ):


        return {


            "type":
                "IfcWall",


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
                    "height",
                    3.2
                ),


            "thickness":
                element.get(
                    "thickness",
                    0.2
                ),


            "level":
                element.get(
                    "level"
                )

        }



    # ==================================================
    # OPENING
    # ==================================================

    def prepare_opening(
        self,
        element
    ):


        return {


            "type":
                element.get(
                    "type"
                ),


            "host_room":
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
        geometry_result
    ):


        prepared = []



        for element in geometry_result.get(
            "geometry_elements",
            []
        ):


            element_type = element.get(
                "type"
            )



            if element_type == "IfcSpace":


                prepared.append(

                    self.prepare_space(
                        element
                    )

                )



            elif element_type == "IfcWall":


                prepared.append(

                    self.prepare_wall(
                        element
                    )

                )



            elif element_type in [

                "IfcDoor",

                "IfcWindow"

            ]:


                prepared.append(

                    self.prepare_opening(
                        element
                    )

                )



        return {


            "ifc_geometry_input":
                prepared

        }