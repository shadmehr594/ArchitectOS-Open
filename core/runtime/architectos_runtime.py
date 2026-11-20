# ==========================================================
# ARCHITECTOS RUNTIME ENGINE v102
# Clean Orchestration Layer
# ==========================================================


from core.pipeline.master_architect_pipeline import (
    MasterArchitectPipeline
)

from core.bim.full_bim_pipeline import (
    FullBIMPipeline
)

from core.intelligence.architectos_runtime_adapter import (
    ArchitectOSRuntimeAdapter
)

from core.pipeline.adapters.furniture_adapter import (
    FurnitureStageAdapter
)

from core.pipeline.diffuscene_scene_producer import (
    DiffuSceneSceneProducer,
    STAGE_NAME as DIFFUSCENE_STAGE_NAME,
)



class ArchitectOSRuntime:


    def __init__(self):

        self.engine = (
            "ARCHITECTOS_RUNTIME_ENGINE_V102"
        )


        self.engines = {

            "bim":
                FullBIMPipeline(),


            DIFFUSCENE_STAGE_NAME:
                DiffuSceneSceneProducer(),


            "furniture":
                FurnitureStageAdapter(),


            "intelligence":
                ArchitectOSRuntimeAdapter()

        }


        self.pipeline = (
            MasterArchitectPipeline(
                self.engines
            )
        )


        # The producer MUST run before the consumer. The existing pipeline_order
        # has no "diffuscene" slot, so insert it immediately before "furniture"
        # rather than appending it out of order.
        if DIFFUSCENE_STAGE_NAME in self.pipeline.pipeline_order:

            self.pipeline.pipeline_order.remove(
                DIFFUSCENE_STAGE_NAME
            )

        furniture_index = self.pipeline.pipeline_order.index(
            "furniture"
        )

        self.pipeline.pipeline_order.insert(
            furniture_index,
            DIFFUSCENE_STAGE_NAME
        )



    def run(self, project):


        print(
            "\n🏛️ ARCHITECTOS RUNTIME v102"
        )


        print(
            "▶ MASTER PIPELINE START"
        )


        result = self.pipeline.run(
            project
        )


        result["runtime"] = {

            "engine":
                self.engine,

            "status":
                "completed"

        }


        print(
            "✅ MASTER PIPELINE COMPLETE"
        )


        return result