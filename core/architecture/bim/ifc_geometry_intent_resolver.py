"""
ArchitectOS IFC Geometry Intent Resolver V1.1

Resolves IFC geometry intent from architectural geometry.

Design Principle
----------------
This resolver determines semantic geometry intent,
but MUST preserve the original architectural geometry.

It MUST NOT discard:

- dimensions
- coordinates
- position
- rotation
- alignment
- profile
- footprint
- elevation
- level
- architectural metadata
"""



class IFCGeometryIntentResolverV1:


    VERSION = "1.1"



    def __init__(
        self
    ):

        print(
            f"IFC GEOMETRY INTENT RESOLVER v{self.VERSION} ONLINE"
        )



    # ======================================
    # MAIN RESOLUTION
    # ======================================

    def resolve(
        self,
        ifc_mapping
    ):

        elements = ifc_mapping.get(
            "ifc_elements",
            []
        )


        geometry_elements = []



        for element in elements:


            original_geometry = (
                element.get(
                    "geometry",
                    {}
                )
            )


            if not isinstance(
                original_geometry,
                dict
            ):

                original_geometry = {}



            # --------------------------------
            # PRESERVE ORIGINAL GEOMETRY
            # --------------------------------

            geometry = dict(
                original_geometry
            )


            # --------------------------------
            # RESOLVE SEMANTIC INTENT
            # --------------------------------

            intent = (
                self._resolve_geometry_intent(
                    element
                )
            )


            # --------------------------------
            # MERGE INTENT WITHOUT LOSING
            # ARCHITECTURAL GEOMETRY
            # --------------------------------

            for key, value in intent.items():

                if value is None:
                    continue


                geometry[key] = value



            # --------------------------------
            # PRESERVE LEVEL
            # --------------------------------

            if (
                geometry.get("level")
                is None
            ):

                geometry["level"] = (
                    element.get(
                        "level"
                    )
                )



            # --------------------------------
            # PRESERVE IFC MAPPING CONTRACT
            #
            # IFC Mapping is authoritative for
            # semantic / provenance metadata.
            #
            # Geometry Intent Resolver may enrich
            # geometry, but must not discard the
            # mapped architectural contract.
            # --------------------------------

            resolved = dict(
                element
            )

            resolved[
                "geometry"
            ] = geometry

            if (
                resolved.get(
                    "level"
                )
                is None
            ):

                resolved[
                    "level"
                ] = geometry.get(
                    "level"
                )



            geometry_elements.append(
                resolved
            )



        return {

            "geometry_elements":
                geometry_elements,


            "element_count":
                len(
                    geometry_elements
                ),


            "source":
                "geometry_intent_resolution_v1.1"

        }



    # ======================================
    # GEOMETRY INTENT
    # ======================================

    def _resolve_geometry_intent(
        self,
        element
    ):

        geometry = element.get(
            "geometry",
            {}
        )


        if not isinstance(
            geometry,
            dict
        ):

            geometry = {}


        ifc_class = element.get(
            "ifc_class"
        )



        # ==================================
        # WALL
        # ==================================

        if ifc_class == "IfcWall":

            return {

                "geometry_type":
                    "extruded_wall",

                "alignment":
                    geometry.get(
                        "alignment"
                    )

            }



        # ==================================
        # SLAB
        # ==================================

        if ifc_class == "IfcSlab":

            return {

                "geometry_type":
                    "floor",


                "level":
                    geometry.get(
                        "level",
                        element.get(
                            "level"
                        )
                    )

            }



        # ==================================
        # ROOF
        # ==================================

        if ifc_class == "IfcRoof":


            if (
                geometry.get(
                    "shape"
                )
                ==
                "dome"
            ):

                return {

                    "geometry_type":
                        "dome",

                    "radius":
                        geometry.get(
                            "radius"
                        ),

                    "height":
                        geometry.get(
                            "height"
                        )

                }



            return {

                "geometry_type":
                    "roof"

            }



        # ==================================
        # COLUMN
        # ==================================

        if ifc_class == "IfcColumn":

            return {

                "geometry_type":
                    "column"

            }



        # ==================================
        # BEAM
        # ==================================

        if ifc_class == "IfcBeam":

            return {

                "geometry_type":
                    "beam"

            }



        # ==================================
        # WINDOW
        # ==================================

        if ifc_class == "IfcWindow":

            return {

                "geometry_type":
                    "opening",


                "facade_relation":
                    geometry.get(
                        "facade_relation"
                    )

            }



        # ==================================
        # DOOR
        # ==================================

        if ifc_class == "IfcDoor":

            return {

                "geometry_type":
                    "opening"

            }



        # ==================================
        # STAIR
        # ==================================

        if ifc_class == "IfcStair":

            return {

                "geometry_type":
                    "stair",


                "continuity":
                    geometry.get(
                        "continuity"
                    )

            }



        # ==================================
        # RAMP
        # ==================================

        if ifc_class == "IfcRamp":

            return {

                "geometry_type":
                    "ramp"

            }



        # ==================================
        # SPACE
        # ==================================

        if ifc_class == "IfcSpace":

            return {

                "geometry_type":
                    "space_volume",


                "closed":
                    geometry.get(
                        "closed"
                    )

            }



        # ==================================
        # GENERIC
        # ==================================

        return {

            "geometry_type":
                "architectural_element"

        }

# ======================================
# BACKWARD COMPATIBILITY
# ======================================

IFCGeometryIntentResolver = IFCGeometryIntentResolverV1