"""
ArchitectOS IFC Export Model Adapter v1.0
"""


class IFCExportModelAdapter:


    VERSION = "1.0"



    def __init__(self):


        print(
            f"🔄 IFC Export Model Adapter v{self.VERSION} ACTIVE"
        )



    def convert(
        self,
        ifc_entities
    ):


        bim_elements = []



        for entity in ifc_entities.get(
            "ifc_entities",
            []
        ):



            ifc_type = entity.get(
                "entity"
            )



            element = {


                "ifc_type":
                    ifc_type

            }



            if "geometry" in entity:

                geometry = entity.get(
                    "geometry"
                )


                element["geometry"] = geometry


                if ifc_type == "IfcWall":


                    element["start"] = geometry.get(
                        "start"
                    )


                    element["end"] = geometry.get(
                        "end"
                    )


                    element["height"] = geometry.get(
                        "height"
                    )


                    element["thickness"] = geometry.get(
                        "thickness"
                    )



            if "level" in entity:


                element["level"] = entity.get(
                    "level"
                )



            if "host" in entity:


                element["host_room"] = entity.get(
                    "host"
                )



            bim_elements.append(

                element

            )



        return {


            "bim_elements":
                bim_elements

        }