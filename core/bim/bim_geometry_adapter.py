"""
ArchitectOS BIM Geometry Adapter v1.0

Converts semantic BIM elements into geometry-ready data.
"""


class BIMGeometryAdapter:


    VERSION = "1.0"



    def __init__(
        self,
        default_height=3.2
    ):


        self.default_height = default_height


        print(
            f"🔄 BIM Geometry Adapter v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # SPACE
    # ==================================================

    def adapt_space(
        self,
        element,
        level="F1"
    ):


        return {


            "type":
                "IfcSpace",


            "level":
                level,


            "polygon":
                element.get(
                    "geometry"
                ),


            "height":
                self.default_height

        }



    # ==================================================
    # WALL
    # ==================================================

    def adapt_wall(
        self,
        element,
        level="F1"
    ):


        boundary = element.get(
            "boundary"
        )



        return {


            "type":
                "IfcWall",


            "level":
                level,


            "start":
                boundary[0],


            "end":
                boundary[1],


            "height":
                self.default_height,


            "thickness":
                element.get(
                    "thickness",
                    0.2
                )

        }



    # ==================================================
    # OPENINGS
    # ==================================================

    def adapt_opening(
        self,
        element,
        level="F1"
    ):


        return {


            "type":
                element.get(
                    "ifc_type"
                ),


            "level":
                level,


            "host_room":
                element.get(
                    "room"
                ),


            "source":
                element.get(
                    "source"
                )

        }



    # ==================================================
    # GENERATE
    # ==================================================

    def generate(
        self,
        semantic_result,
        level="F1"
    ):


        geometry = []



        for element in semantic_result.get(
            "elements",
            []
        ):


            if element.get(
                "ifc_type"
            ) == "IfcSpace":


                geometry.append(

                    self.adapt_space(
                        element,
                        level
                    )

                )



            elif element.get(
                "ifc_type"
            ) == "IfcWall":


                geometry.append(

                    self.adapt_wall(
                        element,
                        level
                    )

                )



            elif element.get(
                "ifc_type"
            ) in [

                "IfcDoor",

                "IfcWindow"

            ]:


                geometry.append(

                    self.adapt_opening(
                        element,
                        level
                    )

                )



        return {


            "geometry_elements":
                geometry

        }