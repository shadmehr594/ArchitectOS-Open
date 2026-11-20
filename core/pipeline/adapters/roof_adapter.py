from core.geometry.roof_intelligence_engine import RoofIntelligenceEngine



class RoofAdapter:


    def __init__(self):

        self.engine = RoofIntelligenceEngine()



    def generate(self, state):


        roof_config = state.get(

            "roof",

            {}

        )


        result = self.engine.generate(

            roof_config

        )


        state["roof_result"] = result


        return state