class FloorplanRenderer:


    def __init__(self):

        print(
            "🎨 Floorplan Renderer Engine v25.1 ACTIVE"
        )



    def render(
        self,
        bim,
        regulation=None
    ):


        objects = []


        elements = (
            bim
            .get("model", {})
            .get("elements", {})
        )


        # -----------------
        # ROOMS
        # -----------------

        for room in elements.get(
            "rooms",
            []
        ):

            objects.append({

                "type":
                "room",

                "name":
                room.get(
                    "name",
                    "unknown"
                ),

                "geometry":
                room.get(
                    "geometry",
                    "space_boundary"
                )

            })



        # -----------------
        # WALLS
        # -----------------

        for wall in elements.get(
            "walls",
            []
        ):

            objects.append({

                "type":
                "wall",

                "material":
                wall.get(
                    "material",
                    "unknown"
                ),

                "geometry":
                "wall_line"

            })



        # -----------------
        # OPENINGS
        # -----------------

        for opening in elements.get(
            "openings",
            []
        ):

            objects.append({

                "type":
                "opening",

                "opening_type":
                opening.get(
                    "type",
                    "unknown"
                ),

                "symbol":
                "opening_symbol"

            })



        return {

            "engine":
            "floorplan_renderer_v25.1",


            "status":
            "rendered",


            "view":{

                "type":
                "top_view",

                "projection":
                "2D"

            },


            "objects":
            objects,


            "regulation_checked":
            regulation is not None

        }