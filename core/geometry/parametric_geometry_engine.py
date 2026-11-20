class ParametricGeometryEngine:


    def __init__(self):

        print(
            "📐 Parametric Geometry Engine v27.1 ACTIVE"
        )



    def generate(
        self,
        floorplans,
        config=None
    ):


        config = config or {}



        wall_thickness = config.get(
            "wall_thickness",
            0.20
        )


        separation_joint = config.get(
            "separation_joint",
            {
                "enabled": False,
                "value_cm": 10
            }
        )


        overhang = config.get(
            "overhang",
            {
                "enabled": False
            }
        )



        geometry = {


            "walls": [],

            "openings": [],

            "envelope": {},

            "floors": {}

        }



        for floor, data in floorplans.items():


            rooms = data.get(
                "rooms",
                []
            )


            geometry["floors"][floor] = []


            for room in rooms:


                g = room.get(
                    "geometry",
                    {}
                )


                geometry["floors"][floor].append(

                    {

                        "space":
                        room.get(
                            "name"
                        ),

                        "boundary":
                        g

                    }

                )



                # room boundary walls

                geometry["walls"].append(

                    {

                        "floor":
                        floor,

                        "type":
                        "room_boundary",

                        "material":
                        "reinforced_concrete",

                        "thickness":
                        wall_thickness

                    }

                )



        # building envelope

        geometry["envelope"] = {


            "type":
            "residential",


            "wall_thickness":
            wall_thickness


        }



        # optional regulation

        geometry["separation_joint"] = {


            "enabled":
            separation_joint.get(
                "enabled",
                False
            ),


            "value_cm":
            separation_joint.get(
                "value_cm",
                0
            )

        }



        # optional overhang

        geometry["overhang"] = {


            "enabled":
            overhang.get(
                "enabled",
                False
            ),


            "projection_m":
            overhang.get(
                "projection_m",
                0
            )

        }



        return {


            "engine":
            "parametric_geometry_v27.1",


            "status":
            "generated",


            "geometry":
            geometry


        }