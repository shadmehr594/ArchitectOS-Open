from core.intelligence.knowledge_graph import (
    KnowledgeGraphEngine
)



class KnowledgeAdapter:


    def __init__(self):

        self.engine = KnowledgeGraphEngine()



    def process(self, data):

        return self.engine.build_graph(

            data.get(
                "semantic_elements",
                []
            )

        )



class ArchitectOSKnowledgeConnector:


    def __init__(self):

        print(
            "🔗 ArchitectOS Knowledge Connector v73.0 ACTIVE"
        )


        self.knowledge = KnowledgeAdapter()



    def process(self, data):

        return self.knowledge.process(
            data
        )