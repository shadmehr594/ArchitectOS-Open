class BIMElementAssemblyEngine:


    def __init__(self):

        print(
            "🏗️ BIM Element Assembly Engine v27.4 ACTIVE"
        )



    def assemble(
        self,
        building_elements,
        config=None
    ):


        config = config or {}


        elements = []



        walls = building_elements.get(
            "walls",
            []
        )


        openings = building_elements.get(
            "openings",
            []
        )



        # -----------------------
        # Walls
        # -----------------------

        for wall in walls:


            elements.append(

                {

                    "type":
                    "IfcWall",


                    "properties":
                    {

                        "facade":
                        wall.get(
                            "facade"
                        ),


                        "length":
                        wall.get(
                            "length"
                        ),


                        "height":
                        wall.get(
                            "height"
                        ),


                        "thickness":
                        wall.get(
                            "thickness"
                        ),


                        "material":
                        "reinforced_concrete"

                    }

                }

            )



        # -----------------------
        # Openings
        # -----------------------

        for opening in openings:


            if opening.get(
                "type"
            ) == "window":


                elements.append(

                    {

                        "type":
                        "IfcWindow",


                        "properties":
                        {

                            "facade":
                            opening.get(
                                "facade"
                            ),


                            "width":
                            opening.get(
                                "width"
                            ),


                            "height":
                            opening.get(
                                "height"
                            ),


                            "position":
                            opening.get(
                                "position"
                            )

                        }

                    }

                )


            elif opening.get(
                "type"
            ) == "door":


                elements.append(

                    {

                        "type":
                        "IfcDoor",


                        "properties":
                        opening

                    }

                )



        # Optional spaces

        spaces = config.get(
            "spaces",
            []
        )


        for space in spaces:


            elements.append(

                {

                    "type":
                    "IfcSpace",


                    "properties":
                    {

                        "name":
                        space

                    }

                }

            )



        return {


            "engine":
            "bim_element_assembly_v27.4",


            "status":
            "assembled",


            "elements":
            elements,


            "statistics":
            {

                "total_elements":
                len(elements),


                "walls":
                len(
                    [
                        e for e in elements
                        if e["type"]=="IfcWall"
                    ]
                ),


                "openings":
                len(
                    [
                        e for e in elements
                        if e["type"] in [
                            "IfcWindow",
                            "IfcDoor"
                        ]
                    ]
                )

            },


            "bim_ready":
            True

        }