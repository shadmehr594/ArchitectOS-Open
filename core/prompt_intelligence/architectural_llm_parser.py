# ==========================================================
# ArchitectOS Architectural LLM Parser v1
# LLM -> Architectural Semantic Intent
#
# Experimental Layer
# Does not modify existing pipeline
# ==========================================================


import json


from core.llm.model_router import model_router



class ArchitecturalLLMParser:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧠 ARCHITECTURAL LLM PARSER v1 ONLINE"
        )



    def parse(
        self,
        text
    ):


        prompt = f"""

You are an architectural intelligence parser.

Analyze the complete architectural scene described by the user.

Extract ALL architectural entities including:

- building type
- architectural style
- materials
- objects placed in the scene
- vehicles
- furniture
- landscape elements
- environmental conditions
- camera
- lighting
- atmosphere

Do not ignore non-building objects.
If the user mentions a car, vehicle, tree, pool, furniture, people, or any visible element, include it inside "objects".

Convert the user architectural request into JSON.

Return ONLY valid JSON.

Schema:

{{
 "building": {{
    "type":"",
    "style":""
 }},
 "materials":[],
 "objects":[],
 "environment":[],
 "site":[],
 "camera":"",
 "lighting":"",
 "atmosphere":""
}}


User request:

{text}

"""


        try:


            result = model_router.generate(

                prompt,

                task="architecture"

            )


            if not result:


                return {}



            start = result.find("{")

            end = result.rfind("}")



            if start == -1 or end == -1:

                return {}



            json_text = result[start:end+1]



            data = json.loads(
                json_text
            )


            print(
                "🧠 LLM ARCHITECTURAL INTENT:",
                data
            )


            building = data.get(
                "building",
                {}
            )

            if not isinstance(
                building,
                dict
            ):
                building = {}


            normalized = {

                "building_type":
                    building.get(
                        "type",
                        ""
                    ),

                "style":
                    building.get(
                        "style",
                        ""
                    ),

                "materials":
                    data.get(
                        "materials",
                        []
                    ),

                "objects":
                    data.get(
                        "objects",
                        []
                    ),

                "environment":
                    data.get(
                        "environment",
                        []
                    ),

                "site":
                    data.get(
                        "site",
                        []
                    ),

                "camera":
                    data.get(
                        "camera",
                        ""
                    ),

                "lighting":
                    data.get(
                        "lighting",
                        ""
                    ),

                "atmosphere":
                    data.get(
                        "atmosphere",
                        ""
                    )

            }


            print(
                "🧠 NORMALIZED ARCHITECTURAL INTENT:",
                normalized
            )


            return normalized



        except Exception as e:


            print(
                "❌ ARCHITECTURAL LLM PARSER ERROR:",
                e
            )


            return {}





# singleton

architectural_llm_parser = ArchitecturalLLMParser()