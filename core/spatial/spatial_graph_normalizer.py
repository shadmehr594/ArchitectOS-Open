# ==========================================================
# ArchitectOS Spatial Graph Normalizer v1.0
#
# Purpose:
# Planner Graph
#        |
#        ↓
# Complete Spatial Graph
#        |
#        ↓
# BIM / IFC Ready
#
# ==========================================================


class SpatialGraphNormalizer:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧩 SPATIAL GRAPH NORMALIZER v1.0 ONLINE"
        )



    # ==================================================
    # NORMALIZE
    # ==================================================

    def normalize(
        self,
        spatial
    ):


        if not isinstance(
            spatial,
            dict
        ):

            spatial = {}



        nodes = spatial.get(
            "nodes",
            []
        )



        connections = spatial.get(
            "connections",
            []
        )


        adjacency = spatial.get(
            "adjacency",
            []
        )



        # ----------------------------------------------
        # Extract missing nodes from connections
        # ----------------------------------------------

        for relation in connections:


            for key in [
                "from",
                "to"
            ]:


                value = relation.get(
                    key
                )


                if value and value not in nodes:

                    nodes.append(
                        value
                    )



        # ----------------------------------------------
        # Extract missing nodes from adjacency
        # ----------------------------------------------

        for relation in adjacency:


            for key in [
                "from",
                "to"
            ]:


                value = relation.get(
                    key
                )


                if value and value not in nodes:

                    nodes.append(
                        value
                    )



        # ----------------------------------------------
        # Normalize
        # ----------------------------------------------

        normalized_nodes = []

        seen = set()


        for node in nodes:

            node_id = (

                node.get("id")

                if isinstance(
                    node,
                    dict
                )

                else node

            )


            if node_id in seen:
                continue


            seen.add(
                node_id
            )


            normalized_nodes.append(
                node
            )



        spatial["nodes"] = normalized_nodes



        # ----------------------------------------------
        # BIM Space Registry
        # ----------------------------------------------

        spatial["space_registry"] = []


        for node in spatial["nodes"]:


            if isinstance(
                node,
                dict
            ):

                registry_item = {

                    "id":
                        node.get(
                            "id"
                        ),

                    "type":
                        node.get(
                            "type",
                            "IfcSpace"
                        ),

                    "level":
                        node.get(
                            "level"
                        ),

                    "semantic":
                        node.get(
                            "semantic",
                            {}
                        ),

                    "status":
                        "planned"

                }


            else:

                registry_item = {

                    "id":
                        node,

                    "type":
                        "IfcSpace",

                    "status":
                        "planned"

                }


            spatial["space_registry"].append(
                registry_item
            )



        return spatial