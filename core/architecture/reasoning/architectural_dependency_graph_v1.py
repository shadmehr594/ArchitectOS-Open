"""Explicit cross-floor architectural decision dependencies."""


class ArchitecturalDependencyGraphV1:
    CONTEXT_TRIGGERS=("road","frontage","neighbors")
    DEMAND_TRIGGERS=("program","requirements","regulations")
    EDGES=tuple((x,"site_resource_region_derivation") for x in CONTEXT_TRIGGERS)+tuple((x,"program_demand_profile") for x in DEMAND_TRIGGERS)+(
           ("site_resource_region_derivation","site_resource_map"),
           ("site_resource_map","scarcity_model"),("program_demand_profile","scarcity_model"),
           ("site_resource_map","pre_realization_daylight_deficit"),("program_demand_profile","pre_realization_daylight_deficit"),
           ("scarcity_model","allocation_plan"),("program_demand_profile","allocation_plan"),
           ("allocation_plan","opportunity_cost"),("allocation_plan","geometry_realization"),
           ("program_demand_profile","operational_relationship_requirements"),("allocation_plan","operational_relationship_requirements"),
           ("pre_realization_daylight_deficit","operational_relationship_requirements"),
           ("opportunity_cost","geometry_realization"),("operational_relationship_requirements","geometry_realization"),
           ("pre_realization_daylight_deficit","geometry_realization"),
           ("geometry_realization","ownership_gate"),("ownership_gate","operational_feasibility"),
           ("operational_feasibility","contextual_quality"),("contextual_quality","architectural_critic"),
           ("architectural_critic","decision_support_shortlist"),
           ("allocation_plan","core_location"),
           ("allocation_plan","daylight_court_location"),("allocation_plan","terrace_location"),
           ("core_location","ground_floor_commercial_geometry"),("core_location","parking_geometry"),
           ("core_location","vertical_alignment"),("core_location","residential_split_feasibility"),
           ("residential_split","daylight_court_location"),("daylight_court_location","terrace_location"),
            ("terrace_location","privacy"),("core_location","common_access"),("residential_split","common_access"))
    def build(self, decisions):
        nodes=sorted({x for edge in self.EDGES for x in edge})
        upstream={n:[a for a,b in self.EDGES if b==n] for n in nodes};downstream={n:[b for a,b in self.EDGES if a==n] for n in nodes}
        return {"contract":"ArchitecturalDependencyGraphV1","decisions":decisions,
                "nodes":[{"node_id":n,"upstream_decisions":upstream[n],"downstream_consequences":downstream[n]} for n in nodes],
                "edges":[{"upstream_decision":a,"downstream_consequence":b} for a,b in self.EDGES],
                "cross_floor_dependency_explicit":True}
