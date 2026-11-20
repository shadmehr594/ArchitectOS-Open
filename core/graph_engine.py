class GraphEngine:

    def build_graph(self, spatial):

        graph = {
            "walls": [],
            "rooms": [],
            "edges": []
        }

        for floor_id, floor in spatial.items():

            nodes = floor["nodes"]
            connections = floor["connections"]

            # WALLS
            for c in connections:
                graph["walls"].append({
                    "from": c[0],
                    "to": c[1],
                    "type": "wall"
                })

            # ROOMS (simple placeholder logic)
            graph["rooms"].append({
                "floor": floor_id,
                "type": "open_space",
                "nodes_count": len(nodes)
            })

            graph["edges"].extend(connections)

        return graph