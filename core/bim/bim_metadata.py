"""
ArchitectOS BIM Metadata Engine v34

Purpose:
- Provide intelligent metadata layer for BIM elements
- Add engineering information
- Prepare IFC / Revit mapping
- Support quantities, cost, lifecycle and analysis
"""


class BIMMetadata:

    VERSION = "BIM_METADATA_v34"

    def __init__(self):

        self.element_database = {}

        self.ifc_mapping = {

            "column": "IfcColumn",
            "beam": "IfcBeam",
            "wall": "IfcWall",
            "slab": "IfcSlab",
            "door": "IfcDoor",
            "window": "IfcWindow",
            "roof": "IfcRoof",
            "stair": "IfcStair"

        }


    def create_metadata(
        self,
        element
    ):

        element_id = element.get(
            "id",
            "UNKNOWN"
        )

        element_type = element.get(
            "type",
            "generic"
        )


        metadata = {

            "id": element_id,

            "bim_type": element_type,


            # Classification

            "classification": {

                "category":
                    element.get(
                        "category",
                        "unknown"
                    ),

                "discipline":
                    self.detect_discipline(
                        element_type
                    )

            },


            # Geometry information

            "geometry": {

                "dimensions":
                    element.get(
                        "geometry",
                        {}
                    )

            },


            # Material intelligence

            "material": {

                "name":
                    element.get(
                        "material",
                        "unknown"
                    ),

                "properties":
                    self.material_properties(
                        element.get(
                            "material",
                            ""
                        )
                    )

            },


            # Engineering data

            "engineering": {

                "load_bearing":
                    self.is_structural(
                        element_type
                    ),

                "fire_rating":
                    "unknown",

                "thermal_value":
                    None,

                "durability":
                    "standard"

            },


            # Quantity

            "quantity": {

                "area":
                    element.get(
                        "area",
                        None
                    ),

                "volume":
                    self.calculate_volume(
                        element
                    )

            },


            # Cost placeholder

            "cost": {

                "estimated":
                    None,

                "currency":
                    "USD"

            },


            # IFC

            "ifc": {

                "class":
                    self.ifc_mapping.get(
                        element_type,
                        "IfcBuildingElementProxy"
                    )

            },


            # Lifecycle

            "lifecycle": {

                "phase":
                    "construction",

                "maintenance":
                    "standard"

            }

        }


        self.element_database[
            element_id
        ] = metadata


        return metadata



    def detect_discipline(
        self,
        element_type
    ):

        structural = [

            "column",
            "beam",
            "slab",
            "wall"

        ]


        architectural = [

            "door",
            "window",
            "roof"

        ]


        if element_type in structural:

            return "structural"


        if element_type in architectural:

            return "architectural"


        return "general"



    def is_structural(
        self,
        element_type
    ):

        return element_type in [

            "column",
            "beam",
            "slab",
            "wall"

        ]



    def material_properties(
        self,
        material
    ):

        material = material.lower()


        database = {


            "reinforced_concrete": {

                "strength":
                    "high",

                "density":
                    2400,

                "fire":
                    "excellent"

            },


            "masonry": {

                "strength":
                    "medium",

                "density":
                    1800,

                "fire":
                    "good"

            },


            "steel": {

                "strength":
                    "very_high",

                "density":
                    7850,

                "fire":
                    "needs_protection"

            }

        }


        return database.get(

            material,

            {

                "strength":
                    "unknown"

            }

        )



    def calculate_volume(
        self,
        element
    ):

        geometry = element.get(
            "geometry",
            {}
        )


        width = geometry.get(
            "width",
            0
        )

        depth = geometry.get(
            "depth",
            0
        )

        height = geometry.get(
            "height",
            0
        )


        if width and depth and height:

            return (
                width *
                depth *
                height
            )


        return None



    def get_all_metadata(
        self
    ):

        return {

            "engine":
                self.VERSION,

            "elements":
                self.element_database

        }