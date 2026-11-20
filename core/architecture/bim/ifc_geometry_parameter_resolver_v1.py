"""
ArchitectOS IFC Geometry Parameter Resolver v1.2

Resolves IFC geometry parameters
from architectural intelligence context.

Design Principle
----------------
This resolver MUST preserve the complete architectural
geometry contract.

It may resolve missing IFC parameters from context,
but MUST NOT discard architectural geometry fields.

Architecture
    |
    v
Geometry Intent
    |
    v
Parameter Resolution
    |
    v
Complete Geometry Contract
"""


class IFCGeometryParameterResolverV1:


    VERSION = "1.2"



    def __init__(
        self,
        context=None
    ):

        print(
            f"IFC GEOMETRY PARAMETER RESOLVER v{self.VERSION} ONLINE"
        )


        self.context = context or {}



    # ======================================
    # MAIN RESOLUTION
    # ======================================

    def resolve(
        self,
        resolved_geometry
    ):


        if isinstance(
            resolved_geometry,
            dict
        ):

            elements = (
                resolved_geometry.get(
                    "geometry_intents",
                    resolved_geometry.get(
                        "resolved_geometry",
                        resolved_geometry.get(
                            "geometry_elements",
                            []
                        )
                    )
                )
            )

        else:

            elements = resolved_geometry



        if not isinstance(
            elements,
            list
        ):

            elements = []



        result = []


        for element in elements:


            if not isinstance(
                element,
                dict
            ):

                continue


            source_geometry = element.get(
                "geometry",
                {}
            )


            if not isinstance(
                source_geometry,
                dict
            ):

                source_geometry = {}



            ifc_class = element.get(
                "ifc_class"
            )



            # --------------------------------
            # PRESERVE ALL ARCHITECTURAL DATA
            # --------------------------------

            geometry = dict(
                source_geometry
            )



            # --------------------------------
            # RESOLVE IFC PARAMETERS
            # --------------------------------

            parameters = self._resolve_parameters(
                ifc_class,
                geometry
            )



            # --------------------------------
            # MERGE PARAMETERS WITHOUT
            # DESTROYING ARCHITECTURAL DATA
            # --------------------------------

            for key, value in parameters.items():

                if value is None:
                    continue


                geometry[key] = value



            # --------------------------------
            # LEVEL PROVENANCE
            # --------------------------------

            level = element.get(
                "level"
            )


            if geometry.get(
                "level"
            ) is None:

                geometry["level"] = level



            result.append(

                {

                    "ifc_class":
                        ifc_class,


                    "name":
                        element.get(
                            "name"
                        ),


                    "level":
                        level,


                    "geometry":
                        geometry

                }

            )



        return {


            "geometry_parameters":
                result,


            "element_count":
                len(
                    result
                ),


            "source":
                "ifc_geometry_parameter_resolution_v1.2"

        }



    # ======================================
    # PARAMETER RESOLUTION
    # ======================================

    def _resolve_parameters(
        self,
        ifc_class,
        geometry
    ):

        # ======================================
        # PRESERVE ORIGINAL ARCHITECTURAL GEOMETRY
        # ======================================

        if not isinstance(
            geometry,
            dict
        ):

            geometry = {}

        parameters = dict(
            geometry
        )

        # ======================================
        # WALL
        # ======================================

        if ifc_class == "IfcWall":

            parameters.update({

                "geometry_type":
                    "extruded_wall",

                "height":
                    self.resolve_height(
                        geometry
                    ),

                "thickness":
                    self.resolve_wall_thickness(
                        geometry
                    ),

                "profile":
                    self.resolve_wall_profile(),

                "direction":
                    self.resolve_direction()

            })

            return parameters

        # ======================================
        # SLAB
        # ======================================

        if ifc_class == "IfcSlab":

            parameters.update({

                "geometry_type":
                    "floor",

                "thickness":
                    self.resolve_slab_thickness(
                        geometry
                    ),

                "elevation":
                    self.resolve_elevation(
                        geometry
                    ),

                "profile":
                    "horizontal"

            })

            return parameters

        # ======================================
        # SPACE
        # ======================================

        if ifc_class == "IfcSpace":

            parameters.update({

                "geometry_type":
                    "closed_volume",

                "height":
                    self.resolve_height(
                        geometry
                    ),

                "closed":
                    True

            })

            return parameters

        # ======================================
        # STAIR
        # ======================================

        if ifc_class == "IfcStair":

            parameters.update({

                "geometry_type":
                    "stair",

                "continuous":
                    geometry.get(
                        "continuity",
                        True
                    )

            })

            return parameters

        # ======================================
        # COLUMN
        # ======================================

        if ifc_class == "IfcColumn":

            parameters.update({

                "geometry_type":
                    "column"

            })

            return parameters

        # ======================================
        # BEAM
        # ======================================

        if ifc_class == "IfcBeam":

            parameters.update({

                "geometry_type":
                    "beam"

            })

            return parameters

        # ======================================
        # WINDOW
        # ======================================

        if ifc_class == "IfcWindow":

            parameters.update({

                "geometry_type":
                    "opening"

            })

            return parameters

        # ======================================
        # DOOR
        # ======================================

        if ifc_class == "IfcDoor":

            parameters.update({

                "geometry_type":
                    "opening"

            })

            return parameters

        # ======================================
        # RAMP
        # ======================================

        if ifc_class == "IfcRamp":

            parameters.update({

                "geometry_type":
                    "ramp"

            })

            return parameters

        # ======================================
        # ROOF
        # ======================================

        if ifc_class == "IfcRoof":

            parameters.update({

                "geometry_type":
                    "roof"

            })

            return parameters

        # ======================================
        # GENERIC
        # ======================================

        parameters.update({

            "geometry_type":
                "architectural_element"

        })

        return parameters



    # ======================================
    # HEIGHT
    # ======================================

    def resolve_height(
        self,
        geometry
    ):


        value = geometry.get(
            "height"
        )


        if value is not None:

            return value


        return self.context.get(
            "floor_height"
        )



    # ======================================
    # WALL THICKNESS
    # ======================================

    def resolve_wall_thickness(
        self,
        geometry
    ):


        value = geometry.get(
            "thickness"
        )


        if value is not None:

            return value


        return self.context.get(
            "wall_thickness"
        )



    # ======================================
    # SLAB THICKNESS
    # ======================================

    def resolve_slab_thickness(
        self,
        geometry
    ):


        value = geometry.get(
            "thickness"
        )


        if value is not None:

            return value


        return self.context.get(
            "slab_thickness"
        )



    # ======================================
    # ELEVATION
    # ======================================

    def resolve_elevation(
        self,
        geometry
    ):


        value = geometry.get(
            "elevation"
        )


        if value is not None:

            return value



        level = geometry.get(
            "level"
        )


        return self.context.get(
            "level_elevations",
            {}
        ).get(
            level
        )



    # ======================================
    # WALL PROFILE
    # ======================================

    def resolve_wall_profile(
        self
    ):


        return self.context.get(
            "wall_profile"
        )



    # ======================================
    # DEFAULT DIRECTION
    # ======================================

    def resolve_direction(
        self
    ):


        return self.context.get(
            "default_direction"
        )