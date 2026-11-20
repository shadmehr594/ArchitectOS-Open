import json
from pathlib import Path



class FacadeLanguageReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🏛 FACADE LANGUAGE REASONER v1.0 ONLINE"
        )


        path = (
            Path(__file__).resolve().parent.parent
            / "knowledge"
            / "facade_language_ontology.json"
        )


        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            self.knowledge = json.load(file)



    def analyze(
        self,
        style_analysis
    ):


        styles = style_analysis.get(
            "style_candidates",
            []
        )


        result = {

            "composition": [],

            "elements": [],

            "materials": [],

            "source":
            "architectural_knowledge"

        }



        for style in styles:


            data = self.knowledge[
                "facade_languages"
            ].get(
                style,
                {}
            )


            result["composition"].extend(
                data.get(
                    "composition",
                    []
                )
            )


            result["elements"].extend(
                data.get(
                    "elements",
                    []
                )
            )


            result["materials"].extend(
                data.get(
                    "materials",
                    []
                )
            )


        return result