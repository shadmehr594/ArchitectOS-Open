from core.bim.bim_context_bridge import (
    BIMContextBridge
)


print(
    "\n=== PLANNING TO BIM CONTEXT TEST ===\n"
)



# ==================================================
# MOCK BUILDING MODEL
# ==================================================

bim_model = {


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


    "spatial":

    {

        "nodes":

        [

            "living_room",

            "kitchen",

            "bedroom",

            "pool",

            "terrace",

            "bathroom"

        ],



        "connections":

        [

            {

                "from":
                    "living_room",

                "to":
                    "terrace",

                "type":
                    "direct_access"

            },


            {

                "from":
                    "terrace",

                "to":
                    "pool",

                "type":
                    "connected"

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

        ],



        "space_registry":

        [

            {

                "id":
                    "living_room",

                "type":
                    "IfcSpace",

                "status":
                    "planned"

            },


            {

                "id":
                    "kitchen",

                "type":
                    "IfcSpace",

                "status":
                    "planned"

            },


            {

                "id":
                    "bedroom",

                "type":
                    "IfcSpace",

                "status":
                    "planned"

            }

        ]

    }

}



# ==================================================
# MOCK IFC
# ==================================================

ifc_model = {


    "ifc_project":

    {

        "name":
            "ArchitectOS Villa"

    },


    "storeys":

    [

        "GroundStorey"

    ],


    "spaces":

    [

        "IfcSpace_Living",

        "IfcSpace_Kitchen"

    ]

}



# ==================================================
# BUILD CONTEXT
# ==================================================

bridge = BIMContextBridge()



context = bridge.build_context(

    bim_model,

    ifc_model

)



print(
    "\n✓ BIM Context Generated"
)


print(
    context
)



# ==================================================
# VALIDATION
# ==================================================

assert (
    "bim_context"
    in
    context
)


assert (
    "ifc_context"
    in
    context
)



building = context[
    "bim_context"
][
    "building"
]



assert (
    building["type"]
    ==
    "villa"
)



assert (
    building["category"]
    ==
    "residential"
)



assert (
    building["style"]
    ==
    "modern"
)



spaces = context[
    "bim_context"
][
    "spaces"
]



assert (
    len(spaces)
    >
    0
)



assert (
    spaces[0]["ifc_type"]
    ==
    "IfcSpace"
)



relationships = context[
    "bim_context"
][
    "relationships"
]



assert (
    len(
        relationships["connections"]
    )
    >
    0
)



assert (
    relationships["connections"][0]["from"]
    ==
    "living_room"
)



ifc = context[
    "ifc_context"
]



assert (
    ifc["project"]["name"]
    ==
    "ArchitectOS Villa"
)



print(
    "\n✓ BIM Context Validation Passed"
)



print(
    "\n================================="
)

print(
    "PLANNING → BIM CONTEXT → IFC"
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