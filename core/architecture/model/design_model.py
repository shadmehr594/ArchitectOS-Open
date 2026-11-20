class DesignModel:


    def __init__(self):

        self.site_analysis = {}

        self.intent = {}

        self.spaces = []

        self.relationships = []

        self.decisions = []

        self.facade_strategy = {}

        self.climate_strategy = {}


        # ===============================
        # ARCHITECTURAL INTELLIGENCE DATA
        # ===============================

        self.design_concept = {}

        self.layout = {}

        self.plan_model = {}

        self.design_strategy = {}

        self.design_alternatives = {}

        self.selected_alternative = {}

        self.architectural_constraints = {}

        self.form_analysis = {}

        self.massing_analysis = {}

        self.massing_selection = {}

        self.design_scenarios = {}

        self.design_scenario_evaluation = {}

        self.style_analysis = {}

        self.facade_language = {}

        self.climate_facade_strategy = {}

        self.material_strategy = {}

        self.facade_assembly = {}

        self.facade_composition = {}

        self.facade_components = {}

        self.facade_geometry = {}

        self.roof_strategy = {}

        self.dome_strategy = {}

        self.boundary_wall = {}

        self.boundary_entrance = {}

        self.landscape_strategy = {}

        self.exterior_details = {}

        self.complete_exterior_design = {}


        # ===============================
        # BIM INTENT
        # ===============================

        self.exterior_bim = {}

        self.bim_enriched = {}

        self.ifc_mapping = {}

        self.geometry_resolution = {}


        # ===============================
        # SPATIAL CONTRACT
        # ===============================

        self.architectural_spatial_contract = {}

        self.vertical_systems = {}


        # ===============================
        # ARCHITECTURAL GEOMETRY PIPELINE
        # ===============================

        self.spatial_contract = {}

        self.vertical_section = {}

        self.layout_intent = {}

        self.element_placement = {}

        self.geometry_intent = {}

        self.architectural_geometry = {}
        self.pre_geometry_spatial_evaluation = {}
        self.layout_regeneration = {}



    def add_space(
        self,
        space
    ):

        self.spaces.append(
            space
        )



    def add_decision(
        self,
        decision
    ):

        self.decisions.append(
            decision
        )



    def to_dict(
        self
    ):

        return {

            "site_analysis":
                self.site_analysis,


            "intent":
                self.intent,


            "spaces":
                [
                    s.to_dict()
                    if hasattr(
                        s,
                        "to_dict"
                    )
                    else s
                    for s in self.spaces
                ],


            "relationships":
                self.relationships,


            "decisions":
                self.decisions,


            "facade_strategy":
                self.facade_strategy,


            "climate_strategy":
                self.climate_strategy,


            "architectural_intelligence":
                {

                    "design_concept":
                        self.design_concept,


                    "layout":
                        self.layout,


                    "plan_model":
                        self.plan_model,


                    "design_strategy":
                        self.design_strategy,


                    "design_alternatives":
                        self.design_alternatives,


                    "selected_alternative":
                        self.selected_alternative,


                    "architectural_constraints":
                        self.architectural_constraints,


                    "form_analysis":
                        self.form_analysis,


                    "massing_analysis":
                        self.massing_analysis,


                    "massing_selection":
                        self.massing_selection,


                    "design_scenarios":
                        self.design_scenarios,


                    "design_scenario_evaluation":
                        self.design_scenario_evaluation,


                    "style_analysis":
                        self.style_analysis,


                    "facade_language":
                        self.facade_language,


                    "climate_facade_strategy":
                        self.climate_facade_strategy,


                    "material_strategy":
                        self.material_strategy,


                    "facade_assembly":
                        self.facade_assembly,


                    "facade_composition":
                        self.facade_composition,


                    "facade_components":
                        self.facade_components,


                    "facade_geometry":
                        self.facade_geometry,


                    "roof_strategy":
                        self.roof_strategy,


                    "dome_strategy":
                        self.dome_strategy,


                    "boundary_wall":
                        self.boundary_wall,


                    "boundary_entrance":
                        self.boundary_entrance,


                    "landscape_strategy":
                        self.landscape_strategy,


                    "exterior_details":
                        self.exterior_details,


                    "complete_exterior_design":
                        self.complete_exterior_design,


                    "architectural_spatial_contract":
                        self.architectural_spatial_contract,


                    "spatial_contract":
                        self.spatial_contract,


                    "vertical_section":
                        self.vertical_section,


                    "layout_intent":
                        self.layout_intent,


                    "element_placement":
                        self.element_placement,


                    "geometry_intent":
                        self.geometry_intent,


                    "architectural_geometry":
                        self.architectural_geometry,

                    "pre_geometry_spatial_evaluation":
                        self.pre_geometry_spatial_evaluation,

                    "layout_regeneration":
                        self.layout_regeneration,


                    "exterior_bim":
                        self.exterior_bim,


                    "bim_enriched":
                        self.bim_enriched,


                    "ifc_mapping":
                        self.ifc_mapping,


                    "geometry_resolution":
                        self.geometry_resolution,


                    "vertical_systems":
                        self.vertical_systems

                }

        }
