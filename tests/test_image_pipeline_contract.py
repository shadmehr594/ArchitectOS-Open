# ==========================================================
# ArchitectOS Image Pipeline Contract Debug Test
#
# Purpose:
# Brain -> ImageTool -> RenderRuntime payload verification
#
# NO IMAGE GENERATION
# NO COMFY EXECUTION
# ==========================================================


print("\n========== IMAGE PIPELINE CONTRACT TEST ==========\n")


from core.tools.image_tool import ImageTool



# ----------------------------------------------------------
# MOCK RENDER RUNTIME
# ----------------------------------------------------------

class MockRenderRuntime:


    def render(
        self,
        project_id,
        design,
        engine,
        image_asset=None
    ):


        print("\n🔥 MOCK RUNTIME RECEIVED")
        print("--------------------------------")

        print(
            "PROJECT:",
            project_id
        )

        print(
            "ENGINE:",
            engine
        )

        print(
            "IMAGE ASSET:",
            image_asset
        )

        print(
            "DESIGN:",
            design
        )

        print("--------------------------------\n")


        return {

            "status":
                "contract_ok",

            "received_design":
                design

        }



# ----------------------------------------------------------
# INIT TOOL
# ----------------------------------------------------------

tool = ImageTool()


# Replace real runtime ONLY for debug

tool.runtime = MockRenderRuntime()



# ----------------------------------------------------------
# TEST PAYLOAD
# ----------------------------------------------------------

payload = {


    "prompt":

        "یک ویلای مدرن با نمای شیشه و بتن و ماشین جلوی ویلا",


    "project_id":

        "chat_project",


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
    "🚀 INPUT PAYLOAD:"
)

print(
    payload
)



# ----------------------------------------------------------
# EXECUTE
# ----------------------------------------------------------

result = tool.execute(
    payload,
    {}
)



print(
    "\n✅ TEST RESULT:"
)

print(
    result
)


print(
    "\n========== TEST FINISHED ==========\n"
)