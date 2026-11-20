"""
ArchitectOS IFC Spatial Structure Builder V1

Builds IFC spatial hierarchy:

IfcProject
    |
IfcSite
    |
IfcBuilding
    |
IfcBuildingStorey
    |
    +-- IfcSpace
    +-- IfcWall
    +-- IfcSlab
"""


import ifcopenshell



class IFCSpatialStructureBuilderV1:


    VERSION = "1.0"



    def __init__(
        self,
        model
    ):

        self.model = model


        print(
            f"🏢 IFC SPATIAL STRUCTURE BUILDER v{self.VERSION} ONLINE"
        )



    # ======================================
    # BUILD PROJECT STRUCTURE
    # ======================================

    def build(
        self,
        project=None,
        site=None,
        building=None,
        storey=None
    ):


        # ===============================
        # PROJECT
        # ===============================

        if project is None:

            projects = self.model.by_type(
                "IfcProject"
            )

            if projects:

                project = projects[0]

            else:

                project = self.model.create_entity(

                    "IfcProject",

                    GlobalId=ifcopenshell.guid.new(),

                    Name="ArchitectOS Project"

                )



        # ===============================
        # SITE
        # ===============================

        if site is None:

            sites = self.model.by_type(
                "IfcSite"
            )

            if sites:

                site = sites[0]

            else:

                site = self.model.create_entity(

                    "IfcSite",

                    GlobalId=ifcopenshell.guid.new(),

                    Name="Site"

                )



        # ===============================
        # BUILDING
        # ===============================

        if building is None:

            buildings = self.model.by_type(
                "IfcBuilding"
            )

            if buildings:

                building = buildings[0]

            else:

                building = self.model.create_entity(

                    "IfcBuilding",

                    GlobalId=ifcopenshell.guid.new(),

                    Name="ArchitectOS Building"

                )



        # ===============================
        # STOREY
        # ===============================

        if storey is None:

            storeys = self.model.by_type(
                "IfcBuildingStorey"
            )

            if storeys:

                storey = storeys[0]

            else:

                storey = self.model.create_entity(

                    "IfcBuildingStorey",

                    GlobalId=ifcopenshell.guid.new(),

                    Name="F1"

                )



        # ===============================
        # AGGREGATION
        # ===============================

        self.ensure_relation(

            project,

            site

        )


        self.ensure_relation(

            site,

            building

        )


        self.ensure_relation(

            building,

            storey

        )



        # ===============================
        # SEMANTIC CONTAINMENT
        # ===============================

        self.create_containment_relation(

            storey

        )



        return {


            "project":

                project,


            "site":

                site,


            "building":

                building,


            "storey":

                storey

        }



    # ======================================
    # SEMANTIC CONTAINMENT
    # ======================================

    def create_containment_relation(
        self,
        storey
    ):


        elements = []


        for entity in self.model.by_type(
            "IfcProduct"
        ):


            if entity.is_a(
                "IfcWall"
            ):

                elements.append(
                    entity
                )


            elif entity.is_a(
                "IfcSlab"
            ):

                elements.append(
                    entity
                )


            elif entity.is_a(
                "IfcSpace"
            ):

                elements.append(
                    entity
                )



        if not elements:

            return None



        # جلوگیری از duplicate

        for relation in self.model.by_type(
            "IfcRelContainedInSpatialStructure"
        ):


            if relation.RelatingStructure == storey:

                return relation



        return self.model.create_entity(

            "IfcRelContainedInSpatialStructure",

            GlobalId=ifcopenshell.guid.new(),

            RelatedElements=elements,

            RelatingStructure=storey

        )



    # ======================================
    # SAFE AGGREGATION
    # ======================================

    def ensure_relation(

        self,

        parent,

        child

    ):


        for relation in self.model.by_type(

            "IfcRelAggregates"

        ):


            if relation.RelatingObject == parent:


                if child in relation.RelatedObjects:

                    return relation



        return self.model.create_entity(

            "IfcRelAggregates",

            GlobalId=ifcopenshell.guid.new(),

            RelatingObject=parent,

            RelatedObjects=[

                child

            ]

        )