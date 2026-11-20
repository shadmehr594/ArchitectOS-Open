class BIMCompiler:


    def compile(self, design):

        edges = []

        floors = []


        for key, data in design.items():

            # فقط طبقات واقعی BIM
            if not key.startswith("F"):
                continue


            if not isinstance(data, dict):
                continue


            floors.append(key)

            edges.extend(
                data.get(
                    "connections",
                    []
                )
            )


        return {

            "edges": edges,

            "floors": len(floors),

            "floor_names": floors,

            "graph_type": "bim_v16"

        }