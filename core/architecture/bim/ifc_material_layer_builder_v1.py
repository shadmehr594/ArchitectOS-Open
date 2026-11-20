"""
ArchitectOS IFC Material Layer Builder V1

Creates IFC material semantics:

IfcWall
    |
IfcMaterialLayerSetUsage
    |
IfcMaterialLayerSet
    |
IfcMaterialLayer
    |
IfcMaterial


Creates:

IfcRelAssociatesMaterial
"""

import ifcopenshell



class IFCMaterialLayerBuilderV1:


    VERSION = "1.0"



    def __init__(
        self,
        model
    ):

        self.model = model


        print(
            f"🧱 IFC MATERIAL LAYER BUILDER v{self.VERSION} ONLINE"
        )



    # ======================================
    # BUILD MATERIALS
    # ======================================

    def build(
        self
    ):


        results = []


        walls = self.model.by_type(
            "IfcWall"
        )


        slabs = self.model.by_type(
            "IfcSlab"
        )



        # ===============================
        # WALL MATERIALS
        # ===============================

        for wall in walls:


            material = self.create_material(
                "Brick"
            )


            layer = self.model.create_entity(

                "IfcMaterialLayer",

                Material=material,

                LayerThickness=0.25

            )


            layer_set = self.model.create_entity(

                "IfcMaterialLayerSet",

                MaterialLayers=[

                    layer

                ],

                LayerSetName="External Wall Assembly"

            )


            usage = self.model.create_entity(

                "IfcMaterialLayerSetUsage",

                ForLayerSet=layer_set,

                LayerSetDirection="AXIS2",

                DirectionSense="POSITIVE",

                OffsetFromReferenceLine=0.0

            )


            relation = self.create_material_relation(

                wall,

                usage

            )


            results.append(
                relation
            )



        # ===============================
        # SLAB MATERIALS
        # ===============================

        for slab in slabs:


            material = self.create_material(
                "Concrete"
            )


            layer = self.model.create_entity(

                "IfcMaterialLayer",

                Material=material,

                LayerThickness=0.20

            )


            layer_set = self.model.create_entity(

                "IfcMaterialLayerSet",

                MaterialLayers=[

                    layer

                ],

                LayerSetName="Floor Slab Assembly"

            )


            relation = self.create_material_relation(

                slab,

                layer_set

            )


            results.append(
                relation
            )



        return {


            "materials":

                results,


            "count":

                len(results)

        }



    # ======================================
    # MATERIAL RELATION
    # ======================================

    def create_material_relation(
        self,
        element,
        material_definition
    ):


        return self.model.create_entity(

            "IfcRelAssociatesMaterial",

            GlobalId=ifcopenshell.guid.new(),

            RelatedObjects=[

                element

            ],

            RelatingMaterial=material_definition

        )



    # ======================================
    # MATERIAL
    # ======================================

    def create_material(
        self,
        name
    ):


        return self.model.create_entity(

            "IfcMaterial",

            Name=name

        )