"""
ArchitectOS IFC Opening Relationship Builder V1

Creates IFC opening semantics:

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


        openings = []


        windows = self.model.by_type(
            "IfcWindow"
        )


        doors = self.model.by_type(
            "IfcDoor"
        )


        fillers = (
            windows +
            doors
        )



        relations = []



        for wall in walls:


            for filler in fillers:


                opening = self.model.create_entity(

                    "IfcOpeningElement",

                    GlobalId=ifcopenshell.guid.new(),

                    Name=
                        filler.Name
                        +
                        "_Opening"

                )



                void_relation = self.model.create_entity(

                    "IfcRelVoidsElement",

                    GlobalId=ifcopenshell.guid.new(),

                    RelatingBuildingElement=wall,

                    RelatedOpeningElement=opening

                )



                fill_relation = self.model.create_entity(

                    "IfcRelFillsElement",

                    GlobalId=ifcopenshell.guid.new(),

                    RelatingOpeningElement=opening,

                    RelatedBuildingElement=filler

                )



                openings.append(
                    opening
                )


                relations.append(
                    void_relation
                )


                relations.append(
                    fill_relation
                )



        return {


            "opening_elements":

                openings,


            "relations":

                relations,


            "count":

                len(openings)

        }