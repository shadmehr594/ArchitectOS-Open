import json
from pathlib import Path



class ClimateFacadeAdaptationReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "☀️ CLIMATE FACADE ADAPTATION REASONER v1.0 ONLINE"
        )


        path = (
            Path(__file__).resolve().parent.parent
            / "knowledge"
            / "climate_facade_ontology.json"
        )


        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            self.knowledge = json.load(file)



    def analyze(
        self,
        site_analysis,
        facade_language
    ):


        climate = (
            site_analysis
            .get(
                "climate_response",
                {}
            )
            .get(
                "type",
                "hot_dry"
            )
        )


        result = {

            "climate": climate,

            "strategies": [],

            "facade_modifications": [],

            "orientation_response": [],

            "source":
            "architectural_reasoning"

        }



        climate_data = self.knowledge[
            "climates"
        ].get(
            climate,
            {}
        )


        result["strategies"].extend(
            climate_data.get(
                "strategies",
                []
            )
        )


        result["facade_modifications"].extend(
            climate_data.get(
                "facade_modifications",
                []
            )
        )



        orientation = (
            site_analysis
            .get(
                "site",
                {}
            )
            .get(
                "orientation",
                {}
            )
        )


        orientation_directions = []


        if isinstance(
            orientation,
            dict
        ):

            orientation_directions = [
                direction
                for direction, value in orientation.items()
                if value
            ]


        elif isinstance(
            orientation,
            (list, tuple, set)
        ):

            orientation_directions = list(
                orientation
            )


        elif isinstance(
            orientation,
            str
        ):

            orientation_directions = [
                orientation
            ]


        elif isinstance(
            orientation,
            (int, float)
        ):

            # Numeric orientation represents parcel geometry angle.
            # It must not be interpreted as a geographic facade direction.
            orientation_directions = []


        for direction in orientation_directions:


            rules = self.knowledge[
                "orientation_rules"
            ].get(
                direction,
                []
            )


            result["orientation_response"].extend(
                rules
            )



        return result