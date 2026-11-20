# ==========================================================
# ArchitectOS App Boot v22
# GOD CORE + CORE TOOL SYSTEM + SELF HEAL + EVOLUTION
# ==========================================================


from core.brain import Brain
from core.registry.engine_registry import EngineRegistry

from core.engine.self_healing_core import SelfHealingCore
from core.engine.evolution_loop import EvolutionLoop

from core.tool_bootstrap import build_tool_registry

from core.memory.memory_manager import memory_manager



class AppBoot:


    def __init__(self):


        print(
            "🚀 AppBoot v22 STARTED"
        )


        # ======================================
        # ENGINE REGISTRY
        # ======================================

        registry = EngineRegistry()



        # ======================================
        # GOD CORE
        # ======================================

        self.brain = Brain(
            registry=registry
        )



        # ======================================
        # TOOL SYSTEM
        # CONNECT TO GOD CORE
        # ======================================

        self.tool_registry = build_tool_registry(

            brain=self.brain,

            memory=memory_manager

        )



        self.brain.tools = self.tool_registry



        print(
            "🛠️ TOOL SYSTEM CONNECTED"
        )



        # ======================================
        # SELF HEALING
        # ======================================

        self.healer = SelfHealingCore(

            registry=self.brain.registry,

            brain=self.brain

        )



        # ======================================
        # EVOLUTION
        # ======================================

        self.evolution = EvolutionLoop(

            self.brain,

            self.healer

        )


        self.brain.attach_evolution(

            self.evolution

        )



        print(
            "🧠 SELF HEAL + EVOLUTION ONLINE"
        )



    # ======================================
    # ACCESSORS
    # ======================================


    def get_brain(self):

        return self.brain



    def get_tools(self):

        return self.tool_registry





# ==========================================================
# DIRECT START
# ==========================================================


if __name__ == "__main__":


    app = AppBoot()


    print(
        "🚀 ArchitectOS v1.0 CORE READY"
    )