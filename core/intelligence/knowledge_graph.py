class KnowledgeGraphEngine:

    VERSION = "38.0"

    def __init__(self):
        print("🕸️ BIM Knowledge Graph Engine v38.0 ACTIVE")


    def __init_node(self, element):

        return {
            "id": element.get("id"),
            "type": element.get("type"),
            "properties": {
                "system": element.get("system"),
                "role": element.get("semantic_role"),
                "behavior": element.get("behavior")
            }
        }


    def build_nodes(self, semantic_elements):

        nodes = []

        for element in semantic_elements:
            nodes.append(
                self.__init_node(element)
            )

        return nodes


    def infer_relationship(self, node_a, node_b):

        relation = None


        if (
            node_a["type"] == "column"
            and
            node_b["type"] == "beam"
        ):
            relation = "carries_load_to"


        elif (
            node_a["type"] == "beam"
            and
            node_b["type"] == "slab"
        ):
            relation = "supports"


        elif (
            node_a["type"] == "wall"
            and
            node_b["type"] == "opening"
        ):
            relation = "hosts"


        return relation


    def build_graph(
        self,
        semantic_elements
    ):

        nodes = self.build_nodes(
            semantic_elements
        )


        relationships = []


        for a in nodes:

            for b in nodes:

                if a["id"] == b["id"]:
                    continue


                relation = self.infer_relationship(
                    a,
                    b
                )

                if relation:

                    relationships.append({

                        "from":
                        a["id"],

                        "to":
                        b["id"],

                        "type":
                        relation

                    })


        return {

            "engine":
            f"knowledge_graph_v{self.VERSION}",

            "status":
            "generated",

            "nodes":
            nodes,

            "relationships":
            relationships
        }