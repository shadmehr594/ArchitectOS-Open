class AssetContract:

    VERSION = "1.0"


    IFC_MAP = {

        "chair":
            "IfcFurniture",

        "table":
            "IfcFurniture",

        "sofa":
            "IfcFurniture",

        "bed":
            "IfcFurniture",

        "cabinet":
            "IfcFurniture",


        "stair":
            "IfcStair",

        "ramp":
            "IfcRamp",

        "railing":
            "IfcRailing",


        "window":
            "IfcWindow",

        "door":
            "IfcDoor",


        "facade_element":
            "IfcBuildingElementProxy"

    }



    def create(
        self,
        asset_type,
        style="generic",
        material=None,
        source="library"
    ):


        return {

            "id":
                None,


            "type":
                asset_type,


            "ifc_type":
                self.IFC_MAP.get(
                    asset_type,
                    "IfcBuildingElementProxy"
                ),


            "system":
                "architectural",


            "style":
                style,


            "material":
                material or {},


            "asset":

            {

                "provider":
                    source,

                "reference":
                    None

            },


            "data":
            {

            }

        }