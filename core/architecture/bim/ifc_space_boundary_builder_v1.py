"""
ArchitectOS IFC Space Boundary Builder V1

Creates semantic boundaries between:

IfcSpace
    |
IfcRelSpaceBoundary
    |
IfcWall / IfcSlab
"""


import ifcopenshell



class IFCSpaceBoundaryBuilderV1:


    VERSION = "1.0"



    def __init__(
        self,
        model
    ):

        self.model = model


        print(
            f"🔲 IFC SPACE BOUNDARY BUILDER v{self.VERSION} ONLINE"
        )



    # ======================================
    # BUILD
    # ======================================

    def build(
        self
    ):


        spaces = self.model.by_type(
            "IfcSpace"
        )


        boundaries = []


        walls = self.model.by_type(
            "IfcWall"
        )


        slabs = self.model.by_type(
            "IfcSlab"
        )


        related_elements = (
            walls +
            slabs
        )



        for space in spaces:


            for element in related_elements:


                boundary = self.model.create_entity(

                    "IfcRelSpaceBoundary",

                    GlobalId=ifcopenshell.guid.new(),

                    RelatingSpace=space,

                    RelatedBuildingElement=element

                )


                boundaries.append(
                    boundary
                )



        return {


            "boundaries":

                boundaries,


            "count":

                len(boundaries)

        }