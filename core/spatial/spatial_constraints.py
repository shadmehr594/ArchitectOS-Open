class SpatialConstraintEngine:


    VERSION = "1.1"



    def __init__(self):

        print(
            "🧠 SPATIAL CONSTRAINT INTELLIGENCE v1.1 ONLINE"
        )



    # ==================================================
    # HELPERS
    # ==================================================

    def priority_level(
        self,
        rule_type
    ):


        high_priority = [

            "connection_rule",
            "privacy_rule",
            "site_position_rule",
            "setback_rule"

        ]


        if rule_type in high_priority:

            return "high"


        return "medium"



    def relationship_behavior(
        self,
        rule
    ):


        text = rule.get(
            "rule",
            ""
        )



        behavior = {

            "type":
                "adjacency",


            "distance":
                "near",


            "visual_connection":
                False,


            "physical_connection":
                False

        }



        if "direct" in text:


            behavior["type"] = (
                "direct_access"
            )


            behavior["distance"] = (
                "immediate"
            )


            behavior["physical_connection"] = True


            behavior["visual_connection"] = True



        elif "connected" in text:


            behavior["type"] = (
                "connected"
            )


            behavior["distance"] = (
                "near"
            )


            behavior["visual_connection"] = True



        return behavior



    def severity(
        self,
        rule_type
    ):


        required = [

            "connection_rule",
            "privacy_rule",
            "site_position_rule",
            "setback_rule"

        ]


        if rule_type in required:

            return "required"


        return "preferred"
    # ==================================================
    # CONNECTION CONSTRAINT
    # ==================================================

    def build_connection_constraint(
        self,
        rule,
        rule_type
    ):


        spaces = rule.get(
            "spaces",
            []
        )



        if len(spaces) < 2:

            return None



        return {

            "constraint_type":
                "adjacency",


            "source":
                spaces[0],


            "target":
                spaces[1],


            "relationship":
                self.relationship_behavior(
                    rule
                ),


            "priority":
                self.priority_level(
                    rule_type
                ),


            "severity":
                self.severity(
                    rule_type
                )

        }



    # ==================================================
    # PRIVACY CONSTRAINT
    # ==================================================

    def build_privacy_constraint(
        self,
        rule
    ):


        return {

            "constraint_type":
                "privacy",


            "space":
                rule.get(
                    "space"
                ),


            "zone_logic":
            {

                "preferred_zone":
                    "private",


                "forbidden_zones":
                [

                    "public",
                    "circulation"

                ]

            },


            "priority":
                "high",


            "severity":
                "required"

        }



    # ==================================================
    # SERVICE CONSTRAINT
    # ==================================================

    def build_service_constraint(
        self,
        rule
    ):


        return {


            "constraint_type":
                "service_access",


            "space":
                rule.get(
                    "space"
                ),


            "access_logic":
            {

                "required":
                    True,


                "access_type":
                    "service"

            },


            "priority":
                "medium",


            "severity":
                "preferred"

        }



    # ==================================================
    # EXTERNAL RELATIONSHIP
    # ==================================================

    def build_external_constraint(
        self,
        rule
    ):


        return {


            "constraint_type":
                "external_relationship",


            "space":
                rule.get(
                    "space"
                ),


            "environment":
                "outdoor",


            "relationship":
            {

                "landscape_connection":
                    True,


                "visual_connection":
                    True

            },


            "priority":
                "medium",


            "severity":
                "preferred"

        }



    # ==================================================
    # SITE CONSTRAINT
    # ==================================================

    def build_site_constraint(
        self,
        rule
    ):


        return {


            "constraint_type":
                "site",


            "rule":
                rule.get(
                    "rule"
                ),


            "priority":
                "high",


            "severity":
                "required"

        }
    # ==================================================
    # MAIN GENERATOR
    # ==================================================

    def generate(
        self,
        reasoning
    ):


        constraints = []



        for rule in reasoning.get(
            "rules",
            []
        ):


            rule_type = rule.get(
                "type"
            )


            constraint = None



            # ------------------------------------------
            # Adjacency / Connection
            # ------------------------------------------

            if rule_type in [

                "connection_rule",

                "adjacency_rule"

            ]:


                constraint = (
                    self.build_connection_constraint(
                        rule,
                        rule_type
                    )
                )



            # ------------------------------------------
            # Privacy
            # ------------------------------------------

            elif rule_type == "privacy_rule":


                constraint = (
                    self.build_privacy_constraint(
                        rule
                    )
                )



            # ------------------------------------------
            # Service
            # ------------------------------------------

            elif rule_type == "service_rule":


                constraint = (
                    self.build_service_constraint(
                        rule
                    )
                )



            # ------------------------------------------
            # External
            # ------------------------------------------

            elif rule_type == "external_zone_rule":


                constraint = (
                    self.build_external_constraint(
                        rule
                    )
                )



            # ------------------------------------------
            # Site
            # ------------------------------------------

            elif rule_type in [

                "site_position_rule",

                "setback_rule"

            ]:


                constraint = (
                    self.build_site_constraint(
                        rule
                    )
                )



            if constraint:


                constraints.append(
                    constraint
                )



        return {


            "constraints":
                constraints,


            "metadata":
            {

                "version":
                    self.VERSION,


                "total_constraints":
                    len(
                        constraints
                    )

            }

        }