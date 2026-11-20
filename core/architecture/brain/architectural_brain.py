from core.architecture.model.design_model import DesignModel
from core.architecture.reasoning.space_reasoner import SpaceReasoner
from core.architecture.reasoning.site_reasoner import SiteReasoner
from core.architecture.reasoning.spatial_reasoner import SpatialReasoner
from core.architecture.reasoning.space_generation_reasoner import SpaceGenerationReasoner
from core.architecture.reasoning.knowledge_space_generator import KnowledgeSpaceGenerator
from core.architecture.reasoning.configuration_reasoner import ConfigurationReasoner
from core.architecture.reasoning.design_concept_reasoner import DesignConceptReasoner
from core.architecture.reasoning.layout_reasoner import LayoutReasoner
from core.architecture.reasoning.plan_model_reasoner import PlanModelReasoner
from core.architecture.reasoning.architectural_decision_engine import ArchitecturalDecisionEngine
from core.architecture.reasoning.design_alternative_reasoner import DesignAlternativeReasoner
from core.architecture.reasoning.alternative_selection_reasoner import AlternativeSelectionReasoner
from core.architecture.reasoning.architectural_constraint_reasoner import ArchitecturalConstraintReasoner
from core.architecture.reasoning.architectural_form_reasoner import ArchitecturalFormReasoner
from core.architecture.reasoning.massing_reasoner import MassingReasoner
from core.architecture.reasoning.architectural_design_generator import ArchitecturalDesignGenerator
from core.architecture.reasoning.massing_selection_reasoner import MassingSelectionReasoner
from core.architecture.reasoning.design_scenario_generator import DesignScenarioGenerator
from core.architecture.reasoning.design_scenario_evaluation_engine import DesignScenarioEvaluationEngine
from core.architecture.reasoning.architectural_style_reasoner import ArchitecturalStyleReasoner
from core.architecture.reasoning.facade_language_reasoner import FacadeLanguageReasoner
from core.architecture.reasoning.climate_facade_adaptation_reasoner import ClimateFacadeAdaptationReasoner
from core.architecture.reasoning.material_selection_reasoner import MaterialSelectionReasoner
from core.architecture.reasoning.facade_assembly_reasoner import FacadeAssemblyReasoner
from core.architecture.reasoning.facade_composition_reasoner import FacadeCompositionReasoner
from core.architecture.reasoning.exterior_detail_reasoner import ExteriorDetailReasoner
from core.architecture.reasoning.roof_form_reasoner import RoofFormReasoner
from core.architecture.reasoning.boundary_entrance_reasoner import BoundaryEntranceReasoner
from core.architecture.reasoning.dome_reasoner import DomeReasoner
from core.architecture.reasoning.boundary_wall_reasoner import BoundaryWallReasoner
from core.architecture.reasoning.landscape_interface_reasoner import LandscapeInterfaceReasoner
from core.architecture.reasoning.complete_exterior_design_reasoner import CompleteExteriorDesignReasoner
from core.architecture.bim.exterior_bim_bridge import ExteriorBIMBridge
from core.architecture.bim.bim_enrichment_bridge import BIMEnrichmentBridge
from core.architecture.bim.ifc_mapping_bridge import IFCMappingBridge
from core.architecture.bim.ifc_geometry_intent_resolver import IFCGeometryIntentResolver
from core.architecture.contract.architectural_spatial_contract import (
    ArchitecturalSpatialContract
)
from core.architecture.vertical_building_section_engine import (
    VerticalBuildingSectionEngine
)
from core.architecture.reasoning.architectural_element_placement_reasoner_v3 import (
    ArchitecturalElementPlacementReasonerV3
)

from core.architecture.geometry.architectural_geometry_intent_generator_v1 import (
    ArchitecturalGeometryIntentGeneratorV1
)

from core.architecture.geometry.architectural_geometry_engine_v2 import (
    ArchitecturalGeometryEngineV2
)

from core.architecture.reasoning.architectural_layout_intent_resolver_v1 import (
    ArchitecturalLayoutIntentResolverV1
)

