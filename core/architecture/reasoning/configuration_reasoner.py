class ConfigurationReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🏛 CONFIGURATION REASONER v1.0 ONLINE"
        )



    def analyze(
        self,
        intent,
        site_analysis,
        space_data
    ):


        decision = {


            "building_strategy": {},

            "space_organization": {},

            "environmental_strategy": {},

            "access_strategy": {}

        }



        site = intent.get(
            "site",
            {}
        )


        climate = site.get(
            "climate",
            {}
        )


        orientation = site.get(
            "orientation",
            {}
        )


        south = None
        orientation_angle = None


        if isinstance(
            orientation,
            dict
        ):

            south = orientation.get(
                "south"
            )


        elif isinstance(
            orientation,
            (int, float)
        ):

            orientation_angle = float(
                orientation
            )


        # ==========================
        # BUILDING PLACEMENT LOGIC
        # ==========================


        if south:

            decision[
                "building_strategy"
            ] = {


                "approach":
                "building placement responds to street access and solar orientation",


                "open_space":
                "preserve meaningful outdoor space according to site conditions"

            }


        elif orientation_angle is not None:

            decision[
                "building_strategy"
            ] = {


                "approach":
                "building placement responds to parcel geometry and available site conditions",


                "open_space":
                "preserve meaningful outdoor space according to site conditions",


                "parcel_orientation_angle":
                orientation_angle

            }



        # ==========================
        # CLIMATE RESPONSE
        # ==========================


        if climate.get(
            "type"
        ) == "hot_dry":


            decision[
                "environmental_strategy"
            ] = {


                "daylight":
                "controlled natural light",


                "outdoor":
                "shaded outdoor areas preferred",


                "facade":
                "reduce uncontrolled solar exposure"

            }



        # ==========================
        # SPACE ORGANIZATION
        # ==========================


        spaces = space_data.get(
            "generated_spaces",
            []
        )



        public_spaces = []

        private_spaces = []



        for space in spaces:


            if space in [

                "living_room",

                "entrance",

                "dining",

                "kitchen"

            ]:

                public_spaces.append(
                    space
                )



            if space in [

                "bedroom",

                "bathroom"

            ]:

                private_spaces.append(
                    space
                )



        decision[
            "space_organization"
        ] = {


            "public_zone":
            public_spaces,


            "private_zone":
            private_spaces,


            "relationship_based":
            True

        }



        # ==========================
        # ACCESS
        # ==========================


        decision[
            "access_strategy"
        ] = {


            "main_access":
            site.get(
                "access",
                {}
            ).get(
                "main_access"
            ),


            "entrance_should_connect":
            "public_spaces"

        }



        return decision