class ThreeExporter:

    def export(self, bim):

        meshes = []

        spatial = bim.get("spatial", {})

        for floor, data in spatial.items():

            for node, props in data["nodes"].items():

                meshes.append({
                    "name": node,
                    "x": props["x"],
                    "y": props["y"],
                    "z": 0,
                    "w": props["w"],
                    "h": props["h"]
                })

        return {
            "meshes": meshes
        }