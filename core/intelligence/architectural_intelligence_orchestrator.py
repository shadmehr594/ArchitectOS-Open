"""
ArchitectOS Architectural Intelligence Orchestrator v1.1

Coordinates architectural reasoning agents
and integrates reasoning into floor programs.
"""


from core.intelligence.architectural_reasoning_engine import (
    ArchitecturalReasoningEngine
)

from core.intelligence.reasoning_program_bridge import (
    ReasoningProgramBridge
)

from core.intelligence.floor_program_reasoning_adapter import (
    FloorProgramReasoningAdapter
)

from core.intelligence.vertical_circulation_reasoning import (
    VerticalCirculationReasoning
)

from core.intelligence.vertical_program_integration_engine import (
    VerticalProgramIntegrationEngine
)

from core.building.floor_program_engine import (
    FloorProgramEngine
)

from core.architecture.architectural_layout_reasoner import (
    ArchitecturalLayoutReasoner
)

from core.intelligence.vehicle_access_feasibility_reasoner import (
    VehicleAccessFeasibilityReasoner
)

from core.intelligence.vehicle_access_decision_resolver import (
    VehicleAccessDecisionResolver
)
from core.intelligence.vehicle_access_candidate_selector import (
    VehicleAccessCandidateSelector
)
from core.architecture.geometry.vehicle_access_geometry_resolver_v1 import (
    VehicleAccessGeometryResolverV1
)
from core.architecture.reasoning.site_access_coordination_reasoner_v1 import (
    SiteAccessCoordinationReasonerV1
)
from core.architecture.reasoning.vehicle_site_access_candidate_geometry_design_reasoner_v1 import (
    VehicleSiteAccessCandidateGeometryDesignReasonerV1
)
from core.architecture.geometry.pedestrian_access_geometry_resolver_v1 import (
    PedestrianAccessGeometryResolverV1
)
from core.architecture.geometry.main_entrance_opening_placement_selector_v1 import (
    MainEntranceOpeningPlacementSelectorV1
)

from core.intelligence.vertical_core_sizing_reasoner import (
    VerticalCoreSizingReasoner
)

from core.intelligence.vertical_core_sizing_profile_selector import (
    VerticalCoreSizingProfileSelector
)

from core.intelligence.vertical_core_sizing_rules import (
    VerticalCoreSizingRules
)

from core.intelligence.vertical_core_rule_evaluator import (
    VerticalCoreRuleEvaluator
)

from core.intelligence.vertical_core_rule_value_provider import (
    VerticalCoreRuleValueProvider
)

from core.intelligence.vertical_core_sizing_applicator import (
    VerticalCoreSizingApplicator
)

