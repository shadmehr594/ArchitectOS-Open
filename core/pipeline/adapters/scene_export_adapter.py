from core.render.scene_exporter import SceneExporter


class SceneExportAdapter:


    def __init__(self):

        self.engine = SceneExporter()


        print(
            "🎬 Scene Export Adapter v30.0 ACTIVE"
        )


    def execute(self, state):

        return self.engine.export(
            state
        )


    def generate(self, state):

        return self.engine.export(
            state
        )


    def export(self, state):

        return self.engine.export(
            state
        )