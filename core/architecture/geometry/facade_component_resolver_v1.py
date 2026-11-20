"""
ArchitectOS Facade Component Resolver V1

Converts architectural facade reasoning into
a normalized facade component contract.

This layer does NOT generate detailed mesh geometry.

It converts semantic facade knowledge such as:

- stone_cladding
- brick_surface
- pilasters
- cornice
- balustrade
- large_glazing
- shading_elements

into procedural facade component requests.
"""


class FacadeComponentResolverV1:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"🏛 FACADE COMPONENT RESOLVER v{self.VERSION} ONLINE"
        )


    # ======================================================
    # RESOLVE
    # ======================================================

    def resolve(
        self,
        complete_exterior_design
    ):


        result = {

            "version":
                self.VERSION,

            "style":
                None,

            "components":
                [],

            "composition":
                {},

            "component_count":
                0,

            "source":
                "architectural_facade_reasoning"

        }


        if not isinstance(
            complete_exterior_design,
            dict
        ):

            return result


        exterior = complete_exterior_design.get(
            "exterior_design",
            complete_exterior_design
        )


        if not isinstance(
            exterior,
            dict
        ):

            return result


        style = exterior.get(
            "style"
        )


        result[
            "style"
        ] = style


        facade = exterior.get(
            "facade",
            {}
        )


        if not isinstance(
            facade,
            dict
        ):

            facade = {}


        assembly = facade.get(
            "assembly",
            {}
        )


        composition = facade.get(
            "composition",
            {}
        )


        result[
            "composition"
        ] = composition


        facade_system = assembly.get(
            "facade_system",
            assembly
        )


        if not isinstance(
            facade_system,
            dict
        ):

            facade_system = {}


        # ==================================================
        # BASE
        # ==================================================

        self._append_single_component(

            result["components"],

            facade_system.get(
                "base"
            ),

            role="base",

            style=style

        )


        # ==================================================
        # WALL SURFACE
        # ==================================================

        self._append_single_component(

            result["components"],

            facade_system.get(
                "wall_surface"
            ),

            role="wall_surface",

            style=style

        )


        # ==================================================
        # OPENINGS
        # ==================================================

        self._append_component_group(

            result["components"],

            facade_system.get(
                "openings"
            ),

            role="opening",

            style=style

        )


        # ==================================================
        # VERTICAL ELEMENTS
        # ==================================================

        self._append_component_group(

            result["components"],

            facade_system.get(
                "vertical_elements"
            ),

            role="vertical_element",

            style=style

        )


        # ==================================================
        # UPPER ELEMENTS
        # ==================================================

        self._append_component_group(

            result["components"],

            facade_system.get(
                "upper_elements"
            ),

            role="upper_element",

            style=style

        )


        # ==================================================
        # COMPOSITION-DRIVEN ENTRANCE COMPONENTS
        # ==================================================

        composition_data = composition.get(
            "facade_composition",
            composition
        )

        resolved_glazing_material = None
        resolved_frame_material = None


        for component in result.get(
            "components",
            []
        ):

            if not isinstance(
                component,
                dict
            ):

                continue


            component_type = str(
                component.get(
                    "component_type",
                    ""
                )
            ).lower()


            component_material = (
                component.get(
                    "material"
                )
            )


            if not component_material:

                continue


            if (
                resolved_glazing_material is None
                and
                (
                    "glazing" in component_type
                    or
                    "glass" in component_type
                )
            ):

                resolved_glazing_material = (
                    component_material
                )


            if (
                resolved_frame_material is None
                and
                "frame" in component_type
            ):

                resolved_frame_material = (
                    component_material
                )


        if isinstance(
            composition_data,
            dict
        ):

            entrance = composition_data.get(
                "entrance",
                {}
            )


            if isinstance(
                entrance,
                dict
            ):

                for element in entrance.get(
                    "elements",
                    []
                ):


                    element_text = str(
                        element
                    ).lower()


                    entrance_material = None


                    if (
                        "glass" in element_text
                        or
                        "glazing" in element_text
                    ):

                        entrance_material = (
                            resolved_glazing_material
                        )


                    elif "frame" in element_text:

                        entrance_material = (
                            resolved_frame_material
                        )


                    self._append_named_component(

                        result["components"],

                        element,

                        role="entrance_feature",

                        style=style,

                        material=entrance_material

                    )


        # ==================================================
        # REMOVE DUPLICATES
        # ==================================================

        result[
            "components"
        ] = self._deduplicate(
            result["components"]
        )


        # ==================================================
        # IDS
        # ==================================================

        for index, component in enumerate(
            result["components"],
            start=1
        ):

            component[
                "id"
            ] = (
                f"facade_component_{index:03}"
            )


        result[
            "component_count"
        ] = len(
            result["components"]
        )


        print(
            "\n====== FACADE COMPONENT CONTRACT ======"
        )

        print(
            "STYLE:",
            result["style"]
        )

        print(
            "COMPONENT COUNT:",
            result["component_count"]
        )

        for component in result["components"]:

            print(
                component["id"],
                component["component_type"],
                component["role"],
                component["geometry_mode"],
                component.get("material")
            )

        print(
            "========================================"
        )


        return result


    # ======================================================
    # SINGLE COMPONENT
    # ======================================================

    def _append_single_component(
        self,
        target,
        data,
        role,
        style
    ):


        if not isinstance(
            data,
            dict
        ):

            return


        element = data.get(
            "element"
        )


        if not element:

            return


        self._append_named_component(

            target,

            element,

            role=role,

            style=style,

            material=data.get(
                "material"
            )

        )


    # ======================================================
    # COMPONENT GROUP
    # ======================================================

    def _append_component_group(
        self,
        target,
        data,
        role,
        style
    ):


        if not isinstance(
            data,
            dict
        ):

            return


        material = data.get(
            "material"
        )


        glazing_material = data.get(
            "glazing_material",
            material
        )


        frame_material = data.get(
            "frame_material",
            material
        )


        single_element = data.get(
            "element"
        )


        if single_element:

            self._append_named_component(

                target,

                single_element,

                role=role,

                style=style,

                material=material

            )


        for element in data.get(
            "elements",
            []
        ):


            element_text = str(
                element
            ).lower()


            resolved_material = material


            if (
                "glazing" in element_text
                or
                "glass" in element_text
            ):

                resolved_material = (
                    glazing_material
                )


            elif "frame" in element_text:

                resolved_material = (
                    frame_material
                )


            self._append_named_component(

                target,

                element,

                role=role,

                style=style,

                material=resolved_material

            )


    # ======================================================
    # NORMALIZED COMPONENT
    # ======================================================

    def _append_named_component(
        self,
        target,
        element,
        role,
        style,
        material
    ):


        if not element:

            return


        component = {

            "component_type":
                element,

            "role":
                role,

            "style":
                style,

            "material":
                material,

            "geometry_mode":
                self._resolve_geometry_mode(
                    element
                ),

            "parameters":
                self._default_parameters(
                    element
                ),

            "architectural_authority":
                True,

            "source":
                "facade_component_resolver"

        }


        target.append(
            component
        )


    # ======================================================
    # GEOMETRY MODE
    # ======================================================

    def _resolve_geometry_mode(
        self,
        component_type
    ):


        text = str(
            component_type
        ).lower()


        if "brick" in text:

            return "surface_pattern"


        if "cladding" in text:

            return "surface_layer"


        if "plinth" in text:

            return "horizontal_profile"


        if "cornice" in text:

            return "horizontal_profile"


        if "parapet" in text:

            return "linear_extrusion"


        if "shadow_gap" in text:

            return "recess_profile"


        if "column" in text:

            return "vertical_profile"


        if "pilaster" in text:

            return "vertical_profile"


        if "balustrade" in text:

            return "repeated_linear_component"


        if "arch" in text:

            return "arched_profile"


        if "window" in text:

            return "opening_frame"


        if "glazing" in text:

            return "glazing_panel"


        if "frame" in text:

            return "opening_frame"


        if "shading" in text:

            return "repeated_shading_component"


        if "vertical_plane" in text:

            return "vertical_panel"


        if "canopy" in text:

            return "horizontal_projection"


        if "entry" in text:

            return "entrance_component"


        return "generic_procedural_component"


    # ======================================================
    # DEFAULT PARAMETERS
    # ======================================================

    def _default_parameters(
        self,
        component_type
    ):


        text = str(
            component_type
        ).lower()


        parameters = {

            "dimension_status":
                "pending_geometry_context",

            "placement_status":
                "pending_facade_surface"

        }


        if "brick" in text:

            parameters[
                "pattern_mode"
            ] = "repeatable"


        if "cornice" in text:

            parameters[
                "profile_mode"
            ] = "continuous"


        if "balustrade" in text:

            parameters[
                "distribution_mode"
            ] = "repeat_along_edge"


        if (
            "column" in text
            or
            "pilaster" in text
        ):

            parameters[
                "alignment_mode"
            ] = "vertical"


        if "shading" in text:

            parameters[
                "distribution_mode"
            ] = "opening_driven"


        return parameters


    # ======================================================
    # DEDUPLICATION
    # ======================================================

    def _deduplicate(
        self,
        components
    ):


        result = []

        seen = set()


        for component in components:

            key = (

                component.get(
                    "component_type"
                ),

                component.get(
                    "role"
                )

            )


            if key in seen:

                continue


            seen.add(
                key
            )


            result.append(
                component
            )


        return result