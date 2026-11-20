from core.intelligence.semantic_engine import SemanticEngine
from core.intelligence.knowledge_graph import KnowledgeGraphEngine
from core.intelligence.reasoning_engine import ReasoningEngine
from core.intelligence.structural_reasoning_v40 import StructuralReasoningEngine


class IntelligencePipeline:

    VERSION = "40.0"


    def __init__(self):

        print(
            "🚀 BIM Intelligence Pipeline v40.0 ACTIVE"
        )

        self.semantic_engine = SemanticEngine()

        self.graph_engine = KnowledgeGraphEngine()

        self.reasoning_engine = ReasoningEngine()

        self.structural_reasoning = StructuralReasoningEngine()



    def process(self, project):


        print(
            "▶️ INTELLIGENCE PIPELINE START"
        )


        # ==================================================
        # BIM DATA NORMALIZATION
        # ==================================================

        bim_elements = project.get(
            "bim_elements",
            []
        )


        # FullBIMPipeline output
        if not bim_elements:

            bim_data = project.get(
                "bim",
                {}
            )


            if isinstance(bim_data, dict):

                bim_elements = bim_data.get(
                    "elements",
                    []
                )


        # Structure fallback
        if not bim_elements:

            structure = project.get(
                "structure",
                {}
            )


            if isinstance(structure, dict):

                bim_elements = (
                    structure.get(
                        "columns",
                        []
                    )
                    +
                    structure.get(
                        "beams",
                        []
                    )
                )


        # ==================================================
        # 1 Semantic Analysis
        # ==================================================

        semantic_result = self.semantic_engine.process(
            bim_elements
        )


        # ==================================================
        # 2 Knowledge Graph
        # ==================================================

        graph_result = self.graph_engine.build_graph(

            semantic_result["elements"]

        )


        # ==================================================
        # 3 Architectural Reasoning
        # ==================================================

        reasoning_result = self.reasoning_engine.process(

            project

        )


        # ==================================================
        # 4 Structural Reasoning v40
        # ==================================================

        structural_result = self.structural_reasoning.process(

            bim_elements

        )


        # ==================================================
        # FINAL INTELLIGENCE OUTPUT
        # ==================================================

        return {


            "engine":
            f"intelligence_pipeline_v{self.VERSION}",


            "status":
            "completed",


            "semantic":
            semantic_result,


            "knowledge_graph":
            graph_result,


            "reasoning":
            reasoning_result,


            "structural_reasoning":
            structural_result


        }