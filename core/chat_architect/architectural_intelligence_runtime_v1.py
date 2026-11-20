# ==========================================================
# ARCHITECTURAL INTELLIGENCE RUNTIME V1
# CHATARCHITECT RUNTIME COMPOSITION LAYER
# ==========================================================


from core.architecture_intelligence.architectural_flow_orchestrator_v1 import (
    ArchitecturalFlowOrchestratorV1
)

from core.memory.architectural_decision_memory_writer_v1 import (
    ArchitecturalDecisionMemoryWriterV1
)

from core.chat_architect.architectural_intelligence_bridge_v1 import (
    ChatArchitectArchitecturalIntelligenceBridgeV1
)



class ArchitecturalIntelligenceRuntimeV1:


    VERSION = "1.0"



    def __init__(self):


        print(
            "⚙️ Architectural Intelligence Runtime v1.0 ACTIVE"
        )


        self.memory_writer = (
            ArchitecturalDecisionMemoryWriterV1()
        )


        self.flow = (
            ArchitecturalFlowOrchestratorV1(
                memory_writer=self.memory_writer
            )
        )


        self.bridge = (
            ChatArchitectArchitecturalIntelligenceBridgeV1(
                architectural_flow=self.flow
            )
        )



    # ======================================================
    # HANDLE REQUEST
    # ======================================================


    def process(
        self,
        user_request,
        context
    ):


        result = (
            self.bridge.process(
                user_request,
                context
            )
        )



        return {


            "engine":

                "ARCHITECTURAL_INTELLIGENCE_RUNTIME_V1",


            "version":

                self.VERSION,


            "result":

                result,


            "ready":

                result.get(
                    "response_ready",
                    False
                )

        }