"""
ArchitectOS Architectural Element Placement Reasoner V3

Places architectural spaces and vertical systems
based on architectural program reasoning.
"""


class ArchitecturalElementPlacementReasonerV3:


    VERSION = "3.0"



    def __init__(self):

        print(
            "🏗 ARCHITECTURAL ELEMENT PLACEMENT REASONER V3 ONLINE"
        )



    def generate(
        self,
        architectural_layout,
        contract,
        vertical_decision,
        accessibility_result=None
    ):


        accessibility_result = accessibility_result or {}



        result = {


            "floors": {},

            "vertical_core": [],

            "floor_heights": {},

            "design_logic": []

        }



        # ==================================
        # FLOOR CREATION
        # ==================================

        floor_distribution = contract.get(

            "vertical_organization",

            {}

        )



        # ==============================================
        # AUTHORITATIVE ARCHITECTURAL SPACE CONTRACT
        #
        # SpatialContract is the normalized architectural
        # contract passed into placement.
        #
        # It preserves semantic/program evidence such as:
        #
        # - protected_zone
        # - placement_scope
        # - access_requirement
        # - dimensional_requirements
        # - parcel / spatial placement evidence
        #
        # LayoutIntent remains a fallback only for older
        # callers that do not provide contract spaces.
        #
        # No architectural metadata is reconstructed here.
        # ==============================================

        spaces = contract.get(
            "spaces",
            []
        )

        if not isinstance(
            spaces,
            list
        ) or not spaces:

            spaces = architectural_layout.get(
                "spaces",
                []
            )



        # ==============================================
        # FLOOR-AWARE SPACE IDENTITY v1.0
        #
        # Space identity is not name-only.
        #
        # Example:
        #
        # corridor @ ground_floor
        # corridor @ upper_floor
        #
        # must remain separate architectural instances.
        # ==============================================

        space_map = {}


        for item in spaces:

            if not isinstance(
                item,
                dict
            ):

                continue


            item_name = item.get(
                "name"
            )

            item_floor = item.get(
                "floor"
            )


            if not item_name:

                continue


            space_map[
                (
                    item_name,
                    item_floor
                )
            ] = item


        # ==============================================
        # REAL FLOOR ↔ SEMANTIC FLOOR RESOLUTION v3.1
        #
        # Resolve floor identity from complete space
        # membership. Level names and semantic floor
        # names remain contract-defined and unrestricted.
        # ==============================================

        semantic_floor_space_names = {}


        for item in spaces:

            if not isinstance(item, dict):

                continue


            item_name = item.get("name")
            item_floor = item.get("floor")


            if not item_name or not item_floor:

                continue


            semantic_floor_space_names.setdefault(
                item_floor,
                []
            ).append(
                item_name
            )


        semantic_floor_by_real_floor = {}


        for real_floor, floor_space_names in (
            floor_distribution.items()
        ):

            if not isinstance(floor_space_names, list):

                continue


            real_floor_names = sorted(
                name
                for name in floor_space_names
                if name
            )


            matched_semantic_floors = [
                semantic_floor
                for semantic_floor, semantic_names
                in semantic_floor_space_names.items()
                if sorted(
                    name
                    for name in semantic_names
                    if name
                ) == real_floor_names
            ]


            if len(matched_semantic_floors) == 1:

                semantic_floor_by_real_floor[
                    real_floor
                ] = matched_semantic_floors[0]



        for floor, names in floor_distribution.items():


            floor_spaces = []


            site_spaces = []



            for name in names:


                semantic_floor = semantic_floor_by_real_floor.get(
                    floor,
                    floor
                )


                space = space_map.get(
                    (
                        name,
                        semantic_floor
                    )
                )


                if not space:

                    continue



                if space.get("zone") == "external":


                    site_spaces.append(

                        space

                    )


                else:


                    floor_spaces.append(

                        space

                    )



            # ------------------------------
            # REAL FLOOR
            # ------------------------------

            if floor_spaces:


                result["floors"][floor] = {


                    "spaces": floor_spaces,


                    "elements": [],


                    "height":

                        self.get_floor_height(

                            floor,

                            contract

                        )

                }



                result["floor_heights"][floor] = (

                    result["floors"][floor]["height"]

                )



            # ------------------------------
            # SITE / EXTERNAL
            # ------------------------------

            if site_spaces:


                result["floors"].setdefault(

                    "SITE",

                    {

                        "spaces": [],

                        "elements": [],

                        "height": 0

                    }

                )


                result["floors"]["SITE"]["spaces"].extend(

                    site_spaces

                )




        # ==================================
        # VERTICAL SYSTEMS
        # ==================================


        vertical_systems = list(


            vertical_decision.get(


                "vertical_systems",


                []

            )

        )



        vertical_systems.extend(


            accessibility_result.get(


                "systems",


                []

            )

        )





        for system in vertical_systems:



            system_type = system.get(

                "type"

            )



            if not system_type:

                continue



            element = {

                "name":
                    system_type,

                "type":
                    system_type,

                "category":
                    self.get_element_category(
                        system_type
                    ),

                "placement_intent":
                    dict(system.get("placement_intent"))
                    if isinstance(system.get("placement_intent"), dict)
                    and system.get("placement_intent")
                    else self.get_placement_intent(system_type),

                "continuous":
                    system.get(
                        "continuous",
                        True
                    ),

                "reason":
                    system.get(
                        "reason"
                    ),

                "connects":
                    list(
                        system.get(
                            "connects",
                            []
                        )
                    ),

                "parameters":
                    dict(
                        system.get(
                            "parameters",
                            {}
                        )
                    ),

                "protected_zone":
                    system.get(
                        "protected_zone",
                        False
                    )

            }



            result["vertical_core"].append(

                element

            )





        # ==================================
        # ATTACH VERTICAL ELEMENTS
        # ==================================


        for floor, data in result["floors"].items():

            for element in result["vertical_core"]:

                connects = element.get(
                    "connects",
                    []
                )

                # ----------------------------------
                # SYSTEM HAS EXPLICIT FLOOR CONTRACT
                # ----------------------------------

                if connects:

                    if floor not in connects:

                        continue

                # ----------------------------------
                # SITE RULE
                #
                # SITE only receives systems that
                # explicitly connect to SITE.
                # ----------------------------------

                if (
                    floor == "SITE"
                    and "SITE" not in connects
                ):

                    continue

                data["elements"].append(

                    {

                        **element,

                        "assigned_floor":
                            floor

                    }

                )





        # ==================================
        # DESIGN LOGIC
        # ==================================


        result["design_logic"] = [


            "public_spaces_near_entrance",


            "vertical_core_centralized",


            "private_spaces_separated",


            "service_spaces_support_public_zone",


            "external_spaces_separated_from_building_levels",


            "vertical_systems_follow_architectural_logic"

        ]



        return result






    # ==================================
    # VERTICAL CATEGORY
    # ==================================


    def get_element_category(

        self,

        element_type

    ):


        mapping = {


            "elevator":

                "vertical_transport",



            "stairs":

                "vertical_escape",



            "escalator":

                "public_vertical_flow",



            "moving_ramp":

                "public_vertical_flow",



            "vehicle_ramp":

                "vehicle_access",



            "car_lift":

                "vehicle_access",



            "vehicle_access_pending":

                "vehicle_access_decision",



            "accessible_ramp":

                "accessibility"

        }



        return mapping.get(

            element_type,

            "architectural_element"

        )






    # ==================================
    # PLACEMENT INTENT
    # ==================================


    def get_placement_intent(

        self,

        element_type

    ):


        mapping = {


            "elevator":

                "central_core",



            "stairs":

                "protected_core",



            "escalator":

                "public_axis",



            "moving_ramp":

                "public_flow_path",



            "vehicle_ramp":

                "parking_access",



            "car_lift":

                "parking_core",



            "vehicle_access_pending":

                "site_aware_decision_pending",



            "accessible_ramp":

                "accessible_route"

        }



        return mapping.get(

            element_type,

            "adaptive_location"

        )






    def get_floor_height(
        self,
        floor,
        context=None
    ):

        context = (
            context
            if isinstance(
                context,
                dict
            )
            else {}
        )

        floor_heights = context.get(
            "floor_heights",
            {}
        )

        if isinstance(
            floor_heights,
            dict
        ):

            height = floor_heights.get(
                floor
            )

            try:

                height = float(
                    height
                )

            except (
                TypeError,
                ValueError
            ):

                height = None

            if (
                height is not None
                and
                height > 0
            ):

                return height

        floor_configuration = context.get(
            "floor_configuration",
            {}
        )

        if isinstance(
            floor_configuration,
            dict
        ):

            configuration_heights = (
                floor_configuration.get(
                    "floor_heights",
                    {}
                )
            )

            if isinstance(
                configuration_heights,
                dict
            ):

                height = (
                    configuration_heights.get(
                        floor
                    )
                )

                try:

                    height = float(
                        height
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    height = None

                if (
                    height is not None
                    and
                    height > 0
                ):

                    return height

        # No architectural height evidence.
        #
        # Do NOT invent a default storey height here.
        return None
