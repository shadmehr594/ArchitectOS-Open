"""
ArchitectOS Facade Geometry Generator V1

Purpose:
Convert FacadeComponentResolver contract
into architectural facade geometry intent.

This layer does NOT:
- invent architectural style
- select materials
- generate render appearance
- modify structural geometry

It only converts resolved facade components
into geometry-ready architectural contracts.
"""


class FacadeGeometryGeneratorV1:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🏛 FACADE GEOMETRY GENERATOR v1.0 ONLINE"
        )


    # ==================================================
    # GENERATE
    # ==================================================

    def generate(
        self,
        component_contract,
        architectural_geometry=None
    ):


        architectural_geometry = (
            architectural_geometry
            if isinstance(
                architectural_geometry,
                dict
            )
            else {}
        )


        component_contract = (
            component_contract
            if isinstance(
                component_contract,
                dict
            )
            else {}
        )


        result = {

            "version":
                self.VERSION,

            "style":
                component_contract.get(
                    "style"
                ),

            "components":
                [],

            "component_count":
                0,

            "geometry_status":
                "pending",

            "source":
                "facade_component_contract"

        }


        physical_walls = architectural_geometry.get(
            "physical_walls",
            []
        )


        openings = architectural_geometry.get(
            "openings",
            []
        )


        floor_geometry = architectural_geometry.get(
            "floor_geometry",
            []
        )


        roof_geometry = architectural_geometry.get(
            "roof_geometry",
            {}
        )


        if not isinstance(
            physical_walls,
            list
        ):

            physical_walls = []


        if not isinstance(
            openings,
            list
        ):

            openings = []


        if not isinstance(
            floor_geometry,
            list
        ):

            floor_geometry = []


        if not isinstance(
            roof_geometry,
            dict
        ):

            roof_geometry = {}


        for component in component_contract.get(
            "components",
            []
        ):


            if not isinstance(
                component,
                dict
            ):

                continue


            item = self._build_component_geometry(
                component,
                physical_walls,
                openings,
                floor_geometry,
                roof_geometry
            )


            if item:

                result[
                    "components"
                ].append(
                    item
                )


        result[
            "component_count"
        ] = len(
            result[
                "components"
            ]
        )


        if result[
            "component_count"
        ]:

            result[
                "geometry_status"
            ] = "resolved_component_geometry_contract"


        print(
            "\n====== FACADE GEOMETRY CONTRACT ======"
        )

        print(
            "STYLE:",
            result.get(
                "style"
            )
        )

        print(
            "COMPONENT COUNT:",
            result.get(
                "component_count"
            )
        )


        for component in result.get(
            "components",
            []
        ):

            print(
                component.get(
                    "id"
                ),
                component.get(
                    "component_type"
                ),
                component.get(
                    "geometry_mode"
                ),
                component.get(
                    "geometry_status"
                )
            )


        print(
            "======================================="
        )


        return result


    # ==================================================
    # COMPONENT GEOMETRY CONTRACT
    # ==================================================

    def _build_component_geometry(
        self,
        component,
        physical_walls,
        openings,
        floor_geometry,
        roof_geometry
    ):


        component_type = component.get(
            "component_type"
        )


        geometry_mode = component.get(
            "geometry_mode"
        )


        item = {

            "id":
                component.get(
                    "id"
                ),

            "component_type":
                component_type,

            "role":
                component.get(
                    "role"
                ),

            "geometry_mode":
                geometry_mode,

            "material":
                component.get(
                    "material"
                ),

            "geometry_status":
                "geometry_reference_resolved",

            "source":
                "facade_component_resolver"

        }


        # ------------------------------------------
        # WALL-BASED COMPONENTS
        # ------------------------------------------

        if geometry_mode in [

            "generic_procedural_component",
            "vertical_panel",
            "repeated_shading_component",
            "recess_profile"

        ]:

            item[
                "reference_geometry"
            ] = {

                "type":
                    "physical_walls",

                "count":
                    len(
                        physical_walls
                    )

            }


        # ------------------------------------------
        # OPENING-BASED COMPONENTS
        # ------------------------------------------

        elif geometry_mode in [

            "glazing_panel",
            "opening_frame",
            "entrance_component"

        ]:

            item[
                "reference_geometry"
            ] = {

                "type":
                    "openings",

                "count":
                    len(
                        openings
                    )

            }


        # ------------------------------------------
        # FLOOR / BASE COMPONENTS
        # ------------------------------------------

        elif geometry_mode in [

            "horizontal_profile",
            "horizontal_projection"

        ]:

            item[
                "reference_geometry"
            ] = {

                "type":
                    "floor_geometry",

                "count":
                    len(
                        floor_geometry
                    )

            }


        # ------------------------------------------
        # ROOF / UPPER COMPONENTS
        # ------------------------------------------

        elif geometry_mode in [

            "linear_extrusion"

        ]:

            item[
                "reference_geometry"
            ] = {

                "type":
                    "roof_geometry",

                "available":
                    bool(
                        roof_geometry
                    )

            }


        else:

            item[
                "reference_geometry"
            ] = {

                "type":
                    "architectural_geometry",

                "status":
                    "generic_reference"

            }


        return item