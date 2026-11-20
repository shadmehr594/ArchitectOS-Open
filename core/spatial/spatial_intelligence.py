class SpatialIntelligence:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🧠 SPATIAL INTELLIGENCE ENGINE v1.0 ONLINE"
        )


    # ==========================================
    # NODE BUILDER
    # ==========================================

    def build_nodes(
        self,
        intent
    ):

        nodes = []


        for space in intent.get(
            "spaces",
            []
        ):

            if space not in nodes:

                nodes.append(
                    space
                )


        return nodes



    # ==========================================
    # RELATION GRAPH
    # ==========================================

    def build_connections(
        self,
        intent
    ):

        connections = []


        for relation in intent.get(
            "relationships",
            []
        ):


            connections.append(

                {

                    "source":
                        relation.get(
                            "from"
                        ),

                    "target":
                        relation.get(
                            "to"
                        ),

                    "behavior":
                        relation.get(
                            "type"
                        )

                }

            )


        return connections



    # ==========================================
    # ZONE MAP
    # ==========================================

    def build_zones(
        self,
        intent
    ):

        zones = {}


        for zone, spaces in intent.get(
            "zones",
            {}
        ).items():


            zones[zone] = list(
                spaces
            )


        return zones



    # ==========================================
    # SITE MODEL
    # ==========================================

    def build_site_model(
        self,
        intent
    ):


        return {

            "position":
                intent.get(
                    "site_constraints",
                    {}
                ).get(
                    "building_position"
                ),

            "setbacks":
                intent.get(
                    "site_constraints",
                    {}
                ).get(
                    "setbacks"
                ),

            "open_spaces":
                intent.get(
                    "site_constraints",
                    {}
                ).get(
                    "open_spaces"
                )

        }



    # ==========================================
    # MAIN ANALYSIS
    # ==========================================

    def analyze(
        self,
        intent
    ):


        model = {


            "building_type":
                intent.get(
                    "building_type"
                ),


            "style":
                intent.get(
                    "style"
                ),


            "materials":
                intent.get(
                    "materials",
                    []
                ),


            "spatial_model":{


                "nodes":
                    self.build_nodes(
                        intent
                    ),


                "connections":
                    self.build_connections(
                        intent
                    ),


                "zones":
                    self.build_zones(
                        intent
                    )

            },


            "site_model":
                self.build_site_model(
                    intent
                )

        }


        return model