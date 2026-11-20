class ZoningSpatialEngine:


    def __init__(self):

        print("🏗️ Zoning Spatial Engine v19.3 ACTIVE")



    def generate(self, spatial, plan):


        zoning = {

            "version": "19.3",

            "zones": {},

            "orientation": {

                "north": None,
                "south": None,
                "east": None,
                "west": None

            },

            "strategy":
                "architectural_zoning"

        }



        for floor, data in spatial.get(
            "floors",
            {}
        ).items():


            rooms = data.get(
                "spaces",
                []
            )


            public = []
            private = []
            service = []
            circulation = []



            for room in rooms:

                if isinstance(room, dict):

                    room = (
                        room.get("type")
                        or
                        room.get("name")
                        or
                        ""
                    )


                name = room.lower()



                if any(
                    x in name
                    for x in [
                        "living",
                        "entrance",
                        "lobby"
                    ]
                ):

                    public.append(room)



                elif any(
                    x in name
                    for x in [
                        "bedroom",
                        "bathroom"
                    ]
                ):

                    private.append(room)



                elif any(
                    x in name
                    for x in [
                        "kitchen",
                        "parking"
                    ]
                ):

                    service.append(room)



                elif any(
                    x in name
                    for x in [
                        "core",
                        "stairs"
                    ]
                ):

                    circulation.append(room)



            zoning["zones"][floor] = {


                "public":
                    public,


                "private":
                    private,


                "service":
                    service,


                "circulation":
                    circulation

            }



        # SITE ZONING


        site = plan.get(
            "spaces",
            {}
        )


        zoning["site"] = {


            "garden":
                "landscape_zone"
                if "site" in site
                else None,


            "parking":
                "access_zone"
                if "parking" in str(site)
                else None


        }



        zoning["orientation"]["south"] = "garden"


        return zoning