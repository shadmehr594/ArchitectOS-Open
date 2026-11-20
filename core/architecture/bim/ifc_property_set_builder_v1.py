"""
ArchitectOS IFC Property Set Builder V1

Creates IFC semantic properties:

IfcObject
    |
IfcRelDefinesByProperties
    |
IfcPropertySet
    |
IfcPropertySingleValue
"""


import ifcopenshell



class IFCPropertySetBuilderV1:


    VERSION = "1.0"



    def __init__(
        self,
        model
    ):

        self.model = model


        print(
            f"📋 IFC PROPERTY SET BUILDER v{self.VERSION} ONLINE"
        )



    # ======================================
    # BUILD
    # ======================================

    def build(
        self
    ):


        results = []


        self.build_wall_properties(
            results
        )


        self.build_slab_properties(
            results
        )


        self.build_window_properties(
            results
        )


        return {

            "property_sets":
                results,

            "count":
                len(results)

        }



    # ======================================
    # WALL
    # ======================================

    def build_wall_properties(
        self,
        results
    ):


        walls = self.model.by_type(
            "IfcWall"
        )


        for wall in walls:


            pset = self.create_property_set(

                "Pset_WallCommon",

                [

                    (
                        "IsExternal",
                        True
                    ),

                    (
                        "LoadBearing",
                        False
                    ),

                    (
                        "FireRating",
                        "60min"
                    )

                ]

            )


            self.attach(
                wall,
                pset
            )


            results.append(
                pset
            )



    # ======================================
    # SLAB
    # ======================================

    def build_slab_properties(
        self,
        results
    ):


        slabs = self.model.by_type(
            "IfcSlab"
        )


        for slab in slabs:


            pset = self.create_property_set(

                "Pset_SlabCommon",

                [

                    (
                        "LoadBearing",
                        True
                    ),

                    (
                        "Thickness",
                        0.20
                    )

                ]

            )


            self.attach(
                slab,
                pset
            )


            results.append(
                pset
            )



    # ======================================
    # WINDOW
    # ======================================

    def build_window_properties(
        self,
        results
    ):


        windows = self.model.by_type(
            "IfcWindow"
        )


        for window in windows:


            pset = self.create_property_set(

                "Pset_WindowCommon",

                [

                    (
                        "GlazingType",
                        "Double"
                    ),

                    (
                        "ThermalTransmittance",
                        1.4
                    )

                ]

            )


            self.attach(
                window,
                pset
            )


            results.append(
                pset
            )



    # ======================================
    # PROPERTY SET
    # ======================================

    def create_property_set(
        self,
        name,
        properties
    ):


        values = []


        for prop_name, prop_value in properties:


            value = self.model.create_entity(

                "IfcPropertySingleValue",

                Name=prop_name,

                NominalValue=
                    self.create_value(
                        prop_value
                    )

            )


            values.append(
                value
            )



        return self.model.create_entity(

            "IfcPropertySet",

            GlobalId=ifcopenshell.guid.new(),

            Name=name,

            HasProperties=values

        )



    # ======================================
    # ATTACH
    # ======================================

    def attach(
        self,
        element,
        pset
    ):


        self.model.create_entity(

            "IfcRelDefinesByProperties",

            GlobalId=ifcopenshell.guid.new(),

            RelatedObjects=[

                element

            ],

            RelatingPropertyDefinition=pset

        )



    # ======================================
    # VALUE CONVERTER
    # ======================================

    def create_value(
        self,
        value
    ):


        if isinstance(
            value,
            bool
        ):

            return self.model.create_entity(
                "IfcBoolean",
                value
            )


        if isinstance(
            value,
            float
        ):

            return self.model.create_entity(
                "IfcReal",
                value
            )


        return self.model.create_entity(

            "IfcLabel",

            value

        )