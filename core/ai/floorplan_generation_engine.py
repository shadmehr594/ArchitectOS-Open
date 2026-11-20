class FloorplanGenerationEngine:


    def __init__(self):

        print(
            "📐 AI Floorplan Generation Engine v27.0 ACTIVE"
        )



    def generate(
        self,
        spatial_plan,
        site=None
    ):


        floors = spatial_plan.get(
            "floors",
            {}
        )


        generated = {}



        for floor_name, floor_data in floors.items():


            spaces = floor_data.get(
                "spaces",
                []
            )


            rooms = []


            x = 0
            y = 0



            for space in spaces:


                width = 3
                depth = 3



                # basic space sizing

                if space == "parking":

                    width = 6
                    depth = 5


                elif space == "living":

                    width = 5
                    depth = 4


                elif space == "kitchen":

                    width = 3
                    depth = 3


                elif "bedroom" in space:

                    width = 3.5
                    depth = 3.5


                elif space == "terrace":

                    width = 3
                    depth = 2



                rooms.append(

                    {

                        "name": space,

                        "geometry":

                        {

                            "x": x,

                            "y": y,

                            "width": width,

                            "depth": depth

                        }

                    }

                )



                x += width



            generated[floor_name] = {


                "zone":
                floor_data.get(
                    "zone"
                ),


                "rooms":
                rooms


            }



        return {


            "engine":
            "floorplan_generation_v27.0",


            "status":
            "generated",


            "site":
            site,


            "floorplans":
            generated,


            "circulation":
            {

                "stairs":
                spatial_plan.get(
                    "vertical_core",
                    {}
                ).get(
                    "stairs",
                    False
                ),


                "access":
                spatial_plan.get(
                    "vertical_core",
                    {}
                ).get(
                    "access"
                )

            }

        }