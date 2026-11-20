class LayoutReasonerV2:


    VERSION = "2.0"


    def __init__(self):

        print(
            "📐 LAYOUT REASONER V2 ONLINE"
        )



    def generate(
        self,
        generated_spaces,
        relationships,
        site_analysis=None,
        design_concept=None
    ):


        layout = {

            "zones": {},

            "floor_distribution": {},

            "connections": [],

            "planning_logic": []

        }



        # ==================================
        # ZONE FROM KNOWLEDGE
        # ==================================

        for space in generated_spaces:


            zone = space.get(
                "zone",
                "unknown"
            )


            name = space.get(
                "name"
            )


            if zone not in layout["zones"]:

                layout["zones"][zone] = []


            layout["zones"][zone].append(
                name
            )



        # ==================================
        # FLOOR DISTRIBUTION
        # ==================================

        for space in generated_spaces:


            floor = space.get(
                "floor",
                "undefined"
            )


            name = space.get(
                "name"
            )

            if floor == "undefined":

                continue


            if floor not in layout["floor_distribution"]:

                layout["floor_distribution"][floor] = []


            layout["floor_distribution"][floor].append(
                name
            )



        # ==================================
        # RELATIONSHIPS
        # ==================================

        for relation in relationships:


            layout["connections"].append(

                {

                    "from":
                        relation.get("from"),

                    "to":
                        relation.get("to"),

                    "type":
                        relation.get("type")

                }

            )



        # ==================================
        # ARCHITECTURAL LOGIC
        # ==================================

        if "external" in layout["zones"]:


            layout["planning_logic"].append(

                "external_spaces_connected_to_public_zone"

            )


        if "private" in layout["zones"]:


            layout["planning_logic"].append(

                "private_zone_separated_from_public_zone"

            )


        if "service" in layout["zones"]:


            layout["planning_logic"].append(

                "service_zone_supports_public_spaces"

            )



        return layout