from core.intelligence.vertical_circulation_reasoning import (
    VerticalCirculationReasoning
)
from core.architecture.reasoning.architectural_spatial_quality_gate_v2 import ArchitecturalSpatialQualityGateV2
from core.architecture.reasoning.architectural_spatial_connectivity_reasoner_v1 import ArchitecturalSpatialConnectivityReasonerV1
from core.architecture.reasoning.architectural_vertical_interface_resolver_v1 import ArchitecturalVerticalInterfaceResolverV1
from core.architecture.reasoning.architectural_vertical_interface_resolver_v1 import ArchitecturalVerticalInterfaceResolverV1
from core.architecture.reasoning.pre_geometry_spatial_constraint_evaluator_v1 import PreGeometrySpatialConstraintEvaluatorV1
from core.architecture.reasoning.layout_regeneration_reasoner_v1 import LayoutRegenerationReasonerV1
from core.architecture.reasoning.exterior_entrance_transition_reasoner_v1 import (
    ExteriorEntranceTransitionReasonerV1
)

from core.architecture.geometry.facade_component_resolver_v1 import (
    FacadeComponentResolverV1
)

from core.architecture.geometry.facade_geometry_generator_v1 import (
    FacadeGeometryGeneratorV1
)
from core.site.separation_joint_engine import SeparationJointEngine

# =============================================================================
# NOT THE PRIMARY ARCHITECTOS PLAN GENERATOR.
# HouseDiffusion is the locked primary plan generator under
# HOUSE_DIFFUSION_GENERATION_POLICY_V1.
# Do not extend this branch as the normal product design path.
#
# Entrypoint: ArchitecturalBrain.design
#             (top-level entry of the internal plan synthesis branch:
#              KnowledgeSpaceGenerator -> LayoutReasoner ->
#              SpatialPlacementReasoner -> PlanModelReasoner)
# Enforced by core/architecture/routing/generation_policy_guard_v1.py
# =============================================================================
ARCHITECTOS_GENERATION_ROLE = "DIAGNOSTIC_OR_EXPLICIT_FALLBACK"
PRODUCTION_PRIMARY = False


