# ==================================================
# ArchitectOS Brain Connector v71
# ==================================================

from core.intelligence.architectos_intelligence_orchestrator_v70 import (
    ArchitectOSIntelligenceOrchestrator
)


class ArchitectOSBrainConnector:


    VERSION = "71.0"



    def __init__(
        self,
        memory_engine=None,
        decision_engine=None,
        agent_engine=None
    ):


        print(
            "🔗 ArchitectOS Brain Connector v71.0 ACTIVE"
        )


        self.memory_engine = memory_engine

        self.decision_engine = decision_engine

        self.agent_engine = agent_engine



        self.orchestrator = (
            ArchitectOSIntelligenceOrchestrator(

                memory_engine=self.memory_engine,

                decision_engine=self.decision_engine,

                agent_engine=self.agent_engine

            )
        )



    # ==========================================
    # RUN BRAIN
    # ==========================================

    def process(
        self,
        request
    ):


        print(
            "🧠 ARCHITECTOS BRAIN CONNECTED"
        )


        return self.orchestrator.process(
            request
        )