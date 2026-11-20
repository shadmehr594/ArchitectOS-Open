"""
ArchitectOS BIM
Structural Decision Pipeline v66

Purpose:
- Unified structural intelligence pipeline
- Connect reasoning, decision, bridge and adapter layers
"""


from core.intelligence.structural_reasoning_v40 import (
    StructuralReasoningEngine
)

from core.intelligence.structural_decision_intelligence_v65 import (
    StructuralDecisionIntelligence
)

from core.intelligence.structural_decision_bridge_v65 import (
    StructuralDecisionBridge
)

from core.intelligence.decision_structural_adapter_v65 import (
    DecisionStructuralAdapter
)



class StructuralDecisionPipeline:


    VERSION = "66.0"



    def __init__(self):

        print(
            "🧠 Structural Decision Pipeline v66.0 ACTIVE"
        )


        self.reasoning = StructuralReasoningEngine()

        self.decision = StructuralDecisionIntelligence()

        self.bridge = StructuralDecisionBridge()

        self.adapter = DecisionStructuralAdapter()



    def process(
        self,
        bim
    ):


        print(
            "▶️ STRUCTURAL DECISION PIPELINE START"
        )



        # ======================================
        # 1 STRUCTURAL REASONING
        # ======================================

        reasoning_result = self.reasoning.analyze(
            bim
        )



        # ======================================
        # 2 STRUCTURAL DECISION
        # ======================================

        decision_result = self.decision.process(
            reasoning_result
        )



        # ======================================
        # 3 BRIDGE
        # ======================================

        bridge_result = self.bridge.translate(
            decision_result
        )



        # ======================================
        # 4 ADAPTER
        # ======================================

        final_decision = self.adapter.adapt(
            bridge_result
        )



        return {


            "engine":
            f"structural_decision_pipeline_v{self.VERSION}",


            "status":
            "completed",


            "reasoning":
            reasoning_result,


            "structural_decision":
            decision_result,


            "bridge":
            bridge_result,


            "final_decision":
            final_decision

        }