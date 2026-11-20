class ArchitecturalLayoutEngine:

    VERSION = "2.0"


    def generate(self, planning):

        layout = {}

        planner_layout = planning.get(
            "layout",
            {}
        )


        for level, floor in planner_layout.items():

            spaces = floor.get(
                "spaces",
                []
            )


            if spaces:

                layout[level] = self.solve_floor(
                    spaces
                )


        return {

            "layout_engine": self.VERSION,

            "levels": layout

        }



    def solve_floor(self, spaces):

        result = []


        cursor_x = 0


        envelope_width = 12
        envelope_height = 10


        zones = {

            "public": {

                "y":0,
                "height":5

            },

            "private": {

                "y":5,
                "height":5

            },

            "service": {

                "y":0,
                "height":5

            }

        }



        for space in spaces:


            zone = space.get(
                "zone",
                "public"
            )


            width = 4
            height = 4


            if cursor_x + width > envelope_width:

                cursor_x = 0



            zone_data = zones.get(
                zone,
                zones["public"]
            )


            room = {

                "name":
                    space.get("name"),


                "level":
                    space.get("level"),


                "zone":
                    zone,


                "geometry":{


                    "x":
                        cursor_x,


                    "y":
                        zone_data["y"],


                    "width":
                        width,


                    "height":
                        height

                }

            }


            result.append(room)


            cursor_x += width



        return result