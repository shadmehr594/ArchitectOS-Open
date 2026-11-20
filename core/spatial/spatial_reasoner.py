class SpatialReasoner:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🧠 SPATIAL REASONER ENGINE v1.0 ONLINE"
        )



    # ==================================================
    # CONNECTION RULES
    # ==================================================

    def analyze_connections(
        self,
        spatial_model
    ):

        rules = []


        for connection in spatial_model.get(
            "connections",
            []
        ):


            source = connection.get(
                "source"
            )

            target = connection.get(
                "target"
            )

            behavior = connection.get(
                "behavior"
            )



            if behavior == "direct_access":


                rules.append(

                    {

                        "type":
                            "connection_rule",

                        "spaces":
                            [
                                source,
                                target
                            ],

                        "rule":
                            "direct indoor outdoor relationship"

                    }

                )



            elif behavior == "connected":


                rules.append(

                    {

                        "type":
                            "adjacency_rule",

                        "spaces":
                            [
                                source,
                                target
                            ],

                        "rule":
                            "functional adjacency required"

                    }

                )



            elif behavior == "adjacent":


                rules.append(

                    {

                        "type":
                            "adjacency_rule",

                        "spaces":
                            [
                                source,
                                target
                            ],

                        "rule":
                            "close spatial relationship"

                    }

                )


        return rules




    # ==================================================
    # ZONE RULES
    # ==================================================

    def analyze_zones(
        self,
        zones
    ):


        rules = []


        for zone, spaces in zones.items():


            for space in spaces:


                if zone == "private":


                    rules.append(

                        {

                            "type":
                                "privacy_rule",

                            "space":
                                space,

                            "rule":
                                "keep separated from public circulation"

                        }

                    )



                elif zone == "external":


                    rules.append(

                        {

                            "type":
                                "external_zone_rule",

                            "space":
                                space,

                            "rule":
                                "outdoor relationship required"

                        }

                    )



                elif zone == "service":


                    rules.append(

                        {

                            "type":
                                "service_rule",

                            "space":
                                space,

                            "rule":
                                "service accessibility required"

                        }

                    )



        return rules




    # ==================================================
    # SITE RULES
    # ==================================================

    def analyze_site(
        self,
        site_model
    ):


        rules = []


        position = site_model.get(
            "position"
        )


        if position:

            side = position.get(
                "side"
            )


            if side:


                rules.append(

                    {

                        "type":
                            "site_position_rule",

                        "rule":
                            f"building positioned on {side} side"

                    }

                )



        setbacks = site_model.get(
            "setbacks",
            {}
        )


        for key, value in setbacks.items():


            if value:


                rules.append(

                    {

                        "type":
                            "setback_rule",

                        "rule":
                            key

                    }

                )



        return rules




    # ==================================================
    # MAIN REASONING
    # ==================================================

    def reason(
        self,
        spatial_model
    ):


        result = {


            "rules": [],


            "summary": {

                "connections": 0,

                "zones": 0,

                "site": 0

            }

        }



        connection_rules = self.analyze_connections(
            spatial_model
        )


        zone_rules = self.analyze_zones(

            spatial_model.get(
                "zones",
                {}
            )

        )


        site_rules = self.analyze_site(
            spatial_model.get(
                "site_model",
                {}
            )
        )



        result["rules"].extend(
            connection_rules
        )


        result["rules"].extend(
            zone_rules
        )


        result["rules"].extend(
            site_rules
        )


        result["summary"]["connections"] = len(
            connection_rules
        )


        result["summary"]["zones"] = len(
            zone_rules
        )


        result["summary"]["site"] = len(
            site_rules
        )


        return result