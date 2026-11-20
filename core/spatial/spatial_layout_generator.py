class SpatialLayoutGenerator:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧠 SPATIAL LAYOUT GENERATOR v1.0 ONLINE"
        )



    # ==================================================
    # POSITION RULES
    # ==================================================

    def generate_positions(
        self,
        spatial_model
    ):


        positions = {}



        zones = spatial_model.get(
            "zones",
            {}
        )



        zone_positions = {

            "public": "center",

            "semi_public": "center",

            "commercial": "front",

            "service": "back",

            "private": "quiet",

            "external": "outside"

        }



        for zone, spaces in zones.items():


            for index, space in enumerate(spaces):


                positions[space] = {


                    "zone": zone,


                    "position":
                        zone_positions.get(
                            zone,
                            "unknown"
                        ),


                    "order":
                        index


                }



        return positions



    # ==================================================
    # CONNECTION GRAPH
    # ==================================================

    def generate_relationships(
        self,
        spatial_model
    ):


        result = []


        for connection in spatial_model.get(
            "connections",
            []
        ):


            result.append(

                {

                    "from":
                        connection["source"],


                    "to":
                        connection["target"],


                    "relationship":
                        connection["behavior"]

                }

            )


        return result



    # ==================================================
    # MAIN
    # ==================================================

    def generate(
        self,
        spatial_model
    ):


        return {


            "layout": 
                self.generate_positions(
                    spatial_model
                ),


            "relationships":
                self.generate_relationships(
                    spatial_model
                ),


            "metadata": {

                "engine":
                    "Spatial Layout Generator",

                "version":
                    self.VERSION

            }

        }