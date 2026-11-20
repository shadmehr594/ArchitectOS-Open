class BIMSystemMapper:


    def __init__(self):

        print(
            "⚙️ BIM System Mapper v37.0 ACTIVE"
        )


    def map(self,state):


        return {


            "materials":
                state.get(
                    "material_result",
                    {}
                ),


            "furniture":
                state.get(
                    "furniture_result",
                    {}
                ),


            "landscape":
                state.get(
                    "landscape_result",
                    {}
                ),


            "lighting":
                state.get(
                    "lighting_result",
                    {}
                ),


            "camera":
                state.get(
                    "camera_result",
                    {}
                )

        }