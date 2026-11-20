from core.architecture.model.architectural_plan_model import ArchitecturalPlanModel

# =============================================================================
# NOT THE PRIMARY ARCHITECTOS PLAN GENERATOR.
# HouseDiffusion is the locked primary plan generator under
# HOUSE_DIFFUSION_GENERATION_POLICY_V1.
# Do not extend this branch as the normal product design path.
#
# Entrypoint: PlanModelReasoner.generate  (internal plan synthesis branch)
# Enforced by core/architecture/routing/generation_policy_guard_v1.py
# =============================================================================
ARCHITECTOS_GENERATION_ROLE = "DIAGNOSTIC_OR_EXPLICIT_FALLBACK"
PRODUCTION_PRIMARY = False


class PlanModelReasoner:


    VERSION = "1.2"



    def __init__(self):

        print(
            "📋 PLAN MODEL REASONER v1.2 ONLINE"
        )



    def generate(
        self,
        layout,
        site_analysis
    ):


        model = ArchitecturalPlanModel()



        model.zones = layout.get(
            "zones",
            {}
        )



        model.floor_distribution = layout.get(
            "floor_distribution",
            {}
        )



        # ==========================
        # SPACES
        # ==========================

        space_registry = layout.get(
            "space_registry",
            []
        )



        for space in space_registry:


            if not isinstance(
                space,
                dict
            ):

                continue



            zone = space.get(
                "zone"
            )



            model_space = {


                "name":
                    space.get(
                        "name"
                    ),

                "canonical_name":
                    space.get(
                        "canonical_name",
                        space.get(
                            "name"
                        )
                    ),


                "zone":
                    zone,


                "planning_zone":
                    space.get(
                        "planning_zone"
                    ),


                "space_type":
                    space.get(
                        "space_type"
                    ),


                "access":
                    list(
                        space.get(
                            "access",
                            []
                        )
                    ),


                "adjacent_to":
                    list(
                        space.get(
                            "adjacent_to",
                            []
                        )
                    ),


                "floor":
                    space.get(
                        "floor"
                    ),


                "dimensional_requirements":
                    dict(
                        space.get(
                            "dimensional_requirements",
                            {}
                        )
                    ),

                "resolved_dimensions":
                    dict(
                        space.get(
                            "resolved_dimensions",
                            {}
                        )
                        or {}
                    ),


                "circulation_profile":
                    space.get(
                        "circulation_profile"
                    ),


                "protected_zone":
                    bool(
                        space.get(
                            "protected_zone",
                            False
                        )
                    ),


                "role":
                    self.get_role(
                        zone
                    )

            }



            model.add_space(
                model_space
            )



            model.space_registry.append(
                model_space
            )

        # ==========================
        # PROGRAM AREA BASIS
        # ==========================
        #
        # Architectural program-area evidence derived
        # from resolved space-program dimensions.
        #
        # IMPORTANT:
        # - This is NOT gross floor area.
        # - External/site spaces are tracked separately.
        # - Spaces without resolved_area remain explicit.
        # - No area value is invented.
        # ==========================

        per_floor = {}

        resolved_internal_program_area = 0.0
        resolved_external_program_area = 0.0

        unresolved_area_spaces = []

        for model_space in model.space_registry:

            if not isinstance(
                model_space,
                dict
            ):
                continue

            name = model_space.get(
                "name"
            )

            floor = model_space.get(
                "floor"
            )

            zone = model_space.get(
                "zone"
            )

            dimensional_requirements = (
                model_space.get(
                    "dimensional_requirements",
                    {}
                )
            )

            if not isinstance(
                dimensional_requirements,
                dict
            ):
                dimensional_requirements = {}

            resolved_area = (
                dimensional_requirements.get(
                    "resolved_area"
                )
            )

            floor_key = (
                floor
                if floor is not None
                else "site"
            )

            if floor_key not in per_floor:

                per_floor[floor_key] = {
                    "resolved_internal_area": 0.0,
                    "resolved_external_area": 0.0,
                    "unresolved_area_spaces": []
                }

            if resolved_area is None:

                unresolved_record = {
                    "name": name,
                    "floor": floor,
                    "zone": zone
                }

                per_floor[
                    floor_key
                ][
                    "unresolved_area_spaces"
                ].append(
                    unresolved_record
                )

                unresolved_area_spaces.append(
                    unresolved_record
                )

                continue

            try:

                resolved_area = float(
                    resolved_area
                )

            except (
                TypeError,
                ValueError
            ):

                unresolved_record = {
                    "name": name,
                    "floor": floor,
                    "zone": zone
                }

                per_floor[
                    floor_key
                ][
                    "unresolved_area_spaces"
                ].append(
                    unresolved_record
                )

                unresolved_area_spaces.append(
                    unresolved_record
                )

                continue

            if zone == "external":

                per_floor[
                    floor_key
                ][
                    "resolved_external_area"
                ] += resolved_area

                resolved_external_program_area += (
                    resolved_area
                )

            else:

                per_floor[
                    floor_key
                ][
                    "resolved_internal_area"
                ] += resolved_area

                resolved_internal_program_area += (
                    resolved_area
                )

        model.program_area_basis = {
            "source":
                "resolved_space_program",

            "per_floor":
                per_floor,

            "resolved_internal_program_area":
                resolved_internal_program_area,

            "resolved_external_program_area":
                resolved_external_program_area,

            "unresolved_area_spaces":
                unresolved_area_spaces,

            "evidence_status":
                (
                    "complete"
                    if not unresolved_area_spaces
                    else "partial"
                )
        }



        # ==========================
        # RELATIONSHIPS
        # ==========================

        for connection in layout.get(
            "connections",
            []
        ):


            model.add_relationship(
                connection
            )



        # ==========================
        # PLANNING LOGIC
        # ==========================

        for item in layout.get(
            "layout_strategy",
            []
        ):


            model.add_logic(
                item
            )



        # ==========================
        # SITE RESPONSE
        # ==========================

        model.site_response = {


            "based_on_site_analysis":

                bool(
                    site_analysis
                )

        }



        return model



    # ==================================
    # SPACE ROLE
    # ==================================

    def get_role(
        self,
        zone
    ):


        roles = {


            "public":

                "social_and_shared_space",


            "private":

                "privacy_and_rest",


            "external":

                "outdoor_relationship",


            "service":

                "supporting_functions",


            "circulation":

                "movement_and_connection"

        }



        return roles.get(

            zone,

            "architectural_space"

        )