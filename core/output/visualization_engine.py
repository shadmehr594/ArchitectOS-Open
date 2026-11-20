class VisualizationEngine:


    def __init__(self):

        print(
            "🎨 Visualization Engine v21.3 ACTIVE"
        )


    def room_dimension(
        self,
        room_type,
        area
    ):

        """
        تبدیل مساحت به ابعاد تقریبی
        """

        if area <= 0:
            return 2, 2


        # نسبت طول به عرض تقریبی

        width = round(
            area ** 0.5,
            2
        )


        depth = round(
            area / width,
            2
        )


        return width, depth



    def generate(
        self,
        area_schedule
    ):


        visualization = {

            "engine":
                "visualization_engine_v21.3",

            "status":
                "generated",

            "floors":[]

        }



        floors = area_schedule.get(
            "area_schedule",
            {}
        )


        for floor_name, floor in floors.items():


            x = 0
            y = 0


            rooms = []


            spaces = floor.get(
                "spaces",
                {}
            )


            for name, area in spaces.items():


                width, depth = self.room_dimension(
                    name,
                    area
                )


                room = {

                    "name":
                        name,

                    "area":
                        area,

                    "x":
                        x,

                    "y":
                        y,

                    "width":
                        width,

                    "depth":
                        depth

                }


                rooms.append(
                    room
                )


                # چیدمان ساده خطی

                x += width



            visualization["floors"].append(

                {

                    "floor":
                        floor_name,

                    "rooms":
                        rooms

                }

            )


        return visualization