class ArchitecturalIntelligenceOrchestrator:


    VERSION = "1.1"



    def __init__(self):

        print(
            f"dYÿ Architectural Intelligence Orchestrator v{self.VERSION} ACTIVE"
        )


        self.reasoning = ArchitecturalReasoningEngine()

        self.program_bridge = ReasoningProgramBridge()

        self.program_adapter = FloorProgramReasoningAdapter()

        self.floor_program_engine = FloorProgramEngine()

        self.vertical_reasoning = VerticalCirculationReasoning()

        self.vertical_core_sizing = (
            VerticalCoreSizingReasoner()
        )

        self.vertical_core_profile_selector = (
            VerticalCoreSizingProfileSelector()
        )

        self.vertical_core_rules = (
            VerticalCoreSizingRules()
        )

        self.vertical_core_rule_evaluator = (
            VerticalCoreRuleEvaluator()
        )

        self.vertical_core_rule_value_provider = (
            VerticalCoreRuleValueProvider()
        )

        self.vertical_core_sizing_applicator = (
            VerticalCoreSizingApplicator()
        )

        self.vehicle_access_feasibility = (
            VehicleAccessFeasibilityReasoner()
        )

        self.vehicle_access_resolver = (
            VehicleAccessDecisionResolver()
        )

        self.vehicle_access_candidate_selector = (
            VehicleAccessCandidateSelector()
        )

        self.vehicle_access_geometry_resolver = (
            VehicleAccessGeometryResolverV1()
        )

        self.site_access_coordination_reasoner = (
            SiteAccessCoordinationReasonerV1()
        )
        self.vehicle_site_access_geometry_design_reasoner = (
            VehicleSiteAccessCandidateGeometryDesignReasonerV1()
        )

        self.vertical_integration = (
            VerticalProgramIntegrationEngine()
        )

        self.layout_reasoning = ArchitecturalLayoutReasoner()



    # ==================================================
    # ANALYZE BUILDING
    # ==================================================

    def analyze(
        self,
        building_intent
    ):


        # -------------------------------
        # Architectural Reasoning
        # -------------------------------

        decisions = self.reasoning.analyze(

            building_intent

        )


        # -------------------------------
        # Program Translation
        # -------------------------------

        program_requirements = self.program_bridge.translate(

            decisions

        )


        # -------------------------------
        # Floor Program Generation
        # -------------------------------

        floor_programs = []


        for floor in building_intent.get(
            "floors",
            []
        ):


            floor_program = self.floor_program_engine.generate(

                floor

            )


            # -------------------------------
            # Apply Reasoning To Floor
            # -------------------------------

            reasoning_floor = self.program_adapter.adapt(

                floor_program,

                program_requirements

            )


            floor_program = self.floor_program_engine.apply_reasoning(

                floor_program,

                reasoning_floor

            )


            floor_programs.append(

                floor_program

            )



        # -------------------------------
        # Vertical Reasoning
        # -------------------------------

        vertical_result = self.vertical_reasoning.analyze(

            building_intent

        )


        # -------------------------------
        # Vehicle Access Resolution
        # -------------------------------

        vehicle_access_feasibility = None
        vehicle_access_decision = None
        vehicle_access_system_decision = None
        vehicle_access_candidate_selection = None
        vehicle_access_geometry = None
        site_access_coordination = None
        vehicle_site_access_geometry_design = None


        vertical_systems = vertical_result.get(
            "vertical_systems",
            []
        )


        pending_vehicle_access = next(

            (
                system

                for system in vertical_systems

                if system.get("type")
                ==
                "vehicle_access_pending"
            ),

            None

        )


        if pending_vehicle_access:


            vehicle_access_feasibility = (
                self.vehicle_access_feasibility.evaluate(

                    pending_vehicle_access,

                    building_intent

                )
            )


            vehicle_access_system_decision = (
                self.vehicle_access_resolver.resolve(

                    vehicle_access_feasibility,

                    building_intent

                )
            )

            authoritative_geometry = building_intent.get("architectural_geometry")
            site_geometry = (
                authoritative_geometry.get("site_geometry", {})
                if isinstance(authoritative_geometry, dict)
                else {}
            )
            pedestrian_design = (
                site_geometry.get("pedestrian_access_design")
                if isinstance(site_geometry, dict)
                else None
            )
            if isinstance(pedestrian_design, dict):
                coordination_requirements = dict(
                    site_geometry.get("site_access_coordination_requirements", {})
                    if isinstance(site_geometry.get("site_access_coordination_requirements"), dict)
                    else {}
                )
                coordination_requirements.setdefault("vehicle_access_required", True)
                coordination_requirements.setdefault(
                    "pedestrian_access_required",
                    building_intent.get("pedestrian_access_required", True),
                )
                coordination_requirements.setdefault(
                    "minimum_clear_separation",
                    building_intent.get("minimum_pedestrian_vehicle_separation"),
                )
                coordination_requirements.setdefault(
                    "crossing_policy", building_intent.get("pedestrian_vehicle_crossing_policy")
                )
                coordination_requirements.setdefault(
                    "protected_zones", site_geometry.get("protected_zones", [])
                )
                coordination_requirements.setdefault(
                    "parking_circulation_zones",
                    site_geometry.get("parking_circulation_zones", []),
                )
                vehicle_site_access_geometry_design = (
                    self.vehicle_site_access_geometry_design_reasoner.design(
                        {
                            **site_geometry,
                            "building_footprints": [
                                floor.get("footprint", {}).get("points")
                                for floor in authoritative_geometry.get("floor_geometry", [])
                                if isinstance(floor, dict)
                                and isinstance(floor.get("footprint"), dict)
                                and isinstance(floor.get("footprint", {}).get("points"), list)
                            ],
                        },
                        vehicle_access_feasibility,
                        vehicle_access_system_decision,
                    )
                )
                site_geometry["vehicle_site_access_geometry_design"] = (
                    vehicle_site_access_geometry_design
                )
                vehicle_coordination_contract = {
                    "selected_system": vehicle_access_system_decision.get("selected_system"),
                    "ramp": {
                        "access_candidates": vehicle_site_access_geometry_design.get(
                            "access_candidates", []
                        )
                    },
                }
                site_access_coordination = self.site_access_coordination_reasoner.coordinate(
                    pedestrian_design,
                    vehicle_coordination_contract,
                    coordination_requirements,
                )
                site_geometry["site_access_coordination"] = site_access_coordination
                if site_access_coordination.get("selection_status") != "resolved":
                    site_geometry.pop("pedestrian_access", None)
                    site_geometry["pedestrian_access_resolution"] = {
                        "type": "pedestrian_access",
                        "access_id": None,
                        "approach_line": None,
                        "geometry_status": "pending",
                        "resolution_reason": "site_access_coordination_not_resolved",
                        "source": self.__class__.__name__,
                    }
                    for opening in authoritative_geometry.get("openings", []):
                        if (
                            isinstance(opening, dict)
                            and opening.get("category") == "main_entrance"
                            and len(opening.get("candidate_wall_ids", [])) > 1
                        ):
                            opening.update({
                                "host_wall_id": None,
                                "host_boundary_id": None,
                                "center": None,
                                "host_resolution_status": "host_pending_multiple_candidates",
                                "host_resolution_reason": "multiple_compatible_walls_require_architectural_evidence",
                                "placement_resolution_status": "pending",
                                "placement_resolution_reason": "site_access_coordination_not_resolved",
                            })

            vehicle_access_candidate_selection = (
                self.vehicle_access_candidate_selector.select(
                    {
                        **vehicle_access_feasibility,
                        "ramp": {
                            **vehicle_access_feasibility.get("ramp", {}),
                            "access_candidates": vehicle_site_access_geometry_design.get(
                                "access_candidates", []
                            ),
                        },
                    }
                    if isinstance(vehicle_site_access_geometry_design, dict)
                    else vehicle_access_feasibility,
                    vehicle_access_system_decision,
                    dict(building_intent, site_access_coordination=site_access_coordination)
                    if isinstance(site_access_coordination, dict)
                    else building_intent
                )
            )

            vehicle_access_decision = vehicle_access_candidate_selection


            if (
                vehicle_access_decision.get("status")
                ==
                "resolved"
                and
                vehicle_access_decision.get(
                    "program_space_generation_allowed",
                    False
                )
            ):


                selected_system = (
                    vehicle_access_decision.get(
                        "selected_system"
                    )
                )


                source_vehicle_access = (
                    vehicle_access_feasibility.get(
                        "source_vehicle_access",
                        {}
                    )
                )

                # ==================================================
                # BUILD RESOLVED VEHICLE ACCESS PARAMETERS
                # ==================================================

                selected_feasibility = (
                    vehicle_access_feasibility.get(
                        "ramp",
                        {}
                    )
                    if selected_system == "vehicle_ramp"
                    else
                    vehicle_access_feasibility.get(
                        "car_lift",
                        {}
                    )
                )


                if selected_system == "vehicle_ramp":

                    resolved_parameters = {

                        "ramp_type":
                            "vehicle_access_ramp",

                        "required_run":
                            selected_feasibility.get(
                                "required_run"
                            ),

                        "clear_width":
                            selected_feasibility.get(
                                "minimum_width"
                            ),

                        "turning_radius":
                            selected_feasibility.get(
                                "turning_radius"
                            ),

                        "site_depth":
                            selected_feasibility.get(
                                "site_depth"
                            ),

                        "site_fit":
                            selected_feasibility.get(
                                "site_fit"
                            ),

                        "feasibility_status":
                            selected_feasibility.get(
                                "status"
                            ),

                        "site_fit_required":
                            True,

                        "transition_zone_required":
                            True,

                        "vehicle_only":
                            True

                    }


                elif selected_system == "car_lift":

                    resolved_parameters = {

                        "car_lift_type":
                            "vehicle_platform_lift",

                        "required_width":
                            selected_feasibility.get(
                                "required_width"
                            ),

                        "required_depth":
                            selected_feasibility.get(
                                "required_depth"
                            ),

                        "queue_length":
                            selected_feasibility.get(
                                "queue_length"
                            ),

                        "site_width":
                            selected_feasibility.get(
                                "site_width"
                            ),

                        "site_depth":
                            selected_feasibility.get(
                                "site_depth"
                            ),

                        "site_fit":
                            selected_feasibility.get(
                                "site_fit"
                            ),

                        "feasibility_status":
                            selected_feasibility.get(
                                "status"
                            ),

                        "service_floors":
                            source_vehicle_access.get(
                                "connects",
                                []
                            ),

                        "queue_space_required":
                            True,

                        "maneuvering_space_required":
                            True,

                        "site_fit_required":
                            True

                    }


                else:

                    resolved_parameters = {}

                selected_access = vehicle_access_decision.get(
                    "selected_access_candidate"
                ) or {}


                resolved_system = {

                    "type":
                        selected_system,

                    "reason":
                        "resolved_by_vehicle_access_feasibility",

                    "role":
                        (
                            "parking_vehicle_access"
                            if selected_system
                            ==
                            "vehicle_ramp"
                            else
                            "parking_vertical_vehicle_transport"
                        ),

                    "connects":
                        source_vehicle_access.get(
                            "connects",
                            []
                        ),

                    "parameters":
                        resolved_parameters,

                    "protected_zone":
                        True,

                    "resolution":
                    {

                        "status":
                            vehicle_access_decision.get(
                                "status"
                            ),

                        "selection_reason":
                            vehicle_access_decision.get(
                                "selection_reason"
                            ),

                        "geometry_generation_allowed":
                            vehicle_access_decision.get(
                                "geometry_generation_allowed",
                                False
                            )

                        ,"ramp_geometry_allowed":
                            vehicle_access_decision.get(
                                "ramp_geometry_allowed",
                                False
                            )

                        ,"driveway_geometry_allowed":
                            vehicle_access_decision.get(
                                "driveway_geometry_allowed",
                                False
                            )

                    }

                }


                if selected_system == "vehicle_ramp":

                    ramp_result = (
                        vehicle_access_feasibility.get(
                            "ramp",
                            {}
                        )
                    )


                    resolved_system["parameters"] = {

                        "ramp_type":
                            "vehicle_access_ramp",

                        "required_run":
                            ramp_result.get(
                                "required_run"
                            ),

                        "clear_width":
                            ramp_result.get(
                                "minimum_width"
                            ),

                        "turning_radius":
                            ramp_result.get(
                                "turning_radius"
                            ),

                        "site_fit":
                            ramp_result.get(
                                "site_fit"
                            ),

                        "site_fit_required":
                            True,

                        "geometry_generation_allowed":
                            False

                    }


                elif selected_system == "car_lift":

                    car_lift_result = (
                        vehicle_access_feasibility.get(
                            "car_lift",
                            {}
                        )
                    )


                    resolved_system["parameters"] = {

                        "car_lift_type":
                            "vehicle_platform_lift",

                        "platform_width":
                            car_lift_result.get(
                                "required_width"
                            ),

                        "platform_length":
                            car_lift_result.get(
                                "required_depth"
                            ),

                        "queue_length":
                            car_lift_result.get(
                                "queue_length"
                            ),

                        "site_fit":
                            car_lift_result.get(
                                "site_fit"
                            ),

                        "site_fit_required":
                            True,

                        "geometry_generation_allowed":
                            False

                    }


                if selected_system == "vehicle_ramp":

                    resolved_system["parameters"].update(
                        {
                            "selected_access_candidate": selected_access,
                            "selected_access_id": selected_access.get("access_id"),
                            "access_mode": selected_access.get("access_mode"),
                            "access_elevation": selected_access.get("access_elevation"),
                            "target_elevation": selected_access.get("target_elevation"),
                            "delta_z": selected_access.get("delta_z"),
                            "absolute_level_difference": selected_access.get(
                                "absolute_level_difference"
                            ),
                            "required_run": selected_access.get("required_run"),
                            "ramp_geometry_required": selected_access.get(
                                "ramp_geometry_required",
                                False
                            ),
                            "geometry_generation_allowed": vehicle_access_decision.get(
                                "geometry_generation_allowed",
                                False
                            ),
                            "ramp_geometry_allowed": vehicle_access_decision.get(
                                "ramp_geometry_allowed",
                                False
                            ),
                            "driveway_geometry_allowed": vehicle_access_decision.get(
                                "driveway_geometry_allowed",
                                False
                            ),
                            "selection_evidence": vehicle_access_decision.get(
                                "evidence_used",
                                []
                            ),
                        }
                    )


                vertical_systems = [

                    system

                    for system in vertical_systems

                    if system.get("type")
                    !=
                    "vehicle_access_pending"

                ]


                vertical_systems.append(
                    resolved_system
                )


                vertical_result[
                    "vertical_systems"
                ] = vertical_systems

            authoritative_geometry = building_intent.get("architectural_geometry")

            # Publish only the coordinated pedestrian candidate, validate it
            # with the existing resolver, then let the unchanged entrance
            # selector consume the coordinated approach.
            if (
                isinstance(authoritative_geometry, dict)
                and isinstance(site_access_coordination, dict)
                and site_access_coordination.get("selection_status") == "resolved"
            ):
                selected_pair = site_access_coordination.get("selected_pair", {}) or {}
                pedestrian_id = selected_pair.get("pedestrian_candidate_id")
                normalized = next((
                    item for item in site_access_coordination.get("pedestrian_candidates", [])
                    if isinstance(item, dict) and item.get("candidate_id") == pedestrian_id
                ), None)
                source_candidate = normalized.get("source_candidate") if isinstance(normalized, dict) else None
                site_geometry = authoritative_geometry.get("site_geometry", {})
                if isinstance(site_geometry, dict) and isinstance(source_candidate, dict):
                    publish_candidate = dict(source_candidate)
                    publish_candidate["access_id"] = publish_candidate.get("candidate_id")
                    publish_candidate["parcel_edge_reference"] = publish_candidate.get("access_edge_reference")
                    publish_candidate["source_evidence"] = list(publish_candidate.get("evidence_used", []))
                    publish_candidate["geometry_status"] = "candidate"
                    site_geometry["pedestrian_access_candidates"] = [publish_candidate]
                    pedestrian_access = PedestrianAccessGeometryResolverV1().resolve(
                        site_geometry, authoritative_geometry.get("floor_geometry", [])
                    )
                    site_geometry["pedestrian_access_resolution"] = pedestrian_access
                    if pedestrian_access.get("geometry_status") == "resolved":
                        site_geometry["pedestrian_access"] = pedestrian_access
                        openings = []
                        for source_opening in authoritative_geometry.get("openings", []):
                            opening = dict(source_opening)
                            if (
                                opening.get("category") == "main_entrance"
                                and len(opening.get("candidate_wall_ids", [])) > 1
                                and opening.get("placement_access_id") != pedestrian_id
                            ):
                                opening.update({
                                    "host_wall_id": None,
                                    "host_boundary_id": None,
                                    "center": None,
                                    "host_resolution_status": "host_pending_multiple_candidates",
                                    "host_resolution_reason": "multiple_compatible_walls_require_architectural_evidence",
                                })
                            openings.append(opening)
                        authoritative_geometry["openings"] = MainEntranceOpeningPlacementSelectorV1().resolve(
                            openings,
                            authoritative_geometry.get("physical_walls", []),
                            authoritative_geometry.get("spaces", []),
                            authoritative_geometry.get("floor_geometry", []),
                            site_geometry,
                        )

            if (
                isinstance(authoritative_geometry, dict)
                and vehicle_access_candidate_selection.get("status") == "resolved"
                and vehicle_access_candidate_selection.get(
                    "selected_system"
                ) == "vehicle_ramp"
            ):

                ramp_contract = vehicle_access_feasibility.get("ramp", {})
                vehicle_access_geometry = self.vehicle_access_geometry_resolver.resolve(
                    vehicle_access_candidate_selection,
                    authoritative_geometry,
                    {
                        "clear_width": ramp_contract.get("minimum_width"),
                        "slope": ramp_contract.get("normalized_slope_ratio"),
                    }
                )


        vertical_systems = vertical_result.get(

            "vertical_systems",

            []

        )

        # -------------------------------
        # Vertical Core Sizing
        # -------------------------------

        vertical_core_sizing = (
            self.vertical_core_sizing.evaluate(
                vertical_result,
                building_intent
            )
        )


        vertical_core_profile = (
            self.vertical_core_profile_selector.select(
                vertical_core_sizing,
                building_intent
            )
        )


        vertical_core_rule_evaluation = (
            self.vertical_core_rule_evaluator.evaluate(
                vertical_core_profile,
                self.vertical_core_rules,
                building_intent
            )
        )


        vertical_core_rule_values = (
            self.vertical_core_rule_value_provider.resolve(
                vertical_core_rule_evaluation,
                building_intent
            )
        )


        vertical_core_applied = (
            self.vertical_core_sizing_applicator.apply(
                vertical_core_rule_values
            )
        )


        sized_systems = (
            vertical_core_applied.get(
                "vertical_systems",
                []
            )
        )


        if sized_systems:

            sized_by_type = {

                system.get("type"):
                    system

                for system in sized_systems

                if system.get("type")
            }


            merged_systems = []


            for system in vertical_result.get(
                "vertical_systems",
                []
            ):

                system_type = system.get(
                    "type"
                )


                if system_type in sized_by_type:

                    merged_systems.append(
                        sized_by_type[
                            system_type
                        ]
                    )

                else:

                    merged_systems.append(
                        system
                    )


            vertical_result[
                "vertical_systems"
            ] = merged_systems



            vertical_systems = (
                vertical_result.get(
                    "vertical_systems",
                    []
                )
            )


        # -------------------------------
        # Vertical Program Integration
        # -------------------------------

        for index, floor_program in enumerate(

            floor_programs

        ):


            floor_programs[index] = (

                self.vertical_integration.apply(

                    floor_program,

                    vertical_result

                )

            )



        # -------------------------------
        # Layout Reasoning
        # -------------------------------

        layout_decisions = []


        for floor_program in floor_programs:


            floor_spaces = floor_program.get(

                "spaces",

                []

            )


            layout_decisions.extend(

                self.layout_reasoning.reason(

                    floor_spaces

                )

            )



        # -------------------------------
        # FINAL RESULT
        # -------------------------------

        return {


            "decisions":

                decisions.get(

                    "decisions",

                    []

                ),


            "program_requirements":

                program_requirements.get(

                    "program_requirements",

                    []

                ),


            "floor_programs":

                floor_programs,


            "layout_decisions":

                layout_decisions,

            "vehicle_access_feasibility":
                vehicle_access_feasibility,


            "vehicle_access_decision":
                vehicle_access_decision,

            "vehicle_access_system_decision":
                vehicle_access_system_decision,

            "vehicle_access_candidate_selection":
                vehicle_access_candidate_selection,

            "vehicle_access_geometry":
                vehicle_access_geometry,

            "site_access_coordination":
                site_access_coordination,

            "vehicle_site_access_geometry_design":
                vehicle_site_access_geometry_design,

            "architectural_geometry":
                (
                    vehicle_access_geometry.get("architectural_geometry")
                    if isinstance(vehicle_access_geometry, dict)
                    else building_intent.get("architectural_geometry")
                ),


            "vertical_systems":
                vertical_result.get(
                    "vertical_systems",
                    []
                )

        }
