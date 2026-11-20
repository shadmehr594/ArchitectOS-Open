import datetime


class RevitTypeMaterialMapper:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"🧱 Revit Type Material Mapper v{self.VERSION} ACTIVE"
        )



    def map(
        self,
        elements
    ):

        result = {}


        for element in elements or []:

            element_id = element.get(
                "id"
            )


            ifc_type = element.get(
                "ifc_type",
                element.get(
                    "type",
                    ""
                )
            )


            mapping = self._resolve(
                ifc_type,
                element
            )


            result[element_id] = mapping



        return {


            "engine":
                f"revit_type_material_mapper_v{self.VERSION}",


            "created":
                datetime.datetime.now().isoformat(),


            "elements":
                result

        }



    def _resolve(
        self,
        ifc_type,
        element
    ):


        if ifc_type == "IfcColumn":

            return {

                "category":
                    "Structural Columns",

                "family":
                    "Structural Columns - Concrete",

                "type":
                    "RC_400x400",

                "material":
                    "Concrete"

            }



        if ifc_type == "IfcBeam":

            return {

                "category":
                    "Structural Framing",

                "family":
                    "Structural Framing - Concrete",

                "type":
                    "RC_Beam_300x500",

                "material":
                    "Concrete"

            }



        if ifc_type == "IfcWall":

            return {

                "category":
                    "Walls",

                "family":
                    "Basic Wall",

                "type":
                    "Concrete Wall 200mm",

                "material":
                    "Concrete"

            }



        if ifc_type in [
            "IfcDoor",
            "IfcWindow",
            "IfcOpening"
        ]:

            return {

                "category":
                    "Openings",

                "family":
                    "Opening System",

                "type":
                    "Generic Opening",

                "material":
                    "N/A"

            }



        return {

            "category":
                "Generic",

            "family":
                "Generic",

            "type":
                "Default",

            "material":
                "Default"

        }