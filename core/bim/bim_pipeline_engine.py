from core.bim.bim_scene_graph import (
    BIMSceneGraphEngine
)


class BIMPipelineEngine:


    def __init__(self):

        self.scene_graph_engine = BIMSceneGraphEngine()


    def run(
        self,
        state,
        geometry=None
    ):

        print(
            "▶️ BIM PIPELINE START"
        )


        # ----------------------------
        # Backward compatibility
        # ----------------------------

        if geometry is not None:

            bim_state = {

                "structural_result":
                    state,

                "geometry_result":
                    geometry

            }

        else:

            bim_state = state



        structural = (

            bim_state.get(
                "structural_result",
                {}
            )

        )


        geometry_data = (

            bim_state.get(
                "geometry_result",
                {}

            )

        )


        print(
            "DEBUG STRUCTURAL:"
        )

        print(
            structural
        )


        print(
            "DEBUG GEOMETRY:"
        )

        print(
            type(geometry_data)
        )


        scene_graph = (

            self.scene_graph_engine.build(

                structural,

                geometry_data

            )

        )


        result = {


            "engine":
                "BIMPipelineEngine_v33.2",


            "status":
                "completed",


            "scene_graph":
                scene_graph


        }


        print(
            "✅ BIM PIPELINE COMPLETE"
        )


        return result