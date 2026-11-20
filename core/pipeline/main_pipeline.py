class MainPipeline:


    def __init__(self, engines):

        self.engines = engines



    def run(self, state):


        pipeline_order = [

            "design",

            "spatial",

            "geometry",

            "structure",

            "bim",

            "facade",

            "roof",

            "materials",

            "lighting",

            "interior",

            "visualization",

            "analysis"

        ]



        for engine_name in pipeline_order:


            engine = self.engines.get(
                engine_name
            )


            if engine is None:

                continue



            if hasattr(engine, "execute"):

                state = engine.execute(
                    state
                )


            elif hasattr(engine, "generate"):

                state = engine.generate(
                    state
                )


            elif hasattr(engine, "build"):

                state = engine.build(
                    state
                )


            elif hasattr(engine, "run"):

                state = engine.run(
                    state
                )


            elif hasattr(engine, "analyze"):

                state = engine.analyze(
                    state
                )


            elif hasattr(engine, "optimize"):

                state = engine.optimize(
                    state
                )



        return state