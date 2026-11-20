from core.geometry.wall_opening_builder import WallOpeningBuilder



class FacadeAdapter:


    def __init__(self):

        self.engine = WallOpeningBuilder()



    def generate(self, state):


        facade_config = state.get(

            "facade",

            {}

        )


        envelope = facade_config.get(

            "envelope",

            {}

        )


        config = facade_config.get(

            "config",

            {}

        )


        result = self.engine.build(

            envelope,

            config

        )


        state["facade_result"] = result


        return state