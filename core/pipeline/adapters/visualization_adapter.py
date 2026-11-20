from core.pipeline.architectural_visualization_pipeline import ArchitecturalVisualizationPipeline



class VisualizationAdapter:


    def __init__(self):

        self.engine = ArchitecturalVisualizationPipeline()



    def generate(self, state):


        result = self.engine.build(
            state
        )


        state["visualization_result"] = result


        return state