class ArchitecturalBrain:


    VERSION = "0.1"



    def __init__(self):

        print(
            "🏛 ARCHITECTURAL BRAIN v0.1 ONLINE"
        )


        self.space_reasoner = SpaceReasoner()

        self.site_reasoner = SiteReasoner()

        self.spatial_reasoner = SpatialReasoner()

        self.space_generation_reasoner = SpaceGenerationReasoner()

        self.knowledge_space_generator = KnowledgeSpaceGenerator()

        self.configuration_reasoner = ConfigurationReasoner()

        self.design_concept_reasoner = DesignConceptReasoner()

        self.layout_reasoner = LayoutReasoner()

        self.plan_model_reasoner = PlanModelReasoner()

        self.decision_engine = ArchitecturalDecisionEngine()

        self.design_alternative_reasoner = DesignAlternativeReasoner()

        self.alternative_selection_reasoner = AlternativeSelectionReasoner()

        self.constraint_reasoner = ArchitecturalConstraintReasoner()

        self.form_reasoner = ArchitecturalFormReasoner()

        self.massing_reasoner = MassingReasoner()

        self.massing_selection_reasoner = MassingSelectionReasoner()

        self.design_scenario_generator = DesignScenarioGenerator()

        self.design_generator = ArchitecturalDesignGenerator()

        self.design_scenario_evaluation_engine = DesignScenarioEvaluationEngine()

        self.style_reasoner = ArchitecturalStyleReasoner()

        self.facade_language_reasoner = FacadeLanguageReasoner()

        self.climate_facade_reasoner = ClimateFacadeAdaptationReasoner()

        self.material_selection_reasoner = MaterialSelectionReasoner()

        self.facade_assembly_reasoner = FacadeAssemblyReasoner()

        self.facade_composition_reasoner = FacadeCompositionReasoner()

        self.facade_component_resolver = (
            FacadeComponentResolverV1()
        )

        self.facade_geometry_generator = (
            FacadeGeometryGeneratorV1()
        )

        self.roof_form_reasoner = RoofFormReasoner()

        self.dome_reasoner = DomeReasoner()

        self.boundary_entrance_reasoner = BoundaryEntranceReasoner()

        self.boundary_wall_reasoner = BoundaryWallReasoner()

        self.landscape_reasoner = LandscapeInterfaceReasoner()

        self.exterior_detail_reasoner = ExteriorDetailReasoner()

        self.complete_exterior_design_reasoner = CompleteExteriorDesignReasoner()

        self.exterior_bim_bridge = ExteriorBIMBridge()

        self.bim_enrichment_bridge = BIMEnrichmentBridge(
            context={
                "floor_height": 3.2,
                "wall_thickness": 0.35
            }
        )

        self.ifc_mapping_bridge = IFCMappingBridge()

        self.ifc_geometry_intent_resolver = IFCGeometryIntentResolver()

        self.spatial_contract = ArchitecturalSpatialContract()

        self.vertical_section_engine = VerticalBuildingSectionEngine()

        self.placement_reasoner = (
            ArchitecturalElementPlacementReasonerV3()
        )

        self.geometry_intent_generator = ArchitecturalGeometryIntentGeneratorV1()

        self.geometry_engine = (
            ArchitecturalGeometryEngineV2()
        )

        self.exterior_entrance_transition_reasoner = ExteriorEntranceTransitionReasonerV1()

        self.layout_intent_resolver = ArchitecturalLayoutIntentResolverV1()

        self.vertical_reasoner = (
            VerticalCirculationReasoning()
        )
        # V1 remains import-compatible; V2 is the final architectural authority.
        self.spatial_quality_gate = ArchitecturalSpatialQualityGateV2()
        self.spatial_connectivity_reasoner = ArchitecturalSpatialConnectivityReasonerV1()
        self.vertical_interface_resolver = ArchitecturalVerticalInterfaceResolverV1()
        self.vertical_interface_resolver = ArchitecturalVerticalInterfaceResolverV1()
        self.pre_geometry_evaluator = PreGeometrySpatialConstraintEvaluatorV1()
        self.layout_regeneration_reasoner = LayoutRegenerationReasonerV1()

        self.separation_joint_engine = SeparationJointEngine()

        



    def design(
        self,
        intent
    ):


        model = DesignModel()


        model.intent = intent



        # ===============================
        # SITE REASONING
        # ===============================

        site = intent.get(
            "site",
            {}
        )


        site_analysis = self.site_reasoner.analyze(
            site
        )

        # Separation is architectural site geometry authority. Resolve the
        # buildable envelope before any room/layout placement occurs.
        parcel_boundary = site_analysis.get("building_strategy", {}).get(
            "parcel_boundary"
        )
        explicit_analysis = site.get("separation_joint_analysis")
        if isinstance(explicit_analysis, dict):
            separation_analysis = explicit_analysis
        else:
            neighbors = site.get("neighbors", {})
            height = site.get("building_height")
            separation_analysis = None
            if isinstance(neighbors, dict) and isinstance(height, (int, float)):
                separation_analysis = self.separation_joint_engine.analyze(
                    {"height": float(height)},
                    neighbors,
                    site.get("separation_joint_requirement", {"enabled": True}),
                )
        if isinstance(separation_analysis, dict):
            envelope = self.separation_joint_engine.resolve_buildable_envelope(
                parcel_boundary, separation_analysis
            )
            site_analysis["separation"] = separation_analysis
            site_analysis["separation_joint_application"] = envelope
            if envelope.get("status") == "resolved":
                site_analysis.setdefault("building_strategy", {})[
                    "buildable_boundary"
                ] = envelope["buildable_boundary"]


        model.site_analysis = site_analysis



        # ===============================
        # SPACE INPUT
        # ===============================

        spaces = intent.get(
            "spaces",
            []
        )



        # ===============================
        # SPACE REASONING
        # ===============================

        analyzed_spaces = self.space_reasoner.analyze(
            spaces
        )


        for space in analyzed_spaces:

            model.add_space(
                space
            )



        spatial_analysis = self.spatial_reasoner.analyze(
            spaces,
            site_analysis
        )


        model.spatial_analysis = spatial_analysis



        # ===============================
        # SPACE GENERATION
        # ===============================

        space_generation = self.space_generation_reasoner.generate(
            intent,
            site_analysis
        )


        knowledge_spaces = self.knowledge_space_generator.generate(
            intent
        )

        print(
            "DEBUG BRAIN GENERATED SPACES:",
            knowledge_spaces.get(
                "generated_spaces",
                []
            )
        )


        configuration = self.configuration_reasoner.analyze(
            intent,
            site_analysis,
            knowledge_spaces
        )


        design_concept = self.design_concept_reasoner.generate(
            intent,
            site_analysis,
            configuration
        )


        model.design_concept = design_concept

        layout_context = dict(
            design_concept
        )


        layout_context[
            "building_type"
        ] = intent.get(
            "building_type"
        )


        layout_context[
            "functions"
        ] = list(
            intent.get(
                "functions",
                []
            )
        )


        layout = self.layout_reasoner.generate(
            knowledge_spaces.get(
                "generated_spaces",
                []
            ),
            knowledge_spaces.get(
                "relationships",
                []
            ),
            layout_context,
            knowledge_spaces.get(
                "generated_spaces",
                []
            ),
            site_analysis
        )

        print(
            "DEBUG LAYOUT INPUT SPACES:",
            knowledge_spaces.get(
                "generated_spaces",
                []
            )
        )


        model.layout = layout

        regeneration_config = intent.get("layout_regeneration", {}) if isinstance(intent, dict) else {}
        if isinstance(regeneration_config, dict) and regeneration_config.get("enabled") is True:
            buildable = site_analysis.get("building_strategy", {}).get("buildable_boundary")
            if isinstance(buildable, list) and len(buildable) >= 3:
                # SpatialPlacement coordinates are local to the buildable
                # envelope; parcel translation is applied by geometry intent.
                min_x = min(float(p[0]) for p in buildable)
                min_y = min(float(p[1]) for p in buildable)
                buildable = [[float(p[0])-min_x, float(p[1])-min_y] for p in buildable]
            protected = list(regeneration_config.get("protected_zones", []))
            pre_connections = []
            seen_pre_connections = set()
            for relation in list(intent.get("relationships", [])) + list(layout.get("connections", [])):
                if not isinstance(relation, dict): continue
                identity = relation.get("connection_id") or tuple(sorted((str(relation.get("from")), str(relation.get("to")))))
                if identity in seen_pre_connections: continue
                seen_pre_connections.add(identity); pre_connections.append(relation)
            pre_evaluation = self.pre_geometry_evaluator.evaluate(
                layout.get("spatial_layout", []), pre_connections, buildable, protected
            )
            model.pre_geometry_spatial_evaluation = pre_evaluation
            if pre_evaluation.get("status") != "passed":
                regeneration = self.layout_regeneration_reasoner.regenerate(
                    layout.get("spatial_layout", []), pre_connections, buildable, protected,
                    regeneration_config.get("max_attempts", 1),
                )
                model.layout_regeneration = regeneration
                if regeneration.get("status") == "resolved":
                    layout["spatial_layout"] = regeneration["selected_layout"]
                    final_evaluation = self.pre_geometry_evaluator.evaluate(
                        layout["spatial_layout"], pre_connections, buildable, protected
                    )
                    model.pre_geometry_spatial_evaluation = final_evaluation
                    if final_evaluation.get("quality_score", 0) <= pre_evaluation.get("quality_score", 0):
                        regeneration["status"] = "unresolved_no_quality_improvement"
                if model.layout_regeneration.get("status") != "resolved":
                    layout["geometry_generation_allowed"] = False
                    model.architectural_geometry = {
                        "geometry_status": "pre_geometry_layout_unresolved",
                        "architectural_authority": False,
                        "physical_walls": [], "openings": [], "slabs": [], "floor_geometry": [],
                        "pre_geometry_spatial_evaluation": model.pre_geometry_spatial_evaluation,
                        "layout_regeneration": model.layout_regeneration,
                    }
                    return model


        plan_model = self.plan_model_reasoner.generate(
            layout,
            site_analysis
        )


        model.plan_model = plan_model.to_dict()

        # ===============================
        # PRESERVE PLAN SPACES
        # ===============================

        model.spaces = list(
            plan_model.spaces
        )

        model.relationships = list(
            plan_model.relationships
        )


        decisions = self.decision_engine.analyze(
            plan_model,
            model.site_analysis,
            design_concept
        )

        model.design_strategy = decisions


        alternatives = self.design_alternative_reasoner.generate(
            model.site_analysis,
            decisions,
            intent
        )

        model.design_alternatives = alternatives


        selection = self.alternative_selection_reasoner.select(
            alternatives.get(
                "alternatives",
                []
            ),
            intent,
            model.site_analysis
        )


        model.selected_alternative = selection


        constraints = self.constraint_reasoner.analyze(
            intent,
            model.site_analysis,
            selection
        )


        model.architectural_constraints = constraints


        form_analysis = self.form_reasoner.analyze(
            intent,
            constraints,
            selection
        )


        model.form_analysis = form_analysis


        massing_analysis = self.massing_reasoner.analyze(
            form_analysis,
            constraints,
            design_concept
        )
        


        model.massing_analysis = massing_analysis


        design_scenarios = self.design_scenario_generator.generate(
            intent,
            site_analysis,
            massing_analysis
        )


        model.design_scenarios = design_scenarios


        scenario_evaluation = self.design_scenario_evaluation_engine.evaluate(
            design_scenarios.get(
                "scenarios",
                []
            ),
            intent,
            site_analysis
        )


        model.design_scenario_evaluation = scenario_evaluation


        style_analysis = self.style_reasoner.analyze(
            intent,
            scenario_evaluation
        )


        model.style_analysis = style_analysis


        style_candidates = style_analysis.get(
            "style_candidates",
            []
        )


        facade_language = self.facade_language_reasoner.analyze(
            style_analysis
        )

        model.facade_language = facade_language


        climate_facade = self.climate_facade_reasoner.analyze(
            intent,
            facade_language
        )

        model.climate_facade_strategy = climate_facade


        materials = self.material_selection_reasoner.select(
            intent.get(
                "style",
                ""
            ),
            facade_language,
            climate_facade
        )


        model.material_strategy = materials


        # ===============================
        # FACADE ASSEMBLY REASONING
        # ===============================

        facade_assembly = self.facade_assembly_reasoner.generate(
            style_candidates[0] if style_candidates else "modern",
            facade_language,
            materials.get(
                "primary_materials",
                []
            )
        )


        model.facade_assembly = facade_assembly


        facade_composition = self.facade_composition_reasoner.analyze(
            style_candidates[0] if style_candidates else "modern",
            facade_assembly
        )


        model.facade_composition = facade_composition


        boundary_entrance = self.boundary_entrance_reasoner.analyze(
            style_candidates[0] if style_candidates else "modern",
            facade_language,
            materials
        )


        model.boundary_entrance = boundary_entrance


        boundary_wall = self.boundary_wall_reasoner.analyze(
            style_candidates[0] if style_candidates else "modern",
            materials
        )

        model.boundary_wall = boundary_wall


        landscape_strategy = self.landscape_reasoner.analyze(
            style_candidates[0] if style_candidates else "modern",
            intent.get("site", {}).get("climate", {}),
            spaces
        )

        model.landscape_strategy = landscape_strategy


        exterior_details = self.exterior_detail_reasoner.analyze(
            style_candidates[0] if style_candidates else "modern",
            facade_language,
            materials
        )

        model.exterior_details = exterior_details


        massing_selection = self.massing_selection_reasoner.select(
            intent,
            site_analysis,
            massing_analysis
        )


        model.massing_selection = massing_selection


        design_intent = self.design_generator.generate(
            intent,
            site_analysis,
            massing_selection,
            decisions
        )


        model.design_intent = design_intent


        roof_strategy = self.roof_form_reasoner.analyze(
            style_candidates[0] if style_candidates else "modern",
            design_intent
        )


        model.roof_strategy = roof_strategy


        dome_strategy = self.dome_reasoner.analyze(
            style_candidates[0] if style_candidates else "modern",
            roof_strategy,
            facade_composition
        )


        model.dome_strategy = dome_strategy


        complete_exterior = self.complete_exterior_design_reasoner.generate(

            style_candidates[0] if style_candidates else "modern",

            facade_language,

            materials,

            facade_assembly,

            facade_composition,

            roof_strategy,

            dome_strategy,

            model.boundary_wall,

            model.boundary_entrance,

            model.landscape_strategy,

            exterior_details

        )


        model.complete_exterior_design = complete_exterior

        


        # ===============================
        # ARCHITECTURAL SPATIAL CONTRACT
        # ===============================

        spatial_contract = self.spatial_contract.generate(
            layout,
            architectural_intent=intent
        )


        model.spatial_contract = spatial_contract

        vertical_section = self.vertical_section_engine.generate(
            spatial_contract,
            architectural_intent=intent
        )

        model.vertical_section = vertical_section

        # ===============================
        # LAYOUT INTENT RESOLUTION
        # ===============================

        layout_intent = self.layout_intent_resolver.resolve(
            spatial_contract
        )

        # ===============================
        # VERTICAL SYSTEM REASONING
        # ===============================

        vertical_systems = self.vertical_reasoner.analyze(
            intent
        )


        model.vertical_systems = vertical_systems


        

        placement = self.placement_reasoner.generate(
            layout_intent,
            spatial_contract,
            vertical_systems
        )

        model.layout_intent = layout_intent

        model.element_placement = placement

        entrance_transition = self.exterior_entrance_transition_reasoner.resolve(
            intent,
            vertical_section=vertical_section
        )

        geometry_intent = (
            self.geometry_intent_generator.generate(
                placement,
                roof_strategy=roof_strategy,
                site_analysis=site_analysis,
                vertical_section=vertical_section,
                entrance_transition=entrance_transition,
                architectural_intent=intent
            )
        )

        model.geometry_intent = geometry_intent

        architectural_geometry = (
            self.geometry_engine.generate(
                geometry_intent
            )
        )

        vertical_interfaces = self.vertical_interface_resolver.resolve(
            architectural_geometry.get("spaces", []), architectural_geometry.get("vertical_geometry", []), intent
        )
        architectural_geometry["vertical_interface_contract"] = vertical_interfaces
        architectural_geometry["vertical_interfaces"] = vertical_interfaces["interfaces"]

        connectivity = self.spatial_connectivity_reasoner.resolve(
            architectural_geometry, spatial_contract, intent
        )
        architectural_geometry["spatial_connection_contract"] = connectivity
        architectural_geometry["connections"] = connectivity["connections"]

        interior_intents = self.geometry_engine.opening_reasoner.resolve_connections(
            connectivity["connections"], architectural_geometry.get("physical_walls", []),
            architectural_geometry.get("openings", []), architectural_geometry.get("architectural_protected_zones", [])
        )
        interior_openings, updated_walls = self.geometry_engine.physical_opening_resolver.resolve(
            interior_intents, architectural_geometry.get("physical_walls", [])
        )
        architectural_geometry["physical_walls"] = updated_walls
        architectural_geometry.setdefault("openings", []).extend(interior_openings)
        by_connection = {item.get("connection_id"): item for item in interior_openings
                         if item.get("connection_id") and item.get("geometry_status") == "resolved"}
        for connection in connectivity["connections"]:
            opening = by_connection.get(connection.get("connection_id"))
            if connection.get("door_required") is True:
                if opening:
                    connection.update({"opening_id": opening.get("opening_id"),
                                       "host_wall_id": opening.get("host_wall_id"),
                                       "opening_center": opening.get("opening_center"),
                                       "opening_geometry_status": "resolved",
                                       "physical_connection_status": "resolved"})
                else:
                    connection["physical_connection_status"] = "pending"
                    connection["opening_geometry_status"] = "pending"

        exposures = self.geometry_engine.opening_reasoner.resolve_exterior_exposure(
            architectural_geometry.get("spaces", []), architectural_geometry.get("physical_walls", [])
        )
        architectural_geometry["room_exterior_exposure"] = exposures
        window_requirements = architectural_geometry.get("project_requirements", {}).get("window_requirements", [])
        window_intents = self.geometry_engine.opening_reasoner.resolve_windows(
            exposures, window_requirements, architectural_geometry.get("physical_walls", []),
            architectural_geometry.get("openings", []), architectural_geometry.get("architectural_protected_zones", [])
        )
        physical_windows, updated_walls = self.geometry_engine.physical_opening_resolver.resolve(
            window_intents, architectural_geometry.get("physical_walls", [])
        )
        architectural_geometry["physical_walls"] = updated_walls
        architectural_geometry.setdefault("openings", []).extend(physical_windows)
        architectural_geometry["window_feasibility_evidence"] = [{
            "window_id": item.get("opening_id"), "served_space_id": item.get("served_space_id"),
            "host_wall_id": item.get("host_wall_id"), "opening_center": item.get("opening_center"),
            "exterior_host_status": item.get("exterior_host_status"),
            "physical_window_status": item.get("geometry_status"),
            "daylight_feasibility_status": item.get("daylight_feasibility_status"),
            "privacy_status": item.get("privacy_status")
        } for item in physical_windows]

        spatial_quality = self.spatial_quality_gate.evaluate(
            architectural_geometry, intent.get("spatial_quality_requirements")
        )
        architectural_geometry["spatial_quality_gate"] = spatial_quality
        if spatial_quality.get("status") != "passed":
            architectural_geometry["architectural_authority"] = False
            architectural_geometry["geometry_status"] = "spatial_quality_" + spatial_quality.get("status", "unresolved")


        model.architectural_geometry = architectural_geometry

        # ===============================
        # FACADE COMPONENT CONTRACT
        # ===============================

        facade_components = (
            self.facade_component_resolver.resolve(
                complete_exterior
            )
        )


        model.facade_components = facade_components


        # ===============================
        # FACADE GEOMETRY CONTRACT
        # ===============================

        facade_geometry = (
            self.facade_geometry_generator.generate(
                facade_components,
                architectural_geometry
            )
        )


        model.facade_geometry = facade_geometry

        # ===============================
        # EXTERIOR BIM BRIDGE
        # ===============================


        exterior_bim = self.exterior_bim_bridge.map_exterior(
            complete_exterior,
            architectural_geometry,
            facade_components=facade_components,
            facade_geometry=facade_geometry
        )


        model.exterior_bim = exterior_bim
        

        bim_enriched = self.bim_enrichment_bridge.enrich(
            exterior_bim
        )


        model.bim_enriched = bim_enriched


        ifc_mapping = self.ifc_mapping_bridge.map(
            bim_enriched
        )


        model.ifc_mapping = ifc_mapping


        geometry_resolution = self.ifc_geometry_intent_resolver.resolve(
            ifc_mapping
        )


        model.geometry_resolution = geometry_resolution



        model.configuration = configuration


        model.knowledge_spaces = knowledge_spaces


        model.space_generation = space_generation



        model.add_decision(
            "site analyzed based on architectural reasoning"
        )


        model.add_decision(
            "spaces analyzed based on architectural knowledge"
        )


        model.add_decision(
            "spaces generated based on architectural program reasoning"
        )


        return model
