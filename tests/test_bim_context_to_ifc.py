from core.bim.bim_ifc_intelligence_engine import (
    BIMIFCIntelligenceEngine
)


print(
    "\n=== BIM CONTEXT TO IFC TEST ===\n"
)



# ==================================================
# MOCK BIM CONTEXT
# ==================================================

bim_context = {


    "bim_context":

    {

        "building":

        {

            "type":
                "villa",

            "category":
                "residential",

            "style":
                "modern"

        },


        "levels":

        [

            {

                "name":
                    "ground",

                "elevation":
                    0

            }

        ],



        "spaces":

        [

            {

                "id":
                    "living_room",

                "ifc_type":
                    "IfcSpace",

                "status":
                    "planned"

            },


            {

                "id":
                    "kitchen",

                "ifc_type":
                    "IfcSpace",

                "status":
                    "planned"

            },


            {

                "id":
                    "bedroom",

                "ifc_type":
                    "IfcSpace",

                "status":
                    "planned"

            }

        ],



        "relationships":

        {

            "connections":

            [

                {

                    "from":
                        "living_room",

                    "to":
                        "terrace",

                    "type":
                        "direct_access"

                }

            ],


            "adjacency":

            [

                {

                    "from":
                        "bedroom",

                    "to":
                        "bathroom",

                    "type":
                        "adjacent"

                }

            ]

        }

    }

}




# ==================================================
# IFC INTELLIGENCE
# ==================================================

engine = BIMIFCIntelligenceEngine()



ifc_model = engine.build(

    bim_context

)



print(
    "\n✓ IFC Semantic Model Generated"
)


print(
    ifc_model
)



# ==================================================
# IFC CORE VALIDATION
# ==================================================

assert (
    "project"
    in
    ifc_model
)


assert (
    "site"
    in
    ifc_model
)


assert (
    "building"
    in
    ifc_model
)


assert (
    "storeys"
    in
    ifc_model
)


assert (
    "spaces"
    in
    ifc_model
)



assert (
    ifc_model["building"]["type"]
    ==
    "IfcBuilding"
)



assert (
    len(
        ifc_model["storeys"]
    )
    ==
    1
)



assert (
    len(
        ifc_model["spaces"]
    )
    ==
    3
)



assert (
    ifc_model["spaces"][0]["type"]
    ==
    "IfcSpace"
)



assert (
    ifc_model["schema"]
    ==
    "IFC4"
)



print(
    "\n✓ IFC Core Validation Passed"
)



print(
    "\n================================="
)

print(
    "BIM CONTEXT → IFC SEMANTIC MODEL"
)

print(
    "PIPELINE VALIDATED SUCCESSFULLY"
)

print(
    "================================="
)



print(
    "\n=== TEST PASSED ===\n"
)