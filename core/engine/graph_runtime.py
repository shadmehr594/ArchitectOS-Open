class GraphRuntime:

    def run(self, design):

        edges = []

        for floor, data in design.items():
            edges.extend(data.get("connections", []))

        return {
            "edges": edges,
            "runtime": "v9_graph_runtime"
        }