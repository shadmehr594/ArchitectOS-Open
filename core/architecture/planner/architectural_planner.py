from core.architecture.model.architectural_design import ArchitecturalDesign


class ArchitecturalPlanner:

    VERSION = "1.0"


    def __init__(
        self,
        knowledge=None
    ):

        self.knowledge = knowledge



    def plan(
        self,
        site,
        intent
    ):

        design = ArchitecturalDesign()


        # -------------------------
        # Site Strategy
        # -------------------------

        design.site_strategy = {

            "site_area":
                site.area_estimate(),

            "orientation":
                site.north,

            "approach":
                "main entrance from accessible side"

        }


        # -------------------------
        # Spatial Planning
        # -------------------------

        if intent.building_type == "residential":


            design.levels.append(

                {

                    "name": "F1",

                    "spaces":[

                        "Entrance",

                        "Living",

                        "Kitchen",

                        "Dining",

                        "Guest WC",

                        "Parking"

                    ]

                }

            )


            design.levels.append(

                {

                    "name": "F2",

                    "spaces":[

                        "Master Bedroom",

                        "Bedrooms",

                        "Bathrooms",

                        "Terrace"

                    ]

                }

            )


        # -------------------------
        # Requirements
        # -------------------------

        for item in intent.requirements:

            design.relationships.append(

                {

                    "requirement": item,

                    "status": "considered"

                }

            )


        # -------------------------
        # Facade
        # -------------------------

        design.facade_strategy = {

            "style":
                intent.style,

            "opening_strategy":
                "controlled natural light"

        }


        return design