import json
from pathlib import Path



class MaterialSelectionReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧱 MATERIAL SELECTION REASONER v1.0 ONLINE"
        )


        path = (
            Path(__file__).resolve().parent.parent
            / "knowledge"
            / "material_ontology.json"
        )


        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            self.knowledge = json.load(file)



    def select(
        self,
        style,
        facade_language,
        climate_strategy
    ):


        result = {

            "primary_materials": [],

            "secondary_materials": [],

            "material_logic": [],

            "source":
            "architectural_reasoning"

        }



        for name, data in self.knowledge["materials"].items():


            if style in data.get(
                "styles",
                []
            ):

                result[
                    "primary_materials"
                ].append(
                    name
                )


                result[
                    "material_logic"
                ].extend(
                    data.get(
                        "properties",
                        []
                    )
                )



        if style == "roman_classic":

            result[
                "secondary_materials"
            ].extend(
                [
                    "dark_metal",
                    "wood_entrance"
                ]
            )



        if "solar control" in str(
            climate_strategy
        ):

            result[
                "material_logic"
            ].append(
                "thermal_response_considered"
            )


        return result