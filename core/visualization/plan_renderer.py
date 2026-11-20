class PlanRenderer:


    def __init__(self):

        print(
            "📐 Plan Renderer Engine v22.1 ACTIVE"
        )


    def render(
        self,
        spatial,
        area_schedule=None,
        plan=None
    ):

        floors = {}

        for floor_name, floor in spatial.get(
            "floors",
            {}
        ).items():

            rooms = []

            spaces = floor.get(
                "spaces",
                []
            )

            x = 0
            y = 0


            for space in spaces:

                rooms.append(
                    {
                        "name": space,
                        "x": x,
                        "y": y,
                        "width": 3,
                        "depth": 3,
                        "type": space
                    }
                )

                x += 3


            floors[floor_name] = {
                "rooms": rooms
            }


        return {

            "engine":
                "plan_renderer_v22.1",

            "status":
                "generated",

            "floors":
                floors
        }