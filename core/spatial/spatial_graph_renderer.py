import json


class SpatialGraphRenderer:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🧠 SPATIAL GRAPH RENDERER v1.0 ONLINE"
        )



    # ==================================================
    # ZONE SYMBOLS
    # ==================================================

    def zone_symbol(
        self,
        zone
    ):

        symbols = {

            "public": "🟦",

            "semi_public": "🟩",

            "private": "🟥",

            "service": "🟨",

            "external": "🟪",

            "commercial": "🟧"

        }


        return symbols.get(
            zone,
            "⬜"
        )



    # ==================================================
    # NODE BUILD
    # ==================================================

    def build_nodes(
        self,
        spatial_model
    ):


        nodes = []


        zones = spatial_model.get(
            "zones",
            {}
        )


        for zone, spaces in zones.items():


            for space in spaces:


                nodes.append(

                    {

                        "name": space,

                        "zone": zone,

                        "symbol":
                            self.zone_symbol(
                                zone
                            )

                    }

                )


        return nodes



    # ==================================================
    # EDGE BUILD
    # ==================================================

    def build_edges(
        self,
        spatial_model
    ):


        edges = []


        for connection in spatial_model.get(
            "connections",
            []
        ):


            edges.append(

                {

                    "from":
                        connection.get(
                            "source"
                        ),


                    "to":
                        connection.get(
                            "target"
                        ),


                    "type":
                        connection.get(
                            "behavior"
                        )

                }

            )


        return edges



    # ==================================================
    # RENDER TEXT GRAPH
    # ==================================================

    def render_text(
        self,
        spatial_model
    ):


        nodes = self.build_nodes(
            spatial_model
        )


        edges = self.build_edges(
            spatial_model
        )


        output = []


        output.append(
            "\n🏗 SPATIAL GRAPH\n"
        )


        for node in nodes:


            output.append(

                f"{node['symbol']} "
                f"{node['name']} "
                f"({node['zone']})"

            )


        output.append(
            "\n🔗 CONNECTIONS\n"
        )


        for edge in edges:


            output.append(

                f"{edge['from']} "
                f"--[{edge['type']}]--> "
                f"{edge['to']}"

            )


        return "\n".join(
            output
        )



    # ==================================================
    # FULL OUTPUT
    # ==================================================

    def render(
        self,
        spatial_model
    ):


        return {


            "nodes":
                self.build_nodes(
                    spatial_model
                ),


            "edges":
                self.build_edges(
                    spatial_model
                ),


            "visual":
                self.render_text(
                    spatial_model
                )

        }