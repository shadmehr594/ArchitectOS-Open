class BIMModelAdapter:

    VERSION = "1.0"


    def __init__(self):

        print(
            "🏗 BIM MODEL ADAPTER v1.0 ONLINE"
        )



    # ==================================================
    # LEVEL EXTRACTION
    # ==================================================

    def extract_levels(
        self,
        layout
    ):

        levels = []


        if not isinstance(
            layout,
            dict
        ):

            return levels



        for level_name, level_data in layout.items():


            if not isinstance(
                level_data,
                dict
            ):

                continue



            levels.append(

                {

                    "name":
                        level_name,


                    "level":
                        level_name

                }

            )


        return levels



    # ==================================================
    # SPACE EXTRACTION
    # ==================================================

    def extract_spaces(
        self,
        layout
    ):

        spaces = []


        if not isinstance(
            layout,
            dict
        ):

            return spaces



        for level_name, level_data in layout.items():


            if not isinstance(
                level_data,
                dict
            ):

                continue



            level_spaces = level_data.get(
                "spaces",
                []
            )



            if not isinstance(
                level_spaces,
                list
            ):

                continue



            for space in level_spaces:


                if isinstance(
                    space,
                    dict
                ):


                    spaces.append(

                        {

                            "name":
                                space.get(
                                    "name",
                                    "space"
                                ),


                            "type":
                                space.get(
                                    "zone",
                                    "architectural_space"
                                ),


                            "zone":
                                space.get(
                                    "zone"
                                ),


                            "position":
                                space.get(
                                    "position"
                                ),


                            "level":
                                level_name

                        }

                    )


                elif isinstance(
                    space,
                    str
                ):


                    spaces.append(

                        {

                            "name":
                                space,


                            "type":
                                "architectural_space",


                            "zone":
                                None,


                            "level":
                                level_name

                        }

                    )



        return spaces



    # ==================================================
    # ELEMENT GENERATION
    # ==================================================

    def generate_elements(
        self,
        spaces
    ):

        elements = []


        for index, space in enumerate(spaces):


            elements.append(

                {

                    "id":
                        f"space_{index+1}",


                    "category":
                        "IfcSpace",


                    "name":
                        space.get(
                            "name"
                        ),


                    "level":
                        space.get(
                            "level"
                        )

                }

            )


        return elements



    # ==================================================
    # ADAPT
    # ==================================================

    def adapt(
        self,
        building_model
    ):


        if not isinstance(
            building_model,
            dict
        ):

            building_model = {}



        layout = building_model.get(
            "layout",
            {}
        )



        levels = self.extract_levels(
            layout
        )



        spaces = self.extract_spaces(
            layout
        )



        elements = self.generate_elements(
            spaces
        )



        print(
            "🏗 BIM LEVELS:",
            levels
        )


        print(
            "🏗 BIM SPACES:",
            spaces
        )


        print(
            "🏗 BIM ELEMENTS:",
            elements
        )



        return {


            "project":

                building_model.get(
                    "building",
                    {}
                ),



            "levels":

                levels,



            "spaces":

                spaces,



            "elements":

                elements,



            "metadata":

            {

                "engine":
                    "BIMModelAdapter",


                "version":
                    self.VERSION

            }

        }