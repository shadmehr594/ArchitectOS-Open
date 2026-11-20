from core.bim.bim_scene_graph import (
    BIMSceneGraphEngine
)



class BIMPipelineEngine:


    def __init__(self):

        print(
            "🚀 BIM Pipeline Engine v33.2 ACTIVE"
        )


        self.scene_graph_engine = (
            BIMSceneGraphEngine()
        )



    def run(
        self,
        state,
        geometry=None
    ):


        print(
            "🔄 BIM PIPELINE START"
        )



        if geometry is not None:

            state = {

                "structural_result":
                    state,

                "geometry_result":
                    geometry

            }



        structural = state.get(
            "structural_result",
            {}
        )


        geometry = state.get(
            "geometry_result",
            {}
        )



        scene_graph = (

            self.scene_graph_engine.build(

                structural,

                geometry

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