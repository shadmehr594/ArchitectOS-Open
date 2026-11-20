from core.scene.scene_builder import SceneBuilderEngine



class SceneBuilderAdapter:


    def __init__(self):

        self.engine = SceneBuilderEngine()



    def build(self, state):

        return self.engine.build(
            state
        )