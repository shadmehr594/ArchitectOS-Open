class BIMSceneGraphEngine:


    def __init__(self):

        print(
          "🏗️ BIM Scene Graph Engine v35.0 ACTIVE"
        )


    def build(
        self,
        structural,
        geometry
    ):


        print(
          "▶️ BUILD BIM SCENE GRAPH"
        )


        graph = {

            "type":
                "Building",

            "version":
                "BIM_GRAPH_v35",

            "levels":[],

            "elements":[]

        }


        floors = geometry.get(
            "floors",
            []
        )


        for floor in floors:


            level_id = (
                f"LEVEL_{floor['level']}"
            )


            level = {

                "id":
                    level_id,

                "elements":[]

            }


            for c in structural.get(
                "columns",
                []
            ):

                if c["level"] == level_id:

                    level["elements"].append(
                        c
                    )


            for b in structural.get(
                "beams",
                []
            ):

                if b["level"] == level_id:

                    level["elements"].append(
                        b
                    )


            for s in structural.get(
                "slabs",
                []
            ):

                if s["level"] == level_id:

                    level["elements"].append(
                        s
                    )


            graph["levels"].append(
                level
            )


        graph["elements"] = [

            e

            for level in graph["levels"]

            for e in level["elements"]

        ]


        return graph