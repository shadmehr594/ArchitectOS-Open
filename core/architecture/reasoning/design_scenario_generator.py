class DesignScenarioGenerator:


    VERSION = "1.0"



    def __init__(self):

        print(
            "💡 DESIGN SCENARIO GENERATOR v1.0 ONLINE"
        )



    def generate(
        self,
        intent,
        site_analysis,
        massing_analysis
    ):


        scenarios = []



        options = massing_analysis.get(
            "massing_options",
            []
        )



        for option in options:


            mass_type = option.get(
                "type"
            )


            if mass_type == "l_shaped_massing":


                scenarios.append(

                    {

                        "name":
                        "garden_relationship_strategy",


                        "massing":
                        mass_type,


                        "concept":
                        [
                            "connect main living spaces with outdoor landscape",
                            "create semi_private outdoor space"
                        ],


                        "site_response":
                        [
                            "use open edge toward preferred outdoor side"
                        ]

                    }

                )



            elif mass_type == "courtyard_massing":


                scenarios.append(

                    {

                        "name":
                        "central_courtyard_strategy",


                        "massing":
                        mass_type,


                        "concept":
                        [
                            "create internal architectural focus",
                            "improve privacy and controlled daylight"
                        ],


                        "site_response":
                        [
                            "respond to neighboring boundaries"
                        ]

                    }

                )



            elif mass_type == "compact_block":


                scenarios.append(

                    {

                        "name":
                        "protected_compact_strategy",


                        "massing":
                        mass_type,


                        "concept":
                        [
                            "create efficient unified volume",
                            "protect private spaces"
                        ],


                        "site_response":
                        [
                            "reduce uncontrolled exposure"
                        ]

                    }

                )



        return {


            "scenarios":
            scenarios,


            "source":
            "architectural_reasoning"

        }