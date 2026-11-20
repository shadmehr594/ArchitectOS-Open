# ==========================================================
# ArchitectOS GOD CORE Brain v21.7
# Multi Agent Design Intelligence Runtime
# Memory Context Bridge
# Compatible with v21.6 Pipeline
# ==========================================================


from core.registry.engine_registry import EngineRegistry



class Brain:


    VERSION = "v21.7"



    def __init__(
        self,
        registry=None
    ):


        # ==================================================
        # REGISTRY INITIALIZATION
        # ==================================================

        if registry is None:

            registry = EngineRegistry()



        self.registry = (
            registry.auto_discover()
        )



        def get(name):

            if name not in self.registry:

                raise Exception(
                    f"Missing registry key: {name}"
                )

            return self.registry[name]



        self._get = get



        # ==================================================
        # CORE ROUTING
        # ==================================================

        self.router = self._get(
            "IntentRouter"
        )()



        self.planner = self._get(
            "PlannerAgent"
        )()



        # ==================================================
        # DESIGN AGENTS
        # ==================================================

        self.agents = {


            "A":

                self._get(
                    "DesignAgent"
                )(
                    style="efficient"
                ),



            "B":

                self._get(
                    "DesignAgent"
                )(
                    style="creative"
                ),



            "C":

                self._get(
                    "DesignAgent"
                )(
                    style="minimal"
                )

        }



        # ==================================================
        # VALIDATION SYSTEM
        # ==================================================

        self.validator = self._get(
            "BIMValidator"
        )()



        self.constraint = self._get(
            "ConstraintAgent"
        )()



        self.repair = self._get(
            "RepairAgent"
        )()



        # ==================================================
        # COMPILER / EXECUTION
        # ==================================================

        self.compiler = self._get(
            "BIMCompiler"
        )()



        self.executor = self._get(
            "Executor"
        )()



        # ==================================================
        # MEMORY + EVOLUTION
        # ==================================================

        self.scorer = self._get(
            "DesignScorer"
        )()



        self.memory = self._get(
            "DesignMemory"
        )()



        self.mutator = self._get(
            "Mutator"
        )()



        # ==================================================
        # SPATIAL INTELLIGENCE
        # ==================================================

        self.spatial = self._get(
            "SpatialLayoutEngine"
        )()



        self.zoning = self._get(
            "ZoningSpatialEngine"
        )()



        self.adjacency = self._get(
            "AdjacencyEngine"
        )()



        self.constraint_solver = self._get(
            "ArchitecturalConstraintSolver"
        )()



        # ==================================================
        # REASONING SYSTEM
        # ==================================================

        self.reasoner = self._get(
            "DesignReasoner"
        )()



        self.critic = self._get(
            "AdaptiveCritic"
        )()



        self.improvement = self._get(
            "ImprovementGenerator"
        )()



        self.improvement_executor = self._get(
            "ImprovementExecutor"
        )()



        self.spatial_optimizer = self._get(
            "SpatialOptimizationMutator"
        )()



        # ==================================================
        # SELF INTELLIGENCE
        # ==================================================

        self.analyzer = self._get(
            "SelfAnalyzer"
        )()



        self.rewriter = self._get(
            "SelfRewriter"
        )()



        self.evolution = None



        print(
            "🚀 GOD CORE v21.7 MEMORY CONTEXT BRIDGE ACTIVE"
        )
    # ======================================================
    # EVOLUTION CONNECTOR
    # ======================================================


    def attach_evolution(
        self,
        evolution_loop
    ):

        self.evolution = evolution_loop




    # ======================================================
    # MAIN EXECUTION PIPELINE
    # MEMORY CONTEXT ENABLED
    # ======================================================


    def run(
        self,
        input_text,
        context=None
    ):



        # ==================================================
        # CONTEXT NORMALIZATION
        # ==================================================

        if context is None:

            context = {}



        runtime_context = {


            "input":

                input_text,



            "memory_context":

                context


        }




        # ==================================================
        # ROUTING
        # ==================================================

        intent = self.router.route(

            input_text

        )



        plan = self.planner.plan(

            input_text,

            intent

        )



        # Attach runtime memory if plan supports it

        if isinstance(
            plan,
            dict
        ):


            plan["runtime_context"] = runtime_context




        print(

            "\n====== PLAN DEBUG ======"

        )


        print(plan)


        print(

            "========================\n"

        )





        # ==================================================
        # DESIGN GENERATION
        # ==================================================

        designs = {}



        for name, agent in self.agents.items():


            try:


                designs[name] = agent.build(

                    plan

                )


            except Exception as e:


                print(

                    f"❌ Agent {name} ERROR:",

                    e

                )





        if not designs:


            return {


                "status":

                    "FAILED_NO_DESIGN"


            }





        # ==================================================
        # VALIDATION + SCORE
        # ==================================================

        scored = {}



        for name, design in designs.items():


            validation = self.validator.validate(

                design

            )



            issues = self.constraint.check(

                design

            )



            score = self.scorer.score(

                design,

                validation,

                issues

            )



            scored[name] = {


                "design":

                    design,


                "score":

                    score


            }




        # ==================================================
        # SELECT BEST DESIGN
        # ==================================================

        best = max(

            scored,

            key=lambda x:

                scored[x]["score"]

        )



        best_design = scored[best]["design"]
        # ==================================================
        # REASONING LOOP
        # ==================================================

        reasoning = self.reasoner.analyze(

            {

                "plan":

                    plan,


                "design":

                    best_design,


                "constraints":

                    {},


                "context":

                    runtime_context

            }

        )




        critic_report = self.critic.evaluate(

            reasoning,

            best_design

        )




        improvement_plan = self.improvement.generate(

            critic_report,

            plan

        )




        improved = self.improvement_executor.apply(

            best_design,

            improvement_plan

        )



        if isinstance(

            improved,

            dict

        ):


            best_design = improved.get(

                "design",

                best_design

            )





        # ==================================================
        # SPATIAL OPTIMIZATION
        # ==================================================

        temp_spatial = self.spatial.generate(

            best_design,

            plan

        )



        optimized = self.spatial_optimizer.optimize(

            best_design,

            temp_spatial,

            {},

            plan

        )



        if isinstance(

            optimized,

            dict

        ):


            best_design = optimized.get(

                "design",

                best_design

            )





        # ==================================================
        # DESIGN MEMORY STORAGE
        # ==================================================

        self.memory.store(

            best_design,

            scored[best]["score"]

        )





        # ==================================================
        # MUTATION
        # ==================================================

        if isinstance(

            best_design,

            dict

        ):


            best_design["reasoning"] = reasoning





        recent_memory = []



        try:


            recent_memory = self.memory.recent()



        except Exception:


            pass





        mutated = self.mutator.mutate(

            best_design,

            recent_memory

        )





        design_core = {


            k:v


            for k,v in mutated.items()


            if k != "reasoning"


        }





        # ==================================================
        # SPATIAL ANALYSIS
        # ==================================================

        spatial = self.spatial.generate(

            design_core,

            plan

        )



        zoning = self.zoning.generate(

            spatial,

            plan

        )



        adjacency = self.adjacency.generate(

            zoning,

            plan

        )



        constraints = self.constraint_solver.solve(

            zoning,

            plan

        )





        # ==================================================
        # REPAIR LOOP
        # ==================================================

        if constraints.get(

            "violations"

        ):


            mutated = self.repair.repair(

                mutated,

                constraints,

                plan

            )
        # ==================================================
        # SELF ANALYSIS
        # ==================================================

        report = self.analyzer.analyze(

            brain=self,


            context={


                "input":

                    input_text,


                "memory_context":

                    context,


                "design":

                    mutated,


                "scores":

                    scored,


                "reasoning":

                    reasoning,


                "zoning":

                    zoning,


                "constraints":

                    constraints


            }

        )





        # ==================================================
        # EVOLUTION
        # ==================================================

        if self.evolution:


            self.evolution.tick(

                {


                    "input":

                        input_text,


                    "memory_context":

                        context,


                    "design":

                        mutated,


                    "report":

                        report


                }

            )





        # ==================================================
        # COMPILE + EXECUTE
        # ==================================================

        graph = self.compiler.compile(

            mutated

        )



        execution = self.executor.execute(

            graph

        )





        # ==================================================
        # FINAL OUTPUT
        # ==================================================

        return {


            "intent":

                intent,


            "plan":

                plan,


            "selected_agent":

                best,


            "spatial":

                spatial,


            "zoning":

                zoning,


            "adjacency":

                adjacency,


            "design":

                mutated,


            "reasoning":

                reasoning,


            "critic":

                critic_report,


            "improvements":

                improvement_plan,


            "constraints":

                constraints,


            "graph":

                graph,


            "execution":

                execution,


            "analysis":

                report,


            "memory_context":

                context,


            "status":

                "GOD_CORE_V21.7_MEMORY_CONTEXT_BRIDGE"

        }





    # ======================================================
    # CHAT COMPATIBILITY LAYER
    # ======================================================


    def think(

        self,

        message,

        domain=None

    ):


        return self.run(

            message

        )