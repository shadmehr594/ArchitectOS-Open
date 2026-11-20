"""
ArchitectOS IFC Element Placement Builder v1.0

Resolves IFC element placement
from architectural context.
"""


class IFCElementPlacementBuilderV1:


    VERSION = "1.0"



    def __init__(
        self,
        context=None
    ):

        print(
            f"📍 IFC ELEMENT PLACEMENT BUILDER v{self.VERSION} ONLINE"
        )

        self.context = context or {}



    # ======================================
    # MAIN BUILD
    # ======================================

    def build(
        self,
        elements
    ):

        placements = []


        for element in elements:


            level = element.get(
                "level"
            )


            placement = self.resolve_placement(
                level
            )


            placements.append(

                {

                    "ifc_class":
                        element.get(
                            "ifc_class"
                        ),


                    "name":
                        element.get(
                            "name"
                        ),


                    "level":
                        level,


                    "placement":
                        placement

                }

            )


        return {

            "placements":
                placements,


            "element_count":
                len(
                    placements
                ),


            "source":
                "ifc_element_placement_builder"

        }



    # ======================================
    # PLACEMENT RESOLUTION
    # ======================================

    def resolve_placement(
        self,
        level
    ):


        elevations = self.context.get(
            "level_elevations",
            {}
        )


        elevation = elevations.get(
            level
        )


        return {

            "location":
                [
                    0,
                    0,
                    elevation
                ],


            "axis":
                [
                    0,
                    0,
                    1
                ]

        }


    # ======================================
    # ATTACH IFC LOCAL PLACEMENT
    # ======================================

    def attach(
        self,
        entity,
        placement
    ):

        model = entity.wrapped_data.file


        point = model.create_entity(
            "IfcCartesianPoint",
            Coordinates=(
                float(placement["location"][0]),
                float(placement["location"][1]),
                float(placement["location"][2])
            )
        )


        axis = model.create_entity(
            "IfcAxis2Placement3D",
            Location=point
        )


        local = model.create_entity(
            "IfcLocalPlacement",
            RelativePlacement=axis
        )


        entity.ObjectPlacement = local


        return entity