# ==========================================================
# ArchitectOS GOD CORE Brain v21.7
# Multi Agent Design Intelligence Runtime
# Memory Context Bridge
# Compatible with v21.6 Pipeline
# ==========================================================


from core.registry.engine_registry import EngineRegistry
from core.reasoning.reasoning_context_builder import reasoning_context_builder
from core.ai.program_intent_bridge import ProgramIntentBridge



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



        # ==================================================
        # TOOL REGISTRY BRIDGE
        # ==================================================

        self.tools = None



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
        # ARCHITECTURAL INTELLIGENCE CHAIN
        # ==================================================

        self.reasoning_engine = self._get(
            "ReasoningEngine"
        )()



        self.decision_adapter = self._get(
            "DecisionAdapter"
        )()



        self.execution_bridge = self._get(
            "DesignExecutionBridge"
        )()



        # ==================================================
        # ARCHITECTURAL INTENT ENGINE
        # ==================================================

        self.architectural_intent_engine = self._get(
            "ArchitecturalIntent"
        )()



        self.program_intent_bridge = (
            ProgramIntentBridge()
        )



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



        # ==================================================
        # IMPORTANT FIX
        # ==================================================
        # جلوگیری از خطای:
            # Brain object has no attribute design_result
        #
        # از این به بعد فقط current_result
        # به عنوان state داخلی استفاده می‌شود.

        self.current_result = {}



        print(
            "🚀 GOD CORE v21.7 MEMORY CONTEXT BRIDGE ACTIVE"
        )

    # ==========================================
    # EVOLUTION BRIDGE
    # ==========================================

    def attach_evolution(
        self,
        evolution=None
    ):

        self.evolution = evolution

        print(
            "🧬 Brain Evolution Bridge ATTACHED"
        )

        return True


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
        # ARCHITECTURAL INTENT EXTRACTION
        # SINGLE SOURCE
        # ==================================================

        architectural_intent = {}



        try:


            if hasattr(
                self,
                "architectural_intent_engine"
            ):


                result = (
                    self.architectural_intent_engine.extract(
                        {
                            "prompt":
                                input_text
                        }
                    )
                )


                if isinstance(
                    result,
                    dict
                ):

                    architectural_intent = result



                print(
                    "🏛️ FINAL ARCHITECTURAL INTENT:",
                    architectural_intent
                )



        except Exception as e:


            print(
                "❌ ARCH INTENT ERROR:",
                e
            )




        runtime_context[
            "architectural_intent"
        ] = architectural_intent



        context[
            "architectural_intent"
        ] = architectural_intent




        # ==================================================
        # BUILDING PROGRAM INTELLIGENCE
        # ==================================================

        try:


            if hasattr(
                self,
                "program_intent_bridge"
            ):


                program_result = (
                    self.program_intent_bridge.build(
                        architectural_intent
                    )
                )



                if isinstance(
                    program_result,
                    dict
                ):


                    architectural_intent[
                        "building_program"
                    ] = program_result.get(
                        "building_program",
                        {}
                    )



                    architectural_intent[
                        "program_analysis"
                    ] = program_result



                print(
                    "🏢 BUILDING PROGRAM GENERATED:",
                    architectural_intent.get(
                        "building_program"
                    )
                )



        except Exception as e:


            print(
                "❌ PROGRAM GENERATION ERROR:",
                e
            )




        # ==================================================
        # ROUTING
        # ==================================================

        if (
            context.get("operation")
            ==
            "design_update"
        ):


            route_result = {


                "intent":

                    "design",


                "mode":

                    "update"


            }


        else:


            route_result = self.router.route(


                input_text,


                image=context.get(
                    "image"
                ),


                context=context


            )




        # ==================================================
        # ROUTE NORMALIZATION
        # ==================================================

        if not isinstance(
            route_result,
            dict
        ):


            route_result = {



                "intent":

                    "chat"



            }



        intent = route_result.get(

            "intent",

            "chat"

        )



        mode = route_result.get(

            "mode",

            None

        )




        # ==================================================
        # FILE EXPORT DETECTION
        # ==================================================

        export_words = [


            "export",
            "convert",
            "save as",

            "dwg",
            "dxf",
            "ifc",
            "rvt",
            "revit",
            "autocad",
            "cad",


            "خروجی",
            "تبدیل",
            "ذخیره",
            "اکسپورت"

        ]



        if any(


            word in input_text.lower()


            for word in export_words


        ):


            intent = "file_export"



            route_result[
                "intent"
            ] = intent



            print(
                "📐 FILE EXPORT INTENT DETECTED:",
                intent
            )




        # ==================================================
        # INTENT NORMALIZATION
        # ==================================================

        if intent == "image":


            if mode == "generate":


                intent = "image_generation"



            elif mode == "edit":


                intent = "image_edit"




        elif intent == "design":


            if mode == "create":


                intent = "design_create"



            elif mode == "update":


                intent = "design_update"



            elif mode == "recall":


                intent = "design_recall"




        # ==================================================
        # SAVE NORMALIZED STATE
        # ==================================================

        runtime_context[
            "intent"
        ] = intent


        runtime_context[
            "mode"
        ] = mode



        print(
            "🧠 NORMALIZED INTENT:",
            intent,
            mode
        )
        # ==================================================
        # DESIGN ROUTE GUARD
        # ==================================================

        if intent not in [

            "design_create",

            "design_update",

            "design_recall",

            "project_export",

        ]:


            return {


                "type":

                    "chat",



                "engine":

                    "brain",



                # CHAT RUNTIME REGRESSION FIX
                #
                # This obsolete fallback called self._chat_response(), a
                # method that has NEVER existed on Brain (Brain defines
                # only __init__, attach_evolution and run). Reaching the
                # branch therefore raised:
                #
                #   AttributeError: 'Brain' object has no attribute
                #   '_chat_response'
                #
                # Brain owns NO chat-response contract, so the method is
                # deliberately NOT restored. The obsolete fallback now
                # returns the same envelope with no content and says so
                # explicitly, and the existing ChatArchitect response
                # path handles the turn.
                "result": "",

                "brain_chat_response_available": False,



                "status":

                    "GENERAL_CHAT_FALLBACK"


            }





        # ==================================================
        # DESIGN PLANNING
        # ARCHITECTURAL INTENT INJECTION
        # ==================================================

        try:



            planner_context = {



                "input":

                    input_text,



                "memory_context":

                    context,



                "architectural_intent":

                    architectural_intent,



                "runtime_context":

                    runtime_context



            }





            print(
                "\n🔥 BRAIN CONTEXT BEFORE PLANNER:"
            )

            print(
                planner_context
            )



            print(
                "TEST ARCH INTENT BEFORE PLANNER:",
                planner_context.get(
                    "architectural_intent"
                )
            )



            print(
                "PLANNER CONTEXT KEYS:",
                planner_context.keys()
            )



            print(
                "PLANNER CONTEXT SIZE:",
                len(
                    str(
                        planner_context
                    )
                )
            )




            # ==========================================
            # IMPORTANT
            # Planner receives normalized context
            # ==========================================

            plan = self.planner.plan(


                input_text,


                intent,


                planner_context



            )



            if not isinstance(
                plan,
                dict
            ):


                plan = {}



            print(
                "🔥 FINAL PLAN KEYS:",
                plan.keys()
            )



            print(
                "🔥 FINAL PLAN SIZE:",
                len(
                    str(
                        plan
                    )
                )
            )



            print(
                "🧪 PLAN ARCH INTENT:",
                plan.get(
                    "architectural_intent"
                )
            )




            # ==================================================
            # ARCH INTENT MERGE
            # SINGLE SOURCE OF TRUTH
            # ==================================================


            planner_intent = plan.get(

                "architectural_intent",

                {}

            )



            if not isinstance(

                planner_intent,

                dict

            ):


                planner_intent = {}




            merged_architectural_intent = {


                **architectural_intent,


                **planner_intent


            }



            plan[
                "architectural_intent"
            ] = merged_architectural_intent



            print(

                "🚨 PLAN AFTER CONTEXT MERGE:",

                plan[
                    "architectural_intent"
                ]

            )



            plan[
                "runtime_context"
            ] = runtime_context





        except Exception as e:


            print(

                "PLANNER ERROR:",

                e

            )



            plan = {



                "intent":

                    intent,



                "building_type":

                    architectural_intent.get(

                        "building_type",

                        "generic"

                    ),



                "floors":

                    1,



                "style":

                    architectural_intent.get(

                        "style",

                        "balanced"

                    ),



                "spaces":

                    {}

            }






        # ==================================================
        # FINAL PLAN NORMALIZATION
        # ==================================================

        if not isinstance(
            plan,
            dict
        ):


            plan = {}



        plan.setdefault(

            "architectural_intent",

            architectural_intent

        )



        plan.setdefault(

            "runtime_context",

            runtime_context

        )



        print(

            "🔥 NORMALIZED PLAN READY FOR DESIGN AGENTS"

        )


        print(

            "PLAN INTENT:",

            plan.get(
                "architectural_intent"
            )

        )
        # ==================================================
        # DESIGN GENERATION
        # ==================================================

        designs = {}



        # ==================================================
        # DESIGN UPDATE MODE
        # ==================================================

        if (

            context.get("operation")

            ==

            "design_update"



            and



            isinstance(

                context.get(

                    "previous_design"

                ),

                dict

            )

        ):


            previous = context.get(

                "previous_design"

            )



            designs["previous_design"] = copy.deepcopy(

                previous

            )



        else:



            # =============================================
            # MULTI AGENT DESIGN GENERATION
            # =============================================


            for name, agent in self.agents.items():



                try:



                    agent_input = {



                        **plan,



                        "architectural_intent":

                            plan.get(

                                "architectural_intent",

                                {}

                            ),



                        "spaces":

                            plan.get(

                                "spaces",

                                {}

                            ),



                        "building_program":

                            plan.get(

                                "architectural_intent",

                                {}

                            ).get(

                                "building_program",

                                {}

                            )

                    }





                    print(

                        "\n🔥 DESIGN AGENT INPUT:",

                        name

                    )



                    print(

                        "SIZE:",

                        len(

                            str(

                                agent_input

                            )

                        )

                    )



                    print(

                        "ARCH INT:",

                        agent_input.get(

                            "architectural_intent"

                        )

                    )



                    print(
                        "🔥 DESIGN AGENT INPUT SPACES:",
                        agent_input.get("spaces")
                    )

                    print(
                        "🔥 DESIGN AGENT INPUT FLOORS:",
                        agent_input.get("floors")
                    )





                    design_result = agent.build(

                        agent_input

                    )



                    if isinstance(

                        design_result,

                        dict

                    ):


                        designs[name] = design_result



                    print(

                        "✅ AGENT RESULT:",

                        name,

                        design_result.keys()

                        if isinstance(

                            design_result,

                            dict

                        )

                        else type(design_result)

                    )


                    print(

                        "🔥 DESIGN LEVELS:",

                        list(design_result.keys())

                        if isinstance(

                            design_result,

                            dict

                        )

                        else "NOT_DICT"

                    )



                    print(

                        "🔥 F1 SAMPLE:",

                        design_result.get("F1")

                        if isinstance(

                            design_result,

                            dict

                        )

                        else None

                    )



                    print(

                        "🔥 F2 SAMPLE:",

                        design_result.get("F2")

                        if isinstance(

                            design_result,

                            dict

                        )

                        else None

                    )





                except Exception as e:



                    print(

                        f"❌ DESIGN AGENT {name} ERROR:",

                        e

                    )







        # ==================================================
        # FALLBACK CHECK
        # ==================================================

        if not designs:



            return {



                "status":

                    "FAILED_NO_DESIGN",



                "reason":

                    "All DesignAgents failed"



            }







        # ==================================================
        # VALIDATION + SCORE
        # ==================================================

        scored = {}



        for name, design in designs.items():



            try:



                validation_target = design





                # ------------------------------------------
                # LIST NORMALIZATION
                # ------------------------------------------

                if isinstance(

                    validation_target,

                    list

                ):



                    validation_target = {


                        "nodes": {


                            f"node_{i}":

                                item


                            for i,item in enumerate(

                                validation_target

                            )


                        },


                        "connections":

                            []

                    }





                # ------------------------------------------
                # SIMPLE DICTIONARY NORMALIZATION
                # ------------------------------------------

                elif (

                    isinstance(

                        validation_target,

                        dict

                    )

                    and

                    "nodes"

                    not

                    in

                    validation_target

                ):



                    if "F1" in validation_target:



                        validation_target = {


                            "nodes":

                                validation_target["F1"],



                            "connections":

                                []

                        }



                    else:



                        validation_target = {


                            "nodes":

                                validation_target,



                            "connections":

                                []

                        }





                validation = self.validator.validate(

                    validation_target

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



                print(

                    "🏆 SCORE:",

                    name,

                    score

                )





            except Exception as e:



                print(

                    "VALIDATION ERROR:",

                    name,

                    e

                )



                scored[name] = {



                    "design":

                        design,



                    "score":

                        0



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


        print(
            "🔥 BEST DESIGN LEVELS:",
            best_design.keys()
            if isinstance(best_design, dict)
            else type(best_design)
        )


        print(
            "🔥 BEST DESIGN F1:",
            best_design.get("F1")
            if isinstance(best_design, dict)
            else None
        )


        print(
            "🔥 BEST DESIGN F2:",
            best_design.get("F2")
            if isinstance(best_design, dict)
            else None
        )





        print(

            "\n====== BEST DESIGN SELECTED ======"

        )


        print(

            "AGENT:",

            best

        )


        print(

            "KEYS:",

            best_design.keys()

            if isinstance(

                best_design,

                dict

            )

            else type(best_design)

        )


        print(

            "ARCH INT:",
            best_design.get(

                "metadata",

                {}

            ).get(

                "architectural_intent",

                {}

            )

            if isinstance(

                best_design,

                dict

            )

            else None

        )
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



        print(
            "🧠 REASONING COMPLETE"
        )




        critic_report = self.critic.evaluate(

            reasoning,

            best_design

        )



        print(
            "🧐 CRITIC COMPLETE"
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
        # PRE EXECUTION SPATIAL GENERATION
        # ==================================================

        print(
            "\n====== BEST DESIGN BEFORE SPATIAL ======"
        )

        print(
            "TYPE:",
            type(best_design)
        )

        if isinstance(best_design, dict):

            print(
                "KEYS:",
                best_design.keys()
            )

            for _floor, _data in best_design.items():

                print(
                    "FLOOR:",
                    _floor,
                    "TYPE:",
                    type(_data)
                )

                if isinstance(_data, dict):

                    print(
                        "FLOOR KEYS:",
                        _data.keys()
                    )

                    print(
                        "NODES COUNT:",
                        len(
                            _data.get(
                                "nodes",
                                {}
                            )
                        )
                        if isinstance(
                            _data.get(
                                "nodes",
                                {}
                            ),
                            dict
                        )
                        else "N/A"
                    )

        try:


            execution_spatial = self.spatial.generate(

                best_design,

                plan,

                architectural_intent

            )


        except Exception as e:


            print(

                "❌ PRE EXECUTION SPATIAL ERROR:",

                e

            )


            execution_spatial = {}




        print(

            "\n====== PRE EXECUTION SPATIAL ======"

        )


        print(

            execution_spatial

        )




        # ==================================================
        # ARCHITECTURAL REASONING ENGINE
        # ==================================================

        architectural_reasoning = None

        execution_bridge_result = None



        try:



            reasoning_context = reasoning_context_builder.build(

                best_design,

                plan,

                input_text

            )




            architectural_reasoning = self.reasoning_engine.process(

                reasoning_context

            )



            print(

                "🤖 ARCHITECTURAL REASONING RESULT:",

                architectural_reasoning

            )




            execution_actions = self.decision_adapter.convert(

                architectural_reasoning.get(

                    "recommendations",

                    []

                )

            )




            # ==================================================
            # BUILD EXECUTION CONTRACT
            # ==================================================


            execution_design = {


                "plan":

                    best_design,



                "spatial":

                    execution_spatial,



                "architectural_intent":

                    architectural_intent,



                "geometry":

                    {}

            }





            print(

                "\n====== BUILD EXECUTION DESIGN CONTRACT ======"

            )


            print(

                "keys:",

                execution_design.keys()

            )


            print(

                "spatial:",

                execution_design.get(

                    "spatial"

                )

            )


            print(

                "geometry:",

                execution_design.get(

                    "geometry"

                )

            )




            execution_bridge_result = self.execution_bridge.process(

                execution_design,

                execution_actions

            )


            print(
                "🔥 EXECUTION BRIDGE TYPE:",
                type(execution_bridge_result)
            )


            if isinstance(execution_bridge_result, dict):

                print(
                    "🔥 EXECUTION BRIDGE KEYS:",
                    execution_bridge_result.keys()
                )


                print(
                    "🔥 EXECUTION BRIDGE GEOMETRY:",
                    execution_bridge_result.get("geometry")
                )


                print(
                    "🔥 EXECUTION DESIGN:",
                    execution_bridge_result.get("design")
                )


                print(
                    "🔥 EXECUTION BIM RESULT:",
                    execution_bridge_result.get("bim_result")
                )




            print(

                "🔧 EXECUTION BRIDGE RESULT:",

                execution_bridge_result

            )




        except Exception as e:



            print(

                "⚠️ ARCHITECTURAL REASONING BRIDGE ERROR:",

                e

            )
        # ==================================================
        # SPATIAL OPTIMIZATION
        # ==================================================

        optimized = self.spatial_optimizer.optimize(

            best_design,

            execution_spatial,

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



        try:

            recent_memory = self.memory.recent()

        except Exception:

            recent_memory = []



        mutated = self.mutator.mutate(

            best_design,

            input_text,

            recent_memory

        )



        # ==================================================
        # KEEP DESIGN STRUCTURE
        # ==================================================

        #
        # Mutator فقط اجازه دارد مقادیر را تغییر دهد
        # نه اینکه Floor ها را حذف کند.
        #

        if isinstance(best_design, dict):

            for key, value in best_design.items():

                if key not in mutated:

                    mutated[key] = value



        #
        # اگر ROOF یا SITE حذف شده باشند
        #

        for fixed in [

            "ROOF",

            "SITE",

            "metadata"

        ]:

            if fixed in best_design:

                mutated.setdefault(

                    fixed,

                    best_design[fixed]

                )



        print(

            "\n====== DESIGN AFTER MUTATOR ======"

        )

        print(

            mutated.keys()

        )



        # ==================================================
        # REMOVE REASONING FOR SPATIAL
        # ==================================================

        design_core = {

            k: v

            for k, v in mutated.items()

            if k != "reasoning"

        }


        # ==================================================
        # SPATIAL GENERATION DEBUG INPUT
        # ==================================================

        print(
            "🔥 INPUT TO SPATIAL LEVELS:",
            design.keys()
            if isinstance(design, dict)
            else type(design)
        )


        print(
            "🔥 INPUT TO SPATIAL F1:",
            design.get("F1")
        )


        print(
            "🔥 INPUT TO SPATIAL F2:",
            design.get("F2")
        )


        print(
            "🔥 BEFORE SPATIAL ARCH INTENT:",
            architectural_intent.keys()
            if isinstance(architectural_intent, dict)
            else architectural_intent
        )

        print(
            "🔥 BEFORE SPATIAL PLAN KEYS:",
            plan.keys()
            if isinstance(plan, dict)
            else type(plan)
        )



        # ==================================================
        # SPATIAL GENERATION
        # ==================================================

        print(
            "====== SECOND SPATIAL INPUT ======"
        )

        print(
            type(design)
        )

        if isinstance(design, dict):

            print(
                design.keys()
            )

            print(
                "SECOND F1:",
                design.get("F1")
            )
 
            print(
                "SECOND F2:",
                design.get("F2")
            )


        print("\n====== FINAL ARCH INTENT BEFORE SPATIAL ======")

        print(
            architectural_intent.get(
                "building_program"
            )
        )

        print(
            "PLAN SPACES:",
            plan.get("spaces")
        )

        print(
            "PLAN LEVELS:",
            plan.get("levels")
        )

        print("============================================")


        spatial = self.spatial.generate(
            design,
            plan,
            architectural_intent
        )


        print(
            "🔥 IMMEDIATE SPATIAL RETURN F2:",
            spatial.get("floors", {}).get("F2")
        )


        print(
            "🔥 SPATIAL OUTPUT TYPE:",
            type(spatial)
        )


        if isinstance(spatial, dict):


            print(
                "🔥 SPATIAL OUTPUT KEYS:",
                spatial.keys()
            )


            print(
                "🔥 SPATIAL FLOORS:",
                spatial.get("floors")
            )


            if isinstance(
                spatial.get("floors"),
                dict
            ):

                print(
                    "🔥 SPATIAL FLOOR KEYS:",
                    spatial["floors"].keys()
                )


                print(
                    "🔥 SPATIAL F1:",
                    spatial["floors"].get("F1")
                )


                print(
                    "🔥 SPATIAL F2:",
                    spatial["floors"].get("F2")
                )


        print(

            "\n====== SPATIAL GENERATED ======"

        )

        print(

            spatial

        )



        # ==================================================
        # ZONING
        # ==================================================

        zoning = self.zoning.generate(

            spatial,

            plan

        )


        print(
            "🔥 AFTER ZONING ZONES:",
            zoning.get("zones")
            if isinstance(zoning, dict)
            else type(zoning)
        )


        print(
            "\n====== ZONING OUTPUT ======"
        )

        print(
            zoning
        )

        print(
            "ZONING FLOORS:",
            zoning.get("floors")
        )

        print(
            "ZONING ZONES:",
            zoning.get("zones")
        )



        # ==================================================
        # ADJACENCY
        # ==================================================

        adjacency = self.adjacency.generate(

            zoning,

            plan

        )


        print(
            "🔥 AFTER ADJACENCY:",
            adjacency
        )



        # ==================================================
        # CONSTRAINT SOLVER
        # ==================================================

        constraints = self.constraint_solver.solve(

            zoning,

            plan

        )


        print(
            "\n====== CONSTRAINT OUTPUT ======"
        )

        print(
            constraints
        )



        print(

            "\n====== CONSTRAINTS ======"

        )

        print(

            constraints

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


                "spatial":

                    spatial,


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
        # FINAL ARCHITECTURAL INTENT
        # SINGLE SOURCE OF TRUTH
        # ==================================================

        final_architectural_intent = {}

        print("\n====== FINAL ARCH INTENT BUILD DEBUG ======")
        print("CURRENT architectural_intent:")
        print(architectural_intent)

        print("PLAN SPACES:")
        print(plan.get("spaces") if isinstance(plan, dict) else None)

        print("PLAN LEVELS:")
        print(plan.get("levels") if isinstance(plan, dict) else None)

        print("==========================================")



        if isinstance(

            architectural_intent,

            dict

        ):

            final_architectural_intent = (

                architectural_intent.copy()

            )



        else:

            final_architectural_intent = {}





        if not final_architectural_intent:


            try:


                final_architectural_intent = (

                    self.architectural_intent_engine.extract(

                        {

                            "prompt":

                                input_text

                        }

                    )

                )


            except Exception as e:


                print(

                    "❌ FINAL ARCH INT ERROR:",

                    e

                )



                final_architectural_intent = {}





        print(

            "🔥 FINAL ARCH INTENT:",

            final_architectural_intent

        )





        # ==================================================
        # BUILDING PROGRAM
        # ==================================================

        if intent in [

            "design_create",

            "design_update"

        ]:


            try:


                if hasattr(

                    self,

                    "program_intent_bridge"

                ):

                    print(
                        "🔥 SECOND PROGRAM BRIDGE INPUT:",
                        final_architectural_intent
                    )


                    program_result = (

                        self.program_intent_bridge.build(

                            final_architectural_intent

                        )

                    )


                    print(
                        "🔥 SECOND PROGRAM RESULT:",
                        program_result
                    )



                    final_architectural_intent[

                        "building_program"

                    ] = program_result.get(

                        "building_program",

                        {}

                    )



                    final_architectural_intent[

                        "program_analysis"

                    ] = program_result



                    print(

                        "🏢 BUILDING PROGRAM GENERATED:",

                        final_architectural_intent.get(

                            "building_program"

                        )

                    )



            except Exception as e:


                print(

                    "❌ PROGRAM BRIDGE ERROR:",

                    e

                )





        # ==================================================
        # FINAL GEOMETRY CONTRACT
        # ==================================================

        final_geometry = {}



        if isinstance(

            execution_bridge_result,

            dict

        ):


            bridge_design = execution_bridge_result.get(

                "design",

                {}

            )


            if isinstance(

                bridge_design,

                dict

            ):


                print(
                    "🔥 BRIDGE DESIGN KEYS:",
                    bridge_design.keys()
                )


                print(
                    "🔥 BRIDGE DESIGN GEOMETRY:",
                    bridge_design.get("geometry")
                )


                final_geometry = bridge_design.get(

                    "geometry",

                    {}

                )





        print(

            "🏗 FINAL GEOMETRY BEFORE RETURN:",

            final_geometry

        )


        print(
            "🔥 FINAL OUTPUT GEOMETRY CHECK:",
            {
                "rooms":
                    len(final_geometry.get("rooms", []))
                    if isinstance(final_geometry, dict)
                    else None,

                "floors":
                    len(final_geometry.get("floors", []))
                    if isinstance(final_geometry, dict)
                    else None,

                "walls":
                    len(final_geometry.get("walls", []))
                    if isinstance(final_geometry, dict)
                    else None,

                "windows":
                    len(final_geometry.get("windows", []))
                    if isinstance(final_geometry, dict)
                    else None
            }
        )





        # ==================================================
        # RENDER CONTRACT
        # ==================================================

        render_contract = {


            "prompt":

                input_text,



            "architectural_intent":

                final_architectural_intent,



            "design":

                mutated,



            "spatial":

                spatial,



            "geometry":

                final_geometry,



            "plan":

                plan,



            "source":

                "GOD_CORE_V21.7"

        }
        # ==================================================
        # COMPILE + EXECUTE
        # ==================================================

        print(
            "🔥 MUTATED KEYS BEFORE COMPILE:",
            mutated.keys()
            if isinstance(mutated, dict)
            else type(mutated)
        )


        print(
            "🔥 MUTATED SAMPLE BEFORE COMPILE:",
            mutated
        )


        print(
            "🔥 MUTATED F1:",
            mutated.get("F1")
        )


        print(
            "🔥 MUTATED F2:",
            mutated.get("F2")
        )


        graph = self.compiler.compile(

            mutated

        )


        print(
            "🔥 COMPILE GRAPH TYPE:",
            type(graph)
        )


        if isinstance(graph, dict):

            print(
                "🔥 COMPILE GRAPH KEYS:",
                graph.keys()
            )


            print(
                "🔥 COMPILE GRAPH GEOMETRY:",
                graph.get("geometry")
            )



        execution = self.executor.execute(

            graph

        )





        # ==================================================
        # FINAL GEOMETRY EXTRACTION
        # ==================================================

        final_geometry = {}



        if isinstance(

            execution_bridge_result,

            dict

        ):


            bridge_design = execution_bridge_result.get(

                "design",

                {}

            )


            if isinstance(

                bridge_design,

                dict

            ):


                final_geometry = bridge_design.get(

                    "geometry",

                    {}

                )



        print(

            "🏗 FINAL RESULT GEOMETRY:",

            final_geometry

        )





        # ==================================================
        # FINAL OUTPUT
        # ==================================================

        final_result = {


            "type":

                "design",



            "engine":

                "GOD_CORE",



            "result":

                mutated,



            "intent":

                intent,



            "plan":

                plan,



            "selected_agent":

                best,



            "render_contract":

                render_contract,



            # ==========================
            # SPATIAL CONTRACT
            # ==========================

            "spatial":

                spatial,



            "geometry":

                final_geometry,



            "zoning":

                zoning,



            "adjacency":

                adjacency,



            # ==========================
            # DESIGN DATA
            # ==========================

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



            # ==========================
            # INTELLIGENCE
            # ==========================

            "analysis":

                report,



            "memory_context":

                context,



            "architectural_reasoning":

                architectural_reasoning,



            "execution_bridge":

                execution_bridge_result,



            "architectural_intent":

                final_architectural_intent,



            "status":

                "GOD_CORE_V21.7_MEMORY_CONTEXT_BRIDGE"

        }





        # ==================================================
        # FINAL STATE MEMORY
        # ==================================================

        self.current_result = final_result



        print(
            "\n========== FINAL DESIGN RESULT =========="
        )


        print(
            "keys:",
            final_result.keys()
        )


        print(
            "spatial:",
            final_result.get(
                "spatial"
            )
        )


        print(
            "geometry:",
            final_result.get(
                "geometry"
            )
        )


        print(
            "execution bridge:",
            bool(
                final_result.get(
                    "execution_bridge"
                )
            )
        )



        return final_result
