from core.intent_router import IntentRouter
from core.agents.planner_agent import PlannerAgent
from core.agents.design_agent import DesignAgent
from core.agents.constraint_agent import ConstraintAgent
from core.agents.repair_agent import RepairAgent

from core.bim_validator import BIMValidator

from core.compiler.bim_compiler import BIMCompiler

from core.engine.executor import Executor
from core.engine.scorer import DesignScorer
from core.engine.memory import DesignMemory
from core.engine.mutator import Mutator

from core.engine.self_analyzer import SelfAnalyzer
from core.engine.self_rewriter import SelfRewriter


# ======================
# SPATIAL ARCHITECTURE ENGINE
# ======================

from core.spatial.spatial_layout_engine import SpatialLayoutEngine
from core.spatial.zoning_spatial_engine import ZoningSpatialEngine
from core.spatial.adjacency_engine import AdjacencyEngine
from core.spatial.constraint_solver import ArchitecturalConstraintSolver

from core.reasoning.design_reasoner import DesignReasoner
from core.reasoning.adaptive_critic import AdaptiveCritic
from core.reasoning.improvement_generator import ImprovementGenerator

from core.mutation.improvement_executor import ImprovementExecutor

from core.optimization.spatial_optimizer import SpatialOptimizationMutator
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.intelligence.reasoning_engine import ReasoningEngine
from core.intelligence.decision_adapter import DecisionAdapter
from core.intelligence.architectos_design_execution_bridge_v100 import ArchitectOSDesignExecutionBridge



class EngineRegistry:


    def __init__(self):

        self.registry = {}

        self.auto_discover()



    def auto_discover(self):


        self.registry = {


            # ======================
            # CORE AGENTS
            # ======================

            "IntentRouter":
                IntentRouter,

            "PlannerAgent":
                PlannerAgent,

            "DesignAgent":
                DesignAgent,

            "ConstraintAgent":
                ConstraintAgent,

            "RepairAgent":
                RepairAgent,



            # ======================
            # SELF EVOLUTION
            # ======================

            "SelfAnalyzer":
                SelfAnalyzer,

            "SelfRewriter":
                SelfRewriter,



            # ======================
            # BIM CORE
            # ======================

            "BIMValidator":
                BIMValidator,

            "BIMCompiler":
                BIMCompiler,



            # ======================
            # RUNTIME ENGINE
            # ======================

            "Executor":
                Executor,

            "DesignScorer":
                DesignScorer,

            "DesignMemory":
                DesignMemory,

            "Mutator":
                Mutator,
                
            "ImprovementExecutor":
                ImprovementExecutor,



            # ======================
            # SPATIAL DESIGN ENGINE
            # ======================

            "SpatialLayoutEngine":
                SpatialLayoutEngine,

            "ZoningSpatialEngine":
                ZoningSpatialEngine,

            "AdjacencyEngine":
                AdjacencyEngine,

            "ArchitecturalConstraintSolver":
                ArchitecturalConstraintSolver,


            # ======================
            # REASONING ENGINE
            # ======================

            "DesignReasoner":
                DesignReasoner,

            "AdaptiveCritic":
                AdaptiveCritic,

            "ImprovementGenerator":
                ImprovementGenerator,

            # ======================
            # REASONING ENGINE
            # ======================

            "SpatialOptimizationMutator":
                SpatialOptimizationMutator,

            "ArchitecturalIntent":

                ArchitecturalIntent,

            # ======================
            # ARCHITECTURAL INTELLIGENCE
            # ======================

            "ReasoningEngine":

                ReasoningEngine,


            "DecisionAdapter":

                DecisionAdapter,


            "DesignExecutionBridge":

                ArchitectOSDesignExecutionBridge,


        }


        print(
            f"🧠 GOD REGISTRY LOADED: {len(self.registry)}"
        )


        return self.registry