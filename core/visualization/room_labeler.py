class RoomLabeler:


    def __init__(self):

        print(
            "🏷️ Room Label Engine v22.4 ACTIVE"
        )


    def label(
        self,
        rooms
    ):

        labels=[]


        for room in rooms:

            labels.append(
                {
                    "text":
                        room["name"],

                    "position":[
                        room["x"]+1,
                        room["y"]+1
                    ]
                }
            )


        return {

            "engine":
                "room_labeler_v22.4",

            "labels":
                labels
        }