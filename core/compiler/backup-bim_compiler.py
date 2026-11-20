class BIMCompiler:

    def compile(self, design):

        edges = []

        for floor, data in design.items():
            edges.extend(data.get("connections", []))

        return {
            "edges": edges,
            "floors": len(design),
            "graph_type": "bim_v16"
        }