from core.scene.geometry_builder import GeometryMeshBuilder



class GeometryAdapter:


    def __init__(self):

        self.engine = GeometryMeshBuilder()



    def build(self, state):

        return self.engine.build(
            state
        )