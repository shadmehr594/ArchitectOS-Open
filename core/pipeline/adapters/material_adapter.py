from core.materials.regional_material_engine import RegionalMaterialEngine


class MaterialAdapter:


    def __init__(self):

        self.engine = RegionalMaterialEngine()


    def generate(self, state):


        material_config = state.get(

            "material",

            {}

        )


        result = self.engine.apply(

            material_config

        )


        state["material_result"] = result


        return state