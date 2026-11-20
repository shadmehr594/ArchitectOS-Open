import os
import json
from datetime import datetime


class RevitBuildPlanGenerator:


    VERSION = "1.4"


    def __init__(self):

        print(
            f"🏢 Revit Build Plan Generator v{self.VERSION} ACTIVE"
        )



    # ==========================================
    # BUILD
    # ==========================================

    def build(
        self,
        revit_package,
        output_dir="architectos_revit_build_plan"
    ):


        os.makedirs(
            output_dir,
            exist_ok=True
        )


        if "package" in revit_package:

            revit_package = revit_package["package"]



        elements = revit_package.get(
            "elements",
            []
        )


        families = revit_package.get(
            "families",
            {}
        )


        levels = revit_package.get(
            "levels",
            {}
        )


        type_materials = revit_package.get(
            "type_materials",
            {}
        )


        if "elements" in type_materials:

            type_materials = type_materials["elements"]




        normalized_elements = (
            self._normalize_elements(
                elements,
                type_materials
            )
        )



        categories = (
            self._categorize_elements(
                normalized_elements
            )
        )



        statistics = {

            "total_elements":
                len(normalized_elements),

            "columns":
                len(categories["columns"]),

            "beams":
                len(categories["beams"]),

            "walls":
                len(categories["walls"]),

            "openings":
                len(categories["openings"])

        }



        revit_actions = (
            self._build_revit_actions(
                normalized_elements
            )
        )



        creation_sequence = [

            {
                "order":1,
                "action":"CREATE_LEVELS",
                "category":"Levels"
            },

            {
                "order":2,
                "action":"CREATE_FAMILY_INSTANCE",
                "category":"Structural Columns"
            },

            {
                "order":3,
                "action":"CREATE_FAMILY_INSTANCE",
                "category":"Structural Framing"
            },

            {
                "order":4,
                "action":"CREATE_FAMILY_INSTANCE",
                "category":"Walls"
            },

            {
                "order":5,
                "action":"CREATE_OPENINGS",
                "category":"Openings"
            }

        ]



        plan = {


            "engine":
                f"revit_build_plan_generator_v{self.VERSION}",


            "created":
                datetime.now().isoformat(),


            "status":
                "ready",


            "units":
                "meters",


            "levels":
                levels,


            "families":
                families,


            "type_materials":
                type_materials,


            "create_order":[

                "Levels",
                "Structural Columns",
                "Structural Framing",
                "Walls",
                "Openings"

            ],


            "creation_sequence":
                creation_sequence,


            "revit_actions":
                revit_actions,


            "statistics":
                statistics,


            "elements":
                normalized_elements

        }



        path = os.path.join(
            output_dir,
            "revit_build_plan.json"
        )


        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:


            json.dump(
                plan,
                f,
                indent=4,
                ensure_ascii=False
            )



        return {

            "status":
                "generated",

            "file":
                path,

            "engine":
                f"RevitBuildPlanGenerator_v{self.VERSION}",

            "elements":
                normalized_elements,

            "revit_actions":
                revit_actions,

            "statistics":
                statistics,

            "plan":
                plan

        }




    # ==========================================
    # NORMALIZER
    # ==========================================

    def _normalize_elements(
        self,
        elements,
        type_materials=None
    ):


        result = []

        type_materials = type_materials or {}



        for element in elements or []:


            element_id = element.get(
                "id"
            )


            mapping = type_materials.get(
                element_id,
                {}
            )


            result.append(

                {

                    "id":
                        element_id,


                    "ifc_type":
                        element.get(
                            "ifc_type",
                            element.get("type")
                        ),


                    "category":
                        mapping.get(
                            "category"
                        ),


                    "family":
                        mapping.get(
                            "family"
                        ),


                    "revit_type":
                        mapping.get(
                            "type"
                        ),


                    "material":
                        mapping.get(
                            "material"
                        ),


                    "geometry":
                        element.get(
                            "data",
                            {}
                        ),


                    "parameters":
                        {}

                }

            )


        return result




    # ==========================================
    # REVIT ACTION BUILDER
    # ==========================================

    def _build_revit_actions(
        self,
        elements
    ):


        actions = []


        for element in elements:


            actions.append(

                {

                    "action":
                        "CREATE_FAMILY_INSTANCE",


                    "element_id":
                        element["id"],


                    "family":
                        element.get(
                            "family"
                        ),


                    "type":
                        element.get(
                            "revit_type"
                        ),


                    "material":
                        element.get(
                            "material"
                        ),


                    "geometry":
                        element.get(
                            "geometry",
                            {}
                        ),


                    "parameters":
                        element.get(
                            "parameters",
                            {}
                        )

                }

            )


        return actions




    # ==========================================
    # CATEGORY
    # ==========================================

    def _categorize_elements(
        self,
        elements
    ):


        result = {

            "columns":[],
            "beams":[],
            "walls":[],
            "openings":[]

        }


        for element in elements:


            t = element.get(
                "ifc_type",
                ""
            )


            if t == "IfcColumn":

                result["columns"].append(
                    element
                )


            elif t == "IfcBeam":

                result["beams"].append(
                    element
                )


            elif t == "IfcWall":

                result["walls"].append(
                    element
                )


            elif t in [
                "IfcOpening",
                "IfcDoor",
                "IfcWindow"
            ]:

                result["openings"].append(
                    element
                )


        return result