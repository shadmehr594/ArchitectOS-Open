"""Architecture-only orchestration authority for regenerative design studies."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from .architectural_design_intelligence_v1 import (
    ArchitecturalCritic, CaseLessonMemory, DaylightDeficitIntelligence,
    PublicPrivateServiceZoning, RedesignScopeResolver, ResourcePriorityReasoning,
    TopologyInvalidationEngine,
)
from .contextual_site_resource_map_v1 import ContextualSiteResourceMapV1
from .contextual_program_demand_profile_v1 import ContextualProgramDemandProfileV1
from .authoritative_stair_requirements_resolution_v1 import AuthoritativeStairRequirementsResolutionV1
from .contextual_level_height_and_floor_assembly_v1 import ContextualLevelHeightAndFloorAssemblyV1
from .stair_configuration_authority_v1 import StairConfigurationAuthorityV1
from .spatial_demand_sizing_and_capacity_v1 import SpatialDemandSizingAndCapacityV1
from .vertical_circulation_footprint_sizing_v1 import VerticalCirculationFootprintSizingV1
from .flexible_area_allocation_authority_v1 import FlexibleAreaAllocationAuthorityV1
from .resource_scarcity_and_competition_v1 import ResourceScarcityAndCompetitionV1
from .contextual_spatial_allocation_planner_v1 import ContextualSpatialAllocationPlannerV1
from .opportunity_cost_evaluator_v1 import OpportunityCostEvaluatorV1


class ArchitecturalBrainOrchestratorV1:
    CAPABILITY_ORDER = ("parking", "vehicle_movement", "pedestrian", "daylight", "privacy", "commercial", "core")

    @staticmethod
    def _contextual_shortlist(hypotheses, ownership):
        valid=ownership.get("hard_validation_status") == "hard_valid"
        return {"shortlist": deepcopy(hypotheses) if valid else [],
                "contextual_scoring_skipped": not valid,
                "ownership_gate_status": ownership.get("hard_validation_status", "not_evaluated")}

    def run(self, context, reasoners):
        missing = [name for name in self.CAPABILITY_ORDER if name not in reasoners]
        if missing:
            raise ValueError("missing architectural reasoners: " + ", ".join(missing))
        source = deepcopy(context)
        trace, evidence = [], {}
        site_map=ContextualSiteResourceMapV1().build(source)
        demand=ContextualProgramDemandProfileV1().build(source.get("program", {"functions":source.get("spaces",[])}),
            source.get("requirements"),source.get("regulations"),source.get("demand_context"))
        level_semantics=ContextualLevelHeightAndFloorAssemblyV1().resolve({
            "occupancies": source.get("project_context", {}).get("occupancies", []),
            "evidence": source.get("level_height_evidence", []),
            "drainage_context": source.get("drainage_context", {}),
            "level_contract": source.get("level_contract"),
            "human_level_confirmations": source.get("human_level_confirmations", []),
        })
        stair_requirements=AuthoritativeStairRequirementsResolutionV1().resolve(
            demand, source.get("requirements"), source.get("regulations"),
            level_semantics["project_level_contract"]["authoritative_stair_level_contract"],
            project_context=source.get("project_context"))
        sizing=SpatialDemandSizingAndCapacityV1().resolve(stair_requirements["demand_profile"])
        stair_configuration=StairConfigurationAuthorityV1().resolve(
            sizing, source.get("stair_configuration"))
        vertical_circulation=VerticalCirculationFootprintSizingV1().resolve(
            stair_configuration["demand_profile"])
        vertical_ready=vertical_circulation["demand_profile"]
        flexible_allocation=FlexibleAreaAllocationAuthorityV1().allocate(site_map,vertical_ready)
        allocation_ready=flexible_allocation["demand_profile"]
        scarcity=ResourceScarcityAndCompetitionV1().evaluate(site_map,allocation_ready)
        allocation=ContextualSpatialAllocationPlannerV1().plan(site_map,allocation_ready,scarcity,source.get("dependencies"))
        opportunity=OpportunityCostEvaluatorV1().evaluate(allocation,allocation_ready)
        contextual={"site_resource_map":site_map,"program_demand_profile":demand,
                    "contextual_level_height_and_floor_assembly":level_semantics,
                    "authoritative_stair_requirements_resolution":stair_requirements,"spatial_demand_sizing":sizing,
                    "stair_configuration_authority":stair_configuration,
                    "vertical_circulation_footprint_sizing":vertical_circulation,
                    "flexible_area_allocation":flexible_allocation,"allocation_ready_demand_profile":allocation_ready,"scarcity_model":scarcity,
                    "allocation_plan":allocation,"opportunity_cost":opportunity}
        for name,value in contextual.items():
            evidence[name]=value; trace.append({"capability":name,"executed":True,"authority":value["contract"],
                                               "before_geometry_realization":True})
        for name in self.CAPABILITY_ORDER:
            result = reasoners[name](deepcopy(source), deepcopy(evidence))
            evidence[name] = result
            trace.append({"capability": name, "executed": True, "authority": result.get("contract", type(result).__name__)})

        spaces = source.get("spaces", [])
        invalidation = TopologyInvalidationEngine().analyze(source.get("changes", []), source.get("floors", []))
        scope = RedesignScopeResolver().resolve(invalidation, source.get("requirements", {}))
        daylight = DaylightDeficitIntelligence().evaluate(spaces, source.get("daylight_sources", []),
                                                          source.get("minimum_daylight_ratio", .12))
        zoning = PublicPrivateServiceZoning().classify(spaces)
        priority = ResourcePriorityReasoning().rank(spaces, source.get("resource_values"))
        ownership=deepcopy(source.get("ownership_evidence", {"hard_validation_status":"not_evaluated","hard_failure_codes":[]}))
        shortlist=self._contextual_shortlist(allocation["hypotheses"],ownership)
        critique = ArchitecturalCritic().review(evidence, zoning, daylight,
            contextual if source.get("resource_regions") is not None else None,
            ownership if ownership["hard_validation_status"] != "not_evaluated" else None)
        lessons = [CaseLessonMemory().record(source.get("case_id", "anonymous"), item.get("decision", "review"),
                                             item.get("rationale", ""), item.get("source", "architect_review"),
                                             item.get("approved", False)) for item in source.get("lessons", [])]
        if scope["major_impact"]:
            regeneration = {"mode": "from_requirements", "seed": deepcopy(source.get("requirements", {})),
                            "prior_geometry_used_as_seed": False, "invalidated_floors": invalidation["affected_floors"]}
        else:
            regeneration = {"mode": "affected_dependencies", "seed": None,
                            "prior_geometry_used_as_seed": False, "invalidated_floors": invalidation["affected_floors"]}
        fingerprint = lambda value: sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]
        old_geometry = source.get("prior_geometry")
        provenance = {"requirements_fingerprint": fingerprint(source.get("requirements", {})),
                      "prior_geometry_fingerprint": fingerprint(old_geometry) if old_geometry is not None else None,
                      "prior_geometry_used_as_seed": False,
                      "regeneration_source": "requirements_and_clean_context",
                      "affected_dependencies": invalidation["invalidated_dependencies"]}
        return {"contract": "ArchitecturalBrainOrchestratorV1", "architecture_only": True,
                "reasoning_sequence": ["SiteResourceAnalysis", "ProgramPriorityReasoning",
                    "DemandSupplyAnalysis", "TopologyHypotheses", "CoupledGeneration",
                    "DependencyDrivenRegeneration", "ArchitecturalCritic", "DecisionSupportShortlist"],
                "execution_trace": trace, "reasoner_evidence": evidence,
                "contextual_resource_allocation":contextual,"contextual_shortlist":shortlist,
                "ownership_evidence":ownership,"contextual_scoring_skipped":shortlist["contextual_scoring_skipped"],
                "resource_priority": priority, "topology_invalidation": invalidation,
                "redesign_scope": scope, "regeneration": regeneration,
                "daylight_deficit": daylight, "zoning": zoning, "architectural_critic": critique,
                "case_lessons": lessons, "regeneration_provenance": provenance,
                "stable_knowledge_mutated": False,
                "final_selection_performed": False, "winner":None, "room_layout_generated": False,
                "final_windows_generated": False, "structure_executed": False,
                "bim_executed": False, "ifc_executed": False, "render_executed":False}
