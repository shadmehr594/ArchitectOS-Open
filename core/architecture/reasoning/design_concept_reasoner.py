class DesignConceptReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "💡 DESIGN CONCEPT REASONER v1.0 ONLINE"
        )



    def generate(
        self,
        intent,
        site_analysis,
        configuration
    ):


        concept = {


            "design_principles": [],

            "spatial_idea": [],

            "environmental_idea": [],

            "architectural_character": []

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
        # SITE BASED CONCEPT
        # ==========================


        if south:


            concept[
                "design_principles"
            ].append(

                "respond to site orientation and access"

            )


            concept[
                "spatial_idea"
            ].append(

                "connect main living spaces with meaningful outdoor areas"

            )


        elif orientation_angle is not None:


            concept[
                "design_principles"
            ].append(

                "respond to parcel geometry and site access"

            )



        # ==========================
        # CLIMATE CONCEPT
        # ==========================


        if climate.get(
            "type"
        ) == "hot_dry":


            concept[
                "environmental_idea"
            ].extend(

                [

                    "controlled daylight",

                    "shaded outdoor relationship",

                    "reduce direct solar gain"

                ]

            )



        # ==========================
        # SPACE LOGIC
        # ==========================


        organization = configuration.get(
            "space_organization",
            {}
        )



        if organization.get(
            "private_zone"
        ):


            concept[
                "spatial_idea"
            ].append(

                "separate private and public experiences"

            )



        # ==========================
        # ARCHITECTURAL CHARACTER
        # ==========================


        style = intent.get(
            "style"
        )



        if style:


            concept[
                "architectural_character"
            ].append(

                f"{style} architectural expression"

            )



        return concept