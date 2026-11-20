"""
ArchitectOS IFC Geometry Generator V1.1

Converts IFC geometry parameters
into IFC-ready geometry definitions.

Architecture-driven geometry generation.
"""


class IFCGeometryGeneratorV1:

    VERSION = "1.1"

    def __init__(self):

        print(
            f"🏗 IFC GEOMETRY GENERATOR v{self.VERSION} ONLINE"
        )

    # ======================================
    # GENERATE GEOMETRY
    # ======================================

    def generate(
        self,
        resolved_elements
    ):

        geometry_elements = []

        if isinstance(
            resolved_elements,
            dict
        ):

            elements = resolved_elements.get(
                "geometry_parameters",
                resolved_elements.get(
                    "resolved_geometry",
                    resolved_elements.get(
                        "geometry_elements",
                        []
                    )
                )
            )

        else:

            elements = resolved_elements

        if not isinstance(
            elements,
            list
        ):

            elements = []

        for element in elements:

            if not isinstance(
                element,
                dict
            ):
                continue

            geometry_elements.append({

                "ifc_class":
                    element.get(
                        "ifc_class"
                    ),

                "name":
                    element.get(
                        "name"
                    ),

                "level":
                    element.get(
                        "level"
                    ),

                "geometry":
                    self.generate_geometry(
                        element
                    )

            })

        return {

            "geometry_elements":
                geometry_elements,

            "element_count":
                len(
                    geometry_elements
                ),

            "source":
                "ifc_geometry_generation_v1.1"

        }

    # ======================================
    # GEOMETRY RESOLUTION
    # ======================================

    def generate_geometry(
        self,
        element
    ):

        geometry_intent = element.get(
            "geometry",
            {}
        )

        if not isinstance(
            geometry_intent,
            dict
        ):

            geometry_intent = {}

        geometry_type = geometry_intent.get(
            "geometry_type"
        )

        # ==================================
        # WALL
        # ==================================

        if geometry_type == "extruded_wall":

            return self._generate_wall_geometry(
                geometry_intent
            )

        # ==================================
        # FLOOR / SLAB
        # ==================================

        if geometry_type == "floor":

            return self._generate_slab_geometry(
                geometry_intent
            )

        # ==================================
        # SPACE
        # ==================================

        if geometry_type in (
            "space_volume",
            "closed_volume"
        ):

            return self._generate_space_geometry(
                geometry_intent
            )

        # ==================================
        # STAIR
        # ==================================

        if geometry_type == "stair":

            return self._generate_stair_geometry(
                geometry_intent
            )

        # ==================================
        # COLUMN
        # ==================================

        if geometry_type == "column":

            return self._generate_column_geometry(
                geometry_intent
            )

        # ==================================
        # BEAM
        # ==================================

        if geometry_type == "beam":

            return self._generate_beam_geometry(
                geometry_intent
            )

        # ==================================
        # OPENING
        # ==================================

        if geometry_type == "opening":

            return self._generate_opening_geometry(
                geometry_intent
            )

        # ==================================
        # DOME
        # ==================================

        if geometry_type == "dome":

            return self._generate_dome_geometry(
                geometry_intent
            )

        # ==================================
        # ROOF
        # ==================================

        if geometry_type == "roof":

            return self._generate_roof_geometry(
                geometry_intent
            )

        # ==================================
        # GENERIC
        # ==================================

        return self._generate_generic_geometry(
            geometry_intent
        )

    # ======================================
    # WALL
    # ======================================

    def _generate_wall_geometry(
        self,
        geometry
    ):

        result = {

            "type":
                "wall_extrusion",

            "height":
                geometry.get(
                    "height"
                ),

            "thickness":
                geometry.get(
                    "thickness"
                ),

            "direction":
                geometry.get(
                    "direction",
                    [0, 0, 1]
                )

        }

        self._preserve_geometry_fields(
            result,
            geometry
        )

        return result

    # ======================================
    # SLAB
    # ======================================

    def _generate_slab_geometry(
        self,
        geometry
    ):

        result = {

            "type":
                "horizontal_slab",

            "thickness":
                geometry.get(
                    "thickness"
                ),

            "direction":
                geometry.get(
                    "direction",
                    [0, 0, 1]
                )

        }

        self._preserve_geometry_fields(
            result,
            geometry
        )

        return result

    # ======================================
    # SPACE
    # ======================================

    def _generate_space_geometry(
        self,
        geometry
    ):

        result = {

            "type":
                "closed_volume",

            "height":
                geometry.get(
                    "height"
                ),

            "closed":
                geometry.get(
                    "closed",
                    True
                )

        }

        self._preserve_geometry_fields(
            result,
            geometry
        )

        return result

    # ======================================
    # STAIR
    # ======================================

    def _generate_stair_geometry(
        self,
        geometry
    ):

        result = {

            "type":
                "vertical_circulation",

            "continuous":
                geometry.get(
                    "continuity",
                    True
                )

        }

        self._preserve_geometry_fields(
            result,
            geometry
        )

        return result

    # ======================================
    # COLUMN
    # ======================================

    def _generate_column_geometry(
        self,
        geometry
    ):

        result = {

            "type":
                "vertical_extrusion",

            "profile":
                geometry.get(
                    "profile"
                ),

            "height":
                geometry.get(
                    "height"
                )

        }

        self._preserve_geometry_fields(
            result,
            geometry
        )

        return result

    # ======================================
    # BEAM
    # ======================================

    def _generate_beam_geometry(
        self,
        geometry
    ):

        result = {

            "type":
                "beam",

            "profile":
                geometry.get(
                    "profile"
                ),

            "height":
                geometry.get(
                    "height"
                )

        }

        self._preserve_geometry_fields(
            result,
            geometry
        )

        return result

    # ======================================
    # OPENING
    # ======================================

    def _generate_opening_geometry(
        self,
        geometry
    ):

        result = {

            "type":
                "opening",

            "facade_relation":
                geometry.get(
                    "facade_relation"
                ),

            "opening_type":
                geometry.get(
                    "opening_type"
                )

        }

        self._preserve_geometry_fields(
            result,
            geometry
        )

        return result

    # ======================================
    # DOME
    # ======================================

    def _generate_dome_geometry(
        self,
        geometry
    ):

        result = {

            "type":
                "dome",

            "position":
                geometry.get(
                    "position"
                ),

            "radius":
                geometry.get(
                    "radius"
                ),

            "height":
                geometry.get(
                    "height"
                )

        }

        self._preserve_geometry_fields(
            result,
            geometry
        )

        return result

    # ======================================
    # ROOF
    # ======================================

    def _generate_roof_geometry(
        self,
        geometry
    ):

        result = {

            "type":
                "roof",

            "shape":
                geometry.get(
                    "shape"
                ),

            "roof_form":
                geometry.get(
                    "roof_form"
                ),

            "height":
                geometry.get(
                    "height"
                )

        }

        self._preserve_geometry_fields(
            result,
            geometry
        )

        return result

    # ======================================
    # GENERIC
    # ======================================

    def _generate_generic_geometry(
        self,
        geometry
    ):

        result = {

            "type":
                "generic_architectural_geometry"

        }

        self._preserve_geometry_fields(
            result,
            geometry
        )

        return result

    # ======================================
    # PRESERVE ARCHITECTURAL DATA
    # ======================================

    def _preserve_geometry_fields(
        self,
        target,
        source
    ):

        if not isinstance(
            source,
            dict
        ):

            return target

        # ----------------------------------
        # Preserve ALL architectural geometry
        # ----------------------------------

        for field, value in source.items():

            if value is None:
                continue

            if field not in target:

                target[field] = value

        return target