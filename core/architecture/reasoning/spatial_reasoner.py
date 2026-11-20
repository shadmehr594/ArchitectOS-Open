class SpatialReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧩 SPATIAL REASONER v1.0 ONLINE"
        )



    def analyze(
        self,
        spaces,
        site_analysis=None
    ):


        result = {


            "zones": {},


            "relationships": [],


            "spatial_strategy": {}

        }



        site_analysis = site_analysis or {}



        # ==================================
        # CLASSIFY SPACES
        # ==================================

        public_spaces = [

            "living_room",
            "dining",
            "lobby",
            "reception"

        ]


        private_spaces = [

            "bedroom",
            "office_room",
            "clinic_room"

        ]


        service_spaces = [

            "kitchen",
            "service_core",
            "parking"

        ]



        external_spaces = [

            "garden",
            "pool",
            "terrace",
            "yard"

        ]



        for space in spaces:


            if space in public_spaces:


                result[
                    "zones"
                ].setdefault(

                    "public",

                    []

                ).append(
                    space
                )



            elif space in private_spaces:


                result[
                    "zones"
                ].setdefault(

                    "private",

                    []

                ).append(
                    space
                )



            elif space in service_spaces:


                result[
                    "zones"
                ].setdefault(

                    "service",

                    []

                ).append(
                    space
                )



            elif space in external_spaces:


                result[
                    "zones"
                ].setdefault(

                    "external",

                    []

                ).append(
                    space
                )



        # ==================================
        # RELATIONSHIP REASONING
        # ==================================


        if (

            "living_room" in spaces

            and

            "garden" in spaces

        ):


            result[
                "relationships"
            ].append(

                {

                    "from":
                        "living_room",

                    "to":
                        "garden",

                    "relation":
                        "direct_connection"

                }

            )



        if (

            "living_room" in spaces

            and

            "pool" in spaces

        ):


            result[
                "relationships"
            ].append(

                {

                    "from":
                        "living_room",

                    "to":
                        "pool",

                    "relation":
                        "visual_and_access_connection"

                }

            )



        if (

            "bedroom" in spaces

            and

            "bathroom" in spaces

        ):


            result[
                "relationships"
            ].append(

                {

                    "from":
                        "bedroom",

                    "to":
                        "bathroom",

                    "relation":
                        "private_connection"

                }

            )



        # ==================================
        # SITE RESPONSE
        # ==================================


        open_space = (

            site_analysis

            .get(

                "open_space_strategy",

                {}

            )

            .get(

                "preferred_location"

            )

        )



        if open_space:


            result[
                "spatial_strategy"
            ][
                "open_space_response"
            ] = open_space



        result[
            "spatial_strategy"
        ][
            "organization"
        ] = (

            "spaces organized according to privacy, access and functional relationships"

        )



        return result