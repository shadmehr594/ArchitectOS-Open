class MultiAgentArchitectTeam:

    def __init__(self, pipeline, zoning_engine, reasoning_engine):

        self.pipeline = pipeline
        self.zoning = zoning_engine
        self.reasoning = reasoning_engine

        # ======================
        # AGENTS
        # ======================
        self.agents = {
            "architect": ArchitectAgent(),
            "structural": StructuralAgent(),
            "zoning": ZoningAgent(zoning_engine),
            "site": SiteAgent(),
            "bim": BIMAgent()
        }

    # ======================
    # MAIN ORCHESTRATION
    # ======================
    def run(self, state):

        context = self._init_context(state)

        # ======================
        # STEP 1 - PARALLEL ANALYSIS
        # ======================
        reports = {}

        for name, agent in self.agents.items():

            reports[name] = agent.analyze(context)

        # ======================
        # STEP 2 - CONSENSUS BUILDING
        # ======================
        decision = self._build_consensus(reports)

        # ======================
        # STEP 3 - DESIGN GENERATION
        # ======================
        design = self.pipeline.generate(
            state=state,
            constraints=decision["constraints"]
        )

        # ======================
        # STEP 4 - CROSS VALIDATION LOOP
        # ======================
        validation = self._cross_validate(design, reports)

        if not validation["approved"]:

            improved_context = self._refine_context(context, validation)

            return self.run(improved_context)

        return {
            "status": "approved",
            "design": design,
            "reports": reports,
            "decision": decision,
            "validation": validation
        }

    # ======================
    # CONSENSUS ENGINE
    # ======================
    def _build_consensus(self, reports):

        constraints = {
            "max_height": 0,
            "max_coverage": 0,
            "required_units": 0
        }

        # zoning sets hard limits
        constraints["max_height"] = reports["zoning"]["limits"]["height"]
        constraints["max_coverage"] = reports["zoning"]["limits"]["coverage"]

        # structural adjusts safety factor
        constraints["safety_factor"] = reports["structural"].get("safety", 1.0)

        return {
            "constraints": constraints,
            "confidence": 0.85
        }

    # ======================
    # CROSS VALIDATION
    # ======================
    def _cross_validate(self, design, reports):

        issues = []

        if design["zoning"]["valid"] is False:
            issues.append("Zoning violation")

        if design.get("structure", {}).get("stress") == "high":
            issues.append("Structural risk")

        return {
            "approved": len(issues) == 0,
            "issues": issues
        }

    # ======================
    # CONTEXT BUILDER
    # ======================
    def _init_context(self, state):

        return {
            "site": state,
            "mode": "multi_agent"
        }

    # ======================
    # REFINEMENT LOOP
    # ======================
    def _refine_context(self, context, validation):

        context["fix_mode"] = True
        context["issues"] = validation["issues"]

        return context