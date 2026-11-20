class BIMObjectIntelligenceEngine:


    """
    BIM Object Intelligence Engine v41.1
    """


    def __init__(self):

        print(
            "🪑 BIM Object Intelligence Engine v41.1 ACTIVE"
        )



    def build(
        self,
        rooms
    ):


        print(
            "▶️ BUILD BIM OBJECT INTELLIGENCE v41.1"
        )


        objects = []



        room_list = rooms.get(
            "rooms",
            []
        )


        for index, room in enumerate(room_list):


            room_id = room.get(
                "id",
                f"ROOM_{index}"
            )


            obj = {


                "id":
                    f"OBJECT_{room_id}",


                "category":
                    "bim_object",


                "room":
                    room_id,


                "level":
                    room.get(
                        "level"
                    ),


                "type":
                    "generic_room",


                "function":
                    self._detect_function(
                        room
                    ),


                "properties":
                {

                    "semantic":
                        True

                }

            }


            objects.append(
                obj
            )



        result = {


            "engine":

                "bim_object_intelligence_v41.1",


            "status":

                "generated",


            "objects":

                objects

        }



        print(
            f"🪑 OBJECTS GENERATED: {len(objects)}"
        )


        return result





    def _detect_function(
        self,
        room
    ):


        room_type = room.get(
            "type",
            ""
        )


        if "main" in room_type:

            return "living_room"


        return "generic_room"