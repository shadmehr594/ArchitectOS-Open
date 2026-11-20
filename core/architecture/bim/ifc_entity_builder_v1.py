"""
ArchitectOS Architectural IFC Entity Builder V1

Creates IFC entities from Architectural BIM elements.

Pipeline:

Architectural BIM
        |
        v
IFC Entity Builder
        |
        v
IfcProject
IfcSite
IfcBuilding
IfcStorey
IfcSpace
IfcWall
IfcSlab
IfcStair
"""


import ifcopenshell
import hashlib


class ArchitecturalIFCEntityBuilderV1:


    VERSION = "1.0"



    def __init__(
        self,
        context=None
    ):

        print(
            f"🏗 ARCHITECTURAL IFC ENTITY BUILDER v{self.VERSION} ONLINE"
        )

        self.context = context or {}



    # =====================================
    # MAIN BUILD
    # =====================================

    def build(
        self,
        elements
    ):


        self.model = ifcopenshell.file(
            schema="IFC4"
        )


        project = self.create_project()

        site = self.create_site()

        building = self.create_building()


        storeys = {}

        entities = []

        entity_levels = {}



        for element in elements:


            level = element.get(
                "level",
                "F1"
            )


            if level not in storeys:

                storeys[level] = (
                    self.create_storey(
                        level
                    )
                )


            entity = (
                self.create_element(
                    element,
                    storeys[level]
                )
            )


            if entity:


                entities.append(
                    entity
                )


                entity_levels[entity] = level



        return {

            "ifc_model":
                self.model,

            "project":
                project,

            "entity_count":
                len(
                    entities
                ),

            "entities":
                entities,

            "entity_levels":
                entity_levels,

            "storeys":
                storeys,

            "source":
                "architectural_ifc_entity_builder_v1"

        }



    # =====================================
    # IFC STRUCTURE
    # =====================================


    def create_project(
        self
    ):

        return self.model.create_entity(

            "IfcProject",

            GlobalId=self.guid(
                "ArchitectOS_Project"
            ),

            Name="ArchitectOS Project"

        )



    def create_site(
        self
    ):

        return self.model.create_entity(

            "IfcSite",

            GlobalId=self.guid(
                "ArchitectOS_Site"
            ),

            Name="ArchitectOS Site"

        )



    def create_building(
        self
    ):

        return self.model.create_entity(

            "IfcBuilding",

            GlobalId=self.guid(
                "ArchitectOS_Building"
            ),

            Name="ArchitectOS Building"

        )



    def create_storey(
        self,
        level
    ):

        return self.model.create_entity(

            "IfcBuildingStorey",

            GlobalId=self.guid(
                level
            ),

            Name=level

        )



    # =====================================
    # ELEMENT CREATION
    # =====================================


    def create_element(
        self,
        element,
        storey
    ):


        ifc_class = element.get(
            "ifc_class"
        )


        name = element.get(
            "name",
            "Unnamed"
        )



        if ifc_class not in [

            "IfcSpace",
            "IfcWall",
            "IfcSlab",
            "IfcStair",
            "IfcWindow",
            "IfcDoor"

        ]:
            return None



        entity = self.model.create_entity(

            ifc_class,

            GlobalId=self.guid(

                name +
                "_" +
                str(
                    element.get(
                        "level"
                    )
                )

            ),

            Name=name

        )


        return entity



    # =====================================
    # STABLE GUID
    # =====================================


    def guid(
        self,
        value
    ):


        digest = hashlib.md5(
            value.encode()
        ).hexdigest()


        return ifcopenshell.guid.compress(
            digest[:22]
        )
# ======================================
# BACKWARD COMPATIBILITY ALIAS
# ======================================

IFCEntityBuilderV1 = ArchitecturalIFCEntityBuilderV1