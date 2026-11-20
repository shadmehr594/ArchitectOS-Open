from core.render.camera_intelligence_engine import CameraIntelligenceEngine



class CameraAdapter:


    def __init__(self):

        self.engine = CameraIntelligenceEngine()



    def generate(self, state):


        camera_config = state.get(

            "camera",

            {}

        )


        result = self.engine.generate(

            camera_config

        )


        state["camera_result"] = result


        return state