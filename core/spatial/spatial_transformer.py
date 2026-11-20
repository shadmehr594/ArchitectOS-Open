class SpatialTransformer:

    def graph_to_layout(self, graph, width, height):
        layout = {}

        for node in graph:
            if "Living" in node:
                layout[node] = (0, 0, width*0.6, height*0.4)

            elif "Kitchen" in node:
                layout[node] = (width*0.6, 0, width*0.4, height*0.4)

            elif "Bedroom" in node:
                layout[node] = (0, height*0.4, width*0.5, height*0.6)

            elif "Circulation" in node:
                layout[node] = (width*0.5, height*0.4, width*0.5, height*0.2)

            elif "Parking" in node:
                layout[node] = (0, 0, width, height)

        return layout