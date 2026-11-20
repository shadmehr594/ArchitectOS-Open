class BIMVisualizer:


    def __init__(self):

        print(
            "🏗️ BIM Visualization Engine v22.2 ACTIVE"
        )


    def generate(
        self,
        drawing
    ):

        model = []


        for floor, data in drawing.get(
            "floors",
            {}
        ).items():

            for room in data.get(
                "rooms",
                []
            ):

                model.append(
                    {
                        "floor":floor,
                        "object":room["name"],
                        "geometry":{
                            "x":room["x"],
                            "y":room["y"],
                            "width":room["width"],
                            "depth":room["depth"]
                        }
                    }
                )


        return {

            "engine":
                "bim_visualizer_v22.2",

            "status":
                "generated",

            "objects":
                model
        }