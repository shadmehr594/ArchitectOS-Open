import time



class MasterArchitectPipeline:


    def __init__(
        self,
        engines,
        decision_adapter=None
    ):

        self.engines = engines

        self.decision_adapter = decision_adapter


        self.pipeline_order = [

            "design",
            "planning",

            "facade",
            "geometry",
            "roof",
            "materials",
            "landscape",

            "interior",
            "furniture",

            "lighting",
            "camera",

            "visualization",

            "scene_builder",
            "scene_export",

            "bim",

            "intelligence"

        ]


        print(
            "🏛️ Master Architect Pipeline v2 ACTIVE"
        )



    # ==================================================
    # RUN PIPELINE
    # ==================================================

    def run(
        self,
        project
    ):


        state = project


        pipeline_report = []



        # ==============================================
        # DECISION INJECTION
        # ==============================================

        state = self.inject_decisions(
            state
        )



        for stage_name in self.pipeline_order:



            engine = self.engines.get(
                stage_name
            )


            if engine is None:

                continue



            print(
                f"▶️ PIPELINE STAGE: {stage_name}"
            )



            previous_state = state


            start_time = time.time()


            status = "success"



            try:


                stage_result = self._execute_engine(
                    engine,
                    state
                )



                if stage_result is None:


                    state = previous_state

                    status = "warning"



                elif isinstance(
                    stage_result,
                    dict
                ):


                    state[stage_name] = stage_result



                    # ==================================
                    # BIM PROMOTION
                    # ==================================

                    if stage_name == "bim":


                        if "structure" in stage_result:

                            state["structure"] = (
                                stage_result["structure"]
                            )


                        if "bim" in stage_result:

                            state["bim"] = (
                                stage_result["bim"]
                            )



                    # ==================================
                    # BIM ELEMENTS
                    # ==================================

                    if "bim_elements" in stage_result:


                        state["bim_elements"] = (
                            stage_result["bim_elements"]
                        )


                    elif "elements" in stage_result:


                        state["bim_elements"] = (
                            stage_result["elements"]
                        )



                    # ==================================
                    # INTELLIGENCE
                    # ==================================

                    if stage_name == "intelligence":


                        state["intelligence"] = stage_result



                else:


                    state = stage_result



            except Exception as error:


                print(
                    f"❌ PIPELINE ERROR [{stage_name}] : {error}"
                )


                state = previous_state


                status = "failed"





            duration = round(
                time.time() - start_time,
                4
            )



            pipeline_report.append(

                {

                    "stage":
                    stage_name,

                    "status":
                    status,

                    "time":
                    duration

                }

            )




        state["pipeline_report"] = pipeline_report


        state["pipeline_status"] = {

            "completed":
            True,

            "stages":
            len(
                pipeline_report
            )

        }



        return state





    # ==================================================
    # DECISION INJECTION LAYER
    # ==================================================

    def inject_decisions(
        self,
        state
    ):


        if not isinstance(
            state,
            dict
        ):

            return state



        decisions = state.get(
            "decisions",
            []
        )



        if not decisions:

            return state



        state["execution_actions"] = decisions



        print(
            f"🧠 Injected Decisions: {len(decisions)}"
        )



        return state





    # ==================================================
    # ENGINE EXECUTOR
    # ==================================================

    def _execute_engine(
        self,
        engine,
        state
    ):



        if hasattr(engine, "execute"):

            return engine.execute(
                state
            )



        elif hasattr(engine, "generate"):

            return engine.generate(
                state
            )



        elif hasattr(engine, "apply"):

            return engine.apply(
                state
            )



        elif hasattr(engine, "build"):

            return engine.build(
                state
            )



        elif hasattr(engine, "process"):

            return engine.process(
                state
            )



        elif hasattr(engine, "analyze"):

            return engine.analyze(
                state
            )



        elif hasattr(engine, "optimize"):

            return engine.optimize(
                state
            )



        elif hasattr(engine, "run"):

            return engine.run(
                state
            )



        else:


            print(
                "⚠️ Unknown Engine Interface"
            )


            return state