"""
ArchitectOS IFC Real Solid Builder V1

Creates real IFC solids from architectural geometry.

Supported:

IfcWall
IfcSlab

Pipeline:

Geometry Parameters
        |
        v
Real IFC Solid
"""


import ifcopenshell



class IFCRealSolidBuilderV1:


    VERSION = "1.0"



    def __init__(
        self,
        model,
        context=None
    ):

        print(
            f"🧱 IFC REAL SOLID BUILDER v{self.VERSION} ONLINE"
        )

        self.model = model

        self.context = context or {}



    # =====================================
    # MAIN BUILD
    # =====================================

    def build(
        self,
        entity,
        geometry
    ):


        if entity.is_a(
            "IfcWall"
        ):

            return self.build_wall(
                geometry
            )


        if entity.is_a(
            "IfcSlab"
        ):

            return self.build_slab(
                geometry
            )


        return None



    # =====================================
    # WALL
    # =====================================

    def build_wall(
        self,
        geometry
    ):


        thickness = (

            geometry.get(
                "thickness"
            )

            or

            self.context.get(
                "wall_thickness"
            )

        )


        height = (

            geometry.get(
                "height"
            )

            or

            self.context.get(
                "floor_height"
            )

        )



        profile = self.model.create_entity(

            "IfcRectangleProfileDef",

            ProfileType="AREA",

            XDim=thickness,

            YDim=height

        )



        solid = self.model.create_entity(

            "IfcExtrudedAreaSolid",

            SweptArea=profile,

            Depth=height,

            ExtrudedDirection=self.create_direction()

        )


        return solid



    # =====================================
    # SLAB
    # =====================================

    def build_slab(
        self,
        geometry
    ):


        thickness = (

            geometry.get(
                "thickness"
            )

            or

            self.context.get(
                "slab_thickness"
            )

        )


        profile = self.model.create_entity(

            "IfcRectangleProfileDef",

            ProfileType="AREA",

            XDim=1.0,

            YDim=1.0

        )



        solid = self.model.create_entity(

            "IfcExtrudedAreaSolid",

            SweptArea=profile,

            Depth=thickness,

            ExtrudedDirection=self.create_direction()

        )


        return solid



    # =====================================
    # DIRECTION
    # =====================================

    def create_direction(
        self
    ):


        return self.model.create_entity(

            "IfcDirection",

            DirectionRatios=[

                0.0,

                0.0,

                1.0

            ]

        )