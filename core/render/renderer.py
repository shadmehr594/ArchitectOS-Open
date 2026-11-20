class Renderer:

    def render(self, design):

        edges = []

        for floor, data in design.items():

            nodes = list(data.get("nodes", {}).keys())

            for i in range(len(nodes) - 1):
                edges.append([nodes[i], nodes[i+1]])

        return {
            "edges": edges,
            "raw": design
        }