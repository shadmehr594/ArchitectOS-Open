# ==========================================================
# ArchitectOS Render Runtime Full Debug Test
#
# Direct:
# ImageTool -> RenderRuntime v7.4
#
# No Brain / No Intent Router
# Purpose:
# Validate render pipeline contract
#
# ==========================================================


print("\n========== RENDER RUNTIME FULL DEBUG ==========\n")


from core.tools.image_tool import ImageTool



# ----------------------------------------------------------
# INPUT
# ----------------------------------------------------------

state = {

    "prompt":
        "یک ویلای مدرن با نمای شیشه و بتن و ماشین جلوی ویلا",


    "project_id":
        "render_debug_project",


    "mode":
        "generate",


    "engine":
        "flux",


    "architectural_intent":
        {

            "building_type":
                "villa",

            "style":
                "modern",

            "materials":
                [
                    "glass facade",
                    "exposed concrete"
                ],

            "objects":
                [
                    "luxury car"
                ]

        }

}



print(
    "🚀 INPUT STATE:"
)

print(
    state
)



# ----------------------------------------------------------
# IMAGE TOOL
# ----------------------------------------------------------

tool = ImageTool()


print(
    "\n🖼️ IMAGE TOOL READY"
)



# ----------------------------------------------------------
# EXECUTE
# ----------------------------------------------------------

result = tool.execute(

    state,

    {

        "project_id":
            "render_debug_project"

    }

)



print(
    "\n========== FINAL RESULT =========="
)


print(
    result
)



# ----------------------------------------------------------
# CONTRACT CHECK
# ----------------------------------------------------------

print(
    "\n========== CONTRACT CHECK =========="
)



if isinstance(result, dict):


    print(
        "STATUS:",
        result.get(
            "status"
        )
    )


    print(
        "MODE:",
        result.get(
            "mode"
        )
    )


    print(
        "ENGINE:",
        result.get(
            "engine"
        )
    )


    print(
        "PROMPT:",
        result.get(
            "prompt"
        )
    )


    print(
        "ARCHITECTURAL INTENT:",
        result.get(
            "architectural_intent"
        )
    )


    print(
        "WORKFLOW:",
        result.get(
            "workflow"
        )
    )


else:

    print(
        "❌ INVALID RESULT"
    )



print(
    "\n========== TEST FINISHED =========="
)