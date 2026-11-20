from core.environment.lighting_environment_engine import LightingEnvironmentEngine



class LightingAdapter:


    def __init__(self):

        self.engine = LightingEnvironmentEngine()



    def analyze(self, state):


        lighting_config = state.get(

            "lighting",

            {}

        )


        objects = []



        facade_result = state.get(

            "facade_result",

            {}

        )


        for opening in facade_result.get(

            "openings",

            []

        ):

            objects.append(

                {

                    "type":

                    "window_void"

                }

            )



        roof_result = state.get(

            "roof_result",

            {}

        )


        roof = roof_result.get(

            "roof",

            {}

        )


        if roof.get(

            "green_roof",

            False

        ):

            objects.append(

                {

                    "type":

                    "roof_surface"

                }

            )



        scene = {


            "scene":

            {

                "objects":

                objects

            }

        }



        result = self.engine.analyze(

            scene,

            lighting_config

        )


        state["lighting_result"] = result


        return state