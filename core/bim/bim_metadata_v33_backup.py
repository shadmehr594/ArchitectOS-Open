class BIMMetadataEngine:


    def __init__(self):

        print(
            "🏗️ BIM Metadata Engine v23.2 ACTIVE"
        )


    def enrich(
        self,
        bim_model
    ):


        metadata = {

            "walls": [],

            "openings": [],

            "rooms": []

        }


        elements = bim_model.get(
            "model",
            {}
        ).get(
            "elements",
            {}
        )


        # ----------------------
        # Rooms Metadata
        # ----------------------

        for room in elements.get(
            "rooms",
            []
        ):

            metadata["rooms"].append(

                {
                    "name":
                        room.get("name"),

                    "category":
                        "space",

                    "usage":
                        room.get(
                            "name",
                            "unknown"
                        )

                }

            )


        # ----------------------
        # Walls Metadata
        # ----------------------

        for wall in elements.get(
            "walls",
            []
        ):

            metadata["walls"].append(

                {
                    "floor":
                        wall.get("floor"),

                    "material":
                        "reinforced_concrete",

                    "thickness":
                        20,

                    "fire_rating":
                        "120min"

                }

            )


        # ----------------------
        # Openings Metadata
        # ----------------------

        for opening in elements.get(
            "openings",
            []
        ):

            metadata["openings"].append(

                {
                    "type":
                        opening.get(
                            "type"
                        ),

                    "material":
                        "aluminium_glass",

                    "thermal_rating":
                        "A"

                }

            )


        return {

            "engine":
                "bim_metadata_v23.2",

            "status":
                "enriched",

            "metadata":
                metadata

        }