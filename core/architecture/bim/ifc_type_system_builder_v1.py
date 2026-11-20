"""
ArchitectOS IFC Type System Builder V1

Creates BIM Type Definitions:

IfcWall
    |
IfcWallType

IfcSlab
    |
IfcSlabType

IfcWindow
    |
IfcWindowType
"""


import ifcopenshell



class IFCTypeSystemBuilderV1:


    VERSION = "1.0"



    def __init__(
        self,
        model
    ):

        self.model = model


        print(
            f"🏷 IFC TYPE SYSTEM BUILDER v{self.VERSION} ONLINE"
        )



    # ======================================
    # BUILD
    # ======================================

    def build(
        self
    ):


        results = []


        results.extend(
            self.build_wall_types()
        )


        results.extend(
            self.build_slab_types()
        )


        results.extend(
            self.build_window_types()
        )


        return {

            "types":
                results,

            "count":
                len(results)

        }



    # ======================================
    # WALL TYPES
    # ======================================

    def build_wall_types(
        self
    ):


        results = []


        wall_types = []


        walls = self.model.by_type(
            "IfcWall"
        )


        if not walls:

            return results



        wall_type = self.model.create_entity(

            "IfcWallType",

            GlobalId=ifcopenshell.guid.new(),

            Name="External Brick Wall Type",

            PredefinedType="STANDARD"

        )



        for wall in walls:


            self.assign_type(
                wall,
                wall_type
            )



        results.append(
            wall_type
        )


        return results



    # ======================================
    # SLAB TYPES
    # ======================================

    def build_slab_types(
        self
    ):


        results = []


        slabs = self.model.by_type(
            "IfcSlab"
        )


        if not slabs:

            return results



        slab_type = self.model.create_entity(

            "IfcSlabType",

            GlobalId=ifcopenshell.guid.new(),

            Name="Concrete Floor Slab Type",

            PredefinedType="FLOOR"

        )



        for slab in slabs:


            self.assign_type(
                slab,
                slab_type
            )


        results.append(
            slab_type
        )


        return results



    # ======================================
    # WINDOW TYPES
    # ======================================

    def build_window_types(
        self
    ):


        results = []


        windows = self.model.by_type(
            "IfcWindow"
        )


        if not windows:

            return results



        window_type = self.model.create_entity(

            "IfcWindowType",

            GlobalId=ifcopenshell.guid.new(),

            Name="Double Glass Window Type",

            PredefinedType="WINDOW"

        )



        for window in windows:


            self.assign_type(
                window,
                window_type
            )


        results.append(
            window_type
        )


        return results



    # ======================================
    # ASSIGN TYPE
    # ======================================

    def assign_type(
        self,
        element,
        type_object
    ):


        self.model.create_entity(

            "IfcRelDefinesByType",

            GlobalId=ifcopenshell.guid.new(),

            RelatedObjects=[

                element

            ],

            RelatingType=type_object

        )