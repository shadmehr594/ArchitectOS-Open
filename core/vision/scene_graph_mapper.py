class SceneGraphMapper:


    def __init__(self):

        print(
            "🌐 Vision Scene Graph Mapper v68 ACTIVE"
        )



    def build(self, bim_result):


        elements = bim_result.get(
            "elements",
            {}
        )


        nodes = []

        relationships = []



        # Walls

        for wall in elements.get(
            "walls",
            []
        ):

            node = {

                "id":
                    wall.get(
                        "id",
                        "wall_unknown"
                    ),

                "type":
                    "Wall",

                "category":
                    wall.get(
                        "category",
                        "Wall"
                    )

            }


            nodes.append(
                node
            )



        # Floors

        for floor in elements.get(
            "floors",
            []
        ):


            node = {

                "id":
                    f"floor_{floor.get('level',1)}",

                "type":
                    "Floor",

                "category":
                    floor.get(
                        "category",
                        "Floor"
                    )

            }


            nodes.append(
                node
            )



        # Openings

        for index, opening in enumerate(
            elements.get(
                "openings",
                []
            )
        ):


            node = {

                "id":
                    f"opening_{index+1}",

                "type":
                    "Opening",

                "category":
                    opening.get(
                        "category",
                        "Opening"
                    )

            }


            nodes.append(
                node
            )



        # Basic relationships


        for node in nodes:


            if node["type"] == "Wall":

                relationships.append(

                    {

                    "from":
                        node["id"],

                    "relation":
                        "belongs_to_building",

                    "to":
                        "building"

                    }

                )



            if node["type"] == "Floor":

                relationships.append(

                    {

                    "from":
                        node["id"],

                    "relation":
                        "supports",

                    "to":
                        "building"

                    }

                )



        return {


            "graph":

            {

                "nodes":
                    nodes,

                "relationships":
                    relationships

            },


            "node_count":
                len(nodes),


            "relationship_count":
                len(relationships),


            "ready_for_reasoning":
                True

        }