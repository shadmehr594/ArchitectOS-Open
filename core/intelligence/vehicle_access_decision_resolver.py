"""
ArchitectOS Vehicle Access Decision Resolver v1.0

Resolves vehicle access after feasibility analysis.

Important:
- Does not invent missing technical criteria.
- Does not generate geometry.
- Does not select a candidate unless evidence supports it.
"""


class VehicleAccessDecisionResolver:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"🚘 Vehicle Access Decision Resolver v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # MAIN
    # ==================================================

    def resolve(
        self,
        feasibility_result,
        building_context=None
    ):

        feasibility_result = (
            feasibility_result
            or
            {}
        )

        building_context = (
            building_context
            or
            {}
        )


        ramp = feasibility_result.get(
            "ramp",
            {}
        )


        car_lift = feasibility_result.get(
            "car_lift",
            {}
        )


        ramp_status = ramp.get(
            "status"
        )


        car_lift_status = car_lift.get(
            "status"
        )


        feasible_candidates = []


        if ramp_status == "feasible":

            feasible_candidates.append(
                "vehicle_ramp"
            )


        if car_lift_status == "feasible":

            feasible_candidates.append(
                "car_lift"
            )


        # ==================================================
        # RESULT BASE
        # ==================================================

        result = {

            "engine":
                "VEHICLE_ACCESS_DECISION_RESOLVER",

            "version":
                self.VERSION,

            "status":
                "unresolved",

            "selected_system":
                None,

            "selection_reason":
                None,

            "feasible_candidates":
                feasible_candidates,

            "comparative_analysis":
                {},

            "geometry_generation_allowed":
                False,

            "program_space_generation_allowed":
                False,

            "source_feasibility":
                feasibility_result,

            "selected_access_candidate":
                None,

            "feasible_access_candidates":
                ramp.get("feasible_access_candidates", [])

        }

        feasible_access_candidates = result["feasible_access_candidates"]

        # A feasible ramp system is not yet a selected site entrance. Keep
        # multiple verified access edges available for comparison instead of
        # selecting the first candidate by list order.
        if (
            ramp_status == "feasible"
            and feasible_candidates == ["vehicle_ramp"]
            and isinstance(feasible_access_candidates, list)
            and len(feasible_access_candidates) > 1
        ):

            result["status"] = "access_candidate_selection_pending"
            result["selection_reason"] = (
                "multiple_feasible_site_access_candidates_require_comparison"
            )
            return result


        # ==================================================
        # NO FEASIBLE CANDIDATE
        # ==================================================

        if not feasible_candidates:

            result["selection_reason"] = (
                "no_vehicle_access_candidate_has_verified_feasibility"
            )

            return result


        # ==================================================
        # SINGLE FEASIBLE CANDIDATE
        # ==================================================

        if len(feasible_candidates) == 1:

            selected = feasible_candidates[0]


            result["status"] = (
                "resolved"
            )


            result["selected_system"] = (
                selected
            )


            result["selection_reason"] = (
                "only_verified_feasible_candidate"
            )


            result[
                "program_space_generation_allowed"
            ] = True

            if (
                selected == "vehicle_ramp"
                and isinstance(feasible_access_candidates, list)
                and len(feasible_access_candidates) == 1
            ):

                result["selected_access_candidate"] = (
                    feasible_access_candidates[0]
                )


            return result


        # ==================================================
        # MULTIPLE FEASIBLE CANDIDATES
        #
        # A comparative decision now requires
        # additional architectural / operational evidence.
        # ==================================================

        site_evidence = feasibility_result.get(
            "site_evidence",
            {}
        )


        preferences = building_context.get(
            "vehicle_access_preferences",
            {}
        )


        prioritize_continuous_flow = preferences.get(
            "prioritize_continuous_vehicle_flow"
        )


        prioritize_compact_footprint = preferences.get(
            "prioritize_compact_footprint"
        )


        avoid_mechanical_dependency = preferences.get(
            "avoid_mechanical_dependency"
        )


        minimize_horizontal_land_use = preferences.get(
            "minimize_horizontal_land_use"
        )


        ramp_score = 0

        car_lift_score = 0


        evidence_used = []


        # ==================================================
        # CONTINUOUS VEHICLE FLOW
        # ==================================================

        if prioritize_continuous_flow is True:

            ramp_score += 2

            evidence_used.append(
                "prioritize_continuous_vehicle_flow"
            )


        # ==================================================
        # COMPACT FOOTPRINT
        # ==================================================

        if prioritize_compact_footprint is True:

            car_lift_score += 2

            evidence_used.append(
                "prioritize_compact_footprint"
            )


        # ==================================================
        # MECHANICAL DEPENDENCY
        # ==================================================

        if avoid_mechanical_dependency is True:

            ramp_score += 2

            evidence_used.append(
                "avoid_mechanical_dependency"
            )


        # ==================================================
        # HORIZONTAL SITE CONSUMPTION
        # ==================================================

        if minimize_horizontal_land_use is True:

            car_lift_score += 2

            evidence_used.append(
                "minimize_horizontal_land_use"
            )


        # ==================================================
        # PHYSICAL FIT QUALITY
        # ==================================================

        required_run = ramp.get(
            "required_run"
        )


        site_depth = ramp.get(
            "site_depth"
        )


        ramp_depth_ratio = None


        if (
            required_run is not None
            and
            site_depth
        ):

            ramp_depth_ratio = (
                float(required_run)
                /
                float(site_depth)
            )


        if (
            ramp_depth_ratio is not None
            and
            ramp_depth_ratio <= 0.75
        ):

            ramp_score += 1

            evidence_used.append(
                "ramp_has_site_depth_margin"
            )


        car_lift_width = car_lift.get(
            "required_width"
        )


        car_lift_depth = car_lift.get(
            "required_depth"
        )


        site_width = car_lift.get(
            "site_width"
        )


        car_lift_site_depth = car_lift.get(
            "site_depth"
        )


        car_lift_width_ratio = None

        car_lift_depth_ratio = None


        if (
            car_lift_width is not None
            and
            site_width
        ):

            car_lift_width_ratio = (
                float(car_lift_width)
                /
                float(site_width)
            )


        if (
            car_lift_depth is not None
            and
            car_lift_site_depth
        ):

            car_lift_depth_ratio = (
                float(car_lift_depth)
                /
                float(car_lift_site_depth)
            )


        if (
            car_lift_width_ratio is not None
            and
            car_lift_depth_ratio is not None
            and
            car_lift_width_ratio <= 0.50
            and
            car_lift_depth_ratio <= 0.50
        ):

            car_lift_score += 1

            evidence_used.append(
                "car_lift_has_site_dimension_margin"
            )


        # ==================================================
        # COMPARATIVE RESULT
        # ==================================================

        result["comparative_analysis"] = {

            "vehicle_ramp":
            {

                "score":
                    ramp_score,

                "required_run":
                    required_run,

                "site_depth":
                    site_depth,

                "depth_ratio":
                    ramp_depth_ratio

            },

            "car_lift":
            {

                "score":
                    car_lift_score,

                "required_width":
                    car_lift_width,

                "required_depth":
                    car_lift_depth,

                "site_width":
                    site_width,

                "site_depth":
                    car_lift_site_depth,

                "width_ratio":
                    car_lift_width_ratio,

                "depth_ratio":
                    car_lift_depth_ratio

            },

            "evidence_used":
                evidence_used,

            "site_evidence":
                site_evidence

        }


        # ==================================================
        # DO NOT GUESS ON A TIE
        # ==================================================

        if ramp_score == car_lift_score:

            result["status"] = (
                "comparative_decision_pending"
            )


            result["selection_reason"] = (
                "multiple_feasible_candidates_without_decisive_evidence"
            )


            return result


        # ==================================================
        # SELECT
        # ==================================================

        if ramp_score > car_lift_score:

            selected = (
                "vehicle_ramp"
            )

        else:

            selected = (
                "car_lift"
            )

        if (
            selected == "vehicle_ramp"
            and isinstance(feasible_access_candidates, list)
            and len(feasible_access_candidates) > 1
        ):

            result["status"] = "access_candidate_selection_pending"
            result["selected_system"] = "vehicle_ramp"
            result["selection_reason"] = (
                "vehicle_ramp_selected_but_site_access_candidate_requires_comparison"
            )
            return result


        result["status"] = (
            "resolved"
        )


        result["selected_system"] = (
            selected
        )


        result["selection_reason"] = (
            "comparative_architectural_evidence"
        )


        result[
            "program_space_generation_allowed"
        ] = True


        return result
