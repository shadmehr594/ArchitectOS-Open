# ==========================================================
# ArchitectOS Full Render Pipeline Debug Test
#
# Purpose:
# Verify:
# ImageTool -> RenderRuntime
# -> Prompt Pipeline
# -> Workflow
# -> Executor
# -> Result Bridge contract
#
# NO CODE CHANGES
# DEBUG ONLY
# ==========================================================


print("\n========== FULL RENDER PIPELINE DEBUG ==========\n")


from core.brain import Brain



# ----------------------------------------------------------
# INPUT
# ----------------------------------------------------------

user_input = (
    "یک ویلای مدرن با نمای شیشه و بتن و ماشین جلوی ویلا"
)


context = {

    "project_id":
        "debug_render_project"

}


print(
    "👤 USER INPUT:",
    user_input
)



# ----------------------------------------------------------
# BOOT BRAIN
# ----------------------------------------------------------

brain = Brain()


print(
    "\n🧠 BRAIN ONLINE"
)



# ----------------------------------------------------------
# ENABLE IMAGE TOOL
# ----------------------------------------------------------

try:

    from core.tools.image_tool import ImageTool


    image_tool = ImageTool()


    brain.tools = {

        "image":
            image_tool

    }


    print(
        "🖼️ IMAGE TOOL CONNECTED"
    )



    # ======================================================
    # DIRECT IMAGE TOOL -> RENDER RUNTIME TEST
    # ======================================================


    render_payload = {

        "prompt":

            user_input,


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

                        "modern car"

                    ],


                "site":

                    [

                        "front yard"

                    ],


                "camera":

                    "architectural visualization",


                "mood":

                    "professional archviz"

            },


        "project_id":

            "debug_render_project",


        "mode":

            "generate",


        "engine":

            "flux"

    }



    print(
        "\n========== DIRECT IMAGE TOOL TEST ==========\n"
    )


    render_result = image_tool.execute(

        render_payload,

        context

    )



    print(
        "\n========== FINAL RENDER RESULT ==========\n"
    )


    print(
        render_result
    )



    # ======================================================
    # RENDER CONTRACT CHECK
    # ======================================================


    print(
        "\n========== RENDER CONTRACT CHECK ==========\n"
    )



    if isinstance(render_result, dict):


        print(
            "STATUS:",
            render_result.get(
                "status"
            )
        )


        print(
            "ENGINE:",
            render_result.get(
                "engine"
            )
        )


        print(
            "WORKFLOW:",
            render_result.get(
                "workflow"
            )
        )


        print(
            "MODE:",
            render_result.get(
                "mode"
            )
        )


        print(
            "ARCH INTENT:",
            render_result.get(
                "architectural_intent"
            )
        )


        print(
            "PROMPT:",
            render_result.get(
                "prompt"
            )
        )


        print(
            "EXECUTION:",
            render_result.get(
                "execution"
            )
        )


        print(
            "RESOLVED:",
            render_result.get(
                "resolved"
            )
        )


    else:


        print(
            "❌ INVALID RENDER RESULT"
        )



except Exception as e:


    print(

        "❌ IMAGE TOOL / RENDER ERROR:",

        e

    )

    raise




print(
    "\n========== TEST FINISHED =========="
)