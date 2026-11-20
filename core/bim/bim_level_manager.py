class BIMLevelManager:


    """
    BIM Level Manager v38.0

    Central Level Intelligence

    Responsibilities:

        Elements
            |
            v
        Level Detection

            |
            +-- LEVEL_0
            +-- LEVEL_1
            +-- LEVEL_2


        LEVEL <-> Elevation Mapping


    Single Source Of Truth
    """


    FLOOR_HEIGHT = 3.0



    def __init__(self):

        print(
            "🏢 BIM Level Manager v38.0 ACTIVE"
        )



    # ==================================================
    # GENERATE LEVELS
    # ==================================================

    def generate(
        self,
        elements
    ):


        print(
            "▶️ GENERATE BIM LEVELS v38"
        )


        levels = {}



        for element in elements:



            level_id = self.get_level(
                element
            )



            if not level_id:

                continue



            if level_id not in levels:



                index = self.level_index(
                    level_id
                )



                levels[level_id] = {


                    "id":

                        level_id,



                    "name":

                        f"Floor {index}",



                    "index":

                        index,



                    "elevation":

                        self.elevation(
                            index
                        ),



                    "height":

                        self.FLOOR_HEIGHT,



                    "elements":

                        []

                }




            element_id = element.get(
                "id"
            )


            if element_id:


                levels[level_id]["elements"].append(

                    element_id

                )




        result = list(
            levels.values()
        )



        print(

            f"🏢 LEVELS GENERATED: {len(result)}"

        )


        return result





    # ==================================================
    # GET LEVEL FROM ELEMENT
    # ==================================================

    def get_level(
        self,
        element
    ):


        level = element.get(
            "level"
        )


        if level:

            return level



        position = element.get(
            "position",
            {}
        )



        z = position.get(
            "z"
        )



        if z is not None:


            index = round(

                z /
                self.FLOOR_HEIGHT

            )


            return f"LEVEL_{index}"



        return "LEVEL_0"





    # ==================================================
    # LEVEL INDEX
    # ==================================================

    def level_index(
        self,
        level_id
    ):


        try:

            return int(

                level_id.split("_")[-1]

            )


        except:


            return 0





    # ==================================================
    # LEVEL -> ELEVATION
    # ==================================================

    def elevation(
        self,
        index
    ):


        return (

            index
            *
            self.FLOOR_HEIGHT

        )





    # ==================================================
    # ELEVATION -> LEVEL
    # ==================================================

    def level_from_elevation(
        self,
        z
    ):


        index = round(

            z /
            self.FLOOR_HEIGHT

        )


        return f"LEVEL_{index}"





    # ==================================================
    # NORMALIZE LEVEL DATA
    # ==================================================

    def normalize(
        self,
        element
    ):


        print("\n====== LEVEL NORMALIZATION DEBUG ======")

        for level, data in levels.items():
            print(
                "LEVEL:",
                level,
                "ELEVATION:",
                data.get("elevation"),
                "Z:",
                data.get("z")
            )


        level = self.get_level(
            element
        )


        index = self.level_index(
            level
        )


        element["level"] = level



        element["elevation"] = self.elevation(
            index
        )


        return element