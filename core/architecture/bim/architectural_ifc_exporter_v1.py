"""
ArchitectOS Architectural IFC Exporter V1

Creates final IFC file from architectural IFC entities.
"""


import ifcopenshell



class ArchitecturalIFCExporterV1:


    VERSION = "1.0"



    def __init__(

        self,

        schema="IFC4"

    ):

        print(

            f"🏛 ARCHITECTURAL IFC EXPORTER v{self.VERSION} ONLINE"

        )


        self.model = ifcopenshell.file(

            schema=schema

        )



        self.elements = []



    # =====================================
    # ADD ELEMENT
    # =====================================

    def add_element(

        self,

        element

    ):


        self.elements.append(

            element

        )



    # =====================================
    # BUILD IFC STRUCTURE
    # =====================================

    def build_project(

        self

    ):


        project = self.model.create_entity(

            "IfcProject",

            GlobalId=self.guid(),

            Name="ArchitectOS Architectural Project"

        )


        site = self.model.create_entity(

            "IfcSite",

            GlobalId=self.guid(),

            Name="Site"

        )


        building = self.model.create_entity(

            "IfcBuilding",

            GlobalId=self.guid(),

            Name="Building"

        )


        storey = self.model.create_entity(

            "IfcBuildingStorey",

            GlobalId=self.guid(),

            Name="F1"

        )


        self.model.create_entity(

            "IfcRelAggregates",

            GlobalId=self.guid(),

            RelatingObject=project,

            RelatedObjects=[

                site

            ]

        )



        self.model.create_entity(

            "IfcRelAggregates",

            GlobalId=self.guid(),

            RelatingObject=site,

            RelatedObjects=[

                building

            ]

        )



        self.model.create_entity(

            "IfcRelAggregates",

            GlobalId=self.guid(),

            RelatingObject=building,

            RelatedObjects=[

                storey

            ]

        )


        return project



    # =====================================
    # EXPORT
    # =====================================

    def export(

        self,

        path

    ):


        self.build_project()


        self.model.write(

            path

        )


        return path



    # =====================================
    # GUID
    # =====================================

    def guid(

        self

    ):


        import uuid

        return str(

            uuid.uuid4()

        )