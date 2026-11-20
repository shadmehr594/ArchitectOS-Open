class ExteriorBIMBridge:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🏗 EXTERIOR BIM BRIDGE v1.0 ONLINE"
        )



    def map_exterior(
        self,
        exterior_design,
        architectural_geometry=None,
        facade_components=None,
        facade_geometry=None
    ):


        exterior = exterior_design.get(
            "exterior_design",
            {}
        )


        elements = []

        if not isinstance(
            architectural_geometry,
            dict
        ):

            architectural_geometry = {}


        if not isinstance(
            facade_components,
            dict
        ):

            facade_components = {}


        if not isinstance(
            facade_geometry,
            dict
        ):

            facade_geometry = {}

        # ===============================
        # ARCHITECTURAL GEOMETRY
        # ===============================

        if architectural_geometry:

            for space in architectural_geometry.get(
                "spaces",
                []
            ):

                elements.append(

                    {

                        "type":
                            "IfcSpace",

                        "name":
                            space.get("name"),

                        "floor":
                            space.get("floor"),

                        "geometry_type":
                            space.get("type"),

                        "shape":
                            space.get("shape"),

                        "height":
                            space.get("height")

                    }

                )


            for vertical in architectural_geometry.get(
                "vertical_geometry",
                []
            ):

                elements.append(

                    {

                        "type":
                            "IfcBuildingElementProxy",

                        "name":
                            vertical.get("name"),

                        "geometry_type":
                            vertical.get("type")

                    }

                )


        # ===============================
        # FACADE COMPONENT GEOMETRY
        # ARCHITECTURE-FIRST v1.0
        # ===============================

        resolved_facade_components = (
            facade_geometry.get(
                "components",
                []
            )
        )


        if not isinstance(
            resolved_facade_components,
            list
        ):

            resolved_facade_components = []


        for component in resolved_facade_components:

            if not isinstance(
                component,
                dict
            ):

                continue


            component_type = component.get(
                "component_type"
            )


            role = component.get(
                "role"
            )


            geometry_mode = component.get(
                "geometry_mode"
            )


            material = component.get(
                "material"
            )


            reference_geometry = component.get(
                "reference_geometry",
                {}
            )


            if not isinstance(
                reference_geometry,
                dict
            ):

                reference_geometry = {}


            # ----------------------------------
            # WALL / CLADDING / SURFACE
            # ----------------------------------

            if role in {
                "wall_surface",
                "vertical_element"
            }:

                ifc_type = (
                    "IfcWall"
                    if role == "wall_surface"
                    else "IfcBuildingElementProxy"
                )


            # ----------------------------------
            # OPENING COMPONENTS
            # ----------------------------------

            elif role == "opening":

                if (
                    "glazing"
                    in str(
                        component_type
                    ).lower()
                ):

                    ifc_type = "IfcWindow"

                else:

                    ifc_type = (
                        "IfcBuildingElementProxy"
                    )


            # ----------------------------------
            # ENTRANCE COMPONENTS
            # ----------------------------------

            elif role == "entrance_feature":

                if (
                    "entry"
                    in str(
                        component_type
                    ).lower()
                    or
                    "door"
                    in str(
                        component_type
                    ).lower()
                ):

                    ifc_type = "IfcDoor"

                else:

                    ifc_type = (
                        "IfcBuildingElementProxy"
                    )


            # ----------------------------------
            # UPPER / ROOF COMPONENTS
            # ----------------------------------

            elif role == "upper_element":

                ifc_type = (
                    "IfcBuildingElementProxy"
                )


            # ----------------------------------
            # BASE
            # ----------------------------------

            elif role == "base":

                ifc_type = (
                    "IfcBuildingElementProxy"
                )


            else:

                ifc_type = (
                    "IfcBuildingElementProxy"
                )


            elements.append(

                {

                    "type":
                        ifc_type,

                    "name":
                        component_type,

                    "component_id":
                        component.get(
                            "id"
                        ),

                    "component_type":
                        component_type,

                    "facade_role":
                        role,

                    "geometry_mode":
                        geometry_mode,

                    "material":
                        material,

                    "reference_geometry":
                        reference_geometry,

                    "architectural_authority":
                        component.get(
                            "architectural_authority",
                            True
                        ),

                    "source":
                        "facade_geometry_contract"

                }

            )



        # ===============================
        # LEGACY FACADE FALLBACK
        # ===============================

        if not resolved_facade_components:

            # ===============================
            # FACADE
            # ===============================

            facade = exterior.get(
                "facade",
                {}
            )


            assembly = facade.get(
                "assembly",
                {}
            )


            facade_system = assembly.get(
                "facade_system",
                {}
            )


            wall_surface = facade_system.get(
                "wall_surface",
                {}
            )


            if wall_surface:

                elements.append(

                    {

                        "type":
                            "IfcWall",

                        "name":
                            "Facade Wall",

                        "material":
                            wall_surface.get(
                                "material"
                            ),

                        "source":
                            "legacy_exterior_fallback"

                    }

                )


            # ===============================
            # WINDOWS
            # ===============================

            details = exterior.get(
                "details",
                {}
            )


            exterior_details = details.get(
                "exterior_details",
                {}
            )


            for window in exterior_details.get(
                "windows",
                []
            ):

                elements.append(

                    {

                        "type":
                            "IfcWindow",

                        "name":
                            window,

                        "material":
                            None,

                        "source":
                            "legacy_exterior_fallback"

                    }

                )


            # ===============================
            # VERTICAL ELEMENTS
            # ===============================

            for element in exterior_details.get(
                "vertical_elements",
                []
            ):

                elements.append(

                    {

                        "type":
                            "IfcBuildingElementProxy",

                        "name":
                            element,

                        "material":
                            None,

                        "source":
                            "legacy_exterior_fallback"

                    }

                )


        # ===============================
        # ARCHITECTURAL ROOF GEOMETRY
        # ARCHITECTURE-FIRST v1.0
        # ===============================

        roof_geometry = architectural_geometry.get(
            "roof_geometry",
            {}
        )


        if not isinstance(
            roof_geometry,
            dict
        ):

            roof_geometry = {}


        roof_geometry_status = roof_geometry.get(
            "geometry_status"
        )


        roof_type = roof_geometry.get(
            "roof_type"
        )


        roof_footprint = roof_geometry.get(
            "footprint",
            {}
        )


        if not isinstance(
            roof_footprint,
            dict
        ):

            roof_footprint = {}


        if (
            roof_type
            and
            roof_geometry_status
            in {
                "resolved_roof_envelope",
                "resolved_metric_envelope"
            }
        ):

            elements.append(

                {

                    "type":
                        "IfcRoof",

                    "name":
                        roof_type,

                    "architectural_role":
                        "building_roof",

                    "roof_type":
                        roof_type,

                    "source_floor":
                        roof_geometry.get(
                            "source_floor"
                        ),

                    "geometry_status":
                        roof_geometry_status,

                    "reference_geometry":
                        {

                            "type":
                                "roof_geometry",

                            "footprint":
                                roof_footprint,

                            "coordinate_mode":
                                roof_geometry.get(
                                    "coordinate_mode"
                                )

                        },

                    "architectural_elements":
                        roof_geometry.get(
                            "elements",
                            []
                        ),

                    "skyline":
                        roof_geometry.get(
                            "skyline"
                        ),

                    "material":
                        roof_geometry.get(
                            "material"
                        ),

                    "architectural_authority":
                        True,

                    "source":
                        "architectural_roof_geometry_contract"

                }

            )



        # ===============================
        # ROOF / DOME
        # ARCHITECTURE-FIRST v1.1
        # ===============================

        dome = exterior.get(
            "dome",
            {}
        )


        if isinstance(
            dome,
            dict
        ):

            dome_data = dome.get(
                "dome_strategy",
                dome
            )


            if not isinstance(
                dome_data,
                dict
            ):

                dome_data = {}


            dome_type = dome_data.get(
                "dome_type"
            )


            if dome_type:

                dome_material = dome_data.get(
                    "material"
                )


                elements.append(

                    {

                        "type":
                            "IfcRoof",

                        "name":
                            dome_type,

                        "material":
                            dome_material,

                        "architectural_role":
                            "dome",

                        "source":
                            "architectural_exterior_contract"

                    }

                )



        # ===============================
        # BOUNDARY
        # ARCHITECTURE-FIRST v1.1
        # ===============================

        boundary = exterior.get(
            "boundary",
            {}
        )


        if isinstance(
            boundary,
            dict
        ):

            boundary_wall = boundary.get(
                "wall",
                {}
            )


            if isinstance(
                boundary_wall,
                dict
            ):

                boundary_wall_data = (
                    boundary_wall.get(
                        "boundary_wall",
                        boundary_wall
                    )
                )


                if not isinstance(
                    boundary_wall_data,
                    dict
                ):

                    boundary_wall_data = {}


                boundary_type = (
                    boundary_wall_data.get(
                        "type"
                    )
                )


                boundary_material = (
                    boundary_wall_data.get(
                        "material"
                    )
                )


                boundary_elements = (
                    boundary_wall_data.get(
                        "elements",
                        []
                    )
                )


                if (
                    boundary_type
                    or boundary_material
                    or boundary_elements
                ):

                    elements.append(

                        {

                            "type":
                                "IfcWall",

                            "name":
                                (
                                    boundary_type
                                    or
                                    "architectural_boundary_wall"
                                ),

                            "material":
                                boundary_material,

                            "architectural_elements":
                                boundary_elements,

                            "architectural_role":
                                "site_boundary",

                            "source":
                                "architectural_exterior_contract"

                        }

                    )

        # ===============================
        # FINAL EXTERIOR BIM CONTRACT
        # ===============================

        return {

            "bim_elements":
                elements,

            "element_count":
                len(elements),

            "source":
                "exterior_bim_mapping",

            "domain":
                "exterior"

        }