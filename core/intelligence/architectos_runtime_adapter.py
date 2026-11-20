from core.intelligence.architectos_intelligence_orchestrator_v70 import (
    ArchitectOSIntelligenceOrchestrator
)

from core.intelligence.experience_memory import (
    ExperienceMemoryEngine
)

from core.intelligence.decision_intelligence import (
    DecisionIntelligenceEngine
)

from core.intelligence.autonomous_agent import (
    AutonomousAgentEngine
)

from core.intelligence.experience_persistence import (
    ExperiencePersistence
)



# ==================================================
# MEMORY ADAPTER
# ==================================================

class MemoryAdapter:


    def __init__(
        self,
        engine,
        persistence=None
    ):

        self.engine = engine
        self.persistence = persistence



    def process(self, data):

        if hasattr(
            self.engine,
            "build"
        ):

            result = self.engine.build(
                data
            )


            if self.persistence:

                self.persistence.store(
                    result
                )


            return result


        if hasattr(
            self.engine,
            "recall"
        ):

            return self.engine.recall(
                data
            )


        return {

            "status":
            "memory_engine_unavailable"

        }



    def recall(self, data):

        if hasattr(
            self.engine,
            "recall"
        ):

            return self.engine.recall(
                data
            )

        return None



    def store(self, data):

        if hasattr(
            self.engine,
            "store"
        ):

            return self.engine.store(
                data
            )

        return None




# ==================================================
# DECISION ADAPTER
# ==================================================

class DecisionAdapter:


    def __init__(self, engine):

        self.engine = engine



    def process(self, data):

        if hasattr(
            self.engine,
            "build"
        ):

            return self.engine.build(
                data
            )


        if hasattr(
            self.engine,
            "evaluate"
        ):

            return self.engine.evaluate(
                data
            )


        return {

            "status":
            "decision_engine_unavailable"

        }



    def evaluate(self, data):

        if hasattr(
            self.engine,
            "evaluate"
        ):

            return self.engine.evaluate(
                data
            )

        return None




# ==================================================
# AGENT ADAPTER
# ==================================================

class AgentAdapter:


    def __init__(self, engine):

        self.engine = engine



    def execute(self, data):

        if hasattr(
            self.engine,
            "execute"
        ):

            return self.engine.execute(
                data
            )


        if hasattr(
            self.engine,
            "build"
        ):

            return self.engine.build(
                data
            )


        return {

            "status":
            "agent_engine_unavailable"

        }




# ==================================================
# ARCHITECTOS RUNTIME ADAPTER
# ==================================================

class ArchitectOSRuntimeAdapter:


    VERSION = "1.0"



    def __init__(self):


        print(
            "🔗 ArchitectOS Runtime Adapter v1.0 ACTIVE"
        )



        self.memory = MemoryAdapter(

            ExperienceMemoryEngine(),

            ExperiencePersistence()

        )



        self.decision = DecisionAdapter(

            DecisionIntelligenceEngine()

        )



        self.agent = AgentAdapter(

            AutonomousAgentEngine()

        )



        self.brain = ArchitectOSIntelligenceOrchestrator(

            memory_engine=self.memory,

            decision_engine=self.decision,

            agent_engine=self.agent

        )




    # ==================================================
    # MAIN ENTRY
    # ==================================================

    def process(
        self,
        request
    ):


        return self.brain.process(
            request
        )