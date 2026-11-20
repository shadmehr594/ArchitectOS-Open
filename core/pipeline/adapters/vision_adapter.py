from core.vision.vision_knowledge_connector import VisionKnowledgeConnector
from core.vision.vision_self_learning_engine import VisionSelfLearningEngine
from core.vision.vision_autonomous_improvement import VisionAutonomousImprovement
from core.vision.vision_optimization_agent import VisionOptimizationAgent
from core.vision.design_correction_engine import DesignCorrectionEngine
from core.vision.vision_design_evaluation import VisionDesignEvaluation
from core.vision.autonomous_architect_agent import AutonomousArchitectAgent


class VisionAdapter:


    def __init__(self):

        self.knowledge = VisionKnowledgeConnector()

        self.learning = VisionSelfLearningEngine()

        self.improvement = VisionAutonomousImprovement()

        self.optimizer = VisionOptimizationAgent()

        self.correction = DesignCorrectionEngine()

        self.evaluation = VisionDesignEvaluation()

        self.architect = AutonomousArchitectAgent()


        print(
            "🧠 Vision Adapter v80 ACTIVE"
        )



    def build(self, state):


        knowledge_result = self.knowledge.update(
            state
        )


        learning_result = self.learning.learn(
            knowledge_result
        )


        improvement_result = self.improvement.improve(
            learning_result
        )


        optimization_result = self.optimizer.optimize(
            improvement_result
        )


        correction_result = self.correction.correct(
            optimization_result
        )


        evaluation_result = self.evaluation.evaluate(
            correction_result
        )


        decision_result = self.architect.decide(
            evaluation_result
        )


        state["vision_result"] = {


            "knowledge":

                knowledge_result,


            "learning":

                learning_result,


            "improvement":

                improvement_result,


            "optimization":

                optimization_result,


            "correction":

                correction_result,


            "evaluation":

                evaluation_result,


            "architect_decision":

                decision_result

        }


        return state