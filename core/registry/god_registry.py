from core.intent_router import IntentRouter
from core.agents.planner_agent import PlannerAgent
from core.agents.design_agent import DesignAgent
from core.agents.constraint_agent import ConstraintAgent
from core.agents.repair_agent import RepairAgent
from core.bim_validator import BIMValidator

from core.engine.executor import Executor
from core.engine.scorer import DesignScorer
from core.engine.memory import DesignMemory
from core.engine.mutator import Mutator
from core.engine.self_analyzer import SelfAnalyzer
from core.engine.self_rewriter import SelfRewriter

from core.compiler.bim_compiler import BIMCompiler


class GodRegistry:

    def __init__(self):
        print("🧠 GOD REGISTRY INIT v18")

        self._map = {
            # 🧠 CORE BRAIN
            "IntentRouter": IntentRouter,
            "PlannerAgent": PlannerAgent,

            # 🎨 DESIGN
            "DesignAgent": DesignAgent,

            # 🔧 VALIDATION LAYER
            "BIMValidator": BIMValidator,
            "ConstraintAgent": ConstraintAgent,
            "RepairAgent": RepairAgent,

            # ⚙️ EXECUTION CORE
            "Executor": Executor,
            "DesignScorer": DesignScorer,
            "DesignMemory": DesignMemory,
            "Mutator": Mutator,

            # 🧠 SELF SYSTEM
            "SelfAnalyzer": SelfAnalyzer,
            "SelfRewriter": SelfRewriter,

            # 📦 COMPILER (IMPORTANT FIX HERE)
            "BIMCompiler": BIMCompiler,
        }

    def auto_discover(self):
        return self._map