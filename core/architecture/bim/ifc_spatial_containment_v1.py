"""
ArchitectOS IFC Spatial Containment V1

Creates IFC spatial containment relations.

IfcBuildingStorey
        |
        v
IfcRelContainedInSpatialStructure
        |
        v
IfcWall / IfcSlab / IfcSpace / IfcStair
"""


class IFCSpatialContainmentV1:


    VERSION = "1.0"



    def __init__(
        self,
        model
    ):

        self.model = model


        print(
            f"🏢 IFC SPATIAL CONTAINMENT v{self.VERSION} ONLINE"
        )



    def contain(
        self,
        storey,
        elements
    ):


        if not elements:

            return None



        relation = self.model.create_entity(

            "IfcRelContainedInSpatialStructure",

            GlobalId=self.guid(),

            RelatingStructure=storey,

            RelatedElements=elements

        )


        return relation



    def guid(
        self
    ):

        import ifcopenshell.guid


        return ifcopenshell.guid.new()