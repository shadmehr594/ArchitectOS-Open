class SpatialLayoutReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧠 SPATIAL LAYOUT REASONER v1.0 ONLINE"
        )



    # ==================================================
    # FIND ANCHOR SPACE
    # ==================================================

    def find_anchor(
        self,
        nodes,
        connections
    ):


        scores = {
            node: 0
            for node in nodes
        }



        for connection in connections:


            source = connection.get(
                "source"
            )

            target = connection.get(
                "target"
            )

            behavior = connection.get(
                "behavior"
            )



            if source in scores:

                scores[source] += 1



            if target in scores:

                scores[target] += 1



            if behavior == "vertical_connection":

                if target in scores:

                    scores[target] += 3



        if not scores:

            return None



        return max(
            scores,
            key=scores.get
        )



    # ==================================================
    # CLASSIFY ZONES
    # ==================================================

    def classify_zones(
        self,
        zones
    ):


        result = {


            "front_zone": [],

            "central_zone": [],

            "service_zone": [],

            "entertainment_zone": []

        }



        for space in zones.get(
            "commercial",
            []
        ):

            result["front_zone"].append(
                space
            )



        for space in zones.get(
            "service",
            []
        ):

            result["service_zone"].append(
                space
            )



        for space in zones.get(
            "public",
            []
        ):


            if space in [
                "food_court",
                "cinema",
                "entertainment"
            ]:


                result["entertainment_zone"].append(
                    space
                )


            else:


                result["central_zone"].append(
                    space
                )



        return result



    # ==================================================
    # RELATION LOGIC
    # ==================================================

    def analyze_connections(
        self,
        connections
    ):


        logic = []



        for connection in connections:


            logic.append({

                "from":
                    connection.get(
                        "source"
                    ),


                "to":
                    connection.get(
                        "target"
                    ),


                "importance":
                    (
                        "high"
                        if connection.get(
                            "behavior"
                        )
                        == "vertical_connection"

                        else

                        "medium"
                    )

            })



        return logic



    # ==================================================
    # MAIN
    # ==================================================

    def generate(
        self,
        normalized_model
    ):


        nodes = normalized_model.get(
            "nodes",
            []
        )


        connections = normalized_model.get(
            "connections",
            []
        )


        zones = normalized_model.get(
            "zones",
            {}
        )



        result = {


            "anchor_space":
                self.find_anchor(
                    nodes,
                    connections
                ),


            "zones":
                self.classify_zones(
                    zones
                ),


            "relationships":
                self.analyze_connections(
                    connections
                ),


            "metadata": {

                "engine":
                    "Spatial Layout Reasoner",

                "version":
                    self.VERSION

            }

        }



        return result