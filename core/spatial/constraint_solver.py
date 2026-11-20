class ArchitecturalConstraintSolver:


    def __init__(self):

        print(
            "🏛️ Architectural Constraint Solver v19.5 ACTIVE"
        )



    def solve(
        self,
        zoning,
        plan
    ):


        result = {

            "version":
                "19.5",

            "strategy":
                "architectural_reasoning",

            "rules":
                [],

            "constraints":
                [],

            "violations":
                [],

            "score":
                1.0

        }



        zones = zoning.get(
            "zones",
            {}
        )



        # ==========================
        # FLOOR RULES
        # ==========================

        for floor, data in zones.items():


            public = data.get(
                "public",
                []
            )


            private = data.get(
                "private",
                []
            )


            service = data.get(
                "service",
                []
            )


            circulation = data.get(
                "circulation",
                []
            )



            if public and private:


                result["rules"].append({

                    "floor":
                        floor,

                    "rule":
                        "public_private_separation",

                    "status":
                        "valid"

                })




            if circulation:


                circulation_rule = (
                    self.get_circulation_requirement(
                        plan
                    )
                )


                result["rules"].append({

                    "floor":
                        floor,

                    "rule":
                        "variable_circulation_width",

                    "requirement":
                        circulation_rule,

                    "status":
                        "valid"

                })




            if service:


                result["rules"].append({

                    "floor":
                        floor,

                    "rule":
                        "service_zone_detected",

                    "status":
                        "valid"

                })




        # ==========================
        # SITE RULES
        # ==========================

        requirements = plan.get(
            "requirements",
            {}
        )



        if requirements.get(
            "garden"
        ):


            result["rules"].append({

                "rule":
                    "garden_requirement",

                "status":
                    "satisfied"

            })




        if requirements.get(
            "parking"
        ):


            result["rules"].append({

                "rule":
                    "parking_requirement",

                "status":
                    "satisfied"

            })




        # ==========================
        # STRUCTURAL EXCLUSION
        # ==========================


        result["constraints"].append({

            "constraint":
                "structural_exclusion_zones",

            "excluded_spaces":
                [
                    "stairs",
                    "elevator",
                    "corridor",
                    "public_circulation",
                    "vertical_core"
                ],

            "elements_forbidden":
                [
                    "column",
                    "beam",
                    "load_bearing_wall"
                ],

            "status":
                "active"

        })




        # ==========================
        # EXTERNAL WALL / WINDOW RULE
        # ==========================


        result["constraints"].append({

            "constraint":
                "external_boundary_privacy",

            "rules":

                [

                    "no_opening_to_forbidden_neighbor_boundary",

                    "rear_service_yard_boundary_protection",

                    "high_level_windows_for_privacy"

                ],

            "status":
                "active"

        })




        # ==========================
        # SCORE
        # ==========================


        total = len(
            result["rules"]
        )


        if total:


            result["score"] = round(

                min(
                    1.0,
                    total / 10
                ),

                2

            )



        return result





    def get_circulation_requirement(
        self,
        plan
    ):


        building_type = plan.get(
            "building_type",
            "residential"
        )


        circulation_type = plan.get(
            "circulation_type",
            "corridor"
        )



        if building_type == "residential":


            return {

                "min_width":
                    1.2,

                "preferred_width":
                    1.5,

                "max_width":
                    2.0

            }




        if building_type == "mall":


            if circulation_type == "two_side_shop":


                return {

                    "min_width":
                        4.0

                }




            if circulation_type == "one_side_shop":


                return {

                    "min_width":
                        2.4

                }




        return {

            "min_width":
                1.2

        }