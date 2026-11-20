# ==========================================================
# ArchitectOS Semantic Intent Engine v1.2
# Natural Language Architectural Understanding Layer
#
# Persian User Text
#        |
#        ↓
# Semantic Understanding
#        |
#        ↓
# Architectural Intent JSON
#
# v1.2 Improvements:
#
# - Preserve full architectural meaning
# - Strong material/style extraction
# - Better facade intelligence
# - LLM primary reasoning
# - ArchitecturalIntent fallback
# - Stable JSON recovery
# ==========================================================


import json
import re




class SemanticIntentEngine:


    VERSION = "1.2"



    def __init__(
        self,
        llm=None,
        fallback=None
    ):


        self.llm = llm

        self.fallback = fallback


        print(
            "🧠 SEMANTIC INTENT ENGINE v1.2 ONLINE"
        )



    # ======================================================
    # SYSTEM PROMPT
    # ======================================================


    def system_prompt(
        self
    ):


        return """

You are ArchitectOS semantic architectural intelligence.

Convert Persian architectural requests into structured JSON.

You understand architectural design language.

Extract:

- building type
- architectural style
- facade style
- materials
- construction materials
- facade details
- objects
- object properties
- environment
- atmosphere
- camera
- lighting
- design constraints


Important rules:

1.
Do not reduce architectural descriptions into generic words.

Example:

"نمای کلاسیک با سنگ تراورتن"

must become:

{
 "style":"classical",
 "materials":["travertine stone"],
 "facade_details":[
   "stone frames",
   "cornices",
   "classical proportions",
   "symmetrical composition"
 ]
}


2.
Keep all user requirements.

3.
Do not invent unrelated objects.

4.
Understand architectural vocabulary:

Classical:
- symmetry
- columns
- cornices
- stone frames
- proportions
- ornamentation

Modern:
- glass
- concrete
- minimal details
- clean geometry

Traditional:
- local materials
- cultural elements
- regional details


5.
Return ONLY valid JSON.


Output example:


{
 "building":{
   "type":"",
   "style":""
 },

 "facade":{
   "style":"",
   "details":[]
 },

 "materials":[],

 "objects":[],

 "environment":[],

 "atmosphere":{},

 "camera":"",

 "lighting":{},

 "constraints":[]
}


"""



    # ======================================================
    # JSON CLEANER
    # ======================================================


    def clean_json(
        self,
        text
    ):


        if not isinstance(
            text,
            str
        ):

            return None



        try:


            text = text.replace(
                "```json",
                ""
            )


            text = text.replace(
                "```",
                ""
            )



            match = re.search(
                r"\{.*\}",
                text,
                re.DOTALL
            )



            if not match:

                return None



            return json.loads(
                match.group(0)
            )



        except Exception as e:


            print(
                "⚠️ JSON CLEAN ERROR:",
                e
            )


            return None



    # ======================================================
    # LLM EXTRACTION
    # ======================================================


    def extract_with_llm(
        self,
        text
    ):


        if not self.llm:

            return None



        try:


            response = self.llm.generate(

                self.system_prompt()
                +
                "\nUSER REQUEST:\n"
                +
                text

            )



            print(
                "🧠 SEMANTIC LLM RESPONSE RECEIVED"
            )



            return self.clean_json(
                response
            )



        except Exception as e:


            print(
                "⚠️ SEMANTIC LLM FAILED:",
                e
            )


            return None



    # ======================================================
    # NORMALIZATION
    # ======================================================


    def normalize(
        self,
        data
    ):


        if not isinstance(
            data,
            dict
        ):

            return None



        building = data.get(
            "building",
            {}
        )



        facade = data.get(
            "facade",
            {}
        )



        return {


            "building":

                building,



            "style":

                building.get(
                    "style",
                    ""
                ),



            "facade":

                facade,



            "materials":

                data.get(
                    "materials",
                    []
                ),



            "facade_details":

                facade.get(
                    "details",
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



            "atmosphere":

                data.get(
                    "atmosphere",
                    {}
                ),



            "camera":

                data.get(
                    "camera",
                    "architectural visualization"
                ),



            "lighting":

                data.get(
                    "lighting",
                    {}
                ),



            "constraints":

                data.get(
                    "constraints",
                    []

                )

        }



    # ======================================================
    # MAIN EXTRACT
    # ======================================================


    def extract(
        self,
        text
    ):


        print(
            "🧠 SEMANTIC INPUT:",
            text
        )



        result = self.extract_with_llm(
            text
        )



        result = self.normalize(
            result
        )



        if result:


            print(
                "✅ SEMANTIC INTENT:",
                result
            )


            return result



        print(
            "↩️ USING ARCHITECTURAL FALLBACK"
        )



        if self.fallback:


            return self.fallback.extract(

                {
                    "prompt": text
                }

            )



        return {


            "building": {},


            "style": "",


            "facade": {},


            "materials": [],


            "facade_details": [],


            "objects": [],


            "environment": [],


            "atmosphere": {},


            "camera":
                "architectural visualization",


            "lighting": {},


            "constraints":[]

        }



# ==========================================================
# Alias
# ==========================================================


ArchitecturalSemanticIntent = SemanticIntentEngine