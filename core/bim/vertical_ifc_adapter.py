"""
ArchitectOS Vertical IFC Adapter v1.0

Converts semantic vertical BIM elements
into IFC export-ready objects.
"""


class VerticalIFCAdapter:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🔗 Vertical IFC Adapter v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # CONVERT SINGLE ELEMENT
    # ==================================================

    def convert(
        self,
        semantic_element
    ):


        semantic_type = semantic_element.get(
            "semantic_type"
        )


        geometry = semantic_element.get(
            "geometry"
        )



        if semantic_type == "stair":

            return {

                "ifc_class":
                    "IfcStair",

                "geometry":
                    geometry,

                "properties":
                    {

                        "Function":
                            "Escape Route"

                    }

            }



        if semantic_type in (

            "escalator",

            "moving_ramp"

        ):


            return {

                "ifc_class":
                    "IfcTransportElement",

                "geometry":
                    geometry,

                "properties":
                    {

                        "System":
                            semantic_type

                    }

            }



        if semantic_type == "elevator":


            return {

                "ifc_class":
                    "IfcBuildingElementProxy",

                "geometry":
                    geometry,

                "properties":
                    {

                        "Function":
                            "Vertical Accessibility"

                    }

            }



        return None



    # ==================================================
    # CONVERT PACKAGE
    # ==================================================

    def convert_package(
        self,
        semantic_package
    ):


        elements = []


        for element in semantic_package.get(

            "semantic_elements",

            []

        ):


            result = self.convert(

                element

            )


            if result:

                elements.append(

                    result

                )



        return {


            "elements":

                elements

        }