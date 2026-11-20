"""
ArchitectOS IFC Opening Relationship Builder V1

Creates:

IfcWall
    |
IfcRelVoidsElement
    |
IfcOpeningElement
    |
IfcRelFillsElement
    |
IfcDoor / IfcWindow
"""


import ifcopenshell



class IFCOpeningRelationshipBuilderV1:


    VERSION = "1.0"



    def __init__(
        self,
        model
    ):

        self.model = model


        print(
            f"🚪 IFC OPENING RELATIONSHIP BUILDER v{self.VERSION} ONLINE"
        )



    # ======================================
    # BUILD
    # ======================================

    def build(
        self
    ):


        walls = self.model.by_type(
            "IfcWall"
        )


        windows = self.model.by_type(
            "IfcWindow"
        )


        doors = self.model.by_type(
            "IfcDoor"
        )


        results = []



        for wall in walls:


            for opening in windows + doors:


                opening_element = self.model.create_entity(

                    "IfcOpeningElement",

                    GlobalId=ifcopenshell.guid.new(),

                    Name=
                        opening.Name
                        +
                        "_Opening"

                )



                self.model.create_entity(

                    "IfcRelVoidsElement",

                    GlobalId=ifcopenshell.guid.new(),

                    RelatingBuildingElement=wall,

                    RelatedOpeningElement=opening_element

                )



                self.model.create_entity(

                    "IfcRelFillsElement",

                    GlobalId=ifcopenshell.guid.new(),

                    RelatingOpeningElement=opening_element,

                    RelatedBuildingElement=opening

                )



                results.append(
                    opening_element
                )



        return {


            "openings":

                results,


            "count":

                len(results)

        }