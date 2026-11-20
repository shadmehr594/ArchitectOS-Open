class SpatialPlanValidator:


    VERSION = "1.0"



    def __init__(self):

        print(
            "✅ SPATIAL PLAN VALIDATOR v1.0 ONLINE"
        )



    # ==================================================
    # SPACE EXISTENCE CHECK
    # ==================================================

    def check_required_spaces(
        self,
        plan
    ):


        required = [

            "lobby",
            "retail",
            "public_circulation"

        ]


        existing = []


        for level in plan.get(
            "building",
            {}
        ).values():


            for space in level.get(
                "spaces",
                []
            ):

                existing.append(
                    space.get(
                        "name"
                    )
                )



        results = []



        for item in required:


            results.append({

                "space":
                    item,

                "exists":
                    item in existing

            })



        return results



    # ==================================================
    # CONNECTION CHECK
    # ==================================================

    def check_connections(
        self,
        plan
    ):


        checks = []



        connections = plan.get(
            "connections",
            []
        )



        required_links = [


            (
                "parking",
                "lobby"
            ),


            (
                "retail",
                "public_circulation"
            )

        ]



        for source, target in required_links:


            found = False



            for connection in connections:


                if (

                    connection.get(
                        "from"
                    )
                    ==
                    source

                    and

                    connection.get(
                        "to"
                    )
                    ==
                    target

                ):

                    found = True



            checks.append({

                "connection":

                    f"{source}->{target}",

                "exists":
                    found

            })



        return checks



    # ==================================================
    # ZONE CHECK
    # ==================================================

    def check_zones(
        self,
        plan
    ):


        result = []



        for level_name, level in plan.get(
            "building",
            {}
        ).items():


            for space in level.get(
                "spaces",
                []
            ):


                if space.get(
                    "name"
                ) == "parking":


                    result.append({

                        "rule":
                            "parking_service_zone",

                        "passed":
                            space.get(
                                "zone"
                            )
                            ==
                            "service"

                    })



        return result



    # ==================================================
    # MAIN VALIDATION
    # ==================================================

    def validate(
        self,
        plan
    ):


        checks = {


            "required_spaces":

                self.check_required_spaces(
                    plan
                ),


            "connections":

                self.check_connections(
                    plan
                ),


            "zones":

                self.check_zones(
                    plan
                )

        }



        passed = True



        for group in checks.values():


            for item in group:


                if item.get(
                    "exists"
                ) is False:


                    passed = False



                if item.get(
                    "passed"
                ) is False:


                    passed = False



        return {


            "validation":

                "passed"
                if passed
                else
                "failed",


            "checks":

                checks,


            "metadata": {

                "engine":
                    "Spatial Plan Validator",

                "version":
                    self.VERSION

            }

        }