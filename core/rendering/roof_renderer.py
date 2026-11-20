class RoofRenderer:


    def __init__(self):

        print(
            "🏠 Roof Renderer Engine v25.4 ACTIVE"
        )


    def render(
        self,
        roof_plan
    ):


        zones = []

        source = (
            roof_plan
            .get("roof_plan", {})
            .get("zones", [])
        )


        for zone in source:

            zones.append({

                "zone":
                zone.get(
                    "zone",
                    "unknown"
                ),

                "type":
                zone.get(
                    "type",
                    "unknown"
                ),

                "water_retention":
                zone.get(
                    "water_retention",
                    False
                )

            })


        return {

            "engine":
            "roof_renderer_v25.4",


            "status":
            "rendered",


            "view":
            "roof_plan",


            "roof":{

                "zones":
                zones

            }

        }