from core.landscape.landscape_intelligence_engine import LandscapeIntelligenceEngine



class LandscapeAdapter:


    def __init__(self):

        self.engine = LandscapeIntelligenceEngine()



    def generate(self, state):


        landscape_config = state.get(

            "landscape",

            {}

        )


        result = self.engine.generate(

            landscape_config

        )


        state["landscape_result"] = result


        return state